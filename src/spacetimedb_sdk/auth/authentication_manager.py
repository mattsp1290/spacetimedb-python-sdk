"""
AuthenticationManager for SpacetimeDB SDK

This module provides centralized authentication flow management extracted from
WebSocketClient. It handles authentication state, credential management, and
integration with the existing Phase 2 secure authentication components.

Features:
- Single responsibility: Authentication flow management only
- Integration with SecureAuthStorage from Phase 2
- Thread-safe authentication operations  
- Authentication state management with proper transitions
- Event emission for authentication status changes
- Secure credential verification with timing attack protection
"""

import logging
import threading
import time
from enum import Enum
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass

from .storage import SecureAuthStorage, AuthCredentials
from .secure_verification import SecureVerificationManager, verify_credentials_secure

# Import AuthenticationState and Handler directly to avoid circular imports
try:
    from ..connection.authentication_handler import AuthenticationState, AuthenticationHandler
except ImportError:
    # Create fallback for when the full connection module isn't available
    from enum import Enum
    class AuthenticationState(Enum):
        UNAUTHENTICATED = "unauthenticated"
        AUTHENTICATING = "authenticating"
        AUTHENTICATED = "authenticated"
        FAILED = "failed"
        EXPIRED = "expired"
    
    class AuthenticationHandler:
        def __init__(self, storage):
            self.storage = storage
            self.state = AuthenticationState.UNAUTHENTICATED
            
        def authenticate(self, token, identity=None):
            return True
            
        def get_state(self):
            return self.state
            
        def refresh_credentials(self, identity, token):
            # Fallback handler doesn't support refresh
            return False

# Import these conditionally to avoid circular imports
try:
    from ..events.enhanced_event_system import EventManager, Event, EventType, EventPriority
    from ..exceptions import AuthenticationError
    from ..utils.error_formatting import ErrorFormatter
    from ..monitoring import get_global_monitor, monitor_performance
except ImportError:
    
    class EventManager:
        def emit(self, event):
            pass
    
    class Event:
        def __init__(self, event_type, data=None):
            self.event_type = event_type
            self.data = data or {}
    
    class EventType(Enum):
        AUTHENTICATION = "authentication"
    
    class EventPriority(Enum):
        NORMAL = 5
    
    AuthenticationError = Exception
    
    def ErrorFormatter_format_websocket_error(operation, error):
        return f"{operation}: {error}"
    
    def monitor_performance(name):
        def decorator(func):
            return func
        return decorator
    
    def get_global_monitor():
        return None


@dataclass
class AuthenticationResult:
    """Result of an authentication operation."""
    success: bool
    identity: Optional[str] = None
    token: Optional[str] = None
    error: Optional[str] = None
    requires_handshake: bool = False


class AuthenticationManager:
    """
    Handles authentication flow management for SpacetimeDB connections.
    
    This class extracts authentication logic from WebSocketClient and provides
    a focused interface for authentication operations while integrating with
    existing Phase 2 secure authentication components.
    """
    
    def __init__(
        self,
        host: str,
        database: str,
        storage: Optional[SecureAuthStorage] = None,
        event_manager: Optional[EventManager] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize AuthenticationManager.
        
        Args:
            host: Database host
            database: Database name
            storage: Secure storage instance (uses global if None)
            event_manager: Event manager for auth events
            logger: Logger instance
        """
        self.host = host
        self.database = database
        self._storage = storage or self._get_global_storage()
        self._event_manager = event_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Authentication state
        self._lock = threading.RLock()
        self._auth_state = AuthenticationState.UNAUTHENTICATED
        self._identity: Optional[str] = None
        self._token: Optional[str] = None
        self._handshake_completed = False
        self._credentials_timestamp: Optional[float] = None
        
        # Initialize Phase 2 components
        self._handler = AuthenticationHandler(self._storage) if self._storage else None
        self._verifier = SecureVerificationManager()
        
        # Load existing credentials
        self._load_stored_credentials()
    
    def _get_global_storage(self) -> Optional[SecureAuthStorage]:
        """Get global auth storage instance."""
        try:
            # Import here to avoid circular imports
            from ..websocket_client import _global_auth_storage
            if _global_auth_storage is None:
                return SecureAuthStorage()
            return _global_auth_storage
        except ImportError:
            return SecureAuthStorage()
    
    def _load_stored_credentials(self) -> None:
        """Load stored credentials if available."""
        if not self._storage:
            return
            
        try:
            credentials = self._storage.get_credentials(
                self.host, 
                self.database, 
                allow_expired=False
            )
            
            if credentials and not credentials.is_expired():
                with self._lock:
                    self._identity = credentials.identity
                    self._token = credentials.token
                    self._handshake_completed = True
                    self._credentials_timestamp = credentials.timestamp
                    self._auth_state = AuthenticationState.AUTHENTICATED
                
                self.logger.info(
                    f"Loaded stored credentials for {self.host}/{self.database}"
                )
                self._emit_auth_event(AuthenticationState.AUTHENTICATED)
            else:
                self.logger.debug("No valid stored credentials found")
                
        except Exception as e:
            self.logger.warning(f"Failed to load stored credentials: {e}")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        with self._lock:
            # Use value comparison to handle different AuthenticationState enum instances
            state_is_authenticated = (
                hasattr(self._auth_state, 'value') and 
                self._auth_state.value == "authenticated"
            ) or (
                hasattr(self._auth_state, 'name') and 
                self._auth_state.name == "AUTHENTICATED"
            )
            
            return (
                state_is_authenticated and
                self._identity is not None and
                self._token is not None and
                self._handshake_completed
            )
    
    @property  
    def authentication_state(self) -> AuthenticationState:
        """Get current authentication state."""
        with self._lock:
            return self._auth_state
    
    @property
    def identity(self) -> Optional[str]:
        """Get current identity."""
        with self._lock:
            return self._identity
    
    @property
    def token(self) -> Optional[str]:
        """Get current token."""
        with self._lock:
            return self._token
    
    @property 
    def handshake_completed(self) -> bool:
        """Check if authentication handshake is completed."""
        with self._lock:
            return self._handshake_completed
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for WebSocket connection.
        
        Returns:
            Dict containing Authorization header if authenticated
        """
        with self._lock:
            if self.is_authenticated:
                return {"Authorization": f"Bearer {self._token}"}
            return {}
    
    @monitor_performance("auth_handshake")
    def handle_auth_handshake(
        self, 
        identity: str, 
        token: str
    ) -> AuthenticationResult:
        """
        Handle SpacetimeDB authentication handshake.
        
        This processes the 400 status code response with spacetime-identity-token
        header that SpacetimeDB sends during authentication handshake.
        
        Args:
            identity: Identity from spacetime-identity header
            token: Token from spacetime-identity-token header
            
        Returns:
            AuthenticationResult with handshake outcome
        """
        try:
            self.logger.info("Processing SpacetimeDB authentication handshake")
            
            # Validate credentials format
            if not identity or not token:
                return AuthenticationResult(
                    success=False,
                    error="Invalid credentials: missing identity or token"
                )
            
            # Use secure verification
            verification_result = self._verifier.verify_token_format(token)
            if not verification_result.is_valid:
                return AuthenticationResult(
                    success=False,
                    error=f"Token validation failed: {verification_result.error}"
                )
            
            # Store credentials securely
            with self._lock:
                self._identity = identity
                self._token = token
                self._handshake_completed = True
                self._credentials_timestamp = time.time()
                self._auth_state = AuthenticationState.AUTHENTICATED
            
            # Persist credentials for future use
            if self._storage:
                try:
                    credentials = AuthCredentials(
                        identity=identity,
                        token=token,
                        host=self.host,
                        database=self.database,
                        timestamp=time.time()
                    )
                    self._storage.store_credentials(
                        identity, token, self.host, self.database
                    )
                    self.logger.debug("Stored credentials for future use")
                except Exception as store_error:
                    self.logger.warning(f"Failed to store credentials: {store_error}")
            
            # Emit authentication event
            self._emit_auth_event(AuthenticationState.AUTHENTICATED)
            
            self.logger.info("Authentication handshake completed successfully")
            return AuthenticationResult(
                success=True,
                identity=identity,
                token=token
            )
            
        except Exception as e:
            error_msg = f"Authentication handshake failed: {e}"
            if 'ErrorFormatter' in globals():
                self.logger.error(ErrorFormatter.format_websocket_error("auth_handshake", e))
            else:
                self.logger.error(ErrorFormatter_format_websocket_error("auth_handshake", e))
            
            with self._lock:
                self._auth_state = AuthenticationState.FAILED
            
            self._emit_auth_event(
                AuthenticationState.FAILED, 
                error=error_msg
            )
            
            return AuthenticationResult(
                success=False,
                error=error_msg
            )
    
    @monitor_performance("auth_authenticate")
    def authenticate(self, credentials: Optional[AuthCredentials] = None) -> AuthenticationResult:
        """
        Authenticate with provided or stored credentials.
        
        Args:
            credentials: Optional credentials to use (uses stored if None)
            
        Returns:
            AuthenticationResult with authentication outcome
        """
        try:
            with self._lock:
                self._auth_state = AuthenticationState.AUTHENTICATING
            
            self._emit_auth_event(AuthenticationState.AUTHENTICATING)
            
            # Use provided credentials or load from storage
            if credentials is None:
                if self._storage:
                    credentials = self._storage.get_credentials(
                        self.host, 
                        self.database, 
                        allow_expired=False
                    )
                    
                if not credentials or credentials.is_expired():
                    with self._lock:
                        self._auth_state = AuthenticationState.UNAUTHENTICATED
                    
                    return AuthenticationResult(
                        success=False,
                        error="No valid credentials available",
                        requires_handshake=True
                    )
            
            # Verify credentials using secure verification
            if self._verifier:
                verification_result = verify_credentials_secure(
                    credentials.identity,
                    credentials.token
                )
                
                if not verification_result.success:
                    with self._lock:
                        self._auth_state = AuthenticationState.FAILED
                        
                    self._emit_auth_event(
                        AuthenticationState.FAILED,
                        error="Credential verification failed"
                    )
                    
                    return AuthenticationResult(
                        success=False,
                        error="Credential verification failed"
                    )
            
            # Update authentication state
            with self._lock:
                self._identity = credentials.identity
                self._token = credentials.token
                self._handshake_completed = True
                self._credentials_timestamp = credentials.timestamp
                self._auth_state = AuthenticationState.AUTHENTICATED
            
            self._emit_auth_event(AuthenticationState.AUTHENTICATED)
            
            return AuthenticationResult(
                success=True,
                identity=credentials.identity,
                token=credentials.token
            )
            
        except Exception as e:
            error_msg = f"Authentication failed: {e}"
            if 'ErrorFormatter' in globals():
                self.logger.error(ErrorFormatter.format_websocket_error("authenticate", e))
            else:
                self.logger.error(ErrorFormatter_format_websocket_error("authenticate", e))
            
            with self._lock:
                self._auth_state = AuthenticationState.FAILED
            
            self._emit_auth_event(
                AuthenticationState.FAILED,
                error=error_msg
            )
            
            return AuthenticationResult(
                success=False,
                error=error_msg
            )
    
    @monitor_performance("auth_refresh_token")
    def refresh_token(self) -> AuthenticationResult:
        """
        Refresh authentication token.
        
        Returns:
            AuthenticationResult with refresh outcome
        """
        try:
            if not self.is_authenticated:
                return AuthenticationResult(
                    success=False,
                    error="Not authenticated - cannot refresh token"
                )
            
            # For SpacetimeDB, token refresh typically requires re-handshake
            # This is a placeholder for future token refresh logic
            with self._lock:
                current_identity = self._identity
                current_token = self._token
            
            if self._handler:
                # Use Phase 2 authentication handler for refresh
                refresh_result = self._handler.refresh_credentials(
                    current_identity, 
                    current_token
                )
                
                if refresh_result:
                    return AuthenticationResult(
                        success=True,
                        identity=current_identity,
                        token=current_token
                    )
            
            # Currently, SpacetimeDB requires full re-authentication
            return AuthenticationResult(
                success=False,
                error="Token refresh not supported - requires re-authentication",
                requires_handshake=True
            )
            
        except Exception as e:
            error_msg = f"Token refresh failed: {e}"
            if 'ErrorFormatter' in globals():
                self.logger.error(ErrorFormatter.format_websocket_error("refresh_token", e))
            else:
                self.logger.error(ErrorFormatter_format_websocket_error("refresh_token", e))
            
            return AuthenticationResult(
                success=False,
                error=error_msg
            )
    
    def logout(self) -> None:
        """
        Log out and clear authentication state.
        
        Note: This clears in-memory state but preserves stored credentials
        for potential future use.
        """
        try:
            self.logger.info("Logging out and clearing authentication state")
            
            with self._lock:
                # Clear in-memory state
                self._identity = None
                self._token = None
                self._handshake_completed = False
                self._credentials_timestamp = None
                self._auth_state = AuthenticationState.UNAUTHENTICATED
            
            # Emit logout event
            self._emit_auth_event(AuthenticationState.UNAUTHENTICATED)
            
            self.logger.info("Logout completed")
            
        except Exception as e:
            if 'ErrorFormatter' in globals():
                self.logger.error(ErrorFormatter.format_websocket_error("logout", e))
            else:
                self.logger.error(ErrorFormatter_format_websocket_error("logout", e))
    
    def clear_stored_credentials(self) -> None:
        """
        Clear stored credentials from secure storage.
        
        This removes credentials from persistent storage completely.
        """
        try:
            if self._storage:
                self._storage.clear_credentials(self.host, self.database)
                self.logger.info("Cleared stored credentials")
            
            # Also clear in-memory state
            self.logout()
            
        except Exception as e:
            self.logger.error(f"Failed to clear stored credentials: {e}")
    
    def get_auth_info(self) -> Dict[str, Any]:
        """
        Get authentication information for debugging/monitoring.
        
        Returns:
            Dict with authentication status info (no sensitive data)
        """
        with self._lock:
            return {
                "state": self._auth_state.value,
                "is_authenticated": self.is_authenticated,
                "handshake_completed": self._handshake_completed,
                "has_identity": self._identity is not None,
                "has_token": self._token is not None,
                "credentials_age_seconds": (
                    time.time() - self._credentials_timestamp 
                    if self._credentials_timestamp else None
                ),
                "host": self.host,
                "database": self.database
            }
    
    def _emit_auth_event(
        self, 
        state: AuthenticationState, 
        error: Optional[str] = None
    ) -> None:
        """Emit authentication event if event manager is available."""
        if not self._event_manager:
            return
            
        try:
            # Try to import AuthenticationEvent if not in fallback mode
            try:
                from ..connection.authentication_handler import AuthenticationEvent
                from ..events.enhanced_event_system import EventType as ET, EventPriority as EP
                
                event = AuthenticationEvent(
                    event_type=ET.AUTHENTICATION,
                    priority=EP.HIGH,
                    state=state,
                    identity=self._identity,
                    host=self.host,
                    database=self.database,
                    error=error
                )
                
                self._event_manager.emit_event(event)
            except (ImportError, NameError):
                # Fallback: create a simple event dict and emit it
                event_data = {
                    'state': state.value if hasattr(state, 'value') else str(state),
                    'identity': self._identity,
                    'host': self.host,
                    'database': self.database,
                    'error': error
                }
                self._event_manager.emit_event(event_data)
            
        except Exception as e:
            self.logger.warning(f"Failed to emit authentication event: {e}")
    
    def __str__(self) -> str:
        """String representation for debugging."""
        with self._lock:
            return (
                f"AuthenticationManager("
                f"host={self.host}, "
                f"database={self.database}, "
                f"state={self._auth_state.value}, "
                f"authenticated={self.is_authenticated})"
            )