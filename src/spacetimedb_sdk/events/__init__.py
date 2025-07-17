"""
Unified Event System for SpacetimeDB SDK

This module provides a consolidated event management system that unifies
all previous event systems into a single, powerful system.

Features:
- Unified EventType enum consolidating all previous event types
- Single UnifiedEventManager replacing all previous managers
- Backward compatibility layer for smooth migration
- Enhanced filtering and routing capabilities
- Async/sync handler support with thread pool integration
- Comprehensive metrics and monitoring
- Event context management with metadata
- Legacy compatibility for gradual migration

Migration Guide:
The old event systems (event_system.py, event_manager.py, events/enhanced_event_system.py)
have been consolidated. Use the legacy_compat module for backward compatibility during migration.

Key Changes:
- All EventType enums unified into single enum
- All event managers unified into UnifiedEventManager
- Consistent API across all event handling
- Enhanced performance and memory usage
- Better error isolation and debugging
"""

# Core unified event system
from .core_events import (
    # Core types and events
    Event,
    BaseEvent,
    EventType,
    EventPriority,
    EventMetadata,
    
    # Specific event types
    ConnectionEvent,
    AuthenticationEvent,
    SubscriptionEvent,
    TableEvent,
    ReducerEvent,
    TransactionEvent,
    MessageEvent,
    ErrorEvent,
    PerformanceEvent,
    
    # Event creation functions
    create_connection_event,
    create_table_event,
    create_reducer_event,
    create_error_event,
    create_performance_event,
)

# Event management
from .event_manager import (
    UnifiedEventManager,
    get_event_manager,
    set_event_manager,
    emit_event,
    emit_event_async,
    subscribe_to_events,
    EventMetrics as ManagerMetrics,
    HandlerInfo,
)

# Event context
from .event_context import (
    EventContext,
)

# Event filtering
from .event_filters import (
    EventFilter,
    TypeFilter,
    PriorityFilter,
    AgeFilter,
    SourceFilter,
    DataFilter,
    RegexFilter,
    CustomFilter,
    CompositeFilter,
    NotFilter,
    CommonFilters,
    
    # Filter creation functions
    type_filter,
    priority_filter,
    age_filter,
    source_filter,
    data_filter,
    regex_filter,
    custom_filter,
    and_filter,
    or_filter,
    not_filter,
)

# Legacy compatibility (with deprecation warnings)
from .legacy_compat import (
    # Legacy types for backward compatibility
    LegacyEventType,
    SDKEventType,
    EnhancedEventType,
    LegacyEventData,
    LegacySDKEventManager,
    LegacyEventEmitter,
    
    # Migration helpers
    map_legacy_to_unified,
    migrate_legacy_handlers,
    create_migration_guide,
    get_legacy_sdk_event_manager,
    get_legacy_event_emitter,
)

__all__ = [
    # Core unified system
    'Event',
    'BaseEvent',
    'EventType',
    'EventPriority',
    'EventMetadata',
    'EventContext',
    
    # Specific event types
    'ConnectionEvent',
    'AuthenticationEvent', 
    'SubscriptionEvent',
    'TableEvent',
    'ReducerEvent',
    'TransactionEvent',
    'MessageEvent',
    'ErrorEvent',
    'PerformanceEvent',
    
    # Event manager
    'UnifiedEventManager',
    'get_event_manager',
    'set_event_manager',
    'ManagerMetrics',
    'HandlerInfo',
    
    # Convenience functions
    'emit_event',
    'emit_event_async',
    'subscribe_to_events',
    'create_connection_event',
    'create_table_event',
    'create_reducer_event',
    'create_error_event',
    'create_performance_event',
    
    # Event filtering
    'EventFilter',
    'TypeFilter',
    'PriorityFilter',
    'AgeFilter',
    'SourceFilter',
    'DataFilter',
    'RegexFilter',
    'CustomFilter',
    'CompositeFilter',
    'NotFilter',
    'CommonFilters',
    'type_filter',
    'priority_filter',
    'age_filter',
    'source_filter',
    'data_filter',
    'regex_filter',
    'custom_filter',
    'and_filter',
    'or_filter',
    'not_filter',
    
    # Legacy compatibility (deprecated)
    'LegacyEventType',
    'SDKEventType',
    'EnhancedEventType',
    'LegacyEventData',
    'LegacySDKEventManager',
    'LegacyEventEmitter',
    'map_legacy_to_unified',
    'migrate_legacy_handlers',
    'create_migration_guide',
    'get_legacy_sdk_event_manager',
    'get_legacy_event_emitter',
]