"""
Bounded Client Cache with Context Pooling for SpacetimeDB SDK

Implements efficient caching and pooling of EventContext objects for better memory management.
This combines the memory-safe bounded collections with context pooling capabilities.
"""

import logging
from typing import Dict, Optional, Any

from .bounded_cache import BoundedClientCache as _BoundedClientCache, BoundedTableCache
from .context_pool import ContextPool, ContextConfiguration
from .memory_management import (
    MemoryAccountant, get_global_memory_accountant,
    DEFAULT_MAX_CACHE_SIZE
)
from .monitoring import get_global_monitor

logger = logging.getLogger(__name__)


class BoundedClientCache:
    """
    Combined client cache with bounded storage for tables/reducers and context pooling.
    
    Features:
    - Bounded table caches with memory management
    - Bounded reducer cache
    - Context pooling for efficient memory usage
    - Client caching with TTL
    - Memory accounting and statistics
    """
    
    def __init__(
        self,
        autogen_package=None,
        max_cache_size: int = DEFAULT_MAX_CACHE_SIZE,
        memory_accountant: Optional[MemoryAccountant] = None,
        max_clients: int = 100,
        context_pool_size: int = 200,
        ttl_seconds: float = 300.0
    ):
        # Create the underlying cache with the specified parameters
        self._cache = _BoundedClientCache(
            autogen_package=autogen_package,
            max_cache_size=max_cache_size,
            memory_accountant=memory_accountant,
            max_clients=max_clients,
            ttl_seconds=ttl_seconds
        )
        
        # Context pool for efficient EventContext management
        self.context_pool = ContextPool(
            min_size=context_pool_size // 4,
            max_size=context_pool_size
        )
        
        self.logger = logging.getLogger(f"{__name__}.BoundedClientCache")
    
    # Delegate all cache methods to the underlying cache
    def get_table_cache(self, table_name: str) -> Optional[BoundedTableCache]:
        """Get table cache by name."""
        return self._cache.get_table_cache(table_name)
    
    def decode(self, table_name: str, value: Any) -> Optional[Any]:
        """Decode a value for a specific table."""
        return self._cache.decode(table_name, value)
    
    def set_entry(self, table_name: str, key: Any, value: Any) -> bool:
        """Set an entry in a table cache."""
        result = self._cache.set_entry(table_name, key, value)
        
        # Record cache write
        monitor = get_global_monitor()
        monitor.record_cache_access(hit=True, cache_name=f"{table_name}_write")
        
        return result
    
    def set_entry_decoded(self, table_name: str, key: Any, value: Any) -> bool:
        """Set an already decoded entry in a table cache."""
        return self._cache.set_entry_decoded(table_name, key, value)
    
    def delete_entry(self, table_name: str, key: Any) -> bool:
        """Delete an entry from a table cache."""
        return self._cache.delete_entry(table_name, key)
    
    def get_entry(self, table_name: str, key: Any) -> Optional[Any]:
        """Get an entry from a table cache."""
        result = self._cache.get_entry(table_name, key)
        
        # Record cache access
        monitor = get_global_monitor()
        monitor.record_cache_access(hit=(result is not None), cache_name=table_name)
        
        return result
    
    def get_client(self, client_id: str) -> Optional[Any]:
        """Get a client from the cache."""
        return self._cache.get_client(client_id)
    
    def put_client(self, client_id: str, client: Any) -> None:
        """Put a client in the cache."""
        self._cache.put_client(client_id, client)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics including context pool metrics."""
        stats = self._cache.get_cache_stats()
        stats['context_pool'] = self.context_pool.get_pool_metrics()
        return stats
    
    def clear_all_caches(self) -> None:
        """Clear all caches."""
        self._cache.clear_all_caches()
    
    def cleanup_memory_pressure(self) -> Dict[str, int]:
        """Perform cleanup when under memory pressure."""
        return self._cache.cleanup_memory_pressure()
    
    def shutdown(self) -> None:
        """Shutdown the cache and cleanup resources."""
        self.context_pool.cleanup()
        self._cache.shutdown()
        self.logger.info("BoundedClientCache shutdown complete")
    
    # Expose cache properties for backward compatibility
    @property
    def tables(self):
        """Access to table caches."""
        return self._cache.tables
    
    @property
    def reducer_cache(self):
        """Access to reducer cache."""
        return self._cache.reducer_cache
    
    @property
    def memory_accountant(self):
        """Access to memory accountant."""
        return self._cache.memory_accountant


# For backward compatibility, provide the same interface as the original client_cache
ClientCache = BoundedClientCache
TableCache = BoundedTableCache

# Re-export from bounded_cache for convenience
from .bounded_cache import snake_to_camel

# Re-export from context_pool for convenience
__all__ = [
    'BoundedClientCache',
    'ClientCache', 
    'TableCache',
    'ContextPool',
    'ContextConfiguration',
    'snake_to_camel'
]