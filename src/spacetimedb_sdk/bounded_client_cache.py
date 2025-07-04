"""
Bounded Client Cache with Context Pooling for SpacetimeDB SDK

Implements efficient caching and pooling of EventContext objects for better memory management.
"""

import threading
import time
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from dataclasses import dataclass, field
import logging
import uuid

from .event_system import EventContext, Event, EventType, EventMetadata


@dataclass
class ContextConfiguration:
    """Configuration for EventContext objects."""
    max_history_size: int = 100
    enable_response_data: bool = True
    enable_propagation_control: bool = True
    default_source_component: str = "system"
    auto_complete_timeout: float = 30.0
    enable_timing_metrics: bool = True


class ContextPool:
    """
    Pool for managing EventContext objects efficiently.
    
    Provides:
    - Context object reuse to reduce allocations
    - Configurable context parameters
    - Thread-safe context acquisition/release
    - Memory-efficient context management
    """
    
    def __init__(
        self,
        min_size: int = 5,
        max_size: int = 50,
        context_config: Optional[ContextConfiguration] = None
    ):
        self.min_size = min_size
        self.max_size = max_size
        self.context_config = context_config or ContextConfiguration()
        
        # Pool storage
        self._available_contexts: deque = deque()
        self._active_contexts: Dict[str, EventContext] = {}
        self._lock = threading.RLock()
        
        # Metrics
        self.total_acquired = 0
        self.total_released = 0
        self.peak_active = 0
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.ContextPool")
        
        # Initialize pool with minimum contexts
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        """Initialize the pool with minimum number of contexts."""
        self.logger.info(f"Initializing context pool with {self.min_size} contexts")
        
        for _ in range(self.min_size):
            context = self._create_context()
            self._available_contexts.append(context)
    
    def _create_context(self) -> EventContext:
        """Create a new EventContext with pool configuration."""
        # Create a placeholder event for the context
        placeholder_event = Event(
            type=EventType.CUSTOM,
            data={"_pooled": True},
            metadata=EventMetadata(
                source=self.context_config.default_source_component
            )
        )
        
        return EventContext(
            event=placeholder_event,
            source_component=self.context_config.default_source_component
        )
    
    def configure_context(self, context: EventContext, **kwargs) -> None:
        """
        Configure an EventContext with the provided parameters.
        
        Args:
            context: The EventContext to configure
            **kwargs: Configuration parameters
        """
        # Apply configuration from pool settings
        if hasattr(context, '_response_data') and not self.context_config.enable_response_data:
            context._response_data.clear()
        
        # Apply any additional configuration from kwargs
        for key, value in kwargs.items():
            if key == 'source_component':
                context.source_component = value
            elif key == 'enable_timing' and hasattr(context, '_start_time'):
                if not value:
                    # Don't modify _start_time directly as it's expected to be a float
                    # Instead, we could add a flag to track if timing is enabled
                    pass
            elif key == 'max_triggered_events':
                # Limit the number of triggered events
                if hasattr(context, '_triggered_events'):
                    context._triggered_events = context._triggered_events[:value]
        
        self.logger.debug(f"Configured context {context.event_id} with parameters: {kwargs}")
    
    def acquire_context(self, event: Event, **config_kwargs) -> EventContext:
        """
        Acquire an EventContext from the pool.
        
        Args:
            event: The event to associate with the context
            **config_kwargs: Additional configuration parameters
            
        Returns:
            Configured EventContext
        """
        with self._lock:
            if self._available_contexts:
                context = self._available_contexts.popleft()
                # Reset the context with the new event
                context.event = event
                context._processed = False
                context._propagation_stopped = False
                context._default_prevented = False
                context._response_data.clear()
                context._triggered_events.clear()
                context._handled_by.clear()
                context._start_time = time.time()
                context._end_time = None
            else:
                # Create new context if pool is empty and under max size
                if len(self._active_contexts) < self.max_size:
                    context = EventContext(
                        event=event,
                        source_component=self.context_config.default_source_component
                    )
                else:
                    # Pool is at capacity, create temporary context
                    context = EventContext(
                        event=event,
                        source_component=self.context_config.default_source_component
                    )
                    self.logger.warning("Context pool at capacity, creating temporary context")
            
            # Configure the context
            self.configure_context(context, **config_kwargs)
            
            # Track active context
            self._active_contexts[context.event_id] = context
            self.total_acquired += 1
            self.peak_active = max(self.peak_active, len(self._active_contexts))
            
            return context
    
    def release_context(self, context: EventContext) -> None:
        """
        Release an EventContext back to the pool.
        
        Args:
            context: The EventContext to release
        """
        with self._lock:
            if context.event_id in self._active_contexts:
                del self._active_contexts[context.event_id]
                self.total_released += 1
                
                # Clean up context before returning to pool
                context.complete()
                
                # Return to pool if not at capacity
                if len(self._available_contexts) < self.max_size:
                    self._available_contexts.append(context)
                else:
                    # Pool is full, let context be garbage collected
                    self.logger.debug("Context pool full, discarding context")
    
    def get_pool_metrics(self) -> Dict[str, Any]:
        """Get pool usage metrics."""
        with self._lock:
            return {
                'min_size': self.min_size,
                'max_size': self.max_size,
                'available_contexts': len(self._available_contexts),
                'active_contexts': len(self._active_contexts),
                'total_acquired': self.total_acquired,
                'total_released': self.total_released,
                'peak_active': self.peak_active,
                'pool_utilization': len(self._active_contexts) / self.max_size
            }
    
    def cleanup(self) -> None:
        """Clean up the pool resources."""
        with self._lock:
            # Complete all active contexts
            for context in self._active_contexts.values():
                context.complete()
            
            self._active_contexts.clear()
            self._available_contexts.clear()
            
            self.logger.info("Context pool cleaned up")


class BoundedClientCache:
    """
    Bounded cache for client connections with context pooling.
    
    Provides efficient caching of client connections and associated contexts.
    """
    
    def __init__(
        self,
        max_clients: int = 100,
        context_pool_size: int = 200,
        ttl_seconds: float = 300.0
    ):
        self.max_clients = max_clients
        self.ttl_seconds = ttl_seconds
        
        # Client cache
        self._clients: Dict[str, Any] = {}
        self._client_timestamps: Dict[str, float] = {}
        self._lock = threading.RLock()
        
        # Context pool
        self.context_pool = ContextPool(
            min_size=context_pool_size // 4,
            max_size=context_pool_size
        )
        
        # Cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_running = True
        self._cleanup_thread.start()
        
        self.logger = logging.getLogger(f"{__name__}.BoundedClientCache")
    
    def _cleanup_loop(self) -> None:
        """Background cleanup of expired clients."""
        while self._cleanup_running:
            try:
                self._cleanup_expired_clients()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")
    
    def _cleanup_expired_clients(self) -> None:
        """Remove expired clients from cache."""
        current_time = time.time()
        expired_keys = []
        
        with self._lock:
            for key, timestamp in self._client_timestamps.items():
                if current_time - timestamp > self.ttl_seconds:
                    expired_keys.append(key)
            
            for key in expired_keys:
                if key in self._clients:
                    del self._clients[key]
                    del self._client_timestamps[key]
        
        if expired_keys:
            self.logger.info(f"Cleaned up {len(expired_keys)} expired clients")
    
    def get_client(self, client_id: str) -> Optional[Any]:
        """Get a client from the cache."""
        with self._lock:
            if client_id in self._clients:
                # Update timestamp
                self._client_timestamps[client_id] = time.time()
                return self._clients[client_id]
            return None
    
    def put_client(self, client_id: str, client: Any) -> None:
        """Put a client in the cache."""
        with self._lock:
            # Remove oldest client if at capacity
            if len(self._clients) >= self.max_clients:
                oldest_key = min(self._client_timestamps.keys(), 
                               key=lambda k: self._client_timestamps[k])
                del self._clients[oldest_key]
                del self._client_timestamps[oldest_key]
            
            self._clients[client_id] = client
            self._client_timestamps[client_id] = time.time()
    
    def shutdown(self) -> None:
        """Shutdown the cache and cleanup resources."""
        self._cleanup_running = False
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        self.context_pool.cleanup()
        self._clients.clear()
        self._client_timestamps.clear()
        
        self.logger.info("BoundedClientCache shutdown complete")