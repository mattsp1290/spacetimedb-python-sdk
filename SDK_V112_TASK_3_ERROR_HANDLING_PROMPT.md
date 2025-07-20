# Task: Error Handling Updates for v1.1.2 (sdk-v112-3)

## Context

You are implementing error handling improvements for the SpacetimeDB Python SDK v1.1.2 migration. The WebSocket URL structure has been fixed (Task 1) and the protocols are already correct (Task 2). However, users are experiencing confusing 404 errors when databases aren't published, and the SDK needs better error handling for v1.1.2-specific scenarios.

## Current Situation

1. **Completed Work**:
   - URL format fixed: `/v1/database/{name}/subscribe` 
   - Protocols correct: `v1.json.spacetimedb` and `v1.bsatn.spacetimedb`
   - Legacy `spacetimedb_client.py` removed, using `modern_client.py`

2. **Current Problems**:
   - 404 errors when connecting to unpublished databases are confusing
   - No clear guidance on how to fix connection issues
   - Error messages don't differentiate between different failure scenarios
   - No pre-flight checks to validate database availability

3. **Test Results Show**:
   ```
   ERROR: Handshake status 404 Not Found
   spacetime-identity: c200... [long hex string]
   spacetime-identity-token: eyJ0... [JWT token]
   ```
   - Server returns identity headers even on 404
   - No helpful error message about database status

## Task Objectives

### 1. Enhance WebSocket Error Handling
**Files**: `src/spacetimedb_sdk/websocket_client.py`, `src/spacetimedb_sdk/spacetime_websocket_client.py`

- Parse WebSocket handshake errors more intelligently
- Detect 404 errors and provide specific guidance
- Extract and use server-provided headers for diagnostics
- Differentiate between:
  - Database not found (never created)
  - Database not published (exists but not accessible)
  - Protocol mismatch errors
  - Authentication failures

### 2. Improve Error Messages in Modern Client
**File**: `src/spacetimedb_sdk/modern_client.py`

- Catch connection errors and provide actionable guidance
- Add error context with suggested fixes:
  ```python
  # Example improved error message:
  SpacetimeDBConnectionError: Failed to connect to database 'blackholio'
  
  Status: 404 Not Found
  Possible causes:
  1. Database not published. Run: spacetime publish blackholio --clear-database
  2. Database name incorrect. Check: spacetime list
  3. Server not running on localhost:3000
  
  Debug info:
  - URL: ws://localhost:3000/v1/database/blackholio/subscribe
  - Protocol: v1.json.spacetimedb
  - Server provided identity: c200...
  ```

### 3. Add Pre-Connection Validation
**New functionality in**: `src/spacetimedb_sdk/modern_client.py`

- Optional pre-flight check before WebSocket connection
- Try HTTP endpoint to verify database exists
- Detect if server is running
- Check server version if possible

### 4. Create Connection Diagnostics Helper
**New file**: `src/spacetimedb_sdk/connection_diagnostics.py`

```python
class ConnectionDiagnostics:
    """Helper class to diagnose connection issues"""
    
    def check_server_available(self, host: str) -> bool:
        """Check if SpacetimeDB server is responding"""
    
    def check_database_exists(self, host: str, database: str) -> bool:
        """Check if database exists (may need to be published)"""
    
    def get_server_version(self, host: str) -> Optional[str]:
        """Try to detect server version"""
    
    def diagnose_connection_error(self, error: Exception, url: str) -> str:
        """Return helpful diagnostic message for connection error"""
```

## Implementation Steps

### Step 1: Update WebSocket Error Handling

1. In `websocket_client.py`, enhance `_on_ws_error` method:
   - Parse handshake status codes
   - Extract server headers from error
   - Create structured error information

2. In `spacetime_websocket_client.py`, update `on_error` handling:
   - Similar enhancements for the basic client
   - Ensure consistency between both implementations

### Step 2: Create Custom Exception Classes

Create `src/spacetimedb_sdk/exceptions.py`:
```python
class SpacetimeDBError(Exception):
    """Base exception for SpacetimeDB SDK"""

class DatabaseNotFoundError(SpacetimeDBError):
    """Database doesn't exist or isn't published"""
    
class ProtocolMismatchError(SpacetimeDBError):
    """Server rejected the protocol"""
    
class ServerNotAvailableError(SpacetimeDBError):
    """Cannot reach SpacetimeDB server"""
```

### Step 3: Enhance Modern Client Error Handling

Update `modern_client.py`:
- Wrap connection errors in custom exceptions
- Add diagnostic information to errors
- Provide actionable error messages
- Optional pre-connection validation

### Step 4: Create Diagnostic Tools

Implement `connection_diagnostics.py`:
- Server availability checks
- Database existence verification
- Version detection
- Comprehensive error diagnosis

### Step 5: Update Tests

Create `test_v112_error_handling.py`:
- Test each error scenario
- Verify error messages are helpful
- Test diagnostic tools
- Ensure backwards compatibility

## Success Criteria

1. **Clear Error Messages**: Users immediately understand why connection failed
2. **Actionable Guidance**: Error messages include specific commands to fix issues
3. **Diagnostic Tools**: Helper functions to troubleshoot connection issues
4. **No Breaking Changes**: Existing error handling still works
5. **Test Coverage**: All error scenarios have tests

## Example Usage After Implementation

```python
from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.exceptions import DatabaseNotFoundError

try:
    client = SpacetimeDBClient.connect(
        host="localhost:3000",
        database="my_game",
        auth_token=None,
        ssl_enabled=False
    )
except DatabaseNotFoundError as e:
    print(e)  # Clear message with spacetime publish command
    print(e.diagnostic_info)  # Additional debugging details
except Exception as e:
    # Use diagnostics for unknown errors
    from spacetimedb_sdk.connection_diagnostics import ConnectionDiagnostics
    diag = ConnectionDiagnostics()
    print(diag.diagnose_connection_error(e, "ws://localhost:3000/..."))
```

## Files to Create/Modify

1. **Create**: `src/spacetimedb_sdk/exceptions.py`
2. **Create**: `src/spacetimedb_sdk/connection_diagnostics.py` 
3. **Modify**: `src/spacetimedb_sdk/websocket_client.py`
4. **Modify**: `src/spacetimedb_sdk/spacetime_websocket_client.py`
5. **Modify**: `src/spacetimedb_sdk/modern_client.py`
6. **Create**: `test_v112_error_handling.py`

## References

- Updated tasks yaml: `/Users/punk1290/git/spacetimedb-python-sdk/spacetimedb-sdk-v1.1.2-migration-tasks-updated.yaml`
- Current test results showing 404 errors: See test output in task 1 completion
- Server response headers contain identity tokens even on error

## Notes

- The server provides `spacetime-identity` and `spacetime-identity-token` headers even on 404 errors
- This suggests the server is running and responding, just the database isn't available
- Focus on user experience - developers should immediately understand what went wrong
- Consider rate limiting diagnostic checks to avoid hammering the server

## Next Steps After This Task

1. Task 4: Authentication Updates - Verify auth works correctly
2. Task 5: Database Publishing Detection - Build on this error handling
3. Task 6: Complete testing with published databases
