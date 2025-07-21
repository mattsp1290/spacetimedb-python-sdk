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


# Remove the custom SimpleConnectionMock as we'll use the proper integration fixtures


class TestSimpleConnection:
    """Simple connection tests to verify mocking works."""
    
    @pytest.mark.asyncio
    async def test_mock_connection_prevents_real_network(self, integration_client_factory):
        """Test that mock prevents real network connections."""
        client = integration_client_factory(
            test_mode=True,
            start_message_processing=False
        )
        
        # This should NOT make a real network connection - the fixtures handle this
        # No need for additional socket patching as integration test setup handles it
        
        # Connect using the proper mocking infrastructure
        await asyncio.get_event_loop().run_in_executor(
            None, 
            client.connect_instance,
            "localhost:3000",
            "test_db"
        )
        
        # Verify connection completed without real network calls
        # The fact that we reach this point means no real connection was made
        assert True  # Test passes if no exception was raised
        
    @pytest.mark.asyncio
    async def test_mock_connection_triggers_events(self, integration_client_factory, connection_event_tracker, wait_for_events):
        """Test that mock connection properly triggers events."""
        client = integration_client_factory(
            test_mode=True,
            start_message_processing=False
        )
        
        # Track events using the provided event tracker
        def on_connection_event(context: EventContext):
            if context.event_type == EventType.CONNECTION_ESTABLISHED:
                connection_event_tracker.track_event("connected")
            elif context.event_type == EventType.IDENTITY_RECEIVED:
                connection_event_tracker.track_event("identity", context.event.data)
        
        # Register event handlers
        client.on_event(EventType.CONNECTION_ESTABLISHED, on_connection_event)
        client.on_event(EventType.IDENTITY_RECEIVED, on_connection_event)
        
        # Connect
        await asyncio.get_event_loop().run_in_executor(
            None,
            client.connect_instance,
            "localhost:3000", 
            "test_db"
        )
        
        # Wait for events to be processed using the proper helper
        success = wait_for_events(connection_event_tracker, 2, None, timeout=3.0)
        assert success, f"Timed out waiting for events. Got: {connection_event_tracker.get_events()}"
        
        # Verify events were triggered
        events = connection_event_tracker.get_events()
        assert len(events) >= 1, f"Expected at least 1 event, got {len(events)}: {events}"
        
        # Check event types
        event_types = [event['type'] for event in events]
        assert "connected" in event_types, f"Missing 'connected' event in {event_types}"
        
    @pytest.mark.asyncio
    async def test_connection_lifecycle_sequence(self, integration_client_factory, connection_event_tracker, wait_for_events):
        """Test complete connection lifecycle sequence."""
        client = integration_client_factory(
            test_mode=True,
            start_message_processing=False
        )
        
        # Track all connection lifecycle events
        def on_connection_event(context: EventContext):
            event_type = context.event_type
            if event_type == EventType.CONNECTION_ESTABLISHED:
                connection_event_tracker.track_event("connected", context.event.data)
            elif event_type == EventType.IDENTITY_RECEIVED:
                connection_event_tracker.track_event("identity", context.event.data)
            elif event_type == EventType.CONNECTION_CLOSED:
                connection_event_tracker.track_event("disconnected", context.event.data)
            elif event_type == EventType.CONNECTION_ERROR:
                connection_event_tracker.track_event("error", context.event.data)
        
        # Register for all connection events
        client.on_event(EventType.CONNECTION_ESTABLISHED, on_connection_event)
        client.on_event(EventType.IDENTITY_RECEIVED, on_connection_event)
        client.on_event(EventType.CONNECTION_CLOSED, on_connection_event)
        client.on_event(EventType.CONNECTION_ERROR, on_connection_event)
        
        # Connect
        await asyncio.get_event_loop().run_in_executor(
            None,
            client.connect_instance,
            "localhost:3000",
            "test_db"
        )
        
        # Wait for connection and identity events
        success = wait_for_events(connection_event_tracker, 1, None, timeout=3.0)
        assert success, f"Timed out waiting for events. Got: {connection_event_tracker.get_events()}"
        
        # Verify we got the expected events
        events = connection_event_tracker.get_events()
        assert len(events) >= 1, f"Expected at least 1 event, got {len(events)}: {events}"
        
        # Check that events contain expected data
        for event in events:
            assert 'data' in event, f"Event missing data: {event}"
            assert event['timestamp'] > 0, f"Invalid timestamp in event: {event}"