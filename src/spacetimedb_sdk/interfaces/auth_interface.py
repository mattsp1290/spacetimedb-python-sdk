"""
Enhanced Authentication Interface for SpacetimeDB clients.

Combines authentication patterns from blackholio-python-client with the
production-ready features of spacetimedb-python-sdk.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timedelta


class AuthenticationState(Enum):
    """Authentication state enumeration."""
    UNAUTHENTICATED = "unauthenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    TOKEN_EXPIRED = "token_expired"
    REFRESHING = "refreshing"
    FAILED = "failed"


class TokenType(Enum):
    """Token type enumeration."""
    BEARER = "bearer"
    IDENTITY = "identity"
    API_KEY = "api_key"
    CUSTOM = "custom"


class AuthInterface(ABC):
    """
    Enhanced abstract interface for SpacetimeDB authentication management.
    
    This interface provides comprehensive authentication capabilities including
    token management, refresh mechanisms, and secure credential handling.
    """

    @property
    @abstractmethod
    def identity(self) -> Optional[str]:
        """
        Get the current user identity.
        
        Returns:
            Current identity string or None if not authenticated
        """
        pass

    @property
    @abstractmethod
    def token(self) -> Optional[str]:
        """
        Get the current authentication token.
        
        Returns:
            Current token string or None if not authenticated
        """
        pass

    @property
    @abstractmethod
    def token_type(self) -> Optional[TokenType]:
        """
        Get the current token type.
        
        Returns:
            Current token type or None if not authenticated
        """
        pass

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        pass

    @property
    @abstractmethod
    def is_token_valid(self) -> bool:
        """
        Check if current token is valid (not expired).
        
        Returns:
            True if token is valid, False otherwise
        """
        pass

    @property
    @abstractmethod
    def auth_state(self) -> AuthenticationState:
        """
        Get current authentication state.
        
        Returns:
            Current authentication state
        """
        pass

    @abstractmethod
    async def authenticate(
        self, 
        credentials: Optional[Dict[str, Any]] = None,
        auto_save: bool = True
    ) -> bool:
        """
        Authenticate with the SpacetimeDB server.
        
        Args:
            credentials: Optional credentials dictionary for authentication
            auto_save: Whether to automatically save token after authentication
            
        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    async def authenticate_with_token(
        self, 
        token: str, 
        token_type: TokenType = TokenType.BEARER
    ) -> bool:
        """
        Authenticate using an existing token.
        
        Args:
            token: Authentication token
            token_type: Type of the token
            
        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    async def logout(self, clear_saved: bool = True) -> bool:
        """
        Logout and clear authentication state.
        
        Args:
            clear_saved: Whether to clear saved tokens from disk
            
        Returns:
            True if logout successful, False otherwise
        """
        pass

    @abstractmethod
    def save_token(
        self, 
        file_path: Optional[str] = None,
        encrypt: bool = True
    ) -> bool:
        """
        Save the current authentication token to disk.
        
        Args:
            file_path: Optional custom file path for saving token
            encrypt: Whether to encrypt the token before saving
            
        Returns:
            True if save successful, False otherwise
        """
        pass

    @abstractmethod
    def load_token(
        self, 
        file_path: Optional[str] = None,
        decrypt: bool = True
    ) -> bool:
        """
        Load authentication token from disk.
        
        Args:
            file_path: Optional custom file path for loading token
            decrypt: Whether to decrypt the token after loading
            
        Returns:
            True if load successful, False otherwise
        """
        pass

    @abstractmethod
    def clear_saved_token(self, file_path: Optional[str] = None) -> bool:
        """
        Clear saved authentication token from disk.
        
        Args:
            file_path: Optional custom file path for token file
            
        Returns:
            True if clear successful, False otherwise
        """
        pass

    @abstractmethod
    def on_authentication_changed(
        self, 
        callback: Callable[[AuthenticationState], None]
    ) -> None:
        """
        Register a callback for authentication state changes.
        
        Args:
            callback: Function to call when authentication state changes
        """
        pass

    @abstractmethod
    def on_token_refresh(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback for token refresh events.
        
        Args:
            callback: Function to call when token is refreshed
        """
        pass

    @abstractmethod
    def on_token_expiring(
        self, 
        callback: Callable[[timedelta], None],
        warning_threshold: timedelta = timedelta(minutes=5)
    ) -> None:
        """
        Register a callback for token expiration warnings.
        
        Args:
            callback: Function to call when token is about to expire
            warning_threshold: How long before expiry to trigger warning
        """
        pass

    @abstractmethod
    def get_auth_info(self) -> Dict[str, Any]:
        """
        Get detailed authentication information.
        
        Returns:
            Dictionary containing auth details (identity, token status, etc.)
        """
        pass

    @abstractmethod
    async def refresh_token(self, force: bool = False) -> bool:
        """
        Refresh the current authentication token.
        
        Args:
            force: Whether to force refresh even if token is not near expiry
            
        Returns:
            True if refresh successful, False otherwise
        """
        pass

    @abstractmethod
    def validate_token(self, token: Optional[str] = None) -> bool:
        """
        Validate an authentication token.
        
        Args:
            token: Token to validate (uses current token if None)
            
        Returns:
            True if token is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_token_expiry(self) -> Optional[datetime]:
        """
        Get token expiration time.
        
        Returns:
            Token expiration datetime or None if unknown/no expiry
        """
        pass

    @abstractmethod
    def get_time_until_expiry(self) -> Optional[timedelta]:
        """
        Get time remaining until token expires.
        
        Returns:
            Time remaining until expiry or None if unknown/no expiry
        """
        pass

    @abstractmethod
    def enable_auto_refresh(
        self, 
        refresh_threshold: timedelta = timedelta(minutes=10)
    ) -> None:
        """
        Enable automatic token refresh.
        
        Args:
            refresh_threshold: How long before expiry to auto-refresh
        """
        pass

    @abstractmethod
    def disable_auto_refresh(self) -> None:
        """Disable automatic token refresh."""
        pass

    @abstractmethod
    def get_auth_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent authentication events.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of authentication events with timestamps
        """
        pass

    @abstractmethod
    async def revoke_token(self, token: Optional[str] = None) -> bool:
        """
        Revoke a token on the server.
        
        Args:
            token: Token to revoke (uses current token if None)
            
        Returns:
            True if revocation successful, False otherwise
        """
        pass

    @abstractmethod
    def get_permission_level(self) -> Optional[str]:
        """
        Get current permission level/role.
        
        Returns:
            Permission level string or None if unknown
        """
        pass