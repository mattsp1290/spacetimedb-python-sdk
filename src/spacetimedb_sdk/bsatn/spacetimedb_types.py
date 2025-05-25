"""
SpacetimeDB-specific types for BSATN serialization.

This module provides BSATN serialization support for SpacetimeDB types like
Identity, ConnectionId, Timestamp, and TimeDuration.
"""

import struct
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from .writer import BsatnWriter
    from .reader import BsatnReader


class SpacetimeDBIdentity:
    """256-bit Identity type for SpacetimeDB."""
    
    def __init__(self, data: bytes):
        """
        Create an Identity from 32 bytes.
        
        Args:
            data: 32 bytes representing the identity
        """
        if len(data) != 32:
            raise ValueError(f"Identity requires exactly 32 bytes, got {len(data)}")
        self.data = data
    
    @classmethod
    def from_hex(cls, hex_str: str) -> 'SpacetimeDBIdentity':
        """Create Identity from hex string."""
        return cls(bytes.fromhex(hex_str))
    
    def to_hex(self) -> str:
        """Convert to hex string."""
        return self.data.hex()
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write Identity to BSATN format."""
        writer.write_u256_bytes(self.data)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'SpacetimeDBIdentity':
        """Read Identity from BSATN format."""
        data = reader.read_u256_bytes()
        return cls(data)
    
    def __eq__(self, other) -> bool:
        return isinstance(other, SpacetimeDBIdentity) and self.data == other.data
    
    def __hash__(self) -> int:
        return hash(self.data)
    
    def __repr__(self) -> str:
        return f"SpacetimeDBIdentity({self.to_hex()})"


class SpacetimeDBAddress:
    """128-bit Address type for SpacetimeDB."""
    
    def __init__(self, data: bytes):
        """
        Create an Address from 16 bytes.
        
        Args:
            data: 16 bytes representing the address
        """
        if len(data) != 16:
            raise ValueError(f"Address requires exactly 16 bytes, got {len(data)}")
        self.data = data
    
    @classmethod
    def from_hex(cls, hex_str: str) -> 'SpacetimeDBAddress':
        """Create Address from hex string."""
        return cls(bytes.fromhex(hex_str))
    
    def to_hex(self) -> str:
        """Convert to hex string."""
        return self.data.hex()
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write Address to BSATN format."""
        writer.write_u128_bytes(self.data)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'SpacetimeDBAddress':
        """Read Address from BSATN format."""
        data = reader.read_u128_bytes()
        return cls(data)
    
    def __eq__(self, other) -> bool:
        return isinstance(other, SpacetimeDBAddress) and self.data == other.data
    
    def __hash__(self) -> int:
        return hash(self.data)
    
    def __repr__(self) -> str:
        return f"SpacetimeDBAddress({self.to_hex()})"


class SpacetimeDBConnectionId:
    """128-bit ConnectionId type for SpacetimeDB."""
    
    def __init__(self, data: bytes):
        """
        Create a ConnectionId from 16 bytes.
        
        Args:
            data: 16 bytes representing the connection ID
        """
        if len(data) != 16:
            raise ValueError(f"ConnectionId requires exactly 16 bytes, got {len(data)}")
        self.data = data
    
    @classmethod
    def from_hex(cls, hex_str: str) -> 'SpacetimeDBConnectionId':
        """Create ConnectionId from hex string."""
        return cls(bytes.fromhex(hex_str))
    
    @classmethod
    def from_u64_pair(cls, high: int, low: int) -> 'SpacetimeDBConnectionId':
        """Create ConnectionId from two u64 values."""
        data = struct.pack('<QQ', high, low)
        return cls(data)
    
    def to_hex(self) -> str:
        """Convert to hex string."""
        return self.data.hex()
    
    def as_u64_pair(self) -> tuple[int, int]:
        """Get as a pair of u64 values (high, low)."""
        high, low = struct.unpack('<QQ', self.data)
        return (high, low)
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write ConnectionId to BSATN format."""
        writer.write_u128_bytes(self.data)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'SpacetimeDBConnectionId':
        """Read ConnectionId from BSATN format."""
        data = reader.read_u128_bytes()
        return cls(data)
    
    def __eq__(self, other) -> bool:
        return isinstance(other, SpacetimeDBConnectionId) and self.data == other.data
    
    def __hash__(self) -> int:
        return hash(self.data)
    
    def __repr__(self) -> str:
        return f"SpacetimeDBConnectionId({self.to_hex()})"


class SpacetimeDBTimestamp:
    """Timestamp type for SpacetimeDB (microseconds since Unix epoch)."""
    
    def __init__(self, micros_since_epoch: int):
        """
        Create a Timestamp.
        
        Args:
            micros_since_epoch: Microseconds since Unix epoch
        """
        self.micros_since_epoch = micros_since_epoch
    
    @classmethod
    def now(cls) -> 'SpacetimeDBTimestamp':
        """Create a Timestamp for the current time."""
        now = datetime.utcnow()
        micros = int(now.timestamp() * 1_000_000)
        return cls(micros)
    
    @classmethod
    def from_datetime(cls, dt: datetime) -> 'SpacetimeDBTimestamp':
        """Create a Timestamp from a datetime object."""
        micros = int(dt.timestamp() * 1_000_000)
        return cls(micros)
    
    def to_datetime(self) -> datetime:
        """Convert to a datetime object."""
        return datetime.fromtimestamp(self.micros_since_epoch / 1_000_000)
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write Timestamp to BSATN format."""
        writer.write_i64(self.micros_since_epoch)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'SpacetimeDBTimestamp':
        """Read Timestamp from BSATN format."""
        micros = reader.read_i64()
        return cls(micros)
    
    def __eq__(self, other) -> bool:
        return isinstance(other, SpacetimeDBTimestamp) and self.micros_since_epoch == other.micros_since_epoch
    
    def __hash__(self) -> int:
        return hash(self.micros_since_epoch)
    
    def __repr__(self) -> str:
        return f"SpacetimeDBTimestamp({self.micros_since_epoch})"
    
    def __str__(self) -> str:
        return str(self.to_datetime())


class SpacetimeDBTimeDuration:
    """Time duration type for SpacetimeDB (microseconds)."""
    
    def __init__(self, micros: int):
        """
        Create a TimeDuration.
        
        Args:
            micros: Duration in microseconds
        """
        self.micros = micros
    
    @classmethod
    def from_timedelta(cls, td: timedelta) -> 'SpacetimeDBTimeDuration':
        """Create TimeDuration from a timedelta."""
        micros = int(td.total_seconds() * 1_000_000)
        return cls(micros)
    
    def to_timedelta(self) -> timedelta:
        """Convert to a timedelta."""
        return timedelta(microseconds=self.micros)
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write TimeDuration to BSATN format."""
        writer.write_i64(self.micros)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'SpacetimeDBTimeDuration':
        """Read TimeDuration from BSATN format."""
        micros = reader.read_i64()
        return cls(micros)
    
    def __eq__(self, other) -> bool:
        return isinstance(other, SpacetimeDBTimeDuration) and self.micros == other.micros
    
    def __hash__(self) -> int:
        return hash(self.micros)
    
    def __repr__(self) -> str:
        return f"SpacetimeDBTimeDuration({self.micros})"
    
    def __str__(self) -> str:
        return str(self.to_timedelta())


# Convenience re-exports that match the protocol.py naming
Identity = SpacetimeDBIdentity
Address = SpacetimeDBAddress
ConnectionId = SpacetimeDBConnectionId
Timestamp = SpacetimeDBTimestamp
TimeDuration = SpacetimeDBTimeDuration 