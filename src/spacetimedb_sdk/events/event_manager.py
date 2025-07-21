"""
Unified Event Manager for SpacetimeDB SDK

This module provides a consolidated event management system that unifies
all previous event managers into a single, powerful system.
"""

import asyncio
import logging
from ..utils.error_formatting import ErrorFormatter
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Set, Union, TypeVar
from weakref import WeakSet
from dataclasses import dataclass, field

from .core_events import Event, EventType, EventPriority, EventMetadata
from .event_context import EventContext
from .event_filters import EventFilter
from ..monitoring import get_global_monitor, monitor_performance

logger = logging.getLogger(__name__)

# Type definitions
EventHandler = Union[Callable[[EventContext], None], Callable[[EventContext], Any]]
AsyncEventHandler = Callable[[EventContext], Any]
HandlerFunction = Union[EventHandler, AsyncEventHandler]


@dataclass
class HandlerInfo:
    """Information about a registered event handler."""
    handler_id: str
    handler: HandlerFunction
    priority: int = 0
    handler_name: Optional[str] = None
    is_async: bool = False
    is_once: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class EventMetrics:
    """Metrics for event system performance."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all metrics."""
        self.events_published = 0
        self.events_processed = 0
        self.events_failed = 0
        self.events_filtered = 0
        self.handlers_executed = 0
        self.handler_errors = 0
        self.events_by_type: Dict[str, int] = defaultdict(int)
        self.events_by_priority: Dict[int, int] = defaultdict(int)
        self.processing_times: List[float] = []
        self.start_time = time.time()
    
    def record_published_event(self, event: Event):
        """Record an event being published."""
        self.events_published += 1
        self.events_by_type[event.event_type.value] += 1
        self.events_by_priority[event.priority.value] += 1
    
    def record_processed_event(self, event: Event, processing_time: float):
        """Record an event being processed."""
        self.events_processed += 1
        self.processing_times.append(processing_time)
        
        # Keep only last 1000 processing times
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]
    
    def record_failed_event(self, event: Event):
        """Record an event processing failure."""
        self.events_failed += 1
    
    def record_filtered_event(self, event: Event):
        """Record an event being filtered out."""
        self.events_filtered += 1
    
    def record_handler_execution(self, success: bool):
        """Record handler execution result."""
        self.handlers_executed += 1
        if not success:
            self.handler_errors += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        uptime = time.time() - self.start_time
        
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
            'events_filtered': self.events_filtered,
            'handlers_executed': self.handlers_executed,
            'handler_errors': self.handler_errors,
            'success_rate': (self.events_processed / max(1, self.events_published)) * 100,
            'handler_success_rate': ((self.handlers_executed - self.handler_errors) / max(1, self.handlers_executed)) * 100,
            'events_per_second': self.events_published / max(1, uptime),
            'events_by_type': dict(self.events_by_type),
            'events_by_priority': dict(self.events_by_priority),
            'avg_processing_time_ms': avg_processing_time * 1000,
            'max_processing_time_ms': max_processing_time * 1000
        }


class UnifiedEventManager:
    """
    Unified event manager that consolidates all previous event systems.
    
    This replaces:
    - SDKEventManager from event_manager.py
    - EventEmitter from event_system.py  
    - EnhancedEventManager from events/enhanced_event_system.py
    
    Supports context manager protocol for proper resource cleanup.
    """
    
    def __init__(
        self,
        name: str = "UnifiedEventManager",
        max_queue_size: int = 10000,
        max_worker_threads: int = 4,
        enable_metrics: bool = True,
        enable_history: bool = True,
        max_history_size: int = 1000,
        default_event_ttl: float = 300.0,
        enable_async: bool = True
    ):
        """Initialize the unified event manager."""
        self.name = name
        self.max_queue_size = max_queue_size
        self.max_worker_threads = max_worker_threads
        self.enable_metrics = enable_metrics
        self.enable_history = enable_history
        self.max_history_size = max_history_size
        self.default_event_ttl = default_event_ttl
        self.enable_async = enable_async
        
        # Handler storage: event_type -> priority -> list of handlers
        self._handlers: Dict[str, Dict[int, List[HandlerInfo]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Wildcard handlers that listen to all events
        self._wildcard_handlers: Dict[int, List[HandlerInfo]] = defaultdict(list)
        
        # Event processing queue
        self._event_queue: Optional[asyncio.Queue] = None
        self._priority_queue: deque = deque()
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._is_shutting_down = False
        
        # Event filters
        self._filters: List[EventFilter] = []
        
        # Event transformers
        self._transformers: List[Callable[[Event], Optional[Event]]] = []
        
        # Event history
        self._history: deque = deque(maxlen=max_history_size if enable_history else 0)
        
        # Metrics
        self._metrics = EventMetrics() if enable_metrics else None
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Thread pool for sync handlers
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        if enable_async:
            self._thread_pool = ThreadPoolExecutor(max_workers=max_worker_threads)
        
        # Async event loop for async handlers
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._owned_loop: Optional[asyncio.AbstractEventLoop] = None
        
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.logger.info(f"Unified event manager '{name}' initialized")
        
        # Start async processing if enabled
        if enable_async:
            self._start_async_processing()
    
    def _start_async_processing(self):
        """Start async event processing."""
        if self._is_shutting_down:
            return
            
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # Create and store reference to new event loop for proper cleanup
                self._owned_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._owned_loop)
                loop = self._owned_loop
                # Initialize the loop's socket infrastructure properly
                # by scheduling a no-op task to trigger internal setup
                loop.call_soon(lambda: None)
                self.logger.debug("Created new event loop for async processing")
            
            # Create shutdown event on the correct loop
            if self._shutdown_event is None:
                try:
                    # Create directly on the current loop
                    self._shutdown_event = asyncio.Event()
                except RuntimeError:
                    # If there's an issue, we'll create it later in the processing task
                    pass
            
            if self._event_queue is None:
                self._event_queue = asyncio.Queue(maxsize=self.max_queue_size)
            
            if self._processing_task is None or self._processing_task.done():
                self._processing_task = loop.create_task(self._process_events())
                
        except RuntimeError as e:
            # No event loop running, will start when one is available
            self.logger.debug(f"No event loop available, will start async processing later: {e}")
    
    
    async def _process_events(self):
        """Main event processing loop."""
        self.logger.info("Event processing started")
        
        # Create shutdown event if it doesn't exist
        if self._shutdown_event is None:
            try:
                self._shutdown_event = asyncio.Event()
            except Exception as e:
                self.logger.error(f"Failed to create shutdown event: {e}")
                return
        
        try:
            while not self._is_shutting_down and not self._shutdown_event.is_set():
                try:
                    # Check for shutdown before processing
                    if self._is_shutting_down:
                        break
                        
                    # Process priority events first
                    if self._priority_queue:
                        event = self._priority_queue.popleft()
                        await self._handle_event(event)
                        continue
                    
                    # Wait for regular events with timeout
                    try:
                        if self._event_queue:
                            event = await asyncio.wait_for(
                                self._event_queue.get(),
                                timeout=0.5  # Shorter timeout for more responsive shutdown
                            )
                            await self._handle_event(event)
                            self._event_queue.task_done()
                        else:
                            # If no queue, just sleep
                            await asyncio.sleep(0.5)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        # Task was cancelled, break out of loop
                        self.logger.debug("Event processing task cancelled")
                        break
                        
                except asyncio.CancelledError:
                    # Task was cancelled, break out of loop
                    self.logger.debug("Event processing task cancelled")
                    break
                except Exception as e:
                    if not self._is_shutting_down:
                        self.logger.error(ErrorFormatter.format_event_error("event processing loop", e), exc_info=True)
                    await asyncio.sleep(0.1)
                    
        except asyncio.CancelledError:
            self.logger.debug("Event processing task cancelled during shutdown")
        except Exception as e:
            if not self._is_shutting_down:
                self.logger.error(f"Event processing loop failed: {e}")
        finally:
            self.logger.info("Event processing stopped")
    
    async def _handle_event(self, event: Event):
        """Handle a single event."""
        start_time = time.time()
        
        try:
            # Create event context
            context = EventContext(event, source_component=self.name)
            
            # Apply transformers
            processed_event = event
            for transformer in self._transformers:
                try:
                    transformed = transformer(processed_event)
                    if transformed is not None:
                        processed_event = transformed
                        context = EventContext(processed_event, source_component=self.name)
                    else:
                        self.logger.debug(f"Event {event.metadata.event_id} transformed to None")
                        return
                except Exception as e:
                    self.logger.error(ErrorFormatter.format_event_error("transformer", e))
            
            # Apply filters
            for event_filter in self._filters:
                try:
                    if not event_filter.matches(processed_event):
                        self.logger.debug(f"Event {event.metadata.event_id} filtered out")
                        if self._metrics:
                            self._metrics.record_filtered_event(processed_event)
                        return
                except Exception as e:
                    self.logger.error(ErrorFormatter.format_event_error("filter", e))
            
            # Check if event has expired
            if processed_event.is_expired(self.default_event_ttl):
                self.logger.warning(f"Event {event.metadata.event_id} expired, discarding")
                return
            
            # Store in history
            if self.enable_history:
                self._history.append((processed_event, context))
            
            # Get all applicable handlers
            handlers = self._get_handlers_for_event(processed_event)
            
            # Execute handlers
            await self._execute_handlers(handlers, context)
            
            # Complete context
            context.complete()
            
            # Record metrics
            if self._metrics:
                processing_time = time.time() - start_time
                self._metrics.record_processed_event(processed_event, processing_time)
            
            # Emit any triggered events
            for triggered_event in context.triggered_events:
                await self.emit_async(triggered_event)
                
        except Exception as e:
            self.logger.error(ErrorFormatter.format_event_error(f"handling event {event.metadata.event_id}", e), exc_info=True)
            if self._metrics:
                self._metrics.record_failed_event(event)
    
    def _get_handlers_for_event(self, event: Event) -> List[HandlerInfo]:
        """Get all handlers for an event, sorted by priority."""
        handlers = []
        
        with self._lock:
            # Get specific handlers
            event_key = event.event_type.value
            if event_key in self._handlers:
                for priority in sorted(self._handlers[event_key].keys(), reverse=True):
                    handlers.extend(self._handlers[event_key][priority])
            
            # Add wildcard handlers
            for priority in sorted(self._wildcard_handlers.keys(), reverse=True):
                handlers.extend(self._wildcard_handlers[priority])
        
        return handlers
    
    async def _execute_handlers(self, handlers: List[HandlerInfo], context: EventContext):
        """Execute all handlers for an event."""
        for handler_info in handlers:
            if context.propagation_stopped:
                break
            
            try:
                if handler_info.is_async or asyncio.iscoroutinefunction(handler_info.handler):
                    await handler_info.handler(context)
                else:
                    # Run sync handler in thread pool
                    if self._thread_pool and not self._is_shutting_down:
                        try:
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(
                                self._thread_pool,
                                handler_info.handler,
                                context
                            )
                        except RuntimeError:
                            # No running loop or loop issues, fall back to direct execution
                            try:
                                handler_info.handler(context)
                            except Exception as e:
                                self.logger.error(f"Error executing sync handler directly: {e}")
                                raise
                    else:
                        handler_info.handler(context)
                
                context.mark_handled(handler_info.handler_id)
                
                if self._metrics:
                    self._metrics.record_handler_execution(True)
                
                # Remove one-time handlers
                if handler_info.is_once:
                    self._remove_handler_info(handler_info)
                
            except Exception as e:
                self.logger.error(ErrorFormatter.format_event_error(f"handler {handler_info.handler_id}", e), exc_info=True)
                context.set_response('error', str(e))
                
                if self._metrics:
                    self._metrics.record_handler_execution(False)
    
    def _remove_handler_info(self, handler_info: HandlerInfo):
        """Remove a specific handler info object."""
        with self._lock:
            # Remove from specific handlers
            for event_type_handlers in self._handlers.values():
                for priority_handlers in event_type_handlers.values():
                    if handler_info in priority_handlers:
                        priority_handlers.remove(handler_info)
                        return
            
            # Remove from wildcard handlers
            for priority_handlers in self._wildcard_handlers.values():
                if handler_info in priority_handlers:
                    priority_handlers.remove(handler_info)
                    return
    
    # Public API methods
    
    def on(
        self,
        event_type: Union[EventType, str],
        handler: HandlerFunction,
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
            is_async = asyncio.iscoroutinefunction(handler)
            
            handler_info = HandlerInfo(
                handler_id=handler_id,
                handler=handler,
                priority=priority,
                handler_name=handler_name,
                is_async=is_async,
                is_once=False
            )
            
            if event_type == "*":
                self._wildcard_handlers[priority].append(handler_info)
            else:
                event_key = event_type.value if isinstance(event_type, EventType) else event_type
                self._handlers[event_key][priority].append(handler_info)
            
            self.logger.debug(f"Registered handler {handler_id} for {event_type} at priority {priority}")
            return handler_id
    
    def subscribe(
        self,
        event_type: Union[EventType, str],
        handler: HandlerFunction,
        priority: int = 0
    ) -> str:
        """
        Subscribe to events (alias for on method).
        
        Args:
            event_type: Type of event to handle
            handler: Function to handle the event
            priority: Handler priority
            
        Returns:
            Handler ID
        """
        return self.on(event_type, handler, priority)
    
    def once(
        self,
        event_type: Union[EventType, str],
        handler: HandlerFunction,
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
        with self._lock:
            handler_id = f"once_{uuid.uuid4().hex[:8]}"
            is_async = asyncio.iscoroutinefunction(handler)
            
            handler_info = HandlerInfo(
                handler_id=handler_id,
                handler=handler,
                priority=priority,
                is_async=is_async,
                is_once=True
            )
            
            if event_type == "*":
                self._wildcard_handlers[priority].append(handler_info)
            else:
                event_key = event_type.value if isinstance(event_type, EventType) else event_type
                self._handlers[event_key][priority].append(handler_info)
            
            self.logger.debug(f"Registered one-time handler {handler_id} for {event_type}")
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
                    for handler_info in priority_handlers[:]:  # Copy to avoid modification during iteration
                        if handler_info.handler_id == handler_id:
                            priority_handlers.remove(handler_info)
                            removed = True
                            break
            else:
                event_key = event_type.value if isinstance(event_type, EventType) else event_type
                if event_key in self._handlers:
                    for priority_handlers in self._handlers[event_key].values():
                        for handler_info in priority_handlers[:]:
                            if handler_info.handler_id == handler_id:
                                priority_handlers.remove(handler_info)
                                removed = True
                                break
            
            if removed:
                self.logger.debug(f"Removed handler {handler_id} for {event_type}")
            
            return removed
    
    @monitor_performance("event_emit")
    def emit(self, event: Event, **context_kwargs) -> EventContext:
        """
        Emit an event synchronously.
        
        Args:
            event: Event to emit
            **context_kwargs: Additional context parameters
            
        Returns:
            EventContext with results
        """
        start_time = time.time()
        
        # Record published event
        if self._metrics:
            self._metrics.record_published_event(event)
        
        # For sync emit, we create context and execute handlers directly
        context = EventContext(event, self.name, **context_kwargs)
        
        # Apply transformers
        processed_event = event
        for transformer in self._transformers:
            try:
                transformed = transformer(processed_event)
                if transformed is not None:
                    processed_event = transformed
                    context = EventContext(processed_event, self.name, **context_kwargs)
                else:
                    context.stop_propagation()
                    return context
            except Exception as e:
                self.logger.error(f"Error in transformer: {e}")
        
        # Apply filters
        for event_filter in self._filters:
            try:
                if not event_filter.matches(processed_event):
                    if self._metrics:
                        self._metrics.record_filtered_event(processed_event)
                    context.stop_propagation()
                    return context
            except Exception as e:
                self.logger.error(f"Error in filter: {e}")
        
        # Store in history
        if self.enable_history:
            self._history.append((processed_event, context))
        
        # Get and execute handlers synchronously
        handlers = self._get_handlers_for_event(processed_event)
        
        for handler_info in handlers:
            if context.propagation_stopped:
                break
            
            try:
                if handler_info.is_async or asyncio.iscoroutinefunction(handler_info.handler):
                    self.logger.warning(f"Skipping async handler {handler_info.handler_id} in sync emit")
                    continue
                
                handler_info.handler(context)
                context.mark_handled(handler_info.handler_id)
                
                if self._metrics:
                    self._metrics.record_handler_execution(True)
                
                # Remove one-time handlers
                if handler_info.is_once:
                    self._remove_handler_info(handler_info)
                
            except Exception as e:
                self.logger.error(ErrorFormatter.format_event_error(f"handler {handler_info.handler_id}", e), exc_info=True)
                context.set_response('error', str(e))
                
                if self._metrics:
                    self._metrics.record_handler_execution(False)
        
        context.complete()
        
        # Record event processing performance
        processing_time = time.time() - start_time
        monitor = get_global_monitor()
        monitor.record_event_processing(processing_time, event.event_type, success=True)
        
        return context
    
    async def emit_async(self, event: Event, priority: bool = False) -> bool:
        """
        Emit an event asynchronously.
        
        Args:
            event: Event to emit
            priority: Whether to process with high priority
            
        Returns:
            True if event was queued successfully
        """
        try:
            # Record published event
            if self._metrics:
                self._metrics.record_published_event(event)
            
            # Add to appropriate queue
            if priority or event.priority.value >= EventPriority.CRITICAL.value:
                self._priority_queue.append(event)
            else:
                if self._event_queue:
                    try:
                        self._event_queue.put_nowait(event)
                    except asyncio.QueueFull:
                        self.logger.warning(f"Event queue full, dropping event {event.metadata.event_id}")
                        return False
                else:
                    # Queue not initialized, handle immediately
                    await self._handle_event(event)
            
            return True
            
        except Exception as e:
            self.logger.error(ErrorFormatter.format_event_error(f"emitting event {event.metadata.event_id}", e))
            return False
    
    def add_filter(self, event_filter: EventFilter) -> None:
        """Add a global event filter."""
        self._filters.append(event_filter)
    
    def remove_filter(self, event_filter: EventFilter) -> bool:
        """Remove a global event filter."""
        try:
            self._filters.remove(event_filter)
            return True
        except ValueError:
            return False
    
    def add_transformer(self, transformer: Callable[[Event], Optional[Event]]) -> None:
        """Add an event transformer."""
        self._transformers.append(transformer)
    
    def remove_transformer(self, transformer: Callable[[Event], Optional[Event]]) -> bool:
        """Remove an event transformer."""
        try:
            self._transformers.remove(transformer)
            return True
        except ValueError:
            return False
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get event system metrics."""
        if self._metrics:
            return self._metrics.get_metrics()
        return None
    
    def reset_metrics(self) -> None:
        """Reset metrics."""
        if self._metrics:
            self._metrics.reset()
    
    def get_history(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        limit: Optional[int] = None
    ) -> List[tuple]:
        """Get event history."""
        if not self.enable_history:
            return []
        
        history = list(self._history)
        
        if event_type:
            event_key = event_type.value if isinstance(event_type, EventType) else event_type
            history = [
                (e, c) for e, c in history
                if e.type.value == event_key
            ]
        
        if limit:
            history = history[-limit:]
        
        return history
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
    
    def clear_all_handlers(self) -> None:
        """Clear all event handlers."""
        with self._lock:
            handler_count = sum(
                len(priority_handlers)
                for event_handlers in self._handlers.values()
                for priority_handlers in event_handlers.values()
            )
            wildcard_count = sum(len(priority_handlers) for priority_handlers in self._wildcard_handlers.values())
            
            self._handlers.clear()
            self._wildcard_handlers.clear()
            
            self.logger.info(f"Cleared {handler_count} specific handlers and {wildcard_count} wildcard handlers")
    
    async def shutdown(self) -> None:
        """Shutdown the event manager gracefully."""
        if self._is_shutting_down:
            return
            
        self.logger.info("Shutting down unified event manager...")
        self._is_shutting_down = True
        
        try:
            # Signal shutdown
            if self._shutdown_event:
                self._shutdown_event.set()
            
            # Wait for processing to complete
            if self._processing_task and not self._processing_task.done():
                try:
                    # Give the task a chance to finish gracefully
                    await asyncio.wait_for(self._processing_task, timeout=2.0)
                except asyncio.TimeoutError:
                    self.logger.warning("Event processing task didn't complete within timeout, cancelling...")
                    self._processing_task.cancel()
                    try:
                        await self._processing_task
                    except asyncio.CancelledError:
                        pass  # Expected when cancelling
                except Exception as e:
                    self.logger.debug(f"Error during task shutdown: {e}")
            
            # Shutdown thread pool
            if self._thread_pool:
                self._thread_pool.shutdown(wait=True)
                self._thread_pool = None
            
            # Clean up event loop resources
            self._cleanup_event_loop()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            self.logger.info("Unified event manager shutdown complete")
    
    def _cleanup_event_loop(self):
        """Clean up event loop resources."""
        if self._owned_loop and not self._owned_loop.is_closed():
            try:
                # Get all tasks on this loop
                all_tasks = []
                try:
                    all_tasks = [task for task in asyncio.all_tasks(self._owned_loop) if not task.done()]
                except RuntimeError:
                    # Loop might be closed, which is fine
                    pass
                
                # Cancel remaining tasks
                for task in all_tasks:
                    if not task.done():
                        task.cancel()
                
                # Try to run the loop briefly to allow cancelled tasks to finish
                if not self._owned_loop.is_closed() and all_tasks:
                    try:
                        # Run the loop for a very short time to process cancellations
                        self._owned_loop.run_until_complete(asyncio.sleep(0.001))
                    except Exception:
                        # If running fails, that's ok
                        pass
                
                # Close the loop
                if not self._owned_loop.is_closed():
                    self._owned_loop.close()
                    self.logger.debug("Closed owned event loop")
                    
            except Exception as e:
                self.logger.warning(f"Error during event loop cleanup: {e}")
            finally:
                self._owned_loop = None
        
        # Cancel processing task if it's from a different loop
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
        
        # Reset other loop-related state
        self._event_queue = None
        self._processing_task = None
        self._shutdown_event = None
    
    def __del__(self):
        """Destructor to ensure proper cleanup."""
        if not self._is_shutting_down:
            try:
                # Try to clean up synchronously for destructor
                if self._thread_pool:
                    self._thread_pool.shutdown(wait=False)
                
                # Cancel processing task if it exists
                if self._processing_task and not self._processing_task.done():
                    self._processing_task.cancel()
                
                # Clean up event loop
                self._cleanup_event_loop()
                
            except Exception as e:
                # Avoid raising exceptions in __del__
                if hasattr(self, 'logger'):
                    self.logger.debug(f"Error during cleanup in __del__: {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup."""
        await self.shutdown()
        return False
    
    def __enter__(self):
        """Sync context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        # For sync context manager, we need to handle shutdown differently
        try:
            # Try to get running loop and schedule shutdown
            try:
                loop = asyncio.get_running_loop()
                # Schedule shutdown as a task
                asyncio.create_task(self.shutdown())
            except RuntimeError:
                # No running loop, clean up synchronously
                self._is_shutting_down = True
                if self._thread_pool:
                    self._thread_pool.shutdown(wait=True)
                self._cleanup_event_loop()
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Error during sync context manager exit: {e}")
        return False


# Global event manager instance
_global_event_manager: Optional[UnifiedEventManager] = None
_event_manager_lock = threading.Lock()


def get_event_manager() -> UnifiedEventManager:
    """Get the global unified event manager instance."""
    global _global_event_manager
    
    with _event_manager_lock:
        if _global_event_manager is None:
            _global_event_manager = UnifiedEventManager()
        return _global_event_manager


def set_event_manager(manager: UnifiedEventManager) -> None:
    """Set the global unified event manager instance."""
    global _global_event_manager
    
    # Shutdown existing manager if it exists
    if _global_event_manager and not _global_event_manager._is_shutting_down:
        try:
            # Try to shutdown properly
            loop = asyncio.get_running_loop()
            asyncio.create_task(_global_event_manager.shutdown())
        except RuntimeError:
            # No loop running, clean up synchronously
            _global_event_manager._is_shutting_down = True
            if _global_event_manager._thread_pool:
                _global_event_manager._thread_pool.shutdown(wait=False)
            _global_event_manager._cleanup_event_loop()
    
    _global_event_manager = manager


async def shutdown_global_event_manager() -> None:
    """Shutdown the global event manager if it exists."""
    global _global_event_manager
    
    if _global_event_manager and not _global_event_manager._is_shutting_down:
        await _global_event_manager.shutdown()
        _global_event_manager = None


def cleanup_global_event_manager() -> None:
    """Cleanup the global event manager synchronously."""
    global _global_event_manager
    
    if _global_event_manager and not _global_event_manager._is_shutting_down:
        _global_event_manager._is_shutting_down = True
        if _global_event_manager._thread_pool:
            _global_event_manager._thread_pool.shutdown(wait=False)
        _global_event_manager._cleanup_event_loop()
        _global_event_manager = None


# Convenience functions
def emit_event(event: Event, **context_kwargs) -> EventContext:
    """Convenience function to emit an event synchronously."""
    manager = get_event_manager()
    return manager.emit(event, **context_kwargs)


async def emit_event_async(event: Event, priority: bool = False) -> bool:
    """Convenience function to emit an event asynchronously."""
    manager = get_event_manager()
    return await manager.emit_async(event, priority)


def subscribe_to_events(
    callback: HandlerFunction,
    event_types: Optional[Union[EventType, List[EventType], str]] = None,
    priority: int = 0,
    handler_name: Optional[str] = None
) -> str:
    """Convenience function to subscribe to events."""
    manager = get_event_manager()
    
    if event_types is None or event_types == "*":
        return manager.on("*", callback, priority, handler_name)
    elif isinstance(event_types, (EventType, str)):
        return manager.on(event_types, callback, priority, handler_name)
    else:
        # Multiple event types - register for each
        handler_ids = []
        for event_type in event_types:
            handler_id = manager.on(event_type, callback, priority, handler_name)
            handler_ids.append(handler_id)
        return ",".join(handler_ids)  # Return comma-separated IDs


def event_context(event: Event, **kwargs) -> EventContext:
    """Create an event context."""
    return EventContext(event, **kwargs)


def publish_event(event: Event, **context_kwargs) -> EventContext:
    """Publish an event (alias for emit_event)."""
    return emit_event(event, **context_kwargs)