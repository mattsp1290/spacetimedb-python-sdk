"""
Authentication Handler for SpacetimeDB SDK

This module provides centralized authentication management for SpacetimeDB connections,
including JWT token handling, credential storage, and authentication state management.

Features:
- JWT token management with automatic refresh
- SpacetimeDB identity management
- Secure credential storage integration
- Authentication state tracking
- Thread-safe operations
- Event integration for auth state changes
"""

import base64
import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from contextlib import contextmanager

try:
    from ..auth.storage import SecureAuthStorage, AuthCredentials
except ImportError:
    # Fallback to deprecated auth storage
    from ..auth_storage import SpacetimeDBAuthStorage as SecureAuthStorage, AuthCredentials

from ..events.enhanced_event_system import Event, EventType, EventPriority
from ..exceptions import AuthenticationError


class AuthenticationState(Enum):
    """Authentication state enumeration."""
    UNAUTHENTICATED = "unauthenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class AuthenticationEvent(Event):
    """Authentication-related event."""
    
    state: AuthenticationState = field(default=AuthenticationState.UNAUTHENTICATED)
    identity: Optional[str] = field(default=None)
    host: Optional[str] = field(default=None)
    database: Optional[str] = field(default=None)
    error: Optional[str] = field(default=None)
    
    def __post_init__(self):
        """Post-initialization hook for validation."""
        super().__post_init__()  # Call parent's post_init
    
    def validate(self) -> None:
        """Validate authentication event."""
        if not isinstance(self.state, AuthenticationState):
            raise ValueError(f"Invalid authentication state: {self.state}")
    
    def get_event_name(self) -> str:
        """Get event name."""
        return f"authentication_{self.state.value}"


@dataclass
class AuthenticationCredentials:
    """Authentication credentials wrapper."""
    
    identity: str
    token: str
    host: str
    database: str
    timestamp: float
    expires_at: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if credentials are expired."""
        if self.expires_at is None:
            # Default 24-hour expiry
            return (time.time() - self.timestamp) > 86400
        return time.time() >= self.expires_at
    
    @property
    def time_until_expiry(self) -> float:
        """Get time until expiry in seconds."""
        if self.expires_at is None:
            return max(0, 86400 - (time.time() - self.timestamp))
        return max(0, self.expires_at - time.time())


class AuthenticationHandler:
    """
    Centralized authentication handler for SpacetimeDB connections.
    
    This class manages all authentication-related operations including:
    - JWT token lifecycle management
    - SpacetimeDB identity management
    - Secure credential storage
    - Authentication state tracking
    - Event notifications
    """
    
    def __init__(
        self,
        storage: Optional[SecureAuthStorage] = None,
        event_handler: Optional[Callable[[AuthenticationEvent], None]] = None,
        auto_refresh_tokens: bool = True,
        token_refresh_threshold: float = 300.0,  # 5 minutes
        max_retry_attempts: int = 3
    ):
        """
        Initialize authentication handler.
        
        Args:
            storage: Secure storage backend (defaults to global instance)
            event_handler: Optional event handler for authentication events
            auto_refresh_tokens: Whether to automatically refresh tokens
            token_refresh_threshold: Seconds before expiry to trigger refresh
            max_retry_attempts: Maximum authentication retry attempts
        """
        self.storage = storage or self._get_default_storage()
        self.event_handler = event_handler
        self.auto_refresh_tokens = auto_refresh_tokens
        self.token_refresh_threshold = token_refresh_threshold
        self.max_retry_attempts = max_retry_attempts
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Authentication state
        self._state = AuthenticationState.UNAUTHENTICATED
        self._current_credentials: Optional[AuthenticationCredentials] = None
        self._retry_count = 0
        self._last_error: Optional[str] = None
        
        # Token refresh management
        self._refresh_timer: Optional[threading.Timer] = None
        self._refresh_callbacks: List[Callable[[AuthenticationCredentials], None]] = []
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.AuthenticationHandler")
        
        # Initialize storage
        self._init_storage()
    
    def _get_default_storage(self) -> SecureAuthStorage:
        """Get default storage instance."""
        try:
            return SecureAuthStorage()
        except Exception as e:
            self.logger.warning(f"Failed to initialize secure storage: {e}")
            # Create basic storage without encryption
            return SecureAuthStorage(prefer_keyring=False)
    
    def _init_storage(self) -> None:
        """Initialize storage backend."""
        try:
            storage_info = self.storage.get_storage_info()
            self.logger.info(f"Initialized authentication storage: {storage_info}")
        except Exception as e:
            self.logger.warning(f"Storage initialization warning: {e}")
    
    def _emit_event(self, event: AuthenticationEvent) -> None:
        """Emit authentication event."""
        event.event_type = EventType.AUTHENTICATION
        event.source = "authentication_handler"
        
        self.logger.debug(f"Authentication event: {event.get_event_name()}")
        
        if self.event_handler:
            try:
                self.event_handler(event)
            except Exception as e:
                self.logger.error(f"Error in authentication event handler: {e}")
    
    def _schedule_token_refresh(self, credentials: AuthenticationCredentials) -> None:
        """Schedule automatic token refresh."""
        if not self.auto_refresh_tokens:
            return
        
        # Calculate refresh time
        refresh_time = max(1.0, credentials.time_until_expiry - self.token_refresh_threshold)
        
        # Cancel existing timer
        if self._refresh_timer:
            self._refresh_timer.cancel()
        
        # Schedule new refresh
        self._refresh_timer = threading.Timer(refresh_time, self._refresh_token_background, [credentials])
        self._refresh_timer.daemon = True
        self._refresh_timer.start()
        
        self.logger.debug(f"Scheduled token refresh in {refresh_time:.1f} seconds")
    
    def _refresh_token_background(self, credentials: AuthenticationCredentials) -> None:
        """Background token refresh."""
        try:
            self.logger.info("Attempting automatic token refresh")
            
            # Notify callbacks
            for callback in self._refresh_callbacks:
                try:
                    callback(credentials)
                except Exception as e:
                    self.logger.error(f"Token refresh callback error: {e}")
            
            # Re-authenticate if still current
            with self._lock:
                if self._current_credentials and self._current_credentials.identity == credentials.identity:
                    self._state = AuthenticationState.AUTHENTICATING
                    self._emit_event(AuthenticationEvent(
                        state=self._state,
                        identity=credentials.identity,
                        host=credentials.host,
                        database=credentials.database,
                        data={"reason": "automatic_refresh"}
                    ))
        except Exception as e:
            self.logger.error(f"Background token refresh failed: {e}")
    
    @contextmanager
    def _authentication_context(self, host: str, database: str):
        """Context manager for authentication operations."""
        with self._lock:
            old_state = self._state
            self._state = AuthenticationState.AUTHENTICATING
            
            self._emit_event(AuthenticationEvent(
                state=self._state,
                host=host,
                database=database,
                data={"previous_state": old_state.value}
            ))
            
            try:
                yield
            except Exception as e:
                self._state = AuthenticationState.FAILED
                self._last_error = str(e)
                self._emit_event(AuthenticationEvent(
                    state=self._state,
                    host=host,
                    database=database,
                    error=str(e)
                ))
                raise
    
    def authenticate_with_legacy_token(
        self,
        auth_token: str,
        host: str,
        database: str
    ) -> Dict[str, str]:
        """
        Prepare legacy token authentication headers.
        
        Args:
            auth_token: Legacy authentication token
            host: Server host
            database: Database name
            
        Returns:
            Authentication headers
        """
        with self._authentication_context(host, database):
            token_bytes = f"token:{auth_token}".encode('utf-8')
            base64_str = base64.b64encode(token_bytes).decode('utf-8')
            
            headers = {"Authorization": f"Basic {base64_str}"}
            
            self.logger.debug(f"Prepared legacy token authentication for {host}/{database}")
            return headers
    
    def get_stored_credentials(
        self,
        host: str,
        database: str,
        allow_expired: bool = False
    ) -> Optional[AuthenticationCredentials]:
        """
        Get stored authentication credentials.
        
        Args:
            host: Server host
            database: Database name
            allow_expired: Whether to return expired credentials
            
        Returns:
            Authentication credentials if found
        """
        try:
            stored_creds = self.storage.get_credentials(host, database, allow_expired)
            if stored_creds:
                credentials = AuthenticationCredentials(
                    identity=stored_creds.identity,
                    token=stored_creds.token,
                    host=stored_creds.host or host,
                    database=stored_creds.database or database,
                    timestamp=stored_creds.timestamp
                )
                
                if not allow_expired and credentials.is_expired:
                    self.logger.debug(f"Stored credentials for {host}/{database} are expired")
                    return None
                
                self.logger.debug(f"Retrieved stored credentials for {host}/{database}")
                return credentials
            
        except Exception as e:
            self.logger.error(f"Failed to get stored credentials: {e}")
        
        return None
    
    def store_credentials(
        self,
        identity: str,
        token: str,
        host: str,
        database: str
    ) -> None:
        """
        Store authentication credentials securely.
        
        Args:
            identity: SpacetimeDB identity
            token: JWT token
            host: Server host
            database: Database name
        """
        try:
            with self._lock:
                # Store in secure storage
                self.storage.store_credentials(identity, token, host, database)
                
                # Update current credentials
                self._current_credentials = AuthenticationCredentials(
                    identity=identity,
                    token=token,
                    host=host,
                    database=database,
                    timestamp=time.time()
                )
                
                # Update state
                self._state = AuthenticationState.AUTHENTICATED
                self._retry_count = 0
                self._last_error = None
                
                # Schedule refresh
                self._schedule_token_refresh(self._current_credentials)
                
                # Emit event
                self._emit_event(AuthenticationEvent(
                    state=self._state,
                    identity=identity,
                    host=host,
                    database=database,
                    data={"stored": True}
                ))
                
                self.logger.info(f"Stored credentials for {host}/{database} (identity: {identity[:8]}...)")
        
        except Exception as e:
            self.logger.error(f"Failed to store credentials: {e}")
            raise
    
    def prepare_jwt_headers(
        self,
        host: str,
        database: str,
        require_fresh: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Prepare JWT authentication headers.
        
        Args:
            host: Server host
            database: Database name
            require_fresh: Whether to require non-expired credentials
            
        Returns:
            Authentication headers or None if not available
        """
        try:
            with self._lock:
                credentials = self._current_credentials
                
                # Get stored credentials if not current
                if not credentials:
                    credentials = self.get_stored_credentials(host, database, not require_fresh)
                    if credentials:
                        self._current_credentials = credentials
                
                if not credentials:
                    self.logger.debug(f"No credentials available for {host}/{database}")
                    return None
                
                # Check expiry
                if require_fresh and credentials.is_expired:
                    self.logger.debug(f"Credentials for {host}/{database} are expired")
                    return None
                
                headers = {"Authorization": f"Bearer {credentials.token}"}
                
                self.logger.debug(f"Prepared JWT authentication for {host}/{database}")
                return headers
        
        except Exception as e:
            self.logger.error(f"Failed to prepare JWT headers: {e}")
            return None
    
    def handle_authentication_handshake(
        self,
        error_message: str,
        host: str,
        database: str
    ) -> bool:
        """
        Handle SpacetimeDB authentication handshake.
        
        Args:
            error_message: WebSocket error message
            host: Server host
            database: Database name
            
        Returns:
            True if handshake was handled and retry should be attempted
        """
        try:
            with self._authentication_context(host, database):
                # Parse handshake headers from error message
                headers = self._parse_handshake_headers(error_message)
                
                identity = headers.get("spacetime-identity")
                token = headers.get("spacetime-identity-token")
                
                if not identity or not token:
                    self.logger.warning("Invalid authentication handshake: missing identity or token")
                    return False
                
                self.logger.info(f"Handling authentication handshake for {host}/{database}")
                self.logger.debug(f"Received identity: {identity[:8]}...")
                
                # Store credentials
                self.store_credentials(identity, token, host, database)
                
                # Reset retry count for successful handshake
                self._retry_count = 0
                
                return True
        
        except Exception as e:
            self.logger.error(f"Failed to handle authentication handshake: {e}")
            return False
    
    def _parse_handshake_headers(self, error_message: str) -> Dict[str, str]:
        """Parse authentication headers from WebSocket error message."""
        headers = {}
        
        # Extract identity
        identity_match = re.search(r"spacetime-identity:\s*([a-fA-F0-9]+)", error_message)
        if identity_match:
            headers["spacetime-identity"] = identity_match.group(1)
        
        # Extract token
        token_match = re.search(r"spacetime-identity-token:\s*([\w.-]+)", error_message)
        if token_match:
            headers["spacetime-identity-token"] = token_match.group(1)
        
        return headers
    
    def should_retry_authentication(self, error_code: int) -> bool:
        """
        Check if authentication should be retried.
        
        Args:
            error_code: HTTP error code
            
        Returns:
            True if retry should be attempted
        """
        with self._lock:
            if self._retry_count >= self.max_retry_attempts:
                self.logger.warning(f"Max retry attempts ({self.max_retry_attempts}) reached")
                return False
            
            # Retry on authentication-related errors
            if error_code in [400, 401, 403]:
                self._retry_count += 1
                self.logger.debug(f"Retry attempt {self._retry_count} for error {error_code}")
                return True
            
            return False
    
    def clear_credentials(self, host: str, database: str) -> None:
        """
        Clear stored credentials.
        
        Args:
            host: Server host
            database: Database name
        """
        try:
            with self._lock:
                # Clear from storage
                self.storage.remove_credentials(host, database)
                
                # Clear current credentials if matching
                if (self._current_credentials and 
                    self._current_credentials.host == host and
                    self._current_credentials.database == database):
                    self._current_credentials = None
                
                # Update state
                self._state = AuthenticationState.UNAUTHENTICATED
                self._retry_count = 0
                self._last_error = None
                
                # Cancel refresh timer
                if self._refresh_timer:
                    self._refresh_timer.cancel()
                    self._refresh_timer = None
                
                # Emit event
                self._emit_event(AuthenticationEvent(
                    state=self._state,
                    host=host,
                    database=database,
                    data={"cleared": True}
                ))
                
                self.logger.info(f"Cleared credentials for {host}/{database}")
        
        except Exception as e:
            self.logger.error(f"Failed to clear credentials: {e}")
    
    def get_authentication_state(self) -> AuthenticationState:
        """Get current authentication state."""
        with self._lock:
            return self._state
    
    def get_current_credentials(self) -> Optional[AuthenticationCredentials]:
        """Get current authentication credentials."""
        with self._lock:
            return self._current_credentials
    
    def add_refresh_callback(self, callback: Callable[[AuthenticationCredentials], None]) -> None:
        """
        Add callback for token refresh events.
        
        Args:
            callback: Callback function to be called when token refresh is needed
        """
        with self._lock:
            self._refresh_callbacks.append(callback)
    
    def remove_refresh_callback(self, callback: Callable[[AuthenticationCredentials], None]) -> None:
        """
        Remove token refresh callback.
        
        Args:
            callback: Callback function to remove
        """
        with self._lock:
            if callback in self._refresh_callbacks:
                self._refresh_callbacks.remove(callback)
    
    def get_authentication_info(self) -> Dict[str, Any]:
        """
        Get comprehensive authentication information.
        
        Returns:
            Dictionary with authentication status and metadata
        """
        with self._lock:
            info = {
                "state": self._state.value,
                "retry_count": self._retry_count,
                "last_error": self._last_error,
                "auto_refresh_enabled": self.auto_refresh_tokens,
                "refresh_threshold_seconds": self.token_refresh_threshold,
                "max_retry_attempts": self.max_retry_attempts
            }
            
            if self._current_credentials:
                info.update({
                    "current_identity": self._current_credentials.identity[:8] + "...",
                    "current_host": self._current_credentials.host,
                    "current_database": self._current_credentials.database,
                    "credentials_age_seconds": time.time() - self._current_credentials.timestamp,
                    "credentials_expired": self._current_credentials.is_expired,
                    "time_until_expiry": self._current_credentials.time_until_expiry
                })
            
            # Add storage info
            try:
                storage_info = self.storage.get_storage_info()
                info["storage"] = storage_info
            except Exception as e:
                info["storage_error"] = str(e)
            
            return info
    
    def shutdown(self) -> None:
        """Shutdown authentication handler and cleanup resources."""
        try:
            with self._lock:
                # Cancel refresh timer
                if self._refresh_timer:
                    self._refresh_timer.cancel()
                    self._refresh_timer = None
                
                # Clear callbacks
                self._refresh_callbacks.clear()
                
                # Clear state
                self._state = AuthenticationState.UNAUTHENTICATED
                self._current_credentials = None
                
                self.logger.info("Authentication handler shutdown complete")
        
        except Exception as e:
            self.logger.error(f"Error during authentication handler shutdown: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()