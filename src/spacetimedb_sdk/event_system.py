"""
Advanced Event System for SpacetimeDB Python SDK.

Provides sophisticated event handling matching TypeScript SDK:
- EventContext with rich metadata and operations
- Enhanced ReducerEvent with full information
- EventEmitter for custom event handling
- Event filtering and routing
- Async event handler support
- Event history and replay capabilities
"""

import asyncio
import enum
import logging
import time
import threading
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union,
    TypeVar, Generic, Awaitable, Deque
)
from weakref import WeakKeyDictionary, WeakSet

from .protocol import Identity, ConnectionId, EnergyQuanta
from .query_id import QueryId

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T')
EventHandler = Union[Callable[..., None], Callable[..., Awaitable[None]]]
EventFilter = Callable[['Event'], bool]
EventTransformer = Callable[['Event'], Optional['Event']]


class EventType(enum.Enum):
    """Standard event types in the system."""
    # Connection events
    CONNECTION_ESTABLISHED = "connection.established"
    CONNECTION_LOST = "connection.lost"
    CONNECTION_ERROR = "connection.error"
    
    # Identity events
    IDENTITY_RECEIVED = "identity.received"
    IDENTITY_CHANGED = "identity.changed"
    
    # Subscription events
    SUBSCRIPTION_APPLIED = "subscription.applied"
    SUBSCRIPTION_ERROR = "subscription.error"
    SUBSCRIPTION_REMOVED = "subscription.removed"
    
    # Table events
    TABLE_ROW_INSERT = "table.row.insert"
    TABLE_ROW_UPDATE = "table.row.update"
    TABLE_ROW_DELETE = "table.row.delete"
    
    # Reducer events
    REDUCER_CALLED = "reducer.called"
    REDUCER_SUCCESS = "reducer.success"
    REDUCER_ERROR = "reducer.error"
    
    # Energy events
    ENERGY_LOW = "energy.low"
    ENERGY_EXHAUSTED = "energy.exhausted"
    ENERGY_REFILLED = "energy.refilled"
    
    # Custom events
    CUSTOM = "custom"


@dataclass
class EventMetadata:
    """Metadata attached to every event."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    user_metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def datetime(self) -> datetime:
        """Get timestamp as datetime object."""
        return datetime.fromtimestamp(self.timestamp)


@dataclass
class Event:
    """Base class for all events in the system."""
    type: EventType
    data: Dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)
    
    def with_metadata(self, **kwargs) -> 'Event':
        """Return a copy of the event with updated metadata."""
        import copy
        new_event = copy.deepcopy(self)
        for key, value in kwargs.items():
            if hasattr(new_event.metadata, key):
                setattr(new_event.metadata, key, value)
            else:
                new_event.metadata.user_metadata[key] = value
        return new_event


@dataclass
class ReducerEvent:
    """Enhanced reducer event with full metadata."""
    reducer_name: str
    type: EventType = EventType.REDUCER_CALLED
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)
    caller_identity: Optional[Identity] = None
    caller_connection_id: Optional[ConnectionId] = None
    args: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    error_message: Optional[str] = None
    energy_used: int = 0
    execution_duration_nanos: int = 0
    request_id: Optional[bytes] = None
    
    def __post_init__(self):
        """Initialize data field if needed."""
        if not self.data:
            self.data = {
                'reducer_name': self.reducer_name,
                'args': self.args,
                'status': self.status,
                'error_message': self.error_message,
                'energy_used': self.energy_used,
                'execution_duration_nanos': self.execution_duration_nanos
            }
    
    @property
    def is_success(self) -> bool:
        """Check if reducer execution was successful."""
        return self.status == "success"
    
    @property
    def is_error(self) -> bool:
        """Check if reducer execution failed."""
        return self.status == "error"
    
    @property
    def execution_time_ms(self) -> float:
        """Get execution time in milliseconds."""
        return self.execution_duration_nanos / 1_000_000.0
    
    def with_metadata(self, **kwargs) -> 'ReducerEvent':
        """Return a copy of the event with updated metadata."""
        import copy
        new_event = copy.deepcopy(self)
        for key, value in kwargs.items():
            if hasattr(new_event.metadata, key):
                setattr(new_event.metadata, key, value)
            else:
                new_event.metadata.user_metadata[key] = value
        return new_event


@dataclass
class TableEvent:
    """Event for table row changes."""
    table_name: str
    operation: str  # "insert", "update", "delete"
    row_data: Any
    type: EventType = EventType.TABLE_ROW_INSERT
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)
    old_row_data: Optional[Any] = None
    primary_key: Optional[Any] = None
    reducer_event: Optional[ReducerEvent] = None
    
    def __post_init__(self):
        """Initialize data field if needed."""
        if not self.data:
            self.data = {
                'table_name': self.table_name,
                'operation': self.operation,
                'row_data': self.row_data,
                'old_row_data': self.old_row_data,
                'primary_key': self.primary_key
            }
    
    def with_metadata(self, **kwargs) -> 'TableEvent':
        """Return a copy of the event with updated metadata."""
        import copy
        new_event = copy.deepcopy(self)
        for key, value in kwargs.items():
            if hasattr(new_event.metadata, key):
                setattr(new_event.metadata, key, value)
            else:
                new_event.metadata.user_metadata[key] = value
        return new_event


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
    def event_type(self) -> EventType:
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


class EventEmitter:
    """
    Powerful event emitter with TypeScript SDK parity.
    
    Features:
    - Sync and async event handlers
    - Event filtering and transformation
    - Handler priorities
    - Error isolation
    - Event history
    - Wildcard listeners
    """
    
    def __init__(
        self,
        name: str = "default",
        max_history_size: int = 1000,
        enable_async: bool = True
    ):
        self.name = name
        self.max_history_size = max_history_size
        self.enable_async = enable_async
        
        # Handler storage: event_type -> priority -> list of handlers
        self._handlers: Dict[str, Dict[int, List[Tuple[str, EventHandler]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Wildcard handlers that listen to all events
        self._wildcard_handlers: Dict[int, List[Tuple[str, EventHandler]]] = defaultdict(list)
        
        # Event filters
        self._filters: List[Tuple[str, EventFilter]] = []
        
        # Event transformers
        self._transformers: List[Tuple[str, EventTransformer]] = []
        
        # Event history
        self._history: Deque[Tuple[Event, EventContext]] = deque(maxlen=max_history_size)
        self._history_enabled = True
        
        # Metrics
        self._metrics = {
            'events_emitted': 0,
            'events_handled': 0,
            'errors_caught': 0,
            'async_handlers_run': 0
        }
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Async event loop for async handlers
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        if enable_async:
            self._setup_async_loop()
        
        self.logger = logging.getLogger(f"{__name__}.EventEmitter.{name}")
    
    def _setup_async_loop(self) -> None:
        """Setup async event loop in separate thread."""
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._async_loop = loop
            loop.run_forever()
        
        self._async_thread = threading.Thread(
            target=run_loop,
            daemon=True,
            name=f"EventEmitter-{self.name}-async"
        )
        self._async_thread.start()
        
        # Wait for loop to be ready
        while self._async_loop is None:
            time.sleep(0.01)
    
    def on(
        self,
        event_type: Union[EventType, str],
        handler: EventHandler,
        priority: int = 0,
        handler_name: Optional[str] = None
    ) -> str:
        """
        Register an event handler.
        
        Args:
            event_type: Type of event to handle (or "*" for all events)
            handler: Function to handle the event
            priority: Handler priority (higher = earlier execution)
            handler_name: Optional name for the handler
            
        Returns:
            Handler ID for removal
        """
        with self._lock:
            handler_id = handler_name or f"{event_type}_{uuid.uuid4().hex[:8]}"
            
            if event_type == "*":
                self._wildcard_handlers[priority].append((handler_id, handler))
            else:
                event_key = event_type.value if isinstance(event_type, EventType) else event_type
                self._handlers[event_key][priority].append((handler_id, handler))
            
            self.logger.debug(f"Registered handler {handler_id} for {event_type} at priority {priority}")
            return handler_id
    
    def off(self, event_type: Union[EventType, str], handler_id: str) -> bool:
        """
        Remove an event handler.
        
        Args:
            event_type: Type of event handler was registered for
            handler_id: Handler ID returned by on()
            
        Returns:
            True if handler was removed
        """
        with self._lock:
            removed = False
            
            if event_type == "*":
                for priority_handlers in self._wildcard_handlers.values():
                    for i, (hid, _) in enumerate(priority_handlers):
                        if hid == handler_id:
                            priority_handlers.pop(i)
                            removed = True
                            break
            else:
                event_key = event_type.value if isinstance(event_type, EventType) else event_type
                if event_key in self._handlers:
                    for priority_handlers in self._handlers[event_key].values():
                        for i, (hid, _) in enumerate(priority_handlers):
                            if hid == handler_id:
                                priority_handlers.pop(i)
                                removed = True
                                break
            
            if removed:
                self.logger.debug(f"Removed handler {handler_id} for {event_type}")
            
            return removed
    
    def once(
        self,
        event_type: Union[EventType, str],
        handler: EventHandler,
        priority: int = 0
    ) -> str:
        """
        Register a one-time event handler.
        
        Args:
            event_type: Type of event to handle
            handler: Function to handle the event
            priority: Handler priority
            
        Returns:
            Handler ID
        """
        handler_id = f"once_{uuid.uuid4().hex[:8]}"
        
        def once_wrapper(context: EventContext, *args, **kwargs):
            try:
                result = handler(context, *args, **kwargs)
                return result
            finally:
                self.off(event_type, handler_id)
        
        return self.on(event_type, once_wrapper, priority, handler_id)
    
    def add_filter(self, filter_func: EventFilter, name: Optional[str] = None) -> str:
        """
        Add an event filter.
        
        Args:
            filter_func: Function that returns True to allow event
            name: Optional name for the filter
            
        Returns:
            Filter ID
        """
        with self._lock:
            filter_id = name or f"filter_{uuid.uuid4().hex[:8]}"
            self._filters.append((filter_id, filter_func))
            return filter_id
    
    def remove_filter(self, filter_id: str) -> bool:
        """Remove an event filter."""
        with self._lock:
            for i, (fid, _) in enumerate(self._filters):
                if fid == filter_id:
                    self._filters.pop(i)
                    return True
            return False
    
    def add_transformer(self, transformer: EventTransformer, name: Optional[str] = None) -> str:
        """
        Add an event transformer.
        
        Args:
            transformer: Function that transforms events
            name: Optional name for the transformer
            
        Returns:
            Transformer ID
        """
        with self._lock:
            transformer_id = name or f"transformer_{uuid.uuid4().hex[:8]}"
            self._transformers.append((transformer_id, transformer))
            return transformer_id
    
    def remove_transformer(self, transformer_id: str) -> bool:
        """Remove an event transformer."""
        with self._lock:
            for i, (tid, _) in enumerate(self._transformers):
                if tid == transformer_id:
                    self._transformers.pop(i)
                    return True
            return False
    
    def emit(self, event: Event, **context_kwargs) -> EventContext:
        """
        Emit an event.
        
        Args:
            event: Event to emit
            **context_kwargs: Additional context parameters
            
        Returns:
            EventContext with results
        """
        with self._lock:
            self._metrics['events_emitted'] += 1
            
            # Apply filters
            for filter_id, filter_func in self._filters:
                try:
                    if not filter_func(event):
                        self.logger.debug(f"Event {event.metadata.event_id} filtered by {filter_id}")
                        context = EventContext(event, self.name)
                        context.stop_propagation()
                        return context
                except Exception as e:
                    self.logger.error(f"Error in filter {filter_id}: {e}")
            
            # Apply transformers
            for transformer_id, transformer in self._transformers:
                try:
                    transformed = transformer(event)
                    if transformed is not None:
                        event = transformed
                except Exception as e:
                    self.logger.error(f"Error in transformer {transformer_id}: {e}")
            
            # Create context
            context = EventContext(event, self.name, **context_kwargs)
            
            # Store in history
            if self._history_enabled:
                self._history.append((event, context))
            
            # Get all applicable handlers
            handlers = self._get_handlers_for_event(event)
            
            # Execute handlers
            for handler_id, handler in handlers:
                if context.propagation_stopped:
                    break
                
                try:
                    if asyncio.iscoroutinefunction(handler):
                        self._run_async_handler(handler_id, handler, context)
                    else:
                        handler(context)
                        context.mark_handled(handler_id)
                    
                    self._metrics['events_handled'] += 1
                    
                except Exception as e:
                    self._metrics['errors_caught'] += 1
                    self.logger.error(f"Error in handler {handler_id}: {e}", exc_info=True)
                    context.set_response('error', str(e))
            
            # Complete context
            context.complete()
            
            # Emit any triggered events
            for triggered_event in context.triggered_events:
                self.emit(triggered_event)
            
            return context
    
    def _get_handlers_for_event(self, event: Event) -> List[Tuple[str, EventHandler]]:
        """Get all handlers for an event, sorted by priority."""
        handlers = []
        
        # Get specific handlers
        event_key = event.type.value if isinstance(event.type, EventType) else str(event.type)
        if event_key in self._handlers:
            for priority in sorted(self._handlers[event_key].keys(), reverse=True):
                handlers.extend(self._handlers[event_key][priority])
        
        # Add wildcard handlers
        for priority in sorted(self._wildcard_handlers.keys(), reverse=True):
            handlers.extend(self._wildcard_handlers[priority])
        
        return handlers
    
    def _run_async_handler(self, handler_id: str, handler: Callable, context: EventContext) -> None:
        """Run an async handler in the event loop."""
        if not self._async_loop:
            self.logger.warning(f"Async loop not available for handler {handler_id}")
            return
        
        async def run():
            try:
                await handler(context)
                context.mark_handled(handler_id)
                self._metrics['async_handlers_run'] += 1
            except Exception as e:
                self._metrics['errors_caught'] += 1
                self.logger.error(f"Error in async handler {handler_id}: {e}", exc_info=True)
                context.set_response('error', str(e))
        
        asyncio.run_coroutine_threadsafe(run(), self._async_loop)
    
    def emit_async(self, event: Event, **context_kwargs) -> asyncio.Future:
        """
        Emit an event asynchronously.
        
        Args:
            event: Event to emit
            **context_kwargs: Additional context parameters
            
        Returns:
            Future that resolves to EventContext
        """
        if not self._async_loop:
            raise RuntimeError("Async support not enabled")
        
        future = asyncio.Future()
        
        def emit_in_thread():
            try:
                context = self.emit(event, **context_kwargs)
                self._async_loop.call_soon_threadsafe(future.set_result, context)
            except Exception as e:
                self._async_loop.call_soon_threadsafe(future.set_exception, e)
        
        threading.Thread(target=emit_in_thread, daemon=True).start()
        return future
    
    def get_history(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        limit: Optional[int] = None
    ) -> List[Tuple[Event, EventContext]]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of events to return
            
        Returns:
            List of (event, context) tuples
        """
        with self._lock:
            history = list(self._history)
            
            if event_type:
                event_key = event_type.value if isinstance(event_type, EventType) else event_type
                history = [
                    (e, c) for e, c in history
                    if (e.type.value if isinstance(e.type, EventType) else str(e.type)) == event_key
                ]
            
            if limit:
                history = history[-limit:]
            
            return history
    
    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._history.clear()
    
    def enable_history(self, enabled: bool) -> None:
        """Enable or disable history recording."""
        self._history_enabled = enabled
    
    def get_metrics(self) -> Dict[str, int]:
        """Get event emitter metrics."""
        with self._lock:
            return self._metrics.copy()
    
    def reset_metrics(self) -> None:
        """Reset metrics."""
        with self._lock:
            for key in self._metrics:
                self._metrics[key] = 0
    
    def shutdown(self) -> None:
        """Shutdown the event emitter."""
        if self._async_loop:
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            if self._async_thread:
                self._async_thread.join(timeout=5.0)


class GlobalEventBus:
    """
    Global event bus for system-wide event handling.
    
    Provides a centralized event system with namespaced emitters.
    """
    
    def __init__(self):
        self._emitters: Dict[str, EventEmitter] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.GlobalEventBus")
    
    def get_emitter(self, namespace: str = "default") -> EventEmitter:
        """Get or create an event emitter for a namespace."""
        with self._lock:
            if namespace not in self._emitters:
                self._emitters[namespace] = EventEmitter(name=namespace)
                self.logger.debug(f"Created emitter for namespace: {namespace}")
            return self._emitters[namespace]
    
    def emit(self, event: Event, namespace: str = "default", **context_kwargs) -> EventContext:
        """Emit an event to a specific namespace."""
        emitter = self.get_emitter(namespace)
        return emitter.emit(event, **context_kwargs)
    
    def on(
        self,
        event_type: Union[EventType, str],
        handler: EventHandler,
        namespace: str = "default",
        **kwargs
    ) -> str:
        """Register a handler in a specific namespace."""
        emitter = self.get_emitter(namespace)
        return emitter.on(event_type, handler, **kwargs)
    
    def off(self, event_type: Union[EventType, str], handler_id: str, namespace: str = "default") -> bool:
        """Remove a handler from a specific namespace."""
        emitter = self.get_emitter(namespace)
        return emitter.off(event_type, handler_id)
    
    def shutdown_all(self) -> None:
        """Shutdown all emitters."""
        with self._lock:
            for emitter in self._emitters.values():
                emitter.shutdown()
            self._emitters.clear()


# Global event bus instance
global_event_bus = GlobalEventBus()


# Helper functions
def create_event(
    event_type: EventType,
    data: Dict[str, Any],
    **metadata_kwargs
) -> Event:
    """Create an event with metadata."""
    metadata = EventMetadata(**metadata_kwargs)
    return Event(type=event_type, data=data, metadata=metadata)


def create_reducer_event(
    reducer_name: str,
    status: str = "pending",
    **kwargs
) -> ReducerEvent:
    """Create a reducer event."""
    return ReducerEvent(
        type=EventType.REDUCER_CALLED,
        reducer_name=reducer_name,
        status=status,
        **kwargs
    )


def create_table_event(
    table_name: str,
    operation: str,
    row_data: Any,
    **kwargs
) -> TableEvent:
    """Create a table event."""
    event_type_map = {
        'insert': EventType.TABLE_ROW_INSERT,
        'update': EventType.TABLE_ROW_UPDATE,
        'delete': EventType.TABLE_ROW_DELETE
    }
    
    event_type = event_type_map.get(operation, EventType.CUSTOM)
    
    return TableEvent(
        type=event_type,
        table_name=table_name,
        operation=operation,
        row_data=row_data,
        **kwargs
    ) 