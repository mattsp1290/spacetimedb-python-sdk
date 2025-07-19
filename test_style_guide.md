# SpacetimeDB Python SDK Test Style Guide

## Test Pattern Standards

### 1. Import Patterns

**Standard Import Template:**
```python
#!/usr/bin/env python3
"""
Brief description of test purpose
"""

# Standard library imports
import sys
import os
import asyncio
import json
from typing import Dict, Any, List, Optional

# Third-party imports
import pytest
import pytest_asyncio

# Add src to path for testing (only in root-level test files)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# SpacetimeDB SDK imports
from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
# ... other specific imports
```

**Rules:**
- Use single `sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))` at top
- No duplicate `sys.path` manipulations
- Group imports: stdlib, third-party, local
- Use specific imports from spacetimedb_sdk modules

### 2. Assertion Patterns

**DO NOT USE:**
```python
def test_something():
    if condition:
        return True
    return False
```

**USE INSTEAD:**
```python
def test_something():
    """Test description"""
    # Test logic
    assert condition, "Descriptive error message"
    
    # Additional assertions
    assert expected == actual, f"Expected {expected}, got {actual}"
```

**Exception Testing:**
```python
def test_exception_handling():
    """Test that exceptions are properly raised"""
    with pytest.raises(ValueError, match="specific error message"):
        some_function_that_should_fail()
```

### 3. Test Method Structure

**Standard Test Method:**
```python
@pytest.mark.unit  # Use appropriate marker
def test_specific_functionality():
    """
    Test specific functionality with clear description.
    
    This test verifies that [specific behavior] works correctly
    when [specific conditions] are met.
    """
    # Arrange
    setup_data = create_test_data()
    
    # Act
    result = function_under_test(setup_data)
    
    # Assert
    assert result is not None, "Result should not be None"
    assert result.property == expected_value, f"Expected {expected_value}"
```

### 4. Test Class Structure

**Standard Test Class:**
```python
class TestSpecificFeature:
    """Test suite for specific feature functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test method"""
        self.test_data = create_test_data()
        yield
        # Cleanup if needed
    
    def test_normal_case(self):
        """Test normal operation"""
        assert self.test_data is not None
    
    def test_edge_case(self):
        """Test edge case handling"""
        assert edge_condition_met()
```

### 5. Async Test Patterns

**Async Test Method:**
```python
@pytest.mark.asyncio
async def test_async_functionality():
    """Test async functionality"""
    client = await create_async_client()
    
    try:
        result = await client.some_async_operation()
        assert result.success, "Async operation should succeed"
    finally:
        await client.cleanup()
```

### 6. Mock Usage Patterns

**Standard Mock Usage:**
```python
from unittest.mock import Mock, patch, MagicMock

def test_with_mocks():
    """Test using mocks"""
    mock_service = Mock()
    mock_service.get_data.return_value = {"test": "data"}
    
    with patch('module.external_service', mock_service):
        result = function_using_service()
        assert result["test"] == "data"
        mock_service.get_data.assert_called_once()
```

### 7. Error Testing Patterns

**Standard Error Testing:**
```python
def test_error_conditions():
    """Test error handling"""
    # Test specific exception type
    with pytest.raises(ValueError):
        invalid_function_call()
    
    # Test exception message
    with pytest.raises(ConnectionError, match="Connection failed"):
        failing_connection()
    
    # Test multiple exception scenarios
    for invalid_input in [None, "", -1, []]:
        with pytest.raises((ValueError, TypeError)):
            validate_input(invalid_input)
```

### 8. Test Markers Usage

**Standard Markers:**
```python
@pytest.mark.unit          # Fast unit tests
@pytest.mark.integration   # Integration tests with external services  
@pytest.mark.slow          # Slow-running tests
@pytest.mark.asyncio       # Async tests
@pytest.mark.security      # Security-related tests
@pytest.mark.performance   # Performance benchmarks
@pytest.mark.regression    # Regression tests for bug fixes
```

### 9. Parametrized Tests

**Parametrized Test Pattern:**
```python
@pytest.mark.parametrize("input_value,expected", [
    ("valid_input", True),
    ("invalid_input", False),
    ("", False),
    (None, False),
])
def test_validation_function(input_value, expected):
    """Test validation with various inputs"""
    result = validate(input_value)
    assert result == expected, f"Failed for input: {input_value}"
```

### 10. Fixture Patterns

**Standard Fixture:**
```python
@pytest.fixture
def test_client():
    """Create test client for tests"""
    client = SpacetimeDBClient.builder()\
        .with_uri("ws://localhost:3000")\
        .with_module_name("test_module")\
        .build()
    
    yield client
    
    # Cleanup
    if hasattr(client, 'disconnect'):
        client.disconnect()
```

## Common Anti-Patterns to Avoid

1. **Returning boolean values from test functions**
2. **Multiple sys.path manipulations**
3. **Test classes with __init__ methods**
4. **Missing docstrings in test methods**
5. **Weak assertion messages**
6. **Tests that don't actually test anything**
7. **Overly complex test setup**
8. **Testing implementation details instead of behavior**

## File Organization

```
tests/
├── unit/               # Fast unit tests
├── integration/        # Integration tests
├── performance/        # Performance tests
├── security/          # Security tests
├── fixtures/          # Shared test fixtures
└── conftest.py        # pytest configuration
```