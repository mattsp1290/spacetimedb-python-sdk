"""
Pytest fixtures and setup utilities for SpacetimeDB testing.

Provides:
- Database setup/teardown
- Test isolation
- CI/CD integration helpers
- Coverage reporting utilities
"""

import asyncio
import os
import pytest
import tempfile
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator, Set
from contextlib import contextmanager

from .testing import (
    MockSpacetimeDBConnection,
    MockWebSocketAdapter,
    TestDataGenerator,
    ProtocolComplianceTester,
    PerformanceBenchmark
)
from .modern_client import ModernSpacetimeDBClient
from .connection_builder import SpacetimeDBConnectionBuilder


# Environment configuration

def is_ci_environment() -> bool:
    """Check if running in CI environment."""
    return any(os.environ.get(var) for var in [
        'CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS',
        'GITLAB_CI', 'JENKINS_URL', 'CIRCLECI'
    ])


def get_test_database_url() -> str:
    """Get test database URL from environment or default."""
    return os.environ.get('SPACETIMEDB_TEST_URL', 'ws://localhost:3000')


def get_test_module_name() -> str:
    """Get test module name from environment or default."""
    return os.environ.get('SPACETIMEDB_TEST_MODULE', 'test_module')


# Pytest fixtures

@pytest.fixture(scope='session')
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_connection() -> MockSpacetimeDBConnection:
    """Provide a mock SpacetimeDB connection."""
    return MockSpacetimeDBConnection()


@pytest.fixture
def mock_websocket() -> MockWebSocketAdapter:
    """Provide a mock WebSocket adapter."""
    return MockWebSocketAdapter()


@pytest.fixture
def test_data() -> TestDataGenerator:
    """Provide test data generator."""
    return TestDataGenerator()


@pytest.fixture
def protocol_tester():
    """Provide protocol compliance tester factory."""
    def _create_tester(connection):
        return ProtocolComplianceTester(connection)
    return _create_tester


@pytest.fixture
def benchmark() -> PerformanceBenchmark:
    """Provide performance benchmark."""
    return PerformanceBenchmark()


@pytest.fixture
async def client_builder() -> SpacetimeDBConnectionBuilder:
    """Provide a connection builder for tests."""
    return ModernSpacetimeDBClient.builder()


@pytest.fixture
async def mock_client(mock_connection) -> ModernSpacetimeDBClient:
    """Provide a mock client for testing."""
    # Create a client that uses mock connection
    client = ModernSpacetimeDBClient(
        uri=get_test_database_url(),
        module_name=get_test_module_name()
    )
    
    # Replace internal connection with mock
    client._ws_client = mock_connection.websocket
    client._identity = mock_connection.identity
    client._connection_id = mock_connection.connection_id
    
    return client


@pytest.fixture
async def connected_mock_client(mock_client):
    """Provide a connected mock client."""
    await mock_client.connect()
    yield mock_client
    await mock_client.disconnect()


@pytest.fixture(scope='session')
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp(prefix='spacetimedb_test_'))
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def test_config(temp_dir) -> Dict[str, Any]:
    """Provide test configuration."""
    return {
        'temp_dir': temp_dir,
        'database_url': get_test_database_url(),
        'module_name': get_test_module_name(),
        'is_ci': is_ci_environment(),
        'timeout': 30.0 if is_ci_environment() else 10.0
    }


# Test database management

class TestDatabase:
    """Manage test database lifecycle."""
    
    def __init__(self, connection: Any):
        self.connection = connection
        self.tables_created: List[str] = []
        self.initial_state: Dict[str, List] = {}
    
    async def setup(self):
        """Set up test database."""
        await self.connection.connect()
        
        # Create test tables
        await self.create_table('users', [
            ('id', 'u32'),
            ('username', 'string'),
            ('email', 'string'),
            ('created_at', 'timestamp')
        ])
        
        await self.create_table('messages', [
            ('id', 'u32'),
            ('user_id', 'u32'),
            ('content', 'string'),
            ('timestamp', 'timestamp')
        ])
        
        # Store initial state
        for table in self.tables_created:
            self.initial_state[table] = await self.get_table_data(table)
    
    async def teardown(self):
        """Tear down test database."""
        # Restore initial state
        for table, data in self.initial_state.items():
            await self.clear_table(table)
            for row in data:
                await self.insert_row(table, row)
        
        await self.connection.disconnect()
    
    async def create_table(self, name: str, schema: List[tuple]):
        """Create a test table."""
        # In mock, just track it
        self.tables_created.append(name)
        if hasattr(self.connection, 'tables'):
            self.connection.tables[name] = []
    
    async def clear_table(self, name: str):
        """Clear all data from a table."""
        if hasattr(self.connection, 'tables'):
            self.connection.tables[name] = []
    
    async def insert_row(self, table: str, row: Dict[str, Any]):
        """Insert a row into a table."""
        if hasattr(self.connection, 'add_table_row'):
            self.connection.add_table_row(table, row)
    
    async def get_table_data(self, table: str) -> List[Dict[str, Any]]:
        """Get all data from a table."""
        if hasattr(self.connection, 'tables'):
            return self.connection.tables.get(table, [])
        return []


@pytest.fixture
async def test_database(mock_connection) -> Generator[TestDatabase, None, None]:
    """Provide a test database with setup/teardown."""
    db = TestDatabase(mock_connection)
    await db.setup()
    yield db
    await db.teardown()


# Test isolation

class TestIsolation:
    """Ensure test isolation."""
    
    def __init__(self):
        self.original_env: Dict[str, str] = {}
        self.temp_files: List[Path] = []
    
    def __enter__(self):
        # Save original environment
        self.original_env = dict(os.environ)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up temp files
        for path in self.temp_files:
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    
    def set_env(self, key: str, value: str):
        """Set environment variable for test."""
        os.environ[key] = value
    
    def create_temp_file(self, name: str, content: str = "") -> Path:
        """Create a temporary file."""
        path = Path(tempfile.mktemp(prefix=f'{name}_'))
        path.write_text(content)
        self.temp_files.append(path)
        return path


@pytest.fixture
def isolated_test() -> Generator[TestIsolation, None, None]:
    """Provide test isolation context."""
    with TestIsolation() as isolation:
        yield isolation


# Coverage utilities

class CoverageTracker:
    """Track test coverage for SpacetimeDB operations."""
    
    def __init__(self):
        self.operations_covered: Set[str] = set()
        self.operations_total: Set[str] = {
            'connect', 'disconnect', 'subscribe', 'unsubscribe',
            'call_reducer', 'query', 'on_connect', 'on_disconnect',
            'on_error', 'on_transaction', 'compression', 'energy_tracking'
        }
    
    def mark_covered(self, operation: str):
        """Mark an operation as covered."""
        self.operations_covered.add(operation)
    
    def get_coverage_report(self) -> str:
        """Get coverage report."""
        covered = len(self.operations_covered)
        total = len(self.operations_total)
        percentage = (covered / total * 100) if total > 0 else 0
        
        report = [
            "SpacetimeDB Operation Coverage",
            "=" * 30,
            f"Total Operations: {total}",
            f"Covered: {covered}",
            f"Coverage: {percentage:.1f}%",
            "",
            "Covered Operations:"
        ]
        
        for op in sorted(self.operations_covered):
            report.append(f"  ✓ {op}")
        
        report.append("\nUncovered Operations:")
        for op in sorted(self.operations_total - self.operations_covered):
            report.append(f"  ✗ {op}")
        
        return "\n".join(report)


@pytest.fixture(scope='session')
def coverage_tracker() -> CoverageTracker:
    """Provide coverage tracker for session."""
    return CoverageTracker()


# CI/CD helpers

def pytest_configure(config):
    """Configure pytest for SpacetimeDB testing."""
    # Add markers
    config.addinivalue_line(
        "markers", 
        "spacetimedb: mark test as SpacetimeDB test"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers",
        "stress: mark test as stress test"
    )
    config.addinivalue_line(
        "markers",
        "wasm: mark test as requiring WASM"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on environment."""
    if is_ci_environment():
        # Skip stress tests in CI by default
        skip_stress = pytest.mark.skip(reason="Stress tests skipped in CI")
        for item in items:
            if "stress" in item.keywords:
                item.add_marker(skip_stress)
    
    # Skip WASM tests if module not available
    if not Path('sdk_test_module.wasm').exists():
        skip_wasm = pytest.mark.skip(reason="WASM module not available")
        for item in items:
            if "wasm" in item.keywords:
                item.add_marker(skip_wasm)


# Test result aggregation

class TestResultAggregator:
    """Aggregate test results across multiple runs."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    def add_result(self, test_name: str, passed: bool, duration: float, **metadata):
        """Add a test result."""
        self.results.append({
            'test_name': test_name,
            'passed': passed,
            'duration': duration,
            'timestamp': time.time(),
            **metadata
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        total_duration = sum(r['duration'] for r in self.results)
        
        return {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'total_duration': total_duration,
            'average_duration': total_duration / total if total > 0 else 0
        }
    
    def export_json(self, filepath: Path):
        """Export results to JSON."""
        import json
        with open(filepath, 'w') as f:
            json.dump({
                'summary': self.get_summary(),
                'results': self.results
            }, f, indent=2)


@pytest.fixture(scope='session')
def result_aggregator() -> TestResultAggregator:
    """Provide test result aggregator."""
    return TestResultAggregator()


# Example usage in conftest.py

CONFTEST_TEMPLATE = '''"""
Pytest configuration for SpacetimeDB tests.

Usage:
    1. Copy this to your test directory as conftest.py
    2. Customize fixtures as needed
    3. Run tests with: pytest --spacetimedb
"""

import pytest
from spacetimedb_sdk.test_fixtures import *

# Add any custom fixtures here

@pytest.fixture
def my_custom_fixture():
    """Example custom fixture."""
    return {"custom": "data"}


# Hook implementations

def pytest_runtest_makereport(item, call):
    """Hook to capture test results."""
    if call.when == 'call':
        # Access result aggregator if available
        aggregator = item.session.config._result_aggregator
        if aggregator and hasattr(call, 'result'):
            aggregator.add_result(
                test_name=item.nodeid,
                passed=call.result.passed,
                duration=call.duration
            )
''' 