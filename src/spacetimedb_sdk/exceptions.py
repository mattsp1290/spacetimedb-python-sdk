"""
SpaceTimeDB SDK Exception Classes - Enhanced for v1.1.2

This module defines custom exceptions with technical diagnostics for debugging
in the SpaceTimeDB Python SDK v1.1.2.
"""

import time
from typing import Optional, Dict, Any, List, Type


class SpacetimeDBError(Exception):
    """
    Base exception for all SpaceTimeDB SDK errors with enhanced diagnostics.
    
    Attributes:
        message: Human-readable error message
        error_code: Error code for programmatic handling
        diagnostic_info: Technical debugging information
        recovery_hint: Suggested recovery action
        timestamp: When the error occurred
        details: Legacy details field for backward compatibility
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        diagnostic_info: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.diagnostic_info = diagnostic_info or {}
        self.recovery_hint = recovery_hint
        self.timestamp = time.time()
        self.details = details or {}
        
        # Merge details into diagnostic_info for consistency
        if self.details and not self.diagnostic_info:
            self.diagnostic_info = self.details
    
    def __str__(self) -> str:
        """Format error with technical information."""
        parts = []
        
        # Main error message
        if self.error_code:
            parts.append(f"[{self.error_code}] {self.message}")
        else:
            parts.append(self.message)
        
        # Add timestamp
        parts.append(f"Timestamp: {self.timestamp:.3f}")
        
        # Add diagnostic info if available
        if self.diagnostic_info:
            parts.append("Diagnostic Info:")
            for key, value in self.diagnostic_info.items():
                if isinstance(value, dict):
                    parts.append(f"  - {key}:")
                    for sub_key, sub_value in value.items():
                        parts.append(f"      {sub_key}: {sub_value}")
                elif isinstance(value, list):
                    parts.append(f"  - {key}:")
                    for item in value:
                        parts.append(f"      • {item}")
                else:
                    parts.append(f"  - {key}: {value}")
        
        # Add recovery hint
        if self.recovery_hint:
            parts.append(f"Recovery Hint: {self.recovery_hint}")
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "timestamp": self.timestamp,
            "diagnostic_info": self.diagnostic_info,
            "recovery_hint": self.recovery_hint
        }


class RetryableError(SpacetimeDBError):
    """Base class for errors that can be retried."""
    pass


class DatabaseNotPublishedError(SpacetimeDBError):
    """
    Specific error for databases that exist but aren't published.
    Provides technical diagnostics and clear fix commands.
    """
    
    def __init__(
        self,
        database_name: str,
        host: str,
        diagnostic_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.database_name = database_name
        self.host = host
        
        # Build technical error message
        message = f"Database '{database_name}' not found on {host}"
        
        # Enhanced diagnostic info
        enhanced_diagnostic_info = {
            'database': database_name,
            'host': host,
            'url_attempted': f"ws://{host}/v1/database/{database_name}/subscribe",
            'likely_cause': 'Database not published',
            'fix_command': f'spacetime publish {database_name}',
            'alternative_fix': f'spacetime publish {database_name} --local',
            **kwargs.get('diagnostic_info', {})
        }
        
        # Recovery hint
        recovery_hint = f"Run 'spacetime publish {database_name}' to publish your database"
        
        super().__init__(
            message=message,
            error_code='DB_NOT_PUBLISHED',
            diagnostic_info=enhanced_diagnostic_info,
            recovery_hint=recovery_hint
        )


class DatabaseNotFoundError(SpacetimeDBError):
    """
    Raised when a database doesn't exist or isn't published.
    Enhanced with technical diagnostics for debugging.
    """
    
    def __init__(
        self,
        database_name: str,
        status_code: int = 404,
        server_message: Optional[str] = None,
        diagnostic_info: Optional[Dict[str, Any]] = None,
        is_likely_unpublished: bool = False
    ):
        self.database_name = database_name
        self.status_code = status_code
        self.server_message = server_message
        self.is_likely_unpublished = is_likely_unpublished
        
        # Extract diagnostic data
        db_state = diagnostic_info.get("database_state", "unknown") if diagnostic_info else "unknown"
        confidence = diagnostic_info.get("confidence", "low") if diagnostic_info else "low"
        
        # Technical error message
        message = f"Failed to connect to database '{database_name}' (HTTP {status_code})"
        
        # Enhanced diagnostic info
        enhanced_diagnostic_info = {
            "database_name": database_name,
            "status_code": status_code,
            "server_message": server_message,
            "database_state": db_state,
            "confidence": confidence,
            "is_likely_unpublished": is_likely_unpublished,
            **(diagnostic_info or {})
        }
        
        # Determine recovery hint based on state
        if is_likely_unpublished or db_state == "unpublished":
            recovery_hint = f"spacetime publish {database_name} --clear-database"
            error_code = "DB_NOT_PUBLISHED"
        elif db_state == "non-existent":
            recovery_hint = f"spacetime publish {database_name} --clear-database OR check database name with 'spacetime list'"
            error_code = "DB_NOT_FOUND"
        else:
            recovery_hint = f"spacetime publish {database_name} --clear-database OR verify database name"
            error_code = "DATABASE_NOT_FOUND"
        
        super().__init__(
            message=message,
            error_code=error_code,
            diagnostic_info=enhanced_diagnostic_info,
            recovery_hint=recovery_hint
        )
    
    @property
    def is_unpublished(self) -> bool:
        """Check if the database is likely unpublished."""
        return (
            self.is_likely_unpublished or
            self.diagnostic_info.get("database_state") == "unpublished" or
            (self.diagnostic_info.get("database_state") == "unknown" and 
             self.diagnostic_info.get("confidence") in ["medium", "high"])
        )


class ProtocolMismatchError(SpacetimeDBError):
    """Raised when the server rejects the protocol version."""
    
    def __init__(
        self,
        requested_protocol: str,
        supported_protocols: Optional[List[str]] = None,
        server_message: Optional[str] = None
    ):
        self.requested_protocol = requested_protocol
        self.supported_protocols = supported_protocols or []
        
        message = f"Protocol mismatch: Server rejected protocol '{requested_protocol}'"
        
        diagnostic_info = {
            "requested_protocol": requested_protocol,
            "supported_protocols": supported_protocols,
            "server_message": server_message,
            "valid_protocols": ["v1.json.spacetimedb", "v1.bsatn.spacetimedb"]
        }
        
        recovery_hint = "Update SDK or use a supported protocol (v1.json.spacetimedb or v1.bsatn.spacetimedb)"
        
        super().__init__(
            message=message,
            error_code="PROTOCOL_MISMATCH",
            diagnostic_info=diagnostic_info,
            recovery_hint=recovery_hint
        )


class ServerNotAvailableError(RetryableError):
    """Raised when the SpaceTimeDB server cannot be reached. Can be retried."""
    
    def __init__(
        self,
        server_address: str,
        reason: str,
        network_diagnostics: Optional[Dict[str, Any]] = None
    ):
        self.server_address = server_address
        self.reason = reason
        
        message = f"Cannot reach SpaceTimeDB server at '{server_address}': {reason}"
        
        diagnostic_info = {
            "server_address": server_address,
            "reason": reason,
            "health_check_url": f"http://{server_address}/health",
            **(network_diagnostics or {})
        }
        
        recovery_hint = f"Verify server is running and try: curl http://{server_address}/health"
        
        super().__init__(
            message=message,
            error_code="SERVER_NOT_AVAILABLE",
            diagnostic_info=diagnostic_info,
            recovery_hint=recovery_hint
        )


class AuthenticationError(SpacetimeDBError):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        reason: str,
        auth_method: Optional[str] = None,
        status_code: Optional[int] = None,
        token_expired: bool = False
    ):
        self.reason = reason
        self.auth_method = auth_method
        self.status_code = status_code
        self.token_expired = token_expired
        
        message = f"Authentication failed: {reason}"
        
        diagnostic_info = {
            "reason": reason,
            "auth_method": auth_method,
            "status_code": status_code,
            "token_expired": token_expired
        }
        
        if token_expired:
            recovery_hint = "Token expired. Reconnect without token to get a new one."
            error_code = "AUTH_TOKEN_EXPIRED"
        else:
            recovery_hint = "Check auth token or reconnect anonymously"
            error_code = "AUTHENTICATION_ERROR"
        
        super().__init__(
            message=message,
            error_code=error_code,
            diagnostic_info=diagnostic_info,
            recovery_hint=recovery_hint
        )


class ConnectionTimeoutError(RetryableError):
    """Raised when a connection attempt times out. Can be retried."""
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        retry_count: int = 0
    ):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        
        message = f"Connection timeout during: {operation} (timeout: {timeout_seconds}s)"
        
        diagnostic_info = {
            "operation": operation,
            "timeout_seconds": timeout_seconds,
            "retry_count": retry_count
        }
        
        recovery_hint = "Increase timeout or check network/server load"
        
        super().__init__(
            message=message,
            error_code="CONNECTION_TIMEOUT",
            diagnostic_info=diagnostic_info,
            recovery_hint=recovery_hint
        )


class WebSocketHandshakeError(SpacetimeDBError):
    """Raised when WebSocket handshake fails with detailed information."""
    
    def __init__(
        self,
        status_code: int,
        status_message: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        diagnostic_info: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.status_message = status_message
        self.url = url
        self.headers = headers or {}
        
        # For 404 errors, check if it's likely an unpublished database
        if status_code == 404:
            database_name = self._extract_database_name(url)
            is_likely_unpublished = diagnostic_info.get("is_likely_unpublished", False) if diagnostic_info else False
            
            # Create a more specific error
            raise DatabaseNotFoundError(
                database_name=database_name,
                status_code=status_code,
                server_message=status_message,
                is_likely_unpublished=is_likely_unpublished,
                diagnostic_info={
                    "url": url,
                    "headers": headers,
                    **(diagnostic_info or {})
                }
            )
        
        message = f"WebSocket handshake failed: {status_code} {status_message}"
        
        enhanced_diagnostic_info = {
            "status_code": status_code,
            "status_message": status_message,
            "url": url,
            "headers": headers,
            **(diagnostic_info or {})
        }
        
        recovery_hint = self._get_recovery_hint(status_code)
        
        super().__init__(
            message=message,
            error_code=f"WS_HANDSHAKE_{status_code}",
            diagnostic_info=enhanced_diagnostic_info,
            recovery_hint=recovery_hint
        )
    
    @staticmethod
    def _extract_database_name(url: str) -> str:
        """Extract database name from WebSocket URL."""
        # URL format: ws://host/v1/database/{name}/subscribe
        parts = url.split("/")
        try:
            if "database" in parts:
                db_index = parts.index("database")
                if db_index + 1 < len(parts):
                    return parts[db_index + 1]
        except:
            pass
        return "unknown"
    
    @staticmethod
    def _get_recovery_hint(status_code: int) -> str:
        """Get recovery hint based on status code."""
        hints = {
            401: "Check authentication token",
            403: "Verify access permissions",
            404: "Check database name and ensure it's published",
            500: "Server error - check server logs",
            503: "Server unavailable - try again later"
        }
        return hints.get(status_code, "Check connection parameters and server status")


class SpacetimeDBConnectionError(SpacetimeDBError):
    """General connection error with comprehensive diagnostics."""
    
    def __init__(
        self,
        message: str,
        cause: Optional[Exception] = None,
        connection_info: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        retryable: bool = False
    ):
        self.cause = cause
        self.retryable = retryable
        
        diagnostic_info = {
            "cause": str(cause) if cause else None,
            "cause_type": type(cause).__name__ if cause else None,
            "retryable": retryable,
            **(connection_info or {})
        }
        
        recovery_hint = suggestions[0] if suggestions else None
        
        super().__init__(
            message=message,
            error_code="CONNECTION_ERROR",
            diagnostic_info=diagnostic_info,
            recovery_hint=recovery_hint
        )


class RetryableConnectionError(RetryableError):
    """Marks connection errors that can be safely retried."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="RETRYABLE_CONNECTION_ERROR",
            **kwargs
        )


# Maintain backward compatibility
__all__ = [
    'SpacetimeDBError',
    'DatabaseNotFoundError',
    'DatabaseNotPublishedError',
    'ProtocolMismatchError',
    'ServerNotAvailableError',
    'AuthenticationError',
    'ConnectionTimeoutError',
    'WebSocketHandshakeError',
    'SpacetimeDBConnectionError',
    'RetryableError',
    'RetryableConnectionError'
]
