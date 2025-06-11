"""
Modern WebSocket client for SpacetimeDB protocol v1.1.1

This replaces the old spacetime_websocket_client.py with support for:
- Modern protocol message types
- Connection lifecycle management
- QueryId-based subscription tracking
- Energy quota management
- Reconnection with exponential backoff
- Message compression (Brotli/Gzip) for production performance
"""

import websocket
import threading
import time
import base64
import logging
import json
from typing import Optional, Callable, Dict, List, Any
from enum import Enum
import uuid

from .exceptions import (
    WebSocketHandshakeError,
    DatabaseNotFoundError,
    DatabaseNotPublishedError,
    AuthenticationError,
    ProtocolMismatchError,
    ConnectionTimeoutError,
    SpacetimeDBConnectionError,
    ServerNotAvailableError,
    RetryableError
)
from .connection_diagnostics import ConnectionDiagnostics
from .retry_policies import RetryPolicy, RetryPolicyPresets
from .protocol import (
    TEXT_PROTOCOL, BIN_PROTOCOL,
    ClientMessage, ServerMessage,
    ProtocolEncoder, ProtocolDecoder,
    Identity, ConnectionId,
    CallReducer, Subscribe, Unsubscribe, OneOffQuery,
    TransactionUpdate, TransactionUpdateLight, InitialSubscription,
    IdentityToken, SubscribeApplied, UnsubscribeApplied,
    SubscriptionError, SubscribeMultiApplied, UnsubscribeMultiApplied,
    CallReducerFlags, generate_request_id
)
from .messages.subscribe import (
    SubscribeSingleMessage,
    SubscribeMultiMessage,
    UnsubscribeMultiMessage
)
from .messages.one_off_query import (
    OneOffQueryMessage
)
from .query_id import QueryId
from .compression import (
    CompressionManager,
    CompressionConfig,
    CompressionType,
    CompressionLevel,
    CompressionMetrics
)


class ConnectionState(Enum):
    """Connection state tracking."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class ModernWebSocketClient:
    """
    Modern WebSocket client for SpacetimeDB with support for protocol v1.1.1.
    
    Features:
    - Modern message types (SubscribeSingle, QueryId, etc.)
    - Connection lifecycle management
    - Automatic reconnection with exponential backoff
    - Energy quota tracking
    - Message compression (Brotli/Gzip) for production performance
    - Compression negotiation and adaptive thresholds
    - Proper error handling
    """
    
    def __init__(
        self,
        protocol: str = TEXT_PROTOCOL,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_message: Optional[Callable[[ServerMessage], None]] = None,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        initial_reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
        compression_config: Optional[CompressionConfig] = None,
        retry_policy: Optional[RetryPolicy] = None
    ):
        self.protocol = protocol
        self.use_binary = protocol == BIN_PROTOCOL
        
        # Callbacks
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_error = on_error
        self._on_message = on_message
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.ws: Optional[websocket.WebSocketApp] = None
        self.connection_thread: Optional[threading.Thread] = None
        
        # Connection details
        self.auth_token: Optional[str] = None
        self.host: Optional[str] = None
        self.database_address: Optional[str] = None
        self.ssl_enabled: bool = True
        
        # Identity and connection tracking
        self.identity: Optional[Identity] = None
        self.connection_id: Optional[ConnectionId] = None
        
        # Protocol handling
        self.encoder = ProtocolEncoder(use_binary=self.use_binary)
        self.decoder = ProtocolDecoder(use_binary=self.use_binary)
        
        # Compression support
        self.compression_manager = CompressionManager(compression_config)
        self.negotiated_compression: Optional[CompressionType] = None
        
        # Reconnection logic
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.initial_reconnect_delay = initial_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.reconnect_attempts = 0
        self.reconnect_timer: Optional[threading.Timer] = None
        
        # Connection diagnostics
        self.diagnostics = ConnectionDiagnostics()
        self.enable_preflight_checks = True
        self.retry_on_transient_errors = True
        
        # Retry policy
        self.retry_policy = retry_policy or RetryPolicyPresets.standard()
        
        # Store connection URL for error diagnostics
        self.connection_url: Optional[str] = None
        
        # Subscription tracking
        self.active_subscriptions: Dict[int, QueryId] = {}  # request_id -> QueryId
        self.subscription_queries: Dict[QueryId, List[str]] = {}  # QueryId -> queries
        
        # Request tracking
        self.pending_requests: Dict[int, threading.Event] = {}
        self.request_responses: Dict[int, Any] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.ModernWebSocketClient_{id(self)}")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            self.logger.propagate = False
        
        self.logger.debug("ModernWebSocketClient initializing...")
        self.logger.info(f"WebSocket client initialized with compression: {self.compression_manager.get_compression_info()['capabilities']['supported_types']}")
        self.logger.debug("ModernWebSocketClient initialized.")
    
    def connect(
        self,
        auth_token: Optional[str],
        host: str,
        database_address: str,
        ssl_enabled: bool = True,
        db_identity: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None
    ) -> None:
        """Connect to SpacetimeDB with preflight checks and better error handling."""
        with self._lock:
            if self.state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
                self.logger.warning("Already connected or connecting")
                return
            
            self.auth_token = auth_token
            self.host = host
            self.database_address = database_address
            self.db_identity = db_identity
            self.ssl_enabled = ssl_enabled
            self.reconnect_attempts = 0
            
            # Use provided retry policy or default
            if retry_policy:
                self.retry_policy = retry_policy
            
            # Run preflight checks if enabled
            if self.enable_preflight_checks:
                try:
                    self.logger.info("Running preflight checks...")
                    checks = self.diagnostics.run_preflight_checks(
                        host=host,
                        database=database_address,
                        raise_on_failure=True
                    )
                    self.logger.info("Preflight checks passed")
                except Exception as e:
                    self.logger.error(f"Preflight checks failed: {e}")
                    if self._on_error:
                        self._on_error(e)
                    raise
            
            self._do_connect()
    
    def _do_connect(self) -> None:
        """Internal connection logic with retry support."""
        self.logger.debug(f"_do_connect called. Current state: {self.state.value}. Attempt: {self.reconnect_attempts + 1}")
        
        def _attempt_connection():
            self.state = ConnectionState.CONNECTING
            
            # Build WebSocket URL for v1.1.2 compatibility
            protocol_scheme = "wss" if self.ssl_enabled else "ws"
            # Always use database_address in the URL path
            url = f"{protocol_scheme}://{self.host}/v1/database/{self.database_address}/subscribe"
            
            # Add db_identity as query parameter if provided
            if self.db_identity:
                url += f"?db_identity={self.db_identity}"
            
            # Store URL for error diagnostics
            self.connection_url = url
            
            self.logger.debug(f"_do_connect: Set state to CONNECTING. URL: {url}")
            
            # Prepare headers
            headers = {}
            if self.auth_token:
                token_bytes = f"token:{self.auth_token}".encode('utf-8')
                base64_str = base64.b64encode(token_bytes).decode('utf-8')
                headers["Authorization"] = f"Basic {base64_str}"
            
            # Add compression negotiation headers
            compression_headers = self.compression_manager.create_compression_headers()
            headers.update(compression_headers)
            
            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                url,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
                header=headers,
                subprotocols=[self.protocol]
            )
            self.logger.debug("_do_connect: WebSocketApp instance created.")
            
            # Start connection in separate thread
            self.connection_thread = threading.Thread(
                target=self.ws.run_forever,
                daemon=True,
                name=f"ModernWebSocketClient-ConnectionThread-{id(self)}"
            )
            self.connection_thread.start()
            self.logger.debug(f"_do_connect: Connection thread (ID: {self.connection_thread.ident}) started for {url}")
        
        # Apply retry policy if this is an initial connection attempt
        if self.reconnect_attempts == 0 and self.retry_on_transient_errors:
            try:
                self.retry_policy.execute_with_retry(_attempt_connection)
            except Exception as e:
                self.logger.error(f"_do_connect: Failed to start connection after retries: {e}", exc_info=True)
                self.state = ConnectionState.DISCONNECTED
                if self._on_error:
                    self._on_error(e)
                # Don't schedule reconnect here as retry policy already attempted
        else:
            # For reconnection attempts, don't use retry policy (already has backoff)
            try:
                _attempt_connection()
            except Exception as e:
                self.logger.error(f"_do_connect: Failed to start connection: {e}", exc_info=True)
                self.state = ConnectionState.DISCONNECTED
                if self._on_error:
                    self._on_error(e)
                self._schedule_reconnect()
    
    def disconnect(self) -> None:
        """Disconnect from SpacetimeDB and ensure the connection thread is stopped."""
        self.logger.debug(f"Disconnect called. Current thread: {threading.get_ident()}, Current state: {self.state.value}")
        with self._lock:
            self.logger.debug("Disconnect: Acquired _lock.")
            self.logger.info("WebSocket client disconnect initiated.")
            # Prevent further auto-reconnection attempts
            self.auto_reconnect = False 
            self.state = ConnectionState.CLOSED # Mark as intentionally closed

            if self.reconnect_timer:
                self.logger.debug("Disconnect: Cancelling reconnect_timer.")
                self.reconnect_timer.cancel()
                self.reconnect_timer = None
            
            current_ws = self.ws
            current_thread = self.connection_thread
            self.logger.debug(f"Disconnect: current_ws is {'set' if current_ws else 'None'}, current_thread is {'set and alive' if current_thread and current_thread.is_alive() else ('set but not alive' if current_thread else 'None')}")

            if current_ws:
                self.logger.debug("Disconnect: Calling current_ws.close().")
                try:
                    current_ws.close()
                    self.logger.debug("Disconnect: current_ws.close() returned.")
                except Exception as e:
                    self.logger.error(f"Disconnect: Exception during current_ws.close(): {e}", exc_info=True)
            
            if current_thread and current_thread.is_alive():
                self.logger.debug(f"Disconnect: Joining connection_thread (ID: {current_thread.ident}).")
                current_thread.join(timeout=2.0)
                if current_thread.is_alive():
                    self.logger.warning(f"Disconnect: connection_thread (ID: {current_thread.ident}) did NOT stop cleanly.")
                else:
                    self.logger.debug(f"Disconnect: connection_thread (ID: {current_thread.ident}) stopped.")
            
            self.ws = None # Clear after join attempt
            self.connection_thread = None # Clear after join attempt
            self.logger.debug("Disconnect: Cleared ws and connection_thread attributes.")
            
            # Clear other state
            self.identity = None
            self.connection_id = None
            self.active_subscriptions.clear()
            self.subscription_queries.clear()
            self.negotiated_compression = None
            self.logger.info("WebSocket client disconnected and cleaned up.")
    
    def send_message(self, message: ClientMessage) -> None:
        """Send a client message to the server with optional compression."""
        if self.state != ConnectionState.CONNECTED or not self.ws:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        try:
            # Encode the message
            encoded_data = self.encoder.encode_client_message(message)
            
            # Apply compression if negotiated and beneficial
            if self.negotiated_compression and self.negotiated_compression != CompressionType.NONE:
                try:
                    compressed_data, compression_used = self.compression_manager.compress(
                        encoded_data, self.negotiated_compression
                    )
                    
                    if compression_used != CompressionType.NONE:
                        # Add compression metadata if needed
                        # For WebSocket, compression is typically transparent
                        encoded_data = compressed_data
                        self.logger.debug(f"Compressed message: {len(encoded_data)} -> {len(compressed_data)} bytes ({compression_used.value})")
                    
                except Exception as e:
                    self.logger.warning(f"Compression failed, sending uncompressed: {e}")
                    # Continue with uncompressed data
            
            # Send the message
            self.ws.send(encoded_data)
            self.logger.debug(f"Sent message: {type(message).__name__} ({len(encoded_data)} bytes)")
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            raise
    
    def call_reducer(
        self,
        reducer_name: str,
        args: bytes,
        flags: Optional[Any] = None
    ) -> int:
        """Call a reducer and return the request ID."""
        request_id = generate_request_id()
        message = CallReducer(
            reducer=reducer_name,
            args=args,
            request_id=request_id,
            flags=flags or CallReducerFlags.FULL_UPDATE
        )
        self.send_message(message)
        return request_id
    
    def subscribe_to_queries(self, queries: List[str]) -> int:
        """Subscribe to a list of queries (legacy method)."""
        request_id = generate_request_id()
        message = Subscribe(
            query_strings=queries,
            request_id=request_id
        )
        self.send_message(message)
        return request_id
    
    def subscribe_single(self, query: str) -> QueryId:
        """Subscribe to a single query with QueryId tracking."""
        request_id = generate_request_id()
        query_id = QueryId.generate()
        
        with self._lock:
            self.active_subscriptions[request_id] = query_id
            self.subscription_queries[query_id] = [query]
        
        message = SubscribeSingleMessage(
            query=query,
            request_id=request_id,
            query_id=query_id
        )
        self.send_message(message)
        return query_id
    
    def subscribe_multi(self, queries: List[str]) -> QueryId:
        """Subscribe to multiple queries with QueryId tracking."""
        request_id = generate_request_id()
        query_id = QueryId.generate()
        
        with self._lock:
            self.active_subscriptions[request_id] = query_id
            self.subscription_queries[query_id] = queries
        
        message = SubscribeMultiMessage(
            query_strings=queries,
            request_id=request_id,
            query_id=query_id
        )
        self.send_message(message)
        return query_id
    
    def unsubscribe(self, query_id: QueryId) -> int:
        """Unsubscribe from a query."""
        request_id = generate_request_id()
        
        with self._lock:
            # Remove from tracking
            if query_id in self.subscription_queries:
                del self.subscription_queries[query_id]
            
            # Find and remove from active subscriptions
            for req_id, qid in list(self.active_subscriptions.items()):
                if qid.id == query_id.id:
                    del self.active_subscriptions[req_id]
                    break
        
        message = Unsubscribe(
            request_id=request_id,
            query_id=query_id
        )
        self.send_message(message)
        return request_id
    
    def execute_one_off_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a one-off query with enhanced metadata tracking.
        
        Args:
            query: The SQL query string to execute
            
        Returns:
            Dict containing metadata about the query execution:
            - message_id: bytes - The message ID for tracking
            - query: str - The original query string  
            - timestamp: float - When the query was sent
            
        Raises:
            RuntimeError: If not connected to SpacetimeDB
        """
        if self.state != ConnectionState.CONNECTED or not self.ws:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        # Generate enhanced one-off query message
        message = OneOffQueryMessage.generate(query)
        
        # Track execution metadata
        metadata = {
            "message_id": message.message_id,
            "query": query,
            "timestamp": time.time()
        }
        
        try:
            self.send_message(message)
            self.logger.debug(f"Sent enhanced one-off query: {query[:50]}...")
        except Exception as e:
            self.logger.error(f"Failed to send enhanced one-off query: {e}")
            raise
        
        return metadata
    
    def one_off_query(self, query: str) -> bytes:
        """
        Execute a one-off query (legacy method for backward compatibility).
        
        Args:
            query: The SQL query string to execute
            
        Returns:
            bytes: The message ID for tracking
            
        Raises:
            RuntimeError: If not connected to SpacetimeDB
        """
        if self.state != ConnectionState.CONNECTED or not self.ws:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        # Use legacy OneOffQuery for backward compatibility
        message_id = uuid.uuid4().bytes
        message = OneOffQuery(
            message_id=message_id,
            query_string=query
        )
        self.send_message(message)
        return message_id
    
    def _on_ws_open(self, ws) -> None:
        """WebSocket connection opened."""
        self.logger.debug(f"_on_ws_open: Callback triggered. Current thread: {threading.get_ident()}")
        with self._lock:
            self.logger.debug("_on_ws_open: Acquired _lock.")
            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0
            
            # Attempt compression negotiation from server response headers
            # In practice, WebSocket compression is usually handled at the WebSocket layer
            # but we can still track what we negotiated for application-level compression
            
        self.logger.info("Connected to SpacetimeDB (WebSocket open). Calling _on_connect callback if any.")
        
        if self._on_connect:
            try:
                self._on_connect()
            except Exception as e:
                self.logger.error(f"_on_ws_open: Error in _on_connect callback: {e}", exc_info=True)
    
    def _on_ws_message(self, ws, message) -> None:
        """WebSocket message received with enhanced large message handling."""
        try:
            # Handle incoming message data
            if isinstance(message, str):
                message_data = message.encode('utf-8')
            else:
                message_data = message
            
            message_size = len(message_data)
            large_message_threshold = 50 * 1024  # 50KB
            
            # Log large message handling for debugging
            if message_size > large_message_threshold:
                self.logger.info(f"Processing large message: {message_size} bytes")
                
                # Log InitialSubscription details if this is a large subscription
                try:
                    if message_data.startswith(b'{') and b'"InitialSubscription"' in message_data:
                        # Parse just enough to get summary info without full processing
                        import json
                        parsed_preview = json.loads(message_data.decode('utf-8'))
                        if "InitialSubscription" in parsed_preview:
                            initial_sub = parsed_preview["InitialSubscription"]
                            database_update = initial_sub.get("database_update", {})
                            tables = database_update.get("tables", [])
                            self.logger.info(f"Large InitialSubscription: {len(tables)} tables, {message_size} bytes")
                            for table in tables:
                                table_name = table.get("table_name", "unknown")
                                num_rows = table.get("num_rows", 0)
                                self.logger.debug(f"  - {table_name}: {num_rows} rows")
                except Exception as parse_error:
                    self.logger.debug(f"Could not parse large message preview: {parse_error}")
            
            # Apply decompression if needed
            if self.negotiated_compression and self.negotiated_compression != CompressionType.NONE:
                try:
                    decompressed_data = self.compression_manager.decompress(
                        message_data, self.negotiated_compression
                    )
                    message_data = decompressed_data
                    self.logger.debug(f"Decompressed message: {len(message)} -> {len(message_data)} bytes")
                except Exception as e:
                    self.logger.warning(f"Decompression failed, processing as uncompressed: {e}")
                    # Continue with original data
            
            # Decode the server message with enhanced error handling for large messages
            try:
                server_message = self.decoder.decode_server_message(message_data)
            except Exception as decode_error:
                if message_size > large_message_threshold:
                    self.logger.error(f"Failed to decode large message ({message_size} bytes): {decode_error}")
                    self.logger.info("Large message decode failure - this may indicate:")
                    self.logger.info("1. Message corruption during transmission")
                    self.logger.info("2. WebSocket frame fragmentation issues")
                    self.logger.info("3. Server-side message formatting problems")
                else:
                    self.logger.error(f"Failed to decode message: {decode_error}")
                raise
            
            # Handle identity token
            if isinstance(server_message, IdentityToken):
                with self._lock:
                    self.identity = server_message.identity
                    self.connection_id = server_message.connection_id
                self.logger.info(f"Received identity: {self.identity}")
            
            # Log successful processing of large messages
            if message_size > large_message_threshold:
                self.logger.info(f"Successfully processed large message: {type(server_message).__name__}")
            
            # Forward to application
            if self._on_message:
                self._on_message(server_message)
                
        except Exception as e:
            # Enhanced error logging for large message issues
            message_size = len(message) if hasattr(message, '__len__') else 0
            if message_size > 50 * 1024:  # 50KB
                self.logger.error(f"Large message processing failed ({message_size} bytes): {e}")
                self.logger.info("Large message error - consider:")
                self.logger.info("1. Increasing WebSocket buffer sizes")
                self.logger.info("2. Implementing message streaming")
                self.logger.info("3. Server-side message compression")
            else:
                self.logger.error(f"Failed to process message: {e}")
            
            if self._on_error:
                self._on_error(e)
    
    def _on_ws_error(self, ws, error) -> None:
        """WebSocket error occurred with enhanced error handling."""
        error_str = str(error).lower()
        
        # Enhanced detection for large message related errors
        if "invalid close frame" in error_str:
            self.logger.error("WebSocket Invalid Close Frame Error detected")
            self.logger.info("This often occurs after processing large messages (>50KB)")
            self.logger.info("Possible causes:")
            self.logger.info("1. Server sending malformed close frames after large data")
            self.logger.info("2. WebSocket buffer overflow during large message processing")
            self.logger.info("3. Protocol violation in close frame format")
            self.logger.info("Implementing enhanced error recovery...")
            
            # Don't propagate this error immediately - try to recover
            # The connection will be handled by the close callback
            return
            
        self.logger.error(f"WebSocket error: {error}")
        
        # Try to parse handshake errors
        try:
            error_str = str(error)
            
            # Check for handshake status codes
            if "Handshake status" in error_str:
                # Extract status code and message
                import re
                status_match = re.search(r"Handshake status (\d+)\s*(.*)?", error_str)
                if status_match:
                    status_code = int(status_match.group(1))
                    status_message = status_match.group(2) or "Unknown"
                    
                    # Extract server headers if available
                    headers = {}
                    if hasattr(error, 'headers'):
                        headers = dict(error.headers)
                    elif "spacetime-identity" in error_str:
                        # Try to extract headers from error string
                        identity_match = re.search(r"spacetime-identity:\s*([a-fA-F0-9]+)", error_str)
                        if identity_match:
                            headers["spacetime-identity"] = identity_match.group(1)
                        
                        token_match = re.search(r"spacetime-identity-token:\s*([\w.-]+)", error_str)
                        if token_match:
                            headers["spacetime-identity-token"] = token_match.group(1)
                    
                    # Create appropriate exception based on status code
                    if status_code == 404:
                        database_name = self.database_address or "unknown"
                        # Run database check to determine if unpublished
                        db_check = self.diagnostics.check_database_exists(self.host, database_name)
                        
                        if db_check.get("exists") in [True, "likely"] and not db_check.get("published"):
                            error = DatabaseNotPublishedError(
                                database_name=database_name,
                                host=self.host,
                                diagnostic_info={
                                    "url": self.connection_url,
                                    "protocol": self.protocol,
                                    "headers": headers,
                                    "database_check": db_check
                                }
                            )
                        else:
                            error = DatabaseNotFoundError(
                                database_name=database_name,
                                status_code=status_code,
                                server_message=status_message,
                                diagnostic_info={
                                    "url": self.connection_url,
                                    "protocol": self.protocol,
                                    "headers": headers,
                                    "database_check": db_check,
                                    "database_state": db_check.get("database_state", "unknown"),
                                    "confidence": db_check.get("confidence", "low")
                                },
                                is_likely_unpublished=db_check.get("confidence") in ["medium", "high"]
                            )
                    elif status_code == 401 or status_code == 403:
                        error = AuthenticationError(
                            reason=f"HTTP {status_code}: {status_message}",
                            auth_method="Basic" if self.auth_token else "None",
                            status_code=status_code
                        )
                    else:
                        error = WebSocketHandshakeError(
                            status_code=status_code,
                            status_message=status_message,
                            url=self.connection_url or "",
                            headers=headers,
                            diagnostic_info={
                                "protocol": self.protocol,
                                "database": self.database_address
                            }
                        )
            
            # Check for protocol mismatch
            elif "protocol" in error_str.lower() and ("mismatch" in error_str.lower() or "rejected" in error_str.lower()):
                error = ProtocolMismatchError(
                    requested_protocol=self.protocol,
                    server_message=error_str
                )
            
            # Check for timeout
            elif "timeout" in error_str.lower():
                error = ConnectionTimeoutError(
                    operation="WebSocket handshake",
                    timeout_seconds=10.0,  # Default WebSocket timeout
                    retry_count=self.reconnect_attempts
                )
            
            # For other errors, use diagnostics
            else:
                # Run diagnostics to provide helpful error message
                try:
                    error = self.diagnostics.diagnose_connection_error(
                        error,
                        self.connection_url or "",
                        self.database_address
                    )
                except Exception as diag_error:
                    # If diagnostics raise an exception, use that
                    error = diag_error
                    
        except Exception as parse_error:
            self.logger.debug(f"Failed to parse WebSocket error: {parse_error}")
            # Keep original error if parsing fails
        
        if self._on_error:
            self._on_error(error)
    
    def _on_ws_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket connection closed."""
        self.logger.debug(f"_on_ws_close: Callback triggered. Current thread: {threading.get_ident()}. Status: {close_status_code}, Msg: {close_msg}, Current state before lock: {self.state.value}")
        with self._lock:
            self.logger.debug("_on_ws_close: Acquired _lock.")
            # Only change state if not already intentionally CLOSED
            # This prevents overwriting the CLOSED state set by an explicit disconnect()
            if self.state != ConnectionState.CLOSED:
                self.logger.debug(f"_on_ws_close: Current state {self.state.value} is not CLOSED, setting to DISCONNECTED.")
                self.state = ConnectionState.DISCONNECTED
            else:
                self.logger.debug(f"_on_ws_close: Current state is already CLOSED, not changing to DISCONNECTED.")
            
            # Store whether we were actively connected before this close event
            # This helps decide if a spontaneous disconnect needs reconnection.    
            # Note: self.state might have been CONNECTING or RECONNECTING if the connection never fully established before closing.
            # We should consider if 'was_connected' should also be true for RECONNECTING if a reconnect attempt fails and closes.
            # For now, let's assume 'was_connected' means it *was* in a state that implies an active or desired active link.
            was_actively_linked = self.state == ConnectionState.CONNECTED or self.state == ConnectionState.CONNECTING or self.state == ConnectionState.RECONNECTING
            self.logger.debug(f"_on_ws_close: was_actively_linked: {was_actively_linked}. State after potential change: {self.state.value}")
            final_state_before_callback = self.state
        
        self.logger.info(f"Disconnected from SpacetimeDB (WebSocket closed). Reason: {close_msg or 'N/A'}. State before _on_disconnect_callback: {final_state_before_callback.value}")
        if self._on_disconnect:
            try:
                self._on_disconnect(close_msg or "Connection closed")
            except Exception as e:
                self.logger.error(f"_on_ws_close: Error in _on_disconnect callback: {e}", exc_info=True)
        
        with self._lock:
            self.logger.debug("_on_ws_close: Re-acquired _lock to check for reconnect.")
            if self.auto_reconnect and self.state != ConnectionState.CLOSED and was_actively_linked:
                self.logger.info(f"_on_ws_close: Conditions met for reconnect. auto_reconnect={self.auto_reconnect}, state={self.state.value}, was_actively_linked={was_actively_linked}. Scheduling...")
                self._schedule_reconnect()
            else:
                self.logger.info(f"_on_ws_close: Conditions NOT met for reconnect. auto_reconnect={self.auto_reconnect}, state={self.state.value}, was_actively_linked={was_actively_linked}.")
    
    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        self.logger.debug(f"_schedule_reconnect called. Current state: {self.state.value}, auto_reconnect: {self.auto_reconnect}, attempts: {self.reconnect_attempts}")
        if not self.auto_reconnect or self.state == ConnectionState.CLOSED:
            self.logger.debug("_schedule_reconnect: Not scheduling (auto_reconnect False or state is CLOSED).")
            return
        
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error("_schedule_reconnect: Max reconnection attempts reached. Setting state to CLOSED.")
            self.state = ConnectionState.CLOSED # Ensure state is CLOSED here
            return
        
        self.state = ConnectionState.RECONNECTING # Set state before scheduling timer
        delay = min(
            self.initial_reconnect_delay * (2 ** self.reconnect_attempts),
            self.max_reconnect_delay
        )
        self.reconnect_attempts += 1
        self.logger.debug(f"_schedule_reconnect: Scheduling timer for {delay:.1f}s.")
        self.reconnect_timer = threading.Timer(delay, self._do_connect)
        self.reconnect_timer.start()
        self.logger.debug(f"_schedule_reconnect: Reconnect timer started for attempt {self.reconnect_attempts}.")
    
    # Compression-specific methods
    
    def set_compression_config(self, config: CompressionConfig) -> None:
        """Update compression configuration."""
        self.compression_manager.config = config
        self.logger.info(f"Updated compression config: enabled={config.enabled}, threshold={config.minimum_size_threshold}")
    
    def get_compression_info(self) -> Dict[str, Any]:
        """Get comprehensive compression information."""
        info = self.compression_manager.get_compression_info()
        info["negotiated_compression"] = self.negotiated_compression.value if self.negotiated_compression else None
        return info
    
    def get_compression_metrics(self) -> CompressionMetrics:
        """Get compression performance metrics."""
        return self.compression_manager.get_metrics()
    
    def reset_compression_metrics(self) -> None:
        """Reset compression metrics."""
        self.compression_manager.reset_metrics()
    
    def enable_compression(self, enabled: bool = True) -> None:
        """Enable or disable compression."""
        self.compression_manager.config.enabled = enabled
        self.logger.info(f"Compression {'enabled' if enabled else 'disabled'}")
    
    def set_compression_threshold(self, threshold: int) -> None:
        """Set minimum compression threshold in bytes."""
        self.compression_manager.config.minimum_size_threshold = threshold
        self.logger.info(f"Compression threshold set to {threshold} bytes")
    
    def set_compression_level(self, level: CompressionLevel) -> None:
        """Set compression level."""
        self.compression_manager.config.compression_level = level
        self.logger.info(f"Compression level set to {level.value}")
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.state == ConnectionState.CONNECTED
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information."""
        compression_info = self.get_compression_info()
        
        return {
            "state": self.state.value,
            "identity": str(self.identity) if self.identity else None,
            "connection_id": str(self.connection_id) if self.connection_id else None,
            "host": self.host,
            "database": self.database_address,
            "protocol": self.protocol,
            "active_subscriptions": len(self.active_subscriptions),
            "reconnect_attempts": self.reconnect_attempts,
            "compression": {
                "enabled": compression_info["config"]["enabled"],
                "negotiated_type": compression_info.get("negotiated_compression"),
                "supported_types": compression_info["capabilities"]["supported_types"],
                "metrics": {
                    "messages_compressed": compression_info["metrics"]["messages_compressed"],
                    "messages_decompressed": compression_info["metrics"]["messages_decompressed"],
                    "compression_ratio": compression_info["metrics"]["compression_ratio"],
                    "space_savings_percent": compression_info["metrics"]["space_savings_percent"]
                }
            }
        }
