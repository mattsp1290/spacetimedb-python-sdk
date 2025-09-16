#!/usr/bin/env python3
"""
Test real connection to the blackholio SpacetimeDB server.
This assumes the server is running as per the user's setup.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import time
import logging

sys.path.insert(0, 'src')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from spacetimedb_sdk import SpacetimeDBClient

def test_blackholio_connection():
    """Test connection to the real blackholio server."""
    logger.info("=== Testing Real Blackholio Server Connection ===")
    
    # Track events
    events = {
        'connected': False,
        'identity_received': False,
        'database_update': False,
        'subscription_applied': False
    }
    
    # Create client
    client = SpacetimeDBClient(protocol="v1.json.spacetimedb")
    
    # Register callbacks
    def on_connect():
        events['connected'] = True
        logger.info("✅ Connected to blackholio server!")
    
    def on_identity(token, identity, connection_id):
        events['identity_received'] = True
        logger.info(f"✅ Received identity: {identity}")
        logger.info(f"   Connection ID: {connection_id}")
    
    def on_error(error):
        logger.error(f"❌ Connection error: {error}")
    
    def on_disconnect(reason):
        logger.info(f"Disconnected: {reason}")
    
    # Track database updates via event emitter
    def on_database_update(event):
        events['database_update'] = True
        logger.info(f"Database update received")
    
    # Register for database updates
    client._event_emitter.on('database.update', on_database_update)
    
    # Register callbacks
    client.register_on_connect(on_connect)
    client.register_on_identity(on_identity)
    client.register_on_error(on_error)
    client.register_on_disconnect(on_disconnect)
    
    try:
        # Connect using instance method to preserve callbacks
        logger.info("Connecting to localhost:3000/blackholio...")
        client.connect_instance(
            host="localhost:3000",
            database_address="blackholio",
            ssl_enabled=False
        )
        
        # Wait for events
        logger.info("Waiting for server events...")
        time.sleep(3)
        
        # Check if connected
        if client.is_connected:
            logger.info("✅ Client reports connected state")
            
            # Try to subscribe to a table (if it exists)
            try:
                logger.info("Attempting to subscribe to tables...")
                client.subscribe(["SELECT * FROM User"])
                time.sleep(2)
            except Exception as e:
                logger.info(f"Subscribe attempt failed (expected if table doesn't exist): {e}")
            
            # Try calling a reducer
            try:
                logger.info("Attempting to call a reducer...")
                client.call_reducer("create_player", {"name": "TestPlayer"})
                time.sleep(1)
            except Exception as e:
                logger.info(f"Reducer call failed (expected if reducer doesn't exist): {e}")
        
        # Report results
        logger.info("\n📊 Event Summary:")
        for event_name, occurred in events.items():
            status = "✅" if occurred else "❌"
            logger.info(f"  {event_name}: {status}")
        
        # Overall result
        if events['connected'] and events['identity_received']:
            logger.info("\n✅ PASS: Successfully connected to blackholio server!")
            return True
        else:
            logger.info("\n❌ FAIL: Could not establish proper connection")
            return False
            
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        return False
        
    finally:
        if client.is_connected:
            client.disconnect()
            time.sleep(1)


if __name__ == "__main__":
    success = test_blackholio_connection()
    sys.exit(0 if success else 1)