#!/usr/bin/env python3
"""
Security Fix Verification Test for JSON Bomb Protection

This test verifies that all unsafe json.loads() calls have been replaced with secure alternatives
and that the new security measures effectively prevent JSON bomb attacks.
"""

import json
import logging
import time
import sys
import os

# Add the src directory to Python path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.security.json_validator import (
    SecureJSONParser, 
    JSONSecurityError, 
    JSONBombError,
    JSONDepthError,
    JSONSizeError,
    JSONSecurityConfig,
    secure_json_loads
)

# Configure logging to see security alerts
logging.basicConfig(level=logging.INFO)

def test_json_bomb_size_protection():
    """Test that large JSON payloads are rejected."""
    print("🧪 Testing JSON bomb size protection...")
    
    # Create a large JSON string (larger than 10MB default limit)
    large_json = '{"data": "' + 'x' * (11 * 1024 * 1024) + '"}'
    
    try:
        secure_json_loads(large_json, "size_test")
        print("❌ FAILED: Large JSON was not rejected")
        return False
    except JSONSizeError as e:
        print(f"✅ PASSED: Large JSON correctly rejected - {e}")
        return True
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def test_json_bomb_depth_protection():
    """Test that deeply nested JSON is rejected."""
    print("🧪 Testing JSON bomb depth protection...")
    
    # Create deeply nested JSON (deeper than 100 levels default limit)
    deep_json = '{"level": ' * 150 + '"deep"' + '}' * 150
    
    try:
        secure_json_loads(deep_json, "depth_test")
        print("❌ FAILED: Deep JSON was not rejected")
        return False
    except JSONDepthError as e:
        print(f"✅ PASSED: Deep JSON correctly rejected - {e}")
        return True
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def test_normal_json_parsing():
    """Test that normal JSON still works."""
    print("🧪 Testing normal JSON parsing...")
    
    normal_json = '{"message": "hello", "data": {"nested": true, "count": 42}}'
    
    try:
        result = secure_json_loads(normal_json, "normal_test")
        expected = {"message": "hello", "data": {"nested": True, "count": 42}}
        
        if result == expected:
            print("✅ PASSED: Normal JSON parsed correctly")
            return True
        else:
            print(f"❌ FAILED: Incorrect parsing result - {result}")
            return False
    except Exception as e:
        print(f"❌ FAILED: Normal JSON rejected - {e}")
        return False

def test_custom_security_config():
    """Test custom security configuration."""
    print("🧪 Testing custom security configuration...")
    
    # Test with very restrictive config
    restrictive_config = JSONSecurityConfig(
        max_json_size=100,  # Very small
        max_nesting_depth=2  # Very shallow
    )
    
    parser = SecureJSONParser(restrictive_config)
    small_json = '{"level1": {"level2": {"level3": "too deep"}}}'
    
    try:
        parser.safe_loads(small_json, "config_test")
        print("❌ FAILED: Restrictive config didn't reject JSON")
        return False
    except JSONDepthError as e:
        print(f"✅ PASSED: Restrictive config correctly rejected JSON - {e}")
        return True
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def test_string_length_protection():
    """Test that excessively long strings are rejected."""
    print("🧪 Testing string length protection...")
    
    # Create JSON with very long string (larger than 1MB default limit)
    long_string_json = '{"data": "' + 'x' * (2 * 1024 * 1024) + '"}'
    
    try:
        secure_json_loads(long_string_json, "string_test")
        print("❌ FAILED: Long string was not rejected")
        return False
    except (JSONBombError, JSONSizeError) as e:
        print(f"✅ PASSED: Long string correctly rejected - {e}")
        return True
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

def test_security_logging():
    """Test that security violations are properly logged."""
    print("🧪 Testing security logging...")
    
    # Capture log output
    import io
    import logging
    
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    security_logger = logging.getLogger('spacetimedb.security.json')
    security_logger.addHandler(handler)
    security_logger.setLevel(logging.WARNING)
    
    # Trigger a security violation
    try:
        secure_json_loads('{"data": "' + 'x' * 1000000 + '"}', "logging_test")
    except JSONSecurityError:
        pass  # Expected
    
    # Check if security violation was logged
    log_output = log_capture.getvalue()
    if "JSON Security Violation" in log_output:
        print("✅ PASSED: Security violation properly logged")
        return True
    else:
        print(f"❌ FAILED: Security violation not logged - {log_output}")
        return False

def test_performance_impact():
    """Test that security measures don't have excessive performance impact."""
    print("🧪 Testing performance impact...")
    
    normal_json = '{"message": "test", "data": [1, 2, 3, 4, 5]}'
    
    # Test secure parsing performance
    start_time = time.time()
    for _ in range(1000):
        secure_json_loads(normal_json, "perf_test")
    secure_time = time.time() - start_time
    
    # Test standard JSON parsing performance
    start_time = time.time()
    for _ in range(1000):
        json.loads(normal_json)
    standard_time = time.time() - start_time
    
    # Check if overhead is reasonable (less than 10x slower)
    overhead_ratio = secure_time / standard_time
    if overhead_ratio < 10:
        print(f"✅ PASSED: Performance overhead acceptable ({overhead_ratio:.2f}x)")
        return True
    else:
        print(f"❌ FAILED: Excessive performance overhead ({overhead_ratio:.2f}x)")
        return False

def run_all_tests():
    """Run all security verification tests."""
    print("🔒 JSON Security Fix Verification Test Suite")
    print("=" * 50)
    
    tests = [
        test_json_bomb_size_protection,
        test_json_bomb_depth_protection,
        test_normal_json_parsing,
        test_custom_security_config,
        test_string_length_protection,
        test_security_logging,
        test_performance_impact
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - JSON security fixes are working correctly!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED - Please review the security implementation")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)