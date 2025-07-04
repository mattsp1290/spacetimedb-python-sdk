"""
SubscriptionManager for SpacetimeDB SDK - Refactoring Test Implementation

A focused, reusable subscription management module extracted from the monolithic
WebSocket client. Provides clean APIs for subscription lifecycle management,
QueryId tracking, health monitoring, and event integration.

Key Features:
- QueryId management and tracking
- Subscription state lifecycle (pending, active, error, closed)
- Health metrics integration (message counts, error rates)
- Multiple subscription type support
- Thread-safe operations
- Event integration for subscription changes
- Memory-bounded subscription tracking
"""

import logging
import threading
import time
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Callable, Union
from dataclasses import dataclass, field

from ..query_id import QueryId
from ..memory_management import BoundedDict, MemoryAccountant

# Import events with fallback for compatibility
try:
    from ..events import (
        UnifiedEventManager, EventType, EventContext, EventPriority
    )
    
    def get_event_manager():
        """Get the default event manager."""
        return UnifiedEventManager()
    
    def publish_event(event_type, context, manager=None):
        """Publish an event."""
        if manager:
            manager.emit(event_type, context)
    
    # Create a subscription event for compatibility
    class SubscriptionEvent:
        def __init__(self, **kwargs):
            self.data = kwargs
    
except ImportError:
    # Fallback for testing - create minimal stubs
    class UnifiedEventManager:
        def emit(self, event_type, context): pass
    
    class EventType:
        SUBSCRIPTION_APPLIED = "subscription_applied"
        SUBSCRIPTION_ERROR = "subscription_error"
        SUBSCRIPTION_CLOSED = "subscription_closed"
    
    class EventContext:
        def __init__(self, **kwargs):
            self.data = kwargs
        
        @classmethod
        def create(cls, **kwargs):
            return cls(**kwargs)
    
    class EventPriority:
        MEDIUM = "medium"
    
    class SubscriptionEvent:
        def __init__(self, **kwargs):
            self.data = kwargs
    
    def get_event_manager():
        return UnifiedEventManager()
    
    def publish_event(event_type, context, manager=None):
        pass


class SubscriptionState(Enum):
    """Subscription lifecycle states."""
    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class SubscriptionInfo:
    """Information about a subscription."""
    query_id: QueryId
    queries: List[str]
    request_id: int
    state: SubscriptionState = SubscriptionState.PENDING
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    message_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def increment_message_count(self) -> None:
        """Increment message count and update activity."""
        self.message_count += 1
        self.update_activity()
    
    def record_error(self, error: str) -> None:
        """Record an error for this subscription."""
        self.error_count += 1
        self.last_error = error
        self.state = SubscriptionState.ERROR
        self.update_activity()
    
    def get_uptime(self) -> float:
        """Get subscription uptime in seconds."""
        return time.time() - self.created_at
    
    def get_idle_time(self) -> float:
        """Get time since last activity in seconds."""
        return time.time() - self.last_activity


@dataclass
class SubscriptionMetrics:
    """Comprehensive subscription metrics."""
    total_subscriptions: int = 0
    active_subscriptions: int = 0
    pending_subscriptions: int = 0
    error_subscriptions: int = 0
    closed_subscriptions: int = 0
    total_messages: int = 0
    total_errors: int = 0
    average_uptime: float = 0.0
    error_rate: float = 0.0
    
    @classmethod
    def from_subscriptions(cls, subscriptions: Dict[QueryId, SubscriptionInfo]) -> 'SubscriptionMetrics':
        """Create metrics from subscription data."""
        if not subscriptions:
            return cls()
        
        state_counts = defaultdict(int)
        total_messages = 0
        total_errors = 0
        total_uptime = 0.0
        
        for sub_info in subscriptions.values():
            state_counts[sub_info.state] += 1
            total_messages += sub_info.message_count
            total_errors += sub_info.error_count
            total_uptime += sub_info.get_uptime()
        
        total_count = len(subscriptions)
        average_uptime = total_uptime / total_count if total_count > 0 else 0.0
        error_rate = total_errors / max(total_messages, 1)
        
        return cls(
            total_subscriptions=total_count,
            active_subscriptions=state_counts[SubscriptionState.ACTIVE],
            pending_subscriptions=state_counts[SubscriptionState.PENDING],
            error_subscriptions=state_counts[SubscriptionState.ERROR],
            closed_subscriptions=state_counts[SubscriptionState.CLOSED],
            total_messages=total_messages,
            total_errors=total_errors,
            average_uptime=average_uptime,
            error_rate=error_rate
        )


class SubscriptionManager:
    """
    Manages subscription lifecycle, QueryId tracking, and health monitoring.
    
    This class provides a clean API for subscription management that was
    previously embedded in the WebSocket client. It handles:
    - QueryId generation and tracking
    - Subscription state management
    - Health metrics and monitoring
    - Event integration for subscription changes
    - Thread-safe operations
    """
    
    def __init__(
        self,
        max_subscriptions: int = 1000,
        memory_accountant: Optional[MemoryAccountant] = None,
        event_manager: Optional[UnifiedEventManager] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the subscription manager.
        
        Args:
            max_subscriptions: Maximum number of concurrent subscriptions
            memory_accountant: Memory accounting for bounded storage
            event_manager: Event manager for subscription events
            logger: Logger for subscription operations
        """
        self.logger = logger or logging.getLogger(__name__)
        self.event_manager = event_manager or get_event_manager()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Core subscription tracking
        self._subscriptions = BoundedDict(
            max_size=max_subscriptions,
            memory_accountant=memory_accountant
        )
        
        # Request ID to QueryId mapping for tracking responses
        self._request_to_query = BoundedDict(
            max_size=max_subscriptions,
            memory_accountant=memory_accountant
        )
        
        # Query string to QueryId mapping for duplicate detection
        self._query_hash_to_id: Dict[str, Set[QueryId]] = defaultdict(set)
        
        # State tracking
        self._state_counts = defaultdict(int)
        self._total_messages = 0
        self._total_errors = 0
        
        # Health monitoring
        self._health_check_interval = 30  # seconds
        self._last_health_check = time.time()
        
        # Event callbacks
        self._state_change_callbacks: List[Callable[[QueryId, SubscriptionState, SubscriptionState], None]] = []
        
        self.logger.info("SubscriptionManager initialized")
    
    def register_subscription(
        self,
        query_id: QueryId,
        queries: List[str],
        request_id: int
    ) -> None:
        """
        Register a new subscription.
        
        Args:
            query_id: The QueryId for this subscription
            queries: List of SQL queries for this subscription
            request_id: The request ID for tracking responses
        """
        with self._lock:
            # Create subscription info
            sub_info = SubscriptionInfo(
                query_id=query_id,
                queries=queries,
                request_id=request_id,
                state=SubscriptionState.PENDING
            )
            
            # Store subscription
            self._subscriptions.set(query_id, sub_info)
            self._request_to_query.set(request_id, query_id)
            
            # Update query hash mapping
            query_hash = self._hash_queries(queries)
            self._query_hash_to_id[query_hash].add(query_id)
            
            # Update state counts
            self._state_counts[SubscriptionState.PENDING] += 1
            
            # Publish event
            self._publish_subscription_event(
                event_type=EventType.SUBSCRIPTION_APPLIED,
                query_id=str(query_id.id),
                sql_query="; ".join(queries),
                operation="subscribe",
                success=True
            )
            
            self.logger.debug(f"Registered subscription {query_id} with {len(queries)} queries")
    
    def activate_subscription(self, query_id: QueryId) -> bool:
        """
        Activate a pending subscription.
        
        Args:
            query_id: The QueryId to activate
            
        Returns:
            True if successfully activated, False otherwise
        """
        with self._lock:
            sub_info = self._subscriptions.get(query_id)
            if not sub_info:
                self.logger.warning(f"Cannot activate unknown subscription {query_id}")
                return False
            
            if sub_info.state != SubscriptionState.PENDING:
                self.logger.warning(f"Cannot activate subscription {query_id} in state {sub_info.state}")
                return False
            
            # Update state
            old_state = sub_info.state
            sub_info.state = SubscriptionState.ACTIVE
            sub_info.update_activity()
            
            # Update counts
            self._state_counts[old_state] -= 1
            self._state_counts[SubscriptionState.ACTIVE] += 1
            
            # Notify callbacks
            self._notify_state_change(query_id, old_state, SubscriptionState.ACTIVE)
            
            # Publish event
            self._publish_subscription_event(
                event_type=EventType.SUBSCRIPTION_APPLIED,
                query_id=str(query_id.id),
                sql_query="; ".join(sub_info.queries),
                operation="activate",
                success=True
            )
            
            self.logger.debug(f"Activated subscription {query_id}")
            return True
    
    def activate_subscription_by_request(self, request_id: int) -> bool:
        """
        Activate a subscription by request ID.
        
        Args:
            request_id: The request ID to activate
            
        Returns:
            True if successfully activated, False otherwise
        """
        with self._lock:
            query_id = self._request_to_query.get(request_id)
            if not query_id:
                self.logger.warning(f"Cannot activate unknown request {request_id}")
                return False
            
            return self.activate_subscription(query_id)
    
    def record_subscription_data(self, query_id: QueryId, data_size: int) -> None:
        """
        Record data received for a subscription.
        
        Args:
            query_id: The QueryId that received data
            data_size: Size of the data in bytes
        """
        with self._lock:
            sub_info = self._subscriptions.get(query_id)
            if not sub_info:
                self.logger.warning(f"Received data for unknown subscription {query_id}")
                return
            
            sub_info.increment_message_count()
            self._total_messages += 1
            
            # Ensure subscription is active
            if sub_info.state == SubscriptionState.PENDING:
                self.activate_subscription(query_id)
            
            self.logger.debug(f"Recorded data for subscription {query_id}: {data_size} bytes")
    
    def record_subscription_error(self, query_id: QueryId, error: str) -> None:
        """
        Record an error for a subscription.
        
        Args:
            query_id: The QueryId that had an error
            error: Error message
        """
        with self._lock:
            sub_info = self._subscriptions.get(query_id)
            if not sub_info:
                self.logger.warning(f"Received error for unknown subscription {query_id}")
                return
            
            old_state = sub_info.state
            sub_info.record_error(error)
            
            # Update counts
            if old_state != SubscriptionState.ERROR:
                self._state_counts[old_state] -= 1
                self._state_counts[SubscriptionState.ERROR] += 1
            
            self._total_errors += 1
            
            # Notify callbacks
            self._notify_state_change(query_id, old_state, SubscriptionState.ERROR)
            
            # Publish event
            self._publish_subscription_event(
                event_type=EventType.SUBSCRIPTION_ERROR,
                query_id=str(query_id.id),
                sql_query="; ".join(sub_info.queries),
                operation="error",
                success=False,
                error=error
            )
            
            self.logger.error(f"Recorded error for subscription {query_id}: {error}")
    
    def unregister_subscription(self, query_id: QueryId) -> bool:
        """
        Unregister a subscription.
        
        Args:
            query_id: The QueryId to unregister
            
        Returns:
            True if successfully unregistered, False otherwise
        """
        with self._lock:
            sub_info = self._subscriptions.get(query_id)
            if not sub_info:
                self.logger.warning(f"Cannot unregister unknown subscription {query_id}")
                return False
            
            # Update state
            old_state = sub_info.state
            sub_info.state = SubscriptionState.CLOSED
            
            # Update counts
            self._state_counts[old_state] -= 1
            self._state_counts[SubscriptionState.CLOSED] += 1
            
            # Remove from tracking
            self._subscriptions.delete(query_id)
            self._request_to_query.delete(sub_info.request_id)
            
            # Update query hash mapping
            query_hash = self._hash_queries(sub_info.queries)
            self._query_hash_to_id[query_hash].discard(query_id)
            if not self._query_hash_to_id[query_hash]:
                del self._query_hash_to_id[query_hash]
            
            # Notify callbacks
            self._notify_state_change(query_id, old_state, SubscriptionState.CLOSED)
            
            # Publish event
            self._publish_subscription_event(
                event_type=EventType.SUBSCRIPTION_CLOSED,
                query_id=str(query_id.id),
                sql_query="; ".join(sub_info.queries),
                operation="unsubscribe",
                success=True
            )
            
            self.logger.debug(f"Unregistered subscription {query_id}")
            return True
    
    def get_subscription_info(self, query_id: QueryId) -> Optional[SubscriptionInfo]:
        """
        Get information about a subscription.
        
        Args:
            query_id: The QueryId to get info for
            
        Returns:
            SubscriptionInfo if found, None otherwise
        """
        with self._lock:
            return self._subscriptions.get(query_id)
    
    def get_subscription_by_request(self, request_id: int) -> Optional[SubscriptionInfo]:
        """
        Get subscription by request ID.
        
        Args:
            request_id: The request ID to look up
            
        Returns:
            SubscriptionInfo if found, None otherwise
        """
        with self._lock:
            query_id = self._request_to_query.get(request_id)
            if not query_id:
                return None
            return self._subscriptions.get(query_id)
    
    def find_subscriptions_by_query(self, queries: List[str]) -> List[QueryId]:
        """
        Find subscriptions that match the given queries.
        
        Args:
            queries: List of SQL queries to match
            
        Returns:
            List of QueryIds that match the queries
        """
        with self._lock:
            query_hash = self._hash_queries(queries)
            return list(self._query_hash_to_id.get(query_hash, set()))
    
    def get_active_subscriptions(self) -> List[QueryId]:
        """Get all active subscription QueryIds."""
        with self._lock:
            return [
                query_id for query_id, sub_info in self._subscriptions.items()
                if sub_info.state == SubscriptionState.ACTIVE
            ]
    
    def get_subscription_count(self, state: Optional[SubscriptionState] = None) -> int:
        """
        Get subscription count by state.
        
        Args:
            state: Specific state to count, or None for total
            
        Returns:
            Number of subscriptions in the given state
        """
        with self._lock:
            if state is None:
                return len(self._subscriptions)
            return self._state_counts[state]
    
    def get_subscription_metrics(self) -> SubscriptionMetrics:
        """Get comprehensive subscription metrics."""
        with self._lock:
            return SubscriptionMetrics.from_subscriptions(dict(self._subscriptions.items()))
    
    def get_subscription_health(self, query_id: QueryId) -> Dict[str, Any]:
        """
        Get health metrics for a specific subscription.
        
        Args:
            query_id: The QueryId to get health for
            
        Returns:
            Dictionary with health metrics
        """
        with self._lock:
            sub_info = self._subscriptions.get(query_id)
            if not sub_info:
                return {'status': 'not_found'}
            
            idle_time = sub_info.get_idle_time()
            uptime = sub_info.get_uptime()
            
            # Determine health status
            if sub_info.state == SubscriptionState.ERROR:
                status = 'error'
            elif sub_info.state == SubscriptionState.CLOSED:
                status = 'closed'
            elif sub_info.state == SubscriptionState.PENDING:
                status = 'pending'
            elif idle_time > 300:  # 5 minutes
                status = 'stale'
            elif idle_time > 60:  # 1 minute
                status = 'warning'
            else:
                status = 'healthy'
            
            error_rate = sub_info.error_count / max(sub_info.message_count, 1)
            
            return {
                'status': status,
                'state': sub_info.state.value,
                'message_count': sub_info.message_count,
                'error_count': sub_info.error_count,
                'error_rate': error_rate,
                'uptime_seconds': uptime,
                'idle_seconds': idle_time,
                'last_error': sub_info.last_error,
                'queries': sub_info.queries
            }
    
    def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check.
        
        Returns:
            Dictionary with health check results
        """
        with self._lock:
            current_time = time.time()
            
            # Check if health check is needed
            if current_time - self._last_health_check < self._health_check_interval:
                return {'status': 'skipped', 'reason': 'too_soon'}
            
            self._last_health_check = current_time
            
            # Get overall metrics
            metrics = self.get_subscription_metrics()
            
            # Check for stale subscriptions
            stale_subscriptions = []
            for query_id, sub_info in self._subscriptions.items():
                if sub_info.get_idle_time() > 300:  # 5 minutes
                    stale_subscriptions.append(query_id)
            
            # Overall health status
            if metrics.error_rate > 0.5:
                overall_status = 'critical'
            elif metrics.error_rate > 0.1 or len(stale_subscriptions) > 0:
                overall_status = 'warning'
            else:
                overall_status = 'healthy'
            
            health_report = {
                'status': overall_status,
                'timestamp': current_time,
                'metrics': metrics,
                'stale_subscriptions': len(stale_subscriptions),
                'total_subscriptions': len(self._subscriptions),
                'active_subscriptions': metrics.active_subscriptions,
                'error_rate': metrics.error_rate
            }
            
            self.logger.info(f"Health check completed: {overall_status}")
            return health_report
    
    def add_state_change_callback(self, callback: Callable[[QueryId, SubscriptionState, SubscriptionState], None]) -> None:
        """
        Add a callback for subscription state changes.
        
        Args:
            callback: Function to call on state changes
        """
        with self._lock:
            self._state_change_callbacks.append(callback)
    
    def remove_state_change_callback(self, callback: Callable[[QueryId, SubscriptionState, SubscriptionState], None]) -> None:
        """
        Remove a state change callback.
        
        Args:
            callback: Function to remove
        """
        with self._lock:
            if callback in self._state_change_callbacks:
                self._state_change_callbacks.remove(callback)
    
    def clear_all_subscriptions(self) -> None:
        """Clear all subscriptions and reset state."""
        with self._lock:
            # Get all subscription IDs for cleanup
            subscription_ids = list(self._subscriptions.keys())
            
            # Clear all data structures
            self._subscriptions.clear()
            self._request_to_query.clear()
            self._query_hash_to_id.clear()
            self._state_counts.clear()
            self._total_messages = 0
            self._total_errors = 0
            
            # Publish events for cleared subscriptions
            for query_id in subscription_ids:
                self._publish_subscription_event(
                    event_type=EventType.SUBSCRIPTION_CLOSED,
                    query_id=str(query_id.id),
                    operation="clear",
                    success=True
                )
            
            self.logger.info(f"Cleared {len(subscription_ids)} subscriptions")
    
    def _hash_queries(self, queries: List[str]) -> str:
        """Create a hash for a list of queries."""
        return str(hash(tuple(sorted(queries))))
    
    def _notify_state_change(self, query_id: QueryId, old_state: SubscriptionState, new_state: SubscriptionState) -> None:
        """Notify all callbacks of a state change."""
        for callback in self._state_change_callbacks:
            try:
                callback(query_id, old_state, new_state)
            except Exception as e:
                self.logger.error(f"Error in state change callback: {e}")
    
    def _publish_subscription_event(
        self,
        event_type,
        query_id: Optional[str] = None,
        table_name: Optional[str] = None,
        sql_query: Optional[str] = None,
        operation: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """Publish a subscription event."""
        if not self.event_manager:
            return
        
        try:
            context = EventContext.create(
                event_type=event_type,
                source="subscription_manager",
                query_id=query_id,
                table_name=table_name,
                sql_query=sql_query,
                operation=operation,
                success=success,
                error=error
            )
            
            publish_event(event_type, context, self.event_manager)
        except Exception as e:
            self.logger.error(f"Error publishing subscription event: {e}")


# Convenience functions for common operations
def create_subscription_manager(
    max_subscriptions: int = 1000,
    memory_accountant: Optional[MemoryAccountant] = None,
    event_manager: Optional[UnifiedEventManager] = None
) -> SubscriptionManager:
    """
    Create a new subscription manager with standard configuration.
    
    Args:
        max_subscriptions: Maximum number of concurrent subscriptions
        memory_accountant: Memory accounting for bounded storage
        event_manager: Event manager for subscription events
        
    Returns:
        Configured SubscriptionManager instance
    """
    return SubscriptionManager(
        max_subscriptions=max_subscriptions,
        memory_accountant=memory_accountant,
        event_manager=event_manager
    )