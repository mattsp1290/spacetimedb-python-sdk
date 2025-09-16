"""Error formatting utilities for consistent error messages across the SDK.

This module provides standardized error message formatting functions that ensure
consistent error reporting across all components of the SpacetimeDB SDK.
The formatters are designed with security in mind, particularly for authentication
errors where sensitive information should not be leaked.
"""

from typing import Optional, Any


class ErrorFormatter:
    """Provides standardized error message formatting for different components.
    
    This class offers static methods to format errors consistently across the SDK.
    Each formatter is tailored for specific component types (auth, connection, etc.)
    with appropriate security considerations and context handling.
    """
    
    @staticmethod
    def format_auth_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format authentication-related errors securely.
        
        Authentication errors are formatted with special security considerations:
        - Only error type is exposed, not the actual error message
        - Prevents leaking sensitive authentication information
        - Always includes the error type for debugging
        
        Args:
            operation: The authentication operation that failed (e.g., 'login', 'token_refresh')
            error: The exception that was raised during the operation
            context: Optional context information (e.g., user session ID)
            
        Returns:
            Formatted error message with security-safe information
            
        Example:
            >>> error = ValueError("Invalid password")
            >>> result = ErrorFormatter.format_auth_error("login", error, "user_123")
            >>> print(result)
            Authentication login failed (context: user_123) [error_type: ValueError]
        """
        error_type = type(error).__name__
        base_msg = f"Authentication {operation} failed"
        if context:
            base_msg += f" (context: {context})"
        base_msg += f" [error_type: {error_type}]"
        return base_msg
    
    @staticmethod
    def format_connection_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format connection-related errors.
        
        Connection errors include the full error message as it's typically safe
        to expose network-level error information for debugging purposes.
        
        Args:
            operation: The connection operation that failed (e.g., 'connect', 'disconnect')
            error: The exception that was raised during the operation
            context: Optional context information (e.g., server URL, connection ID)
            
        Returns:
            Formatted error message including the full error details
            
        Example:
            >>> error = ConnectionError("Connection refused")
            >>> result = ErrorFormatter.format_connection_error("connect", error, "ws://localhost:3000")
            >>> print(result)
            Connection connect failed: Connection refused (context: ws://localhost:3000)
        """
        base_msg = f"Connection {operation} failed: {error}"
        if context is not None:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_event_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format event-related errors.
        
        Event errors include the full error message to help with debugging
        event handling and dispatching issues.
        
        Args:
            operation: The event operation that failed (e.g., 'dispatch', 'subscribe')
            error: The exception that was raised during the operation
            context: Optional context information (e.g., event type, handler name)
            
        Returns:
            Formatted error message including the full error details
            
        Example:
            >>> error = KeyError("Handler not found")
            >>> result = ErrorFormatter.format_event_error("dispatch", error, "user_update")
            >>> print(result)
            Event dispatch failed: Handler not found (context: user_update)
        """
        error_msg = str(error.args[0]) if error.args else str(error)
        base_msg = f"Event {operation} failed: {error_msg}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_websocket_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format WebSocket-related errors.
        
        WebSocket errors include the full error message to aid in debugging
        protocol and communication issues.
        
        Args:
            operation: The WebSocket operation that failed (e.g., 'send_message', 'handshake')
            error: The exception that was raised during the operation
            context: Optional context information (e.g., protocol version, message type)
            
        Returns:
            Formatted error message including the full error details
            
        Example:
            >>> error = ValueError("Invalid frame type")
            >>> result = ErrorFormatter.format_websocket_error("send_message", error, "binary_frame")
            >>> print(result)
            WebSocket send_message failed: Invalid frame type (context: binary_frame)
        """
        base_msg = f"WebSocket {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_cache_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format cache-related errors.
        
        Cache errors include the full error message to help with debugging
        cache operations and memory management issues.
        
        Args:
            operation: The cache operation that failed (e.g., 'get', 'set', 'invalidate')
            error: The exception that was raised during the operation
            context: Optional context information (e.g., cache key, cache type)
            
        Returns:
            Formatted error message including the full error details
            
        Example:
            >>> error = KeyError("Cache miss")
            >>> result = ErrorFormatter.format_cache_error("get", error, "user_data_cache")
            >>> print(result)
            Cache get failed: Cache miss (context: user_data_cache)
        """
        error_msg = str(error.args[0]) if error.args else str(error)
        base_msg = f"Cache {operation} failed: {error_msg}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_protocol_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format protocol-related errors.
        
        Protocol errors include the full error message to aid in debugging
        message encoding, decoding, and protocol compliance issues.
        
        Args:
            operation: The protocol operation that failed (e.g., 'encode', 'decode', 'validate')
            error: The exception that was raised during the operation
            context: Optional context information (e.g., message type, protocol version)
            
        Returns:
            Formatted error message including the full error details
            
        Example:
            >>> error = UnicodeDecodeError('utf-8', b'\\xff', 0, 1, 'invalid start byte')
            >>> result = ErrorFormatter.format_protocol_error("decode", error, "message_frame")
            >>> print(result)
            Protocol decode failed: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte (context: message_frame)
        """
        base_msg = f"Protocol {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_generic_error(component: str, operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format generic errors for any component.
        
        This is a generic formatter that can be used for any component not covered
        by the specialized formatters. It includes the full error message.
        
        Args:
            component: The component name where the error occurred (e.g., 'DatabaseClient', 'QueryManager')
            operation: The operation that failed (e.g., 'query', 'update', 'insert')
            error: The exception that was raised during the operation
            context: Optional context information (e.g., table name, query parameters)
            
        Returns:
            Formatted error message including the full error details
            
        Example:
            >>> error = RuntimeError("Database connection lost")
            >>> result = ErrorFormatter.format_generic_error("DatabaseClient", "query", error, "users_table")
            >>> print(result)
            DatabaseClient query failed: Database connection lost (context: users_table)
        """
        base_msg = f"{component} {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg