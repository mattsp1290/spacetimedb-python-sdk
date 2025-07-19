# SpacetimeDB v1.1.2 Investigation Results

## Key Findings

### 1. Docker Configuration ✓
- The docker-compose.production.yml correctly exposes port 3000
- The Dockerfile.prod correctly sets up the environment
- The container is running with correct parameters:
  ```
  spacetimedb-standalone start --data-dir /var/lib/spacetimedb --listen-addr 0.0.0.0:3000 --jwt-pub-key-path /etc/spacetimedb/keys/jwt_public.pem --jwt-priv-key-path /etc/spacetimedb/keys/jwt_private.pem
  ```
- JWT keys exist and are properly mounted

### 2. Server Code Analysis

From `standalone/src/subcommands/start.rs`:
```rust
let extra = axum::Router::new().nest("/health", spacetimedb_client_api::routes::health::router());
let service = router(&ctx, db_routes, extra).with_state(ctx);
```

The server IS setting up HTTP routes via the `router` function from `spacetimedb_client_api`.

### 3. Protocol Constants Found

From `standalone/src/lib.rs`:
```rust
pub use spacetimedb_client_api::routes::subscribe::{BIN_PROTOCOL, TEXT_PROTOCOL};
```

These are the WebSocket subprotocols the CLI uses.

### 4. CLI Connection Method

From `cli/src/subcommands/subscribe.rs`:
- Connects to WebSocket endpoint at `/subscribe` 
- Uses `TEXT_PROTOCOL` as the WebSocket subprotocol
- Converts HTTP URI to WebSocket URI (http→ws, https→wss)

## Root Cause Analysis

The issue appears to be in the `router` function from `spacetimedb_client_api::routes`. We need to check if:

1. The router is actually registering the `/subscribe` endpoint
2. The router is handling WebSocket upgrades correctly
3. There's a configuration or initialization issue

## Next Steps

1. Check `spacetimedb_client_api::routes::router` implementation
2. Verify if there's a missing configuration flag
3. Check if the issue is specific to v1.1.2 vs earlier versions
