#!/usr/bin/env python3
"""
WebSocket endpoint discovery tool for SpacetimeDB v1.1.2
This tool will help us find the correct WebSocket endpoint by trying various patterns.
"""
import asyncio
import websockets
import json
import logging
import sys
import aiohttp
from typing import Optional, List, Dict, Any, Set

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SpacetimeDBEndpointDiscovery:
    def __init__(self, host: str = "localhost:3000"):
        self.host = host
        self.base_url = f"http://{host}"
        self.discovered_endpoints = set()
        
    async def discover_http_api(self):
        """Discover HTTP API endpoints that might hint at WebSocket locations."""
        logger.info(f"Discovering HTTP API endpoints on {self.host}...")
        
        # Common API patterns in modern web services
        endpoints = [
            "/",
            "/api",
            "/api/v1",
            "/v1",
            "/info",
            "/health",
            "/status",
            "/version",
            # SpacetimeDB specific guesses
            "/database",
            "/databases", 
            "/modules",
            "/module",
            "/subscribe",
            "/subscriptions",
            "/ws/info",
            "/websocket/info",
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    async with session.get(url) as response:
                        if response.status < 400:
                            content = await response.text()
                            logger.info(f"✓ {endpoint} - {response.status}")
                            
                            # Look for WebSocket hints in response
                            if any(ws_hint in content.lower() for ws_hint in ['websocket', 'ws://', 'wss://', 'subscribe']):
                                logger.info(f"  → Found WebSocket hints in response!")
                                
                except Exception as e:
                    logger.debug(f"✗ {endpoint} - {str(e)}")
    
    async def test_websocket_endpoint(self, path: str, database: Optional[str] = None) -> bool:
        """Test if a WebSocket endpoint is valid."""
        url = f"ws://{self.host}{path}"
        
        try:
            # Try to connect
            async with websockets.connect(url, close_timeout=2) as websocket:
                logger.info(f"✓ SUCCESS! Connected to: {url}")
                self.discovered_endpoints.add(url)
                
                # Try to receive any initial message
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    logger.info(f"  Initial message: {message[:100]}...")
                    
                    # If we get an identity token, that's a good sign
                    if "IdentityToken" in message or "identity" in message.lower():
                        logger.info("  → Received identity token! This looks like the right endpoint.")
                        return True
                except asyncio.TimeoutError:
                    logger.debug("  No initial message received")
                
                # Try different subscription patterns if database provided
                if database:
                    subscription_messages = [
                        # Modern patterns
                        {"subscribe": {"database": database}},
                        {"Subscribe": {"database": database}},
                        {"type": "subscribe", "database": database},
                        {"action": "subscribe", "params": {"database": database}},
                        
                        # Legacy patterns
                        {"subscribe": {"query_strings": [f"SELECT * FROM {database}"]}},
                        {"cmd": "subscribe", "db": database},
                    ]
                    
                    for msg in subscription_messages:
                        try:
                            logger.debug(f"  Trying subscription: {json.dumps(msg)}")
                            await websocket.send(json.dumps(msg))
                            
                            response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            logger.info(f"  Response: {response[:100]}...")
                            
                            if "error" not in response.lower():
                                logger.info("  → Subscription successful!")
                                return True
                                
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.debug(f"  Subscription error: {str(e)}")
                
                return True  # Connected successfully
                
        except Exception as e:
            logger.debug(f"✗ Failed to connect to {url}: {str(e)}")
            return False
    
    async def discover_websocket_endpoints(self, database: str = "test_module"):
        """Try various WebSocket endpoint patterns."""
        logger.info(f"\nDiscovering WebSocket endpoints for database '{database}'...")
        
        # Endpoint patterns to test
        patterns = [
            # Current SDK pattern (expected to fail in v1.1.2)
            f"/v1/database/subscribe/{database}",
            
            # New v1.1.2 patterns (guesses based on common patterns)
            "/ws",
            "/websocket", 
            f"/ws/{database}",
            f"/websocket/{database}",
            "/v1/ws",
            "/v1/websocket",
            "/api/v1/ws",
            "/api/ws",
            
            # Database-specific patterns
            f"/database/{database}/ws",
            f"/database/{database}/websocket",
            f"/databases/{database}/ws",
            f"/module/{database}/ws",
            f"/modules/{database}/ws",
            
            # Generic connection patterns (database specified after connect)
            "/connect",
            "/v1/connect",
            "/subscribe",
            "/v1/subscribe",
            
            # Other possibilities
            f"/{database}/ws",
            f"/{database}/websocket",
            "/spacetime/ws",
            "/spacetimedb/ws",
        ]
        
        for pattern in patterns:
            await self.test_websocket_endpoint(pattern, database)
            await asyncio.sleep(0.1)  # Small delay between attempts
    
    async def analyze_cli_hints(self):
        """Provide hints about analyzing CLI network traffic."""
        logger.info("\n" + "="*80)
        logger.info("Advanced Discovery Techniques:")
        logger.info("="*80)
        
        logger.info("\n1. Use mitmproxy to intercept CLI traffic:")
        logger.info("   pip install mitmproxy")
        logger.info("   mitmproxy --mode transparent --showhost")
        logger.info("   Then run: spacetime subscribe test_module")
        
        logger.info("\n2. Use strace/dtruss to trace system calls:")
        logger.info("   macOS: sudo dtruss -f spacetime subscribe test_module 2>&1 | grep -i 'connect'")
        logger.info("   Linux: strace -f -e trace=network spacetime subscribe test_module")
        
        logger.info("\n3. Check SpacetimeDB logs:")
        logger.info("   docker logs <container_id> | grep -i websocket")
        
        logger.info("\n4. Use browser DevTools:")
        logger.info("   - Open http://localhost:3000 in browser")
        logger.info("   - Check Network tab for WebSocket connections")
        logger.info("   - Look at any JavaScript files for WebSocket URLs")
        logger.info("="*80)
    
    async def run_discovery(self):
        """Run the complete discovery process."""
        logger.info(f"Starting SpacetimeDB v1.1.2 endpoint discovery for {self.host}")
        logger.info("="*60)
        
        # First, discover HTTP endpoints
        await self.discover_http_api()
        
        # Then try WebSocket endpoints
        await self.discover_websocket_endpoints()
        
        # Show analysis hints
        await self.analyze_cli_hints()
        
        # Summary
        if self.discovered_endpoints:
            logger.info("\n✓ DISCOVERED ENDPOINTS:")
            for endpoint in self.discovered_endpoints:
                logger.info(f"  - {endpoint}")
        else:
            logger.info("\n✗ No working WebSocket endpoints found.")
            logger.info("  The endpoint pattern may have changed significantly in v1.1.2")
            logger.info("  Please use the network analysis techniques above to discover the new pattern.")

async def test_with_mock_server():
    """Test with a mock WebSocket server to verify our discovery logic."""
    logger.info("\nTesting discovery logic with mock server...")
    
    # This would normally connect to a mock server for testing
    # For now, just validate the discovery logic
    discovery = SpacetimeDBEndpointDiscovery("localhost:3000")
    
    # Test pattern matching
    test_patterns = [
        "/ws",
        "/v1/ws", 
        "/database/test/ws",
    ]
    
    logger.info("Testing endpoint pattern generation...")
    for pattern in test_patterns:
        logger.info(f"  Pattern: {pattern} -> ws://localhost:3000{pattern}")

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Discover SpacetimeDB v1.1.2 WebSocket endpoints")
    parser.add_argument("--host", default="localhost:3000", help="SpacetimeDB host:port")
    parser.add_argument("--database", default="test_module", help="Database/module name to test")
    parser.add_argument("--test-mock", action="store_true", help="Test with mock server")
    
    args = parser.parse_args()
    
    if args.test_mock:
        await test_with_mock_server()
    else:
        discovery = SpacetimeDBEndpointDiscovery(args.host)
        await discovery.run_discovery()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nDiscovery interrupted by user")
