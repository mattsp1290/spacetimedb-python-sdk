# Blackholio Python Client Migration Guide
## SpacetimeDB SDK Protocol Helper Fixes Implementation

### Context and Problem Summary

The blackholio-python-client has been experiencing WebSocket connection failures with HTTP 400 errors due to missing WebSocket subprotocol headers. The root cause was a fundamental issue in the SpacetimeDB Python SDK where the `SpacetimeDBProtocolHelper` always returned `bytes` regardless of the `use_binary` parameter setting, causing WebSocket frame type mismatches.

**Core Issues Resolved:**
1. **Missing WebSocket Subprotocols**: Client was sending empty `subprotocols=[]` instead of required protocol headers
2. **Frame Type Mismatches**: JSON protocol was sending binary frames instead of text frames
3. **SDK Protocol Helper Bug**: Always returned bytes even when `use_binary=False` was set

**SpacetimeDB Requirements:**
- WebSocket connections MUST include `Sec-WebSocket-Protocol` header
- JSON protocol requires `v1.json.spacetimedb` subprotocol and TEXT frames
- Binary protocol requires `v1.bsatn.spacetimedb` subprotocol and BINARY frames

### Current State Analysis

**File: `/src/blackholio_client/connection/spacetimedb_connection.py`**

The connection file has been partially fixed but needs to leverage the new SDK improvements:

**Current Configuration (Lines 66-67):**
```python
# Initialize JSON protocol helper
self.protocol_helper = SpacetimeDBProtocolHelper(use_binary=False)
```

**Current WebSocket Connection (Lines 268-269, 353-354):**
```python
# Use JSON protocol - requires v1.json.spacetimedb subprotocol
subprotocols = ["v1.json.spacetimedb"]
```

**Current Message Handling Issue (Lines 480-485, 533-537):**
```python
# Current workaround - converts bytes to string manually
json_message = self._ensure_json_message(json_message, "encode_subscription")
await self.websocket.send(json_message)  # Sends as text frame
```

### Migration Tasks

#### Task 1: Remove Manual String Conversion Workarounds

**Problem:** The client currently includes `_ensure_json_message()` workaround that manually converts SDK bytes to strings.

**Solution:** With the fixed SDK, this conversion is no longer needed. The SDK now returns proper types based on protocol.

**Files to Update:**
- `/src/blackholio_client/connection/spacetimedb_connection.py`

**Changes:**

1. **Remove the `_ensure_json_message` method entirely** (Lines 442-469):
```python
# DELETE THIS ENTIRE METHOD - no longer needed
def _ensure_json_message(self, message: Union[bytes, str, Any], operation: str = "message") -> str:
    # ... entire method can be removed
```

2. **Simplify subscription request** (Lines 471-484):
```python
# BEFORE (with workaround):
async def _send_subscription_request(self):
    tables = ["entity", "player", "circle", "food", "config"]
    json_message = self.protocol_helper.encode_subscription(tables)
    json_message = self._ensure_json_message(json_message, "encode_subscription")
    await self.websocket.send(json_message)
    logger.info(f"Sent JSON subscription request ({len(json_message)} chars) - frame type: TEXT")

# AFTER (using fixed SDK):
async def _send_subscription_request(self):
    tables = ["entity", "player", "circle", "food", "config"]
    json_message = self.protocol_helper.encode_subscription(tables)
    # SDK now returns str for JSON protocol - send directly
    await self.websocket.send(json_message)
    logger.info(f"Sent JSON subscription request ({len(json_message)} chars) - frame type: TEXT")
```

3. **Simplify message sending** (Lines 486-554):
```python
# BEFORE (with complex conversion logic):
async def _send_message(self, message: Dict[str, Any], request_id: Optional[str] = None):
    # ... complex encoding logic with manual conversion ...
    message_text = self._ensure_json_message(message_bytes, f"encode_{message_type or 'message'}")
    await self.websocket.send(message_text)

# AFTER (direct SDK usage):
async def _send_message(self, message: Dict[str, Any], request_id: Optional[str] = None):
    if not self.websocket or self.state != ConnectionState.CONNECTED:
        raise BlackholioConnectionError("Not connected to SpacetimeDB")
    
    try:
        if request_id:
            message['request_id'] = request_id
            future = asyncio.get_event_loop().create_future()
            self._pending_requests[request_id] = future
        else:
            future = None
        
        # Use SDK methods directly - they return correct types
        message_type = message.get('type', '')
        
        if message_type == 'heartbeat':
            import json
            message_data = json.dumps(message)
        elif 'reducer' in message:
            reducer_name = message.get('reducer', '')
            args = message.get('args', {})
            message_data = self.protocol_helper.encode_reducer_call(reducer_name, args)
        elif 'query' in message:
            query = message.get('query', '')
            message_data = self.protocol_helper.encode_one_off_query(query)
        else:
            import json
            message_data = json.dumps(message)
        
        # SDK returns correct type - send directly
        await self.websocket.send(message_data)
        logger.debug(f"Sent {message_type or 'message'} ({len(str(message_data))} chars)")
        
        # Update statistics
        self._messages_sent += 1
        self._bytes_sent += len(str(message_data).encode('utf-8'))
        
        return future
        
    except Exception as e:
        if request_id and request_id in self._pending_requests:
            del self._pending_requests[request_id]
        logger.error(f"Failed to send message: {e}")
        raise SpacetimeDBError(f"Failed to send message: {e}")
```

#### Task 2: Update BlackholioClient Methods

**File: `/src/blackholio_client/connection/spacetimedb_connection.py`**

**Lines 946-971 and 973-1003:**

```python
# BEFORE (with manual conversion):
async def enter_game(self, player_name: str) -> bool:
    try:
        binary_message = self.connection.protocol_helper.encode_reducer_call(
            "enter_game", 
            {"player_name": player_name}
        )
        json_message = self.connection._ensure_json_message(binary_message, "encode_reducer_call(enter_game)")
        await self.connection.websocket.send(json_message)
        logger.info(f"Sent enter_game reducer as text frame ({len(json_message)} chars) for player: {player_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to enter game: {e}")
        return False

# AFTER (direct SDK usage):
async def enter_game(self, player_name: str) -> bool:
    try:
        # SDK returns string for JSON protocol
        message = self.connection.protocol_helper.encode_reducer_call(
            "enter_game", 
            {"player_name": player_name}
        )
        await self.connection.websocket.send(message)
        logger.info(f"Sent enter_game reducer as text frame ({len(message)} chars) for player: {player_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to enter game: {e}")
        return False

async def update_player_input(self, direction: Vector2) -> bool:
    try:
        # SDK returns string for JSON protocol
        message = self.connection.protocol_helper.encode_reducer_call(
            "update_input", 
            {
                "direction": {
                    "x": direction.x,
                    "y": direction.y
                }
            }
        )
        await self.connection.websocket.send(message)
        logger.debug(f"Sent update_input reducer as text frame ({len(message)} chars)")
        return True
    except Exception as e:
        logger.error(f"Failed to update player input: {e}")
        return False
```

#### Task 3: Add Protocol Validation (Optional Enhancement)

Add validation to ensure protocol consistency:

```python
# Add to SpacetimeDBConnection.__init__ method after line 67:
def __init__(self, config: ServerConfig):
    # ... existing initialization ...
    
    # Initialize JSON protocol helper
    self.protocol_helper = SpacetimeDBProtocolHelper(use_binary=False)
    
    # Validate protocol consistency
    try:
        self.protocol_helper.validate_protocol_consistency()
        expected_frame_type = self.protocol_helper.get_expected_frame_type()
        logger.info(f"Protocol validation passed - using {expected_frame_type} frames")
    except ValueError as e:
        logger.error(f"Protocol configuration error: {e}")
        raise BlackholioConnectionError(f"Protocol configuration error: {e}")
```

#### Task 4: Update Comments and Documentation

Remove outdated comments that reference the old workarounds:

1. **Line 268**: Update comment
```python
# BEFORE:
# Use JSON protocol - requires v1.json.spacetimedb subprotocol

# AFTER:
# Use JSON protocol with proper subprotocol - SDK now returns strings for TEXT frames
```

2. **Remove references to binary protocol in JSON mode**:
```python
# REMOVE comments like:
# "Use binary protocol based on message type"
# "Ensure we have string for text frame transmission"
# "Binary protocol may not support heartbeat"
```

3. **Update method docstrings**:
```python
def encode_reducer_call(self, reducer_name: str, args: Dict[str, Any]) -> str:
    """
    Encode a reducer call using JSON protocol.
    
    Args:
        reducer_name: Name of the reducer to call
        args: Arguments for the reducer
        
    Returns:
        JSON string ready for WebSocket text frame transmission
    """
```

#### Task 5: Simplify Message Handling Logic

**Lines 606-646** - Message handler can be simplified:

```python
# BEFORE (complex frame type handling):
async def _message_handler(self):
    try:
        async for message in self.websocket:
            try:
                self._messages_received += 1
                
                if isinstance(message, bytes):
                    self._bytes_received += len(message)
                    logger.debug(f"Received BINARY frame ({len(message)} bytes) - parsing with binary protocol")
                    data = await self._handle_binary_message(message)
                elif isinstance(message, str):
                    self._bytes_received += len(message.encode('utf-8'))
                    logger.warning(f"Received TEXT frame with binary protocol - this may indicate protocol mismatch")
                    data = json.loads(message)
                else:
                    logger.warning(f"Unknown message type: {type(message)}")
                    continue
                
                if data:
                    await self._process_message(data)

# AFTER (simplified for JSON protocol):
async def _message_handler(self):
    try:
        async for message in self.websocket:
            try:
                self._messages_received += 1
                
                if isinstance(message, str):
                    # Expected for JSON protocol
                    self._bytes_received += len(message.encode('utf-8'))
                    logger.debug(f"Received TEXT frame ({len(message)} chars) - parsing as JSON")
                    data = json.loads(message)
                elif isinstance(message, bytes):
                    # Unexpected for JSON protocol
                    self._bytes_received += len(message)
                    logger.warning(f"Received BINARY frame with JSON protocol - attempting to decode as UTF-8")
                    try:
                        text = message.decode('utf-8')
                        data = json.loads(text)
                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        logger.error(f"Failed to decode binary message: {e}")
                        continue
                else:
                    logger.warning(f"Unknown message type: {type(message)}")
                    continue
                
                if data:
                    await self._process_message(data)
```

### Testing Migration

#### Test 1: Verify Protocol Helper Return Types

```python
# Create test to verify SDK fixes work
def test_protocol_helper_types():
    helper = SpacetimeDBProtocolHelper(use_binary=False)
    
    # Test subscription returns string
    subscription = helper.encode_subscription(["test_table"])
    assert isinstance(subscription, str), f"Expected str, got {type(subscription)}"
    
    # Test reducer call returns string
    reducer_call = helper.encode_reducer_call("test_reducer", {"arg": "value"})
    assert isinstance(reducer_call, str), f"Expected str, got {type(reducer_call)}"
    
    print("✅ Protocol helper types are correct")
```

#### Test 2: Verify WebSocket Connection

```python
# Test that connection works without manual conversions
async def test_simplified_connection():
    config = EnvironmentConfig(
        server_language='rust',
        server_ip='localhost',
        server_port=3000,
        server_use_ssl=False,
        spacetime_db_identity='blackholio'
    )
    
    connection = SpacetimeDBConnection(config)
    
    try:
        success = await connection.connect()
        if success:
            print("✅ Connection successful with simplified code")
            
            # Test sending message directly
            helper = SpacetimeDBProtocolHelper(use_binary=False)
            message = helper.encode_subscription(["test"])
            await connection.websocket.send(message)
            print("✅ Message sent without conversion")
            
        await connection.disconnect()
        return success
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
```

### Expected Outcomes

After implementing this migration:

1. **Simplified Code**: Remove ~100 lines of workaround code
2. **Better Performance**: Eliminate unnecessary string conversions
3. **Improved Reliability**: Use SDK as intended without manual frame type handling
4. **Better Maintainability**: Code follows SDK patterns and is easier to understand
5. **Protocol Compliance**: Proper WebSocket frame types for JSON protocol

### Files Modified Summary

**Primary File:**
- `/src/blackholio_client/connection/spacetimedb_connection.py`

**Key Changes:**
1. Remove `_ensure_json_message()` method (Lines 442-469)
2. Simplify `_send_subscription_request()` (Lines 471-484)
3. Simplify `_send_message()` (Lines 486-554)
4. Update `enter_game()` and `update_player_input()` in BlackholioClient (Lines 946-1003)
5. Simplify message handler frame type logic (Lines 606-646)
6. Add optional protocol validation
7. Update comments and documentation

### Migration Verification

1. **Run existing tests** to ensure no regressions
2. **Verify WebSocket connection** succeeds without HTTP 400 errors
3. **Check frame types** match protocol (TEXT for JSON, BINARY for binary)
4. **Test reducer calls** work without manual conversions
5. **Monitor logs** for protocol mismatch warnings (should be eliminated)

### Backwards Compatibility

This migration maintains full backwards compatibility:
- Existing API interfaces unchanged
- Same configuration options
- Same functionality
- Only internal implementation simplified

The migration leverages the fixed SpacetimeDB Python SDK to eliminate workarounds and provide clean, maintainable code that follows WebSocket standards properly.