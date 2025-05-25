"""
Test the logger module for SpacetimeDB Python SDK.
"""

import json
import pytest
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from spacetimedb_sdk.logger import (
    LogLevel, LogContext, JSONFormatter, TextFormatter, ColoredTextFormatter,
    ConsoleHandler, FileHandler, MemoryHandler, SamplingHandler,
    SpacetimeDBLogger, configure_default_logging, get_logger
)
from spacetimedb_sdk.connection_id import EnhancedConnectionId, EnhancedIdentity
from spacetimedb_sdk.query_id import QueryId


class TestLogContext:
    """Test LogContext functionality."""
    
    def test_log_context_creation(self):
        """Test creating a log context."""
        ctx = LogContext(
            connection_id="conn123",
            identity="identity456",
            request_id="req789",
            extra={"user": "alice", "action": "login"}
        )
        
        assert ctx.connection_id == "conn123"
        assert ctx.identity == "identity456"
        assert ctx.request_id == "req789"
        assert ctx.extra["user"] == "alice"
        assert ctx.extra["action"] == "login"
    
    def test_log_context_to_dict(self):
        """Test converting context to dictionary."""
        ctx = LogContext(
            connection_id="conn123",
            table_name="users",
            duration_ms=42.5,
            extra={"count": 10}
        )
        
        result = ctx.to_dict()
        assert result["connection_id"] == "conn123"
        assert result["table_name"] == "users"
        assert result["duration_ms"] == 42.5
        assert result["count"] == 10
        assert "identity" not in result  # None values excluded


class TestFormatters:
    """Test log formatters."""
    
    def test_json_formatter(self):
        """Test JSON formatter."""
        formatter = JSONFormatter()
        ctx = LogContext(connection_id="test123", extra={"key": "value"})
        timestamp = time.time()
        
        result = formatter.format(LogLevel.INFO, "Test message", ctx, timestamp)
        
        # Parse JSON
        data = json.loads(result)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["connection_id"] == "test123"
        assert data["key"] == "value"
        assert "timestamp" in data
        assert "timestamp_ms" in data
    
    def test_json_formatter_no_timestamp(self):
        """Test JSON formatter without timestamp."""
        formatter = JSONFormatter(include_timestamp=False)
        ctx = LogContext()
        
        result = formatter.format(LogLevel.DEBUG, "Debug", ctx, time.time())
        
        data = json.loads(result)
        assert data["level"] == "DEBUG"
        assert data["message"] == "Debug"
        assert "timestamp" not in data
        assert "timestamp_ms" not in data
    
    def test_text_formatter(self):
        """Test text formatter."""
        formatter = TextFormatter()
        ctx = LogContext(operation="test.op", duration_ms=15.5)
        timestamp = time.time()
        
        result = formatter.format(LogLevel.WARNING, "Warning!", ctx, timestamp)
        
        assert "[WARNING ]" in result
        assert "Warning!" in result
        assert "operation=test.op" in result
        assert "duration_ms=15.5" in result
    
    def test_text_formatter_no_context(self):
        """Test text formatter without context."""
        formatter = TextFormatter(include_context=False)
        ctx = LogContext(operation="test.op")
        
        result = formatter.format(LogLevel.ERROR, "Error", ctx, time.time())
        
        assert "[ERROR   ]" in result
        assert "Error" in result
        assert "operation=" not in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_colored_formatter(self, mock_isatty):
        """Test colored text formatter."""
        formatter = ColoredTextFormatter()
        ctx = LogContext()
        
        # Test different levels
        result_debug = formatter.format(LogLevel.DEBUG, "Debug", ctx, time.time())
        assert "\033[36m" in result_debug  # Cyan
        assert "\033[0m" in result_debug   # Reset
        
        result_error = formatter.format(LogLevel.ERROR, "Error", ctx, time.time())
        assert "\033[31m" in result_error  # Red
    
    @patch('sys.stdout.isatty', return_value=False)
    def test_colored_formatter_no_tty(self, mock_isatty):
        """Test colored formatter when not a TTY."""
        formatter = ColoredTextFormatter()
        ctx = LogContext()
        
        result = formatter.format(LogLevel.INFO, "Info", ctx, time.time())
        assert "\033[" not in result  # No color codes


class TestHandlers:
    """Test log handlers."""
    
    def test_console_handler(self, capsys):
        """Test console handler."""
        handler = ConsoleHandler(formatter=TextFormatter(include_context=False))
        ctx = LogContext()
        
        handler.handle(LogLevel.INFO, "Test message", ctx, time.time())
        
        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert "[INFO    ]" in captured.out
    
    def test_console_handler_min_level(self, capsys):
        """Test console handler minimum level."""
        handler = ConsoleHandler(min_level=LogLevel.WARNING)
        ctx = LogContext()
        
        # Should not log
        handler.handle(LogLevel.DEBUG, "Debug", ctx, time.time())
        handler.handle(LogLevel.INFO, "Info", ctx, time.time())
        
        # Should log
        handler.handle(LogLevel.WARNING, "Warning", ctx, time.time())
        handler.handle(LogLevel.ERROR, "Error", ctx, time.time())
        
        captured = capsys.readouterr()
        assert "Debug" not in captured.out
        assert "Info" not in captured.out
        assert "Warning" in captured.out
        assert "Error" in captured.out
    
    def test_file_handler(self):
        """Test file handler."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            filename = f.name
        
        try:
            handler = FileHandler(filename, formatter=JSONFormatter())
            ctx = LogContext(extra={"test_id": 123})
            
            handler.handle(LogLevel.INFO, "Test 1", ctx, time.time())
            handler.handle(LogLevel.ERROR, "Test 2", ctx, time.time())
            
            handler.close()
            
            # Read file
            content = Path(filename).read_text()
            lines = content.strip().split('\n')
            
            assert len(lines) == 2
            
            data1 = json.loads(lines[0])
            assert data1["message"] == "Test 1"
            assert data1["level"] == "INFO"
            assert data1["test_id"] == 123
            
            data2 = json.loads(lines[1])
            assert data2["message"] == "Test 2"
            assert data2["level"] == "ERROR"
        
        finally:
            Path(filename).unlink(missing_ok=True)
    
    def test_memory_handler(self):
        """Test memory handler."""
        handler = MemoryHandler(max_entries=3)
        ctx = LogContext()
        
        # Add entries
        for i in range(5):
            handler.handle(LogLevel.INFO, f"Message {i}", ctx, time.time())
        
        entries = handler.get_entries()
        assert len(entries) == 3
        assert "Message 2" in entries[0]
        assert "Message 3" in entries[1]
        assert "Message 4" in entries[2]
        
        # Clear
        handler.clear()
        assert len(handler.get_entries()) == 0
    
    def test_sampling_handler(self):
        """Test sampling handler."""
        memory_handler = MemoryHandler()
        handler = SamplingHandler(memory_handler, sample_rate=0.5)
        ctx = LogContext()
        
        # Mock random to control sampling
        with patch('random.random') as mock_random:
            # First call sampled (0.3 < 0.5)
            mock_random.return_value = 0.3
            handler.handle(LogLevel.INFO, "Sampled", ctx, time.time())
            
            # Second call not sampled (0.7 > 0.5)
            mock_random.return_value = 0.7
            handler.handle(LogLevel.INFO, "Not sampled", ctx, time.time())
            
            # Error always logged
            mock_random.return_value = 0.9
            handler.handle(LogLevel.ERROR, "Error", ctx, time.time())
        
        entries = memory_handler.get_entries()
        assert len(entries) == 2
        assert "Sampled" in entries[0]
        assert "Error" in entries[1]
        
        # Check counts
        counts = handler.get_counts()
        assert counts["INFO:Sampled"] == 1
        assert counts["INFO:Not sampled"] == 1
        assert counts["ERROR:Error"] == 1


class TestSpacetimeDBLogger:
    """Test main logger class."""
    
    def test_logger_creation(self):
        """Test creating a logger."""
        logger = SpacetimeDBLogger("test", LogLevel.WARNING)
        
        assert logger.name == "test"
        assert logger.default_level == LogLevel.WARNING
        assert len(logger.handlers) == 0
        assert logger._debug_mode is False
    
    def test_logger_handlers(self):
        """Test adding/removing handlers."""
        logger = SpacetimeDBLogger()
        handler1 = MemoryHandler()
        handler2 = MemoryHandler()
        
        logger.add_handler(handler1)
        logger.add_handler(handler2)
        assert len(logger.handlers) == 2
        
        logger.remove_handler(handler1)
        assert len(logger.handlers) == 1
        assert logger.handlers[0] is handler2
    
    def test_logger_levels(self):
        """Test log levels."""
        logger = SpacetimeDBLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)
        
        logger.set_level(LogLevel.WARNING)
        
        logger.debug("Debug")
        logger.info("Info")
        logger.warning("Warning")
        logger.error("Error")
        logger.critical("Critical")
        
        entries = handler.get_entries()
        assert len(entries) == 3
        assert "Warning" in entries[0]
        assert "Error" in entries[1]
        assert "Critical" in entries[2]
    
    def test_logger_context(self):
        """Test contextual logging."""
        logger = SpacetimeDBLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)
        
        with logger.context(connection_id="conn123", module_name="test"):
            logger.info("With context")
            
            with logger.context(request_id="req456"):
                logger.info("Nested context")
        
        logger.info("No context")
        
        entries = handler.get_entries()
        
        # Check first entry
        assert "connection_id=conn123" in entries[0]
        assert "module_name=test" in entries[0]
        
        # Check nested entry
        assert "connection_id=conn123" in entries[1]
        assert "module_name=test" in entries[1]
        assert "request_id=req456" in entries[1]
        
        # Check no context
        assert "connection_id=" not in entries[2]
    
    def test_logger_debug_mode(self):
        """Test debug mode."""
        logger = SpacetimeDBLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)
        
        logger.set_debug_mode(True)
        assert logger._debug_mode is True
        assert logger.default_level == LogLevel.DEBUG
        
        logger.debug("Debug message")
        entries = handler.get_entries()
        assert len(entries) == 1
        assert "Debug message" in entries[0]
    
    def test_logger_redaction(self):
        """Test sensitive data redaction."""
        logger = SpacetimeDBLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)
        
        # Log with sensitive data
        logger.info("Login", extra={
            "username": "alice",
            "password": "secret123",
            "auth_token": "abcdef123456789012345",
            "api_key": "xyz789"
        })
        
        entries = handler.get_entries()
        assert "password=[REDACTED]" in entries[0]
        assert "auth_token=[REDACTED]" in entries[0]
        assert "api_key=[REDACTED]" in entries[0]
        assert "username=alice" in entries[0]
    
    def test_logger_specialized_events(self):
        """Test specialized event logging."""
        logger = SpacetimeDBLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)
        logger.set_debug_mode(True)  # Enable debug mode to capture table events
        
        # Connection event
        conn_id = EnhancedConnectionId(b'1234567890123456')
        identity = EnhancedIdentity(b'abcdefghijklmnopqrstuvwxyz012345')
        logger.connection_event("connected", conn_id, identity, version="1.0")
        
        # Subscription event
        query_id = QueryId.generate()
        logger.subscription_event("created", query_id, ["SELECT * FROM users"])
        
        # Reducer event
        logger.reducer_event("called", "create_user", "req123", ["alice"])
        
        # Table event
        logger.table_event("insert", "users", row_count=5)
        
        entries = handler.get_entries()
        assert len(entries) == 4
        
        assert "Connection connected" in entries[0]
        assert "connection_id=" in entries[0]
        
        assert "Subscription created" in entries[1]
        assert "query_id=" in entries[1]
        
        assert "Reducer called: create_user" in entries[2]
        assert "reducer_name=create_user" in entries[2]
        
        assert "Table insert: users" in entries[3]
    
    def test_logger_performance(self):
        """Test performance logging."""
        logger = SpacetimeDBLogger()
        handler = MemoryHandler()
        logger.add_handler(handler)
        logger.set_debug_mode(True)
        
        # Fast operation
        with logger.performance("fast_op"):
            time.sleep(0.01)
        
        # Slow operation
        with logger.performance("slow_op"):
            time.sleep(0.15)
        
        entries = handler.get_entries()
        assert len(entries) == 2
        
        assert "Operation completed: fast_op" in entries[0]
        assert "Slow operation: slow_op" in entries[1]
        
        # Check metrics
        metrics = logger.get_performance_metrics()
        assert "fast_op" in metrics
        assert "slow_op" in metrics
        assert metrics["slow_op"]["max_ms"] > 100
    
    def test_logger_error_handling(self, capsys):
        """Test logger handles handler errors gracefully."""
        logger = SpacetimeDBLogger()
        
        # Add a broken handler
        class BrokenHandler(MemoryHandler):
            def write(self, formatted):
                raise RuntimeError("Handler error")
        
        logger.add_handler(BrokenHandler())
        logger.add_handler(MemoryHandler())  # Good handler
        
        # Should not raise
        logger.info("Test message")
        
        captured = capsys.readouterr()
        assert "Error in log handler" in captured.err


class TestLoggerConfiguration:
    """Test logger configuration."""
    
    def test_configure_default_logging(self):
        """Test default logging configuration."""
        # Basic config
        logger = configure_default_logging()
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], ConsoleHandler)
        assert logger._debug_mode is False
        
        # Debug mode
        logger = configure_default_logging(debug=True)
        assert logger._debug_mode is True
        assert logger.default_level == LogLevel.DEBUG
    
    def test_configure_with_file(self):
        """Test configuration with file logging."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name
        
        try:
            logger = configure_default_logging(log_file=filename)
            assert len(logger.handlers) == 2
            
            # Find file handler
            file_handler = None
            for handler in logger.handlers:
                if isinstance(handler, FileHandler):
                    file_handler = handler
                    break
            
            assert file_handler is not None
            assert isinstance(file_handler.formatter, JSONFormatter)
            
            # Log something
            logger.info("Test log")
            
            # Close file handler
            file_handler.close()
            
            # Check file
            content = Path(filename).read_text()
            assert "Test log" in content
        
        finally:
            Path(filename).unlink(missing_ok=True)
    
    def test_get_logger(self):
        """Test getting logger instance."""
        logger1 = get_logger()
        logger2 = get_logger("test")
        
        # Should return same global instance for now
        assert logger1 is logger2


class TestIntegration:
    """Integration tests."""
    
    def test_full_logging_scenario(self):
        """Test a full logging scenario."""
        # Create logger with multiple handlers
        logger = SpacetimeDBLogger("integration")
        
        # Memory handler for testing
        memory_handler = MemoryHandler()
        logger.add_handler(memory_handler)
        
        # Sampling handler
        sampled_memory = MemoryHandler()
        sampling_handler = SamplingHandler(sampled_memory, sample_rate=1.0)
        logger.add_handler(sampling_handler)
        
        # Set debug mode
        logger.set_debug_mode(True)
        
        # Simulate connection lifecycle
        conn_id = EnhancedConnectionId(b'test_connection_')
        identity = EnhancedIdentity(b'test_identity_test_identity_test')
        
        with logger.context(module_name="chat_app"):
            logger.connection_event("connecting", conn_id)
            
            with logger.performance("connection.establish"):
                time.sleep(0.02)
                logger.connection_event("connected", conn_id, identity)
            
            # Subscribe
            query_id = QueryId.generate()
            logger.subscription_event("subscribing", query_id,
                                    ["SELECT * FROM messages", "SELECT * FROM users"])
            
            # Table operations
            with logger.performance("table.bulk_insert"):
                for i in range(10):
                    logger.table_event("insert", "messages", row_count=1)
            
            # Reducer call
            logger.reducer_event("calling", "send_message", "req123",
                               ["room1", "Hello!"])
            
            # Error
            logger.error("Connection lost", error_type="NetworkError",
                        extra={"retry_count": 3})
        
        # Check results
        entries = memory_handler.get_entries()
        assert len(entries) > 10
        
        # Check performance metrics
        metrics = logger.get_performance_metrics()
        assert "connection.establish" in metrics
        assert "table.bulk_insert" in metrics
        
        # Log summary
        logger.log_metrics_summary()
        
        # Check sampling
        sample_counts = sampling_handler.get_counts()
        assert len(sample_counts) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 