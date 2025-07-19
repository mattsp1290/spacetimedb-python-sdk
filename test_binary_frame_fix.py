#!/usr/bin/env python3
"""Test that binary WebSocket frames are sent correctly."""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import websockets
import sys
import logging
sys.path.insert(0, 'src')

from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_binary_frame_sending():
    """Test that binary protocol messages are sent as binary WebSocket frames."""
    
    # Create a test WebSocket server that checks frame types
    frame_types_received = []
    
    async def handle_connection(websocket, path):
        """Handle incoming WebSocket connection and check frame types."""
        logger.info(f"Client connected with subprotocols: {websocket.subprotocol}")
        
        try:
            async for message in websocket:
                # In the websockets library, we can check the type of the received data
                if isinstance(message, bytes):
                    frame_type = "BINARY"
                    logger.info(f"Received BINARY frame: {len(message)} bytes, first 20 bytes: {message[:20].hex()}")
                else:
                    frame_type = "TEXT"
                    logger.info(f"Received TEXT frame: {len(message)} chars, preview: {message[:50]}")
                
                frame_types_received.append(frame_type)
                
                # Send back a simple acknowledgment
                if isinstance(message, bytes):
                    await websocket.send(b"ACK", websockets.frames.Opcode.BINARY)
                else:
                    await websocket.send("ACK")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
    
    # Start test server
    server = await websockets.serve(
        handle_connection, 
        "localhost", 
        8765,
        subprotocols=["v1.bsatn.spacetimedb", "v1.json.spacetimedb"]
    )
    
    logger.info("Test WebSocket server started on ws://localhost:8765")
    
    # Test with websocket-client library (what SDK uses)
    import websocket
    from websocket import ABNF
    
    # Test 1: Binary protocol with explicit binary opcode
    logger.info("\n=== Test 1: Binary protocol with explicit opcode ===")
    helper = SpacetimeDBProtocolHelper(use_binary=True)
    binary_data = helper.encode_subscription(["test_table"])
    
    ws = websocket.create_connection(
        "ws://localhost:8765",
        subprotocols=["v1.bsatn.spacetimedb"]
    )
    
    # Send with explicit binary opcode (our fix)
    ws.send(binary_data, opcode=ABNF.OPCODE_BINARY)
    response = ws.recv()
    logger.info(f"Received response: {response}")
    ws.close()
    
    # Test 2: Binary protocol without explicit opcode (old behavior)
    logger.info("\n=== Test 2: Binary protocol without explicit opcode ===")
    ws = websocket.create_connection(
        "ws://localhost:8765",
        subprotocols=["v1.bsatn.spacetimedb"]
    )
    
    # Send without explicit opcode (might send as text)
    ws.send(binary_data)
    response = ws.recv()
    logger.info(f"Received response: {response}")
    ws.close()
    
    # Test 3: JSON protocol (should be text frame)
    logger.info("\n=== Test 3: JSON protocol ===")
    json_helper = SpacetimeDBProtocolHelper(use_binary=False)
    json_data = json_helper.encode_subscription(["test_table"])
    
    ws = websocket.create_connection(
        "ws://localhost:8765",
        subprotocols=["v1.json.spacetimedb"]
    )
    
    ws.send(json_data)
    response = ws.recv()
    logger.info(f"Received response: {response}")
    ws.close()
    
    # Stop server
    server.close()
    await server.wait_closed()
    
    # Report results
    logger.info("\n=== Test Results ===")
    logger.info(f"Frame types received: {frame_types_received}")
    
    if len(frame_types_received) >= 3:
        if frame_types_received[0] == "BINARY":
            logger.info("✓ Test 1 PASSED: Binary data sent as BINARY frame with explicit opcode")
        else:
            logger.error("✗ Test 1 FAILED: Binary data sent as TEXT frame despite explicit opcode")
            
        if frame_types_received[1] == "TEXT":
            logger.info("✓ Test 2 CONFIRMED: Binary data sent as TEXT frame without explicit opcode (bug reproduced)")
        else:
            logger.info("? Test 2 UNEXPECTED: Binary data sent as BINARY frame without explicit opcode")
            
        if frame_types_received[2] == "TEXT":
            logger.info("✓ Test 3 PASSED: JSON data sent as TEXT frame")
        else:
            logger.error("✗ Test 3 FAILED: JSON data sent as BINARY frame")

if __name__ == "__main__":
    logger.info("Starting WebSocket frame type test...")
    asyncio.run(test_binary_frame_sending())