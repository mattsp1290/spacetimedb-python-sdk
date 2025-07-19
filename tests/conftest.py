"""
Pytest configuration and shared fixtures for v1.1.2 compatibility tests
"""
import pytest
import threading
import json
import time
from unittest.mock import Mock, MagicMock, patch
import websocket
import sys
import os

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.protocol import (
    TEXT_PROTOCOL, BIN_PROTOCOL,
    Identity, ConnectionId, IdentityToken
)


class MockWebSocketApp:
    """Mock WebSocket app for testing"""
    
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
        self._sent_messages = []
        
    def run_forever(self):
        """Simulate connection"""
        # Check URL format for v1.1.2 compatibility
        if "/v1/database/" not in self.url:
            # Old URL format - reject
            if self.on_error:
                self.on_error(self, Exception("Invalid URL format for v1.1.2"))
            if self.on_close:
                self.on_close(self, None, None)
            return
            
        # Check protocol
        if self.subprotocols and self.subprotocols[0] in [TEXT_PROTOCOL, BIN_PROTOCOL]:
            # Valid protocol
            if self.on_open:
                self.on_open(self)
            # Send identity token
            self._send_identity_token()
        else:
            # Invalid protocol
            if self.on_error:
                error = websocket.WebSocketException("Handshake status 400 Bad Request")
                error.status_code = 400
                self.on_error(self, error)
            if self.on_close:
                self.on_close(self, None, None)
                
    def send(self, data):
        """Track sent messages"""
        self._sent_messages.append(data)
        
    def close(self):
        """Close the mock connection"""
        self.closed = True
        
    def _send_identity_token(self):
        """Simulate receiving identity token"""
        if self.on_message:
            # Create mock identity token message
            identity = Identity.from_hex("0" * 32)
            connection_id = ConnectionId.from_hex("0" * 16)
            token_msg = IdentityToken(
                token="test_token",
                identity=identity,
                connection_id=connection_id
            )
            # Simulate encoding (simplified)
            self.on_message(self, json.dumps({
                "IdentityToken": {
                    "token": "test_token",
                    "identity": "0" * 32,
                    "connection_id": "0" * 16
                }
            }))


@pytest.fixture
def mock_websocket():
    """Mock websocket module"""
    with patch('spacetimedb_sdk.websocket_client.websocket') as mock_ws:
        mock_ws.WebSocketApp = MockWebSocketApp
        mock_ws.WebSocketException = websocket.WebSocketException
        yield mock_ws


@pytest.fixture
def test_client_params():
    """Common test client parameters"""
    return {
        "host": "localhost:3000",
        "database_address": "test-db",
        "auth_token": None,
        "ssl_enabled": False,
        "db_identity": "550e8400-e29b-41d4-a716-446655440000"
    }


@pytest.fixture
def mock_server_response():
    """Mock server responses for different scenarios"""
    
    def _response_factory(scenario="success"):
        if scenario == "success":
            return {
                "type": "IdentityToken",
                "token": "test_token",
                "identity": "0" * 32,
                "connection_id": "0" * 16
            }
        elif scenario == "invalid_protocol":
            return {
                "error": "no valid protocol selected",
                "status": 400
            }
        elif scenario == "invalid_db_name":
            return {
                "error": "Invalid URL: invalid characters in database name",
                "status": 400
            }
        elif scenario == "not_found":
            return {
                "error": "Database not found",
                "status": 404
            }
        else:
            return {}
            
    return _response_factory


@pytest.fixture
def cleanup_client():
    """Cleanup any client instances after tests"""
    yield
    # Force cleanup of any lingering clients
    import gc
    gc.collect()


class ConnectionTracker:
    """Track connection attempts for testing"""
    
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.connected = False
        self.disconnected = False
        self.error = None
        self.identity_received = False
        self.token = None
        self.identity = None
        self.connection_id = None
        
    def on_connect(self):
        self.connected = True
        
    def on_disconnect(self, msg):
        self.disconnected = True
        
    def on_error(self, error):
        self.error = error
        
    def on_identity(self, token, identity, connection_id):
        self.identity_received = True
        self.token = token
        self.identity = identity
        self.connection_id = connection_id


@pytest.fixture
def connection_tracker():
    """Create a connection tracker for tests"""
    return ConnectionTracker()


@pytest.fixture
def wait_for_connection():
    """Helper to wait for connection events"""
    
    def _wait(tracker, timeout=5, check_connected=True):
        """Wait for connection to complete or fail"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if check_connected and tracker.connected:
                return True
            if tracker.error:
                return False
            if tracker.disconnected:
                return False
            time.sleep(0.1)
        return False
        
    return _wait


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests"""
    import psutil
    
    class PerformanceMonitor:
        def __init__(self):
            self.process = psutil.Process()
            self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            self.start_cpu = self.process.cpu_percent()
            self.start_time = time.time()
        
        def get_memory_usage(self):
            return self.process.memory_info().rss / 1024 / 1024  # MB
        
        def get_memory_delta(self):
            return self.get_memory_usage() - self.start_memory
        
        def get_cpu_usage(self):
            return self.process.cpu_percent()
        
        def get_elapsed_time(self):
            return time.time() - self.start_time
    
    return PerformanceMonitor()


@pytest.fixture
def event_system():
    """Provide isolated event system for testing"""
    from spacetimedb_sdk.events import UnifiedEventManager
    return UnifiedEventManager()


@pytest.fixture
def mock_auth_handler():
    """Mock authentication handler"""
    mock_handler = Mock()
    mock_handler.authenticate.return_value = {
        "token": "test_token_12345",
        "identity": "test_identity",
        "expires_at": time.time() + 3600
    }
    mock_handler.is_authenticated.return_value = True
    mock_handler.get_token.return_value = "test_token_12345"
    return mock_handler


@pytest.fixture
def mock_websocket_factory():
    """Factory for creating mock WebSocket connections"""
    
    def create_mock_websocket(
        connect_delay=0.1, 
        should_fail=False, 
        fail_message="Connection failed"
    ):
        mock_ws = Mock()
        
        def run_forever():
            if should_fail:
                if mock_ws.on_error:
                    mock_ws.on_error(mock_ws, Exception(fail_message))
                if mock_ws.on_close:
                    mock_ws.on_close(mock_ws, 1006, fail_message)
            else:
                time.sleep(connect_delay)
                if mock_ws.on_open:
                    mock_ws.on_open(mock_ws)
                # Send identity token
                if mock_ws.on_message:
                    identity_msg = json.dumps({
                        "IdentityToken": {
                            "token": "test_token",
                            "identity": "a" * 64,
                            "connection_id": "b" * 32
                        }
                    })
                    mock_ws.on_message(mock_ws, identity_msg)
        
        mock_ws.run_forever = run_forever
        mock_ws.send = Mock()
        mock_ws.close = Mock()
        mock_ws.closed = False
        
        return mock_ws
    
    return create_mock_websocket


@pytest.fixture
def comprehensive_test_data():
    """Provide comprehensive test data for various scenarios"""
    return {
        "valid_hosts": [
            "localhost:3000",
            "127.0.0.1:8080",
            "example.com:9000",
            "192.168.1.100:3000"
        ],
        "invalid_hosts": [
            "",
            "invalid",
            "localhost:99999",
            "127.0.0.1:0"
        ],
        "valid_db_names": [
            "test_db",
            "user-database",
            "db_123",
            "production_db"
        ],
        "invalid_db_names": [
            "",
            "db with spaces",
            "db/with/slashes",
            "db;with;semicolons"
        ],
        "test_events": [
            {"type": "TableUpdate", "table": "users", "data": {"id": 1}},
            {"type": "ReducerResult", "reducer": "create_user", "result": {"success": True}},
            {"type": "ConnectionUpdate", "state": "connected", "timestamp": time.time()},
            {"type": "AuthUpdate", "authenticated": True, "token": "new_token"}
        ],
        "error_scenarios": [
            {"error": "Connection timeout", "code": "TIMEOUT"},
            {"error": "Invalid credentials", "code": "AUTH_FAILED"},
            {"error": "Database not found", "code": "DB_NOT_FOUND"},
            {"error": "Rate limit exceeded", "code": "RATE_LIMITED"}
        ]
    }


@pytest.fixture
def security_test_payloads():
    """Provide security test payloads"""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'--",
            "1; DELETE FROM users WHERE 1=1"
        ],
        "xss_payloads": [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "onerror=alert(1)",
            "<img src=x onerror=alert(1)>"
        ],
        "buffer_overflow": [
            "A" * 1000,
            "A" * 10000,
            "A" * 100000
        ],
        "format_strings": [
            "%s%s%s%s",
            "%x%x%x%x",
            "%n%n%n%n"
        ],
        "null_bytes": [
            "test\x00data",
            "test\x00\x00\x00",
            "\x00test"
        ]
    }


@pytest.fixture(scope="session")
def test_server_config():
    """Configuration for test server"""
    return {
        "host": "localhost",
        "port": 3000,
        "ssl_enabled": False,
        "timeout": 30,
        "max_connections": 100,
        "buffer_size": 8192
    }
