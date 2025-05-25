"""
Example: Core Data Types in SpacetimeDB Python SDK

Demonstrates all primitive and complex data types supported by SpacetimeDB:
- Primitive types: bool, integers, floats, strings, bytes
- SpacetimeDB types: Identity, Address, Timestamp
- Complex types: structs (products), enums (sums), arrays, options
"""

import time
from datetime import datetime

from spacetimedb_sdk import (
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
    OptionType,
    IdentityType,
    AddressType,
    TimestampType,
    FieldInfo,
    VariantInfo,
    type_builder,
)


class CoreDataTypesExample:
    """Examples demonstrating SpacetimeDB core data types."""
    
    def example_1_primitive_types(self):
        """Example 1: Primitive data types."""
        print("\n=== Example 1: Primitive Types ===")
        
        # Boolean
        bool_type = BoolType()
        true_val = AlgebraicValue(bool_type, True)
        false_val = AlgebraicValue(bool_type, False)
        print(f"Boolean: {true_val.value}, {false_val.value}")
        
        # Integers
        u8 = AlgebraicValue(type_builder.u8(), 255)
        i32 = AlgebraicValue(type_builder.i32(), -12345)
        u64 = AlgebraicValue(type_builder.u64(), 18446744073709551615)
        print(f"Integers: u8={u8.value}, i32={i32.value}, u64={u64.value}")
        
        # Floats
        f32 = AlgebraicValue(type_builder.f32(), 3.14159)
        f64 = AlgebraicValue(type_builder.f64(), 2.718281828459045)
        print(f"Floats: f32={f32.value}, f64={f64.value}")
        
        # String
        string_val = AlgebraicValue(type_builder.string(), "Hello, SpacetimeDB! 🚀")
        print(f"String: {string_val.value}")
        
        # Bytes
        bytes_val = AlgebraicValue(type_builder.bytes(), b"\x00\x01\x02\x03")
        print(f"Bytes: {bytes_val.value.hex()}")
    
    def example_2_spacetimedb_types(self):
        """Example 2: SpacetimeDB-specific types."""
        print("\n=== Example 2: SpacetimeDB Types ===")
        
        # Identity (32 bytes)
        identity_type = IdentityType()
        identity_bytes = b'01234567890123456789012345678901'  # 32 bytes
        identity = AlgebraicValue(identity_type, identity_bytes)
        print(f"Identity: {identity.value.hex()[:16]}...")
        
        # Address (16 bytes)
        address_type = AddressType()
        address_bytes = b'0123456789ABCDEF'  # 16 bytes
        address = AlgebraicValue(address_type, address_bytes)
        print(f"Address: {address.value.hex()}")
        
        # Timestamp (microseconds since Unix epoch)
        timestamp_type = TimestampType()
        now_micros = int(time.time() * 1_000_000)
        timestamp = AlgebraicValue(timestamp_type, now_micros)
        
        # Convert to datetime
        dt = datetime.fromtimestamp(timestamp.value / 1_000_000)
        print(f"Timestamp: {timestamp.value} ({dt.isoformat()})")
    
    def example_3_struct_types(self):
        """Example 3: Struct types (products)."""
        print("\n=== Example 3: Struct Types ===")
        
        # Define a User struct
        user_type = type_builder.product([
            FieldInfo("id", type_builder.u64()),
            FieldInfo("username", type_builder.string()),
            FieldInfo("email", type_builder.string()),
            FieldInfo("created_at", type_builder.timestamp()),
            FieldInfo("is_active", type_builder.bool()),
        ], "User")
        
        # Create a user instance
        user_data = {
            "id": 12345,
            "username": "alice",
            "email": "alice@example.com",
            "created_at": int(time.time() * 1_000_000),
            "is_active": True
        }
        user = AlgebraicValue(user_type, user_data)
        
        # Access fields
        print(f"User ID: {user.get_field('id').value}")
        print(f"Username: {user.get_field('username').value}")
        print(f"Email: {user.get_field('email').value}")
        print(f"Active: {user.get_field('is_active').value}")
        
        # Serialize and deserialize
        serialized = user.serialize()
        print(f"Serialized size: {len(serialized)} bytes")
        
        deserialized = AlgebraicValue.deserialize(user_type, serialized)
        print(f"Deserialized username: {deserialized.get_field('username').value}")
    
    def example_4_enum_types(self):
        """Example 4: Enum types (sums)."""
        print("\n=== Example 4: Enum Types ===")
        
        # Define a Status enum
        status_type = type_builder.sum([
            VariantInfo("Pending", 0),  # No associated data
            VariantInfo("Processing", 1, type_builder.string()),  # With message
            VariantInfo("Completed", 2, type_builder.timestamp()),  # With timestamp
            VariantInfo("Failed", 3, type_builder.product([
                FieldInfo("code", type_builder.u32()),
                FieldInfo("message", type_builder.string()),
            ], "ErrorInfo")),
        ], "Status")
        
        # Create different status values
        pending = AlgebraicValue(status_type, {"Pending": None})
        processing = AlgebraicValue(status_type, {"Processing": "Validating data..."})
        completed = AlgebraicValue(status_type, {"Completed": int(time.time() * 1_000_000)})
        failed = AlgebraicValue(status_type, {"Failed": {"code": 404, "message": "Not found"}})
        
        # Check variants
        for status, name in [(pending, "Pending"), (processing, "Processing"), 
                           (completed, "Completed"), (failed, "Failed")]:
            variant_name, variant_value = status.get_variant()
            print(f"{name}: variant={variant_name}")
    
    def example_5_array_types(self):
        """Example 5: Array types."""
        print("\n=== Example 5: Array Types ===")
        
        # Array of integers
        int_array_type = type_builder.array(type_builder.i32(), 5)  # Fixed size array
        numbers = AlgebraicValue(int_array_type, [1, 2, 3, 4, 5])
        print(f"Integer array: {numbers.as_array()}")
        
        # Array of strings
        string_array_type = type_builder.array(type_builder.string(), 4)  # Fixed size
        words = AlgebraicValue(string_array_type, ["hello", "world", "from", "spacetime"])
        print(f"String array: {words.as_array()}")
        
        # Array of structs
        point_type = type_builder.product([
            FieldInfo("x", type_builder.f32()),
            FieldInfo("y", type_builder.f32()),
        ], "Point")
        
        point_array_type = type_builder.array(point_type, 3)  # Fixed size
        points = AlgebraicValue(point_array_type, [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
            {"x": 2.0, "y": 4.0},
        ])
        print(f"Points: {len(points.as_array())} items")
    
    def example_6_option_types(self):
        """Example 6: Option types (nullable values)."""
        print("\n=== Example 6: Option Types ===")
        
        # Optional string
        optional_string_type = type_builder.option(type_builder.string())
        
        # Some value
        some_name = AlgebraicValue(optional_string_type, "Alice")
        print(f"Some: value={some_name.value}")
        
        # None value
        no_name = AlgebraicValue(optional_string_type, None)
        print(f"None: value={no_name.value}")
        
        # Optional number with default
        optional_age_type = type_builder.option(type_builder.u8())
        age = AlgebraicValue(optional_age_type, None)
        age_value = age.value if age.value is not None else 0
        print(f"Age with default: {age_value}")
    
    def example_7_nested_types(self):
        """Example 7: Complex nested types."""
        print("\n=== Example 7: Nested Types ===")
        
        # Define a Message type with nested structures
        message_type = type_builder.product([
            FieldInfo("id", type_builder.u64()),
            FieldInfo("sender", type_builder.identity()),
            FieldInfo("content", type_builder.sum([
                VariantInfo("Text", 0, type_builder.string()),
                VariantInfo("Image", 1, type_builder.product([
                    FieldInfo("url", type_builder.string()),
                    FieldInfo("size", type_builder.u32()),
                ])),
                VariantInfo("File", 2, type_builder.product([
                    FieldInfo("name", type_builder.string()),
                    FieldInfo("data", type_builder.bytes()),
                ])),
            ], "MessageContent")),
            FieldInfo("recipients", type_builder.array(type_builder.identity(), 2)),  # Fixed size
            FieldInfo("reply_to", type_builder.option(type_builder.u64())),
            FieldInfo("timestamp", type_builder.timestamp()),
        ], "Message")
        
        # Create a text message
        message_data = {
            "id": 98765,
            "sender": b'sender_identity_bytes_here_32bit',
            "content": {"Text": "Hello everyone!"},  # Sum type as dict
            "recipients": [
                b'recipient1_identity_bytes_32bits',
                b'recipient2_identity_bytes_32bits',
            ],
            "reply_to": 12345,  # Replying to message 12345
            "timestamp": int(time.time() * 1_000_000),
        }
        
        message = AlgebraicValue(message_type, message_data)
        print(f"Message ID: {message.get_field('id').value}")
        
        reply_to_field = message.get_field('reply_to')
        reply_value = reply_to_field.get_some()
        print(f"Has reply: {reply_value is not None}")
        print(f"Recipients: {len(message.get_field('recipients').as_array())}")
    
    def example_8_serialization(self):
        """Example 8: Serialization and deserialization."""
        print("\n=== Example 8: Serialization ===")
        
        # Create a complex type
        person_type = type_builder.product([
            FieldInfo("name", type_builder.string()),
            FieldInfo("age", type_builder.u8()),
            FieldInfo("hobbies", type_builder.array(type_builder.string(), 3)),  # Fixed size
        ], "Person")
        
        person_data = {
            "name": "Bob",
            "age": 30,
            "hobbies": ["coding", "gaming", "reading"]
        }
        person = AlgebraicValue(person_type, person_data)
        
        # Serialize to BSATN
        bsatn_data = person.serialize()
        print(f"BSATN size: {len(bsatn_data)} bytes")
        print(f"BSATN hex: {bsatn_data.hex()[:32]}...")
        
        # Deserialize back
        restored = AlgebraicValue.deserialize(person_type, bsatn_data)
        print(f"Restored name: {restored.get_field('name').value}")
        print(f"Restored hobbies: {restored.get_field('hobbies').as_array()}")
        
        # JSON conversion
        json_data = person.to_json()
        print(f"JSON: {json_data}")
        
        from_json = AlgebraicValue.from_json(person_type, json_data)
        print(f"From JSON name: {from_json.get_field('name').value}")
    
    def example_9_type_validation(self):
        """Example 9: Type validation and constraints."""
        print("\n=== Example 9: Type Validation ===")
        
        # Integer bounds validation
        u8_type = IntType(bits=8, signed=False)
        print(f"u8 validate 100: {u8_type.validate(100)}")
        print(f"u8 validate 300: {u8_type.validate(300)}")  # Out of range
        print(f"u8 validate -1: {u8_type.validate(-1)}")   # Negative for unsigned
        
        # Custom validator
        class EmailValidator:
            def validate(self, value):
                return isinstance(value, str) and '@' in value and '.' in value
        
        email_type = StringType()
        email_type.add_validator(EmailValidator())
        
        print(f"Email validate 'user@example.com': {email_type.validate('user@example.com')}")
        print(f"Email validate 'invalid': {email_type.validate('invalid')}")
        
        # Address validation (must be 16 bytes)
        address_type = AddressType()
        print(f"Address validate 16 bytes: {address_type.validate(b'0123456789ABCDEF')}")
        print(f"Address validate 10 bytes: {address_type.validate(b'0123456789')}")
    
    def example_10_performance_considerations(self):
        """Example 10: Performance and best practices."""
        print("\n=== Example 10: Performance Tips ===")
        
        import time
        
        # Measure serialization performance
        large_array_type = type_builder.array(type_builder.u64(), 10000)  # Fixed size
        large_data = list(range(10000))
        large_array = AlgebraicValue(large_array_type, large_data)
        
        start = time.perf_counter()
        serialized = large_array.serialize()
        serialize_time = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        deserialized = AlgebraicValue.deserialize(large_array_type, serialized)
        deserialize_time = (time.perf_counter() - start) * 1000
        
        print(f"Array with 10K elements:")
        print(f"  Serialization: {serialize_time:.2f}ms")
        print(f"  Deserialization: {deserialize_time:.2f}ms")
        print(f"  Serialized size: {len(serialized):,} bytes")
        
        # Type caching
        print("\nTip: Reuse type definitions for better performance")
        print("BAD:  for item in items: AlgebraicValue(type_builder.u64(), item)")
        print("GOOD: u64_type = type_builder.u64()")
        print("      for item in items: AlgebraicValue(u64_type, item)")


def main():
    """Run all core data types examples."""
    example = CoreDataTypesExample()
    
    print("SpacetimeDB Core Data Types Examples")
    print("====================================")
    
    example.example_1_primitive_types()
    example.example_2_spacetimedb_types()
    example.example_3_struct_types()
    example.example_4_enum_types()
    example.example_5_array_types()
    example.example_6_option_types()
    example.example_7_nested_types()
    example.example_8_serialization()
    example.example_9_type_validation()
    example.example_10_performance_considerations()
    
    print("\n✅ Core data types examples complete!")
    print("\nKey Concepts:")
    print("- Primitive types: bool, integers (u8-u64, i8-i64), floats (f32, f64), string, bytes")
    print("- SpacetimeDB types: Identity (32 bytes), Address (16 bytes), Timestamp (microseconds)")
    print("- Complex types: Product (struct), Sum (enum), Array, Option (nullable)")
    print("- Serialization: BSATN binary format, JSON conversion")
    print("- Type validation: Built-in constraints, custom validators")
    print("- Performance: Type reuse, efficient serialization")


if __name__ == "__main__":
    main() 