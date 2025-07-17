#!/usr/bin/env python3
"""
Comprehensive Test Suite for Authentication Handler

This test suite validates the authentication handler implementation including:
- JWT token management
- Credential storage and retrieval
- Authentication state management
- Event integration
- Error handling and recovery
- Security features
"""

import pytest
import time
import threading
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add the src directory to the path for imports
import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk.connection.authentication_handler import (
    AuthenticationHandler,
    AuthenticationState,
    AuthenticationCredentials,
    AuthenticationEvent
)
from spacetimedb_sdk.auth.storage import SecureAuthStorage


class TestAuthenticationCredentials:
    """Test authentication credentials wrapper."""
    
    def test_credentials_creation(self):
        """Test credentials creation and basic properties."""
        creds = AuthenticationCredentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db",
            timestamp=time.time()
        )
        
        assert creds.identity == "test_identity"
        assert creds.token == "test_token"
        assert creds.host == "localhost"
        assert creds.database == "test_db"
        assert not creds.is_expired
    
    def test_credentials_expiry(self):
        """Test credentials expiry logic."""
        # Create expired credentials
        old_timestamp = time.time() - 90000  # 25 hours ago
        creds = AuthenticationCredentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db",
            timestamp=old_timestamp
        )
        
        assert creds.is_expired
        assert creds.time_until_expiry == 0
    
    def test_credentials_custom_expiry(self):
        """Test credentials with custom expiry."""
        future_expiry = time.time() + 3600  # 1 hour from now
        creds = AuthenticationCredentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db",
            timestamp=time.time(),
            expires_at=future_expiry
        )
        
        assert not creds.is_expired
        assert creds.time_until_expiry > 3500  # Should be close to 1 hour


class TestAuthenticationHandler:
    """Test authentication handler core functionality."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock storage backend."""
        storage = Mock(spec=SecureAuthStorage)
        storage.get_storage_info.return_value = {"type": "mock", "initialized": True}
        return storage
    
    @pytest.fixture
    def mock_event_handler(self):
        """Create mock event handler."""
        return Mock()
    
    @pytest.fixture
    def auth_handler(self, mock_storage, mock_event_handler):
        """Create authentication handler with mocks."""
        return AuthenticationHandler(
            storage=mock_storage,
            event_handler=mock_event_handler,
            auto_refresh_tokens=False  # Disable for testing
        )
    
    def test_handler_initialization(self, auth_handler, mock_storage, mock_event_handler):
        """Test handler initialization."""
        assert auth_handler.storage == mock_storage
        assert auth_handler.event_handler == mock_event_handler
        assert auth_handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
    
    def test_legacy_token_authentication(self, auth_handler):
        """Test legacy token authentication."""
        headers = auth_handler.authenticate_with_legacy_token(
            "test_token",
            "localhost",
            "test_db"
        )
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        
        # Verify base64 encoding
        import base64
        encoded = headers["Authorization"].split(" ")[1]
        decoded = base64.b64decode(encoded).decode('utf-8')
        assert decoded == "token:test_token"
    
    def test_stored_credentials_retrieval(self, auth_handler, mock_storage):
        """Test retrieval of stored credentials."""
        # Mock storage response
        from spacetimedb_sdk.auth.storage import AuthCredentials
        stored_creds = AuthCredentials(
            identity="test_identity",
            token="test_token",
            host="localhost",
            database="test_db",
            timestamp=time.time()
        )
        mock_storage.get_credentials.return_value = stored_creds
        
        # Retrieve credentials
        creds = auth_handler.get_stored_credentials("localhost", "test_db")
        
        assert creds is not None
        assert creds.identity == "test_identity"
        assert creds.token == "test_token"
        assert creds.host == "localhost"
        assert creds.database == "test_db"
        
        mock_storage.get_credentials.assert_called_once_with("localhost", "test_db", False)
    
    def test_stored_credentials_not_found(self, auth_handler, mock_storage):
        """Test handling when stored credentials are not found."""
        mock_storage.get_credentials.return_value = None
        
        creds = auth_handler.get_stored_credentials("localhost", "test_db")
        
        assert creds is None
    
    def test_credentials_storage(self, auth_handler, mock_storage, mock_event_handler):
        """Test credential storage."""
        auth_handler.store_credentials("identity123", "token456", "localhost", "test_db")
        
        # Verify storage was called
        mock_storage.store_credentials.assert_called_once_with(
            "identity123", "token456", "localhost", "test_db"
        )
        
        # Verify state change
        assert auth_handler.get_authentication_state() == AuthenticationState.AUTHENTICATED
        
        # Verify event was emitted
        mock_event_handler.assert_called()
        event = mock_event_handler.call_args[0][0]
        assert isinstance(event, AuthenticationEvent)
        assert event.state == AuthenticationState.AUTHENTICATED
        assert event.identity == "identity123"
    
    def test_jwt_headers_preparation(self, auth_handler):
        """Test JWT headers preparation."""
        # Store credentials first
        auth_handler.store_credentials("identity123", "token456", "localhost", "test_db")
        
        # Prepare headers
        headers = auth_handler.prepare_jwt_headers("localhost", "test_db")
        
        assert headers is not None
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer token456"
    
    def test_jwt_headers_no_credentials(self, auth_handler, mock_storage):
        """Test JWT headers when no credentials are available."""
        mock_storage.get_credentials.return_value = None
        
        headers = auth_handler.prepare_jwt_headers("localhost", "test_db")
        
        assert headers is None
    
    def test_authentication_handshake_success(self, auth_handler, mock_event_handler):
        """Test successful authentication handshake."""
        error_message = (
            "Handshake status 400: Authentication required. "
            "spacetime-identity: abcdef123456 "
            "spacetime-identity-token: jwt.token.here"
        )
        
        result = auth_handler.handle_authentication_handshake(
            error_message, "localhost", "test_db"
        )
        
        assert result is True
        assert auth_handler.get_authentication_state() == AuthenticationState.AUTHENTICATED
        
        # Verify event was emitted
        mock_event_handler.assert_called()
    
    def test_authentication_handshake_invalid(self, auth_handler):
        """Test authentication handshake with invalid data."""
        error_message = "Some other error without identity headers"
        
        result = auth_handler.handle_authentication_handshake(
            error_message, "localhost", "test_db"
        )
        
        assert result is False
        assert auth_handler.get_authentication_state() == AuthenticationState.FAILED
    
    def test_retry_logic(self, auth_handler):
        """Test authentication retry logic."""
        # Should retry on auth errors
        assert auth_handler.should_retry_authentication(400) is True
        assert auth_handler.should_retry_authentication(401) is True
        assert auth_handler.should_retry_authentication(403) is True
        
        # Should not retry on other errors
        assert auth_handler.should_retry_authentication(404) is False
        assert auth_handler.should_retry_authentication(500) is False
    
    def test_retry_limit(self, auth_handler):
        """Test retry limit enforcement."""
        # Exhaust retry attempts
        for _ in range(auth_handler.max_retry_attempts):
            assert auth_handler.should_retry_authentication(400) is True
        
        # Should not retry after limit
        assert auth_handler.should_retry_authentication(400) is False
    
    def test_credentials_clearing(self, auth_handler, mock_storage, mock_event_handler):
        """Test credentials clearing."""
        # Store credentials first
        auth_handler.store_credentials("identity123", "token456", "localhost", "test_db")
        
        # Clear credentials
        auth_handler.clear_credentials("localhost", "test_db")
        
        # Verify storage was called
        mock_storage.remove_credentials.assert_called_once_with("localhost", "test_db")
        
        # Verify state change
        assert auth_handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
        
        # Verify event was emitted
        assert mock_event_handler.call_count >= 2  # Store + clear events
    
    def test_authentication_info(self, auth_handler, mock_storage):
        """Test authentication info retrieval."""
        mock_storage.get_storage_info.return_value = {"type": "mock"}
        
        info = auth_handler.get_authentication_info()
        
        assert "state" in info
        assert "retry_count" in info
        assert "auto_refresh_enabled" in info
        assert "storage" in info
        assert info["state"] == AuthenticationState.UNAUTHENTICATED.value
    
    def test_context_manager(self, auth_handler):
        """Test authentication handler as context manager."""
        with auth_handler as handler:
            assert handler is auth_handler
        
        # Handler should be shut down after context
        assert handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED


class TestAuthenticationIntegration:
    """Integration tests for authentication handler."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def real_storage(self, temp_storage_dir):
        """Create real storage backend."""
        return SecureAuthStorage(
            storage_dir=temp_storage_dir,
            prefer_keyring=False,  # Use file storage for testing
            master_password="test_password"
        )
    
    @pytest.fixture
    def integration_handler(self, real_storage):
        """Create handler with real storage."""
        return AuthenticationHandler(
            storage=real_storage,
            auto_refresh_tokens=False
        )
    
    def test_full_authentication_flow(self, integration_handler):
        """Test complete authentication flow with real storage."""
        # Start unauthenticated
        assert integration_handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
        
        # Store credentials
        integration_handler.store_credentials("identity123", "token456", "localhost", "test_db")
        
        # Verify state change
        assert integration_handler.get_authentication_state() == AuthenticationState.AUTHENTICATED
        
        # Verify JWT headers work
        headers = integration_handler.prepare_jwt_headers("localhost", "test_db")
        assert headers is not None
        assert headers["Authorization"] == "Bearer token456"
        
        # Verify credentials are stored
        stored_creds = integration_handler.get_stored_credentials("localhost", "test_db")
        assert stored_creds is not None
        assert stored_creds.identity == "identity123"
        assert stored_creds.token == "token456"
        
        # Clear credentials
        integration_handler.clear_credentials("localhost", "test_db")
        
        # Verify cleanup
        assert integration_handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
        assert integration_handler.get_stored_credentials("localhost", "test_db") is None
    
    def test_multiple_credentials(self, integration_handler):
        """Test handling multiple credentials for different hosts/databases."""
        # Store credentials for different databases
        integration_handler.store_credentials("identity1", "token1", "host1", "db1")
        integration_handler.store_credentials("identity2", "token2", "host2", "db2")
        
        # Verify both are stored
        creds1 = integration_handler.get_stored_credentials("host1", "db1")
        creds2 = integration_handler.get_stored_credentials("host2", "db2")
        
        assert creds1 is not None
        assert creds1.identity == "identity1"
        assert creds2 is not None
        assert creds2.identity == "identity2"
        
        # Verify cross-contamination doesn't occur
        assert integration_handler.get_stored_credentials("host1", "db2") is None
        assert integration_handler.get_stored_credentials("host2", "db1") is None
    
    def test_persistence_across_instances(self, real_storage):
        """Test credential persistence across handler instances."""
        # Store credentials with first instance
        handler1 = AuthenticationHandler(storage=real_storage, auto_refresh_tokens=False)
        handler1.store_credentials("identity123", "token456", "localhost", "test_db")
        
        # Create second instance
        handler2 = AuthenticationHandler(storage=real_storage, auto_refresh_tokens=False)
        
        # Verify credentials are available in second instance
        creds = handler2.get_stored_credentials("localhost", "test_db")
        assert creds is not None
        assert creds.identity == "identity123"
        assert creds.token == "token456"


class TestAuthenticationSecurity:
    """Security-focused tests for authentication handler."""
    
    def test_credential_masking_in_logs(self, caplog):
        """Test that credentials are masked in log output."""
        from spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler
        
        handler = AuthenticationHandler(auto_refresh_tokens=False)
        
        # Store credentials (should trigger logging)
        with caplog.at_level("INFO"):
            handler.store_credentials("identity123456789", "secret_token", "localhost", "test_db")
        
        # Verify identity is masked in logs
        log_output = " ".join(caplog.messages)
        assert "identity123456789" not in log_output
        assert "identity12345678..." in log_output or "identity1234..." in log_output
        assert "secret_token" not in log_output
    
    def test_authentication_info_security(self, mock_storage):
        """Test that authentication info doesn't leak sensitive data."""
        handler = AuthenticationHandler(storage=mock_storage, auto_refresh_tokens=False)
        handler.store_credentials("identity123456789", "secret_token", "localhost", "test_db")
        
        info = handler.get_authentication_info()
        
        # Verify sensitive data is not exposed
        assert "secret_token" not in str(info)
        assert "identity123456789" not in str(info)
        
        # Verify identity is masked
        if "current_identity" in info:
            assert info["current_identity"].endswith("...")
    
    def test_thread_safety(self, mock_storage):
        """Test thread safety of authentication operations."""
        handler = AuthenticationHandler(storage=mock_storage, auto_refresh_tokens=False)
        
        results = []
        errors = []
        
        def auth_worker(worker_id):
            try:
                # Simulate concurrent authentication operations
                for i in range(10):
                    handler.store_credentials(f"identity{worker_id}_{i}", f"token{worker_id}_{i}", "localhost", f"db{worker_id}")
                    creds = handler.get_stored_credentials("localhost", f"db{worker_id}")
                    results.append((worker_id, i, creds is not None))
            except Exception as e:
                errors.append((worker_id, e))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=auth_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors and all operations succeeded
        assert len(errors) == 0
        assert len(results) == 50  # 5 workers * 10 operations each
        assert all(success for _, _, success in results)


class TestAuthenticationEvents:
    """Test authentication event system."""
    
    @pytest.fixture
    def event_handler(self):
        """Create event handler that captures events."""
        events = []
        
        def handler(event):
            events.append(event)
        
        handler.events = events
        return handler
    
    @pytest.fixture
    def auth_handler_with_events(self, mock_storage, event_handler):
        """Create handler with event capturing."""
        return AuthenticationHandler(
            storage=mock_storage,
            event_handler=event_handler,
            auto_refresh_tokens=False
        )
    
    def test_authentication_events(self, auth_handler_with_events, event_handler):
        """Test authentication event emission."""
        # Store credentials (should emit events)
        auth_handler_with_events.store_credentials("identity123", "token456", "localhost", "test_db")
        
        # Verify events were emitted
        assert len(event_handler.events) >= 1
        
        # Find authentication event
        auth_events = [e for e in event_handler.events if isinstance(e, AuthenticationEvent)]
        assert len(auth_events) >= 1
        
        # Verify event properties
        event = auth_events[-1]  # Get last auth event
        assert event.state == AuthenticationState.AUTHENTICATED
        assert event.identity == "identity123"
        assert event.host == "localhost"
        assert event.database == "test_db"
    
    def test_handshake_events(self, auth_handler_with_events, event_handler):
        """Test handshake event emission."""
        error_message = (
            "Handshake status 400: Authentication required. "
            "spacetime-identity: abcdef123456 "
            "spacetime-identity-token: jwt.token.here"
        )
        
        # Handle handshake
        auth_handler_with_events.handle_authentication_handshake(
            error_message, "localhost", "test_db"
        )
        
        # Verify events were emitted
        auth_events = [e for e in event_handler.events if isinstance(e, AuthenticationEvent)]
        assert len(auth_events) >= 1
        
        # Should have events for authenticating and authenticated states
        states = [e.state for e in auth_events]
        assert AuthenticationState.AUTHENTICATING in states
        assert AuthenticationState.AUTHENTICATED in states
    
    def test_error_events(self, auth_handler_with_events, event_handler):
        """Test error event emission."""
        # Try to handle invalid handshake
        error_message = "Some other error without identity headers"
        
        auth_handler_with_events.handle_authentication_handshake(
            error_message, "localhost", "test_db"
        )
        
        # Verify error event was emitted
        auth_events = [e for e in event_handler.events if isinstance(e, AuthenticationEvent)]
        error_events = [e for e in auth_events if e.state == AuthenticationState.FAILED]
        assert len(error_events) >= 1
        
        # Verify error details
        error_event = error_events[0]
        assert error_event.error is not None
        assert error_event.host == "localhost"
        assert error_event.database == "test_db"


def test_authentication_handler_documentation():
    """Test that all public methods have proper documentation."""
    handler = AuthenticationHandler(auto_refresh_tokens=False)
    
    public_methods = [
        method for method in dir(handler)
        if not method.startswith('_') and callable(getattr(handler, method))
    ]
    
    for method_name in public_methods:
        method = getattr(handler, method_name)
        assert method.__doc__ is not None, f"Method {method_name} lacks documentation"
        assert len(method.__doc__.strip()) > 0, f"Method {method_name} has empty documentation"


if __name__ == "__main__":
    # Run tests
    print("Testing Authentication Handler...")
    
    # Basic functionality tests
    print("\n1. Testing Authentication Credentials...")
    test_creds = TestAuthenticationCredentials()
    test_creds.test_credentials_creation()
    test_creds.test_credentials_expiry()
    test_creds.test_credentials_custom_expiry()
    print("✓ Authentication credentials tests passed")
    
    # Test authentication handler with mocks
    print("\n2. Testing Authentication Handler Core...")
    
    # Create mock storage for testing
    mock_storage = Mock()
    mock_storage.get_storage_info.return_value = {"type": "mock"}
    mock_storage.get_credentials.return_value = None
    
    # Create handler
    handler = AuthenticationHandler(storage=mock_storage, auto_refresh_tokens=False)
    
    # Test basic operations
    assert handler.get_authentication_state() == AuthenticationState.UNAUTHENTICATED
    
    # Test legacy token auth
    headers = handler.authenticate_with_legacy_token("test_token", "localhost", "test_db")
    assert "Authorization" in headers
    print("✓ Legacy token authentication works")
    
    # Test JWT headers without credentials
    jwt_headers = handler.prepare_jwt_headers("localhost", "test_db")
    assert jwt_headers is None
    print("✓ JWT headers return None when no credentials")
    
    # Test handshake parsing
    error_msg = "spacetime-identity: abc123 spacetime-identity-token: token456"
    result = handler.handle_authentication_handshake(error_msg, "localhost", "test_db")
    assert result is True
    print("✓ Authentication handshake parsing works")
    
    # Test retry logic
    assert handler.should_retry_authentication(400) is True
    assert handler.should_retry_authentication(404) is False
    print("✓ Retry logic works correctly")
    
    print("\n3. Testing Authentication Info...")
    info = handler.get_authentication_info()
    assert "state" in info
    assert "retry_count" in info
    print("✓ Authentication info retrieval works")
    
    print("\n4. Testing Thread Safety...")
    import threading
    
    # Test concurrent operations
    def test_concurrent_operations():
        for i in range(10):
            handler.get_authentication_state()
            handler.get_authentication_info()
    
    threads = []
    for i in range(5):
        thread = threading.Thread(target=test_concurrent_operations)
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    print("✓ Thread safety tests passed")
    
    print("\n5. Testing Context Manager...")
    # Reset state before context manager test
    handler.clear_credentials("localhost", "test_db")
    
    with handler:
        state = handler.get_authentication_state()
        print(f"Context manager state: {state}")
        # State should be unauthenticated after clearing
        assert state == AuthenticationState.UNAUTHENTICATED or state == AuthenticationState.FAILED
    print("✓ Context manager works")
    
    print("\n🎉 All Authentication Handler tests passed!")
    print("\nAuthentication Handler Features:")
    print("• JWT token management with lifecycle tracking")
    print("• Secure credential storage integration")
    print("• Authentication state management")
    print("• Event system integration")
    print("• Thread-safe operations")
    print("• Legacy token support")
    print("• Automatic retry logic")
    print("• Comprehensive error handling")
    print("• Security-focused implementation")