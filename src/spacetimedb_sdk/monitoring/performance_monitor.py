"""
Runtime performance monitoring and metrics collection.
"""

import time
import threading
import asyncio
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict, deque
from contextlib import contextmanager
import logging

from .metrics import (
    EventMetrics, ConnectionMetrics, MemoryMetrics, PoolMetrics, 
    PerformanceReport, MetricsCollector, get_global_collector
)
from .memory_monitor import MemoryAccountant, get_global_accountant
from .alerts import PerformanceAlerts, AlertThresholds


logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Comprehensive performance monitoring system."""
    
    def __init__(self, enable_by_default: bool = True):
        self._enabled = enable_by_default
        self._lock = threading.RLock()
        
        # Core components
        self.metrics_collector = get_global_collector()
        self.memory_accountant = get_global_accountant()
        self.alerts = PerformanceAlerts()
        
        # Monitoring state
        self._active_timers: Dict[str, float] = {}
        self._hook_registry: Dict[str, List[Callable]] = defaultdict(list)
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Performance thresholds (configurable)
        self.thresholds = AlertThresholds(
            connection_setup_warning=0.1,  # 100ms
            event_dispatch_warning=0.0001,  # 0.1ms
            memory_growth_warning=1024 * 1024 * 10,  # 10MB/sec
            pool_exhaustion_warning=0.9  # 90% utilization
        )
        
        # Start background monitoring if enabled
        if self._enabled:
            self.start_background_monitoring()
    
    def enable(self) -> None:
        """Enable performance monitoring."""
        with self._lock:
            if not self._enabled:
                self._enabled = True
                self.start_background_monitoring()
                logger.info("Performance monitoring enabled")
    
    def disable(self) -> None:
        """Disable performance monitoring."""
        with self._lock:
            if self._enabled:
                self._enabled = False
                self.stop_background_monitoring()
                logger.info("Performance monitoring disabled")
    
    @property
    def enabled(self) -> bool:
        """Check if monitoring is enabled."""
        return self._enabled
    
    def start_background_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            self._stop_monitoring.clear()
            self._monitoring_thread = threading.Thread(
                target=self._background_monitor_loop,
                daemon=True
            )
            self._monitoring_thread.start()
    
    def stop_background_monitoring(self) -> None:
        """Stop background monitoring thread."""
        if self._monitoring_thread:
            self._stop_monitoring.set()
            if self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=1.0)
    
    def _background_monitor_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                # Collect memory samples
                current_memory = self.memory_accountant.get_current_memory_usage()
                self.memory_accountant.record_allocation(0, "background_sample")
                self.metrics_collector.record_memory_sample(current_memory)
                
                # Check for performance alerts
                self._check_performance_alerts()
                
                # Sleep for monitoring interval
                self._stop_monitoring.wait(5.0)  # 5 second intervals
            except Exception as e:
                logger.error(f"Error in background monitoring: {e}")
                self._stop_monitoring.wait(10.0)  # Longer wait on error
    
    def _check_performance_alerts(self) -> None:
        """Check for performance threshold violations."""
        if not self._enabled:
            return
        
        try:
            # Check connection performance
            connection_metrics = self.metrics_collector.get_connection_metrics()
            if connection_metrics.avg_connection_time > self.thresholds.connection_setup_warning:
                self.alerts.add_alert(
                    f"Connection setup time ({connection_metrics.avg_connection_time:.3f}s) "
                    f"exceeds threshold ({self.thresholds.connection_setup_warning:.3f}s)"
                )
            
            # Check event performance
            event_metrics = self.metrics_collector.get_event_metrics()
            if event_metrics.avg_processing_time > self.thresholds.event_dispatch_warning:
                self.alerts.add_alert(
                    f"Event dispatch time ({event_metrics.avg_processing_time:.6f}s) "
                    f"exceeds threshold ({self.thresholds.event_dispatch_warning:.6f}s)"
                )
            
            # Check memory growth
            memory_growth = self.memory_accountant.get_memory_growth_rate()
            if memory_growth > self.thresholds.memory_growth_warning:
                self.alerts.add_alert(
                    f"Memory growth rate ({memory_growth / 1024 / 1024:.2f} MB/s) "
                    f"exceeds threshold ({self.thresholds.memory_growth_warning / 1024 / 1024:.2f} MB/s)"
                )
            
            # Check pool utilization
            if connection_metrics.connection_pool_utilization > self.thresholds.pool_exhaustion_warning:
                self.alerts.add_alert(
                    f"Connection pool utilization ({connection_metrics.connection_pool_utilization:.1%}) "
                    f"exceeds threshold ({self.thresholds.pool_exhaustion_warning:.1%})"
                )
                
        except Exception as e:
            logger.error(f"Error checking performance alerts: {e}")
    
    @contextmanager
    def measure_time(self, operation_name: str):
        """Context manager for measuring operation time."""
        if not self._enabled:
            yield
            return
        
        start_time = time.perf_counter()
        self.metrics_collector.start_timer(operation_name)
        
        try:
            yield
        finally:
            elapsed = self.metrics_collector.end_timer(operation_name)
            
            # Record in appropriate category
            if "connection" in operation_name.lower():
                self.metrics_collector.record_connection_time(elapsed)
            elif "event" in operation_name.lower():
                self.metrics_collector.record_event_time(elapsed)
    
    def record_connection_setup(self, duration: float, success: bool = True) -> None:
        """Record connection setup metrics."""
        if not self._enabled:
            return
        
        self.metrics_collector.record_connection_time(duration)
        self.metrics_collector.increment_counter('connections_total')
        
        if success:
            self.metrics_collector.increment_counter('connections_active')
        else:
            self.metrics_collector.increment_counter('connections_failed')
    
    def record_connection_close(self) -> None:
        """Record connection close."""
        if not self._enabled:
            return
        
        current_active = self.metrics_collector.get_counter('connections_active')
        if current_active > 0:
            self.metrics_collector.increment_counter('connections_active', -1)
    
    def record_event_processing(self, duration: float, event_type: str = "general", success: bool = True) -> None:
        """Record event processing metrics."""
        if not self._enabled:
            return
        
        self.metrics_collector.record_event_time(duration)
        self.metrics_collector.increment_counter('events_processed')
        
        if not success:
            self.metrics_collector.increment_counter('events_failed')
        
        # Update handler performance
        if event_type in self.metrics_collector._timers:
            self.metrics_collector._timers[f"handler_{event_type}"].append(duration)
    
    def record_batch_processing(self, batch_size: int, total_duration: float) -> None:
        """Record batch processing metrics."""
        if not self._enabled:
            return
        
        self.metrics_collector.increment_counter('events_batched', batch_size)
        avg_per_event = total_duration / batch_size if batch_size > 0 else 0
        
        for _ in range(batch_size):
            self.metrics_collector.record_event_time(avg_per_event)
    
    def record_websocket_frame(self, sent: bool = True, size: int = 0) -> None:
        """Record WebSocket frame metrics."""
        if not self._enabled:
            return
        
        if sent:
            self.metrics_collector.increment_counter('websocket_frames_sent')
        else:
            self.metrics_collector.increment_counter('websocket_frames_received')
        
        # Update average frame size
        if size > 0:
            current_avg = self.metrics_collector.get_avg_time('frame_size')
            frame_count = (self.metrics_collector.get_counter('websocket_frames_sent') + 
                          self.metrics_collector.get_counter('websocket_frames_received'))
            
            if frame_count > 0:
                new_avg = ((current_avg * (frame_count - 1)) + size) / frame_count
                self.metrics_collector._timers['frame_size'] = [new_avg]
    
    def record_pool_metrics(self, pool_name: str, current_size: int, max_size: int, 
                           acquisition_time: float = 0.0) -> None:
        """Record pool utilization metrics."""
        if not self._enabled:
            return
        
        # Store pool metrics for later retrieval
        utilization = current_size / max_size if max_size > 0 else 0.0
        
        self.metrics_collector.increment_counter(f'pool_{pool_name}_acquisitions')
        if acquisition_time > 0:
            self.metrics_collector._timers[f'pool_{pool_name}_wait_time'].append(acquisition_time)
        
        # Store current pool state
        self.metrics_collector._counters[f'pool_{pool_name}_size'] = current_size
        self.metrics_collector._counters[f'pool_{pool_name}_max'] = max_size
        self.metrics_collector._counters[f'pool_{pool_name}_utilization'] = int(utilization * 100)
    
    def record_cache_access(self, hit: bool = True, cache_name: str = "default") -> None:
        """Record cache access metrics."""
        if not self._enabled:
            return
        
        if hit:
            self.metrics_collector.increment_counter('cache_hits')
            self.metrics_collector.increment_counter(f'cache_{cache_name}_hits')
        else:
            self.metrics_collector.increment_counter('cache_misses')
            self.metrics_collector.increment_counter(f'cache_{cache_name}_misses')
    
    def add_monitoring_hook(self, component: str, hook: Callable) -> None:
        """Add a monitoring hook for a specific component."""
        with self._lock:
            self._hook_registry[component].append(hook)
    
    def remove_monitoring_hook(self, component: str, hook: Callable) -> None:
        """Remove a monitoring hook."""
        with self._lock:
            if component in self._hook_registry:
                try:
                    self._hook_registry[component].remove(hook)
                except ValueError:
                    pass
    
    def trigger_hooks(self, component: str, **kwargs) -> None:
        """Trigger all hooks for a component."""
        if not self._enabled:
            return
        
        with self._lock:
            hooks = self._hook_registry.get(component, [])
            for hook in hooks:
                try:
                    hook(**kwargs)
                except Exception as e:
                    logger.error(f"Error in monitoring hook for {component}: {e}")
    
    def collect_metrics(self) -> Dict[str, float]:
        """Collect current performance metrics."""
        if not self._enabled:
            return {}
        
        event_metrics = self.metrics_collector.get_event_metrics()
        connection_metrics = self.metrics_collector.get_connection_metrics()
        memory_metrics = self.metrics_collector.get_memory_metrics()
        
        return {
            "connection_setup_time": connection_metrics.avg_connection_time,
            "event_dispatch_latency": event_metrics.avg_processing_time,
            "memory_usage": memory_metrics.current_usage,
            "pool_utilization": connection_metrics.connection_pool_utilization,
            "events_per_second": event_metrics.events_per_second,
            "cache_hit_rate": memory_metrics.cache_hit_rate,
            "memory_growth_rate": self.memory_accountant.get_memory_growth_rate()
        }
    
    def generate_report(self) -> PerformanceReport:
        """Generate comprehensive performance report."""
        if not self._enabled:
            return PerformanceReport()
        
        event_metrics = self.metrics_collector.get_event_metrics()
        connection_metrics = self.metrics_collector.get_connection_metrics()
        memory_metrics = self.metrics_collector.get_memory_metrics()
        
        # Collect pool metrics
        pool_metrics = {}
        for counter_name, value in self.metrics_collector._counters.items():
            if counter_name.startswith('pool_') and counter_name.endswith('_size'):
                pool_name = counter_name.replace('pool_', '').replace('_size', '')
                max_size = self.metrics_collector.get_counter(f'pool_{pool_name}_max')
                acquisitions = self.metrics_collector.get_counter(f'pool_{pool_name}_acquisitions')
                avg_wait = self.metrics_collector.get_avg_time(f'pool_{pool_name}_wait_time')
                utilization = self.metrics_collector.get_counter(f'pool_{pool_name}_utilization') / 100.0
                
                pool_metrics[pool_name] = PoolMetrics(
                    pool_name=pool_name,
                    current_size=value,
                    max_size=max_size,
                    acquisitions=acquisitions,
                    avg_wait_time=avg_wait,
                    utilization_rate=utilization
                )
        
        # Get recent alerts
        recent_alerts = self.alerts.get_recent_alerts()
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            event_metrics, connection_metrics, memory_metrics
        )
        
        return PerformanceReport(
            event_metrics=event_metrics,
            connection_metrics=connection_metrics,
            memory_metrics=memory_metrics,
            pool_metrics=pool_metrics,
            alerts=recent_alerts,
            recommendations=recommendations
        )
    
    def _generate_recommendations(self, event_metrics: EventMetrics, 
                                connection_metrics: ConnectionMetrics,
                                memory_metrics: MemoryMetrics) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        # Event processing recommendations
        if event_metrics.avg_processing_time > 0.001:  # 1ms
            recommendations.append(
                "Consider optimizing event handlers or implementing event batching"
            )
        
        if event_metrics.batch_efficiency < 0.5:
            recommendations.append(
                "Increase event batching to improve throughput"
            )
        
        # Connection recommendations
        if connection_metrics.avg_connection_time > 0.2:  # 200ms
            recommendations.append(
                "Consider implementing connection pooling or optimizing connection setup"
            )
        
        if connection_metrics.connection_pool_utilization > 0.8:
            recommendations.append(
                "Consider increasing connection pool size"
            )
        
        # Memory recommendations
        if memory_metrics.cache_hit_rate < 0.8:
            recommendations.append(
                "Optimize caching strategy to improve hit rate"
            )
        
        memory_growth = self.memory_accountant.get_memory_growth_rate()
        if memory_growth > 1024 * 1024:  # 1MB/s
            recommendations.append(
                "Investigate memory leaks - high memory growth rate detected"
            )
        
        return recommendations
    
    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        with self._lock:
            self.metrics_collector.reset_metrics()
            self.memory_accountant.reset_statistics()
            self.alerts.clear_alerts()
            logger.info("Performance metrics reset")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_background_monitoring()


# Convenience decorators for performance monitoring
def monitor_performance(operation_name: str = None):
    """Decorator for monitoring function performance."""
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        def wrapper(*args, **kwargs):
            monitor = get_global_monitor()
            if not monitor.enabled:
                return func(*args, **kwargs)
            
            with monitor.measure_time(operation_name):
                return func(*args, **kwargs)
        
        async def async_wrapper(*args, **kwargs):
            monitor = get_global_monitor()
            if not monitor.enabled:
                return await func(*args, **kwargs)
            
            with monitor.measure_time(operation_name):
                return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator


# Global performance monitor
_global_monitor: PerformanceMonitor = None

def get_global_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor