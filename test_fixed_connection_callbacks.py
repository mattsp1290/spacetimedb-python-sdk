#!/usr/bin/env python3
"""
Test to verify the fixed connection callback behavior.
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

# Test 1: Using class method with callbacks as parameters (current working pattern)
logger.info("\n=== Test 1: Class method with callback parameters ===")
callback_called_1 = False

def on_connect_1():
    global callback_called_1
    callback_called_1 = True
    logger.info("✅ Callback 1 called (via parameter)")

try:
    client1 = SpacetimeDBClient.connect(
        host="localhost:3000",
        database_address="blackholio",
        ssl_enabled=False,
        on_connect=on_connect_1
    )
    
    time.sleep(2)
    logger.info(f"Result: callback_called_1 = {callback_called_1}")
    
finally:
    if 'client1' in locals() and client1.is_connected:
        client1.disconnect()

# Test 2: Using instance method pattern (what users expect but currently doesn't work)
logger.info("\n=== Test 2: Instance method pattern (current broken behavior) ===")
callback_called_2 = False

def on_connect_2():
    global callback_called_2
    callback_called_2 = True
    logger.info("✅ Callback 2 called (via register)")

client2 = SpacetimeDBClient(protocol="v1.json.spacetimedb")
client2.register_on_connect(on_connect_2)
logger.info(f"Registered callback on instance: {len(client2._on_connect)} callbacks")

try:
    # This creates a NEW instance, losing the registered callback
    connected_client = client2.connect(
        host="localhost:3000",
        database_address="blackholio", 
        ssl_enabled=False
    )
    
    logger.info(f"Instance after connect - same object? {connected_client is client2}")
    logger.info(f"Connected client callbacks: {len(connected_client._on_connect)} callbacks")
    
    time.sleep(2)
    logger.info(f"Result: callback_called_2 = {callback_called_2}")
    
finally:
    if 'connected_client' in locals() and connected_client.is_connected:
        connected_client.disconnect()

# Test 3: Using the new instance connect method (what we'll implement)
logger.info("\n=== Test 3: New instance connect method (fixed behavior) ===")
callback_called_3 = False

def on_connect_3():
    global callback_called_3
    callback_called_3 = True
    logger.info("✅ Callback 3 called (via register with instance connect)")

client3 = SpacetimeDBClient(protocol="v1.json.spacetimedb")
client3.register_on_connect(on_connect_3)
logger.info(f"Registered callback on instance: {len(client3._on_connect)} callbacks")

try:
    # Use the internal connect method directly (what we'll expose as connect_instance)
    client3._connect_internal(
        auth_token=None,
        host="localhost:3000",
        database_address="blackholio",
        ssl_enabled=False
    )
    
    logger.info(f"Same instance after connect: {len(client3._on_connect)} callbacks")
    
    time.sleep(2)
    logger.info(f"Result: callback_called_3 = {callback_called_3}")
    
finally:
    if client3.is_connected:
        client3.disconnect()