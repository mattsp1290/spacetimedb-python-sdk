"""
Enhanced ConnectionId and Identity Management for SpacetimeDB Protocol v1.1.1

This module provides comprehensive ConnectionId tracking, Identity management,
connection lifecycle management, event system, and metrics tracking.
"""

from typing import Optional, List, Dict, Any, Callable, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import struct
import time
import threading
import secrets
import hashlib
from collections import defaultdict

if TYPE_CHECKING:
    from .bsatn.writer import BsatnWriter
    from .bsatn.reader import BsatnReader


class ConnectionState(Enum):
    """Connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class ConnectionEventType(Enum):
    """Types of connection events."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    IDENTITY_CHANGED = "identity_changed"
    RECONNECTION_ATTEMPT = "reconnection_attempt"
    CONNECTION_FAILED = "connection_failed"


@dataclass
class ConnectionEvent:
    """Represents a connection event."""
    event_type: ConnectionEventType
    connection_id: Optional['EnhancedConnectionId']
    timestamp: float
    data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class EnhancedConnectionId:
    """Enhanced ConnectionId with [2]uint64 format support and advanced features."""
    
    def __init__(self, data: bytes):
        """
        Initialize ConnectionId from raw bytes.
        
        Args:
            data: Raw bytes representing the connection ID
        """
        self.data = data
    
    @classmethod
    def from_hex(cls, hex_string: str) -> 'EnhancedConnectionId':
        """Create ConnectionId from hex string."""
        return cls(data=bytes.fromhex(hex_string))
    
    @classmethod
    def from_u64_pair(cls, high: int, low: int) -> 'EnhancedConnectionId':
        """
        Create ConnectionId from a pair of u64 values.
        
        Args:
            high: High 64-bit value
            low: Low 64-bit value
            
        Returns:
            New ConnectionId instance
        """
        # Pack as little-endian u64 values
        data = struct.pack('<QQ', high, low)
        return cls(data=data)
    
    @classmethod
    def generate_random(cls) -> 'EnhancedConnectionId':
        """Generate a random ConnectionId."""
        # Generate two random u64 values
        high = secrets.randbits(64)
        low = secrets.randbits(64)
        return cls.from_u64_pair(high, low)
    
    def to_hex(self) -> str:
        """Convert ConnectionId to hex string."""
        return self.data.hex()
    
    def to_u64_pair(self) -> tuple[int, int]:
        """
        Extract ConnectionId as a pair of u64 values.
        
        Returns:
            Tuple of two u64 values (high, low)
        """
        if len(self.data) < 16:
            # Pad with zeros if data is shorter than expected
            padded_data = self.data + b'\x00' * (16 - len(self.data))
        else:
            padded_data = self.data[:16]  # Take first 16 bytes
        
        # Extract as two u64 values (little-endian)
        high = struct.unpack('<Q', padded_data[:8])[0]
        low = struct.unpack('<Q', padded_data[8:16])[0]
        return (high, low)
    
    def as_u64_pair(self) -> tuple[int, int]:
        """Alias for to_u64_pair for backward compatibility."""
        return self.to_u64_pair()
    
    def is_valid(self) -> bool:
        """Check if the ConnectionId is valid (non-zero)."""
        return any(b != 0 for b in self.data)
    
    def get_timestamp(self) -> Optional[int]:
        """
        Extract timestamp from ConnectionId if embedded.
        
        This is a simplified implementation - real ConnectionIds may have
        different timestamp encoding schemes.
        
        Returns:
            Timestamp in milliseconds if extractable, None otherwise
        """
        if len(self.data) >= 8:
            # Extract first 8 bytes as potential timestamp
            timestamp = struct.unpack('<Q', self.data[:8])[0]
            # Check if it looks like a reasonable timestamp (year 2020-2050)
            if 1577836800000 <= timestamp <= 2524608000000:  # 2020-2050 in ms
                return timestamp
        return None
    
    def get_node_id(self) -> Optional[int]:
        """
        Extract node ID from ConnectionId if embedded.
        
        Returns:
            Node ID if extractable, None otherwise
        """
        if len(self.data) >= 16:
            # Extract last 8 bytes as potential node ID
            node_id = struct.unpack('<Q', self.data[8:16])[0]
            return node_id
        return None
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write this ConnectionId to BSATN."""
        writer.write_bytes(self.data)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedConnectionId':
        """Read ConnectionId from BSATN."""
        data = reader.read_bytes_raw()
        return cls(data=data)
    
    def __str__(self) -> str:
        return self.to_hex()
    
    def __repr__(self) -> str:
        return f"EnhancedConnectionId(hex='{self.to_hex()}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, (EnhancedConnectionId, type(self))):
            return False
        return self.data == other.data
    
    def __hash__(self) -> int:
        return hash(self.data)


class EnhancedIdentity:
    """Enhanced Identity with modern format support and advanced features."""
    
    def __init__(self, data: bytes):
        """
        Initialize Identity from raw bytes.
        
        Args:
            data: Raw bytes representing the identity
        """
        self.data = data
    
    @classmethod
    def from_hex(cls, hex_string: str) -> 'EnhancedIdentity':
        """Create Identity from hex string."""
        return cls(data=bytes.fromhex(hex_string))
    
    @classmethod
    def from_public_key(cls, public_key: bytes) -> 'EnhancedIdentity':
        """
        Create Identity from a public key.
        
        Args:
            public_key: Raw public key bytes
            
        Returns:
            New Identity instance
        """
        # Hash the public key to create identity
        identity_hash = hashlib.sha256(public_key).digest()
        return cls(data=identity_hash)
    
    @classmethod
    def generate_random(cls) -> 'EnhancedIdentity':
        """Generate a random Identity for testing."""
        random_data = secrets.token_bytes(32)  # 256-bit identity
        return cls(data=random_data)
    
    def to_hex(self) -> str:
        """Convert Identity to hex string."""
        return self.data.hex()
    
    def get_version(self) -> int:
        """
        Extract version from Identity if embedded.
        
        Returns:
            Version number if extractable, 1 otherwise
        """
        if len(self.data) >= 1:
            # First byte could be version
            return self.data[0]
        return 1
    
    def get_public_key(self) -> Optional[bytes]:
        """
        Extract public key from Identity if available.
        
        This is simplified - real implementations may store
        the full public key or a reference to it.
        
        Returns:
            Public key bytes if available, None otherwise
        """
        # In a simplified model, the identity IS derived from the public key
        # In practice, this might require additional data or lookups
        return None
    
    def is_anonymous(self) -> bool:
        """Check if this is an anonymous identity."""
        # Anonymous identity is typically all zeros or a special pattern
        return all(b == 0 for b in self.data)
    
    def validate_format(self) -> bool:
        """Validate the identity format."""
        # Basic validation - must be non-empty and reasonable length
        return len(self.data) >= 8 and len(self.data) <= 64
    
    def to_address(self) -> str:
        """
        Convert Identity to a user-friendly address.
        
        Returns:
            Base58-encoded address (simplified implementation)
        """
        # Simplified address format using hex encoding
        # Real implementation might use Base58 or Bech32
        return f"stdb1{self.to_hex()[:16]}"
    
    def __str__(self) -> str:
        return self.to_hex()
    
    def __repr__(self) -> str:
        return f"EnhancedIdentity(hex='{self.to_hex()}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, (EnhancedIdentity, type(self))):
            return False
        return self.data == other.data
    
    def __hash__(self) -> int:
        return hash(self.data)


@dataclass
class EnhancedIdentityToken:
    """Enhanced IdentityToken with token processing capabilities."""
    identity: EnhancedIdentity
    token: str
    connection_id: EnhancedConnectionId
    issued_at: Optional[float] = None
    expires_at: Optional[float] = None
    
    def __post_init__(self):
        if self.issued_at is None:
            self.issued_at = time.time()
        if self.expires_at is None:
            # Default to 24 hour expiration
            self.expires_at = self.issued_at + (24 * 60 * 60)
    
    def extract_claims(self) -> Dict[str, Any]:
        """
        Extract claims from the token.
        
        Returns:
            Dictionary of token claims
        """
        # Simplified implementation - real tokens might be JWTs
        return {
            'identity': self.identity.to_hex(),
            'connection_id': self.connection_id.to_hex(),
            'issued_at': self.issued_at,
            'expires_at': self.expires_at,
            'token_length': len(self.token)
        }
    
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def get_issued_at(self) -> Optional[float]:
        """Get token issuance time."""
        return self.issued_at
    
    def get_expires_at(self) -> Optional[float]:
        """Get token expiration time."""
        return self.expires_at
    
    def validate_signature(self) -> bool:
        """
        Validate token signature.
        
        Simplified implementation - real validation would verify
        cryptographic signature.
        
        Returns:
            True if signature is valid
        """
        # Simplified validation - allow alphanumeric and underscores
        return len(self.token) >= 10 and all(c.isalnum() or c == '_' for c in self.token)
    
    def refresh_if_needed(self, threshold: float = 3600) -> bool:
        """
        Check if token needs refresh and mark for refresh.
        
        Args:
            threshold: Seconds before expiration to trigger refresh
            
        Returns:
            True if refresh is needed
        """
        if self.expires_at is None:
            return False
        
        time_until_expiry = self.expires_at - time.time()
        return time_until_expiry <= threshold


class ConnectionStateTracker:
    """Tracks connection states and provides state queries."""
    
    def __init__(self):
        self._states: Dict[EnhancedConnectionId, ConnectionState] = {}
        self._connection_times: Dict[EnhancedConnectionId, float] = {}
        self._lock = threading.Lock()
    
    def track_connection(self, connection_id: EnhancedConnectionId, 
                        state: ConnectionState = ConnectionState.CONNECTED) -> None:
        """
        Track a connection and its state.
        
        Args:
            connection_id: The connection to track
            state: Initial connection state
        """
        with self._lock:
            self._states[connection_id] = state
            if state == ConnectionState.CONNECTED:
                self._connection_times[connection_id] = time.time()
    
    def get_connection_state(self, connection_id: EnhancedConnectionId) -> ConnectionState:
        """
        Get the current state of a connection.
        
        Args:
            connection_id: The connection to query
            
        Returns:
            Current connection state
        """
        with self._lock:
            return self._states.get(connection_id, ConnectionState.DISCONNECTED)
    
    def is_connected(self, connection_id: EnhancedConnectionId) -> bool:
        """Check if a connection is currently connected."""
        return self.get_connection_state(connection_id) == ConnectionState.CONNECTED
    
    def get_active_connections(self) -> List[EnhancedConnectionId]:
        """Get list of currently active connections."""
        with self._lock:
            return [
                conn_id for conn_id, state in self._states.items()
                if state == ConnectionState.CONNECTED
            ]
    
    def connection_established(self, connection_id: EnhancedConnectionId) -> None:
        """Mark a connection as established."""
        self.track_connection(connection_id, ConnectionState.CONNECTED)
    
    def connection_lost(self, connection_id: EnhancedConnectionId) -> None:
        """Mark a connection as lost."""
        with self._lock:
            self._states[connection_id] = ConnectionState.DISCONNECTED
            # Keep connection time for history
    
    def get_connection_duration(self, connection_id: EnhancedConnectionId) -> Optional[float]:
        """
        Get the duration of a connection.
        
        Args:
            connection_id: The connection to query
            
        Returns:
            Duration in seconds if connected, None otherwise
        """
        with self._lock:
            start_time = self._connection_times.get(connection_id)
            if start_time is None:
                return None
            
            if self.is_connected(connection_id):
                return time.time() - start_time
            else:
                # Connection is no longer active, return last known duration
                return None


ConnectionEventListener = Callable[[ConnectionEvent], None]


class ConnectionLifecycleManager:
    """Manages connection lifecycle events and listeners."""
    
    def __init__(self):
        self._listeners: Dict[str, List[ConnectionEventListener]] = defaultdict(list)
        self._connection_history: List[ConnectionEvent] = []
        self._state_tracker = ConnectionStateTracker()
        self._lock = threading.Lock()
    
    def register_listener(self, event_type: str, listener: ConnectionEventListener) -> None:
        """
        Register an event listener.
        
        Args:
            event_type: Type of event to listen for
            listener: Callback function to handle events
        """
        with self._lock:
            self._listeners[event_type].append(listener)
    
    def _emit_event(self, event: ConnectionEvent) -> None:
        """Emit an event to all registered listeners."""
        with self._lock:
            self._connection_history.append(event)
            
            # Notify listeners
            event_type_str = event.event_type.value
            for listener in self._listeners.get(event_type_str, []):
                try:
                    listener(event)
                except Exception as e:
                    # Log error but don't break other listeners
                    print(f"Error in connection event listener: {e}")
    
    def on_connection_established(self, connection_id: EnhancedConnectionId, 
                                identity: Optional[EnhancedIdentity] = None) -> None:
        """Handle connection establishment."""
        self._state_tracker.connection_established(connection_id)
        
        event = ConnectionEvent(
            event_type=ConnectionEventType.CONNECTED,
            connection_id=connection_id,
            timestamp=time.time(),
            data={'identity': identity.to_hex() if identity else None}
        )
        self._emit_event(event)
    
    def on_connection_lost(self, connection_id: EnhancedConnectionId, 
                          reason: Optional[str] = None) -> None:
        """Handle connection loss."""
        self._state_tracker.connection_lost(connection_id)
        
        event = ConnectionEvent(
            event_type=ConnectionEventType.DISCONNECTED,
            connection_id=connection_id,
            timestamp=time.time(),
            data={'reason': reason}
        )
        self._emit_event(event)
    
    def on_identity_changed(self, connection_id: EnhancedConnectionId, 
                           old_identity: Optional[EnhancedIdentity],
                           new_identity: EnhancedIdentity) -> None:
        """Handle identity change."""
        event = ConnectionEvent(
            event_type=ConnectionEventType.IDENTITY_CHANGED,
            connection_id=connection_id,
            timestamp=time.time(),
            data={
                'old_identity': old_identity.to_hex() if old_identity else None,
                'new_identity': new_identity.to_hex()
            }
        )
        self._emit_event(event)
    
    def get_connection_duration(self, connection_id: EnhancedConnectionId) -> Optional[float]:
        """Get connection duration."""
        return self._state_tracker.get_connection_duration(connection_id)
    
    def get_connection_history(self) -> List[ConnectionEvent]:
        """Get connection event history."""
        with self._lock:
            return self._connection_history.copy()


class ConnectionMetrics:
    """Tracks connection metrics and statistics."""
    
    def __init__(self):
        self._total_connections = 0
        self._connection_durations: List[float] = []
        self._active_connections: Dict[EnhancedConnectionId, float] = {}
        self._lock = threading.Lock()
    
    def record_connection(self, connection_id: EnhancedConnectionId) -> None:
        """Record a new connection."""
        with self._lock:
            self._total_connections += 1
            self._active_connections[connection_id] = time.time()
    
    def record_disconnection(self, connection_id: EnhancedConnectionId) -> None:
        """Record a disconnection."""
        with self._lock:
            if connection_id in self._active_connections:
                start_time = self._active_connections.pop(connection_id)
                duration = time.time() - start_time
                self._connection_durations.append(duration)
    
    def get_total_connections(self) -> int:
        """Get total number of connections."""
        return self._total_connections
    
    def get_active_connections(self) -> int:
        """Get number of currently active connections."""
        with self._lock:
            return len(self._active_connections)
    
    def get_average_duration(self) -> float:
        """Get average connection duration."""
        with self._lock:
            if not self._connection_durations:
                return 0.0
            return sum(self._connection_durations) / len(self._connection_durations)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get comprehensive connection statistics."""
        with self._lock:
            return {
                'total_connections': self._total_connections,
                'active_connections': len(self._active_connections),
                'average_duration': self.get_average_duration(),
                'total_completed_connections': len(self._connection_durations),
                'longest_duration': max(self._connection_durations) if self._connection_durations else 0.0,
                'shortest_duration': min(self._connection_durations) if self._connection_durations else 0.0
            }


# Export all enhanced types
__all__ = [
    'ConnectionState',
    'ConnectionEventType',
    'ConnectionEvent',
    'EnhancedConnectionId',
    'EnhancedIdentity',
    'EnhancedIdentityToken',
    'ConnectionStateTracker',
    'ConnectionLifecycleManager',
    'ConnectionMetrics',
    'ConnectionEventListener'
] 