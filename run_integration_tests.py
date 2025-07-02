#!/usr/bin/env python3
"""
Integration Test Runner for SpacetimeDB Python SDK

Comprehensive test runner that validates SDK-client integration,
performance characteristics, and error handling capabilities.
"""

import os
import sys
import subprocess
import time
import argparse
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add src to Python path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))


class TestRunner:
    """Comprehensive test runner for SDK integration tests."""
    
    def __init__(self, verbose: bool = False, fast: bool = False):
        self.verbose = verbose
        self.fast = fast
        self.test_results: Dict[str, Dict[str, Any]] = {}
        
    def run_test_suite(self, test_file: str, description: str) -> Dict[str, Any]:
        """Run a specific test suite and return results."""
        
        print(f"\n{'='*60}")
        print(f"Running {description}")
        print(f"{'='*60}")
        
        # Build pytest command
        cmd = ["python", "-m", "pytest", f"tests/{test_file}"]
        
        if self.verbose:
            cmd.extend(["-v", "-s"])
        else:
            cmd.extend(["-v"])
            
        cmd.extend(["--tb=short", "--color=yes"])
        
        # Add markers for fast mode
        if self.fast:
            cmd.extend(["-m", "not slow"])
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=current_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            output_lines = result.stdout.split('\n')
            failed_tests = []
            passed_tests = []
            
            for line in output_lines:
                if "FAILED" in line:
                    failed_tests.append(line.strip())
                elif "PASSED" in line:
                    passed_tests.append(line.strip())
            
            # Extract summary
            summary_line = ""
            for line in reversed(output_lines):
                if "failed" in line or "passed" in line or "error" in line:
                    summary_line = line.strip()
                    break
            
            test_result = {
                "success": result.returncode == 0,
                "duration": duration,
                "summary": summary_line,
                "passed_count": len(passed_tests),
                "failed_count": len(failed_tests),
                "failed_tests": failed_tests,
                "stdout": result.stdout if self.verbose else "",
                "stderr": result.stderr if result.stderr else ""
            }
            
            if test_result["success"]:
                print(f"✅ {description} - PASSED ({duration:.1f}s)")
                if summary_line:
                    print(f"   {summary_line}")
            else:
                print(f"❌ {description} - FAILED ({duration:.1f}s)")
                if summary_line:
                    print(f"   {summary_line}")
                
                # Show failed tests
                if failed_tests:
                    print("   Failed tests:")
                    for failed_test in failed_tests[:5]:  # Show first 5
                        print(f"     - {failed_test}")
                    if len(failed_tests) > 5:
                        print(f"     ... and {len(failed_tests) - 5} more")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {description} - TIMEOUT (>5 minutes)")
            return {
                "success": False,
                "duration": 300,
                "summary": "Test suite timed out",
                "error": "timeout"
            }
        except Exception as e:
            print(f"💥 {description} - ERROR: {e}")
            return {
                "success": False,
                "duration": 0,
                "summary": f"Test runner error: {e}",
                "error": str(e)
            }
    
    def run_all_tests(self) -> bool:
        """Run all integration test suites."""
        
        print("🚀 Starting SpacetimeDB Python SDK Integration Tests")
        print(f"Mode: {'Fast' if self.fast else 'Comprehensive'}")
        print(f"Verbose: {self.verbose}")
        
        # Test suites to run
        test_suites = [
            {
                "file": "test_sdk_client_integration.py",
                "description": "SDK-Client Integration Tests",
                "critical": True
            },
            {
                "file": "test_performance_benchmarks.py", 
                "description": "Performance Benchmarks",
                "critical": False
            },
            {
                "file": "test_error_scenarios.py",
                "description": "Error Scenario Tests", 
                "critical": True
            }
        ]
        
        total_start_time = time.time()
        overall_success = True
        
        # Run each test suite
        for suite in test_suites:
            result = self.run_test_suite(suite["file"], suite["description"])
            self.test_results[suite["description"]] = result
            
            if not result["success"]:
                overall_success = False
                if suite["critical"]:
                    print(f"🚨 Critical test suite failed: {suite['description']}")
        
        total_duration = time.time() - total_start_time
        
        # Print summary
        self.print_summary(total_duration, overall_success)
        
        return overall_success
    
    def print_summary(self, total_duration: float, overall_success: bool):
        """Print test execution summary."""
        
        print(f"\n{'='*60}")
        print("TEST EXECUTION SUMMARY")
        print(f"{'='*60}")
        
        print(f"Total execution time: {total_duration:.1f}s")
        print(f"Overall result: {'✅ PASSED' if overall_success else '❌ FAILED'}")
        
        print(f"\nTest Suite Results:")
        print(f"{'Suite':<30} {'Result':<10} {'Time':<8} {'Tests'}")
        print(f"{'-'*30} {'-'*10} {'-'*8} {'-'*20}")
        
        total_passed = 0
        total_failed = 0
        
        for suite_name, result in self.test_results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            duration = f"{result['duration']:.1f}s"
            
            passed = result.get("passed_count", 0)
            failed = result.get("failed_count", 0)
            test_summary = f"{passed} passed, {failed} failed"
            
            total_passed += passed
            total_failed += failed
            
            print(f"{suite_name:<30} {status:<10} {duration:<8} {test_summary}")
        
        print(f"{'-'*30} {'-'*10} {'-'*8} {'-'*20}")
        print(f"{'TOTAL':<30} {'':<10} {'':<8} {total_passed} passed, {total_failed} failed")
        
        # Print any critical failures
        critical_failures = []
        for suite_name, result in self.test_results.items():
            if not result["success"] and result.get("failed_tests"):
                critical_failures.extend(result["failed_tests"])
        
        if critical_failures:
            print(f"\n🚨 Critical Failures ({len(critical_failures)} total):")
            for failure in critical_failures[:10]:  # Show first 10
                print(f"   - {failure}")
            if len(critical_failures) > 10:
                print(f"   ... and {len(critical_failures) - 10} more")
        
        # Print recommendations
        print(f"\n📋 Recommendations:")
        if overall_success:
            print("   ✅ All tests passed! SDK-client integration is ready for production.")
            print("   ✅ Performance benchmarks meet requirements.")
            print("   ✅ Error handling is robust and reliable.")
        else:
            print("   ❌ Some tests failed. Review failures before deploying integration.")
            if total_failed > 0:
                print(f"   📝 Fix {total_failed} failing tests to ensure compatibility.")
            
            # Specific recommendations based on failures
            if "Integration Tests" in [name for name, result in self.test_results.items() if not result["success"]]:
                print("   🔧 Core integration issues detected - fix message validation and protocol handling.")
            
            if "Performance Benchmarks" in [name for name, result in self.test_results.items() if not result["success"]]:
                print("   ⚡ Performance issues detected - optimize metrics recording and message processing.")
            
            if "Error Scenario Tests" in [name for name, result in self.test_results.items() if not result["success"]]:
                print("   🛡️ Error handling issues detected - improve resilience and recovery mechanisms.")
    
    def run_specific_test(self, test_pattern: str) -> bool:
        """Run a specific test pattern."""
        
        print(f"🎯 Running specific test pattern: {test_pattern}")
        
        cmd = ["python", "-m", "pytest", "-k", test_pattern]
        
        if self.verbose:
            cmd.extend(["-v", "-s"])
        
        cmd.extend(["--tb=short", "--color=yes", "tests/"])
        
        try:
            result = subprocess.run(
                cmd,
                cwd=current_dir,
                timeout=300
            )
            
            success = result.returncode == 0
            print(f"Result: {'✅ PASSED' if success else '❌ FAILED'}")
            return success
            
        except subprocess.TimeoutExpired:
            print("⏰ Test timed out")
            return False
        except Exception as e:
            print(f"💥 Error running test: {e}")
            return False


def main():
    """Main test runner entry point."""
    
    parser = argparse.ArgumentParser(
        description="Run SpacetimeDB Python SDK integration tests"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--fast", "-f", 
        action="store_true",
        help="Run fast tests only (skip slow performance tests)"
    )
    
    parser.add_argument(
        "--test", "-t",
        type=str,
        help="Run specific test pattern (e.g., 'test_message_validation')"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true", 
        help="List available test files"
    )
    
    args = parser.parse_args()
    
    # List tests if requested
    if args.list:
        test_dir = current_dir / "tests"
        print("Available test files:")
        for test_file in test_dir.glob("test_*.py"):
            print(f"  - {test_file.name}")
        return 0
    
    # Create test runner
    runner = TestRunner(verbose=args.verbose, fast=args.fast)
    
    # Run specific test if requested
    if args.test:
        success = runner.run_specific_test(args.test)
        return 0 if success else 1
    
    # Run all tests
    success = runner.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())