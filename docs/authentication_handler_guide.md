# Authentication Handler Guide

The SpacetimeDB Python SDK includes a comprehensive authentication handler that provides secure credential management, JWT token lifecycle handling, and seamless integration with the WebSocket client.

## Overview

The `AuthenticationHandler` centralizes all authentication-related operations and provides:

- **Secure Credential Storage**: Encrypted storage using system keyring or encrypted files
- **JWT Token Management**: Automatic token lifecycle management with refresh capabilities
- **Authentication State Tracking**: Real-time state management with event notifications
- **Legacy Token Support**: Backward compatibility with existing token-based authentication
- **Thread-Safe Operations**: Concurrent access protection
- **Event Integration**: Real-time authentication event notifications

## Quick Start

### Basic Usage

```python
from spacetimedb_sdk.connection import AuthenticationHandler, AuthenticationState

# Initialize authentication handler
auth_handler = AuthenticationHandler()

# Check for stored credentials
credentials = auth_handler.get_stored_credentials("localhost", "my_database")
if credentials and not credentials.is_expired:
    print(f"Found valid credentials for identity: {credentials.identity[:8]}...")
else:
    print("No valid credentials found")

# Prepare authentication headers
headers = auth_handler.prepare_jwt_headers("localhost", "my_database")
if headers:
    print("Ready to authenticate with JWT")
else:
    print("No authentication headers available")
```

### WebSocket Client Integration

```python
from spacetimedb_sdk.connection import AuthenticationHandler, AuthenticationState
from spacetimedb_sdk.websocket_client import ModernWebSocketClient

class AuthenticatedWebSocketClient:
    def __init__(self, host: str, database: str):
        self.host = host
        self.database = database
        
        # Initialize authentication handler with event notifications
        self.auth_handler = AuthenticationHandler(
            event_handler=self._on_auth_event,
            auto_refresh_tokens=True
        )
        
        # Initialize WebSocket client
        self.ws_client = ModernWebSocketClient()
    
    def _on_auth_event(self, event):
        """Handle authentication events."""
        if event.state == AuthenticationState.AUTHENTICATED:
            print(f"Authentication successful: {event.identity[:8]}...")
            self._reconnect_with_auth()
        elif event.state == AuthenticationState.EXPIRED:
            print("Authentication expired, refreshing...")
            self._handle_auth_refresh()
    
    def connect(self, auth_token=None):
        """Connect with authentication."""
        # Try stored credentials first
        headers = self.auth_handler.prepare_jwt_headers(self.host, self.database)
        
        if not headers and auth_token:
            # Fall back to legacy token
            headers = self.auth_handler.authenticate_with_legacy_token(
                auth_token, self.host, self.database
            )
        
        # Connect to WebSocket
        try:
            self.ws_client.connect(
                auth_token=None,  # We handle auth via headers
                host=self.host,
                database_address=self.database,
                headers=headers
            )
        except Exception as e:
            # Handle authentication handshake
            if "spacetime-identity" in str(e):
                if self.auth_handler.handle_authentication_handshake(
                    str(e), self.host, self.database
                ):
                    # Retry with new credentials
                    self.connect()
```

## Authentication Flow

### 1. Initial Connection

```python
# Initialize handler
auth_handler = AuthenticationHandler()

# Check for stored credentials
stored_creds = auth_handler.get_stored_credentials("localhost", "testdb")

if stored_creds and not stored_creds.is_expired:
    # Use stored credentials
    headers = auth_handler.prepare_jwt_headers("localhost", "testdb")
    # Connect with headers
else:
    # Connect without authentication (triggers handshake)
    # Connect to WebSocket...
```

### 2. Authentication Handshake

When connecting without credentials, SpacetimeDB may respond with an authentication handshake:

```python
def handle_websocket_error(error_message):
    """Handle WebSocket connection errors."""
    if "spacetime-identity" in error_message:
        # Authentication handshake detected
        success = auth_handler.handle_authentication_handshake(
            error_message, "localhost", "testdb"
        )
        
        if success:
            # Credentials stored, retry connection
            headers = auth_handler.prepare_jwt_headers("localhost", "testdb")
            # Reconnect with new headers
```

### 3. Credential Management

```python
# Store credentials manually
auth_handler.store_credentials(
    identity="abcdef123456",
    token="jwt.token.here",
    host="localhost",
    database="testdb"
)

# Get current authentication state
state = auth_handler.get_authentication_state()
print(f"Authentication state: {state}")

# Clear credentials
auth_handler.clear_credentials("localhost", "testdb")
```

## Advanced Features

### Event-Driven Authentication

```python
def auth_event_handler(event):
    """Handle authentication events."""
    print(f"Auth Event: {event.get_event_name()}")
    
    if event.state == AuthenticationState.AUTHENTICATING:
        print("Authentication in progress...")
    elif event.state == AuthenticationState.AUTHENTICATED:
        print(f"Authenticated as: {event.identity[:8]}...")
    elif event.state == AuthenticationState.FAILED:
        print(f"Authentication failed: {event.error}")
    elif event.state == AuthenticationState.EXPIRED:
        print("Authentication expired")

# Initialize with event handler
auth_handler = AuthenticationHandler(event_handler=auth_event_handler)
```

### Token Refresh Management

```python
def token_refresh_callback(credentials):
    """Called when token refresh is needed."""
    print(f"Token refresh needed for {credentials.identity[:8]}...")
    # Implement custom refresh logic

# Add refresh callback
auth_handler.add_refresh_callback(token_refresh_callback)

# Configure auto-refresh
auth_handler = AuthenticationHandler(
    auto_refresh_tokens=True,
    token_refresh_threshold=300.0  # Refresh 5 minutes before expiry
)
```

### Custom Storage Configuration

```python
from spacetimedb_sdk.auth.storage import SecureAuthStorage

# Configure custom storage
storage = SecureAuthStorage(
    storage_dir=Path("/custom/path"),
    max_credential_age_hours=48.0,
    prefer_keyring=True
)

# Initialize handler with custom storage
auth_handler = AuthenticationHandler(storage=storage)
```

## Security Features

### Credential Encryption

The authentication handler uses secure storage with multiple layers:

1. **System Keyring**: Uses OS-level credential storage when available
2. **Encrypted Files**: PBKDF2 + Fernet encryption as fallback
3. **Secure Permissions**: File permissions restricted to owner only

### Thread Safety

All operations are thread-safe using read-write locks:

```python
import threading

def auth_worker():
    """Worker function for concurrent authentication."""
    headers = auth_handler.prepare_jwt_headers("localhost", "testdb")
    # Safe to call from multiple threads

# Start multiple threads
threads = [threading.Thread(target=auth_worker) for _ in range(10)]
for t in threads:
    t.start()
```

### Credential Masking

Sensitive data is automatically masked in logs and debug output:

```python
# Identity is masked in logs
auth_handler.store_credentials("sensitive_identity", "secret_token", "host", "db")
# Logs: "Stored credentials for host/db (identity: sensitiv...)"
```

## Configuration Options

### AuthenticationHandler Parameters

```python
auth_handler = AuthenticationHandler(
    storage=None,                    # Custom storage backend
    event_handler=None,              # Event notification callback
    auto_refresh_tokens=True,        # Enable automatic token refresh
    token_refresh_threshold=300.0,   # Seconds before expiry to refresh
    max_retry_attempts=3             # Maximum authentication retries
)
```

### SecureAuthStorage Parameters

```python
storage = SecureAuthStorage(
    storage_dir=None,                # Custom storage directory
    max_credential_age_hours=24.0,   # Credential expiry time
    auto_cleanup=True,               # Automatic cleanup of expired credentials
    prefer_keyring=True,             # Prefer system keyring
    master_password=None             # Custom master password
)
```

## Error Handling

### Authentication Errors

```python
try:
    auth_handler.store_credentials("identity", "token", "host", "db")
except Exception as e:
    print(f"Failed to store credentials: {e}")

# Check authentication state
if auth_handler.get_authentication_state() == AuthenticationState.FAILED:
    print("Authentication is in failed state")
```

### Retry Logic

```python
# Check if retry is recommended
if auth_handler.should_retry_authentication(401):
    print("Retry recommended for 401 error")
    # Implement retry logic
```

### Graceful Degradation

```python
# Fallback to legacy authentication
try:
    headers = auth_handler.prepare_jwt_headers("host", "db")
except Exception:
    # Fall back to legacy token
    headers = auth_handler.authenticate_with_legacy_token(
        legacy_token, "host", "db"
    )
```

## Monitoring and Diagnostics

### Authentication Information

```python
# Get comprehensive authentication info
info = auth_handler.get_authentication_info()
print(f"State: {info['state']}")
print(f"Retry count: {info['retry_count']}")
print(f"Auto refresh: {info['auto_refresh_enabled']}")

if 'current_identity' in info:
    print(f"Current identity: {info['current_identity']}")
    print(f"Time until expiry: {info['time_until_expiry']:.1f}s")
```

### Storage Information

```python
# Get storage backend information
storage_info = auth_handler.storage.get_storage_info()
print(f"Using keyring: {storage_info['using_keyring']}")
print(f"Cached credentials: {storage_info['cached_credentials']}")
print(f"Storage directory: {storage_info['storage_dir']}")
```

## Migration from Legacy Authentication

### Replacing Direct Authentication Management

**Before (websocket_client.py):**

```python
# Old approach - direct credential management
self.spacetimedb_identity = identity
self.spacetimedb_token = token
self.auth_handshake_completed = True

# Manual header preparation
if self.spacetimedb_token:
    headers["Authorization"] = f"Bearer {self.spacetimedb_token}"
```

**After (with AuthenticationHandler):**

```python
# New approach - centralized authentication
self.auth_handler = AuthenticationHandler()

# Automatic credential management
self.auth_handler.store_credentials(identity, token, host, database)

# Automatic header preparation
headers = self.auth_handler.prepare_jwt_headers(host, database)
```

### Event Integration

**Before:**

```python
# Manual state tracking
if authentication_successful:
    self.auth_state = "authenticated"
    # Manual callbacks
```

**After:**

```python
# Event-driven state management
def on_auth_event(event):
    if event.state == AuthenticationState.AUTHENTICATED:
        # Automatic state tracking and notifications

auth_handler = AuthenticationHandler(event_handler=on_auth_event)
```

## Best Practices

### 1. Use Event-Driven Architecture

```python
# Implement event handlers for authentication state changes
def handle_auth_events(event):
    if event.state == AuthenticationState.AUTHENTICATED:
        # Update UI, start background tasks, etc.
    elif event.state == AuthenticationState.EXPIRED:
        # Handle token expiry gracefully

auth_handler = AuthenticationHandler(event_handler=handle_auth_events)
```

### 2. Configure Appropriate Refresh Thresholds

```python
# For long-running applications
auth_handler = AuthenticationHandler(
    auto_refresh_tokens=True,
    token_refresh_threshold=600.0  # 10 minutes before expiry
)

# For short-lived scripts
auth_handler = AuthenticationHandler(
    auto_refresh_tokens=False  # Manual refresh control
)
```

### 3. Handle Multiple Databases

```python
# Use separate handlers for different contexts
class MultiDatabaseClient:
    def __init__(self):
        self.auth_handlers = {}
    
    def get_auth_handler(self, host, database):
        key = f"{host}:{database}"
        if key not in self.auth_handlers:
            self.auth_handlers[key] = AuthenticationHandler()
        return self.auth_handlers[key]
```

### 4. Implement Graceful Shutdown

```python
# Always cleanup resources
try:
    # Application logic
    pass
finally:
    auth_handler.shutdown()

# Or use context manager
with AuthenticationHandler() as auth_handler:
    # Application logic
    pass
# Automatic cleanup
```

## Troubleshooting

### Common Issues

1. **"No credentials found"**
   - Check if credentials were stored successfully
   - Verify host/database combination matches exactly
   - Check credential expiry

2. **"Authentication handshake failed"**
   - Verify server is sending proper spacetime-identity headers
   - Check network connectivity
   - Ensure WebSocket client is handling errors correctly

3. **"Storage initialization failed"**
   - Check file permissions in storage directory
   - Verify keyring availability
   - Check available disk space

### Debug Logging

```python
import logging

# Enable debug logging
logging.getLogger('spacetimedb_sdk.connection.authentication_handler').setLevel(logging.DEBUG)
logging.getLogger('spacetimedb_sdk.auth.storage').setLevel(logging.DEBUG)

# Now all authentication operations will be logged
```

### Storage Diagnostics

```python
# Check storage health
try:
    info = auth_handler.get_authentication_info()
    storage_info = info.get('storage', {})
    
    if storage_info.get('keyring_available'):
        print("✓ System keyring available")
    else:
        print("⚠ Using file-based storage")
    
    if storage_info.get('cached_credentials', 0) > 0:
        print(f"✓ {storage_info['cached_credentials']} credentials cached")
    else:
        print("ℹ No credentials currently cached")
        
except Exception as e:
    print(f"❌ Storage diagnostic failed: {e}")
```

## API Reference

### AuthenticationHandler

#### Methods

- `authenticate_with_legacy_token(auth_token, host, database)` - Prepare legacy token headers
- `get_stored_credentials(host, database, allow_expired=False)` - Get stored credentials
- `store_credentials(identity, token, host, database)` - Store credentials securely
- `prepare_jwt_headers(host, database, require_fresh=False)` - Prepare JWT headers
- `handle_authentication_handshake(error_message, host, database)` - Handle auth handshake
- `should_retry_authentication(error_code)` - Check if retry is recommended
- `clear_credentials(host, database)` - Clear stored credentials
- `get_authentication_state()` - Get current authentication state
- `get_current_credentials()` - Get current credentials
- `add_refresh_callback(callback)` - Add token refresh callback
- `remove_refresh_callback(callback)` - Remove token refresh callback
- `get_authentication_info()` - Get comprehensive auth information
- `shutdown()` - Cleanup resources

#### Properties

- `storage` - Storage backend instance
- `event_handler` - Event notification callback
- `auto_refresh_tokens` - Auto-refresh enabled flag
- `token_refresh_threshold` - Refresh threshold in seconds
- `max_retry_attempts` - Maximum retry attempts

### AuthenticationState

- `UNAUTHENTICATED` - No authentication
- `AUTHENTICATING` - Authentication in progress
- `AUTHENTICATED` - Successfully authenticated
- `FAILED` - Authentication failed
- `EXPIRED` - Authentication expired

### AuthenticationCredentials

#### Properties

- `identity` - SpacetimeDB identity
- `token` - JWT token
- `host` - Server host
- `database` - Database name
- `timestamp` - Creation timestamp
- `expires_at` - Optional expiry timestamp
- `is_expired` - Expiry check
- `time_until_expiry` - Seconds until expiry

### AuthenticationEvent

#### Properties

- `state` - Authentication state
- `identity` - Optional identity
- `host` - Optional host
- `database` - Optional database
- `error` - Optional error message
- `event_type` - Event type (AUTHENTICATION)
- `timestamp` - Event timestamp
- `data` - Additional event data