#!/usr/bin/env python3
"""
Script to find which test file is hanging by running each test file individually with a timeout.
"""

import subprocess
import sys
import glob
import time
from pathlib import Path

def run_test_with_timeout(test_file, timeout=30):
    """Run a single test file with timeout."""
    print(f"\n{'='*60}")
    print(f"Testing: {test_file}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Run pytest with timeout
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "--timeout=30", "-v"],
            capture_output=True,
            text=True,
            timeout=timeout + 5  # Add 5 seconds to subprocess timeout
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ PASSED in {elapsed:.2f}s")
        else:
            print(f"❌ FAILED in {elapsed:.2f}s")
            if "timeout" in result.stdout.lower() or "timeout" in result.stderr.lower():
                print("   (Test timed out)")
            
        return result.returncode, elapsed, False
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"⏰ TIMEOUT after {elapsed:.2f}s - This test is likely hanging!")
        return -1, elapsed, True

def main():
    # Get all test files
    test_files = sorted(glob.glob("test_*.py"))
    
    # Add test files from src/spacetimedb_sdk/tests/
    test_files.extend(sorted(glob.glob("src/spacetimedb_sdk/tests/test_*.py")))
    
    print(f"Found {len(test_files)} test files to check")
    
    results = []
    hanging_tests = []
    failed_tests = []
    passed_tests = []
    
    for test_file in test_files:
        returncode, elapsed, is_hanging = run_test_with_timeout(test_file)
        
        results.append({
            'file': test_file,
            'returncode': returncode,
            'elapsed': elapsed,
            'is_hanging': is_hanging
        })
        
        if is_hanging:
            hanging_tests.append(test_file)
        elif returncode != 0:
            failed_tests.append(test_file)
        else:
            passed_tests.append(test_file)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {len(test_files)}")
    print(f"Passed: {len(passed_tests)}")
    print(f"Failed: {len(failed_tests)}")
    print(f"Hanging: {len(hanging_tests)}")
    
    if hanging_tests:
        print(f"\n🚨 HANGING TESTS:")
        for test in hanging_tests:
            print(f"  - {test}")
    
    if failed_tests:
        print(f"\n❌ FAILED TESTS:")
        for test in failed_tests:
            print(f"  - {test}")
    
    # Sort by execution time
    results.sort(key=lambda x: x['elapsed'], reverse=True)
    print(f"\n⏱️  SLOWEST TESTS:")
    for result in results[:10]:
        status = "HANGING" if result['is_hanging'] else ("FAILED" if result['returncode'] != 0 else "PASSED")
        print(f"  {result['elapsed']:6.2f}s - {status:8} - {result['file']}")

if __name__ == "__main__":
    main()
