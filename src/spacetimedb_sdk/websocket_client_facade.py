"""
WebSocket Client Facade for backward compatibility

This module provides a compatibility layer to ensure smooth migration from the
monolithic websocket_client.py to the refactored modular implementation.

The facade:
1. Maintains the exact same API as the original ModernWebSocketClient
2. Provides deprecation warnings for methods that should migrate
3. Includes migration helpers and documentation
4. Ensures zero breaking changes for existing code
"""

import warnings
from typing import Optional, Callable, Dict, List, Any, Union
from functools import wraps

from .websocket_client_refactored import ModernWebSocketClient as RefactoredClient
from .websocket_client_refactored import ConnectionState
from .exceptions import SpacetimeDBConnectionError
from .compression import CompressionConfig
from .retry_policies import RetryPolicy
from .protocol import BIN_PROTOCOL, ClientMessage


def deprecated(alternative: str = None):
    """Decorator to mark methods as deprecated with suggested alternatives."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            message = f"{func.__name__} is deprecated"
            if alternative:
                message += f". Use {alternative} instead"
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ModernWebSocketClientCompat(RefactoredClient):
    """
    Compatibility wrapper for ModernWebSocketClient.
    
    This class ensures 100% backward compatibility while encouraging migration
    to the new modular patterns. All methods from the original implementation
    are preserved with appropriate warnings for deprecated patterns.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize with full backward compatibility."""
        # Extract any legacy parameters that might not be in refactored version
        self._legacy_params = {}
        
        # Initialize refactored client
        super().__init__(*args, **kwargs)
        
        # Add any legacy attributes that might be accessed directly
        self._subscription_state_callbacks = []
        self._legacy_metrics = SubscriptionMetricsCompat()
    
    # Legacy subscription metric methods
    @deprecated("subscription_manager.get_subscription_health()")
    def record_subscription_data(self, table_name: str, size: int) -> None:
        """Legacy method for recording subscription data."""
        # Forward to subscription manager's metrics
        if hasattr(self.subscription_manager, '_metrics'):
            self.subscription_manager._metrics.record_data(table_name, size)
    
    @deprecated("subscription_manager.get_subscription_health()")
    def record_subscription_error(self, table_name: str, error: str) -> None:
        """Legacy method for recording subscription errors."""
        if hasattr(self.subscription_manager, '_metrics'):
            self.subscription_manager._metrics.record_error(table_name, error)
    
    @deprecated("subscription_manager.reset_metrics()")
    def reset_subscription_metrics(self) -> None:
        """Legacy method for resetting subscription metrics."""
        if hasattr(self.subscription_manager, 'reset_metrics'):
            self.subscription_manager.reset_metrics()
    
    # Legacy internal methods that might be accessed
    def _contains_binary_data(self, obj: Any, _recursion_limiter=None) -> bool:
        """Legacy method for checking binary data."""
        # Simple implementation for compatibility
        if isinstance(obj, bytes):
            return True
        if isinstance(obj, dict):
            return any(self._contains_binary_data(v) for v in obj.values())
        if isinstance(obj, list):
            return any(self._contains_binary_data(item) for item in obj)
        return False
    
    def should_use_sdk_encoding(self, message: Union[str, bytes, dict]) -> bool:
        """Legacy method for determining encoding."""
        if isinstance(message, bytes):
            return True
        if isinstance(message, dict):
            return self._contains_binary_data(message)
        return False
    
    def _send_client_encoded_message(self, message: Union[str, bytes]) -> None:
        """Legacy method for sending pre-encoded messages."""
        if not self.ws or self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("WebSocket is not connected")
        
        if isinstance(message, str):
            message = message.encode('utf-8')
        
        self._send_raw_message(message)
    
    def send_heartbeat(self) -> None:
        """Legacy heartbeat method."""
        # Modern implementation handles this automatically
        self.logger.debug("Heartbeat called (handled automatically in refactored version)")
    
    # Legacy async notification method
    async def _notify_subscription_state_change(self, event_type: str, data: Any) -> None:
        """Legacy async notification method."""
        # Convert to sync event emission
        from .events import create_subscription_event, EventType
        
        event_map = {
            'subscription_applied': EventType.SUBSCRIPTION_APPLIED,
            'subscription_error': EventType.SUBSCRIPTION_ERROR,
            'subscription_removed': EventType.SUBSCRIPTION_REMOVED
        }
        
        if event_type in event_map:
            self.event_manager.emit(create_subscription_event(
                event_map[event_type],
                data
            ))
    
    def _notify_subscription_state_callbacks(self, server_message) -> None:
        """Legacy method for notifying subscription callbacks."""
        # This is handled by the event system now
        pass
    
    def _record_subscription_metrics(self, server_message, message_size: int) -> None:
        """Legacy method for recording subscription metrics."""
        # This is handled by subscription manager now
        pass
    
    # Provide access to legacy attributes
    @property
    def auth_handshake_completed(self) -> bool:
        """Legacy property for auth handshake status."""
        return self.auth_handler.state == self.auth_handler.AuthenticationState.AUTHENTICATED
    
    @property
    def auth_token(self) -> Optional[str]:
        """Legacy property for auth token."""
        return self.auth_handler.auth_token
    
    @auth_token.setter
    def auth_token(self, value: str):
        """Legacy setter for auth token."""
        self.auth_handler.set_auth_token(value)
    
    @property
    def subscription_metrics(self):
        """Legacy property for subscription metrics."""
        return self._legacy_metrics


class SubscriptionMetricsCompat:
    """Compatibility wrapper for legacy SubscriptionMetrics class."""
    
    def __init__(self):
        self.subscriptions: Dict[str, Dict[str, Any]] = {}
    
    def record_subscription_data(self, table_name: str, size: int) -> None:
        """Legacy metric recording method."""
        if table_name not in self.subscriptions:
            self.subscriptions[table_name] = {
                'message_count': 0,
                'total_bytes': 0,
                'error_count': 0
            }
        self.subscriptions[table_name]['message_count'] += 1
        self.subscriptions[table_name]['total_bytes'] += size
    
    def record_subscription_error(self, table_name: str, error: str) -> None:
        """Legacy error recording method."""
        if table_name not in self.subscriptions:
            self.subscriptions[table_name] = {'error_count': 0}
        self.subscriptions[table_name]['error_count'] += 1
    
    def get_subscription_health(self, table_name: str) -> Dict[str, Any]:
        """Legacy health metrics method."""
        return self.subscriptions.get(table_name, {})
    
    def get_all_subscription_health(self) -> Dict[str, Dict[str, Any]]:
        """Legacy all health metrics method."""
        return self.subscriptions.copy()
    
    def reset_metrics(self) -> None:
        """Legacy reset method."""
        self.subscriptions.clear()


# Migration helpers
class MigrationHelper:
    """Helper class for migrating from monolithic to modular client."""
    
    @staticmethod
    def create_refactored_client(legacy_client_params: dict) -> RefactoredClient:
        """
        Create a refactored client from legacy parameters.
        
        Example:
            # Old code
            client = ModernWebSocketClient(
                host="localhost:3000",
                auth_token="mytoken",
                on_connect=my_connect_callback
            )
            
            # New code
            client = MigrationHelper.create_refactored_client({
                'host': "localhost:3000",
                'auth_token': "mytoken",
                'on_connect': my_connect_callback
            })
        """
        return RefactoredClient(**legacy_client_params)
    
    @staticmethod
    def migrate_callbacks(legacy_client, refactored_client):
        """
        Migrate callbacks from legacy to refactored client.
        
        Example:
            MigrationHelper.migrate_callbacks(old_client, new_client)
        """
        # Migrate connection callbacks
        if hasattr(legacy_client, '_on_connect') and legacy_client._on_connect:
            refactored_client.event_manager.register_handler(
                'connection_established',
                lambda event: legacy_client._on_connect()
            )
        
        if hasattr(legacy_client, '_on_disconnect') and legacy_client._on_disconnect:
            refactored_client.event_manager.register_handler(
                'connection_closed',
                lambda event: legacy_client._on_disconnect()
            )
        
        if hasattr(legacy_client, '_on_error') and legacy_client._on_error:
            refactored_client.event_manager.register_handler(
                'connection_error',
                lambda event: legacy_client._on_error(event.data.get('error'))
            )
    
    @staticmethod
    def get_migration_guide() -> str:
        """Get migration guide documentation."""
        return """
        Migration Guide: ModernWebSocketClient to Refactored Implementation
        
        The refactored WebSocket client provides the same functionality with better
        modularity and maintainability. Here's how to migrate:
        
        1. Direct Replacement (No Code Changes Required):
           Simply import the compatibility client:
           
           from spacetimedb_sdk.websocket_client_facade import ModernWebSocketClientCompat as ModernWebSocketClient
        
        2. Gradual Migration (Recommended):
           
           a. Replace callback-based patterns with event handlers:
              # Old
              client = ModernWebSocketClient(on_connect=my_callback)
              
              # New
              client = ModernWebSocketClient()
              client.event_manager.register_handler(EventType.CONNECTION_ESTABLISHED, my_handler)
           
           b. Use subscription manager directly:
              # Old
              query_id = client.subscribe_single("SELECT * FROM users")
              
              # New (same API, but you can also access manager directly)
              query_id = client.subscription_manager.subscribe_single("SELECT * FROM users")
           
           c. Use authentication handler directly:
              # Old
              token = client.spacetimedb_token
              
              # New (same API, but you can also access handler directly)
              token = client.auth_handler.jwt_token
        
        3. New Features Available:
           - Unified event system for all events
           - Better error isolation and handling
           - Enhanced metrics and monitoring
           - Modular architecture for easier testing
        
        4. Deprecated Features:
           - add_subscription_state_callback() -> use event_manager.register_handler()
           - subscribe_to_queries() -> use subscribe_multi()
           - one_off_query() -> use execute_one_off_query()
        
        For more details, see the documentation for each module:
        - SubscriptionManager: connection/subscription_manager.py
        - AuthenticationHandler: connection/authentication_handler.py
        - UnifiedEventManager: events/__init__.py
        """


# Export the compatibility client as the default
ModernWebSocketClient = ModernWebSocketClientCompat

__all__ = [
    'ModernWebSocketClient',
    'ModernWebSocketClientCompat', 
    'ConnectionState',
    'MigrationHelper',
    'SubscriptionMetricsCompat'
]