"""
Specialized data structures for SpacetimeDB Python SDK.

Provides SpacetimeDB-specific data structures and collection utilities including:
- OperationsMap for efficient key-value operations with custom equality
- Specialized collections for Identity, ConnectionId, QueryId
- Performance-optimized data structures for SpacetimeDB use cases
- Type-safe iteration patterns and concurrent access support
"""

import threading
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict, OrderedDict
from typing import (
    Any, Dict, List, Optional, Union, Tuple, Callable, TypeVar, Generic,
    Iterator, Set, Hashable, Protocol, runtime_checkable
)
from dataclasses import dataclass, field
from enum import Enum
import time
import json
from concurrent.futures import ThreadPoolExecutor
import logging

# Import SpacetimeDB types
from .protocol import Identity, ConnectionId, QueryId
from .time_utils import EnhancedTimestamp

# Type definitions
K = TypeVar('K')
V = TypeVar('V')
T = TypeVar('T')


@runtime_checkable
class Equalable(Protocol):
    """Protocol for objects that support custom equality checking."""
    
    def is_equal(self, other: Any) -> bool:
        """Check if this object is equal to another using custom logic."""
        ...


class CollectionStrategy(Enum):
    """Strategy for collection operations."""
    HASH_MAP = "hash_map"
    ORDERED_MAP = "ordered_map"
    CONCURRENT_MAP = "concurrent_map"
    MEMORY_OPTIMIZED = "memory_optimized"


@dataclass
class CollectionMetrics:
    """Metrics for collection performance monitoring."""
    operation_count: int = 0
    total_time: float = 0.0
    average_time: float = 0.0
    max_time: float = 0.0
    min_time: float = float('inf')
    memory_usage: int = 0
    collision_count: int = 0
    
    def update(self, operation_time: float):
        """Update metrics with a new operation time."""
        self.operation_count += 1
        self.total_time += operation_time
        self.average_time = self.total_time / self.operation_count
        self.max_time = max(self.max_time, operation_time)
        self.min_time = min(self.min_time, operation_time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "operation_count": self.operation_count,
            "total_time": self.total_time,
            "average_time": self.average_time,
            "max_time": self.max_time,
            "min_time": self.min_time if self.min_time != float('inf') else 0.0,
            "memory_usage": self.memory_usage,
            "collision_count": self.collision_count
        }


class OperationsMap(Generic[K, V]):
    """
    A specialized map for SpacetimeDB operations with custom equality checking.
    
    This map supports custom equality checking via isEqual method and provides
    efficient key-value operations optimized for SpacetimeDB objects.
    """
    
    def __init__(self, strategy: CollectionStrategy = CollectionStrategy.HASH_MAP):
        """Initialize the operations map with the specified strategy."""
        self._strategy = strategy
        self._data: Dict[Any, V] = {}
        self._custom_equality_keys: Dict[Any, K] = {}
        self._metrics = CollectionMetrics()
        self._lock = threading.RLock()
        
        # Strategy-specific initialization
        if strategy == CollectionStrategy.ORDERED_MAP:
            self._data = OrderedDict()
        elif strategy == CollectionStrategy.CONCURRENT_MAP:
            self._executor = ThreadPoolExecutor(max_workers=4)
    
    def _get_key_hash(self, key: K) -> Any:
        """Get a hashable representation of the key."""
        if hasattr(key, '__hash__') and key.__hash__ is not None:
            try:
                return hash(key)
            except TypeError:
                pass
        
        # For unhashable types, use string representation
        return str(key)
    
    def _keys_equal(self, key1: K, key2: K) -> bool:
        """Check if two keys are equal using custom equality if available."""
        # Try custom equality first
        if isinstance(key1, Equalable):
            return key1.is_equal(key2)
        elif isinstance(key2, Equalable):
            return key2.is_equal(key1)
        
        # Fall back to standard equality
        return key1 == key2
    
    def _find_matching_key(self, key: K) -> Optional[K]:
        """Find a matching key in the map using custom equality."""
        key_hash = self._get_key_hash(key)
        
        # Check if we have this exact hash
        if key_hash in self._custom_equality_keys:
            stored_key = self._custom_equality_keys[key_hash]
            if self._keys_equal(key, stored_key):
                return stored_key
        
        # Linear search for custom equality (only for Equalable objects)
        if isinstance(key, Equalable):
            for stored_key in self._custom_equality_keys.values():
                if self._keys_equal(key, stored_key):
                    return stored_key
        
        return None
    
    def set(self, key: K, value: V) -> None:
        """Set a key-value pair in the map."""
        start_time = time.perf_counter()
        
        with self._lock:
            # Find existing key or use new one
            existing_key = self._find_matching_key(key)
            if existing_key is not None:
                key_hash = self._get_key_hash(existing_key)
            else:
                key_hash = self._get_key_hash(key)
                self._custom_equality_keys[key_hash] = key
            
            self._data[key_hash] = value
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
    
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Get a value by key, returning default if not found."""
        start_time = time.perf_counter()
        
        with self._lock:
            existing_key = self._find_matching_key(key)
            if existing_key is not None:
                key_hash = self._get_key_hash(existing_key)
                result = self._data.get(key_hash, default)
            else:
                result = default
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return result
    
    def has(self, key: K) -> bool:
        """Check if the map contains the specified key."""
        with self._lock:
            return self._find_matching_key(key) is not None
    
    def delete(self, key: K) -> bool:
        """Delete a key-value pair from the map. Returns True if deleted."""
        start_time = time.perf_counter()
        
        with self._lock:
            existing_key = self._find_matching_key(key)
            if existing_key is not None:
                key_hash = self._get_key_hash(existing_key)
                if key_hash in self._data:
                    del self._data[key_hash]
                    del self._custom_equality_keys[key_hash]
                    operation_time = time.perf_counter() - start_time
                    self._metrics.update(operation_time)
                    return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def clear(self) -> None:
        """Clear all entries from the map."""
        with self._lock:
            self._data.clear()
            self._custom_equality_keys.clear()
    
    def size(self) -> int:
        """Get the number of entries in the map."""
        with self._lock:
            return len(self._data)
    
    def is_empty(self) -> bool:
        """Check if the map is empty."""
        return self.size() == 0
    
    def keys(self) -> Iterator[K]:
        """Iterate over all keys in the map."""
        with self._lock:
            return iter(self._custom_equality_keys.values())
    
    def values(self) -> Iterator[V]:
        """Iterate over all values in the map."""
        with self._lock:
            return iter(self._data.values())
    
    def items(self) -> Iterator[Tuple[K, V]]:
        """Iterate over all key-value pairs in the map."""
        with self._lock:
            for key_hash, value in self._data.items():
                key = self._custom_equality_keys[key_hash]
                yield (key, value)
    
    def get_metrics(self) -> CollectionMetrics:
        """Get performance metrics for this map."""
        return self._metrics
    
    def __len__(self) -> int:
        """Get the number of entries in the map."""
        return self.size()
    
    def __contains__(self, key: K) -> bool:
        """Check if the map contains the specified key."""
        return self.has(key)
    
    def __getitem__(self, key: K) -> V:
        """Get a value by key, raising KeyError if not found."""
        result = self.get(key)
        if result is None:
            raise KeyError(f"Key not found: {key}")
        return result
    
    def __setitem__(self, key: K, value: V) -> None:
        """Set a key-value pair in the map."""
        self.set(key, value)
    
    def __delitem__(self, key: K) -> None:
        """Delete a key-value pair from the map."""
        if not self.delete(key):
            raise KeyError(f"Key not found: {key}")


class IdentityCollection:
    """Specialized collection for SpacetimeDB Identity objects."""
    
    def __init__(self):
        """Initialize the identity collection."""
        self._identity_map: Dict[str, Identity] = {}
        self._lock = threading.RLock()
        self._metrics = CollectionMetrics()
    
    def add(self, identity: Identity) -> bool:
        """Add an identity to the collection. Returns True if added (not duplicate)."""
        start_time = time.perf_counter()
        
        with self._lock:
            identity_str = identity.to_hex()
            if identity_str not in self._identity_map:
                self._identity_map[identity_str] = identity
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def remove(self, identity: Identity) -> bool:
        """Remove an identity from the collection. Returns True if removed."""
        start_time = time.perf_counter()
        
        with self._lock:
            identity_str = identity.to_hex()
            if identity_str in self._identity_map:
                del self._identity_map[identity_str]
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def contains(self, identity: Identity) -> bool:
        """Check if the collection contains the specified identity."""
        with self._lock:
            return identity.to_hex() in self._identity_map
    
    def find_by_hex(self, hex_string: str) -> Optional[Identity]:
        """Find an identity by its hex string representation."""
        with self._lock:
            return self._identity_map.get(hex_string)
    
    def size(self) -> int:
        """Get the number of identities in the collection."""
        with self._lock:
            return len(self._identity_map)
    
    def clear(self) -> None:
        """Clear all identities from the collection."""
        with self._lock:
            self._identity_map.clear()
    
    def to_list(self) -> List[Identity]:
        """Get all identities as a list."""
        with self._lock:
            return list(self._identity_map.values())
    
    def get_metrics(self) -> CollectionMetrics:
        """Get performance metrics for this collection."""
        return self._metrics
    
    def __len__(self) -> int:
        """Get the number of identities in the collection."""
        return self.size()
    
    def __contains__(self, identity: Identity) -> bool:
        """Check if the collection contains the specified identity."""
        return self.contains(identity)
    
    def __iter__(self) -> Iterator[Identity]:
        """Iterate over all identities in the collection."""
        with self._lock:
            return iter(list(self._identity_map.values()))


class ConnectionIdCollection:
    """Specialized collection for SpacetimeDB ConnectionId objects."""
    
    def __init__(self):
        """Initialize the connection ID collection."""
        self._connections: Dict[int, ConnectionId] = {}
        self._connection_metadata: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._metrics = CollectionMetrics()
    
    def add(self, connection_id: ConnectionId, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a connection ID with optional metadata. Returns True if added."""
        start_time = time.perf_counter()
        
        with self._lock:
            conn_hash = hash(connection_id.data)
            if conn_hash not in self._connections:
                self._connections[conn_hash] = connection_id
                self._connection_metadata[conn_hash] = metadata or {}
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def remove(self, connection_id: ConnectionId) -> bool:
        """Remove a connection ID from the collection. Returns True if removed."""
        start_time = time.perf_counter()
        
        with self._lock:
            conn_hash = hash(connection_id.data)
            if conn_hash in self._connections:
                del self._connections[conn_hash]
                del self._connection_metadata[conn_hash]
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def contains(self, connection_id: ConnectionId) -> bool:
        """Check if the collection contains the specified connection ID."""
        with self._lock:
            return hash(connection_id.data) in self._connections
    
    def find_by_hex(self, hex_string: str) -> Optional[ConnectionId]:
        """Find a connection ID by its hex string representation."""
        try:
            target_data = bytes.fromhex(hex_string)
            target_hash = hash(target_data)
            with self._lock:
                return self._connections.get(target_hash)
        except ValueError:
            # Invalid hex string
            return None
    
    def get_metadata(self, connection_id: ConnectionId) -> Dict[str, Any]:
        """Get metadata for a connection ID."""
        with self._lock:
            return self._connection_metadata.get(hash(connection_id.data), {})
    
    def set_metadata(self, connection_id: ConnectionId, metadata: Dict[str, Any]) -> bool:
        """Set metadata for a connection ID. Returns True if connection exists."""
        with self._lock:
            conn_hash = hash(connection_id.data)
            if conn_hash in self._connections:
                self._connection_metadata[conn_hash] = metadata
                return True
            return False
    
    def size(self) -> int:
        """Get the number of connection IDs in the collection."""
        with self._lock:
            return len(self._connections)
    
    def clear(self) -> None:
        """Clear all connection IDs from the collection."""
        with self._lock:
            self._connections.clear()
            self._connection_metadata.clear()
    
    def to_list(self) -> List[ConnectionId]:
        """Get all connection IDs as a list."""
        with self._lock:
            return list(self._connections.values())
    
    def get_metrics(self) -> CollectionMetrics:
        """Get performance metrics for this collection."""
        return self._metrics
    
    def __len__(self) -> int:
        """Get the number of connection IDs in the collection."""
        return self.size()
    
    def __contains__(self, connection_id: ConnectionId) -> bool:
        """Check if the collection contains the specified connection ID."""
        return self.contains(connection_id)
    
    def __iter__(self) -> Iterator[ConnectionId]:
        """Iterate over all connection IDs in the collection."""
        with self._lock:
            return iter(list(self._connections.values()))


class QueryIdCollection:
    """Specialized collection for SpacetimeDB QueryId objects."""
    
    def __init__(self):
        """Initialize the query ID collection."""
        self._queries: Dict[int, QueryId] = {}
        self._query_metadata: Dict[int, Dict[str, Any]] = {}
        self._query_timestamps: Dict[int, float] = {}
        self._lock = threading.RLock()
        self._metrics = CollectionMetrics()
    
    def add(self, query_id: QueryId, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a query ID with optional metadata. Returns True if added."""
        start_time = time.perf_counter()
        
        with self._lock:
            q_id = query_id.id
            if q_id not in self._queries:
                self._queries[q_id] = query_id
                self._query_metadata[q_id] = metadata or {}
                self._query_timestamps[q_id] = time.time()
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def remove(self, query_id: QueryId) -> bool:
        """Remove a query ID from the collection. Returns True if removed."""
        start_time = time.perf_counter()
        
        with self._lock:
            q_id = query_id.id
            if q_id in self._queries:
                del self._queries[q_id]
                del self._query_metadata[q_id]
                del self._query_timestamps[q_id]
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def contains(self, query_id: QueryId) -> bool:
        """Check if the collection contains the specified query ID."""
        with self._lock:
            return query_id.id in self._queries
    
    def find_by_id(self, q_id: int) -> Optional[QueryId]:
        """Find a query ID by its integer value."""
        with self._lock:
            return self._queries.get(q_id)
    
    def get_metadata(self, query_id: QueryId) -> Dict[str, Any]:
        """Get metadata for a query ID."""
        with self._lock:
            return self._query_metadata.get(query_id.id, {})
    
    def get_timestamp(self, query_id: QueryId) -> Optional[float]:
        """Get the timestamp when the query ID was added."""
        with self._lock:
            return self._query_timestamps.get(query_id.id)
    
    def find_by_age(self, max_age_seconds: float) -> List[QueryId]:
        """Find query IDs older than the specified age in seconds."""
        current_time = time.time()
        result = []
        
        with self._lock:
            for q_id, timestamp in self._query_timestamps.items():
                age = current_time - timestamp
                if age > max_age_seconds:
                    result.append(self._queries[q_id])
        
        return result
    
    def cleanup_old_queries(self, max_age_seconds: float) -> int:
        """Remove query IDs older than the specified age. Returns count removed."""
        old_queries = self.find_by_age(max_age_seconds)
        removed_count = 0
        
        for query_id in old_queries:
            if self.remove(query_id):
                removed_count += 1
        
        return removed_count
    
    def size(self) -> int:
        """Get the number of query IDs in the collection."""
        with self._lock:
            return len(self._queries)
    
    def clear(self) -> None:
        """Clear all query IDs from the collection."""
        with self._lock:
            self._queries.clear()
            self._query_metadata.clear()
            self._query_timestamps.clear()
    
    def to_list(self) -> List[QueryId]:
        """Get all query IDs as a list."""
        with self._lock:
            return list(self._queries.values())
    
    def get_metrics(self) -> CollectionMetrics:
        """Get performance metrics for this collection."""
        return self._metrics
    
    def __len__(self) -> int:
        """Get the number of query IDs in the collection."""
        return self.size()
    
    def __contains__(self, query_id: QueryId) -> bool:
        """Check if the collection contains the specified query ID."""
        return self.contains(query_id)
    
    def __iter__(self) -> Iterator[QueryId]:
        """Iterate over all query IDs in the collection."""
        with self._lock:
            return iter(list(self._queries.values()))


class ConcurrentSet(Generic[T]):
    """Thread-safe set implementation optimized for SpacetimeDB use cases."""
    
    def __init__(self):
        """Initialize the concurrent set."""
        self._data: Set[T] = set()
        self._lock = threading.RLock()
        self._metrics = CollectionMetrics()
    
    def add(self, item: T) -> bool:
        """Add an item to the set. Returns True if added (not duplicate)."""
        start_time = time.perf_counter()
        
        with self._lock:
            if item not in self._data:
                self._data.add(item)
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def remove(self, item: T) -> bool:
        """Remove an item from the set. Returns True if removed."""
        start_time = time.perf_counter()
        
        with self._lock:
            if item in self._data:
                self._data.remove(item)
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def contains(self, item: T) -> bool:
        """Check if the set contains the specified item."""
        with self._lock:
            return item in self._data
    
    def size(self) -> int:
        """Get the number of items in the set."""
        with self._lock:
            return len(self._data)
    
    def clear(self) -> None:
        """Clear all items from the set."""
        with self._lock:
            self._data.clear()
    
    def to_list(self) -> List[T]:
        """Get all items as a list."""
        with self._lock:
            return list(self._data)
    
    def union(self, other: 'ConcurrentSet[T]') -> 'ConcurrentSet[T]':
        """Return a new set with items from both sets."""
        result = ConcurrentSet[T]()
        with self._lock:
            with other._lock:
                result._data = self._data.union(other._data)
        return result
    
    def intersection(self, other: 'ConcurrentSet[T]') -> 'ConcurrentSet[T]':
        """Return a new set with items common to both sets."""
        result = ConcurrentSet[T]()
        with self._lock:
            with other._lock:
                result._data = self._data.intersection(other._data)
        return result
    
    def difference(self, other: 'ConcurrentSet[T]') -> 'ConcurrentSet[T]':
        """Return a new set with items in this set but not in other."""
        result = ConcurrentSet[T]()
        with self._lock:
            with other._lock:
                result._data = self._data.difference(other._data)
        return result
    
    def get_metrics(self) -> CollectionMetrics:
        """Get performance metrics for this set."""
        return self._metrics
    
    def __len__(self) -> int:
        """Get the number of items in the set."""
        return self.size()
    
    def __contains__(self, item: T) -> bool:
        """Check if the set contains the specified item."""
        return self.contains(item)
    
    def __iter__(self) -> Iterator[T]:
        """Iterate over all items in the set."""
        with self._lock:
            return iter(list(self._data))


class LRUCache(Generic[K, V]):
    """Least Recently Used cache implementation for SpacetimeDB objects."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize the LRU cache with the specified maximum size."""
        self._max_size = max_size
        self._data: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.RLock()
        self._metrics = CollectionMetrics()
        self._hit_count = 0
        self._miss_count = 0
    
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Get a value by key, moving it to the end (most recently used)."""
        start_time = time.perf_counter()
        
        with self._lock:
            if key in self._data:
                # Move to end (most recently used)
                value = self._data.pop(key)
                self._data[key] = value
                self._hit_count += 1
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return value
            else:
                self._miss_count += 1
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return default
    
    def set(self, key: K, value: V) -> None:
        """Set a key-value pair, evicting least recently used if necessary."""
        start_time = time.perf_counter()
        
        with self._lock:
            if key in self._data:
                # Update existing key
                self._data.pop(key)
            elif len(self._data) >= self._max_size:
                # Evict least recently used
                self._data.popitem(last=False)
            
            self._data[key] = value
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
    
    def delete(self, key: K) -> bool:
        """Delete a key-value pair. Returns True if deleted."""
        start_time = time.perf_counter()
        
        with self._lock:
            if key in self._data:
                del self._data[key]
                operation_time = time.perf_counter() - start_time
                self._metrics.update(operation_time)
                return True
        
        operation_time = time.perf_counter() - start_time
        self._metrics.update(operation_time)
        return False
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._data.clear()
            self._hit_count = 0
            self._miss_count = 0
    
    def size(self) -> int:
        """Get the number of entries in the cache."""
        with self._lock:
            return len(self._data)
    
    def get_hit_ratio(self) -> float:
        """Get the cache hit ratio."""
        total_requests = self._hit_count + self._miss_count
        if total_requests == 0:
            return 0.0
        return self._hit_count / total_requests
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for this cache."""
        base_metrics = self._metrics.to_dict()
        base_metrics.update({
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_ratio": self.get_hit_ratio(),
            "current_size": self.size(),
            "max_size": self._max_size
        })
        return base_metrics
    
    def __len__(self) -> int:
        """Get the number of entries in the cache."""
        return self.size()
    
    def __contains__(self, key: K) -> bool:
        """Check if the cache contains the specified key."""
        with self._lock:
            return key in self._data
    
    def __getitem__(self, key: K) -> V:
        """Get a value by key, raising KeyError if not found."""
        result = self.get(key)
        if result is None:
            raise KeyError(f"Key not found: {key}")
        return result
    
    def __setitem__(self, key: K, value: V) -> None:
        """Set a key-value pair in the cache."""
        self.set(key, value)


class CollectionManager:
    """Manager for all specialized collections in SpacetimeDB."""
    
    def __init__(self):
        """Initialize the collection manager."""
        self._collections: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)
    
    def create_operations_map(self, name: str, strategy: CollectionStrategy = CollectionStrategy.HASH_MAP) -> OperationsMap:
        """Create a new operations map with the specified name and strategy."""
        with self._lock:
            if name in self._collections:
                raise ValueError(f"Collection '{name}' already exists")
            
            operations_map = OperationsMap(strategy)
            self._collections[name] = operations_map
            self._logger.info(f"Created operations map '{name}' with strategy {strategy.value}")
            return operations_map
    
    def create_identity_collection(self, name: str) -> IdentityCollection:
        """Create a new identity collection with the specified name."""
        with self._lock:
            if name in self._collections:
                raise ValueError(f"Collection '{name}' already exists")
            
            identity_collection = IdentityCollection()
            self._collections[name] = identity_collection
            self._logger.info(f"Created identity collection '{name}'")
            return identity_collection
    
    def create_connection_id_collection(self, name: str) -> ConnectionIdCollection:
        """Create a new connection ID collection with the specified name."""
        with self._lock:
            if name in self._collections:
                raise ValueError(f"Collection '{name}' already exists")
            
            connection_collection = ConnectionIdCollection()
            self._collections[name] = connection_collection
            self._logger.info(f"Created connection ID collection '{name}'")
            return connection_collection
    
    def create_query_id_collection(self, name: str) -> QueryIdCollection:
        """Create a new query ID collection with the specified name."""
        with self._lock:
            if name in self._collections:
                raise ValueError(f"Collection '{name}' already exists")
            
            query_collection = QueryIdCollection()
            self._collections[name] = query_collection
            self._logger.info(f"Created query ID collection '{name}'")
            return query_collection
    
    def create_concurrent_set(self, name: str) -> ConcurrentSet:
        """Create a new concurrent set with the specified name."""
        with self._lock:
            if name in self._collections:
                raise ValueError(f"Collection '{name}' already exists")
            
            concurrent_set = ConcurrentSet()
            self._collections[name] = concurrent_set
            self._logger.info(f"Created concurrent set '{name}'")
            return concurrent_set
    
    def create_lru_cache(self, name: str, max_size: int = 1000) -> LRUCache:
        """Create a new LRU cache with the specified name and size."""
        with self._lock:
            if name in self._collections:
                raise ValueError(f"Collection '{name}' already exists")
            
            lru_cache = LRUCache(max_size)
            self._collections[name] = lru_cache
            self._logger.info(f"Created LRU cache '{name}' with max size {max_size}")
            return lru_cache
    
    def get_collection(self, name: str) -> Optional[Any]:
        """Get a collection by name."""
        with self._lock:
            return self._collections.get(name)
    
    def remove_collection(self, name: str) -> bool:
        """Remove a collection by name. Returns True if removed."""
        with self._lock:
            if name in self._collections:
                del self._collections[name]
                self._logger.info(f"Removed collection '{name}'")
                return True
            return False
    
    def list_collections(self) -> List[str]:
        """Get a list of all collection names."""
        with self._lock:
            return list(self._collections.keys())
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all collections."""
        metrics = {}
        with self._lock:
            for name, collection in self._collections.items():
                if hasattr(collection, 'get_metrics'):
                    collection_metrics = collection.get_metrics()
                    if isinstance(collection_metrics, CollectionMetrics):
                        metrics[name] = collection_metrics.to_dict()
                    else:
                        metrics[name] = collection_metrics
        return metrics
    
    def clear_all(self) -> None:
        """Clear all collections."""
        with self._lock:
            for collection in self._collections.values():
                if hasattr(collection, 'clear'):
                    collection.clear()
            self._logger.info("Cleared all collections")


# Global collection manager instance
collection_manager = CollectionManager()


# Convenience functions for creating collections
def create_operations_map(name: str, strategy: CollectionStrategy = CollectionStrategy.HASH_MAP) -> OperationsMap:
    """Create a new operations map with the specified name and strategy."""
    return collection_manager.create_operations_map(name, strategy)


def create_identity_collection(name: str) -> IdentityCollection:
    """Create a new identity collection with the specified name."""
    return collection_manager.create_identity_collection(name)


def create_connection_id_collection(name: str) -> ConnectionIdCollection:
    """Create a new connection ID collection with the specified name."""
    return collection_manager.create_connection_id_collection(name)


def create_query_id_collection(name: str) -> QueryIdCollection:
    """Create a new query ID collection with the specified name."""
    return collection_manager.create_query_id_collection(name)


def create_concurrent_set(name: str) -> ConcurrentSet:
    """Create a new concurrent set with the specified name."""
    return collection_manager.create_concurrent_set(name)


def create_lru_cache(name: str, max_size: int = 1000) -> LRUCache:
    """Create a new LRU cache with the specified name and size."""
    return collection_manager.create_lru_cache(name, max_size)


def get_collection(name: str) -> Optional[Any]:
    """Get a collection by name."""
    return collection_manager.get_collection(name)


def get_all_metrics() -> Dict[str, Any]:
    """Get metrics for all collections."""
    return collection_manager.get_all_metrics() 