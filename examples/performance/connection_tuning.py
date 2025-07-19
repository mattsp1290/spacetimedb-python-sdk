#!/usr/bin/env python3
"""
Connection Tuning Example
=========================

This example demonstrates advanced connection tuning techniques for optimal
performance in different scenarios and workloads.

Key concepts:
- Connection pool optimization
- Timeout configuration
- Retry strategies
- Load balancing
- Connection health monitoring
- Performance benchmarking

Requirements:
- spacetimedb-sdk
- asyncio
- aiohttp (for load testing)
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import time
import statistics
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from spacetimedb_sdk import SpacetimeDBClient, ConnectionPool, ConnectionBuilder
from spacetimedb_sdk.retry_policies import ExponentialBackoffRetry, LinearBackoffRetry
from spacetimedb_sdk.monitoring import PerformanceMonitor, ConnectionMetrics


class WorkloadType(Enum):
    """Different types of workloads"""
    LATENCY_SENSITIVE = "latency_sensitive"
    THROUGHPUT_FOCUSED = "throughput_focused"
    BATCH_PROCESSING = "batch_processing"
    REAL_TIME_STREAMING = "real_time_streaming"
    MIXED_WORKLOAD = "mixed_workload"


@dataclass
class ConnectionConfig:
    """Connection configuration parameters"""
    min_pool_size: int = 5
    max_pool_size: int = 20
    connection_timeout: float = 10.0
    idle_timeout: float = 300.0
    max_lifetime: float = 3600.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    keep_alive: bool = True
    tcp_nodelay: bool = True
    buffer_size: int = 65536
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy parameter passing"""
        return {
            'min_size': self.min_pool_size,
            'max_size': self.max_pool_size,
            'connection_timeout': self.connection_timeout,
            'idle_timeout': self.idle_timeout,
            'max_lifetime': self.max_lifetime,
            'retry_attempts': self.retry_attempts,
            'retry_delay': self.retry_delay,
            'keep_alive': self.keep_alive,
            'tcp_nodelay': self.tcp_nodelay,
            'buffer_size': self.buffer_size
        }


@dataclass
class BenchmarkResult:
    """Results from connection benchmarking"""
    config_name: str
    workload_type: WorkloadType
    total_operations: int
    success_rate: float
    avg_latency: float
    p95_latency: float
    p99_latency: float
    throughput: float
    error_rate: float
    connection_efficiency: float
    memory_usage: float


class ConnectionTuner:
    """Advanced connection tuning and optimization"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.monitor = PerformanceMonitor()
        self.benchmark_results: List[BenchmarkResult] = []
    
    def get_optimized_config(self, workload_type: WorkloadType) -> ConnectionConfig:
        """Get optimized configuration for specific workload type"""
        
        configs = {
            WorkloadType.LATENCY_SENSITIVE: ConnectionConfig(
                min_pool_size=10,
                max_pool_size=30,
                connection_timeout=5.0,
                idle_timeout=60.0,
                max_lifetime=1800.0,
                retry_attempts=2,
                retry_delay=0.5,
                keep_alive=True,
                tcp_nodelay=True,
                buffer_size=32768
            ),
            
            WorkloadType.THROUGHPUT_FOCUSED: ConnectionConfig(
                min_pool_size=20,
                max_pool_size=100,
                connection_timeout=15.0,
                idle_timeout=600.0,
                max_lifetime=7200.0,
                retry_attempts=5,
                retry_delay=2.0,
                keep_alive=True,
                tcp_nodelay=False,  # Allow TCP buffering for throughput
                buffer_size=131072
            ),
            
            WorkloadType.BATCH_PROCESSING: ConnectionConfig(
                min_pool_size=5,
                max_pool_size=50,
                connection_timeout=30.0,
                idle_timeout=900.0,
                max_lifetime=14400.0,
                retry_attempts=10,
                retry_delay=5.0,
                keep_alive=True,
                tcp_nodelay=False,
                buffer_size=262144
            ),
            
            WorkloadType.REAL_TIME_STREAMING: ConnectionConfig(
                min_pool_size=15,
                max_pool_size=40,
                connection_timeout=3.0,
                idle_timeout=30.0,
                max_lifetime=900.0,
                retry_attempts=1,
                retry_delay=0.1,
                keep_alive=True,
                tcp_nodelay=True,
                buffer_size=16384
            ),
            
            WorkloadType.MIXED_WORKLOAD: ConnectionConfig(
                min_pool_size=10,
                max_pool_size=50,
                connection_timeout=10.0,
                idle_timeout=300.0,
                max_lifetime=3600.0,
                retry_attempts=3,
                retry_delay=1.0,
                keep_alive=True,
                tcp_nodelay=True,
                buffer_size=65536
            )
        }
        
        return configs.get(workload_type, ConnectionConfig())
    
    async def benchmark_configuration(
        self,
        config: ConnectionConfig,
        workload_type: WorkloadType,
        test_duration: float = 30.0,
        operations_per_second: int = 100
    ) -> BenchmarkResult:
        """Benchmark a specific configuration"""
        
        print(f"\nBenchmarking {workload_type.value} configuration...")
        print(f"Pool size: {config.min_pool_size}-{config.max_pool_size}")
        print(f"Test duration: {test_duration}s")
        print(f"Target rate: {operations_per_second} ops/s")
        
        # Create connection pool with configuration
        pool = ConnectionPool(self.base_url, **config.to_dict())
        
        # Track metrics
        latencies = []
        successes = 0
        errors = 0
        start_time = time.time()
        
        # Generate workload
        async def run_operation():
            nonlocal successes, errors
            op_start = time.time()
            
            try:
                async with pool.acquire() as conn:
                    # Simulate workload-specific operation
                    await self._simulate_workload(conn, workload_type)
                    
                    op_end = time.time()
                    latencies.append(op_end - op_start)
                    successes += 1
                    
            except Exception as e:
                errors += 1
                # Still record latency for failed operations
                op_end = time.time()
                latencies.append(op_end - op_start)
        
        # Run benchmark
        tasks = []
        operation_interval = 1.0 / operations_per_second
        
        while time.time() - start_time < test_duration:
            task = asyncio.create_task(run_operation())
            tasks.append(task)
            await asyncio.sleep(operation_interval)
        
        # Wait for all operations to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate metrics
        total_operations = successes + errors
        success_rate = successes / total_operations if total_operations > 0 else 0
        avg_latency = statistics.mean(latencies) if latencies else 0
        p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else 0
        p99_latency = statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else 0
        throughput = total_operations / test_duration
        error_rate = errors / total_operations if total_operations > 0 else 0
        
        # Get pool metrics
        pool_metrics = pool.get_metrics()
        connection_efficiency = pool_metrics.get('utilization', 0)
        memory_usage = pool_metrics.get('memory_usage', 0)
        
        # Clean up
        await pool.close()
        
        result = BenchmarkResult(
            config_name=f"{workload_type.value}_optimized",
            workload_type=workload_type,
            total_operations=total_operations,
            success_rate=success_rate,
            avg_latency=avg_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            throughput=throughput,
            error_rate=error_rate,
            connection_efficiency=connection_efficiency,
            memory_usage=memory_usage
        )
        
        self.benchmark_results.append(result)
        self._print_benchmark_result(result)
        
        return result
    
    async def _simulate_workload(self, conn, workload_type: WorkloadType):
        """Simulate different types of workloads"""
        
        if workload_type == WorkloadType.LATENCY_SENSITIVE:
            # Quick operations
            await asyncio.sleep(0.01)
            
        elif workload_type == WorkloadType.THROUGHPUT_FOCUSED:
            # Moderate operations
            await asyncio.sleep(0.1)
            
        elif workload_type == WorkloadType.BATCH_PROCESSING:
            # Long-running operations
            await asyncio.sleep(1.0)
            
        elif workload_type == WorkloadType.REAL_TIME_STREAMING:
            # Very fast operations
            await asyncio.sleep(0.001)
            
        elif workload_type == WorkloadType.MIXED_WORKLOAD:
            # Variable operations
            import random
            await asyncio.sleep(random.uniform(0.01, 0.5))
    
    def _print_benchmark_result(self, result: BenchmarkResult):
        """Print benchmark results"""
        print(f"\n📊 Benchmark Results:")
        print(f"   Success Rate: {result.success_rate:.1%}")
        print(f"   Avg Latency: {result.avg_latency*1000:.1f}ms")
        print(f"   P95 Latency: {result.p95_latency*1000:.1f}ms")
        print(f"   P99 Latency: {result.p99_latency*1000:.1f}ms")
        print(f"   Throughput: {result.throughput:.1f} ops/s")
        print(f"   Error Rate: {result.error_rate:.1%}")
        print(f"   Connection Efficiency: {result.connection_efficiency:.1%}")
    
    async def compare_configurations(self, workload_type: WorkloadType):
        """Compare different configuration approaches"""
        
        print(f"\n\nConfiguration Comparison for {workload_type.value}")
        print("=" * 60)
        
        # Test configurations
        configs = {
            "default": ConnectionConfig(),
            "optimized": self.get_optimized_config(workload_type),
            "conservative": ConnectionConfig(
                min_pool_size=2,
                max_pool_size=10,
                connection_timeout=30.0,
                retry_attempts=5
            ),
            "aggressive": ConnectionConfig(
                min_pool_size=20,
                max_pool_size=200,
                connection_timeout=5.0,
                retry_attempts=1
            )
        }
        
        results = []
        for name, config in configs.items():
            print(f"\n--- Testing {name} configuration ---")
            result = await self.benchmark_configuration(
                config, workload_type, test_duration=15.0
            )
            result.config_name = name
            results.append(result)
        
        # Find best configuration
        best_config = max(results, key=lambda r: r.success_rate * r.throughput * (1 - r.error_rate))
        
        print(f"\n🏆 Best Configuration: {best_config.config_name}")
        print(f"   Overall Score: {best_config.success_rate * best_config.throughput * (1 - best_config.error_rate):.2f}")
        
        return results
    
    async def demonstrate_retry_strategies(self):
        """Demonstrate different retry strategies"""
        
        print("\n\nRetry Strategy Comparison")
        print("=" * 50)
        
        # Create connection with different retry policies
        strategies = {
            "exponential": ExponentialBackoffRetry(
                max_attempts=5,
                initial_delay=0.1,
                max_delay=10.0,
                multiplier=2.0
            ),
            "linear": LinearBackoffRetry(
                max_attempts=5,
                initial_delay=0.5,
                increment=1.0
            ),
            "fixed": ExponentialBackoffRetry(
                max_attempts=3,
                initial_delay=1.0,
                max_delay=1.0,
                multiplier=1.0
            )
        }
        
        for name, strategy in strategies.items():
            print(f"\n--- Testing {name} retry strategy ---")
            
            # Create connection pool with retry strategy
            pool = ConnectionPool(
                self.base_url,
                min_size=5,
                max_size=15,
                retry_policy=strategy
            )
            
            # Test with simulated failures
            success_count = 0
            total_attempts = 0
            
            for i in range(10):
                try:
                    async with pool.acquire() as conn:
                        # Simulate intermittent failures
                        if i % 3 == 0:
                            raise Exception("Simulated connection failure")
                        success_count += 1
                        total_attempts += 1
                except Exception:
                    total_attempts += 1
            
            success_rate = success_count / total_attempts if total_attempts > 0 else 0
            print(f"   Success rate: {success_rate:.1%}")
            print(f"   Total attempts: {total_attempts}")
            
            await pool.close()
    
    async def demonstrate_load_balancing(self):
        """Demonstrate load balancing across multiple endpoints"""
        
        print("\n\nLoad Balancing Demo")
        print("=" * 50)
        
        # Simulate multiple endpoints
        endpoints = [
            "wss://server1.example.com",
            "wss://server2.example.com",
            "wss://server3.example.com"
        ]
        
        class LoadBalancer:
            def __init__(self, endpoints: List[str]):
                self.endpoints = endpoints
                self.pools = {}
                self.current_index = 0
                self.request_counts = {endpoint: 0 for endpoint in endpoints}
            
            async def initialize(self):
                """Initialize connection pools for all endpoints"""
                for endpoint in self.endpoints:
                    self.pools[endpoint] = ConnectionPool(
                        endpoint,
                        min_size=5,
                        max_size=20
                    )
            
            async def get_connection(self, strategy: str = "round_robin"):
                """Get connection using specified load balancing strategy"""
                
                if strategy == "round_robin":
                    endpoint = self.endpoints[self.current_index]
                    self.current_index = (self.current_index + 1) % len(self.endpoints)
                
                elif strategy == "least_connections":
                    # Choose endpoint with fewest active connections
                    endpoint = min(self.endpoints, 
                                 key=lambda e: self.pools[e].get_metrics().get('active_connections', 0))
                
                elif strategy == "random":
                    import random
                    endpoint = random.choice(self.endpoints)
                
                else:
                    endpoint = self.endpoints[0]
                
                self.request_counts[endpoint] += 1
                return self.pools[endpoint].acquire()
            
            def get_distribution(self) -> Dict[str, int]:
                """Get request distribution across endpoints"""
                return self.request_counts.copy()
            
            async def close(self):
                """Close all pools"""
                for pool in self.pools.values():
                    await pool.close()
        
        # Test different load balancing strategies
        strategies = ["round_robin", "least_connections", "random"]
        
        for strategy in strategies:
            print(f"\n--- Testing {strategy} strategy ---")
            
            balancer = LoadBalancer(endpoints)
            await balancer.initialize()
            
            # Generate requests
            for i in range(30):
                try:
                    async with await balancer.get_connection(strategy):
                        # Simulate work
                        await asyncio.sleep(0.01)
                except Exception:
                    pass  # Ignore errors for demo
            
            # Show distribution
            distribution = balancer.get_distribution()
            print(f"   Request distribution:")
            for endpoint, count in distribution.items():
                print(f"     {endpoint}: {count} requests")
            
            await balancer.close()
    
    async def demonstrate_adaptive_tuning(self):
        """Demonstrate adaptive connection tuning"""
        
        print("\n\nAdaptive Tuning Demo")
        print("=" * 50)
        
        class AdaptivePool:
            def __init__(self, base_url: str):
                self.base_url = base_url
                self.current_config = ConnectionConfig()
                self.pool = None
                self.metrics_history = []
                self.tuning_interval = 10.0
                self.last_tuning = 0
            
            async def initialize(self):
                """Initialize the pool"""
                self.pool = ConnectionPool(self.base_url, **self.current_config.to_dict())
            
            async def acquire(self):
                """Acquire connection with adaptive tuning"""
                # Check if tuning is needed
                current_time = time.time()
                if current_time - self.last_tuning > self.tuning_interval:
                    await self._tune_pool()
                    self.last_tuning = current_time
                
                return self.pool.acquire()
            
            async def _tune_pool(self):
                """Automatically tune pool parameters"""
                metrics = self.pool.get_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only recent metrics
                if len(self.metrics_history) > 5:
                    self.metrics_history.pop(0)
                
                if len(self.metrics_history) < 2:
                    return
                
                # Calculate trends
                current = self.metrics_history[-1]
                previous = self.metrics_history[-2]
                
                utilization = current.get('utilization', 0)
                wait_time = current.get('avg_wait_time', 0)
                error_rate = current.get('error_rate', 0)
                
                print(f"\n🔧 Adaptive tuning triggered:")
                print(f"   Utilization: {utilization:.1%}")
                print(f"   Wait time: {wait_time*1000:.1f}ms")
                print(f"   Error rate: {error_rate:.1%}")
                
                # Adjust pool size based on metrics
                if utilization > 0.8 and wait_time > 0.1:
                    # Increase pool size
                    new_max = min(self.current_config.max_pool_size + 5, 100)
                    self.current_config.max_pool_size = new_max
                    print(f"   📈 Increased max pool size to {new_max}")
                
                elif utilization < 0.3 and self.current_config.max_pool_size > 10:
                    # Decrease pool size
                    new_max = max(self.current_config.max_pool_size - 5, 10)
                    self.current_config.max_pool_size = new_max
                    print(f"   📉 Decreased max pool size to {new_max}")
                
                # Adjust timeouts based on error rate
                if error_rate > 0.05:
                    # Increase timeouts
                    self.current_config.connection_timeout = min(
                        self.current_config.connection_timeout * 1.5, 30.0
                    )
                    print(f"   ⏱️  Increased timeout to {self.current_config.connection_timeout:.1f}s")
                
                # Apply changes by recreating pool
                await self.pool.close()
                self.pool = ConnectionPool(self.base_url, **self.current_config.to_dict())
            
            async def close(self):
                """Close the pool"""
                if self.pool:
                    await self.pool.close()
        
        # Test adaptive tuning
        adaptive_pool = AdaptivePool(self.base_url)
        await adaptive_pool.initialize()
        
        print("\nTesting adaptive tuning over 60 seconds...")
        
        # Simulate varying load
        load_phases = [
            (10, 20),  # Low load
            (30, 100), # High load
            (20, 50),  # Medium load
        ]
        
        for duration, ops_per_sec in load_phases:
            print(f"\n--- Load phase: {ops_per_sec} ops/s for {duration}s ---")
            
            start_time = time.time()
            operation_interval = 1.0 / ops_per_sec
            
            while time.time() - start_time < duration:
                try:
                    async with await adaptive_pool.acquire():
                        await asyncio.sleep(0.01)
                except Exception:
                    pass
                
                await asyncio.sleep(operation_interval)
        
        await adaptive_pool.close()
    
    def print_summary_report(self):
        """Print summary of all benchmark results"""
        
        print("\n\n📊 PERFORMANCE TUNING SUMMARY")
        print("=" * 60)
        
        if not self.benchmark_results:
            print("No benchmark results available")
            return
        
        # Group results by workload type
        workload_results = {}
        for result in self.benchmark_results:
            workload = result.workload_type
            if workload not in workload_results:
                workload_results[workload] = []
            workload_results[workload].append(result)
        
        # Print recommendations for each workload
        for workload, results in workload_results.items():
            print(f"\n{workload.value.upper()} WORKLOAD:")
            print("-" * 40)
            
            best_result = max(results, key=lambda r: r.success_rate * r.throughput)
            
            print(f"🏆 Best Configuration: {best_result.config_name}")
            print(f"   Success Rate: {best_result.success_rate:.1%}")
            print(f"   Throughput: {best_result.throughput:.1f} ops/s")
            print(f"   Avg Latency: {best_result.avg_latency*1000:.1f}ms")
            print(f"   P95 Latency: {best_result.p95_latency*1000:.1f}ms")
            
            # Configuration recommendations
            config = self.get_optimized_config(workload)
            print(f"\n📋 Recommended Settings:")
            print(f"   Pool Size: {config.min_pool_size}-{config.max_pool_size}")
            print(f"   Connection Timeout: {config.connection_timeout}s")
            print(f"   Retry Attempts: {config.retry_attempts}")
            print(f"   TCP NoDelay: {config.tcp_nodelay}")
            print(f"   Buffer Size: {config.buffer_size} bytes")


async def main():
    """Run connection tuning demonstrations"""
    
    print("SpacetimeDB Connection Tuning Demo")
    print("=" * 50)
    
    # Initialize tuner
    tuner = ConnectionTuner("wss://example.spacetimedb.com")
    
    try:
        # Test different workload types
        workload_types = [
            WorkloadType.LATENCY_SENSITIVE,
            WorkloadType.THROUGHPUT_FOCUSED,
            WorkloadType.BATCH_PROCESSING,
            WorkloadType.REAL_TIME_STREAMING
        ]
        
        for workload_type in workload_types:
            await tuner.compare_configurations(workload_type)
        
        # Demonstrate advanced features
        await tuner.demonstrate_retry_strategies()
        await tuner.demonstrate_load_balancing()
        await tuner.demonstrate_adaptive_tuning()
        
        # Print final summary
        tuner.print_summary_report()
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())