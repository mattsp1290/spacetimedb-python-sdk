"""Error formatting utilities for consistent error messages across the SDK."""

from typing import Optional, Any


class ErrorFormatter:
    """Provides standardized error message formatting for different components."""
    
    @staticmethod
    def format_auth_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format authentication-related errors securely."""
        error_type = type(error).__name__
        base_msg = f"Authentication {operation} failed"
        if context:
            base_msg += f" (context: {context})"
        base_msg += f" [error_type: {error_type}]"
        return base_msg
    
    @staticmethod
    def format_connection_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format connection-related errors."""
        base_msg = f"Connection {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_event_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format event-related errors."""
        base_msg = f"Event {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_websocket_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format WebSocket-related errors."""
        base_msg = f"WebSocket {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_cache_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format cache-related errors."""
        base_msg = f"Cache {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_protocol_error(operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format protocol-related errors."""
        base_msg = f"Protocol {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg
    
    @staticmethod
    def format_generic_error(component: str, operation: str, error: Exception, context: Optional[str] = None) -> str:
        """Format generic errors for any component."""
        base_msg = f"{component} {operation} failed: {error}"
        if context:
            base_msg += f" (context: {context})"
        return base_msg