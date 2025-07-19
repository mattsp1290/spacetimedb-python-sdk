# SpacetimeDB Python SDK - V1 Prefix Fix Summary

## Issue
The pygame client was unable to connect to the SpacetimeDB server because the Python SDK was constructing URLs without the required `/v1` prefix that the server expects for all API endpoints.

## Root Cause
The SpacetimeDB server routes all API endpoints under the `/v1` prefix (as defined in `crates/client-api/src/routes/mod.rs`), but the Python SDK was constructing URLs directly without this prefix.

## Changes Made

### 1. WebSocket Client (`src/spacetimedb_sdk/websocket_client.py`)
- **Before**: `{protocol_scheme}://{self.host}/database/subscribe/{self.database_address}`
- **After**: `{protocol_scheme}://{self.host}/v1/database/subscribe/{self.database_address}`

### 2. Legacy WebSocket Client (`src/spacetimedb_sdk/spacetime_websocket_client.py`)
- **Before**: `{protocol}://{host}/database/subscribe/{name_or_address}`
- **After**: `{protocol}://{host}/v1/database/subscribe/{name_or_address}`

### 3. JSON API Client (`src/spacetimedb_sdk/json_api.py`)
Updated all HTTP endpoints to include `/v1` prefix:
- `/databases` → `/v1/databases`
- `/databases/{name}` → `/v1/database/{name}`
- `/identity` → `/v1/identity`
- `/databases/{name}/reducers/{reducer}/call` → `/v1/database/{name}/call/{reducer}`
- `/databases/{name}/module` → `/v1/database/{name}/schema`
- `/databases/{name}/sql` → `/v1/database/{name}/sql`

## Testing the Fix
The pygame client should now be able to connect to the SpacetimeDB server. Test with:

```python
# The adapter should now work correctly
from spacetimedb_adapter import SpacetimeDBAdapter

adapter = SpacetimeDBAdapter(server_url="ws://localhost:3000")
await adapter.connect()  # This should now succeed
```

## Note
This fix ensures compatibility with the current SpacetimeDB server API structure where all routes are nested under `/v1`.
