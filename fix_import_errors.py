#!/usr/bin/env python3
"""
Automated fix script for import errors in SpacetimeDB Python SDK
Fixes ModernSpacetimeDBClient → SpacetimeDBClient and ModernWebSocketClient → WebSocketClient
"""

import os
import re
import subprocess
from pathlib import Path

def find_python_files():
    """Find all Python files that need fixing"""
    cmd = ["find", ".", "-name", "*.py", "-type", "f"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return [f.strip() for f in result.stdout.split('\n') if f.strip()]

def find_files_with_pattern(pattern):
    """Find files containing specific patterns using grep"""
    cmd = ["grep", "-l", "-r", pattern, ".", "--include=*.py"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return [f.strip() for f in result.stdout.split('\n') if f.strip()]

def fix_file_content(file_path):
    """Apply all fixes to a single file"""
    print(f"Processing: {file_path}")
    
    # Skip the fix script itself
    if file_path.endswith('fix_import_errors.py'):
        print("  ⏭️  Skipping fix script itself")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes = []
        
        # Fix 1: Import from modern_client module 
        old_import1 = "from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient"
        new_import1 = "from spacetimedb_sdk import SpacetimeDBClient"
        if old_import1 in content:
            content = content.replace(old_import1, new_import1)
            changes.append(f"  ✓ Fixed import: {old_import1} → {new_import1}")
        
        # Fix 2: Import from src.spacetimedb_sdk.modern_client
        old_import2 = "from src.spacetimedb_sdk.modern_client import ModernSpacetimeDBClient"
        new_import2 = "from spacetimedb_sdk import SpacetimeDBClient"
        if old_import2 in content:
            content = content.replace(old_import2, new_import2)
            changes.append(f"  ✓ Fixed import: {old_import2} → {new_import2}")
        
        # Fix 3: Import from spacetime_websocket_client
        old_import3 = "from spacetimedb_sdk.spacetime_websocket_client import WebSocketClient"
        new_import3 = "from spacetimedb_sdk import WebSocketClient"
        if old_import3 in content:
            content = content.replace(old_import3, new_import3)
            changes.append(f"  ✓ Fixed import: {old_import3} → {new_import3}")
            
        # Fix 4: Import with different patterns
        old_import4 = "from src.spacetimedb_sdk.spacetime_websocket_client import WebSocketClient"
        new_import4 = "from spacetimedb_sdk import WebSocketClient"
        if old_import4 in content:
            content = content.replace(old_import4, new_import4)
            changes.append(f"  ✓ Fixed import: {old_import4} → {new_import4}")
        
        # Fix 5: Class name references - ModernSpacetimeDBClient → SpacetimeDBClient
        original_had_modern_client = 'ModernSpacetimeDBClient' in content
        content = re.sub(r'\bModernSpacetimeDBClient\b', 'SpacetimeDBClient', content)
        if original_had_modern_client:
            changes.append(f"  ✓ Fixed class references: ModernSpacetimeDBClient → SpacetimeDBClient")
        
        # Fix 6: Class name references - ModernWebSocketClient → WebSocketClient  
        original_had_modern_ws = 'ModernWebSocketClient' in content
        content = re.sub(r'\bModernWebSocketClient\b', 'WebSocketClient', content)
        if original_had_modern_ws:
            changes.append(f"  ✓ Fixed class references: ModernWebSocketClient → WebSocketClient")
        
        # Fix 7: Mock patch paths - modern_client.ModernSpacetimeDBClient
        mock_patterns = [
            ("'spacetimedb_sdk.modern_client.ModernSpacetimeDBClient'", "'spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient'"),
            ("'src.spacetimedb_sdk.modern_client.ModernSpacetimeDBClient'", "'spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient'"),
            ("'spacetimedb_sdk.modern_client.ModernWebSocketClient'", "'spacetimedb_sdk.websocket_client.WebSocketClient'"),
            ('"spacetimedb_sdk.modern_client.ModernSpacetimeDBClient"', '"spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient"'),
            ('"src.spacetimedb_sdk.modern_client.ModernSpacetimeDBClient"', '"spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient"'),
            ('"spacetimedb_sdk.modern_client.ModernWebSocketClient"', '"spacetimedb_sdk.websocket_client.WebSocketClient"'),
        ]
        
        for old_pattern, new_pattern in mock_patterns:
            if old_pattern in content:
                content = content.replace(old_pattern, new_pattern)
                changes.append(f"  ✓ Fixed mock path: {old_pattern} → {new_pattern}")
        
        # Fix 8: Handle attribute access patterns like ws_client.ModernWebSocketClient
        original_had_attr_ws = re.search(r'\w+\.ModernWebSocketClient', content)
        content = re.sub(r'(\w+)\.ModernWebSocketClient', r'\1.WebSocketClient', content)
        if original_had_attr_ws:
            changes.append(f"  ✓ Fixed attribute access: *.ModernWebSocketClient → *.WebSocketClient")
        
        # Fix 9: Handle attribute access patterns like some_module.ModernSpacetimeDBClient  
        original_had_attr_client = re.search(r'\w+\.ModernSpacetimeDBClient', content)
        content = re.sub(r'(\w+)\.ModernSpacetimeDBClient', r'\1.SpacetimeDBClient', content)
        if original_had_attr_client:
            changes.append(f"  ✓ Fixed attribute access: *.ModernSpacetimeDBClient → *.SpacetimeDBClient")
        
        # Only write if changes were made
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if changes:
                print(f"  📝 Applied {len(changes)} fix(es):")
                for change in changes:
                    print(change)
            return True
        else:
            print(f"  ⏭️  No changes needed")
            return False
            
    except Exception as e:
        print(f"  ❌ Error processing {file_path}: {e}")
        return False

def main():
    """Main execution function"""
    print("🔧 SpacetimeDB Python SDK Import Error Fix Script")
    print("=" * 60)
    
    # Find all files that might need fixing
    files_to_check = []
    
    # Find files with ModernSpacetimeDBClient or ModernWebSocketClient
    modern_client_files = find_files_with_pattern("ModernSpacetimeDBClient|ModernWebSocketClient")
    files_to_check.extend(modern_client_files)
    
    # Find files importing from old modules
    import_files = find_files_with_pattern("from.*modern_client|from.*spacetime_websocket_client")
    files_to_check.extend(import_files)
    
    # Remove duplicates and sort
    files_to_check = sorted(list(set(files_to_check)))
    
    # Filter out this script itself
    files_to_check = [f for f in files_to_check if not f.endswith('fix_import_errors.py')]
    
    if not files_to_check:
        print("✅ No files found that need fixing!")
        return
    
    print(f"📂 Found {len(files_to_check)} files to process:")
    for f in files_to_check:
        print(f"   - {f}")
    print()
    
    # Process each file
    fixed_count = 0
    for file_path in files_to_check:
        if fix_file_content(file_path):
            fixed_count += 1
        print()  # Add spacing between files
    
    print("=" * 60)
    print(f"✅ Processing complete!")
    print(f"📊 Files processed: {len(files_to_check)}")
    print(f"🛠️  Files fixed: {fixed_count}")
    print(f"⏭️  Files unchanged: {len(files_to_check) - fixed_count}")
    
    if fixed_count > 0:
        print(f"\n🎉 Successfully fixed import errors in {fixed_count} files!")
        print("💡 Next steps:")
        print("   1. Run the tests to verify fixes work")
        print("   2. Check for any remaining import errors")
        print("   3. Commit the changes if all tests pass")
    else:
        print("\nℹ️  No files needed fixing - imports may already be correct!")

if __name__ == "__main__":
    main()