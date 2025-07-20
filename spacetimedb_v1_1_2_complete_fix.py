#!/usr/bin/env python3
"""
Complete fix for SpacetimeDB Python SDK to work with v1.1.2

The issue: SpacetimeDB v1.1.2 changed the WebSocket endpoint structure
- Old: ws://{host}/ws
- New: ws://{host}/v1/database/{identity}/subscribe

The Python SDK needs to be updated to use the new endpoint format.
"""

import os
import re

def fix_websocket_client():
    """Fix the WebSocket client to use v1.1.2 endpoints"""
    
    ws_client_file = "src/spacetimedb_sdk/spacetime_websocket_client.py"
    
    if not os.path.exists(ws_client_file):
        print(f"❌ File not found: {ws_client_file}")
        return False
    
    with open(ws_client_file, 'r') as f:
        original_content = f.read()
    
    content = original_content
    
    # Fix 1: Update the connect method to accept db_identity parameter
    # Add db_identity parameter to connect method
    if "def connect(self, auth, host, name_or_address, ssl_enabled):" in content:
        content = content.replace(
            "def connect(self, auth, host, name_or_address, ssl_enabled):",
            "def connect(self, auth, host, name_or_address, ssl_enabled, db_identity=None):"
        )
        print("✓ Added db_identity parameter to connect method")
    
    # Fix 2: Update the URL construction
    # Change from /ws to /v1/database/{identity}/subscribe
    old_url_pattern = r'url = f"{protocol}://{host}/ws"'
    
    if old_url_pattern in content:
        # Replace the URL construction
        new_url_construction = '''# Use db_identity if provided, otherwise try to resolve name_or_address
        if db_identity:
            url = f"{protocol}://{host}/v1/database/{db_identity}/subscribe"
        else:
            # For v1.1.2 compatibility, we need the database identity
            # If not provided, we'll use name_or_address as identity
            url = f"{protocol}://{host}/v1/database/{name_or_address}/subscribe"'''
        
        content = content.replace(
            'url = f"{protocol}://{host}/ws"',
            new_url_construction
        )
        print("✓ Updated WebSocket URL to v1.1.2 format")
    
    # Fix 3: Store db_identity in the class
    if "self.host = host" in content and "self.db_identity" not in content:
        content = content.replace(
            "self.host = host",
            "self.host = host\n        self.db_identity = db_identity"
        )
        print("✓ Added db_identity storage to class")
    
    # Fix 4: Update protocol to match v1.1.2 format if needed
    # The protocol is already passed as subprotocols parameter, so we're good
    
    # Write the fixed content
    if content != original_content:
        with open(ws_client_file, 'w') as f:
            f.write(content)
        print(f"\n✅ Successfully updated {ws_client_file}")
        return True
    else:
        print(f"\n⚠️  No changes needed in {ws_client_file}")
        return False

def fix_spacetimedb_client():
    """Fix the main SpacetimeDB client to pass db_identity"""
    
    client_file = "src/spacetimedb_sdk/spacetimedb_client.py"
    
    if not os.path.exists(client_file):
        print(f"⚠️  File not found: {client_file} - skipping")
        return False
    
    with open(client_file, 'r') as f:
        original_content = f.read()
    
    content = original_content
    
    # Look for websocket_client.connect calls and update them
    # Pattern to find connect calls
    connect_pattern = r'(self\.websocket_client\.connect\([^)]+\))'
    
    def update_connect_call(match):
        call = match.group(1)
        if 'db_identity=' not in call:
            # Add db_identity parameter
            # Remove the closing parenthesis and add the parameter
            return call[:-1] + f", db_identity=self.db_address)"
        return call
    
    content = re.sub(connect_pattern, update_connect_call, content)
    
    if content != original_content:
        with open(client_file, 'w') as f:
            f.write(content)
        print(f"✅ Successfully updated {client_file}")
        return True
    else:
        print(f"⚠️  No changes needed in {client_file}")
        return False

def create_test_script():
    """Create a test script to verify the fix"""
    
    test_script = """#!/usr/bin/env python3
'''Test script to verify SpacetimeDB v1.1.2 connection'''

import asyncio
import websocket

# Test parameters
HOST = "localhost:3000"
DB_IDENTITY = "your_database_identity_here"  # Replace with actual identity
PROTOCOL = "v1.json.spacetimedb"

def test_direct_websocket():
    '''Test direct WebSocket connection to v1.1.2'''
    
    url = f"ws://{HOST}/v1/database/{DB_IDENTITY}/subscribe"
    
    print(f"Testing WebSocket connection to: {url}")
    print(f"Using protocol: {PROTOCOL}")
    
    try:
        ws = websocket.create_connection(
            url,
            subprotocols=[PROTOCOL]
        )
        print("✅ WebSocket connection successful!")
        
        # The server should send an IdentityToken message first
        message = ws.recv()
        print(f"Received message: {message[:100]}...")
        
        ws.close()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    print("SpacetimeDB v1.1.2 WebSocket Test")
    print("-" * 40)
    test_direct_websocket()
"""
    
    with open("test_v1_1_2_websocket.py", 'w') as f:
        f.write(test_script)
    
    print("✅ Created test_v1_1_2_websocket.py")

def main():
    print("SpacetimeDB v1.1.2 Python SDK Fix")
    print("=" * 50)
    
    # Apply fixes
    ws_fixed = fix_websocket_client()
    client_fixed = fix_spacetimedb_client()
    
    # Create test script
    create_test_script()
    
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"- WebSocket client fixed: {'✅' if ws_fixed else '⚠️  No changes'}")
    print(f"- SpacetimeDB client fixed: {'✅' if client_fixed else '⚠️  No changes'}")
    
    print("\n📝 Next steps:")
    print("1. Update your code to pass the database identity when connecting")
    print("2. Use the test script to verify the connection works")
    print("3. The WebSocket protocol should be 'v1.json.spacetimedb' or 'v1.bsatn.spacetimedb'")
    
    print("\nExample usage:")
    print("```python")
    print("client = SpacetimeDBClient()")
    print("# Make sure to pass the database identity")
    print('client.connect("localhost:3000", "your_db_identity", auth_token)')
    print("```")

if __name__ == "__main__":
    main()
