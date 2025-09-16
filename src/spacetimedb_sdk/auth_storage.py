"""
Legacy Auth Storage Module

This module provides backward compatibility for tests and code that expect
the old auth_storage module structure. The functionality has been moved to
the new auth.storage module.
"""

# Import the actual implementations from the new location
from .auth.storage import SecureAuthStorage, AuthCredentials

# Legacy aliases for backward compatibility
AuthenticationStorage = SecureAuthStorage
SpacetimeDBAuthStorage = SecureAuthStorage

__all__ = [
    'AuthenticationStorage',
    'SpacetimeDBAuthStorage', 
    'AuthCredentials',
    'SecureAuthStorage'
]