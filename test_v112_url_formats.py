#!/usr/bin/env python3
"""
Test script to determine the correct URL format for SpacetimeDB v1.1.2
Tests both /v1/database/ and /v1/ws/database/ endpoints
Tests with different protocols and db_identity as query parameter
"""

import websocket
import json
import threading
import time
import sys
from typing import Dict, List, Optional, Tuple

# Test configurations
HOST = "localhost:3000"
DATABASE_NAME = "blackholio"
DATABASE_IDENTITY = None  # Will be populated if we can discover it

# Protocols to test
PROTOCOLS = [
    "v1.json.spacetimedb",
    "v1.bsatn.spacetimedb",
    "v1.text.spacetimedb"  # Expected to fail
]

# URL patterns to test
URL_PATTERNS = [
    # Pattern 1: /v1/database/{name}/subscribe
    ("v1_database_name", "ws://{host}/v1/database/{name}/subscribe"),
    
    # Pattern 2: /v1/ws/database/{name}/subscribe  
    ("v1_ws_database_name", "ws://{host}/v1/ws/database/{name}/subscribe"),
    
    # Pattern 3: /v1/database/{name}/subscribe?db_identity={identity}
    ("v1_database_name_with_identity", "ws://{host}/v1/database/{name}/subscribe?db_identity={identity}"),
    
    # Pattern 4: /v1/ws/database/{name}/subscribe?db_identity={identity}
    ("v1_ws_database_name_with_identity", "ws://{host}/v1/ws/database/{name}/subscribe?db_identity={identity}")
]


class WebSocketTester:
    def __init__(self):
        self.results: List[Dict] = []
        self.connection_event = threading.Event()
        self.error_event = threading.Event()
        self.identity_received = False
        self.last_error = None
        
    def test_url(self, pattern_name: str, url: str, protocol: str) -> Dict:
        """Test a specific URL with a specific protocol"""
        print(f"\nTesting: {pattern_name}")
        print(f"  URL: {url}")
        print(f"  Protocol: {protocol}")
        
        self.connection_event.clear()
        self.error_event.clear()
        self.identity_received = False
        self.last_error = None
        
        result = {
            "pattern_name": pattern_name,
            "url": url,
            "protocol": protocol,
            "connected": False,
            "identity_received": False,
            "error": None,
            "selected_protocol": None
        }
        
        try:
            ws = websocket.WebSocketApp(
                url,
                subprotocols=[protocol],
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Run in a thread with timeout
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection or error (5 second timeout)
            connected = self.connection_event.wait(5.0)
            error_occurred = self.error_event.is_set()
            
            if connected and not error_occurred:
                result["connected"] = True
                result["selected_protocol"] = ws.subprotocol
                
                # Wait a bit for identity message
                time.sleep(1.0)
                result["identity_received"] = self.identity_received
            else:
                result["error"] = self.last_error or "Connection timeout"
            
            # Close the connection
            ws.close()
            ws_thread.join(timeout=1.0)
            
        except Exception as e:
            result["error"] = str(e)
        
        # Print result
        if result["connected"]:
            print(f"  ✓ CONNECTED - Protocol: {result['selected_protocol']}")
            if result["identity_received"]:
                print(f"  ✓ Identity received")
        else:
            print(f"  ✗ FAILED - {result['error']}")
        
        return result
    
    def on_open(self, ws):
        print("  → Connection opened")
        self.connection_event.set()
    
    def on_message(self, ws, message):
        try:
            # Try to parse as JSON
            data = json.loads(message)
            if "IdentityToken" in data:
                self.identity_received = True
                token_data = data["IdentityToken"]
                print(f"  → Received IdentityToken")
                print(f"    Identity: {token_data.get('identity', 'N/A')}")
                print(f"    Connection ID: {token_data.get('connection_id', 'N/A')}")
                
                # Store the database identity if we got one
                global DATABASE_IDENTITY
                if not DATABASE_IDENTITY and "identity" in token_data:
                    DATABASE_IDENTITY = token_data["identity"]
                    print(f"    (Stored database identity for future tests)")
        except json.JSONDecodeError:
            # Might be binary message
            print(f"  → Received non-JSON message (length: {len(message)})")
    
    def on_error(self, ws, error):
        print(f"  → Error: {error}")
        self.last_error = str(error)
        self.error_event.set()
    
    def on_close(self, ws, close_status_code, close_msg):
        if close_status_code or close_msg:
            print(f"  → Connection closed: {close_status_code} - {close_msg}")
            if not self.connection_event.is_set():
                self.last_error = f"Closed: {close_status_code} - {close_msg}"
                self.error_event.set()
    
    def run_all_tests(self):
        """Run all test combinations"""
        print("=" * 80)
        print("SpacetimeDB v1.1.2 WebSocket URL Format Testing")
        print("=" * 80)
        
        # Test each URL pattern with each protocol
        for pattern_name, url_template in URL_PATTERNS:
            for protocol in PROTOCOLS:
                # Build the URL
                if "{identity}" in url_template and not DATABASE_IDENTITY:
                    # Skip tests that need identity if we don't have one yet
                    if "with_identity" in pattern_name:
                        continue
                
                url = url_template.format(
                    host=HOST,
                    name=DATABASE_NAME,
                    identity=DATABASE_IDENTITY or "unknown"
                )
                
                result = self.test_url(pattern_name, url, protocol)
                self.results.append(result)
                
                # Small delay between tests
                time.sleep(0.5)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 80)
        print("SUMMARY OF RESULTS")
        print("=" * 80)
        
        # Group by success
        successful = [r for r in self.results if r["connected"]]
        failed = [r for r in self.results if not r["connected"]]
        
        print(f"\nSuccessful connections: {len(successful)}/{len(self.results)}")
        print("-" * 40)
        
        if successful:
            print("\n✓ WORKING CONFIGURATIONS:")
            for result in successful:
                print(f"  • {result['pattern_name']} + {result['protocol']}")
                print(f"    URL: {result['url']}")
                if result['identity_received']:
                    print(f"    Identity: Received ✓")
                print()
        
        if failed:
            print("\n✗ FAILED CONFIGURATIONS:")
            # Group by error type
            error_groups = {}
            for result in failed:
                error = result['error'] or 'Unknown error'
                if error not in error_groups:
                    error_groups[error] = []
                error_groups[error].append(result)
            
            for error, results in error_groups.items():
                print(f"\n  Error: {error}")
                for result in results:
                    print(f"    • {result['pattern_name']} + {result['protocol']}")
        
        # Recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        
        # Find the best working configuration
        best_configs = [r for r in successful if r['identity_received']]
        if best_configs:
            # Prefer configurations without /ws/ in the path
            non_ws_configs = [c for c in best_configs if "/ws/" not in c['url']]
            recommended = non_ws_configs[0] if non_ws_configs else best_configs[0]
            
            print(f"\n✓ Recommended configuration:")
            print(f"  Pattern: {recommended['pattern_name']}")
            print(f"  Protocol: {recommended['protocol']}")
            print(f"  URL Template: {URL_PATTERNS[[p[0] for p in URL_PATTERNS].index(recommended['pattern_name'])][1]}")
            
            # Check if db_identity should be in query params
            if "with_identity" in recommended['pattern_name']:
                print(f"  Note: db_identity should be passed as a query parameter")
        else:
            print("\n✗ No successful configurations found!")
            print("  Please ensure SpacetimeDB v1.1.2 is running on localhost:3000")


def main():
    """Main entry point"""
    print("Starting SpacetimeDB v1.1.2 URL format tests...")
    print(f"Target: {HOST}")
    print(f"Database: {DATABASE_NAME}")
    
    tester = WebSocketTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
