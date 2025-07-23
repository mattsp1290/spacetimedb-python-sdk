"""Error formatting utilities for consistent error messages across the SDK.

This module provides standardized error message formatting functions that ensure
consistent error reporting across all components of the SpacetimeDB SDK.
The formatters are designed with security in mind, particularly for authentication
errors where sensitive information should not be leaked.

This module consolidates error formatting functionality and provides a unified
interface for all error formatting operations within the SpacetimeDB SDK.
"""

from typing import Optional, Any
import traceback
import logging

# Import the main ErrorFormatter from utils for backwards compatibility
from ..utils.error_formatting import ErrorFormatter as _UtilsErrorFormatter


class ErrorFormatter(_UtilsErrorFormatter):
    """Enhanced error formatter with additional SDK-specific formatting capabilities.
    
    This class extends the base ErrorFormatter from utils with additional
    methods specific to the SpacetimeDB SDK error handling system.
    """
    
    @staticmethod
    def format_exception(exception: Exception, context: Optional[str] = None, 
                        include_traceback: bool = False) -> str:
        """Format any exception with optional context and traceback.
        
        This is a general-purpose exception formatter that can handle any
        exception type with appropriate context information.
        
        Args:
            exception: The exception to format
            context: Optional context information
            include_traceback: Whether to include the full traceback
            
        Returns:
            Formatted error message
            
        Example:
            >>> error = ValueError("Invalid input data")
            >>> result = ErrorFormatter.format_exception(error, "user_validation")
            >>> print(result)
            Exception ValueError: Invalid input data (context: user_validation)
        """
        error_type = type(exception).__name__
        error_message = str(exception)
        
        base_msg = f"Exception {error_type}: {error_message}"
        if context:
            base_msg += f" (context: {context})"
            
        if include_traceback:
            tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
            base_msg += f"\nTraceback:\n{''.join(tb)}"
            
        return base_msg
    
    @staticmethod
    def format_validation_error(operation: str, error: Exception, 
                              field_name: Optional[str] = None,
                              value: Optional[Any] = None) -> str:
        """Format validation-related errors.
        
        Validation errors include information about the field that failed
        validation and optionally the value that caused the failure.
        
        Args:
            operation: The validation operation that failed
            error: The exception that was raised
            field_name: Optional name of the field that failed validation
            value: Optional value that failed validation (will be sanitized)
            
        Returns:
            Formatted error message
            
        Example:
            >>> error = ValueError("Invalid email format")
            >>> result = ErrorFormatter.format_validation_error("email_check", error, "email", "invalid@")
            >>> print(result)
            Validation email_check failed: Invalid email format (field: email, value: invalid@)
        """
        base_msg = f"Validation {operation} failed: {error}"
        
        if field_name:
            base_msg += f" (field: {field_name}"
            if value is not None:
                # Sanitize value to prevent information leakage
                sanitized_value = str(value)[:50]  # Truncate long values
                if len(str(value)) > 50:
                    sanitized_value += "..."
                base_msg += f", value: {sanitized_value}"
            base_msg += ")"
            
        return base_msg
    
    @staticmethod
    def format_serialization_error(operation: str, error: Exception, 
                                 data_type: Optional[str] = None,
                                 context: Optional[str] = None) -> str:
        """Format serialization/deserialization errors.
        
        Serialization errors include information about the data type being
        processed and the specific operation that failed.
        
        Args:
            operation: The serialization operation (encode/decode)
            error: The exception that was raised
            data_type: Optional type of data being serialized
            context: Optional context information
            
        Returns:
            Formatted error message
            
        Example:
            >>> error = UnicodeDecodeError('utf-8', b'\\xff', 0, 1, 'invalid start byte')
            >>> result = ErrorFormatter.format_serialization_error("decode", error, "binary_data")
            >>> print(result)
            Serialization decode failed: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte (data_type: binary_data)
        """
        base_msg = f"Serialization {operation} failed: {error}"
        
        if data_type:
            base_msg += f" (data_type: {data_type}"
            if context:
                base_msg += f", context: {context}"
            base_msg += ")"
        elif context:
            base_msg += f" (context: {context})"
            
        return base_msg
    
    @staticmethod
    def format_sdk_error(component: str, operation: str, error: Exception,
                        error_code: Optional[str] = None,
                        context: Optional[str] = None) -> str:
        """Format SpacetimeDB SDK-specific errors.
        
        This formatter includes SDK-specific information like error codes
        and component context for better debugging.
        
        Args:
            component: SDK component where error occurred
            operation: The operation that failed
            error: The exception that was raised
            error_code: Optional SDK error code
            context: Optional context information
            
        Returns:
            Formatted error message
            
        Example:
            >>> error = ConnectionError("Connection refused")
            >>> result = ErrorFormatter.format_sdk_error("WebSocketClient", "connect", error, "CONN_001")
            >>> print(result)
            SpacetimeDB WebSocketClient connect failed: Connection refused (error_code: CONN_001)
        """
        base_msg = f"SpacetimeDB {component} {operation} failed: {error}"
        
        details = []
        if error_code:
            details.append(f"error_code: {error_code}")
        if context:
            details.append(f"context: {context}")
            
        if details:
            base_msg += f" ({', '.join(details)})"
            
        return base_msg


# For compatibility with potential imports looking for specific functions
def format_exception(exception: Exception, context: Optional[str] = None, 
                    include_traceback: bool = False) -> str:
    """Standalone function for exception formatting."""
    return ErrorFormatter.format_exception(exception, context, include_traceback)


def format_auth_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
    """Standalone function for authentication error formatting."""
    return ErrorFormatter.format_auth_error(operation, error, context)


def format_connection_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
    """Standalone function for connection error formatting."""
    return ErrorFormatter.format_connection_error(operation, error, context)


def format_validation_error(operation: str, error: Exception, 
                          field_name: Optional[str] = None,
                          value: Optional[Any] = None) -> str:
    """Standalone function for validation error formatting."""
    return ErrorFormatter.format_validation_error(operation, error, field_name, value)


def format_serialization_error(operation: str, error: Exception, 
                             data_type: Optional[str] = None,
                             context: Optional[str] = None) -> str:
    """Standalone function for serialization error formatting."""
    return ErrorFormatter.format_serialization_error(operation, error, data_type, context)


def format_sdk_error(component: str, operation: str, error: Exception,
                    error_code: Optional[str] = None,
                    context: Optional[str] = None) -> str:
    """Standalone function for SDK error formatting."""
    return ErrorFormatter.format_sdk_error(component, operation, error, error_code, context)


__all__ = [
    'ErrorFormatter',
    'format_exception',
    'format_auth_error',
    'format_connection_error',
    'format_validation_error',
    'format_serialization_error',
    'format_sdk_error',
]