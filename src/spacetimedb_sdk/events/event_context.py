"""
Event Context for SpacetimeDB SDK Unified Event System

This module provides event context management with operations and metadata.
"""

import time
from typing import Any, Dict, List, Optional
from .core_events import Event


class EventContext:
    """
    Rich context for event handling with operations and metadata.
    
    Provides access to:
    - Event metadata and history
    - Propagation control
    - Response building
    - Related events
    """
    
    def __init__(
        self,
        event: Event,
        source_component: Optional[str] = None,
        parent_context: Optional['EventContext'] = None
    ):
        self.event = event
        self.source_component = source_component or "unknown"
        self.parent_context = parent_context
        
        # Control flags
        self._propagation_stopped = False
        self._default_prevented = False
        self._processed = False
        
        # Response data
        self._response_data: Dict[str, Any] = {}
        
        # Related events triggered by this context
        self._triggered_events: List[Event] = []
        
        # Handler tracking
        self._handled_by: List[str] = []
        
        # Timing
        self._start_time = time.time()
        self._end_time: Optional[float] = None
    
    @property
    def event_type(self):
        """Get the event type."""
        return self.event.type
    
    @property
    def event_id(self) -> str:
        """Get the event ID."""
        return self.event.metadata.event_id
    
    @property
    def timestamp(self) -> float:
        """Get the event timestamp."""
        return self.event.metadata.timestamp
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time since event context creation."""
        end = self._end_time or time.time()
        return end - self._start_time
    
    def stop_propagation(self) -> None:
        """Stop event propagation to remaining handlers."""
        self._propagation_stopped = True
    
    @property
    def propagation_stopped(self) -> bool:
        """Check if propagation has been stopped."""
        return self._propagation_stopped
    
    def prevent_default(self) -> None:
        """Prevent default event handling."""
        self._default_prevented = True
    
    @property
    def default_prevented(self) -> bool:
        """Check if default handling has been prevented."""
        return self._default_prevented
    
    def mark_handled(self, handler_name: str) -> None:
        """Mark event as handled by a specific handler."""
        self._handled_by.append(handler_name)
        self._processed = True
    
    @property
    def is_handled(self) -> bool:
        """Check if event has been handled."""
        return self._processed
    
    @property
    def handlers(self) -> List[str]:
        """Get list of handlers that processed this event."""
        return self._handled_by.copy()
    
    def set_response(self, key: str, value: Any) -> None:
        """Set response data for the event."""
        self._response_data[key] = value
    
    def get_response(self, key: str, default: Any = None) -> Any:
        """Get response data for the event."""
        return self._response_data.get(key, default)
    
    @property
    def response_data(self) -> Dict[str, Any]:
        """Get all response data."""
        return self._response_data.copy()
    
    def trigger_event(self, event: Event) -> None:
        """Trigger a related event from this context."""
        # Set causation metadata
        event.metadata.causation_id = self.event_id
        if self.event.metadata.correlation_id:
            event.metadata.correlation_id = self.event.metadata.correlation_id
        else:
            event.metadata.correlation_id = self.event_id
        
        self._triggered_events.append(event)
    
    @property
    def triggered_events(self) -> List[Event]:
        """Get events triggered from this context."""
        return self._triggered_events.copy()
    
    def complete(self) -> None:
        """Mark context as complete."""
        self._end_time = time.time()
    
    def get_context_data(self, key: str, default: Any = None) -> Any:
        """Get data from the event context."""
        return self.event.get_context(key, default)
    
    def set_context_data(self, key: str, value: Any) -> None:
        """Set data in the event context."""
        self.event.add_context(key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary representation."""
        return {
            'event': self.event.to_dict(),
            'source_component': self.source_component,
            'propagation_stopped': self._propagation_stopped,
            'default_prevented': self._default_prevented,
            'is_handled': self._processed,
            'handlers': self._handled_by.copy(),
            'response_data': self._response_data.copy(),
            'triggered_events_count': len(self._triggered_events),
            'elapsed_time': self.elapsed_time,
            'start_time': self._start_time,
            'end_time': self._end_time
        }