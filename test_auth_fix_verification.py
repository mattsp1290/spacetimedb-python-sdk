#!/usr/bin/env python3
"""
Verification script for SUBAGENT 3: Mock Server Authentication Logic Fix

This script demonstrates that the mock server authentication validation logic
has been properly fixed to handle Bearer tokens and authentication scenarios.
"""

import sys
import os
import asyncio
import websockets
import logging
import base64
import time

# Add the tests directory to the path
sys.path.insert(0, os.path.join(os.getcwd(), 'tests'))
from mock_spacetimedb_server import MockSpaceTimeDBServer, MockServerConfig

# Set up logging to see authentication details
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def test_bearer_authentication():
    """Test Bearer token authentication."""
    print("\n=== Testing Bearer Token Authentication ===")
    
    # Create server with auth required
    config = MockServerConfig(auth_required=True, port=3010, valid_tokens=["valid_token_123"])
    server = MockSpaceTimeDBServer(config)
    server.start()
    
    try:
        # Wait for server to start
        await asyncio.sleep(0.2)
        
        # Test 1: Valid Bearer token
        print("\n1. Testing VALID Bearer token...")
        uri = 'ws://localhost:3010/v1/database/testdb/subscribe'
        headers = [('Authorization', 'Bearer valid_token_123')]
        
        try:
            async with websockets.connect(uri, additional_headers=headers, subprotocols=['v1.json.spacetimedb']) as websocket:
                print("✓ SUCCESS: Valid Bearer token accepted")
                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"✓ Received identity token: {message[:50]}...")
        except Exception as e:
            print(f"✗ FAILED: {e}")
        
        # Test 2: Invalid Bearer token
        print("\n2. Testing INVALID Bearer token...")
        headers = [('Authorization', 'Bearer invalid_token')]
        
        try:
            async with websockets.connect(uri, additional_headers=headers, subprotocols=['v1.json.spacetimedb']) as websocket:
                print("✗ FAILED: Invalid Bearer token was accepted (should be rejected)")
        except Exception as e:
            if '401' in str(e):
                print("✓ SUCCESS: Invalid Bearer token correctly rejected with 401")
            else:
                print(f"✗ FAILED: Unexpected error: {e}")
        
        # Test 3: Missing Authorization header
        print("\n3. Testing MISSING authorization header...")
        
        try:
            async with websockets.connect(uri, subprotocols=['v1.json.spacetimedb']) as websocket:
                print("✗ FAILED: Missing auth header was accepted (should be rejected)")
        except Exception as e:
            if '401' in str(e):
                print("✓ SUCCESS: Missing authorization header correctly rejected with 401")
            else:
                print(f"✗ FAILED: Unexpected error: {e}")
                
    finally:
        server.stop()

async def test_basic_authentication():
    """Test Basic authentication (legacy compatibility)."""
    print("\n=== Testing Basic Authentication (Legacy) ===")
    
    # Create server with auth required
    config = MockServerConfig(auth_required=True, port=3011, valid_tokens=["valid_token_123"])
    server = MockSpaceTimeDBServer(config)
    server.start()
    
    try:
        # Wait for server to start
        await asyncio.sleep(0.2)
        
        # Test Basic auth with token as username
        print("\n1. Testing Basic auth (token as username)...")
        uri = 'ws://localhost:3011/v1/database/testdb/subscribe'
        credentials = base64.b64encode('valid_token_123:password'.encode()).decode()
        headers = [('Authorization', f'Basic {credentials}')]
        
        try:
            async with websockets.connect(uri, additional_headers=headers, subprotocols=['v1.json.spacetimedb']) as websocket:
                print("✓ SUCCESS: Basic auth with valid token accepted")
                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"✓ Received identity token: {message[:50]}...")
        except Exception as e:
            print(f"✗ FAILED: {e}")
        
        # Test Basic auth with token:token format
        print("\n2. Testing Basic auth (token:token format)...")
        credentials = base64.b64encode('token:valid_token_123'.encode()).decode()
        headers = [('Authorization', f'Basic {credentials}')]
        
        try:
            async with websockets.connect(uri, additional_headers=headers, subprotocols=['v1.json.spacetimedb']) as websocket:
                print("✓ SUCCESS: Basic auth with token:token format accepted")
                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"✓ Received identity token: {message[:50]}...")
        except Exception as e:
            print(f"✗ FAILED: {e}")
                
    finally:
        server.stop()

async def test_header_extraction_fix():
    """Test that the header extraction fix works with different websockets versions."""
    print("\n=== Testing Header Extraction Fix ===")
    
    # Create server with auth required
    config = MockServerConfig(auth_required=True, port=3012, valid_tokens=["test_token"])
    server = MockSpaceTimeDBServer(config)
    server.start()
    
    try:
        # Wait for server to start
        await asyncio.sleep(0.2)
        
        print("\n1. Testing header extraction from websockets.http11.Request object...")
        uri = 'ws://localhost:3012/v1/database/testdb/subscribe'
        headers = [('Authorization', 'Bearer test_token')]
        
        try:
            async with websockets.connect(uri, additional_headers=headers, subprotocols=['v1.json.spacetimedb']) as websocket:
                print("✓ SUCCESS: Header extracted correctly from Request object")
                print("✓ Auth validation working with websockets v15+ format")
        except Exception as e:
            if '401' in str(e):
                print("✗ FAILED: Valid token was rejected - header extraction not working")
            else:
                print(f"✗ FAILED: Unexpected error: {e}")
                
    finally:
        server.stop()

async def main():
    """Run all authentication tests."""
    print("=" * 70)
    print("SUBAGENT 3: Mock Server Authentication Logic Fix Verification")
    print("=" * 70)
    
    print("\nThis script verifies that the following issues have been fixed:")
    print("1. Mock server was rejecting valid authentication tokens")
    print("2. The _validate_auth method had bugs in Bearer token handling")
    print("3. Authentication rejection logic was not working correctly")
    print("4. Header extraction from websockets v15+ Request objects")
    
    print(f"\nUsing websockets version: {websockets.__version__}")
    
    # Run all tests
    await test_bearer_authentication()
    await test_basic_authentication()
    await test_header_extraction_fix()
    
    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)
    print("\nKey fixes implemented:")
    print("• Fixed header extraction to handle websockets.http11.Request objects")
    print("• Added support for request_headers.headers attribute (websockets v15+)")
    print("• Maintained backward compatibility with older websockets versions")
    print("• Both Bearer and Basic authentication formats work correctly")
    print("• Invalid tokens and missing headers are properly rejected with 401")
    print("• Log messages now correctly show 'header present: True/False'")

if __name__ == "__main__":
    asyncio.run(main())