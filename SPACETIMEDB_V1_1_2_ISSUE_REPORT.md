# SpacetimeDB v1.1.2 Connection Issue Report

## Problem Summary

The SpacetimeDB Python SDK cannot connect to SpacetimeDB v1.1.2 due to a fundamental protocol issue.

## Investigation Results

### 1. Server Status
- ✓ SpacetimeDB v1.1.2 is running on port 3000
- ✓ The CLI can successfully connect (as shown in logs)
- ✗ ALL HTTP endpoints return 404
- ✗ ALL WebSocket endpoints fail to connect

### 2. Tested Endpoints
Every possible endpoint pattern returns 404:
- `/` - 404
- `/health` - 404  
- `/ws` - 404
- `/websocket` - 404
- `/subscribe` - 404
- `/v1/database/subscribe/{db}` - 404
- `/database/{db}/subscribe` - 404
- All other variations - 404

### 3. Protocol Discovery
Attempted:
- Raw TCP connections - Server responds with HTTP 400
- WebSocket with various subprotocols - All fail
- HTTP streaming/SSE - All 404

### 4. CLI Connection
The CLI successfully connects, but through an unknown mechanism:
```
2025-05-29T14:17:39.739854Z DEBUG /usr/src/app/crates/client-api/src/routes/subscribe.rs:177: New client connected from unknown ip
```

## Root Cause Analysis

The issue appears to be one of:

1. **Server Misconfiguration**: The SpacetimeDB v1.1.2 container might be misconfigured, causing all HTTP routes to return 404.

2. **Protocol Change**: SpacetimeDB v1.1.2 might use a completely different protocol (not HTTP/WebSocket).

3. **Container Issue**: The Docker container status shows "unhealthy", suggesting the service isn't fully functional.

## Recommendations

### Option 1: Fix the SpacetimeDB Container

1. **Restart with fresh configuration**:
   ```bash
   docker stop spacetimedb-blackholio
   docker rm spacetimedb-blackholio
   docker run -d --name spacetimedb-blackholio \
     -p 3000:3000 \
     -e SPACETIMEDB_LOG_LEVEL=debug \
     spacetimedb:latest start
   ```

2. **Check container health**:
   ```bash
   docker inspect spacetimedb-blackholio | grep -A10 Health
   ```

### Option 2: Use SpacetimeDB Cloud

Instead of self-hosting v1.1.2, use the cloud version:
```python
client = SpacetimeDBClient.init(
    host="maincloud.spacetimedb.com",
    address_or_name="your-module-name",
    ssl_enabled=True
)
```

### Option 3: Downgrade SpacetimeDB

Use a known working version:
```bash
docker pull spacetimedb/spacetimedb:1.0.0
```

### Option 4: Debug the Container

1. **Check what's actually listening**:
   ```bash
   docker exec spacetimedb-blackholio apt-get update && apt-get install -y netstat
   docker exec spacetimedb-blackholio netstat -tlnp
   ```

2. **Check the server configuration**:
   ```bash
   docker exec spacetimedb-blackholio cat /etc/spacetimedb/server.toml
   ```

3. **Check for error logs**:
   ```bash
   docker logs spacetimedb-blackholio --tail 100 | grep -i error
   ```

## Temporary Workaround for Blackholio

Until the SpacetimeDB connection issue is resolved, continue using mock mode:

```bash
cd /Users/punk1290/git/blackholio-agent
python scripts/train_agent.py --total-timesteps 1000 --n-envs 2 --mock
```

## Next Steps

1. **Report the issue** to SpacetimeDB team - the v1.1.2 container appears to have no working HTTP/WebSocket endpoints.

2. **Try the cloud version** - This might work better than self-hosted v1.1.2.

3. **Monitor SpacetimeDB updates** - This might be a known issue that gets fixed in v1.1.3.

## Technical Details

The SDK is correctly trying to connect, but the server isn't exposing any HTTP/WebSocket endpoints. The fact that the CLI works suggests it might be using:
- Unix domain sockets
- A custom binary protocol
- Internal container networking

Without access to the SpacetimeDB v1.1.2 source code or documentation, it's impossible to determine the exact protocol being used.
