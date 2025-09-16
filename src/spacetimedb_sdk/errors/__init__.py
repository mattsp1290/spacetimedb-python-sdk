"""
SpacetimeDB Standardized Error Handling Module

This module provides a consistent error handling pattern across the entire SDK.
It includes a standardized exception hierarchy, error decorators, and logging context.
"""

import logging
import traceback
import functools
from typing import Any, Callable, Optional, Type, TypeVar, Union, Dict
from dataclasses import dataclass
from enum import Enum

# Import existing error types to consolidate them
from ..energy import EnergyError, OutOfEnergyError, EnergyExhaustedException
from ..bsatn import (
    BsatnError, BsatnInvalidTagError, BsatnBufferTooSmallError,
    BsatnInvalidUTF8Error, BsatnOverflowError, BsatnInvalidFloatError,
    BsatnTooLargeError
)

F = TypeVar('F', bound=Callable[..., Any])

class ErrorSeverity(Enum):
    """Error severity levels for logging and handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Categories of errors for better classification."""
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    PROTOCOL = "protocol"
    VALIDATION = "validation"
    SERIALIZATION = "serialization"
    ENERGY = "energy"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    INTERNAL = "internal"
    USER_INPUT = "user_input"

@dataclass
class ErrorContext:
    """Context information for errors."""
    module: str
    function: str
    severity: ErrorSeverity
    category: ErrorCategory
    user_message: Optional[str] = None
    technical_details: Optional[str] = None
    suggestions: Optional[str] = None
    related_data: Optional[Dict[str, Any]] = None

class SpacetimeDBBaseError(Exception):
    """Base exception for all SpacetimeDB SDK errors."""
    
    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.context = context
        self.original_exception = original_exception
        self.timestamp = None
        
    def with_context(self, context: ErrorContext) -> 'SpacetimeDBBaseError':
        """Add context to the error."""
        self.context = context
        return self
        
    def get_user_message(self) -> str:
        """Get user-friendly error message."""
        if self.context and self.context.user_message:
            return self.context.user_message
        return self.message
        
    def get_technical_details(self) -> Optional[str]:
        """Get technical details for debugging."""
        if self.context:
            return self.context.technical_details
        return None
        
    def get_suggestions(self) -> Optional[str]:
        """Get suggestions for resolving the error."""
        if self.context:
            return self.context.suggestions
        return None

class ConnectionError(SpacetimeDBBaseError):
    """Raised when connection-related errors occur."""
    pass

class AuthenticationError(SpacetimeDBBaseError):
    """Raised when authentication fails."""
    pass

class ProtocolError(SpacetimeDBBaseError):
    """Raised when protocol-level errors occur."""
    pass

class ValidationError(SpacetimeDBBaseError):
    """Raised when data validation fails."""
    pass

class SerializationError(SpacetimeDBBaseError):
    """Raised when serialization/deserialization fails."""
    pass

class ConfigurationError(SpacetimeDBBaseError):
    """Raised when configuration is invalid."""
    pass

class NetworkError(SpacetimeDBBaseError):
    """Raised when network operations fail."""
    pass

class InternalError(SpacetimeDBBaseError):
    """Raised when internal SDK errors occur."""
    pass

class UserInputError(SpacetimeDBBaseError):
    """Raised when user input is invalid."""
    pass

# Error category mapping
ERROR_CATEGORY_MAP = {
    ErrorCategory.CONNECTION: ConnectionError,
    ErrorCategory.AUTHENTICATION: AuthenticationError,
    ErrorCategory.PROTOCOL: ProtocolError,
    ErrorCategory.VALIDATION: ValidationError,
    ErrorCategory.SERIALIZATION: SerializationError,
    ErrorCategory.ENERGY: EnergyError,  # Use existing energy error
    ErrorCategory.CONFIGURATION: ConfigurationError,
    ErrorCategory.NETWORK: NetworkError,
    ErrorCategory.INTERNAL: InternalError,
    ErrorCategory.USER_INPUT: UserInputError,
}

def create_error(
    category: ErrorCategory,
    message: str,
    context: Optional[ErrorContext] = None,
    original_exception: Optional[Exception] = None
) -> SpacetimeDBBaseError:
    """Create a standardized error with proper type and context."""
    error_class = ERROR_CATEGORY_MAP.get(category, SpacetimeDBBaseError)
    error = error_class(message, context, original_exception)
    return error

def error_handler(
    category: ErrorCategory,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    user_message: Optional[str] = None,
    suggestions: Optional[str] = None,
    reraise: bool = True,
    log_error: bool = True
) -> Callable[[F], F]:
    """
    Decorator for standardized error handling.
    
    Args:
        category: Error category for classification
        severity: Error severity level
        user_message: User-friendly error message
        suggestions: Suggestions for resolving the error
        reraise: Whether to reraise the exception after handling
        log_error: Whether to log the error
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(
                    module=func.__module__,
                    function=func.__name__,
                    severity=severity,
                    category=category,
                    user_message=user_message,
                    technical_details=str(e),
                    suggestions=suggestions,
                    related_data={
                        'args': str(args)[:200],  # Truncate for privacy
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                )
                
                if log_error:
                    logger = logging.getLogger(f"spacetimedb_sdk.{func.__module__}")
                    log_level = _severity_to_log_level(severity)
                    logger.log(
                        log_level,
                        f"Error in {func.__name__}: {e}",
                        extra={
                            'error_category': category.value,
                            'error_severity': severity.value,
                            'function': func.__name__,
                            'module': func.__module__,
                            'traceback': traceback.format_exc()
                        }
                    )
                
                if isinstance(e, SpacetimeDBBaseError):
                    # Add context to existing SpacetimeDB error
                    e.with_context(context)
                    if reraise:
                        raise
                    return None
                else:
                    # Create new standardized error
                    standardized_error = create_error(category, str(e), context, e)
                    if reraise:
                        raise standardized_error from e
                    return None
        return wrapper
    return decorator

def _severity_to_log_level(severity: ErrorSeverity) -> int:
    """Convert error severity to logging level."""
    mapping = {
        ErrorSeverity.LOW: logging.DEBUG,
        ErrorSeverity.MEDIUM: logging.WARNING,
        ErrorSeverity.HIGH: logging.ERROR,
        ErrorSeverity.CRITICAL: logging.CRITICAL,
    }
    return mapping.get(severity, logging.ERROR)

def safe_execute(
    func: Callable[..., Any],
    *args,
    default_return=None,
    category: ErrorCategory = ErrorCategory.INTERNAL,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    log_errors: bool = True,
    **kwargs
) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Arguments for the function
        default_return: Default return value on error
        category: Error category
        severity: Error severity
        log_errors: Whether to log errors
        **kwargs: Keyword arguments for the function
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger = logging.getLogger("spacetimedb_sdk.safe_execute")
            logger.log(
                _severity_to_log_level(severity),
                f"Error in safe_execute for {func.__name__}: {e}",
                extra={
                    'error_category': category.value,
                    'error_severity': severity.value,
                    'function': func.__name__,
                }
            )
        return default_return

# Import error formatting utilities
from .error_formatting_utils import ErrorFormatter

# Exception hierarchy exports - consolidating all existing exceptions
__all__ = [
    # Base error handling
    'SpacetimeDBBaseError',
    'ErrorContext',
    'ErrorSeverity',
    'ErrorCategory',
    
    # Standardized exceptions
    'ConnectionError',
    'AuthenticationError',
    'ProtocolError',
    'ValidationError',
    'SerializationError',
    'ConfigurationError',
    'NetworkError',
    'InternalError',
    'UserInputError',
    
    # Existing energy errors (re-exported for consolidation)
    'EnergyError',
    'OutOfEnergyError',
    'EnergyExhaustedException',
    
    # Existing BSATN errors (re-exported for consolidation)
    'BsatnError',
    'BsatnInvalidTagError',
    'BsatnBufferTooSmallError',
    'BsatnInvalidUTF8Error',
    'BsatnOverflowError',
    'BsatnInvalidFloatError',
    'BsatnTooLargeError',
    
    # Error handling utilities
    'create_error',
    'error_handler',
    'safe_execute',
    'ERROR_CATEGORY_MAP',
    
    # Error formatting utilities
    'ErrorFormatter',
]