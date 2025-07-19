#!/usr/bin/env python3
"""
Standalone test of the monitoring system components.
"""

import sys
import time
from pathlib import Path

# Add the src directory to the path but import directly
sys.path.insert(0, str(Path(__file__).parent / "src" / "spacetimedb_sdk"))

def test_metrics():
    """Test metrics collection."""
    print("Testing metrics collection...")
    
    from monitoring.metrics import (
        EventMetrics, ConnectionMetrics, MemoryMetrics, PoolMetrics,
        MetricsCollector, get_global_collector
    )
    
    # Test metrics data classes
    event_metrics = EventMetrics(total_events=100, avg_processing_time=0.001)
    print(f"Event metrics: {event_metrics}")
    
    # Test metrics collector
    collector = get_global_collector()
    collector.increment_counter("test_counter", 5)
    collector.record_event_time(0.001)
    collector.record_connection_time(0.05)
    
    # Get metrics
    events = collector.get_event_metrics()
    connections = collector.get_connection_metrics()
    memory = collector.get_memory_metrics()
    
    print(f"Events: {events.total_events}, Connections: {connections.total_connections}")
    print("✓ Metrics test passed")


def test_memory_monitor():
    """Test memory monitoring."""
    print("\nTesting memory monitoring...")
    
    from monitoring.memory_monitor import (
        MemoryAccountant, MemoryReport, get_global_accountant
    )
    
    # Test memory accountant
    accountant = get_global_accountant()
    accountant.record_allocation(1024, "test_category")
    accountant.record_deallocation(512, "test_category")
    
    # Get memory report
    report = accountant.get_memory_report()
    print(f"Memory report: RSS={report.current_rss}, Objects={report.python_objects}")
    
    # Test allocation summary
    summary = accountant.get_allocation_summary()
    print(f"Allocation summary: {summary}")
    
    print("✓ Memory monitor test passed")


def test_alerts():
    """Test alert system."""
    print("\nTesting alerts...")
    
    from monitoring.alerts import (
        PerformanceAlerts, AlertThresholds, AlertSeverity
    )
    
    # Test alerts
    alerts = PerformanceAlerts()
    
    # Add some alerts
    alerts.add_alert("Test warning", AlertSeverity.WARNING, "test_component")
    alerts.add_alert("Test error", AlertSeverity.ERROR, "test_component")
    
    # Get recent alerts
    recent = alerts.get_recent_alerts(10)
    print(f"Recent alerts: {len(recent)}")
    
    # Test thresholds
    thresholds = AlertThresholds()
    print(f"Connection threshold: {thresholds.connection_setup_warning}s")
    
    print("✓ Alerts test passed")


def test_config():
    """Test configuration system."""
    print("\nTesting configuration...")
    
    from monitoring.config import (
        MonitoringConfig, ConfigManager, get_monitoring_config
    )
    
    # Test config
    config = MonitoringConfig()
    print(f"Default config - enabled: {config.enabled}")
    
    # Test profile application
    config.apply_profile("production")
    print(f"Production profile - auto-tuning: {config.enable_auto_tuning}")
    
    # Test validation
    issues = config.validate()
    print(f"Validation issues: {len(issues)}")
    
    print("✓ Configuration test passed")


def test_auto_tuner():
    """Test auto-tuning."""
    print("\nTesting auto-tuning...")
    
    from monitoring.auto_tuner import AutoTuner
    
    # Test auto-tuner
    tuner = AutoTuner(enable_auto_apply=False)
    
    # Record usage metrics
    tuner.record_usage_metrics("test_component", {"utilization": 0.8})
    tuner.record_usage_metrics("test_component", {"utilization": 0.9})
    tuner.record_usage_metrics("test_component", {"utilization": 0.85})
    
    # Analyze pattern
    pattern = tuner.analyze_usage_pattern("test_component")
    if pattern:
        print(f"Usage pattern: avg={pattern.avg_utilization:.2f}, trend={pattern.trend}")
    
    print("✓ Auto-tuner test passed")


def test_performance_monitor():
    """Test performance monitoring."""
    print("\nTesting performance monitoring...")
    
    from monitoring.performance_monitor import (
        PerformanceMonitor, monitor_performance
    )
    
    # Test performance monitor
    monitor = PerformanceMonitor()
    
    # Record some metrics
    monitor.record_connection_setup(0.05, success=True)
    monitor.record_event_processing(0.001, "test_event", success=True)
    monitor.record_websocket_frame(sent=True, size=1024)
    
    # Collect metrics
    metrics = monitor.collect_metrics()
    print(f"Performance metrics: {metrics}")
    
    # Generate report
    report = monitor.generate_report()
    print(f"Report generated with {len(report.recommendations)} recommendations")
    
    # Test decorator
    @monitor_performance("test_operation")
    def test_function():
        time.sleep(0.01)
        return "test result"
    
    result = test_function()
    print(f"Decorated function result: {result}")
    
    print("✓ Performance monitor test passed")


def test_dashboard():
    """Test dashboard."""
    print("\nTesting dashboard...")
    
    from monitoring.dashboard import PerformanceDashboard
    from monitoring.performance_monitor import PerformanceMonitor
    
    # Test dashboard
    dashboard = PerformanceDashboard("./test_monitoring_data")
    
    # Record some data
    monitor = PerformanceMonitor()
    monitor.record_connection_setup(0.05, success=True)
    report = monitor.generate_report()
    dashboard.record_performance_report(report)
    
    # Get status
    status = dashboard.get_current_status()
    print(f"Dashboard status: {status}")
    
    # Generate report
    summary = dashboard.generate_report("summary")
    print(f"Summary report length: {len(summary)} characters")
    
    print("✓ Dashboard test passed")


def run_all_tests():
    """Run all monitoring tests."""
    print("Testing SpacetimeDB SDK Monitoring System Components")
    print("=" * 50)
    
    try:
        test_metrics()
        test_memory_monitor()
        test_alerts()
        test_config()
        test_auto_tuner()
        test_performance_monitor()
        test_dashboard()
        
        print("\n" + "=" * 50)
        print("All monitoring component tests passed! ✓")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)