# WebSocket Binary Frame Fix for SpaceTimeDB Python SDK

## Issue Summary

The sister team discovered that the SpaceTimeDB Python SDK was sending binary data as **text WebSocket frames** instead of **binary WebSocket frames**, causing server errors.

### Error Details
- **Server Error**: `Client caused error on text message: data too short for [u8]: Expected 2037540213, given 152`
- **Root Cause**: Binary BSATN protocol messages were being sent with WebSocket text frame opcode (0x1) instead of binary frame opcode (0x2)

## Solution Implemented

### Changes Made

1. **ModernWebSocketClient** (`src/spacetimedb_sdk/websocket_client.py:408-417`)
   - Added explicit binary frame opcode when sending messages with binary protocol
   - Before: `self.ws.send(encoded_data)`
   - After: `self.ws.send(encoded_data, opcode=ABNF.OPCODE_BINARY)` when `use_binary=True`

2. **Legacy WebSocketClient** (`src/spacetimedb_sdk/spacetime_websocket_client.py:112-119`)
   - Added binary frame detection based on protocol type
   - Before: `self.ws.send(data)`
   - After: `self.ws.send(data, opcode=ABNF.OPCODE_BINARY)` when protocol is `v1.bsatn.spacetimedb`

### Technical Details

WebSocket frames have two main data opcodes:
- **0x1 (OPCODE_TEXT)**: For UTF-8 text data
- **0x2 (OPCODE_BINARY)**: For binary data

The Python `websocket-client` library was not automatically detecting that bytes should be sent as binary frames, so we now explicitly specify the opcode.

## Verification

The fix was verified by:
1. Confirming protocol helpers return `bytes` objects
2. Checking that both WebSocket clients now use explicit binary opcodes
3. Creating tests to demonstrate the correct frame type usage

## Impact

This fix resolves:
- Server-side "data too short" errors when receiving binary messages
- Client-side "undecodable binary message" warnings
- WebSocket connection closures with error code 1011 (internal error)

## Testing

Run the verification script to confirm the fix:
```bash
python test_websocket_opcode_verification.py
```

This will verify that:
- Both WebSocket clients explicitly send binary frames
- Protocol helpers return the correct data types
- The frame type issue is resolved