"""
Integration tests for the authentication handler and WebSocket integration.

These tests verify that the authentication handler integrates properly with
WebSocket clients and provides the expected functionality.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from spacetimedb_sdk.connection import (
    AuthenticationHandler,
    AuthenticationState,
    AuthenticationCredentials,
    WebSocketAuthIntegration,
    WebSocketAuthConfig,
    WebSocketClientAuthMixin,
    create_websocket_auth_integration,
    integrate_auth_handler_with_websocket_client,
    get_auth_headers_for_connection,
    handle_websocket_auth_error,
    store_websocket_auth_credentials
)
from spacetimedb_sdk.exceptions import (
    AuthenticationError,
    SpacetimeDBAuthHandshakeError,
    WebSocketHandshakeError
)


class TestAuthenticationHandlerIntegration:
    """Test authentication handler integration functionality."""
    
    def test_authentication_handler_initialization(self):
        """Test that authentication handler initializes correctly."""
        handler = AuthenticationHandler()
        
        assert handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
        assert handler.auto_refresh_tokens is True
        assert handler.token_refresh_threshold == 300.0
        assert handler.max_retry_attempts == 3
    
    def test_websocket_auth_integration_initialization(self):
        """Test WebSocket authentication integration initialization."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        assert integration.auth_handler == handler
        assert integration.config is not None
        assert integration.config.auto_refresh_tokens is True
    
    def test_create_websocket_auth_integration(self):
        """Test convenience function for creating WebSocket auth integration."""
        integration = create_websocket_auth_integration()
        
        assert isinstance(integration, WebSocketAuthIntegration)
        assert integration.auth_handler is not None
        assert integration.config is not None
    
    def test_websocket_client_auth_mixin(self):
        """Test WebSocket client authentication mixin."""
        
        class MockWebSocketClient:
            def __init__(self):
                self.logger = Mock()
                self.host = "localhost"
                self.database = "test_db"
            
            def reconnect(self):
                pass
        
        # Create client with mixin
        class AuthEnabledClient(WebSocketClientAuthMixin, MockWebSocketClient):
            pass
        
        client = AuthEnabledClient()
        
        # Test that mixin methods are available
        assert hasattr(client, '_prepare_auth_headers')
        assert hasattr(client, '_handle_auth_error')
        assert hasattr(client, '_store_auth_credentials')
        assert hasattr(client, '_clear_auth_credentials')
        assert hasattr(client, '_get_auth_status')
    
    def test_prepare_connection_headers_jwt(self):
        """Test preparing connection headers with JWT authentication."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Store test credentials
        handler.store_credentials(
            identity="test_identity_12345678",
            token="test_jwt_token",
            host="localhost",
            database="test_db"
        )
        
        # Get headers
        headers = integration.prepare_connection_headers("localhost", "test_db")
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_jwt_token"
    
    def test_prepare_connection_headers_legacy(self):
        """Test preparing connection headers with legacy token."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Get headers with legacy token
        headers = integration.prepare_connection_headers(
            "localhost", "test_db", legacy_token="legacy_token"
        )
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
    
    def test_handle_authentication_handshake(self):
        """Test handling authentication handshake."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Mock handshake error with identity and token
        error_message = (
            "Authentication failed: spacetime-identity: abcdef123456789 "
            "spacetime-identity-token: jwt.token.here"
        )
        
        handshake_error = SpacetimeDBAuthHandshakeError(error_message)
        
        # Handle the error
        should_retry = integration.handle_authentication_error(
            handshake_error, "localhost", "test_db", error_message
        )
        
        assert should_retry is True
        
        # Verify credentials were stored
        credentials = handler.get_stored_credentials("localhost", "test_db")
        assert credentials is not None
        assert credentials.identity == "abcdef123456789"
        assert credentials.token == "jwt.token.here"
    
    def test_authentication_state_management(self):
        """Test authentication state management."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Initial state
        assert handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
        
        # Store credentials
        handler.store_credentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db"
        )
        
        # Should be authenticated now
        assert handler.get_authentication_state() == AuthenticationState.AUTHENTICATED
        
        # Clear credentials
        handler.clear_credentials("localhost", "test_db")
        
        # Should be unauthenticated again
        assert handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
    
    def test_token_refresh_callback(self):
        """Test token refresh callback functionality."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Mock reconnect callback
        reconnect_called = threading.Event()
        
        def mock_reconnect():
            reconnect_called.set()
        
        integration.set_reconnect_callback(mock_reconnect)
        
        # Create credentials with short expiry
        credentials = AuthenticationCredentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db",
            timestamp=time.time(),
            expires_at=time.time() + 1  # Expires in 1 second
        )
        
        # Simulate token refresh
        integration._handle_token_refresh(credentials)
        
        # Should trigger reconnect callback
        assert reconnect_called.is_set()
    
    def test_integration_with_websocket_client(self):
        """Test integration with existing WebSocket client."""
        
        class MockWebSocketClient:
            def __init__(self):
                self.logger = Mock()
                self.host = "localhost"
                self.database = "test_db"
            
            def reconnect(self):
                pass
        
        client = MockWebSocketClient()
        
        # Integrate authentication handler
        integration = integrate_auth_handler_with_websocket_client(client)
        
        # Verify integration methods are added
        assert hasattr(client, '_auth_integration')
        assert hasattr(client, '_prepare_auth_headers')
        assert hasattr(client, '_handle_auth_error')
        assert hasattr(client, '_store_auth_credentials')
    
    def test_convenience_functions(self):
        """Test convenience functions for authentication."""
        
        # Test getting auth headers
        headers = get_auth_headers_for_connection("localhost", "test_db")
        assert isinstance(headers, dict)
        
        # Test storing credentials
        store_websocket_auth_credentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db"
        )
        
        # Test getting headers again (should have credentials now)
        headers = get_auth_headers_for_connection("localhost", "test_db")
        assert "Authorization" in headers
    
    def test_error_handling(self):
        """Test error handling in authentication integration."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Test handling authentication error
        auth_error = AuthenticationError("Invalid credentials")
        should_retry = integration.handle_authentication_error(
            auth_error, "localhost", "test_db"
        )
        
        # Should indicate retry is possible
        assert should_retry is True
    
    def test_authentication_status_reporting(self):
        """Test authentication status reporting."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Get initial status
        status = integration.get_authentication_status()
        
        assert status["state"] == "unauthenticated"
        assert "config" in status
        assert "auto_refresh_tokens" in status["config"]
        
        # Store credentials and check status again
        handler.store_credentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db"
        )
        
        status = integration.get_authentication_status()
        assert status["state"] == "authenticated"
        assert "current_identity" in status
    
    def test_thread_safety(self):
        """Test thread safety of authentication operations."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Test concurrent access
        errors = []
        
        def store_credentials_worker(worker_id):
            try:
                handler.store_credentials(
                    identity=f"test_identity_{worker_id}",
                    token=f"test_token_{worker_id}",
                    host="localhost",
                    database=f"test_db_{worker_id}"
                )
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=store_credentials_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should not have any errors
        assert len(errors) == 0
    
    def test_cleanup_and_shutdown(self):
        """Test cleanup and shutdown functionality."""
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler)
        
        # Store some credentials
        handler.store_credentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db"
        )
        
        # Test integration shutdown
        integration.shutdown()
        
        # Test handler shutdown
        handler.shutdown()
        
        # Should be in unauthenticated state
        assert handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
    
    def test_legacy_migration_patterns(self):
        """Test migration patterns from legacy authentication."""
        
        class MockLegacyWebSocketClient:
            def __init__(self):
                self.logger = Mock()
                self.identity = "legacy_identity"
                self.spacetimedb_token = "legacy_token"
                self.host = "localhost"
                self.database = "test_db"
            
            def prepare_auth_headers(self, host, database):
                return {"Authorization": "Bearer legacy_token"}
        
        client = MockLegacyWebSocketClient()
        
        # Migrate to use authentication handler
        from spacetimedb_sdk.connection.websocket_client_integration import migrate_legacy_auth_to_handler
        
        migrate_legacy_auth_to_handler(client)
        
        # Should have integration methods
        assert hasattr(client, '_auth_integration')
        assert hasattr(client, '_legacy_prepare_auth_headers')
        
        # Legacy state should be cleared
        assert client.identity is None
        assert client.spacetimedb_token is None
    
    def test_configuration_options(self):
        """Test configuration options for authentication integration."""
        config = WebSocketAuthConfig(
            handshake_timeout=60.0,
            max_retry_attempts=5,
            auto_refresh_tokens=False,
            prefer_jwt_over_legacy=False
        )
        
        handler = AuthenticationHandler()
        integration = WebSocketAuthIntegration(auth_handler=handler, config=config)
        
        assert integration.config.handshake_timeout == 60.0
        assert integration.config.max_retry_attempts == 5
        assert integration.config.auto_refresh_tokens is False
        assert integration.config.prefer_jwt_over_legacy is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])