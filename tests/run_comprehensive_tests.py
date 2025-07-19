#!/usr/bin/env python3
"""
Comprehensive test runner for all test categories.

Runs security, integration, performance, and property-based tests
with detailed reporting and coverage analysis.
"""
import subprocess
import sys
import time
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    start_time = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    duration = time.time() - start_time
    
    print(f"Duration: {duration:.2f}s")
    print(f"Return code: {result.returncode}")
    
    if result.stdout:
        print(f"\nSTDOUT:\n{result.stdout}")
    
    if result.stderr:
        print(f"\nSTDERR:\n{result.stderr}")
    
    return result.returncode == 0

def main():
    """Run comprehensive test suite."""
    # Change to test directory
    test_dir = Path(__file__).parent
    os.chdir(test_dir)
    
    print("SpacetimeDB Python SDK - Comprehensive Test Suite")
    print("=" * 60)
    
    # Test categories to run
    test_categories = [
        {
            "name": "Unit Tests",
            "command": "python -m pytest test_*.py -m 'unit' -v",
            "description": "Run unit tests"
        },
        {
            "name": "Security Tests",
            "command": "python -m pytest security/ -m 'security' -v",
            "description": "Run security tests"
        },
        {
            "name": "Integration Tests",
            "command": "python -m pytest integration/ -m 'integration' -v",
            "description": "Run integration tests"
        },
        {
            "name": "Performance Tests",
            "command": "python -m pytest performance/ -m 'performance' -v --tb=short",
            "description": "Run performance tests"
        },
        {
            "name": "Property-Based Tests",
            "command": "python -m pytest property/ -m 'property' -v",
            "description": "Run property-based tests"
        },
        {
            "name": "Coverage Report",
            "command": "python -m pytest --cov=../src/spacetimedb_sdk --cov-report=term-missing --cov-report=html:../htmlcov",
            "description": "Generate coverage report"
        }
    ]
    
    # Results tracking
    results = {}
    total_start = time.time()
    
    # Run each test category
    for category in test_categories:
        success = run_command(category["command"], category["description"])
        results[category["name"]] = success
    
    total_duration = time.time() - total_start
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for category_name, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"{category_name:<25} {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal Categories: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total Duration: {total_duration:.2f}s")
    
    # Additional reports
    print("\n" + "="*60)
    print("ADDITIONAL REPORTS")
    print("="*60)
    
    # Test files created
    test_files = [
        "security/test_input_validation.py",
        "integration/test_complete_workflows.py", 
        "integration/test_cross_component.py",
        "performance/test_performance_regression.py",
        "property/test_bounded_cache.py",
        "property/test_event_system.py"
    ]
    
    print(f"\nTest files created: {len(test_files)}")
    for test_file in test_files:
        file_path = Path(test_file)
        if file_path.exists():
            lines = len(file_path.read_text().splitlines())
            print(f"  {test_file}: {lines} lines")
        else:
            print(f"  {test_file}: NOT FOUND")
    
    # Coverage information
    coverage_file = Path("../htmlcov/index.html")
    if coverage_file.exists():
        print(f"\nCoverage report: {coverage_file.absolute()}")
    
    # Return appropriate exit code
    if failed == 0:
        print("\n🎉 All test categories passed!")
        return 0
    else:
        print(f"\n❌ {failed} test category(ies) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())