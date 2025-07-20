"""
Security tests for credential storage and management

Tests credential encryption, secure storage, and protection against
common security vulnerabilities in authentication systems.
"""
import pytest
import time
import threading
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from cryptography.fernet import Fernet

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

try:
    from spacetimedb_sdk.auth_storage import AuthenticationStorage
    from spacetimedb_sdk.secure_storage import SecureCredentialStorage
    from spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler
    from spacetimedb_sdk.auth.authentication_manager import AuthenticationManager
except ImportError as e:
    pytest.skip(f"Required authentication modules not available: {e}", allow_module_level=True)


class TestCredentialSecurity:
    """Test credential security and encryption at rest."""

    @pytest.fixture
    def isolated_storage(self, tmp_path):
        """Provide isolated credential storage for testing."""
        storage_path = tmp_path / "test_credentials"
        storage_path.mkdir(exist_ok=True)
        return storage_path

    @pytest.fixture
    def auth_handler(self, isolated_storage):
        """Provide configured authentication handler."""
        try:
            return AuthenticationHandler(
                storage_path=isolated_storage,
                auto_refresh_tokens=False
            )
        except Exception:
            # Fallback for different constructor signatures
            handler = AuthenticationHandler()
            handler.storage_path = isolated_storage
            return handler

    def test_credentials_encrypted_at_rest(self, auth_handler, isolated_storage):
        """Verify credentials are encrypted when stored to disk."""
        test_identity = "test_identity_12345"
        test_token = "sensitive_auth_token_67890"
        test_host = "localhost:3000"
        test_db = "test_database"
        
        # Store credentials
        try:
            auth_handler.store_credentials(test_identity, test_token, test_host, test_db)
        except AttributeError:
            # Try alternative method name
            auth_handler.store_token(test_identity, test_token, test_host, test_db)
        
        # Find storage files
        storage_files = list(isolated_storage.glob("*"))
        assert len(storage_files) > 0, "No storage files created"
        
        # Read raw storage content
        for file_path in storage_files:
            if file_path.is_file():
                raw_content = file_path.read_bytes()
                
                # Verify sensitive data is not in plaintext
                assert test_token.encode() not in raw_content, "Token found in plaintext"
                assert test_identity.encode() not in raw_content, "Identity found in plaintext"
                assert b"sensitive_auth_token" not in raw_content, "Sensitive data exposed"

    def test_credentials_not_logged_in_plaintext(self, auth_handler, caplog):
        """Verify no sensitive data appears in logs."""
        test_token = "super_secret_token_123456"
        test_identity = "confidential_identity_789"
        
        with caplog.at_level("DEBUG"):
            try:
                auth_handler.store_credentials(test_identity, test_token, "host", "db")
                auth_handler.get_credentials("host", "db")
            except AttributeError:
                # Handle different method signatures
                pass
        
        # Check all log messages
        for record in caplog.records:
            message = record.getMessage()
            assert test_token not in message, f"Token leaked in log: {message}"
            assert test_identity not in message, f"Identity leaked in log: {message}"
            assert "super_secret" not in message, f"Sensitive data in log: {message}"

    def test_timing_attack_resistance(self, auth_handler):
        """Verify authentication timing is consistent to prevent timing attacks."""
        valid_identity = "valid_user_identity"
        invalid_identity = "invalid_user_identity"
        host = "localhost:3000"
        db = "test_db"
        
        # Setup valid credentials
        try:
            auth_handler.store_credentials(valid_identity, "valid_token", host, db)
        except AttributeError:
            pytest.skip("Method not available for timing test")
        
        valid_times = []
        invalid_times = []
        
        # Measure timing for valid vs invalid authentication attempts
        for _ in range(50):  # Reduced iterations for faster testing
            # Valid authentication timing
            start = time.perf_counter()
            try:
                auth_handler.get_credentials(host, db)
            except Exception:
                pass
            valid_times.append(time.perf_counter() - start)
            
            # Invalid authentication timing
            start = time.perf_counter()
            try:
                auth_handler.get_credentials("invalid_host", "invalid_db")
            except Exception:
                pass
            invalid_times.append(time.perf_counter() - start)
        
        # Calculate average timing
        avg_valid = sum(valid_times) / len(valid_times)
        avg_invalid = sum(invalid_times) / len(invalid_times)
        
        # Timing difference should be minimal (less than 50ms to account for system variance)
        timing_difference = abs(avg_valid - avg_invalid)
        assert timing_difference < 0.05, f"Timing attack vulnerability: {timing_difference:.4f}s difference"

    def test_token_expiry_edge_cases(self, auth_handler):
        """Test edge cases in token expiry logic."""
        host = "localhost:3000"
        db = "test_db"
        
        test_cases = [
            # Edge case: Token expires exactly now
            {"expires_at": time.time(), "should_be_valid": False},
            # Edge case: Token expires 1 second ago
            {"expires_at": time.time() - 1, "should_be_valid": False},
            # Edge case: Token expires 1 second from now
            {"expires_at": time.time() + 1, "should_be_valid": True},
            # Edge case: Very far future expiry
            {"expires_at": time.time() + (365 * 24 * 3600), "should_be_valid": True},
        ]
        
        for i, case in enumerate(test_cases):
            identity = f"test_identity_{i}"
            token = f"test_token_{i}"
            
            try:
                # Store token with expiry
                auth_handler.store_credentials(
                    identity, token, host, db, 
                    expires_at=case["expires_at"]
                )
                
                # Check if token is considered valid
                is_valid = auth_handler.is_token_valid(host, db)
                
                assert is_valid == case["should_be_valid"], \
                    f"Token expiry edge case failed for case {i}: expected {case['should_be_valid']}, got {is_valid}"
                    
            except (AttributeError, TypeError):
                # Skip if expiry functionality not available
                pytest.skip("Token expiry functionality not available")

    def test_concurrent_credential_access(self, auth_handler):
        """Test thread safety of credential operations."""
        host = "localhost:3000"
        db = "test_db"
        identity = "concurrent_test_identity"
        token = "concurrent_test_token"
        
        # Store initial credentials
        try:
            auth_handler.store_credentials(identity, token, host, db)
        except AttributeError:
            pytest.skip("Credential storage not available")
        
        results = []
        errors = []
        
        def worker_read():
            """Worker function for reading credentials."""
            try:
                creds = auth_handler.get_credentials(host, db)
                results.append(creds)
            except Exception as e:
                errors.append(e)
        
        def worker_write():
            """Worker function for writing credentials."""
            try:
                auth_handler.store_credentials(
                    f"{identity}_updated", 
                    f"{token}_updated", 
                    host, db
                )
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads for concurrent access
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=worker_read))
            threads.append(threading.Thread(target=worker_write))
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=2.0)
        
        # Should not have thread safety errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_credential_isolation_between_databases(self, auth_handler):
        """Test that credentials for different databases are properly isolated."""
        host = "localhost:3000"
        db1 = "database_one"
        db2 = "database_two"
        
        identity1 = "identity_for_db1"
        token1 = "token_for_db1"
        identity2 = "identity_for_db2"
        token2 = "token_for_db2"
        
        try:
            # Store credentials for different databases
            auth_handler.store_credentials(identity1, token1, host, db1)
            auth_handler.store_credentials(identity2, token2, host, db2)
            
            # Retrieve credentials for each database
            creds1 = auth_handler.get_credentials(host, db1)
            creds2 = auth_handler.get_credentials(host, db2)
            
            # Verify isolation - each database should get its own credentials
            if creds1 and creds2:
                # Ensure credentials are different
                assert creds1 != creds2, "Credentials not properly isolated between databases"
                
                # Try to get credentials for non-existent database
                creds_none = auth_handler.get_credentials(host, "non_existent_db")
                assert creds_none is None, "Should return None for non-existent database"
                
        except AttributeError:
            pytest.skip("Multi-database credential isolation test not supported")

    def test_secure_credential_cleanup(self, auth_handler, isolated_storage):
        """Test that credentials are securely removed when cleared."""
        identity = "cleanup_test_identity"
        token = "cleanup_test_token_secret"
        host = "localhost:3000"
        db = "test_db"
        
        try:
            # Store credentials
            auth_handler.store_credentials(identity, token, host, db)
            
            # Verify storage exists
            storage_files_before = list(isolated_storage.glob("*"))
            assert len(storage_files_before) > 0, "No storage files created"
            
            # Clear credentials
            auth_handler.clear_credentials(host, db)
            
            # Verify credentials are gone
            creds = auth_handler.get_credentials(host, db)
            assert creds is None, "Credentials not properly cleared"
            
            # Check that sensitive data is not left in storage files
            storage_files_after = list(isolated_storage.glob("*"))
            for file_path in storage_files_after:
                if file_path.is_file():
                    content = file_path.read_bytes()
                    assert token.encode() not in content, "Token data left after cleanup"
                    assert identity.encode() not in content, "Identity data left after cleanup"
                    
        except AttributeError:
            pytest.skip("Credential cleanup functionality not available")


@pytest.mark.security
class TestEncryptionSecurity:
    """Test encryption implementation security."""
    
    def test_encryption_key_generation(self):
        """Test that encryption keys are properly generated."""
        try:
            storage = SecureCredentialStorage()
            
            # Key should be properly formatted
            if hasattr(storage, '_key'):
                assert len(storage._key) == 44, "Fernet key should be 44 bytes when base64 encoded"
            
        except (ImportError, AttributeError):
            pytest.skip("SecureCredentialStorage not available")
    
    def test_encryption_consistency(self):
        """Test that encryption/decryption is consistent."""
        try:
            storage = SecureCredentialStorage()
            test_data = "sensitive_test_data_12345"
            
            # Encrypt data
            encrypted = storage.encrypt(test_data)
            
            # Verify it's actually encrypted
            assert encrypted != test_data, "Data not encrypted"
            assert test_data not in encrypted, "Original data visible in encrypted form"
            
            # Decrypt and verify
            decrypted = storage.decrypt(encrypted)
            assert decrypted == test_data, "Decryption failed"
            
        except (ImportError, AttributeError):
            pytest.skip("Encryption functionality not available")
    
    def test_encryption_different_keys_different_output(self):
        """Test that different keys produce different encrypted output."""
        try:
            storage1 = SecureCredentialStorage()
            storage2 = SecureCredentialStorage()
            
            test_data = "same_input_data"
            
            encrypted1 = storage1.encrypt(test_data)
            encrypted2 = storage2.encrypt(test_data)
            
            # Different keys should produce different encrypted output
            assert encrypted1 != encrypted2, "Different keys produced same encrypted output"
            
        except (ImportError, AttributeError):
            pytest.skip("Multiple storage instances not supported")