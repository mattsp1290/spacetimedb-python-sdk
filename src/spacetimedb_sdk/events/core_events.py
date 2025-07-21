"""
Core Event Definitions for SpacetimeDB SDK Unified Event System

This module provides consolidated event types and definitions that unify
all previous event systems into a single, coherent system.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
import time
import uuid


class EventType(Enum):
    """
    Unified event type enumeration consolidating all previous event systems.
    
    This replaces the scattered EventType enums from:
    - event_system.py
    - event_manager.py  
    - events/enhanced_event_system.py
    """
    
    # Connection Events (unified from all systems)
    CONNECTION_ESTABLISHED = "connection.established"
    CONNECTION_OPENED = "connection.opened"
    CONNECTION_CLOSED = "connection.closed"
    CONNECTION_LOST = "connection.lost"
    CONNECTION_ERROR = "connection.error"
    
    # Authentication Events
    IDENTITY_RECEIVED = "identity.received"
    IDENTITY_CHANGED = "identity.changed"
    IDENTITY_TOKEN = "identity.token"
    AUTHENTICATION_SUCCESS = "authentication.success"
    AUTHENTICATION_FAILED = "authentication.failed"
    
    # Subscription Events
    SUBSCRIPTION_APPLIED = "subscription.applied"
    SUBSCRIPTION_UPDATE = "subscription.update"
    SUBSCRIPTION_ERROR = "subscription.error"
    SUBSCRIPTION_REMOVED = "subscription.removed"
    INITIAL_SUBSCRIPTION = "subscription.initial"
    
    # Table Events
    TABLE_ROW_INSERT = "table.row.insert"
    TABLE_ROW_UPDATE = "table.row.update"
    TABLE_ROW_DELETE = "table.row.delete"
    TABLE_UPDATE = "table.update"
    
    # Reducer Events
    REDUCER_CALLED = "reducer.called"
    REDUCER_SUCCESS = "reducer.success"
    REDUCER_ERROR = "reducer.error"
    
    # Transaction Events
    TRANSACTION_UPDATE = "transaction.update"
    TRANSACTION_BEGIN = "transaction.begin"
    TRANSACTION_COMMIT = "transaction.commit"
    TRANSACTION_ROLLBACK = "transaction.rollback"
    
    # Database Events
    DATABASE_UPDATE = "database.update"
    
    # Query Events
    QUERY_EXECUTED = "query.executed"
    QUERY_ERROR = "query.error"
    
    # Message Events
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    
    # Energy Events
    ENERGY_LOW = "energy.low"
    ENERGY_EXHAUSTED = "energy.exhausted"
    ENERGY_REFILLED = "energy.refilled"
    
    # System Events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    
    # Error Events
    ERROR_OCCURRED = "error.occurred"
    
    # Debug Events
    DEBUG_INFO = "debug.info"
    DEBUG_WARNING = "debug.warning"
    
    # Performance Events
    PERFORMANCE_METRIC = "performance.metric"
    
    # Custom Events
    CUSTOM = "custom"


class EventPriority(Enum):
    """Event priority levels for processing order."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20
    EMERGENCY = 100


@dataclass
class EventMetadata:
    """
    Unified event metadata consolidating all previous metadata systems.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    source: str = "system"
    user_metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def age_seconds(self) -> float:
        """Get age of event in seconds."""
        return time.time() - self.timestamp
    
    def is_expired(self, max_age_seconds: float) -> bool:
        """Check if event has expired."""
        return self.age_seconds > max_age_seconds


@dataclass
class BaseEvent:
    """
    Base event class unifying all previous event implementations.
    
    This replaces Event classes from:
    - event_system.py
    - event_manager.py
    - events/enhanced_event_system.py
    """
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)
    priority: EventPriority = EventPriority.NORMAL
    
    @property
    def event_type(self) -> EventType:
        """Backward compatibility property for event_type access."""
        return self.type
    
    @property
    def timestamp(self) -> float:
        """Backward compatibility property for timestamp access."""
        return self.metadata.timestamp
    
    def with_metadata(self, **kwargs) -> 'BaseEvent':
        """Return a copy of the event with updated metadata."""
        import copy
        new_event = copy.deepcopy(self)
        for key, value in kwargs.items():
            if hasattr(new_event.metadata, key):
                setattr(new_event.metadata, key, value)
            else:
                new_event.metadata.user_metadata[key] = value
        return new_event
    
    def get_age_seconds(self) -> float:
        """Get age of event in seconds."""
        return self.metadata.age_seconds
    
    def is_expired(self, max_age_seconds: float) -> bool:
        """Check if event has expired."""
        return self.metadata.is_expired(max_age_seconds)
    
    def add_context(self, key: str, value: Any) -> None:
        """Add contextual data to the event."""
        self.data[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get contextual data from the event."""
        return self.data.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation."""
        return {
            'event_id': self.metadata.event_id,
            'timestamp': self.metadata.timestamp,
            'event_type': self.type.value,
            'priority': self.priority.value,
            'source': self.metadata.source,
            'correlation_id': self.metadata.correlation_id,
            'causation_id': self.metadata.causation_id,
            'data': self.data.copy(),
            'user_metadata': self.metadata.user_metadata.copy()
        }


@dataclass
class ConnectionEvent(BaseEvent):
    """Event for connection state changes."""
    
    def __init__(self, connection_id: Optional[str] = None, state: Optional[str] = None, 
                 host: Optional[str] = None, database: Optional[str] = None, 
                 error: Optional[str] = None, **kwargs):
        super().__init__(type=EventType.CONNECTION_ESTABLISHED, **kwargs)
        self.data.update({
            'connection_id': connection_id,
            'state': state,
            'host': host,
            'database': database,
            'error': error
        })


@dataclass
class AuthenticationEvent(BaseEvent):
    """Event for authentication operations."""
    
    def __init__(self, identity: Optional[str] = None, auth_token: Optional[str] = None,
                 success: bool = False, error: Optional[str] = None, **kwargs):
        super().__init__(type=EventType.IDENTITY_RECEIVED, **kwargs)
        self.data.update({
            'identity': identity,
            'auth_token': auth_token,
            'success': success,
            'error': error
        })


@dataclass
class SubscriptionEvent(BaseEvent):
    """Event for subscription operations."""
    
    def __init__(self, query_id: Optional[str] = None, table_name: Optional[str] = None,
                 sql_query: Optional[str] = None, operation: Optional[str] = None,
                 success: bool = False, error: Optional[str] = None, **kwargs):
        super().__init__(type=EventType.SUBSCRIPTION_APPLIED, **kwargs)
        self.data.update({
            'query_id': query_id,
            'table_name': table_name,
            'sql_query': sql_query,
            'operation': operation,
            'success': success,
            'error': error
        })


@dataclass
class TableEvent(BaseEvent):
    """Event for table row changes."""
    
    def __init__(self, table_name: str, operation: str, row_data: Any = None,
                 old_row_data: Any = None, primary_key: Any = None,
                 transaction_id: Optional[str] = None, **kwargs):
        event_type_map = {
            'insert': EventType.TABLE_ROW_INSERT,
            'update': EventType.TABLE_ROW_UPDATE,
            'delete': EventType.TABLE_ROW_DELETE
        }
        event_type = event_type_map.get(operation, EventType.TABLE_UPDATE)
        
        super().__init__(type=event_type, **kwargs)
        self.data.update({
            'table_name': table_name,
            'operation': operation,
            'row_data': row_data,
            'old_row_data': old_row_data,
            'primary_key': primary_key,
            'transaction_id': transaction_id
        })


@dataclass
class ReducerEvent(BaseEvent):
    """Event for reducer function calls."""
    
    def __init__(self, reducer_name: str, args: List[Any] = None, kwargs_dict: Dict[str, Any] = None,
                 status: str = "pending", error_message: Optional[str] = None,
                 energy_used: int = 0, execution_duration_nanos: int = 0,
                 caller_identity: Optional[str] = None, caller_connection_id: Optional[str] = None,
                 request_id: Optional[bytes] = None, **kwargs):
        super().__init__(type=EventType.REDUCER_CALLED, **kwargs)
        self.data.update({
            'reducer_name': reducer_name,
            'args': args or [],
            'kwargs': kwargs_dict or {},
            'status': status,
            'error_message': error_message,
            'energy_used': energy_used,
            'execution_duration_nanos': execution_duration_nanos,
            'caller_identity': caller_identity,
            'caller_connection_id': caller_connection_id,
            'request_id': request_id
        })
    
    @property
    def is_success(self) -> bool:
        """Check if reducer execution was successful."""
        return self.data.get('status') == "success"
    
    @property
    def is_error(self) -> bool:
        """Check if reducer execution failed."""
        return self.data.get('status') == "error"
    
    @property
    def execution_time_ms(self) -> float:
        """Get execution time in milliseconds."""
        return self.data.get('execution_duration_nanos', 0) / 1_000_000.0


@dataclass
class TransactionEvent(BaseEvent):
    """Event for database transactions."""
    
    def __init__(self, transaction_id: str, operation: str, 
                 table_operations: List[Dict[str, Any]] = None,
                 energy_consumed: Optional[int] = None, 
                 execution_time_ms: Optional[float] = None,
                 success: bool = False, error: Optional[str] = None, **kwargs):
        super().__init__(type=EventType.TRANSACTION_UPDATE, **kwargs)
        self.data.update({
            'transaction_id': transaction_id,
            'operation': operation,
            'table_operations': table_operations or [],
            'energy_consumed': energy_consumed,
            'execution_time_ms': execution_time_ms,
            'success': success,
            'error': error
        })


@dataclass
class MessageEvent(BaseEvent):
    """Event for message handling."""
    
    def __init__(self, message_data: Any, direction: str = "received",
                 message_type: Optional[str] = None, **kwargs):
        event_type = EventType.MESSAGE_RECEIVED if direction == "received" else EventType.MESSAGE_SENT
        super().__init__(type=event_type, **kwargs)
        self.data.update({
            'message_data': message_data,
            'direction': direction,
            'message_type': message_type
        })


@dataclass
class ErrorEvent(BaseEvent):
    """Event for error conditions."""
    
    def __init__(self, error_message: str, error_type: str = "UnknownError",
                 stack_trace: Optional[str] = None, component: Optional[str] = None,
                 operation: Optional[str] = None, recovery_action: Optional[str] = None,
                 **kwargs):
        super().__init__(type=EventType.ERROR_OCCURRED, priority=EventPriority.HIGH, **kwargs)
        self.data.update({
            'error_message': error_message,
            'error_type': error_type,
            'stack_trace': stack_trace,
            'component': component,
            'operation': operation,
            'recovery_action': recovery_action
        })


@dataclass
class PerformanceEvent(BaseEvent):
    """Event for performance metrics."""
    
    def __init__(self, operation: str, execution_time_ms: float,
                 memory_used_mb: Optional[float] = None, 
                 cpu_usage_percent: Optional[float] = None,
                 network_bytes: Optional[int] = None, 
                 component: Optional[str] = None,
                 details: Dict[str, Any] = None, **kwargs):
        super().__init__(type=EventType.PERFORMANCE_METRIC, priority=EventPriority.LOW, **kwargs)
        self.data.update({
            'operation': operation,
            'execution_time_ms': execution_time_ms,
            'memory_used_mb': memory_used_mb,
            'cpu_usage_percent': cpu_usage_percent,
            'network_bytes': network_bytes,
            'component': component,
            'details': details or {}
        })


# Convenience functions for creating events
def create_connection_event(connection_id: str, state: str, **kwargs) -> ConnectionEvent:
    """Create a connection event."""
    return ConnectionEvent(connection_id=connection_id, state=state, **kwargs)


def create_table_event(table_name: str, operation: str, row_data: Any = None, **kwargs) -> TableEvent:
    """Create a table event."""
    return TableEvent(table_name=table_name, operation=operation, row_data=row_data, **kwargs)


def create_reducer_event(reducer_name: str, status: str = "pending", **kwargs) -> ReducerEvent:
    """Create a reducer event."""
    return ReducerEvent(reducer_name=reducer_name, status=status, **kwargs)


def create_error_event(error_message: str, error_type: str = "UnknownError", **kwargs) -> ErrorEvent:
    """Create an error event."""
    return ErrorEvent(error_message=error_message, error_type=error_type, **kwargs)


def create_performance_event(operation: str, execution_time_ms: float, **kwargs) -> PerformanceEvent:
    """Create a performance event."""
    return PerformanceEvent(operation=operation, execution_time_ms=execution_time_ms, **kwargs)


# Type aliases for compatibility
Event = BaseEvent  # Main event type