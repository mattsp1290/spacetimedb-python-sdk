#!/usr/bin/env python3
"""
Comprehensive test runner for SpaceTimeDB SDK v1.1.2 compatibility.
Runs all v1.1.2 test suites and generates a summary report.
"""

import sys
import os
import time
import unittest
import json
import argparse
import importlib  # Security fix: Use importlib instead of __import__
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Test result tracking
class V112TestResults:
    """Track and summarize test results."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.test_suites = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.errors = []
        self.performance_metrics = {}
        
    def start_suite(self, suite_name: str):
        """Mark the start of a test suite."""
        self.test_suites[suite_name] = {
            "start_time": time.time(),
            "tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }
        
    def end_suite(self, suite_name: str, result: unittest.TestResult):
        """Mark the end of a test suite."""
        if suite_name in self.test_suites:
            suite = self.test_suites[suite_name]
            suite["end_time"] = time.time()
            suite["duration"] = suite["end_time"] - suite["start_time"]
            suite["tests"] = result.testsRun
            suite["failed"] = len(result.failures) + len(result.errors)
            suite["passed"] = result.testsRun - suite["failed"] - len(result.skipped)
            suite["skipped"] = len(result.skipped)
            
            # Update totals
            self.total_tests += result.testsRun
            self.passed_tests += suite["passed"]
            self.failed_tests += suite["failed"]
            self.skipped_tests += suite["skipped"]
            
            # Collect errors
            for test, traceback in result.failures + result.errors:
                error_info = {
                    "suite": suite_name,
                    "test": str(test),
                    "traceback": traceback
                }
                suite["errors"].append(error_info)
                self.errors.append(error_info)
                
    def add_performance_metric(self, metric_name: str, value: float):
        """Add a performance metric."""
        if metric_name not in self.performance_metrics:
            self.performance_metrics[metric_name] = []
        self.performance_metrics[metric_name].append(value)
        
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a comprehensive test summary."""
        duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration,
            "total_tests": self.total_tests,
            "passed": self.passed_tests,
            "failed": self.failed_tests,
            "skipped": self.skipped_tests,
            "success_rate": (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0,
            "test_suites": self.test_suites,
            "performance_metrics": self.performance_metrics,
            "errors": self.errors
        }


def run_test_suite(suite_module: str, suite_name: str, results: V112TestResults) -> bool:
    """Run a single test suite and track results."""
    print(f"\n{'=' * 60}")
    print(f"Running {suite_name}")
    print(f"{'=' * 60}")
    
    try:
        # Import the test module - Security fix: Use importlib instead of __import__
        test_module = importlib.import_module(suite_module)
        
        # Create test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_module)
        
        # Run tests
        results.start_suite(suite_name)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        results.end_suite(suite_name, result)
        
        # Return success status
        return result.wasSuccessful()
        
    except Exception as e:
        print(f"Error running {suite_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_v112_tests(skip_performance: bool = False, skip_edge_cases: bool = False) -> V112TestResults:
    """Run all v1.1.2 test suites."""
    results = V112TestResults()
    results.start_time = time.time()
    
    # Define test suites to run
    test_suites = [
        ("test_v112_error_handling", "Error Handling Tests"),
        ("test_v112_authentication", "Authentication Tests"),
        ("test_v112_integration", "Integration Tests"),
    ]
    
    if not skip_performance:
        test_suites.append(("test_v112_performance", "Performance Benchmarks"))
        
    if not skip_edge_cases:
        test_suites.append(("test_v112_edge_cases", "Edge Case Tests"))
    
    # Run each test suite
    all_passed = True
    for module_name, suite_name in test_suites:
        success = run_test_suite(module_name, suite_name, results)
        all_passed = all_passed and success
        
    results.end_time = time.time()
    
    return results


def print_summary(results: V112TestResults):
    """Print a formatted test summary."""
    summary = results.generate_summary()
    
    print("\n" + "=" * 80)
    print("SpaceTimeDB SDK v1.1.2 Test Summary")
    print("=" * 80)
    
    print(f"\nTest Run: {summary['timestamp']}")
    print(f"Duration: {summary['duration_seconds']:.2f} seconds")
    
    print(f"\nOverall Results:")
    print(f"  Total Tests: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']} ({summary['success_rate']:.1f}%)")
    print(f"  Failed: {summary['failed']}")
    print(f"  Skipped: {summary['skipped']}")
    
    print(f"\nTest Suite Breakdown:")
    for suite_name, suite_data in summary['test_suites'].items():
        print(f"\n  {suite_name}:")
        print(f"    Tests: {suite_data['tests']}")
        print(f"    Passed: {suite_data['passed']}")
        print(f"    Failed: {suite_data['failed']}")
        print(f"    Skipped: {suite_data['skipped']}")
        print(f"    Duration: {suite_data['duration']:.2f}s")
        
    if summary['errors']:
        print(f"\n{'=' * 80}")
        print("Failed Tests:")
        print("=" * 80)
        for error in summary['errors']:
            print(f"\n{error['suite']} - {error['test']}")
            print("-" * 40)
            print(error['traceback'])
            
    # Performance metrics summary
    if summary['performance_metrics']:
        print(f"\n{'=' * 80}")
        print("Performance Metrics:")
        print("=" * 80)
        for metric, values in summary['performance_metrics'].items():
            if values:
                avg_value = sum(values) / len(values)
                print(f"  {metric}: {avg_value:.2f} (avg of {len(values)} samples)")


def save_results(results: V112TestResults, filename: str = None):
    """Save test results to a JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"v112_test_results_{timestamp}.json"
        
    summary = results.generate_summary()
    
    # Create results directory if it doesn't exist
    results_dir = "test_results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    filepath = os.path.join(results_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(summary, f, indent=2)
        
    print(f"\nResults saved to: {filepath}")
    
    return filepath


def check_requirements():
    """Check if all required dependencies are available."""
    required_modules = [
        'websockets',
        'psutil',
        'spacetimedb_sdk'
    ]
    
    missing = []
    for module in required_modules:
        try:
            # Security fix: Use importlib instead of __import__
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
            
    if missing:
        print("ERROR: Missing required dependencies:")
        for module in missing:
            print(f"  - {module}")
        print("\nPlease install missing dependencies with:")
        print("  pip install -r requirements.txt")
        return False
        
    return True


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run SpaceTimeDB SDK v1.1.2 compatibility tests"
    )
    parser.add_argument(
        "--skip-performance",
        action="store_true",
        help="Skip performance benchmark tests"
    )
    parser.add_argument(
        "--skip-edge-cases",
        action="store_true",
        help="Skip edge case tests"
    )
    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output filename for results (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
        
    print("SpaceTimeDB SDK v1.1.2 Compatibility Test Suite")
    print("=" * 80)
    print(f"Starting test run at {datetime.now()}")
    
    # Run tests
    results = run_all_v112_tests(
        skip_performance=args.skip_performance,
        skip_edge_cases=args.skip_edge_cases
    )
    
    # Print summary
    print_summary(results)
    
    # Save results if requested
    if args.save_results:
        save_results(results, args.output)
        
    # Generate test coverage command hint
    print("\n" + "=" * 80)
    print("Test Coverage:")
    print("=" * 80)
    print("To generate a detailed coverage report, run:")
    print("  pytest tests/test_v112_*.py --cov=spacetimedb_sdk --cov-report=html")
    print("  open htmlcov/index.html")
    
    # Exit with appropriate code
    if results.failed_tests > 0:
        print(f"\n❌ {results.failed_tests} test(s) failed!")
        sys.exit(1)
    else:
        print(f"\n✅ All {results.total_tests} tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
