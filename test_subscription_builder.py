#!/usr/bin/env python3
"""
Tests for SpacetimeDB Advanced Subscription Builder

This test suite verifies the advanced subscription builder API works correctly
and provides the same functionality as the TypeScript SDK's subscription patterns.
"""

import sys
sys.path.append('src')

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import threading

from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from spacetimedb_sdk.subscription_builder import (
    AdvancedSubscriptionBuilder,
    AdvancedSubscription,
    SubscriptionState,
    SubscriptionStrategy,
    SubscriptionError,
    SubscriptionMetrics,
    RetryPolicy
)
from spacetimedb_sdk.query_id import QueryId


class TestAdvancedSubscriptionBuilder:
    """Test the advanced subscription builder pattern implementation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mock_client = Mock(spec=ModernSpacetimeDBClient)
        self.mock_client.is_connected = True
        self.builder = AdvancedSubscriptionBuilder(self.mock_client)
    
    def test_builder_creation(self):
        """Test that subscription builder can be created from client."""
        mock_client = Mock()
        mock_client.subscription_builder.return_value = Mock(spec=AdvancedSubscriptionBuilder)
        
        builder = mock_client.subscription_builder()
        assert builder is not None
    
    def test_fluent_api_chaining(self):
        """Test that all builder methods return self for chaining."""
        def test_callback():
            pass
        
        def error_callback(error):
            pass
        
        def state_callback(state, reason):
            pass
        
        # Test method chaining
        result = (self.builder
                 .on_applied(test_callback)
                 .on_error(error_callback)
                 .on_subscription_applied(test_callback)
                 .on_data_update(lambda table, data: None)
                 .on_state_change(state_callback)
                 .with_strategy(SubscriptionStrategy.MULTI_QUERY)
                 .with_timeout(60.0)
                 .with_retry_policy(max_retries=5))
        
        assert result is self.builder
    
    def test_callback_registration(self):
        """Test callback registration and validation."""
        # Valid callbacks
        applied_callback = lambda: print("applied")
        error_callback = lambda error: print(f"error: {error}")
        data_callback = lambda table, data: print(f"data: {table}, {data}")
        state_callback = lambda state, reason: print(f"state: {state}")
        
        self.builder.on_applied(applied_callback)
        self.builder.on_error(error_callback)
        self.builder.on_data_update(data_callback)
        self.builder.on_state_change(state_callback)
        
        # Verify callbacks are registered
        assert len(self.builder._on_applied_callbacks) == 1
        assert len(self.builder._on_error_callbacks) == 1
        assert len(self.builder._on_data_update_callbacks) == 1
        assert len(self.builder._on_state_change_callbacks) == 1
        
        # Non-callable should raise error
        with pytest.raises(ValueError, match="Callback must be callable"):
            self.builder.on_applied("not_callable")
        
        with pytest.raises(ValueError, match="Callback must be callable"):
            self.builder.on_error(123)
    
    def test_subscription_strategy_configuration(self):
        """Test subscription strategy configuration."""
        # Test strategy setting
        self.builder.with_strategy(SubscriptionStrategy.SINGLE_QUERY)
        assert self.builder._strategy == SubscriptionStrategy.SINGLE_QUERY
        
        self.builder.with_strategy(SubscriptionStrategy.MULTI_QUERY)
        assert self.builder._strategy == SubscriptionStrategy.MULTI_QUERY
        
        self.builder.with_strategy(SubscriptionStrategy.ADAPTIVE)
        assert self.builder._strategy == SubscriptionStrategy.ADAPTIVE
    
    def test_timeout_configuration(self):
        """Test timeout configuration."""
        # Valid timeout
        self.builder.with_timeout(45.0)
        assert self.builder._timeout_seconds == 45.0
        
        # Invalid timeout should raise error
        with pytest.raises(ValueError, match="Timeout must be positive"):
            self.builder.with_timeout(0)
        
        with pytest.raises(ValueError, match="Timeout must be positive"):
            self.builder.with_timeout(-5.0)
    
    def test_retry_policy_configuration(self):
        """Test retry policy configuration."""
        # Valid retry policy
        self.builder.with_retry_policy(
            max_retries=5,
            backoff_seconds=2.0,
            exponential_backoff=True,
            max_backoff_seconds=60.0
        )
        
        policy = self.builder._retry_policy
        assert policy.max_retries == 5
        assert policy.backoff_seconds == 2.0
        assert policy.exponential_backoff == True
        assert policy.max_backoff_seconds == 60.0
        
        # Invalid values should raise errors
        with pytest.raises(ValueError, match="Max retries must be non-negative"):
            self.builder.with_retry_policy(max_retries=-1)
        
        with pytest.raises(ValueError, match="Backoff seconds must be non-negative"):
            self.builder.with_retry_policy(backoff_seconds=-1.0)
    
    def test_query_validation(self):
        """Test SQL query validation."""
        # Valid queries
        valid_queries = [
            "SELECT * FROM messages",
            "SELECT id, content FROM messages WHERE sender = 'user123'",
            "select count(*) from users"
        ]
        errors = self.builder.validate_queries(valid_queries)
        assert len(errors) == 0
        
        # Invalid queries
        invalid_queries = [
            "",  # Empty query
            "INSERT INTO messages VALUES (1, 'hello')",  # Non-SELECT
            "SELECT * FROM messages; DROP TABLE users;--",  # SQL injection attempt
        ]
        errors = self.builder.validate_queries(invalid_queries)
        assert len(errors) > 0
        assert any("Empty query" in error for error in errors)
        assert any("Only SELECT queries are supported" in error for error in errors)
        assert any("Potentially unsafe pattern detected" in error for error in errors)
    
    def test_strategy_selection(self):
        """Test automatic strategy selection."""
        # Single query should use SINGLE_QUERY strategy
        single_query_strategy = self.builder._choose_strategy(["SELECT * FROM messages"])
        assert single_query_strategy == SubscriptionStrategy.SINGLE_QUERY
        
        # Multiple queries (<=5) should use MULTI_QUERY strategy
        multi_queries = [f"SELECT * FROM table{i}" for i in range(3)]
        multi_query_strategy = self.builder._choose_strategy(multi_queries)
        assert multi_query_strategy == SubscriptionStrategy.MULTI_QUERY
        
        # Many queries (>5) should fall back to SINGLE_QUERY strategy
        many_queries = [f"SELECT * FROM table{i}" for i in range(10)]
        many_query_strategy = self.builder._choose_strategy(many_queries)
        assert many_query_strategy == SubscriptionStrategy.SINGLE_QUERY
        
        # When strategy is explicitly set, it should be used
        self.builder.with_strategy(SubscriptionStrategy.MULTI_QUERY)
        explicit_strategy = self.builder._choose_strategy(["SELECT * FROM messages"])
        assert explicit_strategy == SubscriptionStrategy.MULTI_QUERY
    
    def test_subscription_state_management(self):
        """Test subscription state changes and callbacks."""
        state_changes = []
        
        def state_callback(state, reason):
            state_changes.append((state, reason))
        
        self.builder.on_state_change(state_callback)
        
        # Test state changes
        self.builder._change_state(SubscriptionState.ACTIVE, "Subscription applied")
        assert self.builder.get_state() == SubscriptionState.ACTIVE
        assert len(state_changes) == 1
        assert state_changes[0] == (SubscriptionState.ACTIVE, "Subscription applied")
        
        self.builder._change_state(SubscriptionState.ERROR, "Connection lost")
        assert self.builder.get_state() == SubscriptionState.ERROR
        assert len(state_changes) == 2
        assert state_changes[1] == (SubscriptionState.ERROR, "Connection lost")
    
    def test_subscription_metrics(self):
        """Test subscription metrics tracking."""
        metrics = self.builder.get_metrics()
        
        # Check initial metrics
        assert metrics.subscription_id == self.builder._subscription_id
        assert metrics.error_count == 0
        assert metrics.retry_count == 0
        assert metrics.query_count == 0
        assert metrics.creation_time > 0
        
        # Test metrics update
        self.builder._metrics.query_count = 3
        self.builder._metrics.error_count = 1
        
        updated_metrics = self.builder.get_metrics()
        assert updated_metrics.query_count == 3
        assert updated_metrics.error_count == 1
    
    def test_subscription_error_handling(self):
        """Test subscription error handling and recovery."""
        errors_received = []
        
        def error_callback(error):
            errors_received.append(error)
        
        self.builder.on_error(error_callback)
        
        # Create and handle an error
        error = SubscriptionError(
            error_type="test_error",
            message="Test error message",
            query="SELECT * FROM test"
        )
        
        self.builder._handle_subscription_error(error)
        
        # Verify error was recorded
        assert len(self.builder.get_errors()) == 1
        assert len(errors_received) == 1
        assert errors_received[0] == error
        assert self.builder.get_metrics().error_count == 1
    
    def test_single_query_subscription(self):
        """Test subscription using single query strategy."""
        # Setup mock QueryId
        mock_query_id = Mock(spec=QueryId)
        mock_query_id.id = "test_query_id_123"
        self.mock_client.subscribe_single.return_value = mock_query_id
        
        applied_callbacks = []
        subscription_applied_callbacks = []
        
        # Setup callbacks
        self.builder.on_applied(lambda: applied_callbacks.append("applied"))
        self.builder.on_subscription_applied(lambda: subscription_applied_callbacks.append("sub_applied"))
        
        # Execute subscription
        queries = ["SELECT * FROM messages"]
        subscription = self.builder.subscribe(queries)
        
        # Verify subscription was created
        assert isinstance(subscription, AdvancedSubscription)
        assert self.mock_client.subscribe_single.called
        assert len(self.builder._query_ids) == 1
        assert self.builder._query_ids[0] == mock_query_id
        assert self.builder.get_state() == SubscriptionState.ACTIVE
        
        # Verify callbacks were called
        assert len(applied_callbacks) == 1
        assert len(subscription_applied_callbacks) == 1
    
    def test_multi_query_subscription(self):
        """Test subscription using multi-query strategy."""
        # Setup mock QueryId
        mock_query_id = Mock(spec=QueryId)
        mock_query_id.id = "test_multi_query_id_456"
        self.mock_client.subscribe_multi.return_value = mock_query_id
        
        # Force multi-query strategy
        self.builder.with_strategy(SubscriptionStrategy.MULTI_QUERY)
        
        # Execute subscription
        queries = ["SELECT * FROM messages", "SELECT * FROM users"]
        subscription = self.builder.subscribe(queries)
        
        # Verify subscription was created
        assert isinstance(subscription, AdvancedSubscription)
        assert self.mock_client.subscribe_multi.called
        assert len(self.builder._query_ids) == 1
        assert self.builder._query_ids[0] == mock_query_id
        assert self.builder.get_state() == SubscriptionState.ACTIVE
    
    def test_subscription_validation_errors(self):
        """Test subscription validation and error cases."""
        # Empty queries should raise error
        with pytest.raises(ValueError, match="At least one query is required"):
            self.builder.subscribe([])
        
        # Invalid queries should raise error
        with pytest.raises(ValueError, match="Query validation failed"):
            self.builder.subscribe(["INSERT INTO messages VALUES (1, 'test')"])
        
        # Disconnected client should raise error
        self.mock_client.is_connected = False
        with pytest.raises(RuntimeError, match="Client is not connected"):
            self.builder.subscribe(["SELECT * FROM messages"])
    
    def test_typescript_sdk_compatibility(self):
        """Test that the API matches TypeScript SDK patterns."""
        # Setup mock client and responses
        mock_query_id = Mock(spec=QueryId)
        mock_query_id.id = "test_query_id_789"
        self.mock_client.subscribe_multi.return_value = mock_query_id
        
        # This should match TypeScript SDK patterns exactly
        callbacks_called = {
            'applied': False,
            'error': False,
            'subscription_applied': False,
            'state_change': False
        }
        
        def on_applied():
            callbacks_called['applied'] = True
        
        def on_error(error):
            callbacks_called['error'] = True
        
        def on_subscription_applied():
            callbacks_called['subscription_applied'] = True
        
        def on_state_change(state, reason):
            callbacks_called['state_change'] = True
        
        # Build subscription with TypeScript-like API
        subscription = (self.builder
                       .on_applied(on_applied)
                       .on_error(on_error)
                       .on_subscription_applied(on_subscription_applied)
                       .on_state_change(on_state_change)
                       .with_timeout(30.0)
                       .with_retry_policy(max_retries=3)
                       .subscribe([
                           "SELECT * FROM messages WHERE user_id = 'user123'",
                           "SELECT * FROM notifications WHERE user_id = 'user123'"
                       ]))
        
        # Verify subscription was created successfully
        assert isinstance(subscription, AdvancedSubscription)
        assert subscription.is_active()
        assert not subscription.is_cancelled()
        
        # Verify callbacks were called appropriately
        assert callbacks_called['applied']
        assert callbacks_called['subscription_applied']
        assert callbacks_called['state_change']
        assert not callbacks_called['error']  # No errors should have occurred


class TestAdvancedSubscription:
    """Test the AdvancedSubscription class functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mock_client = Mock(spec=ModernSpacetimeDBClient)
        self.mock_client.is_connected = True
        
        # Create builder and subscription
        self.builder = AdvancedSubscriptionBuilder(self.mock_client)
        
        # Mock query IDs
        self.mock_query_id1 = Mock(spec=QueryId)
        self.mock_query_id1.id = "query_1"
        self.mock_query_id2 = Mock(spec=QueryId)
        self.mock_query_id2.id = "query_2"
        
        self.builder._query_ids = [self.mock_query_id1, self.mock_query_id2]
        self.builder._queries = ["SELECT * FROM messages", "SELECT * FROM users"]
        self.builder._state = SubscriptionState.ACTIVE
        
        self.subscription = AdvancedSubscription(self.builder)
    
    def test_subscription_properties(self):
        """Test subscription property access."""
        assert self.subscription.subscription_id == self.builder._subscription_id
        assert self.subscription.is_active()
        assert not self.subscription.is_cancelled()
        assert not self.subscription.has_errors()
        
        # Test query access
        query_ids = self.subscription.get_query_ids()
        assert len(query_ids) == 2
        assert query_ids[0] == self.mock_query_id1
        assert query_ids[1] == self.mock_query_id2
        
        queries = self.subscription.get_queries()
        assert len(queries) == 2
        assert queries[0] == "SELECT * FROM messages"
        assert queries[1] == "SELECT * FROM users"
    
    def test_subscription_cancellation(self):
        """Test subscription cancellation."""
        # Cancel the subscription
        self.subscription.cancel()
        
        # Verify unsubscribe was called for all query IDs
        assert self.mock_client.unsubscribe.call_count == 2
        
        # Verify state was updated
        assert self.subscription.is_cancelled()
        assert not self.subscription.is_active()
    
    def test_subscription_metrics_access(self):
        """Test subscription metrics access."""
        metrics = self.subscription.get_metrics()
        assert isinstance(metrics, SubscriptionMetrics)
        assert metrics.subscription_id == self.builder._subscription_id
    
    def test_subscription_with_errors(self):
        """Test subscription error handling."""
        # Add some errors to the builder
        error1 = SubscriptionError("test_error", "Test error 1")
        error2 = SubscriptionError("test_error", "Test error 2")
        
        self.builder._errors = [error1, error2]
        
        # Test error access
        errors = self.subscription.get_errors()
        assert len(errors) == 2
        assert self.subscription.has_errors()


class TestRetryPolicy:
    """Test retry policy functionality."""
    
    def test_retry_policy_delay_calculation(self):
        """Test retry delay calculation."""
        # Linear backoff
        linear_policy = RetryPolicy(
            max_retries=3,
            backoff_seconds=2.0,
            exponential_backoff=False,
            max_backoff_seconds=10.0
        )
        
        assert linear_policy.calculate_delay(0) == 2.0
        assert linear_policy.calculate_delay(1) == 2.0
        assert linear_policy.calculate_delay(2) == 2.0
        
        # Exponential backoff
        exp_policy = RetryPolicy(
            max_retries=5,
            backoff_seconds=1.0,
            exponential_backoff=True,
            max_backoff_seconds=8.0
        )
        
        assert exp_policy.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert exp_policy.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert exp_policy.calculate_delay(2) == 4.0  # 1.0 * 2^2
        assert exp_policy.calculate_delay(3) == 8.0  # 1.0 * 2^3, capped at max
        assert exp_policy.calculate_delay(4) == 8.0  # 1.0 * 2^4 = 16, but capped at 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 