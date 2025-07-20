# JSONValidator Depth Validation Bug Fix

## Problem Description

The `JSONValidator`'s depth validation was ineffective due to a critical flaw in the `_depth_hook` method. The method attempted to calculate depth from the *current object* rather than from the JSON root, allowing deeply nested JSON structures to bypass `max_json_depth` limits. This could lead to:

1. **Bypass of depth limits**: Deeply nested JSON could pass validation incorrectly
2. **RecursionError crashes**: The recursive `_calculate_depth` and `_validate_data_structure` methods could cause stack overflow
3. **Application crashes**: Instead of graceful validation failure, the application would crash

## Root Cause

The original `_depth_hook` method used `_calculate_depth(obj)` which calculated depth from the current object being processed during JSON parsing. Since `json.loads` processes each dictionary individually via the object hook, each object only knew about its own immediate structure, not its position in the overall JSON hierarchy.

## Solution

### Key Changes Made

1. **Fixed `_depth_hook` method** (lines 187-218):
   - Replaced unreliable depth calculation with simple parsing counter
   - Added recursion safety limits (990 depth limit to prevent stack overflow)
   - Used `_current_parse_depth` counter to track nested object processing during parsing

2. **Enhanced `_calculate_depth` method** (lines 220-240):
   - Added safety check to prevent RecursionError (1000 depth limit)
   - Maintained existing functionality with recursion protection

3. **Added `_calculate_depth_safe` method** (lines 242-265):
   - Provides fallback depth calculation with strict limits
   - Prevents infinite recursion by capping depth at configurable maximum
   - Used for final validation after parsing

4. **Improved `_validate_data_structure` method** (lines 267-285):
   - Added safety margin to prevent RecursionError (990 depth limit)
   - Enhanced error messages for debugging

5. **Updated final validation** (lines 112-118):
   - Uses `_calculate_depth_safe` on parsed data for accurate depth measurement
   - Provides reliable depth validation after parsing completion

### New Validation Flow

1. **Pre-scan depth check**: Catches obvious depth violations before parsing
2. **Safe parsing**: Object hook prevents excessive recursion during parsing
3. **Final depth validation**: Accurate depth measurement on fully parsed data
4. **Graceful error handling**: ValidationError instead of RecursionError crashes

## Testing

The fix was verified with comprehensive tests:
- ✅ Shallow JSON (depth 3, limit 5): Passes correctly
- ✅ Deep JSON (depth 10, limit 5): Correctly rejected with proper error message
- ✅ Edge case JSON (depth 5, limit 5): Passes correctly at exact limit
- ✅ Deep arrays (depth 6, limit 5): Correctly rejected

## Security Improvements

1. **Prevents stack overflow attacks**: Depth limits prevent RecursionError crashes
2. **Accurate depth measurement**: Properly measures depth from JSON root
3. **Graceful failure**: Returns validation errors instead of crashing
4. **Multiple safety layers**: Pre-scan + parsing limits + final validation

## Files Modified

- `src/spacetimedb_sdk/validation/data_validator.py`: Lines 187-285
  - Fixed `_depth_hook` method
  - Enhanced `_calculate_depth` method  
  - Added `_calculate_depth_safe` method
  - Improved `_validate_data_structure` method
  - Updated final validation logic

## Backward Compatibility

The fix maintains full backward compatibility:
- All existing APIs unchanged
- Same validation behavior for valid JSON
- Enhanced error handling for invalid JSON
- No breaking changes to public interfaces