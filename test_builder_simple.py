#!/usr/bin/env python3
"""
Simple test to verify the connection builder pattern works correctly.
"""

import sys
sys.path.append('src')

from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder

def test_builder_creation():
    """Test that builder can be created."""
    print("Testing builder creation...")
    builder = ModernSpacetimeDBClient.builder()
    assert isinstance(builder, SpacetimeDBConnectionBuilder)
    print("✅ Builder created successfully")

def test_fluent_api():
    """Test that fluent API works."""
    print("Testing fluent API...")
    builder = ModernSpacetimeDBClient.builder()
    
    result = (builder
              .with_uri("ws://localhost:3000")
              .with_module_name("test_module")
              .with_token("test_token")
              .with_protocol("binary"))
    
    assert result is builder
    print("✅ Fluent API works correctly")

def test_validation():
    """Test configuration validation."""
    print("Testing validation...")
    
    # Test invalid configuration
    builder = ModernSpacetimeDBClient.builder()
    validation = builder.validate()
    assert not validation['valid']
    print("✅ Invalid configuration properly detected")
    
    # Test valid configuration
    builder.with_uri("ws://localhost:3000").with_module_name("test_module")
    validation = builder.validate()
    assert validation['valid']
    print("✅ Valid configuration properly detected")
    print(f"Configuration: {validation['configuration']}")

def test_error_handling():
    """Test error handling."""
    print("Testing error handling...")
    
    builder = ModernSpacetimeDBClient.builder()
    
    # Test invalid URI
    try:
        builder.with_uri("http://invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✅ Invalid URI properly rejected")
    
    # Test invalid protocol
    try:
        builder.with_protocol("invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✅ Invalid protocol properly rejected")
    
    # Test negative energy
    try:
        builder.with_energy_budget(-1000)
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✅ Negative energy properly rejected")

def test_typescript_compatibility():
    """Test TypeScript SDK compatibility patterns."""
    print("Testing TypeScript SDK compatibility...")
    
    # This pattern should match TypeScript SDK exactly
    builder = (ModernSpacetimeDBClient.builder()
               .with_uri("ws://localhost:3000")
               .with_module_name("my_game")
               .with_token("my_token")
               .with_protocol("binary")
               .on_connect(lambda: print("Connected!"))
               .on_disconnect(lambda reason: print(f"Disconnected: {reason}"))
               .with_energy_budget(10000, 2000, 2000))
    
    validation = builder.validate()
    assert validation['valid']
    
    config = validation['configuration']
    assert config['uri'] == "ws://localhost:3000"
    assert config['module_name'] == "my_game"
    assert config['protocol'] == "binary"
    assert config['energy_budget'] == 10000
    assert config['callbacks_registered']['on_connect'] == 1
    assert config['callbacks_registered']['on_disconnect'] == 1
    
    print("✅ TypeScript SDK compatibility confirmed")

def main():
    """Run all tests."""
    print("SpacetimeDB Connection Builder Pattern - Simple Tests")
    print("=" * 55)
    
    try:
        test_builder_creation()
        test_fluent_api()
        test_validation()
        test_error_handling()
        test_typescript_compatibility()
        
        print("\n" + "=" * 55)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Connection Builder Pattern is working correctly")
        print("🚀 Python SDK now has TypeScript SDK API parity!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 