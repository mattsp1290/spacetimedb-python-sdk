"""
Testing infrastructure for SpacetimeDB Python SDK.

Provides comprehensive testing utilities:
- Mock connections and WebSocket adapters
- Test data generators
- Protocol compliance testing
- Performance benchmarking
- Integration test support
"""

import asyncio
import json
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from io import BytesIO
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union,
    Type, TypeVar, Generic, Protocol, runtime_checkable
)
from unittest.mock import Mock, MagicMock, AsyncMock

from .connection_id import ConnectionState, EnhancedConnectionId, EnhancedIdentity
from .protocol import Identity, generate_request_id
from .query_id import QueryId
from .bsatn import BsatnWriter, BsatnReader
from .websocket_client import ConnectionState as WebSocketState


T = TypeVar('T')
F = TypeVar('F', bound=Callable)


class MessageType(Enum):
    """Types of messages in the SpacetimeDB protocol."""
    INITIAL_SUBSCRIPTION = auto()
    TRANSACTION_UPDATE = auto()
    IDENTITY_TOKEN = auto()
    SUBSCRIPTION_UPDATE = auto()
    QUERY_UPDATE = auto()
    REDUCER_CALL_RESPONSE = auto()
    ONE_OFF_QUERY_RESPONSE = auto()
    ERROR = auto()


@dataclass
class MockMessage:
    """Mock protocol message for testing."""
    type: MessageType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps({
            "type": self.type.name,
            "data": self.data,
            "timestamp": self.timestamp
        })
    
    def to_binary(self) -> bytes:
        """Convert to binary format."""
        buffer = BytesIO()
        writer = BsatnWriter(buffer)
        writer.write_u8(self.type.value)
        # Simplified binary encoding
        json_data = json.dumps(self.data).encode('utf-8')
        writer.write_bytes(json_data)
        return buffer.getvalue()


class MockWebSocketAdapter:
    """
    Mock WebSocket adapter for testing.
    
    Simulates WebSocket behavior without network connection.
    """
    
    def __init__(self, auto_connect: bool = True):
        self.auto_connect = auto_connect
        self.connected = False
        self.messages_sent: List[Tuple[Union[str, bytes], float]] = []
        self.messages_to_receive: List[MockMessage] = []
        self.receive_delay = 0.0
        self.send_callbacks: List[Callable] = []
        self.receive_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        self.close_callbacks: List[Callable] = []
        self._closed = False
    
    async def connect(self, url: str, headers: Optional[Dict[str, str]] = None):
        """Simulate connection."""
        if self._closed:
            raise RuntimeError("WebSocket is closed")
        
        if self.auto_connect:
            await asyncio.sleep(0.01)  # Simulate connection delay
            self.connected = True
            return self
        else:
            raise ConnectionError("Mock connection failed")
    
    async def send(self, data: Union[str, bytes]):
        """Simulate sending data."""
        if not self.connected:
            raise RuntimeError("Not connected")
        
        self.messages_sent.append((data, time.time()))
        
        # Trigger send callbacks
        for callback in self.send_callbacks:
            callback(data)
    
    async def receive(self) -> Union[str, bytes]:
        """Simulate receiving data."""
        if not self.connected:
            raise RuntimeError("Not connected")
        
        if self.receive_delay > 0:
            await asyncio.sleep(self.receive_delay)
        
        if self.messages_to_receive:
            msg = self.messages_to_receive.pop(0)
            
            # Trigger receive callbacks
            for callback in self.receive_callbacks:
                callback(msg)
            
            # Return appropriate format
            if isinstance(msg.data.get("binary"), bool) and msg.data["binary"]:
                return msg.to_binary()
            else:
                return msg.to_json()
        
        # Wait indefinitely if no messages
        await asyncio.sleep(1000)
    
    async def close(self):
        """Simulate closing connection."""
        self.connected = False
        self._closed = True
        
        # Trigger close callbacks
        for callback in self.close_callbacks:
            callback()
    
    def add_message(self, message: MockMessage):
        """Add a message to be received."""
        self.messages_to_receive.append(message)
    
    def on_send(self, callback: Callable):
        """Register send callback."""
        self.send_callbacks.append(callback)
    
    def on_receive(self, callback: Callable):
        """Register receive callback."""
        self.receive_callbacks.append(callback)
    
    def on_error(self, callback: Callable):
        """Register error callback."""
        self.error_callbacks.append(callback)
    
    def on_close(self, callback: Callable):
        """Register close callback."""
        self.close_callbacks.append(callback)
    
    def simulate_error(self, error: Exception):
        """Simulate an error."""
        for callback in self.error_callbacks:
            callback(error)


class MockSpacetimeDBConnection:
    """
    Mock SpacetimeDB connection for testing.
    
    Provides full connection simulation without server.
    """
    
    def __init__(self, module_name: str = "test_module"):
        self.module_name = module_name
        self.websocket = MockWebSocketAdapter()
        self.identity = EnhancedIdentity(bytes(range(32)))
        self.connection_id = EnhancedConnectionId(uuid.uuid4().bytes)
        self.token = f"mock_token_{uuid.uuid4().hex[:8]}"
        self.state = ConnectionState.DISCONNECTED
        
        # Storage
        self.tables: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.reducers: Dict[str, Callable] = {}
        self.subscriptions: Dict[QueryId, str] = {}
        
        # Callbacks
        self.on_connect_callbacks: List[Callable] = []
        self.on_disconnect_callbacks: List[Callable] = []
        self.on_error_callbacks: List[Callable] = []
        
        # Metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.reducers_called = 0
        self.subscriptions_created = 0
    
    async def connect(self) -> 'MockSpacetimeDBConnection':
        """Simulate connection."""
        self.state = ConnectionState.CONNECTING
        
        # Simulate connection process
        await self.websocket.connect(f"ws://mock/{self.module_name}")
        
        # Send identity message
        self.websocket.add_message(MockMessage(
            MessageType.IDENTITY_TOKEN,
            {
                "identity": self.identity.to_hex(),
                "connection_id": self.connection_id.to_hex(),
                "token": self.token
            }
        ))
        
        self.state = ConnectionState.CONNECTED
        
        # Trigger callbacks
        for callback in self.on_connect_callbacks:
            callback()
        
        return self
    
    async def disconnect(self):
        """Simulate disconnection."""
        self.state = ConnectionState.DISCONNECTING
        await self.websocket.close()
        self.state = ConnectionState.DISCONNECTED
        
        # Trigger callbacks
        for callback in self.on_disconnect_callbacks:
            callback()
    
    def subscribe(self, queries: List[str]) -> QueryId:
        """Simulate subscription."""
        query_id = QueryId.generate()
        
        # Store subscription
        for query in queries:
            self.subscriptions[query_id] = query
        
        # Simulate subscription response
        self.websocket.add_message(MockMessage(
            MessageType.SUBSCRIPTION_UPDATE,
            {
                "query_id": query_id.data.hex(),
                "tables": list(self._extract_tables_from_queries(queries))
            }
        ))
        
        self.subscriptions_created += 1
        return query_id
    
    def call_reducer(self, reducer_name: str, *args) -> str:
        """Simulate reducer call."""
        request_id = generate_request_id()
        
        # Check if reducer exists
        if reducer_name in self.reducers:
            # Simulate calling reducer
            result = self.reducers[reducer_name](*args)
            
            # Send response
            self.websocket.add_message(MockMessage(
                MessageType.REDUCER_CALL_RESPONSE,
                {
                    "request_id": request_id,
                    "reducer": reducer_name,
                    "result": result,
                    "energy_used": 1000
                }
            ))
        else:
            # Send error
            self.websocket.add_message(MockMessage(
                MessageType.ERROR,
                {
                    "request_id": request_id,
                    "error": f"Unknown reducer: {reducer_name}"
                }
            ))
        
        self.reducers_called += 1
        return request_id
    
    def add_table_row(self, table_name: str, row: Dict[str, Any]):
        """Add a row to a mock table."""
        self.tables[table_name].append(row)
        
        # Simulate transaction update
        self.websocket.add_message(MockMessage(
            MessageType.TRANSACTION_UPDATE,
            {
                "tables": {
                    table_name: {
                        "inserts": [row]
                    }
                }
            }
        ))
    
    def register_reducer(self, name: str, handler: Callable):
        """Register a mock reducer."""
        self.reducers[name] = handler
    
    def on_connect(self, callback: Callable):
        """Register connect callback."""
        self.on_connect_callbacks.append(callback)
    
    def on_disconnect(self, callback: Callable):
        """Register disconnect callback."""
        self.on_disconnect_callbacks.append(callback)
    
    def on_error(self, callback: Callable):
        """Register error callback."""
        self.on_error_callbacks.append(callback)
    
    def _extract_tables_from_queries(self, queries: List[str]) -> Set[str]:
        """Extract table names from SQL queries."""
        tables = set()
        for query in queries:
            # Simple extraction - real implementation would use SQL parser
            if "FROM" in query.upper():
                parts = query.upper().split("FROM")
                if len(parts) > 1:
                    table_part = parts[1].strip().split()[0]
                    tables.add(table_part.lower())
        return tables


@dataclass
class TestDataGenerator:
    """Generate test data for SpacetimeDB tables."""
    
    @staticmethod
    def generate_identity() -> Identity:
        """Generate a random identity."""
        return Identity(uuid.uuid4().bytes + uuid.uuid4().bytes)
    
    @staticmethod
    def generate_user(user_id: Optional[int] = None) -> Dict[str, Any]:
        """Generate a test user."""
        if user_id is None:
            user_id = uuid.uuid4().int & 0xFFFFFFFF
        
        return {
            "id": user_id,
            "username": f"user_{user_id}",
            "email": f"user_{user_id}@example.com",
            "created_at": int(time.time() * 1_000_000),
            "active": True
        }
    
    @staticmethod
    def generate_message(
        message_id: Optional[int] = None,
        user_id: Optional[int] = None,
        content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a test message."""
        if message_id is None:
            message_id = uuid.uuid4().int & 0xFFFFFFFF
        if user_id is None:
            user_id = uuid.uuid4().int & 0xFFFFFFFF
        if content is None:
            content = f"Test message {message_id}"
        
        return {
            "id": message_id,
            "user_id": user_id,
            "content": content,
            "timestamp": int(time.time() * 1_000_000),
            "edited": False
        }
    
    @staticmethod
    def generate_bulk_data(
        table_name: str,
        count: int,
        generator_func: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Generate bulk test data."""
        if generator_func is None:
            # Default generators
            if table_name == "users":
                generator_func = TestDataGenerator.generate_user
            elif table_name == "messages":
                generator_func = TestDataGenerator.generate_message
            else:
                # Generic generator
                generator_func = lambda i: {"id": i, "data": f"row_{i}"}
        
        return [generator_func(i) for i in range(count)]


class ProtocolComplianceTester:
    """Test protocol compliance for SpacetimeDB connections."""
    
    def __init__(self, connection: Any):
        self.connection = connection
        self.test_results: Dict[str, bool] = {}
        self.test_messages: Dict[str, str] = {}
    
    async def test_connection_lifecycle(self) -> bool:
        """Test connection lifecycle compliance."""
        try:
            # Test connection
            await self.connection.connect()
            self.test_results["connect"] = True
            
            # Check identity
            if hasattr(self.connection, 'identity'):
                self.test_results["identity"] = self.connection.identity is not None
            else:
                self.test_results["identity"] = False
                self.test_messages["identity"] = "No identity attribute"
            
            # Test disconnection
            await self.connection.disconnect()
            self.test_results["disconnect"] = True
            
            return all(self.test_results.values())
            
        except Exception as e:
            self.test_messages["lifecycle"] = str(e)
            return False
    
    async def test_subscription_protocol(self) -> bool:
        """Test subscription protocol compliance."""
        try:
            await self.connection.connect()
            
            # Test subscription
            query_id = self.connection.subscribe(["SELECT * FROM test"])
            self.test_results["subscribe"] = query_id is not None
            
            # Test query ID format
            if hasattr(query_id, 'to_hex'):
                hex_id = query_id.to_hex()
                self.test_results["query_id_format"] = len(hex_id) == 32
            else:
                self.test_results["query_id_format"] = False
            
            await self.connection.disconnect()
            return all(self.test_results.values())
            
        except Exception as e:
            self.test_messages["subscription"] = str(e)
            return False
    
    async def test_reducer_protocol(self) -> bool:
        """Test reducer protocol compliance."""
        try:
            await self.connection.connect()
            
            # Test reducer call
            request_id = self.connection.call_reducer("test_reducer", "arg1", 123)
            self.test_results["reducer_call"] = request_id is not None
            
            # Test request ID format
            self.test_results["request_id_format"] = (
                isinstance(request_id, str) and len(request_id) > 0
            )
            
            await self.connection.disconnect()
            return all(self.test_results.values())
            
        except Exception as e:
            self.test_messages["reducer"] = str(e)
            return False
    
    def get_report(self) -> str:
        """Get compliance test report."""
        report = ["Protocol Compliance Test Report", "=" * 40]
        
        for test_name, passed in self.test_results.items():
            status = "PASS" if passed else "FAIL"
            report.append(f"{test_name}: {status}")
            
            if not passed and test_name in self.test_messages:
                report.append(f"  Error: {self.test_messages[test_name]}")
        
        total = len(self.test_results)
        passed = sum(1 for p in self.test_results.values() if p)
        report.append(f"\nTotal: {passed}/{total} tests passed")
        
        return "\n".join(report)


class PerformanceBenchmark:
    """Performance benchmarking for SpacetimeDB operations."""
    
    def __init__(self):
        self.results: Dict[str, List[float]] = defaultdict(list)
        self.operation_counts: Dict[str, int] = defaultdict(int)
    
    @contextmanager
    def measure(self, operation: str):
        """Context manager to measure operation time."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start_time
            self.results[operation].append(elapsed)
            self.operation_counts[operation] += 1
    
    async def benchmark_connection(self, connection: Any, iterations: int = 10):
        """Benchmark connection operations."""
        for _ in range(iterations):
            with self.measure("connect"):
                await connection.connect()
            
            with self.measure("disconnect"):
                await connection.disconnect()
    
    async def benchmark_subscriptions(
        self,
        connection: Any,
        queries: List[str],
        iterations: int = 100
    ):
        """Benchmark subscription operations."""
        await connection.connect()
        
        for _ in range(iterations):
            with self.measure("subscribe"):
                query_id = connection.subscribe(queries)
            
            # Optionally unsubscribe
            if hasattr(connection, 'unsubscribe'):
                with self.measure("unsubscribe"):
                    connection.unsubscribe(query_id)
        
        await connection.disconnect()
    
    async def benchmark_reducers(
        self,
        connection: Any,
        reducer_name: str,
        args: List[Any],
        iterations: int = 1000
    ):
        """Benchmark reducer calls."""
        await connection.connect()
        
        for _ in range(iterations):
            with self.measure("reducer_call"):
                connection.call_reducer(reducer_name, *args)
        
        await connection.disconnect()
    
    def get_report(self) -> str:
        """Get benchmark report."""
        report = ["Performance Benchmark Report", "=" * 40]
        
        for operation, times in self.results.items():
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                ops_per_sec = 1 / avg_time if avg_time > 0 else 0
                
                report.append(f"\n{operation}:")
                report.append(f"  Iterations: {len(times)}")
                report.append(f"  Average: {avg_time*1000:.3f} ms")
                report.append(f"  Min: {min_time*1000:.3f} ms")
                report.append(f"  Max: {max_time*1000:.3f} ms")
                report.append(f"  Ops/sec: {ops_per_sec:.2f}")
        
        return "\n".join(report)


# Pytest fixtures

def pytest_fixture(func: F) -> F:
    """Decorator to mark pytest fixtures (for documentation)."""
    return func


@pytest_fixture
def mock_connection():
    """Pytest fixture providing a mock SpacetimeDB connection."""
    return MockSpacetimeDBConnection()


@pytest_fixture
def mock_websocket():
    """Pytest fixture providing a mock WebSocket adapter."""
    return MockWebSocketAdapter()


@pytest_fixture
def test_data_generator():
    """Pytest fixture providing test data generator."""
    return TestDataGenerator()


@pytest_fixture
def protocol_tester():
    """Pytest fixture providing protocol compliance tester."""
    def _create_tester(connection):
        return ProtocolComplianceTester(connection)
    return _create_tester


@pytest_fixture
def performance_benchmark():
    """Pytest fixture providing performance benchmark."""
    return PerformanceBenchmark()


# Test decorators

def spacetimedb_test(
    requires_connection: bool = False,
    requires_wasm: bool = False,
    timeout: float = 30.0
):
    """
    Decorator for SpacetimeDB tests.
    
    Args:
        requires_connection: Test requires a connection
        requires_wasm: Test requires WASM module
        timeout: Test timeout in seconds
    """
    def decorator(func: F) -> F:
        # Add metadata
        func._spacetimedb_test = True
        func._requires_connection = requires_connection
        func._requires_wasm = requires_wasm
        func._timeout = timeout
        return func
    return decorator


def integration_test(func: F) -> F:
    """Mark test as integration test."""
    func._integration_test = True
    return func


def performance_test(func: F) -> F:
    """Mark test as performance test."""
    func._performance_test = True
    return func


def stress_test(
    connections: int = 10,
    duration: float = 60.0
):
    """Mark test as stress test with parameters."""
    def decorator(func: F) -> F:
        func._stress_test = True
        func._stress_connections = connections
        func._stress_duration = duration
        return func
    return decorator 