"""
Enhanced SpacetimeDB Client Interface.

Provides a unified interface that combines all SpacetimeDB functionality
while being generic enough for any application (not just games).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union
from .connection_interface import ConnectionInterface, ConnectionState
from .auth_interface import AuthInterface, AuthenticationState
from .subscription_interface import SubscriptionInterface, SubscriptionState
from .reducer_interface import ReducerInterface, ReducerStatus


class SpacetimeDBClientInterface(
    ConnectionInterface, 
    AuthInterface, 
    SubscriptionInterface, 
    ReducerInterface
):
    """
    Enhanced unified interface for SpacetimeDB clients.
    
    This interface combines all sub-interfaces into a single comprehensive API
    that provides access to connection management, authentication, subscriptions,
    and reducer calls for any SpacetimeDB application.
    """

    @abstractmethod
    def __init__(
        self, 
        host: str,
        database: str,
        server_language: str = "rust",
        protocol: str = "v1.json.spacetimedb",
        auto_reconnect: bool = True,
        **kwargs
    ) -> None:
        """
        Initialize the SpacetimeDB client.
        
        Args:
            host: Server host (e.g., "localhost:3000")
            database: Database identity/name
            server_language: Server implementation language (rust, python, csharp, go)
            protocol: SpacetimeDB protocol version
            auto_reconnect: Whether to enable automatic reconnection
            **kwargs: Additional configuration options
        """
        pass

    # High-Level Client Operations
    @abstractmethod
    async def connect_and_authenticate(
        self, 
        auth_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        wait_for_ready: bool = True,
        timeout: Optional[float] = 30.0
    ) -> bool:
        """
        Connect to server and authenticate in one operation.
        
        Args:
            auth_token: Optional authentication token
            credentials: Optional credentials dictionary
            wait_for_ready: Whether to wait for connection to be ready
            timeout: Maximum time to wait for connection and authentication
            
        Returns:
            True if connected and authenticated successfully
        """
        pass

    @abstractmethod
    async def setup_subscriptions(
        self, 
        tables: Optional[List[str]] = None,
        queries: Optional[List[str]] = None,
        auto_subscribe_mode: str = "all_tables"
    ) -> bool:
        """
        Set up initial subscriptions.
        
        Args:
            tables: Specific tables to subscribe to
            queries: Specific queries to subscribe to
            auto_subscribe_mode: Mode for automatic subscription 
                                ("all_tables", "none", "essential")
            
        Returns:
            True if subscriptions set up successfully
        """
        pass

    @abstractmethod
    def get_client_info(self) -> Dict[str, Any]:
        """
        Get comprehensive client information.
        
        Returns:
            Dictionary containing client version, server info, connection details
        """
        pass

    @abstractmethod
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about the connected SpacetimeDB server.
        
        Returns:
            Dictionary containing server version, capabilities, etc.
        """
        pass

    @abstractmethod
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the connected database.
        
        Returns:
            Dictionary containing database schema, tables, reducers, etc.
        """
        pass

    # Data Access Methods
    @abstractmethod
    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schema information for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Schema dictionary or None if table not found
        """
        pass

    @abstractmethod
    def list_tables(self) -> List[str]:
        """
        Get list of available tables in the database.
        
        Returns:
            List of table names
        """
        pass

    @abstractmethod
    def list_reducers(self) -> List[str]:
        """
        Get list of available reducers in the database.
        
        Returns:
            List of reducer names
        """
        pass

    @abstractmethod
    def query_data(
        self, 
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a one-off query and return results.
        
        Args:
            query: SQL query to execute
            parameters: Optional query parameters
            
        Returns:
            List of result rows
        """
        pass

    @abstractmethod
    async def execute_query_async(
        self, 
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = 10.0
    ) -> List[Dict[str, Any]]:
        """
        Execute a query asynchronously.
        
        Args:
            query: SQL query to execute
            parameters: Optional query parameters
            timeout: Query timeout in seconds
            
        Returns:
            List of result rows
        """
        pass

    # Event System
    @abstractmethod
    def on_connected(self, callback: Callable[[], None]) -> None:
        """
        Register callback for successful connection.
        
        Args:
            callback: Function to call when connected
        """
        pass

    @abstractmethod
    def on_disconnected(self, callback: Callable[[], None]) -> None:
        """
        Register callback for disconnection.
        
        Args:
            callback: Function to call when disconnected
        """
        pass

    @abstractmethod
    def on_data_update(
        self, 
        callback: Callable[[str, str, Dict[str, Any]], None]
    ) -> None:
        """
        Register callback for general data updates.
        
        Args:
            callback: Function to call on data updates
                     (table_name, operation, data)
        """
        pass

    @abstractmethod
    def on_client_error(
        self, 
        callback: Callable[[Exception], None]
    ) -> None:
        """
        Register callback for client errors.
        
        Args:
            callback: Function to call when client errors occur
        """
        pass

    # Configuration and Settings
    @abstractmethod
    def configure_logging(
        self, 
        level: str = "INFO",
        format_style: str = "json",
        output_file: Optional[str] = None
    ) -> None:
        """
        Configure client logging.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
            format_style: Log format style (json, text, colored)
            output_file: Optional file to write logs to
        """
        pass

    @abstractmethod
    def set_connection_timeout(self, timeout: float) -> None:
        """
        Set default connection timeout.
        
        Args:
            timeout: Timeout in seconds
        """
        pass

    @abstractmethod
    def set_query_timeout(self, timeout: float) -> None:
        """
        Set default query timeout.
        
        Args:
            timeout: Timeout in seconds
        """
        pass

    @abstractmethod
    def enable_compression(self, compression_type: str = "brotli") -> None:
        """
        Enable data compression.
        
        Args:
            compression_type: Type of compression to use
        """
        pass

    @abstractmethod
    def disable_compression(self) -> None:
        """Disable data compression."""
        pass

    # Performance and Monitoring
    @abstractmethod
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get client performance metrics.
        
        Returns:
            Dictionary containing performance metrics
        """
        pass

    @abstractmethod
    def get_connection_metrics(self) -> Dict[str, Any]:
        """
        Get connection-specific metrics.
        
        Returns:
            Dictionary containing connection metrics
        """
        pass

    @abstractmethod
    def get_subscription_metrics(self) -> Dict[str, Any]:
        """
        Get subscription-specific metrics.
        
        Returns:
            Dictionary containing subscription metrics
        """
        pass

    @abstractmethod
    def get_reducer_metrics(self) -> Dict[str, Any]:
        """
        Get reducer call metrics.
        
        Returns:
            Dictionary containing reducer metrics
        """
        pass

    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        pass

    # Health and Diagnostics
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dictionary containing health status of all components
        """
        pass

    @abstractmethod
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """
        Get diagnostic information for troubleshooting.
        
        Returns:
            Dictionary containing diagnostic information
        """
        pass

    @abstractmethod
    async def test_all_functionality(self) -> Dict[str, bool]:
        """
        Test all client functionality.
        
        Returns:
            Dictionary mapping functionality names to test results
        """
        pass

    # State Management
    @abstractmethod
    def get_client_state(self) -> Dict[str, Any]:
        """
        Get current client state summary.
        
        Returns:
            Dictionary containing current state of all components
        """
        pass

    @abstractmethod
    def export_state(
        self, 
        file_path: str,
        include_sensitive: bool = False
    ) -> bool:
        """
        Export current client state to file.
        
        Args:
            file_path: Path to save state file
            include_sensitive: Whether to include sensitive data
            
        Returns:
            True if export successful, False otherwise
        """
        pass

    @abstractmethod
    def import_state(self, file_path: str) -> bool:
        """
        Import client state from file.
        
        Args:
            file_path: Path to state file
            
        Returns:
            True if import successful, False otherwise
        """
        pass

    # Lifecycle Management
    @abstractmethod
    async def graceful_shutdown(
        self, 
        timeout: Optional[float] = 30.0
    ) -> None:
        """
        Gracefully shutdown the client.
        
        Args:
            timeout: Maximum time to wait for clean shutdown
        """
        pass

    @abstractmethod
    async def force_shutdown(self) -> None:
        """Force immediate shutdown of the client."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """
        Check if client is ready for operations.
        
        Returns:
            True if connected, authenticated, and ready
        """
        pass

    @abstractmethod
    async def wait_for_ready(
        self, 
        timeout: Optional[float] = None
    ) -> bool:
        """
        Wait for client to be ready for operations.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if ready within timeout, False otherwise
        """
        pass

    # Advanced Features
    @abstractmethod
    def enable_auto_recovery(
        self, 
        max_recovery_attempts: int = 5,
        recovery_delay: float = 1.0
    ) -> None:
        """
        Enable automatic error recovery.
        
        Args:
            max_recovery_attempts: Maximum recovery attempts
            recovery_delay: Delay between recovery attempts
        """
        pass

    @abstractmethod
    def disable_auto_recovery(self) -> None:
        """Disable automatic error recovery."""
        pass

    @abstractmethod
    def set_custom_serializer(
        self, 
        serializer: Callable[[Any], bytes],
        deserializer: Callable[[bytes], Any]
    ) -> None:
        """
        Set custom serialization functions.
        
        Args:
            serializer: Function to serialize data
            deserializer: Function to deserialize data
        """
        pass

    @abstractmethod
    def add_middleware(
        self, 
        middleware: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """
        Add middleware for request/response processing.
        
        Args:
            middleware: Middleware function
        """
        pass

    @abstractmethod
    def remove_middleware(self, middleware_id: str) -> bool:
        """
        Remove middleware by ID.
        
        Args:
            middleware_id: ID of middleware to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        pass