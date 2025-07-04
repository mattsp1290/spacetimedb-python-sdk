#!/usr/bin/env python3
"""
SpacetimeDB SDK Migration Checker

This tool analyzes your codebase and identifies areas that need updating
for the new SDK architecture. It can also apply automatic fixes where possible.

Usage:
    python migration_checker.py --check src/           # Check for migration issues
    python migration_checker.py --migrate src/         # Apply automatic migrations
    python migration_checker.py --report migration.json # Generate detailed report
"""

import os
import re
import ast
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class MigrationIssue:
    """Represents a migration issue found in the code."""
    file_path: str
    line_number: int
    issue_type: str
    severity: str  # 'error', 'warning', 'info'
    description: str
    old_code: str
    new_code: Optional[str] = None
    auto_fixable: bool = False


class MigrationChecker:
    """Analyzes code for migration issues."""
    
    # Event name mappings from old to new
    EVENT_MAPPINGS = {
        # event_system.py mappings
        'connection_established': 'CONNECTION_ESTABLISHED',
        'connection_opened': 'CONNECTION_OPENED',
        'connection_closed': 'CONNECTION_CLOSED',
        'connection_lost': 'CONNECTION_LOST',
        'connection_error': 'CONNECTION_ERROR',
        'identity_received': 'IDENTITY_RECEIVED',
        'identity_changed': 'IDENTITY_CHANGED',
        'reducer_called': 'REDUCER_CALLED',
        'reducer_error': 'REDUCER_ERROR',
        'subscription_applied': 'SUBSCRIPTION_APPLIED',
        'subscription_error': 'SUBSCRIPTION_ERROR',
        'transaction_update': 'TRANSACTION_UPDATE',
        'table_row_insert': 'TABLE_ROW_INSERT',
        'table_row_update': 'TABLE_ROW_UPDATE',
        'table_row_delete': 'TABLE_ROW_DELETE',
        'message_received': 'MESSAGE_RECEIVED',
        'message_sent': 'MESSAGE_SENT',
        'error': 'ERROR_OCCURRED',
        'debug': 'DEBUG_INFO',
        
        # event_manager.py mappings
        'CONNECTION_OPENED': 'CONNECTION_OPENED',
        'CONNECTION_CLOSED': 'CONNECTION_CLOSED', 
        'SUBSCRIPTION_UPDATE': 'SUBSCRIPTION_UPDATE',
        'DATABASE_UPDATE': 'DATABASE_UPDATE',
        'MESSAGE_RECEIVED': 'MESSAGE_RECEIVED',
        'ERROR': 'ERROR_OCCURRED',
        'AUTHENTICATION_SUCCESS': 'AUTHENTICATION_SUCCESS',
        'AUTHENTICATION_FAILED': 'AUTHENTICATION_FAILED',
        'REDUCER_CALL_COMPLETE': 'REDUCER_SUCCESS',
        'IDENTITY_RECEIVED': 'IDENTITY_RECEIVED',
        'INITIAL_SUBSCRIPTION': 'INITIAL_SUBSCRIPTION',
        
        # events/ package mappings
        'CONNECTION': 'CONNECTION_ESTABLISHED',
        'AUTHENTICATION': 'AUTHENTICATION_SUCCESS',
        'SUBSCRIPTION': 'SUBSCRIPTION_APPLIED',
        'TABLE_UPDATE': 'TABLE_UPDATE',
        'REDUCER_CALL': 'REDUCER_CALLED',
        'TRANSACTION': 'TRANSACTION_UPDATE',
        'QUERY': 'QUERY_EXECUTED',
        'SYSTEM': 'SYSTEM_STARTUP',
        'ERROR': 'ERROR_OCCURRED',
        'DEBUG': 'DEBUG_INFO',
        'PERFORMANCE': 'PERFORMANCE_METRIC',
    }
    
    # Deprecated imports
    DEPRECATED_IMPORTS = {
        'spacetimedb_sdk.event_system': 'spacetimedb_sdk',
        'spacetimedb_sdk.event_manager': 'spacetimedb_sdk',
        'spacetimedb_sdk.events.enhanced_event_system': 'spacetimedb_sdk',
        'spacetimedb_sdk.events.spacetimedb_events': 'spacetimedb_sdk',
    }
    
    # API pattern changes
    API_PATTERNS = [
        # Event registration patterns
        (r'\.event_system\.on\s*\(', '.on_event(', 'Event registration'),
        (r'\.event_manager\.register_handler\s*\(', '.on_event(', 'Event registration'),
        (r'\.subscribe\s*\(\s*(\w+)\s*,\s*\[([^\]]+)\]\s*\)', r'subscribe_to_events(\1, [\2])', 'Event subscription'),
        
        # Authentication patterns
        (r'\.spacetimedb_identity\s*=\s*(.+)', r'store_credentials(identity=\1, token=self.spacetimedb_token, host=host, database=database)', 'Credential storage'),
        (r'\.spacetimedb_token\s*=\s*(.+)', r'# Token stored with store_credentials()', 'Token storage'),
        (r'\.auth_handshake_completed\s*=\s*True', r'# Handled automatically by AuthenticationHandler', 'Auth handshake'),
        
        # Direct credential access
        (r'with\s+open\s*\([\'"].*credentials\.json[\'"]\)', 'get_credentials(host, database)', 'Credential access'),
        (r'json\.load\s*\(.*credentials.*\)', 'get_credentials(host, database)', 'Credential loading'),
    ]
    
    def __init__(self):
        self.issues: List[MigrationIssue] = []
        self.stats = defaultdict(int)
    
    def check_file(self, file_path: Path) -> List[MigrationIssue]:
        """Check a single Python file for migration issues."""
        issues = []
        
        try:
            content = file_path.read_text()
            lines = content.splitlines()
            
            # Check imports
            issues.extend(self._check_imports(file_path, content, lines))
            
            # Check event usage
            issues.extend(self._check_event_usage(file_path, content, lines))
            
            # Check API patterns
            issues.extend(self._check_api_patterns(file_path, content, lines))
            
            # Check authentication usage
            issues.extend(self._check_authentication(file_path, content, lines))
            
            # Check handler signatures
            issues.extend(self._check_handler_signatures(file_path, content, lines))
            
        except Exception as e:
            print(f"Error checking {file_path}: {e}")
        
        return issues
    
    def _check_imports(self, file_path: Path, content: str, lines: List[str]) -> List[MigrationIssue]:
        """Check for deprecated imports."""
        issues = []
        
        for i, line in enumerate(lines):
            for old_import, new_import in self.DEPRECATED_IMPORTS.items():
                if f'from {old_import}' in line or f'import {old_import}' in line:
                    issues.append(MigrationIssue(
                        file_path=str(file_path),
                        line_number=i + 1,
                        issue_type='deprecated_import',
                        severity='warning',
                        description=f'Deprecated import: {old_import}',
                        old_code=line.strip(),
                        new_code=line.replace(old_import, new_import),
                        auto_fixable=True
                    ))
                    self.stats['deprecated_imports'] += 1
        
        # Check for multiple EventType imports
        event_type_imports = re.findall(r'from .+ import .*(EventType\s+as\s+\w+)', content)
        if len(event_type_imports) > 1:
            issues.append(MigrationIssue(
                file_path=str(file_path),
                line_number=0,
                issue_type='multiple_event_types',
                severity='error',
                description='Multiple EventType imports detected. Use unified EventType from spacetimedb_sdk',
                old_code='Multiple EventType imports',
                new_code='from spacetimedb_sdk import EventType',
                auto_fixable=False
            ))
            self.stats['multiple_event_types'] += 1
        
        return issues
    
    def _check_event_usage(self, file_path: Path, content: str, lines: List[str]) -> List[MigrationIssue]:
        """Check for old event names and patterns."""
        issues = []
        
        for i, line in enumerate(lines):
            # Check for old event names in strings
            for old_name, new_name in self.EVENT_MAPPINGS.items():
                # Look for event names in quotes
                pattern = rf'[\'"]({old_name})[\'"]'
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    if old_name != new_name:  # Only flag if actually different
                        issues.append(MigrationIssue(
                            file_path=str(file_path),
                            line_number=i + 1,
                            issue_type='old_event_name',
                            severity='warning',
                            description=f'Old event name: {old_name} should be {new_name}',
                            old_code=line.strip(),
                            new_code=line.replace(f'"{old_name}"', f'EventType.{new_name}').replace(f"'{old_name}'", f'EventType.{new_name}'),
                            auto_fixable=True
                        ))
                        self.stats['old_event_names'] += 1
        
        return issues
    
    def _check_api_patterns(self, file_path: Path, content: str, lines: List[str]) -> List[MigrationIssue]:
        """Check for old API patterns."""
        issues = []
        
        for pattern, replacement, description in self.API_PATTERNS:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line = lines[line_num - 1] if line_num <= len(lines) else ''
                
                issues.append(MigrationIssue(
                    file_path=str(file_path),
                    line_number=line_num,
                    issue_type='api_pattern',
                    severity='warning',
                    description=f'Old API pattern: {description}',
                    old_code=line.strip(),
                    new_code=re.sub(pattern, replacement, line).strip(),
                    auto_fixable=True
                ))
                self.stats['api_patterns'] += 1
        
        return issues
    
    def _check_authentication(self, file_path: Path, content: str, lines: List[str]) -> List[MigrationIssue]:
        """Check for insecure authentication patterns."""
        issues = []
        
        # Check for plaintext credential storage
        if 'credentials.json' in content and 'json.dump' in content:
            issues.append(MigrationIssue(
                file_path=str(file_path),
                line_number=0,
                issue_type='insecure_storage',
                severity='error',
                description='Plaintext credential storage detected',
                old_code='json.dump(credentials, file)',
                new_code='store_credentials(identity, token, host, database)',
                auto_fixable=False
            ))
            self.stats['insecure_storage'] += 1
        
        # Check for direct token access
        token_patterns = [
            r'self\.spacetimedb_token',
            r'client\.spacetimedb_token',
            r'\.spacetimedb_identity(?!\s*=)',
        ]
        
        for pattern in token_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line = lines[line_num - 1] if line_num <= len(lines) else ''
                
                issues.append(MigrationIssue(
                    file_path=str(file_path),
                    line_number=line_num,
                    issue_type='direct_credential_access',
                    severity='warning',
                    description='Direct credential access - use get_credentials() instead',
                    old_code=line.strip(),
                    new_code=None,
                    auto_fixable=False
                ))
                self.stats['direct_credential_access'] += 1
        
        return issues
    
    def _check_handler_signatures(self, file_path: Path, content: str, lines: List[str]) -> List[MigrationIssue]:
        """Check for old handler signatures."""
        issues = []
        
        # Parse AST to find function definitions
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if this looks like an event handler
                    handler_patterns = [
                        'on_', 'handle_', '_on_', '_handle_',
                        'on_connect', 'on_message', 'on_error',
                        'on_reducer', 'on_table_update'
                    ]
                    
                    if any(node.name.startswith(p) or node.name == p for p in handler_patterns):
                        # Check parameter count and names
                        params = [arg.arg for arg in node.args.args]
                        
                        # Old handlers have various signatures, new ones have (context)
                        if len(params) > 1 or (len(params) == 1 and params[0] != 'context'):
                            line_num = node.lineno
                            
                            issues.append(MigrationIssue(
                                file_path=str(file_path),
                                line_number=line_num,
                                issue_type='old_handler_signature',
                                severity='warning',
                                description=f'Handler {node.name} uses old signature. New handlers should accept (context) parameter',
                                old_code=f'def {node.name}({", ".join(params)}):',
                                new_code=f'def {node.name}(context):',
                                auto_fixable=False  # Requires manual update of function body
                            ))
                            self.stats['old_handler_signatures'] += 1
        
        except SyntaxError:
            # Skip files with syntax errors
            pass
        
        return issues
    
    def check_directory(self, directory: Path) -> List[MigrationIssue]:
        """Check all Python files in a directory."""
        all_issues = []
        
        for py_file in directory.rglob('*.py'):
            # Skip migration scripts and test files
            if 'migration' in str(py_file) or '__pycache__' in str(py_file):
                continue
                
            issues = self.check_file(py_file)
            all_issues.extend(issues)
            self.issues.extend(issues)
        
        return all_issues
    
    def generate_report(self) -> Dict:
        """Generate a detailed migration report."""
        report = {
            'summary': {
                'total_issues': len(self.issues),
                'auto_fixable': sum(1 for i in self.issues if i.auto_fixable),
                'by_severity': {
                    'error': sum(1 for i in self.issues if i.severity == 'error'),
                    'warning': sum(1 for i in self.issues if i.severity == 'warning'),
                    'info': sum(1 for i in self.issues if i.severity == 'info'),
                },
                'by_type': dict(self.stats)
            },
            'issues': [asdict(issue) for issue in self.issues]
        }
        
        return report
    
    def apply_fixes(self, dry_run: bool = False) -> int:
        """Apply automatic fixes to the codebase."""
        fixed_count = 0
        files_to_fix = defaultdict(list)
        
        # Group issues by file
        for issue in self.issues:
            if issue.auto_fixable and issue.new_code:
                files_to_fix[issue.file_path].append(issue)
        
        # Apply fixes file by file
        for file_path, issues in files_to_fix.items():
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                # Sort issues by line number in reverse order to avoid offset issues
                issues.sort(key=lambda x: x.line_number, reverse=True)
                
                for issue in issues:
                    if issue.line_number > 0 and issue.line_number <= len(lines):
                        line_idx = issue.line_number - 1
                        old_line = lines[line_idx]
                        
                        # Apply the fix
                        if issue.old_code in old_line:
                            new_line = old_line.replace(issue.old_code, issue.new_code)
                            lines[line_idx] = new_line
                            fixed_count += 1
                            
                            if not dry_run:
                                print(f"Fixed: {file_path}:{issue.line_number}")
                                print(f"  - {issue.old_code}")
                                print(f"  + {issue.new_code}")
                
                # Write back the file
                if not dry_run and fixed_count > 0:
                    with open(file_path, 'w') as f:
                        f.writelines(lines)
            
            except Exception as e:
                print(f"Error fixing {file_path}: {e}")
        
        return fixed_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='SpacetimeDB SDK Migration Checker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'path',
        type=Path,
        help='Path to check (file or directory)'
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check for migration issues without applying fixes'
    )
    
    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Apply automatic migrations where possible'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without applying changes'
    )
    
    parser.add_argument(
        '--report',
        type=Path,
        help='Generate a detailed JSON report'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Show detailed output'
    )
    
    args = parser.parse_args()
    
    # Create checker
    checker = MigrationChecker()
    
    # Check the codebase
    print(f"Checking {args.path}...")
    
    if args.path.is_file():
        issues = checker.check_file(args.path)
    else:
        issues = checker.check_directory(args.path)
    
    # Display summary
    print(f"\nFound {len(issues)} migration issues:")
    print(f"  - Errors: {checker.stats['error']}")
    print(f"  - Warnings: {sum(1 for i in issues if i.severity == 'warning')}")
    print(f"  - Auto-fixable: {sum(1 for i in issues if i.auto_fixable)}")
    
    # Show issues if verbose
    if args.verbose or args.check:
        print("\nDetailed issues:")
        for issue in sorted(issues, key=lambda x: (x.file_path, x.line_number)):
            print(f"\n{issue.file_path}:{issue.line_number} [{issue.severity}] {issue.issue_type}")
            print(f"  {issue.description}")
            if issue.old_code:
                print(f"  - {issue.old_code}")
            if issue.new_code:
                print(f"  + {issue.new_code}")
    
    # Apply fixes if requested
    if args.migrate:
        if args.dry_run:
            print("\n[DRY RUN] Would fix the following issues:")
        else:
            print("\nApplying automatic fixes...")
        
        fixed = checker.apply_fixes(dry_run=args.dry_run)
        print(f"\nFixed {fixed} issues")
    
    # Generate report if requested
    if args.report:
        report = checker.generate_report()
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to {args.report}")
    
    # Return exit code based on errors
    error_count = sum(1 for i in issues if i.severity == 'error')
    return 1 if error_count > 0 else 0


if __name__ == '__main__':
    exit(main())