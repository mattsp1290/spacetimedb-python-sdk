"""
Mock infrastructure for Phase 2 refactoring tests

This module provides comprehensive mock servers, fixtures, and test data
for testing the refactored modules in isolation and integration.
"""
import json
import time
import uuid
import queue
import threading
import websocket
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from unittest.mock import Mock, MagicMock

from spacetimedb_sdk.protocol import (
    Identity, ConnectionId, QueryId,
    IdentityToken, Subscribe, Unsubscribe, OneOffQuery,
    TransactionUpdate, SubscriptionError, SubscriptionApplied,
    CallReducer, CallReducerFlags
)


class MockServerBehavior(Enum):
    """Server behavior modes for testing"""
    NORMAL = "normal"
    SLOW_RESPONSE = "slow_response"
    INTERMITTENT_ERRORS = "intermittent_errors"
    AUTHENTICATION_FAILURES = "auth_failures"
    CONNECTION_DROPS = "connection_drops"
    PROTOCOL_ERRORS = "protocol_errors"
    MEMORY_PRESSURE = "memory_pressure"


@dataclass
class MockServerConfig:
    """Configuration for mock server behavior"""
    behavior: MockServerBehavior = MockServerBehavior.NORMAL
    response_delay: float = 0.0
    error_rate: float = 0.0
    auth_failure_rate: float = 0.0
    connection_drop_rate: float = 0.0
    max_message_size: int = 1024 * 1024  # 1MB
    max_subscriptions: int = 100
    heartbeat_interval: float = 30.0
    protocol_version: str = "v1.1.2"
    supported_protocols: List[str] = field(default_factory=lambda: ["text", "binary"])


@dataclass
class MockMessage:
    """Mock message structure"""
    message_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    binary: bool = False


class MockSpacetimeDBServer:
    """Comprehensive mock SpacetimeDB server for testing"""
    
    def __init__(self, config: Optional[MockServerConfig] = None):
        self.config = config or MockServerConfig()
        self.clients: List['MockWebSocketConnection'] = []
        self.databases: Dict[str, Dict[str, Any]] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.running = False
        self.server_thread: Optional[threading.Thread] = None
        self.message_queue: queue.Queue = queue.Queue()
        self.metrics = {
            'connections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0,
            'authentications': 0
        }
        self.logger = logging.getLogger(__name__)
        
        # Set up default message handlers
        self._setup_default_handlers()
        
    def _setup_default_handlers(self):
        """Set up default message handlers"""
        self.message_handlers = {
            'Subscribe': self._handle_subscribe,
            'Unsubscribe': self._handle_unsubscribe,
            'CallReducer': self._handle_call_reducer,
            'OneOffQuery': self._handle_one_off_query,
            'Authenticate': self._handle_authenticate
        }
        
    def start(self):
        """Start the mock server"""
        if self.running:
            return
            
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
    def stop(self):
        """Stop the mock server"""
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=1.0)
            
    def add_database(self, address: str, schema: Dict[str, Any], published: bool = True):
        """Add a database to the server"""
        self.databases[address] = {
            'schema': schema,
            'published': published,
            'tables': {},
            'subscriptions': {},
            'reducers': {}
        }
        
    def create_client_connection(self, database_address: str) -> 'MockWebSocketConnection':
        """Create a new client connection"""
        if database_address not in self.databases:
            raise ValueError(f"Database {database_address} not found")
            
        connection = MockWebSocketConnection(self, database_address)
        self.clients.append(connection)
        self.metrics['connections'] += 1
        
        return connection
        
    def _run_server(self):
        """Main server loop"""
        while self.running:
            try:
                # Process message queue
                try:
                    message, client = self.message_queue.get(timeout=0.1)
                    self._process_message(message, client)
                    self.message_queue.task_done()
                except queue.Empty:
                    continue
                    
                # Simulate heartbeat
                if self.config.heartbeat_interval > 0:
                    self._send_heartbeat()
                    
                time.sleep(0.01)  # Small delay to prevent busy waiting
                
            except Exception as e:
                self.logger.error(f"Server error: {e}")
                self.metrics['errors'] += 1
                
    def _process_message(self, message: MockMessage, client: 'MockWebSocketConnection'):
        """Process a message from a client"""
        self.metrics['messages_received'] += 1
        
        # Apply behavior modifications
        if self.config.behavior == MockServerBehavior.SLOW_RESPONSE:
            time.sleep(self.config.response_delay)
        elif self.config.behavior == MockServerBehavior.INTERMITTENT_ERRORS:
            if time.time() % 10 < self.config.error_rate * 10:
                client.send_error("Simulated server error")
                return
                
        # Handle the message
        handler = self.message_handlers.get(message.message_type)
        if handler:
            try:
                handler(message, client)
            except Exception as e:
                self.logger.error(f"Handler error for {message.message_type}: {e}")
                client.send_error(f"Handler error: {e}")
        else:
            client.send_error(f"Unknown message type: {message.message_type}")
            
    def _handle_subscribe(self, message: MockMessage, client: 'MockWebSocketConnection'):
        """Handle subscription message"""
        data = message.data
        query_id = data.get('query_id', str(uuid.uuid4()))
        table_name = data.get('table_name')
        sql_query = data.get('sql_query')
        
        if not table_name or not sql_query:
            client.send_error("Missing table_name or sql_query")
            return
            
        # Check subscription limits
        if len(client.subscriptions) >= self.config.max_subscriptions:
            client.send_subscription_error(query_id, "Subscription limit exceeded")
            return
            
        # Add subscription
        client.subscriptions[query_id] = {
            'table_name': table_name,
            'sql_query': sql_query,
            'created_at': time.time()
        }
        
        # Send subscription applied
        client.send_subscription_applied(query_id, table_name)
        
        # Send initial data
        initial_data = self._get_table_data(client.database_address, table_name)
        if initial_data:
            client.send_subscription_data(table_name, initial_data)
            
    def _handle_unsubscribe(self, message: MockMessage, client: 'MockWebSocketConnection'):
        """Handle unsubscribe message"""
        data = message.data
        query_id = data.get('query_id')
        
        if query_id in client.subscriptions:
            del client.subscriptions[query_id]
            client.send_unsubscribe_applied(query_id)
        else:
            client.send_error(f"Subscription {query_id} not found")
            
    def _handle_call_reducer(self, message: MockMessage, client: 'MockWebSocketConnection'):
        """Handle call reducer message"""
        data = message.data
        reducer_name = data.get('reducer_name')
        args = data.get('args', {})
        call_id = data.get('call_id', str(uuid.uuid4()))
        
        # Simulate reducer execution
        result = self._execute_reducer(client.database_address, reducer_name, args)
        client.send_reducer_result(call_id, result)
        
    def _handle_one_off_query(self, message: MockMessage, client: 'MockWebSocketConnection'):
        """Handle one-off query message"""
        data = message.data
        sql_query = data.get('sql_query')
        query_id = data.get('query_id', str(uuid.uuid4()))
        
        # Simulate query execution
        result = self._execute_query(client.database_address, sql_query)
        client.send_query_result(query_id, result)
        
    def _handle_authenticate(self, message: MockMessage, client: 'MockWebSocketConnection'):
        """Handle authentication message"""
        data = message.data
        token = data.get('token')
        
        if self.config.behavior == MockServerBehavior.AUTHENTICATION_FAILURES:
            if time.time() % 10 < self.config.auth_failure_rate * 10:
                client.send_error("Authentication failed")
                return
                
        # Generate identity
        identity = Identity.from_hex(str(uuid.uuid4()).replace('-', '')[:32])
        connection_id = ConnectionId.from_hex(str(uuid.uuid4()).replace('-', '')[:16])
        
        client.identity = identity
        client.connection_id = connection_id
        client.authenticated = True
        
        # Send identity token
        client.send_identity_token(token or "server_generated_token", identity, connection_id)
        self.metrics['authentications'] += 1
        
    def _get_table_data(self, database_address: str, table_name: str) -> List[Dict[str, Any]]:
        """Get data for a table"""
        database = self.databases.get(database_address, {})
        tables = database.get('tables', {})
        return tables.get(table_name, [])
        
    def _execute_reducer(self, database_address: str, reducer_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate reducer execution"""
        return {
            'success': True,
            'reducer': reducer_name,
            'args': args,
            'timestamp': time.time()
        }
        
    def _execute_query(self, database_address: str, sql_query: str) -> List[Dict[str, Any]]:
        """Simulate query execution"""
        # Simple mock query result
        return [
            {'id': 1, 'data': f'Result for: {sql_query}', 'timestamp': time.time()}
        ]
        
    def _send_heartbeat(self):
        """Send heartbeat to all connected clients"""
        for client in self.clients:
            if client.connected:
                client.send_heartbeat()
                
    def add_table_data(self, database_address: str, table_name: str, data: List[Dict[str, Any]]):
        """Add data to a table"""
        if database_address not in self.databases:
            return
            
        database = self.databases[database_address]
        if 'tables' not in database:
            database['tables'] = {}
            
        database['tables'][table_name] = data
        
        # Notify subscribers
        for client in self.clients:
            if client.database_address == database_address:
                for query_id, subscription in client.subscriptions.items():
                    if subscription['table_name'] == table_name:
                        client.send_subscription_data(table_name, data)
                        
    def get_metrics(self) -> Dict[str, Any]:
        """Get server metrics"""
        return self.metrics.copy()


class MockWebSocketConnection:
    """Mock WebSocket connection for a client"""
    
    def __init__(self, server: MockSpacetimeDBServer, database_address: str):
        self.server = server
        self.database_address = database_address
        self.connected = False
        self.authenticated = False
        self.identity: Optional[Identity] = None
        self.connection_id: Optional[ConnectionId] = None
        self.subscriptions: Dict[str, Dict[str, Any]] = {}
        self.sent_messages: List[MockMessage] = []
        self.callbacks = {
            'on_open': None,
            'on_message': None,
            'on_error': None,
            'on_close': None
        }
        
    def connect(self, on_open=None, on_message=None, on_error=None, on_close=None):
        """Connect to the server"""
        self.callbacks.update({
            'on_open': on_open,
            'on_message': on_message,
            'on_error': on_error,
            'on_close': on_close
        })
        
        # Check if database exists and is published
        database = self.server.databases.get(self.database_address)
        if not database:
            if on_error:
                on_error(Exception("Database not found"))
            return
            
        if not database.get('published', True):
            if on_error:
                on_error(Exception("Database not published"))
            return
            
        self.connected = True
        if on_open:
            on_open()
            
        # Auto-authenticate if enabled
        if self.server.config.behavior != MockServerBehavior.AUTHENTICATION_FAILURES:
            self._auto_authenticate()
            
    def disconnect(self):
        """Disconnect from the server"""
        self.connected = False
        self.authenticated = False
        if self.callbacks['on_close']:
            self.callbacks['on_close'](None, None)
            
        if self in self.server.clients:
            self.server.clients.remove(self)
            
    def send_message(self, message_type: str, data: Dict[str, Any]):
        """Send a message to the server"""
        if not self.connected:
            raise Exception("Not connected")
            
        message = MockMessage(message_type, data)
        self.sent_messages.append(message)
        self.server.message_queue.put((message, self))
        
    def _auto_authenticate(self):
        """Auto-authenticate the connection"""
        self.send_message('Authenticate', {'token': 'auto_token'})
        
    def send_identity_token(self, token: str, identity: Identity, connection_id: ConnectionId):
        """Send identity token to client"""
        self._send_to_client('IdentityToken', {
            'token': token,
            'identity': str(identity),
            'connection_id': str(connection_id)
        })
        
    def send_subscription_applied(self, query_id: str, table_name: str):
        """Send subscription applied to client"""
        self._send_to_client('SubscriptionApplied', {
            'query_id': query_id,
            'table_name': table_name
        })
        
    def send_subscription_error(self, query_id: str, error: str):
        """Send subscription error to client"""
        self._send_to_client('SubscriptionError', {
            'query_id': query_id,
            'error': error
        })
        
    def send_subscription_data(self, table_name: str, data: List[Dict[str, Any]]):
        """Send subscription data to client"""
        self._send_to_client('TransactionUpdate', {
            'table_name': table_name,
            'data': data
        })
        
    def send_unsubscribe_applied(self, query_id: str):
        """Send unsubscribe applied to client"""
        self._send_to_client('UnsubscribeApplied', {
            'query_id': query_id
        })
        
    def send_reducer_result(self, call_id: str, result: Dict[str, Any]):
        """Send reducer result to client"""
        self._send_to_client('CallReducerResult', {
            'call_id': call_id,
            'result': result
        })
        
    def send_query_result(self, query_id: str, result: List[Dict[str, Any]]):
        """Send query result to client"""
        self._send_to_client('OneOffQueryResult', {
            'query_id': query_id,
            'result': result
        })
        
    def send_error(self, error: str):
        """Send error to client"""
        self._send_to_client('Error', {'error': error})
        
    def send_heartbeat(self):
        """Send heartbeat to client"""
        self._send_to_client('Heartbeat', {'timestamp': time.time()})
        
    def _send_to_client(self, message_type: str, data: Dict[str, Any]):
        """Send a message to the client"""
        if self.callbacks['on_message']:
            message = {message_type: data}
            self.callbacks['on_message'](json.dumps(message))
            
        self.server.metrics['messages_sent'] += 1


class TestDataGenerator:
    """Generate test data for various scenarios"""
    
    @staticmethod
    def generate_user_data(count: int = 10) -> List[Dict[str, Any]]:
        """Generate user test data"""
        users = []
        for i in range(count):
            users.append({
                'id': i + 1,
                'name': f'User_{i+1}',
                'email': f'user{i+1}@example.com',
                'created_at': time.time() - (count - i) * 3600,
                'active': i % 2 == 0
            })
        return users
        
    @staticmethod
    def generate_message_data(count: int = 20) -> List[Dict[str, Any]]:
        """Generate message test data"""
        messages = []
        for i in range(count):
            messages.append({
                'id': i + 1,
                'user_id': (i % 10) + 1,
                'content': f'Message content {i+1}',
                'timestamp': time.time() - (count - i) * 60,
                'channel': f'channel_{(i % 3) + 1}'
            })
        return messages
        
    @staticmethod
    def generate_large_dataset(table_name: str, count: int = 1000) -> List[Dict[str, Any]]:
        """Generate large dataset for performance testing"""
        data = []
        for i in range(count):
            data.append({
                'id': i + 1,
                'table': table_name,
                'data': f'Large data entry {i+1}' * 10,  # Make it larger
                'timestamp': time.time() - (count - i),
                'index': i,
                'active': i % 2 == 0,
                'category': f'category_{i % 5}',
                'metadata': {
                    'extra_field_1': f'extra_{i}',
                    'extra_field_2': i * 2,
                    'extra_field_3': [i, i+1, i+2]
                }
            })
        return data
        
    @staticmethod
    def generate_schema(table_names: List[str]) -> Dict[str, Any]:
        """Generate a database schema"""
        schema = {'tables': {}}
        
        for table_name in table_names:
            if table_name == 'users':
                schema['tables'][table_name] = {
                    'columns': [
                        {'name': 'id', 'type': 'int', 'primary_key': True},
                        {'name': 'name', 'type': 'string'},
                        {'name': 'email', 'type': 'string'},
                        {'name': 'created_at', 'type': 'timestamp'},
                        {'name': 'active', 'type': 'boolean'}
                    ]
                }
            elif table_name == 'messages':
                schema['tables'][table_name] = {
                    'columns': [
                        {'name': 'id', 'type': 'int', 'primary_key': True},
                        {'name': 'user_id', 'type': 'int'},
                        {'name': 'content', 'type': 'string'},
                        {'name': 'timestamp', 'type': 'timestamp'},
                        {'name': 'channel', 'type': 'string'}
                    ]
                }
            else:
                # Generic table schema
                schema['tables'][table_name] = {
                    'columns': [
                        {'name': 'id', 'type': 'int', 'primary_key': True},
                        {'name': 'data', 'type': 'string'},
                        {'name': 'timestamp', 'type': 'timestamp'}
                    ]
                }
                
        return schema


class MockWebSocketAppFactory:
    """Factory for creating mock WebSocket apps"""
    
    def __init__(self, server: MockSpacetimeDBServer):
        self.server = server
        
    def create_websocket_app(self, url: str, **kwargs) -> Mock:
        """Create a mock WebSocket app that connects to our mock server"""
        # Extract database address from URL
        database_address = self._extract_database_address(url)
        
        # Create mock app
        mock_app = Mock()
        mock_app.url = url
        
        # Store callbacks
        for key in ['on_open', 'on_message', 'on_error', 'on_close']:
            setattr(mock_app, key, kwargs.get(key))
            
        # Create connection
        connection = self.server.create_client_connection(database_address)
        mock_app._connection = connection
        
        # Mock run_forever
        def run_forever():
            connection.connect(
                on_open=mock_app.on_open,
                on_message=mock_app.on_message,
                on_error=mock_app.on_error,
                on_close=mock_app.on_close
            )
            
        mock_app.run_forever = run_forever
        
        # Mock send
        def send(data):
            try:
                message_data = json.loads(data)
                for message_type, content in message_data.items():
                    connection.send_message(message_type, content)
            except Exception as e:
                if mock_app.on_error:
                    mock_app.on_error(e)
                    
        mock_app.send = send
        
        # Mock close
        def close():
            connection.disconnect()
            
        mock_app.close = close
        
        return mock_app
        
    def _extract_database_address(self, url: str) -> str:
        """Extract database address from WebSocket URL"""
        # Simple extraction for mock purposes
        if '/database/' in url:
            parts = url.split('/database/')
            if len(parts) > 1:
                return parts[1].split('/')[0]
        return 'default-db'


# Test fixtures and utilities
def create_test_server(behavior: MockServerBehavior = MockServerBehavior.NORMAL) -> MockSpacetimeDBServer:
    """Create a test server with default configuration"""
    config = MockServerConfig(behavior=behavior)
    server = MockSpacetimeDBServer(config)
    
    # Add default test database
    schema = TestDataGenerator.generate_schema(['users', 'messages'])
    server.add_database('test-db', schema)
    
    # Add test data
    server.add_table_data('test-db', 'users', TestDataGenerator.generate_user_data())
    server.add_table_data('test-db', 'messages', TestDataGenerator.generate_message_data())
    
    return server


def create_slow_server() -> MockSpacetimeDBServer:
    """Create a server that responds slowly"""
    config = MockServerConfig(
        behavior=MockServerBehavior.SLOW_RESPONSE,
        response_delay=0.5
    )
    return MockSpacetimeDBServer(config)


def create_unreliable_server() -> MockSpacetimeDBServer:
    """Create an unreliable server for testing error handling"""
    config = MockServerConfig(
        behavior=MockServerBehavior.INTERMITTENT_ERRORS,
        error_rate=0.3
    )
    return MockSpacetimeDBServer(config)


def create_auth_failing_server() -> MockSpacetimeDBServer:
    """Create a server that frequently fails authentication"""
    config = MockServerConfig(
        behavior=MockServerBehavior.AUTHENTICATION_FAILURES,
        auth_failure_rate=0.5
    )
    return MockSpacetimeDBServer(config)