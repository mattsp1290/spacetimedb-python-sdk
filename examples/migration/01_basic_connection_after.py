"""
Basic Connection Example - AFTER Migration

This example shows the new way of connecting to SpacetimeDB with improved security and architecture.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
from spacetimedb_sdk import (
    ModernWebSocketClient,
    SpacetimeDBConnectionBuilder,
    store_credentials,
    get_credentials
)


class NewStyleApp:
    def __init__(self):
        # Option 1: Use connection builder for better configuration
        self.client = SpacetimeDBConnectionBuilder() \
            .with_url("ws://localhost:3000") \
            .with_database("mydb") \
            .with_reconnect_policy(max_retries=5, initial_delay=1.0) \
            .build()
            
        # Option 2: Still works with standard client
        # self.client = ModernWebSocketClient()
        
    async def connect(self):
        # Secure credential storage (encrypted)
        store_credentials(
            identity="stored-identity-12345",
            token="stored-token-abcdef",
            host="localhost",
            database="mydb"
        )
        
        # Connection automatically uses stored credentials
        await self.client.connect()
        
        # No manual header preparation needed - handled automatically
        
        # Retrieve credentials if needed (but usually not necessary)
        creds = get_credentials("localhost", "mydb")
        if creds and not creds.is_expired():
            print(f"Connected with identity: {creds.identity[:8]}...")  # Masked for security
        

async def main():
    app = NewStyleApp()
    await app.connect()
    
    # Keep running
    await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())