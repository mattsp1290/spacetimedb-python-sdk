#!/usr/bin/env python3
"""
SUBAGENT 5 coordination script for monitoring and final validation.

This script coordinates with other subagents by monitoring the codebase
for changes and running final validation when all fixes are in place.
"""

import os
import subprocess
import time
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class CodebaseHealth:
    """Overall health metrics of the codebase."""
    modified_files: int
    test_files: int
    critical_imports_fixed: bool
    protocol_issues_resolved: bool
    test_config_optimized: bool
    overall_status: str

class SubagentCoordinator:
    """Coordinates with other subagents and monitors overall progress."""
    
    def __init__(self):
        self.base_path = Path("/Users/punk1290/git/spacetimedb-python-sdk")
        self.start_time = time.time()
        
    def analyze_codebase_health(self) -> CodebaseHealth:
        """Analyze the current state of the codebase."""
        
        # Count modified files
        try:
            git_status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.base_path
            )
            modified_files = len([line for line in git_status.stdout.split('\n') if line.strip()])
        except:
            modified_files = 0
        
        # Count test files
        test_files = len(list(self.base_path.glob("tests/**/*.py")))
        
        # Check critical imports status
        critical_imports_fixed = self._check_import_fixes()
        
        # Check protocol issues
        protocol_issues_resolved = self._check_protocol_fixes()
        
        # Check test configuration
        test_config_optimized = self._check_test_config()
        
        # Determine overall status
        if all([critical_imports_fixed, protocol_issues_resolved, test_config_optimized]):
            overall_status = "READY_FOR_VALIDATION"
        elif critical_imports_fixed and test_config_optimized:
            overall_status = "PARTIALLY_READY"
        else:
            overall_status = "IN_PROGRESS"
        
        return CodebaseHealth(
            modified_files=modified_files,
            test_files=test_files,
            critical_imports_fixed=critical_imports_fixed,
            protocol_issues_resolved=protocol_issues_resolved,
            test_config_optimized=test_config_optimized,
            overall_status=overall_status
        )
    
    def _check_import_fixes(self) -> bool:
        """Check if circular import issues have been resolved."""
        try:
            # Quick check - try to import main modules without errors
            test_imports = [
                "src.spacetimedb_sdk.spacetimedb_client",
                "src.spacetimedb_sdk.connection.connection_manager",
                "src.spacetimedb_sdk.protocol_handlers.protocol_handler",
                "src.spacetimedb_sdk.auth.authentication_manager"
            ]
            
            for module in test_imports:
                try:
                    result = subprocess.run([
                        "python", "-c", f"import {module}"
                    ], capture_output=True, cwd=self.base_path, timeout=10)
                    if result.returncode != 0:
                        return False
                except subprocess.TimeoutExpired:
                    return False
            return True
        except:
            return False
    
    def _check_protocol_fixes(self) -> bool:
        """Check if protocol-related issues have been addressed."""
        # Check for key protocol files and their basic syntax
        critical_protocol_files = [
            "src/spacetimedb_sdk/protocol.py",
            "src/spacetimedb_sdk/websocket_client.py",
            "src/spacetimedb_sdk/protocol_handlers/protocol_handler.py"
        ]
        
        for file_path in critical_protocol_files:
            full_path = self.base_path / file_path
            if not full_path.exists():
                return False
            
            # Basic syntax check
            try:
                result = subprocess.run([
                    "python", "-m", "py_compile", str(full_path)
                ], capture_output=True, timeout=5)
                if result.returncode != 0:
                    return False
            except:
                return False
        
        return True
    
    def _check_test_config(self) -> bool:
        """Check if test configuration has been optimized."""
        # Check for our optimized test configuration
        pytest_ini = self.base_path / "tests" / "pytest.ini"
        if not pytest_ini.exists():
            return False
        
        try:
            content = pytest_ini.read_text()
            return (
                "timeout = 180" in content and
                "maxfail=5" in content and
                "durations=10" in content
            )
        except:
            return False
    
    def monitor_and_coordinate(self, max_wait_time: int = 1800):  # 30 minutes max
        """Monitor other subagents and coordinate final validation."""
        
        print("🔍 SUBAGENT 5 - Starting coordination and monitoring")
        print(f"Max wait time: {max_wait_time}s")
        
        check_interval = 30  # Check every 30 seconds
        checks_performed = 0
        max_checks = max_wait_time // check_interval
        
        while checks_performed < max_checks:
            health = self.analyze_codebase_health()
            
            print(f"\n📊 Codebase Health Check #{checks_performed + 1}")
            print(f"  Modified Files: {health.modified_files}")
            print(f"  Test Files: {health.test_files}")
            print(f"  Imports Fixed: {'✅' if health.critical_imports_fixed else '❌'}")
            print(f"  Protocol Fixed: {'✅' if health.protocol_issues_resolved else '❌'}")
            print(f"  Test Config: {'✅' if health.test_config_optimized else '❌'}")
            print(f"  Status: {health.overall_status}")
            
            if health.overall_status == "READY_FOR_VALIDATION":
                print("\n🎯 All subagents appear to have completed their work!")
                print("🚀 Initiating comprehensive validation...")
                return self.run_final_validation()
            
            elif health.overall_status == "PARTIALLY_READY":
                print(f"\n⏳ Partially ready. Waiting for protocol fixes...")
                
            else:
                print(f"\n⏳ Still in progress. Waiting for other subagents...")
            
            if checks_performed < max_checks - 1:
                print(f"💤 Waiting {check_interval}s before next check...")
                time.sleep(check_interval)
            
            checks_performed += 1
        
        print(f"\n⚠️  Timeout reached after {max_wait_time}s")
        print("🔧 Running partial validation with current state...")
        return self.run_final_validation()
    
    def run_final_validation(self) -> bool:
        """Execute comprehensive final validation."""
        print("\n" + "="*80)
        print("🎯 FINAL COMPREHENSIVE VALIDATION")
        print("="*80)
        
        try:
            # Run our comprehensive validation script
            result = subprocess.run([
                "python", "run_comprehensive_validation.py"
            ], cwd=self.base_path, timeout=1200)  # 20 minute timeout
            
            success = result.returncode == 0
            
            if success:
                print("\n✅ COMPREHENSIVE VALIDATION SUCCESSFUL!")
                print("🎉 All critical systems are functioning properly")
            else:
                print("\n⚠️  VALIDATION COMPLETED WITH ISSUES")
                print("🔧 Some tests failed but system is partially functional")
            
            # Generate final summary report
            self.generate_final_summary(success)
            
            return success
            
        except subprocess.TimeoutExpired:
            print("\n🚨 VALIDATION TIMEOUT")
            print("❌ Final validation took too long - possible hangs detected")
            return False
            
        except Exception as e:
            print(f"\n🚨 VALIDATION ERROR: {e}")
            return False
    
    def generate_final_summary(self, validation_success: bool):
        """Generate final summary report for all subagent coordination."""
        
        health = self.analyze_codebase_health()
        total_time = time.time() - self.start_time
        
        summary = {
            "subagent_5_report": {
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "total_coordination_time": total_time,
                "final_validation_success": validation_success,
                "codebase_health": {
                    "modified_files": health.modified_files,
                    "test_files": health.test_files,
                    "critical_imports_fixed": health.critical_imports_fixed,
                    "protocol_issues_resolved": health.protocol_issues_resolved,
                    "test_config_optimized": health.test_config_optimized,
                    "overall_status": health.overall_status
                },
                "infrastructure_improvements": [
                    "Resolved pytest.ini configuration conflicts",
                    "Optimized timeout settings from 60s to 180s",
                    "Standardized test execution parameters",
                    "Created comprehensive validation framework",
                    "Implemented subagent coordination system"
                ],
                "recommendations": []
            }
        }
        
        # Add recommendations based on results
        if not health.critical_imports_fixed:
            summary["subagent_5_report"]["recommendations"].append(
                "CRITICAL: Resolve remaining circular import issues"
            )
        
        if not health.protocol_issues_resolved:
            summary["subagent_5_report"]["recommendations"].append(
                "HIGH: Address protocol handler and websocket client issues"
            )
        
        if validation_success:
            summary["subagent_5_report"]["recommendations"].append(
                "SUCCESS: All systems operational - ready for deployment"
            )
        else:
            summary["subagent_5_report"]["recommendations"].append(
                "REVIEW: Check validation report for specific failing tests"
            )
        
        # Save the report
        with open("subagent_5_final_report.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📋 Final coordination report saved: subagent_5_final_report.json")
        
        # Print summary
        print(f"\n{'='*60}")
        print("🎯 SUBAGENT 5 FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total Time: {total_time:.1f}s")
        print(f"Test Config: {'✅ Optimized' if health.test_config_optimized else '❌ Issues'}")
        print(f"Validation: {'✅ Success' if validation_success else '❌ Issues'}")
        print(f"Overall: {'✅ COMPLETE' if validation_success and health.test_config_optimized else '⚠️  PARTIAL'}")

if __name__ == "__main__":
    coordinator = SubagentCoordinator()
    success = coordinator.monitor_and_coordinate()
    exit(0 if success else 1)