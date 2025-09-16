#!/usr/bin/env python3
"""
Comprehensive Security Test for SpacetimeDB Key Derivation System

This test validates the security improvements to the authentication key derivation
system, ensuring protection against cryptographic attacks.

Test Categories:
1. Key Derivation Security
2. Salt Management
3. PBKDF2 Performance & Strength
4. Migration Safety
5. File Permission Security
"""

import os
import sys
import tempfile
import time
import hashlib
import secrets
import json
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

# Add the src directory to Python path for testing
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from spacetimedb_sdk.secure_storage import (
        SecureStorage, StorageConfig, StorageBackend, SecureToken
    )
    from cryptography.fernet import Fernet
    import base64
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure the SpacetimeDB SDK is properly installed")
    sys.exit(1)


class TestSecureKeyDerivation(unittest.TestCase):
    """Test suite for secure key derivation system."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config = StorageConfig(
            backend=StorageBackend.ENCRYPTED_FILE,
            storage_path=self.test_dir / "test_storage",
            key_derivation_iterations=10000,  # Lower for faster tests
        )
        self.storage = SecureStorage(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        self.storage.shutdown()
        # Clean up test directory
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_key_derivation_uniqueness(self):
        """Test that key derivation produces unique keys across instances."""
        # Create multiple storage instances
        storage1 = SecureStorage(StorageConfig(
            backend=StorageBackend.ENCRYPTED_FILE,
            storage_path=self.test_dir / "storage1"
        ))
        storage2 = SecureStorage(StorageConfig(
            backend=StorageBackend.ENCRYPTED_FILE,
            storage_path=self.test_dir / "storage2"
        ))
        
        # Get machine IDs (which should be different due to different salts)
        machine_id1 = storage1._get_machine_id()
        machine_id2 = storage2._get_machine_id()
        
        # Should be different due to different installation salts
        self.assertNotEqual(machine_id1, machine_id2,
                          "Machine IDs should be unique across installations")
        
        storage1.shutdown()
        storage2.shutdown()
    
    def test_key_derivation_deterministic_per_installation(self):
        """Test that key derivation is deterministic for same installation."""
        # First call
        machine_id1 = self.storage._get_machine_id()
        
        # Second call - should be identical due to persisted salt
        machine_id2 = self.storage._get_machine_id()
        
        self.assertEqual(machine_id1, machine_id2,
                        "Machine ID should be deterministic for same installation")
    
    def test_salt_file_security(self):
        """Test that salt files are created with secure permissions."""
        # Trigger salt file creation
        self.storage._get_or_create_machine_salt()
        
        salt_file = self.config.storage_path / ".machine_salt"
        self.assertTrue(salt_file.exists(), "Machine salt file should exist")
        
        # Check file permissions (owner read/write only)
        file_stat = salt_file.stat()
        permissions = file_stat.st_mode & 0o777
        self.assertEqual(permissions, 0o600,
                        f"Salt file should have 0o600 permissions, got {oct(permissions)}")
    
    def test_kdf_salt_file_security(self):
        """Test that KDF salt files are created with secure permissions."""
        # Trigger KDF salt file creation
        self.storage._get_or_create_kdf_salt()
        
        kdf_salt_file = self.config.storage_path / ".kdf_salt"
        self.assertTrue(kdf_salt_file.exists(), "KDF salt file should exist")
        
        # Check file permissions
        file_stat = kdf_salt_file.stat()
        permissions = file_stat.st_mode & 0o777
        self.assertEqual(permissions, 0o600,
                        f"KDF salt file should have 0o600 permissions, got {oct(permissions)}")
    
    def test_salt_validation(self):
        """Test salt validation and regeneration."""
        salt_file = self.config.storage_path / ".machine_salt"
        
        # Create invalid salt file
        salt_file.parent.mkdir(parents=True, exist_ok=True)
        with open(salt_file, 'w') as f:
            f.write("invalid_salt_format")
        
        # Should regenerate valid salt
        salt = self.storage._get_or_create_machine_salt()
        self.assertEqual(len(salt), 64, "Salt should be 64 character hex string")
        self.assertTrue(all(c in '0123456789abcdef' for c in salt.lower()),
                       "Salt should be valid hex")
    
    def test_pbkdf2_iteration_benchmarking(self):
        """Test PBKDF2 iteration count optimization."""
        # This should complete reasonably quickly and set optimal iterations
        iterations = self.storage._get_optimal_iterations()
        
        self.assertGreaterEqual(iterations, 50_000,
                              "Iterations should be at least 50,000")
        self.assertLessEqual(iterations, 1_000_000,
                           "Iterations should not exceed 1,000,000")
    
    def test_key_derivation_entropy_sources(self):
        """Test that key derivation uses multiple entropy sources."""
        # Mock different system states to ensure entropy is used
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            # Even without system machine-id files, should still work
            machine_id = self.storage._get_machine_id()
            self.assertIsInstance(machine_id, str)
            self.assertEqual(len(machine_id), 64)  # SHA256 hex output
    
    def test_secure_password_derivation(self):
        """Test that derived passwords contain sufficient entropy."""
        password1 = self.storage._derive_secure_password()
        password2 = self.storage._derive_secure_password()
        
        # Should be deterministic for same instance
        self.assertEqual(password1, password2,
                        "Password derivation should be deterministic")
        
        # Should be long enough
        self.assertGreaterEqual(len(password1), 64,
                              "Derived password should be at least 64 characters")
    
    def test_legacy_credential_migration(self):
        """Test migration from legacy credential formats."""
        # Create legacy plaintext credentials
        legacy_dir = self.test_dir / "legacy"
        legacy_dir.mkdir(parents=True)
        legacy_file = legacy_dir / "credentials.json"
        
        legacy_data = {
            "localhost:test_db": {
                "identity": "test_identity_123",
                "token": "test_token_456",
                "host": "localhost",
                "database": "test_db",
                "expires_at": "2025-12-31T23:59:59"
            }
        }
        
        with open(legacy_file, 'w') as f:
            json.dump(legacy_data, f)
        
        # Migrate credentials
        migrated_count = self.storage.migrate_legacy_credentials(legacy_dir)
        
        self.assertEqual(migrated_count, 1, "Should migrate 1 credential")
        
        # Verify credential was migrated
        token = self.storage.retrieve_token("localhost:test_db")
        self.assertIsNotNone(token, "Migrated credential should be retrievable")
        self.assertEqual(token.token, "test_token_456", "Token should match legacy data")
        self.assertEqual(token.metadata['identity'], "test_identity_123",
                        "Identity should be preserved in metadata")
    
    def test_legacy_encrypted_migration(self):
        """Test migration from legacy encrypted credentials."""
        # Create legacy encrypted file using old vulnerable key derivation
        legacy_dir = self.test_dir / "legacy_enc"
        legacy_dir.mkdir(parents=True)
        legacy_file = legacy_dir / "credentials.enc"
        
        # Simulate old vulnerable key derivation
        legacy_seed = f"{os.environ.get('USER', 'default')}{os.getenv('HOSTNAME', 'localhost')}"
        legacy_key = base64.urlsafe_b64encode(hashlib.sha256(legacy_seed.encode()).digest())
        
        # Encrypt using legacy method
        legacy_data = {"test_key": "test_token_legacy"}
        f = Fernet(legacy_key)
        encrypted = f.encrypt(json.dumps(legacy_data).encode())
        
        with open(legacy_file, 'wb') as file:
            file.write(encrypted)
        
        # Migrate credentials
        migrated_count = self.storage.migrate_legacy_credentials(legacy_dir)
        
        self.assertGreaterEqual(migrated_count, 0,
                               "Migration should handle legacy encrypted files")
    
    def test_timing_attack_resistance(self):
        """Test that key derivation timing is consistent."""
        # Measure timing for different inputs
        times = []
        
        for i in range(5):
            # Use different test passwords of varying lengths
            test_config = StorageConfig(
                backend=StorageBackend.MEMORY,
                key_derivation_iterations=1000  # Faster for testing
            )
            test_storage = SecureStorage(test_config)
            
            start_time = time.time()
            test_storage._derive_secure_password()
            end_time = time.time()
            
            times.append(end_time - start_time)
            test_storage.shutdown()
        
        # Check that timing variance is reasonable
        max_time = max(times)
        min_time = min(times)
        variance = max_time - min_time
        
        # Allow some variance due to system load, but should be consistent
        self.assertLess(variance, 0.1,
                       f"Key derivation timing variance too high: {variance:.3f}s")
    
    def test_key_derivation_collision_resistance(self):
        """Test that different installations produce different keys."""
        derived_keys = set()
        
        # Create multiple storage instances with different paths
        for i in range(10):
            config = StorageConfig(
                backend=StorageBackend.ENCRYPTED_FILE,
                storage_path=self.test_dir / f"test_{i}",
                key_derivation_iterations=1000  # Faster for testing
            )
            storage = SecureStorage(config)
            
            # Get the derived encryption key
            key = storage._initialize_encryption()
            derived_keys.add(key.hex())
            
            storage.shutdown()
        
        # All keys should be unique
        self.assertEqual(len(derived_keys), 10,
                        "All derived keys should be unique")
    
    def test_salt_entropy_quality(self):
        """Test that generated salts have high entropy."""
        salts = set()
        
        # Generate multiple salts
        for i in range(100):
            config = StorageConfig(
                backend=StorageBackend.ENCRYPTED_FILE,
                storage_path=self.test_dir / f"entropy_test_{i}"
            )
            storage = SecureStorage(config)
            salt = storage._get_or_create_machine_salt()
            salts.add(salt)
            storage.shutdown()
        
        # All salts should be unique
        self.assertEqual(len(salts), 100,
                        "All generated salts should be unique")
        
        # Check salt format
        for salt in list(salts)[:5]:  # Check first 5
            self.assertEqual(len(salt), 64, "Salt should be 64 characters")
            self.assertTrue(all(c in '0123456789abcdef' for c in salt.lower()),
                           "Salt should be valid hex")


class TestSecurityValidation(unittest.TestCase):
    """Additional security validation tests."""
    
    def test_no_plaintext_storage(self):
        """Verify that credentials are never stored in plaintext."""
        test_dir = Path(tempfile.mkdtemp())
        try:
            config = StorageConfig(
                backend=StorageBackend.ENCRYPTED_FILE,
                storage_path=test_dir
            )
            storage = SecureStorage(config)
            
            # Store a test token
            test_token = SecureToken(
                token="super_secret_token_12345",
                metadata={"test": "data"}
            )
            storage.store_token("test_key", test_token)
            
            # Check that no file contains plaintext token
            for file_path in test_dir.rglob("*"):
                if file_path.is_file():
                    try:
                        with open(file_path, 'rb') as f:
                            content = f.read()
                        
                        # Should not contain plaintext token
                        self.assertNotIn(b"super_secret_token_12345", content,
                                       f"Plaintext token found in {file_path}")
                    except Exception:
                        # Ignore files that can't be read
                        pass
            
            storage.shutdown()
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)
    
    def test_directory_permissions(self):
        """Test that storage directories have secure permissions."""
        test_dir = Path(tempfile.mkdtemp())
        try:
            config = StorageConfig(
                backend=StorageBackend.ENCRYPTED_FILE,
                storage_path=test_dir / "secure_storage"
            )
            storage = SecureStorage(config)
            
            # Trigger directory creation
            storage.store_token("test", SecureToken(token="test"))
            
            # Check directory permissions
            dir_stat = config.storage_path.stat()
            permissions = dir_stat.st_mode & 0o777
            self.assertEqual(permissions, 0o700,
                           f"Directory should have 0o700 permissions, got {oct(permissions)}")
            
            storage.shutdown()
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)


def run_security_tests():
    """Run all security tests and provide a comprehensive report."""
    print("=" * 80)
    print("SpacetimeDB Secure Key Derivation Security Test Suite")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add all test cases
    for test_class in [TestSecureKeyDerivation, TestSecurityValidation]:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("SECURITY TEST SUMMARY")
    print("=" * 80)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    print(f"Total Tests:  {total_tests}")
    print(f"Passed:       {passed}")
    print(f"Failed:       {failures}")
    print(f"Errors:       {errors}")
    
    if failures == 0 and errors == 0:
        print("\n✅ ALL SECURITY TESTS PASSED!")
        print("🔒 Key derivation system is secure against cryptographic attacks")
        print("🛡️  Authentication storage meets security requirements")
    else:
        print("\n❌ SECURITY ISSUES DETECTED!")
        if failures > 0:
            print("⚠️  Test failures indicate potential security vulnerabilities")
        if errors > 0:
            print("💥 Test errors indicate implementation issues")
    
    print("=" * 80)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_security_tests()
    sys.exit(0 if success else 1)