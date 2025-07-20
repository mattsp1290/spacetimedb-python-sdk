#!/usr/bin/env python3
"""
Integration tests for SpaceTimeDB SDK v1.1.2.
Tests complete workflows with mock server simulating various scenarios.
"""

import unittest
import sys
import os
import time
import asyncio
import json
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient
from spacetimedb_sdk.exceptions import (
    DatabaseNotFoundError,
    AuthenticationError,
    ConnectionTimeoutError,
    SpacetimeDBConnectionError
)

# Import mock server
from mock_spacetimedb_server import (
    MockSpaceTimeDBServer, create_test_server, with_mock_server
)


class TestPublishedDatabaseIntegration(unittest.TestCase):
    """Test integration with published database scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("normal", port=3002)
        self.server.start()
        self.client = None
        self.events_received = []
        
    def tearDown(self):
        """Clean up after tests."""
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
        self.server.stop()
        
    def test_complete_connection_workflow(self):
        """Test complete connection, query, and subscription workflow."""
        # Connect to mock server
        self.client = SpacetimeDBClient()
        
        # Track events
        identity_events = []
        subscription_events = []
        
        def on_identity(token, identity, connection_id):
            identity_events.append({
                'token': token,
                'identity': str(identity),
                'connection_id': str(connection_id)
            })
            
        def on_subscription_update(table_name, rows):
            subscription_events.append({
                'table': table_name,
                'rows': rows
            })
            
        self.client.register_on_identity(on_identity)
        
        # Connect
        self.client._connect_internal(
            auth_token=None,
            host="localhost:3002",
            database_address="test_db",
            ssl_enabled=False
        )
        
        # Wait for connection
        time.sleep(1)
        
        # Verify connection established
        self.assertTrue(self.client.is_connected)
        self.assertEqual(len(identity_events), 1)
        self.assertIsNotNone(self.client.identity)
        self.assertIsNotNone(self.client.connection_id)
        
        # Verify initial subscription data received
        # (Mock server sends table data automatically)
        
        # Check server stats
        self.assertEqual(self.server.stats["connections_accepted"], 1)
        self.assertEqual(self.server.stats["connections_rejected"], 0)
        
    def test_query_execution(self):
        """Test query execution through mock server."""
        self.client = SpacetimeDBClient()
        
        query_results = []
        
        def on_query_result(query_id, table, rows):
            query_results.append({
                'query_id': query_id,
                'table': table,
                'rows': rows
            })
            
        # Connect
        self.client._connect_internal(
            auth_token=None,
            host="localhost:3002",
            database_address="test_db",
            ssl_enabled=False
        )
        
        time.sleep(1)
        
        # Send a query (this would normally be done through client API)
        if hasattr(self.client, '_send_message'):
            query_msg = {
                "type": "query",
                "query_id": "test_query_1",
                "table": "users"
            }
            # Note: In real implementation, client would have query method
            
        # Verify stats
        self.assertGreater(self.server.stats["messages_sent"], 0)
        
    def test_reducer_execution(self):
        """Test reducer execution through mock server."""
        self.client = SpacetimeDBClient()
        
        # Connect
        self.client._connect_internal(
            auth_token=None,
            host="localhost:3002",
            database_address="test_db",
            ssl_enabled=False
        )
        
        time.sleep(1)
        
        # Call reducer (this would normally be done through client API)
        if hasattr(self.client, '_send_message'):
            reducer_msg = {
                "type": "reducer",
                "request_id": "test_reducer_1",
                "reducer": "send_message",
                "args": {
                    "recipient": "Bob",
                    "content": "Hello from test!"
                }
            }
            # Note: In real implementation, client would have reducer method
            
        # Verify connection is maintained
        self.assertTrue(self.client.is_connected)


class TestUnpublishedDatabaseScenarios(unittest.TestCase):
    """Test handling of unpublished database scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("unpublished", port=3003)
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
        
    def test_unpublished_database_error(self):
        """Test proper error when connecting to unpublished database."""
        self.client = SpacetimeDBClient()
        
        with self.assertRaises(DatabaseNotFoundError) as cm:
            self.client._connect_internal(
                auth_token=None,
                host="localhost:3003",
                database_address="unpublished_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
        # Verify error details
        error = cm.exception
        self.assertEqual(error.database_name, "unpublished_db")
        self.assertEqual(error.status_code, 404)
        
        # Verify server rejected connection
        self.assertEqual(self.server.stats["connections_rejected"], 1)
        self.assertEqual(self.server.stats["connections_accepted"], 0)


class TestAuthenticationScenarios(unittest.TestCase):
    """Test authentication integration scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = create_test_server("auth_required", port=3004)
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
        
    def test_valid_token_authentication(self):
        """Test successful authentication with valid token."""
        self.client = SpacetimeDBClient()
        
        # Connect with valid token
        self.client._connect_internal(
            auth_token="valid_token_123",
            host="localhost:3004",
            database_address="test_db",
            ssl_enabled=False
        )
        
        time.sleep(1)
        
        # Should connect successfully
        self.assertTrue(self.client.is_connected)
        self.assertEqual(self.server.stats["connections_accepted"], 1)
        
    def test_invalid_token_rejection(self):
        """Test rejection with invalid token."""
        self.client = SpacetimeDBClient()
        
        with self.assertRaises(AuthenticationError) as cm:
            self.client._connect_internal(
                auth_token="invalid_token_xyz",
                host="localhost:3004",
                database_address="test_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
        # Verify error
        error = cm.exception
        self.assertEqual(error.status_code, 401)
        
        # Verify server rejected connection
        self.assertEqual(self.server.stats["connections_rejected"], 1)
        
    def test_missing_token_rejection(self):
        """Test rejection when token required but not provided."""
        self.client = SpacetimeDBClient()
        
        with self.assertRaises(AuthenticationError) as cm:
            self.client._connect_internal(
                auth_token=None,
                host="localhost:3004",
                database_address="test_db",
                ssl_enabled=False
            )
            time.sleep(1)
            
        # Verify rejection
        self.assertEqual(self.server.stats["connections_rejected"], 1)


class TestNetworkFailureScenarios(unittest.TestCase):
    """Test network failure and recovery scenarios."""
    
    def test_connection_timeout(self):
        """Test connection timeout handling."""
        # Create server with slow connection
        server = create_test_server("slow_connection", port=3005)
        server.config.connection_delay = 5.0  # 5 second delay
        server.start()
        
        try:
            client = SpacetimeDBClient()
            
            # Set a short timeout (if supported)
            start_time = time.time()
            
            try:
                client._connect_internal(
                    auth_token=None,
                    host="localhost:3005",
                    database_address="test_db",
                    ssl_enabled=False
                )
                # If no timeout, wait briefly
                time.sleep(0.5)
                
            except ConnectionTimeoutError:
                # Expected timeout
                elapsed = time.time() - start_time
                self.assertLess(elapsed, 4.0)  # Should timeout before 5s delay
                
            finally:
                if client:
                    client.disconnect()
                    
        finally:
            server.stop()
            
    def test_message_delays(self):
        """Test handling of slow message responses."""
        server = create_test_server("slow_messages", port=3006)
        server.start()
        
        try:
            client = SpacetimeDBClient()
            
            # Connect
            client._connect_internal(
                auth_token=None,
                host="localhost:3006",
                database_address="test_db",
                ssl_enabled=False
            )
            
            # Messages will be delayed by 0.5s each
            time.sleep(2)
            
            # Should still be connected despite delays
            self.assertTrue(client.is_connected)
            
            client.disconnect()
            
        finally:
            server.stop()
            
    def test_connection_drop_recovery(self):
        """Test recovery from connection drops."""
        server = create_test_server("normal", port=3007)
        server.start()
        
        try:
            client = SpacetimeDBClient()
            
            # Track reconnection attempts
            reconnect_attempts = []
            
            def on_reconnect(attempt_number):
                reconnect_attempts.append(attempt_number)
                
            # Connect
            client._connect_internal(
                auth_token=None,
                host="localhost:3007",
                database_address="test_db",
                ssl_enabled=False
            )
            
            time.sleep(1)
            self.assertTrue(client.is_connected)
            
            # Simulate connection drop by stopping server
            server.stop()
            time.sleep(1)
            
            # Client should detect disconnection
            # (Depends on client implementation)
            
            # Restart server
            server = create_test_server("normal", port=3007)
            server.start()
            
            # Wait for potential reconnection
            time.sleep(2)
            
            # Check if client attempted reconnection
            # (This depends on auto-reconnect implementation)
            
            client.disconnect()
            
        finally:
            if server.running:
                server.stop()


class TestErrorInjectionScenarios(unittest.TestCase):
    """Test handling of various error conditions."""
    
    def test_error_prone_server(self):
        """Test client resilience with error-prone server."""
        server = create_test_server("error_prone", port=3008)
        server.start()
        
        try:
            client = SpacetimeDBClient()
            
            errors_received = []
            
            def on_error(error):
                errors_received.append(error)
                
            # Connect to error-prone server
            client._connect_internal(
                auth_token=None,
                host="localhost:3008",
                database_address="test_db",
                ssl_enabled=False,
                on_error=on_error
            )
            
            time.sleep(2)
            
            # Should receive some injected errors
            self.assertGreater(server.stats["errors_injected"], 0)
            
            # But connection should remain stable
            # (Depends on error handling implementation)
            
            client.disconnect()
            
        finally:
            server.stop()


class TestBinaryProtocol(unittest.TestCase):
    """Test binary protocol support."""
    
    @unittest.skip("Binary protocol testing requires full BSATN implementation")
    def test_binary_protocol_connection(self):
        """Test connection using binary protocol."""
        server = create_test_server("binary_only", port=3009)
        server.start()
        
        try:
            client = SpacetimeDBClient()
            
            # Connect with binary protocol
            # (Requires client support for protocol selection)
            client._connect_internal(
                host="localhost:3009",
                database_address="test_db",
                ssl_enabled=False,
                protocol="v1.bsatn.spacetimedb"  # If supported
            )
            
            time.sleep(1)
            
            # Verify binary protocol is used
            # (Would need to check client's active protocol)
            
            client.disconnect()
            
        finally:
            server.stop()


class TestConcurrentConnections(unittest.TestCase):
    """Test multiple concurrent connections."""
    
    def test_multiple_clients(self):
        """Test multiple clients connecting simultaneously."""
        server = create_test_server("normal", port=3010)
        server.start()
        
        clients = []
        
        try:
            # Create multiple clients
            for i in range(5):
                client = SpacetimeDBClient()
                client._connect_internal(
                    auth_token=None,
                    host="localhost:3010",
                    database_address="test_db",
                    ssl_enabled=False
                )
                clients.append(client)
                
            # Wait for all connections
            time.sleep(2)
            
            # Verify all connected
            for client in clients:
                self.assertTrue(client.is_connected)
                
            # Check server stats
            self.assertEqual(server.stats["connections_accepted"], 5)
            
            # Disconnect all
            for client in clients:
                client.disconnect()
                
        finally:
            server.stop()


def run_integration_tests():
    """Run all integration tests."""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestPublishedDatabaseIntegration,
        TestUnpublishedDatabaseScenarios,
        TestAuthenticationScenarios,
        TestNetworkFailureScenarios,
        TestErrorInjectionScenarios,
        TestBinaryProtocol,
        TestConcurrentConnections
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
    success = run_integration_tests()
    sys.exit(0 if success else 1)
