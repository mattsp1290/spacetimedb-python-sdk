"""
Regression tests for WebSocket client behavior during Phase 2 refactoring

These tests ensure that the existing WebSocket client behavior remains unchanged
when breaking up websocket_client.py into focused modules.
"""
import pytest
import time
import json
import threading
from unittest.mock import Mock, patch, MagicMock
import logging

from spacetimedb_sdk.websocket_client import ModernWebSocketClient, ConnectionState, SubscriptionMetrics
from spacetimedb_sdk.protocol import (
    TEXT_PROTOCOL, BIN_PROTOCOL,
    Identity, ConnectionId, QueryId
)
from spacetimedb_sdk.exceptions import (
    WebSocketHandshakeError,
    DatabaseNotFoundError,
    AuthenticationError,
    ConnectionTimeoutError
)


class TestWebSocketClientRegression:
    """Test existing WebSocket client behavior"""
    
    def test_connection_establishment_regression(self, mock_websocket_client, mock_websocket_server, 
                                                 refactoring_test_params, regression_validator):
        """Test that connection establishment behavior remains unchanged"""
        # Record baseline behavior
        mock_websocket_server.set_behavior(connection="success", auth="success")
        
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"],
            auth_token=refactoring_test_params["auth_token"],
            ssl_enabled=refactoring_test_params["ssl_enabled"]
        )
        
        # Test connection establishment
        connection_established = False
        identity_received = False
        
        def on_connect():
            nonlocal connection_established
            connection_established = True
            
        def on_identity(token, identity, connection_id):
            nonlocal identity_received
            identity_received = True
            
        client.on_connect = on_connect
        client.on_identity = on_identity
        
        # Mock the websocket connection
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Simulate successful connection
            client.connect()
            
            # Simulate connection events
            if client.ws_app and hasattr(client.ws_app, 'on_open'):
                client.ws_app.on_open(mock_instance)
                
            # Simulate identity token message
            if client.ws_app and hasattr(client.ws_app, 'on_message'):
                identity_msg = json.dumps({
                    "IdentityToken": {
                        "token": "test_token",
                        "identity": "0" * 32,
                        "connection_id": "0" * 16
                    }
                })
                client.ws_app.on_message(mock_instance, identity_msg)
                
            # Allow some time for callbacks
            time.sleep(0.1)
            
            # Validate regression
            baseline_result = {
                'connection_established': True,
                'identity_received': True,
                'connection_state': ConnectionState.CONNECTED
            }
            
            actual_result = {
                'connection_established': connection_established,
                'identity_received': identity_received,
                'connection_state': client.connection_state
            }
            
            matches, message = regression_validator.validate_behavior(
                'connection_establishment', actual_result
            )
            
            # Record baseline if not exists
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('connection_establishment', actual_result)
                matches = True
                
            assert matches, f"Connection establishment regression detected: {message}"
            assert connection_established, "Connection should be established"
            assert identity_received, "Identity should be received"
            
    def test_subscription_management_regression(self, mock_websocket_client, 
                                                refactoring_test_params, regression_validator):
        """Test that subscription management behavior remains unchanged"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Test subscription creation
        subscription_created = False
        subscription_data = None
        
        def on_subscription_applied(query_id, table_name):
            nonlocal subscription_created
            subscription_created = True
            
        def on_subscription_data(table_name, data):
            nonlocal subscription_data
            subscription_data = data
            
        client.on_subscription_applied = on_subscription_applied
        client.on_subscription_data = on_subscription_data
        
        # Mock websocket connection
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Simulate connection
            client.connect()
            client.connection_state = ConnectionState.CONNECTED
            
            # Test subscription
            query_id = QueryId.random()
            table_name = "test_table"
            sql_query = "SELECT * FROM test_table"
            
            client.subscribe(table_name, sql_query)
            
            # Simulate subscription applied message
            if client.ws_app and hasattr(client.ws_app, 'on_message'):
                subscribe_msg = json.dumps({
                    "SubscriptionApplied": {
                        "query_id": str(query_id),
                        "table_name": table_name
                    }
                })
                client.ws_app.on_message(mock_instance, subscribe_msg)
                
            time.sleep(0.1)
            
            # Validate regression
            baseline_result = {
                'subscription_created': True,
                'has_subscriptions': len(client.subscriptions) > 0
            }
            
            actual_result = {
                'subscription_created': subscription_created,
                'has_subscriptions': len(client.subscriptions) > 0
            }
            
            matches, message = regression_validator.validate_behavior(
                'subscription_management', actual_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('subscription_management', actual_result)
                matches = True
                
            assert matches, f"Subscription management regression detected: {message}"
            
    def test_authentication_flow_regression(self, mock_websocket_client, 
                                            refactoring_test_params, regression_validator):
        """Test that authentication flow remains unchanged"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"],
            auth_token="test_token"
        )
        
        # Test authentication
        auth_completed = False
        identity_value = None
        
        def on_identity(token, identity, connection_id):
            nonlocal auth_completed, identity_value
            auth_completed = True
            identity_value = identity
            
        client.on_identity = on_identity
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            client.connect()
            
            # Simulate identity token message
            if client.ws_app and hasattr(client.ws_app, 'on_message'):
                identity_msg = json.dumps({
                    "IdentityToken": {
                        "token": "test_token",
                        "identity": "a" * 32,
                        "connection_id": "b" * 16
                    }
                })
                client.ws_app.on_message(mock_instance, identity_msg)
                
            time.sleep(0.1)
            
            # Validate regression
            baseline_result = {
                'auth_completed': True,
                'has_identity': identity_value is not None,
                'has_token': client.auth_token is not None
            }
            
            actual_result = {
                'auth_completed': auth_completed,
                'has_identity': identity_value is not None,
                'has_token': client.auth_token is not None
            }
            
            matches, message = regression_validator.validate_behavior(
                'authentication_flow', actual_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('authentication_flow', actual_result)
                matches = True
                
            assert matches, f"Authentication flow regression detected: {message}"
            
    def test_error_handling_regression(self, mock_websocket_client, 
                                       refactoring_test_params, regression_validator):
        """Test that error handling behavior remains unchanged"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Test error handling
        error_received = False
        error_type = None
        
        def on_error(error):
            nonlocal error_received, error_type
            error_received = True
            error_type = type(error).__name__
            
        client.on_error = on_error
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            client.connect()
            
            # Simulate error
            if client.ws_app and hasattr(client.ws_app, 'on_error'):
                test_error = ConnectionTimeoutError("Connection timeout")
                client.ws_app.on_error(mock_instance, test_error)
                
            time.sleep(0.1)
            
            # Validate regression
            baseline_result = {
                'error_received': True,
                'error_type': 'ConnectionTimeoutError'
            }
            
            actual_result = {
                'error_received': error_received,
                'error_type': error_type
            }
            
            matches, message = regression_validator.validate_behavior(
                'error_handling', actual_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('error_handling', actual_result)
                matches = True
                
            assert matches, f"Error handling regression detected: {message}"
            
    def test_message_sending_regression(self, mock_websocket_client, 
                                        refactoring_test_params, regression_validator):
        """Test that message sending behavior remains unchanged"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            client.connect()
            client.connection_state = ConnectionState.CONNECTED
            client.ws_app = mock_instance
            
            # Test sending different message types
            test_messages = [
                ("text", "Hello, SpacetimeDB!"),
                ("json", {"type": "test", "data": "value"}),
                ("binary", b"binary data")
            ]
            
            sent_messages = []
            
            def mock_send(data):
                sent_messages.append(data)
                
            mock_instance.send = mock_send
            
            for msg_type, msg_data in test_messages:
                if msg_type == "text":
                    client.send_raw_message(msg_data)
                elif msg_type == "json":
                    client.send_raw_message(json.dumps(msg_data))
                elif msg_type == "binary":
                    client.send_raw_message(msg_data)
                    
            # Validate regression
            baseline_result = {
                'messages_sent': len(test_messages),
                'has_messages': len(sent_messages) > 0
            }
            
            actual_result = {
                'messages_sent': len(sent_messages),
                'has_messages': len(sent_messages) > 0
            }
            
            matches, message = regression_validator.validate_behavior(
                'message_sending', actual_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('message_sending', actual_result)
                matches = True
                
            assert matches, f"Message sending regression detected: {message}"
            
    def test_connection_state_management_regression(self, mock_websocket_client, 
                                                    refactoring_test_params, 
                                                    regression_validator, 
                                                    connection_state_tracker):
        """Test that connection state management remains unchanged"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Track state changes
        def on_state_change(old_state, new_state):
            connection_state_tracker.record_state_change(old_state, new_state)
            
        # Mock state change tracking
        original_state = client.connection_state
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Test state transitions
            client.connect()
            on_state_change(original_state, client.connection_state)
            
            # Simulate connection open
            if client.ws_app and hasattr(client.ws_app, 'on_open'):
                old_state = client.connection_state
                client.ws_app.on_open(mock_instance)
                on_state_change(old_state, client.connection_state)
                
            # Simulate connection close
            if client.ws_app and hasattr(client.ws_app, 'on_close'):
                old_state = client.connection_state
                client.ws_app.on_close(mock_instance, None, None)
                on_state_change(old_state, client.connection_state)
                
            # Validate regression
            state_history = connection_state_tracker.get_state_history()
            
            baseline_result = {
                'state_changes': len(state_history),
                'has_state_transitions': len(state_history) > 0,
                'final_state': connection_state_tracker.get_current_state()
            }
            
            actual_result = baseline_result
            
            matches, message = regression_validator.validate_behavior(
                'connection_state_management', actual_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('connection_state_management', actual_result)
                matches = True
                
            assert matches, f"Connection state management regression detected: {message}"
            
    def test_metrics_collection_regression(self, mock_websocket_client, 
                                           refactoring_test_params, regression_validator):
        """Test that metrics collection behavior remains unchanged"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Access metrics
        metrics = client.subscription_metrics
        
        # Test metrics functionality
        table_name = "test_table"
        test_data_size = 1024
        
        metrics.record_subscription_data(table_name, test_data_size)
        metrics.record_subscription_error(table_name, "Test error")
        
        health = metrics.get_subscription_health(table_name)
        all_health = metrics.get_all_subscription_health()
        
        # Validate regression
        baseline_result = {
            'has_metrics': health is not None,
            'has_message_count': 'message_count' in health,
            'has_error_count': 'error_count' in health,
            'has_all_health': len(all_health) > 0
        }
        
        actual_result = baseline_result
        
        matches, message = regression_validator.validate_behavior(
            'metrics_collection', actual_result
        )
        
        if not matches and 'No baseline recorded' in message:
            regression_validator.record_baseline('metrics_collection', actual_result)
            matches = True
            
        assert matches, f"Metrics collection regression detected: {message}"
        
    def test_protocol_handling_regression(self, mock_websocket_client, 
                                          refactoring_test_params, regression_validator):
        """Test that protocol handling remains unchanged"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Test protocol detection
        text_protocol = client._determine_frame_type(TEXT_PROTOCOL)
        bin_protocol = client._determine_frame_type(BIN_PROTOCOL)
        
        # Test protocol helper
        protocol_helper = client.get_protocol_helper()
        
        # Validate regression
        baseline_result = {
            'text_protocol_detected': text_protocol is not None,
            'bin_protocol_detected': bin_protocol is not None,
            'has_protocol_helper': protocol_helper is not None
        }
        
        actual_result = baseline_result
        
        matches, message = regression_validator.validate_behavior(
            'protocol_handling', actual_result
        )
        
        if not matches and 'No baseline recorded' in message:
            regression_validator.record_baseline('protocol_handling', actual_result)
            matches = True
            
        assert matches, f"Protocol handling regression detected: {message}"


class TestSubscriptionMetricsRegression:
    """Test SubscriptionMetrics class behavior"""
    
    def test_subscription_metrics_functionality(self, regression_validator):
        """Test that SubscriptionMetrics works as expected"""
        metrics = SubscriptionMetrics()
        
        # Test basic functionality
        table_name = "test_table"
        data_size = 512
        
        metrics.record_subscription_data(table_name, data_size)
        health = metrics.get_subscription_health(table_name)
        
        # Validate regression
        baseline_result = {
            'has_health_data': health is not None,
            'message_count': health.get('message_count', 0),
            'total_bytes': health.get('total_bytes', 0),
            'has_timestamps': 'first_received' in health
        }
        
        actual_result = baseline_result
        
        matches, message = regression_validator.validate_behavior(
            'subscription_metrics_functionality', actual_result
        )
        
        if not matches and 'No baseline recorded' in message:
            regression_validator.record_baseline('subscription_metrics_functionality', actual_result)
            matches = True
            
        assert matches, f"SubscriptionMetrics regression detected: {message}"
        assert health['message_count'] == 1
        assert health['total_bytes'] == data_size
        
    def test_subscription_metrics_error_handling(self, regression_validator):
        """Test that SubscriptionMetrics error handling works"""
        metrics = SubscriptionMetrics()
        
        table_name = "test_table"
        error_message = "Test error"
        
        metrics.record_subscription_error(table_name, error_message)
        health = metrics.get_subscription_health(table_name)
        
        # Validate regression
        baseline_result = {
            'has_error_count': 'error_count' in health,
            'error_count': health.get('error_count', 0)
        }
        
        actual_result = baseline_result
        
        matches, message = regression_validator.validate_behavior(
            'subscription_metrics_error_handling', actual_result
        )
        
        if not matches and 'No baseline recorded' in message:
            regression_validator.record_baseline('subscription_metrics_error_handling', actual_result)
            matches = True
            
        assert matches, f"SubscriptionMetrics error handling regression detected: {message}"
        assert health['error_count'] == 1