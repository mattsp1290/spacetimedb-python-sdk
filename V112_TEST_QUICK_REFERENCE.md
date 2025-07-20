# SpacetimeDB v1.1.2 Test Suite - Quick Reference

## Running Tests

### 🟢 Core Tests (Always Pass)
```bash
./run_passing_tests.sh
# Runs: protocol, migration, validation tests
# 53 tests, ~4 seconds
```

### 🔵 All Mock Tests
```bash
python -m pytest tests/test_v112*.py -v -k "not real_server"
# Runs all tests except real server tests
```

### 🔴 Real Server Tests
```bash
# Start SpacetimeDB server first
SKIP_REAL_SERVER_TESTS=false python -m pytest tests/test_v112_real_server.py -v
```

### 🟡 Specific Test Categories
```bash
# Protocol tests only
python -m pytest tests/test_v112_protocol.py -v

# Migration tests only  
python -m pytest tests/test_v112_migration.py -v

# Validation tests only
python -m pytest tests/test_v112_validation.py -v

# Integration tests (needs server)
python -m pytest tests/test_v112_integration.py -v

# Performance tests (needs server)
python -m pytest tests/test_v112_performance.py -v

# Edge case tests
python -m pytest tests/test_v112_edge_cases.py -v
```

## Test Categories

### Protocol Tests (17 tests) ✅
- Text/Binary protocol configuration
- WebSocket subprotocol negotiation
- Protocol validation

### Migration Tests (15 tests) ✅
- Breaking change detection
- Migration path examples
- Error messages

### Validation Tests (22 tests) ✅
- Connection handling
- Identity validation
- Error recovery

### Integration Tests (24 tests) 🔵
- End-to-end workflows
- Multi-client scenarios
- Complex operations

### Performance Tests (18 tests) 🔵
- Throughput benchmarks
- Latency measurements
- Resource monitoring

### Edge Cases (20 tests) 🔵
- Boundary conditions
- Invalid inputs
- Stress testing

### Real Server (21 tests) 🔴
- Live environment
- Production scenarios
- Cross-version tests

## Quick Debug Commands

### Run specific test
```bash
python -m pytest tests/test_v112_protocol.py::TestProtocolConfiguration::test_default_protocol_is_text -v
```

### Run with output
```bash
python -m pytest tests/test_v112*.py -v -s
```

### Run with coverage
```bash
python -m pytest tests/test_v112*.py --cov=spacetimedb_sdk
```

### Run failed tests only
```bash
python -m pytest tests/test_v112*.py --lf
```

## Test Status Legend
- ✅ Always passes (no external dependencies)
- 🔵 Requires mock server or specific setup
- 🔴 Requires real SpacetimeDB server
- 🟡 Selective/conditional tests

## Common Issues

### Database Not Found
```
DatabaseNotFoundError: [DB_NOT_PUBLISHED]
```
**Fix**: Publish the database or use mock tests

### Connection Refused
```
ConnectionRefusedError: [Errno 61]
```
**Fix**: Start SpacetimeDB server on port 3000

### Protocol Mismatch
```
WebSocketException: Server rejected WebSocket
```
**Fix**: Check protocol configuration matches server

## Environment Variables

```bash
# Skip real server tests (default: true)
SKIP_REAL_SERVER_TESTS=false

# Custom server host
SPACETIME_HOST=localhost:3000

# Enable debug logging
SPACETIME_DEBUG=true
```

---
**Total Tests**: 121 | **Core Passing**: 53 | **Full Suite**: Requires server
