#!/usr/bin/env python3
"""
Validation script for Task 2: Create Shared Types Module
Tests that the circular import issue has been resolved in local source.
"""

import sys
import os
import traceback
from typing import List, Tuple, Optional

# Add the local source directory to the Python path FIRST
sys.path.insert(0, os.path.abspath('src'))

# Test results tracking
test_results: List[Tuple[str, bool, Optional[str]]] = []

def test(test_name: str):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper():
            try:
                func()
                test_results.append((test_name, True, None))
                print(f"✓ {test_name}")
                return True
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                test_results.append((test_name, False, error_msg))
                print(f"✗ {test_name}")
                print(f"  Error: {error_msg}")
                traceback.print_exc()
                return False
        return wrapper
    return decorator


@test("Test 1: Import spacetimedb_sdk package from local source")
def test_basic_import():
    """Test that the main package can be imported without errors."""
    import spacetimedb_sdk
    assert spacetimedb_sdk.__version__
    print(f"  Imported from: {spacetimedb_sdk.__file__}")


@test("Test 2: Import connection_builder module directly")
def test_import_connection_builder():
    """Test importing connection_builder module."""
    from spacetimedb_sdk import connection_builder
    assert hasattr(connection_builder, 'SpacetimeDBConnectionBuilder')


@test("Test 3: Import connection_pool module directly")
def test_import_connection_pool():
    """Test importing connection_pool module."""
    from spacetimedb_sdk import connection_pool
    assert hasattr(connection_pool, 'ConnectionPool')
    assert hasattr(connection_pool, 'LoadBalancedConnectionManager')


@test("Test 4: Import shared_types module")
def test_import_shared_types():
    """Test importing the new shared_types module."""
    from spacetimedb_sdk import shared_types
    assert hasattr(shared_types, 'RetryPolicy')
    assert hasattr(shared_types, 'PooledConnectionState')
    assert hasattr(shared_types, 'CircuitState')
    assert hasattr(shared_types, 'ConnectionHealth')
    assert hasattr(shared_types, 'CircuitBreaker')


@test("Test 5: Import SpacetimeDBClient from package")
def test_import_client():
    """Test importing the client from the main package."""
    from spacetimedb_sdk import SpacetimeDBClient
    assert SpacetimeDBClient


@test("Test 6: Import ModernSpacetimeDBClient")
def test_import_modern_client():
    """Test importing the modern client."""
    from spacetimedb_sdk import ModernSpacetimeDBClient
    assert ModernSpacetimeDBClient


@test("Test 7: Create connection builder")
def test_create_builder():
    """Test creating a connection builder."""
    from spacetimedb_sdk import ModernSpacetimeDBClient
    
    builder = ModernSpacetimeDBClient.builder()
    assert builder is not None
    
    # Test fluent API
    configured_builder = (
        builder
        .with_uri("ws://localhost:3000")
        .with_module_name("test_module")
        .with_token("test_token")
    )
    assert configured_builder is builder  # Should return self


@test("Test 8: Validate builder configuration")
def test_builder_validation():
    """Test builder validation without building."""
    from spacetimedb_sdk import ModernSpacetimeDBClient
    
    builder = (
        ModernSpacetimeDBClient.builder()
        .with_uri("ws://localhost:3000")
        .with_module_name("test_module")
    )
    
    validation = builder.validate()
    assert validation['valid'] == True
    assert len(validation['issues']) == 0
    assert validation['configuration']['uri'] == "ws://localhost:3000"
    assert validation['configuration']['module_name'] == "test_module"


@test("Test 9: Test connection pool configuration")
def test_connection_pool_config():
    """Test configuring connection pool via builder."""
    from spacetimedb_sdk import ModernSpacetimeDBClient
    
    builder = (
        ModernSpacetimeDBClient.builder()
        .with_uri("ws://localhost:3000")
        .with_module_name("test_module")
        .with_connection_pool(
            min_connections=5,
            max_connections=20,
            load_balancing_strategy="least_latency"
        )
        .with_retry_policy(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0
        )
    )
    
    # Should not raise any errors
    assert builder._use_connection_pool == True
    assert builder._pool_min_connections == 5
    assert builder._pool_max_connections == 20


@test("Test 10: Test RetryPolicy from shared_types")
def test_retry_policy():
    """Test RetryPolicy functionality."""
    from spacetimedb_sdk.shared_types import RetryPolicy
    
    policy = RetryPolicy(
        max_retries=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True
    )
    
    # Test delay calculation
    delay0 = policy.get_retry_delay(0)
    delay1 = policy.get_retry_delay(1)
    delay2 = policy.get_retry_delay(2)
    
    # Base delays should be 1, 2, 4 (exponential)
    # With jitter, they should be within 75%-125% of base
    assert 0.75 <= delay0 <= 1.25
    assert 1.5 <= delay1 <= 2.5
    assert 3.0 <= delay2 <= 5.0


@test("Test 11: Test ConnectionHealth from shared_types")
def test_connection_health():
    """Test ConnectionHealth functionality."""
    from spacetimedb_sdk.shared_types import ConnectionHealth, PooledConnectionState
    
    health = ConnectionHealth(
        connection_id="test-123",
        state=PooledConnectionState.IDLE,
        last_successful_operation=1234567890.0
    )
    
    # Record some operations
    health.record_success(10.5)
    health.record_success(12.3)
    health.record_failure()
    
    assert health.consecutive_successes == 0  # Reset by failure
    assert health.consecutive_failures == 1
    assert health.operations_count == 3
    assert len(health.latency_samples) == 2  # Only successes


@test("Test 12: Test CircuitBreaker from shared_types")
def test_circuit_breaker():
    """Test CircuitBreaker functionality."""
    from spacetimedb_sdk.shared_types import CircuitBreaker, CircuitState
    
    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=60.0,
        half_open_requests=2
    )
    
    assert breaker.state == CircuitState.CLOSED
    assert breaker.is_available() == True
    
    # Trigger failures to open circuit
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED  # Still closed
    
    breaker.record_failure()  # Third failure
    assert breaker.state == CircuitState.OPEN
    assert breaker.is_available() == False  # Not available when open


@test("Test 13: Verify no circular import in module loading")
def test_no_circular_import():
    """Verify modules can be loaded in any order without circular imports."""
    # Clear any cached imports
    modules_to_clear = [
        'spacetimedb_sdk.connection_builder',
        'spacetimedb_sdk.connection_pool',
        'spacetimedb_sdk.shared_types'
    ]
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    # Try importing in different orders
    # Order 1: pool -> builder
    from spacetimedb_sdk.connection_pool import ConnectionPool
    from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
    
    # Clear again
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    # Order 2: builder -> pool
    from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
    from spacetimedb_sdk.connection_pool import ConnectionPool
    
    # Both should work without errors
    assert ConnectionPool
    assert SpacetimeDBConnectionBuilder


@test("Test 14: Verify ConnectionBuilder doesn't have direct pool imports")
def test_builder_lazy_imports():
    """Check that connection_builder uses lazy imports for ConnectionPool."""
    import ast
    import os
    
    builder_path = os.path.join('src', 'spacetimedb_sdk', 'connection_builder.py')
    with open(builder_path, 'r') as f:
        content = f.read()
    
    tree = ast.parse(content)
    
    # Find TYPE_CHECKING blocks
    type_checking_blocks = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name):
            if node.test.id == 'TYPE_CHECKING':
                type_checking_blocks.append(node)
    
    # Check for direct imports (not in TYPE_CHECKING)
    direct_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and 'connection_pool' in node.module:
            # Check if this import is inside a TYPE_CHECKING block
            in_type_checking = False
            for tc_block in type_checking_blocks:
                if any(child == node for child in ast.walk(tc_block)):
                    in_type_checking = True
                    break
            
            if not in_type_checking:
                direct_imports.append(node)
    
    # There should be NO direct imports of ConnectionPool at module level
    # (only in TYPE_CHECKING or inside methods)
    assert len(direct_imports) == 0, f"Found {len(direct_imports)} direct imports of connection_pool at module level"


def print_summary():
    """Print test summary."""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success, _ in test_results if success)
    failed = sum(1 for _, success, _ in test_results if not success)
    total = len(test_results)
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nFailed tests:")
        for name, success, error in test_results:
            if not success:
                print(f"  - {name}")
                print(f"    Error: {error}")
    
    print("\n" + "="*60)
    return failed == 0


def main():
    """Run all tests."""
    print("="*60)
    print("Task 2 Validation: Create Shared Types Module (Local Source)")
    print("="*60)
    print()
    
    # Run all tests
    test_basic_import()
    test_import_connection_builder()
    test_import_connection_pool()
    test_import_shared_types()
    test_import_client()
    test_import_modern_client()
    test_create_builder()
    test_builder_validation()
    test_connection_pool_config()
    test_retry_policy()
    test_connection_health()
    test_circuit_breaker()
    test_no_circular_import()
    test_builder_lazy_imports()
    
    # Print summary
    success = print_summary()
    
    if success:
        print("\n✅ All tests passed! The circular import issue has been resolved.")
        print("\nKey achievements:")
        print("- Created shared_types.py module with common data structures")
        print("- Refactored connection_pool.py to use shared types and removed TYPE_CHECKING import")
        print("- Refactored connection_builder.py to use shared types and lazy imports")
        print("- Removed test_fixtures from __init__.py imports")
        print("- All imports work correctly without circular dependencies")
        print("- Builder pattern and connection pooling functionality preserved")
    else:
        print("\n❌ Some tests failed. Please review the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
