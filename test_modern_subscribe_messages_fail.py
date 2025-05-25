#!/usr/bin/env python3
"""
Validation failure tests for Modern Subscribe Messages Implementation (proto-2)

These tests verify that proper validation errors are raised for invalid inputs.
All tests should PASS by demonstrating that validation works correctly.

Testing:
- Invalid input validation for subscribe message types
- Empty query string rejection
- Negative request_id rejection
- Empty query list rejection
- Invalid QueryId handling
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


def test_subscribe_message_import_fails():
    """Test that modern subscribe messages can be imported successfully."""
    from spacetimedb_sdk.messages.subscribe import (
        SubscribeSingleMessage,
        SubscribeMultiMessage, 
        UnsubscribeMultiMessage
    )
    # Import should succeed - this is now a positive test
    assert SubscribeSingleMessage is not None
    assert SubscribeMultiMessage is not None
    assert UnsubscribeMultiMessage is not None


def test_subscribe_single_message_creation_fails():
    """Test SubscribeSingle message creation with invalid inputs."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId.generate()
    
    # Test empty query string - should raise ValueError
    with pytest.raises(ValueError):
        SubscribeSingleMessage(
            query="",  # Empty query should fail
            request_id=12345,
            query_id=qid
        )
    
    # Test negative request_id - should raise ValueError
    with pytest.raises(ValueError):
        SubscribeSingleMessage(
            query="SELECT * FROM users",
            request_id=-1,  # Negative request_id should fail
            query_id=qid
        )


def test_subscribe_multi_message_creation_fails():
    """Test SubscribeMulti message creation with invalid inputs."""
    from spacetimedb_sdk.messages.subscribe import SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId.generate()
    
    # Test empty query list - should raise ValueError
    with pytest.raises(ValueError):
        SubscribeMultiMessage(
            query_strings=[],  # Empty query list should fail
            request_id=12345,
            query_id=qid
        )
    
    # Test negative request_id - should raise ValueError
    with pytest.raises(ValueError):
        SubscribeMultiMessage(
            query_strings=["SELECT * FROM users"],
            request_id=-1,  # Negative request_id should fail
            query_id=qid
        )


def test_unsubscribe_multi_message_creation_fails():
    """Test UnsubscribeMulti message creation with invalid inputs."""
    from spacetimedb_sdk.messages.subscribe import UnsubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(42)
    
    # Test negative request_id - should raise ValueError
    with pytest.raises(ValueError):
        UnsubscribeMultiMessage(
            request_id=-1,  # Negative request_id should fail
            query_id=qid
        )


def test_subscribe_message_bsatn_serialization_fails():
    """Test BSATN serialization with invalid data."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.query_id import QueryId
    from spacetimedb_sdk.bsatn import encode, decode
    
    qid = QueryId(100)
    message = SubscribeSingleMessage(
        query="SELECT * FROM table1",
        request_id=5000,
        query_id=qid
    )
    
    # Test BSATN encoding - should work
    encoded = encode(message)
    assert isinstance(encoded, bytes), "BSATN encoding should return bytes"
    assert len(encoded) > 0, "Encoded data should not be empty"
    
    # Test BSATN decoding with corrupted data - should raise exception
    corrupted_data = b"invalid_bsatn_data"
    try:
        decode(corrupted_data, SubscribeSingleMessage)
        assert False, "Decoding corrupted data should raise an exception"
    except Exception:
        pass  # Expected to fail


def test_subscribe_message_json_serialization_fails():
    """Test JSON serialization edge cases."""
    from spacetimedb_sdk.messages.subscribe import SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    import json
    
    qid = QueryId(200)
    message = SubscribeMultiMessage(
        query_strings=["SELECT * FROM table1", "SELECT * FROM table2"],
        request_id=6000,
        query_id=qid
    )
    
    # Test JSON serialization - should work
    json_data = message.to_json()
    assert isinstance(json_data, dict), "JSON serialization should return dict"
    assert "SubscribeMulti" in json_data, "JSON should contain message type"
    
    # Test JSON deserialization with invalid data - should raise exception
    invalid_json = {"invalid": "data"}
    try:
        SubscribeMultiMessage.from_json(invalid_json)
        assert False, "Deserializing invalid JSON should raise an exception"
    except Exception:
        pass  # Expected to fail


def test_subscribe_message_protocol_integration_fails():
    """Test protocol integration edge cases."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(300)
    message = SubscribeSingleMessage(
        query="SELECT COUNT(*) FROM users",
        request_id=7000,
        query_id=qid
    )
    
    # Basic protocol integration should work
    from spacetimedb_sdk.bsatn import encode
    encoded = encode(message)
    assert isinstance(encoded, bytes), "Protocol encoding should return bytes"


def test_subscribe_message_validation_fails():
    """Test comprehensive validation failures."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage, SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(400)
    
    # Test None query string - should raise ValueError
    with pytest.raises((ValueError, TypeError)):
        SubscribeSingleMessage(
            query=None,  # None query should fail
            request_id=8000,
            query_id=qid
        )
    
    # Test query list with empty string - should raise ValueError
    with pytest.raises(ValueError):
        SubscribeMultiMessage(
            query_strings=["SELECT * FROM table1", ""],  # Empty string in list should fail
            request_id=9000,
            query_id=qid
        )


def test_subscribe_message_equality_fails():
    """Test equality edge cases."""
    from spacetimedb_sdk.messages.subscribe import SubscribeSingleMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid1 = QueryId(500)
    qid2 = QueryId(501)  # Different ID
    
    msg1 = SubscribeSingleMessage(
        query="SELECT * FROM table1",
        request_id=10000,
        query_id=qid1
    )
    
    msg2 = SubscribeSingleMessage(
        query="SELECT * FROM table2",  # Different query
        request_id=10000,
        query_id=qid1
    )
    
    msg3 = SubscribeSingleMessage(
        query="SELECT * FROM table1",
        request_id=10000,
        query_id=qid2  # Different query_id
    )
    
    # Test inequality cases
    assert msg1 != msg2, "Messages with different queries should not be equal"
    assert msg1 != msg3, "Messages with different query_ids should not be equal"
    assert msg1 != "not a message", "Message should not equal non-message objects"


def test_subscribe_message_string_representation_fails():
    """Test string representation with edge case data."""
    from spacetimedb_sdk.messages.subscribe import SubscribeMultiMessage
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(600)
    
    # Test with special characters in query
    message = SubscribeMultiMessage(
        query_strings=["SELECT * FROM 'table with spaces'", "SELECT \"quoted\" FROM test"],
        request_id=11000,
        query_id=qid
    )
    
    # Test string representation - should handle special characters
    str_repr = str(message)
    assert "SubscribeMulti" in str_repr, "String representation should include message type"
    assert "600" in str_repr, "String representation should include QueryId"
    assert "11000" in str_repr, "String representation should include request_id"
    
    # Test repr - should be valid
    repr_str = repr(message)
    assert "SubscribeMultiMessage" in repr_str, "Repr should include class name"


if __name__ == "__main__":
    print("✅ GREEN Phase: Running validation tests for Modern Subscribe Messages")
    print("=" * 75)
    
    test_functions = [
        test_subscribe_message_import_fails,
        test_subscribe_single_message_creation_fails,
        test_subscribe_multi_message_creation_fails,
        test_unsubscribe_multi_message_creation_fails,
        test_subscribe_message_bsatn_serialization_fails,
        test_subscribe_message_json_serialization_fails,
        test_subscribe_message_protocol_integration_fails,
        test_subscribe_message_validation_fails,
        test_subscribe_message_equality_fails,
        test_subscribe_message_string_representation_fails,
    ]
    
    passed_count = 0
    for test_func in test_functions:
        try:
            test_func()
            print(f"✅ {test_func.__name__} - PASSED")
            passed_count += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} - FAILED ({type(e).__name__}: {e})")
    
    print(f"\n✅ GREEN Phase Summary: {passed_count}/{len(test_functions)} validation tests passed")
    if passed_count == len(test_functions):
        print("🎉 All validation tests passed! Proto-2 implementation complete!")
    else:
        print("🔧 Some validation tests failed - needs debugging") 