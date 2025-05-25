"""
Tests for BSATN primitive type encoding/decoding.
"""

import pytest
import math
from spacetimedb_sdk.bsatn import (
    BsatnWriter, BsatnReader, encode_u8, decode_u8, encode_array_i32, decode_array_i32,
    BsatnError, BsatnInvalidTagError, BsatnOverflowError, BsatnInvalidFloatError,
    BsatnTooLargeError, BsatnInvalidUTF8Error,
    TAG_BOOL_FALSE, TAG_BOOL_TRUE, TAG_U8, TAG_I8, TAG_U16, TAG_I16,
    TAG_U32, TAG_I32, TAG_U64, TAG_I64, TAG_F32, TAG_F64, TAG_STRING, TAG_BYTES,
    MAX_PAYLOAD_LEN
)


class TestBsatnWriter:
    """Test BSATN writer functionality."""
    
    def test_write_bool(self):
        """Test boolean encoding."""
        writer = BsatnWriter()
        writer.write_bool(True)
        assert writer.get_bytes() == bytes([TAG_BOOL_TRUE])
        
        writer = BsatnWriter()
        writer.write_bool(False)
        assert writer.get_bytes() == bytes([TAG_BOOL_FALSE])
    
    def test_write_u8(self):
        """Test u8 encoding."""
        writer = BsatnWriter()
        writer.write_u8(42)
        expected = bytes([TAG_U8, 42])
        assert writer.get_bytes() == expected
        
        # Test bounds
        writer = BsatnWriter()
        writer.write_u8(0)
        assert writer.error() is None
        
        writer = BsatnWriter()
        writer.write_u8(255)
        assert writer.error() is None
        
        # Test overflow
        writer = BsatnWriter()
        writer.write_u8(256)
        assert isinstance(writer.error(), BsatnOverflowError)
        
        writer = BsatnWriter()
        writer.write_u8(-1)
        assert isinstance(writer.error(), BsatnOverflowError)
    
    def test_write_i8(self):
        """Test i8 encoding."""
        writer = BsatnWriter()
        writer.write_i8(-42)
        expected = bytes([TAG_I8]) + (-42).to_bytes(1, 'little', signed=True)
        assert writer.get_bytes() == expected
        
        # Test bounds
        writer = BsatnWriter()
        writer.write_i8(-128)
        assert writer.error() is None
        
        writer = BsatnWriter()
        writer.write_i8(127)
        assert writer.error() is None
        
        # Test overflow
        writer = BsatnWriter()
        writer.write_i8(128)
        assert isinstance(writer.error(), BsatnOverflowError)
        
        writer = BsatnWriter()
        writer.write_i8(-129)
        assert isinstance(writer.error(), BsatnOverflowError)
    
    def test_write_u16(self):
        """Test u16 encoding."""
        writer = BsatnWriter()
        writer.write_u16(1234)
        expected = bytes([TAG_U16]) + (1234).to_bytes(2, 'little')
        assert writer.get_bytes() == expected
        
        # Test bounds
        writer = BsatnWriter()
        writer.write_u16(0)
        assert writer.error() is None
        
        writer = BsatnWriter()
        writer.write_u16(65535)
        assert writer.error() is None
        
        # Test overflow
        writer = BsatnWriter()
        writer.write_u16(65536)
        assert isinstance(writer.error(), BsatnOverflowError)
    
    def test_write_i16(self):
        """Test i16 encoding."""
        writer = BsatnWriter()
        writer.write_i16(-1234)
        expected = bytes([TAG_I16]) + (-1234).to_bytes(2, 'little', signed=True)
        assert writer.get_bytes() == expected
    
    def test_write_u32(self):
        """Test u32 encoding."""
        writer = BsatnWriter()
        writer.write_u32(123456)
        expected = bytes([TAG_U32]) + (123456).to_bytes(4, 'little')
        assert writer.get_bytes() == expected
    
    def test_write_i32(self):
        """Test i32 encoding."""
        writer = BsatnWriter()
        writer.write_i32(-123456)
        expected = bytes([TAG_I32]) + (-123456).to_bytes(4, 'little', signed=True)
        assert writer.get_bytes() == expected
    
    def test_write_u64(self):
        """Test u64 encoding."""
        writer = BsatnWriter()
        writer.write_u64(1234567890123456)
        expected = bytes([TAG_U64]) + (1234567890123456).to_bytes(8, 'little')
        assert writer.get_bytes() == expected
    
    def test_write_i64(self):
        """Test i64 encoding."""
        writer = BsatnWriter()
        writer.write_i64(-1234567890123456)
        expected = bytes([TAG_I64]) + (-1234567890123456).to_bytes(8, 'little', signed=True)
        assert writer.get_bytes() == expected
    
    def test_write_f32(self):
        """Test f32 encoding."""
        writer = BsatnWriter()
        writer.write_f32(3.14)
        data = writer.get_bytes()
        assert data[0] == TAG_F32
        assert len(data) == 5  # tag + 4 bytes
        
        # Test invalid values
        writer = BsatnWriter()
        writer.write_f32(float('nan'))
        assert isinstance(writer.error(), BsatnInvalidFloatError)
        
        writer = BsatnWriter()
        writer.write_f32(float('inf'))
        assert isinstance(writer.error(), BsatnInvalidFloatError)
    
    def test_write_f64(self):
        """Test f64 encoding."""
        writer = BsatnWriter()
        writer.write_f64(3.141592653589793)
        data = writer.get_bytes()
        assert data[0] == TAG_F64
        assert len(data) == 9  # tag + 8 bytes
        
        # Test invalid values
        writer = BsatnWriter()
        writer.write_f64(float('nan'))
        assert isinstance(writer.error(), BsatnInvalidFloatError)
        
        writer = BsatnWriter()
        writer.write_f64(float('inf'))
        assert isinstance(writer.error(), BsatnInvalidFloatError)
    
    def test_write_string(self):
        """Test string encoding."""
        writer = BsatnWriter()
        writer.write_string("hello")
        expected = bytes([TAG_STRING]) + (5).to_bytes(4, 'little') + b"hello"
        assert writer.get_bytes() == expected
        
        # Test empty string
        writer = BsatnWriter()
        writer.write_string("")
        expected = bytes([TAG_STRING]) + (0).to_bytes(4, 'little')
        assert writer.get_bytes() == expected
        
        # Test Unicode
        writer = BsatnWriter()
        writer.write_string("héllo")
        utf8_bytes = "héllo".encode('utf-8')
        expected = bytes([TAG_STRING]) + len(utf8_bytes).to_bytes(4, 'little') + utf8_bytes
        assert writer.get_bytes() == expected
    
    def test_write_bytes(self):
        """Test byte array encoding."""
        writer = BsatnWriter()
        data = b"hello"
        writer.write_bytes(data)
        expected = bytes([TAG_BYTES]) + len(data).to_bytes(4, 'little') + data
        assert writer.get_bytes() == expected
        
        # Test empty bytes
        writer = BsatnWriter()
        writer.write_bytes(b"")
        expected = bytes([TAG_BYTES]) + (0).to_bytes(4, 'little')
        assert writer.get_bytes() == expected


class TestBsatnReader:
    """Test BSATN reader functionality."""
    
    def test_read_bool(self):
        """Test boolean decoding."""
        reader = BsatnReader(bytes([TAG_BOOL_TRUE]))
        tag = reader.read_tag()
        assert reader.read_bool(tag) is True
        
        reader = BsatnReader(bytes([TAG_BOOL_FALSE]))
        tag = reader.read_tag()
        assert reader.read_bool(tag) is False
        
        # Test invalid tag
        reader = BsatnReader(bytes([TAG_U8]))
        tag = reader.read_tag()
        with pytest.raises(BsatnInvalidTagError):
            reader.read_bool(tag)
    
    def test_read_u8(self):
        """Test u8 decoding."""
        data = bytes([TAG_U8, 42])
        reader = BsatnReader(data)
        tag = reader.read_tag()
        assert tag == TAG_U8
        assert reader.read_u8() == 42
    
    def test_read_i8(self):
        """Test i8 decoding."""
        data = bytes([TAG_I8]) + (-42).to_bytes(1, 'little', signed=True)
        reader = BsatnReader(data)
        tag = reader.read_tag()
        assert tag == TAG_I8
        assert reader.read_i8() == -42
    
    def test_read_string(self):
        """Test string decoding."""
        test_str = "hello"
        utf8_bytes = test_str.encode('utf-8')
        data = bytes([TAG_STRING]) + len(utf8_bytes).to_bytes(4, 'little') + utf8_bytes
        reader = BsatnReader(data)
        tag = reader.read_tag()
        assert tag == TAG_STRING
        assert reader.read_string() == test_str
        
        # Test empty string
        data = bytes([TAG_STRING]) + (0).to_bytes(4, 'little')
        reader = BsatnReader(data)
        tag = reader.read_tag()
        assert reader.read_string() == ""
    
    def test_read_bytes(self):
        """Test byte array decoding."""
        test_bytes = b"hello"
        data = bytes([TAG_BYTES]) + len(test_bytes).to_bytes(4, 'little') + test_bytes
        reader = BsatnReader(data)
        tag = reader.read_tag()
        assert tag == TAG_BYTES
        assert reader.read_bytes_raw() == test_bytes
        
        # Test empty bytes
        data = bytes([TAG_BYTES]) + (0).to_bytes(4, 'little')
        reader = BsatnReader(data)
        tag = reader.read_tag()
        assert reader.read_bytes_raw() == b""


class TestRoundTrip:
    """Test round-trip encoding/decoding."""
    
    def test_u8_roundtrip(self):
        """Test u8 round-trip."""
        original = 42
        encoded = encode_u8(original)
        decoded = decode_u8(encoded)
        assert decoded == original
    
    def test_array_i32_roundtrip(self):
        """Test array of i32 round-trip."""
        original = [1, -2, 3, -4, 5]
        encoded = encode_array_i32(original)
        decoded = decode_array_i32(encoded)
        assert decoded == original
        
        # Test empty array
        original = []
        encoded = encode_array_i32(original)
        decoded = decode_array_i32(encoded)
        assert decoded == original
    
    def test_string_roundtrip(self):
        """Test string round-trip."""
        writer = BsatnWriter()
        original = "Hello, 世界!"
        writer.write_string(original)
        
        reader = BsatnReader(writer.get_bytes())
        tag = reader.read_tag()
        decoded = reader.read_string()
        assert decoded == original
    
    def test_float_roundtrip(self):
        """Test float round-trip."""
        writer = BsatnWriter()
        original = 3.141592653589793
        writer.write_f64(original)
        
        reader = BsatnReader(writer.get_bytes())
        tag = reader.read_tag()
        decoded = reader.read_f64()
        assert abs(decoded - original) < 1e-15


class TestErrorHandling:
    """Test error handling."""
    
    def test_buffer_too_small(self):
        """Test buffer too small error."""
        # Try to read more data than available
        reader = BsatnReader(bytes([TAG_U8]))  # Missing the u8 payload
        tag = reader.read_tag()
        with pytest.raises(Exception):  # Should raise some buffer error
            reader.read_u8()
    
    def test_payload_too_large(self):
        """Test payload too large error."""
        writer = BsatnWriter()
        large_string = "x" * (MAX_PAYLOAD_LEN + 1)
        writer.write_string(large_string)
        assert isinstance(writer.error(), BsatnTooLargeError)
    
    def test_invalid_utf8(self):
        """Test invalid UTF-8 handling."""
        # Create invalid UTF-8 data
        invalid_utf8 = b'\xff\xfe'
        data = bytes([TAG_STRING]) + len(invalid_utf8).to_bytes(4, 'little') + invalid_utf8
        reader = BsatnReader(data)
        tag = reader.read_tag()
        with pytest.raises(BsatnInvalidUTF8Error):
            reader.read_string()


if __name__ == "__main__":
    pytest.main([__file__])
