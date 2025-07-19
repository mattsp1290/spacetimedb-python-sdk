#!/usr/bin/env python3
"""
Test script to verify SpacetimeDB v1.1.2 connection issues and discover new endpoints.
"""

import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import os
import requests
import websocket
import json
import time
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add SDK to path
sys.path.insert(0, 'src')

def test_http_endpoints(host="localhost:3000"):
    """Test various HTTP endpoints to understand the API structure."""
    logger.info(f"Testing HTTP endpoints on {host}...")
    
    endpoints_to_test = [
        "/health",
        "/",
        "/api",
        "/api/v1",
        "/v1",
        "/database",
        "/databases",
        "/info",
        "/version",
        "/ws",
        "/websocket",
    ]
    
    for endpoint in endpoints_to_test:
        try:
            url = f"http://{host}{endpoint}"
            response = requests.get(url, timeout=5)
            logger.info(f"GET {endpoint}: {response.status_code} - {response.text[:100] if response.text else 'No content'}")
            
            # Check response headers for clues
            if response.headers:
                logger.debug(f"  Headers: {dict(response.headers)}")
                
        except Exception as e:
            logger.error(f"GET {endpoint}: Error - {str(e)}")
    
    # Also try some WebSocket-specific discovery
    ws_endpoints = [
        "/ws",
        "/websocket",
        "/v1/ws",
        "/v1/websocket",
        "/database/ws",
        "/database/websocket",
        "/subscribe",
        "/v1/subscribe",
    ]
    
    logger.info("\nChecking for WebSocket upgrade endpoints...")
    for endpoint in ws_endpoints:
        try:
            url = f"http://{host}{endpoint}"
            headers = {"Upgrade": "websocket", "Connection": "Upgrade"}
            response = requests.get(url, headers=headers, timeout=5)
            logger.info(f"WebSocket probe {endpoint}: {response.status_code}")
        except Exception as e:
            logger.debug(f"WebSocket probe {endpoint}: {str(e)}")

def test_websocket_endpoints(host="localhost:3000", database="test_module"):
    """Test various WebSocket endpoint patterns."""
    logger.info(f"\nTesting WebSocket connections to {host}...")
    
    # List of WebSocket URLs to try
    ws_urls = [
        # Current SDK patterns (known to fail)
        f"ws://{host}/v1/database/subscribe/{database}",
        f"ws://{host}/database/ws/{database}",
        
        # New potential patterns
        f"ws://{host}/ws",
        f"ws://{host}/websocket",
        f"ws://{host}/v1/ws",
        f"ws://{host}/v1/websocket", 
        f"ws://{host}/subscribe",
        f"ws://{host}/v1/subscribe",
        f"ws://{host}/database/{database}/ws",
        f"ws://{host}/database/{database}/websocket",
        f"ws://{host}/db/{database}/ws",
        f"ws://{host}/module/{database}/ws",
        
        # Without database name (might connect first, then subscribe)
        f"ws://{host}/v1",
        f"ws://{host}/api/v1/ws",
        f"ws://{host}/api/ws",
    ]
    
    for url in ws_urls:
        try:
            logger.info(f"Trying WebSocket URL: {url}")
            
            # Try to connect
            ws = websocket.create_connection(url, timeout=5)
            logger.success(f"✓ SUCCESS! Connected to: {url}")
            
            # Try to receive initial message
            try:
                ws.settimeout(2)
                message = ws.recv()
                logger.info(f"  Received initial message: {message[:200]}")
            except:
                logger.info("  No initial message received")
            
            # Try sending a test message
            test_messages = [
                '{"type": "subscribe", "database": "' + database + '"}',
                '{"subscribe": {"database": "' + database + '"}}',
                '{"action": "subscribe", "params": {"database": "' + database + '"}}',
            ]
            
            for msg in test_messages:
                try:
                    logger.debug(f"  Sending: {msg}")
                    ws.send(msg)
                    
                    # Try to receive response
                    ws.settimeout(1)
                    response = ws.recv()
                    logger.info(f"  Response to {msg[:50]}...: {response[:200]}")
                except Exception as e:
                    logger.debug(f"  No response or error: {str(e)}")
            
            ws.close()
            
        except Exception as e:
            logger.debug(f"Failed to connect to {url}: {str(e)}")

def test_current_sdk_connection():
    """Test the current SDK connection to show the failure."""
    logger.info("\nTesting current SDK connection (expected to fail)...")
    
    try:
        from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient
        
        # Try to connect
        client = SpacetimeDBClient.init(
            auth_token=None,
            host="localhost:3000",
            address_or_name="test_module", 
            ssl_enabled=False,
            autogen_package=None,
            on_connect=lambda: logger.info("SDK: Connected!"),
            on_error=lambda err: logger.error(f"SDK: Error - {err}")
        )
        
        # Wait a bit to see if connection succeeds
        time.sleep(3)
        
        if hasattr(client, 'wsc') and client.wsc:
            logger.info(f"SDK WebSocket state: {getattr(client.wsc, 'is_connected', 'unknown')}")
            
    except Exception as e:
        logger.error(f"SDK connection failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

def check_cli_network_traffic():
    """Instructions for checking CLI network traffic."""
    logger.info("\n" + "="*80)
    logger.info("To discover the correct endpoints, run these commands in another terminal:")
    logger.info("="*80)
    logger.info("")
    logger.info("1. Start network monitoring (choose one):")
    logger.info("   - macOS: sudo tcpdump -i lo0 -w spacetime.pcap port 3000")
    logger.info("   - Linux: sudo tcpdump -i lo -w spacetime.pcap port 3000") 
    logger.info("   - Or use Wireshark with filter: port 3000")
    logger.info("")
    logger.info("2. Run the SpacetimeDB CLI command that works:")
    logger.info("   spacetime subscribe test_module")
    logger.info("")
    logger.info("3. Stop the capture and analyze:")
    logger.info("   - tcpdump: Ctrl+C, then: tcpdump -r spacetime.pcap -A")
    logger.info("   - Wireshark: Look for HTTP upgrade requests")
    logger.info("")
    logger.info("Look for:")
    logger.info("- HTTP requests with 'Upgrade: websocket' header")
    logger.info("- The exact URL path being used")
    logger.info("- Any authentication headers")
    logger.info("="*80)

# Add custom log level for success
logging.SUCCESS = 25
logging.addLevelName(logging.SUCCESS, 'SUCCESS')
def success(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.SUCCESS):
        self._log(logging.SUCCESS, message, args, **kwargs)
logging.Logger.success = success

if __name__ == "__main__":
    logger.info("SpacetimeDB v1.1.2 Connection Discovery Tool")
    logger.info("=" * 60)
    
    # Test HTTP endpoints first
    test_http_endpoints()
    
    # Test WebSocket endpoints
    test_websocket_endpoints()
    
    # Test current SDK (show it fails)
    test_current_sdk_connection()
    
    # Show instructions for CLI analysis
    check_cli_network_traffic()
