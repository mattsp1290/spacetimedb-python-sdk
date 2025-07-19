"""
Event Handling Example - BEFORE Migration

This example shows the old way of handling events with multiple event systems.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
from spacetimedb_sdk import ModernWebSocketClient
from spacetimedb_sdk.event_system import EventType as EventType1
from spacetimedb_sdk.event_manager import EventType as EventType2


class OldEventHandling:
    def __init__(self):
        self.client = ModernWebSocketClient()
        self.setup_handlers()
        
    def setup_handlers(self):
        # Three different event systems with different APIs
        
        # System 1: event_system with lowercase events
        self.client.event_system.on('connection_opened', self.on_connect_1)
        self.client.event_system.on('message_received', self.on_message_1)
        self.client.event_system.on('error', self.on_error_1)
        
        # System 2: event_manager with UPPERCASE events
        self.client.event_manager.register_handler('CONNECTION_OPENED', self.on_connect_2)
        self.client.event_manager.register_handler('MESSAGE_RECEIVED', self.on_message_2)
        self.client.event_manager.register_handler('ERROR', self.on_error_2)
        
        # System 3: Direct event registration (if available)
        self.client.on_event('TABLE_UPDATE', self.on_table_update)
        
    # Different handler signatures for each system
    def on_connect_1(self, client):
        print("[System 1] Connected!")
        
    def on_connect_2(self, event_data):
        print("[System 2] Connected!")
        
    def on_message_1(self, message_type, data):
        print(f"[System 1] Message: {message_type} - {data}")
        
    def on_message_2(self, event_data):
        print(f"[System 2] Message: {event_data}")
        
    def on_error_1(self, error):
        print(f"[System 1] Error: {error}")
        
    def on_error_2(self, event_data):
        print(f"[System 2] Error: {event_data.get('error')}")
        
    def on_table_update(self, table, operation, row):
        print(f"Table {table} {operation}: {row}")
        
    # Complex event handling logic scattered across multiple handlers
    def handle_reducer_result(self, reducer_name, args, status):
        if status == "success":
            print(f"Reducer {reducer_name} succeeded")
        else:
            print(f"Reducer {reducer_name} failed")
            
    async def run(self):
        await self.client.connect("ws://localhost:3000/database/mydb")
        
        # Subscribe to tables with old API
        await self.client.subscribe(["SELECT * FROM users", "SELECT * FROM messages"])


async def main():
    app = OldEventHandling()
    await app.run()
    await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())