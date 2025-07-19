"""
Integration tests for module interactions during Phase 2 refactoring

These tests validate that the extracted modules work together correctly
when integrated into the refactored architecture.
"""
import pytest
import time
import json
import threading
import queue
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional, List, Callable

from spacetimedb_sdk.websocket_client import WebSocketClient, ConnectionState
from spacetimedb_sdk.protocol import (
    Identity, ConnectionId,
    IdentityToken, Subscribe, SubscriptionError
)
from spacetimedb_sdk.query_id import QueryId


class MockIntegratedWebSocketClient:
    """Mock integrated client that simulates the refactored architecture"""
    
    def __init__(self, host: str, database_address: str, auth_token: Optional[str] = None):
        self.host = host
        self.database_address = database_address
        self.auth_token = auth_token
        
        # Simulated extracted modules
        self.subscription_manager = None
        self.authentication_handler = None
        self.event_system = None
        self.connection_manager = None
        
        # Integration state
        self.connection_state = ConnectionState.DISCONNECTED
        self.is_modules_initialized = False
        self.integration_errors = []
        
    def initialize_modules(self):
        """Initialize all extracted modules"""
        from .conftest import (
            SubscriptionManagerMock, 
            AuthenticationHandlerMock, 
            EventSystemMock
        )
        
        # Initialize modules
        self.subscription_manager = SubscriptionManagerMock()
        self.authentication_handler = AuthenticationHandlerMock()
        self.event_system = EventSystemMock()
        
        # Wire up module interactions
        self._setup_module_integration()
        
        self.is_modules_initialized = True
        
    def _setup_module_integration(self):
        """Set up integration between modules"""
        # Event system to subscription manager
        self.event_system.subscribe(
            'subscription_applied',
            self._handle_subscription_applied
        )
        
        self.event_system.subscribe(
            'subscription_error',
            self._handle_subscription_error
        )
        
        # Event system to authentication handler
        self.event_system.subscribe(
            'authentication_success',
            self._handle_authentication_success
        )
        
        self.event_system.subscribe(
            'authentication_error',
            self._handle_authentication_error
        )
        
        # Authentication handler to subscription manager
        self.authentication_handler.add_auth_callback(
            self._on_auth_success
        )
        
        self.authentication_handler.add_error_callback(
            self._on_auth_error
        )
        
    def _handle_subscription_applied(self, event):
        """Handle subscription applied events"""
        data = event['data']
        self.subscription_manager.handle_subscription_applied(
            data['query_id'], 
            data['table_name']
        )
        
    def _handle_subscription_error(self, event):
        """Handle subscription error events"""
        data = event['data']
        self.subscription_manager.handle_subscription_error(
            data['query_id'], 
            data['error']
        )
        
    def _handle_authentication_success(self, event):
        """Handle authentication success events"""
        data = event['data']
        self.authentication_handler.set_identity(
            data.get('identity'),
            data.get('connection_id'),
            data.get('token')
        )
        
    def _handle_authentication_error(self, event):
        """Handle authentication error events"""
        data = event['data']
        self.authentication_handler.handle_auth_error(data['error'])
        
    def _on_auth_success(self, token, identity, connection_id):
        """Callback for authentication success"""
        self.connection_state = ConnectionState.AUTHENTICATED
        
        # Notify event system
        self.event_system.emit('client_authenticated', {
            'token': token,
            'identity': identity,
            'connection_id': connection_id
        })
        
    def _on_auth_error(self, error):
        """Callback for authentication error"""
        self.connection_state = ConnectionState.ERROR
        self.integration_errors.append(f"Auth error: {error}")
        
        # Notify event system
        self.event_system.emit('client_auth_error', {'error': error})
        
    def connect(self):
        """Simulate connection process"""
        if not self.is_modules_initialized:
            raise RuntimeError("Modules not initialized")
            
        self.connection_state = ConnectionState.CONNECTING
        
        # Emit connection started event
        self.event_system.emit('connection_started', {
            'host': self.host,
            'database': self.database_address
        })
        
        # Simulate successful connection
        self.connection_state = ConnectionState.CONNECTED
        
        # Start authentication if token provided
        if self.auth_token:
            self.authentication_handler.set_auth_token(self.auth_token)
            self.authentication_handler.authenticate()
            
        # Emit connection established event
        self.event_system.emit('connection_established', {
            'state': self.connection_state
        })
        
    def subscribe(self, table_name: str, sql_query: str) -> str:
        """Subscribe to table updates"""
        if not self.is_modules_initialized:
            raise RuntimeError("Modules not initialized")
            
        if self.connection_state not in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
            raise RuntimeError("Not connected")
            
        # Create subscription through subscription manager
        query_id = str(QueryId.generate())
        success = self.subscription_manager.add_subscription(
            query_id, table_name, sql_query
        )
        
        if not success:
            raise RuntimeError("Failed to create subscription")
            
        # Emit subscription created event
        self.event_system.emit('subscription_created', {
            'query_id': query_id,
            'table_name': table_name,
            'sql_query': sql_query
        })
        
        return query_id
        
    def get_connection_state(self) -> ConnectionState:
        """Get current connection state"""
        return self.connection_state
        
    def get_subscription_count(self) -> int:
        """Get subscription count"""
        if not self.subscription_manager:
            return 0
        return self.subscription_manager.get_subscription_count()
        
    def is_authenticated(self) -> bool:
        """Check if authenticated"""
        if not self.authentication_handler:
            return False
        return self.authentication_handler.is_authenticated()
        
    def get_event_history(self) -> List[Dict]:
        """Get event history"""
        if not self.event_system:
            return []
        return self.event_system.get_events()
        
    def get_integration_errors(self) -> List[str]:
        """Get integration errors"""
        return self.integration_errors.copy()


class TestModuleIntegration:
    """Test integration between extracted modules"""
    
    def test_module_initialization_integration(self):
        """Test that modules initialize and wire up correctly"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        
        # Initialize modules
        client.initialize_modules()
        
        # Verify modules are initialized
        assert client.subscription_manager is not None
        assert client.authentication_handler is not None
        assert client.event_system is not None
        assert client.is_modules_initialized is True
        
    def test_connection_and_authentication_integration(self):
        """Test connection and authentication flow integration"""
        client = MockIntegratedWebSocketClient(
            "localhost:3000", 
            "test-db", 
            auth_token="test_token"
        )
        
        client.initialize_modules()
        
        # Connect (should trigger authentication)
        client.connect()
        
        # Verify connection state
        assert client.get_connection_state() == ConnectionState.CONNECTED
        
        # Simulate successful authentication
        identity = Identity.from_hex("a" * 32)
        connection_id = ConnectionId.from_hex("b" * 16)
        identity_token = IdentityToken(
            token="identity_token_123",
            identity=identity,
            connection_id=connection_id
        )
        
        client.authentication_handler.handle_identity_token(identity_token)
        
        # Verify authentication integration
        assert client.is_authenticated() is True
        assert client.get_connection_state() == ConnectionState.AUTHENTICATED
        
    def test_subscription_and_event_integration(self):
        """Test subscription management and event system integration"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        client.connect()
        
        # Subscribe to table
        query_id = client.subscribe("users", "SELECT * FROM users")
        
        # Verify subscription was created
        assert client.get_subscription_count() == 1
        
        subscription = client.subscription_manager.get_subscription(query_id)
        assert subscription is not None
        assert subscription['table_name'] == "users"
        assert subscription['status'] == 'pending'
        
        # Simulate subscription applied event
        client.event_system.emit('subscription_applied', {
            'query_id': query_id,
            'table_name': "users"
        })
        
        # Wait for event processing
        time.sleep(0.1)
        
        # Verify subscription status updated
        subscription = client.subscription_manager.get_subscription(query_id)
        assert subscription['status'] == 'active'
        
    def test_cross_module_error_handling(self):
        """Test error handling across modules"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        client.connect()
        
        # Subscribe to table
        query_id = client.subscribe("users", "SELECT * FROM users")
        
        # Simulate subscription error
        error_message = "Table not found"
        client.event_system.emit('subscription_error', {
            'query_id': query_id,
            'error': error_message
        })
        
        # Wait for event processing
        time.sleep(0.1)
        
        # Verify error was handled
        subscription = client.subscription_manager.get_subscription(query_id)
        assert subscription['status'] == 'error'
        
        # Check metrics were updated
        health = client.subscription_manager.metrics.get_subscription_health("users")
        assert health['error_count'] == 1
        
    def test_authentication_error_propagation(self):
        """Test authentication error propagation through modules"""
        client = MockIntegratedWebSocketClient(
            "localhost:3000", 
            "test-db", 
            auth_token="invalid_token"
        )
        
        client.initialize_modules()
        client.connect()
        
        # Simulate authentication error
        auth_error = "Invalid credentials"
        client.authentication_handler.handle_auth_error(auth_error)
        
        # Verify error propagation
        assert client.get_connection_state() == ConnectionState.ERROR
        assert len(client.get_integration_errors()) > 0
        assert "Auth error" in client.get_integration_errors()[0]
        
    def test_event_system_module_coordination(self):
        """Test event system coordination between modules"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        
        # Track events across modules
        events_received = []
        
        def event_tracker(event):
            events_received.append(event['type'])
            
        client.event_system.subscribe('connection_started', event_tracker)
        client.event_system.subscribe('connection_established', event_tracker)
        client.event_system.subscribe('subscription_created', event_tracker)
        client.event_system.subscribe('client_authenticated', event_tracker)
        
        # Perform operations
        client.connect()
        client.subscribe("messages", "SELECT * FROM messages")
        
        # Simulate authentication success
        client.authentication_handler.set_identity(
            Identity.from_hex("a" * 32),
            ConnectionId.from_hex("b" * 16),
            "test_token"
        )
        
        # Wait for event processing
        time.sleep(0.1)
        
        # Verify events were coordinated
        assert 'connection_started' in events_received
        assert 'connection_established' in events_received
        assert 'subscription_created' in events_received
        
    def test_module_dependency_management(self):
        """Test proper module dependency management"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        
        # Test operations before module initialization
        with pytest.raises(RuntimeError, match="Modules not initialized"):
            client.connect()
            
        with pytest.raises(RuntimeError, match="Modules not initialized"):
            client.subscribe("users", "SELECT * FROM users")
            
        # Initialize modules
        client.initialize_modules()
        
        # Now operations should work
        client.connect()
        client.subscribe("users", "SELECT * FROM users")
        
    def test_module_state_synchronization(self):
        """Test state synchronization between modules"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        
        # Test connection state synchronization
        assert client.connection_state == ConnectionState.DISCONNECTED
        assert client.authentication_handler.get_auth_status() == "unauthenticated"
        
        # Connect and authenticate
        client.connect()
        
        identity = Identity.from_hex("a" * 32)
        connection_id = ConnectionId.from_hex("b" * 16)
        identity_token = IdentityToken(
            token="identity_token_123",
            identity=identity,
            connection_id=connection_id
        )
        
        client.authentication_handler.handle_identity_token(identity_token)
        
        # Verify state synchronization
        assert client.connection_state == ConnectionState.AUTHENTICATED
        assert client.authentication_handler.get_auth_status() == "authenticated"
        assert client.authentication_handler.get_identity() == identity
        assert client.authentication_handler.get_connection_id() == connection_id
        
    def test_module_cleanup_integration(self):
        """Test proper cleanup when modules are disconnected"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        client.connect()
        
        # Create subscriptions and authenticate
        query_id1 = client.subscribe("users", "SELECT * FROM users")
        query_id2 = client.subscribe("messages", "SELECT * FROM messages")
        
        client.authentication_handler.set_identity(
            Identity.from_hex("a" * 32),
            ConnectionId.from_hex("b" * 16),
            "test_token"
        )
        
        # Verify state before cleanup
        assert client.get_subscription_count() == 2
        assert client.is_authenticated() is True
        
        # Simulate cleanup (would happen during disconnect)
        client.subscription_manager.cleanup_inactive_subscriptions(0.0)  # Clean all
        client.authentication_handler.clear_identity()
        client.event_system.clear_events()
        
        # Verify cleanup
        assert client.authentication_handler.get_auth_status() == "unauthenticated"
        assert client.authentication_handler.get_identity() is None
        assert len(client.event_system.get_events()) == 0
        
    def test_concurrent_module_operations(self):
        """Test concurrent operations across modules"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        client.connect()
        
        results = []
        errors = []
        
        def create_subscriptions():
            try:
                for i in range(10):
                    query_id = client.subscribe(f"table_{i}", f"SELECT * FROM table_{i}")
                    results.append(query_id)
            except Exception as e:
                errors.append(str(e))
                
        def emit_events():
            try:
                for i in range(10):
                    client.event_system.emit('test_event', {'index': i})
            except Exception as e:
                errors.append(str(e))
                
        def handle_auth():
            try:
                client.authentication_handler.set_auth_token("concurrent_token")
                client.authentication_handler.authenticate()
            except Exception as e:
                errors.append(str(e))
                
        # Run concurrent operations
        threads = [
            threading.Thread(target=create_subscriptions),
            threading.Thread(target=emit_events),
            threading.Thread(target=handle_auth)
        ]
        
        for thread in threads:
            thread.start()
            
        for thread in threads:
            thread.join()
            
        # Verify operations completed successfully
        assert len(errors) == 0
        assert len(results) == 10
        assert client.get_subscription_count() == 10


class TestIntegrationScenarios:
    """Test real-world integration scenarios"""
    
    def test_full_client_lifecycle_integration(self):
        """Test complete client lifecycle with all modules"""
        client = MockIntegratedWebSocketClient(
            "localhost:3000", 
            "test-db", 
            auth_token="lifecycle_token"
        )
        
        # Initialize
        client.initialize_modules()
        
        # Connect and authenticate
        client.connect()
        
        # Simulate successful authentication
        identity = Identity.from_hex("c" * 32)
        connection_id = ConnectionId.from_hex("d" * 16)
        identity_token = IdentityToken(
            token="lifecycle_identity_token",
            identity=identity,
            connection_id=connection_id
        )
        
        client.authentication_handler.handle_identity_token(identity_token)
        
        # Create subscriptions
        users_query = client.subscribe("users", "SELECT * FROM users")
        messages_query = client.subscribe("messages", "SELECT * FROM messages")
        
        # Simulate subscription applied
        client.event_system.emit('subscription_applied', {
            'query_id': users_query,
            'table_name': "users"
        })
        
        client.event_system.emit('subscription_applied', {
            'query_id': messages_query,
            'table_name': "messages"
        })
        
        # Wait for processing
        time.sleep(0.1)
        
        # Verify final state
        assert client.is_authenticated() is True
        assert client.get_subscription_count() == 2
        assert client.get_connection_state() == ConnectionState.AUTHENTICATED
        
        # Verify subscriptions are active
        users_sub = client.subscription_manager.get_subscription(users_query)
        messages_sub = client.subscription_manager.get_subscription(messages_query)
        
        assert users_sub['status'] == 'active'
        assert messages_sub['status'] == 'active'
        
        # Verify event history
        events = client.get_event_history()
        event_types = [e['type'] for e in events]
        
        assert 'connection_started' in event_types
        assert 'connection_established' in event_types
        assert 'subscription_created' in event_types
        assert 'subscription_applied' in event_types
        
    def test_error_recovery_integration(self):
        """Test error recovery across modules"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        client.connect()
        
        # Create subscription
        query_id = client.subscribe("unstable_table", "SELECT * FROM unstable_table")
        
        # Simulate subscription error
        client.event_system.emit('subscription_error', {
            'query_id': query_id,
            'error': "Connection lost"
        })
        
        # Wait for processing
        time.sleep(0.1)
        
        # Verify error handling
        subscription = client.subscription_manager.get_subscription(query_id)
        assert subscription['status'] == 'error'
        
        # Simulate recovery by re-applying subscription
        client.event_system.emit('subscription_applied', {
            'query_id': query_id,
            'table_name': "unstable_table"
        })
        
        # Wait for processing
        time.sleep(0.1)
        
        # Verify recovery
        subscription = client.subscription_manager.get_subscription(query_id)
        assert subscription['status'] == 'active'
        
    def test_module_performance_integration(self, performance_tracker):
        """Test performance characteristics of module integration"""
        client = MockIntegratedWebSocketClient("localhost:3000", "test-db")
        client.initialize_modules()
        
        # Test initialization performance
        performance_tracker.start_timing("module_initialization")
        client.initialize_modules()
        init_time = performance_tracker.stop_timing("module_initialization")
        
        # Test connection performance
        performance_tracker.start_timing("connection")
        client.connect()
        connect_time = performance_tracker.stop_timing("connection")
        
        # Test subscription performance
        performance_tracker.start_timing("subscription_creation")
        for i in range(10):
            client.subscribe(f"perf_table_{i}", f"SELECT * FROM perf_table_{i}")
        subscription_time = performance_tracker.stop_timing("subscription_creation")
        
        # Test event processing performance
        performance_tracker.start_timing("event_processing")
        for i in range(100):
            client.event_system.emit('performance_test', {'index': i})
        event_time = performance_tracker.stop_timing("event_processing")
        
        # Verify reasonable performance
        assert connect_time < 1.0  # Connection should be fast
        assert subscription_time < 1.0  # Subscription creation should be fast
        assert event_time < 1.0  # Event processing should be fast
        
        # Check that module integration doesn't significantly impact performance
        assert client.get_subscription_count() == 10
        assert len(client.get_event_history()) >= 100