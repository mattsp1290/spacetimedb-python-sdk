# SpacetimeDB Python SDK - Testing Recommendations
## Comprehensive Test Strategy Improvements

**Review Date:** July 20, 2025  
**Current Test Coverage:** Analysis of 140+ test files  
**Focus Areas:** Security, Performance, Integration, and Reliability Testing  

---

## Current Testing Infrastructure Assessment

### **Existing Test Structure ✅**
```
tests/
├── integration/           # Basic integration tests (4 files)
├── performance/           # Minimal performance tests (1 file)  
├── property/              # Property-based testing (2 files)
├── security/              # Basic security tests (2 files)
├── refactoring/           # Refactoring validation (15+ files)
└── 140+ individual test files
```

### **Current Strengths**
- ✅ **Comprehensive test count:** 140+ test files showing testing commitment
- ✅ **Property-based testing:** Framework exists in `tests/property/`
- ✅ **Integration testing:** Basic structure in `tests/integration/`
- ✅ **Mock infrastructure:** `mock_spacetimedb_server.py` provides foundation
- ✅ **Refactoring validation:** Dedicated test suite for architecture changes

### **Critical Gaps Identified**
- 🚨 **Security testing:** No tests for injection attacks, malformed inputs
- 🚨 **Chaos engineering:** No connection failure simulation
- 🚨 **Performance regression:** Limited load testing capabilities
- 🚨 **Edge cases:** Insufficient boundary condition testing
- 🚨 **Error scenarios:** Missing negative test coverage

---

## Enhanced Testing Strategy

### **1. Security Testing Framework**

#### **Current Security Test Coverage:** ⚠️ Minimal
**Files:** `tests/security/test_credential_security.py`, `tests/security/test_input_validation.py`

#### **Required Security Test Suite:**

**Create:** `tests/security/test_json_security.py`
```python
"""Comprehensive JSON security testing."""
import pytest
from spacetimedb_sdk.security.json_validator import safe_json_loads, JSONSecurityError

class TestJSONSecurity:
    """Test protection against JSON-based attacks."""
    
    def test_json_bomb_protection(self):
        """Test protection against deeply nested JSON bombs."""
        # Create JSON bomb with excessive nesting
        json_bomb = '{"a":' * 1000 + '{}' + '}' * 1000
        
        with pytest.raises(JSONSecurityError, match="nesting too deep"):
            safe_json_loads(json_bomb)
    
    def test_large_json_protection(self):
        """Test protection against oversized JSON payloads."""
        # Create JSON exceeding size limits
        large_json = '{"data": "' + 'x' * (11 * 1024 * 1024) + '"}'
        
        with pytest.raises(JSONSecurityError, match="payload too large"):
            safe_json_loads(large_json)
    
    def test_json_injection_attempts(self):
        """Test protection against JSON injection attacks."""
        injection_attempts = [
            '{"eval": "__import__(\\"os\\").system(\\"rm -rf /\\")"}',
            '{"__proto__": {"isAdmin": true}}',
            '{"constructor": {"prototype": {"polluted": true}}}',
        ]
        
        for attempt in injection_attempts:
            # Should parse but not execute malicious code
            result = safe_json_loads(attempt)
            assert isinstance(result, dict)
            # Verify no code execution occurred
    
    @pytest.mark.parametrize("malformed_json", [
        '{"incomplete": ',
        '{"duplicate": "key", "duplicate": "value"}',
        '{"unicode": "\\u0000\\u0001\\u0002"}',
        '{"number": 123456789012345678901234567890}',  # Overflow
    ])
    def test_malformed_json_handling(self, malformed_json):
        """Test proper handling of malformed JSON."""
        with pytest.raises(JSONSecurityError):
            safe_json_loads(malformed_json)
```

**Create:** `tests/security/test_path_traversal.py`
```python
"""Path traversal security testing."""
import pytest
from spacetimedb_sdk.websocket_client import validate_database_identifier
from spacetimedb_sdk.exceptions import ValidationError

class TestPathTraversalProtection:
    """Test protection against path traversal attacks."""
    
    @pytest.mark.parametrize("attack_vector", [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded
        "....//....//....//etc/passwd",              # Double encoding
        "/etc/passwd",                               # Absolute path
        "C:\\windows\\system32",                     # Windows absolute
        "database/../../../secret",                  # Mixed legitimate/attack
        "data\x00base",                             # Null byte injection
        "database\x2e\x2e\x2fpasswd",              # Hex encoded traversal
    ])
    def test_path_traversal_vectors(self, attack_vector):
        """Test various path traversal attack vectors."""
        with pytest.raises(ValidationError, match="Path traversal|Invalid|forbidden"):
            validate_database_identifier(attack_vector)
    
    @pytest.mark.parametrize("valid_identifier", [
        "valid_database",
        "test-db-123",
        "database_2024",
        "MyDatabase",
        "db1",
    ])
    def test_valid_identifiers(self, valid_identifier):
        """Test that valid identifiers are accepted."""
        result = validate_database_identifier(valid_identifier)
        assert result == valid_identifier
```

**Create:** `tests/security/test_authentication_attacks.py`
```python
"""Authentication security testing."""
import pytest
from spacetimedb_sdk.auth.storage import SecureAuthStorage, AuthCredentials
from spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler

class TestAuthenticationSecurity:
    """Test authentication security measures."""
    
    def test_token_replay_protection(self):
        """Test protection against token replay attacks."""
        # Implementation depends on token expiry mechanisms
        pass
    
    def test_credential_encryption_strength(self):
        """Test that stored credentials use strong encryption."""
        storage = SecureAuthStorage()
        creds = AuthCredentials(
            identity="test_user",
            token="sensitive_token_123",
            host="test.spacetimedb.com"
        )
        
        # Store credentials
        storage.store_credentials(creds)
        
        # Verify stored data is encrypted (not plaintext)
        with open(storage._get_storage_path(), 'rb') as f:
            stored_data = f.read()
            assert b"sensitive_token_123" not in stored_data
            assert b"test_user" not in stored_data
    
    def test_timing_attack_resistance(self):
        """Test that authentication timing is consistent."""
        import time
        
        handler = AuthenticationHandler()
        
        # Measure timing for valid vs invalid credentials
        valid_times = []
        invalid_times = []
        
        for _ in range(10):
            # Time valid authentication
            start = time.perf_counter()
            handler.authenticate(AuthCredentials("valid", "token", "host"))
            valid_times.append(time.perf_counter() - start)
            
            # Time invalid authentication
            start = time.perf_counter()
            handler.authenticate(AuthCredentials("invalid", "badtoken", "host"))
            invalid_times.append(time.perf_counter() - start)
        
        # Timing should be similar to prevent timing attacks
        avg_valid = sum(valid_times) / len(valid_times)
        avg_invalid = sum(invalid_times) / len(invalid_times)
        
        # Allow 20% variance to account for normal timing differences
        assert abs(avg_valid - avg_invalid) / max(avg_valid, avg_invalid) < 0.2
```

### **2. Performance & Load Testing**

#### **Current Performance Testing:** ⚠️ Limited
**File:** `tests/performance/test_performance_regression.py`

#### **Enhanced Performance Test Suite:**

**Create:** `tests/performance/test_connection_pool_performance.py`
```python
"""Connection pool performance testing."""
import asyncio
import time
import pytest
from concurrent.futures import ThreadPoolExecutor
from spacetimedb_sdk.connection_pool import ConnectionPool

class TestConnectionPoolPerformance:
    """Performance tests for connection pooling."""
    
    @pytest.mark.performance
    def test_connection_acquisition_latency(self):
        """Test connection acquisition is O(1)."""
        pool = ConnectionPool(max_connections=100)
        
        # Fill pool with connections
        for i in range(100):
            pool.add_connection(f"conn_{i}")
        
        # Measure acquisition time for different pool sizes
        sizes_to_test = [10, 50, 100]
        acquisition_times = {}
        
        for size in sizes_to_test:
            # Limit pool to test different sizes
            test_pool = ConnectionPool(max_connections=size)
            for i in range(size):
                test_pool.add_connection(f"conn_{i}")
            
            # Measure acquisition time
            start = time.perf_counter()
            for _ in range(1000):  # 1000 acquisitions
                conn = test_pool.get_connection()
                test_pool.return_connection(conn)
            end = time.perf_counter()
            
            acquisition_times[size] = (end - start) / 1000
        
        # Verify O(1) behavior - time should not increase significantly with pool size
        time_10 = acquisition_times[10]
        time_100 = acquisition_times[100]
        
        # Time for 100 connections should be at most 2x time for 10 connections
        assert time_100 <= time_10 * 2, f"Connection acquisition not O(1): {acquisition_times}"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_connection_access(self):
        """Test connection pool under concurrent load."""
        pool = ConnectionPool(max_connections=20)
        
        # Fill pool
        for i in range(20):
            pool.add_connection(f"conn_{i}")
        
        async def worker():
            """Worker that rapidly acquires/releases connections."""
            for _ in range(100):
                conn = pool.get_connection()
                await asyncio.sleep(0.001)  # Simulate work
                pool.return_connection(conn)
        
        # Run 50 concurrent workers
        start = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(50)])
        end = time.perf_counter()
        
        total_time = end - start
        operations_per_second = (50 * 100) / total_time
        
        # Should handle at least 1000 operations/second
        assert operations_per_second > 1000, f"Poor concurrent performance: {operations_per_second} ops/sec"
    
    @pytest.mark.performance
    def test_memory_usage_under_load(self):
        """Test memory usage remains bounded under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        pool = ConnectionPool(max_connections=1000)
        
        # Create many connections
        for i in range(1000):
            pool.add_connection(f"conn_{i}")
        
        # Simulate heavy usage
        for _ in range(10000):
            conn = pool.get_connection()
            pool.return_connection(conn)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024, f"Excessive memory usage: {memory_increase} bytes"
```

**Create:** `tests/performance/test_protocol_performance.py`
```python
"""Protocol performance testing."""
import time
import pytest
from spacetimedb_sdk.protocol import ProtocolHandler
from spacetimedb_sdk.bsatn import BsatnWriter, BsatnReader

class TestProtocolPerformance:
    """Performance tests for protocol operations."""
    
    @pytest.mark.performance
    @pytest.mark.parametrize("message_size", [1024, 10240, 102400])  # 1KB, 10KB, 100KB
    def test_serialization_performance(self, message_size):
        """Test BSATN serialization performance for different message sizes."""
        # Create test data
        test_data = {
            "large_string": "x" * message_size,
            "array": list(range(100)),
            "nested": {"a": {"b": {"c": "value"}}}
        }
        
        writer = BsatnWriter()
        reader = BsatnReader()
        
        # Measure serialization time
        start = time.perf_counter()
        for _ in range(100):  # 100 iterations
            serialized = writer.write(test_data)
        serialize_time = time.perf_counter() - start
        
        # Measure deserialization time
        start = time.perf_counter()
        for _ in range(100):  # 100 iterations
            deserialized = reader.read(serialized)
        deserialize_time = time.perf_counter() - start
        
        # Performance expectations (adjust based on benchmarking)
        serialize_rate = (100 * message_size) / serialize_time  # bytes/second
        deserialize_rate = (100 * message_size) / deserialize_time
        
        # Should handle at least 10MB/s for serialization
        assert serialize_rate > 10 * 1024 * 1024, f"Slow serialization: {serialize_rate} bytes/sec"
        assert deserialize_rate > 10 * 1024 * 1024, f"Slow deserialization: {deserialize_rate} bytes/sec"
```

### **3. Chaos Engineering & Reliability Testing**

#### **Current Chaos Testing:** ❌ None

#### **Required Chaos Engineering Suite:**

**Create:** `tests/chaos/test_connection_resilience.py`
```python
"""Chaos engineering tests for connection resilience."""
import asyncio
import random
import pytest
from unittest.mock import patch
from spacetimedb_sdk.websocket_client import WebSocketClient
from spacetimedb_sdk.exceptions import ConnectionError

class TestConnectionResilience:
    """Chaos engineering tests for connection handling."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_random_connection_failures(self):
        """Test resilience against random connection failures."""
        client = WebSocketClient("ws://test.server.com")
        
        failure_count = 0
        success_count = 0
        
        async def failing_send(message):
            """Randomly failing send operation."""
            nonlocal failure_count, success_count
            if random.random() < 0.3:  # 30% failure rate
                failure_count += 1
                raise ConnectionError("Simulated network failure")
            else:
                success_count += 1
                return "success"
        
        with patch.object(client, '_send_message', failing_send):
            # Attempt 100 operations with random failures
            for i in range(100):
                try:
                    await client.send_message(f"test_message_{i}")
                except ConnectionError:
                    # Should handle gracefully
                    pass
                
                await asyncio.sleep(0.01)  # Small delay
        
        # Should have experienced failures but continued operating
        assert failure_count > 0, "No failures simulated"
        assert success_count > 0, "No successful operations"
        
        # Client should still be in a valid state
        assert client._connection_state == "connected" or client._reconnect_attempts > 0
    
    @pytest.mark.chaos
    def test_memory_pressure_handling(self):
        """Test behavior under memory pressure."""
        client = WebSocketClient("ws://test.server.com")
        
        # Simulate memory pressure by creating large objects
        large_objects = []
        
        try:
            # Fill memory with large objects while using client
            for i in range(1000):
                # Create 1MB object
                large_objects.append(bytearray(1024 * 1024))
                
                # Try to use client
                client.send_message(f"message_{i}")
                
                # Every 100 iterations, clear some memory
                if i % 100 == 0:
                    large_objects = large_objects[-50:]  # Keep only last 50
        
        except MemoryError:
            # Should handle memory errors gracefully
            pass
        
        # Client should still be responsive
        assert client.is_connected() or client._connection_state == "recovering"
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_message_corruption_handling(self):
        """Test handling of corrupted messages."""
        client = WebSocketClient("ws://test.server.com")
        
        corrupted_messages = [
            b"",                                    # Empty message
            b"\x00\x01\x02\x03",                  # Binary garbage
            b"invalid json {{{",                   # Malformed JSON
            b"null" * 10000,                      # Repetitive content
            bytes(range(256)),                     # All byte values
            b"\xff" * 1000,                       # High-bit chars
        ]
        
        error_count = 0
        
        for corrupted in corrupted_messages:
            try:
                await client._handle_message(corrupted)
            except Exception as e:
                error_count += 1
                # Should log error but not crash
                assert isinstance(e, (ValueError, ConnectionError))
        
        # Should have handled all corrupted messages
        assert error_count == len(corrupted_messages)
        
        # Client should still be functional
        assert client._connection_state != "crashed"
```

**Create:** `tests/chaos/test_network_conditions.py`
```python
"""Network condition simulation testing."""
import asyncio
import time
import pytest
from unittest.mock import patch, AsyncMock
from spacetimedb_sdk.websocket_client import WebSocketClient

class TestNetworkConditions:
    """Test behavior under various network conditions."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_high_latency_handling(self):
        """Test behavior under high network latency."""
        client = WebSocketClient("ws://test.server.com")
        
        async def slow_send(message):
            """Simulate high latency."""
            await asyncio.sleep(random.uniform(1.0, 3.0))  # 1-3 second delay
            return "success"
        
        with patch.object(client, '_send_message', slow_send):
            start_time = time.time()
            
            # Send multiple messages
            tasks = []
            for i in range(10):
                task = asyncio.create_task(client.send_message(f"msg_{i}"))
                tasks.append(task)
            
            # Wait for all messages with timeout
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=30)
            except asyncio.TimeoutError:
                pytest.fail("Client failed to handle high latency conditions")
            
            total_time = time.time() - start_time
            
            # Should complete within reasonable time despite latency
            assert total_time < 35, f"Too slow under high latency: {total_time}s"
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_packet_loss_simulation(self):
        """Test behavior with simulated packet loss."""
        client = WebSocketClient("ws://test.server.com")
        
        async def lossy_send(message):
            """Simulate packet loss."""
            if random.random() < 0.2:  # 20% packet loss
                raise ConnectionError("Packet lost")
            return "success"
        
        with patch.object(client, '_send_message', lossy_send):
            successful_sends = 0
            failed_sends = 0
            
            for i in range(50):
                try:
                    await client.send_message(f"message_{i}")
                    successful_sends += 1
                except ConnectionError:
                    failed_sends += 1
                    # Client should retry automatically
                
                await asyncio.sleep(0.1)
            
            # Should have both successes and failures
            assert successful_sends > 0, "No successful sends"
            assert failed_sends > 0, "No packet loss simulated"
            
            # Should achieve reasonable success rate despite packet loss
            success_rate = successful_sends / (successful_sends + failed_sends)
            assert success_rate > 0.5, f"Poor success rate: {success_rate}"
```

### **4. Integration Testing Enhancement**

#### **Current Integration Tests:** ⚠️ Basic
**Files:** `tests/integration/test_basic_connection_mock.py`, etc.

#### **Enhanced Integration Test Suite:**

**Create:** `tests/integration/test_end_to_end_workflows.py`
```python
"""End-to-end workflow testing."""
import pytest
import asyncio
from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.auth.storage import AuthCredentials

class TestEndToEndWorkflows:
    """Test complete user workflows."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_user_session(self):
        """Test a complete user session from auth to data operations."""
        # 1. Authentication
        client = SpacetimeDBClient()
        credentials = AuthCredentials(
            identity="test_user",
            token="test_token",
            host="test.spacetimedb.com"
        )
        
        await client.authenticate(credentials)
        assert client.is_authenticated()
        
        # 2. Database connection
        await client.connect("test_database")
        assert client.is_connected()
        
        # 3. Subscribe to tables
        subscription = await client.subscribe("SELECT * FROM users WHERE active = true")
        assert subscription.is_active()
        
        # 4. Perform operations
        result = await client.call_reducer("create_user", {"name": "Test User"})
        assert result.success
        
        # 5. Verify subscription received update
        await asyncio.sleep(0.1)  # Allow time for subscription update
        updates = subscription.get_updates()
        assert len(updates) > 0
        
        # 6. Clean disconnect
        await client.disconnect()
        assert not client.is_connected()
    
    @pytest.mark.integration
    def test_multi_client_coordination(self):
        """Test coordination between multiple clients."""
        client1 = SpacetimeDBClient()
        client2 = SpacetimeDBClient()
        
        # Both clients connect to same database
        client1.connect("shared_database")
        client2.connect("shared_database")
        
        # Client 1 subscribes to updates
        subscription = client1.subscribe("SELECT * FROM messages")
        
        # Client 2 creates data
        result = client2.call_reducer("send_message", {"text": "Hello from client2"})
        assert result.success
        
        # Client 1 should receive the update
        time.sleep(0.1)  # Allow propagation
        updates = subscription.get_updates()
        assert any("Hello from client2" in str(update) for update in updates)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test recovery from various error conditions."""
        client = SpacetimeDBClient()
        
        # Test auth failure recovery
        bad_credentials = AuthCredentials("bad", "credentials", "host")
        with pytest.raises(AuthenticationError):
            await client.authenticate(bad_credentials)
        
        # Should be able to authenticate with good credentials after failure
        good_credentials = AuthCredentials("good", "credentials", "host")
        await client.authenticate(good_credentials)
        
        # Test connection failure recovery
        with patch.object(client, '_websocket') as mock_ws:
            mock_ws.close.side_effect = ConnectionError("Network failure")
            
            # Trigger disconnect
            await client.disconnect()
            
            # Should be able to reconnect
            await client.connect("test_database")
            assert client.is_connected()
```

### **5. Property-Based Testing Enhancement**

#### **Current Property Testing:** ✅ Foundation exists
**Files:** `tests/property/test_bounded_cache.py`, `tests/property/test_event_system.py`

#### **Enhanced Property-Based Tests:**

**Create:** `tests/property/test_protocol_properties.py`
```python
"""Property-based testing for protocol operations."""
from hypothesis import given, strategies as st
import pytest
from spacetimedb_sdk.bsatn import BsatnWriter, BsatnReader

class TestProtocolProperties:
    """Property-based tests for protocol correctness."""
    
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=100),
        values=st.one_of(
            st.text(max_size=1000),
            st.integers(-2**31, 2**31-1),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans()
        ),
        min_size=1,
        max_size=10
    ))
    def test_serialization_roundtrip(self, data):
        """Test that any serializable data can roundtrip through BSATN."""
        writer = BsatnWriter()
        reader = BsatnReader()
        
        # Serialize
        serialized = writer.write(data)
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0
        
        # Deserialize
        deserialized = reader.read(serialized)
        
        # Should be identical
        assert deserialized == data
    
    @given(st.text(min_size=1, max_size=255, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'),  # Letters, digits, underscore
        whitelist_characters='-'
    )))
    def test_database_identifier_validation(self, identifier):
        """Test that valid identifiers are always accepted."""
        from spacetimedb_sdk.websocket_client import validate_database_identifier
        
        # Should not raise for valid identifiers
        result = validate_database_identifier(identifier)
        assert result == identifier
    
    @given(st.lists(
        st.dictionaries(
            keys=st.sampled_from(['type', 'data', 'id']),
            values=st.text(max_size=100)
        ),
        min_size=1,
        max_size=100
    ))
    def test_message_batch_processing(self, messages):
        """Test that message batches are processed correctly."""
        from spacetimedb_sdk.protocol import ProtocolHandler
        
        handler = ProtocolHandler()
        
        # Process all messages
        results = []
        for message in messages:
            try:
                result = handler.process_message(message)
                results.append(result)
            except Exception as e:
                # Some messages may be invalid, that's ok
                results.append(e)
        
        # Should process all messages without crashing
        assert len(results) == len(messages)
```

---

## Test Infrastructure Improvements

### **Enhanced Mock Server**

**Enhance:** `tests/mock_spacetimedb_server.py`
```python
"""Enhanced mock SpacetimeDB server with comprehensive simulation."""
import asyncio
import json
import random
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

@dataclass
class ErrorInjectionConfig:
    """Configuration for error injection in mock server."""
    connection_failure_rate: float = 0.0
    message_corruption_rate: float = 0.0
    latency_min_ms: int = 0
    latency_max_ms: int = 0
    memory_limit_mb: Optional[int] = None

class EnhancedMockServer:
    """Comprehensive mock server with error injection and realistic simulation."""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.clients: Dict[str, MockClient] = {}
        self.databases: Dict[str, MockDatabase] = {}
        self.error_config = ErrorInjectionConfig()
        self.message_log: List[Dict] = []
        self.performance_metrics = {
            'messages_processed': 0,
            'errors_injected': 0,
            'avg_latency_ms': 0.0
        }
    
    def configure_error_injection(self, config: ErrorInjectionConfig):
        """Configure error injection parameters for chaos testing."""
        self.error_config = config
    
    async def simulate_network_conditions(self):
        """Simulate realistic network conditions."""
        if self.error_config.latency_max_ms > 0:
            delay = random.uniform(
                self.error_config.latency_min_ms / 1000,
                self.error_config.latency_max_ms / 1000
            )
            await asyncio.sleep(delay)
    
    def inject_message_corruption(self, message: bytes) -> bytes:
        """Randomly corrupt messages for robustness testing."""
        if random.random() < self.error_config.message_corruption_rate:
            self.performance_metrics['errors_injected'] += 1
            # Random corruption strategies
            corruption_type = random.choice(['truncate', 'modify', 'duplicate'])
            
            if corruption_type == 'truncate':
                return message[:len(message)//2]
            elif corruption_type == 'modify':
                # Flip random bits
                corrupted = bytearray(message)
                for _ in range(min(10, len(corrupted))):
                    idx = random.randint(0, len(corrupted) - 1)
                    corrupted[idx] = random.randint(0, 255)
                return bytes(corrupted)
            else:  # duplicate
                return message + message
        
        return message
    
    async def handle_client_message(self, client_id: str, message: dict) -> dict:
        """Handle client message with error injection."""
        await self.simulate_network_conditions()
        
        # Inject connection failures
        if random.random() < self.error_config.connection_failure_rate:
            raise ConnectionError("Simulated connection failure")
        
        # Process message normally
        self.message_log.append({
            'timestamp': time.time(),
            'client_id': client_id,
            'message': message,
            'type': 'received'
        })
        
        self.performance_metrics['messages_processed'] += 1
        
        # Simulate different message types
        if message.get('type') == 'authenticate':
            return self._handle_auth(client_id, message)
        elif message.get('type') == 'subscribe':
            return self._handle_subscribe(client_id, message)
        elif message.get('type') == 'call_reducer':
            return self._handle_reducer_call(client_id, message)
        else:
            return {'type': 'error', 'message': 'Unknown message type'}
    
    def get_performance_metrics(self) -> Dict:
        """Get server performance metrics for analysis."""
        return self.performance_metrics.copy()
    
    def get_message_log(self) -> List[Dict]:
        """Get complete message log for debugging."""
        return self.message_log.copy()
```

### **Test Data Generators**

**Create:** `tests/fixtures/data_generators.py`
```python
"""Test data generators for comprehensive testing."""
from typing import Dict, Any, List
import random
import string
from dataclasses import dataclass

@dataclass
class TestDataProfile:
    """Profile for generating test data with specific characteristics."""
    complexity: str  # 'simple', 'medium', 'complex'
    size: str       # 'small', 'medium', 'large'
    types: List[str] # Data types to include

class TestDataGenerator:
    """Generate realistic test data for various scenarios."""
    
    @staticmethod
    def generate_user_data(profile: TestDataProfile) -> Dict[str, Any]:
        """Generate realistic user data."""
        complexity_configs = {
            'simple': {
                'fields': ['id', 'name', 'email'],
                'max_string_length': 50
            },
            'medium': {
                'fields': ['id', 'name', 'email', 'age', 'active', 'created_at'],
                'max_string_length': 100
            },
            'complex': {
                'fields': [
                    'id', 'name', 'email', 'age', 'active', 'created_at',
                    'profile', 'preferences', 'metadata', 'tags'
                ],
                'max_string_length': 500
            }
        }
        
        config = complexity_configs[profile.complexity]
        user_data = {}
        
        for field in config['fields']:
            if field == 'id':
                user_data[field] = random.randint(1, 1000000)
            elif field in ['name', 'email']:
                length = random.randint(5, config['max_string_length'])
                user_data[field] = ''.join(random.choices(string.ascii_letters, k=length))
            elif field == 'age':
                user_data[field] = random.randint(18, 100)
            elif field == 'active':
                user_data[field] = random.choice([True, False])
            elif field == 'created_at':
                user_data[field] = random.randint(1600000000, 1700000000)  # Timestamp
            elif field in ['profile', 'preferences', 'metadata']:
                user_data[field] = TestDataGenerator._generate_nested_object(profile)
            elif field == 'tags':
                user_data[field] = [
                    ''.join(random.choices(string.ascii_lowercase, k=8))
                    for _ in range(random.randint(0, 5))
                ]
        
        return user_data
    
    @staticmethod
    def generate_stress_test_data(size: str) -> List[Dict[str, Any]]:
        """Generate data for stress testing."""
        size_configs = {
            'small': 100,
            'medium': 10000,
            'large': 100000
        }
        
        count = size_configs[size]
        profile = TestDataProfile(complexity='medium', size=size, types=['user'])
        
        return [
            TestDataGenerator.generate_user_data(profile)
            for _ in range(count)
        ]
```

---

## Testing Pipeline Integration

### **CI/CD Testing Stages**

```yaml
# .github/workflows/comprehensive-testing.yml
name: Comprehensive Testing Pipeline

on: [push, pull_request]

jobs:
  security-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt
          pip install bandit safety
      - name: Security Tests
        run: |
          pytest tests/security/ -v
          bandit -r src/
          safety check
  
  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Performance Tests
        run: |
          pytest tests/performance/ -v --benchmark-only
  
  chaos-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Chaos Engineering Tests
        run: |
          pytest tests/chaos/ -v -m chaos
  
  integration-tests:
    runs-on: ubuntu-latest
    services:
      spacetimedb:
        image: spacetimedb/spacetimedb:latest
        ports:
          - 3000:3000
    steps:
      - uses: actions/checkout@v2
      - name: Integration Tests
        run: |
          pytest tests/integration/ -v
```

### **Test Coverage Goals**

- **Overall Coverage:** 95%+
- **Security Tests:** 100% coverage of attack vectors
- **Performance Tests:** All critical paths benchmarked
- **Integration Tests:** All user workflows covered
- **Chaos Tests:** All failure modes tested

This comprehensive testing strategy transforms the SpacetimeDB Python SDK from basic test coverage to production-grade reliability assurance.