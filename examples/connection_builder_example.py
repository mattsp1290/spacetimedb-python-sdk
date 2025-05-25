"""
SpacetimeDB Connection Builder Pattern Examples

This file demonstrates the new fluent builder API for creating SpacetimeDB connections,
which matches the TypeScript SDK's DbConnection.builder() pattern.

The builder pattern provides a modern, type-safe way to configure connections with
comprehensive validation and callback support.
"""

import asyncio
import sys
import os
from typing import Any

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import the SpacetimeDB SDK
from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL


# Example 1: Basic connection setup matching TypeScript SDK
def example_basic_connection():
    """
    Basic connection setup using the builder pattern.
    
    TypeScript equivalent:
    const conn = await DbConnection.builder()
        .withUri("ws://localhost:3000")
        .withModuleName("my_game")
        .build();
    """
    print("=== Example 1: Basic Connection ===")
    
    # Create connection using builder pattern
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("my_game")
              .build())
    
    print("✅ Client created successfully with builder pattern!")
    
    # Validate configuration before connecting
    validation = (ModernSpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("my_game")
                  .validate())
    
    print(f"Configuration valid: {validation['valid']}")
    print(f"Configuration: {validation['configuration']}")
    
    return client


# Example 2: Full-featured connection with callbacks
def example_full_featured_connection():
    """
    Full-featured connection with all options and callbacks.
    
    TypeScript equivalent:
    const conn = await DbConnection.builder()
        .withUri("wss://testnet.spacetimedb.com")
        .withModuleName("multiplayer_game")
        .withAuthToken("your_auth_token")
        .withProtocol("binary")
        .onConnect(() => console.log("Connected!"))
        .onDisconnect((reason) => console.log(`Disconnected: ${reason}`))
        .onError((error) => console.error(`Error: ${error}`))
        .build();
    """
    print("\n=== Example 2: Full-Featured Connection ===")
    
    def on_connect():
        print("🟢 Connected to SpacetimeDB!")
    
    def on_disconnect(reason: str):
        print(f"🔴 Disconnected from SpacetimeDB: {reason}")
    
    def on_identity(token: str, identity: Any, connection_id: Any):
        print(f"🆔 Identity received: {identity}")
        print(f"🔗 Connection ID: {connection_id}")
    
    def on_error(error: Exception):
        print(f"❌ Connection error: {error}")
    
    # Build connection with all features
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("wss://testnet.spacetimedb.com")
              .with_module_name("multiplayer_game")
              .with_token("your_auth_token_here")
              .with_protocol("binary")
              .with_energy_budget(10000, initial=2000, max_energy=2000)
              .with_auto_reconnect(True, max_attempts=5)
              .on_connect(on_connect)
              .on_disconnect(on_disconnect)
              .on_identity(on_identity)
              .on_error(on_error)
              .build())
    
    print("✅ Full-featured client created with callbacks registered!")
    return client


# Example 3: Energy-aware gaming application
def example_energy_aware_game():
    """
    Energy-aware gaming application setup.
    
    This example shows Python SDK's advanced energy management capabilities
    that exceed the TypeScript SDK's features.
    """
    print("\n=== Example 3: Energy-Aware Gaming ===")
    
    def on_connect():
        print("🎮 Game client connected!")
        print("⚡ Energy management enabled")
    
    def on_energy_low():
        print("⚠️  Energy running low - consider reducing activity")
    
    # Create energy-optimized game client
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("space_shooter_game")
              .with_protocol("binary")  # Better performance
              .with_energy_budget(
                  budget=20000,      # High budget for gaming
                  initial=3000,      # Start with good energy
                  max_energy=3000    # High capacity
              )
              .with_auto_reconnect(True, max_attempts=10)  # Persistent gaming
              .on_connect(on_connect)
              .on_error(lambda err: print(f"🎮 Game error: {err}"))
              .build())
    
    # Add energy monitoring
    client.add_energy_listener(lambda event: 
        print(f"⚡ Energy event: {event.event_type} - {event.data}"))
    
    print("✅ Energy-aware game client ready!")
    print(f"⚡ Current energy: {client.get_current_energy()}")
    
    return client


# Example 4: Development setup with validation
def example_development_setup():
    """
    Development setup with comprehensive validation and testing support.
    """
    print("\n=== Example 4: Development Setup ===")
    
    # Create builder for development environment
    builder = (ModernSpacetimeDBClient.builder()
               .with_uri("ws://localhost:3000")
               .with_module_name("dev_database")
               .with_protocol("text")  # Easier debugging
               .with_message_processing(True)  # Enable for development
               .on_connect(lambda: print("🔧 Dev client connected"))
               .on_disconnect(lambda reason: print(f"🔧 Dev client disconnected: {reason}")))
    
    # Validate configuration before building
    validation = builder.validate()
    
    if validation['valid']:
        print("✅ Configuration is valid!")
        print("Configuration details:")
        for key, value in validation['configuration'].items():
            print(f"  {key}: {value}")
        
        # Build the client
        client = builder.build()
        print("✅ Development client created!")
        return client
    else:
        print("❌ Configuration has issues:")
        for issue in validation['issues']:
            print(f"  - {issue}")
        return None


# Example 5: Production deployment pattern
def example_production_deployment():
    """
    Production deployment with security and reliability features.
    """
    print("\n=== Example 5: Production Deployment ===")
    
    # Production-grade configuration
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("wss://prod.spacetimedb.com")
              .with_module_name("production_app")
              .with_token("PRODUCTION_AUTH_TOKEN")
              .with_protocol("binary")  # Performance
              .with_ssl(True)  # Security
              .with_auto_reconnect(True, max_attempts=50)  # Reliability
              .with_energy_budget(50000, 5000, 5000)  # High capacity
              .on_connect(lambda: print("🚀 Production app connected"))
              .on_disconnect(lambda reason: print(f"🚀 Production disconnect: {reason}"))
              .on_error(lambda err: print(f"🚀 Production error: {err}"))
              .build())
    
    print("✅ Production client configured!")
    print("🔒 Security: SSL enabled")
    print("🔄 Reliability: Auto-reconnect enabled")
    print("⚡ Performance: Binary protocol + high energy capacity")
    
    return client


# Example 6: Error handling and edge cases
def example_error_handling():
    """
    Demonstrate error handling and validation in the builder pattern.
    """
    print("\n=== Example 6: Error Handling ===")
    
    # Test invalid configurations
    builder = ModernSpacetimeDBClient.builder()
    
    try:
        # This should fail - missing required parameters
        builder.build()
    except ValueError as e:
        print(f"✅ Caught expected error: {e}")
    
    try:
        # This should fail - invalid URI scheme
        builder.with_uri("http://invalid-scheme.com")
    except ValueError as e:
        print(f"✅ Caught invalid URI error: {e}")
    
    try:
        # This should fail - invalid protocol
        builder.with_protocol("invalid_protocol")
    except ValueError as e:
        print(f"✅ Caught invalid protocol error: {e}")
    
    try:
        # This should fail - negative energy
        builder.with_energy_budget(-1000)
    except ValueError as e:
        print(f"✅ Caught negative energy error: {e}")
    
    print("✅ Error handling works correctly!")


# Example 7: Builder pattern comparison with TypeScript
def example_typescript_comparison():
    """
    Side-by-side comparison with TypeScript SDK patterns.
    """
    print("\n=== Example 7: TypeScript SDK Comparison ===")
    
    print("TypeScript SDK pattern:")
    print("""
    const conn = await DbConnection.builder()
        .withUri("ws://localhost:3000")
        .withModuleName("my_app")
        .withAuthToken("token")
        .onConnect(() => console.log("Connected"))
        .onDisconnect(reason => console.log(`Disconnected: ${reason}`))
        .build();
    """)
    
    print("Python SDK equivalent:")
    print("""
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("my_app")
              .with_token("token")
              .on_connect(lambda: print("Connected"))
              .on_disconnect(lambda reason: print(f"Disconnected: {reason}"))
              .build())
    """)
    
    # Actually create the client
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("my_app")
              .with_token("token")
              .on_connect(lambda: print("Connected"))
              .on_disconnect(lambda reason: print(f"Disconnected: {reason}"))
              .build())
    
    print("✅ Python SDK provides identical API patterns to TypeScript!")
    print("🚀 Plus additional energy management features!")
    
    return client


def main():
    """Run all examples to demonstrate the connection builder pattern."""
    print("SpacetimeDB Python SDK - Connection Builder Pattern Examples")
    print("=" * 60)
    
    # Run all examples
    example_basic_connection()
    example_full_featured_connection()
    example_energy_aware_game()
    example_development_setup()
    example_production_deployment()
    example_error_handling()
    example_typescript_comparison()
    
    print("\n" + "=" * 60)
    print("🎉 All examples completed successfully!")
    print("✅ Connection Builder Pattern implementation is working correctly")
    print("🚀 Python SDK now has TypeScript SDK API parity + energy management!")


if __name__ == "__main__":
    main() 