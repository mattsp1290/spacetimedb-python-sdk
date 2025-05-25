"""
Advanced Algebraic Type System for SpacetimeDB Python SDK.

Provides comprehensive type definitions and validation matching TypeScript SDK:
- AlgebraicType for complex type definitions
- AlgebraicValue for type-safe value handling
- Type inference and validation
- Union types and optional handling
- Custom validators and converters
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union,
    TypeVar, Generic, Protocol, runtime_checkable
)
import struct
from datetime import datetime

from .bsatn import BsatnReader, BsatnWriter
from .bsatn.exceptions import BsatnError
from .bsatn.constants import (
    TAG_BOOL_FALSE, TAG_BOOL_TRUE, TAG_U8, TAG_I8, TAG_U16, TAG_I16,
    TAG_U32, TAG_I32, TAG_U64, TAG_I64, TAG_F32, TAG_F64,
    TAG_STRING, TAG_BYTES
)


T = TypeVar('T')
V = TypeVar('V')


class TypeKind(Enum):
    """Kind of algebraic type."""
    # Primitive types
    BOOL = auto()
    U8 = auto()
    U16 = auto()
    U32 = auto()
    U64 = auto()
    U128 = auto()
    U256 = auto()
    I8 = auto()
    I16 = auto()
    I32 = auto()
    I64 = auto()
    I128 = auto()
    I256 = auto()
    F32 = auto()
    F64 = auto()
    STRING = auto()
    BYTES = auto()
    
    # Complex types
    PRODUCT = auto()  # Struct/Tuple
    SUM = auto()      # Union/Enum
    ARRAY = auto()    # Fixed-size array
    MAP = auto()      # Key-value map
    OPTION = auto()   # Optional/Nullable
    REF = auto()      # Reference to another type
    
    # SpacetimeDB specific
    IDENTITY = auto()
    ADDRESS = auto()
    TIMESTAMP = auto()


@runtime_checkable
class TypeValidator(Protocol):
    """Protocol for custom type validators."""
    def validate(self, value: Any) -> bool:
        """Validate a value against this type."""
        ...


@runtime_checkable
class TypeConverter(Protocol):
    """Protocol for custom type converters."""
    def convert(self, value: Any) -> Any:
        """Convert a value to the expected type."""
        ...


@dataclass
class FieldInfo:
    """Information about a field in a product type."""
    name: str
    type: 'AlgebraicType'
    optional: bool = False
    default: Any = None
    validator: Optional[TypeValidator] = None
    converter: Optional[TypeConverter] = None


@dataclass
class VariantInfo:
    """Information about a variant in a sum type."""
    name: str
    tag: int
    type: Optional['AlgebraicType'] = None


class AlgebraicType(ABC):
    """
    Base class for algebraic types.
    
    Provides type definitions, validation, and serialization.
    """
    
    def __init__(self, kind: TypeKind, name: Optional[str] = None):
        self.kind = kind
        self.name = name
        self._validators: List[TypeValidator] = []
        self._converters: List[TypeConverter] = []
        self._cached_hash: Optional[int] = None
    
    @abstractmethod
    def validate(self, value: Any) -> bool:
        """
        Validate a value against this type.
        
        Returns:
            True if the value is valid for this type
        """
        pass
    
    @abstractmethod
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        """Serialize a value of this type."""
        pass
    
    @abstractmethod
    def deserialize(self, reader: BsatnReader) -> Any:
        """Deserialize a value of this type."""
        pass
    
    @abstractmethod
    def python_type(self) -> Type:
        """Get the Python type that represents this algebraic type."""
        pass
    
    def add_validator(self, validator: TypeValidator) -> 'AlgebraicType':
        """Add a custom validator."""
        self._validators.append(validator)
        return self
    
    def add_converter(self, converter: TypeConverter) -> 'AlgebraicType':
        """Add a custom converter."""
        self._converters.append(converter)
        return self
    
    def convert(self, value: Any) -> Any:
        """Convert a value using registered converters."""
        result = value
        for converter in self._converters:
            result = converter.convert(result)
        return result
    
    def validate_with_custom(self, value: Any) -> bool:
        """Validate using both built-in and custom validators."""
        if not self.validate(value):
            return False
        
        for validator in self._validators:
            if not validator.validate(value):
                return False
        
        return True
    
    def __hash__(self) -> int:
        """Get hash of this type for caching."""
        if self._cached_hash is None:
            self._cached_hash = hash((self.kind, self.name))
        return self._cached_hash
    
    def __eq__(self, other: Any) -> bool:
        """Check equality with another type."""
        if not isinstance(other, AlgebraicType):
            return False
        return self.kind == other.kind and self.name == other.name


# Primitive Types

class BoolType(AlgebraicType):
    """Boolean type."""
    
    def __init__(self):
        super().__init__(TypeKind.BOOL, "bool")
    
    def validate(self, value: Any) -> bool:
        return isinstance(value, bool)
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        writer.write_bool(value)
    
    def deserialize(self, reader: BsatnReader) -> bool:
        tag = reader.read_tag()
        return reader.read_bool(tag)
    
    def python_type(self) -> Type:
        return bool


class IntType(AlgebraicType):
    """Integer type with configurable size and signedness."""
    
    # Tag mapping for integer types
    TAG_MAP = {
        (8, False): TAG_U8, (8, True): TAG_I8,
        (16, False): TAG_U16, (16, True): TAG_I16,
        (32, False): TAG_U32, (32, True): TAG_I32,
        (64, False): TAG_U64, (64, True): TAG_I64,
    }
    
    def __init__(self, bits: int, signed: bool):
        self.bits = bits
        self.signed = signed
        self.tag = self.TAG_MAP.get((bits, signed))
        if self.tag is None:
            # For u128, i128, u256, i256 we'd need different handling
            raise NotImplementedError(f"{'i' if signed else 'u'}{bits} not yet supported")
        kind = getattr(TypeKind, f"{'I' if signed else 'U'}{bits}")
        super().__init__(kind, f"{'i' if signed else 'u'}{bits}")
    
    def validate(self, value: Any) -> bool:
        if not isinstance(value, int):
            return False
        
        if self.signed:
            min_val = -(2 ** (self.bits - 1))
            max_val = 2 ** (self.bits - 1) - 1
        else:
            min_val = 0
            max_val = 2 ** self.bits - 1
        
        return min_val <= value <= max_val
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        method_name = f"write_{'i' if self.signed else 'u'}{self.bits}"
        getattr(writer, method_name)(value)
    
    def deserialize(self, reader: BsatnReader) -> int:
        tag = reader.read_tag()
        if tag != self.tag:
            raise BsatnError(f"Expected tag {self.tag} for {self.name}, got {tag}")
        
        method_name = f"read_{'i' if self.signed else 'u'}{self.bits}"
        return getattr(reader, method_name)()
    
    def python_type(self) -> Type:
        return int


class FloatType(AlgebraicType):
    """Floating point type."""
    
    def __init__(self, bits: int):
        self.bits = bits
        self.tag = TAG_F32 if bits == 32 else TAG_F64
        kind = TypeKind.F32 if bits == 32 else TypeKind.F64
        super().__init__(kind, f"f{bits}")
    
    def validate(self, value: Any) -> bool:
        return isinstance(value, (int, float))
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        method_name = f"write_f{self.bits}"
        getattr(writer, method_name)(float(value))
    
    def deserialize(self, reader: BsatnReader) -> float:
        tag = reader.read_tag()
        if tag != self.tag:
            raise BsatnError(f"Expected tag {self.tag} for {self.name}, got {tag}")
        method_name = f"read_f{self.bits}"
        return getattr(reader, method_name)()
    
    def python_type(self) -> Type:
        return float


class StringType(AlgebraicType):
    """String type."""
    
    def __init__(self):
        super().__init__(TypeKind.STRING, "string")
    
    def validate(self, value: Any) -> bool:
        return isinstance(value, str)
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        writer.write_string(value)
    
    def deserialize(self, reader: BsatnReader) -> str:
        tag = reader.read_tag()
        if tag != TAG_STRING:
            raise BsatnError(f"Expected string tag {TAG_STRING}, got {tag}")
        return reader.read_string()
    
    def python_type(self) -> Type:
        return str


class BytesType(AlgebraicType):
    """Bytes type."""
    
    def __init__(self):
        super().__init__(TypeKind.BYTES, "bytes")
    
    def validate(self, value: Any) -> bool:
        return isinstance(value, (bytes, bytearray))
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        writer.write_bytes(bytes(value))
    
    def deserialize(self, reader: BsatnReader) -> bytes:
        tag = reader.read_tag()
        if tag != TAG_BYTES:
            raise BsatnError(f"Expected bytes tag {TAG_BYTES}, got {tag}")
        return reader.read_bytes_raw()
    
    def python_type(self) -> Type:
        return bytes


# Complex Types

class ProductType(AlgebraicType):
    """Product type (struct/tuple)."""
    
    def __init__(self, fields: List[FieldInfo], name: Optional[str] = None):
        super().__init__(TypeKind.PRODUCT, name)
        self.fields = fields
        self.field_map = {f.name: f for f in fields}
    
    def validate(self, value: Any) -> bool:
        if isinstance(value, dict):
            for field in self.fields:
                if not field.optional and field.name not in value:
                    return False
                if field.name in value:
                    if not field.type.validate(value[field.name]):
                        return False
        elif isinstance(value, (list, tuple)):
            if len(value) != len(self.fields):
                return False
            for i, field in enumerate(self.fields):
                if not field.type.validate(value[i]):
                    return False
        else:
            return False
        
        return True
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        if isinstance(value, dict):
            for field in self.fields:
                val = value.get(field.name, field.default)
                field.type.serialize(val, writer)
        else:
            for i, field in enumerate(self.fields):
                field.type.serialize(value[i], writer)
    
    def deserialize(self, reader: BsatnReader) -> Dict[str, Any]:
        result = {}
        for field in self.fields:
            result[field.name] = field.type.deserialize(reader)
        return result
    
    def python_type(self) -> Type:
        return dict


class SumType(AlgebraicType):
    """Sum type (union/enum)."""
    
    def __init__(self, variants: List[VariantInfo], name: Optional[str] = None):
        super().__init__(TypeKind.SUM, name)
        self.variants = variants
        self.variant_map = {v.name: v for v in variants}
        self.tag_map = {v.tag: v for v in variants}
    
    def validate(self, value: Any) -> bool:
        if isinstance(value, dict) and len(value) == 1:
            variant_name = list(value.keys())[0]
            if variant_name not in self.variant_map:
                return False
            variant = self.variant_map[variant_name]
            if variant.type:
                return variant.type.validate(value[variant_name])
            return True
        return False
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        variant_name = list(value.keys())[0]
        variant = self.variant_map[variant_name]
        writer.write_u8(variant.tag)
        if variant.type:
            variant.type.serialize(value[variant_name], writer)
    
    def deserialize(self, reader: BsatnReader) -> Dict[str, Any]:
        tag = reader.read_u8()
        if tag not in self.tag_map:
            raise BsatnError(f"Unknown variant tag: {tag}")
        variant = self.tag_map[tag]
        if variant.type:
            return {variant.name: variant.type.deserialize(reader)}
        return {variant.name: None}
    
    def python_type(self) -> Type:
        return dict


class ArrayType(AlgebraicType):
    """Fixed-size array type."""
    
    def __init__(self, element_type: AlgebraicType, size: int):
        super().__init__(TypeKind.ARRAY, f"[{element_type.name}; {size}]")
        self.element_type = element_type
        self.size = size
    
    def validate(self, value: Any) -> bool:
        if not isinstance(value, (list, tuple)):
            return False
        if len(value) != self.size:
            return False
        return all(self.element_type.validate(v) for v in value)
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        for item in value:
            self.element_type.serialize(item, writer)
    
    def deserialize(self, reader: BsatnReader) -> List[Any]:
        return [self.element_type.deserialize(reader) for _ in range(self.size)]
    
    def python_type(self) -> Type:
        return list


class MapType(AlgebraicType):
    """Map type (key-value pairs)."""
    
    def __init__(self, key_type: AlgebraicType, value_type: AlgebraicType):
        super().__init__(TypeKind.MAP, f"Map<{key_type.name}, {value_type.name}>")
        self.key_type = key_type
        self.value_type = value_type
    
    def validate(self, value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        for k, v in value.items():
            if not self.key_type.validate(k) or not self.value_type.validate(v):
                return False
        return True
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        writer.write_u32(len(value))
        for k, v in value.items():
            self.key_type.serialize(k, writer)
            self.value_type.serialize(v, writer)
    
    def deserialize(self, reader: BsatnReader) -> Dict[Any, Any]:
        size = reader.read_u32()
        result = {}
        for _ in range(size):
            key = self.key_type.deserialize(reader)
            value = self.value_type.deserialize(reader)
            result[key] = value
        return result
    
    def python_type(self) -> Type:
        return dict


class OptionType(AlgebraicType):
    """Optional type."""
    
    def __init__(self, inner_type: AlgebraicType):
        super().__init__(TypeKind.OPTION, f"Option<{inner_type.name}>")
        self.inner_type = inner_type
    
    def validate(self, value: Any) -> bool:
        return value is None or self.inner_type.validate(value)
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        if value is None:
            writer.write_u8(0)
        else:
            writer.write_u8(1)
            self.inner_type.serialize(value, writer)
    
    def deserialize(self, reader: BsatnReader) -> Optional[Any]:
        tag = reader.read_u8()
        if tag == 0:
            return None
        return self.inner_type.deserialize(reader)
    
    def python_type(self) -> Type:
        return Optional[self.inner_type.python_type()]


# SpacetimeDB Specific Types

class IdentityType(AlgebraicType):
    """SpacetimeDB Identity type."""
    
    def __init__(self):
        super().__init__(TypeKind.IDENTITY, "Identity")
    
    def validate(self, value: Any) -> bool:
        # Identity should be 32 bytes
        if isinstance(value, bytes):
            return len(value) == 32
        if hasattr(value, '__bytes__'):
            return len(bytes(value)) == 32
        return False
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        if hasattr(value, '__bytes__'):
            data = bytes(value)
        else:
            data = value
        if len(data) != 32:
            raise BsatnError(f"Identity must be 32 bytes, got {len(data)}")
        writer.write_bytes(data)
    
    def deserialize(self, reader: BsatnReader) -> bytes:
        tag = reader.read_tag()
        if tag != TAG_BYTES:
            raise BsatnError(f"Expected bytes tag {TAG_BYTES}, got {tag}")
        data = reader.read_bytes_raw()
        if len(data) != 32:
            raise BsatnError(f"Identity must be 32 bytes, got {len(data)}")
        return data
    
    def python_type(self) -> Type:
        return bytes


class AddressType(AlgebraicType):
    """SpacetimeDB Address type."""
    
    def __init__(self):
        super().__init__(TypeKind.ADDRESS, "Address")
    
    def validate(self, value: Any) -> bool:
        # Address should be 16 bytes
        if isinstance(value, bytes):
            return len(value) == 16
        if hasattr(value, '__bytes__'):
            return len(bytes(value)) == 16
        return False
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        if hasattr(value, '__bytes__'):
            data = bytes(value)
        else:
            data = value
        if len(data) != 16:
            raise BsatnError(f"Address must be 16 bytes, got {len(data)}")
        writer.write_bytes(data)
    
    def deserialize(self, reader: BsatnReader) -> bytes:
        tag = reader.read_tag()
        if tag != TAG_BYTES:
            raise BsatnError(f"Expected bytes tag {TAG_BYTES}, got {tag}")
        data = reader.read_bytes_raw()
        if len(data) != 16:
            raise BsatnError(f"Address must be 16 bytes, got {len(data)}")
        return data
    
    def python_type(self) -> Type:
        return bytes


class TimestampType(AlgebraicType):
    """SpacetimeDB Timestamp type (microseconds since epoch)."""
    
    def __init__(self):
        super().__init__(TypeKind.TIMESTAMP, "Timestamp")
    
    def validate(self, value: Any) -> bool:
        return isinstance(value, (int, datetime))
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        if isinstance(value, datetime):
            # Convert to microseconds since epoch
            micros = int(value.timestamp() * 1_000_000)
            writer.write_u64(micros)
        else:
            writer.write_u64(value)
    
    def deserialize(self, reader: BsatnReader) -> int:
        tag = reader.read_tag()
        if tag != TAG_U64:
            raise BsatnError(f"Expected tag {TAG_U64} for timestamp, got {tag}")
        return reader.read_u64()
    
    def python_type(self) -> Type:
        return int


# Type Registry

class TypeRegistry:
    """
    Registry for named types.
    
    Allows referencing types by name for recursive definitions.
    """
    
    def __init__(self):
        self._types: Dict[str, AlgebraicType] = {}
        self._initialize_primitives()
    
    def _initialize_primitives(self):
        """Register primitive types."""
        self.register("bool", BoolType())
        self.register("string", StringType())
        self.register("bytes", BytesType())
        
        # Integer types (only up to 64 bits for now)
        for bits in [8, 16, 32, 64]:
            self.register(f"u{bits}", IntType(bits, False))
            self.register(f"i{bits}", IntType(bits, True))
        
        # Float types
        self.register("f32", FloatType(32))
        self.register("f64", FloatType(64))
        
        # SpacetimeDB types
        self.register("Identity", IdentityType())
        self.register("Address", AddressType())
        self.register("Timestamp", TimestampType())
    
    def register(self, name: str, type_def: AlgebraicType) -> None:
        """Register a named type."""
        self._types[name] = type_def
    
    def get(self, name: str) -> Optional[AlgebraicType]:
        """Get a type by name."""
        return self._types.get(name)
    
    def ref(self, name: str) -> 'RefType':
        """Create a reference to a named type."""
        return RefType(name, self)


class RefType(AlgebraicType):
    """Reference to a named type."""
    
    def __init__(self, ref_name: str, registry: TypeRegistry):
        super().__init__(TypeKind.REF, f"Ref<{ref_name}>")
        self.ref_name = ref_name
        self.registry = registry
        self._resolved: Optional[AlgebraicType] = None
    
    def resolve(self) -> AlgebraicType:
        """Resolve the referenced type."""
        if self._resolved is None:
            self._resolved = self.registry.get(self.ref_name)
            if self._resolved is None:
                raise ValueError(f"Unknown type reference: {self.ref_name}")
        return self._resolved
    
    def validate(self, value: Any) -> bool:
        return self.resolve().validate(value)
    
    def serialize(self, value: Any, writer: BsatnWriter) -> None:
        self.resolve().serialize(value, writer)
    
    def deserialize(self, reader: BsatnReader) -> Any:
        return self.resolve().deserialize(reader)
    
    def python_type(self) -> Type:
        return self.resolve().python_type()


# Type Builder API

class TypeBuilder:
    """Fluent API for building algebraic types."""
    
    def __init__(self, registry: Optional[TypeRegistry] = None):
        self.registry = registry or TypeRegistry()
    
    # Primitive types
    def bool(self) -> BoolType:
        return BoolType()
    
    def u8(self) -> IntType:
        return IntType(8, False)
    
    def u16(self) -> IntType:
        return IntType(16, False)
    
    def u32(self) -> IntType:
        return IntType(32, False)
    
    def u64(self) -> IntType:
        return IntType(64, False)
    
    def u128(self) -> IntType:
        return IntType(128, False)
    
    def u256(self) -> IntType:
        return IntType(256, False)
    
    def i8(self) -> IntType:
        return IntType(8, True)
    
    def i16(self) -> IntType:
        return IntType(16, True)
    
    def i32(self) -> IntType:
        return IntType(32, True)
    
    def i64(self) -> IntType:
        return IntType(64, True)
    
    def i128(self) -> IntType:
        return IntType(128, True)
    
    def i256(self) -> IntType:
        return IntType(256, True)
    
    def f32(self) -> FloatType:
        return FloatType(32)
    
    def f64(self) -> FloatType:
        return FloatType(64)
    
    def string(self) -> StringType:
        return StringType()
    
    def bytes(self) -> BytesType:
        return BytesType()
    
    # Complex types
    def product(self, fields: List[FieldInfo], name: Optional[str] = None) -> ProductType:
        """Create a product type (struct)."""
        return ProductType(fields, name)
    
    def sum(self, variants: List[VariantInfo], name: Optional[str] = None) -> SumType:
        """Create a sum type (union/enum)."""
        return SumType(variants, name)
    
    def array(self, element_type: AlgebraicType, size: int) -> ArrayType:
        """Create a fixed-size array type."""
        return ArrayType(element_type, size)
    
    def map(self, key_type: AlgebraicType, value_type: AlgebraicType) -> MapType:
        """Create a map type."""
        return MapType(key_type, value_type)
    
    def option(self, inner_type: AlgebraicType) -> OptionType:
        """Create an optional type."""
        return OptionType(inner_type)
    
    def ref(self, name: str) -> RefType:
        """Create a reference to a named type."""
        return self.registry.ref(name)
    
    # SpacetimeDB types
    def identity(self) -> IdentityType:
        return IdentityType()
    
    def address(self) -> AddressType:
        return AddressType()
    
    def timestamp(self) -> TimestampType:
        return TimestampType()


# Global type builder instance
type_builder = TypeBuilder()


# Helper functions

def validate_value(type_def: AlgebraicType, value: Any) -> bool:
    """Validate a value against a type definition."""
    return type_def.validate_with_custom(value)


def serialize_value(type_def: AlgebraicType, value: Any) -> bytes:
    """Serialize a value according to a type definition."""
    from io import BytesIO
    buffer = BytesIO()
    writer = BsatnWriter(buffer)
    type_def.serialize(value, writer)
    return buffer.getvalue()


def deserialize_value(type_def: AlgebraicType, data: bytes) -> Any:
    """Deserialize a value according to a type definition."""
    reader = BsatnReader(data)
    return type_def.deserialize(reader) 