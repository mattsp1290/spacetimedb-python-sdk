# AI Agent Instructions: Fix Blackholio WebSocket "Invalid Close Frame" Errors

## 🤖 TASK FOR AI AGENT

You are an AI agent tasked with implementing a WebSocket fix for the Blackholio AI Agent training system. The system experiences "Invalid close frame" errors when processing large InitialSubscription messages (61KB+), causing connection drops and training failures.

**PRIORITY:** HIGH - Training system is completely blocked until this is resolved.

## 📊 CURRENT SITUATION

### ✅ Previous Fix Status:
- Original fix was implemented and is working correctly
- "Invalid close frame" errors are being detected and handled
- SQL query conversion is working correctly
- Error recovery is triggered properly

### ❌ Remaining Issue:
- WebSocket connection still terminates after error handling
- InitialSubscription message is never received
- Player spawning fails due to missing game state
- Training times out with "Timeout waiting for player spawn"

## 📁 COMPLETE FILE REFERENCE

### Source Files (SpacetimeDB Python SDK):
```
/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py
/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX.py
/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_AI_AGENT_DIAGNOSTIC_TOOL.py
/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_WEBSOCKET_FIX_RESULTS.md
```

### Target Files (Blackholio AI Agent):
```
/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py
/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py (to be copied)
```

### Test Command:
```
cd /Users/punk1290/git/blackholio-agent
python scripts/train_agent.py --total-timesteps 1000 --n-envs 1 --experiment-name enhanced_websocket_fix_test --db-identity c200e3d53a455398d91ad688a39a38ca59a8ce0b79863cb9df78f2866c6d31dc
```

## 🔧 STEP-BY-STEP IMPLEMENTATION

### Step 1: Copy Enhanced Fix File
**Action:** Copy the enhanced WebSocket fix to the AI agent directory.

**Command:**
```bash
cp /Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py /Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/
```

**Verification:** Ensure the file exists at:
```
/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py
```

### Step 2: Read Current Connection Implementation
**Action:** Examine the current connection file to understand its structure.

**File to read:**
```
/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py
```

**Look for:**
- Existing import statement (likely `from .BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX import fix_blackholio_websocket_connection`)
- Existing fix application (likely `fix_blackholio_websocket_connection(self)`)
- WebSocket creation (likely `self.ws = websocket.WebSocketApp(...)`)
- Subscription methods

### Step 3: Update Import Statement
**Action:** Replace the existing import with the enhanced version.

**In file:** `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`

**Find this line:**
```python
from .BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX import fix_blackholio_websocket_connection
```

**Replace with:**
```python
from .BLACKHOLIO_ENHANCED_WEBSOCKET_FIX import enhance_blackholio_connection_with_persistence
```

### Step 4: Update Fix Application
**Action:** Replace the fix function call with the enhanced version.

**In file:** `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`

**Find this line (likely in `__init__` method):**
```python
fix_blackholio_websocket_connection(self)
```

**Replace with:**
```python
enhance_blackholio_connection_with_persistence(self)
```

### Step 5: Add Subscription Query Storage
**Action:** Ensure subscription queries are stored for reconnection.

**In file:** `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`

**Find the subscription method** (look for where subscription messages are sent) and add this line before sending:
```python
# Store subscription queries for potential reconnection
self.last_subscription_queries = table_names  # or whatever variable contains the table names
```

**Example integration:**
```python
def subscribe_to_tables(self, table_names):
    """Subscribe to game tables."""
    # Store for reconnection
    self.last_subscription_queries = table_names
    
    # Apply SQL conversion
    fixed_queries = self.fix_subscription_queries(table_names)
    
    # Send subscription message
    # ... existing subscription logic ...
```

### Step 6: Test Implementation
**Action:** Run the AI training pipeline to test the enhanced fix.

**Commands:**
```bash
cd /Users/punk1290/git/blackholio-agent
python scripts/train_agent.py --total-timesteps 1000 --n-envs 1 --experiment-name enhanced_websocket_fix_test --db-identity c200e3d53a455398d91ad688a39a38ca59a8ce0b79863cb9df78f2866c6d31dc
```

### Step 7: Verify Results
**Action:** Check logs for expected enhanced behavior.

**Expected Log Sequence:**
```
✅ Applied enhanced Blackholio WebSocket fix with connection persistence
✅ WebSocket Invalid Close Frame Error detected
✅ Applying enhanced error recovery with connection persistence...
✅ Detected protocol error closure - initiating automatic reconnection
✅ Scheduling reconnection attempt 1/3 in 2.0s
✅ Attempting to reconnect...
✅ Reconnection successful (or failure message)
✅ Re-establishing subscriptions after reconnection
✅ Large InitialSubscription: X tables, 61,XXX bytes
✅ Successfully processed large message: 61,XXX bytes
✅ Player spawning successful
```

## ✅ SUCCESS CRITERIA

### Primary Success Indicators:
1. **Enhanced fix applied successfully** - logs show "Applied enhanced Blackholio WebSocket fix with connection persistence"
2. **Error detection working** - "WebSocket Invalid Close Frame Error detected"
3. **Reconnection triggered** - "Detected protocol error closure - initiating automatic reconnection"
4. **Reconnection attempts logged** - "Scheduling reconnection attempt X/3"
5. **InitialSubscription received** - "Large InitialSubscription: X tables, 61,XXX bytes"
6. **Training proceeds** - No "Timeout waiting for player spawn" errors

### Training Success:
- Player spawning completes successfully
- Game state data is populated
- Training environment initializes properly
- No connection timeout errors

## 🚨 ERROR HANDLING

### If Import Error Occurs:
- Verify `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py` exists
- Check file permissions
- Verify Python syntax in the copied file

### If "Module not found" Error:
- Ensure the import path is correct relative to the connection file
- Check for typos in the import statement
- Verify the file was copied to the correct directory

### If Reconnection Doesn't Trigger:
- Verify the enhanced fix was applied (check for log message)
- Ensure `_last_error_was_invalid_frame` attribute is being set
- Check that close handler is detecting protocol error status codes

### If Reconnection Fails:
- The current implementation may log "Automatic reconnection not yet fully implemented"
- This indicates the reconnection framework is in place but needs connection-specific implementation
- Manual restart may still be required, but the framework is established

## 🔍 DIAGNOSTIC COMMANDS

### Check Enhanced Fix Application:
```bash
cd /Users/punk1290/git/blackholio-agent
python -c "
import sys
sys.path.append('src')
from blackholio_agent.environment.blackholio_connection_v112 import *
print('Enhanced fix imported successfully')
"
```

### Run Diagnostic Tool:
```bash
cd /Users/punk1290/git/blackholio-agent
python -c "
import sys
sys.path.append('/Users/punk1290/git/spacetimedb-python-sdk')
exec(open('/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_AI_AGENT_DIAGNOSTIC_TOOL.py').read())
"
```

## 📋 VERIFICATION CHECKLIST

**Before marking task complete, verify:**

- [ ] Enhanced fix file copied to `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py`
- [ ] Import statement updated in `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`
- [ ] Fix application updated to use `enhance_blackholio_connection_with_persistence(self)`
- [ ] Subscription queries stored in `self.last_subscription_queries`
- [ ] Test run executed: `python scripts/train_agent.py --total-timesteps 1000 --n-envs 1 --experiment-name enhanced_websocket_fix_test`
- [ ] Logs show enhanced fix application
- [ ] Logs show reconnection attempts (even if they fail)
- [ ] No "Timeout waiting for player spawn" errors
- [ ] Training proceeds beyond initial connection phase

## 🎯 EXPECTED FINAL OUTCOME

**After successful implementation:**

1. **Connection persistence implemented** - WebSocket connections survive "Invalid close frame" errors
2. **Automatic reconnection triggered** - System attempts to reconnect when protocol errors occur
3. **Enhanced error recovery** - Better handling of large message processing errors
4. **Training pipeline functional** - AI training can proceed without connection timeouts

**Note:** Even if automatic reconnection doesn't fully work in the first implementation, the enhanced framework will be in place and will provide much better error handling and recovery capabilities than the original fix.

## 📞 COMPLETION REPORTING

**When task is complete, report:**

1. **Files modified** with full paths
2. **Test results** - whether training proceeded further than before
3. **Log excerpts** showing enhanced fix behavior
4. **Any remaining issues** that need further attention
5. **Reconnection status** - whether automatic reconnection worked or needs additional implementation

**Success is measured by:** Training proceeding beyond the initial connection phase without "Timeout waiting for player spawn" errors, even if manual reconnection is still sometimes required.
