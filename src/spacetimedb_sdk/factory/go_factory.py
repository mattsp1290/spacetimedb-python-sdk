"""
Go server optimized factory for SpacetimeDB clients.

This factory creates clients optimized for Go SpacetimeDB servers,
taking advantage of Go-specific performance characteristics and features.
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


class GoOptimizedFactory(SpacetimeDBClientFactoryBase):
    """
    Factory for creating SpacetimeDB clients optimized for Go servers.
    
    Go servers typically offer:
    - Excellent binary protocol performance
    - Very good compression support
    - High concurrency capabilities
    - Low latency connections
    - Efficient memory usage
    - Strong error handling
    """
    
    @property
    def server_language(self) -> ServerLanguage:
        """Get the server language this factory supports."""
        return ServerLanguage.GO
    
    @property
    def supported_protocols(self) -> list[str]:
        """Get list of protocols supported by Go servers."""
        return [BIN_PROTOCOL, TEXT_PROTOCOL]
    
    @property
    def optimization_capabilities(self) -> Dict[str, bool]:
        """Get optimization capabilities for Go servers."""
        return {
            "binary_protocol": True,  # Go excels at binary operations
            "text_protocol": True,
            "gzip_compression": True,
            "brotli_compression": True,
            "high_energy_budget": True,
            "connection_pooling": True,
            "high_concurrency": True,  # Go's goroutines are excellent
            "efficient_serialization": True,  # Go serialization is fast
            "low_latency": True,  # Go has very low latency
            "high_throughput": True,
            "memory_efficient": True,  # Go has efficient memory management
            "fast_startup": True,  # Go compiles to fast-starting binaries
        }
    
    def get_recommended_config(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    ) -> Dict[str, Any]:
        """
        Get recommended configuration for Go servers.
        
        Go servers work best with:
        - Binary protocol for maximum performance
        - Excellent compression support
        - High concurrency settings (goroutines)
        - Aggressive connection settings due to efficiency
        """
        if optimization_profile == OptimizationProfile.PERFORMANCE:
            return self._get_go_performance_config()
        elif optimization_profile == OptimizationProfile.RELIABILITY:
            return self._get_go_reliability_config()
        elif optimization_profile == OptimizationProfile.MINIMAL:
            return self._get_go_minimal_config()
        else:  # BALANCED
            return self._get_go_balanced_config()
    
    def _get_go_performance_config(self) -> Dict[str, Any]:
        """Get performance-optimized configuration for Go servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Go excels at binary operations
            "compression": CompressionType.BROTLI,  # Go handles compression well
            "energy_budget": 320000,  # High budget - Go is very efficient
            "retry_policy": RetryPolicy(
                max_attempts=3,
                initial_delay=0.05,  # Very fast retry - Go handles well
                max_delay=0.5,
                exponential_base=1.5
            ),
            "connection_timeout": 5.0,  # Go servers are fast
            "keep_alive": True,
            "heartbeat_interval": 25.0,  # Less frequent - Go is stable
            "buffer_size": 128 * 1024,  # 128KB buffer for high throughput
            "batch_size": 1000,  # Large batches work well with Go
            "concurrent_requests": 15,  # Go excels at concurrency
            "enable_connection_pooling": True,
            "pool_size": 8,  # Large pool - Go handles many connections
            "request_timeout": 20.0,
            "enable_pipelining": True,  # Go handles pipelining well
        }
    
    def _get_go_reliability_config(self) -> Dict[str, Any]:
        """Get reliability-optimized configuration for Go servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Still use binary for efficiency
            "compression": CompressionType.GZIP,  # More conservative compression
            "energy_budget": 240000,  # Conservative but reasonable
            "retry_policy": RetryPolicy(
                max_attempts=7,
                initial_delay=0.3,
                max_delay=15.0,
                exponential_base=2.0
            ),
            "connection_timeout": 20.0,
            "keep_alive": True,
            "heartbeat_interval": 15.0,  # More frequent health checks
            "buffer_size": 32 * 1024,  # Smaller buffer for reliability
            "batch_size": 200,  # Smaller batches for error isolation
            "concurrent_requests": 5,  # Conservative concurrency
            "enable_connection_pooling": True,
            "pool_size": 3,
            "request_timeout": 40.0,
            "health_check_interval": 10.0,
            "enable_circuit_breaker": True,
        }
    
    def _get_go_balanced_config(self) -> Dict[str, Any]:
        """Get balanced configuration for Go servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Go's strength
            "compression": CompressionType.BROTLI,  # Good compression
            "energy_budget": 280000,  # Higher than most languages
            "retry_policy": RetryPolicy(
                max_attempts=5,
                initial_delay=0.15,
                max_delay=8.0,
                exponential_base=2.0
            ),
            "connection_timeout": 12.0,
            "keep_alive": True,
            "heartbeat_interval": 20.0,
            "buffer_size": 64 * 1024,  # 64KB buffer
            "batch_size": 600,  # Good batch size for Go
            "concurrent_requests": 8,  # Good concurrency for Go
            "enable_connection_pooling": True,
            "pool_size": 4,
            "request_timeout": 30.0,
        }
    
    def _get_go_minimal_config(self) -> Dict[str, Any]:
        """Get minimal configuration for Go servers."""
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
            "request_timeout": 25.0,
        }
    
    def validate_compatibility(
        self,
        server_version: Optional[str] = None
    ) -> bool:
        """
        Validate compatibility with Go server.
        
        Go servers are generally very compatible and performant.
        """
        if not super().validate_compatibility(server_version):
            return False
        
        # Go-specific compatibility checks
        try:
            # Check if binary protocol is available (Go strength)
            if BIN_PROTOCOL not in self.supported_protocols:
                logger.warning("Binary protocol not available for Go server")
                return False
            
            # Go servers should have excellent compression support
            capabilities = self.optimization_capabilities
            if not capabilities.get("brotli_compression", False):
                logger.warning("Brotli compression not available for Go server")
            
            # Check for high concurrency support (Go strength)
            if not capabilities.get("high_concurrency", False):
                logger.warning("High concurrency not available for Go server")
            
            # Check for low latency capabilities
            if not capabilities.get("low_latency", False):
                logger.warning("Low latency not available for Go server")
            
            return True
            
        except Exception as e:
            logger.error(ErrorFormatter.format_generic_error("Go Factory", "compatibility check", e))
            return False