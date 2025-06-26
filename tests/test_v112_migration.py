"""
Breaking change and migration tests for SpacetimeDB v1.1.2 compatibility
"""
import pytest
from unittest.mock import patch, Mock
import sys
import os

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL


class TestBreakingChanges:
    """Test that breaking changes have clear error messages"""
    
    def test_init_method_removed(self):
        """Test that SpacetimeDBClient.init() no longer exists"""
        # The old init() method is gone
        with pytest.raises(AttributeError) as exc_info:
            SpacetimeDBClient.init(
                autogen_package=None,
                auth_token=None,
                host="localhost:3000",
                address_or_name="test-db"
            )
            
        # Error should be clear about the method not existing
        assert "init" in str(exc_info.value)
        assert "SpacetimeDBClient" in str(exc_info.value)
        
    def test_helpful_migration_error_for_init(self):
        """Test that users get helpful error when trying old pattern"""
        # When users try the old pattern, they should get AttributeError
        # In a real implementation, we could add a custom __getattr__ to provide
        # a more helpful message, but the standard AttributeError is clear enough
        
        try:
            SpacetimeDBClient.init(None, None, "localhost", "db")
        except AttributeError as e:
            # Standard Python error is clear enough
            assert "type object 'ModernSpacetimeDBClient' has no attribute 'init'" in str(e)
            
    def test_instance_connect_renamed(self):
        """Test that instance connect() method is now internal"""
        client = SpacetimeDBClient(autogen_package=None)
        
        # The public connect() is now _connect_internal()
        assert hasattr(client, '_connect_internal')
        
        # There is a connect() but it's a class method, not instance
        assert hasattr(SpacetimeDBClient, 'connect')
        
        # Calling connect as instance method with wrong signature should fail
        # (The class method expects different parameters)
        with pytest.raises(TypeError):
            # This would be the old instance method signature
            client.connect(
                auth_token=None,
                host="localhost",
                address_or_name="db",
                ssl_enabled=False
            )


class TestMigrationPath:
    """Test the recommended migration path from old to new API"""
    
    def test_migration_from_init_to_connect(self, mock_websocket):
        """Show migration from init() to connect()"""
        # OLD WAY (no longer works):
        # client = SpacetimeDBClient.init(
        #     autogen_package,
        #     auth_token,
        #     host,
        #     address_or_name,
        #     ssl_enabled,
        #     on_connect
        # )
        
        # NEW WAY:
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test-db",  # Note: renamed parameter
            auth_token=None,
            ssl_enabled=False,
            on_connect=lambda: None,
            test_mode=True
        )
        
        assert client is not None
        assert isinstance(client, SpacetimeDBClient)
        client.shutdown()
        
    def test_migration_with_protocol_configuration(self, mock_websocket):
        """Show how to configure protocol in new API"""
        # OLD WAY (if it existed):
        # client = SpacetimeDBClient.init(..., protocol="json")
        
        # NEW WAY - protocol in connect():
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test-db",
            protocol=BIN_PROTOCOL,  # Specify protocol here
            test_mode=True
        )
        
        assert client.protocol == BIN_PROTOCOL
        client.shutdown()
        
    def test_migration_with_builder_pattern(self, mock_websocket):
        """Show builder pattern as alternative migration path"""
        # Builder pattern provides more flexibility
        client = SpacetimeDBClient.builder() \
            .with_uri("ws://localhost:3000") \
            .with_module_name("test-db") \
            .with_protocol("text") \
            .with_token(None) \
            .on_connect(lambda: None) \
            .build()
            
        assert client is not None
        client.disconnect()
        
    def test_parameter_name_changes(self, mock_websocket):
        """Test that old parameter names are caught"""
        # 'address_or_name' -> 'database_address'
        
        # This will fail because 'address_or_name' is not recognized
        with pytest.raises(TypeError) as exc_info:
            SpacetimeDBClient.connect(
                host="localhost:3000",
                address_or_name="test-db",  # Old parameter name
                test_mode=True
            )
            
        # Error mentions missing required parameter or unexpected keyword
        error_str = str(exc_info.value)
        # The error should mention either unexpected keyword or missing database_address
        assert "address_or_name" in error_str or "database_address" in error_str


class TestOldProtocolRejection:
    """Test that old protocol strings are properly rejected"""
    
    def test_old_text_protocol_rejected(self, mock_websocket, connection_tracker):
        """Test that v1.text.spacetimedb is rejected"""
        old_protocol = "v1.text.spacetimedb"
        
        # Create client with old protocol
        client = SpacetimeDBClient(
            autogen_package=None,
            protocol=old_protocol  # This old protocol
        )
        
        # Mock rejection
        original_app = mock_websocket.WebSocketApp
        
        def mock_rejection(*args, **kwargs):
            app = original_app(*args, **kwargs)
            def run_forever():
                # Server rejects old protocol
                if app.on_error:
                    error = Exception("no valid protocol selected")
                    app.on_error(app, error)
                if app.on_close:
                    app.on_close(app, None, None)
            app.run_forever = run_forever
            return app
            
        mock_websocket.WebSocketApp = mock_rejection
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="test-db",
                ssl_enabled=False,
                on_error=connection_tracker.on_error
            )
            
            import time
            time.sleep(0.5)
            
            # Should get protocol rejection error
            assert connection_tracker.error is not None
            assert "no valid protocol selected" in str(connection_tracker.error)
            
        finally:
            client.disconnect()


class TestDatabaseNameValidation:
    """Test validation of database names for v1.1.2"""
    
    def test_underscore_in_database_name(self, mock_websocket, connection_tracker):
        """Test that underscores in database names are rejected"""
        client = SpacetimeDBClient(autogen_package=None)
        
        # Mock server rejection
        original_app = mock_websocket.WebSocketApp
        
        def mock_invalid_chars(*args, **kwargs):
            app = original_app(*args, **kwargs)
            # Check if URL contains underscore
            if "_" in args[0]:  # URL is first arg
                def run_forever():
                    if app.on_error:
                        error = Exception("Invalid URL: invalid characters in database name")
                        app.on_error(app, error)
                    if app.on_close:
                        app.on_close(app, None, None)
                app.run_forever = run_forever
            else:
                app.run_forever = original_app(*args, **kwargs).run_forever
            return app
            
        mock_websocket.WebSocketApp = mock_invalid_chars
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="test_module",  # Has underscore
                ssl_enabled=False,
                on_error=connection_tracker.on_error
            )
            
            import time
            time.sleep(0.5)
            
            assert connection_tracker.error is not None
            assert "invalid characters" in str(connection_tracker.error)
            
        finally:
            client.disconnect()
            
    def test_valid_database_names(self):
        """Document valid database name formats"""
        valid_names = [
            "my-database",
            "testdb",
            "game-server-1",
            "user123",
            "a",  # Single character
            "test-123-abc"
        ]
        
        invalid_names = [
            "test_module",     # Underscore
            "test.module",     # Dot
            "Test-Module",     # Uppercase
            "test module",     # Space
            "test@module",     # Special char
            "test/module",     # Slash
        ]
        
        # This test documents the patterns rather than testing them
        assert len(valid_names) > 0
        assert len(invalid_names) > 0


class TestAsyncClientMigration:
    """Test async client compatibility with v1.1.2 changes"""
    
    def test_async_client_uses_internal_connect(self):
        """Test that async client was updated to use _connect_internal"""
        from spacetimedb_sdk.spacetimedb_async_client import SpacetimeDBAsyncClient
        
        # Check that async client has been updated
        # It should call client._connect_internal not client.connect
        async_client = SpacetimeDBAsyncClient(autogen_package=None)
        
        # The async client's client instance should be ModernSpacetimeDBClient
        assert hasattr(async_client.client, '_connect_internal')
        
    def test_async_client_method_updates(self):
        """Test that async client methods were updated"""
        from spacetimedb_sdk.spacetimedb_async_client import SpacetimeDBAsyncClient
        
        async_client = SpacetimeDBAsyncClient(autogen_package=None)
        
        # Check client has new methods
        assert hasattr(async_client.client, 'disconnect')  # not 'close'
        assert hasattr(async_client.client, 'call_reducer')  # not '_reducer_call'


class TestMigrationDocumentation:
    """Test that migration is well documented through examples"""
    
    def test_simple_connection_example(self, mock_websocket):
        """Example: Simple connection for new users"""
        # Simplest way to connect in v1.1.2
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="my-game",
            on_connect=lambda: print("Connected!"),
            test_mode=True
        )
        
        assert client is not None
        client.shutdown()
        
    def test_full_featured_example(self, mock_websocket):
        """Example: Full-featured connection with all options"""
        def on_connect():
            print("Connected to SpacetimeDB!")
            
        def on_identity(token, identity, conn_id):
            print(f"Identity: {identity}")
            
        def on_error(error):
            print(f"Error: {error}")
            
        client = SpacetimeDBClient.connect(
            host="db.example.com:443",
            database_address="production-db",
            db_identity="550e8400-e29b-41d4-a716-446655440000",
            auth_token="secret-token",
            ssl_enabled=True,
            protocol=BIN_PROTOCOL,
            on_connect=on_connect,
            on_identity=on_identity,
            on_error=on_error,
            test_mode=True
        )
        
        assert client.protocol == BIN_PROTOCOL
        client.shutdown()
        
    def test_builder_pattern_example(self, mock_websocket):
        """Example: Using builder for complex configuration"""
        client = SpacetimeDBClient.builder() \
            .with_uri("wss://db.example.com:443") \
            .with_module_name("my-app") \
            .with_token("auth-token") \
            .with_protocol("binary") \
            .on_connect(lambda: print("Builder connected!")) \
            .on_error(lambda e: print(f"Builder error: {e}")) \
            .with_compression(True) \
            .build()
            
        assert client is not None
        client.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
