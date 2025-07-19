#!/usr/bin/env python3
"""
Test script to verify the monitoring system integration.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import os
import time
import threading
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from spacetimedb_sdk.monitoring import (
    get_global_monitor, enable_monitoring, disable_monitoring,
    collect_performance_report, get_monitoring_config
)
from spacetimedb_sdk.monitoring.config import apply_monitoring_profile
from spacetimedb_sdk.monitoring.dashboard import PerformanceDashboard
from spacetimedb_sdk.monitoring.alerts import AlertManager


def test_basic_monitoring():
    """Test basic monitoring functionality."""
    print("Testing basic monitoring...")
    
    # Enable monitoring
    enable_monitoring()
    
    # Get monitor instance
    monitor = get_global_monitor()
    
    # Test various metrics
    monitor.record_connection_setup(0.05, success=True)
    monitor.record_connection_setup(0.15, success=True)
    monitor.record_connection_setup(0.08, success=False)
    
    monitor.record_event_processing(0.001, "test_event", success=True)
    monitor.record_event_processing(0.002, "test_event", success=True)
    monitor.record_event_processing(0.003, "test_event", success=False)
    
    monitor.record_websocket_frame(sent=True, size=1024)
    monitor.record_websocket_frame(sent=False, size=2048)
    
    monitor.record_cache_access(hit=True, cache_name="test_cache")
    monitor.record_cache_access(hit=False, cache_name="test_cache")
    
    monitor.record_pool_metrics("test_pool", 5, 10, 0.01)
    
    # Collect metrics
    metrics = monitor.collect_metrics()
    print(f"Collected metrics: {metrics}")
    
    # Generate report
    report = monitor.generate_report()
    print(f"Generated report with {len(report.recommendations)} recommendations")
    
    print("✓ Basic monitoring test passed")


def test_performance_dashboard():
    """Test performance dashboard."""
    print("\nTesting performance dashboard...")
    
    dashboard = PerformanceDashboard("./test_monitoring_data")
    
    # Record some test data
    monitor = get_global_monitor()
    report = monitor.generate_report()
    dashboard.record_performance_report(report)
    
    # Test dashboard functionality
    status = dashboard.get_current_status()
    print(f"Dashboard status: {status}")
    
    # Test report generation
    summary_report = dashboard.generate_report("summary")
    print(f"Summary report:\n{summary_report}")
    
    print("✓ Performance dashboard test passed")


def test_alert_system():
    """Test alert system."""
    print("\nTesting alert system...")
    
    alert_manager = AlertManager()
    
    # Test performance check with high values
    test_metrics = {
        "connection_setup_time": 0.6,  # Above error threshold
        "event_dispatch_latency": 0.002,  # Above error threshold
        "memory_growth_rate": 1024 * 1024 * 60,  # Above error threshold
        "pool_utilization": 0.99  # Above critical threshold
    }
    
    alert_manager.check_performance(test_metrics)
    
    # Get alert summary
    summary = alert_manager.get_alert_summary()
    print(f"Alert summary: {summary}")
    
    print("✓ Alert system test passed")


def test_configuration_system():
    """Test configuration system."""
    print("\nTesting configuration system...")
    
    # Test configuration loading
    config = get_monitoring_config()
    print(f"Default config enabled: {config.enabled}")
    
    # Test profile application
    apply_monitoring_profile("production")
    config = get_monitoring_config()
    print(f"Production config auto-tuning: {config.enable_auto_tuning}")
    
    apply_monitoring_profile("development")
    config = get_monitoring_config()
    print(f"Development config debug: {config.debug_mode}")
    
    print("✓ Configuration system test passed")


def test_auto_tuning():
    """Test auto-tuning system."""
    print("\nTesting auto-tuning system...")
    
    from spacetimedb_sdk.monitoring.auto_tuner import AutoTuner
    
    # Create auto-tuner (without auto-apply for safety)
    tuner = AutoTuner(enable_auto_apply=False)
    
    # Record some usage metrics
    tuner.record_usage_metrics("test_component", {"utilization": 0.95})
    tuner.record_usage_metrics("test_component", {"utilization": 0.92})
    tuner.record_usage_metrics("test_component", {"utilization": 0.88})
    
    # Analyze patterns
    pattern = tuner.analyze_usage_pattern("test_component")
    if pattern:
        print(f"Usage pattern: avg={pattern.avg_utilization:.2f}, trend={pattern.trend}")
    
    # Generate recommendations
    recommendations = tuner.generate_recommendations()
    print(f"Generated {len(recommendations)} recommendations")
    
    print("✓ Auto-tuning system test passed")


def test_memory_monitoring():
    """Test memory monitoring."""
    print("\nTesting memory monitoring...")
    
    from spacetimedb_sdk.monitoring.memory_monitor import get_global_accountant, track_memory
    
    accountant = get_global_accountant()
    
    # Test memory tracking
    with track_memory("test_operation"):
        # Simulate some memory allocation
        data = [i for i in range(1000)]
        time.sleep(0.01)
    
    # Get memory report
    report = accountant.get_memory_report()
    print(f"Memory report: RSS={report.current_rss/(1024*1024):.1f}MB, "
          f"Growth rate={report.memory_growth_rate:.1f} bytes/sec")
    
    print("✓ Memory monitoring test passed")


def test_integration_hooks():
    """Test integration with SDK components."""
    print("\nTesting integration hooks...")
    
    # Test that monitoring hooks are properly integrated
    monitor = get_global_monitor()
    
    # Test hook registration
    def test_hook(**kwargs):
        print(f"Hook called with: {kwargs}")
    
    monitor.add_monitoring_hook("test_component", test_hook)
    monitor.trigger_hooks("test_component", event="test_event")
    
    # Test decorator functionality
    from spacetimedb_sdk.monitoring.performance_monitor import monitor_performance
    
    @monitor_performance("test_function")
    def test_function():
        time.sleep(0.01)
        return "test result"
    
    result = test_function()
    print(f"Decorated function result: {result}")
    
    print("✓ Integration hooks test passed")


def run_all_tests():
    """Run all monitoring tests."""
    print("Starting SpacetimeDB SDK Monitoring System Tests")
    print("=" * 50)
    
    try:
        test_basic_monitoring()
        test_performance_dashboard()
        test_alert_system()
        test_configuration_system()
        test_auto_tuning()
        test_memory_monitoring()
        test_integration_hooks()
        
        print("\n" + "=" * 50)
        print("All monitoring tests passed! ✓")
        
        # Generate final report
        print("\nFinal Performance Report:")
        report = collect_performance_report()
        if report.recommendations:
            print("Recommendations:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)