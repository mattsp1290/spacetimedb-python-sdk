#!/usr/bin/env python3
"""
Integration Test for SpacetimeDB JWT Authentication

This script tests the JWT authentication with a real SpacetimeDB server.
It requires a SpacetimeDB server running with JWT authentication enabled.

Usage:
    # Start SpacetimeDB with authentication:
    spacetimedb start --jwt-pub-key-path ~/.config/spacetime/id_ecdsa.pub
    
    # Publish a test database:
    spacetimedb publish test_auth_db
    
    # Run this test:
    python test_auth_integration.py
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.auth_storage import get_credentials, clear_all_credentials


def setup_logging():
    """Setup logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_authentication_flow():
    """Test the full authentication flow with a real server."""
    print("🔐 Testing SpacetimeDB JWT Authentication Flow")
    print("=" * 50)
    
    # Clear any existing credentials to start fresh
    clear_all_credentials()
    print("✅ Cleared existing credentials")
    
    # Configuration
    HOST = "localhost:3000"
    DATABASE = "test_auth_db"
    
    print(f"📡 Testing connection to {HOST}/{DATABASE}")
    
    # Create client
    client = SpacetimeDBClient(test_mode=False)  # Use real WebSocket
    
    connection_success = False
    auth_token_received = False
    
    def on_connect():
        nonlocal connection_success
        connection_success = True
        print("✅ Successfully connected to SpacetimeDB!")
    
    def on_identity(token, identity, connection_id):
        nonlocal auth_token_received
        auth_token_received = True
        print(f"✅ Received identity: {str(identity)[:16]}...")
        print(f"✅ Connection ID: {str(connection_id)[:16]}...")
    
    def on_error(error):
        print(f"❌ Connection error: {error}")
    
    def on_disconnect(reason):
        print(f"🔌 Disconnected: {reason}")
    
    try:
        print("🔄 Attempting initial connection...")
        
        # Attempt connection - this should trigger the auth handshake if needed
        client._connect_internal(
            auth_token=None,
            host=HOST,
            database_address=DATABASE,
            ssl_enabled=False,
            on_connect=on_connect,
            on_identity=on_identity,
            on_error=on_error,
            on_disconnect=on_disconnect
        )
        
        # Wait for connection or error
        for i in range(30):  # 30 second timeout
            if connection_success and auth_token_received:
                break
            await asyncio.sleep(1)
            if i % 5 == 0:
                print(f"⏳ Waiting for connection... ({i}/30)")
        
        if connection_success and auth_token_received:
            print("✅ Authentication handshake completed successfully!")
            
            # Check that credentials were stored
            stored_creds = get_credentials(HOST, DATABASE)
            if stored_creds:
                print(f"✅ Credentials stored: {stored_creds.identity[:16]}...")
                print(f"📅 Credential age: {stored_creds.age_seconds:.1f} seconds")
            else:
                print("⚠️  No credentials were stored")
            
            # Test a basic operation
            try:
                print("🧪 Testing basic operations...")
                
                # Subscribe to a simple query
                query_id = client.subscribe_single("SELECT * FROM sys.table")
                print(f"✅ Subscription created: {query_id}")
                
                # Wait a bit for any initial data
                await asyncio.sleep(2)
                
                print("✅ Basic operations successful!")
                
            except Exception as e:
                print(f"⚠️  Basic operation failed: {e}")
        
        else:
            print("❌ Connection failed or authentication handshake did not complete")
            return False
    
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            client.disconnect()
            print("🔌 Disconnected from server")
        except:
            pass
    
    print("\n🔄 Testing reconnection with stored credentials...")
    
    # Test reconnection using stored credentials
    try:
        client2 = SpacetimeDBClient(test_mode=False)
        connection_success2 = False
        
        def on_connect2():
            nonlocal connection_success2
            connection_success2 = True
            print("✅ Reconnected successfully using stored credentials!")
        
        client2._connect_internal(
            auth_token=None,
            host=HOST,
            database_address=DATABASE,
            ssl_enabled=False,
            on_connect=on_connect2,
            on_error=on_error
        )
        
        # Wait for reconnection
        for i in range(10):  # 10 second timeout for reconnection
            if connection_success2:
                break
            await asyncio.sleep(1)
        
        if connection_success2:
            print("✅ Reconnection test passed!")
        else:
            print("❌ Reconnection test failed")
            return False
        
        client2.disconnect()
        
    except Exception as e:
        print(f"❌ Reconnection test failed: {e}")
        return False
    
    return True


def print_setup_instructions():
    """Print setup instructions for the test."""
    print("""
🚀 SpacetimeDB JWT Authentication Integration Test

Prerequisites:
1. SpacetimeDB server with JWT authentication enabled
2. A published test database

Setup Instructions:
================

1. Generate JWT keys (if not already done):
   mkdir -p ~/.config/spacetime
   ssh-keygen -t ecdsa -b 256 -f ~/.config/spacetime/id_ecdsa -N ""

2. Start SpacetimeDB server with authentication:
   spacetimedb start --jwt-pub-key-path ~/.config/spacetime/id_ecdsa.pub --jwt-priv-key-path ~/.config/spacetime/id_ecdsa

3. Publish a test database:
   spacetimedb publish test_auth_db --clear-database

4. Run this test:
   python test_auth_integration.py

Expected Flow:
=============
1. Client attempts connection without authentication
2. Server returns 400 with identity token (authentication handshake)
3. Client automatically retries with Bearer token
4. Connection succeeds and credentials are stored
5. Subsequent connections use stored credentials automatically
""")


async def main():
    """Main test function."""
    setup_logging()
    
    print_setup_instructions()
    
    response = input("\n➡️  Do you have a SpacetimeDB server running with authentication? (y/n): ")
    if response.lower() != 'y':
        print("Please set up SpacetimeDB server first and try again.")
        return
    
    print("\n🧪 Starting integration test...\n")
    
    success = await test_authentication_flow()
    
    if success:
        print("\n🎉 All integration tests passed!")
        print("🔐 JWT authentication is working correctly!")
    else:
        print("\n❌ Integration tests failed!")
        print("Check server setup and try again.")
    
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)