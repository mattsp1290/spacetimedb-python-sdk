# ADR-002: Authentication Handler Design

## Status
✅ **ACCEPTED** - Implemented in v1.1.2

## Context

The previous authentication system in the SpacetimeDB Python SDK had several limitations:

1. **Tightly Coupled**: Authentication logic was embedded in client classes
2. **Inflexible**: Difficult to support multiple authentication providers
3. **Insecure**: Plaintext credential storage and poor secret management
4. **Limited Token Management**: No automatic token refresh or rotation
5. **Poor Error Handling**: Inconsistent error handling across auth flows

These issues made it difficult to:
- Support enterprise authentication requirements
- Implement secure credential storage
- Add new authentication providers
- Handle token lifecycle management effectively

## Decision

We will implement a **modular authentication handler system** with the following design principles:

### Core Architecture

1. **Authentication Provider Interface**: Abstract base for all auth providers
2. **Credential Manager**: Secure storage and management of authentication credentials
3. **Token Manager**: Automatic token refresh and lifecycle management
4. **Authentication Handler**: Orchestrates authentication flow and integrates with clients
5. **Security Manager**: Handles encryption, validation, and security policies

### Design Pattern

```python
# Provider interface
class AuthenticationProvider(ABC):
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthResult:
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> TokenResult:
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> bool:
        pass

# Concrete implementations
class JWTAuthProvider(AuthenticationProvider):
    # JWT-specific implementation
    pass

class OAuthProvider(AuthenticationProvider):
    # OAuth-specific implementation
    pass

class APIKeyProvider(AuthenticationProvider):
    # API key-specific implementation
    pass
```

### Key Features

1. **Pluggable Providers**: Support for multiple authentication methods
2. **Secure Storage**: Encrypted credential storage with master password
3. **Automatic Refresh**: Token refresh before expiration
4. **Validation**: Comprehensive token and credential validation
5. **Audit Logging**: Security event logging for compliance

## Rationale

### Benefits

1. **Security**: Encrypted storage and secure credential handling
2. **Flexibility**: Easy to add new authentication providers
3. **Maintainability**: Clear separation of concerns
4. **Compliance**: Built-in audit logging and security policies
5. **Developer Experience**: Simple API for common authentication scenarios

### Trade-offs

1. **Complexity**: More components to understand and configure
2. **Performance**: Slight overhead from encryption/decryption
3. **Dependencies**: Additional security-related dependencies

## Implementation Details

### Authentication Handler Core

```python
class AuthenticationHandler:
    def __init__(self, provider: AuthenticationProvider):
        self.provider = provider
        self.credential_manager = SecureCredentialManager()
        self.token_manager = TokenManager()
        self.security_manager = SecurityManager()
    
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthResult:
        """Authenticate user and store credentials securely"""
        
        # Validate credentials
        validation_result = await self.security_manager.validate_credentials(credentials)
        if not validation_result.is_valid:
            raise AuthenticationError(validation_result.errors)
        
        # Authenticate with provider
        auth_result = await self.provider.authenticate(credentials)
        
        if auth_result.success:
            # Store credentials securely
            await self.credential_manager.store_credential(
                'current_user',
                auth_result.credential_data,
                expires_at=auth_result.expires_at
            )
            
            # Set up token refresh
            if auth_result.refresh_token:
                await self.token_manager.schedule_refresh(
                    auth_result.token,
                    auth_result.refresh_token,
                    auth_result.expires_at
                )
        
        return auth_result
    
    async def get_current_token(self) -> Optional[str]:
        """Get current valid token, refreshing if necessary"""
        
        credential_data = await self.credential_manager.retrieve_credential('current_user')
        if not credential_data:
            return None
        
        token = credential_data.get('token')
        if not token:
            return None
        
        # Check if token needs refresh
        if await self.token_manager.needs_refresh(token):
            token = await self.refresh_current_token()
        
        return token
```

### Secure Credential Storage

```python
class SecureCredentialManager:
    def __init__(self, storage_path: str = "~/.spacetimedb/credentials"):
        self.storage_path = Path(storage_path).expanduser()
        self.encryption_key = None
        self.audit_logger = AuditLogger()
    
    async def initialize(self, master_password: str):
        """Initialize secure storage with master password"""
        
        # Derive encryption key from master password
        salt = self._get_or_create_salt()
        self.encryption_key = self._derive_key(master_password, salt)
        
        # Create secure storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        os.chmod(self.storage_path, 0o700)  # Owner only
    
    async def store_credential(self, credential_id: str, 
                             credential_data: Dict[str, Any],
                             expires_at: Optional[float] = None):
        """Store credential with encryption"""
        
        # Encrypt credential data
        encrypted_data = self._encrypt_data(credential_data)
        
        # Create metadata
        metadata = {
            'created_at': time.time(),
            'expires_at': expires_at,
            'rotation_count': 0
        }
        
        # Store encrypted credential
        credential_entry = {
            'data': encrypted_data,
            'metadata': metadata
        }
        
        await self._save_credential(credential_id, credential_entry)
        
        # Log security event
        self.audit_logger.log_event('credential_stored', {
            'credential_id': credential_id,
            'expires_at': expires_at
        })
```

### Token Lifecycle Management

```python
class TokenManager:
    def __init__(self):
        self.refresh_tasks: Dict[str, asyncio.Task] = {}
        self.token_cache: Dict[str, TokenInfo] = {}
    
    async def schedule_refresh(self, token: str, refresh_token: str, expires_at: float):
        """Schedule automatic token refresh"""
        
        # Calculate refresh time (5 minutes before expiry)
        refresh_time = expires_at - 300
        delay = max(0, refresh_time - time.time())
        
        # Schedule refresh task
        task = asyncio.create_task(self._refresh_after_delay(delay, refresh_token))
        self.refresh_tasks[token] = task
    
    async def _refresh_after_delay(self, delay: float, refresh_token: str):
        """Refresh token after delay"""
        
        await asyncio.sleep(delay)
        
        try:
            # Refresh token
            new_token = await self.provider.refresh_token(refresh_token)
            
            # Update stored credential
            await self.credential_manager.rotate_credential(
                'current_user',
                new_token.credential_data,
                new_token.expires_at
            )
            
            # Schedule next refresh
            await self.schedule_refresh(
                new_token.token,
                new_token.refresh_token,
                new_token.expires_at
            )
            
        except Exception as e:
            # Log refresh failure
            self.audit_logger.log_event('token_refresh_failed', {
                'error': str(e)
            })
```

### Security Validation

```python
class SecurityManager:
    def __init__(self):
        self.validation_rules = []
        self.security_policies = {}
    
    async def validate_credentials(self, credentials: Dict[str, Any]) -> ValidationResult:
        """Validate credentials against security policies"""
        
        result = ValidationResult()
        
        # Check for required fields
        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in credentials:
                result.add_error(f"Missing required field: {field}")
        
        # Validate password strength
        password = credentials.get('password', '')
        if len(password) < 8:
            result.add_error("Password must be at least 8 characters")
        
        if not re.search(r'[A-Z]', password):
            result.add_error("Password must contain uppercase letter")
        
        if not re.search(r'[0-9]', password):
            result.add_error("Password must contain digit")
        
        # Check for common passwords
        if password.lower() in ['password', '123456', 'admin']:
            result.add_error("Password is too common")
        
        return result
    
    async def validate_token(self, token: str) -> bool:
        """Validate JWT token"""
        
        try:
            # Decode token (without verification for basic checks)
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Check expiration
            exp = payload.get('exp')
            if exp and time.time() > exp:
                return False
            
            # Check issuer
            iss = payload.get('iss')
            if iss not in self.security_policies.get('allowed_issuers', []):
                return False
            
            return True
            
        except jwt.InvalidTokenError:
            return False
```

## Migration Strategy

### Phase 1: Core Implementation
- Implement authentication provider interface
- Create secure credential manager
- Build token lifecycle management

### Phase 2: Provider Implementation
- JWT authentication provider
- OAuth 2.0 provider
- API key provider

### Phase 3: Integration
- Integrate with existing clients
- Add backward compatibility layer
- Create migration utilities

### Phase 4: Documentation and Testing
- Comprehensive documentation
- Security testing
- Performance benchmarking

## Security Considerations

### Encryption
- AES-256 encryption for credential storage
- PBKDF2 key derivation with high iteration count
- Secure random salt generation

### Token Management
- Automatic token refresh before expiration
- Secure token storage in memory
- Token revocation support

### Audit Logging
- All authentication events logged
- Structured logging format
- Configurable log retention

### Input Validation
- Comprehensive credential validation
- SQL injection prevention
- XSS protection for web-based auth

## Performance Considerations

### Benchmarks
- Token validation: < 1ms
- Credential retrieval: < 5ms
- Authentication flow: < 100ms

### Optimization Strategies
- Token caching with TTL
- Lazy loading of credentials
- Async I/O for all operations

## Testing Strategy

### Unit Tests
- Authentication provider implementations
- Credential manager operations
- Token lifecycle management
- Security validation

### Integration Tests
- End-to-end authentication flows
- Token refresh scenarios
- Error handling paths

### Security Tests
- Penetration testing
- Vulnerability scanning
- Compliance verification

## Consequences

### Positive
- **Enhanced Security**: Encrypted storage and secure practices
- **Flexibility**: Support for multiple authentication methods
- **Maintainability**: Clear separation of concerns
- **Compliance**: Built-in audit logging and security policies
- **Developer Experience**: Simple API for common scenarios

### Negative
- **Complexity**: More components to understand
- **Performance**: Slight overhead from encryption
- **Dependencies**: Additional security libraries required

### Neutral
- **Bundle Size**: Moderate increase due to crypto dependencies
- **Memory Usage**: Minimal impact from credential caching

## Monitoring and Metrics

### Security Metrics
- Authentication success/failure rates
- Token refresh frequency
- Credential rotation events
- Security policy violations

### Performance Metrics
- Authentication latency
- Token validation performance
- Credential retrieval speed

### Operational Metrics
- Active token count
- Credential storage usage
- Audit log volume

## Related ADRs

- [ADR-001: Event System Unification](ADR-001-event-system-unification.md)
- [ADR-003: Connection Pooling Architecture](ADR-003-connection-pooling-architecture.md)
- [ADR-004: Memory Management Strategy](ADR-004-memory-management-strategy.md)

## References

- [Authentication API Documentation](../authentication_guide.md)
- [Security Best Practices](../security_best_practices.md)
- [Token Management Guide](../token_management.md)
- [OWASP Authentication Guidelines](https://owasp.org/www-project-authentication/)

---

**Author**: SpacetimeDB Python SDK Team  
**Date**: 2024-01-16  
**Last Updated**: 2024-01-22  
**Status**: Accepted and Implemented