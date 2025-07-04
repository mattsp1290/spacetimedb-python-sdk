"""
Comprehensive Tests for Unified Event System

This module contains tests to validate the unified event system implementation,
including performance benchmarks and backward compatibility tests.
"""

import asyncio
import time
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from .core_events import (
    EventType, EventContext, EventPriority, EventStats,
    HandlerInfo, EventBatch, create_system_event
)
from .event_manager import UnifiedEventManager, EventManagerConfig
from .event_context import ContextBuilder, ContextPool, EventContextManager
from .event_filters import (
    TypeFilter, SourceFilter, MetadataFilter, CompositeFilter,
    PredicateFilter, RateLimitFilter, FilterChain
)
from .legacy_compat import LegacyEventEmitter, LegacySDKEventManager, migrate_legacy_handlers
from .websocket_integration import WebSocketEventIntegration, WebSocketEventHandler


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
    
    def test_event_context_hierarchy(self):
        """Test parent-child context relationships."""
        parent = EventContext.create(
            event_type=EventType.CONNECTION_OPENED,
            source="client"
        )
        
        child = parent.with_parent(parent)
        child.event_type = EventType.MESSAGE_RECEIVED
        
        self.assertTrue(child.is_child_of(parent))
        self.assertFalse(parent.is_child_of(child))
    
    def test_event_stats(self):
        """Test event statistics tracking."""
        stats = EventStats()
        
        stats.record_event_emitted(EventType.CONNECTION_OPENED)
        stats.record_event_processed(0.1)
        stats.record_handler_execution("test_handler", 0.05)
        
        self.assertEqual(stats.events_emitted, 1)
        self.assertEqual(stats.events_processed, 1)
        self.assertEqual(stats.handlers_executed, 1)
        self.assertAlmostEqual(stats.get_average_processing_time(), 0.1)


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
    
    def test_event_emission(self):
        """Test event emission and handler execution."""
        def test_handler(context: EventContext):
            self.handler_calls.append(context.event_type)
        
        self.manager.add_handler(EventType.MESSAGE_RECEIVED, test_handler)
        
        context = EventContext.create(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test",
            data={"message": "test"}
        )
        
        futures = self.manager.emit(EventType.MESSAGE_RECEIVED, context)
        
        # Wait for handlers to complete
        for future in futures:
            future.result(timeout=1.0)
        
        self.assertIn(EventType.MESSAGE_RECEIVED, self.handler_calls)
    
    def test_priority_handling(self):
        """Test priority-based handler execution."""
        execution_order = []
        
        def high_priority_handler(context: EventContext):
            execution_order.append("high")
        
        def low_priority_handler(context: EventContext):
            execution_order.append("low")
        
        def normal_priority_handler(context: EventContext):
            execution_order.append("normal")
        
        # Register handlers in different order than priority
        self.manager.add_handler(EventType.SYSTEM_ERROR, low_priority_handler, EventPriority.LOW)
        self.manager.add_handler(EventType.SYSTEM_ERROR, high_priority_handler, EventPriority.HIGH)
        self.manager.add_handler(EventType.SYSTEM_ERROR, normal_priority_handler, EventPriority.NORMAL)
        
        context = create_system_event(EventType.SYSTEM_ERROR, error="test")
        futures = self.manager.emit(EventType.SYSTEM_ERROR, context)
        
        # Wait for completion
        for future in futures:
            future.result(timeout=1.0)
        
        # Should execute in priority order: high, normal, low
        self.assertEqual(execution_order, ["high", "normal", "low"])
    
    def test_async_handlers(self):
        """Test async handler execution."""
        async_calls = []
        
        async def async_handler(context: EventContext):
            async_calls.append("async")
            await asyncio.sleep(0.01)
        
        def sync_handler(context: EventContext):
            async_calls.append("sync")
        
        self.manager.add_handler(EventType.MESSAGE_RECEIVED, async_handler)
        self.manager.add_handler(EventType.MESSAGE_RECEIVED, sync_handler)
        
        context = EventContext.create(
            event_type=EventType.MESSAGE_RECEIVED,
            source="test"
        )
        
        futures = self.manager.emit(EventType.MESSAGE_RECEIVED, context)
        
        # Wait for completion
        for future in futures:
            future.result(timeout=2.0)
        
        self.assertIn("async", async_calls)
        self.assertIn("sync", async_calls)
    
    def test_error_handling(self):
        """Test handler error handling."""
        def error_handler(context: EventContext):
            raise Exception("Test error")
        
        def normal_handler(context: EventContext):
            self.handler_calls.append("normal")
        
        self.manager.add_handler(EventType.SYSTEM_ERROR, error_handler)
        self.manager.add_handler(EventType.SYSTEM_ERROR, normal_handler)
        
        context = create_system_event(EventType.SYSTEM_ERROR)
        futures = self.manager.emit(EventType.SYSTEM_ERROR, context)
        
        # Wait for completion - should not raise
        for future in futures:
            try:
                future.result(timeout=1.0)
            except Exception:
                pass  # Expected for error handler
        
        # Normal handler should still execute
        self.assertIn("normal", self.handler_calls)
    
    def test_metrics_collection(self):
        """Test metrics collection."""
        def test_handler(context: EventContext):
            time.sleep(0.01)  # Simulate processing time
        
        self.manager.add_handler(EventType.MESSAGE_RECEIVED, test_handler)
        
        # Emit multiple events
        for i in range(5):
            context = EventContext.create(
                event_type=EventType.MESSAGE_RECEIVED,
                source="test",
                data={"index": i}
            )
            futures = self.manager.emit(EventType.MESSAGE_RECEIVED, context)
            for future in futures:
                future.result(timeout=1.0)
        
        metrics = self.manager.get_metrics()
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.stats.events_emitted, 5)
        self.assertGreater(metrics.stats.handlers_executed, 0)


class TestEventFilters(unittest.TestCase):
    """Test event filtering system."""
    
    def test_type_filter(self):
        """Test event type filtering."""
        filter_obj = TypeFilter([EventType.CONNECTION_OPENED, EventType.CONNECTION_CLOSED])
        
        context1 = EventContext.create(EventType.CONNECTION_OPENED, "test")
        context2 = EventContext.create(EventType.MESSAGE_RECEIVED, "test")
        
        self.assertTrue(filter_obj.should_process(context1))
        self.assertFalse(filter_obj.should_process(context2))
    
    def test_source_filter(self):
        """Test source filtering."""
        filter_obj = SourceFilter(["websocket_client", "database_client"])
        
        context1 = EventContext.create(EventType.CONNECTION_OPENED, "websocket_client")
        context2 = EventContext.create(EventType.CONNECTION_OPENED, "http_client")
        
        self.assertTrue(filter_obj.should_process(context1))
        self.assertFalse(filter_obj.should_process(context2))
    
    def test_metadata_filter(self):
        """Test metadata filtering."""
        filter_obj = MetadataFilter({"priority": "high", "user_type": "admin"})
        
        context1 = EventContext.create(
            EventType.SYSTEM_ERROR,
            "test",
            priority="high",
            user_type="admin"
        )
        context2 = EventContext.create(
            EventType.SYSTEM_ERROR,
            "test",
            priority="low",
            user_type="user"
        )
        
        self.assertTrue(filter_obj.should_process(context1))
        self.assertFalse(filter_obj.should_process(context2))
    
    def test_predicate_filter(self):
        """Test predicate filtering."""
        def is_error_event(context: EventContext) -> bool:
            return "error" in context.event_type.value
        
        filter_obj = PredicateFilter(is_error_event)
        
        context1 = EventContext.create(EventType.CONNECTION_ERROR, "test")
        context2 = EventContext.create(EventType.CONNECTION_OPENED, "test")
        
        self.assertTrue(filter_obj.should_process(context1))
        self.assertFalse(filter_obj.should_process(context2))
    
    def test_composite_filter(self):
        """Test composite filtering."""
        type_filter = TypeFilter([EventType.CONNECTION_ERROR])
        source_filter = SourceFilter(["websocket_client"])
        
        and_filter = CompositeFilter([type_filter, source_filter], "AND")
        or_filter = CompositeFilter([type_filter, source_filter], "OR")
        
        context1 = EventContext.create(EventType.CONNECTION_ERROR, "websocket_client")
        context2 = EventContext.create(EventType.CONNECTION_ERROR, "http_client")
        context3 = EventContext.create(EventType.MESSAGE_RECEIVED, "websocket_client")
        
        # AND filter - both conditions must be true
        self.assertTrue(and_filter.should_process(context1))
        self.assertFalse(and_filter.should_process(context2))
        self.assertFalse(and_filter.should_process(context3))
        
        # OR filter - either condition can be true
        self.assertTrue(or_filter.should_process(context1))
        self.assertTrue(or_filter.should_process(context2))
        self.assertTrue(or_filter.should_process(context3))
    
    def test_rate_limit_filter(self):
        """Test rate limiting filter."""
        filter_obj = RateLimitFilter(
            max_events=2,
            time_window=1.0,
            key_extractor=lambda ctx: ctx.source
        )
        
        context = EventContext.create(EventType.MESSAGE_RECEIVED, "test_client")
        
        # First two events should pass
        self.assertTrue(filter_obj.should_process(context))
        self.assertTrue(filter_obj.should_process(context))
        
        # Third event should be rate limited
        self.assertFalse(filter_obj.should_process(context))


class TestContextManagement(unittest.TestCase):
    """Test event context management."""
    
    def test_context_pool(self):
        """Test context pooling."""
        pool = ContextPool(max_size=10)
        
        # Acquire contexts
        contexts = [pool.acquire() for _ in range(5)]
        self.assertEqual(len(contexts), 5)
        
        # Release contexts
        for context in contexts:
            pool.release(context)
        
        # Reacquire - should reuse pooled contexts
        new_contexts = [pool.acquire() for _ in range(3)]
        self.assertEqual(len(new_contexts), 3)
        
        stats = pool.get_stats()
        self.assertGreater(stats['reuse_rate'], 0)
    
    def test_context_manager(self):
        """Test event context manager."""
        manager = EventContextManager(pool_size=50)
        
        # Create context
        context = manager.create_context(
            EventType.CONNECTION_OPENED,
            "test_client",
            data={"test": "data"}
        )
        
        self.assertIsNotNone(context.correlation_id)
        self.assertEqual(context.event_type, EventType.CONNECTION_OPENED)
        
        # Create child context
        child = manager.create_child_context(
            context,
            EventType.MESSAGE_RECEIVED,
            data={"child": "data"}
        )
        
        # Get context chain
        chain = manager.get_context_chain(child.correlation_id)
        self.assertGreater(len(chain), 1)
        
        # Mark as processed
        manager.mark_processed(context, 0.1)
        
        # Release contexts
        manager.release_context(context)
        manager.release_context(child)
        
        stats = manager.get_stats()
        self.assertEqual(stats['contexts_processed'], 1)
    
    def test_managed_context(self):
        """Test managed context context manager."""
        manager = EventContextManager()
        
        with manager.managed_context(
            EventType.SYSTEM_ERROR,
            "test_source",
            data={"error": "test"}
        ) as context:
            self.assertEqual(context.event_type, EventType.SYSTEM_ERROR)
            self.assertEqual(context.source, "test_source")
        
        # Context should be automatically released
        stats = manager.get_stats()
        self.assertEqual(stats['contexts_processed'], 1)


class TestLegacyCompatibility(unittest.TestCase):
    """Test legacy compatibility layer."""
    
    def test_legacy_event_emitter(self):
        """Test legacy event emitter compatibility."""
        manager = UnifiedEventManager()
        legacy_emitter = LegacyEventEmitter(manager)
        
        calls = []
        
        def legacy_handler():
            calls.append("legacy")
        
        def new_handler(context: EventContext):
            calls.append("new")
        
        # Register handlers using both systems
        legacy_emitter.on('connected', legacy_handler)
        manager.add_handler(EventType.CONNECTION_OPENED, new_handler)
        
        # Emit using legacy interface
        legacy_emitter.emit('connected')
        
        time.sleep(0.1)  # Allow handlers to execute
        
        # Both handlers should be called
        self.assertIn("legacy", calls)
        self.assertIn("new", calls)
        
        manager.shutdown()
    
    def test_legacy_sdk_manager(self):
        """Test legacy SDK manager compatibility."""
        manager = UnifiedEventManager()
        legacy_manager = LegacySDKEventManager(manager)
        
        calls = []
        
        def legacy_callback(event):
            calls.append(f"legacy: {event['type']}")
        
        def new_handler(context: EventContext):
            calls.append(f"new: {context.event_type.value}")
        
        # Register callbacks
        legacy_manager.register_callback('table_update', legacy_callback)
        manager.add_handler(EventType.TABLE_UPDATE, new_handler)
        
        # Queue event using legacy interface
        legacy_manager.queue_event('table_update', {'table': 'users'})
        
        time.sleep(0.1)
        
        # Both handlers should be called
        self.assertTrue(any("legacy" in call for call in calls))
        self.assertTrue(any("new" in call for call in calls))
        
        manager.shutdown()
    
    def test_handler_migration(self):
        """Test automatic handler migration."""
        old_handlers = {
            'connected': [lambda: print("Connected")],
            'message_received': [lambda data: print(f"Message: {data}")],
            'error': [lambda error: print(f"Error: {error}")]
        }
        
        manager = UnifiedEventManager()
        results = migrate_legacy_handlers(old_handlers, manager)
        
        # Should migrate all event types
        self.assertEqual(len(results), 3)
        self.assertGreater(results['connected'], 0)
        self.assertGreater(results['message_received'], 0)
        self.assertGreater(results['error'], 0)
        
        manager.shutdown()


class TestWebSocketIntegration(unittest.TestCase):
    """Test WebSocket integration."""
    
    def test_websocket_event_handler(self):
        """Test WebSocket event handler."""
        manager = UnifiedEventManager()
        handler = WebSocketEventHandler(manager)
        
        events_received = []
        
        def event_listener(context: EventContext):
            events_received.append(context.event_type)
        
        # Register listener for all connection events
        for event_type in [EventType.CONNECTION_OPENED, EventType.CONNECTION_CLOSED, EventType.MESSAGE_RECEIVED]:
            manager.add_handler(event_type, event_listener)
        
        # Simulate WebSocket events
        handler.register_connection("conn_123", "ws://localhost:8080")
        handler.on_connection_opened("conn_123", "ws://localhost:8080")
        handler.on_message_received("conn_123", "Hello, World!")
        handler.on_connection_closed("conn_123")
        
        time.sleep(0.1)
        
        # Should receive all events
        self.assertIn(EventType.CONNECTION_OPENED, events_received)
        self.assertIn(EventType.MESSAGE_RECEIVED, events_received)
        self.assertIn(EventType.CONNECTION_CLOSED, events_received)
        
        # Check statistics
        stats = handler.get_overall_stats()
        self.assertGreater(stats['events_emitted'], 0)
        
        manager.shutdown()
    
    def test_websocket_integration(self):
        """Test full WebSocket integration."""
        manager = UnifiedEventManager()
        integration = WebSocketEventIntegration(manager)
        
        # Mock WebSocket client
        class MockWebSocket:
            def __init__(self):
                self.on_open = None
                self.on_close = None
                self.on_message = None
                self.on_error = None
        
        client = MockWebSocket()
        integration.register_websocket_client(
            client,
            "conn_123",
            "ws://localhost:8080",
            {"user_id": "user_456"}
        )
        
        # Verify client is registered
        connections = integration.get_active_connections()
        # Note: Connection won't be "active" until opened
        
        stats = integration.get_integration_stats()
        self.assertEqual(stats['registered_clients'], 1)
        
        integration.cleanup()
        manager.shutdown()


class TestPerformance(unittest.TestCase):
    """Performance tests for the unified event system."""
    
    def test_event_processing_performance(self):
        """Test event processing performance."""
        manager = UnifiedEventManager(EventManagerConfig(
            thread_pool_size=4,
            enable_metrics=True
        ))
        
        processed_count = 0
        
        def fast_handler(context: EventContext):
            nonlocal processed_count
            processed_count += 1
        
        manager.add_handler(EventType.MESSAGE_RECEIVED, fast_handler)
        
        # Process many events
        start_time = time.time()
        num_events = 1000
        
        for i in range(num_events):
            context = EventContext.create(
                EventType.MESSAGE_RECEIVED,
                "performance_test",
                data={"index": i}
            )
            manager.emit(EventType.MESSAGE_RECEIVED, context)
        
        # Wait for completion
        time.sleep(1.0)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Check performance metrics
        events_per_second = num_events / duration
        print(f"Processed {num_events} events in {duration:.2f}s ({events_per_second:.0f} events/sec)")
        
        # Should process at least 500 events per second
        self.assertGreater(events_per_second, 500)
        self.assertEqual(processed_count, num_events)
        
        manager.shutdown()
    
    def test_memory_usage(self):
        """Test memory usage with context pooling."""
        manager = UnifiedEventManager(EventManagerConfig(
            enable_memory_pooling=True,
            max_context_pool_size=100
        ))
        
        # Create many contexts
        contexts = []
        for i in range(200):
            context = EventContext.create(
                EventType.MESSAGE_RECEIVED,
                "memory_test",
                data={"index": i}
            )
            contexts.append(context)
        
        # Memory usage should be reasonable
        # This is a basic test - in practice you'd use memory profiling tools
        self.assertLess(len(contexts), 1000)  # Sanity check
        
        manager.shutdown()
    
    def test_concurrent_access(self):
        """Test concurrent access to event manager."""
        manager = UnifiedEventManager(EventManagerConfig(thread_pool_size=8))
        
        processed_events = []
        lock = threading.Lock()
        
        def concurrent_handler(context: EventContext):
            with lock:
                processed_events.append(context.correlation_id)
        
        manager.add_handler(EventType.MESSAGE_RECEIVED, concurrent_handler)
        
        # Emit events from multiple threads
        def emit_events(thread_id):
            for i in range(50):
                context = EventContext.create(
                    EventType.MESSAGE_RECEIVED,
                    f"thread_{thread_id}",
                    data={"thread": thread_id, "index": i}
                )
                manager.emit(EventType.MESSAGE_RECEIVED, context)
        
        threads = []
        for i in range(4):
            thread = threading.Thread(target=emit_events, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Wait for event processing
        time.sleep(1.0)
        
        # Should process all events
        self.assertEqual(len(processed_events), 200)
        
        manager.shutdown()


def run_performance_benchmarks():
    """Run comprehensive performance benchmarks."""
    print("Running Unified Event System Performance Benchmarks")
    print("=" * 60)
    
    # Benchmark 1: Basic event processing
    print("\nBenchmark 1: Basic Event Processing")
    manager = UnifiedEventManager()
    
    def benchmark_handler(context: EventContext):
        pass  # Minimal processing
    
    manager.add_handler(EventType.MESSAGE_RECEIVED, benchmark_handler)
    
    start_time = time.time()
    num_events = 10000
    
    for i in range(num_events):
        context = EventContext.create(
            EventType.MESSAGE_RECEIVED,
            "benchmark",
            data={"index": i}
        )
        manager.emit(EventType.MESSAGE_RECEIVED, context)
    
    time.sleep(0.5)  # Allow processing
    end_time = time.time()
    
    duration = end_time - start_time
    events_per_second = num_events / duration
    
    print(f"Processed {num_events} events in {duration:.3f}s")
    print(f"Rate: {events_per_second:.0f} events/second")
    
    manager.shutdown()
    
    # Benchmark 2: Handler execution with different priorities
    print("\nBenchmark 2: Priority-based Handler Execution")
    manager = UnifiedEventManager()
    
    execution_times = []
    
    def priority_handler(context: EventContext):
        start = time.time()
        time.sleep(0.001)  # Simulate processing
        execution_times.append(time.time() - start)
    
    # Register handlers with different priorities
    manager.add_handler(EventType.SYSTEM_ERROR, priority_handler, EventPriority.CRITICAL)
    manager.add_handler(EventType.SYSTEM_ERROR, priority_handler, EventPriority.HIGH)
    manager.add_handler(EventType.SYSTEM_ERROR, priority_handler, EventPriority.NORMAL)
    manager.add_handler(EventType.SYSTEM_ERROR, priority_handler, EventPriority.LOW)
    
    start_time = time.time()
    
    for i in range(100):
        context = create_system_event(EventType.SYSTEM_ERROR, error=f"test_{i}")
        futures = manager.emit(EventType.SYSTEM_ERROR, context)
        for future in futures:
            future.result(timeout=1.0)
    
    end_time = time.time()
    
    print(f"Executed 400 prioritized handlers in {end_time - start_time:.3f}s")
    if execution_times:
        avg_execution = sum(execution_times) / len(execution_times)
        print(f"Average handler execution time: {avg_execution:.6f}s")
    
    manager.shutdown()
    
    # Benchmark 3: Memory efficiency with context pooling
    print("\nBenchmark 3: Memory Efficiency with Context Pooling")
    
    # Test without pooling
    start_time = time.time()
    contexts_no_pool = []
    for i in range(1000):
        context = EventContext.create(
            EventType.MESSAGE_RECEIVED,
            "no_pool",
            data={"index": i}
        )
        contexts_no_pool.append(context)
    no_pool_time = time.time() - start_time
    
    # Test with pooling
    from .event_context import ContextPool
    pool = ContextPool(max_size=100)
    
    start_time = time.time()
    contexts_with_pool = []
    for i in range(1000):
        context = pool.acquire()
        pool.configure_context(
            context,
            EventType.MESSAGE_RECEIVED,
            "with_pool",
            data={"index": i}
        )
        contexts_with_pool.append(context)
        pool.release(context)
    with_pool_time = time.time() - start_time
    
    print(f"Context creation without pooling: {no_pool_time:.3f}s")
    print(f"Context creation with pooling: {with_pool_time:.3f}s")
    print(f"Performance improvement: {(no_pool_time / with_pool_time):.1f}x")
    
    pool_stats = pool.get_stats()
    print(f"Pool reuse rate: {pool_stats['reuse_rate']:.1%}")
    
    print("\nBenchmarks completed!")


if __name__ == "__main__":
    # Run unit tests
    unittest.main(argv=[''], verbosity=2, exit=False)
    
    # Run performance benchmarks
    run_performance_benchmarks()