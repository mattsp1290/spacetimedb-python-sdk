#!/usr/bin/env python3

import re
import os
import glob

def fix_imports(file_path):
    """Fix imports in a single file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original = content
        
        # Fix imports
        content = re.sub(r'from spacetimedb_sdk\.modern_client import ModernSpacetimeDBClient', 'from spacetimedb_sdk import SpacetimeDBClient', content)
        content = re.sub(r'from src\.spacetimedb_sdk\.modern_client import ModernSpacetimeDBClient', 'from spacetimedb_sdk import SpacetimeDBClient', content)
        content = re.sub(r'from spacetimedb_sdk\.spacetime_websocket_client import WebSocketClient', 'from spacetimedb_sdk import WebSocketClient', content)
        content = re.sub(r'from spacetimedb_sdk import ModernSpacetimeDBClient', 'from spacetimedb_sdk import SpacetimeDBClient', content)
        content = re.sub(r'from spacetimedb_sdk import ModernWebSocketClient', 'from spacetimedb_sdk import WebSocketClient', content)
        
        # Fix class references
        content = re.sub(r'\bModernSpacetimeDBClient\b', 'SpacetimeDBClient', content)
        content = re.sub(r'\bModernWebSocketClient\b', 'WebSocketClient', content)
        
        # Fix mock paths
        content = content.replace("'spacetimedb_sdk.modern_client.ModernSpacetimeDBClient'", "'spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient'")
        content = content.replace("'spacetimedb_sdk.modern_client.ModernWebSocketClient'", "'spacetimedb_sdk.websocket_client.WebSocketClient'")
        content = content.replace("'src.spacetimedb_sdk.modern_client.ModernSpacetimeDBClient'", "'spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient'")
        content = content.replace('"spacetimedb_sdk.modern_client.ModernSpacetimeDBClient"', '"spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient"')
        content = content.replace('"spacetimedb_sdk.modern_client.ModernWebSocketClient"', '"spacetimedb_sdk.websocket_client.WebSocketClient"')
        content = content.replace('"src.spacetimedb_sdk.modern_client.ModernSpacetimeDBClient"', '"spacetimedb_sdk.spacetimedb_client.SpacetimeDBClient"')
        
        if content != original:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"✓ Fixed {file_path}")
            return True
        else:
            print(f"- No changes needed for {file_path}")
            return False
    except Exception as e:
        print(f"✗ Error fixing {file_path}: {e}")
        return False

def main():
    files = glob.glob("*.py")
    fixed = 0
    
    for file_path in files:
        if file_path in ['fix_import_errors.py', 'bulk_fix_imports.py']:
            continue
        if fix_imports(file_path):
            fixed += 1
    
    print(f"\nFixed {fixed} files")

if __name__ == "__main__":
    main()