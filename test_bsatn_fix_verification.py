#!/usr/bin/env python3
"""
Test script to verify the BSATN encoding fix for SpacetimeDB Python SDK.

This test compares the before/after encoding to ensure we're now using proper
BSATN enum format instead of raw variant indices.
"""

import sys
import os
import struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol import ProtocolEncoder, Subscribe
from spacetimedb_sdk.bsatn.writer import BsatnWriter
from spacetimedb_sdk.bsatn.constants import TAG_ENUM

def test_before_after_fix():
    """Test the encoding before and after the fix."""
    print("=== BSATN ENCODING FIX VERIFICATION ===")
    
    # Create a subscription message
    subscription = Subscribe(
        query_strings=["entity"],
        request_id=123
    )
    
    # Test the current (fixed) encoding
    encoder = ProtocolEncoder(use_binary=True)
    fixed_bytes = encoder.encode_client_message(subscription)
    
    print(f"Fixed encoding length: {len(fixed_bytes)} bytes")
    print(f"Fixed encoding hex: {fixed_bytes.hex()}")
    
    # Analyze the fixed encoding
    if len(fixed_bytes) >= 5:
        first_byte = fixed_bytes[0]
        if first_byte == TAG_ENUM:
            print("✅ Fixed encoding starts with TAG_ENUM (0x13)")
            variant = int.from_bytes(fixed_bytes[1:5], 'little')
            print(f"✅ Enum variant: {variant} (should be 1 for Subscribe)")
        else:
            print(f"❌ Fixed encoding does NOT start with TAG_ENUM, starts with: 0x{first_byte:02x}")
    
    # Create the old (broken) encoding for comparison
    old_writer = BsatnWriter()
    old_writer._write_bytes(struct.pack('<I', 1))  # Raw variant without TAG_ENUM
    old_writer.write_struct_header(2)
    old_writer.write_field_name("query_strings")
    old_writer.write_array_header(1)
    old_writer.write_string("entity")
    old_writer.write_field_name("request_id")
    old_writer.write_u32(123)
    old_bytes = old_writer.get_bytes()
    
    print(f"\nOld (broken) encoding length: {len(old_bytes)} bytes")
    print(f"Old (broken) encoding hex: {old_bytes.hex()}")
    
    # Compare the encodings
    print(f"\n=== COMPARISON ===")
    print(f"Fixed:  {fixed_bytes.hex()}")
    print(f"Broken: {old_bytes.hex()}")
    
    if fixed_bytes != old_bytes:
        print("\n✅ ENCODINGS ARE DIFFERENT - Fix is working!")
        
        # Find the first difference
        min_len = min(len(fixed_bytes), len(old_bytes))
        for i in range(min_len):
            if fixed_bytes[i] != old_bytes[i]:
                print(f"First difference at byte {i}: fixed=0x{fixed_bytes[i]:02x}, broken=0x{old_bytes[i]:02x}")
                break
                
        # Check that fixed version starts with proper enum encoding
        if len(fixed_bytes) >= 5:
            if fixed_bytes[0] == TAG_ENUM:
                print("✅ Fixed encoding uses proper BSATN enum format")
            else:
                print("❌ Fixed encoding still doesn't use proper BSATN enum format")
    else:
        print("\n❌ ENCODINGS ARE IDENTICAL - Fix didn't work!")
    
    return fixed_bytes, old_bytes

def test_server_compatibility_format():
    """Test that the encoding matches what SpacetimeDB server expects."""
    print("\n=== SERVER COMPATIBILITY FORMAT TEST ===")
    
    subscription = Subscribe(
        query_strings=["entity"],
        request_id=123
    )
    
    encoder = ProtocolEncoder(use_binary=True)
    encoded = encoder.encode_client_message(subscription)
    
    print(f"Full message hex: {encoded.hex()}")
    
    # Expected format:
    # 13 - TAG_ENUM
    # 01 00 00 00 - Subscribe variant (1) as u32 little-endian
    # 12 - TAG_STRUCT  
    # 02 00 00 00 - Field count (2) as u32 little-endian
    # ... rest of struct data
    
    expected_start = bytes([
        TAG_ENUM,  # 0x13
        0x01, 0x00, 0x00, 0x00,  # variant 1 (Subscribe)
        0x12,  # TAG_STRUCT
        0x02, 0x00, 0x00, 0x00   # 2 fields
    ])
    
    if encoded.startswith(expected_start):
        print("✅ Encoding matches expected server format")
        print(f"Expected start: {expected_start.hex()}")
        print(f"Actual start:   {encoded[:len(expected_start)].hex()}")
    else:
        print("❌ Encoding does NOT match expected server format")
        print(f"Expected start: {expected_start.hex()}")
        actual_start = encoded[:len(expected_start)] if len(encoded) >= len(expected_start) else encoded
        print(f"Actual start:   {actual_start.hex()}")
        
        # Show where they differ
        for i in range(min(len(expected_start), len(encoded))):
            if encoded[i] != expected_start[i]:
                print(f"First difference at byte {i}: expected=0x{expected_start[i]:02x}, actual=0x{encoded[i]:02x}")
                break

def main():
    """Main test function."""
    try:
        fixed_bytes, old_bytes = test_before_after_fix()
        test_server_compatibility_format()
        
        print("\n=== SUMMARY ===")
        if fixed_bytes[0] == TAG_ENUM:
            print("✅ BSATN encoding fix is working correctly")
            print("✅ Messages now use proper BSATN enum format")
            print("✅ Server should be able to parse the messages")
        else:
            print("❌ BSATN encoding fix is NOT working")
            print("❌ Messages still use incorrect format")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()