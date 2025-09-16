#!/usr/bin/env python3
"""
Comprehensive test validation script for SUBAGENT 5 final validation.

This script runs different test categories with optimized settings and provides
detailed reporting for the final validation phase.
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class TestResult:
    category: str
    passed: int
    failed: int
    errors: int
    skipped: int
    duration: float
    exit_code: int
    output: str

class ComprehensiveValidator:
    """Final validation coordinator for all subagent fixes."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
    def run_test_category(self, category: str, test_path: str, timeout: int = 180, 
                         extra_args: List[str] = None) -> TestResult:
        """Run a specific test category with optimized settings."""
        if extra_args is None:
            extra_args = []
            
        cmd = [
            sys.executable, "-m", "pytest",
            test_path,
            "-v",
            "--tb=short",
            "--maxfail=10",
            "--durations=5",
            f"--timeout={timeout}",
            "--disable-warnings",
            "--color=yes"
        ] + extra_args
        
        print(f"\n{'='*60}")
        print(f"Running {category} tests: {test_path}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 60,  # Add buffer for pytest overhead
                cwd="/Users/punk1290/git/spacetimedb-python-sdk"
            )
            duration = time.time() - start_time
            
            # Parse pytest output for statistics
            output = result.stdout + result.stderr
            passed, failed, errors, skipped = self._parse_pytest_stats(output)
            
            test_result = TestResult(
                category=category,
                passed=passed,
                failed=failed,
                errors=errors,
                skipped=skipped,
                duration=duration,
                exit_code=result.returncode,
                output=output
            )
            
            self.results.append(test_result)
            
            print(f"\n{category} Results:")
            print(f"  Passed: {passed}")
            print(f"  Failed: {failed}")
            print(f"  Errors: {errors}")
            print(f"  Skipped: {skipped}")
            print(f"  Duration: {duration:.2f}s")
            print(f"  Exit Code: {result.returncode}")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            test_result = TestResult(
                category=category,
                passed=0,
                failed=0,
                errors=1,
                skipped=0,
                duration=duration,
                exit_code=-1,
                output=f"Test timeout after {timeout}s"
            )
            self.results.append(test_result)
            print(f"\n{category} TIMEOUT after {timeout}s")
            return test_result
            
        except Exception as e:
            duration = time.time() - start_time
            test_result = TestResult(
                category=category,
                passed=0,
                failed=0,
                errors=1,
                skipped=0,
                duration=duration,
                exit_code=-1,
                output=f"Test execution error: {str(e)}"
            )
            self.results.append(test_result)
            print(f"\n{category} ERROR: {str(e)}")
            return test_result
    
    def _parse_pytest_stats(self, output: str) -> tuple[int, int, int, int]:
        """Parse pytest output to extract test statistics."""
        passed = failed = errors = skipped = 0
        
        # Look for the final summary line
        for line in output.split('\n'):
            if 'passed' in line and ('failed' in line or 'error' in line or 'skipped' in line):
                # Parse lines like: "5 passed, 2 failed, 1 error, 3 skipped in 10.5s"
                try:
                    parts = line.split(',')
                    for part in parts:
                        part = part.strip()
                        if 'passed' in part:
                            passed = int(part.split()[0])
                        elif 'failed' in part:
                            failed = int(part.split()[0])
                        elif 'error' in part:
                            errors = int(part.split()[0])
                        elif 'skipped' in part:
                            skipped = int(part.split()[0])
                except (ValueError, IndexError):
                    pass
                    
            elif line.strip().endswith('passed') and 'failed' not in line:
                # Handle lines like "10 passed in 5.2s"
                try:
                    passed = int(line.split()[0])
                except (ValueError, IndexError):
                    pass
        
        return passed, failed, errors, skipped
    
    def run_comprehensive_validation(self):
        """Run comprehensive validation across all test categories."""
        print("🚀 Starting Comprehensive Test Validation")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test categories with optimized settings
        test_categories = [
            # Quick smoke tests first
            ("Integration Smoke", "tests/integration/test_basic_connection_mock.py", 60),
            
            # Core functionality tests
            ("SDK Client Integration", "tests/test_sdk_client_integration.py", 120),
            
            # Protocol and connection tests
            ("V112 Integration", "tests/test_v112_integration.py", 150),
            ("V112 Identity", "tests/test_v112_identity.py", 120),
            
            # Component tests
            ("Connection Manager", "tests/test_connection_manager.py", 90),
            ("Protocol Handler", "tests/test_protocol_handler.py", 90),
            ("Compression Manager", "tests/test_compression_manager.py", 60),
            
            # Security tests
            ("Security Suite", "tests/security/", 120),
            
            # Performance tests (with longer timeout)
            ("Performance", "tests/performance/", 200),
        ]
        
        for category, path, timeout in test_categories:
            if Path(f"/Users/punk1290/git/spacetimedb-python-sdk/{path}").exists():
                self.run_test_category(category, path, timeout)
            else:
                print(f"⚠️  Skipping {category}: {path} not found")
        
        self.generate_final_report()
    
    def generate_final_report(self):
        """Generate comprehensive final validation report."""
        total_duration = time.time() - self.start_time
        
        # Calculate totals
        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results) 
        total_errors = sum(r.errors for r in self.results)
        total_skipped = sum(r.skipped for r in self.results)
        total_tests = total_passed + total_failed + total_errors
        
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n{'='*80}")
        print("🎯 COMPREHENSIVE VALIDATION REPORT")
        print(f"{'='*80}")
        print(f"Total Duration: {total_duration:.2f}s")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {total_passed} ({success_rate:.1f}%)")
        print(f"Failed: {total_failed}")
        print(f"Errors: {total_errors}")
        print(f"Skipped: {total_skipped}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        print(f"\n{'='*60}")
        print("📊 CATEGORY BREAKDOWN")
        print(f"{'='*60}")
        
        for result in self.results:
            status = "✅ PASS" if result.exit_code == 0 else "❌ FAIL"
            print(f"{status} {result.category:25} | "
                  f"P:{result.passed:3} F:{result.failed:3} E:{result.errors:3} "
                  f"| {result.duration:.1f}s")
        
        # Generate JSON report for programmatic access
        report = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "total_duration": total_duration,
            "summary": {
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "errors": total_errors,
                "skipped": total_skipped,
                "success_rate": success_rate
            },
            "categories": [
                {
                    "category": r.category,
                    "passed": r.passed,
                    "failed": r.failed,
                    "errors": r.errors,
                    "skipped": r.skipped,
                    "duration": r.duration,
                    "exit_code": r.exit_code,
                    "success": r.exit_code == 0
                }
                for r in self.results
            ]
        }
        
        with open("comprehensive_validation_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📋 Detailed report saved to: comprehensive_validation_report.json")
        
        # Final assessment
        critical_failures = total_failed + total_errors
        if critical_failures == 0:
            print("\n🎉 ALL TESTS PASSING - Validation Successful!")
            print("✅ Ready for production deployment")
        elif critical_failures <= 3:
            print(f"\n⚠️  Minor issues detected ({critical_failures} failures)")
            print("🔧 Acceptable for continued development")
        else:
            print(f"\n🚨 Significant issues detected ({critical_failures} failures)")
            print("❌ Requires immediate attention before deployment")
        
        return success_rate >= 80  # 80% success rate threshold

if __name__ == "__main__":
    validator = ComprehensiveValidator()
    success = validator.run_comprehensive_validation()
    sys.exit(0 if success else 1)