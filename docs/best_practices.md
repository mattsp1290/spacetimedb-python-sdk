# SpacetimeDB Python SDK - Best Practices Guide

This guide outlines best practices for using the SpacetimeDB Python SDK effectively and securely in production environments.

## Table of Contents

1. [Security Best Practices](#security-best-practices)
2. [Performance Optimization](#performance-optimization)
3. [Error Handling](#error-handling)
4. [Thread Safety](#thread-safety)
5. [Memory Management](#memory-management)
6. [Testing Strategies](#testing-strategies)
7. [Deployment Considerations](#deployment-considerations)
8. [Monitoring and Observability](#monitoring-and-observability)

## Security Best Practices

### Credential Management

**✅ DO:**
- Use encrypted credential storage for sensitive data
- Implement credential rotation policies
- Use environment variables for configuration
- Enable audit logging for security events

```python
from spacetimedb_sdk.auth import SecureAuthStorage

# Initialize secure storage
auth_storage = SecureAuthStorage()
auth_storage.initialize(master_password)

# Store credentials securely
auth_storage.store_credential(
    'spacetimedb_token',
    {'token': token, 'expires_at': expiry},
    expires_at=expiry
)
```

**❌ DON'T:**
- Store credentials in plaintext
- Hard-code secrets in source code
- Log sensitive information
- Use weak passwords or tokens

### Input Validation

**✅ DO:**
- Validate all user inputs
- Sanitize data before processing
- Use parameterized queries
- Implement rate limiting

```python
from spacetimedb_sdk.validation import InputSanitizer

sanitizer = InputSanitizer(ValidationLevel.STRICT)

# Validate user input
result = sanitizer.sanitize_string(user_input, max_length=100)
if result.is_valid:
    processed_data = result.sanitized_data
else:
    handle_validation_errors(result.errors)
```

**❌ DON'T:**
- Trust user input without validation
- Construct queries with string concatenation
- Skip input sanitization
- Ignore validation errors

### Authentication

**✅ DO:**
- Use strong authentication mechanisms
- Implement JWT token validation
- Enable token refresh workflows
- Use secure session management

```python
from spacetimedb_sdk.auth import AuthenticationProvider

auth_provider = AuthenticationProvider()
auth_provider.configure_jwt_validation(
    issuer='your-issuer',
    audience='your-audience',
    algorithm='RS256'
)

# Validate token
if auth_provider.validate_token(token):
    # Proceed with authenticated request
    pass
```

**❌ DON'T:**
- Use weak authentication schemes
- Skip token validation
- Store tokens insecurely
- Use predictable session IDs

## Performance Optimization

### Connection Management

**✅ DO:**
- Use connection pooling for high-throughput applications
- Configure pool sizes based on workload
- Implement connection health checks
- Use connection reuse strategies

```python
from spacetimedb_sdk import ConnectionPool

# Configure connection pool
pool = ConnectionPool(
    database_url,
    min_size=5,
    max_size=20,
    idle_timeout=300,
    max_lifetime=3600
)

# Use pool for connections
async with pool.acquire() as conn:
    result = await conn.execute(query)
```

**❌ DON'T:**
- Create new connections for each request
- Use excessive pool sizes
- Ignore connection timeouts
- Skip connection validation

### Query Optimization

**✅ DO:**
- Use prepared statements
- Implement query result caching
- Optimize query patterns
- Use batch operations when possible

```python
from spacetimedb_sdk.bounded_cache import BoundedCache

# Use bounded cache for query results
query_cache = BoundedCache(max_size=1000)

async def cached_query(query_key, query_func):
    if query_key in query_cache:
        return query_cache.get(query_key)
    
    result = await query_func()
    query_cache.put(query_key, result)
    return result
```

**❌ DON'T:**
- Use unbounded caches
- Ignore query performance
- Skip result caching
- Use inefficient query patterns

### Memory Management

**✅ DO:**
- Use bounded collections
- Implement proper cleanup
- Monitor memory usage
- Use memory-efficient data structures

```python
from spacetimedb_sdk.bounded_client_cache import BoundedClientCache

# Use bounded cache to prevent memory leaks
client_cache = BoundedClientCache(
    max_size=10000,
    ttl=3600  # 1 hour TTL
)
```

**❌ DON'T:**
- Use unbounded data structures
- Ignore memory leaks
- Skip resource cleanup
- Hold references indefinitely

## Error Handling

### Exception Handling

**✅ DO:**
- Use specific exception types
- Implement retry logic with backoff
- Log errors with context
- Provide meaningful error messages

```python
from spacetimedb_sdk.retry_policies import ExponentialBackoffRetry
from spacetimedb_sdk.exceptions import ConnectionError, ValidationError

retry_policy = ExponentialBackoffRetry(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0
)

async def robust_operation():
    try:
        return await operation_with_retry(
            operation,
            retry_policy=retry_policy
        )
    except ConnectionError as e:
        logger.error(f"Connection failed: {e}", extra={'operation': 'database_query'})
        raise
    except ValidationError as e:
        logger.warning(f"Validation failed: {e}", extra={'input': sanitized_input})
        raise
```

**❌ DON'T:**
- Catch all exceptions with broad handlers
- Ignore errors silently
- Skip error logging
- Expose internal error details to users

### Circuit Breaker Pattern

**✅ DO:**
- Implement circuit breakers for external services
- Configure appropriate failure thresholds
- Use fallback mechanisms
- Monitor circuit breaker state

```python
from spacetimedb_sdk.circuit_breaker import CircuitBreaker

circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=ConnectionError
)

@circuit_breaker
async def external_service_call():
    return await external_service.call()
```

## Thread Safety

### Concurrent Operations

**✅ DO:**
- Use thread-safe data structures
- Implement proper locking mechanisms
- Use async/await patterns correctly
- Avoid shared mutable state

```python
import asyncio
from spacetimedb_sdk.thread_safe import ThreadSafeConnectionPool

# Use thread-safe connection pool
pool = ThreadSafeConnectionPool(database_url)

async def concurrent_operations():
    tasks = []
    for i in range(10):
        task = asyncio.create_task(
            perform_operation(pool, i)
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return results
```

**❌ DON'T:**
- Share mutable state between threads
- Use non-thread-safe collections
- Ignore race conditions
- Mix sync and async code improperly

### Async Best Practices

**✅ DO:**
- Use async/await consistently
- Implement proper cancellation
- Use asyncio.gather for concurrent operations
- Handle async exceptions properly

```python
async def main():
    try:
        # Proper async/await usage
        async with SpacetimeDBClient(url) as client:
            tasks = [
                client.query(query1),
                client.query(query2),
                client.query(query3)
            ]
            results = await asyncio.gather(*tasks)
            return results
    except asyncio.CancelledError:
        logger.info("Operation cancelled")
        raise
```

## Memory Management

### Resource Cleanup

**✅ DO:**
- Use context managers for resource management
- Implement proper cleanup in finally blocks
- Use weak references to prevent cycles
- Monitor memory usage

```python
from contextlib import asynccontextmanager
from spacetimedb_sdk import SpacetimeDBClient

@asynccontextmanager
async def get_client():
    client = SpacetimeDBClient(database_url)
    try:
        await client.connect()
        yield client
    finally:
        await client.close()

# Usage
async with get_client() as client:
    result = await client.query(query)
```

**❌ DON'T:**
- Forget to close connections
- Create circular references
- Ignore resource leaks
- Skip cleanup in error paths

### Caching Strategies

**✅ DO:**
- Use bounded caches with TTL
- Implement cache eviction policies
- Monitor cache hit rates
- Use appropriate cache keys

```python
from spacetimedb_sdk.bounded_cache import BoundedCache
import time

class TTLCache(BoundedCache):
    def __init__(self, max_size, ttl):
        super().__init__(max_size)
        self.ttl = ttl
    
    def get(self, key):
        item = super().get(key)
        if item and time.time() - item.timestamp > self.ttl:
            self.remove(key)
            return None
        return item.value if item else None
```

## Testing Strategies

### Unit Testing

**✅ DO:**
- Write comprehensive unit tests
- Use mocking for external dependencies
- Test error conditions
- Maintain high test coverage

```python
import pytest
from unittest.mock import Mock, patch
from spacetimedb_sdk import SpacetimeDBClient

@pytest.fixture
async def mock_client():
    client = Mock(spec=SpacetimeDBClient)
    client.query = Mock(return_value={'status': 'success'})
    return client

async def test_query_success(mock_client):
    result = await mock_client.query("SELECT * FROM users")
    assert result['status'] == 'success'
    mock_client.query.assert_called_once_with("SELECT * FROM users")
```

**❌ DON'T:**
- Skip testing error paths
- Write tests that depend on external services
- Ignore test maintenance
- Use real credentials in tests

### Integration Testing

**✅ DO:**
- Test complete workflows
- Use test databases
- Implement proper test isolation
- Test performance characteristics

```python
import pytest
from spacetimedb_sdk.testing import TestDatabase

@pytest.fixture
async def test_db():
    db = TestDatabase()
    await db.setup()
    yield db
    await db.teardown()

async def test_user_workflow(test_db):
    client = SpacetimeDBClient(test_db.url)
    
    # Test complete user workflow
    user_id = await client.create_user({'name': 'Test User'})
    user = await client.get_user(user_id)
    assert user['name'] == 'Test User'
    
    await client.update_user(user_id, {'name': 'Updated User'})
    updated_user = await client.get_user(user_id)
    assert updated_user['name'] == 'Updated User'
```

## Deployment Considerations

### Configuration Management

**✅ DO:**
- Use environment variables for configuration
- Implement configuration validation
- Use different configs for different environments
- Document configuration options

```python
import os
from dataclasses import dataclass

@dataclass
class Config:
    database_url: str
    pool_size: int = 10
    timeout: float = 30.0
    debug: bool = False
    
    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.getenv('DATABASE_URL', 'ws://localhost:3000'),
            pool_size=int(os.getenv('POOL_SIZE', '10')),
            timeout=float(os.getenv('TIMEOUT', '30.0')),
            debug=os.getenv('DEBUG', 'false').lower() == 'true'
        )
```

**❌ DON'T:**
- Hard-code configuration values
- Use production config in development
- Skip configuration validation
- Ignore environment-specific settings

### Health Checks

**✅ DO:**
- Implement health check endpoints
- Monitor connection health
- Use readiness and liveness probes
- Include dependency health checks

```python
from spacetimedb_sdk.health import HealthChecker

class ApplicationHealthChecker(HealthChecker):
    def __init__(self, client):
        self.client = client
    
    async def check_health(self):
        try:
            # Check database connectivity
            await self.client.ping()
            return {'status': 'healthy', 'database': 'connected'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
```

## Monitoring and Observability

### Logging

**✅ DO:**
- Use structured logging
- Include request IDs for tracing
- Log at appropriate levels
- Avoid logging sensitive information

```python
import logging
import structlog

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

async def process_request(request_id, user_id, operation):
    logger.info(
        "Processing request",
        request_id=request_id,
        user_id=user_id,
        operation=operation
    )
    
    try:
        result = await perform_operation(operation)
        logger.info(
            "Request completed",
            request_id=request_id,
            duration=result.duration,
            status="success"
        )
        return result
    except Exception as e:
        logger.error(
            "Request failed",
            request_id=request_id,
            error=str(e),
            status="error"
        )
        raise
```

**❌ DON'T:**
- Log sensitive information
- Use print statements for logging
- Skip structured logging
- Ignore log levels

### Metrics

**✅ DO:**
- Collect performance metrics
- Monitor error rates
- Track business metrics
- Use appropriate metric types

```python
from spacetimedb_sdk.metrics import MetricsCollector

metrics = MetricsCollector()

async def monitored_operation():
    with metrics.timer('operation_duration'):
        try:
            result = await perform_operation()
            metrics.increment('operation_success')
            return result
        except Exception as e:
            metrics.increment('operation_error')
            raise
```

### Alerting

**✅ DO:**
- Set up appropriate alerts
- Define SLAs and SLOs
- Use escalation policies
- Test alerting systems

```python
from spacetimedb_sdk.alerting import AlertManager

alert_manager = AlertManager()

class DatabaseMonitor:
    def __init__(self):
        self.error_threshold = 0.05  # 5% error rate
        self.response_time_threshold = 1.0  # 1 second
    
    async def check_metrics(self):
        metrics = await self.get_current_metrics()
        
        if metrics.error_rate > self.error_threshold:
            await alert_manager.send_alert(
                'high_error_rate',
                f'Error rate: {metrics.error_rate:.2%}',
                severity='high'
            )
        
        if metrics.avg_response_time > self.response_time_threshold:
            await alert_manager.send_alert(
                'slow_response',
                f'Response time: {metrics.avg_response_time:.2f}s',
                severity='medium'
            )
```

## Summary

Following these best practices will help you build robust, secure, and performant applications with the SpacetimeDB Python SDK:

1. **Security**: Always validate input, use encrypted storage, and implement proper authentication
2. **Performance**: Use connection pooling, caching, and efficient query patterns
3. **Reliability**: Implement proper error handling, retries, and circuit breakers
4. **Maintainability**: Use good testing practices, structured logging, and monitoring
5. **Scalability**: Design for concurrency, use appropriate data structures, and manage resources properly

Remember to regularly review and update your implementation based on changing requirements and new SDK features.