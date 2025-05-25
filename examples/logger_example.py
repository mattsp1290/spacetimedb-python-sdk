"""
Example: Logger Integration for SpacetimeDB Python SDK

Demonstrates how to use the structured logging system:
- Basic logging configuration
- Contextual logging
- Performance tracking
- Custom handlers and formatters
- Production features
"""

import asyncio
import time
from pathlib import Path

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    configure_default_logging,
    get_logger,
    LogLevel,
    JSONFormatter,
    TextFormatter,
    ColoredTextFormatter,
    ConsoleHandler,
    FileHandler,
    MemoryHandler,
    SamplingHandler,
    SpacetimeDBLogger
)


class LoggerExample:
    """Examples demonstrating logger usage."""
    
    def example_1_basic_logging(self):
        """Example 1: Basic logging setup and usage."""
        print("\n=== Example 1: Basic Logging ===")
        
        # Configure default logging
        logger = configure_default_logging(debug=True)
        
        # Log at different levels
        logger.debug("Debug message - detailed information")
        logger.info("Info message - general information")
        logger.warning("Warning message - potential issue")
        logger.error("Error message - something went wrong")
        logger.critical("Critical message - system failure")
        
        # Log with context
        logger.info("User action", 
                   user="alice",
                   action="login",
                   ip_address="192.168.1.100")
    
    def example_2_contextual_logging(self):
        """Example 2: Contextual logging with nested contexts."""
        print("\n=== Example 2: Contextual Logging ===")
        
        logger = get_logger()
        
        # Add console handler with colors
        logger.handlers.clear()
        logger.add_handler(ConsoleHandler(
            formatter=ColoredTextFormatter()
        ))
        
        # Use context manager for consistent context
        with logger.context(module_name="chat_app", version="1.0"):
            logger.info("Application started")
            
            with logger.context(user_id="user123", session_id="sess456"):
                logger.info("User logged in")
                
                with logger.context(room_id="main"):
                    logger.info("User joined room")
                    logger.debug("Loading room history")
            
            logger.info("Context automatically cleaned up")
    
    def example_3_performance_logging(self):
        """Example 3: Performance tracking and metrics."""
        print("\n=== Example 3: Performance Logging ===")
        
        logger = SpacetimeDBLogger("performance")
        logger.add_handler(ConsoleHandler())
        logger.set_debug_mode(True)
        
        # Track operation performance
        with logger.performance("database.query"):
            time.sleep(0.05)  # Simulate query
        
        with logger.performance("api.call", endpoint="/users"):
            time.sleep(0.02)  # Simulate API call
        
        # Simulate slow operation
        with logger.performance("slow.operation"):
            time.sleep(0.15)  # This will trigger a warning
        
        # Multiple operations
        for i in range(5):
            with logger.performance("batch.process", batch_id=i):
                time.sleep(0.01)
        
        # Get metrics summary
        metrics = logger.get_performance_metrics()
        print("\nPerformance Metrics:")
        for op, stats in metrics.items():
            print(f"  {op}:")
            print(f"    Count: {stats['count']}")
            print(f"    Avg: {stats['avg_ms']:.2f}ms")
            print(f"    Min: {stats['min_ms']:.2f}ms")
            print(f"    Max: {stats['max_ms']:.2f}ms")
    
    def example_4_custom_handlers(self):
        """Example 4: Custom handlers and formatters."""
        print("\n=== Example 4: Custom Handlers ===")
        
        logger = SpacetimeDBLogger("custom")
        
        # Console with text format
        console_handler = ConsoleHandler(
            formatter=TextFormatter(include_context=True),
            min_level=LogLevel.INFO
        )
        logger.add_handler(console_handler)
        
        # File with JSON format
        log_file = Path("spacetimedb.log")
        file_handler = FileHandler(
            log_file,
            formatter=JSONFormatter(),
            min_level=LogLevel.DEBUG
        )
        logger.add_handler(file_handler)
        
        # Memory handler for buffering
        memory_handler = MemoryHandler(max_entries=100)
        logger.add_handler(memory_handler)
        
        # Log some events
        logger.info("Application started")
        logger.debug("Debug information", extra={"detail": "value"})
        logger.error("An error occurred", error_code=500)
        
        # Get buffered logs
        print("\nBuffered logs:")
        for entry in memory_handler.get_entries()[-3:]:
            print(f"  {entry}")
        
        # Clean up
        file_handler.close()
        if log_file.exists():
            print(f"\nLog file created: {log_file}")
            log_file.unlink()
    
    def example_5_production_features(self):
        """Example 5: Production features - sampling and security."""
        print("\n=== Example 5: Production Features ===")
        
        logger = SpacetimeDBLogger("production")
        
        # Regular handler
        regular_handler = ConsoleHandler(
            formatter=TextFormatter(include_context=False)
        )
        
        # Sampling handler to reduce log volume
        sampling_handler = SamplingHandler(
            regular_handler,
            sample_rate=0.1,  # Log 10% of messages
            always_log_errors=True  # But always log errors
        )
        logger.add_handler(sampling_handler)
        
        # Add security patterns
        logger.add_redact_pattern("credit_card")
        logger.add_redact_pattern("ssn")
        
        # Simulate high-volume logging
        print("\nSimulating 100 info messages (10% sampling):")
        for i in range(100):
            logger.info(f"Processing request {i}")
        
        # Errors are always logged
        logger.error("Database connection failed", retry_count=3)
        
        # Sensitive data is redacted
        logger.info("User registration", extra={
            "username": "john_doe",
            "email": "john@example.com",
            "password": "secret123",  # Will be redacted
            "credit_card": "1234-5678-9012-3456",  # Will be redacted
            "auth_token": "abcdefghijklmnopqrstuvwxyz123456"  # Will be redacted
        })
        
        # Show sampling statistics
        counts = sampling_handler.get_counts()
        print(f"\nSampling statistics:")
        for key, count in counts.items():
            print(f"  {key}: {count} total messages")
    
    async def example_6_spacetimedb_integration(self):
        """Example 6: Integration with SpacetimeDB client."""
        print("\n=== Example 6: SpacetimeDB Integration ===")
        
        # Configure logging with file output
        logger = configure_default_logging(
            debug=True,
            log_file="spacetimedb_session.log"
        )
        
        # Create client with logging context
        with logger.context(module_name="example_app"):
            try:
                # Build client
                client = (ModernSpacetimeDBClient.builder()
                         .with_uri("ws://localhost:3000")
                         .with_module_name("example")
                         .build())
                
                # These would be logged automatically by the SDK
                logger.connection_event("connecting")
                logger.connection_event("connected", 
                                      extra={"endpoint": "ws://localhost:3000"})
                
                # Subscription
                logger.subscription_event("creating", 
                                        queries=["SELECT * FROM users"])
                
                # Table operations
                with logger.performance("table.batch_insert"):
                    for i in range(10):
                        logger.table_event("insert", "users", row_count=1)
                
                # Reducer calls
                logger.reducer_event("calling", "create_user",
                                   request_id="req123",
                                   args=["alice", "alice@example.com"])
                
                logger.reducer_event("completed", "create_user",
                                   request_id="req123",
                                   extra={"duration_ms": 25.3})
                
            except Exception as e:
                logger.error("Connection failed", 
                           error_type=type(e).__name__,
                           error_message=str(e))
            
            # Log metrics
            logger.log_metrics_summary()
        
        print("\nSession log written to: spacetimedb_session.log")
    
    def example_7_debugging_scenarios(self):
        """Example 7: Debugging scenarios with detailed logging."""
        print("\n=== Example 7: Debugging Scenarios ===")
        
        # Create debug logger
        logger = SpacetimeDBLogger("debug")
        logger.set_debug_mode(True)
        
        # Memory handler to capture all logs
        memory_handler = MemoryHandler()
        logger.add_handler(memory_handler)
        
        # Console for important messages
        console_handler = ConsoleHandler(
            formatter=ColoredTextFormatter(),
            min_level=LogLevel.WARNING
        )
        logger.add_handler(console_handler)
        
        # Simulate a complex operation with detailed logging
        with logger.context(operation="data_sync"):
            logger.debug("Starting data synchronization")
            
            # Phase 1: Fetch
            with logger.performance("sync.fetch"):
                logger.debug("Fetching remote data", source="server_1")
                time.sleep(0.03)
                logger.debug("Received 1000 records")
            
            # Phase 2: Validate
            with logger.performance("sync.validate"):
                logger.debug("Validating data integrity")
                
                # Simulate validation error
                logger.warning("Data validation issue", 
                             record_id=42,
                             field="email",
                             issue="invalid_format")
                
                logger.debug("Validation complete", 
                           valid=950, 
                           invalid=50)
            
            # Phase 3: Apply
            with logger.performance("sync.apply"):
                logger.debug("Applying changes to database")
                
                # Simulate error
                logger.error("Failed to apply changes",
                           error_type="ConstraintViolation",
                           table="users",
                           constraint="unique_email")
                
                logger.debug("Rollback initiated")
        
        # Dump all debug logs for analysis
        print("\n--- Debug Log Dump ---")
        entries = memory_handler.get_entries()
        for entry in entries[-10:]:  # Last 10 entries
            print(entry)
    
    def example_8_monitoring_production(self):
        """Example 8: Production monitoring setup."""
        print("\n=== Example 8: Production Monitoring ===")
        
        # Production logger configuration
        logger = SpacetimeDBLogger("monitoring")
        
        # JSON logs for log aggregation systems
        json_handler = FileHandler(
            "production.log",
            formatter=JSONFormatter(),
            min_level=LogLevel.INFO
        )
        
        # Sampling for high-volume operations
        sampled_json = SamplingHandler(
            json_handler,
            sample_rate=0.01,  # 1% sampling for debug logs
            always_log_errors=True
        )
        
        logger.add_handler(sampled_json)
        
        # Simulate production traffic
        print("Simulating production traffic...")
        
        # Connection events
        for i in range(5):
            logger.info("New connection",
                       operation="connection.new",
                       client_ip=f"192.168.1.{100+i}",
                       protocol="websocket")
        
        # API requests (high volume, sampled)
        for i in range(1000):
            logger.debug("API request",
                        operation="api.request",
                        method="POST",
                        path="/api/messages",
                        latency_ms=10 + (i % 50))
        
        # Errors (always logged)
        logger.error("Database connection lost",
                    operation="db.error",
                    error_type="ConnectionTimeout",
                    retry_attempt=1)
        
        # Performance anomaly
        logger.warning("Slow query detected",
                      operation="db.slow_query",
                      query_id="q123",
                      duration_ms=5432,
                      table="messages")
        
        # System metrics
        logger.info("System metrics",
                   operation="system.metrics",
                   cpu_percent=45.2,
                   memory_mb=1024,
                   connections_active=150,
                   queries_per_second=1200)
        
        # Get sampling stats
        print(f"\nSampling statistics:")
        counts = sampled_json.get_counts()
        for msg_type, count in list(counts.items())[:5]:
            print(f"  {msg_type}: {count}")
        
        # Clean up
        json_handler.close()
        Path("production.log").unlink(missing_ok=True)
    
    def example_9_custom_logger_integration(self):
        """Example 9: Integrating with existing logging systems."""
        print("\n=== Example 9: Custom Logger Integration ===")
        
        import logging
        
        # Bridge to Python's standard logging
        class StandardLoggingHandler(ConsoleHandler):
            def __init__(self, python_logger):
                super().__init__()
                self.python_logger = python_logger
            
            def write(self, formatted: str):
                # Route to Python logger instead of console
                self.python_logger.info(formatted)
        
        # Set up Python logger
        python_logger = logging.getLogger("spacetimedb.bridge")
        python_logger.setLevel(logging.DEBUG)
        
        # Add handler to Python logger
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        python_logger.addHandler(handler)
        
        # Create SpacetimeDB logger with bridge
        stdb_logger = SpacetimeDBLogger("bridged")
        stdb_logger.add_handler(StandardLoggingHandler(python_logger))
        
        # Use SpacetimeDB logger
        stdb_logger.info("Message via bridge",
                        operation="test.bridge",
                        status="success")
        
        print("\nLogs are routed through Python's standard logging!")
    
    def example_10_troubleshooting_guide(self):
        """Example 10: Troubleshooting with logs."""
        print("\n=== Example 10: Troubleshooting Guide ===")
        
        # Create troubleshooting logger
        logger = SpacetimeDBLogger("troubleshoot")
        
        # Capture everything
        trouble_handler = MemoryHandler(max_entries=1000)
        logger.add_handler(trouble_handler)
        
        # Also show warnings on console
        logger.add_handler(ConsoleHandler(
            formatter=ColoredTextFormatter(),
            min_level=LogLevel.WARNING
        ))
        
        logger.set_debug_mode(True)
        
        print("Simulating connection issues...")
        
        # Simulate connection troubleshooting
        with logger.context(troubleshooting=True):
            # Connection attempt 1
            logger.info("Connection attempt 1",
                       server="ws://localhost:3000")
            logger.debug("Resolving hostname", host="localhost")
            logger.debug("DNS resolved", ip="127.0.0.1")
            logger.warning("Connection timeout",
                         timeout_ms=5000,
                         error="ETIMEDOUT")
            
            # Connection attempt 2
            logger.info("Connection attempt 2 with fallback",
                       server="ws://backup.example.com:3000")
            logger.debug("Using backup server")
            logger.error("Connection refused",
                        error="ECONNREFUSED",
                        port=3000)
            
            # Diagnostics
            logger.info("Running diagnostics")
            logger.debug("Checking network connectivity")
            logger.debug("Ping test: OK")
            logger.debug("Port scan: 3000 closed")
            logger.critical("SpacetimeDB server not reachable",
                          suggestion="Check if server is running")
        
        # Generate troubleshooting report
        print("\n--- Troubleshooting Report ---")
        entries = trouble_handler.get_entries()
        
        errors = [e for e in entries if "[ERROR" in e or "[CRITICAL" in e]
        warnings = [e for e in entries if "[WARNING" in e]
        
        print(f"Total log entries: {len(entries)}")
        print(f"Errors/Critical: {len(errors)}")
        print(f"Warnings: {len(warnings)}")
        
        if errors:
            print("\nFirst error:")
            print(errors[0])


def main():
    """Run all logger examples."""
    example = LoggerExample()
    
    # Basic examples
    example.example_1_basic_logging()
    example.example_2_contextual_logging()
    example.example_3_performance_logging()
    example.example_4_custom_handlers()
    
    # Advanced examples
    example.example_5_production_features()
    asyncio.run(example.example_6_spacetimedb_integration())
    example.example_7_debugging_scenarios()
    example.example_8_monitoring_production()
    
    # Integration examples
    example.example_9_custom_logger_integration()
    example.example_10_troubleshooting_guide()
    
    print("\n✅ Logger examples complete!")
    print("\nKey Features Demonstrated:")
    print("- Multiple log levels and contextual logging")
    print("- Performance tracking with metrics")
    print("- Custom handlers and formatters")
    print("- Log sampling for high-volume scenarios")
    print("- Security with sensitive data redaction")
    print("- Integration with SpacetimeDB operations")
    print("- Production monitoring setup")
    print("- Troubleshooting and debugging support")


if __name__ == "__main__":
    main() 