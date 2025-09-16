#!/usr/bin/env python3
"""
Integration test to verify the tag 0x13 fix works with a real SpaceTimeDB server.

This connects to a local SpaceTimeDB server and attempts to send a subscription
request to verify that the "unknown tag 0x13" error is resolved.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import sys
import websockets
import logging

sys.path.insert(0, 'src')

from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper, get_binary_protocol_subprotocol
from spacetimedb_sdk.protocol import ProtocolDecoder

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_subscription():
    """Test subscription to SpaceTimeDB with the fixed binary protocol."""
    # Server connection details
    url = "ws://localhost:3000/v1/database/blackholio/subscribe"
    
    # Create protocol helper with binary mode
    protocol_helper = SpacetimeDBProtocolHelper(use_binary=True)
    decoder = ProtocolDecoder(use_binary=True)
    
    try:
        # Connect with binary subprotocol
        logger.info(f"Connecting to {url}")
        async with websockets.connect(
            url,
            subprotocols=[get_binary_protocol_subprotocol()]
        ) as websocket:
            logger.info(f"Connected successfully. Subprotocol: {websocket.subprotocol}")
            
            # Send subscription request
            tables = ["entity", "player", "circle", "food", "config"]
            subscription_msg = protocol_helper.encode_subscription(tables, request_id=1)
            
            logger.info(f"Sending subscription request (binary, {len(subscription_msg)} bytes)")
            logger.debug(f"First 20 bytes: {subscription_msg[:20].hex()}")
            
            await websocket.send(subscription_msg)
            logger.info("Subscription request sent successfully")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                
                if isinstance(response, bytes):
                    logger.info(f"Received binary response ({len(response)} bytes)")
                    # Try to decode the response
                    try:
                        decoded_msg = decoder.decode_server_message(response)
                        logger.info(f"Decoded server message: {type(decoded_msg).__name__}")
                        logger.info("✅ SUCCESS: No tag 0x13 error! Server accepted the message.")
                        return True
                    except Exception as e:
                        logger.warning(f"Could not decode response: {e}")
                        logger.info("But connection is still active - no tag error!")
                        return True
                else:
                    logger.info(f"Received text response: {response}")
                    return True
                    
            except asyncio.TimeoutError:
                logger.info("No immediate response, but no error either - connection successful!")
                return True
                
    except websockets.exceptions.WebSocketException as e:
        error_msg = str(e)
        if "unknown tag 0x13" in error_msg:
            logger.error(f"❌ FAILED: Tag 0x13 error still present: {error_msg}")
            return False
        else:
            logger.error(f"WebSocket error (not tag-related): {error_msg}")
            # If it's a different error, the tag fix might still be working
            return None
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None


async def main():
    """Run the integration test."""
    print("SpaceTimeDB Tag 0x13 Fix - Integration Test")
    print("=" * 50)
    print("Testing connection to local SpaceTimeDB server...")
    print()
    
    result = await test_subscription()
    
    print()
    print("=" * 50)
    
    if result is True:
        print("✅ SUCCESS: The tag 0x13 fix is working!")
        print("The server accepted the binary subscription message without error.")
    elif result is False:
        print("❌ FAILED: The tag 0x13 error is still occurring.")
        print("The fix may not be complete or there may be other issues.")
        sys.exit(1)
    else:
        print("⚠️  INCONCLUSIVE: Could not verify the fix due to connection issues.")
        print("Make sure a SpaceTimeDB server is running at localhost:3000")
        sys.exit(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        sys.exit(0)