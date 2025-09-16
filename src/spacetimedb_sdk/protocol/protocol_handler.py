"""
Focused ProtocolHandler for SpacetimeDB message encoding/decoding.

This module extracts message processing responsibilities from WebSocketClient
to create a focused, testable component that handles only protocol message
encoding, decoding, validation, and routing.
"""

import logging
import time
import threading
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Protocol constants to avoid circular imports
TEXT_PROTOCOL = "v1.json.spacetimedb"
BIN_PROTOCOL = "v1.bsatn.spacetimedb"

# Import compression support
try:
    from ..compression import CompressionManager, CompressionType
    COMPRESSION_AVAILABLE = True
except ImportError:
    COMPRESSION_AVAILABLE = False
    CompressionManager = None
    CompressionType = None

# Import security validation
try:
    from ..security.input_validation import (
        InputValidator,
        ValidationSecurityError,
        SecurityValidationError
    )
    from ..message_validator import MessageSizeValidator
    SECURITY_VALIDATION_AVAILABLE = True
except ImportError:
    SECURITY_VALIDATION_AVAILABLE = False
    InputValidator = None
    ValidationSecurityError = Exception
    SecurityValidationError = Exception
    MessageSizeValidator = None

# Import memory management
try:
    from ..memory_management import get_global_memory_accountant
    MEMORY_MANAGEMENT_AVAILABLE = True
except ImportError:
    MEMORY_MANAGEMENT_AVAILABLE = False
    get_global_memory_accountant = lambda: None

# Import monitoring
try:
    from ..monitoring import get_global_monitor
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    get_global_monitor = lambda: None

# Import serialization support
try:
    from ..serialization import prepare_message_for_client
    SERIALIZATION_AVAILABLE = True
except ImportError:
    SERIALIZATION_AVAILABLE = False
    prepare_message_for_client = lambda x: x


class ProtocolError(Exception):
    """Base exception for protocol-related errors."""
    pass


class MessageValidationError(ProtocolError):
    """Exception raised when message validation fails."""
    pass


class ProtocolSecurityError(ProtocolError):
    """Exception raised for protocol security violations."""
    pass


@dataclass
class MessageMetrics:
    """Metrics for message processing performance."""
    messages_processed: int = 0
    total_bytes_encoded: int = 0
    total_bytes_decoded: int = 0
    encoding_time_ms: float = 0.0
    decoding_time_ms: float = 0.0
    validation_time_ms: float = 0.0
    compression_ratio: float = 1.0
    error_count: int = 0
    security_violations: int = 0
    
    def record_encoding(self, bytes_processed: int, time_taken_ms: float):
        """Record encoding metrics."""
        self.total_bytes_encoded += bytes_processed
        self.encoding_time_ms += time_taken_ms
        
    def record_decoding(self, bytes_processed: int, time_taken_ms: float):
        """Record decoding metrics."""
        self.total_bytes_decoded += bytes_processed
        self.decoding_time_ms += time_taken_ms
        self.messages_processed += 1
        
    def record_validation(self, time_taken_ms: float):
        """Record validation metrics."""
        self.validation_time_ms += time_taken_ms
        
    def record_error(self):
        """Record an error occurrence."""
        self.error_count += 1
        
    def record_security_violation(self):
        """Record a security violation."""
        self.security_violations += 1
        
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            'messages_processed': self.messages_processed,
            'total_bytes_encoded': self.total_bytes_encoded,
            'total_bytes_decoded': self.total_bytes_decoded,
            'avg_encoding_time_ms': (
                self.encoding_time_ms / max(1, self.messages_processed)
            ),
            'avg_decoding_time_ms': (
                self.decoding_time_ms / max(1, self.messages_processed)
            ),
            'avg_validation_time_ms': (
                self.validation_time_ms / max(1, self.messages_processed)
            ),
            'compression_ratio': self.compression_ratio,
            'error_rate': self.error_count / max(1, self.messages_processed),
            'security_violation_count': self.security_violations
        }


@dataclass
class ProcessedMessage:
    """Result of message processing pipeline."""
    message: Any
    raw_data: bytes
    processing_time_ms: float
    was_compressed: bool = False
    was_chunked: bool = False
    security_validated: bool = False
    message_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtocolConfiguration:
    """Configuration for ProtocolHandler."""
    protocol_version: str = TEXT_PROTOCOL
    use_binary: bool = False
    enable_compression: bool = True
    enable_security_validation: bool = True
    enable_message_size_validation: bool = True
    enable_metrics: bool = True
    max_message_size: int = 50 * 1024 * 1024  # 50MB
    compression_threshold: int = 1024  # 1KB
    enable_large_message_support: bool = True
    thread_safe: bool = True


class ProtocolHandler:
    """
    Focused handler for SpacetimeDB protocol message encoding/decoding only.
    
    This class extracts message processing responsibilities from WebSocketClient
    to provide a clean, testable interface for protocol operations.
    
    Key responsibilities:
    - Message encoding and decoding
    - Protocol validation
    - Security validation
    - Message metrics and monitoring
    - Compression/decompression
    - Error handling for protocol violations
    
    NOT responsible for:
    - WebSocket connection management
    - Subscription state management
    - Callback handling
    - Authentication
    - Network I/O
    """
    
    def __init__(
        self,
        config: Optional[ProtocolConfiguration] = None,
        validator: Optional['InputValidator'] = None,
        compression_manager: Optional['CompressionManager'] = None
    ):
        """
        Initialize ProtocolHandler.
        
        Args:
            config: Protocol configuration
            validator: Input validator for security
            compression_manager: Compression manager for message compression
        """
        self.config = config or ProtocolConfiguration()
        self.logger = logging.getLogger(f"{__name__}.ProtocolHandler")
        
        # Thread safety
        self._lock = threading.RLock() if self.config.thread_safe else None
        
        # Protocol version and binary mode
        self.protocol_version = self.config.protocol_version
        self.use_binary = self.config.use_binary or 'bsatn' in self.protocol_version
        
        # Initialize encoder/decoder with dynamic import to avoid circular dependency
        self.encoder = None
        self.decoder = None
        self._init_encoder_decoder()
        
        # Security validation
        self.validator = validator
        self.enable_security = (
            self.config.enable_security_validation 
            and SECURITY_VALIDATION_AVAILABLE 
            and self.validator is not None
        )
        
        # Message size validation
        self.message_validator = None
        if self.config.enable_message_size_validation and MEMORY_MANAGEMENT_AVAILABLE:
            memory_accountant = get_global_memory_accountant()
            if memory_accountant and MessageSizeValidator:
                self.message_validator = MessageSizeValidator(
                    memory_accountant=memory_accountant
                )
        
        # Compression support
        self.compression_manager = compression_manager
        self.enable_compression = (
            self.config.enable_compression 
            and COMPRESSION_AVAILABLE 
            and self.compression_manager is not None
        )
        self.negotiated_compression: Optional['CompressionType'] = None
        
        # Metrics and monitoring
        self.metrics = MessageMetrics()
        self.enable_metrics = self.config.enable_metrics
        self.monitor = get_global_monitor() if MONITORING_AVAILABLE else None
        
        # Large message handling
        self.large_message_handler = None
        if self.config.enable_large_message_support:
            try:
                from ..large_message_handler import LargeMessageHandler
                self.large_message_handler = LargeMessageHandler()
            except ImportError:
                self.logger.debug("Large message handler not available")
        
        self.logger.info(
            f"ProtocolHandler initialized: protocol={self.protocol_version}, "
            f"binary={self.use_binary}, security={self.enable_security}, "
            f"compression={self.enable_compression}"
        )
    
    def _init_encoder_decoder(self):
        """Initialize encoder/decoder with lazy import to avoid circular dependencies."""
        try:
            from ..protocol import ProtocolEncoder, ProtocolDecoder
            self.encoder = ProtocolEncoder(use_binary=self.use_binary)
            self.decoder = ProtocolDecoder(use_binary=self.use_binary)
        except ImportError:
            self.logger.warning("ProtocolEncoder/Decoder not available")
            # Create simple mock objects for testing
            class SimpleMock:
                def encode_client_message(self, message): return b'mock_encoded'
                def decode_server_message(self, data): return {'mock': 'message'}
            self.encoder = SimpleMock()
            self.decoder = SimpleMock()
    
    def encode_message(self, message: Any) -> bytes:
        """
        Encode message for transmission.
        
        Args:
            message: Client message to encode
            
        Returns:
            Encoded message bytes
            
        Raises:
            MessageValidationError: If message validation fails
            ProtocolSecurityError: If security validation fails
            ProtocolError: If encoding fails
        """
        start_time = time.time()
        
        try:
            with self._lock_context():
                # Validate message if security is enabled
                if self.enable_security:
                    validation_start = time.time()
                    self._validate_message_security(message)
                    if self.enable_metrics:
                        validation_time = (time.time() - validation_start) * 1000
                        self.metrics.record_validation(validation_time)
                
                # Encode the message
                if not self.encoder:
                    raise ProtocolError("Encoder not available")
                encoded_data = self.encoder.encode_client_message(message)
                
                # Apply compression if enabled and beneficial
                if self.enable_compression and len(encoded_data) > self.config.compression_threshold:
                    encoded_data = self._apply_compression(encoded_data)
                
                # Record metrics
                if self.enable_metrics:
                    encoding_time = (time.time() - start_time) * 1000
                    self.metrics.record_encoding(len(encoded_data), encoding_time)
                
                # Record monitoring metrics
                if self.monitor:
                    self.monitor.record_websocket_frame(sent=True, size=len(encoded_data))
                
                return encoded_data
                
        except (ValidationSecurityError, SecurityValidationError) as e:
            if self.enable_metrics:
                self.metrics.record_security_violation()
            raise ProtocolSecurityError(f"Security validation failed: {e}") from e
        except Exception as e:
            if self.enable_metrics:
                self.metrics.record_error()
            raise ProtocolError(f"Message encoding failed: {e}") from e
    
    def decode_message(self, data: bytes) -> Any:
        """
        Decode received message data.
        
        Args:
            data: Raw message data to decode
            
        Returns:
            Decoded server message
            
        Raises:
            MessageValidationError: If message validation fails
            ProtocolSecurityError: If security validation fails
            ProtocolError: If decoding fails
        """
        start_time = time.time()
        
        try:
            with self._lock_context():
                # Validate message size
                if self.message_validator and not self.message_validator.validate_message_size(data):
                    raise MessageValidationError(f"Message too large: {len(data)} bytes")
                
                # Handle large message reassembly if needed
                processed_data = self._handle_large_message(data)
                if processed_data is None:
                    # Waiting for more chunks
                    return None
                
                # Apply decompression if needed
                if self.enable_compression and self.negotiated_compression:
                    processed_data = self._apply_decompression(processed_data)
                
                # Decode the server message
                if not self.decoder:
                    raise ProtocolError("Decoder not available")
                server_message = self.decoder.decode_server_message(processed_data)
                
                # Security validation on decoded message
                if self.enable_security:
                    validation_start = time.time()
                    self._validate_decoded_message_security(server_message)
                    if self.enable_metrics:
                        validation_time = (time.time() - validation_start) * 1000
                        self.metrics.record_validation(validation_time)
                
                # Record metrics
                if self.enable_metrics:
                    decoding_time = (time.time() - start_time) * 1000
                    self.metrics.record_decoding(len(data), decoding_time)
                
                return server_message
                
        except (ValidationSecurityError, SecurityValidationError) as e:
            if self.enable_metrics:
                self.metrics.record_security_violation()
            raise ProtocolSecurityError(f"Security validation failed: {e}") from e
        except Exception as e:
            if self.enable_metrics:
                self.metrics.record_error()
            raise ProtocolError(f"Message decoding failed: {e}") from e
    
    def validate_message(self, message: Any) -> bool:
        """
        Validate message format and content.
        
        Args:
            message: Message to validate
            
        Returns:
            True if message is valid
            
        Raises:
            MessageValidationError: If validation fails
        """
        try:
            with self._lock_context():
                # Basic type validation
                if not hasattr(message, '__class__'):
                    raise MessageValidationError(f"Invalid message type: {type(message)}")
                
                # Security validation if enabled
                if self.enable_security:
                    # Check if it's likely a client message (has reducer, query_string, etc.)
                    if hasattr(message, 'reducer') or hasattr(message, 'query_string'):
                        self._validate_message_security(message)
                    else:
                        self._validate_decoded_message_security(message)
                
                return True
                
        except Exception as e:
            raise MessageValidationError(f"Message validation failed: {e}") from e
    
    def process_message(self, raw_data: bytes) -> ProcessedMessage:
        """
        Complete message processing pipeline.
        
        Args:
            raw_data: Raw message data
            
        Returns:
            Processed message with metadata
            
        Raises:
            ProtocolError: If processing fails
        """
        start_time = time.time()
        
        try:
            with self._lock_context():
                # Decode the message
                message = self.decode_message(raw_data)
                if message is None:
                    # Partial message - waiting for more chunks
                    return None
                
                # Prepare message for client consumption if serialization is available
                if SERIALIZATION_AVAILABLE:
                    try:
                        message = prepare_message_for_client(message)
                    except Exception as e:
                        self.logger.debug(f"Message serialization failed: {e}")
                        # Continue with original message
                
                processing_time = (time.time() - start_time) * 1000
                
                return ProcessedMessage(
                    message=message,
                    raw_data=raw_data,
                    processing_time_ms=processing_time,
                    was_compressed=bool(self.negotiated_compression),
                    was_chunked=bool(self.large_message_handler and len(raw_data) > self.config.compression_threshold),
                    security_validated=self.enable_security,
                    message_type=type(message).__name__,
                    metadata={
                        'protocol_version': self.protocol_version,
                        'use_binary': self.use_binary,
                        'message_size': len(raw_data)
                    }
                )
                
        except Exception as e:
            if self.enable_metrics:
                self.metrics.record_error()
            raise ProtocolError(f"Message processing failed: {e}") from e
    
    def set_compression(self, compression_type: Optional['CompressionType']):
        """
        Set negotiated compression type.
        
        Args:
            compression_type: Compression type to use
        """
        with self._lock_context():
            self.negotiated_compression = compression_type
            if compression_type and self.enable_metrics:
                self.logger.debug(f"Compression enabled: {compression_type.value}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get protocol handling metrics.
        
        Returns:
            Metrics summary
        """
        with self._lock_context():
            return self.metrics.get_summary()
    
    def reset_metrics(self):
        """Reset metrics counters."""
        with self._lock_context():
            self.metrics = MessageMetrics()
    
    def get_protocol_info(self) -> Dict[str, Any]:
        """
        Get protocol handler information.
        
        Returns:
            Protocol configuration and status
        """
        return {
            'protocol_version': self.protocol_version,
            'use_binary': self.use_binary,
            'security_enabled': self.enable_security,
            'compression_enabled': self.enable_compression,
            'large_message_support': self.large_message_handler is not None,
            'thread_safe': self._lock is not None,
            'metrics_enabled': self.enable_metrics
        }
    
    def _lock_context(self):
        """Get lock context manager."""
        if self._lock:
            return self._lock
        else:
            # No-op context manager
            class NoOpContext:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return NoOpContext()
    
    def _validate_message_security(self, message: Any):
        """Validate client message security."""
        if not self.validator:
            return
        
        # Implement security validation based on message type
        try:
            # Basic validation - extend as needed
            if hasattr(message, 'query_string'):
                # Validate SQL queries
                query = getattr(message, 'query_string', '')
                if query:
                    self.validator.validate_input(query, 'sql_query')
            
            if hasattr(message, 'reducer'):
                # Validate reducer names
                reducer = getattr(message, 'reducer', '')
                if reducer:
                    self.validator.validate_input(reducer, 'reducer_name')
                    
        except Exception as e:
            raise SecurityValidationError(f"Security validation failed: {e}") from e
    
    def _validate_decoded_message_security(self, message: Any):
        """Validate decoded server message security."""
        if not self.validator:
            return
        
        # Implement security validation for server messages
        try:
            # Basic validation - extend as needed
            message_size = len(str(message)) if hasattr(message, '__str__') else 0
            if message_size > self.config.max_message_size:
                raise SecurityValidationError(f"Message too large: {message_size} bytes")
                
        except Exception as e:
            raise SecurityValidationError(f"Server message security validation failed: {e}") from e
    
    def _apply_compression(self, data: bytes) -> bytes:
        """Apply compression to data if beneficial."""
        if not self.compression_manager or not self.negotiated_compression:
            return data
        
        try:
            compressed_data, compression_used = self.compression_manager.compress(
                data, self.negotiated_compression
            )
            
            if compression_used != CompressionType.NONE:
                compression_ratio = len(compressed_data) / len(data)
                if self.enable_metrics:
                    self.metrics.compression_ratio = compression_ratio
                
                self.logger.debug(
                    f"Compressed message: {len(data)} -> {len(compressed_data)} bytes "
                    f"({compression_used.value}, ratio: {compression_ratio:.2f})"
                )
                return compressed_data
            
        except Exception as e:
            self.logger.warning(f"Compression failed, using uncompressed data: {e}")
        
        return data
    
    def _apply_decompression(self, data: bytes) -> bytes:
        """Apply decompression to data."""
        if not self.compression_manager or not self.negotiated_compression:
            return data
        
        try:
            decompressed_data = self.compression_manager.decompress(
                data, self.negotiated_compression
            )
            self.logger.debug(f"Decompressed message: {len(data)} -> {len(decompressed_data)} bytes")
            return decompressed_data
            
        except Exception as e:
            self.logger.warning(f"Decompression failed, using original data: {e}")
            return data
    
    def _handle_large_message(self, data: bytes) -> Optional[bytes]:
        """Handle large message reassembly."""
        if not self.large_message_handler:
            return data
        
        # Check if this might be a chunked message
        if len(data) > self.config.compression_threshold:
            try:
                processed_data = self.large_message_handler.handle_incoming_message(data)
                return processed_data  # May be None if waiting for more chunks
            except Exception as e:
                self.logger.debug(f"Large message handling failed: {e}")
                return data
        
        return data


class ProtocolHandlerFactory:
    """Factory for creating ProtocolHandler instances."""
    
    @staticmethod
    def create_handler(
        protocol_version: str = TEXT_PROTOCOL,
        enable_security: bool = True,
        enable_compression: bool = True,
        thread_safe: bool = True
    ) -> ProtocolHandler:
        """
        Create a ProtocolHandler with specified configuration.
        
        Args:
            protocol_version: Protocol version to use
            enable_security: Enable security validation
            enable_compression: Enable compression support
            thread_safe: Enable thread safety
            
        Returns:
            Configured ProtocolHandler
        """
        config = ProtocolConfiguration(
            protocol_version=protocol_version,
            use_binary='bsatn' in protocol_version,
            enable_compression=enable_compression,
            enable_security_validation=enable_security,
            thread_safe=thread_safe
        )
        
        # Create validator if security is enabled
        validator = None
        if enable_security and SECURITY_VALIDATION_AVAILABLE:
            try:
                from ..security.input_validation import create_secure_validators
                validator, _, _ = create_secure_validators()
            except ImportError:
                pass
        
        # Create compression manager if compression is enabled
        compression_manager = None
        if enable_compression and COMPRESSION_AVAILABLE:
            try:
                compression_manager = CompressionManager()
            except Exception:
                pass
        
        return ProtocolHandler(
            config=config,
            validator=validator,
            compression_manager=compression_manager
        )
    
    @staticmethod
    def create_binary_handler(**kwargs) -> ProtocolHandler:
        """Create handler for binary protocol."""
        return ProtocolHandlerFactory.create_handler(
            protocol_version=BIN_PROTOCOL,
            **kwargs
        )
    
    @staticmethod
    def create_json_handler(**kwargs) -> ProtocolHandler:
        """Create handler for JSON protocol."""
        return ProtocolHandlerFactory.create_handler(
            protocol_version=TEXT_PROTOCOL,
            **kwargs
        )


# Global default handler instance
_default_handler: Optional[ProtocolHandler] = None


def get_default_protocol_handler() -> ProtocolHandler:
    """Get or create the default protocol handler."""
    global _default_handler
    if _default_handler is None:
        _default_handler = ProtocolHandlerFactory.create_handler()
    return _default_handler


def set_default_protocol_handler(handler: ProtocolHandler):
    """Set the default protocol handler."""
    global _default_handler
    _default_handler = handler