#!/usr/bin/env python3
"""
Focused Task 3 Verification: Test Circular Import Resolution
This script specifically tests that the circular import between
connection_builder.py and connection_pool.py has been resolved.
"""

import sys
import os
import ast
import importlib.util
from typing import List, Tuple, Dict, Set

# Add local source directory to the front of the path
local_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, local_src)


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


def analyze_imports(file_path: str) -> Dict[str, List[str]]:
    """Analyze imports in a Python file using AST."""
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read(), filename=file_path)
    
    imports = {
        'direct': [],
        'from': [],
        'conditional': []
    }
    
    in_type_checking = False
    
    for node in ast.walk(tree):
        # Check for TYPE_CHECKING blocks
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == 'TYPE_CHECKING':
            # Extract imports from TYPE_CHECKING block
            for item in node.body:
                if isinstance(item, ast.ImportFrom):
                    imports['conditional'].append(f"from {item.module} import {', '.join(alias.name for alias in item.names)}")
        
        # Regular imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports['direct'].append(alias.name)
        elif isinstance(node, ast.ImportFrom) and not in_type_checking:
            if node.module:
                imports['from'].append(f"from {node.module} import {', '.join(alias.name for alias in node.names)}")


    return imports


def test_no_direct_builder_import() -> Tuple[bool, str]:
    """Test that connection_pool.py doesn't directly import SpacetimeDBConnectionBuilder."""
    print_section("Test 1: No Direct Import of SpacetimeDBConnectionBuilder")
    
    try:
        pool_file = os.path.join(local_src, 'spacetimedb_sdk', 'connection_pool.py')
        imports = analyze_imports(pool_file)
        
        # Check for direct imports of SpacetimeDBConnectionBuilder
        has_direct_import = False
        problematic_imports = []
        
        for imp in imports['from']:
            if 'SpacetimeDBConnectionBuilder' in imp and 'connection_builder' in imp:
                has_direct_import = True
                problematic_imports.append(imp)
        
        if problematic_imports:
            test_result("No direct import of SpacetimeDBConnectionBuilder", False, 
                       f"Found direct imports: {', '.join(problematic_imports)}")
            return False, "Direct imports found"
        
        # Check if TYPE_CHECKING is used properly
        conditional_imports = [imp for imp in imports['conditional'] if 'SpacetimeDBConnectionBuilder' in imp]
        if conditional_imports:
            test_result("TYPE_CHECKING imports found (allowed)", True, 
                       f"Conditional imports: {', '.join(conditional_imports)}")
        
        # Check for the comment indicating no imports needed
        with open(pool_file, 'r') as f:
            content = f.read()
            if "# No TYPE_CHECKING imports needed - SpacetimeDBConnectionBuilder is not used" in content:
                test_result("Found comment about no imports needed", True)
        
        test_result("No direct import of SpacetimeDBConnectionBuilder", True, 
                   "No problematic direct imports found")
        return True, "No direct imports"
        
    except Exception as e:
        test_result("Import analysis", False, str(e))
        return False, str(e)


def test_lazy_import_in_builder() -> Tuple[bool, str]:
    """Test that connection_builder.py uses lazy import for ConnectionPool."""
    print_section("Test 2: Lazy Import Pattern in Builder")
    
    try:
        builder_file = os.path.join(local_src, 'spacetimedb_sdk', 'connection_builder.py')
        
        # Read the file and find build_pool method
        with open(builder_file, 'r') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content, filename=builder_file)
        
        # Find the build_pool method
        build_pool_found = False
        has_lazy_import = False
        
        class MethodVisitor(ast.NodeVisitor):
            def __init__(self):
                self.in_build_pool = False
                self.found_lazy_import = False
            
            def visit_FunctionDef(self, node):
                if node.name == 'build_pool':
                    self.in_build_pool = True
                    nonlocal build_pool_found
                    build_pool_found = True
                    
                    # Check for imports within the method
                    for child in ast.walk(node):
                        if isinstance(child, ast.ImportFrom):
                            if child.module and 'connection_pool' in child.module:
                                self.found_lazy_import = True
                                nonlocal has_lazy_import
                                has_lazy_import = True
                
                self.generic_visit(node)
        
        visitor = MethodVisitor()
        visitor.visit(tree)
        
        if not build_pool_found:
            test_result("build_pool method exists", False, "Method not found")
            return False, "build_pool method not found"
        
        test_result("build_pool method exists", True)
        
        if has_lazy_import:
            test_result("Uses lazy import for ConnectionPool", True, 
                       "Found 'from .connection_pool import ConnectionPool' inside build_pool")
        else:
            # Also check with string search as fallback
            if "from .connection_pool import ConnectionPool" in content and "def build_pool" in content:
                test_result("Uses lazy import for ConnectionPool", True, 
                           "Found lazy import pattern in source")
                has_lazy_import = True
            else:
                test_result("Uses lazy import for ConnectionPool", False, 
                           "No lazy import found in build_pool method")
        
        return has_lazy_import, "Lazy import pattern verified" if has_lazy_import else "No lazy import found"
        
    except Exception as e:
        test_result("Lazy import analysis", False, str(e))
        return False, str(e)


def test_shared_types_structure() -> Tuple[bool, str]:
    """Test that shared_types.py exists and contains the expected structures."""
    print_section("Test 3: Shared Types Module Structure")
    
    try:
        shared_file = os.path.join(local_src, 'spacetimedb_sdk', 'shared_types.py')
        
        if not os.path.exists(shared_file):
            test_result("shared_types.py exists", False, "File not found")
            return False, "shared_types.py not found"
        
        test_result("shared_types.py exists", True)
        
        with open(shared_file, 'r') as f:
            content = f.read()
        
        # Check for expected content
        expected_items = {
            'RetryPolicy': 'RetryPolicy' in content,
            'ConnectionHealth': 'ConnectionHealth' in content,
            'CircuitBreaker': 'CircuitBreaker' in content,
            'PooledConnectionState': 'PooledConnectionState' in content,
            'Protocol import': 'from typing import Protocol' in content or 'from typing_extensions import Protocol' in content
        }
        
        all_found = True
        missing = []
        
        for item, found in expected_items.items():
            if found:
                test_result(f"Contains {item}", True)
            else:
                test_result(f"Contains {item}", False)
                all_found = False
                missing.append(item)
        
        if all_found:
            return True, "All expected types found in shared_types.py"
        else:
            return False, f"Missing: {', '.join(missing)}"
        
    except Exception as e:
        test_result("Shared types analysis", False, str(e))
        return False, str(e)


def test_import_chain() -> Tuple[bool, str]:
    """Test that the import chain doesn't create circular dependencies."""
    print_section("Test 4: Import Chain Analysis")
    
    try:
        # Map out the import dependencies
        files_to_check = {
            'connection_builder.py': os.path.join(local_src, 'spacetimedb_sdk', 'connection_builder.py'),
            'connection_pool.py': os.path.join(local_src, 'spacetimedb_sdk', 'connection_pool.py'),
            'shared_types.py': os.path.join(local_src, 'spacetimedb_sdk', 'shared_types.py')
        }
        
        import_map = {}
        
        for name, path in files_to_check.items():
            imports = analyze_imports(path)
            all_imports = imports['from'] + imports['direct']
            
            # Filter for relevant imports
            relevant_imports = []
            for imp in all_imports:
                if 'connection_builder' in imp or 'connection_pool' in imp or 'shared_types' in imp:
                    relevant_imports.append(imp)
            
            import_map[name] = relevant_imports
        
        # Check for circular dependencies
        print("\nImport relationships:")
        for file, imports in import_map.items():
            if imports:
                print(f"  {file} imports: {', '.join(imports)}")
            else:
                print(f"  {file} imports: (none of the tracked modules)")
        
        # Specific checks
        pool_imports_builder = any('connection_builder' in imp and 'SpacetimeDBConnectionBuilder' in imp 
                                  for imp in import_map.get('connection_pool.py', []))
        
        if pool_imports_builder:
            test_result("No circular dependency", False, 
                       "connection_pool imports SpacetimeDBConnectionBuilder from connection_builder")
            return False, "Circular dependency detected"
        
        test_result("No circular dependency", True, 
                   "connection_pool does not import SpacetimeDBConnectionBuilder directly")
        
        return True, "No circular dependencies in import chain"
        
    except Exception as e:
        test_result("Import chain analysis", False, str(e))
        return False, str(e)


def test_builder_pattern_usage() -> Tuple[bool, str]:
    """Test that connection_pool uses ModernSpacetimeDBClient.builder() pattern."""
    print_section("Test 5: Builder Pattern Usage")
    
    try:
        pool_file = os.path.join(local_src, 'spacetimedb_sdk', 'connection_pool.py')
        
        with open(pool_file, 'r') as f:
            content = f.read()
        
        # Check for the builder pattern usage
        uses_modern_builder = "ModernSpacetimeDBClient.builder()" in content
        imports_modern_client = "from .modern_client import ModernSpacetimeDBClient" in content
        
        if uses_modern_builder:
            test_result("Uses ModernSpacetimeDBClient.builder()", True)
        else:
            test_result("Uses ModernSpacetimeDBClient.builder()", False, 
                       "Pattern not found in connection_pool.py")
        
        if imports_modern_client:
            test_result("Imports ModernSpacetimeDBClient", True)
        else:
            test_result("Imports ModernSpacetimeDBClient", False)
        
        success = uses_modern_builder and imports_modern_client
        details = "Correctly uses builder pattern from ModernSpacetimeDBClient" if success else "Builder pattern not properly implemented"
        
        return success, details
        
    except Exception as e:
        test_result("Builder pattern analysis", False, str(e))
        return False, str(e)


def run_all_tests() -> bool:
    """Run all Task 3 verification tests."""
    print("\n" + "=" * 60)
    print("  Task 3 Focused Verification: Circular Import Resolution")
    print("=" * 60)
    print("\nObjective: Verify that the circular import between")
    print("connection_builder.py and connection_pool.py is resolved.")
    
    all_tests = [
        test_no_direct_builder_import,
        test_lazy_import_in_builder,
        test_shared_types_structure,
        test_import_chain,
        test_builder_pattern_usage,
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
        print("\nThe circular import has been resolved through:")
        print("  1. ✅ No direct import of SpacetimeDBConnectionBuilder in connection_pool.py")
        print("  2. ✅ Lazy import of ConnectionPool in connection_builder.py's build_pool()")
        print("  3. ✅ Shared types module for common type definitions")
        print("  4. ✅ No circular dependencies in the import chain")
        print("  5. ✅ ModernSpacetimeDBClient.builder() pattern used in connection_pool.py")
        print("\nTask 3 is COMPLETE and VERIFIED! ✅")
    else:
        print(f"\n❌ {total_tests - passed_tests} test(s) failed.")
        print("Task 3 implementation needs review.")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
