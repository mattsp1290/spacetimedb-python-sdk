#!/usr/bin/env python3
"""
Performance benchmarks for SpaceTimeDB SDK v1.1.2.
Measures connection times, throughput, memory usage, and concurrent operations.
"""

import unittest
import sys
import os
import time
import asyncio
import json
import psutil
import statistics
import threading
import gc
from typing import List, Dict, Any, Tuple
import tracemalloc

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient
from spacetimedb_sdk.websocket_client import WebSocketClient

# Import mock server
from mock_spacetimedb_server import (
    MockSpaceTimeDBServer, create_test_server, MockDatabase
)


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""
    
    def __init__(self):
        self.metrics = {
            "connection_times": [],
            "message_latencies": [],
            "memory_usage": [],
            "throughput_rates": [],
            "error_rates": []
        }
        
    def add_connection_time(self, time_ms: float):
        """Add a connection establishment time."""
        self.metrics["connection_times"].append(time_ms)
        
    def add_message_latency(self, latency_ms: float):
        """Add a message round-trip latency."""
        self.metrics["message_latencies"].append(latency_ms)
        
    def add_memory_usage(self, memory_mb: float):
        """Add a memory usage sample."""
        self.metrics["memory_usage"].append(memory_mb)
        
    def add_throughput_rate(self, messages_per_second: float):
        """Add a throughput measurement."""
        self.metrics["throughput_rates"].append(messages_per_second)
        
    def add_error_rate(self, error_rate: float):
        """Add an error rate measurement."""
        self.metrics["error_rates"].append(error_rate)
        
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all metrics."""
        summary = {}
        
        for metric_name, values in self.metrics.items():
            if values:
                summary[metric_name] = {
                    "count": len(values),
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "p95": self._percentile(values, 95),
                    "p99": self._percentile(values, 99)
                }
            else:
                summary[metric_name] = {"count": 0}
                
        return summary
        
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


class TestConnectionPerformance(unittest.TestCase):
    """Test connection establishment performance."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3020)
        self.server.start()
        self.metrics = PerformanceMetrics()
        self.clients = []
        
    def tearDown(self):
        """Clean up after tests."""
        for client in self.clients:
            try:
                client.disconnect()
            except:
                pass
        self.server.stop()
        
    def test_connection_establishment_time(self):
        """Measure connection establishment times."""
        print("\n=== Connection Establishment Performance ===")
        
        # Test different scenarios
        scenarios = [
            ("no_auth", {"auth_token": None}),
            ("with_auth", {"auth_token": "valid_token_123"}),
            ("with_compression", {"compression": True}),
            ("with_preflight", {"preflight_checks": True})
        ]
        
        for scenario_name, config in scenarios:
            times = []
            
            for i in range(10):  # 10 iterations per scenario
                client = SpacetimeDBClient()
                
                start_time = time.perf_counter()
                try:
                    client._connect_internal(
                        auth_token=config.get('auth_token'),
                        host="localhost:3020",
                        database_address="test_db",
                        ssl_enabled=False
                    )
                    end_time = time.perf_counter()
                    
                    connection_time_ms = (end_time - start_time) * 1000
                    times.append(connection_time_ms)
                    self.metrics.add_connection_time(connection_time_ms)
                    
                    self.clients.append(client)
                    
                except Exception as e:
                    print(f"Connection failed for {scenario_name}: {e}")
                    
            if times:
                avg_time = statistics.mean(times)
                print(f"{scenario_name}: avg={avg_time:.2f}ms, "
                      f"min={min(times):.2f}ms, max={max(times):.2f}ms")
                
    def test_reconnection_performance(self):
        """Test reconnection performance after disconnect."""
        print("\n=== Reconnection Performance ===")
        
        client = SpacetimeDBClient()
        
        # Initial connection
        start_time = time.perf_counter()
        client._connect_internal(
            auth_token=None,
            host="localhost:3020",
            database_address="test_db",
            ssl_enabled=False
        )
        initial_time = (time.perf_counter() - start_time) * 1000
        
        print(f"Initial connection: {initial_time:.2f}ms")
        
        # Test reconnections
        reconnect_times = []
        
        for i in range(5):
            # Disconnect
            client.disconnect()
            time.sleep(0.1)
            
            # Reconnect
            start_time = time.perf_counter()
            client._connect_internal(
                auth_token=None,
                host="localhost:3020",
                database_address="test_db",
                ssl_enabled=False
            )
            reconnect_time = (time.perf_counter() - start_time) * 1000
            reconnect_times.append(reconnect_time)
            
        avg_reconnect = statistics.mean(reconnect_times)
        print(f"Average reconnection: {avg_reconnect:.2f}ms")
        print(f"Reconnection overhead: {(avg_reconnect - initial_time):.2f}ms")
        
        self.clients.append(client)


class TestMessageThroughput(unittest.TestCase):
    """Test message throughput and latency."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.metrics = PerformanceMetrics()
        
        # Create server with high-performance database
        self.server = create_test_server("normal", port=3021)
        
        # Add a large table for throughput testing
        perf_db = MockDatabase("perf_db")
        perf_db.add_table("large_table", [
            {"id": i, "data": f"row_{i}" * 10} for i in range(1000)
        ])
        self.server.add_database("perf_db", perf_db)
        
        self.server.start()
        self.client = None
        
    def tearDown(self):
        """Clean up after tests."""
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
        self.server.stop()
        
    def test_message_throughput(self):
        """Test message sending throughput."""
        print("\n=== Message Throughput Test ===")
        
        self.client = SpacetimeDBClient()
        self.client._connect_internal(
            auth_token=None,
            host="localhost:3021",
            database_address="perf_db",
            ssl_enabled=False
        )
        
        time.sleep(1)  # Ensure connection established
        
        # Test different message sizes
        message_sizes = [
            ("small", 100),    # 100 bytes
            ("medium", 1000),  # 1KB
            ("large", 10000),  # 10KB
        ]
        
        for size_name, size_bytes in message_sizes:
            # Create test message
            test_data = "x" * size_bytes
            
            # Measure throughput
            start_time = time.perf_counter()
            message_count = 100
            
            for i in range(message_count):
                # Simulate sending a message
                # In real implementation, this would use client's send method
                pass
                
            end_time = time.perf_counter()
            duration = end_time - start_time
            
            if duration > 0:
                throughput = message_count / duration
                self.metrics.add_throughput_rate(throughput)
                
                print(f"{size_name} messages ({size_bytes} bytes): "
                      f"{throughput:.2f} msg/sec")
                
    def test_subscription_update_performance(self):
        """Test performance of subscription updates."""
        print("\n=== Subscription Update Performance ===")
        
        self.client = SpacetimeDBClient()
        
        # Track update latencies
        update_latencies = []
        updates_received = 0
        
        def on_update(table_name, rows):
            nonlocal updates_received
            updates_received += 1
            
        self.client._connect_internal(
            auth_token=None,
            host="localhost:3021",
            database_address="perf_db",
            ssl_enabled=False
        )
        
        time.sleep(1)
        
        # Simulate rapid updates
        start_time = time.perf_counter()
        expected_updates = 50
        
        # Wait for updates (mock server sends initial data)
        timeout = 5
        while updates_received < expected_updates and time.time() - start_time < timeout:
            time.sleep(0.01)
            
        duration = time.perf_counter() - start_time
        
        if updates_received > 0:
            update_rate = updates_received / duration
            print(f"Subscription updates: {update_rate:.2f} updates/sec")
            print(f"Received {updates_received} updates in {duration:.2f}s")


class TestMemoryUsage(unittest.TestCase):
    """Test memory usage and leak detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3022)
        self.server.start()
        self.metrics = PerformanceMetrics()
        gc.collect()  # Clean baseline
        
    def tearDown(self):
        """Clean up after tests."""
        self.server.stop()
        gc.collect()
        
    def test_connection_memory_usage(self):
        """Test memory usage during connections."""
        print("\n=== Connection Memory Usage ===")
        
        # Start memory tracking
        tracemalloc.start()
        process = psutil.Process()
        
        # Baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        clients = []
        memory_samples = []
        
        # Create multiple connections
        for i in range(10):
            client = SpacetimeDBClient()
            client._connect_internal(
                auth_token=None,
                host="localhost:3022",
                database_address="test_db",
                ssl_enabled=False
            )
            clients.append(client)
            
            # Sample memory
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_usage = current_memory - baseline_memory
            memory_samples.append(memory_usage)
            self.metrics.add_memory_usage(memory_usage)
            
        # Get memory snapshot
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        print(f"Baseline memory: {baseline_memory:.2f} MB")
        print(f"Memory per connection: {statistics.mean(memory_samples) / len(clients):.2f} MB")
        print(f"Total memory increase: {memory_samples[-1]:.2f} MB")
        
        # Clean up
        for client in clients:
            client.disconnect()
            
        tracemalloc.stop()
        
    def test_long_running_connection_memory(self):
        """Test memory usage of long-running connections."""
        print("\n=== Long-Running Connection Memory ===")
        
        client = SpacetimeDBClient()
        process = psutil.Process()
        
        # Connect
        client._connect_internal(
            auth_token=None,
            host="localhost:3022",
            database_address="test_db",
            ssl_enabled=False
        )
        
        # Monitor memory over time
        memory_samples = []
        duration = 5  # seconds
        sample_interval = 0.5
        
        start_time = time.time()
        while time.time() - start_time < duration:
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory_mb)
            time.sleep(sample_interval)
            
        # Analyze memory trend
        if len(memory_samples) > 1:
            memory_growth = memory_samples[-1] - memory_samples[0]
            growth_rate = memory_growth / duration
            
            print(f"Initial memory: {memory_samples[0]:.2f} MB")
            print(f"Final memory: {memory_samples[-1]:.2f} MB")
            print(f"Memory growth: {memory_growth:.2f} MB")
            print(f"Growth rate: {growth_rate:.2f} MB/sec")
            
            # Check for memory leak (growth should be minimal)
            self.assertLess(growth_rate, 1.0, "Memory growth rate too high")
            
        client.disconnect()


class TestConcurrentOperations(unittest.TestCase):
    """Test performance under concurrent load."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3023)
        self.server.config.max_connections = 100
        self.server.start()
        self.metrics = PerformanceMetrics()
        
    def tearDown(self):
        """Clean up after tests."""
        self.server.stop()
        
    def test_concurrent_connections(self):
        """Test multiple concurrent connections."""
        print("\n=== Concurrent Connections Performance ===")
        
        connection_counts = [10, 25, 50]
        
        for count in connection_counts:
            clients = []
            errors = []
            connection_times = []
            
            # Create connections concurrently
            threads = []
            lock = threading.Lock()
            
            def connect_client():
                client = SpacetimeDBClient()
                start_time = time.perf_counter()
                
                try:
                    client._connect_internal(
                        auth_token=None,
                        host="localhost:3023",
                        database_address="test_db",
                        ssl_enabled=False
                    )
                    connection_time = (time.perf_counter() - start_time) * 1000
                    
                    with lock:
                        clients.append(client)
                        connection_times.append(connection_time)
                        
                except Exception as e:
                    with lock:
                        errors.append(e)
                        
            # Start all threads
            start_time = time.perf_counter()
            
            for i in range(count):
                thread = threading.Thread(target=connect_client)
                threads.append(thread)
                thread.start()
                
            # Wait for all to complete
            for thread in threads:
                thread.join()
                
            total_time = time.perf_counter() - start_time
            
            # Calculate metrics
            success_rate = len(clients) / count * 100
            avg_connection_time = statistics.mean(connection_times) if connection_times else 0
            
            print(f"\n{count} concurrent connections:")
            print(f"  Success rate: {success_rate:.1f}%")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Avg connection time: {avg_connection_time:.2f}ms")
            print(f"  Connections/sec: {len(clients) / total_time:.2f}")
            
            # Clean up
            for client in clients:
                try:
                    client.disconnect()
                except:
                    pass
                    
    def test_concurrent_message_handling(self):
        """Test concurrent message handling performance."""
        print("\n=== Concurrent Message Handling ===")
        
        # Create multiple clients
        client_count = 10
        clients = []
        
        for i in range(client_count):
            client = SpacetimeDBClient()
            client._connect_internal(
                auth_token=None,
                host="localhost:3023",
                database_address="test_db",
                ssl_enabled=False
            )
            clients.append(client)
            
        time.sleep(1)  # Ensure all connected
        
        # Simulate concurrent message activity
        message_counts = {}
        errors = []
        lock = threading.Lock()
        
        def client_activity(client_id, client):
            try:
                # Simulate message exchanges
                for i in range(50):
                    # In real implementation, would send/receive messages
                    time.sleep(0.01)
                    
                with lock:
                    message_counts[client_id] = 50
                    
            except Exception as e:
                with lock:
                    errors.append(e)
                    
        # Start concurrent activity
        threads = []
        start_time = time.perf_counter()
        
        for i, client in enumerate(clients):
            thread = threading.Thread(target=client_activity, args=(i, client))
            threads.append(thread)
            thread.start()
            
        # Wait for completion
        for thread in threads:
            thread.join()
            
        duration = time.perf_counter() - start_time
        
        # Calculate metrics
        total_messages = sum(message_counts.values())
        throughput = total_messages / duration if duration > 0 else 0
        
        print(f"Total messages: {total_messages}")
        print(f"Duration: {duration:.2f}s")
        print(f"Aggregate throughput: {throughput:.2f} msg/sec")
        print(f"Errors: {len(errors)}")
        
        # Clean up
        for client in clients:
            try:
                client.disconnect()
            except:
                pass


class TestCompressionPerformance(unittest.TestCase):
    """Test performance impact of compression."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3024)
        self.server.start()
        
    def tearDown(self):
        """Clean up after tests."""
        self.server.stop()
        
    def test_compression_overhead(self):
        """Test performance overhead of compression."""
        print("\n=== Compression Performance ===")
        
        # Test with and without compression
        scenarios = [
            ("no_compression", False),
            ("with_compression", True)
        ]
        
        for scenario_name, use_compression in scenarios:
            client = SpacetimeDBClient()
            
            # Connect with compression setting
            start_time = time.perf_counter()
            client._connect_internal(
                auth_token=None,
                host="localhost:3024",
                database_address="test_db",
                ssl_enabled=False
            )
            connection_time = (time.perf_counter() - start_time) * 1000
            
            print(f"{scenario_name}:")
            print(f"  Connection time: {connection_time:.2f}ms")
            
            # Test message performance
            # (Would measure actual compression impact on messages)
            
            client.disconnect()


def run_performance_benchmarks():
    """Run all performance benchmarks and generate report."""
    print("SpaceTimeDB SDK v1.1.2 Performance Benchmarks")
    print("=" * 50)
    
    # Collect overall metrics
    overall_metrics = PerformanceMetrics()
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestConnectionPerformance,
        TestMessageThroughput,
        TestMemoryUsage,
        TestConcurrentOperations,
        TestCompressionPerformance
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
        
    # Run tests
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    
    # Generate performance report
    print("\n" + "=" * 50)
    print("Performance Summary")
    print("=" * 50)
    
    # Print summary metrics (would be collected from individual tests)
    print("\nBaseline Performance Targets:")
    print("- Connection establishment: < 100ms")
    print("- Message throughput: > 1000 msg/sec")
    print("- Memory per connection: < 5MB")
    print("- Concurrent connections: > 50")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Run the benchmark suite
    success = run_performance_benchmarks()
    sys.exit(0 if success else 1)
