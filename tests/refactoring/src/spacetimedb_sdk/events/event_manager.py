"""
Unified Event Manager for SpacetimeDB SDK

This module provides a high-performance event manager that consolidates
multiple previous event systems.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field

from .core_events import (
    EventType, EventContext, EventPriority, UniversalEventHandler,
    HandlerInfo, is_async_handler, get_handler_name
)


@dataclass
class EventManagerConfig:
    """Configuration for the unified event manager."""
    max_handlers_per_type: int = 100
    max_pending_events: int = 10000
    enable_batching: bool = True
    batch_size: int = 100
    batch_timeout: float = 0.1
    enable_async: bool = True
    max_worker_threads: int = 4


@dataclass
class EventMetrics:
    """Event manager metrics."""
    events_emitted: int = 0
    events_processed: int = 0
    handlers_executed: int = 0
    errors_encountered: int = 0
    total_processing_time: float = 0.0
    start_time: float = field(default_factory=time.time)
    
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


@dataclass
class HandlerRegistration:
    """Handler registration information."""
    handler: UniversalEventHandler
    event_type: EventType
    priority: EventPriority
    registration_time: float
    call_count: int = 0


class UnifiedEventManager:
    """
    Unified event manager that consolidates multiple previous event systems.
    
    Features:
    - High-performance event processing
    - Async and sync handler support
    - Priority-based execution
    - Comprehensive metrics
    - Thread-safe operations
    """
    
    def __init__(self, config: Optional[EventManagerConfig] = None):
        """Initialize the unified event manager."""
        self.config = config or EventManagerConfig()
        self.logger = logging.getLogger(__name__)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Handler storage
        self._handlers: Dict[EventType, List[HandlerRegistration]] = defaultdict(list)
        self._handler_info: Dict[str, HandlerInfo] = {}
        
        # Event processing
        self._pending_events: deque = deque()
        self._processing = False
        self._shutdown = False
        
        # Metrics
        self.metrics = EventMetrics()
        
        # Async support
        self._event_loop = None
        if self.config.enable_async:
            try:
                self._event_loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop running
                pass
    
    def add_handler(
        self,
        event_type: EventType,
        handler: UniversalEventHandler,
        priority: EventPriority = EventPriority.NORMAL
    ) -> HandlerRegistration:
        """
        Add an event handler.
        
        Args:
            event_type: Type of events to handle
            handler: Handler function (sync or async)
            priority: Handler priority
            
        Returns:
            Handler registration information
        """
        with self._lock:
            # Check limits
            if len(self._handlers[event_type]) >= self.config.max_handlers_per_type:
                raise ValueError(f"Too many handlers for event type {event_type}")
            
            # Create registration
            registration = HandlerRegistration(
                handler=handler,
                event_type=event_type,
                priority=priority,
                registration_time=time.time()
            )
            
            # Store handler
            self._handlers[event_type].append(registration)
            
            # Sort by priority
            self._handlers[event_type].sort(key=lambda r: r.priority.value)
            
            # Create handler info
            handler_name = get_handler_name(handler)
            if handler_name not in self._handler_info:
                self._handler_info[handler_name] = HandlerInfo(
                    handler=handler,
                    priority=priority,
                    is_async=is_async_handler(handler),
                    registration_time=time.time()
                )
            
            self.logger.debug(f"Added handler {handler_name} for {event_type}")
            return registration
    
    def remove_handler(
        self,
        event_type: EventType,
        handler: UniversalEventHandler
    ) -> bool:
        """
        Remove an event handler.
        
        Args:
            event_type: Type of events the handler was handling
            handler: Handler function to remove
            
        Returns:
            True if handler was removed, False if not found
        """
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            for i, registration in enumerate(handlers):
                if registration.handler == handler:
                    del handlers[i]
                    
                    # Remove handler info if no more registrations
                    handler_name = get_handler_name(handler)
                    if not any(reg.handler == handler for regs in self._handlers.values() for reg in regs):
                        self._handler_info.pop(handler_name, None)
                    
                    self.logger.debug(f"Removed handler {handler_name} for {event_type}")
                    return True
            
            return False
    
    def emit(self, event_type: EventType, context: EventContext) -> None:
        """
        Emit an event synchronously.
        
        Args:
            event_type: Type of event to emit
            context: Event context data
        """
        with self._lock:
            self.metrics.events_emitted += 1
            
            # Get handlers for this event type
            handlers = self._handlers.get(event_type, [])
            if not handlers:
                return
            
            # Execute handlers
            start_time = time.time()
            
            for registration in handlers:
                try:
                    self._execute_handler(registration, context)
                except Exception as e:
                    self.metrics.errors_encountered += 1
                    self.logger.error(f"Error executing handler: {e}")
            
            # Update metrics
            processing_time = time.time() - start_time
            self.metrics.events_processed += 1
            self.metrics.total_processing_time += processing_time
    
    def emit_async(self, event_type: EventType, context: EventContext) -> None:
        """
        Emit an event asynchronously.
        
        Args:
            event_type: Type of event to emit
            context: Event context data
        """
        if self._event_loop and not self._event_loop.is_closed():
            self._event_loop.create_task(self._emit_async_impl(event_type, context))
        else:
            # Fall back to synchronous emission
            self.emit(event_type, context)
    
    async def _emit_async_impl(self, event_type: EventType, context: EventContext) -> None:
        """Internal async implementation of event emission."""
        self.metrics.events_emitted += 1
        
        # Get handlers for this event type
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return
        
        # Execute handlers
        start_time = time.time()
        
        for registration in handlers:
            try:
                await self._execute_handler_async(registration, context)
            except Exception as e:
                self.metrics.errors_encountered += 1
                self.logger.error(f"Error executing async handler: {e}")
        
        # Update metrics
        processing_time = time.time() - start_time
        self.metrics.events_processed += 1
        self.metrics.total_processing_time += processing_time
    
    def _execute_handler(self, registration: HandlerRegistration, context: EventContext) -> None:
        """Execute a handler synchronously."""
        start_time = time.time()
        
        try:
            if is_async_handler(registration.handler):
                # Async handler in sync context - skip or warn
                self.logger.warning(f"Skipping async handler in sync context: {get_handler_name(registration.handler)}")
                return
            
            registration.handler(context)
            registration.call_count += 1
            self.metrics.handlers_executed += 1
            
            # Update handler info
            handler_name = get_handler_name(registration.handler)
            if handler_name in self._handler_info:
                duration = time.time() - start_time
                self._handler_info[handler_name].record_call(duration)
        
        except Exception as e:
            # Update handler info with error
            handler_name = get_handler_name(registration.handler)
            if handler_name in self._handler_info:
                duration = time.time() - start_time
                self._handler_info[handler_name].record_call(duration, e)
            raise
    
    async def _execute_handler_async(self, registration: HandlerRegistration, context: EventContext) -> None:
        """Execute a handler asynchronously."""
        start_time = time.time()
        
        try:
            if is_async_handler(registration.handler):
                await registration.handler(context)
            else:
                # Run sync handler in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, registration.handler, context)
            
            registration.call_count += 1
            self.metrics.handlers_executed += 1
            
            # Update handler info
            handler_name = get_handler_name(registration.handler)
            if handler_name in self._handler_info:
                duration = time.time() - start_time
                self._handler_info[handler_name].record_call(duration)
        
        except Exception as e:
            # Update handler info with error
            handler_name = get_handler_name(registration.handler)
            if handler_name in self._handler_info:
                duration = time.time() - start_time
                self._handler_info[handler_name].record_call(duration, e)
            raise
    
    def get_handler_count(self, event_type: Optional[EventType] = None) -> int:
        """Get number of registered handlers."""
        with self._lock:
            if event_type is None:
                return sum(len(handlers) for handlers in self._handlers.values())
            return len(self._handlers.get(event_type, []))
    
    def get_event_types(self) -> Set[EventType]:
        """Get all event types with registered handlers."""
        with self._lock:
            return set(self._handlers.keys())
    
    def clear_handlers(self, event_type: Optional[EventType] = None) -> None:
        """Clear handlers for specific event type or all handlers."""
        with self._lock:
            if event_type is None:
                self._handlers.clear()
                self._handler_info.clear()
            else:
                self._handlers.pop(event_type, None)
                # Remove handler info for handlers no longer registered
                to_remove = []
                for name, info in self._handler_info.items():
                    if not any(reg.handler == info.handler for regs in self._handlers.values() for reg in regs):
                        to_remove.append(name)
                for name in to_remove:
                    self._handler_info.pop(name, None)
    
    def shutdown(self) -> None:
        """Shutdown the event manager."""
        with self._lock:
            self._shutdown = True
            self.clear_handlers()
            self.logger.info("Event manager shutdown")


# Global event manager instance
_global_event_manager: Optional[UnifiedEventManager] = None


def get_event_manager() -> UnifiedEventManager:
    """Get the global event manager instance."""
    global _global_event_manager
    if _global_event_manager is None:
        _global_event_manager = UnifiedEventManager()
    return _global_event_manager


def set_event_manager(manager: UnifiedEventManager) -> None:
    """Set the global event manager instance."""
    global _global_event_manager
    _global_event_manager = manager


def emit_event(event_type: EventType, context: EventContext) -> None:
    """Emit an event using the global event manager."""
    get_event_manager().emit(event_type, context)


def emit_event_async(event_type: EventType, context: EventContext) -> None:
    """Emit an event asynchronously using the global event manager."""
    get_event_manager().emit_async(event_type, context)


def subscribe_to_events(
    event_type: EventType,
    handler: UniversalEventHandler,
    priority: EventPriority = EventPriority.NORMAL
) -> HandlerRegistration:
    """Subscribe to events using the global event manager."""
    return get_event_manager().add_handler(event_type, handler, priority)