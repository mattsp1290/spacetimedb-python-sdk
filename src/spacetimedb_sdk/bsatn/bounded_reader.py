"""
Memory-bounded BSATN Reader implementation.

Extends the base BSATN reader with comprehensive memory limits and recursion protection.
"""

import io
import struct
import math
from typing import Optional, Union, Dict, Any

from .constants import *
from .exceptions import *
from .reader import BsatnReader
from ..memory_management import (
    RecursionLimiter, MemoryAccountant, MessageSizeValidator,
    get_global_memory_accountant
)

import logging

logger = logging.getLogger(__name__)


class BoundedBsatnReader(BsatnReader):
    """
    Memory-bounded BSATN Reader with enhanced safety features.
    
    Features:
    - Total memory limit enforcement
    - Per-field size limits
    - Recursion depth limits
    - Memory accounting
    - Stack overflow prevention
    """
    
    def __init__(
        self,
        data: bytes,
        max_total_memory: int = 100 * 1024 * 1024,  # 100MB total limit
        max_field_size: int = 10 * 1024 * 1024,     # 10MB per field
        max_recursion_depth: int = 50,
        memory_accountant: Optional[MemoryAccountant] = None
    ):
        super().__init__(data)
        
        self._max_total_memory = max_total_memory
        self._max_field_size = max_field_size
        self._max_recursion_depth = max_recursion_depth
        self._memory_accountant = memory_accountant or get_global_memory_accountant()
        self._recursion_limiter = RecursionLimiter(max_recursion_depth)
        self._allocated_memory = 0
        self._field_count = 0
        self._max_fields = 100000  # Prevent field enumeration attacks
        
        # Validate initial data size
        if len(data) > self._max_total_memory:
            raise BsatnTooLargeError(f"Input data too large: {len(data)} bytes")
    
    def _allocate_memory(self, size: int, category: str = 'bsatn_read') -> bool:
        """Try to allocate memory for reading operation."""
        if self._allocated_memory + size > self._max_total_memory:
            self._record_error(BsatnTooLargeError(
                f"Memory limit exceeded: requested {size}, "
                f"allocated {self._allocated_memory}, limit {self._max_total_memory}"
            ))
            return False
        
        if not self._memory_accountant.try_allocate(category, size):
            self._record_error(BsatnTooLargeError(
                f"Global memory allocation failed for {size} bytes"
            ))
            return False
        
        self._allocated_memory += size
        return True
    
    def _release_memory(self, size: int, category: str = 'bsatn_read') -> None:
        """Release allocated memory."""
        self._memory_accountant.release_memory(category, size)
        self._allocated_memory = max(0, self._allocated_memory - size)
    
    def _check_field_limit(self) -> None:
        """Check if we've exceeded the maximum number of fields."""
        self._field_count += 1
        if self._field_count > self._max_fields:
            self._record_error(BsatnTooLargeError(
                f"Too many fields: {self._field_count} (max: {self._max_fields})"
            ))
            raise self._error
    
    def read_string(self) -> str:
        """Read a string value with enhanced bounds checking."""
        if self._error is not None:
            raise self._error
        
        with self._recursion_limiter:
            # Read length prefix
            length_data = self._read_bytes(4)
            length = struct.unpack('<I', length_data)[0]
            
            if length == 0:
                return ""
            
            # Check multiple limits
            if length > MAX_PAYLOAD_LEN:
                self._record_error(BsatnTooLargeError(f"String too large: {length} bytes"))
                raise self._error
            
            if length > self._max_field_size:
                self._record_error(BsatnTooLargeError(
                    f"String exceeds field limit: {length} > {self._max_field_size} bytes"
                ))
                raise self._error
            
            # Try to allocate memory for the string
            if not self._allocate_memory(length):
                raise self._error
            
            try:
                # Read string data
                str_data = self._read_bytes(length)
                try:
                    result = str_data.decode('utf-8')
                    return result
                except UnicodeDecodeError as e:
                    self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 string: {e}"))
                    raise self._error
            finally:
                # Always release memory, even on error
                self._release_memory(length)
    
    def read_bytes_raw(self) -> bytes:
        """Read a byte array value with enhanced bounds checking."""
        if self._error is not None:
            raise self._error
        
        with self._recursion_limiter:
            # Read length prefix
            length_data = self._read_bytes(4)
            length = struct.unpack('<I', length_data)[0]
            
            if length == 0:
                return b""
            
            # Check multiple limits
            if length > MAX_PAYLOAD_LEN:
                self._record_error(BsatnTooLargeError(f"Byte array too large: {length} bytes"))
                raise self._error
            
            if length > self._max_field_size:
                self._record_error(BsatnTooLargeError(
                    f"Byte array exceeds field limit: {length} > {self._max_field_size} bytes"
                ))
                raise self._error
            
            # Try to allocate memory for the byte array
            if not self._allocate_memory(length):
                raise self._error
            
            try:
                # Read byte data
                return self._read_bytes(length)
            finally:
                # Always release memory, even on error
                self._release_memory(length)
    
    def read_list_header(self) -> int:
        """Read the count of items for a list with bounds checking."""
        if self._error is not None:
            raise self._error
        
        with self._recursion_limiter:
            count_data = self._read_bytes(4)
            count = struct.unpack('<I', count_data)[0]
            
            # Prevent extremely large lists
            max_list_items = min(1000000, self._max_total_memory // 8)  # Conservative estimate
            if count > max_list_items:
                self._record_error(BsatnTooLargeError(
                    f"List too large: {count} items (max: {max_list_items})"
                ))
                raise self._error
            
            return count
    
    def read_array_header(self) -> int:
        """Read the count of items for an array with bounds checking."""
        if self._error is not None:
            raise self._error
        
        with self._recursion_limiter:
            count_data = self._read_bytes(4)
            count = struct.unpack('<I', count_data)[0]
            
            # Prevent extremely large arrays
            max_array_items = min(1000000, self._max_total_memory // 8)  # Conservative estimate
            if count > max_array_items:
                self._record_error(BsatnTooLargeError(
                    f"Array too large: {count} items (max: {max_array_items})"
                ))
                raise self._error
            
            return count
    
    def read_struct_header(self) -> int:
        """Read the field count for a struct with bounds checking."""
        if self._error is not None:
            raise self._error
        
        with self._recursion_limiter:
            field_count_data = self._read_bytes(4)
            field_count = struct.unpack('<I', field_count_data)[0]
            
            # Prevent extremely large structs
            max_struct_fields = 10000
            if field_count > max_struct_fields:
                self._record_error(BsatnTooLargeError(
                    f"Struct too large: {field_count} fields (max: {max_struct_fields})"
                ))
                raise self._error
            
            return field_count
    
    def read_field_name(self) -> str:
        """Read a field name for a struct with bounds checking."""
        if self._error is not None:
            raise self._error
        
        with self._recursion_limiter:
            self._check_field_limit()
            
            # Read name length (u8)
            name_len = self._read_byte()
            
            if name_len == 0:
                return ""
            
            # Reasonable field name length limit
            if name_len > 255:
                self._record_error(BsatnTooLargeError(f"Field name too long: {name_len} bytes"))
                raise self._error
            
            # Read name bytes
            name_bytes = self._read_bytes(name_len)
            try:
                return name_bytes.decode('utf-8')
            except UnicodeDecodeError as e:
                self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 field name: {e}"))
                raise self._error
    
    def skip_value(self) -> None:
        """Skip over a BSATN value without parsing it (with recursion limit)."""
        if self._error is not None:
            raise self._error
        
        with self._recursion_limiter:
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
                # Read length and skip string data with bounds checking
                length = struct.unpack('<I', self._read_bytes(4))[0]
                if length > self._max_field_size:
                    self._record_error(BsatnTooLargeError(f"String field too large to skip: {length} bytes"))
                    raise self._error
                self._read_bytes(length)
            elif tag == TAG_BYTES:
                # Read length and skip byte data with bounds checking
                length = struct.unpack('<I', self._read_bytes(4))[0]
                if length > self._max_field_size:
                    self._record_error(BsatnTooLargeError(f"Bytes field too large to skip: {length} bytes"))
                    raise self._error
                self._read_bytes(length)
            elif tag == TAG_LIST or tag == TAG_ARRAY:
                # Read count and skip each element with bounds checking
                count = struct.unpack('<I', self._read_bytes(4))[0]
                max_items = min(100000, self._max_total_memory // 64)  # Conservative limit
                if count > max_items:
                    self._record_error(BsatnTooLargeError(f"Too many items to skip: {count}"))
                    raise self._error
                for _ in range(count):
                    self.skip_value()
            elif tag == TAG_STRUCT:
                # Read field count and skip each field with bounds checking
                field_count = struct.unpack('<I', self._read_bytes(4))[0]
                if field_count > 10000:
                    self._record_error(BsatnTooLargeError(f"Too many struct fields to skip: {field_count}"))
                    raise self._error
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
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics for this reader."""
        return {
            'allocated_bytes': self._allocated_memory,
            'max_total_memory': self._max_total_memory,
            'max_field_size': self._max_field_size,
            'bytes_read': self._bytes_read,
            'field_count': self._field_count,
            'usage_percentage': (self._allocated_memory / self._max_total_memory) * 100
        }
    
    def __del__(self):
        """Cleanup: release any remaining allocated memory."""
        if hasattr(self, '_allocated_memory') and self._allocated_memory > 0:
            self._release_memory(self._allocated_memory)


def create_bounded_reader(
    data: bytes,
    max_memory_mb: int = 100,
    max_field_mb: int = 10,
    max_recursion_depth: int = 50
) -> BoundedBsatnReader:
    """
    Factory function to create a bounded BSATN reader with specified limits.
    
    Args:
        data: Binary data to read
        max_memory_mb: Maximum total memory in MB
        max_field_mb: Maximum field size in MB
        max_recursion_depth: Maximum recursion depth
        
    Returns:
        BoundedBsatnReader instance
    """
    return BoundedBsatnReader(
        data,
        max_total_memory=max_memory_mb * 1024 * 1024,
        max_field_size=max_field_mb * 1024 * 1024,
        max_recursion_depth=max_recursion_depth
    )