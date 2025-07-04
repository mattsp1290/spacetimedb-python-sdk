"""
Memory management utilities for SpacetimeDB Python SDK.

Provides bounded collections, memory accounting, and recursion limiting
to prevent memory exhaustion vulnerabilities.
"""

import threading
import time
import weakref
import sys
import functools
from collections import OrderedDict, deque
from typing import Dict, Any, Optional, Callable, TypeVar, Generic, Set, Tuple, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

# Type variables
K = TypeVar('K')
V = TypeVar('V')

# Constants
DEFAULT_MAX_CACHE_SIZE = 10000
DEFAULT_MAX_SUBSCRIPTION_SIZE = 1000
DEFAULT_MAX_REQUEST_TRACKING_SIZE = 5000
DEFAULT_MAX_RECURSION_DEPTH = 50
DEFAULT_MEMORY_LIMIT_MB = 512  # 512MB default limit
DEFAULT_TTL_SECONDS = 3600  # 1 hour default TTL


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    total_bytes: int = 0
    cache_bytes: int = 0
    subscription_bytes: int = 0
    request_bytes: int = 0
    message_bytes: int = 0
    peak_bytes: int = 0
    evictions: int = 0
    oom_prevented: int = 0


class EvictionPolicy(ABC):
    """Abstract base class for eviction policies."""
    
    @abstractmethod
    def on_access(self, key: Any) -> None:
        """Called when an item is accessed."""
        pass
    
    @abstractmethod
    def get_eviction_candidate(self) -> Optional[Any]:
        """Get the next item to evict."""
        pass
    
    @abstractmethod
    def on_evict(self, key: Any) -> None:
        """Called when an item is evicted."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all tracking data."""
        pass


class LRUEvictionPolicy(EvictionPolicy):
    """Least Recently Used eviction policy."""
    
    def __init__(self):
        self._access_order = OrderedDict()
        self._lock = threading.RLock()
    
    def on_access(self, key: Any) -> None:
        with self._lock:
            if key in self._access_order:
                self._access_order.move_to_end(key)
            else:
                self._access_order[key] = time.time()
    
    def get_eviction_candidate(self) -> Optional[Any]:
        with self._lock:
            if self._access_order:
                # Return least recently used (first item)
                return next(iter(self._access_order))
            return None
    
    def on_evict(self, key: Any) -> None:
        with self._lock:
            self._access_order.pop(key, None)
    
    def clear(self) -> None:
        with self._lock:
            self._access_order.clear()


class TTLEvictionPolicy(EvictionPolicy):
    """Time-To-Live eviction policy."""
    
    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS):
        self._ttl_seconds = ttl_seconds
        self._timestamps: Dict[Any, float] = {}
        self._lock = threading.RLock()
    
    def on_access(self, key: Any) -> None:
        with self._lock:
            self._timestamps[key] = time.time()
    
    def get_eviction_candidate(self) -> Optional[Any]:
        with self._lock:
            current_time = time.time()
            for key, timestamp in self._timestamps.items():
                if current_time - timestamp > self._ttl_seconds:
                    return key
            return None
    
    def on_evict(self, key: Any) -> None:
        with self._lock:
            self._timestamps.pop(key, None)
    
    def clear(self) -> None:
        with self._lock:
            self._timestamps.clear()


class BoundedDict(Generic[K, V]):
    """
    A dictionary with bounded size and eviction policy.
    
    Features:
    - Maximum size limit
    - Configurable eviction policy (LRU, TTL)
    - Memory accounting
    - Thread-safe operations
    """
    
    def __init__(
        self,
        max_size: int = DEFAULT_MAX_CACHE_SIZE,
        eviction_policy: Optional[EvictionPolicy] = None,
        on_evict: Optional[Callable[[K, V], None]] = None,
        memory_accountant: Optional['MemoryAccountant'] = None
    ):
        self._data: Dict[K, V] = {}
        self._max_size = max_size
        self._eviction_policy = eviction_policy or LRUEvictionPolicy()
        self._on_evict = on_evict
        self._memory_accountant = memory_accountant
        self._lock = threading.RLock()
        self._size_cache: Dict[K, int] = {}
    
    def _estimate_size(self, value: V) -> int:
        """Estimate memory size of a value."""
        if hasattr(value, '__sizeof__'):
            return value.__sizeof__()
        elif isinstance(value, dict):
            return sys.getsizeof(value) + sum(self._estimate_size(v) for v in value.values())
        elif isinstance(value, (list, tuple)):
            return sys.getsizeof(value) + sum(self._estimate_size(v) for v in value)
        else:
            return sys.getsizeof(value)
    
    def _evict_if_needed(self) -> None:
        """Evict items if size limit is exceeded."""
        while len(self._data) >= self._max_size:
            candidate = self._eviction_policy.get_eviction_candidate()
            if candidate is None:
                # Fallback: evict first item
                candidate = next(iter(self._data))
            
            value = self._data.pop(candidate)
            size = self._size_cache.pop(candidate, 0)
            
            self._eviction_policy.on_evict(candidate)
            
            if self._memory_accountant:
                self._memory_accountant.release_memory('cache', size)
                self._memory_accountant.record_eviction()
            
            if self._on_evict:
                self._on_evict(candidate, value)
            
            logger.debug(f"Evicted item {candidate} from bounded dict, freed {size} bytes")
    
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Get an item from the dictionary."""
        with self._lock:
            if key in self._data:
                self._eviction_policy.on_access(key)
                return self._data[key]
            return default
    
    def set(self, key: K, value: V) -> None:
        """Set an item in the dictionary."""
        with self._lock:
            # Calculate size
            size = self._estimate_size(value)
            
            # Check memory limit
            if self._memory_accountant:
                if not self._memory_accountant.try_allocate('cache', size):
                    logger.warning(f"Memory allocation failed for cache item {key} ({size} bytes)")
                    return
            
            # Remove old value if exists
            if key in self._data:
                old_size = self._size_cache.get(key, 0)
                if self._memory_accountant:
                    self._memory_accountant.release_memory('cache', old_size)
            
            # Evict if needed
            self._evict_if_needed()
            
            # Store new value
            self._data[key] = value
            self._size_cache[key] = size
            self._eviction_policy.on_access(key)
    
    def delete(self, key: K) -> bool:
        """Delete an item from the dictionary."""
        with self._lock:
            if key in self._data:
                value = self._data.pop(key)
                size = self._size_cache.pop(key, 0)
                self._eviction_policy.on_evict(key)
                
                if self._memory_accountant:
                    self._memory_accountant.release_memory('cache', size)
                
                return True
            return False
    
    def clear(self) -> None:
        """Clear all items."""
        with self._lock:
            total_size = sum(self._size_cache.values())
            
            self._data.clear()
            self._size_cache.clear()
            self._eviction_policy.clear()
            
            if self._memory_accountant:
                self._memory_accountant.release_memory('cache', total_size)
    
    def __len__(self) -> int:
        return len(self._data)
    
    def __contains__(self, key: K) -> bool:
        return key in self._data
    
    def values(self) -> List[V]:
        """Get all values."""
        with self._lock:
            return list(self._data.values())
    
    def items(self) -> List[Tuple[K, V]]:
        """Get all items."""
        with self._lock:
            return list(self._data.items())


class BoundedSubscriptionManager:
    """
    Manager for subscriptions with bounded storage.
    
    Features:
    - Maximum subscriptions limit
    - Per-subscription data size limits
    - Automatic cleanup of stale subscriptions
    """
    
    def __init__(
        self,
        max_subscriptions: int = DEFAULT_MAX_SUBSCRIPTION_SIZE,
        max_data_per_subscription: int = 10 * 1024 * 1024,  # 10MB per subscription
        memory_accountant: Optional['MemoryAccountant'] = None
    ):
        self._subscriptions: Dict[Any, Dict[str, Any]] = {}
        self._subscription_data: Dict[Any, Any] = {}
        self._max_subscriptions = max_subscriptions
        self._max_data_per_subscription = max_data_per_subscription
        self._memory_accountant = memory_accountant
        self._lock = threading.RLock()
        self._access_times: Dict[Any, float] = {}
        self._data_sizes: Dict[Any, int] = {}
    
    def add_subscription(self, subscription_id: Any, metadata: Dict[str, Any]) -> bool:
        """Add a new subscription."""
        with self._lock:
            if len(self._subscriptions) >= self._max_subscriptions:
                # Evict oldest subscription
                if self._access_times:
                    oldest_id = min(self._access_times, key=self._access_times.get)
                    self.remove_subscription(oldest_id)
                    logger.warning(f"Evicted oldest subscription {oldest_id} to make room")
            
            self._subscriptions[subscription_id] = metadata
            self._access_times[subscription_id] = time.time()
            return True
    
    def update_subscription_data(self, subscription_id: Any, data: Any) -> bool:
        """Update subscription data with size checking."""
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            # Estimate data size
            data_size = sys.getsizeof(data)
            if hasattr(data, '__sizeof__'):
                data_size = data.__sizeof__()
            
            # Check size limit
            if data_size > self._max_data_per_subscription:
                logger.error(f"Subscription {subscription_id} data too large: {data_size} bytes")
                return False
            
            # Check memory allocation
            if self._memory_accountant:
                old_size = self._data_sizes.get(subscription_id, 0)
                if not self._memory_accountant.try_allocate('subscription', data_size - old_size):
                    logger.warning(f"Memory allocation failed for subscription {subscription_id}")
                    return False
            
            # Update data
            self._subscription_data[subscription_id] = data
            self._data_sizes[subscription_id] = data_size
            self._access_times[subscription_id] = time.time()
            return True
    
    def get_subscription(self, subscription_id: Any) -> Optional[Tuple[Dict[str, Any], Any]]:
        """Get subscription metadata and data."""
        with self._lock:
            if subscription_id in self._subscriptions:
                self._access_times[subscription_id] = time.time()
                metadata = self._subscriptions[subscription_id]
                data = self._subscription_data.get(subscription_id)
                return metadata, data
            return None
    
    def remove_subscription(self, subscription_id: Any) -> bool:
        """Remove a subscription."""
        with self._lock:
            if subscription_id in self._subscriptions:
                self._subscriptions.pop(subscription_id)
                self._subscription_data.pop(subscription_id, None)
                self._access_times.pop(subscription_id, None)
                
                data_size = self._data_sizes.pop(subscription_id, 0)
                if self._memory_accountant and data_size > 0:
                    self._memory_accountant.release_memory('subscription', data_size)
                
                return True
            return False
    
    def cleanup_stale(self, max_age_seconds: float = 3600) -> int:
        """Remove subscriptions older than max_age_seconds."""
        with self._lock:
            current_time = time.time()
            stale_ids = [
                sub_id for sub_id, access_time in self._access_times.items()
                if current_time - access_time > max_age_seconds
            ]
            
            for sub_id in stale_ids:
                self.remove_subscription(sub_id)
            
            return len(stale_ids)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        with self._lock:
            total_data_size = sum(self._data_sizes.values())
            return {
                'active_subscriptions': len(self._subscriptions),
                'total_data_size': total_data_size,
                'average_data_size': total_data_size / len(self._subscriptions) if self._subscriptions else 0,
                'max_subscriptions': self._max_subscriptions,
                'oldest_access': min(self._access_times.values()) if self._access_times else None
            }


class RecursionLimiter:
    """
    Context manager and decorator for limiting recursion depth.
    
    Prevents stack overflow from unbounded recursive operations.
    """
    
    def __init__(self, max_depth: int = DEFAULT_MAX_RECURSION_DEPTH):
        self._max_depth = max_depth
        self._current_depth = threading.local()
    
    def _get_depth(self) -> int:
        """Get current recursion depth for this thread."""
        if not hasattr(self._current_depth, 'value'):
            self._current_depth.value = 0
        return self._current_depth.value
    
    def _set_depth(self, depth: int) -> None:
        """Set current recursion depth for this thread."""
        self._current_depth.value = depth
    
    def __enter__(self):
        current = self._get_depth()
        if current >= self._max_depth:
            raise RecursionError(f"Maximum recursion depth ({self._max_depth}) exceeded")
        self._set_depth(current + 1)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        current = self._get_depth()
        self._set_depth(max(0, current - 1))
        return False
    
    def __call__(self, func):
        """Decorator usage."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper


class MemoryAccountant:
    """
    Track and limit total memory usage across the SDK.
    
    Features:
    - Category-based memory tracking
    - Global memory limit enforcement
    - Memory usage statistics
    - OOM prevention
    """
    
    def __init__(self, memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB):
        self._memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self._current_usage: Dict[str, int] = {}
        self._stats = MemoryStats()
        self._lock = threading.RLock()
        self._allocation_callbacks: List[Callable[[str, int], None]] = []
    
    def try_allocate(self, category: str, size_bytes: int) -> bool:
        """Try to allocate memory, return False if would exceed limit."""
        with self._lock:
            total_usage = sum(self._current_usage.values())
            
            if total_usage + size_bytes > self._memory_limit_bytes:
                self._stats.oom_prevented += 1
                logger.warning(
                    f"Memory allocation denied for {category}: {size_bytes} bytes "
                    f"(current: {total_usage}, limit: {self._memory_limit_bytes})"
                )
                return False
            
            # Allocate
            self._current_usage[category] = self._current_usage.get(category, 0) + size_bytes
            
            # Update stats
            self._stats.total_bytes = sum(self._current_usage.values())
            self._stats.peak_bytes = max(self._stats.peak_bytes, self._stats.total_bytes)
            
            # Update category stats
            if category == 'cache':
                self._stats.cache_bytes = self._current_usage[category]
            elif category == 'subscription':
                self._stats.subscription_bytes = self._current_usage[category]
            elif category == 'request':
                self._stats.request_bytes = self._current_usage[category]
            elif category == 'message':
                self._stats.message_bytes = self._current_usage[category]
            
            # Notify callbacks
            for callback in self._allocation_callbacks:
                try:
                    callback(category, size_bytes)
                except Exception as e:
                    logger.error(f"Allocation callback error: {e}")
            
            return True
    
    def release_memory(self, category: str, size_bytes: int) -> None:
        """Release allocated memory."""
        with self._lock:
            if category in self._current_usage:
                self._current_usage[category] = max(0, self._current_usage[category] - size_bytes)
                
                # Update stats
                self._stats.total_bytes = sum(self._current_usage.values())
                
                # Update category stats
                if category == 'cache':
                    self._stats.cache_bytes = self._current_usage[category]
                elif category == 'subscription':
                    self._stats.subscription_bytes = self._current_usage[category]
                elif category == 'request':
                    self._stats.request_bytes = self._current_usage[category]
                elif category == 'message':
                    self._stats.message_bytes = self._current_usage[category]
    
    def record_eviction(self) -> None:
        """Record an eviction event."""
        with self._lock:
            self._stats.evictions += 1
    
    def get_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        with self._lock:
            return MemoryStats(
                total_bytes=self._stats.total_bytes,
                cache_bytes=self._stats.cache_bytes,
                subscription_bytes=self._stats.subscription_bytes,
                request_bytes=self._stats.request_bytes,
                message_bytes=self._stats.message_bytes,
                peak_bytes=self._stats.peak_bytes,
                evictions=self._stats.evictions,
                oom_prevented=self._stats.oom_prevented
            )
    
    def get_usage_percentage(self) -> float:
        """Get current memory usage as percentage of limit."""
        with self._lock:
            total = sum(self._current_usage.values())
            return (total / self._memory_limit_bytes) * 100
    
    def add_allocation_callback(self, callback: Callable[[str, int], None]) -> None:
        """Add a callback to be notified of allocations."""
        self._allocation_callbacks.append(callback)
    
    def check_memory_pressure(self) -> bool:
        """Check if memory usage is above 80% of limit."""
        return self.get_usage_percentage() > 80


class MessageSizeValidator:
    """Validate message sizes to prevent memory exhaustion."""
    
    def __init__(
        self,
        max_message_size: int = 50 * 1024 * 1024,  # 50MB
        max_field_size: int = 10 * 1024 * 1024,    # 10MB
        memory_accountant: Optional[MemoryAccountant] = None
    ):
        self._max_message_size = max_message_size
        self._max_field_size = max_field_size
        self._memory_accountant = memory_accountant
    
    def validate_message_size(self, message_data: bytes) -> bool:
        """Validate total message size."""
        size = len(message_data)
        if size > self._max_message_size:
            logger.error(f"Message too large: {size} bytes (max: {self._max_message_size})")
            return False
        
        # Check memory allocation
        if self._memory_accountant:
            if not self._memory_accountant.try_allocate('message', size):
                return False
        
        return True
    
    def validate_field_size(self, field_data: bytes) -> bool:
        """Validate individual field size."""
        size = len(field_data)
        if size > self._max_field_size:
            logger.error(f"Field too large: {size} bytes (max: {self._max_field_size})")
            return False
        return True


# Global memory accountant instance
_global_memory_accountant: Optional[MemoryAccountant] = None


def get_global_memory_accountant() -> MemoryAccountant:
    """Get or create the global memory accountant."""
    global _global_memory_accountant
    if _global_memory_accountant is None:
        _global_memory_accountant = MemoryAccountant()
    return _global_memory_accountant


def configure_memory_limits(
    memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB,
    max_cache_size: int = DEFAULT_MAX_CACHE_SIZE,
    max_subscriptions: int = DEFAULT_MAX_SUBSCRIPTION_SIZE,
    max_recursion_depth: int = DEFAULT_MAX_RECURSION_DEPTH
) -> Dict[str, Any]:
    """
    Configure global memory limits for the SDK.
    
    Returns current configuration.
    """
    global _global_memory_accountant
    _global_memory_accountant = MemoryAccountant(memory_limit_mb)
    
    return {
        'memory_limit_mb': memory_limit_mb,
        'max_cache_size': max_cache_size,
        'max_subscriptions': max_subscriptions,
        'max_recursion_depth': max_recursion_depth
    }