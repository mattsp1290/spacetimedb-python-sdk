"""
End-to-end scenario tests for Phase 2 refactoring

These tests validate complete user scenarios work correctly
with the refactored module architecture.
"""
import pytest
import time
import json
import threading
import queue
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional

from spacetimedb_sdk.websocket_client import ModernWebSocketClient, ConnectionState
from .mock_infrastructure import create_test_server, MockServerBehavior, TestDataGenerator
from .test_fixtures import TestScenario, ScenarioRunner


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios"""
    
    def test_chat_application_scenario(self, mock_websocket_client, refactoring_test_params):
        """Test a complete chat application scenario"""
        # Simulate a chat application using the client
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"],
            auth_token="chat_user_token"
        )
        
        # Track application events
        received_messages = []
        user_joined_events = []
        connection_events = []
        
        def on_connect():
            connection_events.append("connected")
            
        def on_identity(token, identity, connection_id):
            connection_events.append(("identity", token, identity, connection_id))
            
        def on_subscription_data(table_name, data):
            if table_name == "messages":
                received_messages.extend(data)
            elif table_name == "users":
                user_joined_events.extend(data)
                
        def on_subscription_applied(query_id, table_name):
            connection_events.append(("subscription_applied", query_id, table_name))
            
        # Set up callbacks
        client.on_connect = on_connect
        client.on_identity = on_identity
        client.on_subscription_data = on_subscription_data
        client.on_subscription_applied = on_subscription_applied
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # 1. Connect to the chat server
            client.connect()
            
            # Simulate connection established
            if hasattr(client.ws_app, 'on_open'):
                client.ws_app.on_open(mock_instance)
                
            # Simulate identity token
            if hasattr(client.ws_app, 'on_message'):
                identity_msg = json.dumps({
                    "IdentityToken": {
                        "token": "chat_identity_token",
                        "identity": "chat_user_123",
                        "connection_id": "conn_456"
                    }
                })
                client.ws_app.on_message(mock_instance, identity_msg)
                
            # 2. Subscribe to messages and users
            messages_query = client.subscribe("messages", "SELECT * FROM messages ORDER BY timestamp")
            users_query = client.subscribe("users", "SELECT * FROM users WHERE online = true")
            
            # Simulate subscription applied
            if hasattr(client.ws_app, 'on_message'):
                for query_id, table_name in [(messages_query, "messages"), (users_query, "users")]:
                    sub_msg = json.dumps({
                        "SubscriptionApplied": {
                            "query_id": query_id or f"query_{table_name}",
                            "table_name": table_name
                        }
                    })
                    client.ws_app.on_message(mock_instance, sub_msg)
                    
            # 3. Simulate receiving initial data
            if hasattr(client.ws_app, 'on_message'):
                # Initial messages
                initial_messages = [
                    {"id": 1, "user": "Alice", "content": "Hello everyone!", "timestamp": time.time() - 300},
                    {"id": 2, "user": "Bob", "content": "Hey Alice!", "timestamp": time.time() - 200}
                ]
                
                msg_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "messages",
                        "data": initial_messages
                    }
                })
                client.ws_app.on_message(mock_instance, msg_data)
                
                # Online users
                online_users = [
                    {"id": 1, "name": "Alice", "online": True},
                    {"id": 2, "name": "Bob", "online": True}
                ]
                
                users_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "users",
                        "data": online_users
                    }
                })
                client.ws_app.on_message(mock_instance, users_data)
                
            # 4. Send a message (call reducer)
            client.call_reducer("send_message", {
                "content": "Hello from the test client!",
                "channel": "general"
            })
            
            # 5. Simulate new message received
            if hasattr(client.ws_app, 'on_message'):
                new_message = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "messages",
                        "data": [{
                            "id": 3,
                            "user": "TestUser",
                            "content": "Hello from the test client!",
                            "timestamp": time.time()
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, new_message)
                
            # Wait for processing
            time.sleep(0.1)
            
            # Validate the complete scenario
            assert "connected" in connection_events
            assert len([e for e in connection_events if e[0] == "identity"]) == 1
            assert len([e for e in connection_events if e[0] == "subscription_applied"]) == 2
            
            # Should have received initial messages
            assert len(received_messages) >= 3  # 2 initial + 1 new
            
            # Should have received user data
            assert len(user_joined_events) >= 2
            
            # Check subscription count
            assert len(client.subscriptions) >= 2
            
            # Verify sent message (call reducer was called)
            assert mock_instance.send.called
            
    def test_gaming_leaderboard_scenario(self, mock_websocket_client, refactoring_test_params):
        """Test a gaming leaderboard scenario"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"],
            auth_token="game_player_token"
        )
        
        # Track game events
        leaderboard_updates = []
        player_stats = []
        game_events = []
        
        def on_subscription_data(table_name, data):
            if table_name == "leaderboard":
                leaderboard_updates.extend(data)
            elif table_name == "player_stats":
                player_stats.extend(data)
            elif table_name == "game_events":
                game_events.extend(data)
                
        client.on_subscription_data = on_subscription_data
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Connect and authenticate
            client.connect()
            
            if hasattr(client.ws_app, 'on_open'):
                client.ws_app.on_open(mock_instance)
                
            if hasattr(client.ws_app, 'on_message'):
                identity_msg = json.dumps({
                    "IdentityToken": {
                        "token": "game_identity_token",
                        "identity": "player_789",
                        "connection_id": "game_conn_123"
                    }
                })
                client.ws_app.on_message(mock_instance, identity_msg)
                
            # Subscribe to game data
            leaderboard_query = client.subscribe("leaderboard", "SELECT * FROM leaderboard ORDER BY score DESC LIMIT 10")
            stats_query = client.subscribe("player_stats", "SELECT * FROM player_stats WHERE player_id = ?")
            events_query = client.subscribe("game_events", "SELECT * FROM game_events WHERE timestamp > ?")
            
            # Simulate subscription confirmations
            if hasattr(client.ws_app, 'on_message'):
                for query_id, table_name in [
                    (leaderboard_query, "leaderboard"),
                    (stats_query, "player_stats"),
                    (events_query, "game_events")
                ]:
                    sub_msg = json.dumps({
                        "SubscriptionApplied": {
                            "query_id": query_id or f"query_{table_name}",
                            "table_name": table_name
                        }
                    })
                    client.ws_app.on_message(mock_instance, sub_msg)
                    
            # Simulate initial game data
            if hasattr(client.ws_app, 'on_message'):
                # Leaderboard data
                leaderboard_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "leaderboard",
                        "data": [
                            {"rank": 1, "player": "ProGamer123", "score": 15000},
                            {"rank": 2, "player": "SkillMaster", "score": 14500},
                            {"rank": 3, "player": "TestPlayer", "score": 13000}
                        ]
                    }
                })
                client.ws_app.on_message(mock_instance, leaderboard_data)
                
                # Player stats
                stats_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "player_stats",
                        "data": [{
                            "player_id": "player_789",
                            "level": 25,
                            "experience": 12500,
                            "wins": 45,
                            "losses": 12
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, stats_data)
                
            # Simulate game actions
            # Player completes a match
            client.call_reducer("complete_match", {
                "match_id": "match_456",
                "score": 850,
                "result": "win"
            })
            
            # Player levels up
            client.call_reducer("level_up", {
                "player_id": "player_789",
                "new_level": 26
            })
            
            # Simulate real-time updates
            if hasattr(client.ws_app, 'on_message'):
                # Leaderboard update (player moved up)
                updated_leaderboard = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "leaderboard",
                        "data": [
                            {"rank": 1, "player": "ProGamer123", "score": 15000},
                            {"rank": 2, "player": "TestPlayer", "score": 13850},  # Player moved up
                            {"rank": 3, "player": "SkillMaster", "score": 14500}
                        ]
                    }
                })
                client.ws_app.on_message(mock_instance, updated_leaderboard)
                
                # Player stats update
                updated_stats = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "player_stats",
                        "data": [{
                            "player_id": "player_789",
                            "level": 26,  # Leveled up
                            "experience": 13350,
                            "wins": 46,  # Won the match
                            "losses": 12
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, updated_stats)
                
                # Game event
                event_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "game_events",
                        "data": [{
                            "id": 101,
                            "type": "level_up",
                            "player": "TestPlayer",
                            "details": {"from_level": 25, "to_level": 26},
                            "timestamp": time.time()
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, event_data)
                
            time.sleep(0.1)
            
            # Validate gaming scenario
            assert len(leaderboard_updates) >= 4  # Initial 3 + 1 update
            assert len(player_stats) >= 2  # Initial + update
            assert len(game_events) >= 1  # Level up event
            
            # Check that player stats were updated correctly
            latest_stats = player_stats[-1]
            assert latest_stats["level"] == 26
            assert latest_stats["wins"] == 46
            
            # Verify game actions were sent
            assert mock_instance.send.call_count >= 2  # 2 reducer calls
            
    def test_iot_monitoring_scenario(self, mock_websocket_client, refactoring_test_params):
        """Test an IoT device monitoring scenario"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"],
            auth_token="iot_monitor_token"
        )
        
        # Track IoT data
        sensor_readings = []
        device_status = []
        alerts = []
        
        def on_subscription_data(table_name, data):
            if table_name == "sensor_readings":
                sensor_readings.extend(data)
            elif table_name == "device_status":
                device_status.extend(data)
            elif table_name == "alerts":
                alerts.extend(data)
                
        client.on_subscription_data = on_subscription_data
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Connect
            client.connect()
            
            if hasattr(client.ws_app, 'on_open'):
                client.ws_app.on_open(mock_instance)
                
            if hasattr(client.ws_app, 'on_message'):
                identity_msg = json.dumps({
                    "IdentityToken": {
                        "token": "iot_identity_token",
                        "identity": "iot_monitor_001",
                        "connection_id": "iot_conn_789"
                    }
                })
                client.ws_app.on_message(mock_instance, identity_msg)
                
            # Subscribe to IoT data streams
            readings_query = client.subscribe("sensor_readings", "SELECT * FROM sensor_readings WHERE timestamp > ?")
            status_query = client.subscribe("device_status", "SELECT * FROM device_status")
            alerts_query = client.subscribe("alerts", "SELECT * FROM alerts WHERE severity >= 'warning'")
            
            # Confirm subscriptions
            if hasattr(client.ws_app, 'on_message'):
                for query_id, table_name in [
                    (readings_query, "sensor_readings"),
                    (status_query, "device_status"),
                    (alerts_query, "alerts")
                ]:
                    sub_msg = json.dumps({
                        "SubscriptionApplied": {
                            "query_id": query_id or f"query_{table_name}",
                            "table_name": table_name
                        }
                    })
                    client.ws_app.on_message(mock_instance, sub_msg)
                    
            # Simulate IoT data stream
            if hasattr(client.ws_app, 'on_message'):
                # Initial device status
                status_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "device_status",
                        "data": [
                            {"device_id": "temp_sensor_01", "status": "online", "battery": 85},
                            {"device_id": "humidity_sensor_01", "status": "online", "battery": 92},
                            {"device_id": "pressure_sensor_01", "status": "offline", "battery": 5}
                        ]
                    }
                })
                client.ws_app.on_message(mock_instance, status_data)
                
                # Stream of sensor readings
                for i in range(10):
                    readings_data = json.dumps({
                        "TransactionUpdate": {
                            "table_name": "sensor_readings",
                            "data": [{
                                "device_id": "temp_sensor_01",
                                "reading_type": "temperature",
                                "value": 22.5 + i * 0.1,
                                "timestamp": time.time() - (10 - i) * 60
                            }, {
                                "device_id": "humidity_sensor_01",
                                "reading_type": "humidity",
                                "value": 65.0 - i * 0.5,
                                "timestamp": time.time() - (10 - i) * 60
                            }]
                        }
                    })
                    client.ws_app.on_message(mock_instance, readings_data)
                    
                # Simulate alert condition
                alert_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "alerts",
                        "data": [{
                            "id": 1,
                            "device_id": "pressure_sensor_01",
                            "alert_type": "device_offline",
                            "severity": "error",
                            "message": "Device has been offline for 30 minutes",
                            "timestamp": time.time()
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, alert_data)
                
            # Send device command
            client.call_reducer("send_device_command", {
                "device_id": "temp_sensor_01",
                "command": "calibrate",
                "parameters": {"reference_temp": 20.0}
            })
            
            # Acknowledge alert
            client.call_reducer("acknowledge_alert", {
                "alert_id": 1,
                "acknowledged_by": "iot_monitor_001"
            })
            
            time.sleep(0.1)
            
            # Validate IoT scenario
            assert len(sensor_readings) >= 20  # 10 iterations * 2 sensors
            assert len(device_status) >= 3  # 3 devices
            assert len(alerts) >= 1  # 1 alert
            
            # Check data quality
            temp_readings = [r for r in sensor_readings if r["reading_type"] == "temperature"]
            humidity_readings = [r for r in sensor_readings if r["reading_type"] == "humidity"]
            
            assert len(temp_readings) >= 10
            assert len(humidity_readings) >= 10
            
            # Verify commands were sent
            assert mock_instance.send.call_count >= 2
            
    def test_real_time_collaboration_scenario(self, mock_websocket_client, refactoring_test_params):
        """Test a real-time collaboration scenario (like a shared document editor)"""
        client = ModernWebSocketClient(
            host=refactoring_test_params["host"],
            database_address=refactoring_test_params["database_address"],
            auth_token="collab_user_token"
        )
        
        # Track collaboration events
        document_changes = []
        user_cursors = []
        collaboration_events = []
        
        def on_subscription_data(table_name, data):
            if table_name == "document_changes":
                document_changes.extend(data)
            elif table_name == "user_cursors":
                user_cursors.extend(data)
            elif table_name == "collaboration_events":
                collaboration_events.extend(data)
                
        client.on_subscription_data = on_subscription_data
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws_app:
            mock_instance = Mock()
            mock_ws_app.return_value = mock_instance
            
            # Connect
            client.connect()
            
            if hasattr(client.ws_app, 'on_open'):
                client.ws_app.on_open(mock_instance)
                
            if hasattr(client.ws_app, 'on_message'):
                identity_msg = json.dumps({
                    "IdentityToken": {
                        "token": "collab_identity_token",
                        "identity": "user_collab_001",
                        "connection_id": "collab_conn_456"
                    }
                })
                client.ws_app.on_message(mock_instance, identity_msg)
                
            # Subscribe to collaboration streams
            doc_id = "shared_doc_123"
            changes_query = client.subscribe("document_changes", f"SELECT * FROM document_changes WHERE document_id = '{doc_id}'")
            cursors_query = client.subscribe("user_cursors", f"SELECT * FROM user_cursors WHERE document_id = '{doc_id}'")
            events_query = client.subscribe("collaboration_events", f"SELECT * FROM collaboration_events WHERE document_id = '{doc_id}'")
            
            # Confirm subscriptions
            if hasattr(client.ws_app, 'on_message'):
                for query_id, table_name in [
                    (changes_query, "document_changes"),
                    (cursors_query, "user_cursors"),
                    (events_query, "collaboration_events")
                ]:
                    sub_msg = json.dumps({
                        "SubscriptionApplied": {
                            "query_id": query_id or f"query_{table_name}",
                            "table_name": table_name
                        }
                    })
                    client.ws_app.on_message(mock_instance, sub_msg)
                    
            # Simulate collaborative editing session
            if hasattr(client.ws_app, 'on_message'):
                # Initial document state
                initial_change = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "document_changes",
                        "data": [{
                            "id": 1,
                            "document_id": doc_id,
                            "user_id": "user_001",
                            "operation": "insert",
                            "position": 0,
                            "content": "Hello World",
                            "timestamp": time.time() - 300
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, initial_change)
                
                # User cursors
                cursor_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "user_cursors",
                        "data": [
                            {"user_id": "user_001", "document_id": doc_id, "position": 11, "selection_start": 6, "selection_end": 11},
                            {"user_id": "user_002", "document_id": doc_id, "position": 5, "selection_start": None, "selection_end": None}
                        ]
                    }
                })
                client.ws_app.on_message(mock_instance, cursor_data)
                
            # Simulate user making edits
            # Insert text
            client.call_reducer("insert_text", {
                "document_id": doc_id,
                "position": 11,
                "content": " from Python!",
                "user_id": "user_collab_001"
            })
            
            # Update cursor position
            client.call_reducer("update_cursor", {
                "document_id": doc_id,
                "user_id": "user_collab_001",
                "position": 25,
                "selection_start": None,
                "selection_end": None
            })
            
            # Simulate receiving updates from other users
            if hasattr(client.ws_app, 'on_message'):
                # Another user's edit
                other_user_change = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "document_changes",
                        "data": [{
                            "id": 2,
                            "document_id": doc_id,
                            "user_id": "user_002",
                            "operation": "insert",
                            "position": 5,
                            "content": " Amazing",
                            "timestamp": time.time()
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, other_user_change)
                
                # Cursor updates
                cursor_update = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "user_cursors",
                        "data": [{
                            "user_id": "user_002",
                            "document_id": doc_id,
                            "position": 13,
                            "selection_start": None,
                            "selection_end": None
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, cursor_update)
                
                # Collaboration event
                event_data = json.dumps({
                    "TransactionUpdate": {
                        "table_name": "collaboration_events",
                        "data": [{
                            "id": 1,
                            "document_id": doc_id,
                            "event_type": "user_joined",
                            "user_id": "user_003",
                            "timestamp": time.time()
                        }]
                    }
                })
                client.ws_app.on_message(mock_instance, event_data)
                
            time.sleep(0.1)
            
            # Validate collaboration scenario
            assert len(document_changes) >= 2  # Initial + other user's change
            assert len(user_cursors) >= 3  # Initial 2 + 1 update
            assert len(collaboration_events) >= 1  # User joined event
            
            # Verify real-time nature - changes should have recent timestamps
            recent_changes = [c for c in document_changes if c["timestamp"] > time.time() - 60]
            assert len(recent_changes) >= 1
            
            # Verify collaboration commands were sent
            assert mock_instance.send.call_count >= 2


class TestScenarioIntegration:
    """Test scenario integration and orchestration"""
    
    def test_scenario_runner_functionality(self, integration_scenarios):
        """Test the scenario runner with integration scenarios"""
        scenario = integration_scenarios[0]  # Get the first scenario
        runner = ScenarioRunner(scenario)
        
        def test_function(server, scenario):
            # Simple test function
            assert server is not None
            assert scenario.name == "full_lifecycle"
            time.sleep(0.1)  # Simulate some work
            
        # Run the scenario
        results = runner.run(test_function)
        
        # Validate results
        assert results['success'] is True
        assert results['scenario_name'] == "full_lifecycle"
        assert results['duration'] > 0
        assert 'server_metrics' in results
        
    def test_multiple_scenarios_execution(self, integration_scenarios):
        """Test executing multiple scenarios in sequence"""
        results = []
        
        for scenario in integration_scenarios[:2]:  # Test first 2 scenarios
            runner = ScenarioRunner(scenario)
            
            def test_function(server, scenario):
                # Add test data to server
                test_data = TestDataGenerator.generate_user_data(10)
                server.add_table_data('test-db', 'test_table', test_data)
                
                # Verify server is working
                metrics = server.get_metrics()
                assert isinstance(metrics, dict)
                
            result = runner.run(test_function)
            results.append(result)
            
        # Validate all scenarios completed
        assert len(results) == 2
        assert all(r['success'] for r in results)
        
        # Check that scenarios are isolated
        scenario_names = [r['scenario_name'] for r in results]
        assert len(set(scenario_names)) == 2  # All unique
        
    def test_scenario_error_handling(self):
        """Test scenario error handling"""
        scenario = TestScenario(
            name="error_test",
            description="Test error handling",
            server_behavior=MockServerBehavior.NORMAL,
            expected_outcomes={'should_fail': True}
        )
        
        runner = ScenarioRunner(scenario)
        
        def failing_test_function(server, scenario):
            raise Exception("Intentional test failure")
            
        result = runner.run(failing_test_function)
        
        # Should capture the error
        assert result['success'] is False
        assert result['error'] == "Intentional test failure"
        assert result['scenario_name'] == "error_test"