"""
SpacetimeDB Input Validation Framework

This module provides comprehensive input validation to prevent injection attacks
and ensure data integrity throughout the SpacetimeDB Python SDK.

Key Features:
- URL validation and sanitization to prevent injection
- SQL query parameterization to prevent SQL injection
- JSON parsing with size limits to prevent memory exhaustion
- Configurable data size limits for all inputs
- Composable validator chains for complex validation logic
"""

from .validators import (
    Validator,
    CompositeValidator,
    ValidationError,
    ValidationResult,
    ValidationConfig
)
from .url_validator import URLValidator, URLValidationError
from .sql_validator import SQLValidator, SQLValidationError
from .data_validator import (
    JSONValidator,
    DataSizeValidator,
    MessageValidator,
    JSONValidationError,
    DataSizeValidationError
)
from .security_manager import (
    SecurityManager,
    SecurityConfig,
    get_security_manager,
    set_security_manager,
    configure_security,
    validate_url,
    validate_websocket_url,
    validate_sql_query,
    validate_json_data,
    sanitize_url,
    sanitize_sql_query,
    sanitize_json_data
)

__all__ = [
    # Base classes
    'Validator',
    'CompositeValidator',
    'ValidationError',
    'ValidationResult',
    'ValidationConfig',
    
    # Specific validators
    'URLValidator',
    'URLValidationError',
    'SQLValidator',
    'SQLValidationError',
    'JSONValidator',
    'DataSizeValidator',
    'MessageValidator',
    'JSONValidationError',
    'DataSizeValidationError',
    
    # Security management
    'SecurityManager',
    'SecurityConfig',
    'get_security_manager',
    'set_security_manager',
    'configure_security',
    
    # Convenience functions
    'validate_url',
    'validate_websocket_url',
    'validate_sql_query',
    'validate_json_data',
    'sanitize_url',
    'sanitize_sql_query',
    'sanitize_json_data',
]

# Default validation configuration
DEFAULT_CONFIG = ValidationConfig(
    # URL validation
    max_url_length=2048,
    allowed_url_schemes=['ws', 'wss', 'http', 'https'],
    
    # SQL validation
    max_query_length=10000,
    allow_multi_statements=False,
    
    # JSON validation
    max_json_size=10 * 1024 * 1024,  # 10MB
    max_json_depth=100,
    
    # General data size limits
    max_string_length=1024 * 1024,  # 1MB
    max_array_length=10000,
    max_object_keys=1000,
)