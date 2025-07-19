# SpacetimeDB v1.1.2 Python SDK Fix Summary

## Quick Start

1. **Run discovery tools** to find the actual WebSocket endpoint:
   ```bash
   # Basic discovery
   python3 test_spacetimedb_v1_1_2_connection.py
   
   # Advanced discovery
   python3 discover_websocket_endpoint.py
   
   # Network analysis (requires sudo)
   sudo python3 analyze_cli_traffic.py
   ```

2. **Generate patch files** for common patterns:
   ```bash
   python3 spacetimedb_v1_1_2_fix.py
   ```
   This creates patch files for the most likely patterns:
   - `apply_v1_1_2_patch_simple_ws.py` - For `/ws` endpoint
   - `apply_v1_1_2_patch_simple_websocket.py` - For `/websocket` endpoint
   - `apply_v1_1_2_patch_versioned_ws.py` - For `/v1/ws` endpoint

3. **Apply the appropriate patch** based on discovery:
   ```bash
   # Example: if you discovered the endpoint is /ws
   python3 apply_v1_1_2_patch_simple_ws.py
   ```

4. **Test the fix**:
   ```bash
   python3 test_spacetimedb_v1_1_2_connection.py
   ```

5. **Test with Blackholio agent**:
   ```bash
   cd /Users/punk1290/git/blackholio-agent
   python scripts/train_agent.py --total-timesteps 1000 --n-envs 2
   ```

## The Problem

SpacetimeDB v1.1.2 has changed its WebSocket API endpoints:
- **Old (v1.0.x)**: `ws://localhost:3000/v1/database/subscribe/{database_name}`
- **New (v1.1.2)**: Unknown - needs discovery

## Likely New Patterns

Based on modern WebSocket API design, v1.1.2 likely uses one of these patterns:

1. **Simple WebSocket** (`/ws` or `/websocket`)
   - Connect to generic endpoint
   - Send subscription message after connection
   
2. **Versioned WebSocket** (`/v1/ws` or `/api/v1/ws`)
   - Similar to simple, but with API versioning
   
3. **Database-specific** (`/database/{name}/ws`)
   - Database specified in URL path

## Tools Provided

### Discovery Tools

1. **test_spacetimedb_v1_1_2_connection.py**
   - Tests various HTTP and WebSocket endpoints
   - Shows current SDK failure
   - Provides basic endpoint discovery

2. **discover_websocket_endpoint.py**
   - Advanced async discovery
   - Tests multiple patterns systematically
   - Attempts various subscription formats

3. **analyze_cli_traffic.py**
   - Network traffic capture and analysis
   - Multiple methods (tcpdump, lsof, proxy)
   - Analyzes working CLI connections

### Fix Tools

1. **spacetimedb_v1_1_2_fix.py**
   - Generates patch files for different patterns
   - Configurable endpoint patterns
   - Subscription message templates

2. **apply_v1_1_2_patch_*.py** (generated)
   - Patches both WebSocket client files
   - Updates URL construction
   - Adds subscription logic if needed

## Manual Fix (if needed)

If the automated patches don't work, manually update:

### 1. src/spacetimedb_sdk/spacetime_websocket_client.py
```python
# Line 23 - Change from:
url = f"{protocol}://{host}/v1/database/subscribe/{name_or_address}"

# To (example for /ws pattern):
url = f"{protocol}://{host}/ws"
```

### 2. src/spacetimedb_sdk/websocket_client.py
```python
# Line 186 - Change from:
url = f"{protocol_scheme}://{host}/v1/database/subscribe/{self.database_address}"

# To (example for /ws pattern):
url = f"{protocol_scheme}://{host}/ws"
```

### 3. Add subscription message (if URL doesn't include database)
In `websocket_client.py`, after connection is established:
```python
# Send subscription message
subscription_msg = {
    "type": "subscribe",
    "database": self.database_address
}
self.send_message(subscription_msg)
```

## Verification Steps

1. **Check HTTP endpoints work**:
   ```bash
   curl http://localhost:3000/health
   ```

2. **Run basic connection test**:
   ```bash
   python3 test_spacetimedb_v1_1_2_connection.py
   ```

3. **Check with simple script**:
   ```python
   import sys
   sys.path.insert(0, 'src')
   from spacetimedb_sdk import SpacetimeDBClient
   
   client = SpacetimeDBClient.init(
       auth_token=None,
       host="localhost:3000",
       address_or_name="test_module",
       ssl_enabled=False,
       autogen_package=None,
       on_connect=lambda: print("Connected!"),
       on_error=lambda err: print(f"Error: {err}")
   )
   ```

4. **Full integration test**:
   ```bash
   cd /Users/punk1290/git/blackholio-agent
   python scripts/train_agent.py --total-timesteps 1000
   ```

## Troubleshooting

1. **Still getting 404 errors?**
   - The endpoint pattern might be completely different
   - Use browser DevTools on http://localhost:3000
   - Check Docker logs: `docker logs <container_id>`

2. **Connection established but no data?**
   - Subscription message format might be wrong
   - Try different subscription patterns
   - Check server logs for errors

3. **Authentication issues?**
   - Check if v1.1.2 requires different auth headers
   - Try with and without auth token

## Next Steps

1. Use the discovery tools to find the actual endpoint
2. Apply the appropriate patch
3. Test thoroughly
4. Consider adding version detection for backward compatibility
5. Submit a PR with the fix

Good luck! The key is discovering what endpoint pattern SpacetimeDB v1.1.2 actually uses.
