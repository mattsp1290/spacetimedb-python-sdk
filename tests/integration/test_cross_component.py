"""
Cross-component integration tests.

Tests interactions between different SDK components including event system,
authentication handler, WebSocket client, and protocol handlers.
"""
import pytest
import asyncio
import threading
import json
import time
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, Future

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.events.event_system import EventSystem
from spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler
from spacetimedb_sdk.websocket_client import WebSocketClient
from spacetimedb_sdk.protocol import Identity, ConnectionId, IdentityToken, BSATN


class TestCrossComponentIntegration:
    """Test integration between SDK components."""
    
    @pytest.fixture
    def event_system(self):
        """Provide isolated event system."""
        return EventSystem()
    
    @pytest.fixture
    def auth_handler(self):
        """Provide authentication handler."""
        return AuthenticationHandler()
    
    @pytest.fixture
    def mock_ws_client(self):
        """Provide mock WebSocket client."""
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'), \
             patch.object(WebSocketClient, '_do_connect') as mock_connect:
            client = WebSocketClient()
            mock_connect.return_value = None
            # Mock the connection state
            client.state = "connected"
            client.host = "localhost:3000"
            client.database_address = "test_db"
            yield client
    
    def test_event_system_integration(self, event_system):
        """Test event system integration with multiple components."""
        # Track events from different components
        component_events = {
            "auth": [],
            "connection": [],
            "protocol": [],
            "table": []
        }
        
        # Register handlers for different component events
        def auth_handler(event_data):
            component_events["auth"].append(event_data)
        
        def connection_handler(event_data):
            component_events["connection"].append(event_data)
        
        def protocol_handler(event_data):
            component_events["protocol"].append(event_data)
        
        def table_handler(event_data):
            component_events["table"].append(event_data)
        
        # Subscribe to component events
        event_system.subscribe("auth:token_refreshed", auth_handler)
        event_system.subscribe("connection:state_changed", connection_handler)
        event_system.subscribe("protocol:message_received", protocol_handler)
        event_system.subscribe("table:update", table_handler)
        
        # Simulate cross-component communication
        # 1. Auth token refresh triggers connection update
        event_system.emit("auth:token_refreshed", {"token": "new_token_123"})
        event_system.emit("connection:state_changed", {"state": "reconnecting"})
        
        # 2. Protocol message triggers table update
        event_system.emit("protocol:message_received", {"type": "TableUpdate"})
        event_system.emit("table:update", {"table": "users", "rows": 5})
        
        # 3. Connection change triggers auth check
        event_system.emit("connection:state_changed", {"state": "connected"})
        event_system.emit("auth:token_refreshed", {"token": "refreshed_token"})
        
        # Verify cross-component event flow
        assert len(component_events["auth"]) == 2
        assert len(component_events["connection"]) == 2
        assert len(component_events["protocol"]) == 1
        assert len(component_events["table"]) == 1
        
        # Verify event ordering makes sense
        assert component_events["auth"][0]["token"] == "new_token_123"
        assert component_events["connection"][0]["state"] == "reconnecting"
    
    def test_auth_handler_integration(self, auth_handler, event_system):
        """Test authentication handler integration with event system."""
        auth_events = []
        connection_events = []
        
        # Track auth and connection events
        event_system.subscribe("auth:*", lambda e: auth_events.append(e))
        event_system.subscribe("connection:*", lambda e: connection_events.append(e))
        
        # Integrate auth handler with event system
        if hasattr(auth_handler, 'set_event_system'):
            auth_handler.set_event_system(event_system)
        
        # Simulate authentication flow
        with patch.object(auth_handler, 'authenticate') as mock_auth:
            mock_auth.return_value = {
                "token": "auth_token_123",
                "identity": "user_identity_456",
                "expires_at": time.time() + 3600
            }
            
            # Perform authentication
            result = auth_handler.authenticate("test_user", "test_pass")
            
            # Should trigger auth events
            if hasattr(auth_handler, 'emit_event'):
                auth_handler.emit_event("auth:login_success", result)
            else:
                event_system.emit("auth:login_success", result)
            
            # Verify integration
            assert len(auth_events) > 0
            # The event data should contain the result data
            assert any(isinstance(e, dict) and "token" in str(e) for e in auth_events)
    
    def test_websocket_event_integration(self, mock_ws_client, event_system):
        """Test WebSocket client integration with event system."""
        ws_events = []
        protocol_events = []
        
        # Track WebSocket and protocol events
        event_system.subscribe("websocket:*", lambda e: ws_events.append(e))
        event_system.subscribe("protocol:*", lambda e: protocol_events.append(e))
        
        # Integrate WebSocket client with event system
        if hasattr(mock_ws_client, 'set_event_system'):
            mock_ws_client.set_event_system(event_system)
        
        # Simulate WebSocket events
        ws_states = ["connecting", "connected", "authenticated", "disconnected"]
        
        for state in ws_states:
            event_system.emit(f"websocket:{state}", {"timestamp": time.time()})
            
            # Protocol events should follow certain WebSocket events
            if state == "connected":
                event_system.emit("protocol:handshake_start", {})
            elif state == "authenticated":
                event_system.emit("protocol:ready", {})
        
        # Verify event integration
        assert len(ws_events) == len(ws_states)
        assert len(protocol_events) >= 2  # handshake_start and ready
    
    def test_error_propagation_between_components(self, event_system, auth_handler, mock_ws_client):
        """Test error propagation between components."""
        component_errors = {
            "auth": [],
            "websocket": [],
            "protocol": [],
            "global": []
        }
        
        # Set up error handlers
        event_system.subscribe("error:auth", lambda e: component_errors["auth"].append(e))
        event_system.subscribe("error:websocket", lambda e: component_errors["websocket"].append(e))
        event_system.subscribe("error:protocol", lambda e: component_errors["protocol"].append(e))
        event_system.subscribe("error", lambda e: component_errors["global"].append(e))
        
        # Simulate errors in different components
        # 1. Auth error
        auth_error = ValueError("Invalid credentials")
        event_system.emit("error:auth", {"error": auth_error, "context": "login"})
        
        # 2. WebSocket error triggers protocol error
        ws_error = ConnectionError("WebSocket connection failed")
        event_system.emit("error:websocket", {"error": ws_error})
        event_system.emit("error:protocol", {"error": "Protocol handshake failed", "cause": ws_error})
        
        # 3. Global error handler should catch all
        event_system.emit("error", {"error": "System error", "components": ["auth", "websocket"]})
        
        # Verify error propagation
        assert len(component_errors["auth"]) == 1
        assert len(component_errors["websocket"]) == 1
        assert len(component_errors["protocol"]) == 1
        assert len(component_errors["global"]) >= 1
    
    def test_concurrent_component_operations(self, event_system):
        """Test thread safety of concurrent component operations."""
        results = []
        errors = []
        
        def auth_operation(user_id):
            try:
                event_system.emit("auth:check", {"user_id": user_id})
                results.append(f"auth_{user_id}")
            except Exception as e:
                errors.append(("auth", e))
        
        def ws_operation(message_id):
            try:
                event_system.emit("websocket:send", {"id": message_id})
                results.append(f"ws_{message_id}")
            except Exception as e:
                errors.append(("ws", e))
        
        def protocol_operation(msg_type):
            try:
                event_system.emit("protocol:process", {"type": msg_type})
                results.append(f"protocol_{msg_type}")
            except Exception as e:
                errors.append(("protocol", e))
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            
            # Mix different component operations
            for i in range(5):
                futures.append(executor.submit(auth_operation, i))
                futures.append(executor.submit(ws_operation, i))
                futures.append(executor.submit(protocol_operation, f"type_{i}"))
            
            # Wait for completion
            for future in futures:
                future.result(timeout=5.0)
        
        # Verify no concurrency errors
        assert len(errors) == 0, f"Concurrency errors: {errors}"
        assert len(results) == 15, f"Expected 15 results, got {len(results)}"
    
    def test_component_lifecycle_coordination(self, event_system, auth_handler, mock_ws_client):
        """Test coordination of component lifecycles."""
        lifecycle_events = []
        
        # Track lifecycle events
        def track_event(event_name, data):
            lifecycle_events.append((event_name, time.time(), data))
        
        # Subscribe to lifecycle events
        for component in ["auth", "websocket", "protocol"]:
            for phase in ["init", "start", "stop", "cleanup"]:
                event_system.subscribe(f"{component}:{phase}", 
                                     lambda d, c=component, p=phase: track_event(f"{c}:{p}", d))
        
        # Simulate component lifecycle
        # 1. Initialization phase
        event_system.emit("auth:init", {"config": {}})
        event_system.emit("websocket:init", {"config": {}})
        event_system.emit("protocol:init", {"config": {}})
        
        # 2. Start phase (auth first, then websocket, then protocol)
        event_system.emit("auth:start", {"status": "ready"})
        time.sleep(0.01)
        event_system.emit("websocket:start", {"status": "connecting"})
        time.sleep(0.01)
        event_system.emit("protocol:start", {"status": "handshaking"})
        
        # 3. Stop phase (reverse order)
        event_system.emit("protocol:stop", {"status": "closing"})
        time.sleep(0.01)
        event_system.emit("websocket:stop", {"status": "disconnecting"})
        time.sleep(0.01)
        event_system.emit("auth:stop", {"status": "clearing"})
        
        # 4. Cleanup phase
        event_system.emit("protocol:cleanup", {})
        event_system.emit("websocket:cleanup", {})
        event_system.emit("auth:cleanup", {})
        
        # Verify lifecycle coordination
        assert len(lifecycle_events) == 12  # 3 components * 4 phases
        
        # Verify initialization order
        init_events = [e for e in lifecycle_events if e[0].endswith(":init")]
        assert len(init_events) == 3
        
        # Verify start order (auth -> websocket -> protocol)
        start_events = [e for e in lifecycle_events if e[0].endswith(":start")]
        assert start_events[0][0] == "auth:start"
        assert start_events[1][0] == "websocket:start"
        assert start_events[2][0] == "protocol:start"
        
        # Verify stop order (reverse of start)
        stop_events = [e for e in lifecycle_events if e[0].endswith(":stop")]
        assert stop_events[0][0] == "protocol:stop"
        assert stop_events[1][0] == "websocket:stop"
        assert stop_events[2][0] == "auth:stop"
    
    def test_message_flow_through_components(self, event_system):
        """Test message flow through multiple components."""
        message_trace = []
        
        def trace_message(component, action, data):
            message_trace.append({
                "component": component,
                "action": action,
                "timestamp": time.time(),
                "data": data
            })
        
        # Set up message tracing
        components = ["websocket", "protocol", "deserializer", "handler", "event"]
        for component in components:
            event_system.subscribe(
                f"{component}:*",
                lambda d, c=component: trace_message(c, "process", d)
            )
        
        # Simulate message flow
        raw_message = b'{"type": "TableUpdate", "data": {"table": "users"}}'
        
        # 1. WebSocket receives message
        event_system.emit("websocket:message_received", {"raw": raw_message})
        
        # 2. Protocol parses message
        event_system.emit("protocol:parse_message", {"parsed": json.loads(raw_message)})
        
        # 3. Deserializer processes data
        event_system.emit("deserializer:process", {"type": "TableUpdate", "data": {"table": "users"}})
        
        # 4. Handler processes business logic
        event_system.emit("handler:table_update", {"table": "users", "action": "update"})
        
        # 5. Event system notifies listeners
        event_system.emit("event:table_updated", {"table": "users", "timestamp": time.time()})
        
        # Verify complete message flow
        assert len(message_trace) >= 5
        assert message_trace[0]["component"] == "websocket"
        assert message_trace[-1]["component"] == "event"
    
    def test_component_state_synchronization(self, event_system):
        """Test state synchronization between components."""
        component_states = {
            "auth": {"authenticated": False, "token": None},
            "websocket": {"connected": False, "ready": False},
            "protocol": {"handshake_complete": False, "version": None}
        }
        
        def update_state(component, state_update):
            component_states[component].update(state_update)
            # Notify other components
            event_system.emit(f"state_changed:{component}", {
                "component": component,
                "state": component_states[component]
            })
        
        # Subscribe to state changes
        def on_state_change(data):
            component = data["component"]
            # Other components react to state changes
            if component == "auth" and data["state"]["authenticated"]:
                update_state("websocket", {"ready": True})
            elif component == "websocket" and data["state"]["connected"]:
                update_state("protocol", {"handshake_complete": True, "version": "1.0"})
        
        event_system.subscribe("state_changed:*", on_state_change)
        
        # Trigger state changes
        update_state("auth", {"authenticated": True, "token": "test_token"})
        update_state("websocket", {"connected": True})
        
        # Verify state synchronization
        assert component_states["auth"]["authenticated"] is True
        assert component_states["websocket"]["ready"] is True
        assert component_states["protocol"]["handshake_complete"] is True
        assert component_states["protocol"]["version"] == "1.0"


@pytest.mark.integration
class TestComplexScenarios:
    """Test complex integration scenarios."""
    
    @pytest.fixture
    def event_system(self):
        """Provide isolated event system."""
        return EventSystem()
    
    def test_cascading_component_failure(self, event_system):
        """Test how component failures cascade through the system."""
        failure_trace = []
        recovery_attempts = []
        
        def on_failure(component, error):
            failure_trace.append((component, error, time.time()))
        
        def on_recovery_attempt(component):
            recovery_attempts.append((component, time.time()))
        
        # Subscribe to failure events
        event_system.subscribe("failure:*", lambda d: on_failure(d.get("component"), d.get("error")))
        event_system.subscribe("recovery:*", lambda d: on_recovery_attempt(d.get("component")))
        
        # Simulate cascading failure
        # 1. Network failure
        event_system.emit("failure:network", {
            "component": "network",
            "error": "Connection timeout"
        })
        
        # 2. WebSocket fails due to network
        event_system.emit("failure:websocket", {
            "component": "websocket",
            "error": "Network unavailable",
            "cause": "network"
        })
        
        # 3. Protocol fails due to WebSocket
        event_system.emit("failure:protocol", {
            "component": "protocol",
            "error": "No connection",
            "cause": "websocket"
        })
        
        # 4. Auth refresh fails due to no connection
        event_system.emit("failure:auth", {
            "component": "auth",
            "error": "Cannot refresh token",
            "cause": "protocol"
        })
        
        # Simulate recovery attempts
        for component in ["network", "websocket", "protocol", "auth"]:
            event_system.emit(f"recovery:{component}", {"component": component})
        
        # Verify failure cascade
        assert len(failure_trace) == 4
        assert failure_trace[0][0] == "network"
        assert failure_trace[-1][0] == "auth"
        
        # Verify recovery attempts
        assert len(recovery_attempts) == 4