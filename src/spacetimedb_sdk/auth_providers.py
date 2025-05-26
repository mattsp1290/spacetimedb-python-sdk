"""
Authentication Providers for SpacetimeDB

Provides comprehensive authentication support including:
- OAuth 2.0 / OpenID Connect
- JWT token handling
- SAML authentication
- API key authentication
- Multi-factor authentication hooks
- Token exchange protocols
"""

import json
import time
import base64
import logging
import threading
import secrets
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, parse_qs, urlparse

# JWT and cryptography imports
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    jwt = None

# OAuth imports
try:
    from requests_oauthlib import OAuth2Session
    HAS_OAUTH = True
except ImportError:
    HAS_OAUTH = False
    OAuth2Session = None

# SAML imports
try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.utils import OneLogin_Saml2_Utils
    HAS_SAML = True
except ImportError:
    HAS_SAML = False
    OneLogin_Saml2_Auth = None
    OneLogin_Saml2_Utils = None

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

from .secure_storage import SecureToken, SecureStorage, create_secure_token


class AuthMethod(Enum):
    """Supported authentication methods."""
    OAUTH2 = "oauth2"
    JWT = "jwt"
    SAML = "saml"
    API_KEY = "api_key"
    BASIC = "basic"
    CUSTOM = "custom"


class OAuth2Flow(Enum):
    """OAuth 2.0 flow types."""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    IMPLICIT = "implicit"
    PASSWORD = "password"
    DEVICE_CODE = "device_code"


@dataclass
class AuthConfig:
    """Base authentication configuration."""
    method: AuthMethod
    name: str
    priority: int = 0  # Higher priority providers are tried first
    enabled: bool = True
    timeout: float = 30.0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OAuth2Config(AuthConfig):
    """OAuth 2.0 configuration."""
    client_id: str = ""
    client_secret: Optional[str] = None
    authorization_url: str = ""
    token_url: str = ""
    redirect_uri: str = "http://localhost:8080/callback"
    scope: List[str] = field(default_factory=list)
    flow: OAuth2Flow = OAuth2Flow.AUTHORIZATION_CODE
    
    # Additional OAuth settings
    audience: Optional[str] = None
    resource: Optional[str] = None
    response_type: str = "code"
    grant_type: Optional[str] = None
    
    # PKCE settings
    use_pkce: bool = True
    code_challenge_method: str = "S256"
    
    # Token settings
    access_token_name: str = "access_token"
    refresh_token_name: str = "refresh_token"
    
    def __post_init__(self):
        self.method = AuthMethod.OAUTH2


@dataclass
class JWTConfig(AuthConfig):
    """JWT configuration."""
    issuer: Optional[str] = None
    audience: Optional[str] = None
    algorithm: str = "RS256"
    secret_key: Optional[str] = None  # For HMAC algorithms
    public_key: Optional[str] = None  # For RSA/EC algorithms
    private_key: Optional[str] = None  # For signing
    
    # Validation settings
    verify_signature: bool = True
    verify_exp: bool = True
    verify_iat: bool = True
    verify_aud: bool = True
    verify_iss: bool = True
    leeway: int = 0  # Clock skew tolerance in seconds
    
    # Token creation settings
    token_lifetime: int = 3600  # 1 hour
    refresh_lifetime: int = 86400 * 30  # 30 days
    
    def __post_init__(self):
        self.method = AuthMethod.JWT


@dataclass
class SAMLConfig(AuthConfig):
    """SAML configuration."""
    entity_id: str = ""
    sso_url: str = ""
    slo_url: Optional[str] = None
    x509_cert: str = ""
    private_key: Optional[str] = None
    
    # Service Provider settings
    sp_entity_id: str = ""
    sp_acs_url: str = ""
    sp_sls_url: Optional[str] = None
    
    # Additional settings
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    authn_context: List[str] = field(default_factory=lambda: ["urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"])
    signature_algorithm: str = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
    digest_algorithm: str = "http://www.w3.org/2001/04/xmlenc#sha256"
    
    def __post_init__(self):
        self.method = AuthMethod.SAML


@dataclass
class APIKeyConfig(AuthConfig):
    """API key configuration."""
    api_key: str = ""
    header_name: str = "X-API-Key"
    query_param_name: Optional[str] = None
    use_bearer: bool = False
    
    def __post_init__(self):
        self.method = AuthMethod.API_KEY


class AuthProvider(ABC):
    """Base class for authentication providers."""
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._lock = threading.RLock()
        self._token_cache: Optional[SecureToken] = None
        
    @abstractmethod
    def authenticate(self, **kwargs) -> SecureToken:
        """Perform authentication and return token."""
        pass
    
    @abstractmethod
    def refresh_token(self, token: SecureToken) -> Optional[SecureToken]:
        """Refresh an existing token."""
        pass
    
    @abstractmethod
    def validate_token(self, token: SecureToken) -> bool:
        """Validate a token."""
        pass
    
    def revoke_token(self, token: SecureToken) -> bool:
        """Revoke a token (if supported)."""
        return True
    
    def get_auth_headers(self, token: SecureToken) -> Dict[str, str]:
        """Get authorization headers for requests."""
        return {"Authorization": f"Bearer {token.token}"}
    
    def _create_secure_token(
        self,
        access_token: str,
        expires_in: Optional[int] = None,
        refresh_token: Optional[str] = None,
        token_type: str = "bearer",
        scope: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SecureToken:
        """Create a SecureToken from authentication response."""
        return create_secure_token(
            token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            scopes=scope or []
        )


class OAuth2Provider(AuthProvider):
    """OAuth 2.0 authentication provider."""
    
    def __init__(self, config: OAuth2Config):
        super().__init__(config)
        self.config: OAuth2Config = config
        
        if not HAS_OAUTH:
            raise ImportError("requests-oauthlib required for OAuth2 support")
        
        self._session: Optional[OAuth2Session] = None
        self._state: Optional[str] = None
        self._verifier: Optional[str] = None
        self._challenge: Optional[str] = None
    
    def authenticate(self, **kwargs) -> SecureToken:
        """Perform OAuth 2.0 authentication."""
        if self.config.flow == OAuth2Flow.AUTHORIZATION_CODE:
            return self._auth_code_flow(**kwargs)
        elif self.config.flow == OAuth2Flow.CLIENT_CREDENTIALS:
            return self._client_credentials_flow(**kwargs)
        elif self.config.flow == OAuth2Flow.PASSWORD:
            return self._password_flow(**kwargs)
        elif self.config.flow == OAuth2Flow.DEVICE_CODE:
            return self._device_code_flow(**kwargs)
        else:
            raise ValueError(f"Unsupported OAuth2 flow: {self.config.flow}")
    
    def _auth_code_flow(
        self,
        authorization_response: Optional[str] = None,
        state: Optional[str] = None
    ) -> SecureToken:
        """Authorization code flow."""
        if not authorization_response:
            # Step 1: Get authorization URL
            auth_url, state = self.get_authorization_url()
            self._state = state
            
            # Return a token indicating auth needed
            return SecureToken(
                token="",
                metadata={
                    "auth_required": True,
                    "auth_url": auth_url,
                    "state": state
                }
            )
        
        # Step 2: Exchange code for token
        self._session = OAuth2Session(
            self.config.client_id,
            redirect_uri=self.config.redirect_uri,
            state=state or self._state
        )
        
        token_data = self._session.fetch_token(
            self.config.token_url,
            authorization_response=authorization_response,
            client_secret=self.config.client_secret,
            timeout=self.config.timeout
        )
        
        return self._create_token_from_response(token_data)
    
    def _client_credentials_flow(self) -> SecureToken:
        """Client credentials flow."""
        auth = None
        if self.config.client_secret:
            auth = (self.config.client_id, self.config.client_secret)
        
        data = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
        }
        
        if self.config.scope:
            data["scope"] = " ".join(self.config.scope)
        
        response = requests.post(
            self.config.token_url,
            data=data,
            auth=auth,
            timeout=self.config.timeout
        )
        response.raise_for_status()
        
        return self._create_token_from_response(response.json())
    
    def _password_flow(self, username: str, password: str) -> SecureToken:
        """Resource owner password credentials flow."""
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": self.config.client_id,
        }
        
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        if self.config.scope:
            data["scope"] = " ".join(self.config.scope)
        
        response = requests.post(
            self.config.token_url,
            data=data,
            timeout=self.config.timeout
        )
        response.raise_for_status()
        
        return self._create_token_from_response(response.json())
    
    def _device_code_flow(self) -> SecureToken:
        """Device code flow for limited input devices."""
        # Step 1: Request device code
        data = {
            "client_id": self.config.client_id,
        }
        
        if self.config.scope:
            data["scope"] = " ".join(self.config.scope)
        
        response = requests.post(
            self.config.authorization_url.replace("/authorize", "/device/code"),
            data=data,
            timeout=self.config.timeout
        )
        response.raise_for_status()
        
        device_data = response.json()
        device_code = device_data["device_code"]
        user_code = device_data["user_code"]
        verification_uri = device_data["verification_uri"]
        interval = device_data.get("interval", 5)
        expires_in = device_data.get("expires_in", 900)
        
        # Return token with device flow info
        return SecureToken(
            token="",
            metadata={
                "device_flow": True,
                "device_code": device_code,
                "user_code": user_code,
                "verification_uri": verification_uri,
                "interval": interval,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            }
        )
    
    def poll_device_token(self, device_token: SecureToken) -> Optional[SecureToken]:
        """Poll for device code flow completion."""
        if not device_token.metadata.get("device_flow"):
            return None
        
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_token.metadata["device_code"],
            "client_id": self.config.client_id,
        }
        
        response = requests.post(
            self.config.token_url,
            data=data,
            timeout=self.config.timeout
        )
        
        if response.status_code == 200:
            return self._create_token_from_response(response.json())
        elif response.status_code == 400:
            error = response.json().get("error")
            if error == "authorization_pending":
                return None  # Keep polling
            elif error == "slow_down":
                # Increase polling interval
                device_token.metadata["interval"] *= 2
                return None
        
        response.raise_for_status()
        return None
    
    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """Get OAuth2 authorization URL."""
        self._session = OAuth2Session(
            self.config.client_id,
            redirect_uri=self.config.redirect_uri,
            scope=self.config.scope
        )
        
        # Generate PKCE challenge if enabled
        kwargs = {}
        if self.config.use_pkce:
            self._verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(self._verifier.encode('utf-8')).digest()
            ).decode('utf-8').rstrip('=')
            self._challenge = challenge
            
            kwargs["code_challenge"] = challenge
            kwargs["code_challenge_method"] = self.config.code_challenge_method
        
        auth_url, state = self._session.authorization_url(
            self.config.authorization_url,
            state=state,
            **kwargs
        )
        
        return auth_url, state
    
    def refresh_token(self, token: SecureToken) -> Optional[SecureToken]:
        """Refresh OAuth2 token."""
        if not token.refresh_token:
            return None
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": self.config.client_id,
        }
        
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        try:
            response = requests.post(
                self.config.token_url,
                data=data,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            return self._create_token_from_response(response.json())
            
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            return None
    
    def validate_token(self, token: SecureToken) -> bool:
        """Validate OAuth2 token."""
        # Basic validation - check expiry
        if token.is_expired():
            return False
        
        # Some providers have introspection endpoints
        # This is a simplified implementation
        return True
    
    def revoke_token(self, token: SecureToken) -> bool:
        """Revoke OAuth2 token."""
        # Try to find revocation endpoint
        revoke_url = self.config.token_url.replace("/token", "/revoke")
        
        data = {
            "token": token.token,
            "client_id": self.config.client_id,
        }
        
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        try:
            response = requests.post(
                revoke_url,
                data=data,
                timeout=self.config.timeout
            )
            return response.status_code == 200
        except:
            return False
    
    def _create_token_from_response(self, response_data: Dict[str, Any]) -> SecureToken:
        """Create SecureToken from OAuth2 response."""
        return self._create_secure_token(
            access_token=response_data[self.config.access_token_name],
            expires_in=response_data.get("expires_in"),
            refresh_token=response_data.get(self.config.refresh_token_name),
            token_type=response_data.get("token_type", "bearer"),
            scope=response_data.get("scope", "").split() if response_data.get("scope") else self.config.scope,
            metadata=response_data
        )


class JWTProvider(AuthProvider):
    """JWT authentication provider."""
    
    def __init__(self, config: JWTConfig):
        super().__init__(config)
        self.config: JWTConfig = config
        
        if not HAS_JWT:
            raise ImportError("PyJWT required for JWT support")
    
    def authenticate(self, **kwargs) -> SecureToken:
        """Create and sign a JWT token."""
        # Generate claims
        now = datetime.now(timezone.utc)
        claims = {
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.config.token_lifetime)).timestamp()),
            "jti": secrets.token_urlsafe(16),
        }
        
        # Add configured claims
        if self.config.issuer:
            claims["iss"] = self.config.issuer
        if self.config.audience:
            claims["aud"] = self.config.audience
        
        # Add custom claims
        claims.update(kwargs.get("claims", {}))
        
        # Sign token
        if self.config.algorithm.startswith("HS"):
            # HMAC algorithms
            if not self.config.secret_key:
                raise ValueError("Secret key required for HMAC algorithms")
            token = jwt.encode(claims, self.config.secret_key, algorithm=self.config.algorithm)
        else:
            # RSA/EC algorithms
            if not self.config.private_key:
                raise ValueError("Private key required for RSA/EC algorithms")
            token = jwt.encode(claims, self.config.private_key, algorithm=self.config.algorithm)
        
        return create_secure_token(
            token=token,
            expires_in=self.config.token_lifetime,
            scopes=kwargs.get("scopes", [])
        )
    
    def refresh_token(self, token: SecureToken) -> Optional[SecureToken]:
        """Refresh JWT token by creating a new one."""
        try:
            # Decode the old token to get claims
            if self.config.algorithm.startswith("HS"):
                payload = jwt.decode(
                    token.token,
                    self.config.secret_key,
                    algorithms=[self.config.algorithm],
                    options={"verify_exp": False}  # Allow expired tokens for refresh
                )
            else:
                payload = jwt.decode(
                    token.token,
                    self.config.public_key,
                    algorithms=[self.config.algorithm],
                    options={"verify_exp": False}
                )
            
            # Create new token with same claims
            return self.authenticate(claims=payload, scopes=token.scopes)
            
        except Exception as e:
            self.logger.error(f"JWT refresh failed: {e}")
            return None
    
    def validate_token(self, token: SecureToken) -> bool:
        """Validate JWT token."""
        try:
            # Determine key based on algorithm
            if self.config.algorithm.startswith("HS"):
                key = self.config.secret_key
            else:
                key = self.config.public_key
            
            # Decode and validate
            payload = jwt.decode(
                token.token,
                key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience if self.config.verify_aud else None,
                issuer=self.config.issuer if self.config.verify_iss else None,
                options={
                    "verify_signature": self.config.verify_signature,
                    "verify_exp": self.config.verify_exp,
                    "verify_iat": self.config.verify_iat,
                    "verify_aud": self.config.verify_aud,
                    "verify_iss": self.config.verify_iss,
                },
                leeway=self.config.leeway
            )
            
            return True
            
        except jwt.ExpiredSignatureError:
            self.logger.debug("JWT token expired")
            return False
        except jwt.InvalidTokenError as e:
            self.logger.debug(f"JWT validation failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"JWT validation error: {e}")
            return False
    
    def decode_token(self, token: str, verify: bool = True) -> Optional[Dict[str, Any]]:
        """Decode JWT token and return claims."""
        try:
            options = {
                "verify_signature": verify and self.config.verify_signature,
                "verify_exp": verify and self.config.verify_exp,
                "verify_iat": verify and self.config.verify_iat,
                "verify_aud": verify and self.config.verify_aud,
                "verify_iss": verify and self.config.verify_iss,
            }
            
            if self.config.algorithm.startswith("HS"):
                key = self.config.secret_key if verify else ""
            else:
                key = self.config.public_key if verify else ""
            
            return jwt.decode(
                token,
                key,
                algorithms=[self.config.algorithm] if verify else None,
                audience=self.config.audience if verify and self.config.verify_aud else None,
                issuer=self.config.issuer if verify and self.config.verify_iss else None,
                options=options,
                leeway=self.config.leeway
            )
        except Exception as e:
            self.logger.error(f"JWT decode error: {e}")
            return None


class SAMLProvider(AuthProvider):
    """SAML authentication provider."""
    
    def __init__(self, config: SAMLConfig):
        super().__init__(config)
        self.config: SAMLConfig = config
        
        if not HAS_SAML:
            raise ImportError("python3-saml required for SAML support")
    
    def authenticate(self, request_data: Dict[str, Any]) -> SecureToken:
        """Process SAML authentication."""
        # Initialize SAML auth
        auth = OneLogin_Saml2_Auth(request_data, self._get_saml_settings())
        
        # Process SAML response
        auth.process_response()
        
        if not auth.is_authenticated():
            errors = auth.get_errors()
            raise ValueError(f"SAML authentication failed: {errors}")
        
        # Get attributes
        attributes = auth.get_attributes()
        nameid = auth.get_nameid()
        session_index = auth.get_session_index()
        
        # Create token
        return create_secure_token(
            token=session_index or secrets.token_urlsafe(32),
            expires_in=3600,  # 1 hour default
            scopes=attributes.get("roles", []),
            metadata={
                "nameid": nameid,
                "attributes": attributes,
                "session_index": session_index,
            }
        )
    
    def refresh_token(self, token: SecureToken) -> Optional[SecureToken]:
        """SAML doesn't support token refresh."""
        return None
    
    def validate_token(self, token: SecureToken) -> bool:
        """Validate SAML token."""
        # Basic validation - in production, validate against IdP
        return not token.is_expired()
    
    def get_login_url(self, return_to: Optional[str] = None) -> str:
        """Get SAML login URL."""
        auth = OneLogin_Saml2_Auth({}, self._get_saml_settings())
        return auth.login(return_to=return_to)
    
    def get_logout_url(self, return_to: Optional[str] = None, nameid: Optional[str] = None) -> str:
        """Get SAML logout URL."""
        auth = OneLogin_Saml2_Auth({}, self._get_saml_settings())
        return auth.logout(return_to=return_to, name_id=nameid)
    
    def _get_saml_settings(self) -> Dict[str, Any]:
        """Get SAML settings dictionary."""
        return {
            "sp": {
                "entityId": self.config.sp_entity_id,
                "assertionConsumerService": {
                    "url": self.config.sp_acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                },
                "singleLogoutService": {
                    "url": self.config.sp_sls_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                } if self.config.sp_sls_url else None,
                "NameIDFormat": self.config.name_id_format,
                "x509cert": "",
                "privateKey": self.config.private_key or ""
            },
            "idp": {
                "entityId": self.config.entity_id,
                "singleSignOnService": {
                    "url": self.config.sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "singleLogoutService": {
                    "url": self.config.slo_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                } if self.config.slo_url else None,
                "x509cert": self.config.x509_cert
            },
            "security": {
                "nameIdEncrypted": False,
                "authnRequestsSigned": bool(self.config.private_key),
                "logoutRequestSigned": bool(self.config.private_key),
                "logoutResponseSigned": bool(self.config.private_key),
                "signMetadata": False,
                "wantMessagesSigned": True,
                "wantAssertionsSigned": True,
                "wantAssertionsEncrypted": False,
                "wantNameId": True,
                "wantNameIdEncrypted": False,
                "requestedAuthnContext": self.config.authn_context,
                "signatureAlgorithm": self.config.signature_algorithm,
                "digestAlgorithm": self.config.digest_algorithm,
            }
        }


class APIKeyProvider(AuthProvider):
    """API key authentication provider."""
    
    def __init__(self, config: APIKeyConfig):
        super().__init__(config)
        self.config: APIKeyConfig = config
    
    def authenticate(self, **kwargs) -> SecureToken:
        """Create token from API key."""
        api_key = kwargs.get("api_key", self.config.api_key)
        
        if not api_key:
            raise ValueError("API key required")
        
        return create_secure_token(
            token=api_key,
            expires_in=None,  # API keys don't expire
            scopes=kwargs.get("scopes", [])
        )
    
    def refresh_token(self, token: SecureToken) -> Optional[SecureToken]:
        """API keys don't need refresh."""
        return token
    
    def validate_token(self, token: SecureToken) -> bool:
        """Validate API key format."""
        # Basic validation - check format
        return len(token.token) > 0
    
    def get_auth_headers(self, token: SecureToken) -> Dict[str, str]:
        """Get API key headers."""
        if self.config.use_bearer:
            return {"Authorization": f"Bearer {token.token}"}
        elif self.config.header_name:
            return {self.config.header_name: token.token}
        else:
            return {}
    
    def get_auth_params(self, token: SecureToken) -> Dict[str, str]:
        """Get API key query parameters."""
        if self.config.query_param_name:
            return {self.config.query_param_name: token.token}
        return {}


class AuthProviderFactory:
    """Factory for creating authentication providers."""
    
    _providers: Dict[str, type] = {
        AuthMethod.OAUTH2: OAuth2Provider,
        AuthMethod.JWT: JWTProvider,
        AuthMethod.SAML: SAMLProvider,
        AuthMethod.API_KEY: APIKeyProvider,
    }
    
    @classmethod
    def create(cls, config: AuthConfig) -> AuthProvider:
        """Create an authentication provider from config."""
        provider_class = cls._providers.get(config.method)
        
        if not provider_class:
            raise ValueError(f"Unknown auth method: {config.method}")
        
        return provider_class(config)
    
    @classmethod
    def register(cls, method: AuthMethod, provider_class: type) -> None:
        """Register a custom authentication provider."""
        cls._providers[method] = provider_class


class MultiAuthProvider:
    """
    Manages multiple authentication providers with fallback support.
    
    Features:
    - Priority-based provider selection
    - Automatic fallback on failure
    - Token caching and management
    - Unified interface
    """
    
    def __init__(self, providers: List[AuthProvider], storage: Optional[SecureStorage] = None):
        self.providers = sorted(providers, key=lambda p: p.config.priority, reverse=True)
        self.storage = storage
        self._current_provider: Optional[AuthProvider] = None
        self._current_token: Optional[SecureToken] = None
        self.logger = logging.getLogger(__name__)
    
    def authenticate(self, **kwargs) -> SecureToken:
        """Authenticate using available providers."""
        errors = []
        
        for provider in self.providers:
            if not provider.config.enabled:
                continue
            
            try:
                self.logger.info(f"Attempting authentication with {provider.config.name}")
                token = provider.authenticate(**kwargs)
                
                # Cache successful provider and token
                self._current_provider = provider
                self._current_token = token
                
                # Store in secure storage if available
                if self.storage:
                    self.storage.store_token(
                        f"auth_{provider.config.name}",
                        token,
                        namespace="spacetimedb"
                    )
                
                return token
                
            except Exception as e:
                self.logger.warning(f"Authentication failed with {provider.config.name}: {e}")
                errors.append((provider.config.name, str(e)))
                continue
        
        # All providers failed
        error_msg = "; ".join([f"{name}: {err}" for name, err in errors])
        raise ValueError(f"All authentication providers failed: {error_msg}")
    
    def refresh_token(self, token: Optional[SecureToken] = None) -> Optional[SecureToken]:
        """Refresh token using the appropriate provider."""
        token = token or self._current_token
        
        if not token:
            return None
        
        # Try current provider first
        if self._current_provider:
            try:
                new_token = self._current_provider.refresh_token(token)
                if new_token:
                    self._current_token = new_token
                    return new_token
            except Exception as e:
                self.logger.warning(f"Token refresh failed with current provider: {e}")
        
        # Try all providers
        for provider in self.providers:
            if not provider.config.enabled:
                continue
            
            try:
                new_token = provider.refresh_token(token)
                if new_token:
                    self._current_provider = provider
                    self._current_token = new_token
                    return new_token
            except:
                continue
        
        return None
    
    def validate_token(self, token: Optional[SecureToken] = None) -> bool:
        """Validate token using appropriate provider."""
        token = token or self._current_token
        
        if not token:
            return False
        
        # Try all enabled providers
        for provider in self.providers:
            if not provider.config.enabled:
                continue
            
            try:
                if provider.validate_token(token):
                    return True
            except:
                continue
        
        return False
    
    def get_auth_headers(self, token: Optional[SecureToken] = None) -> Dict[str, str]:
        """Get auth headers using current provider."""
        token = token or self._current_token
        
        if not token or not self._current_provider:
            return {}
        
        return self._current_provider.get_auth_headers(token)
    
    def add_provider(self, provider: AuthProvider) -> None:
        """Add a new authentication provider."""
        self.providers.append(provider)
        self.providers.sort(key=lambda p: p.config.priority, reverse=True)
    
    def remove_provider(self, name: str) -> bool:
        """Remove a provider by name."""
        original_count = len(self.providers)
        self.providers = [p for p in self.providers if p.config.name != name]
        return len(self.providers) < original_count
    
    def get_provider(self, name: str) -> Optional[AuthProvider]:
        """Get a provider by name."""
        for provider in self.providers:
            if provider.config.name == name:
                return provider
        return None


# MFA Support
class MFAMethod(Enum):
    """Multi-factor authentication methods."""
    TOTP = "totp"  # Time-based OTP
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    HARDWARE_KEY = "hardware_key"


@dataclass
class MFAConfig:
    """MFA configuration."""
    method: MFAMethod
    enabled: bool = True
    timeout: int = 300  # 5 minutes
    max_attempts: int = 3
    
    # TOTP settings
    totp_secret: Optional[str] = None
    totp_digits: int = 6
    totp_period: int = 30
    
    # SMS/Email settings
    phone_number: Optional[str] = None
    email_address: Optional[str] = None
    
    # Push settings
    push_service_url: Optional[str] = None
    device_id: Optional[str] = None


class MFAProvider:
    """Multi-factor authentication provider."""
    
    def __init__(self, config: MFAConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._pending_challenges: Dict[str, Dict[str, Any]] = {}
    
    def create_challenge(self, user_id: str, primary_token: SecureToken) -> str:
        """Create MFA challenge."""
        challenge_id = secrets.token_urlsafe(32)
        
        self._pending_challenges[challenge_id] = {
            "user_id": user_id,
            "primary_token": primary_token,
            "created_at": datetime.now(timezone.utc),
            "attempts": 0,
            "verified": False,
        }
        
        # Send challenge based on method
        if self.config.method == MFAMethod.TOTP:
            # TOTP doesn't need to send anything
            pass
        elif self.config.method == MFAMethod.SMS:
            self._send_sms_code(challenge_id)
        elif self.config.method == MFAMethod.EMAIL:
            self._send_email_code(challenge_id)
        elif self.config.method == MFAMethod.PUSH:
            self._send_push_notification(challenge_id)
        
        return challenge_id
    
    def verify_challenge(self, challenge_id: str, code: str) -> Optional[SecureToken]:
        """Verify MFA challenge."""
        if challenge_id not in self._pending_challenges:
            return None
        
        challenge = self._pending_challenges[challenge_id]
        
        # Check timeout
        elapsed = (datetime.now(timezone.utc) - challenge["created_at"]).total_seconds()
        if elapsed > self.config.timeout:
            del self._pending_challenges[challenge_id]
            return None
        
        # Check attempts
        challenge["attempts"] += 1
        if challenge["attempts"] > self.config.max_attempts:
            del self._pending_challenges[challenge_id]
            return None
        
        # Verify code
        if self._verify_code(challenge_id, code):
            challenge["verified"] = True
            primary_token = challenge["primary_token"]
            
            # Add MFA metadata to token
            primary_token.metadata["mfa_verified"] = True
            primary_token.metadata["mfa_method"] = self.config.method.value
            primary_token.metadata["mfa_verified_at"] = datetime.now(timezone.utc).isoformat()
            
            # Clean up
            del self._pending_challenges[challenge_id]
            
            return primary_token
        
        return None
    
    def _verify_code(self, challenge_id: str, code: str) -> bool:
        """Verify MFA code based on method."""
        if self.config.method == MFAMethod.TOTP:
            return self._verify_totp(code)
        else:
            # For demo purposes - in production, verify against sent codes
            return True
    
    def _verify_totp(self, code: str) -> bool:
        """Verify TOTP code."""
        try:
            import pyotp
            totp = pyotp.TOTP(self.config.totp_secret)
            return totp.verify(code, valid_window=1)
        except:
            return False
    
    def _send_sms_code(self, challenge_id: str) -> None:
        """Send SMS code (placeholder)."""
        self.logger.info(f"SMS code sent for challenge {challenge_id}")
    
    def _send_email_code(self, challenge_id: str) -> None:
        """Send email code (placeholder)."""
        self.logger.info(f"Email code sent for challenge {challenge_id}")
    
    def _send_push_notification(self, challenge_id: str) -> None:
        """Send push notification (placeholder)."""
        self.logger.info(f"Push notification sent for challenge {challenge_id}")


# Token Exchange
class TokenExchangeProvider:
    """
    Token exchange provider for converting between token types.
    
    Supports:
    - OAuth token to JWT
    - SAML assertion to OAuth token
    - API key to temporary token
    """
    
    def __init__(self, providers: Dict[str, AuthProvider]):
        self.providers = providers
        self.logger = logging.getLogger(__name__)
    
    def exchange_token(
        self,
        source_token: SecureToken,
        source_type: AuthMethod,
        target_type: AuthMethod,
        **kwargs
    ) -> Optional[SecureToken]:
        """Exchange one token type for another."""
        
        # Validate source token
        source_provider = self.providers.get(source_type.value)
        if not source_provider or not source_provider.validate_token(source_token):
            self.logger.error("Invalid source token")
            return None
        
        # Get target provider
        target_provider = self.providers.get(target_type.value)
        if not target_provider:
            self.logger.error(f"No provider for target type: {target_type}")
            return None
        
        # Perform exchange based on types
        if source_type == AuthMethod.OAUTH2 and target_type == AuthMethod.JWT:
            return self._oauth_to_jwt(source_token, target_provider, **kwargs)
        elif source_type == AuthMethod.SAML and target_type == AuthMethod.OAUTH2:
            return self._saml_to_oauth(source_token, target_provider, **kwargs)
        elif source_type == AuthMethod.API_KEY and target_type == AuthMethod.JWT:
            return self._apikey_to_jwt(source_token, target_provider, **kwargs)
        else:
            self.logger.error(f"Unsupported exchange: {source_type} -> {target_type}")
            return None
    
    def _oauth_to_jwt(
        self,
        oauth_token: SecureToken,
        jwt_provider: JWTProvider,
        **kwargs
    ) -> Optional[SecureToken]:
        """Convert OAuth token to JWT."""
        # Extract claims from OAuth token metadata
        claims = {
            "sub": oauth_token.metadata.get("sub", "oauth_user"),
            "scopes": oauth_token.scopes,
            "oauth_token_hash": hashlib.sha256(oauth_token.token.encode()).hexdigest()[:16],
        }
        
        return jwt_provider.authenticate(claims=claims, scopes=oauth_token.scopes)
    
    def _saml_to_oauth(
        self,
        saml_token: SecureToken,
        oauth_provider: OAuth2Provider,
        **kwargs
    ) -> Optional[SecureToken]:
        """Convert SAML assertion to OAuth token."""
        # This would typically involve a token exchange grant
        # For now, return a client credentials token
        return oauth_provider.authenticate()
    
    def _apikey_to_jwt(
        self,
        api_token: SecureToken,
        jwt_provider: JWTProvider,
        **kwargs
    ) -> Optional[SecureToken]:
        """Convert API key to temporary JWT."""
        claims = {
            "sub": f"apikey_{hashlib.sha256(api_token.token.encode()).hexdigest()[:8]}",
            "scopes": api_token.scopes or ["api"],
            "api_key_hint": api_token.token[:4] + "..." + api_token.token[-4:],
        }
        
        # Create short-lived JWT
        jwt_provider.config.token_lifetime = kwargs.get("lifetime", 3600)
        return jwt_provider.authenticate(claims=claims, scopes=api_token.scopes)
