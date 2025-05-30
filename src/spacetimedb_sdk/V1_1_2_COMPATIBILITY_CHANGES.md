# SpacetimeDB Python SDK v1.1.2 Compatibility Changes

## Date: May 29, 2025

## Overview

The SpacetimeDB Python SDK requires updates to support SpacetimeDB server v1.1.2. This document outlines the necessary changes discovered through testing with the Blackholio agent project.

## Problem Statement

When attempting to connect to SpacetimeDB v1.1.2, the Python SDK fails with the following issues:

1. **Protocol Rejection**: Server returns "no valid protocol selected" error
2. **404 Errors**: WebSocket connections to `/v1/database/{name}/subscribe` fail
3. **Missing v1.1.2 Support**: SDK doesn't properly handle new endpoint structure

## Root Cause Analysis

### 1. Incorrect WebSocket Subprotocol

**Current**: `v1.text.spacetimedb` (hardcoded in `spacetimedb_client.py`)
**Required**: `v1.json.spacetimedb` or `v1.bsatn.spacetimedb`

The server rejects `v1.text.spacetimedb` with error: "no valid protocol selected"

### 2. Database Identity Requirements

SpacetimeDB v1.1.2 requires:
- Endpoint: `/v1/database/{identity}/subscribe`
- The `{identity}` must be the actual database identity (UUID/hash), not just the name

### 3. WebSocket Client Updates

The `spacetime_websocket_client.py` has been partially updated to support `db_identity`, but the main client doesn't utilize this properly.

## Required Changes

### 1. Update Protocol in `spacetimedb_client.py`

```python
# Line with WebSocketClient initialization
# Change from:
self.wsc = WebSocketClient(
    "v1.text.spacetimedb",  # <-- This needs to change
    ...
)

# To:
self.wsc = WebSocketClient(
    "v1.json.spacetimedb",  # <-- Updated protocol
    ...
)
```

### 2. Support Database Identity

The SDK should:
- Accept a `db_identity` parameter in connection methods
- Pass this to the WebSocketClient for proper endpoint construction
- Fall back to using `address_or_name` if identity not provided

### 3. Update Connection Flow

```python
# Ideal usage pattern:
client = SpacetimeDBClient(autogen_module)
client.connect(
    auth_token=token,
    host="localhost:3000",
    address_or_name="blackholio",  # Module name
    db_identity="actual-uuid-here",  # v1.1.2 requirement
    ssl_enabled=False,
    ...
)
```

## Test Results

### Before Changes
```
Protocol: v1.text.spacetimedb
Result: 400 Bad Request - "no valid protocol selected"
```

### After Protocol Update
```
Protocol: v1.json.spacetimedb  
Result: 404 Not Found (database needs to be published first)
```

### With Published Database
```
Protocol: v1.json.spacetimedb
Database: Published with known identity
Result: Successful connection
```

## Implementation Priority

1. **Immediate Fix**: Change hardcoded protocol to `v1.json.spacetimedb`
2. **Short-term**: Add proper `db_identity` support throughout the SDK
3. **Long-term**: Make protocol configurable, not hardcoded

## Testing Instructions

1. Apply protocol change to `spacetimedb_client.py`
2. Ensure SpacetimeDB v1.1.2 server is running
3. Publish a test database and note its identity
4. Test connection with:

```python
from spacetimedb_sdk import SpacetimeDBClient

# Create mock autogen module
class MockAutogen:
    __path__ = []

client = SpacetimeDBClient(MockAutogen())
client.connect(
    auth_token=None,
    host="localhost:3000", 
    address_or_name="test_db",
    ssl_enabled=False,
    on_connect=lambda: print("Connected!"),
    on_error=lambda e: print(f"Error: {e}")
)

# Update loop
for _ in range(10):
    client.update()
    time.sleep(0.1)
```

## Backward Compatibility

The protocol change from `v1.text.spacetimedb` to `v1.json.spacetimedb` may affect:
- Existing applications using older SpacetimeDB versions
- Consider making protocol configurable to maintain compatibility

## References

- SpacetimeDB v1.1.2 WebSocket endpoint: `/v1/database/{identity}/subscribe`
- Required subprotocols: `v1.json.spacetimedb`, `v1.bsatn.spacetimedb`
- Original issue discovered in: Blackholio Agent project

## Contact

For questions about these changes, refer to:
- Test scripts in: `/Users/punk1290/git/blackholio-agent/`
- Diagnostic results: `test_spacetimedb_endpoints.py`

---
*Document created by analysis of SpacetimeDB v1.1.2 compatibility issues*
