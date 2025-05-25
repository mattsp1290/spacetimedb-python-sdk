"""
Example: WASM Integration for SpacetimeDB Python SDK

Demonstrates how to use the WASM integration infrastructure:
- Running a local SpacetimeDB server
- Publishing WASM modules
- Connecting clients to WASM databases
- Performance benchmarking
"""

import asyncio
import time
from pathlib import Path

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    configure_default_logging,
    logger
)
from spacetimedb_sdk.wasm_integration import (
    SpacetimeDBServer,
    SpacetimeDBConfig,
    WASMModule,
    WASMTestHarness,
    PerformanceBenchmark,
    find_sdk_test_module
)


class WASMIntegrationExample:
    """Examples demonstrating WASM integration usage."""
    
    def example_1_server_management(self):
        """Example 1: Managing a SpacetimeDB server for testing."""
        print("\n=== Example 1: Server Management ===")
        
        # Configure server
        config = SpacetimeDBConfig(
            listen_port=3000,
            log_level="debug",
            enable_telemetry=False
        )
        
        # Start server
        server = SpacetimeDBServer(config)
        
        try:
            print("Starting SpacetimeDB server...")
            server.start()
            print(f"✓ Server started on port {config.listen_port}")
            
            # Server is running
            print("Server is running, press Enter to stop...")
            input()
            
        finally:
            print("Stopping server...")
            server.stop()
            print("✓ Server stopped")
    
    def example_2_context_manager(self):
        """Example 2: Using server with context manager."""
        print("\n=== Example 2: Context Manager ===")
        
        config = SpacetimeDBConfig(listen_port=3001)
        
        # Server automatically starts and stops
        with SpacetimeDBServer(config) as server:
            print(f"✓ Server running on port {config.listen_port}")
            print("Doing work with server...")
            time.sleep(2)
        
        print("✓ Server automatically stopped")
    
    async def example_3_wasm_module_loading(self):
        """Example 3: Loading and inspecting WASM modules."""
        print("\n=== Example 3: WASM Module Loading ===")
        
        # Find SDK test module
        module_path = find_sdk_test_module()
        if not module_path:
            print("⚠ SDK test module not found")
            print("Set SPACETIMEDB_SDK_TEST_MODULE environment variable")
            return
        
        print(f"Found module at: {module_path}")
        
        # Load module
        module = WASMModule.from_file(module_path, "example_module")
        print(f"✓ Loaded module: {module.name}")
        
        # Get module info
        wasm_bytes = module.get_bytes()
        print(f"Module size: {len(wasm_bytes):,} bytes")
        print(f"WASM magic: {wasm_bytes[:4]}")
    
    async def example_4_test_harness(self):
        """Example 4: Using the test harness for integration testing."""
        print("\n=== Example 4: Test Harness ===")
        
        config = SpacetimeDBConfig(listen_port=3002)
        
        with SpacetimeDBServer(config) as server:
            # Create test harness
            harness = WASMTestHarness(server)
            await harness.setup()
            
            print("✓ Test harness ready")
            
            # In real usage, would publish modules and run tests
            print("Harness can now:")
            print("- Publish WASM modules")
            print("- Create client connections")
            print("- Run integration tests")
            
            await harness.teardown()
    
    async def example_5_publish_module(self):
        """Example 5: Publishing a WASM module to SpacetimeDB."""
        print("\n=== Example 5: Publishing WASM Module ===")
        
        module_path = find_sdk_test_module()
        if not module_path:
            print("⚠ SDK test module not found")
            return
        
        config = SpacetimeDBConfig(listen_port=3003)
        
        with SpacetimeDBServer(config) as server:
            harness = WASMTestHarness(server)
            await harness.setup()
            
            # Load module
            module = WASMModule.from_file(module_path)
            
            # Publish module
            print(f"Publishing {module.name}...")
            address = await harness.publish_module(module, "example_db")
            print(f"✓ Published to address: {address}")
            
            # Module is now running in SpacetimeDB
            print("Module is ready for client connections")
            
            await harness.teardown()
    
    async def example_6_client_connection(self):
        """Example 6: Connecting a client to a WASM database."""
        print("\n=== Example 6: Client Connection ===")
        
        module_path = find_sdk_test_module()
        if not module_path:
            print("⚠ SDK test module not found")
            return
        
        config = SpacetimeDBConfig(listen_port=3004)
        
        with SpacetimeDBServer(config) as server:
            harness = WASMTestHarness(server)
            await harness.setup()
            
            # Publish module
            module = WASMModule.from_file(module_path)
            address = await harness.publish_module(module, "client_test")
            
            # Create client
            print(f"Connecting to {address}...")
            client = await harness.create_client(address)
            print(f"✓ Client connected")
            print(f"  Identity: {client.identity.to_hex()[:16]}...")
            print(f"  Connection: {client.connection_id.to_uuid()}")
            
            # Client can now interact with database
            await asyncio.sleep(1)
            
            # Disconnect
            await client.disconnect()
            print("✓ Client disconnected")
            
            await harness.teardown()
    
    async def example_7_performance_benchmarking(self):
        """Example 7: Performance benchmarking WASM operations."""
        print("\n=== Example 7: Performance Benchmarking ===")
        
        benchmark = PerformanceBenchmark()
        
        # Simulate various operations
        print("Running performance tests...")
        
        # Module loading
        module_path = find_sdk_test_module()
        if module_path:
            with benchmark.measure("module_load"):
                module = WASMModule.from_file(module_path)
                _ = module.get_bytes()
        
        # Server operations
        config = SpacetimeDBConfig(listen_port=3005)
        
        with benchmark.measure("server_start"):
            server = SpacetimeDBServer(config)
            server.start()
        
        try:
            # Connection operations
            with benchmark.measure("client_connect"):
                client = (ModernSpacetimeDBClient.builder()
                         .with_uri(f"ws://localhost:{config.listen_port}")
                         .with_module_name("test")
                         .build())
                # Note: Would fail without real module
        except:
            pass
        
        server.stop()
        
        # Print report
        print("\n" + benchmark.report())
    
    async def example_8_database_context(self):
        """Example 8: Using database context manager."""
        print("\n=== Example 8: Database Context ===")
        
        module_path = find_sdk_test_module()
        if not module_path:
            print("⚠ SDK test module not found")
            return
        
        config = SpacetimeDBConfig(listen_port=3006)
        
        with SpacetimeDBServer(config) as server:
            harness = WASMTestHarness(server)
            await harness.setup()
            
            module = WASMModule.from_file(module_path)
            
            # Use database context
            async with harness.database_context(module, "context_test") as address:
                print(f"✓ Database published to: {address}")
                
                # Database is active within context
                client = await harness.create_client(address)
                print("✓ Client connected to database")
                
                # Do work...
                await asyncio.sleep(1)
                
                await client.disconnect()
            
            print("✓ Database context cleaned up")
            await harness.teardown()
    
    async def example_9_integration_test_pattern(self):
        """Example 9: Integration test pattern with WASM."""
        print("\n=== Example 9: Integration Test Pattern ===")
        
        # This shows how to structure an integration test
        
        async def test_user_management():
            """Test user management features."""
            config = SpacetimeDBConfig(listen_port=3007)
            
            with SpacetimeDBServer(config) as server:
                harness = WASMTestHarness(server)
                await harness.setup()
                
                # Assume we have a user management module
                # module = WASMModule.from_file("user_management.wasm")
                # address = await harness.publish_module(module)
                
                print("Test pattern:")
                print("1. Publish WASM module")
                print("2. Create client connection")
                print("3. Call reducers:")
                print("   - create_user('alice', 'alice@example.com')")
                print("   - update_user(user_id, {'status': 'active'})")
                print("4. Query tables:")
                print("   - SELECT * FROM users")
                print("5. Verify results")
                print("6. Clean up")
                
                await harness.teardown()
        
        # Run the test
        await test_user_management()
    
    async def example_10_multi_client_testing(self):
        """Example 10: Testing with multiple clients."""
        print("\n=== Example 10: Multi-Client Testing ===")
        
        module_path = find_sdk_test_module()
        if not module_path:
            print("⚠ SDK test module not found")
            return
        
        config = SpacetimeDBConfig(listen_port=3008)
        benchmark = PerformanceBenchmark()
        
        with SpacetimeDBServer(config) as server:
            harness = WASMTestHarness(server)
            await harness.setup()
            
            # Publish module
            module = WASMModule.from_file(module_path)
            address = await harness.publish_module(module, "multi_client_test")
            
            # Create multiple clients
            print("Creating multiple clients...")
            clients = []
            
            for i in range(3):
                with benchmark.measure(f"client_{i}_connect"):
                    client = await harness.create_client(address)
                    clients.append(client)
                    print(f"✓ Client {i} connected")
            
            print(f"\nTotal clients connected: {len(clients)}")
            
            # Simulate concurrent operations
            print("\nSimulating concurrent operations...")
            await asyncio.sleep(1)
            
            # Disconnect all
            print("\nDisconnecting clients...")
            for i, client in enumerate(clients):
                await client.disconnect()
                print(f"✓ Client {i} disconnected")
            
            await harness.teardown()
            
            # Show performance
            print("\n" + benchmark.report())


async def main():
    """Run all WASM integration examples."""
    # Configure logging
    configure_default_logging(debug=False)
    
    example = WASMIntegrationExample()
    
    print("SpacetimeDB WASM Integration Examples")
    print("=====================================")
    
    # Check if SpacetimeDB is available
    import shutil
    if not shutil.which("spacetimedb"):
        print("\n⚠️  SpacetimeDB not found in PATH!")
        print("Please install SpacetimeDB to run these examples.")
        print("Visit: https://spacetimedb.com/install")
        return
    
    # Basic examples (non-async)
    # example.example_1_server_management()  # Interactive
    example.example_2_context_manager()
    
    # Async examples
    await example.example_3_wasm_module_loading()
    await example.example_4_test_harness()
    
    # Advanced examples (require SDK test module)
    if find_sdk_test_module():
        await example.example_5_publish_module()
        await example.example_6_client_connection()
        await example.example_8_database_context()
        await example.example_10_multi_client_testing()
    else:
        print("\n⚠️  SDK test module not found!")
        print("To run advanced examples:")
        print("1. Get sdk_test_module.wasm from Go SDK")
        print("2. Set SPACETIMEDB_SDK_TEST_MODULE=/path/to/sdk_test_module.wasm")
    
    # Always run these
    await example.example_7_performance_benchmarking()
    await example.example_9_integration_test_pattern()
    
    print("\n✅ WASM Integration examples complete!")
    print("\nKey Features Demonstrated:")
    print("- SpacetimeDB server management")
    print("- WASM module loading and publishing")
    print("- Client connections to WASM databases")
    print("- Test harness for integration testing")
    print("- Performance benchmarking")
    print("- Multi-client testing patterns")


if __name__ == "__main__":
    asyncio.run(main()) 