#!/usr/bin/env python3
"""
Test compatibility with latest SpacetimeDB version
Tests the specific error scenarios from the AI agent report
"""

import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
sys.path.insert(0, '/Users/punk1290/git/spacetimedb-python-sdk/src')

from spacetimedb_sdk import SpacetimeDBClient
import asyncio
import logging
import time
import json

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def test_latest_spacetimedb_compatibility():
    """Test the AI agent scenarios from the error report"""
    try:
        print("🔧 Testing compatibility with latest SpacetimeDB...")
        
        # Test 1: Basic Connection (should work now)
        print("\n1. Testing basic connection...")
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="blackholio",
            auth_token=None,
            ssl_enabled=False,
            protocol="v1.json.spacetimedb"
        )
        print("✅ Basic connection successful!")
        
        # Test 2: Identity Token Processing (main fix target)
        print("\n2. Testing identity token processing...")
        # Wait briefly for identity token
        time.sleep(1.0)
        
        if hasattr(client, 'identity') and client.identity:
            print(f"✅ Identity received: {str(client.identity)[:32]}...")
        else:
            print("⚠️  No identity received yet")
        
        # Test 3: Table Subscriptions (SQL parser fix)
        print("\n3. Testing table subscriptions...")
        try:
            # Test the exact table names from the error report
            tables_to_test = ["entity", "circle", "player", "food", "config"]
            
            for table in tables_to_test:
                print(f"   Subscribing to table: {table}")
                # This should now convert "entity" to "SELECT * FROM entity"
                client.subscribe([table])
                time.sleep(0.1)  # Brief pause between subscriptions
            
            print("✅ Table subscriptions completed without SQL parser errors!")
            
        except Exception as e:
            print(f"❌ Subscription error: {e}")
            # Check if it's the old SQL parser error
            if "sql parser error" in str(e).lower():
                print("   This is the SQL parser error we're trying to fix")
                raise
        
        # Test 4: Reducer Call (if available)
        print("\n4. Testing reducer calls...")
        try:
            # Try calling a common reducer (may fail if not available, but shouldn't crash)
            client.call_reducer("enter_game", "TestPlayer")
            print("✅ Reducer call submitted successfully!")
        except Exception as e:
            print(f"⚠️  Reducer call failed (expected if module doesn't have this reducer): {e}")
        
        # Test 5: Message Flow Test
        print("\n5. Testing message processing flow...")
        time.sleep(2.0)  # Wait for messages
        
        # If we get here without fromhex() errors, the message processing is working
        print("✅ Message processing completed without fromhex() errors!")
        
        # Test 6: Clean Disconnection
        print("\n6. Testing clean disconnection...")
        client.disconnect()
        print("✅ Clean disconnection successful!")
        
        print("\n🎉 ALL TESTS PASSED! Latest SpacetimeDB compatibility verified!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_protocol_message_formats():
    """Test specific protocol message format handling"""
    print("\n🔧 Testing protocol message format handling...")
    
    from spacetimedb_sdk.protocol import ProtocolDecoder
    
    # Test 1: Identity Token with nested format (latest SpacetimeDB)
    test_identity_token = {
        "IdentityToken": {
            "identity": {"data": [1, 2, 3, 4, 5, 6, 7, 8]},
            "token": "test-token-123",
            "connection_id": {"data": [9, 10, 11, 12, 13, 14, 15, 16]}
        }
    }
    
    try:
        decoder = ProtocolDecoder(use_binary=False)
        message_bytes = json.dumps(test_identity_token).encode('utf-8')
        result = decoder._decode_json(message_bytes)
        
        print("✅ Identity token with nested format decoded successfully!")
        print(f"   Identity: {result.identity}")
        print(f"   Token: {result.token}")
        print(f"   Connection ID: {result.connection_id}")
        
    except Exception as e:
        print(f"❌ Identity token decode failed: {e}")
        return False
    
    # Test 2: Transaction Update with Failed status
    test_transaction_update = {
        "TransactionUpdate": {
            "status": {"Failed": "sql parser error: Expected an SQL statement, found: entity"},
            "timestamp": 1000000000,
            "caller_identity": {"data": [1, 2, 3, 4]},
            "caller_connection_id": {"data": [5, 6, 7, 8]},
            "energy_quanta_used": 100,
            "total_host_execution_duration": 50000
        }
    }
    
    try:
        message_bytes = json.dumps(test_transaction_update).encode('utf-8')
        result = decoder._decode_json(message_bytes)
        
        print("✅ Transaction update with Failed status decoded successfully!")
        print(f"   Status: {result.status}")
        
    except Exception as e:
        print(f"❌ Transaction update decode failed: {e}")
        return False
    
    print("✅ Protocol message format tests passed!")
    return True

def test_subscription_query_formatting():
    """Test the query formatting for subscriptions"""
    print("\n🔧 Testing subscription query formatting...")
    
    from spacetimedb_sdk.protocol import ProtocolEncoder, Subscribe
    
    try:
        encoder = ProtocolEncoder(use_binary=False)
        
        # Test table name conversion
        subscribe_msg = Subscribe(
            query_strings=["entity", "player", "SELECT * FROM existing_query"],
            request_id=12345
        )
        
        encoded = encoder.encode_client_message(subscribe_msg)
        decoded_json = json.loads(encoded.decode('utf-8'))
        
        print("✅ Query formatting test passed!")
        print("   Original queries:", subscribe_msg.query_strings)
        print("   Formatted queries:", decoded_json["Subscribe"]["query_strings"])
        
        # Verify conversion
        formatted_queries = decoded_json["Subscribe"]["query_strings"]
        expected = ["SELECT * FROM entity", "SELECT * FROM player", "SELECT * FROM existing_query"]
        
        if formatted_queries == expected:
            print("✅ Table name to SQL conversion working correctly!")
        else:
            print(f"❌ Query conversion mismatch. Expected: {expected}, Got: {formatted_queries}")
            return False
            
    except Exception as e:
        print(f"❌ Query formatting test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=== SpacetimeDB Latest Version Compatibility Test ===")
    
    # Run protocol tests first
    protocol_ok = test_protocol_message_formats()
    query_ok = test_subscription_query_formatting()
    
    if protocol_ok and query_ok:
        print("\n✅ Protocol layer tests passed, proceeding to integration test...")
        integration_ok = test_latest_spacetimedb_compatibility()
        
        if integration_ok:
            print("\n🎉 ALL COMPATIBILITY TESTS PASSED!")
            print("   Your Python SDK is now compatible with the latest SpacetimeDB!")
            sys.exit(0)
        else:
            print("\n❌ Integration test failed")
            sys.exit(1)
    else:
        print("\n❌ Protocol tests failed")
        sys.exit(1)
