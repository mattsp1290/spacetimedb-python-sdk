# Update SpacetimeDB Python SDK for v1.1.2 Compatibility

## Context and Motivation

The SpacetimeDB Python SDK (located at `/Users/punk1290/git/spacetimedb-python-sdk`) is currently incompatible with SpacetimeDB v1.1.2. This is blocking the Blackholio ML agent training system from connecting to the SpacetimeDB server. The training system can only run in mock mode until this is fixed.

## The Problem

When attempting to connect to SpacetimeDB v1.1.2, the SDK fails with:
```
[Errno 8] nodename nor servname provided, or not known
```

After extensive debugging, we discovered that SpacetimeDB v1.1.2 has fundamentally changed its WebSocket API structure, and all the WebSocket endpoints the SDK expects now return 404 errors.

## Technical Details

### What Currently Happens:
1. The SDK attempts to connect to WebSocket endpoints like:
   - `ws://localhost:3000/database/ws/{database_id}`
   - `ws://localhost:3000/database/ws/blackholio`
   - `ws://localhost:3000/ws`

2. All these endpoints return `404 Not Found` in SpacetimeDB v1.1.2

3. The SDK's `spacetimedb_client.py` expects these endpoints to exist for real-time communication

### What Still Works:
- HTTP endpoints (e.g., `/health` returns 200 OK)
- Module publishing via CLI (`spacetime publish`)
- Database operations through the CLI

## Test Environment Setup

To test your changes, you'll need:

1. **SpacetimeDB v1.1.2 running in Docker**:
```bash
docker run -d --name spacetimedb-test -p 3000:3000 -v spacetimedb-data:/var/lib/spacetimedb spacetimedb:latest start
```

2. **Test script** (create this in the SDK directory):
```python
#!/usr/bin/env python
import sys
sys.path.append('src')
from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient

# Test connection
client = SpacetimeDBClient.init(
    host="localhost:3000",
    address_or_name="test_module",
    ssl_enabled=False
)

# Should connect without errors
print("Connection successful!" if client.is_connected else "Connection failed")
```

3. **Reference test files** from the Blackholio agent project:
   - `/Users/punk1290/git/blackholio-agent/test_minimal_connection.py` - Shows various connection attempts
   - `/Users/punk1290/git/blackholio-agent/test_websocket_connection.py` - Direct WebSocket testing
   - `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/connection.py` - How the SDK is currently used

## Your Mission

1. **Discover the new API structure** in SpacetimeDB v1.1.2:
   - Use browser dev tools or curl to explore available endpoints
   - Check SpacetimeDB v1.1.2 documentation or source code
   - Look for new WebSocket paths or connection protocols

2. **Update the SDK** to use the new API:
   - Modify the connection logic in `spacetimedb_client.py`
   - Update WebSocket endpoint URLs
   - Handle any protocol changes

3. **Maintain backward compatibility** if possible:
   - Detect SpacetimeDB version and use appropriate endpoints
   - Or provide a version parameter in the SDK

4. **Test thoroughly**:
   - Connection establishment
   - Table subscriptions
   - Reducer calls
   - Reconnection logic

## Success Criteria

The SDK update is successful when:
1. The Blackholio agent can connect to SpacetimeDB v1.1.2 without mock mode
2. All WebSocket connections establish successfully
3. Table subscriptions work (Entity, Player, Circle, Food tables)
4. Reducer calls execute properly
5. The connection remains stable during training

## Additional Resources

- **Debugging documentation**: `/Users/punk1290/git/blackholio-agent/docs/SPACETIMEDB_CONNECTION_FIX.md`
- **SpacetimeDB CLI**: Works correctly, so you can use it as a reference for the correct API
- **Working example**: The SpacetimeDB CLI command `spacetime subscribe` successfully connects - trace its network calls

## Testing Your Fix

Once you update the SDK, test it with:
```bash
cd /Users/punk1290/git/blackholio-agent
python scripts/train_agent.py --total-timesteps 1000 --n-envs 2 --experiment-name sdk_test
```

If it connects and starts training without the `--mock` flag, you've succeeded!

Good luck! This fix will unblock the entire Blackholio ML training pipeline.
