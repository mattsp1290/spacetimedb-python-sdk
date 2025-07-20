#!/usr/bin/env python3
import websocket
import sys

# Test raw WebSocket connection
ws_url = "ws://localhost:3000/v1/database/blackholio/subscribe"
print(f"Testing WebSocket connection to: {ws_url}")

try:
    ws = websocket.create_connection(
        ws_url,
        subprotocols=["v1.json.spacetimedb"],
        timeout=5
    )
    print("✅ Raw WebSocket connection successful!")
    ws.close()
except Exception as e:
    print(f"❌ WebSocket connection failed: {e}")
    
# Try with database identity if available
print("\nYou can also try with a database identity (if known):")
print("ws://localhost:3000/v1/database/[identity]/subscribe")
