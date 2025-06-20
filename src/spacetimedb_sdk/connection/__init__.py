"""
Enhanced Connection Management for SpacetimeDB SDK

Production-ready connection management extracted from blackholio-python-client
with advanced features including connection pooling, health monitoring,
circuit breaker pattern, and comprehensive metrics.

Key Features:
- Advanced connection pooling with configurable min/max connections
- Background health monitoring with automatic recovery
- Circuit breaker pattern for failure protection
- Idle connection cleanup and lifecycle management
- Comprehensive metrics and event-driven monitoring
- Multi-server language support with optimized configurations
- Graceful shutdown and resource cleanup
"""

from .enhanced_connection_manager import (
    # Enums
    PoolState,
    HealthStatus,
    
    # Data classes
    ConnectionMetrics,
    PoolConfiguration,
    PooledConnection,
    ServerConfig,
    
    # Main classes
    ConnectionPool,
    EnhancedConnectionManager,
    
    # Convenience functions
    get_connection_manager,
    get_connection
)

__all__ = [
    # Enums
    'PoolState',
    'HealthStatus',
    
    # Data classes
    'ConnectionMetrics',
    'PoolConfiguration', 
    'PooledConnection',
    'ServerConfig',
    
    # Main classes
    'ConnectionPool',
    'EnhancedConnectionManager',
    
    # Convenience functions
    'get_connection_manager',
    'get_connection'
]