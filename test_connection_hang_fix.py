#!/usr/bin/env python3
"""
Test script to isolate and fix the hanging test issue.
"""

import os
import sys
import time
import threading
import signal

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up proper signal handling for timeout
def timeout_handler(signum, frame):
    print("⏰ TIMEOUT: Force exiting due to test hang")
    os._exit(1)

# Set up signal alarm (Unix-like systems only)
if hasattr(signal, 'SIGALRM'):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 second timeout

def test_connection_state_tracker():
    """Test ConnectionStateTracker functionality with proper timeout."""
    print("[DEBUG] Starting test_connection_state_tracker")
    
    try:
        from spacetimedb_sdk.connection_id import (
            ConnectionStateTracker,
            EnhancedConnectionId,
            ConnectionState
        )
        
        tracker = ConnectionStateTracker()
        connection_id = EnhancedConnectionId.generate_random()
        
        # Test initial state
        print("[DEBUG] Testing initial state")
        assert tracker.get_connection_state(connection_id) == ConnectionState.DISCONNECTED
        assert tracker.is_connected(connection_id) == False
        
        # Test connection establishment
        print("[DEBUG] Testing connection establishment")
        tracker.track_connection(connection_id, ConnectionState.CONNECTED)
        assert tracker.get_connection_state(connection_id) == ConnectionState.CONNECTED
        assert tracker.is_connected(connection_id) == True
        
        # Test active connections
        print("[DEBUG] Testing active connections")
        active_connections = tracker.get_active_connections()
        assert connection_id in active_connections
        assert len(active_connections) == 1
        
        # Test connection loss
        print("[DEBUG] Testing connection loss")
        tracker.connection_lost(connection_id)
        assert tracker.get_connection_state(connection_id) == ConnectionState.DISCONNECTED
        assert tracker.is_connected(connection_id) == False
        
        # Test connection duration (may be None for disconnected connections)
        print("[DEBUG] Testing connection duration")
        duration = tracker.get_connection_duration(connection_id)
        assert duration is None or isinstance(duration, float)
        
        print("✅ ConnectionStateTracker works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Error in test_connection_state_tracker: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("[DEBUG] Finished test_connection_state_tracker")


def test_connection_pool_fix():
    """Test connection pool with proper test mode."""
    print("[DEBUG] Starting test_connection_pool_fix")
    
    try:
        from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
        
        # Create builder with test mode enabled
        print("[DEBUG] Creating connection builder with test mode")
        builder = (ModernSpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("test_module")
                  .with_test_mode(True)  # Enable test mode
                  .with_connection_pool(min_connections=2, max_connections=5))
        
        print("[DEBUG] Building connection pool")
        # This should not hang with test mode enabled
        pool = builder.build_pool()
        
        print("✅ Connection pool created successfully with test mode")
        return True
        
    except Exception as e:
        print(f"❌ Error in test_connection_pool_fix: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("[DEBUG] Finished test_connection_pool_fix")


if __name__ == "__main__":
    print("Testing hanging issue fixes...")
    print("=" * 60)
    
    # Test 1: ConnectionStateTracker (isolated)
    print("\nTest 1: ConnectionStateTracker")
    success1 = test_connection_state_tracker()
    
    # Test 2: Connection Pool with test mode
    print("\nTest 2: Connection Pool with test mode")
    success2 = test_connection_pool_fix()
    
    # Cancel the alarm if set
    if hasattr(signal, 'SIGALRM'):
        signal.alarm(0)
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
