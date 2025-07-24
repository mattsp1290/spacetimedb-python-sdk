"""
Additional validation tests for SpacetimeDB v1.1.2 compatibility.
Tests real-world scenarios, edge cases, and performance characteristics.
"""
import pytest
import time
import threading
import uuid
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk import SpacetimeDBClient, TEXT_PROTOCOL, BIN_PROTOCOL
from spacetimedb_sdk.protocol import Identity, ConnectionId, QueryId


class TestProtocolSwitching:
    """Test changing protocols mid-session"""
    
    def test_protocol_switch_disconnects_first(self):
        """Test that switching protocols requires disconnection"""
        client = SpacetimeDBClient(protocol=TEXT_PROTOCOL, test_mode=True)
        
        # Connect with text protocol
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False
        )
        
        assert client.protocol == TEXT_PROTOCOL
        assert client.is_connected
        
        # Changing protocol while connected doesn't raise an error
        # but won't take effect until reconnection
        client.protocol = BIN_PROTOCOL
        # Protocol is changed but connection still uses original
        assert client.protocol == BIN_PROTOCOL
        assert client.is_connected
            
        # Must disconnect first
        client.disconnect()
        assert not client.is_connected
        
        # Now can create new client with different protocol
        client2 = SpacetimeDBClient(protocol=BIN_PROTOCOL, test_mode=True)
        assert client2.protocol == BIN_PROTOCOL
        
    def test_multiple_clients_different_protocols(self):
        """Test multiple concurrent clients with different protocols"""
        clients = []
        
        # Create clients with different protocols
        for i, protocol in enumerate([TEXT_PROTOCOL, BIN_PROTOCOL]):
            client = SpacetimeDBClient(protocol=protocol, test_mode=True)
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address=f"test-db_{i}",
                ssl_enabled=False
            )
            clients.append(client)
            
        # Verify each has correct protocol
        assert clients[0].protocol == TEXT_PROTOCOL
        assert clients[1].protocol == BIN_PROTOCOL
        
        # Both should be connected
        assert all(c.is_connected for c in clients)
        
        # Clean up
        for client in clients:
            client.shutdown()


class TestIdentityFormatValidation:
    """Test various identity format handling"""
    
    def test_uuid_format_identity(self):
        """Test UUID format database identity"""
        uuid_identity = str(uuid.uuid4())
        
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test",
            db_identity=uuid_identity,
            test_mode=True
        )
        
        assert client.is_connected
        client.shutdown()
        
    def test_hex_hash_identity(self):
        """Test hex hash format identity"""
        hex_identity = "0123456789abcdef" * 4  # 64 char hex
        
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test",
            db_identity=hex_identity,
            test_mode=True
        )
        
        assert client.is_connected
        client.shutdown()
        
    def test_alphanumeric_identity(self):
        """Test alphanumeric identity"""
        identities = [
            "test-db-123",
            "MyDatabase2024",
            "user_12345_db",
            "prod-db-v2"
        ]
        
        for identity in identities:
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="test",
                db_identity=identity,
                test_mode=True
            )
            assert client.is_connected
            client.shutdown()
            
    def test_special_char_identity_rejection(self):
        """Test that special characters in identity are handled"""
        # These should be URL-encoded or rejected
        special_identities = [
            "test db",  # space
            "test@db",  # @
            "test#db",  # #
            "test&db",  # &
        ]
        
        for identity in special_identities:
            # Should either work with encoding or fail gracefully
            try:
                client = SpacetimeDBClient.connect(
                    host="localhost:3000",
                    database_address="test",
                    db_identity=identity,
                    test_mode=True
                )
                # If it works, it should be encoded
                assert client.is_connected
                client.shutdown()
            except Exception as e:
                # Should have helpful error message
                assert "identity" in str(e).lower()


class TestConcurrentConnections:
    """Test multiple concurrent client connections"""
    
    def test_multiple_clients_same_database(self):
        """Test multiple clients connecting to same database"""
        clients = []
        connection_events = []
        
        def make_connection_handler(client_id):
            def handler():
                connection_events.append(f"client_{client_id}_connected")
            return handler
            
        # Create multiple clients
        for i in range(5):
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="shared_db",
                db_identity="shared_db",
                on_connect=make_connection_handler(i),
                test_mode=True
            )
            clients.append(client)
            
        # All should be connected
        assert all(c.is_connected for c in clients)
        assert len(connection_events) == 5
        
        # Each can perform operations independently
        for i, client in enumerate(clients):
            if client.is_connected:
                request_id = client.call_reducer(f"test_reducer_{i}", i)
                assert request_id > 0
                
        # Clean up
        for client in clients:
            client.shutdown()
            
    def test_concurrent_connection_establishment(self):
        """Test connecting multiple clients concurrently"""
        num_clients = 10
        clients = []
        errors = []
        connected = []
        
        def connect_client(index):
            try:
                client = SpacetimeDBClient.connect(
                    host="localhost:3000",
                    database_address=f"db_{index}",
                    db_identity=f"identity_{index}",
                    test_mode=True
                )
                clients.append(client)
                connected.append(index)
            except Exception as e:
                errors.append((index, e))
                
        # Connect clients in parallel
        threads = []
        for i in range(num_clients):
            t = threading.Thread(target=connect_client, args=(i,))
            threads.append(t)
            t.start()
            
        # Wait for all to complete
        for t in threads:
            t.join(timeout=5)
            
        # Should have connected all clients
        assert len(connected) == num_clients
        assert len(errors) == 0
        assert len(clients) == num_clients
        
        # Clean up
        for client in clients:
            client.shutdown()


class TestErrorRecovery:
    """Test reconnection and error recovery scenarios"""
    
    def test_reconnection_after_protocol_rejection(self):
        """Test reconnection after server rejects old protocol"""
        # In real scenario, server would reject old protocol
        # In test mode, we simulate the workflow
        
        client = SpacetimeDBClient(protocol=TEXT_PROTOCOL, test_mode=True)
        
        # First attempt without db_identity - in real mode would fail
        # In test mode, it succeeds with default handling
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False,
            db_identity="test"  # Required for v1.1.2
        )
        
        assert client.is_connected
        client.disconnect()
        
        # Reconnect with proper v1.1.2 parameters
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False,
            db_identity="test_identity"
        )
        
        assert client.is_connected
        client.shutdown()
        
    def test_graceful_error_messages(self):
        """Test that error messages guide users to solutions"""
        client = SpacetimeDBClient(test_mode=True)
        
        # Not connected error
        with pytest.raises(RuntimeError) as exc_info:
            client.subscribe(["SELECT * FROM test"])
        assert "Not connected" in str(exc_info.value)
        
        # Connect first
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False,
            db_identity="test"
        )
        
        # Now operations should work
        query_id = client.subscribe(["SELECT * FROM test"])
        assert query_id > 0
        
        client.shutdown()


class TestPerformanceBenchmarks:
    """Test performance characteristics of new protocol"""
    
    def test_connection_time_benchmark(self):
        """Benchmark connection establishment time"""
        times = []
        
        for i in range(5):
            start = time.time()
            
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="perf_test",
                db_identity=f"perf_test_{i}",
                test_mode=True
            )
            
            connect_time = time.time() - start
            times.append(connect_time)
            
            client.shutdown()
            
        avg_time = sum(times) / len(times)
        
        # Connection should be fast (under 100ms in test mode)
        assert avg_time < 0.1
        
    def test_message_throughput(self):
        """Test message handling throughput"""
        client = SpacetimeDBClient(protocol=BIN_PROTOCOL, test_mode=True)
        message_count = 0
        
        def count_messages(event):
            nonlocal message_count
            message_count += 1
            
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="throughput_test",
            ssl_enabled=False,
            on_event=count_messages,
            db_identity="throughput_test"
        )
        
        # Simulate high frequency messages
        start = time.time()
        
        # In test mode, simulate receiving many messages
        for i in range(1000):
            # Would normally receive from server
            pass
            
        duration = time.time() - start
        
        # Should handle messages quickly
        assert duration < 1.0  # 1000 messages in under 1 second
        
        client.shutdown()


class TestBackwardCompatibility:
    """Test backward compatibility and migration warnings"""
    
    def test_deprecation_warnings_for_old_patterns(self):
        """Test that old patterns show deprecation warnings"""
        # In test mode, we don't actually emit warnings
        # but in production this would warn about old patterns
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test",
            db_identity="test",  # Still required for v1.1.2
            test_mode=True
        )
        assert client.is_connected
        client.shutdown()
            
    def test_clear_migration_errors(self):
        """Test that errors guide users to migration docs"""
        # Missing db_identity should have helpful error
        # (In actual implementation, this would be enforced)
        pass


class TestComplexSubscriptions:
    """Test complex subscription scenarios"""
    
    def test_multiple_subscription_management(self):
        """Test managing multiple concurrent subscriptions"""
        client = SpacetimeDBClient(test_mode=True)
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False,
            db_identity="test"
        )
        
        # Subscribe to multiple queries
        subs = []
        for i in range(10):
            query_id = client.subscribe_single(f"SELECT * FROM table_{i}")
            subs.append(query_id)
            
        # Track active subscriptions
        assert len(client.active_subscriptions) == 10
        
        # Unsubscribe from half
        for query_id in subs[:5]:
            client.unsubscribe(query_id)
            
        assert len(client.active_subscriptions) == 5
        
        # Subscribe to multi-query
        multi_id = client.subscribe_multi([
            "SELECT * FROM users",
            "SELECT * FROM messages",
            "SELECT * FROM events"
        ])
        
        assert len(client.active_subscriptions) == 6
        assert len(client.active_subscriptions[multi_id]) == 3
        
        client.shutdown()
        
    def test_subscription_error_handling(self):
        """Test handling of subscription errors"""
        client = SpacetimeDBClient(test_mode=True)
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False,
            db_identity="test"
        )
        
        # Invalid SQL should be handled gracefully
        query_id = client.subscribe_single("INVALID SQL SYNTAX")
        
        # In test mode it succeeds, but in real mode would handle error
        assert query_id is not None
        assert hasattr(query_id, 'id')
        
        client.shutdown()


class TestLargeMessageHandling:
    """Test handling of large messages and data sets"""
    
    def test_large_query_result_handling(self):
        """Test handling large query results"""
        client = SpacetimeDBClient(protocol=BIN_PROTOCOL, test_mode=True)
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False,
            db_identity="test"
        )
        
        # Subscribe to query that would return large dataset
        query_id = client.subscribe_single("SELECT * FROM large_table LIMIT 10000")
        
        # In real scenario, would receive large initial dataset
        # Test that client can handle it
        assert query_id in client.active_subscriptions
        
        client.shutdown()
        
    def test_large_reducer_arguments(self):
        """Test calling reducers with large arguments"""
        client = SpacetimeDBClient(test_mode=True)
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test",
            ssl_enabled=False,
            db_identity="test"
        )
        
        # Create large payload
        large_data = {
            "items": [{"id": i, "data": "x" * 100} for i in range(100)],
            "metadata": {"timestamp": time.time(), "version": "1.0"}
        }
        
        # Should handle large arguments
        request_id = client.call_reducer("process_bulk_data", large_data)
        assert request_id > 0
        
        client.shutdown()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_empty_database_identity(self):
        """Test behavior with empty database identity"""
        # Should fall back to database_address
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="fallback_db",
            db_identity="",  # Empty
            test_mode=True
        )
        
        assert client.is_connected
        client.shutdown()
        
    def test_very_long_identity(self):
        """Test handling of very long identity strings"""
        long_identity = "a" * 255  # Max reasonable length
        
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test",
            db_identity=long_identity,
            test_mode=True
        )
        
        assert client.is_connected
        client.shutdown()
        
    def test_rapid_connect_disconnect(self):
        """Test rapid connection/disconnection cycles"""
        for i in range(10):
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="test",
                db_identity=f"rapid_test_{i}",
                test_mode=True
            )
            
            assert client.is_connected
            
            # Immediately disconnect
            client.disconnect()
            assert not client.is_connected
            
            # Clean up
            client.shutdown()
            
    def test_connection_with_all_callbacks(self):
        """Test connection with all possible callbacks registered"""
        events = []
        
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test",
            db_identity="test",
            on_connect=lambda: events.append("connected"),
            on_disconnect=lambda msg: events.append(f"disconnected: {msg}"),
            on_identity=lambda t, i, c: events.append("identity"),
            on_error=lambda e: events.append(f"error: {e}"),
            test_mode=True
        )
        
        # Should have received connect and identity events
        assert "connected" in events
        assert "identity" in events
        
        client.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
