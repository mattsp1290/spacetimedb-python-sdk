#!/usr/bin/env python3
"""
Test script to identify and fix BSATN encoding issues in SpacetimeDB Python SDK.

Based on issue report: SPACETIMEDB_SDK_BSATN_ENCODING_FIX_REQUEST.md
"""

import sys
import os
import struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol import ProtocolEncoder, Subscribe
from spacetimedb_sdk.bsatn.writer import BsatnWriter

def test_current_subscription_encoding():
    """Test current subscription message encoding to identify the problem."""
    print("=== CURRENT SUBSCRIPTION ENCODING TEST ===")
    
    # Create a subscription message
    subscription = Subscribe(
        query_strings=["entity"],
        request_id=123
    )
    
    # Encode using current protocol encoder
    encoder = ProtocolEncoder(use_binary=True)
    current_bytes = encoder.encode_client_message(subscription)
    
    print(f"Current encoding length: {len(current_bytes)} bytes")
    print(f"Current encoding hex: {current_bytes.hex()}")
    
    # Expected format according to the issue report:
    # 01 00 00 00 - Subscribe variant (4 bytes u32 little-endian) ✅
    # Then BSATN struct with query_strings and request_id
    
    # Let's analyze what we actually get:
    if len(current_bytes) >= 4:
        variant = int.from_bytes(current_bytes[:4], 'little')
        print(f"Message variant: {variant} (should be 1 for Subscribe)")
        
        remaining = current_bytes[4:]
        print(f"Remaining bytes: {remaining.hex()}")
        print(f"First few bytes: {remaining[:10].hex() if len(remaining) >= 10 else remaining.hex()}")
        
        # Analyze byte by byte
        print("\nDetailed analysis:")
        print(f"Bytes 0-3: {current_bytes[:4].hex()} = {variant} (Subscribe variant)")
        print(f"Byte 4: {current_bytes[4]:02x} = {current_bytes[4]} (should be 0x12 for TAG_STRUCT)")
        if len(current_bytes) > 8:
            struct_fields = int.from_bytes(current_bytes[5:9], 'little')
            print(f"Bytes 5-8: {current_bytes[5:9].hex()} = {struct_fields} (struct field count)")
    
    return current_bytes

def test_correct_bsatn_encoding():
    """Test what the BSATN encoding should look like."""
    print("\n=== CORRECT BSATN ENCODING TEST ===")
    
    writer = BsatnWriter()
    
    # Encode Subscribe variant (1)
    writer._write_bytes(struct.pack('<I', 1))
    
    # Encode struct with 2 fields (query_strings, request_id)
    writer.write_struct_header(2)
    
    # Field 1: query_strings
    writer.write_field_name("query_strings")
    writer.write_array_header(1)  # 1 query string
    writer.write_string("entity")
    
    # Field 2: request_id
    writer.write_field_name("request_id")
    writer.write_u32(123)
    
    correct_bytes = writer.get_bytes()
    
    print(f"Correct encoding length: {len(correct_bytes)} bytes")
    print(f"Correct encoding hex: {correct_bytes.hex()}")
    
    if writer.error():
        print(f"Writer error: {writer.error()}")
    
    return correct_bytes

def test_string_encoding():
    """Test individual string encoding to isolate the problem."""
    print("\n=== STRING ENCODING TEST ===")
    
    writer = BsatnWriter()
    writer.write_string("entity")
    string_bytes = writer.get_bytes()
    
    print(f"String 'entity' encoding: {string_bytes.hex()}")
    print(f"Length: {len(string_bytes)} bytes")
    
    # Should be:
    # 0D - TAG_STRING
    # 06 00 00 00 - length (6 bytes, u32 little-endian)
    # 65 6E 74 69 74 79 - "entity" bytes
    
    if len(string_bytes) >= 5:
        tag = string_bytes[0]
        length = int.from_bytes(string_bytes[1:5], 'little')
        data = string_bytes[5:]
        print(f"Tag: 0x{tag:02x} (should be 0x0D)")
        print(f"Length: {length} (should be 6)")
        print(f"Data: {data.hex()} (should be 'entity')")
        print(f"Data as string: {data.decode('utf-8') if len(data) > 0 else 'empty'}")

def test_array_encoding():
    """Test array encoding."""
    print("\n=== ARRAY ENCODING TEST ===")
    
    writer = BsatnWriter()
    writer.write_array_header(1)
    writer.write_string("entity")
    array_bytes = writer.get_bytes()
    
    print(f"Array encoding: {array_bytes.hex()}")
    print(f"Length: {len(array_bytes)} bytes")

def main():
    """Main test function."""
    try:
        print("SpacetimeDB Python SDK - BSATN Encoding Fix Test")
        print("=" * 50)
        
        # Import struct for the fix
        import struct
        
        current_bytes = test_current_subscription_encoding()
        test_string_encoding()
        test_array_encoding()
        correct_bytes = test_correct_bsatn_encoding()
        
        print("\n=== COMPARISON ===")
        print(f"Current:  {current_bytes.hex()}")
        print(f"Correct:  {correct_bytes.hex()}")
        
        if current_bytes != correct_bytes:
            print("\n❌ ENCODING MISMATCH FOUND!")
            print("The current protocol encoder is NOT using proper BSATN format.")
            
            # Find where they diverge
            min_len = min(len(current_bytes), len(correct_bytes))
            for i in range(min_len):
                if current_bytes[i] != correct_bytes[i]:
                    print(f"First difference at byte {i}: current=0x{current_bytes[i]:02x}, correct=0x{correct_bytes[i]:02x}")
                    break
        else:
            print("\n✅ Encodings match!")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()