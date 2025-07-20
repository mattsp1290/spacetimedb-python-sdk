#!/usr/bin/env python3
"""
Test to trace if _handle_connect is being called.
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

# Patch _handle_connect to add logging
original_handle_connect = SpacetimeDBClient._handle_connect

def patched_handle_connect(self):
    logger.info("🎯 _handle_connect CALLED!")
    logger.info(f"   self._on_connect list: {self._on_connect}")
    logger.info(f"   Number of callbacks: {len(self._on_connect)}")
    original_handle_connect(self)
    logger.info("🎯 _handle_connect COMPLETED!")

SpacetimeDBClient._handle_connect = patched_handle_connect

# Now test
client = SpacetimeDBClient(protocol="v1.json.spacetimedb")

callback_called = False

def on_connect():
    global callback_called
    callback_called = True
    logger.info("✅ USER CALLBACK CALLED!")

client.register_on_connect(on_connect)

logger.info(f"📝 Registered callback")

try:
    logger.info("🚀 Connecting...")
    client.connect(
        host="localhost:3000",
        database_address="blackholio",
        ssl_enabled=False
    )
    
    time.sleep(2)
    
    logger.info(f"\n📊 Result: callback_called = {callback_called}")
    
finally:
    if client.is_connected:
        client.disconnect()