# SpaceTimeDB Python SDK - Tag 0x13 Fix Summary

## Problem
The SpaceTimeDB Python SDK was encoding ClientMessage types with an incorrect binary format that included the TAG_ENUM (0x13) prefix, causing the server to reject messages with the error:
```
unknown tag 0x13 for sum type ClientMessage
```

## Root Cause
In the BSATN protocol, when encoding top-level sum types (enums) that are part of the protocol itself (like ClientMessage), the variant index should be written directly as a 4-byte little-endian integer, WITHOUT the TAG_ENUM prefix.

The SDK was incorrectly using `writer.write_enum_header()` which:
1. First writes TAG_ENUM (0x13)
2. Then writes the variant index

This resulted in messages starting with `13 00 00 00 01 00 00 00...` instead of just `01 00 00 00...`

## Solution
Modified the `_encode_bsatn` method in `src/spacetimedb_sdk/protocol.py` to write the variant index directly for all ClientMessage types:

```python
# Before (incorrect):
writer.write_enum_header(1)  # This writes TAG_ENUM + variant

# After (correct):
writer._write_bytes(struct.pack('<I', 1))  # Write variant directly
```

## Files Changed
- `src/spacetimedb_sdk/protocol.py`: Updated `_encode_bsatn` method for all ClientMessage variants:
  - CallReducer (variant 0)
  - Subscribe (variant 1)
  - SubscribeSingleMessage (variant 2)
  - SubscribeMultiMessage (variant 3)
  - Unsubscribe (variant 4)
  - UnsubscribeMultiMessage (variant 5)
  - OneOffQuery (variant 6)
  - OneOffQueryMessage (variant 7)

## Testing
Created test scripts to verify the fix:
- `test_tag_0x13_fix.py`: Unit tests to verify correct encoding
- `test_tag_0x13_integration.py`: Integration test for server connection

## Impact
This fix allows the blackholio-python-client and other Python clients to successfully:
1. Connect to SpaceTimeDB servers using binary protocol
2. Send subscription requests without triggering "unknown tag" errors
3. Receive and process data from the server

## Backward Compatibility
This change only affects binary protocol encoding. JSON protocol encoding remains unchanged and continues to work as before.

## Verification
After applying this fix, binary messages now correctly start with the variant index:
- Subscribe messages: `01 00 00 00 ...` (variant 1)
- CallReducer messages: `00 00 00 00 ...` (variant 0)
- OneOffQuery messages: `06 00 00 00 ...` (variant 6)

Instead of the incorrect format with TAG_ENUM prefix:
- Previously: `13 00 00 00 01 00 00 00 ...` (TAG_ENUM + variant)