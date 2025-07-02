# SpacetimeDB Python SDK Integration Test Suite

Comprehensive test suite validating the integration between `spacetimedb-python-sdk` and `blackholio-python-client` to ensure seamless compatibility and robust operation.

## Overview

This test suite addresses the integration requirements outlined in `SPACETIMEDB_SDK_REMAINING_FIXES.md` and provides comprehensive validation of:

1. **Message Format Compatibility** - Ensures SDK accepts client message formats
2. **Protocol Helper Integration** - Validates SDK-client protocol coordination  
3. **Subscription State Coordination** - Tests subscription callback mechanisms
4. **Large Message Handling** - Validates chunked message processing with progress tracking
5. **Subscription Health Monitoring** - Tests metrics and health status tracking
6. **Connection Recovery** - Validates error recovery and circuit breaker functionality
7. **Performance Characteristics** - Benchmarks throughput and resource usage
8. **Error Handling** - Tests resilience under adverse conditions

## Test Files

### Core Integration Tests

#### `test_sdk_client_integration.py`
Primary integration test suite covering:

- **Message Format Compatibility Tests**
  - Direct variant format validation (`{"CallReducer": {...}}`)
  - Legacy format support with warnings (`{"type": "CallReducer", ...}`)
  - Invalid custom message type rejection
  - Unicode and special character handling

- **Frame Type Selection Tests**
  - Protocol-to-frame-type mapping consistency
  - Binary vs text frame selection for different protocols
  - SDK-client frame type agreement

- **Protocol Helper Integration Tests**
  - Protocol helper access and exposure
  - Client encoding bypass functionality
  - Encoder/decoder component sharing

- **Subscription State Coordination Tests**
  - Callback registration and notification
  - Subscription update event tracking
  - Error event handling

- **Large Message Integration Tests**
  - Progress callback functionality
  - Chunking threshold validation
  - Small message passthrough

- **Subscription Health Monitoring Tests**
  - Metrics recording and calculation
  - Health status determination
  - Error rate tracking and staleness detection

- **End-to-End Integration Tests**
  - Complete message flow validation
  - Subscription lifecycle testing

#### `test_performance_benchmarks.py`
Performance validation and benchmarking:

- **Message Validation Performance**
  - Throughput testing (target: >10,000 msg/sec)
  - Concurrent validation across multiple threads
  - Complex message structure handling

- **Subscription Metrics Performance**
  - High-frequency data recording (50,000+ updates)
  - Health calculation efficiency
  - Memory usage optimization

- **Large Message Performance**
  - Chunking performance for 5MB+ messages
  - Reassembly speed optimization
  - Throughput benchmarks

- **Concurrent Client Simulation**
  - Multiple client handling
  - Resource usage under load
  - Memory leak detection

#### `test_error_scenarios.py`
Error handling and edge case validation:

- **Message Validation Errors**
  - Malformed message structure handling
  - Invalid custom message rejection
  - Unicode and encoding edge cases

- **Large Message Error Scenarios**
  - Chunk corruption handling
  - Missing chunk header recovery
  - Timeout and cleanup mechanisms
  - Out-of-order chunk processing

- **Connection Recovery Errors**
  - Retry exhaustion behavior
  - Non-recoverable error identification
  - Circuit breaker timeout handling

- **Subscription Metrics Errors**
  - Invalid table name handling
  - Concurrent access safety
  - Edge case data validation

- **WebSocket Client Errors**
  - Disconnected state message sending
  - Callback error isolation
  - Protocol mismatch detection

## Running the Tests

### Quick Start

```bash
# Run all integration tests
python run_integration_tests.py

# Run with verbose output
python run_integration_tests.py --verbose

# Run fast tests only (skip slow performance tests)
python run_integration_tests.py --fast

# Run specific test pattern
python run_integration_tests.py --test "test_message_validation"

# List available test files
python run_integration_tests.py --list
```

### Individual Test Suites

```bash
# Run core integration tests
python -m pytest tests/test_sdk_client_integration.py -v

# Run performance benchmarks
python -m pytest tests/test_performance_benchmarks.py -v -s

# Run error scenario tests  
python -m pytest tests/test_error_scenarios.py -v

# Run specific test class
python -m pytest tests/test_sdk_client_integration.py::TestMessageFormatCompatibility -v

# Run specific test method
python -m pytest tests/test_sdk_client_integration.py::TestMessageFormatCompatibility::test_direct_variant_format_validation -v
```

### Advanced Usage

```bash
# Run with coverage reporting
python -m pytest tests/ --cov=spacetimedb_sdk --cov-report=html

# Run with profiling
python -m pytest tests/ --profile

# Run parallel tests
python -m pytest tests/ -n auto

# Run with specific markers
python -m pytest tests/ -m "not slow"
```

## Test Configuration

### Environment Setup

Ensure the following dependencies are installed:

```bash
# Required packages
pip install pytest pytest-asyncio pytest-mock

# Optional performance packages  
pip install pytest-benchmark pytest-cov pytest-xdist
```

### Configuration Files

- `pytest.ini` - Test discovery and execution configuration
- `run_integration_tests.py` - Custom test runner with reporting

## Expected Results

### Success Criteria

All tests should pass with the following benchmarks:

- **Message Validation**: >10,000 messages/second throughput
- **Subscription Metrics**: Handle 50,000+ high-frequency updates  
- **Large Message Handling**: Process 5MB+ messages efficiently
- **Error Recovery**: Graceful handling of all error scenarios
- **Memory Usage**: No memory leaks under load

### Performance Targets

| Metric | Target | Test Coverage |
|--------|--------|---------------|
| Message validation throughput | >10,000 msg/sec | test_validation_throughput |
| Concurrent validation | 4 threads, <3s for 10k msg | test_concurrent_validation |
| Metrics recording | >10,000 updates/sec | test_high_frequency_data_recording |
| Health calculation | >50,000 calc/sec | test_health_calculation_performance |  
| Large message chunking | >1 MB/sec | test_chunking_performance |
| Message reassembly | <100ms for 1MB | test_reassembly_performance |

## Integration Verification Checklist

Use this checklist to verify integration completeness:

- [ ] **Message Format Compatibility**
  - [ ] SDK accepts direct variant format without 'type' field
  - [ ] Legacy format with 'type' field works with warnings
  - [ ] Invalid custom message types properly rejected

- [ ] **Protocol Consistency**  
  - [ ] Frame types match between SDK and client for all protocols
  - [ ] Binary protocols use BINARY frames, JSON protocols use TEXT frames
  - [ ] Protocol helper provides access to encoding/decoding components

- [ ] **Subscription Coordination**
  - [ ] Subscription state callbacks notify client of updates
  - [ ] Error events properly propagated to client callbacks
  - [ ] Multiple callbacks supported without interference

- [ ] **Large Message Support**
  - [ ] Messages >60KB properly chunked and reassembled
  - [ ] Progress callbacks provide real-time status updates
  - [ ] Small messages pass through without chunking overhead

- [ ] **Health Monitoring**
  - [ ] Subscription metrics automatically recorded for all message types
  - [ ] Health status reflects data freshness and error rates
  - [ ] All subscription health accessible via public API

- [ ] **Error Resilience**
  - [ ] Connection recovery handles protocol errors automatically
  - [ ] Circuit breaker prevents excessive retry attempts
  - [ ] Malformed messages don't crash processing

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure src directory is in Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
   ```

2. **Timeout Issues**
   ```bash
   # Increase test timeout for slow systems
   python -m pytest tests/ --timeout=600
   ```

3. **Performance Test Failures**
   ```bash
   # Run performance tests with relaxed thresholds
   python -m pytest tests/test_performance_benchmarks.py -s --tb=short
   ```

### Debug Mode

```bash
# Enable debug logging
python -m pytest tests/ -s -v --log-cli-level=DEBUG

# Run single test with full output
python -m pytest tests/test_sdk_client_integration.py::TestMessageFormatCompatibility::test_direct_variant_format_validation -s -vv
```

## Contributing

When adding new integration requirements:

1. Add test cases to appropriate test file
2. Update performance benchmarks if needed
3. Add error scenarios for new functionality
4. Update this README with new test coverage
5. Ensure all tests pass before committing

## Integration Status

✅ **Message Format Compatibility** - Complete  
✅ **Protocol Helper Integration** - Complete  
✅ **Subscription State Coordination** - Complete  
✅ **Large Message Progress Callbacks** - Complete  
✅ **Subscription Health Monitoring** - Complete  
✅ **Comprehensive Test Suite** - Complete  

The SpacetimeDB Python SDK is now fully compatible with blackholio-python-client and ready for production use.