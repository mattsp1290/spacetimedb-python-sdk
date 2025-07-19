#!/usr/bin/env python3
"""
Test to verify the regression fix - ensuring we use direct variant encoding
without TAG_ENUM for ClientMessage types.
"""

import sys
import os
import struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol import ProtocolEncoder, Subscribe
from spacetimedb_sdk.bsatn.constants import TAG_ENUM

def test_regression_fix():
    """Test that ClientMessage encoding uses direct variants, not TAG_ENUM."""
    print("=== REGRESSION FIX VERIFICATION ===")
    
    # Create a subscription message
    subscription = Subscribe(
        query_strings=["entity"],
        request_id=123
    )
    
    # Encode using current protocol encoder
    encoder = ProtocolEncoder(use_binary=True)
    encoded_bytes = encoder.encode_client_message(subscription)
    
    print(f"Encoded length: {len(encoded_bytes)} bytes")
    print(f"Encoded hex: {encoded_bytes.hex()}")
    
    # Verify it does NOT start with TAG_ENUM
    if len(encoded_bytes) >= 5:
        first_byte = encoded_bytes[0]
        if first_byte == TAG_ENUM:
            print(f"❌ REGRESSION NOT FIXED: Still starts with TAG_ENUM (0x{first_byte:02x})")
            print("   Server will reject with 'unknown tag 0x13' error")
            return False
        else:
            print(f"✅ REGRESSION FIXED: Starts with direct variant (0x{first_byte:02x})")
            
            # Verify it's the correct variant (Subscribe = 1)
            if len(encoded_bytes) >= 4:
                variant = int.from_bytes(encoded_bytes[:4], 'little')
                if variant == 1:
                    print(f"✅ Correct Subscribe variant: {variant}")
                else:
                    print(f"❌ Wrong variant: expected 1, got {variant}")
                    return False
    
    # Expected format: 01 00 00 00 (Subscribe variant) followed by struct data
    expected_start = b'\x01\x00\x00\x00\x12'  # variant 1 + TAG_STRUCT
    actual_start = encoded_bytes[:5]
    
    if actual_start == expected_start:
        print("✅ Encoding matches expected format")
        print(f"   Expected: {expected_start.hex()}")
        print(f"   Actual:   {actual_start.hex()}")
        return True
    else:
        print("❌ Encoding does NOT match expected format")
        print(f"   Expected: {expected_start.hex()}")
        print(f"   Actual:   {actual_start.hex()}")
        return False

def main():
    """Main test function."""
    try:
        if test_regression_fix():
            print("\n✅ SUCCESS: Regression fix is working correctly")
            print("✅ ClientMessage uses direct variant encoding")
            print("✅ Server should NOT see 'unknown tag 0x13' errors")
        else:
            print("\n❌ FAILURE: Regression fix is NOT working")
            print("❌ Need to continue debugging")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()