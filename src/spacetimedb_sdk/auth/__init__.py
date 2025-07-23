"""
SpacetimeDB Authentication Package

This package provides secure authentication and credential storage for SpacetimeDB.
It replaces the old auth_storage.py with encrypted storage capabilities.

Features:
- Encrypted credential storage using system keyring
- Fallback encrypted file storage for systems without keyring
- Secure key derivation and password protection
- Migration utilities for existing plaintext credentials
- Cross-platform compatibility
"""

from .storage import SecureAuthStorage, AuthCredentials, AuthStorage
from .providers import AuthProvider, JWTAuthProvider, IdentityAuthProvider
from .validators import TokenValidator, CredentialsValidator

# For backward compatibility
from .storage import SecureAuthStorage as SpacetimeDBAuthStorage

# Global instance for convenience
_global_auth_storage = None


def get_global_auth_storage():
    """Get the global secure authentication storage instance."""
    global _global_auth_storage
    if _global_auth_storage is None:
        _global_auth_storage = SecureAuthStorage()
    return _global_auth_storage


def store_credentials(identity: str, token: str, host: str, database: str) -> None:
    """Convenience function to store credentials using global storage."""
    storage = get_global_auth_storage()
    storage.store_credentials(identity, token, host, database)


def get_credentials(host: str, database: str, allow_expired: bool = False):
    """Convenience function to get credentials using global storage."""
    storage = get_global_auth_storage()
    return storage.get_credentials(host, database, allow_expired)


def remove_credentials(host: str, database: str) -> bool:
    """Convenience function to remove credentials using global storage."""
    storage = get_global_auth_storage()
    return storage.remove_credentials(host, database)


def clear_all_credentials() -> None:
    """Convenience function to clear all credentials using global storage."""
    storage = get_global_auth_storage()
    storage.clear_all_credentials()


# Backward compatibility aliases
SpacetimeDBAuthStorage = SecureAuthStorage

__all__ = [
    'SecureAuthStorage',
    'AuthStorage',  # Legacy compatibility
    'SpacetimeDBAuthStorage',  # Backward compatibility
    'AuthCredentials',
    'AuthProvider',
    'JWTAuthProvider',
    'IdentityAuthProvider',
    'TokenValidator',
    'CredentialsValidator',
    'get_global_auth_storage',
    'store_credentials',
    'get_credentials',
    'remove_credentials',
    'clear_all_credentials',
]