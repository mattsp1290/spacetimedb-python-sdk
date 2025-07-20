# SpacetimeDB v1.1.2 Protocol Migration Guide for Client Implementations

## Purpose

This guide is designed for agents/developers updating SpacetimeDB client implementations from v1.x to v1.1.2 compatibility. The v1.1.2 release introduces breaking changes in the WebSocket protocol that require client updates.

## Critical Breaking Changes

### 1. WebSocket URL Structure Change

**BREAKING**: The WebSocket endpoint URL format has fundamentally changed.

**Before (v1.0.x):**
```
ws://host:port/database/module_name/subscribe
wss://host:port/database/module_name/subscribe
```

**After (v1.1.2):**
```
ws://host:port/v1/ws/database/module_name/subscribe?db_identity=<uuid_or_hash>
wss://host:port/v1/ws/database/module_name/subscribe?db_identity=<uuid_or_hash>
```

### 2. Required Parameters

- `db_identity` is now **REQUIRED** in the connection URL as a query parameter
- The `/v1/ws/` prefix is **REQUIRED** for all WebSocket connections
- Protocol version must be explicitly specified in the connection headers

### 3. Protocol Version Handling

**Old protocols rejected**: Servers v1.1.2+ will reject connections without the `/v1/` prefix and proper protocol headers.

## Implementation Checklist

### Connection Code Updates

- [ ] Add `/v1/ws/` prefix to all WebSocket URLs
- [ ] Add `db_identity` query parameter to connection URLs
- [ ] Update protocol headers to include version specification
- [ ] Handle protocol rejection errors (HTTP 404 for old endpoints)
- [ ] Implement fallback logic for older server versions

### Error Handling Updates

- [ ] Detect v1.1.2 protocol rejection (404 on old endpoints)
- [ ] Provide clear error messages for missing `db_identity`
- [ ] Guide users to upgrade when connecting to v1.1.2+ servers
- [ ] Handle new error response formats

### Testing Requirements

- [ ] Test connection with v1.1.2 servers
- [ ] Test graceful fallback for older servers
- [ ] Verify `db_identity` parameter handling
- [ ] Test protocol version negotiation
- [ ] Verify error messages are helpful

## Code Transformation Examples

### Python Implementation

**Before:**
```python
def connect(host, database_name, auth_token=None):
    protocol = "wss" if ssl_enabled else "ws"
    url = f"{protocol}://{host}/database/{database_name}/subscribe"
    ws = websocket.WebSocketApp(url, header={"Authorization": f"Bearer {auth_token}"})
    ws.run_forever()
```

**After:**
```python
def connect(host, database_name, auth_token=None, db_identity=None):
    # Use db_identity if provided, otherwise use database_name
    identity = db_identity or database_name
    
    protocol = "wss" if ssl_enabled else "ws"
    url = f"{protocol}://{host}/v1/ws/database/{database_name}/subscribe?db_identity={identity}"
    
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Sec-WebSocket-Protocol": "v1.text.spacetimedb"  # or "v1.bin.spacetimedb"
    }
    
    ws = websocket.WebSocketApp(url, header=headers)
    ws.run_forever()
```

### JavaScript/TypeScript Implementation

**Before:**
```javascript
function connect(host, databaseName, authToken) {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${host}/database/${databaseName}/subscribe`;
    
    const ws = new WebSocket(url);
    ws.onopen = () => console.log('Connected');
}
```

**After:**
```javascript
function connect(host, databaseName, authToken, dbIdentity) {
    const identity = dbIdentity || databaseName;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${host}/v1/ws/database/${databaseName}/subscribe?db_identity=${identity}`;
    
    // Include protocol in subprotocols
    const ws = new WebSocket(url, ['v1.text.spacetimedb']);
    
    // Add auth token after connection
    ws.onopen = () => {
        if (authToken) {
            ws.send(JSON.stringify({
                type: "Authenticate",
                token: authToken
            }));
        }
    };
}
```

### Rust Implementation

**Before:**
```rust
async fn connect(host: &str, database: &str, auth_token: Option<&str>) -> Result<()> {
    let url = format!("ws://{}/database/{}/subscribe", host, database);
    let (ws_stream, _) = connect_async(&url).await?;
    // ...
}
```

**After:**
```rust
async fn connect(
    host: &str, 
    database: &str, 
    auth_token: Option<&str>,
    db_identity: Option<&str>
) -> Result<()> {
    let identity = db_identity.unwrap_or(database);
    let url = format!(
        "ws://{}/v1/ws/database/{}/subscribe?db_identity={}", 
        host, database, identity
    );
    
    let mut request = url.into_client_request()?;
    request.headers_mut().insert(
        "Sec-WebSocket-Protocol",
        "v1.bin.spacetimedb".parse()?
    );
    
    if let Some(token) = auth_token {
        request.headers_mut().insert(
            "Authorization",
            format!("Bearer {}", token).parse()?
        );
    }
    
    let (ws_stream, _) = connect_async(request).await?;
    // ...
}
```

## Protocol Message Changes

### Identity Token

The identity token message structure remains the same, but the connection handshake has changed.

### Subscription Messages

Subscription messages now require proper protocol encoding based on the negotiated protocol (text vs binary).

## Error Response Formats

### Old Server Response (v1.0.x)
```
HTTP/1.1 101 Switching Protocols
```

### New Server Response (v1.1.2+)
```
HTTP/1.1 101 Switching Protocols
Sec-WebSocket-Protocol: v1.text.spacetimedb
```

### Error: Missing v1 Prefix
```
HTTP/1.1 404 Not Found
Content-Type: application/json

{
    "error": "Invalid endpoint. Use /v1/ws/database/... for v1.1.2+"
}
```

### Error: Missing db_identity
```
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
    "error": "Missing required parameter: db_identity"
}
```

## Validation Steps

### 1. URL Construction Test
```python
def test_url_construction():
    url = build_websocket_url("localhost:3000", "my_db", "test_identity")
    assert "/v1/ws/" in url
    assert "db_identity=test_identity" in url
```

### 2. Protocol Header Test
```python
def test_protocol_headers():
    headers = build_connection_headers("text")
    assert headers["Sec-WebSocket-Protocol"] == "v1.text.spacetimedb"
```

### 3. Error Handling Test
```python
def test_old_endpoint_rejection():
    try:
        connect_to_old_endpoint()
    except WebSocketException as e:
        assert e.status_code == 404
        assert "v1.1.2" in str(e)
```

## Common Pitfalls

1. **Forgetting the /v1/ws/ prefix**: Results in 404 errors
2. **Missing db_identity parameter**: Results in 400 errors
3. **Using old protocol headers**: Connection rejected
4. **Not handling underscore in database names**: Some servers reject `_` in names
5. **Incorrect SSL/TLS handling**: Ensure wss:// is used for secure connections

## Migration Strategy

### Phase 1: Detection
1. Attempt connection with new protocol
2. If 404, fall back to old protocol
3. Log deprecation warnings for old protocol usage

### Phase 2: Dual Support
1. Maintain both old and new connection methods
2. Use server version detection to choose protocol
3. Prefer new protocol when available

### Phase 3: Deprecation
1. Remove old protocol support
2. Require minimum server version 1.1.2
3. Clear error messages for old servers

## Server Version Detection

```python
def detect_server_version(host):
    # Try v1.1.2 endpoint
    try:
        response = requests.get(f"http://{host}/v1/health")
        if response.ok:
            return "1.1.2+"
    except:
        pass
    
    # Try old endpoint
    try:
        response = requests.get(f"http://{host}/health")
        if response.ok:
            return "1.0.x"
    except:
        pass
    
    return "unknown"
```

## Testing Against Real Servers

1. **Local Testing**: Use SpacetimeDB v1.1.2 locally
2. **Integration Tests**: Test against both old and new servers
3. **Error Scenarios**: Test all error conditions
4. **Performance**: Verify no performance regression

## Support Resources

- SpacetimeDB v1.1.2 Release Notes
- Protocol Specification: `/v1/ws/` endpoint documentation
- Example Implementations: Reference clients in various languages
- Community Support: Discord/GitHub discussions

## Summary

The v1.1.2 migration primarily involves:
1. Updating WebSocket URLs with `/v1/ws/` prefix
2. Adding `db_identity` parameter
3. Updating protocol headers
4. Handling new error formats
5. Testing thoroughly

Following this guide ensures smooth migration to SpacetimeDB v1.1.2 protocol.
