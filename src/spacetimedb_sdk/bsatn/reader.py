"""
BSATN Reader implementation.

Provides binary deserialization capabilities for BSATN format.
"""

import io
import struct
import math
from typing import Optional, Union

from .constants import *
from .exceptions import *


class BsatnReader:
    """
    Reader helps in decoding BSATN-encoded data into Python values.
    
    It wraps binary data and provides methods for reading various
    BSATN-tagged primitive types and structures.
    """
    
    def __init__(self, data: bytes):
        """
        Create a new BSATN Reader.
        
        Args:
            data: Binary data to read from.
        """
        self._buffer = io.BytesIO(data)
        self._error: Optional[Exception] = None
        self._bytes_read = 0
        self._limit = -1  # -1 for no limit
        self._limit_start = 0
    
    def error(self) -> Optional[Exception]:
        """Return the first error that occurred during reading, if any."""
        return self._error
    
    def bytes_read(self) -> int:
        """Return the total number of bytes successfully read."""
        return self._bytes_read
    
    def remaining(self) -> int:
        """Return the number of bytes left before the current limit is reached."""
        if self._limit == -1:
            return -1
        consumed = self._bytes_read - self._limit_start
        return self._limit - consumed
    
    def _record_error(self, error: Exception) -> None:
        """Record the first error encountered."""
        if self._error is None:
            self._error = error
            # Prevent further reads by setting a limit that's already met
            self._limit = self._bytes_read
            self._limit_start = self._bytes_read
    
    def _read_byte(self) -> int:
        """Read a single byte."""
        if self._error is not None:
            raise self._error
        
        if self._limit != -1 and (self._bytes_read - self._limit_start) >= self._limit:
            self._record_error(BsatnBufferTooSmallError("Limit reached"))
            raise self._error
        
        data = self._buffer.read(1)
        if len(data) != 1:
            self._record_error(BsatnBufferTooSmallError("Unexpected end of data"))
            raise self._error
        
        self._bytes_read += 1
        return data[0]
    
    def _read_bytes(self, count: int) -> bytes:
        """Read exactly count bytes."""
        if self._error is not None:
            raise self._error
        
        if self._limit != -1 and (self._bytes_read - self._limit_start) + count > self._limit:
            self._record_error(BsatnBufferTooSmallError("Not enough bytes remaining within limit"))
            raise self._error
        
        data = self._buffer.read(count)
        if len(data) != count:
            self._record_error(BsatnBufferTooSmallError(f"Expected {count} bytes, got {len(data)}"))
            raise self._error
        
        self._bytes_read += count
        return data
    
    def read_tag(self) -> int:
        """Read and return the next BSATN tag byte."""
        return self._read_byte()
    
    def read_bool(self, tag: int) -> bool:
        """Read a boolean value given its tag."""
        if self._error is not None:
            raise self._error
        
        if tag == TAG_BOOL_FALSE:
            return False
        elif tag == TAG_BOOL_TRUE:
            return True
        else:
            self._record_error(BsatnInvalidTagError(f"Invalid boolean tag: {tag}"))
            raise self._error
    
    def read_u8(self) -> int:
        """Read a uint8 value (tag should have been read already)."""
        return self._read_byte()
    
    def read_i8(self) -> int:
        """Read an int8 value (tag should have been read already)."""
        data = self._read_bytes(1)
        return struct.unpack('<b', data)[0]
    
    def read_u16(self) -> int:
        """Read a uint16 value (tag should have been read already)."""
        data = self._read_bytes(2)
        return struct.unpack('<H', data)[0]
    
    def read_i16(self) -> int:
        """Read an int16 value (tag should have been read already)."""
        data = self._read_bytes(2)
        return struct.unpack('<h', data)[0]
    
    def read_u32(self) -> int:
        """Read a uint32 value (tag should have been read already)."""
        data = self._read_bytes(4)
        return struct.unpack('<I', data)[0]
    
    def read_i32(self) -> int:
        """Read an int32 value (tag should have been read already)."""
        data = self._read_bytes(4)
        return struct.unpack('<i', data)[0]
    
    def read_u64(self) -> int:
        """Read a uint64 value (tag should have been read already)."""
        data = self._read_bytes(8)
        return struct.unpack('<Q', data)[0]
    
    def read_i64(self) -> int:
        """Read an int64 value (tag should have been read already)."""
        data = self._read_bytes(8)
        return struct.unpack('<q', data)[0]
    
    def read_f32(self) -> float:
        """Read a float32 value (tag should have been read already)."""
        data = self._read_bytes(4)
        value = struct.unpack('<f', data)[0]
        if math.isnan(value) or math.isinf(value):
            self._record_error(BsatnInvalidFloatError(f"Invalid float32 value: {value}"))
            raise self._error
        return value
    
    def read_f64(self) -> float:
        """Read a float64 value (tag should have been read already)."""
        data = self._read_bytes(8)
        value = struct.unpack('<d', data)[0]
        if math.isnan(value) or math.isinf(value):
            self._record_error(BsatnInvalidFloatError(f"Invalid float64 value: {value}"))
            raise self._error
        return value
    
    def read_string(self) -> str:
        """Read a string value (tag should have been read already)."""
        if self._error is not None:
            raise self._error
        
        # Read length prefix
        length_data = self._read_bytes(4)
        length = struct.unpack('<I', length_data)[0]
        
        if length == 0:
            return ""
        
        if length > MAX_PAYLOAD_LEN:
            self._record_error(BsatnTooLargeError(f"String too large: {length} bytes"))
            raise self._error
        
        # Read string data
        str_data = self._read_bytes(length)
        try:
            return str_data.decode('utf-8')
        except UnicodeDecodeError as e:
            self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 string: {e}"))
            raise self._error
    
    def read_bytes_raw(self) -> bytes:
        """Read a byte array value (tag should have been read already)."""
        if self._error is not None:
            raise self._error
        
        # Read length prefix
        length_data = self._read_bytes(4)
        length = struct.unpack('<I', length_data)[0]
        
        if length == 0:
            return b""
        
        if length > MAX_PAYLOAD_LEN:
            self._record_error(BsatnTooLargeError(f"Byte array too large: {length} bytes"))
            raise self._error
        
        # Read byte data
        return self._read_bytes(length)
    
    def read_u128_bytes(self) -> bytes:
        """Read 16 bytes for U128 (tag should have been read already)."""
        return self._read_bytes(16)
    
    def read_i128_bytes(self) -> bytes:
        """Read 16 bytes for I128 (tag should have been read already)."""
        return self._read_bytes(16)
    
    def read_u256_bytes(self) -> bytes:
        """Read 32 bytes for U256 (tag should have been read already)."""
        return self._read_bytes(32)
    
    def read_i256_bytes(self) -> bytes:
        """Read 32 bytes for I256 (tag should have been read already)."""
        return self._read_bytes(32)
    
    def read_list_header(self) -> int:
        """Read the count of items for a list (tag should have been read already)."""
        if self._error is not None:
            raise self._error
        
        count_data = self._read_bytes(4)
        return struct.unpack('<I', count_data)[0]
    
    def read_array_header(self) -> int:
        """Read the count of items for an array (tag should have been read already)."""
        if self._error is not None:
            raise self._error
        
        count_data = self._read_bytes(4)
        return struct.unpack('<I', count_data)[0]
    
    def read_struct_header(self) -> int:
        """Read the field count for a struct (tag should have been read already)."""
        if self._error is not None:
            raise self._error
        
        field_count_data = self._read_bytes(4)
        return struct.unpack('<I', field_count_data)[0]
    
    def read_field_name(self) -> str:
        """Read a field name for a struct."""
        if self._error is not None:
            raise self._error
        
        # Read name length (u8)
        name_len = self._read_byte()
        
        if name_len == 0:
            return ""
        
        # Read name bytes
        name_bytes = self._read_bytes(name_len)
        try:
            return name_bytes.decode('utf-8')
        except UnicodeDecodeError as e:
            self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 field name: {e}"))
            raise self._error
    
    def read_enum_header(self) -> int:
        """Read the variant index for an enum (tag should have been read already)."""
        if self._error is not None:
            raise self._error
        
        variant_data = self._read_bytes(4)
        return struct.unpack('<I', variant_data)[0]
    
    def skip_value(self) -> None:
        """Skip over a BSATN value without parsing it."""
        if self._error is not None:
            raise self._error
        
        tag = self.read_tag()
        
        if tag == TAG_BOOL_FALSE or tag == TAG_BOOL_TRUE:
            # Boolean values have no additional data
            pass
        elif tag == TAG_U8 or tag == TAG_I8:
            self._read_bytes(1)
        elif tag == TAG_U16 or tag == TAG_I16:
            self._read_bytes(2)
        elif tag == TAG_U32 or tag == TAG_I32:
            self._read_bytes(4)
        elif tag == TAG_U64 or tag == TAG_I64:
            self._read_bytes(8)
        elif tag == TAG_F32:
            self._read_bytes(4)
        elif tag == TAG_F64:
            self._read_bytes(8)
        elif tag == TAG_U128 or tag == TAG_I128:
            self._read_bytes(16)
        elif tag == TAG_U256 or tag == TAG_I256:
            self._read_bytes(32)
        elif tag == TAG_STRING:
            # Read length and skip string data
            length = struct.unpack('<I', self._read_bytes(4))[0]
            self._read_bytes(length)
        elif tag == TAG_BYTES:
            # Read length and skip byte data
            length = struct.unpack('<I', self._read_bytes(4))[0]
            self._read_bytes(length)
        elif tag == TAG_LIST or tag == TAG_ARRAY:
            # Read count and skip each element
            count = struct.unpack('<I', self._read_bytes(4))[0]
            for _ in range(count):
                self.skip_value()
        elif tag == TAG_STRUCT:
            # Read field count and skip each field
            field_count = struct.unpack('<I', self._read_bytes(4))[0]
            for _ in range(field_count):
                # Skip field name
                name_len = self._read_byte()
                self._read_bytes(name_len)
                # Skip field value
                self.skip_value()
        elif tag == TAG_ENUM:
            # Read variant index and skip variant data
            variant_index = struct.unpack('<I', self._read_bytes(4))[0]
            self.skip_value()  # Skip the variant payload
        elif tag == TAG_OPTION_NONE:
            # No additional data for None
            pass
        elif tag == TAG_OPTION_SOME:
            # Skip the contained value
            self.skip_value()
        else:
            self._record_error(BsatnInvalidTagError(f"Unknown tag for skip_value: {tag}"))
            raise self._error
    
    def read_bytes(self) -> bytes:
        """Read a byte array value (tag should have been read already). Alias for read_bytes_raw."""
        return self.read_bytes_raw()
