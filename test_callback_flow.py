#!/usr/bin/env python3
"""
Test to trace callback flow through the SDK.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import time
import logging

sys.path.insert(0, 'src')

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Patch the websocket client to add more logging
import spacetimedb_sdk.websocket_client as ws_client

original_init = ws_client.WebSocketClient.__init__
def patched_init(self, *args, **kwargs):
    logger.info(f"🔧 WebSocket client init called with callbacks:")
    logger.info(f"   on_connect: {kwargs.get('on_connect', 'None')}")
    logger.info(f"   on_disconnect: {kwargs.get('on_disconnect', 'None')}")
    logger.info(f"   on_error: {kwargs.get('on_error', 'None')}")
    logger.info(f"   on_message: {kwargs.get('on_message', 'None')}")
    original_init(self, *args, **kwargs)
    logger.info(f"🔧 After init, self._on_connect = {self._on_connect}")

ws_client.WebSocketClient.__init__ = patched_init

original_on_open = ws_client.WebSocketClient._on_ws_open
def patched_on_open(self, ws):
    logger.info(f"🔧 _on_ws_open called, self._on_connect = {self._on_connect}")
    original_on_open(self, ws)

ws_client.WebSocketClient._on_ws_open = patched_on_open

# Now test
from spacetimedb_sdk import SpacetimeDBClient

client = SpacetimeDBClient(protocol="v1.json.spacetimedb")

callback_called = False

def on_connect():
    global callback_called
    callback_called = True
    logger.info("✅ ON_CONNECT CALLBACK CALLED!")

client.register_on_connect(on_connect)

logger.info(f"📝 Registered callback, client._on_connect list = {client._on_connect}")

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