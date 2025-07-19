"""
Rust server optimized factory for SpacetimeDB clients.

This factory creates clients optimized for Rust SpacetimeDB servers,
taking advantage of Rust-specific performance characteristics and features.
"""

from typing import Dict, Any, Optional
import logging
from ..utils.error_formatting import ErrorFormatter

from .base import (
    SpacetimeDBClientFactoryBase,
    ServerLanguage,
    OptimizationProfile
)
from ..protocol import BIN_PROTOCOL, TEXT_PROTOCOL
from ..compression import CompressionType
from ..retry_policies import RetryPolicy

logger = logging.getLogger(__name__)


class RustOptimizedFactory(SpacetimeDBClientFactoryBase):
    """
    Factory for creating SpacetimeDB clients optimized for Rust servers.
    
    Rust servers typically offer:
    - Excellent binary protocol performance
    - High-efficiency compression
    - Low latency connections
    - Robust error handling
    """
    
    @property
    def server_language(self) -> ServerLanguage:
        """Get the server language this factory supports."""
        return ServerLanguage.RUST
    
    @property
    def supported_protocols(self) -> list[str]:
        """Get list of protocols supported by Rust servers."""
        return [BIN_PROTOCOL, TEXT_PROTOCOL]
    
    @property
    def optimization_capabilities(self) -> Dict[str, bool]:
        """Get optimization capabilities for Rust servers."""
        return {
            "binary_protocol": True,
            "brotli_compression": True,
            "gzip_compression": True,
            "high_energy_budget": True,
            "fast_reconnect": True,
            "connection_pooling": True,
            "efficient_serialization": True,
            "low_latency": True,
            "high_throughput": True,
        }
    
    def get_recommended_config(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    ) -> Dict[str, Any]:
        """
        Get recommended configuration for Rust servers.
        
        Rust servers perform best with:
        - Binary protocol for maximum efficiency
        - Brotli compression for optimal bandwidth usage
        - Higher energy budgets due to server efficiency
        - Aggressive retry policies for fast recovery
        """
        if optimization_profile == OptimizationProfile.PERFORMANCE:
            return self._get_rust_performance_config()
        elif optimization_profile == OptimizationProfile.RELIABILITY:
            return self._get_rust_reliability_config()
        elif optimization_profile == OptimizationProfile.MINIMAL:
            return self._get_rust_minimal_config()
        else:  # BALANCED
            return self._get_rust_balanced_config()
    
    def _get_rust_performance_config(self) -> Dict[str, Any]:
        """Get performance-optimized configuration for Rust servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Rust excels at binary protocol
            "compression": CompressionType.BROTLI,  # Best compression performance
            "energy_budget": 300000,  # High budget - Rust servers are efficient
            "retry_policy": RetryPolicy(
                max_attempts=3,
                initial_delay=0.05,  # Very fast retry - Rust handles well
                max_delay=0.5,
                exponential_base=1.5
            ),
            "connection_timeout": 5.0,  # Rust servers connect quickly
            "keep_alive": True,
            "heartbeat_interval": 30.0,  # Less frequent - Rust is stable
            "buffer_size": 128 * 1024,  # 128KB buffer for high throughput
            "batch_size": 1000,  # Large batches work well with Rust
            "concurrent_requests": 10,  # Rust handles concurrency well
            "enable_connection_pooling": True,
            "pool_size": 5,
        }
    
    def _get_rust_reliability_config(self) -> Dict[str, Any]:
        """Get reliability-optimized configuration for Rust servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Still use binary for efficiency
            "compression": CompressionType.GZIP,  # More conservative compression
            "energy_budget": 200000,  # Conservative but reasonable
            "retry_policy": RetryPolicy(
                max_attempts=8,
                initial_delay=0.5,
                max_delay=16.0,
                exponential_base=2.0
            ),
            "connection_timeout": 20.0,
            "keep_alive": True,
            "heartbeat_interval": 15.0,  # More frequent health checks
            "buffer_size": 32 * 1024,  # Smaller buffer for reliability
            "batch_size": 100,  # Smaller batches for error isolation
            "concurrent_requests": 3,  # Conservative concurrency
            "enable_connection_pooling": True,
            "pool_size": 2,
            "health_check_interval": 10.0,
        }
    
    def _get_rust_balanced_config(self) -> Dict[str, Any]:
        """Get balanced configuration for Rust servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Binary protocol is Rust's strength
            "compression": CompressionType.BROTLI,  # Good compression efficiency
            "energy_budget": 250000,  # Higher than other languages
            "retry_policy": RetryPolicy(
                max_attempts=5,
                initial_delay=0.2,
                max_delay=8.0,
                exponential_base=2.0
            ),
            "connection_timeout": 15.0,
            "keep_alive": True,
            "heartbeat_interval": 20.0,
            "buffer_size": 64 * 1024,  # 64KB buffer
            "batch_size": 500,  # Good balance
            "concurrent_requests": 5,  # Moderate concurrency
            "enable_connection_pooling": True,
            "pool_size": 3,
        }
    
    def _get_rust_minimal_config(self) -> Dict[str, Any]:
        """Get minimal configuration for Rust servers."""
        return {
            "protocol": TEXT_PROTOCOL,  # Simpler for minimal setup
            "compression": CompressionType.NONE,  # No compression overhead
            "energy_budget": 100000,  # Conservative budget
            "retry_policy": RetryPolicy(
                max_attempts=2,
                initial_delay=1.0,
                max_delay=3.0,
                exponential_base=2.0
            ),
            "connection_timeout": 10.0,
            "keep_alive": False,  # Simpler connection management
            "buffer_size": 16 * 1024,  # Small buffer
            "batch_size": 50,  # Small batches
            "concurrent_requests": 1,  # No concurrency
            "enable_connection_pooling": False,
        }
    
    def validate_compatibility(
        self,
        server_version: Optional[str] = None
    ) -> bool:
        """
        Validate compatibility with Rust server.
        
        Rust servers are generally very compatible and stable.
        """
        if not super().validate_compatibility(server_version):
            return False
        
        # Rust-specific compatibility checks
        try:
            # Check if binary protocol is available
            if BIN_PROTOCOL not in self.supported_protocols:
                logger.warning("Binary protocol not available for Rust server")
                return False
            
            # Rust servers typically have good compression support
            capabilities = self.optimization_capabilities
            if not capabilities.get("brotli_compression", False):
                logger.warning("Brotli compression not available for Rust server")
            
            return True
            
        except Exception as e:
            logger.error(ErrorFormatter.format_generic_error("Rust Factory", "compatibility check", e))
            return False