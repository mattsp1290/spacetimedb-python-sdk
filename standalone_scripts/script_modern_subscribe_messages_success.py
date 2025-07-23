#!/usr/bin/env python3
"""
GREEN Phase: Success tests for Modern Subscribe Messages Implementation (proto-2)

These tests verify that the modern subscribe message types work correctly.
They should all PASS now that implementation is complete.

Testing:
- SubscribeSingle message creation and serialization
- SubscribeMulti message creation and serialization  
- UnsubscribeMulti message handling
- BSATN serialization for all message types
- JSON fallback serialization
- Integration with ClientMessage enum
- QueryId integration
- Validation and error handling
"""

import os
import sys

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Optional pytest import
try:
    import pytest
except ImportError:
    # Create a simple mock for pytest.raises
    class MockPytest:
        @staticmethod
        def raises(exception_type):
            class RaisesContext:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    if exc_type is None:
                        raise AssertionError(f"Expected {exception_type.__name__} but no exception was raised")
                    return issubclass(exc_type, exception_type)
            return RaisesContext()
    pytest = MockPytest()


def test_subscribe_message_import_success():
    """Test that modern subscribe messages can be imported successfully."""
    from spacetimedb_sdk.messages.subscribe import (
        SubscribeSingleMessage,
        SubscribeMultiMessage, 
        UnsubscribeMultiMessage
    )
    assert SubscribeSingleMessage is not None
    assert SubscribeMultiMessage is not None
    assert UnsubscribeMultiMessage is not None
    print("✅ Subscribe message import successful")


def test_subscribe_single_message_creation_success():
    """Test SubscribeSingle message creation works correctly.""" 
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId.generate()
    message = SubscribeSingleMessage(
        query="SELECT * FROM users",
        request_id=12345,
        query_id=qid
    )
    
    assert message.query == "SELECT * FROM users"
    assert message.request_id == 12345
    assert message.query_id == qid
    print("✅ SubscribeSingle creation successful")


def test_subscribe_multi_message_creation_success():
    """Test SubscribeMulti message creation works correctly."""
    from spacetimedb_sdk.messages.subscribe import SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId.generate()
    queries = ["SELECT * FROM users", "SELECT * FROM posts"]
    message = SubscribeMultiMessage(
        query_strings=queries,
        request_id=12345,
        query_id=qid
    )
    
    assert message.query_strings == queries
    assert message.request_id == 12345
    assert message.query_id == qid
    print("✅ SubscribeMulti creation successful")


def test_unsubscribe_multi_message_creation_success():
    """Test UnsubscribeMulti message creation works correctly."""
    from spacetimedb_sdk.messages.subscribe import UnsubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(42)
    message = UnsubscribeMultiMessage(
        request_id=12345,
        query_id=qid
    )
    
    assert message.request_id == 12345
    assert message.query_id == qid
    print("✅ UnsubscribeMulti creation successful")


def test_subscribe_message_bsatn_serialization_success():
    """Test BSATN serialization of subscribe messages works correctly."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.query_id import QueryId
    from spacetimedb_sdk.bsatn import encode, decode
    
    qid = QueryId(100)
    message = SubscribeSingleMessage(
        query="SELECT * FROM table1",
        request_id=5000,
        query_id=qid
    )
    
    # Test BSATN encoding
    encoded = encode(message)
    assert isinstance(encoded, bytes), "BSATN encoding should return bytes"
    assert len(encoded) > 0, "Encoded data should not be empty"
    
    # Test BSATN decoding with type hint
    decoded = decode(encoded, SubscribeSingleMessage)
    assert isinstance(decoded, SubscribeSingleMessage), "Decoded value should be SubscribeSingleMessage"
    assert decoded.query == message.query
    assert decoded.request_id == message.request_id
    assert decoded.query_id == message.query_id
    
    print("✅ Subscribe message BSATN serialization successful")


def test_subscribe_message_json_serialization_success():
    """Test JSON serialization of subscribe messages works correctly."""
    from spacetimedb_sdk.messages.subscribe import SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    import json
    
    qid = QueryId(200)
    message = SubscribeMultiMessage(
        query_strings=["SELECT * FROM table1", "SELECT * FROM table2"],
        request_id=6000,
        query_id=qid
    )
    
    # Test JSON serialization
    json_data = message.to_json()
    assert isinstance(json_data, dict), "JSON serialization should return dict"
    assert "SubscribeMulti" in json_data, "JSON should contain message type"
    
    # Test JSON deserialization
    reconstructed = SubscribeMultiMessage.from_json(json_data)
    assert reconstructed.query_strings == message.query_strings
    assert reconstructed.request_id == message.request_id
    assert reconstructed.query_id.id == message.query_id.id
    
    print("✅ Subscribe message JSON serialization successful")


def test_subscribe_message_protocol_integration_success():
    """Test integration with protocol ClientMessage enum works correctly."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.protocol import ClientMessage, ProtocolEncoder
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(300)
    message = SubscribeSingleMessage(
        query="SELECT COUNT(*) FROM users",
        request_id=7000,
        query_id=qid
    )
    
    # Test that message can be used as ClientMessage
    # Since ClientMessage is a Union type, we can't test isinstance directly
    # but we can test that it works with the protocol encoder
    
    # Test protocol encoding
    encoder = ProtocolEncoder(use_binary=False)
    encoded = encoder.encode_client_message(message)
    assert isinstance(encoded, bytes), "Protocol encoding should return bytes"
    
    print("✅ Subscribe message protocol integration successful")


def test_subscribe_message_validation_success():
    """Test subscribe message validation works correctly."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage, SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(400)
    
    # Test invalid query string
    try:
        SubscribeSingleMessage(
            query="",  # Empty query should fail
            request_id=8000,
            query_id=qid
        )
        assert False, "Should have raised ValueError for empty query"
    except ValueError:
        pass  # Expected
    
    # Test invalid request_id
    try:
        SubscribeSingleMessage(
            query="SELECT * FROM table1",
            request_id=-1,  # Negative request_id should fail
            query_id=qid
        )
        assert False, "Should have raised ValueError for negative request_id"
    except ValueError:
        pass  # Expected
    
    # Test empty query list
    try:
        SubscribeMultiMessage(
            query_strings=[],  # Empty query list should fail
            request_id=9000,
            query_id=qid
        )
        assert False, "Should have raised ValueError for empty query list"
    except ValueError:
        pass  # Expected
    
    print("✅ Subscribe message validation successful")


def test_subscribe_message_equality_success():
    """Test subscribe message equality and hashing works correctly."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid1 = QueryId(500)
    qid2 = QueryId(500)  # Same ID
    qid3 = QueryId(501)  # Different ID
    
    msg1 = SubscribeSingleMessage(
        query="SELECT * FROM table1",
        request_id=10000,
        query_id=qid1
    )
    
    msg2 = SubscribeSingleMessage(
        query="SELECT * FROM table1",
        request_id=10000,
        query_id=qid2
    )
    
    msg3 = SubscribeSingleMessage(
        query="SELECT * FROM table1",
        request_id=10000,
        query_id=qid3
    )
    
    # Test equality
    assert msg1 == msg2, "Messages with same content should be equal"
    assert msg1 != msg3, "Messages with different query_ids should not be equal"
    
    # Test hashing
    assert hash(msg1) == hash(msg2), "Equal messages should have same hash"
    msg_set = {msg1, msg2, msg3}
    assert len(msg_set) == 2, "Set should contain only unique messages"
    
    print("✅ Subscribe message equality and hashing successful")


def test_subscribe_message_string_representation_success():
    """Test subscribe message string representation works correctly."""
    from spacetimedb_sdk.messages.subscribe import UnsubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(600)
    message = UnsubscribeMultiMessage(
        request_id=11000,
        query_id=qid
    )
    
    # Test string representation
    str_repr = str(message)
    assert "UnsubscribeMulti" in str_repr, "String representation should include message type"
    assert "600" in str_repr, "String representation should include QueryId"
    assert "11000" in str_repr, "String representation should include request_id"
    
    # Test repr
    repr_str = repr(message)
    assert "UnsubscribeMultiMessage" in repr_str, "Repr should include class name"
    
    print("✅ Subscribe message string representation successful")


def test_subscribe_message_advanced_features():
    """Test advanced subscribe message features."""
    from spacetimedb_sdk.messages.subscribe import SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    # Test multiple query validation
    qid = QueryId(700)
    queries = [
        "SELECT * FROM users",
        "SELECT * FROM posts WHERE author_id = 123",
        "SELECT COUNT(*) FROM comments"
    ]
    
    message = SubscribeMultiMessage(
        query_strings=queries,
        request_id=12000,
        query_id=qid
    )
    
    assert len(message.query_strings) == 3
    assert all(isinstance(q, str) for q in message.query_strings)
    
    # Test that whitespace-only queries are rejected
    try:
        SubscribeMultiMessage(
            query_strings=["SELECT * FROM users", "   ", "SELECT * FROM posts"],
            request_id=13000,
            query_id=qid
        )
        assert False, "Should have raised ValueError for whitespace-only query"
    except ValueError:
        pass  # Expected
    
    print("✅ Subscribe message advanced features successful")


if __name__ == "__main__":
    print("🟢 GREEN Phase: Running success tests for Modern Subscribe Messages")
    print("=" * 75)
    
    test_functions = [
        test_subscribe_message_import_success,
        test_subscribe_single_message_creation_success,
        test_subscribe_multi_message_creation_success,
        test_unsubscribe_multi_message_creation_success,
        test_subscribe_message_bsatn_serialization_success,
        test_subscribe_message_json_serialization_success,
        test_subscribe_message_protocol_integration_success,
        test_subscribe_message_validation_success,
        test_subscribe_message_equality_success,
        test_subscribe_message_string_representation_success,
        test_subscribe_message_advanced_features,
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
        print("🎉 All Subscribe Message tests passed! Implementation complete.")
        print("Ready to move to proto-3 (OneOffQuery Implementation)!")
    else:
        print("❌ Some tests failed. Need to fix implementation.")
        sys.exit(1) 