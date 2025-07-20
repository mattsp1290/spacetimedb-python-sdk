"""
Property-based tests for bounded cache implementations.

Uses hypothesis to generate test cases that verify cache behavior under
various conditions and edge cases.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, assume, example, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, Bundle

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

try:
    from spacetimedb_sdk.bounded_cache import BoundedCache
    from spacetimedb_sdk.connection.bounded_client_cache import BoundedClientCache
    HAS_CACHE = True
except ImportError:
    HAS_CACHE = False
    

# Skip tests if cache implementations not available
pytestmark = pytest.mark.skipif(not HAS_CACHE, reason="Cache implementations not available")


class TestBoundedCacheProperties:
    """Property-based tests for bounded cache behavior."""
    
    @given(st.integers(min_value=1, max_value=1000))
    def test_cache_never_exceeds_capacity(self, max_size):
        """Test that cache never exceeds its specified capacity."""
        cache = BoundedCache(max_size=max_size)
        
        # Add more items than capacity
        for i in range(max_size * 2):
            cache.put(f"key_{i}", f"value_{i}")
            
            # Cache should never exceed capacity
            assert len(cache) <= max_size
            assert cache.size() <= max_size
    
    @given(
        st.integers(min_value=1, max_value=100),
        st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=1000)
    )
    def test_cache_eviction_maintains_most_recent(self, max_size, keys):
        """Test that cache eviction preserves most recently accessed items."""
        assume(len(set(keys)) > max_size)  # Need more unique keys than capacity
        
        cache = BoundedCache(max_size=max_size)
        
        # Fill cache beyond capacity
        for i, key in enumerate(keys):
            cache.put(key, f"value_{i}")
        
        # The most recently added items should still be in cache
        recent_keys = list(dict.fromkeys(keys))[-max_size:]  # Last unique keys
        
        for key in recent_keys:
            assert cache.get(key) is not None, f"Recent key {key} was evicted"
    
    @given(
        st.integers(min_value=1, max_value=50),
        st.lists(
            st.tuples(st.text(min_size=1, max_size=10), st.text(min_size=1, max_size=20)),
            min_size=1,
            max_size=200
        )
    )
    def test_cache_get_put_consistency(self, max_size, key_value_pairs):
        """Test that get returns what was put (within capacity limits)."""
        cache = BoundedCache(max_size=max_size)
        
        # Track what should be in cache
        expected_items = {}
        
        for key, value in key_value_pairs:
            cache.put(key, value)
            expected_items[key] = value
            
            # Keep only the most recent items within capacity
            if len(expected_items) > max_size:
                # Remove oldest items (simplified LRU simulation)
                oldest_key = next(iter(expected_items))
                del expected_items[oldest_key]
        
        # Check that expected items are in cache
        for key, expected_value in expected_items.items():
            actual_value = cache.get(key)
            assert actual_value == expected_value, f"Cache inconsistency for key {key}"
    
    @given(
        st.integers(min_value=1, max_value=100),
        st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=500)
    )
    def test_cache_contains_consistency(self, max_size, keys):
        """Test that contains() is consistent with get()."""
        cache = BoundedCache(max_size=max_size)
        
        # Add items
        for key in keys:
            cache.put(key, f"value_for_{key}")
        
        # Check consistency between contains and get
        for key in set(keys):  # Check unique keys
            has_key = cache.contains(key) if hasattr(cache, 'contains') else (key in cache)
            get_result = cache.get(key)
            
            if has_key:
                assert get_result is not None, f"contains() says {key} exists but get() returns None"
            if get_result is not None:
                assert has_key, f"get() returns value for {key} but contains() says it doesn't exist"
    
    @given(
        st.integers(min_value=1, max_value=50),
        st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=200)
    )
    def test_cache_clear_empties_cache(self, max_size, keys):
        """Test that clear() completely empties the cache."""
        cache = BoundedCache(max_size=max_size)
        
        # Fill cache
        for key in keys:
            cache.put(key, f"value_{key}")
        
        # Clear cache
        if hasattr(cache, 'clear'):
            cache.clear()
        
            # Cache should be empty
            assert len(cache) == 0
            assert cache.size() == 0
            
            # No keys should be found
            for key in set(keys):
                assert cache.get(key) is None
    
    @given(
        st.integers(min_value=2, max_value=100),
        st.lists(st.text(min_size=1, max_size=10), min_size=10, max_size=300)
    )
    def test_cache_lru_behavior(self, max_size, keys):
        """Test that cache follows LRU (Least Recently Used) eviction policy."""
        cache = BoundedCache(max_size=max_size)
        
        # Fill cache to capacity
        unique_keys = list(dict.fromkeys(keys))[:max_size]
        for key in unique_keys:
            cache.put(key, f"value_{key}")
        
        # Access first key to make it most recently used
        first_key = unique_keys[0]
        cache.get(first_key)
        
        # Add one more item (should evict second key, not first)
        new_key = "new_key_not_in_original"
        cache.put(new_key, "new_value")
        
        # First key should still be in cache (was recently accessed)
        assert cache.get(first_key) is not None, "LRU eviction removed recently accessed key"
        
        # Second key should be evicted (was least recently used)
        if len(unique_keys) > 1:
            second_key = unique_keys[1]
            assert cache.get(second_key) is None, "LRU eviction failed to remove least recently used key"


class CacheStateMachine(RuleBasedStateMachine):
    """State machine for testing cache behavior."""
    
    def __init__(self):
        super().__init__()
        self.cache = BoundedCache(max_size=10)
        self.model = {}  # Our model of what should be in cache
    
    keys = Bundle('keys')
    values = Bundle('values')
    
    @rule(target=keys, key=st.text(min_size=1, max_size=10))
    def add_key(self, key):
        return key
    
    @rule(target=values, value=st.text(min_size=1, max_size=20))
    def add_value(self, value):
        return value
    
    @rule(key=keys, value=values)
    def put_item(self, key, value):
        """Put an item into the cache."""
        self.cache.put(key, value)
        self.model[key] = value
        
        # Keep model within capacity (simplified LRU)
        if len(self.model) > 10:
            # Remove oldest item
            oldest_key = next(iter(self.model))
            del self.model[oldest_key]
    
    @rule(key=keys)
    def get_item(self, key):
        """Get an item from the cache."""
        cache_result = self.cache.get(key)
        model_result = self.model.get(key)
        
        # Results should match
        assert cache_result == model_result, f"Cache/model mismatch for {key}"
    
    @rule(key=keys)
    def check_contains(self, key):
        """Check if cache contains a key."""
        cache_has = self.cache.contains(key) if hasattr(self.cache, 'contains') else (key in self.cache)
        model_has = key in self.model
        
        # Should be consistent
        assert cache_has == model_has, f"Contains inconsistency for {key}"
    
    @rule()
    def clear_cache(self):
        """Clear the cache."""
        if hasattr(self.cache, 'clear'):
            self.cache.clear()
            self.model.clear()
    
    @invariant()
    def cache_size_invariant(self):
        """Cache should never exceed capacity."""
        assert len(self.cache) <= 10
        assert self.cache.size() <= 10
    
    @invariant()
    def cache_model_size_consistency(self):
        """Cache and model should have same size."""
        assert len(self.cache) == len(self.model)


class TestBoundedClientCacheProperties:
    """Property-based tests for bounded client cache."""
    
    @given(
        st.integers(min_value=1, max_value=100),
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=20),  # client_id
                st.text(min_size=1, max_size=30),  # data
            ),
            min_size=1,
            max_size=500
        )
    )
    def test_client_cache_capacity_limits(self, max_clients, client_data):
        """Test that client cache respects capacity limits."""
        cache = BoundedClientCache(max_clients=max_clients)
        
        # Add client data
        for client_id, data in client_data:
            cache.add_client(client_id, data)
            
            # Should never exceed capacity
            assert len(cache) <= max_clients
            assert cache.client_count() <= max_clients
    
    @given(
        st.integers(min_value=1, max_value=50),
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=15),  # client_id
                st.dictionaries(
                    st.text(min_size=1, max_size=10),  # key
                    st.text(min_size=1, max_size=20),  # value
                    min_size=1,
                    max_size=10
                )
            ),
            min_size=1,
            max_size=200
        )
    )
    def test_client_data_consistency(self, max_clients, client_data_pairs):
        """Test that client data is stored and retrieved consistently."""
        cache = BoundedClientCache(max_clients=max_clients)
        
        # Track expected data
        expected_clients = {}
        
        for client_id, data in client_data_pairs:
            cache.add_client(client_id, data)
            expected_clients[client_id] = data
            
            # Keep only recent clients within capacity
            if len(expected_clients) > max_clients:
                # Remove oldest (simplified)
                oldest_client = next(iter(expected_clients))
                del expected_clients[oldest_client]
        
        # Verify expected clients are present
        for client_id, expected_data in expected_clients.items():
            actual_data = cache.get_client(client_id)
            assert actual_data == expected_data, f"Client data mismatch for {client_id}"
    
    @given(
        st.integers(min_value=1, max_value=30),
        st.lists(st.text(min_size=1, max_size=15), min_size=1, max_size=100)
    )
    def test_client_removal_consistency(self, max_clients, client_ids):
        """Test that client removal works consistently."""
        cache = BoundedClientCache(max_clients=max_clients)
        
        # Add clients
        for client_id in client_ids:
            cache.add_client(client_id, f"data_for_{client_id}")
        
        # Remove half of the clients
        clients_to_remove = set(client_ids[::2])  # Every second client
        
        for client_id in clients_to_remove:
            if hasattr(cache, 'remove_client'):
                cache.remove_client(client_id)
        
        # Verify removed clients are gone
        for client_id in clients_to_remove:
            assert cache.get_client(client_id) is None, f"Client {client_id} not removed"
        
        # Verify remaining clients still exist
        remaining_clients = set(client_ids) - clients_to_remove
        for client_id in remaining_clients:
            if len(cache) > 0:  # Only check if cache not empty
                data = cache.get_client(client_id)
                # Data might be None if client was evicted due to capacity
                if data is not None:
                    assert data == f"data_for_{client_id}", f"Remaining client data corrupted"


# Example-based tests for edge cases
class TestCacheEdgeCases:
    """Test specific edge cases found through property-based testing."""
    
    @example(0)
    def test_empty_cache_operations(self):
        """Test operations on empty cache."""
        cache = BoundedCache(max_size=10)
        
        # Empty cache should handle all operations gracefully
        assert cache.get("nonexistent") is None
        assert len(cache) == 0
        assert cache.size() == 0
        
        if hasattr(cache, 'contains'):
            assert not cache.contains("nonexistent")
        
        if hasattr(cache, 'clear'):
            cache.clear()  # Should not crash
    
    @example(0)
    def test_single_item_cache(self):
        """Test cache with capacity of 1."""
        cache = BoundedCache(max_size=1)
        
        # Add first item
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"
        assert len(cache) == 1
        
        # Add second item (should evict first)
        cache.put("key2", "value2")
        assert cache.get("key2") == "value2"
        assert cache.get("key1") is None
        assert len(cache) == 1
    
    @example(0)
    def test_duplicate_keys(self):
        """Test behavior with duplicate keys."""
        cache = BoundedCache(max_size=5)
        
        # Add same key multiple times
        cache.put("key", "value1")
        cache.put("key", "value2")
        cache.put("key", "value3")
        
        # Should have latest value
        assert cache.get("key") == "value3"
        assert len(cache) == 1  # Only one entry for duplicate key


# Run state machine tests
TestCacheStateMachine = CacheStateMachine.TestCase