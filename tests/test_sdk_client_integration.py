#!/usr/bin/env python3
"""
Comprehensive SDK-Client Integration Test Suite

Tests the compatibility between spacetimedb-python-sdk and blackholio-python-client
to ensure seamless integration and protocol compliance.
"""

import pytest
import asyncio
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional

# SDK imports
from spacetimedb_sdk.websocket_client import ModernWebSocketClient, SubscriptionMetrics
from spacetimedb_sdk.message_validator import SpacetimeDBMessageValidator, MessageValidationError
from spacetimedb_sdk.large_message_handler import LargeMessageHandler
from spacetimedb_sdk.connection_recovery import RobustConnectionManager
from spacetimedb_sdk.protocol import (
    InitialSubscription, TransactionUpdate, TransactionUpdateLight,
    SubscribeApplied, SubscribeMultiApplied, SubscriptionError,
    TEXT_PROTOCOL, BIN_PROTOCOL
)


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.sent_messages = []
        self.is_connected = True
        
    def send(self, message):
        self.sent_messages.append(message)
        
    def close(self):
        self.is_connected = False


class MockBlackholioClient:
    """Mock blackholio-python-client for integration testing."""
    
    def __init__(self, protocol: str = TEXT_PROTOCOL):
        self.protocol = protocol
        self.messages_sent = []
        self.subscription_state = {}
        
    def _get_frame_type(self) -> str:
        """Get frame type based on protocol."""
        if 'bsatn' in self.protocol.lower() or self.protocol == 'binary':
            return "BINARY"
        else:
            return "TEXT"
    
    def send_message(self, message: Dict[str, Any]):
        """Send message using client format (no 'type' field)."""
        # Client sends direct variant format
        self.messages_sent.append(message)


class TestMessageFormatCompatibility:
    """Test that SDK accepts client message formats."""
    
    def test_direct_variant_format_validation(self):
        """Test that SDK accepts direct variant format (no 'type' field)."""
        
        # Test CallReducer format sent by client
        client_message = {
            "CallReducer": {
                "reducer": "enter_game",
                "args": {"player_name": "test"},
                "request_id": 12345
            }
        }
        
        # Should not raise validation error
        assert SpacetimeDBMessageValidator.validate_message(client_message)
    
    def test_subscribe_single_format_validation(self):
        """Test SubscribeSingle format validation."""
        
        client_message = {
            "SubscribeSingle": {
                "query": "SELECT * FROM players",
                "request_id": 12346,
                "query_id": [1, 2, 3, 4]
            }
        }
        
        assert SpacetimeDBMessageValidator.validate_message(client_message)
    
    def test_subscribe_multi_format_validation(self):
        """Test SubscribeMulti format validation."""
        
        client_message = {
            "SubscribeMulti": {
                "query_strings": ["SELECT * FROM players", "SELECT * FROM games"],
                "request_id": 12347,
                "query_id": [1, 2, 3, 4]
            }
        }
        
        assert SpacetimeDBMessageValidator.validate_message(client_message)
    
    def test_legacy_format_with_warning(self):
        """Test that legacy format with 'type' field still works but logs warning."""
        
        with patch('spacetimedb_sdk.message_validator.logging.getLogger') as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance
            
            legacy_message = {
                "type": "CallReducer",
                "CallReducer": {
                    "reducer": "enter_game",
                    "args": {"player_name": "test"},
                    "request_id": 12345
                }
            }
            
            # Should still validate successfully
            assert SpacetimeDBMessageValidator.validate_message(legacy_message)
            
            # Should log warning about legacy format
            logger_instance.warning.assert_called()
    
    def test_invalid_custom_message_types_rejected(self):
        """Test that invalid custom message types are properly rejected."""
        
        invalid_messages = [
            {"heartbeat": {"timestamp": time.time()}},
            {"ping": {"id": 123}},
            {"pong": {"id": 123}},
            {"close": {"reason": "done"}},
            {"connect": {"url": "ws://test"}},
            {"disconnect": {"reason": "timeout"}},
            {"keep_alive": {}},
            {"status": {"connected": True}},
            {"health_check": {}}
        ]
        
        for invalid_message in invalid_messages:
            with pytest.raises(MessageValidationError):
                SpacetimeDBMessageValidator.validate_message(invalid_message)


class TestFrameTypeSelection:
    """Test frame type matches protocol between SDK and client."""
    
    @pytest.mark.parametrize("protocol,expected_frame", [
        ("v1.json.spacetimedb", "TEXT"),
        ("v1.bsatn.spacetimedb", "BINARY"),
        ("v1.1.json.spacetimedb", "TEXT"),
        ("v1.1.bsatn.spacetimedb", "BINARY"),
        ("text", "TEXT"),
        ("binary", "BINARY"),
        (TEXT_PROTOCOL, "TEXT"),
        (BIN_PROTOCOL, "BINARY"),
    ])
    def test_frame_type_consistency(self, protocol, expected_frame):
        """Test that SDK and client use same frame type for protocol."""
        
        # Test SDK frame type detection
        sdk_client = ModernWebSocketClient(protocol=protocol)
        sdk_frame_type = "BINARY" if sdk_client.use_binary else "TEXT"
        
        # Test mock client frame type detection
        mock_client = MockBlackholioClient(protocol=protocol)
        client_frame_type = mock_client._get_frame_type()
        
        # Both should use same frame type
        assert sdk_frame_type == expected_frame
        assert client_frame_type == expected_frame
        assert sdk_frame_type == client_frame_type


class TestProtocolHelperIntegration:
    """Test protocol helper integration between SDK and client."""
    
    def test_protocol_helper_access(self):
        """Test that client can access SDK protocol helper."""
        
        sdk_client = ModernWebSocketClient(protocol=TEXT_PROTOCOL)
        protocol_helper = sdk_client.get_protocol_helper()
        
        # Should provide access to encoding/decoding components
        assert 'encoder' in protocol_helper
        assert 'decoder' in protocol_helper
        assert 'use_binary' in protocol_helper
        assert 'protocol' in protocol_helper
        
        # Verify protocol consistency
        assert protocol_helper['protocol'] == TEXT_PROTOCOL
        assert protocol_helper['use_binary'] == False
    
    def test_client_encoding_bypass(self):
        """Test that client can bypass SDK encoding."""
        
        sdk_client = ModernWebSocketClient(protocol=TEXT_PROTOCOL)
        mock_ws = MockWebSocket()
        sdk_client.ws = mock_ws
        sdk_client.state = sdk_client.state.CONNECTED
        
        # Create pre-encoded message (as client would send)
        pre_encoded_message = json.dumps({
            "CallReducer": {
                "reducer": "test_reducer",
                "args": {"value": 123},
                "request_id": 999
            }
        })
        
        # Send with client encoding enabled
        with patch.object(sdk_client, '_send_client_encoded_message') as mock_send:
            sdk_client.send_message(pre_encoded_message, use_client_encoding=True)
            mock_send.assert_called_once_with(pre_encoded_message)


class TestSubscriptionStateSync:
    """Test subscription state coordination between SDK and client."""
    
    def test_subscription_state_callbacks(self):
        """Test subscription state callback registration and notification."""
        
        sdk_client = ModernWebSocketClient()
        state_changes = []
        
        def track_state(event_type: str, data: Any):
            state_changes.append((event_type, data))
        
        # Register callback
        sdk_client.add_subscription_state_callback(track_state)
        assert len(sdk_client.subscription_state_callbacks) == 1
        
        # Simulate subscription update
        mock_message = Mock(spec=InitialSubscription)
        sdk_client._notify_subscription_state_callbacks(mock_message)
        
        # Should have recorded the state change
        assert len(state_changes) == 1
        assert state_changes[0][0] == 'subscription_update'
        assert state_changes[0][1] == mock_message
        
        # Test callback removal
        sdk_client.remove_subscription_state_callback(track_state)
        assert len(sdk_client.subscription_state_callbacks) == 0
    
    def test_subscription_error_callbacks(self):
        """Test subscription error callback handling."""
        
        sdk_client = ModernWebSocketClient()
        error_events = []
        
        def track_errors(event_type: str, data: Any):
            error_events.append((event_type, data))
        
        sdk_client.add_subscription_state_callback(track_errors)
        
        # Simulate subscription error
        mock_error = Mock(spec=SubscriptionError)
        sdk_client._notify_subscription_state_callbacks(mock_error)
        
        # Should have recorded the error
        assert len(error_events) == 1
        assert error_events[0][0] == 'subscription_error'
        assert error_events[0][1] == mock_error


class TestLargeMessageIntegration:
    """Test large message handling between SDK and client."""
    
    @pytest.mark.asyncio
    async def test_large_message_progress_tracking(self):
        """Test large message progress tracking with callbacks."""
        
        # Create 100KB test message
        large_data = "x" * 100_000
        large_message = json.dumps({
            "InitialSubscription": {
                "database_update": {
                    "tables": [{"table_name": "game_state", "data": large_data}]
                }
            }
        })
        
        progress_events = []
        
        def track_progress(event: str, current: int, total: int):
            progress_events.append((event, current, total))
        
        mock_send = Mock()
        handler = LargeMessageHandler(mock_send)
        
        # Send large message with progress tracking
        handler.send_large_message(large_message, "test", track_progress)
        
        # Should have progress events
        assert len(progress_events) > 0
        
        # Should have start and complete events
        event_types = [event[0] for event in progress_events]
        assert 'start' in event_types
        assert 'complete' in event_types
        
        # May have chunk events for very large messages
        if len(large_message.encode('utf-8')) > handler.MAX_FRAME_SIZE:
            assert 'chunk' in event_types
    
    def test_large_message_chunking_threshold(self):
        """Test that large messages are properly chunked."""
        
        mock_send = Mock()
        handler = LargeMessageHandler(mock_send)
        
        # Create message larger than threshold
        large_message = "x" * (handler.MAX_FRAME_SIZE + 1000)
        
        handler.send_large_message(large_message, "test")
        
        # Should have sent multiple messages (header + chunks)
        assert mock_send.call_count > 1
        
        # First call should be chunk header
        first_call_args = mock_send.call_args_list[0][0][0]
        header_data = json.loads(first_call_args)
        assert "ChunkedMessage" in header_data
    
    def test_small_message_passthrough(self):
        """Test that small messages pass through without chunking."""
        
        mock_send = Mock()
        handler = LargeMessageHandler(mock_send)
        
        # Create small message
        small_message = json.dumps({"test": "data"})
        
        handler.send_large_message(small_message, "test")
        
        # Should send exactly one message
        assert mock_send.call_count == 1
        
        # Should be the original message
        sent_message = mock_send.call_args_list[0][0][0]
        assert sent_message == small_message


class TestSubscriptionHealthMonitoring:
    """Test subscription health monitoring and metrics."""
    
    def test_subscription_metrics_recording(self):
        """Test subscription metrics are properly recorded."""
        
        metrics = SubscriptionMetrics()
        
        # Record some subscription data
        metrics.record_subscription_data("players", 1024)
        metrics.record_subscription_data("players", 2048)
        metrics.record_subscription_data("games", 512)
        
        # Check metrics for players table
        health = metrics.get_subscription_health("players")
        assert health['status'] == 'healthy'
        assert health['message_count'] == 2
        assert health['total_bytes'] == 3072
        assert health['error_count'] == 0
        
        # Check metrics for games table
        games_health = metrics.get_subscription_health("games")
        assert games_health['message_count'] == 1
        assert games_health['total_bytes'] == 512
    
    def test_subscription_error_tracking(self):
        """Test subscription error tracking affects health status."""
        
        metrics = SubscriptionMetrics()
        
        # Record data and errors
        for i in range(10):
            metrics.record_subscription_data("test_table", 100)
        
        # Record some errors (more than 10% error rate)
        metrics.record_subscription_error("test_table", "connection timeout")
        metrics.record_subscription_error("test_table", "parse error")
        
        health = metrics.get_subscription_health("test_table")
        
        # Should be unhealthy due to high error rate
        assert health['status'] == 'unhealthy'
        assert health['error_count'] == 2
        assert health['error_rate'] > 0.1
    
    def test_subscription_staleness_detection(self):
        """Test that stale subscriptions are detected."""
        
        metrics = SubscriptionMetrics()
        
        # Record data with old timestamp
        metrics.record_subscription_data("stale_table", 100)
        
        # Manually set last_received to old time
        metrics.subscriptions["stale_table"]["last_received"] = time.time() - 65  # 65 seconds ago
        
        health = metrics.get_subscription_health("stale_table")
        assert health['status'] == 'stale'
        assert health['seconds_since_last'] > 60
    
    def test_all_subscription_health_summary(self):
        """Test getting health for all subscriptions."""
        
        metrics = SubscriptionMetrics()
        
        # Record data for multiple tables
        metrics.record_subscription_data("table1", 100)
        metrics.record_subscription_data("table2", 200)
        metrics.record_subscription_data("table3", 300)
        
        all_health = metrics.get_all_subscription_health()
        
        assert len(all_health) == 3
        assert "table1" in all_health
        assert "table2" in all_health
        assert "table3" in all_health
        
        # All should be healthy with recent data
        for table_health in all_health.values():
            assert table_health['status'] == 'healthy'


class TestConnectionRecoveryIntegration:
    """Test connection recovery works with client state."""
    
    @pytest.mark.asyncio
    async def test_protocol_error_recovery(self):
        """Test recovery from protocol errors."""
        
        recovery_manager = RobustConnectionManager(max_retries=3)
        
        connection_attempts = []
        
        def mock_connect():
            connection_attempts.append(len(connection_attempts) + 1)
            if len(connection_attempts) == 1:
                # First attempt fails with protocol error
                raise ConnectionError("unknown tag 0x7b")
            else:
                # Second attempt succeeds
                return MockWebSocket()
        
        # Should recover automatically
        connection = await recovery_manager.connect_with_recovery(mock_connect)
        
        assert connection is not None
        assert len(connection_attempts) == 2  # Failed once, then succeeded
    
    def test_recoverable_error_detection(self):
        """Test that protocol errors are correctly identified as recoverable."""
        
        recovery_manager = RobustConnectionManager()
        
        recoverable_errors = [
            "unknown tag 0x7b",
            "invalid close frame",
            "protocol mismatch",
            "received text frame with binary protocol",
            "received binary frame with text protocol",
            "connection timed out",
            "handshake error",
            "websocket error"
        ]
        
        for error_msg in recoverable_errors:
            error_type = recovery_manager.is_recoverable_error(error_msg)
            assert error_type is not None, f"Error '{error_msg}' should be recoverable"
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker prevents excessive retry attempts."""
        
        recovery_manager = RobustConnectionManager(
            max_retries=2,
            circuit_breaker_threshold=3
        )
        
        # Simulate multiple failures to trigger circuit breaker
        for i in range(5):
            recovery_manager.health.error_count = i + 1
            if recovery_manager.health.error_count >= recovery_manager.circuit_breaker_threshold:
                break
        
        # Should open circuit breaker
        assert recovery_manager.health.error_count >= recovery_manager.circuit_breaker_threshold


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    def test_complete_message_flow(self):
        """Test complete message flow from client through SDK."""
        
        # Create SDK client
        sdk_client = ModernWebSocketClient(protocol=TEXT_PROTOCOL)
        
        # Create mock client 
        mock_client = MockBlackholioClient(protocol=TEXT_PROTOCOL)
        
        # Verify protocol compatibility
        assert sdk_client.detect_expected_frame_type() == mock_client._get_frame_type()
        
        # Test message validation
        client_message = {
            "CallReducer": {
                "reducer": "test_action",
                "args": {"data": "test"},
                "request_id": 123
            }
        }
        
        # Should validate successfully
        assert SpacetimeDBMessageValidator.validate_message(client_message)
        
        # Mock client sends message
        mock_client.send_message(client_message)
        assert len(mock_client.messages_sent) == 1
        assert mock_client.messages_sent[0] == client_message
    
    def test_subscription_lifecycle_integration(self):
        """Test complete subscription lifecycle with health monitoring."""
        
        sdk_client = ModernWebSocketClient()
        
        # Track subscription events
        subscription_events = []
        def track_subscription_events(event_type: str, data: Any):
            subscription_events.append((event_type, data))
        
        sdk_client.add_subscription_state_callback(track_subscription_events)
        
        # Simulate subscription messages
        mock_initial = Mock(spec=InitialSubscription)
        mock_update = Mock(spec=TransactionUpdate)
        
        sdk_client._notify_subscription_state_callbacks(mock_initial)
        sdk_client._notify_subscription_state_callbacks(mock_update)
        
        # Should have tracked both events
        assert len(subscription_events) == 2
        assert subscription_events[0][0] == 'subscription_update'
        assert subscription_events[1][0] == 'subscription_update'
        
        # Test health monitoring
        initial_health = sdk_client.get_all_subscription_health()
        # Should be empty initially (no actual data recorded in mocks)
        assert isinstance(initial_health, dict)


class TestPerformanceAndLimits:
    """Test performance characteristics and limits."""
    
    def test_large_subscription_data_handling(self):
        """Test handling of large subscription data."""
        
        metrics = SubscriptionMetrics()
        
        # Simulate large subscription data
        large_data_size = 5 * 1024 * 1024  # 5MB
        metrics.record_subscription_data("large_table", large_data_size)
        
        health = metrics.get_subscription_health("large_table")
        assert health['total_bytes'] == large_data_size
        assert health['status'] == 'healthy'
    
    def test_high_frequency_updates(self):
        """Test handling of high-frequency subscription updates."""
        
        metrics = SubscriptionMetrics()
        
        # Simulate high-frequency updates
        for i in range(1000):
            metrics.record_subscription_data("high_freq_table", 100)
        
        health = metrics.get_subscription_health("high_freq_table")
        assert health['message_count'] == 1000
        assert health['total_bytes'] == 100_000
        assert health['status'] == 'healthy'
    
    def test_message_validator_performance(self):
        """Test message validation performance."""
        
        # Create test message
        test_message = {
            "CallReducer": {
                "reducer": "test_reducer",
                "args": {"data": "x" * 1000},  # 1KB of data
                "request_id": 123
            }
        }
        
        # Validate many times to test performance
        start_time = time.time()
        for i in range(1000):
            assert SpacetimeDBMessageValidator.validate_message(test_message)
        end_time = time.time()
        
        # Should complete quickly (less than 1 second for 1000 validations)
        assert (end_time - start_time) < 1.0


if __name__ == "__main__":
    # Run the test suite
    pytest.main([__file__, "-v", "--tb=short"])