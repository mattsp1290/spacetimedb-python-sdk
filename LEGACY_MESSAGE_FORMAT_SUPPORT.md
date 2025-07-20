# Legacy Message Format Support

## Overview

The SpacetimeDB Python SDK now supports legacy message formats that use double-underscore prefixed keys (e.g., `__identity__`) in addition to the standard protocol format. This ensures compatibility with older SpacetimeDB servers that may still use the legacy format.

## Problem

Some SpacetimeDB servers send messages in a legacy format like:
```json
{
  "__identity__": "0xdeadbeef",
  "__token__": "auth-token-here",
  "__connection_id__": 123456789
}
```

However, the SDK was only expecting the standard protocol format:
```json
{
  "IdentityToken": {
    "identity": "0xdeadbeef",
    "token": "auth-token-here",
    "connection_id": "0x00000000000000000000000001E24015"
  }
}
```

This caused the error:
```
AttributeError: 'dict' object has no attribute 'identity'
```

## Solution

The `ProtocolDecoder` in `protocol.py` has been enhanced to handle both formats:

1. **Legacy Identity Format** (`__identity__`):
   - Converts hex string identities (with or without "0x" prefix)
   - Handles integer connection IDs by converting to 16-byte representation
   - Supports hex string connection IDs

2. **Legacy Initial Subscription Format** (`__initial_subscription__`):
   - Parses `__request_id__` and `__duration_nanos__`
   - Handles `__database_update__` with `__tables__`

3. **Legacy Transaction Update Format** (`__transaction_update__`):
   - Parses `__caller_identity__` and `__caller_connection_id__`
   - Handles `__status__`, `__timestamp__`, `__reducer_name__`, etc.

## Supported Legacy Formats

### Identity Token (Fully Supported)
```json
{
  "__identity__": "0xdeadbeef",
  "__token__": "token-string",
  "__connection_id__": 123456789  // or "0xhexstring"
}
```

### Initial Subscription (Partially Supported)
```json
{
  "__initial_subscription__": {
    "__request_id__": 123,
    "__duration_nanos__": 1000000,
    "__database_update__": {
      "__tables__": []
    }
  }
}
```

### Transaction Update (Partially Supported)
```json
{
  "__transaction_update__": {
    "__status__": "success",
    "__timestamp__": 1234567890,
    "__caller_identity__": "0xabcdef",
    "__caller_connection_id__": 987654321,
    "__reducer_name__": "my_reducer",
    "__reducer_id__": 42,
    "__request_id__": 123,
    "__energy_used__": 1000,
    "__duration_nanos__": 500000
  }
}
```

## Error Handling

For partially supported legacy formats, the SDK provides helpful error messages:
```
Partially supported legacy message format: ['__subscribe_applied__']. 
Please update your SpacetimeDB server to use the standard protocol format.
```

## Testing

Run the legacy format test to verify compatibility:
```bash
python test_legacy_message_format.py
```

## Migration Recommendation

While the SDK now supports legacy formats, we recommend updating your SpacetimeDB server to use the standard protocol format for better performance and full feature support. The legacy format support is intended as a compatibility layer during migration.

## Implementation Details

The key changes are in `src/spacetimedb_sdk/protocol.py`:

1. The `_decode_json` method first checks for legacy format keys before standard format
2. Hex string parsing handles the "0x" prefix appropriately
3. Integer connection IDs are converted to 16-byte representations
4. Error messages guide users when encountering unsupported legacy formats

This ensures backward compatibility while encouraging migration to the standard protocol.