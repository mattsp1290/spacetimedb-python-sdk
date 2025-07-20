"""
Pytest configuration and fixtures for integration tests with comprehensive WebSocket mocking.

This module provides mock infrastructure to prevent real network connections
in integration tests while properly simulating connection events and state changes.
"""
import pytest
import threading
import json
import time
import asyncio
import logging
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import websocket
import sys
import os
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import queue
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.websocket_client import WebSocketClient, ConnectionState
from spacetimedb_sdk.events.event_manager import UnifiedEventManager
from spacetimedb_sdk.events.core_events import EventType, Event, create_connection_event, create_error_event
from spacetimedb_sdk.events.event_context import EventContext
from spacetimedb_sdk.protocol import (
    TEXT_PROTOCOL, BIN_PROTOCOL,
    Identity, ConnectionId, IdentityToken
)


class MockConnectionState(Enum):
    """Mock connection states for testing."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


@dataclass
class MockConnectionEvent:
    """Mock connection event for testing."""
    event_type: str
    timestamp: float
    data: Dict[str, Any]
    error: Optional[Exception] = None


class MockWebSocketApp:
    """
    Comprehensive WebSocket app mock that simulates real connection behavior
    including events, callbacks, and state transitions without network calls.
    """
    
    def __init__(self, url, on_open=None, on_message=None, on_error=None, 
                 on_close=None, header=None, subprotocols=None, **kwargs):
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
        self._connection_events = []
        self._event_queue = queue.Queue()
        self._should_fail = False
        self._failure_reason = None
        self._connection_delay = 0.1
        self._auto_send_identity = True
        self._mock_server_responses = True
        self._state = MockConnectionState.DISCONNECTED
        
        # Configure mock behavior based on URL and protocols
        self._configure_mock_behavior()
        
    def _configure_mock_behavior(self):
        """Configure mock behavior based on connection parameters."""
        # Check for v1.1.2 URL format
        if "/v1/database/" not in self.url and "/v1/ws/" not in self.url:
            self._should_fail = True
            self._failure_reason = "Invalid URL format for v1.1.2"
            
        # Check protocol support
        if self.subprotocols and self.subprotocols[0] not in [TEXT_PROTOCOL, BIN_PROTOCOL]:
            self._should_fail = True
            self._failure_reason = "Unsupported protocol"
            
    def run_forever(self, dispatcher=None, sslopt=None, ping_interval=0, ping_timeout=None, **kwargs):
        """
        Simulate connection process with proper event triggering.
        This replaces real network calls with mock behavior.
        """
        self._log_event("connection_attempt", {"url": self.url})
        
        # Simulate connection delay
        if self._connection_delay > 0:
            time.sleep(self._connection_delay)
            
        # Handle connection failures
        if self._should_fail:
            self._trigger_error(Exception(self._failure_reason))
            return
            
        # Simulate successful connection
        self._state = MockConnectionState.CONNECTING
        self._log_event("connecting", {})
        
        # Small delay to simulate handshake
        time.sleep(0.05)
        
        # Trigger connection opened
        self._state = MockConnectionState.CONNECTED
        self.connected = True
        self._log_event("connected", {})
        
        if self.on_open:
            try:
                self.on_open(self)
            except Exception as e:
                logging.error(f"Error in on_open callback: {e}")
                self._trigger_error(e)
                return
                
        # Auto-send identity token if enabled
        if self._auto_send_identity:
            self._send_mock_identity_token()
            
        # Keep connection alive simulation
        self._simulate_keep_alive()
        
    def _send_mock_identity_token(self):
        """Send mock identity token to trigger authentication flow."""
        if not self.on_message:
            return
            
        # Simulate server delay
        time.sleep(0.02)
        
        identity_msg = {
            "IdentityToken": {
                "token": "mock_test_token_12345",
                "identity": "a" * 64,  # 64 hex chars for 32 bytes
                "connection_id": "b" * 32  # 32 hex chars for 16 bytes
            }
        }
        
        self._log_event("identity_token_sent", identity_msg)
        
        try:
            self.on_message(self, json.dumps(identity_msg))
        except Exception as e:
            logging.error(f"Error in on_message callback for identity: {e}")
            
    def _simulate_keep_alive(self):
        """Simulate keep-alive behavior without blocking."""
        # This would normally be a long-running loop, but for tests we just mark as ready
        self._state = MockConnectionState.AUTHENTICATED
        self._log_event("authenticated", {})
        
    def _trigger_error(self, error):
        """Trigger error callback with proper cleanup."""
        self._state = MockConnectionState.ERROR
        self._log_event("error", {"error": str(error)})
        
        if self.on_error:
            try:
                self.on_error(self, error)
            except Exception as e:
                logging.error(f"Error in on_error callback: {e}")
                
        # Also trigger close after error
        self._trigger_close(1006, "Connection error")
        
    def _trigger_close(self, code=1000, reason="Normal closure"):
        """Trigger close callback with proper cleanup."""
        self.connected = False
        self.closed = True
        self._state = MockConnectionState.DISCONNECTED
        self._log_event("closed", {"code": code, "reason": reason})
        
        if self.on_close:
            try:
                self.on_close(self, code, reason)
            except Exception as e:
                logging.error(f"Error in on_close callback: {e}")
                
    def send(self, data, opcode=websocket.ABNF.OPCODE_TEXT):
        """Track sent messages and optionally respond."""
        self._sent_messages.append({
            "data": data,
            "opcode": opcode,
            "timestamp": time.time()
        })
        self._log_event("message_sent", {"data": data, "opcode": opcode})
        
        # Auto-respond to certain message types if enabled
        if self._mock_server_responses:
            self._generate_mock_response(data)
            
    def _generate_mock_response(self, sent_data):
        """Generate mock server responses based on sent data."""
        if not self.on_message:
            return
            
        try:
            message = json.loads(sent_data)
            
            # Handle subscription requests
            if "Subscribe" in message:
                self._send_subscription_response(message)
            elif "CallReducer" in message:
                self._send_reducer_response(message)
            elif "OneOffQuery" in message:
                self._send_query_response(message)
                
        except (json.JSONDecodeError, KeyError):
            # Ignore malformed messages
            pass
            
    def _send_subscription_response(self, subscribe_msg):
        """Send mock subscription response."""
        # Simulate server processing delay
        def delayed_response():
            time.sleep(0.02)
            response = {
                "SubscriptionApplied": {
                    "query_id": subscribe_msg.get("Subscribe", {}).get("query_id", "mock_query_id"),
                    "table_name": "mock_table"
                }
            }
            if self.on_message:
                self.on_message(self, json.dumps(response))
                
        threading.Thread(target=delayed_response, daemon=True).start()
        
    def _send_reducer_response(self, reducer_msg):
        """Send mock reducer response."""
        def delayed_response():
            time.sleep(0.05)
            response = {
                "CallReducerResult": {
                    "call_id": reducer_msg.get("CallReducer", {}).get("call_id", "mock_call_id"),
                    "result": {"success": True, "data": "mock_result"}
                }
            }
            if self.on_message:
                self.on_message(self, json.dumps(response))
                
        threading.Thread(target=delayed_response, daemon=True).start()
        
    def _send_query_response(self, query_msg):
        """Send mock query response."""
        def delayed_response():
            time.sleep(0.03)
            response = {
                "OneOffQueryResult": {
                    "query_id": query_msg.get("OneOffQuery", {}).get("query_id", "mock_query_id"),
                    "result": [{"id": 1, "data": "mock_data"}]
                }
            }
            if self.on_message:
                self.on_message(self, json.dumps(response))
                
        threading.Thread(target=delayed_response, daemon=True).start()
        
    def close(self, code=1000, reason="Normal closure"):
        """Close the mock connection."""
        if not self.closed:
            self._trigger_close(code, reason)
            
    def _log_event(self, event_type, data):
        """Log connection events for testing inspection."""
        event = MockConnectionEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data
        )
        self._connection_events.append(event)
        self._event_queue.put(event)
        
    def get_connection_events(self):
        """Get all connection events for testing."""
        return self._connection_events.copy()
        
    def get_sent_messages(self):
        """Get all sent messages for testing."""
        return self._sent_messages.copy()
        
    def configure_failure(self, should_fail=True, reason="Mock failure"):
        """Configure the mock to fail connections."""
        self._should_fail = should_fail
        self._failure_reason = reason
        
    def configure_delay(self, delay=0.1):
        """Configure connection delay."""
        self._connection_delay = delay
        
    def configure_identity_behavior(self, auto_send=True):
        """Configure identity token behavior."""
        self._auto_send_identity = auto_send
        
    def configure_server_responses(self, enabled=True):
        """Configure automatic server response generation."""
        self._mock_server_responses = enabled


class IntegratedSpacetimeDBClientMock:
    """
    Mock that integrates with SpacetimeDBClient's event system to ensure
    proper event triggering and state management for integration tests.
    """
    
    def __init__(self, original_client, mock_ws_app):
        self.original_client = original_client
        self.mock_ws_app = mock_ws_app
        self._connection_callbacks = []
        self._event_handlers = {}
        
    def setup_event_integration(self):
        """Set up integration between mock WebSocket and client event system."""
        # Hook into the mock WebSocket callbacks to trigger client events
        original_on_open = self.mock_ws_app.on_open
        original_on_message = self.mock_ws_app.on_message
        original_on_close = self.mock_ws_app.on_close
        original_on_error = self.mock_ws_app.on_error
        
        def enhanced_on_open(ws):
            # Call original callback
            if original_on_open:
                original_on_open(ws)
            # Trigger client connection events
            self._trigger_client_connection_event()
            
        def enhanced_on_message(ws, message):
            # Call original callback
            if original_on_message:
                original_on_message(ws, message)
            # Parse and trigger appropriate client events
            self._handle_message_events(message)
            
        def enhanced_on_close(ws, code, reason):
            # Call original callback
            if original_on_close:
                original_on_close(ws, code, reason)
            # Trigger client disconnect events
            self._trigger_client_disconnect_event(reason)
            
        def enhanced_on_error(ws, error):
            # Call original callback
            if original_on_error:
                original_on_error(ws, error)
            # Trigger client error events
            self._trigger_client_error_event(error)
            
        # Replace callbacks with enhanced versions
        self.mock_ws_app.on_open = enhanced_on_open
        self.mock_ws_app.on_message = enhanced_on_message
        self.mock_ws_app.on_close = enhanced_on_close
        self.mock_ws_app.on_error = enhanced_on_error
        
    def _trigger_client_connection_event(self):
        """Trigger client-level connection established event."""
        if hasattr(self.original_client, '_event_emitter'):
            from spacetimedb_sdk.events.core_events import Event, EventType
            event = Event(
                type=EventType.CONNECTION_ESTABLISHED,
                data={"timestamp": time.time()},
                timestamp=time.time()
            )
            self.original_client._event_emitter.emit(event)
            
    def _trigger_client_disconnect_event(self, reason):
        """Trigger client-level connection closed event."""
        if hasattr(self.original_client, '_event_emitter'):
            from spacetimedb_sdk.events.core_events import Event, EventType
            event = Event(
                type=EventType.CONNECTION_CLOSED,
                data={"message": reason, "timestamp": time.time()},
                timestamp=time.time()
            )
            self.original_client._event_emitter.emit(event)
            
    def _trigger_client_error_event(self, error):
        """Trigger client-level connection error event."""
        if hasattr(self.original_client, '_event_emitter'):
            from spacetimedb_sdk.events.core_events import Event, EventType
            event = Event(
                type=EventType.CONNECTION_ERROR,
                data={"error": str(error), "error_type": type(error).__name__, "timestamp": time.time()},
                timestamp=time.time()
            )
            self.original_client._event_emitter.emit(event)
            
    def _handle_message_events(self, message_str):
        """Parse message and trigger appropriate client events."""
        try:
            message = json.loads(message_str)
            
            if "IdentityToken" in message:
                self._trigger_identity_event(message["IdentityToken"])
            elif "SubscriptionApplied" in message:
                self._trigger_subscription_event(message["SubscriptionApplied"])
            elif "TableUpdate" in message:
                self._trigger_table_update_event(message["TableUpdate"])
                
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Failed to parse message for event triggering: {e}")
            
    def _trigger_identity_event(self, identity_data):
        """Trigger identity received event."""
        if hasattr(self.original_client, '_event_emitter'):
            from spacetimedb_sdk.events.core_events import Event, EventType
            event_data = {
                "token": identity_data.get("token"),
                "identity": identity_data.get("identity"),
                "connection_id": identity_data.get("connection_id"),
                "timestamp": time.time()
            }
            event = Event(
                type=EventType.IDENTITY_RECEIVED,
                data=event_data,
                timestamp=time.time()
            )
            self.original_client._event_emitter.emit(event)
            
    def _trigger_subscription_event(self, subscription_data):
        """Trigger subscription applied event."""
        if hasattr(self.original_client, '_event_emitter'):
            from spacetimedb_sdk.events.core_events import Event, EventType
            event_data = {
                "query_id": subscription_data.get("query_id"),
                "table_name": subscription_data.get("table_name"),
                "timestamp": time.time()
            }
            event = Event(
                type=EventType.SUBSCRIPTION_APPLIED,
                data=event_data,
                timestamp=time.time()
            )
            self.original_client._event_emitter.emit(event)
            
    def _trigger_table_update_event(self, table_data):
        """Trigger table update event."""
        if hasattr(self.original_client, '_event_emitter'):
            from spacetimedb_sdk.events.core_events import Event, EventType
            event_data = {
                "table_name": table_data.get("table_name"),
                "updates": table_data.get("updates", []),
                "timestamp": time.time()
            }
            event = Event(
                type=EventType.TABLE_UPDATE,
                data=event_data,
                timestamp=time.time()
            )
            self.original_client._event_emitter.emit(event)


@pytest.fixture
def mock_websocket_comprehensive():
    """
    Comprehensive WebSocket mocking that prevents real network connections
    and properly simulates connection events for integration tests.
    """
    with patch('spacetimedb_sdk.websocket_client.websocket') as mock_ws:
        with patch('websocket.WebSocketApp', MockWebSocketApp):
            mock_ws.WebSocketApp = MockWebSocketApp
            mock_ws.WebSocketException = websocket.WebSocketException
            mock_ws.ABNF = websocket.ABNF
            yield mock_ws


@pytest.fixture
def integration_client_factory(mock_websocket_comprehensive):
    """
    Factory for creating SpacetimeDBClient instances with proper mocking
    for integration tests.
    """
    clients = []
    mock_integrations = []
    patches = []
    
    def create_client(**kwargs):
        # Set test mode and disable real connections
        kwargs.setdefault('test_mode', True)
        kwargs.setdefault('start_message_processing', False)
        
        # Create mock WebSocket first
        mock_ws_app = MockWebSocketApp("ws://localhost:3000/v1/database/test")
        
        # Create mock WebSocketClient
        mock_ws_client = Mock()
        mock_ws_client.ws_app = mock_ws_app
        mock_ws_client.connect = lambda: mock_ws_app.run_forever()
        mock_ws_client.send_message = mock_ws_app.send
        mock_ws_client.close = mock_ws_app.close
        mock_ws_client.connection_state = ConnectionState.DISCONNECTED
        
        # Patch WebSocketClient constructor to return our mock
        ws_patch = patch('spacetimedb_sdk.spacetimedb_client.WebSocketClient', return_value=mock_ws_client)
        ws_patch.start()
        patches.append(ws_patch)
        
        # Create the client
        client = SpacetimeDBClient(**kwargs)
        clients.append(client)
        
        # Set up integration after client creation
        mock_integration = IntegratedSpacetimeDBClientMock(client, mock_ws_app)
        mock_integration.setup_event_integration()
        mock_integrations.append(mock_integration)
        
        return client
        
    yield create_client
    
    # Cleanup patches
    for patch_obj in patches:
        try:
            patch_obj.stop()
        except Exception:
            pass
    patches.clear()
    
    # Cleanup clients and mock integrations
    for client in clients:
        try:
            if hasattr(client, 'close'):
                client.close()
            elif hasattr(client, 'shutdown'):
                client.shutdown()
        except Exception:
            pass
    
    # Clear mock integrations
    mock_integrations.clear()


@pytest.fixture
def mock_connection_events():
    """Track connection events across tests."""
    events = []
    
    def event_handler(context: EventContext):
        events.append({
            'type': context.event_type,
            'data': context.event.data,
            'timestamp': context.event.timestamp
        })
        
    yield events, event_handler
    events.clear()


@pytest.fixture
def connection_event_tracker():
    """Helper to track and verify connection events in tests."""
    class ConnectionEventTracker:
        def __init__(self):
            self.events = []
            self.handlers = {}
            
        def track_event(self, event_type, data=None):
            self.events.append({
                'type': event_type,
                'data': data or {},
                'timestamp': time.time()
            })
            
        def register_handler(self, event_type, handler):
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
            
        def get_events(self, event_type=None):
            if event_type:
                return [e for e in self.events if e['type'] == event_type]
            return self.events.copy()
            
        def get_event_count(self, event_type=None):
            return len(self.get_events(event_type))
            
        def clear_events(self):
            self.events.clear()
            
        def has_event_sequence(self, expected_sequence):
            """Check if events occurred in expected sequence."""
            if len(self.events) < len(expected_sequence):
                return False
                
            for i, expected_type in enumerate(expected_sequence):
                if i >= len(self.events) or self.events[i]['type'] != expected_type:
                    return False
            return True
            
    return ConnectionEventTracker()


@pytest.fixture
def async_test_helper():
    """Helper for async operations in sync tests."""
    class AsyncTestHelper:
        def __init__(self):
            self.loop = None
            
        def run_async(self, coro, timeout=5.0):
            """Run async coroutine in sync test."""
            if self.loop is None:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
            
            return asyncio.wait_for(coro, timeout=timeout)
            
        def run_in_executor(self, func, *args, **kwargs):
            """Run sync function in executor."""
            if self.loop is None:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
            executor = ThreadPoolExecutor(max_workers=2)
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=5.0)
            
    return AsyncTestHelper()


@pytest.fixture
def no_real_connections():
    """Ensure no real network connections are made during tests."""
    with patch('socket.socket') as mock_socket:
        with patch('ssl.create_default_context') as mock_ssl_context:
            # Make any real connection attempts fail fast
            mock_socket.side_effect = ConnectionError("Real connections disabled in tests")
            mock_ssl_context.side_effect = ConnectionError("Real SSL connections disabled in tests")
            yield
            

@pytest.fixture(autouse=True)
def setup_integration_test_environment(no_real_connections):
    """Auto-setup for all integration tests to prevent real connections."""
    # Disable actual networking
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = ConnectionError("HTTP requests disabled in integration tests")
        yield
        

@pytest.fixture
def wait_for_events():
    """Helper to wait for events to be processed."""
    def wait(event_tracker, expected_count, event_type=None, timeout=2.0):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if event_tracker.get_event_count(event_type) >= expected_count:
                return True
            time.sleep(0.01)
        return False
    return wait


@pytest.fixture
def integration_test_config():
    """Configuration for integration tests."""
    return {
        "host": "localhost:3000",
        "database_address": "test_db",
        "auth_token": None,
        "ssl_enabled": False,
        "connection_timeout": 1.0,  # Short timeout for tests
        "max_reconnect_attempts": 2,  # Limited reconnects for tests
        "test_mode": True
    }


@pytest.fixture(scope="function")
def cleanup_threads():
    """Cleanup any lingering threads after tests."""
    yield
    # Give threads time to finish
    time.sleep(0.1)
    # Force cleanup
    import gc
    gc.collect()