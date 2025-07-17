"""
WebSocket Client Integration Patterns for Authentication Handler

This module provides integration patterns and helper functions for existing
WebSocket clients to use the new authentication handler seamlessly.

Features:
- Drop-in replacement for existing authentication patterns
- Backward compatibility with existing WebSocket client code
- Migration helpers for transitioning from legacy auth
- Integration with existing error handling patterns
"""

import logging
import threading
from typing import Dict, Optional, Callable, Any

from .authentication_handler import AuthenticationHandler, AuthenticationState
from .websocket_auth_integration import WebSocketAuthIntegration, WebSocketAuthConfig
from ..exceptions import (
    AuthenticationError,
    SpacetimeDBAuthHandshakeError,
    WebSocketHandshakeError
)


class WebSocketClientAuthMixin:
    """
    Mixin class for WebSocket clients to add authentication handler integration.
    
    This mixin provides methods that can be added to existing WebSocket clients
    to integrate with the authentication handler without major code changes.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize authentication integration."""
        super().__init__(*args, **kwargs)
        
        # Initialize authentication components
        self._auth_handler = AuthenticationHandler()
        self._auth_integration = WebSocketAuthIntegration(
            auth_handler=self._auth_handler,
            logger=getattr(self, 'logger', None)
        )
        
        # Set up integration callbacks
        self._auth_integration.set_websocket_client(self)
        self._auth_integration.set_reconnect_callback(self._handle_auth_reconnect)
        
        # Authentication state
        self._auth_lock = threading.RLock()
        self._auth_retry_count = 0
        self._max_auth_retries = 3
    
    def _handle_auth_reconnect(self) -> None:
        """Handle authentication-triggered reconnection."""
        try:
            if hasattr(self, 'reconnect') and callable(self.reconnect):
                self.reconnect()
            elif hasattr(self, 'connect') and callable(self.connect):
                # Reconnect with existing parameters
                if hasattr(self, 'host') and hasattr(self, 'database'):
                    self.connect(self.host, self.database)
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to reconnect after auth refresh: {e}")
    
    def _prepare_auth_headers(
        self,
        host: str,
        database: str,
        legacy_token: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Prepare authentication headers for WebSocket connection.
        
        Args:
            host: Server host
            database: Database name
            legacy_token: Optional legacy authentication token
            
        Returns:
            Dictionary of headers for WebSocket connection
        """
        return self._auth_integration.prepare_connection_headers(
            host, database, legacy_token
        )
    
    def _handle_auth_error(
        self,
        error: Exception,
        host: str,
        database: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Handle authentication errors from WebSocket connection.
        
        Args:
            error: The authentication error
            host: Server host
            database: Database name
            error_message: Optional error message with handshake details
            
        Returns:
            True if retry should be attempted, False otherwise
        """
        with self._auth_lock:
            if self._auth_retry_count >= self._max_auth_retries:
                if hasattr(self, 'logger'):
                    self.logger.error(f"Max authentication retries ({self._max_auth_retries}) reached")
                return False
            
            should_retry = self._auth_integration.handle_authentication_error(
                error, host, database, error_message
            )
            
            if should_retry:
                self._auth_retry_count += 1
                if hasattr(self, 'logger'):
                    self.logger.info(f"Retrying authentication (attempt {self._auth_retry_count})")
            
            return should_retry
    
    def _reset_auth_state(self) -> None:
        """Reset authentication state for new connection."""
        with self._auth_lock:
            self._auth_retry_count = 0
    
    def _store_auth_credentials(
        self,
        identity: str,
        token: str,
        host: str,
        database: str
    ) -> None:
        """
        Store authentication credentials.
        
        Args:
            identity: SpacetimeDB identity
            token: JWT token
            host: Server host
            database: Database name
        """
        self._auth_integration.store_credentials(identity, token, host, database)
    
    def _clear_auth_credentials(self, host: str, database: str) -> None:
        """
        Clear authentication credentials.
        
        Args:
            host: Server host
            database: Database name
        """
        self._auth_integration.clear_authentication(host, database)
    
    def _get_auth_status(self) -> Dict[str, Any]:
        """Get current authentication status."""
        return self._auth_integration.get_authentication_status()
    
    def _get_current_identity(self) -> Optional[str]:
        """Get current authenticated identity."""
        return self._auth_integration.get_current_identity()
    
    def _is_auth_required(self, host: str, database: str) -> bool:
        """Check if authentication is required."""
        return self._auth_integration.is_authentication_required(host, database)


def integrate_auth_handler_with_websocket_client(
    websocket_client: Any,
    auth_handler: Optional[AuthenticationHandler] = None,
    config: Optional[WebSocketAuthConfig] = None
) -> WebSocketAuthIntegration:
    """
    Integrate authentication handler with existing WebSocket client.
    
    This function provides a way to add authentication handler integration
    to existing WebSocket client instances without modifying their code.
    
    Args:
        websocket_client: Existing WebSocket client instance
        auth_handler: Authentication handler instance
        config: Configuration for auth integration
        
    Returns:
        WebSocketAuthIntegration instance
    """
    # Create authentication integration
    auth_integration = WebSocketAuthIntegration(
        auth_handler=auth_handler,
        config=config,
        logger=getattr(websocket_client, 'logger', None)
    )
    
    # Set up integration
    auth_integration.set_websocket_client(websocket_client)
    
    # Add integration methods to client
    websocket_client._auth_integration = auth_integration
    websocket_client._prepare_auth_headers = auth_integration.prepare_connection_headers
    websocket_client._handle_auth_error = auth_integration.handle_authentication_error
    websocket_client._store_auth_credentials = auth_integration.store_credentials
    websocket_client._clear_auth_credentials = auth_integration.clear_authentication
    websocket_client._get_auth_status = auth_integration.get_authentication_status
    websocket_client._get_current_identity = auth_integration.get_current_identity
    websocket_client._is_auth_required = auth_integration.is_authentication_required
    
    # Set up reconnection callback if possible
    if hasattr(websocket_client, 'reconnect'):
        auth_integration.set_reconnect_callback(websocket_client.reconnect)
    elif hasattr(websocket_client, 'connect'):
        def reconnect_callback():
            if hasattr(websocket_client, 'host') and hasattr(websocket_client, 'database'):
                websocket_client.connect(websocket_client.host, websocket_client.database)
        auth_integration.set_reconnect_callback(reconnect_callback)
    
    return auth_integration


def create_auth_enabled_websocket_client(
    websocket_client_class: type,
    auth_handler: Optional[AuthenticationHandler] = None,
    config: Optional[WebSocketAuthConfig] = None
) -> type:
    """
    Create an authentication-enabled WebSocket client class.
    
    This function creates a new class that inherits from the provided
    WebSocket client class and adds authentication handler integration.
    
    Args:
        websocket_client_class: WebSocket client class to enhance
        auth_handler: Authentication handler instance
        config: Configuration for auth integration
        
    Returns:
        Enhanced WebSocket client class with authentication integration
    """
    class AuthEnabledWebSocketClient(WebSocketClientAuthMixin, websocket_client_class):
        """Authentication-enabled WebSocket client."""
        
        def __init__(self, *args, **kwargs):
            # Initialize with custom auth handler and config
            super().__init__(*args, **kwargs)
            
            if auth_handler:
                self._auth_handler = auth_handler
                self._auth_integration = WebSocketAuthIntegration(
                    auth_handler=auth_handler,
                    config=config,
                    logger=getattr(self, 'logger', None)
                )
                # Re-setup integration
                self._auth_integration.set_websocket_client(self)
                self._auth_integration.set_reconnect_callback(self._handle_auth_reconnect)
    
    return AuthEnabledWebSocketClient


def migrate_legacy_auth_to_handler(
    websocket_client: Any,
    auth_handler: Optional[AuthenticationHandler] = None
) -> None:
    """
    Migrate legacy authentication patterns to use authentication handler.
    
    This function helps migrate existing WebSocket clients that use legacy
    authentication patterns to use the new authentication handler.
    
    Args:
        websocket_client: WebSocket client instance to migrate
        auth_handler: Authentication handler instance
    """
    # Create or use provided auth handler
    if auth_handler is None:
        auth_handler = AuthenticationHandler()
    
    # Create integration
    auth_integration = integrate_auth_handler_with_websocket_client(
        websocket_client, auth_handler
    )
    
    # Migrate existing authentication state if present
    if hasattr(websocket_client, 'identity') and hasattr(websocket_client, 'spacetimedb_token'):
        identity = getattr(websocket_client, 'identity', None)
        token = getattr(websocket_client, 'spacetimedb_token', None)
        host = getattr(websocket_client, 'host', None)
        database = getattr(websocket_client, 'database', None)
        
        if identity and token and host and database:
            auth_integration.store_credentials(identity, token, host, database)
            
            # Clear legacy state
            if hasattr(websocket_client, 'identity'):
                websocket_client.identity = None
            if hasattr(websocket_client, 'spacetimedb_token'):
                websocket_client.spacetimedb_token = None
    
    # Replace legacy authentication methods
    if hasattr(websocket_client, 'prepare_auth_headers'):
        websocket_client._legacy_prepare_auth_headers = websocket_client.prepare_auth_headers
        websocket_client.prepare_auth_headers = auth_integration.prepare_connection_headers
    
    if hasattr(websocket_client, 'handle_auth_error'):
        websocket_client._legacy_handle_auth_error = websocket_client.handle_auth_error
        websocket_client.handle_auth_error = auth_integration.handle_authentication_error


# Convenience functions for common patterns
def get_auth_headers_for_connection(
    host: str,
    database: str,
    legacy_token: Optional[str] = None,
    auth_handler: Optional[AuthenticationHandler] = None
) -> Dict[str, str]:
    """
    Get authentication headers for WebSocket connection.
    
    Args:
        host: Server host
        database: Database name
        legacy_token: Optional legacy authentication token
        auth_handler: Optional authentication handler instance
        
    Returns:
        Dictionary of headers for WebSocket connection
    """
    handler = auth_handler or AuthenticationHandler()
    integration = WebSocketAuthIntegration(auth_handler=handler)
    
    return integration.prepare_connection_headers(host, database, legacy_token)


def handle_websocket_auth_error(
    error: Exception,
    host: str,
    database: str,
    error_message: Optional[str] = None,
    auth_handler: Optional[AuthenticationHandler] = None
) -> bool:
    """
    Handle WebSocket authentication error.
    
    Args:
        error: The authentication error
        host: Server host
        database: Database name
        error_message: Optional error message with handshake details
        auth_handler: Optional authentication handler instance
        
    Returns:
        True if retry should be attempted, False otherwise
    """
    handler = auth_handler or AuthenticationHandler()
    integration = WebSocketAuthIntegration(auth_handler=handler)
    
    return integration.handle_authentication_error(error, host, database, error_message)


def store_websocket_auth_credentials(
    identity: str,
    token: str,
    host: str,
    database: str,
    auth_handler: Optional[AuthenticationHandler] = None
) -> None:
    """
    Store WebSocket authentication credentials.
    
    Args:
        identity: SpacetimeDB identity
        token: JWT token
        host: Server host
        database: Database name
        auth_handler: Optional authentication handler instance
    """
    handler = auth_handler or AuthenticationHandler()
    integration = WebSocketAuthIntegration(auth_handler=handler)
    
    integration.store_credentials(identity, token, host, database)