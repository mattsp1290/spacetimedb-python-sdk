"""
SpacetimeDB Compression Module

This module provides secure compression/decompression capabilities for WebSocket messages
with built-in protection against zip bomb attacks and other security threats.

Features:
- Multi-algorithm compression support (Brotli, Gzip, LZ4)
- Zip bomb protection with configurable limits
- Integration with SpacetimeDB security framework
- Performance monitoring and adaptive thresholds
- Memory-efficient streaming for large messages
- Thread-safe operations
"""

# Import from the compression_manager module to avoid circular imports
from .compression_manager import (
    CompressionType,
    CompressionLevel,
    CompressionMetrics,
    CompressionManager
)

# Define error classes
class CompressionError(Exception):
    """Base compression error."""
    pass

class ZipBombError(CompressionError):
    """Zip bomb protection error."""
    pass

class UnsupportedCompressionError(CompressionError):
    """Unsupported compression type error."""
    pass

class CompressionConfig:
    """Compression configuration placeholder."""
    pass

class CompressionSecurityConfig:
    """Compression security configuration placeholder."""
    pass

__all__ = [
    'CompressionManager',
    'CompressionType',
    'CompressionLevel', 
    'CompressionConfig',
    'CompressionMetrics',
    'CompressionSecurityConfig',
    'CompressionError',
    'ZipBombError',
    'UnsupportedCompressionError'
]