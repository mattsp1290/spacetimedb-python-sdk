#!/usr/bin/env python3
"""
Performance benchmark for connection pool O(1) optimizations.

This script tests the performance improvements of the optimized connection pool
by comparing connection acquisition times with varying pool sizes.
"""

import sys
import os
import time
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
from typing import List, Dict, Any

# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.connection_pool import ConnectionPool, PooledConnection
from spacetimedb_sdk.shared_types import PooledConnectionState, RetryPolicy


def create_mock_client():
    """Create a mock SpacetimeDB client for testing."""
    mock_client = Mock()
    mock_client.is_connected = True
    mock_client.connection_id = f"mock_connection_{time.time()}"
    mock_client.connect = Mock(return_value=True)
    mock_client.disconnect = Mock()
    return mock_client


def benchmark_connection_acquisition(pool_size: int, num_operations: int, num_threads: int = 10) -> Dict[str, Any]:
    """
    Benchmark connection acquisition performance.
    
    Args:
        pool_size: Number of connections in the pool
        num_operations: Number of operations to perform
        num_threads: Number of concurrent threads
        
    Returns:
        Performance metrics
    """
    print(f"\n=== Benchmarking pool size: {pool_size}, operations: {num_operations}, threads: {num_threads} ===")
    
    # Create connection pool with mocked connections
    with patch('spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient.builder'):
        pool = ConnectionPool(
            min_connections=pool_size,
            max_connections=pool_size,
            connection_config={
                'uri': 'ws://localhost:3000',
                'module_name': 'test_module'
            },
            health_check_interval=30.0
        )
        
        # Mock all connections to be healthy
        for conn_id, conn in pool.connections.items():
            conn.client = create_mock_client()
            conn.state = PooledConnectionState.IDLE
            conn.last_health_check = time.time()
    
    # Warm up the healthy cache
    pool._refresh_healthy_cache()
    
    acquisition_times = []
    operation_times = []
    
    def perform_operations(thread_id: int, operations_per_thread: int) -> List[float]:
        """Perform connection acquisitions in a thread."""
        thread_times = []
        
        for i in range(operations_per_thread):
            start_time = time.time()
            
            # Acquire connection
            connection = pool.get_connection()
            
            if connection:
                # Hold connection briefly to simulate work
                time.sleep(0.001)  # 1ms of work
                
                # Release connection
                pool.release_connection(connection)
                
                acquisition_time = (time.time() - start_time) * 1000  # Convert to ms
                thread_times.append(acquisition_time)
            else:
                # Failed to get connection
                thread_times.append(-1)
        
        return thread_times
    
    # Execute operations across multiple threads
    start_benchmark = time.time()
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        operations_per_thread = num_operations // num_threads
        remaining_operations = num_operations % num_threads
        
        # Submit tasks
        futures = []
        for thread_id in range(num_threads):
            thread_ops = operations_per_thread + (1 if thread_id < remaining_operations else 0)
            if thread_ops > 0:
                future = executor.submit(perform_operations, thread_id, thread_ops)
                futures.append(future)
        
        # Collect results
        for future in as_completed(futures):
            thread_times = future.result()
            acquisition_times.extend([t for t in thread_times if t >= 0])
    
    total_benchmark_time = time.time() - start_benchmark
    
    # Get pool metrics
    pool_metrics = pool.get_pool_metrics()
    
    # Calculate performance statistics
    if acquisition_times:
        avg_time = statistics.mean(acquisition_times)
        median_time = statistics.median(acquisition_times)
        p95_time = sorted(acquisition_times)[int(len(acquisition_times) * 0.95)]
        p99_time = sorted(acquisition_times)[int(len(acquisition_times) * 0.99)]
        max_time = max(acquisition_times)
        min_time = min(acquisition_times)
    else:
        avg_time = median_time = p95_time = p99_time = max_time = min_time = 0
    
    # Calculate throughput
    successful_operations = len(acquisition_times)
    throughput = successful_operations / total_benchmark_time if total_benchmark_time > 0 else 0
    
    # Shutdown pool
    pool.shutdown(graceful=False)
    
    return {
        'pool_size': pool_size,
        'num_operations': num_operations,
        'num_threads': num_threads,
        'successful_operations': successful_operations,
        'total_time_seconds': total_benchmark_time,
        'throughput_ops_per_second': throughput,
        'acquisition_times_ms': {
            'avg': avg_time,
            'median': median_time,
            'min': min_time,
            'max': max_time,
            'p95': p95_time,
            'p99': p99_time
        },
        'cache_metrics': {
            'hit_rate_percent': pool_metrics['performance_optimizations']['cache_hit_rate_percent'],
            'cache_hits': pool_metrics['performance_optimizations']['cache_hits'],
            'cache_misses': pool_metrics['performance_optimizations']['cache_misses'],
            'healthy_cache_size': pool_metrics['performance_optimizations']['healthy_cache_size']
        }
    }


def run_scaling_benchmark():
    """Run benchmarks with different pool sizes to test O(1) scaling."""
    print("Running Connection Pool Performance Benchmark")
    print("=" * 60)
    
    # Test different pool sizes to verify O(1) performance
    pool_sizes = [10, 50, 100, 200, 500, 1000]
    operations_per_test = 1000
    threads_per_test = 20
    
    results = []
    
    for pool_size in pool_sizes:
        try:
            result = benchmark_connection_acquisition(
                pool_size=pool_size,
                num_operations=operations_per_test,
                num_threads=threads_per_test
            )
            results.append(result)
            
            # Print immediate results
            print(f"Pool Size: {pool_size}")
            print(f"  Throughput: {result['throughput_ops_per_second']:.1f} ops/sec")
            print(f"  Avg Acquisition Time: {result['acquisition_times_ms']['avg']:.3f}ms")
            print(f"  P95 Acquisition Time: {result['acquisition_times_ms']['p95']:.3f}ms")
            print(f"  Cache Hit Rate: {result['cache_metrics']['hit_rate_percent']:.1f}%")
            
        except Exception as e:
            print(f"Error benchmarking pool size {pool_size}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    print("\n" + "=" * 60)
    print("PERFORMANCE BENCHMARK SUMMARY")
    print("=" * 60)
    
    print(f"{'Pool Size':<10} {'Throughput':<12} {'Avg Time':<10} {'P95 Time':<10} {'Cache Hit':<10}")
    print(f"{'(conns)':<10} {'(ops/sec)':<12} {'(ms)':<10} {'(ms)':<10} {'Rate (%)':<10}")
    print("-" * 60)
    
    for result in results:
        print(f"{result['pool_size']:<10} "
              f"{result['throughput_ops_per_second']:<12.1f} "
              f"{result['acquisition_times_ms']['avg']:<10.3f} "
              f"{result['acquisition_times_ms']['p95']:<10.3f} "
              f"{result['cache_metrics']['hit_rate_percent']:<10.1f}")
    
    # Analyze scaling characteristics
    print("\n" + "=" * 60)
    print("SCALING ANALYSIS")
    print("=" * 60)
    
    if len(results) >= 2:
        # Compare smallest vs largest pool
        small_pool = results[0]
        large_pool = results[-1]
        
        size_ratio = large_pool['pool_size'] / small_pool['pool_size']
        time_ratio = large_pool['acquisition_times_ms']['avg'] / small_pool['acquisition_times_ms']['avg'] if small_pool['acquisition_times_ms']['avg'] > 0 else 1
        
        print(f"Pool size increased by factor: {size_ratio:.1f}x")
        print(f"Avg acquisition time increased by factor: {time_ratio:.2f}x")
        
        if time_ratio < 2.0:
            print("✅ EXCELLENT: Nearly O(1) performance maintained!")
        elif time_ratio < 5.0:
            print("✅ GOOD: Sub-linear performance scaling")
        else:
            print("⚠️  WARNING: Performance degradation detected")
        
        # Check if target performance is met
        target_latency_ms = 1.0
        target_throughput = 1000
        
        print(f"\nTarget Performance Check:")
        print(f"  Target latency: <{target_latency_ms}ms")
        print(f"  Target throughput: >{target_throughput} ops/sec")
        
        for result in results:
            if (result['acquisition_times_ms']['avg'] <= target_latency_ms and 
                result['throughput_ops_per_second'] >= target_throughput):
                print(f"  ✅ Pool size {result['pool_size']}: MEETS TARGETS")
            else:
                print(f"  ❌ Pool size {result['pool_size']}: Below targets")


def run_stress_test():
    """Run stress test with high concurrency."""
    print("\n" + "=" * 60)
    print("STRESS TEST - High Concurrency")
    print("=" * 60)
    
    try:
        result = benchmark_connection_acquisition(
            pool_size=100,
            num_operations=5000,
            num_threads=50
        )
        
        print("Stress Test Results:")
        print(f"  Pool Size: {result['pool_size']} connections")
        print(f"  Operations: {result['successful_operations']}/{result['num_operations']}")
        print(f"  Threads: {result['num_threads']}")
        print(f"  Total Time: {result['total_time_seconds']:.2f}s")
        print(f"  Throughput: {result['throughput_ops_per_second']:.1f} ops/sec")
        print(f"  Average Latency: {result['acquisition_times_ms']['avg']:.3f}ms")
        print(f"  P99 Latency: {result['acquisition_times_ms']['p99']:.3f}ms")
        print(f"  Cache Hit Rate: {result['cache_metrics']['hit_rate_percent']:.1f}%")
        
        # Check stress test success criteria
        success_criteria = [
            result['throughput_ops_per_second'] >= 1000,
            result['acquisition_times_ms']['p99'] <= 5.0,
            result['cache_metrics']['hit_rate_percent'] >= 80.0
        ]
        
        if all(success_criteria):
            print("  ✅ STRESS TEST PASSED")
        else:
            print("  ❌ STRESS TEST FAILED")
            
    except Exception as e:
        print(f"Stress test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        run_scaling_benchmark()
        run_stress_test()
        
        print("\n" + "=" * 60)
        print("🎉 PERFORMANCE BENCHMARK COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)