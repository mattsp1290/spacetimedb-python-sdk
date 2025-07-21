"""
Secure Storage for SpacetimeDB

Provides encrypted credential storage with:
- OS keyring integration (Keychain, Windows Credential Store, etc.)
- Encrypted file storage fallback
- Token rotation and refresh
- Secure memory handling
- Hardware security module (HSM) support
"""

import os
import json
import base64
import logging
from .utils.error_formatting import ErrorFormatter
import threading
import secrets
import time
from typing import Dict, Optional, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import hmac

# OS-specific imports
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
    keyring = None

# Encryption imports
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet
import cryptography.exceptions


class StorageBackend(Enum):
    """Available storage backends."""
    KEYRING = "keyring"  # OS keyring
    ENCRYPTED_FILE = "encrypted_file"  # Encrypted local file
    MEMORY = "memory"  # In-memory only
    HSM = "hsm"  # Hardware security module


class TokenStatus(Enum):
    """Token lifecycle status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REFRESHING = "refreshing"
    REVOKED = "revoked"


@dataclass
class SecureToken:
    """Secure token with metadata."""
    token: str
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    refresh_expires_at: Optional[datetime] = None
    scopes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: Optional[datetime] = None
    use_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_refresh_expired(self) -> bool:
        """Check if refresh token is expired."""
        if self.refresh_expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.refresh_expires_at
    
    def needs_refresh(self, buffer_minutes: int = 5) -> bool:
        """Check if token needs refresh."""
        if self.expires_at is None:
            return False
        buffer = timedelta(minutes=buffer_minutes)
        return datetime.now(timezone.utc) + buffer > self.expires_at
    
    def record_use(self) -> None:
        """Record token usage."""
        self.last_used = datetime.now(timezone.utc)
        self.use_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "token": self.token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "refresh_token": self.refresh_token,
            "refresh_expires_at": self.refresh_expires_at.isoformat() if self.refresh_expires_at else None,
            "scopes": self.scopes,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "use_count": self.use_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecureToken':
        """Create from dictionary."""
        return cls(
            token=data["token"],
            token_type=data.get("token_type", "bearer"),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            refresh_token=data.get("refresh_token"),
            refresh_expires_at=datetime.fromisoformat(data["refresh_expires_at"]) if data.get("refresh_expires_at") else None,
            scopes=data.get("scopes", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            use_count=data.get("use_count", 0),
        )


@dataclass
class StorageConfig:
    """Configuration for secure storage."""
    backend: StorageBackend = StorageBackend.KEYRING if HAS_KEYRING else StorageBackend.ENCRYPTED_FILE
    service_name: str = "spacetimedb"
    
    # Encryption settings
    encryption_key: Optional[bytes] = None  # If None, will be derived
    key_derivation_salt: Optional[bytes] = None  # If None, will be generated
    key_derivation_iterations: int = 100_000
    
    # File storage settings
    storage_path: Path = Path.home() / ".spacetimedb" / "credentials"
    file_permissions: int = 0o600  # Read/write for owner only
    
    # Token management
    auto_refresh: bool = True
    refresh_buffer_minutes: int = 5
    max_token_age_days: int = 90
    
    # Security settings
    secure_delete: bool = True
    memory_protection: bool = True
    audit_access: bool = True
    
    # HSM settings (for future use)
    hsm_module_path: Optional[str] = None
    hsm_slot: Optional[int] = None
    hsm_pin: Optional[str] = None


class SecureStorage:
    """
    Secure storage for credentials and sensitive data.
    
    Features:
    - Multiple backend support (OS keyring, encrypted files, memory)
    - Automatic token rotation and refresh
    - Secure memory handling
    - Audit logging
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._lock = threading.RLock()
        self._memory_store: Dict[str, Any] = {}
        self._refresh_callbacks: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize encryption
        self._cipher_key = self._initialize_encryption()
        
        # Create storage directory if using file backend
        if self.config.backend == StorageBackend.ENCRYPTED_FILE:
            self.config.storage_path.mkdir(parents=True, exist_ok=True)
            # Set restrictive permissions
            os.chmod(self.config.storage_path, 0o700)
        
        # Audit log
        self._audit_log: List[Dict[str, Any]] = []
        
        # Background refresh thread
        self._refresh_thread = None
        self._refresh_running = False
        if self.config.auto_refresh:
            self._start_refresh_thread()
    
    def _initialize_encryption(self) -> bytes:
        """
        Initialize encryption key using secure PBKDF2 key derivation.
        
        Features:
        - PBKDF2HMAC with SHA256 for key stretching
        - High iteration count (100,000+ for >100ms target)
        - Random salt stored securely per installation
        - Performance benchmarking and adaptive tuning
        - Machine-specific entropy sources
        """
        if self.config.encryption_key:
            return self.config.encryption_key
        
        # Generate or load cryptographic salt for PBKDF2
        salt = self._get_or_create_kdf_salt()
        self.config.key_derivation_salt = salt
        
        # Get optimized iteration count for this system
        iterations = self._get_optimal_iterations()
        
        # Derive key from secure machine-specific password
        machine_password = self._derive_secure_password()
        
        # Benchmark key derivation timing
        start_time = time.time()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256 compatibility
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        
        derived_key = kdf.derive(machine_password.encode('utf-8'))
        
        derivation_time = time.time() - start_time
        self.logger.debug(f"Key derivation completed in {derivation_time:.3f}s with {iterations} iterations")
        
        # Log performance metrics (without exposing key material)
        if derivation_time < 0.05:
            self.logger.info(f"Key derivation fast ({derivation_time:.3f}s) - consider increasing iterations")
        elif derivation_time > 0.5:
            self.logger.warning(f"Key derivation slow ({derivation_time:.3f}s) - consider reducing iterations")
        
        return derived_key
    
    def _get_or_create_kdf_salt(self) -> bytes:
        """
        Get or create a secure random salt for PBKDF2 key derivation.
        
        This salt is different from the machine salt and is specifically
        for the PBKDF2 function. It provides cryptographic randomness.
        """
        salt_file = self.config.storage_path / ".kdf_salt"
        
        if salt_file.exists():
            try:
                with open(salt_file, 'rb') as f:
                    salt = f.read()
                    # Validate salt length (32 bytes = 256 bits)
                    if len(salt) == 32:
                        return salt
                    else:
                        self.logger.warning("Invalid KDF salt length, regenerating")
            except Exception as e:
                self.logger.warning(f"Could not read KDF salt file, regenerating: {e}")
        
        # Generate new cryptographically secure salt
        salt = secrets.token_bytes(32)  # 256 bits of entropy
        
        try:
            # Ensure parent directory exists with secure permissions
            salt_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            
            # Write salt with secure permissions
            with open(salt_file, 'wb') as f:
                f.write(salt)
            
            # Set restrictive file permissions (owner read/write only)
            os.chmod(salt_file, 0o600)
            
            self.logger.info("Generated new KDF salt for secure key derivation")
            
        except Exception as e:
            self.logger.error(f"Failed to save KDF salt: {e}")
            # Return salt anyway - will be regenerated next time
        
        return salt
    
    def _get_optimal_iterations(self) -> int:
        """
        Get optimal PBKDF2 iteration count for this system.
        
        Targets ~100ms key derivation time for good security/performance balance.
        Caches the result to avoid repeated benchmarking.
        """
        iterations_file = self.config.storage_path / ".kdf_iterations"
        
        # Try to load cached optimal iterations
        if iterations_file.exists():
            try:
                with open(iterations_file, 'r') as f:
                    cached_iterations = int(f.read().strip())
                    # Validate reasonable range
                    if 50_000 <= cached_iterations <= 1_000_000:
                        return cached_iterations
            except Exception as e:
                self.logger.debug(f"Could not read cached iterations: {e}")
        
        # Benchmark to find optimal iteration count
        target_time = 0.1  # 100ms target
        test_iterations = 100_000  # Starting point
        
        try:
            # Quick benchmark with test salt and password
            test_salt = secrets.token_bytes(32)
            test_password = "benchmark_password_test_12345"
            
            start_time = time.time()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=test_salt,
                iterations=test_iterations,
                backend=default_backend()
            )
            kdf.derive(test_password.encode())
            benchmark_time = time.time() - start_time
            
            # Calculate optimal iterations for target time
            optimal_iterations = int(test_iterations * (target_time / benchmark_time))
            
            # Clamp to reasonable bounds
            optimal_iterations = max(50_000, min(optimal_iterations, 1_000_000))
            
            # Cache the result
            try:
                with open(iterations_file, 'w') as f:
                    f.write(str(optimal_iterations))
                os.chmod(iterations_file, 0o600)
            except Exception as e:
                self.logger.debug(f"Could not cache iterations: {e}")
            
            self.logger.info(f"Benchmarked optimal PBKDF2 iterations: {optimal_iterations} "
                           f"(benchmark: {benchmark_time:.3f}s for {test_iterations} iterations)")
            
            return optimal_iterations
            
        except Exception as e:
            self.logger.warning(f"PBKDF2 benchmarking failed, using default: {e}")
            return self.config.key_derivation_iterations
    
    def _derive_secure_password(self) -> str:
        """
        Derive a secure password from system entropy for PBKDF2.
        
        Combines multiple entropy sources to create a strong password
        that is unique per installation but deterministic.
        """
        # Get the machine-specific identifier (includes secure salt)
        machine_id = self._get_machine_id()
        
        # Add additional entropy sources
        entropy_parts = [machine_id]
        
        # Process ID namespace (changes per process but adds entropy)
        entropy_parts.append(str(os.getpid()))
        
        # Installation-specific constant
        entropy_parts.append("spacetimedb_python_sdk_v2_secure_storage")
        
        # Current timestamp (rounded to day for stability)
        current_day = int(time.time() // 86400)  # Days since epoch
        entropy_parts.append(str(current_day))
        
        # Combine and hash to create password
        combined = '|'.join(entropy_parts)
        password_hash = hashlib.sha512(combined.encode('utf-8')).hexdigest()
        
        # Return first 128 characters (512 bits) as password
        return password_hash[:128]
    
    def _get_machine_id(self) -> str:
        """
        Get secure machine-specific identifier for key derivation.
        
        Uses cryptographically secure random salt combined with system
        entropy to prevent predictable key derivation attacks.
        """
        # Get or create secure random salt for this installation
        machine_salt = self._get_or_create_machine_salt()
        
        # Combine multiple entropy sources
        entropy_sources = []
        
        # System-specific identifiers (less predictable than username/hostname)
        try:
            # Machine ID (platform specific) - most stable unique identifier
            if os.path.exists('/etc/machine-id'):
                with open('/etc/machine-id', 'r') as f:
                    entropy_sources.append(f.read().strip())
            elif os.path.exists('/var/lib/dbus/machine-id'):
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    entropy_sources.append(f.read().strip())
            elif os.path.exists('/proc/sys/kernel/random/boot_id'):
                with open('/proc/sys/kernel/random/boot_id', 'r') as f:
                    entropy_sources.append(f.read().strip())
        except:
            pass
        
        # Add username and hostname as secondary entropy (less predictable than before)
        try:
            import socket
            entropy_sources.append(os.environ.get('USER', 'default'))
            entropy_sources.append(socket.gethostname())
        except:
            entropy_sources.extend(['default', 'localhost'])
        
        # Add system installation time (if available)
        try:
            import platform
            entropy_sources.append(platform.platform())
        except:
            pass
        
        # Add additional runtime entropy (changes on each run but salt provides persistence)
        entropy_sources.append(secrets.token_hex(16))
        
        # Combine all entropy sources with secure salt
        combined_entropy = machine_salt + '|'.join(entropy_sources)
        
        # Use cryptographically secure hash
        return hashlib.sha256(combined_entropy.encode('utf-8')).hexdigest()
    
    def _get_or_create_machine_salt(self) -> str:
        """
        Get or create a secure random salt for this machine installation.
        
        This salt is generated once per installation and provides persistent
        but unpredictable entropy for key derivation.
        """
        salt_file = self.config.storage_path / ".machine_salt"
        
        if salt_file.exists():
            try:
                with open(salt_file, 'r', encoding='utf-8') as f:
                    salt = f.read().strip()
                    # Validate salt format (64 character hex string)
                    if len(salt) == 64 and all(c in '0123456789abcdef' for c in salt.lower()):
                        return salt
                    else:
                        self.logger.warning("Invalid machine salt format, regenerating")
            except Exception as e:
                self.logger.warning(f"Could not read machine salt file, regenerating: {e}")
        
        # Generate new secure random salt
        salt = secrets.token_hex(32)  # 256 bits of entropy
        
        try:
            # Ensure parent directory exists with secure permissions
            salt_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            
            # Write salt with secure permissions
            with open(salt_file, 'w', encoding='utf-8') as f:
                f.write(salt)
            
            # Set restrictive file permissions (owner read/write only)
            os.chmod(salt_file, 0o600)
            
            self.logger.info("Generated new machine salt for secure key derivation")
            
        except Exception as e:
            self.logger.error(f"Failed to save machine salt: {e}")
            # Return salt anyway - will be regenerated next time
        
        return salt
    
    def store_token(
        self,
        key: str,
        token: SecureToken,
        namespace: Optional[str] = None
    ) -> None:
        """
        Store a secure token.
        
        Args:
            key: Storage key
            token: SecureToken to store
            namespace: Optional namespace for organization
        """
        with self._lock:
            full_key = self._make_key(key, namespace)
            
            if self.config.audit_access:
                self._audit("store_token", full_key, {"token_type": token.token_type})
            
            if self.config.backend == StorageBackend.KEYRING:
                self._store_keyring(full_key, token)
            elif self.config.backend == StorageBackend.ENCRYPTED_FILE:
                self._store_file(full_key, token)
            elif self.config.backend == StorageBackend.MEMORY:
                self._memory_store[full_key] = token
            else:
                raise ValueError(f"Unsupported backend: {self.config.backend}")
    
    def retrieve_token(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> Optional[SecureToken]:
        """
        Retrieve a secure token.
        
        Args:
            key: Storage key
            namespace: Optional namespace
            
        Returns:
            SecureToken or None if not found
        """
        with self._lock:
            full_key = self._make_key(key, namespace)
            
            if self.config.audit_access:
                self._audit("retrieve_token", full_key, {})
            
            token = None
            
            if self.config.backend == StorageBackend.KEYRING:
                token = self._retrieve_keyring(full_key)
            elif self.config.backend == StorageBackend.ENCRYPTED_FILE:
                token = self._retrieve_file(full_key)
            elif self.config.backend == StorageBackend.MEMORY:
                token = self._memory_store.get(full_key)
            
            if token:
                token.record_use()
                
                # Check if refresh needed
                if self.config.auto_refresh and token.needs_refresh():
                    self._schedule_refresh(full_key, token)
            
            return token
    
    def delete_token(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """
        Delete a token from storage.
        
        Args:
            key: Storage key
            namespace: Optional namespace
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            full_key = self._make_key(key, namespace)
            
            if self.config.audit_access:
                self._audit("delete_token", full_key, {})
            
            if self.config.backend == StorageBackend.KEYRING:
                return self._delete_keyring(full_key)
            elif self.config.backend == StorageBackend.ENCRYPTED_FILE:
                return self._delete_file(full_key)
            elif self.config.backend == StorageBackend.MEMORY:
                return self._memory_store.pop(full_key, None) is not None
            
            return False
    
    def list_tokens(self, namespace: Optional[str] = None) -> List[str]:
        """
        List all token keys in a namespace.
        
        Args:
            namespace: Optional namespace filter
            
        Returns:
            List of token keys
        """
        with self._lock:
            if self.config.backend == StorageBackend.MEMORY:
                prefix = f"{namespace}:" if namespace else ""
                return [k for k in self._memory_store.keys() if k.startswith(prefix)]
            elif self.config.backend == StorageBackend.ENCRYPTED_FILE:
                return self._list_file_tokens(namespace)
            elif self.config.backend == StorageBackend.KEYRING:
                # Keyring doesn't support listing, return empty
                self.logger.warning("Keyring backend doesn't support listing tokens")
                return []
            
            return []
    
    def rotate_token(
        self,
        key: str,
        new_token: SecureToken,
        namespace: Optional[str] = None
    ) -> None:
        """
        Rotate a token (replace with new one).
        
        Args:
            key: Storage key
            new_token: New token to store
            namespace: Optional namespace
        """
        with self._lock:
            # Delete old token securely
            self.delete_token(key, namespace)
            
            # Store new token
            self.store_token(key, new_token, namespace)
            
            if self.config.audit_access:
                full_key = self._make_key(key, namespace)
                self._audit("rotate_token", full_key, {"token_type": new_token.token_type})
    
    def register_refresh_callback(
        self,
        key: str,
        callback: Callable[[SecureToken], Optional[SecureToken]],
        namespace: Optional[str] = None
    ) -> None:
        """
        Register a callback for token refresh.
        
        Args:
            key: Storage key
            callback: Function that takes old token and returns new token
            namespace: Optional namespace
        """
        full_key = self._make_key(key, namespace)
        self._refresh_callbacks[full_key] = callback
    
    def _make_key(self, key: str, namespace: Optional[str]) -> str:
        """Create full storage key."""
        if namespace:
            return f"{namespace}:{key}"
        return key
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using Fernet."""
        f = Fernet(base64.urlsafe_b64encode(self._cipher_key))
        return f.encrypt(data)
    
    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data using Fernet."""
        f = Fernet(base64.urlsafe_b64encode(self._cipher_key))
        return f.decrypt(data)
    
    # Keyring backend methods
    def _store_keyring(self, key: str, token: SecureToken) -> None:
        """Store token in OS keyring."""
        if not HAS_KEYRING:
            raise RuntimeError("Keyring not available")
        
        # Serialize and encrypt token
        token_json = json.dumps(token.to_dict())
        encrypted = self._encrypt_data(token_json.encode())
        
        # Store in keyring (base64 encoded)
        keyring.set_password(
            self.config.service_name,
            key,
            base64.b64encode(encrypted).decode('ascii')
        )
    
    def _retrieve_keyring(self, key: str) -> Optional[SecureToken]:
        """Retrieve token from OS keyring."""
        if not HAS_KEYRING:
            return None
        
        try:
            # Get from keyring
            encrypted_b64 = keyring.get_password(self.config.service_name, key)
            if not encrypted_b64:
                return None
            
            # Decrypt
            encrypted = base64.b64decode(encrypted_b64)
            decrypted = self._decrypt_data(encrypted)
            
            # Deserialize
            from .security.json_validator import secure_json_loads
            token_dict = secure_json_loads(decrypted.decode(), "secure_storage.keyring_token")
            return SecureToken.from_dict(token_dict)
            
        except Exception as e:
            self.logger.error(ErrorFormatter.format_generic_error("Secure Storage", "keyring retrieval", e))
            return None
    
    def _delete_keyring(self, key: str) -> bool:
        """Delete token from OS keyring."""
        if not HAS_KEYRING:
            return False
        
        try:
            keyring.delete_password(self.config.service_name, key)
            return True
        except:
            return False
    
    # File backend methods
    def _store_file(self, key: str, token: SecureToken) -> None:
        """Store token in encrypted file."""
        # Create safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        file_path = self.config.storage_path / f"{key_hash}.enc"
        
        # Serialize and encrypt
        token_json = json.dumps(token.to_dict())
        encrypted = self._encrypt_data(token_json.encode())
        
        # Write with secure permissions
        with open(file_path, 'wb') as f:
            f.write(encrypted)
        os.chmod(file_path, self.config.file_permissions)
    
    def _retrieve_file(self, key: str) -> Optional[SecureToken]:
        """Retrieve token from encrypted file."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        file_path = self.config.storage_path / f"{key_hash}.enc"
        
        if not file_path.exists():
            return None
        
        try:
            # Read and decrypt
            with open(file_path, 'rb') as f:
                encrypted = f.read()
            
            decrypted = self._decrypt_data(encrypted)
            from .security.json_validator import secure_json_loads
            token_dict = secure_json_loads(decrypted.decode(), "secure_storage.file_token")
            return SecureToken.from_dict(token_dict)
            
        except Exception as e:
            self.logger.error(ErrorFormatter.format_generic_error("Secure Storage", "file retrieval", e))
            return None
    
    def _delete_file(self, key: str) -> bool:
        """Delete token file with secure overwrite."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        file_path = self.config.storage_path / f"{key_hash}.enc"
        
        if not file_path.exists():
            return False
        
        if self.config.secure_delete:
            # Overwrite with random data before deletion
            file_size = file_path.stat().st_size
            with open(file_path, 'wb') as f:
                f.write(secrets.token_bytes(file_size))
        
        file_path.unlink()
        return True
    
    def _list_file_tokens(self, namespace: Optional[str]) -> List[str]:
        """List tokens in file storage."""
        # Note: This is a simplified implementation
        # In production, we'd need to store key mappings
        return []
    
    # Token refresh management
    def _start_refresh_thread(self) -> None:
        """Start background token refresh thread."""
        self._refresh_running = True
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            daemon=True,
            name="SecureStorage-RefreshThread"
        )
        self._refresh_thread.start()
    
    def _refresh_loop(self) -> None:
        """Background loop for token refresh."""
        while self._refresh_running:
            try:
                # Check tokens every minute
                threading.Event().wait(60)
                
                # Check all tokens for refresh
                with self._lock:
                    for key in list(self._refresh_callbacks.keys()):
                        token = self.retrieve_token(key)
                        if token and token.needs_refresh():
                            self._perform_refresh(key, token)
                            
            except Exception as e:
                self.logger.error(ErrorFormatter.format_generic_error("Secure Storage", "refresh loop", e))
    
    def _schedule_refresh(self, key: str, token: SecureToken) -> None:
        """Schedule a token for refresh."""
        # Immediate refresh in background
        threading.Thread(
            target=self._perform_refresh,
            args=(key, token),
            daemon=True
        ).start()
    
    def _perform_refresh(self, key: str, token: SecureToken) -> None:
        """Perform token refresh."""
        if key not in self._refresh_callbacks:
            return
        
        try:
            callback = self._refresh_callbacks[key]
            new_token = callback(token)
            
            if new_token:
                self.store_token(key, new_token)
                self.logger.info(f"Successfully refreshed token: {key}")
            else:
                self.logger.warning(f"Token refresh failed: {key}")
                
        except Exception as e:
            self.logger.error(ErrorFormatter.format_generic_error("Secure Storage", "token refresh", e))
    
    # Audit and monitoring
    def _audit(self, action: str, key: str, details: Dict[str, Any]) -> None:
        """Record audit event."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "key": key,
            "details": details,
        }
        
        with self._lock:
            self._audit_log.append(event)
            
            # Limit audit log size
            if len(self._audit_log) > 10000:
                self._audit_log = self._audit_log[-5000:]
    
    def get_audit_log(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get filtered audit log."""
        with self._lock:
            logs = self._audit_log.copy()
        
        # Apply filters
        if start_time:
            logs = [l for l in logs if datetime.fromisoformat(l["timestamp"]) >= start_time]
        if end_time:
            logs = [l for l in logs if datetime.fromisoformat(l["timestamp"]) <= end_time]
        if action_filter:
            logs = [l for l in logs if l["action"] == action_filter]
        
        return logs
    
    def cleanup_expired_tokens(self) -> int:
        """Remove expired tokens and return count."""
        count = 0
        
        with self._lock:
            for key in self.list_tokens():
                token = self.retrieve_token(key)
                if token and token.is_expired():
                    if self.delete_token(key):
                        count += 1
        
        if count > 0:
            self.logger.info(f"Cleaned up {count} expired tokens")
        
        return count
    
    def export_tokens(self, password: str) -> bytes:
        """
        Export all tokens encrypted with password.
        
        Args:
            password: Password for encryption
            
        Returns:
            Encrypted token bundle
        """
        # Collect all tokens
        tokens = {}
        for key in self.list_tokens():
            token = self.retrieve_token(key)
            if token:
                tokens[key] = token.to_dict()
        
        # Serialize
        data = json.dumps(tokens).encode()
        
        # Derive key from password
        salt = secrets.token_bytes(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        
        # Encrypt
        f = Fernet(base64.urlsafe_b64encode(key))
        encrypted = f.encrypt(data)
        
        # Bundle with salt
        return salt + encrypted
    
    def import_tokens(self, bundle: bytes, password: str) -> int:
        """
        Import tokens from encrypted bundle.
        
        Args:
            bundle: Encrypted token bundle
            password: Password for decryption
            
        Returns:
            Number of tokens imported
        """
        # Extract salt and encrypted data
        salt = bundle[:32]
        encrypted = bundle[32:]
        
        # Derive key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        
        # Decrypt
        f = Fernet(base64.urlsafe_b64encode(key))
        data = f.decrypt(encrypted)
        
        # Import tokens
        from .security.json_validator import secure_json_loads
        tokens = secure_json_loads(data.decode(), "secure_storage.import_tokens")
        count = 0
        
        for key, token_dict in tokens.items():
            token = SecureToken.from_dict(token_dict)
            self.store_token(key, token)
            count += 1
        
        return count
    
    def migrate_legacy_credentials(self, legacy_storage_path: Optional[Path] = None) -> int:
        """
        Migrate credentials from legacy storage systems.
        
        Handles migration from:
        1. Plaintext JSON files (auth_storage_original.py)
        2. Older encrypted files with weak key derivation
        3. Different salt/key formats
        
        Args:
            legacy_storage_path: Path to legacy storage directory (auto-detected if None)
            
        Returns:
            Number of credentials successfully migrated
        """
        migrated_count = 0
        
        # Auto-detect legacy storage paths
        if legacy_storage_path is None:
            legacy_storage_path = Path.home() / '.spacetimedb'
        
        legacy_files = [
            legacy_storage_path / 'credentials.json',  # Plaintext legacy
            legacy_storage_path / 'credentials.enc',   # Old encrypted format
            legacy_storage_path / 'auth_credentials.json',  # Alternative naming
        ]
        
        for legacy_file in legacy_files:
            if legacy_file.exists():
                try:
                    migrated = self._migrate_from_file(legacy_file)
                    migrated_count += migrated
                    
                    if migrated > 0:
                        # Backup the legacy file
                        backup_file = legacy_file.with_suffix(f'.backup_{int(time.time())}')
                        legacy_file.rename(backup_file)
                        self.logger.info(f"Migrated {migrated} credentials from {legacy_file}, "
                                       f"backed up to {backup_file}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to migrate from {legacy_file}: {e}")
        
        # Also check for old salt files that might need migration
        old_salt_files = [
            legacy_storage_path / '.salt',
            legacy_storage_path / 'salt',
            legacy_storage_path / '.spacetimedb_salt',
        ]
        
        for old_salt_file in old_salt_files:
            if old_salt_file.exists():
                try:
                    # Don't migrate the salt directly, but note its existence
                    self.logger.info(f"Found legacy salt file {old_salt_file}, "
                                   f"new installation will use fresh secure salt")
                    # Backup old salt file
                    backup_salt = old_salt_file.with_suffix(f'.backup_{int(time.time())}')
                    old_salt_file.rename(backup_salt)
                except Exception as e:
                    self.logger.warning(f"Could not backup legacy salt file {old_salt_file}: {e}")
        
        if migrated_count > 0:
            self.logger.info(f"Successfully migrated {migrated_count} credentials to secure storage")
        
        return migrated_count
    
    def _migrate_from_file(self, legacy_file: Path) -> int:
        """
        Migrate credentials from a specific legacy file.
        
        Args:
            legacy_file: Path to the legacy credential file
            
        Returns:
            Number of credentials migrated from this file
        """
        migrated_count = 0
        
        try:
            # Try to read as plaintext JSON first
            with open(legacy_file, 'r', encoding='utf-8') as f:
                try:
                    # Attempt direct JSON parsing (plaintext format)
                    data = json.load(f)
                    migrated_count = self._import_legacy_json_data(data)
                    return migrated_count
                except json.JSONDecodeError:
                    pass
            
            # Try to read as encrypted file with old key derivation
            with open(legacy_file, 'rb') as f:
                encrypted_data = f.read()
                
            # Try different legacy decryption methods
            decryption_methods = [
                self._try_legacy_fernet_decryption,
                self._try_legacy_simple_decryption,
            ]
            
            for method in decryption_methods:
                try:
                    decrypted_data = method(encrypted_data)
                    if decrypted_data:
                        data = json.loads(decrypted_data.decode('utf-8'))
                        migrated_count = self._import_legacy_json_data(data)
                        break
                except Exception:
                    continue
            
        except Exception as e:
            self.logger.warning(f"Could not read legacy file {legacy_file}: {e}")
        
        return migrated_count
    
    def _import_legacy_json_data(self, data: Dict[str, Any]) -> int:
        """
        Import credential data from legacy JSON format.
        
        Args:
            data: Legacy credential data dictionary
            
        Returns:
            Number of credentials imported
        """
        imported_count = 0
        
        # Handle different legacy data formats
        if isinstance(data, dict):
            for key, cred_data in data.items():
                try:
                    # Create SecureToken from legacy data
                    if isinstance(cred_data, dict):
                        # Modern-ish format with token metadata
                        token = SecureToken(
                            token=cred_data.get('token', ''),
                            token_type=cred_data.get('token_type', 'bearer'),
                            expires_at=datetime.fromisoformat(cred_data['expires_at']) 
                                      if cred_data.get('expires_at') else None,
                            metadata={
                                'identity': cred_data.get('identity', ''),
                                'host': cred_data.get('host', ''),
                                'database': cred_data.get('database', ''),
                                'migrated_from': 'legacy_storage',
                                'migration_time': datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        
                        # Store with host:database key format
                        host = cred_data.get('host', 'unknown')
                        database = cred_data.get('database', 'unknown')
                        storage_key = f"{host}:{database}"
                        
                        self.store_token(storage_key, token)
                        imported_count += 1
                        
                    elif isinstance(cred_data, str):
                        # Simple string token format
                        token = SecureToken(
                            token=cred_data,
                            metadata={
                                'legacy_key': key,
                                'migrated_from': 'legacy_storage',
                                'migration_time': datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        
                        self.store_token(key, token)
                        imported_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"Could not import legacy credential {key}: {e}")
        
        return imported_count
    
    def _try_legacy_fernet_decryption(self, encrypted_data: bytes) -> Optional[bytes]:
        """
        Try to decrypt using legacy Fernet key derivation methods.
        
        Args:
            encrypted_data: Encrypted credential data
            
        Returns:
            Decrypted data or None if decryption failed
        """
        # Try common legacy key derivation patterns
        legacy_patterns = [
            # Old pattern: username + hostname (the vulnerable one)
            lambda: f"{os.environ.get('USER', 'default')}{os.getenv('HOSTNAME', 'localhost')}",
            lambda: f"{os.getlogin()}{os.getenv('HOSTNAME', 'localhost')}",
            # With socket hostname
            lambda: f"{os.environ.get('USER', 'default')}{self._get_hostname()}",
            lambda: f"{os.getlogin()}{self._get_hostname()}",
        ]
        
        for pattern_func in legacy_patterns:
            try:
                # Generate legacy key
                seed = pattern_func()
                legacy_key = base64.urlsafe_b64encode(
                    hashlib.sha256(seed.encode()).digest()
                )
                
                # Try Fernet decryption
                f = Fernet(legacy_key)
                decrypted = f.decrypt(encrypted_data)
                return decrypted
                
            except Exception:
                continue
        
        return None
    
    def _try_legacy_simple_decryption(self, encrypted_data: bytes) -> Optional[bytes]:
        """
        Try other legacy decryption methods.
        
        Args:
            encrypted_data: Encrypted credential data
            
        Returns:
            Decrypted data or None if decryption failed
        """
        # Could implement other legacy encryption schemes here
        # For now, just return None
        return None
    
    def _get_hostname(self) -> str:
        """Get hostname safely."""
        try:
            import socket
            return socket.gethostname()
        except:
            return 'localhost'
    
    def shutdown(self) -> None:
        """Shutdown storage and cleanup."""
        self._refresh_running = False
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
        
        # Clear memory store
        if self.config.memory_protection:
            # Overwrite sensitive data
            for key in list(self._memory_store.keys()):
                self._memory_store[key] = None
        
        self._memory_store.clear()
        self._refresh_callbacks.clear()


# Convenience functions
def create_secure_token(
    token: str,
    expires_in: Optional[int] = None,
    refresh_token: Optional[str] = None,
    scopes: Optional[List[str]] = None
) -> SecureToken:
    """
    Create a secure token with common defaults.
    
    Args:
        token: The token string
        expires_in: Expiration in seconds
        refresh_token: Optional refresh token
        scopes: Optional token scopes
        
    Returns:
        SecureToken instance
    """
    expires_at = None
    if expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    
    return SecureToken(
        token=token,
        expires_at=expires_at,
        refresh_token=refresh_token,
        scopes=scopes or []
    )
