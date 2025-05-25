"""
BSATN Protocol Integration Example for SpacetimeDB Python SDK.

This example demonstrates:
- Binary protocol (BSATN) vs JSON protocol comparison
- WebSocket client with binary protocol support
- Message encoding/decoding with BSATN
- Performance characteristics
- Protocol negotiation
"""

import asyncio
import time
import json
from typing import Dict, Any, List

from spacetimedb_sdk import (
    # Modern client with protocol support
    ModernWebSocketClient,
    
    # Protocol constants
    TEXT_PROTOCOL,
    BIN_PROTOCOL,
    
    # Protocol messages
    CallReducer,
    CallReducerFlags,
    Subscribe,
    SubscribeSingleMessage,
    SubscribeMultiMessage,
    UnsubscribeMultiMessage,
    OneOffQueryMessage,
    QueryId,
    
    # BSATN
    BsatnWriter,
    BsatnReader,
    SpacetimeDBIdentity,
    SpacetimeDBAddress,
    SpacetimeDBConnectionId,
    SpacetimeDBTimestamp,
    SpacetimeDBTimeDuration,
    
    # Protocol encoding
    ProtocolEncoder,
    ProtocolDecoder,
    
    # Logging
    get_logger,
)


# Initialize logger
logger = get_logger(__name__)


def demonstrate_bsatn_serialization():
    """Demonstrate BSATN serialization of various types."""
    print("=== BSATN Serialization Demo ===\n")
    
    # 1. Primitive types
    print("1. Primitive Types:")
    writer = BsatnWriter()
    
    # Write various primitives
    writer.write_bool(True)
    writer.write_u32(42)
    writer.write_string("Hello, SpacetimeDB!")
    writer.write_f64(3.14159)
    
    data = writer.get_bytes()
    print(f"   Serialized {len(data)} bytes")
    
    # Read them back
    reader = BsatnReader(data)
    assert reader.read_tag() == 0x02  # TAG_BOOL_TRUE
    assert reader.read_bool(0x02) == True
    assert reader.read_tag() == 0x07  # TAG_U32
    assert reader.read_u32() == 42
    assert reader.read_tag() == 0x0D  # TAG_STRING
    assert reader.read_string() == "Hello, SpacetimeDB!"
    assert reader.read_tag() == 0x0C  # TAG_F64
    assert abs(reader.read_f64() - 3.14159) < 0.00001
    print("   ✓ Primitives serialized and deserialized correctly\n")
    
    # 2. SpacetimeDB types
    print("2. SpacetimeDB Types:")
    
    # Identity (256-bit)
    identity = SpacetimeDBIdentity.from_hex("a" * 64)
    writer = BsatnWriter()
    identity.write_bsatn(writer)
    print(f"   Identity: {identity.to_hex()[:16]}...")
    
    # ConnectionId (128-bit)
    conn_id = SpacetimeDBConnectionId.from_u64_pair(0x1234567890ABCDEF, 0xFEDCBA0987654321)
    writer = BsatnWriter()
    conn_id.write_bsatn(writer)
    print(f"   ConnectionId: {conn_id.to_hex()[:16]}...")
    
    # Timestamp
    timestamp = SpacetimeDBTimestamp.now()
    writer = BsatnWriter()
    timestamp.write_bsatn(writer)
    print(f"   Timestamp: {timestamp.micros_since_epoch}")
    
    # Duration
    duration = SpacetimeDBTimeDuration(micros=3600 * 1000000)  # 1 hour in microseconds
    writer = BsatnWriter()
    duration.write_bsatn(writer)
    print(f"   Duration: {duration.micros} microseconds")
    print("   ✓ SpacetimeDB types serialized successfully\n")


def demonstrate_protocol_comparison():
    """Compare JSON vs BSATN protocol encoding."""
    print("=== Protocol Comparison Demo ===\n")
    
    # Create a complex message
    message = SubscribeMultiMessage(
        query_strings=[
            "SELECT * FROM users WHERE active = true AND last_login > NOW() - INTERVAL '30 days'",
            "SELECT * FROM messages WHERE user_id = 123 AND created_at > NOW() - INTERVAL '1 day'",
            "SELECT * FROM notifications WHERE user_id = 123 AND read = false"
        ],
        request_id=12345,
        query_id=QueryId(67890)
    )
    
    # Encode with both protocols
    json_encoder = ProtocolEncoder(use_binary=False)
    binary_encoder = ProtocolEncoder(use_binary=True)
    
    json_encoded = json_encoder.encode_client_message(message)
    binary_encoded = binary_encoder.encode_client_message(message)
    
    print("Message Encoding Comparison:")
    print(f"   JSON size: {len(json_encoded)} bytes")
    print(f"   BSATN size: {len(binary_encoded)} bytes")
    print(f"   Size reduction: {((len(json_encoded) - len(binary_encoded)) / len(json_encoded) * 100):.1f}%")
    
    # Show readability
    print(f"\nJSON (first 100 chars): {json_encoded.decode('utf-8')[:100]}...")
    print(f"BSATN (first 20 bytes): {binary_encoded[:20]}")
    
    # Performance comparison
    print("\nEncoding Performance:")
    
    # JSON encoding performance
    start_time = time.time()
    for _ in range(1000):
        json_encoder.encode_client_message(message)
    json_time = time.time() - start_time
    
    # BSATN encoding performance
    start_time = time.time()
    for _ in range(1000):
        binary_encoder.encode_client_message(message)
    binary_time = time.time() - start_time
    
    print(f"   JSON: {json_time:.3f}s for 1000 encodings ({json_time*1000:.2f}ms per encoding)")
    print(f"   BSATN: {binary_time:.3f}s for 1000 encodings ({binary_time*1000:.2f}ms per encoding)")
    print(f"   Performance improvement: {((json_time - binary_time) / json_time * 100):.1f}%")
    print()


def demonstrate_websocket_client_protocols():
    """Demonstrate WebSocket client with different protocols."""
    print("=== WebSocket Client Protocol Demo ===\n")
    
    # Create clients with different protocols
    json_client = ModernWebSocketClient(
        protocol=TEXT_PROTOCOL,
        auto_reconnect=False
    )
    
    binary_client = ModernWebSocketClient(
        protocol=BIN_PROTOCOL,
        auto_reconnect=False
    )
    
    print("Client Configuration:")
    print(f"   JSON Client Protocol: {json_client.protocol}")
    print(f"   JSON Client Binary Mode: {json_client.use_binary}")
    print(f"   Binary Client Protocol: {binary_client.protocol}")
    print(f"   Binary Client Binary Mode: {binary_client.use_binary}")
    print()
    
    # Test message encoding with both clients
    message = CallReducer(
        reducer="create_user",
        args=b'{"name": "Alice", "email": "alice@example.com", "age": 25}',
        request_id=1,
        flags=CallReducerFlags.FULL_UPDATE
    )
    
    json_encoded = json_client.encoder.encode_client_message(message)
    binary_encoded = binary_client.encoder.encode_client_message(message)
    
    print("Message Encoding Results:")
    print(f"   JSON encoded size: {len(json_encoded)} bytes")
    print(f"   BSATN encoded size: {len(binary_encoded)} bytes")
    print(f"   Formats are different: {json_encoded != binary_encoded}")
    
    # Show that JSON is human-readable
    json_str = json_encoded.decode('utf-8')
    print(f"   JSON contains 'CallReducer': {'CallReducer' in json_str}")
    print(f"   JSON contains 'create_user': {'create_user' in json_str}")
    
    print("   ✓ Protocol selection working correctly\n")


class BsatnGameClient:
    """Example game client using BSATN protocol for performance."""
    
    def __init__(self, use_binary: bool = True):
        self.use_binary = use_binary
        protocol = BIN_PROTOCOL if use_binary else TEXT_PROTOCOL
        
        self.client = ModernWebSocketClient(
            protocol=protocol,
            auto_reconnect=True,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
            on_error=self._on_error,
            on_message=self._on_message
        )
        
        self.connected = False
        self.player_id = None
        self.active_subscriptions = {}
        
        print(f"Game client initialized with {protocol} protocol")
    
    def _on_connect(self):
        """Handle connection established."""
        self.connected = True
        print("✓ Connected to game server")
        
        # Subscribe to game events
        self._subscribe_to_game_events()
    
    def _on_disconnect(self, reason: str):
        """Handle disconnection."""
        self.connected = False
        print(f"✗ Disconnected from game server: {reason}")
    
    def _on_error(self, error: Exception):
        """Handle connection error."""
        print(f"✗ Connection error: {error}")
    
    def _on_message(self, message):
        """Handle incoming server message."""
        print(f"📨 Received message: {type(message).__name__}")
        # In a real game, this would handle various message types
    
    def _subscribe_to_game_events(self):
        """Subscribe to relevant game events."""
        if not self.connected:
            return
        
        # Subscribe to player updates
        query_id = self.client.subscribe_single(
            "SELECT * FROM players WHERE online = true"
        )
        self.active_subscriptions["players"] = query_id
        print("📡 Subscribed to player updates")
        
        # Subscribe to game world events
        query_id = self.client.subscribe_single(
            "SELECT * FROM world_events WHERE timestamp > NOW() - INTERVAL '1 hour'"
        )
        self.active_subscriptions["world_events"] = query_id
        print("📡 Subscribed to world events")
    
    def create_player(self, name: str, character_class: str):
        """Create a new player character."""
        if not self.connected:
            print("✗ Not connected to server")
            return
        
        args = json.dumps({
            "name": name,
            "character_class": character_class,
            "starting_location": "town_square"
        }).encode('utf-8')
        
        request_id = self.client.call_reducer(
            "create_player",
            args,
            CallReducerFlags.FULL_UPDATE
        )
        
        print(f"🎮 Creating player '{name}' (class: {character_class})")
        return request_id
    
    def move_player(self, x: float, y: float, z: float):
        """Move player to new position."""
        if not self.connected:
            print("✗ Not connected to server")
            return
        
        args = json.dumps({
            "player_id": self.player_id,
            "position": {"x": x, "y": y, "z": z},
            "timestamp": time.time()
        }).encode('utf-8')
        
        request_id = self.client.call_reducer(
            "move_player",
            args,
            CallReducerFlags.NO_SUCCESS_NOTIFY  # High-frequency updates
        )
        
        return request_id
    
    def send_chat_message(self, message: str, channel: str = "global"):
        """Send a chat message."""
        if not self.connected:
            print("✗ Not connected to server")
            return
        
        args = json.dumps({
            "player_id": self.player_id,
            "message": message,
            "channel": channel,
            "timestamp": time.time()
        }).encode('utf-8')
        
        request_id = self.client.call_reducer(
            "send_chat_message",
            args,
            CallReducerFlags.FULL_UPDATE
        )
        
        print(f"💬 Sent chat message to {channel}: {message}")
        return request_id
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information including protocol details."""
        return {
            "connected": self.connected,
            "protocol": self.client.protocol,
            "binary_mode": self.use_binary,
            "active_subscriptions": len(self.active_subscriptions),
            "compression_info": self.client.get_compression_info()
        }


def demonstrate_game_client():
    """Demonstrate game client with BSATN protocol."""
    print("=== Game Client Demo ===\n")
    
    # Create game clients with different protocols
    binary_client = BsatnGameClient(use_binary=True)
    json_client = BsatnGameClient(use_binary=False)
    
    print("\nClient Comparison:")
    binary_info = binary_client.get_connection_info()
    json_info = json_client.get_connection_info()
    
    print("Binary Client:")
    for key, value in binary_info.items():
        if key != "compression_info":
            print(f"   {key}: {value}")
    
    print("JSON Client:")
    for key, value in json_info.items():
        if key != "compression_info":
            print(f"   {key}: {value}")
    
    # Simulate game operations (without actual connection)
    print("\nSimulated Game Operations:")
    
    # These would work with a real server connection
    print("Operations that would be performed:")
    print("1. Create player with optimized binary encoding")
    print("2. Subscribe to real-time game events")
    print("3. Send high-frequency position updates")
    print("4. Handle chat messages efficiently")
    print("5. Benefit from BSATN compression for large payloads")
    
    # Show encoding efficiency for game messages
    print("\nGame Message Encoding Efficiency:")
    
    # High-frequency position update
    position_args = json.dumps({
        "player_id": "player_123",
        "position": {"x": 123.45, "y": 67.89, "z": 10.0},
        "velocity": {"x": 1.2, "y": 0.0, "z": 0.5},
        "rotation": {"yaw": 45.0, "pitch": 0.0, "roll": 0.0},
        "timestamp": time.time()
    }).encode('utf-8')
    
    move_message = CallReducer(
        reducer="update_player_position",
        args=position_args,
        request_id=1,
        flags=CallReducerFlags.NO_SUCCESS_NOTIFY
    )
    
    json_encoder = ProtocolEncoder(use_binary=False)
    binary_encoder = ProtocolEncoder(use_binary=True)
    
    json_encoded = json_encoder.encode_client_message(move_message)
    binary_encoded = binary_encoder.encode_client_message(move_message)
    
    print(f"   Position update - JSON: {len(json_encoded)} bytes")
    print(f"   Position update - BSATN: {len(binary_encoded)} bytes")
    print(f"   Bandwidth savings: {((len(json_encoded) - len(binary_encoded)) / len(json_encoded) * 100):.1f}%")
    
    # For a game sending 60 position updates per second
    updates_per_second = 60
    json_bandwidth = len(json_encoded) * updates_per_second
    binary_bandwidth = len(binary_encoded) * updates_per_second
    
    print(f"\nBandwidth Usage (60 FPS):")
    print(f"   JSON: {json_bandwidth:,} bytes/sec ({json_bandwidth/1024:.1f} KB/s)")
    print(f"   BSATN: {binary_bandwidth:,} bytes/sec ({binary_bandwidth/1024:.1f} KB/s)")
    print(f"   Savings: {json_bandwidth - binary_bandwidth:,} bytes/sec ({(json_bandwidth - binary_bandwidth)/1024:.1f} KB/s)")
    print()


def demonstrate_advanced_bsatn_features():
    """Demonstrate advanced BSATN features."""
    print("=== Advanced BSATN Features Demo ===\n")
    
    # 1. Complex nested structures
    print("1. Complex Nested Structures:")
    writer = BsatnWriter()
    
    # Write a complex game state structure
    writer.write_struct_header(4)  # GameState with 4 fields
    
    writer.write_field_name("world_id")
    writer.write_u32(42)
    
    writer.write_field_name("players")
    writer.write_array_header(2)  # 2 players
    
    # Player 1
    writer.write_struct_header(3)
    writer.write_field_name("id")
    writer.write_u64(123)
    writer.write_field_name("name")
    writer.write_string("Alice")
    writer.write_field_name("level")
    writer.write_u16(25)
    
    # Player 2
    writer.write_struct_header(3)
    writer.write_field_name("id")
    writer.write_u64(456)
    writer.write_field_name("name")
    writer.write_string("Bob")
    writer.write_field_name("level")
    writer.write_u16(30)
    
    writer.write_field_name("timestamp")
    timestamp = SpacetimeDBTimestamp.now()
    timestamp.write_bsatn(writer)
    
    writer.write_field_name("metadata")
    writer.write_bytes(b"binary_game_data_chunk")
    
    complex_data = writer.get_bytes()
    print(f"   Complex structure: {len(complex_data)} bytes")
    print("   ✓ Nested structures encoded successfully")
    
    # 2. Error handling
    print("\n2. Error Handling:")
    try:
        # Try to read from empty buffer
        empty_reader = BsatnReader(b"")
        empty_reader.read_tag()
    except Exception as e:
        print(f"   ✓ Proper error handling: {type(e).__name__}")
    
    # 3. Forward compatibility with skip_value
    print("\n3. Forward Compatibility:")
    reader = BsatnReader(complex_data)
    
    # Read struct header
    tag = reader.read_tag()
    field_count = reader.read_struct_header()
    print(f"   Reading struct with {field_count} fields")
    
    # Skip unknown fields gracefully
    for i in range(field_count):
        field_name = reader.read_field_name()
        print(f"   Field {i+1}: {field_name}")
        if field_name in ["world_id", "timestamp"]:
            # Process known fields
            if field_name == "world_id":
                tag = reader.read_tag()
                world_id = reader.read_u32()
                print(f"     World ID: {world_id}")
            elif field_name == "timestamp":
                # Skip timestamp for this demo
                reader.skip_value()
                print("     Timestamp: (skipped)")
        else:
            # Skip unknown fields
            reader.skip_value()
            print("     (skipped unknown field)")
    
    print("   ✓ Forward compatibility demonstrated")
    print()


def main():
    """Run all BSATN protocol demonstrations."""
    print("SpacetimeDB Python SDK - BSATN Protocol Integration Demo")
    print("=" * 60)
    print()
    
    try:
        # Basic BSATN serialization
        demonstrate_bsatn_serialization()
        
        # Protocol comparison
        demonstrate_protocol_comparison()
        
        # WebSocket client protocols
        demonstrate_websocket_client_protocols()
        
        # Game client example
        demonstrate_game_client()
        
        # Advanced features
        demonstrate_advanced_bsatn_features()
        
        print("🎉 All BSATN protocol demonstrations completed successfully!")
        print("\nKey Benefits of BSATN Protocol:")
        print("✓ Smaller message sizes (better bandwidth efficiency)")
        print("✓ Faster encoding/decoding (better performance)")
        print("✓ Type-safe binary format (better reliability)")
        print("✓ Forward compatibility (better maintainability)")
        print("✓ Native SpacetimeDB integration (better ecosystem)")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 