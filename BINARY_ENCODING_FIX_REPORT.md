# SpaceTimeDB Python SDK Binary Encoding Fix Report

## Summary

After thorough investigation, the SpaceTimeDB Python SDK **already correctly implements binary encoding** and returns `bytes` from all encoding methods. The SDK properly sends binary WebSocket frames (opcode 0x2) when using the binary protocol.

## Key Findings

### 1. **BsatnWriter.get_bytes() - Already Returns Bytes**
- Location: `/src/spacetimedb_sdk/bsatn/writer.py:43-47`
- The method correctly returns `bytes` type
- No string conversion occurs

### 2. **Protocol Encoding Methods - All Return Bytes**
- `ProtocolEncoder.encode_client_message()` - Returns `bytes`
- `SpacetimeDBProtocolHelper.encode_subscription()` - Returns `bytes`
- `SpacetimeDBProtocolHelper.encode_reducer_call()` - Returns `bytes`
- All methods have proper type hints: `-> bytes`

### 3. **WebSocket Clients - Correctly Send Binary Frames**

#### Old Client (spacetime_websocket_client.py)
```python
def send(self, data):
    if self.protocol == "v1.bsatn.spacetimedb" and isinstance(data, bytes):
        from websocket import ABNF
        self.ws.send(data, opcode=ABNF.OPCODE_BINARY)
```

#### Modern Client (websocket_client.py)
```python
if self.use_binary:
    from websocket import ABNF
    self.ws.send(encoded_data, opcode=ABNF.OPCODE_BINARY)
```

## Test Results

All tests pass successfully:
- ✓ BsatnWriter.get_bytes() returns bytes
- ✓ ProtocolEncoder returns bytes for all message types
- ✓ SpacetimeDBProtocolHelper returns bytes
- ✓ WebSocket clients send binary frames (opcode 0x2) for binary protocol
- ✓ No string conversions in binary encoding path

## Conclusion

**No fixes are required.** The SDK already implements the requested functionality correctly:

1. All encoding methods return `bytes`, not `str`
2. Binary data is never converted to strings
3. WebSocket clients correctly use `ABNF.OPCODE_BINARY` for binary protocol
4. Type hints are properly set to `-> bytes`

If users are experiencing issues with text frames being sent instead of binary frames, the problem is likely due to:
1. Using the text protocol (`v1.json.spacetimedb`) instead of binary protocol (`v1.bsatn.spacetimedb`)
2. Not using the protocol helper classes correctly
3. A different version of the SDK being used

## Recommendations

For users experiencing binary frame issues:

1. **Ensure binary protocol is used:**
   ```python
   from spacetimedb_sdk.protocol import BIN_PROTOCOL
   client = WebSocketClient(protocol=BIN_PROTOCOL)
   ```

2. **Use the protocol helpers:**
   ```python
   from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper
   helper = SpacetimeDBProtocolHelper(use_binary=True)
   message = helper.encode_subscription(["table_name"])
   ```

3. **Verify the protocol in use:**
   ```python
   print(f"Protocol: {client.protocol}")  # Should be "v1.bsatn.spacetimedb"
   ```