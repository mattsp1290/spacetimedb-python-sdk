"""
Authentication Migration Tools for SpacetimeDB Python SDK

This module provides comprehensive utilities for migrating from deprecated
authentication storage implementations to the secure auth/storage.py system.
"""

import json
import logging
import os
import shutil
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set

from .storage import SecureAuthStorage, AuthCredentials
from ..utils.error_formatting import ErrorFormatter


class AuthenticationMigrator:
    """
    Comprehensive migration utility for consolidating authentication storage.
    
    This class handles migration from all deprecated authentication storage
    implementations to the modern secure storage system, with comprehensive
    validation and rollback capabilities.
    """
    
    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the authentication migrator.
        
        Args:
            storage_dir: Directory containing credentials (default: ~/.spacetimedb)
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(f"{__name__}.AuthenticationMigrator")
        
        # Set up storage directory
        if storage_dir is None:
            storage_dir = Path.home() / '.spacetimedb'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Legacy file paths
        self.legacy_files = {
            'plaintext': self.storage_dir / 'credentials.json',
            'deprecated_backup': self.storage_dir / 'credentials.json.backup',
        }
        
        # Modern storage paths
        self.modern_files = {
            'encrypted': self.storage_dir / 'credentials.enc',
            'salt': self.storage_dir / 'salt',
        }
        
        # Migration tracking
        self.migration_log_file = self.storage_dir / 'auth_migration.log'
        self.backup_dir = self.storage_dir / 'migration_backups'
        
        # Migration state
        self.migration_completed = False
        self.backups_created = False
        self.credentials_migrated = 0
        
        # Deprecation warning utilities
        self._deprecation_warnings_issued = set()
    
    def issue_deprecation_warning(self, module_name: str, stacklevel: int = 3) -> None:
        """
        Issue a deprecation warning for legacy auth module usage.
        
        Args:
            module_name: Name of the deprecated module
            stacklevel: Stack level for warning
        """
        if module_name in self._deprecation_warnings_issued:
            return
        
        message = f"""
The {module_name} module is deprecated and will be removed in a future version.
Please migrate to the new secure auth package:

from spacetimedb_sdk.auth import store_credentials, get_credentials

For automatic migration, run:
from spacetimedb_sdk.auth.migration_tools import AuthenticationMigrator
migrator = AuthenticationMigrator()
migrator.migrate_all_storage()
"""
        
        warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)
        self._deprecation_warnings_issued.add(module_name)
    
    def check_migration_status(self) -> Dict[str, Any]:
        """
        Check the current migration status of the authentication storage.
        
        Returns:
            Dictionary with detailed migration status
        """
        status = {
            'migration_needed': False,
            'legacy_files_found': [],
            'modern_storage_exists': False,
            'modern_credentials_count': 0,
            'migration_completed': False,
            'issues': []
        }
        
        # Check for legacy files
        for file_type, file_path in self.legacy_files.items():
            if file_path.exists():
                status['legacy_files_found'].append({
                    'type': file_type,
                    'path': str(file_path),
                    'size': file_path.stat().st_size,
                    'modified': file_path.stat().st_mtime
                })
                status['migration_needed'] = True
        
        # Check modern storage
        try:
            secure_storage = SecureAuthStorage(self.storage_dir)
            storage_info = secure_storage.get_storage_info()
            
            status['modern_storage_exists'] = storage_info['file_exists']
            status['modern_credentials_count'] = storage_info['cached_credentials']
            
            if status['modern_storage_exists'] and status['modern_credentials_count'] > 0:
                status['migration_completed'] = True
        except Exception as e:
            status['issues'].append(f"Failed to check modern storage: {e}")
        
        # Check for previous migration logs
        if self.migration_log_file.exists():
            try:
                with open(self.migration_log_file, 'r') as f:
                    log_data = json.load(f)
                status['previous_migration'] = log_data
            except Exception as e:
                status['issues'].append(f"Failed to read migration log: {e}")
        
        return status
    
    def analyze_legacy_storage(self) -> Dict[str, Any]:
        """
        Analyze all legacy storage files for migration planning.
        
        Returns:
            Dictionary with detailed analysis of legacy storage
        """
        analysis = {
            'total_legacy_files': 0,
            'total_credentials': 0,
            'valid_credentials': 0,
            'invalid_credentials': 0,
            'expired_credentials': 0,
            'files': {},
            'migration_feasible': True,
            'issues': []
        }
        
        # Analyze each legacy file
        for file_type, file_path in self.legacy_files.items():
            if not file_path.exists():
                continue
            
            analysis['total_legacy_files'] += 1
            file_analysis = self._analyze_credentials_file(file_path)
            analysis['files'][file_type] = file_analysis
            
            # Accumulate totals
            analysis['total_credentials'] += file_analysis.get('total_entries', 0)
            analysis['valid_credentials'] += file_analysis.get('valid_entries', 0)
            analysis['invalid_credentials'] += file_analysis.get('invalid_entries', 0)
            analysis['expired_credentials'] += file_analysis.get('expired_entries', 0)
            
            if 'error' in file_analysis:
                analysis['issues'].append(f"{file_type}: {file_analysis['error']}")
                analysis['migration_feasible'] = False
        
        return analysis
    
    def _analyze_credentials_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single credentials file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            analysis = {
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'total_entries': len(data),
                'valid_entries': 0,
                'invalid_entries': 0,
                'expired_entries': 0,
                'entries_details': []
            }
            
            # Analyze each credential entry
            for key, entry_data in data.items():
                entry_info = {
                    'key': key,
                    'valid': False,
                    'expired': False,
                    'issues': []
                }
                
                try:
                    credentials = AuthCredentials.from_dict(entry_data)
                    
                    # Validate credentials
                    if not credentials.identity or len(credentials.identity) < 8:
                        entry_info['issues'].append('Invalid identity')
                    
                    if not credentials.token or len(credentials.token) < 16:
                        entry_info['issues'].append('Invalid token')
                    
                    if not credentials.host:
                        entry_info['issues'].append('Missing host')
                    
                    if not credentials.database:
                        entry_info['issues'].append('Missing database')
                    
                    # Check expiration
                    if credentials.is_expired():
                        entry_info['expired'] = True
                        analysis['expired_entries'] += 1
                    
                    if not entry_info['issues']:
                        entry_info['valid'] = True
                        analysis['valid_entries'] += 1
                    else:
                        analysis['invalid_entries'] += 1
                    
                    entry_info.update({
                        'identity': credentials.identity[:8] + '...' if credentials.identity else None,
                        'host': credentials.host,
                        'database': credentials.database,
                        'age_hours': credentials.age_seconds / 3600 if credentials.timestamp else None
                    })
                    
                except Exception as e:
                    entry_info['issues'].append(f'Parse error: {str(e)}')
                    analysis['invalid_entries'] += 1
                
                analysis['entries_details'].append(entry_info)
            
            return analysis
            
        except Exception as e:
            return {
                'file_path': str(file_path),
                'error': f'Failed to analyze file: {str(e)}'
            }
    
    def create_migration_backups(self) -> bool:
        """
        Create comprehensive backups of all authentication files before migration.
        
        Returns:
            True if backups were created successfully, False otherwise
        """
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(mode=0o700)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_success = True
        
        try:
            # Backup all legacy files
            for file_type, file_path in self.legacy_files.items():
                if file_path.exists():
                    backup_path = self.backup_dir / f"{file_type}_{timestamp}.json"
                    shutil.copy2(file_path, backup_path)
                    os.chmod(backup_path, 0o600)  # Secure permissions
                    self.logger.info(f"Backed up {file_type} to {backup_path}")
            
            # Backup any existing modern storage files
            for file_type, file_path in self.modern_files.items():
                if file_path.exists():
                    backup_path = self.backup_dir / f"modern_{file_type}_{timestamp}"
                    if file_type == 'encrypted':
                        backup_path = backup_path.with_suffix('.enc')
                    shutil.copy2(file_path, backup_path)
                    os.chmod(backup_path, 0o600)
                    self.logger.info(f"Backed up modern {file_type} to {backup_path}")
            
            # Create backup manifest
            manifest = {
                'timestamp': timestamp,
                'backup_dir': str(self.backup_dir),
                'files_backed_up': [],
                'migration_version': '1.0.0'
            }
            
            for backup_file in self.backup_dir.glob(f"*_{timestamp}*"):
                manifest['files_backed_up'].append(str(backup_file))
            
            manifest_path = self.backup_dir / f"migration_manifest_{timestamp}.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            self.backups_created = True
            self.logger.info(f"Migration backups created in {self.backup_dir}")
            
        except Exception as e:
            self.logger.error(f"Failed to create migration backups: {e}")
            backup_success = False
        
        return backup_success
    
    def migrate_all_storage(
        self,
        secure_storage: Optional[SecureAuthStorage] = None,
        dry_run: bool = False,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate all legacy authentication storage to modern secure storage.
        
        Args:
            secure_storage: Secure storage instance (created if None)
            dry_run: If True, only simulate migration without making changes
            force: If True, skip safety checks and force migration
            
        Returns:
            Dictionary with comprehensive migration results
        """
        results = {
            'migration_started': datetime.now().isoformat(),
            'dry_run': dry_run,
            'force': force,
            'total_files_processed': 0,
            'total_credentials_found': 0,
            'credentials_migrated': 0,
            'credentials_failed': 0,
            'credentials_skipped': 0,
            'files_processed': {},
            'migration_successful': False,
            'issues': []
        }
        
        try:
            # Check migration status
            status = self.check_migration_status()
            if not force and not status['migration_needed']:
                results['message'] = 'No migration needed'
                results['migration_successful'] = True
                return results
            
            # Analyze legacy storage
            analysis = self.analyze_legacy_storage()
            if not analysis['migration_feasible'] and not force:
                results['error'] = 'Migration not feasible due to invalid data'
                results['analysis'] = analysis
                return results
            
            # Create backups (unless dry run)
            if not dry_run:
                if not self.create_migration_backups():
                    results['error'] = 'Failed to create migration backups'
                    return results
            
            # Create secure storage if not provided
            if secure_storage is None:
                secure_storage = SecureAuthStorage(self.storage_dir)
            
            # Process each legacy file
            for file_type, file_path in self.legacy_files.items():
                if not file_path.exists():
                    continue
                
                results['total_files_processed'] += 1
                file_results = self._migrate_credentials_file(
                    file_path, secure_storage, dry_run
                )
                
                results['files_processed'][file_type] = file_results
                results['total_credentials_found'] += file_results.get('total_credentials', 0)
                results['credentials_migrated'] += file_results.get('migrated', 0)
                results['credentials_failed'] += file_results.get('failed', 0)
                results['credentials_skipped'] += file_results.get('skipped', 0)
            
            # Finalize migration
            if not dry_run and results['credentials_migrated'] > 0:
                self._finalize_migration(results)
                results['migration_successful'] = True
            elif dry_run:
                results['migration_successful'] = True
                results['message'] = 'Dry run completed successfully'
            else:
                results['message'] = 'No credentials were migrated'
            
            # Log results
            self._log_migration_results(results)
            
        except Exception as e:
            results['error'] = f'Migration failed: {str(e)}'
            results['exception'] = ErrorFormatter.format_auth_error("migration", e)
            self.logger.error(f"Migration failed: {e}")
        
        return results
    
    def _migrate_credentials_file(
        self,
        file_path: Path,
        secure_storage: SecureAuthStorage,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Migrate credentials from a single file."""
        results = {
            'file_path': str(file_path),
            'total_credentials': 0,
            'migrated': 0,
            'failed': 0,
            'skipped': 0,
            'credentials': []
        }
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            results['total_credentials'] = len(data)
            
            for key, entry_data in data.items():
                cred_result = {
                    'key': key,
                    'status': 'unknown',
                    'message': ''
                }
                
                try:
                    credentials = AuthCredentials.from_dict(entry_data)
                    
                    # Validate credentials
                    if not self._validate_credentials(credentials):
                        cred_result['status'] = 'skipped'
                        cred_result['message'] = 'Invalid credentials'
                        results['skipped'] += 1
                    elif credentials.is_expired():
                        cred_result['status'] = 'skipped'
                        cred_result['message'] = 'Expired credentials'
                        results['skipped'] += 1
                    else:
                        # Migrate credentials
                        if not dry_run:
                            secure_storage.store_credentials(
                                credentials.identity,
                                credentials.token,
                                credentials.host,
                                credentials.database
                            )
                        
                        cred_result['status'] = 'migrated'
                        cred_result['message'] = 'Successfully migrated'
                        results['migrated'] += 1
                        
                        cred_result.update({
                            'identity': credentials.identity[:8] + '...',
                            'host': credentials.host,
                            'database': credentials.database
                        })
                
                except Exception as e:
                    cred_result['status'] = 'failed'
                    cred_result['message'] = f'Migration failed: {str(e)}'
                    results['failed'] += 1
                
                results['credentials'].append(cred_result)
        
        except Exception as e:
            results['error'] = f'Failed to process file: {str(e)}'
        
        return results
    
    def _validate_credentials(self, credentials: AuthCredentials) -> bool:
        """Validate credentials for migration."""
        return (
            credentials.identity and len(credentials.identity) >= 8 and
            credentials.token and len(credentials.token) >= 16 and
            credentials.host and
            credentials.database
        )
    
    def _finalize_migration(self, results: Dict[str, Any]) -> None:
        """Finalize the migration by cleaning up legacy files."""
        try:
            # Remove legacy files after successful migration
            for file_type, file_path in self.legacy_files.items():
                if file_path.exists():
                    file_path.unlink()
                    self.logger.info(f"Removed legacy file: {file_path}")
            
            self.migration_completed = True
            self.credentials_migrated = results['credentials_migrated']
            
        except Exception as e:
            results['finalization_error'] = str(e)
            self.logger.error(f"Failed to finalize migration: {e}")
    
    def _log_migration_results(self, results: Dict[str, Any]) -> None:
        """Log migration results to file."""
        try:
            log_data = {
                'migration_timestamp': datetime.now().isoformat(),
                'migration_results': results,
                'migrator_version': '1.0.0',
                'python_sdk_version': getattr(__import__('spacetimedb_sdk'), '__version__', 'unknown')
            }
            
            with open(self.migration_log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            
            os.chmod(self.migration_log_file, 0o600)
            self.logger.info(f"Migration log saved to {self.migration_log_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save migration log: {e}")
    
    def verify_migration(self) -> Dict[str, Any]:
        """
        Verify that the migration was successful and complete.
        
        Returns:
            Dictionary with comprehensive verification results
        """
        verification = {
            'verification_timestamp': datetime.now().isoformat(),
            'legacy_files_removed': True,
            'modern_storage_functional': False,
            'all_credentials_accessible': False,
            'verification_passed': False,
            'issues': []
        }
        
        try:
            # Check that legacy files are removed
            for file_type, file_path in self.legacy_files.items():
                if file_path.exists():
                    verification['legacy_files_removed'] = False
                    verification['issues'].append(f"Legacy file still exists: {file_path}")
            
            # Verify modern storage
            secure_storage = SecureAuthStorage(self.storage_dir)
            storage_info = secure_storage.get_storage_info()
            
            if storage_info['file_exists'] and storage_info['cached_credentials'] > 0:
                verification['modern_storage_functional'] = True
                
                # Test credential access
                stored_credentials = secure_storage.list_stored_credentials()
                accessible_count = 0
                
                for key, cred_info in stored_credentials.items():
                    try:
                        retrieved = secure_storage.get_credentials(
                            cred_info['host'], cred_info['database']
                        )
                        if retrieved:
                            accessible_count += 1
                    except Exception as e:
                        verification['issues'].append(f"Failed to retrieve {key}: {e}")
                
                if accessible_count == len(stored_credentials):
                    verification['all_credentials_accessible'] = True
                else:
                    verification['issues'].append(
                        f"Only {accessible_count}/{len(stored_credentials)} credentials accessible"
                    )
            else:
                verification['issues'].append("Modern storage not functional or empty")
            
            # Overall verification
            verification['verification_passed'] = (
                verification['legacy_files_removed'] and
                verification['modern_storage_functional'] and
                verification['all_credentials_accessible']
            )
            
        except Exception as e:
            verification['issues'].append(f"Verification failed: {str(e)}")
            self.logger.error(f"Migration verification failed: {e}")
        
        return verification
    
    def rollback_migration(self) -> Dict[str, Any]:
        """
        Rollback the migration by restoring from backups.
        
        Returns:
            Dictionary with rollback results
        """
        rollback_results = {
            'rollback_timestamp': datetime.now().isoformat(),
            'files_restored': [],
            'rollback_successful': False,
            'issues': []
        }
        
        if not self.backup_dir.exists():
            rollback_results['issues'].append("No backup directory found")
            return rollback_results
        
        try:
            # Find the most recent backup manifest
            manifest_files = list(self.backup_dir.glob("migration_manifest_*.json"))
            if not manifest_files:
                rollback_results['issues'].append("No backup manifest found")
                return rollback_results
            
            latest_manifest = max(manifest_files, key=lambda p: p.stat().st_mtime)
            
            with open(latest_manifest, 'r') as f:
                manifest = json.load(f)
            
            # Restore legacy files
            for backup_file_path in manifest['files_backed_up']:
                backup_file = Path(backup_file_path)
                if not backup_file.exists():
                    continue
                
                # Determine original location
                if 'plaintext_' in backup_file.name:
                    original_file = self.legacy_files['plaintext']
                elif 'deprecated_backup_' in backup_file.name:
                    original_file = self.legacy_files['deprecated_backup']
                else:
                    continue  # Skip modern storage backups for rollback
                
                shutil.copy2(backup_file, original_file)
                rollback_results['files_restored'].append(str(original_file))
                self.logger.info(f"Restored {original_file} from {backup_file}")
            
            # Remove modern storage files
            for file_path in self.modern_files.values():
                if file_path.exists():
                    file_path.unlink()
                    self.logger.info(f"Removed modern storage file: {file_path}")
            
            rollback_results['rollback_successful'] = True
            self.logger.info("Migration rollback completed successfully")
            
        except Exception as e:
            rollback_results['issues'].append(f"Rollback failed: {str(e)}")
            self.logger.error(f"Migration rollback failed: {e}")
        
        return rollback_results


# Convenience functions for migration
def migrate_authentication_storage(
    storage_dir: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to migrate authentication storage.
    
    Args:
        storage_dir: Directory containing credentials (default: ~/.spacetimedb)
        dry_run: If True, only simulate migration without making changes
        force: If True, skip safety checks and force migration
        
    Returns:
        Dictionary with migration results
    """
    migrator = AuthenticationMigrator(storage_dir)
    return migrator.migrate_all_storage(dry_run=dry_run, force=force)


def verify_authentication_migration(storage_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Convenience function to verify authentication migration.
    
    Args:
        storage_dir: Directory containing credentials (default: ~/.spacetimedb)
        
    Returns:
        Dictionary with verification results
    """
    migrator = AuthenticationMigrator(storage_dir)
    return migrator.verify_migration()


def get_migration_status(storage_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Convenience function to check migration status.
    
    Args:
        storage_dir: Directory containing credentials (default: ~/.spacetimedb)
        
    Returns:
        Dictionary with migration status
    """
    migrator = AuthenticationMigrator(storage_dir)
    return migrator.check_migration_status()