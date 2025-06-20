"""
Enhanced Reducer Interface for SpacetimeDB clients.

Combines reducer patterns from blackholio-python-client with the
advanced features of spacetimedb-python-sdk.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List, Union
from enum import Enum
from datetime import datetime, timedelta


class ReducerStatus(Enum):
    """Enhanced reducer call status enumeration."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"


class ReducerPriority(Enum):
    """Reducer call priority enumeration."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class CallReducerFlags(Enum):
    """Reducer call flags."""
    NONE = 0
    NO_SIDE_EFFECTS = 1
    REQUIRE_IMMEDIATE = 2
    ALLOW_RETRY = 4
    REQUIRE_CONFIRMATION = 8


class ReducerInterface(ABC):
    """
    Enhanced abstract interface for SpacetimeDB reducer calls.
    
    This interface provides comprehensive reducer calling capabilities including
    priority handling, retry mechanisms, and advanced error handling.
    """

    @abstractmethod
    async def call_reducer(
        self, 
        reducer_name: str, 
        *args,
        request_id: Optional[str] = None,
        timeout: Optional[float] = None,
        priority: ReducerPriority = ReducerPriority.NORMAL,
        flags: CallReducerFlags = CallReducerFlags.NONE,
        retry_count: int = 0
    ) -> bool:
        """
        Call a reducer on the SpacetimeDB server.
        
        Args:
            reducer_name: Name of the reducer to call
            *args: Arguments to pass to the reducer
            request_id: Optional request ID for tracking
            timeout: Optional timeout for the call (seconds)
            priority: Priority level for the call
            flags: Special flags for the call
            retry_count: Number of retries to attempt on failure
            
        Returns:
            True if reducer call successful, False otherwise
        """
        pass

    @abstractmethod
    async def call_reducer_with_response(
        self,
        reducer_name: str,
        *args,
        request_id: Optional[str] = None,
        timeout: Optional[float] = 10.0,
        priority: ReducerPriority = ReducerPriority.NORMAL,
        flags: CallReducerFlags = CallReducerFlags.NONE
    ) -> Dict[str, Any]:
        """
        Call a reducer and wait for response.
        
        Args:
            reducer_name: Name of the reducer to call
            *args: Arguments to pass to the reducer
            request_id: Optional request ID for tracking
            timeout: Timeout for waiting for response (seconds)
            priority: Priority level for the call
            flags: Special flags for the call
            
        Returns:
            Dictionary containing response data and status
        """
        pass

    @abstractmethod
    async def call_reducer_batch(
        self,
        reducer_calls: List[Dict[str, Any]],
        timeout: Optional[float] = None,
        atomic: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Call multiple reducers in a batch.
        
        Args:
            reducer_calls: List of reducer call specifications
            timeout: Optional timeout for the entire batch
            atomic: Whether all calls must succeed or all fail
            
        Returns:
            List of results for each reducer call
        """
        pass

    @abstractmethod
    async def schedule_reducer_call(
        self,
        reducer_name: str,
        *args,
        delay: Optional[timedelta] = None,
        schedule_time: Optional[datetime] = None,
        repeat_interval: Optional[timedelta] = None,
        max_repeats: Optional[int] = None
    ) -> str:
        """
        Schedule a reducer call for future execution.
        
        Args:
            reducer_name: Name of the reducer to call
            *args: Arguments to pass to the reducer
            delay: Delay before execution
            schedule_time: Specific time to execute
            repeat_interval: Interval for repeated execution
            max_repeats: Maximum number of repeats
            
        Returns:
            Schedule ID for tracking
        """
        pass

    @abstractmethod
    def cancel_scheduled_reducer(self, schedule_id: str) -> bool:
        """
        Cancel a scheduled reducer call.
        
        Args:
            schedule_id: Schedule ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        pass

    @abstractmethod
    def on_reducer_response(
        self, 
        callback: Callable[[str, ReducerStatus, Dict[str, Any]], None]
    ) -> None:
        """
        Register a callback for reducer responses.
        
        Args:
            callback: Function to call when reducer response received
                     (request_id, status, data)
        """
        pass

    @abstractmethod
    def on_reducer_error(
        self, 
        callback: Callable[[str, Exception, Optional[str]], None]
    ) -> None:
        """
        Register a callback for reducer errors.
        
        Args:
            callback: Function to call when reducer error occurs
                     (reducer_name, error, request_id)
        """
        pass

    @abstractmethod
    def on_reducer_started(
        self, 
        callback: Callable[[str, str], None]
    ) -> None:
        """
        Register a callback for when reducer execution starts.
        
        Args:
            callback: Function to call when reducer starts
                     (reducer_name, request_id)
        """
        pass

    @abstractmethod
    def on_reducer_completed(
        self, 
        callback: Callable[[str, str, float], None]
    ) -> None:
        """
        Register a callback for when reducer execution completes.
        
        Args:
            callback: Function to call when reducer completes
                     (reducer_name, request_id, execution_time)
        """
        pass

    @abstractmethod
    def get_pending_reducers(self) -> List[Dict[str, Any]]:
        """
        Get list of pending reducer requests with details.
        
        Returns:
            List of dictionaries containing request details
        """
        pass

    @abstractmethod
    def get_scheduled_reducers(self) -> List[Dict[str, Any]]:
        """
        Get list of scheduled reducer calls.
        
        Returns:
            List of dictionaries containing schedule details
        """
        pass

    @abstractmethod
    def cancel_reducer(self, request_id: str) -> bool:
        """
        Cancel a pending reducer request.
        
        Args:
            request_id: Request ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        pass

    @abstractmethod
    def cancel_all_reducers(self) -> int:
        """
        Cancel all pending reducer requests.
        
        Returns:
            Number of requests cancelled
        """
        pass

    @abstractmethod
    def get_reducer_status(self, request_id: str) -> Optional[ReducerStatus]:
        """
        Get status of a specific reducer request.
        
        Args:
            request_id: Request ID to check
            
        Returns:
            Current status or None if request not found
        """
        pass

    @abstractmethod
    def get_reducer_result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get result of a completed reducer request.
        
        Args:
            request_id: Request ID to get result for
            
        Returns:
            Result dictionary or None if not available
        """
        pass

    @abstractmethod
    def set_reducer_timeout(self, reducer_name: str, timeout: float) -> None:
        """
        Set default timeout for a specific reducer.
        
        Args:
            reducer_name: Name of the reducer
            timeout: Default timeout in seconds
        """
        pass

    @abstractmethod
    def set_reducer_priority(
        self, 
        reducer_name: str, 
        priority: ReducerPriority
    ) -> None:
        """
        Set default priority for a specific reducer.
        
        Args:
            reducer_name: Name of the reducer
            priority: Default priority level
        """
        pass

    @abstractmethod
    def set_global_reducer_timeout(self, timeout: float) -> None:
        """
        Set global default timeout for all reducers.
        
        Args:
            timeout: Default timeout in seconds
        """
        pass

    @abstractmethod
    def enable_reducer_rate_limiting(
        self, 
        max_calls_per_second: float,
        burst_size: int = 10
    ) -> None:
        """
        Enable rate limiting for reducer calls.
        
        Args:
            max_calls_per_second: Maximum calls per second
            burst_size: Maximum burst size
        """
        pass

    @abstractmethod
    def disable_reducer_rate_limiting(self) -> None:
        """Disable rate limiting for reducer calls."""
        pass

    @abstractmethod
    def get_reducer_info(self) -> Dict[str, Any]:
        """
        Get detailed reducer information and statistics.
        
        Returns:
            Dictionary containing reducer call statistics and state
        """
        pass

    @abstractmethod
    def get_reducer_metrics(self) -> Dict[str, Any]:
        """
        Get reducer performance metrics.
        
        Returns:
            Dictionary containing metrics (success rate, avg latency, etc.)
        """
        pass

    @abstractmethod
    def get_reducer_schema(self, reducer_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schema information for a reducer.
        
        Args:
            reducer_name: Name of the reducer
            
        Returns:
            Schema dictionary or None if not available
        """
        pass

    @abstractmethod
    def list_available_reducers(self) -> List[str]:
        """
        Get list of available reducers on the server.
        
        Returns:
            List of reducer names
        """
        pass

    @abstractmethod
    def validate_reducer_args(
        self, 
        reducer_name: str, 
        *args
    ) -> bool:
        """
        Validate arguments for a reducer call.
        
        Args:
            reducer_name: Name of the reducer
            *args: Arguments to validate
            
        Returns:
            True if arguments are valid, False otherwise
        """
        pass

    @abstractmethod
    async def test_reducer_connection(self) -> bool:
        """
        Test if reducer calling functionality is working.
        
        Returns:
            True if reducer calls are working, False otherwise
        """
        pass

    # Convenience method for waiting on multiple reducers
    @abstractmethod
    async def wait_for_reducers(
        self, 
        request_ids: List[str],
        timeout: Optional[float] = None,
        require_all: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Wait for multiple reducer calls to complete.
        
        Args:
            request_ids: List of request IDs to wait for
            timeout: Maximum time to wait
            require_all: Whether to wait for all or just any to complete
            
        Returns:
            Dictionary mapping request IDs to results
        """
        pass