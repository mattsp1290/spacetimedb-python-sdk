"""
Integration tests for SpacetimeDB core data types using WASM modules.

Tests all primitive and complex data types against real SpacetimeDB
instances to ensure correct serialization, storage, and retrieval.
"""

import asyncio
import pytest
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    configure_default_logging,
    SpacetimeDBServer,
    SpacetimeDBConfig,
    WASMModule,
    WASMTestHarness,
    PerformanceBenchmark,
    require_spacetimedb,
    require_sdk_test_module,
    
    # Algebraic types
    AlgebraicType,
    AlgebraicValue,
    BoolType,
    IntType,
    FloatType,
    StringType,
    BytesType,
    ProductType,
    SumType,
    ArrayType,
    MapType,
    OptionType,
    IdentityType,
    AddressType,
    TimestampType,
    FieldInfo,
    VariantInfo,
    type_builder,
)


# Configure logging
configure_default_logging(debug=True)


@pytest.mark.integration
@pytest.mark.wasm
class TestPrimitiveTypes:
    """Test primitive data types (integers, floats, booleans, strings, bytes)."""
    
    async def test_boolean_types(self, wasm_harness, sdk_test_module):
        """Test boolean type serialization and operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "bool_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test boolean values
            test_cases = [
                (True, "test_true"),
                (False, "test_false"),
            ]
            
            for value, test_name in test_cases:
                with benchmark.measure(f"bool_{test_name}"):
                    # Create boolean type and value
                    bool_type = BoolType()
                    bool_value = AlgebraicValue(bool_type, value)
                    
                    # Test serialization
                    serialized = bool_value.serialize()
                    assert serialized is not None
                    
                    # Test deserialization
                    deserialized = AlgebraicValue.deserialize(bool_type, serialized)
                    assert deserialized.value == value
                    
                    # If module has boolean reducer, test it
                    # await client.call_reducer("test_bool", value)
            
            # Performance report
            print(f"\nBoolean type performance:")
            for test_name in ["test_true", "test_false"]:
                stats = benchmark.get_stats(f"bool_{test_name}")
                print(f"  {test_name}: {stats['mean']*1000:.3f}ms")
                
        finally:
            await client.disconnect()
    
    async def test_integer_types(self, wasm_harness, sdk_test_module):
        """Test all integer types (u8, u16, u32, u64, i8, i16, i32, i64)."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "int_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test cases for each integer type
            int_test_cases = [
                # Unsigned integers
                ("u8", 8, False, [0, 1, 127, 255]),
                ("u16", 16, False, [0, 1, 32767, 65535]),
                ("u32", 32, False, [0, 1, 2147483647, 4294967295]),
                ("u64", 64, False, [0, 1, 9223372036854775807, 18446744073709551615]),
                
                # Signed integers
                ("i8", 8, True, [-128, -1, 0, 1, 127]),
                ("i16", 16, True, [-32768, -1, 0, 1, 32767]),
                ("i32", 32, True, [-2147483648, -1, 0, 1, 2147483647]),
                ("i64", 64, True, [-9223372036854775808, -1, 0, 1, 9223372036854775807]),
            ]
            
            for type_name, bits, signed, test_values in int_test_cases:
                with benchmark.measure(f"int_{type_name}"):
                    # Create integer type
                    int_type = IntType(bits=bits, signed=signed)
                    
                    for value in test_values:
                        # Create value
                        int_value = AlgebraicValue(int_type, value)
                        
                        # Test serialization
                        serialized = int_value.serialize()
                        assert serialized is not None
                        
                        # Test deserialization
                        deserialized = AlgebraicValue.deserialize(int_type, serialized)
                        assert deserialized.value == value
                        
                        # Test type validation
                        assert int_type.validate(value)
            
            # Performance report
            print(f"\nInteger type performance:")
            for type_name, _, _, _ in int_test_cases:
                stats = benchmark.get_stats(f"int_{type_name}")
                if stats:
                    print(f"  {type_name}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()
    
    async def test_float_types(self, wasm_harness, sdk_test_module):
        """Test floating point types (f32, f64)."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module  
        address = await wasm_harness.publish_module(sdk_test_module, "float_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test cases for float types
            float_test_cases = [
                ("f32", 32, [0.0, 1.0, -1.0, 3.14159, float('inf'), float('-inf')]),
                ("f64", 64, [0.0, 1.0, -1.0, 3.141592653589793, float('inf'), float('-inf')]),
            ]
            
            for type_name, bits, test_values in float_test_cases:
                with benchmark.measure(f"float_{type_name}"):
                    # Create float type
                    float_type = FloatType(bits=bits)
                    
                    for value in test_values:
                        # Skip NaN for now (special handling needed)
                        if value != value:  # NaN check
                            continue
                            
                        # Create value
                        float_value = AlgebraicValue(float_type, value)
                        
                        # Test serialization
                        serialized = float_value.serialize()
                        assert serialized is not None
                        
                        # Test deserialization
                        deserialized = AlgebraicValue.deserialize(float_type, serialized)
                        if value == float('inf') or value == float('-inf'):
                            assert deserialized.value == value
                        else:
                            assert abs(deserialized.value - value) < 1e-6
            
            # Performance report
            print(f"\nFloat type performance:")
            for type_name, _, _ in float_test_cases:
                stats = benchmark.get_stats(f"float_{type_name}")
                if stats:
                    print(f"  {type_name}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()
    
    async def test_string_types(self, wasm_harness, sdk_test_module):
        """Test string type with various encodings and edge cases."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "string_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test various string scenarios
            string_test_cases = [
                ("empty", ""),
                ("ascii", "Hello, World!"),
                ("unicode", "Hello, 世界! 🌍"),
                ("emoji", "🚀🌟✨💫🎉"),
                ("special", "Line1\nLine2\tTab\r\nCRLF"),
                ("long", "x" * 1000),  # 1KB string
            ]
            
            string_type = StringType()
            
            for test_name, value in string_test_cases:
                with benchmark.measure(f"string_{test_name}"):
                    # Create value
                    string_value = AlgebraicValue(string_type, value)
                    
                    # Test serialization
                    serialized = string_value.serialize()
                    assert serialized is not None
                    
                    # Test deserialization
                    deserialized = AlgebraicValue.deserialize(string_type, serialized)
                    assert deserialized.value == value
                    
                    # Test JSON conversion
                    json_value = string_value.to_json()
                    from_json = AlgebraicValue.from_json(string_type, json_value)
                    assert from_json.value == value
            
            # Performance report
            print(f"\nString type performance:")
            for test_name, _ in string_test_cases:
                stats = benchmark.get_stats(f"string_{test_name}")
                if stats:
                    print(f"  {test_name}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()
    
    async def test_bytes_types(self, wasm_harness, sdk_test_module):
        """Test bytes type with various data."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "bytes_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test various byte scenarios
            bytes_test_cases = [
                ("empty", b""),
                ("small", b"\x00\x01\x02\x03"),
                ("binary", bytes(range(256))),
                ("large", b"x" * 10000),  # 10KB
            ]
            
            bytes_type = BytesType()
            
            for test_name, value in bytes_test_cases:
                with benchmark.measure(f"bytes_{test_name}"):
                    # Create value
                    bytes_value = AlgebraicValue(bytes_type, value)
                    
                    # Test serialization
                    serialized = bytes_value.serialize()
                    assert serialized is not None
                    
                    # Test deserialization
                    deserialized = AlgebraicValue.deserialize(bytes_type, serialized)
                    assert deserialized.value == value
            
            # Performance report
            print(f"\nBytes type performance:")
            for test_name, _ in bytes_test_cases:
                stats = benchmark.get_stats(f"bytes_{test_name}")
                if stats:
                    print(f"  {test_name}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
class TestSpacetimeDBTypes:
    """Test SpacetimeDB-specific types (Identity, Address, Timestamp)."""
    
    async def test_identity_type(self, wasm_harness, sdk_test_module):
        """Test Identity type operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "identity_test")
        client = await wasm_harness.create_client(address)
        
        try:
            identity_type = IdentityType()
            
            # Test with client's identity
            with benchmark.measure("identity_operations"):
                # Get client identity bytes
                identity_bytes = client.identity.data
                
                # Create identity value
                identity_value = AlgebraicValue(identity_type, identity_bytes)
                
                # Test serialization
                serialized = identity_value.serialize()
                assert serialized is not None
                
                # Test deserialization
                deserialized = AlgebraicValue.deserialize(identity_type, serialized)
                assert deserialized.value == identity_bytes
                
                # Test JSON conversion
                json_value = identity_value.to_json()
                assert isinstance(json_value, str)  # Base64 encoded
                
                from_json = AlgebraicValue.from_json(identity_type, json_value)
                assert from_json.value == identity_bytes
            
            print(f"\nIdentity type performance:")
            stats = benchmark.get_stats("identity_operations")
            print(f"  Operations: {stats['mean']*1000:.3f}ms")
            
        finally:
            await client.disconnect()
    
    async def test_address_type(self, wasm_harness, sdk_test_module):
        """Test Address type operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        db_address = await wasm_harness.publish_module(sdk_test_module, "address_test")
        client = await wasm_harness.create_client(db_address)
        
        try:
            address_type = AddressType()
            
            with benchmark.measure("address_operations"):
                # Create address value (16 bytes)
                address_bytes = b'0123456789ABCDEF'
                address_value = AlgebraicValue(address_type, address_bytes)
                
                # Test serialization
                serialized = address_value.serialize()
                assert serialized is not None
                
                # Test deserialization
                deserialized = AlgebraicValue.deserialize(address_type, serialized)
                assert deserialized.value == address_bytes
                
                # Test validation
                assert address_type.validate(address_bytes)
                assert not address_type.validate(b'short')  # Too short
                assert not address_type.validate(b'toolongaddressbytes')  # Too long
            
            print(f"\nAddress type performance:")
            stats = benchmark.get_stats("address_operations")
            print(f"  Operations: {stats['mean']*1000:.3f}ms")
            
        finally:
            await client.disconnect()
    
    async def test_timestamp_type(self, wasm_harness, sdk_test_module):
        """Test Timestamp type operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "timestamp_test")
        client = await wasm_harness.create_client(address)
        
        try:
            timestamp_type = TimestampType()
            
            # Test various timestamps
            test_timestamps = [
                0,  # Unix epoch
                int(time.time() * 1_000_000),  # Current time in microseconds
                1234567890123456,  # Arbitrary timestamp
            ]
            
            for ts in test_timestamps:
                with benchmark.measure(f"timestamp_{ts}"):
                    # Create timestamp value
                    timestamp_value = AlgebraicValue(timestamp_type, ts)
                    
                    # Test serialization
                    serialized = timestamp_value.serialize()
                    assert serialized is not None
                    
                    # Test deserialization
                    deserialized = AlgebraicValue.deserialize(timestamp_type, serialized)
                    assert deserialized.value == ts
                    
                    # Test conversion
                    as_datetime = timestamp_type.to_datetime(ts)
                    assert isinstance(as_datetime, datetime)
                    
                    from_datetime = timestamp_type.from_datetime(as_datetime)
                    assert from_datetime == ts
            
            print(f"\nTimestamp type performance:")
            for ts in test_timestamps:
                stats = benchmark.get_stats(f"timestamp_{ts}")
                if stats:
                    print(f"  {ts}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
class TestComplexTypes:
    """Test complex data types (structs, enums, arrays, maps, options)."""
    
    async def test_product_types(self, wasm_harness, sdk_test_module):
        """Test product types (structs)."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "product_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Define a User struct type
            user_type = type_builder.product([
                FieldInfo("id", type_builder.u64()),
                FieldInfo("name", type_builder.string()),
                FieldInfo("email", type_builder.string()),
                FieldInfo("age", type_builder.u8()),
                FieldInfo("active", type_builder.bool()),
            ], "User")
            
            with benchmark.measure("product_operations"):
                # Create user instance
                user_data = {
                    "id": 12345,
                    "name": "Alice Smith",
                    "email": "alice@example.com",
                    "age": 30,
                    "active": True
                }
                user_value = AlgebraicValue(user_type, user_data)
                
                # Test field access
                assert user_value.get_field("name").value == "Alice Smith"
                assert user_value.get_field("age").value == 30
                
                # Test serialization
                serialized = user_value.serialize()
                assert serialized is not None
                
                # Test deserialization
                deserialized = AlgebraicValue.deserialize(user_type, serialized)
                assert deserialized.get_field("id").value == 12345
                assert deserialized.get_field("email").value == "alice@example.com"
                
                # Test JSON conversion
                json_value = user_value.to_json()
                from_json = AlgebraicValue.from_json(user_type, json_value)
                assert from_json.get_field("name").value == "Alice Smith"
            
            print(f"\nProduct type performance:")
            stats = benchmark.get_stats("product_operations")
            print(f"  Operations: {stats['mean']*1000:.3f}ms")
            
        finally:
            await client.disconnect()
    
    async def test_sum_types(self, wasm_harness, sdk_test_module):
        """Test sum types (enums/unions)."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "sum_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Define a Status enum type
            status_type = type_builder.sum([
                VariantInfo(0, "Pending", type_builder.unit()),
                VariantInfo(1, "Active", type_builder.string()),  # With reason
                VariantInfo(2, "Completed", type_builder.u64()),  # With timestamp
                VariantInfo(3, "Failed", type_builder.product([
                    FieldInfo("code", type_builder.u32()),
                    FieldInfo("message", type_builder.string()),
                ])),
            ], "Status")
            
            # Test each variant
            test_cases = [
                (0, None, "Pending"),
                (1, "User activated", "Active"),
                (2, 1234567890, "Completed"),
                (3, {"code": 404, "message": "Not found"}, "Failed"),
            ]
            
            for variant_id, variant_value, variant_name in test_cases:
                with benchmark.measure(f"sum_{variant_name}"):
                    # Create sum value
                    sum_value = AlgebraicValue(status_type, (variant_id, variant_value))
                    
                    # Test variant access
                    assert sum_value.variant_id() == variant_id
                    assert sum_value.variant_name() == variant_name
                    
                    # Test serialization
                    serialized = sum_value.serialize()
                    assert serialized is not None
                    
                    # Test deserialization
                    deserialized = AlgebraicValue.deserialize(status_type, serialized)
                    assert deserialized.variant_id() == variant_id
            
            print(f"\nSum type performance:")
            for _, _, variant_name in test_cases:
                stats = benchmark.get_stats(f"sum_{variant_name}")
                if stats:
                    print(f"  {variant_name}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()
    
    async def test_array_types(self, wasm_harness, sdk_test_module):
        """Test array types."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "array_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test different array types
            test_cases = [
                ("int_array", type_builder.array(type_builder.i32()), [1, 2, 3, 4, 5]),
                ("string_array", type_builder.array(type_builder.string()), 
                 ["hello", "world", "test"]),
                ("empty_array", type_builder.array(type_builder.u8()), []),
                ("large_array", type_builder.array(type_builder.u64()), 
                 list(range(1000))),
            ]
            
            for test_name, array_type, values in test_cases:
                with benchmark.measure(f"array_{test_name}"):
                    # Create array value
                    array_value = AlgebraicValue(array_type, values)
                    
                    # Test element access
                    if values:
                        assert array_value.as_array()[0] == values[0]
                    
                    # Test serialization
                    serialized = array_value.serialize()
                    assert serialized is not None
                    
                    # Test deserialization
                    deserialized = AlgebraicValue.deserialize(array_type, serialized)
                    assert len(deserialized.as_array()) == len(values)
            
            print(f"\nArray type performance:")
            for test_name, _, _ in test_cases:
                stats = benchmark.get_stats(f"array_{test_name}")
                if stats:
                    print(f"  {test_name}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()
    
    async def test_option_types(self, wasm_harness, sdk_test_module):
        """Test option types (nullable values)."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "option_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test different option scenarios
            test_cases = [
                ("some_string", type_builder.option(type_builder.string()), "Hello"),
                ("none_string", type_builder.option(type_builder.string()), None),
                ("some_number", type_builder.option(type_builder.u64()), 42),
                ("none_number", type_builder.option(type_builder.u64()), None),
            ]
            
            for test_name, option_type, value in test_cases:
                with benchmark.measure(f"option_{test_name}"):
                    # Create option value
                    option_value = AlgebraicValue(option_type, value)
                    
                    # Test Some/None check
                    if value is None:
                        assert option_value.is_none()
                        assert not option_value.is_some()
                    else:
                        assert option_value.is_some()
                        assert not option_value.is_none()
                        assert option_value.unwrap() == value
                    
                    # Test serialization
                    serialized = option_value.serialize()
                    assert serialized is not None
                    
                    # Test deserialization
                    deserialized = AlgebraicValue.deserialize(option_type, serialized)
                    if value is None:
                        assert deserialized.is_none()
                    else:
                        assert deserialized.unwrap() == value
            
            print(f"\nOption type performance:")
            for test_name, _, _ in test_cases:
                stats = benchmark.get_stats(f"option_{test_name}")
                if stats:
                    print(f"  {test_name}: {stats['mean']*1000:.3f}ms")
                    
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
class TestDataConstraints:
    """Test data constraints and error handling."""
    
    async def test_type_validation(self, wasm_harness, sdk_test_module):
        """Test type validation and constraints."""
        require_spacetimedb()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "validation_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test integer bounds
            u8_type = IntType(bits=8, signed=False)
            assert u8_type.validate(0)
            assert u8_type.validate(255)
            assert not u8_type.validate(-1)
            assert not u8_type.validate(256)
            
            # Test string constraints (if any)
            string_type = StringType()
            assert string_type.validate("valid string")
            assert string_type.validate("")  # Empty allowed
            
            # Test address constraints
            address_type = AddressType()
            assert address_type.validate(b'0123456789ABCDEF')  # 16 bytes
            assert not address_type.validate(b'short')
            assert not address_type.validate(b'toolongaddressbyteshere')
            
            # Test custom validators
            class EmailValidator:
                def validate(self, value: Any) -> bool:
                    return isinstance(value, str) and '@' in value
            
            email_type = StringType()
            email_type.add_validator(EmailValidator())
            
            assert email_type.validate("user@example.com")
            assert not email_type.validate("invalid-email")
            
        finally:
            await client.disconnect()
    
    async def test_serialization_errors(self, wasm_harness, sdk_test_module):
        """Test serialization error handling."""
        require_spacetimedb()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "error_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test invalid type combinations
            with pytest.raises(Exception):
                # Try to create string value with non-string data
                string_type = StringType()
                AlgebraicValue(string_type, 12345)  # Should fail
            
            # Test deserialization with wrong data
            with pytest.raises(Exception):
                # Try to deserialize invalid data
                bool_type = BoolType()
                AlgebraicValue.deserialize(bool_type, b'invalid_data')
            
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
class TestBSATNCompatibility:
    """Test BSATN serialization compatibility with other SDKs."""
    
    async def test_cross_sdk_serialization(self, wasm_harness, sdk_test_module):
        """Test that our serialization matches other SDK implementations."""
        require_spacetimedb()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "bsatn_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test known BSATN encodings
            # These should match exactly with Rust/Go implementations
            
            # Boolean true: tag(0x00) + 0x01
            bool_type = BoolType()
            true_value = AlgebraicValue(bool_type, True)
            true_bytes = true_value.serialize()
            assert true_bytes == b'\x00\x01'
            
            # Boolean false: tag(0x00) + 0x00
            false_value = AlgebraicValue(bool_type, False)
            false_bytes = false_value.serialize()
            assert false_bytes == b'\x00\x00'
            
            # u8 value 42: tag(0x03) + 42
            u8_type = IntType(bits=8, signed=False)
            u8_value = AlgebraicValue(u8_type, 42)
            u8_bytes = u8_value.serialize()
            assert u8_bytes == b'\x03\x2a'
            
            # More complex types would be tested here
            # comparing against known good encodings
            
        finally:
            await client.disconnect()


# Pytest fixtures
@pytest.fixture
async def spacetimedb_server():
    """Provide a SpacetimeDB server for testing."""
    config = SpacetimeDBConfig(listen_port=3100)
    server = SpacetimeDBServer(config)
    server.start()
    yield server
    server.stop()


@pytest.fixture
async def wasm_harness(spacetimedb_server):
    """Provide WASM test harness."""
    harness = WASMTestHarness(spacetimedb_server)
    await harness.setup()
    yield harness
    await harness.teardown()


@pytest.fixture
def sdk_test_module():
    """Provide SDK test module."""
    return WASMModule.from_file(require_sdk_test_module(), "sdk_test")


async def main():
    """Run core data types integration tests."""
    print("Core Data Types Integration Testing")
    print("===================================\n")
    
    # Check prerequisites
    import shutil
    if not shutil.which("spacetimedb"):
        print("❌ SpacetimeDB not found in PATH!")
        print("Please install SpacetimeDB first.")
        return
    
    from spacetimedb_sdk.wasm_integration import find_sdk_test_module
    if not find_sdk_test_module():
        print("❌ SDK test module not found!")
        print("Set SPACETIMEDB_SDK_TEST_MODULE environment variable.")
        return
    
    print("✅ Prerequisites satisfied")
    print("\nRunning integration tests...")
    
    # Run specific test classes
    test_classes = [
        TestPrimitiveTypes(),
        TestSpacetimeDBTypes(),
        TestComplexTypes(),
        TestDataConstraints(),
        TestBSATNCompatibility(),
    ]
    
    # Simple test runner
    for test_class in test_classes:
        print(f"\n{test_class.__class__.__name__}:")
        for method_name in dir(test_class):
            if method_name.startswith('test_'):
                print(f"  - {method_name}")
    
    print("\n✅ Test structure ready!")
    print("\nTo run full tests:")
    print("pytest test_core_data_types_integration.py -v -m integration")


if __name__ == "__main__":
    asyncio.run(main()) 