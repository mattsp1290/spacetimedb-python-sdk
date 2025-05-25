"""
Example: Advanced Algebraic Types for SpacetimeDB Python SDK

Demonstrates the advanced type system features:
- Type definitions and validation
- Type-safe value handling
- Custom validators and converters
- Complex type structures
- Serialization and JSON conversion
- Type inference and checking
"""

from typing import Any, Optional
from datetime import datetime
import json

from spacetimedb_sdk.algebraic_type import (
    type_builder, TypeRegistry, FieldInfo, VariantInfo,
    TypeValidator, TypeConverter, serialize_value, deserialize_value
)
from spacetimedb_sdk.algebraic_value import (
    AlgebraicValue, bool_value, u32_value, i32_value,
    string_value, bytes_value
)


class AlgebraicTypesExample:
    """Examples demonstrating algebraic type system capabilities."""
    
    def __init__(self):
        self.registry = TypeRegistry()
    
    def example_1_primitive_types(self):
        """Example 1: Working with primitive types."""
        print("\n=== Example 1: Primitive Types ===")
        
        # Create typed values
        age = u32_value(25)
        name = string_value("Alice")
        active = bool_value(True)
        score = i32_value(-100)
        
        print(f"Name: {name.as_string()}")
        print(f"Age: {age.as_int()}")
        print(f"Active: {active.as_bool()}")
        print(f"Score: {score.as_int()}")
        
        # Type checking
        try:
            # This will fail - age must be non-negative u32
            invalid_age = u32_value(-5)
        except TypeError as e:
            print(f"Type error: {e}")
        
        # Serialization
        name_bytes = name.serialize()
        print(f"Serialized name: {name_bytes.hex()}")
        
        # Deserialization
        name_restored = AlgebraicValue.deserialize(
            type_builder.string(),
            name_bytes
        )
        print(f"Restored: {name_restored.as_string()}")
    
    def example_2_product_types(self):
        """Example 2: Product types (structs)."""
        print("\n=== Example 2: Product Types (Structs) ===")
        
        # Define a User struct
        user_type = type_builder.product([
            FieldInfo("id", type_builder.u64()),
            FieldInfo("username", type_builder.string()),
            FieldInfo("email", type_builder.string()),
            FieldInfo("age", type_builder.u8()),
            FieldInfo("verified", type_builder.bool(), default=False)
        ], "User")
        
        # Create a user
        user_data = {
            "id": 12345,
            "username": "alice_wonder",
            "email": "alice@example.com",
            "age": 25,
            "verified": True
        }
        
        user = AlgebraicValue(user_type, user_data)
        
        # Access fields
        print(f"User ID: {user.get_field('id').as_int()}")
        print(f"Username: {user.get_field('username').as_string()}")
        print(f"Verified: {user.get_field('verified').as_bool()}")
        
        # Convert to JSON
        user_json = user.to_json()
        print(f"JSON: {user_json}")
        
        # Register the type for reuse
        self.registry.register("User", user_type)
    
    def example_3_sum_types(self):
        """Example 3: Sum types (unions/enums)."""
        print("\n=== Example 3: Sum Types (Unions) ===")
        
        # Define a Result<T, E> type
        result_type = type_builder.sum([
            VariantInfo("Ok", 0, type_builder.string()),
            VariantInfo("Err", 1, type_builder.string())
        ], "Result")
        
        # Success case
        success = AlgebraicValue(result_type, {"Ok": "Operation completed!"})
        variant_name, variant_value = success.get_variant()
        print(f"Result: {variant_name}")
        if variant_value:
            print(f"Value: {variant_value.as_string()}")
        
        # Error case
        error = AlgebraicValue(result_type, {"Err": "File not found"})
        variant_name, variant_value = error.get_variant()
        print(f"Result: {variant_name}")
        if variant_value:
            print(f"Error: {variant_value.as_string()}")
        
        # Define an enum-like type
        status_type = type_builder.sum([
            VariantInfo("Pending", 0),
            VariantInfo("Processing", 1),
            VariantInfo("Completed", 2),
            VariantInfo("Failed", 3)
        ], "Status")
        
        status = AlgebraicValue(status_type, {"Processing": None})
        print(f"Status: {status.get_variant()[0]}")
    
    def example_4_complex_types(self):
        """Example 4: Complex nested types."""
        print("\n=== Example 4: Complex Types ===")
        
        # Define Address type
        address_type = type_builder.product([
            FieldInfo("street", type_builder.string()),
            FieldInfo("city", type_builder.string()),
            FieldInfo("state", type_builder.string()),
            FieldInfo("zip", type_builder.string())
        ], "Address")
        
        # Define Contact type with optional fields
        contact_type = type_builder.product([
            FieldInfo("name", type_builder.string()),
            FieldInfo("email", type_builder.option(type_builder.string())),
            FieldInfo("phone", type_builder.option(type_builder.string())),
            FieldInfo("address", type_builder.option(address_type))
        ], "Contact")
        
        # Create a contact with full information
        contact_data = {
            "name": "Bob Smith",
            "email": "bob@example.com",
            "phone": "+1-555-0123",
            "address": {
                "street": "123 Main St",
                "city": "Springfield",
                "state": "IL",
                "zip": "62701"
            }
        }
        
        contact = AlgebraicValue(contact_type, contact_data)
        
        # Access nested optional field
        email_opt = contact.get_field("email")
        if email_val := email_opt.get_some():
            print(f"Email: {email_val.as_string()}")
        
        address_opt = contact.get_field("address")
        if address_val := address_opt.get_some():
            city = address_val.get_field("city")
            print(f"City: {city.as_string()}")
        
        # Create a contact with minimal information
        minimal_contact = AlgebraicValue(contact_type, {
            "name": "Anonymous",
            "email": None,
            "phone": None,
            "address": None
        })
        
        print(f"Minimal contact: {minimal_contact.get_field('name').as_string()}")
    
    def example_5_collections(self):
        """Example 5: Collection types (arrays and maps)."""
        print("\n=== Example 5: Collections ===")
        
        # Fixed-size array
        vec3_type = type_builder.array(type_builder.f32(), 3)
        position = AlgebraicValue(vec3_type, [1.0, 2.5, -3.7])
        
        print("3D Position:")
        for i in range(3):
            coord = position.get_element(i)
            print(f"  [{i}] = {coord.as_float()}")
        
        # Map type
        scores_type = type_builder.map(
            type_builder.string(),
            type_builder.u32()
        )
        
        scores_data = {
            "Alice": 1000,
            "Bob": 850,
            "Charlie": 1200
        }
        
        scores = AlgebraicValue(scores_type, scores_data)
        
        print("\nHigh Scores:")
        for name in ["Alice", "Bob", "Charlie"]:
            score = scores.get_entry(name)
            print(f"  {name}: {score.as_int()}")
    
    def example_6_custom_validators(self):
        """Example 6: Custom validators and converters."""
        print("\n=== Example 6: Custom Validators ===")
        
        # Email validator
        class EmailValidator:
            def validate(self, value: Any) -> bool:
                if not isinstance(value, str):
                    return False
                # Simple email check
                return "@" in value and "." in value.split("@")[1]
        
        # Phone number converter (removes non-digits)
        class PhoneConverter:
            def convert(self, value: Any) -> Any:
                if isinstance(value, str):
                    return "".join(c for c in value if c.isdigit())
                return value
        
        # Create validated types
        email_type = type_builder.string().add_validator(EmailValidator())
        phone_type = type_builder.string().add_converter(PhoneConverter())
        
        # Test email validation
        try:
            valid_email = AlgebraicValue(email_type, "user@example.com")
            print(f"Valid email: {valid_email.as_string()}")
        except TypeError:
            print("Invalid email rejected")
        
        try:
            invalid_email = AlgebraicValue(email_type, "not-an-email")
        except TypeError as e:
            print(f"Invalid email rejected: {e}")
        
        # Test phone converter
        phone = AlgebraicValue(phone_type, "+1 (555) 123-4567")
        print(f"Cleaned phone: {phone.as_string()}")  # "15551234567"
    
    def example_7_spacetimedb_types(self):
        """Example 7: SpacetimeDB-specific types."""
        print("\n=== Example 7: SpacetimeDB Types ===")
        
        # Identity type
        identity_bytes = b'\x01' * 32  # 32 bytes
        identity = AlgebraicValue(type_builder.identity(), identity_bytes)
        print(f"Identity: {identity.as_bytes().hex()}")
        
        # Address type
        address_bytes = b'\xFF' * 16  # 16 bytes
        address = AlgebraicValue(type_builder.address(), address_bytes)
        print(f"Address: {address.as_bytes().hex()}")
        
        # Timestamp type
        now = datetime.now()
        timestamp = AlgebraicValue(type_builder.timestamp(), now)
        print(f"Timestamp (microseconds): {timestamp.as_int()}")
        
        # Convert to JSON (ISO format)
        timestamp_json = timestamp.to_json()
        print(f"Timestamp JSON: {timestamp_json}")
    
    def example_8_schema_evolution(self):
        """Example 8: Schema evolution and migration."""
        print("\n=== Example 8: Schema Evolution ===")
        
        # Version 1 of User schema
        user_v1_type = type_builder.product([
            FieldInfo("id", type_builder.u32()),
            FieldInfo("name", type_builder.string())
        ], "UserV1")
        
        # Version 2 adds email field
        user_v2_type = type_builder.product([
            FieldInfo("id", type_builder.u32()),
            FieldInfo("name", type_builder.string()),
            FieldInfo("email", type_builder.option(type_builder.string()))
        ], "UserV2")
        
        # Old data
        old_user_data = {"id": 1, "name": "Alice"}
        
        # Can't directly create v2 from v1 data (missing field)
        # But we can migrate:
        migrated_data = {
            **old_user_data,
            "email": None  # New field with default
        }
        
        user_v2 = AlgebraicValue(user_v2_type, migrated_data)
        print(f"Migrated user: {user_v2.to_json()}")
        
        # Version 3 changes field type
        user_v3_type = type_builder.product([
            FieldInfo("id", type_builder.u64()),  # Changed from u32 to u64
            FieldInfo("name", type_builder.string()),
            FieldInfo("email", type_builder.option(type_builder.string())),
            FieldInfo("created_at", type_builder.timestamp())
        ], "UserV3")
        
        # Migration with type conversion
        final_data = {
            "id": migrated_data["id"],  # u32 -> u64 is safe
            "name": migrated_data["name"],
            "email": migrated_data["email"],
            "created_at": datetime.now()
        }
        
        user_v3 = AlgebraicValue(user_v3_type, final_data)
        print(f"Final user: {user_v3.to_json()}")
    
    def example_9_recursive_types(self):
        """Example 9: Recursive type definitions."""
        print("\n=== Example 9: Recursive Types ===")
        
        # Define a tree node type (recursive)
        # First register the type name
        self.registry.register("TreeNode", None)  # Placeholder
        
        # Define the actual type with self-reference
        tree_node_type = type_builder.product([
            FieldInfo("value", type_builder.i32()),
            FieldInfo("left", type_builder.option(self.registry.ref("TreeNode"))),
            FieldInfo("right", type_builder.option(self.registry.ref("TreeNode")))
        ], "TreeNode")
        
        # Update registration
        self.registry.register("TreeNode", tree_node_type)
        
        # Create a simple tree
        #       5
        #      / \
        #     3   7
        tree_data = {
            "value": 5,
            "left": {
                "value": 3,
                "left": None,
                "right": None
            },
            "right": {
                "value": 7,
                "left": None,
                "right": None
            }
        }
        
        tree = AlgebraicValue(tree_node_type, tree_data)
        
        # Traverse the tree
        def print_tree(node: AlgebraicValue, indent: str = ""):
            value = node.get_field("value").as_int()
            print(f"{indent}Node: {value}")
            
            left_opt = node.get_field("left")
            if left := left_opt.get_some():
                print_tree(left, indent + "  L ")
            
            right_opt = node.get_field("right")
            if right := right_opt.get_some():
                print_tree(right, indent + "  R ")
        
        print_tree(tree)
    
    def example_10_performance(self):
        """Example 10: Performance considerations."""
        print("\n=== Example 10: Performance ===")
        
        import time
        
        # Type caching
        user_type = self.registry.get("User") or type_builder.product([
            FieldInfo("id", type_builder.u64()),
            FieldInfo("name", type_builder.string())
        ], "User")
        
        # Bulk operations
        users_data = [
            {"id": i, "name": f"User{i}"}
            for i in range(1000)
        ]
        
        # Measure creation time
        start = time.time()
        users = [AlgebraicValue(user_type, data) for data in users_data]
        create_time = time.time() - start
        print(f"Created 1000 users in {create_time:.3f}s")
        
        # Measure serialization time
        start = time.time()
        serialized = [user.serialize() for user in users[:100]]
        serialize_time = time.time() - start
        print(f"Serialized 100 users in {serialize_time:.3f}s")
        
        # Measure JSON conversion time
        start = time.time()
        json_data = [user.to_json() for user in users[:100]]
        json_time = time.time() - start
        print(f"Converted 100 users to JSON in {json_time:.3f}s")
        
        # Type validation performance
        start = time.time()
        for data in users_data[:100]:
            user_type.validate(data)
        validate_time = time.time() - start
        print(f"Validated 100 users in {validate_time:.3f}s")


def main():
    """Run all algebraic type examples."""
    print("SpacetimeDB Algebraic Types Examples")
    print("====================================")
    
    example = AlgebraicTypesExample()
    
    # Run all examples
    example.example_1_primitive_types()
    example.example_2_product_types()
    example.example_3_sum_types()
    example.example_4_complex_types()
    example.example_5_collections()
    example.example_6_custom_validators()
    example.example_7_spacetimedb_types()
    example.example_8_schema_evolution()
    example.example_9_recursive_types()
    example.example_10_performance()
    
    print("\n✅ Algebraic types examples complete!")
    print("\nKey Benefits:")
    print("- Type safety at runtime")
    print("- Schema validation and evolution")
    print("- Custom validators and converters")
    print("- Efficient serialization")
    print("- JSON interoperability")
    print("- IDE support with type hints")


if __name__ == "__main__":
    main() 