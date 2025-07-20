#!/usr/bin/env python3
"""
Error Scenario Tests for SDK-Client Integration

Tests error handling, edge cases, and failure recovery scenarios
to ensure robust operation under adverse conditions.
"""

import pytest
import asyncio
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional

from spacetimedb_sdk.websocket_client import WebSocketClient, SubscriptionMetrics
from spacetimedb_sdk.message_validator import (
    SpacetimeDBMessageValidator, 
    MessageValidationError,
    SpacetimeDBHeartbeatManager
)
from spacetimedb_sdk.large_message_handler import LargeMessageHandler
from spacetimedb_sdk.connection_recovery import RobustConnectionManager, ProtocolErrorType
from spacetimedb_sdk.protocol import TEXT_PROTOCOL, BIN_PROTOCOL


class TestMessageValidationErrors:
    """Test message validation error scenarios."""
    
    def test_malformed_message_structures(self):
        """Test handling of malformed message structures."""
        
        malformed_messages = [
            # Empty message
            {},
            
            # Missing required fields
            {"CallReducer": {}},
            {"CallReducer": {"reducer": "test"}},  # Missing args and request_id
            
            # Invalid field types
            {"CallReducer": {"reducer": 123, "args": {}, "request_id": 1}},  # reducer should be string
            {"SubscribeMulti": {"query_strings": "not_a_list", "request_id": 1, "query_id": []}},
            
            # Nested structure errors
            {"CallReducer": {"reducer": "test", "args": "not_a_dict", "request_id": 1}},
            
            # Multiple message types in one message (invalid)
            {"CallReducer": {}, "Subscribe": {}},
        ]
        
        for malformed_message in malformed_messages:
            with pytest.raises(MessageValidationError):
                SpacetimeDBMessageValidator.validate_message(malformed_message)
    
    def test_invalid_custom_message_handling(self):
        """Test proper rejection and error messages for invalid custom types."""
        
        invalid_custom_messages = [
            {"heartbeat": {"timestamp": time.time()}},
            {"custom_type": {"data": "test"}},
            {"client_message": {"action": "test"}},
        ]
        
        for invalid_message in invalid_custom_messages:
            try:
                SpacetimeDBMessageValidator.validate_message(invalid_message)
                assert False, f"Should have rejected invalid message: {invalid_message}"
            except MessageValidationError as e:
                # Should provide helpful error message
                assert "SpacetimeDB" in str(e)
                assert "valid" in str(e).lower()
    
    def test_oversized_message_validation(self):
        """Test handling of oversized messages."""
        
        # Create extremely large message
        large_data = "x" * (10 * 1024 * 1024)  # 10MB
        large_message = {
            "CallReducer": {
                "reducer": "large_test",
                "args": {"data": large_data},
                "request_id": 1
            }
        }
        
        # Should still validate (validation doesn't check size limits)
        assert SpacetimeDBMessageValidator.validate_message(large_message)
    
    def test_unicode_and_encoding_edge_cases(self):
        """Test handling of unicode and encoding edge cases."""
        
        unicode_messages = [
            # Unicode in reducer names
            {"CallReducer": {"reducer": "测试_reducer", "args": {}, "request_id": 1}},
            
            # Unicode in arguments
            {"CallReducer": {"reducer": "test", "args": {"name": "用户名", "emoji": "🚀"}, "request_id": 1}},
            
            # Special characters
            {"CallReducer": {"reducer": "test", "args": {"special": "\n\t\r\\"}, "request_id": 1}},
        ]
        
        for unicode_message in unicode_messages:
            # Should handle unicode properly
            assert SpacetimeDBMessageValidator.validate_message(unicode_message)


class TestLargeMessageErrorScenarios:
    """Test large message handling error scenarios."""
    
    def test_chunk_corruption_handling(self):
        """Test handling of corrupted message chunks."""
        
        handler = LargeMessageHandler(lambda x: None)
        
        # Simulate corrupted chunk data
        corrupted_chunk = {
            "chunk_id": "test_chunk",
            "sequence": 0,
            "data": "invalid_base64_data!!!",  # Invalid base64
            "size": 100
        }
        
        # Should handle corruption gracefully
        result = handler._handle_chunk_data(corrupted_chunk)
        assert result is None  # Should return None for corrupted chunks
    
    def test_missing_chunk_header_handling(self):
        """Test handling when chunk data arrives without header."""
        
        handler = LargeMessageHandler(lambda x: None)
        
        # Send chunk data without header
        orphaned_chunk = {
            "chunk_id": "orphaned_chunk",
            "sequence": 0,
            "data": "dGVzdA==",  # base64 for "test"
            "size": 4
        }
        
        # Should handle gracefully
        result = handler._handle_chunk_data(orphaned_chunk)
        assert result is None
    
    def test_chunk_timeout_handling(self):
        """Test cleanup of timed-out chunks."""
        
        handler = LargeMessageHandler(lambda x: None)
        
        # Create chunks with old timestamps
        old_time = time.time() - 100  # 100 seconds ago
        
        handler._chunk_metadata["old_chunk"] = {
            "total_size": 1000,
            "chunk_count": 5,
            "message_type": "test",
            "start_time": old_time,
            "received_chunks": 2
        }
        
        handler._incoming_chunks["old_chunk"] = {
            0: Mock(),
            1: Mock()
        }
        
        # Should have the old chunk
        assert "old_chunk" in handler._chunk_metadata
        
        # Run cleanup
        handler._cleanup_stale_chunks()
        
        # Should have cleaned up the old chunk
        assert "old_chunk" not in handler._chunk_metadata
        assert "old_chunk" not in handler._incoming_chunks
    
    def test_oversized_message_rejection(self):
        """Test rejection of oversized messages."""
        
        handler = LargeMessageHandler(lambda x: None)
        
        # Try to send message larger than maximum
        oversized_data = "x" * (handler.MAX_MESSAGE_SIZE + 1000)
        
        with pytest.raises(ValueError) as exc_info:
            handler.send_large_message(oversized_data, "test")
        
        assert "too large" in str(exc_info.value).lower()
        assert str(handler.MAX_MESSAGE_SIZE) in str(exc_info.value)
    
    def test_chunk_sequence_out_of_order(self):
        """Test handling of chunks arriving out of order."""
        
        handler = LargeMessageHandler(lambda x: None)
        
        chunk_id = "ooo_chunk"
        test_data = b"0123456789" * 100  # 1KB test data
        
        # Set up chunk metadata
        handler._chunk_metadata[chunk_id] = {
            "total_size": len(test_data),
            "chunk_count": 3,
            "message_type": "test",
            "start_time": time.time(),
            "received_chunks": 0
        }
        handler._incoming_chunks[chunk_id] = {}
        
        # Create chunks
        chunk_size = len(test_data) // 3
        chunks = [
            {"chunk_id": chunk_id, "sequence": 0, "data": test_data[:chunk_size]},
            {"chunk_id": chunk_id, "sequence": 1, "data": test_data[chunk_size:2*chunk_size]},
            {"chunk_id": chunk_id, "sequence": 2, "data": test_data[2*chunk_size:]},
        ]
        
        # Process chunks out of order (2, 0, 1)
        import base64
        
        # Process chunk 2 first
        handler._handle_chunk_data({
            "chunk_id": chunk_id,
            "sequence": 2,
            "data": base64.b64encode(chunks[2]["data"]).decode(),
            "size": len(chunks[2]["data"])
        })
        
        # Process chunk 0
        handler._handle_chunk_data({
            "chunk_id": chunk_id,
            "sequence": 0,
            "data": base64.b64encode(chunks[0]["data"]).decode(),
            "size": len(chunks[0]["data"])
        })
        
        # Process chunk 1 (should complete the message)
        result = handler._handle_chunk_data({
            "chunk_id": chunk_id,
            "sequence": 1,
            "data": base64.b64encode(chunks[1]["data"]).decode(),
            "size": len(chunks[1]["data"])
        })
        
        # Should successfully reassemble despite out-of-order arrival
        assert result is not None
        assert len(result) == len(test_data)


class TestConnectionRecoveryErrors:
    """Test connection recovery error scenarios."""
    
    @pytest.mark.asyncio
    async def test_max_retry_exhaustion(self):
        """Test behavior when max retries are exhausted."""
        
        recovery_manager = RobustConnectionManager(max_retries=3)
        
        def always_fail():
            # Use a recoverable error that will trigger retries
            raise ConnectionError("unknown tag 0x7b")
        
        # Should exhaust retries and raise final error
        with pytest.raises(ConnectionError) as exc_info:
            await recovery_manager.connect_with_recovery(always_fail)
        
        assert "Failed to connect after 3 attempts" in str(exc_info.value)
        assert "unknown tag 0x7b" in str(exc_info.value)
    
    def test_non_recoverable_error_handling(self):
        """Test handling of non-recoverable errors."""
        
        recovery_manager = RobustConnectionManager()
        
        non_recoverable_errors = [
            "authentication failed",
            "database not found", 
            "permission denied",
            "invalid credentials",
            "ssl certificate error"
        ]
        
        for error_msg in non_recoverable_errors:
            error_type = recovery_manager.is_recoverable_error(error_msg)
            assert error_type is None, f"Error '{error_msg}' should not be recoverable"
    
    def test_circuit_breaker_timeout(self):
        """Test circuit breaker timeout and reset behavior."""
        
        recovery_manager = RobustConnectionManager(
            circuit_breaker_threshold=2,
        )
        
        # Trigger circuit breaker
        recovery_manager.health.error_count = 3
        recovery_manager.circuit_open = True
        recovery_manager.circuit_open_time = time.time() - 70  # 70 seconds ago
        
        # Should allow reset after timeout
        asyncio.run(recovery_manager._check_circuit_breaker())
        assert not recovery_manager.circuit_open


class TestSubscriptionMetricsErrors:
    """Test subscription metrics error scenarios."""
    
    def test_metrics_with_invalid_table_names(self):
        """Test metrics handling with invalid/unusual table names."""
        
        metrics = SubscriptionMetrics()
        
        unusual_table_names = [
            "",  # Empty string
            "   ",  # Whitespace only
            "table_with_很长的名字_and_unicode",
            "table\nwith\nnewlines",
            "table\twith\ttabs",
            "a" * 1000,  # Very long name
        ]
        
        for table_name in unusual_table_names:
            # Should handle unusual names gracefully
            metrics.record_subscription_data(table_name, 100)
            health = metrics.get_subscription_health(table_name)
            assert health['message_count'] == 1
            assert health['total_bytes'] == 100
    
    def test_negative_data_sizes(self):
        """Test handling of negative or invalid data sizes."""
        
        metrics = SubscriptionMetrics()
        
        # Record negative sizes (shouldn't happen in practice but test robustness)
        metrics.record_subscription_data("test_table", -100)
        metrics.record_subscription_data("test_table", 0)
        metrics.record_subscription_data("test_table", 200)
        
        health = metrics.get_subscription_health("test_table")
        assert health['message_count'] == 3
        assert health['total_bytes'] == 100  # -100 + 0 + 200
    
    def test_concurrent_metrics_access(self):
        """Test thread safety of metrics under concurrent access."""
        
        metrics = SubscriptionMetrics()
        errors = []
        
        def record_data(thread_id: int):
            try:
                for i in range(1000):
                    table_name = f"thread_{thread_id}_table"
                    metrics.record_subscription_data(table_name, 100)
                    
                    # Occasionally check health
                    if i % 100 == 0:
                        health = metrics.get_subscription_health(table_name)
                        assert health is not None
            except Exception as e:
                errors.append(e)
        
        # Run concurrent access
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=record_data, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should complete without errors
        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        
        # Should have data for all threads
        all_health = metrics.get_all_subscription_health()
        assert len(all_health) == 5


class TestWebSocketClientErrors:
    """Test WebSocket client error scenarios."""
    
    def test_send_message_when_disconnected(self):
        """Test sending message when not connected."""
        
        client = WebSocketClient()
        # Client starts disconnected
        assert client.state.value == "disconnected"
        
        test_message = {
            "CallReducer": {
                "reducer": "test",
                "args": {},
                "request_id": 1
            }
        }
        
        # Should raise error when trying to send while disconnected
        with pytest.raises(RuntimeError) as exc_info:
            client.send_message(test_message)
        
        assert "not connected" in str(exc_info.value).lower()
    
    def test_callback_errors_dont_break_processing(self):
        """Test that errors in callbacks don't break message processing."""
        
        client = WebSocketClient()
        
        def failing_callback(event_type: str, data: Any):
            raise Exception("Callback error")
        
        # Add failing callback
        client.add_subscription_state_callback(failing_callback)
        
        # Should handle callback error gracefully
        mock_message = Mock()
        client._notify_subscription_state_callbacks(mock_message)
        
        # Processing should continue (no exception raised)
    
    def test_protocol_mismatch_detection(self):
        """Test detection and warning of protocol mismatches."""
        
        client = WebSocketClient(protocol="v1.bsatn.spacetimedb")  # Binary protocol
        
        # Simulate receiving text message when binary expected
        with patch.object(client.logger, 'warning') as mock_warning:
            # Mock the _on_ws_message processing
            client._on_ws_message(None, '{"test": "json_data"}')  # Text message
            
            # Should have logged protocol mismatch warning
            mock_warning.assert_called()
            warning_messages = [call[0][0] for call in mock_warning.call_args_list]
            assert any("protocol mismatch" in msg.lower() for msg in warning_messages)


class TestEdgeCases:
    """Test various edge cases and boundary conditions."""
    
    def test_heartbeat_message_creation(self):
        """Test heartbeat message creation under various conditions."""
        
        heartbeat_manager = SpacetimeDBHeartbeatManager()
        
        # Should create valid heartbeat
        heartbeat = heartbeat_manager.create_heartbeat_message()
        assert "OneOffQuery" in heartbeat
        assert "message_id" in heartbeat["OneOffQuery"]
        assert "query_string" in heartbeat["OneOffQuery"]
        
        # Should validate as proper SpacetimeDB message
        assert SpacetimeDBMessageValidator.validate_message(heartbeat)
        
        # Connection test message
        test_message = heartbeat_manager.create_connection_test_message()
        assert "OneOffQuery" in test_message
        assert SpacetimeDBMessageValidator.validate_message(test_message)
    
    def test_empty_subscription_data(self):
        """Test handling of empty subscription data."""
        
        metrics = SubscriptionMetrics()
        
        # Request health for non-existent table
        health = metrics.get_subscription_health("nonexistent_table")
        assert health['status'] == 'no_data'
        
        # Get all health when no data exists
        all_health = metrics.get_all_subscription_health()
        assert len(all_health) == 0
    
    def test_rapid_connect_disconnect_cycles(self):
        """Test rapid connect/disconnect cycles."""
        
        client = WebSocketClient()
        
        # Simulate rapid state changes
        for i in range(10):
            client.state = client.state.CONNECTING
            client.state = client.state.CONNECTED
            client.state = client.state.DISCONNECTED
        
        # Should handle state changes without errors
        assert client.state.value == "disconnected"
    
    def test_large_number_of_subscription_callbacks(self):
        """Test performance with large number of subscription callbacks."""
        
        client = WebSocketClient()
        
        # Add many callbacks
        callbacks = []
        for i in range(1000):
            def callback(event_type: str, data: Any, callback_id=i):
                pass
            callbacks.append(callback)
            client.add_subscription_state_callback(callback)
        
        assert len(client.subscription_state_callbacks) == 1000
        
        # Should handle notification to all callbacks
        mock_message = Mock()
        start_time = time.time()
        client._notify_subscription_state_callbacks(mock_message)
        end_time = time.time()
        
        # Should complete quickly even with many callbacks
        assert (end_time - start_time) < 1.0


if __name__ == "__main__":
    # Run error scenario tests
    pytest.main([__file__, "-v", "--tb=short"])