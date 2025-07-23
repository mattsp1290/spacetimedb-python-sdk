#!/usr/bin/env python3
"""
Test runner script for SpaceTimeDB Python SDK with performance optimizations.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

def run_command(cmd, description="Running command"):
    """Run a command and measure execution time."""
    print(f"🔄 {description}: {' '.join(cmd)}")
    start_time = time.time()
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    end_time = time.time()
    duration = end_time - start_time
    
    if result.returncode == 0:
        print(f"✅ {description} completed in {duration:.2f}s")
    else:
        print(f"❌ {description} failed in {duration:.2f}s")
        
    return result.returncode, duration

def main():
    parser = argparse.ArgumentParser(description="Optimized test runner for SpaceTimeDB SDK")
    parser.add_argument("--fast", action="store_true", help="Run only fast tests")
    parser.add_argument("--slow", action="store_true", help="Run only slow tests")
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel execution")
    parser.add_argument("--coverage", action="store_true", help="Enable coverage reporting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--profile", action="store_true", help="Profile test execution")
    parser.add_argument("tests", nargs="*", help="Specific test files or patterns to run")
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add parallelization unless disabled
    if not args.no_parallel:
        cmd.extend(["-n", "auto"])
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")  # Quiet for faster output
    
    # Add coverage if requested
    if args.coverage:
        cmd.extend(["--cov=src/spacetimedb_sdk", "--cov-report=term-missing"])
    else:
        cmd.append("--no-cov")
    
    # Test selection
    if args.fast:
        cmd.extend(["-m", "not slow"])
    elif args.slow:
        cmd.extend(["-m", "slow"])
    
    # Specific tests
    if args.tests:
        cmd.extend(args.tests)
    else:
        cmd.append("tests/")
    
    # Performance optimizations
    cmd.extend([
        "--tb=short",  # Shorter tracebacks
        "--maxfail=5", # Stop after 5 failures
        "--disable-warnings",  # Suppress warnings for speed
    ])
    
    # Profiling
    if args.profile:
        cmd.extend(["--profile", "--profile-svg"])
    
    print("🚀 Starting optimized test execution...")
    print(f"📋 Command: {' '.join(cmd)}")
    
    exit_code, duration = run_command(cmd, "Test execution")
    
    print(f"\n📊 Test Summary:")
    print(f"   Duration: {duration:.2f} seconds")
    print(f"   Status: {'✅ PASSED' if exit_code == 0 else '❌ FAILED'}")
    
    if args.fast:
        print(f"   Mode: Fast tests only")
    elif args.slow:
        print(f"   Mode: Slow tests only")
    else:
        print(f"   Mode: All tests")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()