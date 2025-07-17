"""
QueryId implementation for refactoring tests.
"""

class QueryId:
    """Simple QueryId implementation for testing."""
    
    def __init__(self, id):
        self.id = id
    
    def __str__(self):
        return str(self.id)
    
    def __repr__(self):
        return f"QueryId({self.id})"
    
    def __eq__(self, other):
        return isinstance(other, QueryId) and self.id == other.id
    
    def __hash__(self):
        return hash(self.id)