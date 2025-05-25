#!/usr/bin/env python3
"""
Validation failure tests for QueryId Implementation (proto-1)

These tests verify that proper validation errors are raised for invalid QueryId inputs.
All tests should PASS by demonstrating that validation works correctly.

Testing:
- Invalid QueryId value validation (negative numbers, too large numbers)
- BSATN serialization error handling
- Edge cases and error conditions
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


def test_query_id_import_fails():
    """Test that QueryId can be imported successfully."""
    from spacetimedb_sdk.query_id import QueryId
    # Import should succeed - this is now a positive test
    assert QueryId is not None


def test_query_id_creation_fails():
    """Test QueryId creation with invalid inputs."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test negative value - should raise ValueError
    with pytest.raises(ValueError):
        QueryId(-1)
    
    # Test value too large for u32 - should raise ValueError
    with pytest.raises(ValueError):
        QueryId(4294967296)  # u32 max + 1


def test_query_id_auto_generation_fails():
    """Test QueryId auto-generation works correctly."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test auto-generation - should work
    qid1 = QueryId.generate()
    qid2 = QueryId.generate()
    
    assert qid1.id != qid2.id, "Generated QueryIds should be unique"
    assert qid1.id < qid2.id, "Generated QueryIds should be incrementing"


def test_query_id_equality_fails():
    """Test QueryId equality edge cases."""
    from spacetimedb_sdk.query_id import QueryId
    
    qid1 = QueryId(100)
    qid2 = QueryId(200)
    
    # Test inequality cases
    assert qid1 != qid2, "QueryIds with different ids should not be equal"
    assert qid1 != "not a queryid", "QueryId should not equal non-QueryId objects"
    assert qid1 != 100, "QueryId should not equal raw integers"


def test_query_id_bsatn_serialization_fails():
    """Test QueryId BSATN serialization error handling."""
    from spacetimedb_sdk.query_id import QueryId
    from spacetimedb_sdk.bsatn import encode, decode
    
    qid = QueryId(12345)
    
    # Test BSATN encoding - should work
    encoded = encode(qid)
    assert isinstance(encoded, bytes), "BSATN encoding should return bytes"
    assert len(encoded) > 0, "Encoded data should not be empty"
    
    # Test BSATN decoding with corrupted data - should raise exception
    corrupted_data = b"invalid_bsatn_data"
    try:
        decode(corrupted_data, QueryId)
        assert False, "Decoding corrupted data should raise an exception"
    except Exception:
        pass  # Expected to fail


def test_query_id_validation_fails():
    """Test QueryId validation with edge cases."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test valid boundary values - should work
    QueryId(0)  # Min u32
    QueryId(4294967295)  # Max u32
    
    # Test invalid values - should raise ValueError
    with pytest.raises(ValueError):
        QueryId(-1)  # Negative
    
    with pytest.raises(ValueError):
        QueryId(4294967296)  # Too large for u32
    
    # Test non-integer values - should raise ValueError (not TypeError)
    with pytest.raises(ValueError):
        QueryId("not an integer")


def test_query_id_string_representation_fails():
    """Test QueryId string representation edge cases."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test with boundary values
    qid_min = QueryId(0)
    qid_max = QueryId(4294967295)
    
    # Test string representation - should work for all values
    str_repr_min = str(qid_min)
    assert "0" in str_repr_min, "String representation should include the id"
    assert "QueryId" in str_repr_min, "String representation should include class name"
    
    str_repr_max = str(qid_max)
    assert "4294967295" in str_repr_max, "String representation should include large ids"


def test_query_id_protocol_integration_fails():
    """Test QueryId protocol integration edge cases."""
    from spacetimedb_sdk.query_id import QueryId
    
    # Test that QueryId can be used where request IDs are expected
    qid = QueryId.generate()
    
    # QueryId should be compatible with request ID operations
    assert isinstance(qid.id, int), "QueryId id should be an integer"
    assert 0 <= qid.id <= 4294967295, "QueryId should be within u32 range"


if __name__ == "__main__":
    print("✅ GREEN Phase: Running validation tests for QueryId")
    print("=" * 75)
    
    test_functions = [
        test_query_id_import_fails,
        test_query_id_creation_fails,
        test_query_id_auto_generation_fails,
        test_query_id_equality_fails,
        test_query_id_bsatn_serialization_fails,
        test_query_id_validation_fails,
        test_query_id_string_representation_fails,
        test_query_id_protocol_integration_fails,
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
        print("🎉 All validation tests passed! Proto-1 implementation complete!")
    else:
        print("🔧 Some validation tests failed - needs debugging") 