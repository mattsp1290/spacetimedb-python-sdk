"""
Legacy Event System Compatibility Layer

This file provides backward compatibility with the original advanced event system
while redirecting to the unified events system. All original functionality is preserved
with deprecation warnings to guide users to the modern system.

DEPRECATED: This module is deprecated in favor of the unified events system.
Use: from spacetimedb_sdk.events import get_event_manager, EventType, Event

Migration Guide:
- EventEmitter -> UnifiedEventManager (get_event_manager())
- EventType -> Use EventType from events.core_events
- EventContext -> Use EventContext from events.event_context
- Global event bus -> Use get_event_manager() directly
"""

import warnings

# Import legacy compatibility wrappers that provide the exact same API
from .events.legacy_compat import (
    # Legacy enums and types
    LegacyEventType as EventType,
    LegacyEventEmitter as EventEmitter,
    LegacyEventContext as EventContext,
    LegacyGlobalEventBus,
    
    # Legacy helper functions
    create_event,
    create_reducer_event,
    create_table_event,
    subscribe_to_raw_events,
    
    # Legacy event data structures
    Event,
    EventMetadata,
    
    # Global instances
    get_legacy_global_event_bus
)

# Re-export specific event classes from modern system with compatibility wrappers
from .events.core_events import (
    ReducerEvent as CoreReducerEvent,
    TableEvent as CoreTableEvent,
    EventPriority
)

# Create legacy-compatible versions with deprecation warnings
class ReducerEvent(CoreReducerEvent):
    """Legacy ReducerEvent with backward compatibility."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ReducerEvent from event_system is deprecated. Use ReducerEvent from events.core_events.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)


class TableEvent(CoreTableEvent):
    """Legacy TableEvent with backward compatibility."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "TableEvent from event_system is deprecated. Use TableEvent from events.core_events.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)


# Global event bus instance for backward compatibility
global_event_bus = get_legacy_global_event_bus()

# Deprecation warning for module import
warnings.warn(
    "event_system module is deprecated. Use 'from spacetimedb_sdk.events import get_event_manager, EventType, Event' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Export all legacy components for backward compatibility
__all__ = [
    # Core types
    'EventType',
    'Event',
    'EventMetadata',
    'EventContext',
    'EventEmitter',
    'EventPriority',
    
    # Specific event types
    'ReducerEvent',
    'TableEvent',
    
    # Helper functions
    'create_event',
    'create_reducer_event',
    'create_table_event',
    'subscribe_to_raw_events',
    
    # Global instances
    'global_event_bus',
]