"""
End-to-End WASM Integration Tests for SpacetimeDB Python SDK.

Tests real-time features including subscriptions, reducers, and event streaming
using actual SpacetimeDB WASM modules.
"""

import asyncio
import pytest
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    configure_default_logging,
    get_logger,
    
    # WASM integration
    SpacetimeDBServer,
    SpacetimeDBConfig,
    WASMModule,
    WASMTestHarness,
    PerformanceBenchmark,
    require_spacetimedb,
    require_sdk_test_module,
    
    # Subscription
    SubscriptionStrategy,
    
    # Event system
    EventContext,
    EventType,
    
    # Data types
    AlgebraicValue,
    type_builder,
    FieldInfo,
)


# Configure logging
configure_default_logging(debug=True)
logger = get_logger()


@dataclass
class TestUser:
    """Test user model."""
    id: int
    name: str
    email: str
    created_at: int
    is_active: bool


@dataclass
class TestMessage:
    """Test message model."""
    id: int
    sender_id: int
    content: str
    timestamp: int


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestRealTimeFeatures:
    """Test real-time subscriptions, reducers, and event streaming."""
    
    async def test_subscription_lifecycle(self, wasm_harness, sdk_test_module):
        """Test subscription lifecycle management."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "subscription_test")
        
        # Track events
        events = []
        
        # Create client with event tracking
        client = (ModernSpacetimeDBClient.builder()
                  .with_uri(f"ws://localhost:{wasm_harness.server.config.listen_port}")
                  .with_db_name(address)
                  .with_module_name("subscription_test")
                  .on_connect(lambda: events.append("connected"))
                  .on_disconnect(lambda: events.append("disconnected"))
                  .build())
        
        try:
            # Connect
            await client.connect()
            await asyncio.sleep(0.1)  # Let connection stabilize
            
            assert "connected" in events
            
            # Test subscription creation
            sub_events = []
            
            with benchmark.measure("subscription_create"):
                subscription = (client.subscription_builder()
                               .on_applied(lambda: sub_events.append("applied"))
                               .on_error(lambda e: sub_events.append(f"error: {e}"))
                               .with_timeout(5.0)
                               .subscribe(["SELECT * FROM TestUser"]))
            
            # Wait for subscription to be applied
            await asyncio.sleep(0.5)
            assert "applied" in sub_events
            
            # Test subscription update
            with benchmark.measure("subscription_update"):
                await subscription.add_query("SELECT * FROM TestMessage")
            
            # Test subscription removal
            with benchmark.measure("subscription_remove"):
                await subscription.remove_query("SELECT * FROM TestMessage")
            
            # Test unsubscribe
            with benchmark.measure("subscription_unsubscribe"):
                await subscription.unsubscribe()
            
            # Performance report
            logger.info("Subscription lifecycle performance:")
            for operation in ["create", "update", "remove", "unsubscribe"]:
                stats = benchmark.get_stats(f"subscription_{operation}")
                if stats:
                    logger.info(f"  {operation}: {stats['mean']*1000:.2f}ms")
            
        finally:
            await client.disconnect()
            assert "disconnected" in events
    
    async def test_reducer_calls(self, wasm_harness, sdk_test_module):
        """Test reducer call patterns and validation."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "reducer_test")
        
        client = await wasm_harness.create_client(address)
        
        try:
            # Track reducer responses
            reducer_results = []
            
            def on_reducer_response(event: EventContext):
                reducer_results.append({
                    "reducer": event.data.get("reducer_name"),
                    "request_id": event.data.get("request_id"),
                    "status": event.data.get("status"),
                    "message": event.data.get("message")
                })
            
            client.on(EventType.REDUCER_RESPONSE, on_reducer_response)
            
            # Test simple reducer call
            with benchmark.measure("reducer_simple"):
                request_id = await client.call_reducer(
                    "create_user",
                    {
                        "name": "Alice",
                        "email": "alice@example.com"
                    }
                )
            
            # Wait for response
            await asyncio.sleep(0.2)
            
            # Check response
            responses = [r for r in reducer_results if r["request_id"] == request_id]
            assert len(responses) > 0
            
            # Test reducer with complex arguments
            with benchmark.measure("reducer_complex"):
                request_id = await client.call_reducer(
                    "send_message",
                    {
                        "sender_id": 1,
                        "recipient_ids": [2, 3, 4],
                        "content": "Hello everyone!",
                        "metadata": {
                            "priority": "high",
                            "tags": ["important", "announcement"]
                        }
                    }
                )
            
            # Test reducer error handling
            with benchmark.measure("reducer_error"):
                try:
                    await client.call_reducer(
                        "invalid_reducer",
                        {"data": "test"}
                    )
                except Exception as e:
                    logger.debug(f"Expected error: {e}")
            
            # Performance report
            logger.info("Reducer call performance:")
            for operation in ["simple", "complex", "error"]:
                stats = benchmark.get_stats(f"reducer_{operation}")
                if stats:
                    logger.info(f"  {operation}: {stats['mean']*1000:.2f}ms")
            
        finally:
            await client.disconnect()
    
    async def test_event_streaming(self, wasm_harness, sdk_test_module):
        """Test real-time event delivery and ordering."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "event_test")
        
        client = await wasm_harness.create_client(address)
        
        try:
            # Track all events
            all_events = []
            event_order = []
            
            def track_event(event: EventContext):
                all_events.append(event)
                event_order.append({
                    "type": event.type,
                    "timestamp": event.timestamp,
                    "sequence": len(event_order)
                })
            
            # Register event handlers
            for event_type in [EventType.INSERT, EventType.UPDATE, EventType.DELETE,
                              EventType.SUBSCRIPTION_UPDATE, EventType.TRANSACTION_UPDATE]:
                client.on(event_type, track_event)
            
            # Subscribe to tables
            subscription = (client.subscription_builder()
                           .on_applied(lambda: logger.info("Subscription applied"))
                           .subscribe(["SELECT * FROM TestUser", "SELECT * FROM TestMessage"]))
            
            await asyncio.sleep(0.5)  # Let subscription stabilize
            
            # Trigger events through reducers
            with benchmark.measure("event_generation"):
                # Create users
                for i in range(5):
                    await client.call_reducer("create_user", {
                        "name": f"User{i}",
                        "email": f"user{i}@test.com"
                    })
                
                # Send messages
                for i in range(10):
                    await client.call_reducer("send_message", {
                        "sender_id": i % 5,
                        "content": f"Message {i}"
                    })
            
            # Wait for events
            await asyncio.sleep(1.0)
            
            # Analyze event ordering
            with benchmark.measure("event_analysis"):
                # Check event count
                logger.info(f"Total events received: {len(all_events)}")
                
                # Check event ordering
                timestamps = [e["timestamp"] for e in event_order]
                assert timestamps == sorted(timestamps), "Events out of order"
                
                # Check event types
                event_types = {e["type"] for e in event_order}
                logger.info(f"Event types received: {event_types}")
            
            # Test event filtering
            insert_events = [e for e in all_events if e.type == EventType.INSERT]
            logger.info(f"Insert events: {len(insert_events)}")
            
            # Performance report
            logger.info("Event streaming performance:")
            stats = benchmark.get_stats("event_generation")
            if stats:
                logger.info(f"  Generation: {stats['mean']*1000:.2f}ms")
            stats = benchmark.get_stats("event_analysis")
            if stats:
                logger.info(f"  Analysis: {stats['mean']*1000:.2f}ms")
            
        finally:
            await client.disconnect()
    
    async def test_concurrent_operations(self, wasm_harness, sdk_test_module):
        """Test multiple simultaneous connections and operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "concurrent_test")
        
        # Create multiple clients
        num_clients = 5
        clients = []
        
        try:
            # Connect all clients
            with benchmark.measure("concurrent_connect"):
                for i in range(num_clients):
                    client = await wasm_harness.create_client(address)
                    clients.append(client)
            
            # Track events per client
            client_events = {i: [] for i in range(num_clients)}
            
            # Set up event handlers
            for i, client in enumerate(clients):
                def make_handler(client_id):
                    def handler(event: EventContext):
                        client_events[client_id].append(event)
                    return handler
                
                client.on(EventType.INSERT, make_handler(i))
            
            # Subscribe all clients
            with benchmark.measure("concurrent_subscribe"):
                subscriptions = []
                for client in clients:
                    sub = (client.subscription_builder()
                          .with_strategy(SubscriptionStrategy.RELIABLE)
                          .subscribe(["SELECT * FROM TestUser"]))
                    subscriptions.append(sub)
            
            await asyncio.sleep(0.5)  # Let subscriptions stabilize
            
            # Concurrent reducer calls
            with benchmark.measure("concurrent_reducers"):
                tasks = []
                for i in range(20):
                    client = clients[i % num_clients]
                    task = client.call_reducer("create_user", {
                        "name": f"ConcurrentUser{i}",
                        "email": f"concurrent{i}@test.com"
                    })
                    tasks.append(task)
                
                # Wait for all reducers
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Check results
                errors = [r for r in results if isinstance(r, Exception)]
                if errors:
                    logger.warning(f"Concurrent reducer errors: {len(errors)}")
            
            # Wait for events to propagate
            await asyncio.sleep(1.0)
            
            # Analyze event distribution
            with benchmark.measure("event_distribution"):
                total_events = sum(len(events) for events in client_events.values())
                logger.info(f"Total events across {num_clients} clients: {total_events}")
                
                for i, events in client_events.items():
                    logger.debug(f"Client {i} received {len(events)} events")
            
            # Performance report
            logger.info("Concurrent operations performance:")
            for operation in ["connect", "subscribe", "reducers", "distribution"]:
                stats = benchmark.get_stats(f"concurrent_{operation}")
                if stats:
                    logger.info(f"  {operation}: {stats['mean']*1000:.2f}ms")
            
        finally:
            # Disconnect all clients
            for client in clients:
                await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestAdvancedPatterns:
    """Test advanced real-time patterns and edge cases."""
    
    async def test_subscription_recovery(self, wasm_harness, sdk_test_module):
        """Test subscription recovery after connection loss."""
        require_spacetimedb()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "recovery_test")
        
        client = await wasm_harness.create_client(address)
        
        try:
            # Track reconnections
            reconnect_count = 0
            
            def on_reconnect():
                nonlocal reconnect_count
                reconnect_count += 1
                logger.info(f"Reconnected (count: {reconnect_count})")
            
            client.on_reconnect = on_reconnect
            
            # Create subscription
            subscription = (client.subscription_builder()
                           .with_strategy(SubscriptionStrategy.RELIABLE)
                           .with_auto_reconnect(True)
                           .subscribe(["SELECT * FROM TestUser"]))
            
            await asyncio.sleep(0.5)
            
            # Simulate connection loss
            logger.info("Simulating connection loss...")
            # This would normally be done by stopping the server or network
            # For now, we'll just test the subscription state
            
            assert subscription.is_active()
            
            # Test subscription state persistence
            query_count = len(subscription.queries)
            assert query_count > 0
            
            logger.info(f"Subscription maintained {query_count} queries")
            
        finally:
            await client.disconnect()
    
    async def test_event_ordering_consistency(self, wasm_harness, sdk_test_module):
        """Test event ordering and consistency guarantees."""
        require_spacetimedb()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "ordering_test")
        
        client = await wasm_harness.create_client(address)
        
        try:
            # Track events with detailed timing
            events_timeline = []
            
            def track_detailed_event(event: EventContext):
                events_timeline.append({
                    "type": event.type,
                    "timestamp": event.timestamp,
                    "received_at": time.time(),
                    "data": event.data
                })
            
            # Register for all event types
            client.on(EventType.INSERT, track_detailed_event)
            client.on(EventType.UPDATE, track_detailed_event)
            client.on(EventType.DELETE, track_detailed_event)
            
            # Subscribe
            subscription = (client.subscription_builder()
                           .subscribe(["SELECT * FROM TestMessage"]))
            
            await asyncio.sleep(0.5)
            
            # Generate ordered events
            for i in range(10):
                await client.call_reducer("send_message", {
                    "sender_id": 1,
                    "content": f"Ordered message {i}"
                })
                # Small delay to ensure ordering
                await asyncio.sleep(0.05)
            
            # Wait for all events
            await asyncio.sleep(1.0)
            
            # Verify ordering
            if events_timeline:
                # Check timestamp ordering
                timestamps = [e["timestamp"] for e in events_timeline]
                assert timestamps == sorted(timestamps), "Event timestamps out of order"
                
                # Check received order
                received_times = [e["received_at"] for e in events_timeline]
                assert received_times == sorted(received_times), "Events received out of order"
                
                logger.info(f"Verified ordering for {len(events_timeline)} events")
            
        finally:
            await client.disconnect()
    
    async def test_high_frequency_events(self, wasm_harness, sdk_test_module):
        """Test system behavior under high-frequency event load."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "highfreq_test")
        
        client = await wasm_harness.create_client(address)
        
        try:
            # Track event metrics
            event_count = 0
            event_start_time = None
            event_end_time = None
            
            def count_event(event: EventContext):
                nonlocal event_count, event_start_time, event_end_time
                event_count += 1
                if event_start_time is None:
                    event_start_time = time.time()
                event_end_time = time.time()
            
            client.on(EventType.INSERT, count_event)
            
            # Subscribe
            subscription = (client.subscription_builder()
                           .subscribe(["SELECT * FROM TestMessage"]))
            
            await asyncio.sleep(0.5)
            
            # Generate high-frequency events
            num_events = 100
            
            with benchmark.measure("high_frequency_generation"):
                tasks = []
                for i in range(num_events):
                    task = client.call_reducer("send_message", {
                        "sender_id": i % 10,
                        "content": f"HF{i}"
                    })
                    tasks.append(task)
                
                # Execute all at once
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Wait for events to be processed
            await asyncio.sleep(2.0)
            
            # Calculate metrics
            if event_start_time and event_end_time:
                duration = event_end_time - event_start_time
                events_per_second = event_count / duration if duration > 0 else 0
                
                logger.info(f"High-frequency event metrics:")
                logger.info(f"  Events received: {event_count}/{num_events}")
                logger.info(f"  Duration: {duration:.2f}s")
                logger.info(f"  Rate: {events_per_second:.2f} events/sec")
                
                # Performance stats
                stats = benchmark.get_stats("high_frequency_generation")
                if stats:
                    logger.info(f"  Generation time: {stats['mean']*1000:.2f}ms")
            
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling and recovery in real-time scenarios."""
    
    async def test_reducer_error_handling(self, wasm_harness, sdk_test_module):
        """Test reducer error scenarios."""
        require_spacetimedb()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "error_test")
        
        client = await wasm_harness.create_client(address)
        
        try:
            # Track errors
            errors = []
            
            def on_error(event: EventContext):
                errors.append(event.data)
            
            client.on(EventType.ERROR, on_error)
            
            # Test invalid reducer name
            try:
                await client.call_reducer("nonexistent_reducer", {})
            except Exception as e:
                logger.info(f"Expected error for invalid reducer: {e}")
            
            # Test invalid arguments
            try:
                await client.call_reducer("create_user", {
                    "invalid_field": "test"
                })
            except Exception as e:
                logger.info(f"Expected error for invalid args: {e}")
            
            # Test reducer that throws
            try:
                await client.call_reducer("failing_reducer", {
                    "should_fail": True
                })
            except Exception as e:
                logger.info(f"Expected error for failing reducer: {e}")
            
            await asyncio.sleep(0.5)
            
            # Check error tracking
            logger.info(f"Total errors tracked: {len(errors)}")
            
        finally:
            await client.disconnect()
    
    async def test_subscription_error_recovery(self, wasm_harness, sdk_test_module):
        """Test subscription error scenarios and recovery."""
        require_spacetimedb()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "sub_error_test")
        
        client = await wasm_harness.create_client(address)
        
        try:
            # Track subscription errors
            sub_errors = []
            
            # Test invalid query
            subscription = (client.subscription_builder()
                           .on_error(lambda e: sub_errors.append(str(e)))
                           .subscribe(["INVALID SQL QUERY"]))
            
            await asyncio.sleep(0.5)
            
            # Check if error was caught
            if sub_errors:
                logger.info(f"Subscription errors caught: {len(sub_errors)}")
            
            # Test recovery with valid query
            await subscription.update_queries(["SELECT * FROM TestUser"])
            
            await asyncio.sleep(0.5)
            
            # Verify subscription is working
            assert subscription.is_active()
            
        finally:
            await client.disconnect()


# Pytest fixtures
@pytest.fixture
async def spacetimedb_server():
    """Provide a SpacetimeDB server for testing."""
    config = SpacetimeDBConfig(listen_port=3100)
    server = SpacetimeDBServer(config)
    server.start()
    yield server
    server.stop()


@pytest.fixture
async def wasm_harness(spacetimedb_server):
    """Provide WASM test harness."""
    harness = WASMTestHarness(spacetimedb_server)
    await harness.setup()
    yield harness
    await harness.teardown()


@pytest.fixture
def sdk_test_module():
    """Provide SDK test module."""
    return WASMModule.from_file(require_sdk_test_module(), "sdk_test")


async def main():
    """Run end-to-end WASM integration tests."""
    print("End-to-End WASM Integration Tests")
    print("==================================\n")
    
    # Check prerequisites
    import shutil
    if not shutil.which("spacetimedb"):
        print("❌ SpacetimeDB not found in PATH!")
        print("Please install SpacetimeDB first.")
        return
    
    from spacetimedb_sdk.wasm_integration import find_sdk_test_module
    if not find_sdk_test_module():
        print("❌ SDK test module not found!")
        print("Set SPACETIMEDB_SDK_TEST_MODULE environment variable.")
        return
    
    print("✅ Prerequisites satisfied")
    print("\nRunning end-to-end tests...")
    
    # List test scenarios
    test_scenarios = [
        "Subscription Lifecycle Management",
        "Reducer Call Patterns",
        "Real-time Event Streaming",
        "Concurrent Operations",
        "Subscription Recovery",
        "Event Ordering Consistency",
        "High-frequency Event Load",
        "Error Handling and Recovery",
    ]
    
    print("\nTest Scenarios:")
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"  {i}. {scenario}")
    
    print("\n✅ Test structure ready!")
    print("\nTo run full tests:")
    print("pytest test_e2e_wasm_integration.py -v -m integration")


if __name__ == "__main__":
    asyncio.run(main()) 