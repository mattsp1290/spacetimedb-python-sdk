"""
SpacetimeDB Authentication Storage (DEPRECATED)

This module handles storage and retrieval of SpacetimeDB authentication credentials,
including identity tokens and connection details for automatic reconnection.

WARNING: This module is deprecated and will be removed in a future version.
Please use the new `spacetimedb_sdk.auth` package for secure credential storage.

The new package provides:
- Encrypted credential storage using system keyring
- Fallback encrypted file storage
- Secure key derivation
- Migration utilities
- Cross-platform compatibility

Migration example:
    # Old way (deprecated)
    from spacetimedb_sdk.auth_storage import store_credentials, get_credentials
    
    # New way (recommended)
    from spacetimedb_sdk.auth import store_credentials, get_credentials
    
    # Or use migration utility
    from spacetimedb_sdk.auth.migration import migrate_auth_storage
    migrate_auth_storage()
"""

import json
import logging
import os
import threading
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any

# Try to import the new secure storage
try:
    from .auth import SecureAuthStorage, AuthCredentials as SecureAuthCredentials
    from .auth.migration import migrate_auth_storage
    SECURE_STORAGE_AVAILABLE = True
except ImportError:
    SECURE_STORAGE_AVAILABLE = False


# Deprecation warning message
DEPRECATION_MESSAGE = """
The auth_storage module is deprecated and will be removed in a future version.
Please migrate to the new secure auth package:

from spacetimedb_sdk.auth import store_credentials, get_credentials

For automatic migration, run:
from spacetimedb_sdk.auth.migration import migrate_auth_storage
migrate_auth_storage()
"""


def _issue_deprecation_warning():
    """Issue a deprecation warning."""
    warnings.warn(
        DEPRECATION_MESSAGE,
        DeprecationWarning,
        stacklevel=3
    )


class AuthCredentials:
    """
    Represents SpacetimeDB authentication credentials.
    
    DEPRECATED: Use spacetimedb_sdk.auth.AuthCredentials instead.
    """
    
    def __init__(
        self,
        identity: str,
        token: str,
        host: Optional[str] = None,
        database: Optional[str] = None,
        timestamp: Optional[float] = None
    ):
        _issue_deprecation_warning()
        
        self.identity = identity
        self.token = token
        self.host = host
        self.database = database
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert credentials to dictionary for storage."""
        return {
            'identity': self.identity,
            'token': self.token,
            'host': self.host,
            'database': self.database,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthCredentials':
        """Create credentials from dictionary."""
        return cls(
            identity=data['identity'],
            token=data['token'],
            host=data.get('host'),
            database=data.get('database'),
            timestamp=data.get('timestamp', time.time())
        )
    
    @property
    def age_seconds(self) -> float:
        """Get age of credentials in seconds."""
        return time.time() - self.timestamp
    
    def is_expired(self, max_age_hours: float = 24.0) -> bool:
        """Check if credentials are expired."""
        max_age_seconds = max_age_hours * 3600
        return self.age_seconds > max_age_seconds
    
    def __str__(self) -> str:
        return f"AuthCredentials(identity={self.identity[:8]}..., host={self.host}, database={self.database})"


class SpacetimeDBAuthStorage:
    """
    Manages storage and retrieval of SpacetimeDB authentication credentials.
    
    DEPRECATED: Use spacetimedb_sdk.auth.SecureAuthStorage instead.
    
    This class now serves as a wrapper around the secure storage backend
    when available, or falls back to the old plaintext storage for
    backward compatibility.
    """
    
    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        max_credential_age_hours: float = 24.0,
        auto_cleanup: bool = True
    ):
        """
        Initialize authentication storage.
        
        Args:
            storage_dir: Directory for credential storage (default: ~/.spacetimedb)
            max_credential_age_hours: Maximum age of credentials before expiry
            auto_cleanup: Whether to automatically clean up expired credentials
        """
        _issue_deprecation_warning()
        
        self.max_credential_age_hours = max_credential_age_hours
        self.auto_cleanup = auto_cleanup
        
        # Set up storage directory
        if storage_dir is None:
            storage_dir = Path.home() / '.spacetimedb'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        self.credentials_file = self.storage_dir / 'credentials.json'
        
        # Thread safety
        self._lock = threading.RLock()
        
        # In-memory cache
        self._credentials_cache: Dict[str, AuthCredentials] = {}
        self._cache_loaded = False
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.SpacetimeDBAuthStorage")
        
        # Try to use secure storage backend
        self._secure_storage = None
        if SECURE_STORAGE_AVAILABLE:
            try:
                self._secure_storage = SecureAuthStorage(
                    storage_dir=storage_dir,
                    max_credential_age_hours=max_credential_age_hours,
                    auto_cleanup=auto_cleanup
                )
                self.logger.info("Using secure storage backend")
                
                # Attempt automatic migration
                if self.credentials_file.exists():
                    self.logger.info("Attempting automatic migration to secure storage...")
                    try:
                        migration_results = migrate_auth_storage(storage_dir, dry_run=False)
                        if migration_results.get('status') == 'completed':
                            self.logger.info("Automatic migration to secure storage completed")
                        else:
                            self.logger.warning("Automatic migration failed, using plaintext storage")
                            self._secure_storage = None
                    except Exception as e:
                        self.logger.warning(f"Automatic migration failed: {e}, using plaintext storage")
                        self._secure_storage = None
                
            except Exception as e:
                self.logger.warning(f"Failed to initialize secure storage: {e}")
                self._secure_storage = None
    
    def _convert_credentials(self, credentials: Any) -> AuthCredentials:
        """Convert between credential types."""
        if isinstance(credentials, AuthCredentials):
            return credentials
        elif hasattr(credentials, 'to_dict'):
            return AuthCredentials.from_dict(credentials.to_dict())
        else:
            raise ValueError(f"Unknown credentials type: {type(credentials)}")
    
    def _get_credential_key(self, host: str, database: str) -> str:
        """Generate a unique key for host/database combination."""
        return f"{host}:{database}"
    
    def _load_credentials(self) -> None:
        """Load credentials from disk into cache."""
        with self._lock:
            if self._cache_loaded:
                return
            
            try:
                if self.credentials_file.exists():
                    with open(self.credentials_file, 'r') as f:
                        data = json.load(f)
                    
                    # Load each credential
                    for key, cred_data in data.items():
                        try:
                            credentials = AuthCredentials.from_dict(cred_data)
                            
                            # Skip expired credentials if auto_cleanup is enabled
                            if self.auto_cleanup and credentials.is_expired(self.max_credential_age_hours):
                                self.logger.debug(f"Skipping expired credentials for {key}")
                                continue
                            
                            self._credentials_cache[key] = credentials
                        except Exception as e:
                            self.logger.warning(f"Failed to load credentials for {key}: {e}")
                
                self._cache_loaded = True
                self.logger.debug(f"Loaded {len(self._credentials_cache)} credential entries")
                
                # Clean up expired credentials if requested
                if self.auto_cleanup:
                    self._cleanup_expired_credentials()
                    
            except Exception as e:
                self.logger.error(f"Failed to load credentials from {self.credentials_file}: {e}")
                self._cache_loaded = True  # Mark as loaded even on error to prevent repeated attempts
    
    def _save_credentials(self) -> None:
        """Save credentials from cache to disk."""
        with self._lock:
            try:
                # Convert all credentials to dict format
                data = {}
                for key, credentials in self._credentials_cache.items():
                    data[key] = credentials.to_dict()
                
                # Write atomically
                temp_file = self.credentials_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Atomic rename
                temp_file.replace(self.credentials_file)
                
                self.logger.debug(f"Saved {len(data)} credential entries to {self.credentials_file}")
                
            except Exception as e:
                self.logger.error(f"Failed to save credentials to {self.credentials_file}: {e}")
    
    def store_credentials(
        self,
        identity: str,
        token: str,
        host: str,
        database: str
    ) -> None:
        """
        Store authentication credentials.
        
        Args:
            identity: SpacetimeDB identity (hex string)
            token: JWT authentication token
            host: Server host (e.g., "localhost:3000")
            database: Database name
        """
        # Use secure storage if available
        if self._secure_storage:
            try:
                self._secure_storage.store_credentials(identity, token, host, database)
                return
            except Exception as e:
                self.logger.warning(f"Failed to store in secure storage: {e}")
        
        # Fallback to plaintext storage
        with self._lock:
            self._load_credentials()
            
            key = self._get_credential_key(host, database)
            credentials = AuthCredentials(
                identity=identity,
                token=token,
                host=host,
                database=database
            )
            
            self._credentials_cache[key] = credentials
            self._save_credentials()
            
            self.logger.info(f"Stored credentials for {host}/{database} (identity: {identity[:8]}...)")
    
    def get_credentials(
        self,
        host: str,
        database: str,
        allow_expired: bool = False
    ) -> Optional[AuthCredentials]:
        """
        Retrieve authentication credentials.
        
        Args:
            host: Server host
            database: Database name
            allow_expired: Whether to return expired credentials
            
        Returns:
            AuthCredentials if found and valid, None otherwise
        """
        # Use secure storage if available
        if self._secure_storage:
            try:
                secure_creds = self._secure_storage.get_credentials(host, database, allow_expired)
                if secure_creds:
                    return self._convert_credentials(secure_creds)
            except Exception as e:
                self.logger.warning(f"Failed to get from secure storage: {e}")
        
        # Fallback to plaintext storage
        with self._lock:
            self._load_credentials()
            
            key = self._get_credential_key(host, database)
            credentials = self._credentials_cache.get(key)
            
            if credentials is None:
                self.logger.debug(f"No credentials found for {host}/{database}")
                return None
            
            # Check expiration
            if not allow_expired and credentials.is_expired(self.max_credential_age_hours):
                self.logger.debug(f"Credentials for {host}/{database} are expired")
                return None
            
            self.logger.debug(f"Retrieved credentials for {host}/{database} (age: {credentials.age_seconds:.1f}s)")
            return credentials
    
    def remove_credentials(self, host: str, database: str) -> bool:
        """
        Remove stored credentials.
        
        Args:
            host: Server host
            database: Database name
            
        Returns:
            True if credentials were removed, False if not found
        """
        removed = False
        
        # Remove from secure storage if available
        if self._secure_storage:
            try:
                if self._secure_storage.remove_credentials(host, database):
                    removed = True
            except Exception as e:
                self.logger.warning(f"Failed to remove from secure storage: {e}")
        
        # Remove from plaintext storage
        with self._lock:
            self._load_credentials()
            
            key = self._get_credential_key(host, database)
            if key in self._credentials_cache:
                del self._credentials_cache[key]
                self._save_credentials()
                removed = True
        
        if removed:
            self.logger.info(f"Removed credentials for {host}/{database}")
        
        return removed
    
    def clear_all_credentials(self) -> None:
        """Remove all stored credentials."""
        # Clear secure storage if available
        if self._secure_storage:
            try:
                self._secure_storage.clear_all_credentials()
            except Exception as e:
                self.logger.warning(f"Failed to clear secure storage: {e}")
        
        # Clear plaintext storage
        with self._lock:
            self._credentials_cache.clear()
            
            try:
                if self.credentials_file.exists():
                    self.credentials_file.unlink()
                self.logger.info("Cleared all stored credentials")
            except Exception as e:
                self.logger.error(f"Failed to clear credentials file: {e}")
    
    def _cleanup_expired_credentials(self) -> int:
        """
        Remove expired credentials from cache and storage.
        
        Returns:
            Number of expired credentials removed
        """
        with self._lock:
            expired_keys = []
            
            for key, credentials in self._credentials_cache.items():
                if credentials.is_expired(self.max_credential_age_hours):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._credentials_cache[key]
            
            if expired_keys:
                self._save_credentials()
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired credential entries")
            
            return len(expired_keys)
    
    def cleanup_expired_credentials(self) -> int:
        """
        Public method to clean up expired credentials.
        
        Returns:
            Number of expired credentials removed
        """
        total_cleaned = 0
        
        # Clean up secure storage if available
        if self._secure_storage:
            try:
                total_cleaned += self._secure_storage.cleanup_expired_credentials()
            except Exception as e:
                self.logger.warning(f"Failed to cleanup secure storage: {e}")
        
        # Clean up plaintext storage
        self._load_credentials()
        total_cleaned += self._cleanup_expired_credentials()
        
        return total_cleaned
    
    def list_stored_credentials(self) -> Dict[str, Dict[str, Any]]:
        """
        List all stored credentials with metadata.
        
        Returns:
            Dict mapping credential keys to metadata
        """
        result = {}
        
        # Get from secure storage if available
        if self._secure_storage:
            try:
                result.update(self._secure_storage.list_stored_credentials())
            except Exception as e:
                self.logger.warning(f"Failed to list secure storage: {e}")
        
        # Get from plaintext storage
        with self._lock:
            self._load_credentials()
            
            for key, credentials in self._credentials_cache.items():
                if key not in result:  # Don't override secure storage results
                    result[key] = {
                        'host': credentials.host,
                        'database': credentials.database,
                        'identity': credentials.identity,
                        'timestamp': credentials.timestamp,
                        'age_seconds': credentials.age_seconds,
                        'is_expired': credentials.is_expired(self.max_credential_age_hours)
                    }
        
        return result
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get information about the storage system.
        
        Returns:
            Dict with storage metadata
        """
        with self._lock:
            self._load_credentials()
            
            storage_exists = self.credentials_file.exists()
            file_size = self.credentials_file.stat().st_size if storage_exists else 0
            
            info = {
                'storage_dir': str(self.storage_dir),
                'credentials_file': str(self.credentials_file),
                'file_exists': storage_exists,
                'file_size_bytes': file_size,
                'max_credential_age_hours': self.max_credential_age_hours,
                'auto_cleanup': self.auto_cleanup,
                'cached_credentials': len(self._credentials_cache),
                'cache_loaded': self._cache_loaded,
                'using_secure_storage': self._secure_storage is not None,
                'deprecated': True
            }
            
            if self._secure_storage:
                try:
                    secure_info = self._secure_storage.get_storage_info()
                    info['secure_storage_info'] = secure_info
                except Exception as e:
                    info['secure_storage_error'] = str(e)
            
            return info


# Global instance for convenience
_global_auth_storage: Optional[SpacetimeDBAuthStorage] = None
_global_storage_lock = threading.Lock()


def get_global_auth_storage() -> SpacetimeDBAuthStorage:
    """Get the global authentication storage instance."""
    global _global_auth_storage
    
    with _global_storage_lock:
        if _global_auth_storage is None:
            _global_auth_storage = SpacetimeDBAuthStorage()
        
        return _global_auth_storage


def store_credentials(identity: str, token: str, host: str, database: str) -> None:
    """Convenience function to store credentials using global storage."""
    _issue_deprecation_warning()
    storage = get_global_auth_storage()
    storage.store_credentials(identity, token, host, database)


def get_credentials(host: str, database: str, allow_expired: bool = False) -> Optional[AuthCredentials]:
    """Convenience function to get credentials using global storage."""
    _issue_deprecation_warning()
    storage = get_global_auth_storage()
    return storage.get_credentials(host, database, allow_expired)


def remove_credentials(host: str, database: str) -> bool:
    """Convenience function to remove credentials using global storage."""
    _issue_deprecation_warning()
    storage = get_global_auth_storage()
    return storage.remove_credentials(host, database)


def clear_all_credentials() -> None:
    """Convenience function to clear all credentials using global storage."""
    _issue_deprecation_warning()
    storage = get_global_auth_storage()
    storage.clear_all_credentials()