"""
Modern SpacetimeDB WebSocket protocol implementation (v1.1.1)

This module implements the modern WebSocket protocol as defined in 
SpacetimeDB/crates/client-api-messages/src/websocket.rs
"""

from typing import Optional, List, Dict, Any, Union, Literal, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import json
import struct
import uuid

if TYPE_CHECKING:
    from .query_id import QueryId

# Import the enhanced CallReducerFlags from the dedicated module
from .call_reducer_flags import CallReducerFlags

# Import enhanced connection management types
from .connection_id import (
    EnhancedConnectionId,
    EnhancedIdentity,
    EnhancedIdentityToken,
    ConnectionState,
    ConnectionEventType,
    ConnectionEvent,
    ConnectionStateTracker,
    ConnectionLifecycleManager,
    ConnectionMetrics
)

# Import modern message types
from .messages.subscribe import (
    SubscribeSingleMessage,
    SubscribeMultiMessage,
    UnsubscribeMultiMessage
)
from .messages.one_off_query import (
    OneOffQueryMessage
)

# Protocol constants
TEXT_PROTOCOL = "v1.json.spacetimedb"
BIN_PROTOCOL = "v1.bsatn.spacetimedb"

# Compression tags
SERVER_MSG_COMPRESSION_TAG_NONE = 0
SERVER_MSG_COMPRESSION_TAG_BROTLI = 1
SERVER_MSG_COMPRESSION_TAG_GZIP = 2


# Import QueryId from the dedicated module to avoid circular imports
def _get_query_id_class():
    """Lazy import QueryId to avoid circular imports."""
    from .query_id import QueryId
    return QueryId


@dataclass
class CallReducer:
    """Request a reducer run."""
    reducer: str
    args: bytes  # BSATN or JSON encoded according to the reducer's argument schema
    request_id: int
    flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE


@dataclass
class Subscribe:
    """Register a set of queries for subscription updates."""
    query_strings: List[str]
    request_id: int


# Use the enhanced message types from messages.subscribe module
# These replace the basic SubscribeSingle, SubscribeMulti, UnsubscribeMulti dataclasses
# with full-featured implementations that include validation, BSATN serialization, etc.

# Legacy Unsubscribe (single query) - keeping for backward compatibility
@dataclass
class Unsubscribe:
    """Remove a subscription to a query."""
    request_id: int
    query_id: 'QueryId'


@dataclass
class OneOffQuery:
    """A one-off query submission."""
    message_id: bytes
    query_string: str


# Client -> Server messages
ClientMessage = Union[
    CallReducer,
    Subscribe,
    SubscribeSingleMessage,  # Modern enhanced version
    SubscribeMultiMessage,   # Modern enhanced version
    Unsubscribe,            # Legacy single unsubscribe
    UnsubscribeMultiMessage, # Modern enhanced version
    OneOffQuery,            # Legacy basic version (for backward compatibility)
    OneOffQueryMessage      # Modern enhanced version
]


# Legacy Identity and ConnectionId classes for backward compatibility
@dataclass
class Identity:
    """Represents a user identity (legacy class for backward compatibility)."""
    data: bytes
    
    @classmethod
    def from_hex(cls, hex_string: str) -> 'Identity':
        """Create Identity from hex string."""
        return cls(data=bytes.fromhex(hex_string))
    
    def to_hex(self) -> str:
        """Convert Identity to hex string."""
        return self.data.hex()
    
    def __str__(self) -> str:
        return self.to_hex()
    
    def to_enhanced(self) -> EnhancedIdentity:
        """Convert to enhanced Identity."""
        return EnhancedIdentity(data=self.data)


@dataclass
class ConnectionId:
    """Represents a connection ID (legacy class for backward compatibility)."""
    data: bytes
    
    @classmethod
    def from_hex(cls, hex_string: str) -> 'ConnectionId':
        """Create ConnectionId from hex string."""
        return cls(data=bytes.fromhex(hex_string))
    
    def to_hex(self) -> str:
        """Convert ConnectionId to hex string."""
        return self.data.hex()
    
    def as_u64_pair(self) -> tuple[int, int]:
        """
        Extract ConnectionId as a pair of u64 values.
        
        ConnectionId is typically represented as [2]uint64 in the protocol.
        
        Returns:
            Tuple of two u64 values (high, low)
        """
        if len(self.data) < 16:
            # Pad with zeros if data is shorter than expected
            padded_data = self.data + b'\x00' * (16 - len(self.data))
        else:
            padded_data = self.data[:16]  # Take first 16 bytes
        
        # Extract as two u64 values (little-endian)
        high = struct.unpack('<Q', padded_data[:8])[0]
        low = struct.unpack('<Q', padded_data[8:16])[0]
        return (high, low)
    
    def __str__(self) -> str:
        return self.to_hex()
    
    def to_enhanced(self) -> EnhancedConnectionId:
        """Convert to enhanced ConnectionId."""
        return EnhancedConnectionId(data=self.data)


@dataclass
class QueryId:
    """Represents a query ID for subscription management."""
    id: int
    
    @classmethod
    def from_int(cls, query_id: int) -> 'QueryId':
        """Create QueryId from integer."""
        return cls(id=query_id)
    
    def to_int(self) -> int:
        """Convert QueryId to integer."""
        return self.id
    
    def __str__(self) -> str:
        return f"QueryId({self.id})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other) -> bool:
        """Check equality with another QueryId."""
        if isinstance(other, QueryId):
            return self.id == other.id
        return False
    
    def __hash__(self) -> int:
        """Make QueryId hashable."""
        return hash(self.id)


# Utility functions for converting between legacy and enhanced types
def ensure_enhanced_connection_id(connection_id: Union[ConnectionId, EnhancedConnectionId]) -> EnhancedConnectionId:
    """Ensure we have an enhanced ConnectionId."""
    if isinstance(connection_id, ConnectionId):
        return connection_id.to_enhanced()
    return connection_id


def ensure_enhanced_identity(identity: Union[Identity, EnhancedIdentity]) -> EnhancedIdentity:
    """Ensure we have an enhanced Identity."""
    if isinstance(identity, Identity):
        return identity.to_enhanced()
    return identity


@dataclass
class Timestamp:
    """Represents a timestamp."""
    nanos_since_epoch: int


@dataclass
class TimeDuration:
    """Represents a time duration."""
    nanos: int


@dataclass
class EnergyQuanta:
    """Represents energy credits consumed by a reducer with enhanced tracking capabilities."""
    quanta: int
    
    def get_cost_estimate(self, operation_type: str, operation_name: str) -> int:
        """
        Estimate energy cost for an operation.
        
        Args:
            operation_type: Type of operation (e.g., "call_reducer", "query")
            operation_name: Specific operation name
            
        Returns:
            Estimated energy cost
        """
        # Basic cost estimation
        base_costs = {
            'call_reducer': 50,
            'query': 25,
            'subscription': 30,
            'one_off_query': 20
        }
        
        # Get base cost or default
        base_cost = base_costs.get(operation_type, 25)
        
        # Simple heuristics for operation complexity
        if operation_type == 'call_reducer':
            # Longer reducer names might indicate more complexity
            complexity_factor = min(1.5, 1 + len(operation_name) * 0.01)
            return int(base_cost * complexity_factor)
        elif operation_type == 'query':
            # Simple query complexity heuristics
            query_lower = operation_name.lower()
            if 'join' in query_lower:
                base_cost = int(base_cost * 1.5)
            if any(func in query_lower for func in ['count', 'sum', 'avg', 'max', 'min']):
                base_cost = int(base_cost * 1.3)
            if 'order by' in query_lower:
                base_cost = int(base_cost * 1.2)
        
        return base_cost
    
    def can_afford(self, cost: int) -> bool:
        """
        Check if the current energy quanta can afford an operation.
        
        Args:
            cost: Energy cost of the operation
            
        Returns:
            True if the operation is affordable
        """
        return self.quanta >= cost
    
    def track_usage(self, cost: int, operation: str = "") -> bool:
        """
        Track energy usage by consuming the specified amount.
        
        Args:
            cost: Energy to consume
            operation: Operation description for tracking
            
        Returns:
            True if energy was successfully consumed
        """
        if self.can_afford(cost):
            self.quanta -= cost
            # Store usage history if we have a tracker available
            if hasattr(self, '_usage_history'):
                from .energy import EnergyOperation
                import time
                operation_record = EnergyOperation(
                    operation_type="tracked",
                    operation_name=operation,
                    energy_cost=cost,
                    timestamp=time.time(),
                    success=True
                )
                self._usage_history.append(operation_record)
            return True
        else:
            # Track failed operation if we have a tracker available
            if hasattr(self, '_usage_history'):
                from .energy import EnergyOperation
                import time
                operation_record = EnergyOperation(
                    operation_type="tracked",
                    operation_name=operation,
                    energy_cost=cost,
                    timestamp=time.time(),
                    success=False
                )
                self._usage_history.append(operation_record)
            return False
    
    def get_usage_history(self) -> List[Dict[str, Any]]:
        """
        Get energy usage history.
        
        Returns:
            List of usage records
        """
        if hasattr(self, '_usage_history'):
            return [
                {
                    'operation_type': op.operation_type,
                    'operation_name': op.operation_name,
                    'energy_cost': op.energy_cost,
                    'timestamp': op.timestamp,
                    'success': op.success
                }
                for op in self._usage_history
            ]
        return []
    
    def enable_usage_tracking(self, history_size: int = 100) -> None:
        """
        Enable usage tracking for this EnergyQuanta instance.
        
        Args:
            history_size: Maximum number of operations to track
        """
        from collections import deque
        self._usage_history = deque(maxlen=history_size)
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """
        Serialize EnergyQuanta to BSATN format.
        
        Args:
            writer: BSATN writer instance
        """
        writer.write_struct_header(1)  # One field: quanta
        writer.write_field_name("quanta")
        writer.write_u64(self.quanta)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnergyQuanta':
        """
        Deserialize EnergyQuanta from BSATN format.
        
        Args:
            reader: BSATN reader instance
            
        Returns:
            EnergyQuanta instance
        """
        field_count = reader.read_struct_header()
        
        quanta = 0
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "quanta":
                quanta = reader.read_u64()
            else:
                # Skip unknown fields for forward compatibility
                reader.skip_value()
        
        return cls(quanta=quanta)
    
    def __add__(self, other: Union[int, 'EnergyQuanta']) -> 'EnergyQuanta':
        """Add energy quanta."""
        if isinstance(other, int):
            return EnergyQuanta(self.quanta + other)
        elif isinstance(other, EnergyQuanta):
            return EnergyQuanta(self.quanta + other.quanta)
        return NotImplemented
    
    def __sub__(self, other: Union[int, 'EnergyQuanta']) -> 'EnergyQuanta':
        """Subtract energy quanta."""
        if isinstance(other, int):
            return EnergyQuanta(max(0, self.quanta - other))
        elif isinstance(other, EnergyQuanta):
            return EnergyQuanta(max(0, self.quanta - other.quanta))
        return NotImplemented
    
    def __bool__(self) -> bool:
        """Return True if there's any energy available."""
        return self.quanta > 0
    
    def __str__(self) -> str:
        return f"EnergyQuanta({self.quanta})"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class IdentityToken:
    """Server message containing identity information (legacy for backward compatibility)."""
    identity: Identity
    token: str
    connection_id: ConnectionId
    
    def to_enhanced(self) -> EnhancedIdentityToken:
        """Convert to enhanced IdentityToken."""
        return EnhancedIdentityToken(
            identity=self.identity.to_enhanced(),
            token=self.token,
            connection_id=self.connection_id.to_enhanced()
        )


@dataclass
class TableUpdate:
    """Updates to a single table."""
    table_id: int
    table_name: str
    num_rows: int
    # In the real implementation, this would contain the actual row data
    # For now, we'll use a simplified representation
    inserts: List[Dict[str, Any]]
    deletes: List[Dict[str, Any]]


@dataclass
class DatabaseUpdate:
    """A collection of table updates."""
    tables: List[TableUpdate]


@dataclass
class ReducerCallInfo:
    """Metadata about a reducer invocation."""
    reducer_name: str
    reducer_id: int
    args: bytes  # BSATN or JSON encoded
    request_id: int


@dataclass
class TransactionUpdate:
    """Server message for reducer run results."""
    status: Union[DatabaseUpdate, str]  # DatabaseUpdate for success, str for error
    timestamp: Timestamp
    caller_identity: Identity
    caller_connection_id: ConnectionId
    reducer_call: ReducerCallInfo
    energy_quanta_used: EnergyQuanta
    total_host_execution_duration: TimeDuration


@dataclass
class TransactionUpdateLight:
    """Lightweight transaction update containing only table changes."""
    request_id: int
    update: DatabaseUpdate


@dataclass
class InitialSubscription:
    """Response to Subscribe containing initial matching rows."""
    database_update: DatabaseUpdate
    request_id: int
    total_host_execution_duration: TimeDuration


@dataclass
class SubscribeApplied:
    """Response to SubscribeSingle containing initial matching rows."""
    request_id: int
    total_host_execution_duration_micros: int
    query_id: 'QueryId'
    table_id: int
    table_name: str
    table_rows: TableUpdate


@dataclass
class UnsubscribeApplied:
    """Response to Unsubscribe."""
    request_id: int
    total_host_execution_duration_micros: int
    query_id: 'QueryId'
    table_id: int
    table_name: str
    table_rows: TableUpdate


@dataclass
class SubscriptionError:
    """Error in subscription lifecycle."""
    total_host_execution_duration_micros: int
    request_id: Optional[int]
    query_id: Optional[int]
    table_id: Optional[int]
    error: str


@dataclass
class SubscribeMultiApplied:
    """Response to SubscribeMulti."""
    request_id: int
    total_host_execution_duration_micros: int
    query_id: 'QueryId'
    update: DatabaseUpdate


@dataclass
class UnsubscribeMultiApplied:
    """Response to UnsubscribeMulti."""
    request_id: int
    total_host_execution_duration_micros: int
    query_id: 'QueryId'
    update: DatabaseUpdate


@dataclass
class OneOffTable:
    """A table included in OneOffQueryResponse."""
    table_name: str
    rows: List[Dict[str, Any]]  # Simplified representation


@dataclass
class OneOffQueryResponse:
    """Response to OneOffQuery."""
    message_id: bytes
    error: Optional[str]
    tables: List[OneOffTable]
    total_host_execution_duration: TimeDuration


# Server -> Client messages
ServerMessage = Union[
    InitialSubscription,
    TransactionUpdate,
    TransactionUpdateLight,
    IdentityToken,
    OneOffQueryResponse,
    SubscribeApplied,
    UnsubscribeApplied,
    SubscriptionError,
    SubscribeMultiApplied,
    UnsubscribeMultiApplied
]


class ProtocolEncoder:
    """Encodes messages for the SpacetimeDB protocol."""
    
    def __init__(self, use_binary: bool = False):
        self.use_binary = use_binary
    
    def encode_client_message(self, message: ClientMessage) -> bytes:
        """Encode a client message for transmission."""
        if self.use_binary:
            return self._encode_bsatn(message)
        else:
            return self._encode_json(message)
    
    def _encode_json(self, message: ClientMessage) -> bytes:
        """Encode message as JSON."""
        if isinstance(message, CallReducer):
            data = {
                "CallReducer": {
                    "reducer": message.reducer,
                    "args": message.args.decode('utf-8') if isinstance(message.args, bytes) else message.args,
                    "request_id": message.request_id,
                    "flags": message.flags.value
                }
            }
        elif isinstance(message, Subscribe):
            # Enhanced query format for latest SpacetimeDB compatibility
            # Convert table names to proper SQL queries if they're just table names
            formatted_queries = []
            for query in message.query_strings:
                # Check if this is just a table name (no spaces, no SQL keywords)
                if query and ' ' not in query and not any(keyword in query.lower() for keyword in ['select', 'from', 'where', 'join']):
                    # Convert table name to SQL query format
                    formatted_queries.append(f"SELECT * FROM {query}")
                else:
                    # Keep as-is if it's already a proper SQL query
                    formatted_queries.append(query)
            
            data = {
                "Subscribe": {
                    "query_strings": formatted_queries,
                    "request_id": message.request_id
                }
            }
        elif isinstance(message, SubscribeSingleMessage):
            # Apply same SQL conversion for single subscriptions
            query = message.query
            if query and ' ' not in query and not any(keyword in query.lower() for keyword in ['select', 'from', 'where', 'join']):
                query = f"SELECT * FROM {query}"
            
            data = {
                "SubscribeSingle": {
                    "query": query,
                    "request_id": message.request_id,
                    "query_id": {"id": message.query_id.id}
                }
            }
        elif isinstance(message, SubscribeMultiMessage):
            # Apply same SQL conversion for multi subscriptions
            formatted_queries = []
            for query in message.query_strings:
                if query and ' ' not in query and not any(keyword in query.lower() for keyword in ['select', 'from', 'where', 'join']):
                    formatted_queries.append(f"SELECT * FROM {query}")
                else:
                    formatted_queries.append(query)
            
            data = {
                "SubscribeMulti": {
                    "query_strings": formatted_queries,
                    "request_id": message.request_id,
                    "query_id": {"id": message.query_id.id}
                }
            }
        elif isinstance(message, Unsubscribe):
            data = {
                "Unsubscribe": {
                    "request_id": message.request_id,
                    "query_id": {"id": message.query_id.id}
                }
            }
        elif isinstance(message, UnsubscribeMultiMessage):
            data = {
                "UnsubscribeMulti": {
                    "request_id": message.request_id,
                    "query_id": {"id": message.query_id.id}
                }
            }
        elif isinstance(message, OneOffQuery):
            data = {
                "OneOffQuery": {
                    "message_id": list(message.message_id),
                    "query_string": message.query_string
                }
            }
        elif isinstance(message, OneOffQueryMessage):
            data = {
                "OneOffQueryMessage": {
                    "message_id": list(message.message_id),
                    "query_string": message.query_string
                }
            }
        else:
            raise ValueError(f"Unknown message type: {type(message)}")
        
        return json.dumps(data).encode('utf-8')
    
    def _encode_bsatn(self, message: ClientMessage) -> bytes:
        """Encode message as BSATN."""
        from .bsatn import BsatnWriter
        
        writer = BsatnWriter()
        
        if isinstance(message, CallReducer):
            # Encode as enum variant 0 (CallReducer)
            writer.write_enum_header(0)
            writer.write_struct_header(4)  # reducer, args, request_id, flags
            
            writer.write_field_name("reducer")
            writer.write_string(message.reducer)
            
            writer.write_field_name("args")
            writer.write_bytes(message.args)
            
            writer.write_field_name("request_id")
            writer.write_u32(message.request_id)
            
            writer.write_field_name("flags")
            writer.write_u8(message.flags.value)
            
        elif isinstance(message, Subscribe):
            # Encode as enum variant 1 (Subscribe)
            writer.write_enum_header(1)
            writer.write_struct_header(2)  # query_strings, request_id
            
            writer.write_field_name("query_strings")
            writer.write_array_header(len(message.query_strings))
            for query in message.query_strings:
                writer.write_string(query)
            
            writer.write_field_name("request_id")
            writer.write_u32(message.request_id)
            
        elif isinstance(message, SubscribeSingleMessage):
            # Encode as enum variant 2 (SubscribeSingle)
            writer.write_enum_header(2)
            writer.write_struct_header(3)  # query, request_id, query_id
            
            writer.write_field_name("query")
            writer.write_string(message.query)
            
            writer.write_field_name("request_id")
            writer.write_u32(message.request_id)
            
            writer.write_field_name("query_id")
            writer.write_struct_header(1)  # QueryId struct
            writer.write_field_name("id")
            writer.write_u32(message.query_id.id)
            
        elif isinstance(message, SubscribeMultiMessage):
            # Encode as enum variant 3 (SubscribeMulti)
            writer.write_enum_header(3)
            writer.write_struct_header(3)  # query_strings, request_id, query_id
            
            writer.write_field_name("query_strings")
            writer.write_array_header(len(message.query_strings))
            for query in message.query_strings:
                writer.write_string(query)
            
            writer.write_field_name("request_id")
            writer.write_u32(message.request_id)
            
            writer.write_field_name("query_id")
            writer.write_struct_header(1)  # QueryId struct
            writer.write_field_name("id")
            writer.write_u32(message.query_id.id)
            
        elif isinstance(message, Unsubscribe):
            # Encode as enum variant 4 (Unsubscribe)
            writer.write_enum_header(4)
            writer.write_struct_header(2)  # request_id, query_id
            
            writer.write_field_name("request_id")
            writer.write_u32(message.request_id)
            
            writer.write_field_name("query_id")
            writer.write_struct_header(1)  # QueryId struct
            writer.write_field_name("id")
            writer.write_u32(message.query_id.id)
            
        elif isinstance(message, UnsubscribeMultiMessage):
            # Encode as enum variant 5 (UnsubscribeMulti)
            writer.write_enum_header(5)
            writer.write_struct_header(2)  # request_id, query_id
            
            writer.write_field_name("request_id")
            writer.write_u32(message.request_id)
            
            writer.write_field_name("query_id")
            writer.write_struct_header(1)  # QueryId struct
            writer.write_field_name("id")
            writer.write_u32(message.query_id.id)
            
        elif isinstance(message, OneOffQuery):
            # Encode as enum variant 6 (OneOffQuery)
            writer.write_enum_header(6)
            writer.write_struct_header(2)  # message_id, query_string
            
            writer.write_field_name("message_id")
            writer.write_bytes(message.message_id)
            
            writer.write_field_name("query_string")
            writer.write_string(message.query_string)
            
        elif isinstance(message, OneOffQueryMessage):
            # Encode as enum variant 7 (OneOffQueryMessage)
            writer.write_enum_header(7)
            writer.write_struct_header(2)  # message_id, query_string
            
            writer.write_field_name("message_id")
            writer.write_bytes(message.message_id)
            
            writer.write_field_name("query_string")
            writer.write_string(message.query_string)
            
        else:
            raise ValueError(f"Unknown message type: {type(message)}")
        
        if writer.error():
            raise writer.error()
        
        return writer.get_bytes()


class ProtocolDecoder:
    """Decodes messages from the SpacetimeDB protocol."""
    
    def __init__(self, use_binary: bool = False):
        self.use_binary = use_binary
    
    def decode_server_message(self, data: bytes) -> ServerMessage:
        """Decode a server message from received data."""
        if self.use_binary:
            return self._decode_bsatn(data)
        else:
            return self._decode_json(data)
    
    def _decode_json(self, data: bytes) -> ServerMessage:
        """Decode message from JSON with enhanced compatibility for latest SpacetimeDB."""
        try:
            message = json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to decode JSON message: {e}")
        
        if "IdentityToken" in message:
            token_data = message["IdentityToken"]
            
            # Enhanced identity/connection_id parsing for latest SpacetimeDB format
            identity_data = token_data.get("identity")
            if isinstance(identity_data, dict):
                # Handle nested identity format: {"identity": {"data": [...]}}
                if "data" in identity_data:
                    identity_bytes = bytes(identity_data["data"]) if isinstance(identity_data["data"], list) else identity_data["data"]
                else:
                    # Try to extract bytes from dict representation
                    identity_bytes = str(identity_data).encode('utf-8')
                identity = Identity(data=identity_bytes)
            elif isinstance(identity_data, str):
                # Handle hex string format
                identity = Identity.from_hex(identity_data)
            elif isinstance(identity_data, list):
                # Handle byte array format
                identity = Identity(data=bytes(identity_data))
            else:
                # Fallback for unknown format
                identity = Identity(data=str(identity_data).encode('utf-8'))
            
            connection_id_data = token_data.get("connection_id")
            if isinstance(connection_id_data, dict):
                # Handle nested connection_id format: {"connection_id": {"data": [...]}}
                if "data" in connection_id_data:
                    conn_id_bytes = bytes(connection_id_data["data"]) if isinstance(connection_id_data["data"], list) else connection_id_data["data"]
                else:
                    conn_id_bytes = str(connection_id_data).encode('utf-8')
                connection_id = ConnectionId(data=conn_id_bytes)
            elif isinstance(connection_id_data, str):
                # Handle hex string format
                connection_id = ConnectionId.from_hex(connection_id_data)
            elif isinstance(connection_id_data, list):
                # Handle byte array format
                connection_id = ConnectionId(data=bytes(connection_id_data))
            else:
                # Fallback for unknown format
                connection_id = ConnectionId(data=str(connection_id_data).encode('utf-8'))
            
            return IdentityToken(
                identity=identity,
                token=token_data.get("token", ""),
                connection_id=connection_id
            )
            
        elif "TransactionUpdate" in message:
            tx_data = message["TransactionUpdate"]
            
            # Enhanced status parsing
            status = tx_data.get("status", "Unknown")
            if isinstance(status, dict):
                # Handle structured status like {"Failed": "error message"} or {"Committed": {...}}
                if "Failed" in status:
                    status = f"Failed: {status['Failed']}"
                elif "Committed" in status:
                    status = "Committed"
                else:
                    status = str(status)
            
            # Enhanced identity parsing for caller fields
            caller_identity_data = tx_data.get("caller_identity", "00")
            if isinstance(caller_identity_data, dict):
                if "data" in caller_identity_data:
                    caller_identity = Identity(data=bytes(caller_identity_data["data"]) if isinstance(caller_identity_data["data"], list) else caller_identity_data["data"])
                else:
                    caller_identity = Identity(data=str(caller_identity_data).encode('utf-8'))
            elif isinstance(caller_identity_data, str):
                caller_identity = Identity.from_hex(caller_identity_data) if caller_identity_data != "00" else Identity(data=b"\x00")
            else:
                caller_identity = Identity(data=b"\x00")
            
            caller_conn_id_data = tx_data.get("caller_connection_id", "00")
            if isinstance(caller_conn_id_data, dict):
                if "data" in caller_conn_id_data:
                    caller_connection_id = ConnectionId(data=bytes(caller_conn_id_data["data"]) if isinstance(caller_conn_id_data["data"], list) else caller_conn_id_data["data"])
                else:
                    caller_connection_id = ConnectionId(data=str(caller_conn_id_data).encode('utf-8'))
            elif isinstance(caller_conn_id_data, str):
                caller_connection_id = ConnectionId.from_hex(caller_conn_id_data) if caller_conn_id_data != "00" else ConnectionId(data=b"\x00")
            else:
                caller_connection_id = ConnectionId(data=b"\x00")
            
            return TransactionUpdate(
                status=status,
                timestamp=Timestamp(nanos_since_epoch=tx_data.get("timestamp", 0)),
                caller_identity=caller_identity,
                caller_connection_id=caller_connection_id,
                reducer_call=ReducerCallInfo(
                    reducer_name=tx_data.get("reducer_name", ""),
                    reducer_id=tx_data.get("reducer_id", 0),
                    args=b"",
                    request_id=tx_data.get("request_id", 0)
                ),
                energy_quanta_used=EnergyQuanta(quanta=tx_data.get("energy_quanta_used", 0)),
                total_host_execution_duration=TimeDuration(nanos=tx_data.get("total_host_execution_duration", 0))
            )
            
        elif "InitialSubscription" in message:
            # Handle InitialSubscription message
            sub_data = message["InitialSubscription"]
            return InitialSubscription(
                database_update=DatabaseUpdate(tables=[]),  # Simplified for now
                request_id=sub_data.get("request_id", 0),
                total_host_execution_duration=TimeDuration(nanos=sub_data.get("total_host_execution_duration", 0))
            )
            
        elif "SubscribeApplied" in message:
            # Handle SubscribeApplied message
            sub_data = message["SubscribeApplied"]
            query_id_data = sub_data.get("query_id", {})
            if isinstance(query_id_data, dict):
                query_id = QueryId(id=query_id_data.get("id", 0))
            else:
                query_id = QueryId(id=query_id_data)
                
            return SubscribeApplied(
                request_id=sub_data.get("request_id", 0),
                total_host_execution_duration_micros=sub_data.get("total_host_execution_duration_micros", 0),
                query_id=query_id,
                table_id=sub_data.get("table_id", 0),
                table_name=sub_data.get("table_name", ""),
                table_rows=None  # Simplified for now
            )
            
        elif "SubscriptionError" in message:
            # Handle SubscriptionError message
            error_data = message["SubscriptionError"]
            return SubscriptionError(
                total_host_execution_duration_micros=error_data.get("total_host_execution_duration_micros", 0),
                request_id=error_data.get("request_id"),
                query_id=error_data.get("query_id"),
                table_id=error_data.get("table_id"),
                error=error_data.get("error", "Unknown subscription error")
            )
            
        # Add more message type parsing as needed
        else:
            raise ValueError(f"Unknown server message format: {list(message.keys())}")
    
    def _decode_bsatn(self, data: bytes) -> ServerMessage:
        """Decode message from BSATN."""
        from .bsatn import BsatnReader
        from .bsatn.constants import TAG_ENUM
        
        reader = BsatnReader(data)
        
        try:
            # Read the outer enum tag to determine message type
            tag = reader.read_tag()
            if tag != TAG_ENUM:
                raise ValueError(f"Expected enum tag for server message, got {tag}")
            
            message_variant = reader.read_enum_header()
            
            # Map variant index to message type (based on server message enum)
            if message_variant == 0:  # IdentityToken
                return self._decode_identity_token_bsatn(reader)
            elif message_variant == 1:  # InitialSubscription
                return self._decode_initial_subscription_bsatn(reader)
            elif message_variant == 2:  # TransactionUpdate
                return self._decode_transaction_update_bsatn(reader)
            elif message_variant == 3:  # TransactionUpdateLight
                return self._decode_transaction_update_light_bsatn(reader)
            elif message_variant == 4:  # SubscribeApplied
                return self._decode_subscribe_applied_bsatn(reader)
            elif message_variant == 5:  # UnsubscribeApplied
                return self._decode_unsubscribe_applied_bsatn(reader)
            elif message_variant == 6:  # SubscriptionError
                return self._decode_subscription_error_bsatn(reader)
            elif message_variant == 7:  # SubscribeMultiApplied
                return self._decode_subscribe_multi_applied_bsatn(reader)
            elif message_variant == 8:  # UnsubscribeMultiApplied
                return self._decode_unsubscribe_multi_applied_bsatn(reader)
            elif message_variant == 9:  # OneOffQueryResponse
                return self._decode_oneoff_query_response_bsatn(reader)
            else:
                raise ValueError(f"Unknown server message variant: {message_variant}")
                
        except Exception as e:
            raise ValueError(f"Failed to decode BSATN server message: {e}")
    
    def _decode_identity_token_bsatn(self, reader: 'BsatnReader') -> IdentityToken:
        """Decode IdentityToken from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for IdentityToken, got {tag}")
        
        field_count = reader.read_struct_header()
        
        identity_data = b""
        token = ""
        connection_id_data = b""
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "identity":
                identity_data = reader.read_bytes()
            elif field_name == "token":
                token = reader.read_string()
            elif field_name == "connection_id":
                connection_id_data = reader.read_bytes()
            else:
                # Skip unknown fields for forward compatibility
                reader.skip_value()
        
        return IdentityToken(
            identity=Identity(data=identity_data),
            token=token,
            connection_id=ConnectionId(data=connection_id_data)
        )
    
    def _decode_subscribe_applied_bsatn(self, reader: 'BsatnReader') -> SubscribeApplied:
        """Decode SubscribeApplied from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        from .query_id import QueryId
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for SubscribeApplied, got {tag}")
        
        field_count = reader.read_struct_header()
        
        request_id = 0
        total_host_execution_duration_micros = 0
        query_id = QueryId(0)
        table_id = 0
        table_name = ""
        table_rows = None
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "request_id":
                request_id = reader.read_u32()
            elif field_name == "total_host_execution_duration_micros":
                total_host_execution_duration_micros = reader.read_u64()
            elif field_name == "query_id":
                # Read QueryId struct
                qid_tag = reader.read_tag()
                if qid_tag == TAG_STRUCT:
                    qid_fields = reader.read_struct_header()
                    for _ in range(qid_fields):
                        qid_field = reader.read_field_name()
                        if qid_field == "id":
                            query_id = QueryId(reader.read_u32())
                        else:
                            reader.skip_value()
            elif field_name == "table_id":
                table_id = reader.read_u32()
            elif field_name == "table_name":
                table_name = reader.read_string()
            elif field_name == "table_rows":
                # For now, skip table rows parsing (complex structure)
                reader.skip_value()
            else:
                reader.skip_value()
        
        return SubscribeApplied(
            request_id=request_id,
            total_host_execution_duration_micros=total_host_execution_duration_micros,
            query_id=query_id,
            table_id=table_id,
            table_name=table_name,
            table_rows=table_rows
        )
    
    def _decode_initial_subscription_bsatn(self, reader: 'BsatnReader') -> InitialSubscription:
        """Decode InitialSubscription from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for InitialSubscription, got {tag}")
        
        field_count = reader.read_struct_header()
        
        database_update = DatabaseUpdate(tables=[])
        request_id = 0
        total_host_execution_duration = TimeDuration(nanos=0)
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "database_update":
                # Skip complex database update parsing for now
                reader.skip_value()
            elif field_name == "request_id":
                request_id = reader.read_u32()
            elif field_name == "total_host_execution_duration":
                duration_nanos = reader.read_u64()
                total_host_execution_duration = TimeDuration(nanos=duration_nanos)
            else:
                reader.skip_value()
        
        return InitialSubscription(
            database_update=database_update,
            request_id=request_id,
            total_host_execution_duration=total_host_execution_duration
        )
    
    def _decode_transaction_update_bsatn(self, reader: 'BsatnReader') -> TransactionUpdate:
        """Decode TransactionUpdate from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for TransactionUpdate, got {tag}")
        
        field_count = reader.read_struct_header()
        
        # Default values
        status = "success"
        timestamp = Timestamp(nanos_since_epoch=0)
        caller_identity = Identity(data=b"")
        caller_connection_id = ConnectionId(data=b"")
        reducer_call = ReducerCallInfo(reducer_name="", reducer_id=0, args=b"", request_id=0)
        energy_quanta_used = EnergyQuanta(quanta=0)
        total_host_execution_duration = TimeDuration(nanos=0)
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "status":
                # For now, read as string (simplified)
                status = reader.read_string()
            elif field_name == "timestamp":
                timestamp_nanos = reader.read_u64()
                timestamp = Timestamp(nanos_since_epoch=timestamp_nanos)
            elif field_name == "caller_identity":
                identity_data = reader.read_bytes()
                caller_identity = Identity(data=identity_data)
            elif field_name == "caller_connection_id":
                connection_id_data = reader.read_bytes()
                caller_connection_id = ConnectionId(data=connection_id_data)
            elif field_name == "energy_quanta_used":
                quanta = reader.read_u64()
                energy_quanta_used = EnergyQuanta(quanta=quanta)
            elif field_name == "total_host_execution_duration":
                duration_nanos = reader.read_u64()
                total_host_execution_duration = TimeDuration(nanos=duration_nanos)
            else:
                # Skip complex fields for now
                reader.skip_value()
        
        return TransactionUpdate(
            status=status,
            timestamp=timestamp,
            caller_identity=caller_identity,
            caller_connection_id=caller_connection_id,
            reducer_call=reducer_call,
            energy_quanta_used=energy_quanta_used,
            total_host_execution_duration=total_host_execution_duration
        )
    
    def _decode_transaction_update_light_bsatn(self, reader: 'BsatnReader') -> TransactionUpdateLight:
        """Decode TransactionUpdateLight from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for TransactionUpdateLight, got {tag}")
        
        field_count = reader.read_struct_header()
        
        request_id = 0
        update = DatabaseUpdate(tables=[])
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "request_id":
                request_id = reader.read_u32()
            elif field_name == "update":
                # Skip complex database update parsing for now
                reader.skip_value()
            else:
                reader.skip_value()
        
        return TransactionUpdateLight(
            request_id=request_id,
            update=update
        )
    
    def _decode_subscription_error_bsatn(self, reader: 'BsatnReader') -> SubscriptionError:
        """Decode SubscriptionError from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for SubscriptionError, got {tag}")
        
        field_count = reader.read_struct_header()
        
        total_host_execution_duration_micros = 0
        request_id = None
        query_id = None
        table_id = None
        error = ""
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "total_host_execution_duration_micros":
                total_host_execution_duration_micros = reader.read_u64()
            elif field_name == "request_id":
                request_id = reader.read_u32()
            elif field_name == "query_id":
                query_id = reader.read_u32()
            elif field_name == "table_id":
                table_id = reader.read_u32()
            elif field_name == "error":
                error = reader.read_string()
            else:
                reader.skip_value()
        
        return SubscriptionError(
            total_host_execution_duration_micros=total_host_execution_duration_micros,
            request_id=request_id,
            query_id=query_id,
            table_id=table_id,
            error=error
        )
    
    def _decode_subscribe_multi_applied_bsatn(self, reader: 'BsatnReader') -> SubscribeMultiApplied:
        """Decode SubscribeMultiApplied from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        from .query_id import QueryId
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for SubscribeMultiApplied, got {tag}")
        
        field_count = reader.read_struct_header()
        
        request_id = 0
        total_host_execution_duration_micros = 0
        query_id = QueryId(0)
        update = DatabaseUpdate(tables=[])
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "request_id":
                request_id = reader.read_u32()
            elif field_name == "total_host_execution_duration_micros":
                total_host_execution_duration_micros = reader.read_u64()
            elif field_name == "query_id":
                # Read QueryId struct
                qid_tag = reader.read_tag()
                if qid_tag == TAG_STRUCT:
                    qid_fields = reader.read_struct_header()
                    for _ in range(qid_fields):
                        qid_field = reader.read_field_name()
                        if qid_field == "id":
                            query_id = QueryId(reader.read_u32())
                        else:
                            reader.skip_value()
            elif field_name == "update":
                # Skip complex database update parsing for now
                reader.skip_value()
            else:
                reader.skip_value()
        
        return SubscribeMultiApplied(
            request_id=request_id,
            total_host_execution_duration_micros=total_host_execution_duration_micros,
            query_id=query_id,
            update=update
        )
    
    def _decode_unsubscribe_applied_bsatn(self, reader: 'BsatnReader') -> UnsubscribeApplied:
        """Decode UnsubscribeApplied from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        from .query_id import QueryId
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for UnsubscribeApplied, got {tag}")
        
        field_count = reader.read_struct_header()
        
        request_id = 0
        total_host_execution_duration_micros = 0
        query_id = QueryId(0)
        table_id = 0
        table_name = ""
        table_rows = None
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "request_id":
                request_id = reader.read_u32()
            elif field_name == "total_host_execution_duration_micros":
                total_host_execution_duration_micros = reader.read_u64()
            elif field_name == "query_id":
                # Read QueryId struct
                qid_tag = reader.read_tag()
                if qid_tag == TAG_STRUCT:
                    qid_fields = reader.read_struct_header()
                    for _ in range(qid_fields):
                        qid_field = reader.read_field_name()
                        if qid_field == "id":
                            query_id = QueryId(reader.read_u32())
                        else:
                            reader.skip_value()
            elif field_name == "table_id":
                table_id = reader.read_u32()
            elif field_name == "table_name":
                table_name = reader.read_string()
            elif field_name == "table_rows":
                # Skip table rows parsing for now
                reader.skip_value()
            else:
                reader.skip_value()
        
        return UnsubscribeApplied(
            request_id=request_id,
            total_host_execution_duration_micros=total_host_execution_duration_micros,
            query_id=query_id,
            table_id=table_id,
            table_name=table_name,
            table_rows=table_rows
        )
    
    def _decode_unsubscribe_multi_applied_bsatn(self, reader: 'BsatnReader') -> UnsubscribeMultiApplied:
        """Decode UnsubscribeMultiApplied from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        from .query_id import QueryId
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for UnsubscribeMultiApplied, got {tag}")
        
        field_count = reader.read_struct_header()
        
        request_id = 0
        total_host_execution_duration_micros = 0
        query_id = QueryId(0)
        update = DatabaseUpdate(tables=[])
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "request_id":
                request_id = reader.read_u32()
            elif field_name == "total_host_execution_duration_micros":
                total_host_execution_duration_micros = reader.read_u64()
            elif field_name == "query_id":
                # Read QueryId struct
                qid_tag = reader.read_tag()
                if qid_tag == TAG_STRUCT:
                    qid_fields = reader.read_struct_header()
                    for _ in range(qid_fields):
                        qid_field = reader.read_field_name()
                        if qid_field == "id":
                            query_id = QueryId(reader.read_u32())
                        else:
                            reader.skip_value()
            elif field_name == "update":
                # Skip complex database update parsing for now
                reader.skip_value()
            else:
                reader.skip_value()
        
        return UnsubscribeMultiApplied(
            request_id=request_id,
            total_host_execution_duration_micros=total_host_execution_duration_micros,
            query_id=query_id,
            update=update
        )
    
    def _decode_oneoff_query_response_bsatn(self, reader: 'BsatnReader') -> OneOffQueryResponse:
        """Decode OneOffQueryResponse from BSATN."""
        from .bsatn.constants import TAG_STRUCT
        
        # Read struct header
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for OneOffQueryResponse, got {tag}")
        
        field_count = reader.read_struct_header()
        
        message_id = b""
        error = None
        tables = []
        total_host_execution_duration = TimeDuration(nanos=0)
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "message_id":
                message_id = reader.read_bytes()
            elif field_name == "error":
                # Check if error is present (Option type)
                error_tag = reader.read_tag()
                if error_tag == 0x11:  # TAG_OPTION_SOME
                    error = reader.read_string()
                # else TAG_OPTION_NONE, error remains None
            elif field_name == "tables":
                # Skip complex table parsing for now
                reader.skip_value()
            elif field_name == "total_host_execution_duration":
                duration_nanos = reader.read_u64()
                total_host_execution_duration = TimeDuration(nanos=duration_nanos)
            else:
                reader.skip_value()
        
        return OneOffQueryResponse(
            message_id=message_id,
            error=error,
            tables=tables,
            total_host_execution_duration=total_host_execution_duration
        )


def generate_request_id() -> int:
    """Generate a unique request ID."""
    return uuid.uuid4().int & 0xFFFFFFFF
