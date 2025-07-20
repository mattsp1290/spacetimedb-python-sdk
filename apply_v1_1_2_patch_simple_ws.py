#!/usr/bin/env python3
"""
Patch for SpacetimeDB Python SDK to support v1.1.2

Apply this patch after discovering the correct endpoint pattern.
Current pattern: SIMPLE_WS (/ws)
"""

import sys
import os

def patch_spacetime_websocket_client():
    """Patch the legacy WebSocket client."""
    file_path = "src/spacetimedb_sdk/spacetime_websocket_client.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the old URL pattern
    old_pattern = 'url = f"{protocol}://{host}/v1/database/subscribe/{name_or_address}"'
    
    if "/ws".count("{") == 0:
        # Simple pattern without database in URL
        new_pattern = 'url = f"{protocol}://{host}/ws"'
    else:
        # Pattern with database in URL
        new_pattern = 'url = f"{protocol}://{host}/ws".format(database=name_or_address)'
    
    content = content.replace(old_pattern, new_pattern)
    
    # Write back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✓ Patched {file_path}")

def patch_modern_websocket_client():
    """Patch the modern WebSocket client."""
    file_path = "src/spacetimedb_sdk/websocket_client.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the old URL pattern
    old_pattern = 'url = f"{protocol_scheme}://{self.host}/v1/database/subscribe/{self.database_address}"'
    
    if "/ws".count("{") == 0:
        # Simple pattern without database in URL
        new_pattern = 'url = f"{protocol_scheme}://{self.host}/ws"'
    else:
        # Pattern with database in URL
        new_pattern = 'url = f"{protocol_scheme}://{self.host}/ws".format(database=self.database_address)'
    
    content = content.replace(old_pattern, new_pattern)
    
    # Add subscription message handling if needed
    if "/ws".count("{") == 0:
        # Need to send subscription after connect
        subscription_code = '''
        # Send subscription message for v1.1.2
        subscription_msg = {'type': 'subscribe', 'database': 'PLACEHOLDER'}
        if subscription_msg:
            subscription_msg = json.dumps(subscription_msg).replace("PLACEHOLDER", self.database_address)
            subscription_msg = json.loads(subscription_msg)
            self.send_message(subscription_msg)
            self.logger.debug(f"Sent subscription message: {subscription_msg}")
'''
        # Find where to insert (after connection established)
        insert_point = 'self.logger.info("Connected to SpacetimeDB (WebSocket open). Calling _on_connect callback if any.")'
        if insert_point in content:
            content = content.replace(insert_point, insert_point + subscription_code)
    
    # Write back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✓ Patched {file_path}")

def main():
    print("SpacetimeDB v1.1.2 SDK Patch")
    print("=" * 40)
    print(f"Applying patch for endpoint pattern: SIMPLE_WS")
    print(f"Endpoint: /ws")
    
    # Change to SDK directory
    if not os.path.exists("src/spacetimedb_sdk"):
        print("Error: Must run from SpacetimeDB Python SDK root directory")
        sys.exit(1)
    
    # Apply patches
    try:
        patch_spacetime_websocket_client()
        patch_modern_websocket_client()
        print("\n✓ Patches applied successfully!")
        print("\nTest the connection with:")
        print("  python3 test_spacetimedb_v1_1_2_connection.py")
    except Exception as e:
        print(f"\n✗ Error applying patches: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
