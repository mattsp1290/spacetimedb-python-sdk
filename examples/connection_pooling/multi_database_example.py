#!/usr/bin/env python3
"""
Multi-Database Connection Example - SpacetimeDB Python SDK

This example demonstrates advanced connection pooling patterns for managing
connections to multiple SpacetimeDB databases simultaneously.

Key Features Demonstrated:
- Connection pooling for multiple databases
- Efficient resource management across databases
- Connection sharing and reuse strategies
- Load balancing across database connections
- Fault tolerance and connection recovery
- Performance optimization techniques

Use Cases Covered:
- Multi-tenant applications with database per tenant
- Microservices connecting to different databases
- Data aggregation from multiple sources
- High-availability configurations with failover
- Performance optimization through connection pooling
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import statistics

from spacetimedb_sdk import SpacetimeDBAsyncClient
from spacetimedb_sdk.connection_pool import ConnectionPool, PoolConfig
from spacetimedb_sdk.auth import AuthenticationHandler
from spacetimedb_sdk.exceptions import ConnectionError, PoolExhaustedError


# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Configuration for a database connection."""
    name: str
    server_url: str
    auth_required: bool = True
    priority: int = 1  # 1 = high, 2 = medium, 3 = low
    max_connections: int = 10
    min_connections: int = 2
    connection_timeout: int = 30
    health_check_interval: int = 60


@dataclass
class ConnectionMetrics:
    """Metrics for monitoring connection performance."""
    database_name: str
    active_connections: int
    idle_connections: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    last_health_check: Optional[float] = None


class MultiDatabaseConnectionManager:
    """
    Advanced connection manager for handling multiple SpacetimeDB databases.
    
    This class provides sophisticated connection pooling, load balancing,
    and fault tolerance for applications that need to connect to multiple
    databases simultaneously.
    """
    
    def __init__(self, global_pool_config: Optional[PoolConfig] = None):
        self.databases: Dict[str, DatabaseConfig] = {}
        self.connection_pools: Dict[str, ConnectionPool] = {}
        self.auth_handlers: Dict[str, AuthenticationHandler] = {}
        self.metrics: Dict[str, ConnectionMetrics] = {}
        
        # Global configuration
        self.global_pool_config = global_pool_config or PoolConfig(
            max_size=50,
            min_size=5,
            connection_timeout=30,
            idle_timeout=300,
            health_check_interval=60,
            max_retries=3
        )
        
        # Connection management
        self.health_check_task: Optional[asyncio.Task] = None
        self.metrics_collection_task: Optional[asyncio.Task] = None
        self.load_balancer_enabled = True
        self.failover_enabled = True
        
        # Performance tracking
        self.request_history: Dict[str, List[float]] = {}
        self.connection_stats: Dict[str, Dict[str, Any]] = {}
    
    async def add_database(self, config: DatabaseConfig) -> bool:
        """
        Add a new database to the connection manager.
        
        Args:
            config: Database configuration
            
        Returns:
            bool: True if database was added successfully
        """
        try:
            logger.info(f"Adding database: {config.name}")
            
            # Store configuration
            self.databases[config.name] = config
            
            # Create database-specific pool configuration
            pool_config = PoolConfig(
                max_size=config.max_connections,
                min_size=config.min_connections,
                connection_timeout=config.connection_timeout,
                idle_timeout=self.global_pool_config.idle_timeout,
                health_check_interval=config.health_check_interval,
                max_retries=self.global_pool_config.max_retries
            )
            
            # Create connection pool
            pool = ConnectionPool(
                server_url=config.server_url,
                config=pool_config
            )
            
            self.connection_pools[config.name] = pool
            
            # Initialize authentication if required
            if config.auth_required:
                auth_handler = AuthenticationHandler()
                self.auth_handlers[config.name] = auth_handler
                pool.set_auth_handler(auth_handler)
            
            # Initialize metrics
            self.metrics[config.name] = ConnectionMetrics(
                database_name=config.name,
                active_connections=0,
                idle_connections=0,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                average_response_time=0.0
            )
            
            # Initialize connection stats tracking
            self.request_history[config.name] = []
            self.connection_stats[config.name] = {
                "created_at": time.time(),
                "total_connections_created": 0,
                "total_connections_closed": 0,
                "peak_connections": 0
            }
            
            # Initialize the pool with minimum connections
            await pool.initialize()
            
            logger.info(f"Database {config.name} added successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add database {config.name}: {e}")
            return False
    
    async def remove_database(self, database_name: str) -> bool:
        """
        Remove a database from the connection manager.
        
        Args:
            database_name: Name of database to remove
            
        Returns:
            bool: True if database was removed successfully
        """
        try:
            logger.info(f"Removing database: {database_name}")
            
            # Close connection pool
            if database_name in self.connection_pools:
                await self.connection_pools[database_name].close()
                del self.connection_pools[database_name]
            
            # Cleanup authentication
            if database_name in self.auth_handlers:
                await self.auth_handlers[database_name].cleanup()
                del self.auth_handlers[database_name]
            
            # Remove tracking data
            self.databases.pop(database_name, None)
            self.metrics.pop(database_name, None)
            self.request_history.pop(database_name, None)
            self.connection_stats.pop(database_name, None)
            
            logger.info(f"Database {database_name} removed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove database {database_name}: {e}")
            return False
    
    async def get_connection(self, database_name: str, 
                           load_balance: bool = True) -> Optional[SpacetimeDBAsyncClient]:
        """
        Get a connection to the specified database.
        
        Args:
            database_name: Database to connect to
            load_balance: Whether to use load balancing
            
        Returns:
            Optional[SpacetimeDBAsyncClient]: Connection or None if unavailable
        """
        try:
            start_time = time.time()
            
            # Track request
            self.metrics[database_name].total_requests += 1
            
            # Get connection from pool
            if database_name not in self.connection_pools:
                logger.error(f"No pool configured for database: {database_name}")
                return None
            
            pool = self.connection_pools[database_name]
            
            # Apply load balancing if enabled
            if load_balance and self.load_balancer_enabled:
                connection = await self._get_load_balanced_connection(database_name)
            else:
                connection = await pool.get_connection()
            
            if connection:
                # Update metrics
                self.metrics[database_name].successful_requests += 1
                self.metrics[database_name].active_connections += 1
                
                # Track response time
                response_time = time.time() - start_time
                self.request_history[database_name].append(response_time)
                
                # Keep only last 100 requests for moving average
                if len(self.request_history[database_name]) > 100:
                    self.request_history[database_name] = \
                        self.request_history[database_name][-100:]
                
                # Update average response time
                self.metrics[database_name].average_response_time = \
                    statistics.mean(self.request_history[database_name])
                
                logger.debug(f"Connection acquired for {database_name} in {response_time:.3f}s")
                return connection
            else:
                self.metrics[database_name].failed_requests += 1
                logger.warning(f"Failed to acquire connection for {database_name}")
                return None
                
        except PoolExhaustedError:
            logger.warning(f"Connection pool exhausted for {database_name}")
            self.metrics[database_name].failed_requests += 1
            
            # Try failover if enabled
            if self.failover_enabled:
                return await self._try_failover_connection(database_name)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting connection for {database_name}: {e}")
            self.metrics[database_name].failed_requests += 1
            return None
    
    async def _get_load_balanced_connection(self, preferred_database: str) -> Optional[SpacetimeDBAsyncClient]:
        """
        Get connection using load balancing algorithm.
        
        Args:
            preferred_database: Preferred database name
            
        Returns:
            Optional[SpacetimeDBAsyncClient]: Load-balanced connection
        """
        try:
            # Calculate load scores for all databases
            database_loads = {}
            
            for db_name, pool in self.connection_pools.items():
                if db_name in self.metrics:
                    metrics = self.metrics[db_name]
                    config = self.databases[db_name]
                    
                    # Calculate load score (lower is better)
                    utilization = metrics.active_connections / config.max_connections
                    response_time_factor = min(metrics.average_response_time / 0.1, 10)  # Cap at 10x
                    priority_factor = config.priority
                    
                    load_score = (utilization * 0.5 + 
                                response_time_factor * 0.3 + 
                                priority_factor * 0.2)
                    
                    database_loads[db_name] = load_score
            
            # Prefer the requested database if its load is reasonable
            if (preferred_database in database_loads and 
                database_loads[preferred_database] < 0.8):  # Less than 80% load
                pool = self.connection_pools[preferred_database]
                return await pool.get_connection()
            
            # Otherwise, choose the least loaded database
            if database_loads:
                best_database = min(database_loads.items(), key=lambda x: x[1])[0]
                logger.info(f"Load balancing: using {best_database} instead of {preferred_database}")
                pool = self.connection_pools[best_database]
                return await pool.get_connection()
            
            return None
            
        except Exception as e:
            logger.error(f"Load balancing error: {e}")
            # Fallback to direct connection
            pool = self.connection_pools[preferred_database]
            return await pool.get_connection()
    
    async def _try_failover_connection(self, failed_database: str) -> Optional[SpacetimeDBAsyncClient]:
        """
        Try to get connection from alternative database for failover.
        
        Args:
            failed_database: Database that failed
            
        Returns:
            Optional[SpacetimeDBAsyncClient]: Failover connection
        """
        try:
            logger.info(f"Attempting failover for database: {failed_database}")
            
            # Find alternative databases with same priority or lower
            failed_config = self.databases[failed_database]
            alternatives = []
            
            for db_name, config in self.databases.items():
                if (db_name != failed_database and 
                    config.priority <= failed_config.priority + 1):
                    alternatives.append((db_name, config))
            
            # Sort by priority (lower number = higher priority)
            alternatives.sort(key=lambda x: x[1].priority)
            
            # Try each alternative
            for db_name, config in alternatives:
                try:
                    pool = self.connection_pools[db_name]
                    connection = await pool.get_connection()
                    
                    if connection:
                        logger.info(f"Failover successful: using {db_name}")
                        return connection
                        
                except Exception as e:
                    logger.warning(f"Failover to {db_name} failed: {e}")
                    continue
            
            logger.error(f"All failover attempts failed for {failed_database}")
            return None
            
        except Exception as e:
            logger.error(f"Failover error: {e}")
            return None
    
    async def return_connection(self, database_name: str, 
                              connection: SpacetimeDBAsyncClient) -> None:
        """
        Return a connection to the pool.
        
        Args:
            database_name: Database name
            connection: Connection to return
        """
        try:
            if database_name in self.connection_pools:
                pool = self.connection_pools[database_name]
                await pool.return_connection(connection)
                
                # Update metrics
                if database_name in self.metrics:
                    self.metrics[database_name].active_connections = \
                        max(0, self.metrics[database_name].active_connections - 1)
                    self.metrics[database_name].idle_connections += 1
                    
        except Exception as e:
            logger.error(f"Error returning connection for {database_name}: {e}")
    
    async def execute_on_database(self, database_name: str, operation: callable, 
                                *args, **kwargs) -> Any:
        """
        Execute an operation on a specific database with automatic connection management.
        
        Args:
            database_name: Database to execute on
            operation: Async function to execute
            *args, **kwargs: Arguments for the operation
            
        Returns:
            Any: Result of the operation
        """
        connection = None
        try:
            connection = await self.get_connection(database_name)
            if not connection:
                raise ConnectionError(f"Could not get connection to {database_name}")
            
            # Execute operation
            result = await operation(connection, *args, **kwargs)
            return result
            
        except Exception as e:
            logger.error(f"Operation failed on {database_name}: {e}")
            raise
        finally:
            if connection:
                await self.return_connection(database_name, connection)
    
    async def execute_on_multiple_databases(self, database_names: List[str], 
                                          operation: callable, 
                                          *args, **kwargs) -> Dict[str, Any]:
        """
        Execute operation on multiple databases concurrently.
        
        Args:
            database_names: List of databases to execute on
            operation: Async function to execute
            *args, **kwargs: Arguments for the operation
            
        Returns:
            Dict[str, Any]: Results keyed by database name
        """
        try:
            # Create tasks for concurrent execution
            tasks = {}
            for db_name in database_names:
                task = asyncio.create_task(
                    self.execute_on_database(db_name, operation, *args, **kwargs)
                )
                tasks[db_name] = task
            
            # Wait for all tasks to complete
            results = {}
            for db_name, task in tasks.items():
                try:
                    results[db_name] = await task
                except Exception as e:
                    logger.error(f"Operation failed on {db_name}: {e}")
                    results[db_name] = {"error": str(e)}
            
            return results
            
        except Exception as e:
            logger.error(f"Multi-database operation failed: {e}")
            return {"error": str(e)}
    
    async def get_connection_metrics(self) -> Dict[str, ConnectionMetrics]:
        """
        Get current connection metrics for all databases.
        
        Returns:
            Dict[str, ConnectionMetrics]: Metrics by database name
        """
        # Update current metrics
        for db_name, pool in self.connection_pools.items():
            if db_name in self.metrics:
                pool_stats = await pool.get_stats()
                self.metrics[db_name].active_connections = pool_stats.get("active", 0)
                self.metrics[db_name].idle_connections = pool_stats.get("idle", 0)
        
        return self.metrics.copy()
    
    async def start_health_monitoring(self) -> None:
        """Start background health monitoring for all databases."""
        try:
            if self.health_check_task and not self.health_check_task.done():
                return  # Already running
            
            self.health_check_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("Health monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start health monitoring: {e}")
    
    async def _health_monitor_loop(self) -> None:
        """Background health monitoring loop."""
        try:
            while True:
                for db_name, pool in self.connection_pools.items():
                    try:
                        health_ok = await pool.health_check()
                        
                        if health_ok:
                            self.metrics[db_name].last_health_check = time.time()
                        else:
                            logger.warning(f"Health check failed for database: {db_name}")
                            
                    except Exception as e:
                        logger.error(f"Health check error for {db_name}: {e}")
                
                # Wait for next health check cycle
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except asyncio.CancelledError:
            logger.info("Health monitoring stopped")
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")
    
    async def cleanup(self) -> None:
        """Clean up all resources."""
        try:
            # Stop background tasks
            if self.health_check_task and not self.health_check_task.done():
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Close all connection pools
            for db_name in list(self.connection_pools.keys()):
                await self.remove_database(db_name)
            
            logger.info("Multi-database connection manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


async def main():
    """
    Main example demonstrating multi-database connection management.
    """
    logger.info("=== Multi-Database Connection Management Example ===")
    
    # Create connection manager
    manager = MultiDatabaseConnectionManager()
    
    try:
        # Configure multiple databases
        databases = [
            DatabaseConfig(
                name="primary_db",
                server_url="ws://localhost:3000",
                priority=1,
                max_connections=15,
                min_connections=3
            ),
            DatabaseConfig(
                name="analytics_db", 
                server_url="ws://localhost:3001",
                priority=2,
                max_connections=10,
                min_connections=2
            ),
            DatabaseConfig(
                name="cache_db",
                server_url="ws://localhost:3002",
                priority=3,
                max_connections=5,
                min_connections=1,
                auth_required=False
            )
        ]
        
        # Add all databases
        logger.info("=== Adding Databases ===")
        for db_config in databases:
            success = await manager.add_database(db_config)
            logger.info(f"Database {db_config.name}: {'✓' if success else '✗'}")
        
        # Start health monitoring
        logger.info("=== Starting Health Monitoring ===")
        await manager.start_health_monitoring()
        
        # Demonstrate single database operations
        logger.info("=== Single Database Operations ===")
        
        async def sample_query(client: SpacetimeDBAsyncClient, query: str) -> Dict[str, Any]:
            """Sample database operation."""
            # Simulate database query
            await asyncio.sleep(0.1)  # Simulate query time
            return {"query": query, "timestamp": time.time(), "status": "success"}
        
        # Execute on primary database
        result = await manager.execute_on_database(
            "primary_db", 
            sample_query, 
            "SELECT * FROM users"
        )
        logger.info(f"Primary DB result: {result}")
        
        # Demonstrate multi-database operations
        logger.info("=== Multi-Database Operations ===")
        multi_results = await manager.execute_on_multiple_databases(
            ["primary_db", "analytics_db", "cache_db"],
            sample_query,
            "SELECT COUNT(*) FROM events"
        )
        
        for db_name, result in multi_results.items():
            logger.info(f"{db_name}: {result}")
        
        # Demonstrate load testing
        logger.info("=== Load Testing ===")
        
        async def load_test_operation():
            """Simulate concurrent load."""
            tasks = []
            for i in range(20):  # 20 concurrent operations
                task = asyncio.create_task(
                    manager.execute_on_database(
                        "primary_db",
                        sample_query,
                        f"QUERY_{i}"
                    )
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(f"Load test: {successful}/{len(results)} operations successful")
        
        await load_test_operation()
        
        # Display metrics
        logger.info("=== Connection Metrics ===")
        metrics = await manager.get_connection_metrics()
        
        for db_name, metric in metrics.items():
            logger.info(f"{db_name}:")
            logger.info(f"  Active: {metric.active_connections}")
            logger.info(f"  Idle: {metric.idle_connections}")
            logger.info(f"  Total Requests: {metric.total_requests}")
            logger.info(f"  Success Rate: {metric.successful_requests}/{metric.total_requests}")
            logger.info(f"  Avg Response Time: {metric.average_response_time:.3f}s")
        
        # Keep connections alive for demonstration
        logger.info("=== Maintaining Connections (10 seconds) ===")
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        logger.info("Example interrupted by user")
    except Exception as e:
        logger.error(f"Example failed: {e}")
    finally:
        logger.info("=== Cleaning Up ===")
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())


"""
Multi-Database Connection Best Practices:

1. **Connection Pool Management**:
   - Configure appropriate pool sizes per database
   - Use different connection limits based on database priority
   - Implement health checks for connection validation
   - Monitor and adjust pool sizes based on usage patterns

2. **Load Balancing and Failover**:
   - Implement intelligent load balancing algorithms
   - Configure failover strategies for high availability
   - Use priority-based connection routing
   - Monitor database performance for routing decisions

3. **Resource Optimization**:
   - Share connections efficiently across operations
   - Implement connection timeouts and cleanup
   - Use connection multiplexing where possible
   - Monitor resource usage and optimize dynamically

4. **Error Handling and Recovery**:
   - Graceful handling of connection failures
   - Automatic retry with exponential backoff
   - Circuit breaker patterns for failing databases
   - Comprehensive error logging and monitoring

5. **Performance Monitoring**:
   - Track connection metrics per database
   - Monitor response times and success rates
   - Implement alerts for performance degradation
   - Use metrics for capacity planning

Production Considerations:
- Use environment-specific database configurations
- Implement proper authentication for each database
- Set up monitoring and alerting for connection pools
- Plan for database maintenance and failover scenarios
- Consider database sharding and partitioning strategies
- Implement proper logging and audit trails
"""