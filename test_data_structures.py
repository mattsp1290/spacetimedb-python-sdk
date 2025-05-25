"""
Comprehensive tests for SpacetimeDB specialized data structures.

Tests all data structures including OperationsMap, specialized collections,
concurrent access patterns, and performance monitoring.
"""

import pytest
import threading
import time
from typing import Any, Dict, List
from unittest.mock import Mock, patch

from src.spacetimedb_sdk.data_structures import (
    OperationsMap, IdentityCollection, ConnectionIdCollection, QueryIdCollection,
    ConcurrentSet, LRUCache, CollectionManager, CollectionStrategy,
    CollectionMetrics, Equalable, collection_manager,
    create_operations_map, create_identity_collection, create_connection_id_collection,
    create_query_id_collection, create_concurrent_set, create_lru_cache,
    get_collection, get_all_metrics
)
from src.spacetimedb_sdk.protocol import Identity, ConnectionId, QueryId
from src.spacetimedb_sdk.time_utils import EnhancedTimestamp


class CustomEqualableObject:
    """Test object that implements custom equality."""
    
    def __init__(self, value: str, custom_id: int):
        self.value = value
        self.custom_id = custom_id
    
    def is_equal(self, other: Any) -> bool:
        """Custom equality based on custom_id only."""
        if isinstance(other, CustomEqualableObject):
            return self.custom_id == other.custom_id
        return False
    
    def __str__(self):
        return f"CustomObject({self.value}, {self.custom_id})"


class TestCollectionMetrics:
    """Test collection metrics functionality."""
    
    def test_metrics_initialization(self):
        """Test metrics are initialized correctly."""
        metrics = CollectionMetrics()
        assert metrics.operation_count == 0
        assert metrics.total_time == 0.0
        assert metrics.average_time == 0.0
        assert metrics.max_time == 0.0
        assert metrics.min_time == float('inf')
        assert metrics.memory_usage == 0
        assert metrics.collision_count == 0
    
    def test_metrics_update(self):
        """Test metrics update correctly."""
        metrics = CollectionMetrics()
        
        # First operation
        metrics.update(0.1)
        assert metrics.operation_count == 1
        assert abs(metrics.total_time - 0.1) < 1e-10
        assert abs(metrics.average_time - 0.1) < 1e-10
        assert abs(metrics.max_time - 0.1) < 1e-10
        assert abs(metrics.min_time - 0.1) < 1e-10
        
        # Second operation
        metrics.update(0.2)
        assert metrics.operation_count == 2
        assert abs(metrics.total_time - 0.3) < 1e-10
        assert abs(metrics.average_time - 0.15) < 1e-10
        assert abs(metrics.max_time - 0.2) < 1e-10
        assert abs(metrics.min_time - 0.1) < 1e-10
    
    def test_metrics_to_dict(self):
        """Test metrics conversion to dictionary."""
        metrics = CollectionMetrics()
        metrics.update(0.1)
        
        result = metrics.to_dict()
        expected_keys = {
            "operation_count", "total_time", "average_time",
            "max_time", "min_time", "memory_usage", "collision_count"
        }
        assert set(result.keys()) == expected_keys
        assert result["operation_count"] == 1
        assert result["min_time"] == 0.1


class TestOperationsMap:
    """Test OperationsMap functionality."""
    
    def test_basic_operations(self):
        """Test basic map operations."""
        ops_map = OperationsMap[str, int]()
        
        # Test set and get
        ops_map.set("key1", 100)
        assert ops_map.get("key1") == 100
        assert ops_map.has("key1")
        assert ops_map.size() == 1
        
        # Test get with default
        assert ops_map.get("nonexistent", 42) == 42
        
        # Test delete
        assert ops_map.delete("key1")
        assert not ops_map.has("key1")
        assert ops_map.size() == 0
        assert not ops_map.delete("key1")  # Already deleted
    
    def test_custom_equality(self):
        """Test custom equality checking."""
        ops_map = OperationsMap[CustomEqualableObject, str]()
        
        obj1 = CustomEqualableObject("first", 1)
        obj2 = CustomEqualableObject("second", 1)  # Same custom_id
        obj3 = CustomEqualableObject("third", 2)   # Different custom_id
        
        # Set with obj1
        ops_map.set(obj1, "value1")
        
        # obj2 should be considered equal to obj1
        assert ops_map.has(obj2)
        assert ops_map.get(obj2) == "value1"
        
        # obj3 should not be equal
        assert not ops_map.has(obj3)
        
        # Update with obj2 (should update same entry)
        ops_map.set(obj2, "value2")
        assert ops_map.size() == 1
        assert ops_map.get(obj1) == "value2"
    
    def test_different_strategies(self):
        """Test different collection strategies."""
        # Hash map strategy
        hash_map = OperationsMap[str, int](CollectionStrategy.HASH_MAP)
        hash_map.set("key", 1)
        assert hash_map.get("key") == 1
        
        # Ordered map strategy
        ordered_map = OperationsMap[str, int](CollectionStrategy.ORDERED_MAP)
        ordered_map.set("key", 2)
        assert ordered_map.get("key") == 2
        
        # Concurrent map strategy
        concurrent_map = OperationsMap[str, int](CollectionStrategy.CONCURRENT_MAP)
        concurrent_map.set("key", 3)
        assert concurrent_map.get("key") == 3
    
    def test_iteration(self):
        """Test map iteration."""
        ops_map = OperationsMap[str, int]()
        
        # Add some data
        ops_map.set("key1", 1)
        ops_map.set("key2", 2)
        ops_map.set("key3", 3)
        
        # Test keys iteration
        keys = list(ops_map.keys())
        assert len(keys) == 3
        assert set(keys) == {"key1", "key2", "key3"}
        
        # Test values iteration
        values = list(ops_map.values())
        assert len(values) == 3
        assert set(values) == {1, 2, 3}
        
        # Test items iteration
        items = list(ops_map.items())
        assert len(items) == 3
        assert set(items) == {("key1", 1), ("key2", 2), ("key3", 3)}
    
    def test_dict_like_interface(self):
        """Test dictionary-like interface."""
        ops_map = OperationsMap[str, int]()
        
        # Test __setitem__ and __getitem__
        ops_map["key1"] = 100
        assert ops_map["key1"] == 100
        
        # Test __contains__
        assert "key1" in ops_map
        assert "nonexistent" not in ops_map
        
        # Test __len__
        assert len(ops_map) == 1
        
        # Test __delitem__
        del ops_map["key1"]
        assert len(ops_map) == 0
        
        # Test KeyError
        with pytest.raises(KeyError):
            _ = ops_map["nonexistent"]
        
        with pytest.raises(KeyError):
            del ops_map["nonexistent"]
    
    def test_metrics_tracking(self):
        """Test metrics are tracked correctly."""
        ops_map = OperationsMap[str, int]()
        
        # Perform some operations
        ops_map.set("key1", 1)
        ops_map.get("key1")
        ops_map.delete("key1")
        
        metrics = ops_map.get_metrics()
        assert metrics.operation_count >= 3
        assert metrics.total_time > 0
        assert metrics.average_time > 0


class TestIdentityCollection:
    """Test IdentityCollection functionality."""
    
    def test_basic_operations(self):
        """Test basic identity collection operations."""
        collection = IdentityCollection()
        identity1 = Identity(b"identity1_bytes_32_chars_long!")
        identity2 = Identity(b"identity2_bytes_32_chars_long!")
        
        # Test add
        assert collection.add(identity1)
        assert not collection.add(identity1)  # Duplicate
        assert collection.size() == 1
        
        # Test contains
        assert collection.contains(identity1)
        assert not collection.contains(identity2)
        
        # Test find by hex
        hex_str = identity1.to_hex()
        found = collection.find_by_hex(hex_str)
        assert found == identity1
        
        # Test remove
        assert collection.remove(identity1)
        assert not collection.remove(identity1)  # Already removed
        assert collection.size() == 0
    
    def test_collection_interface(self):
        """Test collection-like interface."""
        collection = IdentityCollection()
        identity = Identity(b"identity1_bytes_32_chars_long!")
        
        collection.add(identity)
        
        # Test __len__
        assert len(collection) == 1
        
        # Test __contains__
        assert identity in collection
        
        # Test __iter__
        identities = list(collection)
        assert len(identities) == 1
        assert identities[0] == identity
        
        # Test to_list
        identity_list = collection.to_list()
        assert identity_list == [identity]
    
    def test_metrics_tracking(self):
        """Test metrics are tracked correctly."""
        collection = IdentityCollection()
        identity = Identity(b"identity1_bytes_32_chars_long!")
        
        collection.add(identity)
        collection.remove(identity)
        
        metrics = collection.get_metrics()
        assert metrics.operation_count >= 2
        assert metrics.total_time > 0


class TestConnectionIdCollection:
    """Test ConnectionIdCollection functionality."""
    
    def test_basic_operations(self):
        """Test basic connection ID collection operations."""
        collection = ConnectionIdCollection()
        conn_id1 = ConnectionId(b"connection_1_data")
        conn_id2 = ConnectionId(b"connection_2_data")
        metadata = {"client": "test", "version": "1.0"}
        
        # Test add with metadata
        assert collection.add(conn_id1, metadata)
        assert not collection.add(conn_id1)  # Duplicate
        assert collection.size() == 1
        
        # Test contains
        assert collection.contains(conn_id1)
        assert not collection.contains(conn_id2)
        
        # Test find by hex
        found_conn = collection.find_by_hex(conn_id1.to_hex())
        assert found_conn == conn_id1
        assert collection.find_by_hex("nonexistent") is None
        
        # Test metadata operations
        retrieved_metadata = collection.get_metadata(conn_id1)
        assert retrieved_metadata == metadata
        
        new_metadata = {"updated": True}
        assert collection.set_metadata(conn_id1, new_metadata)
        assert collection.get_metadata(conn_id1) == new_metadata
        
        # Test remove
        assert collection.remove(conn_id1)
        assert collection.size() == 0
    
    def test_collection_interface(self):
        """Test collection-like interface."""
        collection = ConnectionIdCollection()
        conn_id = ConnectionId(b"connection_data")
        
        collection.add(conn_id)
        
        # Test __len__
        assert len(collection) == 1
        
        # Test __contains__
        assert conn_id in collection
        
        # Test __iter__
        conn_ids = list(collection)
        assert len(conn_ids) == 1
        assert conn_ids[0] == conn_id


class TestQueryIdCollection:
    """Test QueryIdCollection functionality."""
    
    def test_basic_operations(self):
        """Test basic query ID collection operations."""
        collection = QueryIdCollection()
        query_id1 = QueryId(1)
        query_id2 = QueryId(2)
        metadata = {"query": "SELECT * FROM users", "timeout": 30}
        
        # Test add with metadata
        assert collection.add(query_id1, metadata)
        assert not collection.add(query_id1)  # Duplicate
        assert collection.size() == 1
        
        # Test contains
        assert collection.contains(query_id1)
        assert not collection.contains(query_id2)
        
        # Test find by ID
        found = collection.find_by_id(1)
        assert found == query_id1
        
        # Test metadata and timestamp
        retrieved_metadata = collection.get_metadata(query_id1)
        assert retrieved_metadata == metadata
        
        timestamp = collection.get_timestamp(query_id1)
        assert timestamp is not None
        assert isinstance(timestamp, float)
    
    def test_age_based_operations(self):
        """Test age-based query operations."""
        collection = QueryIdCollection()
        
        # Add some queries
        old_query = QueryId(1)
        new_query = QueryId(2)
        
        collection.add(old_query)
        
        # Simulate time passing by manually setting an old timestamp
        old_timestamp = time.time() - 2.0  # 2 seconds ago
        collection._query_timestamps[1] = old_timestamp
        
        collection.add(new_query)
        
        # Find old queries (older than 1 second)
        old_queries = collection.find_by_age(1.0)
        assert len(old_queries) == 1
        assert old_queries[0] == old_query
        
        # Cleanup old queries
        removed_count = collection.cleanup_old_queries(1.0)
        assert removed_count == 1
        assert collection.size() == 1
        assert collection.contains(new_query)
        assert not collection.contains(old_query)


class TestConcurrentSet:
    """Test ConcurrentSet functionality."""
    
    def test_basic_operations(self):
        """Test basic set operations."""
        concurrent_set = ConcurrentSet[str]()
        
        # Test add
        assert concurrent_set.add("item1")
        assert not concurrent_set.add("item1")  # Duplicate
        assert concurrent_set.size() == 1
        
        # Test contains
        assert concurrent_set.contains("item1")
        assert not concurrent_set.contains("item2")
        
        # Test remove
        assert concurrent_set.remove("item1")
        assert not concurrent_set.remove("item1")  # Already removed
        assert concurrent_set.size() == 0
    
    def test_set_operations(self):
        """Test set mathematical operations."""
        set1 = ConcurrentSet[str]()
        set2 = ConcurrentSet[str]()
        
        # Add items to sets
        set1.add("a")
        set1.add("b")
        set1.add("c")
        
        set2.add("b")
        set2.add("c")
        set2.add("d")
        
        # Test union
        union_set = set1.union(set2)
        union_items = set(union_set.to_list())
        assert union_items == {"a", "b", "c", "d"}
        
        # Test intersection
        intersection_set = set1.intersection(set2)
        intersection_items = set(intersection_set.to_list())
        assert intersection_items == {"b", "c"}
        
        # Test difference
        difference_set = set1.difference(set2)
        difference_items = set(difference_set.to_list())
        assert difference_items == {"a"}
    
    def test_concurrent_access(self):
        """Test concurrent access to the set."""
        concurrent_set = ConcurrentSet[int]()
        results = []
        
        def add_items(start: int, count: int):
            """Add items to the set."""
            for i in range(start, start + count):
                result = concurrent_set.add(i)
                results.append(result)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_items, args=(i * 10, 10))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert concurrent_set.size() == 50
        assert all(results)  # All additions should succeed (no duplicates)


class TestLRUCache:
    """Test LRUCache functionality."""
    
    def test_basic_operations(self):
        """Test basic cache operations."""
        cache = LRUCache[str, int](max_size=3)
        
        # Test set and get
        cache.set("key1", 1)
        cache.set("key2", 2)
        cache.set("key3", 3)
        
        assert cache.get("key1") == 1
        assert cache.get("key2") == 2
        assert cache.get("key3") == 3
        assert cache.size() == 3
        
        # Test eviction
        cache.set("key4", 4)  # Should evict key1 (least recently used)
        assert cache.size() == 3
        assert cache.get("key1") is None
        assert cache.get("key4") == 4
    
    def test_lru_behavior(self):
        """Test LRU eviction behavior."""
        cache = LRUCache[str, int](max_size=2)
        
        cache.set("key1", 1)
        cache.set("key2", 2)
        
        # Access key1 to make it most recently used
        cache.get("key1")
        
        # Add key3, should evict key2
        cache.set("key3", 3)
        
        assert cache.get("key1") == 1
        assert cache.get("key2") is None
        assert cache.get("key3") == 3
    
    def test_hit_ratio_tracking(self):
        """Test hit ratio tracking."""
        cache = LRUCache[str, int](max_size=2)
        
        cache.set("key1", 1)
        
        # 1 hit, 0 misses
        cache.get("key1")
        assert cache.get_hit_ratio() == 1.0
        
        # 1 hit, 1 miss
        cache.get("nonexistent")
        assert cache.get_hit_ratio() == 0.5
        
        # Test metrics
        metrics = cache.get_metrics()
        assert metrics["hit_count"] == 1
        assert metrics["miss_count"] == 1
        assert metrics["hit_ratio"] == 0.5
        assert metrics["current_size"] == 1
        assert metrics["max_size"] == 2
    
    def test_dict_like_interface(self):
        """Test dictionary-like interface."""
        cache = LRUCache[str, int](max_size=2)
        
        # Test __setitem__ and __getitem__
        cache["key1"] = 100
        assert cache["key1"] == 100
        
        # Test __contains__
        assert "key1" in cache
        assert "nonexistent" not in cache
        
        # Test __len__
        assert len(cache) == 1


class TestCollectionManager:
    """Test CollectionManager functionality."""
    
    def test_create_collections(self):
        """Test creating different types of collections."""
        manager = CollectionManager()
        
        # Test operations map creation
        ops_map = manager.create_operations_map("test_ops", CollectionStrategy.HASH_MAP)
        assert isinstance(ops_map, OperationsMap)
        
        # Test identity collection creation
        identity_coll = manager.create_identity_collection("test_identities")
        assert isinstance(identity_coll, IdentityCollection)
        
        # Test connection ID collection creation
        conn_coll = manager.create_connection_id_collection("test_connections")
        assert isinstance(conn_coll, ConnectionIdCollection)
        
        # Test query ID collection creation
        query_coll = manager.create_query_id_collection("test_queries")
        assert isinstance(query_coll, QueryIdCollection)
        
        # Test concurrent set creation
        concurrent_set = manager.create_concurrent_set("test_set")
        assert isinstance(concurrent_set, ConcurrentSet)
        
        # Test LRU cache creation
        lru_cache = manager.create_lru_cache("test_cache", 100)
        assert isinstance(lru_cache, LRUCache)
    
    def test_collection_management(self):
        """Test collection management operations."""
        manager = CollectionManager()
        
        # Create a collection
        ops_map = manager.create_operations_map("test_map")
        
        # Test duplicate creation fails
        with pytest.raises(ValueError, match="already exists"):
            manager.create_operations_map("test_map")
        
        # Test get collection
        retrieved = manager.get_collection("test_map")
        assert retrieved is ops_map
        assert manager.get_collection("nonexistent") is None
        
        # Test list collections
        collections = manager.list_collections()
        assert "test_map" in collections
        
        # Test remove collection
        assert manager.remove_collection("test_map")
        assert not manager.remove_collection("test_map")  # Already removed
        assert manager.get_collection("test_map") is None
    
    def test_metrics_collection(self):
        """Test metrics collection from all collections."""
        manager = CollectionManager()
        
        # Create collections and perform operations
        ops_map = manager.create_operations_map("test_ops")
        ops_map.set("key", "value")
        
        identity_coll = manager.create_identity_collection("test_identities")
        identity = Identity(b"identity1_bytes_32_chars_long!")
        identity_coll.add(identity)
        
        # Get all metrics
        all_metrics = manager.get_all_metrics()
        assert "test_ops" in all_metrics
        assert "test_identities" in all_metrics
        
        # Check metrics structure
        ops_metrics = all_metrics["test_ops"]
        assert "operation_count" in ops_metrics
        assert ops_metrics["operation_count"] >= 1
    
    def test_clear_all(self):
        """Test clearing all collections."""
        manager = CollectionManager()
        
        # Create and populate collections
        ops_map = manager.create_operations_map("test_ops")
        ops_map.set("key", "value")
        
        identity_coll = manager.create_identity_collection("test_identities")
        identity = Identity(b"identity1_bytes_32_chars_long!")
        identity_coll.add(identity)
        
        # Clear all
        manager.clear_all()
        
        # Check collections are empty
        assert ops_map.size() == 0
        assert identity_coll.size() == 0


class TestConvenienceFunctions:
    """Test global convenience functions."""
    
    def test_convenience_functions(self):
        """Test all convenience functions work correctly."""
        # Clean up any existing collections
        collection_manager.clear_all()
        for name in collection_manager.list_collections():
            collection_manager.remove_collection(name)
        
        # Test create functions
        ops_map = create_operations_map("conv_ops")
        assert isinstance(ops_map, OperationsMap)
        
        identity_coll = create_identity_collection("conv_identities")
        assert isinstance(identity_coll, IdentityCollection)
        
        conn_coll = create_connection_id_collection("conv_connections")
        assert isinstance(conn_coll, ConnectionIdCollection)
        
        query_coll = create_query_id_collection("conv_queries")
        assert isinstance(query_coll, QueryIdCollection)
        
        concurrent_set = create_concurrent_set("conv_set")
        assert isinstance(concurrent_set, ConcurrentSet)
        
        lru_cache = create_lru_cache("conv_cache", 50)
        assert isinstance(lru_cache, LRUCache)
        
        # Test get function
        retrieved_ops = get_collection("conv_ops")
        assert retrieved_ops is ops_map
        
        # Test metrics function
        all_metrics = get_all_metrics()
        assert len(all_metrics) >= 6  # At least the collections we created


class TestPerformanceAndConcurrency:
    """Test performance and concurrency aspects."""
    
    def test_operations_map_performance(self):
        """Test OperationsMap performance with many operations."""
        ops_map = OperationsMap[str, int]()
        
        # Perform many operations
        start_time = time.perf_counter()
        for i in range(1000):
            ops_map.set(f"key_{i}", i)
        
        for i in range(1000):
            value = ops_map.get(f"key_{i}")
            assert value == i
        
        end_time = time.perf_counter()
        operation_time = end_time - start_time
        
        # Should complete reasonably quickly
        assert operation_time < 1.0  # Less than 1 second
        
        # Check metrics
        metrics = ops_map.get_metrics()
        assert metrics.operation_count >= 2000
        assert metrics.average_time > 0
    
    def test_concurrent_operations_map_access(self):
        """Test concurrent access to OperationsMap."""
        ops_map = OperationsMap[str, int]()
        errors = []
        
        def worker(worker_id: int):
            """Worker function for concurrent testing."""
            try:
                for i in range(100):
                    key = f"worker_{worker_id}_key_{i}"
                    ops_map.set(key, worker_id * 1000 + i)
                    value = ops_map.get(key)
                    assert value == worker_id * 1000 + i
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for worker_id in range(10):
            thread = threading.Thread(target=worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check for errors
        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        
        # Check final state
        assert ops_map.size() == 1000  # 10 workers * 100 keys each
    
    def test_memory_efficiency(self):
        """Test memory efficiency of collections."""
        # This is a basic test - in a real scenario you'd use memory profiling
        ops_map = OperationsMap[str, str]()
        
        # Add many items
        for i in range(10000):
            ops_map.set(f"key_{i:06d}", f"value_{i:06d}")
        
        assert ops_map.size() == 10000
        
        # Clear and check
        ops_map.clear()
        assert ops_map.size() == 0
        assert ops_map.is_empty()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 