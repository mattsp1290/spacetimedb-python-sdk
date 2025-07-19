"""
Performance monitoring dashboard and reporting utilities.
"""

import time
import json
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional, TextIO
from dataclasses import asdict
from pathlib import Path
import threading
from collections import defaultdict
import logging

from .metrics import (
    EventMetrics, ConnectionMetrics, MemoryMetrics, PoolMetrics, 
    PerformanceReport
)
from .memory_monitor import MemoryReport
from .alerts import Alert, AlertSeverity


logger = logging.getLogger(__name__)


class PerformanceDashboard:
    """Interactive performance monitoring dashboard."""
    
    def __init__(self, export_path: str = "./monitoring_data"):
        self._lock = threading.RLock()
        self.export_path = Path(export_path)
        self.export_path.mkdir(parents=True, exist_ok=True)
        
        # Historical data storage
        self._performance_history: List[PerformanceReport] = []
        self._memory_history: List[MemoryReport] = []
        self._alert_history: List[Alert] = []
        self._custom_metrics: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        
        # Export settings
        self._export_enabled = False
        self._export_format = "json"
        self._export_interval = 300.0  # 5 minutes
        self._last_export = 0
        
    def record_performance_report(self, report: PerformanceReport) -> None:
        """Record a performance report."""
        with self._lock:
            self._performance_history.append(report)
            
            # Limit history size
            if len(self._performance_history) > 1000:
                self._performance_history = self._performance_history[-1000:]
    
    def record_memory_report(self, report: MemoryReport) -> None:
        """Record a memory report."""
        with self._lock:
            self._memory_history.append(report)
            
            # Limit history size
            if len(self._memory_history) > 1000:
                self._memory_history = self._memory_history[-1000:]
    
    def record_alert(self, alert: Alert) -> None:
        """Record an alert."""
        with self._lock:
            self._alert_history.append(alert)
            
            # Limit history size
            if len(self._alert_history) > 1000:
                self._alert_history = self._alert_history[-1000:]
    
    def record_custom_metric(self, name: str, value: float, timestamp: float = None) -> None:
        """Record a custom metric value."""
        with self._lock:
            if timestamp is None:
                timestamp = time.time()
            
            self._custom_metrics[name].append((timestamp, value))
            
            # Limit history per metric
            if len(self._custom_metrics[name]) > 1000:
                self._custom_metrics[name] = self._custom_metrics[name][-1000:]
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current performance status summary."""
        with self._lock:
            if not self._performance_history:
                return {"status": "no_data"}
            
            latest_report = self._performance_history[-1]
            
            # Calculate trends
            event_trend = self._calculate_trend([r.event_metrics.events_per_second 
                                               for r in self._performance_history[-10:]])
            memory_trend = self._calculate_trend([r.memory_metrics.current_usage 
                                                for r in self._performance_history[-10:]])
            
            # Count recent alerts by severity
            recent_alerts = [a for a in self._alert_history 
                           if time.time() - a.timestamp < 300]  # Last 5 minutes
            alert_counts = defaultdict(int)
            for alert in recent_alerts:
                alert_counts[alert.severity.value] += 1
            
            return {
                "timestamp": latest_report.timestamp,
                "summary": {
                    "events_per_second": latest_report.event_metrics.events_per_second,
                    "active_connections": latest_report.connection_metrics.active_connections,
                    "memory_usage_mb": latest_report.memory_metrics.current_usage / (1024 * 1024),
                    "cache_hit_rate": latest_report.memory_metrics.cache_hit_rate,
                },
                "trends": {
                    "event_trend": event_trend,
                    "memory_trend": memory_trend,
                },
                "alerts": {
                    "total": len(recent_alerts),
                    "by_severity": dict(alert_counts)
                },
                "recommendations": latest_report.recommendations[:5]
            }
    
    def get_performance_timeline(self, duration_seconds: float = 3600) -> Dict[str, List[Dict]]:
        """Get performance metrics timeline."""
        with self._lock:
            cutoff_time = time.time() - duration_seconds
            
            # Filter reports within duration
            recent_reports = [r for r in self._performance_history 
                            if r.timestamp > cutoff_time]
            
            if not recent_reports:
                return {}
            
            # Extract time series data
            timeline = {
                "timestamps": [r.timestamp for r in recent_reports],
                "events": {
                    "events_per_second": [r.event_metrics.events_per_second for r in recent_reports],
                    "avg_processing_time": [r.event_metrics.avg_processing_time for r in recent_reports],
                    "failed_events": [r.event_metrics.failed_events for r in recent_reports],
                },
                "connections": {
                    "active_connections": [r.connection_metrics.active_connections for r in recent_reports],
                    "avg_connection_time": [r.connection_metrics.avg_connection_time for r in recent_reports],
                    "pool_utilization": [r.connection_metrics.connection_pool_utilization for r in recent_reports],
                },
                "memory": {
                    "current_usage": [r.memory_metrics.current_usage for r in recent_reports],
                    "cache_hit_rate": [r.memory_metrics.cache_hit_rate for r in recent_reports],
                    "gc_collections": [r.memory_metrics.gc_collections for r in recent_reports],
                }
            }
            
            return timeline
    
    def get_alert_summary(self, duration_seconds: float = 3600) -> Dict[str, Any]:
        """Get alert summary for specified duration."""
        with self._lock:
            cutoff_time = time.time() - duration_seconds
            recent_alerts = [a for a in self._alert_history if a.timestamp > cutoff_time]
            
            # Group by component and severity
            by_component = defaultdict(list)
            by_severity = defaultdict(list)
            
            for alert in recent_alerts:
                by_component[alert.component].append(alert)
                by_severity[alert.severity.value].append(alert)
            
            # Find most frequent alerts
            alert_messages = defaultdict(int)
            for alert in recent_alerts:
                alert_messages[alert.message] += 1
            
            top_alerts = sorted(alert_messages.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "total_alerts": len(recent_alerts),
                "by_component": {comp: len(alerts) for comp, alerts in by_component.items()},
                "by_severity": {sev: len(alerts) for sev, alerts in by_severity.items()},
                "top_alerts": [{"message": msg, "count": count} for msg, count in top_alerts],
                "recent_critical": [asdict(a) for a in recent_alerts 
                                  if a.severity == AlertSeverity.CRITICAL][:5]
            }
    
    def generate_report(self, report_type: str = "summary") -> str:
        """Generate a formatted performance report."""
        with self._lock:
            if report_type == "summary":
                return self._generate_summary_report()
            elif report_type == "detailed":
                return self._generate_detailed_report()
            elif report_type == "alerts":
                return self._generate_alerts_report()
            else:
                return f"Unknown report type: {report_type}"
    
    def _generate_summary_report(self) -> str:
        """Generate a summary performance report."""
        status = self.get_current_status()
        
        if status.get("status") == "no_data":
            return "No performance data available"
        
        report_lines = [
            "=== Performance Summary ===",
            f"Timestamp: {datetime.fromtimestamp(status['timestamp']).isoformat()}",
            "",
            "Current Metrics:",
            f"  Events/sec: {status['summary']['events_per_second']:.2f}",
            f"  Active Connections: {status['summary']['active_connections']}",
            f"  Memory Usage: {status['summary']['memory_usage_mb']:.2f} MB",
            f"  Cache Hit Rate: {status['summary']['cache_hit_rate']:.1%}",
            "",
            "Trends:",
            f"  Event Processing: {status['trends']['event_trend']}",
            f"  Memory Usage: {status['trends']['memory_trend']}",
            "",
            f"Recent Alerts: {status['alerts']['total']}",
        ]
        
        if status['alerts']['by_severity']:
            for severity, count in status['alerts']['by_severity'].items():
                report_lines.append(f"  {severity}: {count}")
        
        if status['recommendations']:
            report_lines.extend(["", "Recommendations:"])
            for i, rec in enumerate(status['recommendations'], 1):
                report_lines.append(f"  {i}. {rec}")
        
        return "\n".join(report_lines)
    
    def _generate_detailed_report(self) -> str:
        """Generate a detailed performance report."""
        if not self._performance_history:
            return "No performance data available"
        
        latest = self._performance_history[-1]
        report_lines = [
            "=== Detailed Performance Report ===",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "Event System Performance:",
            f"  Total Events: {latest.event_metrics.total_events:,}",
            f"  Events/sec: {latest.event_metrics.events_per_second:.2f}",
            f"  Avg Processing Time: {latest.event_metrics.avg_processing_time*1000:.3f} ms",
            f"  Failed Events: {latest.event_metrics.failed_events}",
            f"  Batch Efficiency: {latest.event_metrics.batch_efficiency:.1%}",
            f"  Queue Depth: {latest.event_metrics.queue_depth}/{latest.event_metrics.max_queue_depth}",
            "",
            "Connection Performance:",
            f"  Total Connections: {latest.connection_metrics.total_connections}",
            f"  Active Connections: {latest.connection_metrics.active_connections}",
            f"  Avg Connection Time: {latest.connection_metrics.avg_connection_time*1000:.1f} ms",
            f"  Success Rate: {latest.connection_metrics.connection_success_rate:.1%}",
            f"  Reconnections: {latest.connection_metrics.reconnection_count}",
            f"  Pool Utilization: {latest.connection_metrics.connection_pool_utilization:.1%}",
            "",
            "Memory Performance:",
            f"  Current Usage: {latest.memory_metrics.current_usage/(1024*1024):.2f} MB",
            f"  Peak Usage: {latest.memory_metrics.peak_usage/(1024*1024):.2f} MB",
            f"  Cache Hit Rate: {latest.memory_metrics.cache_hit_rate:.1%}",
            f"  GC Collections: {latest.memory_metrics.gc_collections}",
            f"  Memory Efficiency: {latest.memory_metrics.memory_efficiency:.1%}",
        ]
        
        if latest.pool_metrics:
            report_lines.extend(["", "Pool Performance:"])
            for pool_name, metrics in latest.pool_metrics.items():
                report_lines.extend([
                    f"  {pool_name}:",
                    f"    Size: {metrics.current_size}/{metrics.max_size}",
                    f"    Utilization: {metrics.utilization_rate:.1%}",
                    f"    Acquisitions: {metrics.acquisitions}",
                    f"    Avg Wait Time: {metrics.avg_wait_time*1000:.1f} ms"
                ])
        
        return "\n".join(report_lines)
    
    def _generate_alerts_report(self) -> str:
        """Generate an alerts report."""
        summary = self.get_alert_summary(3600)  # Last hour
        
        report_lines = [
            "=== Alerts Report (Last Hour) ===",
            f"Total Alerts: {summary['total_alerts']}",
            "",
            "By Severity:",
        ]
        
        for severity in ['critical', 'error', 'warning', 'info']:
            count = summary['by_severity'].get(severity, 0)
            if count > 0:
                report_lines.append(f"  {severity.upper()}: {count}")
        
        report_lines.extend(["", "By Component:"])
        for component, count in sorted(summary['by_component'].items(), 
                                     key=lambda x: x[1], reverse=True):
            report_lines.append(f"  {component}: {count}")
        
        if summary['top_alerts']:
            report_lines.extend(["", "Most Frequent Alerts:"])
            for i, alert_info in enumerate(summary['top_alerts'][:5], 1):
                report_lines.append(f"  {i}. {alert_info['message']} ({alert_info['count']} times)")
        
        if summary['recent_critical']:
            report_lines.extend(["", "Recent Critical Alerts:"])
            for alert in summary['recent_critical']:
                timestamp = datetime.fromtimestamp(alert['timestamp']).strftime('%H:%M:%S')
                report_lines.append(f"  [{timestamp}] {alert['message']}")
        
        return "\n".join(report_lines)
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from a series of values."""
        if len(values) < 2:
            return "stable"
        
        # Simple trend detection
        avg_first_half = sum(values[:len(values)//2]) / (len(values)//2)
        avg_second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        change_percent = ((avg_second_half - avg_first_half) / avg_first_half * 100) if avg_first_half > 0 else 0
        
        if change_percent > 10:
            return f"increasing (+{change_percent:.1f}%)"
        elif change_percent < -10:
            return f"decreasing ({change_percent:.1f}%)"
        else:
            return "stable"
    
    def export_data(self, format: str = "json", filename: Optional[str] = None) -> str:
        """Export performance data to file."""
        with self._lock:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"performance_data_{timestamp}.{format}"
            
            filepath = self.export_path / filename
            
            try:
                if format == "json":
                    self._export_json(filepath)
                elif format == "csv":
                    self._export_csv(filepath)
                else:
                    raise ValueError(f"Unsupported export format: {format}")
                
                logger.info(f"Performance data exported to {filepath}")
                return str(filepath)
                
            except Exception as e:
                logger.error(f"Error exporting data: {e}")
                raise
    
    def _export_json(self, filepath: Path) -> None:
        """Export data as JSON."""
        data = {
            "export_timestamp": time.time(),
            "performance_reports": [asdict(r) for r in self._performance_history[-100:]],
            "memory_reports": [asdict(r) for r in self._memory_history[-100:]],
            "alerts": [asdict(a) for a in self._alert_history[-100:]],
            "custom_metrics": dict(self._custom_metrics)
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _export_csv(self, filepath: Path) -> None:
        """Export data as CSV files."""
        # Export performance metrics
        perf_file = filepath.with_suffix('.performance.csv')
        with open(perf_file, 'w', newline='') as f:
            if self._performance_history:
                writer = csv.writer(f)
                # Header
                writer.writerow([
                    'timestamp', 'events_per_second', 'avg_event_time_ms',
                    'active_connections', 'avg_connection_time_ms',
                    'memory_usage_mb', 'cache_hit_rate'
                ])
                # Data
                for report in self._performance_history:
                    writer.writerow([
                        report.timestamp,
                        report.event_metrics.events_per_second,
                        report.event_metrics.avg_processing_time * 1000,
                        report.connection_metrics.active_connections,
                        report.connection_metrics.avg_connection_time * 1000,
                        report.memory_metrics.current_usage / (1024 * 1024),
                        report.memory_metrics.cache_hit_rate
                    ])
        
        # Export alerts
        alerts_file = filepath.with_suffix('.alerts.csv')
        with open(alerts_file, 'w', newline='') as f:
            if self._alert_history:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'severity', 'component', 'message'])
                for alert in self._alert_history:
                    writer.writerow([
                        alert.timestamp,
                        alert.severity.value,
                        alert.component,
                        alert.message
                    ])
    
    def enable_auto_export(self, format: str = "json", interval: float = 300.0) -> None:
        """Enable automatic data export."""
        self._export_enabled = True
        self._export_format = format
        self._export_interval = interval
        logger.info(f"Auto-export enabled: {format} every {interval}s")
    
    def disable_auto_export(self) -> None:
        """Disable automatic data export."""
        self._export_enabled = False
        logger.info("Auto-export disabled")
    
    def check_auto_export(self) -> None:
        """Check if auto-export is due."""
        if not self._export_enabled:
            return
        
        current_time = time.time()
        if current_time - self._last_export >= self._export_interval:
            try:
                self.export_data(self._export_format)
                self._last_export = current_time
            except Exception as e:
                logger.error(f"Auto-export failed: {e}")