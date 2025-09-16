"""
Command Line Interface for SpacetimeDB Authentication Storage

This module provides a CLI for managing secure credential storage,
including migration from plaintext storage and credential management.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any

from .storage import SecureAuthStorage
from .migration import migrate_auth_storage, AuthStorageMigrator
from .migration_tools import AuthenticationMigrator
from .validators import TokenValidator, CredentialsValidator


def setup_logging(verbose: bool = False) -> None:
    """Set up logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def cmd_migrate(args: argparse.Namespace) -> int:
    """Handle migration command."""
    try:
        storage_dir = Path(args.storage_dir) if args.storage_dir else None
        
        print("SpacetimeDB Authentication Storage Migration")
        print("=" * 50)
        
        # Check if migration is needed
        migrator = AuthStorageMigrator(storage_dir)
        
        if not migrator.check_migration_needed():
            print("No migration needed. Encrypted storage is already active or no plaintext credentials found.")
            return 0
        
        # Analyze current storage
        print("\nAnalyzing current storage...")
        analysis = migrator.analyze_plaintext_storage()
        
        if 'error' in analysis:
            print(f"Error analyzing storage: {analysis['error']}")
            return 1
        
        print(f"Found {analysis['total_entries']} credential entries")
        print(f"Valid entries: {analysis['valid_entries']}")
        print(f"Invalid entries: {analysis['invalid_entries']}")
        
        if analysis['valid_entries'] == 0:
            print("No valid credentials to migrate.")
            return 0
        
        # Show details if verbose
        if args.verbose:
            print("\nCredential details:")
            for entry in analysis['entries']:
                status = "✓" if entry['valid'] else "✗"
                print(f"  {status} {entry['key']} - {entry.get('host', 'N/A')}/{entry.get('database', 'N/A')}")
                if entry['issues']:
                    for issue in entry['issues']:
                        print(f"    - {issue}")
        
        # Dry run if requested
        if args.dry_run:
            print("\nPerforming dry run...")
            results = migrate_auth_storage(storage_dir, dry_run=True)
            print(f"Would migrate {results['migrated_entries']} credentials")
            print(f"Would skip {results['skipped_entries']} credentials")
            print(f"Would fail {results['failed_entries']} credentials")
            return 0
        
        # Confirm migration
        if not args.yes:
            response = input(f"\nMigrate {analysis['valid_entries']} credentials to secure storage? (y/N): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                return 0
        
        # Perform migration
        print("\nPerforming migration...")
        results = migrate_auth_storage(storage_dir, dry_run=False)
        
        if results.get('status') == 'completed':
            print(f"✓ Migration completed successfully!")
            print(f"  Migrated: {results['migrated_entries']} credentials")
            print(f"  Skipped: {results['skipped_entries']} credentials")
            print(f"  Failed: {results['failed_entries']} credentials")
            
            if 'verification' in results:
                verification = results['verification']
                if verification['verification_passed']:
                    print("✓ Migration verification passed")
                else:
                    print("⚠ Migration verification failed")
                    if 'verification_error' in verification:
                        print(f"  Error: {verification['verification_error']}")
        else:
            print(f"✗ Migration failed: {results.get('message', 'Unknown error')}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"Migration error: {e}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """Handle list command."""
    try:
        storage_dir = Path(args.storage_dir) if args.storage_dir else None
        storage = SecureAuthStorage(storage_dir)
        
        credentials = storage.list_stored_credentials()
        
        if not credentials:
            print("No credentials found.")
            return 0
        
        print(f"Found {len(credentials)} stored credentials:")
        print()
        
        for key, info in credentials.items():
            status = "✓" if not info['is_expired'] else "✗ (expired)"
            age_hours = info['age_seconds'] / 3600
            print(f"{status} {key}")
            print(f"  Identity: {info['identity'][:8]}...")
            print(f"  Age: {age_hours:.1f} hours")
            if args.verbose:
                print(f"  Timestamp: {info['timestamp']}")
            print()
        
        return 0
        
    except Exception as e:
        print(f"List error: {e}")
        return 1


def cmd_remove(args: argparse.Namespace) -> int:
    """Handle remove command."""
    try:
        storage_dir = Path(args.storage_dir) if args.storage_dir else None
        storage = SecureAuthStorage(storage_dir)
        
        if args.all:
            if not args.yes:
                response = input("Remove ALL stored credentials? (y/N): ")
                if response.lower() != 'y':
                    print("Operation cancelled.")
                    return 0
            
            storage.clear_all_credentials()
            print("All credentials removed.")
        else:
            if not args.host or not args.database:
                print("Host and database are required for removing specific credentials.")
                return 1
            
            if storage.remove_credentials(args.host, args.database):
                print(f"Removed credentials for {args.host}/{args.database}")
            else:
                print(f"No credentials found for {args.host}/{args.database}")
        
        return 0
        
    except Exception as e:
        print(f"Remove error: {e}")
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle validate command."""
    try:
        if args.token:
            # Validate a specific token
            validator = TokenValidator()
            result = validator.validate_token(args.token)
            
            print(f"Token validation: {'✓ VALID' if result else '✗ INVALID'}")
            if result.message:
                print(f"Message: {result.message}")
            
            if args.verbose and result.details:
                print("Details:")
                for key, value in result.details.items():
                    print(f"  {key}: {value}")
            
        else:
            # Validate all stored credentials
            storage_dir = Path(args.storage_dir) if args.storage_dir else None
            storage = SecureAuthStorage(storage_dir)
            credentials = storage.list_stored_credentials()
            
            if not credentials:
                print("No credentials to validate.")
                return 0
            
            print(f"Validating {len(credentials)} stored credentials:")
            print()
            
            validator = CredentialsValidator()
            invalid_count = 0
            
            for key, info in credentials.items():
                # Get the actual credentials
                creds = storage.get_credentials(info['host'], info['database'], allow_expired=True)
                if not creds:
                    print(f"✗ {key} - Cannot retrieve credentials")
                    invalid_count += 1
                    continue
                
                # Validate credentials
                result = validator.validate_credentials(
                    creds.identity,
                    creds.token,
                    creds.host,
                    creds.database,
                    {'token_not_expired': not args.allow_expired}
                )
                
                status = "✓" if result else "✗"
                print(f"{status} {key} - {result.message}")
                
                if not result:
                    invalid_count += 1
                
                if args.verbose and result.details:
                    for detail_key, detail_value in result.details.items():
                        print(f"  {detail_key}: {detail_value}")
            
            print(f"\nValidation complete: {len(credentials) - invalid_count} valid, {invalid_count} invalid")
            
            if invalid_count > 0:
                return 1
        
        return 0
        
    except Exception as e:
        print(f"Validation error: {e}")
        return 1


def cmd_info(args: argparse.Namespace) -> int:
    """Handle info command."""
    try:
        storage_dir = Path(args.storage_dir) if args.storage_dir else None
        storage = SecureAuthStorage(storage_dir)
        
        info = storage.get_storage_info()
        
        print("SpacetimeDB Authentication Storage Information")
        print("=" * 50)
        print(f"Storage directory: {info['storage_dir']}")
        print(f"Using keyring: {info['using_keyring']}")
        print(f"Keyring available: {info['keyring_available']}")
        print(f"Cached credentials: {info['cached_credentials']}")
        print(f"Auto cleanup: {info['auto_cleanup']}")
        print(f"Max credential age: {info['max_credential_age_hours']} hours")
        
        if info['file_exists']:
            print(f"Encrypted file exists: Yes")
        else:
            print(f"Encrypted file exists: No")
        
        if args.verbose:
            print(f"Credentials file: {info['credentials_file']}")
            print(f"Cache loaded: {info['cache_loaded']}")
        
        return 0
        
    except Exception as e:
        print(f"Info error: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SpacetimeDB Authentication Storage Management",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--storage-dir',
        help='Storage directory (default: ~/.spacetimedb)',
        metavar='DIR'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Migration command
    migrate_parser = subparsers.add_parser('migrate', help='Migrate from plaintext to secure storage')
    migrate_parser.add_argument('--dry-run', action='store_true', help='Perform dry run without changes')
    migrate_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')
    migrate_parser.set_defaults(func=cmd_migrate)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List stored credentials')
    list_parser.set_defaults(func=cmd_list)
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove stored credentials')
    remove_parser.add_argument('--host', help='Host to remove credentials for')
    remove_parser.add_argument('--database', help='Database to remove credentials for')
    remove_parser.add_argument('--all', action='store_true', help='Remove all credentials')
    remove_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')
    remove_parser.set_defaults(func=cmd_remove)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate credentials or tokens')
    validate_parser.add_argument('--token', help='Specific token to validate')
    validate_parser.add_argument('--allow-expired', action='store_true', help='Allow expired credentials')
    validate_parser.set_defaults(func=cmd_validate)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show storage information')
    info_parser.set_defaults(func=cmd_info)
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())