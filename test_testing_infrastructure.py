"""
Test the testing infrastructure for SpacetimeDB Python SDK.

Demonstrates usage of:
- Mock connections and adapters
- Test data generators
- Protocol compliance testing
- Performance benchmarking
- Test fixtures
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from spacetimedb_sdk.testing import (
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
    stress_test
)
from spacetimedb_sdk.test_fixtures import (
    TestDatabase,
    TestIsolation,
    CoverageTracker,
    TestResultAggregator
)


class TestMockWebSocketAdapter:
    """Test the mock WebSocket adapter."""
    
    def test_mock_websocket_creation(self):
        """Test creating a mock WebSocket."""
        ws = MockWebSocketAdapter()
        assert ws.auto_connect is True
        assert ws.connected is False
        assert len(ws.messages_sent) == 0
        assert len(ws.messages_to_receive) == 0
    
    async def test_mock_websocket_connect(self):
        """Test connecting mock WebSocket."""
        ws = MockWebSocketAdapter()
        
        # Test successful connection
        await ws.connect("ws://test/module")
        assert ws.connected is True
        
        # Test failed connection
        ws2 = MockWebSocketAdapter(auto_connect=False)
        with pytest.raises(ConnectionError):
            await ws2.connect("ws://test/module")
    
    async def test_mock_websocket_send_receive(self):
        """Test sending and receiving messages."""
        ws = MockWebSocketAdapter()
        await ws.connect("ws://test/module")
        
        # Test sending
        await ws.send("test message")
        assert len(ws.messages_sent) == 1
        assert ws.messages_sent[0][0] == "test message"
        
        # Test receiving
        msg = MockMessage(
            MessageType.IDENTITY_TOKEN,
            {"identity": "test_id", "token": "test_token"}
        )
        ws.add_message(msg)
        
        received = await asyncio.wait_for(ws.receive(), timeout=1.0)
        assert isinstance(received, str)
        assert "IDENTITY_TOKEN" in received
    
    def test_mock_websocket_callbacks(self):
        """Test WebSocket callbacks."""
        ws = MockWebSocketAdapter()
        
        # Track callbacks
        send_called = []
        receive_called = []
        error_called = []
        close_called = []
        
        ws.on_send(lambda data: send_called.append(data))
        ws.on_receive(lambda msg: receive_called.append(msg))
        ws.on_error(lambda err: error_called.append(err))
        ws.on_close(lambda: close_called.append(True))
        
        # Test callbacks
        asyncio.run(ws.send("test"))
        assert len(send_called) == 1
        
        ws.simulate_error(RuntimeError("test error"))
        assert len(error_called) == 1


class TestMockSpacetimeDBConnection:
    """Test the mock SpacetimeDB connection."""
    
    async def test_connection_lifecycle(self):
        """Test connection lifecycle."""
        conn = MockSpacetimeDBConnection("test_module")
        
        # Test initial state
        assert conn.module_name == "test_module"
        assert conn.state.name == "DISCONNECTED"
        
        # Test connection
        await conn.connect()
        assert conn.state.name == "CONNECTED"
        assert conn.identity is not None
        assert conn.connection_id is not None
        assert conn.token is not None
        
        # Test disconnection
        await conn.disconnect()
        assert conn.state.name == "DISCONNECTED"
    
    def test_subscription_management(self):
        """Test subscription management."""
        conn = MockSpacetimeDBConnection()
        
        # Test subscription
        queries = ["SELECT * FROM users", "SELECT * FROM messages"]
        query_id = conn.subscribe(queries)
        
        assert query_id is not None
        assert conn.subscriptions_created == 1
        assert len(conn.subscriptions) == 2
    
    def test_reducer_calls(self):
        """Test reducer calls."""
        conn = MockSpacetimeDBConnection()
        
        # Register a mock reducer
        def mock_reducer(arg1, arg2):
            return {"result": arg1 + arg2}
        
        conn.register_reducer("add", mock_reducer)
        
        # Test reducer call
        request_id = conn.call_reducer("add", 5, 3)
        assert request_id is not None
        assert conn.reducers_called == 1
        
        # Test unknown reducer
        request_id2 = conn.call_reducer("unknown", "arg")
        assert request_id2 is not None
        assert conn.reducers_called == 2
    
    def test_table_operations(self):
        """Test table operations."""
        conn = MockSpacetimeDBConnection()
        
        # Add rows
        user1 = {"id": 1, "name": "Alice"}
        user2 = {"id": 2, "name": "Bob"}
        
        conn.add_table_row("users", user1)
        conn.add_table_row("users", user2)
        
        assert len(conn.tables["users"]) == 2
        assert conn.tables["users"][0] == user1
        assert conn.tables["users"][1] == user2
    
    async def test_connection_callbacks(self):
        """Test connection callbacks."""
        conn = MockSpacetimeDBConnection()
        
        connected = []
        disconnected = []
        errors = []
        
        conn.on_connect(lambda: connected.append(True))
        conn.on_disconnect(lambda: disconnected.append(True))
        conn.on_error(lambda e: errors.append(e))
        
        # Test callbacks
        await conn.connect()
        assert len(connected) == 1
        
        await conn.disconnect()
        assert len(disconnected) == 1


class TestDataGenerator:
    """Test the test data generator."""
    
    def test_generate_identity(self):
        """Test identity generation."""
        identity = TestDataGenerator.generate_identity()
        assert len(identity.data) == 32
        
        # Test uniqueness
        identity2 = TestDataGenerator.generate_identity()
        assert identity.data != identity2.data
    
    def test_generate_user(self):
        """Test user generation."""
        # Test with auto ID
        user = TestDataGenerator.generate_user()
        assert "id" in user
        assert "username" in user
        assert "email" in user
        assert "created_at" in user
        assert user["active"] is True
        
        # Test with specific ID
        user2 = TestDataGenerator.generate_user(user_id=42)
        assert user2["id"] == 42
        assert user2["username"] == "user_42"
        assert user2["email"] == "user_42@example.com"
    
    def test_generate_message(self):
        """Test message generation."""
        # Test with defaults
        msg = TestDataGenerator.generate_message()
        assert "id" in msg
        assert "user_id" in msg
        assert "content" in msg
        assert "timestamp" in msg
        assert msg["edited"] is False
        
        # Test with specific values
        msg2 = TestDataGenerator.generate_message(
            message_id=123,
            user_id=456,
            content="Hello, world!"
        )
        assert msg2["id"] == 123
        assert msg2["user_id"] == 456
        assert msg2["content"] == "Hello, world!"
    
    def test_generate_bulk_data(self):
        """Test bulk data generation."""
        # Test users
        users = TestDataGenerator.generate_bulk_data("users", 10)
        assert len(users) == 10
        for i, user in enumerate(users):
            assert user["id"] == i
        
        # Test messages
        messages = TestDataGenerator.generate_bulk_data("messages", 5)
        assert len(messages) == 5
        
        # Test custom generator
        def custom_gen(i):
            return {"index": i, "value": i * 2}
        
        custom_data = TestDataGenerator.generate_bulk_data(
            "custom", 3, custom_gen
        )
        assert len(custom_data) == 3
        assert custom_data[1]["value"] == 2


class TestProtocolComplianceTester:
    """Test the protocol compliance tester."""
    
    async def test_connection_lifecycle_compliance(self):
        """Test connection lifecycle compliance."""
        conn = MockSpacetimeDBConnection()
        tester = ProtocolComplianceTester(conn)
        
        # Run compliance test
        passed = await tester.test_connection_lifecycle()
        assert passed is True
        
        # Check results
        assert tester.test_results["connect"] is True
        assert tester.test_results["identity"] is True
        assert tester.test_results["disconnect"] is True
    
    async def test_subscription_protocol_compliance(self):
        """Test subscription protocol compliance."""
        conn = MockSpacetimeDBConnection()
        tester = ProtocolComplianceTester(conn)
        
        # Run compliance test
        passed = await tester.test_subscription_protocol()
        assert passed is True
        
        # Check results
        assert tester.test_results["subscribe"] is True
        assert tester.test_results["query_id_format"] is True
    
    async def test_reducer_protocol_compliance(self):
        """Test reducer protocol compliance."""
        conn = MockSpacetimeDBConnection()
        tester = ProtocolComplianceTester(conn)
        
        # Run compliance test
        passed = await tester.test_reducer_protocol()
        assert passed is True
        
        # Check results
        assert tester.test_results["reducer_call"] is True
        assert tester.test_results["request_id_format"] is True
    
    def test_compliance_report(self):
        """Test compliance report generation."""
        conn = MockSpacetimeDBConnection()
        tester = ProtocolComplianceTester(conn)
        
        # Add some test results
        tester.test_results["test1"] = True
        tester.test_results["test2"] = False
        tester.test_messages["test2"] = "Test failed"
        
        # Get report
        report = tester.get_report()
        assert "Protocol Compliance Test Report" in report
        assert "test1: PASS" in report
        assert "test2: FAIL" in report
        assert "Test failed" in report
        assert "1/2 tests passed" in report


class TestPerformanceBenchmark:
    """Test the performance benchmark."""
    
    def test_measure_context_manager(self):
        """Test measurement context manager."""
        benchmark = PerformanceBenchmark()
        
        import time
        with benchmark.measure("test_operation"):
            time.sleep(0.01)
        
        assert "test_operation" in benchmark.results
        assert len(benchmark.results["test_operation"]) == 1
        assert benchmark.results["test_operation"][0] >= 0.01
        assert benchmark.operation_counts["test_operation"] == 1
    
    async def test_benchmark_connection(self):
        """Test connection benchmarking."""
        conn = MockSpacetimeDBConnection()
        benchmark = PerformanceBenchmark()
        
        await benchmark.benchmark_connection(conn, iterations=3)
        
        assert "connect" in benchmark.results
        assert "disconnect" in benchmark.results
        assert len(benchmark.results["connect"]) == 3
        assert len(benchmark.results["disconnect"]) == 3
    
    async def test_benchmark_subscriptions(self):
        """Test subscription benchmarking."""
        conn = MockSpacetimeDBConnection()
        benchmark = PerformanceBenchmark()
        
        queries = ["SELECT * FROM test"]
        await benchmark.benchmark_subscriptions(conn, queries, iterations=5)
        
        assert "subscribe" in benchmark.results
        assert len(benchmark.results["subscribe"]) == 5
    
    async def test_benchmark_reducers(self):
        """Test reducer benchmarking."""
        conn = MockSpacetimeDBConnection()
        benchmark = PerformanceBenchmark()
        
        await benchmark.benchmark_reducers(
            conn, "test_reducer", ["arg1", "arg2"], iterations=10
        )
        
        assert "reducer_call" in benchmark.results
        assert len(benchmark.results["reducer_call"]) == 10
    
    def test_benchmark_report(self):
        """Test benchmark report generation."""
        benchmark = PerformanceBenchmark()
        
        # Add some measurements
        for i in range(5):
            with benchmark.measure("operation1"):
                pass
        
        for i in range(3):
            with benchmark.measure("operation2"):
                pass
        
        # Get report
        report = benchmark.get_report()
        assert "Performance Benchmark Report" in report
        assert "operation1" in report
        assert "operation2" in report
        assert "Iterations: 5" in report
        assert "Iterations: 3" in report
        assert "Ops/sec:" in report


class TestDecorators:
    """Test the test decorators."""
    
    def test_spacetimedb_test_decorator(self):
        """Test spacetimedb_test decorator."""
        @spacetimedb_test(requires_connection=True, timeout=60.0)
        def test_function():
            pass
        
        assert hasattr(test_function, '_spacetimedb_test')
        assert test_function._spacetimedb_test is True
        assert test_function._requires_connection is True
        assert test_function._timeout == 60.0
    
    def test_integration_test_decorator(self):
        """Test integration_test decorator."""
        @integration_test
        def test_function():
            pass
        
        assert hasattr(test_function, '_integration_test')
        assert test_function._integration_test is True
    
    def test_performance_test_decorator(self):
        """Test performance_test decorator."""
        @performance_test
        def test_function():
            pass
        
        assert hasattr(test_function, '_performance_test')
        assert test_function._performance_test is True
    
    def test_stress_test_decorator(self):
        """Test stress_test decorator."""
        @stress_test(connections=20, duration=120.0)
        def test_function():
            pass
        
        assert hasattr(test_function, '_stress_test')
        assert test_function._stress_test is True
        assert test_function._stress_connections == 20
        assert test_function._stress_duration == 120.0


class TestFixtures:
    """Test the test fixtures."""
    
    async def test_test_database(self):
        """Test TestDatabase fixture."""
        conn = MockSpacetimeDBConnection()
        db = TestDatabase(conn)
        
        # Test setup
        await db.setup()
        assert "users" in db.tables_created
        assert "messages" in db.tables_created
        
        # Test operations
        await db.insert_row("users", {"id": 1, "name": "Test"})
        data = await db.get_table_data("users")
        assert len(data) == 1
        
        await db.clear_table("users")
        data = await db.get_table_data("users")
        assert len(data) == 0
        
        # Test teardown
        await db.teardown()
    
    def test_test_isolation(self):
        """Test TestIsolation fixture."""
        import os
        
        # Save original env
        original_value = os.environ.get("TEST_VAR")
        
        with TestIsolation() as isolation:
            # Modify environment
            isolation.set_env("TEST_VAR", "test_value")
            assert os.environ["TEST_VAR"] == "test_value"
            
            # Create temp file
            temp_file = isolation.create_temp_file("test", "content")
            assert temp_file.exists()
            assert temp_file.read_text() == "content"
        
        # Check restoration
        if original_value is None:
            assert "TEST_VAR" not in os.environ
        else:
            assert os.environ["TEST_VAR"] == original_value
        
        # Check cleanup
        assert not temp_file.exists()
    
    def test_coverage_tracker(self):
        """Test CoverageTracker fixture."""
        tracker = CoverageTracker()
        
        # Track operations
        tracker.mark_covered("connect")
        tracker.mark_covered("subscribe")
        tracker.mark_covered("call_reducer")
        
        # Get report
        report = tracker.get_coverage_report()
        assert "SpacetimeDB Operation Coverage" in report
        assert "✓ connect" in report
        assert "✓ subscribe" in report
        assert "✓ call_reducer" in report
        assert "✗ disconnect" in report
        assert "Coverage: 25.0%" in report
    
    def test_result_aggregator(self):
        """Test TestResultAggregator fixture."""
        aggregator = TestResultAggregator()
        
        # Add results
        aggregator.add_result("test1", True, 0.5)
        aggregator.add_result("test2", False, 1.0)
        aggregator.add_result("test3", True, 0.3)
        
        # Get summary
        summary = aggregator.get_summary()
        assert summary["total_tests"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["pass_rate"] == pytest.approx(66.67, rel=0.01)
        assert summary["total_duration"] == 1.8
        assert summary["average_duration"] == 0.6


# Example integration tests using the infrastructure

@integration_test
@spacetimedb_test(requires_connection=True)
async def test_full_integration_example(mock_connection, test_data, benchmark):
    """Example integration test using multiple fixtures."""
    # Set up test data
    users = test_data.generate_bulk_data("users", 100)
    
    # Connect
    await mock_connection.connect()
    
    # Benchmark operations
    with benchmark.measure("bulk_insert"):
        for user in users:
            mock_connection.add_table_row("users", user)
    
    # Verify
    assert len(mock_connection.tables["users"]) == 100
    
    # Test subscription
    query_id = mock_connection.subscribe(["SELECT * FROM users"])
    assert query_id is not None
    
    # Disconnect
    await mock_connection.disconnect()


@performance_test
async def test_performance_example(benchmark):
    """Example performance test."""
    conn = MockSpacetimeDBConnection()
    
    # Benchmark different operations
    await benchmark.benchmark_connection(conn, iterations=10)
    await benchmark.benchmark_subscriptions(
        conn, 
        ["SELECT * FROM users", "SELECT * FROM messages"],
        iterations=50
    )
    
    # Get report
    report = benchmark.get_report()
    print("\n" + report)
    
    # Assert performance criteria
    connect_times = benchmark.results.get("connect", [])
    if connect_times:
        avg_connect = sum(connect_times) / len(connect_times)
        assert avg_connect < 0.1  # Should connect in < 100ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 