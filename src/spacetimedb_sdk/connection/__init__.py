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

from .authentication_handler import (
    # Enums
    AuthenticationState,
    
    # Data classes
    AuthenticationCredentials,
    AuthenticationEvent,
    
    # Main class
    AuthenticationHandler
)

from .websocket_auth_integration import (
    # Data classes
    WebSocketAuthConfig,
    
    # Main class
    WebSocketAuthIntegration,
    
    # Convenience functions
    create_websocket_auth_integration
)

from .websocket_client_integration import (
    # Mixin class
    WebSocketClientAuthMixin,
    
    # Integration functions
    integrate_auth_handler_with_websocket_client,
    create_auth_enabled_websocket_client,
    migrate_legacy_auth_to_handler,
    
    # Convenience functions
    get_auth_headers_for_connection,
    handle_websocket_auth_error,
    store_websocket_auth_credentials
)

from .connection_manager import (
    # Enums
    ConnectionState,
    
    # Data classes
    ConnectionConfig,
    ConnectionMetrics as CoreConnectionMetrics,
    
    # Protocols
    WebSocketFactory,
    EventManager,
    ConnectionDiagnostics,
    
    # Main class
    ConnectionManager,
    
    # Default implementations
    DefaultWebSocketFactory,
    NullEventManager
)

# from .websocket_integration import (
#     # Data classes
#     WebSocketSubscriptionConfig,
#     
#     # Main classes
#     WebSocketSubscriptionIntegration,
#     LegacySubscriptionInterface,
#     
#     # Convenience functions
#     create_websocket_subscription_integration
# )

__all__ = [
    # Enums
    'PoolState',
    'HealthStatus',
    'AuthenticationState',
    'ConnectionState',
    
    # Data classes
    'ConnectionMetrics',
    'PoolConfiguration', 
    'PooledConnection',
    'ServerConfig',
    'AuthenticationCredentials',
    'AuthenticationEvent',
    'WebSocketAuthConfig',
    'ConnectionConfig',
    'CoreConnectionMetrics',
    
    # Protocols
    'WebSocketFactory',
    'EventManager',
    'ConnectionDiagnostics',
    
    # Main classes
    'ConnectionPool',
    'EnhancedConnectionManager',
    'AuthenticationHandler',
    'WebSocketAuthIntegration',
    'WebSocketClientAuthMixin',
    'ConnectionManager',
    'DefaultWebSocketFactory',
    'NullEventManager',
    
    # Convenience functions
    'get_connection_manager',
    'get_connection',
    'create_websocket_auth_integration',
    'integrate_auth_handler_with_websocket_client',
    'create_auth_enabled_websocket_client',
    'migrate_legacy_auth_to_handler',
    'get_auth_headers_for_connection',
    'handle_websocket_auth_error',
    'store_websocket_auth_credentials'
]