#!/usr/bin/env python3
"""
Test script to verify the fix for tag 0x13 error in SpaceTimeDB protocol.

This tests that ClientMessage variants are encoded without the TAG_ENUM prefix,
which was causing "unknown tag 0x13 for sum type ClientMessage" errors.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper
from spacetimedb_sdk.protocol import Subscribe, CallReducer, OneOffQuery
from spacetimedb_sdk.call_reducer_flags import CallReducerFlags
import struct


def test_subscribe_encoding():
    """Test that Subscribe messages don't start with TAG_ENUM (0x13)."""
    helper = SpacetimeDBProtocolHelper(use_binary=True)
    
    # Create a subscription message
    tables = ["entity", "player", "circle"]
    binary_message = helper.encode_subscription(tables, request_id=123)
    
    # Check the first byte - it should be 0x01 (variant index 1 for Subscribe)
    # NOT 0x13 (TAG_ENUM)
    first_bytes = binary_message[:4]
    variant_index = struct.unpack('<I', first_bytes)[0]
    
    print(f"Subscribe message first 4 bytes: {first_bytes.hex()}")
    print(f"Variant index: {variant_index}")
    
    # Verify it's not TAG_ENUM (0x13)
    assert binary_message[0] != 0x13, f"Message should not start with TAG_ENUM (0x13), got {binary_message[0]:02x}"
    
    # Verify it's variant index 1 for Subscribe
    assert variant_index == 1, f"Subscribe should be variant 1, got {variant_index}"
    
    print("✓ Subscribe encoding correct - no TAG_ENUM prefix")


def test_call_reducer_encoding():
    """Test that CallReducer messages don't start with TAG_ENUM (0x13)."""
    helper = SpacetimeDBProtocolHelper(use_binary=True)
    
    # Create a reducer call message
    args = {"player_name": "Alice"}
    binary_message = helper.encode_reducer_call("enter_game", args, request_id=456)
    
    # Check the first byte
    first_bytes = binary_message[:4]
    variant_index = struct.unpack('<I', first_bytes)[0]
    
    print(f"\nCallReducer message first 4 bytes: {first_bytes.hex()}")
    print(f"Variant index: {variant_index}")
    
    # Verify it's not TAG_ENUM (0x13)
    assert binary_message[0] != 0x13, f"Message should not start with TAG_ENUM (0x13), got {binary_message[0]:02x}"
    
    # Verify it's variant index 0 for CallReducer
    assert variant_index == 0, f"CallReducer should be variant 0, got {variant_index}"
    
    print("✓ CallReducer encoding correct - no TAG_ENUM prefix")


def test_one_off_query_encoding():
    """Test that OneOffQuery messages don't start with TAG_ENUM (0x13)."""
    helper = SpacetimeDBProtocolHelper(use_binary=True)
    
    # Create a one-off query message
    binary_message = helper.encode_one_off_query("SELECT * FROM entity WHERE id = 1")
    
    # Check the first byte
    first_bytes = binary_message[:4]
    variant_index = struct.unpack('<I', first_bytes)[0]
    
    print(f"\nOneOffQuery message first 4 bytes: {first_bytes.hex()}")
    print(f"Variant index: {variant_index}")
    
    # Verify it's not TAG_ENUM (0x13)
    assert binary_message[0] != 0x13, f"Message should not start with TAG_ENUM (0x13), got {binary_message[0]:02x}"
    
    # Verify it's variant index 6 for OneOffQuery
    assert variant_index == 6, f"OneOffQuery should be variant 6, got {variant_index}"
    
    print("✓ OneOffQuery encoding correct - no TAG_ENUM prefix")


def main():
    print("Testing SpaceTimeDB protocol tag 0x13 fix...")
    print("=" * 50)
    
    try:
        test_subscribe_encoding()
        test_call_reducer_encoding()
        test_one_off_query_encoding()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! The tag 0x13 issue has been fixed.")
        print("\nThe SDK now correctly encodes ClientMessage variants without")
        print("the TAG_ENUM prefix, which should resolve the server error:")
        print('"unknown tag 0x13 for sum type ClientMessage"')
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()