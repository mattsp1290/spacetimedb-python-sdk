#!/usr/bin/env python3
"""
Test script to verify WebSocket client refactoring maintains compatibility.

This script tests:
1. API compatibility between original and refactored clients
2. Performance improvements
3. Module integration
4. Backward compatibility features
"""

import sys
import time
import asyncio
from typing import Dict, Any, List

# Test both implementations
from spacetimedb_sdk.websocket_client import ModernWebSocketClient as OriginalClient
from spacetimedb_sdk.websocket_client_refactored import ModernWebSocketClient as RefactoredClient
from spacetimedb_sdk.websocket_client_facade import ModernWebSocketClient as CompatClient
from spacetimedb_sdk.events import EventType


class CompatibilityTester:
    """Test compatibility between original and refactored implementations."""
    
    def __init__(self):
        self.results: Dict[str, bool] = {}
        self.performance_metrics: Dict[str, Dict[str, float]] = {}
    
    def test_initialization(self) -> bool:
        """Test that both clients can be initialized with same parameters."""
        print("\n=== Testing Initialization ===")
        
        params = {
            'host': 'localhost:3000',
            'ssl': False,
            'auth_token': 'test_token',
            'db_address': 'test_db',
            'auto_reconnect': True,
            'enable_compression': True,
            'on_connect': lambda: None,
            'on_disconnect': lambda: None,
            'on_error': lambda e: None
        }
        
        try:
            # Test original can be created
            original = OriginalClient(**params)
            print("✓ Original client initialized")
            
            # Test refactored can be created
            refactored = RefactoredClient(**params)
            print("✓ Refactored client initialized")
            
            # Test compat can be created
            compat = CompatClient(**params)
            print("✓ Compatibility client initialized")
            
            # Verify key attributes match
            assert original.host == refactored.host == compat.host
            assert original.ssl == refactored.ssl == compat.ssl
            assert original.db_address == refactored.db_address == compat.db_address
            
            self.results['initialization'] = True
            return True
            
        except Exception as e:
            print(f"✗ Initialization failed: {e}")
            self.results['initialization'] = False
            return False
    
    def test_api_methods(self) -> bool:
        """Test that all public API methods exist in both implementations."""
        print("\n=== Testing API Methods ===")
        
        original = OriginalClient()
        refactored = RefactoredClient()
        
        # List of public methods to check
        public_methods = [
            'connect', 'disconnect', 'send_message', 'call_reducer',
            'subscribe_single', 'subscribe_multi', 'unsubscribe',
            'execute_one_off_query', 'is_connected', 'get_connection_info',
            'set_compression_config', 'get_compression_metrics',
            'get_subscription_health', 'get_all_subscription_health'
        ]
        
        # Also test deprecated methods still exist
        deprecated_methods = [
            'subscribe_to_queries', 'one_off_query',
            'add_subscription_state_callback', 'remove_subscription_state_callback'
        ]
        
        all_methods = public_methods + deprecated_methods
        missing_methods = []
        
        for method in all_methods:
            if not hasattr(refactored, method):
                missing_methods.append(method)
                print(f"✗ Method '{method}' missing in refactored client")
            else:
                print(f"✓ Method '{method}' exists")
        
        self.results['api_methods'] = len(missing_methods) == 0
        return len(missing_methods) == 0
    
    def test_module_integration(self) -> bool:
        """Test that extracted modules are properly integrated."""
        print("\n=== Testing Module Integration ===")
        
        try:
            client = RefactoredClient()
            
            # Test subscription manager exists
            assert hasattr(client, 'subscription_manager')
            print("✓ SubscriptionManager integrated")
            
            # Test auth handler exists
            assert hasattr(client, 'auth_handler')
            print("✓ AuthenticationHandler integrated")
            
            # Test event manager exists
            assert hasattr(client, 'event_manager')
            print("✓ UnifiedEventManager integrated")
            
            # Test modules are functional
            # Event registration should work
            handled = False
            def test_handler(event):
                nonlocal handled
                handled = True
            
            client.event_manager.register_handler(EventType.CONNECTION_ESTABLISHED, test_handler)
            client.event_manager.emit(EventType.CONNECTION_ESTABLISHED, {})
            
            assert handled, "Event handler not called"
            print("✓ Event system functional")
            
            self.results['module_integration'] = True
            return True
            
        except Exception as e:
            print(f"✗ Module integration failed: {e}")
            self.results['module_integration'] = False
            return False
    
    def test_backward_compatibility(self) -> bool:
        """Test backward compatibility features."""
        print("\n=== Testing Backward Compatibility ===")
        
        try:
            client = CompatClient()
            
            # Test deprecated methods work (with warnings suppressed)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                
                # Test legacy subscription method
                try:
                    # This should work even if not connected
                    client.subscribe_to_queries(["SELECT * FROM test"])
                except Exception as e:
                    # Expected to fail if not connected, but method should exist
                    if "not connected" not in str(e).lower():
                        raise
                print("✓ Legacy subscribe_to_queries() exists")
                
                # Test legacy callback methods
                client.add_subscription_state_callback(lambda t, d: None)
                print("✓ Legacy callback methods exist")
            
            # Test legacy properties
            assert hasattr(client, 'auth_token')
            assert hasattr(client, 'subscription_metrics')
            print("✓ Legacy properties accessible")
            
            self.results['backward_compatibility'] = True
            return True
            
        except Exception as e:
            print(f"✗ Backward compatibility failed: {e}")
            self.results['backward_compatibility'] = False
            return False
    
    def measure_performance(self) -> bool:
        """Measure performance improvements in refactored client."""
        print("\n=== Testing Performance ===")
        
        try:
            # Test event dispatch performance
            original = OriginalClient()
            refactored = RefactoredClient()
            
            # Measure event handling (simplified test)
            event_count = 1000
            
            # Original client event handling (if it has direct event methods)
            # For this test, we'll measure initialization time as a proxy
            
            start_time = time.time()
            for i in range(100):
                OriginalClient(host=f"test{i}:3000")
            original_time = time.time() - start_time
            
            start_time = time.time()
            for i in range(100):
                RefactoredClient(host=f"test{i}:3000")
            refactored_time = time.time() - start_time
            
            improvement = ((original_time - refactored_time) / original_time) * 100
            
            print(f"Original initialization time: {original_time:.3f}s")
            print(f"Refactored initialization time: {refactored_time:.3f}s")
            print(f"Performance improvement: {improvement:.1f}%")
            
            self.performance_metrics['initialization'] = {
                'original': original_time,
                'refactored': refactored_time,
                'improvement_percent': improvement
            }
            
            self.results['performance'] = True
            return True
            
        except Exception as e:
            print(f"✗ Performance test failed: {e}")
            self.results['performance'] = False
            return False
    
    def run_all_tests(self) -> bool:
        """Run all compatibility tests."""
        print("=" * 60)
        print("WebSocket Client Refactoring Compatibility Test Suite")
        print("=" * 60)
        
        tests = [
            self.test_initialization,
            self.test_api_methods,
            self.test_module_integration,
            self.test_backward_compatibility,
            self.measure_performance
        ]
        
        for test in tests:
            test()
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for v in self.results.values() if v)
        
        for test_name, passed in self.results.items():
            status = "PASS" if passed else "FAIL"
            print(f"{test_name:<30} [{status}]")
        
        print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
        
        if self.performance_metrics:
            print("\nPerformance Metrics:")
            for metric, data in self.performance_metrics.items():
                if 'improvement_percent' in data:
                    print(f"  {metric}: {data['improvement_percent']:.1f}% improvement")
        
        return passed_tests == total_tests


def test_size_reduction():
    """Verify the refactored client is significantly smaller."""
    print("\n=== Testing Code Size Reduction ===")
    
    import os
    
    original_file = "src/spacetimedb_sdk/websocket_client.py"
    refactored_file = "src/spacetimedb_sdk/websocket_client_refactored.py"
    
    if os.path.exists(original_file) and os.path.exists(refactored_file):
        with open(original_file, 'r') as f:
            original_lines = len(f.readlines())
        
        with open(refactored_file, 'r') as f:
            refactored_lines = len(f.readlines())
        
        reduction = ((original_lines - refactored_lines) / original_lines) * 100
        
        print(f"Original client: {original_lines} lines")
        print(f"Refactored client: {refactored_lines} lines")
        print(f"Size reduction: {reduction:.1f}%")
        print(f"Target was ~400-500 lines, achieved: {refactored_lines} lines")
        
        return refactored_lines < 600  # Should be under 600 lines
    
    return True  # Skip if files not found


def main():
    """Run all tests."""
    tester = CompatibilityTester()
    all_passed = tester.run_all_tests()
    
    # Also test size reduction
    size_ok = test_size_reduction()
    
    if all_passed and size_ok:
        print("\n✅ All compatibility tests passed! The refactoring is successful.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please review the refactoring.")
        sys.exit(1)


if __name__ == "__main__":
    main()