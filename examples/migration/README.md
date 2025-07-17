# SpacetimeDB SDK Migration Examples

This directory contains practical examples showing how to migrate from the old SDK patterns to the new modular architecture.

## Examples Overview

### 1. Basic Connection Migration
- **[01_basic_connection_before.py](01_basic_connection_before.py)** - Old connection pattern with manual credential management
- **[01_basic_connection_after.py](01_basic_connection_after.py)** - New pattern with secure credential storage and connection builder

**Key Changes:**
- Credentials now stored encrypted instead of plaintext
- Connection builder provides better configuration options
- Automatic credential management (no manual token handling)

### 2. Event Handling Migration
- **[02_event_handling_before.py](02_event_handling_before.py)** - Old pattern with 3 different event systems
- **[02_event_handling_after.py](02_event_handling_after.py)** - New unified event system

**Key Changes:**
- Single EventType enum instead of 3 different ones
- Consistent handler signature with EventContext
- Unified subscription API
- Event filtering and prioritization

### 3. Advanced Features
- **[03_advanced_features_example.py](03_advanced_features_example.py)** - Leveraging new SDK capabilities

**New Features Demonstrated:**
- Connection pooling for multiple databases
- Advanced event filtering
- Performance monitoring and optimization
- Secure multi-environment authentication
- Complex subscription building
- Error aggregation and handling

## Running the Examples

1. **Install the SDK:**
```bash
pip install spacetimedb-sdk
```

2. **Start a local SpacetimeDB server:**
```bash
spacetimedb start
```

3. **Run an example:**
```bash
python 01_basic_connection_after.py
```

## Migration Checklist

When migrating your code, follow this checklist:

- [ ] Update imports to use new module structure
- [ ] Replace multiple EventType imports with single unified import
- [ ] Update event handler signatures to use EventContext
- [ ] Replace direct credential access with secure storage API
- [ ] Update event registration to use subscribe_to_events()
- [ ] Consider using connection builder for better configuration
- [ ] Add error handling for new event types
- [ ] Enable performance monitoring if needed
- [ ] Test thoroughly with backward compatibility mode

## Common Migration Patterns

### Pattern 1: Credential Migration
```python
# Old
client.spacetimedb_identity = "identity"
client.spacetimedb_token = "token"

# New
store_credentials("identity", "token", "host", "database")
```

### Pattern 2: Event Registration
```python
# Old
client.event_system.on('connection_opened', handler)
client.event_manager.register_handler('MESSAGE', handler)

# New
subscribe_to_events(handler, [EventType.CONNECTION_OPENED, EventType.MESSAGE_RECEIVED])
```

### Pattern 3: Handler Signature
```python
# Old
def on_message(message_type, data):
    pass

# New
def on_event(context):
    if context.event_type == EventType.MESSAGE_RECEIVED:
        data = context.data
```

## Need Help?

- See the main [MIGRATION_GUIDE.md](../../MIGRATION_GUIDE.md) for comprehensive instructions
- Check the [CHANGELOG.md](../../CHANGELOG.md) for all changes
- Use the migration checker tool: `python scripts/migration_checker.py --check src/`
- Ask questions in the SpacetimeDB Discord community