"""
Example: JSON API Support for SpacetimeDB Python SDK

Demonstrates HTTP/JSON API usage:
- Database management operations
- Identity information retrieval
- HTTP-based reducer calls
- Module information queries
- SQL query execution
- Async and sync patterns
- Error handling
- Performance monitoring
"""

import asyncio
import time
from typing import List, Dict, Any

from spacetimedb_sdk import ModernSpacetimeDBClient
from spacetimedb_sdk.json_api import (
    SpacetimeDBJsonAPI,
    ApiResponse,
    DatabaseInfo,
    ModuleInfo,
    ReducerCallResult
)


class JsonApiExample:
    """Example demonstrating JSON API capabilities."""
    
    def __init__(self):
        # Initialize client with JSON API support
        self.client = (ModernSpacetimeDBClient.builder()
                      .with_uri("ws://localhost:3000")
                      .with_module_name("example_module")
                      .with_json_api_base_url("http://localhost:3000")
                      .build())
        
        # Direct JSON API access
        self.json_api = self.client.json_api
        
        # Enable request logging for debugging
        self.json_api.enable_request_logging(True)
    
    def example_1_list_databases(self):
        """Example 1: List all available databases."""
        print("\n=== Example 1: List Databases ===")
        
        # Synchronous approach
        response = self.json_api.list_databases_sync()
        
        if response.success:
            print(f"Found {len(response.data)} databases:")
            for db in response.data:
                print(f"  - {db.name}")
                print(f"    Address: {db.address}")
                print(f"    Host: {db.host}")
                print(f"    Tables: {db.num_tables}")
                print(f"    Reducers: {db.num_reducers}")
        else:
            print(f"Error: {response.error}")
    
    def example_2_database_info(self):
        """Example 2: Get detailed information about a specific database."""
        print("\n=== Example 2: Database Information ===")
        
        response = self.json_api.get_database_info_sync("example_db")
        
        if response.success:
            db = response.data
            print(f"Database: {db.name}")
            print(f"Address: {db.address}")
            print(f"Owner: {db.owner_identity}")
            print(f"Created: {db.created_at}")
        else:
            print(f"Error: {response.error}")
            print(f"Status Code: {response.status_code}")
    
    def example_3_http_reducer_call(self):
        """Example 3: Call a reducer via HTTP."""
        print("\n=== Example 3: HTTP Reducer Call ===")
        
        # Call a reducer with arguments
        response = self.json_api.call_reducer_http_sync(
            database_name="example_db",
            reducer_name="create_user",
            args=["Alice", "alice@example.com", 25]
        )
        
        if response.success:
            result = response.data
            print(f"Request ID: {result.request_id}")
            print(f"Execution time: {result.execution_time_ms:.2f}ms")
            print(f"Energy used: {result.energy_used}")
            print(f"Result: {result.result}")
        else:
            print(f"Error: {response.error}")
    
    async def example_4_async_operations(self):
        """Example 4: Async operations for better performance."""
        print("\n=== Example 4: Async Operations ===")
        
        # Execute multiple operations concurrently
        tasks = [
            self.json_api.list_databases(),
            self.json_api.get_database_info("example_db"),
            self.json_api.get_module_info("example_db")
        ]
        
        start_time = time.time()
        responses = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        print(f"Completed {len(responses)} operations in {elapsed:.2f}s")
        
        # Process responses
        for i, response in enumerate(responses):
            if response.success:
                print(f"  Operation {i+1}: Success")
            else:
                print(f"  Operation {i+1}: Failed - {response.error}")
    
    def example_5_sql_queries(self):
        """Example 5: Execute SQL queries via HTTP."""
        print("\n=== Example 5: SQL Query Execution ===")
        
        # Note: This would be an async operation in real usage
        # Using sync wrapper for example simplicity
        queries = [
            "SELECT COUNT(*) as user_count FROM users",
            "SELECT * FROM users WHERE active = true LIMIT 10",
            "SELECT table_name FROM information_schema.tables"
        ]
        
        for query in queries:
            print(f"\nQuery: {query}")
            # In real implementation, use async version
            # response = await self.json_api.execute_sql("example_db", query)
            print("  (Would execute via HTTP API)")
    
    def example_6_error_handling(self):
        """Example 6: Error handling and retries."""
        print("\n=== Example 6: Error Handling ===")
        
        # Try to access non-existent database
        response = self.json_api.get_database_info_sync("non_existent_db")
        
        if not response.success:
            print(f"Expected error: {response.error}")
            print(f"Status code: {response.status_code}")
            
            # Check metrics to see retry attempts
            metrics = self.json_api.get_metrics()
            print(f"Total retry attempts: {metrics['total_retry_attempts']}")
    
    def example_7_performance_monitoring(self):
        """Example 7: Monitor API performance."""
        print("\n=== Example 7: Performance Monitoring ===")
        
        # Reset metrics
        self.json_api.reset_metrics()
        
        # Perform some operations
        for i in range(5):
            self.json_api.list_databases_sync()
        
        # Get performance metrics
        metrics = self.json_api.get_metrics()
        
        print("API Performance Metrics:")
        print(f"  Requests sent: {metrics['requests_sent']}")
        print(f"  Success rate: {metrics['success_rate']:.2%}")
        print(f"  Average response time: {metrics['average_response_time_ms']:.2f}ms")
        print(f"  Failed requests: {metrics['requests_failed']}")
        print(f"  Retry attempts: {metrics['total_retry_attempts']}")
    
    def example_8_request_logging(self):
        """Example 8: Request/response logging for debugging."""
        print("\n=== Example 8: Request Logging ===")
        
        # Clear previous logs
        self.json_api.clear_logs()
        
        # Make a request
        self.json_api.get_identity_info()
        
        # Get logs
        request_logs = self.json_api.get_request_logs()
        response_logs = self.json_api.get_response_logs()
        
        if request_logs:
            req = request_logs[0]
            print(f"Request: {req['method']} {req['url']}")
            print(f"Headers: {req['headers']}")
        
        if response_logs:
            resp = response_logs[0]
            print(f"Response: {resp['status_code']} in {resp['response_time_ms']:.2f}ms")
    
    def example_9_standalone_api_client(self):
        """Example 9: Using JSON API client standalone."""
        print("\n=== Example 9: Standalone JSON API Client ===")
        
        # Create standalone client for admin operations
        with SpacetimeDBJsonAPI(
            base_url="https://api.spacetimedb.com",
            auth_token="admin_token",
            timeout=60.0,
            max_retries=5
        ) as admin_api:
            print("Admin API client created")
            # Perform admin operations
            # response = admin_api.list_databases_sync()
            print("  (Would perform admin operations)")
    
    async def example_10_mixed_usage(self):
        """Example 10: Combining WebSocket and HTTP operations."""
        print("\n=== Example 10: Mixed WebSocket + HTTP Usage ===")
        
        print("Use cases for each protocol:")
        print("  WebSocket: Real-time subscriptions, live updates")
        print("  HTTP/JSON: One-off queries, admin tasks, stateless operations")
        
        # Example: Use HTTP for initial data load
        print("\n1. Load initial data via HTTP:")
        db_info = await self.json_api.get_database_info("example_db")
        if db_info.success:
            print(f"   Loaded database: {db_info.data.name}")
        
        # Example: Use WebSocket for live updates
        print("\n2. Subscribe to live updates via WebSocket:")
        print("   client.subscribe(['SELECT * FROM messages'])")
        
        # Example: Use HTTP for occasional admin tasks
        print("\n3. Perform admin task via HTTP:")
        module_info = await self.json_api.get_module_info("example_db")
        if module_info.success:
            print(f"   Module version: {module_info.data.version}")


def run_sync_examples():
    """Run synchronous examples."""
    example = JsonApiExample()
    
    # Run sync examples
    example.example_1_list_databases()
    example.example_2_database_info()
    example.example_3_http_reducer_call()
    example.example_5_sql_queries()
    example.example_6_error_handling()
    example.example_7_performance_monitoring()
    example.example_8_request_logging()
    example.example_9_standalone_api_client()


async def run_async_examples():
    """Run asynchronous examples."""
    example = JsonApiExample()
    
    # Run async examples
    await example.example_4_async_operations()
    await example.example_10_mixed_usage()


def main():
    """Run all JSON API examples."""
    print("SpacetimeDB JSON API Examples")
    print("=============================")
    
    # Run synchronous examples
    run_sync_examples()
    
    # Run asynchronous examples
    print("\n" + "="*50 + "\n")
    asyncio.run(run_async_examples())
    
    print("\n✅ JSON API examples complete!")
    print("\nKey Benefits:")
    print("- No persistent connection required")
    print("- Stateless operations")
    print("- Easy integration with existing HTTP infrastructure")
    print("- Suitable for admin tasks and one-off queries")
    print("- Complements WebSocket for hybrid architectures")


if __name__ == "__main__":
    main() 