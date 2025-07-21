"""
Modern WebSocket client for SpacetimeDB protocol v1.1.2

This replaces the old spacetime_websocket_client.py with support for:
- Modern protocol message types
- Connection lifecycle management
- QueryId-based subscription tracking
- Energy quota management
- Reconnection with exponential backoff
- Message compression (Brotli/Gzip) for production performance
- V1.1.2 protocol compatibility with /v1/ws/ endpoint format
"""

import websocket
import threading
import time
import base64
import logging
from .utils.error_formatting import ErrorFormatter
import json
from typing import Optional, Callable, Dict, List, Any, Union
from enum import Enum
import uuid
import os
import urllib.parse
import re

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
    SpacetimeDBAuthHandshakeError,
    ValidationSecurityError,
    AuthenticationSecurityError,
    ProtocolSecurityError,
    ConnectionSecurityError,
    NetworkOperationalError,
    ResourceOperationalError,
    OperationalError
)
from .security_logger import log_security_exception
from .auth.storage import AuthCredentials
from .auth.storage import SecureAuthStorage
from .auth.authentication_manager import AuthenticationManager

# Global storage instance for compatibility
_global_auth_storage = None

def get_credentials(host: str, database: str, allow_expired: bool = False) -> Optional[AuthCredentials]:
    """Get authentication credentials using modern secure storage."""
    global _global_auth_storage
    if _global_auth_storage is None:
        _global_auth_storage = SecureAuthStorage()
    return _global_auth_storage.get_credentials(host, database, allow_expired)

def store_credentials(identity: str, token: str, host: str, database: str) -> None:
    """Store authentication credentials using modern secure storage."""
    global _global_auth_storage
    if _global_auth_storage is None:
        _global_auth_storage = SecureAuthStorage()
    _global_auth_storage.store_credentials(identity, token, host, database)
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
from .monitoring import get_global_monitor, monitor_performance
from .messages.subscribe import (
    SubscribeSingleMessage,
    SubscribeMultiMessage,
    UnsubscribeMultiMessage
)
from .messages.one_off_query import (
    OneOffQueryMessage
)
from .query_id import QueryId
from .compression_handlers.compression_manager import (
    CompressionManager,
    CompressionConfig,
    CompressionType,
    CompressionLevel,
    CompressionMetrics,
    CompressionSecurityConfig
)
# Also import security manager for enhanced security
try:
    from .validation.security_manager import SecurityManager
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    SecurityManager = None
from .large_message_handler import LargeMessageHandler
from .memory_management import (
    BoundedDict, BoundedSubscriptionManager, RecursionLimiter,
    MemoryAccountant, MessageSizeValidator, get_global_memory_accountant,
    BoundedRequestTracker
)
# Import validation with fallback handling
try:
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
except ImportError:
    # Fallback if validation module is not available
    validate_json_data = None
    ValidationError = Exception
    
    # Define minimal fallback functions - these won't be used in normal operation
    # but prevent ImportError when validation module is unavailable
    
    # Simple ValidationResult mock for fallback
    class ValidationResult:
        def __init__(self, is_valid=True, sanitized_value=None, errors=None, warnings=None):
            self.is_valid = is_valid
            self.sanitized_value = sanitized_value
            self.errors = errors or []
            self.warnings = warnings or []
    
    get_security_manager = lambda: None
    validate_url = lambda url, field=None: ValidationResult(is_valid=True, sanitized_value=url)
    validate_websocket_url = lambda url, field=None: ValidationResult(is_valid=True, sanitized_value=url)
    validate_sql_query = lambda query, field=None: ValidationResult(is_valid=True, sanitized_value=query)
    sanitize_url = lambda url, field=None: url
    sanitize_sql_query = lambda query, field=None: query
    sanitize_json_data = lambda data, field=None: data


def validate_database_identifier(db_identifier: str) -> str:
    """
    Secure validation function for database identifiers to prevent path traversal attacks.
    
    This function provides comprehensive protection against:
    - URL-encoded path traversal attacks (%2e%2e%2f, etc.)
    - Multiple slash variations (/, \\, mixed)
    - Absolute paths and parent directory escapes
    - Invalid characters outside of safe whitelist
    - Null byte attacks and length limits
    - Mixed encoding attacks
    
    Security measures implemented:
    1. URL decoding to handle encoded attacks
    2. Path normalization using os.path.normpath()
    3. Rejection of absolute paths and parent directory escapes
    4. Character whitelist validation (alphanumeric, underscore, hyphen only)
    5. Length limits (max 255 characters)
    6. Comprehensive security logging for attack attempts
    
    Args:
        db_identifier: The database identifier to validate
        
    Returns:
        The validated and sanitized database identifier
        
    Raises:
        ValidationError: If the identifier fails security validation
        
    Examples:
        Valid: "my_database", "db-1", "test123"
        Invalid: "../etc/passwd", "%2e%2e%2fpasswd", "/abs/path", "db\x00name"
    """
    logger = logging.getLogger(__name__)
    
    if not db_identifier:
        logger.warning("Security: Empty database identifier provided")
        raise ValidationError("Database identifier cannot be empty")
    
    original_identifier = db_identifier
    
    # 1. Length validation (before any processing to prevent DoS)
    if len(db_identifier) > 255:
        logger.warning(f"Security: Database identifier too long: {len(db_identifier)} chars (max 255)")
        raise ValidationError("Database identifier too long (max 255 characters)")
    
    # 2. Check for null bytes (prevent null byte injection)
    if '\x00' in db_identifier:
        logger.warning(f"Security: Null byte attack detected in database identifier: {repr(db_identifier)}")
        raise ValidationError("Database identifier contains null bytes")
    
    # 3. URL decode to handle encoded attacks (e.g., %2e%2e%2f for ../)
    try:
        # Decode multiple times to handle double/triple encoding
        decoded = db_identifier
        for _ in range(3):  # Limit iterations to prevent infinite loops
            new_decoded = urllib.parse.unquote(decoded)
            if new_decoded == decoded:
                break  # No more decoding needed
            decoded = new_decoded
        db_identifier = decoded
    except Exception as e:
        logger.warning(f"Security: URL decoding failed for database identifier: {e}")
        raise ValidationError("Invalid URL encoding in database identifier")
    
    # 4. Path normalization to resolve . and .. components
    normalized = os.path.normpath(db_identifier)
    
    # 5. Check for path traversal attempts after normalization
    if '..' in normalized:
        logger.warning(f"Security: Path traversal attempt detected - Original: {repr(original_identifier)}, Normalized: {repr(normalized)}")
        raise ValidationError("Path traversal attempt in database identifier")
    
    # 6. Reject absolute paths (Unix and Windows)
    if normalized.startswith('/') or (len(normalized) > 1 and normalized[1] == ':'):
        logger.warning(f"Security: Absolute path rejected - Original: {repr(original_identifier)}, Normalized: {repr(normalized)}")
        raise ValidationError("Absolute paths not allowed in database identifier")
    
    # 7. Character whitelist validation (only alphanumeric, underscore, hyphen)
    # This is the most restrictive check and should catch most remaining attacks
    if not re.match(r'^[a-zA-Z0-9_-]+$', normalized):
        invalid_chars = set(normalized) - set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
        logger.warning(f"Security: Invalid characters in database identifier - Original: {repr(original_identifier)}, Invalid chars: {invalid_chars}")
        raise ValidationError(f"Database identifier contains invalid characters. Only alphanumeric, underscore, and hyphen allowed. Found: {', '.join(sorted(invalid_chars))}")
    
    # 8. Final length check after normalization
    if len(normalized) > 255:
        logger.warning(f"Security: Normalized database identifier too long: {len(normalized)} chars")
        raise ValidationError("Normalized database identifier too long")
    
    # 9. Additional checks for common attack patterns
    suspicious_patterns = [
        'etc', 'passwd', 'shadow', 'hosts', 'resolv', 'profile',
        'bashrc', 'zshrc', 'ssh', 'config', 'secret', 'key',
        'proc', 'sys', 'dev', 'tmp', 'var', 'usr', 'bin', 'sbin'
    ]
    
    lower_normalized = normalized.lower()
    for pattern in suspicious_patterns:
        if pattern in lower_normalized:
            logger.warning(f"Security: Suspicious pattern '{pattern}' detected in database identifier: {repr(original_identifier)}")
            # Note: This is a warning, not an error, as legitimate database names might contain these substrings
    
    # Log successful validation for audit trail
    if original_identifier != normalized:
        logger.info(f"Security: Database identifier normalized - Original: {repr(original_identifier)}, Final: {repr(normalized)}")
    
    return normalized


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


# ConnectionState moved to connection.connection_manager module
# Import it from there to maintain backward compatibility
from .connection.connection_manager import ConnectionState


class WebSocketClient:
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
    
    def __init__(self, *args, **kwargs):
        """
        Hybrid constructor supporting both legacy and modern API patterns.
        
        Legacy API (backward compatibility):
            WebSocketClient(host, database_address, auth_token=None, ssl_enabled=True)
            
        Modern API (current):
            WebSocketClient(protocol=TEXT_PROTOCOL, on_connect=None, on_disconnect=None, ...)
        """
        # Detect which API is being used
        if self._is_legacy_api(*args, **kwargs):
            self._init_legacy_api(*args, **kwargs)
        else:
            self._init_modern_api(*args, **kwargs)
    
    def _is_legacy_api(self, *args, **kwargs) -> bool:
        """Detect if legacy API is being used."""
        # Legacy API: first positional arg is host (string), or 'host' in kwargs
        if args and isinstance(args[0], str) and not args[0].startswith('ws://') and not args[0].startswith('wss://'):
            return True
        if 'host' in kwargs or 'database_address' in kwargs:
            return True
        return False
    
    def _init_legacy_api(self, *args, **kwargs):
        """Initialize using legacy API pattern."""
        # Parse legacy arguments: host, database_address, auth_token, ssl_enabled
        if args:
            self.host = args[0] if len(args) > 0 else kwargs.get('host')
            self.database_address = args[1] if len(args) > 1 else kwargs.get('database_address')
            self.auth_token = args[2] if len(args) > 2 else kwargs.get('auth_token')
            self.ssl_enabled = args[3] if len(args) > 3 else kwargs.get('ssl_enabled', False)
        else:
            self.host = kwargs.get('host')
            self.database_address = kwargs.get('database_address')
            self.auth_token = kwargs.get('auth_token')
            self.ssl_enabled = kwargs.get('ssl_enabled', False)
        
        # Set default modern API parameters
        self.protocol = TEXT_PROTOCOL
        self._on_connect = None
        self._on_disconnect = None
        self._on_error = None
        self._on_message = None
        self.auto_reconnect = True
        self.max_reconnect_attempts = 10
        self.initial_reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
        self.compression_config = None
        self.retry_policy = None
        
        # Initialize common components
        self._init_common_components()
    
    def _init_modern_api(self, *args, **kwargs):
        """Initialize using modern API pattern."""
        # Parse modern arguments
        self.protocol = kwargs.get('protocol', TEXT_PROTOCOL)
        self._on_connect = kwargs.get('on_connect')
        self._on_disconnect = kwargs.get('on_disconnect')
        self._on_error = kwargs.get('on_error')
        self._on_message = kwargs.get('on_message')
        self.auto_reconnect = kwargs.get('auto_reconnect', True)
        self.max_reconnect_attempts = kwargs.get('max_reconnect_attempts', 10)
        self.initial_reconnect_delay = kwargs.get('initial_reconnect_delay', 1.0)
        self.max_reconnect_delay = kwargs.get('max_reconnect_delay', 60.0)
        self.compression_config = kwargs.get('compression_config')
        self.retry_policy = kwargs.get('retry_policy')
        
        # Connection details (will be set later via connect())
        self.auth_token = None
        self.host = None
        self.database_address = None
        self.ssl_enabled = True
        
        # Initialize common components
        self._init_common_components()
    
    def _init_common_components(self):
        """Initialize components common to both legacy and modern APIs."""
        # Use the module-level logger
        self.logger = logging.getLogger(__name__)
        
        self.use_binary = self._determine_frame_type(self.protocol)
        
        # Initialize ConnectionManager for focused connection lifecycle management
        from .connection.connection_manager import (
            ConnectionManager, 
            ConnectionConfig, 
            DefaultWebSocketFactory,
            NullEventManager
        )
        from .events.websocket_integration import get_websocket_integration
        
        # Create event integration bridge
        self._event_integration = get_websocket_integration(self)
        
        # Create bridge class to connect ConnectionManager to unified event system
        class UnifiedEventBridge:
            def __init__(self, integration, websocket_client):
                self.integration = integration
                self.websocket_client = websocket_client
            
            def emit_connection_opened(self):
                # Bridge to unified event system
                connection_id = getattr(self.websocket_client, 'connection_id', 'unknown')
                host = getattr(self.websocket_client, 'host', 'unknown') 
                database = getattr(self.websocket_client, 'database_address', 'unknown')
                self.integration.emit_connection_opened(connection_id, host, database)
            
            def emit_connection_closed(self, reason: str):
                connection_id = getattr(self.websocket_client, 'connection_id', None)
                self.integration.emit_connection_closed(connection_id, reason)
            
            def emit_connection_error(self, error: Exception):
                connection_id = getattr(self.websocket_client, 'connection_id', None)
                self.integration.emit_connection_error(str(error))
        
        self._connection_manager = ConnectionManager(
            websocket_factory=DefaultWebSocketFactory(),
            event_manager=UnifiedEventBridge(self._event_integration, self),
            diagnostics=getattr(self, 'diagnostics', None)
        )
        
        # Set up connection manager callbacks to maintain WebSocketClient behavior
        self._connection_manager.set_callbacks(
            on_open=self._on_ws_open,
            on_close=self._on_ws_close,
            on_error=self._on_ws_error,
            on_message=self._on_ws_message
        )
        
        # Backward compatibility properties for connection state
        self.state = ConnectionState.DISCONNECTED
        self.ws: Optional[websocket.WebSocketApp] = None
        self.connection_thread: Optional[threading.Thread] = None
        
        # SpacetimeDB JWT Authentication - Backward compatibility properties
        self.spacetimedb_identity: Optional[str] = None
        self.spacetimedb_token: Optional[str] = None
        self.auth_handshake_completed: bool = False
        self.retry_with_auth: bool = False
        
        # AuthenticationManager - Centralized authentication flow management
        # Initialize with None host/database_address - will be set in connect()
        self._auth_manager = AuthenticationManager(
            host=getattr(self, 'host', None),
            database=getattr(self, 'database_address', None),
            storage=_global_auth_storage,
            event_manager=getattr(self, 'event_manager', None),
            logger=self.logger
        )
        
        # Identity and connection tracking
        self.identity: Optional[Identity] = None
        self.connection_id: Optional[ConnectionId] = None
        
        # Initialize Compression Manager before protocol configuration
        security_validator = None
        if SECURITY_AVAILABLE:
            try:
                security_validator = SecurityManager()
                self.logger.debug("Enhanced compression security enabled")
            except Exception as e:
                self.logger.warning(f"Could not initialize compression security: {e}")
        
        # Create default compression config if none exists
        compression_config = getattr(self, 'compression_config', None)
        if compression_config is None:
            # Import the enhanced CompressionConfig here to avoid import issues
            from .compression_handlers.compression_manager import CompressionConfig as EnhancedCompressionConfig
            compression_config = EnhancedCompressionConfig()
            
        self.compression_manager = CompressionManager(
            config=compression_config,
            security_validator=security_validator
        )
        
        # Protocol handling - using focused ProtocolHandler
        from .protocol_handlers.protocol_handler import ProtocolHandlerFactory, ProtocolConfiguration
        
        protocol_config = ProtocolConfiguration(
            protocol_version=self.protocol,
            use_binary=self.use_binary,
            enable_compression=bool(self.compression_manager),
            enable_security_validation=True,
            enable_message_size_validation=True,
            thread_safe=True
        )
        
        self.protocol_handler = ProtocolHandlerFactory.create_handler(
            protocol_version=self.protocol,
            enable_security=True,
            enable_compression=bool(self.compression_manager),
            thread_safe=True
        )
        
        # Set compression manager for protocol handler
        if self.compression_manager:
            self.protocol_handler.compression_manager = self.compression_manager
            
        # Sync compression state when negotiated
        def sync_compression_state() -> None:
            if hasattr(self, 'negotiated_compression') and self.negotiated_compression:
                self.protocol_handler.set_compression(self.negotiated_compression)
                
        self._sync_compression_state = sync_compression_state
        
        # Legacy compatibility: keep encoder/decoder references
        self.encoder = self.protocol_handler.encoder
        self.decoder = self.protocol_handler.decoder
        
        # Compression negotiation state
        self.negotiated_compression: Optional[CompressionType] = None
        
        # Large message handling
        self.large_message_handler: Optional[LargeMessageHandler] = None
        
        # Reconnection logic (using already initialized attributes)
        self.reconnect_attempts = 0
        self.reconnect_timer: Optional[threading.Timer] = None
        
        # Enhanced error recovery with circuit breaker pattern
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.circuit_breaker_timeout = 60.0  # seconds
        self.circuit_breaker_last_failure = 0
        self.transient_error_types = {
            "connection timeout", "connection refused", "connection reset",
            "network unreachable", "host unreachable", "temporary failure"
        }
        
        # Connection timeout handling
        self.connection_timeout = 30.0  # seconds
        self.connection_start_time = None
        self.connection_timeout_timer: Optional[threading.Timer] = None
        
        # Connection diagnostics
        self.diagnostics = ConnectionDiagnostics()
        self.enable_preflight_checks = True
        self.retry_on_transient_errors = True
        
        # Retry policy (use already initialized attribute or default)
        if not hasattr(self, 'retry_policy') or self.retry_policy is None:
            self.retry_policy = RetryPolicyPresets.standard()
        
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
        
        # Request tracking with bounded storage using BoundedRequestTracker
        self.request_tracker = BoundedRequestTracker(
            max_size=10000,
            cleanup_interval=300.0,  # 5 minutes
            default_timeout=30.0,
            memory_accountant=self.memory_accountant
        )
        
        # Subscription state coordination for client integration
        self.subscription_state_callbacks: List[Callable[[str, Any], None]] = []
        
        # Subscription metrics tracking
        self.subscription_metrics = SubscriptionMetrics()
        
        # Threading lock for thread safety
        self._lock = threading.RLock()
        
        # Legacy API compatibility: Add callback attributes
        self.on_connect = None
        self.on_disconnect = None
        self.on_error = None
        self.on_identity = None
        self.on_subscription_applied = None
        self.on_subscription_data = None
        self.on_subscription_error = None
        self.on_reducer_result = None
        self.on_query_result = None
        self.on_message = None
        
        # Additional legacy API attributes
        self.subscriptions = {}  # For backward compatibility
        # Note: connection_state and ws_app are handled as properties for synchronization
        
        # Logging setup (logger already initialized above)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            self.logger.propagate = False
        
        self.logger.debug("WebSocketClient initializing...")
        self.logger.info(f"WebSocket client initialized with compression: {self.compression_manager.get_compression_info()['capabilities']['supported_types']}")
        self.logger.info(f"Memory management: BoundedRequestTracker with max_size={self.request_tracker.max_size}, cleanup_interval={self.request_tracker.cleanup_interval}s")
        self.logger.debug("WebSocketClient initialized.")
        
        # Sync initial state from AuthenticationManager
        self._sync_auth_state_from_manager()
    
    def _sync_auth_state_from_manager(self) -> None:
        """Synchronize authentication state from AuthenticationManager to legacy properties."""
        if self._auth_manager:
            self.spacetimedb_identity = self._auth_manager.identity
            self.spacetimedb_token = self._auth_manager.token
            self.auth_handshake_completed = self._auth_manager.handshake_completed
            self.retry_with_auth = False  # Reset retry flag
    
    def _sync_auth_state_to_manager(self) -> None:
        """Synchronize authentication state from legacy properties to AuthenticationManager."""
        if self._auth_manager and self.spacetimedb_identity and self.spacetimedb_token:
            # This is primarily for backward compatibility when code directly sets properties
            try:
                from .auth.storage import AuthCredentials
                credentials = AuthCredentials(
                    identity=self.spacetimedb_identity,
                    token=self.spacetimedb_token,
                    host=self.host,
                    database=self.database_address
                )
                self._auth_manager.authenticate(credentials)
            except Exception as e:
                self.logger.warning(f"Failed to sync auth state to manager: {e}")
    
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
    
    def get_protocol_helper(self) -> Dict[str, Any]:
        """
        Get the protocol helper for client-side encoding compatibility.
        
        Returns:
            Protocol encoder/decoder for use by client applications
        """
        return {
            'encoder': self.encoder,
            'decoder': self.decoder,
            'protocol': self.protocol,
            'use_binary': self.use_binary,
            'protocol_handler': self.protocol_handler
        }
    
    def get_protocol_metrics(self) -> Dict[str, Any]:
        """
        Get protocol processing metrics.
        
        Returns:
            Protocol metrics including encoding/decoding performance
        """
        if hasattr(self, 'protocol_handler'):
            return self.protocol_handler.get_metrics()
        return {}
    
    def get_protocol_info(self) -> Dict[str, Any]:
        """
        Get protocol handler information and configuration.
        
        Returns:
            Protocol configuration and status
        """
        if hasattr(self, 'protocol_handler'):
            return self.protocol_handler.get_protocol_info()
        return {
            'protocol_version': self.protocol,
            'use_binary': self.use_binary,
            'legacy_mode': True
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
        Send a pre-encoded message from client directly to WebSocket using ConnectionManager.
        
        Args:
            message: Pre-encoded message data
        """
        self.logger.debug(f"Sending client-encoded message: {len(str(message))} bytes")
        
        # Use ConnectionManager to send data
        try:
            self._connection_manager.send_data(message)
            
            # Log frame type for debugging
            if isinstance(message, str):
                self.logger.debug("Sent client-encoded message as TEXT frame")
            elif isinstance(message, bytes):
                self.logger.debug("Sent client-encoded message as BINARY frame")
        except Exception as e:
            self.logger.error(f"Failed to send client-encoded message: {e}")
            raise
    
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
                self.logger.error(ErrorFormatter.format_websocket_error("subscription state callback", e))
    
    def connect(
        self,
        auth_token: Optional[str] = None,
        host: Optional[str] = None,
        database_address: Optional[str] = None,
        ssl_enabled: Optional[bool] = None,
        db_identity: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None
    ) -> None:
        """Connect to SpacetimeDB using ConnectionManager with backward compatibility."""
        with self._lock:
            # Check current connection state through ConnectionManager
            if self._connection_manager.is_connected() or self._connection_manager.get_connection_state() == ConnectionState.CONNECTING:
                self.logger.warning("Already connected or connecting")
                return
            
            # Support both legacy and modern API signatures
            # Legacy: use constructor parameters if not provided
            # Modern: use provided parameters and update instance state
            self.auth_token = auth_token if auth_token is not None else self.auth_token
            self.host = host if host is not None else self.host
            self.database_address = database_address if database_address is not None else self.database_address
            self.ssl_enabled = ssl_enabled if ssl_enabled is not None else self.ssl_enabled
            self.db_identity = db_identity if db_identity is not None else getattr(self, 'db_identity', None)
            
            # Validate required parameters
            if not self.host:
                raise ValueError("host is required (either in constructor or connect() call)")
            
            # For V1.1.2 protocol compatibility:
            # - If db_identity is provided, database_address can be empty
            # - If both are empty, will fall back to module name (handled in URL construction)
            if not self.database_address and not self.db_identity:
                # Both empty - this is allowed for fallback behavior
                pass
            elif not self.database_address and self.db_identity:
                # db_identity provided but database_address empty - allowed in V1.1.2
                pass
            elif self.database_address and not self.db_identity:
                # Traditional mode - database_address only
                pass
            # All other combinations are valid (both provided, etc.)
            
            # Reset authentication state
            self.auth_handshake_completed = False
            self.retry_with_auth = False
            
            # Use AuthenticationManager for credential management
            if self._auth_manager:
                # Update manager with current connection parameters
                self._auth_manager.host = self.host
                self._auth_manager.database = self.database_address
                
                # Load stored credentials through manager
                auth_result = self._auth_manager.authenticate()
                if auth_result.success:
                    self.logger.info(f"AuthenticationManager loaded credentials for {self.host}/{self.database_address}")
                else:
                    self.logger.debug("No valid stored credentials found in AuthenticationManager")
                
                # Sync state from manager to legacy properties
                self._sync_auth_state_from_manager()
            else:
                # Fallback to direct credential loading (backward compatibility)
                stored_credentials = get_credentials(self.host, self.database_address)
                if stored_credentials and not stored_credentials.is_expired():
                    self.logger.info(f"Found stored SpacetimeDB credentials for {self.host}/{self.database_address}")
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
            
            # Create connection configuration for ConnectionManager
            from .connection.connection_manager import ConnectionConfig
            
            config = ConnectionConfig(
                host=self.host,
                database_address=self.database_address,
                auth_token=self.auth_token,
                ssl_enabled=self.ssl_enabled,
                db_identity=self.db_identity,
                protocol=self.protocol,
                connection_timeout=getattr(self, 'connection_timeout', 30.0),
                auto_reconnect=self.auto_reconnect,
                max_reconnect_attempts=self.max_reconnect_attempts,
                initial_reconnect_delay=self.initial_reconnect_delay,
                max_reconnect_delay=self.max_reconnect_delay,
                enable_preflight_checks=getattr(self, 'enable_preflight_checks', True),
                retry_on_transient_errors=getattr(self, 'retry_on_transient_errors', True)
            )
            
            # Use ConnectionManager to establish connection
            try:
                self._connection_manager.connect(config)
                
                # Note: State synchronization will happen in the WebSocket event callbacks
                # (_on_ws_open, _on_ws_error, etc.) to avoid race conditions
                
            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
                if self._on_error:
                    self._on_error(e)
                raise
    
    def _do_connect(self) -> None:
        """Internal connection logic with retry support."""
        self.logger.debug(f"_do_connect called. Current state: {self.state.value}. Attempt: {self.reconnect_attempts + 1}")
        
        def _attempt_connection():
            self.state = ConnectionState.CONNECTING
            
            # Start connection timeout timer
            self.connection_start_time = time.time()
            self._start_connection_timeout()
            
            # Build WebSocket URL for v1.1.2 compatibility with security validation
            protocol_scheme = "wss" if self.ssl_enabled else "ws"
            
            # Validate and sanitize host
            try:
                import urllib.parse
                parsed_host = urllib.parse.urlparse(f"{protocol_scheme}://{self.host}")
                host = parsed_host.hostname
                port = parsed_host.port
                
                # Validate the extracted host by reconstructing URL
                if not host:
                    raise ValidationError(f"Invalid host: {host}")
                
                # Validate the host by creating a URL and validating it
                security_manager = get_security_manager()
                if security_manager:
                    test_url = f"{protocol_scheme}://{host}"
                    host_result = security_manager.validate_url(test_url, "host")
                    if not host_result.is_valid:
                        raise ValidationError(f"Invalid host: {'; '.join(str(e) for e in host_result.errors)}")
                
                # Reconstruct the validated host with port if available
                validated_host = f"{host}:{port}" if port else host
            except ValidationError as e:
                raise WebSocketHandshakeError(f"Invalid host: {e}")
            
            # Use db_identity in URL path if provided, otherwise use database_address
            db_identifier = self.db_identity if self.db_identity else self.database_address
            
            # Validate and sanitize database identifier using comprehensive security validation
            try:
                # Apply comprehensive path traversal protection
                validated_db_identifier = validate_database_identifier(db_identifier)
                
                # Additional security manager validation if available
                security_manager = get_security_manager()
                if security_manager:
                    db_result = security_manager.size_validator.validate(validated_db_identifier, "database_identifier")
                    if not db_result.is_valid:
                        raise ValidationError(f"Invalid database identifier: {'; '.join(str(e) for e in db_result.errors)}")
                    validated_db_identifier = db_result.sanitized_value
                
                # Sanitize for URL inclusion (safe to do after validation)
                validated_db_identifier = urllib.parse.quote(validated_db_identifier, safe='')
                
            except ValidationError as e:
                raise WebSocketHandshakeError(f"Invalid database identifier: {e}")
            
            # Build URL with V1.1.2 format: /v1/ws/database/{identity}/subscribe?db_identity={uuid}
            # For backward compatibility, support both formats
            if self.db_identity:
                # Validate db_identity query parameter for security
                try:
                    validated_db_identity = validate_database_identifier(self.db_identity)
                except ValidationError as e:
                    raise WebSocketHandshakeError(f"Invalid db_identity parameter: {e}")
                
                # V1.1.2 format with /ws/ prefix and db_identity query parameter
                url = f"{protocol_scheme}://{validated_host}/v1/ws/database/{validated_db_identifier}/subscribe?db_identity={urllib.parse.quote(validated_db_identity, safe='')}"
            else:
                # Legacy format for backward compatibility
                url = f"{protocol_scheme}://{validated_host}/v1/database/{validated_db_identifier}/subscribe"
            
            # Final URL validation
            try:
                url_result = validate_websocket_url(url, "connection_url")
                if not url_result.is_valid:
                    raise ValidationError(f"Invalid connection URL: {'; '.join(str(e) for e in url_result.errors)}")
                url = url_result.sanitized_value
            except ValidationError as e:
                raise WebSocketHandshakeError(
                    status_code=400,
                    status_message=f"Invalid connection URL: {e}",
                    url=url
                )
            
            # Store URL for error diagnostics
            self.connection_url = url
            
            self.logger.debug(f"_do_connect: Set state to CONNECTING. URL: {url}")
            
            # Prepare headers
            headers = {}
            
            # Use AuthenticationManager for header generation
            if self._auth_manager and self._auth_manager.is_authenticated:
                auth_headers = self._auth_manager.get_auth_headers()
                headers.update(auth_headers)
                self.logger.debug("Using AuthenticationManager for JWT authentication")
            # Fallback to legacy properties for backward compatibility
            elif self.spacetimedb_token and self.auth_handshake_completed:
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
                name=f"WebSocketClient-ConnectionThread-{id(self)}"
            )
            self.connection_thread.start()
            self.logger.debug(f"_do_connect: Connection thread (ID: {self.connection_thread.ident}) started for {url}")
        
        # Apply retry policy if this is an initial connection attempt
        if self.reconnect_attempts == 0 and self.retry_on_transient_errors:
            try:
                self.retry_policy.execute_with_retry(_attempt_connection)
            except Exception as e:
                self.logger.error(ErrorFormatter.format_websocket_error("connection start after retries", e), exc_info=True)
                self.state = ConnectionState.DISCONNECTED
                if self._on_error:
                    self._on_error(e)
                # Don't schedule reconnect here as retry policy already attempted
        else:
            # For reconnection attempts, don't use retry policy (already has backoff)
            try:
                _attempt_connection()
            except Exception as e:
                self.logger.error(ErrorFormatter.format_websocket_error("connection start", e), exc_info=True)
                self.state = ConnectionState.DISCONNECTED
                if self._on_error:
                    self._on_error(e)
                self._schedule_reconnect()
    
    def disconnect(self) -> None:
        """Disconnect from SpacetimeDB using ConnectionManager with cleanup."""
        self.logger.debug(f"Disconnect called. Current thread: {threading.get_ident()}")
        
        with self._lock:
            self.logger.info("WebSocket client disconnect initiated.")
            
            # Use ConnectionManager to handle connection cleanup
            self._connection_manager.disconnect()
            
            # Sync state for backward compatibility
            self.state = self._connection_manager.get_connection_state()
            
            # Clear WebSocketClient-specific state
            self.identity = None
            self.connection_id = None
            self.active_subscriptions.clear()
            self.subscription_queries.clear()
            self.request_tracker.clear_all()
            self.negotiated_compression = None
            
            # Cleanup large message handler
            if self.large_message_handler:
                self.large_message_handler.shutdown()
                self.large_message_handler = None
            
            # Clear authentication state (but keep stored credentials for future use)
            # Note: We don't clear spacetimedb_identity and spacetimedb_token here
            # as they may be reused for reconnection
            self.retry_with_auth = False
            
            # Clear authentication state in AuthenticationManager (but preserve stored credentials)
            if self._auth_manager:
                # This clears in-memory state but preserves stored credentials
                self._auth_manager.logout()
            
            # Backward compatibility: clear old connection attributes
            self.ws = None
            self.connection_thread = None
            
            self.logger.info("WebSocket client disconnected and cleaned up.")
    
    @monitor_performance("websocket_send_message")
    def send_message(self, message: ClientMessage, use_client_encoding: bool = False) -> None:
        """
        Send a client message to the server with optional compression and proper serialization.
        
        Args:
            message: Message to send
            use_client_encoding: If True, skip SDK encoding and send message directly
        """
        # Thread-safe check of connection state using ConnectionManager
        # We check both the ConnectionManager state and ensure we have a connection reference
        with self._connection_manager._lock:
            if not self._connection_manager.is_connected() or not self._connection_manager._connection:
                state = self._connection_manager.get_connection_state()
                self.logger.debug(f"send_message failed: Not connected (ConnectionManager state: {state.value})")
                raise RuntimeError(f"Not connected to SpacetimeDB (state: {state.value})")
        
        try:
            # Handle client-encoded messages (bypass SDK encoding)
            if use_client_encoding:
                return self._send_client_encoded_message(message)
            
            # Use ProtocolHandler for message processing
            try:
                # Encode message using the focused ProtocolHandler
                # This handles validation, encoding, and compression automatically
                encoded_data = self.protocol_handler.encode_message(message)
                
                # Update compression state from protocol handler
                if hasattr(self.protocol_handler, 'negotiated_compression'):
                    self.negotiated_compression = self.protocol_handler.negotiated_compression
                    
            except Exception as e:
                self.logger.error(ErrorFormatter.format_websocket_error("protocol handler encoding", e))
                raise ValueError(f"Message encoding failed: {e}")
            
            # Compression is now handled by ProtocolHandler
            # encoded_data already includes compression if enabled
            
            # Send the message with large message handling support
            message_type = type(message).__name__
            
            # Use large message handler if available and message is potentially large
            if self.large_message_handler and len(encoded_data) > 1024:  # 1KB threshold for checking
                # Large message handler needs to use ConnectionManager for thread safety
                def connection_manager_send(data: bytes) -> None:
                    self._connection_manager.send_data(data)
                
                # Temporarily update the handler's send function
                original_send = self.large_message_handler._websocket_send_func
                self.large_message_handler._websocket_send_func = connection_manager_send
                try:
                    self.large_message_handler.send_large_message(
                        encoded_data, 
                        message_type=message_type
                    )
                finally:
                    # Restore original send function
                    self.large_message_handler._websocket_send_func = original_send
            else:
                # Send normally with correct frame type based on negotiated protocol
                expected_frame_type = self.detect_expected_frame_type()
                
                # Send data using ConnectionManager
                self._connection_manager.send_data(encoded_data)
                
                # Log frame type for debugging
                if self.use_binary:
                    self.logger.debug(
                        f"Sent {message_type} as BINARY frame "
                        f"(protocol: {self.protocol}, {len(encoded_data)} bytes)"
                    )
                else:
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
            
            # Record WebSocket frame metrics
            monitor = get_global_monitor()
            monitor.record_websocket_frame(sent=True, size=len(encoded_data))
            
        except Exception as e:
            self.logger.error(ErrorFormatter.format_websocket_error("send message", e))
            raise
    
    def call_reducer(
        self,
        reducer_name: str,
        args: Union[bytes, dict, Any],
        flags: Optional[Any] = None
    ) -> int:
        """Call a reducer and return the request ID."""
        request_id = generate_request_id()
        
        # Handle legacy API: convert dict/JSON to bytes
        if isinstance(args, dict):
            import json
            args = json.dumps(args).encode('utf-8')
        elif isinstance(args, str):
            args = args.encode('utf-8')
        elif not isinstance(args, bytes):
            # Convert other types to JSON bytes
            import json
            args = json.dumps(args).encode('utf-8')
        
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
            if not self.active_subscriptions.set(request_id, query_id):
                raise RuntimeError(f"Failed to store subscription for request_id {request_id}")
            if not self.subscription_queries.set(query_id, [query]):
                # Clean up the partial state
                self.active_subscriptions.delete(request_id)
                raise RuntimeError(f"Failed to store subscription query for query_id {query_id}")
            # Legacy compatibility: add to subscriptions dict
            self.subscriptions[str(query_id)] = {
                'query': query,
                'request_id': request_id,
                'active': True
            }
        
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
            if not self.active_subscriptions.set(request_id, query_id):
                raise RuntimeError(f"Failed to store subscription for request_id {request_id}")
            if not self.subscription_queries.set(query_id, queries):
                # Clean up the partial state
                self.active_subscriptions.delete(request_id)
                raise RuntimeError(f"Failed to store subscription queries for query_id {query_id}")
            # Legacy compatibility: add to subscriptions dict
            self.subscriptions[str(query_id)] = {
                'queries': queries,
                'request_id': request_id,
                'active': True
            }
        
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
            self.logger.error(ErrorFormatter.format_websocket_error("send enhanced one-off query", e))
            raise
        
        return metadata
    
    def one_off_query(self, query: str, params: Optional[List[Any]] = None) -> bytes:
        """
        Execute a one-off query (legacy method for backward compatibility).
        
        Args:
            query: The SQL query string to execute
            params: Optional query parameters (for legacy API compatibility)
            
        Returns:
            bytes: The message ID for tracking
            
        Raises:
            RuntimeError: If not connected to SpacetimeDB
        """
        if self.state != ConnectionState.CONNECTED or not self.ws:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        # Note: params parameter is accepted for legacy API compatibility
        # but parameter substitution is not implemented in this version
        if params is not None:
            self.logger.warning("Parameter substitution not implemented in one_off_query. Query will be executed as-is.")
        
        # Validate SQL query for security
        # Validate the query for SQL injection and other security issues
        query_result = validate_sql_query(query, "query_string")
        if not query_result.is_valid:
            raise RuntimeError(f"Invalid SQL query: {'; '.join(str(e) for e in query_result.errors)}")
        
        # Use sanitized query
        sanitized_query = query_result.sanitized_value
        
        # Use legacy OneOffQuery for backward compatibility
        message_id = uuid.uuid4().bytes
        message = OneOffQuery(
            message_id=message_id,
            query_string=sanitized_query
        )
        self.send_message(message)
        return message_id
    
    def _on_ws_open(self, ws) -> None:
        """WebSocket connection opened - sync with ConnectionManager state."""
        self.logger.debug(f"_on_ws_open: Callback triggered. Current thread: {threading.get_ident()}")
        with self._lock:
            self.logger.debug("_on_ws_open: Acquired _lock.")
            
            # Sync state from ConnectionManager
            cm_state = self._connection_manager.get_connection_state()
            self.state = cm_state
            self.ws = ws
            self.logger.debug(f"_on_ws_open: Synced state to {cm_state.value} and set ws reference")
            
            # Initialize large message handler with ConnectionManager
            if not self.large_message_handler:
                def connection_manager_send_func(data: bytes) -> None:
                    """Wrapper function for large message handler to use ConnectionManager."""
                    self._connection_manager.send_data(data)
                
                self.large_message_handler = LargeMessageHandler(connection_manager_send_func)
                self.logger.debug("Large message handler initialized with ConnectionManager")
            
            # Attempt compression negotiation from server response headers
            # In practice, WebSocket compression is usually handled at the WebSocket layer
            # but we can still track what we negotiated for application-level compression
            
        self.logger.info("Connected to SpacetimeDB (WebSocket open). Calling connection callbacks.")
        
        # Call modern callback
        if self._on_connect:
            try:
                self._on_connect()
            except Exception as e:
                self.logger.error(ErrorFormatter.format_websocket_error("modern on_connect callback", e), exc_info=True)
        
        # Call legacy callback for backward compatibility
        if self.on_connect:
            try:
                self.on_connect()
            except Exception as e:
                self.logger.error(ErrorFormatter.format_websocket_error("legacy on_connect callback", e), exc_info=True)
    
    def _on_ws_message(self, ws, message) -> None:
        """WebSocket message received with enhanced large message handling."""
        try:
            # Handle legacy test simulation messages (for backward compatibility)
            # These are not real protocol messages but test simulation helpers
            if isinstance(message, str):
                try:
                    from .security.json_validator import secure_json_loads
                    json_data = secure_json_loads(message, "websocket_test_message")
                    
                    # Handle test simulation of SubscriptionApplied (with legacy format)
                    if "SubscriptionApplied" in json_data:
                        sub_data = json_data["SubscriptionApplied"]
                        if self.on_subscription_applied:
                            query_id = sub_data.get("query_id", "unknown")
                            table_name = sub_data.get("table_name", "unknown")
                            self.on_subscription_applied(str(query_id), table_name)
                        return  # Skip normal protocol processing for test messages
                    
                    # Handle test simulation of TransactionUpdate
                    elif "TransactionUpdate" in json_data:
                        update_data = json_data["TransactionUpdate"]
                        if self.on_subscription_data:
                            table_name = update_data.get("table_name", "unknown")
                            data = update_data.get("data", [])
                            self.on_subscription_data(table_name, data)
                        return  # Skip normal protocol processing for test messages
                        
                    # Handle test simulation of IdentityToken
                    elif "IdentityToken" in json_data:
                        identity_data = json_data["IdentityToken"]
                        if self.on_identity:
                            token = identity_data.get("token", "")
                            identity = identity_data.get("identity", "")
                            connection_id = identity_data.get("connection_id", "")
                            self.on_identity(token, identity, connection_id)
                        return  # Skip normal protocol processing for test messages
                except (json.JSONDecodeError, TypeError):
                    # Not a JSON message, continue normal processing
                    pass
            
            # Convert message to bytes for size validation
            message_bytes = message.encode('utf-8') if isinstance(message, str) else message
            
            # Validate message size
            if not self.message_validator.validate_message_size(message_bytes):
                self.logger.error(ErrorFormatter.format_websocket_error("message size", Exception(f"Message too large: {len(message_bytes)} bytes")))
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
                        # Validate JSON message for security before parsing if validation is available
                        if validate_json_data:
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
                        else:
                            # Fallback to secure parsing if validation not available
                            from .security.json_validator import secure_json_loads
                            json_data = secure_json_loads(message, "websocket_fallback_message")
                            message_types = list(json_data.keys()) if isinstance(json_data, dict) else []
                            self.logger.warning(f"Unknown message type in data: {message_types}")
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
                        from .security.json_validator import secure_json_loads
                        parsed_preview = secure_json_loads(message_data.decode('utf-8'), "initial_subscription_preview")
                        if "InitialSubscription" in parsed_preview:
                            initial_sub = parsed_preview["InitialSubscription"]
                            database_update = initial_sub.get("database_update", {})
                            tables = database_update.get("tables", [])
                            self.logger.info(f"Large InitialSubscription: {len(tables)} tables, {message_size} bytes")
                            for table in tables:
                                table_name = table.get("table_name", "unknown")
                                num_rows = table.get("num_rows", 0)
                                self.logger.debug(f"  - {table_name}: {num_rows} rows")
                except (ValidationSecurityError, AuthenticationSecurityError, ProtocolSecurityError) as parse_error:
                    # Security exceptions in message preview parsing must be logged and re-raised
                    event_id = log_security_exception(parse_error, operation="message_preview_parsing")
                    self.logger.error(f"Security violation during message preview parsing [Event: {event_id}]: {parse_error}")
                    raise  # Always re-raise security exceptions
                except (ValueError, UnicodeDecodeError, KeyError, AttributeError) as parse_error:
                    # Expected errors during preview parsing - safe to handle
                    self.logger.debug(f"Expected error during large message preview parsing: {parse_error}")
                except Exception as parse_error:
                    # Unexpected errors in preview parsing should be logged but not break message processing
                    self.logger.warning(f"Unexpected error during large message preview parsing: {type(parse_error).__name__}: {parse_error}")
            
            # Use ProtocolHandler for complete message processing
            try:
                # Process message using the focused ProtocolHandler
                # This handles decompression, decoding, validation, and metrics automatically
                processed_result = self.protocol_handler.process_message(message_data)
                
                if processed_result is None:
                    # Partial message - waiting for more chunks
                    self.logger.debug("Received partial chunked message, waiting for more chunks")
                    return
                
                server_message = processed_result.message
                
                # Log processing information for debugging
                if processed_result.processing_time_ms > 100:  # Log slow processing
                    self.logger.debug(
                        f"Message processing: {processed_result.message_type} "
                        f"({processed_result.processing_time_ms:.1f}ms, "
                        f"compressed: {processed_result.was_compressed}, "
                        f"chunked: {processed_result.was_chunked})"
                    )
                    
            except Exception as decode_error:
                if message_size > large_message_threshold:
                    self.logger.error(ErrorFormatter.format_websocket_error(f"protocol handler processing large message ({message_size} bytes)", decode_error))
                    self.logger.info("Large message processing failure - this may indicate:")
                    self.logger.info("1. Message corruption during transmission")
                    self.logger.info("2. WebSocket frame fragmentation issues")
                    self.logger.info("3. Server-side message formatting problems")
                    self.logger.info("4. Protocol version mismatch")
                else:
                    self.logger.error(ErrorFormatter.format_websocket_error("protocol handler processing", decode_error))
                raise
            
            # Handle identity token
            if isinstance(server_message, IdentityToken):
                with self._lock:
                    self.identity = server_message.identity
                    self.connection_id = server_message.connection_id
                self.logger.info(f"Received identity: {self.identity}")
                
                # Call legacy on_identity callback for backward compatibility
                if self.on_identity:
                    try:
                        # Legacy callback expects: (token, identity, connection_id)
                        self.on_identity(
                            server_message.token,
                            str(server_message.identity),
                            str(server_message.connection_id)
                        )
                    except Exception as e:
                        self.logger.error(ErrorFormatter.format_websocket_error("legacy on_identity callback", e), exc_info=True)
            
            # Handle subscription applied messages for legacy compatibility
            from .protocol import SubscribeApplied, SubscribeMultiApplied
            if isinstance(server_message, (SubscribeApplied, SubscribeMultiApplied)):
                if self.on_subscription_applied:
                    try:
                        # Legacy callback expects: (query_id, table_name)
                        query_id = getattr(server_message, 'query_id', None)
                        table_name = getattr(server_message, 'table_name', None)
                        
                        # Extract table name from table_rows if available
                        if not table_name and hasattr(server_message, 'table_rows'):
                            table_name = getattr(server_message.table_rows, 'table_name', None)
                            
                        if query_id is not None:
                            self.on_subscription_applied(str(query_id), table_name or 'unknown')
                    except Exception as e:
                        self.logger.error(ErrorFormatter.format_websocket_error("legacy on_subscription_applied callback", e), exc_info=True)
            
            # Handle subscription data messages for legacy compatibility
            from .protocol import TransactionUpdate, TransactionUpdateLight, InitialSubscription
            if isinstance(server_message, (TransactionUpdate, TransactionUpdateLight, InitialSubscription)):
                if self.on_subscription_data:
                    try:
                        # Extract table data from different message types
                        if isinstance(server_message, TransactionUpdate):
                            if hasattr(server_message, 'status') and hasattr(server_message.status, 'tables'):
                                for table in server_message.status.tables:
                                    table_name = getattr(table, 'table_name', 'unknown')
                                    table_data = getattr(table, 'data', [])
                                    self.on_subscription_data(table_name, table_data)
                        elif isinstance(server_message, TransactionUpdateLight):
                            if hasattr(server_message, 'update') and hasattr(server_message.update, 'tables'):
                                for table in server_message.update.tables:
                                    table_name = getattr(table, 'table_name', 'unknown')
                                    table_data = getattr(table, 'data', [])
                                    self.on_subscription_data(table_name, table_data)
                        elif isinstance(server_message, InitialSubscription):
                            if hasattr(server_message, 'database_update') and hasattr(server_message.database_update, 'tables'):
                                for table in server_message.database_update.tables:
                                    table_name = getattr(table, 'table_name', 'unknown')
                                    table_data = getattr(table, 'data', [])
                                    self.on_subscription_data(table_name, table_data)
                    except Exception as e:
                        self.logger.error(ErrorFormatter.format_websocket_error("legacy on_subscription_data callback", e), exc_info=True)
            
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
                
        except (ValidationSecurityError, AuthenticationSecurityError, ProtocolSecurityError, ConnectionSecurityError) as e:
            # Security exceptions must never be silently caught - these indicate potential attacks
            message_size = len(message) if hasattr(message, '__len__') else 0
            event_id = log_security_exception(e, operation="websocket_message_processing")
            self.logger.error(f"SECURITY VIOLATION during message processing ({message_size} bytes) [Event: {event_id}]: {e}")
            self.logger.critical(f"Security context: {getattr(e, 'security_context', 'Unknown')}")
            
            # Always notify error callback of security violations
            if self._on_error:
                self._on_error(e)
            
            # Always re-raise security exceptions
            raise
            
        except (ConnectionError, TimeoutError, OSError, AttributeError, TypeError, ValueError, UnicodeDecodeError) as e:
            # Expected operational errors during message processing - safe to handle
            message_size = len(message) if hasattr(message, '__len__') else 0
            if message_size > 50 * 1024:  # 50KB
                self.logger.warning(f"Expected error during large message processing ({message_size} bytes): {e}")
                self.logger.info("Large message error - consider:")
                self.logger.info("1. Increasing WebSocket buffer sizes")
                self.logger.info("2. Implementing message streaming")  
                self.logger.info("3. Server-side message compression")
            else:
                self.logger.warning(f"Expected error during message processing: {e}")
            
            if self._on_error:
                self._on_error(e)
                
        except Exception as e:
            # Unexpected errors should be logged and converted to operational error
            message_size = len(message) if hasattr(message, '__len__') else 0
            if message_size > 50 * 1024:  # 50KB
                self.logger.critical(f"Unexpected error during large message processing ({message_size} bytes): {type(e).__name__}: {e}")
                self.logger.info("Large message error - consider:")
                self.logger.info("1. Increasing WebSocket buffer sizes")
                self.logger.info("2. Implementing message streaming")
                self.logger.info("3. Server-side message compression")
            else:
                self.logger.critical(f"Unexpected error during message processing: {type(e).__name__}: {e}")
            
            # Convert to operational error with diagnostic info
            operational_error = NetworkOperationalError(
                f"Internal error during message processing: {type(e).__name__}",
                diagnostic_info={
                    "original_error": str(e),
                    "error_type": type(e).__name__,
                    "message_size": message_size,
                    "operation": "websocket_message_processing",
                    "is_large_message": message_size > 50 * 1024
                }
            )
            
            if self._on_error:
                self._on_error(operational_error)
            
            # Re-raise as operational error to maintain error handling chain
            raise operational_error
    
    def _on_ws_error(self, ws, error) -> None:
        """WebSocket error occurred - sync with ConnectionManager."""
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
            
        self.logger.error(ErrorFormatter.format_websocket_error("connection", Exception(f"WebSocket error: {error}")))
        
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
                        
                        token_match = re.search(r"spacetime-identity-token:\s*([A-Za-z0-9+/=._-]+)", error_str)
                        if token_match:
                            headers["spacetime-identity-token"] = token_match.group(1)
                    
                    # Try to parse JSON error response for V1.1.2
                    json_error_body = None
                    try:
                        # Look for JSON error body in the error string
                        json_match = re.search(r'\{[^}]*"error"[^}]*\}', error_str)
                        if json_match:
                            from .security.json_validator import secure_json_loads
                            json_error_body = secure_json_loads(json_match.group(0), "websocket_error_body")
                    except (json.JSONDecodeError, AttributeError):
                        pass
                    
                    # Handle SpacetimeDB authentication handshake (400 with identity token)
                    if status_code == 400 and headers.get("spacetime-identity-token"):
                        self.logger.info("Detected SpacetimeDB authentication handshake")
                        identity = headers.get("spacetime-identity")
                        token = headers.get("spacetime-identity-token")
                        
                        if identity and token:
                            self.logger.info("Received identity token, retrying with authentication")
                            
                            # Use AuthenticationManager for handshake processing
                            if self._auth_manager:
                                auth_result = self._auth_manager.handle_auth_handshake(identity, token)
                                
                                if auth_result.success:
                                    # Update legacy properties for backward compatibility
                                    with self._lock:
                                        self.spacetimedb_identity = identity
                                        self.spacetimedb_token = token
                                        self.auth_handshake_completed = True
                                        self.retry_with_auth = True
                                    
                                    self.logger.info("AuthenticationManager handshake completed successfully")
                                else:
                                    self.logger.error(f"AuthenticationManager handshake failed: {auth_result.error}")
                                    # Fall through to error handling
                                    return
                            else:
                                # Fallback to direct credential handling (backward compatibility)
                                with self._lock:
                                    self.spacetimedb_identity = identity
                                    self.spacetimedb_token = token
                                    self.auth_handshake_completed = True
                                    self.retry_with_auth = True
                                
                                # Store credentials for future use
                                if self.host and self.database_address:
                                    try:
                                        store_credentials(identity, token, self.host, self.database_address)
                                        self.logger.debug("Stored SpacetimeDB credentials for future use")
                                    except Exception as store_error:
                                        self.logger.warning(f"Failed to store credentials: {store_error}")
                            
                            # Schedule an immediate reconnect with authentication
                            # Use a small delay to avoid tight retry loops
                            self.logger.info("Scheduling immediate reconnect with acquired authentication")
                            threading.Timer(0.5, self._do_connect).start()
                            return
                        
                    # Create appropriate exception based on status code
                    elif status_code == 404:
                        database_name = self.database_address or "unknown"
                        
                        # Check for V1.1.2 specific 404 errors
                        if json_error_body:
                            error_msg = json_error_body.get("error", "")
                            if "v1/ws" in error_msg or "v1.1.2" in error_msg:
                                # V1.1.2 endpoint format error
                                error = WebSocketHandshakeError(
                                    status_code=status_code,
                                    status_message=f"V1.1.2 endpoint format error: {error_msg}",
                                    headers=headers,
                                    diagnostic_info={
                                        "url": self.connection_url,
                                        "protocol": self.protocol,
                                        "v112_error": error_msg,
                                        "suggested_fix": "Ensure db_identity parameter is provided and URL uses /v1/ws/ format"
                                    }
                                )
                            else:
                                # Regular 404 with JSON error body
                                db_check = self.diagnostics.check_database_exists(self.host, database_name)
                                
                                if db_check.get("exists") in [True, "likely"] and not db_check.get("published"):
                                    error = DatabaseNotPublishedError(
                                        database_name=database_name,
                                        host=self.host,
                                        diagnostic_info={
                                            "url": self.connection_url,
                                            "protocol": self.protocol,
                                            "headers": headers,
                                            "database_check": db_check,
                                            "v112_error": error_msg
                                        }
                                    )
                                else:
                                    error = DatabaseNotFoundError(
                                        database_name=database_name,
                                        status_code=status_code,
                                        server_message=error_msg,
                                        diagnostic_info={
                                            "url": self.connection_url,
                                            "protocol": self.protocol,
                                            "headers": headers,
                                            "database_check": db_check,
                                            "database_state": db_check.get("database_state", "unknown"),
                                            "confidence": db_check.get("confidence", "low"),
                                            "v112_error": error_msg
                                        },
                                        is_likely_unpublished=db_check.get("confidence") in ["medium", "high"]
                                    )
                        else:
                            # Regular 404 - run database check to determine if unpublished
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
                        # Check for V1.1.2 specific 400 errors
                        if json_error_body:
                            error_msg = json_error_body.get("error", "")
                            if "db_identity" in error_msg:
                                # Missing db_identity parameter
                                error = WebSocketHandshakeError(
                                    status_code=status_code,
                                    status_message=f"V1.1.2 parameter error: {error_msg}",
                                    headers=headers,
                                    diagnostic_info={
                                        "url": self.connection_url,
                                        "protocol": self.protocol,
                                        "v112_error": error_msg,
                                        "suggested_fix": "Provide db_identity parameter for V1.1.2 connections"
                                    }
                                )
                            else:
                                # Regular 400 error with JSON body
                                error = AuthenticationError(
                                    reason=f"HTTP {status_code}: {error_msg}",
                                    auth_method="Bearer" if self.spacetimedb_token else ("Basic" if self.auth_token else "None"),
                                    status_code=status_code
                                )
                        else:
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
        
        # Cancel connection timeout if still running
        self._cancel_connection_timeout()
        
        # Sync state with ConnectionManager
        with self._lock:
            self.state = self._connection_manager.get_connection_state()
        
        # Call error callbacks
        if self._on_error:
            self._on_error(error)
        
        # Call legacy callback for backward compatibility
        if self.on_error:
            try:
                self.on_error(error)
            except Exception as e:
                self.logger.error(f"Error in legacy error callback: {e}")
    
    def _on_ws_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket connection closed - sync with ConnectionManager state."""
        self.logger.debug(f"_on_ws_close: Callback triggered. Status: {close_status_code}, Msg: {close_msg}")
        
        # Sync state with ConnectionManager
        with self._lock:
            self.logger.debug("_on_ws_close: Acquired _lock.")
            
            # Sync state from ConnectionManager
            self.state = self._connection_manager.get_connection_state()
            self.ws = None
        
        # Call disconnect callback outside of lock to avoid deadlocks
        self.logger.info(f"Disconnected from SpacetimeDB (WebSocket closed). Reason: {close_msg or 'N/A'}")
        if self._on_disconnect:
            try:
                self._on_disconnect(close_msg or "Connection closed")
            except Exception as e:
                self.logger.error(ErrorFormatter.format_websocket_error("close callback", e), exc_info=True)
        
        # Call legacy callback for backward compatibility
        if self.on_disconnect:
            try:
                self.on_disconnect()
            except Exception as e:
                self.logger.error(ErrorFormatter.format_websocket_error("legacy on_disconnect callback", e), exc_info=True)
    
    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff and thread safety."""
        with self._lock:
            self.logger.debug(f"_schedule_reconnect called. Current state: {self.state.value}, auto_reconnect: {self.auto_reconnect}, attempts: {self.reconnect_attempts}")
            
            # Check if we should still reconnect (state may have changed)
            if not self.auto_reconnect or self.state == ConnectionState.CLOSED:
                self.logger.debug("_schedule_reconnect: Not scheduling (auto_reconnect False or state is CLOSED).")
                return
            
            # Check circuit breaker
            if self._is_circuit_breaker_open():
                self.logger.warning("_schedule_reconnect: Circuit breaker is open, skipping reconnect attempt")
                return
            
            # Check if we've exceeded max attempts
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                self.logger.error("_schedule_reconnect: Max reconnection attempts reached. Setting state to CLOSED.")
                self.state = ConnectionState.CLOSED
                return
            
            # Cancel any existing reconnect timer to avoid duplicates
            if self.reconnect_timer:
                self.reconnect_timer.cancel()
                self.reconnect_timer = None
            
            # Set state to RECONNECTING and calculate delay
            self.state = ConnectionState.RECONNECTING
            delay = min(
                self.initial_reconnect_delay * (2 ** self.reconnect_attempts),
                self.max_reconnect_delay
            )
            self.reconnect_attempts += 1
            
            self.logger.debug(f"_schedule_reconnect: Scheduling timer for {delay:.1f}s (attempt {self.reconnect_attempts}).")
            self.reconnect_timer = threading.Timer(delay, self._do_connect)
            self.reconnect_timer.start()
            self.logger.debug(f"_schedule_reconnect: Reconnect timer started for attempt {self.reconnect_attempts}.")
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open (preventing connections)."""
        if self.consecutive_failures < self.max_consecutive_failures:
            return False
        
        # Check if enough time has passed to try again
        current_time = time.time()
        if (current_time - self.circuit_breaker_last_failure) > self.circuit_breaker_timeout:
            self.logger.info("Circuit breaker timeout elapsed, allowing connection attempt")
            return False
        
        return True
    
    def _record_connection_failure(self, error: Exception) -> None:
        """Record a connection failure for circuit breaker logic."""
        self.consecutive_failures += 1
        self.circuit_breaker_last_failure = time.time()
        
        error_str = str(error).lower()
        is_transient = any(err_type in error_str for err_type in self.transient_error_types)
        
        self.logger.warning(
            f"Connection failure {self.consecutive_failures}/{self.max_consecutive_failures} "
            f"(transient: {is_transient}): {error}"
        )
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.logger.error(
                f"Circuit breaker triggered after {self.consecutive_failures} consecutive failures. "
                f"Connections will be blocked for {self.circuit_breaker_timeout}s"
            )
    
    def _record_connection_success(self) -> None:
        """Record a successful connection, resetting circuit breaker."""
        if self.consecutive_failures > 0:
            self.logger.info(f"Connection successful, resetting circuit breaker (was {self.consecutive_failures} failures)")
            self.consecutive_failures = 0
            self.circuit_breaker_last_failure = 0
    
    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if an error should trigger a retry."""
        error_str = str(error).lower()
        
        # Don't retry authentication errors (they won't resolve automatically)
        if any(auth_err in error_str for auth_err in ["authentication", "unauthorized", "forbidden"]):
            return False
        
        # Don't retry permanent errors
        if any(perm_err in error_str for perm_err in ["not found", "bad request"]):
            return False
        
        # Retry transient errors
        return any(trans_err in error_str for trans_err in self.transient_error_types)
    
    def _start_connection_timeout(self) -> None:
        """Start connection timeout timer."""
        if self.connection_timeout_timer:
            self.connection_timeout_timer.cancel()
        
        self.connection_timeout_timer = threading.Timer(
            self.connection_timeout,
            self._handle_connection_timeout
        )
        self.connection_timeout_timer.start()
        self.logger.debug(f"Started connection timeout timer ({self.connection_timeout}s)")
    
    def _cancel_connection_timeout(self) -> None:
        """Cancel connection timeout timer."""
        if self.connection_timeout_timer:
            self.connection_timeout_timer.cancel()
            self.connection_timeout_timer = None
            self.logger.debug("Cancelled connection timeout timer")
    
    def _handle_connection_timeout(self) -> None:
        """Handle connection timeout."""
        with self._lock:
            if self.state == ConnectionState.CONNECTING:
                self.logger.error(f"Connection timeout after {self.connection_timeout}s")
                
                # Create timeout error
                timeout_error = ConnectionTimeoutError(
                    operation="WebSocket connection",
                    timeout_seconds=self.connection_timeout,
                    retry_count=self.reconnect_attempts
                )
                
                # Record failure for circuit breaker
                self._record_connection_failure(timeout_error)
                
                # Clean up connection
                if self.ws:
                    try:
                        self.ws.close()
                    except Exception as e:
                        self.logger.debug(f"Error closing timed-out connection: {e}")
                
                # Trigger error callback
                if self._on_error:
                    self._on_error(timeout_error)
    
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
    
    def is_connected(self) -> bool:
        """Check if currently connected using ConnectionManager."""
        return self._connection_manager.is_connected()
    
    def get_connection_state(self) -> ConnectionState:
        """Get current connection state from ConnectionManager."""
        # Sync state for backward compatibility
        self.state = self._connection_manager.get_connection_state()
        return self.state
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information."""
        compression_info = self.get_compression_info()
        memory_stats = self.get_memory_stats()
        
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
            },
            "memory": {
                "total_mb": memory_stats["total_memory_estimate_mb"],
                "usage_percent": memory_stats["memory_accountant"]["usage_percent"],
                "pending_requests": memory_stats["request_tracker"]["pending_requests"],
                "request_tracker_mb": memory_stats["request_tracker"]["memory_mb"],
                "evicted_requests": memory_stats["request_tracker"]["evicted_requests"],
                "expired_requests": memory_stats["request_tracker"]["expired_requests"]
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
                        self.logger.error(ErrorFormatter.format_websocket_error("subscription state callback", e))
                        
            elif isinstance(server_message, SubscriptionError):
                for callback in self.subscription_state_callbacks:
                    try:
                        callback('subscription_error', server_message)
                    except Exception as e:
                        self.logger.error(ErrorFormatter.format_websocket_error("subscription error callback", e))
                        
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
    
    # Memory Management and Monitoring Methods
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive memory usage statistics for the WebSocket client.
        
        Returns:
            Dictionary containing memory usage for all components
        """
        request_stats = self.request_tracker.get_memory_stats()
        accountant_stats = self.memory_accountant.get_stats()
        
        return {
            'request_tracker': request_stats,
            'memory_accountant': {
                'total_bytes': accountant_stats.total_bytes,
                'total_mb': accountant_stats.total_bytes / (1024 * 1024),
                'cache_bytes': accountant_stats.cache_bytes,
                'subscription_bytes': accountant_stats.subscription_bytes,
                'request_bytes': accountant_stats.request_bytes,
                'message_bytes': accountant_stats.message_bytes,
                'peak_bytes': accountant_stats.peak_bytes,
                'peak_mb': accountant_stats.peak_bytes / (1024 * 1024),
                'evictions': accountant_stats.evictions,
                'oom_prevented': accountant_stats.oom_prevented,
                'usage_percent': self.memory_accountant.get_usage_percentage()
            },
            'active_subscriptions': len(self.active_subscriptions),
            'subscription_queries': len(self.subscription_queries),
            'total_memory_estimate_mb': (
                request_stats['memory_bytes'] + 
                accountant_stats.total_bytes
            ) / (1024 * 1024)
        }
    
    def check_memory_health(self) -> Dict[str, Any]:
        """
        Check memory health and return alerts/warnings.
        
        Returns:
            Dictionary with health status and any alerts
        """
        stats = self.get_memory_stats()
        alerts = []
        warnings = []
        
        # Check request tracker memory usage
        if stats['request_tracker']['memory_usage_percent'] > 80:
            alerts.append("Request tracker memory usage above 80%")
        elif stats['request_tracker']['memory_usage_percent'] > 60:
            warnings.append("Request tracker memory usage above 60%")
        
        # Check overall memory accountant usage
        if stats['memory_accountant']['usage_percent'] > 90:
            alerts.append("Overall memory usage above 90%")
        elif stats['memory_accountant']['usage_percent'] > 75:
            warnings.append("Overall memory usage above 75%")
        
        # Check for high eviction rates
        if stats['memory_accountant']['evictions'] > 100:
            warnings.append("High memory eviction rate detected")
        
        # Check request tracker size limits
        req_stats = stats['request_tracker']
        if req_stats['pending_requests'] > req_stats['max_size'] * 0.8:
            warnings.append("Pending requests approaching size limit")
        
        health_status = "healthy"
        if alerts:
            health_status = "critical"
        elif warnings:
            health_status = "warning"
        
        return {
            'status': health_status,
            'alerts': alerts,
            'warnings': warnings,
            'stats': stats,
            'recommendations': self._get_memory_recommendations(stats, alerts, warnings)
        }
    
    def _get_memory_recommendations(self, stats: Dict, alerts: List[str], warnings: List[str]) -> List[str]:
        """Generate memory optimization recommendations."""
        recommendations = []
        
        if stats['memory_accountant']['usage_percent'] > 75:
            recommendations.append("Consider reducing memory limits or increasing available memory")
        
        if stats['request_tracker']['evicted_requests'] > 50:
            recommendations.append("High request eviction rate - consider increasing max_size or reducing request timeout")
        
        if stats['request_tracker']['expired_requests'] > 100:
            recommendations.append("Many expired requests - consider reducing default timeout or improving response handling")
        
        if stats['request_tracker']['pending_requests'] > 1000:
            recommendations.append("Large number of pending requests - check for request handling bottlenecks")
        
        return recommendations
    
    def force_memory_cleanup(self) -> Dict[str, Any]:
        """
        Force immediate memory cleanup across all components.
        
        Returns:
            Statistics about the cleanup operation
        """
        self.logger.info("Forcing memory cleanup across all components")
        
        # Force request tracker cleanup
        cleanup_stats = self.request_tracker.force_cleanup()
        
        # Force subscription cleanup if available
        subscription_cleanup = 0
        if hasattr(self, 'subscription_metrics'):
            # Reset metrics to free memory
            self.subscription_metrics.reset_metrics()
            subscription_cleanup += 1
        
        # Log the results
        total_cleaned = sum(cleanup_stats.values()) + subscription_cleanup
        
        self.logger.info(
            f"Memory cleanup completed: {cleanup_stats['requests_cleaned']} requests, "
            f"{cleanup_stats['responses_cleaned']} responses, "
            f"{cleanup_stats['handlers_cleaned']} handlers, "
            f"{subscription_cleanup} subscription metrics reset"
        )
        
        return {
            'cleanup_stats': cleanup_stats,
            'subscription_cleanup': subscription_cleanup,
            'total_items_cleaned': total_cleaned,
            'memory_stats_after': self.get_memory_stats()
        }
    
    def log_memory_status(self, level: str = 'info') -> None:
        """
        Log current memory status.
        
        Args:
            level: Log level ('debug', 'info', 'warning', 'error')
        """
        health = self.check_memory_health()
        stats = health['stats']
        
        message = (
            f"Memory Status: {health['status']} | "
            f"Total: {stats['total_memory_estimate_mb']:.1f}MB | "
            f"Requests: {stats['request_tracker']['pending_requests']} | "
            f"Usage: {stats['memory_accountant']['usage_percent']:.1f}%"
        )
        
        if health['alerts']:
            message += f" | ALERTS: {', '.join(health['alerts'])}"
        if health['warnings']:
            message += f" | WARNINGS: {', '.join(health['warnings'])}"
        
        log_method = getattr(self.logger, level, self.logger.info)
        log_method(message)
    
    # Legacy API compatibility methods
    def subscribe(self, table_name: str, sql_query: str = None) -> QueryId:
        """
        Legacy API: Subscribe to a table or query.
        
        Args:
            table_name: Table name or full SQL query
            sql_query: SQL query string (optional, for backward compatibility)
            
        Returns:
            QueryId for the subscription
        """
        # Handle both signatures:
        # subscribe(table_name, sql_query) - legacy style
        # subscribe(query) - single argument style
        if sql_query is not None:
            query = sql_query
        else:
            query = table_name
            
        return self.subscribe_single(query)
    
    def send_raw_message(self, message: bytes) -> None:
        """
        Legacy API: Send raw message.
        
        Args:
            message: Raw message bytes
        """
        if self.ws:
            self.ws.send(message, opcode=websocket.ABNF.OPCODE_BINARY)
    
    # Legacy API properties for backward compatibility
    @property
    def connection_state(self) -> ConnectionState:
        """Legacy alias for state."""
        return self.state
    
    @connection_state.setter
    def connection_state(self, value: ConnectionState) -> None:
        """Legacy alias for state."""
        self.state = value
        # Sync with connection manager for API compatibility
        # This allows tests to set connection_state directly and have it work
        if hasattr(self, '_connection_manager') and self._connection_manager:
            # Access the private _state to sync for testing purposes
            with self._connection_manager._lock:
                self._connection_manager._state = value
    
    @property
    def ws_app(self) -> Optional[websocket.WebSocketApp]:
        """Legacy alias for ws."""
        return self.ws
    
    @ws_app.setter
    def ws_app(self, value: Optional[websocket.WebSocketApp]) -> None:
        """Legacy alias for ws."""
        self.ws = value
        # Sync with connection manager for API compatibility
        # This allows tests to set ws_app directly and have it work
        if hasattr(self, '_connection_manager') and self._connection_manager:
            with self._connection_manager._lock:
                self._connection_manager._connection = value
    
    # Legacy API compatibility for request tracking
    @property
    def pending_requests(self) -> 'LegacyRequestDict':
        """Legacy compatibility: access to pending requests via BoundedRequestTracker."""
        return LegacyRequestDict(self.request_tracker, 'requests')
    
    @property
    def request_responses(self) -> 'LegacyRequestDict':
        """Legacy compatibility: access to request responses via BoundedRequestTracker."""
        return LegacyRequestDict(self.request_tracker, 'responses')
    
    # Authentication methods using AuthenticationManager
    def get_authentication_state(self) -> str:
        """
        Get current authentication state.
        
        Returns:
            Authentication state as string
        """
        if self._auth_manager:
            return self._auth_manager.authentication_state.value
        return "unknown"
    
    def get_authentication_info(self) -> Dict[str, Any]:
        """
        Get authentication information for debugging/monitoring.
        
        Returns:
            Dict with authentication status info (no sensitive data)
        """
        if self._auth_manager:
            return self._auth_manager.get_auth_info()
        
        # Fallback to legacy properties
        return {
            "state": "unknown",
            "is_authenticated": self.auth_handshake_completed,
            "handshake_completed": self.auth_handshake_completed,
            "has_identity": self.spacetimedb_identity is not None,
            "has_token": self.spacetimedb_token is not None,
            "host": self.host,
            "database": self.database_address
        }
    
    def refresh_authentication(self) -> bool:
        """
        Refresh authentication credentials.
        
        Returns:
            True if refresh succeeded, False otherwise
        """
        if self._auth_manager:
            result = self._auth_manager.refresh_token()
            if result.success:
                self._sync_auth_state_from_manager()
                return True
            else:
                self.logger.warning(f"Authentication refresh failed: {result.error}")
                return False
        
        self.logger.warning("AuthenticationManager not available for refresh")
        return False
    
    def clear_authentication(self) -> None:
        """
        Clear all authentication state and stored credentials.
        
        This removes credentials from both memory and persistent storage.
        """
        if self._auth_manager:
            self._auth_manager.clear_stored_credentials()
        
        # Also clear legacy properties
        with self._lock:
            self.spacetimedb_identity = None
            self.spacetimedb_token = None
            self.auth_handshake_completed = False
            self.retry_with_auth = False
        
        self.logger.info("Authentication credentials cleared")
    
    def is_authenticated(self) -> bool:
        """
        Check if client is currently authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        if self._auth_manager:
            return self._auth_manager.is_authenticated
        
        # Fallback to legacy check
        return (
            self.spacetimedb_identity is not None and
            self.spacetimedb_token is not None and
            self.auth_handshake_completed
        )


class LegacyRequestDict:
    """
    Legacy compatibility wrapper for the new BoundedRequestTracker.
    
    Provides dict-like interface for backward compatibility with existing code
    that expects `pending_requests` and `request_responses` to be dicts.
    """
    
    def __init__(self, request_tracker: BoundedRequestTracker, dict_type: str):
        self._tracker = request_tracker
        self._type = dict_type
    
    def __setitem__(self, key, value):
        """Set an item (add request or response)."""
        if self._type == 'requests':
            self._tracker.add_request(key, value)
        elif self._type == 'responses':
            self._tracker.add_response_future(key, value)
    
    def __getitem__(self, key):
        """Get an item."""
        if self._type == 'requests':
            result = self._tracker.get_request(key)
        elif self._type == 'responses':
            result = self._tracker.get_response(key)
        else:
            result = None
        
        if result is None:
            raise KeyError(key)
        return result
    
    def __delitem__(self, key):
        """Delete an item."""
        if self._type == 'requests':
            if not self._tracker.remove_request(key):
                raise KeyError(key)
        elif self._type == 'responses':
            if not self._tracker.remove_response(key):
                raise KeyError(key)
    
    def __contains__(self, key):
        """Check if key exists."""
        if self._type == 'requests':
            return key in self._tracker.pending_requests
        elif self._type == 'responses':
            return key in self._tracker.response_futures
        return False
    
    def get(self, key: Any, default: Any = None) -> Any:
        """Get with default value."""
        try:
            return self[key]
        except KeyError:
            return default
    
    def pop(self, key: Any, default: Any = None) -> Any:
        """Pop an item."""
        try:
            value = self[key]
            del self[key]
            return value
        except KeyError:
            if default is not None:
                return default
            raise
    
    def clear(self) -> None:
        """Clear all items."""
        if self._type == 'requests':
            # Clear only requests
            request_ids = list(self._tracker.pending_requests.keys())
            for req_id in request_ids:
                self._tracker.remove_request(req_id)
        elif self._type == 'responses':
            # Clear only responses
            response_ids = list(self._tracker.response_futures.keys())
            for resp_id in response_ids:
                self._tracker.remove_response(resp_id)
    
    def __len__(self):
        """Get number of items."""
        if self._type == 'requests':
            return len(self._tracker.pending_requests)
        elif self._type == 'responses':
            return len(self._tracker.response_futures)
        return 0
