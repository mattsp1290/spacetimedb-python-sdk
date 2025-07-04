"""
Compact refactored WebSocket client for SpacetimeDB protocol v1.1.1
Maintains 100% API compatibility while using modular components.
"""

import websocket
import threading
import time
import logging
from typing import Optional, Callable, Dict, List, Any, Union
from enum import Enum
import warnings

from .exceptions import *
from .connection_diagnostics import ConnectionDiagnostics
from .retry_policies import RetryPolicy, RetryPolicyPresets
from .protocol import *
from .query_id import QueryId
from .compression import *
from .large_message_handler import LargeMessageHandler
from .memory_management import *
from .validation import *

# Import extracted modules
from .connection.subscription_manager import SubscriptionManager
from .connection.authentication_handler import AuthenticationHandler
from .events import UnifiedEventManager, EventType, create_connection_event


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSED = "closed"
    ERROR = "error"


class ModernWebSocketClient:
    """Compact refactored WebSocket client using modular architecture."""
    
    def __init__(
        self, host="127.0.0.1:3000", ssl=False, auth_token=None, db_address=None,
        db_id=None, auto_reconnect=True, reconnect_interval=5.0, max_reconnect_attempts=10,
        enable_compression=True, compression_config=None, on_connect=None, on_disconnect=None,
        on_error=None, on_subscription_applied=None, retry_on_transient_errors=True,
        retry_policy=None, protocol=BIN_PROTOCOL, expect_binary_frames=None,
        enable_diagnostics=False, enable_subscription_metrics=True, memory_limit_mb=None
    ):
        self.logger = logging.getLogger(__name__)
        
        # Core settings
        self.host, self.ssl, self.db_address, self.db_id = host, ssl, db_address, db_id
        self.protocol = protocol
        self.state = ConnectionState.DISCONNECTED
        self._lock = threading.RLock()
        self.ws = None
        self.connection_thread = None
        
        # Initialize modules
        self.event_manager = UnifiedEventManager(enable_metrics=True)
        self.subscription_manager = SubscriptionManager(self.event_manager, enable_subscription_metrics, memory_limit_mb)
        self.auth_handler = AuthenticationHandler(auth_token, self.event_manager)
        self.compression_manager = CompressionManager(compression_config or CompressionConfig(enabled=enable_compression))
        self.large_message_handler = LargeMessageHandler()
        
        # Protocol handling
        self.protocol_encoder = ProtocolEncoder(protocol=protocol)
        self.protocol_decoder = ProtocolDecoder(protocol=protocol)
        self.expect_binary_frames = expect_binary_frames or (protocol == BIN_PROTOCOL)
        
        # Reconnection settings
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_attempts = 0
        self.reconnect_timer = None
        self.retry_on_transient_errors = retry_on_transient_errors
        self.retry_policy = retry_policy or RetryPolicyPresets.default()
        
        # Diagnostics & memory
        self.diagnostics = ConnectionDiagnostics() if enable_diagnostics else None
        self.memory_accountant = get_global_memory_accountant()
        if memory_limit_mb:
            self.memory_accountant.set_memory_limit(memory_limit_mb * 1024 * 1024)
        
        # Register callbacks
        self._register_legacy_callbacks(on_connect, on_disconnect, on_error, on_subscription_applied)
        
        # State tracking
        self._pending_requests = BoundedDict(max_size=10000)
        self.connection_url = None
    
    def _register_legacy_callbacks(self, on_connect, on_disconnect, on_error, on_subscription_applied):
        """Register legacy callbacks with event system."""
        if on_connect:
            self.event_manager.register_handler(EventType.CONNECTION_ESTABLISHED, lambda e: on_connect())
        if on_disconnect:
            self.event_manager.register_handler(EventType.CONNECTION_CLOSED, lambda e: on_disconnect())
        if on_error:
            self.event_manager.register_handler(EventType.CONNECTION_ERROR, lambda e: on_error(e.data.get('error')))
        if on_subscription_applied:
            self.event_manager.register_handler(EventType.SUBSCRIPTION_APPLIED, lambda e: on_subscription_applied(e.data))
        
        # Store for compatibility
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_error = on_error
        self._on_subscription_applied = on_subscription_applied
    
    def connect(self, db_address=None, db_id=None, auth_token=None, timeout=30.0):
        """Connect to SpacetimeDB instance."""
        if db_address: self.db_address = db_address
        if db_id: self.db_id = db_id
        if auth_token: self.auth_handler.set_auth_token(auth_token)
        
        self.reconnect_attempts = 0
        self._do_connect()
        
        # Wait for connection
        start = time.time()
        while time.time() - start < timeout:
            if self.state == ConnectionState.CONNECTED: return True
            if self.state in (ConnectionState.ERROR, ConnectionState.CLOSED): return False
            time.sleep(0.1)
        
        self.disconnect()
        if self._on_error:
            self._on_error(ConnectionTimeoutError(f"Timeout after {timeout}s"))
        return False
    
    def _do_connect(self):
        """Internal connection implementation."""
        def attempt():
            with self._lock:
                if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
                    return
                
                self.state = ConnectionState.CONNECTING
                
                # Build URL
                proto = "wss" if self.ssl else "ws"
                base = f"{proto}://{self.host}"
                if self.db_id:
                    url = f"{base}/v1/ws/{self.db_id}/{self.protocol}"
                elif self.db_address:
                    url = f"{base}/database/{self.db_address}/subscribe/{self.protocol}"
                else:
                    url = f"{base}/subscribe/{self.protocol}"
                
                # Validate URL
                url_result = validate_websocket_url(url, "connection_url")
                if not url_result.is_valid:
                    raise WebSocketHandshakeError(f"Invalid URL: {'; '.join(str(e) for e in url_result.errors)}")
                url = url_result.sanitized_value
                self.connection_url = url
                
                # Create WebSocket
                headers = self.auth_handler.get_auth_headers()
                headers.update(self.compression_manager.create_compression_headers())
                
                self.ws = websocket.WebSocketApp(
                    url, on_open=self._on_ws_open, on_message=self._on_ws_message,
                    on_error=self._on_ws_error, on_close=self._on_ws_close,
                    header=headers, subprotocols=[self.protocol]
                )
                
                self.connection_thread = threading.Thread(
                    target=self.ws.run_forever, daemon=True,
                    name=f"WSClient-{id(self)}"
                )
                self.connection_thread.start()
        
        # Apply retry policy
        try:
            if self.reconnect_attempts == 0 and self.retry_on_transient_errors:
                self.retry_policy.execute_with_retry(attempt)
            else:
                attempt()
        except Exception as e:
            self.logger.error(f"Connection failed: {e}", exc_info=True)
            self.state = ConnectionState.DISCONNECTED
            self.event_manager.emit(create_connection_event(EventType.CONNECTION_ERROR, {'error': e}))
            if self.reconnect_attempts > 0:
                self._schedule_reconnect()
    
    def disconnect(self):
        """Disconnect from SpacetimeDB."""
        with self._lock:
            self.auto_reconnect = False
            self.state = ConnectionState.CLOSED
            
            if self.reconnect_timer:
                self.reconnect_timer.cancel()
                self.reconnect_timer = None
            
            if self.ws:
                try: self.ws.close()
                except: pass
            
            if self.connection_thread and self.connection_thread.is_alive():
                self.connection_thread.join(timeout=5.0)
            
            self.ws = None
            self.connection_thread = None
            self.event_manager.emit(create_connection_event(EventType.CONNECTION_CLOSED, {}))
    
    def send_message(self, message: ClientMessage, use_client_encoding=False):
        """Send a message to the server."""
        if not self.ws or self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("Not connected")
        
        # Encode and compress
        encoded = self.protocol_encoder.encode_client_message(message)
        compressed, info = self.compression_manager.compress_message(encoded)
        
        # Handle large messages
        if self.large_message_handler.should_fragment(compressed):
            for fragment in self.large_message_handler.fragment_message(compressed):
                self._send_raw(fragment)
        else:
            self._send_raw(compressed)
        
        if info:
            self.compression_manager.update_metrics(len(encoded), len(compressed), info['type'], info['duration'])
    
    def _send_raw(self, data):
        """Send raw data over WebSocket."""
        if self.expect_binary_frames:
            self.ws.send(data, websocket.ABNF.OPCODE_BINARY)
        else:
            self.ws.send(data.decode('utf-8') if isinstance(data, bytes) else data, websocket.ABNF.OPCODE_TEXT)
    
    # Subscription operations
    def subscribe_single(self, query):
        """Subscribe to a single query."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("Not connected")
        
        query_result = validate_sql_query(query, "subscription_query")
        if not query_result.is_valid:
            raise ValidationError(f"Invalid query: {'; '.join(str(e) for e in query_result.errors)}")
        
        query_id = self.subscription_manager.subscribe_single(query)
        self.send_message(Subscribe(queries=[query]))
        return query_id
    
    def subscribe_multi(self, queries):
        """Subscribe to multiple queries."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("Not connected")
        
        for q in queries:
            query_result = validate_sql_query(q, "subscription_query")
            if not query_result.is_valid:
                raise ValidationError(f"Invalid query: {'; '.join(str(e) for e in query_result.errors)}")
        
        query_id = self.subscription_manager.subscribe_multi(queries)
        self.send_message(Subscribe(queries=queries))
        return query_id
    
    def unsubscribe(self, query_id):
        """Unsubscribe from a query."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("Not connected")
        
        request_id = self.subscription_manager.unsubscribe(query_id)
        self.send_message(Unsubscribe(query_ids=[query_id.value]))
        return request_id
    
    def execute_one_off_query(self, query):
        """Execute a one-off query."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("Not connected")
        
        query_result = validate_sql_query(query, "one_off_query")
        if not query_result.is_valid:
            raise ValidationError(f"Invalid query: {'; '.join(str(e) for e in query_result.errors)}")
        
        request_id = generate_request_id()
        query_msg = OneOffQuery(sql=query_result.sanitized_value, message_id=request_id)
        
        result_future = threading.Event()
        result_data = {'result': None, 'error': None}
        self._pending_requests[request_id] = (result_future, result_data)
        
        self.send_message(query_msg)
        
        if result_future.wait(timeout=30.0):
            if result_data['error']:
                raise SpacetimeDBConnectionError(f"Query failed: {result_data['error']}")
            return result_data['result']
        else:
            self._pending_requests.pop(request_id, None)
            raise ConnectionTimeoutError("Query timeout")
    
    def call_reducer(self, reducer_name, args, flags=None):
        """Call a reducer on the server."""
        if self.state != ConnectionState.CONNECTED:
            raise SpacetimeDBConnectionError("Not connected")
        
        self.send_message(CallReducer(name=reducer_name, args=args, flags=flags or CallReducerFlags()))
    
    # Auth properties
    @property
    def identity(self): return self.auth_handler.identity
    
    @property
    def spacetimedb_token(self): return self.auth_handler.jwt_token
    
    def set_auth_token(self, token): self.auth_handler.set_auth_token(token)
    
    # WebSocket handlers
    def _on_ws_open(self, ws):
        """Handle connection opened."""
        with self._lock:
            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0
            if hasattr(ws, 'headers'):
                self.compression_manager.process_server_response(dict(ws.headers))
            self.event_manager.emit(create_connection_event(EventType.CONNECTION_ESTABLISHED, {'url': self.connection_url}))
    
    def _on_ws_message(self, ws, message):
        """Handle incoming message."""
        try:
            # Reassemble fragments
            if self.large_message_handler.is_fragment(message):
                message = self.large_message_handler.reassemble_message(message)
                if not message: return
            
            # Decompress
            decompressed, info = self.compression_manager.decompress_message(message)
            if info: message = decompressed
            
            # Decode
            server_msg = self.protocol_decoder.decode_server_message(message)
            
            # Process
            if self.auth_handler.process_server_message(server_msg): return
            if self.subscription_manager.handle_server_message(server_msg): return
            self._handle_server_message(server_msg)
            
        except Exception as e:
            self.logger.error(f"Message error: {e}", exc_info=True)
            self.event_manager.emit(create_connection_event(EventType.MESSAGE_ERROR, {'error': e}))
    
    def _handle_server_message(self, msg):
        """Handle other server messages."""
        if isinstance(msg, (TransactionUpdate, TransactionUpdateLight)):
            self.event_manager.emit(create_connection_event(EventType.TRANSACTION_UPDATE, {'update': msg}))
        elif hasattr(msg, 'message_id') and msg.message_id in self._pending_requests:
            future, result = self._pending_requests.pop(msg.message_id)
            if hasattr(msg, 'error') and msg.error:
                result['error'] = msg.error
            else:
                result['result'] = msg
            future.set()
    
    def _on_ws_error(self, ws, error):
        """Handle connection error."""
        with self._lock:
            self.state = ConnectionState.ERROR
            self.event_manager.emit(create_connection_event(EventType.CONNECTION_ERROR, {'error': error}))
            if self.auto_reconnect and isinstance(error, RetryableError):
                self._schedule_reconnect()
    
    def _on_ws_close(self, ws, code, msg):
        """Handle connection closed."""
        with self._lock:
            was_connected = self.state == ConnectionState.CONNECTED
            self.state = ConnectionState.DISCONNECTED
            self.event_manager.emit(create_connection_event(EventType.CONNECTION_CLOSED, {'code': code, 'msg': msg}))
            if self.auto_reconnect and was_connected:
                self._schedule_reconnect()
    
    def _schedule_reconnect(self):
        """Schedule reconnection attempt."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error(f"Max reconnect attempts reached")
            return
        
        self.reconnect_attempts += 1
        delay = self.reconnect_interval * (2 ** (self.reconnect_attempts - 1))
        
        self.reconnect_timer = threading.Timer(delay, self._do_connect)
        self.reconnect_timer.daemon = True
        self.reconnect_timer.start()
    
    # Utility methods
    def is_connected(self): return self.state == ConnectionState.CONNECTED
    
    def get_connection_info(self):
        return {
            'state': self.state.value, 'host': self.host, 'ssl': self.ssl,
            'protocol': self.protocol, 'db_address': self.db_address, 'db_id': self.db_id,
            'identity': str(self.identity) if self.identity else None,
            'auth_state': self.auth_handler.state.value,
            'active_subscriptions': self.subscription_manager.get_active_count(),
            'compression_enabled': self.compression_manager.is_enabled(),
            'reconnect_attempts': self.reconnect_attempts
        }
    
    # Compression management
    def set_compression_config(self, config): self.compression_manager.config = config
    def get_compression_info(self): return self.compression_manager.get_compression_info()
    def get_compression_metrics(self): return self.compression_manager.metrics
    
    # Subscription metrics
    def get_subscription_health(self, table_name): return self.subscription_manager.get_subscription_health(table_name)
    def get_all_subscription_health(self): return self.subscription_manager.get_all_subscription_health()
    
    # Deprecated methods
    def subscribe_to_queries(self, queries):
        warnings.warn("subscribe_to_queries() is deprecated. Use subscribe_multi().", DeprecationWarning, stacklevel=2)
        return self.subscribe_multi(queries).value
    
    def one_off_query(self, query):
        warnings.warn("one_off_query() is deprecated. Use execute_one_off_query().", DeprecationWarning, stacklevel=2)
        return str(self.execute_one_off_query(query)).encode('utf-8')
    
    def add_subscription_state_callback(self, callback):
        warnings.warn("add_subscription_state_callback() is deprecated. Use event_manager.register_handler().", DeprecationWarning, stacklevel=2)
        self.event_manager.register_handler(EventType.SUBSCRIPTION_STATE_CHANGE, lambda e: callback(e.type, e.data))
    
    def remove_subscription_state_callback(self, callback):
        warnings.warn("remove_subscription_state_callback() is deprecated.", DeprecationWarning, stacklevel=2)
        return False
    
    # Protocol helpers
    def detect_expected_frame_type(self): return "binary" if self.expect_binary_frames else "text"
    
    def get_protocol_helper(self):
        class Helper:
            def __init__(self, enc, dec): self.encoder, self.decoder = enc, dec
            def encode_client_message(self, msg): return self.encoder.encode_client_message(msg)
            def decode_server_message(self, data): return self.decoder.decode_server_message(data)
        return Helper(self.protocol_encoder, self.protocol_decoder)