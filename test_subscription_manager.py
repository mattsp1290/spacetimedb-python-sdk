"""
Comprehensive test suite for SubscriptionManager.

Tests all aspects of subscription management including:
- QueryId operations
- Subscription lifecycle management
- Health monitoring
- Event integration
- Thread safety
- Error handling
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pytest
import threading
import time
from unittest.mock import Mock, patch
from typing import List, Optional

from spacetimedb_sdk.connection.subscription_manager import (
    SubscriptionManager,
    SubscriptionState,
    SubscriptionInfo,
    SubscriptionMetrics,
    create_subscription_manager
)
from spacetimedb_sdk.query_id import QueryId
# Import events with fallback for testing
try:
    from spacetimedb_sdk.events import (
        EnhancedEventManager,
        SubscriptionEvent,
        EventType
    )
except ImportError:
    # Create minimal stubs for testing
    class EnhancedEventManager:
        def publish_event(self, event): pass
        def subscribe(self, handler, event_type): pass
    
    class SubscriptionEvent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class EventType:
        SUBSCRIPTION = "subscription"


class TestSubscriptionManager:
    """Test suite for SubscriptionManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = Mock(spec=EnhancedEventManager)
        self.manager = SubscriptionManager(
            max_subscriptions=100,
            event_manager=self.event_manager
        )
        self.query_id = QueryId.generate()
        self.queries = ["SELECT * FROM test_table", "SELECT count(*) FROM test_table"]
        self.request_id = 12345
    
    def test_subscription_manager_initialization(self):
        """Test SubscriptionManager initialization."""
        manager = SubscriptionManager()
        assert manager is not None
        assert manager.get_subscription_count() == 0
        assert manager.get_subscription_count(SubscriptionState.ACTIVE) == 0
        
        # Test with custom parameters
        event_manager = Mock(spec=EnhancedEventManager)
        manager = SubscriptionManager(
            max_subscriptions=50,
            event_manager=event_manager
        )
        assert manager.event_manager is event_manager
    
    def test_register_subscription(self):
        """Test subscription registration."""
        # Register a subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        
        # Verify registration
        assert self.manager.get_subscription_count() == 1
        assert self.manager.get_subscription_count(SubscriptionState.PENDING) == 1
        
        # Verify subscription info
        sub_info = self.manager.get_subscription_info(self.query_id)
        assert sub_info is not None
        assert sub_info.query_id == self.query_id
        assert sub_info.queries == self.queries
        assert sub_info.request_id == self.request_id
        assert sub_info.state == SubscriptionState.PENDING
        
        # Verify request lookup
        sub_info_by_request = self.manager.get_subscription_by_request(self.request_id)
        assert sub_info_by_request is not None
        assert sub_info_by_request.query_id == self.query_id
        
        # Verify event was published
        assert self.event_manager.publish_event.called
    
    def test_activate_subscription(self):
        """Test subscription activation."""
        # Register and activate subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        
        # Verify initial state
        assert self.manager.get_subscription_count(SubscriptionState.PENDING) == 1
        assert self.manager.get_subscription_count(SubscriptionState.ACTIVE) == 0
        
        # Activate subscription
        result = self.manager.activate_subscription(self.query_id)
        assert result is True
        
        # Verify activation
        assert self.manager.get_subscription_count(SubscriptionState.PENDING) == 0
        assert self.manager.get_subscription_count(SubscriptionState.ACTIVE) == 1
        
        sub_info = self.manager.get_subscription_info(self.query_id)
        assert sub_info.state == SubscriptionState.ACTIVE
    
    def test_activate_subscription_by_request(self):
        """Test subscription activation by request ID."""
        # Register subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        
        # Activate by request ID
        result = self.manager.activate_subscription_by_request(self.request_id)
        assert result is True
        
        # Verify activation
        sub_info = self.manager.get_subscription_info(self.query_id)
        assert sub_info.state == SubscriptionState.ACTIVE
        
        # Test with unknown request ID
        result = self.manager.activate_subscription_by_request(99999)
        assert result is False
    
    def test_record_subscription_data(self):
        """Test recording subscription data."""
        # Register and activate subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        
        # Record data
        self.manager.record_subscription_data(self.query_id, 1024)
        
        # Verify data recording
        sub_info = self.manager.get_subscription_info(self.query_id)
        assert sub_info.message_count == 1
        assert sub_info.state == SubscriptionState.ACTIVE  # Should auto-activate
        
        # Record more data
        self.manager.record_subscription_data(self.query_id, 2048)
        sub_info = self.manager.get_subscription_info(self.query_id)
        assert sub_info.message_count == 2
    
    def test_record_subscription_error(self):
        """Test recording subscription errors."""
        # Register subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        
        # Record error
        error_msg = "Test error message"
        self.manager.record_subscription_error(self.query_id, error_msg)
        
        # Verify error recording
        sub_info = self.manager.get_subscription_info(self.query_id)
        assert sub_info.error_count == 1
        assert sub_info.last_error == error_msg
        assert sub_info.state == SubscriptionState.ERROR
        
        # Verify state count
        assert self.manager.get_subscription_count(SubscriptionState.ERROR) == 1
        assert self.manager.get_subscription_count(SubscriptionState.PENDING) == 0
    
    def test_unregister_subscription(self):
        """Test subscription unregistration."""
        # Register subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        
        # Verify registration
        assert self.manager.get_subscription_count() == 1
        
        # Unregister subscription
        result = self.manager.unregister_subscription(self.query_id)
        assert result is True
        
        # Verify unregistration
        assert self.manager.get_subscription_count() == 0
        sub_info = self.manager.get_subscription_info(self.query_id)
        assert sub_info is None
        
        # Test unregistering unknown subscription
        unknown_query_id = QueryId.generate()
        result = self.manager.unregister_subscription(unknown_query_id)
        assert result is False
    
    def test_find_subscriptions_by_query(self):
        """Test finding subscriptions by query strings."""
        # Register multiple subscriptions
        query_id1 = QueryId.generate()
        query_id2 = QueryId.generate()
        query_id3 = QueryId.generate()
        
        queries1 = ["SELECT * FROM table1"]
        queries2 = ["SELECT * FROM table2"]
        queries3 = ["SELECT * FROM table1"]  # Same as queries1
        
        self.manager.register_subscription(query_id1, queries1, 1)
        self.manager.register_subscription(query_id2, queries2, 2)
        self.manager.register_subscription(query_id3, queries3, 3)
        
        # Find subscriptions by query
        matches1 = self.manager.find_subscriptions_by_query(queries1)
        assert len(matches1) == 2  # query_id1 and query_id3
        assert query_id1 in matches1
        assert query_id3 in matches1
        
        matches2 = self.manager.find_subscriptions_by_query(queries2)
        assert len(matches2) == 1
        assert query_id2 in matches2
        
        # Test with non-existent query
        matches_none = self.manager.find_subscriptions_by_query(["SELECT * FROM nonexistent"])
        assert len(matches_none) == 0
    
    def test_get_active_subscriptions(self):
        """Test getting active subscriptions."""
        # Register multiple subscriptions
        query_id1 = QueryId.generate()
        query_id2 = QueryId.generate()
        query_id3 = QueryId.generate()
        
        self.manager.register_subscription(query_id1, ["SELECT * FROM table1"], 1)
        self.manager.register_subscription(query_id2, ["SELECT * FROM table2"], 2)
        self.manager.register_subscription(query_id3, ["SELECT * FROM table3"], 3)
        
        # Initially no active subscriptions
        active = self.manager.get_active_subscriptions()
        assert len(active) == 0
        
        # Activate some subscriptions
        self.manager.activate_subscription(query_id1)
        self.manager.activate_subscription(query_id3)
        
        # Check active subscriptions
        active = self.manager.get_active_subscriptions()
        assert len(active) == 2
        assert query_id1 in active
        assert query_id3 in active
        assert query_id2 not in active
    
    def test_subscription_metrics(self):
        """Test subscription metrics calculation."""
        # Register subscriptions in different states
        query_id1 = QueryId.generate()
        query_id2 = QueryId.generate()
        query_id3 = QueryId.generate()
        
        self.manager.register_subscription(query_id1, ["SELECT * FROM table1"], 1)
        self.manager.register_subscription(query_id2, ["SELECT * FROM table2"], 2)
        self.manager.register_subscription(query_id3, ["SELECT * FROM table3"], 3)
        
        # Activate one, error one, leave one pending
        self.manager.activate_subscription(query_id1)
        self.manager.record_subscription_error(query_id2, "test error")
        
        # Record some data
        self.manager.record_subscription_data(query_id1, 1024)
        self.manager.record_subscription_data(query_id1, 2048)
        
        # Get metrics
        metrics = self.manager.get_subscription_metrics()
        assert metrics.total_subscriptions == 3
        assert metrics.active_subscriptions == 1
        assert metrics.pending_subscriptions == 1
        assert metrics.error_subscriptions == 1
        assert metrics.total_messages == 2
        assert metrics.total_errors == 1
        assert metrics.error_rate == 0.5  # 1 error / 2 messages
    
    def test_subscription_health(self):
        """Test subscription health monitoring."""
        # Register and activate subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        self.manager.activate_subscription(self.query_id)
        
        # Check health
        health = self.manager.get_subscription_health(self.query_id)
        assert health['status'] == 'healthy'
        assert health['state'] == 'active'
        assert health['message_count'] == 0
        assert health['error_count'] == 0
        
        # Record some activity
        self.manager.record_subscription_data(self.query_id, 1024)
        health = self.manager.get_subscription_health(self.query_id)
        assert health['message_count'] == 1
        
        # Record error
        self.manager.record_subscription_error(self.query_id, "test error")
        health = self.manager.get_subscription_health(self.query_id)
        assert health['status'] == 'error'
        assert health['error_count'] == 1
        assert health['last_error'] == "test error"
    
    def test_health_check(self):
        """Test comprehensive health check."""
        # Register multiple subscriptions
        query_id1 = QueryId.generate()
        query_id2 = QueryId.generate()
        
        self.manager.register_subscription(query_id1, ["SELECT * FROM table1"], 1)
        self.manager.register_subscription(query_id2, ["SELECT * FROM table2"], 2)
        
        # Activate and add activity
        self.manager.activate_subscription(query_id1)
        self.manager.record_subscription_data(query_id1, 1024)
        
        # Add error to second subscription
        self.manager.record_subscription_error(query_id2, "test error")
        
        # Perform health check
        health_report = self.manager.perform_health_check()
        assert health_report['status'] in ['healthy', 'warning', 'critical']
        assert health_report['total_subscriptions'] == 2
        assert health_report['active_subscriptions'] == 1
        assert 'metrics' in health_report
        assert 'timestamp' in health_report
    
    def test_state_change_callbacks(self):
        """Test state change callback system."""
        callback_calls = []
        
        def test_callback(query_id, old_state, new_state):
            callback_calls.append((query_id, old_state, new_state))
        
        # Add callback
        self.manager.add_state_change_callback(test_callback)
        
        # Register and activate subscription
        self.manager.register_subscription(
            query_id=self.query_id,
            queries=self.queries,
            request_id=self.request_id
        )
        self.manager.activate_subscription(self.query_id)
        
        # Verify callback was called
        assert len(callback_calls) == 1
        query_id, old_state, new_state = callback_calls[0]
        assert query_id == self.query_id
        assert old_state == SubscriptionState.PENDING
        assert new_state == SubscriptionState.ACTIVE
        
        # Remove callback
        self.manager.remove_state_change_callback(test_callback)
        
        # Record error (should not trigger callback)
        self.manager.record_subscription_error(self.query_id, "test error")
        assert len(callback_calls) == 1  # No new calls
    
    def test_clear_all_subscriptions(self):
        """Test clearing all subscriptions."""
        # Register multiple subscriptions
        query_id1 = QueryId.generate()
        query_id2 = QueryId.generate()
        
        self.manager.register_subscription(query_id1, ["SELECT * FROM table1"], 1)
        self.manager.register_subscription(query_id2, ["SELECT * FROM table2"], 2)
        
        # Verify registrations
        assert self.manager.get_subscription_count() == 2
        
        # Clear all
        self.manager.clear_all_subscriptions()
        
        # Verify clearing
        assert self.manager.get_subscription_count() == 0
        assert self.manager.get_subscription_info(query_id1) is None
        assert self.manager.get_subscription_info(query_id2) is None
    
    def test_thread_safety(self):
        """Test thread safety of subscription operations."""
        import concurrent.futures
        
        # Test concurrent subscription registration
        def register_subscription(i):
            query_id = QueryId.generate()
            queries = [f"SELECT * FROM table{i}"]
            request_id = 1000 + i
            self.manager.register_subscription(query_id, queries, request_id)
            return query_id
        
        # Register subscriptions concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register_subscription, i) for i in range(50)]
            query_ids = [future.result() for future in futures]
        
        # Verify all subscriptions were registered
        assert self.manager.get_subscription_count() == 50
        
        # Test concurrent activation
        def activate_subscription(query_id):
            return self.manager.activate_subscription(query_id)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(activate_subscription, qid) for qid in query_ids]
            results = [future.result() for future in futures]
        
        # Verify all activations succeeded
        assert all(results)
        assert self.manager.get_subscription_count(SubscriptionState.ACTIVE) == 50
    
    def test_error_handling(self):
        """Test error handling in subscription operations."""
        # Test operations on unknown subscription
        unknown_query_id = QueryId.generate()
        
        # Should handle gracefully
        result = self.manager.activate_subscription(unknown_query_id)
        assert result is False
        
        # Should handle gracefully
        self.manager.record_subscription_data(unknown_query_id, 1024)
        self.manager.record_subscription_error(unknown_query_id, "test error")
        
        # Should return None for unknown subscription
        info = self.manager.get_subscription_info(unknown_query_id)
        assert info is None
        
        # Health check on unknown subscription
        health = self.manager.get_subscription_health(unknown_query_id)
        assert health['status'] == 'not_found'
    
    def test_subscription_info_dataclass(self):
        """Test SubscriptionInfo dataclass functionality."""
        query_id = QueryId.generate()
        queries = ["SELECT * FROM test"]
        request_id = 123
        
        # Create subscription info
        sub_info = SubscriptionInfo(
            query_id=query_id,
            queries=queries,
            request_id=request_id
        )
        
        # Test initial values
        assert sub_info.query_id == query_id
        assert sub_info.queries == queries
        assert sub_info.request_id == request_id
        assert sub_info.state == SubscriptionState.PENDING
        assert sub_info.message_count == 0
        assert sub_info.error_count == 0
        
        # Test update activity
        old_activity = sub_info.last_activity
        time.sleep(0.01)  # Small delay
        sub_info.update_activity()
        assert sub_info.last_activity > old_activity
        
        # Test increment message count
        sub_info.increment_message_count()
        assert sub_info.message_count == 1
        
        # Test record error
        sub_info.record_error("test error")
        assert sub_info.error_count == 1
        assert sub_info.last_error == "test error"
        assert sub_info.state == SubscriptionState.ERROR
        
        # Test uptime and idle time
        uptime = sub_info.get_uptime()
        idle_time = sub_info.get_idle_time()
        assert uptime > 0
        assert idle_time >= 0
    
    def test_subscription_metrics_dataclass(self):
        """Test SubscriptionMetrics dataclass functionality."""
        # Create test subscription data
        query_id1 = QueryId.generate()
        query_id2 = QueryId.generate()
        
        sub_info1 = SubscriptionInfo(
            query_id=query_id1,
            queries=["SELECT * FROM table1"],
            request_id=1,
            state=SubscriptionState.ACTIVE
        )
        sub_info1.message_count = 10
        sub_info1.error_count = 1
        
        sub_info2 = SubscriptionInfo(
            query_id=query_id2,
            queries=["SELECT * FROM table2"],
            request_id=2,
            state=SubscriptionState.ERROR
        )
        sub_info2.message_count = 5
        sub_info2.error_count = 2
        
        subscriptions = {query_id1: sub_info1, query_id2: sub_info2}
        
        # Create metrics from subscription data
        metrics = SubscriptionMetrics.from_subscriptions(subscriptions)
        
        # Verify metrics
        assert metrics.total_subscriptions == 2
        assert metrics.active_subscriptions == 1
        assert metrics.error_subscriptions == 1
        assert metrics.total_messages == 15
        assert metrics.total_errors == 3
        assert metrics.error_rate == 0.2  # 3 errors / 15 messages
    
    def test_create_subscription_manager_function(self):
        """Test the convenience function for creating subscription managers."""
        manager = create_subscription_manager(
            max_subscriptions=50,
            event_manager=self.event_manager
        )
        
        assert manager is not None
        assert isinstance(manager, SubscriptionManager)
        assert manager.event_manager is self.event_manager


class TestSubscriptionManagerIntegration:
    """Integration tests for SubscriptionManager with real event system."""
    
    def test_event_integration(self):
        """Test integration with real event system."""
        try:
            from spacetimedb_sdk.events import EnhancedEventManager as RealEventManager
            event_manager = RealEventManager()
        except ImportError:
            # Use mock event manager for testing
            event_manager = Mock(spec=EnhancedEventManager)
            
        manager = SubscriptionManager(event_manager=event_manager)
        
        # Set up event capture
        received_events = []
        
        def capture_event(event):
            if isinstance(event, SubscriptionEvent):
                received_events.append(event)
        
        event_manager.subscribe(capture_event, EventType.SUBSCRIPTION)
        
        # Perform subscription operations
        query_id = QueryId.generate()
        queries = ["SELECT * FROM test_table"]
        request_id = 123
        
        manager.register_subscription(query_id, queries, request_id)
        manager.activate_subscription(query_id)
        manager.record_subscription_data(query_id, 1024)
        manager.record_subscription_error(query_id, "test error")
        manager.unregister_subscription(query_id)
        
        # Verify events were published
        assert len(received_events) >= 4  # At least register, activate, error, unregister
        
        # Check event types
        operations = [event.operation for event in received_events]
        assert "subscribe" in operations
        assert "activate" in operations
        assert "error" in operations
        assert "unsubscribe" in operations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])