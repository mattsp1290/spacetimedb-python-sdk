"""
Isolated tests for the authentication handler module

These tests will validate the authentication handler functionality 
that will be extracted from websocket_client.py during Phase 2 refactoring.
"""
import pytest
import time
import json
import uuid
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional, List, Callable

from spacetimedb_sdk.protocol import Identity, ConnectionId, IdentityToken
from spacetimedb_sdk.exceptions import (
    AuthenticationError,
    SpacetimeDBAuthHandshakeError,
    WebSocketHandshakeError
)
from spacetimedb_sdk.auth_storage import AuthCredentials, get_credentials, store_credentials


class MockAuthenticationHandler:
    """Mock authentication handler to test the interface that will be extracted"""
    
    def __init__(self):
        self.identity: Optional[Identity] = None
        self.connection_id: Optional[ConnectionId] = None
        self.auth_token: Optional[str] = None
        self.identity_token: Optional[str] = None
        self.auth_status: str = "unauthenticated"
        self.auth_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        self.state_callbacks: List[Callable] = []
        self.credentials_store: Dict[str, AuthCredentials] = {}
        self.handshake_timeout: float = 30.0
        self.retry_count: int = 0
        self.max_retries: int = 3
        self.last_auth_attempt: Optional[float] = None
        self.auth_lock = threading.Lock()
        
    def set_auth_token(self, token: str) -> None:
        """Set authentication token"""
        self.auth_token = token
        
    def clear_auth_token(self) -> None:
        """Clear authentication token"""
        self.auth_token = None
        
    def authenticate(self, token: Optional[str] = None) -> bool:
        """Authenticate with the server"""
        with self.auth_lock:
            if token:
                self.auth_token = token
                
            if not self.auth_token:
                self._notify_auth_error("No authentication token provided")
                return False
                
            self.last_auth_attempt = time.time()
            self.auth_status = "authenticating"
            self._notify_auth_state_change("authenticating")
            
            # Simulate authentication process
            # In real implementation, this would send auth message to server
            return True
            
    def handle_identity_token(self, identity_token_msg: IdentityToken) -> bool:
        """Handle identity token message from server"""
        try:
            self.identity_token = identity_token_msg.token
            self.identity = identity_token_msg.identity
            self.connection_id = identity_token_msg.connection_id
            
            # Store credentials
            if self.auth_token:
                credentials = AuthCredentials(
                    identity=str(self.identity),
                    token=self.auth_token,
                    host="localhost:3000",
                    database="test_db"
                )
                self.credentials_store[str(self.identity)] = credentials
                
            self.auth_status = "authenticated"
            self.retry_count = 0
            
            self._notify_auth_success(
                self.identity_token,
                self.identity,
                self.connection_id
            )
            
            self._notify_auth_state_change("authenticated")
            return True
            
        except Exception as e:
            self._notify_auth_error(f"Failed to handle identity token: {e}")
            return False
            
    def handle_auth_error(self, error: str) -> None:
        """Handle authentication error"""
        self.auth_status = "error"
        self.retry_count += 1
        
        self._notify_auth_error(error)
        self._notify_auth_state_change("error")
        
        # Attempt retry if not exceeded max retries
        if self.retry_count < self.max_retries:
            self._schedule_retry()
            
    def _schedule_retry(self) -> None:
        """Schedule authentication retry"""
        def retry_auth():
            time.sleep(2 ** self.retry_count)  # Exponential backoff
            if self.retry_count < self.max_retries:
                self.authenticate()
                
        threading.Thread(target=retry_auth, daemon=True).start()
        
    def clear_identity(self) -> None:
        """Clear identity information"""
        with self.auth_lock:
            self.identity = None
            self.connection_id = None
            self.identity_token = None
            self.auth_status = "unauthenticated"
            self.retry_count = 0
            self.last_auth_attempt = None
            
        self._notify_auth_state_change("unauthenticated")
        
    def get_auth_status(self) -> str:
        """Get current authentication status"""
        return self.auth_status
        
    def is_authenticated(self) -> bool:
        """Check if currently authenticated"""
        return self.auth_status == "authenticated" and self.identity is not None
        
    def get_identity(self) -> Optional[Identity]:
        """Get current identity"""
        return self.identity
        
    def get_connection_id(self) -> Optional[ConnectionId]:
        """Get current connection ID"""
        return self.connection_id
        
    def get_identity_token(self) -> Optional[str]:
        """Get current identity token"""
        return self.identity_token
        
    def add_auth_callback(self, callback: Callable) -> None:
        """Add authentication success callback"""
        self.auth_callbacks.append(callback)
        
    def remove_auth_callback(self, callback: Callable) -> bool:
        """Remove authentication success callback"""
        try:
            self.auth_callbacks.remove(callback)
            return True
        except ValueError:
            return False
            
    def add_error_callback(self, callback: Callable) -> None:
        """Add authentication error callback"""
        self.error_callbacks.append(callback)
        
    def remove_error_callback(self, callback: Callable) -> bool:
        """Remove authentication error callback"""
        try:
            self.error_callbacks.remove(callback)
            return True
        except ValueError:
            return False
            
    def add_state_callback(self, callback: Callable) -> None:
        """Add authentication state change callback"""
        self.state_callbacks.append(callback)
        
    def remove_state_callback(self, callback: Callable) -> bool:
        """Remove authentication state change callback"""
        try:
            self.state_callbacks.remove(callback)
            return True
        except ValueError:
            return False
            
    def _notify_auth_success(self, token: str, identity: Identity, connection_id: ConnectionId) -> None:
        """Notify authentication success"""
        for callback in self.auth_callbacks:
            try:
                callback(token, identity, connection_id)
            except Exception as e:
                print(f"Auth callback error: {e}")
                
    def _notify_auth_error(self, error: str) -> None:
        """Notify authentication error"""
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                print(f"Auth error callback error: {e}")
                
    def _notify_auth_state_change(self, state: str) -> None:
        """Notify authentication state change"""
        for callback in self.state_callbacks:
            try:
                callback(state)
            except Exception as e:
                print(f"Auth state callback error: {e}")
                
    def get_stored_credentials(self, identity: str) -> Optional[AuthCredentials]:
        """Get stored credentials for identity"""
        return self.credentials_store.get(identity)
        
    def store_credentials(self, identity: str, credentials: AuthCredentials) -> None:
        """Store credentials for identity"""
        self.credentials_store[identity] = credentials
        
    def clear_stored_credentials(self, identity: str) -> bool:
        """Clear stored credentials for identity"""
        if identity in self.credentials_store:
            del self.credentials_store[identity]
            return True
        return False
        
    def validate_token(self, token: str) -> bool:
        """Validate authentication token format"""
        if not token or not isinstance(token, str):
            return False
            
        # Basic token validation (format checks)
        if len(token) < 10:  # Minimum length
            return False
            
        # Check for valid characters (simplified)
        return all(c.isalnum() or c in '-_.' for c in token)
        
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {}
        
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
            
        if self.identity:
            headers['X-SpacetimeDB-Identity'] = str(self.identity)
            
        if self.connection_id:
            headers['X-SpacetimeDB-Connection-ID'] = str(self.connection_id)
            
        return headers
        
    def is_token_expired(self) -> bool:
        """Check if authentication token is expired"""
        if not self.last_auth_attempt:
            return False
            
        # Simple expiration check (1 hour)
        return time.time() - self.last_auth_attempt > 3600
        
    def refresh_authentication(self) -> bool:
        """Refresh authentication if needed"""
        # If no token, can't authenticate
        if not self.auth_token:
            return False
            
        if self.is_token_expired():
            self.clear_identity()
            return self.authenticate()
        return True


class TestAuthenticationHandler:
    """Test authentication handler functionality"""
    
    def test_authentication_handler_initialization(self):
        """Test authentication handler initialization"""
        handler = MockAuthenticationHandler()
        
        assert handler.identity is None
        assert handler.connection_id is None
        assert handler.auth_token is None
        assert handler.identity_token is None
        assert handler.auth_status == "unauthenticated"
        assert handler.retry_count == 0
        assert handler.max_retries == 3
        assert handler.handshake_timeout == 30.0
        assert isinstance(handler.credentials_store, dict)
        assert isinstance(handler.auth_callbacks, list)
        assert isinstance(handler.error_callbacks, list)
        assert isinstance(handler.state_callbacks, list)
        
    def test_auth_token_management(self):
        """Test authentication token management"""
        handler = MockAuthenticationHandler()
        
        # Set token
        test_token = "test_auth_token_123"
        handler.set_auth_token(test_token)
        assert handler.auth_token == test_token
        
        # Clear token
        handler.clear_auth_token()
        assert handler.auth_token is None
        
    def test_authentication_process(self):
        """Test authentication process"""
        handler = MockAuthenticationHandler()
        
        # Authentication without token should fail
        result = handler.authenticate()
        assert result is False
        
        # Set token and authenticate
        handler.set_auth_token("test_token")
        result = handler.authenticate()
        assert result is True
        assert handler.auth_status == "authenticating"
        assert handler.last_auth_attempt is not None
        
    def test_identity_token_handling(self):
        """Test handling identity token messages"""
        handler = MockAuthenticationHandler()
        handler.set_auth_token("test_token")
        
        # Create identity token message
        identity = Identity.from_hex("a" * 32)
        connection_id = ConnectionId.from_hex("b" * 16)
        identity_token = IdentityToken(
            token="identity_token_123",
            identity=identity,
            connection_id=connection_id
        )
        
        # Handle identity token
        result = handler.handle_identity_token(identity_token)
        assert result is True
        assert handler.identity == identity
        assert handler.connection_id == connection_id
        assert handler.identity_token == "identity_token_123"
        assert handler.auth_status == "authenticated"
        assert handler.retry_count == 0
        
    def test_authentication_error_handling(self):
        """Test authentication error handling"""
        handler = MockAuthenticationHandler()
        
        # Handle authentication error
        error_message = "Invalid credentials"
        handler.handle_auth_error(error_message)
        
        assert handler.auth_status == "error"
        assert handler.retry_count == 1
        
    def test_authentication_callbacks(self):
        """Test authentication success callbacks"""
        handler = MockAuthenticationHandler()
        
        # Track callback calls
        callback_called = False
        callback_data = None
        
        def auth_callback(token, identity, connection_id):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = (token, identity, connection_id)
            
        handler.add_auth_callback(auth_callback)
        
        # Handle successful authentication
        handler.set_auth_token("test_token")
        identity = Identity.from_hex("a" * 32)
        connection_id = ConnectionId.from_hex("b" * 16)
        identity_token = IdentityToken(
            token="identity_token_123",
            identity=identity,
            connection_id=connection_id
        )
        
        handler.handle_identity_token(identity_token)
        
        # Verify callback was called
        assert callback_called is True
        assert callback_data[0] == "identity_token_123"
        assert callback_data[1] == identity
        assert callback_data[2] == connection_id
        
    def test_authentication_error_callbacks(self):
        """Test authentication error callbacks"""
        handler = MockAuthenticationHandler()
        
        # Track error callback calls
        error_callback_called = False
        error_message = None
        
        def error_callback(error):
            nonlocal error_callback_called, error_message
            error_callback_called = True
            error_message = error
            
        handler.add_error_callback(error_callback)
        
        # Handle authentication error
        test_error = "Authentication failed"
        handler.handle_auth_error(test_error)
        
        # Verify error callback was called
        assert error_callback_called is True
        assert error_message == test_error
        
    def test_authentication_state_callbacks(self):
        """Test authentication state change callbacks"""
        handler = MockAuthenticationHandler()
        
        # Track state changes
        state_changes = []
        
        def state_callback(state):
            state_changes.append(state)
            
        handler.add_state_callback(state_callback)
        
        # Trigger state changes
        handler.authenticate()  # Should fail without token
        handler.set_auth_token("test_token")
        handler.authenticate()  # Should succeed
        
        # Verify state changes were recorded
        assert "authenticating" in state_changes
        
    def test_callback_management(self):
        """Test adding and removing callbacks"""
        handler = MockAuthenticationHandler()
        
        def test_callback1():
            pass
            
        def test_callback2():
            pass
            
        # Add callbacks
        handler.add_auth_callback(test_callback1)
        handler.add_error_callback(test_callback2)
        
        assert len(handler.auth_callbacks) == 1
        assert len(handler.error_callbacks) == 1
        
        # Remove callbacks
        success1 = handler.remove_auth_callback(test_callback1)
        success2 = handler.remove_error_callback(test_callback2)
        
        assert success1 is True
        assert success2 is True
        assert len(handler.auth_callbacks) == 0
        assert len(handler.error_callbacks) == 0
        
        # Try to remove non-existent callback
        success3 = handler.remove_auth_callback(test_callback1)
        assert success3 is False
        
    def test_identity_management(self):
        """Test identity management"""
        handler = MockAuthenticationHandler()
        
        # Initially no identity
        assert handler.get_identity() is None
        assert handler.get_connection_id() is None
        assert handler.get_identity_token() is None
        assert handler.is_authenticated() is False
        
        # Set identity
        handler.set_auth_token("test_token")
        identity = Identity.from_hex("a" * 32)
        connection_id = ConnectionId.from_hex("b" * 16)
        identity_token = IdentityToken(
            token="identity_token_123",
            identity=identity,
            connection_id=connection_id
        )
        
        handler.handle_identity_token(identity_token)
        
        assert handler.get_identity() == identity
        assert handler.get_connection_id() == connection_id
        assert handler.get_identity_token() == "identity_token_123"
        assert handler.is_authenticated() is True
        
        # Clear identity
        handler.clear_identity()
        
        assert handler.get_identity() is None
        assert handler.get_connection_id() is None
        assert handler.get_identity_token() is None
        assert handler.is_authenticated() is False
        
    def test_credentials_storage(self):
        """Test credentials storage and retrieval"""
        handler = MockAuthenticationHandler()
        
        # Store credentials
        identity_str = "test_identity"
        credentials = AuthCredentials(
            identity=identity_str,
            token="test_token",
            host="localhost:3000",
            database="test_db"
        )
        
        handler.store_credentials(identity_str, credentials)
        
        # Retrieve credentials
        retrieved = handler.get_stored_credentials(identity_str)
        assert retrieved is not None
        assert retrieved.token == "test_token"
        assert retrieved.identity == identity_str
        assert retrieved.host == "localhost:3000"
        assert retrieved.database == "test_db"
        
        # Clear credentials
        success = handler.clear_stored_credentials(identity_str)
        assert success is True
        
        # Try to retrieve cleared credentials
        retrieved = handler.get_stored_credentials(identity_str)
        assert retrieved is None
        
    def test_token_validation(self):
        """Test authentication token validation"""
        handler = MockAuthenticationHandler()
        
        # Valid tokens
        assert handler.validate_token("valid_token_123") is True
        assert handler.validate_token("another.valid-token_456") is True
        
        # Invalid tokens
        assert handler.validate_token("") is False
        assert handler.validate_token("short") is False
        assert handler.validate_token("invalid token with spaces") is False
        assert handler.validate_token("invalid@token#with$special") is False
        assert handler.validate_token(None) is False
        assert handler.validate_token(123) is False
        
    def test_auth_headers_generation(self):
        """Test authentication headers generation"""
        handler = MockAuthenticationHandler()
        
        # No authentication
        headers = handler.get_auth_headers()
        assert len(headers) == 0
        
        # With token only
        handler.set_auth_token("test_token")
        headers = handler.get_auth_headers()
        assert headers['Authorization'] == 'Bearer test_token'
        
        # With full authentication
        identity = Identity.from_hex("a" * 32)
        connection_id = ConnectionId.from_hex("b" * 16)
        identity_token = IdentityToken(
            token="identity_token_123",
            identity=identity,
            connection_id=connection_id
        )
        
        handler.handle_identity_token(identity_token)
        headers = handler.get_auth_headers()
        
        assert headers['Authorization'] == 'Bearer test_token'
        assert headers['X-SpacetimeDB-Identity'] == str(identity)
        assert headers['X-SpacetimeDB-Connection-ID'] == str(connection_id)
        
    def test_token_expiration(self):
        """Test token expiration checking"""
        handler = MockAuthenticationHandler()
        
        # No authentication attempt
        assert handler.is_token_expired() is False
        
        # Recent authentication
        handler.set_auth_token("test_token")
        handler.authenticate()
        assert handler.is_token_expired() is False
        
        # Simulate old authentication
        handler.last_auth_attempt = time.time() - 3700  # Over 1 hour ago
        assert handler.is_token_expired() is True
        
    def test_authentication_refresh(self):
        """Test authentication refresh"""
        handler = MockAuthenticationHandler()
        
        # No authentication
        result = handler.refresh_authentication()
        assert result is False
        
        # Recent authentication
        handler.set_auth_token("test_token")
        handler.authenticate()
        result = handler.refresh_authentication()
        assert result is True
        
        # Expired authentication
        handler.last_auth_attempt = time.time() - 3700
        result = handler.refresh_authentication()
        assert result is True
        assert handler.auth_status == "authenticating"
        
    def test_concurrent_authentication(self):
        """Test concurrent authentication operations"""
        handler = MockAuthenticationHandler()
        handler.set_auth_token("test_token")
        
        results = []
        
        def authenticate_worker():
            result = handler.authenticate()
            results.append(result)
            
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=authenticate_worker)
            threads.append(thread)
            thread.start()
            
        # Wait for all threads
        for thread in threads:
            thread.join()
            
        # All operations should succeed
        assert all(results)
        
    def test_authentication_retry_logic(self):
        """Test authentication retry logic"""
        handler = MockAuthenticationHandler()
        handler.set_auth_token("test_token")
        
        # Handle multiple errors
        for i in range(3):
            handler.handle_auth_error(f"Error {i}")
            
        # Should be at max retries
        assert handler.retry_count == 3
        
        # Another error should not increase retry count beyond max
        handler.handle_auth_error("Final error")
        assert handler.retry_count == 4  # Will increase but retry won't be scheduled
        
    def test_auth_status_tracking(self):
        """Test authentication status tracking"""
        handler = MockAuthenticationHandler()
        
        # Initial status
        assert handler.get_auth_status() == "unauthenticated"
        
        # Authenticating
        handler.set_auth_token("test_token")
        handler.authenticate()
        assert handler.get_auth_status() == "authenticating"
        
        # Authenticated
        identity = Identity.from_hex("a" * 32)
        connection_id = ConnectionId.from_hex("b" * 16)
        identity_token = IdentityToken(
            token="identity_token_123",
            identity=identity,
            connection_id=connection_id
        )
        handler.handle_identity_token(identity_token)
        assert handler.get_auth_status() == "authenticated"
        
        # Error
        handler.handle_auth_error("Test error")
        assert handler.get_auth_status() == "error"
        
        # Clear
        handler.clear_identity()
        assert handler.get_auth_status() == "unauthenticated"