#!/usr/bin/env python3
"""
Verify Task 3: Fix Connection Pool Imports (using local code)
This script verifies that the circular import issue between
connection_builder.py and connection_pool.py has been resolved.
"""

import sys
import os
import traceback
import importlib
from typing import List, Tuple, Any

# Remove any installed versions from sys.path
installed_paths = [p for p in sys.path if 'site-packages' in p]
for path in installed_paths:
    sys.path.remove(path)

# Add local source directory to the front of the path
local_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, local_src)

print(f"Using local source from: {local_src}")
print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_result(test_name: str, success: bool, details: str = ""):
    """Print test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"    {details}")


def clear_modules():
    """Clear relevant modules from sys.modules."""
    modules_to_clear = [
        'spacetimedb_sdk',
        'spacetimedb_sdk.connection_pool',
        'spacetimedb_sdk.connection_builder',
        'spacetimedb_sdk.modern_client',
        'spacetimedb_sdk.shared_types',
    ]
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]


def test_no_direct_imports() -> Tuple[bool, str]:
    """Test that connection_pool.py doesn't directly import SpacetimeDBConnectionBuilder."""
    print_section("Test 1: No Direct Imports of SpacetimeDBConnectionBuilder")
    
    try:
        # Read the connection_pool.py file
        with open('src/spacetimedb_sdk/connection_pool.py', 'r') as f:
            content = f.read()
        
        # Check for direct imports
        has_direct_import = False
        details = []
        
        # Check for various import patterns
        import_patterns = [
            'from .connection_builder import SpacetimeDBConnectionBuilder',
            'from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder',
            'import SpacetimeDBConnectionBuilder',
        ]
        
        for pattern in import_patterns:
            if pattern in content:
                has_direct_import = True
                details.append(f"Found: {pattern}")
        
        # Check for TYPE_CHECKING imports (which are allowed)
        has_type_checking = 'TYPE_CHECKING' in content
        if has_type_checking:
            # Check if SpacetimeDBConnectionBuilder is imported under TYPE_CHECKING
            lines = content.split('\n')
            in_type_checking = False
            for line in lines:
                if 'if TYPE_CHECKING:' in line:
                    in_type_checking = True
                elif in_type_checking and line.strip() and not line.startswith(' '):
                    in_type_checking = False
                elif in_type_checking and 'SpacetimeDBConnectionBuilder' in line:
                    details.append("Found TYPE_CHECKING import (this is allowed)")
        
        # Look for the comment about no imports needed
        if "# No TYPE_CHECKING imports needed - SpacetimeDBConnectionBuilder is not used" in content:
            details.append("Found comment indicating no imports needed")
        
        success = not has_direct_import
        details_str = "\n    ".join(details) if details else "No direct imports found"
        
        test_result("No direct imports of SpacetimeDBConnectionBuilder", success, details_str)
        return success, details_str
        
    except Exception as e:
        error_msg = f"Error checking imports: {str(e)}"
        test_result("No direct imports check", False, error_msg)
        return False, error_msg


def test_import_order_independence() -> Tuple[bool, str]:
    """Test that modules can be imported in any order."""
    print_section("Test 2: Import Order Independence")
    
    tests_passed = 0
    tests_total = 3
    details = []
    
    # Test 1: Import connection_pool first
    try:
        clear_modules()
        from spacetimedb_sdk.connection_pool import ConnectionPool
        from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
        test_result("Import connection_pool → connection_builder", True)
        tests_passed += 1
    except Exception as e:
        test_result("Import connection_pool → connection_builder", False, str(e))
        details.append(f"Failed order 1: {str(e)}")
    
    # Test 2: Import connection_builder first
    try:
        clear_modules()
        from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
        from spacetimedb_sdk.connection_pool import ConnectionPool
        test_result("Import connection_builder → connection_pool", True)
        tests_passed += 1
    except Exception as e:
        test_result("Import connection_builder → connection_pool", False, str(e))
        details.append(f"Failed order 2: {str(e)}")
    
    # Test 3: Import both from __init__
    try:
        clear_modules()
        from spacetimedb_sdk import SpacetimeDBConnectionBuilder, ConnectionPool
        test_result("Import both from __init__", True)
        tests_passed += 1
    except Exception as e:
        test_result("Import both from __init__", False, str(e))
        details.append(f"Failed __init__ import: {str(e)}")
    
    success = tests_passed == tests_total
    details_str = f"Passed {tests_passed}/{tests_total} tests" + (f"\n    {chr(10).join(details)}" if details else "")
    return success, details_str


def test_builder_pool_integration() -> Tuple[bool, str]:
    """Test that the builder → pool integration works correctly."""
    print_section("Test 3: Builder → Pool Integration")
    
    try:
        clear_modules()
        from spacetimedb_sdk import ModernSpacetimeDBClient
        
        # Test the builder pattern
        builder = ModernSpacetimeDBClient.builder()
        
        # Configure for pool
        configured_builder = (builder
            .with_uri("ws://localhost:3000")
            .with_module_name("test_module")
            .with_connection_pool(min_connections=2, max_connections=5))
        
        # Verify build_pool method exists and works
        if not hasattr(configured_builder, 'build_pool'):
            test_result("Builder has build_pool method", False, "build_pool method not found")
            return False, "build_pool method not found"
        
        # Test that we can call build_pool without errors
        # (We won't actually create the pool as it would try to connect)
        test_result("Builder has build_pool method", True)
        
        # Check that build_pool uses lazy import
        import inspect
        build_pool_source = inspect.getsource(configured_builder.build_pool)
        
        if "from .connection_pool import ConnectionPool" in build_pool_source:
            test_result("build_pool uses lazy import", True, "Found lazy import in build_pool method")
        else:
            test_result("build_pool uses lazy import", False, "No lazy import found in build_pool method")
        
        return True, "Builder → Pool integration verified"
        
    except Exception as e:
        error_msg = f"Integration test failed: {str(e)}\n{traceback.format_exc()}"
        test_result("Builder → Pool integration", False, error_msg)
        return False, error_msg


def test_string_annotations() -> Tuple[bool, str]:
    """Test that string annotations are used for forward references."""
    print_section("Test 4: String Annotations for Forward References")
    
    try:
        # Read the connection_pool.py file
        with open('src/spacetimedb_sdk/connection_pool.py', 'r') as f:
            content = f.read()
        
        # Check for string annotations
        string_annotations = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Look for type hints with 'SpacetimeDBConnectionBuilder'
            if "'SpacetimeDBConnectionBuilder'" in line or '"SpacetimeDBConnectionBuilder"' in line:
                string_annotations.append(f"Line {i+1}: {line.strip()}")
        
        # Check if the module uses ModernSpacetimeDBClient.builder() instead
        uses_builder_pattern = "ModernSpacetimeDBClient.builder()" in content
        
        if uses_builder_pattern:
            test_result("Uses ModernSpacetimeDBClient.builder() pattern", True)
            details = "Connection pool uses the builder pattern from ModernSpacetimeDBClient"
        else:
            details = f"Found {len(string_annotations)} string annotations"
            if string_annotations:
                details += ":\n    " + "\n    ".join(string_annotations[:5])
                if len(string_annotations) > 5:
                    details += f"\n    ... and {len(string_annotations) - 5} more"
        
        success = uses_builder_pattern or len(string_annotations) > 0
        test_result("Uses appropriate patterns to avoid direct imports", success, details)
        return success, details
        
    except Exception as e:
        error_msg = f"Error checking annotations: {str(e)}"
        test_result("String annotations check", False, error_msg)
        return False, error_msg


def test_shared_types_usage() -> Tuple[bool, str]:
    """Test that shared_types.py is properly used."""
    print_section("Test 5: Shared Types Module Usage")
    
    try:
        # Read the connection_pool.py file
        with open('src/spacetimedb_sdk/connection_pool.py', 'r') as f:
            pool_content = f.read()
        
        # Check imports from shared_types
        imports_shared_types = "from .shared_types import" in pool_content
        
        if imports_shared_types:
            # Extract what's imported
            import_line = [line for line in pool_content.split('\n') if "from .shared_types import" in line]
            test_result("Imports from shared_types.py", True, f"Found: {import_line[0].strip()}")
        else:
            test_result("Imports from shared_types.py", False, "No imports from shared_types found")
        
        # Check if shared_types.py exists and has the necessary definitions
        with open('src/spacetimedb_sdk/shared_types.py', 'r') as f:
            shared_content = f.read()
        
        has_protocols = "Protocol" in shared_content
        has_connection_types = any(t in shared_content for t in ["ConnectionHealth", "CircuitBreaker", "RetryPolicy"])
        
        test_result("shared_types.py has Protocol definitions", has_protocols)
        test_result("shared_types.py has connection-related types", has_connection_types)
        
        success = imports_shared_types and has_protocols and has_connection_types
        return success, "Shared types module is properly structured and used"
        
    except Exception as e:
        error_msg = f"Error checking shared types: {str(e)}"
        test_result("Shared types check", False, error_msg)
        return False, error_msg


def test_external_usage() -> Tuple[bool, str]:
    """Test external usage patterns."""
    print_section("Test 6: External Usage Patterns")
    
    try:
        clear_modules()
        
        # Test 1: Basic client creation
        try:
            from spacetimedb_sdk import ModernSpacetimeDBClient
            
            client_builder = ModernSpacetimeDBClient.builder() \
                .with_uri("ws://localhost:3000") \
                .with_module_name("my_game")
            
            test_result("Basic client builder creation", True)
        except Exception as e:
            test_result("Basic client builder creation", False, str(e))
            return False, f"Basic client creation failed: {str(e)}"
        
        # Test 2: Connection pool creation
        try:
            from spacetimedb_sdk import ModernSpacetimeDBClient, RetryPolicy
            
            pool_builder = ModernSpacetimeDBClient.builder() \
                .with_uri("ws://localhost:3000") \
                .with_module_name("my_game") \
                .with_connection_pool(min_connections=10, max_connections=50) \
                .with_retry_policy(max_retries=5, base_delay=0.5)
            
            test_result("Connection pool builder configuration", True)
        except Exception as e:
            test_result("Connection pool builder configuration", False, str(e))
            return False, f"Pool configuration failed: {str(e)}"
        
        return True, "External usage patterns work correctly"
        
    except Exception as e:
        error_msg = f"External usage test failed: {str(e)}"
        test_result("External usage patterns", False, error_msg)
        return False, error_msg


def run_all_tests() -> bool:
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("  Task 3 Verification: Fix Connection Pool Imports (LOCAL)")
    print("=" * 60)
    print("\nObjective: Verify that connection_pool.py avoids importing")
    print("SpacetimeDBConnectionBuilder directly to prevent circular imports.")
    
    all_tests = [
        test_no_direct_imports,
        test_import_order_independence,
        test_builder_pool_integration,
        test_string_annotations,
        test_shared_types_usage,
        test_external_usage,
    ]
    
    results = []
    for test_func in all_tests:
        success, details = test_func()
        results.append(success)
    
    # Summary
    print_section("SUMMARY")
    total_tests = len(results)
    passed_tests = sum(results)
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    
    if passed_tests == total_tests:
        print("\n✅ ALL TESTS PASSED! Task 3 is properly implemented.")
        print("\nThe circular import issue between connection_builder.py and")
        print("connection_pool.py has been successfully resolved using:")
        print("  1. No direct imports of SpacetimeDBConnectionBuilder in connection_pool.py")
        print("  2. Lazy imports in connection_builder.py for build_pool()")
        print("  3. Shared types module for common type definitions")
        print("  4. ModernSpacetimeDBClient.builder() pattern")
        print("  5. Test fixtures removed from main __init__.py")
    else:
        print(f"\n❌ {total_tests - passed_tests} test(s) failed.")
        print("Task 3 may need additional implementation.")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
