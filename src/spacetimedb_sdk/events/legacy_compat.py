"""
Legacy Compatibility Layer for SpacetimeDB SDK Event Systems

This module provides backward compatibility with the old event systems while
transitioning to the unified event system.
"""

import warnings
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum

from .core_events import Event, EventType as UnifiedEventType, EventPriority
from .event_manager import get_event_manager, EventContext
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
    """Legacy compatibility wrapper for EventEmitter from event_system.py"""
    
    def __init__(self, name: str = "LegacyEventEmitter", max_history_size: int = 1000, enable_async: bool = True):
        warnings.warn(
            "EventEmitter is deprecated. Use UnifiedEventManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.name = name
        self._unified_manager = get_event_manager()
        self._handler_mapping: Dict[str, str] = {}
    
    def on(self, event_type: Union[LegacyEventType, str], handler: Callable, priority: int = 0, handler_name: Optional[str] = None) -> str:
        """Register an event handler."""
        # Convert legacy handler to unified format
        def unified_handler(context: EventContext):
            handler(context)
        
        if isinstance(event_type, str) and event_type == "*":
            unified_type = "*"
        else:
            unified_type = map_legacy_to_unified(event_type)
        
        handler_id = self._unified_manager.on(unified_type, unified_handler, priority, handler_name)
        return handler_id
    
    def emit(self, event: Event, **context_kwargs) -> EventContext:
        """Emit an event."""
        return self._unified_manager.emit(event, **context_kwargs)


# Enhanced event system compatibility

class LegacyEnhancedEvent:
    """Legacy Event class from enhanced_event_system.py"""
    
    def __init__(self):
        warnings.warn(
            "Enhanced Event system is deprecated. Use the unified Event system instead.",
            DeprecationWarning,
            stacklevel=2
        )


# Global legacy instances for backward compatibility

_legacy_sdk_event_manager = None
_legacy_event_emitter = None


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
    'LegacyEventType',
    'SDKEventType', 
    'EnhancedEventType',
    'LegacyEventData',
    'LegacySDKEventManager',
    'LegacyEventEmitter',
    'LegacyEnhancedEvent',
    'get_legacy_sdk_event_manager',
    'get_legacy_event_emitter',
    'map_legacy_to_unified',
    'migrate_legacy_handlers',
    'create_migration_guide'
]