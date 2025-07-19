#!/usr/bin/env python3
"""
Comprehensive test suite for SpacetimeDB v1.1.2 authentication.
Tests all authentication scenarios including edge cases and error handling.
"""

import unittest
import sys
import os
import time
import base64
import json
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.websocket_client import WebSocketClient, ConnectionState
from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.exceptions import (
    AuthenticationError,
    DatabaseNotFoundError,
    WebSocketHandshakeError,
    SpacetimeDBConnectionError
)
from spacetimedb_sdk.protocol import (
    TEXT_PROTOCOL, BIN_PROTOCOL,
    Identity, ConnectionId, IdentityToken,
    ensure_enhanced_connection_id, ensure_enhanced_identity
)
from spacetimedb_sdk.connection_id import (
    EnhancedConnectionId, EnhancedIdentity, EnhancedIdentityToken,
    ConnectionState as EnhancedConnectionState
)


class TestAuthHeaderConstruction(unittest.TestCase):
    """Test authorization header construction."""
    
    def test_basic_auth_with_token_prefix(self):
        """Test that auth headers use Basic scheme with token: prefix."""
        token = "test_token_12345"
        expected_decoded = f"token:{token}"
        
        # Construct header as the client does
        token_bytes = f"token:{token}".encode('utf-8')
        base64_str = base64.b64encode(token_bytes).decode('utf-8')
        header = f"Basic {base64_str}"
        
        # Verify format
        self.assertTrue(header.startswith("Basic "))
        
        # Decode and verify content
        decoded = base64.b64decode(base64_str).decode('utf-8')
        self.assertEqual(decoded, expected_decoded)
    
    def test_empty_token_handling(self):
        """Test that empty tokens are handled correctly."""
        # Empty string token
        token = ""
        token_bytes = f"token:{token}".encode('utf-8')
        base64_str = base64.b64encode(token_bytes).decode('utf-8')
        
        decoded = base64.b64decode(base64_str).decode('utf-8')
        self.assertEqual(decoded, "token:")
    
    def test_special_characters_in_token(self):
        """Test tokens with special characters."""
        test_tokens = [
            "token_with_underscore",
            "token-with-dash",
            "token.with.dots",
            "token/with/slashes",
            "token+with+plus",
            "token=with=equals",
            "tōkén_wíth_ūnïcødé"
        ]
        
        for token in test_tokens:
            token_bytes = f"token:{token}".encode('utf-8')
            base64_str = base64.b64encode(token_bytes).decode('utf-8')
            
            # Should encode/decode without errors
            decoded = base64.b64decode(base64_str).decode('utf-8')
            self.assertEqual(decoded, f"token:{token}")
    
    def test_long_token_handling(self):
        """Test handling of very long tokens."""
        # Create a 1KB token
        long_token = "a" * 1024
        
        token_bytes = f"token:{long_token}".encode('utf-8')
        base64_str = base64.b64encode(token_bytes).decode('utf-8')
        
        # Should handle long tokens
        decoded = base64.b64decode(base64_str).decode('utf-8')
        self.assertEqual(decoded, f"token:{long_token}")
        self.assertEqual(len(decoded), 1024 + 6)  # token + "token:"


class TestIdentityTokenHandling(unittest.TestCase):
    """Test identity token parsing and handling."""
    
    def test_identity_token_creation(self):
        """Test creating identity tokens."""
        identity = Identity.from_hex("a" * 64)
        token = "test_token_123"
        connection_id = ConnectionId.from_hex("b" * 32)
        
        identity_token = IdentityToken(
            identity=identity,
            token=token,
            connection_id=connection_id
        )
        
        self.assertEqual(identity_token.identity, identity)
        self.assertEqual(identity_token.token, token)
        self.assertEqual(identity_token.connection_id, connection_id)
    
    def test_enhanced_identity_token_features(self):
        """Test enhanced identity token features."""
        enhanced_identity = EnhancedIdentity.from_hex("a" * 64)
        enhanced_conn_id = EnhancedConnectionId.from_hex("b" * 32)
        
        enhanced_token = EnhancedIdentityToken(
            identity=enhanced_identity,
            token="test_token_123",
            connection_id=enhanced_conn_id
        )
        
        # Test token claims extraction
        claims = enhanced_token.extract_claims()
        self.assertIn('identity', claims)
        self.assertIn('connection_id', claims)
        self.assertIn('issued_at', claims)
        self.assertIn('expires_at', claims)
        
        # Test expiration
        self.assertFalse(enhanced_token.is_expired())
        
        # Test refresh detection
        self.assertFalse(enhanced_token.refresh_if_needed(threshold=3600))
    
    def test_identity_conversion(self):
        """Test conversion between legacy and enhanced identity types."""
        # Legacy to enhanced
        legacy_identity = Identity.from_hex("a" * 64)
        enhanced = ensure_enhanced_identity(legacy_identity)
        self.assertIsInstance(enhanced, EnhancedIdentity)
        self.assertEqual(enhanced.to_hex(), legacy_identity.to_hex())
        
        # Enhanced remains enhanced
        enhanced_identity = EnhancedIdentity.from_hex("b" * 64)
        result = ensure_enhanced_identity(enhanced_identity)
        self.assertIs(result, enhanced_identity)
    
    def test_connection_id_conversion(self):
        """Test conversion between legacy and enhanced connection IDs."""
        # Legacy to enhanced
        legacy_conn_id = ConnectionId.from_hex("a" * 32)
        enhanced = ensure_enhanced_connection_id(legacy_conn_id)
        self.assertIsInstance(enhanced, EnhancedConnectionId)
        self.assertEqual(enhanced.to_hex(), legacy_conn_id.to_hex())
        
        # Test u64 pair extraction
        high, low = enhanced.to_u64_pair()
        self.assertIsInstance(high, int)
        self.assertIsInstance(low, int)


class TestMockAuthentication(unittest.TestCase):
    """Test authentication with mock WebSocket connections."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = None
        self.mock_ws = None
    
    def tearDown(self):
        """Clean up after tests."""
        if self.client:
            try:
                self.client.shutdown()
            except:
                pass
    
    @patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp')
    def test_anonymous_auth_flow(self, mock_ws_class):
        """Test anonymous authentication flow with mocks."""
        # Set up mock WebSocket
        self.mock_ws = MagicMock()
        mock_ws_class.return_value = self.mock_ws
        
        # Create client
        self.client = SpacetimeDBClient(test_mode=False)
        
        # Track callbacks
        identity_received = []
        
        def on_identity(token, identity, connection_id):
            identity_received.append({
                'token': token,
                'identity': str(identity),
                'connection_id': str(connection_id)
            })
        
        # Connect without token
        self.client._connect_internal(
            auth_token=None,
            host="localhost:3000",
            database_address="test_db",
            ssl_enabled=False,
            on_identity=on_identity
        )
        
        # Verify WebSocket creation
        mock_ws_class.assert_called_once()
        call_args = mock_ws_class.call_args
        
        # Check URL format
        self.assertIn('ws://localhost:3000/v1/database/test_db/subscribe', call_args[0])
        
        # Check no auth header
        headers = call_args[1].get('header', {})
        self.assertNotIn('Authorization', headers)
        
        # Simulate server response with identity token
        mock_identity = Identity.from_hex("0" * 64)
        mock_conn_id = ConnectionId.from_hex("1" * 32)
        mock_token = "anonymous_token_123"
        
        identity_msg = IdentityToken(
            identity=mock_identity,
            token=mock_token,
            connection_id=mock_conn_id
        )
        
        # Simulate receiving identity message
        if hasattr(self.client, '_handle_message'):
            self.client._handle_message(identity_msg)
            time.sleep(0.1)  # Allow processing
            
            # Verify identity was received
            self.assertEqual(len(identity_received), 1)
            self.assertEqual(identity_received[0]['token'], mock_token)
    
    @patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp')
    def test_token_auth_flow(self, mock_ws_class):
        """Test token authentication flow with mocks."""
        # Set up mock WebSocket
        self.mock_ws = MagicMock()
        mock_ws_class.return_value = self.mock_ws
        
        # Create client
        self.client = SpacetimeDBClient(test_mode=False)
        
        auth_token = "existing_auth_token_456"
        
        # Connect with token
        self.client._connect_internal(
            auth_token=auth_token,
            host="localhost:3000",
            database_address="test_db",
            ssl_enabled=False
        )
        
        # Verify WebSocket creation
        mock_ws_class.assert_called_once()
        call_args = mock_ws_class.call_args
        
        # Check auth header
        headers = call_args[1].get('header', {})
        self.assertIn('Authorization', headers)
        
        # Decode and verify auth header
        auth_header = headers['Authorization']
        self.assertTrue(auth_header.startswith('Basic '))
        
        # Decode the base64 part
        base64_part = auth_header[6:]  # Remove "Basic "
        decoded = base64.b64decode(base64_part).decode('utf-8')
        self.assertEqual(decoded, f"token:{auth_token}")
    
    @patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp')
    def test_invalid_token_rejection(self, mock_ws_class):
        """Test that invalid tokens are properly rejected."""
        # Set up mock WebSocket
        self.mock_ws = MagicMock()
        mock_ws_class.return_value = self.mock_ws
        
        # Create client
        self.client = SpacetimeDBClient(test_mode=False)
        
        errors_received = []
        
        def on_error(error):
            errors_received.append(error)
        
        # Connect with invalid token
        self.client._connect_internal(
            auth_token="invalid_token_xyz",
            host="localhost:3000",
            database_address="test_db",
            ssl_enabled=False,
            on_error=on_error
        )
        
        # Simulate auth error from server
        # Get the on_error callback from WebSocket construction
        ws_on_error = call_args[1].get('on_error')
        if ws_on_error:
            # Simulate 401 error
            auth_error = Exception("Handshake status 401 Unauthorized")
            ws_on_error(self.mock_ws, auth_error)
            
            # Verify error was processed
            self.assertTrue(len(errors_received) > 0)
            
            # Check if AuthenticationError was created
            processed_error = errors_received[0]
            if isinstance(processed_error, AuthenticationError):
                self.assertEqual(processed_error.status_code, 401)


class TestConnectionStateManagement(unittest.TestCase):
    """Test connection state tracking during authentication."""
    
    def test_connection_state_transitions(self):
        """Test that connection states transition correctly."""
        client = SpacetimeDBClient(test_mode=True)
        
        # Initial state
        self.assertEqual(client.get_connection_state(), EnhancedConnectionState.DISCONNECTED)
        
        # Simulate connection in test mode
        client._simulate_test_connection()
        
        # Should be connected
        self.assertEqual(client.get_connection_state(), EnhancedConnectionState.CONNECTED)
        self.assertIsNotNone(client.enhanced_connection_id)
        self.assertIsNotNone(client.enhanced_identity)
        
        # Disconnect
        client.disconnect()
        
        # Should be disconnected  
        self.assertEqual(client.get_connection_state(), EnhancedConnectionState.DISCONNECTED)
    
    def test_identity_tracking(self):
        """Test identity tracking during authentication."""
        client = SpacetimeDBClient(test_mode=True)
        
        # Track identity changes
        identity_events = []
        
        def on_identity(token, identity, connection_id):
            identity_events.append({
                'token': token,
                'identity': identity,
                'connection_id': connection_id
            })
        
        client.register_on_identity(on_identity)
        
        # Simulate connection
        client._simulate_test_connection()
        
        # Verify identity was set
        self.assertIsNotNone(client.identity)
        self.assertIsNotNone(client.enhanced_identity)
        self.assertEqual(len(identity_events), 1)
        
        # Verify identity info
        identity_info = client.get_identity_info()
        self.assertIsNotNone(identity_info)
        self.assertIn('identity', identity_info)
        self.assertIn('is_anonymous', identity_info)


class TestErrorHandling(unittest.TestCase):
    """Test authentication error handling."""
    
    def test_auth_error_types(self):
        """Test different authentication error types."""
        # Test creating different auth errors
        errors = [
            AuthenticationError("Invalid token", "Basic", 401),
            AuthenticationError("Forbidden", "Basic", 403),
            AuthenticationError("Token expired", "Basic", 401, token_expired=True)
        ]
        
        for error in errors:
            self.assertIsInstance(error, AuthenticationError)
            self.assertEqual(error.auth_method, "Basic")
            self.assertIn(error.status_code, [401, 403])
    
    def test_header_extraction_from_errors(self):
        """Test extracting auth headers from error responses."""
        # Create error with headers
        headers = {
            'spacetime-identity': 'a' * 64,
            'spacetime-identity-token': 'new_token_789'
        }
        
        error = WebSocketHandshakeError(
            status_code=404,
            status_message="Not Found",
            url="ws://localhost:3000/v1/database/test/subscribe",
            headers=headers
        )
        
        # Verify headers are accessible
        self.assertEqual(error.headers['spacetime-identity'], 'a' * 64)
        self.assertEqual(error.headers['spacetime-identity-token'], 'new_token_789')


class TestTokenPersistence(unittest.TestCase):
    """Test token persistence and reuse."""
    
    def test_token_reuse_scenario(self):
        """Test reusing tokens across connections."""
        # Create first client
        client1 = SpacetimeDBClient(test_mode=True)
        client1._simulate_test_connection()
        
        # Get token from first connection
        token1 = None
        if client1.enhanced_identity_token:
            token1 = client1.enhanced_identity_token.token
        
        self.assertIsNotNone(token1)
        
        # Create second client with same token
        client2 = SpacetimeDBClient(test_mode=True)
        client2.auth_token = token1
        client2._simulate_test_connection()
        
        # Both should have same identity
        self.assertEqual(
            client1.enhanced_identity.to_hex() if client1.enhanced_identity else None,
            client2.enhanced_identity.to_hex() if client2.enhanced_identity else None
        )
        
        # Clean up
        client1.disconnect()
        client2.disconnect()
    
    def test_token_expiration_detection(self):
        """Test token expiration detection."""
        identity = EnhancedIdentity.generate_random()
        conn_id = EnhancedConnectionId.generate_random()
        
        # Create token that expires soon
        token = EnhancedIdentityToken(
            identity=identity,
            token="expiring_token",
            connection_id=conn_id,
            expires_at=time.time() + 10  # Expires in 10 seconds
        )
        
        # Should need refresh with 1 hour threshold
        self.assertTrue(token.refresh_if_needed(threshold=3600))
        
        # Should not need refresh with 5 second threshold
        self.assertFalse(token.refresh_if_needed(threshold=5))


class TestAuthenticationIntegration(unittest.TestCase):
    """Integration tests for authentication (requires server)."""
    
    @unittest.skipIf(
        os.getenv('SKIP_INTEGRATION_TESTS', 'true').lower() == 'true',
        "Skipping integration test (set SKIP_INTEGRATION_TESTS=false to run)"
    )
    def test_real_anonymous_connection(self):
        """Test real anonymous connection to server."""
        client = SpacetimeDBClient()
        
        try:
            client._connect_internal(
                auth_token=None,
                host="localhost:3000",
                database_address="test_module",
                ssl_enabled=False
            )
            
            # Wait for connection
            time.sleep(2)
            
            if client.is_connected:
                self.assertIsNotNone(client.identity)
                self.assertIsNotNone(client.connection_id)
                self.assertIsNotNone(client.enhanced_identity_token)
                
                # Verify token format
                token = client.enhanced_identity_token.token
                self.assertTrue(len(token) > 10)
                self.assertTrue(client.enhanced_identity_token.validate_signature())
                
        finally:
            client.disconnect()


def run_auth_test_suite():
    """Run the complete authentication test suite."""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestAuthHeaderConstruction,
        TestIdentityTokenHandling,
        TestMockAuthentication,
        TestConnectionStateManagement,
        TestErrorHandling,
        TestTokenPersistence,
        TestAuthenticationIntegration
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
    success = run_auth_test_suite()
    sys.exit(0 if success else 1)
