"""
BSATN utility functions for high-level encoding/decoding.

Provides convenient functions for encoding and decoding Python values
to/from BSATN format.
"""

from typing import Any, Union, List, Dict, Optional, Type
import io

from .constants import *
from .exceptions import *
from .writer import BsatnWriter
from .reader import BsatnReader


def encode(value: Any) -> bytes:
    """
    Encode a Python value to BSATN bytes.
    
    Args:
        value: The value to encode
        
    Returns:
        BSATN-encoded bytes
        
    Raises:
        BsatnError: If encoding fails
    """
    writer = BsatnWriter()
    encode_to_writer(value, writer)
    
    if writer.error():
        raise writer.error()
    
    return writer.get_bytes()


def decode(data: bytes, expected_type: Optional[Type] = None) -> Any:
    """
    Decode BSATN bytes to a Python value.
    
    Args:
        data: BSATN-encoded bytes
        expected_type: Optional type hint for decoding
        
    Returns:
        Decoded Python value
        
    Raises:
        BsatnError: If decoding fails
    """
    reader = BsatnReader(data)
    return decode_from_reader(reader, expected_type)


def encode_to_writer(value: Any, writer: BsatnWriter) -> None:
    """
    Encode a Python value to a BSATN writer.
    
    Args:
        value: The value to encode
        writer: The BSATN writer to write to
        
    Raises:
        BsatnError: If encoding fails
    """
    # Check if the object has a custom BSATN serialization method FIRST
    # This needs to come before int check because CallReducerFlags inherits from IntEnum
    if hasattr(value, 'write_bsatn'):
        value.write_bsatn(writer)
        return
    
    if value is None:
        writer.write_option_none()
    elif isinstance(value, bool):
        writer.write_bool(value)
    elif isinstance(value, int):
        # Try to fit in the smallest appropriate integer type
        if -128 <= value <= 127:
            writer.write_i8(value)
        elif 0 <= value <= 255:
            writer.write_u8(value)
        elif -32768 <= value <= 32767:
            writer.write_i16(value)
        elif 0 <= value <= 65535:
            writer.write_u16(value)
        elif -2147483648 <= value <= 2147483647:
            writer.write_i32(value)
        elif 0 <= value <= 4294967295:
            writer.write_u32(value)
        elif -9223372036854775808 <= value <= 9223372036854775807:
            writer.write_i64(value)
        elif 0 <= value <= 18446744073709551615:
            writer.write_u64(value)
        else:
            raise BsatnOverflowError(f"Integer value {value} too large for any supported type")
    elif isinstance(value, float):
        writer.write_f64(value)
    elif isinstance(value, str):
        writer.write_string(value)
    elif isinstance(value, bytes):
        writer.write_bytes(value)
    elif isinstance(value, (list, tuple)):
        writer.write_array_header(len(value))
        for item in value:
            encode_to_writer(item, writer)
    elif isinstance(value, dict):
        writer.write_struct_header(len(value))
        for key, val in value.items():
            if not isinstance(key, str):
                raise BsatnInvalidTagError(f"Dictionary keys must be strings, got {type(key)}")
            writer.write_field_name(key)
            encode_to_writer(val, writer)
    else:
        # Check for enhanced message types
        try:
            from ..messages.subscribe import (
                SubscribeSingleMessage,
                SubscribeMultiMessage,
                UnsubscribeMultiMessage
            )
            from ..messages.one_off_query import (
                OneOffQueryMessage,
                OneOffQueryResponseMessage
            )
            from ..messages.server import (
                EnhancedSubscribeApplied,
                EnhancedSubscriptionError,
                EnhancedSubscribeMultiApplied,
                EnhancedTransactionUpdateLight,
                EnhancedIdentityToken,
                EnhancedTableUpdate,
                EnhancedDatabaseUpdate
            )
            from ..connection_id import (
                EnhancedConnectionId,
                EnhancedIdentity,
                EnhancedIdentityToken as ConnectionEnhancedIdentityToken,
                ConnectionEvent
            )
            
            # Import energy management types
            from ..energy import (
                EnergyEvent,
                EnergyOperation,
                EnergyUsageReport
            )
            from ..protocol import EnergyQuanta
            
            if isinstance(value, (SubscribeSingleMessage, SubscribeMultiMessage, UnsubscribeMultiMessage,
                                 OneOffQueryMessage, OneOffQueryResponseMessage,
                                 EnhancedSubscribeApplied, EnhancedSubscriptionError, EnhancedSubscribeMultiApplied,
                                 EnhancedTransactionUpdateLight, EnhancedIdentityToken,
                                 EnhancedTableUpdate, EnhancedDatabaseUpdate,
                                 EnhancedConnectionId, EnhancedIdentity, ConnectionEnhancedIdentityToken,
                                 EnergyQuanta, EnergyEvent, EnergyOperation, EnergyUsageReport)):
                value.write_bsatn(writer)
                return
        except ImportError:
            pass
        
        raise BsatnInvalidTagError(f"Cannot encode type {type(value)} to BSATN")


def decode_from_reader(reader: BsatnReader, expected_type: Optional[Type] = None) -> Any:
    """
    Decode a value from a BSATN reader.
    
    Args:
        reader: The BSATN reader to read from
        expected_type: Optional type hint for decoding
        
    Returns:
        Decoded Python value
        
    Raises:
        BsatnError: If decoding fails
    """
    # Check if we have an expected type that can handle its own BSATN reading
    if expected_type:
        # Import here to avoid circular imports
        try:
            from ..query_id import QueryId
            from ..call_reducer_flags import CallReducerFlags
            from ..messages.subscribe import (
                SubscribeSingleMessage,
                SubscribeMultiMessage,
                UnsubscribeMultiMessage
            )
            from ..messages.one_off_query import (
                OneOffQueryMessage,
                OneOffQueryResponseMessage
            )
            from ..messages.server import (
                EnhancedSubscribeApplied,
                EnhancedSubscriptionError,
                EnhancedSubscribeMultiApplied,
                EnhancedTransactionUpdateLight,
                EnhancedIdentityToken
            )
            from ..connection_id import (
                EnhancedConnectionId,
                EnhancedIdentity,
                EnhancedIdentityToken as ConnectionEnhancedIdentityToken
            )
            
            # Import energy management types
            from ..energy import (
                EnergyEvent,
                EnergyOperation,
                EnergyUsageReport
            )
            from ..protocol import EnergyQuanta
            
            # Handle types that have their own complete BSATN readers
            if expected_type in (SubscribeSingleMessage, SubscribeMultiMessage, UnsubscribeMultiMessage,
                               OneOffQueryMessage, OneOffQueryResponseMessage,
                               EnhancedSubscribeApplied, EnhancedSubscriptionError, EnhancedSubscribeMultiApplied,
                               EnhancedTransactionUpdateLight, EnhancedIdentityToken,
                               EnhancedConnectionId, EnhancedIdentity, ConnectionEnhancedIdentityToken,
                               EnergyQuanta, EnergyEvent, EnergyOperation, EnergyUsageReport):
                return expected_type.read_bsatn(reader)
            elif expected_type is QueryId:
                return QueryId.read_bsatn(reader)
            elif expected_type is CallReducerFlags:
                return CallReducerFlags.read_bsatn(reader)
        except ImportError:
            pass
    
    # Fallback to generic tag-based decoding
    tag = reader.read_tag()
    
    if tag == TAG_BOOL_FALSE:
        return False
    elif tag == TAG_BOOL_TRUE:
        return True
    elif tag == TAG_U8:
        return reader.read_u8()
    elif tag == TAG_I8:
        return reader.read_i8()
    elif tag == TAG_U16:
        return reader.read_u16()
    elif tag == TAG_I16:
        return reader.read_i16()
    elif tag == TAG_U32:
        value = reader.read_u32()
        # Check if we're expecting a QueryId (fallback case)
        if expected_type:
            try:
                from ..query_id import QueryId
                from ..call_reducer_flags import CallReducerFlags
                if expected_type is QueryId:
                    return QueryId(value)
                elif expected_type is CallReducerFlags:
                    return CallReducerFlags(value)
            except ImportError:
                pass
        return value
    elif tag == TAG_I32:
        return reader.read_i32()
    elif tag == TAG_U64:
        return reader.read_u64()
    elif tag == TAG_I64:
        return reader.read_i64()
    elif tag == TAG_F32:
        return reader.read_f32()
    elif tag == TAG_F64:
        return reader.read_f64()
    elif tag == TAG_STRING:
        return reader.read_string()
    elif tag == TAG_BYTES:
        return reader.read_bytes_raw()
    elif tag == TAG_OPTION_NONE:
        return None
    elif tag == TAG_OPTION_SOME:
        return decode_from_reader(reader, expected_type)
    elif tag == TAG_ARRAY:
        count = reader.read_array_header()
        items = []
        for _ in range(count):
            items.append(decode_from_reader(reader))
        return items
    elif tag == TAG_LIST:
        count = reader.read_list_header()
        items = []
        for _ in range(count):
            items.append(decode_from_reader(reader))
        return items
    elif tag == TAG_STRUCT:
        field_count = reader.read_struct_header()
        result = {}
        for _ in range(field_count):
            field_name = reader.read_field_name()
            field_value = decode_from_reader(reader)
            result[field_name] = field_value
        return result
    elif tag == TAG_ENUM:
        # Fallback: read variant index and handle generic enum
        variant_index = reader.read_enum_header()
        # Return a simple tuple (index, payload)
        # In a full implementation, this would use type information
        try:
            payload = decode_from_reader(reader)
            return (variant_index, payload)
        except:
            # No payload for this variant
            return (variant_index, None)
    elif tag == TAG_U128:
        return reader.read_u128_bytes()
    elif tag == TAG_I128:
        return reader.read_i128_bytes()
    elif tag == TAG_U256:
        return reader.read_u256_bytes()
    elif tag == TAG_I256:
        return reader.read_i256_bytes()
    else:
        raise BsatnInvalidTagError(f"Unknown BSATN tag: {tag}")


def encode_u8(value: int) -> bytes:
    """Convenience function to encode a u8 value."""
    writer = BsatnWriter()
    writer.write_u8(value)
    if writer.error():
        raise writer.error()
    return writer.get_bytes()


def decode_u8(data: bytes) -> int:
    """Convenience function to decode a u8 value."""
    reader = BsatnReader(data)
    tag = reader.read_tag()
    if tag != TAG_U8:
        raise BsatnInvalidTagError(f"Expected u8 tag, got {tag}")
    return reader.read_u8()


def encode_array_i32(values: List[int]) -> bytes:
    """Convenience function to encode an array of i32 values."""
    writer = BsatnWriter()
    writer.write_array_header(len(values))
    for value in values:
        writer.write_i32(value)
    if writer.error():
        raise writer.error()
    return writer.get_bytes()


def decode_array_i32(data: bytes) -> List[int]:
    """Convenience function to decode an array of i32 values."""
    reader = BsatnReader(data)
    tag = reader.read_tag()
    if tag != TAG_ARRAY:
        raise BsatnInvalidTagError(f"Expected array tag, got {tag}")
    
    count = reader.read_array_header()
    result = []
    for _ in range(count):
        item_tag = reader.read_tag()
        if item_tag != TAG_I32:
            raise BsatnInvalidTagError(f"Expected i32 tag in array, got {item_tag}")
        result.append(reader.read_i32())
    
    return result
