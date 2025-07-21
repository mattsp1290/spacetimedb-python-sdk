"""
Database identity parameter tests for SpacetimeDB v1.1.2 compatibility
"""
import pytest
from unittest.mock import patch, Mock
import sys
import os

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.protocol import TEXT_PROTOCOL


class TestIdentityParameter:
    """Test database identity parameter handling"""
    
    def test_identity_in_url_construction(self, mock_websocket_comprehensive):
        """Test that db_identity is used in WebSocket URL"""
        client = SpacetimeDBClient(autogen_package=None)  # Remove test_mode to allow WebSocket creation
        
        # Track WebSocket creation
        ws_calls = []
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def track_websocket(*args, **kwargs):
            ws_calls.append((args, kwargs))
            return original_app(*args, **kwargs)
            
        mock_websocket_comprehensive.WebSocketApp = track_websocket
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="test-db",
                ssl_enabled=False,
                db_identity="550e8400-e29b-41d4-a716-446655440000"
            )
            
            # Check URL construction
            assert len(ws_calls) == 1
            url = ws_calls[0][0][0]  # First positional arg is URL
            assert "/v1/database/550e8400-e29b-41d4-a716-446655440000/subscribe" in url
            
        finally:
            client.disconnect()
            
    def test_identity_fallback_to_database_address(self, mock_websocket_comprehensive):
        """Test that database_address is used as fallback when db_identity is None"""
        client = SpacetimeDBClient(autogen_package=None)  # Remove test_mode
        
        ws_calls = []
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def track_websocket(*args, **kwargs):
            ws_calls.append((args, kwargs))
            return original_app(*args, **kwargs)
            
        mock_websocket_comprehensive.WebSocketApp = track_websocket
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="my-database",
                ssl_enabled=False,
                db_identity=None  # No identity provided
            )
            
            # Should use database_address in URL
            assert len(ws_calls) == 1
            url = ws_calls[0][0][0]
            assert "/v1/database/my-database/subscribe" in url
            
        finally:
            client.disconnect()
            
    def test_identity_with_different_formats(self, mock_websocket_comprehensive):
        """Test various identity formats are accepted"""
        test_identities = [
            "550e8400-e29b-41d4-a716-446655440000",  # UUID format
            "abc123def456",  # Short hash
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",  # 64-char hex
            "my-database",  # Database name (when used as identity)
        ]
        
        for identity in test_identities:
            client = SpacetimeDBClient(autogen_package=None)
            
            ws_calls = []
            # Need to restore original after each iteration to avoid recursion
            original_app = mock_websocket_comprehensive.WebSocketApp.__class__
            
            def track_websocket(*args, **kwargs):
                ws_calls.append((args, kwargs))
                return original_app(*args, **kwargs)
                
            mock_websocket_comprehensive.WebSocketApp = track_websocket
            
            try:
                client._connect_internal(
                    auth_token=None,
                    host="localhost:3000",
                    database_address="test-db",
                    ssl_enabled=False,
                    db_identity=identity
                )
                
                # Check that identity is in URL
                assert len(ws_calls) == 1
                url = ws_calls[0][0][0]
                assert f"/v1/database/{identity}/subscribe" in url
                
            finally:
                client.disconnect()


class TestIdentityInConnectionMethods:
    """Test db_identity parameter in various connection methods"""
    
    def test_connect_class_method_with_identity(self, mock_websocket_comprehensive):
        """Test SpacetimeDBClient.connect() with db_identity"""
        ws_calls = []
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def track_websocket(*args, **kwargs):
            ws_calls.append((args, kwargs))
            return original_app(*args, **kwargs)
            
        mock_websocket_comprehensive.WebSocketApp = track_websocket
        
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test-db",
            db_identity="my-identity-123"
        )
        
        try:
            # Check URL contains identity
            assert len(ws_calls) == 1
            url = ws_calls[0][0][0]
            assert "/v1/database/my-identity-123/subscribe" in url
        finally:
            client.shutdown()
            
    # Note: The builder doesn't have a with_identity method
    # db_identity is passed as a parameter to connect() or _connect_internal()
            
    def test_builder_without_identity_uses_module_name(self, mock_websocket_comprehensive):
        """Test builder without identity falls back to module name"""
        ws_calls = []
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def track_websocket(*args, **kwargs):
            ws_calls.append((args, kwargs))
            return original_app(*args, **kwargs)
            
        mock_websocket_comprehensive.WebSocketApp = track_websocket
        
        # The builder creates a client but doesn't connect automatically
        # Need to use connect() method
        client = SpacetimeDBClient.builder() \
            .with_uri("ws://localhost:3000") \
            .with_module_name("fallback-module") \
            .connect()  # This connects and returns the client
            
        try:
            # Should use module name in URL
            assert len(ws_calls) == 1
            url = ws_calls[0][0][0]
            assert "/v1/database/fallback-module/subscribe" in url
        finally:
            client.disconnect()


class TestIdentityValidation:
    """Test identity parameter validation and error handling"""
    
    def test_invalid_database_name_characters(self, mock_websocket_comprehensive, connection_tracker):
        """Test error handling for invalid database name characters"""
        client = SpacetimeDBClient(autogen_package=None)
        
        # Mock server rejection for invalid name
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def mock_invalid_name(*args, **kwargs):
            app = original_app(*args, **kwargs)
            # Override run_forever to simulate rejection
            def run_forever():
                if app.on_error:
                    error = Exception("Invalid URL: invalid characters in database name")
                    error.status_code = 400
                    app.on_error(app, error)
                if app.on_close:
                    app.on_close(app, None, None)
            app.run_forever = run_forever
            return app
            
        mock_websocket_comprehensive.WebSocketApp = mock_invalid_name
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="test_module",  # Underscore not allowed
                ssl_enabled=False,
                on_error=connection_tracker.on_error
            )
            
            import time
            time.sleep(0.5)
            
            # Should have error about invalid characters
            assert connection_tracker.error is not None
            assert "invalid characters" in str(connection_tracker.error)
            
        finally:
            client.disconnect()
            
    def test_empty_identity_and_database_address(self):
        """Test that empty identity and database_address is handled"""
        client = SpacetimeDBClient(autogen_package=None)  # Remove test_mode to track WebSocket calls
        
        # This should work - WebSocket client will handle empty identity
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="",  # Empty
            ssl_enabled=False,
            db_identity=None  # Also empty
        )
        
        # Should not crash
        client.disconnect()
        
    def test_identity_priority_over_database_address(self, mock_websocket_comprehensive):
        """Test that db_identity takes priority over database_address"""
        ws_calls = []
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def track_websocket(*args, **kwargs):
            ws_calls.append((args, kwargs))
            return original_app(*args, **kwargs)
            
        mock_websocket_comprehensive.WebSocketApp = track_websocket
        
        client = SpacetimeDBClient(autogen_package=None)  # Remove test_mode to track WebSocket calls
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="address-name",
                ssl_enabled=False,
                db_identity="identity-value"  # This should be used
            )
            
            # URL should use identity, not address
            assert len(ws_calls) == 1
            url = ws_calls[0][0][0]
            assert "/v1/database/identity-value/subscribe" in url
            assert "address-name" not in url
            
        finally:
            client.disconnect()


class TestIdentityErrorMessages:
    """Test error messages related to identity/database issues"""
    
    def test_database_not_found_error(self, mock_websocket_comprehensive, connection_tracker):
        """Test handling of database not found (404) error"""
        client = SpacetimeDBClient(autogen_package=None)
        
        # Mock 404 response
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def mock_not_found(*args, **kwargs):
            app = original_app(*args, **kwargs)
            def run_forever():
                if app.on_error:
                    error = Exception("Handshake status 404 Not Found")
                    error.status_code = 404
                    app.on_error(app, error)
                if app.on_close:
                    app.on_close(app, None, None)
            app.run_forever = run_forever
            return app
            
        mock_websocket_comprehensive.WebSocketApp = mock_not_found
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="nonexistent-db",
                ssl_enabled=False,
                on_error=connection_tracker.on_error,
                db_identity="nonexistent-id"
            )
            
            import time
            time.sleep(0.5)
            
            # Should have 404 error
            assert connection_tracker.error is not None
            assert "404" in str(connection_tracker.error)
            
        finally:
            client.disconnect()


class TestIdentityWithSSL:
    """Test identity parameter with SSL connections"""
    
    def test_ssl_url_with_identity(self, mock_websocket_comprehensive):
        """Test that SSL URLs are constructed correctly with identity"""
        ws_calls = []
        original_app = mock_websocket_comprehensive.WebSocketApp
        
        def track_websocket(*args, **kwargs):
            ws_calls.append((args, kwargs))
            return original_app(*args, **kwargs)
            
        mock_websocket_comprehensive.WebSocketApp = track_websocket
        
        client = SpacetimeDBClient(autogen_package=None)  # Remove test_mode to track WebSocket calls
        
        try:
            client._connect_internal(
                auth_token=None,
                host="example.com:443",
                database_address="test-db",
                ssl_enabled=True,  # SSL enabled
                db_identity="ssl-identity"
            )
            
            # Check URL uses wss:// and includes identity
            assert len(ws_calls) == 1
            url = ws_calls[0][0][0]
            assert url.startswith("wss://")
            assert "/v1/database/ssl-identity/subscribe" in url
            
        finally:
            client.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
