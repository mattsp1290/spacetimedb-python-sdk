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
