#!/usr/bin/env python3

"""Quick performance test to isolate connection setup bottlenecks."""

import time
import sys
from pathlib import Path

# Add SDK to path  
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_import_time():
    """Test import time."""
    start = time.perf_counter()
    from spacetimedb_sdk import SpacetimeDBClient
    import_time = time.perf_counter() - start
    print(f"Import time: {import_time*1000:.2f}ms")
    return SpacetimeDBClient

def test_client_creation():
    """Test client creation time."""
    from spacetimedb_sdk import SpacetimeDBClient
    
    times = []
    for i in range(10):
        start = time.perf_counter()
        client = SpacetimeDBClient(
            start_message_processing=False,
            test_mode=True
        )
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        client.shutdown()
    
    avg_time = sum(times) / len(times)
    print(f"Client creation average: {avg_time*1000:.2f}ms")
    print(f"Client creation times: {[f'{t*1000:.2f}ms' for t in times]}")

def test_connection_setup():
    """Test connection setup time."""
    from spacetimedb_sdk import SpacetimeDBClient
    from unittest.mock import patch
    
    times = []
    for i in range(10):
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'):
            client = SpacetimeDBClient(
                start_message_processing=False,
                test_mode=True  
            )
            
            start = time.perf_counter()
            client.connect_instance(
                host="localhost:3000",
                database_address="test_db",
                auth_token=None,
                ssl_enabled=False
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            client.shutdown()
    
    avg_time = sum(times) / len(times)
    print(f"Connection setup average: {avg_time*1000:.2f}ms")
    print(f"Connection setup times: {[f'{t*1000:.2f}ms' for t in times]}")

if __name__ == "__main__":
    print("=== Performance Breakdown Analysis ===")
    
    print("\n1. Testing import time...")
    SpacetimeDBClient = test_import_time()
    
    print("\n2. Testing client creation...")
    test_client_creation()
    
    print("\n3. Testing connection setup...")
    test_connection_setup()