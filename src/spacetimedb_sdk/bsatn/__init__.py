"""
BSATN (Binary SpacetimeDB Algebraic Type Notation) implementation for Python.

This module provides binary serialization/deserialization capabilities
compatible with SpacetimeDB's BSATN format.
"""

from .constants import *
from .exceptions import *
from .writer import BsatnWriter
from .reader import BsatnReader
from .utils import encode, decode, encode_to_writer, decode_from_reader
from .spacetimedb_types import (
    SpacetimeDBIdentity, SpacetimeDBAddress, SpacetimeDBConnectionId,
    SpacetimeDBTimestamp, SpacetimeDBTimeDuration,
    # Convenience aliases
    Identity, Address, ConnectionId, Timestamp, TimeDuration
)

__all__ = [
    # Constants
    'TAG_BOOL_FALSE', 'TAG_BOOL_TRUE', 'TAG_U8', 'TAG_I8', 'TAG_U16', 'TAG_I16',
    'TAG_U32', 'TAG_I32', 'TAG_U64', 'TAG_I64', 'TAG_F32', 'TAG_F64',
    'TAG_STRING', 'TAG_BYTES', 'TAG_LIST', 'TAG_OPTION_NONE', 'TAG_OPTION_SOME',
    'TAG_STRUCT', 'TAG_ENUM', 'TAG_ARRAY', 'TAG_U128', 'TAG_I128', 'TAG_U256', 'TAG_I256',
    'MAX_PAYLOAD_LEN',
    
    # Exceptions
    'BsatnError', 'BsatnInvalidTagError', 'BsatnBufferTooSmallError',
    'BsatnInvalidUTF8Error', 'BsatnOverflowError', 'BsatnInvalidFloatError',
    'BsatnTooLargeError',
    
    # Core classes
    'BsatnWriter', 'BsatnReader',
    
    # Utility functions
    'encode', 'decode', 'encode_to_writer', 'decode_from_reader',
    
    # SpacetimeDB types
    'SpacetimeDBIdentity', 'SpacetimeDBAddress', 'SpacetimeDBConnectionId',
    'SpacetimeDBTimestamp', 'SpacetimeDBTimeDuration',
    'Identity', 'Address', 'ConnectionId', 'Timestamp', 'TimeDuration',
]
