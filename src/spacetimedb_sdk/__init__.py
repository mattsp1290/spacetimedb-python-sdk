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

# Modern client (protocol v1.1.1)
from .modern_client import (
    ModernSpacetimeDBClient,
    SpacetimeDBClient,  # Alias for backward compatibility
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
    ModernWebSocketClient,
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

# Advanced event system exports
from .event_system import (
    EventEmitter,
    EventContext,
    EventType,
    Event,
    EventMetadata,
    ReducerEvent as AdvancedReducerEvent,
    TableEvent,
    create_event,
    create_reducer_event,
    create_table_event,
    global_event_bus
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

__all__ = [
    # Version
    "__version__",
    
    # Modern client (recommended)
    "ModernSpacetimeDBClient",
    "SpacetimeDBClient",  # Alias pointing to modern client
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
    "ModernWebSocketClient",
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
    
    # Advanced event system
    "EventEmitter",
    "EventContext",
    "EventType",
    "Event",
    "EventMetadata",
    "AdvancedReducerEvent",
    "TableEvent",
    "create_event",
    "create_reducer_event",
    "create_table_event",
    "global_event_bus",
    
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
    "CrossPlatformTestSuite"
]

# Default to modern client
# Users can import as: from spacetimedb_sdk import SpacetimeDBClient
# Or explicitly: from spacetimedb_sdk import ModernSpacetimeDBClient
