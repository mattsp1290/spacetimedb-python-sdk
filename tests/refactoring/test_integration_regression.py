"""
End-to-end integration regression tests for Phase 2 refactoring

These tests ensure that the complete integration behavior remains unchanged
when websocket_client.py is broken up into focused modules.
"""
import pytest
import time
import json
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional, List

from spacetimedb_sdk.websocket_client import WebSocketClient, ConnectionState


class TestIntegrationRegression:
    """Test end-to-end integration behavior"""
    
    def test_complete_connection_flow_regression(self, mock_websocket_client, 
                                                  refactoring_test_params, 
                                                  regression_validator):
        """Test complete connection flow remains unchanged"""
        # Track the complete flow
        flow_events = []
        
        def track_event(event_name):
            flow_events.append((event_name, time.time()))
            
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"],
            auth_token="test_token"
        )
        
        # Set up tracking callbacks
        def on_connect():
            track_event("connected")
            
        def on_identity(token, identity, connection_id):
            track_event("identity_received")
            
        def on_subscription_applied(query_id, table_name):
            track_event("subscription_applied")
            
        def on_subscription_data(table_name, data):
            track_event("subscription_data")
            
        client.on_connect = on_connect
        client.on_identity = on_identity
        client.on_subscription_applied = on_subscription_applied
        client.on_subscription_data = on_subscription_data
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Execute complete flow
            client.connect()
            
            # Simulate connection events by calling both ConnectionManager and client callbacks
            # First set up the mock connection in ConnectionManager
            client._connection_manager._connection = mock_instance
            # Then update ConnectionManager state to CONNECTED
            client._connection_manager._on_ws_open(mock_instance)
            # Finally sync WebSocketClient state
            client._on_ws_open(mock_instance)
                
            # Simulate identity token by calling the client's message callback directly
            identity_msg = json.dumps({
                "IdentityToken": {
                    "token": "test_identity_token",
                    "identity": "a" * 32,
                    "connection_id": "b" * 16
                }
            })
            client._on_ws_message(mock_instance, identity_msg)
                
            # Subscribe to table
            client.subscribe("users", "SELECT * FROM users")
            
            # Simulate subscription applied by calling the client's message callback directly
            sub_msg = json.dumps({
                "SubscriptionApplied": {
                    "query_id": "test_query_id",
                    "table_name": "users"
                }
            })
            client._on_ws_message(mock_instance, sub_msg)
                
            # Simulate subscription data by calling the client's message callback directly
            data_msg = json.dumps({
                "TransactionUpdate": {
                    "table_name": "users",
                    "data": [{"id": 1, "name": "Alice"}]
                }
            })
            client._on_ws_message(mock_instance, data_msg)
                
            time.sleep(0.1)
            
            # Validate complete flow regression
            expected_events = ["connected", "identity_received", "subscription_applied"]
            actual_events = [event[0] for event in flow_events]
            
            baseline_result = {
                'flow_completed': len(actual_events) >= 3,
                'has_connection': "connected" in actual_events,
                'has_identity': "identity_received" in actual_events,
                'has_subscription': "subscription_applied" in actual_events,
                'connection_state': client.connection_state
            }
            
            matches, message = regression_validator.validate_behavior(
                'complete_connection_flow', baseline_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('complete_connection_flow', baseline_result)
                matches = True
                
            assert matches, f"Complete connection flow regression detected: {message}"
            assert "connected" in actual_events
            assert "identity_received" in actual_events
            
    def test_multi_subscription_management_regression(self, mock_websocket_client,
                                                      refactoring_test_params,
                                                      regression_validator):
        """Test multi-subscription management remains unchanged"""
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Track subscription events
        subscription_events = []
        
        def on_subscription_applied(query_id, table_name):
            subscription_events.append(('applied', query_id, table_name))
            
        def on_subscription_data(table_name, data):
            subscription_events.append(('data', table_name, data))
            
        client.on_subscription_applied = on_subscription_applied
        client.on_subscription_data = on_subscription_data
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            client.connect()
            client.connection_state = ConnectionState.CONNECTED
            
            # Create multiple subscriptions
            tables = ["users", "messages", "logs", "settings"]
            queries = [f"SELECT * FROM {table}" for table in tables]
            
            subscription_ids = []
            for table, query in zip(tables, queries):
                query_id = client.subscribe(table, query)
                subscription_ids.append(query_id)
                
            # Simulate subscription applied for all with better timing
            if hasattr(client.ws_app, 'on_message'):
                for i, table in enumerate(tables):
                    sub_msg = json.dumps({
                        "SubscriptionApplied": {
                            "query_id": f"query_id_{i}",
                            "table_name": table
                        }
                    })
                    client.ws_app.on_message(mock_instance, sub_msg)
                    # Small delay between messages for processing
                    time.sleep(0.01)
                    
            # Longer delay for all events to be processed
            time.sleep(0.3)
            
            # Validate multi-subscription regression
            baseline_result = {
                'subscription_count': len(client.subscriptions),
                'applied_events': len([e for e in subscription_events if e[0] == 'applied']),
                'subscribed_tables': len(set(e[2] for e in subscription_events if e[0] == 'applied'))
            }
            
            matches, message = regression_validator.validate_behavior(
                'multi_subscription_management', baseline_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('multi_subscription_management', baseline_result)
                matches = True
                
            assert matches, f"Multi-subscription management regression detected: {message}"
            assert len(client.subscriptions) >= len(tables)
            
    def test_error_handling_and_recovery_regression(self, mock_websocket_client,
                                                    refactoring_test_params,
                                                    regression_validator):
        """Test error handling and recovery remains unchanged"""
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Track errors and recovery
        error_events = []
        recovery_events = []
        
        def on_error(error):
            error_events.append(error)
            
        def on_subscription_error(query_id, error):
            error_events.append(f"Subscription error: {error}")
            
        def on_connect():
            recovery_events.append("reconnected")
            
        client.on_error = on_error
        client.on_subscription_error = on_subscription_error
        client.on_connect = on_connect
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            client.connect()
            client.connection_state = ConnectionState.CONNECTED
            
            # Simulate various errors
            errors_to_simulate = [
                ("WebSocketException", "Connection lost"),
                ("SubscriptionError", "Table not found"),
                ("AuthenticationError", "Invalid token")
            ]
            
            for error_type, error_message in errors_to_simulate:
                if hasattr(client.ws_app, 'on_error'):
                    if error_type == "WebSocketException":
                        import websocket
                        error = websocket.WebSocketException(error_message)
                    else:
                        error = Exception(error_message)
                    client.ws_app.on_error(mock_instance, error)
                    
            # Simulate recovery
            if hasattr(client.ws_app, 'on_open'):
                client.ws_app.on_open(mock_instance)
                
            # Give more time for recovery events to be processed
            time.sleep(0.3)
            
            # Validate error handling regression
            baseline_result = {
                'errors_handled': len(error_events),
                'has_errors': len(error_events) > 0,
                'recovery_attempted': len(recovery_events) > 0
            }
            
            matches, message = regression_validator.validate_behavior(
                'error_handling_and_recovery', baseline_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('error_handling_and_recovery', baseline_result)
                matches = True
                
            assert matches, f"Error handling and recovery regression detected: {message}"
            
    def test_concurrent_operations_regression(self, mock_websocket_client,
                                              refactoring_test_params,
                                              regression_validator):
        """Test concurrent operations remain unchanged"""
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Track concurrent operations
        operation_results = []
        operation_errors = []
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            client.connect()
            # Properly synchronize connection state
            client._connection_manager._connection = mock_instance
            client._connection_manager._on_ws_open(mock_instance)
            client._on_ws_open(mock_instance)
            
            def create_subscriptions():
                try:
                    for i in range(5):
                        query_id = client.subscribe(f"table_{i}", f"SELECT * FROM table_{i}")
                        operation_results.append(f"subscription_{i}")
                except Exception as e:
                    operation_errors.append(str(e))
                    
            def call_reducers():
                try:
                    for i in range(5):
                        client.call_reducer(f"reducer_{i}", {"arg": i})
                        operation_results.append(f"reducer_{i}")
                except Exception as e:
                    operation_errors.append(str(e))
                    
            def send_queries():
                try:
                    for i in range(5):
                        client.one_off_query(f"SELECT * FROM query_table_{i}")
                        operation_results.append(f"query_{i}")
                except Exception as e:
                    operation_errors.append(str(e))
                    
            # Run concurrent operations
            threads = [
                threading.Thread(target=create_subscriptions),
                threading.Thread(target=call_reducers),
                threading.Thread(target=send_queries)
            ]
            
            for thread in threads:
                thread.start()
                
            for thread in threads:
                thread.join()
                
            # Validate concurrent operations regression
            baseline_result = {
                'operations_completed': len(operation_results),
                'operations_failed': len(operation_errors),
                'has_subscriptions': any('subscription' in op for op in operation_results),
                'has_reducers': any('reducer' in op for op in operation_results),
                'has_queries': any('query' in op for op in operation_results)
            }
            
            matches, message = regression_validator.validate_behavior(
                'concurrent_operations', baseline_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('concurrent_operations', baseline_result)
                matches = True
                
            assert matches, f"Concurrent operations regression detected: {message}"
            assert len(operation_errors) == 0
            assert len(operation_results) > 0
            
    def test_memory_usage_regression(self, mock_websocket_client,
                                     refactoring_test_params,
                                     regression_validator,
                                     memory_monitor):
        """Test memory usage patterns remain unchanged"""
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Take initial memory snapshot
        memory_monitor.snapshot("initial")
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Connect
            client.connect()
            # Set connection state to allow subscriptions
            client.state = ConnectionState.CONNECTED
            memory_monitor.snapshot("after_connect")
            
            # Create multiple subscriptions
            for i in range(10):
                client.subscribe(f"table_{i}", f"SELECT * FROM table_{i}")
            memory_monitor.snapshot("after_subscriptions")
            
            # Simulate data processing
            if hasattr(client.ws_app, 'on_message'):
                for i in range(50):
                    data_msg = json.dumps({
                        "TransactionUpdate": {
                            "table_name": f"table_{i % 10}",
                            "data": [{"id": i, "value": f"data_{i}"}]
                        }
                    })
                    client.ws_app.on_message(mock_instance, data_msg)
                    
            memory_monitor.snapshot("after_data_processing")
            
            # Cleanup
            client.disconnect()
            memory_monitor.snapshot("after_cleanup")
            
            # Calculate memory growth
            memory_growth = memory_monitor.get_memory_growth()
            snapshots = memory_monitor.get_snapshots()
            
            # Validate memory usage regression
            baseline_result = {
                'memory_growth_mb': memory_growth / (1024 * 1024),
                'has_reasonable_growth': memory_growth < 50 * 1024 * 1024,  # Less than 50MB
                'snapshots_taken': len(snapshots)
            }
            
            matches, message = regression_validator.validate_behavior(
                'memory_usage', baseline_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('memory_usage', baseline_result)
                matches = True
                
            assert matches, f"Memory usage regression detected: {message}"
            # Memory growth should be reasonable
            assert memory_growth < 100 * 1024 * 1024  # Less than 100MB growth
            
            
    def test_connection_lifecycle_regression(self, mock_websocket_client,
                                             refactoring_test_params,
                                             regression_validator,
                                             connection_state_tracker):
        """Test connection lifecycle remains unchanged"""
        client = WebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"]
        )
        
        # Track state changes
        def on_state_change(old_state, new_state):
            connection_state_tracker.record_state_change(old_state, new_state)
            
        # Monitor initial state
        initial_state = client.connection_state
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Connect
            old_state = client.connection_state
            client.connect()
            on_state_change(old_state, client.connection_state)
            
            # Simulate connection events
            if hasattr(client.ws_app, 'on_open'):
                old_state = client.connection_state
                client.ws_app.on_open(mock_instance)
                on_state_change(old_state, client.connection_state)
                
            # Simulate identity
            if hasattr(client.ws_app, 'on_message'):
                identity_msg = json.dumps({
                    "IdentityToken": {
                        "token": "test_token",
                        "identity": "a" * 32,
                        "connection_id": "b" * 16
                    }
                })
                old_state = client.connection_state
                client.ws_app.on_message(mock_instance, identity_msg)
                on_state_change(old_state, client.connection_state)
                
            # Disconnect
            old_state = client.connection_state
            client.disconnect()
            on_state_change(old_state, client.connection_state)
            
            # Validate connection lifecycle regression
            state_history = connection_state_tracker.get_state_history()
            
            baseline_result = {
                'state_transitions': len(state_history),
                'initial_state': str(initial_state),
                'final_state': str(connection_state_tracker.get_current_state()),
                'has_transitions': len(state_history) > 0
            }
            
            matches, message = regression_validator.validate_behavior(
                'connection_lifecycle', baseline_result
            )
            
            if not matches and 'No baseline recorded' in message:
                regression_validator.record_baseline('connection_lifecycle', baseline_result)
                matches = True
                
            assert matches, f"Connection lifecycle regression detected: {message}"
            assert len(state_history) > 0