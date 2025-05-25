"""
Modern Subscribe Message Types for SpacetimeDB Protocol v1.1.1

This module implements the modern subscription message types with proper
serialization, validation, and protocol integration.
"""

from typing import List, Dict, Any, Union
from dataclasses import dataclass

from ..query_id import QueryId
from ..bsatn.writer import BsatnWriter
from ..bsatn.reader import BsatnReader
from ..bsatn.constants import TAG_ENUM, TAG_STRUCT, TAG_STRING, TAG_ARRAY, TAG_U32


@dataclass
class SubscribeSingleMessage:
    """
    Register a subscription to a single query with QueryId tracking.
    
    This is the modern equivalent of Subscribe with enhanced tracking capabilities.
    """
    query: str
    request_id: int
    query_id: QueryId
    
    def __post_init__(self):
        """Validate message fields after initialization."""
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("Query must be a non-empty string")
        
        if not isinstance(self.request_id, int) or self.request_id < 0:
            raise ValueError("Request ID must be a non-negative integer")
        
        if not isinstance(self.query_id, QueryId):
            raise ValueError("Query ID must be a QueryId instance")
    
    def __eq__(self, other) -> bool:
        """Test equality with another SubscribeSingleMessage."""
        if not isinstance(other, SubscribeSingleMessage):
            return False
        return (self.query == other.query and 
                self.request_id == other.request_id and
                self.query_id == other.query_id)
    
    def __hash__(self) -> int:
        """Return hash for use in sets and dicts."""
        return hash((self.query, self.request_id, self.query_id))
    
    def __str__(self) -> str:
        """Return string representation."""
        return f"SubscribeSingle(query='{self.query}', request_id={self.request_id}, query_id={self.query_id})"
    
    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"SubscribeSingleMessage(query='{self.query}', request_id={self.request_id}, query_id={self.query_id})"
    
    def write_bsatn(self, writer: BsatnWriter) -> None:
        """
        Write this message to a BSATN writer.
        
        Format: enum variant 2 (SubscribeSingle) with struct containing
        query (string), request_id (u32), query_id (QueryId)
        """
        # Write enum variant for SubscribeSingle (variant 2)
        writer.write_enum_header(2)
        
        # Write struct with 3 fields
        writer.write_struct_header(3)
        
        # Field 1: query
        writer.write_field_name("query")
        writer.write_string(self.query)
        
        # Field 2: request_id
        writer.write_field_name("request_id")
        writer.write_u32(self.request_id)
        
        # Field 3: query_id
        writer.write_field_name("query_id")
        writer.write_u32(self.query_id.id)  # Write QueryId as raw u32 within struct
    
    @classmethod
    def read_bsatn(cls, reader: BsatnReader) -> 'SubscribeSingleMessage':
        """
        Read a SubscribeSingleMessage from a BSATN reader.
        """
        # Read the enum tag first
        tag = reader.read_tag()
        if tag != TAG_ENUM:
            raise ValueError(f"Expected enum tag for SubscribeSingle, got {tag}")
        
        # Read enum header (should be variant 2)
        variant = reader.read_enum_header()
        if variant != 2:
            raise ValueError(f"Expected SubscribeSingle variant (2), got {variant}")
        
        # Read struct tag
        struct_tag = reader.read_tag()
        if struct_tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for SubscribeSingle, got {struct_tag}")
        
        # Read struct header (should be 3 fields)
        field_count = reader.read_struct_header()
        if field_count != 3:
            raise ValueError(f"Expected 3 fields, got {field_count}")
        
        # Read fields
        fields = {}
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "query":
                tag = reader.read_tag()
                if tag != TAG_STRING:
                    raise ValueError(f"Expected string tag for query field, got {tag}")
                fields["query"] = reader.read_string()
            elif field_name == "request_id":
                tag = reader.read_tag()
                if tag != TAG_U32:
                    raise ValueError(f"Expected u32 tag for request_id field, got {tag}")
                fields["request_id"] = reader.read_u32()
            elif field_name == "query_id":
                tag = reader.read_tag()
                if tag != TAG_U32:
                    raise ValueError(f"Expected u32 tag for query_id field, got {tag}")
                fields["query_id"] = QueryId(reader.read_u32())  # Read QueryId as raw u32 within struct
            else:
                raise ValueError(f"Unknown field: {field_name}")
        
        return cls(**fields)
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON representation."""
        return {
            "SubscribeSingle": {
                "query": self.query,
                "request_id": self.request_id,
                "query_id": {"id": self.query_id.id}
            }
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'SubscribeSingleMessage':
        """Create from JSON representation."""
        if "SubscribeSingle" not in data:
            raise ValueError("Invalid JSON format for SubscribeSingle")
        
        msg_data = data["SubscribeSingle"]
        return cls(
            query=msg_data["query"],
            request_id=msg_data["request_id"],
            query_id=QueryId(msg_data["query_id"]["id"])
        )


@dataclass
class SubscribeMultiMessage:
    """
    Register a subscription to multiple queries with QueryId tracking.
    
    This allows subscribing to multiple queries under a single QueryId
    for efficient management.
    """
    query_strings: List[str]
    request_id: int
    query_id: QueryId
    
    def __post_init__(self):
        """Validate message fields after initialization."""
        if not isinstance(self.query_strings, list) or len(self.query_strings) == 0:
            raise ValueError("Query strings must be a non-empty list")
        
        for i, query in enumerate(self.query_strings):
            if not isinstance(query, str) or not query.strip():
                raise ValueError(f"Query at index {i} must be a non-empty string")
        
        if not isinstance(self.request_id, int) or self.request_id < 0:
            raise ValueError("Request ID must be a non-negative integer")
        
        if not isinstance(self.query_id, QueryId):
            raise ValueError("Query ID must be a QueryId instance")
    
    def __eq__(self, other) -> bool:
        """Test equality with another SubscribeMultiMessage."""
        if not isinstance(other, SubscribeMultiMessage):
            return False
        return (self.query_strings == other.query_strings and 
                self.request_id == other.request_id and
                self.query_id == other.query_id)
    
    def __hash__(self) -> int:
        """Return hash for use in sets and dicts."""
        return hash((tuple(self.query_strings), self.request_id, self.query_id))
    
    def __str__(self) -> str:
        """Return string representation."""
        queries_str = f"[{len(self.query_strings)} queries]"
        return f"SubscribeMulti(queries={queries_str}, request_id={self.request_id}, query_id={self.query_id})"
    
    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"SubscribeMultiMessage(query_strings={self.query_strings}, request_id={self.request_id}, query_id={self.query_id})"
    
    def write_bsatn(self, writer: BsatnWriter) -> None:
        """
        Write this message to a BSATN writer.
        
        Format: enum variant 3 (SubscribeMulti) with struct containing
        query_strings (array of strings), request_id (u32), query_id (QueryId)
        """
        # Write enum variant for SubscribeMulti (variant 3)
        writer.write_enum_header(3)
        
        # Write struct with 3 fields
        writer.write_struct_header(3)
        
        # Field 1: query_strings
        writer.write_field_name("query_strings")
        writer.write_array_header(len(self.query_strings))
        for query in self.query_strings:
            writer.write_string(query)
        
        # Field 2: request_id
        writer.write_field_name("request_id")
        writer.write_u32(self.request_id)
        
        # Field 3: query_id
        writer.write_field_name("query_id")
        writer.write_u32(self.query_id.id)  # Write QueryId as raw u32 within struct
    
    @classmethod
    def read_bsatn(cls, reader: BsatnReader) -> 'SubscribeMultiMessage':
        """
        Read a SubscribeMultiMessage from a BSATN reader.
        """
        # Read the enum tag first
        tag = reader.read_tag()
        if tag != TAG_ENUM:
            raise ValueError(f"Expected enum tag for SubscribeMulti, got {tag}")
        
        # Read enum header (should be variant 3)
        variant = reader.read_enum_header()
        if variant != 3:
            raise ValueError(f"Expected SubscribeMulti variant (3), got {variant}")
        
        # Read struct tag
        struct_tag = reader.read_tag()
        if struct_tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for SubscribeMulti, got {struct_tag}")
        
        # Read struct header (should be 3 fields)
        field_count = reader.read_struct_header()
        if field_count != 3:
            raise ValueError(f"Expected 3 fields, got {field_count}")
        
        # Read fields
        fields = {}
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "query_strings":
                tag = reader.read_tag()
                if tag != TAG_ARRAY:
                    raise ValueError(f"Expected array tag for query_strings field, got {tag}")
                count = reader.read_array_header()
                queries = []
                for _ in range(count):
                    string_tag = reader.read_tag()
                    if string_tag != TAG_STRING:
                        raise ValueError(f"Expected string tag in query_strings array, got {string_tag}")
                    queries.append(reader.read_string())
                fields["query_strings"] = queries
            elif field_name == "request_id":
                tag = reader.read_tag()
                if tag != TAG_U32:
                    raise ValueError(f"Expected u32 tag for request_id field, got {tag}")
                fields["request_id"] = reader.read_u32()
            elif field_name == "query_id":
                tag = reader.read_tag()
                if tag != TAG_U32:
                    raise ValueError(f"Expected u32 tag for query_id field, got {tag}")
                fields["query_id"] = QueryId(reader.read_u32())  # Read QueryId as raw u32 within struct
            else:
                raise ValueError(f"Unknown field: {field_name}")
        
        return cls(**fields)
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON representation."""
        return {
            "SubscribeMulti": {
                "query_strings": self.query_strings,
                "request_id": self.request_id,
                "query_id": {"id": self.query_id.id}
            }
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'SubscribeMultiMessage':
        """Create from JSON representation."""
        if "SubscribeMulti" not in data:
            raise ValueError("Invalid JSON format for SubscribeMulti")
        
        msg_data = data["SubscribeMulti"]
        return cls(
            query_strings=msg_data["query_strings"],
            request_id=msg_data["request_id"],
            query_id=QueryId(msg_data["query_id"]["id"])
        )


@dataclass
class UnsubscribeMultiMessage:
    """
    Remove a subscription to multiple queries using QueryId.
    
    This unsubscribes from all queries associated with the given QueryId.
    """
    request_id: int
    query_id: QueryId
    
    def __post_init__(self):
        """Validate message fields after initialization."""
        if not isinstance(self.request_id, int) or self.request_id < 0:
            raise ValueError("Request ID must be a non-negative integer")
        
        if not isinstance(self.query_id, QueryId):
            raise ValueError("Query ID must be a QueryId instance")
    
    def __eq__(self, other) -> bool:
        """Test equality with another UnsubscribeMultiMessage."""
        if not isinstance(other, UnsubscribeMultiMessage):
            return False
        return (self.request_id == other.request_id and
                self.query_id == other.query_id)
    
    def __hash__(self) -> int:
        """Return hash for use in sets and dicts."""
        return hash((self.request_id, self.query_id))
    
    def __str__(self) -> str:
        """Return string representation."""
        return f"UnsubscribeMulti(request_id={self.request_id}, query_id={self.query_id})"
    
    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"UnsubscribeMultiMessage(request_id={self.request_id}, query_id={self.query_id})"
    
    def write_bsatn(self, writer: BsatnWriter) -> None:
        """
        Write this message to a BSATN writer.
        
        Format: enum variant 5 (UnsubscribeMulti) with struct containing
        request_id (u32), query_id (QueryId)
        """
        # Write enum variant for UnsubscribeMulti (variant 5)
        writer.write_enum_header(5)
        
        # Write struct with 2 fields
        writer.write_struct_header(2)
        
        # Field 1: request_id
        writer.write_field_name("request_id")
        writer.write_u32(self.request_id)
        
        # Field 2: query_id
        writer.write_field_name("query_id")
        writer.write_u32(self.query_id.id)  # Write QueryId as raw u32 within struct
    
    @classmethod
    def read_bsatn(cls, reader: BsatnReader) -> 'UnsubscribeMultiMessage':
        """
        Read an UnsubscribeMultiMessage from a BSATN reader.
        """
        # Read the enum tag first
        tag = reader.read_tag()
        if tag != TAG_ENUM:
            raise ValueError(f"Expected enum tag for UnsubscribeMulti, got {tag}")
        
        # Read enum header (should be variant 5)
        variant = reader.read_enum_header()
        if variant != 5:
            raise ValueError(f"Expected UnsubscribeMulti variant (5), got {variant}")
        
        # Read struct tag
        struct_tag = reader.read_tag()
        if struct_tag != TAG_STRUCT:
            raise ValueError(f"Expected struct tag for UnsubscribeMulti, got {struct_tag}")
        
        # Read struct header (should be 2 fields)
        field_count = reader.read_struct_header()
        if field_count != 2:
            raise ValueError(f"Expected 2 fields, got {field_count}")
        
        # Read fields
        fields = {}
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "request_id":
                tag = reader.read_tag()
                if tag != TAG_U32:
                    raise ValueError(f"Expected u32 tag for request_id field, got {tag}")
                fields["request_id"] = reader.read_u32()
            elif field_name == "query_id":
                tag = reader.read_tag()
                if tag != TAG_U32:
                    raise ValueError(f"Expected u32 tag for query_id field, got {tag}")
                fields["query_id"] = QueryId(reader.read_u32())  # Read QueryId as raw u32 within struct
            else:
                raise ValueError(f"Unknown field: {field_name}")
        
        return cls(**fields)
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON representation."""
        return {
            "UnsubscribeMulti": {
                "request_id": self.request_id,
                "query_id": {"id": self.query_id.id}
            }
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'UnsubscribeMultiMessage':
        """Create from JSON representation."""
        if "UnsubscribeMulti" not in data:
            raise ValueError("Invalid JSON format for UnsubscribeMulti")
        
        msg_data = data["UnsubscribeMulti"]
        return cls(
            request_id=msg_data["request_id"],
            query_id=QueryId(msg_data["query_id"]["id"])
        )


# Register message types with BSATN system for automatic encoding/decoding
def register_bsatn_support():
    """Register subscribe message types with the BSATN system."""
    try:
        from ..bsatn.utils import encode_to_writer, decode_from_reader
        
        # This will be enhanced when we integrate with the main BSATN system
        # For now, each message type handles its own serialization via write_bsatn/read_bsatn
        pass
    except ImportError:
        pass


# Auto-register on import
register_bsatn_support() 