"""
Python server optimized factory for SpacetimeDB clients.

This factory creates clients optimized for Python SpacetimeDB servers,
accounting for Python-specific performance characteristics and limitations.
"""

from typing import Dict, Any, Optional
import logging

from .base import (
    SpacetimeDBClientFactoryBase,
    ServerLanguage,
    OptimizationProfile
)
from ..protocol import TEXT_PROTOCOL, BIN_PROTOCOL
from ..compression import CompressionType
from ..retry_policies import RetryPolicy

logger = logging.getLogger(__name__)


class PythonOptimizedFactory(SpacetimeDBClientFactoryBase):
    """
    Factory for creating SpacetimeDB clients optimized for Python servers.
    
    Python servers typically have:
    - Good text protocol performance
    - Moderate binary protocol performance
    - Reasonable compression support
    - Need for higher energy budgets due to overhead
    - Benefit from more conservative connection settings
    """
    
    @property
    def server_language(self) -> ServerLanguage:
        """Get the server language this factory supports."""
        return ServerLanguage.PYTHON
    
    @property
    def supported_protocols(self) -> list[str]:
        """Get list of protocols supported by Python servers."""
        return [TEXT_PROTOCOL, BIN_PROTOCOL]
    
    @property
    def optimization_capabilities(self) -> Dict[str, bool]:
        """Get optimization capabilities for Python servers."""
        return {
            "binary_protocol": True,
            "text_protocol": True,  # Python often excels at text processing
            "gzip_compression": True,
            "brotli_compression": True,  # Available but may be slower
            "high_energy_budget": True,  # Python needs higher budgets
            "connection_pooling": True,
            "batch_processing": True,  # Python is good at batch operations
            "async_operations": True,  # Python's asyncio strength
            "moderate_latency": True,
            "good_reliability": True,
        }
    
    def get_recommended_config(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    ) -> Dict[str, Any]:
        """
        Get recommended configuration for Python servers.
        
        Python servers work best with:
        - Text protocol for many use cases (better Python performance)
        - Moderate compression (gzip typically better than brotli)
        - Higher energy budgets to account for Python overhead
        - More conservative timing to accommodate GIL constraints
        """
        if optimization_profile == OptimizationProfile.PERFORMANCE:
            return self._get_python_performance_config()
        elif optimization_profile == OptimizationProfile.RELIABILITY:
            return self._get_python_reliability_config()
        elif optimization_profile == OptimizationProfile.MINIMAL:
            return self._get_python_minimal_config()
        else:  # BALANCED
            return self._get_python_balanced_config()
    
    def _get_python_performance_config(self) -> Dict[str, Any]:
        """Get performance-optimized configuration for Python servers."""
        return {
            "protocol": BIN_PROTOCOL,  # Use binary for performance
            "compression": CompressionType.GZIP,  # Better than brotli for Python
            "energy_budget": 400000,  # Higher budget for Python overhead
            "retry_policy": RetryPolicy(
                max_attempts=4,
                initial_delay=0.2,  # Slightly slower than Rust
                max_delay=2.0,
                exponential_base=1.8
            ),
            "connection_timeout": 20.0,  # More time for Python servers
            "keep_alive": True,
            "heartbeat_interval": 25.0,
            "buffer_size": 64 * 1024,  # 64KB - good balance for Python
            "batch_size": 500,  # Python handles batches well
            "concurrent_requests": 3,  # Conservative due to GIL
            "enable_connection_pooling": True,
            "pool_size": 2,  # Smaller pool due to Python threading
            "request_timeout": 30.0,
        }
    
    def _get_python_reliability_config(self) -> Dict[str, Any]:
        """Get reliability-optimized configuration for Python servers."""
        return {
            "protocol": TEXT_PROTOCOL,  # Python excels at text processing
            "compression": CompressionType.GZIP,  # Reliable compression
            "energy_budget": 300000,  # Conservative but adequate
            "retry_policy": RetryPolicy(
                max_attempts=10,
                initial_delay=1.0,
                max_delay=30.0,
                exponential_base=2.0
            ),
            "connection_timeout": 30.0,
            "keep_alive": True,
            "heartbeat_interval": 10.0,  # Frequent health checks
            "buffer_size": 32 * 1024,  # Smaller buffer for reliability
            "batch_size": 100,  # Smaller batches for error isolation
            "concurrent_requests": 1,  # Single-threaded for reliability
            "enable_connection_pooling": False,  # Simpler connection model
            "request_timeout": 60.0,  # Generous timeout
            "health_check_interval": 15.0,
        }
    
    def _get_python_balanced_config(self) -> Dict[str, Any]:
        """Get balanced configuration for Python servers."""
        return {
            "protocol": TEXT_PROTOCOL,  # Good balance for Python
            "compression": CompressionType.GZIP,  # Optimal for Python
            "energy_budget": 350000,  # Higher than Rust but reasonable
            "retry_policy": RetryPolicy(
                max_attempts=6,
                initial_delay=0.5,
                max_delay=15.0,
                exponential_base=2.0
            ),
            "connection_timeout": 25.0,
            "keep_alive": True,
            "heartbeat_interval": 20.0,
            "buffer_size": 48 * 1024,  # 48KB buffer
            "batch_size": 300,  # Good batch size for Python
            "concurrent_requests": 2,  # Limited concurrency
            "enable_connection_pooling": True,
            "pool_size": 2,
            "request_timeout": 45.0,
        }
    
    def _get_python_minimal_config(self) -> Dict[str, Any]:
        """Get minimal configuration for Python servers."""
        return {
            "protocol": TEXT_PROTOCOL,  # Simplest for Python
            "compression": CompressionType.NONE,  # No compression overhead
            "energy_budget": 150000,  # Conservative budget
            "retry_policy": RetryPolicy(
                max_attempts=3,
                initial_delay=2.0,
                max_delay=10.0,
                exponential_base=2.0
            ),
            "connection_timeout": 20.0,
            "keep_alive": False,  # Simpler connection management
            "buffer_size": 16 * 1024,  # Small buffer
            "batch_size": 50,  # Small batches
            "concurrent_requests": 1,  # No concurrency
            "enable_connection_pooling": False,
            "request_timeout": 30.0,
        }
    
    def validate_compatibility(
        self,
        server_version: Optional[str] = None
    ) -> bool:
        """
        Validate compatibility with Python server.
        
        Python servers are generally compatible but may have
        different performance characteristics.
        """
        if not super().validate_compatibility(server_version):
            return False
        
        # Python-specific compatibility checks
        try:
            # Check if text protocol is available (should always be)
            if TEXT_PROTOCOL not in self.supported_protocols:
                logger.error("Text protocol not available for Python server")
                return False
            
            # Python servers should support basic compression
            capabilities = self.optimization_capabilities
            if not capabilities.get("gzip_compression", False):
                logger.warning("Gzip compression not available for Python server")
            
            # Check for async operation support
            if not capabilities.get("async_operations", False):
                logger.warning("Async operations may not be optimal for Python server")
            
            return True
            
        except Exception as e:
            logger.error(f"Python server compatibility check failed: {e}")
            return False