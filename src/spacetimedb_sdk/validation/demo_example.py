#!/usr/bin/env python3
"""
Demo example showing the enhanced validation system with timeout protection and caching.
"""

import time
import json
from typing import Dict, Any

# Import our enhanced validation system
from .sql_validator import SQLValidator
from .data_validator import JSONValidator
from .validators import ValidationConfig
from .timeout_cache_utils import (
    get_validation_cache_stats,
    clear_validation_cache,
    ValidationTimeoutError
)


def demo_sql_validation_with_caching():
    """Demonstrate SQL validation with caching benefits."""
    print("\n" + "=" * 60)
    print("SQL VALIDATION WITH CACHING DEMO")
    print("=" * 60)
    
    # Configure validator with shorter timeout for demo
    config = ValidationConfig(validation_timeout=2.0)
    sql_validator = SQLValidator(config)
    
    # Clear cache to start fresh
    clear_validation_cache()
    
    # Test queries
    queries = [
        "SELECT * FROM users WHERE id = 1",
        "SELECT name, email FROM users WHERE active = true",
        "SELECT * FROM users WHERE id = 1",  # Duplicate - should be cached
        "SELECT COUNT(*) FROM orders WHERE status = 'pending'",
        "SELECT name, email FROM users WHERE active = true",  # Duplicate - should be cached
    ]
    
    print("\nValidating SQL queries (first run - populating cache):")
    first_run_times = []
    
    for i, query in enumerate(queries, 1):
        start = time.perf_counter()
        result = sql_validator.validate(query)
        end = time.perf_counter()
        
        exec_time = (end - start) * 1000
        first_run_times.append(exec_time)
        
        status = "✓ Valid" if result.is_valid else "✗ Invalid"
        print(f"  Query {i}: {status} ({exec_time:.2f}ms)")
    
    cache_stats = get_validation_cache_stats()
    print(f"\nCache stats after first run: {cache_stats}")
    
    print("\nValidating same queries (second run - cache hits expected):")
    second_run_times = []
    
    for i, query in enumerate(queries, 1):
        start = time.perf_counter()
        result = sql_validator.validate(query)
        end = time.perf_counter()
        
        exec_time = (end - start) * 1000
        second_run_times.append(exec_time)
        
        status = "✓ Valid" if result.is_valid else "✗ Invalid"
        print(f"  Query {i}: {status} ({exec_time:.2f}ms)")
    
    cache_stats = get_validation_cache_stats()
    print(f"\nCache stats after second run: {cache_stats}")
    
    # Calculate improvement
    avg_first = sum(first_run_times) / len(first_run_times)
    avg_second = sum(second_run_times) / len(second_run_times)
    improvement = avg_first / avg_second if avg_second > 0 else 1.0
    
    print(f"\nPerformance Summary:")
    print(f"  First run avg:  {avg_first:.2f}ms")
    print(f"  Second run avg: {avg_second:.2f}ms")
    print(f"  Improvement:    {improvement:.1f}x faster")


def demo_json_validation_with_timeout():
    """Demonstrate JSON validation with timeout protection."""
    print("\n" + "=" * 60)
    print("JSON VALIDATION WITH TIMEOUT PROTECTION DEMO")
    print("=" * 60)
    
    # Configure validator with shorter timeout for demo
    config = ValidationConfig(validation_timeout=1.0, max_json_depth=10)
    json_validator = JSONValidator(config)
    
    # Test cases
    test_cases = [
        {
            'name': 'Simple JSON',
            'data': '{"name": "test", "value": 123, "active": true}'
        },
        {
            'name': 'Nested JSON',
            'data': '{"user": {"profile": {"settings": {"theme": "dark"}}}}'
        },
        {
            'name': 'Large Array',
            'data': json.dumps({"numbers": list(range(1000))})
        }
    ]
    
    # Add a deeply nested case that might timeout
    deeply_nested = {}
    current = deeply_nested
    for i in range(20):  # This exceeds our max_json_depth of 10
        current[f'level_{i}'] = {}
        current = current[f'level_{i}']
    current['data'] = 'deep_value'
    
    test_cases.append({
        'name': 'Deeply Nested JSON (should be rejected)',
        'data': json.dumps(deeply_nested)
    })
    
    print("\nValidating JSON documents:")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  Test {i}: {test_case['name']}")
        
        try:
            start = time.perf_counter()
            result = json_validator.validate(test_case['data'])
            end = time.perf_counter()
            
            exec_time = (end - start) * 1000
            status = "✓ Valid" if result.is_valid else "✗ Invalid"
            
            print(f"    Result: {status} ({exec_time:.2f}ms)")
            
            if not result.is_valid and result.errors:
                for error in result.errors[:2]:  # Show first 2 errors
                    print(f"    Error: {error}")
                    
        except ValidationTimeoutError as e:
            print(f"    Result: ⏰ Timed out - {e}")
        except Exception as e:
            print(f"    Result: ⚠ Error - {e}")


def demo_malicious_input_protection():
    """Demonstrate protection against malicious inputs."""
    print("\n" + "=" * 60)
    print("MALICIOUS INPUT PROTECTION DEMO")
    print("=" * 60)
    
    config = ValidationConfig(validation_timeout=2.0)
    sql_validator = SQLValidator(config)
    json_validator = JSONValidator(config)
    
    # SQL injection attempts
    malicious_sql_queries = [
        "SELECT * FROM users WHERE id = 1; DROP TABLE users; --",
        "SELECT * FROM users WHERE name = '' OR '1'='1' --",
        "SELECT * FROM users WHERE id = 1 UNION SELECT password FROM admin --",
        "SELECT * FROM users; EXEC xp_cmdshell('dir'); --"
    ]
    
    print("\nTesting SQL injection protection:")
    for i, query in enumerate(malicious_sql_queries, 1):
        try:
            start = time.perf_counter()
            result = sql_validator.validate(query)
            end = time.perf_counter()
            
            exec_time = (end - start) * 1000
            status = "🛡️ Blocked" if not result.is_valid else "⚠️ Allowed"
            
            print(f"  Attack {i}: {status} ({exec_time:.2f}ms)")
            
            if not result.is_valid:
                print(f"    Reason: {result.errors[0] if result.errors else 'Unknown'}")
                
        except ValidationTimeoutError:
            print(f"  Attack {i}: ⏰ Timed out (protection active)")
    
    # JSON attacks
    malicious_json_inputs = [
        # Billion laughs attack
        '{"data": "' + 'x' * 10000 + '"}',
        # Deeply nested structure
        json.dumps({"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": "deep"}}}}}}}}}}}),
    ]
    
    print("\nTesting JSON attack protection:")
    for i, json_data in enumerate(malicious_json_inputs, 1):
        try:
            start = time.perf_counter()
            result = json_validator.validate(json_data)
            end = time.perf_counter()
            
            exec_time = (end - start) * 1000
            status = "🛡️ Blocked" if not result.is_valid else "⚠️ Allowed"
            
            print(f"  Attack {i}: {status} ({exec_time:.2f}ms)")
            
            if not result.is_valid:
                print(f"    Reason: {result.errors[0] if result.errors else 'Unknown'}")
                
        except ValidationTimeoutError:
            print(f"  Attack {i}: ⏰ Timed out (protection active)")


def main():
    """Run the complete validation demo."""
    print("SpacetimeDB Enhanced Validation System Demo")
    print("Demonstrating timeout protection and caching improvements")
    
    try:
        # Run demos
        demo_sql_validation_with_caching()
        demo_json_validation_with_timeout()
        demo_malicious_input_protection()
        
        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("Key improvements demonstrated:")
        print("  ✓ Timeout protection prevents DoS attacks")
        print("  ✓ LRU caching reduces validation overhead")
        print("  ✓ Malicious input detection and blocking")
        print("  ✓ Graceful error handling and reporting")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)