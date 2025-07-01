"""
Subscription Manager for SpacetimeDB subscriptions.

This module provides the SubscriptionManager class that handles subscription
state management, addressing the issues identified in the bug report where
subscription states are not properly maintained, leading to missed updates.
"""

import time
import threading
import logging
from typing import Dict, Any, Callable, Optional, List, Set
from dataclasses import dataclass
from enum import Enum

from .serialization import _safe_extract, _get_message_type


logger = logging.getLogger(__name__)


class SubscriptionState(Enum):
    """States for subscription lifecycle management."""
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubscriptionInfo:
    """Information about an active subscription."""
    table_name: str
    query: str
    request_id: int
    state: SubscriptionState
    created_at: float
    last_update: Optional[float] = None
    callback: Optional[Callable[[Any], None]] = None
    error_count: int = 0
    last_error: Optional[str] = None


class SubscriptionManager:
    """
    Manager for SpacetimeDB subscriptions with proper state tracking.
    
    This class addresses the core subscription management issues identified
    in the bug report by providing:
    - Proper subscription state management
    - Callback registration and execution
    - Update tracking and timeout detection
    - Error handling and recovery
    """
    
    def __init__(self):
        """Initialize the subscription manager."""
        self.active_subscriptions: Dict[str, SubscriptionInfo] = {}
        self.subscription_callbacks: Dict[str, Callable[[Any], None]] = {}
        self.last_update_times: Dict[str, float] = {}
        self.request_id_to_table: Dict[int, str] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Configuration
        self.subscription_timeout = 30.0  # seconds
        self.max_error_count = 5
        
        logger.info("SubscriptionManager initialized")
    
    def register_subscription(self, 
                            table_name: str, 
                            query: str,
                            request_id: int,
                            callback: Optional[Callable[[Any], None]] = None) -> None:
        """
        Register a new subscription for table updates.
        
        Args:
            table_name: Name of the table to subscribe to
            query: SQL query string
            request_id: Request ID for tracking
            callback: Optional callback function for updates
        """
        with self._lock:
            subscription_info = SubscriptionInfo(
                table_name=table_name,
                query=query,
                request_id=request_id,
                state=SubscriptionState.PENDING,
                created_at=time.time(),
                callback=callback
            )
            
            self.active_subscriptions[table_name] = subscription_info
            self.request_id_to_table[request_id] = table_name
            
            if callback:
                self.subscription_callbacks[table_name] = callback
            
            self.last_update_times[table_name] = time.time()
            
            logger.info(f"Registered subscription for table '{table_name}' with request_id {request_id}")
    
    def activate_subscription(self, table_name: str) -> bool:
        """
        Mark a subscription as active.
        
        Args:
            table_name: Name of the table
            
        Returns:
            True if successfully activated, False otherwise
        """
        with self._lock:
            if table_name in self.active_subscriptions:
                self.active_subscriptions[table_name].state = SubscriptionState.ACTIVE
                self.last_update_times[table_name] = time.time()
                logger.info(f"Activated subscription for table '{table_name}'")
                return True
            return False
    
    def process_subscription_update(self, update: Any) -> bool:
        """
        Process an incoming subscription update.
        
        This method handles the core issue from the bug report by properly
        extracting table information from both object and dict formats.
        
        Args:
            update: Subscription update data (object or dict)
            
        Returns:
            True if update was processed, False otherwise
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
            
            logger.debug(f"Processed {processed_count} table updates from subscription")
            return processed_count > 0
            
        except Exception as e:
            logger.error(f"Error processing subscription update: {e}")
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
            # Update subscription state
            if table_name in self.active_subscriptions:
                subscription = self.active_subscriptions[table_name]
                subscription.state = SubscriptionState.ACTIVE
                subscription.last_update = time.time()
                subscription.error_count = 0  # Reset error count on successful update
            
            # Update last update time
            self.last_update_times[table_name] = time.time()
            
            # Execute callback if registered
            if table_name in self.subscription_callbacks:
                try:
                    callback = self.subscription_callbacks[table_name]
                    callback(table_data)
                    logger.debug(f"Executed callback for table '{table_name}'")
                    return True
                except Exception as e:
                    logger.error(f"Error executing callback for table '{table_name}': {e}")
                    self._handle_callback_error(table_name, str(e))
                    return False
            
            logger.debug(f"No callback registered for table '{table_name}'")
            return True
    
    def _handle_callback_error(self, table_name: str, error_message: str) -> None:
        """
        Handle callback execution errors.
        
        Args:
            table_name: Name of the table
            error_message: Error message
        """
        with self._lock:
            if table_name in self.active_subscriptions:
                subscription = self.active_subscriptions[table_name]
                subscription.error_count += 1
                subscription.last_error = error_message
                
                if subscription.error_count >= self.max_error_count:
                    subscription.state = SubscriptionState.FAILED
                    logger.warning(f"Subscription for table '{table_name}' marked as failed after {subscription.error_count} errors")
    
    def get_subscription_status(self, table_name: str) -> Dict[str, Any]:
        """
        Get status information for a subscription.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Status information dictionary
        """
        with self._lock:
            if table_name not in self.active_subscriptions:
                return {
                    "exists": False,
                    "table_name": table_name
                }
            
            subscription = self.active_subscriptions[table_name]
            last_update = self.last_update_times.get(table_name)
            
            return {
                "exists": True,
                "table_name": table_name,
                "state": subscription.state.value,
                "request_id": subscription.request_id,
                "created_at": subscription.created_at,
                "last_update": subscription.last_update,
                "time_since_update": time.time() - last_update if last_update else None,
                "has_callback": subscription.callback is not None,
                "error_count": subscription.error_count,
                "last_error": subscription.last_error,
                "is_active": subscription.state == SubscriptionState.ACTIVE,
                "is_timeout": self._is_subscription_timeout(table_name)
            }
    
    def _is_subscription_timeout(self, table_name: str) -> bool:
        """Check if a subscription has timed out."""
        last_update = self.last_update_times.get(table_name)
        if last_update is None:
            return True
        return time.time() - last_update > self.subscription_timeout
    
    def get_active_subscriptions(self) -> List[str]:
        """
        Get list of active subscription table names.
        
        Returns:
            List of table names with active subscriptions
        """
        with self._lock:
            return [
                table_name for table_name, subscription in self.active_subscriptions.items()
                if subscription.state == SubscriptionState.ACTIVE
            ]
    
    def get_failed_subscriptions(self) -> List[str]:
        """
        Get list of failed subscription table names.
        
        Returns:
            List of table names with failed subscriptions
        """
        with self._lock:
            return [
                table_name for table_name, subscription in self.active_subscriptions.items()
                if subscription.state == SubscriptionState.FAILED
            ]
    
    def get_timeout_subscriptions(self) -> List[str]:
        """
        Get list of subscriptions that have timed out.
        
        Returns:
            List of table names with timed out subscriptions
        """
        with self._lock:
            timeout_subscriptions = []
            for table_name in self.active_subscriptions:
                if self._is_subscription_timeout(table_name):
                    timeout_subscriptions.append(table_name)
            return timeout_subscriptions
    
    def unregister_subscription(self, table_name: str) -> bool:
        """
        Unregister a subscription.
        
        Args:
            table_name: Name of the table
            
        Returns:
            True if unregistered, False if not found
        """
        with self._lock:
            removed = False
            
            if table_name in self.active_subscriptions:
                subscription = self.active_subscriptions[table_name]
                subscription.state = SubscriptionState.CANCELLED
                
                # Find and remove request_id mapping
                request_id = subscription.request_id
                if request_id in self.request_id_to_table:
                    del self.request_id_to_table[request_id]
                
                del self.active_subscriptions[table_name]
                removed = True
            
            if table_name in self.subscription_callbacks:
                del self.subscription_callbacks[table_name]
                removed = True
            
            if table_name in self.last_update_times:
                del self.last_update_times[table_name]
                removed = True
            
            if removed:
                logger.info(f"Unregistered subscription for table '{table_name}'")
            
            return removed
    
    def clear_all_subscriptions(self) -> None:
        """Clear all subscriptions."""
        with self._lock:
            count = len(self.active_subscriptions)
            self.active_subscriptions.clear()
            self.subscription_callbacks.clear()
            self.last_update_times.clear()
            self.request_id_to_table.clear()
            
            logger.info(f"Cleared {count} subscriptions")
    
    def get_subscription_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all subscriptions.
        
        Returns:
            Summary information dictionary
        """
        with self._lock:
            active_count = len(self.get_active_subscriptions())
            failed_count = len(self.get_failed_subscriptions())
            timeout_count = len(self.get_timeout_subscriptions())
            
            return {
                "total_subscriptions": len(self.active_subscriptions),
                "active_subscriptions": active_count,
                "failed_subscriptions": failed_count,
                "timeout_subscriptions": timeout_count,
                "subscriptions_with_callbacks": len(self.subscription_callbacks),
                "subscription_timeout_seconds": self.subscription_timeout,
                "max_error_count": self.max_error_count
            }
    
    def process_message_by_type(self, message_data: Any) -> bool:
        """
        Process a message based on its detected type.
        
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
                if table_name:
                    return self.activate_subscription(table_name)
            elif message_type == 'SubscriptionError':
                # Handle subscription errors
                table_name = _safe_extract(message_data, 'table_name')
                error_message = _safe_extract(message_data, 'error', 'Unknown error')
                if table_name:
                    self._handle_callback_error(table_name, error_message)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing message by type: {e}")
            return False


# Global subscription manager instance
_global_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """Get the global subscription manager instance."""
    global _global_subscription_manager
    if _global_subscription_manager is None:
        _global_subscription_manager = SubscriptionManager()
    return _global_subscription_manager


def set_subscription_manager(manager: SubscriptionManager) -> None:
    """Set the global subscription manager instance."""
    global _global_subscription_manager
    _global_subscription_manager = manager