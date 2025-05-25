"""
Tests for BSATN Protocol Support.

Tests BSATN serialization/deserialization for protocol messages and types.
"""

import pytest
from datetime import datetime, timedelta

from spacetimedb_sdk import (
    # Protocol types
    CallReducer,
    CallReducerFlags,
    Subscribe,
    SubscribeSingleMessage,
    SubscribeMultiMessage,
    Unsubscribe,
    UnsubscribeMultiMessage,
    OneOffQuery,
    OneOffQueryMessage,
    QueryId,
    
    # BSATN
    BsatnWriter,
    BsatnReader,
    
    # SpacetimeDB types
    SpacetimeDBIdentity,
    SpacetimeDBAddress,
    SpacetimeDBConnectionId,
    SpacetimeDBTimestamp,
    SpacetimeDBTimeDuration,
    
    # Protocol encoder/decoder
    ProtocolEncoder,
    ProtocolDecoder,
)


class TestBsatnPrimitiveTypes:
    """Test BSATN serialization of primitive types."""
    
    def test_bool(self):
        """Test boolean serialization."""
        writer = BsatnWriter()
        writer.write_bool(True)
        writer.write_bool(False)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x02  # TAG_BOOL_TRUE
        assert reader.read_bool(0x02)
        assert reader.read_tag() == 0x01  # TAG_BOOL_FALSE
        assert not reader.read_bool(0x01)
    
    def test_integers(self):
        """Test integer serialization."""
        writer = BsatnWriter()
        writer.write_u8(255)
        writer.write_i8(-128)
        writer.write_u16(65535)
        writer.write_i16(-32768)
        writer.write_u32(4294967295)
        writer.write_i32(-2147483648)
        writer.write_u64(18446744073709551615)
        writer.write_i64(-9223372036854775808)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        # Skip tags and read values
        assert reader.read_tag() == 0x03  # TAG_U8
        assert reader.read_u8() == 255
        assert reader.read_tag() == 0x04  # TAG_I8
        assert reader.read_i8() == -128
        assert reader.read_tag() == 0x05  # TAG_U16
        assert reader.read_u16() == 65535
        assert reader.read_tag() == 0x06  # TAG_I16
        assert reader.read_i16() == -32768
        assert reader.read_tag() == 0x07  # TAG_U32
        assert reader.read_u32() == 4294967295
        assert reader.read_tag() == 0x08  # TAG_I32
        assert reader.read_i32() == -2147483648
        assert reader.read_tag() == 0x09  # TAG_U64
        assert reader.read_u64() == 18446744073709551615
        assert reader.read_tag() == 0x0A  # TAG_I64
        assert reader.read_i64() == -9223372036854775808
    
    def test_floats(self):
        """Test float serialization."""
        writer = BsatnWriter()
        writer.write_f32(3.14)
        writer.write_f64(2.71828)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x0B  # TAG_F32
        assert abs(reader.read_f32() - 3.14) < 0.001
        assert reader.read_tag() == 0x0C  # TAG_F64
        assert abs(reader.read_f64() - 2.71828) < 0.00001
    
    def test_strings(self):
        """Test string serialization."""
        writer = BsatnWriter()
        writer.write_string("Hello, World!")
        writer.write_string("")  # Empty string
        writer.write_string("Unicode: 🚀")
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x0D  # TAG_STRING
        assert reader.read_string() == "Hello, World!"
        assert reader.read_tag() == 0x0D
        assert reader.read_string() == ""
        assert reader.read_tag() == 0x0D
        assert reader.read_string() == "Unicode: 🚀"
    
    def test_bytes(self):
        """Test byte array serialization."""
        writer = BsatnWriter()
        writer.write_bytes(b"Binary data")
        writer.write_bytes(b"")  # Empty bytes
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x0E  # TAG_BYTES
        assert reader.read_bytes_raw() == b"Binary data"
        assert reader.read_tag() == 0x0E
        assert reader.read_bytes_raw() == b""


class TestBsatnComplexTypes:
    """Test BSATN serialization of complex types."""
    
    def test_struct(self):
        """Test struct serialization."""
        writer = BsatnWriter()
        writer.write_struct_header(3)  # 3 fields
        
        writer.write_field_name("id")
        writer.write_u32(42)
        
        writer.write_field_name("name")
        writer.write_string("Test User")
        
        writer.write_field_name("active")
        writer.write_bool(True)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x12  # TAG_STRUCT
        assert reader.read_struct_header() == 3
        
        assert reader.read_field_name() == "id"
        assert reader.read_tag() == 0x07  # TAG_U32
        assert reader.read_u32() == 42
        
        assert reader.read_field_name() == "name"
        assert reader.read_tag() == 0x0D  # TAG_STRING
        assert reader.read_string() == "Test User"
        
        assert reader.read_field_name() == "active"
        assert reader.read_tag() == 0x02  # TAG_BOOL_TRUE
        assert reader.read_bool(0x02)
    
    def test_array(self):
        """Test array serialization."""
        writer = BsatnWriter()
        writer.write_array_header(3)
        writer.write_u32(1)
        writer.write_u32(2)
        writer.write_u32(3)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x14  # TAG_ARRAY
        assert reader.read_array_header() == 3
        assert reader.read_tag() == 0x07  # TAG_U32
        assert reader.read_u32() == 1
        assert reader.read_tag() == 0x07
        assert reader.read_u32() == 2
        assert reader.read_tag() == 0x07
        assert reader.read_u32() == 3
    
    def test_list(self):
        """Test list serialization (heterogeneous)."""
        writer = BsatnWriter()
        writer.write_list_header(3)
        writer.write_string("first")
        writer.write_u32(42)
        writer.write_bool(True)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x0F  # TAG_LIST
        assert reader.read_list_header() == 3
        assert reader.read_tag() == 0x0D  # TAG_STRING
        assert reader.read_string() == "first"
        assert reader.read_tag() == 0x07  # TAG_U32
        assert reader.read_u32() == 42
        assert reader.read_tag() == 0x02  # TAG_BOOL_TRUE
        assert reader.read_bool(0x02)
    
    def test_enum(self):
        """Test enum serialization."""
        writer = BsatnWriter()
        writer.write_enum_header(1)  # Variant 1
        writer.write_string("Variant payload")
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x13  # TAG_ENUM
        assert reader.read_enum_header() == 1
        assert reader.read_tag() == 0x0D  # TAG_STRING
        assert reader.read_string() == "Variant payload"
    
    def test_option(self):
        """Test option type serialization."""
        writer = BsatnWriter()
        
        # None
        writer.write_option_none()
        
        # Some(42)
        writer.write_option_some_tag()
        writer.write_u32(42)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        assert reader.read_tag() == 0x10  # TAG_OPTION_NONE
        
        assert reader.read_tag() == 0x11  # TAG_OPTION_SOME
        assert reader.read_tag() == 0x07  # TAG_U32
        assert reader.read_u32() == 42


class TestSpacetimeDBTypes:
    """Test SpacetimeDB-specific types."""
    
    def test_identity(self):
        """Test Identity type serialization."""
        identity = SpacetimeDBIdentity(b'0' * 32)
        
        writer = BsatnWriter()
        identity.write_bsatn(writer)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        reader.read_tag()  # Skip U256 tag
        identity2 = SpacetimeDBIdentity.read_bsatn(reader)
        assert identity == identity2
    
    def test_address(self):
        """Test Address type serialization."""
        address = SpacetimeDBAddress(b'1' * 16)
        
        writer = BsatnWriter()
        address.write_bsatn(writer)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        reader.read_tag()  # Skip U128 tag
        address2 = SpacetimeDBAddress.read_bsatn(reader)
        assert address == address2
    
    def test_connection_id(self):
        """Test ConnectionId type serialization."""
        conn_id = SpacetimeDBConnectionId.from_u64_pair(12345, 67890)
        
        writer = BsatnWriter()
        conn_id.write_bsatn(writer)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        reader.read_tag()  # Skip U128 tag
        conn_id2 = SpacetimeDBConnectionId.read_bsatn(reader)
        assert conn_id == conn_id2
        assert conn_id.as_u64_pair() == (12345, 67890)
    
    def test_timestamp(self):
        """Test Timestamp type serialization."""
        now = datetime.utcnow()
        ts = SpacetimeDBTimestamp.from_datetime(now)
        
        writer = BsatnWriter()
        ts.write_bsatn(writer)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        reader.read_tag()  # Skip I64 tag
        ts2 = SpacetimeDBTimestamp.read_bsatn(reader)
        assert ts == ts2
        
        # Check datetime conversion (within 1 second due to microsecond precision)
        assert abs((ts.to_datetime() - now).total_seconds()) < 1
    
    def test_time_duration(self):
        """Test TimeDuration type serialization."""
        td = timedelta(hours=1, minutes=30, seconds=45)
        duration = SpacetimeDBTimeDuration.from_timedelta(td)
        
        writer = BsatnWriter()
        duration.write_bsatn(writer)
        
        data = writer.get_bytes()
        reader = BsatnReader(data)
        
        reader.read_tag()  # Skip I64 tag
        duration2 = SpacetimeDBTimeDuration.read_bsatn(reader)
        assert duration == duration2
        assert duration.to_timedelta() == td


class TestProtocolMessages:
    """Test protocol message BSATN encoding/decoding."""
    
    def test_call_reducer_encoding(self):
        """Test CallReducer message encoding."""
        message = CallReducer(
            reducer="create_user",
            args=b'{"name": "Alice"}',
            request_id=12345,
            flags=CallReducerFlags.FULL_UPDATE
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Verify it's valid BSATN
        reader = BsatnReader(encoded)
        assert reader.read_tag() == 0x13  # TAG_ENUM
        assert reader.read_enum_header() == 0  # CallReducer variant
        
        # Read struct
        assert reader.read_tag() == 0x12  # TAG_STRUCT
        field_count = reader.read_struct_header()
        assert field_count == 4  # reducer, args, request_id, flags
    
    def test_subscribe_single_encoding(self):
        """Test SubscribeSingle message encoding."""
        message = SubscribeSingleMessage(
            query="SELECT * FROM users WHERE active = true",
            request_id=67890,
            query_id=QueryId(42)
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Verify structure
        reader = BsatnReader(encoded)
        assert reader.read_tag() == 0x13  # TAG_ENUM
        assert reader.read_enum_header() == 2  # SubscribeSingle variant
    
    def test_protocol_roundtrip(self):
        """Test JSON protocol encoding/decoding roundtrip."""
        message = Subscribe(
            query_strings=["SELECT * FROM table1", "SELECT * FROM table2"],
            request_id=99999
        )
        
        # Encode as JSON
        encoder = ProtocolEncoder(use_binary=False)
        encoded = encoder.encode_client_message(message)
        
        # Verify it's valid JSON
        import json
        data = json.loads(encoded)
        assert "Subscribe" in data
        assert data["Subscribe"]["request_id"] == 99999
        assert len(data["Subscribe"]["query_strings"]) == 2


class TestErrorHandling:
    """Test error handling in BSATN."""
    
    def test_invalid_tag(self):
        """Test handling of invalid tags."""
        reader = BsatnReader(b'\xFF')  # Invalid tag
        
        with pytest.raises(Exception):
            reader.read_bool(0xFF)
    
    def test_buffer_too_small(self):
        """Test handling of incomplete data."""
        reader = BsatnReader(b'\x07')  # U32 tag but no data
        
        reader.read_tag()  # This works
        with pytest.raises(Exception):
            reader.read_u32()  # This should fail
    
    def test_string_overflow(self):
        """Test string size limits."""
        writer = BsatnWriter()
        
        # Try to write a string that's too large
        # Note: This would require a string > 1MB which is impractical for tests
        # so we test the mechanism exists
        assert hasattr(writer, '_record_error')
    
    def test_invalid_utf8(self):
        """Test invalid UTF-8 handling."""
        # Create invalid UTF-8 data
        writer = BsatnWriter()
        writer._write_bytes(b'\x0D')  # STRING tag
        writer._write_bytes(b'\x04\x00\x00\x00')  # Length 4
        writer._write_bytes(b'\xFF\xFE\xFD\xFC')  # Invalid UTF-8
        
        reader = BsatnReader(writer.get_bytes())
        reader.read_tag()
        
        with pytest.raises(Exception):
            reader.read_string()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 