#!/usr/bin/env python3
"""Test WebSocket frame types with websocket-client library."""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import websocket
import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper

# Test that bytes are sent as binary frames
print("Testing WebSocket frame type behavior:")

# Create binary data
helper = SpacetimeDBProtocolHelper(use_binary=True)
binary_data = helper.encode_subscription(["test_table"])

print(f"\nBinary data type: {type(binary_data)}")
print(f"Binary data is bytes: {isinstance(binary_data, bytes)}")
print(f"Binary data length: {len(binary_data)}")
print(f"First 20 bytes: {binary_data[:20].hex()}")

# Check websocket-client documentation for binary frame sending
print("\nChecking websocket-client binary frame behavior...")
print("According to websocket-client docs:")
print("- ws.send(data, opcode=ABNF.OPCODE_TEXT) sends text frame")
print("- ws.send(data, opcode=ABNF.OPCODE_BINARY) sends binary frame") 
print("- ws.send(bytes_data) should auto-detect and send as binary frame")

# Let's check what ABNF opcodes are available
try:
    from websocket import ABNF
    print(f"\nAvailable opcodes:")
    print(f"OPCODE_TEXT: {ABNF.OPCODE_TEXT}")
    print(f"OPCODE_BINARY: {ABNF.OPCODE_BINARY}")
except ImportError:
    print("\nCouldn't import ABNF opcodes")

print("\nSUGGESTION: The issue might be that the WebSocket client needs to explicitly specify the opcode for binary frames.")
print("Instead of: ws.send(encoded_data)")
print("Use: ws.send(encoded_data, opcode=websocket.ABNF.OPCODE_BINARY)")