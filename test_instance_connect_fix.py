#!/usr/bin/env python3
"""
Test the new connect_instance method that preserves registered callbacks.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import time
import logging

sys.path.insert(0, 'src')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

from spacetimedb_sdk import SpacetimeDBClient

# Test the new connect_instance method
logger.info("=== Testing connect_instance method ===")

callbacks_called = {
    'connect': False,
    'identity': False,
    'disconnect': False
}

def on_connect():
    callbacks_called['connect'] = True
    logger.info("✅ On connect callback called!")

def on_identity(token, identity, connection_id):
    callbacks_called['identity'] = True
    logger.info(f"✅ On identity callback called! Identity: {identity}")

def on_disconnect(reason):
    callbacks_called['disconnect'] = True
    logger.info(f"✅ On disconnect callback called! Reason: {reason}")

# Create client and register callbacks
client = SpacetimeDBClient(protocol="v1.json.spacetimedb")
client.register_on_connect(on_connect)
client.register_on_identity(on_identity)
client.register_on_disconnect(on_disconnect)

logger.info(f"Registered callbacks: connect={len(client._on_connect)}, identity={len(client._on_identity)}, disconnect={len(client._on_disconnect)}")

try:
    # Connect using the new instance method
    client.connect_instance(
        host="localhost:3000",
        database_address="blackholio",
        ssl_enabled=False
    )
    
    logger.info(f"After connect - same instance callbacks: connect={len(client._on_connect)}, identity={len(client._on_identity)}")
    
    # Wait a bit for identity token
    time.sleep(2)
    
    logger.info("\n📊 Results:")
    for callback_name, was_called in callbacks_called.items():
        logger.info(f"  {callback_name}: {'✅ Called' if was_called else '❌ Not called'}")
    
finally:
    if client.is_connected:
        client.disconnect()
        time.sleep(1)  # Give disconnect callback time to fire
        
logger.info(f"\nFinal disconnect callback status: {'✅ Called' if callbacks_called['disconnect'] else '❌ Not called'}")

# Verify all callbacks were called
all_passed = all(callbacks_called.values())
logger.info(f"\n{'✅ All tests passed!' if all_passed else '❌ Some tests failed!'}")