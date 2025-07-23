"""
Test configuration and fixtures for spacetimedb_sdk tests.

This file contains common pytest fixtures, configurations, and setup
for running the spacetimedb_sdk test suite.
"""

import asyncio
import os
import sys
import time
import threading
import pytest
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import socket
import ssl
import urllib.request
import websocket
import json
import queue
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# Configure Hypothesis for better performance
from hypothesis import settings, Verbosity, HealthCheck

# Import SDK components after path setup for mocking classes
try:
    from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL
    from spacetimedb_sdk.websocket_client import ConnectionState
    from spacetimedb_sdk.events.core_events import EventType, Event
    MOCK_SDK_AVAILABLE = True
except ImportError:
    # Define fallback constants for mocking
    TEXT_PROTOCOL = "text"
    BIN_PROTOCOL = "binary" 
    MOCK_SDK_AVAILABLE = False


class MockConnectionState(Enum):
    """Mock connection states for testing."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


@dataclass
class MockConnectionEvent:
    """Mock connection event for testing."""
    event_type: str
    timestamp: float
    data: Dict[str, Any]
    error: Optional[Exception] = None


class MockWebSocketApp:
    """
    Comprehensive WebSocket app mock that simulates real connection behavior
    including events, callbacks, and state transitions without network calls.
    """
    
    def __init__(self, url, on_open=None, on_message=None, on_error=None, 
                 on_close=None, header=None, subprotocols=None, **kwargs):
        self.url = url
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.header = header
        self.subprotocols = subprotocols
        self.closed = False
        self.connected = False
        self.opened = False  # Add opened state tracking
        self._sent_messages = []
        self._connection_events = []
        self._event_queue = queue.Queue()
        self._should_fail = False
        self._failure_reason = None
        self._connection_delay = 0.001  # Optimized minimal delay for tests
        self._auto_send_identity = True
        self._mock_server_responses = True
        self._state = MockConnectionState.DISCONNECTED
        self._custom_behavior = None  # For custom test behavior
        
    def run_forever(self, dispatcher=None, sslopt=None, ping_interval=0, ping_timeout=None, **kwargs):
        """Simulate connection process with proper event triggering."""
        if self._custom_behavior:
            self._custom_behavior()
            return
            
        if self._should_fail:
            self._trigger_error(Exception(self._failure_reason or "Mock connection failure"))
            return
            
        # Simulate connection
        self._state = MockConnectionState.CONNECTING
        if self._connection_delay > 0:
            time.sleep(self._connection_delay)
            
        self._state = MockConnectionState.CONNECTED
        self.connected = True
        
        # Only call on_open if not already opened
        if self.on_open and not self.opened:
            self.opened = True
            try:
                self.on_open(self)
            except Exception as e:
                self._trigger_error(e)
                return
                
        # Auto-send identity if enabled
        if self._auto_send_identity:
            self._send_mock_identity_token()
            
        self._state = MockConnectionState.AUTHENTICATED
        
    def _send_mock_identity_token(self):
        """Send mock identity token."""
        if not self.on_message:
            return
            
        identity_msg = {
            "IdentityToken": {
                "token": "mock_test_token_12345",
                "identity": "a" * 64,
                "connection_id": "b" * 32
            }
        }
        
        try:
            self.on_message(self, json.dumps(identity_msg))
        except Exception as e:
            self._trigger_error(e)
            
    def _trigger_error(self, error):
        """Trigger error callback."""
        self._state = MockConnectionState.ERROR
        if self.on_error:
            self.on_error(self, error)
        self._trigger_close(1006, "Connection error")
        
    def _trigger_close(self, code=1000, reason="Normal closure"):
        """Trigger close callback."""
        self.connected = False
        self.closed = True
        self._state = MockConnectionState.DISCONNECTED
        if self.on_close:
            self.on_close(self, code, reason)
            
    def send(self, data, opcode=None):
        """Track sent messages."""
        self._sent_messages.append({
            "data": data,
            "opcode": opcode or websocket.ABNF.OPCODE_TEXT,
            "timestamp": time.time()
        })
        
    def close(self, code=1000, reason="Normal closure"):
        """Close the mock connection."""
        if not self.closed:
            self._trigger_close(code, reason)
            
    def get_sent_messages(self):
        """Get all sent messages for testing."""
        return self._sent_messages.copy()
        
    def configure_failure(self, should_fail=True, reason="Mock failure"):
        """Configure the mock to fail connections."""
        self._should_fail = should_fail
        self._failure_reason = reason
        
    def configure_custom_behavior(self, behavior_func):
        """Configure custom behavior for testing specific scenarios."""
        self._custom_behavior = behavior_func

# Custom Hypothesis profiles optimized for our tests
settings.register_profile("fast", 
    deadline=3000,  # 3 seconds - more reasonable for complex operations
    max_examples=50,  # Reduced examples for faster execution
    stateful_step_count=20,  # Reduced steps for state machines
    suppress_health_check=[
        HealthCheck.too_slow,  # Our complex tests may be inherently slow
        HealthCheck.function_scoped_fixture,  # Allow function-scoped fixtures
        HealthCheck.filter_too_much,  # Allow reasonable filtering
    ],
    verbosity=Verbosity.normal
)

settings.register_profile("thorough",
    deadline=10000,  # 10 seconds for comprehensive testing
    max_examples=200,  # More examples for thorough testing
    stateful_step_count=100,  # More state machine steps
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        HealthCheck.filter_too_much,
    ],
    verbosity=Verbosity.normal
)

settings.register_profile("ci",
    deadline=5000,  # 5 seconds for CI
    max_examples=75,  # Balanced examples for CI
    stateful_step_count=30,  # Balanced state machine steps
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        HealthCheck.filter_too_much,
    ],
    verbosity=Verbosity.verbose
)

# Load the appropriate profile based on environment
if os.environ.get('HYPOTHESIS_PROFILE'):
    settings.load_profile(os.environ.get('HYPOTHESIS_PROFILE'))
elif os.environ.get('CI'):
    settings.load_profile("ci")
else:
    settings.load_profile("fast")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Import SDK components after path setup
try:
    from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient
    from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
    from spacetimedb_sdk.events.event_system import EventSystem
    from spacetimedb_sdk.auth.storage import AuthStorage
    from spacetimedb_sdk.connection.connection_manager import ConnectionManager
    from spacetimedb_sdk.monitoring.performance_monitor import PerformanceMonitor
    
    SDK_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import SDK components: {e}")
    SDK_AVAILABLE = False


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    yield loop
    
    # Clean up
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
    except Exception:
        pass
    finally:
        if not loop.is_closed():
            loop.close()


@pytest.fixture(scope="function")
def asyncio_event_loop():
    """Function-scoped event loop for asyncio tests."""
    try:
        # Check if there's already a running loop
        existing_loop = asyncio.get_running_loop()
        yield existing_loop
    except RuntimeError:
        # No running loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            yield loop
        finally:
            try:
                # Cancel all running tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            finally:
                try:
                    loop.close()
                finally:
                    # Clear the event loop policy to prevent interference
                    asyncio.set_event_loop(None)


@pytest.fixture(autouse=True)
def ensure_asyncio_event_loop():
    """Auto-applied fixture to ensure there's always an event loop available."""
    try:
        # Check if there's already a running loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create a temporary one for the test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        created_loop = True
    else:
        created_loop = False
    
    try:
        yield loop
    finally:
        if created_loop:
            try:
                # Clean up any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            finally:
                try:
                    if not loop.is_closed():
                        loop.close()
                finally:
                    asyncio.set_event_loop(None)


@pytest.fixture
def robust_asyncio_test():
    """
    Fixture to ensure robust asyncio test execution.
    
    This fixture provides extra safeguards for tests that use asyncio operations
    and might encounter event loop issues in different test environments.
    """
    # Store original event loop policy
    original_policy = asyncio.get_event_loop_policy()
    
    try:
        # Ensure we have a clean event loop for the test
        loop = ensure_event_loop()
        
        # Provide context for the test
        yield {
            'loop': loop,
            'ensure_loop': ensure_event_loop,
            'asyncio_run': lambda coro: asyncio.run(coro) if not loop.is_running() else loop.run_until_complete(coro)
        }
        
    finally:
        # Restore original policy and clean up
        try:
            current_loop = asyncio.get_event_loop()
            if current_loop and not current_loop.is_closed():
                # Cancel remaining tasks
                pending = asyncio.all_tasks(current_loop)
                for task in pending:
                    task.cancel()
                
                if pending:
                    try:
                        current_loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            asyncio.set_event_loop_policy(original_policy)


@pytest.fixture
def mock_spacetimedb_client():
    """Create a mock SpacetimeDB client for testing."""
    if not SDK_AVAILABLE:
        pytest.skip("SDK not available")
    
    mock_client = Mock(spec=SpacetimeDBClient)
    mock_client.is_connected = Mock(return_value=False)
    mock_client.connect = Mock(return_value=True)
    mock_client.disconnect = Mock()
    mock_client.subscribe = Mock()
    mock_client.call_reducer = Mock()
    mock_client.on_connect = Mock()
    mock_client.on_disconnect = Mock()
    mock_client.on_error = Mock()
    
    return mock_client


@pytest.fixture
def connection_tracker():
    """Track connection events for testing."""
    class ConnectionTracker:
        def __init__(self):
            self.reset()
            
        def reset(self):
            self.connected = False
            self.disconnected = False
            self.error = None
            self.identity = None
            self.subscription_applied = False
            self.events_received = []
            
        def on_connect(self, client, identity):
            self.connected = True
            self.identity = identity
            
        def on_disconnect(self, client):
            self.disconnected = True
            
        def on_error(self, error):
            self.error = error
            
        def on_subscription_applied(self, client):
            self.subscription_applied = True
            
        def on_event(self, event_name, event_data):
            self.events_received.append((event_name, event_data))
    
    return ConnectionTracker()


@pytest.fixture
def test_config():
    """Test configuration values."""
    return {
        'timeout': 30.0 if os.environ.get('CI') else 10.0,
        'database_address': 'testdb',
        'module_name': 'test_module',
        'server_url': 'http://localhost:3000',
        'websocket_url': 'ws://localhost:3000',
        'is_ci': bool(os.environ.get('CI'))
    }


def wait_for_connection():
    """Helper to wait for connection events"""
    
    def _wait(tracker, timeout=5, check_connected=True):
        """Wait for connection to complete or fail"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if check_connected and tracker.connected:
                return True
            elif not check_connected and (tracker.disconnected or tracker.error):
                return True
            time.sleep(0.01)  # Reduced from 0.1s to 0.01s for testing
        return False
    
    return _wait


@pytest.fixture
def performance_monitor():
    """Create a performance monitor for testing."""
    if not SDK_AVAILABLE:
        pytest.skip("SDK not available")
    
    monitor = PerformanceMonitor()
    yield monitor
    
    # Clean up
    try:
        monitor.stop()
    except Exception:
        pass


@pytest.fixture
def mock_connection_diagnostics():
    """Mock connection diagnostics to prevent real network calls during tests."""
    def mock_check_server_available(host: str):
        """Mock server availability check that always returns success for tests."""
        return True, {
            "host": host,
            "checked_at": time.time(),
            "socket_reachable": True,
            "http_reachable": True,
            "health_status_code": 200,
            "server_version": "1.1.2-mock",
            "server_status": "ok",
            "response_time_ms": 1.0
        }
    
    def mock_check_database_exists(host: str, database: str):
        """Mock database check that always returns success for tests."""
        return {
            "exists": True,
            "error": None,
            "status_code": None,
            "evidence": [f"Database '{database}' is available on {host}"],
            "suggested_action": None
        }
    
    def mock_run_preflight_checks(host: str, database: str, raise_on_failure: bool = True):
        """Mock preflight checks that always pass for tests."""
        return {
            "all_passed": True,
            "checks_passed": ["server_available", "database_exists", "v112_compatible"],
            "checks_failed": [],
            "server_check": mock_check_server_available(host)[1],
            "database_check": mock_check_database_exists(host, database),
            "v112_check": {
                "v112_compatible": True,
                "issues": []
            },
            "compatibility_warnings": []
        }
    
    def mock_diagnose_connection_error(error, host: str = None):
        """Mock connection error diagnosis."""
        from spacetimedb_sdk.exceptions import ServerNotAvailableError
        return ServerNotAvailableError(
            server_address=host or "localhost:3000",
            reason="Mocked connection error for testing",
            network_diagnostics={"mock": True}
        )
    
    with patch('spacetimedb_sdk.connection_diagnostics.ConnectionDiagnostics.check_server_available', side_effect=mock_check_server_available) as mock1:
        with patch('spacetimedb_sdk.connection_diagnostics.ConnectionDiagnostics.check_database_exists', side_effect=mock_check_database_exists) as mock2:
            with patch('spacetimedb_sdk.connection_diagnostics.ConnectionDiagnostics.run_preflight_checks', side_effect=mock_run_preflight_checks) as mock3:
                with patch('spacetimedb_sdk.connection_diagnostics.ConnectionDiagnostics.diagnose_connection_error', side_effect=mock_diagnose_connection_error) as mock4:
                    yield (mock1, mock2, mock3, mock4)


@pytest.fixture
def mock_websocket_comprehensive():
    """
    Comprehensive WebSocket mocking that prevents real network connections
    and properly simulates connection events for all tests.
    """
    with patch('spacetimedb_sdk.websocket_client.websocket') as mock_ws_client:
        with patch('spacetimedb_sdk.connection.connection_manager.websocket') as mock_ws_manager:
            with patch('websocket.WebSocketApp', MockWebSocketApp):
                # Set up both mocks
                mock_ws_client.WebSocketApp = MockWebSocketApp
                mock_ws_client.WebSocketException = websocket.WebSocketException
                mock_ws_client.ABNF = websocket.ABNF
                
                mock_ws_manager.WebSocketApp = MockWebSocketApp
                mock_ws_manager.WebSocketException = websocket.WebSocketException
                mock_ws_manager.ABNF = websocket.ABNF
                
                yield mock_ws_manager  # Return the connection manager mock since that's what creates WebSocket connections


@pytest.fixture
def no_real_connections():
    """Ensure no real network connections are made during tests, except for localhost testing."""
    patches = []
    
    # Block only network-related socket connections, not local pipes or localhost
    import socket as socket_module
    original_socket = socket_module.socket
    
    def selective_socket_block(*args, **kwargs):
        # Allow AF_UNIX sockets for local pipes (used by asyncio)
        if args and args[0] == socket_module.AF_UNIX:
            return original_socket(*args, **kwargs)
            
        # Allow localhost connections for mock server testing
        # Create the socket normally, we'll block only on bind/connect to external addresses
        return original_socket(*args, **kwargs)
    
    # Don't patch socket creation - let localhost connections through
    # socket_patch = patch('socket.socket', side_effect=selective_socket_block)
    # socket_patch.start()
    # patches.append(socket_patch)
    
    # Block SSL connections for external hosts only
    ssl_patch = patch('ssl.create_default_context')
    mock_ssl = ssl_patch.start()
    mock_ssl.side_effect = ConnectionError("Real SSL connections disabled in tests")
    patches.append(ssl_patch)
    
    # Block HTTP requests to external hosts
    original_urlopen = urllib.request.urlopen
    def selective_urlopen(url, *args, **kwargs):
        if isinstance(url, str):
            if 'localhost' in url or '127.0.0.1' in url:
                return original_urlopen(url, *args, **kwargs)
        raise ConnectionError("HTTP requests to external hosts disabled in tests")
    
    http_patch = patch('urllib.request.urlopen', side_effect=selective_urlopen)
    http_patch.start()
    patches.append(http_patch)
    
    yield
    
    # Cleanup patches
    for patch_obj in patches:
        try:
            patch_obj.stop()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def prevent_real_network_connections(request, mock_connection_diagnostics):
    """
    Auto-applied fixture that prevents real network connections globally.
    This ensures test isolation and prevents accidental external calls.
    Tests marked with @pytest.mark.real_connection are exempt.
    """
    # Skip ALL network blocking for tests that need real connections (like integration tests)
    if request.node.get_closest_marker("real_connection"):
        yield
        return
        
    # Skip ALL network blocking for integration tests
    if "integration" in request.node.nodeid.lower():
        yield
        return
        
    # Apply normal network blocking for other tests (only apply the fixtures for non-integration tests)
    no_real_connections = request.getfixturevalue('no_real_connections')
    mock_websocket_comprehensive = request.getfixturevalue('mock_websocket_comprehensive') 
    
    yield


@pytest.fixture
def event_system():
    """Create an event system for testing."""
    if not SDK_AVAILABLE:
        pytest.skip("SDK not available")
    
    system = EventSystem()
    yield system
    
    # Clean up
    try:
        system.shutdown()
    except Exception:
        pass


@pytest.fixture
def isolated_auth_storage(tmp_path):
    """Create isolated auth storage for testing."""
    if not SDK_AVAILABLE:
        pytest.skip("SDK not available")
    
    # Create temporary auth storage
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    
    storage = AuthStorage(storage_path=str(auth_dir))
    yield storage
    
    # Clean up
    try:
        storage.clear_all()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def cleanup_threads():
    """Clean up background threads after each test."""
    # Get initial thread count
    initial_threads = threading.active_count()
    initial_thread_names = [t.name for t in threading.enumerate()]
    
    yield
    
    # Allow some time for cleanup
    time.sleep(0.01)  # Reduced from 0.1s to 0.01s for testing
    
    # Check for thread leaks (allow some tolerance)
    final_threads = threading.active_count()
    if final_threads > initial_threads + 2:  # Allow some tolerance
        final_thread_names = [t.name for t in threading.enumerate()]
        leaked_threads = [name for name in final_thread_names 
                         if name not in initial_thread_names]
        if leaked_threads:
            print(f"Warning: Potential thread leak detected: {leaked_threads}")


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global SDK state between tests."""
    yield
    
    # Reset any global caches or singletons
    if SDK_AVAILABLE:
        try:
            # Reset performance monitoring
            if hasattr(PerformanceMonitor, '_instance'):
                PerformanceMonitor._instance = None
            
            # Reset any other global state as needed
        except Exception:
            pass


# Test markers
pytest_mark_slow = pytest.mark.slow
pytest_mark_integration = pytest.mark.integration
pytest_mark_property = pytest.mark.property
pytest_mark_security = pytest.mark.security


def ensure_event_loop():
    """Utility function to ensure an event loop exists."""
    try:
        loop = asyncio.get_running_loop()
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "property: marks tests as property-based tests")
    config.addinivalue_line("markers", "security: marks tests as security tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "regression: marks tests as regression tests")
    config.addinivalue_line("markers", "network: marks tests requiring network connectivity")
    config.addinivalue_line("markers", "mock_network: marks tests using mocked network")
    config.addinivalue_line("markers", "websocket: marks tests for WebSocket connections")
    config.addinivalue_line("markers", "real_connection: marks tests requiring real connections")
    config.addinivalue_line("markers", "offline: marks tests that should work offline")
    config.addinivalue_line("markers", "asyncio: marks tests as asyncio tests")
    
    # Ensure there's an event loop available for the session
    try:
        ensure_event_loop()
    except Exception as e:
        print(f"Warning: Could not set up session event loop: {e}")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add automatic markers."""
    for item in items:
        # Add property marker to property-based tests
        if "property" in item.nodeid:
            item.add_marker(pytest_mark_property)
        
        # Add slow marker to tests that might be slow
        if any(keyword in item.nodeid.lower() 
               for keyword in ["concurrent", "threading", "performance", "load"]):
            item.add_marker(pytest_mark_slow)
        
        # Add integration marker to integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest_mark_integration)
        
        # Add security marker to security tests
        if "security" in item.nodeid:
            item.add_marker(pytest_mark_security)
        
        # Add asyncio marker to asyncio tests
        if any(keyword in item.nodeid.lower() 
               for keyword in ["asyncio", "async_"]) or hasattr(item.function, '__code__') and 'async' in str(item.function):
            item.add_marker(pytest.mark.asyncio)
        
        # Specifically mark the problematic tests mentioned in the issue
        if any(test_name in item.nodeid 
               for test_name in ["test_large_message_progress_tracking", "test_protocol_error_recovery"]):
            item.add_marker(pytest.mark.asyncio)


def pytest_runtest_setup(item):
    """Setup for each test item."""
    # Skip tests based on markers and environment
    if item.get_closest_marker("slow") and os.environ.get("SKIP_SLOW_TESTS"):
        pytest.skip("Skipping slow test due to SKIP_SLOW_TESTS")
    
    if item.get_closest_marker("integration") and os.environ.get("SKIP_INTEGRATION_TESTS"):
        pytest.skip("Skipping integration test due to SKIP_INTEGRATION_TESTS")
    
    # Ensure asyncio tests have an event loop available
    if item.get_closest_marker("asyncio"):
        try:
            ensure_event_loop()
        except Exception as e:
            pytest.skip(f"Could not set up event loop for asyncio test: {e}")


def pytest_runtest_teardown(item, nextitem):
    """Cleanup after each test."""
    # Allow time for background operations to complete
    time.sleep(0.005)  # Reduced from 0.05s to 0.005s for testing
    
    # Clean up any lingering event loops
    try:
        import threading
        for thread in threading.enumerate():
            if thread != threading.current_thread() and hasattr(thread, '_target'):
                if thread._target and 'event' in str(thread._target).lower():
                    # Don't forcefully kill threads, just mark for cleanup
                    pass
    except Exception:
        pass
        
    # Clear any global state that might interfere between tests
    import gc
    gc.collect()
    
    # Reset any module-level singletons or caches
    try:
        # Clear any cached event managers
        from spacetimedb_sdk.events.event_manager import UnifiedEventManager
        if hasattr(UnifiedEventManager, '_instances'):
            UnifiedEventManager._instances.clear()
    except (ImportError, AttributeError):
        pass