# Task: Database Publishing Detection for v1.1.2 (sdk-v112-5)

## Context

You are implementing database publishing detection for the SpacetimeDB Python SDK v1.1.2 migration. This task builds directly on the error handling foundation created in Task 3. The main pain point is that users get confusing 404 errors when trying to connect to databases that exist but aren't published, and they need clear guidance on how to fix this.

## Background from Previous Tasks

1. **Task 1 (Completed)**: Fixed WebSocket URL structure to `/v1/database/{name}/subscribe`
2. **Task 3 (Completed)**: Created comprehensive error handling with:
   - Custom exception hierarchy (including `DatabaseNotFoundError`)
   - Connection diagnostics utility with pre-flight checks
   - Enhanced WebSocket error parsing
   - Clear, actionable error messages

## Current Situation

From the tasks yaml (`spacetimedb-sdk-v1.1.2-migration-tasks-updated.yaml`):

```yaml
- id: sdk-v112-5
  name: Database Publishing Detection
  status: NEW (discovered need)
  description: Detect and handle unpublished databases gracefully
  context:
    - "Current implementation returns 404 for unpublished databases"
    - "Users need clear guidance to publish first"
    - "Should provide helpful error messages"
  subtasks:
    - Add pre-connection checks:
        - Try to detect if database exists
        - Check if database is published
        - Provide clear error messages
    - Improve error messages:
        - "Database not found: Did you publish it? Run: spacetime publish {name}"
        - Include link to documentation
        - Suggest troubleshooting steps
  priority: high (user experience)
```

## Task Objectives

### 1. Enhance Database Detection in ConnectionDiagnostics
**File**: `src/spacetimedb_sdk/connection_diagnostics.py`

- Improve `check_database_exists()` to differentiate between:
  - Database doesn't exist at all
  - Database exists but not published
  - Database exists and is published
- Add new method `check_database_published()` if needed
- Try multiple endpoints to gather database status information

### 2. Create Database Status Detection Logic
**New functionality in**: `src/spacetimedb_sdk/connection_diagnostics.py`

- Check HTTP endpoints that might reveal database status:
  - `/v1/database/{name}/info` (might return different errors)
  - `/v1/databases` (list endpoint if available)
  - `/health` or `/status` endpoints that might list databases
- Parse different error responses to determine actual state
- Cache results to avoid repeated checks

### 3. Enhance DatabaseNotFoundError
**File**: `src/spacetimedb_sdk/exceptions.py`

- Add `is_unpublished` property based on detection
- Customize error message based on whether database is unpublished vs non-existent:
  ```
  Database 'mydb' exists but is not published.
  To publish your database, run:
    spacetime publish mydb --clear-database
  
  Or if you're developing locally:
    spacetime publish mydb --local
  ```

### 4. Integrate Publishing Detection into Pre-flight Checks
**Files**: `src/spacetimedb_sdk/connection_diagnostics.py`, `src/spacetimedb_sdk/websocket_client.py`

- Update `run_preflight_checks()` to use enhanced detection
- Provide different error messages for different scenarios
- Add option to skip publishing check if user knows database is published

### 5. Add Publishing Helper Methods
**New methods in**: `src/spacetimedb_sdk/modern_client.py`

```python
def check_database_status(self, database_name: str) -> Dict[str, Any]:
    """Check if a database exists and is published."""
    
def wait_for_database_published(self, database_name: str, timeout: float = 30.0) -> bool:
    """Wait for a database to become published (useful after running spacetime publish)."""
```

## Implementation Strategy

### Phase 1: Research Database Status Detection
1. Test various HTTP endpoints to see what information is available
2. Analyze different error responses (404 vs 403 vs 500)
3. Check if server provides any headers or response body with status info
4. Document findings for reliable detection methods

### Phase 2: Implement Detection Logic
1. Enhance `check_database_exists()` with multi-endpoint checking
2. Add logic to differentiate unpublished vs non-existent
3. Create helper methods for status detection
4. Add caching to avoid repeated checks

### Phase 3: Improve Error Messages
1. Update `DatabaseNotFoundError` to handle unpublished case
2. Add specific guidance for common scenarios:
   - Local development (use --local flag)
   - First-time setup (use --clear-database)
   - Production deployment
3. Include links to documentation

### Phase 4: Integration and Testing
1. Update pre-flight checks to use new detection
2. Add integration with `modern_client.py`
3. Create helper methods for common workflows
4. Test with various database states

## Success Criteria

1. **Clear Differentiation**: Users immediately know if their database is unpublished vs non-existent
2. **Actionable Guidance**: Error messages include the exact `spacetime publish` command to run
3. **Improved Workflow**: Helper methods make it easy to check status and wait for publishing
4. **No False Positives**: Detection is reliable and doesn't incorrectly identify database state
5. **Performance**: Detection adds minimal overhead to connection time

## Test Scenarios

1. **Unpublished Database**: Create a database but don't publish it, verify correct error
2. **Non-existent Database**: Try to connect to a database that was never created
3. **Published Database**: Verify no false warnings for properly published databases
4. **Publishing Workflow**: Test the wait_for_database_published helper
5. **Error Message Clarity**: Ensure all scenarios have clear, actionable messages

## Example Usage After Implementation

```python
from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.exceptions import DatabaseNotFoundError

# Scenario 1: Clear error for unpublished database
try:
    client = SpacetimeDBClient.connect(
        host="localhost:3000",
        database_address="my_game"
    )
except DatabaseNotFoundError as e:
    print(e)
    # Output:
    # Database 'my_game' exists but is not published.
    # To publish your database, run:
    #   spacetime publish my_game --clear-database
    #
    # For local development, use:
    #   spacetime publish my_game --local

# Scenario 2: Check status before connecting
client = SpacetimeDBClient(test_mode=True)
status = client.check_database_status("my_game")
print(f"Database exists: {status['exists']}")
print(f"Database published: {status['published']}")

# Scenario 3: Wait for publishing to complete
if not status['published']:
    print("Publishing database...")
    # User runs: spacetime publish my_game
    if client.wait_for_database_published("my_game", timeout=30):
        print("Database is now published!")
        client.connect(host="localhost:3000", database_address="my_game")
```

## Files to Create/Modify

1. **Enhance**: `src/spacetimedb_sdk/connection_diagnostics.py` (detection logic)
2. **Update**: `src/spacetimedb_sdk/exceptions.py` (better error messages)
3. **Enhance**: `src/spacetimedb_sdk/modern_client.py` (helper methods)
4. **Create**: `test_v112_database_publishing_detection.py` (comprehensive tests)

## References

- Current diagnostics: `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/connection_diagnostics.py`
- Current exceptions: `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/exceptions.py`
- Tasks yaml: `/Users/punk1290/git/spacetimedb-python-sdk/spacetimedb-sdk-v1.1.2-migration-tasks-updated.yaml`
- Previous test results showing 404 errors: Task 1 completion summary

## Key Challenges

1. **Detection Reliability**: Need to find reliable ways to detect unpublished vs non-existent
2. **Server Variations**: Different SpacetimeDB versions might respond differently
3. **Performance**: Don't want to slow down connections with too many checks
4. **False Positives**: Must not incorrectly identify a published database as unpublished

## Definition of Done

- [ ] Reliable detection of unpublished vs non-existent databases
- [ ] Clear, actionable error messages with exact commands to run
- [ ] Helper methods for checking status and waiting for publishing
- [ ] Comprehensive test coverage of all scenarios
- [ ] Documentation updated with new functionality
- [ ] No performance regression in connection time

## Next Steps After This Task

1. Task 4: Authentication Updates - With better error handling for auth issues
2. Task 6: Complete testing with published databases
3. Task 7: Documentation updates including publishing workflow
