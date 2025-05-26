"""
Security Audit and Compliance for SpacetimeDB

Provides comprehensive security auditing including:
- Security event logging
- Failed authentication tracking
- Access pattern analysis
- Anomaly detection hooks
- Compliance reporting (SOC2, HIPAA, etc.)
- Security metrics collection
"""

import json
import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import hmac
import uuid
from collections import defaultdict, deque
import re


class SecurityEventType(Enum):
    """Types of security events."""
    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_REVOKED = "auth_revoked"
    TOKEN_CREATED = "token_created"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_EXPIRED = "token_expired"
    MFA_CHALLENGE = "mfa_challenge"
    MFA_SUCCESS = "mfa_success"
    MFA_FAILURE = "mfa_failure"
    
    # Access events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHECK = "permission_check"
    RESOURCE_ACCESS = "resource_access"
    
    # Connection events
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_FAILED = "connection_failed"
    TLS_HANDSHAKE = "tls_handshake"
    CERTIFICATE_VALIDATION = "certificate_validation"
    
    # Data events
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # Security events
    SECURITY_VIOLATION = "security_violation"
    ANOMALY_DETECTED = "anomaly_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # Administrative events
    CONFIG_CHANGED = "config_changed"
    USER_CREATED = "user_created"
    USER_MODIFIED = "user_modified"
    USER_DELETED = "user_deleted"
    ROLE_ASSIGNED = "role_assigned"
    PERMISSION_GRANTED = "permission_granted"


class ComplianceStandard(Enum):
    """Supported compliance standards."""
    SOC2 = "soc2"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    NIST = "nist"
    CUSTOM = "custom"


class SeverityLevel(Enum):
    """Security event severity levels."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


@dataclass
class SecurityEvent:
    """A security event record."""
    event_id: str
    timestamp: datetime
    event_type: SecurityEventType
    severity: SeverityLevel
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "source_ip": self.source_ip,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "details": self.details,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecurityEvent':
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=SecurityEventType(data["event_type"]),
            severity=SeverityLevel(data["severity"]),
            source_ip=data.get("source_ip"),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            resource=data.get("resource"),
            action=data.get("action"),
            result=data.get("result"),
            details=data.get("details", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AuditConfig:
    """Configuration for security auditing."""
    enabled: bool = True
    
    # Logging settings
    log_file: Optional[Path] = None
    log_rotation: bool = True
    max_log_size_mb: int = 100
    max_log_files: int = 10
    
    # Event filtering
    min_severity: SeverityLevel = SeverityLevel.INFO
    event_types: Optional[Set[SecurityEventType]] = None  # None = all events
    
    # Storage settings
    retention_days: int = 90
    archive_old_events: bool = True
    compression: bool = True
    
    # Real-time monitoring
    enable_alerts: bool = True
    alert_threshold: Dict[SecurityEventType, int] = field(default_factory=dict)
    alert_window_minutes: int = 5
    
    # Compliance settings
    compliance_standards: Set[ComplianceStandard] = field(default_factory=set)
    pii_redaction: bool = True
    encryption_at_rest: bool = True
    
    # Performance settings
    buffer_size: int = 1000
    flush_interval_seconds: int = 5
    async_logging: bool = True


class SecurityAuditor:
    """
    Main security auditing class.
    
    Features:
    - Comprehensive event logging
    - Real-time anomaly detection
    - Compliance reporting
    - Security metrics
    """
    
    def __init__(self, config: Optional[AuditConfig] = None):
        self.config = config or AuditConfig()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        # Event storage
        self._events: deque = deque(maxlen=100000)  # In-memory buffer
        self._event_buffer: List[SecurityEvent] = []
        
        # Metrics
        self._event_counts: Dict[SecurityEventType, int] = defaultdict(int)
        self._failed_auth_attempts: Dict[str, List[datetime]] = defaultdict(list)
        self._access_patterns: Dict[str, Dict[str, Any]] = {}
        
        # Anomaly detection
        self._baseline_metrics: Dict[str, Any] = {}
        self._anomaly_callbacks: List[Callable] = []
        
        # Alert tracking
        self._alert_windows: Dict[SecurityEventType, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        
        # Background threads
        self._flush_thread: Optional[threading.Thread] = None
        self._analysis_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Initialize
        self._initialize_logging()
        if self.config.enabled:
            self._start_background_threads()
    
    def _initialize_logging(self) -> None:
        """Initialize audit logging."""
        if self.config.log_file:
            # Set up file logging with rotation
            import logging.handlers
            
            handler = logging.handlers.RotatingFileHandler(
                self.config.log_file,
                maxBytes=self.config.max_log_size_mb * 1024 * 1024,
                backupCount=self.config.max_log_files
            )
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            
            audit_logger = logging.getLogger("security_audit")
            audit_logger.addHandler(handler)
            audit_logger.setLevel(logging.INFO)
            
            self._audit_logger = audit_logger
        else:
            self._audit_logger = self.logger
    
    def _start_background_threads(self) -> None:
        """Start background processing threads."""
        self._running = True
        
        # Flush thread
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="SecurityAuditor-Flush"
        )
        self._flush_thread.start()
        
        # Analysis thread
        self._analysis_thread = threading.Thread(
            target=self._analysis_loop,
            daemon=True,
            name="SecurityAuditor-Analysis"
        )
        self._analysis_thread.start()
    
    def log_event(
        self,
        event_type: SecurityEventType,
        severity: SeverityLevel = SeverityLevel.INFO,
        user_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> SecurityEvent:
        """Log a security event."""
        if not self.config.enabled:
            return None
        
        # Check if we should log this event
        if self.config.event_types and event_type not in self.config.event_types:
            return None
        
        if severity.value < self.config.min_severity.value:
            return None
        
        # Create event
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            source_ip=source_ip or self._get_source_ip(),
            session_id=kwargs.get("session_id"),
            resource=resource,
            action=action,
            result=result,
            details=details or {},
            metadata=kwargs
        )
        
        # Redact PII if configured
        if self.config.pii_redaction:
            event = self._redact_pii(event)
        
        # Add to buffer
        with self._lock:
            self._event_buffer.append(event)
            self._event_counts[event_type] += 1
            
            # Check for immediate alerts
            self._check_alerts(event)
            
            # Track failed auth attempts
            if event_type == SecurityEventType.AUTH_FAILURE and user_id:
                self._failed_auth_attempts[user_id].append(event.timestamp)
        
        # Log immediately if critical
        if severity == SeverityLevel.CRITICAL:
            self._log_event(event)
        
        return event
    
    def _redact_pii(self, event: SecurityEvent) -> SecurityEvent:
        """Redact PII from event."""
        # Patterns for common PII
        patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        }
        
        # Redact from details
        for key, value in event.details.items():
            if isinstance(value, str):
                for pii_type, pattern in patterns.items():
                    value = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", value)
                event.details[key] = value
        
        return event
    
    def _get_source_ip(self) -> Optional[str]:
        """Get source IP address."""
        # This is a placeholder - in production, get from request context
        return "127.0.0.1"
    
    def _check_alerts(self, event: SecurityEvent) -> None:
        """Check if event triggers alerts."""
        if not self.config.enable_alerts:
            return
        
        # Add to alert window
        self._alert_windows[event.event_type].append(event.timestamp)
        
        # Check threshold
        threshold = self.config.alert_threshold.get(event.event_type)
        if threshold:
            window_start = datetime.now(timezone.utc) - timedelta(
                minutes=self.config.alert_window_minutes
            )
            
            recent_count = sum(
                1 for ts in self._alert_windows[event.event_type]
                if ts > window_start
            )
            
            if recent_count >= threshold:
                self._trigger_alert(event, recent_count, threshold)
    
    def _trigger_alert(
        self,
        event: SecurityEvent,
        count: int,
        threshold: int
    ) -> None:
        """Trigger security alert."""
        alert_event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            event_type=SecurityEventType.SECURITY_VIOLATION,
            severity=SeverityLevel.WARNING,
            details={
                "trigger_event": event.event_id,
                "event_type": event.event_type.value,
                "count": count,
                "threshold": threshold,
                "window_minutes": self.config.alert_window_minutes,
            }
        )
        
        self._log_event(alert_event)
        
        # Call alert callbacks
        for callback in self._anomaly_callbacks:
            try:
                callback(alert_event)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")
    
    def _log_event(self, event: SecurityEvent) -> None:
        """Log event to persistent storage."""
        # Log to file
        self._audit_logger.info(json.dumps(event.to_dict()))
        
        # Add to in-memory storage
        self._events.append(event)
    
    def _flush_loop(self) -> None:
        """Background loop for flushing events."""
        while self._running:
            try:
                time.sleep(self.config.flush_interval_seconds)
                self._flush_events()
            except Exception as e:
                self.logger.error(f"Flush loop error: {e}")
    
    def _flush_events(self) -> None:
        """Flush buffered events to storage."""
        with self._lock:
            if not self._event_buffer:
                return
            
            events_to_flush = self._event_buffer[:]
            self._event_buffer.clear()
        
        # Log all events
        for event in events_to_flush:
            self._log_event(event)
    
    def _analysis_loop(self) -> None:
        """Background loop for security analysis."""
        while self._running:
            try:
                time.sleep(60)  # Run analysis every minute
                self._perform_analysis()
            except Exception as e:
                self.logger.error(f"Analysis loop error: {e}")
    
    def _perform_analysis(self) -> None:
        """Perform security analysis."""
        with self._lock:
            # Analyze failed authentication attempts
            self._analyze_failed_auth()
            
            # Analyze access patterns
            self._analyze_access_patterns()
            
            # Check for anomalies
            self._detect_anomalies()
    
    def _analyze_failed_auth(self) -> None:
        """Analyze failed authentication attempts."""
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=15)
        
        for user_id, attempts in list(self._failed_auth_attempts.items()):
            # Remove old attempts
            recent_attempts = [
                ts for ts in attempts
                if now - ts < window
            ]
            
            if len(recent_attempts) >= 5:
                # Suspicious activity detected
                self.log_event(
                    SecurityEventType.SUSPICIOUS_ACTIVITY,
                    severity=SeverityLevel.WARNING,
                    user_id=user_id,
                    details={
                        "reason": "Multiple failed authentication attempts",
                        "count": len(recent_attempts),
                        "window_minutes": 15,
                    }
                )
            
            # Update attempts list
            if recent_attempts:
                self._failed_auth_attempts[user_id] = recent_attempts
            else:
                del self._failed_auth_attempts[user_id]
    
    def _analyze_access_patterns(self) -> None:
        """Analyze user access patterns."""
        # This is a simplified implementation
        # In production, use ML models for pattern analysis
        pass
    
    def _detect_anomalies(self) -> None:
        """Detect security anomalies."""
        # Calculate current metrics
        current_metrics = self._calculate_metrics()
        
        # Compare with baseline
        if self._baseline_metrics:
            for metric, value in current_metrics.items():
                baseline = self._baseline_metrics.get(metric, 0)
                if baseline > 0:
                    deviation = abs(value - baseline) / baseline
                    
                    if deviation > 0.5:  # 50% deviation
                        self.log_event(
                            SecurityEventType.ANOMALY_DETECTED,
                            severity=SeverityLevel.WARNING,
                            details={
                                "metric": metric,
                                "current_value": value,
                                "baseline_value": baseline,
                                "deviation_percent": deviation * 100,
                            }
                        )
        
        # Update baseline (rolling average)
        for metric, value in current_metrics.items():
            if metric in self._baseline_metrics:
                # Exponential moving average
                self._baseline_metrics[metric] = (
                    0.9 * self._baseline_metrics[metric] + 0.1 * value
                )
            else:
                self._baseline_metrics[metric] = value
    
    def _calculate_metrics(self) -> Dict[str, float]:
        """Calculate current security metrics."""
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        recent_events = [
            e for e in self._events
            if e.timestamp > hour_ago
        ]
        
        if not recent_events:
            return {}
        
        metrics = {
            "events_per_hour": len(recent_events),
            "auth_failure_rate": sum(
                1 for e in recent_events
                if e.event_type == SecurityEventType.AUTH_FAILURE
            ) / len(recent_events),
            "unique_users": len(set(e.user_id for e in recent_events if e.user_id)),
            "unique_ips": len(set(e.source_ip for e in recent_events if e.source_ip)),
        }
        
        # Event type distribution
        for event_type in SecurityEventType:
            count = sum(1 for e in recent_events if e.event_type == event_type)
            if count > 0:
                metrics[f"event_type_{event_type.value}"] = count
        
        return metrics
    
    def register_anomaly_callback(self, callback: Callable[[SecurityEvent], None]) -> None:
        """Register callback for anomaly detection."""
        self._anomaly_callbacks.append(callback)
    
    def get_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[SecurityEventType]] = None,
        user_id: Optional[str] = None,
        severity: Optional[SeverityLevel] = None,
        limit: int = 1000
    ) -> List[SecurityEvent]:
        """Query security events."""
        with self._lock:
            events = list(self._events)
        
        # Apply filters
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if severity:
            events = [e for e in events if e.severity.value >= severity.value]
        
        # Sort by timestamp descending and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    def get_user_activity(
        self,
        user_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get user activity summary."""
        start_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        user_events = self.get_events(
            start_time=start_time,
            user_id=user_id
        )
        
        if not user_events:
            return {
                "user_id": user_id,
                "period_days": days,
                "total_events": 0,
            }
        
        # Calculate summary
        auth_events = [e for e in user_events if e.event_type in [
            SecurityEventType.AUTH_SUCCESS,
            SecurityEventType.AUTH_FAILURE
        ]]
        
        failed_auth = [
            e for e in auth_events
            if e.event_type == SecurityEventType.AUTH_FAILURE
        ]
        
        return {
            "user_id": user_id,
            "period_days": days,
            "total_events": len(user_events),
            "auth_attempts": len(auth_events),
            "failed_auth_attempts": len(failed_auth),
            "auth_success_rate": (
                (len(auth_events) - len(failed_auth)) / len(auth_events) * 100
                if auth_events else 0
            ),
            "unique_ips": len(set(e.source_ip for e in user_events if e.source_ip)),
            "last_activity": max(e.timestamp for e in user_events).isoformat(),
            "event_types": dict(defaultdict(
                int,
                ((e.event_type.value, 1) for e in user_events)
            )),
        }
    
    def generate_compliance_report(
        self,
        standard: ComplianceStandard,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate compliance report."""
        events = self.get_events(
            start_time=start_date,
            end_time=end_date
        )
        
        report = {
            "standard": standard.value,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_events": len(events),
                "unique_users": len(set(e.user_id for e in events if e.user_id)),
                "security_incidents": len([
                    e for e in events
                    if e.severity.value >= SeverityLevel.WARNING.value
                ]),
            },
        }
        
        # Standard-specific sections
        if standard == ComplianceStandard.SOC2:
            report.update(self._generate_soc2_report(events))
        elif standard == ComplianceStandard.HIPAA:
            report.update(self._generate_hipaa_report(events))
        elif standard == ComplianceStandard.GDPR:
            report.update(self._generate_gdpr_report(events))
        elif standard == ComplianceStandard.PCI_DSS:
            report.update(self._generate_pci_dss_report(events))
        
        return report
    
    def _generate_soc2_report(self, events: List[SecurityEvent]) -> Dict[str, Any]:
        """Generate SOC2-specific report sections."""
        return {
            "soc2_controls": {
                "access_control": {
                    "authentication_events": len([
                        e for e in events
                        if e.event_type in [
                            SecurityEventType.AUTH_SUCCESS,
                            SecurityEventType.AUTH_FAILURE
                        ]
                    ]),
                    "access_reviews": len([
                        e for e in events
                        if e.event_type == SecurityEventType.PERMISSION_CHECK
                    ]),
                },
                "data_security": {
                    "encryption_events": len([
                        e for e in events
                        if e.event_type == SecurityEventType.TLS_HANDSHAKE
                    ]),
                    "data_access_events": len([
                        e for e in events
                        if e.event_type in [
                            SecurityEventType.DATA_READ,
                            SecurityEventType.DATA_WRITE
                        ]
                    ]),
                },
                "availability": {
                    "connection_events": len([
                        e for e in events
                        if e.event_type in [
                            SecurityEventType.CONNECTION_ESTABLISHED,
                            SecurityEventType.CONNECTION_FAILED
                        ]
                    ]),
                },
                "change_management": {
                    "config_changes": len([
                        e for e in events
                        if e.event_type == SecurityEventType.CONFIG_CHANGED
                    ]),
                },
            }
        }
    
    def _generate_hipaa_report(self, events: List[SecurityEvent]) -> Dict[str, Any]:
        """Generate HIPAA-specific report sections."""
        return {
            "hipaa_compliance": {
                "access_controls": {
                    "unique_user_auth": len(set(
                        e.user_id for e in events
                        if e.event_type == SecurityEventType.AUTH_SUCCESS and e.user_id
                    )),
                    "access_terminations": len([
                        e for e in events
                        if e.event_type == SecurityEventType.USER_DELETED
                    ]),
                },
                "audit_controls": {
                    "total_audit_events": len(events),
                    "data_access_monitoring": len([
                        e for e in events
                        if e.event_type in [
                            SecurityEventType.DATA_READ,
                            SecurityEventType.DATA_WRITE,
                            SecurityEventType.DATA_DELETE
                        ]
                    ]),
                },
                "transmission_security": {
                    "encrypted_connections": len([
                        e for e in events
                        if e.event_type == SecurityEventType.TLS_HANDSHAKE
                        and e.result == "success"
                    ]),
                },
            }
        }
    
    def _generate_gdpr_report(self, events: List[SecurityEvent]) -> Dict[str, Any]:
        """Generate GDPR-specific report sections."""
        return {
            "gdpr_compliance": {
                "data_access": {
                    "access_requests": len([
                        e for e in events
                        if e.event_type == SecurityEventType.DATA_READ
                        and "personal_data" in e.metadata
                    ]),
                    "data_exports": len([
                        e for e in events
                        if e.event_type == SecurityEventType.DATA_EXPORT
                    ]),
                },
                "data_deletion": {
                    "deletion_requests": len([
                        e for e in events
                        if e.event_type == SecurityEventType.DATA_DELETE
                        and "right_to_erasure" in e.metadata
                    ]),
                },
                "consent_management": {
                    "consent_updates": len([
                        e for e in events
                        if "consent" in e.metadata
                    ]),
                },
            }
        }
    
    def _generate_pci_dss_report(self, events: List[SecurityEvent]) -> Dict[str, Any]:
        """Generate PCI-DSS-specific report sections."""
        return {
            "pci_dss_compliance": {
                "access_control": {
                    "unique_ids": len(set(
                        e.user_id for e in events
                        if e.user_id
                    )),
                    "password_changes": len([
                        e for e in events
                        if "password_change" in e.metadata
                    ]),
                },
                "network_security": {
                    "firewall_events": len([
                        e for e in events
                        if "firewall" in e.metadata
                    ]),
                    "secure_connections": len([
                        e for e in events
                        if e.event_type == SecurityEventType.TLS_HANDSHAKE
                    ]),
                },
                "vulnerability_management": {
                    "security_patches": len([
                        e for e in events
                        if "security_patch" in e.metadata
                    ]),
                },
            }
        }
    
    def export_audit_log(
        self,
        output_path: Path,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> None:
        """Export audit log to file."""
        events = self.get_events(
            start_time=start_date,
            end_time=end_date
        )
        
        if format == "json":
            with open(output_path, 'w') as f:
                json.dump(
                    [e.to_dict() for e in events],
                    f,
                    indent=2
                )
        elif format == "csv":
            import csv
            
            with open(output_path, 'w', newline='') as f:
                if events:
                    writer = csv.DictWriter(f, fieldnames=events[0].to_dict().keys())
                    writer.writeheader()
                    for event in events:
                        writer.writerow(event.to_dict())
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get current security metrics."""
        with self._lock:
            metrics = self._calculate_metrics()
            
            return {
                "current_metrics": metrics,
                "event_counts": dict(self._event_counts),
                "active_alerts": {
                    event_type.value: len([
                        ts for ts in self._alert_windows[event_type]
                        if datetime.now(timezone.utc) - ts < timedelta(
                            minutes=self.config.alert_window_minutes
                        )
                    ])
                    for event_type in SecurityEventType
                },
                "failed_auth_users": len(self._failed_auth_attempts),
                "buffer_size": len(self._event_buffer),
                "total_events": len(self._events),
            }
    
    def shutdown(self) -> None:
        """Shutdown the security auditor."""
        self._running = False
        
        # Flush remaining events
        self._flush_events()
        
        # Wait for threads to complete
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        
        if self._analysis_thread:
            self._analysis_thread.join(timeout=5)
        
        self.logger.info("Security auditor shutdown complete")


# Decorator for security event logging
def security_event(
    event_type: SecurityEventType,
    severity: SeverityLevel = SeverityLevel.INFO,
    include_args: bool = True
):
    """
    Decorator to automatically log security events for methods.
    
    Usage:
        @security_event(SecurityEventType.DATA_READ)
        def read_sensitive_data(self, user_id: str, resource: str):
            # Method implementation
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get auditor from first argument if it has one
            auditor = None
            if args and hasattr(args[0], '_security_auditor'):
                auditor = args[0]._security_auditor
            
            # Prepare event details
            details = {
                "function": func.__name__,
                "module": func.__module__,
            }
            
            if include_args:
                # Sanitize arguments
                details["args"] = str(args[1:])[:100]  # Skip self
                details["kwargs"] = str(kwargs)[:100]
            
            # Extract common parameters
            user_id = kwargs.get('user_id')
            resource = kwargs.get('resource')
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log success
                if auditor:
                    auditor.log_event(
                        event_type=event_type,
                        severity=severity,
                        user_id=user_id,
                        resource=resource,
                        action=func.__name__,
                        result="success",
                        details=details
                    )
                
                return result
                
            except Exception as e:
                # Log failure
                if auditor:
                    details["error"] = str(e)
                    auditor.log_event(
                        event_type=event_type,
                        severity=SeverityLevel.ERROR,
                        user_id=user_id,
                        resource=resource,
                        action=func.__name__,
                        result="failure",
                        details=details
                    )
                raise
        
        return wrapper
    return decorator


# Convenience class for integrating audit with other components
class AuditableMixin:
    """Mixin to add security auditing capabilities to a class."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._security_auditor = kwargs.get('security_auditor')
    
    def set_security_auditor(self, auditor: SecurityAuditor) -> None:
        """Set the security auditor."""
        self._security_auditor = auditor
    
    def audit_event(self, *args, **kwargs) -> Optional[SecurityEvent]:
        """Log an audit event."""
        if self._security_auditor:
            return self._security_auditor.log_event(*args, **kwargs)
        return None
