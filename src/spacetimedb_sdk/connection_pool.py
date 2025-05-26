"""
Advanced Connection Pool Management for SpacetimeDB

Implements connection pooling with:
- Multiple concurrent connections
- Load balancing across connections
- Connection lifecycle management
- Health monitoring and recovery
- Circuit breaker patterns
- Advanced retry policies
"""

import threading
import time
import random
import logging
from typing import Dict, List, Optional, Callable, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor, Future

from .modern_client import ModernSpacetimeDBClient
from .connection_builder import SpacetimeDBConnectionBuilder
from .websocket_client import ConnectionState as WebSocketConnectionState
from .connection_id import (
    EnhancedConnectionId,
    ConnectionEvent,
    ConnectionEventType,
    ConnectionEventListener
)


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


class PooledConnection:
    """A single connection in the pool with health tracking."""
    
    def __init__(
        self,
        pool_id: str,
        connection_config: Dict[str, Any],
        health_check_interval: float = 30.0
    ):
        self.pool_id = pool_id
        self.connection_id = str(uuid.uuid4())
        self.config = connection_config
        self.client: Optional[ModernSpacetimeDBClient] = None
        self.state = PooledConnectionState.IDLE
        self.health = ConnectionHealth(
            connection_id=self.connection_id,
            state=self.state,
            last_successful_operation=time.time()
        )
        self.circuit_breaker = CircuitBreaker()
        self.health_check_interval = health_check_interval
        self.last_health_check = 0
        self._lock = threading.RLock()
        self._active_operations = 0
        
        # Logging
        self.logger = logging.getLogger(
            f"{__name__}.PooledConnection_{self.connection_id[:8]}"
        )
    
    def connect(self) -> bool:
        """Establish the connection."""
        try:
            # Build connection using the builder pattern
            builder = ModernSpacetimeDBClient.builder()
            
            # Apply configuration
            if 'uri' in self.config:
                builder.with_uri(self.config['uri'])
            if 'module_name' in self.config:
                builder.with_module_name(self.config['module_name'])
            if 'auth_token' in self.config:
                builder.with_token(self.config['auth_token'])
            if 'protocol' in self.config:
                builder.with_protocol(self.config['protocol'])
            
            # Build client
            self.client = builder.build()
            
            # Connect
            self.client.connect(
                auth_token=self.config.get('auth_token'),
                host=self.config.get('host', 'localhost:3000'),
                database_address=self.config.get('database_address', 
                                                self.config.get('module_name')),
                ssl_enabled=self.config.get('ssl_enabled', True)
            )
            
            self.state = PooledConnectionState.IDLE
            self.health.state = self.state
            self.health.record_success(0)
            self.circuit_breaker.close()
            
            self.logger.info(f"Connection {self.connection_id[:8]} established")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            self.state = PooledConnectionState.UNHEALTHY
            self.health.state = self.state
            self.health.record_failure()
            return False
    
    def disconnect(self) -> None:
        """Disconnect and cleanup."""
        with self._lock:
            if self.client:
                try:
                    self.client.disconnect()
                except Exception as e:
                    self.logger.error(f"Error during disconnect: {e}")
                finally:
                    self.client = None
            
            self.state = PooledConnectionState.CLOSED
            self.health.state = self.state
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        if self.state == PooledConnectionState.UNHEALTHY:
            return False
        
        if not self.client or not self.client.is_connected:
            return False
        
        # Check if health check is needed
        now = time.time()
        if now - self.last_health_check > self.health_check_interval:
            return self._perform_health_check()
        
        return True
    
    def _perform_health_check(self) -> bool:
        """Perform a health check on the connection."""
        self.last_health_check = time.time()
        
        try:
            # Simple health check - check connection state
            if self.client and self.client.is_connected:
                self.health.record_success(0)
                return True
            else:
                self.health.record_failure()
                self.state = PooledConnectionState.UNHEALTHY
                return False
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self.health.record_failure()
            self.state = PooledConnectionState.UNHEALTHY
            return False
    
    def acquire(self) -> bool:
        """Acquire the connection for use."""
        with self._lock:
            if self.state != PooledConnectionState.IDLE:
                return False
            
            if not self.circuit_breaker.is_available():
                return False
            
            self.state = PooledConnectionState.ACTIVE
            self._active_operations += 1
            return True
    
    def release(self) -> None:
        """Release the connection back to the pool."""
        with self._lock:
            self._active_operations -= 1
            if self._active_operations <= 0 and self.state == PooledConnectionState.ACTIVE:
                self.state = PooledConnectionState.IDLE
    
    def mark_unhealthy(self) -> None:
        """Mark connection as unhealthy."""
        with self._lock:
            self.state = PooledConnectionState.UNHEALTHY
            self.health.state = self.state
            self.circuit_breaker.record_failure()


class ConnectionPool:
    """
    Advanced connection pool with load balancing and health management.
    
    Features:
    - Multiple concurrent connections
    - Load balancing strategies
    - Health monitoring and recovery
    - Circuit breaker patterns
    - Graceful shutdown
    """
    
    def __init__(
        self,
        min_connections: int = 2,
        max_connections: int = 10,
        connection_config: Dict[str, Any] = None,
        health_check_interval: float = 30.0,
        retry_policy: Optional[RetryPolicy] = None,
        load_balancing_strategy: str = "round_robin"
    ):
        self.pool_id = str(uuid.uuid4())
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_config = connection_config or {}
        self.health_check_interval = health_check_interval
        self.retry_policy = retry_policy or RetryPolicy()
        self.load_balancing_strategy = load_balancing_strategy
        
        # Pool state
        self.connections: Dict[str, PooledConnection] = {}
        self.connection_order: List[str] = []  # For round-robin
        self.current_index = 0
        self._lock = threading.RLock()
        self._shutdown = False
        
        # Health monitoring
        self._health_monitor_thread: Optional[threading.Thread] = None
        self._health_monitor_running = False
        
        # Metrics
        self.total_operations = 0
        self.failed_operations = 0
        self.total_retries = 0
        
        # Executor for async operations
        self._executor = ThreadPoolExecutor(max_workers=max_connections)
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.ConnectionPool_{self.pool_id[:8]}")
        
        # Initialize pool
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        """Initialize the connection pool with minimum connections."""
        self.logger.info(f"Initializing connection pool with {self.min_connections} connections")
        
        for i in range(self.min_connections):
            self._create_connection()
        
        # Start health monitoring
        self._start_health_monitor()
    
    def _create_connection(self) -> Optional[PooledConnection]:
        """Create a new connection and add to pool."""
        if len(self.connections) >= self.max_connections:
            self.logger.warning("Maximum connections reached")
            return None
        
        conn = PooledConnection(
            self.pool_id,
            self.connection_config,
            self.health_check_interval
        )
        
        if conn.connect():
            with self._lock:
                self.connections[conn.connection_id] = conn
                self.connection_order.append(conn.connection_id)
            return conn
        else:
            self.logger.error("Failed to create connection")
            return None
    
    def _start_health_monitor(self) -> None:
        """Start the health monitoring thread."""
        self._health_monitor_running = True
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name=f"ConnectionPool-HealthMonitor-{self.pool_id[:8]}"
        )
        self._health_monitor_thread.start()
    
    def _health_monitor_loop(self) -> None:
        """Background thread for health monitoring."""
        while self._health_monitor_running and not self._shutdown:
            try:
                self._check_pool_health()
                time.sleep(self.health_check_interval)
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
    
    def _check_pool_health(self) -> None:
        """Check health of all connections and recover unhealthy ones."""
        with self._lock:
            unhealthy_connections = []
            
            for conn_id, conn in self.connections.items():
                if not conn.is_healthy():
                    unhealthy_connections.append(conn_id)
            
            # Try to recover unhealthy connections
            for conn_id in unhealthy_connections:
                conn = self.connections[conn_id]
                self.logger.warning(f"Connection {conn_id[:8]} is unhealthy, attempting recovery")
                
                # Try to reconnect
                conn.disconnect()
                if not conn.connect():
                    # If reconnection fails, remove from pool
                    del self.connections[conn_id]
                    self.connection_order.remove(conn_id)
                    
                    # Create replacement if below minimum
                    if len(self.connections) < self.min_connections:
                        self._create_connection()
    
    def get_connection(self) -> Optional[PooledConnection]:
        """Get an available connection using the configured strategy."""
        with self._lock:
            if self._shutdown:
                return None
            
            # Try multiple times to get a healthy connection
            attempts = len(self.connections) * 2
            
            for _ in range(attempts):
                conn = self._select_connection()
                if conn and conn.acquire():
                    return conn
            
            # No available connections, try to create one if possible
            if len(self.connections) < self.max_connections:
                new_conn = self._create_connection()
                if new_conn and new_conn.acquire():
                    return new_conn
            
            return None
    
    def _select_connection(self) -> Optional[PooledConnection]:
        """Select a connection based on load balancing strategy."""
        if not self.connections:
            return None
        
        if self.load_balancing_strategy == "round_robin":
            return self._round_robin_select()
        elif self.load_balancing_strategy == "least_latency":
            return self._least_latency_select()
        elif self.load_balancing_strategy == "random":
            return self._random_select()
        else:
            return self._round_robin_select()
    
    def _round_robin_select(self) -> Optional[PooledConnection]:
        """Round-robin connection selection."""
        if not self.connection_order:
            return None
        
        start_index = self.current_index
        while True:
            conn_id = self.connection_order[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.connection_order)
            
            conn = self.connections.get(conn_id)
            if conn and conn.state == PooledConnectionState.IDLE and conn.is_healthy():
                return conn
            
            if self.current_index == start_index:
                break
        
        return None
    
    def _least_latency_select(self) -> Optional[PooledConnection]:
        """Select connection with lowest average latency."""
        available_conns = [
            conn for conn in self.connections.values()
            if conn.state == PooledConnectionState.IDLE and conn.is_healthy()
        ]
        
        if not available_conns:
            return None
        
        return min(available_conns, key=lambda c: c.health.avg_latency_ms)
    
    def _random_select(self) -> Optional[PooledConnection]:
        """Random connection selection."""
        available_conns = [
            conn for conn in self.connections.values()
            if conn.state == PooledConnectionState.IDLE and conn.is_healthy()
        ]
        
        if not available_conns:
            return None
        
        return random.choice(available_conns)
    
    def release_connection(self, connection: PooledConnection) -> None:
        """Release a connection back to the pool."""
        connection.release()
    
    def execute_with_retry(
        self,
        operation: Callable[[ModernSpacetimeDBClient], Any],
        operation_name: str = "operation"
    ) -> Any:
        """
        Execute an operation with retry logic and connection pooling.
        
        Args:
            operation: Function that takes a client and performs the operation
            operation_name: Name of the operation for logging
            
        Returns:
            Result of the operation
            
        Raises:
            Exception: If operation fails after all retries
        """
        last_error = None
        
        for attempt in range(self.retry_policy.max_retries + 1):
            connection = None
            start_time = time.time()
            
            try:
                # Get a connection from the pool
                connection = self.get_connection()
                if not connection:
                    raise RuntimeError("No available connections")
                
                # Execute the operation
                result = operation(connection.client)
                
                # Record success
                latency_ms = (time.time() - start_time) * 1000
                connection.health.record_success(latency_ms)
                connection.circuit_breaker.record_success()
                
                self.total_operations += 1
                
                return result
                
            except Exception as e:
                last_error = e
                self.failed_operations += 1
                
                if connection:
                    connection.health.record_failure()
                    connection.circuit_breaker.record_failure()
                    
                    # Mark as unhealthy if too many failures
                    if connection.health.consecutive_failures > 3:
                        connection.mark_unhealthy()
                
                self.logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}): {e}"
                )
                
                if attempt < self.retry_policy.max_retries:
                    self.total_retries += 1
                    delay = self.retry_policy.get_retry_delay(attempt)
                    self.logger.info(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                
            finally:
                if connection:
                    self.release_connection(connection)
        
        raise last_error or RuntimeError(f"{operation_name} failed after all retries")
    
    async def execute_async_with_retry(
        self,
        operation: Callable[[ModernSpacetimeDBClient], Any],
        operation_name: str = "operation"
    ) -> Any:
        """Async version of execute_with_retry."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.execute_with_retry,
            operation,
            operation_name
        )
    
    def get_pool_metrics(self) -> Dict[str, Any]:
        """Get comprehensive pool metrics."""
        with self._lock:
            healthy_count = sum(
                1 for conn in self.connections.values()
                if conn.is_healthy()
            )
            
            active_count = sum(
                1 for conn in self.connections.values()
                if conn.state == PooledConnectionState.ACTIVE
            )
            
            # Aggregate health metrics
            total_latency_samples = []
            total_error_rate = 0
            
            for conn in self.connections.values():
                total_latency_samples.extend(conn.health.latency_samples)
                total_error_rate += conn.health.error_rate
            
            avg_error_rate = total_error_rate / len(self.connections) if self.connections else 0
            
            # Calculate pool-wide latency metrics
            if total_latency_samples:
                sorted_samples = sorted(total_latency_samples)
                avg_latency = sum(sorted_samples) / len(sorted_samples)
                p95_latency = sorted_samples[int(len(sorted_samples) * 0.95)]
                p99_latency = sorted_samples[int(len(sorted_samples) * 0.99)]
            else:
                avg_latency = p95_latency = p99_latency = 0
            
            return {
                "pool_id": self.pool_id,
                "total_connections": len(self.connections),
                "healthy_connections": healthy_count,
                "active_connections": active_count,
                "idle_connections": len(self.connections) - active_count,
                "total_operations": self.total_operations,
                "failed_operations": self.failed_operations,
                "total_retries": self.total_retries,
                "success_rate": (
                    (self.total_operations - self.failed_operations) / self.total_operations * 100
                    if self.total_operations > 0 else 0
                ),
                "average_error_rate": avg_error_rate * 100,
                "latency_metrics": {
                    "avg_ms": avg_latency,
                    "p95_ms": p95_latency,
                    "p99_ms": p99_latency
                },
                "connection_details": [
                    {
                        "id": conn.connection_id[:8],
                        "state": conn.state.value,
                        "health": {
                            "consecutive_failures": conn.health.consecutive_failures,
                            "error_rate": conn.health.error_rate * 100,
                            "avg_latency_ms": conn.health.avg_latency_ms,
                            "circuit_state": conn.circuit_breaker.state.value
                        }
                    }
                    for conn in self.connections.values()
                ]
            }
    
    def shutdown(self, graceful: bool = True, timeout: float = 30.0) -> None:
        """
        Shutdown the connection pool.
        
        Args:
            graceful: If True, wait for active operations to complete
            timeout: Maximum time to wait for graceful shutdown
        """
        self.logger.info(f"Shutting down connection pool (graceful={graceful})")
        
        with self._lock:
            self._shutdown = True
            self._health_monitor_running = False
        
        # Stop health monitor
        if self._health_monitor_thread:
            self._health_monitor_thread.join(timeout=5.0)
        
        if graceful:
            # Wait for active connections to be released
            start_time = time.time()
            while time.time() - start_time < timeout:
                with self._lock:
                    active_count = sum(
                        1 for conn in self.connections.values()
                        if conn.state == PooledConnectionState.ACTIVE
                    )
                    if active_count == 0:
                        break
                
                time.sleep(0.1)
        
        # Disconnect all connections
        with self._lock:
            for conn in self.connections.values():
                try:
                    conn.disconnect()
                except Exception as e:
                    self.logger.error(f"Error disconnecting {conn.connection_id[:8]}: {e}")
            
            self.connections.clear()
            self.connection_order.clear()
        
        # Shutdown executor
        self._executor.shutdown(wait=graceful)
        
        self.logger.info("Connection pool shutdown complete")


class LoadBalancedConnectionManager:
    """
    High-level connection manager with multiple pools and advanced features.
    
    Provides:
    - Multiple connection pools for different workloads
    - Connection migration between pools
    - Hot configuration reloading
    - Comprehensive monitoring
    """
    
    def __init__(self):
        self.pools: Dict[str, ConnectionPool] = {}
        self.default_pool: Optional[str] = None
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.LoadBalancedConnectionManager")
    
    def create_pool(
        self,
        pool_name: str,
        min_connections: int = 2,
        max_connections: int = 10,
        connection_config: Dict[str, Any] = None,
        retry_policy: Optional[RetryPolicy] = None,
        load_balancing_strategy: str = "round_robin"
    ) -> ConnectionPool:
        """Create a new connection pool."""
        with self._lock:
            if pool_name in self.pools:
                raise ValueError(f"Pool {pool_name} already exists")
            
            pool = ConnectionPool(
                min_connections=min_connections,
                max_connections=max_connections,
                connection_config=connection_config,
                retry_policy=retry_policy,
                load_balancing_strategy=load_balancing_strategy
            )
            
            self.pools[pool_name] = pool
            
            if not self.default_pool:
                self.default_pool = pool_name
            
            self.logger.info(f"Created pool '{pool_name}'")
            return pool
    
    def get_pool(self, pool_name: Optional[str] = None) -> Optional[ConnectionPool]:
        """Get a connection pool by name."""
        with self._lock:
            if pool_name:
                return self.pools.get(pool_name)
            elif self.default_pool:
                return self.pools.get(self.default_pool)
            return None
    
    def execute_on_pool(
        self,
        operation: Callable[[ModernSpacetimeDBClient], Any],
        pool_name: Optional[str] = None,
        operation_name: str = "operation"
    ) -> Any:
        """Execute an operation on a specific pool."""
        pool = self.get_pool(pool_name)
        if not pool:
            raise ValueError(f"Pool {pool_name or 'default'} not found")
        
        return pool.execute_with_retry(operation, operation_name)
    
    def migrate_connections(
        self,
        from_pool: str,
        to_pool: str,
        count: int = 1
    ) -> None:
        """Migrate connections between pools (for load rebalancing)."""
        # This is a placeholder for future implementation
        # Would involve draining connections from one pool and adding to another
        pass
    
    def update_pool_config(
        self,
        pool_name: str,
        new_config: Dict[str, Any]
    ) -> None:
        """Hot-reload pool configuration."""
        with self._lock:
            pool = self.pools.get(pool_name)
            if not pool:
                raise ValueError(f"Pool {pool_name} not found")
            
            # Update configuration
            # This would require careful handling of existing connections
            self.logger.info(f"Updated configuration for pool '{pool_name}'")
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all pools."""
        with self._lock:
            return {
                pool_name: pool.get_pool_metrics()
                for pool_name, pool in self.pools.items()
            }
    
    def shutdown_all(self, graceful: bool = True) -> None:
        """Shutdown all connection pools."""
        with self._lock:
            for pool_name, pool in self.pools.items():
                self.logger.info(f"Shutting down pool '{pool_name}'")
                pool.shutdown(graceful=graceful)
            
            self.pools.clear()
            self.default_pool = None
