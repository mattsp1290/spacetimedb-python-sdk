"""
Enhanced Subscription Interface for SpacetimeDB clients.

Combines subscription patterns from blackholio-python-client with the
query-based subscription system of spacetimedb-python-sdk.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Any, Optional, Union
from enum import Enum
from datetime import datetime


class SubscriptionState(Enum):
    """Enhanced subscription state enumeration."""
    INACTIVE = "inactive"
    SUBSCRIBING = "subscribing"
    ACTIVE = "active"
    RESUBSCRIBING = "resubscribing"
    FAILED = "failed"
    PAUSED = "paused"


class SubscriptionMode(Enum):
    """Subscription mode enumeration."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    THROTTLED = "throttled"


class TableOperation(Enum):
    """Table operation enumeration."""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


class SubscriptionInterface(ABC):
    """
    Enhanced abstract interface for SpacetimeDB subscriptions.
    
    This interface supports both table-based and query-based subscriptions,
    combining the best of both blackholio-python-client and spacetimedb-python-sdk.
    """

    @abstractmethod
    async def subscribe_to_tables(
        self, 
        table_names: List[str],
        mode: SubscriptionMode = SubscriptionMode.REAL_TIME
    ) -> bool:
        """
        Subscribe to specific tables for real-time updates.
        
        Args:
            table_names: List of table names to subscribe to
            mode: Subscription mode (real-time, batch, throttled)
            
        Returns:
            True if subscription successful, False otherwise
        """
        pass

    @abstractmethod
    async def subscribe_to_queries(
        self, 
        queries: List[str],
        mode: SubscriptionMode = SubscriptionMode.REAL_TIME
    ) -> Optional[str]:
        """
        Subscribe to specific SQL queries for real-time updates.
        
        Args:
            queries: List of SQL queries to subscribe to
            mode: Subscription mode (real-time, batch, throttled)
            
        Returns:
            Query ID if subscription successful, None otherwise
        """
        pass

    @abstractmethod
    async def subscribe_to_query(
        self, 
        query: str,
        mode: SubscriptionMode = SubscriptionMode.REAL_TIME
    ) -> Optional[str]:
        """
        Subscribe to a single SQL query for real-time updates.
        
        Args:
            query: SQL query to subscribe to
            mode: Subscription mode (real-time, batch, throttled)
            
        Returns:
            Query ID if subscription successful, None otherwise
        """
        pass

    @abstractmethod
    async def unsubscribe_from_tables(self, table_names: List[str]) -> bool:
        """
        Unsubscribe from specific tables.
        
        Args:
            table_names: List of table names to unsubscribe from
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        pass

    @abstractmethod
    async def unsubscribe_from_query(self, query_id: str) -> bool:
        """
        Unsubscribe from a specific query.
        
        Args:
            query_id: Query ID to unsubscribe from
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        pass

    @abstractmethod
    async def unsubscribe_all(self) -> bool:
        """
        Unsubscribe from all tables and queries.
        
        Returns:
            True if unsubscription successful, False otherwise
        """
        pass

    @abstractmethod
    def get_subscribed_tables(self) -> List[str]:
        """
        Get list of currently subscribed tables.
        
        Returns:
            List of subscribed table names
        """
        pass

    @abstractmethod
    def get_subscribed_queries(self) -> Dict[str, str]:
        """
        Get currently subscribed queries.
        
        Returns:
            Dictionary mapping query IDs to query strings
        """
        pass

    @abstractmethod
    def get_subscription_state(
        self, 
        identifier: str,
        is_query_id: bool = False
    ) -> SubscriptionState:
        """
        Get subscription state for a specific table or query.
        
        Args:
            identifier: Table name or query ID to check
            is_query_id: Whether identifier is a query ID or table name
            
        Returns:
            Current subscription state
        """
        pass

    @abstractmethod
    async def pause_subscription(
        self, 
        identifier: str,
        is_query_id: bool = False
    ) -> bool:
        """
        Pause a subscription temporarily.
        
        Args:
            identifier: Table name or query ID to pause
            is_query_id: Whether identifier is a query ID or table name
            
        Returns:
            True if pause successful, False otherwise
        """
        pass

    @abstractmethod
    async def resume_subscription(
        self, 
        identifier: str,
        is_query_id: bool = False
    ) -> bool:
        """
        Resume a paused subscription.
        
        Args:
            identifier: Table name or query ID to resume
            is_query_id: Whether identifier is a query ID or table name
            
        Returns:
            True if resume successful, False otherwise
        """
        pass

    @abstractmethod
    def on_table_operation(
        self, 
        table_name: str, 
        operation: TableOperation,
        callback: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], None]
    ) -> None:
        """
        Register a callback for specific table operations.
        
        Args:
            table_name: Name of the table to watch
            operation: Type of operation to watch for
            callback: Function to call when operation occurs
                     For INSERT/DELETE: (row, None)
                     For UPDATE: (old_row, new_row)
        """
        pass

    @abstractmethod
    def on_table_insert(
        self, 
        table_name: str, 
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Register a callback for table insert events.
        
        Args:
            table_name: Name of the table to watch
            callback: Function to call when rows are inserted
        """
        pass

    @abstractmethod
    def on_table_update(
        self, 
        table_name: str, 
        callback: Callable[[Dict[str, Any], Dict[str, Any]], None]
    ) -> None:
        """
        Register a callback for table update events.
        
        Args:
            table_name: Name of the table to watch
            callback: Function to call when rows are updated (old_row, new_row)
        """
        pass

    @abstractmethod
    def on_table_delete(
        self, 
        table_name: str, 
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Register a callback for table delete events.
        
        Args:
            table_name: Name of the table to watch
            callback: Function to call when rows are deleted
        """
        pass

    @abstractmethod
    def on_query_update(
        self, 
        query_id: str,
        callback: Callable[[List[Dict[str, Any]]], None]
    ) -> None:
        """
        Register a callback for query result updates.
        
        Args:
            query_id: Query ID to watch
            callback: Function to call when query results change
        """
        pass

    @abstractmethod
    def on_subscription_state_changed(
        self, 
        callback: Callable[[str, SubscriptionState, bool], None]
    ) -> None:
        """
        Register a callback for subscription state changes.
        
        Args:
            callback: Function to call when subscription state changes
                     (identifier, state, is_query_id)
        """
        pass

    @abstractmethod
    def on_initial_data_received(
        self, 
        identifier: str,
        callback: Callable[[List[Dict[str, Any]]], None],
        is_query_id: bool = False
    ) -> None:
        """
        Register a callback for initial data reception.
        
        Args:
            identifier: Table name or query ID to watch
            callback: Function to call when initial data is received
            is_query_id: Whether identifier is a query ID or table name
        """
        pass

    @abstractmethod
    def on_subscription_error(
        self,
        callback: Callable[[str, Exception, bool], None]
    ) -> None:
        """
        Register a callback for subscription errors.
        
        Args:
            callback: Function to call when subscription errors occur
                     (identifier, error, is_query_id)
        """
        pass

    @abstractmethod
    def get_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get current cached data for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of current table rows
        """
        pass

    @abstractmethod
    def get_query_data(self, query_id: str) -> List[Dict[str, Any]]:
        """
        Get current cached data for a query.
        
        Args:
            query_id: Query ID
            
        Returns:
            List of current query result rows
        """
        pass

    @abstractmethod
    def filter_table_data(
        self, 
        table_name: str,
        filter_func: Callable[[Dict[str, Any]], bool]
    ) -> List[Dict[str, Any]]:
        """
        Filter cached table data using a custom function.
        
        Args:
            table_name: Name of the table
            filter_func: Function to filter rows with
            
        Returns:
            List of filtered table rows
        """
        pass

    @abstractmethod
    def clear_table_cache(self, table_name: Optional[str] = None) -> None:
        """
        Clear cached table data.
        
        Args:
            table_name: Specific table to clear (all tables if None)
        """
        pass

    @abstractmethod
    def clear_query_cache(self, query_id: Optional[str] = None) -> None:
        """
        Clear cached query data.
        
        Args:
            query_id: Specific query to clear (all queries if None)
        """
        pass

    @abstractmethod
    def get_subscription_info(self) -> Dict[str, Any]:
        """
        Get detailed subscription information.
        
        Returns:
            Dictionary containing subscription details
        """
        pass

    @abstractmethod
    def get_subscription_metrics(self) -> Dict[str, Any]:
        """
        Get subscription performance metrics.
        
        Returns:
            Dictionary containing metrics (update count, latency, etc.)
        """
        pass

    @abstractmethod
    def set_throttle_rate(
        self, 
        identifier: str,
        max_updates_per_second: float,
        is_query_id: bool = False
    ) -> bool:
        """
        Set throttling rate for a subscription.
        
        Args:
            identifier: Table name or query ID
            max_updates_per_second: Maximum updates to process per second
            is_query_id: Whether identifier is a query ID or table name
            
        Returns:
            True if throttling set successfully, False otherwise
        """
        pass

    @abstractmethod
    def enable_batch_mode(
        self, 
        identifier: str,
        batch_size: int = 100,
        batch_timeout: float = 1.0,
        is_query_id: bool = False
    ) -> bool:
        """
        Enable batch mode for a subscription.
        
        Args:
            identifier: Table name or query ID
            batch_size: Maximum number of updates per batch
            batch_timeout: Maximum time to wait before sending partial batch
            is_query_id: Whether identifier is a query ID or table name
            
        Returns:
            True if batch mode enabled successfully, False otherwise
        """
        pass

    @abstractmethod
    def disable_batch_mode(
        self, 
        identifier: str,
        is_query_id: bool = False
    ) -> bool:
        """
        Disable batch mode for a subscription.
        
        Args:
            identifier: Table name or query ID
            is_query_id: Whether identifier is a query ID or table name
            
        Returns:
            True if batch mode disabled successfully, False otherwise
        """
        pass