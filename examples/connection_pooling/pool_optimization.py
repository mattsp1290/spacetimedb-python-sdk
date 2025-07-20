#!/usr/bin/env python3
"""
Connection Pool Optimization Example
====================================

This example demonstrates how to optimize connection pool settings for different
usage patterns and workloads.

Key concepts covered:
- Pool size tuning based on workload characteristics
- Connection reuse strategies
- Resource management and monitoring
- Performance optimization techniques

Requirements:
- spacetimedb-sdk
- asyncio
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from contextlib import asynccontextmanager

from spacetimedb_sdk import ConnectionPool, ConnectionBuilder
from spacetimedb_sdk.monitoring import PerformanceMonitor, PoolMetrics


@dataclass
class WorkloadProfile:
    """Represents different types of workload patterns"""
    name: str
    concurrent_operations: int
    operation_duration: float
    burst_pattern: bool
    read_write_ratio: float  # 0.0 = all writes, 1.0 = all reads


class PoolOptimizer:
    """Demonstrates connection pool optimization techniques"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.monitor = PerformanceMonitor()
        self.pools: Dict[str, ConnectionPool] = {}
    
    def create_optimized_pool(self, profile: WorkloadProfile) -> ConnectionPool:
        """Create a pool optimized for specific workload profile"""
        
        # Calculate optimal pool size based on workload characteristics
        pool_size = self._calculate_optimal_pool_size(profile)
        
        # Configure pool parameters
        pool_config = {
            'min_size': max(1, pool_size // 4),
            'max_size': pool_size,
            'connection_timeout': 30.0 if profile.burst_pattern else 10.0,
            'idle_timeout': 300.0 if profile.read_write_ratio > 0.7 else 60.0,
            'max_lifetime': 3600.0,  # 1 hour
            'validation_interval': 30.0,
            'retry_policy': {
                'max_attempts': 3 if profile.burst_pattern else 2,
                'backoff_factor': 2.0,
                'max_delay': 10.0
            }
        }
        
        # Create pool with optimized settings
        pool = ConnectionPool(self.base_url, **pool_config)
        
        # Enable performance monitoring
        pool.enable_monitoring(self.monitor)
        
        return pool
    
    def _calculate_optimal_pool_size(self, profile: WorkloadProfile) -> int:
        """Calculate optimal pool size based on Little's Law and workload characteristics"""
        
        # Little's Law: Pool Size = Arrival Rate × Service Time
        # Add buffer for burst handling
        base_size = profile.concurrent_operations
        
        if profile.burst_pattern:
            # Add 50% buffer for burst handling
            base_size = int(base_size * 1.5)
        
        # Adjust for operation duration
        if profile.operation_duration > 1.0:
            # Long operations need more connections
            base_size = int(base_size * (1 + profile.operation_duration / 10))
        
        # Minimum and maximum bounds
        return max(5, min(base_size, 100))
    
    async def demonstrate_pool_optimization(self):
        """Demonstrate pool optimization for different workloads"""
        
        # Define different workload profiles
        workloads = [
            WorkloadProfile(
                name="High Frequency Trading",
                concurrent_operations=50,
                operation_duration=0.1,
                burst_pattern=True,
                read_write_ratio=0.8
            ),
            WorkloadProfile(
                name="Batch Processing",
                concurrent_operations=10,
                operation_duration=5.0,
                burst_pattern=False,
                read_write_ratio=0.3
            ),
            WorkloadProfile(
                name="Real-time Analytics",
                concurrent_operations=20,
                operation_duration=0.5,
                burst_pattern=True,
                read_write_ratio=0.9
            ),
            WorkloadProfile(
                name="CRUD Application",
                concurrent_operations=15,
                operation_duration=0.3,
                burst_pattern=False,
                read_write_ratio=0.5
            )
        ]
        
        print("Connection Pool Optimization Demo")
        print("=" * 50)
        
        for profile in workloads:
            print(f"\nOptimizing for: {profile.name}")
            print(f"Characteristics:")
            print(f"  - Concurrent ops: {profile.concurrent_operations}")
            print(f"  - Op duration: {profile.operation_duration}s")
            print(f"  - Burst pattern: {profile.burst_pattern}")
            print(f"  - Read ratio: {profile.read_write_ratio:.0%}")
            
            # Create optimized pool
            pool = self.create_optimized_pool(profile)
            self.pools[profile.name] = pool
            
            print(f"\nOptimized settings:")
            print(f"  - Pool size: {pool.min_size}-{pool.max_size}")
            print(f"  - Connection timeout: {pool.connection_timeout}s")
            print(f"  - Idle timeout: {pool.idle_timeout}s")
            
            # Run benchmark
            metrics = await self._benchmark_pool(pool, profile)
            self._print_metrics(metrics)
    
    async def _benchmark_pool(self, pool: ConnectionPool, profile: WorkloadProfile) -> Dict[str, Any]:
        """Benchmark pool performance with given workload"""
        
        start_time = time.time()
        completed_ops = 0
        errors = 0
        
        async def simulate_operation():
            nonlocal completed_ops, errors
            try:
                async with pool.acquire() as conn:
                    # Simulate operation
                    await asyncio.sleep(profile.operation_duration)
                    completed_ops += 1
            except Exception as e:
                errors += 1
                print(f"Operation failed: {e}")
        
        # Run concurrent operations
        tasks = []
        for _ in range(profile.concurrent_operations * 10):  # 10 rounds
            task = asyncio.create_task(simulate_operation())
            tasks.append(task)
            
            # Add delay between operations for burst pattern
            if not profile.burst_pattern:
                await asyncio.sleep(0.01)
        
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        
        # Collect metrics
        pool_metrics = pool.get_metrics()
        
        return {
            'duration': duration,
            'operations': completed_ops,
            'errors': errors,
            'throughput': completed_ops / duration,
            'error_rate': errors / (completed_ops + errors) if (completed_ops + errors) > 0 else 0,
            'pool_metrics': pool_metrics
        }
    
    def _print_metrics(self, metrics: Dict[str, Any]):
        """Print benchmark metrics"""
        print(f"\nBenchmark results:")
        print(f"  - Duration: {metrics['duration']:.2f}s")
        print(f"  - Operations: {metrics['operations']}")
        print(f"  - Throughput: {metrics['throughput']:.2f} ops/s")
        print(f"  - Error rate: {metrics['error_rate']:.2%}")
        
        pool_metrics = metrics['pool_metrics']
        if pool_metrics:
            print(f"\nPool metrics:")
            print(f"  - Active connections: {pool_metrics.get('active_connections', 0)}")
            print(f"  - Idle connections: {pool_metrics.get('idle_connections', 0)}")
            print(f"  - Wait queue size: {pool_metrics.get('wait_queue_size', 0)}")
            print(f"  - Connection reuse rate: {pool_metrics.get('reuse_rate', 0):.2%}")
    
    async def demonstrate_adaptive_tuning(self):
        """Demonstrate adaptive pool tuning based on runtime metrics"""
        
        print("\n\nAdaptive Pool Tuning Demo")
        print("=" * 50)
        
        # Create initial pool
        pool = ConnectionPool(
            self.base_url,
            min_size=5,
            max_size=20,
            enable_auto_tuning=True
        )
        
        # Configure auto-tuning parameters
        pool.configure_auto_tuning(
            target_wait_time=0.1,  # Target 100ms wait time
            target_utilization=0.7,  # Target 70% utilization
            adjustment_interval=10.0,  # Check every 10 seconds
            max_adjustment=5  # Max 5 connections per adjustment
        )
        
        print("Initial pool configuration:")
        print(f"  - Size: {pool.min_size}-{pool.max_size}")
        print(f"  - Auto-tuning: Enabled")
        print(f"  - Target wait time: 100ms")
        print(f"  - Target utilization: 70%")
        
        # Simulate varying workload
        workload_phases = [
            ("Low load", 5, 0.1),
            ("Medium load", 15, 0.2),
            ("High load", 30, 0.1),
            ("Burst", 50, 0.05),
            ("Normal", 20, 0.15)
        ]
        
        for phase_name, concurrent_ops, duration in workload_phases:
            print(f"\n{phase_name} phase ({concurrent_ops} concurrent ops)...")
            
            # Run workload
            tasks = []
            for _ in range(concurrent_ops * 20):
                task = asyncio.create_task(self._run_operation(pool, duration))
                tasks.append(task)
                await asyncio.sleep(0.01)
            
            # Wait for some operations to complete
            await asyncio.sleep(5)
            
            # Check current pool state
            metrics = pool.get_metrics()
            print(f"  - Current pool size: {metrics.get('current_size', 0)}")
            print(f"  - Average wait time: {metrics.get('avg_wait_time', 0):.3f}s")
            print(f"  - Utilization: {metrics.get('utilization', 0):.2%}")
        
        await asyncio.gather(*tasks)
    
    async def _run_operation(self, pool: ConnectionPool, duration: float):
        """Run a single operation on the pool"""
        try:
            async with pool.acquire() as conn:
                await asyncio.sleep(duration)
        except Exception:
            pass  # Ignore errors for demo
    
    async def demonstrate_connection_health_monitoring(self):
        """Demonstrate connection health monitoring and recovery"""
        
        print("\n\nConnection Health Monitoring Demo")
        print("=" * 50)
        
        # Create pool with health monitoring
        pool = ConnectionPool(
            self.base_url,
            min_size=5,
            max_size=10,
            health_check_interval=5.0,
            health_check_timeout=1.0
        )
        
        # Configure health check
        async def health_check(conn):
            """Custom health check function"""
            try:
                # Ping the connection
                await conn.ping()
                return True
            except Exception:
                return False
        
        pool.set_health_check(health_check)
        
        print("Health monitoring configuration:")
        print(f"  - Check interval: 5s")
        print(f"  - Check timeout: 1s")
        print(f"  - Recovery enabled: Yes")
        
        # Monitor pool health
        for i in range(5):
            await asyncio.sleep(5)
            
            health_metrics = pool.get_health_metrics()
            print(f"\nHealth check #{i+1}:")
            print(f"  - Healthy connections: {health_metrics.get('healthy', 0)}")
            print(f"  - Unhealthy connections: {health_metrics.get('unhealthy', 0)}")
            print(f"  - Recovery attempts: {health_metrics.get('recovery_attempts', 0)}")
            print(f"  - Last check: {health_metrics.get('last_check', 'N/A')}")
    
    def print_optimization_recommendations(self):
        """Print optimization recommendations based on collected metrics"""
        
        print("\n\nOptimization Recommendations")
        print("=" * 50)
        
        for pool_name, pool in self.pools.items():
            metrics = pool.get_metrics()
            
            print(f"\n{pool_name}:")
            
            # Analyze metrics and provide recommendations
            utilization = metrics.get('utilization', 0)
            wait_time = metrics.get('avg_wait_time', 0)
            error_rate = metrics.get('error_rate', 0)
            
            recommendations = []
            
            if utilization > 0.9:
                recommendations.append("- Increase max pool size (high utilization)")
            elif utilization < 0.3:
                recommendations.append("- Decrease max pool size (low utilization)")
            
            if wait_time > 1.0:
                recommendations.append("- Increase min pool size (high wait times)")
            
            if error_rate > 0.05:
                recommendations.append("- Check connection stability")
                recommendations.append("- Increase retry attempts")
            
            if not recommendations:
                recommendations.append("- Pool is well-optimized for current workload")
            
            for rec in recommendations:
                print(rec)
    
    async def cleanup(self):
        """Clean up all pools"""
        for pool in self.pools.values():
            await pool.close()


async def main():
    """Run the connection pool optimization examples"""
    
    # Initialize optimizer
    optimizer = PoolOptimizer("wss://example.spacetimedb.com")
    
    try:
        # Run demonstrations
        await optimizer.demonstrate_pool_optimization()
        await optimizer.demonstrate_adaptive_tuning()
        await optimizer.demonstrate_connection_health_monitoring()
        
        # Print recommendations
        optimizer.print_optimization_recommendations()
        
    finally:
        await optimizer.cleanup()


if __name__ == "__main__":
    asyncio.run(main())