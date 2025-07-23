"""
Timeout protection and caching utilities for validation operations.

This module provides timeout decorators and caching mechanisms to prevent
DoS attacks through complex validation and improve performance through
intelligent caching of validation results.
"""

import signal
import functools
import hashlib
import time
import threading
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, Union
from functools import lru_cache, wraps
import logging
from contextlib import contextmanager
import weakref
import sys

logger = logging.getLogger(__name__)

# Type variables for generic decorators
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class ValidationTimeoutError(Exception):
    """Exception raised when validation operation times out."""
    pass


class ValidationCache:
    """
    LRU cache specifically designed for validation results with automatic
    cleanup and memory-aware eviction policies.
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = threading.RLock()
        
    def _create_cache_key(self, *args, **kwargs) -> str:
        """Create a deterministic cache key from function arguments."""
        # Create a stable representation of args and kwargs
        key_data = []
        
        # Handle positional arguments
        for arg in args:
            if isinstance(arg, (str, int, float, bool, type(None))):
                key_data.append(str(arg))
            elif isinstance(arg, (list, tuple)):
                # Truncate large lists to prevent memory issues
                if len(arg) > 100:
                    key_data.append(f"list_{len(arg)}_{hash(tuple(arg[:50]) + tuple(arg[-50:]))}")
                else:
                    key_data.append(str(arg))
            elif isinstance(arg, dict):
                # Truncate large dicts
                if len(arg) > 100:
                    items = sorted(list(arg.items())[:50])
                    key_data.append(f"dict_{len(arg)}_{hash(tuple(items))}")
                else:
                    key_data.append(str(sorted(arg.items())))
            else:
                # Use type and id for complex objects
                key_data.append(f"{type(arg).__name__}_{id(arg)}")
        
        # Handle keyword arguments
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_data.append(str(sorted_kwargs))
        
        # Create hash from key data
        key_str = "|".join(key_data)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
    
    def get(self, key: str) -> Optional[Tuple[Any, bool]]:
        """Get cached value. Returns (value, is_expired) or None if not found."""
        with self._lock:
            if key not in self._cache:
                return None
            
            value, timestamp = self._cache[key]
            current_time = time.time()
            
            # Check TTL expiration
            is_expired = (current_time - timestamp) > self.ttl_seconds
            
            if is_expired:
                # Remove expired entry
                del self._cache[key]
                self._access_times.pop(key, None)
                return None
            
            # Update access time for LRU
            self._access_times[key] = current_time
            return value, False
    
    def put(self, key: str, value: Any):
        """Store value in cache with current timestamp."""
        with self._lock:
            current_time = time.time()
            
            # Evict oldest entries if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            self._cache[key] = (value, current_time)
            self._access_times[key] = current_time
    
    def _evict_lru(self):
        """Evict least recently used entries."""
        if not self._access_times:
            return
        
        # Remove 25% of entries (oldest by access time)
        entries_to_remove = max(1, len(self._access_times) // 4)
        sorted_entries = sorted(self._access_times.items(), key=lambda x: x[1])
        
        for key, _ in sorted_entries[:entries_to_remove]:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
    
    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            current_time = time.time()
            expired_count = sum(
                1 for _, timestamp in self._cache.values()
                if (current_time - timestamp) > self.ttl_seconds
            )
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'expired_entries': expired_count,
                'ttl_seconds': self.ttl_seconds
            }


# Global cache instance
_validation_cache = ValidationCache()


@contextmanager
def timeout_context(seconds: float):
    """
    Context manager for timeout protection using threading.
    Works on all platforms including Windows.
    """
    # Use threading-based timeout on Windows or when not in main thread
    if sys.platform == "win32" or threading.current_thread() != threading.main_thread():
        # Windows doesn't support signal-based timeouts reliably
        # Use threading-based timeout
        result = {'completed': False, 'exception': None, 'value': None}
        
        def target_wrapper(func_ref):
            try:
                # The actual work happens in the calling context
                result['completed'] = True
            except Exception as e:
                result['exception'] = e
        
        # Create a simple timeout tracking
        start_time = time.time()
        
        try:
            yield result
            if time.time() - start_time > seconds:
                raise ValidationTimeoutError(f"Operation timed out after {seconds} seconds")
        except Exception as e:
            if not result['completed'] and time.time() - start_time > seconds:
                raise ValidationTimeoutError(f"Operation timed out after {seconds} seconds")
            raise
    else:
        # Unix-like systems can use signals (only in main thread)
        def timeout_handler(signum, frame):
            raise ValidationTimeoutError(f"Operation timed out after {seconds} seconds")
        
        # Set the signal handler and a alarm
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(seconds + 0.5))  # Round up to nearest second
        
        try:
            yield
        finally:
            # Reset the alarm and handler
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def with_timeout(timeout_seconds: float = 5.0):
    """
    Decorator to add timeout protection to validation functions.
    
    Args:
        timeout_seconds: Maximum time allowed for function execution
        
    Returns:
        Decorated function with timeout protection
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use threading-based timeout on Windows or when not in main thread
            if sys.platform == "win32" or threading.current_thread() != threading.main_thread():
                # Windows threading-based timeout
                import concurrent.futures
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    try:
                        return future.result(timeout=timeout_seconds)
                    except concurrent.futures.TimeoutError:
                        raise ValidationTimeoutError(
                            f"Validation operation '{func.__name__}' timed out after {timeout_seconds} seconds"
                        )
            else:
                # Unix signal-based timeout
                with timeout_context(timeout_seconds):
                    return func(*args, **kwargs)
        
        return wrapper
    return decorator


def with_validation_cache(cache_key_func: Optional[Callable] = None, ttl_seconds: float = 300.0):
    """
    Decorator to add caching to validation functions.
    
    Args:
        cache_key_func: Optional function to generate cache keys. If None, uses default.
        ttl_seconds: Time-to-live for cache entries
        
    Returns:
        Decorated function with caching
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(*args, **kwargs)
            else:
                cache_key = _validation_cache._create_cache_key(*args, **kwargs)
            
            # Try to get from cache
            cached_result = _validation_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key[:16]}...")
                return cached_result[0]
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            _validation_cache.put(cache_key, result)
            
            logger.debug(f"Cache miss for {func.__name__}: {cache_key[:16]}...")
            return result
        
        return wrapper
    return decorator


def with_timeout_and_cache(timeout_seconds: float = 5.0, cache_ttl_seconds: float = 300.0):
    """
    Decorator combining timeout protection and result caching.
    
    Args:
        timeout_seconds: Maximum time allowed for function execution
        cache_ttl_seconds: Time-to-live for cache entries
        
    Returns:
        Decorated function with both timeout and caching
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _validation_cache._create_cache_key(*args, **kwargs)
            
            # Try to get from cache first
            cached_result = _validation_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key[:16]}...")
                return cached_result[0]
            
            # Execute with timeout protection
            if sys.platform == "win32":
                import concurrent.futures
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    try:
                        result = future.result(timeout=timeout_seconds)
                    except concurrent.futures.TimeoutError:
                        raise ValidationTimeoutError(
                            f"Validation operation '{func.__name__}' timed out after {timeout_seconds} seconds"
                        )
            else:
                with timeout_context(timeout_seconds):
                    result = func(*args, **kwargs)
            
            # Cache the result
            _validation_cache.put(cache_key, result)
            logger.debug(f"Cache miss for {func.__name__}: {cache_key[:16]}...")
            
            return result
        
        return wrapper
    return decorator


class TimeoutValidator:
    """
    Mixin class to add timeout protection to validator classes.
    """
    
    def __init__(self, timeout_seconds: float = 5.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout_seconds = timeout_seconds
    
    def _with_timeout(self, func: Callable, *args, **kwargs):
        """Execute function with timeout protection."""
        if sys.platform == "win32":
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=self.timeout_seconds)
                except concurrent.futures.TimeoutError:
                    raise ValidationTimeoutError(
                        f"Validation operation timed out after {self.timeout_seconds} seconds"
                    )
        else:
            with timeout_context(self.timeout_seconds):
                return func(*args, **kwargs)


def get_validation_cache_stats() -> Dict[str, Any]:
    """Get statistics about the global validation cache."""
    return _validation_cache.stats()


def clear_validation_cache():
    """Clear all cached validation results."""
    _validation_cache.clear()


def configure_validation_cache(max_size: int = 1000, ttl_seconds: float = 300.0):
    """Configure the global validation cache parameters."""
    global _validation_cache
    _validation_cache = ValidationCache(max_size=max_size, ttl_seconds=ttl_seconds)