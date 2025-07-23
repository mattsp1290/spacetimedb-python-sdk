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
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

logger = logging.getLogger(__name__)


class MockHTTPHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for SpaceTimeDB health checks."""
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(f"[MOCK HTTP] {format % args}")
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "version": "1.1.2-mock",
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


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
    
    # Response delays (for testing timeouts) - optimized for fast testing
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
        self.http_server = None
        self.server_thread = None
        self.http_server_thread = None
        self.running = False
        self._connection_counter = 0
        self._connection_lock = threading.Lock()  # Add lock for thread safety
        
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
        test_db = MockDatabase("testdb")
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
        self.databases["testdb"] = test_db
        
        # Keep the old database name for backward compatibility
        # Legacy alias for backward compatibility
        # self.databases["test_db"] = test_db
        
        # Create an unpublished database
        unpublished_db = MockDatabase("unpublished")
        unpublished_db.published = False
        self.databases["unpublished"] = unpublished_db
        # Keep the old name for backward compatibility
        self.databases["unpublisheddb"] = unpublished_db
        
    def add_database(self, name: str, database: MockDatabase):
        """Add a mock database to the server."""
        self.databases[name] = database
        
    async def process_request(self, path, request_headers):
        """Process request during handshake to reject invalid requests."""
        logger.info(f"[MOCK SERVER] Processing WebSocket request: {path}")
        from websockets.datastructures import Headers
        from websockets.http11 import Response
        
        # Handle websocket path extraction - path might be a connection object
        if hasattr(path, 'path'):
            actual_path = path.path
        elif isinstance(path, str):
            actual_path = path
        else:
            # Default path for testing
            actual_path = "/v1/database/testdb/subscribe"
            
        logger.info(f"[MOCK SERVER] Extracted path: {actual_path}")
        
        # Enhanced validation scenarios
        if self.config.scenario == "validation_errors":
            # Force validation errors for testing
            if "malformed" in actual_path:
                return Response(400, "Bad Request", Headers(), b"Malformed request")
            if "injection" in actual_path:
                return Response(400, "Bad Request", Headers(), b"Invalid characters detected")
        
        # Parse the path - support both v1.1.2 format (/v1/ws/database/) and legacy format (/v1/database/)
        if actual_path.startswith("/v1/ws/database/"):
            # V1.1.2 format with /ws/ prefix
            path_parts = actual_path.split("/")
            if len(path_parts) < 5:
                logger.warning(f"[MOCK SERVER] Invalid V1.1.2 endpoint: {actual_path}")
                self.stats["connections_rejected"] += 1
                return Response(404, "Not Found", Headers(), b"Invalid endpoint")
            db_name = path_parts[4]  # /v1/ws/database/{db_name}/subscribe
            
        elif actual_path.startswith("/v1/database/"):
            # Legacy format without /ws/
            path_parts = actual_path.split("/")
            if len(path_parts) < 4:
                logger.warning(f"[MOCK SERVER] Invalid legacy endpoint: {actual_path}")
                self.stats["connections_rejected"] += 1
                return Response(404, "Not Found", Headers(), b"Invalid endpoint")
            db_name = path_parts[3]  # /v1/database/{db_name}/subscribe
            
        else:
            logger.warning(f"[MOCK SERVER] Invalid path rejected: {actual_path}")
            self.stats["connections_rejected"] += 1
            return Response(404, "Not Found", Headers(), b"Invalid path")
        logger.info(f"[MOCK SERVER] Database requested: {db_name}")
        
        # Check for malicious database names and return appropriate errors
        if self._is_malicious_database_name(db_name):
            logger.warning(f"[MOCK SERVER] Malicious database name detected: {db_name}")
            self.stats["connections_rejected"] += 1
            return Response(400, "Bad Request", Headers(), b"Invalid database name")
        
        # Check if database exists
        if db_name not in self.databases:
            logger.warning(f"[MOCK SERVER] Database not found: {db_name}")
            self.stats["connections_rejected"] += 1
            return Response(404, "Not Found", Headers(), b"Database not found")
            
        db = self.databases[db_name]
        
        # Handle unpublished database scenario
        if self.config.scenario == "unpublished":
            logger.warning(f"[MOCK SERVER] Unpublished database scenario - rejecting {db_name}")
            self.stats["connections_rejected"] += 1
            return Response(404, "Not Found", Headers(), b"Database not published")
        
        # Check authentication if required
        if self.config.auth_required:
            auth_header = None
            
            # Handle different formats of request_headers
            if hasattr(request_headers, 'headers'):
                # It's a Request object with a headers attribute (websockets v15+)
                headers = request_headers.headers
                auth_header = headers.get("authorization") or headers.get("Authorization")
            elif hasattr(request_headers, 'get'):
                # It's a Headers object, access directly
                auth_header = request_headers.get("authorization") or request_headers.get("Authorization")
            elif hasattr(request_headers, '__iter__'):
                # It's an iterable of (name, value) tuples
                try:
                    for name, value in request_headers:
                        if name.lower() == "authorization":
                            auth_header = value
                            break
                except (TypeError, ValueError):
                    # Failed to iterate, no auth header found
                    pass
                    
            logger.info(f"[MOCK SERVER] Auth required, header present: {auth_header is not None}")
            if not auth_header or not self._validate_auth(auth_header):
                logger.warning(f"[MOCK SERVER] Authentication failed")
                self.stats["connections_rejected"] += 1
                return Response(401, "Unauthorized", Headers(), b"Unauthorized")
        
        # Allow connection to proceed
        logger.info(f"[MOCK SERVER] Connection allowed for database: {db_name}")
        return None
        
    async def handle_connection(self, websocket):
        """Handle a WebSocket connection."""
        # Extract path from WebSocket object
        path = websocket.path if hasattr(websocket, 'path') else "/v1/database/testdb/subscribe"
        
        # Generate connection ID with thread safety
        with self._connection_lock:
            connection_id = f"conn_{self._connection_counter}"
            self._connection_counter += 1
        
        logger.info(f"[MOCK SERVER] New connection: {connection_id} for path {path}")
        
        try:
            # Check connection limit before processing (with thread safety)
            with self._connection_lock:
                current_connections = len(self.connections)
                logger.info(f"[MOCK SERVER] Connection attempt: current={current_connections}, limit={self.config.max_connections}")
                if current_connections >= self.config.max_connections:
                    logger.warning(f"[MOCK SERVER] Connection limit reached ({current_connections}/{self.config.max_connections})")
                    self.stats["connections_rejected"] += 1
                    # Close immediately without adding to connections
                    await websocket.close(code=1011, reason="Server overloaded")
                    return
            
            # Inject connection delay if configured
            if self.config.connection_delay > 0:
                await asyncio.sleep(self.config.connection_delay)
            
            # Extract path and database info (validation already done in process_request)
            # Support both v1.1.2 format (/v1/ws/database/) and legacy format (/v1/database/)
            if path.startswith("/v1/ws/database/"):
                path_parts = path.split("/")
                db_name = path_parts[4]  # /v1/ws/database/{db_name}/subscribe
            else:
                path_parts = path.split("/")
                db_name = path_parts[3]  # /v1/database/{db_name}/subscribe
                
            db = self.databases[db_name]
            
            # Handle identity (authentication already validated in process_request)
            identity = None
            if self.config.auth_required:
                # Extract identity from validated auth
                auth_header = None
                if hasattr(websocket, 'request_headers'):
                    for header in websocket.request_headers:
                        if header[0].lower() == "authorization":
                            auth_header = header[1]
                            break
                elif hasattr(websocket, 'request') and hasattr(websocket.request, 'headers'):
                    auth_header = websocket.request.headers.get("authorization")
                identity = self._extract_identity_from_auth(auth_header) if auth_header else self._generate_identity()
            else:
                # Generate anonymous identity
                identity = self._generate_identity()
                
            # Check subprotocol
            subprotocol = getattr(websocket, 'subprotocol', self.config.protocol)
                
            # Store connection info and mark as accepted (with thread safety)
            with self._connection_lock:
                self.connections[connection_id] = {
                    "websocket": websocket,
                    "database": db_name,
                    "identity": identity,
                    "connection_id": connection_id,
                    "protocol": subprotocol,
                    "subscriptions": set()
                }
                # Connection accepted - increment counter AFTER storing connection
                self.stats["connections_accepted"] += 1
                
            logger.info(f"[MOCK SERVER] Connection accepted: {connection_id} for database {db_name} (total: {self.stats['connections_accepted']})")
            
            # Send identity token and handshake messages immediately
            # This ensures the client completes the handshake quickly
            try:
                await self._send_identity_token(websocket, identity, connection_id)
                logger.info(f"[MOCK SERVER] Identity token sent for connection {connection_id}")
                
                # Force flush the websocket to ensure immediate delivery
                if hasattr(websocket, 'flush'):
                    await websocket.flush()
                
                # Small delay to allow identity processing
                await asyncio.sleep(0.01)  # 10ms
                
                # Send initial subscription data
                await self._send_initial_subscription(websocket, db)
                logger.info(f"[MOCK SERVER] Initial subscription data sent for connection {connection_id}")
                
            except Exception as e:
                logger.error(f"[MOCK SERVER] Error sending handshake messages for {connection_id}: {e}")
            
            # Handle messages
            async for message in websocket:
                await self._handle_message(connection_id, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection {connection_id} closed")
        except Exception as e:
            logger.error(f"Error handling connection {connection_id}: {e}")
        finally:
            # Clean up connection (with thread safety)
            with self._connection_lock:
                if connection_id in self.connections:
                    del self.connections[connection_id]
                
    def _validate_auth(self, auth_header: str) -> bool:
        """Validate authorization header - supports both Basic and Bearer tokens."""
        logger.info(f"[MOCK SERVER] Validating auth header: {auth_header[:20]}...")
        
        # Handle Bearer tokens (JWT style like real SpacetimeDB)
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            is_valid = token in self.config.valid_tokens
            logger.info(f"[MOCK SERVER] Bearer token validation: {is_valid}")
            return is_valid
            
        # Handle Basic auth for legacy compatibility
        if auth_header.startswith("Basic "):
            try:
                encoded = auth_header[6:]
                decoded = base64.b64decode(encoded).decode('utf-8')
                
                if decoded.startswith("token:"):
                    token = decoded[6:]
                    is_valid = token in self.config.valid_tokens
                    logger.info(f"[MOCK SERVER] Basic token validation: {is_valid}")
                    return is_valid
                else:
                    # Handle username:password format where username is token
                    if ":" in decoded:
                        token = decoded.split(":", 1)[0]
                        is_valid = token in self.config.valid_tokens
                        logger.info(f"[MOCK SERVER] Basic auth username validation: {is_valid}")
                        return is_valid
                    
            except Exception as e:
                logger.warning(f"[MOCK SERVER] Basic auth decode error: {e}")
                return False
        
        logger.warning(f"[MOCK SERVER] Unknown auth format")
        return False
            
    def _is_malicious_database_name(self, db_name: str) -> bool:
        """Check if database name contains malicious patterns."""
        if not db_name:
            return False
            
        malicious_patterns = [
            "../",          # Path traversal
            "..",           # Path traversal
            "DROP",         # SQL injection
            "DELETE",       # SQL injection
            "<script>",     # XSS
            "javascript:",  # JavaScript injection
            "'",            # SQL injection quotes
            '"',            # SQL injection quotes
            ";",            # SQL injection statement separator
            "--",           # SQL comment
            "/*",           # SQL block comment
            "\x00",         # Null bytes
            "\r",           # CRLF injection
            "\n",           # CRLF injection
        ]
        
        db_name_upper = db_name.upper()
        for pattern in malicious_patterns:
            if pattern.upper() in db_name_upper:
                return True
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
            
        # Inject message delay if configured - but ensure it's not too long for tests
        message_delay = self.config.message_delay
        if message_delay > 0:
            # For test stability, cap the delay to avoid timeouts
            max_test_delay = 0.1  # 100ms maximum for tests
            actual_delay = min(message_delay, max_test_delay)
            await asyncio.sleep(actual_delay)
            
        message = {
            "IdentityToken": {
                "identity": identity,
                "token": f"test_token_{int(time.time())}",
                "connection_id": connection_id[5:]  # Remove "conn_" prefix
            }
        }
        
        # Send identity token immediately after connection establishment
        await self._send_message(websocket, message)
        
        # Also send subscription applied event to complete the handshake
        applied_message = {
            "SubscriptionApplied": {
                "request_id": "initial_subscription",
                "total_host_execution_duration_micros": 1000
            }
        }
        await self._send_message(websocket, applied_message)
        
    async def _send_initial_subscription(self, websocket, database: MockDatabase):
        """Send initial subscription data."""
        if self._should_inject_error():
            await self._inject_error(websocket, "Initial subscription error")
            return
            
        # Send table data - optimized for test performance
        for table_name, rows in database.tables.items():
            message = {
                "TransactionUpdate": {
                    "table_name": table_name,
                    "data": rows
                }
            }
            await self._send_message(websocket, message)
            
            # Small delay between table updates to prevent overwhelming the client
            await asyncio.sleep(0.001)  # 1ms between updates
            
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
        subprotocol = getattr(websocket, 'subprotocol', self.config.protocol)
        if subprotocol == self.config.binary_protocol:
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
        print(f"[MOCK SERVER] Starting server on {self.config.host}:{self.config.port}")
        async with websockets.serve(
            self.handle_connection,
            self.config.host,
            self.config.port,
            subprotocols=[self.config.protocol, self.config.binary_protocol],
            process_request=self.process_request
        ) as server:
            self.server = server
            print(f"[MOCK SERVER] Server started and listening on {self.config.host}:{self.config.port}")
            logger.info(f"Mock server started on {self.config.host}:{self.config.port}")
            
            # Keep server running
            while self.running:
                await asyncio.sleep(0.1)
                
            print(f"[MOCK SERVER] Server stopped")
                
    def _run_http_server(self):
        """Run the HTTP server for health checks."""
        try:
            print(f"[MOCK HTTP] Starting HTTP server on {self.config.host}:{self.config.port}")
            
            class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
                daemon_threads = True  # Allow threads to die when main program dies
                
            self.http_server = ThreadingHTTPServer((self.config.host, self.config.port), MockHTTPHandler)
            
            print(f"[MOCK HTTP] HTTP server started and listening on {self.config.host}:{self.config.port}")
            logger.info(f"Mock HTTP server started on {self.config.host}:{self.config.port}")
            
            while self.running:
                self.http_server.timeout = 0.1  # Short timeout for responsive shutdown
                self.http_server.handle_request()
                
        except Exception as e:
            logger.error(f"HTTP server error: {e}")
        finally:
            if self.http_server:
                self.http_server.server_close()
            print(f"[MOCK HTTP] HTTP server stopped")

    def start(self):
        """Start the mock server in a background thread."""
        if self.running:
            return
            
        self.running = True
        
        def run_websocket_server():
            self._server_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._server_loop)
            try:
                self._server_loop.run_until_complete(self._run_server())
            finally:
                # Ensure proper cleanup of event loop
                if not self._server_loop.is_closed():
                    self._server_loop.close()
        
        def run_http_server():
            # Use a different port for HTTP server (WebSocket + 100)
            http_port = self.config.port + 100
            original_port = self.config.port
            self.config.port = http_port
            try:
                self._run_http_server()
            finally:
                self.config.port = original_port  # Restore original port
            
        # Start WebSocket server on main port
        self.server_thread = threading.Thread(target=run_websocket_server, daemon=True)
        self.server_thread.start()
        
        # Start HTTP server on different port (only if needed for health checks)
        # For integration tests, we primarily need WebSocket server
        # self.http_server_thread = threading.Thread(target=run_http_server, daemon=True)
        # self.http_server_thread.start()
        
        # Wait for server to start - optimized for tests but ensure proper startup
        max_wait_time = 1.0  # Maximum wait time
        wait_interval = 0.05  # Check every 50ms
        elapsed = 0
        
        while elapsed < max_wait_time:
            time.sleep(wait_interval)
            elapsed += wait_interval
            # Simple check if server thread is running
            if self.server_thread and self.server_thread.is_alive():
                # Give it a bit more time to fully initialize
                time.sleep(0.1)
                break
        
    def stop(self):
        """Stop the mock server."""
        self.running = False
        
        # Stop WebSocket server
        if self.server_thread:
            self.server_thread.join(timeout=2)
        
        # Stop HTTP server
        if self.http_server:
            try:
                self.http_server.shutdown()
            except:
                pass  # Ignore shutdown errors
        if self.http_server_thread:
            self.http_server_thread.join(timeout=2)
        
        # Clean up server event loop if it exists
        if hasattr(self, '_server_loop') and self._server_loop:
            if not self._server_loop.is_closed():
                try:
                    self._server_loop.close()
                except Exception:
                    pass  # Ignore cleanup errors
            self._server_loop = None
            
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
        # Preserve current port and other settings
        current_port = self.config.port if self.config else 3001
        current_max_connections = self.config.max_connections if self.config else 100
        
        scenarios = {
            "normal": MockServerConfig(port=current_port, max_connections=current_max_connections),
            "auth_required": MockServerConfig(auth_required=True, port=current_port, max_connections=current_max_connections),
            "unpublished": MockServerConfig(database_published=False, port=current_port, max_connections=current_max_connections),
            "slow_connection": MockServerConfig(connection_delay=0.5, port=current_port, max_connections=current_max_connections),  # Reduced from 2.0s
            "slow_messages": MockServerConfig(message_delay=0.1, port=current_port, max_connections=current_max_connections),  # Reduced from 0.5s
            "error_prone": MockServerConfig(inject_errors=True, error_rate=0.3, port=current_port, max_connections=current_max_connections),
            "binary_only": MockServerConfig(support_binary_protocol=True, port=current_port, max_connections=current_max_connections),
            "validation_errors": MockServerConfig(port=current_port, max_connections=current_max_connections),  # For testing validation errors
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
