#!/usr/bin/env python3
"""
Simple BSATN Test Script

This script tests the Python BSATN implementation directly without importing the full SDK.
"""

import os
import sys
import struct

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import BSATN modules directly
from spacetimedb_sdk.bsatn.writer import BsatnWriter
from spacetimedb_sdk.bsatn.reader import BsatnReader
from spacetimedb_sdk.bsatn.constants import *
from spacetimedb_sdk.bsatn.utils import encode, decode


def test_basic_encoding():
    """Test basic BSATN encoding functionality."""
    print("Testing basic BSATN encoding...")
    
    # Test u8
    writer = BsatnWriter()
    writer.write_u8(42)
    if writer.error():
        print(f"❌ Error writing u8: {writer.error()}")
        return False
    
    encoded = writer.get_bytes()
    expected = bytes([TAG_U8, 42])
    if encoded == expected:
        print(f"✓ u8(42) encoded correctly: {encoded.hex()}")
    else:
        print(f"❌ u8(42) encoding failed: expected {expected.hex()}, got {encoded.hex()}")
        return False
    
    # Test decoding
    reader = BsatnReader(encoded)
    tag = reader.read_tag()
    if tag != TAG_U8:
        print(f"❌ Wrong tag read: expected {TAG_U8}, got {tag}")
        return False
    
    value = reader.read_u8()
    if value == 42:
        print(f"✓ u8(42) decoded correctly: {value}")
    else:
        print(f"❌ u8(42) decoding failed: expected 42, got {value}")
        return False
    
    return True


def test_array_encoding():
    """Test array encoding that matches the bsatn-test module."""
    print("Testing array encoding...")
    
    # Test i32 array [10, 20] to match echo_vec2 from bsatn-test
    writer = BsatnWriter()
    values = [10, 20]
    writer.write_array_header(len(values))
    for val in values:
        writer.write_i32(val)
    
    if writer.error():
        print(f"❌ Error writing array: {writer.error()}")
        return False
    
    encoded = writer.get_bytes()
    print(f"✓ i32 array {values} encoded as: {encoded.hex()}")
    
    # Verify the format manually
    # TAG_ARRAY (0x14) + count (2 as u32 LE) + TAG_I32 (0x08) + 10 (as i32 LE) + TAG_I32 (0x08) + 20 (as i32 LE)
    expected_bytes = [TAG_ARRAY]  # Array tag
    expected_bytes.extend(struct.pack('<I', 2))  # Count as u32 LE
    expected_bytes.extend([TAG_I32])  # First element tag
    expected_bytes.extend(struct.pack('<i', 10))  # First element value
    expected_bytes.extend([TAG_I32])  # Second element tag  
    expected_bytes.extend(struct.pack('<i', 20))  # Second element value
    
    expected = bytes(expected_bytes)
    if encoded == expected:
        print(f"✓ Array encoding matches expected format")
    else:
        print(f"❌ Array encoding mismatch:")
        print(f"   Expected: {expected.hex()}")
        print(f"   Got:      {encoded.hex()}")
        return False
    
    # Test decoding
    reader = BsatnReader(encoded)
    tag = reader.read_tag()
    if tag != TAG_ARRAY:
        print(f"❌ Wrong array tag: expected {TAG_ARRAY}, got {tag}")
        return False
    
    count = reader.read_array_header()
    if count != 2:
        print(f"❌ Wrong array count: expected 2, got {count}")
        return False
    
    decoded_values = []
    for i in range(count):
        item_tag = reader.read_tag()
        if item_tag != TAG_I32:
            print(f"❌ Wrong item tag at index {i}: expected {TAG_I32}, got {item_tag}")
            return False
        decoded_values.append(reader.read_i32())
    
    if decoded_values == values:
        print(f"✓ Array decoded correctly: {decoded_values}")
    else:
        print(f"❌ Array decoding failed: expected {values}, got {decoded_values}")
        return False
    
    return True


def test_high_level_api():
    """Test the high-level encode/decode API."""
    print("Testing high-level API...")
    
    # Test various types
    test_values = [
        42,
        True,
        False,
        "Hello, World!",
        b"binary data",
        [1, 2, 3],
        {"name": "test", "value": 123}
    ]
    
    for original in test_values:
        try:
            encoded = encode(original)
            decoded = decode(encoded)
            
            if decoded == original:
                print(f"✓ {type(original).__name__}: {original} -> {encoded.hex()[:20]}... -> {decoded}")
            else:
                print(f"❌ Round-trip failed for {type(original).__name__}: {original} != {decoded}")
                return False
        except Exception as e:
            print(f"❌ Error with {type(original).__name__} {original}: {e}")
            return False
    
    return True


def main():
    """Run all tests."""
    print("BSATN Simple Test Suite")
    print("=" * 40)
    
    tests = [
        test_basic_encoding,
        test_array_encoding,
        test_high_level_api
    ]
    
    all_passed = True
    for test in tests:
        try:
            if not test():
                all_passed = False
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
            print()
    
    if all_passed:
        print("🎉 All tests passed! The BSATN implementation is working correctly.")
        print("The Python SDK BSATN implementation should be compatible with SpacetimeDB.")
    else:
        print("❌ Some tests failed. Please check the implementation.")
        sys.exit(1)


if __name__ == "__main__":
    main() 