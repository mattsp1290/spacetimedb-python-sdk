#!/usr/bin/env python3
"""
Optimized test runner for spacetimedb-python-sdk.

This script provides optimized test execution with parallel processing,
reduced overhead, and performance-focused configurations.
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def run_tests_optimized():
    """Run tests with optimized configuration for speed."""
    
    # Base optimized pytest arguments
    base_args = [
        sys.executable, "-m", "pytest",
        "--tb=no",  # No traceback for speed
        "-q",  # Quiet mode
        "--disable-warnings",  # Disable warnings for speed
        "--no-header",  # No header for speed
        "--no-summary",  # No summary for speed
        "-x",  # Stop on first failure
        "--maxfail=3",  # Stop after 3 failures max
        "--timeout=30",  # 30 second timeout per test
        "--timeout-method=thread",
        "-n", "auto",  # Parallel execution
        "--dist=loadscope",  # Better distribution
        "--durations=5",  # Show only top 5 slowest tests
    ]
    
    # Add test path
    test_path = Path(__file__).parent / "tests"
    base_args.append(str(test_path))
    
    print("Running optimized test suite...")
    print(f"Command: {' '.join(base_args)}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(base_args, cwd=Path(__file__).parent)
        end_time = time.time()
        
        print(f"\nTest execution completed in {end_time - start_time:.2f} seconds")
        
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print(f"❌ Tests failed with exit code {result.returncode}")
            
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

def run_tests_quick():
    """Run only fast unit tests for quick feedback."""
    
    quick_args = [
        sys.executable, "-m", "pytest",
        "--tb=no", "-q", "--disable-warnings",
        "-x", "--maxfail=1",
        "--timeout=10",  # Very short timeout
        "-n", "auto",
        "-m", "unit",  # Only unit tests
        "tests/"
    ]
    
    print("Running quick unit tests...")
    start_time = time.time()
    
    try:
        result = subprocess.run(quick_args, cwd=Path(__file__).parent)
        end_time = time.time()
        
        print(f"Quick tests completed in {end_time - start_time:.2f} seconds")
        return result.returncode
        
    except Exception as e:
        print(f"Error running quick tests: {e}")
        return 1

def run_tests_with_coverage():
    """Run tests with coverage but optimized settings."""
    
    coverage_args = [
        sys.executable, "-m", "pytest",
        "--tb=short", "-v",
        "--disable-warnings",  
        "--maxfail=5",
        "--timeout=60",
        "-n", "auto",
        "--cov=src/spacetimedb_sdk",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=html:htmlcov",
        "--cov-fail-under=80",  # Require 80% coverage
        "tests/"
    ]
    
    print("Running tests with coverage...")
    start_time = time.time()
    
    try:
        result = subprocess.run(coverage_args, cwd=Path(__file__).parent)
        end_time = time.time()
        
        print(f"Coverage tests completed in {end_time - start_time:.2f} seconds")
        return result.returncode
        
    except Exception as e:
        print(f"Error running coverage tests: {e}")
        return 1

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimized test runner")
    parser.add_argument("--quick", action="store_true", 
                       help="Run only quick unit tests")
    parser.add_argument("--coverage", action="store_true",
                       help="Run tests with coverage")
    
    args = parser.parse_args()
    
    if args.quick:
        exit_code = run_tests_quick()
    elif args.coverage:
        exit_code = run_tests_with_coverage()
    else:
        exit_code = run_tests_optimized()
    
    sys.exit(exit_code)