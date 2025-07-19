# Critical SpacetimeDB Python SDK Issues - Action Required

## Overview
This document outlines critical issues discovered during integration testing of the blackholio-python-client with SpacetimeDB servers. These issues are preventing proper data flow and blocking production use.

## Critical Issue: DatabaseUpdate Event Not Handled

### Problem Description
The SDK is receiving `DatabaseUpdate` and `IdentityToken` events from the server but has no registered handlers for them. This causes:
- No initial subscription data is received by clients
- Table queries return empty results despite data existing in the database
- The critical warning: `🚀 [EVENT] ⚠️ CRITICAL: No callbacks registered for important event 'DatabaseUpdate'!`

### Evidence
```
🚀 [EVENT] ⚠️ CRITICAL: No callbacks registered for important event 'IdentityToken'!
🚀 [EVENT] ⚠️ CRITICAL: No callbacks registered for important event 'DatabaseUpdate'!
Timeout waiting for subscription data after 5.0s
```

### Root Cause Analysis
1. The SDK's event system doesn't include `DatabaseUpdate` in the EventType enum
2. These events are being received at the WebSocket level but not propagated to clients
3. The `subscribe_to_events()` function cannot register handlers for unknown event types

### Required Fix
1. Add to `event_system.py`:
```python
class EventType(enum.Enum):
    # ... existing events ...
    
    # Add these critical events
    DATABASE_UPDATE = "database.update"
    IDENTITY_TOKEN = "identity.token"
    INITIAL_SUBSCRIPTION = "subscription.initial"
```

2. Update the WebSocket message handler to properly route these events
3. Ensure `DatabaseUpdate` events populate table caches with initial data

## Issue 2: Subscription Data Flow Not Working

### Problem Description
After connecting and subscribing to tables, no data flows to the client:
- `get_all_players()` returns empty list even after players join
- Subscription callbacks are never triggered
- Initial table state is never received

### Test Results
```
Table Access: ❌ Failed - "Could not access game tables or no data found"
Subscription Data Flow: ❌ Failed - "No subscription events received"
```

### Required Fix
The SDK needs to:
1. Handle the initial subscription response that contains current table state
2. Properly parse and route `DatabaseUpdate` messages to table caches
3. Trigger registered callbacks when subscription data arrives

## Issue 3: Event Registration System Limitations

### Problem Description
Clients cannot register handlers for events that aren't in the EventType enum, making it impossible to handle server events that the SDK doesn't know about.

### Attempted Workarounds That Failed
```python
# These don't work because EventType doesn't include DATABASE_UPDATE
for event_name in ['DatabaseUpdate', 'DATABASE_UPDATE', 'INITIAL_SUBSCRIPTION']:
    event_type = getattr(EventType, event_name, None)  # Returns None
    if event_type:
        subscribe_to_events(on_database_update, [event_type], ...)
```

### Required Fix
1. Add a way to register handlers for raw event names:
```python
def subscribe_to_raw_events(handler, event_names: List[str], subscription_id: str):
    """Subscribe to events by name without requiring EventType enum."""
    pass
```

2. Or make the event system more dynamic to handle unknown events

## Issue 4: Protocol Message Handling

### Problem Description
The BSATN protocol decoder may not be handling all message types correctly, particularly:
- Initial subscription responses
- Database state snapshots
- Identity token messages

### Required Investigation
1. Log all incoming WebSocket messages at the protocol level
2. Verify BSATN decoder handles all SpacetimeDB message types
3. Ensure message routing works for all protocol message types

## Testing Information

### Integration Test Command
```bash
./run-integration-test.sh --server ws://host.docker.internal:3000 --module blackholio
```

### Current Test Results
- Connection: ✅ PASSED (with BSATN protocol)
- Subscription Registration: ✅ PASSED
- Reducer Calls: ✅ PASSED  
- Table Access: ❌ FAILED (no data received)
- Subscription Data Flow: ❌ FAILED (no events received)

### Test Environment
- Server: Rust-based SpacetimeDB using BSATN protocol
- Client: blackholio-python-client using spacetimedb-python-sdk
- Issue occurs even when server has data and other clients can see it

## Recommended Priority Actions

1. **URGENT**: Add `DATABASE_UPDATE` and `IDENTITY_TOKEN` to EventType enum
2. **URGENT**: Implement handlers for these events in the WebSocket client
3. **HIGH**: Ensure DatabaseUpdate events populate table caches
4. **HIGH**: Add integration tests for subscription data flow
5. **MEDIUM**: Add raw event subscription capability for flexibility

## Code References

Key files to investigate:
- `src/spacetimedb_sdk/event_system.py` - Add new EventType values
- `src/spacetimedb_sdk/websocket_client.py` - Handle new message types
- `src/spacetimedb_sdk/modern_client.py` - Route events to client callbacks
- `src/spacetimedb_sdk/protocol.py` - Verify message parsing

## Success Criteria

The SDK changes are successful when:
1. No more "CRITICAL: No callbacks registered" warnings
2. `DatabaseUpdate` events are received and handled
3. Table queries return actual data after connection
4. Subscription callbacks fire when data changes
5. All 5 integration tests pass

## Additional Context

This issue is blocking production use of the SpacetimeDB Python SDK. The blackholio-python-client has implemented workarounds for other issues, but cannot work around the missing event handlers at the SDK level.

For questions or clarification, refer to the integration test output and the fixes already applied in the blackholio-python-client repository.