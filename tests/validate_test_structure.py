#!/usr/bin/env python3
"""
Validate test structure and count test cases.

This script validates the test structure without importing the full SDK.
"""
import ast
import sys
from pathlib import Path
from collections import defaultdict

def count_test_functions(file_path):
    """Count test functions in a Python file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        test_functions = []
        test_classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                test_functions.append(node.name)
            elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                test_classes.append(node.name)
                # Count methods in test classes
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                        test_functions.append(f"{node.name}::{item.name}")
        
        return test_functions, test_classes
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return [], []

def validate_test_structure():
    """Validate the test structure."""
    test_dir = Path(__file__).parent
    
    # Test directories to validate
    test_dirs = {
        'security': test_dir / 'security',
        'integration': test_dir / 'integration', 
        'performance': test_dir / 'performance',
        'property': test_dir / 'property'
    }
    
    results = defaultdict(dict)
    total_tests = 0
    total_classes = 0
    
    print("SpacetimeDB Python SDK - Test Structure Validation")
    print("=" * 60)
    
    for category, dir_path in test_dirs.items():
        print(f"\n{category.upper()} Tests:")
        print("-" * 40)
        
        if not dir_path.exists():
            print(f"  Directory not found: {dir_path}")
            continue
        
        category_tests = 0
        category_classes = 0
        
        for test_file in dir_path.glob('test_*.py'):
            functions, classes = count_test_functions(test_file)
            category_tests += len(functions)
            category_classes += len(classes)
            
            print(f"  {test_file.name}:")
            print(f"    Test functions: {len(functions)}")
            print(f"    Test classes: {len(classes)}")
            
            if functions:
                print(f"    Functions: {', '.join(functions[:5])}")
                if len(functions) > 5:
                    print(f"    ... and {len(functions) - 5} more")
        
        print(f"  Total for {category}: {category_tests} tests, {category_classes} classes")
        total_tests += category_tests
        total_classes += category_classes
        
        results[category] = {
            'tests': category_tests,
            'classes': category_classes
        }
    
    # Check existing test files
    print(f"\nEXISTING Tests:")
    print("-" * 40)
    existing_tests = 0
    for test_file in test_dir.glob('test_*.py'):
        if test_file.name != 'test_validation.py':
            functions, classes = count_test_functions(test_file)
            existing_tests += len(functions)
            print(f"  {test_file.name}: {len(functions)} tests, {len(classes)} classes")
    
    print(f"  Total existing: {existing_tests} tests")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"New test categories: {len(test_dirs)}")
    print(f"Total new tests: {total_tests}")
    print(f"Total new classes: {total_classes}")
    print(f"Total existing tests: {existing_tests}")
    print(f"Grand total: {total_tests + existing_tests} tests")
    
    # Test coverage analysis
    print(f"\n{'='*60}")
    print("COVERAGE ANALYSIS")
    print(f"{'='*60}")
    
    coverage_areas = {
        'Security': results['security']['tests'],
        'Integration': results['integration']['tests'],
        'Performance': results['performance']['tests'], 
        'Property-based': results['property']['tests'],
        'Existing': existing_tests
    }
    
    for area, count in coverage_areas.items():
        percentage = (count / (total_tests + existing_tests)) * 100 if total_tests + existing_tests > 0 else 0
        print(f"{area:<15}: {count:3d} tests ({percentage:5.1f}%)")
    
    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")
    
    if total_tests < 50:
        print("⚠️  Consider adding more tests to reach 90%+ coverage")
    else:
        print("✅ Good test coverage with comprehensive test suite")
    
    if results['security']['tests'] < 10:
        print("⚠️  Security tests could be expanded")
    else:
        print("✅ Comprehensive security test coverage")
    
    if results['performance']['tests'] < 5:
        print("⚠️  Performance tests could be expanded")
    else:
        print("✅ Good performance test coverage")
    
    if results['property']['tests'] < 5:
        print("⚠️  Property-based tests could be expanded")
    else:
        print("✅ Good property-based test coverage")
    
    return total_tests > 0

if __name__ == "__main__":
    success = validate_test_structure()
    sys.exit(0 if success else 1)