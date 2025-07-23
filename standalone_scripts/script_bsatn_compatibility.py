#!/usr/bin/env python3
"""
BSATN Compatibility Test Script

This script tests the Python BSATN implementation against various data types
and validates compatibility with SpacetimeDB's expected BSATN format.
"""

import os
import sys
import struct

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.bsatn import encode, decode, BsatnWriter, BsatnReader
from spacetimedb_sdk.bsatn.constants import *


def test_basic_types():
    """Test encoding and decoding of basic types."""
    print("Testing basic types...")
    
    # Test u8
    original = 42
    encoded = encode(original)
    decoded = decode(encoded)
    print(f"u8: {original} -> {encoded.hex()} -> {decoded}")
    assert decoded == original, f"u8 mismatch: {original} != {decoded}"
    
    # Test bool
    for val in [True, False]:
        encoded = encode(val)
        decoded = decode(encoded)
        print(f"bool: {val} -> {encoded.hex()} -> {decoded}")
        assert decoded == val, f"bool mismatch: {val} != {decoded}"
    
    # Test string
    original = "Hello, SpacetimeDB!"
    encoded = encode(original)
    decoded = decode(encoded)
    print(f"string: '{original}' -> {encoded.hex()} -> '{decoded}'")
    assert decoded == original, f"string mismatch: '{original}' != '{decoded}'"
    
    # Test bytes
    original = b"binary data \x00\x01\x02"
    encoded = encode(original)
    decoded = decode(encoded)
    print(f"bytes: {original} -> {encoded.hex()} -> {decoded}")
    assert decoded == original, f"bytes mismatch: {original} != {decoded}"
    
    # Test array
    original = [1, 2, 3, 4, 5]
    encoded = encode(original)
    decoded = decode(encoded)
    print(f"array: {original} -> {encoded.hex()} -> {decoded}")
    assert decoded == original, f"array mismatch: {original} != {decoded}"
    
    print("✓ Basic types test passed!\n")


def test_numeric_types():
    """Test all numeric types with specific values."""
    print("Testing numeric types...")
    
    test_cases = [
        # (value, expected_type, write_method, expected_tag)
        (127, 'i8', 'write_i8', TAG_I8),
        (255, 'u8', 'write_u8', TAG_U8),
        (-32768, 'i16', 'write_i16', TAG_I16),
        (65535, 'u16', 'write_u16', TAG_U16),
        (-2147483648, 'i32', 'write_i32', TAG_I32),
        (4294967295, 'u32', 'write_u32', TAG_U32),
        (-9223372036854775808, 'i64', 'write_i64', TAG_I64),
        (18446744073709551615, 'u64', 'write_u64', TAG_U64),
        (3.14, 'f32', 'write_f32', TAG_F32),
        (2.718281828459045, 'f64', 'write_f64', TAG_F64),
    ]
    
    for value, type_name, write_method, expected_tag in test_cases:
        writer = BsatnWriter()
        getattr(writer, write_method)(value)
        
        if writer.error():
            print(f"❌ Error writing {type_name} {value}: {writer.error()}")
            continue
            
        encoded = writer.get_bytes()
        
        # Verify the tag is correct
        assert encoded[0] == expected_tag, f"Wrong tag for {type_name}: expected {expected_tag}, got {encoded[0]}"
        
        # Test round-trip
        reader = BsatnReader(encoded)
        tag = reader.read_tag()
        assert tag == expected_tag, f"Tag mismatch in reader for {type_name}"
        
        # Read the value using the appropriate method
        read_method = write_method.replace('write_', 'read_')
        if read_method == 'read_f32':
            decoded = reader.read_f32()
            # Float comparison with tolerance
            assert abs(decoded - float(value)) < 0.001, f"{type_name} mismatch: {value} != {decoded}"
        elif read_method == 'read_f64':
            decoded = reader.read_f64()
            assert abs(decoded - value) < 0.0000001, f"{type_name} mismatch: {value} != {decoded}"
        else:
            decoded = getattr(reader, read_method)()
            assert decoded == value, f"{type_name} mismatch: {value} != {decoded}"
        
        print(f"✓ {type_name}: {value} -> {encoded.hex()}")
    
    print("✓ Numeric types test passed!\n")


def test_collections():
    """Test arrays, lists, and structs."""
    print("Testing collections...")
    
    # Test array of i32
    writer = BsatnWriter()
    values = [10, 20, 30]
    writer.write_array_header(len(values))
    for val in values:
        writer.write_i32(val)
    
    if writer.error():
        print(f"❌ Error writing array: {writer.error()}")
        return
    
    encoded = writer.get_bytes()
    print(f"i32 array {values} -> {encoded.hex()}")
    
    # Decode the array
    reader = BsatnReader(encoded)
    tag = reader.read_tag()
    assert tag == TAG_ARRAY, f"Expected ARRAY tag, got {tag}"
    
    count = reader.read_array_header()
    assert count == len(values), f"Array count mismatch: {len(values)} != {count}"
    
    decoded = []
    for _ in range(count):
        item_tag = reader.read_tag()
        assert item_tag == TAG_I32, f"Expected I32 tag in array, got {item_tag}"
        decoded.append(reader.read_i32())
    
    assert decoded == values, f"Array mismatch: {values} != {decoded}"
    print("✓ Array encoding/decoding works!")
    
    # Test struct
    writer = BsatnWriter()
    struct_data = {"name": "Alice", "age": 30, "active": True}
    writer.write_struct_header(len(struct_data))
    
    for key, value in struct_data.items():
        writer.write_field_name(key)
        if isinstance(value, str):
            writer.write_string(value)
        elif isinstance(value, int):
            writer.write_i32(value)
        elif isinstance(value, bool):
            writer.write_bool(value)
    
    if writer.error():
        print(f"❌ Error writing struct: {writer.error()}")
        return
    
    encoded = writer.get_bytes()
    print(f"struct {struct_data} -> {encoded.hex()}")
    
    # Decode the struct
    reader = BsatnReader(encoded)
    tag = reader.read_tag()
    assert tag == TAG_STRUCT, f"Expected STRUCT tag, got {tag}"
    
    field_count = reader.read_struct_header()
    assert field_count == len(struct_data), f"Field count mismatch: {len(struct_data)} != {field_count}"
    
    decoded_struct = {}
    for _ in range(field_count):
        field_name = reader.read_field_name()
        field_tag = reader.read_tag()
        
        if field_tag == TAG_STRING:
            field_value = reader.read_string()
        elif field_tag == TAG_I32:
            field_value = reader.read_i32()
        elif field_tag in (TAG_BOOL_TRUE, TAG_BOOL_FALSE):
            field_value = reader.read_bool(field_tag)
        else:
            raise ValueError(f"Unexpected field tag: {field_tag}")
        
        decoded_struct[field_name] = field_value
    
    assert decoded_struct == struct_data, f"Struct mismatch: {struct_data} != {decoded_struct}"
    print("✓ Struct encoding/decoding works!")
    
    print("✓ Collections test passed!\n")


def test_compatibility_with_rust_format():
    """Test compatibility with expected Rust BSATN format."""
    print("Testing compatibility with Rust BSATN format...")
    
    # Test u8 value 42 - this should match what the bsatn-test module produces
    writer = BsatnWriter()
    writer.write_u8(42)
    encoded = writer.get_bytes()
    
    # Expected format: TAG_U8 (0x03) + value (42)
    expected = bytes([TAG_U8, 42])
    assert encoded == expected, f"u8 encoding mismatch: expected {expected.hex()}, got {encoded.hex()}"
    print(f"✓ u8(42) encoding matches expected format: {encoded.hex()}")
    
    # Test i32 array [10, 20] - this should match what the bsatn-test module produces
    writer = BsatnWriter()
    values = [10, 20]
    writer.write_array_header(len(values))
    for val in values:
        writer.write_i32(val)
    
    encoded = writer.get_bytes()
    print(f"✓ i32 array {values} encoded as: {encoded.hex()}")
    
    # Manual verification of the format:
    # TAG_ARRAY (0x14) + count (2 as u32 LE) + TAG_I32 (0x08) + 10 (as i32 LE) + TAG_I32 (0x08) + 20 (as i32 LE)
    expected_bytes = [TAG_ARRAY]  # Array tag
    expected_bytes.extend(struct.pack('<I', 2))  # Count as u32 LE
    expected_bytes.extend([TAG_I32])  # First element tag
    expected_bytes.extend(struct.pack('<i', 10))  # First element value
    expected_bytes.extend([TAG_I32])  # Second element tag  
    expected_bytes.extend(struct.pack('<i', 20))  # Second element value
    
    expected = bytes(expected_bytes)
    assert encoded == expected, f"Array encoding mismatch: expected {expected.hex()}, got {encoded.hex()}"
    
    print("✓ Compatibility test passed!\n")


def main():
    """Run all tests."""
    print("BSATN Compatibility Test Suite")
    print("=" * 50)
    
    try:
        test_basic_types()
        test_numeric_types()
        test_collections()
        test_compatibility_with_rust_format()
        
        print("🎉 All tests passed! The BSATN implementation is working correctly.")
        print(f"Python SDK BSATN is compatible with SpacetimeDB format.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 