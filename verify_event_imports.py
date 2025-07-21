#!/usr/bin/env python3
"""
Event System Import Verification Script

This script verifies that all event system imports have been migrated to use
the unified events/ directory system instead of legacy root-level imports.

Usage:
    python verify_event_imports.py [--fix]
    
    --fix: Automatically suggest fixes for legacy imports found
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set

def find_legacy_imports(directory: str) -> Dict[str, List[Tuple[int, str]]]:
    """Find all legacy event system imports in the codebase."""
    legacy_patterns = [
        r'from\s+\.event_system\s+import',
        r'from\s+\.event_manager\s+import',
        r'from\s+spacetimedb_sdk\.event_system\s+import',
        r'from\s+spacetimedb_sdk\.event_manager\s+import',
        r'import\s+.*\.event_system',
        r'import\s+.*\.event_manager'
    ]
    
    compiled_patterns = [re.compile(pattern) for pattern in legacy_patterns]
    results = {}
    
    # Search in src/ directory
    src_path = Path(directory) / "src"
    if not src_path.exists():
        src_path = Path(directory)
    
    for python_file in src_path.rglob("*.py"):
        # Skip files in events/ directory that are part of the unified system
        if "events/" in str(python_file) and any(part in str(python_file) for part in [
            "events/event_system.py", "events/enhanced_event_system.py", 
            "events/legacy_compat.py", "events/__init__.py", "events/websocket_integration.py",
            "events/spacetimedb_events.py"
        ]):
            continue
            
        # Skip legacy root-level files that maintain backward compatibility
        if any(part in str(python_file) for part in [
            "event_manager.py", "event_system.py"
        ]) and "events/" not in str(python_file):
            continue
            
        try:
            with open(python_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            file_results = []
            for line_num, line in enumerate(lines, 1):
                for pattern in compiled_patterns:
                    if pattern.search(line):
                        file_results.append((line_num, line.strip()))
                        
            if file_results:
                results[str(python_file)] = file_results
                
        except (UnicodeDecodeError, IOError) as e:
            print(f"Warning: Could not read {python_file}: {e}")
            
    return results

def find_legacy_class_usage(directory: str) -> Dict[str, List[Tuple[int, str]]]:
    """Find usage of legacy event classes that should be updated."""
    legacy_classes = [
        r'\bEventEmitter\s*\(',
        r'\bSDKEventManager\s*\(',
        r'=\s*EventEmitter\s*\(',
        r'=\s*SDKEventManager\s*\('
    ]
    
    compiled_patterns = [re.compile(pattern) for pattern in legacy_classes]
    results = {}
    
    src_path = Path(directory) / "src"
    if not src_path.exists():
        src_path = Path(directory)
    
    for python_file in src_path.rglob("*.py"):
        # Skip legacy compatibility files and root-level legacy files
        if any(part in str(python_file) for part in [
            "legacy_compat.py", "event_manager.py", "event_system.py"
        ]):
            continue
            
        try:
            with open(python_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            file_results = []
            for line_num, line in enumerate(lines, 1):
                for pattern in compiled_patterns:
                    if pattern.search(line):
                        file_results.append((line_num, line.strip()))
                        
            if file_results:
                results[str(python_file)] = file_results
                
        except (UnicodeDecodeError, IOError) as e:
            print(f"Warning: Could not read {python_file}: {e}")
            
    return results

def generate_migration_suggestions() -> Dict[str, str]:
    """Generate mapping of legacy imports to modern unified imports."""
    return {
        "from .event_system import": "from .events import",
        "from .event_manager import": "from .events import",
        "from spacetimedb_sdk.event_system import": "from spacetimedb_sdk.events import",
        "from spacetimedb_sdk.event_manager import": "from spacetimedb_sdk.events import",
        "EventEmitter": "UnifiedEventManager",
        "SDKEventManager": "UnifiedEventManager",
        "get_event_manager": "get_event_manager",
        "EventType": "EventType",
        "Event": "Event",
        "EventContext": "EventContext",
        "EventMetadata": "EventMetadata"
    }

def print_results(legacy_imports: Dict[str, List[Tuple[int, str]]], 
                  legacy_usage: Dict[str, List[Tuple[int, str]]],
                  suggest_fixes: bool = False) -> bool:
    """Print the verification results."""
    
    has_issues = bool(legacy_imports or legacy_usage)
    
    if not has_issues:
        print("✅ SUCCESS: All event system imports have been migrated to the unified events/ system!")
        print("No legacy imports found.")
        return False
        
    print("❌ LEGACY IMPORTS FOUND")
    print("=" * 50)
    
    if legacy_imports:
        print("\n📦 Legacy Import Statements:")
        for file_path, issues in legacy_imports.items():
            print(f"\n  📁 {file_path}")
            for line_num, line in issues:
                print(f"    Line {line_num:3d}: {line}")
                
    if legacy_usage:
        print("\n🏗️  Legacy Class Usage:")
        for file_path, issues in legacy_usage.items():
            print(f"\n  📁 {file_path}")
            for line_num, line in issues:
                print(f"    Line {line_num:3d}: {line}")
    
    if suggest_fixes:
        print("\n🔧 MIGRATION SUGGESTIONS")
        print("=" * 50)
        suggestions = generate_migration_suggestions()
        print("\nRecommended replacements:")
        for old, new in suggestions.items():
            print(f"  {old} → {new}")
            
        print("\n📋 Migration Steps:")
        print("1. Replace legacy import statements with unified imports")
        print("2. Update EventEmitter usage to UnifiedEventManager")
        print("3. Update SDKEventManager usage to UnifiedEventManager")
        print("4. Test that all functionality continues to work")
        print("5. Run this script again to verify migration")
    
    return True

def main():
    """Main verification function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify event system import migration')
    parser.add_argument('--fix', action='store_true', help='Show migration suggestions')
    parser.add_argument('--directory', default='.', help='Directory to scan (default: current)')
    
    args = parser.parse_args()
    
    print("🔍 Event System Import Migration Verification")
    print("=" * 50)
    print(f"Scanning directory: {os.path.abspath(args.directory)}")
    
    # Find legacy imports and usage
    legacy_imports = find_legacy_imports(args.directory)
    legacy_usage = find_legacy_class_usage(args.directory)
    
    # Print results
    has_issues = print_results(legacy_imports, legacy_usage, args.fix)
    
    # Summary
    total_files_with_issues = len(set(legacy_imports.keys()) | set(legacy_usage.keys()))
    total_issues = sum(len(issues) for issues in legacy_imports.values()) + \
                   sum(len(issues) for issues in legacy_usage.values())
    
    print(f"\n📊 SUMMARY")
    print("=" * 20)
    print(f"Files with issues: {total_files_with_issues}")
    print(f"Total issues found: {total_issues}")
    
    if has_issues:
        print("\n⚠️  Migration incomplete. Please update the legacy imports.")
        sys.exit(1)
    else:
        print("\n✅ Migration complete! All imports are using the unified events/ system.")
        sys.exit(0)

if __name__ == "__main__":
    main()