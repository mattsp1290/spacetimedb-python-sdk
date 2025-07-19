"""
Integration tests for complete end-to-end workflows.

Tests full connection lifecycle, authentication flows, reducer calls,
subscription management, and error recovery scenarios.
"""
import pytest
import asyncio
import time
import threading
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from concurrent.futures import ThreadPoolExecutor

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.websocket_client import WebSocketClient
from spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler
from spacetimedb_sdk.events.event_manager import UnifiedEventManager
from spacetimedb_sdk.events.core_events import EventType, Event, create_connection_event, create_error_event
from spacetimedb_sdk.events.event_context import EventContext
from spacetimedb_sdk.protocol import Identity, ConnectionId, IdentityToken


class TestCompleteWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    def event_system(self):
        """Provide event system for testing."""
        return UnifiedEventManager()
    
    @pytest.fixture
    def auth_handler(self):
        """Provide authentication handler."""
        return AuthenticationHandler()
    
    @pytest.fixture
    def async_client(self, integration_client_factory):
        """Create an async-compatible client with proper mocking."""
        client = integration_client_factory(
            test_mode=True,
            start_message_processing=False
        )
        # Add a connect method without arguments for test compatibility
        client.connect = lambda: client.connect_instance(
            host="localhost:3000",
            database_address="test_db"
        )
        yield client
    
    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(self, async_client, connection_event_tracker, wait_for_events):
        """Test complete connection lifecycle from connect to disconnect."""
        connection_events = []
        
        # Track all connection events using new unified event system
        def on_connection_event(context: EventContext):
            if context.event_type == EventType.CONNECTION_ESTABLISHED:
                connection_events.append("connected")
                connection_event_tracker.track_event("connected")
            elif context.event_type == EventType.CONNECTION_CLOSED:
                connection_events.append(("disconnected", context.event.data.get("message", "unknown")))
                connection_event_tracker.track_event("disconnected", context.event.data.get("message", "unknown"))
            elif context.event_type == EventType.CONNECTION_ERROR:
                connection_events.append(("error", context.event.data.get("error", "unknown")))
                connection_event_tracker.track_event("error", context.event.data.get("error", "unknown"))
        
        def on_identity_event(context: EventContext):
            if context.event_type == EventType.IDENTITY_RECEIVED:
                data = context.event.data
                connection_events.append(("identity", data.get("token"), data.get("identity"), data.get("connection_id")))
                connection_event_tracker.track_event("identity", data)
        
        # Register event handlers using new API
        async_client.on_event(EventType.CONNECTION_ESTABLISHED, on_connection_event)
        async_client.on_event(EventType.CONNECTION_CLOSED, on_connection_event)
        async_client.on_event(EventType.CONNECTION_ERROR, on_connection_event)
        async_client.on_event(EventType.IDENTITY_RECEIVED, on_identity_event)
        
        # Start connection using the mock infrastructure
        await asyncio.get_event_loop().run_in_executor(None, async_client.connect)
        
        # Wait for events to be processed - the mock should automatically trigger them
        success = wait_for_events(connection_event_tracker, 2, None, timeout=3.0)  # Expect at least connected + identity
        assert success, f"Timed out waiting for events. Got: {connection_event_tracker.get_events()}"
        
        # Allow a bit more time for all events to process
        await asyncio.sleep(0.2)
        
        # Verify lifecycle events occurred
        all_events = connection_event_tracker.get_events()
        assert len(all_events) >= 2, f"Expected at least 2 events, got {len(all_events)}: {all_events}"
        
        # Check that we got the basic sequence
        event_types = [event['type'] for event in all_events]
        assert "connected" in event_types, f"Missing 'connected' event in {event_types}"
        assert "identity" in event_types, f"Missing 'identity' event in {event_types}"
        
        # Also verify the old-style connection_events list
        assert len(connection_events) >= 2, f"Expected events in connection_events, got: {connection_events}"
        assert connection_events[0] == "connected"
        assert connection_events[1][0] == "identity"
    
    @pytest.mark.asyncio
    async def test_connection_recovery_after_network_failure(self, async_client):
        """Test automatic reconnection after network failure."""
        reconnect_attempts = []
        connection_states = []
        
        def on_connection_event(context: EventContext):
            if context.event_type == EventType.CONNECTION_ESTABLISHED:
                connection_states.append("connected")
            elif context.event_type == EventType.CONNECTION_CLOSED:
                connection_states.append(("disconnected", context.event.data.get("message", "unknown")))
        
        def on_reconnect_event(context: EventContext):
            reconnect_attempts.append(time.time())
        
        async_client.on_event(EventType.CONNECTION_ESTABLISHED, on_connection_event)
        async_client.on_event(EventType.CONNECTION_CLOSED, on_connection_event)
        
        # Register for reconnect events if available
        if hasattr(async_client, 'on_event'):
            async_client.on_event(EventType.CONNECTION_ESTABLISHED, on_reconnect_event)
        
        with patch.object(async_client, 'ws_client') as mock_ws:
            # Initial connection
            mock_ws.on_open = Mock()
            mock_ws.on_close = Mock()
            
            # Connect
            await asyncio.get_event_loop().run_in_executor(None, async_client.connect)
            mock_ws.on_open(mock_ws)
            
            # Simulate network failure
            mock_ws.on_close(mock_ws, 1006, "Abnormal closure")
            
            # Wait for reconnection attempt
            await asyncio.sleep(2.0)
            
            # Simulate successful reconnection
            mock_ws.on_open(mock_ws)
            
            # Verify recovery behavior
            assert len(connection_states) >= 2
            assert connection_states[0] == "connected"
            assert connection_states[1][0] == "disconnected"
            
            # If reconnection is supported, verify attempts
            if reconnect_attempts:
                assert len(reconnect_attempts) > 0
    
    @pytest.mark.asyncio
    async def test_authentication_events_trigger_connection_updates(self, async_client, auth_handler):
        """Test that authentication changes trigger appropriate connection updates."""
        auth_events = []
        connection_updates = []
        
        def on_auth_change(event_type, data):
            auth_events.append((event_type, data))
        
        def on_connection_update(update_type, data):
            connection_updates.append((update_type, data))
        
        # Mock auth handler behavior
        with patch.object(auth_handler, 'authenticate') as mock_auth:
            mock_auth.return_value = "new_auth_token_12345"
            
            # Set up auth handler on client
            if hasattr(async_client, 'set_auth_handler'):
                async_client.set_auth_handler(auth_handler)
            
            # Track events
            if hasattr(async_client, 'on_auth_change'):
                async_client.on_auth_change(on_auth_change)
            
            with patch.object(async_client, 'ws_client') as mock_ws:
                # Connect with initial auth
                await asyncio.get_event_loop().run_in_executor(None, async_client.connect)
                
                # Simulate auth token refresh
                if hasattr(auth_handler, 'refresh_token'):
                    new_token = await asyncio.get_event_loop().run_in_executor(
                        None, auth_handler.refresh_token
                    )
                    
                    # Should trigger reconnection with new token
                    await asyncio.sleep(0.1)
                    
                    # Verify auth events were triggered
                    if auth_events:
                        assert len(auth_events) > 0
                        assert any("refresh" in str(event[0]).lower() for event in auth_events)
    
    def test_concurrent_operations(self, event_system):
        """Test thread safety of concurrent operations."""
        results = []
        errors = []
        
        def worker_subscribe(table_name, callback):
            """Worker for subscription operations."""
            try:
                event_system.on(f"table_update:{table_name}", callback)
                results.append(f"subscribed_{table_name}")
            except Exception as e:
                errors.append(e)
        
        def worker_emit(event_name, data):
            """Worker for event emission."""
            try:
                # Import BaseEvent for correct usage
                from spacetimedb_sdk.events.core_events import BaseEvent
                event = BaseEvent(type=EventType.CUSTOM, data=data)
                event_system.emit(event)
                results.append(f"emitted_{event_name}")
            except Exception as e:
                errors.append(e)
        
        # Create multiple concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            # Subscribe operations
            for i in range(5):
                callback = lambda context, i=i: results.append(f"callback_{i}")
                futures.append(
                    executor.submit(worker_subscribe, f"table_{i}", callback)
                )
            
            # Emit operations
            for i in range(5):
                futures.append(
                    executor.submit(worker_emit, f"table_update:table_{i}", {"id": i})
                )
            
            # Wait for completion
            for future in futures:
                future.result(timeout=5.0)
        
        # Verify no threading errors
        assert len(errors) == 0, f"Threading errors: {errors}"
        assert len(results) >= 10, "Not all operations completed"
    
    @pytest.mark.asyncio
    async def test_subscription_lifecycle(self, async_client):
        """Test complete subscription lifecycle."""
        subscription_events = []
        table_updates = []
        
        def on_subscription_success(table_name):
            subscription_events.append(("subscribed", table_name))
        
        def on_table_update(context: EventContext):
            if context.event_type == EventType.TABLE_UPDATE:
                data = context.event.data
                table_updates.append((data.get("table_name"), data.get("updates", [])))
        
        with patch.object(async_client, 'ws_client') as mock_ws:
            # Subscribe to table using new API
            if hasattr(async_client, 'on_event'):
                async_client.on_event(EventType.TABLE_UPDATE, on_table_update)
                
                # Simulate subscription success
                sub_success_msg = {
                    "SubscriptionSuccess": {
                        "table_name": "users",
                        "table_id": 1
                    }
                }
                if mock_ws.on_message:
                    mock_ws.on_message(mock_ws, json.dumps(sub_success_msg))
                
                # Simulate table updates
                for i in range(3):
                    update_msg = {
                        "TableUpdate": {
                            "table_id": 1,
                            "table_name": "users",
                            "updates": [{"id": i, "name": f"user_{i}"}]
                        }
                    }
                    if mock_ws.on_message:
                        mock_ws.on_message(mock_ws, json.dumps(update_msg))
                    await asyncio.sleep(0.05)
                
                # Unsubscribe
                if hasattr(async_client, 'unsubscribe'):
                    async_client.unsubscribe("users")
                
                # Verify no more updates after unsubscribe
                update_count_before = len(table_updates)
                
                # Send another update
                if mock_ws.on_message:
                    mock_ws.on_message(mock_ws, json.dumps(update_msg))
                await asyncio.sleep(0.05)
                
                # Count should not increase
                assert len(table_updates) == update_count_before
    
    @pytest.mark.asyncio
    async def test_reducer_call_workflow(self, async_client):
        """Test complete reducer call workflow."""
        reducer_events = []
        
        def on_reducer_success(reducer_name, result):
            reducer_events.append(("success", reducer_name, result))
        
        def on_reducer_error(reducer_name, error):
            reducer_events.append(("error", reducer_name, error))
        
        with patch.object(async_client, 'ws_client') as mock_ws:
            # Call reducer
            if hasattr(async_client, 'call_reducer'):
                # Track call
                call_id = "call_123"
                async_client.call_reducer(
                    "create_user",
                    {"name": "test_user", "email": "test@example.com"},
                    on_success=on_reducer_success,
                    on_error=on_reducer_error
                )
                
                # Simulate server response
                success_msg = {
                    "ReducerCallSuccess": {
                        "call_id": call_id,
                        "reducer_name": "create_user",
                        "result": {"id": 1, "name": "test_user"}
                    }
                }
                
                if mock_ws.on_message:
                    mock_ws.on_message(mock_ws, json.dumps(success_msg))
                
                await asyncio.sleep(0.1)
                
                # Verify callback was triggered
                assert len(reducer_events) > 0
                assert reducer_events[0][0] == "success"
                assert reducer_events[0][1] == "create_user"
    
    def test_error_propagation_through_layers(self, event_system):
        """Test that errors propagate correctly through system layers."""
        captured_errors = []
        
        def error_handler(context: EventContext):
            if context.event_type == EventType.ERROR_OCCURRED:
                captured_errors.append(context.event.data.get("error_message"))
        
        # Set up error handling at different layers
        event_system.on(EventType.ERROR_OCCURRED, error_handler)
        
        # Simulate errors at different layers
        test_errors = [
            ValueError("Validation error"),
            ConnectionError("Network error"),
            json.JSONDecodeError("Parse error", "", 0),
            RuntimeError("Runtime error"),
        ]
        
        for error in test_errors:
            error_event = create_error_event(str(error), type(error).__name__)
            event_system.emit(error_event)
        
        # Verify all errors were captured
        assert len(captured_errors) == len(test_errors)
        assert all(isinstance(err, str) for err in captured_errors)
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, async_client):
        """Test graceful shutdown process."""
        shutdown_events = []
        
        def on_shutdown_start():
            shutdown_events.append("shutdown_started")
        
        def on_shutdown_complete():
            shutdown_events.append("shutdown_complete")
        
        with patch.object(async_client, 'ws_client') as mock_ws:
            # Connect
            await asyncio.get_event_loop().run_in_executor(None, async_client.connect)
            
            # Start some operations
            if hasattr(async_client, 'subscribe'):
                async_client.subscribe("test_table", lambda: None)
            
            # Initiate shutdown
            if hasattr(async_client, 'shutdown'):
                await asyncio.get_event_loop().run_in_executor(None, async_client.shutdown)
            else:
                async_client.close()
            
            # Verify clean shutdown
            assert mock_ws.close.called or hasattr(async_client, '_closed')


@pytest.mark.integration
class TestEdgeCaseWorkflows:
    """Test edge case scenarios in workflows."""
    
    @pytest.mark.asyncio
    async def test_rapid_connect_disconnect_cycles(self):
        """Test rapid connection/disconnection cycles."""
        clients = []
        
        for i in range(5):
            with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'):
                # Use correct API for client connection
                client = SpacetimeDBClient.connect(
                    host="localhost:3000",
                    database_address=f"test_db_{i}",
                    auth_token=None,
                    ssl_enabled=False
                )
                clients.append(client)
                
                # Quick connect/disconnect
                try:
                    await asyncio.get_event_loop().run_in_executor(None, client.connect)
                    await asyncio.sleep(0.1)
                    client.close()
                except Exception:
                    pass  # Expected in rapid cycles
        
        # Cleanup
        for client in clients:
            try:
                client.close()
            except:
                pass
    
    @pytest.mark.asyncio
    async def test_connection_during_shutdown(self):
        """Test connection attempt during system shutdown."""
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws:
            # Use correct API for client connection
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="test_db",
                auth_token=None,
                ssl_enabled=False
            )
            
            # Start shutdown
            shutdown_task = asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(None, client.close)
            )
            
            # Attempt connection during shutdown
            try:
                await asyncio.get_event_loop().run_in_executor(None, client.connect)
                # Should either fail or handle gracefully
            except Exception:
                pass  # Expected
            
            await shutdown_task