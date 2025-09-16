"""
Bounded Client Cache for Connection Management

This module provides a client-specific cache implementation for managing
client connections and associated data with bounded storage and LRU eviction.
"""

from typing import Dict, Optional, Any
from collections import OrderedDict


class BoundedClientCache:
    """
    Client cache with bounded storage for managing client connections.
    
    This cache is designed for the property-based tests and provides:
    - Client-specific data storage with capacity limits
    - LRU eviction when capacity is exceeded
    - Methods for adding, retrieving, and removing clients
    """
    
    def __init__(self, max_clients: int):
        if max_clients <= 0:
            raise ValueError("max_clients must be positive")
        
        self.max_clients = max_clients
        self._clients: OrderedDict[str, Any] = OrderedDict()
    
    def add_client(self, client_id: str, data: Any) -> None:
        """Add or update a client with associated data."""
        if client_id in self._clients:
            # Update existing client - move to end (most recent)
            del self._clients[client_id]
        elif len(self._clients) >= self.max_clients:
            # Evict least recently used client (first item)
            self._clients.popitem(last=False)
        
        # Add/update the client at the end (most recent)
        self._clients[client_id] = data
    
    def get_client(self, client_id: str) -> Optional[Any]:
        """Get client data by ID. Returns None if not found."""
        if client_id not in self._clients:
            return None
        
        # Move to end to mark as recently accessed
        data = self._clients[client_id]
        del self._clients[client_id]
        self._clients[client_id] = data
        return data
    
    def remove_client(self, client_id: str) -> bool:
        """Remove a client from the cache. Returns True if removed, False if not found."""
        if client_id in self._clients:
            del self._clients[client_id]
            return True
        return False
    
    def contains_client(self, client_id: str) -> bool:
        """Check if cache contains the client."""
        return client_id in self._clients
    
    def __contains__(self, client_id: str) -> bool:
        """Check if cache contains the client (Python magic method)."""
        return self.contains_client(client_id)
    
    def client_count(self) -> int:
        """Get the current number of clients in the cache."""
        return len(self._clients)
    
    def __len__(self) -> int:
        """Get the current number of clients in the cache (Python magic method)."""
        return len(self._clients)
    
    def clear(self) -> None:
        """Clear all clients from the cache."""
        self._clients.clear()
    
    def get_client_ids(self):
        """Get all client IDs in cache (in LRU order, oldest first)."""
        return list(self._clients.keys())
    
    def get_all_clients(self):
        """Get all client data in cache (in LRU order, oldest first)."""
        return list(self._clients.values())