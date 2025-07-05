"""
Bounded Client Cache with Context Pooling for SpacetimeDB SDK

Implements efficient caching and pooling of EventContext objects for better memory management.
This combines the memory-safe bounded collections with context pooling capabilities.
"""

import importlib
import pkgutil
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from dataclasses import dataclass, field
import uuid

from .event_system import EventContext, Event, EventType, EventMetadata
from .memory_management import (
    BoundedDict, MemoryAccountant, get_global_memory_accountant,
    DEFAULT_MAX_CACHE_SIZE
)

logger = logging.getLogger(__name__)


def snake_to_camel(snake_case_string: str) -> str:
    """Convert snake_case to CamelCase."""
    return snake_case_string.replace("_", " ").title().replace(" ", "")


@dataclass
class ContextConfiguration:
    """Configuration for EventContext objects."""
    max_history_size: int = 100
    enable_response_data: bool = True
    enable_propagation_control: bool = True
    default_source_component: str = "system"
    auto_complete_timeout: float = 30.0
    enable_timing_metrics: bool = True


class BoundedTableCache:
    """
    Table cache with bounded storage and memory management.
    
    Features:
    - Maximum entry limit
    - Memory accounting
    - Automatic eviction on memory pressure
    """
    
    def __init__(
        self,
        table_class,
        max_entries: int = DEFAULT_MAX_CACHE_SIZE,
        memory_accountant: Optional[MemoryAccountant] = None
    ):
        self.table_class = table_class
        self.memory_accountant = memory_accountant or get_global_memory_accountant()
        
        def on_evict(key, value):
            logger.debug(f"Evicted cache entry for table {self.table_class.__name__}: {key}")
        
        self.entries = BoundedDict(
            max_size=max_entries,
            memory_accountant=self.memory_accountant,
            on_evict=on_evict
        )
    
    def decode(self, value: Any) -> Any:
        """Decode a value using the table class."""
        return self.table_class(value)
    
    def set_entry(self, key: Any, value: Any) -> None:
        """Set an entry after decoding."""
        try:
            decoded_value = self.decode(value)
            self.entries.set(key, decoded_value)
        except Exception as e:
            logger.error(f"Failed to decode and cache entry for key {key}: {e}")
    
    def set_entry_decoded(self, key: Any, decoded_value: Any) -> None:
        """Set an already decoded entry."""
        self.entries.set(key, decoded_value)
    
    def delete_entry(self, key: Any) -> bool:
        """Delete an entry."""
        if self.entries.delete(key):
            return True
        else:
            logger.warning(f"[delete_entry] Key not found: {key}")
            return False
    
    def get_entry(self, key: Any) -> Optional[Any]:
        """Get an entry."""
        return self.entries.get(key)
    
    def values(self):
        """Get all cached values."""
        return self.entries.values()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'entry_count': len(self.entries),
            'table_class': self.table_class.__name__
        }


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
    Combined client cache with bounded storage for tables/reducers and context pooling.
    
    Features:
    - Bounded table caches with memory management
    - Bounded reducer cache
    - Context pooling for efficient memory usage
    - Client caching with TTL
    - Memory accounting and statistics
    """
    
    def __init__(
        self,
        autogen_package=None,
        max_cache_size: int = DEFAULT_MAX_CACHE_SIZE,
        memory_accountant: Optional[MemoryAccountant] = None,
        max_clients: int = 100,
        context_pool_size: int = 200,
        ttl_seconds: float = 300.0
    ):
        self.memory_accountant = memory_accountant or get_global_memory_accountant()
        self.max_cache_size = max_cache_size
        self.max_clients = max_clients
        self.ttl_seconds = ttl_seconds
        
        # Bounded storage for tables and reducers
        self.tables: Dict[str, BoundedTableCache] = {}
        self.reducer_cache = BoundedDict(
            max_size=1000,  # Reasonable limit for reducers
            memory_accountant=self.memory_accountant
        )
        
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
        
        # Load tables and reducers from autogen package if provided
        if autogen_package:
            self._load_autogen_package(autogen_package)
    
    def _load_autogen_package(self, autogen_package) -> None:
        """Load tables and reducers from autogenerated package."""
        try:
            for importer, module_name, is_package in pkgutil.iter_modules(
                autogen_package.__path__
            ):
                if not is_package:
                    module = importlib.import_module(
                        f"{autogen_package.__name__}.{module_name}"
                    )
                    
                    # Check if it's a reducer
                    if module_name.endswith("_reducer"):
                        reducer_name = getattr(module, "reducer_name", None)
                        args_class = getattr(module, "_decode_args", None)
                        
                        if reducer_name and args_class:
                            self.reducer_cache.set(reducer_name, args_class)
                            logger.debug(f"Loaded reducer: {reducer_name}")
                    else:
                        # Assuming table class name is the same as the module name
                        table_class_name = snake_to_camel(module_name)
                        
                        if hasattr(module, table_class_name):
                            table_class = getattr(module, table_class_name)
                            
                            # Check for a special property, e.g. 'is_table_class'
                            if getattr(table_class, "is_table_class", False):
                                self.tables[table_class_name] = BoundedTableCache(
                                    table_class,
                                    max_entries=self.max_cache_size,
                                    memory_accountant=self.memory_accountant
                                )
                                logger.debug(f"Loaded table: {table_class_name}")
        
        except Exception as e:
            logger.error(f"Failed to load autogen package: {e}")
    
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
    
    def get_table_cache(self, table_name: str) -> Optional[BoundedTableCache]:
        """Get table cache by name."""
        return self.tables.get(table_name)
    
    def decode(self, table_name: str, value: Any) -> Optional[Any]:
        """Decode a value for a specific table."""
        if table_name not in self.tables:
            logger.error(f"[decode] Table not found: {table_name}")
            return None
        
        try:
            return self.tables[table_name].decode(value)
        except Exception as e:
            logger.error(f"[decode] Failed to decode value for table {table_name}: {e}")
            return None
    
    def set_entry(self, table_name: str, key: Any, value: Any) -> bool:
        """Set an entry in a table cache."""
        if table_name not in self.tables:
            logger.error(f"[set_entry] Table not found: {table_name}")
            return False
        
        try:
            self.tables[table_name].set_entry(key, value)
            return True
        except Exception as e:
            logger.error(f"[set_entry] Failed to set entry for table {table_name}: {e}")
            return False
    
    def set_entry_decoded(self, table_name: str, key: Any, value: Any) -> bool:
        """Set an already decoded entry in a table cache."""
        if table_name not in self.tables:
            logger.error(f"[set_entry_decoded] Table not found: {table_name}")
            return False
        
        try:
            self.tables[table_name].set_entry_decoded(key, value)
            return True
        except Exception as e:
            logger.error(f"[set_entry_decoded] Failed to set decoded entry for table {table_name}: {e}")
            return False
    
    def delete_entry(self, table_name: str, key: Any) -> bool:
        """Delete an entry from a table cache."""
        if table_name not in self.tables:
            logger.error(f"[delete_entry] Table not found: {table_name}")
            return False
        
        return self.tables[table_name].delete_entry(key)
    
    def get_entry(self, table_name: str, key: Any) -> Optional[Any]:
        """Get an entry from a table cache."""
        if table_name not in self.tables:
            logger.error(f"[get_entry] Table not found: {table_name}")
            return None
        
        return self.tables[table_name].get_entry(key)
    
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
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        memory_stats = self.memory_accountant.get_stats()
        
        table_stats = {}
        for table_name, table_cache in self.tables.items():
            table_stats[table_name] = table_cache.get_stats()
        
        return {
            'memory_usage': {
                'total_bytes': memory_stats.total_bytes,
                'cache_bytes': memory_stats.cache_bytes,
                'peak_bytes': memory_stats.peak_bytes,
                'evictions': memory_stats.evictions,
                'oom_prevented': memory_stats.oom_prevented,
                'usage_percentage': self.memory_accountant.get_usage_percentage()
            },
            'table_caches': table_stats,
            'reducer_cache': {
                'entry_count': len(self.reducer_cache)
            },
            'client_cache': {
                'client_count': len(self._clients)
            },
            'context_pool': self.context_pool.get_pool_metrics()
        }
    
    def clear_all_caches(self) -> None:
        """Clear all caches."""
        for table_cache in self.tables.values():
            table_cache.entries.clear()
        
        self.reducer_cache.clear()
        
        with self._lock:
            self._clients.clear()
            self._client_timestamps.clear()
        
        logger.info("All caches cleared")
    
    def cleanup_memory_pressure(self) -> Dict[str, int]:
        """Perform cleanup when under memory pressure."""
        cleared_counts = {}
        
        # Clear least important caches first
        for table_name, table_cache in self.tables.items():
            old_count = len(table_cache.entries)
            # Force eviction of half the entries by temporarily reducing size
            original_size = table_cache.entries._max_size
            table_cache.entries._max_size = original_size // 2
            table_cache.entries._evict_if_needed()
            table_cache.entries._max_size = original_size
            
            cleared_count = old_count - len(table_cache.entries)
            if cleared_count > 0:
                cleared_counts[table_name] = cleared_count
        
        return cleared_counts
    
    def shutdown(self) -> None:
        """Shutdown the cache and cleanup resources."""
        self._cleanup_running = False
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        self.context_pool.cleanup()
        self._clients.clear()
        self._client_timestamps.clear()
        
        self.logger.info("BoundedClientCache shutdown complete")


# For backward compatibility, provide the same interface as the original client_cache
ClientCache = BoundedClientCache
TableCache = BoundedTableCache