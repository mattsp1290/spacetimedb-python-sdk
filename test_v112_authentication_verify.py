#!/usr/bin/env python3
"""
Initial verification script for v1.1.2 authentication testing.
Tests the current authentication implementation to establish a baseline.
"""

import sys
import os
import time
import logging
import base64

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.websocket_client import WebSocketClient
from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.exceptions import (
    AuthenticationError,
    DatabaseNotFoundError,
    SpacetimeDBConnectionError
)
from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_auth_header_construction():
    """Test how auth headers are constructed."""
    print("\n=== Testing Auth Header Construction ===")
    
    test_tokens = [
        ("test_token_123", "Basic authentication with test token"),
        ("", "Empty token"),
        (None, "None token"),
        ("bearer:some_jwt_token", "Token with bearer prefix"),
        ("a" * 100, "Long token")
    ]
    
    for token, description in test_tokens:
        print(f"\nTest: {description}")
        print(f"Token: {token}")
        
        if token:
            # Replicate the header construction logic
            token_bytes = f"token:{token}".encode('utf-8')
            base64_str = base64.b64encode(token_bytes).decode('utf-8')
            header = f"Basic {base64_str}"
            print(f"Authorization header: {header}")
            
            # Decode to verify
            decoded = base64.b64decode(base64_str).decode('utf-8')
            print(f"Decoded: {decoded}")
        else:
            print("No authorization header would be sent")


def test_anonymous_connection():
    """Test anonymous connection (no auth token)."""
    print("\n=== Testing Anonymous Connection ===")
    
    client = None
    try:
        client = SpacetimeDBClient(test_mode=False)
        
        # Track connection events
        connection_events = []
        identity_received = []
        
        def on_connect():
            connection_events.append("connected")
            logger.info("Connected successfully (anonymous)")
        
        def on_disconnect(reason):
            connection_events.append(f"disconnected: {reason}")
            logger.info(f"Disconnected: {reason}")
        
        def on_identity(token, identity, connection_id):
            identity_info = {
                'token': token,
                'identity': str(identity),
                'connection_id': str(connection_id)
            }
            identity_received.append(identity_info)
            logger.info(f"Received identity: {identity_info}")
        
        def on_error(error):
            logger.error(f"Connection error: {error}")
            connection_events.append(f"error: {error}")
        
        # Connect without auth token
        client._connect_internal(
            auth_token=None,  # Anonymous
            host="localhost:3000",
            database_address="test_module",  # Use a test database
            ssl_enabled=False,
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            on_identity=on_identity,
            on_error=on_error
        )
        
        # Wait for connection
        time.sleep(3)
        
        print(f"\nConnection events: {connection_events}")
        print(f"Identity received: {identity_received}")
        
        if client.is_connected:
            print("✓ Anonymous connection successful")
            print(f"  Identity: {client.identity}")
            print(f"  Connection ID: {client.connection_id}")
            if client.enhanced_identity_token:
                print(f"  Token received: {len(client.enhanced_identity_token.token)} chars")
        else:
            print("✗ Anonymous connection failed")
            
    except Exception as e:
        print(f"✗ Anonymous connection error: {e}")
        logger.exception("Anonymous connection failed")
    finally:
        if client:
            client.disconnect()
            time.sleep(1)


def test_token_authentication():
    """Test authentication with a token."""
    print("\n=== Testing Token Authentication ===")
    
    # First, get a token from anonymous connection
    anonymous_client = None
    auth_token = None
    
    try:
        print("Step 1: Getting token from anonymous connection...")
        anonymous_client = SpacetimeDBClient(test_mode=False)
        
        token_received = []
        
        def on_identity(token, identity, connection_id):
            token_received.append(token)
            logger.info(f"Received token: {token[:20]}..." if len(token) > 20 else token)
        
        anonymous_client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test_module",
            ssl_enabled=False,
            on_identity=on_identity
        )
        
        # Wait for identity token
        time.sleep(3)
        
        if token_received:
            auth_token = token_received[0]
            print(f"✓ Received auth token: {auth_token[:20]}..." if len(auth_token) > 20 else auth_token)
        else:
            print("✗ No token received from anonymous connection")
            return
            
    except Exception as e:
        print(f"✗ Failed to get token: {e}")
        return
    finally:
        if anonymous_client:
            anonymous_client.disconnect()
            time.sleep(1)
    
    # Now test with the token
    if auth_token:
        print("\nStep 2: Testing connection with received token...")
        
        auth_client = None
        try:
            auth_client = SpacetimeDBClient(test_mode=False)
            
            connection_events = []
            identity_info = []
            
            def on_connect():
                connection_events.append("connected")
                logger.info("Connected with auth token")
            
            def on_identity(token, identity, connection_id):
                identity_info.append({
                    'token': token,
                    'identity': str(identity),
                    'connection_id': str(connection_id)
                })
                logger.info(f"Identity confirmed: {identity}")
            
            def on_error(error):
                connection_events.append(f"error: {error}")
                logger.error(f"Auth error: {error}")
            
            auth_client._connect_internal(
                auth_token=auth_token,
                host="localhost:3000",
                database_address="test_module",
                ssl_enabled=False,
                on_connect=on_connect,
                on_identity=on_identity,
                on_error=on_error
            )
            
            # Wait for connection
            time.sleep(3)
            
            print(f"\nConnection events: {connection_events}")
            print(f"Identity info: {identity_info}")
            
            if auth_client.is_connected:
                print("✓ Token authentication successful")
                print(f"  Identity: {auth_client.identity}")
                print(f"  Same token returned: {identity_info[0]['token'] == auth_token if identity_info else 'N/A'}")
            else:
                print("✗ Token authentication failed")
                
        except AuthenticationError as e:
            print(f"✗ Authentication error: {e}")
        except Exception as e:
            print(f"✗ Connection error: {e}")
            logger.exception("Token authentication failed")
        finally:
            if auth_client:
                auth_client.disconnect()
                time.sleep(1)


def test_invalid_token():
    """Test authentication with an invalid token."""
    print("\n=== Testing Invalid Token ===")
    
    client = None
    try:
        client = SpacetimeDBClient(test_mode=False)
        
        errors_received = []
        
        def on_error(error):
            errors_received.append(error)
            logger.error(f"Expected auth error: {error}")
        
        # Try with obviously invalid token
        client._connect_internal(
            auth_token="invalid_token_12345",
            host="localhost:3000",
            database_address="test_module",
            ssl_enabled=False,
            on_error=on_error
        )
        
        # Wait for error
        time.sleep(3)
        
        if errors_received:
            print("✓ Invalid token properly rejected")
            for error in errors_received:
                print(f"  Error: {error}")
                if isinstance(error, AuthenticationError):
                    print(f"  Auth method: {error.auth_method}")
                    print(f"  Status code: {error.status_code}")
        else:
            if client.is_connected:
                print("✗ Invalid token was accepted (unexpected)")
            else:
                print("✗ Connection failed but no specific auth error")
                
    except Exception as e:
        print(f"✓ Invalid token rejected with exception: {e}")
    finally:
        if client:
            client.disconnect()
            time.sleep(1)


def test_header_extraction_from_errors():
    """Test extraction of auth headers from error responses."""
    print("\n=== Testing Header Extraction from Errors ===")
    
    # This tests the error handling that extracts spacetime-identity headers
    client = None
    try:
        client = SpacetimeDBClient(test_mode=False)
        
        errors_with_headers = []
        
        def on_error(error):
            errors_with_headers.append(error)
            if hasattr(error, 'diagnostic_info'):
                logger.info(f"Error diagnostic info: {error.diagnostic_info}")
        
        # Try to connect to non-existent database
        client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="non_existent_database_xyz",
            ssl_enabled=False,
            on_error=on_error
        )
        
        # Wait for error
        time.sleep(3)
        
        if errors_with_headers:
            print("✓ Received errors, checking for headers...")
            for error in errors_with_headers:
                print(f"\nError type: {type(error).__name__}")
                print(f"Error message: {error}")
                
                if isinstance(error, DatabaseNotFoundError) and hasattr(error, 'diagnostic_info'):
                    headers = error.diagnostic_info.get('headers', {})
                    if headers:
                        print("  Headers found:")
                        for key, value in headers.items():
                            print(f"    {key}: {value}")
                    else:
                        print("  No headers in diagnostic info")
                        
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        if client:
            client.disconnect()
            time.sleep(1)


def main():
    """Run all authentication verification tests."""
    print("=" * 80)
    print("SpacetimeDB v1.1.2 Authentication Verification")
    print("=" * 80)
    
    # Test header construction
    test_auth_header_construction()
    
    # Test connections
    print("\n" + "=" * 80)
    print("Testing actual connections (requires SpacetimeDB server on localhost:3000)")
    print("=" * 80)
    
    try:
        test_anonymous_connection()
        test_token_authentication()
        test_invalid_token()
        test_header_extraction_from_errors()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    
    print("\n" + "=" * 80)
    print("Verification Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
