"""
Unit tests for ProtocolHandler

This module tests the focused ProtocolHandler implementation to ensure
proper message encoding, decoding, validation, and error handling.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict

# Import the ProtocolHandler and related classes
from .protocol_handler import (
    ProtocolHandler,
    ProtocolHandlerFactory,
    ProtocolConfiguration,
    MessageMetrics,
    ProcessedMessage,
    ProtocolError,
    MessageValidationError,
    ProtocolSecurityError
)

# Import protocol types for testing
try:
    from ..protocol import (
        CallReducer,
        Subscribe,
        OneOffQuery,
        ClientMessage,
        ServerMessage,
        TEXT_PROTOCOL,
        BIN_PROTOCOL
    )
    PROTOCOL_AVAILABLE = True
except ImportError:
    PROTOCOL_AVAILABLE = False
    CallReducer = None
    TEXT_PROTOCOL = "v1.json.spacetimedb"
    BIN_PROTOCOL = "v1.bsatn.spacetimedb"


class TestMessageMetrics:
    """Test MessageMetrics functionality."""
    
    def test_initialization(self):
        """Test metrics initialization."""
        metrics = MessageMetrics()
        assert metrics.messages_processed == 0
        assert metrics.total_bytes_encoded == 0
        assert metrics.total_bytes_decoded == 0
        assert metrics.error_count == 0
        assert metrics.security_violations == 0
    
    def test_record_encoding(self):
        """Test encoding metrics recording."""
        metrics = MessageMetrics()
        metrics.record_encoding(100, 5.0)
        
        assert metrics.total_bytes_encoded == 100
        assert metrics.encoding_time_ms == 5.0
    
    def test_record_decoding(self):
        """Test decoding metrics recording."""
        metrics = MessageMetrics()
        metrics.record_decoding(200, 10.0)
        
        assert metrics.total_bytes_decoded == 200
        assert metrics.decoding_time_ms == 10.0
        assert metrics.messages_processed == 1
    
    def test_record_validation(self):
        """Test validation metrics recording."""
        metrics = MessageMetrics()
        metrics.record_validation(2.0)
        
        assert metrics.validation_time_ms == 2.0
    
    def test_record_error(self):
        """Test error metrics recording."""
        metrics = MessageMetrics()
        metrics.record_error()
        
        assert metrics.error_count == 1
    
    def test_record_security_violation(self):
        """Test security violation metrics recording."""
        metrics = MessageMetrics()
        metrics.record_security_violation()
        
        assert metrics.security_violations == 1
    
    def test_get_summary(self):
        """Test metrics summary generation."""
        metrics = MessageMetrics()
        metrics.record_encoding(100, 5.0)
        metrics.record_decoding(200, 10.0)
        metrics.record_validation(2.0)
        metrics.record_error()
        
        summary = metrics.get_summary()
        
        assert summary['messages_processed'] == 1
        assert summary['total_bytes_encoded'] == 100
        assert summary['total_bytes_decoded'] == 200
        assert summary['avg_encoding_time_ms'] == 5.0
        assert summary['avg_decoding_time_ms'] == 10.0
        assert summary['avg_validation_time_ms'] == 2.0
        assert summary['error_rate'] == 1.0


class TestProtocolConfiguration:
    """Test ProtocolConfiguration functionality."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = ProtocolConfiguration()
        
        assert config.protocol_version == TEXT_PROTOCOL
        assert config.use_binary == False
        assert config.enable_compression == True
        assert config.enable_security_validation == True
        assert config.enable_message_size_validation == True
        assert config.enable_metrics == True
        assert config.max_message_size == 50 * 1024 * 1024
        assert config.compression_threshold == 1024
        assert config.enable_large_message_support == True
        assert config.thread_safe == True
    
    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = ProtocolConfiguration(
            protocol_version=BIN_PROTOCOL,
            use_binary=True,
            enable_compression=False,
            max_message_size=1024 * 1024
        )
        
        assert config.protocol_version == BIN_PROTOCOL
        assert config.use_binary == True
        assert config.enable_compression == False
        assert config.max_message_size == 1024 * 1024


class TestProtocolHandler:
    """Test ProtocolHandler functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ProtocolConfiguration(
            enable_compression=False,  # Disable for simpler testing
            enable_security_validation=False,  # Disable for simpler testing
            enable_large_message_support=False  # Disable for simpler testing
        )
    
    def test_initialization(self):
        """Test ProtocolHandler initialization."""
        handler = ProtocolHandler(config=self.config)
        
        assert handler.config == self.config
        assert handler.protocol_version == TEXT_PROTOCOL
        assert handler.use_binary == False
        assert handler.enable_security == False
        assert handler.enable_compression == False
        assert isinstance(handler.metrics, MessageMetrics)
    
    def test_initialization_binary_protocol(self):
        """Test initialization with binary protocol."""
        config = ProtocolConfiguration(protocol_version=BIN_PROTOCOL)
        handler = ProtocolHandler(config=config)
        
        assert handler.protocol_version == BIN_PROTOCOL
        assert handler.use_binary == True
    
    def test_thread_safety(self):
        """Test thread safety configuration."""
        config = ProtocolConfiguration(thread_safe=True)
        handler = ProtocolHandler(config=config)
        
        assert handler._lock is not None
        
        config_no_thread = ProtocolConfiguration(thread_safe=False)
        handler_no_thread = ProtocolHandler(config=config_no_thread)
        
        assert handler_no_thread._lock is None
    
    @patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolEncoder')
    @patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolDecoder')
    def test_encode_message(self, mock_decoder, mock_encoder):
        """Test message encoding."""
        # Setup mocks
        mock_encoder_instance = Mock()
        mock_encoder.return_value = mock_encoder_instance
        mock_encoder_instance.encode_client_message.return_value = b'encoded_data'
        
        handler = ProtocolHandler(config=self.config)
        
        # Create a mock message
        mock_message = Mock()
        
        # Test encoding
        result = handler.encode_message(mock_message)
        
        assert result == b'encoded_data'
        mock_encoder_instance.encode_client_message.assert_called_once_with(mock_message)
        
        # Check metrics were recorded
        metrics = handler.get_metrics()
        assert metrics['total_bytes_encoded'] > 0
    
    @patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolEncoder')
    @patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolDecoder')
    def test_decode_message(self, mock_decoder, mock_encoder):
        """Test message decoding."""
        # Setup mocks
        mock_decoder_instance = Mock()
        mock_decoder.return_value = mock_decoder_instance
        mock_server_message = Mock()
        mock_decoder_instance.decode_server_message.return_value = mock_server_message
        
        handler = ProtocolHandler(config=self.config)
        
        # Test decoding
        result = handler.decode_message(b'raw_data')
        
        assert result == mock_server_message
        mock_decoder_instance.decode_server_message.assert_called_once_with(b'raw_data')
        
        # Check metrics were recorded
        metrics = handler.get_metrics()
        assert metrics['messages_processed'] == 1
        assert metrics['total_bytes_decoded'] == 8  # len(b'raw_data')
    
    @patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolEncoder')
    @patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolDecoder')
    def test_process_message(self, mock_decoder, mock_encoder):
        """Test complete message processing pipeline."""
        # Setup mocks
        mock_decoder_instance = Mock()
        mock_decoder.return_value = mock_decoder_instance
        mock_server_message = Mock()
        mock_server_message.__class__.__name__ = 'TestMessage'
        mock_decoder_instance.decode_server_message.return_value = mock_server_message
        
        handler = ProtocolHandler(config=self.config)
        
        # Test processing
        result = handler.process_message(b'raw_data')
        
        assert isinstance(result, ProcessedMessage)
        assert result.message == mock_server_message
        assert result.raw_data == b'raw_data'
        assert result.processing_time_ms > 0
        assert result.message_type == 'TestMessage'
        assert result.security_validated == False  # Disabled in config
        assert result.was_compressed == False
    
    def test_validate_message_invalid_type(self):
        """Test message validation with invalid type."""
        handler = ProtocolHandler(config=self.config)
        
        with pytest.raises(MessageValidationError, match="Invalid message type"):
            handler.validate_message("invalid_message")
    
    def test_encode_message_error_handling(self):
        """Test error handling during encoding."""
        with patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolEncoder') as mock_encoder:
            mock_encoder_instance = Mock()
            mock_encoder.return_value = mock_encoder_instance
            mock_encoder_instance.encode_client_message.side_effect = Exception("Encoding failed")
            
            handler = ProtocolHandler(config=self.config)
            mock_message = Mock()
            
            with pytest.raises(ProtocolError, match="Message encoding failed"):
                handler.encode_message(mock_message)
            
            # Check error was recorded in metrics
            metrics = handler.get_metrics()
            assert metrics['error_rate'] > 0
    
    def test_decode_message_error_handling(self):
        """Test error handling during decoding."""
        with patch('spacetimedb_sdk.protocol.protocol_handler.ProtocolDecoder') as mock_decoder:
            mock_decoder_instance = Mock()
            mock_decoder.return_value = mock_decoder_instance
            mock_decoder_instance.decode_server_message.side_effect = Exception("Decoding failed")
            
            handler = ProtocolHandler(config=self.config)
            
            with pytest.raises(ProtocolError, match="Message decoding failed"):
                handler.decode_message(b'raw_data')
            
            # Check error was recorded in metrics
            metrics = handler.get_metrics()
            assert metrics['error_rate'] > 0
    
    def test_compression_state_management(self):
        """Test compression state management."""
        handler = ProtocolHandler(config=self.config)
        
        # Mock compression type
        mock_compression = Mock()
        mock_compression.value = "test_compression"
        
        # Test setting compression
        handler.set_compression(mock_compression)
        assert handler.negotiated_compression == mock_compression
    
    def test_get_protocol_info(self):
        """Test protocol information retrieval."""
        handler = ProtocolHandler(config=self.config)
        
        info = handler.get_protocol_info()
        
        assert info['protocol_version'] == TEXT_PROTOCOL
        assert info['use_binary'] == False
        assert info['security_enabled'] == False
        assert info['compression_enabled'] == False
        assert info['thread_safe'] == True
        assert info['metrics_enabled'] == True
    
    def test_reset_metrics(self):
        """Test metrics reset functionality."""
        handler = ProtocolHandler(config=self.config)
        
        # Record some metrics
        handler.metrics.record_error()
        assert handler.metrics.error_count == 1
        
        # Reset metrics
        handler.reset_metrics()
        assert handler.metrics.error_count == 0


class TestProtocolHandlerFactory:
    """Test ProtocolHandlerFactory functionality."""
    
    def test_create_handler_default(self):
        """Test default handler creation."""
        handler = ProtocolHandlerFactory.create_handler()
        
        assert handler.protocol_version == TEXT_PROTOCOL
        assert handler.use_binary == False
    
    def test_create_handler_custom(self):
        """Test custom handler creation."""
        handler = ProtocolHandlerFactory.create_handler(
            protocol_version=BIN_PROTOCOL,
            enable_security=False,
            enable_compression=False,
            thread_safe=False
        )
        
        assert handler.protocol_version == BIN_PROTOCOL
        assert handler.use_binary == True
        assert handler.enable_security == False
        assert handler.enable_compression == False
        assert handler._lock is None
    
    def test_create_binary_handler(self):
        """Test binary handler creation."""
        handler = ProtocolHandlerFactory.create_binary_handler()
        
        assert handler.protocol_version == BIN_PROTOCOL
        assert handler.use_binary == True
    
    def test_create_json_handler(self):
        """Test JSON handler creation."""
        handler = ProtocolHandlerFactory.create_json_handler()
        
        assert handler.protocol_version == TEXT_PROTOCOL
        assert handler.use_binary == False


class TestProtocolHandlerIntegration:
    """Integration tests for ProtocolHandler."""
    
    @pytest.mark.skipif(not PROTOCOL_AVAILABLE, reason="Protocol module not available")
    def test_real_message_encoding_decoding(self):
        """Test encoding and decoding with real protocol messages."""
        handler = ProtocolHandlerFactory.create_handler(
            enable_security=False,
            enable_compression=False
        )
        
        # Create a real CallReducer message
        message = CallReducer(
            reducer="test_reducer",
            args=b"test_args",
            request_id=12345
        )
        
        # Test encoding
        encoded_data = handler.encode_message(message)
        assert isinstance(encoded_data, bytes)
        assert len(encoded_data) > 0
        
        # Test metrics
        metrics = handler.get_metrics()
        assert metrics['total_bytes_encoded'] > 0
    
    def test_concurrent_access(self):
        """Test thread safety with concurrent access."""
        handler = ProtocolHandlerFactory.create_handler(thread_safe=True)
        results = []
        errors = []
        
        def worker():
            try:
                mock_message = Mock()
                with patch.object(handler.encoder, 'encode_client_message', return_value=b'test'):
                    result = handler.encode_message(mock_message)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = [threading.Thread(target=worker) for _ in range(10)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert all(result == b'test' for result in results)
    
    def test_large_message_simulation(self):
        """Test handling of large messages."""
        config = ProtocolConfiguration(
            enable_large_message_support=True,
            compression_threshold=100  # Low threshold for testing
        )
        handler = ProtocolHandler(config=config)
        
        # Create large data
        large_data = b'x' * 1000  # 1KB data
        
        # Mock successful decoding
        with patch.object(handler.decoder, 'decode_server_message') as mock_decode:
            mock_message = Mock()
            mock_message.__class__.__name__ = 'LargeMessage'
            mock_decode.return_value = mock_message
            
            result = handler.process_message(large_data)
            
            assert isinstance(result, ProcessedMessage)
            assert result.message == mock_message
            assert len(result.raw_data) == 1000


if __name__ == '__main__':
    pytest.main([__file__])