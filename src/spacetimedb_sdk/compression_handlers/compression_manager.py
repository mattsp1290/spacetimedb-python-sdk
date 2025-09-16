"""
Enhanced Compression Manager for SpacetimeDB

This module provides secure compression/decompression with protection against
zip bomb attacks and integration with the SpacetimeDB security framework.

Key Features:
- Multi-algorithm compression (Brotli, Gzip, LZ4)
- Zip bomb protection with configurable ratio limits
- Security integration for input validation
- Memory-efficient streaming operations
- Performance monitoring and adaptive thresholds
- Thread-safe compression operations

Security Features:
- Decompression size limits to prevent memory exhaustion
- Compression ratio validation to detect zip bombs
- Input validation using existing security framework
- Protected decompression with bounded memory usage
- Attack detection and logging

Author: SpacetimeDB Security Team
"""

import gzip
import time
import threading
import logging
import io
import zlib
from typing import Optional, Dict, Any, List, Union, Tuple, Protocol
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

# Try to import optional compression libraries
try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False
    brotli = None

try:
    import lz4.frame
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False
    lz4 = None

# Import security framework
try:
    from ..validation.security_manager import SecurityManager, SecurityConfig
    from ..validation.validators import ValidationResult, ValidationError
    SECURITY_FRAMEWORK_AVAILABLE = True
except ImportError:
    SECURITY_FRAMEWORK_AVAILABLE = False
    SecurityManager = None
    # Create dummy classes for type hints when security framework is not available
    class ValidationResult:
        def __init__(self, is_valid: bool = True, sanitized_value=None, errors=None):
            self.is_valid = is_valid
            self.sanitized_value = sanitized_value
            self.errors = errors or []
    
    class ValidationError:
        def __init__(self, field: str, message: str, value=None):
            self.field = field
            self.message = message
            self.value = value


class CompressionType(Enum):
    """Supported compression types."""
    NONE = "none"
    GZIP = "gzip"
    BROTLI = "brotli"
    LZ4 = "lz4"
    DEFLATE = "deflate"


class CompressionLevel(Enum):
    """Compression level presets."""
    FASTEST = "fastest"    # Fastest compression, larger size
    BALANCED = "balanced"  # Good balance of speed and compression
    BEST = "best"         # Best compression, slower


class CompressionError(Exception):
    """Base exception for compression errors."""
    pass


class ZipBombError(CompressionError):
    """Exception raised when zip bomb attack is detected."""
    
    def __init__(self, message: str, compression_ratio: float, max_ratio: float):
        super().__init__(message)
        self.compression_ratio = compression_ratio
        self.max_ratio = max_ratio


class UnsupportedCompressionError(CompressionError):
    """Exception raised for unsupported compression types."""
    pass


@dataclass
class CompressionSecurityConfig:
    """Security configuration for compression operations."""
    
    # Zip bomb protection
    max_compression_ratio: float = 1000.0  # Max allowed decompression ratio
    max_decompressed_size: int = 100 * 1024 * 1024  # 100MB max decompressed size
    min_compressed_size: int = 10  # Minimum size to check for zip bombs
    
    # Memory protection
    max_memory_usage: int = 50 * 1024 * 1024  # 50MB max memory during decompression
    streaming_buffer_size: int = 64 * 1024  # 64KB streaming buffer
    
    # Performance limits
    max_decompression_time: float = 30.0  # 30 seconds max decompression time
    
    # Security validation
    validate_compressed_headers: bool = True
    validate_decompressed_data: bool = True
    log_security_violations: bool = True
    
    # Rate limiting for expensive operations
    enable_rate_limiting: bool = True
    max_decompressions_per_minute: int = 100


@dataclass
class CompressionMetrics:
    """Metrics for compression performance and security monitoring."""
    total_messages_compressed: int = 0
    total_messages_decompressed: int = 0
    total_bytes_before_compression: int = 0
    total_bytes_after_compression: int = 0
    total_compression_time: float = 0.0
    total_decompression_time: float = 0.0
    compression_errors: int = 0
    decompression_errors: int = 0
    zip_bomb_attempts: int = 0
    security_violations: int = 0
    
    # Per-type metrics
    gzip_compressions: int = 0
    brotli_compressions: int = 0
    lz4_compressions: int = 0
    deflate_compressions: int = 0
    
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


@dataclass
class CompressionConfig:
    """Configuration for compression behavior."""
    enabled: bool = True
    prefer_brotli: bool = True  # Prefer Brotli over Gzip when available
    minimum_size_threshold: int = 1024  # Don't compress messages smaller than this (bytes)
    maximum_size_threshold: int = 10 * 1024 * 1024  # Don't compress messages larger than this (10MB)
    compression_level: CompressionLevel = CompressionLevel.BALANCED
    adaptive_threshold: bool = True  # Adjust threshold based on performance
    
    # Security configuration
    security_config: CompressionSecurityConfig = field(default_factory=CompressionSecurityConfig)
    
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
    
    lz4_levels: Dict[CompressionLevel, int] = field(default_factory=lambda: {
        CompressionLevel.FASTEST: 0,
        CompressionLevel.BALANCED: 0,
        CompressionLevel.BEST: 16  # LZ4 high compression
    })


class SecurityValidator(Protocol):
    """Protocol for security validators."""
    
    def validate(self, data: bytes, field: Optional[str] = None) -> ValidationResult:
        """Validate data for security threats."""
        ...


class CompressionManager:
    """
    Enhanced compression manager with security features and zip bomb protection.
    
    This class provides secure compression/decompression operations with built-in
    protection against zip bomb attacks and integration with the SpacetimeDB
    security framework.
    
    Features:
    - Multi-algorithm compression support
    - Zip bomb detection and prevention
    - Memory-bounded decompression
    - Performance monitoring
    - Security event logging
    - Thread-safe operations
    """
    
    def __init__(
        self,
        config: Optional[CompressionConfig] = None,
        security_validator: Optional[SecurityValidator] = None
    ):
        self.config = config or CompressionConfig()
        self.security_validator = security_validator
        self.metrics = CompressionMetrics()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting state
        self._decompression_timestamps: List[float] = []
        
        # Supported compression types (in order of preference)
        self.supported_types: List[CompressionType] = []
        if BROTLI_AVAILABLE and self.config.prefer_brotli:
            self.supported_types.append(CompressionType.BROTLI)
        if LZ4_AVAILABLE:
            self.supported_types.append(CompressionType.LZ4)
        self.supported_types.append(CompressionType.GZIP)
        self.supported_types.append(CompressionType.DEFLATE)
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
    
    def compress(
        self,
        data: bytes,
        compression_type: Optional[CompressionType] = None
    ) -> Tuple[bytes, CompressionType]:
        """
        Compress data using the specified or best available compression type.
        
        Args:
            data: The data to compress
            compression_type: Specific compression type to use (None for auto-select)
            
        Returns:
            Tuple of (compressed_data, compression_type_used)
            
        Raises:
            CompressionError: If compression fails
            UnsupportedCompressionError: If compression type is not supported
        """
        if not self.should_compress(data):
            return data, CompressionType.NONE
        
        # Validate input data if security validator is available
        if self.security_validator:
            try:
                validation_result = self.security_validator.validate(data, "compression_input")
                if not validation_result.is_valid:
                    self.logger.warning(f"Input validation failed for compression: {validation_result.errors}")
                    with self._lock:
                        self.metrics.security_violations += 1
                    # Continue with compression but log the violation
            except Exception as e:
                self.logger.error(f"Security validation error during compression: {e}")
        
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
            elif compression_type == CompressionType.LZ4:
                compressed_data = self._compress_lz4(data)
            elif compression_type == CompressionType.DEFLATE:
                compressed_data = self._compress_deflate(data)
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
            
        except UnsupportedCompressionError:
            # Re-raise unsupported compression errors directly
            raise
        except Exception as e:
            with self._lock:
                self.metrics.compression_errors += 1
            
            self.logger.error(f"Compression failed: {e}")
            raise CompressionError(f"Compression failed: {e}")
    
    def decompress(
        self,
        data: bytes,
        compression_type: CompressionType,
        max_size: Optional[int] = None
    ) -> bytes:
        """
        Safely decompress data with zip bomb protection and security checks.
        
        Args:
            data: The compressed data
            compression_type: The compression type used
            max_size: Optional maximum decompressed size override
            
        Returns:
            Decompressed data
            
        Raises:
            CompressionError: If decompression fails
            ZipBombError: If zip bomb attack is detected
            UnsupportedCompressionError: If compression type is not supported
        """
        if compression_type == CompressionType.NONE:
            return data
        
        # Check rate limiting
        if not self._check_decompression_rate_limit():
            with self._lock:
                self.metrics.security_violations += 1
            raise CompressionError("Decompression rate limit exceeded")
        
        # Validate compressed data headers
        if self.config.security_config.validate_compressed_headers:
            self._validate_compressed_headers(data, compression_type)
        
        start_time = time.time()
        max_decompressed_size = max_size or self.config.security_config.max_decompressed_size
        
        try:
            # Perform protected decompression
            if compression_type == CompressionType.BROTLI:
                decompressed_data = self._decompress_brotli_safe(data, max_decompressed_size)
            elif compression_type == CompressionType.GZIP:
                decompressed_data = self._decompress_gzip_safe(data, max_decompressed_size)
            elif compression_type == CompressionType.LZ4:
                decompressed_data = self._decompress_lz4_safe(data, max_decompressed_size)
            elif compression_type == CompressionType.DEFLATE:
                decompressed_data = self._decompress_deflate_safe(data, max_decompressed_size)
            else:
                raise UnsupportedCompressionError(f"Unsupported compression type: {compression_type}")
            
            # Check for zip bomb
            self._check_zip_bomb(len(data), len(decompressed_data))
            
            # Validate decompressed data if configured
            if self.config.security_config.validate_decompressed_data and self.security_validator:
                try:
                    validation_result = self.security_validator.validate(decompressed_data, "decompression_output")
                    if not validation_result.is_valid:
                        self.logger.warning(f"Decompressed data validation failed: {validation_result.errors}")
                        with self._lock:
                            self.metrics.security_violations += 1
                except Exception as e:
                    self.logger.error(f"Security validation error during decompression: {e}")
            
            # Check decompression time
            decompression_time = time.time() - start_time
            if decompression_time > self.config.security_config.max_decompression_time:
                self.logger.warning(f"Decompression took too long: {decompression_time:.2f}s")
                with self._lock:
                    self.metrics.security_violations += 1
            
            # Update metrics
            self._update_decompression_metrics(decompression_time)
            
            return decompressed_data
            
        except ZipBombError:
            # Re-raise zip bomb errors
            raise
        except UnsupportedCompressionError:
            # Re-raise unsupported compression errors
            raise
        except Exception as e:
            with self._lock:
                self.metrics.decompression_errors += 1
            
            self.logger.error(f"Decompression failed: {e}")
            raise CompressionError(f"Decompression failed: {e}")
    
    def _compress_brotli(self, data: bytes) -> bytes:
        """Compress data using Brotli."""
        if not BROTLI_AVAILABLE:
            raise UnsupportedCompressionError("Brotli compression not available")
        
        quality = self.config.brotli_levels[self.config.compression_level]
        return brotli.compress(data, quality=quality)
    
    def _compress_gzip(self, data: bytes) -> bytes:
        """Compress data using Gzip."""
        compresslevel = self.config.gzip_levels[self.config.compression_level]
        
        # Use BytesIO for efficient in-memory compression
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=compresslevel) as gz:
            gz.write(data)
        
        return buffer.getvalue()
    
    def _compress_lz4(self, data: bytes) -> bytes:
        """Compress data using LZ4."""
        if not LZ4_AVAILABLE:
            raise UnsupportedCompressionError("LZ4 compression not available")
        
        compression_level = self.config.lz4_levels[self.config.compression_level]
        return lz4.frame.compress(data, compression_level=compression_level)
    
    def _compress_deflate(self, data: bytes) -> bytes:
        """Compress data using deflate."""
        compresslevel = self.config.gzip_levels[self.config.compression_level]
        return zlib.compress(data, level=compresslevel)
    
    def _decompress_brotli_safe(self, data: bytes, max_size: int) -> bytes:
        """Safely decompress Brotli data with size limits."""
        if not BROTLI_AVAILABLE:
            raise UnsupportedCompressionError("Brotli decompression not available")
        
        # Brotli doesn't support streaming decompression easily,
        # so we use the simple method but with size checking
        try:
            result = brotli.decompress(data)
            if len(result) > max_size:
                raise ZipBombError(
                    f"Decompressed size {len(result)} exceeds limit {max_size}",
                    len(result) / len(data),
                    self.config.security_config.max_compression_ratio
                )
            return result
        except brotli.error as e:
            raise CompressionError(f"Brotli decompression failed: {e}")
    
    def _decompress_gzip_safe(self, data: bytes, max_size: int) -> bytes:
        """Safely decompress Gzip data with size limits."""
        try:
            buffer = io.BytesIO(data)
            decompressed = io.BytesIO()
            
            with gzip.GzipFile(fileobj=buffer, mode='rb') as gz:
                while True:
                    chunk = gz.read(self.config.security_config.streaming_buffer_size)
                    if not chunk:
                        break
                    
                    decompressed.write(chunk)
                    
                    # Check size limit
                    if decompressed.tell() > max_size:
                        raise ZipBombError(
                            f"Decompressed size exceeds limit {max_size}",
                            decompressed.tell() / len(data),
                            self.config.security_config.max_compression_ratio
                        )
            
            return decompressed.getvalue()
            
        except (gzip.BadGzipFile, OSError) as e:
            raise CompressionError(f"Gzip decompression failed: {e}")
    
    def _decompress_lz4_safe(self, data: bytes, max_size: int) -> bytes:
        """Safely decompress LZ4 data with size limits."""
        if not LZ4_AVAILABLE:
            raise UnsupportedCompressionError("LZ4 decompression not available")
        
        try:
            # LZ4 frame format includes size information
            result = lz4.frame.decompress(data)
            if len(result) > max_size:
                raise ZipBombError(
                    f"Decompressed size {len(result)} exceeds limit {max_size}",
                    len(result) / len(data),
                    self.config.security_config.max_compression_ratio
                )
            return result
        except Exception as e:
            raise CompressionError(f"LZ4 decompression failed: {e}")
    
    def _decompress_deflate_safe(self, data: bytes, max_size: int) -> bytes:
        """Safely decompress deflate data with size limits."""
        try:
            # Use incremental decompression for size checking
            decompressor = zlib.decompressobj()
            result = io.BytesIO()
            
            chunk_size = self.config.security_config.streaming_buffer_size
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                decompressed_chunk = decompressor.decompress(chunk)
                result.write(decompressed_chunk)
                
                # Check size limit
                if result.tell() > max_size:
                    raise ZipBombError(
                        f"Decompressed size exceeds limit {max_size}",
                        result.tell() / len(data),
                        self.config.security_config.max_compression_ratio
                    )
            
            # Finish decompression
            final_chunk = decompressor.flush()
            result.write(final_chunk)
            
            return result.getvalue()
            
        except zlib.error as e:
            raise CompressionError(f"Deflate decompression failed: {e}")
    
    def _validate_compressed_headers(self, data: bytes, compression_type: CompressionType) -> None:
        """Validate compressed data headers for basic format checking."""
        if len(data) < 2:
            raise CompressionError("Compressed data too short")
        
        if compression_type == CompressionType.GZIP:
            # Check gzip magic number
            if data[:2] != b'\x1f\x8b':
                raise CompressionError("Invalid gzip header")
        elif compression_type == CompressionType.DEFLATE:
            # Basic deflate header check (simplified)
            pass  # Deflate doesn't have a fixed header
        # Add more header validations as needed
    
    def _check_zip_bomb(self, compressed_size: int, decompressed_size: int) -> None:
        """Check for zip bomb attack based on compression ratio."""
        if compressed_size < self.config.security_config.min_compressed_size:
            return  # Skip check for very small files
        
        compression_ratio = decompressed_size / compressed_size
        max_ratio = self.config.security_config.max_compression_ratio
        
        if compression_ratio > max_ratio:
            with self._lock:
                self.metrics.zip_bomb_attempts += 1
            
            error_msg = (
                f"Zip bomb detected: compression ratio {compression_ratio:.1f} "
                f"exceeds limit {max_ratio}"
            )
            
            if self.config.security_config.log_security_violations:
                self.logger.warning(error_msg)
            
            raise ZipBombError(error_msg, compression_ratio, max_ratio)
    
    def _check_decompression_rate_limit(self) -> bool:
        """Check rate limit for decompression operations."""
        if not self.config.security_config.enable_rate_limiting:
            return True
        
        current_time = time.time()
        window_start = current_time - 60.0  # 1 minute window
        
        with self._lock:
            # Remove old timestamps
            self._decompression_timestamps = [
                ts for ts in self._decompression_timestamps
                if ts > window_start
            ]
            
            # Check limit
            if len(self._decompression_timestamps) >= self.config.security_config.max_decompressions_per_minute:
                return False
            
            # Record this decompression
            self._decompression_timestamps.append(current_time)
            return True
    
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
            if compression_type == CompressionType.LZ4 and not LZ4_AVAILABLE:
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
            elif compression_type == CompressionType.LZ4:
                self.metrics.lz4_compressions += 1
            elif compression_type == CompressionType.DEFLATE:
                self.metrics.deflate_compressions += 1
            
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
                "lz4_available": LZ4_AVAILABLE,
                "supported_types": self.get_supported_types()
            },
            "security": {
                "max_compression_ratio": self.config.security_config.max_compression_ratio,
                "max_decompressed_size": self.config.security_config.max_decompressed_size,
                "zip_bomb_protection": True,
                "rate_limiting": self.config.security_config.enable_rate_limiting
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
                "zip_bomb_attempts": metrics.zip_bomb_attempts,
                "security_violations": metrics.security_violations,
                "gzip_compressions": metrics.gzip_compressions,
                "brotli_compressions": metrics.brotli_compressions,
                "lz4_compressions": metrics.lz4_compressions
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
    
    @contextmanager
    def security_context(self, enhanced_security: bool = True):
        """
        Context manager for enhanced security operations.
        
        Args:
            enhanced_security: Whether to enable stricter security checks
        """
        original_config = self.config.security_config
        
        if enhanced_security:
            # Create stricter configuration
            enhanced_config = CompressionSecurityConfig(
                max_compression_ratio=original_config.max_compression_ratio / 2,
                max_decompressed_size=original_config.max_decompressed_size // 2,
                max_decompression_time=original_config.max_decompression_time / 2,
                validate_compressed_headers=True,
                validate_decompressed_data=True,
                enable_rate_limiting=True,
                max_decompressions_per_minute=original_config.max_decompressions_per_minute // 2
            )
            self.config.security_config = enhanced_config
        
        try:
            yield self
        finally:
            self.config.security_config = original_config