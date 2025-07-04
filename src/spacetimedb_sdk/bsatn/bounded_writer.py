"""
Memory-bounded BSATN Writer implementation.

Extends the base BSATN writer with comprehensive memory limits and safety features.
"""

import io
import struct
import math
from typing import Optional, Union, Dict, Any

from .constants import *
from .exceptions import *
from .writer import BsatnWriter
from ..memory_management import (
    RecursionLimiter, MemoryAccountant, MessageSizeValidator,
    get_global_memory_accountant
)

import logging

logger = logging.getLogger(__name__)


class BoundedBsatnWriter(BsatnWriter):
    """
    Memory-bounded BSATN Writer with enhanced safety features.
    
    Features:
    - Total output size limits
    - Per-field size limits
    - Recursion depth limits
    - Memory accounting
    - Stack overflow prevention
    """
    
    def __init__(
        self,
        buffer: Optional[io.BytesIO] = None,
        max_output_size: int = 100 * 1024 * 1024,  # 100MB output limit
        max_field_size: int = 10 * 1024 * 1024,    # 10MB per field
        max_recursion_depth: int = 50,
        memory_accountant: Optional[MemoryAccountant] = None
    ):
        super().__init__(buffer)
        
        self._max_output_size = max_output_size
        self._max_field_size = max_field_size
        self._max_recursion_depth = max_recursion_depth
        self._memory_accountant = memory_accountant or get_global_memory_accountant()
        self._recursion_limiter = RecursionLimiter(max_recursion_depth)
        self._field_count = 0
        self._max_fields = 100000  # Prevent field enumeration attacks
    
    def _check_output_size(self, additional_bytes: int = 0) -> bool:
        """Check if writing additional bytes would exceed limits."""
        total_size = self._bytes_written + additional_bytes
        
        if total_size > self._max_output_size:
            self._record_error(BsatnTooLargeError(
                f"Output size limit exceeded: {total_size} > {self._max_output_size} bytes"
            ))
            return False
        
        # Check global memory allocation
        if not self._memory_accountant.try_allocate('bsatn_write', additional_bytes):
            self._record_error(BsatnTooLargeError(
                f"Global memory allocation failed for {additional_bytes} bytes"
            ))
            return False
        
        return True
    
    def _check_field_limit(self) -> None:
        """Check if we've exceeded the maximum number of fields."""
        self._field_count += 1
        if self._field_count > self._max_fields:
            self._record_error(BsatnTooLargeError(
                f"Too many fields: {self._field_count} (max: {self._max_fields})"
            ))
            raise self._error
    
    def _write_bytes(self, data: bytes) -> None:
        """Write raw bytes to the buffer with size checking."""
        if self._error is not None:
            return
        
        if not self._check_output_size(len(data)):
            return
        
        try:
            written = self._buffer.write(data)
            self._bytes_written += written
        except Exception as e:
            self._record_error(e)
    
    def write_string(self, value: str) -> None:
        """Write a string value with enhanced bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            try:
                str_bytes = value.encode('utf-8')
            except UnicodeEncodeError as e:
                self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 string: {e}"))
                return
            
            # Check multiple limits
            if len(str_bytes) > MAX_PAYLOAD_LEN:
                self._record_error(BsatnTooLargeError(f"String too large: {len(str_bytes)} bytes"))
                return
            
            if len(str_bytes) > self._max_field_size:
                self._record_error(BsatnTooLargeError(
                    f"String exceeds field limit: {len(str_bytes)} > {self._max_field_size} bytes"
                ))
                return
            
            # Check if we can write the tag, length, and data
            total_size = 1 + 4 + len(str_bytes)  # tag + length + data
            if not self._check_output_size(total_size):
                return
            
            self.write_tag(TAG_STRING)
            self._write_bytes(struct.pack('<I', len(str_bytes)))
            if str_bytes:
                self._write_bytes(str_bytes)
    
    def write_bytes(self, value: bytes) -> None:
        """Write a byte array value with enhanced bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            # Check multiple limits
            if len(value) > MAX_PAYLOAD_LEN:
                self._record_error(BsatnTooLargeError(f"Byte array too large: {len(value)} bytes"))
                return
            
            if len(value) > self._max_field_size:
                self._record_error(BsatnTooLargeError(
                    f"Byte array exceeds field limit: {len(value)} > {self._max_field_size} bytes"
                ))
                return
            
            # Check if we can write the tag, length, and data
            total_size = 1 + 4 + len(value)  # tag + length + data
            if not self._check_output_size(total_size):
                return
            
            self.write_tag(TAG_BYTES)
            self._write_bytes(struct.pack('<I', len(value)))
            if value:
                self._write_bytes(value)
    
    def write_list_header(self, count: int) -> None:
        """Write the header for a list with bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            # Prevent extremely large lists
            max_list_items = min(1000000, self._max_output_size // 8)  # Conservative estimate
            if count > max_list_items:
                self._record_error(BsatnTooLargeError(
                    f"List too large: {count} items (max: {max_list_items})"
                ))
                return
            
            if not self._check_output_size(5):  # tag + count
                return
            
            self.write_tag(TAG_LIST)
            self._write_bytes(struct.pack('<I', count))
    
    def write_array_header(self, count: int) -> None:
        """Write the header for an array with bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            # Prevent extremely large arrays
            max_array_items = min(1000000, self._max_output_size // 8)  # Conservative estimate
            if count > max_array_items:
                self._record_error(BsatnTooLargeError(
                    f"Array too large: {count} items (max: {max_array_items})"
                ))
                return
            
            if not self._check_output_size(5):  # tag + count
                return
            
            self.write_tag(TAG_ARRAY)
            self._write_bytes(struct.pack('<I', count))
    
    def write_struct_header(self, field_count: int) -> None:
        """Write the header for a struct with bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            # Prevent extremely large structs
            max_struct_fields = 10000
            if field_count > max_struct_fields:
                self._record_error(BsatnTooLargeError(
                    f"Struct too large: {field_count} fields (max: {max_struct_fields})"
                ))
                return
            
            if not self._check_output_size(5):  # tag + field_count
                return
            
            self.write_tag(TAG_STRUCT)
            self._write_bytes(struct.pack('<I', field_count))
    
    def write_field_name(self, name: str) -> None:
        """Write a field name for a struct with bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            self._check_field_limit()
            
            try:
                name_bytes = name.encode('utf-8')
            except UnicodeEncodeError as e:
                self._record_error(BsatnInvalidUTF8Error(f"Invalid UTF-8 field name: {e}"))
                return
            
            if len(name_bytes) > 255:
                self._record_error(BsatnTooLargeError(f"Field name too long: {len(name_bytes)} bytes, max 255"))
                return
            
            if not self._check_output_size(1 + len(name_bytes)):  # length + name
                return
            
            self._write_bytes(bytes([len(name_bytes)]))
            if name_bytes:
                self._write_bytes(name_bytes)
    
    def write_map_header(self, count: int) -> None:
        """Write the header for a map with bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            # Prevent extremely large maps
            max_map_items = min(1000000, self._max_output_size // 16)  # Conservative estimate for key-value pairs
            if count > max_map_items:
                self._record_error(BsatnTooLargeError(
                    f"Map too large: {count} items (max: {max_map_items})"
                ))
                return
            
            if not self._check_output_size(5):  # tag + count
                return
            
            self.write_tag(TAG_MAP)
            self._write_bytes(struct.pack('<I', count))
    
    def write_enum_header(self, variant_index: int) -> None:
        """Write the header for an enum with bounds checking."""
        if self._error is not None:
            return
        
        with self._recursion_limiter:
            # Reasonable enum variant limit
            max_enum_variants = 100000
            if variant_index > max_enum_variants:
                self._record_error(BsatnTooLargeError(
                    f"Enum variant index too large: {variant_index} (max: {max_enum_variants})"
                ))
                return
            
            if not self._check_output_size(5):  # tag + variant_index
                return
            
            self.write_tag(TAG_ENUM)
            self._write_bytes(struct.pack('<I', variant_index))
    
    def get_bytes(self) -> bytes:
        """Return the written bytes if no error occurred."""
        if self._error is not None:
            return b""
        
        result = self._buffer.getvalue()
        
        # Release memory allocation
        self._memory_accountant.release_memory('bsatn_write', len(result))
        
        return result
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics for this writer."""
        return {
            'bytes_written': self._bytes_written,
            'max_output_size': self._max_output_size,
            'max_field_size': self._max_field_size,
            'field_count': self._field_count,
            'usage_percentage': (self._bytes_written / self._max_output_size) * 100
        }
    
    def __del__(self):
        """Cleanup: release any remaining allocated memory."""
        if hasattr(self, '_bytes_written') and self._bytes_written > 0:
            try:
                self._memory_accountant.release_memory('bsatn_write', self._bytes_written)
            except:
                pass  # Ignore errors during cleanup


def create_bounded_writer(
    max_output_mb: int = 100,
    max_field_mb: int = 10,
    max_recursion_depth: int = 50
) -> BoundedBsatnWriter:
    """
    Factory function to create a bounded BSATN writer with specified limits.
    
    Args:
        max_output_mb: Maximum output size in MB
        max_field_mb: Maximum field size in MB
        max_recursion_depth: Maximum recursion depth
        
    Returns:
        BoundedBsatnWriter instance
    """
    return BoundedBsatnWriter(
        max_output_size=max_output_mb * 1024 * 1024,
        max_field_size=max_field_mb * 1024 * 1024,
        max_recursion_depth=max_recursion_depth
    )