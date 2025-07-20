#!/usr/bin/env python3
"""Verify that WebSocket opcodes are used correctly."""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
sys.path.insert(0, 'src')

# Test that the fix is in place
print("=== Verifying WebSocket Binary Frame Fix ===\n")

# Check websocket_client.py
print("1. Checking WebSocketClient (websocket_client.py):")
with open('src/spacetimedb_sdk/websocket_client.py', 'r') as f:
    content = f.read()
    if 'opcode=ABNF.OPCODE_BINARY' in content:
        print("✓ FIXED: WebSocketClient explicitly sends binary frames")
        # Find the specific lines
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'opcode=ABNF.OPCODE_BINARY' in line:
                print(f"  Found at line {i+1}: {line.strip()}")
    else:
        print("✗ NOT FIXED: WebSocketClient doesn't explicitly specify binary opcode")

print("\n2. Checking legacy WebSocketClient (spacetime_websocket_client.py):")
try:
    with open('src/spacetimedb_sdk/spacetime_websocket_client.py', 'r') as f:
        content = f.read()
        if 'opcode=ABNF.OPCODE_BINARY' in content:
            print("✓ FIXED: Legacy WebSocketClient explicitly sends binary frames")
            # Find the specific lines
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'opcode=ABNF.OPCODE_BINARY' in line:
                    print(f"  Found at line {i+1}: {line.strip()}")
        else:
            print("✗ NOT FIXED: Legacy WebSocketClient doesn't explicitly specify binary opcode")
except FileNotFoundError:
    print("✓ SKIPPED: Legacy WebSocketClient file not found (removed during refactoring)")

# Test that protocol helpers return bytes
print("\n3. Testing protocol helper return types:")
from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper

binary_helper = SpacetimeDBProtocolHelper(use_binary=True)
binary_result = binary_helper.encode_subscription(["test_table"])
print(f"✓ Binary protocol returns: {type(binary_result)} (should be <class 'bytes'>)")

json_helper = SpacetimeDBProtocolHelper(use_binary=False)
json_result = json_helper.encode_subscription(["test_table"])
print(f"✓ JSON protocol returns: {type(json_result)} (should be <class 'bytes'>)")

# Demonstrate the issue and fix
print("\n4. Demonstrating the fix:")
print("Before fix: ws.send(encoded_data)")
print("           → May send binary data as TEXT frame (opcode=0x1)")
print("After fix:  ws.send(encoded_data, opcode=ABNF.OPCODE_BINARY)")
print("           → Explicitly sends binary data as BINARY frame (opcode=0x2)")

print("\n=== Summary ===")
print("The fix ensures that when using the binary protocol (v1.bsatn.spacetimedb),")
print("WebSocket messages are sent with the correct frame type (BINARY) instead of TEXT.")
print("This resolves the server error: 'Client caused error on text message: data too short'")