"""
Unified Events Test Suite

Tests for the event system with context pooling and memory efficiency benchmarks.
This combines comprehensive tests for the unified event system with context pooling validation.
"""

import asyncio
import time
import threading
import unittest
import gc
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from typing import List, Dict, Any

try:
    import psutil
except ImportError:
    psutil = None

# Import the fixed modules
from spacetimedb_sdk.bounded_client_cache import ContextPool, ContextConfiguration
from spacetimedb_sdk.event_system import EventContext, Event, EventType, EventMetadata

# Import comprehensive event system modules if available
try:
    from refactoring.src.spacetimedb_sdk.events.core_events import (
        EventPriority, EventStats, HandlerInfo, EventBatch, create_system_event
    )
    from refactoring.src.spacetimedb_sdk.events.event_manager import UnifiedEventManager, EventManagerConfig
    from refactoring.src.spacetimedb_sdk.events.event_context import ContextBuilder, EventContextManager
    from refactoring.src.spacetimedb_sdk.events.event_filters import (
        TypeFilter, SourceFilter, MetadataFilter, CompositeFilter,
        PredicateFilter, RateLimitFilter, FilterChain
    )
    from refactoring.src.spacetimedb_sdk.events.legacy_compat import LegacyEventEmitter, LegacySDKEventManager, migrate_legacy_handlers
    from refactoring.src.spacetimedb_sdk.events.websocket_integration import WebSocketEventIntegration, WebSocketEventHandler
    COMPREHENSIVE_TESTS_AVAILABLE = True
except ImportError:
    COMPREHENSIVE_TESTS_AVAILABLE = False


class TestUnifiedEvents(unittest.TestCase):
    """Test suite for unified event system with context pooling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pool = ContextPool(
            min_size=10,
            max_size=50,
            context_config=ContextConfiguration(
                max_history_size=100,
                enable_response_data=True,
                default_source_component="test_component"
            )
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.pool.cleanup()
    
    def test_context_pool_basic_operations(self):
        """Test basic context pool operations."""
        # Test context acquisition
        event = Event(
            type=EventType.CUSTOM,
            data={"test": "data"},
            metadata=EventMetadata(source="test")
        )
        
        context = self.pool.acquire_context(event)
        self.assertIsNotNone(context)
        self.assertEqual(context.event.data["test"], "data")
        
        # Test context release
        self.pool.release_context(context)
        
        # Check pool metrics
        metrics = self.pool.get_pool_metrics()
        self.assertEqual(metrics['total_acquired'], 1)
        self.assertEqual(metrics['total_released'], 1)
    
    def test_context_configuration(self):
        """Test the configure_context method that was missing."""
        event = Event(
            type=EventType.CUSTOM,
            data={"test": "data"}
        )
        
        context = self.pool.acquire_context(event)
        
        # Test configuration - this is the method that was missing!
        self.pool.configure_context(
            context,
            source_component="configured_component",
            max_triggered_events=5
        )
        
        # Verify configuration was applied
        self.assertEqual(context.source_component, "configured_component")
        
        self.pool.release_context(context)
    
    def test_context_pool_thread_safety(self):
        """Test thread safety of context pool operations."""
        results = []
        errors = []
        
        def worker():
            try:
                for i in range(100):
                    event = Event(
                        type=EventType.CUSTOM,
                        data={"worker_id": threading.current_thread().ident, "iteration": i}
                    )
                    
                    context = self.pool.acquire_context(event)
                    
                    # Configure context
                    self.pool.configure_context(
                        context,
                        source_component=f"worker_{threading.current_thread().ident}"
                    )
                    
                    # Simulate some work
                    time.sleep(0.001)
                    
                    results.append(context.event.data["iteration"])
                    self.pool.release_context(context)
                    
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 500)  # 5 threads * 100 iterations
    
    @unittest.skipIf(psutil is None, "psutil not available for memory testing")
    def test_memory_efficiency_with_context_pooling(self):
        """
        Memory Efficiency with Context Pooling benchmark.
        
        This is the test that was failing with AttributeError when trying to call
        pool.configure_context() - now it should work!
        """
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test without pooling first (create many contexts)
        start_time = time.time()
        contexts_without_pool = []
        
        for i in range(1000):
            event = Event(
                type=EventType.CUSTOM,
                data={"benchmark": "no_pool", "iteration": i}
            )
            context = EventContext(event, "benchmark")
            contexts_without_pool.append(context)
        
        no_pool_time = time.time() - start_time
        no_pool_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Clean up
        del contexts_without_pool
        gc.collect()
        
        # Test with pooling
        start_time = time.time()
        
        for i in range(1000):
            event = Event(
                type=EventType.CUSTOM,
                data={"benchmark": "with_pool", "iteration": i}
            )
            
            # Acquire context from pool
            context = self.pool.acquire_context(event)
            
            # THIS IS THE LINE THAT WAS FAILING BEFORE THE FIX!
            # The configure_context method was missing from ContextPool
            self.pool.configure_context(
                context,
                source_component="benchmark_component",
                max_triggered_events=10
            )
            
            # Simulate some work
            context.set_response("benchmark_result", f"iteration_{i}")
            
            # Release context back to pool
            self.pool.release_context(context)
        
        pool_time = time.time() - start_time
        pool_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Log benchmark results
        print(f"\nMemory Efficiency Benchmark Results:")
        print(f"Initial Memory: {initial_memory:.2f} MB")
        print(f"Without Pool - Time: {no_pool_time:.4f}s, Memory: {no_pool_memory:.2f} MB")
        print(f"With Pool - Time: {pool_time:.4f}s, Memory: {pool_memory:.2f} MB")
        print(f"Final Memory: {final_memory:.2f} MB")
        
        # Get pool metrics
        metrics = self.pool.get_pool_metrics()
        print(f"Pool Metrics: {metrics}")
        
        # Assertions
        self.assertLess(pool_time, no_pool_time * 1.5, "Pool should not be significantly slower")
        self.assertEqual(metrics['total_acquired'], 1000)
        self.assertEqual(metrics['total_released'], 1000)
        self.assertGreater(metrics['peak_active'], 0, "Pool should have been utilized")
    
    def test_bug_reproduction_and_fix(self):
        """
        Reproduce the original bug and verify the fix.
        
        Original Error:
        AttributeError: ContextPool object has no attribute 'configure_context'
        """
        # Create a context pool
        pool = ContextPool(min_size=5, max_size=20)
        
        # Create an event
        event = Event(
            type=EventType.REDUCER_CALLED,
            data={"reducer": "test_reducer", "args": {"param": "value"}}
        )
        
        # Acquire context
        context = pool.acquire_context(event)
        
        # THIS WOULD HAVE FAILED BEFORE THE FIX!
        # AttributeError: 'ContextPool' object has no attribute 'configure_context'
        try:
            pool.configure_context(
                context,
                source_component="test_component",
                enable_timing=True,
                max_triggered_events=15
            )
            
            # If we get here, the fix worked!
            fix_successful = True
            
        except AttributeError as e:
            fix_successful = False
            self.fail(f"configure_context method still missing: {e}")
        
        # Verify the method exists and works
        self.assertTrue(fix_successful, "configure_context method should exist and work")
        self.assertTrue(hasattr(pool, 'configure_context'), "ContextPool should have configure_context method")
        
        # Verify configuration was applied
        self.assertEqual(context.source_component, "test_component")
        
        # Clean up
        pool.release_context(context)
        pool.cleanup()
    
    def test_context_pool_configuration_options(self):
        """Test various configuration options for context pool."""
        # Test with different configuration
        custom_config = ContextConfiguration(
            max_history_size=50,
            enable_response_data=False,
            default_source_component="custom_component"
        )
        
        pool = ContextPool(
            min_size=3,
            max_size=15,
            context_config=custom_config
        )
        
        event = Event(
            type=EventType.TABLE_ROW_INSERT,
            data={"table": "test_table", "row": {"id": 1, "name": "test"}}
        )
        
        context = pool.acquire_context(event)
        
        # Test configuration
        pool.configure_context(
            context,
            source_component="table_handler",
            max_triggered_events=3
        )
        
        # Verify configuration
        self.assertEqual(context.source_component, "table_handler")
        
        pool.release_context(context)
        pool.cleanup()
    
    def test_context_pool_edge_cases(self):
        """Test edge cases and error conditions."""
        # Test with small pool
        small_pool = ContextPool(min_size=1, max_size=2)
        
        # Acquire all contexts
        event1 = Event(type=EventType.CUSTOM, data={"test": 1})
        event2 = Event(type=EventType.CUSTOM, data={"test": 2})
        event3 = Event(type=EventType.CUSTOM, data={"test": 3})
        
        context1 = small_pool.acquire_context(event1)
        context2 = small_pool.acquire_context(event2)
        context3 = small_pool.acquire_context(event3)  # Should still work (creates temporary)
        
        # All should be valid
        self.assertIsNotNone(context1)
        self.assertIsNotNone(context2)
        self.assertIsNotNone(context3)
        
        # Configure all contexts
        small_pool.configure_context(context1, source_component="edge_case_1")
        small_pool.configure_context(context2, source_component="edge_case_2")
        small_pool.configure_context(context3, source_component="edge_case_3")
        
        # Release contexts
        small_pool.release_context(context1)
        small_pool.release_context(context2)
        small_pool.release_context(context3)
        
        # Check metrics
        metrics = small_pool.get_pool_metrics()
        self.assertEqual(metrics['total_acquired'], 3)
        self.assertEqual(metrics['total_released'], 3)
        
        small_pool.cleanup()


class TestContextPoolPerformance(unittest.TestCase):
    """Performance tests for context pool."""
    
    def setUp(self):
        """Set up performance test fixtures."""
        self.pool = ContextPool(min_size=20, max_size=100)
    
    def tearDown(self):
        """Clean up after performance tests."""
        self.pool.cleanup()
    
    def test_high_throughput_context_operations(self):
        """Test high-throughput context operations."""
        num_operations = 10000
        start_time = time.time()
        
        for i in range(num_operations):
            event = Event(
                type=EventType.CUSTOM,
                data={"operation": i, "batch": "performance_test"}
            )
            
            context = self.pool.acquire_context(event)
            
            # Configure context
            self.pool.configure_context(
                context,
                source_component=f"perf_test_{i % 10}",
                max_triggered_events=5
            )
            
            # Simulate some work
            context.set_response("performance_result", f"operation_{i}")
            
            self.pool.release_context(context)
        
        elapsed_time = time.time() - start_time
        operations_per_second = num_operations / elapsed_time
        
        print(f"\nPerformance Test Results:")
        print(f"Operations: {num_operations}")
        print(f"Time: {elapsed_time:.4f}s")
        print(f"Operations/second: {operations_per_second:.2f}")
        
        # Get final metrics
        metrics = self.pool.get_pool_metrics()
        print(f"Pool Metrics: {metrics}")
        
        # Assertions
        self.assertEqual(metrics['total_acquired'], num_operations)
        self.assertEqual(metrics['total_released'], num_operations)
        self.assertGreater(operations_per_second, 1000, "Should handle at least 1000 operations per second")


# Comprehensive event system tests (only if modules are available)
@unittest.skipIf(not COMPREHENSIVE_TESTS_AVAILABLE, "Comprehensive event system modules not available")
class TestCoreEvents(unittest.TestCase):
    """Test core event types and contexts."""
    
    def test_event_context_creation(self):
        """Test event context creation."""
        context = EventContext.create(
            event_type=EventType.CONNECTION_OPENED,
            source="test_client",
            data={"test": "data"},
            metadata_key="metadata_value"
        )
        
        self.assertEqual(context.event_type, EventType.CONNECTION_OPENED)
        self.assertEqual(context.source, "test_client")
        self.assertEqual(context.data, {"test": "data"})
        self.assertEqual(context.get_metadata("metadata_key"), "metadata_value")
        self.assertIsNotNone(context.correlation_id)
        self.assertIsNotNone(context.timestamp)
    
    def test_context_builder(self):
        """Test context builder pattern."""
        context = (ContextBuilder(EventType.MESSAGE_RECEIVED)
                  .source("websocket_client")
                  .data({"message": "hello"})
                  .metadata(user_id="123", session_id="456")
                  .build())
        
        self.assertEqual(context.event_type, EventType.MESSAGE_RECEIVED)
        self.assertEqual(context.source, "websocket_client")
        self.assertEqual(context.data, {"message": "hello"})
        self.assertEqual(context.get_metadata("user_id"), "123")
        self.assertEqual(context.get_metadata("session_id"), "456")


@unittest.skipIf(not COMPREHENSIVE_TESTS_AVAILABLE, "Comprehensive event system modules not available")
class TestEventManager(unittest.TestCase):
    """Test unified event manager."""
    
    def setUp(self):
        """Set up test event manager."""
        self.config = EventManagerConfig(
            thread_pool_size=2,
            enable_metrics=True,
            debug_mode=True
        )
        self.manager = UnifiedEventManager(self.config)
        self.handler_calls = []
    
    def tearDown(self):
        """Clean up after tests."""
        self.manager.shutdown()
    
    def test_handler_registration(self):
        """Test handler registration and removal."""
        def test_handler(context: EventContext):
            self.handler_calls.append(context.event_type)
        
        # Register handler
        handler_id = self.manager.add_handler(EventType.CONNECTION_OPENED, test_handler)
        self.assertIsNotNone(handler_id)
        
        # Check handler count
        self.assertEqual(self.manager.get_handler_count(EventType.CONNECTION_OPENED), 1)
        
        # Remove handler
        removed = self.manager.remove_handler(EventType.CONNECTION_OPENED, test_handler)
        self.assertTrue(removed)
        self.assertEqual(self.manager.get_handler_count(EventType.CONNECTION_OPENED), 0)


def run_performance_benchmarks():
    """Run comprehensive performance benchmarks."""
    print("Running Unified Event System Performance Benchmarks")
    print("=" * 60)
    
    # Create context pool for benchmarking
    pool = ContextPool(min_size=50, max_size=200)
    
    # Benchmark 1: Context pool operations
    print("\nBenchmark 1: Context Pool Operations")
    start_time = time.time()
    num_operations = 10000
    
    for i in range(num_operations):
        event = Event(
            type=EventType.CUSTOM,
            data={"benchmark": "pool_ops", "iteration": i}
        )
        
        context = pool.acquire_context(event)
        pool.configure_context(
            context,
            source_component="benchmark",
            max_triggered_events=5
        )
        pool.release_context(context)
    
    end_time = time.time()
    duration = end_time - start_time
    operations_per_second = num_operations / duration
    
    print(f"Processed {num_operations} context operations in {duration:.3f}s")
    print(f"Rate: {operations_per_second:.0f} operations/second")
    
    # Get final metrics
    metrics = pool.get_pool_metrics()
    print(f"Pool Metrics: {metrics}")
    
    pool.cleanup()
    print("\nBenchmarks completed!")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2, exit=False)
    
    # Run performance benchmarks
    run_performance_benchmarks()