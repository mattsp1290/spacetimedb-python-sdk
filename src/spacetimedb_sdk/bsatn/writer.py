"""
BSATN Writer implementation.

Provides binary serialization capabilities for BSATN format.
"""

import io
import struct
import math
from typing import Optional, Union

from .constants import *
from .exceptions import *


class BsatnWriter:
    """
    Writer helps in encoding Python values into BSATN format.
    
    It wraps an io.BytesIO and provides methods for writing various
    BSATN-tagged primitive types and structures.
    """
    
    def __init__(self, buffer: Optional[io.BytesIO] = None):
        """
        Create a new BSATN Writer.
        
        Args:
            buffer: Optional BytesIO buffer. If None, creates a new one.
        """
        self._buffer = buffer if buffer is not None else io.BytesIO()
        self._error: Optional[Exception] = None
        self._bytes_written = 0
    
    def error(self) -> Optional[Exception]:
        """Return the first error that occurred during writing, if any."""
        return self._error
    
    def bytes_written(self) -> int:
        """Return the number of bytes successfully written."""
        return self._bytes_written
    
    def get_bytes(self) -> bytes:
        """Return the written bytes if no error occurred."""
        if self._error is not None:
            return b""
        return self._buffer.getvalue()
    
    def _record_error(self, error: Exception) -> None:
        """Record the first error encountered."""
        if self._error is None:
            self._error = error
    
    def _write_bytes(self, data: bytes) -> None:
        """Write raw bytes to the buffer."""
        if self._error is not None:
            return
        try:
            written = self._buffer.write(data)
            self._bytes_written += written
        except Exception as e:
            self._record_error(e)
    
    def write_tag(self, tag: int) -> None:
        """Write a BSATN type tag."""
        self._write_bytes(bytes([tag]))
    
    def write_bool(self, value: bool) -> None:
        """Write a boolean value."""
        if value:
            self.write_tag(TAG_BOOL_TRUE)
        else:
            self.write_tag(TAG_BOOL_FALSE)
    
    def write_u8(self, value: int) -> None:
        """Write a uint8 value."""
        if self._error is not None:
            return
        if not (0 <= value <= 255):
            self._record_error(BsatnOverflowError(f"u8 value {value} out of range [0, 255]"))
            return
        self.write_tag(TAG_U8)
        self._write_bytes(bytes([value]))
    
    def write_i8(self, value: int) -> None:
        """Write an int8 value."""
        if self._error is not None:
            return
        if not (-128 <= value <= 127):
            self._record_error(BsatnOverflowError(f"i8 value {value} out of range [-128, 127]"))
            return
        self.write_tag(TAG_I8)
        self._write_bytes(struct.pack('<b', value))
    
    def write_u16(self, value: int) -> None:
        """Write a uint16 value."""
        if self._error is not None:
            return
        if not (0 <= value <= 65535):
            self._record_error(BsatnOverflowError(f"u16 value {value} out of range [0, 65535]"))
            return
        self.write_tag(TAG_U16)
        self._write_bytes(struct.pack('<H', value))
    
    def write_i16(self, value: int) -> None:
        """Write an int16 value."""
        if self._error is not None:
            return
        if not (-32768 <= value <= 32767):
            self._record_error(BsatnOverflowError(f"i16 value {value} out of range [-32768, 32767]"))
            return
        self.write_tag(TAG_I16)
        self._write_bytes(struct.pack('<h', value))
    
    def write_u32(self, value: int) -> None:
        """Write a uint32 value."""
        if self._error is not None:
            return
        if not (0 <= value <= 4294967295):
            self._record_error(BsatnOverflowError(f"u32 value {value} out of range [0, 4294967295]"))
            return
        self.write_tag(TAG_U32)
        self._write_bytes(struct.pack('<I', value))
    
    def write_i32(self, value: int) -> None:
        """Write an int32 value."""
        if self._error is not None:
            return
        if not (-2147483648 <= value <= 2147483647):
            self._record_error(BsatnOverflowError(f"i32 value {value} out of range [-2147483648, 2147483647]"))
            return
        self.write_tag(TAG_I32)
        self._write_bytes(struct.pack('<i', value))
    
    def write_u64(self, value: int) -> None:
        """Write a uint64 value."""
        if self._error is not None:
            return
        if not (0 <= value <= 18446744073709551615):
            self._record_error(BsatnOverflowError(f"u64 value {value} out of range [0, 18446744073709551615]"))
            return
        self.write_tag(TAG_U64)
        self._write_bytes(struct.pack('<Q', value))
    
    def write_i64(self, value: int) -> None:
        """Write an int64 value."""
        if self._error is not None:
            return
        if not (-9223372036854775808 <= value <= 9223372036854775807):
            self._record_error(BsatnOverflowError(f"i64 value {value} out of range [-9223372036854775808, 9223372036854775807]"))
            return
        self.write_tag(TAG_I64)
        self._write_bytes(struct.pack('<q', value))
    
    def write_f32(self, value: float) -> None:
        """Write a float32 value."""
        if self._error is not None:
            return
        if math.isnan(value) or math.isinf(value):
            self._record_error(BsatnInvalidFloatError(f"Invalid float32 value: {value}"))
            return
        self.write_tag(TAG_F32)
        self._write_bytes(struct.pack('<f', value))
    
    def write_f64(self, value: float) -> None:
        """Write a float64 value."""
        if self._error is not None:
            return
        if math.isnan(value) or math.isinf(value):
            self._record_error(BsatnInvalidFloatError(f"Invalid float64 value: {value}"))
            return
        self.write_tag(TAG_F64)
        self._write_bytes(struct.pack('<d', value))
    
    def write_string(self, value: str) -> None:
        """Write a string value."""
        if self._error is not None:
            return
        try:
            str_bytes = value.encode('utf-8')
        except UnicodeEncodeError as e:
            self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 string: {e}"))
            return
        
        if len(str_bytes) > MAX_PAYLOAD_LEN:
            self._record_error(BsatnTooLargeError(f"String too large: {len(str_bytes)} bytes"))
            return
        
        self.write_tag(TAG_STRING)
        self._write_bytes(struct.pack('<I', len(str_bytes)))
        if str_bytes:
            self._write_bytes(str_bytes)
    
    def write_bytes(self, value: bytes) -> None:
        """Write a byte array value."""
        if self._error is not None:
            return
        if len(value) > MAX_PAYLOAD_LEN:
            self._record_error(BsatnTooLargeError(f"Byte array too large: {len(value)} bytes"))
            return
        
        self.write_tag(TAG_BYTES)
        self._write_bytes(struct.pack('<I', len(value)))
        if value:
            self._write_bytes(value)
    
    def write_option_none(self) -> None:
        """Write a None option value."""
        self.write_tag(TAG_OPTION_NONE)
    
    def write_option_some_tag(self) -> None:
        """Write the tag for Some option. Caller must write the payload next."""
        self.write_tag(TAG_OPTION_SOME)
    
    def write_u128_bytes(self, value: bytes) -> None:
        """Write a U128 as 16 bytes."""
        if self._error is not None:
            return
        if len(value) != 16:
            self._record_error(BsatnInvalidTagError(f"U128 requires exactly 16 bytes, got {len(value)}"))
            return
        self.write_tag(TAG_U128)
        self._write_bytes(value)
    
    def write_i128_bytes(self, value: bytes) -> None:
        """Write an I128 as 16 bytes."""
        if self._error is not None:
            return
        if len(value) != 16:
            self._record_error(BsatnInvalidTagError(f"I128 requires exactly 16 bytes, got {len(value)}"))
            return
        self.write_tag(TAG_I128)
        self._write_bytes(value)
    
    def write_u256_bytes(self, value: bytes) -> None:
        """Write a U256 as 32 bytes."""
        if self._error is not None:
            return
        if len(value) != 32:
            self._record_error(BsatnInvalidTagError(f"U256 requires exactly 32 bytes, got {len(value)}"))
            return
        self.write_tag(TAG_U256)
        self._write_bytes(value)
    
    def write_i256_bytes(self, value: bytes) -> None:
        """Write an I256 as 32 bytes."""
        if self._error is not None:
            return
        if len(value) != 32:
            self._record_error(BsatnInvalidTagError(f"I256 requires exactly 32 bytes, got {len(value)}"))
            return
        self.write_tag(TAG_I256)
        self._write_bytes(value)
    
    def write_list_header(self, count: int) -> None:
        """Write the header for a list. Caller must write each item next."""
        if self._error is not None:
            return
        self.write_tag(TAG_LIST)
        self._write_bytes(struct.pack('<I', count))
    
    def write_array_header(self, count: int) -> None:
        """Write the header for an array. Caller must write each item next."""
        if self._error is not None:
            return
        self.write_tag(TAG_ARRAY)
        self._write_bytes(struct.pack('<I', count))
    
    def write_map_header(self, count: int) -> None:
        """Write the header for a map. Caller must write each key-value pair next."""
        if self._error is not None:
            return
        self.write_tag(TAG_MAP)
        self._write_bytes(struct.pack('<I', count))
    
    def write_struct_header(self, field_count: int) -> None:
        """Write the header for a struct. Caller must write each field next."""
        if self._error is not None:
            return
        self.write_tag(TAG_STRUCT)
        self._write_bytes(struct.pack('<I', field_count))
    
    def write_field_name(self, name: str) -> None:
        """Write a field name for a struct."""
        if self._error is not None:
            return
        try:
            name_bytes = name.encode('utf-8')
        except UnicodeEncodeError as e:
            self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 field name: {e}"))
            return
        
        if len(name_bytes) > 255:
            self._record_error(BsatnTooLargeError(f"Field name too long: {len(name_bytes)} bytes, max 255"))
            return
        
        self._write_bytes(bytes([len(name_bytes)]))
        if name_bytes:
            self._write_bytes(name_bytes)
    
    def write_enum_header(self, variant_index: int) -> None:
        """Write the header for an enum. Caller must write the payload next."""
        if self._error is not None:
            return
        self.write_tag(TAG_ENUM)
        self._write_bytes(struct.pack('<I', variant_index))
