# SpacetimeDB Python SDK - Circular Import Analysis Report

## Task 1: Analyze and Document Circular Dependencies

**Date:** 2025-05-27  
**Analysis Tool:** analyze_circular_imports.py + manual inspection  

## Executive Summary

The SpacetimeDB Python SDK has a **critical circular import** that prevents the module from being imported. While the automated analysis detected 0 circular dependencies at the module graph level, the actual import test confirms:

```
ImportError: cannot import name 'SpacetimeDBConnectionBuilder' from partially 
initialized module 'spacetimedb_sdk.connection_builder'
```

## Circular Dependency Details

### Primary Circular Import

**File 1: `src/spacetimedb_sdk/connection_builder.py`**
- Line 32-34: Imports from connection_pool:
  ```python
  from .connection_pool import (
      ConnectionPool, LoadBalancedConnectionManager, RetryPolicy
  )
  ```

**File 2: `src/spacetimedb_sdk/connection_pool.py`**
- Line 26: Imports from connection_builder:
  ```python
  from .connection_builder import SpacetimeDBConnectionBuilder
  ```

### Import Chain Analysis

1. When Python tries to import `spacetimedb_sdk`:
   - `__init__.py` imports `SpacetimeDBConnectionBuilder` from `connection_builder.py` (line 264)
   - `connection_builder.py` starts loading
   - `connection_builder.py` tries to import from `connection_pool.py` (line 32)
   - `connection_pool.py` starts loading
   - `connection_pool.py` tries to import `SpacetimeDBConnectionBuilder` from `connection_builder.py` (line 26)
   - But `connection_builder.py` hasn't finished loading yet → **CIRCULAR IMPORT ERROR**

### Secondary Issue: Test Fixtures in Main Package

**File: `src/spacetimedb_sdk/__init__.py`**
- Lines 222-230: Imports test fixtures into main package:
  ```python
  from .test_fixtures import (
      TestDatabase,
      TestIsolation,
      CoverageTracker,
      TestResultAggregator,
      is_ci_environment,
      get_test_database_url,
      get_test_module_name
  )
  ```

**File: `src/spacetimedb_sdk/test_fixtures.py`**
- Line 29: Also imports SpacetimeDBConnectionBuilder:
  ```python
  from .connection_builder import SpacetimeDBConnectionBuilder
  ```

This creates an additional path to the circular import and violates best practices by including test utilities in the main package.

## Import Type Analysis

### Runtime vs Type-Only Imports

1. **connection_pool.py → connection_builder.py**
   - Import type: **RUNTIME** (not in TYPE_CHECKING block)
   - Usage: Only mentioned in comments, no actual usage found in the code
   - **Can be converted to TYPE_CHECKING import**

2. **connection_builder.py → connection_pool.py**
   - Import type: **RUNTIME** 
   - Usage: 
     - Line 809: `ConnectionPool` instantiated in `build_pool()` method
     - Line 823: `RetryPolicy` instantiated in `with_retry_policy()` method
   - **Cannot be easily converted to TYPE_CHECKING**

### Lazy Import Analysis

The `modern_client.py` file shows a pattern of lazy imports to avoid circular dependencies:
- Line 149: Lazy import of SpacetimeDBConnectionBuilder in `builder()` method

## Recommended Solutions

### Quick Fix (Immediate Resolution)

1. **Fix connection_pool.py imports:**
   ```python
   from typing import TYPE_CHECKING
   
   if TYPE_CHECKING:
       from .connection_builder import SpacetimeDBConnectionBuilder
   ```
   
2. **Remove test_fixtures from __init__.py:**
   - Remove lines 222-230 from `__init__.py`
   - Remove corresponding entries from `__all__`

### Long-term Fix (Architectural Improvement)

1. **Create a shared types module** (`shared_types.py`):
   - Move `RetryPolicy` class to shared module
   - Both files can import from shared module

2. **Implement factory pattern:**
   - Move pool creation logic to a separate factory module
   - Keep builder focused on single client creation

3. **Create proper test package structure:**
   - Move `test_fixtures.py` to `src/spacetimedb_sdk/testing/fixtures.py`
   - Only import when running tests

## Verification Tests

### Test 1: Basic Import
```python
import spacetimedb_sdk
```
**Current Result:** ❌ ImportError

### Test 2: Builder Pattern
```python
from spacetimedb_sdk import SpacetimeDBClient
client = SpacetimeDBClient.builder()
```
**Current Result:** ❌ Cannot import

### Test 3: Direct Connection Pool Import
```python
from spacetimedb_sdk.connection_pool import ConnectionPool
```
**Current Result:** ❌ Circular import error

## Impact Assessment

- **Severity:** CRITICAL - Complete SDK unusability
- **Affected Components:** All - cannot import SDK at all
- **User Impact:** 100% - No users can use the SDK
- **Fix Complexity:** Low for quick fix, Medium for proper architectural fix

## Next Steps

1. Implement the quick fix immediately to restore functionality
2. Create comprehensive tests to prevent regression
3. Plan architectural improvements for long-term maintainability
4. Update import guidelines in developer documentation
