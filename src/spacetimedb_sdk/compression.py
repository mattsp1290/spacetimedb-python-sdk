"""
SpacetimeDB Message Compression Support

Provides Brotli and Gzip compression/decompression for WebSocket messages
to match TypeScript SDK compression capabilities and improve production performance.

Features:
- Brotli compression (primary, best compression)
- Gzip compression (fallback, broader compatibility)
- Adaptive compression thresholds based on message size and network conditions
- Compression performance monitoring and metrics
- Automatic compression negotiation
- Memory-efficient streaming for large messages
"""

import gzip
import time
import threading
import logging
from typing import Optional, Dict, Any, List, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import io

# Try to import brotli, gracefully handle if not available
try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False
    brotli = None


class CompressionType(Enum):
    """Supported compression types."""
    NONE = "none"
    GZIP = "gzip"
    BROTLI = "brotli"


class CompressionLevel(Enum):
    """Compression level presets."""
    FASTEST = "fastest"    # Fastest compression, larger size
    BALANCED = "balanced"  # Good balance of speed and compression
    BEST = "best"         # Best compression, slower


@dataclass
class CompressionMetrics:
    """Metrics for compression performance monitoring."""
    total_messages_compressed: int = 0
    total_messages_decompressed: int = 0
    total_bytes_before_compression: int = 0
    total_bytes_after_compression: int = 0
    total_compression_time: float = 0.0
    total_decompression_time: float = 0.0
    compression_errors: int = 0
    decompression_errors: int = 0
    
    # Per-type metrics
    gzip_compressions: int = 0
    brotli_compressions: int = 0
    
    def get_compression_ratio(self) -> float:
        """Get overall compression ratio (compressed / original)."""
        if self.total_bytes_before_compression == 0:
            return 1.0
        return self.total_bytes_after_compression / self.total_bytes_before_compression
    
    def get_average_compression_time(self) -> float:
        """Get average compression time per message."""
        if self.total_messages_compressed == 0:
            return 0.0
        return self.total_compression_time / self.total_messages_compressed
    
    def get_average_decompression_time(self) -> float:
        """Get average decompression time per message."""
        if self.total_messages_decompressed == 0:
            return 0.0
        return self.total_decompression_time / self.total_messages_decompressed
    
    def get_space_savings_percent(self) -> float:
        """Get space savings as percentage."""
        ratio = self.get_compression_ratio()
        return (1.0 - ratio) * 100.0
    
    def get_throughput_improvement(self) -> float:
        """Estimate throughput improvement from compression."""
        if self.total_bytes_before_compression == 0:
            return 0.0
        
        # Assume network transfer is much slower than compression
        # This is a simplified calculation
        compression_ratio = self.get_compression_ratio()
        if compression_ratio < 1.0:
            return (1.0 / compression_ratio) - 1.0
        return 0.0


@dataclass
class CompressionConfig:
    """Configuration for compression behavior."""
    enabled: bool = True
    prefer_brotli: bool = True  # Prefer Brotli over Gzip when available
    minimum_size_threshold: int = 1024  # Don't compress messages smaller than this (bytes)
    maximum_size_threshold: int = 10 * 1024 * 1024  # Don't compress messages larger than this (10MB)
    compression_level: CompressionLevel = CompressionLevel.BALANCED
    adaptive_threshold: bool = True  # Adjust threshold based on performance
    
    # Compression level mappings
    gzip_levels: Dict[CompressionLevel, int] = field(default_factory=lambda: {
        CompressionLevel.FASTEST: 1,
        CompressionLevel.BALANCED: 6,
        CompressionLevel.BEST: 9
    })
    
    brotli_levels: Dict[CompressionLevel, int] = field(default_factory=lambda: {
        CompressionLevel.FASTEST: 1,
        CompressionLevel.BALANCED: 6,
        CompressionLevel.BEST: 11
    })


class CompressionManager:
    """
    Manages message compression and decompression for SpacetimeDB WebSocket connections.
    
    Provides automatic compression type selection, performance monitoring,
    and adaptive threshold adjustment to optimize network performance.
    """
    
    def __init__(self, config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()
        self.metrics = CompressionMetrics()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        # Supported compression types (in order of preference)
        self.supported_types: List[CompressionType] = []
        if BROTLI_AVAILABLE and self.config.prefer_brotli:
            self.supported_types.append(CompressionType.BROTLI)
        self.supported_types.append(CompressionType.GZIP)
        self.supported_types.append(CompressionType.NONE)
        
        # Adaptive threshold tracking
        self._recent_compression_ratios: List[float] = []
        self._recent_compression_times: List[float] = []
        self._max_recent_samples = 100
        
        self.logger.info(f"CompressionManager initialized with types: {[t.value for t in self.supported_types]}")
    
    def get_supported_types(self) -> List[str]:
        """Get list of supported compression types for negotiation."""
        return [t.value for t in self.supported_types if t != CompressionType.NONE]
    
    def should_compress(self, data: bytes) -> bool:
        """
        Determine if data should be compressed based on size and configuration.
        
        Args:
            data: The data to potentially compress
            
        Returns:
            True if data should be compressed
        """
        if not self.config.enabled:
            return False
        
        data_size = len(data)
        
        # Check size thresholds
        if data_size < self.config.minimum_size_threshold:
            return False
        
        if data_size > self.config.maximum_size_threshold:
            return False
        
        # Adaptive threshold adjustment
        if self.config.adaptive_threshold:
            adjusted_threshold = self._get_adaptive_threshold()
            if data_size < adjusted_threshold:
                return False
        
        return True
    
    def compress(self, data: bytes, compression_type: Optional[CompressionType] = None) -> Tuple[bytes, CompressionType]:
        """
        Compress data using the specified or best available compression type.
        
        Args:
            data: The data to compress
            compression_type: Specific compression type to use (None for auto-select)
            
        Returns:
            Tuple of (compressed_data, compression_type_used)
            
        Raises:
            ValueError: If compression fails
        """
        if not self.should_compress(data):
            return data, CompressionType.NONE
        
        start_time = time.time()
        
        try:
            # Auto-select compression type if not specified
            if compression_type is None:
                compression_type = self._select_compression_type(data)
            
            # Perform compression
            if compression_type == CompressionType.BROTLI:
                compressed_data = self._compress_brotli(data)
            elif compression_type == CompressionType.GZIP:
                compressed_data = self._compress_gzip(data)
            else:
                compressed_data = data
                compression_type = CompressionType.NONE
            
            # Only use compression if it actually reduces size
            if len(compressed_data) >= len(data):
                self.logger.debug(f"Compression didn't reduce size ({len(data)} -> {len(compressed_data)}), using uncompressed")
                compressed_data = data
                compression_type = CompressionType.NONE
            
            # Update metrics
            compression_time = time.time() - start_time
            self._update_compression_metrics(
                original_size=len(data),
                compressed_size=len(compressed_data),
                compression_time=compression_time,
                compression_type=compression_type
            )
            
            return compressed_data, compression_type
            
        except Exception as e:
            with self._lock:
                self.metrics.compression_errors += 1
            
            self.logger.error(f"Compression failed: {e}")
            raise ValueError(f"Compression failed: {e}")
    
    def decompress(self, data: bytes, compression_type: CompressionType) -> bytes:
        """
        Decompress data using the specified compression type.
        
        Args:
            data: The compressed data
            compression_type: The compression type used
            
        Returns:
            Decompressed data
            
        Raises:
            ValueError: If decompression fails
        """
        if compression_type == CompressionType.NONE:
            return data
        
        start_time = time.time()
        
        try:
            # Perform decompression
            if compression_type == CompressionType.BROTLI:
                decompressed_data = self._decompress_brotli(data)
            elif compression_type == CompressionType.GZIP:
                decompressed_data = self._decompress_gzip(data)
            else:
                raise ValueError(f"Unsupported compression type: {compression_type}")
            
            # Update metrics
            decompression_time = time.time() - start_time
            self._update_decompression_metrics(decompression_time)
            
            return decompressed_data
            
        except Exception as e:
            with self._lock:
                self.metrics.decompression_errors += 1
            
            self.logger.error(f"Decompression failed: {e}")
            raise ValueError(f"Decompression failed: {e}")
    
    def _compress_brotli(self, data: bytes) -> bytes:
        """Compress data using Brotli."""
        if not BROTLI_AVAILABLE:
            raise ValueError("Brotli compression not available")
        
        quality = self.config.brotli_levels[self.config.compression_level]
        return brotli.compress(data, quality=quality)
    
    def _decompress_brotli(self, data: bytes) -> bytes:
        """Decompress Brotli data."""
        if not BROTLI_AVAILABLE:
            raise ValueError("Brotli decompression not available")
        
        return brotli.decompress(data)
    
    def _compress_gzip(self, data: bytes) -> bytes:
        """Compress data using Gzip."""
        compresslevel = self.config.gzip_levels[self.config.compression_level]
        
        # Use BytesIO for efficient in-memory compression
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=compresslevel) as gz:
            gz.write(data)
        
        return buffer.getvalue()
    
    def _decompress_gzip(self, data: bytes) -> bytes:
        """Decompress Gzip data."""
        return gzip.decompress(data)
    
    def _select_compression_type(self, data: bytes) -> CompressionType:
        """
        Select the best compression type for the given data.
        
        Args:
            data: The data to compress
            
        Returns:
            Best compression type to use
        """
        # For now, use simple preference order
        # In the future, could analyze data characteristics
        for compression_type in self.supported_types:
            if compression_type == CompressionType.NONE:
                continue
            
            # Check if compression type is available
            if compression_type == CompressionType.BROTLI and not BROTLI_AVAILABLE:
                continue
            
            return compression_type
        
        return CompressionType.NONE
    
    def _update_compression_metrics(
        self,
        original_size: int,
        compressed_size: int,
        compression_time: float,
        compression_type: CompressionType
    ) -> None:
        """Update compression metrics."""
        with self._lock:
            self.metrics.total_messages_compressed += 1
            self.metrics.total_bytes_before_compression += original_size
            self.metrics.total_bytes_after_compression += compressed_size
            self.metrics.total_compression_time += compression_time
            
            if compression_type == CompressionType.GZIP:
                self.metrics.gzip_compressions += 1
            elif compression_type == CompressionType.BROTLI:
                self.metrics.brotli_compressions += 1
            
            # Update adaptive threshold data
            if compression_type != CompressionType.NONE:
                compression_ratio = compressed_size / original_size
                self._recent_compression_ratios.append(compression_ratio)
                self._recent_compression_times.append(compression_time)
                
                # Keep only recent samples
                if len(self._recent_compression_ratios) > self._max_recent_samples:
                    self._recent_compression_ratios.pop(0)
                    self._recent_compression_times.pop(0)
    
    def _update_decompression_metrics(self, decompression_time: float) -> None:
        """Update decompression metrics."""
        with self._lock:
            self.metrics.total_messages_decompressed += 1
            self.metrics.total_decompression_time += decompression_time
    
    def _get_adaptive_threshold(self) -> int:
        """Get adaptive compression threshold based on recent performance."""
        base_threshold = self.config.minimum_size_threshold
        
        if not self._recent_compression_ratios:
            return base_threshold
        
        # Calculate average compression effectiveness
        avg_ratio = sum(self._recent_compression_ratios) / len(self._recent_compression_ratios)
        avg_time = sum(self._recent_compression_times) / len(self._recent_compression_times)
        
        # If compression is very effective (good ratio) and fast, lower threshold
        if avg_ratio < 0.7 and avg_time < 0.001:  # Very good compression and fast
            return max(base_threshold // 2, 512)
        
        # If compression is not very effective or slow, raise threshold
        if avg_ratio > 0.9 or avg_time > 0.01:  # Poor compression or slow
            return min(base_threshold * 2, 4096)
        
        return base_threshold
    
    def get_metrics(self) -> CompressionMetrics:
        """Get current compression metrics."""
        with self._lock:
            return self.metrics
    
    def reset_metrics(self) -> None:
        """Reset compression metrics."""
        with self._lock:
            self.metrics = CompressionMetrics()
            self._recent_compression_ratios.clear()
            self._recent_compression_times.clear()
    
    def get_compression_info(self) -> Dict[str, Any]:
        """Get comprehensive compression information."""
        metrics = self.get_metrics()
        
        return {
            "config": {
                "enabled": self.config.enabled,
                "prefer_brotli": self.config.prefer_brotli,
                "minimum_threshold": self.config.minimum_size_threshold,
                "compression_level": self.config.compression_level.value,
                "adaptive_threshold": self.config.adaptive_threshold
            },
            "capabilities": {
                "brotli_available": BROTLI_AVAILABLE,
                "supported_types": self.get_supported_types()
            },
            "metrics": {
                "messages_compressed": metrics.total_messages_compressed,
                "messages_decompressed": metrics.total_messages_decompressed,
                "compression_ratio": metrics.get_compression_ratio(),
                "space_savings_percent": metrics.get_space_savings_percent(),
                "average_compression_time_ms": metrics.get_average_compression_time() * 1000,
                "average_decompression_time_ms": metrics.get_average_decompression_time() * 1000,
                "compression_errors": metrics.compression_errors,
                "decompression_errors": metrics.decompression_errors,
                "gzip_compressions": metrics.gzip_compressions,
                "brotli_compressions": metrics.brotli_compressions
            },
            "adaptive": {
                "current_threshold": self._get_adaptive_threshold(),
                "recent_samples": len(self._recent_compression_ratios)
            }
        }
    
    def negotiate_compression(self, client_types: List[str], server_types: List[str]) -> Optional[CompressionType]:
        """
        Negotiate compression type between client and server.
        
        Args:
            client_types: Compression types supported by client
            server_types: Compression types supported by server
            
        Returns:
            Negotiated compression type or None if no common type
        """
        # Find first common compression type in order of client preference
        for client_type in client_types:
            if client_type in server_types:
                try:
                    return CompressionType(client_type)
                except ValueError:
                    continue
        
        return None
    
    def create_compression_headers(self) -> Dict[str, str]:
        """Create HTTP headers for compression negotiation."""
        headers = {}
        
        if self.config.enabled:
            supported = self.get_supported_types()
            if supported:
                # Use standard HTTP compression headers
                headers["Accept-Encoding"] = ", ".join(supported)
                headers["X-SpacetimeDB-Compression"] = ", ".join(supported)
        
        return headers
    
    def parse_compression_headers(self, headers: Dict[str, str]) -> List[CompressionType]:
        """Parse compression types from HTTP headers."""
        compression_types = []
        
        # Check standard compression header
        encoding_header = headers.get("Content-Encoding", "")
        spacetime_header = headers.get("X-SpacetimeDB-Compression", "")
        
        for header_value in [encoding_header, spacetime_header]:
            if header_value:
                for type_str in header_value.split(","):
                    type_str = type_str.strip()
                    try:
                        compression_type = CompressionType(type_str)
                        if compression_type not in compression_types:
                            compression_types.append(compression_type)
                    except ValueError:
                        continue
        
        return compression_types 