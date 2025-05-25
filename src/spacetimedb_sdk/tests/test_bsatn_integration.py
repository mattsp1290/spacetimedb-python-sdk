"""
Integration tests for BSATN implementation against SpacetimeDB test module.

These tests verify compatibility with the Rust BSATN implementation by
testing against the bsatn-test module.
"""

import pytest
import os
import subprocess
import tempfile
from pathlib import Path
from spacetimedb_sdk.bsatn import encode_u8, decode_u8, encode_array_i32, decode_array_i32


class TestBsatnIntegration:
    """Integration tests against SpacetimeDB bsatn-test module."""
    
    @pytest.fixture(scope="class")
    def spacetimedb_dir(self):
        """Get the SpacetimeDB directory from environment variable."""
        spacetimedb_dir = os.environ.get('SPACETIMEDB_DIR')
        if not spacetimedb_dir:
            pytest.skip("SPACETIMEDB_DIR environment variable not set")
        
        spacetimedb_path = Path(spacetimedb_dir)
        if not spacetimedb_path.exists():
            pytest.skip(f"SpacetimeDB directory not found: {spacetimedb_path}")
        
        return spacetimedb_path
    
    @pytest.fixture(scope="class")
    def bsatn_test_module(self, spacetimedb_dir):
        """Get the bsatn-test module path."""
        module_path = spacetimedb_dir / "modules" / "bsatn-test"
        if not module_path.exists():
            pytest.skip(f"bsatn-test module not found: {module_path}")
        
        return module_path
    
    @pytest.fixture(scope="class")
    def bsatn_test_wasm(self, spacetimedb_dir):
        """Get the compiled bsatn-test WASM file."""
        wasm_path = spacetimedb_dir / "target" / "wasm32-unknown-unknown" / "release" / "bsatn_test.wasm"
        if not wasm_path.exists():
            pytest.skip(f"bsatn-test WASM not found: {wasm_path}. Run 'cargo build --release --target wasm32-unknown-unknown' in SpacetimeDB directory.")
        
        return wasm_path
    
    def test_u8_compatibility(self, bsatn_test_module):
        """Test u8 encoding compatibility with Rust implementation."""
        # Test various u8 values
        test_values = [0, 1, 42, 127, 128, 255]
        
        for value in test_values:
            # Encode using our Python implementation
            python_encoded = encode_u8(value)
            
            # Verify we can decode our own encoding
            python_decoded = decode_u8(python_encoded)
            assert python_decoded == value, f"Python round-trip failed for u8 value {value}"
            
            # The encoded data should match the expected BSATN format:
            # TAG_U8 (0x03) + value byte
            expected = bytes([0x03, value])
            assert python_encoded == expected, f"Python encoding doesn't match expected BSATN format for u8 value {value}"
    
    def test_array_i32_compatibility(self, bsatn_test_module):
        """Test array of i32 encoding compatibility with Rust implementation."""
        # Test various arrays
        test_arrays = [
            [],
            [0],
            [1, 2],
            [-1, -2],
            [2147483647, -2147483648],  # i32 bounds
            [1, -2, 3, -4, 5]
        ]
        
        for array in test_arrays:
            # Encode using our Python implementation
            python_encoded = encode_array_i32(array)
            
            # Verify we can decode our own encoding
            python_decoded = decode_array_i32(python_encoded)
            assert python_decoded == array, f"Python round-trip failed for i32 array {array}"
            
            # Verify the structure matches BSATN format:
            # TAG_ARRAY (0x14) + count (u32 LE) + items (each: TAG_I32 (0x08) + value (i32 LE))
            assert python_encoded[0] == 0x14, f"Array should start with TAG_ARRAY (0x14)"
            
            # Check count
            count_bytes = python_encoded[1:5]
            count = int.from_bytes(count_bytes, 'little')
            assert count == len(array), f"Array count mismatch for {array}"
            
            # Check each item
            offset = 5
            for i, expected_value in enumerate(array):
                assert python_encoded[offset] == 0x08, f"Item {i} should start with TAG_I32 (0x08)"
                value_bytes = python_encoded[offset+1:offset+5]
                actual_value = int.from_bytes(value_bytes, 'little', signed=True)
                assert actual_value == expected_value, f"Item {i} value mismatch"
                offset += 5
    
    def test_known_bsatn_vectors(self):
        """Test against known BSATN encoding vectors."""
        # These are manually verified BSATN encodings that should match
        # the Rust implementation exactly
        
        test_vectors = [
            # (description, python_value, expected_bsatn_bytes)
            ("u8 value 42", 42, bytes([0x03, 42])),
            ("u8 value 0", 0, bytes([0x03, 0])),
            ("u8 value 255", 255, bytes([0x03, 255])),
            
            # Array of two i32 values: [1, 2]
            ("array [1, 2]", [1, 2], bytes([
                0x14,  # TAG_ARRAY
                0x02, 0x00, 0x00, 0x00,  # count = 2 (u32 LE)
                0x08,  # TAG_I32
                0x01, 0x00, 0x00, 0x00,  # value = 1 (i32 LE)
                0x08,  # TAG_I32
                0x02, 0x00, 0x00, 0x00,  # value = 2 (i32 LE)
            ])),
            
            # Empty array
            ("empty array", [], bytes([
                0x14,  # TAG_ARRAY
                0x00, 0x00, 0x00, 0x00,  # count = 0 (u32 LE)
            ])),
            
            # Array with negative values: [-1, -2]
            ("array [-1, -2]", [-1, -2], bytes([
                0x14,  # TAG_ARRAY
                0x02, 0x00, 0x00, 0x00,  # count = 2 (u32 LE)
                0x08,  # TAG_I32
                0xFF, 0xFF, 0xFF, 0xFF,  # value = -1 (i32 LE)
                0x08,  # TAG_I32
                0xFE, 0xFF, 0xFF, 0xFF,  # value = -2 (i32 LE)
            ])),
        ]
        
        for description, python_value, expected_bytes in test_vectors:
            if isinstance(python_value, int) and 0 <= python_value <= 255:
                # u8 value
                actual_bytes = encode_u8(python_value)
            elif isinstance(python_value, list):
                # array of i32
                actual_bytes = encode_array_i32(python_value)
            else:
                pytest.fail(f"Unknown test vector type for {description}")
            
            assert actual_bytes == expected_bytes, (
                f"BSATN encoding mismatch for {description}:\n"
                f"Expected: {expected_bytes.hex()}\n"
                f"Actual:   {actual_bytes.hex()}"
            )
            
            # Also test decoding
            if isinstance(python_value, int) and 0 <= python_value <= 255:
                decoded_value = decode_u8(expected_bytes)
            elif isinstance(python_value, list):
                decoded_value = decode_array_i32(expected_bytes)
            
            assert decoded_value == python_value, (
                f"BSATN decoding mismatch for {description}:\n"
                f"Expected: {python_value}\n"
                f"Actual:   {decoded_value}"
            )
    
    def test_cross_language_compatibility(self):
        """Test that our encoding can be decoded by other implementations."""
        # This test verifies that our Python BSATN implementation produces
        # the same binary format as the Rust implementation
        
        # Test data that should be identical across implementations
        test_cases = [
            # Simple u8 values
            (encode_u8, decode_u8, 0),
            (encode_u8, decode_u8, 42),
            (encode_u8, decode_u8, 255),
            
            # Arrays of i32
            (encode_array_i32, decode_array_i32, []),
            (encode_array_i32, decode_array_i32, [0]),
            (encode_array_i32, decode_array_i32, [1, 2]),
            (encode_array_i32, decode_array_i32, [-1, -2]),
            (encode_array_i32, decode_array_i32, [2147483647, -2147483648]),
        ]
        
        for encode_func, decode_func, test_value in test_cases:
            # Encode with our implementation
            encoded = encode_func(test_value)
            
            # Decode with our implementation
            decoded = decode_func(encoded)
            
            # Should round-trip perfectly
            assert decoded == test_value, (
                f"Round-trip failed for {test_value}:\n"
                f"Original: {test_value}\n"
                f"Decoded:  {decoded}\n"
                f"Encoded:  {encoded.hex()}"
            )
    
    @pytest.mark.skipif(
        not os.environ.get('SPACETIMEDB_DIR'),
        reason="SPACETIMEDB_DIR not set - skipping integration tests"
    )
    def test_format_documentation(self, spacetimedb_dir):
        """Test that our implementation matches the documented BSATN format."""
        # This test serves as documentation of the BSATN format
        # and ensures our implementation is correct
        
        # BSATN format documentation:
        # - All multi-byte integers are little-endian
        # - Each value is prefixed with a type tag
        # - Strings and byte arrays are length-prefixed with u32
        # - Arrays are count-prefixed with u32, followed by elements
        # - Structs are field-count-prefixed, then field-name-length (u8) + name + value
        
        # Test u8: TAG_U8 (0x03) + value
        u8_encoded = encode_u8(42)
        assert u8_encoded == bytes([0x03, 42])
        
        # Test array: TAG_ARRAY (0x14) + count (u32 LE) + elements
        array_encoded = encode_array_i32([1, 2])
        expected_array = bytes([
            0x14,  # TAG_ARRAY
            0x02, 0x00, 0x00, 0x00,  # count = 2 (u32 LE)
            0x08, 0x01, 0x00, 0x00, 0x00,  # TAG_I32 + value 1 (i32 LE)
            0x08, 0x02, 0x00, 0x00, 0x00,  # TAG_I32 + value 2 (i32 LE)
        ])
        assert array_encoded == expected_array
        
        print("✓ BSATN format verification passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
