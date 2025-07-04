# SpacetimeDB Secure Authentication Storage Guide

## Overview

The SpacetimeDB Python SDK now includes a secure authentication storage system that replaces the previous plaintext credential storage with encrypted, cross-platform secure storage.

### Security Improvements

- **Encrypted Storage**: Credentials are encrypted using industry-standard encryption (Fernet with PBKDF2)
- **System Keyring Integration**: Uses OS-level credential storage (Keychain on macOS, Credential Manager on Windows, Secret Service on Linux)
- **Secure Key Derivation**: PBKDF2 with 100,000 iterations and random salt
- **Cross-platform Compatibility**: Works on all major operating systems
- **Automatic Migration**: Seamlessly migrates from plaintext storage

## Quick Start

### Installation

The secure storage system requires additional dependencies:

```bash
pip install keyring cryptography PyJWT
```

Or install with the secure storage extras:

```bash
pip install spacetimedb_sdk[secure-storage]
```

### Basic Usage

```python
from spacetimedb_sdk.auth import store_credentials, get_credentials

# Store credentials (automatically encrypted)
store_credentials(
    identity="abcdef1234567890abcdef1234567890abcdef12",
    token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    host="localhost:3000",
    database="my_database"
)

# Retrieve credentials
credentials = get_credentials("localhost:3000", "my_database")
if credentials:
    print(f"Identity: {credentials.identity}")
    print(f"Token: {credentials.token}")
```

### Migration from Old System

If you have existing plaintext credentials, they will be automatically migrated:

```python
from spacetimedb_sdk.auth.migration import migrate_auth_storage

# Automatic migration
result = migrate_auth_storage()
print(f"Migrated {result['migrated_entries']} credentials")
```

## Architecture

### Storage Backends

The system uses a tiered approach to credential storage:

1. **System Keyring (Preferred)**: Uses the operating system's secure credential storage
   - macOS: Keychain
   - Windows: Credential Manager
   - Linux: Secret Service (GNOME Keyring, KWallet)

2. **Encrypted File Storage (Fallback)**: When keyring is unavailable
   - Uses Fernet encryption with AES-128
   - PBKDF2 key derivation with 100,000 iterations
   - Random salt for each installation

### Security Features

#### Encryption Details

- **Algorithm**: Fernet (AES-128 in CBC mode with HMAC-SHA256)
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Salt**: 32-byte random salt, unique per installation
- **Master Password**: User-provided or automatically generated

#### File Permissions

- Storage directory: 0o700 (owner read/write/execute only)
- Credential files: 0o600 (owner read/write only)
- Salt file: 0o600 (owner read/write only)

## API Reference

### Core Classes

#### SecureAuthStorage

Main class for secure credential storage.

```python
from spacetimedb_sdk.auth import SecureAuthStorage

storage = SecureAuthStorage(
    storage_dir=None,  # Default: ~/.spacetimedb
    max_credential_age_hours=24.0,
    auto_cleanup=True,
    prefer_keyring=True
)

# Store credentials
storage.store_credentials(identity, token, host, database)

# Retrieve credentials
credentials = storage.get_credentials(host, database)

# Remove credentials
storage.remove_credentials(host, database)

# List all credentials
all_creds = storage.list_stored_credentials()

# Get storage information
info = storage.get_storage_info()
```

#### AuthCredentials

Represents authentication credentials.

```python
from spacetimedb_sdk.auth import AuthCredentials

creds = AuthCredentials(
    identity="hex_identity_string",
    token="jwt_or_auth_token",
    host="server_host",
    database="database_name"
)

# Check if expired
if creds.is_expired(max_age_hours=24.0):
    print("Credentials are expired")

# Get age
print(f"Credentials are {creds.age_seconds} seconds old")
```

### Authentication Providers

#### JWTAuthProvider

Handles JWT token creation and validation.

```python
from spacetimedb_sdk.auth.providers import JWTAuthProvider

provider = JWTAuthProvider(
    secret_key="your_secret_key",
    algorithm="HS256",
    token_lifetime_hours=24.0
)

# Create token
token = provider.create_token(
    identity="user_identity",
    audience="spacetimedb",
    issuer="your_app"
)

# Validate token
is_valid = provider.validate_token(token)

# Extract identity
identity = provider.extract_identity(token)

# Check expiration
is_expired = provider.is_token_expired(token)
```

#### IdentityAuthProvider

Handles simple identity-based authentication.

```python
from spacetimedb_sdk.auth.providers import IdentityAuthProvider

provider = IdentityAuthProvider(token_lifetime_hours=24.0)

# Create identity token
token = provider.create_token("user_identity")

# Validate token
is_valid = provider.validate_token(token)
```

### Validators

#### TokenValidator

Validates authentication tokens.

```python
from spacetimedb_sdk.auth.validators import TokenValidator

validator = TokenValidator()

# Validate any token (auto-detects type)
result = validator.validate_token(token)
print(f"Valid: {result.is_valid}")
print(f"Message: {result.message}")

# Validate specific token types
jwt_result = validator.validate_jwt_token(jwt_token)
identity_result = validator.validate_identity_token(identity_token)
```

#### CredentialsValidator

Validates complete credential sets.

```python
from spacetimedb_sdk.auth.validators import CredentialsValidator

validator = CredentialsValidator()

# Validate credentials
result = validator.validate_credentials(
    identity="hex_string",
    token="auth_token",
    host="localhost:3000",
    database="test_db"
)

if result.is_valid:
    print("Credentials are valid")
else:
    print(f"Validation failed: {result.message}")
```

## Migration Guide

### From Old auth_storage Module

The old `auth_storage` module is now deprecated but remains functional with automatic migration:

```python
# Old way (deprecated, but still works)
from spacetimedb_sdk.auth_storage import store_credentials, get_credentials

# New way (recommended)
from spacetimedb_sdk.auth import store_credentials, get_credentials
```

### Automatic Migration

The system automatically detects and migrates plaintext credentials:

1. When you first use the new secure storage
2. Existing plaintext credentials are encrypted
3. Original file is backed up and removed
4. All operations transparently use secure storage

### Manual Migration

For more control over the migration process:

```python
from spacetimedb_sdk.auth.migration import AuthStorageMigrator

migrator = AuthStorageMigrator()

# Check if migration is needed
if migrator.check_migration_needed():
    # Analyze current storage
    analysis = migrator.analyze_plaintext_storage()
    print(f"Found {analysis['valid_entries']} valid credentials")
    
    # Create backup
    migrator.create_backup()
    
    # Perform migration
    results = migrator.migrate_credentials()
    
    # Complete migration
    migrator.complete_migration()
    
    # Verify migration
    verification = migrator.verify_migration()
    if verification['verification_passed']:
        print("Migration successful!")
```

## CLI Tools

The package includes a command-line interface for managing credentials:

### Installation

```bash
python -m spacetimedb_sdk.auth.cli --help
```

### Commands

#### Migrate Credentials

```bash
# Dry run migration
python -m spacetimedb_sdk.auth.cli migrate --dry-run

# Perform migration
python -m spacetimedb_sdk.auth.cli migrate --yes

# Verbose migration
python -m spacetimedb_sdk.auth.cli migrate --verbose
```

#### List Credentials

```bash
# List all stored credentials
python -m spacetimedb_sdk.auth.cli list

# Verbose listing
python -m spacetimedb_sdk.auth.cli list --verbose
```

#### Remove Credentials

```bash
# Remove specific credentials
python -m spacetimedb_sdk.auth.cli remove --host localhost:3000 --database test_db

# Remove all credentials
python -m spacetimedb_sdk.auth.cli remove --all --yes
```

#### Validate Credentials

```bash
# Validate all stored credentials
python -m spacetimedb_sdk.auth.cli validate

# Validate specific token
python -m spacetimedb_sdk.auth.cli validate --token "eyJhbGci..."

# Allow expired credentials
python -m spacetimedb_sdk.auth.cli validate --allow-expired
```

#### Storage Information

```bash
# Show storage information
python -m spacetimedb_sdk.auth.cli info

# Verbose information
python -m spacetimedb_sdk.auth.cli info --verbose
```

## Security Best Practices

### For Developers

1. **Use the New API**: Migrate to `spacetimedb_sdk.auth` from `spacetimedb_sdk.auth_storage`
2. **Handle Migration**: Test your application with both old and new credential formats
3. **Validate Tokens**: Use the provided validators for token validation
4. **Error Handling**: Handle cases where credentials are unavailable or expired

### For Users

1. **Master Password**: Choose a strong master password when prompted
2. **Backup**: Keep a backup of your credentials before migration
3. **Permissions**: Ensure your home directory has appropriate permissions
4. **System Security**: Keep your operating system and keyring software updated

### For System Administrators

1. **Dependencies**: Ensure keyring libraries are available in production
2. **Fallback**: Test encrypted file storage fallback scenarios
3. **Monitoring**: Monitor for deprecation warnings in logs
4. **Migration**: Plan migration during maintenance windows

## Troubleshooting

### Common Issues

#### Keyring Not Available

```
Warning: Keyring not available, falling back to encrypted file storage
```

**Solution**: Install keyring backend for your system:
- Linux: `sudo apt-get install python3-keyring`
- macOS: Keyring is built-in
- Windows: Keyring is built-in

#### Permission Errors

```
Error: Permission denied accessing storage directory
```

**Solutions**:
1. Check directory permissions: `ls -la ~/.spacetimedb`
2. Fix permissions: `chmod 700 ~/.spacetimedb`
3. Check ownership: `ls -la ~/ | grep spacetimedb`

#### Migration Failures

```
Error: Migration failed: Cannot read plaintext file
```

**Solutions**:
1. Check file exists: `ls -la ~/.spacetimedb/credentials.json`
2. Check file format: Ensure it's valid JSON
3. Manual recovery: Use the CLI tool with `--verbose` for details

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from spacetimedb_sdk.auth import SecureAuthStorage
storage = SecureAuthStorage()
```

### Recovery Procedures

#### Restore from Backup

If migration fails, restore from automatic backup:

```bash
cd ~/.spacetimedb
cp credentials.json.backup credentials.json
```

#### Reset Storage

To start fresh (destroys all stored credentials):

```bash
rm -rf ~/.spacetimedb
```

## Performance Considerations

### Storage Performance

- **Keyring**: Fastest, native OS performance
- **Encrypted File**: Slightly slower due to encryption/decryption
- **Cache**: In-memory cache reduces file system access

### Migration Performance

- **Small datasets** (< 100 credentials): Near-instantaneous
- **Large datasets** (> 1000 credentials): May take several seconds
- **Network storage**: Slower on network-mounted home directories

## Future Enhancements

Planned improvements for future versions:

1. **Hardware Security Modules**: Support for HSM-based credential storage
2. **Multi-factor Authentication**: Support for MFA-protected credentials
3. **Credential Sharing**: Secure credential sharing between applications
4. **Cloud Synchronization**: Optional cloud-based credential synchronization
5. **Audit Logging**: Detailed audit logs for credential access

## Contributing

To contribute to the secure authentication system:

1. **Security Reviews**: Report security vulnerabilities privately
2. **Testing**: Test on different operating systems and configurations
3. **Documentation**: Improve documentation and examples
4. **Features**: Propose and implement new security features

## Support

For issues with the secure authentication system:

1. **GitHub Issues**: Report bugs and feature requests
2. **Security Issues**: Email security@clockworklabs.io for vulnerabilities
3. **Documentation**: Refer to this guide and inline documentation
4. **Community**: Ask questions in the SpacetimeDB community forums