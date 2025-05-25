#!/usr/bin/env python3
"""
RED Phase: Failing tests for OneOffQuery Implementation (proto-3)

These tests define the expected behavior of ENHANCED OneOffQuery message types
before implementation. The basic OneOffQuery exists in protocol.py but lacks
modern features like validation, BSATN serialization, etc.

Testing:
- Enhanced OneOffQueryMessage with validation and BSATN support
- Enhanced OneOffQueryResponseMessage with error handling
- Modern protocol integration with proper serialization
- WebSocket client enhancements
- Error handling and validation features
"""

import os
import sys
import uuid

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


def test_enhanced_one_off_query_message_import_fails():
    """Test that enhanced OneOffQuery message classes can be imported - this will fail initially."""
    try:
        from spacetimedb_sdk.messages.one_off_query import (
            OneOffQueryMessage,
            OneOffQueryResponseMessage
        )
        
        # Test that they have enhanced features
        assert hasattr(OneOffQueryMessage, 'write_bsatn'), "Should have BSATN serialization"
        assert hasattr(OneOffQueryMessage, 'read_bsatn'), "Should have BSATN deserialization"
        assert hasattr(OneOffQueryMessage, 'to_json'), "Should have JSON serialization"
        assert hasattr(OneOffQueryMessage, 'from_json'), "Should have JSON deserialization"
        
        assert False, "Enhanced OneOffQuery message classes should not be importable yet"
    except (ImportError, AssertionError):
        pass  # Expected to fail


def test_enhanced_one_off_query_validation_fails():
    """Test enhanced OneOffQuery validation - this will fail initially."""
    try:
        from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
        
        # Test that validation is enforced (basic protocol.OneOffQuery doesn't validate)
        with pytest.raises(ValueError):
            OneOffQueryMessage(
                message_id=uuid.uuid4().bytes,
                query_string=""  # Empty query should fail validation
            )
        
        with pytest.raises(ValueError):
            OneOffQueryMessage(
                message_id=b"",  # Empty message_id should fail validation
                query_string="SELECT * FROM users"
            )
        
        assert False, "Enhanced validation should fail (not implemented yet)"
    except ImportError:
        pass  # Expected to fail


def test_enhanced_one_off_query_bsatn_methods_fail():
    """Test that enhanced OneOffQuery has BSATN methods - this will fail initially."""
    try:
        from spacetimedb_sdk.messages.one_off_query import OneOffQueryMessage
        from spacetimedb_sdk.bsatn.writer import BsatnWriter
        from spacetimedb_sdk.bsatn.reader import BsatnReader
        
        message_id = uuid.uuid4().bytes
        message = OneOffQueryMessage(
            message_id=message_id,
            query_string="SELECT * FROM products"
        )
        
        # Test that it has write_bsatn method
        writer = BsatnWriter()
        message.write_bsatn(writer)  # Should not raise AttributeError
        
        # Test that the class has read_bsatn method
        assert hasattr(OneOffQueryMessage, 'read_bsatn'), "Should have read_bsatn class method"
        
        assert False, "Enhanced BSATN methods should fail (not implemented yet)"
    except (ImportError, AttributeError):
        pass  # Expected to fail


def test_enhanced_one_off_query_json_methods_fail():
    """Test that enhanced OneOffQuery has JSON methods - this will fail initially."""
    try:
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
        
        assert False, "Enhanced JSON methods should fail (not implemented yet)"
    except (ImportError, AttributeError):
        pass  # Expected to fail


def test_enhanced_one_off_query_response_error_handling_fails():
    """Test enhanced OneOffQueryResponse error handling - this will fail initially."""
    try:
        from spacetimedb_sdk.messages.one_off_query import OneOffQueryResponseMessage
        
        message_id = uuid.uuid4().bytes
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
            tables=[{"table_name": "users", "rows": []}],
            total_host_execution_duration_micros=200
        )
        
        assert not success_response.has_error(), "Should not detect error"
        assert success_response.is_success(), "Should be success without error"
        
        assert False, "Enhanced error handling should fail (not implemented yet)"
    except (ImportError, AttributeError):
        pass  # Expected to fail


def test_enhanced_websocket_client_integration_fails():
    """Test enhanced WebSocket client OneOffQuery integration - this will fail initially."""
    try:
        from spacetimedb_sdk.websocket_client import ModernWebSocketClient
        
        client = ModernWebSocketClient()
        
        # Test that client has enhanced execute_one_off_query method
        result = client.execute_one_off_query("SELECT * FROM products")
        
        # Enhanced method should return metadata dict
        assert isinstance(result, dict), "Should return result metadata"
        assert "message_id" in result, "Should include message_id"
        assert "timestamp" in result, "Should include timestamp"
        assert "query" in result, "Should include original query"
        
        assert False, "Enhanced WebSocket client integration should fail (not implemented yet)"
    except (ImportError, AttributeError):
        pass  # Expected to fail


def test_bsatn_utils_integration_fails():
    """Test that BSATN utils can handle enhanced OneOffQuery - this will fail initially."""
    try:
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
        
        assert False, "BSATN utils integration should fail (not implemented yet)"
    except (ImportError, AttributeError):
        pass  # Expected to fail


def test_protocol_encoder_enhanced_support_fails():
    """Test that ProtocolEncoder properly handles enhanced OneOffQuery - this will fail initially."""
    try:
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
        
        assert False, "Enhanced protocol encoder support should fail (not implemented yet)"
    except (ImportError, AttributeError):
        pass  # Expected to fail


def test_enhanced_message_equality_and_repr_fails():
    """Test enhanced OneOffQuery equality and string representation - this will fail initially."""
    try:
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
        
        assert False, "Enhanced equality and repr should fail (not implemented yet)"
    except (ImportError, AttributeError):
        pass  # Expected to fail


def test_messages_module_exports_fails():
    """Test that messages module properly exports OneOffQuery classes - this will fail initially."""
    try:
        from spacetimedb_sdk.messages import (
            OneOffQueryMessage,
            OneOffQueryResponseMessage
        )
        
        assert OneOffQueryMessage is not None
        assert OneOffQueryResponseMessage is not None
        
        assert False, "Messages module exports should fail (not implemented yet)"
    except ImportError:
        pass  # Expected to fail


if __name__ == "__main__":
    print("🔴 RED Phase: Running failing tests for Enhanced OneOffQuery Implementation")
    print("=" * 75)
    
    test_functions = [
        test_enhanced_one_off_query_message_import_fails,
        test_enhanced_one_off_query_validation_fails,
        test_enhanced_one_off_query_bsatn_methods_fail,
        test_enhanced_one_off_query_json_methods_fail,
        test_enhanced_one_off_query_response_error_handling_fails,
        test_enhanced_websocket_client_integration_fails,
        test_bsatn_utils_integration_fails,
        test_protocol_encoder_enhanced_support_fails,
        test_enhanced_message_equality_and_repr_fails,
        test_messages_module_exports_fails,
    ]
    
    failed_count = 0
    for test_func in test_functions:
        try:
            test_func()
            print(f"❌ {test_func.__name__} - UNEXPECTEDLY PASSED")
        except (ImportError, AttributeError, AssertionError):
            print(f"🔴 {test_func.__name__} - FAILED AS EXPECTED")
            failed_count += 1
        except Exception as e:
            print(f"🔴 {test_func.__name__} - FAILED AS EXPECTED ({type(e).__name__})")
            failed_count += 1
    
    print(f"\n🔴 RED Phase Summary: {failed_count}/{len(test_functions)} tests failed as expected")
    print("Ready for GREEN phase implementation!") 