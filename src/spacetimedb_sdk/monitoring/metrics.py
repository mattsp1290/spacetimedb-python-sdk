"""
Performance metrics data structures and collection utilities.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import threading


@dataclass
class EventMetrics:
    """Metrics for event system performance."""
    total_events: int = 0
    avg_processing_time: float = 0.0
    events_per_second: float = 0.0
    failed_events: int = 0
    handler_performance: Dict[str, float] = field(default_factory=dict)
    batched_events: int = 0
    batch_efficiency: float = 0.0
    queue_depth: int = 0
    max_queue_depth: int = 0


@dataclass
class ConnectionMetrics:
    """Metrics for connection performance."""
    total_connections: int = 0
    active_connections: int = 0
    avg_connection_time: float = 0.0
    connection_success_rate: float = 1.0
    reconnection_count: int = 0
    websocket_frames_sent: int = 0
    websocket_frames_received: int = 0
    avg_frame_size: float = 0.0
    connection_pool_utilization: float = 0.0


@dataclass
class MemoryMetrics:
    """Metrics for memory usage."""
    current_usage: int = 0
    peak_usage: int = 0
    allocated_objects: int = 0
    deallocated_objects: int = 0
    memory_efficiency: float = 0.0
    gc_collections: int = 0
    cache_hit_rate: float = 0.0
    cache_size: int = 0


@dataclass
class PoolMetrics:
    """Metrics for object pools."""
    pool_name: str = ""
    current_size: int = 0
    max_size: int = 0
    min_size: int = 0
    acquisitions: int = 0
    releases: int = 0
    pool_hits: int = 0
    pool_misses: int = 0
    avg_wait_time: float = 0.0
    utilization_rate: float = 0.0


@dataclass
class PerformanceReport:
    """Comprehensive performance report."""
    timestamp: float = field(default_factory=time.time)
    event_metrics: EventMetrics = field(default_factory=EventMetrics)
    connection_metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    memory_metrics: MemoryMetrics = field(default_factory=MemoryMetrics)
    pool_metrics: Dict[str, PoolMetrics] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class MetricsCollector:
    """Thread-safe metrics collection utility."""
    
    def __init__(self, max_history: int = 1000):
        self._lock = threading.RLock()
        self.max_history = max_history
        self._event_times: deque = deque(maxlen=max_history)
        self._connection_times: deque = deque(maxlen=max_history)
        self._memory_samples: deque = deque(maxlen=max_history)
        self._counters: Dict[str, int] = defaultdict(int)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._start_times: Dict[str, float] = {}
        
    def increment_counter(self, name: str, value: int = 1) -> None:
        """Thread-safe counter increment."""
        with self._lock:
            self._counters[name] += value
    
    def get_counter(self, name: str) -> int:
        """Get counter value thread-safely."""
        with self._lock:
            return self._counters[name]
    
    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        with self._lock:
            self._start_times[name] = time.perf_counter()
    
    def end_timer(self, name: str) -> float:
        """End a named timer and return elapsed time."""
        end_time = time.perf_counter()
        with self._lock:
            if name in self._start_times:
                elapsed = end_time - self._start_times[name]
                self._timers[name].append(elapsed)
                del self._start_times[name]
                return elapsed
            return 0.0
    
    def get_avg_time(self, name: str) -> float:
        """Get average time for a named timer."""
        with self._lock:
            times = self._timers.get(name, [])
            return sum(times) / len(times) if times else 0.0
    
    def record_event_time(self, processing_time: float) -> None:
        """Record event processing time."""
        with self._lock:
            self._event_times.append(processing_time)
    
    def record_connection_time(self, connection_time: float) -> None:
        """Record connection setup time."""
        with self._lock:
            self._connection_times.append(connection_time)
    
    def record_memory_sample(self, memory_usage: int) -> None:
        """Record memory usage sample."""
        with self._lock:
            self._memory_samples.append(memory_usage)
    
    def get_event_metrics(self) -> EventMetrics:
        """Calculate current event metrics."""
        with self._lock:
            total_events = self.get_counter('events_processed')
            failed_events = self.get_counter('events_failed')
            batched_events = self.get_counter('events_batched')
            
            # Calculate average processing time
            avg_time = 0.0
            if self._event_times:
                avg_time = sum(self._event_times) / len(self._event_times)
            
            # Calculate events per second (based on recent history)
            eps = 0.0
            if len(self._event_times) > 1:
                time_window = min(60.0, len(self._event_times) * avg_time)  # 1 minute or available data
                if time_window > 0:
                    recent_events = min(len(self._event_times), int(60.0 / avg_time)) if avg_time > 0 else len(self._event_times)
                    eps = recent_events / time_window
            
            # Calculate batch efficiency
            batch_efficiency = 0.0
            if total_events > 0:
                batch_efficiency = batched_events / total_events
            
            return EventMetrics(
                total_events=total_events,
                avg_processing_time=avg_time,
                events_per_second=eps,
                failed_events=failed_events,
                batched_events=batched_events,
                batch_efficiency=batch_efficiency,
                queue_depth=self.get_counter('event_queue_depth'),
                max_queue_depth=self.get_counter('max_event_queue_depth')
            )
    
    def get_connection_metrics(self) -> ConnectionMetrics:
        """Calculate current connection metrics."""
        with self._lock:
            total_connections = self.get_counter('connections_total')
            active_connections = self.get_counter('connections_active')
            reconnections = self.get_counter('reconnections')
            frames_sent = self.get_counter('websocket_frames_sent')
            frames_received = self.get_counter('websocket_frames_received')
            
            # Calculate average connection time
            avg_conn_time = 0.0
            if self._connection_times:
                avg_conn_time = sum(self._connection_times) / len(self._connection_times)
            
            # Calculate success rate
            success_rate = 1.0
            if total_connections > 0:
                failed_connections = self.get_counter('connections_failed')
                success_rate = (total_connections - failed_connections) / total_connections
            
            # Calculate pool utilization
            pool_size = self.get_counter('connection_pool_size')
            pool_utilization = 0.0
            if pool_size > 0:
                pool_utilization = active_connections / pool_size
            
            return ConnectionMetrics(
                total_connections=total_connections,
                active_connections=active_connections,
                avg_connection_time=avg_conn_time,
                connection_success_rate=success_rate,
                reconnection_count=reconnections,
                websocket_frames_sent=frames_sent,
                websocket_frames_received=frames_received,
                connection_pool_utilization=pool_utilization
            )
    
    def get_memory_metrics(self) -> MemoryMetrics:
        """Calculate current memory metrics."""
        with self._lock:
            current_usage = self._memory_samples[-1] if self._memory_samples else 0
            peak_usage = max(self._memory_samples) if self._memory_samples else 0
            allocated = self.get_counter('objects_allocated')
            deallocated = self.get_counter('objects_deallocated')
            gc_collections = self.get_counter('gc_collections')
            cache_hits = self.get_counter('cache_hits')
            cache_misses = self.get_counter('cache_misses')
            cache_size = self.get_counter('cache_size')
            
            # Calculate efficiency
            efficiency = 0.0
            if allocated > 0:
                efficiency = deallocated / allocated
            
            # Calculate cache hit rate
            hit_rate = 0.0
            total_cache_requests = cache_hits + cache_misses
            if total_cache_requests > 0:
                hit_rate = cache_hits / total_cache_requests
            
            return MemoryMetrics(
                current_usage=current_usage,
                peak_usage=peak_usage,
                allocated_objects=allocated,
                deallocated_objects=deallocated,
                memory_efficiency=efficiency,
                gc_collections=gc_collections,
                cache_hit_rate=hit_rate,
                cache_size=cache_size
            )
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._event_times.clear()
            self._connection_times.clear()
            self._memory_samples.clear()
            self._counters.clear()
            self._timers.clear()
            self._start_times.clear()


# Global metrics collector instance
_global_collector: MetricsCollector = MetricsCollector()

def get_global_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _global_collector