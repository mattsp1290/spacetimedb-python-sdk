"""
Event Handling Example - AFTER Migration

This example shows the new unified event handling system.
"""

import asyncio
from spacetimedb_sdk import (
    ModernWebSocketClient,
    EventType,
    subscribe_to_events,
    EventContext,
    AdvancedSubscriptionBuilder
)


class NewEventHandling:
    def __init__(self):
        self.client = ModernWebSocketClient()
        self.setup_handlers()
        
    def setup_handlers(self):
        # Single unified event system with consistent API
        
        # Subscribe to multiple events with one handler
        subscribe_to_events(self.on_event, [
            EventType.CONNECTION_OPENED,
            EventType.CONNECTION_CLOSED,
            EventType.CONNECTION_ERROR,
            EventType.MESSAGE_RECEIVED,
            EventType.TABLE_UPDATE,
            EventType.REDUCER_SUCCESS,
            EventType.REDUCER_ERROR,
            EventType.ERROR_OCCURRED
        ])
        
        # Or use specific handlers for specific events
        subscribe_to_events(self.on_connection_events, [
            EventType.CONNECTION_OPENED,
            EventType.CONNECTION_CLOSED,
            EventType.CONNECTION_LOST
        ], priority=100)  # Higher priority
        
        # One-time handlers
        from spacetimedb_sdk import get_event_manager
        get_event_manager().once(EventType.AUTHENTICATION_SUCCESS, self.on_auth_success)
        
    # Unified handler signature with EventContext
    def on_event(self, context: EventContext):
        """Single handler for all events with consistent context."""
        event_type = context.event_type
        data = context.data
        metadata = context.metadata
        
        if event_type == EventType.CONNECTION_OPENED:
            print(f"Connected! Session: {metadata.get('session_id')}")
            
        elif event_type == EventType.MESSAGE_RECEIVED:
            print(f"Message: {data}")
            
        elif event_type == EventType.TABLE_UPDATE:
            table = data.get('table_name')
            operation = data.get('operation')  # 'insert', 'update', 'delete'
            row = data.get('row')
            print(f"Table {table} {operation}: {row}")
            
        elif event_type == EventType.REDUCER_SUCCESS:
            reducer = data.get('reducer_name')
            result = data.get('result')
            print(f"Reducer {reducer} succeeded: {result}")
            
        elif event_type == EventType.REDUCER_ERROR:
            reducer = data.get('reducer_name')
            error = data.get('error')
            print(f"Reducer {reducer} failed: {error}")
            
        elif event_type == EventType.ERROR_OCCURRED:
            print(f"Error: {data.get('message')} (Code: {data.get('code')})")
            
    def on_connection_events(self, context: EventContext):
        """Specialized handler for connection events."""
        if context.event_type == EventType.CONNECTION_OPENED:
            print("Connection established - ready for operations")
        elif context.event_type == EventType.CONNECTION_CLOSED:
            print("Connection closed gracefully")
        elif context.event_type == EventType.CONNECTION_LOST:
            print("Connection lost - will attempt reconnection")
            
    def on_auth_success(self, context: EventContext):
        """One-time handler for authentication success."""
        print(f"Authentication successful! Identity: {context.data.get('identity')[:8]}...")
        
    async def run(self):
        await self.client.connect("ws://localhost:3000/database/mydb")
        
        # Enhanced subscription with builder pattern
        subscription = AdvancedSubscriptionBuilder() \
            .select("SELECT * FROM users") \
            .select("SELECT * FROM messages ORDER BY created_at DESC LIMIT 100") \
            .with_error_handler(self.on_subscription_error) \
            .with_auto_reconnect() \
            .build()
            
        await self.client.subscribe(subscription)
        
    def on_subscription_error(self, error):
        """Handle subscription-specific errors."""
        print(f"Subscription error: {error}")


async def main():
    app = NewEventHandling()
    await app.run()
    await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())