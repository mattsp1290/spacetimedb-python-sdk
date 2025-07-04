# Subscription Manager Migration Guide

## Overview

This guide provides step-by-step instructions for migrating from the monolithic WebSocket client subscription logic to the new modular `SubscriptionManager` system.

## Why Migrate?

The new subscription manager provides:

- **Separation of Concerns**: Clean separation between WebSocket communication and subscription management
- **Reusability**: Subscription manager can be used with different connection types
- **Testability**: Easier to test subscription logic in isolation
- **Maintainability**: Focused modules are easier to maintain and extend
- **Health Monitoring**: Built-in health monitoring and metrics
- **Event Integration**: Native integration with the event system

## Migration Steps

### Step 1: Analyze Current Usage

First, identify how your code currently uses WebSocket client subscriptions:

```python
# OLD - Monolithic WebSocket client
from spacetimedb_sdk.websocket_client import ModernWebSocketClient

client = ModernWebSocketClient(url, database_address)
query_id = client.subscribe_single("SELECT * FROM users")
client.subscribe_multi(["SELECT * FROM orders", "SELECT * FROM products"])
```

### Step 2: Install New Dependencies

Ensure you have the new subscription manager components:

```python
# NEW - Modular subscription management
from spacetimedb_sdk.connection import (
    SubscriptionManager,
    WebSocketSubscriptionIntegration,
    LegacySubscriptionInterface,
    create_subscription_manager,
    create_websocket_subscription_integration
)
```

### Step 3: Create Subscription Manager

Replace direct WebSocket client usage with subscription manager:

```python
# OLD
client = ModernWebSocketClient(url, database_address)

# NEW
# Option 1: Direct subscription manager
manager = create_subscription_manager(
    max_subscriptions=1000,
    event_manager=my_event_manager
)

# Option 2: WebSocket integration (recommended)
integration = create_websocket_subscription_integration(
    max_subscriptions=1000,
    event_manager=my_event_manager
)

# Set up message sending
def send_message(message):
    websocket.send(message)

integration.set_message_send_callback(send_message)
```

### Step 4: Migrate Subscription Methods

#### Single Query Subscriptions

```python
# OLD
query_id = client.subscribe_single("SELECT * FROM users")

# NEW
query_id = integration.subscribe_single("SELECT * FROM users", request_id=123)
```

#### Multiple Query Subscriptions

```python
# OLD
query_id = client.subscribe_multi(["SELECT * FROM orders", "SELECT * FROM products"])

# NEW
query_id = integration.subscribe_multi([
    "SELECT * FROM orders", 
    "SELECT * FROM products"
], request_id=124)
```

#### Unsubscribe Operations

```python
# OLD
request_id = client.unsubscribe(query_id)

# NEW
success = integration.unsubscribe(query_id, request_id=125)
```

### Step 5: Migrate Message Handling

#### Server Response Handling

```python
# OLD - Handled internally by WebSocket client
def handle_message(message):
    if isinstance(message, SubscribeApplied):
        # Internal handling
        pass

# NEW - Explicit response handling
def handle_message(message):
    if isinstance(message, SubscribeApplied):
        integration.handle_subscribe_applied(message)
    elif isinstance(message, SubscriptionError):
        integration.handle_subscription_error(message)
    elif isinstance(message, UnsubscribeApplied):
        integration.handle_unsubscribe_applied(message)
```

#### Table Update Handling

```python
# OLD - Automatic handling within WebSocket client
# No explicit action needed

# NEW - Explicit table update handling
def handle_table_update(table_name, data, data_size):
    integration.handle_table_update(table_name, data_size)
```

### Step 6: Migrate Health Monitoring

#### Replace Built-in Metrics

```python
# OLD - Access through WebSocket client
metrics = client.subscription_metrics.get_all_subscription_health()

# NEW - Direct access through subscription manager
metrics = integration.subscription_manager.get_subscription_metrics()
health_report = integration.subscription_manager.perform_health_check()

# Get individual subscription health
health = integration.subscription_manager.get_subscription_health(query_id)
```

### Step 7: Migrate Event Handling

#### State Change Callbacks

```python
# OLD - No built-in state change callbacks

# NEW - Proper state change callbacks
def on_state_change(query_id, old_state, new_state):
    print(f"Subscription {query_id}: {old_state} -> {new_state}")

integration.subscription_manager.add_state_change_callback(on_state_change)
```

#### Event System Integration

```python
# OLD - No event system integration

# NEW - Full event system integration
from spacetimedb_sdk.events import EventType, SubscriptionEvent

def handle_subscription_events(event):
    if isinstance(event, SubscriptionEvent):
        print(f"Subscription event: {event.operation} - {event.success}")

event_manager.subscribe(handle_subscription_events, EventType.SUBSCRIPTION)
```

## Legacy Compatibility

For minimal migration effort, use the legacy compatibility interface:

```python
# Create legacy interface
legacy = LegacySubscriptionInterface(integration)

# Use existing method signatures
query_id = legacy.subscribe_single("SELECT * FROM users")
request_id = legacy.subscribe_to_queries(["SELECT * FROM orders"])
legacy.unsubscribe(query_id)

# Access subscription information
active_subs = legacy.get_active_subscriptions()
metrics = legacy.get_subscription_metrics()
```

## Migration Patterns

### Pattern 1: Minimal Migration

For minimal code changes, use the legacy interface:

```python
# OLD
class MyApplication:
    def __init__(self):
        self.client = ModernWebSocketClient(url, database_address)
    
    def setup_subscriptions(self):
        self.user_query = self.client.subscribe_single("SELECT * FROM users")
        self.order_query = self.client.subscribe_multi([
            "SELECT * FROM orders",
            "SELECT * FROM products"
        ])

# NEW - Minimal changes
class MyApplication:
    def __init__(self):
        integration = create_websocket_subscription_integration()
        self.client = LegacySubscriptionInterface(integration)
        # Setup WebSocket message routing
        self._setup_websocket_integration(integration)
    
    def setup_subscriptions(self):
        self.user_query = self.client.subscribe_single("SELECT * FROM users")
        self.order_query = self.client.subscribe_multi([
            "SELECT * FROM orders",
            "SELECT * FROM products"
        ])
    
    def _setup_websocket_integration(self, integration):
        # Connect WebSocket message sending
        integration.set_message_send_callback(self._send_websocket_message)
        # Handle incoming messages
        self._integration = integration
```

### Pattern 2: Full Migration

For maximum benefits, fully migrate to the new system:

```python
# OLD
class MyApplication:
    def __init__(self):
        self.client = ModernWebSocketClient(url, database_address)
        self.subscriptions = {}
    
    def setup_subscriptions(self):
        self.subscriptions['users'] = self.client.subscribe_single("SELECT * FROM users")

# NEW - Full migration
class MyApplication:
    def __init__(self):
        self.integration = create_websocket_subscription_integration(
            max_subscriptions=1000,
            event_manager=self.event_manager
        )
        self.subscriptions = {}
        self._setup_integration()
    
    def setup_subscriptions(self):
        request_id = self._generate_request_id()
        self.subscriptions['users'] = self.integration.subscribe_single(
            "SELECT * FROM users", 
            request_id=request_id
        )
    
    def _setup_integration(self):
        # Setup message sending
        self.integration.set_message_send_callback(self._send_message)
        
        # Setup state change callbacks
        self.integration.subscription_manager.add_state_change_callback(
            self._handle_state_change
        )
        
        # Setup event handling
        self.event_manager.subscribe(
            self._handle_subscription_events,
            EventType.SUBSCRIPTION
        )
    
    def _handle_state_change(self, query_id, old_state, new_state):
        logger.info(f"Subscription {query_id} state changed: {old_state} -> {new_state}")
    
    def _handle_subscription_events(self, event):
        if isinstance(event, SubscriptionEvent):
            logger.info(f"Subscription event: {event.operation}")
```

## Testing Migration

### Unit Tests

Update your unit tests to use the new subscription manager:

```python
# OLD
def test_subscription(self):
    client = ModernWebSocketClient(url, database_address)
    query_id = client.subscribe_single("SELECT * FROM users")
    assert query_id is not None

# NEW
def test_subscription(self):
    integration = create_websocket_subscription_integration()
    query_id = integration.subscribe_single("SELECT * FROM users", request_id=123)
    assert query_id is not None
    
    # Test subscription state
    sub_info = integration.subscription_manager.get_subscription_info(query_id)
    assert sub_info.state == SubscriptionState.PENDING
```

### Integration Tests

Test the full integration with WebSocket communication:

```python
def test_full_integration(self):
    integration = create_websocket_subscription_integration()
    
    # Mock WebSocket sending
    sent_messages = []
    integration.set_message_send_callback(lambda msg: sent_messages.append(msg))
    
    # Subscribe
    query_id = integration.subscribe_single("SELECT * FROM users", request_id=123)
    
    # Verify message was sent
    assert len(sent_messages) == 1
    assert isinstance(sent_messages[0], SubscribeSingleMessage)
    
    # Simulate server response
    response = SubscribeApplied(request_id=123, query_id=query_id)
    integration.handle_subscribe_applied(response)
    
    # Verify subscription is active
    sub_info = integration.subscription_manager.get_subscription_info(query_id)
    assert sub_info.state == SubscriptionState.ACTIVE
```

## Performance Considerations

### Memory Usage

The new subscription manager uses bounded collections:

```python
# Configure memory limits
integration = create_websocket_subscription_integration(
    max_subscriptions=1000  # Prevent memory exhaustion
)
```

### Thread Safety

All operations are thread-safe by default:

```python
# Safe to use from multiple threads
import threading

def subscribe_worker(integration, query):
    query_id = integration.subscribe_single(query, request_id=generate_id())
    return query_id

# Create multiple subscription threads
threads = []
for i in range(10):
    thread = threading.Thread(target=subscribe_worker, args=(integration, f"SELECT * FROM table{i}"))
    threads.append(thread)
    thread.start()
```

## Error Handling

### Migration Error Handling

```python
# OLD - Limited error handling
try:
    query_id = client.subscribe_single("SELECT * FROM users")
except Exception as e:
    logger.error(f"Subscription failed: {e}")

# NEW - Comprehensive error handling
try:
    query_id = integration.subscribe_single("SELECT * FROM users", request_id=123)
    
    # Monitor subscription health
    health = integration.subscription_manager.get_subscription_health(query_id)
    if health['status'] == 'error':
        logger.error(f"Subscription error: {health['last_error']}")
    
except Exception as e:
    logger.error(f"Subscription failed: {e}")
```

## Common Migration Issues

### Issue 1: Missing Request IDs

**Problem**: New system requires explicit request IDs
**Solution**: Generate request IDs consistently

```python
import time

def generate_request_id():
    return int(time.time() * 1000000) % 1000000

# Use in subscriptions
query_id = integration.subscribe_single("SELECT * FROM users", request_id=generate_request_id())
```

### Issue 2: Message Routing

**Problem**: Need to route server messages to integration
**Solution**: Update message handling loop

```python
def handle_websocket_message(message):
    if isinstance(message, SubscribeApplied):
        integration.handle_subscribe_applied(message)
    elif isinstance(message, SubscriptionError):
        integration.handle_subscription_error(message)
    # ... handle other message types
```

### Issue 3: Health Monitoring

**Problem**: Need to adapt health monitoring code
**Solution**: Use new health monitoring APIs

```python
# OLD
health = client.subscription_metrics.get_subscription_health("table_name")

# NEW
health = integration.subscription_manager.get_subscription_health(query_id)
```

## Validation Checklist

After migration, verify:

- [ ] All subscription methods work correctly
- [ ] Server messages are properly routed
- [ ] Health monitoring functions
- [ ] Event system integration works
- [ ] Error handling is comprehensive
- [ ] Memory usage is bounded
- [ ] Thread safety is maintained
- [ ] Performance is acceptable
- [ ] Tests pass
- [ ] Documentation is updated

## Rollback Strategy

If migration issues occur:

1. **Gradual Migration**: Migrate one component at a time
2. **Feature Flags**: Use feature flags to toggle between old and new systems
3. **Parallel Running**: Run both systems in parallel during transition
4. **Monitoring**: Monitor performance and error rates closely

```python
# Feature flag approach
USE_NEW_SUBSCRIPTION_MANAGER = os.getenv('USE_NEW_SUBSCRIPTION_MANAGER', 'false').lower() == 'true'

if USE_NEW_SUBSCRIPTION_MANAGER:
    integration = create_websocket_subscription_integration()
    client = LegacySubscriptionInterface(integration)
else:
    client = ModernWebSocketClient(url, database_address)
```

## Support and Resources

- **Documentation**: [Subscription Manager Guide](subscription_manager_guide.md)
- **Examples**: See test files for usage examples
- **Issues**: Report migration issues in the project repository
- **API Reference**: Complete API documentation in the code

This migration guide provides a comprehensive path from the monolithic WebSocket client to the modular subscription manager system. Follow the steps carefully and test thoroughly to ensure a successful migration.