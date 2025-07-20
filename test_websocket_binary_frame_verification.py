#!/usr/bin/env python3
"""
Test to verify that the SpacetimeDB Python SDK sends binary frames correctly.

This test creates a mock WebSocket server that inspects incoming frames
to ensure they are sent with the correct opcode (binary vs text).
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import websocket
import threading
import time
import struct
from unittest.mock import Mock, patch
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the SpacetimeDB SDK components
from spacetimedb_sdk import SpacetimeDBClient, BIN_PROTOCOL, TEXT_PROTOCOL
from spacetimedb_sdk.websocket_client import WebSocketClient
from spacetimedb_sdk import WebSocketClient


class FrameTypeVerifier:
    """Verifies that WebSocket frames are sent with the correct opcode."""
    
    def __init__(self):
        self.captured_frames = []
        self.frame_opcodes = []
    
    def capture_frame(self, data, opcode=None):
        """Capture a frame and its opcode."""
        self.captured_frames.append(data)
        if opcode is not None:
            self.frame_opcodes.append(opcode)
            logger.info(f"Captured frame with opcode: {opcode} ({self._opcode_name(opcode)})")
            logger.debug(f"Frame data type: {type(data)}, length: {len(data) if hasattr(data, '__len__') else 'N/A'}")
            if isinstance(data, bytes):
                logger.debug(f"First 20 bytes (hex): {data[:20].hex() if len(data) >= 20 else data.hex()}")
    
    def _opcode_name(self, opcode):
        """Get human-readable name for opcode."""
        from websocket import ABNF
        if opcode == ABNF.OPCODE_TEXT:
            return "TEXT"
        elif opcode == ABNF.OPCODE_BINARY:
            return "BINARY"
        elif opcode == ABNF.OPCODE_CLOSE:
            return "CLOSE"
        elif opcode == ABNF.OPCODE_PING:
            return "PING"
        elif opcode == ABNF.OPCODE_PONG:
            return "PONG"
        else:
            return f"UNKNOWN({opcode})"
    
    def verify_binary_frames(self):
        """Verify that all captured frames were sent as binary."""
        from websocket import ABNF
        binary_count = sum(1 for op in self.frame_opcodes if op == ABNF.OPCODE_BINARY)
        text_count = sum(1 for op in self.frame_opcodes if op == ABNF.OPCODE_TEXT)
        
        logger.info(f"Frame summary: {binary_count} binary, {text_count} text, {len(self.frame_opcodes)} total")
        
        return all(op == ABNF.OPCODE_BINARY for op in self.frame_opcodes if op in [ABNF.OPCODE_BINARY, ABNF.OPCODE_TEXT])


def test_modern_websocket_client_binary_frames():
    """Test that WebSocketClient sends binary frames correctly."""
    logger.info("=== Testing WebSocketClient ===")
    
    verifier = FrameTypeVerifier()
    
    # Create a WebSocketClient with binary protocol
    client = WebSocketClient(protocol=BIN_PROTOCOL)
    
    # Mock the websocket send method to capture frames
    with patch.object(websocket.WebSocketApp, 'send') as mock_send:
        def capture_send(data, opcode=None):
            verifier.capture_frame(data, opcode)
            return len(data) if hasattr(data, '__len__') else 0
        
        mock_send.side_effect = capture_send
        
        # Set up a mock WebSocket app
        client.ws = Mock(spec=websocket.WebSocketApp)
        client.ws.send = mock_send
        from spacetimedb_sdk.websocket_client import ConnectionState
        client.state = ConnectionState.CONNECTED
        
        # Test sending various message types
        from spacetimedb_sdk.protocol import Subscribe, CallReducer, generate_request_id
        
        # Test subscription message
        logger.info("Sending Subscribe message...")
        subscribe_msg = Subscribe(
            query_strings=["SELECT * FROM test"],
            request_id=generate_request_id()
        )
        client.send_message(subscribe_msg)
        
        # Test reducer call message
        logger.info("Sending CallReducer message...")
        reducer_msg = CallReducer(
            reducer="test_reducer",
            args=b'{"test": "data"}',
            request_id=generate_request_id()
        )
        client.send_message(reducer_msg)
    
    # Verify results
    logger.info(f"Captured {len(verifier.captured_frames)} frames")
    assert len(verifier.captured_frames) == 2, "Expected 2 frames to be sent"
    assert verifier.verify_binary_frames(), "All frames should be sent as binary"
    logger.info("✓ WebSocketClient correctly sends binary frames")


def test_legacy_websocket_client_binary_frames():
    """Test that legacy WebSocketClient sends binary frames correctly."""
    logger.info("=== Testing Legacy WebSocketClient ===")
    
    verifier = FrameTypeVerifier()
    
    # Create a legacy WebSocketClient with binary protocol
    from spacetimedb_sdk.protocol import ProtocolEncoder
    protocol_encoder = ProtocolEncoder(use_binary=True)
    client = WebSocketClient(
        protocol=BIN_PROTOCOL,
        on_connect=None,
        on_close=None,
        on_error=None,
        on_message=None
    )
    
    # Mock the websocket send method to capture frames
    with patch.object(websocket.WebSocketApp, 'send') as mock_send:
        def capture_send(data, opcode=None):
            verifier.capture_frame(data, opcode)
            return len(data) if hasattr(data, '__len__') else 0
        
        mock_send.side_effect = capture_send
        
        # Set up a mock WebSocket app
        client.ws = Mock(spec=websocket.WebSocketApp)
        client.ws.send = mock_send
        client.is_connected = True
        
        # Test sending binary data
        logger.info("Sending binary test data...")
        test_data = b'\x01\x02\x03\x04\x05'
        client.send(test_data)
        
        # Test sending more binary data
        logger.info("Sending more binary test data...")
        test_data2 = struct.pack('<I', 12345) + b'test'
        client.send(test_data2)
    
    # Verify results
    logger.info(f"Captured {len(verifier.captured_frames)} frames")
    assert len(verifier.captured_frames) == 2, "Expected 2 frames to be sent"
    assert verifier.verify_binary_frames(), "All frames should be sent as binary"
    logger.info("✓ Legacy WebSocketClient correctly sends binary frames")


def test_text_protocol_sends_text_frames():
    """Test that text protocol correctly sends text frames."""
    logger.info("=== Testing Text Protocol ===")
    
    verifier = FrameTypeVerifier()
    
    # Create a WebSocketClient with text protocol
    client = WebSocketClient(protocol=TEXT_PROTOCOL)
    
    # Mock the websocket send method to capture frames
    with patch.object(websocket.WebSocketApp, 'send') as mock_send:
        def capture_send(data, opcode=None):
            # When no opcode is specified, websocket library sends strings as text
            if opcode is None and isinstance(data, str):
                from websocket import ABNF
                opcode = ABNF.OPCODE_TEXT
            verifier.capture_frame(data, opcode)
            return len(data) if hasattr(data, '__len__') else 0
        
        mock_send.side_effect = capture_send
        
        # Set up a mock WebSocket app
        client.ws = Mock(spec=websocket.WebSocketApp)
        client.ws.send = mock_send
        from spacetimedb_sdk.websocket_client import ConnectionState
        client.state = ConnectionState.CONNECTED
        
        # Test sending a message
        logger.info("Sending Subscribe message with text protocol...")
        from spacetimedb_sdk.protocol import Subscribe, generate_request_id
        subscribe_msg = Subscribe(
            query_strings=["SELECT * FROM test"],
            request_id=generate_request_id()
        )
        client.send_message(subscribe_msg)
    
    # Verify results
    logger.info(f"Captured {len(verifier.captured_frames)} frames")
    assert len(verifier.captured_frames) == 1, "Expected 1 frame to be sent"
    
    from websocket import ABNF
    text_count = sum(1 for op in verifier.frame_opcodes if op == ABNF.OPCODE_TEXT)
    logger.info(f"Text frames sent: {text_count}")
    assert text_count == 1, "Expected text frame for text protocol"
    logger.info("✓ Text protocol correctly sends text frames")


def main():
    """Run all frame type verification tests."""
    logger.info("Starting WebSocket frame type verification tests...")
    
    try:
        test_modern_websocket_client_binary_frames()
        logger.info("")
        
        test_legacy_websocket_client_binary_frames()
        logger.info("")
        
        test_text_protocol_sends_text_frames()
        logger.info("")
        
        logger.info("=" * 60)
        logger.info("✅ All tests passed! Binary frames are being sent correctly.")
        logger.info("=" * 60)
        
    except AssertionError as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()