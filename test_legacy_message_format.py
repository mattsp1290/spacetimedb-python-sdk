#!/usr/bin/env python3
"""
Test legacy message format handling in the SpacetimeDB SDK.

This test verifies that the SDK can properly decode messages in the legacy
format used by some SpacetimeDB servers, particularly the __identity__ format.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol import ProtocolDecoder, Identity, ConnectionId, IdentityToken
from spacetimedb_sdk.websocket_client import WebSocketClient


def test_legacy_identity_format():
    """Test that legacy __identity__ format is properly decoded."""
    print("Testing legacy identity message format...")
    
    # Create a decoder
    decoder = ProtocolDecoder(use_binary=False)
    
    # Test case 1: Legacy format with hex string identity
    legacy_message = {
        "__identity__": "0xdeadbeef",
        "__token__": "test-token-123",
        "__connection_id__": 123456789
    }
    
    message_bytes = json.dumps(legacy_message).encode('utf-8')
    decoded = decoder.decode_server_message(message_bytes)
    
    assert isinstance(decoded, IdentityToken), f"Expected IdentityToken, got {type(decoded)}"
    assert decoded.identity.to_hex() == "deadbeef", f"Expected identity 'deadbeef', got '{decoded.identity.to_hex()}'"
    assert decoded.token == "test-token-123", f"Expected token 'test-token-123', got '{decoded.token}'"
    
    print("✓ Legacy hex identity format decoded correctly")
    
    # Test case 2: Legacy format with connection_id as hex string
    legacy_message2 = {
        "__identity__": "0xabcdef123456",
        "__token__": "another-token",
        "__connection_id__": "0x1234567890abcdef"
    }
    
    message_bytes2 = json.dumps(legacy_message2).encode('utf-8')
    decoded2 = decoder.decode_server_message(message_bytes2)
    
    assert isinstance(decoded2, IdentityToken), f"Expected IdentityToken, got {type(decoded2)}"
    assert decoded2.identity.to_hex() == "abcdef123456", f"Expected identity 'abcdef123456', got '{decoded2.identity.to_hex()}'"
    assert decoded2.connection_id.to_hex().endswith("1234567890abcdef"), "Connection ID hex mismatch"
    
    print("✓ Legacy hex connection_id format decoded correctly")
    
    # Test case 3: Standard format still works
    standard_message = {
        "IdentityToken": {
            "identity": "0xfeedface",
            "token": "standard-token",
            "connection_id": "0xdeadbeefcafe"
        }
    }
    
    message_bytes3 = json.dumps(standard_message).encode('utf-8')
    decoded3 = decoder.decode_server_message(message_bytes3)
    
    assert isinstance(decoded3, IdentityToken), f"Expected IdentityToken, got {type(decoded3)}"
    assert decoded3.identity.to_hex() == "feedface", f"Expected identity 'feedface', got '{decoded3.identity.to_hex()}'"
    
    print("✓ Standard format still works correctly")
    
    print("\n✅ All legacy format tests passed!")


def test_legacy_message_in_websocket():
    """Test that legacy messages work in the WebSocket client context."""
    print("\nTesting legacy message handling in WebSocket client...")
    
    # Create a mock message handler to capture decoded messages
    received_messages = []
    
    def on_message(msg):
        received_messages.append(msg)
    
    # Create WebSocket client
    client = WebSocketClient(
        protocol="v1.json.spacetimedb",
        on_message=on_message
    )
    
    # Simulate receiving a legacy format message
    # This would normally come from the WebSocket, but we'll test the decoder directly
    decoder = client.decoder
    
    legacy_ws_message = json.dumps({
        "__identity__": "0x1234567890abcdef",
        "__token__": "ws-test-token",
        "__connection_id__": 9876543210
    })
    
    try:
        decoded = decoder.decode_server_message(legacy_ws_message.encode('utf-8'))
        print(f"✓ WebSocket decoder handled legacy format: {type(decoded).__name__}")
        assert isinstance(decoded, IdentityToken)
        assert decoded.identity.to_hex() == "1234567890abcdef"
    except Exception as e:
        print(f"✗ WebSocket decoder failed on legacy format: {e}")
        raise
    
    print("\n✅ WebSocket legacy format test passed!")


def test_error_on_partial_legacy_support():
    """Test that we get helpful errors for partially supported legacy formats."""
    print("\nTesting error messages for unsupported legacy formats...")
    
    decoder = ProtocolDecoder(use_binary=False)
    
    # Test unsupported legacy format
    unsupported_message = {
        "__subscribe_applied__": {
            "__request_id__": 123,
            "__table_name__": "users"
        }
    }
    
    try:
        message_bytes = json.dumps(unsupported_message).encode('utf-8')
        decoder.decode_server_message(message_bytes)
        print("✗ Should have raised an error for unsupported legacy format")
        assert False
    except ValueError as e:
        assert "Partially supported legacy message format" in str(e)
        print(f"✓ Got expected error: {e}")
    
    print("\n✅ Error handling test passed!")


if __name__ == "__main__":
    test_legacy_identity_format()
    test_legacy_message_in_websocket()
    test_error_on_partial_legacy_support()
    
    print("\n🎉 All legacy format tests completed successfully!")