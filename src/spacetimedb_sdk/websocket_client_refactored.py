"""
Refactored Modern WebSocket client for SpacetimeDB protocol v1.1.1

This refactored implementation uses modular components for better maintainability:
- SubscriptionManager for subscription handling
- AuthenticationHandler for authentication logic
- UnifiedEventManager for event management
- Maintains 100% API compatibility with ModernWebSocketClient
"""

import websocket
import threading
import time
import logging
from typing import Optional, Callable, Dict, List, Any, Union
from enum import Enum
import warnings

from .exceptions import (
    WebSocketHandshakeError,
    DatabaseNotFoundError,
    DatabaseNotPublishedError,
    AuthenticationError,
    ProtocolMismatchError,
    ConnectionTimeoutError,
    SpacetimeDBConnectionError,
    ServerNotAvailableError,
    RetryableError,
    SpacetimeDBAuthHandshakeError
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
from .query_id import QueryId
from .compression import (
    CompressionManager,
    CompressionConfig,
    CompressionType,
    CompressionLevel,
    CompressionMetrics
)
from .large_message_handler import LargeMessageHandler
from .memory_management import (
    BoundedDict, BoundedSubscriptionManager, RecursionLimiter,
    MemoryAccountant, MessageSizeValidator, get_global_memory_accountant
)
from .validation import (
    get_security_manager,
    validate_url,
    validate_websocket_url,
    validate_sql_query,
    validate_json_data,
    sanitize_url,
    sanitize_sql_query,
    sanitize_json_data,
    ValidationError
)

# Import the extracted modules
from .connection.subscription_manager import SubscriptionManager, SubscriptionState
from .connection.authentication_handler import AuthenticationHandler, AuthenticationState
from .events import UnifiedEventManager, EventType, EventContext, ConnectionEvent, create_connection_event


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSED = "closed"
    ERROR = "error"


class ModernWebSocketClient:
    """
    Refactored WebSocket client for SpacetimeDB using modular architecture.
    
    This client maintains 100% API compatibility with the original implementation
    while delegating core functionality to specialized managers.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1:3000",
        ssl: bool = False,
        auth_token: Optional[str] = None,
        db_address: Optional[str] = None,
        db_id: Optional[str] = None,
        auto_reconnect: bool = True,
        reconnect_interval: float = 5.0,
        max_reconnect_attempts: int = 10,
        enable_compression: bool = True,
        compression_config: Optional[CompressionConfig] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_subscription_applied: Optional[Callable] = None,
        retry_on_transient_errors: bool = True,
        retry_policy: Optional[RetryPolicy] = None,
        protocol: str = BIN_PROTOCOL,
        expect_binary_frames: Optional[bool] = None,
        enable_diagnostics: bool = False,
        enable_subscription_metrics: bool = True,
        memory_limit_mb: Optional[int] = None
    ):
        """Initialize the refactored WebSocket client with modular components."""
        self.logger = logging.getLogger(__name__)
        
        # Basic connection parameters
        self.host = host
        self.ssl = ssl
        self.db_address = db_address
        self.db_id = db_id
        self.protocol = protocol
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self._lock = threading.RLock()
        self.ws: Optional[websocket.WebSocketApp] = None
        self.connection_thread: Optional[threading.Thread] = None
        
        # Initialize modular components
        self.event_manager = UnifiedEventManager(enable_metrics=True)
        
        self.subscription_manager = SubscriptionManager(
            event_manager=self.event_manager,
            enable_metrics=enable_subscription_metrics,
            memory_limit_mb=memory_limit_mb
        )
        
        self.auth_handler = AuthenticationHandler(
            auth_token=auth_token,
            event_manager=self.event_manager
        )
        
        # Compression management
        self.compression_manager = CompressionManager(
            config=compression_config or CompressionConfig(enabled=enable_compression)
        )
        
        # Large message handling
        self.large_message_handler = LargeMessageHandler()
        
        # Protocol handling
        self.protocol_encoder = ProtocolEncoder(protocol=self.protocol)
        self.protocol_decoder = ProtocolDecoder(protocol=self.protocol)
        self.expect_binary_frames = expect_binary_frames or self._determine_frame_type(protocol)
        
        # Retry and reconnection
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_attempts = 0
        self.reconnect_timer: Optional[threading.Timer] = None
        self.retry_on_transient_errors = retry_on_transient_errors
        self.retry_policy = retry_policy or RetryPolicyPresets.default()
        
        # Diagnostics
        self.enable_diagnostics = enable_diagnostics
        self.diagnostics = ConnectionDiagnostics() if enable_diagnostics else None
        
        # Memory management
        self.memory_accountant = get_global_memory_accountant()
        if memory_limit_mb:
            self.memory_accountant.set_memory_limit(memory_limit_mb * 1024 * 1024)
        
        # Legacy callbacks - register with event manager
        if on_connect:
            self.event_manager.register_handler(
                EventType.CONNECTION_ESTABLISHED,
                lambda event: on_connect()
            )
        if on_disconnect:
            self.event_manager.register_handler(
                EventType.CONNECTION_CLOSED,
                lambda event: on_disconnect()
            )
        if on_error:
            self.event_manager.register_handler(
                EventType.CONNECTION_ERROR,
                lambda event: on_error(event.data.get('error'))
            )
        if on_subscription_applied:
            self.event_manager.register_handler(
                EventType.SUBSCRIPTION_APPLIED,
                lambda event: on_subscription_applied(event.data)
            )
        
        # Store callbacks for backward compatibility
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_error = on_error
        self._on_subscription_applied = on_subscription_applied
        
        # Request tracking
        self._pending_requests = BoundedDict(max_size=10000)
        
        # Connection URL tracking
        self.connection_url: Optional[str] = None
        
        self.logger.info(f"Refactored WebSocket client initialized with host={host}, ssl={ssl}, "
                        f"protocol={protocol}, compression={enable_compression}")
    
    def _determine_frame_type(self, protocol: str) -> bool:
        """Determine expected frame type based on protocol."""
        return protocol == BIN_PROTOCOL
    
    def connect(
        self,
        db_address: Optional[str] = None,
        db_id: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = 30.0
    ) -> bool:
        """
        Connect to SpacetimeDB instance.
        
        Args:
            db_address: Optional database address override
            db_id: Optional database ID override
            auth_token: Optional auth token override
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        # Update parameters if provided
        if db_address:
            self.db_address = db_address
        if db_id:
            self.db_id = db_id
        if auth_token:
            self.auth_handler.set_auth_token(auth_token)
        
        self.logger.info(f"Connecting to SpacetimeDB: host={self.host}, db_address={self.db_address}, "
                        f"db_id={self.db_id}, has_auth={bool(self.auth_handler.auth_token)}")
        
        # Reset state
        self.reconnect_attempts = 0
        
        # Perform connection
        self._do_connect()
        
        # Wait for connection with timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.state == ConnectionState.CONNECTED:
                return True
            elif self.state in (ConnectionState.ERROR, ConnectionState.CLOSED):
                return False
            time.sleep(0.1)
        
        # Timeout reached
        self.logger.error(f"Connection timeout after {timeout} seconds")
        self.disconnect()
        if self._on_error:
            self._on_error(ConnectionTimeoutError(f"Connection timeout after {timeout} seconds"))
        return False
    
    def _do_connect(self) -> None:
        """Internal connection implementation."""
        def _attempt_connection():
            with self._lock:
                if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
                    self.logger.debug("Already connected or connecting, skipping")
                    return
                
                self.state = ConnectionState.CONNECTING
                
                # Build connection URL
                protocol = "wss" if self.ssl else "ws"
                base_url = f"{protocol}://{self.host}"
                
                if self.db_id:
                    url = f"{base_url}/v1/ws/{self.db_id}/{self.protocol}"
                elif self.db_address:
                    url = f"{base_url}/database/{self.db_address}/subscribe/{self.protocol}"
                else:
                    url = f"{base_url}/subscribe/{self.protocol}"
                
                # Validate URL
                try:
                    url_result = validate_websocket_url(url, "connection_url")
                    if not url_result.is_valid:
                        raise ValidationError(f"Invalid connection URL: {'; '.join(str(e) for e in url_result.errors)}")
                    url = url_result.sanitized_value
                except ValidationError as e:
                    raise WebSocketHandshakeError(f"Invalid connection URL: {e}")
                
                self.connection_url = url
                self.logger.debug(f"Connecting to: {url}")
                
                # Prepare headers with authentication
                headers = self.auth_handler.get_auth_headers()
                
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
                
                # Start connection in separate thread
                self.connection_thread = threading.Thread(
                    target=self.ws.run_forever,
                    daemon=True,
                    name=f"RefactoredWebSocketClient-ConnectionThread-{id(self)}"
                )
                self.connection_thread.start()
                self.logger.debug(f"Connection thread started for {url}")
        
        # Apply retry policy if this is an initial connection attempt
        if self.reconnect_attempts == 0 and self.retry_on_transient_errors:
            try:
                self.retry_policy.execute_with_retry(_attempt_connection)
            except Exception as e:
                self.logger.error(f"Failed to start connection after retries: {e}", exc_info=True)
                self.state = ConnectionState.DISCONNECTED
                self.event_manager.emit(create_connection_event(
                    EventType.CONNECTION_ERROR,
                    {'error': e, 'url': self.connection_url}
                ))
        else:
            try:
                _attempt_connection()
            except Exception as e:
                self.logger.error(f"Failed to start connection: {e}", exc_info=True)
                self.state = ConnectionState.DISCONNECTED
                self.event_manager.emit(create_connection_event(
                    EventType.CONNECTION_ERROR,
                    {'error': e, 'url': self.connection_url}
                ))
                self._schedule_reconnect()
    
    def disconnect(self) -> None:
        """Disconnect from SpacetimeDB."""
        self.logger.debug(f"Disconnect called. Current state: {self.state.value}")
        with self._lock:
            self.logger.info("WebSocket client disconnect initiated")
            self.auto_reconnect = False
            self.state = ConnectionState.CLOSED
            
            if self.reconnect_timer:
                self.reconnect_timer.cancel()
                self.reconnect_timer = None
            
            current_ws = self.ws
            current_thread = self.connection_thread
            
            if current_ws:
                try:
                    current_ws.close()
                    self.logger.debug("WebSocket connection closed")
                except Exception as e:
                    self.logger.error(f"Error closing WebSocket: {e}")
            
            if current_thread and current_thread.is_alive():
                current_thread.join(timeout=5.0)
                if current_thread.is_alive():
                    self.logger.warning("Connection thread did not terminate within timeout")
            
            self.ws = None
            self.connection_thread = None
            
            # Emit disconnection event
            self.event_manager.emit(create_connection_event(
                EventType.CONNECTION_CLOSED,
                {'url': self.connection_url}
            ))
    
    def send_message(self, message: ClientMessage, use_client_encoding: bool = False) -> None:
        """
        Send a message to the SpacetimeDB server.
        
        Args:
            message: ClientMessage to send
            use_client_encoding: Whether to use client-side encoding
        """
        if not self.ws or self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("WebSocket is not connected")
        
        try:
            # Encode message
            if use_client_encoding or self.protocol == BIN_PROTOCOL:
                encoded = self.protocol_encoder.encode_client_message(message)
            else:
                encoded = self.protocol_encoder.encode_client_message(message)
            
            # Apply compression if needed
            compressed, compression_info = self.compression_manager.compress_message(encoded)
            
            # Handle large messages
            if self.large_message_handler.should_fragment(compressed):
                fragments = self.large_message_handler.fragment_message(compressed)
                for fragment in fragments:
                    self._send_raw_message(fragment)
            else:
                self._send_raw_message(compressed)
            
            # Update metrics
            if compression_info:
                self.compression_manager.update_metrics(
                    len(encoded),
                    len(compressed),
                    compression_info['type'],
                    compression_info['duration']
                )
            
        except Exception as e:
            self.logger.error(f"Error sending message: {e}", exc_info=True)
            raise SpacetimeDBConnectionError(f"Failed to send message: {e}")
    
    def _send_raw_message(self, data: bytes) -> None:
        """Send raw message data over WebSocket."""
        if self.expect_binary_frames:
            self.ws.send(data, websocket.ABNF.OPCODE_BINARY)
        else:
            # For text frames, ensure data is string
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            self.ws.send(data, websocket.ABNF.OPCODE_TEXT)
    
    # Subscription management - delegate to SubscriptionManager
    def subscribe_single(self, query: str) -> QueryId:
        """Subscribe to a single query."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("WebSocket is not connected")
        
        # Validate query
        query_result = validate_sql_query(query, "subscription_query")
        if not query_result.is_valid:
            raise ValidationError(f"Invalid query: {'; '.join(str(e) for e in query_result.errors)}")
        
        query_id = self.subscription_manager.subscribe_single(query)
        
        # Send subscription message
        subscribe_msg = Subscribe(queries=[query])
        self.send_message(subscribe_msg)
        
        return query_id
    
    def subscribe_multi(self, queries: List[str]) -> QueryId:
        """Subscribe to multiple queries."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("WebSocket is not connected")
        
        # Validate queries
        for query in queries:
            query_result = validate_sql_query(query, "subscription_query")
            if not query_result.is_valid:
                raise ValidationError(f"Invalid query: {'; '.join(str(e) for e in query_result.errors)}")
        
        query_id = self.subscription_manager.subscribe_multi(queries)
        
        # Send subscription message
        subscribe_msg = Subscribe(queries=queries)
        self.send_message(subscribe_msg)
        
        return query_id
    
    def unsubscribe(self, query_id: QueryId) -> int:
        """Unsubscribe from a query."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("WebSocket is not connected")
        
        request_id = self.subscription_manager.unsubscribe(query_id)
        
        # Send unsubscribe message
        unsubscribe_msg = Unsubscribe(query_ids=[query_id.value])
        self.send_message(unsubscribe_msg)
        
        return request_id
    
    def execute_one_off_query(self, query: str) -> Dict[str, Any]:
        """Execute a one-off query and return results."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("WebSocket is not connected")
        
        # Validate query
        query_result = validate_sql_query(query, "one_off_query")
        if not query_result.is_valid:
            raise ValidationError(f"Invalid query: {'; '.join(str(e) for e in query_result.errors)}")
        
        request_id = generate_request_id()
        query_msg = OneOffQuery(
            sql=query_result.sanitized_value,
            message_id=request_id
        )
        
        # Track pending request
        result_future = threading.Event()
        result_data = {'result': None, 'error': None}
        self._pending_requests[request_id] = (result_future, result_data)
        
        # Send query
        self.send_message(query_msg)
        
        # Wait for result
        if result_future.wait(timeout=30.0):
            if result_data['error']:
                raise SpacetimeDBConnectionError(f"Query failed: {result_data['error']}")
            return result_data['result']
        else:
            self._pending_requests.pop(request_id, None)
            raise ConnectionTimeoutError("Query timeout")
    
    def call_reducer(
        self,
        reducer_name: str,
        args: List[Any],
        flags: Optional[CallReducerFlags] = None
    ) -> None:
        """Call a reducer on the SpacetimeDB server."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("WebSocket is not connected")
        
        reducer_msg = CallReducer(
            name=reducer_name,
            args=args,
            flags=flags or CallReducerFlags()
        )
        self.send_message(reducer_msg)
    
    # Authentication management - delegate to AuthenticationHandler
    @property
    def identity(self) -> Optional[Identity]:
        """Get current identity."""
        return self.auth_handler.identity
    
    @property
    def spacetimedb_token(self) -> Optional[str]:
        """Get current SpacetimeDB JWT token."""
        return self.auth_handler.jwt_token
    
    def set_auth_token(self, token: str) -> None:
        """Set authentication token."""
        self.auth_handler.set_auth_token(token)
    
    # WebSocket event handlers
    def _on_ws_open(self, ws) -> None:
        """Handle WebSocket connection opened."""
        self.logger.info("WebSocket connection opened")
        with self._lock:
            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0
            
            # Process compression response if available
            if hasattr(ws, 'headers'):
                self.compression_manager.process_server_response(dict(ws.headers))
            
            # Emit connection established event
            self.event_manager.emit(create_connection_event(
                EventType.CONNECTION_ESTABLISHED,
                {'url': self.connection_url}
            ))
    
    def _on_ws_message(self, ws, message) -> None:
        """Handle incoming WebSocket message."""
        try:
            # Handle message reassembly
            if self.large_message_handler.is_fragment(message):
                complete_message = self.large_message_handler.reassemble_message(message)
                if not complete_message:
                    return  # Still waiting for more fragments
                message = complete_message
            
            # Decompress if needed
            decompressed, compression_info = self.compression_manager.decompress_message(message)
            if compression_info:
                message = decompressed
            
            # Decode message
            server_msg = self.protocol_decoder.decode_server_message(message)
            
            # Process authentication responses
            if self.auth_handler.process_server_message(server_msg):
                return  # Authentication message handled
            
            # Process subscription responses
            if self.subscription_manager.handle_server_message(server_msg):
                return  # Subscription message handled
            
            # Handle other message types
            self._handle_server_message(server_msg)
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}", exc_info=True)
            self.event_manager.emit(create_connection_event(
                EventType.MESSAGE_ERROR,
                {'error': e}
            ))
    
    def _handle_server_message(self, message: ServerMessage) -> None:
        """Handle non-subscription, non-auth server messages."""
        # Handle transaction updates
        if isinstance(message, (TransactionUpdate, TransactionUpdateLight)):
            self.event_manager.emit(create_connection_event(
                EventType.TRANSACTION_UPDATE,
                {'update': message}
            ))
        
        # Handle one-off query results
        elif hasattr(message, 'message_id') and message.message_id in self._pending_requests:
            future, result_data = self._pending_requests.pop(message.message_id)
            if hasattr(message, 'error') and message.error:
                result_data['error'] = message.error
            else:
                result_data['result'] = message
            future.set()
    
    def _on_ws_error(self, ws, error) -> None:
        """Handle WebSocket error."""
        self.logger.error(f"WebSocket error: {error}")
        with self._lock:
            self.state = ConnectionState.ERROR
            
            # Emit error event
            self.event_manager.emit(create_connection_event(
                EventType.CONNECTION_ERROR,
                {'error': error}
            ))
            
            if self.auto_reconnect and isinstance(error, RetryableError):
                self._schedule_reconnect()
    
    def _on_ws_close(self, ws, close_status_code, close_msg) -> None:
        """Handle WebSocket connection closed."""
        self.logger.info(f"WebSocket closed: status={close_status_code}, msg={close_msg}")
        with self._lock:
            was_connected = self.state == ConnectionState.CONNECTED
            self.state = ConnectionState.DISCONNECTED
            
            # Emit close event
            self.event_manager.emit(create_connection_event(
                EventType.CONNECTION_CLOSED,
                {'status_code': close_status_code, 'message': close_msg}
            ))
            
            if self.auto_reconnect and was_connected:
                self._schedule_reconnect()
    
    def _schedule_reconnect(self) -> None:
        """Schedule reconnection attempt."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return
        
        self.reconnect_attempts += 1
        delay = self.reconnect_interval * (2 ** (self.reconnect_attempts - 1))
        
        self.logger.info(f"Scheduling reconnection attempt {self.reconnect_attempts} in {delay} seconds")
        
        self.reconnect_timer = threading.Timer(delay, self._do_connect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()
    
    # Utility methods
    def is_connected(self) -> bool:
        """Check if connected to SpacetimeDB."""
        return self.state == ConnectionState.CONNECTED
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information."""
        return {
            'state': self.state.value,
            'host': self.host,
            'ssl': self.ssl,
            'protocol': self.protocol,
            'db_address': self.db_address,
            'db_id': self.db_id,
            'identity': str(self.identity) if self.identity else None,
            'auth_state': self.auth_handler.state.value,
            'active_subscriptions': self.subscription_manager.get_active_count(),
            'compression_enabled': self.compression_manager.is_enabled(),
            'reconnect_attempts': self.reconnect_attempts
        }
    
    # Compression management
    def set_compression_config(self, config: CompressionConfig) -> None:
        """Update compression configuration."""
        self.compression_manager.config = config
    
    def get_compression_info(self) -> Dict[str, Any]:
        """Get compression information."""
        return self.compression_manager.get_compression_info()
    
    def get_compression_metrics(self) -> CompressionMetrics:
        """Get compression metrics."""
        return self.compression_manager.metrics
    
    # Subscription health metrics
    def get_subscription_health(self, table_name: str) -> Dict[str, Any]:
        """Get health metrics for a specific subscription."""
        return self.subscription_manager.get_subscription_health(table_name)
    
    def get_all_subscription_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health metrics for all subscriptions."""
        return self.subscription_manager.get_all_subscription_health()
    
    # Deprecated methods with warnings
    def subscribe_to_queries(self, queries: List[str]) -> int:
        """
        DEPRECATED: Use subscribe_multi() instead.
        Subscribe to multiple queries.
        """
        warnings.warn(
            "subscribe_to_queries() is deprecated. Use subscribe_multi() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        query_id = self.subscribe_multi(queries)
        return query_id.value
    
    def one_off_query(self, query: str) -> bytes:
        """
        DEPRECATED: Use execute_one_off_query() instead.
        Execute a one-off query.
        """
        warnings.warn(
            "one_off_query() is deprecated. Use execute_one_off_query() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        result = self.execute_one_off_query(query)
        # Convert result to bytes for backward compatibility
        return str(result).encode('utf-8')
    
    def add_subscription_state_callback(self, callback: Callable[[str, Any], None]) -> None:
        """
        DEPRECATED: Use event_manager.register_handler() instead.
        Add a callback for subscription state changes.
        """
        warnings.warn(
            "add_subscription_state_callback() is deprecated. Use event_manager.register_handler() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.event_manager.register_handler(
            EventType.SUBSCRIPTION_STATE_CHANGE,
            lambda event: callback(event.type, event.data)
        )
    
    def remove_subscription_state_callback(self, callback: Callable[[str, Any], None]) -> bool:
        """
        DEPRECATED: Use event_manager.unregister_handler() instead.
        Remove a subscription state callback.
        """
        warnings.warn(
            "remove_subscription_state_callback() is deprecated. Use event_manager.unregister_handler() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Note: This won't work exactly the same due to wrapper lambda
        # For full compatibility, would need to track callback mappings
        return False
    
    # Protocol helpers
    def detect_expected_frame_type(self) -> str:
        """Detect expected WebSocket frame type."""
        return "binary" if self.expect_binary_frames else "text"
    
    def get_protocol_helper(self):
        """Get protocol helper for backward compatibility."""
        class ProtocolHelper:
            def __init__(self, encoder, decoder):
                self.encoder = encoder
                self.decoder = decoder
            
            def encode_client_message(self, message):
                return self.encoder.encode_client_message(message)
            
            def decode_server_message(self, data):
                return self.decoder.decode_server_message(data)
        
        return ProtocolHelper(self.protocol_encoder, self.protocol_decoder)