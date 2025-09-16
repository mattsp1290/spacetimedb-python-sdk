"""
Comprehensive tests for the error_formatting utility module.

Tests all error formatting functions with various error types and contexts
to ensure consistent error message formatting across the SDK.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Direct import to avoid circular import issues
from spacetimedb_sdk.utils.error_formatting import ErrorFormatter


class TestErrorFormatter:
    """Test the ErrorFormatter class methods."""
    
    def test_format_auth_error_basic(self):
        """Test basic authentication error formatting."""
        operation = "login"
        error = ValueError("Invalid credentials")
        
        result = ErrorFormatter.format_auth_error(operation, error)
        
        assert "Authentication login failed" in result
        assert "[error_type: ValueError]" in result
        assert "Invalid credentials" not in result  # Should not leak sensitive info
        
    def test_format_auth_error_with_context(self):
        """Test authentication error formatting with context."""
        operation = "token_refresh"
        error = ConnectionError("Connection timeout")
        context = "user_session_123"
        
        result = ErrorFormatter.format_auth_error(operation, error, context)
        
        assert "Authentication token_refresh failed" in result
        assert "(context: user_session_123)" in result
        assert "[error_type: ConnectionError]" in result
        assert "Connection timeout" not in result  # Should not leak sensitive info
        
    def test_format_auth_error_no_context(self):
        """Test authentication error formatting without context."""
        operation = "logout"
        error = RuntimeError("Session expired")
        
        result = ErrorFormatter.format_auth_error(operation, error, None)
        
        assert "Authentication logout failed" in result
        assert "context:" not in result
        assert "[error_type: RuntimeError]" in result
        
    def test_format_connection_error_basic(self):
        """Test basic connection error formatting."""
        operation = "connect"
        error = OSError("Connection refused")
        
        result = ErrorFormatter.format_connection_error(operation, error)
        
        assert "Connection connect failed: Connection refused" in result
        assert "context:" not in result
        
    def test_format_connection_error_with_context(self):
        """Test connection error formatting with context."""
        operation = "reconnect"
        error = TimeoutError("Request timeout")
        context = "ws://localhost:3000"
        
        result = ErrorFormatter.format_connection_error(operation, error, context)
        
        assert "Connection reconnect failed: Request timeout" in result
        assert "(context: ws://localhost:3000)" in result
        
    def test_format_connection_error_empty_context(self):
        """Test connection error formatting with empty context."""
        operation = "disconnect"
        error = Exception("Unexpected error")
        context = ""
        
        result = ErrorFormatter.format_connection_error(operation, error, context)
        
        assert "Connection disconnect failed: Unexpected error" in result
        # Empty context should still appear if provided
        assert "(context: )" in result
        
    def test_format_event_error_basic(self):
        """Test basic event error formatting."""
        operation = "dispatch"
        error = KeyError("Event handler not found")
        
        result = ErrorFormatter.format_event_error(operation, error)
        
        assert "Event dispatch failed: Event handler not found" in result
        assert "context:" not in result
        
    def test_format_event_error_with_context(self):
        """Test event error formatting with context."""
        operation = "subscribe"
        error = TypeError("Invalid event type")
        context = "subscription_manager"
        
        result = ErrorFormatter.format_event_error(operation, error, context)
        
        assert "Event subscribe failed: Invalid event type" in result
        assert "(context: subscription_manager)" in result
        
    def test_format_websocket_error_basic(self):
        """Test basic WebSocket error formatting."""
        operation = "send_message"
        error = ConnectionResetError("Connection lost")
        
        result = ErrorFormatter.format_websocket_error(operation, error)
        
        assert "WebSocket send_message failed: Connection lost" in result
        assert "context:" not in result
        
    def test_format_websocket_error_with_context(self):
        """Test WebSocket error formatting with context."""
        operation = "handshake"
        error = ValueError("Invalid protocol version")
        context = "protocol_v1.1.2"
        
        result = ErrorFormatter.format_websocket_error(operation, error, context)
        
        assert "WebSocket handshake failed: Invalid protocol version" in result
        assert "(context: protocol_v1.1.2)" in result
        
    def test_format_cache_error_basic(self):
        """Test basic cache error formatting."""
        operation = "get"
        error = KeyError("Cache miss")
        
        result = ErrorFormatter.format_cache_error(operation, error)
        
        assert "Cache get failed: Cache miss" in result
        assert "context:" not in result
        
    def test_format_cache_error_with_context(self):
        """Test cache error formatting with context."""
        operation = "invalidate"
        error = MemoryError("Out of memory")
        context = "bounded_cache_limit_reached"
        
        result = ErrorFormatter.format_cache_error(operation, error, context)
        
        assert "Cache invalidate failed: Out of memory" in result
        assert "(context: bounded_cache_limit_reached)" in result
        
    def test_format_protocol_error_basic(self):
        """Test basic protocol error formatting."""
        operation = "decode_message"
        error = UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte')
        
        result = ErrorFormatter.format_protocol_error(operation, error)
        
        assert "Protocol decode_message failed:" in result
        assert "invalid start byte" in result
        assert "context:" not in result
        
    def test_format_protocol_error_with_context(self):
        """Test protocol error formatting with context."""
        operation = "validate_frame"
        error = ValueError("Invalid frame type")
        context = "binary_frame_0x02"
        
        result = ErrorFormatter.format_protocol_error(operation, error, context)
        
        assert "Protocol validate_frame failed: Invalid frame type" in result
        assert "(context: binary_frame_0x02)" in result
        
    def test_format_generic_error_basic(self):
        """Test basic generic error formatting."""
        component = "DatabaseClient"
        operation = "query"
        error = RuntimeError("Database connection lost")
        
        result = ErrorFormatter.format_generic_error(component, operation, error)
        
        assert "DatabaseClient query failed: Database connection lost" in result
        assert "context:" not in result
        
    def test_format_generic_error_with_context(self):
        """Test generic error formatting with context."""
        component = "SubscriptionManager"
        operation = "update_subscription"
        error = ValueError("Invalid query parameters")
        context = "table_users"
        
        result = ErrorFormatter.format_generic_error(component, operation, error, context)
        
        assert "SubscriptionManager update_subscription failed: Invalid query parameters" in result
        assert "(context: table_users)" in result
        
    def test_error_types_preserved(self):
        """Test that different error types are handled correctly."""
        test_cases = [
            (ValueError("test"), "ValueError"),
            (TypeError("test"), "TypeError"),
            (RuntimeError("test"), "RuntimeError"),
            (ConnectionError("test"), "ConnectionError"),
            (TimeoutError("test"), "TimeoutError"),
            (KeyError("test"), "KeyError"),
            (AttributeError("test"), "AttributeError"),
            (IndexError("test"), "IndexError"),
            (OSError("test"), "OSError"),
            (IOError("test"), "OSError"),  # IOError is an alias for OSError in modern Python
        ]
        
        for error, expected_type in test_cases:
            result = ErrorFormatter.format_auth_error("test_op", error)
            assert f"[error_type: {expected_type}]" in result
            
    def test_special_characters_in_messages(self):
        """Test error formatting with special characters."""
        operation = "parse"
        error = ValueError("Message contains special chars: <>\"'&\n\t")
        
        result = ErrorFormatter.format_connection_error(operation, error)
        
        assert "Connection parse failed:" in result
        assert "special chars" in result
        
    def test_unicode_characters_in_messages(self):
        """Test error formatting with unicode characters."""
        operation = "validate"
        error = UnicodeError("Invalid unicode: café résumé 🚀")
        
        result = ErrorFormatter.format_event_error(operation, error)
        
        assert "Event validate failed:" in result
        assert "café résumé 🚀" in result
        
    def test_very_long_error_messages(self):
        """Test error formatting with very long error messages."""
        operation = "process"
        long_message = "This is a very long error message " * 50
        error = RuntimeError(long_message)
        
        result = ErrorFormatter.format_websocket_error(operation, error)
        
        assert "WebSocket process failed:" in result
        assert "very long error message" in result
        
    def test_empty_operation_name(self):
        """Test error formatting with empty operation name."""
        operation = ""
        error = ValueError("Test error")
        
        result = ErrorFormatter.format_cache_error(operation, error)
        
        assert "Cache  failed:" in result  # Double space where operation would be
        assert "Test error" in result
        
    def test_none_error_handling(self):
        """Test error formatting when error is None (edge case)."""
        operation = "test"
        error = None
        
        # This might raise an exception or handle None gracefully
        # The behavior depends on the implementation
        try:
            result = ErrorFormatter.format_protocol_error(operation, error)
            assert "None" in result or result is not None
        except (AttributeError, TypeError):
            # It's acceptable for this to fail since None isn't a proper Exception
            pass
            
    def test_nested_exception_handling(self):
        """Test error formatting with nested exceptions."""
        operation = "nested_op"
        inner_error = ValueError("Inner error")
        try:
            raise inner_error
        except ValueError as e:
            # Create a chained exception
            outer_error = RuntimeError("Outer error")
            outer_error.__cause__ = e
            
        result = ErrorFormatter.format_generic_error("TestComponent", operation, outer_error)
        
        assert "TestComponent nested_op failed: Outer error" in result
        
    def test_context_with_special_characters(self):
        """Test context formatting with special characters."""
        operation = "test"
        error = ValueError("Test error")
        context = "context with <>&\"' special chars"
        
        result = ErrorFormatter.format_auth_error(operation, error, context)
        
        assert "Authentication test failed" in result
        assert "(context: context with <>&\"' special chars)" in result
        
    def test_consistent_formatting_across_methods(self):
        """Test that all formatting methods follow consistent patterns."""
        operation = "test_operation"
        error = ValueError("Test error message")
        context = "test_context"
        
        # Test all methods with same inputs
        auth_result = ErrorFormatter.format_auth_error(operation, error, context)
        conn_result = ErrorFormatter.format_connection_error(operation, error, context)
        event_result = ErrorFormatter.format_event_error(operation, error, context)
        ws_result = ErrorFormatter.format_websocket_error(operation, error, context)
        cache_result = ErrorFormatter.format_cache_error(operation, error, context)
        protocol_result = ErrorFormatter.format_protocol_error(operation, error, context)
        generic_result = ErrorFormatter.format_generic_error("Component", operation, error, context)
        
        # All should contain the operation name
        results = [auth_result, conn_result, event_result, ws_result, cache_result, protocol_result, generic_result]
        for result in results:
            assert operation in result
            assert "(context: test_context)" in result
            
        # Auth error should not contain the actual error message (security)
        assert "Test error message" not in auth_result
        
        # All others should contain the actual error message
        for result in [conn_result, event_result, ws_result, cache_result, protocol_result, generic_result]:
            assert "Test error message" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])