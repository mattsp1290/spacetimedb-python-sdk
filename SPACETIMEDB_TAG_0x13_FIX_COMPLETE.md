# SpaceTimeDB Python SDK - Binary Protocol Tag 0x13 Fix

## Executive Summary

The SpaceTimeDB Python SDK has been successfully patched to fix the "unknown tag 0x13 for sum type ClientMessage" error that was preventing the blackholio-python-client from communicating with SpaceTimeDB servers using the binary BSATN protocol.

## Problem Description

### Error Message
```
unknown tag 0x13 for sum type ClientMessage
```

### Root Cause
The SDK was incorrectly encoding ClientMessage enum variants by prefixing them with TAG_ENUM (0x13). In the SpaceTimeDB binary protocol, top-level protocol message types (like ClientMessage) should have their variant index written directly as a 4-byte little-endian integer, without any type tag prefix.

### Impact
- WebSocket connections would establish successfully
- Binary subscription messages would be rejected immediately
- Clients would enter infinite reconnection loops
- No data could be received from SpaceTimeDB servers

## Technical Details

### Incorrect Encoding (Before Fix)
```
Subscribe message: 13 00 00 00 01 00 00 00 ...
                   ^^ TAG_ENUM  ^^ variant 1
```

### Correct Encoding (After Fix)
```
Subscribe message: 01 00 00 00 ...
                   ^^ variant 1 (no TAG_ENUM prefix)
```

### Why This Matters
The SpaceTimeDB server's BSATN decoder expects ClientMessage variants to be "untagged" at the top level because the message type is already known from the protocol context. The TAG_ENUM (0x13) is only used for enum fields within structs, not for top-level protocol messages.

## Implementation Details

### File Modified
`/Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/protocol.py`

### Changes Made
In the `ProtocolEncoder._encode_bsatn()` method, replaced all instances of:
```python
writer.write_enum_header(variant_index)
```

With:
```python
writer._write_bytes(struct.pack('<I', variant_index))
```

### Affected Message Types
All ClientMessage variants were updated:
- `CallReducer` (variant 0)
- `Subscribe` (variant 1)
- `SubscribeSingleMessage` (variant 2)
- `SubscribeMultiMessage` (variant 3)
- `Unsubscribe` (variant 4)
- `UnsubscribeMultiMessage` (variant 5)
- `OneOffQuery` (variant 6)
- `OneOffQueryMessage` (variant 7)

## How to Apply This Fix to blackholio-agent

### Option 1: Update SpaceTimeDB SDK
If the blackholio-agent uses the SpaceTimeDB SDK as a dependency:
```bash
cd /Users/punk1290/git/blackholio-agent
pip install --upgrade /Users/punk1290/git/spacetimedb-python-sdk
```

### Option 2: Direct File Copy
If the SDK is vendored or copied:
```bash
cp /Users/punk1290/git/spacetimedb-python-sdk/src/spacetimedb_sdk/protocol.py \
   /Users/punk1290/git/blackholio-agent/path/to/spacetimedb_sdk/protocol.py
```

### Option 3: Manual Patch
If you need to apply the fix manually, search for `write_enum_header` in your protocol encoding code and replace it with direct binary writes for ClientMessage encoding.

## Verification Steps

### 1. Unit Test
Run the provided test to verify encoding:
```bash
python /Users/punk1290/git/spacetimedb-python-sdk/test_tag_0x13_fix.py
```

Expected output:
```
✅ All tests passed! The tag 0x13 issue has been fixed.
```

### 2. Integration Test
Test with a real SpaceTimeDB server:
```bash
python /Users/punk1290/git/spacetimedb-python-sdk/test_tag_0x13_integration.py
```

### 3. Manual Verification
Check that binary messages start with the correct bytes:
- Subscribe: `01 00 00 00 ...`
- CallReducer: `00 00 00 00 ...`
- OneOffQuery: `06 00 00 00 ...`

## Usage Example

```python
from spacetimedb_sdk.protocol_helpers import SpacetimeDBProtocolHelper

# Create helper with binary mode
helper = SpacetimeDBProtocolHelper(use_binary=True)

# Create subscription message (will now work correctly)
tables = ["entity", "player", "circle", "food", "config"]
binary_msg = helper.encode_subscription(tables)

# Send via WebSocket
await websocket.send(binary_msg)
# No more "unknown tag 0x13" error!
```

## Important Notes

1. **Binary Protocol Only**: This fix only affects binary BSATN encoding. JSON protocol continues to work as before.

2. **Backward Compatibility**: This change maintains compatibility with the SpaceTimeDB v1.1.2 protocol specification.

3. **Server Versions**: Tested with SpaceTimeDB server v1.1.2. Should work with any server expecting standard BSATN encoding.

4. **Performance**: The fix has no performance impact - it actually reduces message size by 4 bytes per message.

## Troubleshooting

If you still see tag 0x13 errors after applying this fix:

1. **Verify the fix is applied**: Check that your `protocol.py` uses `writer._write_bytes()` instead of `writer.write_enum_header()`

2. **Check dependencies**: Ensure you're not loading an old version of the SDK from elsewhere

3. **Clear caches**: Remove any `__pycache__` directories and `.pyc` files

4. **Verify binary mode**: Ensure you're using `SpacetimeDBProtocolHelper(use_binary=True)`

## Additional Resources

- Test scripts: `/Users/punk1290/git/spacetimedb-python-sdk/test_tag_0x13_*.py`
- Fix summary: `/Users/punk1290/git/spacetimedb-python-sdk/TAG_0x13_FIX_SUMMARY.md`
- Original issue: `/Users/punk1290/git/blackholio-agent/SPACETIMEDB_SDK_PROTOCOL_TAG_0x13_FIX_REQUEST.md`

## Success Criteria Met

✅ Client can send subscription requests without triggering "unknown tag" errors  
✅ Client can successfully subscribe to tables and receive data  
✅ All message types (subscribe, reducer calls, etc.) work with binary protocol  
✅ Clear documentation of the fix provided

---

*Fix implemented on 2025-06-25 in the spacetimedb-python-sdk repository*