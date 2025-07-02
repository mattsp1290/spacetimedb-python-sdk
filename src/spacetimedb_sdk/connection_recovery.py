"""
Connection Recovery and Retry Logic for SpacetimeDB

Provides automatic recovery from protocol errors and connection failures
with intelligent retry strategies.
"""

import asyncio
import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum
from dataclasses import dataclass
import random


class ProtocolErrorType(Enum):
    """Types of protocol errors that can be recovered from."""
    UNKNOWN_TAG = "unknown_tag"
    INVALID_CLOSE_FRAME = "invalid_close_frame"
    PROTOCOL_MISMATCH = "protocol_mismatch"
    FRAME_TYPE_CONFLICT = "frame_type_conflict"
    MESSAGE_FORMAT_ERROR = "message_format_error"
    WEBSOCKET_ERROR = "websocket_error"
    CONNECTION_TIMEOUT = "connection_timeout"
    HANDSHAKE_ERROR = "handshake_error"


@dataclass
class RecoveryAttempt:
    """Information about a recovery attempt."""
    attempt_number: int
    error_type: ProtocolErrorType
    error_message: str
    timestamp: float
    success: bool
    recovery_time: Optional[float] = None


@dataclass
class ConnectionHealth:
    """Tracks connection health metrics."""
    last_successful_message: float
    last_error: Optional[str]
    error_count: int
    recovery_count: int
    uptime_start: float
    protocol_errors: List[RecoveryAttempt]


class RobustConnectionManager:
    """
    Connection manager with protocol error recovery and intelligent retry logic.
    
    Features:
    - Automatic recovery from protocol errors
    - Exponential backoff with jitter
    - Circuit breaker pattern for persistent failures
    - Health monitoring and diagnostics
    """
    
    def __init__(
        self,
        max_retries: int = 5,
        retry_delays: List[float] = None,
        circuit_breaker_threshold: int = 10,
        health_check_interval: float = 30.0
    ):
        """
        Initialize connection recovery manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delays: List of delays between retries (seconds)
            circuit_breaker_threshold: Number of failures before circuit opens
            health_check_interval: Interval for health checks (seconds)
        """
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [1, 2, 4, 8, 16]
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.health_check_interval = health_check_interval
        
        # Protocol error patterns that can be recovered from
        self.recoverable_errors = {
            "unknown tag": ProtocolErrorType.UNKNOWN_TAG,
            "invalid close frame": ProtocolErrorType.INVALID_CLOSE_FRAME,
            "protocol mismatch": ProtocolErrorType.PROTOCOL_MISMATCH,
            "frame type conflict": ProtocolErrorType.FRAME_TYPE_CONFLICT,
            "received text frame with binary protocol": ProtocolErrorType.FRAME_TYPE_CONFLICT,
            "received binary frame with text protocol": ProtocolErrorType.FRAME_TYPE_CONFLICT,
            "connection timed out": ProtocolErrorType.CONNECTION_TIMEOUT,
            "handshake error": ProtocolErrorType.HANDSHAKE_ERROR,
            "websocket error": ProtocolErrorType.WEBSOCKET_ERROR
        }
        
        # Connection state
        self.health = ConnectionHealth(
            last_successful_message=time.time(),
            last_error=None,
            error_count=0,
            recovery_count=0,
            uptime_start=time.time(),
            protocol_errors=[]
        )
        
        # Circuit breaker state
        self.circuit_open = False
        self.circuit_open_time: Optional[float] = None
        self.circuit_reset_timeout = 60.0  # 1 minute
        
        # Callbacks
        self.on_recovery_started: Optional[Callable[[ProtocolErrorType, str], None]] = None
        self.on_recovery_completed: Optional[Callable[[RecoveryAttempt], None]] = None
        self.on_circuit_breaker_opened: Optional[Callable[[], None]] = None
        self.on_circuit_breaker_closed: Optional[Callable[[], None]] = None
        
        self.logger = logging.getLogger(__name__)
    
    def is_recoverable_error(self, error_message: str) -> Optional[ProtocolErrorType]:
        """
        Check if an error is recoverable.
        
        Args:
            error_message: Error message to check
            
        Returns:
            ProtocolErrorType if recoverable, None otherwise
        """
        error_lower = error_message.lower()
        
        for pattern, error_type in self.recoverable_errors.items():
            if pattern in error_lower:
                return error_type
        
        return None
    
    async def connect_with_recovery(
        self,
        connect_func: Callable[[], Any],
        test_func: Optional[Callable[[], Any]] = None
    ) -> Any:
        """
        Connect with automatic retry on protocol errors.
        
        Args:
            connect_func: Function to establish connection
            test_func: Optional function to test connection health
            
        Returns:
            Connection object
            
        Raises:
            ConnectionError: If all retry attempts fail
        """
        if self.circuit_open:
            await self._check_circuit_breaker()
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Connection attempt {attempt + 1}/{self.max_retries}")
                
                # Attempt connection
                connection = await self._execute_with_timeout(connect_func)
                
                # Test connection if test function provided
                if test_func:
                    await self._test_connection_health(test_func)
                
                # Reset circuit breaker on success
                if self.circuit_open:
                    await self._close_circuit_breaker()
                
                # Reset error count
                self.health.error_count = 0
                self.health.last_successful_message = time.time()
                
                self.logger.info(f"✅ Connected successfully on attempt {attempt + 1}")
                return connection
                
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Check if it's a recoverable protocol error
                error_type = self.is_recoverable_error(error_msg)
                
                if error_type:
                    await self._handle_recoverable_error(error_type, str(e), attempt)
                    
                    # Calculate delay with exponential backoff and jitter
                    delay = self._calculate_retry_delay(attempt)
                    
                    self.logger.warning(
                        f"Protocol error on attempt {attempt + 1}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    # Non-recoverable error
                    self.logger.error(f"Non-recoverable error: {e}")
                    raise e
        
        # All retry attempts failed
        await self._handle_connection_failure(last_error)
        raise ConnectionError(
            f"Failed to connect after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
    
    async def _handle_recoverable_error(
        self,
        error_type: ProtocolErrorType,
        error_message: str,
        attempt: int
    ) -> None:
        """Handle a recoverable protocol error."""
        self.health.error_count += 1
        self.health.last_error = error_message
        
        # Create recovery attempt record
        recovery_attempt = RecoveryAttempt(
            attempt_number=attempt + 1,
            error_type=error_type,
            error_message=error_message,
            timestamp=time.time(),
            success=False  # Will be updated if recovery succeeds
        )
        
        self.health.protocol_errors.append(recovery_attempt)
        
        # Notify recovery started
        if self.on_recovery_started:
            try:
                self.on_recovery_started(error_type, error_message)
            except Exception as e:
                self.logger.error(f"Error in recovery started callback: {e}")
        
        # Check circuit breaker threshold
        if self.health.error_count >= self.circuit_breaker_threshold:
            await self._open_circuit_breaker()
    
    async def _test_connection_health(self, test_func: Callable[[], Any]) -> None:
        """Test connection health with timeout."""
        try:
            await asyncio.wait_for(
                self._execute_with_timeout(test_func),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            raise ConnectionError("Connection test timeout - protocol may be broken")
    
    async def _execute_with_timeout(self, func: Callable[[], Any], timeout: float = 30.0) -> Any:
        """Execute function with timeout."""
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(func(), timeout=timeout)
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, func),
                timeout=timeout
            )
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        if attempt < len(self.retry_delays):
            base_delay = self.retry_delays[attempt]
        else:
            # Use last delay for additional attempts
            base_delay = self.retry_delays[-1]
        
        # Add jitter (±25%)
        jitter = random.uniform(0.75, 1.25)
        return base_delay * jitter
    
    async def _open_circuit_breaker(self) -> None:
        """Open circuit breaker to prevent further attempts."""
        if not self.circuit_open:
            self.circuit_open = True
            self.circuit_open_time = time.time()
            
            self.logger.warning(
                f"Circuit breaker opened after {self.health.error_count} failures. "
                f"Will retry after {self.circuit_reset_timeout}s"
            )
            
            if self.on_circuit_breaker_opened:
                try:
                    self.on_circuit_breaker_opened()
                except Exception as e:
                    self.logger.error(f"Error in circuit breaker opened callback: {e}")
    
    async def _close_circuit_breaker(self) -> None:
        """Close circuit breaker after successful connection."""
        if self.circuit_open:
            self.circuit_open = False
            self.circuit_open_time = None
            
            self.logger.info("Circuit breaker closed - connection recovered")
            
            if self.on_circuit_breaker_closed:
                try:
                    self.on_circuit_breaker_closed()
                except Exception as e:
                    self.logger.error(f"Error in circuit breaker closed callback: {e}")
    
    async def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker should be reset."""
        if (self.circuit_open and self.circuit_open_time and 
            time.time() - self.circuit_open_time > self.circuit_reset_timeout):
            
            self.logger.info("Circuit breaker timeout reached, allowing retry attempt")
            self.circuit_open = False
            self.circuit_open_time = None
    
    async def _handle_connection_failure(self, last_error: Exception) -> None:
        """Handle final connection failure."""
        self.health.last_error = str(last_error)
        
        # Mark last recovery attempt as failed
        if self.health.protocol_errors:
            self.health.protocol_errors[-1].success = False
    
    async def with_connection_recovery(
        self,
        operation: Callable[[], Any],
        max_operation_retries: int = 3
    ) -> Any:
        """
        Execute operation with automatic connection recovery.
        
        Args:
            operation: Operation to execute
            max_operation_retries: Max retries for the operation
            
        Returns:
            Operation result
        """
        for attempt in range(max_operation_retries):
            try:
                result = await self._execute_with_timeout(operation)
                
                # Update health on success
                self.health.last_successful_message = time.time()
                
                return result
                
            except Exception as e:
                error_type = self.is_recoverable_error(str(e))
                
                if error_type and attempt < max_operation_retries - 1:
                    self.logger.warning(
                        f"Operation failed with recoverable error: {e}. "
                        f"Attempt {attempt + 1}/{max_operation_retries}"
                    )
                    
                    # Short delay for operation retries
                    await asyncio.sleep(1.0)
                    continue
                else:
                    raise e
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get connection health metrics."""
        current_time = time.time()
        uptime = current_time - self.health.uptime_start
        time_since_last_message = current_time - self.health.last_successful_message
        
        return {
            "uptime_seconds": uptime,
            "time_since_last_message": time_since_last_message,
            "error_count": self.health.error_count,
            "recovery_count": self.health.recovery_count,
            "circuit_open": self.circuit_open,
            "last_error": self.health.last_error,
            "total_protocol_errors": len(self.health.protocol_errors),
            "recent_errors": [
                {
                    "type": attempt.error_type.value,
                    "message": attempt.error_message,
                    "timestamp": attempt.timestamp,
                    "success": attempt.success
                }
                for attempt in self.health.protocol_errors[-5:]  # Last 5 errors
            ]
        }
    
    def reset_health_metrics(self) -> None:
        """Reset health metrics."""
        self.health = ConnectionHealth(
            last_successful_message=time.time(),
            last_error=None,
            error_count=0,
            recovery_count=0,
            uptime_start=time.time(),
            protocol_errors=[]
        )
        
        self.circuit_open = False
        self.circuit_open_time = None


class ThreadedConnectionManager(RobustConnectionManager):
    """
    Threaded version of RobustConnectionManager for synchronous environments.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()
    
    def _start_event_loop(self) -> None:
        """Start event loop in background thread."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        # Wait for loop to be ready
        while self._loop is None:
            time.sleep(0.01)
    
    def connect_with_recovery_sync(
        self,
        connect_func: Callable[[], Any],
        test_func: Optional[Callable[[], Any]] = None
    ) -> Any:
        """Synchronous version of connect_with_recovery."""
        return asyncio.run_coroutine_threadsafe(
            self.connect_with_recovery(connect_func, test_func),
            self._loop
        ).result()
    
    def with_connection_recovery_sync(
        self,
        operation: Callable[[], Any],
        max_operation_retries: int = 3
    ) -> Any:
        """Synchronous version of with_connection_recovery."""
        return asyncio.run_coroutine_threadsafe(
            self.with_connection_recovery(operation, max_operation_retries),
            self._loop
        ).result()
    
    def shutdown(self) -> None:
        """Shutdown the event loop and thread."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)


# Convenience functions
def create_recovery_manager(
    max_retries: int = 5,
    use_threaded: bool = False,
    **kwargs
) -> RobustConnectionManager:
    """
    Create a connection recovery manager.
    
    Args:
        max_retries: Maximum retry attempts
        use_threaded: Use threaded version for sync environments
        **kwargs: Additional configuration options
        
    Returns:
        Connection recovery manager
    """
    if use_threaded:
        return ThreadedConnectionManager(max_retries=max_retries, **kwargs)
    else:
        return RobustConnectionManager(max_retries=max_retries, **kwargs)


def is_protocol_error(error_message: str) -> bool:
    """
    Check if an error message indicates a protocol error.
    
    Args:
        error_message: Error message to check
        
    Returns:
        True if it's a protocol error
    """
    manager = RobustConnectionManager()
    return manager.is_recoverable_error(error_message) is not None