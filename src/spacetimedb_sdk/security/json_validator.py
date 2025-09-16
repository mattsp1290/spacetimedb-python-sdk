"""
Secure JSON Parser for SpacetimeDB Python SDK

This module provides a comprehensive secure JSON parser that prevents JSON bomb attacks
and other malicious JSON payloads through strict size and depth limits.

Security Features:
- Maximum JSON size limit (10MB default)
- Maximum nesting depth limit (100 levels default) 
- Maximum string length validation (1MB default)
- Protection against billion laughs attacks
- Comprehensive error handling with security-specific exceptions
- Security violation logging for monitoring
"""

import json
import logging
import sys
import time
from typing import Any, Optional, Dict, Union
from dataclasses import dataclass

# Configure security logging
security_logger = logging.getLogger('spacetimedb.security.json')

# Ensure the security logger is properly configured
if not security_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s [SECURITY] %(name)s %(levelname)s: %(message)s'
    )
    handler.setFormatter(formatter)
    security_logger.addHandler(handler)
    security_logger.setLevel(logging.WARNING)  # Log all security violations


class JSONSecurityError(Exception):
    """Base exception for JSON security violations."""
    
    def __init__(self, message: str, attack_type: str = "unknown", value: Any = None):
        super().__init__(message)
        self.attack_type = attack_type
        self.value = value
        self.timestamp = time.time()
        
        # Log security violation
        security_logger.warning(
            f"JSON Security Violation: {attack_type} - {message}",
            extra={
                'attack_type': attack_type,
                'timestamp': self.timestamp,
                'has_value': value is not None
            }
        )


class JSONBombError(JSONSecurityError):
    """Specific error for JSON bomb attacks (size/depth violations)."""
    
    def __init__(self, message: str, value: Any = None):
        super().__init__(message, "json_bomb", value)


class JSONDepthError(JSONSecurityError):
    """Specific error for JSON depth violations."""
    
    def __init__(self, message: str, depth: int, max_depth: int, value: Any = None):
        super().__init__(message, "excessive_depth", value)
        self.depth = depth
        self.max_depth = max_depth


class JSONSizeError(JSONSecurityError):
    """Specific error for JSON size violations."""
    
    def __init__(self, message: str, size: int, max_size: int, value: Any = None):
        super().__init__(message, "excessive_size", value)
        self.size = size
        self.max_size = max_size


@dataclass
class JSONSecurityConfig:
    """Configuration for secure JSON parsing."""
    
    # Size limits
    max_json_size: int = 10 * 1024 * 1024  # 10MB
    max_string_length: int = 1024 * 1024    # 1MB
    
    # Depth limits
    max_nesting_depth: int = 100
    
    # Object/Array limits
    max_object_keys: int = 1000
    max_array_length: int = 10000
    
    # Security features
    enable_logging: bool = True
    strict_mode: bool = True


class SecureJSONParser:
    """
    Secure JSON parser that prevents JSON bomb attacks and enforces strict limits.
    
    This parser implements multiple layers of security:
    1. Pre-parsing size validation
    2. Pre-parsing depth scanning
    3. Controlled parsing with depth tracking
    4. Post-parsing validation
    5. Comprehensive logging of security violations
    """
    
    def __init__(self, config: Optional[JSONSecurityConfig] = None):
        self.config = config or JSONSecurityConfig()
        self.logger = logging.getLogger(f'{__name__}.SecureJSONParser')
        
        # Initialize depth tracking
        self._current_depth = 0
        self._max_depth_seen = 0
    
    def safe_loads(self, json_str: str, field_name: Optional[str] = None) -> Any:
        """
        Safely parse JSON string with comprehensive security validation.
        
        Args:
            json_str: JSON string to parse
            field_name: Optional field name for error reporting
            
        Returns:
            Parsed JSON object
            
        Raises:
            JSONSecurityError: If security validation fails
            json.JSONDecodeError: If JSON syntax is invalid
        """
        if not isinstance(json_str, str):
            raise TypeError(f"Expected string, got {type(json_str).__name__}")
        
        # 1. Pre-parsing size validation
        self._validate_size(json_str, field_name)
        
        # 2. Pre-parsing depth scanning
        self._validate_depth_prescan(json_str, field_name)
        
        # 3. Controlled parsing with depth tracking
        try:
            self._reset_depth_tracking()
            parsed_data = json.loads(json_str, object_hook=self._depth_tracking_hook)
        except json.JSONDecodeError:
            # Let JSONDecodeError bubble up as-is
            raise
        except RecursionError as e:
            raise JSONDepthError(
                f"JSON nesting too deep (recursion limit exceeded)",
                self._max_depth_seen, 
                self.config.max_nesting_depth,
                json_str
            )
        except JSONSecurityError:
            # Re-raise our security errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise JSONSecurityError(
                f"Unexpected error during JSON parsing: {e}",
                "parsing_error",
                json_str
            )
        
        # 4. Post-parsing validation
        self._validate_parsed_data(parsed_data, field_name)
        
        # 5. Log successful parsing if enabled
        if self.config.enable_logging:
            self.logger.debug(
                f"Successfully parsed JSON (size: {len(json_str)}, max_depth: {self._max_depth_seen})"
            )
            
            # Log security statistics for monitoring
            security_logger.info(
                f"Secure JSON parsing successful for {field_name or 'unknown_field'}: "
                f"size={len(json_str)} bytes, depth={self._max_depth_seen}, "
                f"within_limits=size<{self.config.max_json_size}&depth<{self.config.max_nesting_depth}"
            )
        
        return parsed_data
    
    def _validate_size(self, json_str: str, field_name: Optional[str] = None):
        """Validate JSON string size before parsing."""
        size = len(json_str.encode('utf-8'))
        
        if size > self.config.max_json_size:
            raise JSONSizeError(
                f"JSON size too large: {size} bytes > {self.config.max_json_size} bytes" +
                (f" for field '{field_name}'" if field_name else ""),
                size,
                self.config.max_json_size,
                json_str
            )
    
    def _validate_depth_prescan(self, json_str: str, field_name: Optional[str] = None):
        """Pre-scan JSON string for excessive nesting before parsing."""
        max_depth = 0
        current_depth = 0
        in_string = False
        escaped = False
        
        for char in json_str:
            if escaped:
                escaped = False
                continue
            
            if char == '\\' and in_string:
                escaped = True
                continue
            
            if char == '"' and not escaped:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char in '{[':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
                
                # Fail fast on excessive depth
                if current_depth > self.config.max_nesting_depth:
                    raise JSONDepthError(
                        f"JSON nesting too deep: {current_depth} > {self.config.max_nesting_depth}" +
                        (f" for field '{field_name}'" if field_name else ""),
                        current_depth,
                        self.config.max_nesting_depth,
                        json_str
                    )
            elif char in '}]':
                current_depth = max(0, current_depth - 1)
    
    def _reset_depth_tracking(self):
        """Reset depth tracking for new parsing operation."""
        self._current_depth = 0
        self._max_depth_seen = 0
    
    def _depth_tracking_hook(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Object hook for tracking parsing depth during json.loads()."""
        self._current_depth += 1
        self._max_depth_seen = max(self._max_depth_seen, self._current_depth)
        
        # Safety check during parsing
        if self._current_depth > self.config.max_nesting_depth:
            raise JSONDepthError(
                f"JSON parsing depth exceeded: {self._current_depth} > {self.config.max_nesting_depth}",
                self._current_depth,
                self.config.max_nesting_depth
            )
        
        # Additional safety check against Python recursion limits
        if self._current_depth > 900:  # Conservative limit before Python's ~1000 limit
            raise JSONDepthError(
                f"JSON parsing approaching Python recursion limit: {self._current_depth}",
                self._current_depth,
                900
            )
        
        try:
            return obj
        finally:
            self._current_depth -= 1
    
    def _validate_parsed_data(self, data: Any, field_name: Optional[str] = None, depth: int = 0):
        """Recursively validate parsed JSON data structure."""
        # Prevent recursion beyond limits
        if depth > self.config.max_nesting_depth:
            raise JSONDepthError(
                f"Parsed data nesting too deep: {depth} > {self.config.max_nesting_depth}" +
                (f" for field '{field_name}'" if field_name else ""),
                depth,
                self.config.max_nesting_depth,
                data
            )
        
        if isinstance(data, dict):
            self._validate_dict(data, field_name, depth)
        elif isinstance(data, list):
            self._validate_list(data, field_name, depth)
        elif isinstance(data, str):
            self._validate_string(data, field_name)
        # Other types (int, float, bool, None) are inherently safe
    
    def _validate_dict(self, data: Dict[str, Any], field_name: Optional[str], depth: int):
        """Validate dictionary structure and contents."""
        # Check number of keys
        if len(data) > self.config.max_object_keys:
            raise JSONBombError(
                f"Object has too many keys: {len(data)} > {self.config.max_object_keys}" +
                (f" for field '{field_name}'" if field_name else ""),
                data
            )
        
        # Validate each key-value pair
        for key, value in data.items():
            # Validate key
            if not isinstance(key, str):
                raise JSONSecurityError(
                    f"Object key must be string, got {type(key).__name__}" +
                    (f" for field '{field_name}'" if field_name else ""),
                    "invalid_key_type",
                    data
                )
            
            # Validate key length
            if len(key) > 1000:  # Reasonable key length limit
                raise JSONBombError(
                    f"Object key too long: {len(key)} > 1000" +
                    (f" for field '{field_name}'" if field_name else ""),
                    data
                )
            
            # Recursively validate value
            child_field = f"{field_name}.{key}" if field_name else key
            self._validate_parsed_data(value, child_field, depth + 1)
    
    def _validate_list(self, data: list, field_name: Optional[str], depth: int):
        """Validate list structure and contents."""
        # Check array length
        if len(data) > self.config.max_array_length:
            raise JSONBombError(
                f"Array too long: {len(data)} > {self.config.max_array_length}" +
                (f" for field '{field_name}'" if field_name else ""),
                data
            )
        
        # Validate each element
        for i, item in enumerate(data):
            child_field = f"{field_name}[{i}]" if field_name else f"[{i}]"
            self._validate_parsed_data(item, child_field, depth + 1)
    
    def _validate_string(self, data: str, field_name: Optional[str]):
        """Validate string length."""
        if len(data) > self.config.max_string_length:
            raise JSONBombError(
                f"String too long: {len(data)} > {self.config.max_string_length}" +
                (f" for field '{field_name}'" if field_name else ""),
                data
            )


# Default secure JSON parser instance
_default_parser = SecureJSONParser()


def secure_json_loads(json_str: str, field_name: Optional[str] = None, 
                     config: Optional[JSONSecurityConfig] = None) -> Any:
    """
    Convenience function for secure JSON parsing.
    
    Args:
        json_str: JSON string to parse
        field_name: Optional field name for error reporting
        config: Optional custom configuration
        
    Returns:
        Parsed JSON object
        
    Raises:
        JSONSecurityError: If security validation fails
        json.JSONDecodeError: If JSON syntax is invalid
    """
    if config:
        parser = SecureJSONParser(config)
        return parser.safe_loads(json_str, field_name)
    else:
        return _default_parser.safe_loads(json_str, field_name)


def configure_json_security(config: JSONSecurityConfig):
    """
    Configure the default secure JSON parser.
    
    Args:
        config: New security configuration
    """
    global _default_parser
    _default_parser = SecureJSONParser(config)