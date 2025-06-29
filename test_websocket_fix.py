#!/usr/bin/env python3
"""
Test script to verify WebSocket subprotocol fix
"""
import sys
import os
import asyncio
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException, InvalidStatus

# Add the blackholio-client path to sys.path
sys.path.insert(0, '/Users/punk1290/git/blackholio-python-client/src')

from blackholio_client.connection.spacetimedb_connection import SpacetimeDBConnection
from blackholio_client.config.environment import EnvironmentConfig

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

async def main():
    print("🚀 WebSocket Subprotocol Fix Test")
    print("=" * 50)
    
    # Test 1: Direct WebSocket connection
    direct_success = await test_direct_websocket()
    
    # Test 2: Through SpacetimeDBConnection
    connection_success = await test_connection()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   Direct WebSocket: {'✅ PASS' if direct_success else '❌ FAIL'}")
    print(f"   SpacetimeDB Connection: {'✅ PASS' if connection_success else '❌ FAIL'}")
    
    if direct_success and connection_success:
        print("🎉 All tests passed! WebSocket subprotocol fix is working.")
        return 0
    else:
        print("⚠️  Some tests failed. WebSocket subprotocol may need further fixes.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))