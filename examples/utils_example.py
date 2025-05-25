"""
Comprehensive example demonstrating SpacetimeDB Python SDK utilities.

This example showcases all the utility functions including:
- Identity and connection ID formatting
- URI parsing and validation
- Request ID generation
- Data conversion and formatting
- Schema introspection
- Connection diagnostics
- Performance profiling
- Configuration management
"""

import asyncio
import json
import time
import secrets
from pathlib import Path

from spacetimedb_sdk.utils import (
    # Enums
    IdentityFormat, URIScheme,
    
    # Classes
    IdentityFormatter, ConnectionIdFormatter, URIParser,
    DataConverter, SchemaIntrospector, ConnectionDiagnostics,
    PerformanceProfiler, ConfigurationManager, RequestIdGenerator,
    
    # Convenience functions
    format_identity, parse_identity, format_connection_id, parse_connection_id,
    parse_uri, validate_spacetimedb_uri, normalize_uri, generate_request_id,
    bytes_to_human_readable, duration_to_human_readable, test_connection_latency,
    get_system_info,
    
    # Global instances
    request_id_generator, performance_profiler
)


def demonstrate_identity_formatting():
    """Demonstrate identity formatting utilities."""
    print("=== Identity Formatting Utilities ===\n")
    
    # Generate a sample identity (32 bytes)
    identity_bytes = secrets.token_bytes(32)
    print(f"Original identity bytes: {len(identity_bytes)} bytes")
    
    # Format in different ways
    hex_format = format_identity(identity_bytes, IdentityFormat.HEX)
    base64_format = format_identity(identity_bytes, IdentityFormat.BASE64)
    abbreviated_format = format_identity(identity_bytes, IdentityFormat.ABBREVIATED)
    human_readable_format = format_identity(identity_bytes, IdentityFormat.HUMAN_READABLE)
    base58_format = format_identity(identity_bytes, IdentityFormat.BASE58)
    
    print(f"Hex format: {hex_format}")
    print(f"Base64 format: {base64_format}")
    print(f"Abbreviated format: {abbreviated_format}")
    print(f"Human readable format: {human_readable_format}")
    print(f"Base58 format: {base58_format}")
    
    # Parse back from hex
    parsed_identity = parse_identity(hex_format)
    print(f"Parsed back correctly: {parsed_identity == identity_bytes}")
    
    # Validate identity
    is_valid = IdentityFormatter.validate_identity(identity_bytes)
    print(f"Identity is valid: {is_valid}")
    
    # Test with invalid identity
    invalid_identity = b'\x00' * 32
    is_invalid = IdentityFormatter.validate_identity(invalid_identity)
    print(f"All-zero identity is valid: {is_invalid}")
    
    print()


def demonstrate_connection_id_formatting():
    """Demonstrate connection ID formatting utilities."""
    print("=== Connection ID Formatting Utilities ===\n")
    
    # Generate a sample connection ID
    connection_id = secrets.randbits(64)
    print(f"Original connection ID: {connection_id}")
    
    # Format in different ways
    hex_format = format_connection_id(connection_id, IdentityFormat.HEX)
    abbreviated_format = format_connection_id(connection_id, IdentityFormat.ABBREVIATED)
    human_readable_format = format_connection_id(connection_id, IdentityFormat.HUMAN_READABLE)
    
    print(f"Hex format: {hex_format}")
    print(f"Abbreviated format: {abbreviated_format}")
    print(f"Human readable format: {human_readable_format}")
    
    # Parse back
    parsed_connection_id = parse_connection_id(hex_format)
    print(f"Parsed back correctly: {parsed_connection_id == connection_id}")
    
    # Test with bytes input
    connection_bytes = connection_id.to_bytes(8, 'big')
    bytes_format = format_connection_id(connection_bytes)
    print(f"From bytes format: {bytes_format}")
    
    print()


def demonstrate_uri_parsing():
    """Demonstrate URI parsing and validation utilities."""
    print("=== URI Parsing and Validation Utilities ===\n")
    
    # Test various URI formats
    test_uris = [
        "ws://localhost:3000",
        "wss://example.com:443/database?token=abc123&user=alice",
        "http://api.spacetimedb.com/v1/database",
        "https://secure.example.com:8443/api#section1",
        "ws://192.168.1.100:3000/my_database"
    ]
    
    for uri in test_uris:
        print(f"Testing URI: {uri}")
        
        # Parse the URI
        try:
            parsed = parse_uri(uri)
            print(f"  Scheme: {parsed.scheme.value}")
            print(f"  Host: {parsed.host}")
            print(f"  Port: {parsed.port}")
            print(f"  Path: {parsed.path}")
            print(f"  Query: {parsed.query}")
            print(f"  Fragment: {parsed.fragment}")
            print(f"  Is secure: {parsed.is_secure}")
            
            # Convert to different formats
            ws_uri = parsed.to_websocket_uri()
            http_uri = parsed.to_http_uri()
            print(f"  As WebSocket: {ws_uri}")
            print(f"  As HTTP: {http_uri}")
            
        except ValueError as e:
            print(f"  Error: {e}")
        
        # Validate for SpacetimeDB
        is_valid = validate_spacetimedb_uri(uri)
        print(f"  Valid for SpacetimeDB: {is_valid}")
        
        # Normalize
        try:
            normalized = normalize_uri(uri)
            print(f"  Normalized: {normalized}")
        except ValueError:
            print(f"  Cannot normalize (invalid URI)")
        
        print()


def demonstrate_request_id_generation():
    """Demonstrate request ID generation utilities."""
    print("=== Request ID Generation Utilities ===\n")
    
    # Use global generator
    print("Using global request ID generator:")
    for i in range(3):
        req_id = generate_request_id()
        print(f"  Request ID {i+1}: {req_id}")
    
    # Create custom generator
    print("\nUsing custom generator with different prefix:")
    custom_generator = RequestIdGenerator(_prefix="api")
    for i in range(3):
        req_id = custom_generator.generate()
        print(f"  API Request ID {i+1}: {req_id}")
    
    # Different generation methods
    print("\nDifferent generation methods:")
    hex_id = custom_generator.generate_hex()
    uuid_id = custom_generator.generate_uuid_style()
    print(f"  Hex-based ID: {hex_id}")
    print(f"  UUID-style ID: {uuid_id}")
    
    print()


def demonstrate_data_conversion():
    """Demonstrate data conversion utilities."""
    print("=== Data Conversion Utilities ===\n")
    
    # Bytes to human readable
    print("Bytes to human readable:")
    byte_sizes = [0, 512, 1024, 1536, 1024*1024, 1024*1024*1024, 1024*1024*1024*1024]
    for size in byte_sizes:
        human = bytes_to_human_readable(size)
        print(f"  {size:>12} bytes = {human}")
    
    # Duration to human readable
    print("\nDuration to human readable:")
    durations = [0.001, 0.5, 1.5, 30, 90, 3600, 7200, 86400]
    for duration in durations:
        human = duration_to_human_readable(duration)
        print(f"  {duration:>8} seconds = {human}")
    
    # JSON formatting
    print("\nJSON formatting:")
    sample_data = {
        "name": "SpacetimeDB",
        "version": "1.0.0",
        "features": ["real-time", "multiplayer", "serverless"],
        "config": {
            "max_connections": 1000,
            "timeout": 30.0
        }
    }
    pretty_json = DataConverter.format_json_pretty(sample_data)
    print("Pretty JSON:")
    print(pretty_json)
    
    # String truncation
    print("\nString truncation:")
    long_text = "This is a very long string that demonstrates the truncation functionality of the data converter utility class"
    truncated = DataConverter.truncate_string(long_text, 50)
    print(f"Original: {long_text}")
    print(f"Truncated: {truncated}")
    
    print()


def demonstrate_schema_introspection():
    """Demonstrate schema introspection utilities."""
    print("=== Schema Introspection Utilities ===\n")
    
    # Sample table data
    table_data = [
        {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30, "active": True},
        {"id": 2, "name": "Bob", "email": None, "age": 25, "active": True},
        {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35, "active": False},
        {"id": 4, "name": "Diana", "email": "diana@example.com", "age": 28, "active": True},
        {"id": 5, "name": "Eve", "email": None, "age": 32, "active": True}
    ]
    
    print("Analyzing sample table data...")
    analysis = SchemaIntrospector.analyze_table_schema(table_data)
    
    print(f"Row count: {analysis['row_count']}")
    print(f"Estimated size: {analysis['estimated_size_human']}")
    print("\nColumn analysis:")
    
    for column_name, column_info in analysis['columns'].items():
        print(f"  {column_name}:")
        print(f"    Type: {column_info['type']}")
        print(f"    Nullable: {column_info['nullable']}")
        print(f"    Unique values: {column_info['unique_count']}")
        if column_info.get('min_length') is not None:
            print(f"    Min length: {column_info['min_length']}")
            print(f"    Max length: {column_info['max_length']}")
    
    print()


def demonstrate_connection_diagnostics():
    """Demonstrate connection diagnostics utilities."""
    print("=== Connection Diagnostics Utilities ===\n")
    
    # Get system information
    print("System information:")
    system_info = get_system_info()
    for key, value in system_info.items():
        if key == "python_version":
            # Truncate long Python version string
            value = value.split('\n')[0]
        print(f"  {key}: {value}")
    
    # Test connection latency
    print("\nTesting connection latency:")
    test_hosts = [
        "ws://localhost:3000",
        "ws://127.0.0.1:3000",
        "ws://google.com:80",
        "ws://invalid-host-12345:3000"
    ]
    
    for host in test_hosts:
        print(f"  Testing {host}...")
        result = test_connection_latency(host, timeout=2.0)
        if result["success"]:
            print(f"    ✓ Connected in {result['latency_human']}")
        else:
            print(f"    ✗ Failed: {result['error']}")
    
    print()


def demonstrate_performance_profiling():
    """Demonstrate performance profiling utilities."""
    print("=== Performance Profiling Utilities ===\n")
    
    # Create a custom profiler
    profiler = PerformanceProfiler()
    
    # Simulate some operations
    print("Simulating operations...")
    
    # Operation 1: Fast operation
    for i in range(5):
        start_time = profiler.start_timer("fast_operation")
        time.sleep(0.01)  # 10ms
        profiler.end_timer("fast_operation", start_time)
        profiler.increment_counter("fast_operations")
    
    # Operation 2: Slow operation
    for i in range(3):
        start_time = profiler.start_timer("slow_operation")
        time.sleep(0.05)  # 50ms
        profiler.end_timer("slow_operation", start_time)
        profiler.increment_counter("slow_operations")
    
    # Operation 3: Variable operation
    for i in range(4):
        start_time = profiler.start_timer("variable_operation")
        time.sleep(0.01 + i * 0.01)  # 10ms, 20ms, 30ms, 40ms
        profiler.end_timer("variable_operation", start_time)
    
    # Get statistics
    print("Performance statistics:")
    
    for operation in ["fast_operation", "slow_operation", "variable_operation"]:
        stats = profiler.get_timer_stats(operation)
        if stats["count"] > 0:
            print(f"  {operation}:")
            print(f"    Count: {stats['count']}")
            print(f"    Total time: {stats['total']:.3f}s")
            print(f"    Average time: {stats['average']:.3f}s")
            print(f"    Min time: {stats['min']:.3f}s")
            print(f"    Max time: {stats['max']:.3f}s")
    
    # Get full summary
    summary = profiler.get_summary()
    print(f"\nCounters: {summary['counters']}")
    
    # Test global profiler
    print("\nUsing global profiler:")
    start_time = performance_profiler.start_timer("global_test")
    time.sleep(0.02)
    performance_profiler.end_timer("global_test", start_time)
    
    global_stats = performance_profiler.get_timer_stats("global_test")
    print(f"Global test operation took: {global_stats['average']:.3f}s")
    
    print()


def demonstrate_configuration_management():
    """Demonstrate configuration management utilities."""
    print("=== Configuration Management Utilities ===\n")
    
    # Sample configurations
    config1 = {
        "server": {
            "host": "localhost",
            "port": 3000
        },
        "database": {
            "name": "my_app"
        },
        "features": {
            "compression": True
        }
    }
    
    config2 = {
        "server": {
            "port": 3001,  # Override port
            "ssl": True    # Add SSL
        },
        "auth": {
            "token": "secret123"
        }
    }
    
    config3 = {
        "features": {
            "compression": False,  # Override compression
            "logging": True        # Add logging
        }
    }
    
    print("Original configurations:")
    print("Config 1:", json.dumps(config1, indent=2))
    print("Config 2:", json.dumps(config2, indent=2))
    print("Config 3:", json.dumps(config3, indent=2))
    
    # Merge configurations
    merged_config = ConfigurationManager.merge_configs(config1, config2, config3)
    print("\nMerged configuration:")
    print(json.dumps(merged_config, indent=2))
    
    # Test file operations with temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        # Save configuration
        ConfigurationManager.save_config_file(merged_config, temp_path)
        print(f"\nSaved configuration to: {temp_path}")
        
        # Load configuration
        loaded_config = ConfigurationManager.load_config_file(temp_path)
        print("Loaded configuration matches:", loaded_config == merged_config)
        
    finally:
        Path(temp_path).unlink(missing_ok=True)
    
    # Show default config path
    default_path = ConfigurationManager.get_default_config_path()
    print(f"Default config path: {default_path}")
    
    print()


def demonstrate_typescript_parity():
    """Demonstrate TypeScript SDK parity features."""
    print("=== TypeScript SDK Parity Features ===\n")
    
    print("1. Identity Utilities (TypeScript Parity):")
    # Generate identity like TypeScript SDK
    identity_bytes = secrets.token_bytes(32)
    identity_hex = format_identity(identity_bytes, IdentityFormat.HEX)
    identity_abbreviated = format_identity(identity_bytes, IdentityFormat.ABBREVIATED)
    print(f"   Full identity: {identity_hex}")
    print(f"   Abbreviated: {identity_abbreviated}")
    
    print("\n2. Connection ID Utilities (TypeScript Parity):")
    # Generate connection ID like TypeScript SDK
    connection_id = secrets.randbits(64)
    connection_hex = format_connection_id(connection_id)
    connection_readable = format_connection_id(connection_id, IdentityFormat.HUMAN_READABLE)
    print(f"   Connection ID: {connection_hex}")
    print(f"   Human readable: {connection_readable}")
    
    print("\n3. URI Parsing (TypeScript Parity):")
    # Parse URIs like TypeScript SDK
    test_uri = "wss://spacetimedb.com:443/database?token=abc123"
    parsed = parse_uri(test_uri)
    print(f"   Original: {test_uri}")
    print(f"   Host: {parsed.host}")
    print(f"   Secure: {parsed.is_secure}")
    print(f"   Query params: {parsed.query}")
    
    print("\n4. Request ID Generation (TypeScript Parity):")
    # Generate request IDs like TypeScript SDK
    for i in range(3):
        req_id = generate_request_id()
        print(f"   Request {i+1}: {req_id}")
    
    print("\n5. Data Formatting (TypeScript Parity):")
    # Format data like TypeScript SDK
    size_bytes = 1024 * 1024 * 2.5  # 2.5 MB
    duration_secs = 125.75  # 2 minutes 5.75 seconds
    print(f"   Size: {bytes_to_human_readable(int(size_bytes))}")
    print(f"   Duration: {duration_to_human_readable(duration_secs)}")
    
    print("\n6. System Diagnostics (TypeScript Parity):")
    # System info like TypeScript SDK
    system_info = get_system_info()
    print(f"   Platform: {system_info['platform']}")
    print(f"   Architecture: {system_info['architecture'][0]}")
    print(f"   Hostname: {system_info['hostname']}")
    
    print()


async def main():
    """Run all utility demonstrations."""
    print("SpacetimeDB Python SDK - Advanced Utilities Demo")
    print("=" * 60)
    print()
    
    try:
        # Core utilities
        demonstrate_identity_formatting()
        demonstrate_connection_id_formatting()
        demonstrate_uri_parsing()
        demonstrate_request_id_generation()
        
        # Data utilities
        demonstrate_data_conversion()
        demonstrate_schema_introspection()
        
        # Diagnostic utilities
        demonstrate_connection_diagnostics()
        demonstrate_performance_profiling()
        
        # Configuration utilities
        demonstrate_configuration_management()
        
        # TypeScript parity
        demonstrate_typescript_parity()
        
        print("🎉 All utility demonstrations completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✅ Identity formatting with multiple formats (hex, base64, base58, abbreviated)")
        print("✅ Connection ID formatting and parsing")
        print("✅ Comprehensive URI parsing and validation")
        print("✅ Request ID generation with multiple strategies")
        print("✅ Data conversion and human-readable formatting")
        print("✅ Schema introspection and analysis")
        print("✅ Connection diagnostics and latency testing")
        print("✅ Performance profiling with timers and counters")
        print("✅ Configuration management with file operations")
        print("✅ Full TypeScript SDK parity for utility functions")
        
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 