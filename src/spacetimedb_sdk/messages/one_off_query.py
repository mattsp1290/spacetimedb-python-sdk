"""
Enhanced OneOffQuery Message Types for SpacetimeDB Protocol v1.1.1

This module implements the enhanced one-off query message types with proper
validation, serialization, and error handling capabilities.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid

from ..bsatn.writer import BsatnWriter
from ..bsatn.reader import BsatnReader
from ..bsatn.constants import TAG_ENUM, TAG_STRUCT, TAG_STRING, TAG_BYTES, TAG_ARRAY, TAG_U64, TAG_OPTION_NONE, TAG_OPTION_SOME


@dataclass
class OneOffQueryMessage:
    """
    Enhanced one-off query message with validation and serialization support.
    
    Executes a single query without creating a subscription, returning results directly.
    """
    message_id: bytes
    query_string: str
    
    def __post_init__(self):
        """Validate message fields after initialization."""
        if not isinstance(self.message_id, bytes) or len(self.message_id) == 0:
            raise ValueError("Message ID must be non-empty bytes")
        
        if not isinstance(self.query_string, str) or not self.query_string.strip():
            raise ValueError("Query string must be a non-empty string")
    
    def __eq__(self, other) -> bool:
        """Test equality with another OneOffQueryMessage."""
        if not isinstance(other, OneOffQueryMessage):
            return False
        return (self.message_id == other.message_id and 
                self.query_string == other.query_string)
    
    def __hash__(self) -> int:
        """Return hash for use in sets and dicts."""
        return hash((self.message_id, self.query_string))
    
    def __str__(self) -> str:
        """Return string representation."""
        query_preview = self.query_string[:50] + "..." if len(self.query_string) > 50 else self.query_string
        return f"OneOffQuery(message_id={self.message_id.hex()[:8]}..., query='{query_preview}')"
    
    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"OneOffQueryMessage(message_id={self.message_id!r}, query_string={self.query_string!r})"
    
    def write_bsatn(self, writer: BsatnWriter) -> None:
        """
        Write this message to a BSATN writer.
        
        Format: enum variant 6 (OneOffQuery) with struct containing
        message_id (bytes), query_string (string)
        """
        # Write enum variant for OneOffQuery (variant 6)
        writer.write_enum_header(6)
        
        # Write struct with 2 fields
        writer.write_struct_header(2)
        
        # Field 1: message_id
        writer.write_field_name("message_id")
        writer.write_bytes(self.message_id)
        
        # Field 2: query_string
        writer.write_field_name("query_string")
        writer.write_string(self.query_string)
    
    @classmethod
    def read_bsatn(cls, reader: BsatnReader) -> 'OneOffQueryMessage':
        """
        Read a OneOffQueryMessage from a BSATN reader.
        """
        # Read the enum tag first
        tag = reader.read_tag()
        if tag != TAG_ENUM:
            raise ValueError(f"Expected enum tag for OneOffQuery, got {tag}")
        
        # Read enum header (should be variant 6)
        variant = reader.read_enum_header()
        if variant != 6:
            raise ValueError(f"Expected OneOffQuery variant (6), got {variant}")
        
        # Read struct tag
        struct_tag = reader.read_tag()
        if struct_tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for OneOffQuery, got {struct_tag}")
        
        # Read struct header (should be 2 fields)
        field_count = reader.read_struct_header()
        if field_count != 2:
            raise ValueError(f"Expected 2 fields, got {field_count}")
        
        # Read fields
        fields = {}
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "message_id":
                tag = reader.read_tag()
                if tag != TAG_BYTES:
                    raise ValueError(f"Expected bytes tag for message_id field, got {tag}")
                fields["message_id"] = reader.read_bytes_raw()
            elif field_name == "query_string":
                tag = reader.read_tag()
                if tag != TAG_STRING:
                    raise ValueError(f"Expected string tag for query_string field, got {tag}")
                fields["query_string"] = reader.read_string()
            else:
                raise ValueError(f"Unknown field: {field_name}")
        
        return cls(**fields)
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON representation."""
        return {
            "OneOffQuery": {
                "message_id": list(self.message_id),  # Convert bytes to list for JSON
                "query_string": self.query_string
            }
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'OneOffQueryMessage':
        """Create from JSON representation."""
        if "OneOffQuery" not in data:
            raise ValueError("Invalid JSON format for OneOffQuery")
        
        msg_data = data["OneOffQuery"]
        return cls(
            message_id=bytes(msg_data["message_id"]),  # Convert list back to bytes
            query_string=msg_data["query_string"]
        )
    
    @classmethod
    def generate(cls, query_string: str) -> 'OneOffQueryMessage':
        """Generate a new OneOffQuery with random message_id."""
        return cls(
            message_id=uuid.uuid4().bytes,
            query_string=query_string
        )


@dataclass
class OneOffTable:
    """
    A table result included in OneOffQueryResponse.
    """
    table_name: str
    rows: List[Dict[str, Any]]
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON representation."""
        return {
            "table_name": self.table_name,
            "rows": self.rows
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'OneOffTable':
        """Create from JSON representation."""
        return cls(
            table_name=data["table_name"],
            rows=data["rows"]
        )


@dataclass
class OneOffQueryResponseMessage:
    """
    Enhanced response to a one-off query with error handling support.
    """
    message_id: bytes
    error: Optional[str]
    tables: List[OneOffTable]
    total_host_execution_duration_micros: int
    
    def __post_init__(self):
        """Validate message fields after initialization."""
        if not isinstance(self.message_id, bytes) or len(self.message_id) == 0:
            raise ValueError("Message ID must be non-empty bytes")
        
        if not isinstance(self.total_host_execution_duration_micros, int) or self.total_host_execution_duration_micros < 0:
            raise ValueError("Execution duration must be a non-negative integer")
        
        if not isinstance(self.tables, list):
            raise ValueError("Tables must be a list")
        
        # Convert dict tables to OneOffTable objects if needed
        converted_tables = []
        for table in self.tables:
            if isinstance(table, dict):
                converted_tables.append(OneOffTable.from_json(table))
            elif isinstance(table, OneOffTable):
                converted_tables.append(table)
            else:
                raise ValueError(f"Invalid table type: {type(table)}")
        self.tables = converted_tables
    
    def __eq__(self, other) -> bool:
        """Test equality with another OneOffQueryResponseMessage."""
        if not isinstance(other, OneOffQueryResponseMessage):
            return False
        return (self.message_id == other.message_id and 
                self.error == other.error and
                self.tables == other.tables and
                self.total_host_execution_duration_micros == other.total_host_execution_duration_micros)
    
    def __hash__(self) -> int:
        """Return hash for use in sets and dicts."""
        return hash((self.message_id, self.error, tuple(self.tables), self.total_host_execution_duration_micros))
    
    def __str__(self) -> str:
        """Return string representation."""
        status = "ERROR" if self.has_error() else "SUCCESS"
        table_count = len(self.tables)
        duration_ms = self.total_host_execution_duration_micros / 1000
        return f"OneOffQueryResponse({status}, {table_count} tables, {duration_ms:.1f}ms)"
    
    def __repr__(self) -> str:
        """Return detailed representation."""
        return (f"OneOffQueryResponseMessage(message_id={self.message_id!r}, "
                f"error={self.error!r}, tables={self.tables!r}, "
                f"total_host_execution_duration_micros={self.total_host_execution_duration_micros})")
    
    def has_error(self) -> bool:
        """Check if this response contains an error."""
        return self.error is not None and self.error != ""
    
    def is_success(self) -> bool:
        """Check if this response is successful (no error)."""
        return not self.has_error()
    
    def get_error_message(self) -> Optional[str]:
        """Get the error message if present."""
        return self.error if self.has_error() else None
    
    def get_table_count(self) -> int:
        """Get the number of tables in the response."""
        return len(self.tables)
    
    def get_total_rows(self) -> int:
        """Get the total number of rows across all tables."""
        return sum(len(table.rows) for table in self.tables)
    
    def write_bsatn(self, writer: BsatnWriter) -> None:
        """
        Write this message to a BSATN writer.
        
        Format: struct containing message_id (bytes), error (option<string>), 
        tables (array), total_host_execution_duration (u64)
        """
        # Write struct with 4 fields
        writer.write_struct_header(4)
        
        # Field 1: message_id
        writer.write_field_name("message_id")
        writer.write_bytes(self.message_id)
        
        # Field 2: error (Option<String>)
        writer.write_field_name("error")
        if self.error is None:
            writer.write_option_none()
        else:
            writer.write_option_some()
            writer.write_string(self.error)
        
        # Field 3: tables (Array<OneOffTable>)
        writer.write_field_name("tables")
        writer.write_array_header(len(self.tables))
        for table in self.tables:
            # Write each table as a struct
            writer.write_struct_header(2)
            writer.write_field_name("table_name")
            writer.write_string(table.table_name)
            writer.write_field_name("rows")
            # For simplicity, serialize rows as a single bytes field (JSON-encoded)
            import json
            rows_json = json.dumps(table.rows).encode('utf-8')
            writer.write_bytes(rows_json)
        
        # Field 4: total_host_execution_duration_micros
        writer.write_field_name("total_host_execution_duration_micros")
        writer.write_u64(self.total_host_execution_duration_micros)
    
    @classmethod
    def read_bsatn(cls, reader: BsatnReader) -> 'OneOffQueryResponseMessage':
        """
        Read a OneOffQueryResponseMessage from a BSATN reader.
        """
        # Read struct tag
        tag = reader.read_tag()
        if tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for OneOffQueryResponse, got {tag}")
        
        # Read struct header (should be 4 fields)
        field_count = reader.read_struct_header()
        if field_count != 4:
            raise ValueError(f"Expected 4 fields, got {field_count}")
        
        # Read fields
        fields = {}
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "message_id":
                tag = reader.read_tag()
                if tag != TAG_BYTES:
                    raise ValueError(f"Expected bytes tag for message_id field, got {tag}")
                fields["message_id"] = reader.read_bytes_raw()
            elif field_name == "error":
                tag = reader.read_tag()
                if tag == TAG_OPTION_NONE:
                    fields["error"] = None
                elif tag == TAG_OPTION_SOME:
                    string_tag = reader.read_tag()
                    if string_tag != TAG_STRING:
                        raise ValueError(f"Expected string tag for error option, got {string_tag}")
                    fields["error"] = reader.read_string()
                else:
                    raise ValueError(f"Expected option tag for error field, got {tag}")
            elif field_name == "tables":
                tag = reader.read_tag()
                if tag != TAG_ARRAY:
                    raise ValueError(f"Expected array tag for tables field, got {tag}")
                count = reader.read_array_header()
                tables = []
                for _ in range(count):
                    # Read table struct
                    table_tag = reader.read_tag()
                    if table_tag != TAG_STRUCT:
                        raise ValueError(f"Expected struct tag for table, got {table_tag}")
                    table_field_count = reader.read_struct_header()
                    if table_field_count != 2:
                        raise ValueError(f"Expected 2 fields in table, got {table_field_count}")
                    
                    table_name = None
                    rows = None
                    for _ in range(table_field_count):
                        table_field_name = reader.read_field_name()
                        if table_field_name == "table_name":
                            name_tag = reader.read_tag()
                            if name_tag != TAG_STRING:
                                raise ValueError(f"Expected string tag for table_name, got {name_tag}")
                            table_name = reader.read_string()
                        elif table_field_name == "rows":
                            rows_tag = reader.read_tag()
                            if rows_tag != TAG_BYTES:
                                raise ValueError(f"Expected bytes tag for rows, got {rows_tag}")
                            rows_json = reader.read_bytes_raw()
                            import json
                            rows = json.loads(rows_json.decode('utf-8'))
                    
                    tables.append(OneOffTable(table_name=table_name, rows=rows))
                fields["tables"] = tables
            elif field_name == "total_host_execution_duration_micros":
                tag = reader.read_tag()
                if tag != TAG_U64:
                    raise ValueError(f"Expected u64 tag for duration field, got {tag}")
                fields["total_host_execution_duration_micros"] = reader.read_u64()
            else:
                raise ValueError(f"Unknown field: {field_name}")
        
        return cls(**fields)
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON representation."""
        return {
            "OneOffQueryResponse": {
                "message_id": list(self.message_id),
                "error": self.error,
                "tables": [table.to_json() for table in self.tables],
                "total_host_execution_duration_micros": self.total_host_execution_duration_micros
            }
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'OneOffQueryResponseMessage':
        """Create from JSON representation."""
        if "OneOffQueryResponse" not in data:
            raise ValueError("Invalid JSON format for OneOffQueryResponse")
        
        msg_data = data["OneOffQueryResponse"]
        return cls(
            message_id=bytes(msg_data["message_id"]),
            error=msg_data["error"],
            tables=[OneOffTable.from_json(table) for table in msg_data["tables"]],
            total_host_execution_duration_micros=msg_data["total_host_execution_duration_micros"]
        )


# Register message types with BSATN system for automatic encoding/decoding
def register_bsatn_support():
    """Register one-off query message types with the BSATN system."""
    try:
        from ..bsatn.utils import encode_to_writer, decode_from_reader
        
        # This will be enhanced when we integrate with the main BSATN system
        # For now, each message type handles its own serialization via write_bsatn/read_bsatn
        pass
    except ImportError:
        pass


# Auto-register on import
register_bsatn_support() 