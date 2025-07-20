"""
Authentication Handler Usage Examples for SpacetimeDB SDK

This example demonstrates how to use the authentication handler with WebSocket clients,
including JWT token management, automatic refresh, and integration patterns.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import logging
from typing import Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk.connection import (
    AuthenticationHandler,
    AuthenticationState,
    WebSocketAuthIntegration,
    WebSocketAuthConfig,
    WebSocketClientAuthMixin,
    create_websocket_auth_integration,
    integrate_auth_handler_with_websocket_client,
    get_auth_headers_for_connection,
    handle_websocket_auth_error,
    store_websocket_auth_credentials
)
from spacetimedb_sdk.exceptions import (
    AuthenticationError,
    SpacetimeDBAuthHandshakeError
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_basic_authentication_handler():
    """Example 1: Basic authentication handler usage."""
    print("\n=== Example 1: Basic Authentication Handler ===")
    
    # Create authentication handler
    handler = AuthenticationHandler()
    
    # Check initial state
    print(f"Initial state: {handler.get_authentication_state()}")
    
    # Store credentials
    handler.store_credentials(
        identity="user123456789abcdef",
        token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example.token",
        host="localhost:3000",
        database="my_game"
    )
    
    # Check state after storing credentials
    print(f"State after storing credentials: {handler.get_authentication_state()}")
    
    # Get stored credentials
    credentials = handler.get_stored_credentials("localhost:3000", "my_game")
    if credentials:
        print(f"Retrieved credentials for identity: {credentials.identity[:8]}...")
    
    # Prepare JWT headers
    headers = handler.prepare_jwt_headers("localhost:3000", "my_game")
    if headers:
        print(f"JWT headers prepared: {list(headers.keys())}")
    
    # Get comprehensive authentication info
    auth_info = handler.get_authentication_info()
    print(f"Authentication info: {auth_info}")
    
    # Cleanup
    handler.shutdown()


def example_2_websocket_auth_integration():
    """Example 2: WebSocket authentication integration."""
    print("\n=== Example 2: WebSocket Authentication Integration ===")
    
    # Create authentication handler with custom configuration
    handler = AuthenticationHandler(
        auto_refresh_tokens=True,
        token_refresh_threshold=300.0,  # 5 minutes
        max_retry_attempts=3
    )
    
    # Create WebSocket auth integration
    config = WebSocketAuthConfig(
        handshake_timeout=30.0,
        max_retry_attempts=3,
        auto_refresh_tokens=True,
        prefer_jwt_over_legacy=True
    )
    
    integration = WebSocketAuthIntegration(
        auth_handler=handler,
        config=config
    )
    
    # Prepare connection headers
    headers = integration.prepare_connection_headers(
        host="localhost:3000",
        database="my_game"
    )
    print(f"Connection headers: {headers}")
    
    # Handle authentication handshake
    handshake_message = (
        "Authentication required: "
        "spacetime-identity: abc123def456789 "
        "spacetime-identity-token: eyJhbGciOiJIUzI1NiJ9.example.token"
    )
    
    handshake_error = SpacetimeDBAuthHandshakeError(handshake_message)
    should_retry = integration.handle_authentication_error(
        handshake_error, "localhost:3000", "my_game", handshake_message
    )
    
    print(f"Should retry after handshake: {should_retry}")
    
    # Get authentication status
    status = integration.get_authentication_status()
    print(f"Authentication status: {status}")
    
    # Cleanup
    integration.shutdown()


def example_3_websocket_client_with_auth_mixin():
    """Example 3: WebSocket client with authentication mixin."""
    print("\n=== Example 3: WebSocket Client with Auth Mixin ===")
    
    # Mock WebSocket client
    class MockWebSocketClient:
        def __init__(self):
            self.logger = logger
            self.host = None
            self.database = None
            self.connected = False
        
        def connect(self, host: str, database: str):
            self.host = host
            self.database = database
            self.connected = True
            print(f"Connected to {host}/{database}")
        
        def reconnect(self):
            if self.host and self.database:
                print(f"Reconnecting to {self.host}/{self.database}")
                self.connect(self.host, self.database)
    
    # Create authentication-enabled client
    class AuthEnabledWebSocketClient(WebSocketClientAuthMixin, MockWebSocketClient):
        pass
    
    client = AuthEnabledWebSocketClient()
    
    # Connect with authentication
    client.connect("localhost:3000", "my_game")
    
    # Prepare authentication headers
    headers = client._prepare_auth_headers("localhost:3000", "my_game")
    print(f"Auth headers: {headers}")
    
    # Store credentials
    client._store_auth_credentials(
        identity="user987654321fedcba",
        token="eyJhbGciOiJIUzI1NiJ9.another.token",
        host="localhost:3000",
        database="my_game"
    )
    
    # Get authentication status
    status = client._get_auth_status()
    print(f"Client auth status: {status['state']}")
    
    # Get current identity
    identity = client._get_current_identity()
    print(f"Current identity: {identity[:8]}..." if identity else "No identity")


def example_4_integration_with_existing_client():
    """Example 4: Integration with existing WebSocket client."""
    print("\n=== Example 4: Integration with Existing Client ===")
    
    # Mock existing WebSocket client
    class ExistingWebSocketClient:
        def __init__(self):
            self.logger = logger
            self.host = None
            self.database = None
            self.identity = None
            self.spacetimedb_token = None
        
        def connect(self, host: str, database: str):
            self.host = host
            self.database = database
            print(f"Existing client connected to {host}/{database}")
        
        def reconnect(self):
            if self.host and self.database:
                self.connect(self.host, self.database)
    
    client = ExistingWebSocketClient()
    
    # Integrate authentication handler
    integration = integrate_auth_handler_with_websocket_client(client)
    
    # Use integrated authentication methods
    headers = client._prepare_auth_headers("localhost:3000", "my_game")
    print(f"Integrated auth headers: {headers}")
    
    # Store credentials through integration
    client._store_auth_credentials(
        identity="user111222333aaabbb",
        token="eyJhbGciOiJIUzI1NiJ9.integrated.token",
        host="localhost:3000",
        database="my_game"
    )
    
    # Get status through integration
    status = client._get_auth_status()
    print(f"Integrated auth status: {status['state']}")


def example_5_convenience_functions():
    """Example 5: Using convenience functions."""
    print("\n=== Example 5: Convenience Functions ===")
    
    # Store credentials using convenience function
    store_websocket_auth_credentials(
        identity="userconvenience123",
        token="eyJhbGciOiJIUzI1NiJ9.convenience.token",
        host="localhost:3000",
        database="my_game"
    )
    
    # Get auth headers using convenience function
    headers = get_auth_headers_for_connection("localhost:3000", "my_game")
    print(f"Convenience headers: {headers}")
    
    # Handle authentication error using convenience function
    auth_error = AuthenticationError("Invalid token")
    should_retry = handle_websocket_auth_error(
        auth_error, "localhost:3000", "my_game"
    )
    print(f"Should retry after error: {should_retry}")


def example_6_error_handling_and_retry():
    """Example 6: Error handling and retry logic."""
    print("\n=== Example 6: Error Handling and Retry ===")
    
    handler = AuthenticationHandler(max_retry_attempts=3)
    integration = WebSocketAuthIntegration(auth_handler=handler)
    
    # Simulate authentication errors
    errors = [
        AuthenticationError("Invalid credentials"),
        SpacetimeDBAuthHandshakeError("Handshake failed"),
        Exception("Network error")
    ]
    
    for i, error in enumerate(errors):
        print(f"\nHandling error {i+1}: {type(error).__name__}")
        
        should_retry = integration.handle_authentication_error(
            error, "localhost:3000", "my_game"
        )
        
        print(f"Should retry: {should_retry}")
        
        # Check retry count
        if hasattr(error, 'status_code'):
            can_retry = handler.should_retry_authentication(error.status_code)
        else:
            can_retry = handler.should_retry_authentication(401)
        
        print(f"Can retry: {can_retry}")


def example_7_token_refresh_and_lifecycle():
    """Example 7: Token refresh and lifecycle management."""
    print("\n=== Example 7: Token Refresh and Lifecycle ===")
    
    # Create handler with token refresh enabled
    handler = AuthenticationHandler(
        auto_refresh_tokens=True,
        token_refresh_threshold=5.0  # 5 seconds for demo
    )
    
    integration = WebSocketAuthIntegration(auth_handler=handler)
    
    # Set up refresh callback
    refresh_called = False
    
    def refresh_callback(credentials):
        nonlocal refresh_called
        refresh_called = True
        print(f"Token refresh callback called for identity: {credentials.identity[:8]}...")
    
    handler.add_refresh_callback(refresh_callback)
    
    # Store credentials with short expiry
    handler.store_credentials(
        identity="userrefresh123456",
        token="eyJhbGciOiJIUzI1NiJ9.refresh.token",
        host="localhost:3000",
        database="my_game"
    )
    
    # Get current credentials
    credentials = handler.get_current_credentials()
    if credentials:
        print(f"Stored credentials for: {credentials.identity[:8]}...")
        print(f"Time until expiry: {credentials.time_until_expiry:.1f} seconds")
    
    # Simulate token refresh (in real scenario, this would be automatic)
    if credentials:
        handler._refresh_token_background(credentials)
        print(f"Refresh callback called: {refresh_called}")
    
    # Cleanup
    handler.remove_refresh_callback(refresh_callback)
    handler.shutdown()


def main():
    """Run all examples."""
    print("SpacetimeDB Authentication Handler Examples")
    print("=" * 50)
    
    try:
        example_1_basic_authentication_handler()
        example_2_websocket_auth_integration()
        example_3_websocket_client_with_auth_mixin()
        example_4_integration_with_existing_client()
        example_5_convenience_functions()
        example_6_error_handling_and_retry()
        example_7_token_refresh_and_lifecycle()
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()