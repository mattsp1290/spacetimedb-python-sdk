# ADR-004: Memory Management Strategy

## Status
✅ **ACCEPTED** - Implemented in v1.1.2

## Context

The previous SpacetimeDB Python SDK implementation suffered from significant memory management issues:

1. **Unbounded Growth**: Unlimited cache sizes leading to memory exhaustion
2. **Memory Leaks**: Circular references and improper cleanup
3. **Poor Resource Management**: No systematic approach to resource lifecycle
4. **Inefficient Data Structures**: High memory overhead for common operations
5. **Lack of Monitoring**: No visibility into memory usage patterns

Production deployments experienced:
- Memory usage growing from 100MB to 2GB+ over 24 hours
- Out of memory errors under moderate load
- Garbage collection pauses affecting performance
- Container restarts due to memory limits

## Decision

We will implement a **comprehensive memory management strategy** based on bounded collections, proactive monitoring, and intelligent resource lifecycle management:

### Core Principles

1. **Bounded Everything**: All collections have explicit size limits
2. **Proactive Monitoring**: Continuous memory usage tracking
3. **Intelligent Eviction**: Smart cache eviction policies
4. **Resource Cleanup**: Automatic and manual cleanup mechanisms
5. **Memory Efficiency**: Optimized data structures and patterns

### Architecture Components

```python
# Bounded cache with TTL and eviction policies
cache = BoundedCache(
    max_size=10000,
    ttl=3600,
    eviction_policy='lru'
)

# Memory monitoring and alerts
monitor = MemoryMonitor(
    alert_threshold=500,  # MB
    cleanup_threshold=400  # MB
)

# Resource management with automatic cleanup
async with ResourceManager() as resources:
    connection = await resources.acquire('connection')
    # Automatic cleanup on exit
```

## Rationale

### Benefits

1. **Predictable Memory Usage**: Bounded collections prevent runaway growth
2. **Better Performance**: Reduced GC pressure and memory fragmentation
3. **Operational Stability**: Fewer memory-related crashes and restarts
4. **Monitoring Visibility**: Clear insights into memory usage patterns
5. **Developer Experience**: Easier debugging and optimization

### Trade-offs

1. **Cache Miss Rate**: Bounded caches may have higher miss rates
2. **Configuration Complexity**: More parameters to tune
3. **Monitoring Overhead**: Additional CPU/memory for monitoring
4. **Eviction Costs**: Computational overhead for eviction decisions

## Implementation Details

### Bounded Cache System

```python
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from collections import OrderedDict
import time
import threading
import weakref

@dataclass
class CacheEntry:
    value: Any
    timestamp: float
    access_count: int = 0
    last_access: float = 0
    
    def __post_init__(self):
        self.last_access = self.timestamp

class BoundedCache:
    def __init__(self, 
                 max_size: int,
                 ttl: float = 3600,
                 eviction_policy: str = 'lru'):
        
        self.max_size = max_size
        self.ttl = ttl
        self.eviction_policy = eviction_policy
        
        # Thread-safe storage
        self._storage: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def put(self, key: str, value: Any) -> None:
        """Store value in cache with eviction if necessary"""
        
        with self._lock:
            current_time = time.time()
            
            # Update existing entry
            if key in self._storage:
                self._storage[key].value = value
                self._storage[key].timestamp = current_time
                self._storage[key].last_access = current_time
                self._storage.move_to_end(key)
                return
            
            # Add new entry
            entry = CacheEntry(value, current_time)
            self._storage[key] = entry
            
            # Evict if necessary
            if len(self._storage) > self.max_size:
                self._evict()
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache"""
        
        with self._lock:
            if key not in self._storage:
                self._misses += 1
                return None
            
            entry = self._storage[key]
            current_time = time.time()
            
            # Check TTL
            if current_time - entry.timestamp > self.ttl:
                del self._storage[key]
                self._misses += 1
                return None
            
            # Update access statistics
            entry.access_count += 1
            entry.last_access = current_time
            
            # Move to end for LRU
            if self.eviction_policy == 'lru':
                self._storage.move_to_end(key)
            
            self._hits += 1
            return entry.value
    
    def _evict(self) -> None:
        """Evict entries based on policy"""
        
        if self.eviction_policy == 'lru':
            # Remove least recently used
            self._storage.popitem(last=False)
        
        elif self.eviction_policy == 'lfu':
            # Remove least frequently used
            min_access = min(entry.access_count for entry in self._storage.values())
            for key, entry in self._storage.items():
                if entry.access_count == min_access:
                    del self._storage[key]
                    break
        
        elif self.eviction_policy == 'ttl':
            # Remove oldest entry
            oldest_key = min(self._storage.keys(), 
                           key=lambda k: self._storage[k].timestamp)
            del self._storage[oldest_key]
        
        self._evictions += 1
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        
        import asyncio
        
        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)  # Cleanup every minute
                self._cleanup_expired()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._storage.items():
                if current_time - entry.timestamp > self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._storage[key]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                'size': len(self._storage),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'evictions': self._evictions,
                'utilization': len(self._storage) / self.max_size
            }
```

### Memory Monitoring System

```python
import psutil
import gc
import threading
import time
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
from collections import deque

@dataclass
class MemorySnapshot:
    timestamp: float
    rss_mb: float
    vms_mb: float
    heap_objects: int
    gc_collections: Dict[int, int]
    
class MemoryMonitor:
    def __init__(self, 
                 alert_threshold: float = 500,  # MB
                 cleanup_threshold: float = 400,  # MB
                 monitoring_interval: float = 10.0):  # seconds
        
        self.alert_threshold = alert_threshold
        self.cleanup_threshold = cleanup_threshold
        self.monitoring_interval = monitoring_interval
        
        # History and callbacks
        self.snapshots: deque = deque(maxlen=1000)
        self.alert_callbacks: List[Callable] = []
        self.cleanup_callbacks: List[Callable] = []
        
        # Process reference
        self.process = psutil.Process()
        
        # Monitoring state
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Baseline measurement
        self.baseline_snapshot = self._take_snapshot()
    
    def start_monitoring(self) -> None:
        """Start memory monitoring"""
        
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop memory monitoring"""
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        
        while self.monitoring:
            try:
                snapshot = self._take_snapshot()
                self.snapshots.append(snapshot)
                
                # Check thresholds
                if snapshot.rss_mb > self.alert_threshold:
                    self._trigger_alerts(snapshot)
                
                if snapshot.rss_mb > self.cleanup_threshold:
                    self._trigger_cleanup(snapshot)
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                print(f"Memory monitoring error: {e}")
    
    def _take_snapshot(self) -> MemorySnapshot:
        """Take memory snapshot"""
        
        memory_info = self.process.memory_info()
        gc_stats = gc.get_stats()
        
        return MemorySnapshot(
            timestamp=time.time(),
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            heap_objects=len(gc.get_objects()),
            gc_collections={i: stat['collections'] for i, stat in enumerate(gc_stats)}
        )
    
    def _trigger_alerts(self, snapshot: MemorySnapshot) -> None:
        """Trigger memory alerts"""
        
        for callback in self.alert_callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                print(f"Alert callback error: {e}")
    
    def _trigger_cleanup(self, snapshot: MemorySnapshot) -> None:
        """Trigger memory cleanup"""
        
        for callback in self.cleanup_callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                print(f"Cleanup callback error: {e}")
        
        # Force garbage collection
        self._force_gc()
    
    def _force_gc(self) -> None:
        """Force garbage collection"""
        
        collected = gc.collect()
        print(f"Garbage collection collected {collected} objects")
    
    def add_alert_callback(self, callback: Callable[[MemorySnapshot], None]) -> None:
        """Add memory alert callback"""
        self.alert_callbacks.append(callback)
    
    def add_cleanup_callback(self, callback: Callable[[MemorySnapshot], None]) -> None:
        """Add memory cleanup callback"""
        self.cleanup_callbacks.append(callback)
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage"""
        
        if not self.snapshots:
            return {}
        
        current = self.snapshots[-1]
        baseline = self.baseline_snapshot
        
        return {
            'current_rss_mb': current.rss_mb,
            'current_vms_mb': current.vms_mb,
            'rss_delta_mb': current.rss_mb - baseline.rss_mb,
            'vms_delta_mb': current.vms_mb - baseline.vms_mb,
            'heap_objects': current.heap_objects,
            'object_growth': current.heap_objects - baseline.heap_objects
        }
    
    def detect_memory_leaks(self) -> List[str]:
        """Detect potential memory leaks"""
        
        if len(self.snapshots) < 10:
            return []
        
        issues = []
        recent_snapshots = list(self.snapshots)[-10:]
        
        # Check for steadily increasing memory
        rss_trend = self._calculate_trend([s.rss_mb for s in recent_snapshots])
        if rss_trend > 5:  # More than 5MB increase per measurement
            issues.append(f"Increasing RSS memory trend: +{rss_trend:.1f}MB/interval")
        
        # Check for object count growth
        obj_trend = self._calculate_trend([s.heap_objects for s in recent_snapshots])
        if obj_trend > 1000:  # More than 1000 objects increase per measurement
            issues.append(f"Increasing object count trend: +{obj_trend:.0f} objects/interval")
        
        # Check for memory fragmentation
        recent_vms = [s.vms_mb for s in recent_snapshots]
        recent_rss = [s.rss_mb for s in recent_snapshots]
        
        if recent_vms and recent_rss:
            fragmentation = (sum(recent_vms) - sum(recent_rss)) / len(recent_vms)
            if fragmentation > 100:  # More than 100MB fragmentation
                issues.append(f"High memory fragmentation: {fragmentation:.1f}MB")
        
        return issues
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend (slope) of values"""
        
        if len(values) < 2:
            return 0
        
        n = len(values)
        sum_x = sum(range(n))
        sum_y = sum(values)
        sum_xy = sum(i * values[i] for i in range(n))
        sum_x2 = sum(i * i for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        return slope
```

### Resource Management

```python
import asyncio
import weakref
from typing import Any, Dict, Optional, TypeVar, Generic, AsyncContextManager
from contextlib import asynccontextmanager

T = TypeVar('T')

class ResourceManager(Generic[T]):
    def __init__(self):
        self.resources: Dict[str, T] = {}
        self.resource_refs: Dict[str, weakref.ref] = {}
        self.cleanup_callbacks: Dict[str, Callable] = {}
        self.lock = asyncio.Lock()
    
    async def acquire(self, 
                     resource_id: str, 
                     factory: Optional[Callable] = None) -> T:
        """Acquire resource with lazy initialization"""
        
        async with self.lock:
            # Check if resource exists
            if resource_id in self.resources:
                return self.resources[resource_id]
            
            # Create new resource
            if factory:
                resource = await factory()
            else:
                raise ValueError(f"No factory provided for resource {resource_id}")
            
            # Store resource
            self.resources[resource_id] = resource
            
            # Set up weak reference for cleanup
            def cleanup_callback(ref):
                asyncio.create_task(self._cleanup_resource(resource_id))
            
            self.resource_refs[resource_id] = weakref.ref(resource, cleanup_callback)
            
            return resource
    
    async def release(self, resource_id: str) -> None:
        """Explicitly release resource"""
        
        async with self.lock:
            if resource_id in self.resources:
                resource = self.resources[resource_id]
                
                # Call cleanup callback if exists
                if resource_id in self.cleanup_callbacks:
                    await self.cleanup_callbacks[resource_id](resource)
                
                # Remove from tracking
                del self.resources[resource_id]
                del self.resource_refs[resource_id]
    
    async def _cleanup_resource(self, resource_id: str) -> None:
        """Internal cleanup when resource is garbage collected"""
        
        if resource_id in self.cleanup_callbacks:
            try:
                # Note: resource may already be garbage collected
                await self.cleanup_callbacks[resource_id](None)
            except Exception as e:
                print(f"Cleanup callback error for {resource_id}: {e}")
        
        # Remove from tracking
        self.resources.pop(resource_id, None)
        self.cleanup_callbacks.pop(resource_id, None)
    
    def set_cleanup_callback(self, 
                           resource_id: str, 
                           callback: Callable[[T], None]) -> None:
        """Set cleanup callback for resource"""
        
        self.cleanup_callbacks[resource_id] = callback
    
    async def cleanup_all(self) -> None:
        """Clean up all resources"""
        
        async with self.lock:
            for resource_id in list(self.resources.keys()):
                await self.release(resource_id)
    
    @asynccontextmanager
    async def managed_resource(self, 
                             resource_id: str, 
                             factory: Optional[Callable] = None) -> AsyncContextManager[T]:
        """Context manager for automatic resource cleanup"""
        
        resource = await self.acquire(resource_id, factory)
        try:
            yield resource
        finally:
            await self.release(resource_id)
```

### Memory-Efficient Data Structures

```python
import sys
from typing import Any, Iterator, List, Optional
from collections import deque

class MemoryEfficientList:
    """Memory-efficient list with chunked storage"""
    
    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size
        self.chunks: List[List[Any]] = []
        self.size = 0
    
    def append(self, item: Any) -> None:
        """Append item to list"""
        
        if not self.chunks or len(self.chunks[-1]) >= self.chunk_size:
            self.chunks.append([])
        
        self.chunks[-1].append(item)
        self.size += 1
    
    def __getitem__(self, index: int) -> Any:
        """Get item by index"""
        
        if index < 0 or index >= self.size:
            raise IndexError("Index out of range")
        
        chunk_index = index // self.chunk_size
        item_index = index % self.chunk_size
        
        return self.chunks[chunk_index][item_index]
    
    def __len__(self) -> int:
        return self.size
    
    def __iter__(self) -> Iterator[Any]:
        """Iterate over all items"""
        
        for chunk in self.chunks:
            for item in chunk:
                yield item
    
    def memory_usage(self) -> int:
        """Calculate approximate memory usage"""
        
        total_size = 0
        for chunk in self.chunks:
            total_size += sys.getsizeof(chunk)
            for item in chunk:
                total_size += sys.getsizeof(item)
        
        return total_size

class BoundedDeque:
    """Bounded deque with automatic eviction"""
    
    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self.data = deque(maxlen=maxsize)
        self.evicted_count = 0
    
    def append(self, item: Any) -> Optional[Any]:
        """Append item, returning evicted item if any"""
        
        evicted = None
        if len(self.data) >= self.maxsize:
            evicted = self.data[0]
            self.evicted_count += 1
        
        self.data.append(item)
        return evicted
    
    def appendleft(self, item: Any) -> Optional[Any]:
        """Append item to left, returning evicted item if any"""
        
        evicted = None
        if len(self.data) >= self.maxsize:
            evicted = self.data[-1]
            self.evicted_count += 1
        
        self.data.appendleft(item)
        return evicted
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get deque statistics"""
        
        return {
            'size': len(self.data),
            'maxsize': self.maxsize,
            'evicted_count': self.evicted_count,
            'utilization': len(self.data) / self.maxsize
        }
```

## Configuration Guidelines

### Memory Limits by Environment

#### Development Environment
```python
# Relaxed limits for development
memory_config = {
    'cache_size': 1000,
    'alert_threshold': 200,  # MB
    'cleanup_threshold': 150,  # MB
    'monitoring_interval': 30.0  # seconds
}
```

#### Production Environment
```python
# Strict limits for production
memory_config = {
    'cache_size': 10000,
    'alert_threshold': 500,  # MB
    'cleanup_threshold': 400,  # MB
    'monitoring_interval': 10.0  # seconds
}
```

#### High-Memory Environment
```python
# Generous limits for high-memory systems
memory_config = {
    'cache_size': 50000,
    'alert_threshold': 2000,  # MB
    'cleanup_threshold': 1500,  # MB
    'monitoring_interval': 60.0  # seconds
}
```

## Testing Strategy

### Memory Leak Tests
```python
import pytest
import time
import gc

class TestMemoryLeaks:
    def test_bounded_cache_memory_leak(self):
        """Test that bounded cache doesn't leak memory"""
        
        cache = BoundedCache(max_size=1000)
        
        # Initial memory baseline
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Add many items
        for i in range(10000):
            cache.put(f"key_{i}", f"value_{i}")
        
        # Force cleanup
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Should not have significant object growth
        growth = final_objects - initial_objects
        assert growth < 2000, f"Too many objects created: {growth}"
    
    def test_resource_manager_cleanup(self):
        """Test that resource manager cleans up properly"""
        
        manager = ResourceManager()
        
        # Create resources
        for i in range(100):
            resource = await manager.acquire(f"resource_{i}", lambda: {"data": i})
        
        # Release all resources
        await manager.cleanup_all()
        
        # Should have no resources left
        assert len(manager.resources) == 0
        assert len(manager.resource_refs) == 0
```

### Performance Tests
```python
class TestMemoryPerformance:
    def test_cache_performance(self):
        """Test cache performance under load"""
        
        cache = BoundedCache(max_size=10000)
        
        # Measure put performance
        start_time = time.time()
        for i in range(10000):
            cache.put(f"key_{i}", f"value_{i}")
        put_time = time.time() - start_time
        
        # Measure get performance
        start_time = time.time()
        for i in range(10000):
            cache.get(f"key_{i}")
        get_time = time.time() - start_time
        
        # Performance assertions
        assert put_time < 1.0, f"Put operations too slow: {put_time}s"
        assert get_time < 0.5, f"Get operations too slow: {get_time}s"
```

## Monitoring and Observability

### Memory Dashboards
- Real-time memory usage graphs
- Cache hit/miss rates
- Garbage collection frequency
- Memory leak detection alerts

### Key Metrics
```python
# Memory usage metrics
memory_usage_mb = gauge('memory_usage_mb')
memory_growth_rate = gauge('memory_growth_rate_mb_per_hour')

# Cache metrics
cache_hit_rate = gauge('cache_hit_rate')
cache_eviction_rate = gauge('cache_eviction_rate')
cache_utilization = gauge('cache_utilization')

# Resource metrics
active_resources = gauge('active_resources')
resource_creation_rate = gauge('resource_creation_rate')
resource_cleanup_rate = gauge('resource_cleanup_rate')
```

## Consequences

### Positive
- **Predictable Memory Usage**: Bounded collections prevent runaway growth
- **Operational Stability**: Fewer memory-related crashes
- **Better Performance**: Reduced GC pressure
- **Debugging Capability**: Clear memory usage insights
- **Scalability**: Supports larger deployments

### Negative
- **Configuration Complexity**: More parameters to tune
- **Potential Cache Misses**: Bounded caches may evict useful data
- **Monitoring Overhead**: Additional CPU/memory for monitoring
- **Development Complexity**: More sophisticated memory management

### Neutral
- **Memory Efficiency**: Trade-off between memory usage and performance
- **Eviction Policies**: Different policies suit different use cases

## Migration Strategy

1. **Phase 1**: Implement bounded cache system
2. **Phase 2**: Add memory monitoring
3. **Phase 3**: Integrate resource management
4. **Phase 4**: Replace unbounded collections
5. **Phase 5**: Optimize and tune for production

## Related ADRs

- [ADR-001: Event System Unification](ADR-001-event-system-unification.md)
- [ADR-002: Authentication Handler Design](ADR-002-authentication-handler-design.md)
- [ADR-003: Connection Pooling Architecture](ADR-003-connection-pooling-architecture.md)

## References

- [Python Memory Management](https://docs.python.org/3/library/gc.html)
- [Memory Profiling Best Practices](../memory_profiling_guide.md)
- [Cache Design Patterns](../cache_design_patterns.md)
- [Resource Management Patterns](../resource_management_patterns.md)

---

**Author**: SpacetimeDB Python SDK Team  
**Date**: 2024-01-20  
**Last Updated**: 2024-01-28  
**Status**: Accepted and Implemented