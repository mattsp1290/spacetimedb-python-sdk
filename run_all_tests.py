#!/usr/bin/env python3
"""
Run all test files to verify everything is working properly.
"""

import os
import sys
import subprocess
import time

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# List of test files to run
test_files = [
    # Basic functionality tests
    'test_algebraic_types.py',
    'test_bsatn_compatibility.py',
    'test_bsatn_protocol.py',
    'test_bsatn_simple.py',
    'test_collections_integration.py',
    'test_compression.py',
    'test_connection_builder.py',
    'test_connection_identity_success.py',
    'test_connection_pool.py',
    'test_core_data_types_integration.py',
    'test_cross_platform_validation.py',
    'test_data_structures.py',
    'test_db_context.py',
    'test_event_system.py',
    'test_json_api.py',
    'test_logger.py',
    'test_performance_benchmarks_simple.py',
    'test_query_id_success.py',
    'test_remote_module.py',
    'test_security_features.py',
    'test_subscription_builder.py',
    'test_table_interface.py',
    'test_testing_infrastructure.py',
    'test_time_scheduling.py',
    'test_utils.py',
    'test_wasm_integration.py',
]

def run_test(test_file):
    """Run a single test file."""
    print(f"\n{'='*60}")
    print(f"Running: {test_file}")
    print('='*60)
    
    start_time = time.time()
    try:
        # Run the test with a timeout
        result = subprocess.run(
            [sys.executable, test_file],
            env={**os.environ, 'PYTHONPATH': 'src'},
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout per test
        )
        
        elapsed_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ PASSED ({elapsed_time:.2f}s)")
            # Show last few lines of output if test passed
            output_lines = result.stdout.strip().split('\n')
            if len(output_lines) > 3:
                print("Last few lines of output:")
                for line in output_lines[-3:]:
                    print(f"  {line}")
            return True
        else:
            print(f"❌ FAILED ({elapsed_time:.2f}s)")
            print("STDOUT:")
            print(result.stdout)
            print("STDERR:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ TIMEOUT (>30s)")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all tests and report results."""
    print("Running all tests...")
    print(f"Total tests to run: {len(test_files)}")
    
    passed = 0
    failed = 0
    timed_out = 0
    
    start_time = time.time()
    
    for test_file in test_files:
        if os.path.exists(test_file):
            if run_test(test_file):
                passed += 1
            else:
                failed += 1
        else:
            print(f"\n⚠️  Skipping {test_file} - file not found")
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    print(f"Total tests run: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per test: {total_time/(passed + failed):.2f}s" if (passed + failed) > 0 else "N/A")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {failed} tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
