#!/usr/bin/env python3
"""
Example demonstrating how to use the SpacetimeDB SDK monitoring system.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import time
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from spacetimedb_sdk.monitoring import (
    get_global_monitor, enable_monitoring, disable_monitoring,
    collect_performance_report
)
from spacetimedb_sdk.monitoring.config import (
    get_monitoring_config, apply_monitoring_profile, update_monitoring_config
)
from spacetimedb_sdk.monitoring.dashboard import PerformanceDashboard
from spacetimedb_sdk.monitoring.alerts import AlertManager
from spacetimedb_sdk.monitoring.auto_tuner import AutoTuner
from spacetimedb_sdk.monitoring.performance_monitor import monitor_performance


def example_basic_usage():
    """Basic monitoring usage example."""
    print("=== Basic Monitoring Usage ===")
    
    # 1. Enable monitoring
    enable_monitoring()
    
    # 2. Get monitor instance
    monitor = get_global_monitor()
    
    # 3. Record various metrics during operations
    with monitor.measure_time("database_connection"):
        # Simulate database connection
        time.sleep(0.1)
    
    # Record specific events
    monitor.record_connection_setup(0.05, success=True)
    monitor.record_event_processing(0.001, "user_login", success=True)
    monitor.record_cache_access(hit=True, cache_name="user_cache")
    
    # 4. Collect current metrics
    metrics = monitor.collect_metrics()
    print(f"Current metrics: {metrics}")
    
    # 5. Generate performance report
    report = monitor.generate_report()
    print(f"Report generated with {len(report.recommendations)} recommendations")
    
    print()


def example_configuration():
    """Configuration system example."""
    print("=== Configuration Example ===")
    
    # 1. Get current configuration
    config = get_monitoring_config()
    print(f"Default monitoring enabled: {config.enabled}")
    print(f"Auto-tuning enabled: {config.enable_auto_tuning}")
    
    # 2. Apply a profile for different environments
    apply_monitoring_profile("production")
    config = get_monitoring_config()
    print(f"Production profile - auto-tuning: {config.enable_auto_tuning}")
    
    apply_monitoring_profile("development")
    config = get_monitoring_config()
    print(f"Development profile - debug mode: {config.debug_mode}")
    
    # 3. Update specific configuration values
    update_monitoring_config(
        metrics_collection_interval=10.0,
        connection_setup_threshold_ms=50.0
    )
    config = get_monitoring_config()
    print(f"Updated collection interval: {config.metrics_collection_interval}s")
    
    print()


def example_performance_dashboard():
    """Performance dashboard example."""
    print("=== Performance Dashboard Example ===")
    
    # 1. Create dashboard
    dashboard = PerformanceDashboard("./monitoring_data")
    
    # 2. Record some performance data
    monitor = get_global_monitor()
    report = monitor.generate_report()
    dashboard.record_performance_report(report)
    
    # 3. Get current status
    status = dashboard.get_current_status()
    print(f"Current status: {status}")
    
    # 4. Generate various reports
    summary = dashboard.generate_report("summary")
    print("Summary Report:")
    print(summary)
    
    # 5. Export data
    try:
        filepath = dashboard.export_data("json")
        print(f"Data exported to: {filepath}")
    except Exception as e:
        print(f"Export failed: {e}")
    
    print()


def example_alert_system():
    """Alert system example."""
    print("=== Alert System Example ===")
    
    # 1. Create alert manager
    alert_manager = AlertManager()
    
    # 2. Configure custom thresholds
    alert_manager.configure_thresholds(
        connection_setup_threshold_ms=100.0,
        event_dispatch_threshold_ms=1.0,
        memory_growth_threshold_mb_per_sec=50.0
    )
    
    # 3. Set up alert callback
    def alert_callback(alert):
        print(f"ALERT: [{alert.severity.value}] {alert.message}")
    
    alert_manager.alerts.add_callback(alert_callback)
    
    # 4. Check performance and trigger alerts
    test_metrics = {
        "connection_setup_time": 0.15,  # Above threshold
        "event_dispatch_latency": 0.002,  # Above threshold
        "memory_growth_rate": 1024 * 1024 * 60,  # Above threshold
    }
    
    alert_manager.check_performance(test_metrics)
    
    # 5. Get alert summary
    summary = alert_manager.get_alert_summary()
    print(f"Alert summary: {summary}")
    
    print()


def example_auto_tuning():
    """Auto-tuning system example."""
    print("=== Auto-Tuning Example ===")
    
    # 1. Create auto-tuner (without auto-apply for safety)
    tuner = AutoTuner(enable_auto_apply=False)
    
    # 2. Record usage metrics over time
    components = ["connection_pool", "event_system", "cache_manager"]
    
    for i in range(20):
        for component in components:
            # Simulate varying utilization
            utilization = 0.7 + 0.3 * (i / 20)  # Gradually increasing
            tuner.record_usage_metrics(component, {"utilization": utilization})
    
    # 3. Analyze usage patterns
    for component in components:
        pattern = tuner.analyze_usage_pattern(component)
        if pattern:
            print(f"{component}: avg={pattern.avg_utilization:.2f}, trend={pattern.trend}")
    
    # 4. Generate recommendations
    recommendations = tuner.generate_recommendations()
    print(f"Generated {len(recommendations)} recommendations:")
    for rec in recommendations:
        print(f"  - {rec.component}.{rec.parameter}: {rec.current_value} → {rec.recommended_value}")
        print(f"    Rationale: {rec.rationale}")
    
    print()


@monitor_performance("example_decorated_function")
def example_decorated_function():
    """Example function with performance monitoring decorator."""
    print("=== Decorated Function Example ===")
    
    # Simulate some work
    time.sleep(0.05)
    
    # This function's execution time is automatically monitored
    return "Function completed"


def example_memory_monitoring():
    """Memory monitoring example."""
    print("=== Memory Monitoring Example ===")
    
    from spacetimedb_sdk.monitoring.memory_monitor import get_global_accountant, track_memory
    
    # 1. Get memory accountant
    accountant = get_global_accountant()
    
    # 2. Track memory usage of specific operations
    with track_memory("data_processing"):
        # Simulate memory allocation
        data = [i * 2 for i in range(10000)]
        time.sleep(0.01)
    
    # 3. Get memory report
    report = accountant.get_memory_report()
    print(f"Memory usage: {report.current_rss / (1024 * 1024):.1f} MB")
    print(f"Peak usage: {report.peak_rss / (1024 * 1024):.1f} MB")
    print(f"Growth rate: {report.memory_growth_rate:.1f} bytes/sec")
    
    # 4. Get allocation summary
    summary = accountant.get_allocation_summary()
    for category, stats in summary.items():
        print(f"{category}: allocated={stats['allocated']}, net={stats['net']}")
    
    print()


def example_integration_with_sdk():
    """Example of monitoring integration with SDK components."""
    print("=== SDK Integration Example ===")
    
    # Note: This is a conceptual example showing how monitoring
    # would be integrated with actual SDK usage
    
    print("Monitoring is automatically integrated with:")
    print("- Authentication: Connection setup time tracking")
    print("- Event System: Event processing latency monitoring")
    print("- Connection Pool: Pool utilization and wait times")
    print("- WebSocket Client: Frame size and transmission monitoring")
    print("- Cache System: Hit rates and access patterns")
    
    # Example of manual monitoring hooks
    monitor = get_global_monitor()
    
    def custom_hook(**kwargs):
        print(f"Custom monitoring hook triggered: {kwargs}")
    
    monitor.add_monitoring_hook("custom_component", custom_hook)
    monitor.trigger_hooks("custom_component", operation="test", duration=0.01)
    
    print()


def main():
    """Run all monitoring examples."""
    print("SpacetimeDB SDK Monitoring System Examples")
    print("=" * 50)
    
    # Run examples
    example_basic_usage()
    example_configuration()
    example_performance_dashboard()
    example_alert_system()
    example_auto_tuning()
    
    # Test decorated function
    result = example_decorated_function()
    print(f"Decorated function result: {result}\n")
    
    example_memory_monitoring()
    example_integration_with_sdk()
    
    # Generate final comprehensive report
    print("=== Final Comprehensive Report ===")
    report = collect_performance_report()
    
    print(f"Events processed: {report.event_metrics.total_events}")
    print(f"Active connections: {report.connection_metrics.active_connections}")
    print(f"Memory usage: {report.memory_metrics.current_usage / (1024 * 1024):.1f} MB")
    print(f"Cache hit rate: {report.memory_metrics.cache_hit_rate:.1%}")
    
    if report.recommendations:
        print("\nRecommendations:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec}")
    
    print("\n" + "=" * 50)
    print("All examples completed successfully!")


if __name__ == "__main__":
    main()