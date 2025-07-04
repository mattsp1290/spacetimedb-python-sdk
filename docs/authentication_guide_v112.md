# SpacetimeDB Python SDK v1.1.2 Authentication Guide

## Overview

The SpacetimeDB Python SDK v1.1.2 supports both anonymous and token-based authentication. This guide covers authentication patterns, best practices, and troubleshooting.

## Authentication Methods

### 1. Anonymous Authentication

Connect without providing any authentication token. The server will assign a new identity and provide a token for future connections.

```python
from spacetimedb_sdk import ModernSpacetimeDBClient

# Anonymous connection
client = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database",
    auth_token=None  # or omit entirely
)

# After connection, you'll receive an identity and token
print(f"Assigned identity: {client.identity}")
print(f"Auth token for reuse: {client.enhanced_identity_token.token}")
```

### 2. Token Authentication

Use a previously obtained token to connect with an existing identity.

```python
# Connect with existing token
client = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database",
    auth_token="your_auth_token_here"
)
```

## Authentication Flow

### Authorization Header Format

The SDK uses HTTP Basic Authentication with a special format:
- Scheme: `Basic`
- Credentials: Base64-encoded string of `token:{auth_token}`

Example:
```
Authorization: Basic dG9rZW46eW91cl9hdXRoX3Rva2VuX2hlcmU=
```

### Identity Token Message

After successful authentication, the server sends an `IdentityToken` message containing:
- `identity`: Your assigned identity (hex string)
- `token`: Authentication token for future use
- `connection_id`: Unique connection identifier

## Token Management

### Storing Tokens

```python
# Get token after connection
def on_identity(token, identity, connection_id):
    # Store token for future use
    with open('.spacetimedb_token', 'w') as f:
        f.write(token)
    print(f"Identity confirmed: {identity}")

client = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database",
    on_identity=on_identity
)
```

### Reusing Tokens

```python
# Load stored token
try:
    with open('.spacetimedb_token', 'r') as f:
        stored_token = f.read().strip()
except FileNotFoundError:
    stored_token = None

# Connect with stored token or anonymously
client = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database",
    auth_token=stored_token
)
```

### Token Expiration

The SDK provides enhanced token management:

```python
# Check if token needs refresh
if client.enhanced_identity_token:
    if client.enhanced_identity_token.is_expired():
        print("Token has expired")
    
    # Check if refresh is needed (1 hour before expiry)
    if client.enhanced_identity_token.refresh_if_needed(threshold=3600):
        print("Token should be refreshed soon")
    
    # Get token metadata
    claims = client.enhanced_identity_token.extract_claims()
    print(f"Token issued at: {claims['issued_at']}")
    print(f"Token expires at: {claims['expires_at']}")
```

## Error Handling

### Authentication Errors

```python
from spacetimedb_sdk.exceptions import AuthenticationError

try:
    client = ModernSpacetimeDBClient.connect(
        host="localhost:3000",
        database_address="my_database",
        auth_token="invalid_token"
    )
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    print(f"Status code: {e.status_code}")
    print(f"Auth method: {e.auth_method}")
    
    if e.status_code == 401:
        print("Invalid or expired token")
    elif e.status_code == 403:
        print("Access forbidden")
```

### Connection Errors with Identity Headers

When connection fails, the server may still provide identity information in error headers:

```python
from spacetimedb_sdk.exceptions import DatabaseNotFoundError

def on_error(error):
    if isinstance(error, DatabaseNotFoundError):
        # Check for identity headers in error
        if hasattr(error, 'diagnostic_info'):
            headers = error.diagnostic_info.get('headers', {})
            if 'spacetime-identity' in headers:
                print(f"Server assigned identity: {headers['spacetime-identity']}")
            if 'spacetime-identity-token' in headers:
                print(f"Server provided token: {headers['spacetime-identity-token']}")

client = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="non_existent_db",
    on_error=on_error
)
```

## Advanced Authentication

### Connection State Tracking

```python
# Monitor connection state during authentication
client = ModernSpacetimeDBClient()

# Add connection event listener
def on_connection_event(event):
    print(f"Connection event: {event.event_type.value}")
    if event.event_type == ConnectionEventType.CONNECTED:
        print(f"Connected with ID: {event.connection_id}")
    elif event.event_type == ConnectionEventType.IDENTITY_CHANGED:
        print(f"Identity changed: {event.data}")

client.add_connection_listener(on_connection_event)

# Get connection info
info = client.get_connection_info()
print(f"Connection state: {info['state']}")
print(f"Identity info: {info['identity_info']}")
```

### Multiple Connections with Same Identity

```python
# First connection - get token
client1 = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database"
)
token = client1.enhanced_identity_token.token

# Second connection - same identity
client2 = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database",
    auth_token=token
)

# Both clients share the same identity
assert client1.identity.to_hex() == client2.identity.to_hex()
```

## Security Best Practices

### 1. Token Storage

- Never hardcode tokens in source code
- Store tokens securely (e.g., environment variables, secure storage)
- Use appropriate file permissions for token files

```python
import os
import stat

# Secure token storage
token_file = os.path.expanduser('~/.spacetimedb/token')
os.makedirs(os.path.dirname(token_file), exist_ok=True)

# Write with restricted permissions
with open(token_file, 'w') as f:
    f.write(token)
os.chmod(token_file, stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions
```

### 2. Token Rotation

Implement token rotation for long-running applications:

```python
import time
import threading

class TokenManager:
    def __init__(self, client):
        self.client = client
        self.refresh_timer = None
        
    def start_auto_refresh(self, check_interval=3600):
        """Check token expiry every hour."""
        def check_and_refresh():
            if self.client.enhanced_identity_token:
                if self.client.enhanced_identity_token.refresh_if_needed(threshold=3600):
                    # Token needs refresh - reconnect
                    print("Token expiring soon, reconnecting...")
                    current_token = self.client.enhanced_identity_token.token
                    self.client.disconnect()
                    self.client.connect(
                        auth_token=current_token,
                        # ... other connection params
                    )
            
            # Schedule next check
            self.refresh_timer = threading.Timer(check_interval, check_and_refresh)
            self.refresh_timer.daemon = True
            self.refresh_timer.start()
        
        check_and_refresh()
    
    def stop_auto_refresh(self):
        if self.refresh_timer:
            self.refresh_timer.cancel()
```

### 3. Environment-based Authentication

```python
import os

def get_auth_token():
    """Get auth token from environment or file."""
    # Check environment variable first
    token = os.getenv('SPACETIMEDB_TOKEN')
    if token:
        return token
    
    # Check token file
    token_file = os.path.expanduser('~/.spacetimedb/token')
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            return f.read().strip()
    
    # No token found - will connect anonymously
    return None

# Use environment-based auth
client = ModernSpacetimeDBClient.connect(
    host=os.getenv('SPACETIMEDB_HOST', 'localhost:3000'),
    database_address=os.getenv('SPACETIMEDB_DATABASE', 'my_database'),
    auth_token=get_auth_token()
)
```

## Troubleshooting

### Common Authentication Issues

1. **Invalid Token Format**
   - Ensure token is a string, not bytes
   - Don't include "Bearer" or "Basic" prefix in the token
   - The SDK handles header construction

2. **Token Expired**
   - Tokens have a 24-hour default expiration
   - Implement token refresh or reconnection logic
   - Store new tokens received after reconnection

3. **Connection Rejected**
   - Verify the database exists and is published
   - Check server logs for authentication errors
   - Ensure SSL settings match server configuration

### Debugging Authentication

Enable debug logging to see authentication details:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Authentication headers and responses will be logged
client = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database",
    auth_token="debug_token"
)
```

### Testing Authentication

Run the verification script to test authentication:

```bash
# Test current authentication implementation
python test_v112_authentication_verify.py

# Run comprehensive test suite
python test_v112_authentication.py

# Run only unit tests (no server required)
SKIP_INTEGRATION_TESTS=true python test_v112_authentication.py
```

## Migration from Older Versions

If migrating from an older SDK version:

1. **Token Format**: The token format remains compatible
2. **Header Construction**: No changes needed in application code
3. **Identity Types**: Legacy `Identity` and `ConnectionId` types are still supported
4. **Enhanced Features**: New enhanced types provide additional functionality

```python
# Legacy code still works
identity = client.identity  # Legacy Identity type
connection_id = client.connection_id  # Legacy ConnectionId type

# New enhanced types available
enhanced_identity = client.enhanced_identity
enhanced_conn_id = client.enhanced_connection_id

# Conversion helpers
from spacetimedb_sdk.protocol import ensure_enhanced_identity
enhanced = ensure_enhanced_identity(identity)
```

## Examples

### Complete Authentication Example

```python
import os
import logging
from spacetimedb_sdk import ModernSpacetimeDBClient
from spacetimedb_sdk.exceptions import AuthenticationError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuthenticatedClient:
    def __init__(self, host, database):
        self.host = host
        self.database = database
        self.client = None
        self.token_file = os.path.expanduser('~/.spacetimedb/token')
        
    def connect(self):
        """Connect with stored token or anonymously."""
        token = self._load_token()
        
        try:
            self.client = ModernSpacetimeDBClient.connect(
                host=self.host,
                database_address=self.database,
                auth_token=token,
                on_identity=self._on_identity,
                on_error=self._on_error
            )
            logger.info("Connected successfully")
            return True
            
        except AuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            if e.status_code == 401 and token:
                # Token invalid, try anonymous
                logger.info("Retrying with anonymous connection")
                self._remove_token()
                return self.connect()
            return False
            
    def _on_identity(self, token, identity, connection_id):
        """Handle identity token received."""
        logger.info(f"Identity confirmed: {identity}")
        self._save_token(token)
        
    def _on_error(self, error):
        """Handle connection errors."""
        logger.error(f"Connection error: {error}")
        
    def _load_token(self):
        """Load stored token."""
        try:
            with open(self.token_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
            
    def _save_token(self, token):
        """Save token securely."""
        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
        with open(self.token_file, 'w') as f:
            f.write(token)
        os.chmod(self.token_file, 0o600)
        
    def _remove_token(self):
        """Remove stored token."""
        try:
            os.remove(self.token_file)
        except FileNotFoundError:
            pass

# Usage
if __name__ == "__main__":
    client = AuthenticatedClient("localhost:3000", "my_database")
    if client.connect():
        print("Ready to use SpacetimeDB!")
        # Use client.client for database operations
```

## Summary

The SpacetimeDB v1.1.2 authentication system provides:
- Simple anonymous and token-based authentication
- Automatic identity assignment and token generation
- Enhanced token management with expiration tracking
- Comprehensive error handling with diagnostic information
- Support for both legacy and enhanced identity types
- Secure token storage and rotation capabilities

For most applications, anonymous authentication with token persistence provides the best balance of simplicity and functionality.
