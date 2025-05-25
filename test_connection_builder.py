"""
Tests for SpacetimeDB Connection Builder Pattern

This test suite verifies the fluent builder API works correctly and provides
the same functionality as the TypeScript SDK's DbConnection.builder() pattern.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from types import ModuleType

from src.spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from src.spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder


class TestSpacetimeDBConnectionBuilder:
    """Test the connection builder pattern implementation."""
    
    def test_builder_creation(self):
        """Test that builder can be created from client class."""
        builder = ModernSpacetimeDBClient.builder()
        assert isinstance(builder, SpacetimeDBConnectionBuilder)
    
    def test_fluent_api_chaining(self):
        """Test that all builder methods return self for chaining."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Test method chaining
        result = (builder
                 .with_uri("ws://localhost:3000")
                 .with_module_name("test_module")
                 .with_token("test_token")
                 .with_protocol("binary")
                 .on_connect(lambda: None)
                 .on_disconnect(lambda reason: None)
                 .with_energy_budget(10000))
        
        assert result is builder
    
    def test_uri_configuration(self):
        """Test URI configuration and validation."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Valid URIs
        builder.with_uri("ws://localhost:3000")
        builder.with_uri("wss://testnet.spacetimedb.com")
        
        # Invalid URIs should raise errors
        with pytest.raises(ValueError, match="URI cannot be empty"):
            builder.with_uri("")
        
        with pytest.raises(ValueError, match="Invalid URI scheme"):
            builder.with_uri("http://localhost:3000")
        
        with pytest.raises(ValueError, match="Invalid URI scheme"):
            builder.with_uri("invalid://localhost:3000")
    
    def test_ssl_detection_from_uri(self):
        """Test that SSL is automatically detected from URI scheme."""
        builder = ModernSpacetimeDBClient.builder()
        
        # ws:// should disable SSL
        builder.with_uri("ws://localhost:3000")
        validation = builder.validate()
        assert not validation['configuration']['ssl_enabled']
        
        # wss:// should enable SSL
        builder.with_uri("wss://secure.example.com")
        validation = builder.validate()
        assert validation['configuration']['ssl_enabled']
    
    def test_module_name_configuration(self):
        """Test module name configuration."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Valid module name
        builder.with_module_name("my_game_module")
        
        # Empty module name should raise error
        with pytest.raises(ValueError, match="Module name cannot be empty"):
            builder.with_module_name("")
    
    def test_protocol_configuration(self):
        """Test protocol configuration."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Valid protocols
        builder.with_protocol("text")
        builder.with_protocol("binary")
        
        # Invalid protocol should raise error
        with pytest.raises(ValueError, match="Invalid protocol"):
            builder.with_protocol("invalid")
    
    def test_energy_configuration(self):
        """Test energy management configuration."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Valid energy settings
        builder.with_energy_budget(15000, initial=2000, max_energy=2000)
        
        # Negative values should raise error
        with pytest.raises(ValueError, match="Energy values must be non-negative"):
            builder.with_energy_budget(-1000)
        
        with pytest.raises(ValueError, match="Energy values must be non-negative"):
            builder.with_energy_budget(1000, initial=-500)
        
        with pytest.raises(ValueError, match="Energy values must be non-negative"):
            builder.with_energy_budget(1000, max_energy=-500)
    
    def test_callback_registration(self):
        """Test callback registration."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Valid callbacks
        connect_callback = lambda: print("connected")
        disconnect_callback = lambda reason: print(f"disconnected: {reason}")
        identity_callback = lambda token, identity, conn_id: print("identity")
        error_callback = lambda error: print(f"error: {error}")
        
        builder.on_connect(connect_callback)
        builder.on_disconnect(disconnect_callback)
        builder.on_identity(identity_callback)
        builder.on_error(error_callback)
        
        # Non-callable should raise error
        with pytest.raises(ValueError, match="Callback must be callable"):
            builder.on_connect("not_callable")
        
        with pytest.raises(ValueError, match="Callback must be callable"):
            builder.on_disconnect(123)
    
    def test_autogen_package_configuration(self):
        """Test autogen package configuration."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Mock module
        mock_module = Mock(spec=ModuleType)
        builder.with_autogen_package(mock_module)
        
        # Should accept any module-like object
        assert True  # If no exception raised, test passes
    
    def test_validation_missing_required_fields(self):
        """Test validation with missing required fields."""
        builder = ModernSpacetimeDBClient.builder()
        
        # No configuration
        validation = builder.validate()
        assert not validation['valid']
        assert "URI is required" in validation['issues']
        assert "Module name is required" in validation['issues']
        
        # Only URI configured
        builder.with_uri("ws://localhost:3000")
        validation = builder.validate()
        assert not validation['valid']
        assert "Module name is required" in validation['issues']
        
        # Both URI and module configured
        builder.with_module_name("test_module")
        validation = builder.validate()
        assert validation['valid']
        assert len(validation['issues']) == 0
    
    def test_validation_complete_configuration(self):
        """Test validation with complete configuration."""
        builder = (ModernSpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("test_module")
                  .with_token("test_token")
                  .with_protocol("binary")
                  .with_energy_budget(15000, 2000, 2000)
                  .on_connect(lambda: None)
                  .on_disconnect(lambda reason: None))
        
        validation = builder.validate()
        assert validation['valid']
        assert len(validation['issues']) == 0
        
        config = validation['configuration']
        assert config['uri'] == "ws://localhost:3000"
        assert config['module_name'] == "test_module"
        assert config['protocol'] == "binary"
        assert config['energy_budget'] == 15000
        assert config['callbacks_registered']['on_connect'] == 1
        assert config['callbacks_registered']['on_disconnect'] == 1
    
    @patch('src.spacetimedb_sdk.modern_client.ModernSpacetimeDBClient.__init__')
    def test_build_creates_client(self, mock_init):
        """Test that build() creates a client with correct parameters."""
        mock_init.return_value = None
        
        builder = (ModernSpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("test_module")
                  .with_protocol("binary")
                  .with_energy_budget(15000, 2000, 2000)
                  .with_auto_reconnect(True, 5))
        
        # Mock the client creation
        with patch('src.spacetimedb_sdk.connection_builder.ModernSpacetimeDBClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            client = builder.build()
            
            # Verify client was created with correct parameters
            mock_client_class.assert_called_once_with(
                autogen_package=None,
                protocol="binary",
                auto_reconnect=True,
                max_reconnect_attempts=5,
                start_message_processing=True,
                initial_energy=2000,
                max_energy=2000,
                energy_budget=15000
            )
            
            assert client == mock_client
    
    def test_build_missing_required_parameters(self):
        """Test that build() fails with missing required parameters."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Missing URI
        with pytest.raises(ValueError, match="URI is required"):
            builder.build()
        
        # Missing module name
        builder.with_uri("ws://localhost:3000")
        with pytest.raises(ValueError, match="Module name is required"):
            builder.build()
    
    @patch('src.spacetimedb_sdk.modern_client.ModernSpacetimeDBClient.__init__')
    def test_callback_registration_on_build(self, mock_init):
        """Test that callbacks are properly registered when building."""
        mock_init.return_value = None
        
        connect_callback = Mock()
        disconnect_callback = Mock()
        identity_callback = Mock()
        error_callback = Mock()
        
        builder = (ModernSpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("test_module")
                  .on_connect(connect_callback)
                  .on_disconnect(disconnect_callback)
                  .on_identity(identity_callback)
                  .on_error(error_callback))
        
        with patch('src.spacetimedb_sdk.connection_builder.ModernSpacetimeDBClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            client = builder.build()
            
            # Verify callbacks were registered
            mock_client.register_on_connect.assert_called_once_with(connect_callback)
            mock_client.register_on_disconnect.assert_called_once_with(disconnect_callback)
            mock_client.register_on_identity.assert_called_once_with(identity_callback)
            mock_client.register_on_error.assert_called_once_with(error_callback)
    
    @patch('src.spacetimedb_sdk.modern_client.ModernSpacetimeDBClient.__init__')
    def test_connect_method(self, mock_init):
        """Test the connect() convenience method."""
        mock_init.return_value = None
        
        builder = (ModernSpacetimeDBClient.builder()
                  .with_uri("wss://testnet.spacetimedb.com:443")
                  .with_module_name("test_module")
                  .with_token("auth_token"))
        
        with patch('src.spacetimedb_sdk.connection_builder.ModernSpacetimeDBClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            client = builder.connect()
            
            # Verify client was created and connect was called
            assert client == mock_client
            mock_client.connect.assert_called_once_with(
                auth_token="auth_token",
                host="testnet.spacetimedb.com:443",
                database_address="test_module",
                ssl_enabled=True
            )
    
    def test_typescript_sdk_compatibility_example(self):
        """Test that the API matches TypeScript SDK patterns."""
        # This should compile without errors and match TypeScript patterns
        builder = (ModernSpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("my_game")
                  .with_token("my_token")
                  .with_protocol("binary")
                  .on_connect(lambda: print("Connected to SpacetimeDB!"))
                  .on_disconnect(lambda reason: print(f"Disconnected: {reason}"))
                  .on_error(lambda error: print(f"Connection error: {error}"))
                  .with_energy_budget(10000, 2000, 2000)
                  .with_auto_reconnect(True, 3))
        
        # Should validate successfully
        validation = builder.validate()
        assert validation['valid']
        
        # Configuration should match what was set
        config = validation['configuration']
        assert config['uri'] == "ws://localhost:3000"
        assert config['module_name'] == "my_game"
        assert config['protocol'] == "binary"
        assert config['energy_budget'] == 10000
        assert config['auto_reconnect'] == True
        assert config['callbacks_registered']['on_connect'] == 1
        assert config['callbacks_registered']['on_disconnect'] == 1
        assert config['callbacks_registered']['on_error'] == 1


class TestBuilderErrorHandling:
    """Test error handling in the connection builder."""
    
    def test_multiple_callbacks_same_type(self):
        """Test that multiple callbacks of the same type can be registered."""
        builder = ModernSpacetimeDBClient.builder()
        
        callback1 = lambda: print("callback1")
        callback2 = lambda: print("callback2")
        
        builder.on_connect(callback1).on_connect(callback2)
        
        validation = builder.validate()
        assert validation['configuration']['callbacks_registered']['on_connect'] == 2
    
    def test_builder_reuse(self):
        """Test that builder instances can be reused and reconfigured."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Configure for first use
        builder.with_uri("ws://localhost:3000").with_module_name("module1")
        validation1 = builder.validate()
        assert validation1['configuration']['module_name'] == "module1"
        
        # Reconfigure for second use
        builder.with_module_name("module2")
        validation2 = builder.validate()
        assert validation2['configuration']['module_name'] == "module2"
    
    def test_empty_string_validation(self):
        """Test validation of empty strings."""
        builder = ModernSpacetimeDBClient.builder()
        
        # Empty strings should be rejected
        with pytest.raises(ValueError):
            builder.with_uri("")
        
        with pytest.raises(ValueError):
            builder.with_module_name("")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 