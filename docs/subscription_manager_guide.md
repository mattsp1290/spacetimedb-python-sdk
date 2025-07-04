# SubscriptionManager Guide

## Overview

The `SubscriptionManager` is a focused, reusable subscription management module extracted from the monolithic WebSocket client. It provides clean APIs for subscription lifecycle management, QueryId tracking, health monitoring, and event integration.

## Key Features

- **QueryId Management**: Centralized tracking of subscription identifiers
- **Subscription Lifecycle**: Complete state management (pending, active, error, closed)
- **Health Monitoring**: Comprehensive metrics and health checking
- **Event Integration**: Publishes subscription events to the event system
- **Thread Safety**: All operations are thread-safe with proper locking
- **Memory Bounded**: Uses bounded collections to prevent memory exhaustion
- **Error Handling**: Robust error handling and recovery mechanisms

## Architecture

The subscription management system consists of three main components:

1. **SubscriptionManager**: Core subscription management logic
2. **WebSocketSubscriptionIntegration**: Integration layer with WebSocket clients
3. **LegacySubscriptionInterface**: Compatibility layer for existing code

## Basic Usage

### Creating a Subscription Manager

```python
from spacetimedb_sdk.connection import (
    SubscriptionManager,
    create_subscription_manager
)

# Create with default settings
manager = create_subscription_manager()

# Create with custom configuration
manager = SubscriptionManager(
    max_subscriptions=500,
    memory_accountant=my_memory_accountant,
    event_manager=my_event_manager
)
```

### Managing Subscriptions

```python
from spacetimedb_sdk.query_id import QueryId

# Register a subscription
query_id = QueryId.generate()
queries = ["SELECT * FROM users", "SELECT * FROM orders"]
request_id = 12345

manager.register_subscription(query_id, queries, request_id)

# Activate the subscription
manager.activate_subscription(query_id)

# Record data activity
manager.record_subscription_data(query_id, data_size=1024)

# Record errors
manager.record_subscription_error(query_id, "Connection timeout")

# Unregister subscription
manager.unregister_subscription(query_id)
```

### Monitoring Subscription Health

```python
# Get health for a specific subscription
health = manager.get_subscription_health(query_id)
print(f"Status: {health['status']}")
print(f"Message count: {health['message_count']}")
print(f"Error rate: {health['error_rate']}")

# Get comprehensive metrics
metrics = manager.get_subscription_metrics()
print(f"Total subscriptions: {metrics.total_subscriptions}")
print(f"Active subscriptions: {metrics.active_subscriptions}")
print(f"Error rate: {metrics.error_rate}")

# Perform health check
health_report = manager.perform_health_check()
print(f"Overall status: {health_report['status']}")
```

### State Change Callbacks

```python
def on_subscription_state_change(query_id, old_state, new_state):
    print(f"Subscription {query_id} changed from {old_state} to {new_state}")

# Add callback
manager.add_state_change_callback(on_subscription_state_change)

# Remove callback
manager.remove_state_change_callback(on_subscription_state_change)
```

## WebSocket Integration

### Setting up WebSocket Integration

```python
from spacetimedb_sdk.connection import (
    WebSocketSubscriptionIntegration,
    WebSocketSubscriptionConfig,
    create_websocket_subscription_integration
)

# Create integration
integration = create_websocket_subscription_integration(
    max_subscriptions=1000,
    event_manager=my_event_manager
)

# Set message sending callback
def send_message(message):
    websocket.send(message)

integration.set_message_send_callback(send_message)
```

### Using the Integration

```python
# Subscribe to queries
query_id = integration.subscribe_single("SELECT * FROM users", request_id=123)
multi_query_id = integration.subscribe_multi([
    "SELECT * FROM orders",
    "SELECT * FROM products"
], request_id=124)

# Handle server responses
integration.handle_subscribe_applied(subscribe_applied_message)
integration.handle_subscription_error(subscription_error_message)
integration.handle_table_update("users", data_size=2048)

# Unsubscribe
integration.unsubscribe(query_id, request_id=125)
```

### Legacy Compatibility

```python
from spacetimedb_sdk.connection import LegacySubscriptionInterface

# Create legacy interface
legacy = LegacySubscriptionInterface(integration)

# Use legacy methods
query_id = legacy.subscribe_single("SELECT * FROM users")
request_id = legacy.subscribe_to_queries(["SELECT * FROM orders"])
legacy.unsubscribe(query_id)
```

## Configuration

### SubscriptionManager Configuration

```python
manager = SubscriptionManager(
    max_subscriptions=1000,        # Maximum concurrent subscriptions
    memory_accountant=accountant,  # Memory accounting (optional)
    event_manager=event_manager,   # Event system integration (optional)
    logger=custom_logger          # Custom logger (optional)
)
```

### WebSocket Integration Configuration

```python
config = WebSocketSubscriptionConfig(
    max_subscriptions=1000,
    enable_health_monitoring=True,
    health_check_interval=30.0,
    enable_events=True,
    auto_activate_subscriptions=True,
    retry_failed_subscriptions=True,
    max_retry_attempts=3
)

integration = WebSocketSubscriptionIntegration(
    subscription_manager=manager,
    config=config
)
```

## Subscription States

The subscription manager tracks subscriptions through the following states:

- **PENDING**: Subscription registered but not yet active
- **ACTIVE**: Subscription is active and receiving data
- **ERROR**: Subscription encountered an error
- **CLOSED**: Subscription has been closed/unregistered

## Health Monitoring

The subscription manager provides comprehensive health monitoring:

### Health Status Types

- **healthy**: Subscription is active and receiving data
- **warning**: Subscription is active but may be experiencing issues
- **stale**: Subscription hasn't received data recently
- **error**: Subscription is in error state
- **closed**: Subscription has been closed

### Health Metrics

```python
health = manager.get_subscription_health(query_id)
# Returns:
{
    'status': 'healthy',
    'state': 'active',
    'message_count': 100,
    'error_count': 2,
    'error_rate': 0.02,
    'uptime_seconds': 3600,
    'idle_seconds': 30,
    'last_error': None,
    'queries': ['SELECT * FROM users']
}
```

## Event Integration

The subscription manager integrates with the event system to publish subscription events:

```python
from spacetimedb_sdk.events import EventType, SubscriptionEvent

# Subscribe to subscription events
def handle_subscription_event(event):
    if isinstance(event, SubscriptionEvent):
        print(f"Subscription {event.operation}: {event.success}")

event_manager.subscribe(handle_subscription_event, EventType.SUBSCRIPTION)
```

## Error Handling

The subscription manager provides robust error handling:

### Error Recording

```python
# Record errors for subscriptions
manager.record_subscription_error(query_id, "Database connection lost")

# Errors automatically transition subscription to ERROR state
# and trigger state change callbacks
```

### Error Recovery

```python
# With retry enabled in WebSocket integration
config = WebSocketSubscriptionConfig(
    retry_failed_subscriptions=True,
    max_retry_attempts=3
)

# Failed subscriptions will be automatically retried
```

## Best Practices

### 1. Resource Management

```python
# Always clean up when done
try:
    # Use subscriptions
    pass
finally:
    manager.clear_all_subscriptions()
```

### 2. Error Handling

```python
# Always check subscription existence before operations
sub_info = manager.get_subscription_info(query_id)
if sub_info:
    manager.record_subscription_data(query_id, data_size)
```

### 3. Health Monitoring

```python
# Regularly check subscription health
health_report = manager.perform_health_check()
if health_report['status'] == 'critical':
    # Take corrective action
    pass
```

### 4. Event Integration

```python
# Use events for decoupled architecture
def handle_subscription_events(event):
    if event.operation == 'error':
        logger.error(f"Subscription error: {event.error}")
    elif event.operation == 'activate':
        logger.info(f"Subscription activated: {event.query_id}")

event_manager.subscribe(handle_subscription_events, EventType.SUBSCRIPTION)
```

## Performance Considerations

### Memory Usage

- Uses bounded collections to prevent memory exhaustion
- Configurable maximum subscription limits
- Automatic cleanup of closed subscriptions

### Thread Safety

- All operations are thread-safe with proper locking
- Uses RLock for nested lock support
- Minimal lock contention through careful design

### Scalability

- Supports thousands of concurrent subscriptions
- Efficient QueryId lookup and tracking
- Optimized health monitoring with configurable intervals

## Migration Guide

See [Migration Guide](subscription_manager_migration.md) for detailed instructions on migrating from the monolithic WebSocket client to the new subscription manager.

## Testing

The subscription manager includes comprehensive test coverage:

```bash
# Run subscription manager tests
python -m pytest test_subscription_manager.py -v

# Run specific test categories
python -m pytest test_subscription_manager.py::TestSubscriptionManager::test_thread_safety -v
```

## Troubleshooting

### Common Issues

1. **Subscription not activating**: Check if `activate_subscription` was called
2. **Memory issues**: Verify `max_subscriptions` setting and memory accountant
3. **Event not publishing**: Ensure event manager is properly configured
4. **Thread safety issues**: All operations should be thread-safe by design

### Debug Logging

```python
import logging

# Enable debug logging
logging.getLogger('spacetimedb_sdk.connection.subscription_manager').setLevel(logging.DEBUG)
```

### Health Diagnostics

```python
# Get detailed health report
health_report = manager.perform_health_check()
print(f"Status: {health_report['status']}")
print(f"Stale subscriptions: {health_report['stale_subscriptions']}")
print(f"Error rate: {health_report['error_rate']}")
```