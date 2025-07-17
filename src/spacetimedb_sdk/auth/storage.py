"""
Secure Authentication Storage for SpacetimeDB

This module provides encrypted storage for authentication credentials using
industry best practices. It supports both system keyring and encrypted file
storage as fallback options.
"""

import json
import logging
import os
import threading
import time
import hashlib
import getpass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

try:
    import keyring
    import keyring.backends
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


class AuthCredentials:
    """
    Represents SpacetimeDB authentication credentials.
    
    This class is compatible with the old auth_storage.py implementation
    but provides additional security features.
    """
    
    def __init__(
        self,
        identity: str,
        token: str,
        host: Optional[str] = None,
        database: Optional[str] = None,
        timestamp: Optional[float] = None
    ):
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


class SecureAuthStorage:
    """
    Secure storage manager for SpacetimeDB authentication credentials.
    
    This class provides encrypted storage using multiple backends:
    1. System keyring (preferred) - uses OS-level credential storage
    2. Encrypted file storage (fallback) - uses PBKDF2 + Fernet encryption
    
    Features:
    - Cross-platform compatibility
    - Secure key derivation
    - Thread-safe operations
    - Automatic cleanup of expired credentials
    - Migration support from plaintext storage
    """
    
    KEYRING_SERVICE_NAME = "spacetimedb-python-sdk"
    SALT_LENGTH = 32
    ITERATIONS = 100000  # PBKDF2 iterations
    
    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        max_credential_age_hours: float = 24.0,
        auto_cleanup: bool = True,
        prefer_keyring: bool = True,
        master_password: Optional[str] = None
    ):
        """
        Initialize secure authentication storage.
        
        Args:
            storage_dir: Directory for credential storage (default: ~/.spacetimedb)
            max_credential_age_hours: Maximum age of credentials before expiry
            auto_cleanup: Whether to automatically clean up expired credentials
            prefer_keyring: Whether to prefer system keyring over file storage
            master_password: Master password for file encryption (prompted if None)
        """
        self.max_credential_age_hours = max_credential_age_hours
        self.auto_cleanup = auto_cleanup
        self.prefer_keyring = prefer_keyring and KEYRING_AVAILABLE
        self.master_password = master_password
        
        # Set up storage directory
        if storage_dir is None:
            storage_dir = Path.home() / '.spacetimedb'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(mode=0o700, exist_ok=True)  # Secure permissions
        
        # File paths
        self.credentials_file = self.storage_dir / 'credentials.enc'
        self.salt_file = self.storage_dir / 'salt'
        self.legacy_file = self.storage_dir / 'credentials.json'
        
        # Thread safety
        self._lock = threading.RLock()
        
        # In-memory cache
        self._credentials_cache: Dict[str, AuthCredentials] = {}
        self._cache_loaded = False
        
        # Encryption
        self._fernet: Optional[Fernet] = None
        self._salt: Optional[bytes] = None
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.SecureAuthStorage")
        
        # Initialize storage backend
        self._init_storage_backend()
    
    def _init_storage_backend(self) -> None:
        """Initialize the storage backend (keyring or encrypted file)."""
        if self.prefer_keyring:
            try:
                # Test keyring availability
                keyring.get_password(self.KEYRING_SERVICE_NAME, "test")
                self.logger.info("Using system keyring for credential storage")
                return
            except Exception as e:
                self.logger.warning(f"Keyring not available, falling back to encrypted file: {e}")
        
        # Initialize encrypted file storage
        self._init_file_encryption()
    
    def _init_file_encryption(self) -> None:
        """Initialize file-based encryption."""
        # Load or generate salt
        if self.salt_file.exists():
            with open(self.salt_file, 'rb') as f:
                self._salt = f.read()
        else:
            self._salt = os.urandom(self.SALT_LENGTH)
            with open(self.salt_file, 'wb') as f:
                f.write(self._salt)
            # Secure file permissions
            os.chmod(self.salt_file, 0o600)
        
        # Get master password
        if self.master_password is None:
            self.master_password = self._get_master_password()
        
        # Derive encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=self.ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_password.encode()))
        self._fernet = Fernet(key)
        
        self.logger.info("Initialized encrypted file storage")
    
    def _get_master_password(self) -> str:
        """Get master password for file encryption."""
        # Try to get from keyring first
        if KEYRING_AVAILABLE:
            try:
                password = keyring.get_password(self.KEYRING_SERVICE_NAME, "master_password")
                if password:
                    return password
            except Exception:
                pass
        
        # Prompt user for password
        password = getpass.getpass("Enter master password for SpacetimeDB credentials: ")
        
        # Store in keyring for future use
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(self.KEYRING_SERVICE_NAME, "master_password", password)
            except Exception:
                pass
        
        return password
    
    def _get_credential_key(self, host: str, database: str) -> str:
        """Generate a unique key for host/database combination."""
        return f"{host}:{database}"
    
    def _store_in_keyring(self, key: str, credentials: AuthCredentials) -> None:
        """Store credentials in system keyring."""
        try:
            data = json.dumps(credentials.to_dict())
            keyring.set_password(self.KEYRING_SERVICE_NAME, key, data)
        except Exception as e:
            self.logger.error(f"Failed to store credentials in keyring: {e}")
            raise
    
    def _get_from_keyring(self, key: str) -> Optional[AuthCredentials]:
        """Get credentials from system keyring."""
        try:
            data = keyring.get_password(self.KEYRING_SERVICE_NAME, key)
            if data:
                return AuthCredentials.from_dict(json.loads(data))
            return None
        except Exception as e:
            self.logger.error(f"Failed to get credentials from keyring: {e}")
            return None
    
    def _remove_from_keyring(self, key: str) -> bool:
        """Remove credentials from system keyring."""
        try:
            keyring.delete_password(self.KEYRING_SERVICE_NAME, key)
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove credentials from keyring: {e}")
            return False
    
    def _load_credentials_from_file(self) -> Dict[str, AuthCredentials]:
        """Load credentials from encrypted file."""
        if not self.credentials_file.exists():
            return {}
        
        try:
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode())
            
            credentials = {}
            for key, cred_data in data.items():
                try:
                    credentials[key] = AuthCredentials.from_dict(cred_data)
                except Exception as e:
                    self.logger.warning(f"Failed to load credentials for {key}: {e}")
            
            return credentials
        except Exception as e:
            self.logger.error(f"Failed to load credentials from file: {e}")
            return {}
    
    def _save_credentials_to_file(self, credentials: Dict[str, AuthCredentials]) -> None:
        """Save credentials to encrypted file."""
        try:
            # Convert to dict format
            data = {}
            for key, cred in credentials.items():
                data[key] = cred.to_dict()
            
            # Encrypt and save
            plaintext = json.dumps(data, indent=2).encode()
            encrypted_data = self._fernet.encrypt(plaintext)
            
            # Write atomically
            temp_file = self.credentials_file.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Secure file permissions
            os.chmod(temp_file, 0o600)
            
            # Atomic rename
            temp_file.replace(self.credentials_file)
            
        except Exception as e:
            self.logger.error(f"Failed to save credentials to file: {e}")
            raise
    
    def _load_credentials(self) -> None:
        """Load credentials from storage into cache."""
        with self._lock:
            if self._cache_loaded:
                return
            
            try:
                if self.prefer_keyring:
                    # For keyring, we need to load all stored keys
                    # This is a limitation - we'd need to store an index
                    # For now, we'll also maintain file storage as backup
                    pass
                
                # Load from encrypted file
                if not self.prefer_keyring or not KEYRING_AVAILABLE:
                    self._credentials_cache = self._load_credentials_from_file()
                
                # Clean up expired credentials if requested
                if self.auto_cleanup:
                    self._cleanup_expired_credentials()
                
                self._cache_loaded = True
                self.logger.debug(f"Loaded {len(self._credentials_cache)} credential entries")
                
            except Exception as e:
                self.logger.error(f"Failed to load credentials: {e}")
                self._cache_loaded = True
    
    def store_credentials(
        self,
        identity: str,
        token: str,
        host: str,
        database: str
    ) -> None:
        """
        Store authentication credentials securely.
        
        Args:
            identity: SpacetimeDB identity (hex string)
            token: JWT authentication token
            host: Server host (e.g., "localhost:3000")
            database: Database name
        """
        with self._lock:
            self._load_credentials()
            
            key = self._get_credential_key(host, database)
            credentials = AuthCredentials(
                identity=identity,
                token=token,
                host=host,
                database=database
            )
            
            # Store in cache
            self._credentials_cache[key] = credentials
            
            # Store in backend
            if self.prefer_keyring:
                self._store_in_keyring(key, credentials)
            else:
                self._save_credentials_to_file(self._credentials_cache)
            
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
        with self._lock:
            self._load_credentials()
            
            key = self._get_credential_key(host, database)
            
            # Try cache first
            credentials = self._credentials_cache.get(key)
            
            # Try keyring if not in cache
            if credentials is None and self.prefer_keyring:
                credentials = self._get_from_keyring(key)
                if credentials:
                    self._credentials_cache[key] = credentials
            
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
        with self._lock:
            self._load_credentials()
            
            key = self._get_credential_key(host, database)
            removed = False
            
            # Remove from cache
            if key in self._credentials_cache:
                del self._credentials_cache[key]
                removed = True
            
            # Remove from backend
            if self.prefer_keyring:
                if self._remove_from_keyring(key):
                    removed = True
            else:
                if removed:
                    self._save_credentials_to_file(self._credentials_cache)
            
            if removed:
                self.logger.info(f"Removed credentials for {host}/{database}")
            
            return removed
    
    def clear_all_credentials(self) -> None:
        """Remove all stored credentials."""
        with self._lock:
            self._credentials_cache.clear()
            
            try:
                # Clear file storage
                if self.credentials_file.exists():
                    self.credentials_file.unlink()
                
                # Clear keyring (this is limited without an index)
                if self.prefer_keyring:
                    # We'd need to maintain an index of stored keys
                    # For now, we'll clear what we can
                    pass
                
                self.logger.info("Cleared all stored credentials")
            except Exception as e:
                self.logger.error(f"Failed to clear credentials: {e}")
    
    def _cleanup_expired_credentials(self) -> int:
        """Remove expired credentials from cache and storage."""
        with self._lock:
            expired_keys = []
            
            for key, credentials in self._credentials_cache.items():
                if credentials.is_expired(self.max_credential_age_hours):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._credentials_cache[key]
                if self.prefer_keyring:
                    self._remove_from_keyring(key)
            
            if expired_keys and not self.prefer_keyring:
                self._save_credentials_to_file(self._credentials_cache)
            
            if expired_keys:
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired credential entries")
            
            return len(expired_keys)
    
    def cleanup_expired_credentials(self) -> int:
        """Public method to clean up expired credentials."""
        self._load_credentials()
        return self._cleanup_expired_credentials()
    
    def list_stored_credentials(self) -> Dict[str, Dict[str, Any]]:
        """List all stored credentials with metadata."""
        with self._lock:
            self._load_credentials()
            
            result = {}
            for key, credentials in self._credentials_cache.items():
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
        """Get information about the storage system."""
        with self._lock:
            self._load_credentials()
            
            return {
                'storage_dir': str(self.storage_dir),
                'credentials_file': str(self.credentials_file),
                'keyring_available': KEYRING_AVAILABLE,
                'using_keyring': self.prefer_keyring,
                'file_exists': self.credentials_file.exists(),
                'max_credential_age_hours': self.max_credential_age_hours,
                'auto_cleanup': self.auto_cleanup,
                'cached_credentials': len(self._credentials_cache),
                'cache_loaded': self._cache_loaded
            }
    
    def migrate_from_plaintext(self, plaintext_file: Optional[Path] = None) -> int:
        """
        Migrate credentials from plaintext storage to encrypted storage.
        
        Args:
            plaintext_file: Path to plaintext credentials file (default: legacy location)
            
        Returns:
            Number of credentials migrated
        """
        if plaintext_file is None:
            plaintext_file = self.legacy_file
        
        if not plaintext_file.exists():
            self.logger.info("No plaintext credentials file found to migrate")
            return 0
        
        try:
            with open(plaintext_file, 'r') as f:
                data = json.load(f)
            
            migrated = 0
            for key, cred_data in data.items():
                try:
                    credentials = AuthCredentials.from_dict(cred_data)
                    
                    # Store in new secure format
                    if credentials.host and credentials.database:
                        self.store_credentials(
                            credentials.identity,
                            credentials.token,
                            credentials.host,
                            credentials.database
                        )
                        migrated += 1
                except Exception as e:
                    self.logger.warning(f"Failed to migrate credentials for {key}: {e}")
            
            self.logger.info(f"Migrated {migrated} credentials from plaintext storage")
            
            # Backup and remove plaintext file
            if migrated > 0:
                backup_file = plaintext_file.with_suffix('.backup')
                plaintext_file.rename(backup_file)
                self.logger.info(f"Backed up plaintext file to {backup_file}")
            
            return migrated
            
        except Exception as e:
            self.logger.error(f"Failed to migrate from plaintext: {e}")
            return 0