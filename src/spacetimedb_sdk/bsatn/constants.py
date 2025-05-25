"""
BSATN type tags and constants.

These constants define the binary format tags used in BSATN encoding.
They must match the values defined in SpacetimeDB's Rust implementation.
"""

# Type tags - must match SpacetimeDB/crates/bindings-go/internal/bsatn/constants.go
TAG_BOOL_FALSE = 0x01
TAG_BOOL_TRUE = 0x02
TAG_U8 = 0x03
TAG_I8 = 0x04
TAG_U16 = 0x05
TAG_I16 = 0x06
TAG_U32 = 0x07
TAG_I32 = 0x08
TAG_U64 = 0x09
TAG_I64 = 0x0A
TAG_F32 = 0x0B
TAG_F64 = 0x0C
TAG_STRING = 0x0D  # length prefixed u32 LE
TAG_BYTES = 0x0E   # length prefixed u32 LE
TAG_LIST = 0x0F    # length-prefixed list of elements
TAG_OPTION_NONE = 0x10
TAG_OPTION_SOME = 0x11
TAG_STRUCT = 0x12  # struct: fieldCount u32 then nameLen u8 + name bytes + value
TAG_ENUM = 0x13    # enum: variantIndex u32 + payload(optional)
TAG_ARRAY = 0x14   # homogeneous array/slice
TAG_U128 = 0x15    # 16 bytes
TAG_I128 = 0x16    # 16 bytes
TAG_U256 = 0x17    # 32 bytes
TAG_I256 = 0x18    # 32 bytes

# Safety cap for strings/byte slices (1 MiB)
MAX_PAYLOAD_LEN = 1 << 20

# Algebraic type kind constants for type system
AT_REF = 0
AT_SUM = 1
AT_PRODUCT = 2
AT_ARRAY = 3
AT_STRING = 4
AT_BOOL = 5
AT_I8 = 6
AT_U8 = 7
AT_I16 = 8
AT_U16 = 9
AT_I32 = 10
AT_U32 = 11
AT_I64 = 12
AT_U64 = 13
AT_I128 = 14
AT_U128 = 15
AT_I256 = 16
AT_U256 = 17
AT_F32 = 18
AT_F64 = 19
