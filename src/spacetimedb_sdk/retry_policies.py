"""
Retry Policies for SpaceTimeDB v1.1.2

Provides configurable retry policies for handling transient connection errors.
"""

import time
import random
import threading
from dataclasses import dataclass, field
from typing import List, Type, Optional, Callable, Any, Dict
from enum import Enum

from .exceptions import (
    RetryableError,
    ServerNotAvailableError,
    ConnectionTimeoutError,
    RetryableConnectionError
)


class BackoffStrategy(Enum):
    """Backoff strategies for retry policies."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryPolicy:
    """
    Configurable retry policy for connection operations.
    
    Attributes:
        max_attempts: Maximum number of retry attempts (0 = no retries)
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        backoff_strategy: Strategy for calculating delays
        retryable_errors: List of exception types that can be retried
        retry_condition: Optional custom function to determine if retry should happen
        on_retry: Optional callback called before each retry
    """
    
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER
    retryable_errors: List[Type[Exception]] = field(default_factory=lambda: [
        RetryableError,
        ConnectionTimeoutError,
        ServerNotAvailableError,
        RetryableConnectionError,
        ConnectionRefusedError,
        TimeoutError
    ])
    retry_condition: Optional[Callable[[Exception], bool]] = None
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if an operation should be retried.
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-based)
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_attempts:
            return False
        
        # Check custom retry condition first
        if self.retry_condition:
            return self.retry_condition(error)
        
        # Check if error type is retryable
        return any(isinstance(error, error_type) for error_type in self.retryable_errors)
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        if self.backoff_strategy == BackoffStrategy.CONSTANT:
            delay = self.initial_delay
            
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.initial_delay * attempt
            
        elif self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
            
        elif self.backoff_strategy == BackoffStrategy.EXPONENTIAL_JITTER:
            # Exponential with jitter to prevent thundering herd
            base_delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
            jitter = random.uniform(0, base_delay * 0.1)  # 10% jitter
            delay = base_delay + jitter
            
        else:
            delay = self.initial_delay
        
        # Clamp to max delay
        return min(delay, self.max_delay)
    
    def execute_with_retry(self, operation: Callable[[], Any]) -> Any:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Function to execute
            
        Returns:
            Result of the operation
            
        Raises:
            The last exception if all retries fail
        """
        last_error = None
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation()
                
            except Exception as error:
                last_error = error
                
                if not self.should_retry(error, attempt):
                    raise
                
                if attempt < self.max_attempts:
                    delay = self.get_delay(attempt)
                    
                    # Call retry callback if provided
                    if self.on_retry:
                        self.on_retry(attempt, error, delay)
                    
                    # Wait before retry
                    time.sleep(delay)
        
        # All retries exhausted
        raise last_error


class RetryPolicyPresets:
    """Common retry policy presets."""
    
    @staticmethod
    def aggressive() -> RetryPolicy:
        """Aggressive retry policy for critical operations."""
        return RetryPolicy(
            max_attempts=10,
            initial_delay=0.5,
            max_delay=60.0,
            exponential_base=1.5,
            backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER
        )
    
    @staticmethod
    def standard() -> RetryPolicy:
        """Standard retry policy for normal operations."""
        return RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER
        )
    
    @staticmethod
    def conservative() -> RetryPolicy:
        """Conservative retry policy to avoid overload."""
        return RetryPolicy(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=60.0,
            exponential_base=3.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL
        )
    
    @staticmethod
    def no_retry() -> RetryPolicy:
        """No retry policy - fail immediately."""
        return RetryPolicy(
            max_attempts=0,
            initial_delay=0,
            max_delay=0
        )
    
    @staticmethod
    def custom(
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        retryable_errors: Optional[List[Type[Exception]]] = None
    ) -> RetryPolicy:
        """Create a custom retry policy."""
        policy = RetryPolicy(
            max_attempts=max_attempts,
            initial_delay=initial_delay
        )
        
        if retryable_errors:
            policy.retryable_errors = retryable_errors
            
        return policy


class RetryableOperation:
    """
    Wrapper for operations that should be retried on failure.
    
    This class provides a context manager interface for retry logic.
    """
    
    def __init__(
        self,
        policy: RetryPolicy,
        operation_name: str = "operation",
        logger: Optional[Any] = None
    ):
        self.policy = policy
        self.operation_name = operation_name
        self.logger = logger
        self.attempt = 0
        self.start_time = None
        
    def __enter__(self):
        """Enter retry context."""
        self.attempt = 1
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Handle exceptions with retry logic."""
        if exc_val is None:
            # No exception, success
            return False
        
        # Check if we should retry
        if self.policy.should_retry(exc_val, self.attempt):
            if self.attempt < self.policy.max_attempts:
                delay = self.policy.get_delay(self.attempt)
                
                if self.logger:
                    self.logger.warning(
                        f"Retry {self.attempt}/{self.policy.max_attempts} for {self.operation_name} "
                        f"after {delay:.1f}s delay. Error: {exc_val}"
                    )
                
                # Call retry callback
                if self.policy.on_retry:
                    self.policy.on_retry(self.attempt, exc_val, delay)
                
                # Sleep and retry
                time.sleep(delay)
                self.attempt += 1
                
                # Suppress exception to retry
                return True
        
        # Don't retry - let exception propagate
        return False
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since operation started."""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0


class CircuitBreaker:
    """
    Circuit breaker pattern for preventing cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Requests fail immediately without attempting
    - HALF_OPEN: Test if service has recovered
    """
    
    class State(Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = self.State.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.lock = threading.Lock()
    
    def call(self, func: Callable[[], Any]) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            
        Returns:
            Result of function
            
        Raises:
            Exception from function or CircuitBreakerOpenError
        """
        with self.lock:
            if self.state == self.State.OPEN:
                # Check if we should try half-open
                if self._should_attempt_reset():
                    self.state = self.State.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN (failures: {self.failure_count})"
                    )
        
        try:
            result = func()
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful call."""
        with self.lock:
            self.failure_count = 0
            self.state = self.State.CLOSED
    
    def _on_failure(self):
        """Handle failed call."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = self.State.OPEN
            elif self.state == self.State.HALF_OPEN:
                self.state = self.State.OPEN
    
    def reset(self):
        """Manually reset the circuit breaker."""
        with self.lock:
            self.state = self.State.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        with self.lock:
            return {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time
            }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and preventing calls."""
    pass


# Export convenience functions
def with_retry(
    func: Callable[[], Any],
    policy: Optional[RetryPolicy] = None,
    operation_name: str = "operation"
) -> Any:
    """
    Execute a function with retry logic.
    
    Args:
        func: Function to execute
        policy: Retry policy (uses standard if not provided)
        operation_name: Name for logging
        
    Returns:
        Result of function
        
    Example:
        result = with_retry(
            lambda: client.connect(),
            policy=RetryPolicyPresets.aggressive()
        )
    """
    if policy is None:
        policy = RetryPolicyPresets.standard()
    
    return policy.execute_with_retry(func)


__all__ = [
    'RetryPolicy',
    'RetryPolicyPresets',
    'RetryableOperation',
    'CircuitBreaker',
    'CircuitBreakerOpenError',
    'BackoffStrategy',
    'with_retry'
]
