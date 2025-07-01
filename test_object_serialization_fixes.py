#!/usr/bin/env python3
"""
Comprehensive tests for SpacetimeDB object serialization fixes.

This test suite validates that all SpacetimeDB objects now support
dictionary-like operations and client compatibility, addressing
the AttributeError issues described in the requirements.
"""

import sys
import os
import pytest
import json
from typing import Any, Dict

# Add the src directory to the path so we can import SpacetimeDB modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import the modules we're testing
from spacetimedb_sdk.base_objects import DictLikeMixin, SpacetimeDBObject
from spacetimedb_sdk.protocol import (
    Identity, ConnectionId, QueryId, Timestamp, TimeDuration, 
    EnergyQuanta, DatabaseUpdate, ReducerCallInfo, IdentityToken, TableUpdate
)
from spacetimedb_sdk.serialization import (
    serialize_for_client, prepare_message_for_client, 
    ensure_dict_compatible, ClientCompatibilityWrapper
)
from spacetimedb_sdk.protocol_handler import (
    ProtocolHandler, ProtocolHandlerFactory, format_for_client
)


class TestDictLikeMixin:
    """Test the DictLikeMixin functionality."""
    
    def test_dict_like_mixin_basic_operations(self):
        """Test basic dictionary-like operations on DictLikeMixin."""
        
        class TestObject(DictLikeMixin):
            def __init__(self):
                self.name = "test"
                self.value = 42
                self.active = True
        
        obj = TestObject()
        
        # Test .get() method
        assert obj.get('name') == "test"
        assert obj.get('value') == 42
        assert obj.get('active') == True
        assert obj.get('nonexistent') is None
        assert obj.get('nonexistent', 'default') == 'default'
        
        # Test __getitem__ access
        assert obj['name'] == "test"
        assert obj['value'] == 42
        assert obj['active'] == True
        
        # Test __contains__ operator
        assert 'name' in obj
        assert 'value' in obj
        assert 'active' in obj
        assert 'nonexistent' not in obj
        
        # Test keys(), values(), items()
        keys = obj.keys()
        assert 'name' in keys
        assert 'value' in keys
        assert 'active' in keys
        
        values = obj.values()
        assert "test" in values
        assert 42 in values
        assert True in values
        
        items = obj.items()
        items_dict = dict(items)
        assert items_dict['name'] == "test"
        assert items_dict['value'] == 42
        assert items_dict['active'] == True
    
    def test_dict_like_mixin_error_handling(self):
        """Test error handling for dictionary-like operations."""
        
        class TestObject(DictLikeMixin):
            def __init__(self):
                self.name = "test"
        
        obj = TestObject()
        
        # Test KeyError for non-existent keys
        with pytest.raises(KeyError):
            _ = obj['nonexistent']
    
    def test_dict_like_mixin_to_dict(self):
        """Test conversion to dictionary."""
        
        class TestObject(DictLikeMixin):
            def __init__(self):
                self.name = "test"
                self.value = 42
        
        obj = TestObject()
        result_dict = obj.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict['name'] == "test"
        assert result_dict['value'] == 42


class TestProtocolObjectsCompatibility:
    """Test that all protocol objects now support dictionary operations."""
    
    def test_identity_dict_operations(self):
        """Test Identity object dictionary operations."""
        identity = Identity(data=b"test_identity_data")
        
        # Test .get() method
        assert identity.get('data') == b"test_identity_data"
        assert identity.get('nonexistent') is None
        
        # Test __getitem__ access
        assert identity['data'] == b"test_identity_data"
        
        # Test __contains__ operator
        assert 'data' in identity
        assert 'nonexistent' not in identity
        
        # Test keys(), values(), items()
        assert 'data' in identity.keys()
        assert b"test_identity_data" in identity.values()
    
    def test_connection_id_dict_operations(self):
        """Test ConnectionId object dictionary operations."""
        conn_id = ConnectionId(data=b"test_connection_data")
        
        # Test .get() method
        assert conn_id.get('data') == b"test_connection_data"
        assert conn_id.get('nonexistent') is None
        
        # Test __getitem__ access
        assert conn_id['data'] == b"test_connection_data"
        
        # Test __contains__ operator
        assert 'data' in conn_id
        assert 'nonexistent' not in conn_id
    
    def test_query_id_dict_operations(self):
        """Test QueryId object dictionary operations."""
        query_id = QueryId(id=12345)
        
        # Test .get() method
        assert query_id.get('id') == 12345
        assert query_id.get('nonexistent') is None
        
        # Test __getitem__ access
        assert query_id['id'] == 12345
        
        # Test __contains__ operator
        assert 'id' in query_id
    
    def test_timestamp_dict_operations(self):
        """Test Timestamp object dictionary operations."""
        timestamp = Timestamp(nanos_since_epoch=1234567890)
        
        # Test .get() method
        assert timestamp.get('nanos_since_epoch') == 1234567890
        assert timestamp.get('nonexistent') is None
        
        # Test __getitem__ access
        assert timestamp['nanos_since_epoch'] == 1234567890
        
        # Test __contains__ operator
        assert 'nanos_since_epoch' in timestamp
    
    def test_time_duration_dict_operations(self):
        """Test TimeDuration object dictionary operations."""
        duration = TimeDuration(nanos=5000000)
        
        # Test .get() method
        assert duration.get('nanos') == 5000000
        assert duration.get('nonexistent') is None
        
        # Test __getitem__ access
        assert duration['nanos'] == 5000000
        
        # Test __contains__ operator
        assert 'nanos' in duration
    
    def test_energy_quanta_dict_operations(self):
        """Test EnergyQuanta object dictionary operations."""
        energy = EnergyQuanta(quanta=1000)
        
        # Test .get() method
        assert energy.get('quanta') == 1000
        assert energy.get('nonexistent') is None
        
        # Test __getitem__ access
        assert energy['quanta'] == 1000
        
        # Test __contains__ operator
        assert 'quanta' in energy
    
    def test_database_update_dict_operations(self):
        """Test DatabaseUpdate object dictionary operations."""
        table_update = TableUpdate(
            table_id=1,
            table_name="test_table",
            num_rows=5,
            inserts=[],
            deletes=[]
        )
        db_update = DatabaseUpdate(tables=[table_update])
        
        # Test .get() method
        tables = db_update.get('tables')
        assert isinstance(tables, list)
        assert len(tables) == 1
        assert tables[0].table_name == "test_table"
        
        # Test __getitem__ access
        assert db_update['tables'][0].table_name == "test_table"
        
        # Test __contains__ operator
        assert 'tables' in db_update
    
    def test_reducer_call_info_dict_operations(self):
        """Test ReducerCallInfo object dictionary operations."""
        reducer_info = ReducerCallInfo(
            reducer_name="test_reducer",
            reducer_id=42,
            args=b"test_args",
            request_id=12345
        )
        
        # Test .get() method
        assert reducer_info.get('reducer_name') == "test_reducer"
        assert reducer_info.get('reducer_id') == 42
        assert reducer_info.get('args') == b"test_args"
        assert reducer_info.get('request_id') == 12345
        
        # Test __getitem__ access
        assert reducer_info['reducer_name'] == "test_reducer"
        assert reducer_info['reducer_id'] == 42
        
        # Test __contains__ operator
        assert 'reducer_name' in reducer_info
        assert 'reducer_id' in reducer_info
        assert 'args' in reducer_info
        assert 'request_id' in reducer_info


class TestSerialization:
    """Test serialization functions for client compatibility."""
    
    def test_serialize_database_update(self):
        """Test DatabaseUpdate serialization."""
        table_update = TableUpdate(
            table_id=1,
            table_name="test_table",
            num_rows=2,
            inserts=[{"id": 1, "name": "test"}],
            deletes=[]
        )
        db_update = DatabaseUpdate(tables=[table_update])
        
        result = serialize_for_client(db_update)
        
        assert isinstance(result, dict)
        assert 'tables' in result
        assert isinstance(result['tables'], list)
        assert len(result['tables']) == 1
        
        serialized_table = result['tables'][0]
        assert serialized_table['table_name'] == "test_table"
        assert serialized_table['table_id'] == 1
        assert serialized_table['num_rows'] == 2
    
    def test_serialize_time_duration(self):
        """Test TimeDuration serialization."""
        # Test simple nanos format
        duration = TimeDuration(nanos=5000000)
        result = serialize_for_client(duration)
        
        assert isinstance(result, dict)
        assert 'nanos' in result
        assert result['nanos'] == 5000000
        
        # Test complex nanos format (dict)
        duration_complex = TimeDuration(nanos={'__time_duration_micros__': 5000})
        result_complex = serialize_for_client(duration_complex)
        
        assert isinstance(result_complex, dict)
        assert 'nanos' in result_complex
        assert '__time_duration_micros__' in result_complex
        assert result_complex['__time_duration_micros__'] == 5000
    
    def test_serialize_identity(self):
        """Test Identity serialization."""
        identity = Identity(data=b"test_identity")
        result = serialize_for_client(identity)
        
        assert isinstance(result, dict)
        assert 'data' in result
        assert result['data'] == b"test_identity"
    
    def test_serialize_connection_id(self):
        """Test ConnectionId serialization."""
        conn_id = ConnectionId(data=b"test_connection")
        result = serialize_for_client(conn_id)
        
        assert isinstance(result, dict)
        assert 'data' in result
        assert result['data'] == b"test_connection"
    
    def test_serialize_energy_quanta(self):
        """Test EnergyQuanta serialization."""
        energy = EnergyQuanta(quanta=1500)
        result = serialize_for_client(energy)
        
        assert isinstance(result, dict)
        assert 'quanta' in result
        assert result['quanta'] == 1500
    
    def test_serialize_nested_objects(self):
        """Test serialization of nested objects."""
        identity = Identity(data=b"test_identity")
        conn_id = ConnectionId(data=b"test_connection") 
        identity_token = IdentityToken(
            identity=identity,
            token="test_token",
            connection_id=conn_id
        )
        
        result = serialize_for_client(identity_token)
        
        assert isinstance(result, dict)
        assert 'identity' in result
        assert 'token' in result
        assert 'connection_id' in result
        
        # Check nested serialization
        assert isinstance(result['identity'], dict)
        assert result['identity']['data'] == b"test_identity"
        
        assert isinstance(result['connection_id'], dict)
        assert result['connection_id']['data'] == b"test_connection"
        
        assert result['token'] == "test_token"
    
    def test_prepare_message_for_client(self):
        """Test preparing complete messages for client consumption."""
        # Create a complex message similar to what might come from SpacetimeDB
        message_data = {
            'database_update': DatabaseUpdate(tables=[]),
            'total_host_execution_duration': TimeDuration(nanos=1500000),
            'identity': Identity(data=b"test_identity"),
            'energy_used': EnergyQuanta(quanta=750)
        }
        
        result = prepare_message_for_client(message_data)
        
        assert isinstance(result, dict)
        
        # Check that all objects are now dict-compatible
        assert isinstance(result['database_update'], dict)
        assert 'tables' in result['database_update']
        
        assert isinstance(result['total_host_execution_duration'], dict)
        assert 'nanos' in result['total_host_execution_duration']
        
        assert isinstance(result['identity'], dict)
        assert 'data' in result['identity']
        
        assert isinstance(result['energy_used'], dict)
        assert 'quanta' in result['energy_used']
    
    def test_ensure_dict_compatible(self):
        """Test ensure_dict_compatible function."""
        # Test with already compatible dict
        original_dict = {'key': 'value'}
        result = ensure_dict_compatible(original_dict)
        assert result is original_dict
        
        # Test with object that has dictionary-like methods (should return as-is)
        identity = Identity(data=b"test")
        result = ensure_dict_compatible(identity)
        # Should return the object itself since it now has dict-like methods
        assert result is identity
        assert result.get('data') == b"test"  # Should support dict operations
        
        # Test with object that doesn't have dict methods (create a simple class)
        class SimpleObject:
            def __init__(self):
                self.value = 42
        
        simple_obj = SimpleObject()
        result = ensure_dict_compatible(simple_obj)
        assert isinstance(result, dict)  # Should be converted to dict
    
    def test_client_compatibility_wrapper(self):
        """Test ClientCompatibilityWrapper class."""
        identity = Identity(data=b"test_data")
        wrapper = ClientCompatibilityWrapper(identity)
        
        # Test .get() method
        assert wrapper.get('data') == b"test_data"
        assert wrapper.get('nonexistent') is None
        assert wrapper.get('nonexistent', 'default') == 'default'
        
        # Test __getitem__ access
        assert wrapper['data'] == b"test_data"
        
        # Test __contains__ operator
        assert 'data' in wrapper
        assert 'nonexistent' not in wrapper
        
        # Test keys(), values(), items()
        assert 'data' in wrapper.keys()
        assert b"test_data" in wrapper.values()
        
        # Test to_dict()
        result_dict = wrapper.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict['data'] == b"test_data"


class TestProtocolHandler:
    """Test ProtocolHandler functionality."""
    
    def test_protocol_handler_message_formatting(self):
        """Test ProtocolHandler message formatting."""
        handler = ProtocolHandlerFactory.create_v1_1_2_handler(compatibility_mode=True)
        
        # Test with DatabaseUpdate
        db_update = DatabaseUpdate(tables=[])
        formatted = handler.format_message(db_update)
        
        assert isinstance(formatted, dict)
        assert 'tables' in formatted
    
    def test_protocol_handler_server_message_preparation(self):
        """Test server message preparation."""
        handler = ProtocolHandlerFactory.create_v1_1_2_handler(compatibility_mode=True)
        
        message_data = {
            'database_update': DatabaseUpdate(tables=[]),
            'total_host_execution_duration': TimeDuration(nanos=1000000)
        }
        
        result = handler.prepare_server_message(message_data)
        
        assert isinstance(result, dict)
        assert isinstance(result['database_update'], dict)
        assert isinstance(result['total_host_execution_duration'], dict)
    
    def test_format_for_client_convenience_function(self):
        """Test format_for_client convenience function."""
        identity = Identity(data=b"test")
        result = format_for_client(identity)
        
        assert isinstance(result, dict)
        assert 'data' in result
        assert result['data'] == b"test"


class TestBackwardCompatibility:
    """Test that the fixes don't break existing functionality."""
    
    def test_objects_still_work_as_objects(self):
        """Test that objects still work as regular objects."""
        identity = Identity(data=b"test")
        
        # Should still work as regular object
        assert identity.data == b"test"
        assert hasattr(identity, 'to_hex')
        
        # Should also work as dict
        assert identity.get('data') == b"test"
        assert identity['data'] == b"test"
    
    def test_existing_methods_preserved(self):
        """Test that existing methods are preserved."""
        identity = Identity(data=b"test")
        
        # Test existing methods still work
        hex_str = identity.to_hex()
        assert isinstance(hex_str, str)
        
        # Test enhanced functionality
        enhanced = identity.to_enhanced()
        assert enhanced is not None
    
    def test_dataclass_functionality_preserved(self):
        """Test that dataclass functionality is preserved."""
        identity1 = Identity(data=b"test")
        identity2 = Identity(data=b"test")
        identity3 = Identity(data=b"different")
        
        # Test equality (dataclass feature)
        assert identity1 == identity2
        assert identity1 != identity3
        
        # Test string representation (Identity.__str__ returns hex string)
        str_repr = str(identity1)
        assert str_repr == "74657374"  # hex representation of b"test"
        
        # Test repr representation (should show class name)
        repr_str = repr(identity1)
        assert "Identity" in repr_str


class TestRealWorldScenarios:
    """Test real-world scenarios that were causing AttributeError."""
    
    def test_blackholio_client_scenario(self):
        """Test the specific scenario mentioned in blackholio-python-client."""
        # Simulate the scenario where client code expects dictionary operations
        message_data = {
            'database_update': DatabaseUpdate(tables=[]),
            'total_host_execution_duration': TimeDuration(nanos={'__time_duration_micros__': 527}),
            'identity': Identity(data=b"{'__identity__': '0x...'}"),
            'connection_id': ConnectionId(data=b"{'__connection_id__': 246634077236934735698079173074425116788}"),
            'energy_quanta': EnergyQuanta(quanta=1134000)
        }
        
        # This should not raise AttributeError anymore
        prepared = prepare_message_for_client(message_data)
        
        # Test the operations that were failing before
        db_update = prepared['database_update']
        assert db_update.get('tables') is not None  # This was failing before
        
        duration = prepared['total_host_execution_duration']
        assert duration.get('nanos') is not None  # This was failing before
        assert duration.get('__time_duration_micros__') == 527
        
        identity = prepared['identity']
        assert identity.get('data') is not None  # This was failing before
        
        connection_id = prepared['connection_id']
        assert connection_id.get('data') is not None  # This was failing before
        
        energy = prepared['energy_quanta']
        assert energy.get('quanta') == 1134000  # This was failing before
    
    def test_json_serialization_works(self):
        """Test that serialized objects can be JSON encoded."""
        identity = Identity(data=b"test")
        serialized = serialize_for_client(identity)
        
        # Should be JSON serializable (with bytes handling)
        json_str = json.dumps(serialized, default=lambda x: list(x) if isinstance(x, bytes) else str(x))
        assert isinstance(json_str, str)
        
        # Should be parseable back
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert 'data' in parsed


def run_tests():
    """Run all tests and report results."""
    print("Running SpacetimeDB Object Serialization Tests...")
    print("=" * 60)
    
    # Run pytest with verbose output
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"
    ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    print("=" * 60)
    if result.returncode == 0:
        print("✅ All tests passed! Object serialization fixes are working correctly.")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    
    return result.returncode == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)