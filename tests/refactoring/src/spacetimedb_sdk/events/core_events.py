"""
Core Event System Types and Definitions

This module defines the 36 consolidated event types that unify the previous
scattered event systems, along with core data structures and handler types.
"""

import time
from enum import Enum
from typing import Any, Dict, Optional, Callable, Union, Awaitable, List
from dataclasses import dataclass, field
import uuid
import asyncio


class EventType(Enum):
    """
    Unified event types consolidating 43 scattered events into 36 organized types.
    
    Categories:
    - Connection Events: WebSocket connection lifecycle
    - Authentication Events: Auth state changes
    - Subscription Events: Subscription lifecycle
    - Message Events: Message processing
    - Database Events: Database operations
    - System Events: System-level events
    """
    
    # Connection Events (6 types)
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_ERROR = "connection_error"
    CONNECTION_RECONNECTING = "connection_reconnecting"
    CONNECTION_TIMEOUT = "connection_timeout"
    CONNECTION_HEARTBEAT = "connection_heartbeat"
    
    # Authentication Events (6 types)
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHENTICATION_EXPIRED = "authentication_expired"
    AUTHENTICATION_REFRESH = "authentication_refresh"
    AUTHENTICATION_LOGOUT = "authentication_logout"
    AUTHENTICATION_CHALLENGE = "authentication_challenge"
    
    # Subscription Events (6 types)
    SUBSCRIPTION_APPLIED = "subscription_applied"
    SUBSCRIPTION_ERROR = "subscription_error"
    SUBSCRIPTION_CLOSED = "subscription_closed"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    SUBSCRIPTION_PAUSED = "subscription_paused"
    SUBSCRIPTION_RESUMED = "subscription_resumed"
    
    # Message Events (6 types)
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    MESSAGE_ERROR = "message_error"
    MESSAGE_QUEUED = "message_queued"
    MESSAGE_DROPPED = "message_dropped"
    MESSAGE_BATCH_PROCESSED = "message_batch_processed"
    
    # Database Events (6 types)
    TABLE_UPDATE = "table_update"
    REDUCER_CALL = "reducer_call"
    TRANSACTION_COMMITTED = "transaction_committed"
    TRANSACTION_ROLLBACK = "transaction_rollback"
    SCHEMA_UPDATED = "schema_updated"
    DATABASE_ERROR = "database_error"
    
    # System Events (6 types)
    SYSTEM_ERROR = "system_error"
    PERFORMANCE_WARNING = "performance_warning"
    MEMORY_PRESSURE = "memory_pressure"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    SYSTEM_READY = "system_ready"
    SYSTEM_SHUTDOWN = "system_shutdown"


class EventPriority(Enum):
    """Handler execution priority levels."""
    CRITICAL = 0    # Critical system handlers
    HIGH = 1        # High priority handlers
    NORMAL = 2      # Normal priority handlers
    LOW = 3         # Low priority handlers
    BACKGROUND = 4  # Background processing


@dataclass
class EventMetadata:
    """
    Event metadata container with extensible additional data.
    
    Attributes:
        source: Source component that generated the event
        timestamp: Unix timestamp when event was created
        correlation_id: Unique identifier for event correlation
        additional_data: Extensible metadata dictionary
    """
    source: str
    timestamp: float
    correlation_id: str
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create(cls, source: str, **additional_data) -> 'EventMetadata':
        """Create metadata with auto-generated correlation ID and timestamp."""
        return cls(
            source=source,
            timestamp=time.time(),
            correlation_id=str(uuid.uuid4()),
            additional_data=additional_data
        )


@dataclass
class EventContext:
    """
    Complete event context containing all event information.
    
    This is the primary data structure passed to event handlers and contains
    all necessary information about the event, its source, and metadata.
    
    Attributes:
        event_type: Type of event being emitted
        source: Source component that generated the event
        timestamp: Unix timestamp when event was created
        metadata: Event metadata dictionary
        correlation_id: Optional correlation ID for event tracking
        data: Event-specific data payload
        parent_context: Optional parent context for nested events
    """
    event_type: EventType
    source: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    data: Optional[Any] = None
    parent_context: Optional['EventContext'] = None
    
    def __post_init__(self):
        """Initialize correlation ID if not provided."""
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())
    
    @classmethod
    def create(
        cls,
        event_type: EventType,
        source: str,
        data: Optional[Any] = None,
        **metadata
    ) -> 'EventContext':
        """Create an event context with auto-generated timestamp and correlation ID."""
        return cls(
            event_type=event_type,
            source=source,
            timestamp=time.time(),
            metadata=metadata,
            data=data
        )
    
    def with_parent(self, parent: 'EventContext') -> 'EventContext':
        """Create a new context with this context as parent."""
        return EventContext(
            event_type=self.event_type,
            source=self.source,
            timestamp=self.timestamp,
            metadata=self.metadata.copy(),
            correlation_id=self.correlation_id,
            data=self.data,
            parent_context=parent
        )
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value with optional default."""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any):
        """Set metadata value."""
        self.metadata[key] = value
    
    def is_child_of(self, other: 'EventContext') -> bool:
        """Check if this context is a child of another context."""
        parent = self.parent_context
        while parent:
            if parent.correlation_id == other.correlation_id:
                return True
            parent = parent.parent_context
        return False


# Handler type definitions
EventHandler = Callable[[EventContext], None]
AsyncEventHandler = Callable[[EventContext], Awaitable[None]]
UniversalEventHandler = Union[EventHandler, AsyncEventHandler]


@dataclass
class HandlerInfo:
    """Information about a registered event handler."""
    handler: UniversalEventHandler
    priority: EventPriority
    is_async: bool
    registration_time: float
    call_count: int = 0
    total_duration: float = 0.0
    last_error: Optional[Exception] = None
    
    def __post_init__(self):
        """Initialize handler type detection."""
        if self.is_async is None:
            self.is_async = asyncio.iscoroutinefunction(self.handler)
    
    def record_call(self, duration: float, error: Optional[Exception] = None):
        """Record handler execution statistics."""
        self.call_count += 1
        self.total_duration += duration
        if error:
            self.last_error = error
    
    @property
    def average_duration(self) -> float:
        """Calculate average handler execution duration."""
        if self.call_count == 0:
            return 0.0
        return self.total_duration / self.call_count


class EventBatch:
    """
    Container for batching multiple events for efficient processing.
    
    This enables performance optimizations by processing similar events
    together rather than individually.
    """
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 0.1):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.events: List[EventContext] = []
        self.last_flush = time.time()
    
    def add_event(self, context: EventContext) -> bool:
        """
        Add event to batch.
        
        Returns:
            True if batch should be flushed, False otherwise
        """
        self.events.append(context)
        current_time = time.time()
        
        return (
            len(self.events) >= self.batch_size or
            current_time - self.last_flush >= self.flush_interval
        )
    
    def flush(self) -> List[EventContext]:
        """Flush and return all batched events."""
        events = self.events.copy()
        self.events.clear()
        self.last_flush = time.time()
        return events
    
    def should_flush(self) -> bool:
        """Check if batch should be flushed based on time."""
        return time.time() - self.last_flush >= self.flush_interval


class EventStats:
    """Event system statistics and metrics."""
    
    def __init__(self):
        self.events_emitted = 0
        self.events_processed = 0
        self.handlers_executed = 0
        self.errors_encountered = 0
        self.total_processing_time = 0.0
        self.start_time = time.time()
        self.event_type_counts: Dict[EventType, int] = {}
        self.handler_performance: Dict[str, HandlerInfo] = {}
    
    def record_event_emitted(self, event_type: EventType):
        """Record that an event was emitted."""
        self.events_emitted += 1
        self.event_type_counts[event_type] = self.event_type_counts.get(event_type, 0) + 1
    
    def record_event_processed(self, processing_time: float):
        """Record that an event was processed."""
        self.events_processed += 1
        self.total_processing_time += processing_time
    
    def record_handler_execution(self, handler_name: str, duration: float, error: Optional[Exception] = None):
        """Record handler execution statistics."""
        self.handlers_executed += 1
        if error:
            self.errors_encountered += 1
        
        if handler_name not in self.handler_performance:
            self.handler_performance[handler_name] = HandlerInfo(
                handler=None,  # Not stored in stats
                priority=EventPriority.NORMAL,
                is_async=False,
                registration_time=time.time()
            )
        
        self.handler_performance[handler_name].record_call(duration, error)
    
    def get_average_processing_time(self) -> float:
        """Get average event processing time."""
        if self.events_processed == 0:
            return 0.0
        return self.total_processing_time / self.events_processed
    
    def get_events_per_second(self) -> float:
        """Get events per second rate."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        return self.events_emitted / elapsed
    
    def get_error_rate(self) -> float:
        """Get error rate as percentage."""
        if self.handlers_executed == 0:
            return 0.0
        return (self.errors_encountered / self.handlers_executed) * 100
    
    def reset(self):
        """Reset all statistics."""
        self.events_emitted = 0
        self.events_processed = 0
        self.handlers_executed = 0
        self.errors_encountered = 0
        self.total_processing_time = 0.0
        self.start_time = time.time()
        self.event_type_counts.clear()
        self.handler_performance.clear()


# Event system exceptions
class EventSystemError(Exception):
    """Base exception for event system errors."""
    pass


class HandlerExecutionError(EventSystemError):
    """Exception raised when event handler execution fails."""
    
    def __init__(self, handler_name: str, original_error: Exception):
        self.handler_name = handler_name
        self.original_error = original_error
        super().__init__(f"Handler '{handler_name}' failed: {original_error}")


class EventFilterError(EventSystemError):
    """Exception raised when event filtering fails."""
    pass


class EventBatchError(EventSystemError):
    """Exception raised when event batching fails."""
    pass


# Utility functions
def is_async_handler(handler: UniversalEventHandler) -> bool:
    """Check if a handler is async."""
    return asyncio.iscoroutinefunction(handler)


def get_handler_name(handler: UniversalEventHandler) -> str:
    """Get a descriptive name for a handler."""
    if hasattr(handler, '__name__'):
        return handler.__name__
    elif hasattr(handler, '__class__'):
        return f"{handler.__class__.__name__}.{getattr(handler, '__name__', 'unknown')}"
    else:
        return str(handler)


def create_system_event(
    event_type: EventType,
    source: str = "event_system",
    **metadata
) -> EventContext:
    """Create a system-level event context."""
    return EventContext.create(
        event_type=event_type,
        source=source,
        **metadata
    )


def create_connection_event(
    event_type: EventType,
    connection_id: str,
    **metadata
) -> EventContext:
    """Create a connection-related event context."""
    return EventContext.create(
        event_type=event_type,
        source="websocket_client",
        connection_id=connection_id,
        **metadata
    )


def create_database_event(
    event_type: EventType,
    database_name: str,
    **metadata
) -> EventContext:
    """Create a database-related event context."""
    return EventContext.create(
        event_type=event_type,
        source="database_client",
        database_name=database_name,
        **metadata
    )