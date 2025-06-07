# ⚠️ BREAKING CHANGE: SpacetimeDB v1.1.2 Compatibility

**Important**: This SDK has been updated for SpacetimeDB v1.1.2+ compatibility. If you're upgrading from an older version, please read the [Migration Guide](MIGRATION_GUIDE_v1.1.2.md) for detailed instructions on updating your code.

### Key Changes:
- **New connection URL format**: `/v1/ws/` prefix required
- **Required parameter**: `db_identity` must be provided
- **Minimum server version**: SpacetimeDB v1.1.2+

For migration assistance, see [MIGRATION_GUIDE_v1.1.2.md](MIGRATION_GUIDE_v1.1.2.md).

---

# Notice: Seeking Maintainers

Due to resource constraints, we are not actively maintaining the SpacetimeDB Python SDK at this time. Official Python SDK support will return in the future when Python modules are also supported.

For now, help wanted! We believe in the importance of open-source collaboration and want to ensure that SpacetimeDB continues to thrive. Therefore, we are seeking individuals or organizations who are interested in taking over the maintenance and development of the Python SDK.

If you are passionate about SpacetimeDB and have the time and expertise to contribute, we welcome you to step forward and become a maintainer. Your contributions will be highly valued by the community and will help ensure the longevity and sustainability of this project.

# SpacetimeDB SDK for Python

## Overview

This repository contains the [Python](https://python.org/) SDK for SpacetimeDB. The SDK allows to interact with the database server and is prepared to work with code generated from a SpacetimeDB backend code.

**Requirements**: 
- Python 3.8+
- SpacetimeDB server v1.1.2 or higher

## Documentation

The Python SDK has a [Quick Start](https://spacetimedb.com/docs/client-languages/python/python-sdk-quickstart-guide) guide and a [Reference](https://spacetimedb.com/docs/client-languages/python/python-sdk-reference).

## Installation

The SDK is available as a [PyPi package](https://pypi.org/project/spacetimedb-sdk/). To install it, run the following command:

```bash
pip install spacetimedb-sdk
```

## Usage

The Python SpacetimeDB SDK provides two client options:
1. **Modern Client** (recommended): Synchronous API with v1.1.2 protocol support
2. **Async Client**: Legacy async API for backward compatibility

### Modern Client (Recommended for v1.1.2+)

The modern client provides a synchronous API with full support for SpacetimeDB v1.1.2 features:

```python
from spacetimedb_sdk import SpacetimeDBClient

# Simple connection
client = SpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database",
    db_identity="my_identity",  # Required for v1.1.2+
    auth_token="your_auth_token",
    ssl_enabled=False
)

# Using the builder pattern
client = SpacetimeDBClient.builder() \
    .with_uri("ws://localhost:3000") \
    .with_module_name("my_database") \
    .with_db_identity("my_identity") \
    .with_token("your_auth_token") \
    .on_connect(lambda: print("Connected!")) \
    .on_identity(lambda token, identity, conn_id: print(f"Identity: {identity}")) \
    .connect()
```

### Subscribing to Queries

```python
# Subscribe to queries
query_id = client.subscribe_single("SELECT * FROM users WHERE active = true")

# Subscribe to multiple queries
query_id = client.subscribe_multi([
    "SELECT * FROM messages",
    "SELECT * FROM users"
])

# Unsubscribe
client.unsubscribe(query_id)
```

### Calling Reducers

```python
# Call a reducer
request_id = client.call_reducer("create_user", "Alice", "alice@example.com")

# Call with custom flags
from spacetimedb_sdk import CallReducerFlags
request_id = client.call_reducer(
    "update_user",
    user_id,
    new_data,
    flags=CallReducerFlags.NO_SIDE_EFFECTS
)
```

### Legacy Async Client

The async client is maintained for backward compatibility:

```python
from spacetimedb_sdk.spacetimedb_async_client import SpacetimeDBAsyncClient

spacetime_client = SpacetimeDBAsyncClient(module_bindings)
```

To connect to SpacetimeDB, you need to call the `run` method on the `SpacetimeDBAsyncClient` instance. The `run` method takes the following parameters:

- `auth_token`: The authentication token to use to connect to SpacetimeDB
- `host_name`: The hostname of the SpacetimeDB server (e.g., `http://localhost:3000`)
- `module_address`: The address of the module to connect to
- `ssl_enabled`: Whether to use SSL (required for SpacetimeDB Cloud)
- `on_connect`: A callback that is called when the client connects
- `queries`: A list of queries to subscribe to

Example:

```python
import asyncio

asyncio.run(
    spacetime_client.run(
        local_config.get_string("auth_token"),
        "http://localhost:3000",
        "chatqs",
        on_connect,
        ["SELECT * FROM User", "SELECT * FROM Message"],
    )
)
```

### Listening to events

To listen to events, you need to register callbacks on the client instance:

- `on_subscription_applied`: Called when the client receives the initial data from SpacetimeDB after subscribing to tables
- `register_row_update`: Called when a row is inserted, updated, or deleted from the table

Example:
    
```python
def on_message_row_update(row_op, message_old, message, reducer_event):
    if reducer_event is not None and row_op == "insert":
        print_message(message)

Message.register_row_update(on_message_row_update)
```

You can register for reducer call updates as well:

```python
def on_send_message_reducer(sender, status, message, msg):
    if sender == local_identity:
        if status == "failed":
            print(f"Failed to send message: {message}")

send_message_reducer.register_on_send_message(on_send_message_reducer)
```

### Accessing the client cache

The client cache is a local cache of the data that the client has received from SpacetimeDB:

```python
from module_bindings.user import User

# Filter by column
my_user = User.filter_by_identity(local_identity)

# Iterate over all rows
for user in User.iter():
    print(user.name)
```

### Calling Reducers

To call a reducer, use the autogenerated method:

```python
import module_bindings.send_message_reducer as send_message_reducer

send_message_reducer.send_message("Hello World!")
```

## Migration from Older Versions

If you're upgrading from a version prior to v1.1.2, please see the [Migration Guide](MIGRATION_GUIDE_v1.1.2.md) for detailed instructions.

### Quick Migration Example:

**Before (v1.0.x):**
```python
client = SpacetimeDBClient()
client.connect("localhost:3000", "my_database", auth_token)
```

**After (v1.1.2+):**
```python
client = SpacetimeDBClient.connect(
    host="localhost:3000",
    database_address="my_database", 
    db_identity="my_database",  # Now required!
    auth_token=auth_token
)
```

## Support

- [Documentation](https://spacetimedb.com/docs)
- [Discord Community](https://discord.gg/spacetimedb)
- [GitHub Issues](https://github.com/clockworklabs/spacetimedb-python-sdk/issues)
