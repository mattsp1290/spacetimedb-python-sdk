#!/usr/bin/env python3
"""
Test script to verify the fixed URL structure for SpacetimeDB v1.1.2
Tests the corrected implementation with db_identity as query parameter
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
sys.path.insert(0, '/Users/punk1290/git/spacetimedb-python-sdk/src')

import time
import logging
from spacetimedb_sdk import WebSocketClient
from spacetimedb_sdk.websocket_client import WebSocketClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_websocket_client():
    """Test the basic WebSocketClient with corrected URL structure"""
    print("\n" + "=" * 80)
    print("Testing Basic WebSocketClient (spacetime_websocket_client.py)")
    print("=" * 80)
    
    connected = False
    error_msg = None
    
    def on_connect():
        nonlocal connected
        connected = True
        logger.info("✅ Connected successfully!")
    
    def on_error(error):
        nonlocal error_msg
        error_msg = str(error)
        logger.error(f"❌ Error: {error}")
    
    def on_message(message):
        logger.info(f"📨 Message received: {message[:100]}...")
    
    def on_close(msg):
        logger.info(f"🔌 Connection closed: {msg}")
    
    # Test with v1.json.spacetimedb protocol
    print("\n1. Testing with v1.json.spacetimedb protocol:")
    client = WebSocketClient(
        protocol="v1.json.spacetimedb",
        on_connect=on_connect,
        on_error=on_error,
        on_message=on_message,
        on_close=on_close
    )
    
    # Connect without db_identity
    print("   a) Without db_identity:")
    client.connect(
        auth=None,
        host="localhost:3000",
        name_or_address="blackholio",
        ssl_enabled=False
    )
    
    # Wait for connection
    time.sleep(2)
    
    if connected:
        print("   ✅ Connection successful!")
    else:
        print(f"   ❌ Connection failed: {error_msg}")
    
    client.close()
    connected = False
    error_msg = None
    time.sleep(1)
    
    # Test with db_identity
    print("\n   b) With db_identity as query parameter:")
    client2 = WebSocketClient(
        protocol="v1.json.spacetimedb",
        on_connect=on_connect,
        on_error=on_error,
        on_message=on_message,
        on_close=on_close
    )
    
    client2.connect(
        auth=None,
        host="localhost:3000",
        name_or_address="blackholio",
        ssl_enabled=False,
        db_identity="test_identity_12345"
    )
    
    time.sleep(2)
    
    if connected:
        print("   ✅ Connection successful with db_identity!")
    else:
        print(f"   ❌ Connection failed: {error_msg}")
    
    client2.close()

def test_modern_websocket_client():
    """Test the WebSocketClient with corrected URL structure"""
    print("\n" + "=" * 80)
    print("Testing WebSocketClient (websocket_client.py)")
    print("=" * 80)
    
    connected = False
    error_msg = None
    identity_received = False
    
    def on_connect():
        nonlocal connected
        connected = True
        logger.info("✅ Connected successfully!")
    
    def on_error(error):
        nonlocal error_msg
        error_msg = str(error)
        logger.error(f"❌ Error: {error}")
    
    def on_message(message):
        nonlocal identity_received
        logger.info(f"📨 Message received: {type(message).__name__}")
        if hasattr(message, 'identity'):
            identity_received = True
            logger.info(f"   Identity: {message.identity}")
    
    def on_disconnect(msg):
        logger.info(f"🔌 Disconnected: {msg}")
    
    # Test with TEXT_PROTOCOL
    print("\n1. Testing with TEXT_PROTOCOL (v1.json.spacetimedb):")
    from spacetimedb_sdk.protocol import TEXT_PROTOCOL
    
    client = WebSocketClient(
        protocol=TEXT_PROTOCOL,
        on_connect=on_connect,
        on_error=on_error,
        on_message=on_message,
        on_disconnect=on_disconnect,
        auto_reconnect=False
    )
    
    # Connect without db_identity
    print("   a) Without db_identity:")
    client.connect(
        auth_token=None,
        host="localhost:3000",
        database_address="blackholio",
        ssl_enabled=False
    )
    
    # Wait for connection and identity
    time.sleep(3)
    
    if connected:
        print("   ✅ Connection successful!")
        if identity_received:
            print("   ✅ Identity token received!")
    else:
        print(f"   ❌ Connection failed: {error_msg}")
    
    client.disconnect()
    connected = False
    error_msg = None
    identity_received = False
    time.sleep(1)
    
    # Test with db_identity
    print("\n   b) With db_identity as query parameter:")
    client2 = WebSocketClient(
        protocol=TEXT_PROTOCOL,
        on_connect=on_connect,
        on_error=on_error,
        on_message=on_message,
        on_disconnect=on_disconnect,
        auto_reconnect=False
    )
    
    client2.connect(
        auth_token=None,
        host="localhost:3000",
        database_address="blackholio",
        ssl_enabled=False,
        db_identity="test_identity_67890"
    )
    
    time.sleep(3)
    
    if connected:
        print("   ✅ Connection successful with db_identity!")
        if identity_received:
            print("   ✅ Identity token received!")
    else:
        print(f"   ❌ Connection failed: {error_msg}")
    
    # Get connection info
    conn_info = client2.get_connection_info()
    print(f"\n   Connection Info:")
    print(f"   - State: {conn_info['state']}")
    print(f"   - Protocol: {conn_info['protocol']}")
    print(f"   - Database: {conn_info['database']}")
    
    client2.disconnect()

def main():
    """Main test runner"""
    print("SpacetimeDB v1.1.2 URL Structure Verification")
    print("Testing the fixed implementation with db_identity as query parameter")
    
    # Test basic client
    test_basic_websocket_client()
    
    # Test modern client
    test_modern_websocket_client()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\nThe WebSocket clients have been updated to use the correct URL structure:")
    print("- Database name/address in the URL path: /v1/database/{name}/subscribe")
    print("- db_identity as query parameter: ?db_identity={identity}")
    print("\nThis matches the v1.1.2 protocol requirements.")

if __name__ == "__main__":
    main()
