"""
Migration Utility for SpacetimeDB Authentication Storage

This module provides utilities to migrate from plaintext credential storage
to encrypted storage, ensuring backward compatibility and data safety.
"""

import json
import logging
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from .storage import SecureAuthStorage, AuthCredentials


class MigrationError(Exception):
    """Exception raised during migration operations."""
    pass


class AuthStorageMigrator:
    """
    Migration utility for authentication storage.
    
    This class handles the migration from plaintext credential storage
    to encrypted storage, with safety checks and rollback capabilities.
    """
    
    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the migration utility.
        
        Args:
            storage_dir: Directory containing credentials (default: ~/.spacetimedb)
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(f"{__name__}.AuthStorageMigrator")
        
        # Set up storage directory
        if storage_dir is None:
            storage_dir = Path.home() / '.spacetimedb'
        
        self.storage_dir = Path(storage_dir)
        self.plaintext_file = self.storage_dir / 'credentials.json'
        self.backup_file = self.storage_dir / 'credentials.json.backup'
        self.migration_log_file = self.storage_dir / 'migration.log'
        
        # Migration state
        self.migration_completed = False
        self.backup_created = False
        self.credentials_migrated = 0
    
    def check_migration_needed(self) -> bool:
        """
        Check if migration is needed.
        
        Returns:
            True if migration is needed, False otherwise
        """
        # Check if plaintext file exists
        if not self.plaintext_file.exists():
            self.logger.info("No plaintext credentials file found")
            return False
        
        # Check if encrypted storage already exists
        secure_storage = SecureAuthStorage(self.storage_dir)
        storage_info = secure_storage.get_storage_info()
        
        if storage_info['file_exists'] and storage_info['cached_credentials'] > 0:
            self.logger.info("Encrypted storage already exists and has credentials")
            return False
        
        self.logger.info("Plaintext credentials found, migration needed")
        return True
    
    def analyze_plaintext_storage(self) -> Dict[str, Any]:
        """
        Analyze the plaintext storage file.
        
        Returns:
            Dictionary with analysis results
        """
        if not self.plaintext_file.exists():
            return {
                'file_exists': False,
                'error': 'Plaintext credentials file not found'
            }
        
        try:
            with open(self.plaintext_file, 'r') as f:
                data = json.load(f)
            
            analysis = {
                'file_exists': True,
                'file_size': self.plaintext_file.stat().st_size,
                'total_entries': len(data),
                'entries': [],
                'valid_entries': 0,
                'invalid_entries': 0
            }
            
            # Analyze each entry
            for key, entry_data in data.items():
                entry_info = {
                    'key': key,
                    'valid': False,
                    'issues': []
                }
                
                try:
                    # Try to create credentials object
                    credentials = AuthCredentials.from_dict(entry_data)
                    
                    # Check for required fields
                    if not credentials.identity:
                        entry_info['issues'].append('Missing identity')
                    elif len(credentials.identity) < 8:
                        entry_info['issues'].append('Identity too short')
                    
                    if not credentials.token:
                        entry_info['issues'].append('Missing token')
                    elif len(credentials.token) < 16:
                        entry_info['issues'].append('Token too short')
                    
                    if not credentials.host:
                        entry_info['issues'].append('Missing host')
                    
                    if not credentials.database:
                        entry_info['issues'].append('Missing database')
                    
                    # Check expiration
                    if credentials.is_expired():
                        entry_info['issues'].append('Credentials expired')
                    
                    if not entry_info['issues']:
                        entry_info['valid'] = True
                        analysis['valid_entries'] += 1
                    else:
                        analysis['invalid_entries'] += 1
                    
                    entry_info.update({
                        'identity': credentials.identity[:8] + '...' if credentials.identity else None,
                        'host': credentials.host,
                        'database': credentials.database,
                        'age_hours': credentials.age_seconds / 3600 if credentials.timestamp else None,
                        'expired': credentials.is_expired()
                    })
                    
                except Exception as e:
                    entry_info['issues'].append(f'Parse error: {str(e)}')
                    analysis['invalid_entries'] += 1
                
                analysis['entries'].append(entry_info)
            
            return analysis
            
        except Exception as e:
            return {
                'file_exists': True,
                'error': f'Failed to analyze plaintext file: {str(e)}'
            }
    
    def create_backup(self) -> bool:
        """
        Create a backup of the plaintext credentials file.
        
        Returns:
            True if backup was created successfully, False otherwise
        """
        if not self.plaintext_file.exists():
            self.logger.error("Cannot create backup: plaintext file does not exist")
            return False
        
        try:
            # Add timestamp to backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.storage_dir / f'credentials.json.backup_{timestamp}'
            
            shutil.copy2(self.plaintext_file, backup_file)
            
            # Also create a standard backup
            shutil.copy2(self.plaintext_file, self.backup_file)
            
            self.backup_created = True
            self.logger.info(f"Created backup: {backup_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False
    
    def migrate_credentials(
        self,
        secure_storage: Optional[SecureAuthStorage] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate credentials from plaintext to encrypted storage.
        
        Args:
            secure_storage: Secure storage instance (created if None)
            dry_run: If True, only simulate migration without making changes
            
        Returns:
            Dictionary with migration results
        """
        if not self.plaintext_file.exists():
            raise MigrationError("Plaintext credentials file not found")
        
        # Create secure storage if not provided
        if secure_storage is None:
            secure_storage = SecureAuthStorage(self.storage_dir)
        
        # Load plaintext data
        try:
            with open(self.plaintext_file, 'r') as f:
                plaintext_data = json.load(f)
        except Exception as e:
            raise MigrationError(f"Failed to load plaintext data: {e}")
        
        # Migration results
        results = {
            'dry_run': dry_run,
            'total_entries': len(plaintext_data),
            'migrated_entries': 0,
            'failed_entries': 0,
            'skipped_entries': 0,
            'entries': []
        }
        
        # Process each entry
        for key, entry_data in plaintext_data.items():
            entry_result = {
                'key': key,
                'status': 'unknown',
                'message': ''
            }
            
            try:
                # Parse credentials
                credentials = AuthCredentials.from_dict(entry_data)
                
                # Validate credentials
                if not credentials.identity or not credentials.token:
                    entry_result['status'] = 'skipped'
                    entry_result['message'] = 'Missing required fields'
                    results['skipped_entries'] += 1
                elif credentials.is_expired():
                    entry_result['status'] = 'skipped'
                    entry_result['message'] = 'Credentials expired'
                    results['skipped_entries'] += 1
                else:
                    # Migrate credentials
                    if not dry_run:
                        secure_storage.store_credentials(
                            credentials.identity,
                            credentials.token,
                            credentials.host,
                            credentials.database
                        )
                    
                    entry_result['status'] = 'migrated'
                    entry_result['message'] = 'Successfully migrated'
                    results['migrated_entries'] += 1
                    
                    # Add details
                    entry_result.update({
                        'identity': credentials.identity[:8] + '...',
                        'host': credentials.host,
                        'database': credentials.database
                    })
                    
            except Exception as e:
                entry_result['status'] = 'failed'
                entry_result['message'] = f'Migration failed: {str(e)}'
                results['failed_entries'] += 1
                self.logger.error(f"Failed to migrate entry {key}: {e}")
            
            results['entries'].append(entry_result)
        
        # Log migration summary
        if not dry_run:
            self.credentials_migrated = results['migrated_entries']
            self._log_migration_results(results)
        
        return results
    
    def _log_migration_results(self, results: Dict[str, Any]) -> None:
        """Log migration results to file."""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'migration_results': results,
                'migrator_version': '1.0.0'
            }
            
            with open(self.migration_log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            
            self.logger.info(f"Migration log saved to {self.migration_log_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save migration log: {e}")
    
    def complete_migration(self) -> bool:
        """
        Complete the migration by removing the plaintext file.
        
        Returns:
            True if migration was completed successfully, False otherwise
        """
        if not self.backup_created:
            self.logger.error("Cannot complete migration: backup was not created")
            return False
        
        if self.credentials_migrated == 0:
            self.logger.error("Cannot complete migration: no credentials were migrated")
            return False
        
        try:
            # Remove plaintext file
            if self.plaintext_file.exists():
                self.plaintext_file.unlink()
                self.logger.info("Removed plaintext credentials file")
            
            self.migration_completed = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to complete migration: {e}")
            return False
    
    def rollback_migration(self) -> bool:
        """
        Rollback the migration by restoring the plaintext file.
        
        Returns:
            True if rollback was successful, False otherwise
        """
        if not self.backup_file.exists():
            self.logger.error("Cannot rollback: backup file not found")
            return False
        
        try:
            # Restore plaintext file from backup
            shutil.copy2(self.backup_file, self.plaintext_file)
            
            # Remove encrypted storage (optional)
            encrypted_file = self.storage_dir / 'credentials.enc'
            if encrypted_file.exists():
                encrypted_file.unlink()
                self.logger.info("Removed encrypted credentials file")
            
            self.logger.info("Migration rolled back successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to rollback migration: {e}")
            return False
    
    def verify_migration(self) -> Dict[str, Any]:
        """
        Verify that the migration was successful.
        
        Returns:
            Dictionary with verification results
        """
        results = {
            'plaintext_file_removed': not self.plaintext_file.exists(),
            'backup_file_exists': self.backup_file.exists(),
            'encrypted_storage_exists': False,
            'encrypted_credentials_count': 0,
            'verification_passed': False
        }
        
        try:
            # Check encrypted storage
            secure_storage = SecureAuthStorage(self.storage_dir)
            storage_info = secure_storage.get_storage_info()
            
            results['encrypted_storage_exists'] = storage_info['file_exists']
            results['encrypted_credentials_count'] = storage_info['cached_credentials']
            
            # Verify that we can load and access credentials
            if results['encrypted_credentials_count'] > 0:
                stored_credentials = secure_storage.list_stored_credentials()
                results['accessible_credentials'] = len(stored_credentials)
                
                # Check if we can actually retrieve credentials
                for key, cred_info in stored_credentials.items():
                    host = cred_info['host']
                    database = cred_info['database']
                    retrieved = secure_storage.get_credentials(host, database)
                    if retrieved is None:
                        results['retrieval_error'] = f"Failed to retrieve credentials for {key}"
                        break
                else:
                    results['all_credentials_retrievable'] = True
            
            # Overall verification
            results['verification_passed'] = (
                results['plaintext_file_removed'] and
                results['backup_file_exists'] and
                results['encrypted_storage_exists'] and
                results['encrypted_credentials_count'] > 0 and
                results.get('all_credentials_retrievable', False)
            )
            
        except Exception as e:
            results['verification_error'] = str(e)
            self.logger.error(f"Migration verification failed: {e}")
        
        return results


def migrate_auth_storage(
    storage_dir: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to perform authentication storage migration.
    
    Args:
        storage_dir: Directory containing credentials (default: ~/.spacetimedb)
        dry_run: If True, only simulate migration without making changes
        force: If True, skip safety checks and force migration
        
    Returns:
        Dictionary with migration results
    """
    migrator = AuthStorageMigrator(storage_dir)
    
    # Check if migration is needed
    if not force and not migrator.check_migration_needed():
        return {
            'migration_needed': False,
            'message': 'Migration not needed'
        }
    
    # Analyze current storage
    analysis = migrator.analyze_plaintext_storage()
    if 'error' in analysis:
        return {
            'migration_needed': True,
            'error': analysis['error']
        }
    
    # Create backup (unless dry run)
    if not dry_run:
        if not migrator.create_backup():
            return {
                'migration_needed': True,
                'error': 'Failed to create backup'
            }
    
    # Perform migration
    try:
        migration_results = migrator.migrate_credentials(dry_run=dry_run)
        
        if not dry_run and migration_results['migrated_entries'] > 0:
            # Complete migration
            if migrator.complete_migration():
                # Verify migration
                verification_results = migrator.verify_migration()
                migration_results['verification'] = verification_results
                
                if verification_results['verification_passed']:
                    migration_results['status'] = 'completed'
                    migration_results['message'] = 'Migration completed successfully'
                else:
                    migration_results['status'] = 'completed_with_warnings'
                    migration_results['message'] = 'Migration completed but verification failed'
            else:
                migration_results['status'] = 'failed'
                migration_results['message'] = 'Migration failed to complete'
        else:
            migration_results['status'] = 'dry_run' if dry_run else 'no_migration'
            migration_results['message'] = 'Dry run completed' if dry_run else 'No credentials to migrate'
        
        return migration_results
        
    except Exception as e:
        return {
            'migration_needed': True,
            'error': f'Migration failed: {str(e)}'
        }