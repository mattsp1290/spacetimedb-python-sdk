# SpacetimeDB Python SDK - JWT Authentication Implementation

## 🎯 Overview

This document describes the implementation of JWT authentication support in the SpacetimeDB Python SDK, addressing the authentication handshake protocol used by SpacetimeDB servers.

## 🚨 Problem Solved

**Issue**: The SpacetimeDB Python SDK could not connect to SpacetimeDB servers with JWT authentication enabled. When attempting to connect, the server would respond with HTTP 400 "invalid auth credentials" along with identity and token headers, but the SDK treated this as a connection failure instead of part of the authentication handshake.

**Solution**: Implemented automatic detection and handling of the SpacetimeDB authentication handshake protocol, allowing seamless connection to authenticated servers.

## 🔧 Implementation Details

### 1. Authentication Storage System

**File**: `src/spacetimedb_sdk/auth_storage.py`

- **`AuthCredentials`**: Class to represent SpacetimeDB authentication credentials
- **`SpacetimeDBAuthStorage`**: Thread-safe credential storage with persistence
- **Features**:
  - Persistent storage in `~/.spacetimedb/credentials.json`
  - Automatic expiration handling (24-hour default)
  - Thread-safe operations
  - Support for multiple host/database combinations

### 2. Authentication Exception

**File**: `src/spacetimedb_sdk/exceptions.py`

- **`SpacetimeDBAuthHandshakeError`**: Special exception for authentication handshake detection
- Contains identity and token information from server response

### 3. WebSocket Client Authentication

**File**: `src/spacetimedb_sdk/websocket_client.py`

**Key Changes**:
- Added JWT authentication state tracking
- Modified `connect()` to check for stored credentials
- Enhanced `_do_connect()` to use JWT Bearer tokens
- Implemented authentication handshake detection in `_on_ws_error()`
- Automatic retry with authentication after receiving identity token

**Authentication Flow**:
1. Check for stored credentials for host/database
2. If credentials exist and are valid, use Bearer authentication
3. If no credentials, attempt connection without auth
4. If server returns 400 with `spacetime-identity-token`, store credentials and retry
5. Use Bearer token for authenticated connection

### 4. Modern Client Integration

**File**: `src/spacetimedb_sdk/modern_client.py`

- No changes required - inherits authentication support from `ModernWebSocketClient`
- Works transparently with existing client code

### 5. Package Exports

**File**: `src/spacetimedb_sdk/__init__.py`

- Added exports for authentication storage functionality
- Users can access credential management functions directly

## 📋 SpacetimeDB Authentication Protocol

### Protocol Flow

1. **Initial Connection (No Auth)**
   ```
   GET /v1/database/{db_name}/subscribe
   Upgrade: websocket
   ```

2. **Server Response (400 with Token)**
   ```
   HTTP/1.1 400 Bad Request
   spacetime-identity: {hex_identity}
   spacetime-identity-token: {JWT_token}
   Body: "invalid auth credentials"
   ```

3. **Authenticated Reconnection**
   ```
   GET /v1/database/{db_name}/subscribe
   Upgrade: websocket
   Authorization: Bearer {JWT_token}
   ```

4. **Success**
   ```
   HTTP/1.1 101 Switching Protocols
   ```

### Header Extraction

The implementation extracts authentication headers from WebSocket handshake errors:
- `spacetime-identity`: Hex-encoded identity
- `spacetime-identity-token`: JWT token for authentication

## 🧪 Testing

### Unit Tests

**File**: `test_spacetimedb_jwt_auth.py`

- Tests credential storage and retrieval
- Tests authentication state management
- Tests handshake flow simulation
- Tests credential persistence

### Integration Tests

**File**: `test_auth_integration.py`

- Tests with real SpacetimeDB server
- Validates complete authentication flow
- Tests credential reuse across connections

## 🚀 Usage Examples

### Basic Usage (Automatic)

```python
from spacetimedb_sdk import ModernSpacetimeDBClient

# Create client
client = ModernSpacetimeDBClient()

# Connect - authentication happens automatically if required
client._connect_internal(
    auth_token=None,
    host="localhost:3000",
    database_address="my_database",
    ssl_enabled=True
)

# Client automatically:
# 1. Attempts connection
# 2. Handles authentication handshake if needed
# 3. Stores credentials for future use
# 4. Retries with authentication
```

### Manual Credential Management

```python
from spacetimedb_sdk.auth_storage import store_credentials, get_credentials

# Store credentials manually
store_credentials(
    identity="abc123...",
    token="eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9...",
    host="localhost:3000",
    database="my_database"
)

# Retrieve stored credentials
credentials = get_credentials("localhost:3000", "my_database")
if credentials and not credentials.is_expired():
    print(f"Found valid credentials for {credentials.identity[:8]}...")
```

### Advanced Usage

```python
from spacetimedb_sdk.auth_storage import SpacetimeDBAuthStorage

# Custom storage location
storage = SpacetimeDBAuthStorage(
    storage_dir=Path("/custom/path"),
    max_credential_age_hours=48.0,
    auto_cleanup=True
)

# List all stored credentials
credentials_info = storage.list_stored_credentials()
for key, info in credentials_info.items():
    print(f"Host/DB: {key}")
    print(f"Identity: {info['identity'][:8]}...")
    print(f"Expired: {info['is_expired']}")
```

## 🔄 Backwards Compatibility

- **Fully backwards compatible** - existing code continues to work unchanged
- Legacy token-based authentication still supported
- JWT authentication takes precedence when available
- No breaking changes to existing APIs

## 🛡️ Security Considerations

### Credential Storage
- Credentials stored in user's home directory (`~/.spacetimedb/`)
- JSON format for easy inspection and management
- Automatic expiration prevents stale credentials
- Thread-safe operations prevent corruption

### Token Handling
- JWT tokens treated as opaque strings
- Tokens automatically expire after 24 hours (configurable)
- No token validation or parsing in client (server validates)
- Credentials cleared on explicit disconnect (optional)

### Error Handling
- Graceful handling of expired tokens
- Automatic cleanup of invalid credentials
- Clear error messages for authentication failures
- No sensitive information in logs

## 📊 Success Criteria - Before vs After

### Before Fix
```
ERROR - Failed to connect to SpacetimeDB: server rejected WebSocket connection: HTTP 400
ERROR - Connection failed permanently: invalid auth credentials
```

### After Fix
```
INFO - Connecting to SpacetimeDB at ws://localhost:3000/v1/database/blackholio/subscribe
DEBUG - Received 400 with identity token, retrying with authentication...
INFO - Successfully connected to SpacetimeDB with identity: c20058f56a2e84b1589e8c2b50ce488888f88c9898e7a27c5e8600738267518e
```

## 🔍 Implementation Files

| File | Purpose |
|------|---------|
| `src/spacetimedb_sdk/auth_storage.py` | Credential storage and management |
| `src/spacetimedb_sdk/exceptions.py` | Authentication exceptions |
| `src/spacetimedb_sdk/websocket_client.py` | WebSocket authentication logic |
| `src/spacetimedb_sdk/__init__.py` | Package exports |
| `test_spacetimedb_jwt_auth.py` | Unit tests |
| `test_auth_integration.py` | Integration tests |

## 🎉 Benefits

1. **Production Ready**: Python clients can now connect to authenticated SpacetimeDB servers
2. **Automatic**: Zero-configuration authentication for most use cases
3. **Persistent**: Credentials stored and reused across sessions
4. **Secure**: Follows SpacetimeDB authentication protocol correctly
5. **Compatible**: Works with both authenticated and non-authenticated servers
6. **Transparent**: Existing code works without modification

## 🔮 Future Enhancements

Potential future improvements:
- Token refresh handling for long-lived connections
- Multiple authentication methods support
- Credential encryption for enhanced security
- Authentication event callbacks for advanced use cases
- Integration with external credential providers

---

**Implementation Status**: ✅ **COMPLETE**  
**Testing Status**: ✅ **PASSED**  
**Compatibility**: ✅ **BACKWARDS COMPATIBLE**  
**Production Ready**: ✅ **YES**