"""
Testing utilities and fixtures for SpacetimeDB SDK.

This package provides test utilities, fixtures, and helpers that should only
be used in test environments, not in production code.

To use testing utilities, import them directly:
    from spacetimedb_sdk.test_fixtures import is_ci_environment, TestDatabase
    from spacetimedb_sdk.testing import MockSpacetimeDBConnection  # from main testing module

Or import everything:
    from spacetimedb_sdk.test_fixtures.fixtures import *
"""

# Re-export only fixture utilities to avoid circular imports
from .fixtures import (
    # Environment configuration
    is_ci_environment,
    get_test_database_url,
    get_test_module_name,
    
    # Test database management
    TestDatabase,
    
    # Test isolation
    TestIsolation,
    
    # Coverage utilities
    CoverageTracker,
    
    # Test result aggregation
    TestResultAggregator,
    
    # Template for conftest.py
    CONFTEST_TEMPLATE,
    
    # Pytest fixtures - these are the actual fixture functions
    # Users should typically import these via conftest.py
    event_loop,
    mock_connection,
    mock_websocket,
    test_data,
    protocol_tester,
    benchmark,
    client_builder,
    mock_client,
    connected_mock_client,
    temp_dir,
    test_config,
    test_database,
    isolated_test,
    coverage_tracker,
    result_aggregator,
    
    # Pytest configuration functions
    pytest_configure,
    pytest_collection_modifyitems
)

# NOTE: MockSpacetimeDBConnection, MockWebSocketAdapter, and other testing
# framework utilities are available from spacetimedb_sdk.testing module.
# Import them directly from there to avoid circular imports:
#   from spacetimedb_sdk.testing import MockSpacetimeDBConnection

__all__ = [
    # Environment helpers
    "is_ci_environment",
    "get_test_database_url", 
    "get_test_module_name",
    
    # Test utilities
    "TestDatabase",
    "TestIsolation",
    "CoverageTracker",
    "TestResultAggregator",
    
    # Templates
    "CONFTEST_TEMPLATE",
    
    # Pytest fixtures
    "event_loop",
    "mock_connection",
    "mock_websocket",
    "test_data",
    "protocol_tester",
    "benchmark",
    "client_builder",
    "mock_client",
    "connected_mock_client",
    "temp_dir",
    "test_config",
    "test_database",
    "isolated_test",
    "coverage_tracker",
    "result_aggregator",
    
    # Pytest configuration
    "pytest_configure",
    "pytest_collection_modifyitems"
]
