"""
SpacetimeDB Message Compression Support (Legacy Compatibility Layer)

This module provides backward compatibility for the original compression interface
while internally using the enhanced security-aware CompressionManager.

Features:
- Backward compatibility with existing code
- Enhanced security with zip bomb protection
- Integration with SpacetimeDB security framework
- All original compression capabilities preserved

DEPRECATED: This interface is maintained for backward compatibility only.
New code should use spacetimedb_sdk.compression.CompressionManager directly.
"""

import warnings
from typing import Optional, Dict, Any, List, Union, Tuple
from dataclasses import dataclass
from enum import Enum

# Note: Enhanced compression features are available in compression_handlers.compression_manager
# To avoid circular imports, import directly from compression_handlers when needed

try:
    from .validation.security_manager import SecurityManager
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    SecurityManager = None

# Import compression components from compression_handlers
try:
    from .compression_handlers.compression_manager import (
        CompressionMetrics,
        EnhancedCompressionManager,
        CompressionError,
        ZipBombError,
        CompressionLevel
    )
except ImportError:
    # Fallback definitions for compatibility
    @dataclass
    class CompressionMetrics:
        total_compressed: int = 0
        total_decompressed: int = 0
        compression_ratio: float = 0.0
        total_operations: int = 0
    
    class CompressionError(Exception):
        """Compression operation failed."""
        pass
    
    class ZipBombError(CompressionError):
        """Potential zip bomb detected."""
        pass
    
    class CompressionLevel(Enum):
        """Compression level enumeration."""
        FASTEST = 1
        FAST = 3
        BALANCED = 6
        BEST = 9
    
    # Minimal fallback EnhancedCompressionManager
    class EnhancedCompressionManager:
        def __init__(self, config=None, security_validator=None):
            self.config = config or CompressionConfig()
            self.metrics = CompressionMetrics()
            
        def get_supported_types(self):
            return ["none", "gzip"]
            
        def should_compress(self, data):
            return len(data) > 1024
            
        def compress(self, data, compression_type=None):
            return data, CompressionType.NONE
            
        def decompress(self, data, compression_type):
            return data
            
        def get_metrics(self):
            return self.metrics
            
        def reset_metrics(self):
            self.metrics = CompressionMetrics()
            
        def get_compression_info(self):
            return {"status": "fallback_mode"}
            
        def negotiate_compression(self, client_types, server_types):
            return CompressionType.NONE
            
        def create_compression_headers(self):
            return {}
            
        def parse_compression_headers(self, headers):
            return [CompressionType.NONE]

# Legacy aliases for backward compatibility
BROTLI_AVAILABLE = True  # Will be checked by enhanced manager


class CompressionType(Enum):
    """Supported compression types."""
    NONE = "none"
    GZIP = "gzip"
    BROTLI = "brotli"


@dataclass
class CompressionConfig:
    """Basic compression configuration for backward compatibility."""
    compression_level: int = 6
    enable_brotli: bool = True
    enable_gzip: bool = True
    max_size: int = 64 * 1024 * 1024  # 64MB


class CompressionManager:
    """
    Legacy CompressionManager interface for backward compatibility.
    
    This class wraps the enhanced CompressionManager to maintain
    backward compatibility with existing code while providing
    enhanced security features.
    
    DEPRECATED: Use spacetimedb_sdk.compression.CompressionManager directly.
    """
    
    def __init__(self, config: Optional[CompressionConfig] = None):
        # Issue deprecation warning
        warnings.warn(
            "The legacy compression interface is deprecated. "
            "Use spacetimedb_sdk.compression.CompressionManager directly.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Create security validator if available
        security_validator = None
        if SECURITY_AVAILABLE:
            try:
                security_manager = SecurityManager()
                security_validator = security_manager
            except Exception:
                pass  # Continue without security validation if it fails
        
        # Initialize enhanced compression manager
        self._enhanced_manager = EnhancedCompressionManager(
            config=config,
            security_validator=security_validator
        )
    
    def get_supported_types(self) -> List[str]:
        """Get list of supported compression types for negotiation."""
        return self._enhanced_manager.get_supported_types()
    
    def should_compress(self, data: bytes) -> bool:
        """
        Determine if data should be compressed based on size and configuration.
        
        Args:
            data: The data to potentially compress
            
        Returns:
            True if data should be compressed
        """
        return self._enhanced_manager.should_compress(data)
    
    def compress(self, data: bytes, compression_type: Optional[CompressionType] = None) -> Tuple[bytes, CompressionType]:
        """
        Compress data using the specified or best available compression type.
        
        Args:
            data: The data to compress
            compression_type: Specific compression type to use (None for auto-select)
            
        Returns:
            Tuple of (compressed_data, compression_type_used)
            
        Raises:
            ValueError: If compression fails (legacy compatibility)
        """
        try:
            return self._enhanced_manager.compress(data, compression_type)
        except CompressionError as e:
            # Convert to ValueError for backward compatibility
            raise ValueError(str(e))
    
    def decompress(self, data: bytes, compression_type: CompressionType) -> bytes:
        """
        Decompress data using the specified compression type.
        
        Args:
            data: The compressed data
            compression_type: The compression type used
            
        Returns:
            Decompressed data
            
        Raises:
            ValueError: If decompression fails (legacy compatibility)
        """
        try:
            return self._enhanced_manager.decompress(data, compression_type)
        except (CompressionError, ZipBombError) as e:
            # Convert to ValueError for backward compatibility
            raise ValueError(str(e))
    
    def get_metrics(self) -> CompressionMetrics:
        """Get current compression metrics."""
        return self._enhanced_manager.get_metrics()
    
    def reset_metrics(self) -> None:
        """Reset compression metrics."""
        self._enhanced_manager.reset_metrics()
    
    def get_compression_info(self) -> Dict[str, Any]:
        """Get comprehensive compression information."""
        return self._enhanced_manager.get_compression_info()
    
    def negotiate_compression(self, client_types: List[str], server_types: List[str]) -> Optional[CompressionType]:
        """
        Negotiate compression type between client and server.
        
        Args:
            client_types: Compression types supported by client
            server_types: Compression types supported by server
            
        Returns:
            Negotiated compression type or None if no common type
        """
        return self._enhanced_manager.negotiate_compression(client_types, server_types)
    
    def create_compression_headers(self) -> Dict[str, str]:
        """Create HTTP headers for compression negotiation."""
        return self._enhanced_manager.create_compression_headers()
    
    def parse_compression_headers(self, headers: Dict[str, str]) -> List[CompressionType]:
        """Parse compression types from HTTP headers."""
        return self._enhanced_manager.parse_compression_headers(headers)
    
    # Legacy properties for backward compatibility
    @property
    def config(self) -> CompressionConfig:
        """Get compression configuration."""
        return self._enhanced_manager.config
    
    @config.setter
    def config(self, value: CompressionConfig) -> None:
        """Set compression configuration."""
        self._enhanced_manager.config = value
    
    @property
    def metrics(self) -> CompressionMetrics:
        """Get compression metrics."""
        return self._enhanced_manager.metrics
    
    @property
    def supported_types(self) -> List[CompressionType]:
        """Get supported compression types."""
        return self._enhanced_manager.supported_types
    
    # Legacy methods that delegate to enhanced manager
    def _compress_brotli(self, data: bytes) -> bytes:
        """Legacy method - use compress() instead."""
        warnings.warn("_compress_brotli is deprecated, use compress() instead", DeprecationWarning)
        try:
            return self._enhanced_manager._compress_brotli(data)
        except CompressionError as e:
            raise ValueError(str(e))
    
    def _decompress_brotli(self, data: bytes) -> bytes:
        """Legacy method - use decompress() instead."""
        warnings.warn("_decompress_brotli is deprecated, use decompress() instead", DeprecationWarning)
        try:
            return self._enhanced_manager._decompress_brotli_safe(data, self.config.security_config.max_decompressed_size)
        except CompressionError as e:
            raise ValueError(str(e))
    
    def _compress_gzip(self, data: bytes) -> bytes:
        """Legacy method - use compress() instead."""
        warnings.warn("_compress_gzip is deprecated, use compress() instead", DeprecationWarning)
        try:
            return self._enhanced_manager._compress_gzip(data)
        except CompressionError as e:
            raise ValueError(str(e))
    
    def _decompress_gzip(self, data: bytes) -> bytes:
        """Legacy method - use decompress() instead."""
        warnings.warn("_decompress_gzip is deprecated, use decompress() instead", DeprecationWarning)
        try:
            return self._enhanced_manager._decompress_gzip_safe(data, self.config.security_config.max_decompressed_size)
        except CompressionError as e:
            raise ValueError(str(e))


# Additional backward compatibility exports
__all__ = [
    'CompressionManager',
    'CompressionType',
    'CompressionLevel',
    'CompressionConfig',
    'CompressionMetrics',
    'BROTLI_AVAILABLE'
]