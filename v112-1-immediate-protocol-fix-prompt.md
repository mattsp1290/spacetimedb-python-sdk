# Task v112-1: Immediate Protocol Fix for SpacetimeDB v1.1.2 Compatibility

## Context

Users are currently blocked from using the SpacetimeDB Python SDK with SpacetimeDB server v1.1.2 due to an outdated WebSocket protocol. The server rejects connections with the error "no valid protocol selected".

**Task Reference**: `/Users/punk1290/git/spacetimedb-python-sdk/spacetimedb-v112-compatibility-tasks.yaml` - Task v112-1

## Problem

1. **Current Protocol**: The SDK uses `"v1.text.spacetimedb"` (hardcoded in `spacetimedb_client.py`)
2. **Required Protocol**: SpacetimeDB v1.1.2 requires `"v1.json.spacetimedb"` or `"v1.bsatn.spacetimedb"`
3. **Database Identity**: v1.1.2 also requires database identity (UUID/hash) in the WebSocket URL format: `/v1/database/{identity}/subscribe`

## Implementation Requirements

### 1. Update Protocol String
- **File**: `src/spacetimedb_sdk/spacetimedb_client.py`
- **Location**: In the `connect()` method around line 312 where `WebSocketClient` is initialized
- **Change**: `"v1.text.spacetimedb"` → `"v1.json.spacetimedb"`

### 2. Add Database Identity Support
- Add `db_identity` parameter to:
  - `connect()` method
  - `init()` class method (to pass through to `connect()`)
- Pass `db_identity` to `WebSocketClient` (which already supports it according to the compatibility analysis)

### 3. Important Notes
- This is a **BREAKING CHANGE** - SDK will no longer work with SpacetimeDB < v1.1.2
- The `spacetime_websocket_client.py` already has partial support for `db_identity`
- The canonical protocol constants are defined in `src/spacetimedb_sdk/protocol.py` as `TEXT_PROTOCOL = "v1.json.spacetimedb"`

## Testing Environment
- **Server**: SpacetimeDB running on `localhost:3000` (Docker container ID: 027e3ed65892)
- **Test Module**: Available at `/Users/punk1290/git/Blackholio/server-rust`
- **Validation**: Need to verify "no valid protocol selected" error is resolved

## Implementation Steps

1. **Examine current implementation**:
   - Check exact line numbers and current structure in `spacetimedb_client.py`
   - Verify `WebSocketClient` interface in `spacetime_websocket_client.py`

2. **Make minimal changes**:
   - Update protocol string
   - Add `db_identity` parameter handling
   - Ensure parameter is passed correctly to WebSocketClient

3. **Create test script**:
   - Write a simple connection test to verify the fix works
   - Test with the Blackholio server module if possible

4. **Run existing tests**:
   - Execute test suite to identify any broken tests
   - Fix tests as needed (as mentioned by the user)

## Success Criteria
- Connection to SpacetimeDB v1.1.2 succeeds without "no valid protocol selected" error
- `db_identity` parameter is properly handled when provided
- Existing functionality remains intact (except for the breaking change of requiring v1.1.2+)

## Files to Examine/Modify
1. `src/spacetimedb_sdk/spacetimedb_client.py` - Main changes
2. `src/spacetimedb_sdk/spacetime_websocket_client.py` - Verify db_identity support
3. `src/spacetimedb_sdk/protocol.py` - Reference for protocol constants (future task)
4. Various test files - Fix as needed after running tests

## Additional Context from Analysis
- The modern client (`modern_client.py`) already uses the correct protocol from `protocol.py`
- This suggests the legacy client was not updated when protocols changed
- The fix is straightforward but critical for unblocking users
