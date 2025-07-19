# Task: WebSocket URL Structure Update (sdk-v112-1)

## Context

You are implementing the first critical task from the SpacetimeDB Python SDK v1.1.2 migration plan. The full task list is in `/Users/punk1290/git/spacetimedb-python-sdk/spacetimedb-sdk-v1.1.2-migration-tasks.yaml`.

## Current Situation

1. **Server Version**: SpacetimeDB v1.1.2 is running on localhost:3000
2. **Current SDK State**: 
   - Uses protocol `v1.text.spacetimedb` which is rejected by v1.1.2
   - Has partial db_identity support in WebSocketClient
   - URL format needs verification (could be `/v1/database/` or `/v1/ws/database/`)
3. **No Backward Compatibility Needed**: Only supporting v1.1.x going forward

## Task Objectives

### 1. Determine Correct URL Format
**First Priority**: Test which URL format v1.1.2 actually uses:
- Option A: `ws://host:port/v1/database/{name}/subscribe?db_identity={identity}`
- Option B: `ws://host:port/v1/ws/database/{name}/subscribe?db_identity={identity}`

Create a test script to verify the correct endpoint format.

### 2. Review Current db_identity Implementation
Examine the existing implementation in `spacetime_websocket_client.py`:
```python
def connect(self, auth, host, name_or_address, ssl_enabled, db_identity=None):
    # Current implementation already has db_identity parameter
    if db_identity:
        url = f"{protocol}://{host}/v1/database/{db_identity}/subscribe"
    else:
        url = f"{protocol}://{host}/v1/database/{name_or_address}/subscribe"
```

Determine if this needs any enhancements or if it's sufficient.

### 3. Update WebSocket URL Construction

Based on findings from steps 1 and 2:
- Update URL construction in `spacetime_websocket_client.py`
- Ensure db_identity is properly passed as query parameter (not in path)
- Handle URL encoding for special characters
- Remove any legacy URL format code since we're only supporting v1.1.x

### 4. Update SpacetimeDBClient Interface

Modify `spacetimedb_client.py`:
- Ensure db_identity parameter flows through from SpacetimeDBClient.init()
- Update any documentation strings
- Remove legacy connection code

## Implementation Steps

1. **Create URL format test script**:
   ```python
   # test_v112_url_formats.py
   # Test both /v1/database/ and /v1/ws/database/ formats
   # Try with different protocols (v1.json.spacetimedb, v1.text.spacetimedb)
   # Test with and without db_identity parameter
   ```

2. **Based on test results, update WebSocketClient**:
   - Fix URL construction
   - Ensure db_identity is a query parameter
   - Clean up any legacy code

3. **Update SpacetimeDBClient**:
   - Pass db_identity through connection chain
   - Update method signatures
   - Update docstrings

4. **Verify the changes**:
   - Test connection to blackholio database
   - Ensure proper URL format is used
   - Verify db_identity is correctly included

## Success Criteria

- [ ] Correct v1.1.2 URL format identified and implemented
- [ ] db_identity properly passed as query parameter
- [ ] Connection succeeds with v1.1.2 server
- [ ] No legacy URL formats remain in code
- [ ] All connection parameters properly flow through the SDK

## Files to Modify

1. `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/spacetime_websocket_client.py`
2. `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/spacetimedb_client.py`

## Testing Approach

1. Create comprehensive URL format test
2. Test against running SpacetimeDB v1.1.2 instance
3. Verify blackholio database connection works
4. Document findings for future reference

## Notes

- The MIGRATION_GUIDE mentions `/v1/ws/` but our tests showed `/v1/` works
- Need to determine which is correct for v1.1.2
- Current SDK already has db_identity support but uses it incorrectly (in path instead of query param)
- Focus only on v1.1.x compatibility, no legacy support needed

## References

- Migration Guide: `/Users/punk1290/git/spacetimedb-python-sdk/MIGRATION_GUIDE_v1.1.2.md`
- Current Issues: `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/V1_1_2_COMPATIBILITY_CHANGES.md`
- Test Results: `/Users/punk1290/git/blackholio-agent/test_spacetimedb_endpoints.py`
