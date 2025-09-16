"""
SpacetimeDB Python SDK

Modern Python client library for SpacetimeDB with support for protocol v1.1.1.

Features:
- Modern WebSocket protocol support
- QueryId-based subscription management
- Enhanced connection lifecycle management
- Connection state tracking and metrics
- Connection event system
- Energy quota tracking
- Automatic reconnection
- Proper error handling
"""

from ._version import __version__

# SpacetimeDB client (protocol v1.1.1)
from .spacetimedb_client import (
    SpacetimeDBClient,
    ReducerEvent,
    DbEvent
)

# Protocol types
from .protocol import (
    TEXT_PROTOCOL,
    BIN_PROTOCOL,
    Identity,
    ConnectionId,
    CallReducerFlags,
    generate_request_id,
    ensure_enhanced_connection_id,
    ensure_enhanced_identity,
    EnergyQuanta,
    CallReducer,
    Subscribe,
    Unsubscribe,
    OneOffQuery,
    SubscribeSingleMessage,
    SubscribeMultiMessage,
    UnsubscribeMultiMessage,
    OneOffQueryMessage,
    IdentityToken,
    TransactionUpdate,
    TransactionUpdateLight,
    InitialSubscription,
    SubscribeApplied,
    UnsubscribeApplied,
    SubscriptionError,
    SubscribeMultiApplied,
    UnsubscribeMultiApplied,
    OneOffQueryResponse,
    ProtocolEncoder,
    ProtocolDecoder,
    Timestamp,
    TimeDuration
)

# Enhanced connection management
from .connection_id import (
    EnhancedConnectionId,
    EnhancedIdentity,
    EnhancedIdentityToken,
    ConnectionState as EnhancedConnectionState,
    ConnectionEventType,
    ConnectionEvent,
    ConnectionStateTracker,
    ConnectionLifecycleManager,
    ConnectionMetrics,
    ConnectionEventListener
)

# Energy management
from .energy import (
    EnergyError,
    OutOfEnergyError,
    EnergyExhaustedException,
    EnergyEventType,
    EnergyEvent,
    EnergyEventListener,
    EnergyOperation,
    EnergyUsageReport,
    EnergyTracker,
    EnergyBudgetManager,
    EnergyEventManager,
    EnergyCostEstimator,
    EnergyUsageAnalytics
)

# Query ID for subscription management
from .query_id import QueryId

# Request tracking for reducer calls
from .request_tracker import RequestTracker

# WebSocket client
from .websocket_client import (
    WebSocketClient,
    ConnectionState
)

# Address type (still needed from other modules)
from .protocol import Identity

# Async client
from .spacetimedb_async_client import SpacetimeDBAsyncClient

# Client cache
from .client_cache import ClientCache

# Local config functions (not a class)
from . import local_config

# Table interface exports
from .table_interface import (
    TableHandle,
    DatabaseInterface,
    TableEventProcessor,
    RowChange,
    ReducerEvent,
    CallbackManager,
    create_event_context
)

# Event System Exports
# 
# MODERN (RECOMMENDED): Use the unified events system
# from spacetimedb_sdk.events import get_event_manager, EventType, Event
#
# LEGACY (DEPRECATED): Old event system imports are deprecated but maintained for compatibility

# Modern unified event system (RECOMMENDED - USE THESE)
from .events import (
    # MODERN CORE SYSTEM - RECOMMENDED
    UnifiedEventManager,           # Replaces EventEmitter and SDKEventManager
    get_event_manager,            # Primary entry point for event management
    set_event_manager,            # For custom event manager setup
    
    # MODERN EVENTS - RECOMMENDED  
    Event,                        # Replaces legacy Event classes
    EventType,                    # Unified event type enum
    EventPriority,                # Event priority levels
    EventMetadata,                # Event metadata
    EventContext,                 # Event context for handlers
    
    # MODERN SPECIFIC EVENT TYPES - RECOMMENDED
    ConnectionEvent,              # Connection state events
    AuthenticationEvent,          # Authentication events  
    SubscriptionEvent,            # Subscription events
    TableEvent,                   # Table change events
    ReducerEvent,                 # Reducer call events
    TransactionEvent,             # Transaction events
    MessageEvent,                 # Message events
    ErrorEvent,                   # Error events
    PerformanceEvent,             # Performance monitoring events
    
    # MODERN EVENT CREATION - RECOMMENDED
    create_connection_event,      # Create connection events
    create_table_event,           # Create table events
    create_reducer_event,         # Create reducer events
    create_error_event,           # Create error events
    create_performance_event,     # Create performance events
    
    # MODERN CONVENIENCE FUNCTIONS - RECOMMENDED
    emit_event,                   # Emit events synchronously
    emit_event_async,             # Emit events asynchronously
    subscribe_to_events,          # Subscribe to multiple event types
    
    # MODERN EVENT FILTERING - RECOMMENDED
    EventFilter,                  # Base event filter
    type_filter,                  # Filter by event type
    priority_filter,              # Filter by priority
    source_filter,                # Filter by source
    
    # LEGACY COMPATIBILITY (DEPRECATED)
    # These provide backward compatibility but show deprecation warnings
    LegacyEventEmitter,           # DEPRECATED: Use UnifiedEventManager
    LegacySDKEventManager,        # DEPRECATED: Use UnifiedEventManager
    LegacyEventType,              # DEPRECATED: Use EventType
    LegacyEventData,              # DEPRECATED: Use Event
    # LegacyEventContext,           # DEPRECATED: Use EventContext - commented out due to import issue
    
    # Legacy aliases for backward compatibility
    LegacyEventEmitter as EventEmitter,  # DEPRECATED
    LegacyEventType as LegacyEventTypeAlias,  # DEPRECATED
)

# Additional legacy compatibility - these redirect to modern system with warnings
from .event_system import (
    global_event_bus,             # DEPRECATED: Use get_event_manager()
    create_event,                 # DEPRECATED: Use Event() constructor
    subscribe_to_raw_events,      # DEPRECATED: Use manager.on()
    ReducerEvent as AdvancedReducerEvent,  # DEPRECATED: Use ReducerEvent from events
)

from .event_manager import (
    SDKEventManager,              # DEPRECATED: Use UnifiedEventManager  
    EventType as SDKEventType,    # DEPRECATED: Use EventType from events
    EventData,                    # DEPRECATED: Use Event from events
    get_event_manager as get_sdk_event_manager,  # DEPRECATED: Use get_event_manager from events
    set_event_manager as set_sdk_event_manager,  # DEPRECATED: Use set_event_manager from events
)

# JSON API exports
from .json_api import (
    SpacetimeDBJsonAPI,
    ApiResponse,
    DatabaseInfo,
    ModuleInfo,
    ReducerCallResult,
    HttpMethod
)

# Algebraic type system exports
from .algebraic_type import (
    TypeKind,
    AlgebraicType,
    BoolType,
    IntType,
    FloatType,
    StringType,
    BytesType,
    ProductType,
    SumType,
    ArrayType,
    MapType,
    OptionType,
    IdentityType,
    AddressType,
    TimestampType,
    FieldInfo,
    VariantInfo,
    TypeValidator,
    TypeConverter,
    TypeBuilder,
    TypeRegistry,
    RefType,
    type_builder,
    validate_value,
    serialize_value,
    deserialize_value
)

from .algebraic_value import (
    AlgebraicValue,
    bool_value,
    u8_value,
    u16_value,
    u32_value,
    u64_value,
    i8_value,
    i16_value,
    i32_value,
    i64_value,
    f32_value,
    f64_value,
    string_value,
    bytes_value
)

# Testing infrastructure
# Import from .testing module directly when needed for tests
# This avoids circular imports and keeps test utilities separate from main package

# Test fixtures should not be imported in main package - import directly when needed
# from spacetimedb_sdk.testing import (...) when writing tests

# Logger integration
from .logger import (
    LogLevel,
    LogContext,
    LogFormatter,
    JSONFormatter,
    TextFormatter,
    ColoredTextFormatter,
    LogHandler,
    ConsoleHandler,
    FileHandler,
    MemoryHandler,
    SamplingHandler,
    SpacetimeDBLogger,
    logger,
    configure_default_logging,
    get_logger
)

# WASM integration
from .wasm_integration import (
    SpacetimeDBConfig,
    SpacetimeDBServer,
    WASMModule,
    WASMTestHarness,
    PerformanceBenchmark,
    find_sdk_test_module,
    require_spacetimedb,
    require_sdk_test_module
)

# Connection builder and pooling
from .connection_builder import SpacetimeDBConnectionBuilder
from .connection_pool import ConnectionPool, LoadBalancedConnectionManager
from .shared_types import RetryPolicy

# DbContext
from .db_context import (
    DbContext,
    DbView,
    Reducers,
    SetReducerFlags,
    TableProtocol,
    ReducerProtocol,
    TableAccessor,
    ReducerAccessor,
    create_db_context,
    DbContextBuilder,
    GeneratedDbView,
    GeneratedReducers,
    TypedDbContext
)

# RemoteModule system
from .remote_module import (
    RemoteModule,
    TableMetadata,
    ReducerMetadata,
    SpacetimeModule,
    GeneratedModule,
    DynamicModule,
    ModuleConstructors,
    EventContextConstructor,
    DbViewConstructor,
    ReducersConstructor,
    SetReducerFlagsConstructor,
    ModuleIntrospector,
    ModuleRegistry,
    get_module_registry,
    register_module,
    get_module
)

# Subscription builder
from .subscription_builder import (
    AdvancedSubscriptionBuilder,
    AdvancedSubscription,
    SubscriptionStrategy,
    SubscriptionState,
    SubscriptionError,
    SubscriptionMetrics,
    RetryPolicy as SubscriptionRetryPolicy  # Aliased to avoid conflict with shared_types.RetryPolicy
)

# BSATN serialization
from .bsatn import (
    # Core classes
    BsatnWriter,
    BsatnReader,
    # Exceptions
    BsatnError,
    BsatnInvalidTagError,
    BsatnBufferTooSmallError,
    BsatnInvalidUTF8Error,
    BsatnOverflowError,
    BsatnInvalidFloatError,
    BsatnTooLargeError,
    # Utility functions
    encode,
    decode,
    encode_to_writer,
    decode_from_reader,
    # SpacetimeDB types
    SpacetimeDBIdentity,
    SpacetimeDBAddress,
    SpacetimeDBConnectionId,
    SpacetimeDBTimestamp,
    SpacetimeDBTimeDuration,
)

# Time utilities and scheduling
from .time_utils import (
    EnhancedTimestamp,
    EnhancedTimeDuration,
    ScheduleAt,
    ScheduleAtTime,
    ScheduleAtInterval,
    TimeRange,
    TimeUnit,
    PrecisionTimer,
    TimeMetrics,
    duration_from_seconds,
    duration_from_minutes,
    duration_from_hours,
    duration_from_days,
    timestamp_now,
    timestamp_from_iso
)

from .scheduling import (
    ReducerScheduler,
    ScheduledReducerCall,
    ScheduleResult,
    ScheduleStatus,
    SchedulerError,
    ScheduleNotFoundError,
    ScheduleValidationError,
    schedule_once,
    schedule_repeating,
    schedule_at
)

# Advanced utilities
from .utils import (
    # Enums
    IdentityFormat,
    URIScheme,
    
    # Classes
    ParsedURI,
    RequestIdGenerator,
    IdentityFormatter,
    ConnectionIdFormatter,
    URIParser,
    DataConverter,
    SchemaIntrospector,
    ConnectionDiagnostics,
    PerformanceProfiler,
    ConfigurationManager,
    
    # Convenience functions
    format_identity,
    parse_identity,
    format_connection_id,
    parse_connection_id,
    parse_uri,
    validate_spacetimedb_uri,
    normalize_uri,
    generate_request_id,
    bytes_to_human_readable,
    duration_to_human_readable,
    test_connection_latency,
    get_system_info,
    
    # Global instances
    request_id_generator,
    performance_profiler
)

# Enhanced Interfaces (extracted from blackholio-python-client patterns)
from .interfaces import (
    ConnectionInterface,
    ConnectionState,
    AuthInterface,
    SubscriptionInterface,
    ReducerInterface,
    SpacetimeDBClientInterface
)

# Enhanced Connection Management (extracted from blackholio-python-client patterns)
from .connection import (
    PoolState,
    HealthStatus,
    ConnectionMetrics,
    PoolConfiguration,
    PooledConnection,
    ServerConfig,
    ConnectionPool,
    EnhancedConnectionManager,
    get_connection_manager,
    get_connection as get_pooled_connection
)

# Enhanced Event System (extracted from blackholio-python-client patterns)
# Import events with fallback for compatibility during development
try:
    from .events import (
        # Core event system
        EventType,
        EventPriority,
        Event,
        SubscriptionEvent,
    )
    # Try to import optional components
    try:
        from .events import (
            EventFilter,
            EventMetrics,
            EventHandler,
            AsyncEventHandler,
            SyncEventHandler,
            EventSubscriber,
            CallbackEventSubscriber,
            FilteredEventSubscriber,
            EnhancedEventManager,
            get_event_manager,
            event_context,
            publish_event,
            subscribe_to_events,
        )
    except ImportError:
        # These are optional
        pass
        
    try:
        from .events import (
            ConnectionEvent,
            AuthenticationEvent,
            TableUpdateEvent,
            ReducerCallEvent,
            TransactionEvent,
            QueryEvent,
            SystemEvent,
            ErrorEvent,
            DebugEvent,
            PerformanceEvent,
            create_connection_event,
            create_table_update_event,
            create_reducer_call_event,
            create_error_event,
            create_performance_event
        )
    except ImportError:
        # These are optional
        pass
        
except ImportError as e:
    # Fallback for compatibility - minimal event system
    print(f"Warning: Event system import failed ({e}), using minimal fallback")
    
    class EventType:
        SUBSCRIPTION = "subscription"
        CONNECTION = "connection"
    
    class EventPriority:
        MEDIUM = "medium"
        HIGH = "high"
        LOW = "low"
    
    class Event:
        def __init__(self, **kwargs): pass
    
    class SubscriptionEvent(Event):
        def __init__(self, **kwargs): 
            super().__init__(**kwargs)
            for k, v in kwargs.items():
                setattr(self, k, v)

# Authentication storage (using modern secure implementation)
from .auth.storage import (
    AuthCredentials,
    SecureAuthStorage as SpacetimeDBAuthStorage,
)

# Global instance for backward compatibility
from .auth.storage import SecureAuthStorage
_global_auth_storage = None

def get_global_auth_storage():
    """Get the global authentication storage instance."""
    global _global_auth_storage
    if _global_auth_storage is None:
        _global_auth_storage = SecureAuthStorage()
    return _global_auth_storage

def store_credentials(identity: str, token: str, host: str, database: str) -> None:
    """Store authentication credentials using modern secure storage."""
    storage = get_global_auth_storage()
    storage.store_credentials(identity, token, host, database)

def get_credentials(host: str, database: str, allow_expired: bool = False):
    """Get authentication credentials using modern secure storage."""
    storage = get_global_auth_storage()
    return storage.get_credentials(host, database, allow_expired)

def remove_credentials(host: str, database: str) -> bool:
    """Remove authentication credentials using modern secure storage."""
    storage = get_global_auth_storage()
    return storage.remove_credentials(host, database)

def clear_all_credentials() -> None:
    """Clear all authentication credentials using modern secure storage."""
    storage = get_global_auth_storage()
    storage.clear_all_credentials()

# Enhanced Factory Pattern for multi-server language support
from .factory import (
    SpacetimeDBClientFactory,
    SpacetimeDBClientFactoryBase,
    SpacetimeDBFactoryRegistry,
    RustOptimizedFactory,
    PythonOptimizedFactory,
    CSharpOptimizedFactory,
    GoOptimizedFactory,
    create_spacetimedb_client,
    get_spacetimedb_factory,
    list_supported_languages,
    get_language_info,
    create_optimized_client,
    # Convenience functions for each language
    create_rust_client,
    create_python_client,
    create_csharp_client,
    create_go_client,
    # Additional utilities
    get_recommended_config,
    validate_server_compatibility,
    get_optimization_capabilities
)

# Data structures
from .data_structures import (
    OperationsMap, IdentityCollection, ConnectionIdCollection, QueryIdCollection,
    ConcurrentSet, LRUCache, CollectionManager, CollectionStrategy,
    CollectionMetrics, Equalable, collection_manager,
    create_operations_map, create_identity_collection, create_connection_id_collection,
    create_query_id_collection, create_concurrent_set, create_lru_cache,
    get_collection, get_all_metrics
)

# Cross-platform validation
from .cross_platform_validation import (
    PlatformType,
    ArchitectureType,
    EnvironmentType,
    NetworkCondition,
    SystemInfo,
    ValidationResult,
    NetworkSimulator,
    PlatformValidator,
    CrossPlatformTestSuite
)

# Subscription data flow fixes (addressing bug report issues)
from .connection.subscription_manager import (
    SubscriptionManager,
    SubscriptionState,
    SubscriptionInfo,
    get_subscription_manager,
    set_subscription_manager
)

# Legacy event manager compatibility (deprecated)
from .events import (
    # Use UnifiedEventManager instead of these legacy imports
    LegacySDKEventManager as SDKEventManager,
    SDKEventType,
    LegacyEventData as EventData,
    get_legacy_sdk_event_manager as get_sdk_event_manager,
    set_event_manager as set_sdk_event_manager
)

from .serialization import (
    _safe_extract,
    _get_message_type,
    _handle_database_update,
    _handle_subscription_update,
    serialize_for_client,
    prepare_message_for_client,
    ensure_dict_compatible,
    validate_serialization,
    ClientCompatibilityWrapper,
    wrap_for_client_compatibility
)

__all__ = [
    # Version
    "__version__",
    
    # SpacetimeDB client (recommended)
    "SpacetimeDBClient",
    "ReducerEvent",
    "DbEvent",
    
    # Protocol
    "TEXT_PROTOCOL",
    "BIN_PROTOCOL",
    "Identity",
    "ConnectionId", 
    "QueryId",
    "RequestTracker",
    "CallReducerFlags",
    "generate_request_id",
    "ensure_enhanced_connection_id",
    "ensure_enhanced_identity",
    "EnergyQuanta",
    "CallReducer",
    "Subscribe",
    "Unsubscribe",
    "OneOffQuery",
    "SubscribeSingleMessage",
    "SubscribeMultiMessage",
    "UnsubscribeMultiMessage",
    "OneOffQueryMessage",
    "IdentityToken",
    "TransactionUpdate",
    "TransactionUpdateLight",
    "InitialSubscription",
    "SubscribeApplied",
    "UnsubscribeApplied",
    "SubscriptionError",
    "SubscribeMultiApplied",
    "UnsubscribeMultiApplied",
    "OneOffQueryResponse",
    "ProtocolEncoder",
    "ProtocolDecoder",
    "Timestamp",
    "TimeDuration",
    
    # Enhanced connection management
    "EnhancedConnectionId",
    "EnhancedIdentity",
    "EnhancedIdentityToken",
    "EnhancedConnectionState",
    "ConnectionEventType",
    "ConnectionEvent",
    "ConnectionStateTracker",
    "ConnectionLifecycleManager",
    "ConnectionMetrics",
    "ConnectionEventListener",
    
    # WebSocket
    "WebSocketClient",
    "ConnectionState",
    

    
    # Async
    "SpacetimeDBAsyncClient",
    
    # Utilities
    "ClientCache",
    "local_config",
    
    # Energy management
    "EnergyError",
    "OutOfEnergyError",
    "EnergyExhaustedException",
    "EnergyEventType",
    "EnergyEvent",
    "EnergyEventListener",
    "EnergyOperation",
    "EnergyUsageReport",
    "EnergyTracker",
    "EnergyBudgetManager",
    "EnergyEventManager",
    "EnergyCostEstimator",
    "EnergyUsageAnalytics",
    
    # Table interface
    "TableHandle",
    "DatabaseInterface", 
    "TableEventProcessor",
    "RowChange",
    "ReducerEvent",
    "CallbackManager",
    "create_event_context",
    
    # ====================================================================
    # EVENT SYSTEM EXPORTS
    # ====================================================================
    # 
    # MODERN (RECOMMENDED): Use these for new code
    # from spacetimedb_sdk.events import get_event_manager, EventType, Event
    # 
    # LEGACY (DEPRECATED): These are maintained for compatibility but deprecated
    # 
    
    # MODERN EVENT SYSTEM (RECOMMENDED - USE THESE)
    "UnifiedEventManager",        # RECOMMENDED: Use instead of EventEmitter/SDKEventManager
    "get_event_manager",          # RECOMMENDED: Primary entry point
    "set_event_manager",          # RECOMMENDED: For custom setup
    
    # MODERN EVENT TYPES (RECOMMENDED)
    "Event",                      # RECOMMENDED: Modern event class
    "EventType",                  # RECOMMENDED: Unified event type enum
    "EventPriority",              # RECOMMENDED: Event priority levels
    "EventMetadata",              # RECOMMENDED: Event metadata
    "EventContext",               # RECOMMENDED: Event context for handlers
    
    # MODERN SPECIFIC EVENTS (RECOMMENDED)
    "ConnectionEvent",            # RECOMMENDED: Connection state events
    "AuthenticationEvent",        # RECOMMENDED: Authentication events
    "SubscriptionEvent",          # RECOMMENDED: Subscription events
    "TableEvent",                 # RECOMMENDED: Table change events
    "ReducerEvent",               # RECOMMENDED: Reducer call events
    "TransactionEvent",           # RECOMMENDED: Transaction events
    "MessageEvent",               # RECOMMENDED: Message events
    "ErrorEvent",                 # RECOMMENDED: Error events
    "PerformanceEvent",           # RECOMMENDED: Performance events
    
    # MODERN EVENT FUNCTIONS (RECOMMENDED)
    "emit_event",                 # RECOMMENDED: Emit events synchronously
    "emit_event_async",           # RECOMMENDED: Emit events asynchronously
    "subscribe_to_events",        # RECOMMENDED: Subscribe to multiple events
    "create_connection_event",    # RECOMMENDED: Create connection events
    "create_table_event",         # RECOMMENDED: Create table events
    "create_reducer_event",       # RECOMMENDED: Create reducer events
    "create_error_event",         # RECOMMENDED: Create error events
    "create_performance_event",   # RECOMMENDED: Create performance events
    
    # MODERN EVENT FILTERING (RECOMMENDED)
    "EventFilter",                # RECOMMENDED: Event filtering
    "type_filter",                # RECOMMENDED: Filter by type
    "priority_filter",            # RECOMMENDED: Filter by priority
    "source_filter",              # RECOMMENDED: Filter by source
    
    # LEGACY EVENT SYSTEM (DEPRECATED - Use modern system above)
    "EventEmitter",               # DEPRECATED: Use UnifiedEventManager
    "SDKEventManager",            # DEPRECATED: Use UnifiedEventManager
    "AdvancedReducerEvent",       # DEPRECATED: Use ReducerEvent
    "create_event",               # DEPRECATED: Use Event() constructor
    "subscribe_to_raw_events",    # DEPRECATED: Use manager.on()
    "global_event_bus",           # DEPRECATED: Use get_event_manager()
    "SDKEventType",               # DEPRECATED: Use EventType
    "EventData",                  # DEPRECATED: Use Event
    "get_sdk_event_manager",      # DEPRECATED: Use get_event_manager
    "set_sdk_event_manager",      # DEPRECATED: Use set_event_manager
    
    # JSON API
    "SpacetimeDBJsonAPI",
    "ApiResponse",
    "DatabaseInfo",
    "ModuleInfo",
    "ReducerCallResult",
    "HttpMethod",
    
    # Algebraic type system
    "TypeKind",
    "AlgebraicType",
    "BoolType",
    "IntType",
    "FloatType",
    "StringType",
    "BytesType",
    "ProductType",
    "SumType",
    "ArrayType",
    "MapType",
    "OptionType",
    "IdentityType",
    "AddressType",
    "TimestampType",
    "FieldInfo",
    "VariantInfo",
    "TypeValidator",
    "TypeConverter",
    "TypeBuilder",
    "TypeRegistry",
    "RefType",
    "type_builder",
    "validate_value",
    "serialize_value",
    "deserialize_value",
    
    # Algebraic value system
    "AlgebraicValue",
    "bool_value",
    "u8_value",
    "u16_value",
    "u32_value",
    "u64_value",
    "i8_value",
    "i16_value",
    "i32_value",
    "i64_value",
    "f32_value",
    "f64_value",
    "string_value",
    "bytes_value",
    
    # Testing infrastructure removed - import directly when needed:
    # from spacetimedb_sdk.testing import MockSpacetimeDBConnection, etc.
    # from spacetimedb_sdk.testing import TestDatabase, TestIsolation, etc.
    
    # Logger integration
    "LogLevel",
    "LogContext",
    "LogFormatter",
    "JSONFormatter",
    "TextFormatter", 
    "ColoredTextFormatter",
    "LogHandler",
    "ConsoleHandler",
    "FileHandler",
    "MemoryHandler",
    "SamplingHandler",
    "SpacetimeDBLogger",
    "logger",
    "configure_default_logging",
    "get_logger",
    
    # WASM integration
    "SpacetimeDBConfig",
    "SpacetimeDBServer",
    "WASMModule",
    "WASMTestHarness",
    "PerformanceBenchmark",
    "find_sdk_test_module",
    "require_spacetimedb",
    "require_sdk_test_module",
    
    # Connection builder and pooling
    "SpacetimeDBConnectionBuilder",
    "ConnectionPool",
    "LoadBalancedConnectionManager",
    
    # DbContext
    "DbContext",
    "DbView",
    "Reducers",
    "SetReducerFlags",
    "TableProtocol",
    "ReducerProtocol",
    "TableAccessor",
    "ReducerAccessor",
    "create_db_context",
    "DbContextBuilder",
    "GeneratedDbView",
    "GeneratedReducers",
    "TypedDbContext",
    
    # RemoteModule system
    "RemoteModule",
    "TableMetadata",
    "ReducerMetadata",
    "SpacetimeModule",
    "GeneratedModule",
    "DynamicModule",
    "ModuleConstructors",
    "EventContextConstructor",
    "DbViewConstructor",
    "ReducersConstructor",
    "SetReducerFlagsConstructor",
    "ModuleIntrospector",
    "ModuleRegistry",
    "get_module_registry",
    "register_module",
    "get_module",
    
    # Subscription builder
    "AdvancedSubscriptionBuilder",
    "AdvancedSubscription",
    "SubscriptionStrategy",
    "SubscriptionState",
    "SubscriptionError",
    "SubscriptionMetrics",
    "RetryPolicy",
    
    # BSATN serialization
    "BsatnWriter",
    "BsatnReader",
    "BsatnError",
    "BsatnInvalidTagError",
    "BsatnBufferTooSmallError",
    "BsatnInvalidUTF8Error",
    "BsatnOverflowError",
    "BsatnInvalidFloatError",
    "BsatnTooLargeError",
    "encode",
    "decode",
    "encode_to_writer",
    "decode_from_reader",
    "SpacetimeDBIdentity",
    "SpacetimeDBAddress",
    "SpacetimeDBConnectionId",
    "SpacetimeDBTimestamp",
    "SpacetimeDBTimeDuration",
    
    # Time utilities and scheduling
    "EnhancedTimestamp",
    "EnhancedTimeDuration",
    "ScheduleAt",
    "ScheduleAtTime",
    "ScheduleAtInterval",
    "TimeRange",
    "TimeUnit",
    "PrecisionTimer",
    "TimeMetrics",
    "duration_from_seconds",
    "duration_from_minutes",
    "duration_from_hours",
    "duration_from_days",
    "timestamp_now",
    "timestamp_from_iso",
    "ReducerScheduler",
    "ScheduledReducerCall",
    "ScheduleResult",
    "ScheduleStatus",
    "SchedulerError",
    "ScheduleNotFoundError",
    "ScheduleValidationError",
    "schedule_once",
    "schedule_repeating",
    "schedule_at",
    
    # Advanced utilities
    "IdentityFormat",
    "URIScheme",
    "ParsedURI",
    "RequestIdGenerator",
    "IdentityFormatter",
    "ConnectionIdFormatter",
    "URIParser",
    "DataConverter",
    "SchemaIntrospector",
    "ConnectionDiagnostics",
    "PerformanceProfiler",
    "ConfigurationManager",
    "format_identity",
    "parse_identity",
    "format_connection_id",
    "parse_connection_id",
    "parse_uri",
    "validate_spacetimedb_uri",
    "normalize_uri",
    "bytes_to_human_readable",
    "duration_to_human_readable",
    "test_connection_latency",
    "get_system_info",
    "request_id_generator",
    "performance_profiler",
    
    # Data structures
    "OperationsMap",
    "IdentityCollection",
    "ConnectionIdCollection",
    "QueryIdCollection",
    "ConcurrentSet",
    "LRUCache",
    "CollectionManager",
    "CollectionStrategy",
    "CollectionMetrics",
    "Equalable",
    "collection_manager",
    "create_operations_map",
    "create_identity_collection",
    "create_connection_id_collection",
    "create_query_id_collection",
    "create_concurrent_set",
    "create_lru_cache",
    "get_collection",
    "get_all_metrics",
    
    # Cross-platform validation
    "PlatformType",
    "ArchitectureType",
    "EnvironmentType",
    "NetworkCondition",
    "SystemInfo",
    "ValidationResult",
    "NetworkSimulator",
    "PlatformValidator",
    "CrossPlatformTestSuite",
    
    # Authentication storage
    "AuthCredentials",
    "SpacetimeDBAuthStorage", 
    "get_global_auth_storage",
    "store_credentials",
    "get_credentials",
    "remove_credentials",
    "clear_all_credentials",
    
    # Enhanced Interfaces (extracted from blackholio-python-client patterns)
    "ConnectionInterface",
    "ConnectionState",
    "AuthInterface", 
    "SubscriptionInterface",
    "ReducerInterface",
    "SpacetimeDBClientInterface",
    
    # Enhanced Connection Management (extracted from blackholio-python-client patterns)
    "PoolState",
    "HealthStatus",
    "ConnectionMetrics",
    "PoolConfiguration",
    "PooledConnection",
    "ServerConfig",
    "ConnectionPool",
    "EnhancedConnectionManager",
    "get_connection_manager",
    "get_pooled_connection",
    
    # Enhanced Event System (extracted from blackholio-python-client patterns)
    "EventType",
    "EventPriority",
    "Event",
    # "EventT",  # Temporarily commented out
    "EventFilter",
    "EventMetrics",
    "EventHandler",
    "AsyncEventHandler",
    "SyncEventHandler",
    "EventSubscriber",
    "CallbackEventSubscriber",
    "FilteredEventSubscriber",
    "EnhancedEventManager",
    "get_event_manager",
    "event_context",
    "publish_event",
    "subscribe_to_events",
    
    # SpacetimeDB-specific events
    "ConnectionEvent",
    "AuthenticationEvent",
    "SubscriptionEvent",
    "TableUpdateEvent",
    "ReducerCallEvent",
    "TransactionEvent",
    "QueryEvent",
    "SystemEvent",
    "ErrorEvent",
    "DebugEvent",
    "PerformanceEvent",
    "create_connection_event",
    "create_table_update_event",
    "create_reducer_call_event",
    "create_error_event",
    "create_performance_event",
    
    # Enhanced Factory Pattern for multi-server language support
    "SpacetimeDBClientFactory",
    "SpacetimeDBClientFactoryBase",
    "SpacetimeDBFactoryRegistry",
    "RustOptimizedFactory",
    "PythonOptimizedFactory",
    "CSharpOptimizedFactory",
    "GoOptimizedFactory",
    "create_spacetimedb_client",
    "get_spacetimedb_factory",
    "list_supported_languages",
    "get_language_info",
    "create_optimized_client",
    
    # Convenience functions for each language
    "create_rust_client",
    "create_python_client",
    "create_csharp_client",
    "create_go_client",
    
    # Additional factory utilities
    "get_recommended_config",
    "validate_server_compatibility",
    "get_optimization_capabilities",
    
    # Subscription data flow fixes (addressing bug report issues)
    "SubscriptionManager",
    "SubscriptionState",
    "SubscriptionInfo", 
    "get_subscription_manager",
    "set_subscription_manager",
    "SDKEventManager",
    "SDKEventType",
    "EventData",
    "get_sdk_event_manager",
    "set_sdk_event_manager",
    "_safe_extract",
    "_get_message_type",
    "_handle_database_update",
    "_handle_subscription_update",
    "serialize_for_client",
    "prepare_message_for_client",
    "ensure_dict_compatible",
    "validate_serialization",
    "ClientCompatibilityWrapper",
    "wrap_for_client_compatibility",
    
]

# Default to SpacetimeDB client
# Users can import as: from spacetimedb_sdk import SpacetimeDBClient

# No backward compatibility - use the new class names directly
