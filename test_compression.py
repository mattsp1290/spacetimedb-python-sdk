#!/usr/bin/env python3
"""
Tests for SpacetimeDB Message Compression Support

This test suite verifies the compression functionality works correctly
and provides the same performance benefits as the TypeScript SDK.
"""

import sys
sys.path.append('src')

import pytest
import time
import random
import string
from unittest.mock import Mock, patch, MagicMock

from spacetimedb_sdk.compression import (
    CompressionManager,
    CompressionConfig,
    CompressionType,
    CompressionLevel,
    CompressionMetrics,
    BROTLI_AVAILABLE
)
from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder


class TestCompressionConfig:
    """Test compression configuration and settings."""
    
    def test_default_config(self):
        """Test default compression configuration."""
        config = CompressionConfig()
        
        assert config.enabled is True
        assert config.prefer_brotli is True
        assert config.minimum_size_threshold == 1024
        assert config.maximum_size_threshold == 10 * 1024 * 1024
        assert config.compression_level == CompressionLevel.BALANCED
        assert config.adaptive_threshold is True
    
    def test_custom_config(self):
        """Test custom compression configuration."""
        config = CompressionConfig(
            enabled=False,
            prefer_brotli=False,
            minimum_size_threshold=2048,
            compression_level=CompressionLevel.BEST,
            adaptive_threshold=False
        )
        
        assert config.enabled is False
        assert config.prefer_brotli is False
        assert config.minimum_size_threshold == 2048
        assert config.compression_level == CompressionLevel.BEST
        assert config.adaptive_threshold is False
    
    def test_compression_level_mappings(self):
        """Test compression level mappings for different algorithms."""
        config = CompressionConfig()
        
        # Test Gzip levels
        assert config.gzip_levels[CompressionLevel.FASTEST] == 1
        assert config.gzip_levels[CompressionLevel.BALANCED] == 6
        assert config.gzip_levels[CompressionLevel.BEST] == 9
        
        # Test Brotli levels
        assert config.brotli_levels[CompressionLevel.FASTEST] == 1
        assert config.brotli_levels[CompressionLevel.BALANCED] == 6
        assert config.brotli_levels[CompressionLevel.BEST] == 11


class TestCompressionManager:
    """Test the CompressionManager class functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = CompressionConfig()
        self.manager = CompressionManager(self.config)
    
    def test_manager_initialization(self):
        """Test compression manager initialization."""
        assert self.manager.config == self.config
        assert isinstance(self.manager.metrics, CompressionMetrics)
        
        # Check supported types
        supported_types = self.manager.get_supported_types()
        assert "gzip" in supported_types
        if BROTLI_AVAILABLE:
            assert "brotli" in supported_types
    
    def test_should_compress_logic(self):
        """Test compression decision logic."""
        # Small data should not be compressed
        small_data = b"x" * 100
        assert not self.manager.should_compress(small_data)
        
        # Large data should be compressed
        large_data = b"x" * 2048
        assert self.manager.should_compress(large_data)
        
        # Disabled compression
        self.manager.config.enabled = False
        assert not self.manager.should_compress(large_data)
    
    def test_gzip_compression(self):
        """Test Gzip compression and decompression."""
        original_data = b"Hello, World! " * 100  # Repeating data compresses well
        
        compressed_data, compression_type = self.manager.compress(
            original_data, CompressionType.GZIP
        )
        
        assert compression_type == CompressionType.GZIP
        assert len(compressed_data) < len(original_data)
        
        # Test decompression
        decompressed_data = self.manager.decompress(compressed_data, CompressionType.GZIP)
        assert decompressed_data == original_data
    
    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="Brotli not available")
    def test_brotli_compression(self):
        """Test Brotli compression and decompression."""
        original_data = b"SpacetimeDB compression test! " * 50
        
        compressed_data, compression_type = self.manager.compress(
            original_data, CompressionType.BROTLI
        )
        
        assert compression_type == CompressionType.BROTLI
        assert len(compressed_data) < len(original_data)
        
        # Test decompression
        decompressed_data = self.manager.decompress(compressed_data, CompressionType.BROTLI)
        assert decompressed_data == original_data
    
    def test_compression_auto_selection(self):
        """Test automatic compression type selection."""
        test_data = b"Auto-selection test data! " * 100
        
        compressed_data, compression_type = self.manager.compress(test_data)
        
        # Should select the preferred compression type
        if BROTLI_AVAILABLE and self.config.prefer_brotli:
            assert compression_type == CompressionType.BROTLI
        else:
            assert compression_type == CompressionType.GZIP
        
        assert len(compressed_data) < len(test_data)
    
    def test_compression_effectiveness_check(self):
        """Test that compression is only used when it reduces size."""
        # Random data that doesn't compress well
        random_data = bytes(random.randint(0, 255) for _ in range(2048))
        
        compressed_data, compression_type = self.manager.compress(random_data)
        
        # If compression doesn't help, should return original data
        if len(compressed_data) >= len(random_data):
            assert compression_type == CompressionType.NONE
            assert compressed_data == random_data
    
    def test_compression_levels(self):
        """Test different compression levels."""
        test_data = b"Compression level test! " * 100
        
        # Test different levels
        for level in CompressionLevel:
            self.manager.config.compression_level = level
            compressed_data, compression_type = self.manager.compress(test_data, CompressionType.GZIP)
            
            assert compression_type == CompressionType.GZIP
            assert len(compressed_data) < len(test_data)
    
    def test_compression_metrics(self):
        """Test compression metrics tracking."""
        test_data = b"Metrics test data! " * 100  # Make this larger
        
        # Initial metrics
        initial_metrics = self.manager.get_metrics()
        assert initial_metrics.total_messages_compressed == 0
        
        # Compress data
        compressed_data, compression_type = self.manager.compress(test_data)
        
        # Check updated metrics
        metrics = self.manager.get_metrics()
        assert metrics.total_messages_compressed == 1
        assert metrics.total_bytes_before_compression == len(test_data)
        assert metrics.total_bytes_after_compression == len(compressed_data)
        assert metrics.get_compression_ratio() < 1.0
        assert metrics.get_space_savings_percent() > 0
    
    def test_decompression_metrics(self):
        """Test decompression metrics tracking."""
        test_data = b"Decompression metrics test! " * 50  # Make this larger
        
        # Compress and decompress
        compressed_data, compression_type = self.manager.compress(test_data)
        self.manager.decompress(compressed_data, compression_type)
        
        # Check metrics
        metrics = self.manager.get_metrics()
        assert metrics.total_messages_decompressed == 1
        assert metrics.get_average_decompression_time() >= 0
    
    def test_adaptive_threshold(self):
        """Test adaptive compression threshold adjustment."""
        # Enable adaptive threshold
        self.manager.config.adaptive_threshold = True
        
        # Get initial threshold
        initial_threshold = self.manager._get_adaptive_threshold()
        assert initial_threshold == self.manager.config.minimum_size_threshold
        
        # Simulate some compressions with good ratios
        for _ in range(10):
            test_data = b"Very compressible data! " * 100
            self.manager.compress(test_data)
        
        # Threshold might be adjusted based on performance
        new_threshold = self.manager._get_adaptive_threshold()
        # The exact threshold depends on compression performance
        assert isinstance(new_threshold, int)
        assert new_threshold > 0
    
    def test_compression_error_handling(self):
        """Test compression error handling."""
        # Test with invalid compression type
        test_data = b"Error test data"
        
        with pytest.raises(ValueError):
            self.manager.decompress(test_data, CompressionType.BROTLI if not BROTLI_AVAILABLE else CompressionType.NONE)
    
    def test_compression_headers(self):
        """Test compression header creation and parsing."""
        # Test header creation
        headers = self.manager.create_compression_headers()
        
        if self.config.enabled:
            assert "Accept-Encoding" in headers
            assert "X-SpacetimeDB-Compression" in headers
            assert "gzip" in headers["Accept-Encoding"]
    
    def test_compression_negotiation(self):
        """Test compression type negotiation."""
        client_types = ["brotli", "gzip"]
        server_types = ["gzip", "deflate"]
        
        negotiated = self.manager.negotiate_compression(client_types, server_types)
        assert negotiated == CompressionType.GZIP  # First common type
        
        # No common types
        negotiated = self.manager.negotiate_compression(["brotli"], ["deflate"])
        assert negotiated is None
    
    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        # Generate some metrics with larger data to trigger compression
        test_data = b"Reset test data! " * 100  # Make this larger
        self.manager.compress(test_data)
        
        # Verify metrics exist
        metrics = self.manager.get_metrics()
        assert metrics.total_messages_compressed > 0
        
        # Reset metrics
        self.manager.reset_metrics()
        
        # Verify metrics are reset
        metrics = self.manager.get_metrics()
        assert metrics.total_messages_compressed == 0
        assert metrics.total_bytes_before_compression == 0


class TestCompressionIntegration:
    """Test compression integration with ModernSpacetimeDBClient."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.compression_config = CompressionConfig(
            enabled=True,
            minimum_size_threshold=512,
            compression_level=CompressionLevel.BALANCED
        )
    
    def test_client_compression_config(self):
        """Test client creation with compression configuration."""
        client = ModernSpacetimeDBClient(
            compression_config=self.compression_config,
            start_message_processing=False  # Disable for testing
        )
        
        assert client.compression_config == self.compression_config
        
        # Test compression info
        info = client.get_compression_info()
        assert info["config"]["enabled"] is True
        assert info["config"]["minimum_threshold"] == 512
    
    def test_client_compression_methods(self):
        """Test client compression control methods."""
        client = ModernSpacetimeDBClient(
            compression_config=self.compression_config,
            start_message_processing=False
        )
        
        # Test enabling/disabling compression
        client.enable_compression(False)
        assert client.compression_config.enabled is False
        
        client.enable_compression(True)
        assert client.compression_config.enabled is True
        
        # Test threshold setting
        client.set_compression_threshold(2048)
        assert client.compression_config.minimum_size_threshold == 2048
        
        # Test compression level
        client.set_compression_level(CompressionLevel.BEST)
        assert client.compression_config.compression_level == CompressionLevel.BEST
    
    def test_connection_builder_compression(self):
        """Test compression configuration through connection builder."""
        builder = SpacetimeDBConnectionBuilder()
        
        # Test compression configuration
        result = builder.with_compression(
            enabled=True,
            level=CompressionLevel.BEST,
            threshold=2048,
            prefer_brotli=False
        )
        
        assert result is builder  # Method chaining
        assert builder._compression_config.enabled is True
        assert builder._compression_config.compression_level == CompressionLevel.BEST
        assert builder._compression_config.minimum_size_threshold == 2048
        assert builder._compression_config.prefer_brotli is False
    
    def test_builder_compression_methods(self):
        """Test individual compression configuration methods."""
        builder = SpacetimeDBConnectionBuilder()
        
        # Test individual methods
        builder.enable_compression(True)
        assert builder._compression_config.enabled is True
        
        builder.with_compression_level(CompressionLevel.FASTEST)
        assert builder._compression_config.compression_level == CompressionLevel.FASTEST
        
        builder.with_compression_threshold(4096)
        assert builder._compression_config.minimum_size_threshold == 4096
        
        # Test validation
        with pytest.raises(ValueError):
            builder.with_compression_threshold(-1)


class TestCompressionPerformance:
    """Test compression performance and benchmarking."""
    
    def setup_method(self):
        """Setup performance test fixtures."""
        self.manager = CompressionManager()
    
    def test_compression_benchmark(self):
        """Basic compression performance benchmark."""
        # Generate test data of different types
        test_cases = [
            ("small_text", b"Hello World!" * 10),
            ("large_text", b"SpacetimeDB compression test! " * 1000),
            ("json_like", b'{"key": "value", "array": [1, 2, 3]} ' * 500),
            ("binary_like", bytes(range(256)) * 20)
        ]
        
        results = {}
        
        for test_name, test_data in test_cases:
            if len(test_data) < self.manager.config.minimum_size_threshold:
                continue
                
            start_time = time.time()
            compressed_data, compression_type = self.manager.compress(test_data)
            compression_time = time.time() - start_time
            
            start_time = time.time()
            decompressed_data = self.manager.decompress(compressed_data, compression_type)
            decompression_time = time.time() - start_time
            
            assert decompressed_data == test_data
            
            results[test_name] = {
                "original_size": len(test_data),
                "compressed_size": len(compressed_data),
                "compression_ratio": len(compressed_data) / len(test_data),
                "compression_time": compression_time,
                "decompression_time": decompression_time,
                "compression_type": compression_type.value
            }
        
        # Log results for analysis
        for test_name, result in results.items():
            print(f"\n{test_name}:")
            print(f"  Size: {result['original_size']} -> {result['compressed_size']} bytes")
            print(f"  Ratio: {result['compression_ratio']:.3f}")
            print(f"  Savings: {(1 - result['compression_ratio']) * 100:.1f}%")
            print(f"  Compression time: {result['compression_time'] * 1000:.2f}ms")
            print(f"  Type: {result['compression_type']}")
    
    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="Brotli not available")
    def test_brotli_vs_gzip_performance(self):
        """Compare Brotli vs Gzip performance."""
        test_data = b"Performance comparison test data! " * 500
        
        # Test Gzip
        start_time = time.time()
        gzip_compressed, _ = self.manager.compress(test_data, CompressionType.GZIP)
        gzip_time = time.time() - start_time
        
        # Test Brotli
        start_time = time.time()
        brotli_compressed, _ = self.manager.compress(test_data, CompressionType.BROTLI)
        brotli_time = time.time() - start_time
        
        print(f"\nCompression comparison:")
        print(f"Original size: {len(test_data)} bytes")
        print(f"Gzip: {len(gzip_compressed)} bytes ({gzip_time*1000:.2f}ms)")
        print(f"Brotli: {len(brotli_compressed)} bytes ({brotli_time*1000:.2f}ms)")
        
        # Brotli should generally compress better (smaller size)
        # Time comparison varies by implementation and data
        assert len(gzip_compressed) < len(test_data)
        assert len(brotli_compressed) < len(test_data)


class TestCompressionCompatibility:
    """Test TypeScript SDK compatibility patterns."""
    
    def test_typescript_pattern_compatibility(self):
        """Test that compression patterns match TypeScript SDK."""
        # TypeScript SDK uses these compression types
        typescript_types = ["brotli", "gzip"]
        
        manager = CompressionManager()
        python_types = manager.get_supported_types()
        
        # Python SDK should support the same types
        for ts_type in typescript_types:
            if ts_type == "brotli" and not BROTLI_AVAILABLE:
                continue
            assert ts_type in python_types
        
        # Test header format compatibility
        headers = manager.create_compression_headers()
        
        # Should use standard HTTP headers
        assert "Accept-Encoding" in headers
        
        # Should include TypeScript-compatible types
        encoding_header = headers["Accept-Encoding"]
        assert "gzip" in encoding_header
        if BROTLI_AVAILABLE:
            assert "brotli" in encoding_header


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"]) 