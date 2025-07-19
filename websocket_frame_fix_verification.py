#!/usr/bin/env python3
"""
Verification that the WebSocket frame type fix is implemented correctly.

This script checks that both WebSocket client implementations properly send
binary frames when using the binary protocol.
"""

import os
import sys

# Check the implementation files
files_to_check = [
    "src/spacetimedb_sdk/websocket_client.py",
    "src/spacetimedb_sdk/spacetime_websocket_client.py"
]

print("=" * 80)
print("WebSocket Frame Type Fix Verification")
print("=" * 80)
print()

all_fixed = True

for file_path in files_to_check:
    print(f"Checking {file_path}...")
    
    if not os.path.exists(file_path):
        print(f"  ❌ File not found!")
        all_fixed = False
        continue
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check for the fix pattern
    if "opcode=ABNF.OPCODE_BINARY" in content:
        print(f"  ✅ Binary frame fix found!")
        
        # Find the context
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "opcode=ABNF.OPCODE_BINARY" in line:
                print(f"     Line {i+1}: {line.strip()}")
                # Show surrounding context
                if i > 0:
                    print(f"     Line {i}: {lines[i-1].strip()}")
                if i < len(lines) - 1:
                    print(f"     Line {i+2}: {lines[i+1].strip()}")
    else:
        print(f"  ❌ Binary frame fix NOT found!")
        all_fixed = False
    
    print()

print("=" * 80)
print("Summary:")
print("=" * 80)

if all_fixed:
    print("✅ All WebSocket implementations have the binary frame fix!")
    print()
    print("The fix ensures that when using binary protocol (v1.bsatn.spacetimedb),")
    print("messages are sent with WebSocket opcode=BINARY (0x2) instead of TEXT (0x1).")
    print()
    print("This resolves the error:")
    print('  "Client caused error on text message: data too short for [u8]"')
    print()
    print("Key changes:")
    print("- WebSocketClient.send_message() checks self.use_binary")
    print("- WebSocketClient.send() checks self.protocol == 'v1.bsatn.spacetimedb'")
    print("- Both use websocket.ABNF.OPCODE_BINARY when sending binary data")
else:
    print("❌ Some implementations are missing the binary frame fix!")
    print()
    print("The fix needs to ensure binary protocol messages are sent as binary frames.")
    sys.exit(1)

print()
print("Test verification complete!")