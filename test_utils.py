"""
Comprehensive tests for SpacetimeDB Python SDK utilities.

Tests all utility functions including identity formatting, URI parsing,
request ID generation, and other helper functions.
"""

import pytest
import json
import time
from pathlib import Path
import tempfile
import secrets

from src.spacetimedb_sdk.utils import (
    # Classes
    IdentityFormat, URIScheme, ParsedURI, RequestIdGenerator,
    IdentityFormatter, ConnectionIdFormatter, URIParser,
    DataConverter, SchemaIntrospector, ConnectionDiagnostics,
    PerformanceProfiler, ConfigurationManager,
    
    # Convenience functions
    format_identity, parse_identity, format_connection_id, parse_connection_id,
    parse_uri, validate_spacetimedb_uri, normalize_uri, generate_request_id,
    bytes_to_human_readable, duration_to_human_readable, test_connection_latency,
    get_system_info,
    
    # Global instances
    request_id_generator, performance_profiler
)


class TestIdentityFormatter:
    """Test identity formatting functionality."""
    
    def test_format_identity_hex(self):
        """Test hex formatting of identity."""
        identity_bytes = bytes.fromhex("0123456789abcdef" * 4)  # 32 bytes
        result = IdentityFormatter.format_identity(identity_bytes, IdentityFormat.HEX)
        expected = "0123456789abcdef" * 4
        assert result == expected
    
    def test_format_identity_base64(self):
        """Test base64 formatting of identity."""
        identity_bytes = b"test_identity_32_bytes_long_here"
        result = IdentityFormatter.format_identity(identity_bytes, IdentityFormat.BASE64)
        assert result == "dGVzdF9pZGVudGl0eV8zMl9ieXRlc19sb25nX2hlcmU="
    
    def test_format_identity_abbreviated(self):
        """Test abbreviated formatting of identity."""
        identity_bytes = bytes.fromhex("0123456789abcdef" * 4)
        result = IdentityFormatter.format_identity(identity_bytes, IdentityFormat.ABBREVIATED)
        assert result == "0123456789abcdef..."
    
    def test_format_identity_human_readable(self):
        """Test human-readable formatting of identity."""
        identity_bytes = bytes.fromhex("0123456789abcdef" * 4)
        result = IdentityFormatter.format_identity(identity_bytes, IdentityFormat.HUMAN_READABLE)
        assert result.startswith("Identity(01234567...")
        assert result.endswith("...abcdef)")
    
    def test_parse_identity_hex(self):
        """Test parsing hex identity."""
        hex_str = "0123456789abcdef" * 4
        result = IdentityFormatter.parse_identity(hex_str)
        expected = bytes.fromhex(hex_str)
        assert result == expected
    
    def test_parse_identity_with_0x_prefix(self):
        """Test parsing identity with 0x prefix."""
        hex_str = "0x" + "0123456789abcdef" * 4
        result = IdentityFormatter.parse_identity(hex_str)
        expected = bytes.fromhex("0123456789abcdef" * 4)
        assert result == expected
    
    def test_parse_identity_base64(self):
        """Test parsing base64 identity."""
        identity_bytes = b"test_identity_32_bytes_long_here"
        base64_str = "dGVzdF9pZGVudGl0eV8zMl9ieXRlc19sb25nX2hlcmU="
        result = IdentityFormatter.parse_identity(base64_str)
        assert result == identity_bytes
    
    def test_parse_identity_invalid(self):
        """Test parsing invalid identity."""
        with pytest.raises(ValueError):
            IdentityFormatter.parse_identity("invalid_identity_string")
    
    def test_validate_identity_valid(self):
        """Test validating valid identity."""
        identity_bytes = secrets.token_bytes(32)
        assert IdentityFormatter.validate_identity(identity_bytes) == True
    
    def test_validate_identity_wrong_length(self):
        """Test validating identity with wrong length."""
        identity_bytes = secrets.token_bytes(16)  # Wrong length
        assert IdentityFormatter.validate_identity(identity_bytes) == False
    
    def test_validate_identity_all_zeros(self):
        """Test validating all-zero identity."""
        identity_bytes = b'\x00' * 32
        assert IdentityFormatter.validate_identity(identity_bytes) == False
    
    def test_base58_roundtrip(self):
        """Test Base58 encoding and decoding roundtrip."""
        original_data = secrets.token_bytes(32)
        encoded = IdentityFormatter._base58_encode(original_data)
        decoded = IdentityFormatter._base58_decode(encoded)
        assert decoded == original_data


class TestConnectionIdFormatter:
    """Test connection ID formatting functionality."""
    
    def test_format_connection_id_from_int(self):
        """Test formatting connection ID from integer."""
        connection_id = 0x123456789abcdef0
        result = ConnectionIdFormatter.format_connection_id(connection_id)
        assert result == "123456789abcdef0"
    
    def test_format_connection_id_from_bytes(self):
        """Test formatting connection ID from bytes."""
        connection_bytes = bytes.fromhex("123456789abcdef0")
        result = ConnectionIdFormatter.format_connection_id(connection_bytes)
        assert result == "123456789abcdef0"
    
    def test_format_connection_id_abbreviated(self):
        """Test abbreviated formatting of connection ID."""
        connection_id = 0x123456789abcdef0
        result = ConnectionIdFormatter.format_connection_id(connection_id, IdentityFormat.ABBREVIATED)
        assert result == "12345678..."
    
    def test_format_connection_id_human_readable(self):
        """Test human-readable formatting of connection ID."""
        connection_id = 0x123456789abcdef0
        result = ConnectionIdFormatter.format_connection_id(connection_id, IdentityFormat.HUMAN_READABLE)
        assert result == "ConnectionId(123456789abcdef0)"
    
    def test_parse_connection_id(self):
        """Test parsing connection ID."""
        connection_id_str = "123456789abcdef0"
        result = ConnectionIdFormatter.parse_connection_id(connection_id_str)
        assert result == 0x123456789abcdef0
    
    def test_parse_connection_id_with_prefix(self):
        """Test parsing connection ID with 0x prefix."""
        connection_id_str = "0x123456789abcdef0"
        result = ConnectionIdFormatter.parse_connection_id(connection_id_str)
        assert result == 0x123456789abcdef0
    
    def test_parse_connection_id_human_readable(self):
        """Test parsing human-readable connection ID."""
        connection_id_str = "ConnectionId(123456789abcdef0)"
        result = ConnectionIdFormatter.parse_connection_id(connection_id_str)
        assert result == 0x123456789abcdef0


class TestURIParser:
    """Test URI parsing functionality."""
    
    def test_parse_websocket_uri(self):
        """Test parsing WebSocket URI."""
        uri = "ws://localhost:3000/database"
        result = URIParser.parse_uri(uri)
        
        assert result.scheme == URIScheme.WS
        assert result.host == "localhost"
        assert result.port == 3000
        assert result.path == "/database"
        assert result.is_secure == False
    
    def test_parse_secure_websocket_uri(self):
        """Test parsing secure WebSocket URI."""
        uri = "wss://example.com:443/database?token=abc123"
        result = URIParser.parse_uri(uri)
        
        assert result.scheme == URIScheme.WSS
        assert result.host == "example.com"
        assert result.port == 443
        assert result.path == "/database"
        assert result.query == {"token": "abc123"}
        assert result.is_secure == True
    
    def test_parse_http_uri(self):
        """Test parsing HTTP URI."""
        uri = "http://api.example.com/v1/database"
        result = URIParser.parse_uri(uri)
        
        assert result.scheme == URIScheme.HTTP
        assert result.host == "api.example.com"
        assert result.port == 80
        assert result.path == "/v1/database"
        assert result.is_secure == False
    
    def test_parse_uri_with_fragment(self):
        """Test parsing URI with fragment."""
        uri = "wss://example.com/database#section1"
        result = URIParser.parse_uri(uri)
        
        assert result.fragment == "section1"
    
    def test_parse_uri_invalid_scheme(self):
        """Test parsing URI with invalid scheme."""
        with pytest.raises(ValueError, match="Unsupported URI scheme"):
            URIParser.parse_uri("ftp://example.com")
    
    def test_parse_uri_no_host(self):
        """Test parsing URI without host."""
        with pytest.raises(ValueError, match="URI must contain a valid hostname"):
            URIParser.parse_uri("ws:///database")
    
    def test_validate_spacetimedb_uri_valid(self):
        """Test validating valid SpacetimeDB URI."""
        assert URIParser.validate_spacetimedb_uri("ws://localhost:3000") == True
        assert URIParser.validate_spacetimedb_uri("wss://example.com") == True
    
    def test_validate_spacetimedb_uri_invalid(self):
        """Test validating invalid SpacetimeDB URI."""
        assert URIParser.validate_spacetimedb_uri("http://example.com") == False
        assert URIParser.validate_spacetimedb_uri("invalid_uri") == False
    
    def test_normalize_uri(self):
        """Test URI normalization."""
        uri = "ws://localhost:3000/database?token=abc"
        result = URIParser.normalize_uri(uri)
        assert result == "ws://localhost:3000/database?token=abc"
    
    def test_parsed_uri_to_websocket_uri(self):
        """Test converting ParsedURI to WebSocket URI."""
        parsed = ParsedURI(
            scheme=URIScheme.HTTP,
            host="example.com",
            port=8080,
            path="/api",
            query={"key": "value"},
            fragment="section",
            is_secure=False
        )
        result = parsed.to_websocket_uri()
        assert result == "ws://example.com:8080/api?key=value#section"
    
    def test_parsed_uri_to_http_uri(self):
        """Test converting ParsedURI to HTTP URI."""
        parsed = ParsedURI(
            scheme=URIScheme.WS,
            host="example.com",
            port=3000,
            path="/database",
            query={},
            fragment=None,
            is_secure=True
        )
        result = parsed.to_http_uri()
        assert result == "https://example.com:3000/database"


class TestRequestIdGenerator:
    """Test request ID generation."""
    
    def test_generate_request_id(self):
        """Test generating request ID."""
        generator = RequestIdGenerator()
        id1 = generator.generate()
        id2 = generator.generate()
        
        assert id1 != id2
        assert id1.startswith("req_")
        assert id2.startswith("req_")
    
    def test_generate_hex_request_id(self):
        """Test generating hex request ID."""
        generator = RequestIdGenerator()
        hex_id = generator.generate_hex()
        
        assert hex_id.startswith("req_")
        assert len(hex_id) == 4 + 1 + 16  # "req_" + 16 hex chars
    
    def test_generate_uuid_style_request_id(self):
        """Test generating UUID-style request ID."""
        generator = RequestIdGenerator()
        uuid_id = generator.generate_uuid_style()
        
        # Should be in format: 8-4-4-4-12
        parts = uuid_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12
    
    def test_custom_prefix(self):
        """Test custom prefix for request ID generator."""
        generator = RequestIdGenerator(_prefix="test")
        test_id = generator.generate()
        assert test_id.startswith("test_")


class TestDataConverter:
    """Test data conversion utilities."""
    
    def test_bytes_to_human_readable(self):
        """Test converting bytes to human-readable format."""
        assert DataConverter.bytes_to_human_readable(0) == "0 B"
        assert DataConverter.bytes_to_human_readable(512) == "512.0 B"
        assert DataConverter.bytes_to_human_readable(1024) == "1.0 KB"
        assert DataConverter.bytes_to_human_readable(1536) == "1.5 KB"
        assert DataConverter.bytes_to_human_readable(1024 * 1024) == "1.0 MB"
        assert DataConverter.bytes_to_human_readable(1024 * 1024 * 1024) == "1.0 GB"
    
    def test_duration_to_human_readable(self):
        """Test converting duration to human-readable format."""
        assert DataConverter.duration_to_human_readable(0.5) == "500.0 ms"
        assert DataConverter.duration_to_human_readable(1.5) == "1.5 s"
        assert DataConverter.duration_to_human_readable(90) == "1.5 min"
        assert DataConverter.duration_to_human_readable(3600) == "1.0 h"
        assert DataConverter.duration_to_human_readable(7200) == "2.0 h"
    
    def test_format_json_pretty(self):
        """Test pretty JSON formatting."""
        data = {"name": "test", "value": 123, "nested": {"key": "value"}}
        result = DataConverter.format_json_pretty(data)
        
        assert '"name": "test"' in result
        assert '"value": 123' in result
        assert '"nested":' in result
        assert result.count('\n') > 0  # Should be multi-line
    
    def test_truncate_string(self):
        """Test string truncation."""
        long_string = "This is a very long string that should be truncated"
        result = DataConverter.truncate_string(long_string, 20)
        assert len(result) == 20
        assert result.endswith("...")
        
        short_string = "Short"
        result = DataConverter.truncate_string(short_string, 20)
        assert result == "Short"


class TestSchemaIntrospector:
    """Test schema introspection utilities."""
    
    def test_analyze_table_schema_empty(self):
        """Test analyzing empty table schema."""
        result = SchemaIntrospector.analyze_table_schema([])
        assert result["row_count"] == 0
        assert result["columns"] == {}
        assert result["estimated_size"] == 0
    
    def test_analyze_table_schema_with_data(self):
        """Test analyzing table schema with data."""
        table_data = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": None},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com"}
        ]
        
        result = SchemaIntrospector.analyze_table_schema(table_data)
        
        assert result["row_count"] == 3
        assert "id" in result["columns"]
        assert "name" in result["columns"]
        assert "email" in result["columns"]
        
        # Check email column (has nulls)
        email_col = result["columns"]["email"]
        assert email_col["nullable"] == True
        assert email_col["unique_count"] == 2  # Two unique non-null values
        
        # Check name column (no nulls)
        name_col = result["columns"]["name"]
        assert name_col["nullable"] == False
        assert name_col["unique_count"] == 3
        assert name_col["min_length"] == 3  # "Bob"
        assert name_col["max_length"] == 7  # "Charlie"


class TestConnectionDiagnostics:
    """Test connection diagnostics utilities."""
    
    def test_get_system_info(self):
        """Test getting system information."""
        info = ConnectionDiagnostics.get_system_info()
        
        assert "platform" in info
        assert "python_version" in info
        assert "architecture" in info
        assert "processor" in info
        assert "hostname" in info
        
        assert isinstance(info["platform"], str)
        assert isinstance(info["python_version"], str)
    
    def test_test_connection_latency_invalid_host(self):
        """Test connection latency with invalid host."""
        result = ConnectionDiagnostics.test_connection_latency("ws://invalid-host-12345:3000", timeout=1.0)
        assert result["success"] == False
        assert "error" in result


class TestPerformanceProfiler:
    """Test performance profiling utilities."""
    
    def test_timer_functionality(self):
        """Test timer functionality."""
        profiler = PerformanceProfiler()
        
        # Start and end a timer
        start_time = profiler.start_timer("test_operation")
        time.sleep(0.01)  # Sleep for 10ms
        duration = profiler.end_timer("test_operation", start_time)
        
        assert duration > 0.005  # Should be at least 5ms
        
        # Get timer stats
        stats = profiler.get_timer_stats("test_operation")
        assert stats["count"] == 1
        assert stats["total"] > 0
        assert stats["average"] > 0
        assert stats["min"] > 0
        assert stats["max"] > 0
    
    def test_counter_functionality(self):
        """Test counter functionality."""
        profiler = PerformanceProfiler()
        
        profiler.increment_counter("test_counter", 5)
        profiler.increment_counter("test_counter", 3)
        
        summary = profiler.get_summary()
        assert summary["counters"]["test_counter"] == 8
    
    def test_get_summary(self):
        """Test getting profiler summary."""
        profiler = PerformanceProfiler()
        
        # Add some data
        start_time = profiler.start_timer("operation1")
        profiler.end_timer("operation1", start_time)
        profiler.increment_counter("counter1", 10)
        
        summary = profiler.get_summary()
        assert "timers" in summary
        assert "counters" in summary
        assert "operation1" in summary["timers"]
        assert "counter1" in summary["counters"]


class TestConfigurationManager:
    """Test configuration management utilities."""
    
    def test_load_nonexistent_config(self):
        """Test loading non-existent config file."""
        result = ConfigurationManager.load_config_file("/nonexistent/path/config.json")
        assert result == {}
    
    def test_save_and_load_config(self):
        """Test saving and loading config file."""
        config = {"key1": "value1", "key2": 123, "nested": {"inner": "value"}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save config
            ConfigurationManager.save_config_file(config, temp_path)
            
            # Load config
            loaded_config = ConfigurationManager.load_config_file(temp_path)
            
            assert loaded_config == config
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_merge_configs(self):
        """Test merging configuration dictionaries."""
        config1 = {"a": 1, "b": 2}
        config2 = {"b": 3, "c": 4}
        config3 = {"c": 5, "d": 6}
        
        result = ConfigurationManager.merge_configs(config1, config2, config3)
        
        assert result == {"a": 1, "b": 3, "c": 5, "d": 6}
    
    def test_get_default_config_path(self):
        """Test getting default config path."""
        path = ConfigurationManager.get_default_config_path()
        assert str(path).endswith(".spacetimedb/config.json")
        assert path.is_absolute()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_format_identity_convenience(self):
        """Test format_identity convenience function."""
        identity_bytes = secrets.token_bytes(32)
        result = format_identity(identity_bytes)
        expected = IdentityFormatter.format_identity(identity_bytes)
        assert result == expected
    
    def test_parse_identity_convenience(self):
        """Test parse_identity convenience function."""
        identity_bytes = secrets.token_bytes(32)
        hex_str = identity_bytes.hex()
        result = parse_identity(hex_str)
        assert result == identity_bytes
    
    def test_format_connection_id_convenience(self):
        """Test format_connection_id convenience function."""
        connection_id = 0x123456789abcdef0
        result = format_connection_id(connection_id)
        expected = ConnectionIdFormatter.format_connection_id(connection_id)
        assert result == expected
    
    def test_parse_connection_id_convenience(self):
        """Test parse_connection_id convenience function."""
        connection_id_str = "123456789abcdef0"
        result = parse_connection_id(connection_id_str)
        assert result == 0x123456789abcdef0
    
    def test_parse_uri_convenience(self):
        """Test parse_uri convenience function."""
        uri = "ws://localhost:3000"
        result = parse_uri(uri)
        assert isinstance(result, ParsedURI)
        assert result.host == "localhost"
    
    def test_validate_spacetimedb_uri_convenience(self):
        """Test validate_spacetimedb_uri convenience function."""
        assert validate_spacetimedb_uri("ws://localhost:3000") == True
        assert validate_spacetimedb_uri("invalid") == False
    
    def test_normalize_uri_convenience(self):
        """Test normalize_uri convenience function."""
        uri = "ws://localhost:3000/database"
        result = normalize_uri(uri)
        assert result == "ws://localhost:3000/database"
    
    def test_generate_request_id_convenience(self):
        """Test generate_request_id convenience function."""
        id1 = generate_request_id()
        id2 = generate_request_id()
        assert id1 != id2
        assert id1.startswith("req_")
    
    def test_bytes_to_human_readable_convenience(self):
        """Test bytes_to_human_readable convenience function."""
        result = bytes_to_human_readable(1024)
        assert result == "1.0 KB"
    
    def test_duration_to_human_readable_convenience(self):
        """Test duration_to_human_readable convenience function."""
        result = duration_to_human_readable(1.5)
        assert result == "1.5 s"
    
    def test_get_system_info_convenience(self):
        """Test get_system_info convenience function."""
        info = get_system_info()
        assert "platform" in info
        assert "python_version" in info


class TestGlobalInstances:
    """Test global instances."""
    
    def test_global_request_id_generator(self):
        """Test global request ID generator."""
        id1 = request_id_generator.generate()
        id2 = request_id_generator.generate()
        assert id1 != id2
        assert id1.startswith("req_")
    
    def test_global_performance_profiler(self):
        """Test global performance profiler."""
        start_time = performance_profiler.start_timer("global_test")
        performance_profiler.end_timer("global_test", start_time)
        
        stats = performance_profiler.get_timer_stats("global_test")
        assert stats["count"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 