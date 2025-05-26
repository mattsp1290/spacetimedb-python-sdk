"""
Test and demonstrate advanced connection pool management features.

This shows the prof-3 implementation with:
- Connection pooling
- Load balancing
- Circuit breakers
- Health monitoring
- Retry policies
"""

import asyncio
import time
import threading
from typing import Any, Dict

from src.spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from src.spacetimedb_sdk.connection_pool import (
    ConnectionPool, LoadBalancedConnectionManager, RetryPolicy
)
from src.spacetimedb_sdk.compression import CompressionLevel


def test_basic_connection_pool():
    """Test basic connection pool functionality."""
    print("\n=== Testing Basic Connection Pool ===")
    
    # Create a connection pool using the builder
    pool = (ModernSpacetimeDBClient.builder()
            .with_uri("ws://localhost:3000")
            .with_module_name("test_module")
            .with_connection_pool(
                min_connections=3,
                max_connections=10,
                health_check_interval=15.0
            )
            .with_retry_policy(
                max_retries=3,
                base_delay=0.5
            )
            .build_pool())
    
    # Get pool metrics
    metrics = pool.get_pool_metrics()
    print(f"Initial pool metrics:")
    print(f"  Total connections: {metrics['total_connections']}")
    print(f"  Healthy connections: {metrics['healthy_connections']}")
    print(f"  Active connections: {metrics['active_connections']}")
    
    # Define an operation to execute
    def simple_operation(client: ModernSpacetimeDBClient) -> str:
        # In a real scenario, this would call a reducer or query
        return f"Operation executed on connection {client.connection_id}"
    
    try:
        # Execute operation with retry
        result = pool.execute_with_retry(simple_operation, "test_operation")
        print(f"Operation result: {result}")
        
        # Check metrics after operation
        metrics = pool.get_pool_metrics()
        print(f"\nPool metrics after operation:")
        print(f"  Total operations: {metrics['total_operations']}")
        print(f"  Failed operations: {metrics['failed_operations']}")
        print(f"  Success rate: {metrics['success_rate']:.2f}%")
        
    finally:
        # Graceful shutdown
        print("\nShutting down pool...")
        pool.shutdown(graceful=True)


def test_load_balancing_strategies():
    """Test different load balancing strategies."""
    print("\n=== Testing Load Balancing Strategies ===")
    
    strategies = ["round_robin", "least_latency", "random"]
    
    for strategy in strategies:
        print(f"\nTesting {strategy} strategy:")
        
        pool = (ModernSpacetimeDBClient.builder()
                .with_uri("ws://localhost:3000")
                .with_module_name("test_module")
                .with_connection_pool(
                    min_connections=5,
                    max_connections=5,
                    load_balancing_strategy=strategy
                )
                .build_pool())
        
        # Track which connections are used
        connection_usage = {}
        
        def track_connection(client: ModernSpacetimeDBClient) -> str:
            conn_id = getattr(client, 'connection_id', 'unknown')
            connection_usage[conn_id] = connection_usage.get(conn_id, 0) + 1
            return conn_id
        
        # Execute multiple operations
        for i in range(20):
            try:
                pool.execute_with_retry(track_connection, f"op_{i}")
            except:
                pass
        
        print(f"  Connection usage distribution: {connection_usage}")
        
        pool.shutdown()


def test_circuit_breaker():
    """Test circuit breaker functionality."""
    print("\n=== Testing Circuit Breaker ===")
    
    pool = (ModernSpacetimeDBClient.builder()
            .with_uri("ws://localhost:3000")
            .with_module_name("test_module")
            .with_connection_pool(min_connections=2, max_connections=5)
            .with_retry_policy(max_retries=2)
            .build_pool())
    
    # Simulate failures
    failure_count = 0
    
    def failing_operation(client: ModernSpacetimeDBClient) -> None:
        nonlocal failure_count
        failure_count += 1
        if failure_count < 6:  # Fail first 5 times
            raise RuntimeError("Simulated failure")
        return "Success after failures"
    
    # Try operations that will trigger circuit breaker
    for i in range(8):
        try:
            result = pool.execute_with_retry(failing_operation, f"test_{i}")
            print(f"  Operation {i}: Success - {result}")
        except Exception as e:
            print(f"  Operation {i}: Failed - {e}")
        
        # Check circuit states
        metrics = pool.get_pool_metrics()
        for conn in metrics['connection_details']:
            print(f"    Connection {conn['id']}: Circuit state = {conn['health']['circuit_state']}")
        
        time.sleep(0.5)
    
    pool.shutdown()


def test_health_monitoring():
    """Test health monitoring and recovery."""
    print("\n=== Testing Health Monitoring ===")
    
    pool = (ModernSpacetimeDBClient.builder()
            .with_uri("ws://localhost:3000")
            .with_module_name("test_module")
            .with_connection_pool(
                min_connections=3,
                max_connections=8,
                health_check_interval=5.0  # Fast health checks for testing
            )
            .build_pool())
    
    print("Monitoring pool health for 15 seconds...")
    
    # Monitor health metrics over time
    start_time = time.time()
    while time.time() - start_time < 15:
        metrics = pool.get_pool_metrics()
        
        print(f"\nTime: {time.time() - start_time:.1f}s")
        print(f"  Healthy/Total: {metrics['healthy_connections']}/{metrics['total_connections']}")
        print(f"  Average latency: {metrics['latency_metrics']['avg_ms']:.2f}ms")
        print(f"  P95 latency: {metrics['latency_metrics']['p95_ms']:.2f}ms")
        print(f"  Average error rate: {metrics['average_error_rate']:.2f}%")
        
        # Simulate some operations
        for _ in range(5):
            try:
                pool.execute_with_retry(
                    lambda client: time.sleep(0.01),  # Simulate work
                    "health_test"
                )
            except:
                pass
        
        time.sleep(2)
    
    pool.shutdown()


async def test_async_operations():
    """Test async operations with connection pool."""
    print("\n=== Testing Async Operations ===")
    
    pool = (ModernSpacetimeDBClient.builder()
            .with_uri("ws://localhost:3000")
            .with_module_name("test_module")
            .with_connection_pool(
                min_connections=5,
                max_connections=10
            )
            .build_pool())
    
    # Define async operation
    async def async_operation(client: ModernSpacetimeDBClient) -> Dict[str, Any]:
        # Simulate async work
        await asyncio.sleep(0.1)
        return {
            "connection_id": getattr(client, 'connection_id', 'unknown'),
            "timestamp": time.time()
        }
    
    # Execute multiple async operations concurrently
    tasks = []
    for i in range(20):
        task = pool.execute_async_with_retry(
            lambda client: asyncio.run(async_operation(client)),
            f"async_op_{i}"
        )
        tasks.append(task)
    
    # Wait for all operations
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    print(f"Completed {success_count}/{len(tasks)} async operations successfully")
    
    # Show final metrics
    metrics = pool.get_pool_metrics()
    print(f"\nFinal pool metrics:")
    print(f"  Total operations: {metrics['total_operations']}")
    print(f"  Success rate: {metrics['success_rate']:.2f}%")
    print(f"  Total retries: {metrics['total_retries']}")
    
    pool.shutdown()


def test_multiple_pools():
    """Test managing multiple connection pools."""
    print("\n=== Testing Multiple Connection Pools ===")
    
    manager = LoadBalancedConnectionManager()
    
    # Create different pools for different workloads
    
    # High-throughput pool
    manager.create_pool(
        "high_throughput",
        min_connections=10,
        max_connections=50,
        retry_policy=RetryPolicy(max_retries=1, base_delay=0.1),
        load_balancing_strategy="round_robin"
    )
    
    # Low-latency pool
    manager.create_pool(
        "low_latency",
        min_connections=5,
        max_connections=20,
        retry_policy=RetryPolicy(max_retries=3, base_delay=0.5),
        load_balancing_strategy="least_latency"
    )
    
    # Reliable pool (more retries)
    manager.create_pool(
        "reliable",
        min_connections=3,
        max_connections=10,
        retry_policy=RetryPolicy(max_retries=5, base_delay=1.0),
        load_balancing_strategy="random"
    )
    
    # Execute operations on different pools
    def test_operation(client: ModernSpacetimeDBClient) -> str:
        return f"Executed on {client.connection_id}"
    
    # High throughput operations
    for i in range(10):
        try:
            result = manager.execute_on_pool(test_operation, "high_throughput", f"ht_op_{i}")
            print(f"High throughput op {i}: Success")
        except Exception as e:
            print(f"High throughput op {i}: Failed - {e}")
    
    # Low latency operations
    for i in range(5):
        try:
            result = manager.execute_on_pool(test_operation, "low_latency", f"ll_op_{i}")
            print(f"Low latency op {i}: Success")
        except Exception as e:
            print(f"Low latency op {i}: Failed - {e}")
    
    # Get metrics for all pools
    all_metrics = manager.get_all_metrics()
    
    print("\n=== Pool Metrics Summary ===")
    for pool_name, metrics in all_metrics.items():
        print(f"\n{pool_name} pool:")
        print(f"  Connections: {metrics['healthy_connections']}/{metrics['total_connections']} healthy")
        print(f"  Operations: {metrics['total_operations']} total, {metrics['success_rate']:.1f}% success")
        print(f"  Latency: {metrics['latency_metrics']['avg_ms']:.2f}ms avg, {metrics['latency_metrics']['p95_ms']:.2f}ms p95")
    
    # Shutdown all pools
    manager.shutdown_all(graceful=True)


def test_compression_with_pool():
    """Test connection pool with compression enabled."""
    print("\n=== Testing Connection Pool with Compression ===")
    
    pool = (ModernSpacetimeDBClient.builder()
            .with_uri("ws://localhost:3000")
            .with_module_name("test_module")
            .with_compression(
                enabled=True,
                level=CompressionLevel.BEST,
                threshold=512
            )
            .with_connection_pool(
                min_connections=3,
                max_connections=5
            )
            .build_pool())
    
    # Test with operations that would benefit from compression
    def large_data_operation(client: ModernSpacetimeDBClient) -> Dict[str, Any]:
        # Simulate operation with large payload
        large_data = "x" * 10000  # 10KB of data
        
        # In real usage, this would send the data
        compression_info = client.get_compression_info()
        
        return {
            "data_size": len(large_data),
            "compression_enabled": compression_info['config']['enabled'],
            "compression_metrics": compression_info.get('metrics', {})
        }
    
    # Execute several operations
    for i in range(5):
        try:
            result = pool.execute_with_retry(large_data_operation, f"compress_op_{i}")
            print(f"Operation {i}: Sent {result['data_size']} bytes")
            if result['compression_enabled']:
                print(f"  Compression enabled, metrics: {result['compression_metrics']}")
        except Exception as e:
            print(f"Operation {i}: Failed - {e}")
    
    pool.shutdown()


if __name__ == "__main__":
    print("SpacetimeDB Advanced Connection Management Demo")
    print("=" * 50)
    
    # Note: These tests require a running SpacetimeDB instance
    # Some tests will fail gracefully if no server is available
    
    try:
        # Run synchronous tests
        test_basic_connection_pool()
        test_load_balancing_strategies()
        test_circuit_breaker()
        test_health_monitoring()
        test_multiple_pools()
        test_compression_with_pool()
        
        # Run async tests
        print("\n" + "=" * 50)
        asyncio.run(test_async_operations())
        
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"\nTest suite failed with error: {e}")
    
    print("\n" + "=" * 50)
    print("Advanced Connection Management Demo Complete!")
