#!/usr/bin/env python3
"""
Integration test to verify that object serialization fixes work in practice.

This test simulates the real-world scenario where client code receives
SpacetimeDB objects and tries to access them like dictionaries.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol import (
    Identity, ConnectionId, TimeDuration, DatabaseUpdate, EnergyQuanta,
    TableUpdate, ReducerCallInfo, IdentityToken
)
from spacetimedb_sdk.serialization import prepare_message_for_client
from spacetimedb_sdk.protocol_handler import format_for_client


def test_integration_client_compatibility():
    """Test the full integration scenario that was failing in blackholio-python-client."""
    
    print("🧪 Testing SpacetimeDB Object Serialization Integration...")
    
    # Simulate a server message with the problematic objects
    server_message = {
        'database_update': DatabaseUpdate(tables=[
            TableUpdate(
                table_id=1,
                table_name="users",
                num_rows=5,
                inserts=[{"id": 1, "name": "Alice"}],
                deletes=[]
            )
        ]),
        'total_host_execution_duration': TimeDuration(nanos={'__time_duration_micros__': 527}),
        'caller_identity': Identity(data=b"{'__identity__': '0x...'}"),
        'caller_connection_id': ConnectionId(data=b"{'__connection_id__': 246634077236934735698079173074425116788}"),
        'energy_quanta_used': EnergyQuanta(quanta=1134000),
        'reducer_call': ReducerCallInfo(
            reducer_name="update_user",
            reducer_id=42,
            args=b'{"name": "Bob"}',
            request_id=12345
        )
    }
    
    print("✅ Created server message with complex nested objects")
    
    # Process the message for client compatibility (this is what our fix does)
    client_message = prepare_message_for_client(server_message)
    
    print("✅ Processed message for client compatibility")
    
    # Now test the operations that were failing before
    
    # Test 1: DatabaseUpdate.get('tables') - this was causing AttributeError before
    try:
        tables = client_message['database_update'].get('tables')
        assert tables is not None, "tables should not be None"
        assert len(tables) == 1, "should have 1 table"
        assert tables[0]['table_name'] == "users", "table name should be 'users'"
        print("✅ DatabaseUpdate.get('tables') works correctly")
    except AttributeError as e:
        print(f"❌ DatabaseUpdate.get('tables') failed: {e}")
        return False
    
    # Test 2: TimeDuration.get('nanos') - this was causing AttributeError before
    try:
        nanos = client_message['total_host_execution_duration'].get('nanos')
        assert nanos is not None, "nanos should not be None"
        micros = client_message['total_host_execution_duration'].get('__time_duration_micros__')
        assert micros == 527, "micros should be 527"
        print("✅ TimeDuration.get('nanos') and get('__time_duration_micros__') work correctly")
    except AttributeError as e:
        print(f"❌ TimeDuration.get() failed: {e}")
        return False
    
    # Test 3: Identity.get('data') - this was causing AttributeError before
    try:
        identity_data = client_message['caller_identity'].get('data')
        assert identity_data is not None, "identity data should not be None"
        print("✅ Identity.get('data') works correctly")
    except AttributeError as e:
        print(f"❌ Identity.get('data') failed: {e}")
        return False
    
    # Test 4: ConnectionId.get('data') - this was causing AttributeError before
    try:
        conn_data = client_message['caller_connection_id'].get('data')
        assert conn_data is not None, "connection data should not be None"
        print("✅ ConnectionId.get('data') works correctly")
    except AttributeError as e:
        print(f"❌ ConnectionId.get('data') failed: {e}")
        return False
    
    # Test 5: EnergyQuanta.get('quanta') - this was causing AttributeError before
    try:
        quanta = client_message['energy_quanta_used'].get('quanta')
        assert quanta == 1134000, "quanta should be 1134000"
        print("✅ EnergyQuanta.get('quanta') works correctly")
    except AttributeError as e:
        print(f"❌ EnergyQuanta.get('quanta') failed: {e}")
        return False
    
    # Test 6: Test that objects also support 'in' operator and dictionary-like access
    try:
        assert 'tables' in client_message['database_update'], "'tables' should be in database_update"
        assert 'nanos' in client_message['total_host_execution_duration'], "'nanos' should be in time_duration"
        assert 'data' in client_message['caller_identity'], "'data' should be in identity"
        assert 'quanta' in client_message['energy_quanta_used'], "'quanta' should be in energy"
        
        # Test dictionary-style access
        table_name = client_message['database_update']['tables'][0]['table_name']
        assert table_name == "users", "dictionary access should work"
        
        print("✅ Dictionary-like 'in' operator and [] access work correctly")
    except (AttributeError, KeyError) as e:
        print(f"❌ Dictionary-like operations failed: {e}")
        return False
    
    # Test 7: Test that original object functionality is preserved
    try:
        # Objects should still work as objects
        original_identity = server_message['caller_identity']
        hex_str = original_identity.to_hex()
        assert isinstance(hex_str, str), "to_hex() should still work"
        
        # But also work as dictionaries
        data = original_identity.get('data')
        assert data is not None, "get() should also work"
        
        print("✅ Original object methods preserved alongside dictionary compatibility")
    except Exception as e:
        print(f"❌ Original object functionality broken: {e}")
        return False
    
    print("\n🎉 ALL INTEGRATION TESTS PASSED!")
    print("The AttributeError issues have been successfully resolved!")
    return True


def test_format_for_client_function():
    """Test the convenience function for formatting messages."""
    
    print("\n🧪 Testing format_for_client convenience function...")
    
    # Test with individual objects
    identity = Identity(data=b"test_identity")
    formatted = format_for_client(identity)
    
    try:
        data = formatted.get('data')
        assert data == b"test_identity", "formatted identity should support .get()"
        print("✅ format_for_client works with individual objects")
    except AttributeError as e:
        print(f"❌ format_for_client failed: {e}")
        return False
    
    return True


def test_nested_object_scenarios():
    """Test complex nested object scenarios."""
    
    print("\n🧪 Testing nested object scenarios...")
    
    # Create a complex nested structure
    identity = Identity(data=b"user_identity")
    connection_id = ConnectionId(data=b"connection_data")
    identity_token = IdentityToken(
        identity=identity,
        token="auth_token_123",
        connection_id=connection_id
    )
    
    # Format for client
    formatted = format_for_client(identity_token)
    
    try:
        # Test nested access
        nested_identity = formatted.get('identity')
        assert nested_identity is not None, "nested identity should exist"
        
        nested_data = nested_identity.get('data')
        assert nested_data == b"user_identity", "nested data should be accessible"
        
        # Test multiple levels
        token = formatted['token']
        assert token == "auth_token_123", "token should be accessible"
        
        conn_data = formatted['connection_id']['data']
        assert conn_data == b"connection_data", "connection data should be accessible"
        
        print("✅ Nested object serialization works correctly")
    except (AttributeError, KeyError) as e:
        print(f"❌ Nested object test failed: {e}")
        return False
    
    return True


def main():
    """Run all integration tests."""
    print("SpacetimeDB Object Serialization Integration Tests")
    print("=" * 60)
    
    success = True
    
    # Run all tests
    success &= test_integration_client_compatibility()
    success &= test_format_for_client_function()
    success &= test_nested_object_scenarios()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ The SpacetimeDB object serialization fixes are working correctly.")
        print("✅ Client code should no longer experience AttributeError issues.")
        print("✅ Objects now support both object methods and dictionary operations.")
    else:
        print("❌ Some integration tests failed.")
        print("💡 Check the output above for specific failure details.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)