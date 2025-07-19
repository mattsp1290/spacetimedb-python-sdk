#!/usr/bin/env python3
"""
Test script to discover how to interact with SpacetimeDB v1.1.2 databases
"""

import requests
import json

HOST = "http://localhost:3000"

def test_database_endpoints():
    """Test various database-related endpoints"""
    print("=" * 80)
    print("Testing SpacetimeDB v1.1.2 Database Endpoints")
    print("=" * 80)
    
    # Test different HTTP methods on /v1/database
    methods = ['GET', 'POST', 'PUT']
    for method in methods:
        print(f"\nTesting {method} /v1/database")
        try:
            response = requests.request(method, f"{HOST}/v1/database", timeout=5)
            print(f"  Status: {response.status_code}")
            if response.status_code < 400:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Try to list databases with various endpoints
    list_endpoints = [
        "/v1/databases",
        "/v1/database/list",
        "/api/v1/databases",
        "/databases",
        "/database/list"
    ]
    
    print("\n" + "-" * 40)
    print("Testing database listing endpoints:")
    for endpoint in list_endpoints:
        try:
            response = requests.get(f"{HOST}{endpoint}", timeout=5)
            print(f"\n{endpoint} - Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"\n{endpoint} - Error: {e}")
    
    # Try to get info about specific database
    print("\n" + "-" * 40)
    print("Testing database-specific endpoints:")
    databases = ["blackholio", "test"]
    for db in databases:
        endpoints = [
            f"/v1/database/{db}",
            f"/v1/database/{db}/info",
            f"/v1/database/{db}/status",
            f"/database/{db}",
            f"/api/v1/database/{db}"
        ]
        
        print(f"\nDatabase: {db}")
        for endpoint in endpoints:
            try:
                response = requests.get(f"{HOST}{endpoint}", timeout=5)
                print(f"  {endpoint} - Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"    Response: {response.text[:100]}")
            except Exception as e:
                print(f"  {endpoint} - Error: {e}")

def test_cli_commands():
    """Show CLI commands that might help"""
    print("\n" + "=" * 80)
    print("Suggested CLI Commands to Try:")
    print("=" * 80)
    
    print("\nTo check if SpacetimeDB CLI is available and list databases:")
    print("  spacetime list")
    print("  spacetime database list")
    
    print("\nTo publish a database:")
    print("  spacetime publish blackholio --clear-database")
    print("  spacetime publish blackholio")
    
    print("\nTo get database info:")
    print("  spacetime info blackholio")
    print("  spacetime describe blackholio")

if __name__ == "__main__":
    test_database_endpoints()
    test_cli_commands()
