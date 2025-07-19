"""
Performance monitoring and auto-tuning system for SpacetimeDB SDK.

This module provides comprehensive performance monitoring capabilities including:
- Runtime performance metrics collection
- Auto-tuning for pool sizes and configuration
- Memory usage tracking and optimization
- Performance alerts and threshold monitoring
- Integration hooks for existing components
"""

from .performance_monitor import PerformanceMonitor, monitor_performance
from .auto_tuner import AutoTuner
from .metrics import (
    EventMetrics,
    ConnectionMetrics,
    MemoryMetrics,
    PoolMetrics,
    PerformanceReport
)
from .memory_monitor import MemoryAccountant, MemoryReport
from .alerts import PerformanceAlerts, AlertThresholds
from .config import MonitoringConfig, get_monitoring_config
from .dashboard import PerformanceDashboard

__all__ = [
    'PerformanceMonitor',
    'monitor_performance',
    'AutoTuner',
    'EventMetrics',
    'ConnectionMetrics',
    'MemoryMetrics',
    'PoolMetrics',
    'PerformanceReport',
    'MemoryAccountant',
    'MemoryReport',
    'PerformanceAlerts',
    'AlertThresholds',
    'MonitoringConfig',
    'get_monitoring_config',
    'PerformanceDashboard'
]

# Global monitoring instance
_global_monitor: PerformanceMonitor = None

def get_global_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor

def enable_monitoring() -> None:
    """Enable performance monitoring globally."""
    get_global_monitor().enable()

def disable_monitoring() -> None:
    """Disable performance monitoring globally."""
    get_global_monitor().disable()

def collect_performance_report() -> PerformanceReport:
    """Collect a comprehensive performance report."""
    return get_global_monitor().generate_report()