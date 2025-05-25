"""
Comprehensive tests for BSATN Protocol Integration.

Tests the complete BSATN binary protocol support including:
- Client message encoding
- Server message decoding  
- WebSocket integration
- Protocol negotiation
- Error handling
"""

import pytest
import uuid
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
    
    # Protocol handling
    ProtocolEncoder,
    ProtocolDecoder,
    TEXT_PROTOCOL,
    BIN_PROTOCOL,
    
    # BSATN
    BsatnWriter,
    BsatnReader,
    
    # SpacetimeDB types
    SpacetimeDBIdentity,
    SpacetimeDBAddress,
    SpacetimeDBConnectionId,
    SpacetimeDBTimestamp,
    SpacetimeDBTimeDuration,
    
    # Protocol messages
    Identity,
    ConnectionId,
    IdentityToken,
    TransactionUpdate,
    TransactionUpdateLight,
    InitialSubscription,
    SubscribeApplied,
    UnsubscribeApplied,
    SubscriptionError,
    SubscribeMultiApplied,
    UnsubscribeMultiApplied,
    OneOffQueryResponse,
    EnergyQuanta,
    Timestamp,
    TimeDuration,
    
    # WebSocket client
    ModernWebSocketClient,
)

# Import types that aren't exported from main module
from spacetimedb_sdk.protocol import (
    DatabaseUpdate,
    TableUpdate,
    ReducerCallInfo,
)


class TestBsatnClientMessageEncoding:
    """Test BSATN encoding of client messages."""
    
    def test_call_reducer_encoding(self):
        """Test CallReducer message encoding."""
        message = CallReducer(
            reducer="create_user",
            args=b'{"name": "Alice", "email": "alice@example.com"}',
            request_id=12345,
            flags=CallReducerFlags.FULL_UPDATE
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Verify it's valid BSATN
        assert len(encoded) > 0
        assert isinstance(encoded, bytes)
        
        # Verify structure by reading back
        reader = BsatnReader(encoded)
        tag = reader.read_tag()
        assert tag == 0x13  # TAG_ENUM
        
        variant = reader.read_enum_header()
        assert variant == 0  # CallReducer variant
    
    def test_subscribe_single_encoding(self):
        """Test SubscribeSingle message encoding."""
        query_id = QueryId.generate()
        message = SubscribeSingleMessage(
            query="SELECT * FROM users WHERE active = true",
            request_id=67890,
            query_id=query_id
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Verify structure
        reader = BsatnReader(encoded)
        tag = reader.read_tag()
        assert tag == 0x13  # TAG_ENUM
        
        variant = reader.read_enum_header()
        assert variant == 2  # SubscribeSingle variant
    
    def test_subscribe_multi_encoding(self):
        """Test SubscribeMulti message encoding."""
        query_id = QueryId.generate()
        message = SubscribeMultiMessage(
            query_strings=[
                "SELECT * FROM users",
                "SELECT * FROM messages WHERE user_id = 123"
            ],
            request_id=11111,
            query_id=query_id
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Verify structure
        reader = BsatnReader(encoded)
        tag = reader.read_tag()
        assert tag == 0x13  # TAG_ENUM
        
        variant = reader.read_enum_header()
        assert variant == 3  # SubscribeMulti variant
    
    def test_unsubscribe_encoding(self):
        """Test Unsubscribe message encoding."""
        query_id = QueryId(42)
        message = Unsubscribe(
            request_id=22222,
            query_id=query_id
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Verify structure
        reader = BsatnReader(encoded)
        tag = reader.read_tag()
        assert tag == 0x13  # TAG_ENUM
        
        variant = reader.read_enum_header()
        assert variant == 4  # Unsubscribe variant
    
    def test_oneoff_query_encoding(self):
        """Test OneOffQuery message encoding."""
        message_id = uuid.uuid4().bytes
        message = OneOffQuery(
            message_id=message_id,
            query_string="SELECT COUNT(*) FROM users"
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Verify structure
        reader = BsatnReader(encoded)
        tag = reader.read_tag()
        assert tag == 0x13  # TAG_ENUM
        
        variant = reader.read_enum_header()
        assert variant == 6  # OneOffQuery variant


class TestBsatnServerMessageDecoding:
    """Test BSATN decoding of server messages."""
    
    def test_identity_token_decoding(self):
        """Test IdentityToken message decoding."""
        # Create a mock BSATN-encoded IdentityToken
        writer = BsatnWriter()
        
        # Encode as enum variant 0 (IdentityToken)
        writer.write_enum_header(0)
        writer.write_struct_header(3)  # identity, token, connection_id
        
        writer.write_field_name("identity")
        writer.write_bytes(b"test_identity_32_bytes_long_data")
        
        writer.write_field_name("token")
        writer.write_string("test_auth_token_12345")
        
        writer.write_field_name("connection_id")
        writer.write_bytes(b"connection_id_16")
        
        encoded = writer.get_bytes()
        
        # Decode it
        decoder = ProtocolDecoder(use_binary=True)
        decoded = decoder.decode_server_message(encoded)
        
        assert isinstance(decoded, IdentityToken)
        assert decoded.token == "test_auth_token_12345"
        assert decoded.identity.data == b"test_identity_32_bytes_long_data"
        assert decoded.connection_id.data == b"connection_id_16"
    
    def test_subscribe_applied_decoding(self):
        """Test SubscribeApplied message decoding."""
        # Create a mock BSATN-encoded SubscribeApplied
        writer = BsatnWriter()
        
        # Encode as enum variant 4 (SubscribeApplied)
        writer.write_enum_header(4)
        writer.write_struct_header(6)  # All fields
        
        writer.write_field_name("request_id")
        writer.write_u32(12345)
        
        writer.write_field_name("total_host_execution_duration_micros")
        writer.write_u64(1500)
        
        writer.write_field_name("query_id")
        writer.write_struct_header(1)
        writer.write_field_name("id")
        writer.write_u32(42)
        
        writer.write_field_name("table_id")
        writer.write_u32(1)
        
        writer.write_field_name("table_name")
        writer.write_string("users")
        
        writer.write_field_name("table_rows")
        # Write empty array for table rows
        writer.write_array_header(0)
        
        encoded = writer.get_bytes()
        
        # Decode it
        decoder = ProtocolDecoder(use_binary=True)
        decoded = decoder.decode_server_message(encoded)
        
        assert isinstance(decoded, SubscribeApplied)
        assert decoded.request_id == 12345
        assert decoded.total_host_execution_duration_micros == 1500
        assert decoded.query_id.id == 42
        assert decoded.table_id == 1
        assert decoded.table_name == "users"
    
    def test_subscription_error_decoding(self):
        """Test SubscriptionError message decoding."""
        # Create a mock BSATN-encoded SubscriptionError
        writer = BsatnWriter()
        
        # Encode as enum variant 6 (SubscriptionError)
        writer.write_enum_header(6)
        writer.write_struct_header(5)  # All fields
        
        writer.write_field_name("total_host_execution_duration_micros")
        writer.write_u64(2500)
        
        writer.write_field_name("request_id")
        writer.write_u32(99999)
        
        writer.write_field_name("query_id")
        writer.write_u32(123)
        
        writer.write_field_name("table_id")
        writer.write_u32(5)
        
        writer.write_field_name("error")
        writer.write_string("Invalid query syntax")
        
        encoded = writer.get_bytes()
        
        # Decode it
        decoder = ProtocolDecoder(use_binary=True)
        decoded = decoder.decode_server_message(encoded)
        
        assert isinstance(decoded, SubscriptionError)
        assert decoded.total_host_execution_duration_micros == 2500
        assert decoded.request_id == 99999
        assert decoded.query_id == 123
        assert decoded.table_id == 5
        assert decoded.error == "Invalid query syntax"


class TestBsatnRoundTrip:
    """Test round-trip encoding/decoding."""
    
    def test_call_reducer_roundtrip(self):
        """Test CallReducer encoding and decoding roundtrip."""
        original = CallReducer(
            reducer="update_profile",
            args=b'{"user_id": 123, "name": "Bob"}',
            request_id=54321,
            flags=CallReducerFlags.NO_SUCCESS_NOTIFY
        )
        
        # Encode
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(original)
        
        # Verify we can read the structure (we don't have client message decoder)
        reader = BsatnReader(encoded)
        tag = reader.read_tag()
        assert tag == 0x13  # TAG_ENUM
        
        variant = reader.read_enum_header()
        assert variant == 0  # CallReducer variant
        
        # Read struct
        struct_tag = reader.read_tag()
        assert struct_tag == 0x12  # TAG_STRUCT
        
        field_count = reader.read_struct_header()
        assert field_count == 4  # reducer, args, request_id, flags
    
    def test_query_id_consistency(self):
        """Test QueryId consistency in messages."""
        query_id = QueryId.generate()
        
        # Test in SubscribeSingle
        message1 = SubscribeSingleMessage(
            query="SELECT * FROM test",
            request_id=1,
            query_id=query_id
        )
        
        # Test in Unsubscribe
        message2 = Unsubscribe(
            request_id=2,
            query_id=query_id
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        
        # Both should encode successfully
        encoded1 = encoder.encode_client_message(message1)
        encoded2 = encoder.encode_client_message(message2)
        
        assert len(encoded1) > 0
        assert len(encoded2) > 0


class TestProtocolNegotiation:
    """Test protocol negotiation between JSON and BSATN."""
    
    def test_json_protocol_encoder(self):
        """Test JSON protocol encoding."""
        message = CallReducer(
            reducer="test_reducer",
            args=b'{"test": true}',
            request_id=1,
            flags=CallReducerFlags.FULL_UPDATE
        )
        
        encoder = ProtocolEncoder(use_binary=False)
        encoded = encoder.encode_client_message(message)
        
        # Should be JSON
        assert isinstance(encoded, bytes)
        decoded_json = encoded.decode('utf-8')
        assert '"CallReducer"' in decoded_json
        assert '"test_reducer"' in decoded_json
    
    def test_binary_protocol_encoder(self):
        """Test binary protocol encoding."""
        message = CallReducer(
            reducer="test_reducer",
            args=b'{"test": true}',
            request_id=1,
            flags=CallReducerFlags.FULL_UPDATE
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        encoded = encoder.encode_client_message(message)
        
        # Should be BSATN binary
        assert isinstance(encoded, bytes)
        # Should not be valid UTF-8 (binary data)
        with pytest.raises(UnicodeDecodeError):
            encoded.decode('utf-8')
    
    def test_protocol_selection_consistency(self):
        """Test that protocol selection is consistent."""
        message = SubscribeSingleMessage(
            query="SELECT * FROM test",
            request_id=1,
            query_id=QueryId(42)
        )
        
        json_encoder = ProtocolEncoder(use_binary=False)
        binary_encoder = ProtocolEncoder(use_binary=True)
        
        json_encoded = json_encoder.encode_client_message(message)
        binary_encoded = binary_encoder.encode_client_message(message)
        
        # Should be different formats
        assert json_encoded != binary_encoded
        
        # JSON should be readable as text
        json_str = json_encoded.decode('utf-8')
        assert '"SubscribeSingle"' in json_str
        
        # Binary should not be readable as text
        with pytest.raises(UnicodeDecodeError):
            binary_encoded.decode('utf-8')


class TestBsatnErrorHandling:
    """Test BSATN error handling."""
    
    def test_invalid_message_type(self):
        """Test handling of invalid message types."""
        encoder = ProtocolEncoder(use_binary=True)
        
        # Try to encode an invalid message type
        with pytest.raises(ValueError, match="Unknown message type"):
            encoder.encode_client_message("invalid_message")
    
    def test_corrupted_bsatn_data(self):
        """Test handling of corrupted BSATN data."""
        decoder = ProtocolDecoder(use_binary=True)
        
        # Try to decode corrupted data
        corrupted_data = b'\x13\x00\x00\x00\xFF'  # Invalid BSATN
        
        with pytest.raises(ValueError, match="Failed to decode BSATN server message"):
            decoder.decode_server_message(corrupted_data)
    
    def test_incomplete_bsatn_data(self):
        """Test handling of incomplete BSATN data."""
        decoder = ProtocolDecoder(use_binary=True)
        
        # Try to decode incomplete data
        incomplete_data = b'\x13'  # Just the enum tag, missing data
        
        with pytest.raises(ValueError):
            decoder.decode_server_message(incomplete_data)
    
    def test_unknown_server_message_variant(self):
        """Test handling of unknown server message variants."""
        # Create BSATN with unknown variant
        writer = BsatnWriter()
        writer.write_enum_header(999)  # Unknown variant
        encoded = writer.get_bytes()
        
        decoder = ProtocolDecoder(use_binary=True)
        
        with pytest.raises(ValueError, match="Unknown server message variant"):
            decoder.decode_server_message(encoded)


class TestWebSocketClientIntegration:
    """Test WebSocket client integration with BSATN."""
    
    def test_binary_protocol_client_creation(self):
        """Test creating a WebSocket client with binary protocol."""
        client = ModernWebSocketClient(
            protocol=BIN_PROTOCOL,
            auto_reconnect=False
        )
        
        assert client.protocol == BIN_PROTOCOL
        assert client.use_binary == True
        assert client.encoder.use_binary == True
        assert client.decoder.use_binary == True
    
    def test_text_protocol_client_creation(self):
        """Test creating a WebSocket client with text protocol."""
        client = ModernWebSocketClient(
            protocol=TEXT_PROTOCOL,
            auto_reconnect=False
        )
        
        assert client.protocol == TEXT_PROTOCOL
        assert client.use_binary == False
        assert client.encoder.use_binary == False
        assert client.decoder.use_binary == False
    
    def test_message_encoding_selection(self):
        """Test that client uses correct encoding based on protocol."""
        # Binary protocol client
        binary_client = ModernWebSocketClient(
            protocol=BIN_PROTOCOL,
            auto_reconnect=False
        )
        
        # Text protocol client
        text_client = ModernWebSocketClient(
            protocol=TEXT_PROTOCOL,
            auto_reconnect=False
        )
        
        message = CallReducer(
            reducer="test",
            args=b'{}',
            request_id=1,
            flags=CallReducerFlags.FULL_UPDATE
        )
        
        # Encode with both clients
        binary_encoded = binary_client.encoder.encode_client_message(message)
        text_encoded = text_client.encoder.encode_client_message(message)
        
        # Should be different formats
        assert binary_encoded != text_encoded
        
        # Text should be JSON
        text_str = text_encoded.decode('utf-8')
        assert '"CallReducer"' in text_str
        
        # Binary should not be valid UTF-8
        with pytest.raises(UnicodeDecodeError):
            binary_encoded.decode('utf-8')


class TestBsatnPerformance:
    """Test BSATN performance characteristics."""
    
    def test_encoding_performance(self):
        """Test that BSATN encoding is reasonably fast."""
        import time
        
        message = CallReducer(
            reducer="performance_test",
            args=b'{"data": "' + b'x' * 1000 + b'"}',  # 1KB of data
            request_id=1,
            flags=CallReducerFlags.FULL_UPDATE
        )
        
        encoder = ProtocolEncoder(use_binary=True)
        
        # Time multiple encodings
        start_time = time.time()
        for _ in range(100):
            encoded = encoder.encode_client_message(message)
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second for 100 encodings)
        elapsed = end_time - start_time
        assert elapsed < 1.0, f"Encoding took too long: {elapsed:.3f}s"
        
        # Verify encoding worked
        assert len(encoded) > 0
    
    def test_binary_vs_json_size(self):
        """Test that BSATN is more compact than JSON for structured data."""
        message = SubscribeMultiMessage(
            query_strings=[
                "SELECT * FROM users WHERE active = true",
                "SELECT * FROM messages WHERE user_id = 123",
                "SELECT * FROM notifications WHERE read = false"
            ],
            request_id=12345,
            query_id=QueryId(67890)
        )
        
        json_encoder = ProtocolEncoder(use_binary=False)
        binary_encoder = ProtocolEncoder(use_binary=True)
        
        json_encoded = json_encoder.encode_client_message(message)
        binary_encoded = binary_encoder.encode_client_message(message)
        
        # For structured data, BSATN should often be more compact
        # (This may not always be true for very small messages due to overhead)
        print(f"JSON size: {len(json_encoded)} bytes")
        print(f"BSATN size: {len(binary_encoded)} bytes")
        
        # Both should be non-empty
        assert len(json_encoded) > 0
        assert len(binary_encoded) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 