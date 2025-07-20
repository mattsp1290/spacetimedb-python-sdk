#!/usr/bin/env python3

import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
sys.path.insert(0, '/Users/punk1290/git/spacetimedb-python-sdk/src')

from spacetimedb_sdk import SpacetimeDBClient
import asyncio
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def test_blackholio():
    try:
        # Connect using module name
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="blackholio",  # Or use the database identity
            auth_token=None,
            ssl_enabled=False,
            protocol="v1.json.spacetimedb"
        )
        print("✅ Connection successful!")
        
        # Test basic operations here if needed
        # For example, call a reducer if the module has one
        
        client.disconnect()
        print("✅ Disconnection successful!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_blackholio()
