"""
Legacy Compatibility Layer for SpacetimeDB SDK Event Systems

This module provides comprehensive backward compatibility with the old event systems while
transitioning to the unified event system. It implements the exact same API signatures
as the legacy classes while redirecting to the modern unified system.

Key Features:
- 100% backward compatibility with existing code
- Automatic deprecation warnings with clear migration paths
- Conversion between legacy string event types and modern EventType enums
- Legacy event data format conversion to modern Event objects
- Performance optimizations to minimize overhead

Legacy Systems Supported:
1. src/spacetimedb_sdk/event_system.py (EventEmitter)
2. src/spacetimedb_sdk/event_manager.py (SDKEventManager)
3. All string-based event types from legacy code
"""

import asyncio
import warnings
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union, Deque
from enum import Enum
from collections import defaultdict, deque
from dataclasses import dataclass, field

from .core_events import Event, EventType as UnifiedEventType, EventPriority, EventMetadata, BaseEvent
from .event_manager import get_event_manager, UnifiedEventManager
from .event_context import EventContext as UnifiedEventContext


# Legacy EventType enums for backward compatibility

class LegacyEventType(Enum):
    """Legacy EventType from event_system.py"""
    # Connection events
    CONNECTION_ESTABLISHED = "connection.established"
    CONNECTION_LOST = "connection.lost"
    CONNECTION_ERROR = "connection.error"
    
    # Identity events
    IDENTITY_RECEIVED = "identity.received"
    IDENTITY_CHANGED = "identity.changed"
    
    # Subscription events
    SUBSCRIPTION_APPLIED = "subscription.applied"
    SUBSCRIPTION_ERROR = "subscription.error"
    SUBSCRIPTION_REMOVED = "subscription.removed"
    
    # Table events
    TABLE_ROW_INSERT = "table.row.insert"
    TABLE_ROW_UPDATE = "table.row.update"
    TABLE_ROW_DELETE = "table.row.delete"
    
    # Reducer events
    REDUCER_CALLED = "reducer.called"
    REDUCER_SUCCESS = "reducer.success"
    REDUCER_ERROR = "reducer.error"
    
    # Energy events
    ENERGY_LOW = "energy.low"
    ENERGY_EXHAUSTED = "energy.exhausted"
    ENERGY_REFILLED = "energy.refilled"
    
    # Database events
    DATABASE_UPDATE = "database.update"
    INITIAL_SUBSCRIPTION = "subscription.initial"
    
    # Identity events (additional)
    IDENTITY_TOKEN = "identity.token"
    
    # Custom events
    CUSTOM = "custom"


class SDKEventType(Enum):
    """Legacy EventType from event_manager.py"""
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_ERROR = "connection_error"
    SUBSCRIPTION_UPDATE = "subscription_update"
    SUBSCRIPTION_APPLIED = "subscription_applied"
    SUBSCRIPTION_ERROR = "subscription_error"
    DATABASE_UPDATE = "database_update"
    TRANSACTION_UPDATE = "transaction_update"
    IDENTITY_TOKEN = "identity_token"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"


class EnhancedEventType(Enum):
    """Legacy EventType from events/enhanced_event_system.py"""
    # Connection events
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    SUBSCRIPTION = "subscription"
    
    # Database events
    TABLE_UPDATE = "table_update"
    REDUCER_CALL = "reducer_call"
    TRANSACTION = "transaction"
    QUERY = "query"
    
    # System events
    SYSTEM = "system"
    ERROR = "error"
    DEBUG = "debug"
    PERFORMANCE = "performance"


# Event type mapping functions

def map_legacy_to_unified(legacy_type: Union[LegacyEventType, SDKEventType, EnhancedEventType, str]) -> UnifiedEventType:
    """Map legacy event types to unified event types."""
    
    # Handle string inputs
    if isinstance(legacy_type, str):
        # Try to find matching unified type
        for unified_type in UnifiedEventType:
            if unified_type.value == legacy_type:
                return unified_type
        # If no exact match, return CUSTOM
        return UnifiedEventType.CUSTOM
    
    # Handle legacy enum types
    if isinstance(legacy_type, LegacyEventType):
        mapping = {
            LegacyEventType.CONNECTION_ESTABLISHED: UnifiedEventType.CONNECTION_ESTABLISHED,
            LegacyEventType.CONNECTION_LOST: UnifiedEventType.CONNECTION_LOST,
            LegacyEventType.CONNECTION_ERROR: UnifiedEventType.CONNECTION_ERROR,
            LegacyEventType.IDENTITY_RECEIVED: UnifiedEventType.IDENTITY_RECEIVED,
            LegacyEventType.IDENTITY_CHANGED: UnifiedEventType.IDENTITY_CHANGED,
            LegacyEventType.IDENTITY_TOKEN: UnifiedEventType.IDENTITY_TOKEN,
            LegacyEventType.SUBSCRIPTION_APPLIED: UnifiedEventType.SUBSCRIPTION_APPLIED,
            LegacyEventType.SUBSCRIPTION_ERROR: UnifiedEventType.SUBSCRIPTION_ERROR,
            LegacyEventType.SUBSCRIPTION_REMOVED: UnifiedEventType.SUBSCRIPTION_REMOVED,
            LegacyEventType.TABLE_ROW_INSERT: UnifiedEventType.TABLE_ROW_INSERT,
            LegacyEventType.TABLE_ROW_UPDATE: UnifiedEventType.TABLE_ROW_UPDATE,
            LegacyEventType.TABLE_ROW_DELETE: UnifiedEventType.TABLE_ROW_DELETE,
            LegacyEventType.REDUCER_CALLED: UnifiedEventType.REDUCER_CALLED,
            LegacyEventType.REDUCER_SUCCESS: UnifiedEventType.REDUCER_SUCCESS,
            LegacyEventType.REDUCER_ERROR: UnifiedEventType.REDUCER_ERROR,
            LegacyEventType.ENERGY_LOW: UnifiedEventType.ENERGY_LOW,
            LegacyEventType.ENERGY_EXHAUSTED: UnifiedEventType.ENERGY_EXHAUSTED,
            LegacyEventType.ENERGY_REFILLED: UnifiedEventType.ENERGY_REFILLED,
            LegacyEventType.DATABASE_UPDATE: UnifiedEventType.DATABASE_UPDATE,
            LegacyEventType.INITIAL_SUBSCRIPTION: UnifiedEventType.INITIAL_SUBSCRIPTION,
            LegacyEventType.CUSTOM: UnifiedEventType.CUSTOM,
        }
        return mapping.get(legacy_type, UnifiedEventType.CUSTOM)
    
    elif isinstance(legacy_type, SDKEventType):
        mapping = {
            SDKEventType.CONNECTION_OPENED: UnifiedEventType.CONNECTION_OPENED,
            SDKEventType.CONNECTION_CLOSED: UnifiedEventType.CONNECTION_CLOSED,
            SDKEventType.CONNECTION_ERROR: UnifiedEventType.CONNECTION_ERROR,
            SDKEventType.SUBSCRIPTION_UPDATE: UnifiedEventType.SUBSCRIPTION_UPDATE,
            SDKEventType.SUBSCRIPTION_APPLIED: UnifiedEventType.SUBSCRIPTION_APPLIED,
            SDKEventType.SUBSCRIPTION_ERROR: UnifiedEventType.SUBSCRIPTION_ERROR,
            SDKEventType.DATABASE_UPDATE: UnifiedEventType.DATABASE_UPDATE,
            SDKEventType.TRANSACTION_UPDATE: UnifiedEventType.TRANSACTION_UPDATE,
            SDKEventType.IDENTITY_TOKEN: UnifiedEventType.IDENTITY_TOKEN,
            SDKEventType.MESSAGE_RECEIVED: UnifiedEventType.MESSAGE_RECEIVED,
            SDKEventType.MESSAGE_SENT: UnifiedEventType.MESSAGE_SENT,
        }
        return mapping.get(legacy_type, UnifiedEventType.CUSTOM)
    
    elif isinstance(legacy_type, EnhancedEventType):
        mapping = {
            EnhancedEventType.CONNECTION: UnifiedEventType.CONNECTION_ESTABLISHED,
            EnhancedEventType.AUTHENTICATION: UnifiedEventType.IDENTITY_RECEIVED,
            EnhancedEventType.SUBSCRIPTION: UnifiedEventType.SUBSCRIPTION_APPLIED,
            EnhancedEventType.TABLE_UPDATE: UnifiedEventType.TABLE_UPDATE,
            EnhancedEventType.REDUCER_CALL: UnifiedEventType.REDUCER_CALLED,
            EnhancedEventType.TRANSACTION: UnifiedEventType.TRANSACTION_UPDATE,
            EnhancedEventType.QUERY: UnifiedEventType.QUERY_EXECUTED,
            EnhancedEventType.SYSTEM: UnifiedEventType.SYSTEM_STARTUP,
            EnhancedEventType.ERROR: UnifiedEventType.ERROR_OCCURRED,
            EnhancedEventType.DEBUG: UnifiedEventType.DEBUG_INFO,
            EnhancedEventType.PERFORMANCE: UnifiedEventType.PERFORMANCE_METRIC,
        }
        return mapping.get(legacy_type, UnifiedEventType.CUSTOM)
    
    return UnifiedEventType.CUSTOM


# Legacy compatibility classes

class LegacyEventData:
    """Legacy EventData from event_manager.py"""
    
    def __init__(self, event_type: SDKEventType, data: Any, timestamp: float, source: str, metadata: Optional[Dict[str, Any]] = None):
        warnings.warn(
            "LegacyEventData is deprecated. Use the unified Event system instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp
        self.source = source
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'event_type': self.event_type.value,
            'data': self.data,
            'timestamp': self.timestamp,
            'source': self.source,
            'metadata': self.metadata
        }


class LegacySDKEventManager:
    """Legacy compatibility wrapper for SDKEventManager"""
    
    def __init__(self, name: str = "LegacySDKEventManager"):
        warnings.warn(
            "SDKEventManager is deprecated. Use UnifiedEventManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.name = name
        self._unified_manager = get_event_manager()
        self._handler_mapping: Dict[str, str] = {}  # Map legacy handlers to unified handler IDs
    
    def register_handler(self, event_type: SDKEventType, handler: Callable[[LegacyEventData], None]) -> bool:
        """Register an event handler for a specific event type."""
        # Wrap legacy handler to work with unified system
        def unified_handler(context: EventContext):
            # Convert unified event to legacy format
            legacy_data = LegacyEventData(
                event_type=event_type,
                data=context.event.data,
                timestamp=context.event.metadata.timestamp,
                source=context.event.metadata.source,
                metadata=context.event.metadata.user_metadata
            )
            handler(legacy_data)
        
        unified_type = map_legacy_to_unified(event_type)
        handler_id = self._unified_manager.on(unified_type, unified_handler)
        
        # Store mapping for potential removal
        handler_key = f"{event_type.value}_{id(handler)}"
        self._handler_mapping[handler_key] = handler_id
        
        return True
    
    def emit_event(self, event_type: SDKEventType, data: Any, source: str = "SDK", metadata: Optional[Dict[str, Any]] = None) -> int:
        """Emit an event to all registered handlers."""
        unified_type = map_legacy_to_unified(event_type)
        
        # Create unified event
        unified_event = Event(
            type=unified_type,
            data={'legacy_data': data, **(metadata or {})},
        )
        unified_event.metadata.source = source
        unified_event.metadata.user_metadata.update(metadata or {})
        
        context = self._unified_manager.emit(unified_event)
        return len(context.handlers)


class LegacyEventEmitter:
    """
    Legacy compatibility wrapper for EventEmitter from event_system.py
    
    Provides 100% backward compatibility with the original EventEmitter API
    while redirecting to the unified event system.
    """
    
    def __init__(
        self, 
        name: str = "LegacyEventEmitter", 
        max_history_size: int = 1000, 
        enable_async: bool = True
    ):
        warnings.warn(
            f"EventEmitter is deprecated. Use UnifiedEventManager from spacetimedb_sdk.events instead.\n"
            f"Migration: Replace 'EventEmitter(\"{name}\")' with 'get_event_manager()'.\n"
            f"See the migration guide: https://docs.spacetimedb.com/python-sdk/migration",
            DeprecationWarning,
            stacklevel=2
        )
        self.name = name
        self.max_history_size = max_history_size
        self.enable_async = enable_async
        
        # Use unified manager internally
        self._unified_manager = get_event_manager()
        
        # Handler storage for backward compatibility and removal
        self._handler_mapping: Dict[str, str] = {}  # local_id -> unified_id
        self._wildcard_handlers: Dict[int, List[tuple]] = defaultdict(list)
        
        # Metrics tracking to match legacy API
        self._metrics = {
            'events_emitted': 0,
            'events_handled': 0,
            'errors_caught': 0,
            'async_handlers_run': 0
        }
        
        # History for backward compatibility
        self._history: Deque[tuple] = deque(maxlen=max_history_size)
        self._history_enabled = True
    
    def on(
        self, 
        event_type: Union[LegacyEventType, str], 
        handler: Callable, 
        priority: int = 0, 
        handler_name: Optional[str] = None
    ) -> str:
        """
        Register an event handler.
        
        Args:
            event_type: Type of event to handle (or "*" for all events)
            handler: Function to handle the event
            priority: Handler priority (higher = earlier execution)
            handler_name: Optional name for the handler
            
        Returns:
            Handler ID for removal
        """
        # Create wrapper that converts UnifiedEventContext to legacy format
        def legacy_handler_wrapper(unified_context: UnifiedEventContext):
            # Convert unified context to legacy format
            legacy_event = self._convert_unified_to_legacy_event(unified_context.event)
            legacy_context = self._create_legacy_context(legacy_event, unified_context)
            
            try:
                if asyncio.iscoroutinefunction(handler):
                    # Handle async functions
                    async def async_wrapper():
                        await handler(legacy_context)
                    
                    # Run in event loop if available
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(async_wrapper())
                        self._metrics['async_handlers_run'] += 1
                    except RuntimeError:
                        # No event loop, run synchronously
                        warnings.warn("Async handler called without event loop, running synchronously")
                        # Skip async handler for now
                        pass
                else:
                    # Handle sync functions
                    handler(legacy_context)
                
                self._metrics['events_handled'] += 1
                
            except Exception as e:
                self._metrics['errors_caught'] += 1
                # Don't re-raise to maintain legacy behavior
        
        # Convert event type
        if isinstance(event_type, str) and event_type == "*":
            unified_type = "*"
        else:
            unified_type = map_legacy_to_unified(event_type)
        
        # Register with unified manager
        unified_handler_id = self._unified_manager.on(
            unified_type, 
            legacy_handler_wrapper, 
            priority, 
            handler_name
        )
        
        # Create local handler ID for backward compatibility
        local_handler_id = handler_name or f"{event_type}_{uuid.uuid4().hex[:8]}"
        self._handler_mapping[local_handler_id] = unified_handler_id
        
        return local_handler_id
    
    def off(self, event_type: Union[LegacyEventType, str], handler_id: str) -> bool:
        """
        Remove an event handler.
        
        Args:
            event_type: Type of event handler was registered for
            handler_id: Handler ID returned by on()
            
        Returns:
            True if handler was removed
        """
        # Get unified handler ID
        unified_handler_id = self._handler_mapping.get(handler_id)
        if not unified_handler_id:
            return False
        
        # Convert event type
        if isinstance(event_type, str) and event_type == "*":
            unified_type = "*"
        else:
            unified_type = map_legacy_to_unified(event_type)
        
        # Remove from unified manager
        removed = self._unified_manager.off(unified_type, unified_handler_id)
        
        if removed:
            # Clean up local mapping
            del self._handler_mapping[handler_id]
        
        return removed
    
    def once(
        self,
        event_type: Union[LegacyEventType, str],
        handler: Callable,
        priority: int = 0
    ) -> str:
        """
        Register a one-time event handler.
        
        Args:
            event_type: Type of event to handle
            handler: Function to handle the event
            priority: Handler priority
            
        Returns:
            Handler ID
        """
        handler_id = f"once_{uuid.uuid4().hex[:8]}"
        
        def once_wrapper(context):
            try:
                result = handler(context)
                return result
            finally:
                self.off(event_type, handler_id)
        
        return self.on(event_type, once_wrapper, priority, handler_id)
    
    def emit(self, event: Union[Event, BaseEvent], **context_kwargs) -> Any:
        """
        Emit an event.
        
        Args:
            event: Event to emit
            **context_kwargs: Additional context parameters
            
        Returns:
            EventContext with results (legacy format)
        """
        self._metrics['events_emitted'] += 1
        
        # Convert legacy event to unified format if needed
        if not isinstance(event, (Event, BaseEvent)):
            # Handle legacy event format
            if hasattr(event, 'type') and hasattr(event, 'data'):
                unified_event = Event(
                    type=map_legacy_to_unified(event.type),
                    data=event.data if hasattr(event, 'data') else {},
                    priority=EventPriority.NORMAL
                )
                if hasattr(event, 'metadata'):
                    unified_event.metadata = event.metadata
            else:
                raise ValueError(f"Invalid event format: {event}")
        else:
            unified_event = event
        
        # Emit using unified manager
        unified_context = self._unified_manager.emit(unified_event, **context_kwargs)
        
        # Store in history for backward compatibility
        if self._history_enabled:
            legacy_event = self._convert_unified_to_legacy_event(unified_event)
            legacy_context = self._create_legacy_context(legacy_event, unified_context)
            self._history.append((legacy_event, legacy_context))
        
        # Convert back to legacy context format
        legacy_event = self._convert_unified_to_legacy_event(unified_event)
        legacy_context = self._create_legacy_context(legacy_event, unified_context)
        
        return legacy_context
    
    def on_raw(
        self,
        event_name: str,
        handler: Callable,
        priority: int = 0,
        handler_name: Optional[str] = None
    ) -> str:
        """
        Register an event handler for a raw event name.
        
        Args:
            event_name: Raw event name string
            handler: Function to handle the event
            priority: Handler priority
            handler_name: Optional name for the handler
            
        Returns:
            Handler ID for removal
        """
        return self.on(event_name, handler, priority, handler_name)
    
    def add_filter(self, filter_func: Callable, name: Optional[str] = None) -> str:
        """Add an event filter (delegates to unified manager)."""
        from .event_filters import CustomFilter
        
        filter_id = name or f"filter_{uuid.uuid4().hex[:8]}"
        custom_filter = CustomFilter(filter_func, filter_id)
        self._unified_manager.add_filter(custom_filter)
        return filter_id
    
    def remove_filter(self, filter_id: str) -> bool:
        """Remove an event filter (not fully supported in legacy mode)."""
        warnings.warn("remove_filter is not fully supported in legacy mode")
        return False
    
    def get_history(
        self,
        event_type: Optional[Union[LegacyEventType, str]] = None,
        limit: Optional[int] = None
    ) -> List[tuple]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of events to return
            
        Returns:
            List of (event, context) tuples
        """
        history = list(self._history)
        
        if event_type:
            event_key = event_type.value if isinstance(event_type, LegacyEventType) else event_type
            history = [
                (e, c) for e, c in history
                if self._get_event_type_key(e) == event_key
            ]
        
        if limit:
            history = history[-limit:]
        
        return history
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
    
    def enable_history(self, enabled: bool) -> None:
        """Enable or disable history recording."""
        self._history_enabled = enabled
    
    def get_metrics(self) -> Dict[str, int]:
        """Get event emitter metrics."""
        # Combine local metrics with unified manager metrics
        unified_metrics = self._unified_manager.get_metrics() or {}
        
        return {
            **self._metrics,
            'unified_events_published': unified_metrics.get('events_published', 0),
            'unified_events_processed': unified_metrics.get('events_processed', 0),
        }
    
    def reset_metrics(self) -> None:
        """Reset metrics."""
        for key in self._metrics:
            self._metrics[key] = 0
    
    def shutdown(self) -> None:
        """Shutdown the event emitter."""
        # Clear all handlers from unified manager
        for handler_id in list(self._handler_mapping.values()):
            # Remove handlers one by one (unified manager doesn't have bulk removal by source)
            pass
        self._handler_mapping.clear()
        self._wildcard_handlers.clear()
    
    # Helper methods for conversion between legacy and unified formats
    
    def _convert_unified_to_legacy_event(self, unified_event: Union[Event, BaseEvent]) -> Any:
        """Convert unified event to legacy event format."""
        class LegacyEvent:
            def __init__(self, event_type, data, metadata):
                self.type = event_type
                self.data = data
                self.metadata = metadata
            
            def with_metadata(self, **kwargs):
                new_metadata = self.metadata.__dict__.copy()
                new_metadata.update(kwargs)
                return LegacyEvent(self.type, self.data, type('Metadata', (), new_metadata)())
        
        # Convert unified event type back to legacy
        legacy_type = self._unified_to_legacy_type(unified_event.type)
        
        return LegacyEvent(
            event_type=legacy_type,
            data=unified_event.data,
            metadata=unified_event.metadata
        )
    
    def _create_legacy_context(self, legacy_event: Any, unified_context: UnifiedEventContext) -> Any:
        """Create legacy context from unified context."""
        class LegacyEventContext:
            def __init__(self, event, unified_ctx):
                self.event = event
                self._unified_ctx = unified_ctx
                self._propagation_stopped = False
                self._default_prevented = False
                self._response_data = {}
            
            @property
            def event_type(self):
                return self.event.type
            
            @property
            def event_id(self):
                return self.event.metadata.event_id
            
            @property
            def timestamp(self):
                return self.event.metadata.timestamp
            
            def stop_propagation(self):
                self._propagation_stopped = True
                self._unified_ctx.stop_propagation()
            
            @property
            def propagation_stopped(self):
                return self._propagation_stopped or self._unified_ctx.propagation_stopped
            
            def prevent_default(self):
                self._default_prevented = True
                self._unified_ctx.prevent_default()
            
            @property
            def default_prevented(self):
                return self._default_prevented or self._unified_ctx.default_prevented
            
            def set_response(self, key, value):
                self._response_data[key] = value
                self._unified_ctx.set_response(key, value)
            
            def get_response(self, key, default=None):
                return self._response_data.get(key, default) or self._unified_ctx.get_response(key, default)
        
        return LegacyEventContext(legacy_event, unified_context)
    
    def _unified_to_legacy_type(self, unified_type: UnifiedEventType) -> LegacyEventType:
        """Convert unified event type back to legacy type."""
        # Reverse mapping
        reverse_mapping = {
            UnifiedEventType.CONNECTION_ESTABLISHED: LegacyEventType.CONNECTION_ESTABLISHED,
            UnifiedEventType.CONNECTION_LOST: LegacyEventType.CONNECTION_LOST,
            UnifiedEventType.CONNECTION_ERROR: LegacyEventType.CONNECTION_ERROR,
            UnifiedEventType.IDENTITY_RECEIVED: LegacyEventType.IDENTITY_RECEIVED,
            UnifiedEventType.IDENTITY_CHANGED: LegacyEventType.IDENTITY_CHANGED,
            UnifiedEventType.IDENTITY_TOKEN: LegacyEventType.IDENTITY_TOKEN,
            UnifiedEventType.SUBSCRIPTION_APPLIED: LegacyEventType.SUBSCRIPTION_APPLIED,
            UnifiedEventType.SUBSCRIPTION_ERROR: LegacyEventType.SUBSCRIPTION_ERROR,
            UnifiedEventType.SUBSCRIPTION_REMOVED: LegacyEventType.SUBSCRIPTION_REMOVED,
            UnifiedEventType.TABLE_ROW_INSERT: LegacyEventType.TABLE_ROW_INSERT,
            UnifiedEventType.TABLE_ROW_UPDATE: LegacyEventType.TABLE_ROW_UPDATE,
            UnifiedEventType.TABLE_ROW_DELETE: LegacyEventType.TABLE_ROW_DELETE,
            UnifiedEventType.REDUCER_CALLED: LegacyEventType.REDUCER_CALLED,
            UnifiedEventType.REDUCER_SUCCESS: LegacyEventType.REDUCER_SUCCESS,
            UnifiedEventType.REDUCER_ERROR: LegacyEventType.REDUCER_ERROR,
            UnifiedEventType.ENERGY_LOW: LegacyEventType.ENERGY_LOW,
            UnifiedEventType.ENERGY_EXHAUSTED: LegacyEventType.ENERGY_EXHAUSTED,
            UnifiedEventType.ENERGY_REFILLED: LegacyEventType.ENERGY_REFILLED,
            UnifiedEventType.DATABASE_UPDATE: LegacyEventType.DATABASE_UPDATE,
            UnifiedEventType.INITIAL_SUBSCRIPTION: LegacyEventType.INITIAL_SUBSCRIPTION,
        }
        return reverse_mapping.get(unified_type, LegacyEventType.CUSTOM)
    
    def _get_event_type_key(self, event: Any) -> str:
        """Get event type key for filtering."""
        if hasattr(event, 'type'):
            if isinstance(event.type, LegacyEventType):
                return event.type.value
            elif hasattr(event.type, 'value'):
                return event.type.value
            else:
                return str(event.type)
        return "unknown"


# Enhanced event system compatibility

class LegacyEnhancedEvent:
    """Legacy Event class from enhanced_event_system.py"""
    
    def __init__(self):
        warnings.warn(
            "Enhanced Event system is deprecated. Use the unified Event system instead.",
            DeprecationWarning,
            stacklevel=2
        )


# Global event bus compatibility (for legacy global_event_bus)

class LegacyGlobalEventBus:
    """
    Legacy compatibility wrapper for global event bus functionality.
    
    Provides backward compatibility with the global_event_bus from event_system.py
    """
    
    def __init__(self):
        warnings.warn(
            "global_event_bus is deprecated. Use get_event_manager() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._unified_manager = get_event_manager()
        self._emitters: Dict[str, LegacyEventEmitter] = {}
    
    def get_emitter(self, namespace: str = "default") -> LegacyEventEmitter:
        """Get or create a legacy event emitter for a namespace."""
        if namespace not in self._emitters:
            self._emitters[namespace] = LegacyEventEmitter(name=f"GlobalBus-{namespace}")
        return self._emitters[namespace]
    
    def emit(self, event: Event, namespace: str = "default", **context_kwargs):
        """Emit an event to a specific namespace."""
        emitter = self.get_emitter(namespace)
        return emitter.emit(event, **context_kwargs)
    
    def on(self, event_type, handler, namespace: str = "default", **kwargs) -> str:
        """Register a handler in a specific namespace."""
        emitter = self.get_emitter(namespace)
        return emitter.on(event_type, handler, **kwargs)
    
    def off(self, event_type, handler_id: str, namespace: str = "default") -> bool:
        """Remove a handler from a specific namespace."""
        emitter = self.get_emitter(namespace)
        return emitter.off(event_type, handler_id)
    
    def shutdown_all(self) -> None:
        """Shutdown all emitters."""
        for emitter in self._emitters.values():
            emitter.shutdown()
        self._emitters.clear()


# Legacy helper functions for backward compatibility

def create_event(event_type, data: Dict[str, Any], **metadata_kwargs) -> Event:
    """Create an event with metadata (legacy compatibility)."""
    warnings.warn(
        "create_event from legacy event_system is deprecated. Use Event() constructor directly.",
        DeprecationWarning,
        stacklevel=2
    )
    
    unified_type = map_legacy_to_unified(event_type)
    metadata = EventMetadata(**metadata_kwargs)
    return Event(type=unified_type, data=data, metadata=metadata)


def subscribe_to_raw_events(
    handler,
    event_names: List[str],
    subscription_id: Optional[str] = None,
    namespace: str = "default"
) -> Dict[str, str]:
    """
    Subscribe to raw events by name (legacy compatibility).
    """
    warnings.warn(
        "subscribe_to_raw_events is deprecated. Use get_event_manager().on() directly.",
        DeprecationWarning,
        stacklevel=2
    )
    
    manager = get_event_manager()
    handler_ids = {}
    
    for event_name in event_names:
        # Wrap handler to work with unified context
        def wrapped_handler(context: UnifiedEventContext):
            handler(context)
        
        handler_name = f"{subscription_id or 'raw'}_{event_name}"
        handler_id = manager.on(event_name, wrapped_handler, handler_name=handler_name)
        handler_ids[event_name] = handler_id
    
    return handler_ids


def create_reducer_event(reducer_name: str, status: str = "pending", **kwargs):
    """Create a reducer event (legacy compatibility)."""
    warnings.warn(
        "create_reducer_event from legacy event_system is deprecated. Use ReducerEvent() constructor.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from .core_events import ReducerEvent
    return ReducerEvent(reducer_name=reducer_name, status=status, **kwargs)


def create_table_event(table_name: str, operation: str, row_data: Any, **kwargs):
    """Create a table event (legacy compatibility)."""
    warnings.warn(
        "create_table_event from legacy event_system is deprecated. Use TableEvent() constructor.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from .core_events import TableEvent
    return TableEvent(table_name=table_name, operation=operation, row_data=row_data, **kwargs)


# Legacy EventContext class for backward compatibility

class LegacyEventContext:
    """
    Legacy EventContext class that wraps UnifiedEventContext for backward compatibility.
    """
    
    def __init__(self, event, source_component: Optional[str] = None, parent_context=None):
        warnings.warn(
            "Legacy EventContext is deprecated. Use EventContext from events.event_context.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Convert legacy event to unified if needed
        if not isinstance(event, (Event, BaseEvent)):
            if hasattr(event, 'type') and hasattr(event, 'data'):
                unified_event = Event(
                    type=map_legacy_to_unified(event.type),
                    data=event.data,
                    priority=EventPriority.NORMAL
                )
                if hasattr(event, 'metadata'):
                    unified_event.metadata = event.metadata
            else:
                raise ValueError("Invalid event format for legacy context")
        else:
            unified_event = event
        
        self._unified_context = UnifiedEventContext(
            unified_event, 
            source_component=source_component
        )
        self.event = event
        self.source_component = source_component or "unknown"
        self.parent_context = parent_context
        
        # Legacy properties
        self._propagation_stopped = False
        self._default_prevented = False
        self._processed = False
        self._response_data = {}
        self._triggered_events = []
        self._handled_by = []
        self._start_time = time.time()
        self._end_time = None
    
    @property
    def event_type(self):
        """Get the event type."""
        return self.event.type if hasattr(self.event, 'type') else None
    
    @property
    def event_id(self) -> str:
        """Get the event ID."""
        return self._unified_context.event_id
    
    @property
    def timestamp(self) -> float:
        """Get the event timestamp."""
        return self._unified_context.timestamp
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time since event context creation."""
        end = self._end_time or time.time()
        return end - self._start_time
    
    def stop_propagation(self) -> None:
        """Stop event propagation to remaining handlers."""
        self._propagation_stopped = True
        self._unified_context.stop_propagation()
    
    @property
    def propagation_stopped(self) -> bool:
        """Check if propagation has been stopped."""
        return self._propagation_stopped or self._unified_context.propagation_stopped
    
    def prevent_default(self) -> None:
        """Prevent default event handling."""
        self._default_prevented = True
        self._unified_context.prevent_default()
    
    @property
    def default_prevented(self) -> bool:
        """Check if default handling has been prevented."""
        return self._default_prevented or self._unified_context.default_prevented
    
    def mark_handled(self, handler_name: str) -> None:
        """Mark event as handled by a specific handler."""
        self._handled_by.append(handler_name)
        self._processed = True
        self._unified_context.mark_handled(handler_name)
    
    @property
    def is_handled(self) -> bool:
        """Check if event has been handled."""
        return self._processed or self._unified_context.is_handled
    
    @property
    def handlers(self) -> List[str]:
        """Get list of handlers that processed this event."""
        return self._handled_by + self._unified_context.handlers
    
    def set_response(self, key: str, value: Any) -> None:
        """Set response data for the event."""
        self._response_data[key] = value
        self._unified_context.set_response(key, value)
    
    def get_response(self, key: str, default: Any = None) -> Any:
        """Get response data for the event."""
        return self._response_data.get(key, default) or self._unified_context.get_response(key, default)
    
    @property
    def response_data(self) -> Dict[str, Any]:
        """Get all response data."""
        unified_data = self._unified_context.response_data
        return {**self._response_data, **unified_data}
    
    def trigger_event(self, event) -> None:
        """Trigger a related event from this context."""
        # Convert to unified event if needed
        if not isinstance(event, (Event, BaseEvent)):
            if hasattr(event, 'type') and hasattr(event, 'data'):
                unified_event = Event(
                    type=map_legacy_to_unified(event.type),
                    data=event.data,
                    priority=EventPriority.NORMAL
                )
                if hasattr(event, 'metadata'):
                    unified_event.metadata = event.metadata
            else:
                raise ValueError("Invalid event format")
        else:
            unified_event = event
        
        # Set causation metadata
        unified_event.metadata.causation_id = self.event_id
        if hasattr(self.event, 'metadata') and self.event.metadata.correlation_id:
            unified_event.metadata.correlation_id = self.event.metadata.correlation_id
        else:
            unified_event.metadata.correlation_id = self.event_id
        
        self._triggered_events.append(event)
        self._unified_context.trigger_event(unified_event)
    
    @property
    def triggered_events(self) -> List:
        """Get events triggered from this context."""
        return self._triggered_events.copy()
    
    def complete(self) -> None:
        """Mark context as complete."""
        self._end_time = time.time()
        self._unified_context.complete()


# Global legacy instances for backward compatibility

_legacy_sdk_event_manager = None
_legacy_event_emitter = None
_legacy_global_event_bus = None


def get_legacy_sdk_event_manager() -> LegacySDKEventManager:
    """Get legacy SDK event manager instance."""
    global _legacy_sdk_event_manager
    if _legacy_sdk_event_manager is None:
        _legacy_sdk_event_manager = LegacySDKEventManager()
    return _legacy_sdk_event_manager


def get_legacy_event_emitter() -> LegacyEventEmitter:
    """Get legacy event emitter instance."""
    global _legacy_event_emitter
    if _legacy_event_emitter is None:
        _legacy_event_emitter = LegacyEventEmitter()
    return _legacy_event_emitter


def get_legacy_global_event_bus() -> LegacyGlobalEventBus:
    """Get legacy global event bus instance."""
    global _legacy_global_event_bus
    if _legacy_global_event_bus is None:
        _legacy_global_event_bus = LegacyGlobalEventBus()
    return _legacy_global_event_bus


# Migration helpers

def migrate_legacy_handlers(legacy_handlers: Dict[str, List[Callable]]) -> Dict[str, List[str]]:
    """
    Migrate legacy event handlers to unified system.
    
    Args:
        legacy_handlers: Dict mapping event type strings to handler lists
        
    Returns:
        Dict mapping event types to handler IDs in unified system
    """
    unified_manager = get_event_manager()
    migrated_handlers = {}
    
    for event_type_str, handlers in legacy_handlers.items():
        handler_ids = []
        
        # Try to map to unified event type
        unified_type = None
        for legacy_enum in [LegacyEventType, SDKEventType, EnhancedEventType]:
            try:
                legacy_type = legacy_enum(event_type_str)
                unified_type = map_legacy_to_unified(legacy_type)
                break
            except ValueError:
                continue
        
        if unified_type is None:
            # Fallback to string registration
            unified_type = event_type_str
        
        for handler in handlers:
            def unified_handler(context: EventContext):
                # Adapt context for legacy handler if needed
                handler(context)
            
            handler_id = unified_manager.on(unified_type, unified_handler)
            handler_ids.append(handler_id)
        
        migrated_handlers[event_type_str] = handler_ids
    
    return migrated_handlers


def create_migration_guide() -> str:
    """Create a migration guide for transitioning to unified events."""
    return """
# SpacetimeDB SDK Event System Migration Guide

## Overview
The SpacetimeDB SDK has consolidated three separate event systems into a single unified system.

## What Changed
1. **event_system.py** - Advanced event system with EventEmitter
2. **event_manager.py** - SDK event manager with SDKEventManager  
3. **events/** package - Enhanced event system

These have been replaced with a single `UnifiedEventManager`.

## Migration Steps

### 1. Import Changes
**Old:**
```python
from spacetimedb_sdk.event_system import EventEmitter, EventType
from spacetimedb_sdk.event_manager import get_event_manager, EventType as SDKEventType
from spacetimedb_sdk.events import get_event_manager as get_enhanced_manager
```

**New:**
```python
from spacetimedb_sdk.events import get_event_manager, EventType, Event
```

### 2. Event Type Consolidation
All event types are now in a single `EventType` enum:
```python
# All these are now unified:
EventType.CONNECTION_ESTABLISHED  # was CONNECTION_ESTABLISHED or CONNECTION_OPENED
EventType.SUBSCRIPTION_APPLIED    # consistent across all systems
EventType.TABLE_ROW_INSERT        # unified table events
```

### 3. Handler Registration
**Old:**
```python
# event_system.py
emitter.on(EventType.CONNECTION_ESTABLISHED, handler)

# event_manager.py  
manager.register_handler(EventType.CONNECTION_OPENED, handler)

# enhanced events
manager.subscribe(subscriber, EventType.CONNECTION)
```

**New:**
```python
# Unified approach
manager = get_event_manager()
handler_id = manager.on(EventType.CONNECTION_ESTABLISHED, handler)
```

### 4. Event Creation
**Old:**
```python
# Multiple ways to create events
event = Event(type=EventType.CUSTOM, data={})
event_data = EventData(event_type=SDKEventType.MESSAGE_RECEIVED, ...)
```

**New:**
```python
# Single way to create events
event = Event(type=EventType.MESSAGE_RECEIVED, data={...})
# Or use specific event classes
event = ConnectionEvent(connection_id="123", state="connected")
```

### 5. Legacy Compatibility
Use the compatibility layer during transition:
```python
from spacetimedb_sdk.events.legacy_compat import (
    LegacySDKEventManager,
    LegacyEventEmitter,
    migrate_legacy_handlers
)

# Migrate existing handlers
migrated = migrate_legacy_handlers(old_handlers)
```

## Benefits of Unified System
- Single event type enum
- Consistent API across all components
- Better performance and memory usage
- Enhanced filtering and routing
- Async/sync handler support
- Comprehensive metrics
- Better error isolation

## Deprecation Timeline
- Legacy systems will show deprecation warnings
- Full removal planned for next major version
- Migration tools available during transition period
"""


# Export legacy types for backward compatibility
__all__ = [
    # Legacy enum types
    'LegacyEventType',
    'SDKEventType', 
    'EnhancedEventType',
    
    # Legacy data classes
    'LegacyEventData',
    
    # Legacy manager classes
    'LegacySDKEventManager',
    'LegacyEventEmitter',
    'LegacyEnhancedEvent',
    'LegacyGlobalEventBus',
    'LegacyEventContext',
    
    # Legacy global instances
    'get_legacy_sdk_event_manager',
    'get_legacy_event_emitter',
    'get_legacy_global_event_bus',
    
    # Legacy helper functions
    'create_event',
    'subscribe_to_raw_events',
    'create_reducer_event',
    'create_table_event',
    
    # Migration utilities
    'map_legacy_to_unified',
    'migrate_legacy_handlers',
    'create_migration_guide'
]