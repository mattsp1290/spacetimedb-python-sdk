"""
Shared types and protocols for connection management.

This module contains shared data structures and protocols used by both
connection_builder.py and connection_pool.py to avoid circular imports.
"""

from typing import Protocol, Optional, Callable, Any, Dict, runtime_checkable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import time
import random


# Shared data structures

class PooledConnectionState(Enum):
    """State of a pooled connection."""
    IDLE = "idle"
    ACTIVE = "active"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"
    CLOSED = "closed"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ConnectionHealth:
    """Health metrics for a connection."""
    connection_id: str
    state: PooledConnectionState
    last_successful_operation: float
    last_failed_operation: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    latency_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    operations_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    
    def record_success(self, latency_ms: float) -> None:
        """Record a successful operation."""
        self.last_successful_operation = time.time()
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.latency_samples.append(latency_ms)
        self.operations_count += 1
        self._update_metrics()
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.last_failed_operation = time.time()
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.operations_count += 1
        self._update_metrics()
    
    def _update_metrics(self) -> None:
        """Update computed metrics."""
        if self.latency_samples:
            sorted_samples = sorted(self.latency_samples)
            self.avg_latency_ms = sum(sorted_samples) / len(sorted_samples)
            self.p95_latency_ms = sorted_samples[int(len(sorted_samples) * 0.95)]
            self.p99_latency_ms = sorted_samples[int(len(sorted_samples) * 0.99)]
        
        # Calculate error rate over last 100 operations
        if self.operations_count > 0:
            recent_errors = min(self.consecutive_failures, 100)
            self.error_rate = recent_errors / min(self.operations_count, 100)


@dataclass
class CircuitBreaker:
    """Circuit breaker for connection failure handling."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_requests: int = 3
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0
    half_open_successes: int = 0
    
    def record_success(self) -> None:
        """Record a successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_requests:
                self.close()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.open()
        elif self.failure_count >= self.failure_threshold:
            self.open()
    
    def open(self) -> None:
        """Open the circuit (stop allowing requests)."""
        self.state = CircuitState.OPEN
        self.half_open_successes = 0
    
    def close(self) -> None:
        """Close the circuit (resume normal operation)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_successes = 0
    
    def attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
        return self.state != CircuitState.OPEN
    
    def is_available(self) -> bool:
        """Check if the circuit allows requests."""
        if self.state == CircuitState.OPEN:
            return self.attempt_reset()
        return True


@dataclass
class RetryPolicy:
    """Advanced retry policy with jittered exponential backoff."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay for given attempt."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            # Add random jitter (±25%)
            jitter_factor = 0.75 + (random.random() * 0.5)
            delay *= jitter_factor
        
        return delay


# Protocol definitions for type hints

@runtime_checkable
class ConnectionBuilderProtocol(Protocol):
    """Protocol for SpacetimeDBConnectionBuilder to avoid circular imports."""
    
    def with_uri(self, uri: str) -> 'ConnectionBuilderProtocol':
        """Set the connection URI."""
        ...
    
    def with_module_name(self, module_name: str) -> 'ConnectionBuilderProtocol':
        """Set the module/database name."""
        ...
    
    def with_token(self, token: str) -> 'ConnectionBuilderProtocol':
        """Set the authentication token."""
        ...
    
    def with_protocol(self, protocol: str) -> 'ConnectionBuilderProtocol':
        """Set the communication protocol."""
        ...
    
    def build(self) -> Any:  # Returns ModernSpacetimeDBClient
        """Build and return the configured client."""
        ...
    
    def build_pool(self) -> 'ConnectionPoolProtocol':
        """Build a connection pool instead of a single client."""
        ...


@runtime_checkable
class ConnectionPoolProtocol(Protocol):
    """Protocol for ConnectionPool to avoid circular imports."""
    
    def get_connection(self) -> Optional[Any]:  # Returns PooledConnection
        """Get an available connection from the pool."""
        ...
    
    def release_connection(self, connection: Any) -> None:
        """Release a connection back to the pool."""
        ...
    
    def execute_with_retry(
        self,
        operation: Callable[[Any], Any],
        operation_name: str = "operation"
    ) -> Any:
        """Execute an operation with retry logic."""
        ...
    
    def get_pool_metrics(self) -> Dict[str, Any]:
        """Get comprehensive pool metrics."""
        ...
    
    def shutdown(self, graceful: bool = True, timeout: float = 30.0) -> None:
        """Shutdown the connection pool."""
        ...


@runtime_checkable
class ModernSpacetimeDBClientProtocol(Protocol):
    """Protocol for ModernSpacetimeDBClient to avoid circular imports."""
    
    @classmethod
    def builder(cls) -> ConnectionBuilderProtocol:
        """Create a new connection builder."""
        ...
    
    def connect(
        self,
        auth_token: Optional[str] = None,
        host: str = "localhost:3000",
        database_address: Optional[str] = None,
        ssl_enabled: bool = True,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_identity: Optional[Callable[[str, Any, Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ) -> None:
        """Connect to SpacetimeDB."""
        ...
    
    def disconnect(self) -> None:
        """Disconnect from SpacetimeDB."""
        ...
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        ...
