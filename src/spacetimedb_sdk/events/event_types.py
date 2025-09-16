"""
Event Types Module for SpacetimeDB SDK Enhanced Event System

Defines core event types, enums, and base classes for the event system.
This module extracts the type definitions from enhanced_event_system.py
for better separation of concerns.
"""

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, Optional, TypeVar

# Import our serializable enum base class
from ..base_enum import SerializableEnum


class EventType(SerializableEnum):
    """Event type enumeration for categorizing SpacetimeDB events."""
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


class EventPriority(SerializableEnum):
    """Event priority levels (higher numbers = higher priority)."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20
    EMERGENCY = 100


@dataclass
class Event(ABC):
    """
    Base event class for all events in the SpacetimeDB SDK.
    
    All events must inherit from this class and provide type information
    and relevant data for the event.
    """
    
    # Event metadata
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    event_type: EventType = field(default=EventType.SYSTEM)
    priority: EventPriority = field(default=EventPriority.NORMAL)
    
    # Event context
    source: Optional[str] = field(default=None)
    correlation_id: Optional[str] = field(default=None)
    
    # Event data
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Post-initialization hook for validation."""
        self.validate()
    
    @abstractmethod
    def validate(self) -> None:
        """Validate event data and configuration."""
        pass
    
    @abstractmethod
    def get_event_name(self) -> str:
        """Get the human-readable event name."""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation."""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type.value,
            'priority': self.priority.value,
            'source': self.source,
            'correlation_id': self.correlation_id,
            'event_name': self.get_event_name(),
            'data': self.data.copy()
        }
    
    def get_age_seconds(self) -> float:
        """Get the age of the event in seconds."""
        return time.time() - self.timestamp
    
    def is_expired(self, max_age_seconds: float) -> bool:
        """Check if the event has expired based on max age."""
        return self.get_age_seconds() > max_age_seconds
    
    def add_context(self, key: str, value: Any) -> None:
        """Add contextual data to the event."""
        self.data[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get contextual data from the event."""
        return self.data.get(key, default)
    
    def __str__(self) -> str:
        """String representation of the event."""
        return f"{self.get_event_name()}({self.event_id[:8]})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the event."""
        return (f"{self.__class__.__name__}("
                f"event_id='{self.event_id}', "
                f"timestamp={self.timestamp}, "
                f"event_type={self.event_type.value}, "
                f"priority={self.priority.value}, "
                f"source='{self.source}', "
                f"data_keys={list(self.data.keys())})")


# Type variable for generic event handling
EventT = TypeVar('EventT', bound=Event)


class EventMetrics:
    """Event system metrics collector."""
    
    def __init__(self) -> None:
        self.reset()
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.events_published = 0
        self.events_processed = 0
        self.events_failed = 0
        self.events_by_type = {}
        self.events_by_priority = {}
        self.processing_times = []
        self.start_time = time.time()
    
    def record_published_event(self, event: Event) -> None:
        """Record an event being published."""
        self.events_published += 1
        event_type = event.event_type.value
        priority = event.priority.value
        
        self.events_by_type[event_type] = self.events_by_type.get(event_type, 0) + 1
        self.events_by_priority[priority] = self.events_by_priority.get(priority, 0) + 1
    
    def record_processed_event(self, event: Event, processing_time: float) -> None:
        """Record an event being processed."""
        self.events_processed += 1
        self.processing_times.append(processing_time)
        
        # Keep only last 1000 processing times
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]
    
    def record_failed_event(self, event: Event, error: Exception) -> None:
        """Record an event processing failure."""
        self.events_failed += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        uptime = time.time() - self.start_time
        
        # Calculate processing time statistics
        avg_processing_time = 0
        max_processing_time = 0
        if self.processing_times:
            avg_processing_time = sum(self.processing_times) / len(self.processing_times)
            max_processing_time = max(self.processing_times)
        
        return {
            'uptime_seconds': uptime,
            'events_published': self.events_published,
            'events_processed': self.events_processed,
            'events_failed': self.events_failed,
            'success_rate': (self.events_processed / max(1, self.events_published)) * 100,
            'events_per_second': self.events_published / max(1, uptime),
            'events_by_type': self.events_by_type.copy(),
            'events_by_priority': self.events_by_priority.copy(),
            'avg_processing_time_ms': avg_processing_time * 1000,
            'max_processing_time_ms': max_processing_time * 1000,
            'queue_length': len(self.processing_times)
        }