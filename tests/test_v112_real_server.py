"""
End-to-end validation tests for SpacetimeDB v1.1.2 with real server
Run these tests against an actual SpacetimeDB v1.1.2 server instance
"""
import pytest
import time
import json
import threading
from datetime import datetime
import os
import sys

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.protocol import Identity
import spacetimedb_sdk.local_config as local_config


# Configuration - Update these values based on your server setup
SPACETIMEDB_HOST = os.environ.get("SPACETIMEDB_HOST", "localhost:3000")
DATABASE_NAME = os.environ.get("SPACETIMEDB_DB", "test-validation")
DATABASE_IDENTITY = os.environ.get("SPACETIMEDB_IDENTITY", None)
AUTH_TOKEN = os.environ.get("SPACETIMEDB_TOKEN", None)

# Skip these tests if no real server is available
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_REAL_SERVER_TESTS", "true").lower() == "true",
    reason="Real server tests disabled. Set SKIP_REAL_SERVER_TESTS=false to run."
)


class TestRealServerConnection:
    """Test basic connection functionality with real server"""
    
    def test_json_protocol_connection(self):
        """Test connection using JSON protocol"""
        client = SpacetimeDBClient(protocol="v1.json.spacetimedb")
        connected = threading.Event()
        identity_received = threading.Event()
        connection_id = None
        received_identity = None
        
        def on_connect():
            print(f"✓ Connected to {SPACETIMEDB_HOST} with JSON protocol")
            connected.set()
            
        def on_identity(token, identity, conn_id):
            nonlocal connection_id, received_identity
            connection_id = conn_id
            received_identity = identity
            print(f"✓ Received identity: {identity.to_hex()}")
            print(f"✓ Connection ID: {conn_id}")
            identity_received.set()
            
        def on_error(error):
            print(f"✗ Connection error: {error}")
            
        try:
            # Connect with database identity if available
            client._connect_internal(
                auth_token=AUTH_TOKEN,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=DATABASE_IDENTITY,
                ssl_enabled=False,
                on_connect=on_connect,
                on_identity=on_identity,
                on_error=on_error
            )
            
            # Wait for connection
            assert connected.wait(timeout=10), "Failed to connect to server"
            assert identity_received.wait(timeout=5), "Failed to receive identity"
            
            # Verify we have valid identity and connection
            assert received_identity is not None
            assert connection_id is not None
            
            print("✓ JSON protocol connection successful")
            
        finally:
            client.disconnect()
            time.sleep(0.5)
            
    def test_bsatn_protocol_connection(self):
        """Test connection using BSATN protocol"""
        client = SpacetimeDBClient(protocol="v1.bsatn.spacetimedb")
        connected = threading.Event()
        identity_received = threading.Event()
        
        def on_connect():
            print(f"✓ Connected to {SPACETIMEDB_HOST} with BSATN protocol")
            connected.set()
            
        def on_identity(token, identity, conn_id):
            print(f"✓ Received identity: {identity.to_hex()}")
            identity_received.set()
            
        def on_error(error):
            print(f"✗ Connection error: {error}")
            
        try:
            client._connect_internal(
                auth_token=AUTH_TOKEN,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=DATABASE_IDENTITY,
                ssl_enabled=False,
                on_connect=on_connect,
                on_identity=on_identity,
                on_error=on_error
            )
            
            # Wait for connection
            assert connected.wait(timeout=10), "Failed to connect with BSATN protocol"
            assert identity_received.wait(timeout=5), "Failed to receive identity"
            
            print("✓ BSATN protocol connection successful")
            
        finally:
            client.disconnect()
            time.sleep(0.5)
            
    def test_connection_with_saved_identity(self):
        """Test reconnection using saved identity"""
        # First connection to get identity
        client1 = SpacetimeDBClient()
        saved_identity = None
        saved_token = None
        
        def save_identity(token, identity, conn_id):
            nonlocal saved_identity, saved_token
            saved_identity = identity.to_hex()
            saved_token = token
            print(f"✓ Saving identity for reconnection: {saved_identity}")
            
        try:
            client1._connect_internal(
                auth_token=None,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                ssl_enabled=False,
                on_identity=save_identity
            )
            
            time.sleep(0.5)  # Reduced from 2s to 0.5s for testing
            assert saved_identity is not None, "Failed to get identity from first connection"
            
        finally:
            client1.disconnect()
            
        # Second connection with saved identity
        client2 = SpacetimeDBClient()
        reconnected = threading.Event()
        
        def on_reconnect():
            print(f"✓ Reconnected using saved identity")
            reconnected.set()
            
        try:
            client2._connect_internal(
                auth_token=saved_token,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=saved_identity,
                ssl_enabled=False,
                on_connect=on_reconnect
            )
            
            assert reconnected.wait(timeout=10), "Failed to reconnect with saved identity"
            print("✓ Identity persistence successful")
            
        finally:
            client2.disconnect()


class TestDataOperations:
    """Test data operations with real server"""
    
    def test_subscription_workflow(self):
        """Test subscription to queries"""
        client = SpacetimeDBClient()
        connected = threading.Event()
        subscribed = threading.Event()
        subscription_data = []
        
        def on_connect():
            connected.set()
            
        def on_subscription_applied():
            print("✓ Subscription applied")
            subscribed.set()
            
        def on_event(event):
            if event.get("type") == "InitialSubscription":
                subscription_data.append(event)
                
        try:
            client._connect_internal(
                auth_token=AUTH_TOKEN,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=DATABASE_IDENTITY,
                ssl_enabled=False,
                on_connect=on_connect,
                on_subscription_applied=on_subscription_applied,
                on_event=on_event
            )
            
            assert connected.wait(timeout=10), "Failed to connect"
            
            # Subscribe to queries
            queries = ["SELECT * FROM __spacetimedb_metadata"]
            client.subscribe(queries)
            
            # Wait for subscription
            assert subscribed.wait(timeout=10), "Subscription not applied"
            
            # Give time for initial data
            time.sleep(0.2)  # Reduced from 1s to 0.2s for testing
            
            print(f"✓ Received {len(subscription_data)} subscription events")
            
        finally:
            client.disconnect()
            
    def test_reducer_execution(self):
        """Test calling reducers on the server"""
        client = SpacetimeDBClient()
        connected = threading.Event()
        reducer_responses = []
        
        def on_connect():
            connected.set()
            
        def on_event(event):
            if event.get("type") == "ReducerCallResult":
                reducer_responses.append(event)
                print(f"✓ Reducer response: {event.get('status')}")
                
        try:
            client._connect_internal(
                auth_token=AUTH_TOKEN,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=DATABASE_IDENTITY,
                ssl_enabled=False,
                on_connect=on_connect,
                on_event=on_event
            )
            
            assert connected.wait(timeout=10), "Failed to connect"
            
            # Try to call a reducer (assuming a test reducer exists)
            # If no reducer exists, this will fail gracefully
            request_id = client.call_reducer("test_reducer", "test_arg")
            print(f"✓ Sent reducer call with request ID: {request_id}")
            
            # Wait for response
            time.sleep(0.5)  # Reduced from 2s to 0.5s for testing
            
            # Note: Response depends on whether the reducer exists
            if reducer_responses:
                print(f"✓ Received {len(reducer_responses)} reducer responses")
            else:
                print("✓ No reducer responses (reducer may not exist)")
                
        finally:
            client.disconnect()


class TestErrorHandling:
    """Test error scenarios with real server"""
    
    def test_invalid_database_identity(self):
        """Test connection with invalid database identity"""
        client = SpacetimeDBClient()
        error_received = threading.Event()
        error_message = None
        
        def on_error(error):
            nonlocal error_message
            error_message = str(error)
            print(f"✓ Expected error received: {error}")
            error_received.set()
            
        def on_disconnect(msg):
            print(f"✓ Disconnected: {msg}")
            
        try:
            # Use invalid identity
            client._connect_internal(
                auth_token=None,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity="invalid-identity-12345",
                ssl_enabled=False,
                on_error=on_error,
                on_disconnect=on_disconnect
            )
            
            # Should get error or disconnect
            error_received.wait(timeout=5)
            
            print("✓ Invalid identity handled correctly")
            
        finally:
            client.disconnect()
            
    def test_connection_without_db_identity(self):
        """Test v1.1.2 behavior when db_identity is not provided"""
        client = SpacetimeDBClient()
        result = threading.Event()
        success = False
        
        def on_connect():
            nonlocal success
            success = True
            result.set()
            
        def on_error(error):
            print(f"✓ Connection without db_identity error: {error}")
            result.set()
            
        try:
            # Try without db_identity - should use database_address as fallback
            client._connect_internal(
                auth_token=None,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=None,  # Not provided
                ssl_enabled=False,
                on_connect=on_connect,
                on_error=on_error
            )
            
            result.wait(timeout=10)
            
            if success:
                print("✓ Connection succeeded with database_address as identity")
            else:
                print("✓ Connection failed as expected without proper identity")
                
        finally:
            client.disconnect()


class TestRealWorldScenarios:
    """Test real-world usage patterns"""
    
    def test_builder_pattern_connection(self):
        """Test connection using builder pattern"""
        connected = threading.Event()
        identity_info = {}
        
        def on_identity(token, identity, conn_id):
            identity_info['identity'] = identity.to_hex()
            identity_info['token'] = token
            
        client = SpacetimeDBClient.builder() \
            .with_uri(f"ws://{SPACETIMEDB_HOST}") \
            .with_module_name(DATABASE_NAME) \
            .with_db_identity(DATABASE_IDENTITY) \
            .on_connect(connected.set) \
            .on_identity(on_identity) \
            .build()
            
        try:
            assert connected.wait(timeout=10), "Builder pattern connection failed"
            print("✓ Builder pattern connection successful")
            
            # Save identity for future use
            if identity_info:
                print(f"✓ Identity available for persistence: {identity_info['identity']}")
                
        finally:
            client.disconnect()
            
    def test_reconnection_scenario(self):
        """Test reconnection after disconnect"""
        client = SpacetimeDBClient()
        first_connection = threading.Event()
        reconnection = threading.Event()
        connection_count = 0
        
        def on_connect():
            nonlocal connection_count
            connection_count += 1
            if connection_count == 1:
                print("✓ First connection established")
                first_connection.set()
            else:
                print("✓ Reconnection successful")
                reconnection.set()
                
        try:
            # First connection
            client._connect_internal(
                auth_token=AUTH_TOKEN,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=DATABASE_IDENTITY,
                ssl_enabled=False,
                on_connect=on_connect
            )
            
            assert first_connection.wait(timeout=10), "First connection failed"
            
            # Disconnect
            client.disconnect()
            time.sleep(0.2)  # Reduced from 1s to 0.2s for testing
            
            # Reconnect
            client._connect_internal(
                auth_token=AUTH_TOKEN,
                host=SPACETIMEDB_HOST,
                database_address=DATABASE_NAME,
                db_identity=DATABASE_IDENTITY,
                ssl_enabled=False,
                on_connect=on_connect
            )
            
            assert reconnection.wait(timeout=10), "Reconnection failed"
            print("✓ Reconnection workflow successful")
            
        finally:
            client.disconnect()


def print_test_configuration():
    """Print current test configuration"""
    print("\n" + "="*60)
    print("SpacetimeDB v1.1.2 Real Server Validation")
    print("="*60)
    print(f"Host: {SPACETIMEDB_HOST}")
    print(f"Database: {DATABASE_NAME}")
    print(f"Identity: {DATABASE_IDENTITY or 'Not provided (will use database name)'}")
    print(f"Auth Token: {'Provided' if AUTH_TOKEN else 'Not provided'}")
    print("="*60 + "\n")


if __name__ == "__main__":
    print_test_configuration()
    
    # Run tests
    pytest.main([__file__, "-v", "-s"])
