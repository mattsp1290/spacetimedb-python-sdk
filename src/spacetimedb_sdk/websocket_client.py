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
from typing import Optional, Callable, Dict, List, Any, Union
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
    RetryableError,
    SpacetimeDBAuthHandshakeError
)
from .auth_storage import AuthCredentials, get_credentials, store_credentials
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


class SubscriptionMetrics:
    """Track subscription health and performance metrics."""
    
    def __init__(self):
        self.subscriptions: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
    
    def record_subscription_data(self, table_name: str, size: int) -> None:
        """Record data received for a subscription."""
        if table_name not in self.subscriptions:
            self.subscriptions[table_name] = {
                'message_count': 0,
                'total_bytes': 0,
                'last_received': None,
                'first_received': time.time(),
                'error_count': 0
            }
        
        stats = self.subscriptions[table_name]
        stats['message_count'] += 1
        stats['total_bytes'] += size
        stats['last_received'] = time.time()
    
    def record_subscription_error(self, table_name: str, error: str) -> None:
        """Record an error for a subscription."""
        if table_name not in self.subscriptions:
            self.subscriptions[table_name] = {
                'message_count': 0,
                'total_bytes': 0,
                'last_received': None,
                'first_received': time.time(),
                'error_count': 0
            }
        
        self.subscriptions[table_name]['error_count'] += 1
        self.logger.warning(f"Subscription error for {table_name}: {error}")
    
    def get_subscription_health(self, table_name: str) -> Dict[str, Any]:
        """Get health metrics for a subscription."""
        if table_name not in self.subscriptions:
            return {'status': 'no_data'}
        
        stats = self.subscriptions[table_name]
        current_time = time.time()
        time_since_last = current_time - (stats['last_received'] or current_time)
        
        # Determine health status
        if time_since_last < 30:
            status = 'healthy'
        elif time_since_last < 60:
            status = 'warning'
        else:
            status = 'stale'
        
        # Consider error rate
        error_rate = stats['error_count'] / max(stats['message_count'], 1)
        if error_rate > 0.1:  # More than 10% errors
            status = 'unhealthy'
        
        return {
            'status': status,
            'message_count': stats['message_count'],
            'total_bytes': stats['total_bytes'],
            'seconds_since_last': time_since_last,
            'error_count': stats['error_count'],
            'error_rate': error_rate,
            'uptime_seconds': current_time - stats['first_received']
        }
    
    def get_all_subscription_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health metrics for all subscriptions."""
        return {
            table_name: self.get_subscription_health(table_name)
            for table_name in self.subscriptions.keys()
        }
    
    def reset_metrics(self) -> None:
        """Reset all subscription metrics."""
        self.subscriptions.clear()


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
        # Use the module-level logger
        self.logger = logger
        
        self.protocol = protocol
        self.use_binary = self._determine_frame_type(protocol)
        
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
        
        # SpacetimeDB JWT Authentication
        self.spacetimedb_identity: Optional[str] = None
        self.spacetimedb_token: Optional[str] = None
        self.auth_handshake_completed: bool = False
        self.retry_with_auth: bool = False
        
        # Identity and connection tracking
        self.identity: Optional[Identity] = None
        self.connection_id: Optional[ConnectionId] = None
        
        # Protocol handling
        self.encoder = ProtocolEncoder(use_binary=self.use_binary)
        self.decoder = ProtocolDecoder(use_binary=self.use_binary)
        
        # Compression support
        self.compression_manager = CompressionManager(compression_config)
        self.negotiated_compression: Optional[CompressionType] = None
        
        # Large message handling
        self.large_message_handler: Optional[LargeMessageHandler] = None
        
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
        
        # Memory management
        self.memory_accountant = get_global_memory_accountant()
        self.message_validator = MessageSizeValidator(memory_accountant=self.memory_accountant)
        
        # Subscription tracking with bounded storage
        self.active_subscriptions = BoundedDict[int, QueryId](
            max_size=1000,
            memory_accountant=self.memory_accountant
        )
        self.subscription_queries = BoundedDict[QueryId, List[str]](
            max_size=1000,
            memory_accountant=self.memory_accountant
        )
        
        # Request tracking with bounded storage
        self.pending_requests = BoundedDict[int, threading.Event](
            max_size=5000,
            memory_accountant=self.memory_accountant
        )
        self.request_responses = BoundedDict[int, Any](
            max_size=5000,
            memory_accountant=self.memory_accountant
        )
        
        # Subscription state coordination for client integration
        self.subscription_state_callbacks: List[Callable[[str, Any], None]] = []
        
        # Subscription health monitoring
        self.subscription_metrics = SubscriptionMetrics()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Logging setup (logger already initialized above)
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
    
    def _determine_frame_type(self, protocol: str) -> bool:
        """
        Determine the correct WebSocket frame type based on negotiated protocol.
        
        This method ensures that:
        - JSON protocols (v1.json.spacetimedb, text) use TEXT WebSocket frames
        - Binary protocols (v1.bsatn.spacetimedb, binary) use BINARY WebSocket frames
        
        Args:
            protocol: The negotiated protocol string
            
        Returns:
            True if binary frames should be used, False for text frames
        """
        # Check for binary protocols (BSATN)
        if 'bsatn' in protocol.lower() or protocol == 'binary':
            return True
        
        # Check for text protocols (JSON)
        elif 'json' in protocol.lower() or protocol == 'text':
            return False
        
        # Fallback check against protocol constants
        elif protocol == BIN_PROTOCOL:
            return True
        elif protocol == TEXT_PROTOCOL:
            return False
        
        # Default to text frames for unknown protocols (safer fallback)
        else:
            self.logger.warning(f"Unknown protocol '{protocol}', defaulting to text frames")
            return False
    
    def detect_expected_frame_type(self) -> str:
        """
        Detect expected WebSocket frame type from current protocol for debugging.
        
        Returns:
            'BINARY' or 'TEXT' indicating expected frame type
        """
        return 'BINARY' if self.use_binary else 'TEXT'
    
    def send_heartbeat(self) -> None:
        """
        Send a heartbeat message using valid SpacetimeDB protocol.
        
        This replaces invalid custom heartbeat messages with a proper OneOffQuery
        that serves as a connection keep-alive mechanism.
        """
        from .message_validator import create_heartbeat_message
        from .messages.one_off_query import OneOffQueryMessage
        import uuid
        
        # Create valid heartbeat using OneOffQuery
        heartbeat = OneOffQueryMessage(
            message_id=uuid.uuid4().bytes,
            query_string="SELECT 1",
        )
        
        self.logger.debug("Sending heartbeat via OneOffQuery")
        self.send_message(heartbeat)
    
    def get_protocol_helper(self):
        """
        Get the protocol helper for client-side encoding compatibility.
        
        Returns:
            Protocol encoder/decoder for use by client applications
        """
        return {
            'encoder': self.encoder,
            'decoder': self.decoder,
            'protocol': self.protocol,
            'use_binary': self.use_binary
        }
    
    def should_use_sdk_encoding(self, message: Union[str, bytes, dict]) -> bool:
        """
        Determine if SDK should encode the message or pass it through.
        
        Args:
            message: Message to check
            
        Returns:
            True if SDK should handle encoding, False to pass through
        """
        # If message is already encoded (string/bytes), pass through
        if isinstance(message, (str, bytes)):
            return False
            
        # If message has raw binary data, let SDK handle
        if isinstance(message, dict) and self._contains_binary_data(message):
            return True
            
        # For simple JSON messages, either can handle - default to SDK
        return True
    
    def _contains_binary_data(self, obj: Any, _recursion_limiter: Optional[RecursionLimiter] = None) -> bool:
        """Check if object contains binary data that needs special handling."""
        if _recursion_limiter is None:
            _recursion_limiter = RecursionLimiter(max_depth=50)
        
        with _recursion_limiter:
            if isinstance(obj, bytes):
                return True
            elif isinstance(obj, dict):
                return any(self._contains_binary_data(value, _recursion_limiter) for value in obj.values())
            elif isinstance(obj, (list, tuple)):
                return any(self._contains_binary_data(item, _recursion_limiter) for item in obj)
            return False
    
    def _send_client_encoded_message(self, message: Union[str, bytes]) -> None:
        """
        Send a pre-encoded message from client directly to WebSocket.
        
        Args:
            message: Pre-encoded message data
        """
        self.logger.debug(f"Sending client-encoded message: {len(str(message))} bytes")
        
        # Send directly with appropriate frame type
        if isinstance(message, str):
            # Text message - send as TEXT frame
            self.ws.send(message)
            self.logger.debug("Sent client-encoded message as TEXT frame")
        elif isinstance(message, bytes):
            # Binary message - send as BINARY frame  
            from websocket import ABNF
            self.ws.send(message, opcode=ABNF.OPCODE_BINARY)
            self.logger.debug("Sent client-encoded message as BINARY frame")
        else:
            raise ValueError(f"Client-encoded message must be str or bytes, got {type(message)}")
    
    def add_subscription_state_callback(self, callback: Callable[[str, Any], None]) -> None:
        """
        Add callback for subscription state changes.
        
        Allows client applications to track subscription lifecycle events.
        
        Args:
            callback: Function to call with (event_type, data) when subscription state changes
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self.subscription_state_callbacks.append(callback)
        self.logger.debug(f"Added subscription state callback, total: {len(self.subscription_state_callbacks)}")
    
    def remove_subscription_state_callback(self, callback: Callable[[str, Any], None]) -> bool:
        """
        Remove a subscription state callback.
        
        Args:
            callback: Callback to remove
            
        Returns:
            True if callback was found and removed
        """
        try:
            self.subscription_state_callbacks.remove(callback)
            self.logger.debug(f"Removed subscription state callback, remaining: {len(self.subscription_state_callbacks)}")
            return True
        except ValueError:
            return False
    
    async def _notify_subscription_state_change(self, event_type: str, data: Any) -> None:
        """
        Notify all registered callbacks of subscription state change.
        
        Args:
            event_type: Type of subscription event
            data: Event data
        """
        if not self.subscription_state_callbacks:
            return
        
        for callback in self.subscription_state_callbacks:
            try:
                # Support both sync and async callbacks
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data)
                else:
                    callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Error in subscription state callback: {e}")
    
    def connect(
        self,
        auth_token: Optional[str],
        host: str,
        database_address: str,
        ssl_enabled: bool = True,
        db_identity: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None
    ) -> None:
        """Connect to SpacetimeDB with JWT authentication support and preflight checks."""
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
            
            # Reset authentication state
            self.auth_handshake_completed = False
            self.retry_with_auth = False
            
            # Check for stored SpacetimeDB credentials
            stored_credentials = get_credentials(host, database_address)
            if stored_credentials and not stored_credentials.is_expired():
                self.logger.info(f"Found stored SpacetimeDB credentials for {host}/{database_address}")
                self.spacetimedb_identity = stored_credentials.identity
                self.spacetimedb_token = stored_credentials.token
                self.auth_handshake_completed = True
            else:
                # Clear any expired credentials
                self.spacetimedb_identity = None
                self.spacetimedb_token = None
            
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
            
            # Build WebSocket URL for v1.1.2 compatibility with security validation
            protocol_scheme = "wss" if self.ssl_enabled else "ws"
            
            # Validate and sanitize host
            try:
                import urllib.parse
                parsed_host = urllib.parse.urlparse(f"{protocol_scheme}://{self.host}")
                host = parsed_host.hostname
                port = parsed_host.port
                
                # Validate the extracted host
                if not host or not get_security_manager().validate_hostname(host):
                    raise ValidationError(f"Invalid host: {host}")
                
                # Reconstruct the validated host with port if available
                validated_host = f"{host}:{port}" if port else host
            except ValidationError as e:
                raise WebSocketHandshakeError(f"Invalid host: {e}")
            
            # Use db_identity in URL path if provided, otherwise use database_address
            db_identifier = self.db_identity if self.db_identity else self.database_address
            
            # Validate and sanitize database identifier
            try:
                security_manager = get_security_manager()
                # Use data size validator to check database identifier
                db_result = security_manager.size_validator.validate(db_identifier, "database_identifier")
                if not db_result.is_valid:
                    raise ValidationError(f"Invalid database identifier: {'; '.join(str(e) for e in db_result.errors)}")
                validated_db_identifier = db_result.sanitized_value
                
                # Additional validation: prevent path traversal
                if '../' in validated_db_identifier or '..\\' in validated_db_identifier:
                    raise ValidationError("Path traversal attempt in database identifier")
                
                # Sanitize for URL inclusion
                validated_db_identifier = urllib.parse.quote(validated_db_identifier, safe='')
                
            except ValidationError as e:
                raise WebSocketHandshakeError(f"Invalid database identifier: {e}")
            
            url = f"{protocol_scheme}://{validated_host}/v1/database/{validated_db_identifier}/subscribe"
            
            # Final URL validation
            try:
                url_result = validate_websocket_url(url, "connection_url")
                if not url_result.is_valid:
                    raise ValidationError(f"Invalid connection URL: {'; '.join(str(e) for e in url_result.errors)}")
                url = url_result.sanitized_value
            except ValidationError as e:
                raise WebSocketHandshakeError(f"Invalid connection URL: {e}")
            
            # Store URL for error diagnostics
            self.connection_url = url
            
            self.logger.debug(f"_do_connect: Set state to CONNECTING. URL: {url}")
            
            # Prepare headers
            headers = {}
            
            # SpacetimeDB JWT Authentication (takes precedence)
            if self.spacetimedb_token and self.auth_handshake_completed:
                self.logger.debug("Using stored SpacetimeDB JWT token for authentication")
                headers["Authorization"] = f"Bearer {self.spacetimedb_token}"
            # Legacy token-based auth
            elif self.auth_token:
                self.logger.debug("Using legacy token-based authentication")
                token_bytes = f"token:{self.auth_token}".encode('utf-8')
                base64_str = base64.b64encode(token_bytes).decode('utf-8')
                headers["Authorization"] = f"Basic {base64_str}"
            else:
                self.logger.debug("Connecting without authentication (will attempt handshake if required)")
            
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
            self.pending_requests.clear()
            self.request_responses.clear()
            self.negotiated_compression = None
            
            # Cleanup large message handler
            if self.large_message_handler:
                self.large_message_handler.shutdown()
                self.large_message_handler = None
            
            # Clear authentication state (but keep stored credentials for future use)
            # Note: We don't clear spacetimedb_identity and spacetimedb_token here
            # as they may be reused for reconnection
            self.retry_with_auth = False
            self.logger.info("WebSocket client disconnected and cleaned up.")
    
    def send_message(self, message: ClientMessage, use_client_encoding: bool = False) -> None:
        """
        Send a client message to the server with optional compression and proper serialization.
        
        Args:
            message: Message to send
            use_client_encoding: If True, skip SDK encoding and send message directly
        """
        if self.state != ConnectionState.CONNECTED or not self.ws:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        try:
            # Handle client-encoded messages (bypass SDK encoding)
            if use_client_encoding:
                return self._send_client_encoded_message(message)
            
            # Validate message conforms to SpacetimeDB protocol
            from .message_validator import SpacetimeDBMessageValidator, MessageValidationError
            try:
                SpacetimeDBMessageValidator.validate_message(message)
            except MessageValidationError as e:
                self.logger.error(f"Message validation failed: {e}")
                raise ValueError(f"Invalid SpacetimeDB message: {e}")
            
            # Import serialization functions
            from .serialization import prepare_message_for_client
            from .protocol_handler import get_default_handler
            
            # Prepare message with client compatibility (for any embedded objects)
            # This ensures any response objects are properly serialized
            if hasattr(message, '__dict__'):
                # For client messages, we typically don't need to serialize since
                # they're going TO the server, but we may have response objects embedded
                prepared_message = message
            else:
                prepared_message = message
            
            # Encode the message
            encoded_data = self.encoder.encode_client_message(prepared_message)
            
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
            
            # Send the message with large message handling support
            message_type = type(message).__name__
            
            # Use large message handler if available and message is potentially large
            if self.large_message_handler and len(encoded_data) > 1024:  # 1KB threshold for checking
                self.large_message_handler.send_large_message(
                    encoded_data, 
                    message_type=message_type
                )
            else:
                # Send normally with correct frame type based on negotiated protocol
                expected_frame_type = self.detect_expected_frame_type()
                
                if self.use_binary:
                    # Binary protocol → BINARY WebSocket frame
                    from websocket import ABNF
                    self.ws.send(encoded_data, opcode=ABNF.OPCODE_BINARY)
                    self.logger.debug(
                        f"Sent {message_type} as BINARY frame "
                        f"(protocol: {self.protocol}, {len(encoded_data)} bytes)"
                    )
                else:
                    # JSON protocol → TEXT WebSocket frame
                    self.ws.send(encoded_data)  # Default opcode is TEXT
                    self.logger.debug(
                        f"Sent {message_type} as TEXT frame "
                        f"(protocol: {self.protocol}, {len(encoded_data)} bytes)"
                    )
                
                # Log protocol consistency check for debugging
                if 'bsatn' in self.protocol.lower() and not self.use_binary:
                    self.logger.warning(
                        f"Protocol mismatch warning: protocol '{self.protocol}' suggests binary "
                        f"but sending as {expected_frame_type} frame"
                    )
                elif 'json' in self.protocol.lower() and self.use_binary:
                    self.logger.warning(
                        f"Protocol mismatch warning: protocol '{self.protocol}' suggests text "
                        f"but sending as {expected_frame_type} frame"
                    )
            
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
            self.active_subscriptions.set(request_id, query_id)
            self.subscription_queries.set(query_id, [query])
        
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
            self.active_subscriptions.set(request_id, query_id)
            self.subscription_queries.set(query_id, queries)
        
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
            self.subscription_queries.delete(query_id)
            
            # Find and remove from active subscriptions
            for req_id, qid in list(self.active_subscriptions.items()):
                if qid.id == query_id.id:
                    self.active_subscriptions.delete(req_id)
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
        
        # Validate SQL query for security
        try:
            # Validate the query for SQL injection and other security issues
            query_result = validate_sql_query(query, "query_string")
            if not query_result.is_valid:
                raise RuntimeError(f"Invalid SQL query: {'; '.join(str(e) for e in query_result.errors)}")
            
            # Use sanitized query
            sanitized_query = query_result.sanitized_value
            
        except ValidationError as e:
            raise RuntimeError(f"SQL query validation failed: {e}")
        
        # Use legacy OneOffQuery for backward compatibility
        message_id = uuid.uuid4().bytes
        message = OneOffQuery(
            message_id=message_id,
            query_string=sanitized_query
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
            
            # Initialize large message handler
            if not self.large_message_handler:
                def websocket_send_func(data):
                    """Wrapper function for large message handler to send data via WebSocket."""
                    if self.ws:
                        if isinstance(data, str):
                            self.ws.send(data)
                        else:
                            from websocket import ABNF
                            self.ws.send(data, opcode=ABNF.OPCODE_BINARY)
                
                self.large_message_handler = LargeMessageHandler(websocket_send_func)
                self.logger.debug("Large message handler initialized")
            
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
            # Convert message to bytes for size validation
            message_bytes = message.encode('utf-8') if isinstance(message, str) else message
            
            # Validate message size
            if not self.message_validator.validate_message_size(message_bytes):
                self.logger.error(f"Message too large, rejecting: {len(message_bytes)} bytes")
                return
            
            # Validate frame type against protocol configuration
            frame_type = "TEXT" if isinstance(message, str) else "BINARY"
            expected_frame_type = "BINARY" if self.use_binary else "TEXT"
            
            if frame_type != expected_frame_type:
                self.logger.warning(f"Received {frame_type} frame with {self.protocol} protocol - this may indicate protocol mismatch")
                self.logger.warning(f"Expected {expected_frame_type} frame for protocol {self.protocol}")
                
                # Check if this is a JSON message received when binary protocol is expected
                if frame_type == "TEXT" and self.use_binary:
                    try:
                        # Validate JSON message for security before parsing
                        json_result = validate_json_data(message, "websocket_message")
                        if json_result.is_valid:
                            json_data = json_result.sanitized_value
                            message_types = list(json_data.keys()) if isinstance(json_data, dict) else []
                            self.logger.warning(f"Unknown message type in data: {message_types}")
                            
                            # Log specific message types that are commonly mismatched
                            for msg_type in ['IdentityToken', 'InitialSubscription', 'TransactionUpdate']:
                                if isinstance(json_data, dict) and msg_type in json_data:
                                    self.logger.warning(f"Unknown message type in data: {{'{msg_type}': {{...}}}}")
                        else:
                            self.logger.warning(f"Invalid JSON message: {'; '.join(str(e) for e in json_result.errors)}")
                    except ValidationError as e:
                        self.logger.warning(f"JSON validation failed: {e}")
                    except Exception as e:
                        self.logger.warning(f"JSON processing error: {e}")
                        pass  # Continue with normal processing
            
            # Handle incoming message data with large message support
            processed_message_data = None
            
            # Try large message handler first if available
            if self.large_message_handler:
                processed_message_data = self.large_message_handler.handle_incoming_message(message)
                
                # If processed_message_data is None, it means we're waiting for more chunks
                if processed_message_data is None:
                    self.logger.debug("Received partial chunked message, waiting for more chunks")
                    return
            
            # Use processed data if available, otherwise use original message
            if processed_message_data is not None:
                message_data = processed_message_data
            else:
                if isinstance(message, str):
                    message_data = message.encode('utf-8')
                else:
                    message_data = message
            
            message_size = len(message_data)
            large_message_threshold = 50 * 1024  # 50KB
            
            # Log large message handling for debugging
            if message_size > large_message_threshold:
                self.logger.info(f"Processing large message: {message_size} bytes (reassembled from chunks)")
            elif self.large_message_handler and message_size > 1024:
                self.logger.debug(f"Processing message: {message_size} bytes")
                
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
            
            # Record subscription metrics for applicable message types
            self._record_subscription_metrics(server_message, message_size)
            
            # Notify subscription state callbacks
            self._notify_subscription_state_callbacks(server_message)
            
            # Log successful processing of large messages
            if message_size > large_message_threshold:
                self.logger.info(f"Successfully processed large message: {type(server_message).__name__}")
            
            # Forward to application
            if self._on_message:
                # Pass the raw server message object to the handler
                # The modern client expects protocol objects, not serialized dicts
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
                    
                    # Handle SpacetimeDB authentication handshake (400 with identity token)
                    if status_code == 400 and headers.get("spacetime-identity-token"):
                        self.logger.info("Detected SpacetimeDB authentication handshake")
                        identity = headers.get("spacetime-identity")
                        token = headers.get("spacetime-identity-token")
                        
                        if identity and token:
                            self.logger.info(f"Received identity token, retrying with authentication: {identity[:8]}...")
                            
                            # Store the credentials
                            self.spacetimedb_identity = identity
                            self.spacetimedb_token = token
                            self.auth_handshake_completed = True
                            
                            # Store credentials for future use
                            if self.host and self.database_address:
                                store_credentials(identity, token, self.host, self.database_address)
                            
                            # Retry connection with authentication
                            self.retry_with_auth = True
                            
                            # Schedule an immediate reconnect with authentication
                            threading.Timer(0.1, self._do_connect).start()
                            return
                        
                    # Create appropriate exception based on status code
                    elif status_code == 404:
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
                    elif status_code == 400:
                        # Handle regular 400 errors (not authentication handshake)
                        error = AuthenticationError(
                            reason=f"HTTP {status_code}: {status_message}",
                            auth_method="Bearer" if self.spacetimedb_token else ("Basic" if self.auth_token else "None"),
                            status_code=status_code
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
    
    def _record_subscription_metrics(self, server_message, message_size: int) -> None:
        """Record subscription metrics for applicable message types."""
        try:
            # Handle different subscription-related message types
            from .protocol import (
                InitialSubscription, TransactionUpdate, TransactionUpdateLight,
                SubscribeApplied, SubscribeMultiApplied
            )
            
            if isinstance(server_message, InitialSubscription):
                # Record metrics for initial subscription data
                if hasattr(server_message, 'database_update') and server_message.database_update:
                    tables = getattr(server_message.database_update, 'tables', [])
                    for table in tables:
                        table_name = getattr(table, 'table_name', 'unknown')
                        self.subscription_metrics.record_subscription_data(table_name, message_size // len(tables))
                        
            elif isinstance(server_message, TransactionUpdate):
                # Record metrics for transaction updates
                if hasattr(server_message, 'status'):
                    status = server_message.status
                    if hasattr(status, 'tables'):
                        tables = getattr(status, 'tables', [])
                        for table in tables:
                            table_name = getattr(table, 'table_name', 'unknown')
                            self.subscription_metrics.record_subscription_data(table_name, message_size // len(tables))
                            
            elif isinstance(server_message, TransactionUpdateLight):
                # Record metrics for light transaction updates
                if hasattr(server_message, 'update') and hasattr(server_message.update, 'tables'):
                    tables = getattr(server_message.update, 'tables', [])
                    for table in tables:
                        table_name = getattr(table, 'table_name', 'unknown')
                        self.subscription_metrics.record_subscription_data(table_name, message_size // len(tables))
                        
            elif isinstance(server_message, (SubscribeApplied, SubscribeMultiApplied)):
                # Record metrics for subscription applied messages
                if hasattr(server_message, 'table_rows'):
                    table_update = server_message.table_rows
                    table_name = getattr(table_update, 'table_name', 'unknown')
                    self.subscription_metrics.record_subscription_data(table_name, message_size)
                    
        except Exception as e:
            # Don't let metrics recording break message processing
            self.logger.debug(f"Failed to record subscription metrics: {e}")
    
    def _notify_subscription_state_callbacks(self, server_message) -> None:
        """Notify subscription state callbacks of relevant updates."""
        try:
            from .protocol import (
                InitialSubscription, TransactionUpdate, TransactionUpdateLight,
                SubscribeApplied, SubscribeMultiApplied, SubscriptionError
            )
            
            if isinstance(server_message, (InitialSubscription, TransactionUpdate, 
                                         TransactionUpdateLight, SubscribeApplied, 
                                         SubscribeMultiApplied)):
                for callback in self.subscription_state_callbacks:
                    try:
                        callback('subscription_update', server_message)
                    except Exception as e:
                        self.logger.error(f"Subscription state callback error: {e}")
                        
            elif isinstance(server_message, SubscriptionError):
                for callback in self.subscription_state_callbacks:
                    try:
                        callback('subscription_error', server_message)
                    except Exception as e:
                        self.logger.error(f"Subscription error callback error: {e}")
                        
        except Exception as e:
            self.logger.debug(f"Failed to notify subscription state callbacks: {e}")
    
    def get_subscription_health(self, table_name: str) -> Dict[str, Any]:
        """
        Get health metrics for a specific subscription.
        
        Args:
            table_name: Name of the table to get health metrics for
            
        Returns:
            Dictionary containing health status, message counts, error rates, etc.
        """
        return self.subscription_metrics.get_subscription_health(table_name)
    
    def get_all_subscription_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Get health metrics for all active subscriptions.
        
        Returns:
            Dictionary mapping table names to their health metrics
        """
        return self.subscription_metrics.get_all_subscription_health()
    
    def reset_subscription_metrics(self) -> None:
        """Reset all subscription health metrics."""
        self.subscription_metrics.reset_metrics()
    
    def get_protocol_helper(self):
        """Get the protocol helper for client-side encoding compatibility."""
        return {
            'encoder': self.encoder,
            'decoder': self.decoder,
            'use_binary': self.use_binary,
            'protocol': self.protocol
        }
