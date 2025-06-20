"""
Enhanced Event System for SpacetimeDB SDK

Production-ready event management system with advanced features extracted
from blackholio-python-client's battle-tested patterns.

Features:
- Hierarchical event types and priority-based processing
- Multi-layered filtering and middleware pipeline
- Async/sync handler support with thread pool integration
- Comprehensive metrics and monitoring
- Event lifecycle management with TTL
- Publisher/subscriber pattern with context management
- Error isolation and graceful degradation
"""

import asyncio
import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Union, TypeVar, Generic


logger = logging.getLogger(__name__)


class EventType(Enum):
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


class EventPriority(IntEnum):
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
    
    def __post_init__(self):
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


class EventMetrics:
    """Event system metrics collector."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all metrics."""
        self.events_published = 0
        self.events_processed = 0
        self.events_failed = 0
        self.events_by_type = {}
        self.events_by_priority = {}
        self.processing_times = []
        self.start_time = time.time()
    
    def record_published_event(self, event: Event):
        """Record an event being published."""
        self.events_published += 1
        event_type = event.event_type.value
        priority = event.priority.value
        
        self.events_by_type[event_type] = self.events_by_type.get(event_type, 0) + 1
        self.events_by_priority[priority] = self.events_by_priority.get(priority, 0) + 1
    
    def record_processed_event(self, event: Event, processing_time: float):
        """Record an event being processed."""
        self.events_processed += 1
        self.processing_times.append(processing_time)
        
        # Keep only last 1000 processing times
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]
    
    def record_failed_event(self, event: Event, error: Exception):
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


class EnhancedEventManager:
    """
    Enhanced event management system for SpacetimeDB SDK.
    
    Provides centralized event management with subscription handling, event routing,
    middleware processing, and comprehensive monitoring.
    """
    
    def __init__(self,
                 max_queue_size: int = 10000,
                 max_worker_threads: int = 4,
                 enable_metrics: bool = True,
                 default_event_ttl: float = 300.0):
        """
        Initialize event manager.
        
        Args:
            max_queue_size: Maximum number of events in queue
            max_worker_threads: Maximum worker threads for sync handlers
            enable_metrics: Whether to collect event metrics
            default_event_ttl: Default event time-to-live in seconds
        """
        self.max_queue_size = max_queue_size
        self.max_worker_threads = max_worker_threads
        self.default_event_ttl = default_event_ttl
        
        # Event queue and processing
        self._event_queue = asyncio.Queue(maxsize=max_queue_size)
        self._priority_queue = deque()
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Subscriber management
        self._subscribers: Dict[EventType, Set[EventSubscriber]] = defaultdict(set)
        self._global_subscribers: Set[EventSubscriber] = set()
        self._subscriber_lock = threading.RLock()
        
        # Handler management
        self._async_handlers: Dict[EventType, List[AsyncEventHandler]] = defaultdict(list)
        self._sync_handlers: Dict[EventType, List[SyncEventHandler]] = defaultdict(list)
        self._handler_lock = threading.RLock()
        
        # Thread pool for sync handlers
        self._thread_pool = ThreadPoolExecutor(max_workers=max_worker_threads)
        
        # Metrics and monitoring
        self._metrics = EventMetrics() if enable_metrics else None
        self._enable_metrics = enable_metrics
        
        # Configuration
        self._filters: List[EventFilter] = []
        self._middleware: List[Callable[[Event], Optional[Event]]] = []
        
        # Auto-start processing
        self._start_processing()
    
    def _start_processing(self):
        """Start the event processing task."""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_events())
    
    async def _process_events(self):
        """Main event processing loop."""
        logger.info("Enhanced event manager started processing events")
        
        while not self._shutdown_event.is_set():
            try:
                # Process priority events first
                if self._priority_queue:
                    event = self._priority_queue.popleft()
                    await self._handle_event(event)
                    continue
                
                # Wait for regular events with timeout
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                    await self._handle_event(event)
                    self._event_queue.task_done()
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}", exc_info=True)
                await asyncio.sleep(0.1)  # Brief pause on error
        
        logger.info("Enhanced event manager stopped processing events")
    
    async def _handle_event(self, event: Event):
        """Handle a single event."""
        start_time = time.time()
        
        try:
            # Apply middleware transformations
            processed_event = event
            for middleware in self._middleware:
                processed_event = middleware(processed_event)
                if processed_event is None:
                    logger.debug(f"Event {event.event_id} filtered out by middleware")
                    return
            
            # Apply filters
            for event_filter in self._filters:
                if not event_filter.matches(processed_event):
                    logger.debug(f"Event {event.event_id} filtered out by filter")
                    return
            
            # Check if event has expired
            if processed_event.is_expired(self.default_event_ttl):
                logger.warning(f"Event {event.event_id} expired, discarding")
                return
            
            # Notify subscribers and handlers
            await self._notify_subscribers(processed_event)
            await self._execute_handlers(processed_event)
            
            # Record metrics
            if self._enable_metrics and self._metrics:
                processing_time = time.time() - start_time
                self._metrics.record_processed_event(processed_event, processing_time)
                
        except Exception as e:
            logger.error(f"Error handling event {event.event_id}: {e}", exc_info=True)
            if self._enable_metrics and self._metrics:
                self._metrics.record_failed_event(event, e)
    
    async def _notify_subscribers(self, event: Event):
        """Notify all relevant subscribers about the event."""
        # Get type-specific subscribers
        type_subscribers = set()
        with self._subscriber_lock:
            type_subscribers.update(self._subscribers.get(event.event_type, set()))
            type_subscribers.update(self._global_subscribers)
        
        # Notify each subscriber
        for subscriber in type_subscribers:
            try:
                await subscriber.handle_event(event)
            except Exception as e:
                logger.error(f"Error in subscriber {subscriber}: {e}", exc_info=True)
    
    async def _execute_handlers(self, event: Event):
        """Execute all relevant handlers for the event."""
        # Execute async handlers
        async_handlers = []
        with self._handler_lock:
            async_handlers = self._async_handlers.get(event.event_type, []).copy()
        
        for handler in async_handlers:
            try:
                await handler.handle_event(event)
            except Exception as e:
                logger.error(f"Error in async handler {handler}: {e}", exc_info=True)
        
        # Execute sync handlers in thread pool
        sync_handlers = []
        with self._handler_lock:
            sync_handlers = self._sync_handlers.get(event.event_type, []).copy()
        
        for handler in sync_handlers:
            try:
                # Submit to thread pool
                self._thread_pool.submit(handler.handle_event_sync, event)
                # Don't wait for completion to avoid blocking
            except Exception as e:
                logger.error(f"Error submitting sync handler {handler}: {e}", exc_info=True)
    
    async def publish(self, event: Event, priority: bool = False) -> bool:
        """
        Publish an event to the system.
        
        Args:
            event: Event to publish
            priority: Whether to process with high priority
            
        Returns:
            True if event was queued successfully
        """
        try:
            # Record published event
            if self._enable_metrics and self._metrics:
                self._metrics.record_published_event(event)
            
            # Add to appropriate queue
            if priority or event.priority >= EventPriority.CRITICAL:
                self._priority_queue.append(event)
            else:
                try:
                    self._event_queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"Event queue full, dropping event {event.event_id}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error publishing event {event.event_id}: {e}")
            return False
    
    def subscribe(self, 
                  subscriber: EventSubscriber, 
                  event_types: Optional[Union[EventType, List[EventType]]] = None) -> None:
        """
        Subscribe to events.
        
        Args:
            subscriber: Event subscriber
            event_types: Event types to subscribe to (None for global subscription)
        """
        with self._subscriber_lock:
            if event_types is None:
                self._global_subscribers.add(subscriber)
            else:
                if isinstance(event_types, EventType):
                    event_types = [event_types]
                
                for event_type in event_types:
                    self._subscribers[event_type].add(subscriber)
    
    def unsubscribe(self, 
                    subscriber: EventSubscriber, 
                    event_types: Optional[Union[EventType, List[EventType]]] = None) -> None:
        """
        Unsubscribe from events.
        
        Args:
            subscriber: Event subscriber
            event_types: Event types to unsubscribe from (None for global unsubscription)
        """
        with self._subscriber_lock:
            if event_types is None:
                self._global_subscribers.discard(subscriber)
            else:
                if isinstance(event_types, EventType):
                    event_types = [event_types]
                
                for event_type in event_types:
                    self._subscribers[event_type].discard(subscriber)
    
    def add_handler(self, 
                    handler: Union[AsyncEventHandler, SyncEventHandler], 
                    event_types: Union[EventType, List[EventType]]) -> None:
        """
        Add an event handler.
        
        Args:
            handler: Event handler
            event_types: Event types to handle
        """
        if isinstance(event_types, EventType):
            event_types = [event_types]
        
        with self._handler_lock:
            for event_type in event_types:
                if isinstance(handler, AsyncEventHandler):
                    self._async_handlers[event_type].append(handler)
                elif isinstance(handler, SyncEventHandler):
                    self._sync_handlers[event_type].append(handler)
                else:
                    raise ValueError(f"Invalid handler type: {type(handler)}")
    
    def add_filter(self, event_filter: EventFilter) -> None:
        """Add a global event filter."""
        self._filters.append(event_filter)
    
    def add_middleware(self, middleware: Callable[[Event], Optional[Event]]) -> None:
        """Add event middleware."""
        self._middleware.append(middleware)
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get event system metrics."""
        if self._metrics:
            return self._metrics.get_metrics()
        return None
    
    async def shutdown(self) -> None:
        """Shutdown the event manager gracefully."""
        logger.info("Shutting down enhanced event manager...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for processing to complete
        if self._processing_task:
            try:
                await asyncio.wait_for(self._processing_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Event processing task didn't complete within timeout")
                self._processing_task.cancel()
        
        # Shutdown thread pool
        self._thread_pool.shutdown(wait=True)
        
        logger.info("Enhanced event manager shutdown complete")


# Global event manager instance
_event_manager: Optional[EnhancedEventManager] = None
_event_manager_lock = threading.Lock()


def get_event_manager() -> EnhancedEventManager:
    """
    Get global event manager instance (singleton).
    
    Returns:
        EnhancedEventManager instance
    """
    global _event_manager
    
    with _event_manager_lock:
        if _event_manager is None:
            _event_manager = EnhancedEventManager()
        return _event_manager


@asynccontextmanager
async def event_context():
    """Context manager for event processing."""
    manager = get_event_manager()
    try:
        yield manager
    finally:
        # Cleanup if needed
        pass


# Convenience functions
async def publish_event(event: Event, priority: bool = False) -> bool:
    """Convenience function to publish an event."""
    manager = get_event_manager()
    return await manager.publish(event, priority)


def subscribe_to_events(callback: Callable[[Event], Any], 
                       event_types: Optional[Union[EventType, List[EventType]]] = None,
                       name: Optional[str] = None) -> CallbackEventSubscriber:
    """Convenience function to subscribe to events with a callback."""
    manager = get_event_manager()
    subscriber = CallbackEventSubscriber(callback, name)
    manager.subscribe(subscriber, event_types)
    return subscriber


__all__ = [
    'EventType',
    'EventPriority',
    'Event',
    'EventT',
    'EventFilter',
    'EventMetrics',
    'EventHandler',
    'AsyncEventHandler',
    'SyncEventHandler',
    'EventSubscriber',
    'CallbackEventSubscriber',
    'FilteredEventSubscriber',
    'EnhancedEventManager',
    'get_event_manager',
    'event_context',
    'publish_event',
    'subscribe_to_events'
]