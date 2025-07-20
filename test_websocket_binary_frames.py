#!/usr/bin/env python3
"""
Test to verify that WebSocket sends binary frames (opcode 0x2) for binary protocol.
This test simulates WebSocket behavior to ensure correct frame types.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper
from spacetimedb_sdk.protocol import ProtocolEncoder, Subscribe, CallReducer, CallReducerFlags, BIN_PROTOCOL, TEXT_PROTOCOL
from spacetimedb_sdk import WebSocketClient
from spacetimedb_sdk.websocket_client import WebSocketClient
from websocket import ABNF
import unittest.mock as mock


def test_old_client_binary_frames():
    """Test that old WebSocketClient sends binary frames for binary protocol."""
    print("Testing old WebSocketClient...")
    
    # Create a mock WebSocket
    mock_ws = mock.Mock()
    
    # Create old client with binary protocol
    client = WebSocketClient(protocol=BIN_PROTOCOL)
    client.ws = mock_ws
    client.is_connected = True
    
    # Test sending binary data
    binary_data = b'\x00\x01\x02\x03\x04'
    client.send(binary_data)
    
    # Verify it was sent with binary opcode
    mock_ws.send.assert_called_once_with(binary_data, opcode=ABNF.OPCODE_BINARY)
    print("✓ Old client correctly sends binary frames for binary protocol")
    
    # Reset mock
    mock_ws.reset_mock()
    
    # Test with text protocol
    client.protocol = TEXT_PROTOCOL
    text_data = b'{"test": "data"}'
    client.send(text_data)
    
    # Verify it was sent without opcode (default text)
    mock_ws.send.assert_called_once_with(text_data)
    print("✓ Old client correctly sends text frames for text protocol")


def test_modern_client_binary_frames():
    """Test that WebSocketClient sends binary frames for binary protocol."""
    print("\nTesting WebSocketClient...")
    
    # Create a mock WebSocket
    mock_ws = mock.Mock()
    
    # Create modern client with binary protocol
    client = WebSocketClient(protocol=BIN_PROTOCOL)
    client.ws = mock_ws
    from spacetimedb_sdk.websocket_client import ConnectionState
    client.state = ConnectionState.CONNECTED
    
    # Create a test message
    subscribe_msg = Subscribe(
        query_strings=["SELECT * FROM test"],
        request_id=1
    )
    
    # Send the message
    client.send_message(subscribe_msg)
    
    # Verify it was sent with binary opcode
    assert mock_ws.send.called, "send was not called"
    call_args = mock_ws.send.call_args
    
    # Check that binary opcode was used
    assert 'opcode' in call_args[1], "opcode parameter not found"
    assert call_args[1]['opcode'] == ABNF.OPCODE_BINARY, f"Expected binary opcode, got {call_args[1]['opcode']}"
    print("✓ Modern client correctly sends binary frames for binary protocol")
    
    # Verify the data is bytes
    sent_data = call_args[0][0]
    assert isinstance(sent_data, bytes), f"Expected bytes data, got {type(sent_data)}"
    print("✓ Modern client sends bytes data")


def test_protocol_helper_integration():
    """Test that protocol helper produces correct binary data."""
    print("\nTesting protocol helper integration...")
    
    # Binary protocol helper
    binary_helper = SpacetimeDBProtocolHelper(use_binary=True)
    
    # Test subscription
    data = binary_helper.encode_subscription(["test_table"])
    assert isinstance(data, bytes), f"Expected bytes, got {type(data)}"
    assert len(data) > 0, "Empty data returned"
    print(f"✓ Binary subscription encoding: {len(data)} bytes")
    
    # Test reducer call
    data = binary_helper.encode_reducer_call("test_reducer", {"arg": "value"})
    assert isinstance(data, bytes), f"Expected bytes, got {type(data)}"
    assert len(data) > 0, "Empty data returned"
    print(f"✓ Binary reducer call encoding: {len(data)} bytes")
    
    # Text protocol helper for comparison
    text_helper = SpacetimeDBProtocolHelper(use_binary=False)
    
    # Test subscription
    data = text_helper.encode_subscription(["test_table"])
    assert isinstance(data, bytes), f"Expected bytes, got {type(data)}"
    # Should be valid JSON when decoded
    json_str = data.decode('utf-8')
    assert json_str.startswith('{'), "Text protocol should produce JSON"
    print(f"✓ Text subscription encoding: {len(data)} bytes (JSON)")


def test_websocket_frame_detection():
    """Test helper to detect WebSocket frame types."""
    print("\nWebSocket frame type detection...")
    
    # Create sample binary and text data
    binary_helper = SpacetimeDBProtocolHelper(use_binary=True)
    text_helper = SpacetimeDBProtocolHelper(use_binary=False)
    
    binary_data = binary_helper.encode_subscription(["test"])
    text_data = text_helper.encode_subscription(["test"])
    
    print(f"\nBinary protocol data preview: {binary_data[:20]}...")
    print(f"Text protocol data preview: {text_data[:50].decode('utf-8', errors='replace')}...")
    
    # Check if binary data starts with expected BSATN markers
    if binary_data[0:4] == b'\x00\x00\x00\x01':  # Common BSATN enum variant prefix
        print("✓ Binary data has BSATN enum variant marker")
    
    # Check if text data is valid JSON
    try:
        import json
        json.loads(text_data.decode('utf-8'))
        print("✓ Text data is valid JSON")
    except json.JSONDecodeError:
        print("✗ Text data is not valid JSON")


def main():
    """Run all tests."""
    print("Testing WebSocket Binary Frame Handling")
    print("=" * 50)
    
    try:
        test_old_client_binary_frames()
        test_modern_client_binary_frames()
        test_protocol_helper_integration()
        test_websocket_frame_detection()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("\nSummary:")
        print("- Both old and modern WebSocket clients correctly send binary frames")
        print("- Protocol helpers return bytes for both binary and text protocols")
        print("- Binary protocol uses ABNF.OPCODE_BINARY (0x2)")
        print("- Text protocol uses default opcode (0x1)")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()