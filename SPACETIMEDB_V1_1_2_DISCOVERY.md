# SpacetimeDB v1.1.2 WebSocket Endpoint Discovery

This document explains how to discover the new WebSocket endpoints in SpacetimeDB v1.1.2 and fix the Python SDK compatibility issue.

## The Problem

The Python SDK currently expects WebSocket endpoints at:
- `ws://localhost:3000/v1/database/subscribe/{database_name}`

In SpacetimeDB v1.1.2, this endpoint returns 404 Not Found.

## Discovery Tools

We've created three scripts to help discover the new endpoints:

### 1. test_spacetimedb_v1_1_2_connection.py
Basic connection tester that:
- Tests various HTTP endpoints to understand the API structure
- Tries multiple WebSocket URL patterns
- Shows the current SDK failure

**Usage:**
```bash
# First, ensure SpacetimeDB v1.1.2 is running:
docker run -d --name spacetimedb-test -p 3000:3000 spacetimedb:latest start

# Run the test script
python3 test_spacetimedb_v1_1_2_connection.py
```

### 2. discover_websocket_endpoint.py
Advanced async WebSocket discovery tool that:
- Discovers HTTP API endpoints for clues
- Tests various WebSocket patterns systematically
- Attempts different subscription message formats

**Usage:**
```bash
# Install dependencies
pip install aiohttp websockets

# Run discovery
python3 discover_websocket_endpoint.py --host localhost:3000 --database test_module
```

### 3. analyze_cli_traffic.py
Network traffic analyzer to capture what the working CLI does:
- Uses tcpdump/lsof to capture network traffic
- Analyzes the spacetime CLI's successful connections
- Provides multiple analysis methods

**Usage:**
```bash
# On macOS (requires sudo)
sudo python3 analyze_cli_traffic.py

# Alternative: Use with proxy
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
spacetime subscribe test_module
```

## Manual Discovery Methods

### Method 1: Browser Developer Tools
1. Open http://localhost:3000 in Chrome/Firefox
2. Open Developer Tools (F12)
3. Go to Network tab
4. Filter by "WS" (WebSocket)
5. Look for any WebSocket connections made by the web interface

### Method 2: Docker Logs
```bash
# Get container ID
docker ps

# Check logs for WebSocket hints
docker logs <container_id> | grep -i websocket
docker logs <container_id> | grep -i "upgrade"
```

### Method 3: tcpdump Manual Analysis
```bash
# Start capture (macOS)
sudo tcpdump -i lo0 -A -s 0 'port 3000' -w spacetime.pcap

# In another terminal, run working CLI
spacetime subscribe test_module

# Stop tcpdump (Ctrl+C) and analyze
tcpdump -r spacetime.pcap -A | grep -i "GET.*HTTP"
```

### Method 4: mitmproxy Interception
```bash
# Install mitmproxy
pip install mitmproxy

# Start proxy
mitmweb --listen-port 8080

# Configure environment
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080

# Run CLI
spacetime subscribe test_module

# Check mitmweb interface at http://localhost:8081
```

## Common WebSocket Endpoint Patterns

Based on modern web services, the new endpoint might be:

1. **Simple pattern**: `/ws` or `/websocket`
2. **Versioned**: `/v1/ws` or `/api/v1/websocket`
3. **Resource-based**: `/database/{name}/ws`
4. **Connect-then-subscribe**: Connect to `/ws`, then send subscription message

## Quick Fix Attempts

Once you discover the endpoint, try these quick fixes:

### Fix 1: Update URLs in spacetime_websocket_client.py
```python
# Line 23 - Old:
url = f"{protocol}://{host}/v1/database/subscribe/{name_or_address}"

# New (example):
url = f"{protocol}://{host}/ws"  # or whatever you discovered
```

### Fix 2: Update URLs in websocket_client.py
```python
# Line 186 - Old:
url = f"{protocol_scheme}://{host}/v1/database/subscribe/{self.database_address}"

# New (example):
url = f"{protocol_scheme}://{host}/ws"
```

### Fix 3: Add version detection
```python
def get_websocket_url(host, database, version="1.1.2"):
    if version >= "1.1.2":
        return f"ws://{host}/ws"  # New pattern
    else:
        return f"ws://{host}/v1/database/subscribe/{database}"  # Legacy
```

## Testing Your Fix

After updating the SDK:

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient

client = SpacetimeDBClient.init(
    auth_token=None,
    host="localhost:3000",
    address_or_name="test_module",
    ssl_enabled=False,
    autogen_package=None,
    on_connect=lambda: print("Connected!"),
    on_error=lambda err: print(f"Error: {err}")
)

# Test with the Blackholio agent
cd /Users/punk1290/git/blackholio-agent
python scripts/train_agent.py --total-timesteps 1000 --n-envs 2
```

## Next Steps

1. Run the discovery scripts to find the actual endpoint
2. Update both WebSocket client files with the new URL pattern
3. Test the connection
4. Implement backward compatibility if needed
5. Submit the fix

Good luck! The key is finding what URL the working CLI uses for WebSocket connections.
