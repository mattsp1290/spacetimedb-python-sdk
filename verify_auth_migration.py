#!/usr/bin/env python3
"""
Authentication Migration Verification Script

This script verifies that the authentication storage consolidation was successful:
1. Confirms all deprecated auth files are removed
2. Checks that no imports reference deprecated modules
3. Tests that the modern auth system is working
4. Verifies backward compatibility
"""

import ast
import importlib
import logging
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Set


class AuthMigrationVerifier:
    """Comprehensive verifier for authentication migration."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.spacetimedb_sdk_dir = self.src_dir / "spacetimedb_sdk"
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Deprecated modules that should be removed
        self.deprecated_modules = {
            'auth_storage.py',
            'auth_storage_deprecated.py', 
            'auth_storage_original.py'
        }
        
        # Expected modern auth files
        self.modern_auth_files = {
            'auth/__init__.py',
            'auth/storage.py',
            'auth/migration.py',
            'auth/migration_tools.py',
            'auth/cli.py',
            'auth/providers.py',
            'auth/validators.py'
        }
    
    def verify_deprecated_files_removed(self) -> Dict[str, Any]:
        """Verify that all deprecated authentication files are removed."""
        result = {
            'deprecated_files_removed': True,
            'remaining_deprecated_files': [],
            'issues': []
        }
        
        for deprecated_file in self.deprecated_modules:
            file_path = self.spacetimedb_sdk_dir / deprecated_file
            if file_path.exists():
                result['deprecated_files_removed'] = False
                result['remaining_deprecated_files'].append(str(file_path))
                result['issues'].append(f"Deprecated file still exists: {file_path}")
        
        return result
    
    def verify_modern_auth_files_exist(self) -> Dict[str, Any]:
        """Verify that all modern authentication files exist."""
        result = {
            'modern_files_exist': True,
            'missing_modern_files': [],
            'existing_modern_files': [],
            'issues': []
        }
        
        for modern_file in self.modern_auth_files:
            file_path = self.spacetimedb_sdk_dir / modern_file
            if file_path.exists():
                result['existing_modern_files'].append(str(file_path))
            else:
                result['modern_files_exist'] = False
                result['missing_modern_files'].append(str(file_path))
                result['issues'].append(f"Modern auth file missing: {file_path}")
        
        return result
    
    def find_deprecated_imports(self) -> Dict[str, Any]:
        """Find any remaining imports from deprecated auth modules."""
        result = {
            'deprecated_imports_found': False,
            'files_with_deprecated_imports': [],
            'deprecated_import_details': [],
            'issues': []
        }
        
        deprecated_patterns = [
            '.auth_storage',  # More precise pattern to avoid false positives
            'auth_storage_deprecated', 
            'auth_storage_original'
        ]
        
        # Search all Python files in src directory
        for py_file in self.src_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for deprecated import patterns
                for pattern in deprecated_patterns:
                    if pattern in content:
                        # Use AST to properly parse imports
                        try:
                            tree = ast.parse(content)
                            for node in ast.walk(tree):
                                if isinstance(node, (ast.Import, ast.ImportFrom)):
                                    if isinstance(node, ast.ImportFrom) and node.module:
                                        if pattern in node.module:
                                            result['deprecated_imports_found'] = True
                                            result['files_with_deprecated_imports'].append(str(py_file))
                                            result['deprecated_import_details'].append({
                                                'file': str(py_file),
                                                'line': node.lineno,
                                                'module': node.module,
                                                'type': 'ImportFrom'
                                            })
                                    elif isinstance(node, ast.Import):
                                        for alias in node.names:
                                            if pattern in alias.name:
                                                result['deprecated_imports_found'] = True
                                                result['files_with_deprecated_imports'].append(str(py_file))
                                                result['deprecated_import_details'].append({
                                                    'file': str(py_file),
                                                    'line': node.lineno,
                                                    'module': alias.name,
                                                    'type': 'Import'
                                                })
                        except SyntaxError:
                            # Skip files with syntax errors
                            pass
                        
                        # Also do simple text search as backup
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if (('import' in line or 'from' in line) and 
                                pattern in line and 
                                not line.strip().startswith('#')):
                                result['deprecated_imports_found'] = True
                                if str(py_file) not in result['files_with_deprecated_imports']:
                                    result['files_with_deprecated_imports'].append(str(py_file))
                                result['deprecated_import_details'].append({
                                    'file': str(py_file),
                                    'line': i,
                                    'content': line.strip(),
                                    'type': 'TextSearch'
                                })
                        
            except Exception as e:
                result['issues'].append(f"Error reading {py_file}: {e}")
        
        # Remove duplicates
        result['files_with_deprecated_imports'] = list(set(result['files_with_deprecated_imports']))
        
        return result
    
    def test_modern_auth_import(self) -> Dict[str, Any]:
        """Test that the modern auth system can be imported and used."""
        result = {
            'import_successful': False,
            'basic_functionality_works': False,
            'issues': []
        }
        
        try:
            # Add src to Python path temporarily
            sys.path.insert(0, str(self.src_dir))
            
            # Test importing main components
            from spacetimedb_sdk.auth.storage import SecureAuthStorage, AuthCredentials
            from spacetimedb_sdk.auth.migration_tools import AuthenticationMigrator
            
            result['import_successful'] = True
            self.logger.info("✓ Modern auth imports successful")
            
            # Test basic functionality with temporary storage
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_storage_dir = Path(temp_dir) / "test_storage"
                
                # Test SecureAuthStorage creation
                storage = SecureAuthStorage(
                    storage_dir=temp_storage_dir,
                    prefer_keyring=False,  # Use file storage for testing
                    master_password="test_password_123"
                )
                
                # Test credential creation
                creds = AuthCredentials(
                    identity="test_identity_12345678",
                    token="test_token_1234567890abcdef",
                    host="localhost",
                    database="test_db"
                )
                
                # Test basic operations
                storage.store_credentials(
                    creds.identity, creds.token, creds.host, creds.database
                )
                
                retrieved = storage.get_credentials(creds.host, creds.database)
                
                if retrieved and retrieved.identity == creds.identity:
                    result['basic_functionality_works'] = True
                    self.logger.info("✓ Basic auth functionality works")
                else:
                    result['issues'].append("Retrieved credentials don't match stored credentials")
                
        except Exception as e:
            result['issues'].append(f"Modern auth test failed: {e}")
            self.logger.error(f"✗ Modern auth test failed: {e}")
        finally:
            # Remove src from path
            if str(self.src_dir) in sys.path:
                sys.path.remove(str(self.src_dir))
        
        return result
    
    def test_backward_compatibility(self) -> Dict[str, Any]:
        """Test that backward compatibility functions work."""
        result = {
            'main_module_import_works': False,
            'convenience_functions_work': False,
            'issues': []
        }
        
        try:
            # Add src to Python path temporarily
            sys.path.insert(0, str(self.src_dir))
            
            # Test importing from main module
            from spacetimedb_sdk import (
                store_credentials, get_credentials, 
                remove_credentials, clear_all_credentials,
                AuthCredentials, SpacetimeDBAuthStorage
            )
            
            result['main_module_import_works'] = True
            self.logger.info("✓ Main module backward compatibility imports work")
            
            # Test convenience functions with temporary storage
            with tempfile.TemporaryDirectory() as temp_dir:
                # Override global storage for testing
                import spacetimedb_sdk
                original_global = getattr(spacetimedb_sdk, '_global_auth_storage', None)
                
                from spacetimedb_sdk.auth.storage import SecureAuthStorage
                spacetimedb_sdk._global_auth_storage = SecureAuthStorage(
                    storage_dir=Path(temp_dir) / "test_compat",
                    prefer_keyring=False,
                    master_password="test_compat_123"
                )
                
                try:
                    # Test convenience functions
                    store_credentials("test_id_87654321", "test_token_abcdef", "test.host", "test_db")
                    retrieved = get_credentials("test.host", "test_db")
                    
                    if retrieved and retrieved.identity == "test_id_87654321":
                        result['convenience_functions_work'] = True
                        self.logger.info("✓ Backward compatibility functions work")
                    else:
                        result['issues'].append("Convenience functions don't work correctly")
                
                finally:
                    # Restore original global storage
                    spacetimedb_sdk._global_auth_storage = original_global
                
        except Exception as e:
            result['issues'].append(f"Backward compatibility test failed: {e}")
            self.logger.error(f"✗ Backward compatibility test failed: {e}")
        finally:
            # Remove src from path
            if str(self.src_dir) in sys.path:
                sys.path.remove(str(self.src_dir))
        
        return result
    
    def run_full_verification(self) -> Dict[str, Any]:
        """Run complete verification of the auth migration."""
        self.logger.info("Starting authentication migration verification...")
        
        verification_results = {
            'verification_timestamp': str(Path(__file__).stat().st_mtime),
            'deprecated_files': self.verify_deprecated_files_removed(),
            'modern_files': self.verify_modern_auth_files_exist(), 
            'deprecated_imports': self.find_deprecated_imports(),
            'modern_auth_test': self.test_modern_auth_import(),
            'backward_compatibility': self.test_backward_compatibility(),
            'overall_success': False,
            'summary': []
        }
        
        # Calculate overall success
        success_criteria = [
            verification_results['deprecated_files']['deprecated_files_removed'],
            verification_results['modern_files']['modern_files_exist'],
            not verification_results['deprecated_imports']['deprecated_imports_found'],
            verification_results['modern_auth_test']['import_successful'],
            verification_results['modern_auth_test']['basic_functionality_works'],
            verification_results['backward_compatibility']['main_module_import_works'],
            verification_results['backward_compatibility']['convenience_functions_work']
        ]
        
        verification_results['overall_success'] = all(success_criteria)
        
        # Generate summary
        if verification_results['overall_success']:
            verification_results['summary'].append("✓ Authentication migration verification PASSED")
            verification_results['summary'].append("✓ All deprecated files removed")
            verification_results['summary'].append("✓ Modern auth system working")
            verification_results['summary'].append("✓ No deprecated imports found")
            verification_results['summary'].append("✓ Backward compatibility maintained")
        else:
            verification_results['summary'].append("✗ Authentication migration verification FAILED")
            
            if not verification_results['deprecated_files']['deprecated_files_removed']:
                verification_results['summary'].append("✗ Some deprecated files still exist")
            
            if not verification_results['modern_files']['modern_files_exist']:
                verification_results['summary'].append("✗ Some modern auth files missing")
            
            if verification_results['deprecated_imports']['deprecated_imports_found']:
                verification_results['summary'].append("✗ Deprecated imports still found")
            
            if not verification_results['modern_auth_test']['import_successful']:
                verification_results['summary'].append("✗ Modern auth import failed")
            
            if not verification_results['modern_auth_test']['basic_functionality_works']:
                verification_results['summary'].append("✗ Modern auth functionality failed")
            
            if not verification_results['backward_compatibility']['main_module_import_works']:
                verification_results['summary'].append("✗ Main module imports failed")
            
            if not verification_results['backward_compatibility']['convenience_functions_work']:
                verification_results['summary'].append("✗ Convenience functions failed")
        
        return verification_results
    
    def print_verification_report(self, results: Dict[str, Any]) -> None:
        """Print a detailed verification report."""
        print("\n" + "="*80)
        print("SPACETIMEDB AUTHENTICATION MIGRATION VERIFICATION REPORT")
        print("="*80)
        
        # Print summary
        print("\nSUMMARY:")
        for summary_line in results['summary']:
            print(f"  {summary_line}")
        
        # Detailed results
        if not results['deprecated_files']['deprecated_files_removed']:
            print(f"\nREMAINING DEPRECATED FILES:")
            for file_path in results['deprecated_files']['remaining_deprecated_files']:
                print(f"  - {file_path}")
        
        if not results['modern_files']['modern_files_exist']:
            print(f"\nMISSING MODERN FILES:")
            for file_path in results['modern_files']['missing_modern_files']:
                print(f"  - {file_path}")
        
        if results['deprecated_imports']['deprecated_imports_found']:
            print(f"\nDEPRECATED IMPORTS FOUND:")
            for import_detail in results['deprecated_imports']['deprecated_import_details']:
                print(f"  - {import_detail['file']}:{import_detail['line']} - {import_detail.get('module', import_detail.get('content', ''))}")
        
        # Issues
        all_issues = []
        for section in results.values():
            if isinstance(section, dict) and 'issues' in section:
                all_issues.extend(section['issues'])
        
        if all_issues:
            print(f"\nISSUES FOUND:")
            for issue in all_issues:
                print(f"  - {issue}")
        
        print("\n" + "="*80)
        
        if results['overall_success']:
            print("VERIFICATION PASSED - Authentication migration is successful!")
        else:
            print("VERIFICATION FAILED - Please address the issues above.")
        
        print("="*80)


def main():
    """Main verification function."""
    project_root = Path(__file__).parent
    verifier = AuthMigrationVerifier(project_root)
    
    try:
        results = verifier.run_full_verification()
        verifier.print_verification_report(results)
        
        # Exit with appropriate code
        sys.exit(0 if results['overall_success'] else 1)
        
    except Exception as e:
        print(f"Verification script failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()