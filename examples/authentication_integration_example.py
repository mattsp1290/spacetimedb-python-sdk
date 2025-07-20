#!/usr/bin/env python3
"""
Authentication Handler Integration Example

This example demonstrates how to integrate the new Authentication Handler
with the existing WebSocket client to provide secure credential management
and authentication state tracking.

Features demonstrated:
- Secure credential storage and retrieval
- Authentication state management
- Event-driven authentication notifications
- JWT token lifecycle management
- Integration with existing WebSocket client
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import os
import logging
import time
from typing import Optional

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk.connection.authentication_handler import (
    AuthenticationHandler,
    AuthenticationState,
    AuthenticationCredentials,
    AuthenticationEvent
)
from spacetimedb_sdk.events.enhanced_event_system import EventType


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketClientIntegration:
    """
    Example integration of Authentication Handler with WebSocket client.
    
    This demonstrates how to refactor the existing websocket_client.py to use
    the new authentication handler instead of managing auth state directly.
    """
    
    def __init__(self, host: str, database: str):
        """
        Initialize client with authentication handler.
        
        Args:
            host: Server host
            database: Database name
        """
        self.host = host
        self.database = database
        
        # Initialize authentication handler
        self.auth_handler = AuthenticationHandler(
            event_handler=self._on_auth_event,
            auto_refresh_tokens=True,
            token_refresh_threshold=300.0  # 5 minutes
        )
        
        # Connection state
        self.connected = False
        self.identity = None
        self.connection_id = None
        
        logger.info(f"Initialized WebSocket client for {host}/{database}")
    
    def _on_auth_event(self, event: AuthenticationEvent) -> None:
        """
        Handle authentication events.
        
        Args:
            event: Authentication event
        """
        logger.info(f"Authentication event: {event.get_event_name()}")
        
        if event.state == AuthenticationState.AUTHENTICATED:
            logger.info(f"Successfully authenticated with identity: {event.identity[:8]}...")
            self._schedule_reconnect_with_auth()
        elif event.state == AuthenticationState.FAILED:
            logger.error(f"Authentication failed: {event.error}")
        elif event.state == AuthenticationState.EXPIRED:
            logger.warning("Authentication expired, will attempt refresh")
            self._handle_auth_expiry()
    
    def _schedule_reconnect_with_auth(self) -> None:
        """Schedule reconnection with authentication."""
        logger.info("Scheduling reconnection with authentication...")
        # In real implementation, this would trigger WebSocket reconnection
        # with the new authentication headers
    
    def _handle_auth_expiry(self) -> None:
        """Handle authentication expiry."""
        logger.info("Handling authentication expiry...")
        # In real implementation, this would attempt to refresh tokens
        # or re-authenticate as needed
    
    def connect(self, auth_token: Optional[str] = None) -> bool:
        """
        Connect to SpacetimeDB with authentication.
        
        Args:
            auth_token: Legacy auth token (optional)
            
        Returns:
            True if connection successful
        """
        logger.info(f"Connecting to {self.host}/{self.database}...")
        
        # Check for stored credentials first
        stored_creds = self.auth_handler.get_stored_credentials(self.host, self.database)
        if stored_creds and not stored_creds.is_expired:
            logger.info("Using stored credentials for authentication")
            headers = self.auth_handler.prepare_jwt_headers(self.host, self.database)
            return self._connect_with_headers(headers)
        
        # Try legacy token authentication
        if auth_token:
            logger.info("Using legacy token authentication")
            headers = self.auth_handler.authenticate_with_legacy_token(
                auth_token, self.host, self.database
            )
            return self._connect_with_headers(headers)
        
        # Connect without authentication (will trigger handshake if needed)
        logger.info("Connecting without authentication")
        return self._connect_with_headers(None)
    
    def _connect_with_headers(self, headers: Optional[dict]) -> bool:
        """
        Connect with authentication headers.
        
        Args:
            headers: Authentication headers
            
        Returns:
            True if connection successful
        """
        try:
            # Simulate WebSocket connection
            logger.info("Establishing WebSocket connection...")
            
            # Simulate connection success
            self.connected = True
            self.identity = "simulated_identity"
            self.connection_id = "simulated_connection_id"
            
            logger.info("WebSocket connection established successfully")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            
            # Simulate authentication handshake error
            if "400" in str(e) and "spacetime-identity" in str(e):
                self._handle_auth_handshake_error(str(e))
            
            return False
    
    def _handle_auth_handshake_error(self, error_message: str) -> None:
        """
        Handle authentication handshake error.
        
        Args:
            error_message: Error message from WebSocket
        """
        logger.info("Handling authentication handshake...")
        
        # Use authentication handler to process the handshake
        if self.auth_handler.handle_authentication_handshake(
            error_message, self.host, self.database
        ):
            logger.info("Authentication handshake successful, retrying connection")
            # In real implementation, this would retry the WebSocket connection
            # with the new authentication headers
        else:
            logger.error("Authentication handshake failed")
    
    def disconnect(self) -> None:
        """Disconnect from SpacetimeDB."""
        if self.connected:
            logger.info("Disconnecting from SpacetimeDB...")
            self.connected = False
            self.identity = None
            self.connection_id = None
            logger.info("Disconnected successfully")
    
    def get_connection_info(self) -> dict:
        """Get connection information."""
        auth_info = self.auth_handler.get_authentication_info()
        
        return {
            "connected": self.connected,
            "host": self.host,
            "database": self.database,
            "identity": self.identity,
            "connection_id": self.connection_id,
            "authentication": auth_info
        }
    
    def clear_stored_credentials(self) -> None:
        """Clear stored credentials."""
        logger.info("Clearing stored credentials...")
        self.auth_handler.clear_credentials(self.host, self.database)
        logger.info("Stored credentials cleared")
    
    def shutdown(self) -> None:
        """Shutdown client and cleanup resources."""
        logger.info("Shutting down WebSocket client...")
        self.disconnect()
        self.auth_handler.shutdown()
        logger.info("Shutdown complete")


def demonstrate_authentication_flow():
    """Demonstrate the authentication flow."""
    print("=== Authentication Handler Integration Demo ===\n")
    
    # Initialize client
    client = WebSocketClientIntegration("localhost:3000", "testdb")
    
    print("1. Initial connection attempt (no auth)...")
    success = client.connect()
    if not success:
        print("   Connection failed as expected (no auth)")
    
    print("\n2. Simulating authentication handshake...")
    # Simulate receiving authentication handshake
    handshake_error = (
        "WebSocket handshake failed: HTTP 400 Bad Request. "
        "spacetime-identity: abcdef123456789 "
        "spacetime-identity-token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example.token"
    )
    
    client._handle_auth_handshake_error(handshake_error)
    
    print("\n3. Attempting connection with stored credentials...")
    success = client.connect()
    if success:
        print("   Connection successful with stored credentials!")
    
    print("\n4. Connection information:")
    info = client.get_connection_info()
    for key, value in info.items():
        if key == "authentication":
            print(f"   {key}:")
            for auth_key, auth_value in value.items():
                print(f"     {auth_key}: {auth_value}")
        else:
            print(f"   {key}: {value}")
    
    print("\n5. Clearing credentials...")
    client.clear_stored_credentials()
    
    print("\n6. Final authentication state:")
    auth_info = client.auth_handler.get_authentication_info()
    print(f"   State: {auth_info['state']}")
    print(f"   Retry count: {auth_info['retry_count']}")
    
    print("\n7. Shutting down...")
    client.shutdown()
    
    print("\n=== Demo Complete ===")


def demonstrate_legacy_token_auth():
    """Demonstrate legacy token authentication."""
    print("\n=== Legacy Token Authentication Demo ===\n")
    
    # Initialize client
    client = WebSocketClientIntegration("localhost:3000", "testdb")
    
    print("1. Connecting with legacy token...")
    success = client.connect(auth_token="legacy_token_123")
    if success:
        print("   Connection successful with legacy token!")
    
    print("\n2. Connection information:")
    info = client.get_connection_info()
    print(f"   Connected: {info['connected']}")
    print(f"   Identity: {info['identity']}")
    print(f"   Auth state: {info['authentication']['state']}")
    
    print("\n3. Shutting down...")
    client.shutdown()
    
    print("\n=== Legacy Demo Complete ===")


def demonstrate_event_integration():
    """Demonstrate event system integration."""
    print("\n=== Event Integration Demo ===\n")
    
    # Custom event handler
    events_received = []
    
    def custom_event_handler(event: AuthenticationEvent):
        events_received.append(event)
        print(f"   Event: {event.get_event_name()}")
        if event.identity:
            print(f"   Identity: {event.identity[:8]}...")
        if event.error:
            print(f"   Error: {event.error}")
    
    # Initialize authentication handler with custom event handler
    auth_handler = AuthenticationHandler(
        event_handler=custom_event_handler,
        auto_refresh_tokens=False
    )
    
    print("1. Storing credentials (should trigger events)...")
    auth_handler.store_credentials(
        "event_test_identity", "event_test_token", "localhost", "eventdb"
    )
    
    print("\n2. Attempting invalid handshake (should trigger error event)...")
    invalid_handshake = "Some invalid handshake without proper headers"
    auth_handler.handle_authentication_handshake(
        invalid_handshake, "localhost", "eventdb"
    )
    
    print("\n3. Clearing credentials (should trigger events)...")
    auth_handler.clear_credentials("localhost", "eventdb")
    
    print(f"\n4. Total events received: {len(events_received)}")
    for i, event in enumerate(events_received):
        print(f"   Event {i+1}: {event.get_event_name()}")
    
    print("\n5. Shutting down...")
    auth_handler.shutdown()
    
    print("\n=== Event Demo Complete ===")


if __name__ == "__main__":
    # Run all demonstrations
    demonstrate_authentication_flow()
    demonstrate_legacy_token_auth()
    demonstrate_event_integration()
    
    print("\n" + "="*50)
    print("Authentication Handler Integration Features:")
    print("• Secure credential storage with encryption")
    print("• Automatic JWT token lifecycle management")
    print("• Event-driven authentication notifications")
    print("• Legacy token authentication support")
    print("• Thread-safe operations")
    print("• Comprehensive error handling")
    print("• Integration with existing WebSocket client")
    print("• Authentication state tracking")
    print("• Automatic retry logic")
    print("• Security-focused credential handling")
    print("="*50)