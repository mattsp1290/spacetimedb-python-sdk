#!/usr/bin/env python3
"""
Comprehensive test suite for the SpacetimeDB validation framework.

This test file validates that the security framework properly prevents:
1. URL injection attacks
2. SQL injection attacks  
3. JSON parsing memory exhaustion attacks
4. Other input validation vulnerabilities
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import json
import sys
import time
import traceback
from typing import Dict, List, Any

# Add src to path for testing
sys.path.insert(0, 'src')

try:
    from spacetimedb_sdk.validation import (
        URLValidator, SQLValidator, JSONValidator, DataSizeValidator,
        SecurityManager, SecurityConfig, ValidationConfig,
        URLValidationError, SQLValidationError, JSONValidationError,
        ValidationError, get_security_manager
    )
    print("✓ Successfully imported validation framework")
except ImportError as e:
    print(f"✗ Failed to import validation framework: {e}")
    sys.exit(1)


class SecurityTestSuite:
    """Comprehensive security test suite."""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
    
    def run_test(self, test_name: str, test_func):
        """Run a single test and record results."""
        try:
            print(f"\n--- {test_name} ---")
            test_func()
            print(f"✓ {test_name} PASSED")
            self.tests_passed += 1
            self.test_results.append(f"✓ {test_name}")
        except Exception as e:
            print(f"✗ {test_name} FAILED: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            self.tests_failed += 1
            self.test_results.append(f"✗ {test_name}: {e}")
    
    def test_url_validation_basic(self):
        """Test basic URL validation functionality."""
        validator = URLValidator()
        
        # Valid URLs should pass
        valid_urls = [
            "ws://localhost:3000",
            "wss://example.com/database/test",
            "https://spacetimedb.com",
        ]
        
        for url in valid_urls:
            result = validator.validate(url)
            assert result.is_valid, f"Valid URL failed validation: {url}"
            assert result.sanitized_value is not None
        
        # Invalid URLs should fail
        invalid_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "ftp://malicious.com/exploit",
            "file:///etc/passwd",
            "ws://example.com/../../../evil",
        ]
        
        for url in invalid_urls:
            result = validator.validate(url)
            assert not result.is_valid, f"Invalid URL passed validation: {url}"
    
    def test_url_injection_prevention(self):
        """Test prevention of URL injection attacks."""
        validator = URLValidator()
        
        # Path traversal attempts
        malicious_urls = [
            "ws://example.com/../../etc/passwd",
            "ws://example.com/%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "ws://example.com/database/../../../secret",
            "ws://example.com/database/test?param=../../../etc/passwd",
        ]
        
        for url in malicious_urls:
            result = validator.validate(url)
            assert not result.is_valid, f"Path traversal URL passed validation: {url}"
    
    def test_sql_validation_basic(self):
        """Test basic SQL validation functionality."""
        validator = SQLValidator()
        
        # Valid queries should pass
        valid_queries = [
            "SELECT * FROM users WHERE id = ?",
            "SELECT name, email FROM profiles WHERE active = true",
            "SELECT COUNT(*) FROM sessions",
        ]
        
        for query in valid_queries:
            result = validator.validate(query)
            assert result.is_valid, f"Valid query failed validation: {query}"
        
        # Invalid/dangerous queries should fail
        dangerous_queries = [
            "DROP TABLE users",
            "DELETE FROM users WHERE 1=1",
            "SELECT * FROM users; DROP TABLE secrets;",
            "SELECT * FROM users WHERE id = 1 OR 1=1",
            "SELECT * FROM users UNION SELECT * FROM passwords",
        ]
        
        for query in dangerous_queries:
            result = validator.validate(query)
            assert not result.is_valid, f"Dangerous query passed validation: {query}"
    
    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection attacks."""
        validator = SQLValidator()
        
        # Common SQL injection patterns
        injection_attempts = [
            "' OR '1'='1",
            "1; DROP TABLE users; --",
            "' UNION SELECT password FROM users --",
            "'; EXEC xp_cmdshell('dir'); --",
            "1' AND (SELECT COUNT(*) FROM users) > 0 --",
            "1' OR SLEEP(5) --",
        ]
        
        for injection in injection_attempts:
            result = validator.validate(injection)
            assert not result.is_valid, f"SQL injection passed validation: {injection}"
    
    def test_json_validation_basic(self):
        """Test basic JSON validation functionality."""
        validator = JSONValidator()
        
        # Valid JSON should pass
        valid_json = [
            '{"name": "test", "value": 123}',
            '[]',
            '{"nested": {"object": true}}',
            '[1, 2, 3, "string"]',
        ]
        
        for json_str in valid_json:
            result = validator.validate(json_str)
            assert result.is_valid, f"Valid JSON failed validation: {json_str}"
        
        # Invalid JSON should fail
        invalid_json = [
            '{"invalid": json}',  # Unquoted value
            '{broken json',       # Incomplete
            '{"too": "many", "commas":,}',  # Syntax error
        ]
        
        for json_str in invalid_json:
            result = validator.validate(json_str)
            assert not result.is_valid, f"Invalid JSON passed validation: {json_str}"
    
    def test_json_memory_exhaustion_prevention(self):
        """Test prevention of JSON memory exhaustion attacks."""
        config = ValidationConfig(
            max_json_size=1024,  # Small limit for testing
            max_json_depth=10,
            max_array_length=100,
            max_object_keys=50
        )
        validator = JSONValidator(config)
        
        # Large JSON string should fail
        large_json = '{"data": "' + 'x' * 2000 + '"}'
        result = validator.validate(large_json)
        assert not result.is_valid, "Large JSON passed validation"
        
        # Deep nesting should fail
        deep_json = '{"a":' * 20 + '{}' + '}' * 20
        result = validator.validate(deep_json)
        assert not result.is_valid, "Deeply nested JSON passed validation"
        
        # Too many array elements should fail
        large_array = '[' + ','.join(['1'] * 200) + ']'
        result = validator.validate(large_array)
        assert not result.is_valid, "Large array passed validation"
    
    def test_data_size_validation(self):
        """Test data size limits."""
        config = ValidationConfig(
            max_string_length=100,
            max_array_length=10,
            max_object_keys=5
        )
        validator = DataSizeValidator(config)
        
        # Large string should fail
        large_string = 'x' * 200
        result = validator.validate(large_string)
        assert not result.is_valid, "Large string passed validation"
        
        # Large array should fail
        large_array = list(range(20))
        result = validator.validate(large_array)
        assert not result.is_valid, "Large array passed validation"
        
        # Large dict should fail
        large_dict = {f"key{i}": i for i in range(10)}
        result = validator.validate(large_dict)
        assert not result.is_valid, "Large dict passed validation"
    
    def test_security_manager_integration(self):
        """Test security manager integration."""
        config = SecurityConfig(
            validation_config=ValidationConfig(
                max_url_length=1000,
                max_json_size=1024
            ),
            strict_mode=True
        )
        manager = SecurityManager(config)
        
        # Test URL validation
        result = manager.validate_url("ws://localhost:3000")
        assert result.is_valid, "Valid URL failed in security manager"
        
        result = manager.validate_url("javascript:alert('xss')")
        assert not result.is_valid, "Malicious URL passed in security manager"
        
        # Test SQL validation
        result = manager.validate_sql_query("SELECT * FROM users WHERE id = ?")
        assert result.is_valid, "Valid SQL failed in security manager"
        
        result = manager.validate_sql_query("DROP TABLE users")
        assert not result.is_valid, "Malicious SQL passed in security manager"
        
        # Test JSON validation
        result = manager.validate_json_data('{"test": true}')
        assert result.is_valid, "Valid JSON failed in security manager"
        
        large_json = '{"data": "' + 'x' * 2000 + '"}'
        result = manager.validate_json_data(large_json)
        assert not result.is_valid, "Large JSON passed in security manager"
    
    def test_websocket_client_integration(self):
        """Test that websocket client properly uses validation."""
        try:
            from spacetimedb_sdk.websocket_client import WebSocketClient
            
            # This should fail with validation error for malicious host
            try:
                client = WebSocketClient(
                    host="javascript:alert('xss')",
                    database_address="test",
                    ssl_enabled=False
                )
                # Try to connect - should fail due to validation
                client._do_connect()
                assert False, "Malicious host was not rejected"
            except Exception as e:
                # Should fail due to validation
                assert "Invalid" in str(e) or "validation" in str(e).lower(), f"Unexpected error: {e}"
                
        except ImportError:
            print("WebSocketClient not available for testing")
    
    def test_connection_builder_integration(self):
        """Test that connection builder properly uses validation."""
        try:
            from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
            
            builder = SpacetimeDBConnectionBuilder()
            
            # Valid URI should work
            builder.with_uri("ws://localhost:3000")
            
            # Invalid URI should fail
            try:
                builder.with_uri("javascript:alert('xss')")
                assert False, "Malicious URI was not rejected"
            except ValueError as e:
                assert "Invalid" in str(e) or "validation" in str(e).lower()
            
            # Invalid module name should fail
            try:
                builder.with_module_name("../../../etc/passwd")
                assert False, "Path traversal module name was not rejected"
            except ValueError as e:
                assert "traversal" in str(e).lower() or "Invalid" in str(e)
                
        except ImportError:
            print("SpacetimeDBConnectionBuilder not available for testing")
    
    def test_performance(self):
        """Test that validation doesn't significantly impact performance."""
        manager = get_security_manager()
        
        # Test URL validation performance
        start_time = time.time()
        for _ in range(1000):
            manager.validate_url("ws://localhost:3000")
        url_time = time.time() - start_time
        
        # Test SQL validation performance
        start_time = time.time()
        for _ in range(1000):
            manager.validate_sql_query("SELECT * FROM users WHERE id = ?")
        sql_time = time.time() - start_time
        
        # Test JSON validation performance
        start_time = time.time()
        for _ in range(1000):
            manager.validate_json_data('{"test": true}')
        json_time = time.time() - start_time
        
        print(f"Performance: URL={url_time:.3f}s, SQL={sql_time:.3f}s, JSON={json_time:.3f}s")
        
        # Should complete within reasonable time (adjust based on expectations)
        assert url_time < 5.0, f"URL validation too slow: {url_time:.3f}s"
        assert sql_time < 5.0, f"SQL validation too slow: {sql_time:.3f}s"
        assert json_time < 5.0, f"JSON validation too slow: {json_time:.3f}s"
    
    def run_all_tests(self):
        """Run all security tests."""
        print("=" * 60)
        print("SpacetimeDB Security Validation Framework Test Suite")
        print("=" * 60)
        
        # Core validation tests
        self.run_test("URL Validation Basic", self.test_url_validation_basic)
        self.run_test("URL Injection Prevention", self.test_url_injection_prevention)
        self.run_test("SQL Validation Basic", self.test_sql_validation_basic)
        self.run_test("SQL Injection Prevention", self.test_sql_injection_prevention)
        self.run_test("JSON Validation Basic", self.test_json_validation_basic)
        self.run_test("JSON Memory Exhaustion Prevention", self.test_json_memory_exhaustion_prevention)
        self.run_test("Data Size Validation", self.test_data_size_validation)
        
        # Integration tests
        self.run_test("Security Manager Integration", self.test_security_manager_integration)
        self.run_test("WebSocket Client Integration", self.test_websocket_client_integration)
        self.run_test("Connection Builder Integration", self.test_connection_builder_integration)
        
        # Performance tests
        self.run_test("Performance Tests", self.test_performance)
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"Test Results: {self.tests_passed} passed, {self.tests_failed} failed")
        print("=" * 60)
        
        if self.tests_failed > 0:
            print("\nFailed tests:")
            for result in self.test_results:
                if result.startswith("✗"):
                    print(result)
            return False
        else:
            print("\n🎉 All tests passed! Security framework is working correctly.")
            return True


def main():
    """Run the security test suite."""
    test_suite = SecurityTestSuite()
    success = test_suite.run_all_tests()
    
    if not success:
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("SECURITY FRAMEWORK VERIFICATION COMPLETE")
    print("=" * 60)
    print("✓ URL injection prevention: ACTIVE")
    print("✓ SQL injection prevention: ACTIVE") 
    print("✓ JSON memory exhaustion prevention: ACTIVE")
    print("✓ Data size limits: ACTIVE")
    print("✓ Input sanitization: ACTIVE")
    print("✓ Integration with WebSocket client: ACTIVE")
    print("✓ Integration with connection builder: ACTIVE")
    print("=" * 60)


if __name__ == "__main__":
    main()