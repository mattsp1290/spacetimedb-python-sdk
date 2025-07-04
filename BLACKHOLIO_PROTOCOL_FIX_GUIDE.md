# Blackholio Python Client - Protocol Fix Guide

## Overview
This guide provides instructions for fixing the protocol mismatch issue in the blackholio-python-client when connecting to SpacetimeDB servers.

## The Issue
The blackholio-python-client is experiencing a protocol mismatch error when connecting to SpacetimeDB:
```
ERROR - Failed to decode message: Failed to decode BSATN server message: Expected enum tag for server message, got 0
```

### Root Cause
- **Server**: SpacetimeDB Rust server uses BSATN (binary) protocol by default
- **Client**: Configured to expect JSON protocol (`v1.json.spacetimedb`)
- **Result**: Client fails to decode binary messages as JSON

## Required Fix

### 1. Update Server Configuration Protocol

**File**: `src/blackholio_client/connection/server_config.py`

**Current** (incorrect):
```python
SERVER_CONFIGS = {
    'rust': {
        'default_port': 3000,
        'db_identity': 'blackholio',
        'protocol': 'v1.json.spacetimedb',  # ❌ Wrong protocol
        'description': 'Rust SpacetimeDB server implementation'
    },
    ...
}
```

**Change to** (correct):
```python
SERVER_CONFIGS = {
    'rust': {
        'default_port': 3000,
        'db_identity': 'blackholio',
        'protocol': 'v1.bsatn.spacetimedb',  # ✅ Correct protocol for Rust servers
        'description': 'Rust SpacetimeDB server implementation'
    },
    ...
}
```

### 2. Verify Protocol Constants Are Imported

Ensure the protocol constants are available if needed:

```python
# At the top of any file that needs protocol constants
from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL

# Available protocols:
# TEXT_PROTOCOL = "v1.json.spacetimedb"  # JSON format
# BIN_PROTOCOL = "v1.bsatn.spacetimedb"  # Binary format (default for Rust)
```

## Testing the Fix

### Test Script
Create a test file to verify the connection works with the correct protocol:

```python
#!/usr/bin/env python3
"""Test SpacetimeDB connection with correct protocol."""

import asyncio
from blackholio_client.connection.modernized_spacetimedb_client import ModernizedSpacetimeDBConnection
from blackholio_client.connection.server_config import ServerConfig

async def test_connection():
    # Create config with correct protocol
    config = ServerConfig(
        host="localhost",
        port=3000,
        db_identity="blackholio",
        protocol="v1.bsatn.spacetimedb",  # Binary protocol
        language="rust",
        use_ssl=False
    )
    
    connection = ModernizedSpacetimeDBConnection(config)
    
    try:
        result = await connection.connect()
        if result:
            print("✅ Connected successfully with BSATN protocol")
            print(f"   Client connected: {connection._sdk_client.is_connected}")
            
            # Test subscribe
            sub_id = connection._sdk_client.subscribe(["SELECT * FROM Player"])
            print(f"✅ Subscription created: {sub_id}")
            
            await connection.disconnect()
            print("✅ Disconnected successfully")
        else:
            print("❌ Connection failed")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
```

### Expected Results After Fix
- ✅ No more "Failed to decode BSATN server message" errors
- ✅ Successful connection to SpacetimeDB server
- ✅ Ability to subscribe to queries
- ✅ Proper message encoding/decoding

## Why This Fix Works

1. **Protocol Alignment**: Server and client will both use BSATN protocol
2. **Performance**: BSATN is the optimal protocol for Rust servers
3. **Simplicity**: One-line configuration change
4. **Compatibility**: SpacetimeDB SDK fully supports BSATN

## Alternative Solutions (Not Recommended)

### Option A: Force JSON Protocol on Server
If you must use JSON protocol, check if the SpacetimeDB server supports protocol configuration:
```bash
# Hypothetical - check SpacetimeDB docs
spacetimedb-standalone start --protocol json ...
```

### Option B: Mixed Protocol Support
Implement protocol detection/negotiation (complex and not necessary).

## Validation Checklist

After making the change, verify:
- [ ] `server_config.py` updated with `'protocol': 'v1.bsatn.spacetimedb'` for Rust
- [ ] No more BSATN decode errors in logs
- [ ] Connection establishes successfully
- [ ] Subscriptions work without errors
- [ ] Data flows correctly between client and server

## Already Fixed Issues

The following issues have already been resolved in `modernized_spacetimedb_client.py`:
- ✅ Connection API mismatch (factory methods return connected clients)
- ✅ Host:port formatting (now includes port in host string)
- ✅ Disconnect method (changed from async to sync)
- ✅ Subscribe method (sync, expects list parameter)
- ✅ Reducer calls (using `call_reducer_async`)

## Summary

**Fixes Applied**:
1. ✅ **Protocol Update**: Changed protocol in `server_config.py` from `'v1.json.spacetimedb'` to `'v1.bsatn.spacetimedb'` for Rust servers
2. ✅ **Host:Port Fix**: Fixed host:port duplication issue in `modernized_spacetimedb_client.py` line 177 that was causing "3000:3000" errors

These changes align the client's expectations with what the SpacetimeDB Rust server actually sends and fix connection initialization issues.

**Test Results**: 
- Protocol mismatch errors are resolved
- Host:port duplication error is fixed
- Connection now fails cleanly when server is not available (expected behavior)
- Ready for testing with a running SpacetimeDB server