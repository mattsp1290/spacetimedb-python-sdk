"""
Event Context Management

This module provides enhanced context management for events, including
context building, memory pooling, and lifecycle management.
"""

import time
import threading
from typing import Any, Dict, Optional, Type, Union, List
from collections import deque
from dataclasses import dataclass, field
from contextlib import contextmanager
import uuid

from .core_events import EventType, EventContext, EventMetadata


class ContextBuilder:
    """
    Builder pattern for creating event contexts with fluent API.
    
    Example:
        context = (ContextBuilder(EventType.CONNECTION_OPENED)
                  .source("websocket_client")
                  .data({"connection_id": "conn_123"})
                  .metadata(user_id="user_456")
                  .build())
    """
    
    def __init__(self, event_type: EventType):
        self.event_type = event_type
        self._source = "unknown"
        self._data = None
        self._metadata = {}
        self._correlation_id = None
        self._parent_context = None
        self._timestamp = None
    
    def source(self, source: str) -> 'ContextBuilder':
        """Set the event source."""
        self._source = source
        return self
    
    def data(self, data: Any) -> 'ContextBuilder':
        """Set the event data payload."""
        self._data = data
        return self
    
    def metadata(self, **metadata) -> 'ContextBuilder':
        """Set event metadata."""
        self._metadata.update(metadata)
        return self
    
    def correlation_id(self, correlation_id: str) -> 'ContextBuilder':
        """Set the correlation ID."""
        self._correlation_id = correlation_id
        return self
    
    def parent(self, parent_context: EventContext) -> 'ContextBuilder':
        """Set the parent context."""
        self._parent_context = parent_context
        return self
    
    def timestamp(self, timestamp: float) -> 'ContextBuilder':
        """Set the timestamp."""
        self._timestamp = timestamp
        return self
    
    def build(self) -> EventContext:
        """Build the event context."""
        return EventContext(
            event_type=self.event_type,
            source=self._source,
            timestamp=self._timestamp or time.time(),
            metadata=self._metadata,
            correlation_id=self._correlation_id,
            data=self._data,
            parent_context=self._parent_context
        )


class ContextPool:
    """
    Memory pool for event contexts to reduce garbage collection overhead.
    
    This pool maintains a collection of reusable EventContext objects
    to improve performance by reducing object allocation and deallocation.
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.pool = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.created_count = 0
        self.reused_count = 0
        self.peak_usage = 0
    
    def acquire(self) -> EventContext:
        """Acquire a context from the pool or create a new one."""
        with self.lock:
            if self.pool:
                context = self.pool.popleft()
                self.reused_count += 1
                return context
            else:
                context = EventContext(
                    event_type=EventType.SYSTEM_READY,  # Placeholder
                    source="pool",
                    timestamp=0.0
                )
                self.created_count += 1
                return context
    
    def release(self, context: EventContext):
        """Release a context back to the pool."""
        with self.lock:
            if len(self.pool) < self.max_size:
                # Reset context for reuse
                context.event_type = EventType.SYSTEM_READY
                context.source = "pool"
                context.timestamp = 0.0
                context.metadata.clear()
                context.correlation_id = None
                context.data = None
                context.parent_context = None
                
                self.pool.append(context)
                self.peak_usage = max(self.peak_usage, len(self.pool))
    
    def configure_context(
        self,
        context: EventContext,
        event_type: EventType,
        source: str,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        data: Optional[Any] = None,
        parent_context: Optional[EventContext] = None
    ) -> EventContext:
        """Configure a pooled context with new values."""
        context.event_type = event_type
        context.source = source
        context.timestamp = timestamp or time.time()
        context.metadata = metadata or {}
        context.correlation_id = correlation_id or str(uuid.uuid4())
        context.data = data
        context.parent_context = parent_context
        return context
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self.lock:
            return {
                'pool_size': len(self.pool),
                'max_size': self.max_size,
                'created_count': self.created_count,
                'reused_count': self.reused_count,
                'peak_usage': self.peak_usage,
                'reuse_rate': self.reused_count / max(self.created_count + self.reused_count, 1)
            }
    
    def clear(self):
        """Clear the pool."""
        with self.lock:
            self.pool.clear()
    
    @contextmanager
    def context(self, event_type: EventType, source: str, **kwargs):
        """Context manager for automatic context acquisition and release."""
        context = self.acquire()
        try:
            yield self.configure_context(context, event_type, source, **kwargs)
        finally:
            self.release(context)


class EventContextManager:
    """
    Advanced context manager for event processing with lifecycle management.
    
    This class provides:
    - Context creation and lifecycle management
    - Memory pooling for performance
    - Context chaining and correlation
    - Automatic cleanup and resource management
    - Context filtering and routing
    """
    
    def __init__(self, pool_size: int = 1000):
        self.context_pool = ContextPool(pool_size)
        self.active_contexts: Dict[str, EventContext] = {}
        self.context_chains: Dict[str, List[str]] = {}
        self.lock = threading.RLock()
        
        # Statistics
        self.contexts_created = 0
        self.contexts_processed = 0
        self.contexts_failed = 0
        self.average_processing_time = 0.0
        self.processing_times = deque(maxlen=1000)
    
    def create_context(
        self,
        event_type: EventType,
        source: str,
        data: Optional[Any] = None,
        parent_context: Optional[EventContext] = None,
        use_pool: bool = True,
        **metadata
    ) -> EventContext:
        """
        Create a new event context.
        
        Args:
            event_type: Type of event
            source: Source component
            data: Optional event data
            parent_context: Optional parent context
            use_pool: Whether to use memory pool
            **metadata: Additional metadata
            
        Returns:
            New event context
        """
        with self.lock:
            if use_pool:
                context = self.context_pool.acquire()
                context = self.context_pool.configure_context(
                    context=context,
                    event_type=event_type,
                    source=source,
                    data=data,
                    parent_context=parent_context,
                    metadata=metadata
                )
            else:
                context = EventContext.create(
                    event_type=event_type,
                    source=source,
                    data=data,
                    **metadata
                )
                if parent_context:
                    context.parent_context = parent_context
            
            # Register active context
            self.active_contexts[context.correlation_id] = context
            
            # Build context chain
            if parent_context:
                parent_chain = self.context_chains.get(parent_context.correlation_id, [])
                self.context_chains[context.correlation_id] = parent_chain + [parent_context.correlation_id]
            
            self.contexts_created += 1
            return context
    
    def create_child_context(
        self,
        parent_context: EventContext,
        event_type: EventType,
        source: Optional[str] = None,
        data: Optional[Any] = None,
        **metadata
    ) -> EventContext:
        """Create a child context from a parent context."""
        return self.create_context(
            event_type=event_type,
            source=source or parent_context.source,
            data=data,
            parent_context=parent_context,
            **metadata
        )
    
    def create_correlated_context(
        self,
        correlation_id: str,
        event_type: EventType,
        source: str,
        data: Optional[Any] = None,
        **metadata
    ) -> EventContext:
        """Create a context with a specific correlation ID."""
        context = self.create_context(
            event_type=event_type,
            source=source,
            data=data,
            **metadata
        )
        context.correlation_id = correlation_id
        
        # Update active contexts with new correlation ID
        with self.lock:
            self.active_contexts[correlation_id] = context
        
        return context
    
    def get_context(self, correlation_id: str) -> Optional[EventContext]:
        """Get an active context by correlation ID."""
        with self.lock:
            return self.active_contexts.get(correlation_id)
    
    def get_context_chain(self, correlation_id: str) -> List[EventContext]:
        """Get the full context chain for a correlation ID."""
        with self.lock:
            chain_ids = self.context_chains.get(correlation_id, [])
            chain_contexts = []
            
            for chain_id in chain_ids:
                context = self.active_contexts.get(chain_id)
                if context:
                    chain_contexts.append(context)
            
            # Add the target context
            target_context = self.active_contexts.get(correlation_id)
            if target_context:
                chain_contexts.append(target_context)
            
            return chain_contexts
    
    def mark_processed(self, context: EventContext, processing_time: float):
        """Mark a context as processed."""
        with self.lock:
            self.contexts_processed += 1
            self.processing_times.append(processing_time)
            
            # Update average processing time
            if self.processing_times:
                self.average_processing_time = sum(self.processing_times) / len(self.processing_times)
    
    def mark_failed(self, context: EventContext, error: Exception):
        """Mark a context as failed."""
        with self.lock:
            self.contexts_failed += 1
            context.set_metadata('error', str(error))
            context.set_metadata('failed', True)
    
    def release_context(self, context: EventContext):
        """Release a context and return it to the pool."""
        with self.lock:
            # Remove from active contexts
            if context.correlation_id in self.active_contexts:
                del self.active_contexts[context.correlation_id]
            
            # Remove from context chains
            if context.correlation_id in self.context_chains:
                del self.context_chains[context.correlation_id]
            
            # Return to pool
            self.context_pool.release(context)
    
    def cleanup_expired_contexts(self, max_age: float = 3600.0):
        """Clean up contexts older than max_age seconds."""
        current_time = time.time()
        expired_contexts = []
        
        with self.lock:
            for correlation_id, context in self.active_contexts.items():
                if current_time - context.timestamp > max_age:
                    expired_contexts.append(correlation_id)
            
            for correlation_id in expired_contexts:
                context = self.active_contexts.pop(correlation_id, None)
                if context:
                    self.context_pool.release(context)
                
                # Clean up context chain
                self.context_chains.pop(correlation_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context manager statistics."""
        with self.lock:
            pool_stats = self.context_pool.get_stats()
            
            return {
                'contexts_created': self.contexts_created,
                'contexts_processed': self.contexts_processed,
                'contexts_failed': self.contexts_failed,
                'active_contexts': len(self.active_contexts),
                'active_chains': len(self.context_chains),
                'average_processing_time': self.average_processing_time,
                'pool_stats': pool_stats
            }
    
    def clear(self):
        """Clear all contexts and reset statistics."""
        with self.lock:
            self.active_contexts.clear()
            self.context_chains.clear()
            self.context_pool.clear()
            
            self.contexts_created = 0
            self.contexts_processed = 0
            self.contexts_failed = 0
            self.average_processing_time = 0.0
            self.processing_times.clear()
    
    @contextmanager
    def managed_context(
        self,
        event_type: EventType,
        source: str,
        data: Optional[Any] = None,
        **metadata
    ):
        """Context manager for automatic context lifecycle management."""
        context = self.create_context(
            event_type=event_type,
            source=source,
            data=data,
            **metadata
        )
        
        start_time = time.time()
        try:
            yield context
            processing_time = time.time() - start_time
            self.mark_processed(context, processing_time)
        except Exception as e:
            self.mark_failed(context, e)
            raise
        finally:
            self.release_context(context)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.clear()


# Global context manager instance
_default_context_manager = None


def get_default_context_manager() -> EventContextManager:
    """Get the default global context manager."""
    global _default_context_manager
    if _default_context_manager is None:
        _default_context_manager = EventContextManager()
    return _default_context_manager


def set_default_context_manager(manager: EventContextManager):
    """Set the default global context manager."""
    global _default_context_manager
    _default_context_manager = manager


# Convenience functions
def create_context(event_type: EventType, source: str, **kwargs) -> EventContext:
    """Create a context using the default context manager."""
    return get_default_context_manager().create_context(event_type, source, **kwargs)


def create_child_context(parent: EventContext, event_type: EventType, **kwargs) -> EventContext:
    """Create a child context using the default context manager."""
    return get_default_context_manager().create_child_context(parent, event_type, **kwargs)


def release_context(context: EventContext):
    """Release a context using the default context manager."""
    get_default_context_manager().release_context(context)


@contextmanager
def managed_context(event_type: EventType, source: str, **kwargs):
    """Managed context using the default context manager."""
    with get_default_context_manager().managed_context(event_type, source, **kwargs) as context:
        yield context