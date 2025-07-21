"""
SpacetimeDB Security Framework

This module provides comprehensive security validation and protection
mechanisms for the SpacetimeDB Python SDK.
"""

from .json_validator import (
    SecureJSONParser,
    JSONSecurityError,
    JSONBombError,
    JSONDepthError,
    JSONSizeError,
    JSONSecurityConfig,
    secure_json_loads,
    configure_json_security
)

# Backward compatibility - try to import legacy components if they exist
try:
    from .input_validation import (
        SQLSecurityValidator,
        ProtocolMessageValidator,
        ResourceProtection,
        SecurityValidationError,
        SecurityViolation,
        AttackType
    )
    
    _legacy_available = True
except ImportError:
    # Legacy components not available
    _legacy_available = False

if _legacy_available:
    __all__ = [
        # New JSON security components
        'SecureJSONParser',
        'JSONSecurityError', 
        'JSONBombError',
        'JSONDepthError',
        'JSONSizeError',
        'JSONSecurityConfig',
        'secure_json_loads',
        'configure_json_security',
        
        # Legacy components
        'SQLSecurityValidator',
        'ProtocolMessageValidator', 
        'ResourceProtection',
        'SecurityValidationError',
        'SecurityViolation',
        'AttackType'
    ]
else:
    __all__ = [
        # New JSON security components
        'SecureJSONParser',
        'JSONSecurityError', 
        'JSONBombError',
        'JSONDepthError',
        'JSONSizeError',
        'JSONSecurityConfig',
        'secure_json_loads',
        'configure_json_security'
    ]