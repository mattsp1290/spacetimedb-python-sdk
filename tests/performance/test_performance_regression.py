"""
Performance regression tests.

Tests to detect performance degradation in critical operations including
connection setup, event dispatch, and memory usage under load.
"""
import pytest
import time
import gc
import asyncio
import threading
import sys
import psutil
import statistics
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Callable

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.events.event_system import EventSystem
from spacetimedb_sdk.websocket_client import WebSocketClient
from spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler


@dataclass
class PerformanceMetric:
    """Container for performance metrics."""
    operation: str
    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    std_dev: float
    samples: int
    
    def is_regression(self, baseline_avg: float, tolerance: float = 0.20) -> bool:
        """Check if this metric represents a regression from baseline."""
        return self.avg_time > baseline_avg * (1 + tolerance)


class TestPerformanceRegression:
    """Test for performance regressions in critical operations."""
    
    # Baseline performance metrics (in seconds)
    BASELINES = {
        "connection_setup": 0.100,  # 100ms
        "event_dispatch": 0.001,    # 1ms
        "message_parse": 0.005,     # 5ms
        "auth_token_refresh": 0.050, # 50ms
        "subscription_setup": 0.010, # 10ms
    }
    
    # Tolerance for performance regression (20% slower is considered regression)
    REGRESSION_TOLERANCE = 0.20
    
    @pytest.fixture
    def process(self):
        """Get current process for memory monitoring."""
        return psutil.Process()
    
    @pytest.fixture
    def event_system(self):
        """Provide event system for testing."""
        return EventSystem()
    
    def measure_operation(self, operation: Callable, iterations: int = 100) -> PerformanceMetric:
        """Measure performance of an operation over multiple iterations."""
        times = []
        
        # Warm up
        for _ in range(10):
            operation()
        
        # Measure
        for _ in range(iterations):
            start = time.perf_counter()
            operation()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        return PerformanceMetric(
            operation=operation.__name__,
            min_time=min(times),
            max_time=max(times),
            avg_time=statistics.mean(times),
            median_time=statistics.median(times),
            std_dev=statistics.stdev(times) if len(times) > 1 else 0,
            samples=len(times)
        )
    
    def test_connection_setup_performance_regression(self):
        """Test connection setup performance hasn't regressed."""
        setup_times = []
        
        def setup_connection():
            with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws:
                # Mock instant connection
                mock_ws.return_value.run_forever = Mock()
                
                start = time.perf_counter()
                client = SpacetimeDBClient()
                client.connect_instance(
                    host="localhost:3000",
                    database_address="test_db",
                    auth_token=None,
                    ssl_enabled=False
                )
                # Simulate connection lifecycle
                if hasattr(client, '_on_open'):
                    client._on_open(mock_ws)
                elapsed = time.perf_counter() - start
                setup_times.append(elapsed)
                
                # Cleanup
                if hasattr(client, 'close'):
                    client.close()
        
        # Measure connection setup
        metric = self.measure_operation(setup_connection, iterations=50)
        
        # Check for regression
        baseline = self.BASELINES["connection_setup"]
        assert not metric.is_regression(baseline, self.REGRESSION_TOLERANCE), \
            f"Connection setup regression: {metric.avg_time:.3f}s (baseline: {baseline:.3f}s)"
        
        # Log performance
        print(f"\nConnection Setup Performance:")
        print(f"  Average: {metric.avg_time*1000:.2f}ms")
        print(f"  Median: {metric.median_time*1000:.2f}ms")
        print(f"  Min: {metric.min_time*1000:.2f}ms")
        print(f"  Max: {metric.max_time*1000:.2f}ms")
    
    def test_event_dispatch_performance_regression(self, event_system):
        """Test event dispatch performance hasn't regressed."""
        # Set up subscribers
        call_count = 0
        
        def handler(data):
            nonlocal call_count
            call_count += 1
        
        # Subscribe multiple handlers
        for i in range(10):
            event_system.subscribe(f"test_event_{i}", handler)
        
        def dispatch_events():
            for i in range(10):
                event_system.emit(f"test_event_{i}", {"index": i})
        
        # Measure event dispatch
        metric = self.measure_operation(dispatch_events, iterations=100)
        
        # Check for regression
        baseline = self.BASELINES["event_dispatch"]
        assert not metric.is_regression(baseline, self.REGRESSION_TOLERANCE), \
            f"Event dispatch regression: {metric.avg_time:.3f}s (baseline: {baseline:.3f}s)"
        
        print(f"\nEvent Dispatch Performance:")
        print(f"  Average: {metric.avg_time*1000:.2f}ms per 10 events")
        print(f"  Throughput: {10/metric.avg_time:.0f} events/second")
    
    def test_memory_usage_under_sustained_load(self, process, event_system):
        """Test memory usage doesn't grow excessively under sustained load."""
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_samples = [initial_memory]
        
        # Create load
        def sustained_load():
            clients = []
            
            # Create multiple clients
            for i in range(5):
                with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'):
                    client = SpacetimeDBClient()
                    client.connect_instance(
                        host="localhost:3000",
                        database_address=f"test_db_{i}",
                        auth_token=None,
                        ssl_enabled=False
                    )
                    clients.append(client)
            
            # Generate events
            for _ in range(1000):
                event_system.emit("load_test", {"data": "x" * 1000})
            
            # Cleanup
            for client in clients:
                if hasattr(client, 'close'):
                    client.close()
            
            # Force garbage collection
            gc.collect()
        
        # Run sustained load test
        for i in range(10):
            sustained_load()
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)
            time.sleep(0.1)
        
        # Analyze memory usage
        memory_growth = max(memory_samples) - initial_memory
        avg_memory = statistics.mean(memory_samples)
        
        # Check for memory leaks (should not grow more than 50MB)
        assert memory_growth < 50, \
            f"Excessive memory growth: {memory_growth:.1f}MB (initial: {initial_memory:.1f}MB)"
        
        print(f"\nMemory Usage Under Load:")
        print(f"  Initial: {initial_memory:.1f}MB")
        print(f"  Peak: {max(memory_samples):.1f}MB")
        print(f"  Average: {avg_memory:.1f}MB")
        print(f"  Growth: {memory_growth:.1f}MB")
    
    def test_message_parsing_performance(self):
        """Test message parsing performance."""
        import json
        
        # Create test messages of varying sizes
        small_msg = json.dumps({"type": "Test", "data": {"id": 1}})
        medium_msg = json.dumps({"type": "TableUpdate", "data": {"rows": [{"id": i} for i in range(100)]}})
        large_msg = json.dumps({"type": "BulkUpdate", "data": {"items": [{"id": i, "data": "x" * 100} for i in range(1000)]}})
        
        messages = [small_msg, medium_msg, large_msg]
        
        def parse_messages():
            for msg in messages:
                parsed = json.loads(msg)
                _ = parsed.get("type")
                _ = parsed.get("data")
        
        # Measure parsing performance
        metric = self.measure_operation(parse_messages, iterations=100)
        
        # Check for regression
        baseline = self.BASELINES["message_parse"]
        assert not metric.is_regression(baseline, self.REGRESSION_TOLERANCE), \
            f"Message parsing regression: {metric.avg_time:.3f}s (baseline: {baseline:.3f}s)"
        
        print(f"\nMessage Parsing Performance:")
        print(f"  Average: {metric.avg_time*1000:.2f}ms per batch")
        print(f"  Throughput: {3/metric.avg_time:.0f} messages/second")
    
    def test_concurrent_operation_performance(self, event_system):
        """Test performance under concurrent operations."""
        results = []
        
        def concurrent_operation(op_id):
            start = time.perf_counter()
            
            # Simulate mixed operations
            with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'):
                client = SpacetimeDBClient()
                client.connect_instance(
                    host="localhost:3000",
                    database_address=f"test_db_{op_id}",
                    auth_token=None,
                    ssl_enabled=False
                )
                
                # Emit events
                for i in range(10):
                    event_system.emit(f"concurrent_{op_id}", {"index": i})
                
                # Cleanup
                if hasattr(client, 'close'):
                    client.close()
            
            elapsed = time.perf_counter() - start
            return elapsed
        
        # Run concurrent operations
        start_time = time.perf_counter()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(20)]
            results = [f.result() for f in as_completed(futures)]
        total_time = time.perf_counter() - start_time
        
        # Analyze results
        avg_time = statistics.mean(results)
        max_time = max(results)
        
        # Performance should scale reasonably with concurrency
        assert total_time < 5.0, f"Concurrent operations too slow: {total_time:.2f}s"
        assert max_time < 1.0, f"Individual operation too slow under load: {max_time:.2f}s"
        
        print(f"\nConcurrent Operations Performance:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Average per operation: {avg_time*1000:.2f}ms")
        print(f"  Max operation time: {max_time*1000:.2f}ms")
        print(f"  Throughput: {20/total_time:.1f} ops/second")
    
    def test_authentication_performance(self):
        """Test authentication operation performance."""
        auth_handler = AuthenticationHandler()
        
        def auth_operation():
            with patch.object(auth_handler, 'authenticate') as mock_auth:
                mock_auth.return_value = {
                    "token": "test_token_12345",
                    "expires_at": time.time() + 3600
                }
                
                # Simulate auth flow
                result = auth_handler.authenticate("user", "pass")
                # Simulate token validation
                if hasattr(auth_handler, 'validate_token'):
                    auth_handler.validate_token(result.get("token"))
        
        # Measure authentication performance
        metric = self.measure_operation(auth_operation, iterations=50)
        
        # Check for regression
        baseline = self.BASELINES["auth_token_refresh"]
        assert not metric.is_regression(baseline, self.REGRESSION_TOLERANCE), \
            f"Authentication regression: {metric.avg_time:.3f}s (baseline: {baseline:.3f}s)"
        
        print(f"\nAuthentication Performance:")
        print(f"  Average: {metric.avg_time*1000:.2f}ms")
        print(f"  Min: {metric.min_time*1000:.2f}ms")
        print(f"  Max: {metric.max_time*1000:.2f}ms")
    
    def test_subscription_setup_performance(self, event_system):
        """Test subscription setup performance."""
        handlers = []
        
        # Create handlers
        for i in range(100):
            handlers.append(lambda data, i=i: None)
        
        def setup_subscriptions():
            for i, handler in enumerate(handlers):
                event_system.subscribe(f"table_{i}", handler)
        
        def teardown_subscriptions():
            for i in range(len(handlers)):
                event_system.unsubscribe(f"table_{i}", handlers[i])
        
        # Measure subscription setup
        metric = self.measure_operation(setup_subscriptions, iterations=10)
        
        # Clean up after each iteration
        for _ in range(10):
            teardown_subscriptions()
        
        # Check for regression
        baseline = self.BASELINES["subscription_setup"]
        assert not metric.is_regression(baseline * 100, self.REGRESSION_TOLERANCE), \
            f"Subscription setup regression: {metric.avg_time:.3f}s (baseline: {baseline * 100:.3f}s)"
        
        print(f"\nSubscription Setup Performance (100 subscriptions):")
        print(f"  Average: {metric.avg_time*1000:.2f}ms")
        print(f"  Per subscription: {metric.avg_time*10:.2f}ms")


@pytest.mark.performance
class TestScalabilityLimits:
    """Test scalability limits and performance boundaries."""
    
    def test_max_concurrent_connections(self):
        """Test maximum concurrent connections without degradation."""
        max_clients = 50  # Reasonable limit for testing
        clients = []
        connection_times = []
        
        try:
            for i in range(max_clients):
                start = time.perf_counter()
                
                with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'):
                    client = SpacetimeDBClient()
                    client.connect_instance(
                        host="localhost:3000",
                        database_address=f"test_db_{i}",
                        auth_token=None,
                        ssl_enabled=False
                    )
                    clients.append(client)
                
                elapsed = time.perf_counter() - start
                connection_times.append(elapsed)
                
                # Check if performance is degrading
                if i > 10 and elapsed > connection_times[0] * 5:
                    print(f"Performance degradation at {i} connections")
                    break
        
        finally:
            # Cleanup
            for client in clients:
                try:
                    if hasattr(client, 'close'):
                        client.close()
                except:
                    pass
        
        # Analyze results
        avg_time = statistics.mean(connection_times)
        max_time = max(connection_times)
        
        print(f"\nConcurrent Connections Scalability:")
        print(f"  Connections tested: {len(clients)}")
        print(f"  Average setup time: {avg_time*1000:.2f}ms")
        print(f"  Max setup time: {max_time*1000:.2f}ms")
        
        # Should handle at least 50 concurrent connections
        assert len(clients) >= 50, f"Could only handle {len(clients)} concurrent connections"
    
    def test_event_system_scalability(self, event_system):
        """Test event system scalability with many subscribers."""
        subscriber_counts = [10, 100, 1000]
        performance_results = []
        
        for count in subscriber_counts:
            # Set up subscribers
            handlers = []
            for i in range(count):
                handler = lambda data, i=i: None
                handlers.append(handler)
                event_system.subscribe("scalability_test", handler)
            
            # Measure event dispatch time
            start = time.perf_counter()
            for _ in range(100):
                event_system.emit("scalability_test", {"test": "data"})
            elapsed = time.perf_counter() - start
            
            performance_results.append({
                "subscribers": count,
                "total_time": elapsed,
                "time_per_emit": elapsed / 100,
                "time_per_notification": elapsed / (100 * count)
            })
            
            # Cleanup
            for handler in handlers:
                event_system.unsubscribe("scalability_test", handler)
        
        # Analyze scalability
        print(f"\nEvent System Scalability:")
        for result in performance_results:
            print(f"  {result['subscribers']} subscribers:")
            print(f"    Total time: {result['total_time']*1000:.2f}ms")
            print(f"    Per emit: {result['time_per_emit']*1000:.2f}ms")
            print(f"    Per notification: {result['time_per_notification']*1000000:.2f}µs")
        
        # Performance should scale reasonably (not exponentially)
        # Time should increase less than linearly with subscriber count
        time_ratio = performance_results[-1]["time_per_emit"] / performance_results[0]["time_per_emit"]
        subscriber_ratio = performance_results[-1]["subscribers"] / performance_results[0]["subscribers"]
        
        assert time_ratio < subscriber_ratio * 0.5, \
            f"Event dispatch doesn't scale well: {time_ratio:.1f}x time for {subscriber_ratio}x subscribers"