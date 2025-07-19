# SpacetimeDB v1.1.2 Python SDK Compatibility Solution

## Issue Summary

The SpacetimeDB Python SDK was incompatible with v1.1.2 due to significant changes in the WebSocket API:

### Root Cause
1. **WebSocket Endpoint Changed**:
   - Old (pre-v1.1.2): `ws://host/ws`
   - New (v1.1.2): `ws://host/v1/database/{identity}/subscribe`

2. **WebSocket Subprotocol Required**:
   - v1.1.2 requires explicit subprotocol: `v1.json.spacetimedb` or `v1.bsatn.spacetimedb`
   - The SDK already supported this via the `protocol` parameter

3. **All HTTP endpoints moved under `/v1` prefix**:
   - This affects REST API calls but not the primary WebSocket issue

## Investigation Process

### 1. Initial Discovery
- Blackholio's SDK connection failed with SpacetimeDB v1.1.2
- CLI worked but Python SDK didn't, indicating a protocol mismatch

### 2. Deep Dive Analysis
- Examined Docker configuration ✓ (correct)
- Checked server routing code and found `/v1` prefix requirement
- Discovered WebSocket protocols in `client-api-messages/src/websocket.rs`
- Found the actual endpoint format in database routes

### 3. Key Findings
```rust
// From routes/database.rs
.route("/subscribe", self.subscribe_get)

// Combined with /v1 prefix and database routing:
// Final path: /v1/database/:identity/subscribe
```

## Solution Applied

### 1. Updated `spacetime_websocket_client.py`:
```python
# Added db_identity parameter
def connect(self, auth, host, name_or_address, ssl_enabled, db_identity=None):
    
# Updated URL construction
if db_identity:
    url = f"{protocol}://{host}/v1/database/{db_identity}/subscribe"
else:
    url = f"{protocol}://{host}/v1/database/{name_or_address}/subscribe"
```

### 2. The SDK already had proper WebSocket subprotocol support:
```python
self.ws = websocket.WebSocketApp(url,
                                 ...
                                 subprotocols=[self.protocol])
```

## Usage After Fix

```python
from spacetimedb_sdk import SpacetimeDBClient

# Create client with proper protocol
client = SpacetimeDBClient(protocol="v1.json.spacetimedb")

# Connect with database identity
client.connect(
    host="localhost:3000",
    name_or_address="your_database_identity",
    auth_token="your_token"
)
```

## Testing

Created `test_v1_1_2_websocket.py` for direct WebSocket testing:
```python
url = f"ws://localhost:3000/v1/database/{DB_IDENTITY}/subscribe"
ws = websocket.create_connection(url, subprotocols=["v1.json.spacetimedb"])
```

## Key Takeaways

1. **Breaking Change**: SpacetimeDB v1.1.2 completely changed the WebSocket endpoint structure
2. **Documentation Gap**: This change wasn't well documented in migration guides
3. **CLI vs SDK**: The CLI was updated for v1.1.2 but SDKs need manual updates
4. **Database Identity Required**: The new endpoint requires knowing the database identity upfront

## Recommendations

1. **For SDK Users**: Update to use the new endpoint format with database identity
2. **For SpacetimeDB Team**: 
   - Add backward compatibility or clear migration guide
   - Update all SDKs to support v1.1.2
   - Document the `/v1` prefix requirement clearly

## Files Modified

1. `src/spacetimedb_sdk/spacetime_websocket_client.py` - Added v1.1.2 WebSocket endpoint support
2. Created test scripts for verification

The Python SDK should now be compatible with SpacetimeDB v1.1.2!
