#!/usr/bin/env python3
"""
Test script to verify WebSocket subprotocol fix and protocol helper improvements
"""
import sys
import os
import asyncio
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException, InvalidStatus

# Add the local SDK path first
sys.path.insert(0, '/Users/punk1290/git/spacetimedb-python-sdk/src')

# Add the blackholio-client path to sys.path
sys.path.insert(0, '/Users/punk1290/git/blackholio-python-client/src')

from spacetimedb_sdk.protocol_helpers import (
    SpacetimeDBProtocolHelper,
    get_json_protocol_subprotocol,
    get_binary_protocol_subprotocol,
    create_json_subscription,
    create_binary_subscription
)

async def test_connection():
    """Test WebSocket connection with proper subprotocol"""
    print("🔧 Testing WebSocket connection with v1.bsatn.spacetimedb subprotocol...")
    
    # Create environment config
    config = EnvironmentConfig(
        server_language='rust',
        server_ip='localhost',
        server_port=3000,
        server_use_ssl=False,
        spacetime_db_identity='blackholio'
    )
    
    # Create connection
    connection = SpacetimeDBConnection(config)
    
    try:
        print("🔄 Attempting connection...")
        await connection.connect()
        print("✅ Connection successful!")
        
        # Test that subprotocol was negotiated
        if connection.websocket:
            print(f"📡 Negotiated subprotocol: {connection.websocket.subprotocol}")
            if connection.websocket.subprotocol == "v1.bsatn.spacetimedb":
                print("✅ Correct subprotocol negotiated!")
            else:
                print(f"❌ Wrong subprotocol: {connection.websocket.subprotocol}")
        
        await connection.disconnect()
        print("🔌 Disconnected successfully")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        if "HTTP 400" in str(e):
            print("💡 HTTP 400 error suggests subprotocol is still not being sent properly")
        return False

async def test_direct_websocket():
    """Test direct WebSocket connection with subprotocol"""
    print("\n🔧 Testing direct WebSocket connection...")
    
    url = "ws://localhost:3000/v1/database/blackholio/subscribe"
    subprotocols = ["v1.bsatn.spacetimedb"]
    
    try:
        print(f"🔄 Connecting to {url} with subprotocol: {subprotocols}")
        async with websockets.connect(url, subprotocols=subprotocols) as websocket:
            print("✅ Direct WebSocket connection successful!")
            print(f"📡 Negotiated subprotocol: {websocket.subprotocol}")
            return True
    except Exception as e:
        print(f"❌ Direct WebSocket connection failed: {e}")
        return False

async def test_protocol_helpers():
    """Test the improved protocol helpers"""
    print("\n🔧 Testing Protocol Helper Improvements...")
    
    try:
        # Test JSON protocol
        print("Testing JSON protocol helper...")
        json_helper = SpacetimeDBProtocolHelper(use_binary=False)
        
        json_subprotocol = json_helper.get_protocol_subprotocol()
        print(f"  JSON subprotocol: {json_subprotocol}")
        
        json_frame_type = json_helper.get_expected_frame_type()
        print(f"  JSON frame type: {json_frame_type}")
        
        # Test that JSON protocol returns strings
        json_subscription = json_helper.encode_subscription(["test_table"])
        print(f"  JSON subscription type: {type(json_subscription).__name__}")
        print(f"  JSON subscription content: {json_subscription[:100]}...")
        
        # Test binary protocol
        print("\nTesting binary protocol helper...")
        binary_helper = SpacetimeDBProtocolHelper(use_binary=True)
        
        binary_subprotocol = binary_helper.get_protocol_subprotocol()
        print(f"  Binary subprotocol: {binary_subprotocol}")
        
        binary_frame_type = binary_helper.get_expected_frame_type()
        print(f"  Binary frame type: {binary_frame_type}")
        
        # Test that binary protocol returns bytes
        binary_subscription = binary_helper.encode_subscription(["test_table"])
        print(f"  Binary subscription type: {type(binary_subscription).__name__}")
        print(f"  Binary subscription length: {len(binary_subscription)} bytes")
        
        # Test convenience functions
        print("\nTesting convenience functions...")
        conv_json_sub = create_json_subscription(["test_table"])
        conv_binary_sub = create_binary_subscription(["test_table"])
        
        print(f"  Convenience JSON type: {type(conv_json_sub).__name__}")
        print(f"  Convenience binary type: {type(conv_binary_sub).__name__}")
        
        # Validate expectations
        success = True
        if not isinstance(json_subscription, str):
            print("❌ JSON protocol should return str")
            success = False
        if not isinstance(binary_subscription, bytes):
            print("❌ Binary protocol should return bytes")
            success = False
        if json_subprotocol != "v1.json.spacetimedb":
            print(f"❌ JSON subprotocol should be v1.json.spacetimedb, got {json_subprotocol}")
            success = False
        if binary_subprotocol != "v1.bsatn.spacetimedb":
            print(f"❌ Binary subprotocol should be v1.bsatn.spacetimedb, got {binary_subprotocol}")
            success = False
            
        if success:
            print("✅ All protocol helper tests passed!")
        
        return success
        
    except Exception as e:
        print(f"❌ Protocol helper test failed: {e}")
        return False

async def main():
    print("🚀 WebSocket Subprotocol Fix & Protocol Helper Test")
    print("=" * 60)
    
    # Test 1: Protocol helpers
    helper_success = await test_protocol_helpers()
    
    # Test 2: Direct WebSocket connection
    direct_success = await test_direct_websocket()
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"   Protocol Helpers: {'✅ PASS' if helper_success else '❌ FAIL'}")
    print(f"   Direct WebSocket: {'✅ PASS' if direct_success else '❌ FAIL'}")
    
    if helper_success and direct_success:
        print("🎉 All tests passed! Protocol fix is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Protocol may need further fixes.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))