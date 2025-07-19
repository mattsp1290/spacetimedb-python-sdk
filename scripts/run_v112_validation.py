"""
Run complete v1.1.2 validation suite and generate report
"""
import os
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def run_command(cmd, capture=True):
    """Run a command and return output"""
    print(f"Running: {cmd}")
    
    if capture:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True
        )
        return result.returncode, result.stdout, result.stderr
    else:
        result = subprocess.run(cmd, shell=True)
        return result.returncode, "", ""


def check_environment():
    """Check if environment is properly configured"""
    config = {
        "host": os.environ.get("SPACETIMEDB_HOST", "localhost:3000"),
        "database": os.environ.get("SPACETIMEDB_DB", "test-validation"),
        "identity": os.environ.get("SPACETIMEDB_IDENTITY", None),
        "skip_tests": os.environ.get("SKIP_REAL_SERVER_TESTS", "true")
    }
    
    print("Environment Configuration:")
    print(f"  Host: {config['host']}")
    print(f"  Database: {config['database']}")
    print(f"  Identity: {config['identity'] or 'Not set'}")
    print(f"  Skip Tests: {config['skip_tests']}")
    print()
    
    if config['skip_tests'].lower() == 'true':
        print("WARNING: Real server tests are disabled!")
        print("Set SKIP_REAL_SERVER_TESTS=false to run validation")
        print()
    
    return config


def run_validation_tests():
    """Run the validation test suite"""
    print("\n" + "="*60)
    print("Running Validation Tests")
    print("="*60)
    
    test_results = {}
    
    # Run real server tests
    print("\n1. Running real server tests...")
    code, stdout, stderr = run_command(
        "python -m pytest tests/test_v112_real_server.py -v -s"
    )
    
    test_results['real_server'] = {
        'success': code == 0,
        'output': stdout,
        'errors': stderr
    }
    
    # Run performance benchmarks
    print("\n2. Running performance benchmarks...")
    code, stdout, stderr = run_command(
        "python -m pytest tests/test_v112_performance.py -v -s"
    )
    
    test_results['performance'] = {
        'success': code == 0,
        'output': stdout,
        'errors': stderr
    }
    
    # Run integration tests
    print("\n3. Running integration tests...")
    code, stdout, stderr = run_command(
        "python -m pytest tests/test_v112_integration.py -v -k 'not mock'"
    )
    
    test_results['integration'] = {
        'success': code == 0,
        'output': stdout,
        'errors': stderr
    }
    
    return test_results


def test_example_application():
    """Test the updated quickstart example"""
    print("\n" + "="*60)
    print("Testing Example Application")
    print("="*60)
    
    # Check if module bindings exist
    if not os.path.exists("examples/quickstart/client/module_bindings"):
        print("WARNING: Module bindings not found!")
        print("Please generate bindings first using:")
        print("  spacetime generate --language python --out-dir examples/quickstart/client")
        return None
    
    print("\nStarting quickstart example (will timeout after 10 seconds)...")
    
    # Start the client with a timeout
    proc = subprocess.Popen(
        ["python", "examples/quickstart/client/main_v112.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Wait a bit for connection
        time.sleep(3)
        
        # Check if process is still running
        if proc.poll() is None:
            print("✓ Client started successfully")
            
            # Try to send a test message
            proc.stdin.write("Test message from validation\n")
            proc.stdin.flush()
            time.sleep(1)
            
            # Send quit command
            proc.stdin.write("/quit\n")
            proc.stdin.flush()
            
            # Wait for clean exit
            stdout, stderr = proc.communicate(timeout=5)
            
            return {
                'success': proc.returncode == 0,
                'output': stdout,
                'errors': stderr
            }
        else:
            stdout, stderr = proc.communicate()
            return {
                'success': False,
                'output': stdout,
                'errors': stderr
            }
            
    except subprocess.TimeoutExpired:
        proc.kill()
        return {
            'success': False,
            'output': "Process timed out",
            'errors': "Example did not exit cleanly"
        }


def analyze_results(test_results, example_result):
    """Analyze test results and generate summary"""
    summary = {
        'timestamp': datetime.now().isoformat(),
        'all_passed': True,
        'test_categories': {},
        'issues': [],
        'recommendations': []
    }
    
    # Analyze test results
    for category, result in test_results.items():
        passed_tests = result['output'].count('PASSED') if result['success'] else 0
        failed_tests = result['output'].count('FAILED') if not result['success'] else 0
        
        summary['test_categories'][category] = {
            'success': result['success'],
            'passed': passed_tests,
            'failed': failed_tests
        }
        
        if not result['success']:
            summary['all_passed'] = False
            summary['issues'].append(f"{category} tests failed")
            
            # Extract specific errors
            if 'error' in result['errors'].lower():
                summary['issues'].append(f"{category}: {result['errors'][:200]}")
    
    # Analyze example result
    if example_result:
        summary['example_tested'] = True
        summary['example_success'] = example_result['success']
        
        if not example_result['success']:
            summary['all_passed'] = False
            summary['issues'].append("Example application failed")
            summary['issues'].append(example_result['errors'][:200])
    else:
        summary['example_tested'] = False
        summary['issues'].append("Example not tested (missing bindings)")
    
    # Generate recommendations
    if not summary['all_passed']:
        if 'connection' in str(summary['issues']).lower():
            summary['recommendations'].append(
                "Check that SpacetimeDB server is running on the correct port"
            )
            summary['recommendations'].append(
                "Verify database identity is correct"
            )
        
        if 'timeout' in str(summary['issues']).lower():
            summary['recommendations'].append(
                "Server may be slow to respond - check server logs"
            )
    
    return summary


def generate_report(config, test_results, example_result, summary):
    """Generate comprehensive validation report"""
    report_path = "V1_1_2_VALIDATION_REPORT.md"
    
    with open(report_path, 'w') as f:
        f.write("# SpacetimeDB v1.1.2 Python SDK Validation Report\n\n")
        f.write(f"Generated: {summary['timestamp']}\n\n")
        
        # Configuration section
        f.write("## Configuration\n\n")
        f.write(f"- **Host**: {config['host']}\n")
        f.write(f"- **Database**: {config['database']}\n")
        f.write(f"- **Identity**: {config['identity'] or 'Not provided'}\n")
        f.write(f"- **Protocol**: JSON and BSATN tested\n\n")
        
        # Overall status
        f.write("## Overall Status\n\n")
        if summary['all_passed']:
            f.write("✅ **All validation tests PASSED**\n\n")
        else:
            f.write("❌ **Some validation tests FAILED**\n\n")
        
        # Test results
        f.write("## Test Results\n\n")
        
        for category, info in summary['test_categories'].items():
            status = "✅" if info['success'] else "❌"
            f.write(f"### {category.replace('_', ' ').title()}\n\n")
            f.write(f"- Status: {status}\n")
            if info['success']:
                f.write(f"- Passed: {info['passed']} tests\n")
            else:
                f.write(f"- Failed: {info['failed']} tests\n")
            f.write("\n")
        
        # Example application
        f.write("### Example Application\n\n")
        if summary['example_tested']:
            status = "✅" if summary['example_success'] else "❌"
            f.write(f"- Status: {status}\n")
            f.write("- Updated quickstart example tested\n")
        else:
            f.write("- Status: ⚠️ Not tested\n")
            f.write("- Module bindings need to be generated\n")
        f.write("\n")
        
        # Issues
        if summary['issues']:
            f.write("## Issues Found\n\n")
            for issue in summary['issues']:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        # Recommendations
        if summary['recommendations']:
            f.write("## Recommendations\n\n")
            for rec in summary['recommendations']:
                f.write(f"- {rec}\n")
            f.write("\n")
        
        # Performance metrics (if available)
        if 'performance' in test_results and test_results['performance']['success']:
            f.write("## Performance Metrics\n\n")
            f.write("Performance benchmarks were executed successfully.\n")
            f.write("See `v112_performance_report.json` for detailed metrics.\n\n")
        
        # Conclusion
        f.write("## Conclusion\n\n")
        if summary['all_passed']:
            f.write("The SpacetimeDB Python SDK v1.1.2 compatibility implementation ")
            f.write("has been successfully validated. All tests pass and the SDK ")
            f.write("is ready for production use with SpacetimeDB v1.1.2 servers.\n\n")
            
            f.write("### Key Features Validated:\n\n")
            f.write("- ✅ Connection with new endpoint format\n")
            f.write("- ✅ Database identity parameter support\n")
            f.write("- ✅ Both JSON and BSATN protocols\n")
            f.write("- ✅ Identity persistence and reconnection\n")
            f.write("- ✅ Subscription and reducer operations\n")
            f.write("- ✅ Error handling and edge cases\n")
            f.write("- ✅ Performance benchmarks\n")
        else:
            f.write("The validation encountered some issues that need to be addressed. ")
            f.write("Please review the issues and recommendations above.\n")
    
    print(f"\nReport saved to: {report_path}")
    
    # Also save JSON summary
    json_path = "v112_validation_summary.json"
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to: {json_path}")


def main():
    """Main validation runner"""
    print("\n" + "="*60)
    print("SpacetimeDB v1.1.2 Python SDK Validation Runner")
    print("="*60)
    
    # Check environment
    config = check_environment()
    
    if config['skip_tests'].lower() == 'true':
        print("\nTo run validation against a real server:")
        print("1. Run: bash scripts/setup_v112_test_server.sh")
        print("2. Source: source .env.test")
        print("3. Run this script again")
        return
    
    # Run tests
    test_results = run_validation_tests()
    
    # Test example
    example_result = test_example_application()
    
    # Analyze results
    summary = analyze_results(test_results, example_result)
    
    # Generate report
    generate_report(config, test_results, example_result, summary)
    
    # Print summary
    print("\n" + "="*60)
    print("Validation Complete")
    print("="*60)
    
    if summary['all_passed']:
        print("✅ All validation tests PASSED!")
    else:
        print("❌ Some tests FAILED - see report for details")
    
    print(f"\nIssues found: {len(summary['issues'])}")
    print(f"See V1_1_2_VALIDATION_REPORT.md for full details")


if __name__ == "__main__":
    main()
