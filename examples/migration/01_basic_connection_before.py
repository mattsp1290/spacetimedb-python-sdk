"""
Basic Connection Example - BEFORE Migration

This example shows the old way of connecting to SpacetimeDB.
"""

import asyncio
from spacetimedb_sdk import ModernWebSocketClient


class OldStyleApp:
    def __init__(self):
        self.client = ModernWebSocketClient()
        
    async def connect(self):
        # Manual credential management (insecure)
        self.client.spacetimedb_identity = "stored-identity-12345"
        self.client.spacetimedb_token = "stored-token-abcdef"
        self.client.auth_handshake_completed = True
        
        # Direct connection
        await self.client.connect("ws://localhost:3000/database/mydb")
        
        # Manual header preparation for auth
        headers = {}
        if self.client.spacetimedb_token and self.client.auth_handshake_completed:
            headers["Authorization"] = f"Bearer {self.client.spacetimedb_token}"
        
        print(f"Connected with identity: {self.client.spacetimedb_identity}")
        

async def main():
    app = OldStyleApp()
    await app.connect()
    
    # Keep running
    await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())