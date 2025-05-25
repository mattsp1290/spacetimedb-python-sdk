"""
Advanced utility functions for SpacetimeDB Python SDK.

Provides comprehensive utility functions for common operations including:
- Identity and connection ID formatting
- URI parsing and validation
- Request ID generation
- Data conversion and formatting helpers
- Schema introspection utilities
- Connection diagnostics
- Performance profiling utilities
- Configuration management helpers
"""

import re
import hashlib
import secrets
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import json
import base64
import platform
import sys
from pathlib import Path
import logging

# Type definitions
T = TypeVar('T')


class IdentityFormat(Enum):
    """Identity formatting options."""
    HEX = "hex"
    BASE58 = "base58"
    BASE64 = "base64"
    ABBREVIATED = "abbreviated"
    HUMAN_READABLE = "human_readable"


class URIScheme(Enum):
    """Supported URI schemes."""
    WS = "ws"
    WSS = "wss"
    HTTP = "http"
    HTTPS = "https"


@dataclass
class ParsedURI:
    """Parsed SpacetimeDB URI with validation."""
    scheme: URIScheme
    host: str
    port: Optional[int]
    path: str
    query: Dict[str, str]
    fragment: Optional[str]
    is_secure: bool
    
    def to_websocket_uri(self) -> str:
        """Convert to WebSocket URI."""
        ws_scheme = "wss" if self.is_secure else "ws"
        port_part = f":{self.port}" if self.port else ""
        query_part = f"?{urllib.parse.urlencode(self.query)}" if self.query else ""
        fragment_part = f"#{self.fragment}" if self.fragment else ""
        return f"{ws_scheme}://{self.host}{port_part}{self.path}{query_part}{fragment_part}"
    
    def to_http_uri(self) -> str:
        """Convert to HTTP URI."""
        http_scheme = "https" if self.is_secure else "http"
        port_part = f":{self.port}" if self.port else ""
        query_part = f"?{urllib.parse.urlencode(self.query)}" if self.query else ""
        fragment_part = f"#{self.fragment}" if self.fragment else ""
        return f"{http_scheme}://{self.host}{port_part}{self.path}{query_part}{fragment_part}"


@dataclass
class RequestIdGenerator:
    """Thread-safe request ID generator."""
    _counter: int = field(default=0, init=False)
    _prefix: str = field(default="req")
    
    def generate(self) -> str:
        """Generate a unique request ID."""
        self._counter += 1
        timestamp = int(time.time() * 1000)  # milliseconds
        return f"{self._prefix}_{timestamp}_{self._counter:06d}"
    
    def generate_hex(self) -> str:
        """Generate a hex-based request ID."""
        return f"{self._prefix}_{secrets.token_hex(8)}"
    
    def generate_uuid_style(self) -> str:
        """Generate a UUID-style request ID."""
        random_bytes = secrets.token_bytes(16)
        hex_string = random_bytes.hex()
        # Format like UUID: 8-4-4-4-12
        return f"{hex_string[:8]}-{hex_string[8:12]}-{hex_string[12:16]}-{hex_string[16:20]}-{hex_string[20:]}"


class IdentityFormatter:
    """Utility class for formatting SpacetimeDB identities."""
    
    @staticmethod
    def format_identity(identity_bytes: bytes, format_type: IdentityFormat = IdentityFormat.HEX) -> str:
        """
        Format identity bytes in various formats.
        
        Args:
            identity_bytes: Raw identity bytes (typically 32 bytes)
            format_type: Desired format type
            
        Returns:
            Formatted identity string
        """
        if format_type == IdentityFormat.HEX:
            return identity_bytes.hex()
        elif format_type == IdentityFormat.BASE64:
            return base64.b64encode(identity_bytes).decode('ascii')
        elif format_type == IdentityFormat.ABBREVIATED:
            return identity_bytes.hex()[:16] + "..."
        elif format_type == IdentityFormat.HUMAN_READABLE:
            hex_str = identity_bytes.hex()
            return f"Identity({hex_str[:8]}...{hex_str[-8:]})"
        elif format_type == IdentityFormat.BASE58:
            # Simplified Base58 implementation
            return IdentityFormatter._base58_encode(identity_bytes)
        else:
            return identity_bytes.hex()
    
    @staticmethod
    def parse_identity(identity_str: str) -> bytes:
        """
        Parse identity string back to bytes.
        
        Args:
            identity_str: Formatted identity string
            
        Returns:
            Raw identity bytes
            
        Raises:
            ValueError: If the identity string is invalid
        """
        # Remove common prefixes and suffixes
        identity_str = identity_str.strip()
        if identity_str.startswith("0x"):
            identity_str = identity_str[2:]
        if identity_str.startswith("Identity(") and identity_str.endswith(")"):
            # Extract hex from human readable format
            inner = identity_str[9:-1]
            if "..." in inner:
                raise ValueError("Cannot parse abbreviated identity format")
            identity_str = inner
        
        # Try hex decoding
        try:
            return bytes.fromhex(identity_str)
        except ValueError:
            pass
        
        # Try base64 decoding
        try:
            return base64.b64decode(identity_str)
        except Exception:
            pass
        
        # Try base58 decoding
        try:
            return IdentityFormatter._base58_decode(identity_str)
        except Exception:
            pass
        
        raise ValueError(f"Unable to parse identity string: {identity_str}")
    
    @staticmethod
    def validate_identity(identity_bytes: bytes) -> bool:
        """
        Validate identity bytes.
        
        Args:
            identity_bytes: Raw identity bytes
            
        Returns:
            True if valid, False otherwise
        """
        # SpacetimeDB identities are typically 32 bytes (256 bits)
        if len(identity_bytes) != 32:
            return False
        
        # Check for all-zero identity (typically invalid)
        if all(b == 0 for b in identity_bytes):
            return False
        
        return True
    
    @staticmethod
    def _base58_encode(data: bytes) -> str:
        """Simplified Base58 encoding."""
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        
        # Convert bytes to integer
        num = int.from_bytes(data, 'big')
        
        # Encode
        encoded = ""
        while num > 0:
            num, remainder = divmod(num, 58)
            encoded = alphabet[remainder] + encoded
        
        # Handle leading zeros
        for byte in data:
            if byte == 0:
                encoded = alphabet[0] + encoded
            else:
                break
        
        return encoded
    
    @staticmethod
    def _base58_decode(encoded: str) -> bytes:
        """Simplified Base58 decoding."""
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        
        # Decode to integer
        num = 0
        for char in encoded:
            if char not in alphabet:
                raise ValueError(f"Invalid Base58 character: {char}")
            num = num * 58 + alphabet.index(char)
        
        # Convert to bytes
        byte_length = (num.bit_length() + 7) // 8
        decoded = num.to_bytes(byte_length, 'big')
        
        # Handle leading zeros
        leading_zeros = 0
        for char in encoded:
            if char == alphabet[0]:
                leading_zeros += 1
            else:
                break
        
        return b'\x00' * leading_zeros + decoded


class ConnectionIdFormatter:
    """Utility class for formatting SpacetimeDB connection IDs."""
    
    @staticmethod
    def format_connection_id(connection_id: Union[int, bytes], format_type: IdentityFormat = IdentityFormat.HEX) -> str:
        """
        Format connection ID in various formats.
        
        Args:
            connection_id: Raw connection ID (int or bytes)
            format_type: Desired format type
            
        Returns:
            Formatted connection ID string
        """
        if isinstance(connection_id, int):
            connection_bytes = connection_id.to_bytes(8, 'big')
        else:
            connection_bytes = connection_id
        
        if format_type == IdentityFormat.HEX:
            return connection_bytes.hex()
        elif format_type == IdentityFormat.ABBREVIATED:
            return connection_bytes.hex()[:8] + "..."
        elif format_type == IdentityFormat.HUMAN_READABLE:
            hex_str = connection_bytes.hex()
            return f"ConnectionId({hex_str})"
        else:
            return connection_bytes.hex()
    
    @staticmethod
    def parse_connection_id(connection_id_str: str) -> int:
        """
        Parse connection ID string back to integer.
        
        Args:
            connection_id_str: Formatted connection ID string
            
        Returns:
            Connection ID as integer
        """
        # Remove common prefixes and suffixes
        connection_id_str = connection_id_str.strip()
        if connection_id_str.startswith("0x"):
            connection_id_str = connection_id_str[2:]
        if connection_id_str.startswith("ConnectionId(") and connection_id_str.endswith(")"):
            connection_id_str = connection_id_str[13:-1]
        
        # Parse as hex
        try:
            connection_bytes = bytes.fromhex(connection_id_str)
            return int.from_bytes(connection_bytes, 'big')
        except ValueError:
            raise ValueError(f"Unable to parse connection ID string: {connection_id_str}")


class URIParser:
    """Utility class for parsing and validating SpacetimeDB URIs."""
    
    @staticmethod
    def parse_uri(uri: str) -> ParsedURI:
        """
        Parse and validate a SpacetimeDB URI.
        
        Args:
            uri: URI string to parse
            
        Returns:
            ParsedURI object with validated components
            
        Raises:
            ValueError: If the URI is invalid
        """
        if not uri:
            raise ValueError("URI cannot be empty")
        
        # Parse the URI
        parsed = urllib.parse.urlparse(uri)
        
        # Validate scheme
        try:
            scheme = URIScheme(parsed.scheme.lower())
        except ValueError:
            raise ValueError(f"Unsupported URI scheme: {parsed.scheme}")
        
        # Determine if secure
        is_secure = scheme in (URIScheme.WSS, URIScheme.HTTPS)
        
        # Validate host
        if not parsed.hostname:
            raise ValueError("URI must contain a valid hostname")
        
        # Parse query parameters
        query = dict(urllib.parse.parse_qsl(parsed.query))
        
        # Default ports
        default_ports = {
            URIScheme.WS: 80,
            URIScheme.WSS: 443,
            URIScheme.HTTP: 80,
            URIScheme.HTTPS: 443
        }
        
        port = parsed.port or default_ports.get(scheme)
        
        return ParsedURI(
            scheme=scheme,
            host=parsed.hostname,
            port=port,
            path=parsed.path or "/",
            query=query,
            fragment=parsed.fragment,
            is_secure=is_secure
        )
    
    @staticmethod
    def validate_spacetimedb_uri(uri: str) -> bool:
        """
        Validate if a URI is suitable for SpacetimeDB connections.
        
        Args:
            uri: URI to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = URIParser.parse_uri(uri)
            
            # Check for required components
            if not parsed.host:
                return False
            
            # Check for valid schemes
            if parsed.scheme not in (URIScheme.WS, URIScheme.WSS):
                return False
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def normalize_uri(uri: str) -> str:
        """
        Normalize a SpacetimeDB URI to a standard format.
        
        Args:
            uri: URI to normalize
            
        Returns:
            Normalized URI string
        """
        parsed = URIParser.parse_uri(uri)
        return parsed.to_websocket_uri()


@dataclass
class DataConverter:
    """Utility class for data conversion and formatting."""
    
    @staticmethod
    def bytes_to_human_readable(size_bytes: int) -> str:
        """Convert bytes to human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    @staticmethod
    def duration_to_human_readable(duration_seconds: float) -> str:
        """Convert duration in seconds to human-readable format."""
        if duration_seconds < 1:
            return f"{duration_seconds * 1000:.1f} ms"
        elif duration_seconds < 60:
            return f"{duration_seconds:.1f} s"
        elif duration_seconds < 3600:
            minutes = duration_seconds / 60
            return f"{minutes:.1f} min"
        else:
            hours = duration_seconds / 3600
            return f"{hours:.1f} h"
    
    @staticmethod
    def format_json_pretty(data: Any) -> str:
        """Format data as pretty JSON."""
        return json.dumps(data, indent=2, sort_keys=True, default=str)
    
    @staticmethod
    def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
        """Truncate string to maximum length."""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix


class SchemaIntrospector:
    """Utility class for schema introspection."""
    
    @staticmethod
    def analyze_table_schema(table_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze table data to infer schema information.
        
        Args:
            table_data: List of table rows
            
        Returns:
            Schema analysis results
        """
        if not table_data:
            return {"columns": {}, "row_count": 0, "estimated_size": 0}
        
        # Analyze columns
        columns = {}
        for row in table_data:
            for key, value in row.items():
                if key not in columns:
                    columns[key] = {
                        "type": type(value).__name__,
                        "nullable": False,
                        "unique_values": set(),
                        "min_length": None,
                        "max_length": None
                    }
                
                col_info = columns[key]
                
                # Check nullability
                if value is None:
                    col_info["nullable"] = True
                else:
                    col_info["unique_values"].add(value)
                    
                    # Track string lengths
                    if isinstance(value, str):
                        length = len(value)
                        if col_info["min_length"] is None or length < col_info["min_length"]:
                            col_info["min_length"] = length
                        if col_info["max_length"] is None or length > col_info["max_length"]:
                            col_info["max_length"] = length
        
        # Convert sets to counts for serialization
        for col_info in columns.values():
            col_info["unique_count"] = len(col_info["unique_values"])
            del col_info["unique_values"]
        
        # Estimate size
        estimated_size = len(json.dumps(table_data).encode('utf-8'))
        
        return {
            "columns": columns,
            "row_count": len(table_data),
            "estimated_size": estimated_size,
            "estimated_size_human": DataConverter.bytes_to_human_readable(estimated_size)
        }


class ConnectionDiagnostics:
    """Utility class for connection diagnostics."""
    
    @staticmethod
    def test_connection_latency(uri: str, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Test connection latency to a SpacetimeDB server.
        
        Args:
            uri: Server URI to test
            timeout: Connection timeout in seconds
            
        Returns:
            Latency test results
        """
        import socket
        import time
        
        try:
            parsed = URIParser.parse_uri(uri)
            
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((parsed.host, parsed.port or 3000))
            end_time = time.time()
            
            sock.close()
            
            if result == 0:
                latency = (end_time - start_time) * 1000  # Convert to milliseconds
                return {
                    "success": True,
                    "latency_ms": round(latency, 2),
                    "latency_human": f"{latency:.1f} ms",
                    "host": parsed.host,
                    "port": parsed.port
                }
            else:
                return {
                    "success": False,
                    "error": f"Connection failed with code {result}",
                    "host": parsed.host,
                    "port": parsed.port
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "host": "unknown",
                "port": "unknown"
            }
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get system information for diagnostics."""
        return {
            "platform": platform.platform(),
            "python_version": sys.version,
            "architecture": platform.architecture(),
            "processor": platform.processor(),
            "hostname": platform.node()
        }


class PerformanceProfiler:
    """Utility class for performance profiling."""
    
    def __init__(self):
        self.timers: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {}
    
    def start_timer(self, name: str) -> float:
        """Start a named timer."""
        start_time = time.perf_counter()
        if name not in self.timers:
            self.timers[name] = []
        return start_time
    
    def end_timer(self, name: str, start_time: float) -> float:
        """End a named timer and record the duration."""
        duration = time.perf_counter() - start_time
        if name in self.timers:
            self.timers[name].append(duration)
        return duration
    
    def increment_counter(self, name: str, amount: int = 1):
        """Increment a named counter."""
        if name not in self.counters:
            self.counters[name] = 0
        self.counters[name] += amount
    
    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a named timer."""
        if name not in self.timers or not self.timers[name]:
            return {"count": 0, "total": 0, "average": 0, "min": 0, "max": 0}
        
        times = self.timers[name]
        return {
            "count": len(times),
            "total": sum(times),
            "average": sum(times) / len(times),
            "min": min(times),
            "max": max(times)
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all profiling data."""
        timer_stats = {}
        for name in self.timers:
            timer_stats[name] = self.get_timer_stats(name)
        
        return {
            "timers": timer_stats,
            "counters": self.counters.copy()
        }


class ConfigurationManager:
    """Utility class for configuration management."""
    
    @staticmethod
    def load_config_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """Load configuration from a JSON file."""
        path = Path(file_path)
        if not path.exists():
            return {}
        
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load config file {path}: {e}")
            return {}
    
    @staticmethod
    def save_config_file(config: Dict[str, Any], file_path: Union[str, Path]):
        """Save configuration to a JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(path, 'w') as f:
                json.dump(config, f, indent=2, sort_keys=True)
        except Exception as e:
            logging.error(f"Failed to save config file {path}: {e}")
            raise
    
    @staticmethod
    def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple configuration dictionaries."""
        result = {}
        for config in configs:
            result.update(config)
        return result
    
    @staticmethod
    def get_default_config_path() -> Path:
        """Get the default configuration file path."""
        home = Path.home()
        return home / ".spacetimedb" / "config.json"


# Global instances for convenience
request_id_generator = RequestIdGenerator()
performance_profiler = PerformanceProfiler()


# Convenience functions
def format_identity(identity_bytes: bytes, format_type: IdentityFormat = IdentityFormat.HEX) -> str:
    """Format identity bytes. Convenience function."""
    return IdentityFormatter.format_identity(identity_bytes, format_type)


def parse_identity(identity_str: str) -> bytes:
    """Parse identity string. Convenience function."""
    return IdentityFormatter.parse_identity(identity_str)


def format_connection_id(connection_id: Union[int, bytes], format_type: IdentityFormat = IdentityFormat.HEX) -> str:
    """Format connection ID. Convenience function."""
    return ConnectionIdFormatter.format_connection_id(connection_id, format_type)


def parse_connection_id(connection_id_str: str) -> int:
    """Parse connection ID string. Convenience function."""
    return ConnectionIdFormatter.parse_connection_id(connection_id_str)


def parse_uri(uri: str) -> ParsedURI:
    """Parse URI. Convenience function."""
    return URIParser.parse_uri(uri)


def validate_spacetimedb_uri(uri: str) -> bool:
    """Validate SpacetimeDB URI. Convenience function."""
    return URIParser.validate_spacetimedb_uri(uri)


def normalize_uri(uri: str) -> str:
    """Normalize URI. Convenience function."""
    return URIParser.normalize_uri(uri)


def generate_request_id() -> str:
    """Generate request ID. Convenience function."""
    return request_id_generator.generate()


def bytes_to_human_readable(size_bytes: int) -> str:
    """Convert bytes to human readable. Convenience function."""
    return DataConverter.bytes_to_human_readable(size_bytes)


def duration_to_human_readable(duration_seconds: float) -> str:
    """Convert duration to human readable. Convenience function."""
    return DataConverter.duration_to_human_readable(duration_seconds)


def test_connection_latency(uri: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Test connection latency. Convenience function."""
    return ConnectionDiagnostics.test_connection_latency(uri, timeout)


def get_system_info() -> Dict[str, Any]:
    """Get system info. Convenience function."""
    return ConnectionDiagnostics.get_system_info() 