"""
SpacetimeDB SDK Event System Migration Examples

This file demonstrates how to migrate from the legacy event systems
to the modern unified event system.

Examples cover:
1. EventEmitter migration
2. SDKEventManager migration  
3. Event handler migration
4. Event creation migration
5. Best practices for new code
"""

import warnings
import asyncio
from typing import Dict, Any

# Suppress deprecation warnings for examples
warnings.filterwarnings("ignore", category=DeprecationWarning)

def example_1_event_emitter_migration():
    """
    Example 1: Migrating from EventEmitter to UnifiedEventManager
    """
    print("=== Example 1: EventEmitter Migration ===")
    
    # OLD WAY (DEPRECATED)
    print("\n--- OLD WAY (Deprecated) ---")
    from spacetimedb_sdk.event_system import EventEmitter, EventType, create_event
    
    # Create legacy event emitter
    old_emitter = EventEmitter("LegacyExample")
    
    # Register handler the old way
    def old_handler(context):
        print(f"Legacy handler received: {context.event_type}")
    
    handler_id = old_emitter.on(EventType.CONNECTION_ESTABLISHED, old_handler)
    
    # Emit event the old way
    event = create_event(EventType.CONNECTION_ESTABLISHED, {"status": "connected"})
    old_emitter.emit(event)
    
    print(f"Legacy handler registered with ID: {handler_id}")
    
    # NEW WAY (RECOMMENDED)
    print("\n--- NEW WAY (Recommended) ---")
    from spacetimedb_sdk.events import get_event_manager, EventType as ModernEventType, Event
    
    # Get modern event manager
    manager = get_event_manager()
    
    # Register handler the new way
    def modern_handler(context):
        print(f"Modern handler received: {context.event.type}")
    
    handler_id = manager.on(ModernEventType.CONNECTION_ESTABLISHED, modern_handler)
    
    # Create and emit event the new way
    event = Event(
        type=ModernEventType.CONNECTION_ESTABLISHED,
        data={"status": "connected"}
    )
    manager.emit(event)
    
    print(f"Modern handler registered with ID: {handler_id}")
    print()


def example_2_sdk_event_manager_migration():
    """
    Example 2: Migrating from SDKEventManager to UnifiedEventManager
    """
    print("=== Example 2: SDKEventManager Migration ===")
    
    # OLD WAY (DEPRECATED)
    print("\n--- OLD WAY (Deprecated) ---")
    from spacetimedb_sdk.event_manager import SDKEventManager, EventType as SDKEventType, EventData
    
    # Create legacy SDK event manager
    old_manager = SDKEventManager("LegacySDK")
    
    # Register handler the old way
    def old_sdk_handler(event_data):
        print(f"Legacy SDK handler: {event_data.event_type.value} from {event_data.source}")
    
    old_manager.register_handler(SDKEventType.CONNECTION_OPENED, old_sdk_handler)
    
    # Emit event the old way
    old_manager.emit_event(
        SDKEventType.CONNECTION_OPENED,
        {"connection_id": "conn123"},
        source="WebSocketClient"
    )
    
    # NEW WAY (RECOMMENDED)
    print("\n--- NEW WAY (Recommended) ---")
    from spacetimedb_sdk.events import get_event_manager, EventType, ConnectionEvent
    
    # Get modern event manager
    manager = get_event_manager()
    
    # Register handler the new way
    def modern_sdk_handler(context):
        print(f"Modern SDK handler: {context.event.type.value} from {context.event.metadata.source}")
    
    manager.on(EventType.CONNECTION_OPENED, modern_sdk_handler)
    
    # Create and emit event the new way (using specific event type)
    event = ConnectionEvent(
        connection_id="conn123",
        state="opened"
    )
    event.metadata.source = "WebSocketClient"
    manager.emit(event)
    print()


def example_3_event_handler_patterns():
    """
    Example 3: Event handler patterns - sync, async, and filtering
    """
    print("=== Example 3: Event Handler Patterns ===")
    
    from spacetimedb_sdk.events import (
        get_event_manager, EventType, Event, EventPriority,
        type_filter, priority_filter
    )
    
    manager = get_event_manager()
    
    # Synchronous handler
    def sync_handler(context):
        print(f"Sync handler: {context.event.type.value}")
    
    # Asynchronous handler
    async def async_handler(context):
        print(f"Async handler: {context.event.type.value}")
        await asyncio.sleep(0.01)  # Simulate async work
    
    # High priority handler
    def priority_handler(context):
        print(f"Priority handler (first): {context.event.type.value}")
    
    # Register handlers with different priorities
    manager.on(EventType.DATABASE_UPDATE, sync_handler, priority=0)
    manager.on(EventType.DATABASE_UPDATE, async_handler, priority=0)
    manager.on(EventType.DATABASE_UPDATE, priority_handler, priority=10)  # Higher priority = earlier
    
    # Add global filter for high priority events only
    high_priority_filter = priority_filter(EventPriority.HIGH)
    manager.add_filter(high_priority_filter)
    
    # Emit events with different priorities
    print("\n--- Normal Priority Event (filtered out) ---")
    normal_event = Event(
        type=EventType.DATABASE_UPDATE,
        data={"changes": 5},
        priority=EventPriority.NORMAL
    )
    manager.emit(normal_event)
    
    print("\n--- High Priority Event (processed) ---")
    high_event = Event(
        type=EventType.DATABASE_UPDATE,
        data={"critical_changes": 1},
        priority=EventPriority.HIGH
    )
    manager.emit(high_event)
    
    # Remove filter for next examples
    manager.remove_filter(high_priority_filter)
    print()


def example_4_event_creation_migration():
    """
    Example 4: Migrating event creation patterns
    """
    print("=== Example 4: Event Creation Migration ===")
    
    # OLD WAY (DEPRECATED)
    print("\n--- OLD WAY (Deprecated) ---")
    from spacetimedb_sdk.event_system import (
        create_reducer_event, create_table_event, EventType
    )
    
    # Create events the old way
    old_reducer_event = create_reducer_event("my_reducer", "success")
    old_table_event = create_table_event("users", "insert", {"id": 1, "name": "Alice"})
    
    print(f"Old reducer event: {old_reducer_event.reducer_name}")
    print(f"Old table event: {old_table_event.table_name}")
    
    # NEW WAY (RECOMMENDED)
    print("\n--- NEW WAY (Recommended) ---")
    from spacetimedb_sdk.events import (
        ReducerEvent, TableEvent, EventType, EventPriority
    )
    
    # Create events the new way (more explicit and flexible)
    new_reducer_event = ReducerEvent(
        reducer_name="my_reducer",
        status="success",
        energy_used=100,
        execution_duration_nanos=1000000
    )
    new_reducer_event.type = EventType.REDUCER_SUCCESS  # Set specific type
    new_reducer_event.priority = EventPriority.NORMAL
    
    new_table_event = TableEvent(
        table_name="users",
        operation="insert",
        row_data={"id": 1, "name": "Alice"},
        transaction_id="tx123"
    )
    
    print(f"New reducer event: {new_reducer_event.data['reducer_name']}")
    print(f"New table event: {new_table_event.data['table_name']}")
    
    # Modern way also supports metadata and correlation
    new_reducer_event.metadata.correlation_id = "request_abc"
    new_reducer_event.metadata.source = "ReducerProcessor"
    
    print(f"With metadata - correlation ID: {new_reducer_event.metadata.correlation_id}")
    print()


def example_5_best_practices_new_code():
    """
    Example 5: Best practices for new code using modern event system
    """
    print("=== Example 5: Best Practices for New Code ===")
    
    from spacetimedb_sdk.events import (
        get_event_manager, EventType, Event, EventPriority,
        ConnectionEvent, SubscriptionEvent, ErrorEvent,
        type_filter, source_filter
    )
    
    # Get the global event manager
    manager = get_event_manager()
    
    # 1. Use specific event types when possible
    connection_event = ConnectionEvent(
        connection_id="conn456",
        state="connected",
        host="localhost:3000",
        database="my_app"
    )
    
    # 2. Set appropriate priorities
    error_event = ErrorEvent(
        error_message="Database connection lost",
        error_type="ConnectionError",
        component="WebSocketClient",
        recovery_action="reconnect"
    )
    error_event.priority = EventPriority.HIGH  # Errors are high priority
    
    # 3. Use correlation IDs for request tracking
    subscription_event = SubscriptionEvent(
        query_id="q123",
        table_name="users",
        operation="subscribe",
        success=True
    )
    subscription_event.metadata.correlation_id = "user_request_789"
    
    # 4. Create focused event handlers
    def connection_handler(context):
        if context.event.data.get("state") == "connected":
            print(f"✓ Connected to {context.event.data.get('host')}")
        else:
            print(f"✗ Connection issue: {context.event.data}")
    
    def error_handler(context):
        error_msg = context.event.data.get("error_message")
        recovery = context.event.data.get("recovery_action")
        print(f"🚨 Error: {error_msg} (will {recovery})")
    
    # 5. Use filters for efficient processing
    connection_filter = type_filter(EventType.CONNECTION_ESTABLISHED, EventType.CONNECTION_LOST)
    error_filter = type_filter(EventType.ERROR_OCCURRED)
    
    # 6. Register handlers with appropriate priorities
    manager.on(EventType.CONNECTION_ESTABLISHED, connection_handler, priority=5)
    manager.on(EventType.CONNECTION_LOST, connection_handler, priority=5)
    manager.on(EventType.ERROR_OCCURRED, error_handler, priority=10)  # Handle errors first
    
    # 7. Emit events with proper context
    print("\n--- Processing Events ---")
    manager.emit(connection_event)
    manager.emit(subscription_event)
    manager.emit(error_event)
    
    # 8. Use async events for non-blocking operations
    async def async_example():
        async def async_processor(context):
            print(f"Async processing: {context.event.type.value}")
            await asyncio.sleep(0.01)  # Simulate async work
        
        manager.on(EventType.SUBSCRIPTION_APPLIED, async_processor)
        
        # Emit async
        await manager.emit_async(subscription_event)
        print("Async event emitted")
    
    # Run async example
    print("\n--- Async Event Processing ---")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create task if loop is already running
            loop.create_task(async_example())
        else:
            loop.run_until_complete(async_example())
    except RuntimeError:
        # No event loop available, skip async example
        print("(Async example skipped - no event loop)")
    
    print()


def example_6_migration_checklist():
    """
    Example 6: Migration checklist and common patterns
    """
    print("=== Example 6: Migration Checklist ===")
    
    migration_checklist = """
    ✅ MIGRATION CHECKLIST
    
    1. Replace imports:
       ❌ from spacetimedb_sdk.event_system import EventEmitter
       ✅ from spacetimedb_sdk.events import get_event_manager
       
    2. Replace event manager creation:
       ❌ emitter = EventEmitter("my_app")
       ✅ manager = get_event_manager()
       
    3. Update event type usage:
       ❌ from spacetimedb_sdk.event_system import EventType
       ✅ from spacetimedb_sdk.events import EventType
       
    4. Update event creation:
       ❌ event = create_event(EventType.CUSTOM, data)
       ✅ event = Event(type=EventType.CUSTOM, data=data)
       
    5. Update handler signatures:
       ❌ def handler(event_data: EventData):
       ✅ def handler(context: EventContext):
       
    6. Use specific event types:
       ❌ Generic Event with custom data
       ✅ ConnectionEvent, ReducerEvent, TableEvent, etc.
       
    7. Add proper error handling:
       ❌ No error context
       ✅ try/except with ErrorEvent emission
       
    8. Consider async patterns:
       ❌ Blocking event processing
       ✅ async def handler + await manager.emit_async()
       
    9. Use event filtering:
       ❌ Check event type in every handler
       ✅ Use type_filter, priority_filter, etc.
       
    10. Test with deprecation warnings enabled:
        ✅ Ensure no deprecated APIs are used
    """
    
    print(migration_checklist)


if __name__ == "__main__":
    """Run all migration examples"""
    print("SpacetimeDB SDK Event System Migration Examples")
    print("=" * 50)
    
    try:
        example_1_event_emitter_migration()
        example_2_sdk_event_manager_migration()
        example_3_event_handler_patterns()
        example_4_event_creation_migration()
        example_5_best_practices_new_code()
        example_6_migration_checklist()
        
        print("✅ All migration examples completed successfully!")
        print("\nFor more information, see:")
        print("- Modern event system: from spacetimedb_sdk.events import get_event_manager")
        print("- Migration guide: spacetimedb_sdk.events.legacy_compat.create_migration_guide()")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        print("This may be due to missing dependencies or import issues.")