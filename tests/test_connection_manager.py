"""
Unit tests for ConnectionManager
"""

import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

from spacetimedb_sdk.connection.connection_manager import (
    ConnectionManager,
    ConnectionConfig,
    ConnectionState,
    ConnectionMetrics,
    DefaultWebSocketFactory,
    NullEventManager
)
from spacetimedb_sdk.exceptions import ValidationError, WebSocketHandshakeError, SpacetimeDBConnectionError


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.closed = False
        self.sent_data = []
        self.on_open = None
        self.on_close = None
        self.on_error = None
        self.on_message = None
    
    def send(self, data, opcode=None):
        """Mock send method."""
        if self.closed:
            raise RuntimeError("Connection closed")
        self.sent_data.append((data, opcode))
    
    def close(self):
        """Mock close method."""
        self.closed = True
        if self.on_close:
            self.on_close(self, 1000, "Normal closure")
    
    def run_forever(self):
        """Mock run_forever method."""
        if self.on_open:
            self.on_open(self)


class MockWebSocketFactory:
    """Mock WebSocket factory for testing."""
    
    def __init__(self):
        self.created_websockets = []
        self.should_fail = False
        self.failure_exception = Exception("Connection failed")
    
    def create_websocket(self, url, on_open=None, on_message=None, 
                        on_error=None, on_close=None, headers=None, 
                        subprotocols=None):
        """Create a mock WebSocket."""
        if self.should_fail:
            raise self.failure_exception
        
        ws = MockWebSocket()
        ws.on_open = on_open
        ws.on_message = on_message
        ws.on_error = on_error
        ws.on_close = on_close
        self.created_websockets.append(ws)
        return ws


class MockEventManager:
    """Mock event manager for testing."""
    
    def __init__(self):
        self.events = []
    
    def emit_connection_opened(self):
        """Record connection opened event."""
        self.events.append(("connection_opened",))
    
    def emit_connection_closed(self, reason):
        """Record connection closed event."""
        self.events.append(("connection_closed", reason))
    
    def emit_connection_error(self, error):
        """Record connection error event."""
        self.events.append(("connection_error", error))


class TestConnectionManager(unittest.TestCase):
    """Test cases for ConnectionManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_factory = MockWebSocketFactory()
        self.mock_events = MockEventManager()
        self.connection_manager = ConnectionManager(
            websocket_factory=self.mock_factory,
            event_manager=self.mock_events
        )
        
        self.test_config = ConnectionConfig(
            host="localhost:8080",
            database_address="testdb",
            auth_token="test_token",
            ssl_enabled=False,
            connection_timeout=5.0,
            auto_reconnect=False  # Disable for testing
        )
    
    def test_initial_state(self):
        """Test initial connection manager state."""
        self.assertEqual(self.connection_manager.get_connection_state(), ConnectionState.DISCONNECTED)
        self.assertFalse(self.connection_manager.is_connected())
    
    def test_successful_connection(self):
        """Test successful connection establishment."""
        # Start connection
        self.connection_manager.connect(self.test_config)
        
        # Give a moment for connection thread to start
        time.sleep(0.1)
        
        # Verify WebSocket was created
        self.assertEqual(len(self.mock_factory.created_websockets), 1)
        
        # Simulate successful connection
        ws = self.mock_factory.created_websockets[0]
        ws.run_forever()
        
        # Give a moment for callbacks to execute
        time.sleep(0.1)
        
        # Verify state
        self.assertTrue(self.connection_manager.is_connected())
        self.assertEqual(self.connection_manager.get_connection_state(), ConnectionState.CONNECTED)
        
        # Verify events
        self.assertIn(("connection_opened",), self.mock_events.events)
    
    def test_connection_failure(self):
        """Test connection failure handling."""
        # Configure factory to fail
        self.mock_factory.should_fail = True
        self.mock_factory.failure_exception = WebSocketHandshakeError(
            status_code=500,
            status_message="Connection failed",
            url="wss://testhost/database/test"
        )
        
        # Attempt connection
        with self.assertRaises(WebSocketHandshakeError):
            self.connection_manager.connect(self.test_config)
        
        # Verify state remains disconnected
        self.assertFalse(self.connection_manager.is_connected())
        self.assertEqual(self.connection_manager.get_connection_state(), ConnectionState.DISCONNECTED)
    
    def test_invalid_config(self):
        """Test validation of invalid configuration."""
        invalid_config = ConnectionConfig(
            host="",  # Invalid empty host
            database_address="testdb"
        )
        
        with self.assertRaises(ValueError):
            self.connection_manager.connect(invalid_config)
    
    def test_disconnect(self):
        """Test disconnection."""
        # First connect
        self.connection_manager.connect(self.test_config)
        time.sleep(0.1)
        
        ws = self.mock_factory.created_websockets[0]
        ws.run_forever()
        time.sleep(0.1)
        
        # Verify connected
        self.assertTrue(self.connection_manager.is_connected())
        
        # Disconnect
        self.connection_manager.disconnect()
        time.sleep(0.1)
        
        # Verify disconnected
        self.assertFalse(self.connection_manager.is_connected())
        self.assertEqual(self.connection_manager.get_connection_state(), ConnectionState.CLOSED)
    
    def test_send_data_when_connected(self):
        """Test sending data when connected."""
        # Connect
        self.connection_manager.connect(self.test_config)
        time.sleep(0.1)
        
        ws = self.mock_factory.created_websockets[0]
        ws.run_forever()
        time.sleep(0.1)
        
        # Send data
        test_data = "test message"
        self.connection_manager.send_data(test_data)
        
        # Verify data was sent
        self.assertEqual(len(ws.sent_data), 1)
        self.assertEqual(ws.sent_data[0][0], test_data)
    
    def test_send_data_when_disconnected(self):
        """Test sending data when disconnected raises error."""
        with self.assertRaises(RuntimeError):
            self.connection_manager.send_data("test")
    
    def test_connection_metrics(self):
        """Test connection metrics tracking."""
        # Get initial metrics
        metrics = self.connection_manager.get_connection_metrics()
        self.assertEqual(metrics.connection_attempts, 0)
        self.assertEqual(metrics.successful_connections, 0)
        
        # Connect
        self.connection_manager.connect(self.test_config)
        time.sleep(0.1)
        
        # Verify attempt and success recorded (connection completes immediately in mock)
        metrics = self.connection_manager.get_connection_metrics()
        self.assertEqual(metrics.connection_attempts, 1)
        self.assertEqual(metrics.successful_connections, 1)
        self.assertIsNotNone(metrics.last_connection_time)
    
    def test_connection_info(self):
        """Test connection info reporting."""
        info = self.connection_manager.get_connection_info()
        
        # Verify structure
        self.assertIn("state", info)
        self.assertIn("config", info)
        self.assertIn("metrics", info)
        self.assertIn("reconnection", info)
        
        # Verify initial values
        self.assertEqual(info["state"], "disconnected")
        self.assertIsNone(info["config"])
    
    def test_callbacks(self):
        """Test callback registration and execution."""
        callback_events = []
        
        def on_open(ws):
            callback_events.append("open")
        
        def on_close(ws, code, msg):
            callback_events.append("close")
        
        def on_error(ws, error):
            callback_events.append("error")
        
        # Set callbacks
        self.connection_manager.set_callbacks(
            on_open=on_open,
            on_close=on_close,
            on_error=on_error
        )
        
        # Connect and simulate events
        self.connection_manager.connect(self.test_config)
        time.sleep(0.1)
        
        ws = self.mock_factory.created_websockets[0]
        ws.run_forever()  # Triggers on_open
        time.sleep(0.1)
        
        ws.close()  # Triggers on_close
        time.sleep(0.1)
        
        # Verify callbacks were called
        self.assertIn("open", callback_events)
        self.assertIn("close", callback_events)
    
    @patch('urllib.parse.urlparse')
    def test_url_validation(self, mock_urlparse):
        """Test URL validation during connection."""
        # Mock invalid URL parsing
        mock_urlparse.return_value.hostname = None
        
        with self.assertRaises(SpacetimeDBConnectionError):
            self.connection_manager.connect(self.test_config)
    
    def test_thread_safety(self):
        """Test thread safety of connection operations."""
        results = []
        
        def connect_worker():
            try:
                self.connection_manager.connect(self.test_config)
                results.append("connect_success")
            except Exception as e:
                results.append(f"connect_error: {e}")
        
        def disconnect_worker():
            try:
                self.connection_manager.disconnect()
                results.append("disconnect_success")
            except Exception as e:
                results.append(f"disconnect_error: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=connect_worker)
            threads.append(t)
            t.start()
        
        for i in range(2):
            t = threading.Thread(target=disconnect_worker)
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=5.0)
        
        # Verify no deadlocks or crashes
        self.assertGreaterEqual(len(results), 5)
    
    def test_concurrent_connections(self):
        """Test creating multiple concurrent connections successfully."""
        num_connections = 3
        connection_managers = []
        results = []
        
        # Create multiple connection managers with separate factories
        for i in range(num_connections):
            factory = MockWebSocketFactory()
            events = MockEventManager()
            manager = ConnectionManager(
                websocket_factory=factory,
                event_manager=events
            )
            connection_managers.append((manager, factory, events))
        
        def connection_worker(manager, factory, events, index):
            """Worker function for concurrent connection testing."""
            try:
                config = ConnectionConfig(
                    host=f"localhost:808{index}",
                    database_address=f"testdb{index}",
                    auth_token=f"test_token_{index}",
                    ssl_enabled=False,
                    connection_timeout=2.0,
                    auto_reconnect=False
                )
                
                # Attempt connection
                manager.connect(config)
                time.sleep(0.1)
                
                # Simulate successful connection
                if factory.created_websockets:
                    ws = factory.created_websockets[0]
                    ws.run_forever()
                    time.sleep(0.1)
                
                # Verify connection is established
                if manager.is_connected():
                    results.append(f"connection_{index}_success")
                else:
                    results.append(f"connection_{index}_failed")
                    
                # Clean disconnect
                manager.disconnect()
                time.sleep(0.1)
                
                results.append(f"disconnect_{index}_success")
                
            except Exception as e:
                results.append(f"connection_{index}_error: {e}")
        
        # Start all connection workers concurrently
        threads = []
        for i, (manager, factory, events) in enumerate(connection_managers):
            thread = threading.Thread(
                target=connection_worker,
                args=(manager, factory, events, i),
                name=f"ConnectionTest-{i}"
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete with timeout
        for thread in threads:
            thread.join(timeout=10.0)
            if thread.is_alive():
                self.fail(f"Thread {thread.name} did not complete within timeout")
        
        # Verify results
        self.assertGreaterEqual(len(results), num_connections)
        
        # Count successful connections
        successful_connections = sum(1 for r in results if "connection_" in r and "_success" in r)
        self.assertEqual(successful_connections, num_connections, 
                        f"Expected {num_connections} successful concurrent connections, got {successful_connections}. Results: {results}")
        
        # Verify no connection errors occurred
        error_results = [r for r in results if "_error:" in r]
        if error_results:
            self.fail(f"Connection errors occurred: {error_results}")


class TestConnectionConfig(unittest.TestCase):
    """Test cases for ConnectionConfig."""
    
    def test_valid_config(self):
        """Test valid configuration."""
        config = ConnectionConfig(
            host="localhost:8080",
            database_address="testdb"
        )
        
        # Should not raise
        config.validate()
    
    def test_invalid_host(self):
        """Test invalid host validation."""
        config = ConnectionConfig(
            host="",
            database_address="testdb"
        )
        
        with self.assertRaises(ValueError):
            config.validate()
    
    def test_invalid_timeout(self):
        """Test invalid timeout validation."""
        config = ConnectionConfig(
            host="localhost",
            database_address="testdb",
            connection_timeout=-1.0
        )
        
        with self.assertRaises(ValueError):
            config.validate()


class TestConnectionMetrics(unittest.TestCase):
    """Test cases for ConnectionMetrics."""
    
    def test_metrics_recording(self):
        """Test metrics recording functionality."""
        metrics = ConnectionMetrics()
        
        # Record connection attempt
        metrics.record_connection_attempt()
        self.assertEqual(metrics.connection_attempts, 1)
        
        # Record success
        metrics.record_connection_success()
        self.assertEqual(metrics.successful_connections, 1)
        self.assertEqual(metrics.consecutive_failures, 0)
        self.assertIsNotNone(metrics.last_connection_time)
        
        # Record failure
        metrics.record_connection_failure()
        self.assertEqual(metrics.failed_connections, 1)
        self.assertEqual(metrics.consecutive_failures, 1)
        
        # Record disconnection
        metrics.record_disconnection()
        self.assertEqual(metrics.disconnections, 1)


if __name__ == '__main__':
    unittest.main()