"""
SpacetimeDB Advanced Subscription Builder

Provides a fluent builder API for creating and managing SpacetimeDB subscriptions,
matching the TypeScript SDK's subscription_builder() pattern.

Example usage:
    subscription = client.subscription_builder() \
        .on_applied(lambda: print("Subscription applied!")) \
        .on_error(lambda error: print(f"Subscription error: {error}")) \
        .on_subscription_applied(lambda: print("All subscriptions ready")) \
        .with_retry_policy(max_retries=3, backoff_seconds=1.0) \
        .with_timeout(30.0) \
        .subscribe(["SELECT * FROM messages", "SELECT * FROM users"])
"""

from typing import List, Dict, Callable, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
import logging
import re
import uuid
from .query_id import QueryId


class SubscriptionState(Enum):
    """Subscription state enumeration."""
    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class SubscriptionStrategy(Enum):
    """Subscription strategy enumeration."""
    SINGLE_QUERY = "single_query"      # One subscription per query
    MULTI_QUERY = "multi_query"        # One subscription for multiple queries
    ADAPTIVE = "adaptive"              # Choose based on query count and complexity


@dataclass
class SubscriptionError:
    """Information about a subscription error."""
    error_type: str
    message: str
    query_id: Optional[QueryId] = None
    query: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0


@dataclass
class SubscriptionMetrics:
    """Metrics for subscription performance monitoring."""
    subscription_id: str
    creation_time: float = field(default_factory=time.time)
    apply_time: Optional[float] = None
    error_count: int = 0
    retry_count: int = 0
    data_updates_received: int = 0
    last_update_time: Optional[float] = None
    query_count: int = 0
    
    def get_lifetime_seconds(self) -> float:
        """Get subscription lifetime in seconds."""
        return time.time() - self.creation_time
    
    def get_apply_duration_seconds(self) -> Optional[float]:
        """Get time taken to apply subscription in seconds."""
        if self.apply_time and self.creation_time:
            return self.apply_time - self.creation_time
        return None


@dataclass
class RetryPolicy:
    """Retry policy for failed subscriptions."""
    max_retries: int = 3
    backoff_seconds: float = 1.0
    exponential_backoff: bool = True
    max_backoff_seconds: float = 30.0
    
    def calculate_delay(self, retry_count: int) -> float:
        """Calculate retry delay based on policy."""
        if self.exponential_backoff:
            delay = self.backoff_seconds * (2 ** retry_count)
            return min(delay, self.max_backoff_seconds)
        return self.backoff_seconds


class AdvancedSubscriptionBuilder:
    """
    Advanced subscription builder with fluent API and comprehensive lifecycle management.
    
    Provides TypeScript SDK-compatible subscription patterns with enhanced Python-specific
    features like retry policies, metrics, and advanced error handling.
    """
    
    def __init__(self, client: 'ModernSpacetimeDBClient'):
        # Client reference
        self._client = client
        
        # Subscription configuration
        self._queries: List[str] = []
        self._strategy: SubscriptionStrategy = SubscriptionStrategy.ADAPTIVE
        self._timeout_seconds: float = 30.0
        self._retry_policy: RetryPolicy = RetryPolicy()
        
        # Callback configurations
        self._on_applied_callbacks: List[Callable[[], None]] = []
        self._on_error_callbacks: List[Callable[[SubscriptionError], None]] = []
        self._on_subscription_applied_callbacks: List[Callable[[], None]] = []
        self._on_data_update_callbacks: List[Callable[[str, Any], None]] = []  # table_name, update
        self._on_state_change_callbacks: List[Callable[[SubscriptionState, Optional[str]], None]] = []
        
        # Subscription state
        self._subscription_id: str = str(uuid.uuid4())
        self._state: SubscriptionState = SubscriptionState.PENDING
        self._query_ids: List[QueryId] = []
        self._metrics: SubscriptionMetrics = SubscriptionMetrics(self._subscription_id)
        self._errors: List[SubscriptionError] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Logging
        self.logger = logging.getLogger(__name__)
    
    def on_applied(self, callback: Callable[[], None]) -> 'AdvancedSubscriptionBuilder':
        """
        Register a callback for when the subscription is successfully applied.
        
        Args:
            callback: Function to call when subscription is applied
            
        Returns:
            Self for method chaining
            
        Example:
            builder.on_applied(lambda: print("Subscription is now active!"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_applied_callbacks.append(callback)
        return self
    
    def on_error(self, callback: Callable[[SubscriptionError], None]) -> 'AdvancedSubscriptionBuilder':
        """
        Register a callback for subscription errors.
        
        Args:
            callback: Function to call when subscription error occurs
            
        Returns:
            Self for method chaining
            
        Example:
            builder.on_error(lambda error: print(f"Subscription error: {error.message}"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_error_callbacks.append(callback)
        return self
    
    def on_subscription_applied(self, callback: Callable[[], None]) -> 'AdvancedSubscriptionBuilder':
        """
        Register a callback for when all subscriptions are applied.
        
        Args:
            callback: Function to call when all subscriptions are ready
            
        Returns:
            Self for method chaining
            
        Example:
            builder.on_subscription_applied(lambda: print("All subscriptions ready!"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_subscription_applied_callbacks.append(callback)
        return self
    
    def on_data_update(self, callback: Callable[[str, Any], None]) -> 'AdvancedSubscriptionBuilder':
        """
        Register a callback for data updates.
        
        Args:
            callback: Function to call when subscription data updates (table_name, update_data)
            
        Returns:
            Self for method chaining
            
        Example:
            builder.on_data_update(lambda table, data: print(f"Update to {table}: {data}"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_data_update_callbacks.append(callback)
        return self
    
    def on_state_change(self, callback: Callable[[SubscriptionState, Optional[str]], None]) -> 'AdvancedSubscriptionBuilder':
        """
        Register a callback for subscription state changes.
        
        Args:
            callback: Function to call when subscription state changes (new_state, reason)
            
        Returns:
            Self for method chaining
            
        Example:
            builder.on_state_change(lambda state, reason: print(f"State: {state.value}, Reason: {reason}"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_state_change_callbacks.append(callback)
        return self
    
    def with_strategy(self, strategy: SubscriptionStrategy) -> 'AdvancedSubscriptionBuilder':
        """
        Set the subscription strategy.
        
        Args:
            strategy: Subscription strategy to use
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_strategy(SubscriptionStrategy.MULTI_QUERY)
        """
        self._strategy = strategy
        return self
    
    def with_timeout(self, timeout_seconds: float) -> 'AdvancedSubscriptionBuilder':
        """
        Set subscription timeout.
        
        Args:
            timeout_seconds: Maximum time to wait for subscription to be applied
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_timeout(60.0)
        """
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        
        self._timeout_seconds = timeout_seconds
        return self
    
    def with_retry_policy(
        self,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        exponential_backoff: bool = True,
        max_backoff_seconds: float = 30.0
    ) -> 'AdvancedSubscriptionBuilder':
        """
        Configure retry policy for failed subscriptions.
        
        Args:
            max_retries: Maximum number of retry attempts
            backoff_seconds: Initial backoff delay in seconds
            exponential_backoff: Whether to use exponential backoff
            max_backoff_seconds: Maximum backoff delay
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_retry_policy(max_retries=5, backoff_seconds=2.0)
        """
        if max_retries < 0:
            raise ValueError("Max retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("Backoff seconds must be non-negative")
        
        self._retry_policy = RetryPolicy(
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            exponential_backoff=exponential_backoff,
            max_backoff_seconds=max_backoff_seconds
        )
        return self
    
    def validate_queries(self, queries: List[str]) -> List[str]:
        """
        Validate SQL queries.
        
        Args:
            queries: List of SQL queries to validate
            
        Returns:
            List of validation error messages (empty if valid)
            
        Example:
            errors = builder.validate_queries(["SELECT * FROM messages"])
        """
        errors = []
        
        for i, query in enumerate(queries):
            if not query or not query.strip():
                errors.append(f"Query {i+1}: Empty query")
                continue
            
            # Basic SQL validation (can be enhanced)
            query_upper = query.strip().upper()
            if not query_upper.startswith('SELECT'):
                errors.append(f"Query {i+1}: Only SELECT queries are supported")
                continue
            
            # Check for common SQL injection patterns (basic protection)
            suspicious_patterns = [';--', '/*', '*/', 'xp_', 'sp_cmdshell']
            for pattern in suspicious_patterns:
                if pattern in query.lower():
                    errors.append(f"Query {i+1}: Potentially unsafe pattern detected: {pattern}")
                    break
        
        return errors
    
    def _choose_strategy(self, queries: List[str]) -> SubscriptionStrategy:
        """Choose optimal subscription strategy based on queries."""
        if self._strategy != SubscriptionStrategy.ADAPTIVE:
            return self._strategy
        
        # Adaptive strategy logic
        if len(queries) == 1:
            return SubscriptionStrategy.SINGLE_QUERY
        elif len(queries) <= 5:  # Arbitrary threshold
            return SubscriptionStrategy.MULTI_QUERY
        else:
            # For many queries, use single query strategy to avoid complexity
            return SubscriptionStrategy.SINGLE_QUERY
    
    def _change_state(self, new_state: SubscriptionState, reason: Optional[str] = None) -> None:
        """Change subscription state and notify callbacks."""
        with self._lock:
            old_state = self._state
            self._state = new_state
            
            self.logger.info(f"Subscription {self._subscription_id} state: {old_state.value} -> {new_state.value}")
            if reason:
                self.logger.info(f"Reason: {reason}")
        
        # Notify state change callbacks
        for callback in self._on_state_change_callbacks:
            try:
                callback(new_state, reason)
            except Exception as e:
                self.logger.error(f"Error in state change callback: {e}")
    
    def _handle_subscription_applied(self) -> None:
        """Handle successful subscription application."""
        with self._lock:
            self._metrics.apply_time = time.time()
            self._change_state(SubscriptionState.ACTIVE, "Subscription successfully applied")
        
        # Notify applied callbacks
        for callback in self._on_applied_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in applied callback: {e}")
        
        # Notify subscription applied callbacks
        for callback in self._on_subscription_applied_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in subscription applied callback: {e}")
    
    def _handle_subscription_error(self, error: SubscriptionError) -> None:
        """Handle subscription error."""
        with self._lock:
            self._errors.append(error)
            self._metrics.error_count += 1
            
            # Determine if we should retry
            should_retry = (
                error.retry_count < self._retry_policy.max_retries and
                self._state != SubscriptionState.CANCELLED
            )
            
            if should_retry:
                self._change_state(SubscriptionState.RETRYING, f"Error occurred, retrying: {error.message}")
                self._metrics.retry_count += 1
            else:
                self._change_state(SubscriptionState.ERROR, f"Max retries exceeded: {error.message}")
        
        # Notify error callbacks
        for callback in self._on_error_callbacks:
            try:
                callback(error)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    def subscribe(self, queries: List[str]) -> 'AdvancedSubscription':
        """
        Execute the subscription with the configured queries and callbacks.
        
        Args:
            queries: List of SQL queries to subscribe to
            
        Returns:
            AdvancedSubscription object for managing the active subscription
            
        Raises:
            ValueError: If queries are invalid
            RuntimeError: If client is not connected
            
        Example:
            subscription = builder.subscribe([
                "SELECT * FROM messages WHERE sender = 'user123'",
                "SELECT * FROM notifications WHERE user_id = 'user123'"
            ])
        """
        # Validate inputs
        if not queries:
            raise ValueError("At least one query is required")
        
        validation_errors = self.validate_queries(queries)
        if validation_errors:
            raise ValueError(f"Query validation failed: {', '.join(validation_errors)}")
        
        if not self._client.is_connected:
            raise RuntimeError("Client is not connected to SpacetimeDB")
        
        # Update metrics
        with self._lock:
            self._queries = queries.copy()
            self._metrics.query_count = len(queries)
        
        # Choose subscription strategy
        strategy = self._choose_strategy(queries)
        
        try:
            # Execute subscription based on strategy
            if strategy == SubscriptionStrategy.SINGLE_QUERY:
                self._execute_single_query_strategy(queries)
            elif strategy == SubscriptionStrategy.MULTI_QUERY:
                self._execute_multi_query_strategy(queries)
            else:
                raise ValueError(f"Unsupported strategy: {strategy}")
            
            # Create and return subscription object
            return AdvancedSubscription(self)
            
        except Exception as e:
            error = SubscriptionError(
                error_type="subscription_failed",
                message=str(e),
                query=queries[0] if queries else None
            )
            self._handle_subscription_error(error)
            raise
    
    def _execute_single_query_strategy(self, queries: List[str]) -> None:
        """Execute subscriptions using single query strategy."""
        with self._lock:
            for query in queries:
                try:
                    query_id = self._client.subscribe_single(query)
                    self._query_ids.append(query_id)
                    self.logger.info(f"Subscribed to query with ID {query_id.id}: {query}")
                except Exception as e:
                    error = SubscriptionError(
                        error_type="subscribe_single_failed",
                        message=str(e),
                        query=query
                    )
                    self._handle_subscription_error(error)
                    raise
        
        # Handle successful subscription
        self._handle_subscription_applied()
    
    def _execute_multi_query_strategy(self, queries: List[str]) -> None:
        """Execute subscription using multi-query strategy."""
        try:
            query_id = self._client.subscribe_multi(queries)
            with self._lock:
                self._query_ids.append(query_id)
            
            self.logger.info(f"Subscribed to {len(queries)} queries with ID {query_id.id}")
            
            # Handle successful subscription
            self._handle_subscription_applied()
            
        except Exception as e:
            error = SubscriptionError(
                error_type="subscribe_multi_failed",
                message=str(e),
                query=queries[0] if queries else None
            )
            self._handle_subscription_error(error)
            raise
    
    def get_metrics(self) -> SubscriptionMetrics:
        """Get subscription metrics."""
        with self._lock:
            return self._metrics
    
    def get_state(self) -> SubscriptionState:
        """Get current subscription state."""
        with self._lock:
            return self._state
    
    def get_errors(self) -> List[SubscriptionError]:
        """Get list of subscription errors."""
        with self._lock:
            return self._errors.copy()


class AdvancedSubscription:
    """
    Represents an active advanced subscription with management capabilities.
    
    Provides methods to monitor, control, and interact with an active subscription
    created through the AdvancedSubscriptionBuilder.
    """
    
    def __init__(self, builder: AdvancedSubscriptionBuilder):
        self._builder = builder
        self._client = builder._client
        self.subscription_id = builder._subscription_id
        self.logger = logging.getLogger(__name__)
    
    def cancel(self) -> None:
        """
        Cancel the subscription.
        
        Unsubscribes from all associated queries and marks the subscription as cancelled.
        """
        with self._builder._lock:
            # Unsubscribe from all query IDs
            for query_id in self._builder._query_ids:
                try:
                    self._client.unsubscribe(query_id)
                    self.logger.info(f"Unsubscribed from query {query_id.id}")
                except Exception as e:
                    self.logger.error(f"Error unsubscribing from query {query_id.id}: {e}")
            
            # Update state
            self._builder._change_state(SubscriptionState.CANCELLED, "Subscription cancelled by user")
    
    def get_metrics(self) -> SubscriptionMetrics:
        """Get subscription performance metrics."""
        return self._builder.get_metrics()
    
    def get_state(self) -> SubscriptionState:
        """Get current subscription state."""
        return self._builder.get_state()
    
    def get_errors(self) -> List[SubscriptionError]:
        """Get list of subscription errors."""
        return self._builder.get_errors()
    
    def get_query_ids(self) -> List[QueryId]:
        """Get list of active query IDs."""
        with self._builder._lock:
            return self._builder._query_ids.copy()
    
    def get_queries(self) -> List[str]:
        """Get list of subscribed queries."""
        with self._builder._lock:
            return self._builder._queries.copy()
    
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.get_state() == SubscriptionState.ACTIVE
    
    def is_cancelled(self) -> bool:
        """Check if subscription has been cancelled."""
        return self.get_state() == SubscriptionState.CANCELLED
    
    def has_errors(self) -> bool:
        """Check if subscription has encountered errors."""
        return len(self.get_errors()) > 0 