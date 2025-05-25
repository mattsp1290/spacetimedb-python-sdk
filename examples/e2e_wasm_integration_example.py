"""
Example: End-to-End WASM Integration with SpacetimeDB Python SDK

Demonstrates real-world usage patterns with actual WASM modules:
- Real-time subscriptions and updates
- Reducer calls and responses
- Event streaming and handling
- Concurrent operations
- Error handling and recovery
"""

import asyncio
import time
from typing import List, Dict, Any

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    SubscriptionStrategy,
    EventContext,
    EventType,
    
    # WASM integration
    SpacetimeDBServer,
    SpacetimeDBConfig,
    WASMModule,
    WASMTestHarness,
    PerformanceBenchmark,
    
    # Logging
    configure_default_logging,
    get_logger,
)


# Configure logging
configure_default_logging(debug=False)
logger = get_logger()


class E2EWASMIntegrationExample:
    """Examples demonstrating end-to-end WASM integration."""
    
    def __init__(self):
        self.server = None
        self.harness = None
        self.benchmark = PerformanceBenchmark()
    
    async def setup(self):
        """Set up SpacetimeDB server and test harness."""
        print("Setting up SpacetimeDB server...")
        
        # Configure and start server
        config = SpacetimeDBConfig(listen_port=3100)
        self.server = SpacetimeDBServer(config)
        self.server.start()
        
        # Create test harness
        self.harness = WASMTestHarness(self.server)
        await self.harness.setup()
        
        print("✅ Server ready!")
    
    async def teardown(self):
        """Clean up resources."""
        if self.harness:
            await self.harness.teardown()
        if self.server:
            self.server.stop()
    
    async def example_1_real_time_chat(self):
        """Example 1: Real-time chat application."""
        print("\n=== Example 1: Real-Time Chat ===")
        
        # Load WASM module
        module = WASMModule.from_file("path/to/chat_module.wasm", "chat")
        
        # Publish module
        db_address = await self.harness.publish_module(module, "chat_demo")
        print(f"Chat module published at: {db_address}")
        
        # Create client
        client = (ModernSpacetimeDBClient.builder()
                  .with_uri(f"ws://localhost:3100")
                  .with_db_name(db_address)
                  .with_module_name("chat_demo")
                  .build())
        
        await client.connect()
        
        try:
            # Track messages
            messages = []
            
            def on_message(event: EventContext):
                if event.type == EventType.INSERT:
                    msg = event.data
                    messages.append(msg)
                    print(f"💬 {msg.get('sender', 'Unknown')}: {msg.get('content', '')}")
            
            # Subscribe to messages
            client.on(EventType.INSERT, on_message)
            
            subscription = (client.subscription_builder()
                           .with_strategy(SubscriptionStrategy.REALTIME)
                           .subscribe(["SELECT * FROM messages"]))
            
            await asyncio.sleep(0.5)  # Let subscription stabilize
            
            # Send some messages
            await client.call_reducer("send_message", {
                "sender": "Alice",
                "content": "Hello everyone!"
            })
            
            await client.call_reducer("send_message", {
                "sender": "Bob",
                "content": "Hey Alice! How are you?"
            })
            
            await client.call_reducer("send_message", {
                "sender": "Alice",
                "content": "Doing great, thanks!"
            })
            
            # Wait for messages
            await asyncio.sleep(1.0)
            
            print(f"\nTotal messages received: {len(messages)}")
            
        finally:
            await client.disconnect()
    
    async def example_2_collaborative_todo(self):
        """Example 2: Collaborative todo list."""
        print("\n=== Example 2: Collaborative Todo List ===")
        
        # Create simulated module
        module = WASMModule.from_bytes(b"mock_todo_module", "todo")
        db_address = await self.harness.publish_module(module, "todo_demo")
        
        # Create multiple clients (simulating different users)
        clients = []
        for i, user in enumerate(["Alice", "Bob", "Charlie"]):
            client = await self.harness.create_client(db_address)
            client.user_name = user
            clients.append(client)
        
        try:
            # Track todos across all clients
            todos_per_client = {i: [] for i in range(len(clients))}
            
            # Set up event handlers
            for i, client in enumerate(clients):
                def make_handler(client_id):
                    def handler(event: EventContext):
                        if event.type == EventType.INSERT:
                            todos_per_client[client_id].append(event.data)
                            print(f"👤 {clients[client_id].user_name} sees new todo: "
                                  f"{event.data.get('title')}")
                    return handler
                
                client.on(EventType.INSERT, make_handler(i))
            
            # Subscribe all clients
            for client in clients:
                await (client.subscription_builder()
                      .subscribe(["SELECT * FROM todos"]))
            
            await asyncio.sleep(0.5)
            
            # Users create todos
            with self.benchmark.measure("todo_creation"):
                await clients[0].call_reducer("create_todo", {
                    "title": "Buy groceries",
                    "assigned_to": "Alice"
                })
                
                await clients[1].call_reducer("create_todo", {
                    "title": "Review PR #123",
                    "assigned_to": "Bob"
                })
                
                await clients[2].call_reducer("create_todo", {
                    "title": "Deploy to production",
                    "assigned_to": "Charlie"
                })
            
            # Wait for propagation
            await asyncio.sleep(1.0)
            
            # Check consistency
            print("\nTodo visibility check:")
            for i, (client_id, todos) in enumerate(todos_per_client.items()):
                print(f"  {clients[i].user_name} sees {len(todos)} todos")
            
            # Performance stats
            stats = self.benchmark.get_stats("todo_creation")
            if stats:
                print(f"\nTodo creation time: {stats['mean']*1000:.2f}ms")
            
        finally:
            for client in clients:
                await client.disconnect()
    
    async def example_3_live_dashboard(self):
        """Example 3: Live analytics dashboard."""
        print("\n=== Example 3: Live Analytics Dashboard ===")
        
        # Create simulated module
        module = WASMModule.from_bytes(b"mock_analytics_module", "analytics")
        db_address = await self.harness.publish_module(module, "analytics_demo")
        
        client = await self.harness.create_client(db_address)
        
        try:
            # Track metrics
            metrics = {
                "page_views": 0,
                "unique_users": set(),
                "events": []
            }
            
            def on_analytics_event(event: EventContext):
                data = event.data
                event_type = data.get("event_type")
                
                if event_type == "page_view":
                    metrics["page_views"] += 1
                    metrics["unique_users"].add(data.get("user_id"))
                
                metrics["events"].append({
                    "type": event_type,
                    "timestamp": time.time()
                })
            
            client.on(EventType.INSERT, on_analytics_event)
            
            # Subscribe to analytics events
            subscription = (client.subscription_builder()
                           .subscribe(["SELECT * FROM analytics_events"]))
            
            await asyncio.sleep(0.5)
            
            # Simulate user activity
            print("Simulating user activity...")
            
            with self.benchmark.measure("event_ingestion"):
                # Simulate page views
                for i in range(20):
                    await client.call_reducer("track_event", {
                        "event_type": "page_view",
                        "user_id": f"user_{i % 5}",
                        "page": f"/page_{i % 3}",
                        "timestamp": int(time.time() * 1000)
                    })
                    await asyncio.sleep(0.05)  # Simulate real-time events
            
            # Display live metrics
            print(f"\nLive Dashboard Metrics:")
            print(f"  Total page views: {metrics['page_views']}")
            print(f"  Unique users: {len(metrics['unique_users'])}")
            print(f"  Events in last second: "
                  f"{len([e for e in metrics['events'] if time.time() - e['timestamp'] < 1])}")
            
            # Performance stats
            stats = self.benchmark.get_stats("event_ingestion")
            if stats:
                print(f"\nEvent ingestion rate: "
                      f"{20 / (stats['mean'] or 1):.2f} events/sec")
            
        finally:
            await client.disconnect()
    
    async def example_4_high_frequency_trading(self):
        """Example 4: High-frequency trading simulation."""
        print("\n=== Example 4: High-Frequency Trading ===")
        
        # Create simulated module
        module = WASMModule.from_bytes(b"mock_trading_module", "trading")
        db_address = await self.harness.publish_module(module, "trading_demo")
        
        client = await self.harness.create_client(db_address)
        
        try:
            # Track trades
            trades = []
            trade_latencies = []
            
            def on_trade(event: EventContext):
                if event.type == EventType.INSERT:
                    trade = event.data
                    trades.append(trade)
                    
                    # Calculate latency
                    if "client_timestamp" in trade:
                        latency = time.time() * 1000 - trade["client_timestamp"]
                        trade_latencies.append(latency)
            
            client.on(EventType.INSERT, on_trade)
            
            # Subscribe to trades
            subscription = (client.subscription_builder()
                           .with_strategy(SubscriptionStrategy.REALTIME)
                           .subscribe(["SELECT * FROM trades"]))
            
            await asyncio.sleep(0.5)
            
            # Execute rapid trades
            print("Executing rapid trades...")
            
            with self.benchmark.measure("trade_execution"):
                tasks = []
                for i in range(100):
                    task = client.call_reducer("execute_trade", {
                        "symbol": f"STOCK{i % 10}",
                        "quantity": 100 + i,
                        "price": 100.0 + (i % 20) * 0.5,
                        "side": "buy" if i % 2 == 0 else "sell",
                        "client_timestamp": time.time() * 1000
                    })
                    tasks.append(task)
                
                # Execute all trades concurrently
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Wait for all trades to be processed
            await asyncio.sleep(2.0)
            
            # Analyze performance
            print(f"\nTrading Performance Metrics:")
            print(f"  Trades executed: {len(trades)}")
            
            if trade_latencies:
                avg_latency = sum(trade_latencies) / len(trade_latencies)
                min_latency = min(trade_latencies)
                max_latency = max(trade_latencies)
                
                print(f"  Average latency: {avg_latency:.2f}ms")
                print(f"  Min latency: {min_latency:.2f}ms")
                print(f"  Max latency: {max_latency:.2f}ms")
            
            stats = self.benchmark.get_stats("trade_execution")
            if stats:
                print(f"  Execution time: {stats['mean']*1000:.2f}ms")
                print(f"  Throughput: {100 / (stats['mean'] or 1):.2f} trades/sec")
            
        finally:
            await client.disconnect()
    
    async def example_5_error_handling(self):
        """Example 5: Robust error handling."""
        print("\n=== Example 5: Error Handling ===")
        
        # Create simulated module
        module = WASMModule.from_bytes(b"mock_error_module", "errors")
        db_address = await self.harness.publish_module(module, "error_demo")
        
        client = await self.harness.create_client(db_address)
        
        try:
            # Track errors
            errors = []
            recoveries = 0
            
            def on_error(event: EventContext):
                errors.append({
                    "type": event.type,
                    "message": event.data.get("message", "Unknown error"),
                    "timestamp": time.time()
                })
                print(f"❌ Error: {event.data.get('message')}")
            
            def on_recovery():
                nonlocal recoveries
                recoveries += 1
                print("✅ Connection recovered!")
            
            client.on(EventType.ERROR, on_error)
            client.on_reconnect = on_recovery
            
            # Test various error scenarios
            print("Testing error scenarios...")
            
            # 1. Invalid reducer
            try:
                await client.call_reducer("nonexistent_reducer", {})
            except Exception as e:
                print(f"  Expected: {e}")
            
            # 2. Invalid arguments
            try:
                await client.call_reducer("valid_reducer", {
                    "invalid_field": "test"
                })
            except Exception as e:
                print(f"  Expected: {e}")
            
            # 3. Subscription error
            try:
                sub = (client.subscription_builder()
                      .on_error(lambda e: print(f"  Subscription error: {e}"))
                      .subscribe(["INVALID SQL SYNTAX"]))
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"  Expected: {e}")
            
            # 4. Recovery test
            print("\nTesting recovery...")
            
            # Create valid subscription
            subscription = (client.subscription_builder()
                           .with_auto_reconnect(True)
                           .subscribe(["SELECT * FROM events"]))
            
            await asyncio.sleep(0.5)
            
            # Simulate brief disconnection
            # In real scenario, this would be network interruption
            
            print(f"\nError handling summary:")
            print(f"  Total errors: {len(errors)}")
            print(f"  Recoveries: {recoveries}")
            print(f"  System stable: {subscription.is_active()}")
            
        finally:
            await client.disconnect()


async def main():
    """Run all end-to-end WASM integration examples."""
    print("SpacetimeDB End-to-End WASM Integration Examples")
    print("===============================================")
    
    example = E2EWASMIntegrationExample()
    
    try:
        # Set up server
        await example.setup()
        
        # Note: These examples use mock WASM modules for demonstration
        # In real usage, you would use actual compiled WASM modules
        
        # Run examples
        # await example.example_1_real_time_chat()
        await example.example_2_collaborative_todo()
        await example.example_3_live_dashboard()
        await example.example_4_high_frequency_trading()
        await example.example_5_error_handling()
        
        print("\n✅ All examples completed!")
        
        print("\nKey Takeaways:")
        print("- Real-time subscriptions provide instant updates")
        print("- Multiple clients stay synchronized automatically")
        print("- High-frequency operations are supported")
        print("- Error handling ensures system reliability")
        print("- Performance metrics help optimization")
        
    finally:
        await example.teardown()


if __name__ == "__main__":
    asyncio.run(main()) 