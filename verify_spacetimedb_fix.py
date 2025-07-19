#!/usr/bin/env python3
"""
Verify if SpacetimeDB v1.1.2 fix is working
"""

import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import aiohttp
import websockets
import json

async def test_endpoints():
    """Test various endpoints to see if any are working"""
    
    print("Testing SpacetimeDB v1.1.2 Fix Verification")
    print("=" * 50)
    
    # Test HTTP endpoints
    print("\n1. Testing HTTP endpoints:")
    endpoints = ["/", "/health", "/database", "/v1", "/api", "/ws"]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            url = f"http://localhost:3000{endpoint}"
            try:
                async with session.get(url) as resp:
                    print(f"   {endpoint}: {resp.status} {resp.reason}")
            except Exception as e:
                print(f"   {endpoint}: ERROR - {e}")
    
    # Test WebSocket endpoints
    print("\n2. Testing WebSocket endpoints:")
    ws_endpoints = ["/", "/ws", "/websocket", "/subscribe"]
    
    for endpoint in ws_endpoints:
        url = f"ws://localhost:3000{endpoint}"
        try:
            ws = await asyncio.wait_for(websockets.connect(url), timeout=2.0)
            print(f"   {endpoint}: ✓ Connected!")
            await ws.close()
            return True  # If any WebSocket works, the fix is successful
        except Exception as e:
            error_msg = str(e).split('\n')[0]  # First line only
            print(f"   {endpoint}: ✗ {error_msg}")
    
    # Test specific database WebSocket
    print("\n3. Testing database-specific WebSocket:")
    db_id = "c20097ce74a369174df8955fd57b45c0ac8ae35e8d587b377aadc1ba21d352e0"
    url = f"ws://localhost:3000/database/{db_id}/subscribe"
    try:
        ws = await asyncio.wait_for(websockets.connect(url), timeout=2.0)
        print(f"   ✓ Connected to database WebSocket!")
        await ws.close()
        return True
    except Exception as e:
        error_msg = str(e).split('\n')[0]
        print(f"   ✗ {error_msg}")
    
    return False

async def test_sdk_connection():
    """Test if the SDK can connect"""
    print("\n4. Testing Python SDK connection:")
    
    try:
        import sys
        sys.path.insert(0, 'src')
        from spacetimedb_sdk import SpacetimeDBClient
        
        client = SpacetimeDBClient.init(
            auth_token=None,
            host='localhost:3000',
            address_or_name='c20097ce74a369174df8955fd57b45c0ac8ae35e8d587b377aadc1ba21d352e0',
            ssl_enabled=False,
            autogen_package=None,
            on_connect=lambda: print("   ✓ SDK Connected!"),
            on_error=lambda e: print(f"   ✗ SDK Error: {e}")
        )
        
        # Wait a bit for connection
        await asyncio.sleep(2)
        
        if hasattr(client, 'is_connected') and client.is_connected:
            print("   ✓ SDK connection successful!")
            return True
        else:
            print("   ✗ SDK failed to connect")
            
    except Exception as e:
        print(f"   ✗ SDK Error: {type(e).__name__}: {e}")
    
    return False

async def main():
    """Run all tests"""
    
    endpoint_fixed = await test_endpoints()
    sdk_fixed = await test_sdk_connection()
    
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY:")
    print(f"- HTTP/WebSocket endpoints fixed: {'YES ✓' if endpoint_fixed else 'NO ✗'}")
    print(f"- SDK can connect: {'YES ✓' if sdk_fixed else 'NO ✗'}")
    
    if endpoint_fixed or sdk_fixed:
        print("\n✓ SpacetimeDB v1.1.2 appears to be FIXED!")
        print("The Python SDK should now be able to connect.")
    else:
        print("\n✗ SpacetimeDB v1.1.2 is still NOT WORKING")
        print("All endpoints still return 404. The issue persists.")
        print("\nPossible reasons:")
        print("1. The fix hasn't been applied to the running container")
        print("2. The container needs to be rebuilt with the fixed code")
        print("3. The fix addresses a different issue")

if __name__ == "__main__":
    asyncio.run(main())
