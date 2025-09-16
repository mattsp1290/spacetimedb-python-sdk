"""
Validation module for SpacetimeDB SDK.

This module provides comprehensive validation functions for URLs, JSON data,
SQL queries, database identifiers, and other security-critical inputs.
"""

# Import validation errors and base classes
from .validators import ValidationError, ValidationResult, ValidationConfig, Validator

# Import security manager and its functions
from .security_manager import (
    get_security_manager,
    validate_url,
    validate_json_data,
    validate_sql_query,
    sanitize_url,
    sanitize_sql_query,
    sanitize_json_data,
)

# Import specific validators
from .url_validator import validate_websocket_url
from .database_validator import validate_database_identifier
from .sql_validator import SQLValidator, SQLValidationError
from .data_validator import JSONValidator, JSONValidationError, DataSizeValidationError

# Import timeout utilities
from .timeout_cache_utils import ValidationTimeoutError, TimeoutValidator

__all__ = [
    # Core validation classes
    'ValidationError',
    'ValidationResult', 
    'ValidationConfig',
    'Validator',
    'TimeoutValidator',
    
    # Security manager
    'get_security_manager',
    
    # Validation functions
    'validate_url',
    'validate_websocket_url',
    'validate_json_data',
    'validate_sql_query',
    'validate_database_identifier',
    
    # Sanitization functions
    'sanitize_url',
    'sanitize_sql_query', 
    'sanitize_json_data',
    
    # Specific validators
    'SQLValidator',
    'JSONValidator',
    
    # Validation errors
    'SQLValidationError',
    'JSONValidationError',
    'DataSizeValidationError',
    'ValidationTimeoutError',
]