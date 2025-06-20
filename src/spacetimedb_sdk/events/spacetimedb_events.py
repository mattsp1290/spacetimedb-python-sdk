"""
SpacetimeDB-specific Event Types

Concrete event implementations for SpacetimeDB operations including
connection events, table updates, reducer calls, and system events.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .enhanced_event_system import Event, EventType, EventPriority


@dataclass
class ConnectionEvent(Event):
    """Event for connection state changes."""
    
    connection_id: Optional[str] = None
    host: Optional[str] = None
    database: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.CONNECTION
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate connection event."""
        if not self.connection_id and not self.host:
            raise ValueError("ConnectionEvent must have connection_id or host")
    
    def get_event_name(self) -> str:
        """Get event name."""
        return f"Connection{self.state.title() if self.state else 'Change'}"


@dataclass
class AuthenticationEvent(Event):
    """Event for authentication operations."""
    
    identity: Optional[str] = None
    auth_token: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.AUTHENTICATION
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate authentication event."""
        if not self.identity and not self.auth_token:
            raise ValueError("AuthenticationEvent must have identity or auth_token")
    
    def get_event_name(self) -> str:
        """Get event name."""
        status = "Success" if self.success else "Failed"
        return f"Authentication{status}"


@dataclass
class SubscriptionEvent(Event):
    """Event for subscription operations."""
    
    query_id: Optional[str] = None
    table_name: Optional[str] = None
    sql_query: Optional[str] = None
    operation: Optional[str] = None  # subscribe, unsubscribe, update
    success: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.SUBSCRIPTION
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate subscription event."""
        if not self.query_id and not self.table_name:
            raise ValueError("SubscriptionEvent must have query_id or table_name")
    
    def get_event_name(self) -> str:
        """Get event name."""
        op = self.operation.title() if self.operation else "Subscription"
        return f"{op}Event"


@dataclass
class TableUpdateEvent(Event):
    """Event for table data updates."""
    
    table_name: str = ""
    operation: str = ""  # insert, update, delete
    row_data: Optional[Dict[str, Any]] = None
    old_row_data: Optional[Dict[str, Any]] = None
    primary_key: Optional[Any] = None
    transaction_id: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.TABLE_UPDATE
        if self.operation in ['insert', 'update', 'delete']:
            self.priority = EventPriority.HIGH
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate table update event."""
        if not self.table_name:
            raise ValueError("TableUpdateEvent must have table_name")
        if self.operation not in ['insert', 'update', 'delete', '']:
            raise ValueError(f"Invalid operation: {self.operation}")
    
    def get_event_name(self) -> str:
        """Get event name."""
        op = self.operation.title() if self.operation else "Update"
        return f"Table{op}"


@dataclass
class ReducerCallEvent(Event):
    """Event for reducer function calls."""
    
    reducer_name: str = ""
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    energy_consumed: Optional[int] = None
    execution_time_ms: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.REDUCER_CALL
        self.priority = EventPriority.NORMAL
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate reducer call event."""
        if not self.reducer_name:
            raise ValueError("ReducerCallEvent must have reducer_name")
    
    def get_event_name(self) -> str:
        """Get event name."""
        return f"ReducerCall.{self.reducer_name}"


@dataclass
class TransactionEvent(Event):
    """Event for database transactions."""
    
    transaction_id: str = ""
    operation: str = ""  # begin, commit, rollback
    table_operations: List[Dict[str, Any]] = field(default_factory=list)
    energy_consumed: Optional[int] = None
    execution_time_ms: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.TRANSACTION
        if self.operation in ['commit', 'rollback']:
            self.priority = EventPriority.HIGH
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate transaction event."""
        if not self.transaction_id:
            raise ValueError("TransactionEvent must have transaction_id")
        if self.operation not in ['begin', 'commit', 'rollback', '']:
            raise ValueError(f"Invalid operation: {self.operation}")
    
    def get_event_name(self) -> str:
        """Get event name."""
        op = self.operation.title() if self.operation else "Transaction"
        return f"{op}Transaction"


@dataclass
class QueryEvent(Event):
    """Event for database queries."""
    
    query_id: Optional[str] = None
    sql_query: Optional[str] = None
    table_name: Optional[str] = None
    query_type: str = ""  # select, subscribe, one_off
    result_count: Optional[int] = None
    execution_time_ms: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.QUERY
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate query event."""
        if not self.query_id and not self.sql_query:
            raise ValueError("QueryEvent must have query_id or sql_query")
    
    def get_event_name(self) -> str:
        """Get event name."""
        qtype = self.query_type.title() if self.query_type else "Query"
        return f"{qtype}Query"


@dataclass
class SystemEvent(Event):
    """Event for system-level operations."""
    
    component: str = ""
    operation: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.SYSTEM
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate system event."""
        if not self.component:
            raise ValueError("SystemEvent must have component")
    
    def get_event_name(self) -> str:
        """Get event name."""
        return f"System.{self.component}.{self.operation}" if self.operation else f"System.{self.component}"


@dataclass
class ErrorEvent(Event):
    """Event for error conditions."""
    
    error_type: str = ""
    error_message: str = ""
    stack_trace: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    recovery_action: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.ERROR
        self.priority = EventPriority.HIGH
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate error event."""
        if not self.error_message:
            raise ValueError("ErrorEvent must have error_message")
    
    def get_event_name(self) -> str:
        """Get event name."""
        return f"Error.{self.error_type}" if self.error_type else "Error"


@dataclass
class DebugEvent(Event):
    """Event for debug information."""
    
    debug_level: str = "info"  # debug, info, warning
    message: str = ""
    component: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.event_type = EventType.DEBUG
        self.priority = EventPriority.LOW
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate debug event."""
        if not self.message:
            raise ValueError("DebugEvent must have message")
        if self.debug_level not in ['debug', 'info', 'warning']:
            raise ValueError(f"Invalid debug_level: {self.debug_level}")
    
    def get_event_name(self) -> str:
        """Get event name."""
        return f"Debug.{self.debug_level.title()}"


@dataclass
class PerformanceEvent(Event):
    """Event for performance metrics."""
    
    operation: str = ""
    execution_time_ms: float = 0.0
    memory_used_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    network_bytes: Optional[int] = None
    component: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.event_type = EventType.PERFORMANCE
        self.priority = EventPriority.LOW
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate performance event."""
        if not self.operation:
            raise ValueError("PerformanceEvent must have operation")
        if self.execution_time_ms < 0:
            raise ValueError("execution_time_ms must be non-negative")
    
    def get_event_name(self) -> str:
        """Get event name."""
        return f"Performance.{self.operation}"


# Convenience functions for creating specific events
def create_connection_event(connection_id: str, state: str, **kwargs) -> ConnectionEvent:
    """Create a connection event."""
    return ConnectionEvent(connection_id=connection_id, state=state, **kwargs)


def create_table_update_event(table_name: str, operation: str, **kwargs) -> TableUpdateEvent:
    """Create a table update event."""
    return TableUpdateEvent(table_name=table_name, operation=operation, **kwargs)


def create_reducer_call_event(reducer_name: str, success: bool = True, **kwargs) -> ReducerCallEvent:
    """Create a reducer call event."""
    return ReducerCallEvent(reducer_name=reducer_name, success=success, **kwargs)


def create_error_event(error_message: str, error_type: str = "UnknownError", **kwargs) -> ErrorEvent:
    """Create an error event."""
    return ErrorEvent(error_message=error_message, error_type=error_type, **kwargs)


def create_performance_event(operation: str, execution_time_ms: float, **kwargs) -> PerformanceEvent:
    """Create a performance event."""
    return PerformanceEvent(operation=operation, execution_time_ms=execution_time_ms, **kwargs)


__all__ = [
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
    'create_connection_event',
    'create_table_update_event',
    'create_reducer_call_event',
    'create_error_event',
    'create_performance_event'
]