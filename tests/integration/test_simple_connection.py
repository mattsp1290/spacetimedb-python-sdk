"""
Simple integration test for connection mocking infrastructure.

This is a simplified test to verify that the connection mocking
prevents real network connections while properly triggering events.
"""
import pytest
import asyncio
import time
import json
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.events.core_events import EventType, Event
from spacetimedb_sdk.events.event_context import EventContext


class SimpleConnectionMock:
    """Simple mock that prevents real connections and simulates events."""
    
    def __init__(self):
        self.events_triggered = []
        self.connected = False
        
    def create_mock_client(self, **kwargs):
        """Create a client with mocked WebSocket that triggers events."""
        # Ensure test mode and disable processing
        kwargs.setdefault('test_mode', True)
        kwargs.setdefault('start_message_processing', False)
        
        client = SpacetimeDBClient(**kwargs)
        
        # Mock the WebSocket client creation to prevent real connections
        original_ws_client = None
        
        def mock_connect_instance(host, database_address, **connect_kwargs):
            """Mock connection that triggers events instead of real connection."""
            self.events_triggered.append("connect_called")
            
            # Simulate connection established
            self._trigger_connection_established(client)
            
            # Simulate identity token received
            threading.Thread(
                target=lambda: self._trigger_identity_received(client),
                daemon=True
            ).start()
            
            self.connected = True
            return None
            
        # Replace the connect_instance method
        client.connect_instance = mock_connect_instance
        
        return client
        
    def _trigger_connection_established(self, client):
        """Trigger connection established event."""
        if hasattr(client, '_event_emitter'):
            event = Event(
                type=EventType.CONNECTION_ESTABLISHED,
                data={"timestamp": time.time()},
                timestamp=time.time()
            )
            client._event_emitter.emit(event)
            self.events_triggered.append("connection_established")
            
    def _trigger_identity_received(self, client):
        """Trigger identity received event after a short delay."""
        time.sleep(0.05)  # Small delay to simulate network
        
        if hasattr(client, '_event_emitter'):
            event = Event(
                type=EventType.IDENTITY_RECEIVED,
                data={
                    "token": "mock_token_12345",
                    "identity": "a" * 64,
                    "connection_id": "b" * 32,
                    "timestamp": time.time()
                },
                timestamp=time.time()
            )
            client._event_emitter.emit(event)
            self.events_triggered.append("identity_received")


@pytest.fixture
def simple_mock():
    """Provide simple connection mock."""
    return SimpleConnectionMock()


@pytest.fixture
def connection_events():
    """Track connection events."""
    events = []
    
    def event_handler(context: EventContext):
        events.append({
            'type': context.event_type,
            'data': context.event.data,
            'timestamp': context.event.timestamp
        })
        
    yield events, event_handler
    events.clear()


class TestSimpleConnection:
    """Simple connection tests to verify mocking works."""
    
    @pytest.mark.asyncio
    async def test_mock_connection_prevents_real_network(self, simple_mock):
        """Test that mock prevents real network connections."""
        client = simple_mock.create_mock_client()
        
        # This should NOT make a real network connection
        with patch('socket.socket') as mock_socket:
            mock_socket.side_effect = AssertionError("Real network connection attempted!")
            
            # Connect using mock
            await asyncio.get_event_loop().run_in_executor(
                None, 
                client.connect_instance,
                "localhost:3000",
                "test_db"
            )
            
            # Verify no real socket was created
            mock_socket.assert_not_called()
            
        # Verify mock connection worked
        assert simple_mock.connected
        assert "connect_called" in simple_mock.events_triggered
        
    @pytest.mark.asyncio
    async def test_mock_connection_triggers_events(self, simple_mock, connection_events):
        """Test that mock connection properly triggers events."""
        events, event_handler = connection_events
        
        client = simple_mock.create_mock_client()
        
        # Register event handler
        client.on_event(EventType.CONNECTION_ESTABLISHED, event_handler)
        client.on_event(EventType.IDENTITY_RECEIVED, event_handler)
        
        # Connect
        await asyncio.get_event_loop().run_in_executor(
            None,
            client.connect_instance,
            "localhost:3000", 
            "test_db"
        )
        
        # Wait for events to be processed
        for _ in range(10):  # Wait up to 1 second
            if len(events) >= 2:
                break
            await asyncio.sleep(0.1)
            
        # Verify events were triggered
        assert len(events) >= 1, f"Expected at least 1 event, got {len(events)}: {events}"
        
        # Check event types
        event_types = [event['type'] for event in events]
        assert EventType.CONNECTION_ESTABLISHED in event_types, f"Missing CONNECTION_ESTABLISHED in {event_types}"
        
        # Verify mock events were also triggered
        assert "connection_established" in simple_mock.events_triggered
        
    @pytest.mark.asyncio
    async def test_connection_lifecycle_sequence(self, simple_mock, connection_events):
        """Test complete connection lifecycle sequence."""
        events, event_handler = connection_events
        
        client = simple_mock.create_mock_client()
        
        # Register for all connection events
        client.on_event(EventType.CONNECTION_ESTABLISHED, event_handler)
        client.on_event(EventType.IDENTITY_RECEIVED, event_handler)
        client.on_event(EventType.CONNECTION_CLOSED, event_handler)
        client.on_event(EventType.CONNECTION_ERROR, event_handler)
        
        # Connect
        await asyncio.get_event_loop().run_in_executor(
            None,
            client.connect_instance,
            "localhost:3000",
            "test_db"
        )
        
        # Wait for connection and identity events
        for _ in range(20):  # Wait up to 2 seconds
            if len(events) >= 2:
                break
            await asyncio.sleep(0.1)
            
        # Verify we got the expected events
        assert len(events) >= 1, f"Expected at least 1 event, got {len(events)}: {events}"
        
        # Check that events contain expected data
        for event in events:
            assert 'timestamp' in event['data'], f"Event missing timestamp: {event}"
            assert event['timestamp'] > 0, f"Invalid timestamp in event: {event}"
            
        # Verify the mock tracked events correctly
        assert len(simple_mock.events_triggered) >= 2, f"Mock should have tracked events: {simple_mock.events_triggered}"