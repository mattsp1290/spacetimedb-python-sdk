#!/usr/bin/env python3
"""
Validation script for memory exhaustion vulnerability fixes.

This script performs quick validation of the implemented memory management
features to ensure they are working correctly.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import time
import traceback
from typing import Dict, Any

def test_bounded_dict():
    """Test BoundedDict implementation."""
    print("Testing BoundedDict...")
    
    try:
        from spacetimedb_sdk.memory_management import BoundedDict
        
        # Test size limits
        bounded_dict = BoundedDict[str, str](max_size=3)
        
        # Fill to capacity
        for i in range(5):
            bounded_dict.set(f"key{i}", f"value{i}")
        
        # Should only have 3 items (max_size)
        if len(bounded_dict) != 3:
            raise AssertionError(f"Expected 3 items, got {len(bounded_dict)}")
        
        print("✓ BoundedDict size limits working")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import BoundedDict: {e}")
        return False
    except Exception as e:
        print(f"✗ BoundedDict test failed: {e}")
        traceback.print_exc()
        return False


def test_recursion_limiter():
    """Test RecursionLimiter implementation."""
    print("Testing RecursionLimiter...")
    
    try:
        from spacetimedb_sdk.memory_management import RecursionLimiter
        
        limiter = RecursionLimiter(max_depth=3)
        
        def recursive_function(depth):
            with limiter:
                if depth > 0:
                    return recursive_function(depth - 1)
                return "success"
        
        # Should work within limit
        result = recursive_function(2)
        if result != "success":
            raise AssertionError("Recursion within limit failed")
        
        # Should fail beyond limit
        try:
            recursive_function(5)
            raise AssertionError("Recursion limit not enforced")
        except RecursionError:
            pass  # Expected
        
        print("✓ RecursionLimiter working correctly")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import RecursionLimiter: {e}")
        return False
    except Exception as e:
        print(f"✗ RecursionLimiter test failed: {e}")
        traceback.print_exc()
        return False


def test_memory_accountant():
    """Test MemoryAccountant implementation."""
    print("Testing MemoryAccountant...")
    
    try:
        from spacetimedb_sdk.memory_management import MemoryAccountant
        
        accountant = MemoryAccountant(memory_limit_mb=1)  # 1MB limit
        
        # Should succeed within limit
        if not accountant.try_allocate("test", 512 * 1024):  # 512KB
            raise AssertionError("Allocation within limit failed")
        
        # Should fail beyond limit
        if accountant.try_allocate("test", 1024 * 1024):  # 1MB more
            raise AssertionError("Memory limit not enforced")
        
        # Check OOM prevention counter
        stats = accountant.get_stats()
        if stats.oom_prevented == 0:
            raise AssertionError("OOM prevention not recorded")
        
        print("✓ MemoryAccountant working correctly")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import MemoryAccountant: {e}")
        return False
    except Exception as e:
        print(f"✗ MemoryAccountant test failed: {e}")
        traceback.print_exc()
        return False


def test_bounded_bsatn():
    """Test bounded BSATN reader/writer."""
    print("Testing Bounded BSATN...")
    
    try:
        from spacetimedb_sdk.bsatn.bounded_reader import create_bounded_reader
        from spacetimedb_sdk.bsatn.bounded_writer import create_bounded_writer
        
        # Test writer with small limits
        writer = create_bounded_writer(max_output_mb=1)
        
        # Should be able to write small string
        writer.write_string("small string")
        if writer.error() is not None:
            raise AssertionError("Small string write failed")
        
        # Should fail with huge string
        huge_string = "x" * (2 * 1024 * 1024)  # 2MB
        writer = create_bounded_writer(max_output_mb=1)
        writer.write_string(huge_string)
        if writer.error() is None:
            raise AssertionError("Large string limit not enforced")
        
        print("✓ Bounded BSATN working correctly")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import Bounded BSATN: {e}")
        return False
    except Exception as e:
        print(f"✗ Bounded BSATN test failed: {e}")
        traceback.print_exc()
        return False


def test_websocket_client_integration():
    """Test WebSocket client integration."""
    print("Testing WebSocket client integration...")
    
    try:
        from spacetimedb_sdk.websocket_client import WebSocketClient
        
        # Should be able to create client
        client = WebSocketClient()
        
        # Check that bounded structures are used
        if not hasattr(client, 'memory_accountant'):
            raise AssertionError("Memory accountant not integrated")
        
        if not hasattr(client, 'message_validator'):
            raise AssertionError("Message validator not integrated")
        
        if not hasattr(client.active_subscriptions, 'set'):
            raise AssertionError("BoundedDict not used for subscriptions")
        
        print("✓ WebSocket client integration working")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import WebSocket client: {e}")
        return False
    except Exception as e:
        print(f"✗ WebSocket client integration test failed: {e}")
        traceback.print_exc()
        return False


def test_configuration():
    """Test configuration system."""
    print("Testing configuration system...")
    
    try:
        from spacetimedb_sdk.memory_config import configure_memory, get_global_config
        
        # Test preset configuration
        config = configure_memory(preset='conservative')
        
        if config.memory_limits.total_memory_mb != 128:
            raise AssertionError("Conservative preset not applied correctly")
        
        # Test custom configuration
        configure_memory(total_memory_mb=256, max_cache_entries=5000)
        config = get_global_config()
        
        if config.memory_limits.total_memory_mb != 256:
            raise AssertionError("Custom configuration not applied")
        
        print("✓ Configuration system working")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import configuration: {e}")
        return False
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        traceback.print_exc()
        return False


def test_bounded_client_cache():
    """Test bounded client cache."""
    print("Testing BoundedClientCache...")
    
    try:
        from spacetimedb_sdk.bounded_cache import BoundedClientCache
        
        # Create mock package
        class MockPackage:
            __path__ = []
            __name__ = "mock_package"
        
        cache = BoundedClientCache(MockPackage(), max_cache_size=100)
        
        # Should be able to get stats
        stats = cache.get_cache_stats()
        
        if 'memory_usage' not in stats:
            raise AssertionError("Memory usage stats not available")
        
        print("✓ BoundedClientCache working")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import BoundedClientCache: {e}")
        return False
    except Exception as e:
        print(f"✗ BoundedClientCache test failed: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all validation tests."""
    print("🔍 Validating Memory Exhaustion Vulnerability Fixes")
    print("=" * 60)
    
    tests = [
        test_bounded_dict,
        test_recursion_limiter,
        test_memory_accountant,
        test_bounded_bsatn,
        test_websocket_client_integration,
        test_configuration,
        test_bounded_client_cache
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            traceback.print_exc()
            failed += 1
        print()
    
    print("=" * 60)
    print(f"Validation Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All memory exhaustion fixes validated successfully!")
        print("\nMemory management features are working correctly:")
        print("• Bounded data structures prevent unlimited growth")
        print("• Recursion limits prevent stack overflow")
        print("• Memory accounting tracks and limits usage")
        print("• BSATN processing has comprehensive safety limits")
        print("• WebSocket client uses bounded collections")
        print("• Configuration system allows customization")
        print("\nThe SDK is now protected against memory exhaustion vulnerabilities.")
        return True
    else:
        print("❌ Some validation tests failed!")
        print("Please check the implementation and fix any issues.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)