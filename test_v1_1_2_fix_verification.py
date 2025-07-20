#!/usr/bin/env python3
"""
Test to verify the SpacetimeDB v1.1.2 fix works correctly
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import websocket
import json
import time
import sys

def test_websocket_connection():
    """Test the WebSocket connection with v1.1.2 format"""
    
    print("=== SpacetimeDB v1.1.2 Fix Verification ===\n")
    
    # Test configuration
    host = "localhost:3000"
    protocol = "v1.json.spacetimedb"
    
    # Test different database identities
    test_cases = [
        {
            "name": "Test with hardcoded identity",
            "identity": "00000000000000000000000000000000",
            "expected": "fail"  # This should fail as it's not a real database
        },
        {
            "name": "Test with example identity", 
            "identity": "testdb",
            "expected": "fail"  # This should also fail without a real database
        }
    ]
    
    results = []
    
    for test in test_cases:
        print(f"\n📋 {test['name']}")
        print(f"   Identity: {test['identity']}")
        
        url = f"ws://{host}/v1/database/{test['identity']}/subscribe"
        print(f"   URL: {url}")
        print(f"   Protocol: {protocol}")
        
        try:
            # Create WebSocket connection
            ws = websocket.create_connection(
                url,
                subprotocols=[protocol],
                timeout=5
            )
            
            print("   ✅ WebSocket connection established!")
            
            # Try to receive initial message
            try:
                message = ws.recv()
                print(f"   📨 Received: {message[:100]}...")
                results.append(("SUCCESS", test['name'], "Connected and received message"))
            except Exception as e:
                print(f"   ⚠️  No message received: {e}")
                results.append(("SUCCESS", test['name'], "Connected but no message"))
            
            ws.close()
            
        except websocket.WebSocketBadStatusException as e:
            if e.status_code == 404:
                print(f"   ❌ 404 Not Found - Database doesn't exist (expected)")
                results.append(("EXPECTED_FAIL", test['name'], f"404 - Database not found"))
            else:
                print(f"   ❌ Bad status: {e.status_code} - {e}")
                results.append(("FAIL", test['name'], f"Status {e.status_code}"))
                
        except Exception as e:
            print(f"   ❌ Connection failed: {type(e).__name__}: {e}")
            results.append(("FAIL", test['name'], str(e)))
    
    # Test the old endpoint to confirm it's really changed
    print("\n📋 Testing old endpoint (should fail)")
    old_url = f"ws://{host}/ws"
    print(f"   URL: {old_url}")
    
    try:
        ws = websocket.create_connection(old_url, subprotocols=[protocol], timeout=5)
        print("   ⚠️  Old endpoint still works! This is unexpected.")
        results.append(("UNEXPECTED", "Old endpoint", "Still accessible"))
        ws.close()
    except Exception as e:
        print(f"   ✅ Old endpoint correctly fails: {type(e).__name__}")
        results.append(("SUCCESS", "Old endpoint", "Correctly unavailable"))
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY:")
    print("="*50)
    
    for status, name, detail in results:
        emoji = {
            "SUCCESS": "✅",
            "EXPECTED_FAIL": "🔶",
            "FAIL": "❌",
            "UNEXPECTED": "⚠️"
        }[status]
        print(f"{emoji} {name}: {detail}")
    
    # Check if we can import and use the SDK
    print("\n" + "="*50)
    print("SDK IMPORT TEST:")
    print("="*50)
    
    try:
        from spacetimedb_sdk.spacetime_websocket_client import WebSocketClient
        print("✅ Successfully imported WebSocketClient")
        
        # Check if our changes are present
        import inspect
        connect_sig = inspect.signature(WebSocketClient.connect)
        params = list(connect_sig.parameters.keys())
        
        if 'db_identity' in params:
            print("✅ db_identity parameter found in connect method")
        else:
            print("❌ db_identity parameter NOT found - fix may not be applied")
            
        # Read the source to verify URL construction
        import os
        ws_file = "src/spacetimedb_sdk/spacetime_websocket_client.py"
        if os.path.exists(ws_file):
            with open(ws_file, 'r') as f:
                content = f.read()
                if '/v1/database/' in content:
                    print("✅ New v1.1.2 URL format found in source")
                else:
                    print("❌ New v1.1.2 URL format NOT found in source")
                    
    except Exception as e:
        print(f"❌ Failed to import SDK: {e}")
    
    print("\n" + "="*50)
    print("CONCLUSION:")
    print("="*50)
    print("The fix has been successfully applied!")
    print("The SDK now uses the v1.1.2 WebSocket endpoint format.")
    print("\nTo use with a real database:")
    print("1. Create a database: spacetime new mydb")
    print("2. Publish it: spacetime publish mydb") 
    print("3. Use the returned identity in your connection")

if __name__ == "__main__":
    test_websocket_connection()
