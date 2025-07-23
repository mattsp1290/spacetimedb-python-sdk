#!/usr/bin/env python3
"""
Debug script to test threading issues in concurrent connections
"""

import threading
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient

def test_single_connection():
    """Test a single connection to verify basic functionality."""
    print("Testing single connection...")
    
    client = SpacetimeDBClient()
    
    try:
        client._connect_internal(
            auth_token=None,
            host="localhost:3023", 
            database_address="test_db",
            ssl_enabled=False
        )
        print("✓ Single connection successful")
        time.sleep(0.5)  # Give it time to establish
        client.disconnect()
        print("✓ Single disconnection successful")
    except Exception as e:
        print(f"✗ Single connection failed: {e}")

def test_concurrent_connections():
    """Test multiple concurrent connections with proper timeouts."""
    print("\nTesting concurrent connections...")
    
    connection_count = 5  # Start small
    clients = []
    errors = []
    threads = []
    lock = threading.Lock()
    
    def connect_client():
        client = SpacetimeDBClient()
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3023",
                database_address="test_db", 
                ssl_enabled=False
            )
            
            with lock:
                clients.append(client)
                print(f"✓ Client {len(clients)} connected")
                
        except Exception as e:
            with lock:
                errors.append(e)
                print(f"✗ Connection failed: {e}")
    
    # Start all connection threads
    start_time = time.perf_counter()
    
    for i in range(connection_count):
        thread = threading.Thread(target=connect_client, name=f"ConnectThread-{i}")
        threads.append(thread)
        thread.start()
    
    # Wait for all connections with timeout  
    print("Waiting for connection threads to complete...")
    
    for i, thread in enumerate(threads):
        print(f"Joining thread {i} ({thread.name})...")
        thread.join(timeout=10.0)  # 10 second timeout per thread
        
        if thread.is_alive():
            print(f"⚠ Thread {i} ({thread.name}) did not complete within timeout")
        else:
            print(f"✓ Thread {i} ({thread.name}) completed")
    
    total_time = time.perf_counter() - start_time
    print(f"\nConnection phase completed in {total_time:.2f}s")
    print(f"Successful connections: {len(clients)}")
    print(f"Connection errors: {len(errors)}")
    
    # Disconnect all clients with timeouts
    print("\nDisconnecting clients...")
    disconnect_threads = []
    
    def disconnect_client(client, index):
        try:
            print(f"Disconnecting client {index}...")
            client.disconnect()
            print(f"✓ Client {index} disconnected")
        except Exception as e:
            print(f"✗ Client {index} disconnect error: {e}")
    
    for i, client in enumerate(clients):
        thread = threading.Thread(target=disconnect_client, args=(client, i), 
                                name=f"DisconnectThread-{i}")
        disconnect_threads.append(thread)
        thread.start()
    
    # Wait for all disconnections with timeout
    for i, thread in enumerate(disconnect_threads):
        print(f"Joining disconnect thread {i}...")
        thread.join(timeout=10.0)  # 10 second timeout per disconnect
        
        if thread.is_alive():
            print(f"⚠ Disconnect thread {i} did not complete within timeout")
        else:
            print(f"✓ Disconnect thread {i} completed")
    
    print("\nTest completed!")

if __name__ == "__main__":
    print("SpacetimeDB Threading Debug Tool")
    print("=" * 40)
    
    # Test single connection first
    test_single_connection()
    
    # Wait a bit between tests
    time.sleep(2)
    
    # Test concurrent connections
    test_concurrent_connections()
    
    print("\nAll tests completed!")