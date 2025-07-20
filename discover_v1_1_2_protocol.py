#!/usr/bin/env python3
"""
Advanced discovery for SpacetimeDB v1.1.2 protocol
"""
import asyncio
import websockets
import json
import struct
import sys
from typing import Optional, Dict, Any

class ProtocolDiscoverer:
    def __init__(self, host: str = "localhost", port: int = 3000):
        self.host = host
        self.port = port
        self.db_id = "c200790a25c83d93389b2bd36bc7c7b76a3036c80797b4be7dc40f47f7a851e7"
        
    async def try_raw_tcp(self):
        """Try raw TCP connection with various protocols"""
        print("\n=== Testing raw TCP connection ===")
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            print(f"✓ Connected to {self.host}:{self.port} via raw TCP")
            
            # Try sending various initial messages
            test_messages = [
                # JSON messages
                json.dumps({"type": "subscribe", "database": self.db_id}).encode(),
                json.dumps({"action": "subscribe", "db": self.db_id}).encode(),
                json.dumps({"subscribe": {"database": self.db_id}}).encode(),
                # Binary messages
                b'\x00\x00\x00\x01',  # Simple binary header
                b'STDB\x00\x00\x00\x01',  # Custom protocol header
            ]
            
            for msg in test_messages:
                print(f"\nSending: {msg[:50]}...")
                writer.write(msg + b'\n')
                await writer.drain()
                
                # Try to read response
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                    if data:
                        print(f"✓ Received: {data[:100]}")
                        # Try to decode as various formats
                        try:
                            decoded = data.decode('utf-8')
                            print(f"  As UTF-8: {decoded[:100]}")
                        except:
                            print(f"  As hex: {data.hex()[:100]}")
                except asyncio.TimeoutError:
                    print("  × No response")
                    
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            print(f"× Raw TCP failed: {e}")
            
    async def try_websocket_subprotocols(self):
        """Try WebSocket with various subprotocols"""
        print("\n=== Testing WebSocket subprotocols ===")
        
        # Common WebSocket subprotocols
        subprotocols = [
            None,  # No subprotocol
            ["v1.spacetimedb.bin"],
            ["v1.spacetimedb.text"],
            ["spacetimedb"],
            ["spacetimedb.v1"],
            ["spacetimedb.v1.1.2"],
            ["binary"],
            ["text"],
            ["json"],
            ["msgpack"],
            ["bsatn"],
        ]
        
        # Various endpoint patterns
        endpoints = [
            "/",
            "/ws",
            "/websocket",
            "/subscribe",
            f"/subscribe/{self.db_id}",
            f"/database/{self.db_id}/subscribe",
            f"/db/{self.db_id}/ws",
        ]
        
        for endpoint in endpoints:
            for subproto in subprotocols:
                url = f"ws://{self.host}:{self.port}{endpoint}"
                try:
                    extra_headers = {}
                    if subproto:
                        print(f"\nTrying {url} with subprotocol: {subproto}")
                        ws = await asyncio.wait_for(
                            websockets.connect(url, subprotocols=subproto),
                            timeout=2.0
                        )
                    else:
                        print(f"\nTrying {url} with no subprotocol")
                        ws = await asyncio.wait_for(
                            websockets.connect(url),
                            timeout=2.0
                        )
                    
                    print(f"✓ Connected! Subprotocol: {ws.subprotocol}")
                    
                    # Try to receive initial message
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        print(f"✓ Received initial message: {msg[:200]}")
                        
                        # Try sending subscription
                        sub_msg = json.dumps({
                            "type": "subscribe",
                            "database": self.db_id,
                            "queries": ["SELECT * FROM *"]
                        })
                        await ws.send(sub_msg)
                        print(f"  Sent: {sub_msg}")
                        
                        # Try to receive response
                        response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        print(f"✓ Received response: {response[:200]}")
                        
                    except asyncio.TimeoutError:
                        print("  × No initial message received")
                        
                    await ws.close()
                    print(f"\n✓✓✓ SUCCESS: {url} with subprotocol {subproto} works!")
                    return url, subproto
                    
                except (websockets.exceptions.WebSocketException, asyncio.TimeoutError) as e:
                    # Silently skip failures
                    pass
                except Exception as e:
                    print(f"  × Error: {type(e).__name__}: {str(e)[:50]}")
                    
        return None, None
        
    async def try_http_streaming(self):
        """Try HTTP streaming/SSE endpoints"""
        print("\n=== Testing HTTP streaming/SSE ===")
        import aiohttp
        
        endpoints = [
            f"/subscribe/{self.db_id}",
            f"/stream/{self.db_id}",
            f"/events/{self.db_id}",
            f"/sse/{self.db_id}",
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                url = f"http://{self.host}:{self.port}{endpoint}"
                print(f"\nTrying {url}...")
                
                try:
                    async with session.get(
                        url,
                        headers={
                            "Accept": "text/event-stream",
                            "Cache-Control": "no-cache",
                        }
                    ) as response:
                        if response.status == 200:
                            print(f"✓ Connected! Status: {response.status}")
                            print(f"  Headers: {dict(response.headers)}")
                            
                            # Try to read some data
                            data = await response.content.read(1024)
                            if data:
                                print(f"✓ Received: {data[:200]}")
                                return url
                        else:
                            print(f"  × Status: {response.status}")
                            
                except Exception as e:
                    print(f"  × Error: {e}")
                    
        return None
        
    async def discover(self):
        """Run all discovery methods"""
        print(f"SpacetimeDB v1.1.2 Protocol Discovery")
        print(f"Target: {self.host}:{self.port}")
        print(f"Database: {self.db_id}")
        
        # Try different approaches
        await self.try_raw_tcp()
        
        ws_url, subprotocol = await self.try_websocket_subprotocols()
        if ws_url:
            print(f"\n✓✓✓ FOUND WebSocket endpoint: {ws_url}")
            print(f"    Subprotocol: {subprotocol}")
            return
            
        sse_url = await self.try_http_streaming()
        if sse_url:
            print(f"\n✓✓✓ FOUND HTTP streaming endpoint: {sse_url}")
            return
            
        print("\n× No working endpoints found!")
        print("\nThe CLI is connecting somehow. Possible reasons:")
        print("1. Using a custom protocol over raw TCP")
        print("2. Using Unix domain sockets")
        print("3. Using a different port internally")
        print("4. Requires specific authentication/headers")

async def main():
    discoverer = ProtocolDiscoverer()
    await discoverer.discover()

if __name__ == "__main__":
    asyncio.run(main())
