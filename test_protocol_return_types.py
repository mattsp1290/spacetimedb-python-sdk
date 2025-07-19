#!/usr/bin/env python3
"""Test to verify protocol helper return types."""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper

# Test binary protocol
print("Testing Binary Protocol:")
binary_helper = SpacetimeDBProtocolHelper(use_binary=True)
binary_result = binary_helper.encode_subscription(["test_table"])
print(f"Type: {type(binary_result)}")
print(f"Is bytes: {isinstance(binary_result, bytes)}")
print(f"Length: {len(binary_result)}")
print(f"First 20 bytes (hex): {binary_result[:20].hex()}")
print(f"First 20 bytes (repr): {repr(binary_result[:20])}")
print()

# Test JSON protocol
print("Testing JSON Protocol:")
json_helper = SpacetimeDBProtocolHelper(use_binary=False)
json_result = json_helper.encode_subscription(["test_table"])
print(f"Type: {type(json_result)}")
print(f"Is bytes: {isinstance(json_result, bytes)}")
print(f"Length: {len(json_result)}")
print(f"First 20 bytes (hex): {json_result[:20].encode('utf-8').hex() if isinstance(json_result, str) else json_result[:20].hex()}")
print(f"First 20 bytes (repr): {repr(json_result[:20])}")
print(f"Decoded as string: {json_result[:100] if isinstance(json_result, str) else json_result.decode('utf-8')[:100]}")