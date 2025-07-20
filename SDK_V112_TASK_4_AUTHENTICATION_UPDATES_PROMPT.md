# Task: Authentication Updates for v1.1.2 (sdk-v112-4)

## Context

You are implementing authentication verification and updates for the SpacetimeDB Python SDK v1.1.2 migration. This is a **high priority, security critical** task that ensures authentication works correctly with v1.1.2 servers.

## Background from Previous Tasks

1. **Task 1 (Completed)**: Fixed WebSocket URL structure to `/v1/database/{name}/subscribe`
2. **Task 2 (Completed)**: Protocol headers already correct (v1.json.spacetimedb)
3. **Task 5 (Completed)**: Enhanced error handling for database publishing detection

## Current Situation

From the tasks yaml (`spacetimedb-sdk-v1.1.2-migration-tasks-updated.yaml`):

```yaml
- id: sdk-v112-4
  name: Authentication Updates
  status: needs-investigation
  description: Verify authentication works with v1.1.2 protocol
  updated_context:
    - "Auth handling in websocket_client.py and modern_client.py"
    - "Headers include spacetime-identity in responses"
    - "Need to verify token format compatibility"
  subtasks:
    - Verify current auth implementation:
        - Check if Authorization header format is correct
        - Test with actual auth tokens
        - Verify identity token parsing
    - Update if needed:
        - Handle new auth response formats
        - Update token refresh logic if changed
        - Ensure backward compatibility
  references:
    - websocket_client.py (auth header construction)
    - modern_client.py (auth token handling)
  verification: Authentication works with v1.1.2 servers
  priority: high (security critical)
```

## Task Objectives

### 1. Investigate Current Authentication Implementation

**Files to examine**:
- `src/spacetimedb_sdk/websocket_client.py` - Auth header construction
- `src/spacetimedb_sdk/modern_client.py` - Auth token handling
- `src/spacetimedb_sdk/protocol.py` - IdentityToken message handling
- `src/spacetimedb_sdk/connection_id.py` - Enhanced identity/token classes

**Key areas to investigate**:
- How auth tokens are formatted and sent in headers
- How identity tokens are received and parsed
- Whether there's token refresh logic
- How authentication errors are handled

### 2. Verify Authorization Header Format

**Current implementation to check**:
```python
# In websocket_client.py, around line ~175
if self.auth_token:
    token_bytes = f"token:{self.auth_token}".encode('utf-8')
    base64_str = base64.b64encode(token_bytes).decode('utf-8')
    headers["Authorization"] = f"Basic {base64_str}"
```

**Questions to answer**:
- Is the `Basic` auth scheme correct for v1.1.2?
- Is the `token:` prefix still required?
- Should we support Bearer tokens?

### 3. Test Identity Token Handling

**Server response headers to verify**:
- `spacetime-identity` - The identity assigned to the client
- `spacetime-identity-token` - The auth token for future connections

**Message handling to verify**:
- `IdentityToken` server message processing
- Enhanced identity/connection ID conversion
- Token storage and reuse

### 4. Create Comprehensive Authentication Tests

**Test scenarios needed**:
1. **Anonymous authentication** (no token provided)
2. **Token authentication** (valid token)
3. **Invalid token handling**
4. **Identity token reception and storage**
5. **Token reuse on reconnection**
6. **Authentication error handling**

### 5. Update if Necessary

Based on findings, potentially update:
- Authorization header construction
- Identity token parsing
- Error messages for auth failures
- Token refresh logic (if applicable)
- Documentation on authentication

## Implementation Strategy

### Phase 1: Investigation and Analysis
1. Trace through current auth flow in the code
2. Document current implementation details
3. Identify any v1.1.2 specific requirements
4. Check SpacetimeDB server source for auth expectations

### Phase 2: Verification Testing
1. Create test script for various auth scenarios
2. Test against actual v1.1.2 server (if available)
3. Use mocks for scenarios we can't test live
4. Verify backward compatibility

### Phase 3: Updates (if needed)
1. Update auth header format if required
2. Enhance identity token handling
3. Improve auth error messages
4. Add any missing auth features

### Phase 4: Documentation
1. Document auth flow for SDK users
2. Update API docs with auth examples
3. Add auth troubleshooting guide

## Success Criteria

1. **Correct Header Format**: Authorization headers work with v1.1.2 servers
2. **Identity Token Handling**: Properly receive and store identity tokens
3. **Error Handling**: Clear error messages for auth failures
4. **Test Coverage**: Comprehensive tests for all auth scenarios
5. **Documentation**: Clear docs on how to authenticate

## Key Questions to Answer

1. Does the current `Basic` auth with `token:` prefix work with v1.1.2?
2. Are there any new auth schemes we should support?
3. Is token refresh/rotation implemented or needed?
4. How should we handle auth state across reconnections?
5. Are there any breaking changes in auth between versions?

## References

- Current implementation: `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/`
- Tasks yaml: `/Users/punk1290/git/spacetimedb-python-sdk/spacetimedb-sdk-v1.1.2-migration-tasks-updated.yaml`
- Previous completions: Task 1, 2, and 5 summaries
- SpacetimeDB server source: `/Users/punk1290/git/SpacetimeDB/` (for auth implementation details)

## Testing Approach

Create `test_v112_authentication.py` with:
1. Unit tests for header construction
2. Integration tests with mock server responses
3. End-to-end tests if server available
4. Error scenario tests
5. Token reuse/persistence tests

## Potential Challenges

1. **Server Availability**: May need to mock server responses
2. **Token Generation**: Need valid tokens for testing
3. **Backward Compatibility**: Ensure we don't break existing auth
4. **Security**: Handle tokens securely in tests

## Definition of Done

- [ ] Current auth implementation investigated and documented
- [ ] Authorization header format verified to work with v1.1.2
- [ ] Identity token handling tested and working
- [ ] Comprehensive test suite created
- [ ] Any necessary updates implemented
- [ ] Documentation updated
- [ ] No regression in existing auth functionality

## Next Steps After This Task

1. Task 6: Testing and Validation - Integration tests with real databases
2. Task 3: Error Handling Updates - Though mostly addressed
3. Task 7: Documentation Updates - Include auth docs
