# Authentication Handler Implementation

This document describes the complete authentication handler implementation for the SpacetimeDB Python SDK, including all security features and integration patterns.

## Overview

The authentication handler provides centralized authentication management for SpacetimeDB connections with the following features:

- **JWT Token Management**: Full lifecycle management of JWT tokens with automatic refresh
- **Secure Storage**: Integration with Phase 1 secure credential storage (AES-128 encryption)
- **Authentication State Management**: Comprehensive state tracking and event notifications
- **WebSocket Integration**: Seamless integration with WebSocket clients
- **Thread Safety**: All operations are thread-safe with proper locking
- **Error Handling**: Robust error handling with retry logic and graceful degradation

## Files Implemented

### Core Authentication Handler
- **`authentication_handler.py`** (~638 lines): Main authentication handler implementation
  - `AuthenticationHandler` class with JWT lifecycle management
  - `AuthenticationState` enum for state tracking
  - `AuthenticationCredentials` dataclass for credential management
  - `AuthenticationEvent` dataclass for event notifications
  - Integration with secure storage from Phase 1
  - Automatic token refresh with configurable thresholds
  - Thread-safe operations with RLock protection

### WebSocket Integration
- **`websocket_auth_integration.py`** (~340 lines): WebSocket authentication integration
  - `WebSocketAuthIntegration` class for WebSocket client integration
  - `WebSocketAuthConfig` dataclass for configuration
  - Automatic token refresh callbacks
  - Authentication error handling and retry logic
  - Event-driven state management

- **`websocket_client_integration.py`** (~410 lines): Integration patterns for existing clients
  - `WebSocketClientAuthMixin` class for adding auth to existing clients
  - Migration helpers for transitioning from legacy authentication
  - Convenience functions for common authentication patterns
  - Backward compatibility with existing WebSocket client code

### Testing and Examples
- **`test_authentication_handler_integration.py`** (~415 lines): Comprehensive integration tests
- **`authentication_handler_usage.py`** (~380 lines): Usage examples and patterns

## Key Features Implemented

### 1. Core Authentication Management
```python
class AuthenticationHandler:
    def __init__(self, auto_refresh_tokens=True, token_refresh_threshold=300.0):
        # Initialize with secure storage from Phase 1
        
    def store_credentials(self, identity: str, token: str, host: str, database: str):
        # Store using Phase 1 secure credential storage
        
    def get_stored_credentials(self, host: str, database: str) -> Optional[AuthenticationCredentials]:
        # Retrieve from secure storage
        
    def prepare_jwt_headers(self, host: str, database: str) -> Dict[str, str]:
        # Prepare Authorization headers for WebSocket connection
```

### 2. Authentication State Management
```python
class AuthenticationState(Enum):
    UNAUTHENTICATED = "unauthenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    EXPIRED = "expired"
```

### 3. JWT Token Management
- Automatic token expiry detection with configurable safety margins
- Background token refresh with callback notifications
- Secure token storage with AES-128 encryption
- Thread-safe token operations

### 4. WebSocket Integration Patterns
- **Mixin Pattern**: `WebSocketClientAuthMixin` for adding auth to existing clients
- **Integration Pattern**: `integrate_auth_handler_with_websocket_client()` for runtime integration
- **Factory Pattern**: `create_auth_enabled_websocket_client()` for creating auth-enabled clients
- **Migration Pattern**: `migrate_legacy_auth_to_handler()` for transitioning from legacy auth

### 5. Security Features
- **Secure Storage**: Integration with AES-128 encrypted credential storage
- **Credential Masking**: Mask sensitive data in logs (identity123456... format)
- **Thread Safety**: RLock protection for all operations
- **Memory Security**: Clear sensitive data from memory on shutdown
- **Input Validation**: Comprehensive input validation for all operations

### 6. Event System Integration
- Emit `AuthenticationEvent` for all state changes
- Integration with unified event system
- Automatic retry logic with event notifications
- Configurable event handling and filtering

## Usage Examples

### Basic Usage
```python
from spacetimedb_sdk.connection import AuthenticationHandler

# Create handler
handler = AuthenticationHandler()

# Store credentials
handler.store_credentials(
    identity="user123456789",
    token="eyJhbGciOiJIUzI1NiJ9.token",
    host="localhost:3000",
    database="my_game"
)

# Get JWT headers for WebSocket connection
headers = handler.prepare_jwt_headers("localhost:3000", "my_game")
```

### WebSocket Integration
```python
from spacetimedb_sdk.connection import WebSocketAuthIntegration

# Create integration
integration = WebSocketAuthIntegration()

# Prepare connection headers
headers = integration.prepare_connection_headers("localhost:3000", "my_game")

# Handle authentication errors
should_retry = integration.handle_authentication_error(
    error, "localhost:3000", "my_game", error_message
)
```

### Legacy Client Migration
```python
from spacetimedb_sdk.connection import integrate_auth_handler_with_websocket_client

# Integrate with existing client
integration = integrate_auth_handler_with_websocket_client(existing_client)

# Use new authentication methods
headers = existing_client._prepare_auth_headers("localhost:3000", "my_game")
```

## Integration Points

### Phase 1 Secure Storage
- Uses `SecureAuthStorage` from Phase 1 for encrypted credential storage
- Automatic migration from legacy plaintext storage
- Secure key derivation with PBKDF2 and AES-128 encryption

### Event System
- Publishes `AuthenticationEvent` for all state changes
- Integration with unified event system
- Configurable event priorities and filtering

### WebSocket Client
- Clean interface for authentication operations
- Automatic token refresh with reconnection
- Error handling with retry logic
- Backward compatibility with existing patterns

## Configuration Options

### AuthenticationHandler Configuration
```python
handler = AuthenticationHandler(
    auto_refresh_tokens=True,           # Enable automatic token refresh
    token_refresh_threshold=300.0,      # Refresh 5 minutes before expiry
    max_retry_attempts=3                # Maximum authentication retries
)
```

### WebSocket Integration Configuration
```python
config = WebSocketAuthConfig(
    handshake_timeout=30.0,             # Authentication handshake timeout
    max_retry_attempts=3,               # Maximum retry attempts
    auto_refresh_tokens=True,           # Enable automatic token refresh
    prefer_jwt_over_legacy=True         # Prefer JWT over legacy tokens
)
```

## Testing

The implementation includes comprehensive tests covering:
- Basic authentication handler functionality
- WebSocket integration patterns
- Error handling and retry logic
- Thread safety and concurrent access
- Token refresh and lifecycle management
- Legacy migration patterns
- Configuration options and customization

Run tests with:
```bash
python -m pytest tests/refactoring/test_authentication_handler_integration.py -v
```

## Production Readiness

The authentication handler is production-ready with:
- **Security**: AES-128 encryption for credential storage
- **Performance**: Efficient token caching and refresh
- **Reliability**: Comprehensive error handling and retry logic
- **Scalability**: Thread-safe operations with minimal locking
- **Monitoring**: Event-driven state tracking and metrics
- **Maintainability**: Clean separation of concerns and modular design

## Migration Guide

### From Legacy Authentication
1. **Install new handler**: `handler = AuthenticationHandler()`
2. **Migrate credentials**: Use `migrate_legacy_auth_to_handler(client)`
3. **Update connection code**: Use `client._prepare_auth_headers()`
4. **Handle errors**: Use `client._handle_auth_error()`

### Integration with Existing Clients
1. **Runtime integration**: `integrate_auth_handler_with_websocket_client(client)`
2. **Mixin pattern**: Inherit from `WebSocketClientAuthMixin`
3. **Factory pattern**: Use `create_auth_enabled_websocket_client()`

## Security Considerations

- All credentials are encrypted at rest using AES-128
- JWT tokens are validated for expiry with configurable safety margins
- Sensitive data is masked in log outputs
- Thread-safe operations prevent race conditions
- Automatic cleanup of expired credentials
- Secure transmission via HTTPS enforcement

## Future Enhancements

- Support for multiple authentication providers
- Advanced token refresh strategies
- Credential rotation and versioning
- Integration with hardware security modules
- Support for OAuth2 and other authentication protocols