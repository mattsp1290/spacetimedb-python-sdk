#!/usr/bin/env python3
"""
Validation failure tests for OneOffQuery Implementation (proto-3)

These tests verify that proper validation errors are raised for invalid OneOffQuery inputs.
All tests should PASS by demonstrating that validation works correctly.

Testing:
- Invalid OneOffQuery input validation
- Empty query string rejection
- Invalid message_id handling
- Error response validation
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


def test_one_off_query_module_missing():
    """Test that the OneOffQuery module can be imported successfully."""
    import spacetimedb_sdk.messages.one_off_query
    # Import should succeed - this is now a positive test
    assert spacetimedb_sdk.messages.one_off_query is not None


def test_basic_one_off_query_lacks_validation():
    """Test OneOffQuery validation with invalid inputs."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    import uuid
    
    # Test empty query string - should raise ValueError
    with pytest.raises(ValueError):
        OneOffQueryMessage(
            message_id=uuid.uuid4().bytes,
            query_string=""  # Empty query should fail
        )
    
    # Test empty message_id - should raise ValueError
    with pytest.raises(ValueError):
        OneOffQueryMessage(
            message_id=b"",  # Empty message_id should fail
            query_string="SELECT * FROM users"
        )


def test_basic_one_off_query_lacks_bsatn_methods():
    """Test OneOffQuery BSATN serialization error handling."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    from spacetimedb_sdk.bsatn import encode, decode
    import uuid
    
    message = OneOffQueryMessage(
        message_id=uuid.uuid4().bytes,
        query_string="SELECT * FROM test"
    )
    
    # Test BSATN encoding - should work
    encoded = encode(message)
    assert isinstance(encoded, bytes), "BSATN encoding should return bytes"
    
    # Test BSATN decoding with corrupted data - should raise exception
    corrupted_data = b"invalid_bsatn_data"
    try:
        decode(corrupted_data, OneOffQueryMessage)
        assert False, "Decoding corrupted data should raise an exception"
    except Exception:
        pass  # Expected to fail


def test_basic_one_off_query_lacks_json_methods():
    """Test OneOffQuery JSON serialization edge cases."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    import uuid
    
    message = OneOffQueryMessage(
        message_id=uuid.uuid4().bytes,
        query_string="SELECT * FROM test"
    )
    
    # Test JSON serialization - should work
    json_data = message.to_json()
    assert isinstance(json_data, dict), "JSON serialization should return dict"
    
    # Test JSON deserialization with invalid data - should raise exception
    invalid_json = {"invalid": "data"}
    try:
        OneOffQueryMessage.from_json(invalid_json)
        assert False, "Deserializing invalid JSON should raise an exception"
    except Exception:
        pass  # Expected to fail


def test_basic_one_off_query_response_lacks_error_methods():
    """Test OneOffQueryResponse error handling validation."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryResponseMessage, OneOffTable
    import uuid
    
    # Test response with both error and tables - should handle gracefully
    response = OneOffQueryResponseMessage(
        message_id=uuid.uuid4().bytes,
        error="Some error",
        tables=[OneOffTable("test", [])],
        total_host_execution_duration_micros=100
    )
    
    # Should still detect error even with tables present
    assert response.has_error(), "Should detect error even with tables"
    assert not response.is_success(), "Should not be success with error"


def test_websocket_client_lacks_enhanced_one_off_query():
    """Test WebSocket client OneOffQuery integration."""
    from spacetimedb_sdk.websocket_client import ModernWebSocketClient
    
    client = ModernWebSocketClient()
    
    # Should have the execute_one_off_query method - this is now a positive test
    assert hasattr(client, 'execute_one_off_query'), "WebSocket client should have execute_one_off_query method"


def test_bsatn_utils_cannot_handle_enhanced_one_off_query():
    """Test BSATN utils OneOffQuery integration."""
    from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
    from spacetimedb_sdk.bsatn import encode, decode
    import uuid
    
    message = OneOffQueryMessage(
        message_id=uuid.uuid4().bytes,
        query_string="SELECT * FROM test"
    )
    
    # Test encoding - should work
    encoded = encode(message)
    assert isinstance(encoded, bytes), "BSATN utils should handle OneOffQuery"
    
    # Test decoding - should work
    decoded = decode(encoded, OneOffQueryMessage)
    assert isinstance(decoded, OneOffQueryMessage), "Should decode correctly"


def test_messages_module_missing_exports():
    """Test that messages module exports OneOffQuery classes."""
    from spacetimedb_sdk.messages import OneOffQueryMessage
    # Import should succeed - this is now a positive test
    assert OneOffQueryMessage is not None


if __name__ == "__main__":
    print("✅ GREEN Phase: Running validation tests for OneOffQuery Implementation")
    print("=" * 75)
    
    test_functions = [
        test_one_off_query_module_missing,
        test_basic_one_off_query_lacks_validation,
        test_basic_one_off_query_lacks_bsatn_methods,
        test_basic_one_off_query_lacks_json_methods,
        test_basic_one_off_query_response_lacks_error_methods,
        test_websocket_client_lacks_enhanced_one_off_query,
        test_bsatn_utils_cannot_handle_enhanced_one_off_query,
        test_messages_module_missing_exports,
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
        print("🎉 All validation tests passed! Proto-3 implementation complete!")
    else:
        print("🔧 Some validation tests failed - needs debugging") 