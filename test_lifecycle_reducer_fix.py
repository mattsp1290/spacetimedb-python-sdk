#!/usr/bin/env python3
"""
Test for the automatic lifecycle reducer triggering fix.

This test verifies that the Python SDK now automatically triggers the
client_connected lifecycle reducer after connection, matching C# SDK behavior.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
import time
from unittest.mock import Mock, patch
from typing import Optional, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_auto_trigger_lifecycle_enabled():
    """Test that auto_trigger_lifecycle is enabled by default."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    # Create client with default settings
    client = SpacetimeDBClient(test_mode=True)
    
    # Verify auto_trigger_lifecycle is enabled by default
    assert client.auto_trigger_lifecycle == True
    logger.info("✅ auto_trigger_lifecycle is enabled by default")
    
    client.shutdown()

def test_auto_trigger_lifecycle_configurable():
    """Test that auto_trigger_lifecycle can be disabled."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    # Create client with auto_trigger_lifecycle disabled
    client = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=False)
    
    # Verify auto_trigger_lifecycle is disabled
    assert client.auto_trigger_lifecycle == False
    logger.info("✅ auto_trigger_lifecycle can be disabled")
    
    client.shutdown()

def test_lifecycle_trigger_called_on_identity():
    """Test that _trigger_client_connected is called when identity is received."""
    from spacetimedb_sdk import SpacetimeDBClient
    from spacetimedb_sdk.protocol import IdentityToken, Identity, ConnectionId
    
    # Create client with auto_trigger_lifecycle enabled
    client = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=True)
    
    # Mock the _trigger_client_connected method to track calls
    client._trigger_client_connected = Mock()
    
    # Create a test identity token
    identity = Identity.from_hex("a" * 32)  # 16 bytes = 32 hex chars
    connection_id = ConnectionId.from_hex("b" * 16)  # 8 bytes = 16 hex chars
    token_msg = IdentityToken(
        identity=identity,
        connection_id=connection_id,
        token="test_token"
    )
    
    # Simulate receiving identity token
    client._handle_identity_token(token_msg)
    
    # Verify _trigger_client_connected was called
    client._trigger_client_connected.assert_called_once()
    logger.info("✅ _trigger_client_connected called on identity token")
    
    client.shutdown()

def test_lifecycle_trigger_not_called_when_disabled():
    """Test that _trigger_client_connected is NOT called when auto_trigger_lifecycle is disabled."""
    from spacetimedb_sdk import SpacetimeDBClient
    from spacetimedb_sdk.protocol import IdentityToken, Identity, ConnectionId
    
    # Create client with auto_trigger_lifecycle disabled
    client = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=False)
    
    # Mock the _trigger_client_connected method to track calls
    client._trigger_client_connected = Mock()
    
    # Create a test identity token
    identity = Identity.from_hex("a" * 32)
    connection_id = ConnectionId.from_hex("b" * 16)
    token_msg = IdentityToken(
        identity=identity,
        connection_id=connection_id,
        token="test_token"
    )
    
    # Simulate receiving identity token
    client._handle_identity_token(token_msg)
    
    # Verify _trigger_client_connected was NOT called
    client._trigger_client_connected.assert_not_called()
    logger.info("✅ _trigger_client_connected NOT called when disabled")
    
    client.shutdown()

def test_trigger_client_connected_calls_reducer():
    """Test that _trigger_client_connected actually calls the client_connected reducer."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    # Create client in test mode
    client = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=True)
    
    # Mock the call_reducer method to track calls
    client.call_reducer = Mock(return_value=12345)
    
    # Set up the client as "connected"
    client.identity = Mock()
    client.enhanced_connection_id = Mock()
    
    # Call _trigger_client_connected directly
    client._trigger_client_connected()
    
    # Verify call_reducer was called with "client_connected"
    client.call_reducer.assert_called_once_with("client_connected")
    logger.info("✅ _trigger_client_connected calls call_reducer with 'client_connected'")
    
    client.shutdown()

def test_trigger_client_connected_handles_errors_gracefully():
    """Test that _trigger_client_connected handles errors gracefully."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    # Create client in test mode
    client = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=True)
    
    # Mock call_reducer to raise an exception
    client.call_reducer = Mock(side_effect=Exception("Reducer not found"))
    
    # Set up the client as "connected"
    client.identity = Mock()
    client.enhanced_connection_id = Mock()
    
    # Call _trigger_client_connected - should not raise exception
    try:
        client._trigger_client_connected()
        logger.info("✅ _trigger_client_connected handles errors gracefully")
    except Exception as e:
        logger.error(f"❌ _trigger_client_connected should not raise exceptions: {e}")
        raise
    
    # Verify call_reducer was still called
    client.call_reducer.assert_called_once_with("client_connected")
    
    client.shutdown()

def test_trigger_client_connected_skips_when_not_connected():
    """Test that _trigger_client_connected skips when not connected."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    # Create client in test mode but don't set up connection
    client = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=True)
    
    # Mock call_reducer to track calls
    client.call_reducer = Mock()
    
    # Don't set up identity/connection (simulate not connected)
    client.identity = None
    client.enhanced_connection_id = None
    
    # Call _trigger_client_connected
    client._trigger_client_connected()
    
    # Verify call_reducer was NOT called
    client.call_reducer.assert_not_called()
    logger.info("✅ _trigger_client_connected skips when not connected")
    
    client.shutdown()

def test_end_to_end_simulation():
    """Test the complete end-to-end flow in test mode."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    # Track reducer calls
    reducer_calls = []
    
    def mock_call_reducer(reducer_name, *args, **kwargs):
        reducer_calls.append((reducer_name, args, kwargs))
        return 12345
    
    # Create client and connect in test mode
    client = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=True)
    
    # Replace call_reducer with our mock
    client.call_reducer = mock_call_reducer
    
    # Simulate connection using the connect class method
    # This should trigger the complete flow including lifecycle reducer
    try:
        # Use the class method that handles the full connection flow
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test_database",
            ssl_enabled=False
        )
        
        # Wait a moment for any async processing
        time.sleep(0.1)
        
        # Verify that client_connected was called
        reducer_names = [call[0] for call in reducer_calls]
        assert "client_connected" in reducer_names, f"client_connected not called. Calls: {reducer_calls}"
        
        logger.info("✅ End-to-end simulation: client_connected automatically triggered")
        
    finally:
        client.shutdown()

def test_backward_compatibility():
    """Test that existing code still works without changes."""
    from spacetimedb_sdk import SpacetimeDBClient  # Backward compatibility alias
    
    # This should work exactly as before
    client = SpacetimeDBClient(test_mode=True)
    
    # Should have auto_trigger_lifecycle enabled by default
    assert client.auto_trigger_lifecycle == True
    
    # Should be able to disable it
    client2 = SpacetimeDBClient(test_mode=True, auto_trigger_lifecycle=False)
    assert client2.auto_trigger_lifecycle == False
    
    logger.info("✅ Backward compatibility maintained")
    
    client.shutdown()
    client2.shutdown()

def test_connect_method_passes_auto_trigger_lifecycle():
    """Test that the connect class method passes through auto_trigger_lifecycle parameter."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    # Test with auto_trigger_lifecycle=False
    with patch.object(SpacetimeDBClient, '_connect_internal') as mock_connect:
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test",
            auto_trigger_lifecycle=False,
            test_mode=True
        )
        
        # Should have auto_trigger_lifecycle=False
        assert client.auto_trigger_lifecycle == False
        logger.info("✅ connect() method passes auto_trigger_lifecycle parameter")
        
        client.shutdown()

def run_all_tests():
    """Run all tests."""
    logger.info("🚀 Starting lifecycle reducer fix tests...")
    
    tests = [
        test_auto_trigger_lifecycle_enabled,
        test_auto_trigger_lifecycle_configurable,
        test_lifecycle_trigger_called_on_identity,
        test_lifecycle_trigger_not_called_when_disabled,
        test_trigger_client_connected_calls_reducer,
        test_trigger_client_connected_handles_errors_gracefully,
        test_trigger_client_connected_skips_when_not_connected,
        test_end_to_end_simulation,
        test_backward_compatibility,
        test_connect_method_passes_auto_trigger_lifecycle,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            logger.info(f"\n🧪 Running {test.__name__}...")
            test()
            passed += 1
            logger.info(f"✅ {test.__name__} PASSED")
        except Exception as e:
            failed += 1
            logger.error(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("🎉 All tests passed! Lifecycle reducer fix is working correctly.")
        return True
    else:
        logger.error("💥 Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
