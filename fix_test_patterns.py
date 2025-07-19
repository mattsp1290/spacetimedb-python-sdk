#!/usr/bin/env python3
"""
Script to fix common test pattern violations in the SpacetimeDB Python SDK
"""

import os
import re
import glob
from typing import List, Tuple

def fix_import_patterns(file_path: str) -> bool:
    """Fix inconsistent import patterns in test files"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Check if this is a root-level test file (not in tests/ subdirectory)
    is_root_level = not '/tests/' in file_path and file_path.startswith('/Users/punk1290/git/spacetimedb-python-sdk/test_')
    
    if is_root_level:
        # Fix multiple sys.path manipulations
        lines = content.split('\n')
        new_lines = []
        sys_path_added = False
        
        for line in lines:
            # Skip duplicate sys.path lines
            if 'sys.path.insert' in line or 'sys.path.append' in line:
                if not sys_path_added:
                    # Add the standard import pattern
                    if 'import sys' in content and 'import os' in content:
                        new_lines.append("sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))")
                        sys_path_added = True
                continue
            new_lines.append(line)
        
        content = '\n'.join(new_lines)
    
    # Save if changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def fix_return_patterns(file_path: str) -> bool:
    """Fix return True/False patterns in test functions"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match test functions that end with return True/False
    # This is a simplified fix - more complex cases might need manual review
    patterns = [
        # Simple return True at end of function
        (r'(\n    )print\([^)]+\)\n    return True\n', r'\1print(\2)\n'),
        # Return False in else cases - replace with assertion
        (r'(\n    )return False\n', r'\1assert False, "Test condition not met"\n'),
        # Return True at end of function without print
        (r'(\n    )return True\n(?=\ndef|\nif __name__|$)', r'\1pass\n'),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    # Save if changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def find_test_files() -> List[str]:
    """Find all test files in the project"""
    test_files = []
    
    # Root level test files
    for pattern in ['test_*.py', 'tests/**/*.py']:
        test_files.extend(glob.glob(pattern, recursive=True))
    
    return [f for f in test_files if os.path.isfile(f)]

def main():
    """Main function to fix test patterns"""
    print("SpacetimeDB Python SDK Test Pattern Fixer")
    print("=" * 50)
    
    test_files = find_test_files()
    print(f"Found {len(test_files)} test files")
    
    import_fixes = 0
    return_fixes = 0
    
    for file_path in test_files:
        print(f"Processing: {file_path}")
        
        # Fix import patterns
        if fix_import_patterns(file_path):
            import_fixes += 1
            print(f"  ✓ Fixed import patterns")
        
        # Fix return patterns  
        if fix_return_patterns(file_path):
            return_fixes += 1
            print(f"  ✓ Fixed return patterns")
    
    print(f"\nSummary:")
    print(f"  Import pattern fixes: {import_fixes}")
    print(f"  Return pattern fixes: {return_fixes}")
    print(f"  Total files processed: {len(test_files)}")

if __name__ == "__main__":
    main()