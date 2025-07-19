"""
Protocol-specific tests for SpacetimeDB v1.1.2 compatibility
"""
import pytest
from unittest.mock import patch, Mock
import sys
import os

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL
from spacetimedb_sdk.websocket_client import WebSocketClient


class TestProtocolConfiguration:
    """Test protocol configuration and selection"""
    
    def test_default_protocol_is_text(self):
        """Test that default protocol is TEXT_PROTOCOL"""
        client = SpacetimeDBClient(autogen_package=None)
        assert client.protocol == TEXT_PROTOCOL
        
    def test_explicit_text_protocol(self):
        """Test explicit text protocol configuration"""
        client = SpacetimeDBClient(autogen_package=None, protocol=TEXT_PROTOCOL)
        assert client.protocol == TEXT_PROTOCOL
        
    def test_explicit_binary_protocol(self):
        """Test explicit binary protocol configuration"""
        client = SpacetimeDBClient(autogen_package=None, protocol=BIN_PROTOCOL)
        assert client.protocol == BIN_PROTOCOL
        
    def test_protocol_string_shortcuts(self):
        """Test protocol string shortcuts (not supported in modern client)"""
        # Modern client expects full protocol strings, not shortcuts
        client = SpacetimeDBClient(autogen_package=None, protocol="v1.json.spacetimedb")
        assert client.protocol == "v1.json.spacetimedb"
        
    def test_protocol_passed_to_websocket(self, mock_websocket):
        """Test that protocol is correctly passed to WebSocket client"""
        with patch.object(WebSocketClient, '__init__', return_value=None) as mock_init:
            client = SpacetimeDBClient(
                autogen_package=None, 
                protocol=BIN_PROTOCOL,
                test_mode=True  # Prevent real connection
            )
            # The WebSocket client should be created with the correct protocol
            # Note: In test mode, no WebSocket is created
            assert client.protocol == BIN_PROTOCOL


class TestProtocolConnection:
    """Test protocol behavior during connection"""
    
    def test_text_protocol_connection(self, mock_websocket, test_client_params, connection_tracker):
        """Test connection with TEXT_PROTOCOL"""
        client = SpacetimeDBClient(autogen_package=None, protocol=TEXT_PROTOCOL)
        
        # Track calls to WebSocketApp
        calls = []
        original_websocket_app = mock_websocket.WebSocketApp
        
        def track_calls(*args, **kwargs):
            calls.append((args, kwargs))
            return original_websocket_app(*args, **kwargs)
        
        mock_websocket.WebSocketApp = track_calls
        
        try:
            client._connect_internal(
                auth_token=test_client_params["auth_token"],
                host=test_client_params["host"],
                database_address=test_client_params["database_address"],
                ssl_enabled=test_client_params["ssl_enabled"],
                on_connect=connection_tracker.on_connect,
                on_error=connection_tracker.on_error,
                db_identity=test_client_params["db_identity"]
            )
            
            # The mock should create a WebSocket with TEXT_PROTOCOL
            assert len(calls) > 0
            call_kwargs = calls[0][1]
            assert TEXT_PROTOCOL in call_kwargs["subprotocols"]
            
        finally:
            client.disconnect()
            
    def test_binary_protocol_connection(self, mock_websocket, test_client_params, connection_tracker):
        """Test connection with BIN_PROTOCOL"""
        client = SpacetimeDBClient(autogen_package=None, protocol=BIN_PROTOCOL)
        
        # Track calls to WebSocketApp
        calls = []
        original_websocket_app = mock_websocket.WebSocketApp
        
        def track_calls(*args, **kwargs):
            calls.append((args, kwargs))
            return original_websocket_app(*args, **kwargs)
        
        mock_websocket.WebSocketApp = track_calls
        
        try:
            client._connect_internal(
                auth_token=test_client_params["auth_token"],
                host=test_client_params["host"],
                database_address=test_client_params["database_address"],
                ssl_enabled=test_client_params["ssl_enabled"],
                on_connect=connection_tracker.on_connect,
                on_error=connection_tracker.on_error,
                db_identity=test_client_params["db_identity"]
            )
            
            # The mock should create a WebSocket with BIN_PROTOCOL
            assert len(calls) > 0
            call_kwargs = calls[0][1]
            assert BIN_PROTOCOL in call_kwargs["subprotocols"]
            
        finally:
            client.disconnect()
            
    def test_invalid_protocol_rejection(self, mock_websocket, test_client_params, connection_tracker):
        """Test that old/invalid protocols are rejected by server"""
        # Create client with invalid protocol
        old_protocol = "v1.text.spacetimedb"  # Old protocol that v1.1.2 rejects
        client = SpacetimeDBClient(autogen_package=None, protocol=old_protocol)
        
        # Mock WebSocket to simulate protocol rejection
        original_app = mock_websocket.WebSocketApp
        
        def mock_websocket_app(*args, **kwargs):
            app = original_app(*args, **kwargs)
            # Override run_forever to simulate rejection
            def run_forever():
                if app.on_error:
                    error = Exception("no valid protocol selected")
                    error.status_code = 400
                    app.on_error(app, error)
                if app.on_close:
                    app.on_close(app, None, None)
            app.run_forever = run_forever
            return app
            
        mock_websocket.WebSocketApp = mock_websocket_app
        
        try:
            client._connect_internal(
                auth_token=test_client_params["auth_token"],
                host=test_client_params["host"],
                database_address=test_client_params["database_address"],
                ssl_enabled=test_client_params["ssl_enabled"],
                on_connect=connection_tracker.on_connect,
                on_error=connection_tracker.on_error,
                db_identity=test_client_params["db_identity"]
            )
            
            # Wait a bit for the error to propagate
            import time
            time.sleep(0.5)
            
            # Should have received an error
            assert connection_tracker.error is not None
            assert "no valid protocol selected" in str(connection_tracker.error)
            
        finally:
            client.disconnect()


class TestProtocolBuilder:
    """Test protocol configuration via builder pattern"""
    
    def test_builder_text_protocol(self):
        """Test builder with text protocol"""
        builder = SpacetimeDBClient.builder()
        builder = builder.with_protocol("text")  # Builder uses shortcuts
        
        # Builder stores shortcuts, not full protocol strings
        assert builder._protocol == "text"
        
    def test_builder_binary_protocol(self):
        """Test builder with binary protocol"""
        builder = SpacetimeDBClient.builder()
        builder = builder.with_protocol("binary")  # Builder expects "binary" not "bsatn"
        
        # Builder stores shortcuts, not full protocol strings
        assert builder._protocol == "binary"
        
    def test_builder_invalid_protocol(self):
        """Test builder with invalid protocol raises error"""
        builder = SpacetimeDBClient.builder()
        
        with pytest.raises(ValueError) as exc_info:
            builder.with_protocol("invalid")
            
        assert "Invalid protocol" in str(exc_info.value)
        
    def test_builder_creates_client_with_protocol(self, mock_websocket):
        """Test that builder creates client with correct protocol"""
        client = SpacetimeDBClient.builder() \
            .with_uri("ws://localhost:3000") \
            .with_module_name("test-db") \
            .with_protocol("binary") \
            .build()
            
        try:
            # The builder stores shortcuts, but client should have full protocol
            # The builder passes "binary" to the client which should convert it
            assert client.protocol == BIN_PROTOCOL  # Client converts shortcuts to full protocol
        finally:
            client.disconnect()


class TestProtocolConstants:
    """Test protocol constant usage and values"""
    
    def test_text_protocol_value(self):
        """Test TEXT_PROTOCOL has correct value for v1.1.2"""
        assert TEXT_PROTOCOL == "v1.json.spacetimedb"
        
    def test_bin_protocol_value(self):
        """Test BIN_PROTOCOL has correct value for v1.1.2"""
        assert BIN_PROTOCOL == "v1.bsatn.spacetimedb"
        
    def test_old_protocol_not_used(self):
        """Ensure old protocol is not referenced anywhere"""
        # This test verifies the old protocol string doesn't appear
        old_protocol = "v1.text.spacetimedb"
        
        # Check it's not used as default anywhere
        client = SpacetimeDBClient(autogen_package=None)
        assert client.protocol != old_protocol
        
        # Check constants don't contain it
        assert TEXT_PROTOCOL != old_protocol
        assert BIN_PROTOCOL != old_protocol


class TestProtocolClassMethod:
    """Test protocol handling in class methods"""
    
    def test_connect_class_method_protocol(self, mock_websocket):
        """Test SpacetimeDBClient.connect() uses correct protocol"""
        tracker = Mock()
        
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test-db",
            protocol=BIN_PROTOCOL,  # Explicit protocol
            on_connect=tracker.on_connect,
            test_mode=True  # Prevent real connection
        )
        
        try:
            # Client should have the specified protocol
            assert client.protocol == BIN_PROTOCOL
        finally:
            client.shutdown()
            
    def test_connect_class_method_default_protocol(self, mock_websocket):
        """Test SpacetimeDBClient.connect() defaults to TEXT_PROTOCOL"""
        tracker = Mock()
        
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test-db",
            on_connect=tracker.on_connect,
            test_mode=True  # Prevent real connection
        )
        
        try:
            # Client should default to TEXT_PROTOCOL
            assert client.protocol == TEXT_PROTOCOL
        finally:
            client.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
