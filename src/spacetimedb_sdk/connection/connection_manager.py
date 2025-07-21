"""
Connection Manager for SpacetimeDB WebSocket Client

Focused connection lifecycle management extracted from WebSocketClient.
Handles only connection establishment, maintenance, and teardown with
proper dependency injection for testability.

Features:
- Single responsibility: connection lifecycle only
- Dependency injection for WebSocket factory and event handling
- Thread-safe operations with proper locking
- Connection state management and monitoring
- Health checking and circuit breaker pattern
- Comprehensive error handling and logging
- Performance metrics and monitoring hooks
"""

import logging
import threading
import time
import urllib.parse
import websocket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Dict, Any, Protocol
from weakref import WeakSet

from ..exceptions import (
    SpacetimeDBError,
    ConnectionTimeoutError,
    WebSocketHandshakeError,
    ValidationError
)
from ..validation.security_manager import get_security_manager
from ..validation.url_validator import validate_websocket_url
from ..validation.database_validator import validate_database_identifier
from ..utils.error_formatting import ErrorFormatter
from ..monitoring.metrics import monitor_performance


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state tracking."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class ConnectionMetrics:
    """Connection performance and health metrics."""
    connection_attempts: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    disconnections: int = 0
    reconnection_attempts: int = 0
    last_connection_time: Optional[float] = None
    last_disconnection_time: Optional[float] = None
    total_connection_time: float = 0.0
    average_connection_duration: float = 0.0
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    
    def record_connection_attempt(self) -> None:
        """Record a connection attempt."""
        self.connection_attempts += 1
    
    def record_connection_success(self) -> None:
        """Record a successful connection."""
        self.successful_connections += 1
        self.consecutive_failures = 0
        self.last_connection_time = time.time()
    
    def record_connection_failure(self) -> None:
        """Record a connection failure."""
        self.failed_connections += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
    
    def record_disconnection(self) -> None:
        """Record a disconnection."""
        self.disconnections += 1
        self.last_disconnection_time = time.time()
        
        # Update connection duration metrics
        if self.last_connection_time:
            duration = time.time() - self.last_connection_time
            self.total_connection_time += duration
            if self.successful_connections > 0:
                self.average_connection_duration = self.total_connection_time / self.successful_connections


@dataclass
class ConnectionConfig:
    """Configuration for connection manager."""
    host: str
    database_address: str
    auth_token: Optional[str] = None
    ssl_enabled: bool = True
    db_identity: Optional[str] = None
    protocol: str = "v1.json.spacetimedb"
    connection_timeout: float = 30.0
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    initial_reconnect_delay: float = 1.0
    max_reconnect_delay: float = 60.0
    enable_preflight_checks: bool = True
    retry_on_transient_errors: bool = True
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if not self.host:
            raise ValueError("host is required")
        
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
        
        if self.connection_timeout <= 0:
            raise ValueError("connection_timeout must be positive")
        if self.max_reconnect_attempts < 0:
            raise ValueError("max_reconnect_attempts must be non-negative")
        if self.initial_reconnect_delay <= 0:
            raise ValueError("initial_reconnect_delay must be positive")
        if self.max_reconnect_delay <= 0:
            raise ValueError("max_reconnect_delay must be positive")


class WebSocketFactory(Protocol):
    """Protocol for WebSocket factory dependency injection."""
    
    def create_websocket(
        self,
        url: str,
        on_open: Optional[Callable] = None,
        on_message: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        headers: Optional[Dict[str, str]] = None,
        subprotocols: Optional[list] = None
    ) -> websocket.WebSocketApp:
        """Create a WebSocket connection."""
        ...


class EventManager(Protocol):
    """Protocol for event manager dependency injection."""
    
    def emit_connection_opened(self) -> None:
        """Emit connection opened event."""
        ...
    
    def emit_connection_closed(self, reason: str) -> None:
        """Emit connection closed event."""
        ...
    
    def emit_connection_error(self, error: Exception) -> None:
        """Emit connection error event."""
        ...


class ConnectionDiagnostics(Protocol):
    """Protocol for connection diagnostics dependency injection."""
    
    def run_preflight_checks(
        self,
        host: str,
        database: str,
        raise_on_failure: bool = False
    ) -> Dict[str, Any]:
        """Run preflight connectivity checks."""
        ...


class DefaultWebSocketFactory:
    """Default WebSocket factory implementation."""
    
    def create_websocket(
        self,
        url: str,
        on_open: Optional[Callable] = None,
        on_message: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        headers: Optional[Dict[str, str]] = None,
        subprotocols: Optional[list] = None
    ) -> websocket.WebSocketApp:
        """Create a WebSocket connection using websocket-client library."""
        return websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            header=headers,
            subprotocols=subprotocols
        )


class NullEventManager:
    """Null object pattern event manager for optional event handling."""
    
    def emit_connection_opened(self) -> None:
        """No-op connection opened event."""
        pass
    
    def emit_connection_closed(self, reason: str) -> None:
        """No-op connection closed event."""
        pass
    
    def emit_connection_error(self, error: Exception) -> None:
        """No-op connection error event."""
        pass


class ConnectionManager:
    """
    Manages WebSocket connection lifecycle with dependency injection.
    
    Single responsibility: Handle connection establishment, maintenance,
    and teardown. All other concerns (message handling, subscriptions, etc.)
    are handled by other components.
    
    Features:
    - Thread-safe connection management
    - Connection state tracking and metrics
    - Automatic reconnection with exponential backoff
    - Circuit breaker pattern for failure protection
    - Comprehensive error handling and logging
    - Dependency injection for testability
    """
    
    def __init__(
        self,
        websocket_factory: Optional[WebSocketFactory] = None,
        event_manager: Optional[EventManager] = None,
        diagnostics: Optional[ConnectionDiagnostics] = None
    ):
        """
        Initialize connection manager with dependency injection.
        
        Args:
            websocket_factory: Factory for creating WebSocket connections
            event_manager: Manager for emitting connection events
            diagnostics: Connection diagnostics and preflight checks
        """
        self.logger = logging.getLogger(__name__)
        
        # Dependencies (use defaults if not provided)
        self._websocket_factory = websocket_factory or DefaultWebSocketFactory()
        self._event_manager = event_manager or NullEventManager()
        self._diagnostics = diagnostics
        
        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._connection: Optional[websocket.WebSocketApp] = None
        self._connection_thread: Optional[threading.Thread] = None
        self._config: Optional[ConnectionConfig] = None
        
        # Connection lifecycle tracking
        self._connection_start_time: Optional[float] = None
        self._connection_timeout_timer: Optional[threading.Timer] = None
        
        # Reconnection state
        self._reconnect_attempts = 0
        self._reconnect_timer: Optional[threading.Timer] = None
        
        # Circuit breaker state
        self._max_consecutive_failures = 5
        self._circuit_breaker_timeout = 60.0
        self._circuit_breaker_last_failure = 0
        self._transient_error_types = {
            "connection timeout", "connection refused", "connection reset",
            "network unreachable", "host unreachable", "temporary failure"
        }
        
        # Performance metrics
        self._metrics = ConnectionMetrics()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Store connection URL for error diagnostics
        self._connection_url: Optional[str] = None
        
        # Callback handlers (injected by WebSocketClient)
        self._on_open_callback: Optional[Callable] = None
        self._on_close_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None
        self._on_message_callback: Optional[Callable] = None
        
        self.logger.debug("ConnectionManager initialized with dependency injection")
    
    def set_callbacks(
        self,
        on_open: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_message: Optional[Callable] = None
    ) -> None:
        """Set callback handlers for WebSocket events."""
        with self._lock:
            self._on_open_callback = on_open
            self._on_close_callback = on_close
            self._on_error_callback = on_error
            self._on_message_callback = on_message
    
    @monitor_performance("connection_manager_connect")
    def connect(self, config: ConnectionConfig) -> None:
        """
        Establish WebSocket connection.
        
        Args:
            config: Connection configuration
            
        Raises:
            ValueError: If configuration is invalid
            ConnectionTimeoutError: If connection times out
            WebSocketHandshakeError: If WebSocket handshake fails
        """
        with self._lock:
            if self._state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
                self.logger.warning(f"Already connected or connecting (state: {self._state.value})")
                return
            
            # Validate configuration
            config.validate()
            self._config = config
            
            # Reset reconnection attempts for new connection
            self._reconnect_attempts = 0
            
            # Run preflight checks if enabled and diagnostics available
            if config.enable_preflight_checks and self._diagnostics:
                try:
                    self.logger.info("Running preflight checks...")
                    self._diagnostics.run_preflight_checks(
                        host=config.host,
                        database=config.database_address,
                        raise_on_failure=True
                    )
                    self.logger.info("Preflight checks passed")
                except Exception as e:
                    self.logger.error(f"Preflight checks failed: {e}")
                    self._event_manager.emit_connection_error(e)
                    raise
            
            self._do_connect()
    
    def disconnect(self) -> None:
        """
        Disconnect WebSocket connection and clean up resources.
        """
        self.logger.debug(f"Disconnect called. Current state: {self._state.value}")
        
        with self._lock:
            # Prevent further auto-reconnection attempts
            if self._config:
                self._config.auto_reconnect = False
            self._state = ConnectionState.CLOSED
            
            # Cancel timers
            self._cancel_reconnect_timer()
            self._cancel_connection_timeout()
            
            # Store references for cleanup outside lock
            current_connection = self._connection
            current_thread = self._connection_thread
            
            self.logger.debug(
                f"Disconnect: connection={'set' if current_connection else 'None'}, "
                f"thread={'alive' if current_thread and current_thread.is_alive() else 'stopped'}"
            )
        
        # Clean up connection outside lock to prevent deadlocks
        if current_connection:
            try:
                current_connection.close()
                self.logger.debug("Connection closed")
            except Exception as e:
                self.logger.error(f"Error closing connection: {e}")
        
        # Aggressive thread cleanup with shorter timeout
        if current_thread and current_thread.is_alive():
            self.logger.debug(f"Waiting for connection thread to stop...")
            
            # Try shorter timeout first
            current_thread.join(timeout=0.5)
            
            if current_thread.is_alive():
                self.logger.debug("Thread still alive, attempting more aggressive cleanup...")
                
                # Try to force close connection again
                if current_connection:
                    try:
                        # Force close the underlying socket if available
                        if hasattr(current_connection, 'sock') and current_connection.sock:
                            current_connection.sock.close()
                            self.logger.debug("Forced socket close")
                    except Exception as e:
                        self.logger.debug(f"Error forcing socket close: {e}")
                
                # Try one more time with very short timeout
                current_thread.join(timeout=0.2)
                
                if current_thread.is_alive():
                    self.logger.warning("Connection thread did not stop cleanly - this is expected in some cases")
                    # Don't block further - just set to None and continue
                else:
                    self.logger.debug("Connection thread stopped after aggressive cleanup")
            else:
                self.logger.debug("Connection thread stopped")
        
        # Final cleanup
        with self._lock:
            self._connection = None
            self._connection_thread = None
            self._connection_url = None
            self._metrics.record_disconnection()
        
        self.logger.info("Connection manager disconnected and cleaned up")
    
    def is_connected(self) -> bool:
        """
        Check if connection is currently active.
        
        Returns:
            True if connected, False otherwise
        """
        return self._state == ConnectionState.CONNECTED
    
    def get_connection_state(self) -> ConnectionState:
        """
        Get current connection state.
        
        Returns:
            Current connection state
        """
        return self._state
    
    def get_connection_metrics(self) -> ConnectionMetrics:
        """
        Get connection performance metrics.
        
        Returns:
            Copy of current connection metrics
        """
        with self._lock:
            # Return a copy to prevent external modification
            return ConnectionMetrics(
                connection_attempts=self._metrics.connection_attempts,
                successful_connections=self._metrics.successful_connections,
                failed_connections=self._metrics.failed_connections,
                disconnections=self._metrics.disconnections,
                reconnection_attempts=self._metrics.reconnection_attempts,
                last_connection_time=self._metrics.last_connection_time,
                last_disconnection_time=self._metrics.last_disconnection_time,
                total_connection_time=self._metrics.total_connection_time,
                average_connection_duration=self._metrics.average_connection_duration,
                consecutive_failures=self._metrics.consecutive_failures,
                last_failure_time=self._metrics.last_failure_time
            )
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get comprehensive connection information.
        
        Returns:
            Dictionary with connection details and metrics
        """
        with self._lock:
            return {
                "state": self._state.value,
                "url": self._connection_url,
                "config": {
                    "host": self._config.host if self._config else None,
                    "database": self._config.database_address if self._config else None,
                    "protocol": self._config.protocol if self._config else None,
                    "ssl_enabled": self._config.ssl_enabled if self._config else None,
                    "auto_reconnect": self._config.auto_reconnect if self._config else None,
                } if self._config else None,
                "reconnection": {
                    "attempts": self._reconnect_attempts,
                    "max_attempts": self._config.max_reconnect_attempts if self._config else None,
                    "scheduled": self._reconnect_timer is not None
                },
                "metrics": {
                    "connection_attempts": self._metrics.connection_attempts,
                    "successful_connections": self._metrics.successful_connections,
                    "failed_connections": self._metrics.failed_connections,
                    "success_rate": (
                        self._metrics.successful_connections / self._metrics.connection_attempts
                        if self._metrics.connection_attempts > 0 else 0.0
                    ),
                    "consecutive_failures": self._metrics.consecutive_failures,
                    "average_connection_duration": self._metrics.average_connection_duration
                }
            }
    
    def send_data(self, data: str | bytes) -> None:
        """
        Send data through the WebSocket connection.
        
        Args:
            data: Data to send
            
        Raises:
            RuntimeError: If not connected
        """
        with self._lock:
            if self._state != ConnectionState.CONNECTED or not self._connection:
                self.logger.debug(f"send_data failed: Not connected (ConnectionManager state: {self._state.value})")
                raise RuntimeError(f"Not connected (state: {self._state.value})")
            
            connection = self._connection
        
        # Send outside lock to prevent blocking
        try:
            if isinstance(data, str):
                connection.send(data)
            else:
                from websocket import ABNF
                connection.send(data, opcode=ABNF.OPCODE_BINARY)
        except Exception as e:
            self.logger.error(f"Error sending data: {e}")
            raise
    
    def _do_connect(self) -> None:
        """Internal connection logic with proper error handling."""
        if not self._config:
            raise RuntimeError("No configuration set")
        
        self.logger.debug(f"Attempting connection (attempt {self._reconnect_attempts + 1})")
        
        try:
            self._state = ConnectionState.CONNECTING
            self._metrics.record_connection_attempt()
            
            # Start connection timeout
            self._connection_start_time = time.time()
            self._start_connection_timeout()
            
            # Build connection URL
            url = self._build_connection_url(self._config)
            self._connection_url = url
            
            # Prepare headers
            headers = self._build_connection_headers(self._config)
            
            # Create WebSocket connection
            self._connection = self._websocket_factory.create_websocket(
                url=url,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
                headers=headers,
                subprotocols=[self._config.protocol]
            )
            
            # Start connection in separate thread
            self._connection_thread = threading.Thread(
                target=self._connection.run_forever,
                daemon=True,
                name=f"ConnectionManager-Thread-{id(self)}"
            )
            self._connection_thread.start()
            
            self.logger.debug(f"Connection thread started for {url}")
            
        except Exception as e:
            self.logger.error(f"Connection attempt failed: {e}")
            self._state = ConnectionState.DISCONNECTED
            self._metrics.record_connection_failure()
            self._event_manager.emit_connection_error(e)
            
            # Schedule reconnect if appropriate
            if self._config and self._config.auto_reconnect and self._should_retry_error(e):
                self._schedule_reconnect()
            else:
                raise
    
    def _build_connection_url(self, config: ConnectionConfig) -> str:
        """Build WebSocket connection URL with security validation."""
        protocol_scheme = "wss" if config.ssl_enabled else "ws"
        
        # Validate and sanitize host
        try:
            parsed_host = urllib.parse.urlparse(f"{protocol_scheme}://{config.host}")
            host = parsed_host.hostname
            port = parsed_host.port
            
            if not host:
                raise ValidationError(f"Invalid host: {config.host}")
            
            # Security validation
            security_manager = get_security_manager()
            if security_manager:
                test_url = f"{protocol_scheme}://{host}"
                host_result = security_manager.validate_url(test_url, "host")
                if not host_result.is_valid:
                    raise ValidationError(f"Invalid host: {'; '.join(str(e) for e in host_result.errors)}")
            
            validated_host = f"{host}:{port}" if port else host
            
        except ValidationError as e:
            raise WebSocketHandshakeError(f"Invalid host: {e}")
        
        # Validate database identifier
        db_identifier = config.db_identity if config.db_identity else config.database_address
        
        # For V1.1.2 compatibility: if both are empty, use a default fallback
        if not db_identifier:
            db_identifier = "default"  # Default fallback when both identifiers are empty
        
        try:
            validation_result = validate_database_identifier(db_identifier)
            if not validation_result.is_valid:
                error_messages = [str(error) for error in validation_result.errors]
                raise ValidationError(f"Database identifier validation failed: {'; '.join(error_messages)}")
            validated_db_identifier = urllib.parse.quote(validation_result.sanitized_value, safe='')
        except ValidationError as e:
            raise WebSocketHandshakeError(f"Invalid database identifier: {e}")
        
        # Build URL
        if config.db_identity:
            try:
                validation_result = validate_database_identifier(config.db_identity)
                if not validation_result.is_valid:
                    error_messages = [str(error) for error in validation_result.errors]
                    raise ValidationError(f"Database identity validation failed: {'; '.join(error_messages)}")
                validated_db_identity = validation_result.sanitized_value
            except ValidationError as e:
                raise WebSocketHandshakeError(f"Invalid db_identity parameter: {e}")
            
            url = (f"{protocol_scheme}://{validated_host}/v1/ws/database/"
                   f"{validated_db_identifier}/subscribe?db_identity="
                   f"{urllib.parse.quote(validated_db_identity, safe='')}")
        else:
            url = (f"{protocol_scheme}://{validated_host}/v1/database/"
                   f"{validated_db_identifier}/subscribe")
        
        # Final URL validation
        try:
            url_result = validate_websocket_url(url, "connection_url")
            if not url_result.is_valid:
                raise ValidationError(f"Invalid connection URL: {'; '.join(str(e) for e in url_result.errors)}")
            url = url_result.sanitized_value
        except ValidationError as e:
            raise WebSocketHandshakeError(f"Invalid connection URL: {e}")
        
        return url
    
    def _build_connection_headers(self, config: ConnectionConfig) -> Dict[str, str]:
        """Build connection headers including authentication."""
        headers = {}
        
        if config.auth_token:
            import base64
            token_bytes = f"token:{config.auth_token}".encode('utf-8')
            base64_str = base64.b64encode(token_bytes).decode('utf-8')
            headers["Authorization"] = f"Basic {base64_str}"
        
        return headers
    
    def _on_ws_open(self, ws) -> None:
        """WebSocket connection opened handler."""
        self.logger.debug(f"WebSocket opened (thread: {threading.get_ident()})")
        
        with self._lock:
            self._state = ConnectionState.CONNECTED
            self._reconnect_attempts = 0
            self._metrics.record_connection_success()
            
            # Cancel connection timeout
            self._cancel_connection_timeout()
        
        self.logger.info("Connected to SpacetimeDB")
        
        # Emit event
        self._event_manager.emit_connection_opened()
        
        # Call user callback
        if self._on_open_callback:
            try:
                self._on_open_callback(ws)
            except Exception as e:
                self.logger.error(f"Error in open callback: {e}")
    
    def _on_ws_message(self, ws, message) -> None:
        """WebSocket message received handler."""
        if self._on_message_callback:
            try:
                self._on_message_callback(ws, message)
            except Exception as e:
                self.logger.error(f"Error in message callback: {e}")
    
    def _on_ws_error(self, ws, error) -> None:
        """WebSocket error handler."""
        self.logger.error(f"WebSocket error: {error}")
        
        with self._lock:
            self._metrics.record_connection_failure()
        
        # Emit event
        self._event_manager.emit_connection_error(error)
        
        # Call user callback
        if self._on_error_callback:
            try:
                self._on_error_callback(ws, error)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    def _on_ws_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket connection closed handler."""
        self.logger.debug(f"WebSocket closed (status: {close_status_code}, message: {close_msg})")
        
        with self._lock:
            original_state = self._state
            
            # Cancel connection timeout
            self._cancel_connection_timeout()
            
            # Update state if not already closed
            if self._state != ConnectionState.CLOSED:
                self._state = ConnectionState.DISCONNECTED
            
            # Determine if reconnection should be attempted
            should_reconnect = (
                self._config and
                self._config.auto_reconnect and
                self._state != ConnectionState.CLOSED and
                original_state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING, ConnectionState.RECONNECTING]
            )
        
        self.logger.info(f"Disconnected from SpacetimeDB. Reason: {close_msg or 'N/A'}")
        
        # Emit event
        self._event_manager.emit_connection_closed(close_msg or "Connection closed")
        
        # Call user callback
        if self._on_close_callback:
            try:
                self._on_close_callback(ws, close_status_code, close_msg)
            except Exception as e:
                self.logger.error(f"Error in close callback: {e}")
        
        # Schedule reconnect if needed
        if should_reconnect:
            self.logger.info("Scheduling reconnection attempt")
            self._schedule_reconnect()
    
    def _schedule_reconnect(self) -> None:
        """Schedule reconnection attempt with exponential backoff."""
        with self._lock:
            if not self._config or not self._config.auto_reconnect or self._state == ConnectionState.CLOSED:
                return
            
            # Check circuit breaker
            if self._is_circuit_breaker_open():
                self.logger.warning("Circuit breaker open, skipping reconnect")
                return
            
            # Check max attempts
            if self._reconnect_attempts >= self._config.max_reconnect_attempts:
                self.logger.error("Max reconnection attempts reached")
                self._state = ConnectionState.CLOSED
                return
            
            # Cancel existing timer
            self._cancel_reconnect_timer()
            
            # Calculate delay with exponential backoff
            delay = min(
                self._config.initial_reconnect_delay * (2 ** self._reconnect_attempts),
                self._config.max_reconnect_delay
            )
            
            self._state = ConnectionState.RECONNECTING
            self._reconnect_attempts += 1
            
            self.logger.debug(f"Scheduling reconnect in {delay:.1f}s (attempt {self._reconnect_attempts})")
            
            self._reconnect_timer = threading.Timer(delay, self._do_connect)
            self._reconnect_timer.start()
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._metrics.consecutive_failures < self._max_consecutive_failures:
            return False
        
        current_time = time.time()
        if (current_time - self._circuit_breaker_last_failure) > self._circuit_breaker_timeout:
            self.logger.info("Circuit breaker timeout elapsed, allowing connection attempt")
            return False
        
        return True
    
    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if error should trigger retry."""
        error_str = str(error).lower()
        
        # Don't retry authentication errors
        if any(auth_err in error_str for auth_err in ["authentication", "unauthorized", "forbidden"]):
            return False
        
        # Don't retry permanent errors
        if any(perm_err in error_str for perm_err in ["not found", "bad request"]):
            return False
        
        # Retry transient errors
        return any(trans_err in error_str for trans_err in self._transient_error_types)
    
    def _start_connection_timeout(self) -> None:
        """Start connection timeout timer."""
        if not self._config:
            return
        
        if self._connection_timeout_timer:
            self._connection_timeout_timer.cancel()
        
        self._connection_timeout_timer = threading.Timer(
            self._config.connection_timeout,
            self._on_connection_timeout
        )
        self._connection_timeout_timer.start()
    
    def _cancel_connection_timeout(self) -> None:
        """Cancel connection timeout timer."""
        if self._connection_timeout_timer:
            self._connection_timeout_timer.cancel()
            self._connection_timeout_timer = None
    
    def _cancel_reconnect_timer(self) -> None:
        """Cancel reconnect timer."""
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None
    
    def _on_connection_timeout(self) -> None:
        """Handle connection timeout."""
        self.logger.error("Connection timeout")
        
        with self._lock:
            if self._state == ConnectionState.CONNECTING:
                self._state = ConnectionState.ERROR
                self._metrics.record_connection_failure()
        
        # Force close connection
        if self._connection:
            try:
                self._connection.close()
            except Exception as e:
                self.logger.error(f"Error closing timed out connection: {e}")
        
        # Emit error event
        error = ConnectionTimeoutError(
            operation="connection_attempt",
            timeout_seconds=self._config.connection_timeout,
            retry_count=self._reconnect_attempts
        )
        self._event_manager.emit_connection_error(error)
        
        # Schedule reconnect if appropriate
        if self._config and self._config.auto_reconnect:
            self._schedule_reconnect()