"""
C# server optimized factory for SpacetimeDB clients.

This factory creates clients optimized for C# SpacetimeDB servers,
taking advantage of .NET-specific performance characteristics and features.
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


class CSharpOptimizedFactory(SpacetimeDBClientFactoryBase):
    """
    Factory for creating SpacetimeDB clients optimized for C# servers.
    
    C# servers typically offer:
    - Excellent binary protocol performance (.NET serialization)
    - Good compression support
    - Strong async/await patterns
    - Robust error handling and recovery
    - Good connection pooling support
    """
    
    @property
    def server_language(self) -> ServerLanguage:
        """Get the server language this factory supports."""
        return ServerLanguage.CSHARP
    
    @property
    def supported_protocols(self) -> list[str]:
        """Get list of protocols supported by C# servers."""
        return [BIN_PROTOCOL, TEXT_PROTOCOL]
    
    @property
    def optimization_capabilities(self) -> Dict[str, bool]:
        """Get optimization capabilities for C# servers."""
        return {
            "binary_protocol": True,  # .NET excels at binary serialization
            "text_protocol": True,
            "gzip_compression": True,
            "brotli_compression": True,
            "high_energy_budget": True,
            "connection_pooling": True,
            "async_operations": True,  # C# async/await is excellent
            "efficient_serialization": True,  # .NET serialization is fast
            "good_latency": True,
            "high_reliability": True,
            "thread_safety": True,  # .NET threading model is robust
        }
    
    def get_recommended_config(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    ) -> Dict[str, Any]:
        """
        Get recommended configuration for C# servers.
        
        C# servers work well with:
        - Binary protocol for .NET serialization efficiency
        - Good compression support
        - Moderate to high energy budgets
        - Robust retry policies leveraging .NET error handling
        """
        if optimization_profile == OptimizationProfile.PERFORMANCE:
            return self._get_csharp_performance_config()
        elif optimization_profile == OptimizationProfile.RELIABILITY:
            return self._get_csharp_reliability_config()
        elif optimization_profile == OptimizationProfile.MINIMAL:
            return self._get_csharp_minimal_config()
        else:  # BALANCED
            return self._get_csharp_balanced_config()
    
    def _get_csharp_performance_config(self) -> Dict[str, Any]:
        """Get performance-optimized configuration for C# servers."""
        return {
            "protocol": BIN_PROTOCOL,  # .NET binary serialization is excellent
            "compression": CompressionType.BROTLI,  # Good compression performance
            "energy_budget": 280000,  # Good budget for .NET efficiency
            "retry_policy": RetryPolicy(
                max_attempts=4,
                initial_delay=0.1,
                max_delay=1.0,
                exponential_base=1.6
            ),
            "connection_timeout": 10.0,
            "keep_alive": True,
            "heartbeat_interval": 30.0,
            "buffer_size": 96 * 1024,  # 96KB - good for .NET
            "batch_size": 750,  # .NET handles large batches well
            "concurrent_requests": 8,  # .NET threading is good
            "enable_connection_pooling": True,
            "pool_size": 4,
            "request_timeout": 25.0,
            "enable_async_operations": True,
        }
    
    def _get_csharp_reliability_config(self) -> Dict[str, Any]:
        """Get reliability-optimized configuration for C# servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Still use binary for efficiency
            "compression": CompressionType.GZIP,  # More conservative compression
            "energy_budget": 220000,  # Conservative but reasonable
            "retry_policy": RetryPolicy(
                max_attempts=8,
                initial_delay=0.5,
                max_delay=20.0,
                exponential_base=2.0
            ),
            "connection_timeout": 25.0,
            "keep_alive": True,
            "heartbeat_interval": 12.0,  # Frequent health checks
            "buffer_size": 32 * 1024,  # Smaller buffer for reliability
            "batch_size": 200,  # Smaller batches for error isolation
            "concurrent_requests": 3,  # Conservative concurrency
            "enable_connection_pooling": True,
            "pool_size": 2,
            "request_timeout": 45.0,
            "health_check_interval": 10.0,
            "enable_detailed_logging": True,
        }
    
    def _get_csharp_balanced_config(self) -> Dict[str, Any]:
        """Get balanced configuration for C# servers."""
        return {
            "protocol": BIN_PROTOCOL,  # .NET's strength
            "compression": CompressionType.GZIP,  # Good balance
            "energy_budget": 250000,  # Good budget for .NET
            "retry_policy": RetryPolicy(
                max_attempts=5,
                initial_delay=0.3,
                max_delay=10.0,
                exponential_base=2.0
            ),
            "connection_timeout": 18.0,
            "keep_alive": True,
            "heartbeat_interval": 20.0,
            "buffer_size": 64 * 1024,  # 64KB buffer
            "batch_size": 400,  # Good batch size for .NET
            "concurrent_requests": 5,  # Moderate concurrency
            "enable_connection_pooling": True,
            "pool_size": 3,
            "request_timeout": 35.0,
        }
    
    def _get_csharp_minimal_config(self) -> Dict[str, Any]:
        """Get minimal configuration for C# servers."""
        return {
            "protocol": TEXT_PROTOCOL,  # Simpler for minimal setup
            "compression": CompressionType.NONE,  # No compression overhead
            "energy_budget": 120000,  # Conservative budget
            "retry_policy": RetryPolicy(
                max_attempts=3,
                initial_delay=1.0,
                max_delay=5.0,
                exponential_base=2.0
            ),
            "connection_timeout": 15.0,
            "keep_alive": False,  # Simpler connection management
            "buffer_size": 16 * 1024,  # Small buffer
            "batch_size": 100,  # Small batches
            "concurrent_requests": 1,  # No concurrency
            "enable_connection_pooling": False,
            "request_timeout": 30.0,
        }
    
    def validate_compatibility(
        self,
        server_version: Optional[str] = None
    ) -> bool:
        """
        Validate compatibility with C# server.
        
        C# servers should have good compatibility and robust error handling.
        """
        if not super().validate_compatibility(server_version):
            return False
        
        # C#-specific compatibility checks
        try:
            # Check if binary protocol is available (.NET strength)
            if BIN_PROTOCOL not in self.supported_protocols:
                logger.warning("Binary protocol not available for C# server")
                return False
            
            # C# servers should have good compression support
            capabilities = self.optimization_capabilities
            if not capabilities.get("gzip_compression", False):
                logger.warning("Gzip compression not available for C# server")
            
            # Check for async operation support (.NET strength)
            if not capabilities.get("async_operations", False):
                logger.warning("Async operations not available for C# server")
            
            # Check for thread safety (important for .NET)
            if not capabilities.get("thread_safety", False):
                logger.warning("Thread safety not guaranteed for C# server")
            
            return True
            
        except Exception as e:
            logger.error(ErrorFormatter.format_generic_error("C# Factory", "compatibility check", e))
            return False