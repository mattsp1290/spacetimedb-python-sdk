"""
Security Logger for Authentication Events

This module provides secure logging capabilities for authentication-related events
while ensuring that sensitive information is never exposed in log files.

Key Security Features:
- No credential or token data in logs
- Hashed identifiers for privacy
- Structured logging for SIEM integration
- Rate limiting event detection
- Timing attack monitoring
- Compliance-ready audit trails

IMPORTANT: This logger is designed to capture security events without exposing
any personally identifiable information or authentication secrets.
"""

import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timezone
import threading
from collections import defaultdict, deque


class SecurityEventType(Enum):
    """Types of security events to log."""
    AUTH_SUCCESS = "authentication_success"
    AUTH_FAILURE = "authentication_failure"
    AUTH_RATE_LIMITED = "authentication_rate_limited"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_EXPIRED = "token_expired"
    CREDENTIAL_STORE = "credential_store"
    CREDENTIAL_CLEAR = "credential_clear"
    TIMING_ANOMALY = "timing_anomaly"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SECURITY_VIOLATION = "security_violation"


class SecurityLevel(Enum):
    """Security event severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class SecurityEvent:
    """Structured security event for logging."""
    event_type: SecurityEventType
    level: SecurityLevel
    timestamp: float
    
    # Context information (never contains sensitive data)
    host: Optional[str] = None
    database: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address_hash: Optional[str] = None  # Hashed IP for privacy
    session_id_hash: Optional[str] = None  # Hashed session ID
    
    # Timing and performance metrics
    duration_ms: Optional[float] = None
    timing_variance_ms: Optional[float] = None
    
    # Rate limiting and abuse detection
    attempt_count: Optional[int] = None
    rate_limit_window: Optional[float] = None
    
    # Additional metadata (no sensitive data)
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Ensure timestamp is set
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string for structured logging."""
        return json.dumps(self.to_dict(), default=str)


class SecurityLogger:
    """
    Secure authentication event logger.
    
    This logger captures security-relevant events while ensuring that:
    - No credentials, tokens, or sensitive data are logged
    - User identifiers are hashed for privacy
    - Events are structured for automated analysis
    - Performance metrics are captured for timing attack detection
    """
    
    def __init__(self, logger_name: str = "spacetimedb.security"):
        """
        Initialize security logger.
        
        Args:
            logger_name: Name for the underlying logger
        """
        self.logger = logging.getLogger(logger_name)
        self._lock = threading.RLock()
        
        # Metrics for anomaly detection
        self._timing_history: deque = deque(maxlen=1000)
        self._failure_counts: defaultdict = defaultdict(lambda: deque(maxlen=100))
        self._rate_limit_events: defaultdict = defaultdict(int)
        
        # Security thresholds
        self.timing_anomaly_threshold_ms = 5.0
        self.failure_rate_threshold = 10  # failures per minute
        self.timing_variance_threshold = 2.0  # ms
    
    def log_authentication_success(
        self,
        host: Optional[str] = None,
        database: Optional[str] = None,
        user_identifier: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log successful authentication event.
        
        Args:
            host: Server host (logged as-is, not sensitive)
            database: Database name (logged as-is, not sensitive)
            user_identifier: User identifier (will be hashed for privacy)
            duration_ms: Authentication duration in milliseconds
            metadata: Additional non-sensitive metadata
        """
        event = SecurityEvent(
            event_type=SecurityEventType.AUTH_SUCCESS,
            level=SecurityLevel.INFO,
            timestamp=time.time(),
            host=host,
            database=database,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )
        
        # Add hashed user identifier if provided
        if user_identifier:
            event.session_id_hash = self._hash_identifier(user_identifier)
        
        # Track timing for anomaly detection
        if duration_ms is not None:
            self._track_timing(duration_ms)
        
        self._log_event(event)
    
    def log_authentication_failure(
        self,
        host: Optional[str] = None,
        database: Optional[str] = None,
        user_identifier: Optional[str] = None,
        duration_ms: Optional[float] = None,
        failure_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log failed authentication event.
        
        Args:
            host: Server host
            database: Database name
            user_identifier: User identifier (will be hashed)
            duration_ms: Authentication duration
            failure_reason: Non-sensitive reason for failure
            metadata: Additional non-sensitive metadata
        """
        event = SecurityEvent(
            event_type=SecurityEventType.AUTH_FAILURE,
            level=SecurityLevel.WARNING,
            timestamp=time.time(),
            host=host,
            database=database,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )
        
        # Add hashed user identifier and failure reason
        if user_identifier:
            event.session_id_hash = self._hash_identifier(user_identifier)
            # Track failure for rate analysis
            self._track_failure(user_identifier)
        
        if failure_reason:
            event.metadata["failure_reason"] = failure_reason
        
        # Track timing for anomaly detection
        if duration_ms is not None:
            self._track_timing(duration_ms)
        
        self._log_event(event)
    
    def log_rate_limiting_event(
        self,
        user_identifier: str,
        attempt_count: int,
        rate_limit_window: float,
        host: Optional[str] = None,
        database: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log rate limiting event.
        
        Args:
            user_identifier: User identifier (will be hashed)
            attempt_count: Number of attempts in window
            rate_limit_window: Rate limit window in seconds
            host: Server host
            database: Database name
            metadata: Additional metadata
        """
        event = SecurityEvent(
            event_type=SecurityEventType.AUTH_RATE_LIMITED,
            level=SecurityLevel.WARNING,
            timestamp=time.time(),
            host=host,
            database=database,
            attempt_count=attempt_count,
            rate_limit_window=rate_limit_window,
            session_id_hash=self._hash_identifier(user_identifier),
            metadata=metadata or {}
        )
        
        # Track rate limiting for pattern analysis
        self._rate_limit_events[self._hash_identifier(user_identifier)] += 1
        
        self._log_event(event)
    
    def log_timing_anomaly(
        self,
        measured_time_ms: float,
        expected_time_ms: float,
        variance_ms: float,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log timing anomaly that could indicate timing attack attempts.
        
        Args:
            measured_time_ms: Actual measured time
            expected_time_ms: Expected time based on baseline
            variance_ms: Variance from expected time
            operation: Type of operation being timed
            metadata: Additional metadata
        """
        event = SecurityEvent(
            event_type=SecurityEventType.TIMING_ANOMALY,
            level=SecurityLevel.CRITICAL if variance_ms > self.timing_anomaly_threshold_ms else SecurityLevel.WARNING,
            timestamp=time.time(),
            duration_ms=measured_time_ms,
            timing_variance_ms=variance_ms,
            metadata=metadata or {}
        )
        
        event.metadata.update({
            "operation": operation,
            "expected_time_ms": expected_time_ms,
            "variance_threshold_ms": self.timing_anomaly_threshold_ms
        })
        
        self._log_event(event)
    
    def log_security_violation(
        self,
        violation_type: str,
        description: str,
        severity: SecurityLevel = SecurityLevel.CRITICAL,
        host: Optional[str] = None,
        database: Optional[str] = None,
        user_identifier: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log security violation event.
        
        Args:
            violation_type: Type of security violation
            description: Non-sensitive description
            severity: Severity level
            host: Server host
            database: Database name
            user_identifier: User identifier (will be hashed)
            metadata: Additional metadata
        """
        event = SecurityEvent(
            event_type=SecurityEventType.SECURITY_VIOLATION,
            level=severity,
            timestamp=time.time(),
            host=host,
            database=database,
            metadata=metadata or {}
        )
        
        if user_identifier:
            event.session_id_hash = self._hash_identifier(user_identifier)
        
        event.metadata.update({
            "violation_type": violation_type,
            "description": description
        })
        
        self._log_event(event)
    
    def log_token_event(
        self,
        event_type: SecurityEventType,
        host: Optional[str] = None,
        database: Optional[str] = None,
        user_identifier: Optional[str] = None,
        token_hint: Optional[str] = None,  # Only first/last few chars, never full token
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log token-related security event.
        
        Args:
            event_type: Type of token event
            host: Server host
            database: Database name
            user_identifier: User identifier (will be hashed)
            token_hint: Safe token hint (first/last chars only)
            metadata: Additional metadata
        """
        event = SecurityEvent(
            event_type=event_type,
            level=SecurityLevel.INFO,
            timestamp=time.time(),
            host=host,
            database=database,
            metadata=metadata or {}
        )
        
        if user_identifier:
            event.session_id_hash = self._hash_identifier(user_identifier)
        
        if token_hint:
            # Ensure token hint is safe (max 8 chars, no middle content)
            safe_hint = token_hint[:4] + "..." + token_hint[-4:] if len(token_hint) > 8 else "****"
            event.metadata["token_hint"] = safe_hint
        
        self._log_event(event)
    
    def _log_event(self, event: SecurityEvent) -> None:
        """
        Log security event with appropriate level.
        
        Args:
            event: Security event to log
        """
        with self._lock:
            # Convert event to structured format
            log_data = event.to_dict()
            
            # Log at appropriate level
            if event.level == SecurityLevel.INFO:
                self.logger.info(f"Security Event: {event.event_type.value}", extra=log_data)
            elif event.level == SecurityLevel.WARNING:
                self.logger.warning(f"Security Event: {event.event_type.value}", extra=log_data)
            elif event.level == SecurityLevel.CRITICAL:
                self.logger.critical(f"Security Event: {event.event_type.value}", extra=log_data)
            elif event.level == SecurityLevel.EMERGENCY:
                self.logger.error(f"Security Emergency: {event.event_type.value}", extra=log_data)
    
    def _hash_identifier(self, identifier: str) -> str:
        """
        Create privacy-preserving hash of identifier.
        
        Args:
            identifier: User identifier to hash
            
        Returns:
            SHA-256 hash of identifier (first 16 chars for readability)
        """
        if not identifier:
            return "anonymous"
        
        # Add salt to prevent rainbow table attacks
        salt = "spacetimedb_security_logger_v1"
        salted = f"{salt}:{identifier}"
        
        hash_obj = hashlib.sha256(salted.encode('utf-8'))
        return hash_obj.hexdigest()[:16]  # First 16 chars for readability
    
    def _track_timing(self, duration_ms: float) -> None:
        """Track timing for anomaly detection."""
        with self._lock:
            self._timing_history.append(duration_ms)
            
            # Check for timing anomalies if we have enough data
            if len(self._timing_history) >= 10:
                recent_times = list(self._timing_history)[-10:]
                avg_time = sum(recent_times) / len(recent_times)
                variance = abs(duration_ms - avg_time)
                
                if variance > self.timing_variance_threshold:
                    self.log_timing_anomaly(
                        measured_time_ms=duration_ms,
                        expected_time_ms=avg_time,
                        variance_ms=variance,
                        operation="authentication_verification"
                    )
    
    def _track_failure(self, user_identifier: str) -> None:
        """Track authentication failures for pattern analysis."""
        with self._lock:
            user_hash = self._hash_identifier(user_identifier)
            now = time.time()
            
            # Add failure timestamp
            self._failure_counts[user_hash].append(now)
            
            # Check failure rate (failures per minute)
            minute_ago = now - 60
            recent_failures = [t for t in self._failure_counts[user_hash] if t > minute_ago]
            
            if len(recent_failures) > self.failure_rate_threshold:
                self.log_security_violation(
                    violation_type="excessive_auth_failures",
                    description=f"User exceeded failure rate threshold: {len(recent_failures)} failures in 60 seconds",
                    severity=SecurityLevel.WARNING,
                    user_identifier=user_identifier,
                    metadata={
                        "failure_count": len(recent_failures),
                        "threshold": self.failure_rate_threshold,
                        "window_seconds": 60
                    }
                )
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """
        Get security metrics for monitoring and alerting.
        
        Returns:
            Dictionary with current security metrics
        """
        with self._lock:
            return {
                "timing_samples": len(self._timing_history),
                "average_timing_ms": sum(self._timing_history) / len(self._timing_history) if self._timing_history else 0,
                "tracked_users": len(self._failure_counts),
                "rate_limited_users": len(self._rate_limit_events),
                "timing_anomaly_threshold_ms": self.timing_anomaly_threshold_ms,
                "failure_rate_threshold": self.failure_rate_threshold,
                "total_rate_limit_events": sum(self._rate_limit_events.values())
            }
    
    def configure_thresholds(
        self,
        timing_anomaly_threshold_ms: Optional[float] = None,
        failure_rate_threshold: Optional[int] = None,
        timing_variance_threshold: Optional[float] = None
    ) -> None:
        """
        Configure security detection thresholds.
        
        Args:
            timing_anomaly_threshold_ms: Threshold for timing anomaly detection
            failure_rate_threshold: Max failures per minute before alerting
            timing_variance_threshold: Timing variance threshold in ms
        """
        if timing_anomaly_threshold_ms is not None:
            self.timing_anomaly_threshold_ms = timing_anomaly_threshold_ms
        
        if failure_rate_threshold is not None:
            self.failure_rate_threshold = failure_rate_threshold
        
        if timing_variance_threshold is not None:
            self.timing_variance_threshold = timing_variance_threshold


# Global security logger instance
_global_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """Get or create global security logger instance."""
    global _global_security_logger
    
    if _global_security_logger is None:
        _global_security_logger = SecurityLogger()
    
    return _global_security_logger


def configure_security_logging(
    logger_name: Optional[str] = None,
    log_level: int = logging.INFO,
    log_format: Optional[str] = None
) -> SecurityLogger:
    """
    Configure security logging with custom settings.
    
    Args:
        logger_name: Custom logger name
        log_level: Logging level
        log_format: Custom log format
        
    Returns:
        Configured SecurityLogger instance
    """
    logger = SecurityLogger(logger_name or "spacetimedb.security")
    
    # Configure the underlying Python logger
    if not logger.logger.handlers:
        handler = logging.StreamHandler()
        
        if log_format:
            formatter = logging.Formatter(log_format)
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        handler.setFormatter(formatter)
        logger.logger.addHandler(handler)
        logger.logger.setLevel(log_level)
    
    return logger


# Convenience functions for common security events
def log_auth_success(user_id: str, host: str = None, database: str = None, duration_ms: float = None) -> None:
    """Log authentication success event."""
    get_security_logger().log_authentication_success(
        host=host,
        database=database,
        user_identifier=user_id,
        duration_ms=duration_ms
    )


def log_auth_failure(user_id: str, reason: str = None, host: str = None, database: str = None) -> None:
    """Log authentication failure event."""
    get_security_logger().log_authentication_failure(
        host=host,
        database=database,
        user_identifier=user_id,
        failure_reason=reason
    )


def log_rate_limit(user_id: str, attempts: int, window: float = 60.0) -> None:
    """Log rate limiting event."""
    get_security_logger().log_rate_limiting_event(
        user_identifier=user_id,
        attempt_count=attempts,
        rate_limit_window=window
    )


def log_security_event(event_type: str, description: str, severity: str = "warning") -> None:
    """Log general security event."""
    severity_map = {
        "info": SecurityLevel.INFO,
        "warning": SecurityLevel.WARNING,
        "critical": SecurityLevel.CRITICAL,
        "emergency": SecurityLevel.EMERGENCY
    }
    
    get_security_logger().log_security_violation(
        violation_type=event_type,
        description=description,
        severity=severity_map.get(severity, SecurityLevel.WARNING)
    )