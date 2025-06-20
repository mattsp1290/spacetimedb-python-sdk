"""
Enhanced Connection Manager for SpacetimeDB SDK

Production-ready connection management with pooling, health monitoring,
circuit breaker pattern, and comprehensive metrics. Extracted from
blackholio-python-client's battle-tested patterns.

Features:
- Advanced connection pooling with configurable min/max connections
- Health monitoring with automatic recovery
- Circuit breaker pattern for failure protection
- Background cleanup of idle connections
- Comprehensive metrics and monitoring
- Event-driven architecture for monitoring hooks
- Multi-server language support
- Graceful shutdown handling
"""

import asyncio
import logging
import time
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator, Tuple
from weakref import WeakSet

from ..exceptions import (
    SpacetimeDBError,
    ConnectionTimeoutError,
    ServerNotAvailableError,
    RetryableConnectionError
)
from ..factory.base import ServerLanguage, OptimizationProfile
from ..retry_policies import RetryPolicy, CircuitBreaker
from ..modern_client import ModernSpacetimeDBClient


logger = logging.getLogger(__name__)


class PoolState(Enum):
    """Connection pool state enumeration."""
    INACTIVE = "inactive"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DRAINING = "draining"
    SHUTDOWN = "shutdown"


class HealthStatus(Enum):
    """Connection health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectionMetrics:
    """Connection metrics and statistics."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_health_check: Optional[float] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.total_requests > 0:
            self.success_rate = self.successful_requests / self.total_requests
        else:
            self.success_rate = 0.0


@dataclass
class PoolConfiguration:
    """Connection pool configuration."""
    min_connections: int = 1
    max_connections: int = 10
    max_idle_time: float = 300.0  # 5 minutes
    health_check_interval: float = 30.0  # 30 seconds
    connection_timeout: float = 30.0
    request_timeout: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 2.0
    retry_max_delay: float = 60.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    enable_health_checks: bool = True
    enable_metrics: bool = True
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.min_connections < 0:
            raise ValueError("min_connections must be >= 0")
        if self.max_connections < 1:
            raise ValueError("max_connections must be >= 1")
        if self.min_connections > self.max_connections:
            raise ValueError("min_connections cannot exceed max_connections")
        if self.max_idle_time <= 0:
            raise ValueError("max_idle_time must be > 0")
        if self.health_check_interval <= 0:
            raise ValueError("health_check_interval must be > 0")


@dataclass
class PooledConnection:
    """Wrapper for pooled connection with metadata."""
    connection: ModernSpacetimeDBClient
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    in_use: bool = False
    use_count: int = 0
    error_count: int = 0
    last_error: Optional[Exception] = None
    
    @property
    def is_idle(self) -> bool:
        """Check if connection is idle."""
        return not self.in_use
    
    @property
    def age(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        if self.in_use:
            return 0.0
        return time.time() - self.last_used
    
    def mark_used(self) -> None:
        """Mark connection as used."""
        self.in_use = True
        self.use_count += 1
        self.last_used = time.time()
    
    def mark_idle(self) -> None:
        """Mark connection as idle."""
        self.in_use = False
        self.last_used = time.time()
    
    def mark_error(self, error: Exception) -> None:
        """Mark connection as having an error."""
        self.error_count += 1
        self.last_error = error


@dataclass
class ServerConfig:
    """Server configuration for connection pooling."""
    language: ServerLanguage
    host: str
    port: int
    database: str
    auth_token: Optional[str] = None
    optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    additional_config: Dict[str, Any] = field(default_factory=dict)


class ConnectionPool:
    """
    Advanced connection pool with health monitoring and automatic recovery.
    """
    
    def __init__(self, server_config: ServerConfig, config: Optional[PoolConfiguration] = None):
        """
        Initialize connection pool.
        
        Args:
            server_config: Server configuration
            config: Pool configuration (uses defaults if None)
        """
        self.server_config = server_config
        self.config = config or PoolConfiguration()
        self.config.validate()
        
        # Pool state
        self.state = PoolState.INACTIVE
        self.connections: List[PooledConnection] = []
        self.metrics = ConnectionMetrics()
        
        # Synchronization
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_breaker_threshold,
            recovery_timeout=self.config.circuit_breaker_timeout
        )
        
        # Event callbacks
        self._event_callbacks: Dict[str, List[Callable]] = {}
        
        logger.info(f"Initialized connection pool for {server_config.language.value} server")
    
    async def initialize(self) -> None:
        """Initialize the connection pool."""
        async with self._lock:
            if self.state != PoolState.INACTIVE:
                logger.warning("Connection pool already initialized")
                return
            
            self.state = PoolState.INITIALIZING
            logger.info("Initializing connection pool...")
            
            try:
                # Create minimum connections
                for i in range(self.config.min_connections):
                    await self._create_connection()
                
                # Start background tasks
                if self.config.enable_health_checks:
                    self._health_check_task = asyncio.create_task(
                        self._health_check_loop(),
                        name="connection_pool_health_check"
                    )
                
                self._cleanup_task = asyncio.create_task(
                    self._cleanup_loop(),
                    name="connection_pool_cleanup"
                )
                
                self.state = PoolState.ACTIVE
                self.metrics.health_status = HealthStatus.HEALTHY
                
                logger.info(f"Connection pool initialized with {len(self.connections)} connections")
                await self._trigger_event('pool_initialized', {
                    'connection_count': len(self.connections),
                    'min_connections': self.config.min_connections,
                    'max_connections': self.config.max_connections
                })
                
            except Exception as e:
                self.state = PoolState.INACTIVE
                logger.error(f"Failed to initialize connection pool: {e}")
                raise
    
    async def shutdown(self) -> None:
        """Shutdown the connection pool gracefully."""
        async with self._lock:
            if self.state == PoolState.SHUTDOWN:
                return
            
            logger.info("Shutting down connection pool...")
            previous_state = self.state
            self.state = PoolState.DRAINING
            
            # Stop accepting new requests
            self._shutdown_event.set()
            
            # Cancel background tasks
            tasks_to_cancel = []
            if self._health_check_task:
                tasks_to_cancel.append(self._health_check_task)
            if self._cleanup_task:
                tasks_to_cancel.append(self._cleanup_task)
            
            for task in tasks_to_cancel:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Close all connections
            for pooled_conn in self.connections:
                try:
                    await pooled_conn.connection.disconnect()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")
            
            self.connections.clear()
            self.state = PoolState.SHUTDOWN
            
            logger.info("Connection pool shutdown complete")
            await self._trigger_event('pool_shutdown', {
                'previous_state': previous_state.value,
                'final_metrics': self.get_metrics()
            })
    
    @asynccontextmanager
    async def get_connection(self, timeout: Optional[float] = None) -> AsyncGenerator[ModernSpacetimeDBClient, None]:
        """
        Get a connection from the pool.
        
        Args:
            timeout: Maximum time to wait for a connection
            
        Yields:
            ModernSpacetimeDBClient instance
            
        Raises:
            SpacetimeDBError: If unable to get connection
            ConnectionTimeoutError: If timeout exceeded
        """
        if self.state not in (PoolState.ACTIVE, PoolState.DRAINING):
            raise SpacetimeDBError(f"Connection pool is not active (state: {self.state.value})")
        
        if self.circuit_breaker.state == self.circuit_breaker.State.OPEN:
            raise ServerNotAvailableError("Circuit breaker is open - server appears unhealthy")
        
        timeout = timeout or self.config.connection_timeout
        start_time = time.time()
        
        try:
            # Get connection from pool
            pooled_conn = await self._acquire_connection(timeout)
            
            try:
                # Ensure connection is healthy
                if not pooled_conn.connection.is_connected:
                    await pooled_conn.connection.connect()
                
                # Mark as in use
                pooled_conn.mark_used()
                
                # Update metrics
                self.metrics.active_connections += 1
                
                yield pooled_conn.connection
                
            finally:
                # Return connection to pool
                await self._release_connection(pooled_conn)
                
        except Exception as e:
            self.circuit_breaker._on_failure()
            elapsed = time.time() - start_time
            
            if elapsed >= timeout:
                raise ConnectionTimeoutError(f"Connection timeout after {timeout}s")
            raise
    
    async def _acquire_connection(self, timeout: float) -> PooledConnection:
        """Acquire a connection from the pool."""
        async with self._condition:
            deadline = time.time() + timeout
            
            while True:
                # Check for available idle connection
                for pooled_conn in self.connections:
                    if pooled_conn.is_idle and pooled_conn.connection.is_connected:
                        return pooled_conn
                
                # Try to create new connection if under limit
                if len(self.connections) < self.config.max_connections:
                    return await self._create_connection()
                
                # Wait for connection to become available
                remaining_time = deadline - time.time()
                if remaining_time <= 0:
                    raise ConnectionTimeoutError(f"Connection timeout after {timeout}s")
                
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=remaining_time)
                except asyncio.TimeoutError:
                    raise ConnectionTimeoutError(f"Connection timeout after {timeout}s")
    
    async def _create_connection(self) -> PooledConnection:
        """Create a new pooled connection."""
        try:
            # Import here to avoid circular imports
            from ..factory.client_factory import create_spacetimedb_client
            
            connection = create_spacetimedb_client(
                host=self.server_config.host,
                database=self.server_config.database,
                auth_token=self.server_config.auth_token,
                server_language=self.server_config.language,
                optimization_profile=self.server_config.optimization_profile,
                **self.server_config.additional_config
            )
            
            pooled_conn = PooledConnection(connection=connection)
            
            # Connect to server
            await connection.connect()
            if not connection.is_connected:
                raise SpacetimeDBError("Failed to connect to server")
            
            self.connections.append(pooled_conn)
            self.metrics.total_connections += 1
            
            logger.debug(f"Created new connection (total: {len(self.connections)})")
            return pooled_conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise
    
    async def _release_connection(self, pooled_conn: PooledConnection) -> None:
        """Release a connection back to the pool."""
        async with self._condition:
            pooled_conn.mark_idle()
            self.metrics.active_connections = max(0, self.metrics.active_connections - 1)
            
            # Notify waiting tasks
            self._condition.notify()
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._perform_health_checks()
                    await asyncio.sleep(self.config.health_check_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in health check loop: {e}")
                    await asyncio.sleep(5.0)  # Brief pause on error
        except Exception as e:
            logger.error(f"Fatal error in health check loop: {e}")
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        async with self._lock:
            healthy_count = 0
            unhealthy_connections = []
            
            for pooled_conn in self.connections:
                try:
                    if pooled_conn.is_idle:
                        # Check if connection is still alive
                        if pooled_conn.connection.is_connected:
                            # Optional: Send ping if available
                            if hasattr(pooled_conn.connection, 'ping'):
                                await asyncio.wait_for(
                                    pooled_conn.connection.ping(),
                                    timeout=5.0
                                )
                            healthy_count += 1
                        else:
                            unhealthy_connections.append(pooled_conn)
                    else:
                        # Connection in use, assume healthy
                        healthy_count += 1
                        
                except Exception as e:
                    logger.warning(f"Health check failed for connection: {e}")
                    pooled_conn.mark_error(e)
                    unhealthy_connections.append(pooled_conn)
            
            # Remove unhealthy connections
            for unhealthy_conn in unhealthy_connections:
                await self._remove_connection(unhealthy_conn)
            
            # Ensure minimum connections
            while len(self.connections) < self.config.min_connections:
                try:
                    await self._create_connection()
                except Exception as e:
                    logger.error(f"Failed to maintain minimum connections: {e}")
                    break
            
            # Update health status
            total_connections = len(self.connections)
            if total_connections == 0:
                self.metrics.health_status = HealthStatus.UNHEALTHY
            elif healthy_count < total_connections * 0.5:
                self.metrics.health_status = HealthStatus.DEGRADED
            else:
                self.metrics.health_status = HealthStatus.HEALTHY
            
            self.metrics.last_health_check = time.time()
            
            logger.debug(f"Health check complete: {healthy_count}/{total_connections} healthy connections")
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for idle connections."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._cleanup_idle_connections()
                    await asyncio.sleep(60.0)  # Run every minute
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup loop: {e}")
                    await asyncio.sleep(5.0)
        except Exception as e:
            logger.error(f"Fatal error in cleanup loop: {e}")
    
    async def _cleanup_idle_connections(self) -> None:
        """Clean up idle connections that exceed max idle time."""
        async with self._lock:
            connections_to_remove = []
            
            for pooled_conn in self.connections:
                if (pooled_conn.is_idle and 
                    pooled_conn.idle_time > self.config.max_idle_time and
                    len(self.connections) > self.config.min_connections):
                    connections_to_remove.append(pooled_conn)
            
            for conn in connections_to_remove:
                await self._remove_connection(conn)
            
            if connections_to_remove:
                logger.debug(f"Cleaned up {len(connections_to_remove)} idle connections")
    
    async def _remove_connection(self, pooled_conn: PooledConnection) -> None:
        """Remove a connection from the pool."""
        try:
            if pooled_conn in self.connections:
                self.connections.remove(pooled_conn)
            
            await pooled_conn.connection.disconnect()
            self.metrics.failed_connections += 1
            
        except Exception as e:
            logger.error(f"Error removing connection: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current pool metrics."""
        idle_count = sum(1 for conn in self.connections if conn.is_idle)
        
        return {
            'state': self.state.value,
            'total_connections': len(self.connections),
            'active_connections': len(self.connections) - idle_count,
            'idle_connections': idle_count,
            'failed_connections': self.metrics.failed_connections,
            'total_requests': self.metrics.total_requests,
            'successful_requests': self.metrics.successful_requests,
            'failed_requests': self.metrics.failed_requests,
            'success_rate': getattr(self.metrics, 'success_rate', 0.0),
            'health_status': self.metrics.health_status.value,
            'last_health_check': self.metrics.last_health_check,
            'circuit_breaker_state': self.circuit_breaker.state.value,
            'circuit_breaker_failures': self.circuit_breaker.failure_count,
            'config': {
                'min_connections': self.config.min_connections,
                'max_connections': self.config.max_connections,
                'max_idle_time': self.config.max_idle_time,
                'health_check_interval': self.config.health_check_interval
            }
        }
    
    def on(self, event: str, callback: Callable):
        """Register event callback."""
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)
    
    async def _trigger_event(self, event: str, data: Any = None):
        """Trigger event callbacks."""
        if event in self._event_callbacks:
            for callback in self._event_callbacks[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Error in event callback for {event}: {e}")


class EnhancedConnectionManager:
    """
    High-level connection manager that manages multiple connection pools
    and provides unified access to SpacetimeDB connections.
    """
    
    def __init__(self):
        """Initialize connection manager."""
        self.pools: Dict[str, ConnectionPool] = {}
        self.default_pool_config = PoolConfiguration()
        
        # Global metrics
        self.global_metrics = ConnectionMetrics()
        
        # Synchronization
        self._lock = asyncio.Lock()
        
        logger.info("Initialized enhanced connection manager")
    
    async def get_pool(self, server_config: ServerConfig, 
                       pool_config: Optional[PoolConfiguration] = None) -> ConnectionPool:
        """
        Get or create connection pool for specified server configuration.
        
        Args:
            server_config: Server configuration
            pool_config: Pool configuration (uses default if None)
            
        Returns:
            ConnectionPool instance
        """
        pool_key = f"{server_config.language.value}_{server_config.host}_{server_config.port}_{server_config.database}"
        
        async with self._lock:
            if pool_key not in self.pools:
                config = pool_config or self.default_pool_config
                pool = ConnectionPool(server_config, config)
                await pool.initialize()
                self.pools[pool_key] = pool
                
                logger.info(f"Created connection pool for {server_config.language.value} server")
            
            return self.pools[pool_key]
    
    @asynccontextmanager
    async def get_connection(self, server_config: ServerConfig,
                           timeout: Optional[float] = None,
                           pool_config: Optional[PoolConfiguration] = None) -> AsyncGenerator[ModernSpacetimeDBClient, None]:
        """
        Get a connection for the specified server configuration.
        
        Args:
            server_config: Server configuration
            timeout: Connection timeout
            pool_config: Pool configuration (uses default if None)
            
        Yields:
            ModernSpacetimeDBClient instance
        """
        pool = await self.get_pool(server_config, pool_config)
        
        async with pool.get_connection(timeout) as connection:
            yield connection
    
    async def shutdown_all(self) -> None:
        """Shutdown all connection pools."""
        async with self._lock:
            shutdown_tasks = []
            for pool in self.pools.values():
                shutdown_tasks.append(pool.shutdown())
            
            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            
            self.pools.clear()
            logger.info("All connection pools shutdown")
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global metrics across all pools."""
        total_metrics = {
            'total_pools': len(self.pools),
            'pools': {},
            'aggregate': {
                'total_connections': 0,
                'active_connections': 0,
                'idle_connections': 0,
                'failed_connections': 0,
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0
            }
        }
        
        for pool_key, pool in self.pools.items():
            pool_metrics = pool.get_metrics()
            total_metrics['pools'][pool_key] = pool_metrics
            
            # Aggregate metrics
            agg = total_metrics['aggregate']
            agg['total_connections'] += pool_metrics['total_connections']
            agg['active_connections'] += pool_metrics['active_connections']
            agg['idle_connections'] += pool_metrics['idle_connections']
            agg['failed_connections'] += pool_metrics['failed_connections']
            agg['total_requests'] += pool_metrics['total_requests']
            agg['successful_requests'] += pool_metrics['successful_requests']
            agg['failed_requests'] += pool_metrics['failed_requests']
        
        # Calculate aggregate success rate
        if total_metrics['aggregate']['total_requests'] > 0:
            total_metrics['aggregate']['success_rate'] = (
                total_metrics['aggregate']['successful_requests'] / 
                total_metrics['aggregate']['total_requests']
            )
        else:
            total_metrics['aggregate']['success_rate'] = 0.0
        
        return total_metrics


# Global connection manager instance
_connection_manager: Optional[EnhancedConnectionManager] = None
_manager_lock = threading.Lock()


def get_connection_manager() -> EnhancedConnectionManager:
    """
    Get global connection manager instance (singleton).
    
    Returns:
        EnhancedConnectionManager instance
    """
    global _connection_manager
    
    with _manager_lock:
        if _connection_manager is None:
            _connection_manager = EnhancedConnectionManager()
        return _connection_manager


@asynccontextmanager
async def get_connection(server_config: ServerConfig, 
                        timeout: Optional[float] = None,
                        pool_config: Optional[PoolConfiguration] = None) -> AsyncGenerator[ModernSpacetimeDBClient, None]:
    """
    Convenience function to get a connection.
    
    Args:
        server_config: Server configuration
        timeout: Connection timeout
        pool_config: Pool configuration (uses default if None)
        
    Yields:
        ModernSpacetimeDBClient instance
    """
    manager = get_connection_manager()
    async with manager.get_connection(server_config, timeout, pool_config) as connection:
        yield connection


__all__ = [
    'PoolState',
    'HealthStatus',
    'ConnectionMetrics',
    'PoolConfiguration',
    'PooledConnection',
    'ServerConfig',
    'ConnectionPool',
    'EnhancedConnectionManager',
    'get_connection_manager',
    'get_connection'
]