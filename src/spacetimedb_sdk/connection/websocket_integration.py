"""
WebSocket Integration Interface for SubscriptionManager

This module provides a clean integration interface between the WebSocket client
and the subscription manager, ensuring proper separation of concerns while
maintaining existing API compatibility.

Key Features:
- Clean interface between WebSocket client and subscription manager
- Maintains existing API compatibility
- Proper error handling and recovery
- Event-driven architecture
- Thread-safe operations
"""

import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from ..query_id import QueryId
from ..messages import (
    SubscribeSingleMessage,
    SubscribeMultiMessage,
)
from ..protocol import (
    Unsubscribe,
    SubscribeApplied,
    UnsubscribeApplied,
    SubscriptionError,
    SubscribeMultiApplied,
    UnsubscribeMultiApplied
)
from .subscription_manager import SubscriptionManager, SubscriptionState

# Import events with fallback for compatibility
try:
    from ..events import EnhancedEventManager
except ImportError:
    # Fallback for testing
    class EnhancedEventManager:
        def publish_event(self, event): pass


@dataclass
class WebSocketSubscriptionConfig:
    """Configuration for WebSocket subscription integration."""
    max_subscriptions: int = 1000
    enable_health_monitoring: bool = True
    health_check_interval: float = 30.0
    enable_events: bool = True
    auto_activate_subscriptions: bool = True
    retry_failed_subscriptions: bool = False
    max_retry_attempts: int = 3


class WebSocketSubscriptionIntegration:
    """
    Integration layer between WebSocket client and subscription manager.
    
    This class provides a clean interface for WebSocket clients to manage
    subscriptions without directly interacting with the subscription manager.
    It handles protocol message conversion, response routing, and error handling.
    """
    
    def __init__(
        self,
        subscription_manager: SubscriptionManager,
        config: Optional[WebSocketSubscriptionConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the WebSocket subscription integration.
        
        Args:
            subscription_manager: The subscription manager instance
            config: Configuration for the integration
            logger: Logger for integration operations
        """
        self.subscription_manager = subscription_manager
        self.config = config or WebSocketSubscriptionConfig()
        self.logger = logger or logging.getLogger(__name__)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Message callbacks
        self._message_send_callback: Optional[Callable[[Any], None]] = None
        
        # Response tracking
        self._pending_responses: Dict[int, QueryId] = {}
        
        # Retry tracking
        self._retry_counts: Dict[QueryId, int] = {}
        
        # Setup subscription manager callbacks
        self._setup_subscription_callbacks()
        
        self.logger.info("WebSocket subscription integration initialized")
    
    def set_message_send_callback(self, callback: Callable[[Any], None]) -> None:
        """
        Set the callback for sending messages to the WebSocket.
        
        Args:
            callback: Function to call when sending messages
        """
        with self._lock:
            self._message_send_callback = callback
    
    def subscribe_single(self, query: str, request_id: int) -> QueryId:
        """
        Subscribe to a single query.
        
        Args:
            query: The SQL query string
            request_id: The request ID for tracking
            
        Returns:
            QueryId for the subscription
        """
        with self._lock:
            # Generate query ID
            query_id = QueryId.generate()
            
            # Register with subscription manager
            self.subscription_manager.register_subscription(
                query_id=query_id,
                queries=[query],
                request_id=request_id
            )
            
            # Track pending response
            self._pending_responses[request_id] = query_id
            
            # Create and send message
            message = SubscribeSingleMessage(
                query=query,
                request_id=request_id,
                query_id=query_id
            )
            
            self._send_message(message)
            
            self.logger.debug(f"Subscribed to single query {query_id}: {query}")
            return query_id
    
    def subscribe_multi(self, queries: List[str], request_id: int) -> QueryId:
        """
        Subscribe to multiple queries.
        
        Args:
            queries: List of SQL query strings
            request_id: The request ID for tracking
            
        Returns:
            QueryId for the subscription
        """
        with self._lock:
            # Generate query ID
            query_id = QueryId.generate()
            
            # Register with subscription manager
            self.subscription_manager.register_subscription(
                query_id=query_id,
                queries=queries,
                request_id=request_id
            )
            
            # Track pending response
            self._pending_responses[request_id] = query_id
            
            # Create and send message
            message = SubscribeMultiMessage(
                query_strings=queries,
                request_id=request_id,
                query_id=query_id
            )
            
            self._send_message(message)
            
            self.logger.debug(f"Subscribed to multi query {query_id}: {len(queries)} queries")
            return query_id
    
    def unsubscribe(self, query_id: QueryId, request_id: int) -> bool:
        """
        Unsubscribe from a query.
        
        Args:
            query_id: The QueryId to unsubscribe from
            request_id: The request ID for tracking
            
        Returns:
            True if unsubscribe request was sent, False otherwise
        """
        with self._lock:
            # Check if subscription exists
            sub_info = self.subscription_manager.get_subscription_info(query_id)
            if not sub_info:
                self.logger.warning(f"Cannot unsubscribe from unknown query {query_id}")
                return False
            
            # Track pending response
            self._pending_responses[request_id] = query_id
            
            # Create and send message
            message = Unsubscribe(
                request_id=request_id,
                query_id=query_id
            )
            
            self._send_message(message)
            
            self.logger.debug(f"Unsubscribed from query {query_id}")
            return True
    
    def handle_subscribe_applied(self, message: SubscribeApplied) -> None:
        """
        Handle SubscribeApplied message from server.
        
        Args:
            message: The SubscribeApplied message
        """
        with self._lock:
            # Find the subscription by request ID
            query_id = self._pending_responses.get(message.request_id)
            if not query_id:
                self.logger.warning(f"Received SubscribeApplied for unknown request {message.request_id}")
                return
            
            # Activate the subscription
            success = self.subscription_manager.activate_subscription(query_id)
            if success:
                self.logger.debug(f"Activated subscription {query_id}")
            else:
                self.logger.warning(f"Failed to activate subscription {query_id}")
            
            # Clean up pending response
            del self._pending_responses[message.request_id]
    
    def handle_subscribe_multi_applied(self, message: SubscribeMultiApplied) -> None:
        """
        Handle SubscribeMultiApplied message from server.
        
        Args:
            message: The SubscribeMultiApplied message
        """
        with self._lock:
            # Find the subscription by request ID
            query_id = self._pending_responses.get(message.request_id)
            if not query_id:
                self.logger.warning(f"Received SubscribeMultiApplied for unknown request {message.request_id}")
                return
            
            # Activate the subscription
            success = self.subscription_manager.activate_subscription(query_id)
            if success:
                self.logger.debug(f"Activated multi subscription {query_id}")
            else:
                self.logger.warning(f"Failed to activate multi subscription {query_id}")
            
            # Clean up pending response
            del self._pending_responses[message.request_id]
    
    def handle_unsubscribe_applied(self, message: UnsubscribeApplied) -> None:
        """
        Handle UnsubscribeApplied message from server.
        
        Args:
            message: The UnsubscribeApplied message
        """
        with self._lock:
            # Find the subscription by request ID
            query_id = self._pending_responses.get(message.request_id)
            if not query_id:
                self.logger.warning(f"Received UnsubscribeApplied for unknown request {message.request_id}")
                return
            
            # Unregister the subscription
            success = self.subscription_manager.unregister_subscription(query_id)
            if success:
                self.logger.debug(f"Unregistered subscription {query_id}")
            else:
                self.logger.warning(f"Failed to unregister subscription {query_id}")
            
            # Clean up pending response
            del self._pending_responses[message.request_id]
    
    def handle_unsubscribe_multi_applied(self, message: UnsubscribeMultiApplied) -> None:
        """
        Handle UnsubscribeMultiApplied message from server.
        
        Args:
            message: The UnsubscribeMultiApplied message
        """
        with self._lock:
            # Find the subscription by request ID
            query_id = self._pending_responses.get(message.request_id)
            if not query_id:
                self.logger.warning(f"Received UnsubscribeMultiApplied for unknown request {message.request_id}")
                return
            
            # Unregister the subscription
            success = self.subscription_manager.unregister_subscription(query_id)
            if success:
                self.logger.debug(f"Unregistered multi subscription {query_id}")
            else:
                self.logger.warning(f"Failed to unregister multi subscription {query_id}")
            
            # Clean up pending response
            del self._pending_responses[message.request_id]
    
    def handle_subscription_error(self, message: SubscriptionError) -> None:
        """
        Handle SubscriptionError message from server.
        
        Args:
            message: The SubscriptionError message
        """
        with self._lock:
            # Record error for the subscription
            self.subscription_manager.record_subscription_error(
                query_id=message.query_id,
                error=message.error
            )
            
            # Check if retry is enabled and should be attempted
            if self.config.retry_failed_subscriptions:
                retry_count = self._retry_counts.get(message.query_id, 0)
                if retry_count < self.config.max_retry_attempts:
                    self._retry_subscription(message.query_id)
                else:
                    self.logger.error(f"Max retry attempts reached for subscription {message.query_id}")
            
            self.logger.error(f"Subscription error for {message.query_id}: {message.error}")
    
    def handle_table_update(self, table_name: str, data_size: int) -> None:
        """
        Handle table update data for subscriptions.
        
        Args:
            table_name: Name of the table that was updated
            data_size: Size of the update data
        """
        with self._lock:
            # Find subscriptions that might be interested in this table
            # This is a simplified version - in practice, you'd need to match
            # table names to query strings in the subscription manager
            active_subscriptions = self.subscription_manager.get_active_subscriptions()
            
            for query_id in active_subscriptions:
                sub_info = self.subscription_manager.get_subscription_info(query_id)
                if sub_info and self._subscription_matches_table(sub_info.queries, table_name):
                    self.subscription_manager.record_subscription_data(query_id, data_size)
    
    def get_subscription_status(self) -> Dict[str, Any]:
        """
        Get comprehensive subscription status.
        
        Returns:
            Dictionary with subscription status information
        """
        with self._lock:
            metrics = self.subscription_manager.get_subscription_metrics()
            active_subscriptions = self.subscription_manager.get_active_subscriptions()
            
            return {
                'metrics': metrics,
                'active_subscriptions': len(active_subscriptions),
                'pending_responses': len(self._pending_responses),
                'retry_counts': dict(self._retry_counts),
                'health_status': self.subscription_manager.perform_health_check()
            }
    
    def cleanup(self) -> None:
        """Clean up resources and subscriptions."""
        with self._lock:
            # Clear all subscriptions
            self.subscription_manager.clear_all_subscriptions()
            
            # Clear tracking data
            self._pending_responses.clear()
            self._retry_counts.clear()
            
            self.logger.info("WebSocket subscription integration cleaned up")
    
    def _setup_subscription_callbacks(self) -> None:
        """Setup callbacks for subscription state changes."""
        def on_state_change(query_id: QueryId, old_state: SubscriptionState, new_state: SubscriptionState):
            self.logger.debug(f"Subscription {query_id} state changed: {old_state} -> {new_state}")
            
            # Handle state-specific logic
            if new_state == SubscriptionState.ERROR:
                # Clear from pending responses if error occurs
                for request_id, qid in list(self._pending_responses.items()):
                    if qid == query_id:
                        del self._pending_responses[request_id]
                        break
        
        self.subscription_manager.add_state_change_callback(on_state_change)
    
    def _send_message(self, message: Any) -> None:
        """
        Send a message through the WebSocket.
        
        Args:
            message: The message to send
        """
        if self._message_send_callback:
            try:
                self._message_send_callback(message)
            except Exception as e:
                self.logger.error(f"Error sending message: {e}")
        else:
            self.logger.warning("No message send callback configured")
    
    def _retry_subscription(self, query_id: QueryId) -> None:
        """
        Retry a failed subscription.
        
        Args:
            query_id: The QueryId to retry
        """
        # Get subscription info
        sub_info = self.subscription_manager.get_subscription_info(query_id)
        if not sub_info:
            return
        
        # Increment retry count
        self._retry_counts[query_id] = self._retry_counts.get(query_id, 0) + 1
        
        # Generate new request ID
        import time
        request_id = int(time.time() * 1000000) % 1000000
        
        # Re-register the subscription
        self.subscription_manager.register_subscription(
            query_id=query_id,
            queries=sub_info.queries,
            request_id=request_id
        )
        
        # Send subscription message
        if len(sub_info.queries) == 1:
            message = SubscribeSingleMessage(
                query=sub_info.queries[0],
                request_id=request_id,
                query_id=query_id
            )
        else:
            message = SubscribeMultiMessage(
                query_strings=sub_info.queries,
                request_id=request_id,
                query_id=query_id
            )
        
        self._send_message(message)
        
        self.logger.info(f"Retrying subscription {query_id} (attempt {self._retry_counts[query_id]})")
    
    def _subscription_matches_table(self, queries: List[str], table_name: str) -> bool:
        """
        Check if subscription queries match a table name.
        
        Args:
            queries: List of SQL queries
            table_name: Name of the table to match
            
        Returns:
            True if any query matches the table name
        """
        # Simple heuristic - check if table name appears in query
        # In practice, this would need proper SQL parsing
        table_name_lower = table_name.lower()
        for query in queries:
            if table_name_lower in query.lower():
                return True
        return False


# Compatibility layer for existing WebSocket client
class LegacySubscriptionInterface:
    """
    Compatibility layer for existing WebSocket client subscription methods.
    
    This class provides the same interface as the original WebSocket client
    subscription methods while delegating to the new subscription manager.
    """
    
    def __init__(self, integration: WebSocketSubscriptionIntegration):
        """
        Initialize the legacy interface.
        
        Args:
            integration: The WebSocket subscription integration
        """
        self.integration = integration
    
    def subscribe_single(self, query: str) -> QueryId:
        """Subscribe to a single query (legacy method)."""
        import time
        request_id = int(time.time() * 1000000) % 1000000
        return self.integration.subscribe_single(query, request_id)
    
    def subscribe_multi(self, queries: List[str]) -> QueryId:
        """Subscribe to multiple queries (legacy method)."""
        import time
        request_id = int(time.time() * 1000000) % 1000000
        return self.integration.subscribe_multi(queries, request_id)
    
    def unsubscribe(self, query_id: QueryId) -> int:
        """Unsubscribe from a query (legacy method)."""
        import time
        request_id = int(time.time() * 1000000) % 1000000
        success = self.integration.unsubscribe(query_id, request_id)
        return request_id if success else -1
    
    def subscribe_to_queries(self, queries: List[str]) -> int:
        """Subscribe to a list of queries (legacy method)."""
        query_id = self.subscribe_multi(queries)
        return query_id.id
    
    # Expose subscription manager methods
    def get_active_subscriptions(self) -> List[QueryId]:
        """Get active subscriptions."""
        return self.integration.subscription_manager.get_active_subscriptions()
    
    def get_subscription_count(self) -> int:
        """Get total subscription count."""
        return self.integration.subscription_manager.get_subscription_count()
    
    def get_subscription_metrics(self):
        """Get subscription metrics."""
        return self.integration.subscription_manager.get_subscription_metrics()


# Convenience function for creating WebSocket integration
def create_websocket_subscription_integration(
    max_subscriptions: int = 1000,
    event_manager: Optional[EnhancedEventManager] = None,
    config: Optional[WebSocketSubscriptionConfig] = None
) -> WebSocketSubscriptionIntegration:
    """
    Create a WebSocket subscription integration with standard configuration.
    
    Args:
        max_subscriptions: Maximum number of concurrent subscriptions
        event_manager: Event manager for subscription events
        config: Configuration for the integration
        
    Returns:
        Configured WebSocketSubscriptionIntegration instance
    """
    from .subscription_manager import create_subscription_manager
    
    # Create subscription manager
    subscription_manager = create_subscription_manager(
        max_subscriptions=max_subscriptions,
        event_manager=event_manager
    )
    
    # Create integration
    integration = WebSocketSubscriptionIntegration(
        subscription_manager=subscription_manager,
        config=config
    )
    
    return integration