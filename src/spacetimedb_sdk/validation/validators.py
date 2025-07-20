"""
Base validator classes for the SpacetimeDB validation framework.

This module provides the abstract base classes and core functionality
for all validators used throughout the SDK.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, NamedTuple
from dataclasses import dataclass, field
import logging
import re
import time
from functools import wraps
from ..utils.error_formatting import ErrorFormatter

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base exception for validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value
        self.message = message
    
    def __str__(self):
        if self.field:
            return f"Validation error for field '{self.field}': {self.message}"
        return f"Validation error: {self.message}"


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    sanitized_value: Any = None
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def value(self) -> Any:
        """Get the sanitized value or original value if validation failed."""
        return self.sanitized_value if self.is_valid else None



@dataclass
class ValidationConfig:
    """Configuration for validators."""
    
    # URL validation settings
    max_url_length: int = 2048
    allowed_url_schemes: List[str] = field(default_factory=lambda: ['ws', 'wss', 'http', 'https'])
    allowed_url_hosts: Optional[List[str]] = None  # None means all hosts allowed
    
    # SQL validation settings
    max_query_length: int = 10000
    allow_multi_statements: bool = False
    blocked_sql_keywords: List[str] = field(default_factory=lambda: [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE'
    ])
    
    # JSON validation settings
    max_json_size: int = 10 * 1024 * 1024  # 10MB
    max_json_depth: int = 100
    
    # General data size limits
    max_string_length: int = 1024 * 1024  # 1MB
    max_array_length: int = 10000
    max_object_keys: int = 1000
    
    # Performance settings
    validation_timeout: float = 5.0  # seconds
    enable_strict_mode: bool = False  # If True, any warning becomes an error


class Validator(ABC):
    """Abstract base class for all validators."""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """
        Validate and optionally sanitize a value.
        
        Args:
            value: The value to validate
            field: Optional field name for error reporting
            
        Returns:
            ValidationResult with validation status and sanitized value
        """
        pass
    
    def is_valid(self, value: Any, field: Optional[str] = None) -> bool:
        """Check if a value is valid without sanitization."""
        try:
            result = self.validate(value, field)
            return result.is_valid
        except Exception as e:
            self.logger.error(ErrorFormatter.format_generic_error("Validator", "validation", e))
            return False
    
    def sanitize(self, value: Any, field: Optional[str] = None) -> Any:
        """
        Sanitize a value, raising ValidationError if invalid.
        
        Args:
            value: The value to sanitize
            field: Optional field name for error reporting
            
        Returns:
            Sanitized value
            
        Raises:
            ValidationError: If validation fails
        """
        result = self.validate(value, field)
        if not result.is_valid:
            raise ValidationError(
                f"Validation failed: {'; '.join(str(e) for e in result.errors)}",
                field=field,
                value=value
            )
        return result.sanitized_value


class CompositeValidator(Validator):
    """Validator that combines multiple validators."""
    
    def __init__(self, validators: List[Validator], config: Optional[ValidationConfig] = None):
        super().__init__(config)
        self.validators = validators
    
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Apply all validators in sequence."""
        current_value = value
        all_errors = []
        all_warnings = []
        
        for validator in self.validators:
            try:
                result = validator.validate(current_value, field)
                
                if not result.is_valid:
                    all_errors.extend(result.errors)
                    if self.config.enable_strict_mode:
                        # In strict mode, stop at first failure
                        break
                
                all_warnings.extend(result.warnings)
                
                # Use sanitized value for next validator if available
                if result.sanitized_value is not None:
                    current_value = result.sanitized_value
                    
            except Exception as e:
                all_errors.append(ValidationError(
                    f"Validator {validator.__class__.__name__} failed: {e}",
                    field=field,
                    value=current_value
                ))
                if self.config.enable_strict_mode:
                    break
        
        is_valid = len(all_errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            sanitized_value=current_value if is_valid else None,
            errors=all_errors,
            warnings=all_warnings
        )


class LengthValidator(Validator):
    """Validator for string and collection length limits."""
    
    def __init__(self, max_length: int, min_length: int = 0, config: Optional[ValidationConfig] = None):
        super().__init__(config)
        self.max_length = max_length
        self.min_length = min_length
    
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Validate length of string or collection."""
        errors = []
        
        if value is None:
            return ValidationResult(is_valid=True, sanitized_value=value)
        
        try:
            length = len(value)
            
            if length < self.min_length:
                errors.append(ValidationError(
                    f"Value too short: {length} < {self.min_length}",
                    field=field,
                    value=value
                ))
            
            if length > self.max_length:
                errors.append(ValidationError(
                    f"Value too long: {length} > {self.max_length}",
                    field=field,
                    value=value
                ))
            
        except TypeError:
            errors.append(ValidationError(
                f"Value does not support len(): {type(value).__name__}",
                field=field,
                value=value
            ))
        
        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            sanitized_value=value if is_valid else None,
            errors=errors
        )


class TypeValidator(Validator):
    """Validator for type checking."""
    
    def __init__(self, expected_type: Union[type, tuple], config: Optional[ValidationConfig] = None):
        super().__init__(config)
        self.expected_type = expected_type
    
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Validate that value is of expected type."""
        if isinstance(value, self.expected_type):
            return ValidationResult(is_valid=True, sanitized_value=value)
        
        error = ValidationError(
            f"Expected type {self.expected_type}, got {type(value).__name__}",
            field=field,
            value=value
        )
        
        return ValidationResult(
            is_valid=False,
            sanitized_value=None,
            errors=[error]
        )


class RegexValidator(Validator):
    """Validator using regular expressions."""
    
    def __init__(self, pattern: str, config: Optional[ValidationConfig] = None):
        super().__init__(config)
        self.pattern = pattern
        self.regex = re.compile(pattern)
    
    def validate(self, value: Any, field: Optional[str] = None) -> ValidationResult:
        """Validate that value matches regex pattern."""
        if not isinstance(value, str):
            error = ValidationError(
                f"RegexValidator requires string, got {type(value).__name__}",
                field=field,
                value=value
            )
            return ValidationResult(is_valid=False, sanitized_value=None, errors=[error])
        
        if self.regex.match(value):
            return ValidationResult(is_valid=True, sanitized_value=value)
        
        error = ValidationError(
            f"Value does not match pattern: {self.pattern}",
            field=field,
            value=value
        )
        
        return ValidationResult(
            is_valid=False,
            sanitized_value=None,
            errors=[error]
        )