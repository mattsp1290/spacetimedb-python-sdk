"""
Legacy Event Manager Compatibility Layer

This file provides backward compatibility with the original SDKEventManager
while redirecting to the unified events system. All original functionality is preserved
with deprecation warnings to guide users to the modern system.

DEPRECATED: This module is deprecated in favor of the unified events system.
Use: from spacetimedb_sdk.events import get_event_manager

Migration Guide:
- SDKEventManager -> UnifiedEventManager (get_event_manager())
- EventType -> Use EventType from events.core_events
- EventData -> Use Event from events.core_events
- get_event_manager() -> Use get_event_manager() from events.event_manager
"""

import warnings

# Import legacy compatibility wrappers that provide the exact same API
from .events.legacy_compat import (
    # Legacy manager class
    LegacySDKEventManager as SDKEventManager,
    
    # Legacy enum and data types
    SDKEventType as EventType,
    LegacyEventData as EventData,
    
    # Legacy global instance getters
    get_legacy_sdk_event_manager
)

# Import from core events for modern compatibility
from .events.core_events import Event

# Global manager instances for backward compatibility
_global_event_manager = None

def get_event_manager() -> SDKEventManager:
    """
    Get the global legacy SDK event manager instance.
    
    DEPRECATED: Use get_event_manager() from spacetimedb_sdk.events instead.
    """
    warnings.warn(
        "get_event_manager() from event_manager is deprecated. "
        "Use 'from spacetimedb_sdk.events import get_event_manager' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return get_legacy_sdk_event_manager()


def set_event_manager(manager: SDKEventManager) -> None:
    """
    Set the global legacy SDK event manager instance.
    
    DEPRECATED: Use set_event_manager() from spacetimedb_sdk.events instead.
    """
    warnings.warn(
        "set_event_manager() from event_manager is deprecated. "
        "Use 'from spacetimedb_sdk.events import set_event_manager' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    global _global_event_manager
    _global_event_manager = manager


# Deprecation warning for module import
warnings.warn(
    "event_manager module is deprecated. Use 'from spacetimedb_sdk.events import get_event_manager' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Export all legacy components for backward compatibility
__all__ = [
    # Legacy manager class
    'SDKEventManager',
    
    # Legacy data types
    'EventType',
    'EventData',
    
    # Legacy global functions
    'get_event_manager',
    'set_event_manager',
]