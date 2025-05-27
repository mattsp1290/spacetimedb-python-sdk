#!/usr/bin/env python3
"""
Verification script for circular import issue in SpacetimeDB Python SDK

This script tests various import scenarios to document the circular import problem.
"""

import sys
import traceback
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_import(description: str, import_func):
    """Test an import and report the result."""
    print(f"\n{'='*60}")
    print(f"Test: {description}")
    print('='*60)
    
    try:
        import_func()
        print("✅ SUCCESS: Import completed without errors")
        return True
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        print("\nTraceback:")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("\nTraceback:")
        traceback.print_exc()
        return False

def main():
    """Run all import tests."""
    print("SpacetimeDB Python SDK - Circular Import Verification")
    print("="*60)
    
    results = []
    
    # Test 1: Basic SDK import
    results.append(test_import(
        "Basic SDK Import",
        lambda: __import__('spacetimedb_sdk')
    ))
    
    # Test 2: Import SpacetimeDBClient
    results.append(test_import(
        "Import SpacetimeDBClient",
        lambda: exec("from spacetimedb_sdk import SpacetimeDBClient")
    ))
    
    # Test 3: Import connection builder directly
    results.append(test_import(
        "Import SpacetimeDBConnectionBuilder directly",
        lambda: exec("from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder")
    ))
    
    # Test 4: Import connection pool directly
    results.append(test_import(
        "Import ConnectionPool directly",
        lambda: exec("from spacetimedb_sdk.connection_pool import ConnectionPool")
    ))
    
    # Test 5: Import test fixtures
    results.append(test_import(
        "Import test fixtures from main package",
        lambda: exec("from spacetimedb_sdk import TestDatabase")
    ))
    
    # Test 6: Try builder pattern
    def test_builder():
        from spacetimedb_sdk import SpacetimeDBClient
        builder = SpacetimeDBClient.builder()
        print(f"Builder instance created: {builder}")
    
    results.append(test_import(
        "SpacetimeDBClient.builder() pattern",
        test_builder
    ))
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == 0:
        print("\n⚠️  CRITICAL: All imports are failing due to circular dependencies!")
        print("\nRoot cause:")
        print("1. connection_builder.py imports from connection_pool.py")
        print("2. connection_pool.py imports from connection_builder.py")
        print("3. This creates a circular dependency that prevents module loading")
        
        print("\nRecommended immediate fix:")
        print("1. In connection_pool.py, change the import to use TYPE_CHECKING:")
        print("   from typing import TYPE_CHECKING")
        print("   if TYPE_CHECKING:")
        print("       from .connection_builder import SpacetimeDBConnectionBuilder")
        print("2. Remove test_fixtures imports from __init__.py")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
