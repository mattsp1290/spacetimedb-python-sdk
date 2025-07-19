"""
Event Handlers Module for SpacetimeDB SDK Enhanced Event System

Defines event handlers, subscribers, and filtering utilities for the event system.
This module extracts the handler functionality from enhanced_event_system.py
for better separation of concerns.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Set, Union, TypeVar, Generic

from .event_types import Event, EventT, EventType, EventPriority


logger = logging.getLogger(__name__)


class EventFilter(Generic[EventT]):
    """
    Generic event filter for selecting specific events.
    
    Can filter by event type, priority, age, source, or custom predicates.
    """
    
    def __init__(self,
                 event_types: Optional[Union[EventType, List[EventType]]] = None,
                 min_priority: Optional[EventPriority] = None,
                 max_age_seconds: Optional[float] = None,
                 sources: Optional[Union[str, List[str]]] = None,
                 custom_filter: Optional[Callable[[EventT], bool]] = None):
        """
        Initialize event filter.
        
        Args:
            event_types: Event type(s) to match
            min_priority: Minimum priority level to match
            max_age_seconds: Maximum age of events to match
            sources: Source(s) to match
            custom_filter: Custom filter function taking an Event and returning bool
        """
        self.event_types = self._normalize_to_set(event_types)
        self.min_priority = min_priority
        self.max_age_seconds = max_age_seconds
        self.sources = self._normalize_to_set(sources)
        self.custom_filter = custom_filter
    
    def _normalize_to_set(self, value):
        """Convert single value or list to set."""
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return set(value)
        return {value}
    
    def matches(self, event: EventT) -> bool:
        """Check if event matches the filter criteria."""
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # Check priority
        if self.min_priority and event.priority < self.min_priority:
            return False
        
        # Check age
        if self.max_age_seconds and event.is_expired(self.max_age_seconds):
            return False
        
        # Check source
        if self.sources and event.source not in self.sources:
            return False
        
        # Check custom filter
        if self.custom_filter and not self.custom_filter(event):
            return False
        
        return True
    
    def __call__(self, event: EventT) -> bool:
        """Allow filter to be used as a callable."""
        return self.matches(event)


class EventHandler(ABC):
    """Abstract base class for event handlers."""
    
    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an event."""
        pass
    
    def get_name(self) -> str:
        """Get handler name for logging."""
        return self.__class__.__name__


class AsyncEventHandler(EventHandler):
    """Base class for async event handlers."""
    
    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an event asynchronously."""
        pass


class SyncEventHandler(EventHandler):
    """Base class for sync event handlers."""
    
    @abstractmethod
    def handle_event_sync(self, event: Event) -> None:
        """Handle an event synchronously."""
        pass
    
    async def handle_event(self, event: Event) -> None:
        """Wrapper to handle event asynchronously by delegating to sync method."""
        self.handle_event_sync(event)


class EventSubscriber(ABC):
    """Abstract base class for event subscribers."""
    
    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an event."""
        pass


class CallbackEventSubscriber(EventSubscriber):
    """Event subscriber that wraps a callback function."""
    
    def __init__(self, callback: Callable[[Event], Any], name: Optional[str] = None):
        """
        Initialize callback subscriber.
        
        Args:
            callback: Function to call with events
            name: Optional name for the subscriber
        """
        self.callback = callback
        self.name = name or f"callback_{id(callback)}"
    
    async def handle_event(self, event: Event) -> None:
        """Handle event by calling the callback."""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(event)
            else:
                self.callback(event)
        except Exception as e:
            logger.error(f"Error in callback subscriber {self.name}: {e}")
    
    def __str__(self) -> str:
        return f"CallbackSubscriber({self.name})"


class FilteredEventSubscriber(EventSubscriber):
    """Event subscriber with built-in filtering."""
    
    def __init__(self, 
                 subscriber: EventSubscriber, 
                 event_filter: EventFilter,
                 name: Optional[str] = None):
        """
        Initialize filtered subscriber.
        
        Args:
            subscriber: Underlying subscriber
            event_filter: Filter to apply
            name: Optional name for the subscriber
        """
        self.subscriber = subscriber
        self.event_filter = event_filter
        self.name = name or f"filtered_{subscriber}"
    
    async def handle_event(self, event: Event) -> None:
        """Handle event if it matches the filter."""
        if self.event_filter.matches(event):
            await self.subscriber.handle_event(event)
    
    def __str__(self) -> str:
        return f"FilteredSubscriber({self.name})"


# Convenience functions for creating handlers
def create_callback_handler(
    callback: Callable[[Event], Any], 
    name: Optional[str] = None
) -> CallbackEventSubscriber:
    """Create a callback-based event handler."""
    return CallbackEventSubscriber(callback, name)


def create_filtered_handler(
    handler: EventSubscriber,
    event_filter: EventFilter,
    name: Optional[str] = None
) -> FilteredEventSubscriber:
    """Create a filtered event handler."""
    return FilteredEventSubscriber(handler, event_filter, name)


def create_type_filter(event_types: Union[EventType, List[EventType]]) -> EventFilter:
    """Create a filter that matches specific event types."""
    return EventFilter(event_types=event_types)


def create_priority_filter(min_priority: EventPriority) -> EventFilter:
    """Create a filter that matches events above a certain priority."""
    return EventFilter(min_priority=min_priority)


def create_source_filter(sources: Union[str, List[str]]) -> EventFilter:
    """Create a filter that matches events from specific sources."""
    return EventFilter(sources=sources)


def create_age_filter(max_age_seconds: float) -> EventFilter:
    """Create a filter that matches events younger than max_age_seconds."""
    return EventFilter(max_age_seconds=max_age_seconds)