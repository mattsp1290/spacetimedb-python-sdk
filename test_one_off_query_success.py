#!/usr/bin/env python3
"""
GREEN Phase: Success tests for Enhanced OneOffQuery Implementation (proto-3)

These tests verify that the enhanced OneOffQuery message types work correctly.
They should all PASS now that implementation is complete.

Testing:
- Enhanced OneOffQueryMessage with validation and BSATN support
- Enhanced OneOffQueryResponseMessage with error handling
- Modern protocol integration with proper serialization
- WebSocket client enhancements
- BSATN utils integration
- JSON serialization support
"""

import os
import sys
import uuid

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_enhanced_one_off_query_message_import_success():
    """Test that enhanced OneOffQuery message classes can be imported successfully."""
    from spacetimedb_sdk.messages.one_off_query import (
        OneOffQueryMessage,
        OneOffQueryResponseMessage,
        OneOffTable
    )
    
    # Test that they have enhanced features
    assert hasattr(OneOffQueryMessage, 'write_bsatn'), "Should have BSATN serialization"
    assert hasattr(OneOffQueryMessage, 'read_bsatn'), "Should have BSATN deserialization"
    assert hasattr(OneOffQueryMessage, 'to_json'), "Should have JSON serialization"
    assert hasattr(OneOffQueryMessage, 'from_json'), "Should have JSON deserialization"
    
    print("✅ Enhanced OneOffQuery message import successful")


def test_enhanced_one_off_query_validation_success():
    """Test enhanced OneOffQuery validation works correctly."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    
    # Test valid creation
    message_id = uuid.uuid4().bytes
    message = OneOffQueryMessage(
        message_id=message_id,
        query_string="SELECT * FROM users"
    )
    assert message.message_id == message_id
    assert message.query_string == "SELECT * FROM users"
    
    # Test validation is enforced
    try:
        OneOffQueryMessage(
            message_id=message_id,
            query_string=""  # Empty query should fail validation
        )
        assert False, "Should have raised ValueError for empty query"
    except ValueError:
        pass  # Expected
    
    try:
        OneOffQueryMessage(
            message_id=b"",  # Empty message_id should fail validation
            query_string="SELECT * FROM users"
        )
        assert False, "Should have raised ValueError for empty message_id"
    except ValueError:
        pass  # Expected
    
    print("✅ Enhanced OneOffQuery validation successful")


def test_enhanced_one_off_query_bsatn_methods_success():
    """Test that enhanced OneOffQuery has working BSATN methods."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    from spacetimedb_sdk.bsatn.writer import BsatnWriter
    from spacetimedb_sdk.bsatn.reader import BsatnReader
    
    message_id = uuid.uuid4().bytes
    message = OneOffQueryMessage(
        message_id=message_id,
        query_string="SELECT * FROM products"
    )
    
    # Test write_bsatn method
    writer = BsatnWriter()
    message.write_bsatn(writer)
    assert not writer.error(), "BSATN writing should not error"
    
    # Test that the class has read_bsatn method
    assert hasattr(OneOffQueryMessage, 'read_bsatn'), "Should have read_bsatn class method"
    
    # Test round-trip serialization
    encoded = writer.get_bytes()
    reader = BsatnReader(encoded)
    decoded = OneOffQueryMessage.read_bsatn(reader)
    
    assert decoded.message_id == message.message_id
    assert decoded.query_string == message.query_string
    
    print("✅ Enhanced OneOffQuery BSATN methods successful")


def test_enhanced_one_off_query_json_methods_success():
    """Test that enhanced OneOffQuery has working JSON methods."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    
    message_id = uuid.uuid4().bytes
    message = OneOffQueryMessage(
        message_id=message_id,
        query_string="SELECT COUNT(*) FROM orders"
    )
    
    # Test JSON serialization method
    json_data = message.to_json()
    assert isinstance(json_data, dict), "Should return dict"
    assert "OneOffQuery" in json_data, "Should contain message type"
    
    # Test JSON deserialization method
    reconstructed = OneOffQueryMessage.from_json(json_data)
    assert reconstructed.message_id == message.message_id
    assert reconstructed.query_string == message.query_string
    
    print("✅ Enhanced OneOffQuery JSON methods successful")


def test_enhanced_one_off_query_response_error_handling_success():
    """Test enhanced OneOffQueryResponse error handling works correctly."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryResponseMessage, OneOffTable
    
    message_id = uuid.uuid4().bytes
    
    # Test error response
    error_response = OneOffQueryResponseMessage(
        message_id=message_id,
        error="Table 'nonexistent' doesn't exist",
        tables=[],
        total_host_execution_duration_micros=500
    )
    
    # Test enhanced error handling methods
    assert error_response.has_error(), "Should detect error condition"
    assert not error_response.is_success(), "Should not be success with error"
    assert error_response.get_error_message() == "Table 'nonexistent' doesn't exist"
    
    # Test success case
    success_response = OneOffQueryResponseMessage(
        message_id=message_id,
        error=None,
        tables=[OneOffTable(table_name="users", rows=[])],
        total_host_execution_duration_micros=200
    )
    
    assert not success_response.has_error(), "Should not detect error"
    assert success_response.is_success(), "Should be success without error"
    assert success_response.get_table_count() == 1
    assert success_response.get_total_rows() == 0
    
    print("✅ Enhanced OneOffQueryResponse error handling successful")


def test_enhanced_websocket_client_integration_success():
    """Test enhanced WebSocket client OneOffQuery integration works correctly."""
    from spacetimedb_sdk.websocket_client import ModernWebSocketClient
    
    client = ModernWebSocketClient()
    
    # Test that client has enhanced execute_one_off_query method
    assert hasattr(client, 'execute_one_off_query'), "Should have execute_one_off_query method"
    
    # We can't test actual execution without a connection, but we can verify method signature
    import inspect
    sig = inspect.signature(client.execute_one_off_query)
    params = list(sig.parameters.keys())
    assert 'query' in params, "Should have query parameter"
    
    print("✅ Enhanced WebSocket client integration successful")


def test_bsatn_utils_integration_success():
    """Test that BSATN utils can handle enhanced OneOffQuery correctly."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    from spacetimedb_sdk.bsatn import encode, decode
    
    message_id = uuid.uuid4().bytes
    message = OneOffQueryMessage(
        message_id=message_id,
        query_string="SELECT * FROM inventory"
    )
    
    # Test encoding with bsatn.encode()
    encoded = encode(message)
    assert isinstance(encoded, bytes), "Should encode to bytes"
    
    # Test decoding with type hint
    decoded = decode(encoded, OneOffQueryMessage)
    assert isinstance(decoded, OneOffQueryMessage), "Should decode to OneOffQueryMessage"
    assert decoded.message_id == message.message_id
    assert decoded.query_string == message.query_string
    
    print("✅ BSATN utils integration successful")


def test_protocol_encoder_enhanced_support_success():
    """Test that ProtocolEncoder properly handles enhanced OneOffQuery."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    from spacetimedb_sdk.protocol import ProtocolEncoder
    
    message_id = uuid.uuid4().bytes
    message = OneOffQueryMessage(
        message_id=message_id,
        query_string="SELECT * FROM transactions"
    )
    
    # Test that ProtocolEncoder can handle enhanced message
    encoder = ProtocolEncoder(use_binary=True)
    encoded = encoder.encode_client_message(message)
    assert isinstance(encoded, bytes), "Should encode to bytes"
    
    # Test JSON encoding too
    json_encoder = ProtocolEncoder(use_binary=False)
    json_encoded = json_encoder.encode_client_message(message)
    assert isinstance(json_encoded, bytes), "Should encode to JSON bytes"
    
    print("✅ Enhanced protocol encoder support successful")


def test_enhanced_message_equality_and_repr_success():
    """Test enhanced OneOffQuery equality and string representation work correctly."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    
    message_id1 = uuid.uuid4().bytes
    message_id2 = message_id1  # Same ID
    
    msg1 = OneOffQueryMessage(
        message_id=message_id1,
        query_string="SELECT * FROM users"
    )
    
    msg2 = OneOffQueryMessage(
        message_id=message_id2,
        query_string="SELECT * FROM users"
    )
    
    # Test enhanced equality
    assert msg1 == msg2, "Messages with same content should be equal"
    assert hash(msg1) == hash(msg2), "Equal messages should have same hash"
    
    # Test enhanced string representation
    str_repr = str(msg1)
    assert "OneOffQuery" in str_repr, "Should include message type in string"
    assert "users" in str_repr, "Should include query info"
    
    repr_str = repr(msg1)
    assert "OneOffQueryMessage" in repr_str, "Should include class name in repr"
    
    print("✅ Enhanced equality and repr successful")


def test_messages_module_exports_success():
    """Test that messages module properly exports OneOffQuery classes."""
    from spacetimedb_sdk.messages import (
        OneOffQueryMessage,
        OneOffQueryResponseMessage,
        OneOffTable
    )
    
    assert OneOffQueryMessage is not None
    assert OneOffQueryResponseMessage is not None
    assert OneOffTable is not None
    
    print("✅ Messages module exports successful")


def test_advanced_features_success():
    """Test advanced OneOffQuery features work correctly."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage, OneOffQueryResponseMessage, OneOffTable
    
    # Test generate class method
    query = "SELECT * FROM advanced_table"
    message = OneOffQueryMessage.generate(query)
    assert len(message.message_id) == 16, "Should generate 16-byte UUID"
    assert message.query_string == query
    
    # Test OneOffTable functionality
    table = OneOffTable(
        table_name="test_table",
        rows=[{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}]
    )
    
    table_json = table.to_json()
    reconstructed_table = OneOffTable.from_json(table_json)
    assert reconstructed_table.table_name == table.table_name
    assert reconstructed_table.rows == table.rows
    
    # Test response with multiple tables
    response = OneOffQueryResponseMessage(
        message_id=message.message_id,
        error=None,
        tables=[table, OneOffTable("empty_table", [])],
        total_host_execution_duration_micros=1500
    )
    
    assert response.get_table_count() == 2
    assert response.get_total_rows() == 2
    assert response.is_success()
    
    print("✅ Advanced features successful")


if __name__ == "__main__":
    print("🟢 GREEN Phase: Running success tests for Enhanced OneOffQuery Implementation")
    print("=" * 75)
    
    test_functions = [
        test_enhanced_one_off_query_message_import_success,
        test_enhanced_one_off_query_validation_success,
        test_enhanced_one_off_query_bsatn_methods_success,
        test_enhanced_one_off_query_json_methods_success,
        test_enhanced_one_off_query_response_error_handling_success,
        test_enhanced_websocket_client_integration_success,
        test_bsatn_utils_integration_success,
        test_protocol_encoder_enhanced_support_success,
        test_enhanced_message_equality_and_repr_success,
        test_messages_module_exports_success,
        test_advanced_features_success,
    ]
    
    passed_count = 0
    for test_func in test_functions:
        try:
            test_func()
            passed_count += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} - FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n🟢 GREEN Phase Summary: {passed_count}/{len(test_functions)} tests passed")
    if passed_count == len(test_functions):
        print("🎉 All Enhanced OneOffQuery tests passed! Implementation complete.")
        print("Ready to move to proto-4 (CallReducer Enhancements)!")
    else:
        print("❌ Some tests failed. Need to fix implementation.")
        sys.exit(1) 