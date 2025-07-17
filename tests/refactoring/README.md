# Phase 2 Refactoring Test Infrastructure

This directory contains comprehensive test infrastructure to support the Phase 2 refactoring of the SpacetimeDB Python SDK, specifically for breaking up `websocket_client.py` (1,475 lines) into focused modules.

## Overview

The Phase 2 refactoring involves:
- Extracting subscription manager functionality
- Extracting authentication handler functionality  
- Creating a unified event system
- Ensuring 100% backward compatibility
- Maintaining or improving performance

## Test Suite Structure

### Core Test Categories

#### 1. Regression Tests
- **`test_websocket_client_regression.py`** - Ensures existing WebSocket client behavior unchanged
- **`test_api_compatibility.py`** - Validates 100% API backward compatibility
- **`test_integration_regression.py`** - End-to-end integration regression tests

#### 2. Module Tests (Isolated)
- **`test_subscription_manager.py`** - Isolated subscription manager testing
- **`test_authentication_handler.py`** - Isolated authentication handler testing
- **`test_unified_event_system.py`** - Event system testing

#### 3. Integration Tests
- **`test_module_integration.py`** - Test interactions between new modules
- **`test_end_to_end_scenarios.py`** - Complete user scenarios

#### 4. Performance Tests
- **`test_performance_regression.py`** - Performance regression and monitoring tests

### Infrastructure Components

#### Mock Infrastructure
- **`mock_infrastructure.py`** - Comprehensive mock servers and test infrastructure
- **`conftest.py`** - Pytest fixtures and test configuration
- **`test_fixtures.py`** - Reusable test fixtures and data generators

## Running Tests

### Quick Start

```bash
# Install dependencies
make install

# Run all tests
make test

# Run specific test suites
make test-regression
make test-module
make test-integration
make test-performance

# Run with coverage
make test-coverage
```

### Using the Test Runner

```bash
# Run all tests
./run_tests.py --suite all

# Run regression tests only
./run_tests.py --suite regression --verbose

# Run fast tests (exclude slow tests)
./run_tests.py --suite fast

# Run with custom markers
./run_tests.py --markers "regression and not slow"

# Generate test report
./run_tests.py --suite all --report test_report.json
```

### Test Markers

Tests are categorized using pytest markers:

- `regression` - Regression tests
- `module` - Isolated module tests
- `integration` - Integration tests
- `performance` - Performance tests
- `slow` - Tests taking >1 second
- `api_compatibility` - API compatibility tests
- `mock_server` - Tests using mock server
- `end_to_end` - Complete scenario tests
- `memory` - Memory usage tests
- `concurrent` - Concurrency tests

## Test Infrastructure Components

### 1. Mock Server Infrastructure

The mock infrastructure provides realistic testing environments:

```python
from .mock_infrastructure import create_test_server, MockServerBehavior

# Create normal mock server
server = create_test_server()

# Create server with specific behavior
slow_server = create_test_server(MockServerBehavior.SLOW_RESPONSE)
unreliable_server = create_test_server(MockServerBehavior.INTERMITTENT_ERRORS)
```

### 2. Test Fixtures

Comprehensive fixtures for different scenarios:

```python
def test_example(connection_scenarios, mock_websocket_client):
    for scenario in connection_scenarios:
        # Test with different connection scenarios
        pass
```

### 3. Performance Monitoring

Built-in performance monitoring for regression detection:

```python
def test_performance(performance_tracker):
    performance_tracker.start_timing("operation")
    # ... perform operation
    duration = performance_tracker.stop_timing("operation")
    assert duration < baseline_time
```

## Key Testing Strategies

### 1. Regression Prevention

- **API Surface Testing**: Every public method and property is tested
- **Behavior Validation**: All existing behaviors are captured and validated
- **Integration Flows**: Complete end-to-end flows are tested
- **Performance Baselines**: Performance characteristics are monitored

### 2. Module Isolation

- **Interface Testing**: Module interfaces are tested in isolation
- **Mock Dependencies**: All external dependencies are mocked
- **State Management**: Module state is tested independently
- **Error Handling**: Error scenarios are tested for each module

### 3. Integration Validation

- **Module Interactions**: How modules work together is thoroughly tested
- **Event Flow**: Event propagation between modules is validated
- **State Synchronization**: Cross-module state consistency is verified
- **Error Propagation**: Error handling across module boundaries is tested

### 4. Performance Monitoring

- **Memory Usage**: Memory efficiency and leak detection
- **Processing Speed**: Message processing performance
- **Connection Performance**: Connection establishment and management
- **Concurrent Operations**: Performance under concurrent load

## Development Workflow

### Pre-Refactoring

1. **Run baseline tests**: Capture current behavior
```bash
make test-regression
```

2. **Generate coverage report**: Identify test gaps
```bash
make test-coverage
```

### During Refactoring

1. **Run module tests**: Test extracted modules in isolation
```bash
make test-module
```

2. **Run integration tests**: Ensure modules work together
```bash
make test-integration
```

3. **Performance validation**: Check for performance regressions
```bash
make test-performance
```

### Post-Refactoring

1. **Full regression suite**: Ensure nothing broke
```bash
make test
```

2. **End-to-end validation**: Test complete scenarios
```bash
make test-e2e
```

3. **Generate final report**: Document test results
```bash
make test-report
```

## Configuration

### Pytest Configuration

Test configuration is in `pytest.ini`:
- Coverage settings
- Test discovery patterns
- Marker definitions
- Output formatting

### Performance Baselines

Performance baselines are defined in test fixtures:
- Connection time: 1.0 seconds
- Authentication time: 0.5 seconds
- Subscription time: 0.1 seconds per subscription
- Message processing: 0.001 seconds per message

### Test Data

Test data generators provide realistic data sets:
- User data (small/medium/large datasets)
- Message data with realistic content
- IoT sensor data for monitoring scenarios
- Gaming data for real-time scenarios

## Continuous Integration

The test suite is designed for CI/CD integration:

```yaml
# Example CI configuration
- name: Run Phase 2 Refactoring Tests
  run: |
    cd tests/refactoring
    make setup
    make ci-test
```

## Monitoring and Reporting

### Coverage Reports

- HTML coverage reports in `coverage_html/`
- XML reports for CI integration
- Missing line identification

### Performance Reports

- Duration tracking for all operations
- Memory usage monitoring
- Benchmark comparisons
- Regression detection

### Test Reports

- JUnit XML for CI integration
- JSON reports for detailed analysis
- Custom reporting for stakeholders

## Best Practices

### Writing Tests

1. **Use descriptive names**: Test names should clearly indicate what is being tested
2. **Test one thing**: Each test should focus on a single behavior
3. **Use fixtures**: Leverage existing fixtures for common setup
4. **Mock external dependencies**: Don't rely on external services
5. **Test error conditions**: Include negative test cases

### Performance Testing

1. **Establish baselines**: Set realistic performance expectations
2. **Test under load**: Include concurrent operation tests
3. **Monitor memory**: Check for memory leaks and efficiency
4. **Measure consistently**: Use the same environment for comparisons

### Maintenance

1. **Update baselines**: Adjust baselines when legitimate improvements are made
2. **Review failures**: Investigate all test failures thoroughly
3. **Refactor tests**: Keep test code clean and maintainable
4. **Document changes**: Update documentation when test behavior changes

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure `PYTHONPATH` includes the source directory
2. **Mock server issues**: Check that mock servers are properly started/stopped
3. **Performance variations**: Run performance tests multiple times
4. **Memory tests**: Ensure garbage collection before memory measurements

### Debug Mode

Enable debug mode for detailed logging:

```bash
./run_tests.py --suite regression --verbose
```

### Selective Testing

Run specific test files or methods:

```bash
# Run specific file
make test-file FILE=test_websocket_client_regression.py

# Run specific marker
make test-marker MARKER=api_compatibility

# Run specific test method
python -m pytest test_websocket_client_regression.py::TestWebSocketClientRegression::test_connection_establishment_regression -v
```

## Contributing

When contributing to the test suite:

1. Follow the existing test patterns
2. Add appropriate markers to new tests
3. Update documentation for new features
4. Ensure tests are deterministic
5. Include both positive and negative test cases

## Future Enhancements

Planned improvements to the test infrastructure:

1. **Property-based testing**: Using hypothesis for more comprehensive testing
2. **Load testing**: Extended stress testing capabilities  
3. **Mutation testing**: Verify test quality using mutation testing
4. **Visual reports**: Enhanced reporting with charts and graphs
5. **Automated baseline updates**: Intelligent baseline adjustment

This comprehensive test infrastructure ensures that the Phase 2 refactoring can be performed with confidence, maintaining backward compatibility while improving code organization and maintainability.