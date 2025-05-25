"""
Enhanced Server Message Types for SpacetimeDB Protocol v1.1.1

This module provides enhanced server message types with full BSATN serialization,
validation, and factory patterns for parsing server responses.
"""

from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import struct

if TYPE_CHECKING:
    from ..bsatn.writer import BsatnWriter
    from ..bsatn.reader import BsatnReader
    from ..query_id import QueryId


class ServerMessageError(Exception):
    """Base exception for server message validation errors."""
    pass


class SubscriptionErrorCategory(Enum):
    """Categories of subscription errors."""
    QUERY_PARSE_ERROR = "query_parse_error"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT_ERROR = "timeout_error"  
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERNAL_ERROR = "internal_error"
    UNKNOWN = "unknown"


@dataclass
class EnhancedTableUpdate:
    """Enhanced table update with analysis capabilities."""
    table_id: int
    table_name: str
    num_rows: int
    inserts: List[Dict[str, Any]]
    deletes: List[Dict[str, Any]]
    
    def get_insert_count(self) -> int:
        """Get the number of inserted rows."""
        return len(self.inserts)
    
    def get_delete_count(self) -> int:
        """Get the number of deleted rows."""
        return len(self.deletes)
    
    def has_changes(self) -> bool:
        """Check if this table has any changes."""
        return len(self.inserts) > 0 or len(self.deletes) > 0
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write this TableUpdate to BSATN."""
        writer.write_struct_header(5)  # table_id, table_name, num_rows, inserts, deletes
        
        writer.write_field_name("table_id")
        writer.write_u32(self.table_id)
        
        writer.write_field_name("table_name")
        writer.write_string(self.table_name)
        
        writer.write_field_name("num_rows")
        writer.write_u32(self.num_rows)
        
        writer.write_field_name("inserts")
        writer.write_array_header(len(self.inserts))
        for insert in self.inserts:
            # Simplified - would need proper row serialization
            writer.write_struct_header(len(insert))
            for key, value in insert.items():
                writer.write_field_name(key)
                # Simplified value encoding
                if isinstance(value, str):
                    writer.write_string(value)
                elif isinstance(value, int):
                    writer.write_i64(value)
                else:
                    writer.write_string(str(value))
        
        writer.write_field_name("deletes")
        writer.write_array_header(len(self.deletes))
        for delete in self.deletes:
            # Similar to inserts
            writer.write_struct_header(len(delete))
            for key, value in delete.items():
                writer.write_field_name(key)
                if isinstance(value, str):
                    writer.write_string(value)
                elif isinstance(value, int):
                    writer.write_i64(value)
                else:
                    writer.write_string(str(value))


@dataclass
class EnhancedDatabaseUpdate:
    """Enhanced database update with analysis capabilities."""
    tables: List[EnhancedTableUpdate]
    
    def get_affected_table_names(self) -> List[str]:
        """Get list of affected table names."""
        return [table.table_name for table in self.tables if table.has_changes()]
    
    def get_total_rows_affected(self) -> int:
        """Get total number of rows affected across all tables."""
        return sum(table.get_insert_count() + table.get_delete_count() for table in self.tables)
    
    def has_table(self, table_name: str) -> bool:
        """Check if update contains changes for a specific table."""
        return any(table.table_name == table_name and table.has_changes() for table in self.tables)
    
    def get_table_update(self, table_name: str) -> Optional[EnhancedTableUpdate]:
        """Get the update for a specific table."""
        for table in self.tables:
            if table.table_name == table_name:
                return table
        return None


@dataclass
class EnhancedSubscribeApplied:
    """Enhanced SubscribeApplied message with BSATN support."""
    request_id: int
    total_host_execution_duration_micros: int
    query_id: 'QueryId'
    table_id: int
    table_name: str
    table_rows: Optional[EnhancedTableUpdate]
    
    def get_execution_duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        return self.total_host_execution_duration_micros / 1000.0
    
    def has_results(self) -> bool:
        """Check if the subscription has any initial results."""
        return self.table_rows is not None and self.table_rows.has_changes()
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write this SubscribeApplied to BSATN."""
        writer.write_struct_header(6)
        
        writer.write_field_name("request_id")
        writer.write_u32(self.request_id)
        
        writer.write_field_name("total_host_execution_duration_micros")
        writer.write_u64(self.total_host_execution_duration_micros)
        
        writer.write_field_name("query_id")
        self.query_id.write_bsatn(writer)
        
        writer.write_field_name("table_id")
        writer.write_u32(self.table_id)
        
        writer.write_field_name("table_name")
        writer.write_string(self.table_name)
        
        writer.write_field_name("table_rows")
        if self.table_rows:
            writer.write_option_some_tag()
            self.table_rows.write_bsatn(writer)
        else:
            writer.write_option_none()
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedSubscribeApplied':
        """Read SubscribeApplied from BSATN."""
        from ..bsatn.constants import TAG_STRUCT
        from ..query_id import QueryId
        
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ServerMessageError(f"Expected struct tag for SubscribeApplied, got {tag}")
        
        field_count = reader.read_struct_header()
        if field_count != 6:
            raise ServerMessageError(f"Expected 6 fields for SubscribeApplied, got {field_count}")
        
        # Read fields in order
        reader.read_field_name()  # request_id
        request_id = reader.read_u32()
        
        reader.read_field_name()  # total_host_execution_duration_micros
        duration = reader.read_u64()
        
        reader.read_field_name()  # query_id
        query_id = QueryId.read_bsatn(reader)
        
        reader.read_field_name()  # table_id
        table_id = reader.read_u32()
        
        reader.read_field_name()  # table_name
        table_name = reader.read_string()
        
        reader.read_field_name()  # table_rows
        # Simplified - would need proper table row parsing
        table_rows = None  # TODO: Parse table rows properly
        
        return cls(
            request_id=request_id,
            total_host_execution_duration_micros=duration,
            query_id=query_id,
            table_id=table_id,
            table_name=table_name,
            table_rows=table_rows
        )


@dataclass
class EnhancedSubscriptionError:
    """Enhanced SubscriptionError message with categorization and BSATN support."""
    total_host_execution_duration_micros: int
    request_id: Optional[int]
    query_id: Optional[int]
    table_id: Optional[int]
    error: str
    
    def get_execution_duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        return self.total_host_execution_duration_micros / 1000.0
    
    def error_category(self) -> SubscriptionErrorCategory:
        """Categorize the error based on the error message."""
        error_lower = self.error.lower()
        
        if "parse" in error_lower or "syntax" in error_lower:
            return SubscriptionErrorCategory.QUERY_PARSE_ERROR
        elif "permission" in error_lower or "denied" in error_lower:
            return SubscriptionErrorCategory.PERMISSION_DENIED
        elif "timeout" in error_lower:
            return SubscriptionErrorCategory.TIMEOUT_ERROR
        elif "resource" in error_lower or "exhausted" in error_lower:
            return SubscriptionErrorCategory.RESOURCE_EXHAUSTED
        elif "internal" in error_lower:
            return SubscriptionErrorCategory.INTERNAL_ERROR
        else:
            return SubscriptionErrorCategory.UNKNOWN
    
    def is_timeout_error(self) -> bool:
        """Check if this is a timeout error."""
        return self.error_category() == SubscriptionErrorCategory.TIMEOUT_ERROR
    
    def is_retryable(self) -> bool:
        """Check if this error is potentially retryable."""
        category = self.error_category()
        return category in (
            SubscriptionErrorCategory.TIMEOUT_ERROR,
            SubscriptionErrorCategory.RESOURCE_EXHAUSTED,
            SubscriptionErrorCategory.INTERNAL_ERROR
        )
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write this SubscriptionError to BSATN."""
        writer.write_struct_header(5)
        
        writer.write_field_name("total_host_execution_duration_micros")
        writer.write_u64(self.total_host_execution_duration_micros)
        
        writer.write_field_name("request_id")
        if self.request_id is not None:
            writer.write_option_some_tag()
            writer.write_u32(self.request_id)
        else:
            writer.write_option_none()
        
        writer.write_field_name("query_id")
        if self.query_id is not None:
            writer.write_option_some_tag()
            writer.write_u32(self.query_id)
        else:
            writer.write_option_none()
        
        writer.write_field_name("table_id")
        if self.table_id is not None:
            writer.write_option_some_tag()
            writer.write_u32(self.table_id)
        else:
            writer.write_option_none()
        
        writer.write_field_name("error")
        writer.write_string(self.error)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedSubscriptionError':
        """Read SubscriptionError from BSATN."""
        from ..bsatn.constants import TAG_STRUCT, TAG_OPTION_NONE, TAG_OPTION_SOME
        
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ServerMessageError(f"Expected struct tag for SubscriptionError, got {tag}")
        
        field_count = reader.read_struct_header()
        if field_count != 5:
            raise ServerMessageError(f"Expected 5 fields for SubscriptionError, got {field_count}")
        
        reader.read_field_name()  # total_host_execution_duration_micros
        duration = reader.read_u64()
        
        reader.read_field_name()  # request_id
        request_id_tag = reader.read_tag()
        request_id = reader.read_u32() if request_id_tag == TAG_OPTION_SOME else None
        
        reader.read_field_name()  # query_id
        query_id_tag = reader.read_tag()
        query_id = reader.read_u32() if query_id_tag == TAG_OPTION_SOME else None
        
        reader.read_field_name()  # table_id
        table_id_tag = reader.read_tag()
        table_id = reader.read_u32() if table_id_tag == TAG_OPTION_SOME else None
        
        reader.read_field_name()  # error
        error = reader.read_string()
        
        return cls(
            total_host_execution_duration_micros=duration,
            request_id=request_id,
            query_id=query_id,
            table_id=table_id,
            error=error
        )


@dataclass
class EnhancedSubscribeMultiApplied:
    """Enhanced SubscribeMultiApplied message with analysis capabilities."""
    request_id: int
    total_host_execution_duration_micros: int
    query_id: 'QueryId'
    update: Optional[EnhancedDatabaseUpdate]
    
    def get_execution_duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        return self.total_host_execution_duration_micros / 1000.0
    
    def get_affected_tables(self) -> List[str]:
        """Get list of affected table names."""
        if self.update:
            return self.update.get_affected_table_names()
        return []
    
    def get_row_count(self) -> int:
        """Get total number of rows affected."""
        if self.update:
            return self.update.get_total_rows_affected()
        return 0
    
    def has_results(self) -> bool:
        """Check if the subscription has any results."""
        return self.update is not None and self.update.get_total_rows_affected() > 0
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write this SubscribeMultiApplied to BSATN."""
        writer.write_struct_header(4)
        
        writer.write_field_name("request_id")
        writer.write_u32(self.request_id)
        
        writer.write_field_name("total_host_execution_duration_micros")
        writer.write_u64(self.total_host_execution_duration_micros)
        
        writer.write_field_name("query_id")
        self.query_id.write_bsatn(writer)
        
        writer.write_field_name("update")
        if self.update:
            writer.write_option_some_tag()
            writer.write_array_header(len(self.update.tables))
            for table in self.update.tables:
                table.write_bsatn(writer)
        else:
            writer.write_option_none()
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedSubscribeMultiApplied':
        """Read SubscribeMultiApplied from BSATN."""
        from ..bsatn.constants import TAG_STRUCT
        from ..query_id import QueryId
        
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ServerMessageError(f"Expected struct tag for SubscribeMultiApplied, got {tag}")
        
        field_count = reader.read_struct_header()
        if field_count != 4:
            raise ServerMessageError(f"Expected 4 fields for SubscribeMultiApplied, got {field_count}")
        
        reader.read_field_name()  # request_id
        request_id = reader.read_u32()
        
        reader.read_field_name()  # total_host_execution_duration_micros
        duration = reader.read_u64()
        
        reader.read_field_name()  # query_id
        query_id = QueryId.read_bsatn(reader)
        
        reader.read_field_name()  # update
        # Simplified - would need proper database update parsing
        update = None  # TODO: Parse database update properly
        
        return cls(
            request_id=request_id,
            total_host_execution_duration_micros=duration,
            query_id=query_id,
            update=update
        )


@dataclass
class EnhancedTransactionUpdateLight:
    """Enhanced TransactionUpdateLight with analysis capabilities."""
    request_id: int
    update: Optional[EnhancedDatabaseUpdate]
    
    def get_affected_table_names(self) -> List[str]:
        """Get list of affected table names."""
        if self.update:
            return self.update.get_affected_table_names()
        return []
    
    def get_total_rows_affected(self) -> int:
        """Get total number of rows affected."""
        if self.update:
            return self.update.get_total_rows_affected()
        return 0
    
    def has_table(self, table_name: str) -> bool:
        """Check if update affects a specific table."""
        if self.update:
            return self.update.has_table(table_name)
        return False
    
    def get_table_update(self, table_name: str) -> Optional[EnhancedTableUpdate]:
        """Get the update for a specific table."""
        if self.update:
            return self.update.get_table_update(table_name)
        return None
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write this TransactionUpdateLight to BSATN."""
        writer.write_struct_header(2)
        
        writer.write_field_name("request_id")
        writer.write_u32(self.request_id)
        
        writer.write_field_name("update")
        if self.update:
            writer.write_option_some_tag()
            writer.write_array_header(len(self.update.tables))
            for table in self.update.tables:
                table.write_bsatn(writer)
        else:
            writer.write_option_none()
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedTransactionUpdateLight':
        """Read TransactionUpdateLight from BSATN."""
        from ..bsatn.constants import TAG_STRUCT
        
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ServerMessageError(f"Expected struct tag for TransactionUpdateLight, got {tag}")
        
        field_count = reader.read_struct_header()
        if field_count != 2:
            raise ServerMessageError(f"Expected 2 fields for TransactionUpdateLight, got {field_count}")
        
        reader.read_field_name()  # request_id
        request_id = reader.read_u32()
        
        reader.read_field_name()  # update
        # Simplified - would need proper database update parsing
        update = None  # TODO: Parse database update properly
        
        return cls(
            request_id=request_id,
            update=update
        )


@dataclass
class EnhancedIdentityToken:
    """Enhanced IdentityToken with validation and ConnectionId integration."""
    identity: 'Identity'
    token: str
    connection_id: 'ConnectionId'
    
    def validate_token(self) -> bool:
        """Validate the token format (simplified validation)."""
        return len(self.token) > 0 and all(c.isalnum() or c == '_' for c in self.token)
    
    def is_connection_active(self) -> bool:
        """Check if the connection appears to be active (simplified check)."""
        return len(self.connection_id.data) > 0
    
    def get_token_length(self) -> int:
        """Get the length of the token."""
        return len(self.token)
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write this IdentityToken to BSATN."""
        writer.write_struct_header(3)
        
        writer.write_field_name("identity")
        writer.write_bytes(self.identity.data)
        
        writer.write_field_name("token")
        writer.write_string(self.token)
        
        writer.write_field_name("connection_id")
        writer.write_bytes(self.connection_id.data)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedIdentityToken':
        """Read IdentityToken from BSATN."""
        from ..bsatn.constants import TAG_STRUCT
        from ..protocol import Identity, ConnectionId
        
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ServerMessageError(f"Expected struct tag for IdentityToken, got {tag}")
        
        field_count = reader.read_struct_header()
        if field_count != 3:
            raise ServerMessageError(f"Expected 3 fields for IdentityToken, got {field_count}")
        
        reader.read_field_name()  # identity
        identity_data = reader.read_bytes_raw()
        
        reader.read_field_name()  # token
        token = reader.read_string()
        
        reader.read_field_name()  # connection_id
        connection_id_data = reader.read_bytes_raw()
        
        return cls(
            identity=Identity(data=identity_data),
            token=token,
            connection_id=ConnectionId(data=connection_id_data)
        )


class ServerMessageValidator:
    """Validator for server messages."""
    
    def validate_subscribe_applied(self, message: EnhancedSubscribeApplied) -> bool:
        """Validate a SubscribeApplied message."""
        if message.request_id < 0:
            raise ServerMessageError("request_id must be non-negative")
        if message.total_host_execution_duration_micros < 0:
            raise ServerMessageError("execution duration must be non-negative")
        if not message.table_name:
            raise ServerMessageError("table_name cannot be empty")
        return True
    
    def validate_subscription_error(self, message: EnhancedSubscriptionError) -> bool:
        """Validate a SubscriptionError message."""
        if message.total_host_execution_duration_micros < 0:
            raise ServerMessageError("execution duration must be non-negative")
        if not message.error:
            raise ServerMessageError("error message cannot be empty")
        return True
    
    def validate_identity_token(self, message: EnhancedIdentityToken) -> bool:
        """Validate an IdentityToken message."""
        if not message.validate_token():
            raise ServerMessageError("invalid token format")
        if len(message.identity.data) == 0:
            raise ServerMessageError("identity data cannot be empty")
        return True


class ServerMessageFactory:
    """Factory for creating server messages from raw data."""
    
    def __init__(self):
        self.validator = ServerMessageValidator()
    
    def detect_message_type(self, data: Union[Dict[str, Any], bytes]) -> str:
        """Detect the message type from raw data."""
        if isinstance(data, dict):
            return self._detect_json_message_type(data)
        else:
            return self._detect_bsatn_message_type(data)
    
    def _detect_json_message_type(self, data: Dict[str, Any]) -> str:
        """Detect message type from JSON data."""
        message_types = [
            "SubscribeApplied", "SubscriptionError", "SubscribeMultiApplied",
            "UnsubscribeApplied", "UnsubscribeMultiApplied", "TransactionUpdateLight",
            "IdentityToken"
        ]
        
        for msg_type in message_types:
            if msg_type in data:
                return msg_type
        
        raise ServerMessageError(f"Unknown message type in JSON data: {list(data.keys())}")
    
    def _detect_bsatn_message_type(self, data: bytes) -> str:
        """Detect message type from BSATN data (simplified)."""
        # In a real implementation, this would parse the BSATN enum header
        # For now, return a placeholder
        return "Unknown"
    
    def create_from_json(self, data: Dict[str, Any]) -> Any:
        """Create a server message from JSON data."""
        msg_type = self.detect_message_type(data)
        
        if msg_type == "SubscribeApplied":
            return self._create_subscribe_applied_from_json(data[msg_type])
        elif msg_type == "SubscriptionError":
            return self._create_subscription_error_from_json(data[msg_type])
        elif msg_type == "IdentityToken":
            return self._create_identity_token_from_json(data[msg_type])
        else:
            raise ServerMessageError(f"Unsupported message type: {msg_type}")
    
    def create_from_bsatn(self, data: bytes) -> Any:
        """Create a server message from BSATN data."""
        # TODO: Implement BSATN parsing
        raise NotImplementedError("BSATN parsing not yet implemented")
    
    def _create_subscribe_applied_from_json(self, data: Dict[str, Any]) -> EnhancedSubscribeApplied:
        """Create SubscribeApplied from JSON data."""
        from ..query_id import QueryId
        
        message = EnhancedSubscribeApplied(
            request_id=data["request_id"],
            total_host_execution_duration_micros=data["total_host_execution_duration_micros"],
            query_id=QueryId(data["query_id"]["id"]),
            table_id=data["table_id"],
            table_name=data["table_name"],
            table_rows=None  # Simplified
        )
        
        self.validator.validate_subscribe_applied(message)
        return message
    
    def _create_subscription_error_from_json(self, data: Dict[str, Any]) -> EnhancedSubscriptionError:
        """Create SubscriptionError from JSON data."""
        message = EnhancedSubscriptionError(
            total_host_execution_duration_micros=data["total_host_execution_duration_micros"],
            request_id=data.get("request_id"),
            query_id=data.get("query_id"),
            table_id=data.get("table_id"),
            error=data["error"]
        )
        
        self.validator.validate_subscription_error(message)
        return message
    
    def _create_identity_token_from_json(self, data: Dict[str, Any]) -> EnhancedIdentityToken:
        """Create IdentityToken from JSON data."""
        from ..protocol import Identity, ConnectionId
        
        message = EnhancedIdentityToken(
            identity=Identity.from_hex(data["identity"]),
            token=data["token"],
            connection_id=ConnectionId.from_hex(data["connection_id"])
        )
        
        self.validator.validate_identity_token(message)
        return message


def validate_server_message(message: Any) -> bool:
    """Validate any server message."""
    validator = ServerMessageValidator()
    
    if isinstance(message, EnhancedSubscribeApplied):
        return validator.validate_subscribe_applied(message)
    elif isinstance(message, EnhancedSubscriptionError):
        return validator.validate_subscription_error(message)
    elif isinstance(message, EnhancedIdentityToken):
        return validator.validate_identity_token(message)
    else:
        raise ServerMessageError(f"Unknown message type for validation: {type(message)}")


# Export all enhanced types
__all__ = [
    'ServerMessageError',
    'SubscriptionErrorCategory',
    'EnhancedTableUpdate',
    'EnhancedDatabaseUpdate',
    'EnhancedSubscribeApplied',
    'EnhancedSubscriptionError',
    'EnhancedSubscribeMultiApplied',
    'EnhancedTransactionUpdateLight',
    'EnhancedIdentityToken',
    'ServerMessageValidator',
    'ServerMessageFactory',
    'validate_server_message'
] 