"""
Memory management utilities for refactoring tests.
"""

class BoundedDict:
    """A dictionary with bounded size for testing."""
    
    def __init__(self, max_size=None, memory_accountant=None):
        self._dict = {}
        self.max_size = max_size
        self.memory_accountant = memory_accountant
    
    def get(self, key):
        return self._dict.get(key)
    
    def set(self, key, value):
        self._dict[key] = value
    
    def delete(self, key):
        self._dict.pop(key, None)
    
    def items(self):
        return self._dict.items()
    
    def keys(self):
        return self._dict.keys()
    
    def values(self):
        return self._dict.values()
    
    def clear(self):
        self._dict.clear()
    
    def __len__(self):
        return len(self._dict)
    
    def __contains__(self, key):
        return key in self._dict
    
    def __iter__(self):
        return iter(self._dict)
    
    def __getitem__(self, key):
        return self._dict[key]
    
    def __setitem__(self, key, value):
        self._dict[key] = value
    
    def __delitem__(self, key):
        del self._dict[key]

class MemoryAccountant:
    """Memory accountant for testing."""
    
    def __init__(self):
        self.total_memory = 0
    
    def allocate(self, size):
        self.total_memory += size
    
    def deallocate(self, size):
        self.total_memory -= size