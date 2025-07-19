"""
Unit tests for subscription data flow fixes in SpacetimeDB Python SDK.

This test module validates the fixes implemented to address the subscription
data flow issues identified in the bug report.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import unittest
import time
from unittest.mock import Mock, patch
from typing import Any, Dict

# Import the modules we're testing
from spacetimedb_sdk.serialization import (
    _safe_extract, _get_message_type, _handle_database_update,
    _handle_subscription_update, serialize_for_client
)
from spacetimedb_sdk.subscription_manager import (
    SubscriptionManager, SubscriptionState, SubscriptionInfo
)
from spacetimedb_sdk.event_manager import (
    SDKEventManager, EventType, EventData
)


class TestSafeExtract(unittest.TestCase):
    """Test the _safe_extract function for object/dict compatibility."""
    
    def test_safe_extract_from_dict(self):
        """Test extracting from dictionary."""
        data = {'key': 'value', 'tables': ['table1', 'table2']}
        
        self.assertEqual(_safe_extract(data, 'key'), 'value')
        self.assertEqual(_safe_extract(data, 'tables'), ['table1', 'table2'])
        self.assertEqual(_safe_extract(data, 'missing', 'default'), 'default')
    
    def test_safe_extract_from_object(self):
        """Test extracting from object attributes."""
        class TestObj:
            def __init__(self):
                self.key = 'value'
                self.tables = ['table1', 'table2']
        
        obj = TestObj()
        
        self.assertEqual(_safe_extract(obj, 'key'), 'value')
        self.assertEqual(_safe_extract(obj, 'tables'), ['table1', 'table2'])
        self.assertEqual(_safe_extract(obj, 'missing', 'default'), 'default')
    
    def test_safe_extract_from_dict_like_object(self):
        """Test extracting from object with dict-like behavior."""
        class DictLikeObj:
            def __init__(self):
                self._data = {'key': 'value', 'tables': ['table1']}
            
            def get(self, key, default=None):
                return self._data.get(key, default)
            
            def __getitem__(self, key):
                return self._data[key]
        
        obj = DictLikeObj()
        
        self.assertEqual(_safe_extract(obj, 'key'), 'value')
        self.assertEqual(_safe_extract(obj, 'tables'), ['table1'])
        self.assertEqual(_safe_extract(obj, 'missing', 'default'), 'default')
    
    def test_safe_extract_none_object(self):
        """Test extracting from None."""
        self.assertEqual(_safe_extract(None, 'key', 'default'), 'default')
    
    def test_safe_extract_with_attribute_error(self):
        """Test extracting when attribute access raises exception."""
        class ProblematicObj:
            @property
            def key(self):
                raise AttributeError("Simulated error")
        
        obj = ProblematicObj()
        self.assertEqual(_safe_extract(obj, 'key', 'default'), 'default')


class TestMessageTypeDetection(unittest.TestCase):
    """Test the enhanced message type detection."""
    
    def test_detect_object_message_types(self):
        """Test detecting message types from object class names."""
        class DatabaseUpdate:
            pass
        
        class SubscriptionUpdate:
            pass
        
        class IdentityToken:
            pass
        
        self.assertEqual(_get_message_type(DatabaseUpdate()), 'DatabaseUpdate')
        self.assertEqual(_get_message_type(SubscriptionUpdate()), 'SubscriptionUpdate')
        self.assertEqual(_get_message_type(IdentityToken()), 'IdentityToken')
    
    def test_detect_dict_message_types(self):
        """Test detecting message types from dictionary keys."""
        db_update = {'database_update': {'tables': []}}
        sub_update = {'subscription_update': {'tables': []}}
        identity_token = {'identity_token': {'token': 'abc'}}
        
        self.assertEqual(_get_message_type(db_update), 'DatabaseUpdate')
        self.assertEqual(_get_message_type(sub_update), 'SubscriptionUpdate')
        self.assertEqual(_get_message_type(identity_token), 'IdentityToken')
    
    def test_detect_unknown_message_type(self):
        """Test handling unknown message types."""
        unknown_obj = object()
        unknown_dict = {'unknown_key': 'value'}
        
        self.assertIsNone(_get_message_type(unknown_obj))
        self.assertIsNone(_get_message_type(unknown_dict))
    
    def test_detect_none_message(self):
        """Test handling None input."""
        self.assertIsNone(_get_message_type(None))


class TestMessageHandlers(unittest.TestCase):
    """Test the enhanced message handlers."""
    
    def test_handle_database_update_dict(self):
        """Test handling database update from dictionary."""
        data = {
            'tables': [{'table_name': 'players', 'num_rows': 5}],
            'request_id': 123
        }
        
        result = _handle_database_update(data)
        
        self.assertEqual(result['type'], 'DatabaseUpdate')
        self.assertEqual(result['tables'], data['tables'])
        self.assertEqual(result['request_id'], 123)
    
    def test_handle_database_update_object(self):
        """Test handling database update from object."""
        class DatabaseUpdateObj:
            def __init__(self):
                self.tables = [{'table_name': 'entities', 'num_rows': 10}]
                self.request_id = 456
        
        obj = DatabaseUpdateObj()
        result = _handle_database_update(obj)
        
        self.assertEqual(result['type'], 'DatabaseUpdate')
        self.assertEqual(result['tables'], obj.tables)
        self.assertEqual(result['request_id'], 456)
    
    def test_handle_subscription_update_dict(self):
        """Test handling subscription update from dictionary."""
        data = {
            'tables': [{'table_name': 'players'}],
            'query_id': 'query-123',
            'request_id': 789
        }
        
        result = _handle_subscription_update(data)
        
        self.assertEqual(result['type'], 'SubscriptionUpdate')
        self.assertEqual(result['tables'], data['tables'])
        self.assertEqual(result['query_id'], 'query-123')
        self.assertEqual(result['request_id'], 789)


class TestSubscriptionManager(unittest.TestCase):
    """Test the SubscriptionManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = SubscriptionManager()
    
    def test_register_subscription(self):
        """Test registering a subscription."""
        callback = Mock()
        
        self.manager.register_subscription(
            table_name='players',
            query='SELECT * FROM players',
            request_id=123,
            callback=callback
        )
        
        # Check subscription was registered
        status = self.manager.get_subscription_status('players')
        self.assertTrue(status['exists'])
        self.assertEqual(status['table_name'], 'players')
        self.assertEqual(status['request_id'], 123)
        self.assertEqual(status['state'], SubscriptionState.PENDING.value)
        self.assertTrue(status['has_callback'])
    
    def test_activate_subscription(self):
        """Test activating a subscription."""
        self.manager.register_subscription('players', 'SELECT * FROM players', 123)
        
        result = self.manager.activate_subscription('players')
        self.assertTrue(result)
        
        status = self.manager.get_subscription_status('players')
        self.assertEqual(status['state'], SubscriptionState.ACTIVE.value)
    
    def test_process_subscription_update_dict(self):
        """Test processing subscription update from dictionary."""
        callback = Mock()
        self.manager.register_subscription('players', 'SELECT * FROM players', 123, callback)
        
        update_data = {
            'tables': [
                {
                    'table_name': 'players',
                    'num_rows': 5,
                    'inserts': [{'id': 1, 'name': 'player1'}],
                    'deletes': []
                }
            ],
            'request_id': 123
        }
        
        result = self.manager.process_subscription_update(update_data)
        self.assertTrue(result)
        
        # Check callback was called
        callback.assert_called_once()
        
        # Check subscription status
        status = self.manager.get_subscription_status('players')
        self.assertEqual(status['state'], SubscriptionState.ACTIVE.value)
        self.assertIsNotNone(status['last_update'])
    
    def test_process_subscription_update_object(self):
        """Test processing subscription update from object."""
        callback = Mock()
        self.manager.register_subscription('entities', 'SELECT * FROM entities', 456, callback)
        
        class UpdateObj:
            def __init__(self):
                self.tables = [
                    type('TableObj', (), {
                        'table_name': 'entities',
                        'num_rows': 3,
                        'inserts': [{'id': 1, 'type': 'npc'}],
                        'deletes': []
                    })()
                ]
                self.request_id = 456
        
        update_obj = UpdateObj()
        result = self.manager.process_subscription_update(update_obj)
        self.assertTrue(result)
        
        # Check callback was called
        callback.assert_called_once()
    
    def test_get_active_subscriptions(self):
        """Test getting active subscriptions."""
        self.manager.register_subscription('players', 'SELECT * FROM players', 123)
        self.manager.register_subscription('entities', 'SELECT * FROM entities', 456)
        
        # Initially, subscriptions are pending
        active = self.manager.get_active_subscriptions()
        self.assertEqual(len(active), 0)
        
        # Activate one subscription
        self.manager.activate_subscription('players')
        active = self.manager.get_active_subscriptions()
        self.assertEqual(len(active), 1)
        self.assertIn('players', active)
    
    def test_unregister_subscription(self):
        """Test unregistering a subscription."""
        self.manager.register_subscription('players', 'SELECT * FROM players', 123)
        
        # Verify it exists
        status = self.manager.get_subscription_status('players')
        self.assertTrue(status['exists'])
        
        # Unregister
        result = self.manager.unregister_subscription('players')
        self.assertTrue(result)
        
        # Verify it's gone
        status = self.manager.get_subscription_status('players')
        self.assertFalse(status['exists'])
    
    def test_subscription_summary(self):
        """Test getting subscription summary."""
        self.manager.register_subscription('players', 'SELECT * FROM players', 123)
        self.manager.register_subscription('entities', 'SELECT * FROM entities', 456)
        self.manager.activate_subscription('players')
        
        summary = self.manager.get_subscription_summary()
        
        self.assertEqual(summary['total_subscriptions'], 2)
        self.assertEqual(summary['active_subscriptions'], 1)
        self.assertEqual(summary['failed_subscriptions'], 0)


class TestSDKEventManager(unittest.TestCase):
    """Test the SDKEventManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_manager = SDKEventManager("TestEventManager")
    
    def test_register_and_emit_event(self):
        """Test registering handlers and emitting events."""
        handler1 = Mock()
        handler2 = Mock()
        
        # Register handlers
        result1 = self.event_manager.register_handler(EventType.CONNECTION_OPENED, handler1)
        result2 = self.event_manager.register_handler(EventType.CONNECTION_OPENED, handler2)
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        
        # Emit event
        handled_count = self.event_manager.emit_event(
            EventType.CONNECTION_OPENED,
            {'host': 'localhost', 'port': 3000}
        )
        
        self.assertEqual(handled_count, 2)
        
        # Check handlers were called
        handler1.assert_called_once()
        handler2.assert_called_once()
        
        # Check event data
        event_data = handler1.call_args[0][0]
        self.assertIsInstance(event_data, EventData)
        self.assertEqual(event_data.event_type, EventType.CONNECTION_OPENED)
        self.assertEqual(event_data.data['host'], 'localhost')
    
    def test_register_global_handler(self):
        """Test registering global handlers."""
        global_handler = Mock()
        specific_handler = Mock()
        
        # Register handlers
        self.event_manager.register_global_handler(global_handler)
        self.event_manager.register_handler(EventType.CONNECTION_OPENED, specific_handler)
        
        # Emit different events
        self.event_manager.emit_event(EventType.CONNECTION_OPENED, {})
        self.event_manager.emit_event(EventType.CONNECTION_CLOSED, {})
        
        # Global handler should be called twice, specific handler once
        self.assertEqual(global_handler.call_count, 2)
        specific_handler.assert_called_once()
    
    def test_emit_subscription_event(self):
        """Test emitting subscription events."""
        handler = Mock()
        self.event_manager.register_handler(EventType.SUBSCRIPTION_UPDATE, handler)
        
        subscription_data = {
            'table_name': 'players',
            'request_id': 123,
            'num_rows': 5
        }
        
        count = self.event_manager.emit_subscription_event(
            EventType.SUBSCRIPTION_UPDATE,
            subscription_data
        )
        
        self.assertEqual(count, 1)
        handler.assert_called_once()
        
        # Check metadata
        event_data = handler.call_args[0][0]
        self.assertEqual(event_data.metadata['category'], 'subscription')
        self.assertEqual(event_data.metadata['table_name'], 'players')
        self.assertEqual(event_data.metadata['request_id'], 123)
    
    def test_emit_message_event(self):
        """Test emitting message events based on message type."""
        handler = Mock()
        self.event_manager.register_handler(EventType.DATABASE_UPDATE, handler)
        
        # Create a message that should be detected as DatabaseUpdate
        message_data = {
            'database_update': {
                'tables': [{'table_name': 'players'}]
            }
        }
        
        count = self.event_manager.emit_message_event(message_data, "received")
        
        self.assertEqual(count, 1)
        handler.assert_called_once()
        
        # Check metadata
        event_data = handler.call_args[0][0]
        self.assertEqual(event_data.metadata['category'], 'message')
        self.assertEqual(event_data.metadata['direction'], 'received')
        self.assertEqual(event_data.metadata['message_type'], 'DatabaseUpdate')
    
    def test_handler_error_handling(self):
        """Test error handling in event handlers."""
        def failing_handler(event_data):
            raise ValueError("Simulated handler error")
        
        def working_handler(event_data):
            pass
        
        self.event_manager.register_handler(EventType.CONNECTION_OPENED, failing_handler)
        self.event_manager.register_handler(EventType.CONNECTION_OPENED, working_handler)
        
        # Emit event - should handle errors gracefully
        handled_count = self.event_manager.emit_event(EventType.CONNECTION_OPENED, {})
        
        # Only one handler should succeed
        self.assertEqual(handled_count, 1)
        
        # Check error statistics
        stats = self.event_manager.get_statistics()
        self.assertEqual(stats['handler_errors'], 1)
    
    def test_unregister_handlers(self):
        """Test unregistering handlers."""
        handler = Mock()
        
        # Register and verify
        self.event_manager.register_handler(EventType.CONNECTION_OPENED, handler)
        self.assertEqual(self.event_manager.get_handler_count(EventType.CONNECTION_OPENED), 1)
        
        # Unregister and verify
        result = self.event_manager.unregister_handler(EventType.CONNECTION_OPENED, handler)
        self.assertTrue(result)
        self.assertEqual(self.event_manager.get_handler_count(EventType.CONNECTION_OPENED), 0)
        
        # Try to unregister again
        result = self.event_manager.unregister_handler(EventType.CONNECTION_OPENED, handler)
        self.assertFalse(result)
    
    def test_event_statistics(self):
        """Test event manager statistics."""
        handler = Mock()
        self.event_manager.register_handler(EventType.CONNECTION_OPENED, handler)
        
        # Emit some events
        self.event_manager.emit_event(EventType.CONNECTION_OPENED, {})
        self.event_manager.emit_event(EventType.CONNECTION_OPENED, {})
        
        stats = self.event_manager.get_statistics()
        
        self.assertEqual(stats['events_emitted'], 2)
        self.assertEqual(stats['events_handled'], 2)
        self.assertEqual(stats['handler_errors'], 0)
        self.assertEqual(stats['success_rate'], 100.0)


class TestIntegration(unittest.TestCase):
    """Test integration between components."""
    
    def test_subscription_manager_event_integration(self):
        """Test integration between SubscriptionManager and EventManager."""
        # Create managers
        subscription_manager = SubscriptionManager()
        event_manager = SDKEventManager("IntegrationTest")
        
        # Set up event handler
        events_received = []
        
        def event_handler(event_data):
            events_received.append(event_data)
        
        event_manager.register_handler(EventType.SUBSCRIPTION_UPDATE, event_handler)
        
        # Register subscription
        subscription_manager.register_subscription('players', 'SELECT * FROM players', 123)
        
        # Create subscription update
        update_data = {
            'tables': [{'table_name': 'players', 'num_rows': 1}],
            'request_id': 123
        }
        
        # Process update and emit event
        subscription_manager.process_subscription_update(update_data)
        event_manager.emit_subscription_event(EventType.SUBSCRIPTION_UPDATE, update_data)
        
        # Verify integration
        self.assertEqual(len(events_received), 1)
        
        status = subscription_manager.get_subscription_status('players')
        self.assertEqual(status['state'], SubscriptionState.ACTIVE.value)
    
    def test_serialization_subscription_integration(self):
        """Test integration between serialization and subscription manager."""
        subscription_manager = SubscriptionManager()
        
        # Register subscription with callback
        received_data = []
        
        def callback(data):
            received_data.append(data)
        
        subscription_manager.register_subscription('players', 'SELECT * FROM players', 123, callback)
        
        # Create object-based update (the problematic case from bug report)
        class TableUpdateObj:
            def __init__(self):
                self.table_name = 'players'
                self.num_rows = 3
                self.inserts = [{'id': 1, 'name': 'test'}]
                self.deletes = []
        
        class DatabaseUpdateObj:
            def __init__(self):
                self.tables = [TableUpdateObj()]
                self.request_id = 123
        
        update_obj = DatabaseUpdateObj()
        
        # Process the object-based update
        result = subscription_manager.process_subscription_update(update_obj)
        self.assertTrue(result)
        
        # Verify callback was called with the table data
        self.assertEqual(len(received_data), 1)
        
        # Verify the data was properly extracted using _safe_extract
        table_data = received_data[0]
        self.assertEqual(_safe_extract(table_data, 'table_name'), 'players')
        self.assertEqual(_safe_extract(table_data, 'num_rows'), 3)


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Run tests
    unittest.main(verbosity=2)