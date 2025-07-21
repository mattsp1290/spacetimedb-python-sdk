"""
SubscriptionManager for SpacetimeDB SDK

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
from ..serialization import _safe_extract, _get_message_type
from ..utils.error_formatting import ErrorFormatter
# Import events with fallback for compatibility
try:
    from ..events import (
        UnifiedEventManager as EnhancedEventManager, SubscriptionEvent, EventType, EventPriority,
        get_event_manager, emit_event as publish_event
    )
except ImportError:
    # Fallback for testing - create minimal stubs
    class EnhancedEventManager:
        def publish_event(self, event): pass
    
    class SubscriptionEvent:
        def __init__(self, **kwargs): pass
    
    class EventType:
        SUBSCRIPTION = "subscription"
    
    class EventPriority:
        MEDIUM = "medium"
    
    def get_event_manager():
        """Get the global event manager, fallback to NullEventManager if unavailable."""
        try:
            from ..events import get_event_manager as get_unified_manager
            return get_unified_manager()
        except ImportError:
            # Fallback to null object pattern
            return type('NullEventManager', (), {
                'emit': lambda self, *args, **kwargs: None,
                'emit_event': lambda self, *args, **kwargs: None,
                'on': lambda self, *args, **kwargs: None,
                'off': lambda self, *args, **kwargs: None,
                'subscribe': lambda self, *args, **kwargs: None,
                'unsubscribe': lambda self, *args, **kwargs: None,
            })()
    def publish_event(event, manager=None): pass


class SubscriptionState(Enum):
    """Subscription lifecycle states."""
    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    FAILED = "failed"  # Alias for ERROR for backward compatibility
    CLOSED = "closed"
    CANCELLED = "cancelled"  # Alias for CLOSED for backward compatibility


@dataclass
class SubscriptionInfo:
    """Information about a subscription."""
    query_id: QueryId
    queries: List[str]
    request_id: int
    state: SubscriptionState = SubscriptionState.PENDING
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    last_update: Optional[float] = None  # For backward compatibility
    message_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    callback: Optional[Callable[[Any], None]] = None  # For backward compatibility
    table_name: Optional[str] = None  # For backward compatibility
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
        self.last_update = self.last_activity  # Keep both in sync for backward compatibility
    
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
        event_manager: Optional[EnhancedEventManager] = None,
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
        self._subscriptions = BoundedDict[QueryId, SubscriptionInfo](
            max_size=max_subscriptions,
            memory_accountant=memory_accountant
        )
        
        # Request ID to QueryId mapping for tracking responses
        self._request_to_query = BoundedDict[int, QueryId](
            max_size=max_subscriptions,
            memory_accountant=memory_accountant
        )
        
        # Query string to QueryId mapping for duplicate detection
        self._query_hash_to_id: Dict[str, Set[QueryId]] = defaultdict(set)
        
        # State tracking
        self._state_counts = defaultdict(int)
        self._total_messages = 0
        self._total_errors = 0
        
        # Backward compatibility: table-name based tracking
        self._table_name_to_query_id: Dict[str, QueryId] = {}
        self._subscription_callbacks: Dict[str, Callable[[Any], None]] = {}
        self._last_update_times: Dict[str, float] = {}
        
        # Configuration for backward compatibility
        self.subscription_timeout = 30.0  # seconds
        self.max_error_count = 5
        
        # Health monitoring
        self._health_check_interval = 30  # seconds
        self._last_health_check = time.time()
        
        # Event callbacks
        self._state_change_callbacks: List[Callable[[QueryId, SubscriptionState, SubscriptionState], None]] = []
        
        self.logger.info("SubscriptionManager initialized")
    
    def register_subscription(
        self,
        query_id: QueryId = None,
        queries: List[str] = None,
        request_id: int = None,
        table_name: str = None,
        query: str = None,
        callback: Optional[Callable[[Any], None]] = None
    ) -> None:
        """
        Register a new subscription with backward compatibility support.
        
        Supports both new-style (query_id, queries) and old-style (table_name, query) APIs.
        
        Args:
            query_id: The QueryId for this subscription (new API)
            queries: List of SQL queries for this subscription (new API)
            request_id: The request ID for tracking responses
            table_name: Name of the table to subscribe to (old API)
            query: SQL query string (old API)
            callback: Optional callback function for updates (old API)
        """
        with self._lock:
            # Handle both API styles
            if query_id is not None and queries is not None:
                # New-style API
                self._register_subscription_new_style(query_id, queries, request_id)
            elif table_name is not None and query is not None and request_id is not None:
                # Old-style API
                self._register_subscription_old_style(table_name, query, request_id, callback)
            else:
                raise ValueError("Must provide either (query_id, queries) or (table_name, query, request_id)")
    
    def activate_subscription(self, query_id: QueryId = None, table_name: str = None) -> bool:
        """
        Activate a subscription with backward compatibility support.
        
        Args:
            query_id: The QueryId to activate (new API)
            table_name: The table name to activate (old API)
            
        Returns:
            True if successfully activated, False otherwise
        """
        with self._lock:
            # Handle both API styles
            if query_id is not None:
                return self._activate_subscription_by_query_id(query_id)
            elif table_name is not None:
                return self._activate_subscription_by_table_name(table_name)
            else:
                raise ValueError("Must provide either query_id or table_name")
    
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
                query_id=str(query_id.id),
                sql_query="; ".join(sub_info.queries),
                operation="error",
                success=False,
                error=error
            )
            
            self.logger.error(f"Recorded error for subscription {query_id}: {error}")
    
    def unregister_subscription(self, query_id: QueryId = None, table_name: str = None) -> bool:
        """
        Unregister a subscription with backward compatibility support.
        
        Args:
            query_id: The QueryId to unregister (new API)
            table_name: The table name to unregister (old API)
            
        Returns:
            True if unregistered, False if not found
        """
        with self._lock:
            # Handle both API styles
            if query_id is not None:
                return self._unregister_subscription_by_query_id(query_id)
            elif table_name is not None:
                return self._unregister_subscription_by_table_name(table_name)
            else:
                raise ValueError("Must provide either query_id or table_name")
    
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
                    query_id=str(query_id.id),
                    operation="clear",
                    success=True
                )
            
            self.logger.info(f"Cleared {len(subscription_ids)} subscriptions")
    
    def _hash_queries(self, queries: List[str]) -> str:
        """Create a hash for a list of queries."""
        return hash(tuple(sorted(queries)))
    
    def _notify_state_change(self, query_id: QueryId, old_state: SubscriptionState, new_state: SubscriptionState) -> None:
        """Notify all callbacks of a state change."""
        for callback in self._state_change_callbacks:
            try:
                callback(query_id, old_state, new_state)
            except Exception as e:
                self.logger.error(f"Error in state change callback: {e}")
    
    def _publish_subscription_event(
        self,
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
            event = SubscriptionEvent(
                query_id=query_id,
                table_name=table_name,
                sql_query=sql_query,
                operation=operation,
                success=success,
                error=error,
                priority=EventPriority.MEDIUM
            )
            
            publish_event(event, self.event_manager)
        except Exception as e:
            self.logger.error(f"Error publishing subscription event: {e}")
    
    # Backward compatibility methods from root-level subscription_manager.py
    
    def _register_subscription_new_style(self, query_id: QueryId, queries: List[str], request_id: int) -> None:
        """Register subscription using new QueryId-based API."""
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
            query_id=str(query_id.id),
            sql_query="; ".join(queries),
            operation="subscribe",
            success=True
        )
        
        self.logger.debug(f"Registered subscription {query_id} with {len(queries)} queries")
    
    def _register_subscription_old_style(
        self, 
        table_name: str, 
        query: str, 
        request_id: int, 
        callback: Optional[Callable[[Any], None]]
    ) -> None:
        """Register subscription using old table-name based API."""
        # Create a QueryId for backward compatibility
        from ..query_id import QueryId
        query_id = QueryId()
        
        # Create subscription info with backward compatibility fields
        sub_info = SubscriptionInfo(
            query_id=query_id,
            queries=[query],
            request_id=request_id,
            state=SubscriptionState.PENDING,
            callback=callback,
            table_name=table_name
        )
        
        # Store subscription
        self._subscriptions.set(query_id, sub_info)
        self._request_to_query.set(request_id, query_id)
        
        # Backward compatibility mappings
        self._table_name_to_query_id[table_name] = query_id
        if callback:
            self._subscription_callbacks[table_name] = callback
        self._last_update_times[table_name] = time.time()
        
        # Update query hash mapping
        query_hash = self._hash_queries([query])
        self._query_hash_to_id[query_hash].add(query_id)
        
        # Update state counts
        self._state_counts[SubscriptionState.PENDING] += 1
        
        # Publish event
        self._publish_subscription_event(
            query_id=str(query_id.id),
            table_name=table_name,
            sql_query=query,
            operation="subscribe",
            success=True
        )
        
        self.logger.info(f"Registered subscription for table '{table_name}' with request_id {request_id}")
    
    def _activate_subscription_by_query_id(self, query_id: QueryId) -> bool:
        """Activate subscription by QueryId (new API)."""
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
        
        # Update backward compatibility tracking
        if sub_info.table_name:
            self._last_update_times[sub_info.table_name] = time.time()
        
        # Notify callbacks
        self._notify_state_change(query_id, old_state, SubscriptionState.ACTIVE)
        
        # Publish event
        self._publish_subscription_event(
            query_id=str(query_id.id),
            table_name=sub_info.table_name,
            sql_query="; ".join(sub_info.queries),
            operation="activate",
            success=True
        )
        
        self.logger.debug(f"Activated subscription {query_id}")
        return True
    
    def _activate_subscription_by_table_name(self, table_name: str) -> bool:
        """Activate subscription by table name (old API)."""
        query_id = self._table_name_to_query_id.get(table_name)
        if not query_id:
            self.logger.warning(f"Cannot activate subscription for unknown table '{table_name}'")
            return False
        
        result = self._activate_subscription_by_query_id(query_id)
        if result:
            self.logger.info(f"Activated subscription for table '{table_name}'")
        return result
    
    def process_subscription_update(self, update: Any) -> bool:
        """
        Process an incoming subscription update with backward compatibility.
        
        This method handles both new QueryId-based and old table-name based updates.
        """
        try:
            # Use _safe_extract to handle both objects and dicts
            tables = _safe_extract(update, 'tables', [])
            request_id = _safe_extract(update, 'request_id')
            
            if not isinstance(tables, list):
                # Sometimes tables might be a single object
                tables = [tables] if tables is not None else []
            
            processed_count = 0
            
            for table_data in tables:
                table_name = _safe_extract(table_data, 'table_name')
                
                if table_name and self._process_table_update(table_name, table_data, request_id):
                    processed_count += 1
            
            self.logger.debug(f"Processed {processed_count} table updates from subscription")
            return processed_count > 0
            
        except Exception as e:
            self.logger.error(ErrorFormatter.format_generic_error("Subscription Manager", "subscription update processing", e))
            return False
    
    def _process_table_update(self, table_name: str, table_data: Any, request_id: Optional[int]) -> bool:
        """
        Process an update for a specific table.
        
        Args:
            table_name: Name of the table
            table_data: Table update data
            request_id: Request ID if available
            
        Returns:
            True if processed successfully, False otherwise
        """
        with self._lock:
            # Find subscription by table name or request ID
            query_id = None
            if table_name in self._table_name_to_query_id:
                query_id = self._table_name_to_query_id[table_name]
            elif request_id and request_id in self._request_to_query:
                query_id = self._request_to_query.get(request_id)
            
            if query_id:
                sub_info = self._subscriptions.get(query_id)
                if sub_info:
                    # Update subscription state
                    sub_info.state = SubscriptionState.ACTIVE
                    sub_info.increment_message_count()
                    sub_info.error_count = 0  # Reset error count on successful update
                    
                    # Update state counts if needed
                    self._state_counts[SubscriptionState.ACTIVE] += 1
                    
                    # Update backward compatibility tracking
                    if table_name:
                        self._last_update_times[table_name] = time.time()
                    
                    # Execute callback if registered
                    callback = sub_info.callback or self._subscription_callbacks.get(table_name)
                    if callback:
                        try:
                            callback(table_data)
                            self.logger.debug(f"Executed callback for table '{table_name}'")
                            return True
                        except Exception as e:
                            error_msg = str(e)
                            self.logger.error(ErrorFormatter.format_generic_error("Subscription Manager", f"callback execution for table '{table_name}'", e))
                            self._handle_callback_error(table_name, error_msg)
                            return False
                    
                    self.logger.debug(f"No callback registered for table '{table_name}'")
                    return True
            
            self.logger.warning(f"No subscription found for table '{table_name}' or request_id {request_id}")
            return False
    
    def _handle_callback_error(self, table_name: str, error_message: str) -> None:
        """
        Handle callback execution errors.
        
        Args:
            table_name: Name of the table
            error_message: Error message
        """
        with self._lock:
            query_id = self._table_name_to_query_id.get(table_name)
            if query_id:
                sub_info = self._subscriptions.get(query_id)
                if sub_info:
                    sub_info.error_count += 1
                    sub_info.last_error = error_message
                    
                    if sub_info.error_count >= self.max_error_count:
                        old_state = sub_info.state
                        sub_info.state = SubscriptionState.FAILED
                        
                        # Update counts
                        self._state_counts[old_state] -= 1
                        self._state_counts[SubscriptionState.FAILED] += 1
                        
                        self.logger.warning(f"Subscription for table '{table_name}' marked as failed after {sub_info.error_count} errors")
    
    def get_subscription_status(self, table_name: str) -> Dict[str, Any]:
        """
        Get status information for a subscription by table name (backward compatibility).
        
        Args:
            table_name: Name of the table
            
        Returns:
            Status information dictionary
        """
        with self._lock:
            query_id = self._table_name_to_query_id.get(table_name)
            if not query_id:
                return {
                    "exists": False,
                    "table_name": table_name
                }
            
            sub_info = self._subscriptions.get(query_id)
            if not sub_info:
                return {
                    "exists": False,
                    "table_name": table_name
                }
            
            last_update = self._last_update_times.get(table_name)
            
            return {
                "exists": True,
                "table_name": table_name,
                "state": sub_info.state.value,
                "request_id": sub_info.request_id,
                "created_at": sub_info.created_at,
                "last_update": sub_info.last_update,
                "time_since_update": time.time() - last_update if last_update else None,
                "has_callback": sub_info.callback is not None,
                "error_count": sub_info.error_count,
                "last_error": sub_info.last_error,
                "is_active": sub_info.state == SubscriptionState.ACTIVE,
                "is_timeout": self._is_subscription_timeout(table_name)
            }
    
    def _is_subscription_timeout(self, table_name: str) -> bool:
        """Check if a subscription has timed out."""
        last_update = self._last_update_times.get(table_name)
        if last_update is None:
            return True
        return time.time() - last_update > self.subscription_timeout
    
    def get_active_subscriptions(self) -> Union[List[QueryId], List[str]]:
        """
        Get list of active subscriptions.
        
        Returns QueryIds for new API, table names for backward compatibility when available.
        """
        with self._lock:
            active_query_ids = [
                query_id for query_id, sub_info in self._subscriptions.items()
                if sub_info.state == SubscriptionState.ACTIVE
            ]
            
            # If we have table name mappings, return table names for backward compatibility
            if self._table_name_to_query_id:
                active_table_names = []
                for query_id in active_query_ids:
                    sub_info = self._subscriptions.get(query_id)
                    if sub_info and sub_info.table_name:
                        active_table_names.append(sub_info.table_name)
                return active_table_names if active_table_names else active_query_ids
            
            return active_query_ids
    
    def get_failed_subscriptions(self) -> List[str]:
        """
        Get list of failed subscription table names (backward compatibility).
        
        Returns:
            List of table names with failed subscriptions
        """
        with self._lock:
            failed_tables = []
            for query_id, sub_info in self._subscriptions.items():
                if sub_info.state in [SubscriptionState.FAILED, SubscriptionState.ERROR] and sub_info.table_name:
                    failed_tables.append(sub_info.table_name)
            return failed_tables
    
    def get_timeout_subscriptions(self) -> List[str]:
        """
        Get list of subscriptions that have timed out (backward compatibility).
        
        Returns:
            List of table names with timed out subscriptions
        """
        with self._lock:
            timeout_subscriptions = []
            for table_name in self._table_name_to_query_id:
                if self._is_subscription_timeout(table_name):
                    timeout_subscriptions.append(table_name)
            return timeout_subscriptions
    
    def unregister_subscription(self, query_id: QueryId = None, table_name: str = None) -> bool:
        """
        Unregister a subscription with backward compatibility support.
        
        Args:
            query_id: The QueryId to unregister (new API)
            table_name: The table name to unregister (old API)
            
        Returns:
            True if unregistered, False if not found
        """
        with self._lock:
            # Handle both API styles
            if query_id is not None:
                return self._unregister_subscription_by_query_id(query_id)
            elif table_name is not None:
                return self._unregister_subscription_by_table_name(table_name)
            else:
                raise ValueError("Must provide either query_id or table_name")
    
    def _unregister_subscription_by_query_id(self, query_id: QueryId) -> bool:
        """Unregister subscription by QueryId (new API)."""
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
        
        # Remove backward compatibility mappings
        if sub_info.table_name:
            if sub_info.table_name in self._table_name_to_query_id:
                del self._table_name_to_query_id[sub_info.table_name]
            if sub_info.table_name in self._subscription_callbacks:
                del self._subscription_callbacks[sub_info.table_name]
            if sub_info.table_name in self._last_update_times:
                del self._last_update_times[sub_info.table_name]
        
        # Update query hash mapping
        query_hash = self._hash_queries(sub_info.queries)
        self._query_hash_to_id[query_hash].discard(query_id)
        if not self._query_hash_to_id[query_hash]:
            del self._query_hash_to_id[query_hash]
        
        # Notify callbacks
        self._notify_state_change(query_id, old_state, SubscriptionState.CLOSED)
        
        # Publish event
        self._publish_subscription_event(
            query_id=str(query_id.id),
            table_name=sub_info.table_name,
            sql_query="; ".join(sub_info.queries),
            operation="unsubscribe",
            success=True
        )
        
        self.logger.debug(f"Unregistered subscription {query_id}")
        return True
    
    def _unregister_subscription_by_table_name(self, table_name: str) -> bool:
        """Unregister subscription by table name (old API)."""
        query_id = self._table_name_to_query_id.get(table_name)
        if not query_id:
            self.logger.warning(f"Cannot unregister subscription for unknown table '{table_name}'")
            return False
        
        result = self._unregister_subscription_by_query_id(query_id)
        if result:
            self.logger.info(f"Unregistered subscription for table '{table_name}'")
        return result
    
    def get_subscription_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all subscriptions (backward compatibility).
        
        Returns:
            Summary information dictionary
        """
        with self._lock:
            metrics = self.get_subscription_metrics()
            active_count = len([q for q, s in self._subscriptions.items() if s.state == SubscriptionState.ACTIVE])
            failed_count = len([q for q, s in self._subscriptions.items() if s.state in [SubscriptionState.FAILED, SubscriptionState.ERROR]])
            timeout_count = len(self.get_timeout_subscriptions())
            
            return {
                "total_subscriptions": len(self._subscriptions),
                "active_subscriptions": active_count,
                "failed_subscriptions": failed_count,
                "timeout_subscriptions": timeout_count,
                "subscriptions_with_callbacks": len(self._subscription_callbacks),
                "subscription_timeout_seconds": self.subscription_timeout,
                "max_error_count": self.max_error_count
            }
    
    def process_message_by_type(self, message_data: Any) -> bool:
        """
        Process a message based on its detected type (backward compatibility).
        
        This method uses the enhanced message type detection to properly
        handle different message formats.
        
        Args:
            message_data: Message data to process
            
        Returns:
            True if message was processed, False otherwise
        """
        try:
            message_type = _get_message_type(message_data)
            
            if message_type in ['DatabaseUpdate', 'SubscriptionUpdate']:
                return self.process_subscription_update(message_data)
            elif message_type == 'SubscribeApplied':
                # Handle subscription confirmation
                table_name = _safe_extract(message_data, 'table_name')
                request_id = _safe_extract(message_data, 'request_id')
                if table_name:
                    return self.activate_subscription(table_name=table_name)
                elif request_id:
                    return self.activate_subscription_by_request(request_id)
            elif message_type == 'SubscriptionError':
                # Handle subscription errors
                table_name = _safe_extract(message_data, 'table_name')
                error_message = _safe_extract(message_data, 'error', 'Unknown error')
                if table_name:
                    self._handle_callback_error(table_name, error_message)
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(ErrorFormatter.format_generic_error("Subscription Manager", "message processing by type", e))
            return False


# Global subscription manager instance for backward compatibility
_global_subscription_manager: Optional['SubscriptionManager'] = None


def get_subscription_manager() -> 'SubscriptionManager':
    """Get the global subscription manager instance."""
    global _global_subscription_manager
    if _global_subscription_manager is None:
        _global_subscription_manager = SubscriptionManager()
    return _global_subscription_manager


def set_subscription_manager(manager: 'SubscriptionManager') -> None:
    """Set the global subscription manager instance."""
    global _global_subscription_manager
    _global_subscription_manager = manager


# Convenience functions for common operations
def create_subscription_manager(
    max_subscriptions: int = 1000,
    memory_accountant: Optional[MemoryAccountant] = None,
    event_manager: Optional[EnhancedEventManager] = None
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