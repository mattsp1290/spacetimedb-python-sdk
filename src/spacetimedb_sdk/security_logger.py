"""
Security Event Logging for SpacetimeDB Python SDK

This module provides centralized security logging functionality to ensure
all security-related events are properly logged with appropriate severity
and context information.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, Union
from enum import Enum
from .exceptions import (
    SecurityError,
    ValidationSecurityError,
    AuthenticationSecurityError,
    ProtocolSecurityError,
    ConnectionSecurityError
)


class SecurityEventType(Enum):
    """Types of security events that can be logged."""
    VALIDATION_FAILURE = "validation_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    PROTOCOL_VIOLATION = "protocol_violation"
    CONNECTION_VIOLATION = "connection_violation"
    INJECTION_ATTEMPT = "injection_attempt"
    OVERSIZED_INPUT = "oversized_input"
    MALFORMED_DATA = "malformed_data"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    TOKEN_TAMPERING = "token_tampering"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class SecurityEventSeverity(Enum):
    """Severity levels for security events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityLogger:
    """
    Centralized security event logger with structured logging and context tracking.
    
    This logger ensures all security events are properly captured with:
    - Appropriate severity levels
    - Structured context information
    - Timestamps and event correlation
    - Configurable output formats
    """
    
    def __init__(self, logger_name: Optional[str] = None):
        """
        Initialize security logger.
        
        Args:
            logger_name: Optional logger name, defaults to security logger
        """
        self.logger = logging.getLogger(logger_name or f"{__name__}.SecurityLogger")
        self._event_counter = 0
        
        # Ensure critical security events are always logged
        if self.logger.level > logging.WARNING:
            self.logger.setLevel(logging.WARNING)
    
    def log_security_event(
        self,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
        operation: Optional[str] = None,
        user_input: Optional[str] = None
    ) -> str:
        """
        Log a security event with full context.
        
        Args:
            event_type: Type of security event
            severity: Severity level
            message: Human-readable message
            context: Additional context information
            exception: Associated exception if any
            operation: Operation being performed when event occurred
            user_input: User input that triggered the event (sanitized)
            
        Returns:
            Event ID for correlation
        """
        self._event_counter += 1
        event_id = f"SEC-{int(time.time())}-{self._event_counter:04d}"
        
        # Build security event record
        security_event = {
            "event_id": event_id,
            "timestamp": time.time(),
            "event_type": event_type.value,
            "severity": severity.value,
            "message": message,
            "operation": operation,
            "context": context or {},
            "exception_type": type(exception).__name__ if exception else None,
            "exception_message": str(exception) if exception else None,
            "user_input_length": len(user_input) if user_input else 0,
            "user_input_type": type(user_input).__name__ if user_input else None
        }
        
        # Add security context from exception if available
        if isinstance(exception, SecurityError) and hasattr(exception, 'security_context'):
            security_event["security_context"] = exception.security_context
        
        # Sanitize user input for logging (don't log actual malicious content)
        if user_input and len(user_input) > 100:
            security_event["user_input_preview"] = user_input[:100] + "...[TRUNCATED]"
        elif user_input:
            security_event["user_input_preview"] = user_input
        
        # Log with appropriate level based on severity
        log_message = f"SECURITY EVENT [{event_id}] {severity.value.upper()}: {message}"
        
        if severity == SecurityEventSeverity.CRITICAL:
            self.logger.critical(f"{log_message}\nDetails: {json.dumps(security_event, indent=2)}")
        elif severity == SecurityEventSeverity.HIGH:
            self.logger.error(f"{log_message}\nDetails: {json.dumps(security_event, indent=2)}")
        elif severity == SecurityEventSeverity.MEDIUM:
            self.logger.warning(f"{log_message}\nDetails: {json.dumps(security_event, indent=2)}")
        else:
            self.logger.info(f"{log_message}\nDetails: {json.dumps(security_event, indent=2)}")
        
        return event_id
    
    def log_validation_failure(
        self,
        field: str,
        attempted_value: Any,
        message: str,
        operation: Optional[str] = None,
        severity: SecurityEventSeverity = SecurityEventSeverity.HIGH
    ) -> str:
        """Log input validation failure."""
        return self.log_security_event(
            event_type=SecurityEventType.VALIDATION_FAILURE,
            severity=severity,
            message=f"Validation failure for field '{field}': {message}",
            context={
                "field": field,
                "attempted_value_type": type(attempted_value).__name__,
                "attempted_value_length": len(str(attempted_value)) if attempted_value else 0,
                "validation_rule_violated": message
            },
            operation=operation,
            user_input=str(attempted_value) if attempted_value else None
        )
    
    def log_injection_attempt(
        self,
        injection_type: str,
        field: str,
        attempted_payload: str,
        operation: Optional[str] = None
    ) -> str:
        """Log suspected injection attempt."""
        return self.log_security_event(
            event_type=SecurityEventType.INJECTION_ATTEMPT,
            severity=SecurityEventSeverity.CRITICAL,
            message=f"Suspected {injection_type} injection attempt in field '{field}'",
            context={
                "injection_type": injection_type,
                "field": field,
                "payload_length": len(attempted_payload),
                "detection_rules": f"{injection_type} pattern detection"
            },
            operation=operation,
            user_input=attempted_payload
        )
    
    def log_authentication_failure(
        self,
        auth_method: str,
        reason: str,
        user_identifier: Optional[str] = None,
        operation: Optional[str] = None
    ) -> str:
        """Log authentication failure."""
        return self.log_security_event(
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            severity=SecurityEventSeverity.HIGH,
            message=f"Authentication failure using {auth_method}: {reason}",
            context={
                "auth_method": auth_method,
                "failure_reason": reason,
                "user_identifier": user_identifier,
                "timestamp": time.time()
            },
            operation=operation
        )
    
    def log_protocol_violation(
        self,
        protocol: str,
        violation_type: str,
        message: str,
        message_type: Optional[str] = None,
        operation: Optional[str] = None
    ) -> str:
        """Log protocol violation."""
        return self.log_security_event(
            event_type=SecurityEventType.PROTOCOL_VIOLATION,
            severity=SecurityEventSeverity.HIGH,
            message=f"Protocol violation in {protocol}: {message}",
            context={
                "protocol": protocol,
                "violation_type": violation_type,
                "message_type": message_type,
                "details": message
            },
            operation=operation
        )
    
    def log_oversized_input(
        self,
        field: str,
        actual_size: int,
        max_allowed_size: int,
        operation: Optional[str] = None
    ) -> str:
        """Log oversized input attempt."""
        return self.log_security_event(
            event_type=SecurityEventType.OVERSIZED_INPUT,
            severity=SecurityEventSeverity.MEDIUM,
            message=f"Oversized input in field '{field}': {actual_size} bytes (max: {max_allowed_size})",
            context={
                "field": field,
                "actual_size": actual_size,
                "max_allowed_size": max_allowed_size,
                "size_ratio": actual_size / max_allowed_size if max_allowed_size > 0 else float('inf')
            },
            operation=operation
        )
    
    def log_connection_violation(
        self,
        violation_type: str,
        message: str,
        connection_info: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None
    ) -> str:
        """Log connection-level security violation."""
        return self.log_security_event(
            event_type=SecurityEventType.CONNECTION_VIOLATION,
            severity=SecurityEventSeverity.HIGH,
            message=f"Connection violation ({violation_type}): {message}",
            context={
                "violation_type": violation_type,
                "connection_info": connection_info or {},
                "details": message
            },
            operation=operation
        )


# Global security logger instance
_global_security_logger = None


def get_security_logger() -> SecurityLogger:
    """Get the global security logger instance."""
    global _global_security_logger
    if _global_security_logger is None:
        _global_security_logger = SecurityLogger("spacetimedb.security")
    return _global_security_logger


def configure_security_logging(
    level: Union[int, str] = logging.WARNING,
    format_string: Optional[str] = None,
    handler: Optional[logging.Handler] = None
) -> None:
    """
    Configure security logging with custom settings.
    
    Args:
        level: Logging level
        format_string: Custom format string
        handler: Custom logging handler
    """
    security_logger = get_security_logger()
    
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    
    security_logger.logger.setLevel(level)
    
    if handler:
        security_logger.logger.addHandler(handler)
    
    if format_string:
        formatter = logging.Formatter(format_string)
        for handler in security_logger.logger.handlers:
            handler.setFormatter(formatter)


# Convenience functions for common security events
def log_security_exception(exception: SecurityError, operation: Optional[str] = None) -> str:
    """Log a security exception with appropriate context."""
    security_logger = get_security_logger()
    
    if isinstance(exception, ValidationSecurityError):
        return security_logger.log_validation_failure(
            field=getattr(exception, 'field', 'unknown'),
            attempted_value=getattr(exception, 'attempted_value', None),
            message=str(exception),
            operation=operation
        )
    elif isinstance(exception, AuthenticationSecurityError):
        return security_logger.log_authentication_failure(
            auth_method=getattr(exception, 'auth_method', 'unknown'),
            reason=str(exception),
            operation=operation
        )
    elif isinstance(exception, ProtocolSecurityError):
        return security_logger.log_protocol_violation(
            protocol=getattr(exception, 'protocol', 'unknown'),
            violation_type="protocol_security_error",
            message=str(exception),
            message_type=getattr(exception, 'message_type', None),
            operation=operation
        )
    elif isinstance(exception, ConnectionSecurityError):
        return security_logger.log_connection_violation(
            violation_type="connection_security_error",
            message=str(exception),
            connection_info=getattr(exception, 'connection_info', None),
            operation=operation
        )
    else:
        return security_logger.log_security_event(
            event_type=SecurityEventType.VALIDATION_FAILURE,  # Default type
            severity=SecurityEventSeverity.HIGH,
            message=str(exception),
            exception=exception,
            operation=operation
        )


__all__ = [
    'SecurityLogger',
    'SecurityEventType',
    'SecurityEventSeverity',
    'get_security_logger',
    'configure_security_logging',
    'log_security_exception'
]