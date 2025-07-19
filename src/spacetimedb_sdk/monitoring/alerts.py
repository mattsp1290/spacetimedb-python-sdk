"""
Performance alert system for threshold monitoring and notifications.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from collections import deque
from enum import Enum
import logging


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Performance alert data."""
    timestamp: float = field(default_factory=time.time)
    severity: AlertSeverity = AlertSeverity.WARNING
    component: str = ""
    message: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold_value: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertThresholds:
    """Configurable performance thresholds."""
    # Connection thresholds
    connection_setup_warning: float = 0.1  # 100ms
    connection_setup_error: float = 0.5    # 500ms
    connection_pool_warning: float = 0.8   # 80% utilization
    connection_pool_critical: float = 0.95 # 95% utilization
    
    # Event thresholds
    event_dispatch_warning: float = 0.0001  # 0.1ms
    event_dispatch_error: float = 0.001     # 1ms
    event_queue_warning: int = 1000         # 1000 events
    event_queue_critical: int = 10000       # 10000 events
    
    # Memory thresholds
    memory_growth_warning: float = 1024 * 1024 * 10   # 10MB/s
    memory_growth_error: float = 1024 * 1024 * 50     # 50MB/s
    memory_usage_warning: float = 0.8                  # 80% of available
    memory_usage_critical: float = 0.95                # 95% of available
    
    # Pool thresholds
    pool_exhaustion_warning: float = 0.9   # 90% utilization
    pool_wait_time_warning: float = 0.01   # 10ms wait time
    
    # WebSocket thresholds
    websocket_frame_size_warning: int = 1024 * 1024    # 1MB frames
    websocket_reconnect_warning: int = 5                # 5 reconnects
    
    # Cache thresholds
    cache_hit_rate_warning: float = 0.7    # 70% hit rate
    cache_eviction_rate_warning: float = 0.3  # 30% eviction rate


class PerformanceAlerts:
    """Performance alert management system."""
    
    def __init__(self, max_alerts: int = 1000):
        self._lock = threading.RLock()
        self.max_alerts = max_alerts
        self._alerts: deque = deque(maxlen=max_alerts)
        self._alert_counts: Dict[str, int] = {}
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._suppression_rules: Dict[str, float] = {}  # component -> min interval
        self._last_alert_time: Dict[str, float] = {}
        
    def add_alert(self, message: str, severity: AlertSeverity = AlertSeverity.WARNING,
                  component: str = "general", metric_name: str = "", metric_value: float = 0.0,
                  threshold_value: float = 0.0, context: Dict[str, Any] = None) -> None:
        """Add a new performance alert."""
        with self._lock:
            # Check suppression
            if self._should_suppress_alert(component):
                return
            
            alert = Alert(
                severity=severity,
                component=component,
                message=message,
                metric_name=metric_name,
                metric_value=metric_value,
                threshold_value=threshold_value,
                context=context or {}
            )
            
            self._alerts.append(alert)
            self._alert_counts[component] = self._alert_counts.get(component, 0) + 1
            self._last_alert_time[component] = time.time()
            
            # Trigger callbacks
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
            
            # Log alert
            self._log_alert(alert)
    
    def _should_suppress_alert(self, component: str) -> bool:
        """Check if alert should be suppressed based on rate limiting."""
        if component not in self._suppression_rules:
            return False
        
        min_interval = self._suppression_rules[component]
        last_time = self._last_alert_time.get(component, 0)
        
        return (time.time() - last_time) < min_interval
    
    def _log_alert(self, alert: Alert) -> None:
        """Log alert to appropriate logging level."""
        message = f"[{alert.component}] {alert.message}"
        
        if alert.metric_name:
            message += f" - {alert.metric_name}: {alert.metric_value:.4f}"
            if alert.threshold_value:
                message += f" (threshold: {alert.threshold_value:.4f})"
        
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(message)
        elif alert.severity == AlertSeverity.ERROR:
            logger.error(message)
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(message)
        else:
            logger.info(message)
    
    def add_callback(self, callback: Callable[[Alert], None]) -> None:
        """Add an alert callback."""
        with self._lock:
            self._alert_callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[Alert], None]) -> None:
        """Remove an alert callback."""
        with self._lock:
            try:
                self._alert_callbacks.remove(callback)
            except ValueError:
                pass
    
    def set_suppression_rule(self, component: str, min_interval: float) -> None:
        """Set minimum interval between alerts for a component."""
        with self._lock:
            self._suppression_rules[component] = min_interval
    
    def get_recent_alerts(self, limit: int = 100, severity: AlertSeverity = None,
                         component: str = None) -> List[Alert]:
        """Get recent alerts with optional filtering."""
        with self._lock:
            alerts = list(self._alerts)
            
            # Apply filters
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            if component:
                alerts = [a for a in alerts if a.component == component]
            
            # Sort by timestamp (newest first) and limit
            alerts.sort(key=lambda a: a.timestamp, reverse=True)
            return alerts[:limit]
    
    def get_alert_counts(self) -> Dict[str, int]:
        """Get alert counts by component."""
        with self._lock:
            return self._alert_counts.copy()
    
    def clear_alerts(self) -> None:
        """Clear all alerts."""
        with self._lock:
            self._alerts.clear()
            self._alert_counts.clear()
            self._last_alert_time.clear()
    
    def check_thresholds(self, metrics: Dict[str, float], thresholds: AlertThresholds) -> None:
        """Check metrics against thresholds and generate alerts."""
        # Connection metrics
        if 'connection_setup_time' in metrics:
            conn_time = metrics['connection_setup_time']
            if conn_time > thresholds.connection_setup_error:
                self.add_alert(
                    f"Connection setup time critically high",
                    AlertSeverity.ERROR,
                    "connection",
                    "connection_setup_time",
                    conn_time,
                    thresholds.connection_setup_error
                )
            elif conn_time > thresholds.connection_setup_warning:
                self.add_alert(
                    f"Connection setup time high",
                    AlertSeverity.WARNING,
                    "connection",
                    "connection_setup_time",
                    conn_time,
                    thresholds.connection_setup_warning
                )
        
        # Event metrics
        if 'event_dispatch_latency' in metrics:
            event_latency = metrics['event_dispatch_latency']
            if event_latency > thresholds.event_dispatch_error:
                self.add_alert(
                    f"Event dispatch latency critically high",
                    AlertSeverity.ERROR,
                    "event_system",
                    "event_dispatch_latency",
                    event_latency,
                    thresholds.event_dispatch_error
                )
            elif event_latency > thresholds.event_dispatch_warning:
                self.add_alert(
                    f"Event dispatch latency high",
                    AlertSeverity.WARNING,
                    "event_system",
                    "event_dispatch_latency",
                    event_latency,
                    thresholds.event_dispatch_warning
                )
        
        # Memory metrics
        if 'memory_growth_rate' in metrics:
            growth_rate = metrics['memory_growth_rate']
            if growth_rate > thresholds.memory_growth_error:
                self.add_alert(
                    f"Memory growth rate critically high",
                    AlertSeverity.ERROR,
                    "memory",
                    "memory_growth_rate",
                    growth_rate,
                    thresholds.memory_growth_error
                )
            elif growth_rate > thresholds.memory_growth_warning:
                self.add_alert(
                    f"Memory growth rate high",
                    AlertSeverity.WARNING,
                    "memory",
                    "memory_growth_rate",
                    growth_rate,
                    thresholds.memory_growth_warning
                )
        
        # Pool metrics
        if 'pool_utilization' in metrics:
            pool_util = metrics['pool_utilization']
            if pool_util > thresholds.connection_pool_critical:
                self.add_alert(
                    f"Connection pool critically exhausted",
                    AlertSeverity.CRITICAL,
                    "connection_pool",
                    "pool_utilization",
                    pool_util,
                    thresholds.connection_pool_critical
                )
            elif pool_util > thresholds.connection_pool_warning:
                self.add_alert(
                    f"Connection pool utilization high",
                    AlertSeverity.WARNING,
                    "connection_pool",
                    "pool_utilization",
                    pool_util,
                    thresholds.connection_pool_warning
                )


class AlertManager:
    """High-level alert management interface."""
    
    def __init__(self):
        self.alerts = PerformanceAlerts()
        self.thresholds = AlertThresholds()
        self._monitoring_enabled = True
        
    def enable_monitoring(self) -> None:
        """Enable alert monitoring."""
        self._monitoring_enabled = True
        
    def disable_monitoring(self) -> None:
        """Disable alert monitoring."""
        self._monitoring_enabled = False
        
    def check_performance(self, metrics: Dict[str, float]) -> None:
        """Check performance metrics and generate alerts."""
        if not self._monitoring_enabled:
            return
        
        self.alerts.check_thresholds(metrics, self.thresholds)
    
    def configure_thresholds(self, **kwargs) -> None:
        """Update alert thresholds."""
        for key, value in kwargs.items():
            if hasattr(self.thresholds, key):
                setattr(self.thresholds, key, value)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of current alert status."""
        recent_alerts = self.alerts.get_recent_alerts(100)
        
        # Count by severity
        severity_counts = {}
        for severity in AlertSeverity:
            severity_counts[severity.value] = sum(
                1 for a in recent_alerts if a.severity == severity
            )
        
        # Count by component
        component_counts = self.alerts.get_alert_counts()
        
        # Find most recent critical alerts
        critical_alerts = [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
        
        return {
            'total_alerts': len(recent_alerts),
            'severity_counts': severity_counts,
            'component_counts': component_counts,
            'recent_critical': critical_alerts[:5],
            'monitoring_enabled': self._monitoring_enabled
        }