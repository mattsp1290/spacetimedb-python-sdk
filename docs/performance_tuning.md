# SpacetimeDB Python SDK - Performance Tuning Guide

This comprehensive guide covers performance optimization techniques for the SpacetimeDB Python SDK, helping you achieve optimal performance in production environments.

## Table of Contents

1. [Connection Optimization](#connection-optimization)
2. [Memory Usage Optimization](#memory-usage-optimization)
3. [Event System Tuning](#event-system-tuning)
4. [Pool Configuration](#pool-configuration)
5. [Monitoring and Metrics](#monitoring-and-metrics)
6. [Caching Strategies](#caching-strategies)
7. [Query Optimization](#query-optimization)
8. [Async Programming Best Practices](#async-programming-best-practices)

## Connection Optimization

### Connection Pool Configuration

The connection pool is crucial for performance. Configure it based on your workload characteristics:

```python
from spacetimedb_sdk import ConnectionPool

# For latency-sensitive applications
latency_pool = ConnectionPool(
    database_url="ws://localhost:3000",
    min_size=10,           # Keep connections warm
    max_size=30,           # Allow bursts
    connection_timeout=5.0, # Quick timeout
    idle_timeout=60.0,     # Short idle timeout
    max_lifetime=1800.0,   # 30 minutes max lifetime
    tcp_nodelay=True,      # Disable Nagle's algorithm
    buffer_size=32768      # 32KB buffer
)

# For throughput-focused applications
throughput_pool = ConnectionPool(
    database_url="ws://localhost:3000",
    min_size=20,           # More persistent connections
    max_size=100,          # Higher concurrency
    connection_timeout=15.0, # Longer timeout
    idle_timeout=600.0,    # 10 minutes idle
    max_lifetime=7200.0,   # 2 hours max lifetime
    tcp_nodelay=False,     # Allow TCP buffering
    buffer_size=131072     # 128KB buffer
)
```

### Connection Tuning Parameters

#### Pool Size Optimization

Use Little's Law to calculate optimal pool size:
```
Pool Size = (Request Rate × Average Response Time) + Buffer
```

```python
class PoolOptimizer:
    def __init__(self, pool):
        self.pool = pool
        self.metrics = []
    
    def calculate_optimal_size(self, request_rate, avg_response_time, buffer_factor=1.5):
        base_size = int(request_rate * avg_response_time * buffer_factor)
        return max(5, min(base_size, 100))  # Between 5-100 connections
    
    async def auto_tune(self):
        metrics = self.pool.get_metrics()
        
        utilization = metrics['utilization']
        wait_time = metrics['avg_wait_time']
        
        if utilization > 0.9 and wait_time > 0.1:
            # Increase pool size
            new_size = min(self.pool.max_size + 5, 100)
            await self.pool.resize(max_size=new_size)
        elif utilization < 0.3 and self.pool.max_size > 10:
            # Decrease pool size
            new_size = max(self.pool.max_size - 5, 10)
            await self.pool.resize(max_size=new_size)
```

#### Connection Timeout Tuning

```python
# Adaptive timeout based on response time history
class AdaptiveTimeout:
    def __init__(self, initial_timeout=10.0):
        self.timeout = initial_timeout
        self.response_times = []
    
    def record_response_time(self, response_time):
        self.response_times.append(response_time)
        if len(self.response_times) > 100:
            self.response_times.pop(0)
    
    def get_adaptive_timeout(self):
        if not self.response_times:
            return self.timeout
        
        # Use 95th percentile + buffer
        import statistics
        p95 = statistics.quantiles(self.response_times, n=20)[18]
        return max(p95 * 2, self.timeout)
```

### Connection Health Monitoring

```python
class ConnectionHealthMonitor:
    def __init__(self, pool):
        self.pool = pool
        self.health_stats = {
            'healthy': 0,
            'unhealthy': 0,
            'recovering': 0
        }
    
    async def health_check(self):
        connections = await self.pool.get_all_connections()
        
        for conn in connections:
            try:
                await conn.ping(timeout=1.0)
                self.health_stats['healthy'] += 1
            except Exception:
                self.health_stats['unhealthy'] += 1
                # Mark for replacement
                await self.pool.replace_connection(conn)
    
    async def start_monitoring(self, interval=30):
        while True:
            await self.health_check()
            await asyncio.sleep(interval)
```

## Memory Usage Optimization

### Bounded Collections

Always use bounded collections to prevent memory leaks:

```python
from spacetimedb_sdk.bounded_cache import BoundedCache

# Configure cache with appropriate size limits
cache = BoundedCache(
    max_size=10000,        # Maximum items
    ttl=3600,             # 1 hour TTL
    eviction_policy='lru'  # Least Recently Used
)

# Monitor cache performance
cache_stats = cache.get_statistics()
if cache_stats['hit_rate'] < 0.8:
    print("Consider increasing cache size")
```

### Memory-Efficient Data Structures

```python
from collections import deque
import weakref

class MemoryOptimizedClient:
    def __init__(self, max_history=1000):
        # Use deque for bounded history
        self.query_history = deque(maxlen=max_history)
        
        # Use weak references for callbacks
        self.callbacks = weakref.WeakSet()
        
        # Use slots for memory-efficient classes
        __slots__ = ['query_history', 'callbacks', 'client']
    
    def add_callback(self, callback):
        self.callbacks.add(callback)
    
    def record_query(self, query, result):
        # Automatically removes old entries
        self.query_history.append({
            'query': query,
            'timestamp': time.time(),
            'result_size': len(result) if result else 0
        })
```

### Memory Monitoring

```python
import psutil
import gc

class MemoryMonitor:
    def __init__(self, alert_threshold=500):  # 500MB threshold
        self.process = psutil.Process()
        self.alert_threshold = alert_threshold
        self.baseline = self.get_memory_usage()
    
    def get_memory_usage(self):
        return self.process.memory_info().rss / 1024 / 1024  # MB
    
    def check_memory_usage(self):
        current = self.get_memory_usage()
        if current > self.alert_threshold:
            print(f"Memory usage high: {current:.1f}MB")
            self.force_gc()
            return True
        return False
    
    def force_gc(self):
        # Force garbage collection
        collected = gc.collect()
        print(f"GC collected {collected} objects")
        
        # Get memory after GC
        after_gc = self.get_memory_usage()
        print(f"Memory after GC: {after_gc:.1f}MB")
```

## Event System Tuning

### Event Processing Optimization

```python
from spacetimedb_sdk.events import EventManager

class OptimizedEventManager(EventManager):
    def __init__(self):
        super().__init__()
        self.batch_size = 100
        self.batch_timeout = 0.1
        self.event_buffer = []
    
    async def process_events_batch(self):
        if not self.event_buffer:
            return
        
        # Process events in batches for better performance
        events = self.event_buffer[:self.batch_size]
        self.event_buffer = self.event_buffer[self.batch_size:]
        
        # Parallel processing
        tasks = []
        for event in events:
            task = asyncio.create_task(self.process_event(event))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def emit_event(self, event):
        self.event_buffer.append(event)
        
        # Trigger batch processing
        if len(self.event_buffer) >= self.batch_size:
            await self.process_events_batch()
```

### Event Filtering Performance

```python
class PerformantEventFilter:
    def __init__(self):
        # Pre-compile regex patterns
        self.patterns = {}
        self.compiled_filters = {}
    
    def compile_filter(self, filter_name, pattern):
        import re
        self.patterns[filter_name] = re.compile(pattern)
    
    def fast_filter(self, event, filter_name):
        if filter_name not in self.patterns:
            return False
        
        pattern = self.patterns[filter_name]
        return pattern.match(event.data.get('message', '')) is not None
```

## Pool Configuration

### Dynamic Pool Sizing

```python
class DynamicConnectionPool:
    def __init__(self, base_url, initial_size=5):
        self.base_url = base_url
        self.pool = ConnectionPool(base_url, min_size=initial_size, max_size=initial_size)
        self.metrics_window = deque(maxlen=100)
        self.last_resize = time.time()
    
    async def record_metrics(self):
        metrics = self.pool.get_metrics()
        self.metrics_window.append({
            'timestamp': time.time(),
            'utilization': metrics['utilization'],
            'wait_time': metrics['avg_wait_time'],
            'active_connections': metrics['active_connections']
        })
    
    async def auto_resize(self):
        if time.time() - self.last_resize < 60:  # Don't resize too frequently
            return
        
        if len(self.metrics_window) < 10:
            return
        
        # Calculate average metrics
        avg_utilization = sum(m['utilization'] for m in self.metrics_window) / len(self.metrics_window)
        avg_wait_time = sum(m['wait_time'] for m in self.metrics_window) / len(self.metrics_window)
        
        current_size = self.pool.max_size
        
        if avg_utilization > 0.8 and avg_wait_time > 0.05:
            # Scale up
            new_size = min(current_size * 2, 100)
            await self.pool.resize(max_size=new_size)
            self.last_resize = time.time()
            print(f"Scaled up to {new_size} connections")
        
        elif avg_utilization < 0.3 and current_size > 5:
            # Scale down
            new_size = max(current_size // 2, 5)
            await self.pool.resize(max_size=new_size)
            self.last_resize = time.time()
            print(f"Scaled down to {new_size} connections")
```

### Connection Lifecycle Management

```python
class ConnectionLifecycleManager:
    def __init__(self, pool):
        self.pool = pool
        self.connection_stats = {}
    
    async def track_connection_performance(self, connection_id, operation_time):
        if connection_id not in self.connection_stats:
            self.connection_stats[connection_id] = {
                'operations': 0,
                'total_time': 0,
                'errors': 0,
                'created_at': time.time()
            }
        
        stats = self.connection_stats[connection_id]
        stats['operations'] += 1
        stats['total_time'] += operation_time
        
        # Replace slow connections
        avg_time = stats['total_time'] / stats['operations']
        if avg_time > 1.0 and stats['operations'] > 10:
            await self.pool.replace_connection(connection_id)
    
    async def cleanup_old_connections(self, max_age=3600):
        current_time = time.time()
        for conn_id, stats in self.connection_stats.items():
            if current_time - stats['created_at'] > max_age:
                await self.pool.replace_connection(conn_id)
```

## Monitoring and Metrics

### Performance Metrics Collection

```python
import time
from collections import defaultdict

class PerformanceMetrics:
    def __init__(self):
        self.metrics = defaultdict(list)
        self.counters = defaultdict(int)
        self.timers = {}
    
    def start_timer(self, name):
        self.timers[name] = time.time()
    
    def end_timer(self, name):
        if name in self.timers:
            duration = time.time() - self.timers[name]
            self.metrics[f"{name}_duration"].append(duration)
            del self.timers[name]
            return duration
        return 0
    
    def increment_counter(self, name):
        self.counters[name] += 1
    
    def get_statistics(self):
        stats = {}
        
        # Calculate averages for timing metrics
        for name, values in self.metrics.items():
            if values:
                stats[f"{name}_avg"] = sum(values) / len(values)
                stats[f"{name}_min"] = min(values)
                stats[f"{name}_max"] = max(values)
                stats[f"{name}_p95"] = sorted(values)[int(len(values) * 0.95)]
        
        # Add counters
        stats.update(self.counters)
        
        return stats
```

### Real-time Performance Dashboard

```python
class PerformanceDashboard:
    def __init__(self, client):
        self.client = client
        self.metrics = PerformanceMetrics()
        self.running = False
    
    async def start_monitoring(self):
        self.running = True
        
        while self.running:
            await self.collect_metrics()
            await self.display_metrics()
            await asyncio.sleep(5)  # Update every 5 seconds
    
    async def collect_metrics(self):
        # Collect connection pool metrics
        pool_stats = self.client.pool.get_statistics()
        
        # Collect memory metrics
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Collect event system metrics
        event_stats = self.client.event_manager.get_statistics()
        
        # Store metrics
        self.metrics.metrics['memory_usage'].append(memory_usage)
        self.metrics.metrics['pool_utilization'].append(pool_stats.get('utilization', 0))
        self.metrics.metrics['event_rate'].append(event_stats.get('events_per_second', 0))
    
    async def display_metrics(self):
        stats = self.metrics.get_statistics()
        
        print("\n" + "="*50)
        print("PERFORMANCE DASHBOARD")
        print("="*50)
        print(f"Memory Usage: {stats.get('memory_usage_avg', 0):.1f} MB")
        print(f"Pool Utilization: {stats.get('pool_utilization_avg', 0):.1%}")
        print(f"Event Rate: {stats.get('event_rate_avg', 0):.1f} events/sec")
        print(f"Query Response Time: {stats.get('query_duration_avg', 0):.3f}s")
```

## Caching Strategies

### Multi-Level Caching

```python
class MultiLevelCache:
    def __init__(self):
        # L1: In-memory cache (fastest)
        self.l1_cache = BoundedCache(max_size=1000, ttl=60)
        
        # L2: Compressed cache (larger)
        self.l2_cache = BoundedCache(max_size=10000, ttl=3600)
        
        # L3: Persistent cache (largest)
        self.l3_cache = PersistentCache(max_size=100000, ttl=86400)
    
    async def get(self, key):
        # Try L1 first
        result = self.l1_cache.get(key)
        if result is not None:
            return result
        
        # Try L2
        result = self.l2_cache.get(key)
        if result is not None:
            # Promote to L1
            self.l1_cache.put(key, result)
            return result
        
        # Try L3
        result = await self.l3_cache.get(key)
        if result is not None:
            # Promote to L2 and L1
            self.l2_cache.put(key, result)
            self.l1_cache.put(key, result)
            return result
        
        return None
    
    async def put(self, key, value):
        # Store in all levels
        self.l1_cache.put(key, value)
        self.l2_cache.put(key, value)
        await self.l3_cache.put(key, value)
```

### Cache Warming

```python
class CacheWarmer:
    def __init__(self, client, cache):
        self.client = client
        self.cache = cache
        self.warming_queries = []
    
    def add_warming_query(self, query, params=None):
        self.warming_queries.append((query, params))
    
    async def warm_cache(self):
        print("Warming cache...")
        
        tasks = []
        for query, params in self.warming_queries:
            task = asyncio.create_task(self.execute_and_cache(query, params))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        print(f"Cache warmed: {success_count}/{len(self.warming_queries)} queries")
    
    async def execute_and_cache(self, query, params):
        try:
            result = await self.client.query(query, params)
            cache_key = f"{query}:{hash(str(params))}"
            self.cache.put(cache_key, result)
            return result
        except Exception as e:
            print(f"Cache warming failed for {query}: {e}")
            raise
```

## Query Optimization

### Query Batching

```python
class QueryBatcher:
    def __init__(self, client, batch_size=10, flush_interval=0.1):
        self.client = client
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.pending_queries = []
        self.last_flush = time.time()
    
    async def add_query(self, query, params=None):
        self.pending_queries.append((query, params))
        
        if (len(self.pending_queries) >= self.batch_size or 
            time.time() - self.last_flush > self.flush_interval):
            return await self.flush_batch()
        
        return None
    
    async def flush_batch(self):
        if not self.pending_queries:
            return []
        
        batch = self.pending_queries
        self.pending_queries = []
        self.last_flush = time.time()
        
        # Execute batch
        results = await self.client.batch_query(batch)
        return results
```

### Query Result Streaming

```python
class StreamingQueryHandler:
    def __init__(self, client):
        self.client = client
    
    async def stream_large_result(self, query, params=None, chunk_size=1000):
        """Stream large query results in chunks"""
        
        # Add LIMIT and OFFSET to query
        offset = 0
        
        while True:
            chunked_query = f"{query} LIMIT {chunk_size} OFFSET {offset}"
            chunk = await self.client.query(chunked_query, params)
            
            if not chunk:
                break
            
            # Yield chunk for processing
            yield chunk
            
            offset += chunk_size
            
            # Rate limiting
            await asyncio.sleep(0.01)
```

## Async Programming Best Practices

### Efficient Async Patterns

```python
class AsyncOptimizations:
    def __init__(self, client):
        self.client = client
    
    async def concurrent_queries(self, queries):
        """Execute multiple queries concurrently"""
        
        # Create tasks
        tasks = []
        for query, params in queries:
            task = asyncio.create_task(self.client.query(query, params))
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful results from errors
        successes = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append((i, result))
            else:
                successes.append((i, result))
        
        return successes, errors
    
    async def pipeline_processing(self, items, process_func, concurrency=10):
        """Process items in a pipeline with controlled concurrency"""
        
        semaphore = asyncio.Semaphore(concurrency)
        
        async def process_item(item):
            async with semaphore:
                return await process_func(item)
        
        tasks = [asyncio.create_task(process_item(item)) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
```

### Resource Management

```python
class ResourceManager:
    def __init__(self):
        self.resources = {}
        self.locks = {}
    
    async def acquire_resource(self, resource_id, factory_func):
        """Acquire resource with lazy initialization"""
        
        if resource_id not in self.locks:
            self.locks[resource_id] = asyncio.Lock()
        
        async with self.locks[resource_id]:
            if resource_id not in self.resources:
                self.resources[resource_id] = await factory_func()
            
            return self.resources[resource_id]
    
    async def cleanup_resources(self):
        """Clean up all resources"""
        
        for resource_id, resource in self.resources.items():
            try:
                if hasattr(resource, 'close'):
                    await resource.close()
            except Exception as e:
                print(f"Error closing resource {resource_id}: {e}")
        
        self.resources.clear()
```

## Performance Testing

### Benchmark Framework

```python
class PerformanceBenchmark:
    def __init__(self, client):
        self.client = client
        self.results = []
    
    async def benchmark_operation(self, operation_name, operation_func, iterations=100):
        """Benchmark a specific operation"""
        
        times = []
        errors = 0
        
        for i in range(iterations):
            start_time = time.time()
            try:
                await operation_func()
                duration = time.time() - start_time
                times.append(duration)
            except Exception as e:
                errors += 1
        
        # Calculate statistics
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]
        else:
            avg_time = min_time = max_time = p95_time = 0
        
        result = {
            'operation': operation_name,
            'iterations': iterations,
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'p95_time': p95_time,
            'errors': errors,
            'success_rate': (iterations - errors) / iterations
        }
        
        self.results.append(result)
        return result
    
    def print_results(self):
        """Print benchmark results"""
        
        print("\nBenchmark Results:")
        print("="*80)
        print(f"{'Operation':<20} {'Avg Time':<10} {'Min':<8} {'Max':<8} {'P95':<8} {'Success':<8}")
        print("-"*80)
        
        for result in self.results:
            print(f"{result['operation']:<20} "
                  f"{result['avg_time']*1000:>8.1f}ms "
                  f"{result['min_time']*1000:>6.1f}ms "
                  f"{result['max_time']*1000:>6.1f}ms "
                  f"{result['p95_time']*1000:>6.1f}ms "
                  f"{result['success_rate']:>6.1%}")
```

This performance tuning guide provides comprehensive strategies for optimizing your SpacetimeDB Python SDK applications. Remember to:

1. **Profile first**: Always measure performance before optimizing
2. **Monitor continuously**: Set up monitoring in production
3. **Test thoroughly**: Verify that optimizations don't break functionality
4. **Document changes**: Keep track of what optimizations you've applied
5. **Review regularly**: Performance characteristics can change over time

By following these guidelines and implementing the appropriate optimizations for your use case, you can achieve significant performance improvements in your SpacetimeDB applications.