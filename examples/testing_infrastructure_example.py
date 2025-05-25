"""
Example: Testing Infrastructure for SpacetimeDB Python SDK

Demonstrates how to use the comprehensive testing utilities:
- Mock connections for unit testing
- Test data generation
- Protocol compliance testing
- Performance benchmarking
- Test fixtures and isolation
"""

import asyncio
import pytest
import time
from pathlib import Path

from spacetimedb_sdk import (
    MockSpacetimeDBConnection,
    MockWebSocketAdapter,
    TestDataGenerator,
    ProtocolComplianceTester,
    PerformanceBenchmark,
    MockMessage,
    MessageType,
    spacetimedb_test,
    integration_test,
    performance_test,
    TestDatabase,
    TestIsolation,
    CoverageTracker
)


class TestingInfrastructureExample:
    """Examples demonstrating testing infrastructure usage."""
    
    async def example_1_mock_connection(self):
        """Example 1: Using mock connections for unit testing."""
        print("\n=== Example 1: Mock Connection ===")
        
        # Create a mock connection
        mock_conn = MockSpacetimeDBConnection("test_module")
        
        # Track connection events
        connected = False
        def on_connect():
            nonlocal connected
            connected = True
        
        mock_conn.on_connect(on_connect)
        
        # Connect
        await mock_conn.connect()
        print(f"Connected: {connected}")
        print(f"Identity: {mock_conn.identity.to_hex()[:16]}...")
        print(f"Connection ID: {mock_conn.connection_id.to_uuid()}")
        
        # Subscribe to queries
        query_id = mock_conn.subscribe([
            "SELECT * FROM users WHERE active = true",
            "SELECT * FROM messages ORDER BY timestamp DESC"
        ])
        print(f"Subscription created: {query_id.to_hex()[:16]}...")
        
        # Add test data
        mock_conn.add_table_row("users", {
            "id": 1,
            "name": "Alice",
            "active": True
        })
        print("Added test user")
        
        # Disconnect
        await mock_conn.disconnect()
        print("Disconnected")
    
    async def example_2_websocket_mocking(self):
        """Example 2: Mock WebSocket adapter for protocol testing."""
        print("\n=== Example 2: WebSocket Mocking ===")
        
        # Create mock WebSocket
        ws = MockWebSocketAdapter()
        
        # Set up message queue
        ws.add_message(MockMessage(
            MessageType.IDENTITY_TOKEN,
            {
                "identity": "00112233445566778899aabbccddeeff",
                "token": "test_token_123",
                "address": "1234567890abcdef"
            }
        ))
        
        ws.add_message(MockMessage(
            MessageType.TRANSACTION_UPDATE,
            {
                "tables": {
                    "users": {
                        "inserts": [
                            {"id": 1, "name": "Test User"}
                        ]
                    }
                }
            }
        ))
        
        # Connect and receive messages
        await ws.connect("ws://test/module")
        
        # Receive identity
        identity_msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
        print(f"Received identity message: {identity_msg[:50]}...")
        
        # Receive transaction
        transaction_msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
        print(f"Received transaction: {transaction_msg[:50]}...")
        
        await ws.close()
    
    def example_3_test_data_generation(self):
        """Example 3: Generate test data for tables."""
        print("\n=== Example 3: Test Data Generation ===")
        
        # Generate individual records
        user = TestDataGenerator.generate_user(user_id=42)
        print(f"Generated user: {user}")
        
        message = TestDataGenerator.generate_message(
            message_id=100,
            user_id=42,
            content="Hello, SpacetimeDB!"
        )
        print(f"Generated message: {message}")
        
        # Generate bulk data
        users = TestDataGenerator.generate_bulk_data("users", 5)
        print(f"\nGenerated {len(users)} users:")
        for user in users:
            print(f"  - {user['username']} ({user['email']})")
        
        # Custom generator
        def generate_game_state(game_id):
            return {
                "id": game_id,
                "players": [],
                "status": "waiting",
                "created_at": int(time.time() * 1_000_000)
            }
        
        games = TestDataGenerator.generate_bulk_data(
            "games", 3, generate_game_state
        )
        print(f"\nGenerated {len(games)} games")
    
    async def example_4_protocol_compliance(self):
        """Example 4: Test protocol compliance."""
        print("\n=== Example 4: Protocol Compliance Testing ===")
        
        # Create connection
        conn = MockSpacetimeDBConnection()
        
        # Create compliance tester
        tester = ProtocolComplianceTester(conn)
        
        # Run compliance tests
        print("Running connection lifecycle test...")
        lifecycle_passed = await tester.test_connection_lifecycle()
        print(f"Lifecycle test: {'PASSED' if lifecycle_passed else 'FAILED'}")
        
        print("\nRunning subscription protocol test...")
        subscription_passed = await tester.test_subscription_protocol()
        print(f"Subscription test: {'PASSED' if subscription_passed else 'FAILED'}")
        
        print("\nRunning reducer protocol test...")
        reducer_passed = await tester.test_reducer_protocol()
        print(f"Reducer test: {'PASSED' if reducer_passed else 'FAILED'}")
        
        # Get full report
        print("\n" + tester.get_report())
    
    async def example_5_performance_benchmarking(self):
        """Example 5: Benchmark performance of operations."""
        print("\n=== Example 5: Performance Benchmarking ===")
        
        # Create benchmark
        benchmark = PerformanceBenchmark()
        conn = MockSpacetimeDBConnection()
        
        # Benchmark connection
        print("Benchmarking connection operations...")
        await benchmark.benchmark_connection(conn, iterations=5)
        
        # Benchmark subscriptions
        print("Benchmarking subscriptions...")
        await benchmark.benchmark_subscriptions(
            conn,
            ["SELECT * FROM users", "SELECT * FROM messages"],
            iterations=10
        )
        
        # Benchmark reducer calls
        print("Benchmarking reducer calls...")
        
        # Register a test reducer
        conn.register_reducer("test_reducer", lambda x, y: x + y)
        
        await benchmark.benchmark_reducers(
            conn,
            "test_reducer",
            [10, 20],
            iterations=100
        )
        
        # Get report
        print("\n" + benchmark.get_report())
    
    async def example_6_test_database_fixture(self):
        """Example 6: Use test database fixture."""
        print("\n=== Example 6: Test Database Fixture ===")
        
        # Create connection and database
        conn = MockSpacetimeDBConnection()
        db = TestDatabase(conn)
        
        # Set up test database
        await db.setup()
        print(f"Created tables: {db.tables_created}")
        
        # Insert test data
        test_users = [
            {"id": 1, "username": "alice", "email": "alice@test.com"},
            {"id": 2, "username": "bob", "email": "bob@test.com"}
        ]
        
        for user in test_users:
            await db.insert_row("users", user)
        
        # Query data
        users = await db.get_table_data("users")
        print(f"Users in database: {len(users)}")
        
        # Clear table
        await db.clear_table("users")
        users_after = await db.get_table_data("users")
        print(f"Users after clear: {len(users_after)}")
        
        # Teardown restores initial state
        await db.teardown()
    
    def example_7_test_isolation(self):
        """Example 7: Test isolation for environment and files."""
        print("\n=== Example 7: Test Isolation ===")
        
        import os
        
        # Save current environment
        original_env = os.environ.get("SPACETIMEDB_TEST")
        
        with TestIsolation() as isolation:
            # Modify environment
            isolation.set_env("SPACETIMEDB_TEST", "isolated_value")
            print(f"Test env: {os.environ['SPACETIMEDB_TEST']}")
            
            # Create temporary files
            config_file = isolation.create_temp_file(
                "test_config",
                "database_url: ws://localhost:3000\n"
            )
            print(f"Created temp file: {config_file}")
            
            # Use the file
            config_content = config_file.read_text()
            print(f"Config content: {config_content.strip()}")
        
        # Environment restored
        restored = os.environ.get("SPACETIMEDB_TEST", "not set")
        print(f"Environment after test: {restored}")
        print(f"Temp file exists: {config_file.exists()}")
    
    def example_8_coverage_tracking(self):
        """Example 8: Track test coverage of operations."""
        print("\n=== Example 8: Coverage Tracking ===")
        
        # Create coverage tracker
        tracker = CoverageTracker()
        
        # Mark operations as covered
        operations_tested = [
            "connect", "disconnect", "subscribe",
            "call_reducer", "compression", "energy_tracking"
        ]
        
        for op in operations_tested:
            tracker.mark_covered(op)
            print(f"Tested: {op}")
        
        # Get coverage report
        print("\n" + tracker.get_coverage_report())
    
    def example_9_test_decorators(self):
        """Example 9: Using test decorators."""
        print("\n=== Example 9: Test Decorators ===")
        
        # Define test functions with decorators
        @spacetimedb_test(requires_connection=True, timeout=30.0)
        async def test_subscription():
            """Test requiring connection."""
            conn = MockSpacetimeDBConnection()
            await conn.connect()
            query_id = conn.subscribe(["SELECT * FROM test"])
            assert query_id is not None
            await conn.disconnect()
        
        @integration_test
        @performance_test
        async def test_full_workflow():
            """Integration and performance test."""
            benchmark = PerformanceBenchmark()
            conn = MockSpacetimeDBConnection()
            
            with benchmark.measure("full_workflow"):
                await conn.connect()
                conn.subscribe(["SELECT * FROM users"])
                conn.call_reducer("test", "arg")
                await conn.disconnect()
        
        # Check decorator metadata
        print(f"test_subscription requires connection: "
              f"{test_subscription._requires_connection}")
        print(f"test_subscription timeout: {test_subscription._timeout}s")
        print(f"test_full_workflow is integration test: "
              f"{hasattr(test_full_workflow, '_integration_test')}")
        print(f"test_full_workflow is performance test: "
              f"{hasattr(test_full_workflow, '_performance_test')}")
    
    async def example_10_full_test_scenario(self):
        """Example 10: Complete test scenario."""
        print("\n=== Example 10: Full Test Scenario ===")
        
        # Set up test infrastructure
        conn = MockSpacetimeDBConnection("chat_module")
        benchmark = PerformanceBenchmark()
        tester = ProtocolComplianceTester(conn)
        tracker = CoverageTracker()
        
        # Test connection
        with benchmark.measure("connection_test"):
            await conn.connect()
            tracker.mark_covered("connect")
        
        # Test subscription
        with benchmark.measure("subscription_test"):
            query_id = conn.subscribe([
                "SELECT * FROM messages WHERE room_id = 'main'",
                "SELECT * FROM users WHERE online = true"
            ])
            tracker.mark_covered("subscribe")
        
        # Test data operations
        with benchmark.measure("data_operations"):
            # Add test data
            for i in range(10):
                conn.add_table_row("messages", {
                    "id": i,
                    "room_id": "main",
                    "user_id": i % 3,
                    "content": f"Test message {i}"
                })
        
        # Test reducer
        conn.register_reducer("send_message", 
                            lambda room, msg: {"sent": True})
        
        with benchmark.measure("reducer_test"):
            request_id = conn.call_reducer("send_message", "main", "Hello!")
            tracker.mark_covered("call_reducer")
        
        # Disconnect
        with benchmark.measure("disconnect_test"):
            await conn.disconnect()
            tracker.mark_covered("disconnect")
        
        # Generate reports
        print("\nPerformance Summary:")
        print("-" * 40)
        for op, times in benchmark.results.items():
            avg_time = sum(times) / len(times) * 1000
            print(f"{op}: {avg_time:.2f}ms")
        
        print(f"\nCoverage: {len(tracker.operations_covered)}"
              f"/{len(tracker.operations_total)} operations")
        
        # Protocol compliance
        compliance_passed = await tester.test_connection_lifecycle()
        print(f"\nProtocol Compliance: "
              f"{'PASSED' if compliance_passed else 'FAILED'}")


# Pytest examples

@pytest.mark.asyncio
@spacetimedb_test(requires_connection=True)
async def test_example_with_fixtures(
    mock_connection,
    test_data,
    benchmark,
    coverage_tracker
):
    """Example pytest test using fixtures."""
    # Generate test data
    users = test_data.generate_bulk_data("users", 50)
    
    # Connect and benchmark
    with benchmark.measure("setup"):
        await mock_connection.connect()
        coverage_tracker.mark_covered("connect")
    
    # Add data
    with benchmark.measure("bulk_insert"):
        for user in users:
            mock_connection.add_table_row("users", user)
    
    # Subscribe
    query_id = mock_connection.subscribe(["SELECT * FROM users"])
    coverage_tracker.mark_covered("subscribe")
    
    # Assertions
    assert len(mock_connection.tables["users"]) == 50
    assert query_id is not None
    
    # Cleanup
    await mock_connection.disconnect()
    coverage_tracker.mark_covered("disconnect")


def main():
    """Run all testing infrastructure examples."""
    import time
    
    print("SpacetimeDB Testing Infrastructure Examples")
    print("==========================================")
    
    example = TestingInfrastructureExample()
    
    # Run all examples
    asyncio.run(example.example_1_mock_connection())
    asyncio.run(example.example_2_websocket_mocking())
    example.example_3_test_data_generation()
    asyncio.run(example.example_4_protocol_compliance())
    asyncio.run(example.example_5_performance_benchmarking())
    asyncio.run(example.example_6_test_database_fixture())
    example.example_7_test_isolation()
    example.example_8_coverage_tracking()
    example.example_9_test_decorators()
    asyncio.run(example.example_10_full_test_scenario())
    
    print("\n✅ Testing infrastructure examples complete!")
    print("\nKey Features Demonstrated:")
    print("- Mock connections for unit testing")
    print("- WebSocket adapter mocking")
    print("- Test data generation")
    print("- Protocol compliance testing")
    print("- Performance benchmarking")
    print("- Test database fixtures")
    print("- Test isolation")
    print("- Coverage tracking")
    print("- Test decorators")
    print("- Integration with pytest")


if __name__ == "__main__":
    main() 