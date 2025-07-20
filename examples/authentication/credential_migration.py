#!/usr/bin/env python3
"""
Credential Migration Example - SpacetimeDB Python SDK

This example demonstrates credential migration patterns for upgrading from legacy
authentication systems to modern secure authentication with the SpacetimeDB Python SDK.

Key Features Demonstrated:
- Migration from legacy plaintext to encrypted storage
- Backward compatibility with existing credentials
- Safe migration strategies with rollback capabilities
- Data integrity verification during migration
- Production-ready migration patterns

Migration Scenarios Covered:
- Legacy to modern authentication handler migration
- Plaintext to encrypted credential storage
- Token format migrations (v1 to v2)
- Database schema updates for authentication
- Bulk user migration strategies
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from spacetimedb_sdk import SpacetimeDBAsyncClient
from spacetimedb_sdk.auth import AuthenticationHandler
from spacetimedb_sdk.auth.storage import SecureAuthStorage
from spacetimedb_sdk.auth.migration import CredentialMigrator
from spacetimedb_sdk.exceptions import AuthenticationError, MigrationError


# Configure detailed logging for migration tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LegacyCredentialStorage:
    """
    Simulates legacy credential storage system for migration demonstration.
    
    In production, this would represent your existing authentication system
    that needs to be migrated to the new secure storage format.
    """
    
    def __init__(self, storage_path: str = "/tmp/legacy_credentials.json"):
        self.storage_path = storage_path
        self.credentials: Dict[str, Any] = {}
        self._load_legacy_credentials()
    
    def _load_legacy_credentials(self) -> None:
        """Load existing legacy credentials from file."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    self.credentials = json.load(f)
                    logger.info(f"Loaded {len(self.credentials)} legacy credentials")
            else:
                # Create sample legacy credentials for demonstration
                self.credentials = {
                    "user1": {
                        "database": "legacy_db1",
                        "token": "legacy_token_123_plaintext",
                        "identity": "user1_identity",
                        "created_at": "2023-01-01T00:00:00Z",
                        "format_version": "1.0"
                    },
                    "user2": {
                        "database": "legacy_db2", 
                        "token": "legacy_token_456_plaintext",
                        "identity": "user2_identity",
                        "created_at": "2023-06-01T00:00:00Z",
                        "format_version": "1.0"
                    }
                }
                self._save_legacy_credentials()
                logger.info("Created sample legacy credentials for demonstration")
        except Exception as e:
            logger.error(f"Error loading legacy credentials: {e}")
            self.credentials = {}
    
    def _save_legacy_credentials(self) -> None:
        """Save legacy credentials to file."""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.credentials, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving legacy credentials: {e}")
    
    def get_all_users(self) -> List[str]:
        """Get list of all users with legacy credentials."""
        return list(self.credentials.keys())
    
    def get_user_credentials(self, username: str) -> Optional[Dict[str, Any]]:
        """Get credentials for a specific user."""
        return self.credentials.get(username)
    
    def mark_migrated(self, username: str) -> None:
        """Mark a user as migrated in legacy system."""
        if username in self.credentials:
            self.credentials[username]["migrated"] = True
            self.credentials[username]["migrated_at"] = datetime.utcnow().isoformat()
            self._save_legacy_credentials()


class CredentialMigrationManager:
    """
    Comprehensive credential migration manager demonstrating production patterns.
    
    This class handles the complete migration process from legacy authentication
    systems to the modern SpacetimeDB Python SDK authentication framework.
    """
    
    def __init__(self, server_url: str = "ws://localhost:3000"):
        self.server_url = server_url
        self.legacy_storage = LegacyCredentialStorage()
        self.modern_storage = SecureAuthStorage()
        self.migration_log: List[Dict[str, Any]] = []
        
        # Migration configuration
        self.migration_config = {
            "batch_size": 5,  # Migrate users in batches
            "verification_enabled": True,  # Verify each migration
            "rollback_enabled": True,  # Enable rollback on failures
            "backup_legacy": True,  # Backup legacy data before migration
            "migration_timeout": 300,  # 5 minutes per batch
        }
    
    async def analyze_migration_requirements(self) -> Dict[str, Any]:
        """
        Analyze legacy credentials to determine migration requirements.
        
        Returns:
            Dict containing migration analysis results
        """
        try:
            users = self.legacy_storage.get_all_users()
            analysis = {
                "total_users": len(users),
                "migrated_users": 0,
                "pending_users": 0,
                "credential_formats": {},
                "databases": set(),
                "migration_complexity": "low",
                "estimated_duration_minutes": 0
            }
            
            for username in users:
                cred = self.legacy_storage.get_user_credentials(username)
                if not cred:
                    continue
                
                # Check migration status
                if cred.get("migrated", False):
                    analysis["migrated_users"] += 1
                else:
                    analysis["pending_users"] += 1
                
                # Track credential formats
                format_version = cred.get("format_version", "unknown")
                analysis["credential_formats"][format_version] = \
                    analysis["credential_formats"].get(format_version, 0) + 1
                
                # Track databases
                analysis["databases"].add(cred.get("database", "unknown"))
            
            # Determine migration complexity
            if len(analysis["credential_formats"]) > 1:
                analysis["migration_complexity"] = "medium"
            
            if analysis["total_users"] > 100:
                analysis["migration_complexity"] = "high"
            
            # Estimate migration duration
            analysis["estimated_duration_minutes"] = \
                max(1, analysis["pending_users"] // self.migration_config["batch_size"]) * 2
            
            logger.info(f"Migration analysis completed: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Migration analysis failed: {e}")
            return {}
    
    async def create_migration_backup(self) -> str:
        """
        Create backup of legacy credentials before migration.
        
        Returns:
            str: Backup file path
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = f"/tmp/legacy_credentials_backup_{timestamp}.json"
            
            # Copy legacy credentials to backup
            users = self.legacy_storage.get_all_users()
            backup_data = {
                "backup_timestamp": timestamp,
                "total_users": len(users),
                "credentials": {}
            }
            
            for username in users:
                cred = self.legacy_storage.get_user_credentials(username)
                if cred:
                    backup_data["credentials"][username] = cred.copy()
            
            # Save backup
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            logger.info(f"Migration backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create migration backup: {e}")
            raise MigrationError(f"Backup creation failed: {e}")
    
    async def migrate_user_credentials(self, username: str) -> bool:
        """
        Migrate credentials for a single user.
        
        Args:
            username: Username to migrate
            
        Returns:
            bool: True if migration was successful
        """
        try:
            # Get legacy credentials
            legacy_cred = self.legacy_storage.get_user_credentials(username)
            if not legacy_cred:
                logger.warning(f"No legacy credentials found for user: {username}")
                return False
            
            # Skip if already migrated
            if legacy_cred.get("migrated", False):
                logger.info(f"User {username} already migrated")
                return True
            
            logger.info(f"Migrating credentials for user: {username}")
            
            # Extract legacy credential information
            database_name = legacy_cred.get("database")
            legacy_token = legacy_cred.get("token")
            identity = legacy_cred.get("identity")
            
            if not all([database_name, legacy_token, identity]):
                logger.error(f"Incomplete legacy credentials for user: {username}")
                return False
            
            # Transform legacy token to modern format
            modern_token = await self._transform_legacy_token(legacy_token, identity)
            if not modern_token:
                logger.error(f"Failed to transform token for user: {username}")
                return False
            
            # Store in modern secure storage
            await self.modern_storage.store_token(database_name, modern_token)
            await self.modern_storage.store_identity(database_name, identity)
            
            # Verify migration by retrieving stored credentials
            if self.migration_config["verification_enabled"]:
                verification_success = await self._verify_migrated_credentials(
                    database_name, identity, modern_token
                )
                
                if not verification_success:
                    logger.error(f"Migration verification failed for user: {username}")
                    return False
            
            # Mark as migrated in legacy system
            self.legacy_storage.mark_migrated(username)
            
            # Log migration success
            self._log_migration_event(username, "success", {
                "database": database_name,
                "identity": identity,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Successfully migrated user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed for user {username}: {e}")
            self._log_migration_event(username, "error", {"error": str(e)})
            return False
    
    async def _transform_legacy_token(self, legacy_token: str, identity: str) -> Optional[str]:
        """
        Transform legacy token format to modern secure format.
        
        Args:
            legacy_token: Legacy token to transform
            identity: User identity
            
        Returns:
            Optional[str]: Transformed token or None if transformation failed
        """
        try:
            # In a real migration, this would involve:
            # 1. Validating the legacy token format
            # 2. Extracting any embedded information
            # 3. Creating a new secure token with proper format
            # 4. Potentially re-authenticating with the server
            
            # For demonstration, we'll create a modern token format
            modern_token_data = {
                "version": "2.0",
                "identity": identity,
                "legacy_token": legacy_token,  # Keep reference for debugging
                "migrated_at": datetime.utcnow().isoformat(),
                "migration_id": f"migration_{int(datetime.utcnow().timestamp())}"
            }
            
            # In production, this would be a proper JWT or encrypted token
            modern_token = json.dumps(modern_token_data)
            
            return modern_token
            
        except Exception as e:
            logger.error(f"Token transformation failed: {e}")
            return None
    
    async def _verify_migrated_credentials(self, database_name: str, 
                                         identity: str, token: str) -> bool:
        """
        Verify that migrated credentials are properly stored and accessible.
        
        Args:
            database_name: Database name
            identity: User identity
            token: Migrated token
            
        Returns:
            bool: True if verification successful
        """
        try:
            # Verify token storage
            stored_token = await self.modern_storage.get_token(database_name)
            if stored_token != token:
                logger.error("Token verification failed - mismatch")
                return False
            
            # Verify identity storage
            stored_identity = await self.modern_storage.get_identity(database_name)
            if stored_identity != identity:
                logger.error("Identity verification failed - mismatch")
                return False
            
            # Test authentication with migrated credentials
            auth_handler = AuthenticationHandler(storage=self.modern_storage)
            
            # This would test actual authentication in a real scenario
            # For demonstration, we'll just verify the handler can access the credentials
            test_token = await auth_handler.get_current_token(database_name)
            if not test_token:
                logger.error("Authentication handler verification failed")
                return False
            
            logger.info("Credential verification successful")
            return True
            
        except Exception as e:
            logger.error(f"Credential verification error: {e}")
            return False
    
    def _log_migration_event(self, username: str, event_type: str, details: Dict[str, Any]) -> None:
        """
        Log migration events for auditing and troubleshooting.
        
        Args:
            username: Username
            event_type: Type of event (success, error, warning)
            details: Additional event details
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "username": username,
            "event_type": event_type,
            "details": details
        }
        
        self.migration_log.append(log_entry)
        
        # Also save to file for persistence
        try:
            log_file = "/tmp/credential_migration.log"
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write migration log: {e}")
    
    async def batch_migrate_users(self, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Migrate users in batches for better performance and error handling.
        
        Args:
            batch_size: Optional batch size override
            
        Returns:
            Dict containing migration results
        """
        batch_size = batch_size or self.migration_config["batch_size"]
        
        try:
            # Get all pending users
            all_users = self.legacy_storage.get_all_users()
            pending_users = []
            
            for username in all_users:
                cred = self.legacy_storage.get_user_credentials(username)
                if cred and not cred.get("migrated", False):
                    pending_users.append(username)
            
            if not pending_users:
                logger.info("No users pending migration")
                return {"status": "complete", "migrated": 0, "failed": 0}
            
            logger.info(f"Starting batch migration of {len(pending_users)} users")
            
            # Process in batches
            results = {"migrated": 0, "failed": 0, "errors": []}
            
            for i in range(0, len(pending_users), batch_size):
                batch = pending_users[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(pending_users) + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} users")
                
                # Migrate batch with timeout
                try:
                    migration_tasks = [
                        self.migrate_user_credentials(username) 
                        for username in batch
                    ]
                    
                    batch_results = await asyncio.wait_for(
                        asyncio.gather(*migration_tasks, return_exceptions=True),
                        timeout=self.migration_config["migration_timeout"]
                    )
                    
                    # Process batch results
                    for j, result in enumerate(batch_results):
                        username = batch[j]
                        if isinstance(result, Exception):
                            logger.error(f"Batch migration error for {username}: {result}")
                            results["failed"] += 1
                            results["errors"].append({"username": username, "error": str(result)})
                        elif result:
                            results["migrated"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append({"username": username, "error": "Migration returned False"})
                    
                    # Brief pause between batches
                    if i + batch_size < len(pending_users):
                        await asyncio.sleep(1)
                        
                except asyncio.TimeoutError:
                    logger.error(f"Batch {batch_num} timed out")
                    results["failed"] += len(batch)
                    for username in batch:
                        results["errors"].append({"username": username, "error": "Batch timeout"})
                
                except Exception as e:
                    logger.error(f"Batch {batch_num} failed: {e}")
                    results["failed"] += len(batch)
                    for username in batch:
                        results["errors"].append({"username": username, "error": f"Batch error: {e}"})
            
            # Final results
            results["status"] = "complete" if results["failed"] == 0 else "partial"
            results["total_processed"] = results["migrated"] + results["failed"]
            
            logger.info(f"Batch migration completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Batch migration failed: {e}")
            return {"status": "error", "error": str(e), "migrated": 0, "failed": 0}
    
    async def rollback_migration(self, username: str) -> bool:
        """
        Rollback migration for a specific user.
        
        Args:
            username: Username to rollback
            
        Returns:
            bool: True if rollback was successful
        """
        try:
            logger.info(f"Rolling back migration for user: {username}")
            
            # Get legacy credentials
            legacy_cred = self.legacy_storage.get_user_credentials(username)
            if not legacy_cred or not legacy_cred.get("migrated", False):
                logger.warning(f"User {username} not migrated or no legacy credentials")
                return False
            
            database_name = legacy_cred.get("database")
            if not database_name:
                logger.error(f"No database name for user: {username}")
                return False
            
            # Remove from modern storage
            await self.modern_storage.clear_credentials(database_name)
            
            # Unmark as migrated in legacy system
            legacy_cred["migrated"] = False
            if "migrated_at" in legacy_cred:
                del legacy_cred["migrated_at"]
            
            # Add rollback timestamp
            legacy_cred["rolled_back_at"] = datetime.utcnow().isoformat()
            
            # Save changes
            self.legacy_storage._save_legacy_credentials()
            
            # Log rollback event
            self._log_migration_event(username, "rollback", {
                "database": database_name,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Successfully rolled back migration for user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed for user {username}: {e}")
            return False
    
    async def generate_migration_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive migration report.
        
        Returns:
            Dict containing detailed migration report
        """
        try:
            # Analyze current state
            all_users = self.legacy_storage.get_all_users()
            report = {
                "report_timestamp": datetime.utcnow().isoformat(),
                "total_users": len(all_users),
                "migration_status": {
                    "migrated": 0,
                    "pending": 0,
                    "failed": 0
                },
                "migration_events": len(self.migration_log),
                "users_by_status": {},
                "databases": {},
                "migration_timeline": []
            }
            
            # Analyze user status
            for username in all_users:
                cred = self.legacy_storage.get_user_credentials(username)
                if not cred:
                    continue
                
                if cred.get("migrated", False):
                    report["migration_status"]["migrated"] += 1
                    status = "migrated"
                else:
                    report["migration_status"]["pending"] += 1
                    status = "pending"
                
                report["users_by_status"][username] = status
                
                # Track databases
                database = cred.get("database", "unknown")
                if database not in report["databases"]:
                    report["databases"][database] = {"migrated": 0, "pending": 0}
                report["databases"][database][status] += 1
            
            # Process migration log for timeline
            for log_entry in self.migration_log:
                if log_entry["event_type"] in ["success", "error"]:
                    report["migration_timeline"].append({
                        "timestamp": log_entry["timestamp"],
                        "username": log_entry["username"],
                        "event": log_entry["event_type"]
                    })
            
            logger.info("Migration report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate migration report: {e}")
            return {"error": f"Report generation failed: {e}"}


async def main():
    """
    Main example demonstrating credential migration.
    """
    logger.info("=== SpacetimeDB Credential Migration Example ===")
    
    migration_manager = CredentialMigrationManager()
    
    try:
        # Step 1: Analyze migration requirements
        logger.info("=== Analyzing Migration Requirements ===")
        analysis = await migration_manager.analyze_migration_requirements()
        
        if analysis.get("pending_users", 0) == 0:
            logger.info("No users require migration")
            return
        
        logger.info(f"Found {analysis['pending_users']} users requiring migration")
        logger.info(f"Estimated duration: {analysis['estimated_duration_minutes']} minutes")
        
        # Step 2: Create backup
        logger.info("=== Creating Migration Backup ===")
        backup_path = await migration_manager.create_migration_backup()
        logger.info(f"Backup created at: {backup_path}")
        
        # Step 3: Perform batch migration
        logger.info("=== Starting Batch Migration ===")
        migration_results = await migration_manager.batch_migrate_users()
        
        logger.info(f"Migration Results:")
        logger.info(f"  Migrated: {migration_results.get('migrated', 0)}")
        logger.info(f"  Failed: {migration_results.get('failed', 0)}")
        logger.info(f"  Status: {migration_results.get('status', 'unknown')}")
        
        # Step 4: Generate final report
        logger.info("=== Generating Migration Report ===")
        report = await migration_manager.generate_migration_report()
        
        logger.info("Migration Report Summary:")
        logger.info(f"  Total Users: {report.get('total_users', 0)}")
        logger.info(f"  Migrated: {report.get('migration_status', {}).get('migrated', 0)}")
        logger.info(f"  Pending: {report.get('migration_status', {}).get('pending', 0)}")
        
        # Demonstrate rollback for one user (if any errors occurred)
        if migration_results.get("errors"):
            first_error = migration_results["errors"][0]
            logger.info(f"=== Demonstrating Rollback for {first_error['username']} ===")
            rollback_success = await migration_manager.rollback_migration(first_error["username"])
            logger.info(f"Rollback successful: {rollback_success}")
        
    except Exception as e:
        logger.error(f"Migration example failed: {e}")
    
    logger.info("=== Migration Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())


"""
Credential Migration Best Practices:

1. **Pre-Migration Planning**:
   - Analyze existing credential formats and requirements
   - Create comprehensive backups before starting
   - Estimate migration duration and resource requirements
   - Plan for rollback scenarios

2. **Migration Safety**:
   - Process users in batches to limit impact
   - Verify each migration before marking complete
   - Implement timeout protection for hanging operations
   - Maintain detailed logs for auditing and troubleshooting

3. **Error Handling**:
   - Graceful handling of individual user failures
   - Batch-level error recovery
   - Rollback capabilities for failed migrations
   - Comprehensive error reporting and tracking

4. **Data Integrity**:
   - Verification of migrated credentials
   - Secure transformation of legacy tokens
   - Preservation of user identity information
   - Audit trails for all migration activities

5. **Production Considerations**:
   - Test migration process thoroughly in staging
   - Plan migration during low-usage periods
   - Have rollback procedures ready
   - Monitor system performance during migration
   - Communicate migration schedule to users

Migration Phases:
1. Analysis and Planning
2. Backup Creation
3. Pilot Migration (small batch)
4. Verification and Testing
5. Full Migration
6. Post-Migration Validation
7. Legacy System Cleanup

This example provides a foundation for real-world credential migrations
while demonstrating the security and reliability patterns necessary for
production systems.
"""