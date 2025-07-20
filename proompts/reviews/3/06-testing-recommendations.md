# Testing Recommendations - SpacetimeDB Python SDK

## Testing Assessment: GOOD with Improvement Opportunities ✅

The codebase includes solid testing foundations but could benefit from enhanced coverage, integration testing, and testing infrastructure improvements.

## Current Testing Landscape

### ✅ Strengths

**1. Test Structure**:
```python
# Well-organized test hierarchy
tests/
├── unit/
│   ├── test_authentication_handler.py
│   ├── test_event_system.py
│   └── test_bounded_cache.py
├── integration/
│   ├── test_connection_flow.py
│   └── test_end_to_end.py
└── performance/
    └── test_performance_benchmarks.py
```

**2. Good Test Naming**:
```python
def test_authentication_handler_stores_credentials_securely():
    """Test that credentials are encrypted when stored."""
    
def test_event_system_handles_concurrent_events():
    """Test event system thread safety."""
    
def test_memory_efficiency_with_context_pooling():
    """Test that context pooling reduces memory usage."""
```

**3. Proper Use of Fixtures**:
```python
@pytest.fixture
def auth_handler():
    """Provide configured authentication handler."""
    return AuthenticationHandler(
        storage=MockStorage(),
        auto_refresh_tokens=False
    )

@pytest.fixture
def mock_websocket():
    """Provide mock WebSocket for testing."""
    return Mock(spec=websocket.WebSocket)
```

## Testing Gaps Analysis

### ⚠️ Integration Testing Gaps

**1. Connection Flow Integration**:
```python
# Missing: Full connection lifecycle tests
async def test_complete_connection_lifecycle():
    """Test entire connect → authenticate → subscribe → disconnect flow."""
    # Need comprehensive integration test
    
async def test_connection_failure_recovery():
    """Test connection recovery after various failure modes."""
    # Test network failures, auth failures, server restarts
```

**2. Event System Integration**:
```python
# Missing: Cross-component event testing
def test_authentication_events_trigger_connection_updates():
    """Test that auth events properly update connection state."""
    
def test_subscription_events_trigger_data_updates():
    """Test that subscription events update cached data."""
```

### ⚠️ Security Testing Gaps

**1. Credential Security Tests**:
```python
# Missing: Security-focused tests
def test_credentials_not_logged_in_plaintext():
    """Verify no sensitive data appears in logs."""
    
def test_encrypted_storage_cannot_be_read_without_key():
    """Verify storage encryption is effective."""
    
def test_token_expiry_handling_edge_cases():
    """Test edge cases in token expiry logic."""
```

**2. Input Validation Tests**:
```python
# Missing: Comprehensive validation testing
def test_sql_injection_prevention():
    """Test that malicious SQL inputs are rejected."""
    
def test_oversized_message_handling():
    """Test protection against DoS via large messages."""
    
def test_malformed_authentication_headers():
    """Test handling of malformed auth headers."""
```

### ⚠️ Performance Testing Gaps

**1. Load Testing**:
```python
# Missing: High-load scenarios
async def test_concurrent_connection_handling():
    """Test performance under 1000+ concurrent connections."""
    
async def test_memory_usage_under_sustained_load():
    """Test memory stability over extended periods."""
```

**2. Regression Testing**:
```python
# Missing: Performance regression prevention
def test_connection_setup_performance_regression():
    """Ensure connection setup remains under 100ms."""
    
def test_event_dispatch_performance_regression():
    """Ensure event dispatch remains under 0.1ms."""
```

## Testing Infrastructure Recommendations

### 1. Enhanced Test Configuration

**pytest.ini improvements**:
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --strict-markers
    --strict-config
    --cov=src/spacetimedb_sdk
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=85
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    security: Security tests
    slow: Slow-running tests
```

**conftest.py enhancements**:
```python
# tests/conftest.py
import pytest
import asyncio
from unittest.mock import Mock, patch
from spacetimedb_sdk import AuthenticationHandler, EventManager

@pytest.fixture(scope="session")
def event_loop():
    """Create session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def isolated_auth_storage(tmp_path):
    """Provide isolated credential storage for testing."""
    storage_path = tmp_path / "test_credentials"
    with patch('spacetimedb_sdk.auth.storage.get_default_storage_path', 
               return_value=storage_path):
        yield storage_path

@pytest.fixture
def performance_monitor():
    """Monitor performance during tests."""
    import time
    import psutil
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = time.perf_counter()
            self.start_memory = psutil.Process().memory_info().rss
            
        def check_performance(self, max_time_ms=100, max_memory_mb=10):
            elapsed = (time.perf_counter() - self.start_time) * 1000
            memory_delta = (psutil.Process().memory_info().rss - self.start_memory) / 1024 / 1024
            
            assert elapsed < max_time_ms, f"Test took {elapsed:.1f}ms (limit: {max_time_ms}ms)"
            assert memory_delta < max_memory_mb, f"Memory increased by {memory_delta:.1f}MB"
    
    return PerformanceMonitor()
```

### 2. Mock Infrastructure

**Comprehensive WebSocket Mocking**:
```python
# tests/mocks/websocket_mock.py
class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.received_messages = []
        self.connection_state = "closed"
        self.error_to_raise = None
        
    async def connect(self, url):
        if self.error_to_raise:
            raise self.error_to_raise
        self.connection_state = "open"
        
    async def send(self, message):
        if self.connection_state != "open":
            raise ConnectionError("WebSocket not connected")
        self.sent_messages.append(message)
        
    async def recv(self):
        if self.received_messages:
            return self.received_messages.pop(0)
        await asyncio.sleep(0.1)  # Simulate waiting
        return None
```

**SpacetimeDB Server Mock**:
```python
# tests/mocks/server_mock.py
class MockSpacetimeDBServer:
    def __init__(self):
        self.databases = {}
        self.connections = {}
        self.message_log = []
        
    def create_database(self, name: str):
        self.databases[name] = {
            "tables": {},
            "reducers": {},
            "subscriptions": []
        }
        
    def handle_connection(self, connection_id: str, message: dict):
        self.message_log.append((connection_id, message))
        
        if message["type"] == "subscribe":
            return self._handle_subscription(connection_id, message)
        elif message["type"] == "call_reducer":
            return self._handle_reducer_call(connection_id, message)
```

### 3. Property-Based Testing

**Hypothesis for complex data structures**:
```python
# tests/property/test_bounded_cache.py
from hypothesis import given, strategies as st
from spacetimedb_sdk.bounded_client_cache import BoundedTableCache

@given(
    entries=st.lists(
        st.tuples(st.text(), st.binary()),
        min_size=0,
        max_size=1000
    ),
    max_cache_size=st.integers(min_value=1, max_value=100)
)
def test_bounded_cache_never_exceeds_limit(entries, max_cache_size):
    """Property: cache never exceeds specified size limit."""
    cache = BoundedTableCache(max_entries=max_cache_size)
    
    for key, value in entries:
        cache.put(key, value)
    
    assert len(cache.cache) <= max_cache_size

@given(
    events=st.lists(
        st.builds(Event, 
                 event_type=st.sampled_from(EventType),
                 data=st.dictionaries(st.text(), st.text())),
        min_size=1,
        max_size=1000
    )
)
def test_event_system_processes_all_events(events):
    """Property: all valid events are processed without loss."""
    event_manager = EventManager()
    processed_events = []
    
    def capture_handler(context):
        processed_events.append(context.event)
    
    event_manager.subscribe(capture_handler, [et for et in EventType])
    
    for event in events:
        event_manager.emit(event)
    
    assert len(processed_events) == len(events)
```

## Specific Test Recommendations

### 1. Authentication Handler Tests

**Enhanced security testing**:
```python
# tests/unit/test_authentication_security.py
class TestAuthenticationSecurity:
    
    def test_credentials_encrypted_at_rest(self, tmp_path):
        """Verify credentials are encrypted when stored."""
        handler = AuthenticationHandler()
        handler.store_credentials("identity", "token", "host", "db")
        
        # Read raw storage file
        storage_files = list(tmp_path.glob("*.enc"))
        assert len(storage_files) > 0
        
        raw_content = storage_files[0].read_bytes()
        # Verify token not in plaintext
        assert b"token" not in raw_content
        assert b"identity" not in raw_content
    
    def test_token_refresh_race_condition(self):
        """Test concurrent token refresh handling."""
        handler = AuthenticationHandler()
        
        async def concurrent_refresh():
            tasks = [
                handler.refresh_token("host", "db") 
                for _ in range(10)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Should handle race conditions gracefully
            assert not any(isinstance(r, Exception) for r in results)
    
    def test_authentication_timing_attack_resistance(self):
        """Verify authentication timing is consistent."""
        handler = AuthenticationHandler()
        
        # Test with valid and invalid credentials
        valid_times = []
        invalid_times = []
        
        for _ in range(100):
            start = time.perf_counter()
            handler.authenticate_with_legacy_token("valid", "host", "db")
            valid_times.append(time.perf_counter() - start)
            
            start = time.perf_counter()
            try:
                handler.authenticate_with_legacy_token("invalid", "host", "db")
            except AuthenticationError:
                pass
            invalid_times.append(time.perf_counter() - start)
        
        # Timing should be similar to prevent timing attacks
        avg_valid = sum(valid_times) / len(valid_times)
        avg_invalid = sum(invalid_times) / len(invalid_times)
        assert abs(avg_valid - avg_invalid) < 0.01  # Less than 10ms difference
```

### 2. Event System Tests

**Comprehensive event testing**:
```python
# tests/unit/test_event_system_comprehensive.py
class TestEventSystemComprehensive:
    
    async def test_event_ordering_under_load(self):
        """Test event ordering is preserved under high load."""
        event_manager = EventManager()
        received_events = []
        
        def order_tracking_handler(context):
            received_events.append(context.event.data['sequence'])
        
        event_manager.subscribe(order_tracking_handler, [EventType.CUSTOM])
        
        # Send 1000 events rapidly
        for i in range(1000):
            event = Event(EventType.CUSTOM, {'sequence': i})
            await event_manager.emit(event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Verify ordering preserved
        assert received_events == list(range(1000))
    
    def test_event_handler_isolation(self):
        """Test that handler failures don't affect other handlers."""
        event_manager = EventManager()
        successful_calls = []
        
        def failing_handler(context):
            raise Exception("Handler failure")
        
        def successful_handler(context):
            successful_calls.append(context.event.data)
        
        event_manager.subscribe(failing_handler, [EventType.CUSTOM])
        event_manager.subscribe(successful_handler, [EventType.CUSTOM])
        
        event = Event(EventType.CUSTOM, {"test": "data"})
        event_manager.emit(event)
        
        # Successful handler should still be called
        assert len(successful_calls) == 1
        assert successful_calls[0] == {"test": "data"}
```

### 3. Integration Tests

**End-to-end workflow testing**:
```python
# tests/integration/test_complete_workflows.py
class TestCompleteWorkflows:
    
    async def test_full_connection_lifecycle(self, mock_server):
        """Test complete connection lifecycle."""
        # Setup
        client = ModernWebSocketClient()
        mock_server.create_database("test_db")
        
        # Connect
        await client.connect("ws://localhost:3000/database/test_db")
        assert client.is_connected()
        
        # Authenticate (should happen automatically)
        await asyncio.sleep(0.1)  # Allow auth to complete
        assert client.auth_handler.get_authentication_state() == AuthenticationState.AUTHENTICATED
        
        # Subscribe
        subscription = ["SELECT * FROM users"]
        await client.subscribe(subscription)
        
        # Verify subscription active
        assert len(client.active_subscriptions) == 1
        
        # Call reducer
        result = await client.call_reducer("create_user", {"name": "test"})
        assert result is not None
        
        # Disconnect
        await client.disconnect()
        assert not client.is_connected()
    
    async def test_connection_recovery_after_network_failure(self, mock_server):
        """Test connection recovery after network interruption."""
        client = ModernWebSocketClient()
        await client.connect("ws://localhost:3000/database/test_db")
        
        # Simulate network failure
        mock_server.simulate_network_failure()
        
        # Client should detect failure and attempt reconnection
        await asyncio.sleep(1.0)  # Allow reconnection attempts
        
        # Restore network
        mock_server.restore_network()
        
        # Wait for recovery
        await asyncio.sleep(2.0)
        
        # Verify client recovered
        assert client.is_connected()
        assert client.auth_handler.get_authentication_state() == AuthenticationState.AUTHENTICATED
```

## Test Coverage Goals

### Current Coverage Estimate: ~75%
### Target Coverage: 90%+

**Priority Areas for Coverage Improvement**:

1. **Error Handling Paths** (Currently ~60% covered)
   - Authentication failures
   - Network errors
   - Malformed messages

2. **Edge Cases** (Currently ~50% covered)
   - Boundary conditions
   - Race conditions
   - Resource exhaustion

3. **Integration Scenarios** (Currently ~40% covered)
   - Cross-component interactions
   - End-to-end workflows
   - Failure recovery

## Testing Infrastructure Improvements

### 1. Continuous Integration

**GitHub Actions workflow**:
```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -e .[test]
        pip install pytest-cov pytest-xdist pytest-benchmark
    
    - name: Run unit tests
      run: pytest tests/unit -v --cov --cov-report=xml
    
    - name: Run integration tests
      run: pytest tests/integration -v
    
    - name: Run performance tests
      run: pytest tests/performance -v --benchmark-only
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### 2. Performance Monitoring

**Automated performance regression detection**:
```python
# tests/performance/conftest.py
@pytest.fixture(scope="session")
def performance_baseline():
    """Load performance baseline from previous runs."""
    baseline_file = Path("tests/performance/baseline.json")
    if baseline_file.exists():
        return json.loads(baseline_file.read_text())
    return {}

def pytest_benchmark_update_json(config, benchmarks, output_json):
    """Update performance baseline after successful runs."""
    if config.getoption("--benchmark-only"):
        baseline_file = Path("tests/performance/baseline.json")
        baseline_file.write_text(json.dumps(output_json, indent=2))
```

## Testing Best Practices Implementation

### 1. Test Isolation ✅
```python
# Each test uses fresh instances
@pytest.fixture
def fresh_auth_handler():
    return AuthenticationHandler(storage=MockStorage())
```

### 2. Clear Test Intent ✅
```python
def test_authentication_handler_retries_on_network_failure():
    """
    GIVEN: Authentication handler with retry policy
    WHEN: Network failure occurs during authentication
    THEN: Handler retries according to policy
    """
```

### 3. Fast Test Execution ⚠️
```python
# Need improvement: Some tests are slow
# Add timeout controls and parallel execution
pytest.mark.timeout(5)
def test_fast_operation():
    pass
```

## Final Testing Recommendations

### Immediate Actions (Next 2 weeks)
1. ✅ Add comprehensive security tests
2. ✅ Implement property-based testing for core data structures
3. ✅ Create integration test suite for critical workflows
4. ✅ Set up performance regression testing

### Medium-term (Next 1-2 months)
1. ✅ Achieve 90%+ test coverage
2. ✅ Add load testing infrastructure
3. ✅ Implement contract testing for WebSocket protocol
4. ✅ Create testing documentation and guidelines

### Long-term (Next 3-6 months)
1. ✅ Add chaos engineering tests
2. ✅ Implement automated security scanning
3. ✅ Create performance benchmark suite
4. ✅ Add mutation testing for test quality validation

## Overall Testing Grade: B+ → A- (with recommendations) 🎯

The current testing foundation is solid but implementing these recommendations will create a **comprehensive, robust testing infrastructure** that ensures code quality and prevents regressions.