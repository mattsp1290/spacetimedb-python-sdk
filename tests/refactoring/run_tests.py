#!/usr/bin/env python3
"""
Test runner for Phase 2 refactoring tests

This script provides various test execution modes and configurations
for the comprehensive test suite.
"""
import sys
import os
import argparse
import subprocess
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import json


class TestRunner:
    """Main test runner for refactoring tests"""
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.test_results = {}
        
    def run_regression_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run regression tests to ensure no functionality breaks"""
        print("🔄 Running regression tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "regression",
            "--tb=short",
            str(self.base_dir / "test_websocket_client_regression.py"),
            str(self.base_dir / "test_api_compatibility.py"),
            str(self.base_dir / "test_integration_regression.py")
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['regression'] = result
        return result
        
    def run_module_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run isolated module tests"""
        print("🧩 Running module tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "module",
            "--tb=short",
            str(self.base_dir / "test_subscription_manager.py"),
            str(self.base_dir / "test_authentication_handler.py"),
            str(self.base_dir / "test_unified_event_system.py")
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['module'] = result
        return result
        
    def run_integration_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run integration tests"""
        print("🔗 Running integration tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "integration",
            "--tb=short",
            str(self.base_dir / "test_module_integration.py")
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['integration'] = result
        return result
        
    def run_performance_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run performance tests"""
        print("⚡ Running performance tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "performance",
            "--tb=short",
            str(self.base_dir / "test_performance_regression.py")
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['performance'] = result
        return result
        
    def run_end_to_end_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run end-to-end scenario tests"""
        print("🎯 Running end-to-end tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "end_to_end",
            "--tb=short",
            str(self.base_dir / "test_end_to_end_scenarios.py")
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['end_to_end'] = result
        return result
        
    def run_all_tests(self, verbose: bool = False, parallel: bool = False) -> Dict[str, Any]:
        """Run all tests"""
        print("🚀 Running all refactoring tests...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.base_dir),
            "--tb=short",
            "--durations=10"
        ]
        
        if verbose:
            cmd.append("-v")
            
        if parallel:
            cmd.extend(["-n", "auto"])  # Requires pytest-xdist
            
        result = self._run_command(cmd)
        self.test_results['all'] = result
        return result
        
    def run_fast_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run fast tests only (exclude slow tests)"""
        print("⚡ Running fast tests only...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "not slow",
            str(self.base_dir),
            "--tb=short"
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['fast'] = result
        return result
        
    def run_coverage_analysis(self) -> Dict[str, Any]:
        """Run tests with coverage analysis"""
        print("📊 Running coverage analysis...")
        
        cmd = [
            "python", "-m", "pytest",
            str(self.base_dir),
            "--cov=spacetimedb_sdk.websocket_client",
            "--cov-report=term-missing",
            "--cov-report=html:coverage_html",
            "--cov-report=xml:coverage.xml",
            "--cov-fail-under=80"
        ]
        
        result = self._run_command(cmd)
        self.test_results['coverage'] = result
        return result
        
    def run_memory_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run memory-focused tests"""
        print("🧠 Running memory tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "memory",
            "--tb=short",
            str(self.base_dir)
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['memory'] = result
        return result
        
    def run_concurrent_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run concurrency tests"""
        print("🔀 Running concurrent tests...")
        
        cmd = [
            "python", "-m", "pytest",
            "-m", "concurrent",
            "--tb=short",
            str(self.base_dir)
        ]
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['concurrent'] = result
        return result
        
    def run_custom_suite(self, markers: List[str], files: List[str] = None, verbose: bool = False) -> Dict[str, Any]:
        """Run custom test suite with specified markers and files"""
        print(f"🎛️  Running custom test suite with markers: {', '.join(markers)}")
        
        cmd = ["python", "-m", "pytest"]
        
        if markers:
            marker_expr = " or ".join(markers)
            cmd.extend(["-m", marker_expr])
            
        if files:
            cmd.extend([str(self.base_dir / f) for f in files])
        else:
            cmd.append(str(self.base_dir))
            
        cmd.append("--tb=short")
        
        if verbose:
            cmd.append("-v")
            
        result = self._run_command(cmd)
        self.test_results['custom'] = result
        return result
        
    def generate_test_report(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        report = {
            "timestamp": time.time(),
            "test_results": self.test_results,
            "summary": {
                "total_suites": len(self.test_results),
                "passed_suites": len([r for r in self.test_results.values() if r.get('success', False)]),
                "failed_suites": len([r for r in self.test_results.values() if not r.get('success', False)])
            }
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
                
            print(f"📄 Test report saved to: {output_path}")
            
        return report
        
    def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run a command and capture results"""
        start_time = time.time()
        
        try:
            # Add Python path
            env = os.environ.copy()
            env['PYTHONPATH'] = str(self.base_dir.parent.parent / 'src')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.base_dir,
                env=env,
                timeout=300  # 5 minute timeout
            )
            
            end_time = time.time()
            
            return {
                "success": result.returncode == 0,
                "duration": end_time - start_time,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "duration": time.time() - start_time,
                "return_code": -1,
                "stdout": "",
                "stderr": "Test execution timed out",
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start_time,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "command": " ".join(cmd)
            }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run Phase 2 refactoring tests")
    
    parser.add_argument("--suite", choices=[
        "regression", "module", "integration", "performance", 
        "end-to-end", "all", "fast", "coverage", "memory", "concurrent"
    ], default="all", help="Test suite to run")
    
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    parser.add_argument("--markers", "-m", nargs="+", help="Custom test markers")
    parser.add_argument("--files", "-f", nargs="+", help="Specific test files to run")
    parser.add_argument("--report", "-r", help="Generate test report to file")
    parser.add_argument("--base-dir", help="Base directory for tests")
    
    args = parser.parse_args()
    
    runner = TestRunner(args.base_dir)
    
    print("🧪 SpacetimeDB Python SDK - Phase 2 Refactoring Test Suite")
    print("=" * 60)
    
    # Run the specified test suite
    if args.suite == "regression":
        result = runner.run_regression_tests(args.verbose)
    elif args.suite == "module":
        result = runner.run_module_tests(args.verbose)
    elif args.suite == "integration":
        result = runner.run_integration_tests(args.verbose)
    elif args.suite == "performance":
        result = runner.run_performance_tests(args.verbose)
    elif args.suite == "end-to-end":
        result = runner.run_end_to_end_tests(args.verbose)
    elif args.suite == "fast":
        result = runner.run_fast_tests(args.verbose)
    elif args.suite == "coverage":
        result = runner.run_coverage_analysis()
    elif args.suite == "memory":
        result = runner.run_memory_tests(args.verbose)
    elif args.suite == "concurrent":
        result = runner.run_concurrent_tests(args.verbose)
    elif args.suite == "all":
        if args.markers or args.files:
            result = runner.run_custom_suite(args.markers or [], args.files or [], args.verbose)
        else:
            result = runner.run_all_tests(args.verbose, args.parallel)
    
    # Print summary
    print("\n" + "=" * 60)
    if result['success']:
        print("✅ Tests PASSED")
    else:
        print("❌ Tests FAILED")
        
    print(f"⏱️  Duration: {result['duration']:.2f} seconds")
    
    if result['stderr']:
        print(f"⚠️  Errors: {result['stderr']}")
        
    # Generate report if requested
    if args.report:
        runner.generate_test_report(args.report)
        
    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()