"""
Isolated tests for the subscription manager module

These tests will validate the subscription manager functionality 
that will be extracted from websocket_client.py during Phase 2 refactoring.
"""
import pytest
import time
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional, List

from spacetimedb_sdk.websocket_client import SubscriptionMetrics
from spacetimedb_sdk.query_id import QueryId
from spacetimedb_sdk.protocol import Subscribe, Unsubscribe, SubscriptionError


class MockSubscriptionManager:
    """Mock subscription manager to test the interface that will be extracted"""
    
    def __init__(self):
        self.subscriptions: Dict[str, Dict[str, Any]] = {}
        self.query_states: Dict[str, str] = {}
        self.metrics = SubscriptionMetrics()
        self.callbacks = []
        self.error_callbacks = []
        self.data_callbacks = []
        
    def add_subscription(self, query_id: str, table_name: str, sql_query: str) -> bool:
        """Add a new subscription"""
        if query_id in self.subscriptions:
            return False
            
        self.subscriptions[query_id] = {
            'table_name': table_name,
            'sql_query': sql_query,
            'status': 'pending',
            'created_at': time.time(),
            'last_activity': time.time()
        }
        
        self.query_states[query_id] = 'pending'
        return True
        
    def remove_subscription(self, query_id: str) -> bool:
        """Remove a subscription"""
        if query_id not in self.subscriptions:
            return False
            
        del self.subscriptions[query_id]
        if query_id in self.query_states:
            del self.query_states[query_id]
        return True
        
    def get_subscription(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription details"""
        return self.subscriptions.get(query_id)
        
    def get_all_subscriptions(self) -> Dict[str, Dict[str, Any]]:
        """Get all subscriptions"""
        return self.subscriptions.copy()
        
    def update_subscription_status(self, query_id: str, status: str) -> bool:
        """Update subscription status"""
        if query_id not in self.subscriptions:
            return False
            
        self.subscriptions[query_id]['status'] = status
        self.subscriptions[query_id]['last_activity'] = time.time()
        self.query_states[query_id] = status
        return True
        
    def handle_subscription_applied(self, query_id: str, table_name: str) -> None:
        """Handle subscription applied message"""
        if query_id in self.subscriptions:
            self.update_subscription_status(query_id, 'active')
            
            # Notify callbacks
            for callback in self.callbacks:
                try:
                    callback('subscription_applied', {
                        'query_id': query_id,
                        'table_name': table_name
                    })
                except Exception as e:
                    print(f"Callback error: {e}")
                    
    def handle_subscription_error(self, query_id: str, error: str) -> None:
        """Handle subscription error message"""
        if query_id in self.subscriptions:
            self.update_subscription_status(query_id, 'error')
            self.metrics.record_subscription_error(
                self.subscriptions[query_id]['table_name'], 
                error
            )
            
            # Notify error callbacks
            for callback in self.error_callbacks:
                try:
                    callback('subscription_error', {
                        'query_id': query_id,
                        'error': error
                    })
                except Exception as e:
                    print(f"Error callback error: {e}")
                    
    def handle_subscription_data(self, table_name: str, data: Any) -> None:
        """Handle subscription data"""
        # Record metrics
        data_size = len(json.dumps(data)) if data else 0
        self.metrics.record_subscription_data(table_name, data_size)
        
        # Notify data callbacks
        for callback in self.data_callbacks:
            try:
                callback('subscription_data', {
                    'table_name': table_name,
                    'data': data
                })
            except Exception as e:
                print(f"Data callback error: {e}")
                
    def add_callback(self, callback_type: str, callback) -> None:
        """Add a callback"""
        if callback_type == 'general':
            self.callbacks.append(callback)
        elif callback_type == 'error':
            self.error_callbacks.append(callback)
        elif callback_type == 'data':
            self.data_callbacks.append(callback)
            
    def remove_callback(self, callback_type: str, callback) -> bool:
        """Remove a callback"""
        try:
            if callback_type == 'general':
                self.callbacks.remove(callback)
            elif callback_type == 'error':
                self.error_callbacks.remove(callback)
            elif callback_type == 'data':
                self.data_callbacks.remove(callback)
            return True
        except ValueError:
            return False
            
    def get_subscription_count(self) -> int:
        """Get total subscription count"""
        return len(self.subscriptions)
        
    def get_active_subscription_count(self) -> int:
        """Get active subscription count"""
        return sum(1 for sub in self.subscriptions.values() if sub['status'] == 'active')
        
    def cleanup_inactive_subscriptions(self, max_age: float = 300.0) -> int:
        """Cleanup inactive subscriptions"""
        current_time = time.time()
        to_remove = []
        
        for query_id, subscription in self.subscriptions.items():
            if current_time - subscription['last_activity'] > max_age:
                if subscription['status'] in ['error', 'inactive']:
                    to_remove.append(query_id)
                    
        for query_id in to_remove:
            self.remove_subscription(query_id)
            
        return len(to_remove)


class TestSubscriptionManager:
    """Test the subscription manager functionality"""
    
    def test_subscription_creation(self, subscription_manager_mock):
        """Test creating subscriptions"""
        manager = MockSubscriptionManager()
        
        # Test basic subscription creation
        query_id = str(uuid.uuid4())
        table_name = "users"
        sql_query = "SELECT * FROM users"
        
        success = manager.add_subscription(query_id, table_name, sql_query)
        assert success is True
        
        # Verify subscription was added
        subscription = manager.get_subscription(query_id)
        assert subscription is not None
        assert subscription['table_name'] == table_name
        assert subscription['sql_query'] == sql_query
        assert subscription['status'] == 'pending'
        
    def test_duplicate_subscription_prevention(self):
        """Test that duplicate subscriptions are prevented"""
        manager = MockSubscriptionManager()
        
        query_id = str(uuid.uuid4())
        table_name = "users"
        sql_query = "SELECT * FROM users"
        
        # Add first subscription
        success1 = manager.add_subscription(query_id, table_name, sql_query)
        assert success1 is True
        
        # Try to add duplicate
        success2 = manager.add_subscription(query_id, table_name, sql_query)
        assert success2 is False
        
        # Should still have only one subscription
        assert manager.get_subscription_count() == 1
        
    def test_subscription_removal(self):
        """Test removing subscriptions"""
        manager = MockSubscriptionManager()
        
        query_id = str(uuid.uuid4())
        table_name = "users"
        sql_query = "SELECT * FROM users"
        
        # Add subscription
        manager.add_subscription(query_id, table_name, sql_query)
        assert manager.get_subscription_count() == 1
        
        # Remove subscription
        success = manager.remove_subscription(query_id)
        assert success is True
        assert manager.get_subscription_count() == 0
        
        # Try to remove non-existent subscription
        success = manager.remove_subscription(query_id)
        assert success is False
        
    def test_subscription_status_updates(self):
        """Test updating subscription status"""
        manager = MockSubscriptionManager()
        
        query_id = str(uuid.uuid4())
        table_name = "users"
        sql_query = "SELECT * FROM users"
        
        # Add subscription
        manager.add_subscription(query_id, table_name, sql_query)
        
        # Update status
        success = manager.update_subscription_status(query_id, 'active')
        assert success is True
        
        subscription = manager.get_subscription(query_id)
        assert subscription['status'] == 'active'
        
        # Update to error status
        success = manager.update_subscription_status(query_id, 'error')
        assert success is True
        
        subscription = manager.get_subscription(query_id)
        assert subscription['status'] == 'error'
        
    def test_subscription_applied_handling(self):
        """Test handling subscription applied messages"""
        manager = MockSubscriptionManager()
        
        query_id = str(uuid.uuid4())
        table_name = "users"
        sql_query = "SELECT * FROM users"
        
        # Add subscription
        manager.add_subscription(query_id, table_name, sql_query)
        
        # Track callback
        callback_called = False
        callback_data = None
        
        def test_callback(event_type, data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = data
            
        manager.add_callback('general', test_callback)
        
        # Handle subscription applied
        manager.handle_subscription_applied(query_id, table_name)
        
        # Verify status update
        subscription = manager.get_subscription(query_id)
        assert subscription['status'] == 'active'
        
        # Verify callback was called
        assert callback_called is True
        assert callback_data['query_id'] == query_id
        assert callback_data['table_name'] == table_name
        
    def test_subscription_error_handling(self):
        """Test handling subscription error messages"""
        manager = MockSubscriptionManager()
        
        query_id = str(uuid.uuid4())
        table_name = "users"
        sql_query = "SELECT * FROM users"
        
        # Add subscription
        manager.add_subscription(query_id, table_name, sql_query)
        
        # Track error callback
        error_callback_called = False
        error_data = None
        
        def error_callback(event_type, data):
            nonlocal error_callback_called, error_data
            error_callback_called = True
            error_data = data
            
        manager.add_callback('error', error_callback)
        
        # Handle subscription error
        error_message = "Table not found"
        manager.handle_subscription_error(query_id, error_message)
        
        # Verify status update
        subscription = manager.get_subscription(query_id)
        assert subscription['status'] == 'error'
        
        # Verify error callback was called
        assert error_callback_called is True
        assert error_data['query_id'] == query_id
        assert error_data['error'] == error_message
        
        # Verify metrics recorded
        health = manager.metrics.get_subscription_health(table_name)
        assert health['error_count'] == 1
        
    def test_subscription_data_handling(self):
        """Test handling subscription data"""
        manager = MockSubscriptionManager()
        
        table_name = "users"
        test_data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
        
        # Track data callback
        data_callback_called = False
        received_data = None
        
        def data_callback(event_type, data):
            nonlocal data_callback_called, received_data
            data_callback_called = True
            received_data = data
            
        manager.add_callback('data', data_callback)
        
        # Handle subscription data
        manager.handle_subscription_data(table_name, test_data)
        
        # Verify data callback was called
        assert data_callback_called is True
        assert received_data['table_name'] == table_name
        assert received_data['data'] == test_data
        
        # Verify metrics recorded
        health = manager.metrics.get_subscription_health(table_name)
        assert health['message_count'] == 1
        assert health['total_bytes'] > 0
        
    def test_callback_management(self):
        """Test adding and removing callbacks"""
        manager = MockSubscriptionManager()
        
        def test_callback1(event_type, data):
            pass
            
        def test_callback2(event_type, data):
            pass
            
        # Add callbacks
        manager.add_callback('general', test_callback1)
        manager.add_callback('error', test_callback2)
        
        assert len(manager.callbacks) == 1
        assert len(manager.error_callbacks) == 1
        
        # Remove callbacks
        success1 = manager.remove_callback('general', test_callback1)
        success2 = manager.remove_callback('error', test_callback2)
        
        assert success1 is True
        assert success2 is True
        assert len(manager.callbacks) == 0
        assert len(manager.error_callbacks) == 0
        
        # Try to remove non-existent callback
        success3 = manager.remove_callback('general', test_callback1)
        assert success3 is False
        
    def test_subscription_counting(self):
        """Test subscription counting methods"""
        manager = MockSubscriptionManager()
        
        # Initially no subscriptions
        assert manager.get_subscription_count() == 0
        assert manager.get_active_subscription_count() == 0
        
        # Add subscriptions
        query_id1 = str(uuid.uuid4())
        query_id2 = str(uuid.uuid4())
        
        manager.add_subscription(query_id1, "users", "SELECT * FROM users")
        manager.add_subscription(query_id2, "messages", "SELECT * FROM messages")
        
        assert manager.get_subscription_count() == 2
        assert manager.get_active_subscription_count() == 0  # Still pending
        
        # Activate one subscription
        manager.update_subscription_status(query_id1, 'active')
        
        assert manager.get_subscription_count() == 2
        assert manager.get_active_subscription_count() == 1
        
        # Activate second subscription
        manager.update_subscription_status(query_id2, 'active')
        
        assert manager.get_subscription_count() == 2
        assert manager.get_active_subscription_count() == 2
        
    def test_subscription_cleanup(self):
        """Test cleaning up inactive subscriptions"""
        manager = MockSubscriptionManager()
        
        # Add subscriptions with different statuses
        query_id1 = str(uuid.uuid4())
        query_id2 = str(uuid.uuid4())
        query_id3 = str(uuid.uuid4())
        
        manager.add_subscription(query_id1, "users", "SELECT * FROM users")
        manager.add_subscription(query_id2, "messages", "SELECT * FROM messages")
        manager.add_subscription(query_id3, "logs", "SELECT * FROM logs")
        
        # Set different statuses and ages
        manager.update_subscription_status(query_id1, 'active')
        manager.update_subscription_status(query_id2, 'error')
        manager.update_subscription_status(query_id3, 'inactive')
        
        # Make query_id2 and query_id3 old
        old_time = time.time() - 400  # 400 seconds ago
        manager.subscriptions[query_id2]['last_activity'] = old_time
        manager.subscriptions[query_id3]['last_activity'] = old_time
        
        # Cleanup with max_age of 300 seconds
        cleaned_count = manager.cleanup_inactive_subscriptions(300.0)
        
        # Should have cleaned up 2 subscriptions (error and inactive)
        assert cleaned_count == 2
        assert manager.get_subscription_count() == 1
        
        # Only active subscription should remain
        remaining = manager.get_subscription(query_id1)
        assert remaining is not None
        assert remaining['status'] == 'active'
        
    def test_subscription_metrics_integration(self):
        """Test integration with subscription metrics"""
        manager = MockSubscriptionManager()
        
        table_name = "users"
        
        # Handle some data
        test_data = {"id": 1, "name": "Alice"}
        manager.handle_subscription_data(table_name, test_data)
        
        # Handle an error
        query_id = str(uuid.uuid4())
        manager.add_subscription(query_id, table_name, "SELECT * FROM users")
        manager.handle_subscription_error(query_id, "Connection lost")
        
        # Check metrics
        health = manager.metrics.get_subscription_health(table_name)
        assert health['message_count'] == 1
        assert health['error_count'] == 1
        assert health['total_bytes'] > 0
        
    def test_concurrent_subscription_operations(self):
        """Test concurrent subscription operations"""
        import threading
        
        manager = MockSubscriptionManager()
        results = []
        
        def add_subscriptions(start_id, count):
            for i in range(count):
                query_id = f"query_{start_id}_{i}"
                success = manager.add_subscription(
                    query_id, 
                    f"table_{i}", 
                    f"SELECT * FROM table_{i}"
                )
                results.append(success)
                
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=add_subscriptions, args=(i, 10))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads
        for thread in threads:
            thread.join()
            
        # All operations should succeed
        assert all(results)
        assert manager.get_subscription_count() == 30


class TestSubscriptionManagerMockBehavior:
    """Test the mock subscription manager behavior"""
    
    def test_mock_manager_initialization(self):
        """Test that mock manager initializes properly"""
        manager = MockSubscriptionManager()
        
        assert isinstance(manager.subscriptions, dict)
        assert isinstance(manager.query_states, dict)
        assert isinstance(manager.metrics, SubscriptionMetrics)
        assert isinstance(manager.callbacks, list)
        assert isinstance(manager.error_callbacks, list)
        assert isinstance(manager.data_callbacks, list)
        
    def test_mock_manager_interface_completeness(self):
        """Test that mock manager implements the expected interface"""
        manager = MockSubscriptionManager()
        
        # Test all expected methods exist
        expected_methods = [
            'add_subscription',
            'remove_subscription',
            'get_subscription',
            'get_all_subscriptions',
            'update_subscription_status',
            'handle_subscription_applied',
            'handle_subscription_error',
            'handle_subscription_data',
            'add_callback',
            'remove_callback',
            'get_subscription_count',
            'get_active_subscription_count',
            'cleanup_inactive_subscriptions'
        ]
        
        for method_name in expected_methods:
            assert hasattr(manager, method_name), f"Missing method: {method_name}"
            assert callable(getattr(manager, method_name)), f"Method {method_name} is not callable"