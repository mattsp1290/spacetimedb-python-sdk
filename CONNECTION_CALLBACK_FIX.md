# Connection Callback Fix Documentation

## Issue Summary

Connection callbacks registered via `register_on_connect()` were not being triggered when using the `connect()` method because it's a class method that creates a new instance, losing any callbacks registered on the original instance.

## Root Cause

The `connect()` method is defined as a `@classmethod`, which means:
1. It creates a NEW instance of the client
2. Any callbacks registered on the original instance are lost
3. Only callbacks passed as parameters to `connect()` are preserved

## Solution

Added a new instance method `connect_instance()` that preserves registered callbacks:

```python
def connect_instance(
    self,
    host: str,
    database_address: str,
    auth_token: Optional[str] = None,
    ssl_enabled: bool = True,
    db_identity: Optional[str] = None
) -> None:
    """
    Connect this instance to SpacetimeDB, preserving any registered callbacks.
    """
```

## Usage Patterns

### Pattern 1: Class Method (One-Step Connection)
Use when you want to create and connect in one step:

```python
client = ModernSpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_module",
    on_connect=lambda: print("Connected!")
)
```

### Pattern 2: Instance Method (Pre-registered Callbacks)
Use when you need to register callbacks before connecting:

```python
# Create client and register callbacks
client = ModernSpacetimeDBClient()
client.register_on_connect(lambda: print("Connected!"))
client.register_on_identity(lambda t, i, c: print(f"Identity: {i}"))

# Connect using instance method
client.connect_instance(
    host="localhost:3000",
    database_address="my_module"
)
```

## Key Differences

| Aspect | `connect()` (class method) | `connect_instance()` (instance method) |
|--------|---------------------------|----------------------------------------|
| Creates new instance | Yes | No |
| Preserves registered callbacks | No | Yes |
| Accepts callback parameters | Yes | No |
| Use case | Simple one-step connection | Complex callback setup |

## Migration Guide

If your code was doing this (broken pattern):
```python
client = ModernSpacetimeDBClient()
client.register_on_connect(my_callback)  # This won't work!
client.connect("localhost:3000", "my_db")  # Creates new instance
```

Change to either:
```python
# Option 1: Use connect_instance
client = ModernSpacetimeDBClient()
client.register_on_connect(my_callback)
client.connect_instance("localhost:3000", "my_db")

# Option 2: Pass callbacks as parameters
client = ModernSpacetimeDBClient.connect(
    "localhost:3000", "my_db",
    on_connect=my_callback
)
```

## Test Results

All three test scenarios now pass:
- ✅ Class method with callback parameters (already worked)
- ✅ Instance method pattern (now fixed with `connect_instance`)
- ✅ Direct use of `_connect_internal` (proves the fix works)

## Implementation Details

The fix reuses the existing `_connect_internal()` method, which already handles:
- WebSocket connection setup
- Callback storage and invocation
- Connection state management
- Error handling

No changes were needed to the underlying connection logic, only the addition of a proper public instance method that preserves the client instance.