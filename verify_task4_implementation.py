#!/usr/bin/env python3
"""
Verify Task 4: Remove test_fixtures from Main Package Imports

This script validates that:
1. test_fixtures is not imported in __init__.py
2. The package can be imported without circular import errors
3. Test fixtures can still be imported directly when needed
4. The testing package structure is correct
"""

import ast
import sys
import traceback
from pathlib import Path
import importlib.util
import json
from datetime import datetime


def check_no_test_fixtures_in_init():
    """Check that test_fixtures is not imported in __init__.py"""
    init_path = Path("src/spacetimedb_sdk/__init__.py")
    
    with open(init_path, 'r') as f:
        content = f.read()
    
    # Parse the AST
    tree = ast.parse(content)
    
    # Check for test_fixtures imports
    test_fixtures_imported = False
    test_fixtures_in_all = False
    
    for node in ast.walk(tree):
        # Check import statements
        if isinstance(node, ast.ImportFrom):
            if node.module and 'test_fixtures' in node.module:
                test_fixtures_imported = True
                print(f"❌ Found import from test_fixtures: {ast.unparse(node)}")
        
        # Check __all__ assignments
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__all__':
                    if isinstance(node.value, ast.List):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                if 'TestDatabase' in str(elt.value) or \
                                   'TestIsolation' in str(elt.value) or \
                                   'CoverageTracker' in str(elt.value) or \
                                   'TestResultAggregator' in str(elt.value):
                                    test_fixtures_in_all = True
                                    print(f"❌ Found test fixture export in __all__: {elt.value}")
    
    # Check for comments about test_fixtures
    has_comment = "Test fixtures should not be imported in main package" in content
    
    return {
        'test_fixtures_imported': test_fixtures_imported,
        'test_fixtures_in_all': test_fixtures_in_all,
        'has_explanatory_comment': has_comment,
        'success': not test_fixtures_imported and not test_fixtures_in_all
    }


def check_package_imports():
    """Verify the package can be imported without errors"""
    try:
        # Add src to path
        sys.path.insert(0, 'src')
        
        # Try importing the package
        import spacetimedb_sdk
        print("✅ Successfully imported spacetimedb_sdk")
        
        # Check that SpacetimeDBClient is available
        assert hasattr(spacetimedb_sdk, 'SpacetimeDBClient')
        print("✅ SpacetimeDBClient is available")
        
        # Check that test fixtures are NOT available from main package
        has_test_fixtures = any([
            hasattr(spacetimedb_sdk, 'TestDatabase'),
            hasattr(spacetimedb_sdk, 'TestIsolation'),
            hasattr(spacetimedb_sdk, 'CoverageTracker'),
            hasattr(spacetimedb_sdk, 'TestResultAggregator')
        ])
        
        if has_test_fixtures:
            print("❌ Test fixtures are still available from main package")
            return False
        else:
            print("✅ Test fixtures are not available from main package")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to import package: {e}")
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if 'spacetimedb_sdk' in sys.modules:
            del sys.modules['spacetimedb_sdk']
        sys.path.pop(0)


def check_testing_package_structure():
    """Verify the testing package structure is correct"""
    results = {}
    
    # Check that test_fixtures directory exists
    testing_dir = Path("src/spacetimedb_sdk/test_fixtures")
    results['testing_dir_exists'] = testing_dir.exists()
    print(f"{'✅' if results['testing_dir_exists'] else '❌'} Test fixtures directory exists: {testing_dir}")
    
    # Check __init__.py exists
    testing_init = testing_dir / "__init__.py"
    results['testing_init_exists'] = testing_init.exists()
    print(f"{'✅' if results['testing_init_exists'] else '❌'} Test fixtures __init__.py exists: {testing_init}")
    
    # Check fixtures.py exists
    fixtures_file = testing_dir / "fixtures.py"
    results['fixtures_file_exists'] = fixtures_file.exists()
    print(f"{'✅' if results['fixtures_file_exists'] else '❌'} fixtures.py exists: {fixtures_file}")
    
    # Check that old test_fixtures.py is removed
    old_test_fixtures = Path("src/spacetimedb_sdk/test_fixtures.py")
    results['old_file_removed'] = not old_test_fixtures.exists()
    print(f"{'✅' if results['old_file_removed'] else '❌'} Old test_fixtures.py removed: {not old_test_fixtures.exists()}")
    
    results['success'] = all([
        results['testing_dir_exists'],
        results['testing_init_exists'],
        results['fixtures_file_exists'],
        results['old_file_removed']
    ])
    
    return results


def check_direct_import():
    """Verify test fixtures can be imported directly"""
    try:
        sys.path.insert(0, 'src')
        
        # Try importing from test_fixtures package
        from spacetimedb_sdk.test_fixtures import (
            TestDatabase,
            TestIsolation,
            CoverageTracker,
            TestResultAggregator,
            is_ci_environment,
            get_test_database_url,
            get_test_module_name
        )
        print("✅ Successfully imported test utilities from test_fixtures package")
        
        # Verify they are the expected types
        assert callable(is_ci_environment)
        assert callable(get_test_database_url)
        assert callable(get_test_module_name)
        assert isinstance(TestDatabase, type)
        assert isinstance(TestIsolation, type)
        assert isinstance(CoverageTracker, type)
        assert isinstance(TestResultAggregator, type)
        print("✅ All test utilities are available and have correct types")
        
        # Try importing fixtures directly
        from spacetimedb_sdk.test_fixtures.fixtures import CONFTEST_TEMPLATE
        assert isinstance(CONFTEST_TEMPLATE, str)
        assert "from spacetimedb_sdk.test_fixtures.fixtures import *" in CONFTEST_TEMPLATE
        print("✅ CONFTEST_TEMPLATE uses correct import path")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to import test fixtures: {e}")
        traceback.print_exc()
        return False
    finally:
        # Clean up
        modules_to_remove = [
            'spacetimedb_sdk.test_fixtures',
            'spacetimedb_sdk.test_fixtures.fixtures',
            'spacetimedb_sdk'
        ]
        for module in modules_to_remove:
            if module in sys.modules:
                del sys.modules[module]
        sys.path.pop(0)


def check_no_circular_imports():
    """Verify there are no circular imports"""
    try:
        # Clear any cached modules
        modules_to_clear = [k for k in sys.modules.keys() if k.startswith('spacetimedb_sdk')]
        for module in modules_to_clear:
            del sys.modules[module]
        
        sys.path.insert(0, 'src')
        
        # Import in the order that would expose circular imports
        import spacetimedb_sdk
        from spacetimedb_sdk import SpacetimeDBClient
        from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
        from spacetimedb_sdk.connection_pool import ConnectionPool
        
        print("✅ No circular imports detected")
        return True
        
    except ImportError as e:
        if "circular" in str(e).lower() or "partially initialized" in str(e):
            print(f"❌ Circular import detected: {e}")
            return False
        else:
            print(f"❌ Import error: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if 'spacetimedb_sdk' in sys.modules:
            del sys.modules['spacetimedb_sdk']
        sys.path.pop(0)


def main():
    """Run all validation checks"""
    print("=" * 60)
    print("Task 4 Validation: Remove test_fixtures from Main Package")
    print("=" * 60)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'checks': {}
    }
    
    # Check 1: No test_fixtures in __init__.py
    print("\n1. Checking __init__.py for test_fixtures imports...")
    init_check = check_no_test_fixtures_in_init()
    results['checks']['no_test_fixtures_in_init'] = init_check
    
    # Check 2: Package imports successfully
    print("\n2. Checking package imports...")
    results['checks']['package_imports'] = check_package_imports()
    
    # Check 3: Testing package structure
    print("\n3. Checking testing package structure...")
    structure_check = check_testing_package_structure()
    results['checks']['testing_package_structure'] = structure_check
    
    # Check 4: Direct imports work
    print("\n4. Checking direct imports of test fixtures...")
    results['checks']['direct_imports'] = check_direct_import()
    
    # Check 5: No circular imports
    print("\n5. Checking for circular imports...")
    results['checks']['no_circular_imports'] = check_no_circular_imports()
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = all([
        init_check['success'],
        results['checks']['package_imports'],
        structure_check['success'],
        results['checks']['direct_imports'],
        results['checks']['no_circular_imports']
    ])
    
    results['overall_success'] = all_passed
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED! Task 4 is complete.")
        print("\nKey achievements:")
        print("- test_fixtures removed from main package imports")
        print("- Testing utilities moved to separate testing package")
        print("- No circular imports")
        print("- Test fixtures can still be imported directly when needed")
    else:
        print("\n❌ Some checks failed. Please review the issues above.")
    
    # Save results
    with open('task4_validation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: task4_validation_results.json")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
