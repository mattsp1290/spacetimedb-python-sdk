"""
Structured logging support for SpacetimeDB Python SDK.

Provides:
- Configurable log levels and formatting
- Contextual logging with request/connection tracking
- Performance logging and metrics
- Production-ready features (sampling, security)
"""

import json
import logging
import sys
import time
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from pathlib import Path
import uuid

from .connection_id import EnhancedConnectionId, EnhancedIdentity
from .query_id import QueryId


class LogLevel(IntEnum):
    """Log levels matching Python's logging module."""
    DEBUG = logging.DEBUG       # 10
    INFO = logging.INFO         # 20
    WARNING = logging.WARNING   # 30
    ERROR = logging.ERROR       # 40
    CRITICAL = logging.CRITICAL # 50


@dataclass
class LogContext:
    """Context for a log entry."""
    connection_id: Optional[str] = None
    identity: Optional[str] = None
    request_id: Optional[str] = None
    query_id: Optional[str] = None
    reducer_name: Optional[str] = None
    table_name: Optional[str] = None
    module_name: Optional[str] = None
    operation: Optional[str] = None
    duration_ms: Optional[float] = None
    error_type: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if key == 'extra':
                result.update(value)
            elif value is not None:
                result[key] = value
        return result


class LogFormatter:
    """Base class for log formatters."""
    
    def format(self, level: LogLevel, message: str, context: LogContext, 
               timestamp: float) -> str:
        """Format a log entry."""
        raise NotImplementedError


class JSONFormatter(LogFormatter):
    """JSON structured log formatter."""
    
    def __init__(self, include_timestamp: bool = True):
        self.include_timestamp = include_timestamp
    
    def format(self, level: LogLevel, message: str, context: LogContext,
               timestamp: float) -> str:
        """Format log entry as JSON."""
        entry = {
            'level': level.name,
            'message': message,
            **context.to_dict()
        }
        
        if self.include_timestamp:
            entry['timestamp'] = datetime.fromtimestamp(timestamp).isoformat()
            entry['timestamp_ms'] = int(timestamp * 1000)
        
        return json.dumps(entry, default=str)


class TextFormatter(LogFormatter):
    """Human-readable text log formatter."""
    
    def __init__(self, include_context: bool = True):
        self.include_context = include_context
    
    def format(self, level: LogLevel, message: str, context: LogContext,
               timestamp: float) -> str:
        """Format log entry as text."""
        dt = datetime.fromtimestamp(timestamp)
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        parts = [f"{time_str} [{level.name:8}] {message}"]
        
        if self.include_context:
            ctx_dict = context.to_dict()
            if ctx_dict:
                ctx_str = " ".join(f"{k}={v}" for k, v in ctx_dict.items())
                parts.append(f"  Context: {ctx_str}")
        
        return "\n".join(parts)


class ColoredTextFormatter(TextFormatter):
    """Colored text formatter for terminal output."""
    
    COLORS = {
        LogLevel.DEBUG: '\033[36m',     # Cyan
        LogLevel.INFO: '\033[32m',      # Green
        LogLevel.WARNING: '\033[33m',   # Yellow
        LogLevel.ERROR: '\033[31m',     # Red
        LogLevel.CRITICAL: '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, level: LogLevel, message: str, context: LogContext,
               timestamp: float) -> str:
        """Format log entry with colors."""
        base = super().format(level, message, context, timestamp)
        
        if sys.stdout.isatty():
            color = self.COLORS.get(level, '')
            return f"{color}{base}{self.RESET}"
        
        return base


class LogHandler:
    """Base class for log handlers."""
    
    def __init__(self, formatter: Optional[LogFormatter] = None,
                 min_level: LogLevel = LogLevel.DEBUG):
        self.formatter = formatter or TextFormatter()
        self.min_level = min_level
    
    def should_log(self, level: LogLevel) -> bool:
        """Check if this level should be logged."""
        return level >= self.min_level
    
    def handle(self, level: LogLevel, message: str, context: LogContext,
               timestamp: float) -> None:
        """Handle a log entry."""
        if not self.should_log(level):
            return
        
        formatted = self.formatter.format(level, message, context, timestamp)
        self.write(formatted)
    
    def write(self, formatted: str) -> None:
        """Write formatted log entry."""
        raise NotImplementedError


class ConsoleHandler(LogHandler):
    """Handler that writes to console."""
    
    def __init__(self, stream=None, **kwargs):
        super().__init__(**kwargs)
        self.stream = stream or sys.stdout
    
    def write(self, formatted: str) -> None:
        """Write to console."""
        print(formatted, file=self.stream)
        self.stream.flush()


class FileHandler(LogHandler):
    """Handler that writes to file."""
    
    def __init__(self, filename: Union[str, Path], mode: str = 'a', **kwargs):
        super().__init__(**kwargs)
        self.filename = Path(filename)
        self.mode = mode
        self._file = None
        self._lock = threading.Lock()
    
    def write(self, formatted: str) -> None:
        """Write to file."""
        with self._lock:
            if self._file is None:
                self._file = open(self.filename, self.mode)
            
            self._file.write(formatted + '\n')
            self._file.flush()
    
    def close(self) -> None:
        """Close the file."""
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None
    
    def __del__(self):
        """Ensure file is closed."""
        self.close()


class MemoryHandler(LogHandler):
    """Handler that stores logs in memory."""
    
    def __init__(self, max_entries: int = 1000, **kwargs):
        super().__init__(**kwargs)
        self.max_entries = max_entries
        self.entries: List[str] = []
        self._lock = threading.Lock()
    
    def write(self, formatted: str) -> None:
        """Store in memory."""
        with self._lock:
            self.entries.append(formatted)
            if len(self.entries) > self.max_entries:
                self.entries.pop(0)
    
    def get_entries(self) -> List[str]:
        """Get all stored entries."""
        with self._lock:
            return self.entries.copy()
    
    def clear(self) -> None:
        """Clear stored entries."""
        with self._lock:
            self.entries.clear()


class SamplingHandler(LogHandler):
    """Handler that samples logs to reduce volume."""
    
    def __init__(self, wrapped_handler: LogHandler, sample_rate: float = 0.1,
                 always_log_errors: bool = True):
        super().__init__(min_level=wrapped_handler.min_level)
        self.wrapped_handler = wrapped_handler
        self.sample_rate = sample_rate
        self.always_log_errors = always_log_errors
        self._counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def should_log(self, level: LogLevel) -> bool:
        """Check if this entry should be sampled."""
        if not super().should_log(level):
            return False
        
        # Always log errors and above
        if self.always_log_errors and level >= LogLevel.ERROR:
            return True
        
        # Sample based on rate
        import random
        return random.random() < self.sample_rate
    
    def handle(self, level: LogLevel, message: str, context: LogContext,
               timestamp: float) -> None:
        """Handle with sampling."""
        # Track all messages
        with self._lock:
            key = f"{level.name}:{message[:50]}"
            self._counts[key] += 1
        
        # Only log if sampled
        if self.should_log(level):
            # Add sampling info to context
            context.extra['sampled'] = True
            context.extra['sample_rate'] = self.sample_rate
            
            self.wrapped_handler.handle(level, message, context, timestamp)
    
    def get_counts(self) -> Dict[str, int]:
        """Get message counts."""
        with self._lock:
            return dict(self._counts)


class SpacetimeDBLogger:
    """
    Main logger class for SpacetimeDB Python SDK.
    
    Features:
    - Multiple handlers and formatters
    - Contextual logging
    - Performance tracking
    - Log sampling
    - Thread-safe operations
    """
    
    def __init__(self, name: str = "spacetimedb", 
                 default_level: LogLevel = LogLevel.INFO):
        self.name = name
        self.default_level = default_level
        self.handlers: List[LogHandler] = []
        self._context_stack: threading.local = threading.local()
        self._performance_metrics: Dict[str, List[float]] = defaultdict(list)
        self._metrics_lock = threading.Lock()
        
        # Debug mode flag
        self._debug_mode = False
        
        # Security settings
        self._redact_patterns: Set[str] = {
            'password', 'token', 'secret', 'key', 'auth'
        }
    
    def add_handler(self, handler: LogHandler) -> None:
        """Add a log handler."""
        self.handlers.append(handler)
    
    def remove_handler(self, handler: LogHandler) -> None:
        """Remove a log handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)
    
    def set_level(self, level: LogLevel) -> None:
        """Set default log level."""
        self.default_level = level
    
    def set_debug_mode(self, enabled: bool) -> None:
        """Enable/disable debug mode."""
        self._debug_mode = enabled
        if enabled:
            self.set_level(LogLevel.DEBUG)
    
    def add_redact_pattern(self, pattern: str) -> None:
        """Add a pattern to redact from logs."""
        self._redact_patterns.add(pattern.lower())
    
    def _get_context(self) -> LogContext:
        """Get current context."""
        if not hasattr(self._context_stack, 'stack'):
            self._context_stack.stack = []
        
        # Merge all contexts in stack
        merged = LogContext()
        for ctx in self._context_stack.stack:
            for key, value in ctx.__dict__.items():
                if key == 'extra':
                    merged.extra.update(value)
                elif value is not None:
                    setattr(merged, key, value)
        
        return merged
    
    @contextmanager
    def context(self, **kwargs):
        """Context manager for adding context to logs."""
        ctx = LogContext(**kwargs)
        
        if not hasattr(self._context_stack, 'stack'):
            self._context_stack.stack = []
        
        self._context_stack.stack.append(ctx)
        try:
            yield
        finally:
            self._context_stack.stack.pop()
    
    def _redact_sensitive(self, data: Any) -> Any:
        """Redact sensitive information."""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                key_lower = key.lower()
                if any(pattern in key_lower for pattern in self._redact_patterns):
                    result[key] = "[REDACTED]"
                else:
                    result[key] = self._redact_sensitive(value)
            return result
        elif isinstance(data, (list, tuple)):
            return [self._redact_sensitive(item) for item in data]
        elif isinstance(data, str):
            # Check if string looks like a token/secret
            if len(data) > 20 and data.isalnum():
                return "[REDACTED]"
        return data
    
    def _log(self, level: LogLevel, message: str, **context_kwargs) -> None:
        """Internal log method."""
        if level < self.default_level:
            return
        
        # Get context
        ctx = self._get_context()
        
        # Add any additional context
        for key, value in context_kwargs.items():
            if key == 'extra':
                ctx.extra.update(value)
            else:
                setattr(ctx, key, value)
        
        # Redact sensitive data
        ctx_dict = ctx.to_dict()
        ctx_dict = self._redact_sensitive(ctx_dict)
        
        # Create new context with redacted data
        redacted_ctx = LogContext()
        for key, value in ctx_dict.items():
            if key in redacted_ctx.__dict__:
                setattr(redacted_ctx, key, value)
            else:
                redacted_ctx.extra[key] = value
        
        # Get timestamp
        timestamp = time.time()
        
        # Send to all handlers
        for handler in self.handlers:
            try:
                handler.handle(level, message, redacted_ctx, timestamp)
            except Exception as e:
                # Don't let handler errors break logging
                print(f"Error in log handler: {e}", file=sys.stderr)
    
    # Convenience methods
    
    def debug(self, message: str, **context) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **context)
    
    def info(self, message: str, **context) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **context)
    
    def warning(self, message: str, **context) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **context)
    
    def error(self, message: str, **context) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, **context)
    
    def critical(self, message: str, **context) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **context)
    
    # Specialized logging methods
    
    def connection_event(self, event: str, connection_id: Optional[EnhancedConnectionId] = None,
                        identity: Optional[EnhancedIdentity] = None, **extra) -> None:
        """Log connection lifecycle event."""
        ctx = {
            'operation': f'connection.{event}',
            'extra': extra
        }
        
        if connection_id:
            ctx['connection_id'] = connection_id.to_hex()[:16]
        
        if identity:
            ctx['identity'] = identity.to_hex()[:16]
        
        self.info(f"Connection {event}", **ctx)
    
    def subscription_event(self, event: str, query_id: Optional[QueryId] = None,
                          queries: Optional[List[str]] = None, **extra) -> None:
        """Log subscription event."""
        ctx = {
            'operation': f'subscription.{event}',
            'extra': extra
        }
        
        if query_id:
            ctx['query_id'] = f"qid_{query_id.id}"
        
        if queries:
            ctx['extra']['query_count'] = len(queries)
            if self._debug_mode:
                ctx['extra']['queries'] = queries
        
        self.info(f"Subscription {event}", **ctx)
    
    def reducer_event(self, event: str, reducer_name: str, request_id: Optional[str] = None,
                     args: Optional[List[Any]] = None, **extra) -> None:
        """Log reducer event."""
        ctx = {
            'operation': f'reducer.{event}',
            'reducer_name': reducer_name,
            'extra': extra
        }
        
        if request_id:
            ctx['request_id'] = request_id
        
        if args and self._debug_mode:
            ctx['extra']['args'] = self._redact_sensitive(args)
        
        self.info(f"Reducer {event}: {reducer_name}", **ctx)
    
    def table_event(self, event: str, table_name: str, row_count: Optional[int] = None,
                   **extra) -> None:
        """Log table event."""
        ctx = {
            'operation': f'table.{event}',
            'table_name': table_name,
            'extra': extra
        }
        
        if row_count is not None:
            ctx['extra']['row_count'] = row_count
        
        self.debug(f"Table {event}: {table_name}", **ctx)
    
    @contextmanager
    def performance(self, operation: str, **context):
        """Context manager for performance logging."""
        start_time = time.perf_counter()
        
        try:
            with self.context(operation=operation, **context):
                yield
        finally:
            duration = time.perf_counter() - start_time
            duration_ms = duration * 1000
            
            # Store metric
            with self._metrics_lock:
                self._performance_metrics[operation].append(duration_ms)
            
            # Log if slow
            if duration_ms > 100:  # More than 100ms
                self.warning(f"Slow operation: {operation}",
                           operation=operation,
                           duration_ms=duration_ms,
                           **context)
            elif self._debug_mode:
                self.debug(f"Operation completed: {operation}",
                         operation=operation,
                         duration_ms=duration_ms,
                         **context)
    
    def get_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics summary."""
        with self._metrics_lock:
            summary = {}
            
            for operation, durations in self._performance_metrics.items():
                if durations:
                    summary[operation] = {
                        'count': len(durations),
                        'avg_ms': sum(durations) / len(durations),
                        'min_ms': min(durations),
                        'max_ms': max(durations),
                        'total_ms': sum(durations)
                    }
            
            return summary
    
    def log_metrics_summary(self) -> None:
        """Log performance metrics summary."""
        metrics = self.get_performance_metrics()
        
        if metrics:
            self.info("Performance metrics summary",
                     operation="metrics.summary",
                     extra={'metrics': metrics})


# Global logger instance
logger = SpacetimeDBLogger()

# Configure default handlers based on environment
def configure_default_logging(debug: bool = False, log_file: Optional[str] = None):
    """Configure default logging setup."""
    global logger
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with colors
    console_formatter = ColoredTextFormatter() if sys.stdout.isatty() else TextFormatter()
    console_handler = ConsoleHandler(
        formatter=console_formatter,
        min_level=LogLevel.DEBUG if debug else LogLevel.INFO
    )
    logger.add_handler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = FileHandler(
            log_file,
            formatter=JSONFormatter(),
            min_level=LogLevel.DEBUG
        )
        logger.add_handler(file_handler)
    
    # Set debug mode
    logger.set_debug_mode(debug)
    
    return logger


# Export convenience functions
def get_logger(name: Optional[str] = None) -> SpacetimeDBLogger:
    """Get a logger instance."""
    if name:
        # Could implement named loggers in future
        return logger
    return logger 