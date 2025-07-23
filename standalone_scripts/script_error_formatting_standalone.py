#!/usr/bin/env python3
"""
Standalone comprehensive tests for the error_formatting utility module.

This test file is designed to work around circular import issues and 
test the error formatting utility in isolation.
"""

import sys
import os
from pathlib import Path

# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Direct import to avoid circular import issues
try:
    from spacetimedb_sdk.utils.error_formatting import ErrorFormatter
    print("✅ Successfully imported ErrorFormatter")
except ImportError as e:
    print(f"❌ Failed to import ErrorFormatter: {e}")
    sys.exit(1)


def test_format_auth_error_basic():
    """Test basic authentication error formatting."""
    operation = "login"
    error = ValueError("Invalid credentials")
    
    result = ErrorFormatter.format_auth_error(operation, error)
    
    assert "Authentication login failed" in result
    assert "[error_type: ValueError]" in result
    assert "Invalid credentials" not in result  # Should not leak sensitive info
    print("✅ test_format_auth_error_basic passed")


def test_format_auth_error_with_context():
    """Test authentication error formatting with context."""
    operation = "token_refresh"
    error = ConnectionError("Connection timeout")
    context = "user_session_123"
    
    result = ErrorFormatter.format_auth_error(operation, error, context)
    
    assert "Authentication token_refresh failed" in result
    assert "(context: user_session_123)" in result
    assert "[error_type: ConnectionError]" in result
    assert "Connection timeout" not in result  # Should not leak sensitive info
    print("✅ test_format_auth_error_with_context passed")


def test_format_connection_error_basic():
    """Test basic connection error formatting."""
    operation = "connect"
    error = OSError("Connection refused")
    
    result = ErrorFormatter.format_connection_error(operation, error)
    
    assert "Connection connect failed: Connection refused" in result
    assert "context:" not in result
    print("✅ test_format_connection_error_basic passed")


def test_format_connection_error_with_context():
    """Test connection error formatting with context."""
    operation = "reconnect"
    error = TimeoutError("Request timeout")
    context = "ws://localhost:3000"
    
    result = ErrorFormatter.format_connection_error(operation, error, context)
    
    assert "Connection reconnect failed: Request timeout" in result
    assert "(context: ws://localhost:3000)" in result
    print("✅ test_format_connection_error_with_context passed")


def test_format_event_error_basic():
    """Test basic event error formatting."""
    operation = "dispatch"
    error = KeyError("Event handler not found")
    
    result = ErrorFormatter.format_event_error(operation, error)
    
    assert "Event dispatch failed: Event handler not found" in result
    assert "context:" not in result
    print("✅ test_format_event_error_basic passed")


def test_format_websocket_error_basic():
    """Test basic WebSocket error formatting."""
    operation = "send_message"
    error = ConnectionResetError("Connection lost")
    
    result = ErrorFormatter.format_websocket_error(operation, error)
    
    assert "WebSocket send_message failed: Connection lost" in result
    assert "context:" not in result
    print("✅ test_format_websocket_error_basic passed")


def test_format_cache_error_basic():
    """Test basic cache error formatting."""
    operation = "get"
    error = KeyError("Cache miss")
    
    result = ErrorFormatter.format_cache_error(operation, error)
    
    assert "Cache get failed: Cache miss" in result
    assert "context:" not in result
    print("✅ test_format_cache_error_basic passed")


def test_format_protocol_error_basic():
    """Test basic protocol error formatting."""
    operation = "decode_message"
    error = UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte')
    
    result = ErrorFormatter.format_protocol_error(operation, error)
    
    assert "Protocol decode_message failed:" in result
    assert "invalid start byte" in result
    assert "context:" not in result
    print("✅ test_format_protocol_error_basic passed")


def test_format_generic_error_basic():
    """Test basic generic error formatting."""
    component = "DatabaseClient"
    operation = "query"
    error = RuntimeError("Database connection lost")
    
    result = ErrorFormatter.format_generic_error(component, operation, error)
    
    assert "DatabaseClient query failed: Database connection lost" in result
    assert "context:" not in result
    print("✅ test_format_generic_error_basic passed")


def test_format_generic_error_with_context():
    """Test generic error formatting with context."""
    component = "SubscriptionManager"
    operation = "update_subscription"
    error = ValueError("Invalid query parameters")
    context = "table_users"
    
    result = ErrorFormatter.format_generic_error(component, operation, error, context)
    
    assert "SubscriptionManager update_subscription failed: Invalid query parameters" in result
    assert "(context: table_users)" in result
    print("✅ test_format_generic_error_with_context passed")


def test_error_types_preserved():
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
        (IOError("test"), "IOError"),
    ]
    
    for error, expected_type in test_cases:
        result = ErrorFormatter.format_auth_error("test_op", error)
        assert f"[error_type: {expected_type}]" in result
    
    print("✅ test_error_types_preserved passed")


def test_special_characters_in_messages():
    """Test error formatting with special characters."""
    operation = "parse"
    error = ValueError("Message contains special chars: <>\"'&\n\t")
    
    result = ErrorFormatter.format_connection_error(operation, error)
    
    assert "Connection parse failed:" in result
    assert "special chars" in result
    print("✅ test_special_characters_in_messages passed")


def test_unicode_characters_in_messages():
    """Test error formatting with unicode characters."""
    operation = "validate"
    error = UnicodeError("Invalid unicode: café résumé 🚀")
    
    result = ErrorFormatter.format_event_error(operation, error)
    
    assert "Event validate failed:" in result
    assert "café résumé 🚀" in result
    print("✅ test_unicode_characters_in_messages passed")


def test_very_long_error_messages():
    """Test error formatting with very long error messages."""
    operation = "process"
    long_message = "This is a very long error message " * 50
    error = RuntimeError(long_message)
    
    result = ErrorFormatter.format_websocket_error(operation, error)
    
    assert "WebSocket process failed:" in result
    assert "very long error message" in result
    print("✅ test_very_long_error_messages passed")


def test_empty_operation_name():
    """Test error formatting with empty operation name."""
    operation = ""
    error = ValueError("Test error")
    
    result = ErrorFormatter.format_cache_error(operation, error)
    
    assert "Cache  failed:" in result  # Double space where operation would be
    assert "Test error" in result
    print("✅ test_empty_operation_name passed")


def test_context_with_special_characters():
    """Test context formatting with special characters."""
    operation = "test"
    error = ValueError("Test error")
    context = "context with <>&\"' special chars"
    
    result = ErrorFormatter.format_auth_error(operation, error, context)
    
    assert "Authentication test failed" in result
    assert "(context: context with <>&\"' special chars)" in result
    print("✅ test_context_with_special_characters passed")


def test_consistent_formatting_across_methods():
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
    
    print("✅ test_consistent_formatting_across_methods passed")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_format_auth_error_basic,
        test_format_auth_error_with_context,
        test_format_connection_error_basic,
        test_format_connection_error_with_context,
        test_format_event_error_basic,
        test_format_websocket_error_basic,
        test_format_cache_error_basic,
        test_format_protocol_error_basic,
        test_format_generic_error_basic,
        test_format_generic_error_with_context,
        test_error_types_preserved,
        test_special_characters_in_messages,
        test_unicode_characters_in_messages,
        test_very_long_error_messages,
        test_empty_operation_name,
        test_context_with_special_characters,
        test_consistent_formatting_across_methods,
    ]
    
    passed = 0
    failed = 0
    
    print(f"\n🧪 Running {len(tests)} tests for ErrorFormatter...")
    print("=" * 60)
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Error formatting utility has excellent test coverage.")
        return True
    else:
        print("⚠️ Some tests failed. Check the implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)