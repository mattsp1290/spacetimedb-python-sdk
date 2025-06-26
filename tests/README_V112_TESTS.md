# SpaceTimeDB Python SDK v1.1.2 Test Suite Documentation

## Overview

This document describes the comprehensive test suite for SpaceTimeDB Python SDK v1.1.2 compatibility. The test suite validates all aspects of the v1.1.2 protocol implementation, ensuring robust error handling, performance, and reliability.

## Test Organization

### 1. **Mock Server Framework** (`mock_spacetimedb_server.py`)
A fully-featured mock SpaceTimeDB server that simulates v1.1.2 protocol behavior.

**Features:**
- WebSocket endpoint simulation (`/v1/database/{name}/subscribe`)
- Protocol support (JSON and BSATN)
- Authentication simulation
- Error injection capabilities
- Configurable scenarios (slow connections, auth required, etc.)
- Statistics tracking

**Usage:**
```python
from mock_spacetimedb_server import create_test_server

# Create and start a mock server
server = create_test_server("normal", port=3001)
server.start()

# Use in tests...

server.stop()
```

### 2. **Error Handling Tests** (`test_v112_error_handling.py`)
Validates the enhanced error handling implemented in Task 3.

**Test Coverage:**
- ✅ DatabaseNotFoundError detection
- ✅ Connection diagnostics
- ✅ Retry configuration
- ✅ Server availability checks
- ✅ Preflight checks
- ✅ Error message clarity

**Key Tests:**
- `test_database_not_found()` - Validates 404 error handling
- `test_connection_diagnostics()` - Tests diagnostic utilities
- `test_retry_configuration()` - Verifies retry logic setup

### 3. **Authentication Tests** (`test_v112_authentication.py`)
Comprehensive authentication flow testing from Task 4.

**Test Coverage:**
- ✅ Basic auth header construction
- ✅ Token format validation
- ✅ Identity token parsing
- ✅ Anonymous authentication
- ✅ Token persistence
- ✅ Connection state tracking

**Key Tests:**
- `TestAuthHeaderConstruction` - Validates auth header format
- `TestMockAuthentication` - Tests auth flows with mocks
- `TestTokenPersistence` - Validates token reuse

### 4. **Integration Tests** (`test_v112_integration.py`)
End-to-end workflow testing with mock server.

**Test Scenarios:**
- ✅ Published database connections
- ✅ Unpublished database handling
- ✅ Authentication workflows
- ✅ Network failure recovery
- ✅ Error injection resilience
- ✅ Concurrent connections

**Key Test Classes:**
- `TestPublishedDatabaseIntegration` - Normal operation flows
- `TestUnpublishedDatabaseScenarios` - 404 error cases
- `TestAuthenticationScenarios` - Auth success/failure
- `TestNetworkFailureScenarios` - Timeout and recovery

### 5. **Performance Benchmarks** (`test_v112_performance.py`)
Measures SDK performance characteristics.

**Benchmarks:**
- ✅ Connection establishment time
- ✅ Message throughput
- ✅ Memory usage profiling
- ✅ Concurrent operation stress tests
- ✅ Compression overhead

**Performance Targets:**
- Connection establishment: < 100ms
- Message throughput: > 1000 msg/sec
- Memory per connection: < 5MB
- Concurrent connections: > 50

### 6. **Edge Case Tests** (`test_v112_edge_cases.py`)
Tests unusual and extreme scenarios.

**Test Coverage:**
- ✅ Malformed server responses
- ✅ Unicode handling
- ✅ Extreme value lengths
- ✅ Rapid connect/disconnect cycles
- ✅ Resource exhaustion
- ✅ Thread safety
- ✅ Boundary conditions

**Key Scenarios:**
- 1MB+ message handling
- 1000+ character database names
- Concurrent operations on single client
- Memory pressure simulation

## Running the Tests

### Individual Test Suites

```bash
# Run error handling tests
python tests/test_v112_error_handling.py

# Run authentication tests
python tests/test_v112_authentication.py

# Run integration tests
python tests/test_v112_integration.py

# Run performance benchmarks
python tests/test_v112_performance.py

# Run edge case tests
python tests/test_v112_edge_cases.py
```

### Run All v1.1.2 Tests

```bash
# Use the comprehensive test runner
python tests/run_v112_tests.py
```

### With Coverage

```bash
# Generate coverage report
pytest tests/test_v112_*.py --cov=spacetimedb_sdk --cov-report=html
```

## Test Configuration

### Environment Variables

- `SKIP_INTEGRATION_TESTS` - Set to `false` to run tests requiring real server
- `MOCK_SERVER_PORT` - Override default mock server port (3001)
- `TEST_TIMEOUT` - Override default test timeout (30s)

### Mock Server Scenarios

The mock server supports predefined scenarios:

| Scenario | Description |
|----------|-------------|
| `normal` | Standard operation |
| `auth_required` | Requires authentication |
| `unpublished` | Simulates unpublished database |
| `slow_connection` | 2s connection delay |
| `slow_messages` | 0.5s message delay |
| `error_prone` | 30% error injection rate |
| `binary_only` | Only BSATN protocol |

## Debugging Tests

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Mock Server Statistics

The mock server tracks statistics accessible via:

```python
print(server.stats)
# Output: {'connections_accepted': 5, 'messages_sent': 100, ...}
```

### Connection Diagnostics

Use the built-in diagnostics for troubleshooting:

```python
from spacetimedb_sdk.connection_diagnostics import diagnose_connection

results = diagnose_connection("localhost:3000", "test_db", verbose=True)
```

## Test Maintenance

### Adding New Tests

1. Create test file following naming convention: `test_v112_<feature>.py`
2. Import required modules and mock server
3. Use appropriate test base class
4. Document test purpose and expected behavior

### Updating Mock Server

The mock server can be extended with new behaviors:

```python
# Add custom database
custom_db = MockDatabase("custom")
custom_db.add_table("data", initial_rows)
server.add_database("custom", custom_db)

# Add custom reducer
def custom_reducer(identity, **kwargs):
    return {"result": "custom"}
    
custom_db.add_reducer("custom_action", custom_reducer)
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: v1.1.2 Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: python tests/run_v112_tests.py
      - uses: actions/upload-artifact@v2
        if: failure()
        with:
          name: test-results
          path: test_results/
```

## Success Criteria

All v1.1.2 tests must pass with:

- ✅ 100% of error handling paths tested
- ✅ All authentication scenarios validated
- ✅ Performance within acceptable bounds
- ✅ Edge cases handled gracefully
- ✅ No memory leaks detected
- ✅ Thread-safe operations verified

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Mock server uses ports 3001-3040
   - Check for conflicting services
   - Override with different port range

2. **Test Timeouts**
   - Increase timeout with environment variable
   - Check for deadlocks in concurrent tests
   - Verify mock server is responding

3. **Import Errors**
   - Ensure src directory is in Python path
   - Check for circular imports
   - Verify all dependencies installed

### Getting Help

- Check test output for detailed error messages
- Enable debug logging for more context
- Review mock server logs for connection issues
- Consult specific test documentation

---

**Last Updated:** May 30, 2025  
**Version:** 1.0.0  
**Maintainer:** SpaceTimeDB SDK Team
