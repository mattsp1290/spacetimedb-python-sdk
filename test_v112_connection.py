#!/usr/bin/env python3
"""
Test script to verify SpacetimeDB v1.1.2 compatibility fix
"""

import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import time
import asyncio

# Add the SDK to the path
sys.path.insert(0, 'src')

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL

def on_connect():
    print("✅ Connected successfully!")
    print("The v1.1.2 protocol fix is working!")

def on_error(error):
    print(f"❌ Connection error: {error}")
    if "no valid protocol selected" in str(error):
        print("The fix did not work - still getting protocol error")
    elif "invalid characters in database name" in str(error):
        print("Database name contains invalid characters - use only alphanumeric characters and hyphens")
    else:
        print("Different error - check if server is running")

def on_identity(token, identity, connection_id):
    print(f"✅ Identity received!")
    print(f"   Token: {token[:20]}..." if token else "   Token: None")
    print(f"   Identity: {identity}")
    print(f"   Connection ID: {connection_id}")

def on_disconnect(msg):
    print(f"Disconnected: {msg}")

def test_simple_connection():
    print("\n" + "="*60)
    print("Testing SpacetimeDB v1.1.2 connection with simple connect")
    print("="*60)
    
    try:
        # Note: Replace with your actual database name
        # Database names should only contain alphanumeric characters and hyphens
        # Examples: "my-database", "testdb", "game-server"
        # NOT: "test_module", "my.database", "test module"
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test-module",  # Changed from test_module to test-module
            auth_token=None,  # Will generate a new token
            ssl_enabled=False,
            on_connect=on_connect,
            on_error=on_error,
            on_identity=on_identity,
            on_disconnect=on_disconnect,
            db_identity=None  # Will use database name as fallback
            # protocol is now handled internally and defaults to TEXT_PROTOCOL
        )
        
        print("\nConnection initiated. Waiting for response...")
        # Give it some time to connect
        time.sleep(3)
        
        # Keep the client alive for a bit
        print("\nConnection test complete. Disconnecting...")
        client.disconnect()
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()

def test_builder_pattern():
    print("\n" + "="*60)
    print("Testing with builder pattern")
    print("="*60)
    
    try:
        client = SpacetimeDBClient.builder() \
            .with_uri("ws://localhost:3000") \
            .with_module_name("test-module") \
            .with_protocol("text") \
            .on_connect(lambda: print("✅ Connected with builder!")) \
            .on_error(lambda e: print(f"❌ Error with builder: {e}")) \
            .build()
        
        print("\nConnection initiated via builder. Waiting...")
        time.sleep(3)
        
        print("\nBuilder test complete. Disconnecting...")
        client.disconnect()
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()

async def test_async_operations():
    print("\n" + "="*60)
    print("Testing async operations")
    print("="*60)
    
    try:
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test-module",
            ssl_enabled=False,
            on_connect=lambda: print("✅ Connected for async test!")
        )
        
        # Wait for connection
        await asyncio.sleep(2)
        
        if client.is_connected:
            print("✅ Client is connected, ready for operations")
            
            # Get connection info
            info = client.get_connection_info()
            print(f"\nConnection Info:")
            print(f"  State: {info.get('state')}")
            print(f"  Identity: {info.get('identity')}")
            print(f"  Protocol: {info.get('protocol')}")
            
        client.disconnect()
        await asyncio.sleep(1)
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("SpacetimeDB v1.1.2 Protocol Fix Test")
    print("="*60)
    print("IMPORTANT: Database names in v1.1.2 can only contain:")
    print("  - Lowercase letters (a-z)")
    print("  - Numbers (0-9)")
    print("  - Hyphens (-)")
    print("")
    print("Examples of VALID names: my-database, testdb, game-server")
    print("Examples of INVALID names: test_module, my.database, TestDB")
    print("="*60)
    print("Make sure SpacetimeDB is running on localhost:3000")
    print("Replace 'test-module' with your actual database name")
    
    # Test simple connection
    test_simple_connection()
    
    # Small delay between tests
    time.sleep(2)
    
    # Test builder pattern
    test_builder_pattern()
    
    # Small delay between tests
    time.sleep(2)
    
    # Test async operations
    asyncio.run(test_async_operations())
    
    print("\n" + "="*60)
    print("Test complete!")
    print("If you see 'Connected successfully!' messages above,")
    print("the v1.1.2 compatibility fix is working correctly.")
    print("="*60)
