"""
EventSystem compatibility layer for backward compatibility.

This module provides the old EventSystem API that wraps the new UnifiedEventManager
for backward compatibility with existing tests and code.
"""

import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set
from .event_manager import UnifiedEventManager, get_event_manager
from .core_events import Event, EventType, EventPriority
from .spacetimedb_events import SystemEvent


class LegacyEvent:
    """Legacy event for backward compatibility with the old EventSystem API."""
    
    def __init__(self, event_name: str, event_data: Any):
        """Initialize legacy event."""
        self.event_name = event_name
        self.event_data = event_data
        self.event_type = EventType.CUSTOM
        self.priority = EventPriority.NORMAL
        self.data = {"event_name": event_name, "event_data": event_data}
    
    def validate(self) -> None:
        """Validate the event."""
        if not self.event_name:
            raise ValueError("Event name is required")


class LegacyEventHandler:
    """Wrapper for legacy event handlers."""
    
    def __init__(self, event_name: str, handler: Callable[[Any], None]):
        """Initialize legacy event handler."""
        self.event_name = event_name
        self.handler = handler
        self.is_wildcard = event_name.endswith("*")
        if self.is_wildcard:
            self.prefix = event_name[:-1]  # Remove the *
    
    def _matches_event(self, event_name: str) -> bool:
        """Check if event name matches this handler's pattern."""
        if self.is_wildcard:
            return event_name.startswith(self.prefix)
        else:
            return event_name == self.event_name
    
    def __call__(self, event_context) -> None:
        """Handle the event if it matches the expected event name."""
        # Get the actual event from the context
        event = event_context.event if hasattr(event_context, 'event') else event_context
        
        if isinstance(event, LegacyEvent) and self._matches_event(event.event_name):
            self.handler(event.event_data)
        elif hasattr(event, 'data') and isinstance(event.data, dict):
            # Handle case where event data contains event_name
            event_name = event.data.get("event_name")
            if event_name and self._matches_event(event_name):
                self.handler(event.data.get("event_data"))


class EventSystem:
    """
    Legacy EventSystem compatibility wrapper.
    
    This class provides the old EventSystem API that wraps the new UnifiedEventManager
    for backward compatibility with existing tests and code.
    """
    
    def __init__(self, manager: Optional[UnifiedEventManager] = None):
        """
        Initialize the EventSystem.
        
        Args:
            manager: Optional UnifiedEventManager instance. If None, uses global manager.
        """
        self._manager = manager or get_event_manager()
        self._handler_registry: Dict[str, Dict[Callable, str]] = {}  # event_name -> {handler_func: handler_id}
        self._legacy_handlers: Dict[str, Dict[Callable, LegacyEventHandler]] = {}  # event_name -> {handler_func: wrapper}
        
    def subscribe(self, event_name: str, handler: Callable[[Any], None]) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: Name of the event to subscribe to
            handler: Function to call when event is emitted
        """
        if event_name not in self._handler_registry:
            self._handler_registry[event_name] = {}
        if event_name not in self._legacy_handlers:
            self._legacy_handlers[event_name] = {}
        
        # Create a legacy handler wrapper
        legacy_handler = LegacyEventHandler(event_name, handler)
        
        # Register the wrapper with the unified manager for CUSTOM events
        handler_id = self._manager.subscribe(EventType.CUSTOM, legacy_handler)
        
        # Store the mappings
        self._handler_registry[event_name][handler] = handler_id
        self._legacy_handlers[event_name][handler] = legacy_handler
    
    def unsubscribe(self, event_name: str, handler: Callable[[Any], None]) -> bool:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: Name of the event to unsubscribe from
            handler: The handler function to remove
            
        Returns:
            True if handler was removed, False if not found
        """
        if event_name not in self._handler_registry:
            return False
        
        handler_dict = self._handler_registry[event_name]
        if handler not in handler_dict:
            return False
        
        # Get the handler ID and remove it from the unified manager
        handler_id = handler_dict[handler]
        success = self._manager.off(EventType.CUSTOM, handler_id)
        
        # Remove from our registries
        if success:
            del handler_dict[handler]
            if not handler_dict:
                del self._handler_registry[event_name]
            
            # Also remove from legacy handlers
            if event_name in self._legacy_handlers and handler in self._legacy_handlers[event_name]:
                del self._legacy_handlers[event_name][handler]
                if not self._legacy_handlers[event_name]:
                    del self._legacy_handlers[event_name]
        
        return success
    
    def emit(self, event_name: str, data: Any) -> None:
        """
        Emit an event.
        
        Args:
            event_name: Name of the event to emit
            data: Data to send with the event
        """
        # Create a legacy event 
        event = LegacyEvent(event_name=event_name, event_data=data)
        
        # Emit the event
        self._manager.emit(event)
    
    def clear_handlers(self, event_name: Optional[str] = None) -> None:
        """
        Clear all handlers for an event or all events.
        
        Args:
            event_name: Name of event to clear handlers for. If None, clears all handlers.
        """
        if event_name is None:
            # Clear all handlers
            for event_name, handler_dict in self._handler_registry.items():
                for handler, handler_id in handler_dict.items():
                    self._manager.off(EventType.CUSTOM, handler_id)
            self._handler_registry.clear()
            self._legacy_handlers.clear()
        else:
            # Clear handlers for specific event
            if event_name in self._handler_registry:
                handler_dict = self._handler_registry[event_name]
                for handler, handler_id in handler_dict.items():
                    self._manager.off(EventType.CUSTOM, handler_id)
                del self._handler_registry[event_name]
            
            # Clear legacy handlers
            if event_name in self._legacy_handlers:
                del self._legacy_handlers[event_name]
    
    def get_handler_count(self, event_name: str) -> int:
        """
        Get the number of handlers for an event.
        
        Args:
            event_name: Name of the event
            
        Returns:
            Number of handlers registered for the event
        """
        if event_name not in self._handler_registry:
            return 0
        return len(self._handler_registry[event_name])
    
    def get_registered_events(self) -> Set[str]:
        """
        Get all registered event names.
        
        Returns:
            Set of event names that have handlers
        """
        return set(self._handler_registry.keys())


# For backward compatibility, create a default instance
_default_event_system = None


def get_event_system() -> EventSystem:
    """Get the default EventSystem instance."""
    global _default_event_system
    if _default_event_system is None:
        _default_event_system = EventSystem()
    return _default_event_system


# Legacy alias for backward compatibility
EventManager = EventSystem