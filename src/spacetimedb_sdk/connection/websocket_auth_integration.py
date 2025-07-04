"""
WebSocket Authentication Integration for SpacetimeDB SDK

This module provides seamless integration between the AuthenticationHandler
and WebSocket client, ensuring proper authentication flow and state management.

Features:
- Seamless WebSocket authentication integration
- Automatic token refresh and retry logic
- JWT and legacy token support
- Event-driven authentication state management
- Thread-safe operations
"""

import logging
import threading
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass

from .authentication_handler import (
    AuthenticationHandler,
    AuthenticationState,
    AuthenticationCredentials,
    AuthenticationEvent
)
from ..exceptions import (
    AuthenticationError,
    SpacetimeDBAuthHandshakeError,
    WebSocketHandshakeError
)


@dataclass
class WebSocketAuthConfig:
    """Configuration for WebSocket authentication integration."""
    
    # Authentication timeouts
    handshake_timeout: float = 30.0
    token_refresh_window: float = 300.0  # 5 minutes
    
    # Retry configuration
    max_retry_attempts: int = 3
    retry_delay: float = 1.0
    
    # Token management
    auto_refresh_tokens: bool = True
    prefer_jwt_over_legacy: bool = True
    
    # Event configuration
    emit_auth_events: bool = True
    enable_debug_logging: bool = False


class WebSocketAuthIntegration:
    """
    Integration layer between WebSocket client and authentication handler.
    
    This class provides a clean interface for WebSocket clients to handle
    authentication without directly managing authentication state.
    """
    
    def __init__(
        self,
        auth_handler: Optional[AuthenticationHandler] = None,
        config: Optional[WebSocketAuthConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize WebSocket authentication integration.
        
        Args:
            auth_handler: Authentication handler instance
            config: Configuration for auth integration
            logger: Logger for auth operations
        """
        self.auth_handler = auth_handler or AuthenticationHandler()
        self.config = config or WebSocketAuthConfig()
        self.logger = logger or logging.getLogger(__name__)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # WebSocket client callback
        self._websocket_client = None
        self._reconnect_callback: Optional[Callable[[], None]] = None
        
        # Authentication state tracking
        self._current_host: Optional[str] = None
        self._current_database: Optional[str] = None
        self._auth_in_progress: bool = False
        self._last_auth_attempt: Optional[float] = None
        
        # Register for auth events
        self.auth_handler.add_refresh_callback(self._handle_token_refresh)
        
        self.logger.info("WebSocket authentication integration initialized")
    
    def set_websocket_client(self, websocket_client: Any) -> None:
        """
        Set the WebSocket client instance for integration.
        
        Args:
            websocket_client: WebSocket client instance
        """
        with self._lock:
            self._websocket_client = websocket_client
            self.logger.debug("WebSocket client registered for auth integration")
    
    def set_reconnect_callback(self, callback: Callable[[], None]) -> None:
        """
        Set callback for triggering WebSocket reconnection.
        
        Args:
            callback: Function to call for reconnection
        """
        with self._lock:
            self._reconnect_callback = callback
            self.logger.debug("Reconnect callback registered")
    
    def prepare_connection_headers(
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
        with self._lock:
            self._current_host = host
            self._current_database = database
            
            headers = {}
            
            # Try JWT authentication first
            if self.config.prefer_jwt_over_legacy:
                jwt_headers = self.auth_handler.prepare_jwt_headers(
                    host, database, require_fresh=True
                )
                if jwt_headers:
                    headers.update(jwt_headers)
                    self.logger.debug(f"Using JWT authentication for {host}/{database}")
                    return headers
            
            # Fall back to legacy token
            if legacy_token:
                legacy_headers = self.auth_handler.authenticate_with_legacy_token(
                    legacy_token, host, database
                )
                headers.update(legacy_headers)
                self.logger.debug(f"Using legacy token authentication for {host}/{database}")
                return headers
            
            # Try stored JWT credentials
            jwt_headers = self.auth_handler.prepare_jwt_headers(
                host, database, require_fresh=False
            )
            if jwt_headers:
                headers.update(jwt_headers)
                self.logger.debug(f"Using stored JWT credentials for {host}/{database}")
                return headers
            
            self.logger.debug(f"No authentication credentials available for {host}/{database}")
            return headers
    
    def handle_authentication_error(
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
        with self._lock:
            self._current_host = host
            self._current_database = database
            
            # Handle authentication handshake errors
            if isinstance(error, SpacetimeDBAuthHandshakeError) and error_message:
                self.logger.info(f"Handling authentication handshake for {host}/{database}")
                
                # Parse handshake and store credentials
                if self.auth_handler.handle_authentication_handshake(
                    error_message, host, database
                ):
                    self.logger.info("Authentication handshake completed successfully")
                    return True
                else:
                    self.logger.error("Failed to handle authentication handshake")
                    return False
            
            # Handle other authentication errors
            if isinstance(error, (AuthenticationError, WebSocketHandshakeError)):
                # Check if retry is possible
                if hasattr(error, 'status_code'):
                    return self.auth_handler.should_retry_authentication(error.status_code)
                else:
                    return self.auth_handler.should_retry_authentication(401)
            
            return False
    
    def _handle_token_refresh(self, credentials: AuthenticationCredentials) -> None:
        """
        Handle token refresh notification.
        
        Args:
            credentials: The credentials that need refreshing
        """
        with self._lock:
            self.logger.info("Token refresh needed, triggering reconnection")
            
            # Trigger reconnection if callback is available
            if self._reconnect_callback:
                try:
                    self._reconnect_callback()
                except Exception as e:
                    self.logger.error(f"Failed to trigger reconnection: {e}")
    
    def get_authentication_status(self) -> Dict[str, Any]:
        """
        Get current authentication status.
        
        Returns:
            Dictionary with authentication status information
        """
        with self._lock:
            status = {
                "state": self.auth_handler.get_authentication_state().value,
                "host": self._current_host,
                "database": self._current_database,
                "auth_in_progress": self._auth_in_progress,
                "last_auth_attempt": self._last_auth_attempt,
                "config": {
                    "auto_refresh_tokens": self.config.auto_refresh_tokens,
                    "prefer_jwt_over_legacy": self.config.prefer_jwt_over_legacy,
                    "max_retry_attempts": self.config.max_retry_attempts
                }
            }
            
            # Add handler information
            status.update(self.auth_handler.get_authentication_info())
            
            return status
    
    def clear_authentication(self, host: str, database: str) -> None:
        """
        Clear authentication for a specific host/database.
        
        Args:
            host: Server host
            database: Database name
        """
        with self._lock:
            self.auth_handler.clear_credentials(host, database)
            
            if self._current_host == host and self._current_database == database:
                self._current_host = None
                self._current_database = None
                self._auth_in_progress = False
                self._last_auth_attempt = None
            
            self.logger.info(f"Cleared authentication for {host}/{database}")
    
    def store_credentials(
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
        with self._lock:
            self.auth_handler.store_credentials(identity, token, host, database)
            
            # Update current connection info
            self._current_host = host
            self._current_database = database
            self._auth_in_progress = False
            self._last_auth_attempt = time.time()
            
            self.logger.info(f"Stored credentials for {host}/{database}")
    
    def begin_authentication_attempt(self, host: str, database: str) -> None:
        """
        Mark the beginning of an authentication attempt.
        
        Args:
            host: Server host
            database: Database name
        """
        with self._lock:
            self._current_host = host
            self._current_database = database
            self._auth_in_progress = True
            self._last_auth_attempt = time.time()
            
            self.logger.debug(f"Beginning authentication attempt for {host}/{database}")
    
    def complete_authentication_attempt(self, success: bool) -> None:
        """
        Mark the completion of an authentication attempt.
        
        Args:
            success: Whether the authentication was successful
        """
        with self._lock:
            self._auth_in_progress = False
            
            if success:
                self.logger.debug("Authentication attempt completed successfully")
            else:
                self.logger.debug("Authentication attempt failed")
    
    def is_authentication_required(self, host: str, database: str) -> bool:
        """
        Check if authentication is required for the given host/database.
        
        Args:
            host: Server host
            database: Database name
            
        Returns:
            True if authentication is required, False otherwise
        """
        with self._lock:
            # Check if we have valid credentials
            credentials = self.auth_handler.get_stored_credentials(
                host, database, allow_expired=False
            )
            
            return credentials is None
    
    def get_current_identity(self) -> Optional[str]:
        """
        Get the current authenticated identity.
        
        Returns:
            Current identity if authenticated, None otherwise
        """
        with self._lock:
            credentials = self.auth_handler.get_current_credentials()
            return credentials.identity if credentials else None
    
    def shutdown(self) -> None:
        """Shutdown the authentication integration."""
        try:
            with self._lock:
                # Remove callbacks
                self.auth_handler.remove_refresh_callback(self._handle_token_refresh)
                
                # Clear state
                self._websocket_client = None
                self._reconnect_callback = None
                self._current_host = None
                self._current_database = None
                self._auth_in_progress = False
                
                self.logger.info("WebSocket authentication integration shutdown")
        except Exception as e:
            self.logger.error(f"Error during auth integration shutdown: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


def create_websocket_auth_integration(
    auth_handler: Optional[AuthenticationHandler] = None,
    config: Optional[WebSocketAuthConfig] = None,
    logger: Optional[logging.Logger] = None
) -> WebSocketAuthIntegration:
    """
    Convenience function to create a WebSocket authentication integration.
    
    Args:
        auth_handler: Authentication handler instance
        config: Configuration for auth integration
        logger: Logger for auth operations
        
    Returns:
        WebSocketAuthIntegration instance
    """
    return WebSocketAuthIntegration(
        auth_handler=auth_handler,
        config=config,
        logger=logger
    )