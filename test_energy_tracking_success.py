#!/usr/bin/env python3
"""
GREEN Phase: Success tests for EnergyQuanta Tracking System (proto-7)

These tests verify that the energy quota tracking and management system
works correctly after implementation. They should all PASS now.

Testing:
- Enhanced EnergyQuanta class with tracking capabilities
- EnergyTracker for monitoring current energy levels and usage
- EnergyBudgetManager for managing energy budgets and quotas
- OutOfEnergyError and energy-related exceptions
- Energy event system with callbacks
- Energy-aware client operations
- Energy usage analytics and reporting
"""

import os
import sys
import time
import signal
from contextlib import contextmanager

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

class TimeoutError(Exception):
    pass

@contextmanager
def timeout(seconds):
    """Context manager for timeout on macOS."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Test timed out after {seconds} seconds")
    
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def test_energy_module_exists():
    """Test that the energy module exists and can be imported."""
    try:
        import spacetimedb_sdk.energy
        print("🟢 PASS: energy module exists and can be imported")
        return True
    except ImportError as e:
        print(f"❌ FAIL: energy module import failed: {e}")
        return False


def test_enhanced_energy_quanta_features():
    """Test that enhanced EnergyQuanta class has all expected features."""
    try:
        from spacetimedb_sdk.protocol import EnergyQuanta
        
        # Create EnergyQuanta instance
        energy = EnergyQuanta(quanta=100)
        
        # Test enhanced features
        assert hasattr(energy, 'get_cost_estimate'), "Should have get_cost_estimate method"
        assert hasattr(energy, 'can_afford'), "Should have can_afford method"
        assert hasattr(energy, 'track_usage'), "Should have track_usage method"
        assert hasattr(energy, 'get_usage_history'), "Should have get_usage_history method"
        assert hasattr(energy, 'write_bsatn'), "Should have BSATN serialization"
        assert hasattr(EnergyQuanta, 'read_bsatn'), "Should have BSATN deserialization"
        
        # Test operations
        cost = energy.get_cost_estimate("call_reducer", "test_reducer")
        assert isinstance(cost, int), "Cost estimate should be an integer"
        assert cost > 0, "Cost should be positive"
        
        assert energy.can_afford(50) == True, "Should be able to afford 50 energy"
        assert energy.can_afford(150) == False, "Should not be able to afford 150 energy"
        
        # Test tracking (enable first)
        energy.enable_usage_tracking()
        
        # Test successful usage tracking
        success = energy.track_usage(30, "test_operation")
        assert success == True, "Should successfully track 30 energy usage"
        assert energy.quanta == 70, "Should have 70 energy remaining"
        
        # Test failed usage tracking
        success = energy.track_usage(100, "large_operation")
        assert success == False, "Should fail to track 100 energy usage"
        assert energy.quanta == 70, "Energy should remain unchanged after failed tracking"
        
        # Test usage history
        history = energy.get_usage_history()
        assert len(history) == 2, "Should have 2 operations in history"
        assert history[0]['success'] == True, "First operation should be successful"
        assert history[1]['success'] == False, "Second operation should have failed"
        
        print("🟢 PASS: Enhanced EnergyQuanta has all features and works correctly")
        return True
    except Exception as e:
        print(f"❌ FAIL: Enhanced EnergyQuanta test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_energy_tracker():
    """Test that EnergyTracker works correctly."""
    try:
        from spacetimedb_sdk.energy import EnergyTracker
        
        tracker = EnergyTracker(initial_energy=500, max_energy=1000)
        
        # Test basic functionality
        assert hasattr(tracker, 'get_current_energy'), "Should have get_current_energy method"
        assert hasattr(tracker, 'get_max_energy'), "Should have get_max_energy method"
        assert hasattr(tracker, 'get_energy_usage'), "Should have get_energy_usage method"
        assert hasattr(tracker, 'predict_energy_cost'), "Should have predict_energy_cost method"
        assert hasattr(tracker, 'track_operation'), "Should have track_operation method"
        assert hasattr(tracker, 'get_replenishment_rate'), "Should have get_replenishment_rate method"
        
        # Test energy tracking
        current = tracker.get_current_energy()
        max_energy = tracker.get_max_energy()
        assert isinstance(current, int), "Current energy should be an integer"
        assert isinstance(max_energy, int), "Max energy should be an integer"
        assert current <= max_energy, "Current energy should not exceed max"
        assert current == 500, "Initial energy should be 500"
        assert max_energy == 1000, "Max energy should be 1000"
        
        # Test energy consumption
        success = tracker.consume_energy(100, "test_operation")
        assert success == True, "Should successfully consume 100 energy"
        assert tracker.get_current_energy() == 400, "Should have 400 energy remaining"
        
        # Test failed consumption
        success = tracker.consume_energy(500, "large_operation")
        assert success == False, "Should fail to consume 500 energy"
        assert tracker.get_current_energy() == 400, "Energy should remain unchanged"
        
        # Test cost prediction
        predicted_cost = tracker.predict_energy_cost("call_reducer", "test_reducer")
        assert isinstance(predicted_cost, int), "Predicted cost should be an integer"
        assert predicted_cost > 0, "Predicted cost should be positive"
        
        # Test usage statistics
        usage_stats = tracker.get_energy_usage()
        assert isinstance(usage_stats, dict), "Usage stats should be a dictionary"
        assert 'total_energy_used' in usage_stats, "Should include total energy used"
        assert 'operation_count' in usage_stats, "Should include operation count"
        assert 'efficiency_score' in usage_stats, "Should include efficiency score"
        
        print("🟢 PASS: EnergyTracker works correctly")
        return True
    except Exception as e:
        print(f"❌ FAIL: EnergyTracker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_energy_budget_manager():
    """Test that EnergyBudgetManager works correctly."""
    try:
        from spacetimedb_sdk.energy import EnergyBudgetManager
        
        manager = EnergyBudgetManager(initial_budget=1000)
        
        # Test basic functionality
        assert hasattr(manager, 'set_budget'), "Should have set_budget method"
        assert hasattr(manager, 'get_remaining_budget'), "Should have get_remaining_budget method"
        assert hasattr(manager, 'can_execute_operation'), "Should have can_execute_operation method"
        assert hasattr(manager, 'reserve_energy'), "Should have reserve_energy method"
        assert hasattr(manager, 'release_energy'), "Should have release_energy method"
        assert hasattr(manager, 'get_budget_utilization'), "Should have get_budget_utilization method"
        
        # Test budget management
        manager.set_budget(1000)
        remaining = manager.get_remaining_budget()
        assert isinstance(remaining, int), "Remaining budget should be an integer"
        assert remaining == 1000, "Initial remaining budget should be 1000"
        
        can_execute = manager.can_execute_operation("call_reducer", estimated_cost=50)
        assert isinstance(can_execute, bool), "can_execute should return a boolean"
        assert can_execute == True, "Should be able to execute 50-cost operation"
        
        # Test energy reservation
        success = manager.reserve_energy("test_reservation", 200)
        assert success == True, "Should successfully reserve 200 energy"
        assert manager.get_remaining_budget() == 800, "Remaining budget should be 800"
        
        # Test energy consumption with reservation
        success = manager.consume_budget(200, "test_reservation")
        assert success == True, "Should successfully consume reserved energy"
        assert manager.get_used_energy() == 200, "Used energy should be 200"
        
        # Test budget utilization
        utilization = manager.get_budget_utilization()
        assert isinstance(utilization, dict), "Utilization should be a dictionary"
        assert 'total_budget' in utilization, "Should include total budget"
        assert 'used_energy' in utilization, "Should include used energy"
        assert 'utilization_percent' in utilization, "Should include utilization percentage"
        
        print("🟢 PASS: EnergyBudgetManager works correctly")
        return True
    except Exception as e:
        print(f"❌ FAIL: EnergyBudgetManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_energy_errors():
    """Test that energy-related exceptions work correctly."""
    try:
        from spacetimedb_sdk.energy import OutOfEnergyError, EnergyExhaustedException
        
        # Test OutOfEnergyError
        error = OutOfEnergyError("Not enough energy", required=100, available=50, operation="test_op")
        assert hasattr(error, 'required'), "Should have required attribute"
        assert hasattr(error, 'available'), "Should have available attribute"
        assert hasattr(error, 'operation'), "Should have operation attribute"
        
        assert error.required == 100, "Required should be 100"
        assert error.available == 50, "Available should be 50"
        assert error.operation == "test_op", "Operation should be test_op"
        assert "Not enough energy" in str(error), "Error message should be included"
        
        # Test that it's properly an exception
        try:
            raise error
        except OutOfEnergyError as caught:
            assert caught is error, "Should catch the same exception instance"
        
        print("🟢 PASS: Energy exceptions work correctly")
        return True
    except Exception as e:
        print(f"❌ FAIL: Energy exceptions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_energy_event_system():
    """Test that energy event system works correctly."""
    try:
        from spacetimedb_sdk.energy import (
            EnergyEventType,
            EnergyEvent,
            EnergyEventListener,
            EnergyEventManager
        )
        
        # Test event types
        assert hasattr(EnergyEventType, 'ENERGY_LOW'), "Should have ENERGY_LOW event type"
        assert hasattr(EnergyEventType, 'ENERGY_EXHAUSTED'), "Should have ENERGY_EXHAUSTED event type"
        assert hasattr(EnergyEventType, 'ENERGY_REPLENISHED'), "Should have ENERGY_REPLENISHED event type"
        assert hasattr(EnergyEventType, 'OPERATION_DEFERRED'), "Should have OPERATION_DEFERRED event type"
        
        # Test event creation
        event = EnergyEvent(
            event_type=EnergyEventType.ENERGY_LOW,
            current_energy=25,
            threshold=50,
            timestamp=time.time()
        )
        
        assert hasattr(event, 'event_type'), "Should have event_type attribute"
        assert hasattr(event, 'current_energy'), "Should have current_energy attribute"
        assert hasattr(event, 'timestamp'), "Should have timestamp attribute"
        assert event.event_type == EnergyEventType.ENERGY_LOW, "Event type should be ENERGY_LOW"
        assert event.current_energy == 25, "Current energy should be 25"
        
        # Test event manager
        manager = EnergyEventManager()
        
        # Test event listener registration
        events_received = []
        def test_listener(event):
            events_received.append(event)
        
        manager.register_listener("energy_low", test_listener)
        
        # Test event emission
        manager.emit_event(event)
        assert len(events_received) == 1, "Should have received 1 event"
        assert events_received[0] is event, "Should have received the same event"
        
        print("🟢 PASS: Energy event system works correctly")
        return True
    except Exception as e:
        print(f"❌ FAIL: Energy event system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_energy_aware_client():
    """Test that energy-aware client features work correctly."""
    try:
        from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
        
        # Create client with energy settings but without background threads to avoid hanging
        client = ModernSpacetimeDBClient(
            start_message_processing=False,  # Disable to prevent hanging
            initial_energy=500,
            max_energy=1000,
            energy_budget=2000
        )
        
        try:
            # Test energy-aware client features
            assert hasattr(client, 'get_current_energy'), "Should have get_current_energy method"
            assert hasattr(client, 'get_energy_budget'), "Should have get_energy_budget method"
            assert hasattr(client, 'can_afford_operation'), "Should have can_afford_operation method"
            assert hasattr(client, 'call_reducer_energy_aware'), "Should have call_reducer_energy_aware method"
            assert hasattr(client, 'set_energy_budget'), "Should have set_energy_budget method"
            assert hasattr(client, 'add_energy_listener'), "Should have add_energy_listener method"
            assert hasattr(client, 'get_energy_usage_stats'), "Should have get_energy_usage_stats method"
            
            # Test energy-aware operations
            energy_level = client.get_current_energy()
            budget_info = client.get_energy_budget()
            can_afford = client.can_afford_operation("test_reducer", [])
            
            assert isinstance(energy_level, int), "Energy level should be an integer"
            assert isinstance(budget_info, dict), "Budget info should be a dictionary"
            assert isinstance(can_afford, bool), "can_afford should return a boolean"
            
            assert energy_level == 500, "Initial energy should be 500"
            assert budget_info['total_budget'] == 2000, "Budget should be 2000"
            assert can_afford == True, "Should be able to afford basic operation"
            
            # Test energy statistics
            stats = client.get_energy_usage_stats()
            assert isinstance(stats, dict), "Stats should be a dictionary"
            assert 'current_energy' in stats, "Should include current energy"
            assert 'budget_info' in stats, "Should include budget info"
            assert 'usage_report' in stats, "Should include usage report"
            
            # Test energy listener
            events_received = []
            def energy_listener(event):
                events_received.append(event)
            
            client.add_energy_listener(energy_listener)
            
            print("🟢 PASS: Energy-aware client features work correctly")
            return True
            
        finally:
            # Ensure proper cleanup to prevent hanging
            client.shutdown()
            
    except Exception as e:
        print(f"❌ FAIL: Energy-aware client test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_energy_usage_analytics():
    """Test that energy usage analytics work correctly."""
    try:
        from spacetimedb_sdk.energy import EnergyUsageAnalytics, EnergyUsageReport
        
        analytics = EnergyUsageAnalytics()
        
        # Test analytics capabilities
        assert hasattr(analytics, 'track_operation'), "Should have track_operation method"
        assert hasattr(analytics, 'generate_report'), "Should have generate_report method"
        assert hasattr(analytics, 'get_top_consumers'), "Should have get_top_consumers method"
        assert hasattr(analytics, 'get_usage_trends'), "Should have get_usage_trends method"
        assert hasattr(analytics, 'get_efficiency_metrics'), "Should have get_efficiency_metrics method"
        assert hasattr(analytics, 'export_data'), "Should have export_data method"
        
        # Test analytics operations
        analytics.track_operation("call_reducer", "test_reducer", energy_cost=50, duration=0.1, success=True)
        analytics.track_operation("query", "SELECT * FROM users", energy_cost=25, duration=0.05, success=True)
        
        report = analytics.generate_report(time_range="1h")
        
        assert isinstance(report, EnergyUsageReport), "Report should be EnergyUsageReport instance"
        assert hasattr(report, 'total_energy_used'), "Report should have total_energy_used"
        assert hasattr(report, 'operation_count'), "Report should have operation_count"
        assert hasattr(report, 'efficiency_score'), "Report should have efficiency_score"
        
        assert report.total_energy_used == 75, "Total energy should be 75"
        assert report.operation_count == 2, "Operation count should be 2"
        assert isinstance(report.efficiency_score, float), "Efficiency score should be a float"
        
        # Test top consumers
        top_consumers = analytics.get_top_consumers(limit=5)
        assert isinstance(top_consumers, list), "Top consumers should be a list"
        assert len(top_consumers) >= 1, "Should have at least 1 consumer"
        
        # Test efficiency metrics
        metrics = analytics.get_efficiency_metrics()
        assert isinstance(metrics, dict), "Metrics should be a dictionary"
        assert 'efficiency_score' in metrics, "Should include efficiency score"
        assert 'success_rate' in metrics, "Should include success rate"
        
        print("🟢 PASS: Energy usage analytics work correctly")
        return True
    except Exception as e:
        print(f"❌ FAIL: Energy usage analytics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_energy_cost_estimation():
    """Test that energy cost estimation system works correctly."""
    try:
        from spacetimedb_sdk.energy import EnergyCostEstimator
        
        estimator = EnergyCostEstimator()
        
        # Test cost estimation capabilities
        assert hasattr(estimator, 'estimate_reducer_cost'), "Should have estimate_reducer_cost method"
        assert hasattr(estimator, 'estimate_query_cost'), "Should have estimate_query_cost method"
        assert hasattr(estimator, 'estimate_subscription_cost'), "Should have estimate_subscription_cost method"
        assert hasattr(estimator, 'calibrate_costs'), "Should have calibrate_costs method"
        assert hasattr(estimator, 'get_cost_breakdown'), "Should have get_cost_breakdown method"
        
        # Test cost estimation
        reducer_cost = estimator.estimate_reducer_cost("test_reducer", args=[1, 2, 3])
        query_cost = estimator.estimate_query_cost("SELECT * FROM users")
        subscription_cost = estimator.estimate_subscription_cost("SELECT * FROM messages")
        
        assert isinstance(reducer_cost, int), "Reducer cost should be an integer"
        assert isinstance(query_cost, int), "Query cost should be an integer"
        assert isinstance(subscription_cost, int), "Subscription cost should be an integer"
        assert reducer_cost > 0, "Reducer cost should be positive"
        assert query_cost > 0, "Query cost should be positive"
        assert subscription_cost > 0, "Subscription cost should be positive"
        
        # Test cost calibration
        estimator.calibrate_costs("call_reducer", "test_reducer", 75)
        new_cost = estimator.estimate_reducer_cost("test_reducer")
        # Cost should be updated based on calibration
        
        # Test cost breakdown
        breakdown = estimator.get_cost_breakdown("call_reducer", "test_reducer")
        assert isinstance(breakdown, dict), "Breakdown should be a dictionary"
        assert 'estimated_cost' in breakdown, "Should include estimated cost"
        assert 'factors' in breakdown, "Should include cost factors"
        assert 'confidence' in breakdown, "Should include confidence level"
        
        print("🟢 PASS: Energy cost estimation works correctly")
        return True
    except Exception as e:
        print(f"❌ FAIL: Energy cost estimation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all success tests with timeout protection."""
    print("🟢 GREEN Phase: Running success tests for EnergyQuanta Tracking System")
    print("=" * 75)
    
    test_functions = [
        test_energy_module_exists,
        test_enhanced_energy_quanta_features,
        test_energy_tracker,
        test_energy_budget_manager,
        test_energy_errors,
        test_energy_event_system,
        test_energy_aware_client,
        test_energy_usage_analytics,
        test_energy_cost_estimation,
    ]
    
    passed_count = 0
    
    try:
        with timeout(60):  # 60 second total timeout
            for test_func in test_functions:
                try:
                    with timeout(10):  # 10 second per-test timeout
                        if test_func():
                            passed_count += 1
                except TimeoutError:
                    print(f"⏰ {test_func.__name__} - TIMED OUT")
                except Exception as e:
                    print(f"❌ {test_func.__name__} - FAILED: {e}")
                    import traceback
                    traceback.print_exc()
    
    except TimeoutError:
        print("⏰ Overall test suite timed out")
    
    print(f"\n🟢 GREEN Phase Summary: {passed_count}/{len(test_functions)} tests passed")
    if passed_count == len(test_functions):
        print("🎯 Perfect! All energy management features work correctly!")
        print("✅ Proto-7: EnergyQuanta Tracking System - COMPLETE")
    elif passed_count >= len(test_functions) * 0.8:  # 80% success rate
        print("🟢 Most energy management features work correctly!")
    else:
        print("❌ Some energy management features need fixes.")


if __name__ == "__main__":
    main() 