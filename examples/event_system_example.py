"""
Example: Advanced Event System for SpacetimeDB Python SDK

Demonstrates TypeScript SDK-compatible event handling:
- EventContext with rich metadata
- Event filtering and transformation
- Async event handlers
- Event history and metrics
- Custom event types
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Any, List

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    EventType, EventContext, Event,
    create_event, create_reducer_event, create_table_event,
    global_event_bus
)


# Example data models
@dataclass
class User:
    id: int
    name: str
    email: str
    online: bool = False


@dataclass
class ChatMessage:
    id: int
    user_id: int
    text: str
    timestamp: float
    channel: str = "general"


class EventSystemExample:
    """Example demonstrating advanced event system features."""
    
    def __init__(self):
        self.client = ModernSpacetimeDBClient()
        self.event_log: List[str] = []
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Set up various event handlers demonstrating different features."""
        
        # 1. Basic event handler with priority
        self.client.on_event(
            EventType.CONNECTION_ESTABLISHED,
            self.on_connection_established,
            priority=100,  # High priority
            handler_name="connection_logger"
        )
        
        # 2. Wildcard handler that logs all events
        self.client.on_event(
            "*",  # Catch all events
            self.log_all_events,
            priority=1  # Low priority
        )
        
        # 3. Table event handlers with filtering
        self.client.on_event(
            EventType.TABLE_ROW_INSERT,
            self.on_user_joined,
            handler_name="user_join_handler"
        )
        
        self.client.on_event(
            EventType.TABLE_ROW_UPDATE,
            self.on_user_status_change,
            handler_name="user_status_handler"
        )
        
        # 4. Reducer event handlers
        self.client.on_event(
            EventType.REDUCER_SUCCESS,
            self.on_reducer_success,
            priority=50
        )
        
        self.client.on_event(
            EventType.REDUCER_ERROR,
            self.on_reducer_error,
            priority=50
        )
        
        # 5. Add event filter - only process events from specific tables
        self.client.event_emitter.add_filter(
            lambda event: self.filter_important_tables(event),
            name="important_tables_filter"
        )
        
        # 6. Add event transformer - enrich events with additional data
        self.client.event_emitter.add_transformer(
            lambda event: self.enrich_event_data(event),
            name="event_enricher"
        )
    
    def on_connection_established(self, ctx: EventContext):
        """Handle connection established event."""
        self.event_log.append(f"[{ctx.timestamp}] Connected to SpacetimeDB!")
        
        # Add connection info to response
        ctx.set_response("connection_time", time.time())
        ctx.set_response("status", "ready")
        
        # Trigger a custom event
        welcome_event = create_event(
            EventType.CUSTOM,
            {"message": "Welcome to the chat!", "type": "system_message"}
        )
        ctx.trigger_event(welcome_event)
    
    def log_all_events(self, ctx: EventContext):
        """Log all events (wildcard handler)."""
        event_info = f"Event: {ctx.event_type.value}, ID: {ctx.event_id[:8]}"
        
        # Don't log our own log events to avoid recursion
        if ctx.event.data.get("type") != "log_entry":
            self.event_log.append(f"[LOG] {event_info}")
    
    def on_user_joined(self, ctx: EventContext):
        """Handle user join events."""
        if ctx.event.type != EventType.TABLE_ROW_INSERT:
            return
        
        table_event = ctx.event
        if table_event.table_name == "users":
            user_data = table_event.row_data
            self.event_log.append(
                f"[USER] {user_data.get('name', 'Unknown')} joined the chat!"
            )
            
            # Stop propagation if this is a system user
            if user_data.get('name', '').startswith('system_'):
                ctx.stop_propagation()
    
    def on_user_status_change(self, ctx: EventContext):
        """Handle user status updates."""
        if ctx.event.type != EventType.TABLE_ROW_UPDATE:
            return
        
        table_event = ctx.event
        if table_event.table_name == "users" and table_event.old_row_data:
            old_status = table_event.old_row_data.get('online', False)
            new_status = table_event.row_data.get('online', False)
            
            if old_status != new_status:
                user_name = table_event.row_data.get('name', 'Unknown')
                status = "online" if new_status else "offline"
                self.event_log.append(f"[STATUS] {user_name} is now {status}")
    
    def on_reducer_success(self, ctx: EventContext):
        """Handle successful reducer calls."""
        reducer_event = ctx.event
        reducer_name = reducer_event.reducer_name
        
        # Track execution time
        exec_time = reducer_event.execution_time_ms
        self.event_log.append(
            f"[REDUCER] {reducer_name} succeeded in {exec_time:.2f}ms"
        )
        
        # Mark specific reducers as handled to stop further processing
        if reducer_name in ["system_maintenance", "debug_command"]:
            ctx.mark_handled(f"admin_reducer_{reducer_name}")
            ctx.stop_propagation()
    
    def on_reducer_error(self, ctx: EventContext):
        """Handle reducer errors."""
        reducer_event = ctx.event
        error_msg = reducer_event.error_message or "Unknown error"
        
        self.event_log.append(
            f"[ERROR] Reducer {reducer_event.reducer_name} failed: {error_msg}"
        )
        
        # Set error response
        ctx.set_response("error_handled", True)
        ctx.set_response("support_ticket_id", f"ERR-{ctx.event_id[:8]}")
    
    def filter_important_tables(self, event: Event) -> bool:
        """Filter to only process events from important tables."""
        # Only process table events
        if not isinstance(event.type, EventType):
            return True
        
        if event.type in [EventType.TABLE_ROW_INSERT, 
                         EventType.TABLE_ROW_UPDATE,
                         EventType.TABLE_ROW_DELETE]:
            # Only process users and messages tables
            table_name = event.data.get('table_name', '')
            return table_name in ['users', 'messages', 'chat_messages']
        
        # Allow all non-table events
        return True
    
    def enrich_event_data(self, event: Event) -> Event:
        """Transform events by adding enrichment data."""
        # Add processing timestamp
        event.data['processed_at'] = time.time()
        
        # Add environment info
        event.data['environment'] = 'production'
        event.data['sdk_version'] = '1.1.1'
        
        # For table events, add table statistics
        if hasattr(event, 'table_name'):
            event.data['table_stats'] = {
                'estimated_rows': 1000,  # In real app, get from cache
                'last_update': time.time()
            }
        
        return event
    
    async def demonstrate_async_handlers(self):
        """Demonstrate async event handling."""
        
        # Define an async handler
        async def async_message_processor(ctx: EventContext):
            """Async handler that processes messages with delay."""
            if ctx.event.type != EventType.TABLE_ROW_INSERT:
                return
            
            table_event = ctx.event
            if table_event.table_name == "chat_messages":
                # Simulate async processing (e.g., calling external API)
                await asyncio.sleep(0.1)
                
                message_data = table_event.row_data
                self.event_log.append(
                    f"[ASYNC] Processed message: {message_data.get('text', '')[:50]}..."
                )
                
                # Set async processing result
                ctx.set_response("sentiment", "positive")  # Simulated sentiment
                ctx.set_response("processed_by", "async_handler")
        
        # Register async handler
        handler_id = self.client.on_event(
            EventType.TABLE_ROW_INSERT,
            async_message_processor,
            handler_name="async_message_processor"
        )
        
        # Simulate some message inserts
        for i in range(3):
            message_event = create_table_event(
                "chat_messages",
                "insert",
                {
                    "id": i,
                    "user_id": 1,
                    "text": f"Hello from async test message {i}!",
                    "timestamp": time.time()
                }
            )
            self.client.emit_event(message_event)
        
        # Wait for async processing
        await asyncio.sleep(0.5)
        
        # Clean up
        self.client.off_event(EventType.TABLE_ROW_INSERT, handler_id)
    
    def demonstrate_event_metrics(self):
        """Demonstrate event metrics and history."""
        print("\n=== Event Metrics ===")
        
        # Get metrics
        metrics = self.client.get_event_metrics()
        print(f"Events emitted: {metrics['events_emitted']}")
        print(f"Events handled: {metrics['events_handled']}")
        print(f"Errors caught: {metrics['errors_caught']}")
        print(f"Async handlers run: {metrics['async_handlers_run']}")
        
        print("\n=== Recent Event History ===")
        
        # Get recent history
        history = self.client.get_event_history(limit=5)
        for event, context in history:
            print(f"- {event.type.value}: {event.metadata.event_id[:8]}")
            if context.is_handled:
                print(f"  Handled by: {', '.join(context.handlers)}")
            if context.response_data:
                print(f"  Response: {context.response_data}")
    
    def demonstrate_custom_events(self):
        """Demonstrate custom event types and global event bus."""
        
        # Define handler for custom events
        def custom_handler(ctx: EventContext):
            event_type = ctx.event.data.get('custom_type', 'unknown')
            self.event_log.append(f"[CUSTOM] Received {event_type} event")
        
        # Register on global bus in custom namespace
        global_event_bus.on(
            EventType.CUSTOM,
            custom_handler,
            namespace="game_events"
        )
        
        # Emit custom game events
        for event_type in ["player_joined", "match_started", "power_up_collected"]:
            event = create_event(
                EventType.CUSTOM,
                {
                    "custom_type": event_type,
                    "player_id": 12345,
                    "timestamp": time.time()
                }
            )
            global_event_bus.emit(event, namespace="game_events")
    
    def print_event_log(self):
        """Print the collected event log."""
        print("\n=== Event Log ===")
        for entry in self.event_log:
            print(entry)


def main():
    """Run the event system example."""
    example = EventSystemExample()
    
    print("Advanced Event System Example")
    print("=============================\n")
    
    # 1. Simulate connection
    print("1. Simulating connection...")
    connection_event = create_event(
        EventType.CONNECTION_ESTABLISHED,
        {"host": "localhost", "port": 3000}
    )
    example.client.emit_event(connection_event)
    
    # 2. Simulate user activity
    print("\n2. Simulating user activity...")
    
    # User joins
    user_join_event = create_table_event(
        "users",
        "insert",
        {"id": 1, "name": "Alice", "email": "alice@example.com", "online": True}
    )
    example.client.emit_event(user_join_event)
    
    # User status change
    user_update_event = create_table_event(
        "users",
        "update",
        {"id": 1, "name": "Alice", "email": "alice@example.com", "online": False},
        old_row_data={"id": 1, "name": "Alice", "email": "alice@example.com", "online": True}
    )
    example.client.emit_event(user_update_event)
    
    # 3. Simulate reducer calls
    print("\n3. Simulating reducer calls...")
    
    # Successful reducer
    success_reducer = create_reducer_event(
        "send_message",
        "success",
        args={"text": "Hello, world!"},
        energy_used=50,
        execution_duration_nanos=1_500_000
    )
    success_reducer.type = EventType.REDUCER_SUCCESS
    example.client.emit_event(success_reducer)
    
    # Failed reducer
    error_reducer = create_reducer_event(
        "invalid_operation",
        "error",
        error_message="Permission denied",
        energy_used=10
    )
    error_reducer.type = EventType.REDUCER_ERROR
    example.client.emit_event(error_reducer)
    
    # 4. Demonstrate custom events
    print("\n4. Demonstrating custom events...")
    example.demonstrate_custom_events()
    
    # 5. Run async demonstration
    print("\n5. Running async handlers...")
    asyncio.run(example.demonstrate_async_handlers())
    
    # 6. Show metrics and history
    example.demonstrate_event_metrics()
    
    # 7. Print event log
    example.print_event_log()
    
    print("\n✅ Event system example complete!")


if __name__ == "__main__":
    main() 