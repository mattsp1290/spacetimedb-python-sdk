#!/usr/bin/env python3
"""
GREEN Phase: Success tests for QueryId System Implementation (proto-1)

These tests verify that the QueryId implementation works correctly.
They should all PASS now that implementation is complete.
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


def test_query_id_import_success():
    """Test that QueryId can be imported successfully."""
    from spacetimedb_sdk.query_id import QueryId
    assert QueryId is not None
    print("✅ QueryId import successful")


def test_query_id_creation_success():
    """Test QueryId creation works correctly.""" 
    from spacetimedb_sdk.query_id import QueryId
    
    # Test basic creation
    qid = QueryId(42)
    assert qid.id == 42
    print("✅ QueryId creation successful")


def test_query_id_auto_generation_success():
    """Test automatic QueryId generation works correctly."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test auto-generation
    qid1 = QueryId.generate()
    qid2 = QueryId.generate()
    
    assert qid1.id != qid2.id, "Generated QueryIds should be unique"
    assert qid1.id < qid2.id, "Generated QueryIds should be incrementing"
    print("✅ QueryId auto-generation successful")


def test_query_id_equality_success():
    """Test QueryId equality and hashing works correctly."""
    from spacetimedb_sdk.query_id import QueryId
    
    qid1 = QueryId(100)
    qid2 = QueryId(100)
    qid3 = QueryId(200)
    
    # Test equality
    assert qid1 == qid2, "QueryIds with same id should be equal"
    assert qid1 != qid3, "QueryIds with different ids should not be equal"
    
    # Test hashing (for use in dicts/sets)
    assert hash(qid1) == hash(qid2), "Equal QueryIds should have same hash"
    assert hash(qid1) != hash(qid3), "Different QueryIds should have different hashes"
    
    # Test use in sets
    qid_set = {qid1, qid2, qid3}
    assert len(qid_set) == 2, "Set should contain only unique QueryIds"
    
    print("✅ QueryId equality and hashing successful")


def test_query_id_bsatn_serialization_success():
    """Test QueryId BSATN serialization works correctly."""
    from spacetimedb_sdk.query_id import QueryId
    from spacetimedb_sdk.bsatn import encode, decode
    
    qid = QueryId(12345)
    
    # Test BSATN encoding
    encoded = encode(qid)
    assert isinstance(encoded, bytes), "BSATN encoding should return bytes"
    assert len(encoded) > 0, "Encoded data should not be empty"
    
    # Test BSATN decoding with type hint
    decoded = decode(encoded, QueryId)
    assert isinstance(decoded, QueryId), "Decoded value should be QueryId"
    assert decoded == qid, "Round-trip should preserve value"
    
    print("✅ QueryId BSATN serialization successful")


def test_query_id_validation_success():
    """Test QueryId validation works correctly."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test valid values
    QueryId(0)  # Should work
    QueryId(4294967295)  # u32 max - should work
    
    # Test invalid values
    try:
        QueryId(-1)  # Negative should fail
        assert False, "Should have raised ValueError for negative value"
    except ValueError:
        pass  # Expected
        
    try:
        QueryId(4294967296)  # > u32 max should fail
        assert False, "Should have raised ValueError for value > u32 max"
    except ValueError:
        pass  # Expected
    
    print("✅ QueryId validation successful")


def test_query_id_string_representation_success():
    """Test QueryId string representation works correctly."""
    from spacetimedb_sdk.query_id import QueryId
    
    qid = QueryId(42)
    
    # Test string representation
    str_repr = str(qid)
    assert "42" in str_repr, "String representation should include the id"
    assert "QueryId" in str_repr, "String representation should include class name"
    
    # Test repr
    repr_str = repr(qid)
    assert "QueryId" in repr_str, "Repr should include class name"
    assert "42" in repr_str, "Repr should include the id"
    
    print("✅ QueryId string representation successful")


def test_query_id_protocol_integration_success():
    """Test QueryId integration with protocol module works correctly."""
    from spacetimedb_sdk.query_id import QueryId
    from spacetimedb_sdk.protocol import generate_request_id
    
    # Test that QueryId can be used where request IDs are expected
    qid = QueryId.generate()
    request_id = generate_request_id()
    
    # QueryId should be compatible with request ID operations
    assert isinstance(qid.id, int), "QueryId id should be an integer"
    assert isinstance(request_id, int), "Request ID should be an integer"
    
    print("✅ QueryId protocol integration successful")


def test_query_id_advanced_features():
    """Test advanced QueryId features."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test copy constructor
    qid1 = QueryId(500)
    qid2 = QueryId(qid1)
    assert qid1 == qid2, "Copy constructor should work"
    assert qid1 is not qid2, "Copy should create new instance"
    
    # Test threading safety of generation
    import threading
    generated_ids = []
    
    def generate_ids():
        for _ in range(100):
            generated_ids.append(QueryId.generate().id)
    
    threads = [threading.Thread(target=generate_ids) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Check all IDs are unique
    assert len(set(generated_ids)) == len(generated_ids), "All generated IDs should be unique"
    
    print("✅ QueryId advanced features successful")


if __name__ == "__main__":
    print("🟢 GREEN Phase: Running success tests for QueryId System")
    print("=" * 65)
    
    test_functions = [
        test_query_id_import_success,
        test_query_id_creation_success, 
        test_query_id_auto_generation_success,
        test_query_id_equality_success,
        test_query_id_bsatn_serialization_success,
        test_query_id_validation_success,
        test_query_id_string_representation_success,
        test_query_id_protocol_integration_success,
        test_query_id_advanced_features,
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
        print("🎉 All QueryId tests passed! Implementation complete.")
        print("Ready to move to proto-2 (Modern Message Types)!")
    else:
        print("❌ Some tests failed. Need to fix implementation.")
        sys.exit(1) 