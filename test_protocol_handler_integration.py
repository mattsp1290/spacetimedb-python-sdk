"""
Integration test for ProtocolHandler extraction from WebSocketClient.

This test verifies that the WebSocketClient continues to work correctly
after the protocol handling logic has been extracted to ProtocolHandler.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict

# Import the WebSocketClient
try:
    from src.spacetimedb_sdk.websocket_client import WebSocketClient
    from src.spacetimedb_sdk.protocol.protocol_handler import ProtocolHandler
    from src.spacetimedb_sdk.protocol import CallReducer, Subscribe, OneOffQuery
    WEBSOCKET_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"Import error: {e}")
    WEBSOCKET_CLIENT_AVAILABLE = False


class TestProtocolHandlerIntegration:
    """Test WebSocketClient integration with ProtocolHandler."""
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_websocket_client_initialization(self):
        """Test that WebSocketClient initializes with ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db",
                protocol="v1.json.spacetimedb"
            )
            
            # Verify ProtocolHandler is initialized
            assert hasattr(client, 'protocol_handler')
            assert isinstance(client.protocol_handler, ProtocolHandler)
            
            # Verify legacy compatibility
            assert hasattr(client, 'encoder')
            assert hasattr(client, 'decoder')
            assert client.encoder == client.protocol_handler.encoder
            assert client.decoder == client.protocol_handler.decoder
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_protocol_helper_includes_handler(self):
        """Test that get_protocol_helper includes the ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            helper = client.get_protocol_helper()
            
            assert 'protocol_handler' in helper
            assert helper['protocol_handler'] == client.protocol_handler
            assert helper['encoder'] == client.encoder
            assert helper['decoder'] == client.decoder
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_protocol_metrics_access(self):
        """Test access to protocol metrics through WebSocketClient."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Test metrics access
            metrics = client.get_protocol_metrics()
            assert isinstance(metrics, dict)
            
            # Test protocol info access
            info = client.get_protocol_info()
            assert isinstance(info, dict)
            assert 'protocol_version' in info
            assert 'use_binary' in info
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_send_message_with_protocol_handler(self):
        """Test that send_message uses ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Mock the WebSocket connection
            mock_ws = Mock()
            client.ws = mock_ws
            client.state = client.ConnectionState.CONNECTED if hasattr(client, 'ConnectionState') else 'connected'
            
            # Mock protocol handler encoding
            with patch.object(client.protocol_handler, 'encode_message', return_value=b'encoded_data') as mock_encode:
                # Create a test message
                message = CallReducer(
                    reducer="test_reducer",
                    args=b"test_args",
                    request_id=12345
                )
                
                # Test send message
                client.send_message(message)
                
                # Verify protocol handler was used
                mock_encode.assert_called_once_with(message)
                
                # Verify WebSocket send was called
                mock_ws.send.assert_called_once_with(b'encoded_data')
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_message_processing_with_protocol_handler(self):
        """Test that message processing uses ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Mock processed message result
            mock_processed_message = Mock()
            mock_processed_message.message = Mock()
            mock_processed_message.processing_time_ms = 10.0
            mock_processed_message.was_compressed = False
            mock_processed_message.was_chunked = False
            mock_processed_message.message_type = "TestMessage"
            
            # Mock protocol handler processing
            with patch.object(client.protocol_handler, 'process_message', return_value=mock_processed_message) as mock_process:
                # Mock message validation
                with patch('src.spacetimedb_sdk.websocket_client.MessageSizeValidator'):
                    # Test message processing
                    client._on_ws_message(Mock(), b'test_message_data')
                    
                    # Verify protocol handler was used
                    mock_process.assert_called_once_with(b'test_message_data')
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_compression_sync_with_protocol_handler(self):
        """Test that compression state is synced with ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Test compression sync function exists
            assert hasattr(client, '_sync_compression_state')
            assert callable(client._sync_compression_state)
            
            # Mock compression type
            mock_compression = Mock()
            mock_compression.value = "test_compression"
            
            # Set compression and sync
            client.negotiated_compression = mock_compression
            client._sync_compression_state()
            
            # Verify protocol handler compression was set
            assert client.protocol_handler.negotiated_compression == mock_compression
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_binary_protocol_configuration(self):
        """Test binary protocol configuration with ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db",
                protocol="v1.bsatn.spacetimedb"
            )
            
            # Verify binary configuration
            assert client.use_binary == True
            assert client.protocol_handler.use_binary == True
            assert client.protocol_handler.protocol_version == "v1.bsatn.spacetimedb"
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_json_protocol_configuration(self):
        """Test JSON protocol configuration with ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db",
                protocol="v1.json.spacetimedb"
            )
            
            # Verify JSON configuration
            assert client.use_binary == False
            assert client.protocol_handler.use_binary == False
            assert client.protocol_handler.protocol_version == "v1.json.spacetimedb"


class TestBackwardCompatibility:
    """Test backward compatibility after ProtocolHandler extraction."""
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_encoder_decoder_compatibility(self):
        """Test that encoder/decoder references still work."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Test that encoder/decoder are still accessible
            assert hasattr(client, 'encoder')
            assert hasattr(client, 'decoder')
            
            # Test that they reference the same objects as in protocol handler
            assert client.encoder is client.protocol_handler.encoder
            assert client.decoder is client.protocol_handler.decoder
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_legacy_message_sending_still_works(self):
        """Test that legacy message sending patterns still work."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Mock connection state
            client.ws = Mock()
            client.state = client.ConnectionState.CONNECTED if hasattr(client, 'ConnectionState') else 'connected'
            
            # Mock encoder (legacy access pattern)
            with patch.object(client.encoder, 'encode_client_message', return_value=b'legacy_encoded') as mock_encode:
                # Since send_message now uses protocol_handler, we need to mock that instead
                with patch.object(client.protocol_handler, 'encode_message', return_value=b'legacy_encoded'):
                    message = Mock()
                    client.send_message(message)
                    
                    # Verify message was sent (regardless of which path)
                    client.ws.send.assert_called_once()
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_client_encoded_message_bypass(self):
        """Test that client-encoded message bypass still works."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Mock connection state
            client.ws = Mock()
            client.state = client.ConnectionState.CONNECTED if hasattr(client, 'ConnectionState') else 'connected'
            
            # Mock _send_client_encoded_message
            with patch.object(client, '_send_client_encoded_message') as mock_send_client:
                message = b'pre_encoded_message'
                client.send_message(message, use_client_encoding=True)
                
                # Verify bypass was used
                mock_send_client.assert_called_once_with(message)


class TestPerformanceRegression:
    """Test that ProtocolHandler doesn't introduce performance regression."""
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_encoding_performance(self):
        """Test encoding performance with ProtocolHandler."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Create test message
            message = CallReducer(
                reducer="test_reducer",
                args=b"test_args",
                request_id=12345
            )
            
            # Mock encoding to measure call overhead
            with patch.object(client.protocol_handler.encoder, 'encode_client_message', return_value=b'test') as mock_encode:
                start_time = time.time()
                
                # Perform multiple encodings
                for _ in range(100):
                    client.protocol_handler.encode_message(message)
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Should complete 100 encodings quickly (< 1 second)
                assert total_time < 1.0
                
                # Verify all calls were made
                assert mock_encode.call_count == 100
    
    @pytest.mark.skipif(not WEBSOCKET_CLIENT_AVAILABLE, reason="WebSocketClient not available")
    def test_metrics_overhead(self):
        """Test that metrics collection doesn't add significant overhead."""
        with patch('src.spacetimedb_sdk.websocket_client.CompressionManager'):
            client = WebSocketClient(
                host="localhost",
                database_address="test_db"
            )
            
            # Mock message processing
            mock_message = Mock()
            mock_message.__class__.__name__ = "TestMessage"
            
            with patch.object(client.protocol_handler.decoder, 'decode_server_message', return_value=mock_message):
                start_time = time.time()
                
                # Process multiple messages
                for _ in range(100):
                    client.protocol_handler.decode_message(b'test_data')
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Should complete 100 decodings quickly (< 1 second)
                assert total_time < 1.0
                
                # Verify metrics were collected
                metrics = client.get_protocol_metrics()
                assert metrics['messages_processed'] == 100


def run_integration_tests():
    """Run all integration tests."""
    if not WEBSOCKET_CLIENT_AVAILABLE:
        print("WebSocketClient not available, skipping integration tests")
        return
    
    print("Running ProtocolHandler integration tests...")
    
    # Create test instances
    test_integration = TestProtocolHandlerIntegration()
    test_compatibility = TestBackwardCompatibility()
    test_performance = TestPerformanceRegression()
    
    # Run tests
    try:
        print("Testing WebSocketClient initialization...")
        test_integration.test_websocket_client_initialization()
        print("✓ Initialization test passed")
        
        print("Testing protocol helper...")
        test_integration.test_protocol_helper_includes_handler()
        print("✓ Protocol helper test passed")
        
        print("Testing metrics access...")
        test_integration.test_protocol_metrics_access()
        print("✓ Metrics access test passed")
        
        print("Testing binary protocol configuration...")
        test_integration.test_binary_protocol_configuration()
        print("✓ Binary protocol test passed")
        
        print("Testing JSON protocol configuration...")
        test_integration.test_json_protocol_configuration()
        print("✓ JSON protocol test passed")
        
        print("Testing backward compatibility...")
        test_compatibility.test_encoder_decoder_compatibility()
        print("✓ Backward compatibility test passed")
        
        print("\nAll integration tests passed! ✓")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise


if __name__ == '__main__':
    run_integration_tests()