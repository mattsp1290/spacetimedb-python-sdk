#!/usr/bin/env python3
"""
SpacetimeDB v1.1.2 WebSocket Endpoint Fix

This script provides a flexible approach to fixing the WebSocket endpoint issue
by implementing configurable endpoint patterns that can be easily updated.
"""

import os
import sys
import json
from typing import Optional, Dict, Tuple
from enum import Enum

class SpacetimeDBVersion(Enum):
    """Known SpacetimeDB versions and their characteristics."""
    LEGACY = "1.0.x"  # Uses /v1/database/subscribe/{database}
    V1_1_2 = "1.1.2"  # Unknown pattern - needs discovery
    
class EndpointPattern(Enum):
    """Possible WebSocket endpoint patterns."""
    LEGACY = "/v1/database/subscribe/{database}"
    SIMPLE_WS = "/ws"
    SIMPLE_WEBSOCKET = "/websocket"
    VERSIONED_WS = "/v1/ws"
    VERSIONED_WEBSOCKET = "/v1/websocket"
    DATABASE_WS = "/database/{database}/ws"
    DATABASE_WEBSOCKET = "/database/{database}/websocket"
    MODULE_WS = "/module/{database}/ws"
    API_WS = "/api/v1/ws"

class SpacetimeDBEndpointConfig:
    """Configuration for SpacetimeDB endpoint patterns."""
    
    # Default endpoint patterns for each version
    VERSION_ENDPOINTS = {
        SpacetimeDBVersion.LEGACY: EndpointPattern.LEGACY,
        SpacetimeDBVersion.V1_1_2: EndpointPattern.SIMPLE_WS,  # Best guess - update after discovery
    }
    
    # Subscription message patterns for endpoints that don't include database in URL
    SUBSCRIPTION_PATTERNS = {
        EndpointPattern.SIMPLE_WS: {
            "type": "subscribe",
            "database": "{database}"
        },
        EndpointPattern.SIMPLE_WEBSOCKET: {
            "subscribe": {
                "database": "{database}"
            }
        },
        EndpointPattern.VERSIONED_WS: {
            "subscribe": {
                "query_strings": ["SELECT * FROM {database}"]
            }
        },
        EndpointPattern.API_WS: {
            "action": "subscribe",
            "params": {
                "database": "{database}"
            }
        }
    }
    
    @classmethod
    def get_endpoint_url(cls, host: str, database: str, version: SpacetimeDBVersion = None, pattern: EndpointPattern = None) -> str:
        """Get the WebSocket endpoint URL for the given configuration."""
        # Use explicit pattern if provided, otherwise use version default
        if pattern is None:
            pattern = cls.VERSION_ENDPOINTS.get(version, EndpointPattern.LEGACY)
        
        # Format the endpoint pattern
        endpoint = pattern.value.format(database=database)
        
        # Construct full URL
        protocol = "wss" if "https" in host or ":443" in host else "ws"
        host = host.replace("http://", "").replace("https://", "").replace("ws://", "").replace("wss://", "")
        
        return f"{protocol}://{host}{endpoint}"
    
    @classmethod
    def get_subscription_message(cls, database: str, pattern: EndpointPattern) -> Optional[Dict]:
        """Get the subscription message for patterns that require post-connection subscription."""
        if pattern in cls.SUBSCRIPTION_PATTERNS:
            message = cls.SUBSCRIPTION_PATTERNS[pattern].copy()
            # Replace {database} placeholder
            message_str = json.dumps(message).replace("{database}", database)
            return json.loads(message_str)
        return None
    
    @classmethod
    def detect_version(cls, host: str) -> Tuple[SpacetimeDBVersion, Optional[str]]:
        """Attempt to detect SpacetimeDB version from server (placeholder for real implementation)."""
        # In a real implementation, this would:
        # 1. Try to connect to /health or /version endpoint
        # 2. Parse version from response
        # 3. Return detected version
        
        # For now, return unknown
        return SpacetimeDBVersion.V1_1_2, None

def generate_patch_file(pattern: EndpointPattern = EndpointPattern.SIMPLE_WS):
    """Generate a patch file for the SDK based on the discovered endpoint pattern."""
    
    patch_content = f"""#!/usr/bin/env python3
\"\"\"
Patch for SpacetimeDB Python SDK to support v1.1.2

Apply this patch after discovering the correct endpoint pattern.
Current pattern: {pattern.name} ({pattern.value})
\"\"\"

import sys
import os

def patch_spacetime_websocket_client():
    \"\"\"Patch the legacy WebSocket client.\"\"\"
    file_path = "src/spacetimedb_sdk/spacetime_websocket_client.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the old URL pattern
    old_pattern = 'url = f"{{protocol}}://{{host}}/v1/database/subscribe/{{name_or_address}}"'
    
    if "{pattern.value}".count("{{") == 0:
        # Simple pattern without database in URL
        new_pattern = 'url = f"{{protocol}}://{{host}}{pattern.value}"'
    else:
        # Pattern with database in URL
        new_pattern = 'url = f"{{protocol}}://{{host}}{pattern.value}".format(database=name_or_address)'
    
    content = content.replace(old_pattern, new_pattern)
    
    # Write back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✓ Patched {{file_path}}")

def patch_modern_websocket_client():
    \"\"\"Patch the modern WebSocket client.\"\"\"
    file_path = "src/spacetimedb_sdk/websocket_client.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the old URL pattern
    old_pattern = 'url = f"{{protocol_scheme}}://{{self.host}}/v1/database/subscribe/{{self.database_address}}"'
    
    if "{pattern.value}".count("{{") == 0:
        # Simple pattern without database in URL
        new_pattern = 'url = f"{{protocol_scheme}}://{{self.host}}{pattern.value}"'
    else:
        # Pattern with database in URL
        new_pattern = 'url = f"{{protocol_scheme}}://{{self.host}}{pattern.value}".format(database=self.database_address)'
    
    content = content.replace(old_pattern, new_pattern)
    
    # Add subscription message handling if needed
    if "{pattern.value}".count("{{") == 0:
        # Need to send subscription after connect
        subscription_code = '''
        # Send subscription message for v1.1.2
        subscription_msg = {repr(SpacetimeDBEndpointConfig.get_subscription_message("PLACEHOLDER", pattern))}
        if subscription_msg:
            subscription_msg = json.dumps(subscription_msg).replace("PLACEHOLDER", self.database_address)
            subscription_msg = json.loads(subscription_msg)
            self.send_message(subscription_msg)
            self.logger.debug(f"Sent subscription message: {{subscription_msg}}")
'''
        # Find where to insert (after connection established)
        insert_point = 'self.logger.info("Connected to SpacetimeDB (WebSocket open). Calling _on_connect callback if any.")'
        if insert_point in content:
            content = content.replace(insert_point, insert_point + subscription_code)
    
    # Write back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✓ Patched {{file_path}}")

def main():
    print("SpacetimeDB v1.1.2 SDK Patch")
    print("=" * 40)
    print(f"Applying patch for endpoint pattern: {pattern.name}")
    print(f"Endpoint: {pattern.value}")
    
    # Change to SDK directory
    if not os.path.exists("src/spacetimedb_sdk"):
        print("Error: Must run from SpacetimeDB Python SDK root directory")
        sys.exit(1)
    
    # Apply patches
    try:
        patch_spacetime_websocket_client()
        patch_modern_websocket_client()
        print("\\n✓ Patches applied successfully!")
        print("\\nTest the connection with:")
        print("  python3 test_spacetimedb_v1_1_2_connection.py")
    except Exception as e:
        print(f"\\n✗ Error applying patches: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    
    filename = f"apply_v1_1_2_patch_{pattern.name.lower()}.py"
    with open(filename, 'w') as f:
        f.write(patch_content)
    
    os.chmod(filename, 0o755)
    print(f"Generated patch file: {filename}")
    return filename

def main():
    """Main function to demonstrate the fix approach."""
    print("SpacetimeDB v1.1.2 WebSocket Endpoint Fix")
    print("=" * 50)
    
    print("\n1. Current SDK expects:")
    print("   ws://localhost:3000/v1/database/subscribe/{database}")
    
    print("\n2. Most likely v1.1.2 patterns:")
    for pattern in [EndpointPattern.SIMPLE_WS, EndpointPattern.SIMPLE_WEBSOCKET, 
                    EndpointPattern.VERSIONED_WS, EndpointPattern.API_WS]:
        url = SpacetimeDBEndpointConfig.get_endpoint_url("localhost:3000", "test_module", pattern=pattern)
        print(f"   - {pattern.name}: {url}")
        
        sub_msg = SpacetimeDBEndpointConfig.get_subscription_message("test_module", pattern)
        if sub_msg:
            print(f"     Subscription: {json.dumps(sub_msg, indent=6).replace('{', ' {', 1)}")
    
    print("\n3. To apply a fix:")
    print("   a) First, discover the actual endpoint using the discovery tools")
    print("   b) Then generate and apply a patch:")
    print()
    
    # Generate patch files for most likely patterns
    print("Generating patch files for common patterns...")
    for pattern in [EndpointPattern.SIMPLE_WS, EndpointPattern.SIMPLE_WEBSOCKET, 
                    EndpointPattern.VERSIONED_WS]:
        generate_patch_file(pattern)
    
    print("\n4. Quick test after patching:")
    print("   python3 test_spacetimedb_v1_1_2_connection.py")
    
    print("\n5. Full test with Blackholio:")
    print("   cd /Users/punk1290/git/blackholio-agent")
    print("   python scripts/train_agent.py --total-timesteps 1000")
    
    print("\nREMEMBER: First use the discovery tools to find the actual endpoint!")
    print("Then apply the appropriate patch file.")

if __name__ == "__main__":
    main()
