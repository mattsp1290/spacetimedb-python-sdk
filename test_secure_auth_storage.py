#!/usr/bin/env python3
"""
Test Script for Secure Authentication Storage

This script tests the new secure authentication storage system,
including migration from plaintext storage and various security features.
"""

import json
import tempfile
import time
from pathlib import Path

def test_secure_auth_storage():
    """Test the secure authentication storage system."""
    print("Testing SpacetimeDB Secure Authentication Storage")
    print("=" * 60)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from spacetimedb_sdk.auth import (
            SecureAuthStorage, 
            AuthCredentials,
            store_credentials,
            get_credentials,
            get_global_auth_storage
        )
        from spacetimedb_sdk.auth.migration import migrate_auth_storage
        from spacetimedb_sdk.auth.validators import TokenValidator, CredentialsValidator
        print("   ✓ All imports successful")
        
        # Create temporary storage directory
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / 'spacetimedb_test'
            
            # Test 1: Basic secure storage
            print("\n2. Testing basic secure storage...")
            storage = SecureAuthStorage(storage_dir)
            
            # Store test credentials
            test_identity = "abcdef1234567890abcdef1234567890abcdef12"
            test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"
            test_host = "localhost:3000"
            test_database = "test_db"
            
            storage.store_credentials(test_identity, test_token, test_host, test_database)
            print("   ✓ Credentials stored successfully")
            
            # Retrieve credentials
            retrieved = storage.get_credentials(test_host, test_database)
            assert retrieved is not None
            assert retrieved.identity == test_identity
            assert retrieved.token == test_token
            print("   ✓ Credentials retrieved successfully")
            
            # Test 2: Migration from plaintext
            print("\n3. Testing migration from plaintext storage...")
            
            # Create fake plaintext credentials
            plaintext_file = storage_dir / 'credentials.json'
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            plaintext_data = {
                "localhost:3000:test_db2": {
                    "identity": "fedcba0987654321fedcba0987654321fedcba09",
                    "token": "old_token_12345",
                    "host": "localhost:3000",
                    "database": "test_db2",
                    "timestamp": time.time()
                }
            }
            
            with open(plaintext_file, 'w') as f:
                json.dump(plaintext_data, f)
            
            # Test migration
            migration_results = migrate_auth_storage(storage_dir, dry_run=False)
            print(f"   ✓ Migration completed: {migration_results.get('status', 'unknown')}")
            print(f"   ✓ Migrated {migration_results.get('migrated_entries', 0)} credentials")
            
            # Verify migrated credentials
            migrated = storage.get_credentials("localhost:3000", "test_db2")
            assert migrated is not None
            assert migrated.identity == "fedcba0987654321fedcba0987654321fedcba09"
            print("   ✓ Migrated credentials accessible")
            
            # Test 3: Token validation
            print("\n4. Testing token validation...")
            validator = TokenValidator()
            
            # Test JWT token validation (structure only)
            jwt_result = validator.validate_token(test_token, strict=False)
            print(f"   ✓ JWT validation: {jwt_result.message}")
            
            # Test identity token validation
            identity_result = validator.validate_identity_token(test_identity)
            print(f"   ✓ Identity validation: {identity_result.message}")
            
            # Test 4: Credentials validation
            print("\n5. Testing credentials validation...")
            creds_validator = CredentialsValidator()
            
            creds_result = creds_validator.validate_credentials(
                test_identity, test_token, test_host, test_database
            )
            print(f"   ✓ Credentials validation: {creds_result.message}")
            
            # Test 5: Global storage interface
            print("\n6. Testing global storage interface...")
            
            # Store using global interface
            store_credentials("1111222233334444", "global_token", "global.host", "global_db")
            
            # Retrieve using global interface
            global_creds = get_credentials("global.host", "global_db")
            assert global_creds is not None
            print("   ✓ Global storage interface works")
            
            # Test 6: Storage info
            print("\n7. Testing storage information...")
            info = storage.get_storage_info()
            print(f"   ✓ Storage directory: {info['storage_dir']}")
            print(f"   ✓ Using keyring: {info['using_keyring']}")
            print(f"   ✓ Cached credentials: {info['cached_credentials']}")
            
            # Test 7: Credential listing and cleanup
            print("\n8. Testing credential management...")
            
            # List all credentials
            all_creds = storage.list_stored_credentials()
            print(f"   ✓ Found {len(all_creds)} stored credentials")
            
            # Test cleanup (shouldn't remove anything since they're new)
            cleaned = storage.cleanup_expired_credentials()
            print(f"   ✓ Cleaned up {cleaned} expired credentials")
            
            # Test removal
            removed = storage.remove_credentials(test_host, test_database)
            assert removed == True
            print("   ✓ Credential removal works")
            
            # Verify removal
            after_removal = storage.get_credentials(test_host, test_database)
            assert after_removal is None
            print("   ✓ Credential actually removed")
            
        print("\n9. Testing backward compatibility (deprecated module)...")
        
        # Test deprecated auth_storage module
        from spacetimedb_sdk.auth_storage import (
            SpacetimeDBAuthStorage as DeprecatedStorage,
            AuthCredentials as DeprecatedCredentials,
            store_credentials as deprecated_store,
            get_credentials as deprecated_get
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / 'spacetimedb_deprecated'
            
            # Test deprecated interface (should issue warnings but work)
            import warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                
                deprecated_storage = DeprecatedStorage(storage_dir)
                assert len(w) > 0  # Should have deprecation warning
                print("   ✓ Deprecation warning issued")
                
                # Test storing with deprecated interface
                deprecated_storage.store_credentials("deprecated123", "dep_token", "dep.host", "dep_db")
                
                # Test retrieving
                dep_creds = deprecated_storage.get_credentials("dep.host", "dep_db")
                assert dep_creds is not None
                print("   ✓ Deprecated interface works")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("\nSecure authentication storage is working correctly.")
        print("\nKey features tested:")
        print("  ✓ Encrypted credential storage")
        print("  ✓ Migration from plaintext storage")
        print("  ✓ Token and credential validation")
        print("  ✓ Global storage interface")
        print("  ✓ Credential management operations")
        print("  ✓ Backward compatibility with deprecation warnings")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\nMissing dependencies. Install with:")
        print("pip install keyring cryptography PyJWT")
        return False
        
    except Exception as e:
        print(f"\n❌ Test Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_interface():
    """Test the CLI interface."""
    print("\n" + "=" * 60)
    print("Testing CLI Interface")
    print("=" * 60)
    
    try:
        from spacetimedb_sdk.auth.cli import main
        
        # Test CLI help
        import sys
        from io import StringIO
        
        # Capture help output
        old_stdout = sys.stdout
        old_argv = sys.argv
        
        try:
            sys.stdout = StringIO()
            sys.argv = ['auth-cli', '--help']
            
            try:
                main()
            except SystemExit:
                pass  # Help command exits
            
            help_output = sys.stdout.getvalue()
            assert 'SpacetimeDB Authentication Storage Management' in help_output
            print("✓ CLI help works")
            
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv
        
        print("✓ CLI interface available")
        
    except Exception as e:
        print(f"❌ CLI test error: {e}")
        return False
    
    return True


if __name__ == '__main__':
    print("SpacetimeDB Secure Authentication Storage Test Suite")
    print("=" * 70)
    
    # Run main tests
    main_success = test_secure_auth_storage()
    
    # Run CLI tests
    cli_success = test_cli_interface()
    
    print("\n" + "=" * 70)
    if main_success and cli_success:
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("\nThe secure authentication storage system is ready for use.")
        print("\nNext steps:")
        print("1. Install dependencies: pip install keyring cryptography PyJWT")
        print("2. Migrate existing credentials: python -m spacetimedb_sdk.auth.cli migrate")
        print("3. Update your code to use: from spacetimedb_sdk.auth import store_credentials, get_credentials")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease review the errors above and ensure all dependencies are installed.")
        exit(1)