#!/usr/bin/env python3
"""
Mock SpaceTimeDB server for comprehensive testing.
Simulates v1.1.2 protocol behavior with configurable responses and error injection.
"""

import asyncio
import websockets
import json
import base64
import threading
import time
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import struct
import uuid

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """SpaceTimeDB message types."""
    IDENTITY_TOKEN = "identity_token"
    INITIAL_SUBSCRIPTION = "initial_subscription"
    TRANSACTION_UPDATE = "transaction_update"
    SUBSCRIPTION_UPDATE = "subscription_update"
    QUERY_RESULT = "query_result"
    REDUCER_RESULT = "reducer_result"
    ERROR = "error"


@dataclass
class MockServerConfig:
    """Configuration for mock server behavior."""
    host: str = "localhost"
    port: int = 3001
    protocol: str = "v1.json.spacetimedb"
    binary_protocol: str = "v1.bsatn.spacetimedb"
    
    # Behavior configuration
    auth_required: bool = False
    valid_tokens: List[str] = field(default_factory=lambda: ["valid_token_123"])
    database_published: bool = True
    inject_errors: bool = False
    error_rate: float = 0.0
    
    # Response delays (for testing timeouts)
    connection_delay: float = 0.0
    message_delay: float = 0.0
    
    # Connection limits
    max_connections: int = 100
    max_message_size: int = 1024 * 1024  # 1MB
    
    # Feature flags
    compression_enabled: bool = True
    support_binary_protocol: bool = True
    
    # Test scenarios
    scenario: Optional[str] = None


class MockDatabase:
    """Mock database state."""
    
    def __init__(self, name: str):
        self.name = name
        self.tables: Dict[str, List[Dict]] = {}
        self.reducers: Dict[str, Callable] = {}
        self.subscribers: Dict[str, set] = {}
        self.published = True
        
    def add_table(self, table_name: str, initial_data: List[Dict] = None):
        """Add a table to the mock database."""
        self.tables[table_name] = initial_data or []
        
    def add_reducer(self, reducer_name: str, handler: Callable):
        """Add a reducer to the mock database."""
        self.reducers[reducer_name] = handler
        
    def insert(self, table_name: str, row: Dict):
        """Insert a row into a table."""
        if table_name not in self.tables:
            self.tables[table_name] = []
        self.tables[table_name].append(row)
        
    def query(self, table_name: str, filter_fn: Optional[Callable] = None) -> List[Dict]:
        """Query a table with optional filter."""
        if table_name not in self.tables:
            return []
        
        data = self.tables[table_name]
        if filter_fn:
            data = [row for row in data if filter_fn(row)]
        
        return data


class MockSpaceTimeDBServer:
    """Mock SpaceTimeDB server implementation."""
    
    def __init__(self, config: MockServerConfig = None):
        self.config = config or MockServerConfig()
        self.databases: Dict[str, MockDatabase] = {}
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.server = None
        self.server_thread = None
        self.running = False
        self._connection_counter = 0
        
        # Statistics
        self.stats = {
            "connections_accepted": 0,
            "connections_rejected": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors_injected": 0
        }
        
        # Set up default databases
        self._setup_default_databases()
        
    def _setup_default_databases(self):
        """Set up default test databases."""
        # Create a test database
        test_db = MockDatabase("test_db")
        test_db.add_table("users", [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"}
        ])
        test_db.add_table("messages", [])
        
        # Add a simple reducer
        def send_message(caller_identity: str, recipient: str, content: str):
            return {
                "sender": caller_identity,
                "recipient": recipient,
                "content": content,
                "timestamp": time.time()
            }
        
        test_db.add_reducer("send_message", send_message)
        self.databases["test_db"] = test_db
        
        # Create an unpublished database
        unpublished_db = MockDatabase("unpublished_db")
        unpublished_db.published = False
        self.databases["unpublished_db"] = unpublished_db
        
    def add_database(self, name: str, database: MockDatabase):
        """Add a mock database to the server."""
        self.databases[name] = database
        
    async def handle_connection(self, websocket, path: str):
        """Handle a WebSocket connection."""
        connection_id = f"conn_{self._connection_counter}"
        self._connection_counter += 1
        
        try:
            # Inject connection delay if configured
            if self.config.connection_delay > 0:
                await asyncio.sleep(self.config.connection_delay)
            
            # Parse the path
            if not path.startswith("/v1/database/"):
                await websocket.close(code=404, reason="Invalid path")
                self.stats["connections_rejected"] += 1
                return
                
            # Extract database name
            path_parts = path.split("/")
            if len(path_parts) < 5 or path_parts[4] != "subscribe":
                await websocket.close(code=404, reason="Invalid endpoint")
                self.stats["connections_rejected"] += 1
                return
                
            db_name = path_parts[3]
            
            # Check if database exists and is published
            if db_name not in self.databases:
                await websocket.close(code=404, reason="Database not found")
                self.stats["connections_rejected"] += 1
                return
                
            db = self.databases[db_name]
            if not db.published and not self.config.database_published:
                await websocket.close(code=404, reason="Database not published")
                self.stats["connections_rejected"] += 1
                return
            
            # Check authentication if required
            auth_header = None
            for header in websocket.request_headers:
                if header[0].lower() == "authorization":
                    auth_header = header[1]
                    break
                    
            identity = None
            if self.config.auth_required:
                if not auth_header or not self._validate_auth(auth_header):
                    await websocket.close(code=401, reason="Unauthorized")
                    self.stats["connections_rejected"] += 1
                    return
                identity = self._extract_identity_from_auth(auth_header)
            else:
                # Generate anonymous identity
                identity = self._generate_identity()
                
            # Check subprotocol
            if websocket.subprotocol not in [self.config.protocol, self.config.binary_protocol]:
                await websocket.close(code=400, reason="Unsupported protocol")
                self.stats["connections_rejected"] += 1
                return
                
            # Connection accepted
            self.stats["connections_accepted"] += 1
            
            # Store connection info
            self.connections[connection_id] = {
                "websocket": websocket,
                "database": db_name,
                "identity": identity,
                "connection_id": connection_id,
                "protocol": websocket.subprotocol,
                "subscriptions": set()
            }
            
            # Send identity token
            await self._send_identity_token(websocket, identity, connection_id)
            
            # Send initial subscription data
            await self._send_initial_subscription(websocket, db)
            
            # Handle messages
            async for message in websocket:
                await self._handle_message(connection_id, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection {connection_id} closed")
        except Exception as e:
            logger.error(f"Error handling connection {connection_id}: {e}")
        finally:
            # Clean up connection
            if connection_id in self.connections:
                del self.connections[connection_id]
                
    def _validate_auth(self, auth_header: str) -> bool:
        """Validate authorization header."""
        if not auth_header.startswith("Basic "):
            return False
            
        try:
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode('utf-8')
            
            if not decoded.startswith("token:"):
                return False
                
            token = decoded[6:]
            return token in self.config.valid_tokens
            
        except Exception:
            return False
            
    def _extract_identity_from_auth(self, auth_header: str) -> str:
        """Extract identity from auth header."""
        # In a real system, this would look up the token
        # For testing, we'll generate a deterministic identity
        return "a" * 64
        
    def _generate_identity(self) -> str:
        """Generate an anonymous identity."""
        return uuid.uuid4().hex + uuid.uuid4().hex
        
    async def _send_identity_token(self, websocket, identity: str, connection_id: str):
        """Send identity token message."""
        if self._should_inject_error():
            await self._inject_error(websocket, "Identity token error")
            return
            
        # Inject message delay if configured
        if self.config.message_delay > 0:
            await asyncio.sleep(self.config.message_delay)
            
        message = {
            "type": MessageType.IDENTITY_TOKEN.value,
            "identity": identity,
            "token": f"test_token_{int(time.time())}",
            "connection_id": connection_id[5:]  # Remove "conn_" prefix
        }
        
        await self._send_message(websocket, message)
        
    async def _send_initial_subscription(self, websocket, database: MockDatabase):
        """Send initial subscription data."""
        if self._should_inject_error():
            await self._inject_error(websocket, "Initial subscription error")
            return
            
        # Send table data
        for table_name, rows in database.tables.items():
            message = {
                "type": MessageType.INITIAL_SUBSCRIPTION.value,
                "table": table_name,
                "rows": rows
            }
            await self._send_message(websocket, message)
            
    async def _handle_message(self, connection_id: str, message: Union[str, bytes]):
        """Handle incoming message from client."""
        self.stats["messages_received"] += 1
        
        if self._should_inject_error():
            conn = self.connections.get(connection_id)
            if conn:
                await self._inject_error(conn["websocket"], "Message handling error")
            return
            
        try:
            # Parse message based on protocol
            conn = self.connections[connection_id]
            if conn["protocol"] == self.config.binary_protocol:
                # Handle binary protocol (simplified)
                data = self._parse_binary_message(message)
            else:
                # Handle JSON protocol
                data = json.loads(message)
                
            message_type = data.get("type")
            
            if message_type == "subscribe":
                await self._handle_subscribe(connection_id, data)
            elif message_type == "unsubscribe":
                await self._handle_unsubscribe(connection_id, data)
            elif message_type == "query":
                await self._handle_query(connection_id, data)
            elif message_type == "reducer":
                await self._handle_reducer(connection_id, data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            conn = self.connections.get(connection_id)
            if conn:
                await self._send_error(conn["websocket"], str(e))
                
    def _parse_binary_message(self, message: bytes) -> Dict:
        """Parse binary protocol message (simplified)."""
        # This is a simplified parser for testing
        # Real implementation would use proper BSATN decoding
        try:
            # Assume first byte is message type
            msg_type = message[0]
            # Rest is JSON for simplicity in tests
            data = json.loads(message[1:].decode('utf-8'))
            data["type"] = ["subscribe", "unsubscribe", "query", "reducer"][msg_type % 4]
            return data
        except:
            return {"type": "unknown"}
            
    async def _handle_subscribe(self, connection_id: str, data: Dict):
        """Handle subscription request."""
        conn = self.connections[connection_id]
        table = data.get("table")
        
        if table:
            conn["subscriptions"].add(table)
            
            # Send current table data
            db = self.databases[conn["database"]]
            if table in db.tables:
                message = {
                    "type": MessageType.SUBSCRIPTION_UPDATE.value,
                    "table": table,
                    "rows": db.tables[table]
                }
                await self._send_message(conn["websocket"], message)
                
    async def _handle_unsubscribe(self, connection_id: str, data: Dict):
        """Handle unsubscription request."""
        conn = self.connections[connection_id]
        table = data.get("table")
        
        if table and table in conn["subscriptions"]:
            conn["subscriptions"].remove(table)
            
    async def _handle_query(self, connection_id: str, data: Dict):
        """Handle query request."""
        conn = self.connections[connection_id]
        db = self.databases[conn["database"]]
        
        query_id = data.get("query_id", str(uuid.uuid4()))
        table = data.get("table")
        
        if table in db.tables:
            rows = db.query(table)
            message = {
                "type": MessageType.QUERY_RESULT.value,
                "query_id": query_id,
                "table": table,
                "rows": rows
            }
        else:
            message = {
                "type": MessageType.ERROR.value,
                "query_id": query_id,
                "error": f"Table '{table}' not found"
            }
            
        await self._send_message(conn["websocket"], message)
        
    async def _handle_reducer(self, connection_id: str, data: Dict):
        """Handle reducer call."""
        conn = self.connections[connection_id]
        db = self.databases[conn["database"]]
        
        reducer_name = data.get("reducer")
        args = data.get("args", {})
        request_id = data.get("request_id", str(uuid.uuid4()))
        
        if reducer_name in db.reducers:
            try:
                # Call reducer with identity
                result = db.reducers[reducer_name](conn["identity"], **args)
                
                message = {
                    "type": MessageType.REDUCER_RESULT.value,
                    "request_id": request_id,
                    "reducer": reducer_name,
                    "result": result
                }
            except Exception as e:
                message = {
                    "type": MessageType.ERROR.value,
                    "request_id": request_id,
                    "error": str(e)
                }
        else:
            message = {
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "error": f"Reducer '{reducer_name}' not found"
            }
            
        await self._send_message(conn["websocket"], message)
        
    async def _send_message(self, websocket, message: Dict):
        """Send a message to the client."""
        self.stats["messages_sent"] += 1
        
        # Check if binary protocol
        if hasattr(websocket, 'subprotocol') and websocket.subprotocol == self.config.binary_protocol:
            # Send as binary (simplified - just JSON with a type byte)
            msg_bytes = json.dumps(message).encode('utf-8')
            type_byte = bytes([hash(message.get("type", "")) % 256])
            await websocket.send(type_byte + msg_bytes)
        else:
            # Send as JSON
            await websocket.send(json.dumps(message))
            
    async def _send_error(self, websocket, error: str):
        """Send an error message."""
        message = {
            "type": MessageType.ERROR.value,
            "error": error,
            "timestamp": time.time()
        }
        await self._send_message(websocket, message)
        
    def _should_inject_error(self) -> bool:
        """Determine if an error should be injected."""
        if not self.config.inject_errors:
            return False
            
        import random
        should_inject = random.random() < self.config.error_rate
        if should_inject:
            self.stats["errors_injected"] += 1
        return should_inject
        
    async def _inject_error(self, websocket, error_msg: str):
        """Inject an error for testing."""
        await self._send_error(websocket, f"Injected error: {error_msg}")
        
    async def _run_server(self):
        """Run the WebSocket server."""
        async with websockets.serve(
            self.handle_connection,
            self.config.host,
            self.config.port,
            subprotocols=[self.config.protocol, self.config.binary_protocol]
        ) as server:
            self.server = server
            logger.info(f"Mock server started on {self.config.host}:{self.config.port}")
            
            # Keep server running
            while self.running:
                await asyncio.sleep(0.1)
                
    def start(self):
        """Start the mock server in a background thread."""
        if self.running:
            return
            
        self.running = True
        
        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_server())
            
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait for server to start
        time.sleep(0.5)
        
    def stop(self):
        """Stop the mock server."""
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=2)
            
    def reset_stats(self):
        """Reset server statistics."""
        self.stats = {
            "connections_accepted": 0,
            "connections_rejected": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors_injected": 0
        }
        
    def configure_scenario(self, scenario: str):
        """Configure a specific test scenario."""
        scenarios = {
            "normal": MockServerConfig(),
            "auth_required": MockServerConfig(auth_required=True),
            "unpublished": MockServerConfig(database_published=False),
            "slow_connection": MockServerConfig(connection_delay=2.0),
            "slow_messages": MockServerConfig(message_delay=0.5),
            "error_prone": MockServerConfig(inject_errors=True, error_rate=0.3),
            "binary_only": MockServerConfig(support_binary_protocol=True),
        }
        
        if scenario in scenarios:
            self.config = scenarios[scenario]
            self.config.scenario = scenario
        else:
            raise ValueError(f"Unknown scenario: {scenario}")


# Convenience functions for testing
def create_test_server(scenario: str = "normal", port: int = 3001) -> MockSpaceTimeDBServer:
    """Create a test server with a specific scenario."""
    server = MockSpaceTimeDBServer()
    server.config.port = port
    server.configure_scenario(scenario)
    return server


def with_mock_server(scenario: str = "normal", port: int = 3001):
    """Decorator to run a test with a mock server."""
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            server = create_test_server(scenario, port)
            server.start()
            try:
                # Pass server URL to test
                kwargs['server_url'] = f"localhost:{port}"
                return test_func(*args, **kwargs)
            finally:
                server.stop()
        return wrapper
    return decorator


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("Starting mock SpaceTimeDB server...")
    server = create_test_server("normal")
    server.start()
    
    print(f"Server running on localhost:{server.config.port}")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
            print(f"Stats: {server.stats}")
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop()
