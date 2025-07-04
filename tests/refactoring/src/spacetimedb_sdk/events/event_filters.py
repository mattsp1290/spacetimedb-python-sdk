"""
Event Filtering and Routing System

This module provides advanced filtering capabilities for the unified event system,
enabling conditional event processing and intelligent routing.
"""

import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Union, Set, Pattern
from dataclasses import dataclass
from enum import Enum

from .core_events import EventType, EventContext


class FilterResult(Enum):
    """Result of filter evaluation."""
    ALLOW = "allow"
    BLOCK = "block"
    TRANSFORM = "transform"


class EventFilter(ABC):
    """
    Base class for event filters.
    
    Filters are used to determine whether an event should be processed
    by a particular handler or routing destination.
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.enabled = True
        self.invocation_count = 0
        self.last_invocation = 0.0
        self.processing_time = 0.0
    
    @abstractmethod
    def should_process(self, context: EventContext) -> bool:
        """
        Determine if the event should be processed.
        
        Args:
            context: Event context to evaluate
            
        Returns:
            True if event should be processed, False otherwise
        """
        pass
    
    def evaluate(self, context: EventContext) -> FilterResult:
        """
        Evaluate the filter and return detailed result.
        
        Args:
            context: Event context to evaluate
            
        Returns:
            FilterResult indicating the evaluation outcome
        """
        start_time = time.time()
        
        try:
            self.invocation_count += 1
            self.last_invocation = start_time
            
            if not self.enabled:
                return FilterResult.BLOCK
            
            result = self.should_process(context)
            return FilterResult.ALLOW if result else FilterResult.BLOCK
        
        finally:
            self.processing_time += time.time() - start_time
    
    def enable(self):
        """Enable the filter."""
        self.enabled = True
    
    def disable(self):
        """Disable the filter."""
        self.enabled = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filter statistics."""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'invocation_count': self.invocation_count,
            'last_invocation': self.last_invocation,
            'total_processing_time': self.processing_time,
            'average_processing_time': (
                self.processing_time / self.invocation_count
                if self.invocation_count > 0 else 0.0
            )
        }


class TypeFilter(EventFilter):
    """Filter events by event type."""
    
    def __init__(self, allowed_types: Union[EventType, List[EventType]], name: Optional[str] = None):
        super().__init__(name)
        if isinstance(allowed_types, EventType):
            self.allowed_types = {allowed_types}
        else:
            self.allowed_types = set(allowed_types)
    
    def should_process(self, context: EventContext) -> bool:
        """Check if event type is allowed."""
        return context.event_type in self.allowed_types
    
    def add_type(self, event_type: EventType):
        """Add an allowed event type."""
        self.allowed_types.add(event_type)
    
    def remove_type(self, event_type: EventType):
        """Remove an allowed event type."""
        self.allowed_types.discard(event_type)


class SourceFilter(EventFilter):
    """Filter events by source."""
    
    def __init__(self, allowed_sources: Union[str, List[str]], name: Optional[str] = None):
        super().__init__(name)
        if isinstance(allowed_sources, str):
            self.allowed_sources = {allowed_sources}
        else:
            self.allowed_sources = set(allowed_sources)
    
    def should_process(self, context: EventContext) -> bool:
        """Check if event source is allowed."""
        return context.source in self.allowed_sources
    
    def add_source(self, source: str):
        """Add an allowed source."""
        self.allowed_sources.add(source)
    
    def remove_source(self, source: str):
        """Remove an allowed source."""
        self.allowed_sources.discard(source)


class MetadataFilter(EventFilter):
    """Filter events by metadata conditions."""
    
    def __init__(self, metadata_conditions: Dict[str, Any], name: Optional[str] = None):
        super().__init__(name)
        self.metadata_conditions = metadata_conditions
    
    def should_process(self, context: EventContext) -> bool:
        """Check if metadata conditions are met."""
        for key, expected_value in self.metadata_conditions.items():
            actual_value = context.get_metadata(key)
            
            if callable(expected_value):
                # If expected value is a function, use it as predicate
                if not expected_value(actual_value):
                    return False
            else:
                # Direct value comparison
                if actual_value != expected_value:
                    return False
        
        return True
    
    def add_condition(self, key: str, value: Any):
        """Add a metadata condition."""
        self.metadata_conditions[key] = value
    
    def remove_condition(self, key: str):
        """Remove a metadata condition."""
        self.metadata_conditions.pop(key, None)


class TimeFilter(EventFilter):
    """Filter events by time conditions."""
    
    def __init__(
        self,
        min_time: Optional[float] = None,
        max_time: Optional[float] = None,
        time_window: Optional[float] = None,
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.min_time = min_time
        self.max_time = max_time
        self.time_window = time_window
        self.window_start = time.time() if time_window else None
    
    def should_process(self, context: EventContext) -> bool:
        """Check if event time meets conditions."""
        event_time = context.timestamp
        
        # Check absolute time bounds
        if self.min_time is not None and event_time < self.min_time:
            return False
        
        if self.max_time is not None and event_time > self.max_time:
            return False
        
        # Check time window
        if self.time_window is not None and self.window_start is not None:
            current_time = time.time()
            if current_time - self.window_start > self.time_window:
                # Reset window
                self.window_start = current_time
                return False
        
        return True
    
    def reset_window(self):
        """Reset the time window."""
        if self.time_window is not None:
            self.window_start = time.time()


class RegexFilter(EventFilter):
    """Filter events using regular expressions."""
    
    def __init__(
        self,
        pattern: Union[str, Pattern],
        field: str = "source",
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.field = field
    
    def should_process(self, context: EventContext) -> bool:
        """Check if field matches regex pattern."""
        if self.field == "source":
            value = context.source
        elif self.field == "event_type":
            value = context.event_type.value
        elif self.field == "correlation_id":
            value = context.correlation_id or ""
        else:
            # Check metadata
            value = str(context.get_metadata(self.field, ""))
        
        return self.pattern.search(value) is not None


class PredicateFilter(EventFilter):
    """Filter events using a custom predicate function."""
    
    def __init__(self, predicate: Callable[[EventContext], bool], name: Optional[str] = None):
        super().__init__(name)
        self.predicate = predicate
    
    def should_process(self, context: EventContext) -> bool:
        """Evaluate predicate function."""
        return self.predicate(context)


class RateLimitFilter(EventFilter):
    """Filter events based on rate limiting."""
    
    def __init__(
        self,
        max_events: int,
        time_window: float,
        key_extractor: Optional[Callable[[EventContext], str]] = None,
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.max_events = max_events
        self.time_window = time_window
        self.key_extractor = key_extractor or (lambda ctx: ctx.source)
        self.event_counts: Dict[str, List[float]] = {}
    
    def should_process(self, context: EventContext) -> bool:
        """Check if event is within rate limit."""
        key = self.key_extractor(context)
        current_time = time.time()
        
        # Get or create event list for this key
        if key not in self.event_counts:
            self.event_counts[key] = []
        
        event_times = self.event_counts[key]
        
        # Remove old events outside time window
        cutoff_time = current_time - self.time_window
        self.event_counts[key] = [t for t in event_times if t > cutoff_time]
        
        # Check if we're within rate limit
        if len(self.event_counts[key]) >= self.max_events:
            return False
        
        # Add current event
        self.event_counts[key].append(current_time)
        return True
    
    def reset_counts(self):
        """Reset all rate limit counts."""
        self.event_counts.clear()


class CompositeFilter(EventFilter):
    """Combine multiple filters with logical operations."""
    
    def __init__(
        self,
        filters: List[EventFilter],
        operation: str = "AND",
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.filters = filters
        self.operation = operation.upper()
        
        if self.operation not in ["AND", "OR", "NOT"]:
            raise ValueError(f"Invalid operation: {operation}")
    
    def should_process(self, context: EventContext) -> bool:
        """Evaluate composite filter."""
        if not self.filters:
            return True
        
        if self.operation == "AND":
            return all(f.should_process(context) for f in self.filters)
        elif self.operation == "OR":
            return any(f.should_process(context) for f in self.filters)
        elif self.operation == "NOT":
            # NOT operation only considers the first filter
            return not self.filters[0].should_process(context)
        
        return True
    
    def add_filter(self, filter_obj: EventFilter):
        """Add a filter to the composite."""
        self.filters.append(filter_obj)
    
    def remove_filter(self, filter_obj: EventFilter):
        """Remove a filter from the composite."""
        if filter_obj in self.filters:
            self.filters.remove(filter_obj)


class FilterChain(EventFilter):
    """Chain multiple filters in sequence."""
    
    def __init__(self, filters: List[EventFilter], name: Optional[str] = None):
        super().__init__(name)
        self.filters = filters
        self.short_circuit = True  # Stop on first failure
    
    def should_process(self, context: EventContext) -> bool:
        """Evaluate all filters in chain."""
        for filter_obj in self.filters:
            if not filter_obj.should_process(context):
                if self.short_circuit:
                    return False
                # Continue evaluation if not short-circuiting
        
        return True
    
    def add_filter(self, filter_obj: EventFilter):
        """Add a filter to the chain."""
        self.filters.append(filter_obj)
    
    def insert_filter(self, index: int, filter_obj: EventFilter):
        """Insert a filter at a specific position."""
        self.filters.insert(index, filter_obj)
    
    def remove_filter(self, filter_obj: EventFilter):
        """Remove a filter from the chain."""
        if filter_obj in self.filters:
            self.filters.remove(filter_obj)
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed statistics for all filters in chain."""
        stats = self.get_stats()
        stats['filter_stats'] = [f.get_stats() for f in self.filters]
        return stats


class EventRouter:
    """
    Route events to different handlers based on filtering rules.
    
    This class enables complex event routing scenarios where different
    handlers should receive events based on sophisticated filtering rules.
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or "event_router"
        self.routes: List[Dict[str, Any]] = []
        self.default_handler = None
        self.stats = {
            'events_routed': 0,
            'routes_matched': 0,
            'default_handler_used': 0
        }
    
    def add_route(
        self,
        handler: Callable,
        filter_obj: EventFilter,
        priority: int = 0,
        name: Optional[str] = None
    ):
        """
        Add a routing rule.
        
        Args:
            handler: Handler function to call
            filter_obj: Filter to determine if route applies
            priority: Route priority (lower = higher priority)
            name: Optional route name
        """
        route = {
            'handler': handler,
            'filter': filter_obj,
            'priority': priority,
            'name': name or f"route_{len(self.routes)}",
            'match_count': 0
        }
        
        # Insert maintaining priority order
        inserted = False
        for i, existing_route in enumerate(self.routes):
            if priority < existing_route['priority']:
                self.routes.insert(i, route)
                inserted = True
                break
        
        if not inserted:
            self.routes.append(route)
    
    def set_default_handler(self, handler: Callable):
        """Set default handler for unmatched events."""
        self.default_handler = handler
    
    def route_event(self, context: EventContext) -> List[Callable]:
        """
        Route an event to appropriate handlers.
        
        Args:
            context: Event context to route
            
        Returns:
            List of handlers that should process the event
        """
        self.stats['events_routed'] += 1
        handlers = []
        
        for route in self.routes:
            if route['filter'].should_process(context):
                handlers.append(route['handler'])
                route['match_count'] += 1
                self.stats['routes_matched'] += 1
        
        # Use default handler if no routes matched
        if not handlers and self.default_handler:
            handlers.append(self.default_handler)
            self.stats['default_handler_used'] += 1
        
        return handlers
    
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        route_stats = []
        for route in self.routes:
            route_stats.append({
                'name': route['name'],
                'priority': route['priority'],
                'match_count': route['match_count'],
                'filter_stats': route['filter'].get_stats()
            })
        
        return {
            'router_name': self.name,
            'total_routes': len(self.routes),
            'events_routed': self.stats['events_routed'],
            'routes_matched': self.stats['routes_matched'],
            'default_handler_used': self.stats['default_handler_used'],
            'route_stats': route_stats
        }
    
    def clear_routes(self):
        """Clear all routing rules."""
        self.routes.clear()
        self.default_handler = None
        self.stats = {
            'events_routed': 0,
            'routes_matched': 0,
            'default_handler_used': 0
        }


# Predefined filter factories
def create_connection_filter() -> TypeFilter:
    """Create a filter for connection events."""
    return TypeFilter([
        EventType.CONNECTION_OPENED,
        EventType.CONNECTION_CLOSED,
        EventType.CONNECTION_ERROR,
        EventType.CONNECTION_RECONNECTING,
        EventType.CONNECTION_TIMEOUT,
        EventType.CONNECTION_HEARTBEAT
    ], name="connection_filter")


def create_database_filter() -> TypeFilter:
    """Create a filter for database events."""
    return TypeFilter([
        EventType.TABLE_UPDATE,
        EventType.REDUCER_CALL,
        EventType.TRANSACTION_COMMITTED,
        EventType.TRANSACTION_ROLLBACK,
        EventType.SCHEMA_UPDATED,
        EventType.DATABASE_ERROR
    ], name="database_filter")


def create_system_filter() -> TypeFilter:
    """Create a filter for system events."""
    return TypeFilter([
        EventType.SYSTEM_ERROR,
        EventType.PERFORMANCE_WARNING,
        EventType.MEMORY_PRESSURE,
        EventType.RESOURCE_EXHAUSTED,
        EventType.SYSTEM_READY,
        EventType.SYSTEM_SHUTDOWN
    ], name="system_filter")


def create_websocket_filter() -> SourceFilter:
    """Create a filter for WebSocket events."""
    return SourceFilter([
        "websocket_client",
        "websocket_connection",
        "websocket_handler"
    ], name="websocket_filter")


def create_error_filter() -> CompositeFilter:
    """Create a filter for error events."""
    error_types = TypeFilter([
        EventType.CONNECTION_ERROR,
        EventType.AUTHENTICATION_FAILED,
        EventType.SUBSCRIPTION_ERROR,
        EventType.MESSAGE_ERROR,
        EventType.DATABASE_ERROR,
        EventType.SYSTEM_ERROR
    ])
    
    error_metadata = MetadataFilter({"error": lambda x: x is not None})
    
    return CompositeFilter([error_types, error_metadata], "OR", name="error_filter")


def create_priority_filter(priority_levels: Set[str]) -> MetadataFilter:
    """Create a filter for events with specific priority levels."""
    return MetadataFilter(
        {"priority": lambda x: x in priority_levels},
        name="priority_filter"
    )


def create_user_filter(user_ids: Set[str]) -> MetadataFilter:
    """Create a filter for events from specific users."""
    return MetadataFilter(
        {"user_id": lambda x: x in user_ids},
        name="user_filter"
    )


def create_recent_events_filter(seconds: float) -> TimeFilter:
    """Create a filter for recent events."""
    return TimeFilter(
        min_time=time.time() - seconds,
        name=f"recent_{seconds}s_filter"
    )