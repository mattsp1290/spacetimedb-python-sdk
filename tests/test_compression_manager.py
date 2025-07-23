"""
Comprehensive Unit Tests for Enhanced CompressionManager

Tests security features including:
- Zip bomb protection
- Memory limits during decompression
- Rate limiting
- Security validation integration
- Performance monitoring
- Thread safety

Author: SpacetimeDB Security Team
"""

import pytest
import threading
import time
import gzip
import io
from unittest.mock import Mock, patch
from typing import List, Optional

from spacetimedb_sdk.compression_handlers.compression_manager import (
    CompressionManager,
    CompressionType,
    CompressionLevel,
    CompressionConfig,
    CompressionSecurityConfig,
    CompressionMetrics,
    CompressionError,
    ZipBombError,
    UnsupportedCompressionError
)

try:
    from spacetimedb_sdk.validation.validators import ValidationResult, ValidationError
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    ValidationResult = None
    ValidationError = None


class MockSecurityValidator:
    """Mock security validator for testing."""
    
    def __init__(self, should_fail: bool = False, errors: Optional[List[str]] = None):
        self.should_fail = should_fail
        self.errors = errors or []
        self.validate_calls = []
    
    def validate(self, data: bytes, field: Optional[str] = None):
        """Mock validation method."""
        self.validate_calls.append((data, field))
        
        if VALIDATION_AVAILABLE:
            if self.should_fail:
                return ValidationResult(
                    is_valid=False,
                    sanitized_value=data,
                    errors=[ValidationError("test_field", "Test validation error", data)]
                )
            else:
                return ValidationResult(
                    is_valid=True,
                    sanitized_value=data,
                    errors=[]
                )
        else:
            # Fallback for when validation framework is not available
            class MockResult:
                def __init__(self, is_valid: bool, errors: List[str]):
                    self.is_valid = is_valid
                    self.errors = errors
            
            return MockResult(not self.should_fail, self.errors if self.should_fail else [])


class TestCompressionManager:
    """Test suite for CompressionManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_data = b"Hello, World! " * 100  # Repeatable data for compression
        self.small_data = b"Small"
        self.large_data = b"Large data " * 10000
        
        # Create test configurations
        self.default_config = CompressionConfig()
        self.security_config = CompressionSecurityConfig(
            max_compression_ratio=100.0,  # Increase ratio limit for normal compressed data
            max_decompressed_size=1024 * 1024,
            max_decompression_time=5.0
        )
        self.test_config = CompressionConfig(
            security_config=self.security_config
        )
    
    def test_initialization(self):
        """Test CompressionManager initialization."""
        manager = CompressionManager()
        assert manager.config is not None
        assert manager.metrics is not None
        assert len(manager.supported_types) > 0
        assert CompressionType.GZIP in manager.supported_types
    
    def test_initialization_with_config(self):
        """Test CompressionManager initialization with custom config."""
        manager = CompressionManager(config=self.test_config)
        assert manager.config == self.test_config
        assert manager.config.security_config.max_compression_ratio == 100.0
    
    def test_initialization_with_security_validator(self):
        """Test CompressionManager initialization with security validator."""
        mock_validator = MockSecurityValidator()
        manager = CompressionManager(security_validator=mock_validator)
        assert manager.security_validator == mock_validator
    
    def test_should_compress_logic(self):
        """Test compression decision logic."""
        manager = CompressionManager(config=self.test_config)
        
        # Small data should not be compressed
        assert not manager.should_compress(self.small_data)
        
        # Large enough data should be compressed
        assert manager.should_compress(self.test_data)
        
        # Disabled compression should return False
        manager.config.enabled = False
        assert not manager.should_compress(self.test_data)
    
    def test_gzip_compression(self):
        """Test Gzip compression and decompression."""
        manager = CompressionManager(config=self.test_config)
        
        compressed, compression_type = manager.compress(self.test_data, CompressionType.GZIP)
        assert compression_type == CompressionType.GZIP
        assert len(compressed) < len(self.test_data)
        
        decompressed = manager.decompress(compressed, CompressionType.GZIP)
        assert decompressed == self.test_data
    
    def test_brotli_compression(self):
        """Test Brotli compression if available."""
        manager = CompressionManager(config=self.test_config)
        
        # Skip if Brotli is not available
        if CompressionType.BROTLI not in manager.supported_types:
            pytest.skip("Brotli not available")
        
        compressed, compression_type = manager.compress(self.test_data, CompressionType.BROTLI)
        assert compression_type == CompressionType.BROTLI
        assert len(compressed) < len(self.test_data)
        
        decompressed = manager.decompress(compressed, CompressionType.BROTLI)
        assert decompressed == self.test_data
    
    def test_no_compression_for_small_data(self):
        """Test that small data is not compressed."""
        manager = CompressionManager(config=self.test_config)
        
        compressed, compression_type = manager.compress(self.small_data)
        assert compression_type == CompressionType.NONE
        assert compressed == self.small_data
    
    def test_compression_doesnt_increase_size(self):
        """Test that compression is skipped if it doesn't reduce size."""
        manager = CompressionManager(config=self.test_config)
        
        # Create data that compresses poorly
        random_data = b'\x00\x01\x02\x03' * 100
        
        with patch.object(manager, '_compress_gzip', return_value=random_data + b'extra'):
            compressed, compression_type = manager.compress(random_data, CompressionType.GZIP)
            assert compression_type == CompressionType.NONE
            assert compressed == random_data
    
    def test_zip_bomb_protection(self):
        """Test zip bomb detection and prevention."""
        manager = CompressionManager(config=self.test_config)
        
        # Create a fake compressed data that would decompress to huge size
        fake_compressed = b"fake compressed data"
        
        # Mock the decompression to return huge data
        huge_data = b"A" * (2 * 1024 * 1024)  # 2MB
        
        # Disable header validation to test zip bomb detection
        manager.config.security_config.validate_compressed_headers = False
        with patch.object(manager, '_decompress_gzip_safe', return_value=huge_data):
            with pytest.raises(ZipBombError) as exc_info:
                manager.decompress(fake_compressed, CompressionType.GZIP)
            
            assert "compression ratio" in str(exc_info.value)
            assert manager.metrics.zip_bomb_attempts == 1
    
    def test_decompression_size_limit(self):
        """Test maximum decompression size limit."""
        # Create config with small max size
        small_limit_config = CompressionSecurityConfig(
            max_decompressed_size=100,  # Very small limit
            max_compression_ratio=1000.0,
            validate_compressed_headers=False  # Disable header validation
        )
        config = CompressionConfig(
            security_config=small_limit_config,
            minimum_size_threshold=10  # Set very low threshold to ensure compression happens
        )
        manager = CompressionManager(config=config)
        
        # Compress data larger than the limit
        large_data = b"Large data " * 50  # 550 bytes
        compressed, compression_type = manager.compress(large_data, CompressionType.GZIP)
        
        # Ensure compression actually happened
        assert compression_type == CompressionType.GZIP
        
        # Should raise error due to size limit
        with pytest.raises(ZipBombError):
            manager.decompress(compressed, CompressionType.GZIP)
    
    def test_rate_limiting(self):
        """Test decompression rate limiting."""
        # Create config with very low rate limit
        rate_limit_config = CompressionSecurityConfig(
            enable_rate_limiting=True,
            max_decompressions_per_minute=2
        )
        config = CompressionConfig(security_config=rate_limit_config)
        manager = CompressionManager(config=config)
        
        # Compress test data
        compressed, _ = manager.compress(self.test_data, CompressionType.GZIP)
        
        # First two decompressions should work
        manager.decompress(compressed, CompressionType.GZIP)
        manager.decompress(compressed, CompressionType.GZIP)
        
        # Third should fail due to rate limit
        with pytest.raises(CompressionError) as exc_info:
            manager.decompress(compressed, CompressionType.GZIP)
        assert "rate limit" in str(exc_info.value)
    
    def test_security_validator_integration(self):
        """Test integration with security validator."""
        mock_validator = MockSecurityValidator()
        
        # Create config that ensures compression happens
        test_config = CompressionConfig(
            minimum_size_threshold=10,  # Set very low threshold
            security_config=CompressionSecurityConfig(
                max_compression_ratio=100.0,
                max_decompressed_size=1024 * 1024,
                max_decompression_time=5.0,
                validate_compressed_headers=False,  # Disable header validation
                validate_decompressed_data=True
            )
        )
        
        manager = CompressionManager(
            config=test_config,
            security_validator=mock_validator
        )
        
        # Compression should call validator on input
        compressed, compression_type = manager.compress(self.test_data)
        assert len(mock_validator.validate_calls) == 1
        assert mock_validator.validate_calls[0][0] == self.test_data
        assert mock_validator.validate_calls[0][1] == "compression_input"
        
        # Ensure compression actually happened
        assert compression_type != CompressionType.NONE
        
        # Decompression should call validator on output if configured
        mock_validator.validate_calls.clear()
        
        manager.decompress(compressed, compression_type)
        # Should have called validator on decompressed output
        assert len(mock_validator.validate_calls) == 1
        assert mock_validator.validate_calls[0][1] == "decompression_output"
    
    def test_security_validator_failure(self):
        """Test handling of security validator failures."""
        mock_validator = MockSecurityValidator(should_fail=True)
        manager = CompressionManager(
            config=self.test_config,
            security_validator=mock_validator
        )
        
        # Compression should continue even if validation fails (with warning)
        compressed, compression_type = manager.compress(self.test_data)
        assert compression_type != CompressionType.NONE
        assert manager.metrics.security_violations == 1
    
    def test_compression_header_validation(self):
        """Test compressed data header validation."""
        manager = CompressionManager(config=self.test_config)
        
        # Valid gzip header should pass
        valid_gzip = gzip.compress(b"test data")
        manager.decompress(valid_gzip, CompressionType.GZIP)
        
        # Invalid header should fail
        invalid_data = b"not a gzip file"
        with pytest.raises(CompressionError):
            manager.decompress(invalid_data, CompressionType.GZIP)
    
    def test_unsupported_compression_type(self):
        """Test handling of unsupported compression types."""
        manager = CompressionManager(config=self.test_config)
        
        # Create a fake compression type (assuming LZ4 might not be available)
        fake_type = CompressionType.LZ4
        
        # Mock LZ4 as unavailable
        with patch('spacetimedb_sdk.compression_handlers.compression_manager.LZ4_AVAILABLE', False):
            with pytest.raises(UnsupportedCompressionError):
                manager.compress(self.test_data, fake_type)
            
            with pytest.raises(UnsupportedCompressionError):
                manager.decompress(b"fake compressed", fake_type)
    
    def test_metrics_tracking(self):
        """Test compression metrics tracking."""
        manager = CompressionManager(config=self.test_config)
        
        # Perform compression and decompression
        compressed, compression_type = manager.compress(self.test_data, CompressionType.GZIP)
        decompressed = manager.decompress(compressed, CompressionType.GZIP)
        
        metrics = manager.get_metrics()
        assert metrics.total_messages_compressed == 1
        assert metrics.total_messages_decompressed == 1
        assert metrics.total_bytes_before_compression == len(self.test_data)
        assert metrics.total_bytes_after_compression == len(compressed)
        assert metrics.gzip_compressions == 1
        assert metrics.get_compression_ratio() == len(compressed) / len(self.test_data)
        assert metrics.get_space_savings_percent() > 0
    
    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        manager = CompressionManager(config=self.test_config)
        
        # Generate some metrics
        manager.compress(self.test_data, CompressionType.GZIP)
        assert manager.get_metrics().total_messages_compressed == 1
        
        # Reset metrics
        manager.reset_metrics()
        assert manager.get_metrics().total_messages_compressed == 0
    
    def test_adaptive_threshold(self):
        """Test adaptive compression threshold."""
        config = CompressionConfig(
            adaptive_threshold=True,
            minimum_size_threshold=1000
        )
        manager = CompressionManager(config=config)
        
        # Perform several compressions to populate adaptive data
        for _ in range(10):
            test_data = b"Good compression data " * 50
            manager.compress(test_data, CompressionType.GZIP)
        
        # Adaptive threshold should be different from base
        adaptive_threshold = manager._get_adaptive_threshold()
        # This is hard to test deterministically, but we can check it's reasonable
        assert 500 <= adaptive_threshold <= 2000
    
    def test_thread_safety(self):
        """Test thread safety of compression operations."""
        manager = CompressionManager(config=self.test_config)
        
        results = []
        errors = []
        
        def compress_decompress():
            try:
                compressed, compression_type = manager.compress(self.test_data)
                decompressed = manager.decompress(compressed, compression_type)
                results.append(decompressed == self.test_data)
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=compress_decompress)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert all(results), "Some compressions failed"
        assert len(results) == 10
    
    def test_compression_info(self):
        """Test comprehensive compression information."""
        manager = CompressionManager(config=self.test_config)
        
        info = manager.get_compression_info()
        
        # Check required sections
        assert "config" in info
        assert "capabilities" in info
        assert "security" in info
        assert "metrics" in info
        assert "adaptive" in info
        
        # Check security info
        assert info["security"]["zip_bomb_protection"] is True
        assert info["security"]["max_compression_ratio"] == 100.0
        
        # Check capabilities
        assert isinstance(info["capabilities"]["supported_types"], list)
        assert len(info["capabilities"]["supported_types"]) > 0
    
    def test_compression_negotiation(self):
        """Test compression type negotiation."""
        manager = CompressionManager(config=self.test_config)
        
        # Test successful negotiation
        client_types = ["gzip", "brotli"]
        server_types = ["gzip", "deflate"]
        negotiated = manager.negotiate_compression(client_types, server_types)
        assert negotiated == CompressionType.GZIP
        
        # Test no common type
        client_types = ["brotli"]
        server_types = ["deflate"]
        negotiated = manager.negotiate_compression(client_types, server_types)
        assert negotiated is None
    
    def test_compression_headers(self):
        """Test compression header creation and parsing."""
        manager = CompressionManager(config=self.test_config)
        
        # Test header creation
        headers = manager.create_compression_headers()
        assert "Accept-Encoding" in headers
        assert "X-SpacetimeDB-Compression" in headers
        
        # Test header parsing
        test_headers = {
            "Content-Encoding": "gzip",
            "X-SpacetimeDB-Compression": "brotli, gzip"
        }
        types = manager.parse_compression_headers(test_headers)
        assert CompressionType.GZIP in types
    
    def test_security_context_manager(self):
        """Test security context manager for enhanced security."""
        manager = CompressionManager(config=self.test_config)
        
        original_ratio = manager.config.security_config.max_compression_ratio
        
        with manager.security_context(enhanced_security=True):
            # Should have stricter limits
            enhanced_ratio = manager.config.security_config.max_compression_ratio
            assert enhanced_ratio < original_ratio
        
        # Should restore original limits
        assert manager.config.security_config.max_compression_ratio == original_ratio
    
    def test_error_handling(self):
        """Test proper error handling and conversion."""
        manager = CompressionManager(config=self.test_config)
        
        # Test compression error
        with patch.object(manager, '_compress_gzip', side_effect=Exception("Test error")):
            with pytest.raises(CompressionError) as exc_info:
                manager.compress(self.test_data, CompressionType.GZIP)
            assert "Compression failed" in str(exc_info.value)
            assert manager.metrics.compression_errors == 1
        
        # Test decompression error - disable header validation to test safe decompression
        manager.config.security_config.validate_compressed_headers = False
        with patch.object(manager, '_decompress_gzip_safe', side_effect=Exception("Test error")):
            with pytest.raises(CompressionError) as exc_info:
                manager.decompress(b"fake", CompressionType.GZIP)
            assert "Decompression failed" in str(exc_info.value)
            assert manager.metrics.decompression_errors == 1
    
    def test_performance_benchmarks(self):
        """Test compression performance characteristics."""
        # Create config with higher compression ratio limit to prevent false zip bomb alerts
        performance_config = CompressionConfig(
            minimum_size_threshold=10,  # Ensure compression happens
            security_config=CompressionSecurityConfig(
                max_compression_ratio=1000.0,  # Set high limit to avoid false zip bomb detection
                max_decompressed_size=1024 * 1024,
                max_decompression_time=5.0
            )
        )
        manager = CompressionManager(config=performance_config)
        
        # Test compression speed
        start_time = time.time()
        compressed, compression_type = manager.compress(self.large_data, CompressionType.GZIP)
        compression_time = time.time() - start_time
        
        # Should be reasonably fast (less than 1 second for test data)
        assert compression_time < 1.0
        
        # Ensure compression actually happened
        assert compression_type == CompressionType.GZIP
        
        # Test decompression speed
        start_time = time.time()
        decompressed = manager.decompress(compressed, CompressionType.GZIP)
        decompression_time = time.time() - start_time
        
        # Should be even faster than compression
        assert decompression_time < compression_time
        assert decompressed == self.large_data
        
        # Check compression ratio
        ratio = len(compressed) / len(self.large_data)
        assert ratio < 0.5  # Should achieve at least 50% compression


@pytest.mark.integration
class TestCompressionManagerIntegration:
    """Integration tests for CompressionManager with real security components."""
    
    def test_real_security_manager_integration(self):
        """Test integration with real SecurityManager if available."""
        try:
            from spacetimedb_sdk.validation.security_manager import SecurityManager
            
            security_manager = SecurityManager()
            manager = CompressionManager(security_validator=security_manager)
            
            # Should work without errors
            test_data = b"Integration test data " * 100
            compressed, compression_type = manager.compress(test_data)
            decompressed = manager.decompress(compressed, compression_type)
            
            assert decompressed == test_data
            
        except ImportError:
            pytest.skip("Security framework not available")
    
    def test_websocket_client_compatibility(self):
        """Test compatibility with WebSocketClient usage patterns."""
        # This would test the patterns used in WebSocketClient
        config = CompressionConfig(
            minimum_size_threshold=512,
            compression_level=CompressionLevel.BALANCED
        )
        
        manager = CompressionManager(config=config)
        
        # Test header creation (used in connection setup)
        headers = manager.create_compression_headers()
        assert isinstance(headers, dict)
        
        # Test compression/decompression cycle (used in message handling)
        test_message = b'{"type": "subscribe", "data": "' + b"test data " * 100 + b'"}'
        
        compressed, compression_type = manager.compress(test_message)
        if compression_type != CompressionType.NONE:
            decompressed = manager.decompress(compressed, compression_type)
            assert decompressed == test_message
        
        # Test metrics (used in monitoring)
        info = manager.get_compression_info()
        assert "metrics" in info
        assert "capabilities" in info


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])