"""
Authentication Providers for SpacetimeDB

This module provides different authentication providers for SpacetimeDB,
including JWT token authentication and identity-based authentication.
"""

import abc
import json
import jwt
import time
import logging
from typing import Optional, Dict, Any, Union, List
from datetime import datetime, timedelta


class AuthProvider(abc.ABC):
    """
    Abstract base class for authentication providers.
    
    Authentication providers handle the creation, validation, and management
    of authentication tokens for SpacetimeDB connections.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abc.abstractmethod
    def create_token(self, identity: str, **kwargs) -> str:
        """
        Create an authentication token.
        
        Args:
            identity: User identity
            **kwargs: Additional parameters for token creation
            
        Returns:
            Authentication token string
        """
        pass
    
    @abc.abstractmethod
    def validate_token(self, token: str, **kwargs) -> bool:
        """
        Validate an authentication token.
        
        Args:
            token: Authentication token to validate
            **kwargs: Additional parameters for validation
            
        Returns:
            True if token is valid, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def extract_identity(self, token: str) -> Optional[str]:
        """
        Extract identity from an authentication token.
        
        Args:
            token: Authentication token
            
        Returns:
            Identity string if extractable, None otherwise
        """
        pass
    
    @abc.abstractmethod
    def is_token_expired(self, token: str) -> bool:
        """
        Check if a token is expired.
        
        Args:
            token: Authentication token
            
        Returns:
            True if expired, False otherwise
        """
        pass


class JWTAuthProvider(AuthProvider):
    """
    JWT-based authentication provider for SpacetimeDB.
    
    This provider handles JWT (JSON Web Token) authentication tokens
    used by SpacetimeDB for secure authentication.
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        token_lifetime_hours: float = 24.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize JWT authentication provider.
        
        Args:
            secret_key: Secret key for JWT signing (None for validation-only)
            algorithm: JWT algorithm (default: HS256)
            token_lifetime_hours: Token lifetime in hours
            logger: Logger instance
        """
        super().__init__(logger)
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_lifetime_hours = token_lifetime_hours
    
    def create_token(
        self,
        identity: str,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Create a JWT token for the given identity.
        
        Args:
            identity: User identity
            audience: Token audience
            issuer: Token issuer
            additional_claims: Additional JWT claims
            **kwargs: Additional parameters
            
        Returns:
            JWT token string
            
        Raises:
            ValueError: If secret key is not provided
        """
        if not self.secret_key:
            raise ValueError("Secret key is required for token creation")
        
        now = datetime.utcnow()
        exp = now + timedelta(hours=self.token_lifetime_hours)
        
        payload = {
            'sub': identity,  # Subject (identity)
            'iat': now.timestamp(),  # Issued at
            'exp': exp.timestamp(),  # Expiration
        }
        
        if audience:
            payload['aud'] = audience
        
        if issuer:
            payload['iss'] = issuer
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        self.logger.debug(f"Created JWT token for identity {identity[:8]}...")
        return token
    
    def validate_token(
        self,
        token: str,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Validate a JWT token.
        
        Args:
            token: JWT token to validate
            audience: Expected audience
            issuer: Expected issuer
            **kwargs: Additional validation parameters
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            options = kwargs.get('options', {})
            
            # For validation without secret key, we can still check structure
            if not self.secret_key:
                # Basic structure validation
                parts = token.split('.')
                if len(parts) != 3:
                    return False
                
                # Try to decode payload without verification
                try:
                    payload = jwt.decode(token, options={"verify_signature": False})
                    
                    # Check expiration
                    if 'exp' in payload:
                        if datetime.utcnow().timestamp() > payload['exp']:
                            return False
                    
                    return True
                except:
                    return False
            
            # Full validation with secret key
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience=audience,
                issuer=issuer,
                options=options
            )
            
            self.logger.debug(f"Validated JWT token for identity {payload.get('sub', 'unknown')[:8]}...")
            return True
            
        except jwt.ExpiredSignatureError:
            self.logger.debug("JWT token has expired")
            return False
        except jwt.InvalidTokenError as e:
            self.logger.debug(f"Invalid JWT token: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error validating JWT token: {e}")
            return False
    
    def extract_identity(self, token: str) -> Optional[str]:
        """
        Extract identity from JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            Identity string if extractable, None otherwise
        """
        try:
            # Decode without verification to extract identity
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload.get('sub')
        except Exception as e:
            self.logger.error(f"Error extracting identity from JWT: {e}")
            return None
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if JWT token is expired.
        
        Args:
            token: JWT token
            
        Returns:
            True if expired, False otherwise
        """
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            
            if 'exp' in payload:
                return datetime.utcnow().timestamp() > payload['exp']
            
            # If no expiration claim, consider it expired
            return True
            
        except Exception:
            # If we can't decode, consider it expired
            return True
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get information about a JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            Dictionary with token information
        """
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            
            info = {
                'identity': payload.get('sub'),
                'issued_at': payload.get('iat'),
                'expires_at': payload.get('exp'),
                'audience': payload.get('aud'),
                'issuer': payload.get('iss'),
                'is_expired': self.is_token_expired(token)
            }
            
            if info['issued_at']:
                info['age_seconds'] = time.time() - info['issued_at']
            
            if info['expires_at']:
                info['expires_in_seconds'] = info['expires_at'] - time.time()
            
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting token info: {e}")
            return {'error': str(e)}


class IdentityAuthProvider(AuthProvider):
    """
    Identity-based authentication provider for SpacetimeDB.
    
    This provider handles simple identity-based authentication where
    the identity string itself serves as the authentication token.
    """
    
    def __init__(
        self,
        token_lifetime_hours: float = 24.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize identity authentication provider.
        
        Args:
            token_lifetime_hours: Token lifetime in hours
            logger: Logger instance
        """
        super().__init__(logger)
        self.token_lifetime_hours = token_lifetime_hours
        self._token_timestamps: Dict[str, float] = {}
    
    def create_token(
        self,
        identity: str,
        **kwargs
    ) -> str:
        """
        Create an identity-based token.
        
        Args:
            identity: User identity
            **kwargs: Additional parameters (ignored)
            
        Returns:
            Identity token string
        """
        # For identity-based auth, the token is the identity itself
        # We'll track when it was created for expiration purposes
        self._token_timestamps[identity] = time.time()
        
        self.logger.debug(f"Created identity token for {identity[:8]}...")
        return identity
    
    def validate_token(self, token: str, **kwargs) -> bool:
        """
        Validate an identity token.
        
        Args:
            token: Identity token to validate
            **kwargs: Additional parameters (ignored)
            
        Returns:
            True if token is valid, False otherwise
        """
        # Basic validation - check if it looks like a valid identity
        if not token or len(token) < 8:
            return False
        
        # Check if it's expired
        if self.is_token_expired(token):
            return False
        
        self.logger.debug(f"Validated identity token {token[:8]}...")
        return True
    
    def extract_identity(self, token: str) -> Optional[str]:
        """
        Extract identity from identity token.
        
        Args:
            token: Identity token
            
        Returns:
            Identity string (same as token)
        """
        return token if self.validate_token(token) else None
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if identity token is expired.
        
        Args:
            token: Identity token
            
        Returns:
            True if expired, False otherwise
        """
        timestamp = self._token_timestamps.get(token)
        if not timestamp:
            # If we don't have a timestamp, consider it expired
            return True
        
        age_seconds = time.time() - timestamp
        max_age_seconds = self.token_lifetime_hours * 3600
        
        return age_seconds > max_age_seconds
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get information about an identity token.
        
        Args:
            token: Identity token
            
        Returns:
            Dictionary with token information
        """
        timestamp = self._token_timestamps.get(token)
        
        info = {
            'identity': token,
            'issued_at': timestamp,
            'is_expired': self.is_token_expired(token)
        }
        
        if timestamp:
            info['age_seconds'] = time.time() - timestamp
            info['expires_in_seconds'] = (self.token_lifetime_hours * 3600) - info['age_seconds']
        
        return info


class AuthProviderFactory:
    """
    Factory class for creating authentication providers.
    """
    
    @staticmethod
    def create_provider(
        provider_type: str,
        **kwargs
    ) -> AuthProvider:
        """
        Create an authentication provider.
        
        Args:
            provider_type: Type of provider ('jwt' or 'identity')
            **kwargs: Provider-specific parameters
            
        Returns:
            Authentication provider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type.lower() == 'jwt':
            return JWTAuthProvider(**kwargs)
        elif provider_type.lower() == 'identity':
            return IdentityAuthProvider(**kwargs)
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    
    @staticmethod
    def get_available_providers() -> List[str]:
        """
        Get list of available provider types.
        
        Returns:
            List of provider type names
        """
        return ['jwt', 'identity']