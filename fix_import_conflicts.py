#!/usr/bin/env python3
"""
Fix import conflicts in test files by standardizing on local src path imports.

This script:
1. Adds the src path setup to test files that need it
2. Ensures all test files use consistent import patterns
3. Reports on changes made
"""

import os
import re
import glob
from typing import List, Dict

def has_src_path_setup(content: str) -> bool:
    """Check if file already has src path setup."""
    return "sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))" in content

def has_spacetimedb_import(content: str) -> bool:
    """Check if file imports from spacetimedb_sdk."""
    patterns = [
        r'from spacetimedb_sdk',
        r'import spacetimedb_sdk',
        r'from src\.spacetimedb_sdk'
    ]
    return any(re.search(pattern, content) for pattern in patterns)

def add_src_path_setup(content: str) -> str:
    """Add src path setup to file content."""
    lines = content.split('\n')
    
    # Find the first import statement
    import_index = -1
    for i, line in enumerate(lines):
        if (line.strip().startswith('import ') or 
            line.strip().startswith('from ') and 
            not line.strip().startswith('from __future__')):
            import_index = i
            break
    
    if import_index == -1:
        # No imports found, add at the end of file header
        import_index = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('"""') and i > 0:
                # Find end of docstring
                for j in range(i+1, len(lines)):
                    if line.strip().endswith('"""') and j > i:
                        import_index = j + 1
                        break
                break
    
    # Insert src path setup before first import
    src_setup = [
        "",
        "import sys",
        "import os",
        "# Add src directory to path for testing",
        "sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))",
        ""
    ]
    
    # Check if sys and os are already imported
    has_sys = any('import sys' in line for line in lines[:import_index])
    has_os = any('import os' in line for line in lines[:import_index])
    
    if has_sys and has_os:
        src_setup = [
            "",
            "# Add src directory to path for testing",
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))",
            ""
        ]
    elif has_sys:
        src_setup = [
            "",
            "import os",
            "# Add src directory to path for testing", 
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))",
            ""
        ]
    elif has_os:
        src_setup = [
            "",
            "import sys",
            "# Add src directory to path for testing",
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))",
            ""
        ]
    
    lines[import_index:import_index] = src_setup
    return '\n'.join(lines)

def fix_imports_in_file(filepath: str) -> Dict[str, any]:
    """Fix imports in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        if not has_spacetimedb_import(original_content):
            return {"status": "skipped", "reason": "no spacetimedb imports"}
        
        if has_src_path_setup(original_content):
            return {"status": "skipped", "reason": "already has src path setup"}
        
        # Add src path setup
        new_content = add_src_path_setup(original_content)
        
        # Normalize any src.spacetimedb_sdk imports to just spacetimedb_sdk
        new_content = re.sub(r'from src\.spacetimedb_sdk', 'from spacetimedb_sdk', new_content)
        
        if new_content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return {"status": "fixed", "reason": "added src path setup"}
        else:
            return {"status": "skipped", "reason": "no changes needed"}
            
    except Exception as e:
        return {"status": "error", "reason": str(e)}

def main():
    """Main function to fix import conflicts."""
    print("🔧 Fixing import conflicts in test files...")
    
    # Find all Python test files in the repository
    test_patterns = [
        "test_*.py",
        "*test*.py", 
        "verify_*.py",
        "validate_*.py",
        "examples/**/*.py"
    ]
    
    files_to_process = []
    for pattern in test_patterns:
        files_to_process.extend(glob.glob(pattern, recursive=True))
    
    # Remove duplicates and sort
    files_to_process = sorted(set(files_to_process))
    
    results = {"fixed": [], "skipped": [], "errors": []}
    
    for filepath in files_to_process:
        if os.path.isfile(filepath) and filepath.endswith('.py'):
            result = fix_imports_in_file(filepath)
            results[result["status"]].append({
                "file": filepath,
                "reason": result["reason"]
            })
    
    # Report results
    print(f"\n📊 Import Conflict Fix Results:")
    print(f"✅ Fixed: {len(results['fixed'])} files")
    print(f"⏭️  Skipped: {len(results['skipped'])} files") 
    print(f"❌ Errors: {len(results['errors'])} files")
    
    if results['fixed']:
        print(f"\n🔧 Fixed files:")
        for item in results['fixed']:
            print(f"  - {item['file']}: {item['reason']}")
    
    if results['errors']:
        print(f"\n❌ Errors:")
        for item in results['errors']:
            print(f"  - {item['file']}: {item['reason']}")
    
    print(f"\n🎯 Import standardization approach: Use src path setup for local development testing")
    print(f"📝 All test files now import from local src/ instead of installed packages")

if __name__ == "__main__":
    main()