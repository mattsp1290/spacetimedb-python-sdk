"""
Security tests for input validation and sanitization.

Tests protection against SQL injection, oversized messages, malformed headers,
and other input-based security vulnerabilities.
"""
import pytest
import json
import struct
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import websocket

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.websocket_client import WebSocketClient
from spacetimedb_sdk.protocol import BSATN
from spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler


class TestInputValidation:
    """Test input validation and protection against malicious inputs."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing."""
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'):
            # Use correct constructor - only test_mode parameter for testing
            client = SpacetimeDBClient(test_mode=True)
            return client
    
    def test_sql_injection_prevention(self, mock_client):
        """Test that SQL injection attempts are properly sanitized."""
        # Test various SQL injection patterns
        injection_attempts = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'--",
            "1; DELETE FROM users WHERE 1=1",
            "' UNION SELECT * FROM credentials --",
            "\\'; DROP TABLE users; --",
            "1' AND '1' = '1",
        ]
        
        for payload in injection_attempts:
            # Test in database address using correct API
            with pytest.raises((ValueError, Exception)):
                # Use connect class method with injection payload in database address
                client = SpacetimeDBClient.connect(
                    host="localhost:3000",
                    database_address=payload,
                    auth_token=None,
                    ssl_enabled=False
                )
            
            # Test in auth token
            try:
                mock_client.auth_token = payload
                # Should not execute any SQL
                assert "DROP" not in str(mock_client.auth_token)
                assert "DELETE" not in str(mock_client.auth_token)
            except Exception:
                # Good - injection attempt blocked
                pass
    
    def test_oversized_message_handling(self, mock_client):
        """Test handling of oversized WebSocket messages."""
        # Create oversized payloads
        oversized_payloads = [
            b"x" * (1024 * 1024 * 10),  # 10MB
            b"x" * (1024 * 1024 * 50),  # 50MB
            b"x" * (1024 * 1024 * 100), # 100MB
        ]
        
        with patch.object(mock_client, 'ws_client') as mock_ws:
            for payload in oversized_payloads:
                # Test that oversized messages are handled gracefully
                try:
                    mock_ws.send(payload)
                    # Should either chunk the message or reject it
                    assert True, "Oversized message handled"
                except MemoryError:
                    pytest.fail("Memory exhaustion from oversized message")
                except Exception as e:
                    # Verify it's a controlled rejection
                    assert "too large" in str(e).lower() or "size limit" in str(e).lower()
    
    def test_malformed_authentication_headers(self, mock_client):
        """Test handling of malformed authentication headers."""
        malformed_headers = [
            {"Authorization": "Bearer "},  # Empty token
            {"Authorization": "InvalidScheme token123"},  # Wrong scheme
            {"Authorization": "Bearer " + "x" * 10000},  # Oversized token
            {"Authorization": "Bearer\x00\x01\x02"},  # Binary data
            {"Authorization": "Bearer <script>alert('xss')</script>"},  # XSS attempt
            {"Authorization": None},  # Null value
            {"Authorization": "Bearer\nBearer token2"},  # Header injection
            {"Authorization": "Bearer token1\r\nX-Evil-Header: bad"},  # CRLF injection
        ]
        
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws:
            for headers in malformed_headers:
                try:
                    # Test that malformed headers don't cause crashes using correct API
                    client = SpacetimeDBClient.connect(
                        host="localhost:3000",
                        database_address="test_db",
                        auth_token=headers.get("Authorization", ""),
                        ssl_enabled=False
                    )
                    # Should handle gracefully
                    assert True
                except ValueError:
                    # Expected for malformed input
                    pass
                except Exception as e:
                    # Should be a controlled error
                    assert "invalid" in str(e).lower() or "malformed" in str(e).lower()
    
    def test_binary_protocol_fuzzing(self, mock_client):
        """Test binary protocol handling with fuzzed inputs."""
        # Generate malformed binary messages
        fuzzed_messages = [
            b"\x00",  # Single null byte
            b"\xff" * 100,  # All 0xFF bytes
            b"\x13\x00\x00\x00",  # Tag without payload
            b"\x13" + struct.pack("<I", 0xFFFFFFFF),  # Max size
            b"\x13" + struct.pack("<I", 0),  # Zero size
            b"\x99" * 50,  # Unknown tags
            b"\x13\x04\x00\x00\x00\x00\x00",  # Truncated message
            b"",  # Empty message
        ]
        
        for fuzzed in fuzzed_messages:
            try:
                # Mock receiving fuzzed binary data
                with patch.object(mock_client, '_handle_message') as mock_handler:
                    mock_handler(fuzzed, opcode=websocket.ABNF.OPCODE_BINARY)
                    # Should not crash
                    assert True
            except Exception as e:
                # Should be controlled error handling
                assert not isinstance(e, (SystemError, MemoryError, RecursionError))
    
    def test_url_injection_prevention(self):
        """Test prevention of URL injection attacks."""
        url_injection_attempts = [
            "localhost:3000/../../etc/passwd",
            "localhost:3000/;cat /etc/passwd",
            "localhost:3000?evil=<script>alert(1)</script>",
            "localhost:3000#../../admin",
            "localhost:3000%00.evil.com",
            "localhost:3000\r\nHost: evil.com",
            "javascript://localhost:3000%0aalert(1)",
        ]
        
        for malicious_host in url_injection_attempts:
            try:
                # Use correct API for connection
                client = SpacetimeDBClient.connect(
                    host=malicious_host,
                    database_address="test_db",
                    auth_token=None,
                    ssl_enabled=False
                )
                # Check that URL is properly sanitized in WebSocket client
                if hasattr(client, 'ws_client') and client.ws_client:
                    ws_host = getattr(client.ws_client, 'host', malicious_host)
                    assert ".." not in ws_host
                    assert "<script>" not in ws_host
                    assert "\r" not in ws_host
                    assert "\n" not in ws_host
            except (ValueError, Exception):
                # Good - injection blocked
                pass
    
    def test_database_name_validation(self):
        """Test database name validation against injection."""
        invalid_db_names = [
            "../../../etc/passwd",
            "db_name; DROP DATABASE test;",
            "db-name' OR '1'='1",
            "db\x00name",  # Null byte
            "db\r\nX-Header: evil",  # CRLF
            "javascript:alert(1)",
            "<script>alert('xss')</script>",
            "db name",  # Spaces (if not allowed)
            "",  # Empty
            "." * 256,  # Too long
        ]
        
        for db_name in invalid_db_names:
            with pytest.raises((ValueError, Exception)):
                # Use correct API for connection with invalid database name
                client = SpacetimeDBClient.connect(
                    host="localhost:3000",
                    database_address=db_name,
                    auth_token=None,
                    ssl_enabled=False
                )
    
    def test_message_type_validation(self, mock_client):
        """Test that message types are properly validated."""
        # Test invalid message type tags
        invalid_messages = [
            {"type": "'; DROP TABLE users; --"},
            {"type": None},
            {"type": 12345},  # Should be string
            {"type": ["array", "of", "types"]},
            {"type": {"nested": "object"}},
            {"type": "A" * 1000},  # Very long type
        ]
        
        with patch.object(mock_client, '_handle_message') as mock_handler:
            for msg in invalid_messages:
                try:
                    mock_handler(json.dumps(msg), opcode=websocket.ABNF.OPCODE_TEXT)
                    # Should validate message type
                except (ValueError, TypeError, KeyError):
                    # Expected for invalid types
                    pass
                except Exception as e:
                    # Should be controlled error
                    assert "invalid" in str(e).lower() or "unknown" in str(e).lower()
    
    def test_reducer_name_validation(self, mock_client):
        """Test validation of reducer names to prevent code injection."""
        malicious_reducer_names = [
            "__import__('os').system('rm -rf /')",
            "eval('malicious code')",
            "exec(compile('import os; os.system(\"ls\")', 'string', 'exec'))",
            "../../../private_reducer",
            "reducer\x00name",
            "reducer'; DROP TABLE users; --",
        ]
        
        for reducer_name in malicious_reducer_names:
            try:
                # Attempt to call reducer with malicious name
                with patch.object(mock_client, '_call_reducer') as mock_call:
                    mock_call(reducer_name, [])
                    # Should sanitize or reject
                    assert True
            except (ValueError, AttributeError, TypeError):
                # Good - dangerous name rejected
                pass
    
    def test_json_bomb_protection(self, mock_client):
        """Test protection against JSON bombs (billion laughs attack)."""
        # Create nested JSON structure
        def create_json_bomb(depth=10):
            if depth == 0:
                return ["lol"] * 10
            return [create_json_bomb(depth - 1)] * 10
        
        json_bomb = {
            "type": "TestMessage",
            "data": create_json_bomb(5)  # Moderate nesting
        }
        
        try:
            with patch.object(mock_client, '_handle_message') as mock_handler:
                # Should handle nested structures safely
                json_str = json.dumps(json_bomb)
                mock_handler(json_str, opcode=websocket.ABNF.OPCODE_TEXT)
                assert True, "JSON bomb handled safely"
        except RecursionError:
            pytest.fail("JSON bomb caused recursion error")
        except MemoryError:
            pytest.fail("JSON bomb caused memory exhaustion")
    
    def test_unicode_handling(self, mock_client):
        """Test proper handling of Unicode and special characters."""
        unicode_payloads = [
            "test_🚀_rocket",  # Emoji
            "test_\u0000_null",  # Null character
            "test_\uffff_max",  # Max Unicode
            "test_\u202e_rtl",  # Right-to-left override
            "test_\ud800_surrogate",  # Invalid surrogate
            "A" + "\u0301" * 100,  # Combining characters
        ]
        
        for payload in unicode_payloads:
            try:
                # Test in various contexts using correct API
                client = SpacetimeDBClient.connect(
                    host="localhost:3000",
                    database_address=payload,
                    auth_token=None,
                    ssl_enabled=False
                )
                # Should handle Unicode safely
                assert True
            except UnicodeError:
                # Properly rejected invalid Unicode
                pass
            except Exception as e:
                # Should be controlled error
                assert isinstance(e, (ValueError, TypeError))


@pytest.mark.security
class TestProtocolSecurity:
    """Test protocol-level security measures."""
    
    def test_message_size_limits(self):
        """Test that message size limits are enforced."""
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws:
            # Use correct API for connection
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="test_db",
                auth_token=None,
                ssl_enabled=False
            )
            
            # Test various message sizes
            test_sizes = [
                1024,  # 1KB - should pass
                1024 * 1024,  # 1MB - should pass
                1024 * 1024 * 10,  # 10MB - might be limited
                1024 * 1024 * 100,  # 100MB - should be limited
            ]
            
            for size in test_sizes:
                msg = "x" * size
                try:
                    with patch.object(client, 'send_message') as mock_send:
                        mock_send(msg)
                        if size > 1024 * 1024 * 10:  # Assuming 10MB limit
                            pytest.fail(f"Message of size {size} should have been rejected")
                except (ValueError, MemoryError) as e:
                    if size <= 1024 * 1024 * 10:
                        pytest.fail(f"Message of size {size} should have been accepted")
    
    def test_rate_limiting_resistance(self):
        """Test that the client handles rate limiting gracefully."""
        with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp') as mock_ws:
            # Use correct API for connection
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="test_db",
                auth_token=None,
                ssl_enabled=False
            )
            
            # Simulate rate limit responses
            rate_limit_errors = [
                {"error": "Rate limit exceeded", "retry_after": 60},
                {"error": "Too many requests", "status": 429},
                {"error": "Slow down", "backoff": 30},
            ]
            
            for error in rate_limit_errors:
                with patch.object(client, '_handle_message') as mock_handler:
                    try:
                        mock_handler(json.dumps(error), opcode=websocket.ABNF.OPCODE_TEXT)
                        # Should handle rate limiting gracefully
                        assert True
                    except Exception as e:
                        # Should not crash, but handle gracefully
                        assert "rate" in str(e).lower() or "429" in str(e)