"""
Enhanced Connection Builder with Security Features

Integrates all security components into an easy-to-use builder pattern.
"""

from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from enum import Enum

from .connection_builder import SpacetimeDBConnectionBuilder
from .security_manager import (
    SecurityManager, SecurityConfig, CertificatePin, 
    TLSVersion, pin_from_string
)
from .secure_storage import (
    SecureStorage, StorageConfig, StorageBackend,
    SecureToken, create_secure_token
)
from .auth_providers import (
    AuthProvider, AuthProviderFactory, MultiAuthProvider,
    OAuth2Config, JWTConfig, SAMLConfig, APIKeyConfig,
    OAuth2Flow, AuthMethod, MFAProvider, MFAConfig, MFAMethod
)
from .security_audit import (
    SecurityAuditor, AuditConfig, ComplianceStandard,
    SecurityEventType, SeverityLevel
)


class EnhancedConnectionBuilder(SpacetimeDBConnectionBuilder):
    """
    Enhanced connection builder with comprehensive security features.
    
    Example:
        client = EnhancedConnectionBuilder()
            .with_uri("wss://mydb.spacetimedb.com")
            .with_certificate_pinning([
                "sha256//base64hash1",
                "sha256//base64hash2"
            ])
            .with_oauth2(
                client_id="my_client_id",
                client_secret="my_secret",
                authorization_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token"
            )
            .with_secure_storage()
            .with_audit_logging(
                compliance_standards=[ComplianceStandard.SOC2, ComplianceStandard.HIPAA]
            )
            .build()
    """
    
    def __init__(self):
        super().__init__()
        
        # Security components
        self._security_manager: Optional[SecurityManager] = None
        self._secure_storage: Optional[SecureStorage] = None
        self._auth_providers: List[AuthProvider] = []
        self._multi_auth: Optional[MultiAuthProvider] = None
        self._mfa_provider: Optional[MFAProvider] = None
        self._security_auditor: Optional[SecurityAuditor] = None
        
        # Security configuration
        self._security_config: Optional[SecurityConfig] = None
        self._storage_config: Optional[StorageConfig] = None
        self._audit_config: Optional[AuditConfig] = None
    
    # Certificate Pinning
    def with_certificate_pinning(
        self,
        pins: List[str],
        enforce: bool = True
    ) -> 'EnhancedConnectionBuilder':
        """
        Enable certificate pinning.
        
        Args:
            pins: List of pin strings in format "sha256//base64hash" or "sha256:hexhash"
            enforce: Whether to enforce pinning (fail if no pins match)
            
        Example:
            builder.with_certificate_pinning([
                "sha256//AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            ])
        """
        if not self._security_config:
            self._security_config = SecurityConfig()
        
        self._security_config.pins = [
            pin_from_string(pin_str) for pin_str in pins
        ]
        self._security_config.enforce_pinning = enforce
        
        return self
    
    def with_custom_ca(
        self,
        ca_bundle_path: Path,
        verify_hostname: bool = True
    ) -> 'EnhancedConnectionBuilder':
        """
        Use custom CA certificate bundle.
        
        Args:
            ca_bundle_path: Path to CA bundle file
            verify_hostname: Whether to verify hostname
        """
        if not self._security_config:
            self._security_config = SecurityConfig()
        
        self._security_config.custom_ca_bundle = ca_bundle_path
        self._security_config.check_hostname = verify_hostname
        
        return self
    
    def with_client_cert(
        self,
        cert_path: Path,
        key_path: Path,
        key_password: Optional[str] = None
    ) -> 'EnhancedConnectionBuilder':
        """
        Use client certificate authentication.
        
        Args:
            cert_path: Path to client certificate
            key_path: Path to private key
            key_password: Password for encrypted private key
        """
        if not self._security_config:
            self._security_config = SecurityConfig()
        
        self._security_config.client_cert = cert_path
        self._security_config.client_key = key_path
        self._security_config.client_key_password = key_password
        
        return self
    
    def with_tls_version(
        self,
        minimum: str = "1.2",
        maximum: Optional[str] = None
    ) -> 'EnhancedConnectionBuilder':
        """
        Set TLS version requirements.
        
        Args:
            minimum: Minimum TLS version ("1.2" or "1.3")
            maximum: Maximum TLS version (optional)
        """
        if not self._security_config:
            self._security_config = SecurityConfig()
        
        self._security_config.minimum_tls_version = TLSVersion.from_string(minimum)
        if maximum:
            self._security_config.maximum_tls_version = TLSVersion.from_string(maximum)
        
        return self
    
    # Authentication
    def with_oauth2(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
        authorization_url: Optional[str] = None,
        token_url: Optional[str] = None,
        flow: OAuth2Flow = OAuth2Flow.CLIENT_CREDENTIALS,
        scope: Optional[List[str]] = None,
        priority: int = 10
    ) -> 'EnhancedConnectionBuilder':
        """
        Add OAuth 2.0 authentication.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            authorization_url: Authorization endpoint (for auth code flow)
            token_url: Token endpoint
            flow: OAuth flow type
            scope: List of scopes
            priority: Provider priority (higher = tried first)
        """
        config = OAuth2Config(
            method=AuthMethod.OAUTH2,
            name="oauth2",
            priority=priority,
            client_id=client_id,
            client_secret=client_secret,
            authorization_url=authorization_url or "",
            token_url=token_url or "",
            flow=flow,
            scope=scope or []
        )
        
        provider = AuthProviderFactory.create(config)
        self._auth_providers.append(provider)
        
        return self
    
    def with_jwt(
        self,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        algorithm: str = "RS256",
        private_key: Optional[str] = None,
        public_key: Optional[str] = None,
        priority: int = 5
    ) -> 'EnhancedConnectionBuilder':
        """
        Add JWT authentication.
        
        Args:
            issuer: JWT issuer
            audience: JWT audience
            algorithm: JWT algorithm (HS256, RS256, etc.)
            private_key: Private key for signing
            public_key: Public key for verification
            priority: Provider priority
        """
        config = JWTConfig(
            method=AuthMethod.JWT,
            name="jwt",
            priority=priority,
            issuer=issuer,
            audience=audience,
            algorithm=algorithm,
            private_key=private_key,
            public_key=public_key
        )
        
        provider = AuthProviderFactory.create(config)
        self._auth_providers.append(provider)
        
        return self
    
    def with_api_key(
        self,
        api_key: str,
        header_name: str = "X-API-Key",
        use_bearer: bool = False,
        priority: int = 1
    ) -> 'EnhancedConnectionBuilder':
        """
        Add API key authentication.
        
        Args:
            api_key: The API key
            header_name: Header name for API key
            use_bearer: Use Bearer token format
            priority: Provider priority
        """
        config = APIKeyConfig(
            method=AuthMethod.API_KEY,
            name="api_key",
            priority=priority,
            api_key=api_key,
            header_name=header_name,
            use_bearer=use_bearer
        )
        
        provider = AuthProviderFactory.create(config)
        self._auth_providers.append(provider)
        
        return self
    
    def with_saml(
        self,
        entity_id: str,
        sso_url: str,
        x509_cert: str,
        sp_entity_id: str,
        sp_acs_url: str,
        priority: int = 8
    ) -> 'EnhancedConnectionBuilder':
        """
        Add SAML authentication.
        
        Args:
            entity_id: Identity provider entity ID
            sso_url: SSO URL
            x509_cert: IdP certificate
            sp_entity_id: Service provider entity ID
            sp_acs_url: Assertion consumer service URL
            priority: Provider priority
        """
        config = SAMLConfig(
            method=AuthMethod.SAML,
            name="saml",
            priority=priority,
            entity_id=entity_id,
            sso_url=sso_url,
            x509_cert=x509_cert,
            sp_entity_id=sp_entity_id,
            sp_acs_url=sp_acs_url
        )
        
        provider = AuthProviderFactory.create(config)
        self._auth_providers.append(provider)
        
        return self
    
    def with_mfa(
        self,
        method: MFAMethod = MFAMethod.TOTP,
        totp_secret: Optional[str] = None,
        phone_number: Optional[str] = None,
        email_address: Optional[str] = None
    ) -> 'EnhancedConnectionBuilder':
        """
        Enable multi-factor authentication.
        
        Args:
            method: MFA method
            totp_secret: TOTP secret (for TOTP method)
            phone_number: Phone number (for SMS method)
            email_address: Email address (for email method)
        """
        config = MFAConfig(
            method=method,
            totp_secret=totp_secret,
            phone_number=phone_number,
            email_address=email_address
        )
        
        self._mfa_provider = MFAProvider(config)
        
        return self
    
    # Secure Storage
    def with_secure_storage(
        self,
        backend: Optional[StorageBackend] = None,
        storage_path: Optional[Path] = None,
        auto_refresh: bool = True
    ) -> 'EnhancedConnectionBuilder':
        """
        Enable secure credential storage.
        
        Args:
            backend: Storage backend (auto-detected if None)
            storage_path: Path for file storage
            auto_refresh: Enable automatic token refresh
        """
        config = StorageConfig()
        
        if backend:
            config.backend = backend
        if storage_path:
            config.storage_path = storage_path
        config.auto_refresh = auto_refresh
        
        self._storage_config = config
        
        return self
    
    # Audit Logging
    def with_audit_logging(
        self,
        log_file: Optional[Path] = None,
        compliance_standards: Optional[List[ComplianceStandard]] = None,
        min_severity: SeverityLevel = SeverityLevel.INFO,
        enable_alerts: bool = True
    ) -> 'EnhancedConnectionBuilder':
        """
        Enable security audit logging.
        
        Args:
            log_file: Path to audit log file
            compliance_standards: List of compliance standards to track
            min_severity: Minimum severity level to log
            enable_alerts: Enable real-time security alerts
        """
        config = AuditConfig(
            log_file=log_file,
            compliance_standards=set(compliance_standards or []),
            min_severity=min_severity,
            enable_alerts=enable_alerts
        )
        
        # Set alert thresholds
        config.alert_threshold = {
            SecurityEventType.AUTH_FAILURE: 5,
            SecurityEventType.SECURITY_VIOLATION: 1,
            SecurityEventType.SUSPICIOUS_ACTIVITY: 3,
        }
        
        self._audit_config = config
        
        return self
    
    def build(self):
        """Build the enhanced client with security features."""
        # Initialize security components
        if self._security_config:
            self._security_manager = SecurityManager(self._security_config)
        
        if self._storage_config:
            self._secure_storage = SecureStorage(self._storage_config)
        
        if self._auth_providers:
            self._multi_auth = MultiAuthProvider(
                self._auth_providers,
                self._secure_storage
            )
        
        if self._audit_config:
            self._security_auditor = SecurityAuditor(self._audit_config)
        
        # Build base client
        client = super().build()
        
        # Enhance client with security features
        self._enhance_client(client)
        
        # Perform initial authentication if configured
        if self._multi_auth:
            try:
                token = self._multi_auth.authenticate()
                if token and token.token:
                    # Apply auth token
                    client._auth_token = token.token
                    
                    # Log successful auth
                    if self._security_auditor:
                        self._security_auditor.log_event(
                            SecurityEventType.AUTH_SUCCESS,
                            severity=SeverityLevel.INFO,
                            details={"provider": self._multi_auth._current_provider.config.name}
                        )
            except Exception as e:
                if self._security_auditor:
                    self._security_auditor.log_event(
                        SecurityEventType.AUTH_FAILURE,
                        severity=SeverityLevel.ERROR,
                        details={"error": str(e)}
                    )
                raise
        
        return client
    
    def _enhance_client(self, client):
        """Enhance client with security features."""
        # Add security manager
        if self._security_manager:
            client._security_manager = self._security_manager
            
            # Override connection method to use secure SSL context
            original_connect = client.connect
            
            def secure_connect(*args, **kwargs):
                # Create secure SSL context
                hostname = kwargs.get('host', '').split(':')[0]
                ssl_context = self._security_manager.create_ssl_context(hostname)
                
                # Apply SSL context (implementation depends on client)
                # This is a simplified example
                kwargs['ssl_context'] = ssl_context
                
                # Log connection attempt
                if self._security_auditor:
                    self._security_auditor.log_event(
                        SecurityEventType.CONNECTION_ESTABLISHED,
                        severity=SeverityLevel.INFO,
                        details={"host": kwargs.get('host')}
                    )
                
                return original_connect(*args, **kwargs)
            
            client.connect = secure_connect
        
        # Add secure storage
        if self._secure_storage:
            client._secure_storage = self._secure_storage
        
        # Add auth providers
        if self._multi_auth:
            client._auth_provider = self._multi_auth
        
        # Add MFA
        if self._mfa_provider:
            client._mfa_provider = self._mfa_provider
        
        # Add auditor
        if self._security_auditor:
            client._security_auditor = self._security_auditor
            
            # Add audit mixin methods
            client.audit_event = self._security_auditor.log_event
            client.get_security_metrics = self._security_auditor.get_security_metrics
            client.generate_compliance_report = self._security_auditor.generate_compliance_report


# Convenience functions
def create_secure_client(
    uri: str,
    auth_token: Optional[str] = None,
    enable_security: bool = True
) -> Any:
    """
    Create a secure SpacetimeDB client with sensible defaults.
    
    Args:
        uri: Database URI
        auth_token: Authentication token
        enable_security: Enable security features
        
    Returns:
        Configured client
    """
    builder = EnhancedConnectionBuilder().with_uri(uri)
    
    if auth_token:
        builder.with_token(auth_token)
    
    if enable_security:
        # Enable secure storage
        builder.with_secure_storage()
        
        # Enable audit logging
        builder.with_audit_logging(
            compliance_standards=[ComplianceStandard.SOC2]
        )
        
        # Use TLS 1.2+
        builder.with_tls_version(minimum="1.2")
    
    return builder.build()


def create_enterprise_client(
    uri: str,
    oauth_config: Optional[Dict[str, Any]] = None,
    certificate_pins: Optional[List[str]] = None,
    client_cert_path: Optional[Path] = None,
    client_key_path: Optional[Path] = None,
    compliance_standards: Optional[List[ComplianceStandard]] = None
) -> Any:
    """
    Create an enterprise-grade secure client.
    
    Args:
        uri: Database URI
        oauth_config: OAuth configuration
        certificate_pins: Certificate pins
        client_cert_path: Client certificate path
        client_key_path: Client key path
        compliance_standards: Required compliance standards
        
    Returns:
        Enterprise-configured client
    """
    builder = EnhancedConnectionBuilder().with_uri(uri)
    
    # OAuth authentication
    if oauth_config:
        builder.with_oauth2(**oauth_config)
    
    # Certificate pinning
    if certificate_pins:
        builder.with_certificate_pinning(certificate_pins)
    
    # Client certificates
    if client_cert_path and client_key_path:
        builder.with_client_cert(client_cert_path, client_key_path)
    
    # Compliance
    builder.with_audit_logging(
        compliance_standards=compliance_standards or [
            ComplianceStandard.SOC2,
            ComplianceStandard.ISO_27001
        ]
    )
    
    # Security features
    builder.with_secure_storage()
    builder.with_tls_version(minimum="1.3")  # Require TLS 1.3
    
    return builder.build()
