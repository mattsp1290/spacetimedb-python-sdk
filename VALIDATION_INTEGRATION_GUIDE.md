# SpacetimeDB Validation Framework Integration Guide

## Quick Start

The validation framework is automatically integrated into the SpacetimeDB Python SDK. No code changes are required for basic protection.

## Automatic Protection

### WebSocket Connections
```python
from spacetimedb_sdk import SpacetimeDBClient

# Validation happens automatically
client = SpacetimeDBClient(
    host="localhost:3000",           # ✅ Validated for security
    database_address="my_game_db",   # ✅ Validated for path traversal
    ssl_enabled=False
)
```

### Connection Builder
```python
from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder

# All inputs validated automatically
client = SpacetimeDBConnectionBuilder() \
    .with_uri("ws://localhost:3000") \    # ✅ URL validation
    .with_module_name("my_game_db") \     # ✅ Module validation
    .with_token("auth_token") \           # ✅ Token validation
    .build()
```

### SQL Queries
```python
# Query validation happens automatically
client.query("SELECT * FROM users WHERE id = ?")  # ✅ SQL injection prevention
```

## Custom Configuration

### Basic Configuration
```python
from spacetimedb_sdk.validation import configure_security, SecurityConfig, ValidationConfig

# Configure globally
configure_security(SecurityConfig(
    validation_config=ValidationConfig(
        max_url_length=1000,      # Custom URL limit
        max_json_size=5*1024*1024, # 5MB JSON limit
    ),
    strict_mode=True,             # Strict validation
    log_violations=True           # Enable logging
))
```

### Advanced Configuration
```python
from spacetimedb_sdk.validation import SecurityConfig, ValidationConfig

def security_violation_handler(violation_type, details, value):
    print(f"🚨 Security violation: {violation_type}")
    # Log to your security system
    
config = SecurityConfig(
    validation_config=ValidationConfig(
        max_url_length=500,
        max_json_size=1024*1024,  # 1MB
        max_string_length=10000,
        enable_strict_mode=True
    ),
    strict_mode=True,
    log_violations=True,
    enable_rate_limiting=True,
    max_requests_per_second=10,
    on_security_violation=security_violation_handler
)

configure_security(config)
```

## Manual Validation

### Direct Validation
```python
from spacetimedb_sdk.validation import validate_url, validate_sql_query, ValidationError

# Manual URL validation
try:
    result = validate_url(user_input_url)
    if result.is_valid:
        safe_url = result.sanitized_value
    else:
        print(f"Invalid URL: {result.errors}")
except ValidationError as e:
    print(f"Validation failed: {e}")

# Manual SQL validation
try:
    result = validate_sql_query(user_query)
    if result.is_valid:
        safe_query = result.sanitized_value
        # Execute safe query
    else:
        print(f"Dangerous query: {result.errors}")
except ValidationError as e:
    print(f"Query validation failed: {e}")
```

### Sanitization
```python
from spacetimedb_sdk.validation import sanitize_url, sanitize_sql_query, ValidationError

try:
    # Sanitize and validate in one step
    safe_url = sanitize_url(user_input)
    safe_query = sanitize_sql_query(user_query)
    
    # Use sanitized values
    client = SpacetimeDBClient(host=safe_url.split('://')[1])
    client.query(safe_query)
    
except ValidationError as e:
    print(f"Input rejected: {e}")
    # Handle invalid input appropriately
```

## Error Handling

### Graceful Error Handling
```python
from spacetimedb_sdk.validation import ValidationError, URLValidationError, SQLValidationError

def safe_connection(user_url, user_db):
    try:
        client = SpacetimeDBClient(
            host=user_url,
            database_address=user_db
        )
        return client
    except URLValidationError as e:
        print(f"Invalid URL: {e}")
        return None
    except ValidationError as e:
        print(f"Validation error: {e}")
        return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None
```

### Specific Error Types
```python
from spacetimedb_sdk.validation import (
    URLValidationError, 
    SQLValidationError, 
    JSONValidationError,
    DataSizeValidationError
)

try:
    # Your validation code
    pass
except URLValidationError as e:
    # Handle URL-specific errors
    log_security_event("url_validation_failure", str(e))
except SQLValidationError as e:
    # Handle SQL-specific errors  
    log_security_event("sql_injection_attempt", str(e))
except JSONValidationError as e:
    # Handle JSON-specific errors
    log_security_event("json_attack_attempt", str(e))
except DataSizeValidationError as e:
    # Handle size limit errors
    log_security_event("size_limit_exceeded", str(e))
```

## Security Monitoring

### Basic Monitoring
```python
from spacetimedb_sdk.validation import get_security_manager

# Get security metrics
manager = get_security_manager()
metrics = manager.get_security_metrics()

print(f"Validation failures: {metrics['validation_failures']}")
print(f"Security violations: {metrics['security_violations']}")
print(f"Blocked requests: {metrics['blocked_requests']}")
print(f"Sanitized inputs: {metrics['sanitized_inputs']}")
```

### Advanced Monitoring
```python
import time
from spacetimedb_sdk.validation import get_security_manager

def monitor_security():
    manager = get_security_manager()
    
    while True:
        metrics = manager.get_security_metrics()
        
        # Alert on high violation rates
        if metrics['validation_failures'] > 100:
            alert_security_team("High validation failure rate")
        
        if metrics['security_violations'] > 10:
            alert_security_team("Active security violations detected")
        
        # Reset metrics periodically
        manager.reset_security_metrics()
        
        time.sleep(60)  # Check every minute
```

## Best Practices

### 1. Use Automatic Validation
```python
# ✅ Good - automatic validation
client = SpacetimeDBClient(host=user_input, database_address=user_db)

# ❌ Avoid - manual string building without validation
url = f"ws://{user_input}/database/{user_db}"
```

### 2. Handle Validation Errors
```python
# ✅ Good - proper error handling
try:
    client = SpacetimeDBClient(host=user_input)
except ValidationError as e:
    show_user_error("Invalid connection details")
    log_security_event(str(e))

# ❌ Avoid - ignoring validation errors
try:
    client = SpacetimeDBClient(host=user_input)
except:
    pass  # Silent failures are dangerous
```

### 3. Use Parameterized Queries
```python
# ✅ Good - parameterized query
query = "SELECT * FROM users WHERE name = ?"
params = [user_name]
client.query_with_params(query, params)

# ❌ Avoid - string concatenation
query = f"SELECT * FROM users WHERE name = '{user_name}'"
client.query(query)
```

### 4. Configure Appropriate Limits
```python
# ✅ Good - configure based on your needs
configure_security(SecurityConfig(
    validation_config=ValidationConfig(
        max_json_size=1024*1024,    # 1MB for small messages
        max_url_length=200,         # Short URLs for your use case
    )
))

# ❌ Avoid - using default limits without consideration
# (defaults may be too permissive or restrictive for your use case)
```

### 5. Monitor Security Events
```python
# ✅ Good - monitor and respond to security events
def security_callback(violation_type, details, value):
    logger.warning(f"Security violation: {violation_type}")
    metrics_collector.increment('security_violations')
    
    # Take action for repeated violations
    if violation_type == 'sql_injection':
        block_ip(get_client_ip())

configure_security(SecurityConfig(
    on_security_violation=security_callback
))
```

## Testing Your Integration

### Validation Test
```python
def test_validation_integration():
    """Test that validation is working correctly."""
    
    # Test URL validation
    try:
        SpacetimeDBClient(host="javascript:alert('xss')")
        assert False, "Malicious URL should be rejected"
    except ValidationError:
        print("✅ URL validation working")
    
    # Test SQL validation  
    try:
        client = SpacetimeDBClient(host="localhost:3000")
        client.query("DROP TABLE users")
        assert False, "Malicious query should be rejected" 
    except ValidationError:
        print("✅ SQL validation working")
    
    print("🔒 Security validation is active and working!")

# Run the test
test_validation_integration()
```

### Performance Test
```python
import time
from spacetimedb_sdk.validation import validate_url

def test_validation_performance():
    """Test validation performance impact."""
    
    # Test validation performance
    start_time = time.time()
    for i in range(1000):
        validate_url(f"ws://localhost:300{i % 10}")
    end_time = time.time()
    
    print(f"1000 validations took {end_time - start_time:.3f} seconds")
    print(f"Average: {(end_time - start_time) * 1000:.3f}ms per validation")

test_validation_performance()
```

## Troubleshooting

### Common Issues

1. **Validation Too Strict**
   ```python
   # Increase limits if legitimate inputs are rejected
   configure_security(SecurityConfig(
       validation_config=ValidationConfig(
           max_url_length=4096,  # Increase if needed
           max_json_size=50*1024*1024,  # 50MB
       )
   ))
   ```

2. **Performance Impact**
   ```python
   # Disable strict mode for better performance
   configure_security(SecurityConfig(
       validation_config=ValidationConfig(
           enable_strict_mode=False
       )
   ))
   ```

3. **Legacy Compatibility**
   ```python
   # Temporarily disable validation if needed (not recommended)
   import spacetimedb_sdk.validation as validation
   validation.validate_url = lambda x, f=None: validation.ValidationResult(True, x)
   ```

### Debug Mode
```python
import logging
logging.getLogger('spacetimedb_sdk.validation').setLevel(logging.DEBUG)

# This will show detailed validation information
```

## Migration Guide

If you have existing code that bypasses validation:

### Before (Unsafe)
```python
# Old unsafe pattern
url = f"ws://{user_host}/database/{user_db}"
client = UnsafeWebSocketClient(url)
```

### After (Safe)
```python
# New safe pattern with automatic validation
client = SpacetimeDBClient(
    host=user_host,        # Automatically validated
    database_address=user_db  # Automatically validated  
)
```

The validation framework provides comprehensive security with minimal code changes. Most existing code will work unchanged with added security protection.