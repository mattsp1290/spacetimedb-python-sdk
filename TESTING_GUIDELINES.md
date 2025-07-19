# SpacetimeDB Python SDK Testing Guidelines

## Overview

This document provides guidelines and best practices for writing unit tests in the SpacetimeDB Python SDK that are isolated, fast, and don't require external dependencies like live servers.

## Key Principles

### 1. Test Isolation
- **No External Dependencies**: Tests should not require live SpacetimeDB servers, real WebSocket connections, or actual HTTP endpoints
- **Deterministic**: Tests should produce the same results every time
- **Fast Execution**: Tests should complete quickly (under 1 second each)

### 2. Proper Mocking Strategies

#### HTTP Client Mocking
For tests involving the JSON API client:

```python
import unittest
from unittest.mock import Mock, patch, AsyncMock

# For sync requests using the requests library
@patch('spacetimedb_sdk.json_api.HAS_HTTPX', False)  # Force requests usage
@patch('spacetimedb_sdk.json_api.requests.Session')
def test_sync_operation(self, mock_session_class):
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    mock_response.headers = {}
    mock_response.text = ''
    
    # Mock session
    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session.verify = True
    mock_session_class.return_value = mock_session
    
    # Test your functionality
    api = SpacetimeDBJsonAPI(base_url="http://test", use_async=False)
    api._session = None  # Force session creation
    response = api.some_operation()
    
    # Verify
    mock_session_class.assert_called_once()
    self.assertTrue(response.success)
```

#### Async HTTP Client Mocking
For async operations, mock at the method level rather than the HTTP client level:

```python
async def test_async_operation(self):
    # Mock the internal async request method
    mock_response = ApiResponse(
        success=True,
        data={"result": "success"},
        status_code=200
    )
    
    with patch.object(self.api, '_async_request', new_callable=AsyncMock) as mock_async_request:
        mock_async_request.return_value = mock_response
        
        response = await self.api.some_async_operation()
        
        mock_async_request.assert_called_once()
        self.assertTrue(response.success)
```

#### WebSocket Client Mocking
For tests involving the main SpacetimeDBClient:

```python
def setUp(self):
    with patch('spacetimedb_sdk.spacetimedb_client.WebSocketClient') as mock_ws_class:
        self.mock_ws = Mock()
        self.mock_ws.is_connected = False
        self.mock_ws._host = 'localhost:3000'
        self.mock_ws._ssl = False
        mock_ws_class.return_value = self.mock_ws
        
        self.client = SpacetimeDBClient(start_message_processing=False)
        self.client.ws_client = self.mock_ws
```

### 3. Error Handling Tests

Test various failure scenarios without actual network failures:

```python
@patch('spacetimedb_sdk.json_api.HAS_HTTPX', False)
@patch('spacetimedb_sdk.json_api.requests.Session')
def test_connection_timeout(self, mock_session_class):
    import requests
    
    # Mock timeout exception
    mock_session = Mock()
    mock_session.request.side_effect = requests.Timeout("Connection timeout")
    mock_session.verify = True
    mock_session_class.return_value = mock_session
    
    # Set low retry for faster testing
    api = SpacetimeDBJsonAPI(base_url="http://test", max_retries=1, retry_delay=0.01)
    api.use_async = False
    api._session = None
    
    response = api.some_operation()
    
    self.assertFalse(response.success)
    self.assertIn("timeout", response.error.lower())
```

### 4. Testing Patterns to Avoid

#### ❌ Don't Do This
```python
def test_real_connection():
    # BAD: Tries to connect to actual server
    client = SpacetimeDBClient.builder().with_uri("ws://localhost:3000").build()
    client.connect()  # This will fail if no server is running
```

#### ✅ Do This Instead
```python
@patch('spacetimedb_sdk.spacetimedb_client.WebSocketClient')
def test_connection_setup(self, mock_ws_class):
    # GOOD: Mocks the WebSocket connection
    mock_ws = Mock()
    mock_ws.is_connected = True
    mock_ws_class.return_value = mock_ws
    
    client = SpacetimeDBClient.builder().with_uri("ws://localhost:3000").build()
    # Test configuration and setup, not actual connection
```

### 5. Common Mock Patterns

#### API Response Mocking
```python
# For successful responses
mock_response = ApiResponse(
    success=True,
    data={"expected": "data"},
    status_code=200,
    headers={"Content-Type": "application/json"}
)

# For error responses
mock_error_response = ApiResponse(
    success=False,
    error="Simulated error",
    status_code=500
)
```

#### WebSocket Message Mocking
```python
def test_message_handling(self):
    mock_message = {
        "type": "TransactionUpdate",
        "data": {"table_name": "users", "updates": [...]}
    }
    
    # Test message processing without actual WebSocket
    self.client._handle_message(mock_message)
```

### 6. Integration Test Markers

For tests that require actual servers, use pytest markers:

```python
import pytest

@pytest.mark.integration
@pytest.mark.requires_server
def test_real_server_integration():
    # This test will be skipped in normal test runs
    pass
```

Run only unit tests:
```bash
pytest -m "not integration"
```

### 7. Test Structure Best Practices

#### Organize Tests by Component
```
tests/
├── unit/
│   ├── test_json_api.py           # HTTP API tests
│   ├── test_websocket_client.py   # WebSocket client tests
│   ├── test_protocol.py           # Protocol message tests
│   └── test_auth.py               # Authentication tests
├── integration/
│   ├── test_e2e_scenarios.py      # End-to-end tests
│   └── test_server_integration.py # Real server tests
└── fixtures/
    ├── mock_responses.py          # Shared mock data
    └── test_helpers.py            # Test utilities
```

#### Use Descriptive Test Names
```python
def test_json_api_handles_server_timeout_gracefully(self):
    """Test that JSON API properly handles and retries on server timeouts."""
    
def test_websocket_client_reconnects_after_connection_loss(self):
    """Test automatic reconnection when WebSocket connection is lost."""
```

### 8. Performance Considerations

- Keep test execution under 1 second per test
- Use small retry counts and delays in tests (e.g., `max_retries=1, retry_delay=0.01`)
- Mock at the appropriate level - don't over-mock or under-mock
- Batch related test cases in the same test class

### 9. Example Fixed Test File

See `test_json_api.py` as an example of properly mocked tests that:
- ✅ Run without external dependencies
- ✅ Execute quickly (all 19 tests in under 1 second)
- ✅ Test both success and failure scenarios
- ✅ Provide good code coverage
- ✅ Are deterministic and reliable

## Summary

The goal is to create a test suite that:
1. **Runs anywhere** - no server dependencies
2. **Runs fast** - complete test suite in seconds, not minutes
3. **Runs reliably** - no flaky tests due to network issues
4. **Tests behavior** - focuses on code logic, not network infrastructure
5. **Provides confidence** - catches regressions and validates functionality

By following these guidelines, we ensure that the test suite remains maintainable, fast, and reliable for all developers working on the SpacetimeDB Python SDK.