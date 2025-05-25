"""
Test Advanced Event System for SpacetimeDB Python SDK.

Tests the TypeScript SDK-compatible advanced event system with:
- EventContext with rich metadata and operations
- Enhanced ReducerEvent with full information
- EventEmitter with sync/async handlers
- Event filtering and transformation
- Event history and metrics
"""

import asyncio
import unittest
import time
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

from spacetimedb_sdk.event_system import (
    EventEmitter,
    EventContext,
    EventType,
    Event,
    EventMetadata,
    ReducerEvent,
    TableEvent,
    create_event,
    create_reducer_event,
    create_table_event,
    global_event_bus
)
from spacetimedb_sdk.protocol import Identity, ConnectionId
from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient


class TestEventMetadata(unittest.TestCase):
    """Test EventMetadata functionality."""
    
    def test_metadata_creation(self):
        """Test metadata creation with defaults."""
        metadata = EventMetadata()
        
        self.assertIsInstance(metadata.event_id, str)
        self.assertIsInstance(metadata.timestamp, float)
        self.assertEqual(metadata.source, "system")
        self.assertIsNone(metadata.correlation_id)
        self.assertIsNone(metadata.causation_id)
        self.assertEqual(metadata.user_metadata, {})
    
    def test_datetime_property(self):
        """Test datetime conversion."""
        metadata = EventMetadata()
        dt = metadata.datetime
        
        from datetime import datetime
        self.assertIsInstance(dt, datetime)
    
    def test_custom_metadata(self):
        """Test custom metadata fields."""
        metadata = EventMetadata(
            source="test",
            correlation_id="corr-123",
            user_metadata={"custom": "value"}
        )
        
        self.assertEqual(metadata.source, "test")
        self.assertEqual(metadata.correlation_id, "corr-123")
        self.assertEqual(metadata.user_metadata["custom"], "value")


class TestEventTypes(unittest.TestCase):
    """Test Event and specialized event types."""
    
    def test_basic_event_creation(self):
        """Test basic event creation."""
        event = Event(
            type=EventType.CONNECTION_ESTABLISHED,
            data={"host": "localhost", "port": 3000}
        )
        
        self.assertEqual(event.type, EventType.CONNECTION_ESTABLISHED)
        self.assertEqual(event.data["host"], "localhost")
        self.assertIsInstance(event.metadata, EventMetadata)
    
    def test_event_with_metadata(self):
        """Test event with metadata updates."""
        event = Event(type=EventType.CUSTOM, data={})
        
        # Update metadata
        new_event = event.with_metadata(
            source="test_source",
            custom_field="custom_value"
        )
        
        self.assertEqual(new_event.metadata.source, "test_source")
        self.assertEqual(new_event.metadata.user_metadata["custom_field"], "custom_value")
        
        # Original event unchanged
        self.assertEqual(event.metadata.source, "system")
    
    def test_reducer_event(self):
        """Test ReducerEvent creation and properties."""
        event = ReducerEvent(
            type=EventType.REDUCER_SUCCESS,
            reducer_name="create_user",
            args={"name": "Alice", "email": "alice@example.com"},
            status="success",
            energy_used=100,
            execution_duration_nanos=1_000_000
        )
        
        self.assertEqual(event.reducer_name, "create_user")
        self.assertTrue(event.is_success)
        self.assertFalse(event.is_error)
        self.assertEqual(event.execution_time_ms, 1.0)
        
        # Data should be populated in __post_init__
        self.assertEqual(event.data["reducer_name"], "create_user")
    
    def test_table_event(self):
        """Test TableEvent creation."""
        reducer_event = create_reducer_event("create_user", "success")
        
        event = TableEvent(
            type=EventType.TABLE_ROW_INSERT,
            table_name="users",
            operation="insert",
            row_data={"id": 1, "name": "Alice"},
            reducer_event=reducer_event
        )
        
        self.assertEqual(event.table_name, "users")
        self.assertEqual(event.operation, "insert")
        self.assertEqual(event.row_data["name"], "Alice")
        self.assertEqual(event.data["table_name"], "users")


class TestEventContext(unittest.TestCase):
    """Test EventContext functionality."""
    
    def test_context_creation(self):
        """Test event context creation."""
        event = create_event(EventType.CUSTOM, {"test": "data"})
        context = EventContext(event, "test_component")
        
        self.assertEqual(context.event, event)
        self.assertEqual(context.source_component, "test_component")
        self.assertFalse(context.propagation_stopped)
        self.assertFalse(context.default_prevented)
        self.assertFalse(context.is_handled)
    
    def test_propagation_control(self):
        """Test propagation control."""
        event = create_event(EventType.CUSTOM, {})
        context = EventContext(event)
        
        # Stop propagation
        context.stop_propagation()
        self.assertTrue(context.propagation_stopped)
        
        # Prevent default
        context.prevent_default()
        self.assertTrue(context.default_prevented)
    
    def test_handler_tracking(self):
        """Test handler tracking."""
        event = create_event(EventType.CUSTOM, {})
        context = EventContext(event)
        
        # Mark as handled
        context.mark_handled("handler1")
        self.assertTrue(context.is_handled)
        self.assertIn("handler1", context.handlers)
        
        context.mark_handled("handler2")
        self.assertEqual(len(context.handlers), 2)
    
    def test_response_data(self):
        """Test response data management."""
        event = create_event(EventType.CUSTOM, {})
        context = EventContext(event)
        
        # Set response data
        context.set_response("result", "success")
        context.set_response("count", 42)
        
        self.assertEqual(context.get_response("result"), "success")
        self.assertEqual(context.get_response("count"), 42)
        self.assertIsNone(context.get_response("missing"))
        
        # Get all response data
        response_data = context.response_data
        self.assertEqual(response_data["result"], "success")
        self.assertEqual(response_data["count"], 42)
    
    def test_triggered_events(self):
        """Test event triggering from context."""
        event = create_event(EventType.CUSTOM, {})
        context = EventContext(event)
        
        # Trigger new events
        child_event1 = create_event(EventType.CUSTOM, {"child": 1})
        child_event2 = create_event(EventType.CUSTOM, {"child": 2})
        
        context.trigger_event(child_event1)
        context.trigger_event(child_event2)
        
        triggered = context.triggered_events
        self.assertEqual(len(triggered), 2)
        
        # Check causation chain
        self.assertEqual(child_event1.metadata.causation_id, context.event_id)
        self.assertEqual(child_event1.metadata.correlation_id, context.event_id)
    
    def test_timing(self):
        """Test context timing."""
        event = create_event(EventType.CUSTOM, {})
        context = EventContext(event)
        
        # Small delay
        time.sleep(0.01)
        
        # Check elapsed time
        self.assertGreater(context.elapsed_time, 0)
        
        # Complete context
        context.complete()
        elapsed1 = context.elapsed_time
        
        # Elapsed time should be fixed after completion
        time.sleep(0.01)
        elapsed2 = context.elapsed_time
        self.assertEqual(elapsed1, elapsed2)


class TestEventEmitter(unittest.TestCase):
    """Test EventEmitter functionality."""
    
    def setUp(self):
        """Set up test emitter."""
        self.emitter = EventEmitter(name="test", enable_async=False)
        self.events_handled = []
    
    def test_basic_event_handling(self):
        """Test basic event emission and handling."""
        def handler(ctx: EventContext):
            self.events_handled.append(ctx.event)
        
        # Register handler
        handler_id = self.emitter.on(EventType.CUSTOM, handler)
        self.assertIsInstance(handler_id, str)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {"test": "data"})
        context = self.emitter.emit(event)
        
        # Check handling
        self.assertEqual(len(self.events_handled), 1)
        self.assertEqual(self.events_handled[0], event)
        self.assertTrue(context.is_handled)
    
    def test_handler_priority(self):
        """Test handler execution priority."""
        order = []
        
        def handler1(ctx):
            order.append("handler1")
        
        def handler2(ctx):
            order.append("handler2")
        
        def handler3(ctx):
            order.append("handler3")
        
        # Register with different priorities
        self.emitter.on(EventType.CUSTOM, handler2, priority=5)
        self.emitter.on(EventType.CUSTOM, handler3, priority=1)
        self.emitter.on(EventType.CUSTOM, handler1, priority=10)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {})
        self.emitter.emit(event)
        
        # Check order (higher priority first)
        self.assertEqual(order, ["handler1", "handler2", "handler3"])
    
    def test_wildcard_handlers(self):
        """Test wildcard handlers that catch all events."""
        caught_events = []
        
        def wildcard_handler(ctx):
            caught_events.append(ctx.event_type)
        
        # Register wildcard handler
        self.emitter.on("*", wildcard_handler)
        
        # Emit different event types
        self.emitter.emit(create_event(EventType.CUSTOM, {}))
        self.emitter.emit(create_event(EventType.CONNECTION_ESTABLISHED, {}))
        self.emitter.emit(create_event(EventType.TABLE_ROW_INSERT, {}))
        
        # Should catch all
        self.assertEqual(len(caught_events), 3)
        self.assertIn(EventType.CUSTOM, caught_events)
        self.assertIn(EventType.CONNECTION_ESTABLISHED, caught_events)
        self.assertIn(EventType.TABLE_ROW_INSERT, caught_events)
    
    def test_once_handler(self):
        """Test one-time event handlers."""
        call_count = 0
        
        def once_handler(ctx):
            nonlocal call_count
            call_count += 1
        
        # Register once handler
        self.emitter.once(EventType.CUSTOM, once_handler)
        
        # Emit multiple times
        event = create_event(EventType.CUSTOM, {})
        self.emitter.emit(event)
        self.emitter.emit(event)
        self.emitter.emit(event)
        
        # Should only be called once
        self.assertEqual(call_count, 1)
    
    def test_handler_removal(self):
        """Test handler removal."""
        handled = []
        
        def handler(ctx):
            handled.append("handled")
        
        # Register and remove
        handler_id = self.emitter.on(EventType.CUSTOM, handler)
        removed = self.emitter.off(EventType.CUSTOM, handler_id)
        self.assertTrue(removed)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {})
        self.emitter.emit(event)
        
        # Should not be handled
        self.assertEqual(len(handled), 0)
    
    def test_event_filters(self):
        """Test event filtering."""
        handled = []
        
        def handler(ctx):
            handled.append(ctx.event)
        
        # Only allow events with specific data
        def filter_func(event):
            return event.data.get("allowed", False)
        
        self.emitter.add_filter(filter_func)
        self.emitter.on(EventType.CUSTOM, handler)
        
        # Emit filtered event
        event1 = create_event(EventType.CUSTOM, {"allowed": False})
        self.emitter.emit(event1)
        self.assertEqual(len(handled), 0)
        
        # Emit allowed event
        event2 = create_event(EventType.CUSTOM, {"allowed": True})
        self.emitter.emit(event2)
        self.assertEqual(len(handled), 1)
    
    def test_event_transformers(self):
        """Test event transformation."""
        handled = []
        
        def handler(ctx):
            handled.append(ctx.event.data)
        
        # Transform events
        def transformer(event):
            event.data["transformed"] = True
            return event
        
        self.emitter.add_transformer(transformer)
        self.emitter.on(EventType.CUSTOM, handler)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {"original": True})
        self.emitter.emit(event)
        
        # Check transformation
        self.assertEqual(len(handled), 1)
        self.assertTrue(handled[0]["original"])
        self.assertTrue(handled[0]["transformed"])
    
    def test_error_isolation(self):
        """Test error isolation in handlers."""
        handled = []
        
        def good_handler(ctx):
            handled.append("good")
        
        def bad_handler(ctx):
            raise RuntimeError("Test error")
        
        def another_good_handler(ctx):
            handled.append("another_good")
        
        # Register handlers
        self.emitter.on(EventType.CUSTOM, good_handler)
        self.emitter.on(EventType.CUSTOM, bad_handler)
        self.emitter.on(EventType.CUSTOM, another_good_handler)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {})
        context = self.emitter.emit(event)
        
        # Good handlers should still run
        self.assertEqual(handled, ["good", "another_good"])
        self.assertIsNotNone(context.get_response("error"))
    
    def test_propagation_stopping(self):
        """Test stopping event propagation."""
        handled = []
        
        def handler1(ctx):
            handled.append("handler1")
            ctx.stop_propagation()
        
        def handler2(ctx):
            handled.append("handler2")
        
        # Register handlers
        self.emitter.on(EventType.CUSTOM, handler1, priority=10)
        self.emitter.on(EventType.CUSTOM, handler2, priority=5)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {})
        self.emitter.emit(event)
        
        # Only first handler should run
        self.assertEqual(handled, ["handler1"])
    
    def test_event_history(self):
        """Test event history tracking."""
        # Emit various events
        self.emitter.emit(create_event(EventType.CUSTOM, {"id": 1}))
        self.emitter.emit(create_event(EventType.CONNECTION_ESTABLISHED, {}))
        self.emitter.emit(create_event(EventType.CUSTOM, {"id": 2}))
        
        # Get all history
        history = self.emitter.get_history()
        self.assertEqual(len(history), 3)
        
        # Get filtered history
        custom_history = self.emitter.get_history(EventType.CUSTOM)
        self.assertEqual(len(custom_history), 2)
        
        # Get limited history
        limited_history = self.emitter.get_history(limit=1)
        self.assertEqual(len(limited_history), 1)
        
        # Clear history
        self.emitter.clear_history()
        self.assertEqual(len(self.emitter.get_history()), 0)
    
    def test_metrics(self):
        """Test event metrics."""
        def handler(ctx):
            pass
        
        def error_handler(ctx):
            raise RuntimeError("Test")
        
        # Register handlers
        self.emitter.on(EventType.CUSTOM, handler)
        self.emitter.on(EventType.CUSTOM, error_handler)
        
        # Emit events
        for _ in range(5):
            self.emitter.emit(create_event(EventType.CUSTOM, {}))
        
        # Check metrics
        metrics = self.emitter.get_metrics()
        self.assertEqual(metrics['events_emitted'], 5)
        self.assertEqual(metrics['events_handled'], 5)  # handler called 5 times
        self.assertEqual(metrics['errors_caught'], 5)   # error_handler failed 5 times
        
        # Reset metrics
        self.emitter.reset_metrics()
        metrics = self.emitter.get_metrics()
        self.assertEqual(metrics['events_emitted'], 0)


class TestAsyncEventHandling(unittest.TestCase):
    """Test async event handling capabilities."""
    
    def setUp(self):
        """Set up async test emitter."""
        self.emitter = EventEmitter(name="async_test", enable_async=True)
        self.handled = []
    
    def tearDown(self):
        """Clean up async emitter."""
        self.emitter.shutdown()
    
    def test_async_handler(self):
        """Test async event handler."""
        async def async_handler(ctx):
            await asyncio.sleep(0.01)
            self.handled.append("async_handled")
        
        # Register async handler
        self.emitter.on(EventType.CUSTOM, async_handler)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {})
        self.emitter.emit(event)
        
        # Wait for async handler
        time.sleep(0.05)
        
        # Check handled
        self.assertEqual(self.handled, ["async_handled"])
    
    def test_mixed_sync_async_handlers(self):
        """Test mixing sync and async handlers."""
        order = []
        
        def sync_handler(ctx):
            order.append("sync")
        
        async def async_handler(ctx):
            await asyncio.sleep(0.01)
            order.append("async")
        
        # Register both
        self.emitter.on(EventType.CUSTOM, sync_handler)
        self.emitter.on(EventType.CUSTOM, async_handler)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {})
        self.emitter.emit(event)
        
        # Sync should complete immediately
        self.assertIn("sync", order)
        
        # Wait for async
        time.sleep(0.05)
        self.assertIn("async", order)


class TestGlobalEventBus(unittest.TestCase):
    """Test global event bus functionality."""
    
    def test_namespace_isolation(self):
        """Test namespace isolation in global bus."""
        handled_default = []
        handled_custom = []
        
        def default_handler(ctx):
            handled_default.append(ctx.event)
        
        def custom_handler(ctx):
            handled_custom.append(ctx.event)
        
        # Register in different namespaces
        global_event_bus.on(EventType.CUSTOM, default_handler, namespace="default")
        global_event_bus.on(EventType.CUSTOM, custom_handler, namespace="custom")
        
        # Emit to different namespaces
        event1 = create_event(EventType.CUSTOM, {"id": 1})
        event2 = create_event(EventType.CUSTOM, {"id": 2})
        
        global_event_bus.emit(event1, namespace="default")
        global_event_bus.emit(event2, namespace="custom")
        
        # Check isolation
        self.assertEqual(len(handled_default), 1)
        self.assertEqual(handled_default[0].data["id"], 1)
        
        self.assertEqual(len(handled_custom), 1)
        self.assertEqual(handled_custom[0].data["id"], 2)
    
    def test_emitter_reuse(self):
        """Test emitter reuse across namespaces."""
        emitter1 = global_event_bus.get_emitter("test_namespace")
        emitter2 = global_event_bus.get_emitter("test_namespace")
        
        # Should be same instance
        self.assertIs(emitter1, emitter2)


class TestClientIntegration(unittest.TestCase):
    """Test integration with ModernSpacetimeDBClient."""
    
    @patch('spacetimedb_sdk.modern_client.ModernWebSocketClient')
    def setUp(self, mock_ws_client_class):
        """Set up test client."""
        self.mock_ws = Mock()
        mock_ws_client_class.return_value = self.mock_ws
        
        self.client = ModernSpacetimeDBClient(
            start_message_processing=False  # Disable for testing
        )
        
        self.handled_events = []
    
    def test_event_emitter_access(self):
        """Test accessing event emitter from client."""
        emitter = self.client.event_emitter
        self.assertIsInstance(emitter, EventEmitter)
    
    def test_client_event_registration(self):
        """Test registering events through client."""
        def handler(ctx):
            self.handled_events.append(ctx.event)
        
        # Register handler
        handler_id = self.client.on_event(EventType.CUSTOM, handler)
        self.assertIsInstance(handler_id, str)
        
        # Emit event
        event = create_event(EventType.CUSTOM, {"test": True})
        context = self.client.emit_event(event)
        
        # Check handled
        self.assertEqual(len(self.handled_events), 1)
        self.assertTrue(context.is_handled)
        
        # Remove handler
        removed = self.client.off_event(EventType.CUSTOM, handler_id)
        self.assertTrue(removed)
    
    def test_event_history_access(self):
        """Test accessing event history through client."""
        # Emit some events
        self.client.emit_event(create_event(EventType.CUSTOM, {"id": 1}))
        self.client.emit_event(create_event(EventType.CUSTOM, {"id": 2}))
        
        # Get history
        history = self.client.get_event_history(EventType.CUSTOM)
        self.assertEqual(len(history), 2)
    
    def test_event_metrics_access(self):
        """Test accessing event metrics through client."""
        # Emit event
        self.client.emit_event(create_event(EventType.CUSTOM, {}))
        
        # Get metrics
        metrics = self.client.get_event_metrics()
        self.assertGreater(metrics['events_emitted'], 0)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""
    
    def test_create_event(self):
        """Test create_event helper."""
        event = create_event(
            EventType.CUSTOM,
            {"key": "value"},
            source="test"
        )
        
        self.assertEqual(event.type, EventType.CUSTOM)
        self.assertEqual(event.data["key"], "value")
        self.assertEqual(event.metadata.source, "test")
    
    def test_create_reducer_event(self):
        """Test create_reducer_event helper."""
        event = create_reducer_event(
            "test_reducer",
            status="success",
            args={"arg": "value"}
        )
        
        self.assertIsInstance(event, ReducerEvent)
        self.assertEqual(event.reducer_name, "test_reducer")
        self.assertEqual(event.status, "success")
        self.assertEqual(event.args["arg"], "value")
    
    def test_create_table_event(self):
        """Test create_table_event helper."""
        event = create_table_event(
            "users",
            "insert",
            {"id": 1, "name": "Alice"}
        )
        
        self.assertIsInstance(event, TableEvent)
        self.assertEqual(event.table_name, "users")
        self.assertEqual(event.operation, "insert")
        self.assertEqual(event.type, EventType.TABLE_ROW_INSERT)


if __name__ == '__main__':
    unittest.main() 