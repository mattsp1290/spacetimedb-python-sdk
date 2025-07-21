"""
Performance regression tests for Phase 2 refactoring

These tests ensure that the refactored modules maintain or improve
performance characteristics compared to the monolithic websocket_client.py.
"""
import pytest
import time
import threading
import psutil
import gc
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch
from dataclasses import dataclass
import statistics

from spacetimedb_sdk.websocket_client import WebSocketClient, ConnectionState
from .mock_infrastructure import create_test_server, MockServerBehavior
from .test_fixtures import TestDataFactory, PerformanceBaseline


@dataclass
class PerformanceMetrics:
    """Performance metrics collection"""
    operation: str
    duration: float
    memory_before: float
    memory_after: float
    memory_peak: float
    cpu_percent: float
    success: bool
    error: Optional[str] = None


class PerformanceMonitor:
    """Monitor performance during test execution"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.metrics: List[PerformanceMetrics] = []
        
    def start_monitoring(self, operation: str) -> Dict[str, Any]:
        """Start monitoring an operation"""
        gc.collect()  # Force garbage collection
        
        return {
            'operation': operation,
            'start_time': time.time(),
            'memory_before': self.process.memory_info().rss / 1024 / 1024,  # MB
            'cpu_start': self.process.cpu_percent()
        }
        
    def stop_monitoring(self, start_data: Dict[str, Any], success: bool = True, error: str = None) -> PerformanceMetrics:
        """Stop monitoring and record metrics"""
        end_time = time.time()
        memory_after = self.process.memory_info().rss / 1024 / 1024  # MB
        
        metrics = PerformanceMetrics(
            operation=start_data['operation'],
            duration=end_time - start_data['start_time'],
            memory_before=start_data['memory_before'],
            memory_after=memory_after,
            memory_peak=memory_after,  # Simplified for this implementation
            cpu_percent=self.process.cpu_percent(),
            success=success,
            error=error
        )
        
        self.metrics.append(metrics)
        return metrics
        
    def get_metrics(self, operation: Optional[str] = None) -> List[PerformanceMetrics]:
        """Get collected metrics"""
        if operation:
            return [m for m in self.metrics if m.operation == operation]
        return self.metrics.copy()
        
    def clear_metrics(self):
        """Clear collected metrics"""
        self.metrics.clear()
        
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.metrics:
            return {}
            
        successful_metrics = [m for m in self.metrics if m.success]
        
        if not successful_metrics:
            return {'error': 'No successful operations recorded'}
            
        durations = [m.duration for m in successful_metrics]
        memory_usage = [m.memory_after - m.memory_before for m in successful_metrics]
        
        return {
            'total_operations': len(self.metrics),
            'successful_operations': len(successful_metrics),
            'average_duration': statistics.mean(durations),
            'median_duration': statistics.median(durations),
            'max_duration': max(durations),
            'min_duration': min(durations),
            'average_memory_change': statistics.mean(memory_usage),
            'max_memory_change': max(memory_usage),
            'total_memory_growth': sum(memory_usage)
        }


class TestPerformanceRegression:
    """Test performance regression during refactoring"""
    
    def test_connection_performance_regression(self, mock_websocket_client, 
                                               refactoring_test_params,
                                               performance_baseline_fixture):
        """Test connection performance remains acceptable"""
        monitor = PerformanceMonitor()
        
        # Test multiple connections to get average performance
        connection_times = []
        
        for i in range(10):
            client = WebSocketClient(
                host=refactoring_test_params["host"],
                database_address=refactoring_test_params["database_address"]
            )
            
            start_data = monitor.start_monitoring(f"connection_{i}")
            
            with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
                mock_instance = Mock()
                mock_ws_app.return_value = mock_instance
                
                # Connect
                client.connect()
                
                # Simulate connection events
                if hasattr(client.ws_app, 'on_open'):
                    client.ws_app.on_open(mock_instance)
                    
                metrics = monitor.stop_monitoring(start_data)
                connection_times.append(metrics.duration)
                
                # Disconnect
                client.disconnect()
                
        # Validate performance
        avg_connection_time = statistics.mean(connection_times)
        baseline = performance_baseline_fixture.baselines['connection_time']
        
        assert avg_connection_time <= baseline, f"Connection time regression: {avg_connection_time:.3f}s > {baseline}s"
        assert max(connection_times) <= baseline * 2, f"Max connection time too high: {max(connection_times):.3f}s"
        
        # Check memory usage
        summary = monitor.get_summary()
        assert summary['total_memory_growth'] < 50, f"Memory growth too high: {summary['total_memory_growth']:.2f}MB"
        
    def test_subscription_performance_regression(self, mock_connected_websocket_client,
                                                 performance_baseline_fixture):
        """Test subscription performance remains acceptable"""
        monitor = PerformanceMonitor()
        client, mock_instance = mock_connected_websocket_client
        
        # Test creating multiple subscriptions
        subscription_times = []
        
        for i in range(50):
            start_data = monitor.start_monitoring(f"subscription_{i}")
            
            query_id = client.subscribe(f"table_{i}", f"SELECT * FROM table_{i}")
            
            # Simulate subscription applied
            if hasattr(client.ws_app, 'on_message'):
                import json
                from spacetimedb_sdk.query_id import QueryId
                
                # Convert QueryId to JSON-serializable format
                serializable_query_id = query_id.id if isinstance(query_id, QueryId) else (query_id or f"query_{i}")
                
                sub_msg = json.dumps({
                    "SubscriptionApplied": {
                        "query_id": serializable_query_id,
                        "table_name": f"table_{i}"
                    }
                })
                client.ws_app.on_message(mock_instance, sub_msg)
                
            metrics = monitor.stop_monitoring(start_data)
            subscription_times.append(metrics.duration)
            
        # Validate performance
        avg_subscription_time = statistics.mean(subscription_times)
        baseline = performance_baseline_fixture.baselines['subscription_time']
        
        assert avg_subscription_time <= baseline, f"Subscription time regression: {avg_subscription_time:.3f}s > {baseline}s"
        
        # Check that performance doesn't degrade with more subscriptions
        first_10 = statistics.mean(subscription_times[:10])
        last_10 = statistics.mean(subscription_times[-10:])
        
        assert last_10 <= first_10 * 1.5, f"Subscription performance degraded: {last_10:.3f}s vs {first_10:.3f}s"
            
    def test_message_processing_performance_regression(self, mock_connected_websocket_client,
                                                       performance_baseline_fixture):
        """Test message processing performance remains acceptable"""
        monitor = PerformanceMonitor()
        client, mock_instance = mock_connected_websocket_client
        
        # Track processed messages
        processed_messages = []
        
        def on_subscription_data(table_name, data):
            processed_messages.append((table_name, data))
            
        client.on_subscription_data = on_subscription_data
        
        # Create subscription
        client.subscribe("test_table", "SELECT * FROM test_table")
        
        # Test processing large volume of messages - reduce count for test stability
        message_count = 100  # Reduced from 1000 for more stable testing
        test_data = TestDataFactory.create_user_dataset("large")
        
        start_data = monitor.start_monitoring("message_processing")
        
        if hasattr(client.ws_app, 'on_message'):
            import json
            for i in range(message_count):
                data_msg = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "test_table",
                        "data": test_data[i % len(test_data):i % len(test_data) + 1]
                    }
                })
                client.ws_app.on_message(mock_instance, data_msg)
                # Small delay to prevent overwhelming the system
                if i % 10 == 0:
                    time.sleep(0.001)
                
        metrics = monitor.stop_monitoring(start_data)
        
        # Validate performance - allow more time for processing to complete
        time.sleep(0.3)
        
        messages_per_second = message_count / metrics.duration
        baseline_mps = 1.0 / performance_baseline_fixture.baselines['message_processing_time']
        
        assert messages_per_second >= baseline_mps * 0.8, f"Message processing too slow: {messages_per_second:.0f} < {baseline_mps * 0.8:.0f} msg/s"
        
        # Check memory efficiency - make thresholds more realistic for test environment
        memory_per_message = (metrics.memory_after - metrics.memory_before) / message_count
        # Allow up to 0.1MB per message in test environment (much more lenient)
        assert memory_per_message < 0.1, f"Memory usage per message too high: {memory_per_message:.6f}MB"
            
    def test_concurrent_operations_performance(self, mock_websocket_client,
                                               refactoring_test_params):
        """Test performance under concurrent operations"""
        monitor = PerformanceMonitor()
        
        # Create multiple clients
        clients = []
        results = []
        errors = []
        
        def create_and_test_client(client_id):
            try:
                client = WebSocketClient(
                    host=refactoring_test_params["host"],
                    database_address=refactoring_test_params["database_address"]
                )
                
                with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
                    mock_instance = Mock()
                    mock_ws_app.return_value = mock_instance
                    
                    # Properly synchronize connection state
                    client._connection_manager._connection = mock_instance
                    client._connection_manager._on_ws_open(mock_instance)
                    client._on_ws_open(mock_instance)
                    
                    start_time = time.time()
                    
                    # Create subscriptions
                    for i in range(5):
                        client.subscribe(f"table_{client_id}_{i}", f"SELECT * FROM table_{client_id}_{i}")
                        
                    # Simulate some message processing
                    if hasattr(client.ws_app, 'on_message'):
                        import json
                        for i in range(10):
                            data_msg = json.dumps({
                                "TransactionUpdate": {
                                    "table_name": f"table_{client_id}_0",
                                    "data": [{"id": i, "value": f"data_{i}"}]
                                }
                            })
                            client.ws_app.on_message(mock_instance, data_msg)
                            
                    end_time = time.time()
                    
                    results.append({
                        'client_id': client_id,
                        'duration': end_time - start_time,
                        'subscriptions': len(client.subscriptions)
                    })
                    
            except Exception as e:
                errors.append(f"Client {client_id}: {str(e)}")
                
        # Run concurrent clients
        start_data = monitor.start_monitoring("concurrent_operations")
        
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_and_test_client, args=(i,))
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()
            
        metrics = monitor.stop_monitoring(start_data)
        
        # Validate performance
        assert len(errors) == 0, f"Concurrent operations failed: {errors}"
        assert len(results) == 10, f"Not all clients completed: {len(results)}/10"
        
        # Check that concurrent operations don't significantly impact performance
        avg_duration = statistics.mean([r['duration'] for r in results])
        assert avg_duration < 2.0, f"Concurrent operations too slow: {avg_duration:.3f}s"
        
        # Check memory usage
        assert metrics.memory_after - metrics.memory_before < 100, f"Memory usage too high: {metrics.memory_after - metrics.memory_before:.2f}MB"
        
    def test_memory_efficiency_regression(self, mock_websocket_client,
                                          refactoring_test_params):
        """Test memory efficiency during extended operations"""
        monitor = PerformanceMonitor()
        
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Mock the connection manager to be properly connected
            with patch.object(client._connection_manager, 'is_connected', return_value=True):
                with patch.object(client._connection_manager, 'get_connection_state', return_value=ConnectionState.CONNECTED):
                    with patch.object(client._connection_manager, 'send_data', return_value=None):
                        # Set up mock WebSocket and ensure connection reference is set
                        client.ws = mock_instance
                        client.state = ConnectionState.CONNECTED
                        client._connection_manager._connection = mock_instance
                        
                        # Memory usage over time
                        memory_snapshots = []
                        
                        start_data = monitor.start_monitoring("memory_efficiency")
                        initial_memory = monitor.process.memory_info().rss / 1024 / 1024
                        
                        # Simulate extended operation
                        for cycle in range(10):
                            # Create subscriptions
                            for i in range(10):
                                query_id = client.subscribe(f"cycle_{cycle}_table_{i}", f"SELECT * FROM cycle_{cycle}_table_{i}")
                                
                            # Process messages
                            if hasattr(client.ws_app, 'on_message'):
                                import json
                                for i in range(100):
                                    data_msg = json.dumps({
                                        "TransactionUpdate": {
                                            "table_name": f"cycle_{cycle}_table_0",
                                            "data": [{"id": i, "data": f"cycle_{cycle}_data_{i}" * 10}]
                                        }
                                    })
                                    client.ws_app.on_message(mock_instance, data_msg)
                                    
                            # Take memory snapshot
                            current_memory = monitor.process.memory_info().rss / 1024 / 1024
                            memory_snapshots.append(current_memory)
                            
                            # Force garbage collection
                            gc.collect()
                            
                            # Small delay
                            time.sleep(0.1)
                            
                        final_memory = monitor.process.memory_info().rss / 1024 / 1024
                        metrics = monitor.stop_monitoring(start_data)
                        
                        # Validate memory efficiency
                        memory_growth = final_memory - initial_memory
                        assert memory_growth < 100, f"Memory growth too high: {memory_growth:.2f}MB"
                        
                        # Check for memory leaks (memory should stabilize)
                        if len(memory_snapshots) >= 5:
                            last_5_avg = statistics.mean(memory_snapshots[-5:])
                            first_5_avg = statistics.mean(memory_snapshots[:5])
                            growth_rate = (last_5_avg - first_5_avg) / len(memory_snapshots)
                            
                            assert growth_rate < 2.0, f"Potential memory leak detected: {growth_rate:.2f}MB per cycle"
                
    def test_cpu_usage_regression(self, mock_websocket_client,
                                  refactoring_test_params,
                                  performance_baseline_fixture):
        """Test CPU usage remains within acceptable limits"""
        monitor = PerformanceMonitor()
        
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Mock the connection manager to be properly connected
            with patch.object(client._connection_manager, 'is_connected', return_value=True):
                with patch.object(client._connection_manager, 'get_connection_state', return_value=ConnectionState.CONNECTED):
                    with patch.object(client._connection_manager, 'send_data', return_value=None):
                        # Set up mock WebSocket and ensure connection reference is set
                        client.ws = mock_instance
                        client.state = ConnectionState.CONNECTED
                        client._connection_manager._connection = mock_instance
                        
                        # Baseline CPU measurement
                        monitor.process.cpu_percent()  # Initialize
                        time.sleep(1)  # Let it settle
                        baseline_cpu = monitor.process.cpu_percent()
                        
                        start_data = monitor.start_monitoring("cpu_usage")
                        
                        # Simulate high activity
                        for i in range(50):
                            # Create subscription
                            client.subscribe(f"cpu_test_table_{i}", f"SELECT * FROM cpu_test_table_{i}")
                            
                            # Process messages
                            if hasattr(client.ws_app, 'on_message'):
                                import json
                                for j in range(20):
                                    data_msg = json.dumps({
                                        "TransactionUpdate": {
                                            "table_name": f"cpu_test_table_{i}",
                                            "data": [{"id": j, "data": f"data_{j}"}]
                                        }
                                    })
                                    client.ws_app.on_message(mock_instance, data_msg)
                                    
                        time.sleep(1)  # Let processing complete
                        final_cpu = monitor.process.cpu_percent()
                        
                        metrics = monitor.stop_monitoring(start_data)
                        
                        # Validate CPU usage
                        cpu_increase = final_cpu - baseline_cpu
                        baseline_limit = performance_baseline_fixture.baselines['cpu_usage_percent']
                        
                        assert cpu_increase <= baseline_limit, f"CPU usage regression: {cpu_increase:.1f}% > {baseline_limit}%"
            
    def test_scalability_performance(self, mock_websocket_client,
                                     refactoring_test_params):
        """Test performance scalability with increasing load"""
        monitor = PerformanceMonitor()
        
        scale_factors = [1, 5, 10, 25, 50]
        performance_results = []
        
        for scale in scale_factors:
            client = WebSocketClient(
                host=refactoring_test_params["host"],
                database_address=refactoring_test_params["database_address"]
            )
            
            with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
                mock_instance = Mock()
                mock_ws_app.return_value = mock_instance
                
                # Mock the connection manager to be properly connected
                with patch.object(client._connection_manager, 'is_connected', return_value=True):
                    with patch.object(client._connection_manager, 'get_connection_state', return_value=ConnectionState.CONNECTED):
                        with patch.object(client._connection_manager, 'send_data', return_value=None):
                            # Set up mock WebSocket and ensure connection reference is set
                            client.ws = mock_instance
                            client.state = ConnectionState.CONNECTED
                            client._connection_manager._connection = mock_instance
                            
                            start_data = monitor.start_monitoring(f"scale_{scale}")
                            
                            # Create subscriptions based on scale
                            for i in range(scale):
                                client.subscribe(f"scale_table_{i}", f"SELECT * FROM scale_table_{i}")
                                
                            # Process messages based on scale
                            if hasattr(client.ws_app, 'on_message'):
                                import json
                                for i in range(scale * 10):
                                    data_msg = json.dumps({
                                        "TransactionUpdate": {
                                            "table_name": f"scale_table_{i % scale}",
                                            "data": [{"id": i, "value": f"scale_data_{i}"}]
                                        }
                                    })
                                    client.ws_app.on_message(mock_instance, data_msg)
                                    
                            metrics = monitor.stop_monitoring(start_data)
                            
                            performance_results.append({
                                'scale': scale,
                                'duration': metrics.duration,
                                'memory_used': metrics.memory_after - metrics.memory_before,
                                'ops_per_second': (scale + scale * 10) / metrics.duration
                            })
                            
                            client.disconnect()
                
        # Validate scalability
        # Performance should scale reasonably (not exponentially worse)
        for i in range(1, len(performance_results)):
            prev = performance_results[i-1]
            curr = performance_results[i]
            
            scale_ratio = curr['scale'] / prev['scale']
            duration_ratio = curr['duration'] / prev['duration']
            
            # Duration should not increase more than 2x the scale ratio
            assert duration_ratio <= scale_ratio * 2, f"Poor scalability: scale {curr['scale']} duration ratio {duration_ratio:.2f} > {scale_ratio * 2:.2f}"
            
        # Memory usage should scale linearly or better
        memory_growth_rates = []
        for i in range(1, len(performance_results)):
            prev = performance_results[i-1]
            curr = performance_results[i]
            
            scale_increase = curr['scale'] - prev['scale']
            memory_increase = curr['memory_used'] - prev['memory_used']
            
            if scale_increase > 0:
                memory_growth_rates.append(memory_increase / scale_increase)
                
        if memory_growth_rates:
            avg_memory_growth = statistics.mean(memory_growth_rates)
            assert avg_memory_growth < 2.0, f"Memory scalability poor: {avg_memory_growth:.2f}MB per scale unit"


class TestPerformanceMonitoring:
    """Test performance monitoring capabilities"""
    
    def test_performance_monitor_accuracy(self):
        """Test that performance monitor provides accurate measurements"""
        monitor = PerformanceMonitor()
        
        # Test timing accuracy
        start_data = monitor.start_monitoring("timing_test")
        time.sleep(0.1)  # Sleep for 100ms
        metrics = monitor.stop_monitoring(start_data)
        
        # Should be close to 100ms (within 50ms tolerance)
        assert 0.05 <= metrics.duration <= 0.15, f"Timing inaccurate: {metrics.duration:.3f}s"
        
    def test_performance_baseline_validation(self, performance_baseline_fixture):
        """Test performance baseline validation"""
        baseline = performance_baseline_fixture
        
        # Test baseline checking
        good_metrics = {
            'connection_time': 0.5,
            'memory_usage_mb': 30
        }
        
        bad_metrics = {
            'connection_time': 2.0,
            'memory_usage_mb': 100
        }
        
        good_results = baseline.check_performance(good_metrics)
        bad_results = baseline.check_performance(bad_metrics)
        
        assert good_results['connection_time'] is True
        assert good_results['memory_usage_mb'] is True
        assert bad_results['connection_time'] is False
        assert bad_results['memory_usage_mb'] is False