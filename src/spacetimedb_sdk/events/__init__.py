"""
Enhanced Event System for SpacetimeDB SDK

Production-ready event management system extracted from blackholio-python-client
with SpacetimeDB-specific event types and advanced features.

Key Features:
- Hierarchical event types with priority-based processing
- Multi-layered filtering and middleware pipeline
- Async/sync handler support with thread pool integration
- Comprehensive metrics and monitoring capabilities
- Event lifecycle management with TTL and expiration
- Publisher/subscriber pattern with context management
- Error isolation and graceful degradation
- SpacetimeDB-specific event types for database operations

Event Types:
- CONNECTION: Connection state changes and network events
- AUTHENTICATION: Identity and token management events
- SUBSCRIPTION: Query subscription lifecycle events
- TABLE_UPDATE: Database table modification events
- REDUCER_CALL: Reducer function execution events
- TRANSACTION: Database transaction events
- QUERY: Database query execution events
- SYSTEM: System-level operation events
- ERROR: Error condition events
- DEBUG: Debug and diagnostic events
- PERFORMANCE: Performance monitoring events
"""

# Enhanced event system core
from .enhanced_event_system import (
    # Core types
    EventType,
    EventPriority,
    Event,
    EventT,
    
    # Filtering and metrics
    EventFilter,
    EventMetrics,
    
    # Handlers and subscribers
    EventHandler,
    AsyncEventHandler,
    SyncEventHandler,
    EventSubscriber,
    CallbackEventSubscriber,
    FilteredEventSubscriber,
    
    # Event manager
    EnhancedEventManager,
    
    # Convenience functions
    get_event_manager,
    event_context,
    publish_event,
    subscribe_to_events
)

# SpacetimeDB-specific events
from .spacetimedb_events import (
    # Event classes
    ConnectionEvent,
    AuthenticationEvent,
    SubscriptionEvent,
    TableUpdateEvent,
    ReducerCallEvent,
    TransactionEvent,
    QueryEvent,
    SystemEvent,
    ErrorEvent,
    DebugEvent,
    PerformanceEvent,
    
    # Convenience functions
    create_connection_event,
    create_table_update_event,
    create_reducer_call_event,
    create_error_event,
    create_performance_event
)

__all__ = [
    # Core types
    'EventType',
    'EventPriority',
    'Event',
    'EventT',
    
    # Filtering and metrics
    'EventFilter',
    'EventMetrics',
    
    # Handlers and subscribers
    'EventHandler',
    'AsyncEventHandler',
    'SyncEventHandler',
    'EventSubscriber',
    'CallbackEventSubscriber',
    'FilteredEventSubscriber',
    
    # Event manager
    'EnhancedEventManager',
    
    # Convenience functions
    'get_event_manager',
    'event_context',
    'publish_event',
    'subscribe_to_events',
    
    # SpacetimeDB-specific events
    'ConnectionEvent',
    'AuthenticationEvent',
    'SubscriptionEvent',
    'TableUpdateEvent',
    'ReducerCallEvent',
    'TransactionEvent',
    'QueryEvent',
    'SystemEvent',
    'ErrorEvent',
    'DebugEvent',
    'PerformanceEvent',
    
    # Event creation functions
    'create_connection_event',
    'create_table_update_event',
    'create_reducer_call_event',
    'create_error_event',
    'create_performance_event'
]