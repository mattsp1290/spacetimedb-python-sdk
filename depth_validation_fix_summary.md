# Depth Validation Bug Fix Summary

## Problem Description

The `_depth_hook` method in `src/spacetimedb_sdk/validation/data_validator.py` had a critical bug that caused:

1. **Inaccurate Depth Validation**: The validation did not reflect the true nesting level from the JSON root
2. **Performance Degradation**: O(n²) complexity due to repeated recursive calls to `_calculate_depth`
3. **Incorrect `_max_parse_depth`**: The overall maximum depth tracked was inaccurate

## Root Cause

The bug was in lines 187-218 of `data_validator.py`:

```python
def _depth_hook(self, obj: Dict[str, Any]) -> Dict[str, Any]:
    """Object hook to track parsing depth."""
    # Calculate depth by inspecting the object structure
    depth = self._calculate_depth(obj)  # ❌ PROBLEM: Recalculates depth for each object
    self._max_parse_depth = max(self._max_parse_depth, depth)
    
    # Check depth limit during parsing
    if depth > self.config.max_json_depth:
        raise JSONValidationError(f"JSON nesting too deep: {depth}")
    
    return obj

def _calculate_depth(self, obj: Any, current_depth: int = 1) -> int:
    """Calculate the actual depth of a nested object/array structure."""
    # ❌ PROBLEM: This method recursively calculates depth from each object's perspective
    # causing O(n²) complexity and inaccurate depth tracking
    ...
```

When `json.loads()` called `_depth_hook` for each object during parsing, `_calculate_depth` was called repeatedly, calculating depth from each object's local perspective rather than the true depth from the JSON root.

## Solution Applied

The fix was to **remove the redundant and problematic `_depth_hook` mechanism** entirely because:

1. **Pre-scan already handles depth validation**: The `_pre_scan_depth` method already correctly and efficiently validates depth before parsing
2. **Accurate and efficient**: The pre-scan method uses O(n) complexity and provides accurate depth measurement from the JSON root
3. **Prevents redundant work**: No need to validate depth again during parsing

## Changes Made

### 1. Removed `_depth_hook` method
```python
# REMOVED: The problematic depth hook
def _depth_hook(self, obj: Dict[str, Any]) -> Dict[str, Any]:
    # ... entire method removed
```

### 2. Removed `_calculate_depth` helper method
```python
# REMOVED: The recursive depth calculation causing O(n²) complexity
def _calculate_depth(self, obj: Any, current_depth: int = 1) -> int:
    # ... entire method removed
```

### 3. Simplified JSON parsing
```python
# BEFORE:
parsed_data = json.loads(json_str, object_hook=self._depth_hook)

# AFTER:
parsed_data = json.loads(json_str)
```

### 4. Removed `_max_parse_depth` attribute
```python
# REMOVED: No longer needed since we don't track depth during parsing
self._max_parse_depth = 0
```

## Benefits of the Fix

1. **Accurate Depth Validation**: Depth is now correctly measured from the JSON root using the pre-scan method
2. **Improved Performance**: Complexity reduced from O(n²) to O(n)
3. **Simpler Code**: Removed redundant complexity while maintaining all functionality
4. **Better Error Handling**: Depth validation now happens before expensive parsing, preventing memory exhaustion

## Validation Strategy

The fix maintains robust depth validation through:

1. **Pre-scan Depth Check**: `_pre_scan_depth()` efficiently scans the JSON string character by character
2. **Post-parse Structure Validation**: `_validate_data_structure()` recursively validates the parsed data structure
3. **Early Termination**: Invalid JSON is rejected before expensive parsing operations

## Files Modified

- `src/spacetimedb_sdk/validation/data_validator.py`: Removed problematic depth tracking, simplified JSON parsing

## Testing

The fix has been verified to:
- ✅ Correctly validate depth limits
- ✅ Reject overly nested JSON structures
- ✅ Accept valid JSON within depth limits
- ✅ Maintain O(n) performance characteristics
- ✅ Preserve all existing functionality

This fix resolves the depth validation bug while improving both accuracy and performance.