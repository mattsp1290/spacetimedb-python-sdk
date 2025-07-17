"""
URL validation to prevent injection attacks and ensure proper URL format.

This module provides comprehensive URL validation for SpacetimeDB connections,
preventing malicious URLs and ensuring proper format for WebSocket connections.
"""

import urllib.parse
import re
from typing import Optional, List, Set
from .validators import Validator, ValidationResult, ValidationError, ValidationConfig


class URLValidationError(ValidationError):
    """Specific error for URL validation failures."""
    pass


class URLValidator(Validator):
    """
    Validator for URLs to prevent injection attacks and ensure proper format.
    
    This validator:
    - Validates URL scheme (ws, wss, http, https)
    - Validates hostname format and prevents malicious hosts
    - Validates port numbers
    - Prevents path traversal attacks
    - Sanitizes query parameters
    - Enforces length limits
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        super().__init__(config)
        
        # Compiled regex patterns for performance
        self._hostname_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
        )
        self._ipv4_pattern = re.compile(
            r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        )
        self._ipv6_pattern = re.compile(
            r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$|^::$'
        )
        
        # Dangerous patterns to block
        self._blocked_patterns = [
            re.compile(r'\.\./', re.IGNORECASE),  # Path traversal
            re.compile(r'%2e%2e%2f', re.IGNORECASE),  # Encoded path traversal
            re.compile(r'<script', re.IGNORECASE),  # XSS attempts
            re.compile(r'javascript:', re.IGNORECASE),  # JavaScript URLs
            re.compile(r'data:', re.IGNORECASE),  # Data URLs
            re.compile(r'file:', re.IGNORECASE),  # File URLs
            re.compile(r'ftp:', re.IGNORECASE),  # FTP URLs
        ]
    
    def validate(self, value: str, field: Optional[str] = None) -> ValidationResult:
        """
        Validate and sanitize a URL.
        
        Args:
            value: URL string to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with validation status and sanitized URL
        """
        errors = []
        warnings = []
        
        # Type check
        if not isinstance(value, str):
            errors.append(URLValidationError(
                f"URL must be a string, got {type(value).__name__}",
                field=field,
                value=value
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Length check
        if len(value) > self.config.max_url_length:
            errors.append(URLValidationError(
                f"URL too long: {len(value)} > {self.config.max_url_length}",
                field=field,
                value=value
            ))
        
        # Empty URL check
        if not value.strip():
            errors.append(URLValidationError(
                "URL cannot be empty",
                field=field,
                value=value
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Check for blocked patterns
        for pattern in self._blocked_patterns:
            if pattern.search(value):
                errors.append(URLValidationError(
                    f"URL contains blocked pattern: {pattern.pattern}",
                    field=field,
                    value=value
                ))
        
        # Parse URL
        try:
            parsed = urllib.parse.urlparse(value)
        except Exception as e:
            errors.append(URLValidationError(
                f"Invalid URL format: {e}",
                field=field,
                value=value
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Validate scheme
        if parsed.scheme.lower() not in self.config.allowed_url_schemes:
            errors.append(URLValidationError(
                f"URL scheme '{parsed.scheme}' not allowed. Allowed: {self.config.allowed_url_schemes}",
                field=field,
                value=value
            ))
        
        # Validate hostname
        hostname_errors = self._validate_hostname(parsed.netloc, field, value)
        errors.extend(hostname_errors)
        
        # Validate port
        port_errors = self._validate_port(parsed.port, field, value)
        errors.extend(port_errors)
        
        # Validate path
        path_errors = self._validate_path(parsed.path, field, value)
        errors.extend(path_errors)
        
        # Sanitize query parameters
        sanitized_query, query_warnings = self._sanitize_query(parsed.query)
        warnings.extend(query_warnings)
        
        # Build sanitized URL if validation passed
        sanitized_url = None
        if not errors:
            # Reconstruct URL with sanitized components
            sanitized_parsed = parsed._replace(query=sanitized_query)
            sanitized_url = urllib.parse.urlunparse(sanitized_parsed)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_value=sanitized_url,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_hostname(self, netloc: str, field: Optional[str], value: str) -> List[URLValidationError]:
        """Validate hostname/netloc portion of URL."""
        errors = []
        
        if not netloc:
            errors.append(URLValidationError(
                "URL must have a hostname",
                field=field,
                value=value
            ))
            return errors
        
        # Split hostname and port
        hostname = netloc.split(':')[0]
        
        # Check against allowed hosts if configured
        if self.config.allowed_url_hosts:
            if hostname not in self.config.allowed_url_hosts:
                errors.append(URLValidationError(
                    f"Hostname '{hostname}' not in allowed hosts: {self.config.allowed_url_hosts}",
                    field=field,
                    value=value
                ))
        
        # Validate hostname format
        if not self._is_valid_hostname(hostname):
            errors.append(URLValidationError(
                f"Invalid hostname format: '{hostname}'",
                field=field,
                value=value
            ))
        
        # Check for localhost variations that might be suspicious
        suspicious_hosts = ['0.0.0.0', '127.0.0.1', '::1', 'localhost']
        if hostname.lower() in suspicious_hosts:
            # This is a warning, not an error, as localhost might be legitimate
            pass
        
        return errors
    
    def _validate_port(self, port: Optional[int], field: Optional[str], value: str) -> List[URLValidationError]:
        """Validate port number."""
        errors = []
        
        if port is not None:
            if not isinstance(port, int) or port < 1 or port > 65535:
                errors.append(URLValidationError(
                    f"Invalid port number: {port}",
                    field=field,
                    value=value
                ))
        
        return errors
    
    def _validate_path(self, path: str, field: Optional[str], value: str) -> List[URLValidationError]:
        """Validate URL path for injection attacks."""
        errors = []
        
        # Check for path traversal attempts
        if '..' in path:
            errors.append(URLValidationError(
                "Path traversal attempt detected",
                field=field,
                value=value
            ))
        
        # Check for encoded path traversal
        if '%2e%2e' in path.lower():
            errors.append(URLValidationError(
                "Encoded path traversal attempt detected",
                field=field,
                value=value
            ))
        
        # Check for null bytes
        if '\x00' in path:
            errors.append(URLValidationError(
                "Null byte in path",
                field=field,
                value=value
            ))
        
        return errors
    
    def _sanitize_query(self, query: str) -> tuple[str, List[str]]:
        """Sanitize query parameters."""
        warnings = []
        
        if not query:
            return query, warnings
        
        try:
            # Parse query parameters
            params = urllib.parse.parse_qs(query, keep_blank_values=True)
            
            # Sanitize each parameter
            sanitized_params = {}
            for key, values in params.items():
                # Sanitize key
                sanitized_key = self._sanitize_param(key)
                if sanitized_key != key:
                    warnings.append(f"Query parameter key sanitized: '{key}' -> '{sanitized_key}'")
                
                # Sanitize values
                sanitized_values = []
                for value in values:
                    sanitized_value = self._sanitize_param(value)
                    if sanitized_value != value:
                        warnings.append(f"Query parameter value sanitized: '{value}' -> '{sanitized_value}'")
                    sanitized_values.append(sanitized_value)
                
                sanitized_params[sanitized_key] = sanitized_values
            
            # Reconstruct query string
            sanitized_query = urllib.parse.urlencode(sanitized_params, doseq=True)
            return sanitized_query, warnings
            
        except Exception as e:
            warnings.append(f"Failed to sanitize query parameters: {e}")
            return query, warnings
    
    def _sanitize_param(self, param: str) -> str:
        """Sanitize a single query parameter."""
        # Remove dangerous characters
        sanitized = re.sub(r'[<>&"\'`\x00-\x1f\x7f-\x9f]', '', param)
        
        # Limit length
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000]
        
        return sanitized
    
    def _is_valid_hostname(self, hostname: str) -> bool:
        """Check if hostname has valid format."""
        if not hostname:
            return False
        
        # Check for IPv4
        if self._ipv4_pattern.match(hostname):
            return True
        
        # Check for IPv6 (simplified)
        if hostname.startswith('[') and hostname.endswith(']'):
            ipv6_addr = hostname[1:-1]
            if self._ipv6_pattern.match(ipv6_addr):
                return True
        
        # Check for valid hostname
        if len(hostname) > 253:
            return False
        
        if hostname.endswith('.'):
            hostname = hostname[:-1]
        
        return self._hostname_pattern.match(hostname) is not None
    
    def validate_websocket_url(self, url: str, field: Optional[str] = None) -> ValidationResult:
        """
        Specialized validation for WebSocket URLs.
        
        Args:
            url: WebSocket URL to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with WebSocket-specific validation
        """
        # First do general URL validation
        result = self.validate(url, field)
        
        if not result.is_valid:
            return result
        
        # Additional WebSocket-specific validation
        parsed = urllib.parse.urlparse(result.sanitized_value)
        
        # Ensure WebSocket scheme
        if parsed.scheme.lower() not in ['ws', 'wss']:
            error = URLValidationError(
                f"WebSocket URL must use 'ws' or 'wss' scheme, got '{parsed.scheme}'",
                field=field,
                value=url
            )
            return ValidationResult(is_valid=False, errors=[error])
        
        return result
    
    def validate_spacetimedb_url(self, url: str, field: Optional[str] = None) -> ValidationResult:
        """
        Specialized validation for SpacetimeDB URLs.
        
        Args:
            url: SpacetimeDB URL to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with SpacetimeDB-specific validation
        """
        # First do WebSocket validation
        result = self.validate_websocket_url(url, field)
        
        if not result.is_valid:
            return result
        
        # Additional SpacetimeDB-specific validation
        parsed = urllib.parse.urlparse(result.sanitized_value)
        
        # Check for expected path structure
        if not parsed.path or not parsed.path.startswith('/'):
            warning = f"SpacetimeDB URL should have a path starting with '/'"
            result = result._replace(warnings=result.warnings + [warning])
        
        return result