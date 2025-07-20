#!/usr/bin/env python3
"""
Fix for SpacetimeDB Python SDK to work with v1.1.2

The issue: SpacetimeDB v1.1.2 uses different WebSocket paths and protocols:
- WebSocket endpoint: /v1/database/{identity}/subscribe (not /subscribe)
- WebSocket subprotocol: "v1.json.spacetimedb" or "v1.bsatn.spacetimedb"
"""

import re
import os

def fix_websocket_connection():
    """Fix the WebSocket connection to use v1.1.2 paths"""
    
    # Fix 1: Update the WebSocket path in spacetime_websocket_client.py
    ws_client_file = "src/spacetimedb_sdk/spacetime_websocket_client.py"
    
    if os.path.exists(ws_client_file):
        with open(ws_client_file, 'r') as f:
            content = f.read()
        
        # Fix the WebSocket path construction
        # Old: ws://{host}/subscribe
        # New: ws://{host}/v1/database/{database_identity}/subscribe
        
        # Look for the connect method
        old_pattern = r'(ws_url\s*=\s*f"ws://{self\.host})(:[^/]+)?(/subscribe.*?)"'
        new_pattern = r'\1\2/v1/database/{self.db_identity}/subscribe"'
        
        content = re.sub(old_pattern, new_pattern, content)
        
        # Also handle wss:// URLs
        old_pattern = r'(ws_url\s*=\s*f"wss://{self\.host})(:[^/]+)?(/subscribe.*?)"'
        new_pattern = r'\1\2/v1/database/{self.db_identity}/subscribe"'
        
        content = re.sub(old_pattern, new_pattern, content)
        
        # Fix the WebSocket subprotocol
        # Add subprotocol header if not present
        if 'subprotocols=' not in content:
            # Find the WebSocket connection call
            ws_pattern = r'(websocket\.connect\([^)]+)'
            replacement = r'\1, subprotocols=["v1.json.spacetimedb"]'
            content = re.sub(ws_pattern, replacement, content)
        
        with open(ws_client_file, 'w') as f:
            f.write(content)
        
        print(f"✓ Fixed WebSocket path in {ws_client_file}")
    
    # Fix 2: Update the connection builder if it exists
    conn_builder_file = "src/spacetimedb_sdk/connection_builder.py"
    
    if os.path.exists(conn_builder_file):
        with open(conn_builder_file, 'r') as f:
            content = f.read()
        
        # Look for WebSocket URL construction
        old_ws_pattern = r'ws://[^/]+/subscribe'
        new_ws_pattern = 'ws://{host}/v1/database/{db_identity}/subscribe'
        
        # This is a more complex fix - we need to ensure db_identity is available
        # Let's just add a comment for now
        if '/subscribe' in content and '/v1/database' not in content:
            content = f"""# Note: SpacetimeDB v1.1.2 requires WebSocket URLs in format:
# ws://host/v1/database/{{db_identity}}/subscribe
# with subprotocol "v1.json.spacetimedb"

{content}"""
            
            with open(conn_builder_file, 'w') as f:
                f.write(content)
            
            print(f"✓ Added v1.1.2 compatibility note to {conn_builder_file}")

def verify_fix():
    """Verify the fix was applied"""
    ws_client_file = "src/spacetimedb_sdk/spacetime_websocket_client.py"
    
    if os.path.exists(ws_client_file):
        with open(ws_client_file, 'r') as f:
            content = f.read()
        
        if '/v1/database/' in content:
            print("\n✅ Fix verified: WebSocket path updated to v1.1.2 format")
            return True
        else:
            print("\n❌ Fix not applied: WebSocket path still using old format")
            return False
    
    return False

if __name__ == "__main__":
    print("Applying SpacetimeDB v1.1.2 compatibility fix...")
    fix_websocket_connection()
    verify_fix()
    
    print("\n📝 Additional manual fixes may be needed:")
    print("1. Ensure db_identity is passed to WebSocket connection")
    print("2. Update any hardcoded WebSocket URLs to use /v1/database/{identity}/subscribe")
    print("3. Add WebSocket subprotocol 'v1.json.spacetimedb' to connection headers")
