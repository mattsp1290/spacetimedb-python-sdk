"""
RequestTracker - System for tracking reducer call requests and responses

This module provides the RequestTracker class that manages request IDs,
tracks pending requests, and correlates requests with their responses.
"""

import time
import threading
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class PendingRequest:
    """Information about a pending request."""
    request_id: int
    timestamp: float
    timeout_seconds: float
    response: Optional[Any] = None


class RequestTracker:
    """
    Tracks reducer call requests and their responses.
    
    This class provides:
    - Unique request ID generation
    - Pending request tracking
    - Request-response correlation
    - Timeout management
    - Thread-safe operations
    """
    
    def __init__(self, default_timeout: float = 30.0):
        """
        Initialize the request tracker.
        
        Args:
            default_timeout: Default timeout in seconds for requests
        """
        self._lock = threading.Lock()
        self._next_request_id = 1
        self._pending_requests: Dict[int, PendingRequest] = {}
        self._completed_responses: Dict[int, Any] = {}
        self._default_timeout = default_timeout
    
    def generate_request_id(self) -> int:
        """
        Generate a unique request ID.
        
        Returns:
            A unique integer request ID
        """
        with self._lock:
            request_id = self._next_request_id
            self._next_request_id += 1
            # Handle wrap-around at reasonable limit (2^31 - 1)
            if self._next_request_id >= 2147483647:
                self._next_request_id = 1
            return request_id
    
    def add_pending_request(
        self, 
        request_id: int, 
        timeout_seconds: Optional[float] = None
    ) -> None:
        """
        Add a request to the pending requests tracker.
        
        Args:
            request_id: The request ID to track
            timeout_seconds: Timeout for this specific request (uses default if None)
        """
        timeout = timeout_seconds if timeout_seconds is not None else self._default_timeout
        
        with self._lock:
            pending_request = PendingRequest(
                request_id=request_id,
                timestamp=time.time(),
                timeout_seconds=timeout
            )
            self._pending_requests[request_id] = pending_request
    
    def is_request_pending(self, request_id: int) -> bool:
        """
        Check if a request is still pending.
        
        Args:
            request_id: The request ID to check
            
        Returns:
            True if the request is pending, False otherwise
        """
        with self._lock:
            return request_id in self._pending_requests
    
    def resolve_request(self, request_id: int, response: Any) -> bool:
        """
        Resolve a pending request with a response.
        
        Args:
            request_id: The request ID to resolve
            response: The response data
            
        Returns:
            True if the request was pending and resolved, False otherwise
        """
        with self._lock:
            if request_id in self._pending_requests:
                # Remove from pending and store response
                del self._pending_requests[request_id]
                self._completed_responses[request_id] = response
                return True
            return False
    
    def get_response(self, request_id: int) -> Optional[Any]:
        """
        Get the response for a completed request.
        
        Args:
            request_id: The request ID to get response for
            
        Returns:
            The response data if available, None otherwise
        """
        with self._lock:
            return self._completed_responses.get(request_id)
    
    def remove_completed_response(self, request_id: int) -> Optional[Any]:
        """
        Remove and return a completed response.
        
        Args:
            request_id: The request ID to remove
            
        Returns:
            The response data if it existed, None otherwise
        """
        with self._lock:
            return self._completed_responses.pop(request_id, None)
    
    def check_timeouts(self) -> Set[int]:
        """
        Check for timed out requests and remove them.
        
        Returns:
            Set of request IDs that have timed out
        """
        current_time = time.time()
        timed_out_requests = set()
        
        with self._lock:
            # Find timed out requests
            for request_id, pending_request in list(self._pending_requests.items()):
                elapsed = current_time - pending_request.timestamp
                if elapsed > pending_request.timeout_seconds:
                    timed_out_requests.add(request_id)
                    del self._pending_requests[request_id]
        
        return timed_out_requests
    
    def get_pending_count(self) -> int:
        """
        Get the number of pending requests.
        
        Returns:
            Number of currently pending requests
        """
        with self._lock:
            return len(self._pending_requests)
    
    def get_completed_count(self) -> int:
        """
        Get the number of completed responses.
        
        Returns:
            Number of completed responses waiting to be retrieved
        """
        with self._lock:
            return len(self._completed_responses)
    
    def clear_all(self) -> None:
        """Clear all pending requests and completed responses."""
        with self._lock:
            self._pending_requests.clear()
            self._completed_responses.clear()
    
    def get_pending_request_ids(self) -> Set[int]:
        """
        Get the set of all pending request IDs.
        
        Returns:
            Set of pending request IDs
        """
        with self._lock:
            return set(self._pending_requests.keys())
    
    def get_oldest_pending_age(self) -> Optional[float]:
        """
        Get the age in seconds of the oldest pending request.
        
        Returns:
            Age in seconds of oldest pending request, or None if no pending requests
        """
        current_time = time.time()
        
        with self._lock:
            if not self._pending_requests:
                return None
            
            oldest_timestamp = min(
                pending.timestamp for pending in self._pending_requests.values()
            )
            return current_time - oldest_timestamp 