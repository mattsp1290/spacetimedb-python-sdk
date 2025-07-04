"""
Event Filters for SpacetimeDB SDK Unified Event System

This module provides event filtering and routing capabilities.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Set, Union
from .core_events import Event, EventType, EventPriority


class EventFilter(ABC):
    """
    Abstract base class for event filters.
    """
    
    @abstractmethod
    def matches(self, event: Event) -> bool:
        """Check if event matches the filter criteria."""
        pass
    
    def __call__(self, event: Event) -> bool:
        """Allow filter to be used as a callable."""
        return self.matches(event)


class TypeFilter(EventFilter):
    """Filter events by type."""
    
    def __init__(self, event_types: Union[EventType, List[EventType], str, List[str]]):
        """
        Initialize type filter.
        
        Args:
            event_types: Event type(s) to match
        """
        if isinstance(event_types, (EventType, str)):
            event_types = [event_types]
        
        self.event_types = set()
        for event_type in event_types:
            if isinstance(event_type, EventType):
                self.event_types.add(event_type.value)
            else:
                self.event_types.add(event_type)
    
    def matches(self, event: Event) -> bool:
        """Check if event type matches."""
        return event.type.value in self.event_types


class PriorityFilter(EventFilter):
    """Filter events by priority level."""
    
    def __init__(self, min_priority: Optional[EventPriority] = None, 
                 max_priority: Optional[EventPriority] = None):
        """
        Initialize priority filter.
        
        Args:
            min_priority: Minimum priority level to match
            max_priority: Maximum priority level to match
        """
        self.min_priority = min_priority
        self.max_priority = max_priority
    
    def matches(self, event: Event) -> bool:
        """Check if event priority matches."""
        if self.min_priority and event.priority.value < self.min_priority.value:
            return False
        if self.max_priority and event.priority.value > self.max_priority.value:
            return False
        return True


class AgeFilter(EventFilter):
    """Filter events by age."""
    
    def __init__(self, max_age_seconds: float):
        """
        Initialize age filter.
        
        Args:
            max_age_seconds: Maximum age of events to match
        """
        self.max_age_seconds = max_age_seconds
    
    def matches(self, event: Event) -> bool:
        """Check if event age matches."""
        return not event.is_expired(self.max_age_seconds)


class SourceFilter(EventFilter):
    """Filter events by source."""
    
    def __init__(self, sources: Union[str, List[str]]):
        """
        Initialize source filter.
        
        Args:
            sources: Source(s) to match
        """
        if isinstance(sources, str):
            sources = [sources]
        self.sources = set(sources)
    
    def matches(self, event: Event) -> bool:
        """Check if event source matches."""
        return event.metadata.source in self.sources


class DataFilter(EventFilter):
    """Filter events by data content."""
    
    def __init__(self, key: str, value: Any = None, predicate: Optional[Callable[[Any], bool]] = None):
        """
        Initialize data filter.
        
        Args:
            key: Data key to check
            value: Expected value (if predicate not provided)
            predicate: Custom predicate function
        """
        self.key = key
        self.value = value
        self.predicate = predicate
    
    def matches(self, event: Event) -> bool:
        """Check if event data matches."""
        if self.key not in event.data:
            return False
        
        data_value = event.data[self.key]
        
        if self.predicate:
            return self.predicate(data_value)
        elif self.value is not None:
            return data_value == self.value
        else:
            return True  # Just check existence


class RegexFilter(EventFilter):
    """Filter events using regex patterns."""
    
    def __init__(self, pattern: str, field: str = "event_type"):
        """
        Initialize regex filter.
        
        Args:
            pattern: Regex pattern to match
            field: Field to match against ("event_type", "source", or data key)
        """
        self.pattern = re.compile(pattern)
        self.field = field
    
    def matches(self, event: Event) -> bool:
        """Check if event matches regex pattern."""
        if self.field == "event_type":
            value = event.type.value
        elif self.field == "source":
            value = event.metadata.source
        else:
            # Assume it's a data field
            value = event.data.get(self.field, "")
        
        if not isinstance(value, str):
            value = str(value)
        
        return bool(self.pattern.search(value))


class CustomFilter(EventFilter):
    """Filter events using custom predicate function."""
    
    def __init__(self, predicate: Callable[[Event], bool], name: str = "custom"):
        """
        Initialize custom filter.
        
        Args:
            predicate: Custom predicate function
            name: Name for the filter
        """
        self.predicate = predicate
        self.name = name
    
    def matches(self, event: Event) -> bool:
        """Check if event matches custom predicate."""
        try:
            return self.predicate(event)
        except Exception:
            return False


class CompositeFilter(EventFilter):
    """Combine multiple filters with AND/OR logic."""
    
    def __init__(self, filters: List[EventFilter], operator: str = "AND"):
        """
        Initialize composite filter.
        
        Args:
            filters: List of filters to combine
            operator: "AND" or "OR" logic
        """
        self.filters = filters
        self.operator = operator.upper()
        
        if self.operator not in ["AND", "OR"]:
            raise ValueError("Operator must be 'AND' or 'OR'")
    
    def matches(self, event: Event) -> bool:
        """Check if event matches composite filter."""
        if not self.filters:
            return True
        
        if self.operator == "AND":
            return all(f.matches(event) for f in self.filters)
        else:  # OR
            return any(f.matches(event) for f in self.filters)


class NotFilter(EventFilter):
    """Invert another filter."""
    
    def __init__(self, filter_to_invert: EventFilter):
        """
        Initialize NOT filter.
        
        Args:
            filter_to_invert: Filter to invert
        """
        self.filter_to_invert = filter_to_invert
    
    def matches(self, event: Event) -> bool:
        """Check if event does NOT match the wrapped filter."""
        return not self.filter_to_invert.matches(event)


# Convenience functions for creating filters

def type_filter(event_types: Union[EventType, List[EventType], str, List[str]]) -> TypeFilter:
    """Create a type filter."""
    return TypeFilter(event_types)


def priority_filter(min_priority: Optional[EventPriority] = None, 
                   max_priority: Optional[EventPriority] = None) -> PriorityFilter:
    """Create a priority filter."""
    return PriorityFilter(min_priority, max_priority)


def age_filter(max_age_seconds: float) -> AgeFilter:
    """Create an age filter."""
    return AgeFilter(max_age_seconds)


def source_filter(sources: Union[str, List[str]]) -> SourceFilter:
    """Create a source filter."""
    return SourceFilter(sources)


def data_filter(key: str, value: Any = None, predicate: Optional[Callable[[Any], bool]] = None) -> DataFilter:
    """Create a data filter."""
    return DataFilter(key, value, predicate)


def regex_filter(pattern: str, field: str = "event_type") -> RegexFilter:
    """Create a regex filter."""
    return RegexFilter(pattern, field)


def custom_filter(predicate: Callable[[Event], bool], name: str = "custom") -> CustomFilter:
    """Create a custom filter."""
    return CustomFilter(predicate, name)


def and_filter(*filters: EventFilter) -> CompositeFilter:
    """Create an AND composite filter."""
    return CompositeFilter(list(filters), "AND")


def or_filter(*filters: EventFilter) -> CompositeFilter:
    """Create an OR composite filter."""
    return CompositeFilter(list(filters), "OR")


def not_filter(filter_to_invert: EventFilter) -> NotFilter:
    """Create a NOT filter."""
    return NotFilter(filter_to_invert)


# Pre-defined filter sets for common use cases

class CommonFilters:
    """Collection of commonly used filters."""
    
    @staticmethod
    def connection_events() -> TypeFilter:
        """Filter for connection-related events."""
        return type_filter([
            EventType.CONNECTION_ESTABLISHED,
            EventType.CONNECTION_OPENED,
            EventType.CONNECTION_CLOSED,
            EventType.CONNECTION_LOST,
            EventType.CONNECTION_ERROR
        ])
    
    @staticmethod
    def authentication_events() -> TypeFilter:
        """Filter for authentication-related events."""
        return type_filter([
            EventType.IDENTITY_RECEIVED,
            EventType.IDENTITY_CHANGED,
            EventType.IDENTITY_TOKEN,
            EventType.AUTHENTICATION_SUCCESS,
            EventType.AUTHENTICATION_FAILED
        ])
    
    @staticmethod
    def subscription_events() -> TypeFilter:
        """Filter for subscription-related events."""
        return type_filter([
            EventType.SUBSCRIPTION_APPLIED,
            EventType.SUBSCRIPTION_UPDATE,
            EventType.SUBSCRIPTION_ERROR,
            EventType.SUBSCRIPTION_REMOVED,
            EventType.INITIAL_SUBSCRIPTION
        ])
    
    @staticmethod
    def table_events() -> TypeFilter:
        """Filter for table-related events."""
        return type_filter([
            EventType.TABLE_ROW_INSERT,
            EventType.TABLE_ROW_UPDATE,
            EventType.TABLE_ROW_DELETE,
            EventType.TABLE_UPDATE
        ])
    
    @staticmethod
    def reducer_events() -> TypeFilter:
        """Filter for reducer-related events."""
        return type_filter([
            EventType.REDUCER_CALLED,
            EventType.REDUCER_SUCCESS,
            EventType.REDUCER_ERROR
        ])
    
    @staticmethod
    def transaction_events() -> TypeFilter:
        """Filter for transaction-related events."""
        return type_filter([
            EventType.TRANSACTION_UPDATE,
            EventType.TRANSACTION_BEGIN,
            EventType.TRANSACTION_COMMIT,
            EventType.TRANSACTION_ROLLBACK
        ])
    
    @staticmethod
    def error_events() -> TypeFilter:
        """Filter for error events."""
        return type_filter([
            EventType.ERROR_OCCURRED,
            EventType.CONNECTION_ERROR,
            EventType.SUBSCRIPTION_ERROR,
            EventType.REDUCER_ERROR,
            EventType.QUERY_ERROR
        ])
    
    @staticmethod
    def high_priority_events() -> PriorityFilter:
        """Filter for high priority events."""
        return priority_filter(min_priority=EventPriority.HIGH)
    
    @staticmethod
    def critical_events() -> PriorityFilter:
        """Filter for critical events."""
        return priority_filter(min_priority=EventPriority.CRITICAL)
    
    @staticmethod
    def recent_events(max_age_seconds: float = 60.0) -> AgeFilter:
        """Filter for recent events."""
        return age_filter(max_age_seconds)
    
    @staticmethod
    def websocket_events() -> SourceFilter:
        """Filter for WebSocket-related events."""
        return source_filter(["websocket", "WebSocketClient", "SpacetimeWebSocketClient"])
    
    @staticmethod
    def database_activity() -> CompositeFilter:
        """Filter for database activity events."""
        return or_filter(
            CommonFilters.table_events(),
            CommonFilters.transaction_events(),
            type_filter(EventType.DATABASE_UPDATE)
        )