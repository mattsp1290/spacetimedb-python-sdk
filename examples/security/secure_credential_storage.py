#!/usr/bin/env python3
"""
Secure Credential Storage Example
=================================

This example demonstrates secure credential storage and management techniques
including encryption, secure key derivation, and best practices for handling
sensitive authentication data.

Key concepts:
- Encrypted credential storage
- Secure key derivation (PBKDF2, scrypt)
- Token rotation and refresh
- Secure memory handling
- Audit logging for security events
- Constant-time credential verification to prevent timing attacks

Requirements:
- spacetimedb-sdk
- cryptography
- keyring (optional, for system keychain integration)
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import os
import json
import time
import getpass
from typing import Dict, Optional, Any, Union
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path

# Cryptography imports
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import base64
import secrets

# Optional keyring for system integration
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
    print("Warning: keyring not available. System keychain integration disabled.")

from spacetimedb_sdk.auth import AuthenticationProvider
from spacetimedb_sdk.secure_storage import SecureStorage


@dataclass
class CredentialMetadata:
    """Metadata for stored credentials"""
    created_at: float
    last_used: float
    expires_at: Optional[float]
    rotation_count: int
    access_count: int
    origin: str  # Where the credential was created
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'created_at': self.created_at,
            'last_used': self.last_used,
            'expires_at': self.expires_at,
            'rotation_count': self.rotation_count,
            'access_count': self.access_count,
            'origin': self.origin
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CredentialMetadata':
        return cls(
            created_at=data['created_at'],
            last_used=data['last_used'],
            expires_at=data.get('expires_at'),
            rotation_count=data.get('rotation_count', 0),
            access_count=data.get('access_count', 0),
            origin=data.get('origin', 'unknown')
        )


class SecureCredentialManager:
    """Secure credential storage and management"""
    
    def __init__(self, storage_path: str = "~/.spacetimedb/credentials"):
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Set restrictive permissions
        os.chmod(self.storage_path, 0o700)
        
        self.credentials_file = self.storage_path / "credentials.enc"
        self.metadata_file = self.storage_path / "metadata.json"
        self.audit_file = self.storage_path / "audit.log"
        
        self._fernet = None
        self._master_key = None
        self._audit_logger = AuditLogger(self.audit_file)
    
    def _derive_key(self, password: str, salt: bytes, algorithm: str = "pbkdf2") -> bytes:
        """Derive encryption key from password using specified algorithm"""
        
        if algorithm == "pbkdf2":
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,  # OWASP recommended minimum
            )
        elif algorithm == "scrypt":
            kdf = Scrypt(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                n=2**14,  # CPU/memory cost parameter
                r=8,      # Block size
                p=1,      # Parallelization parameter
            )
        else:
            raise ValueError(f"Unsupported KDF algorithm: {algorithm}")
        
        return kdf.derive(password.encode())
    
    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one"""
        salt_file = self.storage_path / "salt"
        
        if salt_file.exists():
            with open(salt_file, 'rb') as f:
                return f.read()
        else:
            salt = secrets.token_bytes(32)
            with open(salt_file, 'wb') as f:
                f.write(salt)
            # Set restrictive permissions
            os.chmod(salt_file, 0o600)
            return salt
    
    def initialize(self, password: str, algorithm: str = "pbkdf2") -> bool:
        """Initialize secure storage with master password"""
        
        try:
            salt = self._get_or_create_salt()
            key = self._derive_key(password, salt, algorithm)
            self._fernet = Fernet(base64.urlsafe_b64encode(key))
            self._master_key = key
            
            # Test encryption/decryption
            test_data = b"test_encryption"
            encrypted = self._fernet.encrypt(test_data)
            decrypted = self._fernet.decrypt(encrypted)
            
            if decrypted != test_data:
                raise ValueError("Encryption test failed")
            
            self._audit_logger.log_security_event(
                "storage_initialized",
                {"algorithm": algorithm, "success": True}
            )
            
            return True
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "storage_initialization_failed",
                {"algorithm": algorithm, "error": str(e)}
            )
            return False
    
    def store_credential(
        self,
        credential_id: str,
        credential_data: Dict[str, Any],
        expires_at: Optional[float] = None
    ) -> bool:
        """Store encrypted credential"""
        
        if not self._fernet:
            raise RuntimeError("Storage not initialized")
        
        try:
            # Load existing credentials
            credentials = self._load_credentials()
            
            # Create metadata
            metadata = CredentialMetadata(
                created_at=time.time(),
                last_used=time.time(),
                expires_at=expires_at,
                rotation_count=0,
                access_count=0,
                origin=f"stored_by_{getpass.getuser()}"
            )
            
            # Encrypt credential data
            encrypted_data = self._fernet.encrypt(
                json.dumps(credential_data).encode()
            )
            
            # Store credential
            credentials[credential_id] = {
                'data': base64.b64encode(encrypted_data).decode(),
                'metadata': metadata.to_dict()
            }
            
            # Save to file
            self._save_credentials(credentials)
            
            self._audit_logger.log_security_event(
                "credential_stored",
                {
                    "credential_id": credential_id,
                    "expires_at": expires_at,
                    "success": True
                }
            )
            
            return True
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "credential_storage_failed",
                {
                    "credential_id": credential_id,
                    "error": str(e)
                }
            )
            return False
    
    def retrieve_credential(self, credential_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve and decrypt credential"""
        
        if not self._fernet:
            raise RuntimeError("Storage not initialized")
        
        try:
            credentials = self._load_credentials()
            
            if credential_id not in credentials:
                self._audit_logger.log_security_event(
                    "credential_not_found",
                    {"credential_id": credential_id}
                )
                return None
            
            credential_entry = credentials[credential_id]
            metadata = CredentialMetadata.from_dict(credential_entry['metadata'])
            
            # Check if credential is expired
            if metadata.expires_at and time.time() > metadata.expires_at:
                self._audit_logger.log_security_event(
                    "credential_expired",
                    {"credential_id": credential_id}
                )
                return None
            
            # Decrypt credential data
            encrypted_data = base64.b64decode(credential_entry['data'])
            decrypted_data = self._fernet.decrypt(encrypted_data)
            credential_data = json.loads(decrypted_data.decode())
            
            # Update metadata
            metadata.last_used = time.time()
            metadata.access_count += 1
            credential_entry['metadata'] = metadata.to_dict()
            
            # Save updated metadata
            self._save_credentials(credentials)
            
            self._audit_logger.log_security_event(
                "credential_retrieved",
                {
                    "credential_id": credential_id,
                    "access_count": metadata.access_count,
                    "success": True
                }
            )
            
            return credential_data
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "credential_retrieval_failed",
                {
                    "credential_id": credential_id,
                    "error": str(e)
                }
            )
            return None
    
    def rotate_credential(
        self,
        credential_id: str,
        new_credential_data: Dict[str, Any],
        new_expires_at: Optional[float] = None
    ) -> bool:
        """Rotate an existing credential"""
        
        try:
            credentials = self._load_credentials()
            
            if credential_id not in credentials:
                return False
            
            # Update credential data
            encrypted_data = self._fernet.encrypt(
                json.dumps(new_credential_data).encode()
            )
            
            # Update metadata
            metadata = CredentialMetadata.from_dict(credentials[credential_id]['metadata'])
            metadata.rotation_count += 1
            metadata.last_used = time.time()
            if new_expires_at:
                metadata.expires_at = new_expires_at
            
            # Store updated credential
            credentials[credential_id] = {
                'data': base64.b64encode(encrypted_data).decode(),
                'metadata': metadata.to_dict()
            }
            
            self._save_credentials(credentials)
            
            self._audit_logger.log_security_event(
                "credential_rotated",
                {
                    "credential_id": credential_id,
                    "rotation_count": metadata.rotation_count,
                    "success": True
                }
            )
            
            return True
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "credential_rotation_failed",
                {
                    "credential_id": credential_id,
                    "error": str(e)
                }
            )
            return False
    
    def delete_credential(self, credential_id: str) -> bool:
        """Securely delete a credential"""
        
        try:
            credentials = self._load_credentials()
            
            if credential_id not in credentials:
                return False
            
            # Remove credential
            del credentials[credential_id]
            
            # Save updated credentials
            self._save_credentials(credentials)
            
            self._audit_logger.log_security_event(
                "credential_deleted",
                {
                    "credential_id": credential_id,
                    "success": True
                }
            )
            
            return True
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "credential_deletion_failed",
                {
                    "credential_id": credential_id,
                    "error": str(e)
                }
            )
            return False
    
    def list_credentials(self) -> List[Dict[str, Any]]:
        """List all stored credentials (metadata only)"""
        
        try:
            credentials = self._load_credentials()
            
            result = []
            for credential_id, credential_entry in credentials.items():
                metadata = CredentialMetadata.from_dict(credential_entry['metadata'])
                
                result.append({
                    'id': credential_id,
                    'created_at': metadata.created_at,
                    'last_used': metadata.last_used,
                    'expires_at': metadata.expires_at,
                    'rotation_count': metadata.rotation_count,
                    'access_count': metadata.access_count,
                    'is_expired': metadata.expires_at and time.time() > metadata.expires_at
                })
            
            return result
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "credential_listing_failed",
                {"error": str(e)}
            )
            return []
    
    def cleanup_expired_credentials(self) -> int:
        """Remove expired credentials"""
        
        try:
            credentials = self._load_credentials()
            current_time = time.time()
            
            expired_ids = []
            for credential_id, credential_entry in credentials.items():
                metadata = CredentialMetadata.from_dict(credential_entry['metadata'])
                if metadata.expires_at and current_time > metadata.expires_at:
                    expired_ids.append(credential_id)
            
            # Remove expired credentials
            for credential_id in expired_ids:
                del credentials[credential_id]
            
            if expired_ids:
                self._save_credentials(credentials)
            
            self._audit_logger.log_security_event(
                "expired_credentials_cleaned",
                {
                    "count": len(expired_ids),
                    "credential_ids": expired_ids
                }
            )
            
            return len(expired_ids)
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "credential_cleanup_failed",
                {"error": str(e)}
            )
            return 0
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials from encrypted file"""
        
        if not self.credentials_file.exists():
            return {}
        
        try:
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()
            
            if not encrypted_data:
                return {}
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
            
        except Exception as e:
            self._audit_logger.log_security_event(
                "credential_load_failed",
                {"error": str(e)}
            )
            return {}
    
    def _save_credentials(self, credentials: Dict[str, Any]):
        """Save credentials to encrypted file"""
        
        encrypted_data = self._fernet.encrypt(
            json.dumps(credentials).encode()
        )
        
        # Write to temporary file first
        temp_file = self.credentials_file.with_suffix('.tmp')
        with open(temp_file, 'wb') as f:
            f.write(encrypted_data)
        
        # Set restrictive permissions
        os.chmod(temp_file, 0o600)
        
        # Atomic rename
        temp_file.replace(self.credentials_file)
    
    @contextmanager
    def secure_string(self, value: str):
        """Context manager for secure string handling"""
        # In a real implementation, this would use secure memory
        # For demonstration purposes, we'll just ensure cleanup
        try:
            yield value
        finally:
            # Overwrite string in memory (limited effectiveness in Python)
            if hasattr(value, 'encode'):
                # This doesn't actually work in Python due to string immutability
                # but demonstrates the concept
                pass


class AuditLogger:
    """Security audit logging"""
    
    def __init__(self, audit_file: Path):
        self.audit_file = audit_file
    
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security event"""
        
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'details': details,
            'user': getpass.getuser(),
            'pid': os.getpid()
        }
        
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(event) + '\n')


class SystemKeychainIntegration:
    """Integration with system keychain/keyring"""
    
    def __init__(self, service_name: str = "spacetimedb-sdk"):
        self.service_name = service_name
        self.available = HAS_KEYRING
    
    def store_master_password(self, username: str, password: str) -> bool:
        """Store master password in system keychain"""
        
        if not self.available:
            return False
        
        try:
            keyring.set_password(self.service_name, username, password)
            return True
        except Exception:
            return False
    
    def retrieve_master_password(self, username: str) -> Optional[str]:
        """Retrieve master password from system keychain"""
        
        if not self.available:
            return None
        
        try:
            return keyring.get_password(self.service_name, username)
        except Exception:
            return None
    
    def delete_master_password(self, username: str) -> bool:
        """Delete master password from system keychain"""
        
        if not self.available:
            return False
        
        try:
            keyring.delete_password(self.service_name, username)
            return True
        except Exception:
            return False


class SecureCredentialDemo:
    """Demonstration of secure credential storage"""
    
    def __init__(self):
        self.manager = SecureCredentialManager()
        self.keychain = SystemKeychainIntegration()
    
    def demonstrate_basic_storage(self):
        """Demonstrate basic credential storage"""
        
        print("Basic Credential Storage Demo")
        print("=" * 50)
        
        # Initialize storage
        password = "demo_master_password_123"
        print("\n1. Initializing secure storage...")
        
        if self.manager.initialize(password, algorithm="pbkdf2"):
            print("   ✅ Storage initialized successfully")
        else:
            print("   ❌ Storage initialization failed")
            return
        
        # Store credentials
        print("\n2. Storing credentials...")
        
        credentials = [
            {
                'id': 'spacetimedb_token',
                'data': {
                    'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                    'refresh_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                    'token_type': 'Bearer',
                    'expires_in': 3600
                },
                'expires_at': time.time() + 3600
            },
            {
                'id': 'database_credentials',
                'data': {
                    'host': 'db.example.com',
                    'username': 'db_user',
                    'password': 'secure_db_password',
                    'database': 'spacetimedb'
                },
                'expires_at': None
            }
        ]
        
        for cred in credentials:
            success = self.manager.store_credential(
                cred['id'],
                cred['data'],
                cred['expires_at']
            )
            if success:
                print(f"   ✅ Stored credential: {cred['id']}")
            else:
                print(f"   ❌ Failed to store credential: {cred['id']}")
        
        # Retrieve credentials
        print("\n3. Retrieving credentials...")
        
        token_data = self.manager.retrieve_credential('spacetimedb_token')
        if token_data:
            print(f"   ✅ Retrieved token (type: {token_data['token_type']})")
        else:
            print("   ❌ Failed to retrieve token")
        
        db_data = self.manager.retrieve_credential('database_credentials')
        if db_data:
            print(f"   ✅ Retrieved database credentials (host: {db_data['host']})")
        else:
            print("   ❌ Failed to retrieve database credentials")
    
    def demonstrate_credential_rotation(self):
        """Demonstrate credential rotation"""
        
        print("\n\nCredential Rotation Demo")
        print("=" * 50)
        
        # Store initial credential
        initial_token = {
            'token': 'old_token_12345',
            'refresh_token': 'old_refresh_token_12345',
            'expires_in': 3600
        }
        
        print("\n1. Storing initial token...")
        self.manager.store_credential('rotating_token', initial_token)
        
        # Rotate credential
        print("\n2. Rotating token...")
        new_token = {
            'token': 'new_token_67890',
            'refresh_token': 'new_refresh_token_67890',
            'expires_in': 3600
        }
        
        success = self.manager.rotate_credential(
            'rotating_token',
            new_token,
            time.time() + 3600
        )
        
        if success:
            print("   ✅ Token rotated successfully")
        else:
            print("   ❌ Token rotation failed")
        
        # Verify rotation
        print("\n3. Verifying rotation...")
        retrieved_token = self.manager.retrieve_credential('rotating_token')
        if retrieved_token and secrets.compare_digest(retrieved_token['token'], new_token['token']):
            print("   ✅ Rotation verified - new token retrieved")
        else:
            print("   ❌ Rotation verification failed")
    
    def demonstrate_credential_expiration(self):
        """Demonstrate credential expiration and cleanup"""
        
        print("\n\nCredential Expiration Demo")
        print("=" * 50)
        
        # Store credential with short expiration
        print("\n1. Storing credential with 2-second expiration...")
        
        short_lived_cred = {
            'data': 'this_will_expire_soon',
            'type': 'temporary'
        }
        
        self.manager.store_credential(
            'short_lived',
            short_lived_cred,
            time.time() + 2  # Expires in 2 seconds
        )
        
        # Try to retrieve immediately
        print("\n2. Retrieving credential immediately...")
        data = self.manager.retrieve_credential('short_lived')
        if data:
            print(f"   ✅ Retrieved: {data['data']}")
        else:
            print("   ❌ Failed to retrieve")
        
        # Wait for expiration
        print("\n3. Waiting for expiration...")
        time.sleep(3)
        
        # Try to retrieve after expiration
        print("\n4. Retrieving after expiration...")
        data = self.manager.retrieve_credential('short_lived')
        if data:
            print(f"   ❌ Should have expired: {data['data']}")
        else:
            print("   ✅ Credential correctly expired")
        
        # Cleanup expired credentials
        print("\n5. Cleaning up expired credentials...")
        cleaned_count = self.manager.cleanup_expired_credentials()
        print(f"   🗑️  Cleaned up {cleaned_count} expired credentials")
    
    def demonstrate_keychain_integration(self):
        """Demonstrate system keychain integration"""
        
        print("\n\nSystem Keychain Integration Demo")
        print("=" * 50)
        
        if not self.keychain.available:
            print("   ⚠️  System keychain not available")
            return
        
        username = getpass.getuser()
        master_password = "secure_master_password_123"
        
        print("\n1. Storing master password in system keychain...")
        if self.keychain.store_master_password(username, master_password):
            print("   ✅ Master password stored in keychain")
        else:
            print("   ❌ Failed to store master password")
            return
        
        print("\n2. Retrieving master password from keychain...")
        retrieved_password = self.keychain.retrieve_master_password(username)
        if retrieved_password and secrets.compare_digest(retrieved_password, master_password):
            print("   ✅ Master password retrieved successfully")
        else:
            print("   ❌ Failed to retrieve master password")
        
        print("\n3. Initializing storage with keychain password...")
        if self.manager.initialize(retrieved_password):
            print("   ✅ Storage initialized with keychain password")
        else:
            print("   ❌ Failed to initialize storage")
        
        # Clean up
        print("\n4. Cleaning up keychain...")
        if self.keychain.delete_master_password(username):
            print("   ✅ Master password removed from keychain")
        else:
            print("   ❌ Failed to remove master password")
    
    def demonstrate_audit_logging(self):
        """Demonstrate security audit logging"""
        
        print("\n\nSecurity Audit Logging Demo")
        print("=" * 50)
        
        print("\n1. Performing various credential operations...")
        
        # These operations will be logged
        self.manager.store_credential('audit_test', {'data': 'test'})
        self.manager.retrieve_credential('audit_test')
        self.manager.rotate_credential('audit_test', {'data': 'rotated'})
        self.manager.delete_credential('audit_test')
        
        print("\n2. Reading audit log...")
        
        if self.manager.audit_file.exists():
            with open(self.manager.audit_file, 'r') as f:
                lines = f.readlines()
            
            print(f"   📋 Found {len(lines)} audit entries:")
            
            for line in lines[-5:]:  # Show last 5 entries
                try:
                    event = json.loads(line.strip())
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event['timestamp']))
                    print(f"   {timestamp}: {event['event_type']}")
                except json.JSONDecodeError:
                    pass
        else:
            print("   ⚠️  No audit log found")
    
    def list_all_credentials(self):
        """List all stored credentials"""
        
        print("\n\nStored Credentials Summary")
        print("=" * 50)
        
        credentials = self.manager.list_credentials()
        
        if not credentials:
            print("   📭 No credentials stored")
            return
        
        print(f"   📊 Found {len(credentials)} credentials:")
        
        for cred in credentials:
            created = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cred['created_at']))
            last_used = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cred['last_used']))
            
            status = "🔴 EXPIRED" if cred['is_expired'] else "🟢 ACTIVE"
            
            print(f"\n   📁 {cred['id']} [{status}]")
            print(f"      Created: {created}")
            print(f"      Last Used: {last_used}")
            print(f"      Rotations: {cred['rotation_count']}")
            print(f"      Access Count: {cred['access_count']}")
            
            if cred['expires_at']:
                expires = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cred['expires_at']))
                print(f"      Expires: {expires}")


def main():
    """Run secure credential storage demonstration"""
    
    print("SpacetimeDB Secure Credential Storage Demo")
    print("=" * 60)
    
    demo = SecureCredentialDemo()
    
    try:
        demo.demonstrate_basic_storage()
        demo.demonstrate_credential_rotation()
        demo.demonstrate_credential_expiration()
        demo.demonstrate_keychain_integration()
        demo.demonstrate_audit_logging()
        demo.list_all_credentials()
        
        print("\n" + "=" * 60)
        print("✅ Demo completed successfully!")
        print("📋 Check the audit log for security events")
        print("🔐 Credentials are stored encrypted on disk")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()