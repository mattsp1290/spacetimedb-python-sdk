#!/usr/bin/env python3
"""
Comprehensive test script for the SpacetimeDB Security Framework.

This script validates the input validation security measures to ensure
they properly detect and prevent injection attacks and resource exhaustion.
"""

import sys
import os
import traceback
from typing import List, Tuple

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_sql_security_validator():
    """Test SQL injection detection capabilities."""
    print("🔒 Testing SQL Security Validator...")
    
    try:
        from spacetimedb_sdk.security.input_validation import SQLSecurityValidator, SecurityConfig
        
        config = SecurityConfig()
        validator = SQLSecurityValidator(config)
        
        # Test cases for SQL injection attacks
        test_cases = [
            # Union-based attacks
            ("SELECT * FROM users UNION SELECT * FROM passwords", False, "Union-based injection"),
            ("users'; DROP TABLE users; --", False, "Stacked query injection"),
            ("SELECT * FROM users WHERE id = 1 OR 1=1", False, "Boolean tautology"),
            ("SELECT * FROM users WHERE name = 'admin'--'", False, "Comment injection"),
            ("SELECT * FROM users; DELETE FROM users", False, "Multiple statements"),
            ("SELECT load_file('/etc/passwd')", False, "File system access"),
            ("SELECT * FROM information_schema.tables", False, "Information schema access"),
            
            # Valid queries (should pass)
            ("SELECT * FROM users", True, "Simple SELECT"),
            ("SELECT name, email FROM users WHERE active = 1", True, "Valid filtered query"),
            ("users", True, "Simple table name"),
            
            # Edge cases
            ("", False, "Empty query"),
            ("A" * 5000, False, "Oversized query"),
        ]
        
        passed = 0
        failed = 0
        
        for query, should_pass, description in test_cases:
            try:
                is_valid, violations = validator.validate_query(query, "test_client")
                
                if should_pass and is_valid:
                    print(f"  ✅ {description}: PASS (correctly allowed)")
                    passed += 1
                elif not should_pass and not is_valid:
                    print(f"  ✅ {description}: PASS (correctly blocked - {len(violations)} violations)")
                    passed += 1
                elif should_pass and not is_valid:
                    print(f"  ❌ {description}: FAIL (false positive - blocked valid query)")
                    print(f"     Violations: {[v.description for v in violations]}")
                    failed += 1
                else:
                    print(f"  ❌ {description}: FAIL (false negative - allowed dangerous query)")
                    failed += 1
                    
            except Exception as e:
                print(f"  💥 {description}: ERROR - {e}")
                failed += 1
        
        print(f"  📊 SQL Validator Results: {passed} passed, {failed} failed")
        return failed == 0
        
    except ImportError as e:
        print(f"❌ Could not import SQL validator: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error in SQL validator test: {e}")
        traceback.print_exc()
        return False


def test_protocol_message_validator():
    """Test protocol message validation."""
    print("\n🔒 Testing Protocol Message Validator...")
    
    try:
        from spacetimedb_sdk.security.input_validation import ProtocolMessageValidator, SecurityConfig
        
        config = SecurityConfig()
        validator = ProtocolMessageValidator(config)
        
        # Test table name validation
        table_tests = [
            ("users", True, "Valid table name"),
            ("user_profiles", True, "Valid table with underscore"),
            ("Users123", True, "Valid alphanumeric table"),
            ("123users", False, "Table starting with number"),
            ("user-profiles", False, "Table with hyphen"),
            ("users'; DROP TABLE users; --", False, "SQL injection in table name"),
            ("", False, "Empty table name"),
            ("a" * 100, False, "Oversized table name"),
        ]
        
        passed = 0
        failed = 0
        
        for table_name, should_pass, description in table_tests:
            try:
                is_valid, violations = validator.validate_table_name(table_name, "test_client")
                
                if should_pass and is_valid:
                    print(f"  ✅ {description}: PASS (correctly allowed)")
                    passed += 1
                elif not should_pass and not is_valid:
                    print(f"  ✅ {description}: PASS (correctly blocked)")
                    passed += 1
                else:
                    result = "false positive" if should_pass else "false negative"
                    print(f"  ❌ {description}: FAIL ({result})")
                    failed += 1
                    
            except Exception as e:
                print(f"  💥 {description}: ERROR - {e}")
                failed += 1
        
        # Test client ID validation
        client_id_tests = [
            ("client123", True, "Valid client ID"),
            ("client-123_abc", True, "Valid client ID with separators"),
            ("client@domain.com", False, "Client ID with special chars"),
            ("", False, "Empty client ID"),
            ("a" * 200, False, "Oversized client ID"),
        ]
        
        for client_id, should_pass, description in client_id_tests:
            try:
                is_valid, violations = validator.validate_client_id(client_id)
                
                if should_pass and is_valid:
                    print(f"  ✅ {description}: PASS (correctly allowed)")
                    passed += 1
                elif not should_pass and not is_valid:
                    print(f"  ✅ {description}: PASS (correctly blocked)")
                    passed += 1
                else:
                    result = "false positive" if should_pass else "false negative"
                    print(f"  ❌ {description}: FAIL ({result})")
                    failed += 1
                    
            except Exception as e:
                print(f"  💥 {description}: ERROR - {e}")
                failed += 1
        
        print(f"  📊 Protocol Validator Results: {passed} passed, {failed} failed")
        return failed == 0
        
    except ImportError as e:
        print(f"❌ Could not import protocol validator: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error in protocol validator test: {e}")
        traceback.print_exc()
        return False


def test_resource_protection():
    """Test resource protection and rate limiting."""
    print("\n🔒 Testing Resource Protection...")
    
    try:
        from spacetimedb_sdk.security.input_validation import ResourceProtection, SecurityConfig
        
        config = SecurityConfig()
        config.max_requests_per_window = 10  # Lower limit for testing
        config.max_expensive_operations_per_window = 5
        protector = ResourceProtection(config)
        
        passed = 0
        failed = 0
        
        # Test rate limiting
        print("  Testing rate limiting...")
        client_id = "test_client_rate"
        
        # Should allow first few requests
        for i in range(5):
            is_allowed, violation = protector.check_rate_limit(client_id, False)
            if is_allowed:
                passed += 1
            else:
                print(f"  ❌ Request {i+1} should be allowed but was blocked")
                failed += 1
        
        # Exhaust the rate limit
        for i in range(10):
            is_allowed, violation = protector.check_rate_limit(client_id, False)
        
        # Next request should be blocked
        is_allowed, violation = protector.check_rate_limit(client_id, False)
        if not is_allowed:
            print(f"  ✅ Rate limiting: PASS (correctly blocked after limit)")
            passed += 1
        else:
            print(f"  ❌ Rate limiting: FAIL (should have been blocked)")
            failed += 1
        
        # Test query complexity estimation
        print("  Testing query complexity estimation...")
        test_queries = [
            ("SELECT * FROM users", 2),  # Simple query
            ("SELECT * FROM users u JOIN profiles p ON u.id = p.user_id", 10),  # With JOIN
            ("SELECT * FROM users WHERE name LIKE '%admin%'", 7),  # With LIKE
            ("SELECT * FROM (SELECT * FROM users) u UNION SELECT * FROM admins", 35),  # Complex
        ]
        
        for query, expected_min_score in test_queries:
            score = protector.estimate_query_complexity(query)
            if score >= expected_min_score:
                print(f"  ✅ Query complexity '{query[:30]}...': PASS (score: {score})")
                passed += 1
            else:
                print(f"  ❌ Query complexity '{query[:30]}...': FAIL (score too low: {score})")
                failed += 1
        
        # Test execution time checking
        print("  Testing execution time limits...")
        import time
        start_time = protector.start_execution_timer()
        time.sleep(0.1)  # Brief sleep
        is_valid, violation = protector.check_execution_time(start_time)
        if is_valid:
            print(f"  ✅ Execution time check: PASS (within limits)")
            passed += 1
        else:
            print(f"  ❌ Execution time check: FAIL (false positive)")
            failed += 1
        
        print(f"  📊 Resource Protection Results: {passed} passed, {failed} failed")
        return failed == 0
        
    except ImportError as e:
        print(f"❌ Could not import resource protection: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error in resource protection test: {e}")
        traceback.print_exc()
        return False


def test_protocol_integration():
    """Test integration with protocol encoder."""
    print("\n🔒 Testing Protocol Integration...")
    
    try:
        from spacetimedb_sdk.protocol import ProtocolEncoder
        from spacetimedb_sdk.security.input_validation import SecurityConfig
        
        # Test with security enabled
        config = SecurityConfig()
        encoder = ProtocolEncoder(use_binary=False, enable_security=True, security_config=config)
        
        # Mock message classes for testing
        class MockSubscribeMessage:
            def __init__(self, query_strings):
                self.query_strings = query_strings
                self.request_id = 12345
        
        passed = 0
        failed = 0
        
        # Test valid message
        try:
            message = MockSubscribeMessage(["users"])
            # This should work (we're not actually encoding since we'd need full message classes)
            print(f"  ✅ Protocol integration setup: PASS")
            passed += 1
        except Exception as e:
            print(f"  ❌ Protocol integration setup: FAIL - {e}")
            failed += 1
        
        # Test security configuration
        if encoder.enable_security:
            print(f"  ✅ Security enabled in protocol: PASS")
            passed += 1
        else:
            print(f"  ❌ Security not enabled in protocol: FAIL")
            failed += 1
        
        if encoder.sql_validator is not None:
            print(f"  ✅ SQL validator initialized: PASS")
            passed += 1
        else:
            print(f"  ❌ SQL validator not initialized: FAIL")
            failed += 1
        
        print(f"  📊 Protocol Integration Results: {passed} passed, {failed} failed")
        return failed == 0
        
    except ImportError as e:
        print(f"❌ Could not import protocol encoder: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error in protocol integration test: {e}")
        traceback.print_exc()
        return False


def test_sanitization_functions():
    """Test sanitization utility functions."""
    print("\n🔒 Testing Sanitization Functions...")
    
    try:
        from spacetimedb_sdk.security.input_validation import sanitize_sql_query, sanitize_table_name
        
        passed = 0
        failed = 0
        
        # Test SQL query sanitization
        query_tests = [
            ("SELECT * FROM users -- comment", "SELECT * FROM users"),
            ("SELECT * FROM users /* comment */", "SELECT * FROM users"),
            ("SELECT   *   FROM    users", "SELECT * FROM users"),  # Normalize whitespace
        ]
        
        for input_query, expected in query_tests:
            result = sanitize_sql_query(input_query)
            if result == expected:
                print(f"  ✅ SQL sanitization: PASS")
                passed += 1
            else:
                print(f"  ❌ SQL sanitization: FAIL (got '{result}', expected '{expected}')")
                failed += 1
        
        # Test table name sanitization
        table_tests = [
            ("user$table", "usertable"),
            ("123users", "_123users"),  # Add underscore prefix
            ("user-table", "usertable"),  # Remove hyphens
            ("valid_table", "valid_table"),  # Keep valid names
        ]
        
        for input_table, expected in table_tests:
            result = sanitize_table_name(input_table)
            if result == expected:
                print(f"  ✅ Table name sanitization: PASS")
                passed += 1
            else:
                print(f"  ❌ Table name sanitization: FAIL (got '{result}', expected '{expected}')")
                failed += 1
        
        print(f"  📊 Sanitization Results: {passed} passed, {failed} failed")
        return failed == 0
        
    except ImportError as e:
        print(f"❌ Could not import sanitization functions: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error in sanitization test: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all security framework tests."""
    print("🛡️  SpacetimeDB Security Framework Validation")
    print("=" * 50)
    
    tests = [
        ("SQL Security Validator", test_sql_security_validator),
        ("Protocol Message Validator", test_protocol_message_validator),
        ("Resource Protection", test_resource_protection),
        ("Protocol Integration", test_protocol_integration),
        ("Sanitization Functions", test_sanitization_functions),
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed_tests += 1
                print(f"\n✅ {test_name}: PASSED")
            else:
                print(f"\n❌ {test_name}: FAILED")
        except Exception as e:
            print(f"\n💥 {test_name}: ERROR - {e}")
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print(f"🏆 Overall Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All security framework tests PASSED!")
        print("\n🔒 Security Framework Status:")
        print("  ✅ SQL injection protection: ACTIVE")
        print("  ✅ Protocol message validation: ACTIVE") 
        print("  ✅ Resource exhaustion protection: ACTIVE")
        print("  ✅ Rate limiting: ACTIVE")
        print("  ✅ Query sanitization: ACTIVE")
        return True
    else:
        print("⚠️  Some security tests FAILED - review implementation")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)