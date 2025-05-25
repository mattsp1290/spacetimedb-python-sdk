"""
Test Algebraic Types for SpacetimeDB Python SDK.

Tests the advanced algebraic type system:
- Type definitions and validation
- Type-safe value handling
- Serialization and deserialization
- Custom validators and converters
- Complex type structures
- JSON conversion
- Type inference
"""

import unittest
import json
from datetime import datetime
from typing import Any

from spacetimedb_sdk.algebraic_type import (
    TypeKind, TypeBuilder, TypeRegistry,
    AlgebraicType, BoolType, IntType, FloatType, StringType, BytesType,
    ProductType, SumType, ArrayType, MapType, OptionType,
    IdentityType, AddressType, TimestampType,
    FieldInfo, VariantInfo,
    TypeValidator, TypeConverter,
    type_builder, validate_value, serialize_value, deserialize_value
)
from spacetimedb_sdk.algebraic_value import (
    AlgebraicValue,
    bool_value, u8_value, u32_value, i32_value,
    f32_value, f64_value, string_value, bytes_value
)


class TestPrimitiveTypes(unittest.TestCase):
    """Test primitive algebraic types."""
    
    def test_bool_type(self):
        """Test boolean type."""
        bool_type = BoolType()
        
        self.assertTrue(bool_type.validate(True))
        self.assertTrue(bool_type.validate(False))
        self.assertFalse(bool_type.validate(1))
        self.assertFalse(bool_type.validate("true"))
        
        # Test serialization
        from io import BytesIO
        from spacetimedb_sdk.bsatn import BsatnWriter, BsatnReader
        
        buffer = BytesIO()
        writer = BsatnWriter(buffer)
        bool_type.serialize(True, writer)
        
        # Get bytes from buffer
        data = buffer.getvalue()
        reader = BsatnReader(data)
        value = bool_type.deserialize(reader)
        self.assertEqual(value, True)
    
    def test_integer_types(self):
        """Test integer types with bounds checking."""
        # Test u8
        u8 = IntType(8, False)
        self.assertTrue(u8.validate(0))
        self.assertTrue(u8.validate(255))
        self.assertFalse(u8.validate(-1))
        self.assertFalse(u8.validate(256))
        
        # Test i8
        i8 = IntType(8, True)
        self.assertTrue(i8.validate(-128))
        self.assertTrue(i8.validate(127))
        self.assertFalse(i8.validate(-129))
        self.assertFalse(i8.validate(128))
        
        # Test u32
        u32 = IntType(32, False)
        self.assertTrue(u32.validate(0))
        self.assertTrue(u32.validate(4294967295))
        self.assertFalse(u32.validate(-1))
        self.assertFalse(u32.validate(4294967296))
    
    def test_float_types(self):
        """Test floating point types."""
        f32 = FloatType(32)
        f64 = FloatType(64)
        
        self.assertTrue(f32.validate(3.14))
        self.assertTrue(f32.validate(0))
        self.assertTrue(f32.validate(-1.5))
        self.assertFalse(f32.validate("3.14"))
        
        self.assertEqual(f32.python_type(), float)
        self.assertEqual(f64.python_type(), float)
    
    def test_string_type(self):
        """Test string type."""
        string_type = StringType()
        
        self.assertTrue(string_type.validate("hello"))
        self.assertTrue(string_type.validate(""))
        self.assertTrue(string_type.validate("Unicode: 日本語"))
        self.assertFalse(string_type.validate(123))
        self.assertFalse(string_type.validate(b"bytes"))
    
    def test_bytes_type(self):
        """Test bytes type."""
        bytes_type = BytesType()
        
        self.assertTrue(bytes_type.validate(b"hello"))
        self.assertTrue(bytes_type.validate(b""))
        self.assertTrue(bytes_type.validate(bytearray(b"data")))
        self.assertFalse(bytes_type.validate("string"))
        self.assertFalse(bytes_type.validate(123))


class TestComplexTypes(unittest.TestCase):
    """Test complex algebraic types."""
    
    def test_product_type(self):
        """Test product type (struct)."""
        # Define a User struct
        user_type = ProductType([
            FieldInfo("id", IntType(32, False)),
            FieldInfo("name", StringType()),
            FieldInfo("age", IntType(8, False), optional=True, default=0)
        ], "User")
        
        # Test validation with dict
        valid_user = {"id": 123, "name": "Alice", "age": 25}
        self.assertTrue(user_type.validate(valid_user))
        
        # Test with missing optional field
        valid_user2 = {"id": 456, "name": "Bob"}
        self.assertTrue(user_type.validate(valid_user2))
        
        # Test with missing required field
        invalid_user = {"id": 789}
        self.assertFalse(user_type.validate(invalid_user))
        
        # Test with wrong type
        invalid_user2 = {"id": "not-a-number", "name": "Charlie"}
        self.assertFalse(user_type.validate(invalid_user2))
    
    def test_sum_type(self):
        """Test sum type (union/enum)."""
        # Define a Result<T, E> union
        result_type = SumType([
            VariantInfo("Ok", 0, StringType()),
            VariantInfo("Err", 1, StringType())
        ], "Result")
        
        # Test valid variants
        ok_result = {"Ok": "Success!"}
        self.assertTrue(result_type.validate(ok_result))
        
        err_result = {"Err": "Something went wrong"}
        self.assertTrue(result_type.validate(err_result))
        
        # Test invalid variants
        invalid_result = {"Unknown": "value"}
        self.assertFalse(result_type.validate(invalid_result))
        
        # Test multiple variants (invalid)
        invalid_result2 = {"Ok": "value", "Err": "error"}
        self.assertFalse(result_type.validate(invalid_result2))
    
    def test_array_type(self):
        """Test fixed-size array type."""
        # Define a [u8; 4] array
        array_type = ArrayType(IntType(8, False), 4)
        
        valid_array = [1, 2, 3, 4]
        self.assertTrue(array_type.validate(valid_array))
        
        # Wrong size
        invalid_array = [1, 2, 3]
        self.assertFalse(array_type.validate(invalid_array))
        
        # Wrong element type
        invalid_array2 = ["a", "b", "c", "d"]
        self.assertFalse(array_type.validate(invalid_array2))
    
    def test_map_type(self):
        """Test map type."""
        # Define Map<string, u32>
        map_type = MapType(StringType(), IntType(32, False))
        
        valid_map = {"alice": 100, "bob": 200}
        self.assertTrue(map_type.validate(valid_map))
        
        # Invalid key type
        invalid_map = {123: 100}
        self.assertFalse(map_type.validate(invalid_map))
        
        # Invalid value type
        invalid_map2 = {"alice": "not-a-number"}
        self.assertFalse(map_type.validate(invalid_map2))
    
    def test_option_type(self):
        """Test optional type."""
        # Define Option<string>
        option_type = OptionType(StringType())
        
        self.assertTrue(option_type.validate("hello"))
        self.assertTrue(option_type.validate(None))
        self.assertFalse(option_type.validate(123))
        
        # Test serialization
        data_some = serialize_value(option_type, "hello")
        data_none = serialize_value(option_type, None)
        
        value_some = deserialize_value(option_type, data_some)
        value_none = deserialize_value(option_type, data_none)
        
        self.assertEqual(value_some, "hello")
        self.assertIsNone(value_none)


class TestSpacetimeDBTypes(unittest.TestCase):
    """Test SpacetimeDB-specific types."""
    
    def test_identity_type(self):
        """Test Identity type."""
        identity_type = IdentityType()
        
        # Valid 32-byte identity
        valid_identity = b'\x00' * 32
        self.assertTrue(identity_type.validate(valid_identity))
        
        # Invalid size
        invalid_identity = b'\x00' * 31
        self.assertFalse(identity_type.validate(invalid_identity))
    
    def test_address_type(self):
        """Test Address type."""
        address_type = AddressType()
        
        # Valid 16-byte address
        valid_address = b'\xFF' * 16
        self.assertTrue(address_type.validate(valid_address))
        
        # Invalid size
        invalid_address = b'\xFF' * 15
        self.assertFalse(address_type.validate(invalid_address))
    
    def test_timestamp_type(self):
        """Test Timestamp type."""
        timestamp_type = TimestampType()
        
        # Test with microseconds
        self.assertTrue(timestamp_type.validate(1234567890123456))
        
        # Test with datetime
        now = datetime.now()
        self.assertTrue(timestamp_type.validate(now))
        
        # Test serialization
        data = serialize_value(timestamp_type, now)
        micros = deserialize_value(timestamp_type, data)
        self.assertIsInstance(micros, int)


class TestAlgebraicValue(unittest.TestCase):
    """Test AlgebraicValue wrapper."""
    
    def test_primitive_values(self):
        """Test primitive type values."""
        # Boolean
        bool_val = bool_value(True)
        self.assertEqual(bool_val.as_bool(), True)
        self.assertEqual(bool_val.kind, TypeKind.BOOL)
        
        # Integer
        u32_val = u32_value(42)
        self.assertEqual(u32_val.as_int(), 42)
        
        # Float
        f64_val = f64_value(3.14159)
        self.assertAlmostEqual(f64_val.as_float(), 3.14159)
        
        # String
        str_val = string_value("hello")
        self.assertEqual(str_val.as_string(), "hello")
        
        # Bytes
        bytes_val = bytes_value(b"data")
        self.assertEqual(bytes_val.as_bytes(), b"data")
    
    def test_type_validation(self):
        """Test type validation in AlgebraicValue."""
        # Valid value
        u8_val = u8_value(100)
        self.assertEqual(u8_val.as_int(), 100)
        
        # Invalid value should raise
        with self.assertRaises(TypeError):
            u8_value(256)  # Out of range
        
        with self.assertRaises(TypeError):
            u8_value("not a number")
    
    def test_complex_value(self):
        """Test complex type values."""
        # Create a product type value
        user_type = ProductType([
            FieldInfo("id", IntType(32, False)),
            FieldInfo("name", StringType())
        ])
        
        user_data = {"id": 123, "name": "Alice"}
        user_val = AlgebraicValue(user_type, user_data)
        
        # Access fields
        id_val = user_val.get_field("id")
        self.assertEqual(id_val.as_int(), 123)
        
        name_val = user_val.get_field("name")
        self.assertEqual(name_val.as_string(), "Alice")
        
        # Test non-existent field
        with self.assertRaises(KeyError):
            user_val.get_field("email")
    
    def test_json_conversion(self):
        """Test JSON conversion."""
        # Create a complex value
        user_type = ProductType([
            FieldInfo("id", IntType(32, False)),
            FieldInfo("name", StringType()),
            FieldInfo("active", BoolType())
        ])
        
        user_data = {"id": 456, "name": "Bob", "active": True}
        user_val = AlgebraicValue(user_type, user_data)
        
        # Convert to JSON
        json_str = user_val.to_json()
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed["id"], 456)
        self.assertEqual(parsed["name"], "Bob")
        self.assertEqual(parsed["active"], True)
        
        # Convert back from JSON
        user_val2 = AlgebraicValue.from_json(user_type, json_str)
        self.assertEqual(user_val2.get_field("id").as_int(), 456)
    
    def test_serialization(self):
        """Test BSATN serialization."""
        # Create a value
        str_val = string_value("Hello, SpacetimeDB!")
        
        # Serialize
        data = str_val.serialize()
        self.assertIsInstance(data, bytes)
        
        # Deserialize
        str_val2 = AlgebraicValue.deserialize(StringType(), data)
        self.assertEqual(str_val2.as_string(), "Hello, SpacetimeDB!")


class TestTypeBuilder(unittest.TestCase):
    """Test type builder fluent API."""
    
    def test_type_builder(self):
        """Test building types with fluent API."""
        # Build primitive types
        bool_t = type_builder.bool()
        self.assertIsInstance(bool_t, BoolType)
        
        u32_t = type_builder.u32()
        self.assertIsInstance(u32_t, IntType)
        self.assertEqual(u32_t.bits, 32)
        self.assertFalse(u32_t.signed)
        
        # Build complex types
        user_t = type_builder.product([
            FieldInfo("id", type_builder.u64()),
            FieldInfo("name", type_builder.string()),
            FieldInfo("email", type_builder.option(type_builder.string()))
        ], "User")
        
        self.assertIsInstance(user_t, ProductType)
        self.assertEqual(len(user_t.fields), 3)
    
    def test_type_registry(self):
        """Test type registry for recursive types."""
        registry = TypeRegistry()
        
        # Register a custom type
        user_type = type_builder.product([
            FieldInfo("id", type_builder.u32()),
            FieldInfo("name", type_builder.string())
        ])
        registry.register("User", user_type)
        
        # Create a reference to it
        user_ref = registry.ref("User")
        self.assertEqual(user_ref.ref_name, "User")
        
        # Resolve the reference
        resolved = user_ref.resolve()
        self.assertIs(resolved, user_type)


class TestCustomValidators(unittest.TestCase):
    """Test custom validators and converters."""
    
    def test_custom_validator(self):
        """Test adding custom validators."""
        # Create an email validator
        class EmailValidator:
            def validate(self, value: Any) -> bool:
                return isinstance(value, str) and "@" in value
        
        # Create string type with email validation
        email_type = StringType()
        email_type.add_validator(EmailValidator())
        
        # Test validation
        self.assertTrue(email_type.validate_with_custom("user@example.com"))
        self.assertFalse(email_type.validate_with_custom("not-an-email"))
    
    def test_custom_converter(self):
        """Test adding custom converters."""
        # Create a converter that uppercases strings
        class UppercaseConverter:
            def convert(self, value: Any) -> Any:
                if isinstance(value, str):
                    return value.upper()
                return value
        
        # Create string type with converter
        upper_string = StringType()
        upper_string.add_converter(UppercaseConverter())
        
        # Test conversion
        converted = upper_string.convert("hello")
        self.assertEqual(converted, "HELLO")
        
        # Use in AlgebraicValue
        val = AlgebraicValue(upper_string, "world")
        self.assertEqual(val.as_string(), "WORLD")


class TestNestedTypes(unittest.TestCase):
    """Test deeply nested type structures."""
    
    def test_nested_products(self):
        """Test nested product types."""
        # Define Address type
        address_type = type_builder.product([
            FieldInfo("street", type_builder.string()),
            FieldInfo("city", type_builder.string()),
            FieldInfo("zip", type_builder.string())
        ], "Address")
        
        # Define User type with Address
        user_type = type_builder.product([
            FieldInfo("id", type_builder.u32()),
            FieldInfo("name", type_builder.string()),
            FieldInfo("address", address_type)
        ], "User")
        
        # Create test data
        user_data = {
            "id": 123,
            "name": "Alice",
            "address": {
                "street": "123 Main St",
                "city": "Springfield",
                "zip": "12345"
            }
        }
        
        # Validate and create value
        self.assertTrue(user_type.validate(user_data))
        user_val = AlgebraicValue(user_type, user_data)
        
        # Access nested fields
        address_val = user_val.get_field("address")
        city_val = address_val.get_field("city")
        self.assertEqual(city_val.as_string(), "Springfield")
    
    def test_array_of_options(self):
        """Test array of optional values."""
        # Define [Option<string>; 3]
        array_type = type_builder.array(
            type_builder.option(type_builder.string()),
            3
        )
        
        # Test data
        data = ["hello", None, "world"]
        self.assertTrue(array_type.validate(data))
        
        # Create value
        array_val = AlgebraicValue(array_type, data)
        
        # Access elements
        elem0 = array_val.get_element(0)
        self.assertEqual(elem0.get_some().as_string(), "hello")
        
        elem1 = array_val.get_element(1)
        self.assertIsNone(elem1.get_some())
        
        elem2 = array_val.get_element(2)
        self.assertEqual(elem2.get_some().as_string(), "world")


if __name__ == '__main__':
    unittest.main() 