#!/usr/bin/env python3
"""
Edge case tests for SpaceTimeDB SDK v1.1.2.
Tests handling of unusual, extreme, and error-prone scenarios.
"""

import unittest
import sys
import os
import time
import threading
import json
import random
import string
from typing import List, Dict, Any
import concurrent.futures

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient
from spacetimedb_sdk.exceptions import (
    SpacetimeDBConnectionError,
    DatabaseNotFoundError,
    ProtocolMismatchError
)

# Import mock server
from mock_spacetimedb_server import (
    MockSpaceTimeDBServer, create_test_server, MockDatabase
)


class TestMalformedResponses(unittest.TestCase):
    """Test handling of malformed server responses."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = None
        self.client = None
        
    def tearDown(self):
        """Clean up after tests."""
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
        if self.server:
            self.server.stop()
            
    def test_malformed_json_response(self):
        """Test handling of malformed JSON responses."""
        # Create a custom mock server that sends malformed JSON
        self.server = create_test_server("normal", port=3030)
        
        # Override message sending to corrupt JSON
        original_send = self.server._send_message
        
        async def corrupt_send(websocket, message):
            # Occasionally send malformed JSON
            if random.random() < 0.3:
                await websocket.send("{invalid json}")
            else:
                await original_send(websocket, message)
                
        self.server._send_message = corrupt_send
        self.server.start()
        
        # Try to connect and handle errors
        self.client = SpacetimeDBClient()
        errors_received = []
        
        def on_error(error):
            errors_received.append(error)
            
        try:
            self.client._connect_internal(
                auth_token=None,
                host="localhost:3030",
                database_address="test_db",
                ssl_enabled=False,
                on_error=on_error
            )
            time.sleep(2)
            
            # Should receive some JSON parsing errors
            # But connection might still work with valid messages
            
        except Exception as e:
            # Expected - malformed responses may break connection
            pass
            
    def test_incomplete_message_handling(self):
        """Test handling of incomplete/partial messages."""
        # This would test WebSocket frame fragmentation
        # Real implementation would need lower-level WebSocket control
        self.skipTest("Requires low-level WebSocket frame control")
        
    def test_oversized_message_handling(self):
        """Test handling of messages exceeding size limits."""
        self.server = create_test_server("normal", port=3031)
        
        # Create database with large data
        large_db = MockDatabase("large_db")
        
        # Add table with very large rows
        huge_data = "x" * (1024 * 1024)  # 1MB string
        large_db.add_table("huge_table", [
            {"id": i, "data": huge_data} for i in range(5)
        ])
        
        self.server.add_database("large_db", large_db)
        self.server.start()
        
        self.client = SpacetimeDBClient()
        
        try:
            self.client._connect_internal(
                auth_token=None,
                host="localhost:3031",
                database_address="large_db",
                ssl_enabled=False
            )
            
            # Initial subscription will send large data
            time.sleep(2)
            
            # Should handle large messages gracefully
            # (May depend on client's max message size settings)
            
        except Exception as e:
            # Large messages might cause issues
            print(f"Large message handling: {e}")


class TestUnicodeAndSpecialCharacters(unittest.TestCase):
    """Test handling of Unicode and special characters."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3032)
        
        # Create database with Unicode data
        unicode_db = MockDatabase("unicode_db")
        
        # Various Unicode test cases
        unicode_data = [
            {"id": 1, "text": "Hello 世界"},
            {"id": 2, "text": "Émojis: 😀🎉🔥"},
            {"id": 3, "text": "Special: \n\t\r\0"},
            {"id": 4, "text": "RTL: العربية עברית"},
            {"id": 5, "text": "Math: ∑∏∫≤≥±∞"},
            {"id": 6, "text": "Symbols: ♠♣♥♦★☆"},
            {"id": 7, "text": "Combining: é = e\u0301"},
            {"id": 8, "text": "Zero-width: ‌‍⁠"},
        ]
        
        unicode_db.add_table("unicode_test", unicode_data)
        self.server.add_database("unicode_db", unicode_db)
        self.server.start()
        
        self.client = None
        
    def tearDown(self):
        """Clean up after tests."""
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
        self.server.stop()
        
    def test_unicode_in_data(self):
        """Test Unicode characters in data."""
        self.client = SpacetimeDBClient()
        
        received_data = []
        
        def on_data(table_name, rows):
            received_data.extend(rows)
            
        self.client._connect_internal(
            auth_token=None,
            host="localhost:3032",
            database_address="unicode_db",
            ssl_enabled=False
        )
        
        time.sleep(1)
        
        # Verify Unicode data was received correctly
        # (Would need to check actual received data)
        
    def test_unicode_in_identifiers(self):
        """Test Unicode in database/table names."""
        # Create database with Unicode name
        unicode_name_db = MockDatabase("データベース")
        unicode_name_db.add_table("テーブル", [{"id": 1, "data": "test"}])
        
        self.server.add_database("データベース", unicode_name_db)
        
        # Try to connect to Unicode-named database
        client2 = SpacetimeDBClient()
        
        try:
            client2._connect_internal(
                auth_token=None,
                host="localhost:3032",
                database_address="データベース",
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Should handle Unicode database names
            
        except Exception as e:
            print(f"Unicode database name handling: {e}")
        finally:
            try:
                client2.disconnect()
            except:
                pass


class TestExtremeLengths(unittest.TestCase):
    """Test handling of extremely long values."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3033)
        self.server.start()
        self.clients = []
        
    def tearDown(self):
        """Clean up after tests."""
        for client in self.clients:
            try:
                client.disconnect()
            except:
                pass
        self.server.stop()
        
    def test_very_long_database_names(self):
        """Test extremely long database names."""
        # Create database with very long name
        long_name = "a" * 1000
        long_db = MockDatabase(long_name)
        self.server.add_database(long_name, long_db)
        
        client = SpacetimeDBClient()
        self.clients.append(client)
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3033",
                database_address=long_name,
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Should handle long names (or reject gracefully)
            
        except Exception as e:
            # Long names might be rejected
            print(f"Long database name handling: {type(e).__name__}")
            
    def test_very_long_tokens(self):
        """Test extremely long authentication tokens."""
        # Generate a very long token
        long_token = "".join(random.choices(string.ascii_letters, k=10000))
        
        client = SpacetimeDBClient()
        self.clients.append(client)
        
        try:
            client._connect_internal(
                auth_token=long_token,
                host="localhost:3033",
                database_address="test_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Should handle long tokens (likely reject as invalid)
            
        except Exception as e:
            # Expected - very long tokens should be rejected
            pass
            
    def test_deeply_nested_data(self):
        """Test deeply nested data structures."""
        # Create deeply nested data
        def create_nested_dict(depth):
            if depth == 0:
                return {"value": "leaf"}
            return {"nested": create_nested_dict(depth - 1)}
            
        nested_db = MockDatabase("nested_db")
        nested_db.add_table("nested_table", [
            {"id": 1, "data": create_nested_dict(100)}  # 100 levels deep
        ])
        
        self.server.add_database("nested_db", nested_db)
        
        client = SpacetimeDBClient()
        self.clients.append(client)
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3033",
                database_address="nested_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Should handle or reject deeply nested data
            
        except Exception as e:
            print(f"Deeply nested data handling: {type(e).__name__}")


class TestRapidOperations(unittest.TestCase):
    """Test rapid connect/disconnect and other operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3034)
        self.server.start()
        
    def tearDown(self):
        """Clean up after tests."""
        self.server.stop()
        
    def test_rapid_connect_disconnect(self):
        """Test rapid connection/disconnection cycles."""
        print("\n=== Rapid Connect/Disconnect Test ===")
        
        errors = []
        successful_cycles = 0
        
        for i in range(20):
            client = SpacetimeDBClient()
            
            try:
                # Connect
                client._connect_internal(
                    auth_token=None,
                    host="localhost:3034",
                    database_address="test_db",
                    ssl_enabled=False
                )
                
                # Immediately disconnect
                client.disconnect()
                successful_cycles += 1
                
                # No delay between cycles
                
            except Exception as e:
                errors.append(e)
            finally:
                try:
                    client.disconnect()
                except:
                    pass
                    
        print(f"Successful cycles: {successful_cycles}/20")
        print(f"Errors: {len(errors)}")
        
        # Should handle rapid cycles gracefully
        self.assertGreater(successful_cycles, 15)  # Allow some failures
        
    def test_concurrent_operations_same_client(self):
        """Test concurrent operations on the same client."""
        client = SpacetimeDBClient()
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3034",
                database_address="test_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Simulate concurrent operations
            def operation():
                try:
                    # In real implementation, would perform actual operations
                    # like queries, subscriptions, etc.
                    time.sleep(random.uniform(0.01, 0.1))
                    return True
                except Exception as e:
                    return False
                    
            # Run multiple operations concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(operation) for _ in range(50)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                
            success_rate = sum(results) / len(results) * 100
            print(f"Concurrent operations success rate: {success_rate:.1f}%")
            
        finally:
            client.disconnect()


class TestResourceExhaustion(unittest.TestCase):
    """Test behavior under resource exhaustion."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3035)
        self.server.config.max_connections = 10  # Low limit
        self.server.start()
        self.clients = []
        
    def tearDown(self):
        """Clean up after tests."""
        for client in self.clients:
            try:
                client.disconnect()
            except:
                pass
        self.server.stop()
        
    def test_connection_limit_exhaustion(self):
        """Test behavior when connection limit is reached."""
        print("\n=== Connection Limit Exhaustion Test ===")
        
        successful_connections = 0
        rejected_connections = 0
        
        # Try to create more connections than allowed
        for i in range(15):
            client = SpacetimeDBClient()
            
            try:
                client._connect_internal(
                    auth_token=None,
                    host="localhost:3035",
                    database_address="test_db",
                    ssl_enabled=False
                )
                self.clients.append(client)
                successful_connections += 1
                
            except Exception as e:
                rejected_connections += 1
                
        print(f"Successful connections: {successful_connections}")
        print(f"Rejected connections: {rejected_connections}")
        
        # Should accept up to limit and reject beyond
        self.assertLessEqual(successful_connections, 10)
        self.assertGreater(rejected_connections, 0)
        
    def test_memory_pressure_simulation(self):
        """Simulate memory pressure scenarios."""
        # Create large amounts of data to simulate memory pressure
        memory_db = MockDatabase("memory_test")
        
        # Add multiple large tables
        for i in range(10):
            large_rows = [
                {"id": j, "data": "x" * 10000}  # 10KB per row
                for j in range(100)  # 100 rows = 1MB per table
            ]
            memory_db.add_table(f"table_{i}", large_rows)
            
        self.server.add_database("memory_test", memory_db)
        
        # Connect multiple clients to increase memory usage
        clients_created = 0
        
        try:
            for i in range(5):
                client = SpacetimeDBClient()
                client._connect_internal(
                    auth_token=None,
                    host="localhost:3035",
                    database_address="memory_test",
                    ssl_enabled=False
                )
                self.clients.append(client)
                clients_created += 1
                time.sleep(0.5)  # Let data transfer
                
        except Exception as e:
            print(f"Memory pressure test stopped after {clients_created} clients: {e}")
            
        # Should handle memory pressure gracefully
        self.assertGreater(clients_created, 0)


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of SDK operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3036)
        self.server.start()
        
    def tearDown(self):
        """Clean up after tests."""
        self.server.stop()
        
    def test_concurrent_client_creation(self):
        """Test creating multiple clients from different threads."""
        print("\n=== Thread Safety: Concurrent Client Creation ===")
        
        clients = []
        errors = []
        lock = threading.Lock()
        
        def create_client(client_id):
            try:
                client = SpacetimeDBClient()
                client._connect_internal(
                    auth_token=None,
                    host="localhost:3036",
                    database_address="test_db",
                    ssl_enabled=False
                )
                
                with lock:
                    clients.append(client)
                    
            except Exception as e:
                with lock:
                    errors.append((client_id, e))
                    
        # Create clients from multiple threads
        threads = []
        for i in range(20):
            thread = threading.Thread(target=create_client, args=(i,))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads
        for thread in threads:
            thread.join()
            
        print(f"Successfully created {len(clients)} clients")
        print(f"Errors: {len(errors)}")
        
        # Clean up
        for client in clients:
            try:
                client.disconnect()
            except:
                pass
                
        # Should create most clients successfully
        self.assertGreater(len(clients), 15)
        
    def test_shared_client_thread_safety(self):
        """Test using a single client from multiple threads."""
        client = SpacetimeDBClient()
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3036",
                database_address="test_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Simulate concurrent access to client
            operation_counts = {}
            errors = []
            lock = threading.Lock()
            
            def perform_operations(thread_id):
                count = 0
                try:
                    for i in range(100):
                        # Simulate various operations
                        # In real implementation, would call client methods
                        if hasattr(client, 'is_connected'):
                            _ = client.is_connected
                        if hasattr(client, 'identity'):
                            _ = client.identity
                        count += 1
                        
                except Exception as e:
                    with lock:
                        errors.append((thread_id, e))
                        
                with lock:
                    operation_counts[thread_id] = count
                    
            # Run operations from multiple threads
            threads = []
            for i in range(10):
                thread = threading.Thread(target=perform_operations, args=(i,))
                threads.append(thread)
                thread.start()
                
            for thread in threads:
                thread.join()
                
            total_operations = sum(operation_counts.values())
            print(f"Total operations performed: {total_operations}")
            print(f"Thread errors: {len(errors)}")
            
            # Should complete most operations without errors
            self.assertGreater(total_operations, 800)  # 80% success rate
            
        finally:
            client.disconnect()


class TestBoundaryConditions(unittest.TestCase):
    """Test various boundary conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3037)
        self.server.start()
        
    def tearDown(self):
        """Clean up after tests."""
        self.server.stop()
        
    def test_empty_database(self):
        """Test connecting to database with no tables."""
        empty_db = MockDatabase("empty_db")
        self.server.add_database("empty_db", empty_db)
        
        client = SpacetimeDBClient()
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3037",
                database_address="empty_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Should handle empty database gracefully
            self.assertTrue(client.is_connected)
            
        finally:
            client.disconnect()
            
    def test_null_and_empty_values(self):
        """Test handling of null and empty values."""
        null_db = MockDatabase("null_db")
        null_db.add_table("null_test", [
            {"id": 1, "value": None},
            {"id": 2, "value": ""},
            {"id": 3, "value": []},
            {"id": 4, "value": {}},
            {"id": 5, "value": 0},
            {"id": 6, "value": False},
        ])
        
        self.server.add_database("null_db", null_db)
        
        client = SpacetimeDBClient()
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3037",
                database_address="null_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
            # Should handle various empty/null values
            
        finally:
            client.disconnect()
            
    def test_special_port_numbers(self):
        """Test connection to special port numbers."""
        # Test high port number
        high_port_server = create_test_server("normal", port=65535)
        high_port_server.start()
        
        try:
            client = SpacetimeDBClient()
            client._connect_internal(
                auth_token=None,
                host="localhost:65535",
                database_address="test_db",
                ssl_enabled=False
            )
            time.sleep(0.5)
            client.disconnect()
            
        finally:
            high_port_server.stop()


def run_edge_case_tests():
    """Run all edge case tests."""
    print("SpaceTimeDB SDK v1.1.2 Edge Case Tests")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestMalformedResponses,
        TestUnicodeAndSpecialCharacters,
        TestExtremeLengths,
        TestRapidOperations,
        TestResourceExhaustion,
        TestThreadSafety,
        TestBoundaryConditions
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
        
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Run the test suite
    success = run_edge_case_tests()
    sys.exit(0 if success else 1)
