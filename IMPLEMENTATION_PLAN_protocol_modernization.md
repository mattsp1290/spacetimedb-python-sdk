# Implementation Plan: Protocol Modernization (task-3) and BSATN Support (task-4)

## Current State Analysis

### Already Implemented:
1. **Modern Message Types** (partially):
   - ✅ SubscribeSingle, SubscribeMulti, UnsubscribeMulti (in messages/subscribe.py)
   - ✅ OneOffQuery (in messages/one_off_query.py)
   - ✅ CallReducerFlags (proper implementation)
   - ✅ QueryId system
   - ✅ Enhanced connection management (EnhancedConnectionId, EnhancedIdentity)
   - ✅ EnergyQuanta with tracking

2. **BSATN Module** (basic implementation exists):
   - ✅ BsatnWriter with primitive types
   - ✅ BsatnReader 
   - ✅ Basic tags and constants
   - ❌ Missing: Complex type serialization (Product, Sum, Array, Map)
   - ❌ Missing: Integration with protocol messages

### Task-3: Protocol Modernization - What's Needed

1. **Complete Message Type Updates**:
   - ✅ Already have modern subscribe messages
   - ❌ Need to verify TransactionUpdateLight handling
   - ❌ Need to ensure all v1.1.1 message variants are supported
   - ❌ Need proper BSATN encoding/decoding for messages

2. **Protocol Encoder/Decoder Enhancement**:
   - Current ProtocolEncoder has JSON support but incomplete BSATN
   - Need to implement full BSATN encoding for all client messages
   - Need to implement full BSATN decoding for all server messages

3. **WebSocket Client Integration**:
   - Ensure BIN_PROTOCOL is fully supported
   - Add proper compression tag handling
   - Verify message serialization/deserialization

### Task-4: BSATN Protocol Support - What's Needed

1. **Complex Type Support**:
   - Product types (structs) - partially implemented
   - Sum types (enums/unions) - basic support
   - Arrays (fixed-size) - header support exists
   - Maps - not implemented
   - Optional types - basic support exists
   - Nested structures - needs testing

2. **SpacetimeDB-Specific Types**:
   - Identity (256-bit)
   - Address (128-bit) 
   - ConnectionId (128-bit)
   - Timestamp (i64 microseconds)
   - TimeDuration (i64 nanoseconds)

3. **Integration Features**:
   - Serialize/deserialize protocol messages
   - Handle table row encoding/decoding
   - Support for compressed messages
   - Efficient memory usage

## Implementation Steps

### Phase 1: Complete Protocol Message Types (task-3 part 1)
1. Review all message types in SpacetimeDB reference
2. Update protocol.py with any missing message variants
3. Ensure proper dataclass definitions match Rust types
4. Add validation and type checking

### Phase 2: BSATN Complex Types (task-4 part 1)
1. Implement Map type support in BsatnWriter/Reader
2. Enhance Product type handling with field names
3. Complete Sum type implementation
4. Add comprehensive tests for complex types

### Phase 3: Protocol BSATN Integration (task-3 + task-4)
1. Update ProtocolEncoder._encode_bsatn() for all client messages
2. Update ProtocolDecoder._decode_bsatn() for all server messages
3. Add proper type serialization for:
   - CallReducer args
   - ReducerCallInfo args
   - TableUpdate row data
   - QueryUpdate inserts/deletes

### Phase 4: WebSocket Integration
1. Update websocket_client.py for full BIN_PROTOCOL support
2. Add compression integration (already have compression module)
3. Test with real SpacetimeDB server
4. Performance optimization

### Phase 5: Testing & Documentation
1. Unit tests for all BSATN types
2. Integration tests for protocol messages
3. Performance benchmarks
4. Update documentation

## Next Steps
1. Start with completing BSATN complex type support
2. Then integrate with protocol messages
3. Finally update WebSocket client 