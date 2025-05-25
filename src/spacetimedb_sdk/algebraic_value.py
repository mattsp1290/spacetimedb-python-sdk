"""
AlgebraicValue: Type-safe value wrapper for SpacetimeDB Python SDK.

Provides runtime type safety and value operations matching TypeScript SDK:
- Type-safe value wrapping
- Runtime type checking
- Value conversion and coercion
- Equality and comparison operations
- Serialization/deserialization
"""

from typing import Any, Optional, Union, Type, TypeVar, Generic, cast
from dataclasses import dataclass
import json
from datetime import datetime

from .algebraic_type import (
    AlgebraicType, TypeKind, BoolType, IntType, FloatType,
    StringType, BytesType, ProductType, SumType, ArrayType,
    MapType, OptionType, IdentityType, AddressType, TimestampType,
    FieldInfo, VariantInfo, validate_value, serialize_value, deserialize_value
)
from .bsatn import BsatnReader, BsatnWriter
from .bsatn.exceptions import BsatnError


T = TypeVar('T')


class AlgebraicValue(Generic[T]):
    """
    Type-safe wrapper for values with algebraic types.
    
    Provides runtime type checking and safe operations on values
    that conform to SpacetimeDB's algebraic type system.
    """
    
    def __init__(self, type_def: AlgebraicType, value: T):
        """
        Create a new AlgebraicValue.
        
        Args:
            type_def: The algebraic type definition
            value: The value to wrap
            
        Raises:
            TypeError: If the value doesn't match the type definition
        """
        self._type = type_def
        
        # Convert value if needed
        converted_value = type_def.convert(value)
        
        # Validate the value
        if not type_def.validate_with_custom(converted_value):
            raise TypeError(
                f"Value {value!r} does not match type {type_def.name or type_def.kind}"
            )
        
        self._value = converted_value
    
    @property
    def type(self) -> AlgebraicType:
        """Get the algebraic type definition."""
        return self._type
    
    @property
    def value(self) -> T:
        """Get the wrapped value."""
        return self._value
    
    @property
    def kind(self) -> TypeKind:
        """Get the type kind."""
        return self._type.kind
    
    def unwrap(self) -> T:
        """Unwrap and return the raw value."""
        return self._value
    
    def as_type(self, target_type: Type[T]) -> T:
        """
        Cast the value to a specific Python type.
        
        Args:
            target_type: The target Python type
            
        Returns:
            The value cast to the target type
            
        Raises:
            TypeError: If the cast is not valid
        """
        if isinstance(self._value, target_type):
            return cast(T, self._value)
        
        # Try to convert
        try:
            return target_type(self._value)
        except (TypeError, ValueError) as e:
            raise TypeError(f"Cannot cast {self._value!r} to {target_type}") from e
    
    # Type-specific accessors
    
    def as_bool(self) -> bool:
        """Get value as boolean."""
        if self.kind != TypeKind.BOOL:
            raise TypeError(f"Cannot get {self.kind} as bool")
        return bool(self._value)
    
    def as_int(self) -> int:
        """Get value as integer."""
        if self.kind not in (TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
                            TypeKind.U128, TypeKind.U256, TypeKind.I8, TypeKind.I16,
                            TypeKind.I32, TypeKind.I64, TypeKind.I128, TypeKind.I256):
            raise TypeError(f"Cannot get {self.kind} as int")
        return int(self._value)
    
    def as_float(self) -> float:
        """Get value as float."""
        if self.kind not in (TypeKind.F32, TypeKind.F64):
            raise TypeError(f"Cannot get {self.kind} as float")
        return float(self._value)
    
    def as_string(self) -> str:
        """Get value as string."""
        if self.kind != TypeKind.STRING:
            raise TypeError(f"Cannot get {self.kind} as string")
        return str(self._value)
    
    def as_bytes(self) -> bytes:
        """Get value as bytes."""
        if self.kind != TypeKind.BYTES:
            raise TypeError(f"Cannot get {self.kind} as bytes")
        return bytes(self._value)
    
    def as_product(self) -> dict:
        """Get value as product (struct) dictionary."""
        if self.kind != TypeKind.PRODUCT:
            raise TypeError(f"Cannot get {self.kind} as product")
        return dict(self._value)
    
    def as_sum(self) -> dict:
        """Get value as sum (union) dictionary."""
        if self.kind != TypeKind.SUM:
            raise TypeError(f"Cannot get {self.kind} as sum")
        return dict(self._value)
    
    def as_array(self) -> list:
        """Get value as array."""
        if self.kind != TypeKind.ARRAY:
            raise TypeError(f"Cannot get {self.kind} as array")
        return list(self._value)
    
    def as_map(self) -> dict:
        """Get value as map."""
        if self.kind != TypeKind.MAP:
            raise TypeError(f"Cannot get {self.kind} as map")
        return dict(self._value)
    
    def as_option(self) -> Optional[Any]:
        """Get value as optional."""
        if self.kind != TypeKind.OPTION:
            raise TypeError(f"Cannot get {self.kind} as option")
        return self._value
    
    # Field/element access for complex types
    
    def get_field(self, field_name: str) -> 'AlgebraicValue':
        """
        Get a field from a product type.
        
        Args:
            field_name: Name of the field
            
        Returns:
            AlgebraicValue wrapping the field value
            
        Raises:
            TypeError: If not a product type
            KeyError: If field doesn't exist
        """
        if not isinstance(self._type, ProductType):
            raise TypeError(f"Cannot get field from {self.kind}")
        
        if field_name not in self._type.field_map:
            raise KeyError(f"Field '{field_name}' not found in product type")
        
        field_info = self._type.field_map[field_name]
        field_value = self._value[field_name]
        
        return AlgebraicValue(field_info.type, field_value)
    
    def get_variant(self) -> tuple[str, Optional['AlgebraicValue']]:
        """
        Get the active variant from a sum type.
        
        Returns:
            Tuple of (variant_name, variant_value)
            
        Raises:
            TypeError: If not a sum type
        """
        if not isinstance(self._type, SumType):
            raise TypeError(f"Cannot get variant from {self.kind}")
        
        variant_name = list(self._value.keys())[0]
        variant_info = self._type.variant_map[variant_name]
        
        if variant_info.type:
            variant_value = AlgebraicValue(
                variant_info.type,
                self._value[variant_name]
            )
            return (variant_name, variant_value)
        else:
            return (variant_name, None)
    
    def get_element(self, index: int) -> 'AlgebraicValue':
        """
        Get an element from an array type.
        
        Args:
            index: Index of the element
            
        Returns:
            AlgebraicValue wrapping the element
            
        Raises:
            TypeError: If not an array type
            IndexError: If index out of bounds
        """
        if not isinstance(self._type, ArrayType):
            raise TypeError(f"Cannot get element from {self.kind}")
        
        if index < 0 or index >= len(self._value):
            raise IndexError(f"Index {index} out of bounds")
        
        return AlgebraicValue(self._type.element_type, self._value[index])
    
    def get_entry(self, key: Any) -> 'AlgebraicValue':
        """
        Get an entry from a map type.
        
        Args:
            key: Key to look up
            
        Returns:
            AlgebraicValue wrapping the value
            
        Raises:
            TypeError: If not a map type
            KeyError: If key doesn't exist
        """
        if not isinstance(self._type, MapType):
            raise TypeError(f"Cannot get entry from {self.kind}")
        
        if key not in self._value:
            raise KeyError(f"Key {key!r} not found in map")
        
        return AlgebraicValue(self._type.value_type, self._value[key])
    
    def get_some(self) -> Optional['AlgebraicValue']:
        """
        Get the inner value from an option type.
        
        Returns:
            AlgebraicValue wrapping the inner value, or None
            
        Raises:
            TypeError: If not an option type
        """
        if not isinstance(self._type, OptionType):
            raise TypeError(f"Cannot get inner value from {self.kind}")
        
        if self._value is None:
            return None
        
        return AlgebraicValue(self._type.inner_type, self._value)
    
    # Comparison operations
    
    def __eq__(self, other: Any) -> bool:
        """Check equality with another value."""
        if isinstance(other, AlgebraicValue):
            return self._type == other._type and self._value == other._value
        return self._value == other
    
    def __ne__(self, other: Any) -> bool:
        """Check inequality."""
        return not self.__eq__(other)
    
    def __lt__(self, other: Any) -> bool:
        """Less than comparison."""
        if isinstance(other, AlgebraicValue):
            if self._type != other._type:
                raise TypeError(f"Cannot compare {self._type.name} with {other._type.name}")
            return self._value < other._value
        return self._value < other
    
    def __le__(self, other: Any) -> bool:
        """Less than or equal comparison."""
        return self.__lt__(other) or self.__eq__(other)
    
    def __gt__(self, other: Any) -> bool:
        """Greater than comparison."""
        return not self.__le__(other)
    
    def __ge__(self, other: Any) -> bool:
        """Greater than or equal comparison."""
        return not self.__lt__(other)
    
    # String representation
    
    def __str__(self) -> str:
        """Get string representation of the value."""
        return str(self._value)
    
    def __repr__(self) -> str:
        """Get detailed representation."""
        type_name = self._type.name or str(self._type.kind)
        return f"AlgebraicValue({type_name}, {self._value!r})"
    
    # Serialization
    
    def serialize(self) -> bytes:
        """Serialize this value to BSATN format."""
        return serialize_value(self._type, self._value)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self._to_json_value())
    
    def _to_json_value(self) -> Any:
        """Convert to JSON-serializable value."""
        if self.kind in (TypeKind.BOOL, TypeKind.STRING):
            return self._value
        elif self.kind in (TypeKind.U8, TypeKind.U16, TypeKind.U32, TypeKind.U64,
                          TypeKind.I8, TypeKind.I16, TypeKind.I32, TypeKind.I64,
                          TypeKind.F32, TypeKind.F64):
            return self._value
        elif self.kind == TypeKind.BYTES:
            # Convert bytes to base64
            import base64
            return base64.b64encode(self._value).decode('ascii')
        elif self.kind == TypeKind.PRODUCT:
            result = {}
            for field_name, field_value in self._value.items():
                field_av = self.get_field(field_name)
                result[field_name] = field_av._to_json_value()
            return result
        elif self.kind == TypeKind.SUM:
            variant_name, variant_value = self.get_variant()
            if variant_value:
                return {variant_name: variant_value._to_json_value()}
            return {variant_name: None}
        elif self.kind == TypeKind.ARRAY:
            return [self.get_element(i)._to_json_value() 
                   for i in range(len(self._value))]
        elif self.kind == TypeKind.MAP:
            # Note: JSON only supports string keys
            result = {}
            for key, value in self._value.items():
                key_str = str(key)
                value_av = AlgebraicValue(self._type.value_type, value)
                result[key_str] = value_av._to_json_value()
            return result
        elif self.kind == TypeKind.OPTION:
            inner = self.get_some()
            return inner._to_json_value() if inner else None
        elif self.kind == TypeKind.IDENTITY:
            # Convert to hex string
            return self._value.hex()
        elif self.kind == TypeKind.ADDRESS:
            # Convert to hex string
            return self._value.hex()
        elif self.kind == TypeKind.TIMESTAMP:
            # Convert to ISO format
            if isinstance(self._value, int):
                dt = datetime.fromtimestamp(self._value / 1_000_000)
                return dt.isoformat()
            return self._value
        else:
            return str(self._value)
    
    @classmethod
    def from_json(cls, type_def: AlgebraicType, json_str: str) -> 'AlgebraicValue':
        """Create AlgebraicValue from JSON string."""
        data = json.loads(json_str)
        return cls._from_json_value(type_def, data)
    
    @classmethod
    def _from_json_value(cls, type_def: AlgebraicType, data: Any) -> 'AlgebraicValue':
        """Create AlgebraicValue from JSON-parsed data."""
        if type_def.kind == TypeKind.BYTES and isinstance(data, str):
            # Decode base64
            import base64
            value = base64.b64decode(data)
        elif type_def.kind == TypeKind.IDENTITY and isinstance(data, str):
            # Decode hex
            value = bytes.fromhex(data)
        elif type_def.kind == TypeKind.ADDRESS and isinstance(data, str):
            # Decode hex
            value = bytes.fromhex(data)
        elif type_def.kind == TypeKind.TIMESTAMP and isinstance(data, str):
            # Parse ISO format
            dt = datetime.fromisoformat(data)
            value = int(dt.timestamp() * 1_000_000)
        else:
            value = data
        
        return cls(type_def, value)
    
    @classmethod
    def deserialize(cls, type_def: AlgebraicType, data: bytes) -> 'AlgebraicValue':
        """Deserialize from BSATN format."""
        value = deserialize_value(type_def, data)
        return cls(type_def, value)


# Convenience constructors

def bool_value(value: bool) -> AlgebraicValue[bool]:
    """Create a boolean AlgebraicValue."""
    return AlgebraicValue(BoolType(), value)


def u8_value(value: int) -> AlgebraicValue[int]:
    """Create a u8 AlgebraicValue."""
    return AlgebraicValue(IntType(8, False), value)


def u16_value(value: int) -> AlgebraicValue[int]:
    """Create a u16 AlgebraicValue."""
    return AlgebraicValue(IntType(16, False), value)


def u32_value(value: int) -> AlgebraicValue[int]:
    """Create a u32 AlgebraicValue."""
    return AlgebraicValue(IntType(32, False), value)


def u64_value(value: int) -> AlgebraicValue[int]:
    """Create a u64 AlgebraicValue."""
    return AlgebraicValue(IntType(64, False), value)


def i8_value(value: int) -> AlgebraicValue[int]:
    """Create an i8 AlgebraicValue."""
    return AlgebraicValue(IntType(8, True), value)


def i16_value(value: int) -> AlgebraicValue[int]:
    """Create an i16 AlgebraicValue."""
    return AlgebraicValue(IntType(16, True), value)


def i32_value(value: int) -> AlgebraicValue[int]:
    """Create an i32 AlgebraicValue."""
    return AlgebraicValue(IntType(32, True), value)


def i64_value(value: int) -> AlgebraicValue[int]:
    """Create an i64 AlgebraicValue."""
    return AlgebraicValue(IntType(64, True), value)


def f32_value(value: float) -> AlgebraicValue[float]:
    """Create an f32 AlgebraicValue."""
    return AlgebraicValue(FloatType(32), value)


def f64_value(value: float) -> AlgebraicValue[float]:
    """Create an f64 AlgebraicValue."""
    return AlgebraicValue(FloatType(64), value)


def string_value(value: str) -> AlgebraicValue[str]:
    """Create a string AlgebraicValue."""
    return AlgebraicValue(StringType(), value)


def bytes_value(value: bytes) -> AlgebraicValue[bytes]:
    """Create a bytes AlgebraicValue."""
    return AlgebraicValue(BytesType(), value) 