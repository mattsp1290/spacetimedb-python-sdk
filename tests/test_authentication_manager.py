"""
Unit tests for AuthenticationManager

This module tests the AuthenticationManager class that handles authentication
flow management extracted from WebSocketClient.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Optional, Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from spacetimedb_sdk.auth.authentication_manager import (
    AuthenticationManager,
    AuthenticationResult
)
from spacetimedb_sdk.auth.storage import AuthCredentials, SecureAuthStorage
from spacetimedb_sdk.connection.authentication_handler import AuthenticationState
from spacetimedb_sdk.auth.secure_verification import SecureVerificationManager


class TestAuthenticationManager:
    """Test suite for AuthenticationManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.host = "test.spacetimedb.com"
        self.database = "test_db"
        
        # Mock dependencies
        self.mock_storage = Mock(spec=SecureAuthStorage)
        self.mock_event_manager = Mock()
        self.mock_logger = Mock()
        
        # Create AuthenticationManager instance
        self.auth_manager = AuthenticationManager(
            host=self.host,
            database=self.database,
            storage=self.mock_storage,
            event_manager=self.mock_event_manager,
            logger=self.mock_logger
        )
    
    def test_initialization(self):
        """Test AuthenticationManager initialization."""
        assert self.auth_manager.host == self.host
        assert self.auth_manager.database == self.database
        assert self.auth_manager.authentication_state == AuthenticationState.UNAUTHENTICATED
        assert not self.auth_manager.is_authenticated
        assert self.auth_manager.identity is None
        assert self.auth_manager.token is None
        assert not self.auth_manager.handshake_completed
    
    def test_initialization_with_stored_credentials(self):
        """Test initialization with valid stored credentials."""
        # Mock stored credentials
        mock_credentials = AuthCredentials(
            identity="test_identity",
            token="test_token",
            host=self.host,
            database=self.database,
            timestamp=time.time()
        )
        mock_credentials.is_expired = Mock(return_value=False)
        
        self.mock_storage.get_credentials.return_value = mock_credentials
        
        # Create new AuthenticationManager
        auth_manager = AuthenticationManager(
            host=self.host,
            database=self.database,
            storage=self.mock_storage,
            event_manager=self.mock_event_manager,
            logger=self.mock_logger
        )
        
        # Verify credentials were loaded
        assert auth_manager.is_authenticated
        assert auth_manager.identity == "test_identity"
        assert auth_manager.token == "test_token"
        assert auth_manager.handshake_completed
        assert auth_manager.authentication_state == AuthenticationState.AUTHENTICATED
    
    def test_initialization_with_expired_credentials(self):
        """Test initialization with expired stored credentials."""
        # Mock expired credentials
        mock_credentials = AuthCredentials(
            identity="test_identity",
            token="test_token",
            host=self.host,
            database=self.database,
            timestamp=time.time() - 86400  # 24 hours ago
        )
        mock_credentials.is_expired = Mock(return_value=True)
        
        self.mock_storage.get_credentials.return_value = mock_credentials
        
        # Create new AuthenticationManager
        auth_manager = AuthenticationManager(
            host=self.host,
            database=self.database,
            storage=self.mock_storage,
            event_manager=self.mock_event_manager,
            logger=self.mock_logger
        )
        
        # Verify expired credentials were not loaded
        assert not auth_manager.is_authenticated
        assert auth_manager.identity is None
        assert auth_manager.token is None
        assert not auth_manager.handshake_completed
    
    def test_handle_auth_handshake_success(self):
        """Test successful authentication handshake."""
        identity = "test_identity"
        token = "test_token"
        
        # Mock secure verification
        with patch.object(self.auth_manager._verifier, 'verify_token_format') as mock_verify:
            mock_verify.return_value = Mock(is_valid=True, error=None)
            
            result = self.auth_manager.handle_auth_handshake(identity, token)
        
        # Verify successful result
        assert result.success
        assert result.identity == identity
        assert result.token == token
        assert result.error is None
        
        # Verify state was updated
        assert self.auth_manager.is_authenticated
        assert self.auth_manager.identity == identity
        assert self.auth_manager.token == token
        assert self.auth_manager.handshake_completed
        assert self.auth_manager.authentication_state == AuthenticationState.AUTHENTICATED
        
        # Verify credentials were stored
        self.mock_storage.store_credentials.assert_called_once_with(
            identity, token, self.host, self.database
        )
    
    def test_handle_auth_handshake_invalid_token(self):
        """Test authentication handshake with invalid token."""
        identity = "test_identity"
        token = "invalid_token"
        
        # Mock secure verification failure
        with patch.object(self.auth_manager._verifier, 'verify_token_format') as mock_verify:
            mock_verify.return_value = Mock(is_valid=False, error="Invalid token format")
            
            result = self.auth_manager.handle_auth_handshake(identity, token)
        
        # Verify failed result
        assert not result.success
        assert result.error == "Token validation failed: Invalid token format"
        
        # Verify state was not updated
        assert not self.auth_manager.is_authenticated
        assert self.auth_manager.identity is None
        assert self.auth_manager.token is None
    
    def test_handle_auth_handshake_missing_credentials(self):
        """Test authentication handshake with missing credentials."""
        result = self.auth_manager.handle_auth_handshake("", "")
        
        assert not result.success
        assert "missing identity or token" in result.error
        assert not self.auth_manager.is_authenticated
    
    def test_authenticate_with_valid_credentials(self):
        """Test authentication with valid credentials."""
        credentials = AuthCredentials(
            identity="test_identity",
            token="test_token",
            host=self.host,
            database=self.database,
            timestamp=time.time()
        )
        credentials.is_expired = Mock(return_value=False)
        
        # Mock secure verification
        with patch('spacetimedb_sdk.auth.authentication_manager.verify_credentials_secure') as mock_verify:
            mock_verify.return_value = Mock(success=True)
            
            result = self.auth_manager.authenticate(credentials)
        
        # Verify successful authentication
        assert result.success
        assert result.identity == "test_identity"
        assert result.token == "test_token"
        assert self.auth_manager.is_authenticated
    
    def test_authenticate_with_stored_credentials(self):
        """Test authentication using stored credentials."""
        # Mock stored credentials
        mock_credentials = AuthCredentials(
            identity="test_identity",
            token="test_token",
            host=self.host,
            database=self.database,
            timestamp=time.time()
        )
        mock_credentials.is_expired = Mock(return_value=False)
        
        self.mock_storage.get_credentials.return_value = mock_credentials
        
        # Mock secure verification
        with patch('spacetimedb_sdk.auth.authentication_manager.verify_credentials_secure') as mock_verify:
            mock_verify.return_value = Mock(success=True)
            
            result = self.auth_manager.authenticate()
        
        # Verify successful authentication
        assert result.success
        assert result.identity == "test_identity"
        assert result.token == "test_token"
        assert self.auth_manager.is_authenticated
    
    def test_authenticate_no_stored_credentials(self):
        """Test authentication when no stored credentials exist."""
        self.mock_storage.get_credentials.return_value = None
        
        result = self.auth_manager.authenticate()
        
        assert not result.success
        assert result.requires_handshake
        assert "No valid credentials available" in result.error
    
    def test_authenticate_verification_failure(self):
        """Test authentication with credential verification failure."""
        credentials = AuthCredentials(
            identity="test_identity",
            token="test_token",
            host=self.host,
            database=self.database,
            timestamp=time.time()
        )
        credentials.is_expired = Mock(return_value=False)
        
        # Mock secure verification failure
        with patch('spacetimedb_sdk.auth.authentication_manager.verify_credentials_secure') as mock_verify:
            mock_verify.return_value = False
            
            result = self.auth_manager.authenticate(credentials)
        
        # Verify failed authentication
        assert not result.success
        assert "Credential verification failed" in result.error
        assert not self.auth_manager.is_authenticated
    
    def test_get_auth_headers(self):
        """Test authentication header generation."""
        # Initially no headers
        headers = self.auth_manager.get_auth_headers()
        assert headers == {}
        
        # Set up authenticated state
        self.auth_manager._identity = "test_identity"
        self.auth_manager._token = "test_token"
        self.auth_manager._handshake_completed = True
        self.auth_manager._auth_state = AuthenticationState.AUTHENTICATED
        
        # Should return Bearer token header
        headers = self.auth_manager.get_auth_headers()
        assert headers == {"Authorization": "Bearer test_token"}
    
    def test_refresh_token_not_authenticated(self):
        """Test token refresh when not authenticated."""
        result = self.auth_manager.refresh_token()
        
        assert not result.success
        assert "Not authenticated" in result.error
    
    def test_refresh_token_not_supported(self):
        """Test token refresh - currently not supported."""
        # Set up authenticated state
        self.auth_manager._identity = "test_identity"
        self.auth_manager._token = "test_token"
        self.auth_manager._handshake_completed = True
        self.auth_manager._auth_state = AuthenticationState.AUTHENTICATED
        
        result = self.auth_manager.refresh_token()
        
        assert not result.success
        assert result.requires_handshake
        assert "not supported" in result.error
    
    def test_logout(self):
        """Test logout functionality."""
        # Set up authenticated state
        self.auth_manager._identity = "test_identity"
        self.auth_manager._token = "test_token"
        self.auth_manager._handshake_completed = True
        self.auth_manager._auth_state = AuthenticationState.AUTHENTICATED
        
        # Logout
        self.auth_manager.logout()
        
        # Verify state was cleared
        assert not self.auth_manager.is_authenticated
        assert self.auth_manager.identity is None
        assert self.auth_manager.token is None
        assert not self.auth_manager.handshake_completed
        assert self.auth_manager.authentication_state == AuthenticationState.UNAUTHENTICATED
    
    def test_clear_stored_credentials(self):
        """Test clearing stored credentials."""
        # Set up authenticated state
        self.auth_manager._identity = "test_identity"
        self.auth_manager._token = "test_token"
        self.auth_manager._handshake_completed = True
        self.auth_manager._auth_state = AuthenticationState.AUTHENTICATED
        
        # Clear stored credentials
        self.auth_manager.clear_stored_credentials()
        
        # Verify storage was cleared
        self.mock_storage.clear_credentials.assert_called_once_with(
            self.host, self.database
        )
        
        # Verify state was also cleared (logout is called)
        assert not self.auth_manager.is_authenticated
    
    def test_get_auth_info(self):
        """Test authentication info retrieval."""
        # Set up authenticated state
        self.auth_manager._identity = "test_identity"
        self.auth_manager._token = "test_token"
        self.auth_manager._handshake_completed = True
        self.auth_manager._auth_state = AuthenticationState.AUTHENTICATED
        self.auth_manager._credentials_timestamp = time.time()
        
        info = self.auth_manager.get_auth_info()
        
        # Verify info contains expected fields
        assert info["state"] == "authenticated"
        assert info["is_authenticated"] is True
        assert info["handshake_completed"] is True
        assert info["has_identity"] is True
        assert info["has_token"] is True
        assert info["host"] == self.host
        assert info["database"] == self.database
        assert "credentials_age_seconds" in info
    
    def test_thread_safety(self):
        """Test thread safety of authentication operations."""
        def authenticate_worker():
            credentials = AuthCredentials(
                identity="test_identity",
                token="test_token",
                host=self.host,
                database=self.database,
                timestamp=time.time()
            )
            credentials.is_expired = Mock(return_value=False)
            
            with patch('spacetimedb_sdk.auth.authentication_manager.verify_credentials_secure') as mock_verify:
                mock_verify.return_value = Mock(success=True)
                self.auth_manager.authenticate(credentials)
        
        def logout_worker():
            self.auth_manager.logout()
        
        # Run multiple threads concurrently
        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=authenticate_worker)
            t2 = threading.Thread(target=logout_worker)
            threads.extend([t1, t2])
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should not raise any exceptions
        assert True
    
    def test_event_emission(self):
        """Test authentication event emission."""
        identity = "test_identity"
        token = "test_token"
        
        # Mock secure verification
        with patch.object(self.auth_manager._verifier, 'verify_token_format') as mock_verify:
            mock_verify.return_value = Mock(is_valid=True, error=None)
            
            self.auth_manager.handle_auth_handshake(identity, token)
        
        # Verify event was emitted
        assert self.mock_event_manager.emit_event.called
    
    def test_string_representation(self):
        """Test string representation of AuthenticationManager."""
        str_repr = str(self.auth_manager)
        
        assert "AuthenticationManager" in str_repr
        assert self.host in str_repr
        assert self.database in str_repr
        assert "unauthenticated" in str_repr


if __name__ == '__main__':
    pytest.main([__file__])