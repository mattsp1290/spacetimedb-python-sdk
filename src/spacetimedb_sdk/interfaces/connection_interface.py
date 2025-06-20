"""
Enhanced Connection Interface for SpacetimeDB clients.

Combines the excellent patterns from blackholio-python-client with the
production-ready features of spacetimedb-python-sdk.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional, Dict, Any, List
import asyncio


class ConnectionState(Enum):
    """Enhanced connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    AUTHENTICATING = "authenticating"
    READY = "ready"  # Connected and authenticated


class ConnectionHealthStatus(Enum):
    """Connection health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ConnectionInterface(ABC):
    """
    Enhanced abstract interface for SpacetimeDB connection management.
    
    This interface combines connection management patterns from blackholio-python-client
    with the production-ready features of spacetimedb-python-sdk.
    """

    @abstractmethod
    async def connect(
        self, 
        auth_token: Optional[str] = None,
        auto_authenticate: bool = True
    ) -> bool:
        """
        Connect to the SpacetimeDB server.
        
        Args:
            auth_token: Optional authentication token for connecting
            auto_authenticate: Whether to automatically authenticate after connection
            
        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self, graceful: bool = True) -> None:
        """
        Disconnect from the SpacetimeDB server.
        
        Args:
            graceful: Whether to perform graceful disconnect with cleanup
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to the server.
        
        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """
        Check if connection is ready for operations (connected + authenticated).
        
        Returns:
            True if ready for operations, False otherwise
        """
        pass

    @abstractmethod
    def get_connection_state(self) -> ConnectionState:
        """
        Get the current connection state.
        
        Returns:
            Current connection state
        """
        pass

    @abstractmethod
    async def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for connection to be established.
        
        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)
            
        Returns:
            True if connected within timeout, False otherwise
        """
        pass

    @abstractmethod
    async def wait_for_ready(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for connection to be ready for operations.
        
        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)
            
        Returns:
            True if ready within timeout, False otherwise
        """
        pass

    @abstractmethod
    def on_connection_state_changed(
        self, 
        callback: Callable[[ConnectionState], None]
    ) -> None:
        """
        Register a callback for connection state changes.
        
        Args:
            callback: Function to call when connection state changes
        """
        pass

    @abstractmethod
    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """
        Register a callback for connection errors.
        
        Args:
            callback: Function to call when connection errors occur
        """
        pass

    @abstractmethod
    def on_ready(self, callback: Callable[[], None]) -> None:
        """
        Register a callback for when connection is ready for operations.
        
        Args:
            callback: Function to call when connection is ready
        """
        pass

    @abstractmethod
    async def reconnect(self, force: bool = False) -> bool:
        """
        Attempt to reconnect to the server.
        
        Args:
            force: Whether to force reconnection even if currently connected
            
        Returns:
            True if reconnection successful, False otherwise
        """
        pass

    @abstractmethod
    def enable_auto_reconnect(
        self, 
        max_attempts: int = 10, 
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_backoff: bool = True,
        jitter: bool = True
    ) -> None:
        """
        Enable automatic reconnection on connection loss.
        
        Args:
            max_attempts: Maximum number of reconnection attempts
            initial_delay: Initial delay between reconnection attempts (seconds)
            max_delay: Maximum delay between attempts (seconds)
            exponential_backoff: Whether to use exponential backoff for delays
            jitter: Whether to add random jitter to prevent thundering herd
        """
        pass

    @abstractmethod
    def disable_auto_reconnect(self) -> None:
        """Disable automatic reconnection."""
        pass

    @abstractmethod
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get detailed connection information.
        
        Returns:
            Dictionary containing connection details (host, port, protocol, etc.)
        """
        pass

    @abstractmethod
    def get_connection_metrics(self) -> Dict[str, Any]:
        """
        Get connection performance metrics.
        
        Returns:
            Dictionary containing metrics (latency, reconnect count, etc.)
        """
        pass

    @abstractmethod
    async def ping(self, timeout: float = 5.0) -> bool:
        """
        Send a ping to test connection health.
        
        Args:
            timeout: Ping timeout in seconds
            
        Returns:
            True if ping successful, False otherwise
        """
        pass

    @abstractmethod
    async def check_health(self) -> ConnectionHealthStatus:
        """
        Perform comprehensive connection health check.
        
        Returns:
            Current connection health status
        """
        pass

    @abstractmethod
    def get_last_error(self) -> Optional[Exception]:
        """
        Get the last connection error.
        
        Returns:
            Last error exception or None if no error
        """
        pass

    @abstractmethod
    def get_error_history(self, limit: int = 10) -> List[Exception]:
        """
        Get recent connection errors.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of recent error exceptions
        """
        pass

    @abstractmethod
    async def reset_connection(self) -> bool:
        """
        Reset connection to clean state (disconnect + reconnect).
        
        Returns:
            True if reset successful, False otherwise
        """
        pass

    @abstractmethod
    def get_uptime(self) -> float:
        """
        Get connection uptime in seconds.
        
        Returns:
            Connection uptime in seconds
        """
        pass

    @abstractmethod
    def get_reconnect_count(self) -> int:
        """
        Get number of reconnections performed.
        
        Returns:
            Number of reconnections
        """
        pass