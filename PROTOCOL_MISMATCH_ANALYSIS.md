# SpacetimeDB Protocol Mismatch Analysis

## The Problem

When connecting to a SpacetimeDB server, we're seeing this error:
```
ERROR - Failed to decode message: Failed to decode BSATN server message: Expected enum tag for server message, got 0
```

## Root Cause

There's a protocol mismatch between what the server is sending and what the client expects:

1. **SpacetimeDB Server** (started with your command) defaults to **BSATN protocol** (binary format)
2. **Blackholio Client Config** specifies `protocol: 'v1.json.spacetimedb'` (JSON format)
3. **SDK Rust Factory** defaults to `BIN_PROTOCOL` (BSATN) for performance

## The Mismatch Flow

```
Server (BSATN) → Client expects JSON → Decoding fails
```

## Solutions

### Option 1: Force Client to Use JSON Protocol (Implemented)

We've updated the client to explicitly pass the protocol from config:
```python
self._sdk_client = create_rust_client(
    host=host_with_port,
    database=self._sdk_server_config.database,
    auth_token=self._sdk_server_config.auth_token,
    protocol=self.config.protocol  # 'v1.json.spacetimedb'
)
```

### Option 2: Configure Server for JSON Protocol

The server might need to be configured to use JSON protocol. Check if there's a flag like:
```bash
spacetimedb-standalone start --protocol json ...
```

### Option 3: Change Client to Use Binary Protocol

Update the blackholio ServerConfig to use binary protocol:
```python
'rust': {
    'default_port': 3000,
    'db_identity': 'blackholio',
    'protocol': 'v1.bsatn.spacetimedb',  # Changed from v1.json.spacetimedb
    'description': 'Rust SpacetimeDB server implementation'
}
```

## Protocol Details

- **JSON Protocol**: `v1.json.spacetimedb`
  - Human-readable
  - Easier to debug
  - Slightly slower

- **BSATN Protocol**: `v1.bsatn.spacetimedb`
  - Binary format
  - More efficient
  - Default for Rust servers

## Recommendation

Since the SpacetimeDB server is a Rust implementation, it's optimized for BSATN. I recommend:

1. **Update the blackholio ServerConfig** to use `'v1.bsatn.spacetimedb'`
2. **Or** check SpacetimeDB server documentation for protocol configuration options

The error "Expected enum tag for server message, got 0" suggests the server is definitely sending binary data when the client expects JSON structure.