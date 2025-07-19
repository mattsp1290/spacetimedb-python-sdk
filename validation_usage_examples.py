#!/usr/bin/env python3
"""
Usage examples for the SpacetimeDB validation framework.

This file demonstrates how to use the validation framework in various scenarios
to protect against injection attacks and ensure data integrity.
"""

import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk.validation import (
    # Validators
    URLValidator, SQLValidator, JSONValidator, DataSizeValidator,
    
    # Security manager
    SecurityManager, SecurityConfig, ValidationConfig,
    
    # Convenience functions
    validate_url, validate_websocket_url, validate_sql_query, validate_json_data,
    sanitize_url, sanitize_sql_query, sanitize_json_data,
    
    # Exceptions
    ValidationError, URLValidationError, SQLValidationError, JSONValidationError
)


def example_basic_validation():
    """Basic validation examples."""
    print("=== Basic Validation Examples ===")
    
    # URL validation
    print("\n1. URL Validation:")
    try:
        result = validate_url("ws://localhost:3000")
        print(f"✓ Valid URL: {result.sanitized_value}")
        
        result = validate_url("javascript:alert('xss')")
        print(f"✗ Invalid URL: {result.errors}")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")
    
    # SQL validation
    print("\n2. SQL Validation:")
    try:
        safe_query = "SELECT * FROM users WHERE id = ?"
        result = validate_sql_query(safe_query)
        print(f"✓ Safe query: {result.sanitized_value}")
        
        dangerous_query = "DROP TABLE users"
        result = validate_sql_query(dangerous_query)
        print(f"✗ Dangerous query: {result.errors}")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")
    
    # JSON validation
    print("\n3. JSON Validation:")
    try:
        safe_json = '{"name": "test", "value": 123}'
        result = validate_json_data(safe_json)
        print(f"✓ Safe JSON: {type(result.sanitized_value)}")
        
        malicious_json = '{"data": "' + 'x' * 100000 + '"}'
        result = validate_json_data(malicious_json)
        print(f"✗ Large JSON: {result.errors}")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")


def example_custom_configuration():
    """Custom validation configuration examples."""
    print("\n=== Custom Configuration Examples ===")
    
    # Create custom validation config
    config = ValidationConfig(
        max_url_length=500,           # Shorter URL limit
        max_json_size=1024,          # 1KB JSON limit
        max_string_length=100,        # 100 char string limit
        enable_strict_mode=True       # Strict validation
    )
    
    # Create security manager with custom config
    security_config = SecurityConfig(
        validation_config=config,
        strict_mode=True,
        log_violations=True
    )
    security_manager = SecurityManager(security_config)
    
    print(f"Custom config: max_url_length={config.max_url_length}")
    
    # Test with custom limits
    long_url = "ws://localhost:3000/" + "x" * 1000
    result = security_manager.validate_url(long_url)
    print(f"Long URL validation: {'✓ passed' if result.is_valid else '✗ failed'}")


def example_websocket_client_integration():
    """WebSocket client integration example."""
    print("\n=== WebSocket Client Integration ===")
    
    try:
        from spacetimedb_sdk.websocket_client import WebSocketClient
        
        print("Creating WebSocket client with validation...")
        
        # This will use validation automatically
        try:
            client = WebSocketClient(
                host="localhost:3000",
                database_address="my_game_db",
                ssl_enabled=False
            )
            print("✓ Client created with valid parameters")
        except Exception as e:
            print(f"✗ Client creation failed: {e}")
        
        # This should fail validation
        try:
            malicious_client = WebSocketClient(
                host="javascript:alert('xss')",
                database_address="../../../etc/passwd",
                ssl_enabled=False
            )
            print("✗ Malicious client was created (should not happen!)")
        except Exception as e:
            print(f"✓ Malicious client rejected: {e}")
            
    except ImportError:
        print("WebSocketClient not available")


def example_connection_builder_integration():
    """Connection builder integration example."""
    print("\n=== Connection Builder Integration ===")
    
    try:
        from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
        
        print("Creating connection with builder...")
        
        # This will use validation automatically
        try:
            client = SpacetimeDBConnectionBuilder() \
                .with_uri("ws://localhost:3000") \
                .with_module_name("my_game_db") \
                .with_token("safe_token_123")
            print("✓ Builder configured with valid parameters")
        except Exception as e:
            print(f"✗ Builder configuration failed: {e}")
        
        # This should fail validation
        try:
            malicious_builder = SpacetimeDBConnectionBuilder() \
                .with_uri("javascript:alert('xss')")
            print("✗ Malicious URI was accepted (should not happen!)")
        except Exception as e:
            print(f"✓ Malicious URI rejected: {e}")
            
    except ImportError:
        print("SpacetimeDBConnectionBuilder not available")


def example_parameterized_queries():
    """Parameterized query examples."""
    print("\n=== Parameterized Query Examples ===")
    
    validator = SQLValidator()
    
    # Safe parameterized query
    template = "SELECT * FROM users WHERE name = :name AND age > :min_age"
    params = {"name": "john_doe", "min_age": 18}
    
    try:
        query, param_list = validator.create_parameterized_query(template, params)
        print(f"✓ Parameterized query: {query}")
        print(f"✓ Parameters: {param_list}")
    except Exception as e:
        print(f"✗ Parameterized query failed: {e}")
    
    # Validate individual parameters
    print("\n4. Parameter Validation:")
    safe_params = ["john_doe", 25, True]
    dangerous_params = ["'; DROP TABLE users; --", "x" * 10000]
    
    for param in safe_params + dangerous_params:
        result = validator.validate_parameter_value(param, "test_param")
        status = "✓" if result.is_valid else "✗"
        print(f"{status} Parameter '{param}': {'valid' if result.is_valid else 'invalid'}")


def example_security_monitoring():
    """Security monitoring examples."""
    print("\n=== Security Monitoring Examples ===")
    
    # Create security manager with monitoring
    def on_validation_failure(validation_type, value):
        print(f"🚨 Validation failure: {validation_type} - {value}")
    
    def on_security_violation(violation_type, details, value):
        print(f"🔒 Security violation: {violation_type} - {details}")
    
    config = SecurityConfig(
        log_violations=True,
        on_validation_failure=on_validation_failure,
        on_security_violation=on_security_violation
    )
    
    manager = SecurityManager(config)
    
    # Trigger some validation failures for demonstration
    print("\nTriggering validation failures...")
    manager.validate_url("javascript:alert('test')")  # Should trigger callback
    manager.validate_sql_query("DROP TABLE users")    # Should trigger callback
    
    # Show security metrics
    metrics = manager.get_security_metrics()
    print(f"\nSecurity metrics: {metrics}")


def example_performance_optimization():
    """Performance optimization examples."""
    print("\n=== Performance Optimization Examples ===")
    
    import time
    
    # Create validators once and reuse
    url_validator = URLValidator()
    sql_validator = SQLValidator()
    json_validator = JSONValidator()
    
    # Batch validation for better performance
    urls_to_validate = [
        "ws://localhost:3000",
        "wss://example.com/db",
        "ws://test.spacetimedb.com"
    ]
    
    start_time = time.time()
    
    valid_urls = []
    for url in urls_to_validate:
        result = url_validator.validate(url)
        if result.is_valid:
            valid_urls.append(result.sanitized_value)
    
    end_time = time.time()
    
    print(f"Validated {len(urls_to_validate)} URLs in {end_time - start_time:.3f}s")
    print(f"Valid URLs: {len(valid_urls)}")


def example_error_handling():
    """Error handling examples."""
    print("\n=== Error Handling Examples ===")
    
    # Specific validation errors
    try:
        sanitize_url("javascript:alert('xss')")
    except URLValidationError as e:
        print(f"URL error: {e}")
    except ValidationError as e:
        print(f"General validation error: {e}")
    
    try:
        sanitize_sql_query("DROP TABLE users")
    except SQLValidationError as e:
        print(f"SQL error: {e}")
    except ValidationError as e:
        print(f"General validation error: {e}")
    
    try:
        large_json = '{"data": "' + 'x' * 100000 + '"}'
        sanitize_json_data(large_json)
    except JSONValidationError as e:
        print(f"JSON error: {e}")
    except ValidationError as e:
        print(f"General validation error: {e}")


def example_best_practices():
    """Best practices examples."""
    print("\n=== Best Practices Examples ===")
    
    print("1. Always validate user input before processing")
    print("2. Use parameterized queries for SQL operations")
    print("3. Set appropriate size limits for your use case")
    print("4. Enable logging for security monitoring")
    print("5. Use the global security manager for consistency")
    print("6. Handle validation errors gracefully")
    print("7. Regularly review security metrics")
    
    # Example of proper input validation flow
    def safe_database_operation(user_query: str, user_data: dict):
        """Example of safe database operation with validation."""
        try:
            # 1. Validate SQL query
            query_result = validate_sql_query(user_query)
            if not query_result.is_valid:
                raise ValueError("Invalid query")
            
            # 2. Validate JSON data
            data_result = validate_json_data(user_data)
            if not data_result.is_valid:
                raise ValueError("Invalid data")
            
            # 3. Use sanitized values
            safe_query = query_result.sanitized_value
            safe_data = data_result.sanitized_value
            
            print(f"✓ Safe operation with query: {safe_query[:50]}...")
            return True
            
        except ValidationError as e:
            print(f"✗ Operation rejected: {e}")
            return False
    
    # Test safe operation
    print("\nTesting safe database operation:")
    safe_database_operation(
        "SELECT * FROM users WHERE id = ?",
        {"user_id": 123, "active": True}
    )
    
    safe_database_operation(
        "DROP TABLE users",  # Should be rejected
        {"malicious": "data"}
    )


def main():
    """Run all validation examples."""
    print("SpacetimeDB Validation Framework - Usage Examples")
    print("=" * 60)
    
    example_basic_validation()
    example_custom_configuration()
    example_websocket_client_integration()
    example_connection_builder_integration()
    example_parameterized_queries()
    example_security_monitoring()
    example_performance_optimization()
    example_error_handling()
    example_best_practices()
    
    print("\n" + "=" * 60)
    print("🎯 Examples complete! Check the output above for usage patterns.")
    print("📖 Integrate these patterns into your SpacetimeDB applications.")
    print("=" * 60)


if __name__ == "__main__":
    main()