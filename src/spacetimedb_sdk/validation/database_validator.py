"""
Database name validation to prevent injection attacks and ensure proper format.

This module provides comprehensive validation for SpacetimeDB database names,
preventing SQL injection, path traversal, and other security vulnerabilities.
"""

import re
import unicodedata
from typing import Optional, List
from .validators import Validator, ValidationResult, ValidationError, ValidationConfig
from .sql_validator import SQLValidator


class DatabaseValidationError(ValidationError):
    """Specific error for database name validation failures."""
    pass


class DatabaseNameValidator(Validator):
    """
    Validator for database names to prevent injection attacks and ensure proper format.
    
    This validator:
    - Detects and prevents SQL injection attempts
    - Validates Unicode characters and encoding
    - Prevents path traversal attacks
    - Validates database name format and characters
    - Enforces length limits
    - Blocks dangerous patterns and characters
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        super().__init__(config)
        
        # Initialize SQL validator for injection detection
        self.sql_validator = SQLValidator(config)
        
        # Patterns for detecting malicious database names
        self._injection_patterns = [
            # SQL injection patterns
            re.compile(r"'.*?'", re.IGNORECASE),  # Single quotes
            re.compile(r'".*?"', re.IGNORECASE),  # Double quotes
            re.compile(r'--', re.IGNORECASE),     # SQL comments
            re.compile(r'/\*.*?\*/', re.IGNORECASE | re.DOTALL),  # Block comments
            re.compile(r';\s*\w+', re.IGNORECASE),  # Statement separators
            re.compile(r'\bor\b.*?=.*?', re.IGNORECASE),  # Boolean injection
            re.compile(r'\band\b.*?=.*?', re.IGNORECASE),  # Boolean injection
            re.compile(r'\bunion\b.*?\bselect\b', re.IGNORECASE),  # Union injection
            re.compile(r'\bdrop\b.*?\btable\b', re.IGNORECASE),  # Drop table
            re.compile(r'\bdelete\b.*?\bfrom\b', re.IGNORECASE),  # Delete statements
            re.compile(r'\binsert\b.*?\binto\b', re.IGNORECASE),  # Insert statements
            re.compile(r'\bupdate\b.*?\bset\b', re.IGNORECASE),  # Update statements
            re.compile(r'\bexec\b', re.IGNORECASE),  # Execute commands
            re.compile(r'\bsp_\w+', re.IGNORECASE),  # Stored procedures
            
            # Path traversal patterns
            re.compile(r'\.\./', re.IGNORECASE),  # Directory traversal
            re.compile(r'%2e%2e%2f', re.IGNORECASE),  # Encoded traversal
            re.compile(r'\.\.\\', re.IGNORECASE),  # Windows traversal
            re.compile(r'%2e%2e%5c', re.IGNORECASE),  # Encoded Windows traversal
            
            # Script injection patterns
            re.compile(r'<script', re.IGNORECASE),  # Script tags
            re.compile(r'javascript:', re.IGNORECASE),  # JavaScript URLs
            re.compile(r'vbscript:', re.IGNORECASE),  # VBScript URLs
            re.compile(r'data:', re.IGNORECASE),  # Data URLs
            re.compile(r'file:', re.IGNORECASE),  # File URLs
            
            # Command injection patterns
            re.compile(r'[;&|`$]', re.IGNORECASE),  # Command separators
            re.compile(r'\$\(.*?\)', re.IGNORECASE),  # Command substitution
            re.compile(r'`.*?`', re.IGNORECASE),  # Backtick execution
            
            # Null byte injection
            re.compile(r'\x00'),  # Null bytes
            
            # CRLF injection
            re.compile(r'[\r\n]'),  # Carriage return/line feed
        ]
        
        # Characters that are explicitly blocked in database names
        self._blocked_chars = {
            '\x00', '\r', '\n', '\t',  # Control characters
            '<', '>', '"', "'", '`',   # Quote/bracket characters
            '&', '|', ';', '$',        # Command separators
            '?', '*', ':', '\\',       # Wildcard/path characters
            '%', '#',                  # URL encoding/comments
            '_',                       # Underscore not allowed
        }
        
        # Valid database name pattern (letters, numbers, dash, dot) - underscores not allowed
        self._valid_name_pattern = re.compile(r'^[a-zA-Z0-9.-]+$')
        
        # Maximum reasonable database name length
        self._max_db_name_length = 100
        
        # Minimum database name length
        self._min_db_name_length = 1
    
    def validate(self, value: str, field: Optional[str] = None) -> ValidationResult:
        """
        Validate database name for security and format issues.
        
        Args:
            value: Database name to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with validation status and sanitized name
        """
        errors = []
        warnings = []
        
        # Type check
        if not isinstance(value, str):
            errors.append(DatabaseValidationError(
                f"Database name must be a string, got {type(value).__name__}",
                field=field,
                value=value
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Empty check
        if not value or not value.strip():
            errors.append(DatabaseValidationError(
                "Database name cannot be empty",
                field=field,
                value=value
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        # Length checks
        if len(value) < self._min_db_name_length:
            errors.append(DatabaseValidationError(
                f"Database name too short: {len(value)} < {self._min_db_name_length}",
                field=field,
                value=value
            ))
        
        if len(value) > self._max_db_name_length:
            errors.append(DatabaseValidationError(
                f"Database name too long: {len(value)} > {self._max_db_name_length}",
                field=field,
                value=value
            ))
        
        # Unicode validation
        unicode_errors = self._validate_unicode(value, field)
        errors.extend(unicode_errors)
        
        # SQL injection detection
        injection_errors = self._detect_sql_injection(value, field)
        errors.extend(injection_errors)
        
        # Pattern-based malicious content detection
        pattern_errors = self._detect_malicious_patterns(value, field)
        errors.extend(pattern_errors)
        
        # Character validation
        char_errors = self._validate_characters(value, field)
        errors.extend(char_errors)
        
        # Format validation
        format_errors = self._validate_format(value, field)
        errors.extend(format_errors)
        
        # Additional security checks
        security_warnings = self._security_checks(value, field)
        warnings.extend(security_warnings)
        
        # Sanitize the name if validation passed
        sanitized_name = value.strip() if not errors else None
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_value=sanitized_name,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_unicode(self, name: str, field: Optional[str]) -> List[DatabaseValidationError]:
        """Validate Unicode encoding and characters."""
        errors = []
        
        try:
            # Check for valid UTF-8 encoding
            name.encode('utf-8')
            
            # Check for problematic Unicode characters
            for i, char in enumerate(name):
                category = unicodedata.category(char)
                
                # Block control characters (except basic whitespace)
                if category.startswith('C') and char not in [' ', '\t']:
                    errors.append(DatabaseValidationError(
                        f"Invalid Unicode control character at position {i}: U+{ord(char):04X}",
                        field=field,
                        value=name
                    ))
                
                # Block private use characters
                if category == 'Co':
                    errors.append(DatabaseValidationError(
                        f"Private use Unicode character at position {i}: U+{ord(char):04X}",
                        field=field,
                        value=name
                    ))
                
                # Block surrogates (should not appear in valid UTF-8)
                if category == 'Cs':
                    errors.append(DatabaseValidationError(
                        f"Surrogate Unicode character at position {i}: U+{ord(char):04X}",
                        field=field,
                        value=name
                    ))
                
                # Block certain symbols that could be confusing
                if ord(char) in [0x200B, 0x200C, 0x200D, 0xFEFF]:  # Zero-width chars, BOM
                    errors.append(DatabaseValidationError(
                        f"Invisible Unicode character at position {i}: U+{ord(char):04X}",
                        field=field,
                        value=name
                    ))
            
            # Check for emoji and other non-basic characters
            # For database names, we should be conservative
            has_emoji = any(
                ord(char) >= 0x1F600 and ord(char) <= 0x1F64F or  # Emoticons
                ord(char) >= 0x1F300 and ord(char) <= 0x1F5FF or  # Misc Symbols
                ord(char) >= 0x1F680 and ord(char) <= 0x1F6FF or  # Transport
                ord(char) >= 0x2600 and ord(char) <= 0x26FF or    # Misc symbols
                ord(char) >= 0x2700 and ord(char) <= 0x27BF       # Dingbats
                for char in name
            )
            
            if has_emoji:
                errors.append(DatabaseValidationError(
                    "Database name contains emoji or special symbols",
                    field=field,
                    value=name
                ))
            
        except UnicodeError as e:
            errors.append(DatabaseValidationError(
                f"Invalid Unicode encoding: {e}",
                field=field,
                value=name
            ))
        
        return errors
    
    def _detect_sql_injection(self, name: str, field: Optional[str]) -> List[DatabaseValidationError]:
        """Detect SQL injection attempts in database name."""
        errors = []
        
        # Use SQL validator to check for injection patterns
        sql_result = self.sql_validator.validate(f"SELECT * FROM {name}", f"{field}_sql_check")
        
        if not sql_result.is_valid:
            # If treating the name as part of a SQL query fails validation,
            # it's likely dangerous
            for sql_error in sql_result.errors:
                errors.append(DatabaseValidationError(
                    f"Potential SQL injection detected: {sql_error.message}",
                    field=field,
                    value=name
                ))
        
        return errors
    
    def _detect_malicious_patterns(self, name: str, field: Optional[str]) -> List[DatabaseValidationError]:
        """Detect malicious patterns in database name."""
        errors = []
        
        for pattern in self._injection_patterns:
            if pattern.search(name):
                errors.append(DatabaseValidationError(
                    f"Malicious pattern detected: {pattern.pattern}",
                    field=field,
                    value=name
                ))
        
        return errors
    
    def _validate_characters(self, name: str, field: Optional[str]) -> List[DatabaseValidationError]:
        """Validate individual characters in database name."""
        errors = []
        
        # Check for blocked characters
        for i, char in enumerate(name):
            if char in self._blocked_chars:
                errors.append(DatabaseValidationError(
                    f"Blocked character '{char}' at position {i}",
                    field=field,
                    value=name
                ))
        
        return errors
    
    def _validate_format(self, name: str, field: Optional[str]) -> List[DatabaseValidationError]:
        """Validate overall format of database name."""
        errors = []
        
        # Check against valid pattern
        if not self._valid_name_pattern.match(name):
            errors.append(DatabaseValidationError(
                "Database name contains invalid characters. Only letters, numbers, dash, and dot are allowed",
                field=field,
                value=name
            ))
        
        # Check for leading/trailing dots or dashes
        if name.startswith('.') or name.endswith('.'):
            errors.append(DatabaseValidationError(
                "Database name cannot start or end with a dot",
                field=field,
                value=name
            ))
        
        if name.startswith('-') or name.endswith('-'):
            errors.append(DatabaseValidationError(
                "Database name cannot start or end with a dash",
                field=field,
                value=name
            ))
        
        # Check for consecutive dots
        if '..' in name:
            errors.append(DatabaseValidationError(
                "Database name cannot contain consecutive dots",
                field=field,
                value=name
            ))
        
        # Check for spaces (should be caught by pattern, but explicit check)
        if ' ' in name:
            errors.append(DatabaseValidationError(
                "Database name cannot contain spaces",
                field=field,
                value=name
            ))
        
        return errors
    
    def _security_checks(self, name: str, field: Optional[str]) -> List[str]:
        """Additional security checks that generate warnings."""
        warnings = []
        
        # Check for suspicious patterns that might not be malicious
        suspicious_patterns = [
            (re.compile(r'^test', re.IGNORECASE), "Database name starts with 'test'"),
            (re.compile(r'^admin', re.IGNORECASE), "Database name starts with 'admin'"),
            (re.compile(r'^root', re.IGNORECASE), "Database name starts with 'root'"),
            (re.compile(r'password', re.IGNORECASE), "Database name contains 'password'"),
            (re.compile(r'secret', re.IGNORECASE), "Database name contains 'secret'"),
            (re.compile(r'key', re.IGNORECASE), "Database name contains 'key'"),
        ]
        
        for pattern, message in suspicious_patterns:
            if pattern.search(name):
                warnings.append(message)
        
        # Check for very short names
        if len(name) <= 2:
            warnings.append("Database name is very short and might be confusing")
        
        # Check for all numeric names
        if name.isdigit():
            warnings.append("Database name is all numeric")
        
        return warnings
    
    def validate_and_raise(self, value: str, field: Optional[str] = None) -> str:
        """
        Validate database name and raise ValueError if invalid.
        
        Args:
            value: Database name to validate
            field: Optional field name for error reporting
            
        Returns:
            Sanitized database name
            
        Raises:
            ValueError: If validation fails
        """
        result = self.validate(value, field)
        
        if not result.is_valid:
            error_messages = [str(error) for error in result.errors]
            raise ValueError(f"Invalid database name: {'; '.join(error_messages)}")
        
        return result.sanitized_value


# Global instance for convenience functions
_database_validator = DatabaseNameValidator()


def validate_database_identifier(name: str, field: Optional[str] = None) -> ValidationResult:
    """
    Convenience function to validate database identifiers.
    
    Args:
        name: Database name to validate
        field: Optional field name for error reporting
        
    Returns:
        ValidationResult with validation results
    """
    return _database_validator.validate(name, field)


__all__ = [
    'DatabaseNameValidator',
    'validate_database_identifier'
]