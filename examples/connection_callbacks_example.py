#!/usr/bin/env python3
"""
Example demonstrating proper callback registration patterns with SpacetimeDB client.

This shows the difference between:
1. Class method connect() - creates a new instance
2. Instance method connect_instance() - preserves registered callbacks
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import time
import logging

# Add src to path for development
sys.path.insert(0, '../src')

from spacetimedb_sdk import ModernSpacetimeDBClient, Identity, ConnectionId

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def example_class_method_pattern():
    """
    Pattern 1: Using the class method with callbacks as parameters.
    This is the simplest approach for basic use cases.
    """
    logger.info("\n=== Pattern 1: Class method with callback parameters ===")
    
    def on_connect():
        logger.info("Connected to SpacetimeDB!")
    
    def on_identity(token: str, identity: Identity, connection_id: ConnectionId):
        logger.info(f"Received identity: {identity}")
        logger.info(f"Auth token: {token[:20]}...")
        logger.info(f"Connection ID: {connection_id}")
    
    # Create and connect in one step
    client = ModernSpacetimeDBClient.connect(
        host="localhost:3000",
        database_address="my_module",
        ssl_enabled=False,
        on_connect=on_connect,
        on_identity=on_identity
    )
    
    time.sleep(2)  # Let callbacks fire
    
    if client.is_connected:
        client.disconnect()


def example_instance_method_pattern():
    """
    Pattern 2: Using the instance method for more complex callback setup.
    This allows registering multiple callbacks and preserves them during connection.
    """
    logger.info("\n=== Pattern 2: Instance method with pre-registered callbacks ===")
    
    # Create client instance first
    client = ModernSpacetimeDBClient(protocol="v1.json.spacetimedb")
    
    # Track various events
    events = {
        'connected': False,
        'identity_received': False,
        'disconnected': False
    }
    
    # Register multiple callbacks
    def on_connect():
        events['connected'] = True
        logger.info("✅ Connected to SpacetimeDB!")
    
    def on_identity(token: str, identity: Identity, connection_id: ConnectionId):
        events['identity_received'] = True
        logger.info(f"✅ Received identity: {identity}")
    
    def on_disconnect(reason: str):
        events['disconnected'] = True
        logger.info(f"✅ Disconnected: {reason}")
    
    def on_error(error: Exception):
        logger.error(f"❌ Error: {error}")
    
    # Register all callbacks before connecting
    client.register_on_connect(on_connect)
    client.register_on_identity(on_identity)
    client.register_on_disconnect(on_disconnect)
    client.register_on_error(on_error)
    
    # You can even register multiple callbacks for the same event
    client.register_on_connect(lambda: logger.info("Another connect callback!"))
    
    logger.info(f"Registered {len(client._on_connect)} connect callbacks")
    logger.info(f"Registered {len(client._on_identity)} identity callbacks")
    
    # Now connect using the instance method
    client.connect_instance(
        host="localhost:3000",
        database_address="my_module",
        ssl_enabled=False
    )
    
    time.sleep(2)  # Let callbacks fire
    
    # Check events
    logger.info("\nEvent status:")
    for event, fired in events.items():
        logger.info(f"  {event}: {'✅' if fired else '❌'}")
    
    if client.is_connected:
        client.disconnect()
        time.sleep(1)  # Let disconnect callback fire


def example_advanced_pattern():
    """
    Pattern 3: Advanced usage with event emitter and table callbacks.
    """
    logger.info("\n=== Pattern 3: Advanced pattern with event emitter ===")
    
    from spacetimedb_sdk import EventType, subscribe_to_raw_events
    
    client = ModernSpacetimeDBClient()
    
    # Subscribe to raw events for debugging
    def on_raw_event(event_type: str, data: dict):
        logger.info(f"Raw event: {event_type} -> {data}")
    
    subscribe_to_raw_events(on_raw_event)
    
    # Register table callbacks (assuming a 'users' table exists)
    client.db.users.on_insert(lambda ctx, row: logger.info(f"User inserted: {row}"))
    client.db.users.on_update(lambda ctx, old, new: logger.info(f"User updated: {old} -> {new}"))
    client.db.users.on_delete(lambda ctx, row: logger.info(f"User deleted: {row}"))
    
    # Register for specific events
    client.register_on_connect(lambda: logger.info("Connected!"))
    
    # Connect
    client.connect_instance(
        host="localhost:3000", 
        database_address="my_module",
        ssl_enabled=False
    )
    
    time.sleep(2)
    
    if client.is_connected:
        # Try calling a reducer (if it exists)
        try:
            client.call_reducer("create_user", {"name": "Alice", "age": 30})
        except Exception as e:
            logger.info(f"Reducer call failed (expected if reducer doesn't exist): {e}")
        
        client.disconnect()


def main():
    """Run all examples."""
    logger.info("SpacetimeDB Connection Callback Examples")
    logger.info("=" * 50)
    
    try:
        # Run each pattern
        example_class_method_pattern()
        time.sleep(1)
        
        example_instance_method_pattern()
        time.sleep(1)
        
        example_advanced_pattern()
        
    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
    
    logger.info("\n✅ All examples completed!")


if __name__ == "__main__":
    main()