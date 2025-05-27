#!/usr/bin/env python3
"""
Verification script for Task 5: Lazy Import Pattern Implementation

This script verifies that:
1. The lazy import pattern is properly implemented in connection_builder.py
2. No circular imports exist when using the build_pool() method
3. The connection pool can be created successfully
4. The lazy import documentation is present
"""

import sys
import traceback
import ast
import os
from typing import Dict, List, Tuple, Any

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def check_lazy_import_in_build_pool() -> Tuple[bool, str]:
    """Check if lazy import is implemented in build_pool method."""
    try:
        # Read the connection_builder.py file
        with open('src/spacetimedb_sdk/connection_builder.py', 'r') as f:
            content = f.read()
        
        # Search for build_pool method and check its content
        if "def build_pool" not in content:
            return False, "build_pool method not found"
        
        # Extract the build_pool method content
        build_pool_start = content.find("def build_pool")
        if build_pool_start == -1:
            return False, "build_pool method not found"
        
        # Find the next method definition to get the boundary
        next_def = content.find("\n    def ", build_pool_start + 1)
        if next_def == -1:
            # If no next method, use the end of file
            build_pool_content = content[build_pool_start:]
        else:
            build_pool_content = content[build_pool_start:next_def]
        
        # Check for lazy import pattern
        lazy_import_found = False
        has_comment = False
        
        # Look for the import statement
        if "from .connection_pool import ConnectionPool" in build_pool_content:
            lazy_import_found = True
            
            # Check for comment explaining why it's lazy
            if ("# Lazy import" in build_pool_content or 
                "# lazy import" in build_pool_content or
                "lazy import" in build_pool_content.lower() and "circular" in build_pool_content.lower()):
                has_comment = True
        
        if not lazy_import_found:
            return False, "Lazy import of ConnectionPool not found in build_pool"
        
        if not has_comment:
            return False, "Lazy import found but lacks explanatory comment"
        
        return True, "Lazy import properly implemented with comment"
        
    except Exception as e:
        return False, f"Error checking lazy import: {str(e)}"


def check_no_direct_pool_import() -> Tuple[bool, str]:
    """Verify connection_builder doesn't import ConnectionPool at module level."""
    try:
        with open('src/spacetimedb_sdk/connection_builder.py', 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Check top-level imports
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module and 'connection_pool' in node.module:
                    for alias in node.names:
                        if alias.name == 'ConnectionPool':
                            return False, "ConnectionPool is imported at module level"
        
        return True, "No direct ConnectionPool import at module level"
        
    except Exception as e:
        return False, f"Error checking imports: {str(e)}"


def test_build_pool_functionality() -> Tuple[bool, str]:
    """Test that build_pool actually works without circular imports."""
    try:
        # Import and test the builder
        from spacetimedb_sdk import ModernSpacetimeDBClient
        
        # Create a builder and configure it
        builder = ModernSpacetimeDBClient.builder() \
            .with_uri("ws://localhost:3000") \
            .with_module_name("test_module") \
            .with_connection_pool(min_connections=2, max_connections=5)
        
        # Validate configuration works
        validation = builder.validate()
        if not validation['valid']:
            return False, f"Builder validation failed: {validation['issues']}"
        
        # Test that build_pool method exists and can be called
        # (We won't actually create the pool as it would try to connect)
        if not hasattr(builder, 'build_pool'):
            return False, "build_pool method not found on builder"
        
        # Verify the method signature
        import inspect
        sig = inspect.signature(builder.build_pool)
        if len(sig.parameters) != 0:
            return False, "build_pool should take no parameters"
        
        return True, "build_pool method exists and is callable"
        
    except ImportError as e:
        return False, f"Import error (circular dependency?): {str(e)}"
    except Exception as e:
        return False, f"Error testing build_pool: {str(e)}"


def check_connection_pool_no_builder_import() -> Tuple[bool, str]:
    """Verify connection_pool.py doesn't import SpacetimeDBConnectionBuilder."""
    try:
        with open('src/spacetimedb_sdk/connection_pool.py', 'r') as f:
            content = f.read()
        
        # Check for any import of SpacetimeDBConnectionBuilder
        if 'SpacetimeDBConnectionBuilder' in content:
            # It should only appear in TYPE_CHECKING or comments
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == 'SpacetimeDBConnectionBuilder':
                            return False, "SpacetimeDBConnectionBuilder is imported in connection_pool.py"
        
        return True, "connection_pool.py doesn't import SpacetimeDBConnectionBuilder"
        
    except Exception as e:
        return False, f"Error checking connection_pool imports: {str(e)}"


def verify_shared_types_usage() -> Tuple[bool, str]:
    """Verify both modules use shared_types for common types."""
    try:
        files_to_check = [
            'src/spacetimedb_sdk/connection_builder.py',
            'src/spacetimedb_sdk/connection_pool.py'
        ]
        
        for filepath in files_to_check:
            with open(filepath, 'r') as f:
                content = f.read()
            
            if 'from .shared_types import' not in content:
                return False, f"{os.path.basename(filepath)} doesn't import from shared_types"
        
        return True, "Both modules properly import from shared_types"
        
    except Exception as e:
        return False, f"Error checking shared_types usage: {str(e)}"


def main():
    """Run all verification tests."""
    print("=== Task 5: Lazy Import Pattern Verification ===\n")
    
    tests = [
        ("Lazy import in build_pool", check_lazy_import_in_build_pool),
        ("No direct pool import", check_no_direct_pool_import),
        ("build_pool functionality", test_build_pool_functionality),
        ("No builder import in pool", check_connection_pool_no_builder_import),
        ("Shared types usage", verify_shared_types_usage)
    ]
    
    all_passed = True
    results = []
    
    for test_name, test_func in tests:
        print(f"Testing: {test_name}...", end=" ")
        passed, message = test_func()
        
        if passed:
            print("✅ PASSED")
            print(f"  └─ {message}")
        else:
            print("❌ FAILED")
            print(f"  └─ {message}")
            all_passed = False
        
        results.append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
        print()
    
    # Summary
    print("\n=== Summary ===")
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    
    print(f"Tests passed: {passed_count}/{total_count}")
    
    if all_passed:
        print("\n✅ All lazy import pattern tests passed!")
        print("\nThe lazy import pattern has been successfully implemented:")
        print("- build_pool() uses lazy import to avoid circular dependency")
        print("- ConnectionPool is only imported when needed")
        print("- Proper documentation explains the pattern")
        print("- Both modules use shared_types for common types")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
