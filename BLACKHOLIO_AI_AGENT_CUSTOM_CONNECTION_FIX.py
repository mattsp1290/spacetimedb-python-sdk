#!/usr/bin/env python3
"""
Fix for Blackholio AI Agent Custom Connection Module

The issue is that the AI training system uses a custom connection implementation
in src.blackholio_agent.environment.blackholio_connection_v112 that bypasses
the fixed SDK protocol layer and sends raw table names instead of SQL queries.

This fix provides the SQL conversion logic that should be applied to their
custom connection module.
"""

def convert_table_name_to_sql(query: str) -> str:
    """
    Convert table names to proper SQL queries for SpacetimeDB latest version.
    
    This is the same logic implemented in the SDK protocol.py fixes.
    
    Args:
        query: Table name or SQL query
        
    Returns:
        Properly formatted SQL query
    """
    # Check if this is just a table name (no spaces, no SQL keywords)
    if query and ' ' not in query and not any(keyword in query.lower() for keyword in ['select', 'from', 'where', 'join']):
        # Convert table name to SQL query format
        return f"SELECT * FROM {query}"
    else:
        # Keep as-is if it's already a proper SQL query
        return query

def fix_subscription_queries(queries):
    """
    Fix subscription queries for latest SpacetimeDB compatibility.
    
    Args:
        queries: List of table names or SQL queries
        
    Returns:
        List of properly formatted SQL queries
    """
    if isinstance(queries, str):
        # Single query
        return convert_table_name_to_sql(queries)
    elif isinstance(queries, list):
        # Multiple queries
        return [convert_table_name_to_sql(query) for query in queries]
    else:
        return queries

# Example of how to apply this fix to their custom connection module:

class FixedBlackholioConnection:
    """
    Example of how their custom connection should be modified.
    
    They need to apply the SQL conversion before sending subscription messages.
    """
    
    def subscribe_to_entities(self, table_names):
        """
        Fixed version of entity subscription that converts table names to SQL.
        
        BEFORE (causing SQL parser error):
        websocket.send(json.dumps({
            "Subscribe": {
                "query_strings": ["entity", "player", "circle"],  # Raw table names
                "request_id": request_id
            }
        }))
        
        AFTER (working with latest SpacetimeDB):
        websocket.send(json.dumps({
            "Subscribe": {
                "query_strings": ["SELECT * FROM entity", "SELECT * FROM player", "SELECT * FROM circle"],  # Proper SQL
                "request_id": request_id
            }
        }))
        """
        
        # Apply the fix
        fixed_queries = fix_subscription_queries(table_names)
        
        # Now send the properly formatted subscription
        subscription_message = {
            "Subscribe": {
                "query_strings": fixed_queries,
                "request_id": self.generate_request_id()
            }
        }
        
        # Send to WebSocket
        self.websocket.send(json.dumps(subscription_message))
        
        print(f"📤 Sent subscription with fixed queries: {fixed_queries}")

# Test the fix with their exact error case
if __name__ == "__main__":
    print("🔧 Testing Blackholio AI Agent Custom Connection Fix")
    
    # Test the exact case that was failing
    failing_queries = ["entity", "player", "circle", "food", "config"]
    print(f"❌ Original (failing) queries: {failing_queries}")
    
    # Apply the fix
    fixed_queries = fix_subscription_queries(failing_queries)
    print(f"✅ Fixed queries: {fixed_queries}")
    
    # Verify the conversion
    expected = ["SELECT * FROM entity", "SELECT * FROM player", "SELECT * FROM circle", "SELECT * FROM food", "SELECT * FROM config"]
    
    if fixed_queries == expected:
        print("🎉 Fix working correctly!")
        print("\n📋 Instructions for AI Agent Team:")
        print("1. Locate src/blackholio_agent/environment/blackholio_connection_v112.py")
        print("2. Find where subscription messages are constructed")
        print("3. Apply fix_subscription_queries() before sending to WebSocket")
        print("4. Test with: python scripts/train_agent.py")
    else:
        print("❌ Fix not working correctly")
        print(f"Expected: {expected}")
        print(f"Got: {fixed_queries}")
