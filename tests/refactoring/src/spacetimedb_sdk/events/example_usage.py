"""
Example Usage of the Unified Event System

This module demonstrates how to use the unified event system with
various features including handlers, filters, WebSocket integration,
and legacy compatibility.
"""

import time
import asyncio
from typing import Dict, Any

from .core_events import EventType, EventContext, EventPriority
from .event_manager import UnifiedEventManager, EventManagerConfig
from .event_filters import (
    TypeFilter, SourceFilter, MetadataFilter, CompositeFilter,
    create_connection_filter, create_database_filter, create_error_filter
)
from .event_context import ContextBuilder, EventContextManager
from .websocket_integration import WebSocketEventIntegration, create_websocket_integration
from .legacy_compat import LegacyEventEmitter, migrate_legacy_handlers


def basic_usage_example():
    """Basic usage example of the unified event system."""
    print("=== Basic Usage Example ===")
    
    # Create event manager
    config = EventManagerConfig(
        enable_metrics=True,
        enable_batching=True,
        debug_mode=True
    )
    event_manager = UnifiedEventManager(config)
    
    # Define event handlers
    def on_connection_opened(context: EventContext):
        print(f"Connection opened: {context.get_metadata('connection_id')}")
    
    def on_message_received(context: EventContext):
        print(f"Message received: {context.data}")
    
    def on_system_error(context: EventContext):
        print(f"System error: {context.get_metadata('error')}")
    
    # Register handlers
    event_manager.add_handler(EventType.CONNECTION_OPENED, on_connection_opened)
    event_manager.add_handler(EventType.MESSAGE_RECEIVED, on_message_received)
    event_manager.add_handler(EventType.SYSTEM_ERROR, on_system_error, EventPriority.HIGH)
    
    # Create and emit events
    context1 = EventContext.create(
        event_type=EventType.CONNECTION_OPENED,
        source="websocket_client",
        connection_id="conn_123",
        url="ws://localhost:8080"
    )
    
    context2 = EventContext.create(
        event_type=EventType.MESSAGE_RECEIVED,
        source="websocket_client",
        data={"type": "chat", "message": "Hello, World!"}
    )
    
    context3 = EventContext.create(
        event_type=EventType.SYSTEM_ERROR,
        source="event_system",
        error="Connection timeout"
    )
    
    # Emit events
    event_manager.emit(EventType.CONNECTION_OPENED, context1)
    event_manager.emit(EventType.MESSAGE_RECEIVED, context2)
    event_manager.emit(EventType.SYSTEM_ERROR, context3)
    
    # Get metrics
    time.sleep(0.1)  # Allow handlers to execute
    metrics = event_manager.get_metrics()
    if metrics:
        print(f"Events emitted: {metrics.stats.events_emitted}")
        print(f"Handlers executed: {metrics.stats.handlers_executed}")
    
    event_manager.shutdown()


def advanced_filtering_example():
    """Advanced filtering example."""
    print("\n=== Advanced Filtering Example ===")
    
    event_manager = UnifiedEventManager()
    
    # Create filters
    connection_filter = create_connection_filter()
    error_filter = create_error_filter()
    websocket_filter = SourceFilter(["websocket_client"])
    
    # Composite filter for critical websocket connection errors
    critical_filter = CompositeFilter([
        connection_filter,
        error_filter,
        websocket_filter
    ], "AND")
    
    # Handler with filter
    def on_critical_websocket_error(context: EventContext):
        print(f"CRITICAL: WebSocket error - {context.get_metadata('error')}")
    
    event_manager.add_handler(
        EventType.CONNECTION_ERROR,
        on_critical_websocket_error,
        EventPriority.CRITICAL,
        critical_filter
    )
    
    # Regular handler without filter
    def on_any_connection_error(context: EventContext):
        print(f"Connection error: {context.get_metadata('error')}")
    
    event_manager.add_handler(
        EventType.CONNECTION_ERROR,
        on_any_connection_error,
        EventPriority.NORMAL
    )
    
    # Emit events
    websocket_error = EventContext.create(
        event_type=EventType.CONNECTION_ERROR,
        source="websocket_client",
        error="Connection refused"
    )
    
    database_error = EventContext.create(
        event_type=EventType.CONNECTION_ERROR,
        source="database_client",
        error="Database timeout"
    )
    
    event_manager.emit(EventType.CONNECTION_ERROR, websocket_error)
    event_manager.emit(EventType.CONNECTION_ERROR, database_error)
    
    time.sleep(0.1)
    event_manager.shutdown()


async def async_handlers_example():
    """Async handlers example."""
    print("\n=== Async Handlers Example ===")
    
    event_manager = UnifiedEventManager()
    
    # Async handler
    async def async_message_handler(context: EventContext):
        print(f"Processing message async: {context.data}")
        await asyncio.sleep(0.1)  # Simulate async processing
        print(f"Async processing complete for: {context.correlation_id}")
    
    # Sync handler
    def sync_message_handler(context: EventContext):
        print(f"Processing message sync: {context.data}")
    
    # Register handlers
    event_manager.add_handler(EventType.MESSAGE_RECEIVED, async_message_handler)
    event_manager.add_handler(EventType.MESSAGE_RECEIVED, sync_message_handler)
    
    # Emit event
    context = EventContext.create(
        event_type=EventType.MESSAGE_RECEIVED,
        source="test_client",
        data={"message": "Async test message"}
    )
    
    # Emit async
    future = event_manager.emit_async(EventType.MESSAGE_RECEIVED, context)
    await future
    
    time.sleep(0.2)  # Allow async handlers to complete
    event_manager.shutdown()


def context_management_example():
    """Context management example."""
    print("\n=== Context Management Example ===")
    
    # Create context manager
    context_manager = EventContextManager(pool_size=100)
    
    # Create contexts using builder pattern
    context1 = (ContextBuilder(EventType.CONNECTION_OPENED)
               .source("websocket_client")
               .data({"connection_id": "conn_123"})
               .metadata(user_id="user_456", session_id="session_789")
               .build())
    
    # Create child context
    context2 = context_manager.create_child_context(
        context1,
        EventType.MESSAGE_RECEIVED,
        data={"message": "Hello from child context"}
    )
    
    # Use managed context
    with context_manager.managed_context(
        EventType.DATABASE_ERROR,
        "database_client",
        data={"error": "Query timeout"}
    ) as context3:
        print(f"Processing context: {context3.correlation_id}")
        context_manager.mark_processed(context3, 0.05)
    
    # Get context chain
    chain = context_manager.get_context_chain(context2.correlation_id)
    print(f"Context chain length: {len(chain)}")
    
    # Get statistics
    stats = context_manager.get_stats()
    print(f"Contexts created: {stats['contexts_created']}")
    print(f"Contexts processed: {stats['contexts_processed']}")
    
    context_manager.clear()


def websocket_integration_example():
    """WebSocket integration example."""
    print("\n=== WebSocket Integration Example ===")
    
    # Create event manager
    event_manager = UnifiedEventManager()
    
    # Create WebSocket integration
    websocket_integration = create_websocket_integration(event_manager)
    
    # Handler for WebSocket events
    def on_websocket_event(context: EventContext):
        print(f"WebSocket event: {context.event_type.value}")
        print(f"Connection: {context.get_metadata('connection_id')}")
        if context.data:
            print(f"Data: {context.data}")
    
    # Register handler for all WebSocket events
    websocket_filter = SourceFilter(["websocket_client"])
    event_manager.add_handler(
        EventType.CONNECTION_OPENED,
        on_websocket_event,
        event_filter=websocket_filter
    )
    event_manager.add_handler(
        EventType.MESSAGE_RECEIVED,
        on_websocket_event,
        event_filter=websocket_filter
    )
    
    # Simulate WebSocket client
    class MockWebSocketClient:
        def __init__(self):
            self.on_open = None
            self.on_close = None
            self.on_message = None
            self.on_error = None
        
        def connect(self):
            if self.on_open:
                self.on_open()
        
        def receive_message(self, message):
            if self.on_message:
                self.on_message(message)
        
        def disconnect(self):
            if self.on_close:
                self.on_close()
    
    # Register mock client
    client = MockWebSocketClient()
    websocket_integration.register_websocket_client(
        client,
        "conn_123",
        "ws://localhost:8080",
        metadata={"user_id": "user_456"}
    )
    
    # Simulate WebSocket events
    client.connect()
    client.receive_message("Hello from WebSocket!")
    client.disconnect()
    
    # Get integration statistics
    stats = websocket_integration.get_integration_stats()
    print(f"WebSocket integration stats: {stats}")
    
    time.sleep(0.1)
    websocket_integration.cleanup()
    event_manager.shutdown()


def legacy_compatibility_example():
    """Legacy compatibility example."""
    print("\n=== Legacy Compatibility Example ===")
    
    # Create unified event manager
    event_manager = UnifiedEventManager()
    
    # Create legacy event emitter (compatibility layer)
    legacy_emitter = LegacyEventEmitter(event_manager)
    
    # Register legacy handlers
    legacy_emitter.on('connected', lambda: print("Legacy: Connected"))
    legacy_emitter.on('message_received', lambda data: print(f"Legacy: Message - {data}"))
    legacy_emitter.on('error', lambda error: print(f"Legacy: Error - {error}"))
    
    # Register new-style handlers
    def new_style_handler(context: EventContext):
        print(f"New style: {context.event_type.value} from {context.source}")
    
    event_manager.add_handler(EventType.CONNECTION_OPENED, new_style_handler)
    event_manager.add_handler(EventType.MESSAGE_RECEIVED, new_style_handler)
    event_manager.add_handler(EventType.SYSTEM_ERROR, new_style_handler)
    
    # Emit events using legacy interface
    legacy_emitter.emit('connected')
    legacy_emitter.emit('message_received', {"text": "Hello from legacy"})
    legacy_emitter.emit('error', "Legacy error occurred")
    
    # Emit events using new interface
    context = EventContext.create(
        event_type=EventType.CONNECTION_OPENED,
        source="new_client",
        connection_id="new_conn_123"
    )
    event_manager.emit(EventType.CONNECTION_OPENED, context)
    
    # Get legacy statistics
    legacy_stats = legacy_emitter.get_legacy_stats()
    print(f"Legacy stats: {legacy_stats}")
    
    time.sleep(0.1)
    event_manager.shutdown()


def migration_example():
    """Migration from legacy systems example."""
    print("\n=== Migration Example ===")
    
    # Simulate old handlers
    old_handlers = {
        'connected': [
            lambda: print("Old handler 1: Connected"),
            lambda: print("Old handler 2: Connected")
        ],
        'message_received': [
            lambda data: print(f"Old handler: Message - {data}")
        ],
        'error': [
            lambda error: print(f"Old handler: Error - {error}")
        ]
    }
    
    # Create unified event manager
    event_manager = UnifiedEventManager()
    
    # Migrate handlers
    migration_results = migrate_legacy_handlers(old_handlers, event_manager)
    print(f"Migration results: {migration_results}")
    
    # Test migrated handlers
    context1 = EventContext.create(
        event_type=EventType.CONNECTION_OPENED,
        source="migrated_client"
    )
    
    context2 = EventContext.create(
        event_type=EventType.MESSAGE_RECEIVED,
        source="migrated_client",
        data={"text": "Migrated message"}
    )
    
    event_manager.emit(EventType.CONNECTION_OPENED, context1)
    event_manager.emit(EventType.MESSAGE_RECEIVED, context2)
    
    time.sleep(0.1)
    event_manager.shutdown()


def performance_monitoring_example():
    """Performance monitoring example."""
    print("\n=== Performance Monitoring Example ===")
    
    # Create event manager with performance monitoring
    config = EventManagerConfig(
        enable_metrics=True,
        log_handler_performance=True,
        debug_mode=False
    )
    event_manager = UnifiedEventManager(config)
    
    # Create handlers with different performance characteristics
    def fast_handler(context: EventContext):
        pass  # Very fast handler
    
    def slow_handler(context: EventContext):
        time.sleep(0.01)  # Simulate slow processing
    
    def error_handler(context: EventContext):
        if context.get_metadata('should_error'):
            raise Exception("Simulated error")
    
    # Register handlers
    event_manager.add_handler(EventType.MESSAGE_RECEIVED, fast_handler)
    event_manager.add_handler(EventType.MESSAGE_RECEIVED, slow_handler)
    event_manager.add_handler(EventType.MESSAGE_RECEIVED, error_handler)
    
    # Emit many events
    for i in range(100):
        context = EventContext.create(
            event_type=EventType.MESSAGE_RECEIVED,
            source="performance_test",
            data={"message_id": i},
            should_error=(i % 10 == 0)  # Error every 10th message
        )
        event_manager.emit(EventType.MESSAGE_RECEIVED, context)
    
    time.sleep(0.5)  # Allow all handlers to complete
    
    # Get performance metrics
    metrics = event_manager.get_metrics()
    if metrics:
        health = metrics.get_system_health()
        print(f"System health: {health}")
        
        print(f"Events per second: {health['events_per_second']:.2f}")
        print(f"Average processing time: {health['average_processing_time']:.4f}s")
        print(f"Error rate: {health['error_rate']:.2f}%")
    
    event_manager.shutdown()


def comprehensive_example():
    """Comprehensive example showcasing all features."""
    print("\n=== Comprehensive Example ===")
    
    # Create advanced configuration
    config = EventManagerConfig(
        thread_pool_size=8,
        enable_batching=True,
        batch_size=50,
        enable_metrics=True,
        enable_memory_pooling=True,
        debug_mode=True
    )
    
    # Create event manager and integrations
    event_manager = UnifiedEventManager(config)
    websocket_integration = create_websocket_integration(event_manager)
    context_manager = EventContextManager(pool_size=500)
    
    # Create sophisticated filters
    critical_filter = CompositeFilter([
        create_error_filter(),
        MetadataFilter({"priority": "critical"})
    ], "AND")
    
    # Create handlers with different characteristics
    async def async_critical_handler(context: EventContext):
        print(f"CRITICAL ASYNC: {context.event_type.value}")
        await asyncio.sleep(0.001)  # Simulate async processing
    
    def sync_critical_handler(context: EventContext):
        print(f"CRITICAL SYNC: {context.event_type.value}")
    
    def performance_handler(context: EventContext):
        start_time = time.time()
        # Simulate processing
        time.sleep(0.001)
        duration = time.time() - start_time
        print(f"Processed {context.event_type.value} in {duration:.4f}s")
    
    # Register handlers with various configurations
    event_manager.add_handler(
        EventType.SYSTEM_ERROR,
        async_critical_handler,
        EventPriority.CRITICAL,
        critical_filter
    )
    
    event_manager.add_handler(
        EventType.CONNECTION_ERROR,
        sync_critical_handler,
        EventPriority.HIGH
    )
    
    # Register performance handler for all events
    for event_type in EventType:
        event_manager.add_handler(
            event_type,
            performance_handler,
            EventPriority.LOW
        )
    
    # Create and emit various events
    events = [
        EventContext.create(
            EventType.CONNECTION_OPENED,
            "websocket_client",
            connection_id="conn_001"
        ),
        EventContext.create(
            EventType.SYSTEM_ERROR,
            "system",
            error="Critical system failure",
            priority="critical"
        ),
        EventContext.create(
            EventType.MESSAGE_RECEIVED,
            "websocket_client",
            data={"message": "Important message"}
        ),
        EventContext.create(
            EventType.DATABASE_ERROR,
            "database_client",
            error="Query timeout"
        )
    ]
    
    # Emit events both sync and async
    for event in events:
        event_manager.emit(event.event_type, event)
    
    # Wait for processing
    time.sleep(0.2)
    
    # Get comprehensive statistics
    metrics = event_manager.get_metrics()
    if metrics:
        print(f"Final metrics: {metrics.get_system_health()}")
    
    websocket_stats = websocket_integration.get_integration_stats()
    print(f"WebSocket integration stats: {websocket_stats}")
    
    context_stats = context_manager.get_stats()
    print(f"Context manager stats: {context_stats}")
    
    # Cleanup
    websocket_integration.cleanup()
    context_manager.clear()
    event_manager.shutdown()


def main():
    """Run all examples."""
    print("SpacetimeDB Python SDK - Unified Event System Examples")
    print("=" * 60)
    
    # Run synchronous examples
    basic_usage_example()
    advanced_filtering_example()
    context_management_example()
    websocket_integration_example()
    legacy_compatibility_example()
    migration_example()
    performance_monitoring_example()
    comprehensive_example()
    
    # Run async example
    print("\n=== Running Async Example ===")
    asyncio.run(async_handlers_example())
    
    print("\n" + "=" * 60)
    print("All examples completed successfully!")


if __name__ == "__main__":
    main()