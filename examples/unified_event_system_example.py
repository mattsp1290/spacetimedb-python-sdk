#!/usr/bin/env python3
"""
Unified Event System Example for SpacetimeDB SDK

This example demonstrates the new unified event system that consolidates
all previous event systems into a single, powerful system.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
import time
from typing import Any, Dict

# Import the unified event system
from spacetimedb_sdk.events import (
    # Core event system
    get_event_manager,
    EventType,
    Event,
    EventContext,
    EventPriority,
    
    # Specific event types
    ConnectionEvent,
    AuthenticationEvent,
    SubscriptionEvent,
    TableEvent,
    ReducerEvent,
    ErrorEvent,
    
    # Event creation helpers
    create_connection_event,
    create_table_event,
    create_reducer_event,
    emit_event,
    emit_event_async,
    subscribe_to_events,
    
    # Event filtering
    CommonFilters,
    type_filter,
    priority_filter,
    custom_filter,
    and_filter,
    
    # WebSocket integration
    get_websocket_integration,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpacetimeDBEventExample:
    """Example class demonstrating unified event system usage."""
    
    def __init__(self):
        self.event_manager = get_event_manager()
        self.websocket_integration = get_websocket_integration()
        self.handler_ids = []
        
        # Setup event handlers
        self.setup_event_handlers()
        
        # Setup event filters
        self.setup_event_filters()
    
    def setup_event_handlers(self):
        """Setup various event handlers to demonstrate the system."""
        
        # 1. Connection event handler
        def connection_handler(context: EventContext):
            event = context.event
            connection_id = event.get_context('connection_id', 'unknown')
            state = event.get_context('state', 'unknown')
            
            logger.info(f"Connection {connection_id} changed to state: {state}")
            
            # Demonstrate context usage
            context.set_response('handled_by', 'connection_handler')
            
            # Trigger follow-up events based on connection state
            if state == 'established':
                # Trigger authentication check
                auth_event = AuthenticationEvent(
                    identity=f"user_{connection_id}",
                    success=True
                )
                context.trigger_event(auth_event)
        
        # Register with high priority for connection events
        handler_id = self.event_manager.on(
            EventType.CONNECTION_ESTABLISHED,
            connection_handler,
            priority=10,
            handler_name="connection_state_handler"
        )
        self.handler_ids.append(handler_id)
        
        # 2. Authentication event handler  
        async def auth_handler(context: EventContext):
            """Async authentication handler."""
            event = context.event
            identity = event.get_context('identity')
            success = event.get_context('success', False)
            
            if success:
                logger.info(f"Authentication successful for {identity}")
                
                # Simulate async authentication processing
                await asyncio.sleep(0.1)
                
                # Set authentication result
                context.set_response('auth_status', 'verified')
            else:
                logger.warning(f"Authentication failed for {identity}")
                
                # Trigger error event
                error_event = ErrorEvent(
                    error_message=f"Authentication failed for {identity}",
                    error_type="AuthenticationError",
                    component="AuthenticationHandler"
                )
                context.trigger_event(error_event)
        
        handler_id = self.event_manager.on(
            EventType.AUTHENTICATION_SUCCESS,
            auth_handler,
            priority=5,
            handler_name="async_auth_handler"
        )
        self.handler_ids.append(handler_id)
        
        # 3. Database event handler using filtering
        def database_handler(context: EventContext):
            event = context.event
            
            if event.type == EventType.TABLE_ROW_INSERT:
                table_name = event.get_context('table_name', 'unknown')
                row_data = event.get_context('row_data', {})
                logger.info(f"New row inserted in {table_name}: {row_data}")
                
            elif event.type == EventType.TABLE_ROW_UPDATE:
                table_name = event.get_context('table_name', 'unknown')
                old_data = event.get_context('old_row_data', {})
                new_data = event.get_context('row_data', {})
                logger.info(f"Row updated in {table_name}: {old_data} -> {new_data}")
                
            elif event.type == EventType.TABLE_ROW_DELETE:
                table_name = event.get_context('table_name', 'unknown')
                row_data = event.get_context('row_data', {})
                logger.info(f"Row deleted from {table_name}: {row_data}")
        
        # Use convenience function for multiple event types
        handler_id = subscribe_to_events(
            database_handler,
            [EventType.TABLE_ROW_INSERT, EventType.TABLE_ROW_UPDATE, EventType.TABLE_ROW_DELETE],
            priority=0,
            handler_name="database_activity_handler"
        )
        self.handler_ids.append(handler_id)
        
        # 4. Error event handler with high priority
        def error_handler(context: EventContext):
            event = context.event
            error_message = event.get_context('error_message', 'Unknown error')
            error_type = event.get_context('error_type', 'UnknownError')
            component = event.get_context('component', 'Unknown')
            
            logger.error(f"Error in {component}: {error_type} - {error_message}")
            
            # Log error details for debugging
            context.set_response('error_logged', True)
            context.set_response('logged_at', time.time())
        
        handler_id = self.event_manager.on(
            EventType.ERROR_OCCURRED,
            error_handler,
            priority=20,  # High priority for error handling
            handler_name="error_logger"
        )
        self.handler_ids.append(handler_id)
        
        # 5. Wildcard handler for debugging (receives all events)
        def debug_handler(context: EventContext):
            if logger.isEnabledFor(logging.DEBUG):
                event = context.event
                logger.debug(f"Event: {event.type.value} from {event.metadata.source}")
        
        handler_id = self.event_manager.on(
            "*",  # Listen to all events
            debug_handler,
            priority=-10,  # Low priority to run last
            handler_name="debug_logger"
        )
        self.handler_ids.append(handler_id)
    
    def setup_event_filters(self):
        """Setup event filters to demonstrate filtering capabilities."""
        
        # 1. Filter out low priority events during high load
        def high_load_filter(event):
            # In a real scenario, check system load
            return event.priority.value >= EventPriority.NORMAL.value
        
        # Don't add this filter by default - it's just an example
        # self.event_manager.add_filter(custom_filter(high_load_filter, "high_load_filter"))
        
        # 2. Example of compound filter
        important_events_filter = and_filter(
            priority_filter(min_priority=EventPriority.HIGH),
            type_filter([
                EventType.CONNECTION_ERROR,
                EventType.AUTHENTICATION_FAILED,
                EventType.ERROR_OCCURRED
            ])
        )
        # Also not adding by default
        # self.event_manager.add_filter(important_events_filter)
    
    def demonstrate_basic_events(self):
        """Demonstrate basic event creation and emission."""
        logger.info("=== Demonstrating Basic Events ===")
        
        # 1. Connection events
        logger.info("1. Emitting connection events...")
        
        # Using specific event class
        connection_event = ConnectionEvent(
            connection_id="conn_12345",
            state="established",
            host="localhost",
            database="my_spacetimedb"
        )
        context = self.event_manager.emit(connection_event)
        logger.info(f"Connection event handled by: {context.handlers}")
        
        # 2. Table events
        logger.info("2. Emitting table events...")
        
        # User table insert
        user_insert = create_table_event(
            table_name="users",
            operation="insert",
            row_data={"id": 1, "name": "Alice", "email": "alice@example.com"}
        )
        self.event_manager.emit(user_insert)
        
        # User table update
        user_update = TableEvent(
            table_name="users", 
            operation="update",
            old_row_data={"id": 1, "name": "Alice", "email": "alice@example.com"},
            row_data={"id": 1, "name": "Alice Smith", "email": "alice.smith@example.com"}
        )
        self.event_manager.emit(user_update)
        
        # 3. Reducer events
        logger.info("3. Emitting reducer events...")
        
        reducer_event = create_reducer_event(
            reducer_name="create_user",
            status="success",
            args=[{"name": "Bob", "email": "bob@example.com"}],
            energy_used=50,
            execution_duration_nanos=1500000  # 1.5ms
        )
        self.event_manager.emit(reducer_event)
        
        # 4. Error events
        logger.info("4. Emitting error events...")
        
        error_event = ErrorEvent(
            error_message="Failed to connect to database",
            error_type="DatabaseConnectionError",
            component="DatabaseManager",
            recovery_action="retry_connection"
        )
        self.event_manager.emit(error_event)
    
    async def demonstrate_async_events(self):
        """Demonstrate async event handling."""
        logger.info("=== Demonstrating Async Events ===")
        
        # Setup async event handlers
        events_processed = []
        
        async def async_processor(context: EventContext):
            # Simulate async processing
            await asyncio.sleep(0.05)
            events_processed.append(context.event.type.value)
            logger.info(f"Async processed: {context.event.type.value}")
        
        # Register async handler
        handler_id = self.event_manager.on(
            EventType.SUBSCRIPTION_APPLIED,
            async_processor,
            handler_name="async_subscription_processor"
        )
        
        try:
            # Emit events asynchronously
            events_to_emit = [
                SubscriptionEvent(
                    query_id=f"query_{i}",
                    table_name="users",
                    operation="applied",
                    success=True
                )
                for i in range(3)
            ]
            
            # Emit all events
            tasks = []
            for event in events_to_emit:
                task = emit_event_async(event)
                tasks.append(task)
            
            # Wait for all events to be processed
            results = await asyncio.gather(*tasks)
            logger.info(f"Async event emission results: {results}")
            
            # Give handlers time to process
            await asyncio.sleep(0.2)
            
            logger.info(f"Events processed asynchronously: {events_processed}")
            
        finally:
            # Clean up
            self.event_manager.off(EventType.SUBSCRIPTION_APPLIED, handler_id)
    
    def demonstrate_websocket_integration(self):
        """Demonstrate WebSocket integration."""
        logger.info("=== Demonstrating WebSocket Integration ===")
        
        # Setup WebSocket event handlers
        def websocket_handler(context: EventContext):
            event = context.event
            if event.type.value.startswith('connection'):
                logger.info(f"WebSocket connection event: {event.type.value}")
            elif event.type.value.startswith('message'):
                logger.info(f"WebSocket message event: {event.type.value}")
        
        # Subscribe to WebSocket events
        handler_id = self.websocket_integration.on_connection_event(websocket_handler)
        
        try:
            # Simulate WebSocket events
            self.websocket_integration.emit_connection_opened(
                "ws_conn_123", "wss://spacetimedb.example.com", "my_database"
            )
            
            self.websocket_integration.emit_connection_established(
                "ws_conn_123", "wss://spacetimedb.example.com", "my_database"
            )
            
            # Simulate message events
            self.websocket_integration.emit_message_received(
                {"type": "DatabaseUpdate", "data": {"table": "users", "operation": "insert"}},
                "DatabaseUpdate"
            )
            
            self.websocket_integration.emit_identity_token_received(
                "auth_token_xyz", "user_alice"
            )
            
        finally:
            # Cleanup would normally be done by the integration
            pass
    
    def demonstrate_metrics_and_monitoring(self):
        """Demonstrate metrics and monitoring capabilities."""
        logger.info("=== Demonstrating Metrics and Monitoring ===")
        
        # Get current metrics
        metrics = self.event_manager.get_metrics()
        if metrics:
            logger.info("Event System Metrics:")
            logger.info(f"  Events Published: {metrics['events_published']}")
            logger.info(f"  Events Processed: {metrics['events_processed']}")
            logger.info(f"  Success Rate: {metrics['success_rate']:.1f}%")
            logger.info(f"  Handler Success Rate: {metrics['handler_success_rate']:.1f}%")
            logger.info(f"  Average Processing Time: {metrics['avg_processing_time_ms']:.2f}ms")
            logger.info(f"  Events by Type: {metrics['events_by_type']}")
        
        # Get event history
        history = self.event_manager.get_history(limit=5)
        logger.info(f"Recent Events (last 5):")
        for event, context in history:
            logger.info(f"  {event.type.value} at {time.ctime(event.metadata.timestamp)}")
    
    def demonstrate_legacy_compatibility(self):
        """Demonstrate legacy compatibility features."""
        logger.info("=== Demonstrating Legacy Compatibility ===")
        
        try:
            # Import legacy compatibility layer
            from spacetimedb_sdk.events.legacy_compat import (
                LegacySDKEventManager,
                map_legacy_to_unified,
                SDKEventType,
                LegacyEventType
            )
            
            # Show event type mapping
            legacy_type = SDKEventType.CONNECTION_OPENED
            unified_type = map_legacy_to_unified(legacy_type)
            logger.info(f"Legacy {legacy_type.value} maps to {unified_type.value}")
            
            # Use legacy manager (with deprecation warning)
            legacy_manager = LegacySDKEventManager("legacy_demo")
            
            def legacy_handler(event_data):
                logger.info(f"Legacy handler received: {event_data.event_type.value}")
            
            # Register legacy handler
            legacy_manager.register_handler(SDKEventType.CONNECTION_OPENED, legacy_handler)
            
            # Emit event through legacy manager
            legacy_manager.emit_event(
                SDKEventType.CONNECTION_OPENED,
                {"connection_id": "legacy_conn"},
                "LegacyClient"
            )
            
        except ImportError as e:
            logger.warning(f"Legacy compatibility not available: {e}")
    
    def cleanup(self):
        """Clean up event handlers and resources."""
        logger.info("Cleaning up event handlers...")
        
        # Remove all registered handlers
        for handler_id in self.handler_ids:
            # Try to remove from common event types
            for event_type in [EventType.CONNECTION_ESTABLISHED, EventType.AUTHENTICATION_SUCCESS, 
                              EventType.ERROR_OCCURRED]:
                try:
                    if self.event_manager.off(event_type, handler_id):
                        break
                except:
                    pass
            
            # Try wildcard removal
            try:
                self.event_manager.off("*", handler_id)
            except:
                pass
        
        self.handler_ids.clear()
        logger.info("Cleanup complete")


async def main():
    """Main example function."""
    logger.info("Starting SpacetimeDB Unified Event System Example")
    
    # Create example instance
    example = SpacetimeDBEventExample()
    
    try:
        # Run demonstrations
        example.demonstrate_basic_events()
        print()
        
        await example.demonstrate_async_events()
        print()
        
        example.demonstrate_websocket_integration()
        print()
        
        example.demonstrate_metrics_and_monitoring()
        print()
        
        example.demonstrate_legacy_compatibility()
        print()
        
        logger.info("Example completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)
    
    finally:
        # Clean up
        example.cleanup()
        
        # Shutdown event manager
        await example.event_manager.shutdown()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())