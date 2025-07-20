# AI Agent Task: Fix Blackholio AI Agent WebSocket "Invalid Close Frame" Errors

## 🎯 TASK OBJECTIVE

You are tasked with implementing a fix for the Blackholio AI Agent training system that is experiencing "Invalid close frame" WebSocket errors when processing large InitialSubscription messages (61KB+). The solution has been developed and tested, you need to apply it to their custom connection implementation.

## 🔍 PROBLEM SUMMARY

**Issue:** Blackholio AI Agent training fails with "Invalid close frame" WebSocket errors after receiving large InitialSubscription messages (61,108 bytes containing 600+ game entities).

**Root Cause:** The AI training system uses a custom WebSocket connection implementation in `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py` that bypasses the SpacetimeDB Python SDK's enhanced large message handling capabilities.

**Evidence:** The standard SpacetimeDB Python SDK (located at `/Users/punk1290/git/spacetimedb-python-sdk/`) works correctly and processes the same 61KB+ messages without errors.

## 📁 FILE LOCATIONS

### SpacetimeDB Python SDK Directory:
```
/Users/punk1290/git/spacetimedb-python-sdk/
```

### Key SDK Files (Reference Only):
- `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/protocol.py` - Contains working SQL conversion fixes
- `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/websocket_client.py` - Contains working large message handling
- `/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX.py` - The fix to apply

### AI Agent Files (Target for Implementation):
- `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py` - Custom connection that needs fixing

### Fix Files You Need to Use:
- `/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX.py` - Primary fix implementation
- `/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_AI_AGENT_DIAGNOSTIC_TOOL.py` - Diagnostic tool for verification

## 🔧 IMPLEMENTATION STEPS

### Step 1: Copy the Fix File
Copy `/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX.py` to the AI agent directory:
```bash
cp /Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX.py /Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/
```

### Step 2: Locate the Custom Connection File
Find and examine `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`

Look for:
- WebSocket creation (likely `websocket.WebSocketApp()` or similar)
- Message handling methods (`on_message`, `on_error`, `on_close`)
- Connection initialization

### Step 3: Apply the Fix
Modify `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`:

1. **Add import at the top:**
```python
from .BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX import fix_blackholio_websocket_connection
```

2. **Apply fix after WebSocket creation:**
Find where the WebSocket is created (usually in `__init__` method) and add the fix immediately after:
```python
# After WebSocket creation (e.g., self.ws = websocket.WebSocketApp(...))
fix_blackholio_websocket_connection(self)
```

### Step 4: Verify SQL Conversion
Ensure the custom connection has SQL conversion for table names. Look for subscription message creation and verify table names are converted to SQL format:

**Before (causes errors):**
```python
"query_strings": ["entity", "player", "circle"]  # Raw table names
```

**After (working):**
```python
"query_strings": ["SELECT * FROM entity", "SELECT * FROM player", "SELECT * FROM circle"]  # SQL format
```

If not present, add this conversion function to `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`:

```python
def fix_subscription_queries(queries):
    """Convert table names to SQL queries for latest SpacetimeDB compatibility."""
    def convert_table_name_to_sql(query: str) -> str:
        if query and ' ' not in query and not any(keyword in query.lower() for keyword in ['select', 'from', 'where', 'join']):
            return f"SELECT * FROM {query}"
        else:
            return query
    
    if isinstance(queries, str):
        return convert_table_name_to_sql(queries)
    elif isinstance(queries, list):
        return [convert_table_name_to_sql(query) for query in queries]
    else:
        return queries
```

And apply it before sending subscription messages:
```python
fixed_queries = fix_subscription_queries(["entity", "player", "circle", "food", "config"])
```

### Step 5: Test the Implementation
Run the diagnostic tool to verify the fix:
```bash
cd /Users/punk1290/git/blackholio-agent
python -c "
import sys
sys.path.append('/Users/punk1290/git/spacetimedb-python-sdk')
exec(open('/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_AI_AGENT_DIAGNOSTIC_TOOL.py').read())
"
```

### Step 6: Test AI Training
Test the AI training pipeline:
```bash
cd /Users/punk1290/git/blackholio-agent
python scripts/train_agent.py --total-timesteps 1000 --n-envs 1 --experiment-name websocket_fix_test --db-identity c200e3d53a455398d91ad688a39a38ca59a8ce0b79863cb9df78f2866c6d31dc
```

## ✅ SUCCESS CRITERIA

After implementing the fix, you should see:

### 1. No "Invalid Close Frame" Errors
The WebSocket connection should remain stable during large message processing.

### 2. Successful Large Message Processing
Look for logs indicating:
```
✅ Processing large message: 61,XXX bytes
✅ Large InitialSubscription: X tables, 61,XXX bytes
✅ Successfully processed large message: 61,XXX bytes
```

### 3. Stable AI Training
The training pipeline should:
- Connect successfully
- Receive identity
- Subscribe to tables without SQL parser errors
- Process large InitialSubscription without connection drops
- Spawn players successfully
- Continue training without timeouts

## 🚨 COMMON ISSUES TO WATCH FOR

### Import Errors
If you get import errors, ensure:
- The fix file is in the correct directory
- The import path is correct relative to the connection file
- Python path includes the necessary directories

### WebSocket Attribute Not Found
If `fix_blackholio_websocket_connection()` reports it can't find the WebSocket instance:
- Check the attribute name (might be `self.ws`, `self.websocket`, `self._ws`, etc.)
- Ensure you're calling the fix after WebSocket creation
- Verify the WebSocket object is properly initialized

### Still Getting SQL Parser Errors
If you still see "sql parser error: Expected an SQL statement, found: entity":
- Verify the SQL conversion is applied before sending subscription messages
- Check that table names are being converted to "SELECT * FROM tablename" format
- Ensure the conversion function is being called in the right place

## 📋 VERIFICATION CHECKLIST

Before completing the task, verify:

- [ ] Fix file copied to `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX.py`
- [ ] Import added to `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`
- [ ] `fix_blackholio_websocket_connection(self)` called after WebSocket creation
- [ ] SQL conversion function present and applied to subscription queries
- [ ] Diagnostic tool runs without errors
- [ ] AI training test completes successfully without "Invalid close frame" errors

## 🎯 EXPECTED OUTCOME

After successful implementation:
1. **WebSocket connections remain stable** during 61KB+ message processing
2. **No "Invalid close frame" errors** occur
3. **AI training pipeline works normally** with full access to game state data
4. **Connection logs show successful large message processing**

## 📞 TROUBLESHOOTING

If issues persist after implementation:
1. **Check file paths** - Ensure all file references use the correct absolute paths
2. **Verify WebSocket library versions** - Should match SDK test environment
3. **Enable debug logging** - Add logging to see detailed message processing
4. **Compare with working SDK** - Reference `/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/websocket_client.py` for working implementation

## 📄 REFERENCE DOCUMENTATION

Working examples can be found in:
- `/Users/punk1290/git/spacetimedb-python-sdk/test_large_message_websocket_fix.py` - Test that proves the fix works
- `/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_AI_AGENT_FINAL_SOLUTION_COMPREHENSIVE.md` - Complete technical documentation

This task should resolve the WebSocket "Invalid close frame" errors and restore full functionality to the Blackholio AI Agent training system.
