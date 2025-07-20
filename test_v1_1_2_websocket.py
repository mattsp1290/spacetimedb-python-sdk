#!/usr/bin/env python3
'''Test script to verify SpacetimeDB v1.1.2 connection'''

import asyncio
import websocket

# Test parameters
HOST = "localhost:3000"
DB_IDENTITY = "your_database_identity_here"  # Replace with actual identity
PROTOCOL = "v1.json.spacetimedb"

def test_direct_websocket():
    '''Test direct WebSocket connection to v1.1.2'''
    
    url = f"ws://{HOST}/v1/database/{DB_IDENTITY}/subscribe"
    
    print(f"Testing WebSocket connection to: {url}")
    print(f"Using protocol: {PROTOCOL}")
    
    try:
        ws = websocket.create_connection(
            url,
            subprotocols=[PROTOCOL]
        )
        print("✅ WebSocket connection successful!")
        
        # The server should send an IdentityToken message first
        message = ws.recv()
        print(f"Received message: {message[:100]}...")
        
        ws.close()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    print("SpacetimeDB v1.1.2 WebSocket Test")
    print("-" * 40)
    test_direct_websocket()
