#!/usr/bin/env python3
"""
Test to verify that binary encoding methods return bytes, not strings.
This ensures WebSocket sends binary frames (opcode 0x2) instead of text frames (opcode 0x1).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper
from spacetimedb_sdk.protocol import ProtocolEncoder, Subscribe, CallReducer, CallReducerFlags
from spacetimedb_sdk.bsatn.writer import BsatnWriter


def test_bsatn_writer_returns_bytes():
    """Test that BsatnWriter.get_bytes() returns bytes."""
    writer = BsatnWriter()
    writer.write_string("test")
    result = writer.get_bytes()
    
    print(f"BsatnWriter.get_bytes() returns: {type(result)}")
    assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    print("✓ BsatnWriter.get_bytes() correctly returns bytes")


def test_protocol_encoder_returns_bytes():
    """Test that ProtocolEncoder returns bytes for binary protocol."""
    encoder = ProtocolEncoder(use_binary=True)
    
    # Test Subscribe message
    subscribe_msg = Subscribe(
        query_strings=["SELECT * FROM test"],
        request_id=1
    )
    
    result = encoder.encode_client_message(subscribe_msg)
    print(f"\nProtocolEncoder.encode_client_message(Subscribe) returns: {type(result)}")
    assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    print("✓ ProtocolEncoder correctly returns bytes for Subscribe")
    
    # Test CallReducer message
    call_reducer_msg = CallReducer(
        reducer="test_reducer",
        args=b'{"test": "value"}',
        request_id=2,
        flags=CallReducerFlags.FULL_UPDATE
    )
    
    result = encoder.encode_client_message(call_reducer_msg)
    print(f"\nProtocolEncoder.encode_client_message(CallReducer) returns: {type(result)}")
    assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    print("✓ ProtocolEncoder correctly returns bytes for CallReducer")


def test_protocol_helper_returns_bytes():
    """Test that SpacetimeDBProtocolHelper returns bytes."""
    helper = SpacetimeDBProtocolHelper(use_binary=True)
    
    # Test encode_subscription
    result = helper.encode_subscription(["test_table"])
    print(f"\nSpacetimeDBProtocolHelper.encode_subscription() returns: {type(result)}")
    assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    print("✓ encode_subscription() correctly returns bytes")
    
    # Test encode_reducer_call
    result = helper.encode_reducer_call("test_reducer", {"key": "value"})
    print(f"\nSpacetimeDBProtocolHelper.encode_reducer_call() returns: {type(result)}")
    assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    print("✓ encode_reducer_call() correctly returns bytes")
    
    # Test encode_single_subscription
    result = helper.encode_single_subscription("test_table")
    print(f"\nSpacetimeDBProtocolHelper.encode_single_subscription() returns: {type(result)}")
    assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    print("✓ encode_single_subscription() correctly returns bytes")


def test_no_string_conversion():
    """Test that there's no accidental string conversion in the encoding process."""
    encoder = ProtocolEncoder(use_binary=True)
    
    # Create a message with binary data
    call_reducer_msg = CallReducer(
        reducer="test",
        args=b'\x00\x01\x02\x03',  # Binary data that would fail if converted to string
        request_id=3,
        flags=CallReducerFlags.FULL_UPDATE
    )
    
    try:
        result = encoder.encode_client_message(call_reducer_msg)
        print(f"\nBinary data encoding successful, result type: {type(result)}")
        assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
        print("✓ No string conversion detected in binary encoding")
    except UnicodeDecodeError as e:
        print(f"✗ String conversion detected! Error: {e}")
        raise


def main():
    """Run all tests."""
    print("Testing SpacetimeDB Python SDK Binary Encoding Fix")
    print("=" * 50)
    
    try:
        test_bsatn_writer_returns_bytes()
        test_protocol_encoder_returns_bytes()
        test_protocol_helper_returns_bytes()
        test_no_string_conversion()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed! Binary encoding is working correctly.")
        print("\nThe SDK methods now return bytes for binary protocol,")
        print("which will cause WebSocket to send binary frames (opcode 0x2)")
        print("instead of text frames (opcode 0x1).")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()