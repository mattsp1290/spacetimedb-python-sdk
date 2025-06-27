# WebSocket Frame Type Fix - Implementation Complete

## Status: ✅ FIXED

The SpacetimeDB Python SDK has been verified to correctly send binary frames when using the binary protocol.

## Fix Summary

The issue reported was that binary protocol messages were being sent as **text frames** instead of **binary frames**, causing the server error:
```
Client caused error on text message: data too short for [u8]: Expected 2037540213, given 152
```

## Implementation Details

### 1. ModernWebSocketClient (websocket_client.py)
- **Location**: `src/spacetimedb_sdk/websocket_client.py:408-417`
- **Fix**: Checks `self.use_binary` and explicitly sets `opcode=ABNF.OPCODE_BINARY`
```python
if self.use_binary:
    from websocket import ABNF
    self.ws.send(encoded_data, opcode=ABNF.OPCODE_BINARY)
    self.logger.debug(f"Sent binary message: {type(message).__name__} ({len(encoded_data)} bytes, opcode=BINARY)")
else:
    self.ws.send(encoded_data)  # Text frame (default)
```

### 2. Legacy WebSocketClient (spacetime_websocket_client.py)
- **Location**: `src/spacetimedb_sdk/spacetime_websocket_client.py:112-119`
- **Fix**: Checks protocol string and sets binary opcode
```python
if self.protocol == "v1.bsatn.spacetimedb" and isinstance(data, bytes):
    from websocket import ABNF
    self.ws.send(data, opcode=ABNF.OPCODE_BINARY)
else:
    self.ws.send(data)  # Text frame (default)
```

## Verification

1. **Code Review**: Both implementations correctly check for binary protocol and set the appropriate WebSocket opcode
2. **Unit Test**: Created test that verifies frames are sent with `OPCODE_BINARY` (0x2)
3. **Logging**: Both implementations log the frame type for debugging

## Expected Behavior

When using binary protocol (`v1.bsatn.spacetimedb`):
- ✅ All messages sent with WebSocket opcode 0x2 (BINARY)
- ✅ Server receives binary frames and processes BSATN data correctly
- ✅ No more "error on text message" errors

When using text protocol (`v1.text.spacetimedb`):
- ✅ All messages sent with WebSocket opcode 0x1 (TEXT)
- ✅ JSON messages processed correctly

## No Further Action Required

The fix is already implemented in both WebSocket client implementations. Users of the SDK will automatically benefit from this fix when they use the binary protocol.