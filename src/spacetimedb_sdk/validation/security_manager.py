"""
Security Manager for SpacetimeDB SDK

This module provides a centralized security manager that integrates all
validation components to provide comprehensive security for the SDK.
"""

import logging
import threading
from typing import Any, Dict, Optional, List, Callable, Union
from dataclasses import dataclass, field
from .validators import ValidationConfig, ValidationResult, CompositeValidator
from .url_validator import URLValidator
from .sql_validator import SQLValidator
from .data_validator import JSONValidator, DataSizeValidator, MessageValidator


@dataclass
class SecurityConfig:
    """Configuration for security manager."""
    
    # Validation configuration
    validation_config: ValidationConfig = field(default_factory=ValidationConfig)
    
    # Security policies
    strict_mode: bool = False
    log_violations: bool = True
    block_on_validation_failure: bool = True
    
    # Rate limiting
    enable_rate_limiting: bool = False
    max_requests_per_second: int = 100
    max_requests_per_minute: int = 1000
    
    # Security callbacks
    on_validation_failure: Optional[Callable[[str, Any], None]] = None
    on_security_violation: Optional[Callable[[str, str, Any], None]] = None


class SecurityManager:
    """
    Centralized security manager for SpacetimeDB SDK.
    
    This class provides a single point of entry for all security-related
    operations including input validation, sanitization, and security
    policy enforcement.
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        
        # Initialize validators
        self.url_validator = URLValidator(self.config.validation_config)
        self.sql_validator = SQLValidator(self.config.validation_config)
        self.json_validator = JSONValidator(self.config.validation_config)
        self.size_validator = DataSizeValidator(self.config.validation_config)
        self.message_validator = MessageValidator(self.config.validation_config)
        
        # Rate limiting state
        self._request_timestamps: List[float] = []
        
        # Security metrics
        self._security_metrics = {
            'validation_failures': 0,
            'security_violations': 0,
            'blocked_requests': 0,
            'sanitized_inputs': 0,
        }
    
    def validate_url(self, url: str, field: Optional[str] = None) -> ValidationResult:
        """
        Validate URL with security checks.
        
        Args:
            url: URL to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with URL validation
        """
        with self._lock:
            result = self.url_validator.validate(url, field)
            
            if not result.is_valid:
                self._handle_validation_failure('URL', url, result)
            else:
                self._security_metrics['sanitized_inputs'] += 1
            
            return result
    
    def validate_websocket_url(self, url: str, field: Optional[str] = None) -> ValidationResult:
        """
        Validate WebSocket URL with security checks.
        
        Args:
            url: WebSocket URL to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with WebSocket URL validation
        """
        with self._lock:
            result = self.url_validator.validate_websocket_url(url, field)
            
            if not result.is_valid:
                self._handle_validation_failure('WebSocket URL', url, result)
            else:
                self._security_metrics['sanitized_inputs'] += 1
            
            return result
    
    def validate_sql_query(self, query: str, field: Optional[str] = None) -> ValidationResult:
        """
        Validate SQL query with security checks.
        
        Args:
            query: SQL query to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with SQL validation
        """
        with self._lock:
            result = self.sql_validator.validate(query, field)
            
            if not result.is_valid:
                self._handle_validation_failure('SQL Query', query, result)
            else:
                self._security_metrics['sanitized_inputs'] += 1
            
            return result
    
    def validate_json_data(self, data: Any, field: Optional[str] = None) -> ValidationResult:
        """
        Validate JSON data with security checks.
        
        Args:
            data: JSON data to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with JSON validation
        """
        with self._lock:
            result = self.json_validator.validate(data, field)
            
            if not result.is_valid:
                self._handle_validation_failure('JSON Data', data, result)
            else:
                self._security_metrics['sanitized_inputs'] += 1
            
            return result
    
    def validate_message(self, message: Any, field: Optional[str] = None) -> ValidationResult:
        """
        Validate SpacetimeDB message with security checks.
        
        Args:
            message: Message to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with message validation
        """
        with self._lock:
            result = self.message_validator.validate(message, field)
            
            if not result.is_valid:
                self._handle_validation_failure('Message', message, result)
            else:
                self._security_metrics['sanitized_inputs'] += 1
            
            return result
    
    def sanitize_url(self, url: str, field: Optional[str] = None) -> str:
        """
        Sanitize URL, raising exception if invalid.
        
        Args:
            url: URL to sanitize
            field: Optional field name for error reporting
            
        Returns:
            Sanitized URL
            
        Raises:
            ValidationError: If URL is invalid
        """
        return self.url_validator.sanitize(url, field)
    
    def sanitize_sql_query(self, query: str, field: Optional[str] = None) -> str:
        """
        Sanitize SQL query, raising exception if invalid.
        
        Args:
            query: SQL query to sanitize
            field: Optional field name for error reporting
            
        Returns:
            Sanitized SQL query
            
        Raises:
            ValidationError: If query is invalid
        """
        return self.sql_validator.sanitize(query, field)
    
    def sanitize_json_data(self, data: Any, field: Optional[str] = None) -> Any:
        """
        Sanitize JSON data, raising exception if invalid.
        
        Args:
            data: JSON data to sanitize
            field: Optional field name for error reporting
            
        Returns:
            Sanitized JSON data
            
        Raises:
            ValidationError: If data is invalid
        """
        return self.json_validator.sanitize(data, field)
    
    def check_rate_limit(self, identifier: str) -> bool:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: Identifier for rate limiting (e.g., IP address)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        if not self.config.enable_rate_limiting:
            return True
        
        import time
        current_time = time.time()
        
        with self._lock:
            # Clean old timestamps
            self._request_timestamps = [
                ts for ts in self._request_timestamps
                if current_time - ts < 60  # Keep last minute
            ]
            
            # Check per-second limit
            recent_requests = [
                ts for ts in self._request_timestamps
                if current_time - ts < 1  # Last second
            ]
            
            if len(recent_requests) >= self.config.max_requests_per_second:
                self._security_metrics['blocked_requests'] += 1
                return False
            
            # Check per-minute limit
            if len(self._request_timestamps) >= self.config.max_requests_per_minute:
                self._security_metrics['blocked_requests'] += 1
                return False
            
            # Record request
            self._request_timestamps.append(current_time)
            return True
    
    def validate_connection_parameters(self, host: str, database: str, 
                                     auth_token: Optional[str] = None) -> ValidationResult:
        """
        Validate connection parameters comprehensively.
        
        Args:
            host: Database host
            database: Database name/identifier
            auth_token: Optional authentication token
            
        Returns:
            ValidationResult with connection validation
        """
        errors = []
        warnings = []
        sanitized_values = {}
        
        # Validate host
        if host:
            # Construct URL for validation
            test_url = f"wss://{host}"
            host_result = self.url_validator.validate(test_url, "host")
            if not host_result.is_valid:
                errors.extend(host_result.errors)
            else:
                import urllib.parse
                parsed = urllib.parse.urlparse(host_result.sanitized_value)
                sanitized_values['host'] = parsed.netloc
            warnings.extend(host_result.warnings)
        
        # Validate database identifier
        if database:
            db_result = self.size_validator.validate(database, "database")
            if not db_result.is_valid:
                errors.extend(db_result.errors)
            else:
                sanitized_values['database'] = db_result.sanitized_value
            warnings.extend(db_result.warnings)
        
        # Validate auth token
        if auth_token:
            token_result = self.size_validator.validate(auth_token, "auth_token")
            if not token_result.is_valid:
                errors.extend(token_result.errors)
            else:
                sanitized_values['auth_token'] = token_result.sanitized_value
            warnings.extend(token_result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_value=sanitized_values if len(errors) == 0 else None,
            errors=errors,
            warnings=warnings
        )
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """
        Get current security metrics.
        
        Returns:
            Dictionary of security metrics
        """
        with self._lock:
            return self._security_metrics.copy()
    
    def reset_security_metrics(self):
        """Reset security metrics."""
        with self._lock:
            self._security_metrics = {
                'validation_failures': 0,
                'security_violations': 0,
                'blocked_requests': 0,
                'sanitized_inputs': 0,
            }
    
    def _handle_validation_failure(self, validation_type: str, value: Any, result: ValidationResult):
        """Handle validation failure."""
        self._security_metrics['validation_failures'] += 1
        
        if self.config.log_violations:
            self.logger.warning(
                f"Validation failure for {validation_type}: {'; '.join(str(e) for e in result.errors)}"
            )
        
        if self.config.on_validation_failure:
            try:
                self.config.on_validation_failure(validation_type, value)
            except Exception as e:
                self.logger.error(f"Error in validation failure callback: {e}")
        
        if self.config.strict_mode:
            self._security_metrics['security_violations'] += 1
            if self.config.on_security_violation:
                try:
                    self.config.on_security_violation(
                        'validation_failure', 
                        validation_type, 
                        value
                    )
                except Exception as e:
                    self.logger.error(f"Error in security violation callback: {e}")


# Global security manager instance
_global_security_manager: Optional[SecurityManager] = None
_global_security_manager_lock = threading.RLock()


def get_security_manager() -> SecurityManager:
    """
    Get the global security manager instance.
    
    Returns:
        Global SecurityManager instance
    """
    global _global_security_manager
    
    with _global_security_manager_lock:
        if _global_security_manager is None:
            _global_security_manager = SecurityManager()
        return _global_security_manager


def set_security_manager(manager: SecurityManager):
    """
    Set the global security manager instance.
    
    Args:
        manager: SecurityManager instance to use globally
    """
    global _global_security_manager
    
    with _global_security_manager_lock:
        _global_security_manager = manager


def configure_security(config: SecurityConfig):
    """
    Configure the global security manager.
    
    Args:
        config: SecurityConfig to apply
    """
    set_security_manager(SecurityManager(config))


# Convenience functions for common validation tasks
def validate_url(url: str, field: Optional[str] = None) -> ValidationResult:
    """Validate URL using global security manager."""
    return get_security_manager().validate_url(url, field)


def validate_websocket_url(url: str, field: Optional[str] = None) -> ValidationResult:
    """Validate WebSocket URL using global security manager."""
    return get_security_manager().validate_websocket_url(url, field)


def validate_sql_query(query: str, field: Optional[str] = None) -> ValidationResult:
    """Validate SQL query using global security manager."""
    return get_security_manager().validate_sql_query(query, field)


def validate_json_data(data: Any, field: Optional[str] = None) -> ValidationResult:
    """Validate JSON data using global security manager."""
    return get_security_manager().validate_json_data(data, field)


def sanitize_url(url: str, field: Optional[str] = None) -> str:
    """Sanitize URL using global security manager."""
    return get_security_manager().sanitize_url(url, field)


def sanitize_sql_query(query: str, field: Optional[str] = None) -> str:
    """Sanitize SQL query using global security manager."""
    return get_security_manager().sanitize_sql_query(query, field)


def sanitize_json_data(data: Any, field: Optional[str] = None) -> Any:
    """Sanitize JSON data using global security manager."""
    return get_security_manager().sanitize_json_data(data, field)