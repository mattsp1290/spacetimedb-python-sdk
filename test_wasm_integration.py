"""
Test WASM integration foundation for SpacetimeDB Python SDK.

This test file demonstrates the WASM integration infrastructure.
"""

import asyncio
import pytest
from pathlib import Path

from spacetimedb_sdk.wasm_integration import (
    SpacetimeDBServer,
    SpacetimeDBConfig,
    WASMModule,
    WASMTestHarness,
    PerformanceBenchmark,
    find_sdk_test_module,
    require_spacetimedb,
    require_sdk_test_module
)
from spacetimedb_sdk import configure_default_logging


# Configure logging for tests
configure_default_logging(debug=True)


class TestWASMIntegrationFoundation:
    """Test the WASM integration foundation."""
    
    def test_spacetimedb_config(self):
        """Test SpacetimeDB configuration."""
        # Default config
        config = SpacetimeDBConfig()
        assert config.listen_port == 3000
        assert config.log_level == "info"
        assert config.enable_telemetry is False
        assert config.data_dir is not None
        
        # Custom config
        custom_config = SpacetimeDBConfig(
            listen_port=3001,
            log_level="debug"
        )
        assert custom_config.listen_port == 3001
        assert custom_config.log_level == "debug"
    
    @pytest.mark.skipif(
        not find_sdk_test_module(),
        reason="sdk_test_module.wasm not found"
    )
    def test_wasm_module_loading(self):
        """Test WASM module loading."""
        module_path = find_sdk_test_module()
        assert module_path is not None
        
        # Load module
        module = WASMModule.from_file(module_path, "test")
        assert module.name == "test"
        assert module.path == module_path
        
        # Get bytes
        wasm_bytes = module.get_bytes()
        assert len(wasm_bytes) > 0
        assert wasm_bytes[:4] == b'\x00asm'  # WASM magic number
    
    @pytest.mark.integration
    @pytest.mark.skipif(
        not Path("/usr/local/bin/spacetimedb").exists(),
        reason="SpacetimeDB not installed"
    )
    async def test_spacetimedb_server(self):
        """Test SpacetimeDB server management."""
        require_spacetimedb()
        
        config = SpacetimeDBConfig(listen_port=3002)
        server = SpacetimeDBServer(config)
        
        # Start server
        server.start()
        assert server._started is True
        assert server.process is not None
        
        # Stop server
        server.stop()
        assert server._started is False
        assert server.process is None
    
    @pytest.mark.integration
    async def test_server_context_manager(self):
        """Test SpacetimeDB server as context manager."""
        require_spacetimedb()
        
        config = SpacetimeDBConfig(listen_port=3003)
        
        with SpacetimeDBServer(config) as server:
            assert server._started is True
            # Server is running
        
        # Server should be stopped
        assert server._started is False
    
    def test_performance_benchmark(self):
        """Test performance benchmarking."""
        benchmark = PerformanceBenchmark()
        
        # Measure some operations
        import time
        
        with benchmark.measure("fast_op"):
            time.sleep(0.01)
        
        with benchmark.measure("slow_op"):
            time.sleep(0.05)
        
        # Multiple measurements
        for _ in range(3):
            with benchmark.measure("repeated_op"):
                time.sleep(0.02)
        
        # Check stats
        fast_stats = benchmark.get_stats("fast_op")
        assert fast_stats["count"] == 1
        assert 0.01 <= fast_stats["mean"] <= 0.02
        
        slow_stats = benchmark.get_stats("slow_op")
        assert slow_stats["count"] == 1
        assert 0.05 <= slow_stats["mean"] <= 0.06
        
        repeated_stats = benchmark.get_stats("repeated_op")
        assert repeated_stats["count"] == 3
        assert 0.02 <= repeated_stats["mean"] <= 0.03
        
        # Test report
        report = benchmark.report()
        assert "Performance Benchmark Report" in report
        assert "fast_op" in report
        assert "slow_op" in report
        assert "repeated_op" in report


@pytest.mark.integration
@pytest.mark.wasm
class TestWASMHarness:
    """Test the WASM test harness with real SpacetimeDB."""
    
    async def test_wasm_harness_setup(self):
        """Test WASM harness setup and teardown."""
        require_spacetimedb()
        
        config = SpacetimeDBConfig(listen_port=3004)
        server = SpacetimeDBServer(config)
        
        harness = WASMTestHarness(server)
        
        # Setup
        await harness.setup()
        assert harness.server._started is True
        
        # Teardown
        await harness.teardown()
        harness.server.stop()
    
    @pytest.mark.skipif(
        not find_sdk_test_module(),
        reason="sdk_test_module.wasm not found"
    )
    async def test_publish_module(self):
        """Test publishing a WASM module."""
        require_spacetimedb()
        require_sdk_test_module()
        
        config = SpacetimeDBConfig(listen_port=3005)
        
        with SpacetimeDBServer(config) as server:
            harness = WASMTestHarness(server)
            await harness.setup()
            
            # Load test module
            module = WASMModule.from_file(require_sdk_test_module())
            
            # Publish module
            address = await harness.publish_module(module, "test_db")
            assert address is not None
            assert len(address) > 0
            
            await harness.teardown()
    
    @pytest.mark.slow
    @pytest.mark.skipif(
        not find_sdk_test_module(),
        reason="sdk_test_module.wasm not found"
    )
    async def test_full_integration_flow(self):
        """Test full integration flow with WASM module."""
        require_spacetimedb()
        require_sdk_test_module()
        
        config = SpacetimeDBConfig(listen_port=3006)
        benchmark = PerformanceBenchmark()
        
        with SpacetimeDBServer(config) as server:
            harness = WASMTestHarness(server)
            await harness.setup()
            
            # Load and publish module
            module = WASMModule.from_file(require_sdk_test_module())
            
            with benchmark.measure("publish_module"):
                async with harness.database_context(module, "integration_test") as address:
                    print(f"Published to address: {address}")
                    
                    # Create client
                    with benchmark.measure("create_client"):
                        client = await harness.create_client(address)
                    
                    assert client is not None
                    assert client.connected
                    
                    # Wait for connection to stabilize
                    await asyncio.sleep(0.5)
                    
                    # In real test, would call reducers and verify results
                    # For now, just verify connection works
                    
                    # Disconnect
                    await client.disconnect()
            
            await harness.teardown()
            
            # Print performance report
            print("\n" + benchmark.report())


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_find_sdk_test_module(self):
        """Test finding SDK test module."""
        # This might return None if module not found
        module_path = find_sdk_test_module()
        
        if module_path:
            assert module_path.exists()
            assert module_path.suffix == ".wasm"
            print(f"Found SDK test module at: {module_path}")
        else:
            print("SDK test module not found (this is OK for CI)")


def main():
    """Run basic integration tests."""
    print("Testing WASM Integration Foundation")
    print("===================================")
    
    # Test config
    test = TestWASMIntegrationFoundation()
    test.test_spacetimedb_config()
    print("✓ SpacetimeDB config works")
    
    # Test module loading if available
    if find_sdk_test_module():
        test.test_wasm_module_loading()
        print("✓ WASM module loading works")
    else:
        print("⚠ SDK test module not found - skipping module tests")
    
    # Test performance benchmark
    test.test_performance_benchmark()
    print("✓ Performance benchmarking works")
    
    print("\n✅ WASM Integration Foundation is ready!")
    print("\nTo run full integration tests:")
    print("1. Install SpacetimeDB")
    print("2. Set SPACETIMEDB_SDK_TEST_MODULE to point to sdk_test_module.wasm")
    print("3. Run: pytest test_wasm_integration.py -v -m integration")


if __name__ == "__main__":
    main() 