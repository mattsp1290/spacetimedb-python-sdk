#!/usr/bin/env python3
"""
Test SpacetimeDB v1.1.2 endpoints to understand the connection issue
"""
import subprocess
import json
import sys

def test_endpoint(url, method="GET", headers=None):
    """Test an endpoint with curl"""
    cmd = ["curl", "-v", "-X", method]
    
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
    
    cmd.append(url)
    
    print(f"\nTesting: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Exit code: {result.returncode}")
    if result.stdout:
        print(f"STDOUT: {result.stdout}")
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    
    return result

def main():
    """Test various endpoint patterns"""
    base_url = "http://localhost:3000"
    db_id = "c200790a25c83d93389b2bd36bc7c7b76a3036c80797b4be7dc40f47f7a851e7"
    
    # Test patterns based on v1.1.2 changes
    patterns = [
        f"{base_url}/",
        f"{base_url}/health",
        f"{base_url}/database/{db_id}",
        f"{base_url}/db/{db_id}",
        f"{base_url}/identity/{db_id}/subscribe",
        f"{base_url}/spacetimedb/subscribe/{db_id}",
        # Test with database as header instead of URL
        (f"{base_url}/subscribe", {"X-Database-Identity": db_id}),
        (f"{base_url}/v1/subscribe", {"X-Database-Identity": db_id}),
    ]
    
    for pattern in patterns:
        if isinstance(pattern, tuple):
            url, headers = pattern
            test_endpoint(url, headers=headers)
        else:
            test_endpoint(pattern)
    
    # Test WebSocket upgrade
    print("\n\nTesting WebSocket upgrades with database in header:")
    ws_patterns = [
        (f"{base_url}/subscribe", {"X-Database-Identity": db_id}),
        (f"{base_url}/ws", {"X-Database-Identity": db_id}),
        (f"{base_url}/websocket", {"X-Database-Identity": db_id}),
    ]
    
    for url, headers in ws_patterns:
        headers.update({
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Key": "x3JJHMbDL1EzLkh9GBhXDw==",
            "Sec-WebSocket-Version": "13"
        })
        test_endpoint(url, headers=headers)

if __name__ == "__main__":
    main()
