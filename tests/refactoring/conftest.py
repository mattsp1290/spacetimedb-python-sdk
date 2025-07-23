"""
Pytest configuration and fixtures for Phase 2 refactoring tests
"""
import pytest
import threading
import json
import time
import logging
from unittest.mock import Mock, MagicMock, patch
import websocket
import sys
import os
from typing import Dict, Any, Optional, List, Callable
import asyncio
import queue
from dataclasses import dataclass
import tempfile
import shutil

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from spacetimedb_sdk.websocket_client import WebSocketClient, SubscriptionMetrics, ConnectionState
from spacetimedb_sdk.protocol import (
    TEXT_PROTOCOL, BIN_PROTOCOL,
    Identity, ConnectionId, IdentityToken,
    CallReducer, Subscribe, Unsubscribe, OneOffQuery,
    TransactionUpdate, SubscriptionError
)
from spacetimedb_sdk.exceptions import (
    WebSocketHandshakeError,
    DatabaseNotFoundError,
    AuthenticationError,
    ConnectionTimeoutError
)

# Import test fixtures to make them available
from .test_fixtures import *


@dataclass
class MockMessage:
    """Mock message for testing"""
    data: str
    type: str = "text"
    
    
@dataclass
class ConnectionEvent:
    """Track connection events for testing"""
    event_type: str
    timestamp: float
    data: Any = None
    error: Optional[Exception] = None


class MockWebSocketServer:
    """Mock WebSocket server for testing refactored modules"""
    
    def __init__(self):
        self.clients = []
        self.messages = []
        self.responses = queue.Queue()
        self.connection_behavior = "success"  # success, fail, timeout
        self.protocol_support = [TEXT_PROTOCOL, BIN_PROTOCOL]
        self.database_status = "published"  # published, not_found, not_published
        self.auth_behavior = "success"  # success, fail, invalid_token
        self.message_delay = 0.0
        self.max_message_size = 1024 * 1024  # 1MB
        self.compression_enabled = True
        self.event_log = []
        
    def set_behavior(self, connection="success", auth="success", database="published"):
        """Configure server behavior for testing"""
        self.connection_behavior = connection
        self.auth_behavior = auth
        self.database_status = database
        
    def add_response(self, message_type, data):
        """Add a mock response to the queue"""
        self.responses.put((message_type, data))
        
    def simulate_message(self, message_type, data, delay=0.0):
        """Simulate receiving a message from the server"""
        if delay > 0:
            time.sleep(delay)
        self.messages.append((message_type, data, time.time()))
        
    def get_received_messages(self):
        """Get all messages received by the server"""
        return self.messages.copy()
        
    def clear_messages(self):
        """Clear all received messages"""
        self.messages.clear()
        
    def log_event(self, event_type, data=None):
        """Log an event for testing"""
        self.event_log.append(ConnectionEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data
        ))


class WebSocketClientMock:
    """Mock WebSocket client for testing"""
    
    def __init__(self, url, on_open=None, on_message=None, on_error=None, 
                 on_close=None, header=None, subprotocols=None):
        self.url = url
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.header = header
        self.subprotocols = subprotocols
        self.closed = False
        self.connected = False
        self._sent_messages = []
        self._server = None
        
    def connect_to_server(self, server: MockWebSocketServer):
        """Connect to a mock server"""
        self._server = server
        server.clients.append(self)
        
    def run_forever(self):
        """Simulate connection"""
        if not self._server:
            return
            
        server = self._server
        
        # Simulate connection behavior
        if server.connection_behavior == "fail":
            if self.on_error:
                self.on_error(self, Exception("Connection failed"))
            return
        elif server.connection_behavior == "timeout":
            time.sleep(2)  # Simulate timeout
            if self.on_error:
                self.on_error(self, Exception("Connection timeout"))
            return
            
        # Check protocol support
        if self.subprotocols and self.subprotocols[0] not in server.protocol_support:
            if self.on_error:
                error = websocket.WebSocketException("Unsupported protocol")
                error.status_code = 400
                self.on_error(self, error)
            return
            
        # Check database status
        if server.database_status == "not_found":
            if self.on_error:
                error = websocket.WebSocketException("Database not found")
                error.status_code = 404
                self.on_error(self, error)
            return
        elif server.database_status == "not_published":
            if self.on_error:
                error = websocket.WebSocketException("Database not published")
                error.status_code = 403
                self.on_error(self, error)
            return
            
        # Successful connection
        self.connected = True
        server.log_event("client_connected", self.url)
        
        if self.on_open:
            self.on_open(self)
            
        # Send identity token if auth is successful
        if server.auth_behavior == "success":
            self._send_identity_token()
        elif server.auth_behavior == "fail":
            if self.on_error:
                self.on_error(self, Exception("Authentication failed"))
                
    def send(self, data):
        """Track sent messages"""
        self._sent_messages.append(data)
        if self._server:
            self._server.messages.append(("client_send", data, time.time()))
            
    def close(self):
        """Close the mock connection"""
        self.closed = True
        self.connected = False
        if self._server:
            self._server.log_event("client_disconnected", self.url)
            if self in self._server.clients:
                self._server.clients.remove(self)
                
    def _send_identity_token(self):
        """Simulate receiving identity token"""
        if self.on_message:
            identity = Identity.from_hex("0" * 32)
            connection_id = ConnectionId.from_hex("0" * 16)
            token_msg = {
                "IdentityToken": {
                    "token": "test_token",
                    "identity": "0" * 32,
                    "connection_id": "0" * 16
                }
            }
            self.on_message(self, json.dumps(token_msg))


class SubscriptionManagerMock:
    """Mock subscription manager for testing"""
    
    def __init__(self):
        self.subscriptions = {}
        self.query_states = {}
        self.metrics = SubscriptionMetrics()
        self.callbacks = []
        
    def add_subscription(self, query_id, table_name, sql_query):
        """Add a subscription"""
        self.subscriptions[query_id] = {
            'table_name': table_name,
            'sql_query': sql_query,
            'status': 'pending',
            'created_at': time.time()
        }
        return True
        
    def remove_subscription(self, query_id):
        """Remove a subscription"""
        if query_id in self.subscriptions:
            del self.subscriptions[query_id]
            
    def get_subscription(self, query_id):
        """Get subscription details"""
        return self.subscriptions.get(query_id)
        
    def get_all_subscriptions(self):
        """Get all subscriptions"""
        return self.subscriptions.copy()
    
    def get_subscription_count(self):
        """Get number of active subscriptions"""
        return len(self.subscriptions)
        
    def update_subscription_status(self, query_id, status):
        """Update subscription status"""
        if query_id in self.subscriptions:
            self.subscriptions[query_id]['status'] = status
    
    def handle_subscription_applied(self, query_id, table_name):
        """Handle subscription applied event"""
        if query_id in self.subscriptions:
            self.subscriptions[query_id]['status'] = 'active'
            
    def handle_subscription_error(self, query_id, error):
        """Handle subscription error event"""
        if query_id in self.subscriptions:
            self.subscriptions[query_id]['status'] = 'error'
            self.subscriptions[query_id]['error'] = error
            
            # Update metrics for error tracking
            table_name = self.subscriptions[query_id]['table_name']
            self.metrics.record_subscription_error(table_name, error)
            
    def cleanup_inactive_subscriptions(self, max_age_hours):
        """Clean up inactive subscriptions older than specified age"""
        current_time = time.time()
        to_remove = []
        
        for query_id, subscription in self.subscriptions.items():
            # Calculate age in hours
            age_seconds = current_time - subscription['created_at']
            age_hours = age_seconds / 3600
            
            # Remove subscriptions that are older than max_age_hours
            if age_hours >= max_age_hours:
                to_remove.append(query_id)
                
        for query_id in to_remove:
            del self.subscriptions[query_id]
            
        return len(to_remove)


class AuthenticationHandlerMock:
    """Mock authentication handler for testing"""
    
    def __init__(self):
        self.identity = None
        self.connection_id = None
        self.token = None
        self.identity_token = None
        self.auth_callbacks = []
        self.error_callbacks = []
        self.auth_status = "unauthenticated"
        
    def set_identity(self, identity, connection_id, token):
        """Set identity information"""
        self.identity = identity
        self.connection_id = connection_id
        self.token = token
        self.auth_status = "authenticated"
        
    def clear_identity(self):
        """Clear identity information"""
        self.identity = None
        self.connection_id = None
        self.token = None
        self.auth_status = "unauthenticated"
        
    def add_auth_callback(self, callback):
        """Add authentication callback"""
        self.auth_callbacks.append(callback)
        
    def remove_auth_callback(self, callback):
        """Remove authentication callback"""
        if callback in self.auth_callbacks:
            self.auth_callbacks.remove(callback)
    
    def add_error_handler(self, callback):
        """Add error handler callback - alias for add_error_callback"""
        self.error_callbacks.append(callback)
    
    def add_error_callback(self, callback):
        """Add error callback"""
        self.error_callbacks.append(callback)
    
    def set_auth_token(self, token):
        """Set authentication token"""
        self.token = token
        
    def get_auth_token(self):
        """Get authentication token"""
        return self.token
    
    def authenticate(self, token=None):
        """Authenticate with optional token"""
        if token:
            self.token = token
        if self.token:
            self.auth_status = "authenticated"
            return True
        return False
    
    def is_authenticated(self):
        """Check if authenticated"""
        return self.auth_status == "authenticated"
    
    def handle_identity_token(self, identity_token_msg):
        """Handle identity token message from server"""
        try:
            self.identity_token = identity_token_msg.token
            self.identity = identity_token_msg.identity
            self.connection_id = identity_token_msg.connection_id
            self.auth_status = "authenticated"
            
            # Notify auth callbacks
            for callback in self.auth_callbacks:
                try:
                    callback(self.identity_token, self.identity, self.connection_id)
                except Exception as e:
                    logging.error(f"Auth callback error: {e}")
            
            return True
        except Exception:
            return False
    
    def get_identity(self):
        """Get current identity"""
        return self.identity
    
    def get_connection_id(self):
        """Get current connection ID"""
        return self.connection_id
    
    def get_auth_status(self):
        """Get authentication status"""
        return self.auth_status
            
    def notify_auth_change(self, event_type, data):
        """Notify authentication change"""
        for callback in self.auth_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logging.error(f"Auth callback error: {e}")
                
    def handle_auth_error(self, error):
        """Handle authentication error"""
        self.auth_status = "error"
        self.clear_identity()
        
        # Notify error callbacks
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logging.error(f"Auth error callback error: {e}")


class EventSystemMock:
    """Mock unified event system for testing"""
    
    def __init__(self):
        self.events = []
        self.subscribers = {}
        self.event_queue = queue.Queue()
        
    def emit(self, event_type, data=None):
        """Emit an event"""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        }
        self.events.append(event)
        self.event_queue.put(event)
        
        # Notify subscribers
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logging.error(f"Event callback error: {e}")
                    
    def subscribe(self, event_type, callback):
        """Subscribe to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        
    def unsubscribe(self, event_type, callback):
        """Unsubscribe from an event type"""
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            
    def get_events(self, event_type=None):
        """Get events, optionally filtered by type"""
        if event_type:
            return [e for e in self.events if e['type'] == event_type]
        return self.events.copy()
        
    def clear_events(self):
        """Clear all events"""
        self.events.clear()
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except queue.Empty:
                break


@pytest.fixture
def mock_websocket_server():
    """Create a mock WebSocket server"""
    return MockWebSocketServer()


@pytest.fixture
def mock_websocket_client():
    """Mock websocket client"""
    with patch('spacetimedb_sdk.websocket_client.websocket') as mock_ws:
        mock_ws.WebSocketApp = WebSocketClientMock
        mock_ws.WebSocketException = websocket.WebSocketException
        yield mock_ws


@pytest.fixture
def subscription_manager_mock():
    """Create a mock subscription manager"""
    return SubscriptionManagerMock()


@pytest.fixture
def authentication_handler_mock():
    """Create a mock authentication handler"""
    return AuthenticationHandlerMock()


@pytest.fixture
def event_system_mock():
    """Create a mock event system"""
    return EventSystemMock()


@pytest.fixture
def refactoring_test_params():
    """Common test parameters for refactoring tests"""
    return {
        "host": "localhost:3000",
        "database_address": "test-db",
        "auth_token": None,
        "ssl_enabled": False,
        "db_identity": "550e8400-e29b-41d4-a716-446655440000"
    }


@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests"""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = {}
            self.start_times = {}
            
        def start_timing(self, operation):
            self.start_times[operation] = time.time()
            
        def stop_timing(self, operation):
            if operation in self.start_times:
                duration = time.time() - self.start_times[operation]
                if operation not in self.metrics:
                    self.metrics[operation] = []
                self.metrics[operation].append(duration)
                del self.start_times[operation]
                return duration
            return None
            
        def get_average_time(self, operation):
            if operation in self.metrics and self.metrics[operation]:
                return sum(self.metrics[operation]) / len(self.metrics[operation])
            return None
            
        def get_metrics(self):
            return self.metrics.copy()
            
    return PerformanceTracker()


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for tests"""
    workspace = tempfile.mkdtemp(prefix="spacetimedb_refactoring_test_")
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def regression_validator():
    """Validator for regression testing"""
    class RegressionValidator:
        def __init__(self):
            self.baseline_behaviors = {}
            self.test_results = {}
            
        def record_baseline(self, operation, result):
            """Record baseline behavior"""
            self.baseline_behaviors[operation] = result
            
        def validate_behavior(self, operation, result):
            """Validate behavior against baseline"""
            if operation not in self.baseline_behaviors:
                return True, "No baseline recorded"
                
            baseline = self.baseline_behaviors[operation]
            matches = self._compare_results(baseline, result)
            
            self.test_results[operation] = {
                'baseline': baseline,
                'result': result,
                'matches': matches
            }
            
            return matches, f"Baseline: {baseline}, Result: {result}"
            
        def _compare_results(self, baseline, result):
            """Compare two results"""
            if type(baseline) != type(result):
                return False
            if isinstance(baseline, dict):
                return all(
                    key in result and self._compare_results(baseline[key], result[key])
                    for key in baseline
                )
            return baseline == result
            
        def get_validation_report(self):
            """Get validation report"""
            return self.test_results.copy()
            
    return RegressionValidator()


@pytest.fixture
def connection_state_tracker():
    """Track connection state changes"""
    class ConnectionStateTracker:
        def __init__(self):
            self.state_changes = []
            self.current_state = None
            
        def record_state_change(self, old_state, new_state, timestamp=None):
            """Record a state change"""
            if timestamp is None:
                timestamp = time.time()
                
            self.state_changes.append({
                'old_state': old_state,
                'new_state': new_state,
                'timestamp': timestamp
            })
            self.current_state = new_state
            
        def get_state_history(self):
            """Get state change history"""
            return self.state_changes.copy()
            
        def get_current_state(self):
            """Get current state"""
            return self.current_state
            
    return ConnectionStateTracker()


@pytest.fixture
def memory_monitor():
    """Monitor memory usage during tests"""
    class MemoryMonitor:
        def __init__(self):
            self.snapshots = []
            
        def snapshot(self, label=""):
            """Take a memory snapshot"""
            import psutil
            import gc
            
            gc.collect()  # Force garbage collection
            
            process = psutil.Process()
            memory_info = process.memory_info()
            
            snapshot = {
                'label': label,
                'timestamp': time.time(),
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'percent': process.memory_percent()
            }
            
            self.snapshots.append(snapshot)
            return snapshot
            
        def get_snapshots(self):
            """Get all memory snapshots"""
            return self.snapshots.copy()
            
        def get_memory_growth(self):
            """Calculate memory growth"""
            if len(self.snapshots) < 2:
                return 0
                
            first = self.snapshots[0]
            last = self.snapshots[-1]
            
            return last['rss'] - first['rss']
            
    return MemoryMonitor()


@pytest.fixture
def mock_connected_websocket_client():
    """Create a properly mocked and connected WebSocket client for performance testing"""
    from spacetimedb_sdk.websocket_client import WebSocketClient, ConnectionState
    from unittest.mock import Mock, patch
    
    client = WebSocketClient()
    mock_instance = Mock()
    
    with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
        mock_ws_app.return_value = mock_instance
        
        # Initialize the connection manager by accessing the property
        connection_manager = client.connection_manager
        
        # Mock the connection manager to be properly connected
        with patch.object(connection_manager, 'is_connected', return_value=True):
            with patch.object(connection_manager, 'get_connection_state', return_value=ConnectionState.CONNECTED):
                with patch.object(connection_manager, 'send_data', return_value=None):
                    # Set up mock WebSocket and ensure connection reference is set
                    client.ws = mock_instance
                    client.state = ConnectionState.CONNECTED
                    client.ws_app = mock_instance
                    connection_manager._connection = mock_instance
                    
                    yield client, mock_instance


@pytest.fixture
def performance_baseline_fixture():
    """Create performance baseline for comparison"""
    from .test_fixtures import PerformanceBaseline
    baseline = PerformanceBaseline()
    # Set reasonable default baselines for test environment
    baseline.baselines = {
        'connection_time': 1.0,  # 1 second max connection time
        'subscription_time': 0.1,  # 100ms max subscription time
        'message_processing_time': 0.01,  # 10ms max per message
        'cpu_usage_percent': 50.0,  # Max 50% CPU increase
        'memory_usage_mb': 50.0,  # Max 50MB memory usage
    }
    return baseline


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test"""
    yield
    # Force garbage collection
    import gc
    gc.collect()
    
    # Clear any global state
    logging.getLogger().handlers.clear()