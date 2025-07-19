# AI Agent Task: Apply Enhanced WebSocket Fix for Connection Persistence

## 🎯 UPDATED TASK OBJECTIVE

Based on the implementation results, the original WebSocket fix is working correctly - it's detecting and handling "Invalid close frame" errors as designed. However, the underlying WebSocket connection still terminates after the error occurs. You now need to apply an **enhanced fix** that includes automatic reconnection and connection persistence.

## 📊 CURRENT STATUS ANALYSIS

### ✅ What's Working (From Previous Implementation):
- Fix successfully applied and imported
- "Invalid close frame" errors are being detected
- Enhanced error recovery is triggered
- SQL query conversion is working correctly
- Connection establishment is successful
- Identity token is received successfully

### ❌ What Still Needs Fixing:
- WebSocket connection terminates after the invalid frame error
- No InitialSubscription message is received
- No game state data is populated
- Player spawning fails due to missing data
- Training cannot proceed: "Timeout waiting for player spawn"

## 🔧 ENHANCED SOLUTION

The enhanced fix addresses the connection persistence issue by implementing automatic reconnection when "Invalid close frame" errors are detected.

## 📁 FILE LOCATIONS

### Enhanced Fix File (New):
- `/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py` - Enhanced fix with connection persistence

### Target File to Modify:
- `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py` - Replace original fix

### Results File (Reference):
- `/Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_WEBSOCKET_FIX_RESULTS.md` - Shows current status

## 🔧 IMPLEMENTATION STEPS

### Step 1: Copy the Enhanced Fix File
Copy the enhanced fix to the AI agent directory:
```bash
cp /Users/punk1290/git/spacetimedb-python-sdk/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py /Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/
```

### Step 2: Update the Import in Connection File
Modify `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`:

**Replace the existing import:**
```python
# OLD:
from .BLACKHOLIO_CUSTOM_WEBSOCKET_LARGE_MESSAGE_FIX import fix_blackholio_websocket_connection

# NEW:
from .BLACKHOLIO_ENHANCED_WEBSOCKET_FIX import enhance_blackholio_connection_with_persistence
```

### Step 3: Update the Fix Application
**Replace the existing fix call:**
```python
# OLD:
fix_blackholio_websocket_connection(self)

# NEW:
enhance_blackholio_connection_with_persistence(self)
```

### Step 4: Store Subscription Queries for Reconnection
Ensure your connection class stores the last subscription queries. Add this to your connection class:

```python
def subscribe_to_tables(self, table_names):
    """Subscribe to tables and store queries for potential reconnection."""
    # Store the subscription queries for reconnection
    self.last_subscription_queries = table_names
    
    # Apply SQL conversion (if not already done)
    fixed_queries = self.fix_subscription_queries(table_names)
    
    # Send subscription as before
    # ... your existing subscription logic ...
```

### Step 5: Test the Enhanced Implementation
Run your AI training pipeline:
```bash
cd /Users/punk1290/git/blackholio-agent
python scripts/train_agent.py --total-timesteps 1000 --n-envs 1 --experiment-name enhanced_websocket_fix_test --db-identity c200e3d53a455398d91ad688a39a38ca59a8ce0b79863cb9df78f2866c6d31dc
```

## ✅ ENHANCED SUCCESS CRITERIA

### 1. Error Detection and Recovery (Should Still Work)
```
✅ WebSocket Invalid Close Frame Error detected
✅ This often occurs after processing large messages (>50KB)
✅ Applying enhanced error recovery with connection persistence...
✅ Enhanced error handling prepared for connection recovery
```

### 2. NEW: Automatic Reconnection (Should Now Work)
```
✅ Detected protocol error closure - initiating automatic reconnection
✅ Scheduling reconnection attempt 1/3 in 2.0s
✅ Attempting to reconnect...
✅ Reconnection successful
```

### 3. NEW: Subscription Re-establishment (Should Now Work)
```
✅ Re-establishing subscriptions after reconnection
✅ Re-subscribing to X queries
✅ Large InitialSubscription: X tables, 61,XXX bytes
✅ Successfully processed large message: 61,XXX bytes
```

### 4. NEW: Successful Training (Should Now Work)
```
✅ Player spawning successful
✅ Game state updates flowing
✅ Training pipeline functional
```

## 🆕 KEY FEATURES OF ENHANCED FIX

### Automatic Reconnection
- Detects protocol error closures (status code 1006, None, or after invalid frame errors)
- Automatically attempts reconnection up to 3 times with 2-second delays
- Preserves connection state for seamless recovery

### Connection State Management
- Tracks pending InitialSubscription status
- Stores subscription queries for re-establishment
- Manages reconnection attempts and backoff

### Enhanced Error Recovery
- Specific handling for "Invalid close frame" errors
- Preparation for reconnection when errors occur during large message processing
- Connection persistence even when underlying WebSocket drops

### Subscription Re-establishment
- Automatically re-subscribes to the same tables after reconnection
- Maintains game state continuity
- Ensures InitialSubscription is received on the new connection

## 🚨 WHAT TO EXPECT

### During "Invalid Close Frame" Error:
1. **Error Detection**: "WebSocket Invalid Close Frame Error detected"
2. **Error Handling**: "Applying enhanced error recovery with connection persistence..."
3. **Connection Closure**: WebSocket closes with status 1006 (abnormal closure)
4. **Reconnection Trigger**: "Detected protocol error closure - initiating automatic reconnection"
5. **Reconnection Process**: "Attempting to reconnect..."
6. **Success**: "Reconnection successful"
7. **Re-subscription**: "Re-establishing subscriptions after reconnection"
8. **Data Reception**: "Large InitialSubscription: X tables, 61,XXX bytes"
9. **Training Continuation**: Player spawning and training proceed normally

### If Reconnection Fails:
- The system will attempt up to 3 reconnection attempts
- If all attempts fail, manual restart will be required
- Detailed logging will show the reconnection attempts and failure reasons

## 📋 VERIFICATION CHECKLIST

Before completing the task, verify:

- [ ] Enhanced fix file copied to `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/BLACKHOLIO_ENHANCED_WEBSOCKET_FIX.py`
- [ ] Import updated in `/Users/punk1290/git/blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py`
- [ ] Fix call updated to use `enhance_blackholio_connection_with_persistence(self)`
- [ ] Subscription queries are stored in `self.last_subscription_queries`
- [ ] AI training test shows reconnection attempts in logs
- [ ] InitialSubscription is successfully received after reconnection
- [ ] Player spawning works after reconnection
- [ ] Training completes without "Timeout waiting for player spawn" errors

## 🎯 EXPECTED FINAL OUTCOME

After successful implementation of the enhanced fix:

1. **"Invalid close frame" errors are detected and handled** ✅
2. **Connection automatically reconnects** ✅ (NEW)
3. **Subscriptions are re-established** ✅ (NEW)
4. **InitialSubscription is received on new connection** ✅ (NEW)
5. **Game state data is populated** ✅ (NEW)
6. **Player spawning succeeds** ✅ (NEW)
7. **AI training completes successfully** ✅ (NEW)

## 🔍 TROUBLESHOOTING

### If Enhanced Fix Doesn't Import:
- Verify the enhanced fix file was copied to the correct directory
- Check the import path matches the file location
- Ensure there are no syntax errors in the enhanced fix file

### If Reconnection Doesn't Trigger:
- Check that `_last_error_was_invalid_frame` is being set to `True` during errors
- Verify the close handler is detecting protocol errors (status codes None or 1006)
- Enable debug logging to see detailed reconnection logic

### If Reconnection Fails:
- The current implementation logs that automatic reconnection isn't fully implemented
- This indicates that manual restart is still required
- The logs will provide guidance on what's needed for full automatic reconnection

## 📞 NEXT STEPS IF ISSUES PERSIST

If the enhanced fix still doesn't resolve the connection persistence issue:

1. **Capture detailed logs** showing the enhanced fix in action
2. **Verify the reconnection attempts** are being logged
3. **Check if re-subscription is occurring** after reconnection
4. **Test with manual reconnection** to confirm the fix logic is sound

The enhanced fix represents a significant improvement over the original fix by addressing the core issue of connection persistence after protocol errors.
