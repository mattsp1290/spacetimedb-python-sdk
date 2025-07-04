# Subscription Manager API Reference

## Core Classes

### SubscriptionManager

The main subscription management class that handles QueryId tracking, state management, and health monitoring.

#### Constructor

```python
SubscriptionManager(
    max_subscriptions: int = 1000,
    memory_accountant: Optional[MemoryAccountant] = None,
    event_manager: Optional[EnhancedEventManager] = None,
    logger: Optional[logging.Logger] = None
)
```

**Parameters:**
- `max_subscriptions`: Maximum number of concurrent subscriptions
- `memory_accountant`: Memory accounting for bounded storage (optional)
- `event_manager`: Event manager for subscription events (optional)
- `logger`: Logger for subscription operations (optional)

#### Methods

##### register_subscription()
```python
register_subscription(
    query_id: QueryId,
    queries: List[str],
    request_id: int
) -> None
```
Register a new subscription with the manager.

**Parameters:**
- `query_id`: The QueryId for this subscription
- `queries`: List of SQL queries for this subscription
- `request_id`: The request ID for tracking responses

##### activate_subscription()
```python
activate_subscription(query_id: QueryId) -> bool
```
Activate a pending subscription.

**Parameters:**
- `query_id`: The QueryId to activate

**Returns:** `True` if successfully activated, `False` otherwise

##### activate_subscription_by_request()
```python
activate_subscription_by_request(request_id: int) -> bool
```
Activate a subscription by request ID.

**Parameters:**
- `request_id`: The request ID to activate

**Returns:** `True` if successfully activated, `False` otherwise

##### record_subscription_data()
```python
record_subscription_data(query_id: QueryId, data_size: int) -> None
```
Record data received for a subscription.

**Parameters:**
- `query_id`: The QueryId that received data
- `data_size`: Size of the data in bytes

##### record_subscription_error()
```python
record_subscription_error(query_id: QueryId, error: str) -> None
```
Record an error for a subscription.

**Parameters:**
- `query_id`: The QueryId that had an error
- `error`: Error message

##### unregister_subscription()
```python
unregister_subscription(query_id: QueryId) -> bool
```
Unregister a subscription.

**Parameters:**
- `query_id`: The QueryId to unregister

**Returns:** `True` if successfully unregistered, `False` otherwise

##### get_subscription_info()
```python
get_subscription_info(query_id: QueryId) -> Optional[SubscriptionInfo]
```
Get information about a subscription.

**Parameters:**
- `query_id`: The QueryId to get info for

**Returns:** `SubscriptionInfo` if found, `None` otherwise

##### get_subscription_by_request()
```python
get_subscription_by_request(request_id: int) -> Optional[SubscriptionInfo]
```
Get subscription by request ID.

**Parameters:**
- `request_id`: The request ID to look up

**Returns:** `SubscriptionInfo` if found, `None` otherwise

##### find_subscriptions_by_query()
```python
find_subscriptions_by_query(queries: List[str]) -> List[QueryId]
```
Find subscriptions that match the given queries.

**Parameters:**
- `queries`: List of SQL queries to match

**Returns:** List of QueryIds that match the queries

##### get_active_subscriptions()
```python
get_active_subscriptions() -> List[QueryId]
```
Get all active subscription QueryIds.

**Returns:** List of active QueryIds

##### get_subscription_count()
```python
get_subscription_count(state: Optional[SubscriptionState] = None) -> int
```
Get subscription count by state.

**Parameters:**
- `state`: Specific state to count, or `None` for total

**Returns:** Number of subscriptions in the given state

##### get_subscription_metrics()
```python
get_subscription_metrics() -> SubscriptionMetrics
```
Get comprehensive subscription metrics.

**Returns:** `SubscriptionMetrics` object with detailed metrics

##### get_subscription_health()
```python
get_subscription_health(query_id: QueryId) -> Dict[str, Any]
```
Get health metrics for a specific subscription.

**Parameters:**
- `query_id`: The QueryId to get health for

**Returns:** Dictionary with health metrics

##### perform_health_check()
```python
perform_health_check() -> Dict[str, Any]
```
Perform a comprehensive health check.

**Returns:** Dictionary with health check results

##### add_state_change_callback()
```python
add_state_change_callback(
    callback: Callable[[QueryId, SubscriptionState, SubscriptionState], None]
) -> None
```
Add a callback for subscription state changes.

**Parameters:**
- `callback`: Function to call on state changes

##### remove_state_change_callback()
```python
remove_state_change_callback(
    callback: Callable[[QueryId, SubscriptionState, SubscriptionState], None]
) -> None
```
Remove a state change callback.

**Parameters:**
- `callback`: Function to remove

##### clear_all_subscriptions()
```python
clear_all_subscriptions() -> None
```
Clear all subscriptions and reset state.

### WebSocketSubscriptionIntegration

Integration layer between WebSocket client and subscription manager.

#### Constructor

```python
WebSocketSubscriptionIntegration(
    subscription_manager: SubscriptionManager,
    config: Optional[WebSocketSubscriptionConfig] = None,
    logger: Optional[logging.Logger] = None
)
```

**Parameters:**
- `subscription_manager`: The subscription manager instance
- `config`: Configuration for the integration (optional)
- `logger`: Logger for integration operations (optional)

#### Methods

##### set_message_send_callback()
```python
set_message_send_callback(callback: Callable[[Any], None]) -> None
```
Set the callback for sending messages to the WebSocket.

**Parameters:**
- `callback`: Function to call when sending messages

##### subscribe_single()
```python
subscribe_single(query: str, request_id: int) -> QueryId
```
Subscribe to a single query.

**Parameters:**
- `query`: The SQL query string
- `request_id`: The request ID for tracking

**Returns:** QueryId for the subscription

##### subscribe_multi()
```python
subscribe_multi(queries: List[str], request_id: int) -> QueryId
```
Subscribe to multiple queries.

**Parameters:**
- `queries`: List of SQL query strings
- `request_id`: The request ID for tracking

**Returns:** QueryId for the subscription

##### unsubscribe()
```python
unsubscribe(query_id: QueryId, request_id: int) -> bool
```
Unsubscribe from a query.

**Parameters:**
- `query_id`: The QueryId to unsubscribe from
- `request_id`: The request ID for tracking

**Returns:** `True` if unsubscribe request was sent, `False` otherwise

##### handle_subscribe_applied()
```python
handle_subscribe_applied(message: SubscribeApplied) -> None
```
Handle SubscribeApplied message from server.

**Parameters:**
- `message`: The SubscribeApplied message

##### handle_subscribe_multi_applied()
```python
handle_subscribe_multi_applied(message: SubscribeMultiApplied) -> None
```
Handle SubscribeMultiApplied message from server.

**Parameters:**
- `message`: The SubscribeMultiApplied message

##### handle_unsubscribe_applied()
```python
handle_unsubscribe_applied(message: UnsubscribeApplied) -> None
```
Handle UnsubscribeApplied message from server.

**Parameters:**
- `message`: The UnsubscribeApplied message

##### handle_unsubscribe_multi_applied()
```python
handle_unsubscribe_multi_applied(message: UnsubscribeMultiApplied) -> None
```
Handle UnsubscribeMultiApplied message from server.

**Parameters:**
- `message`: The UnsubscribeMultiApplied message

##### handle_subscription_error()
```python
handle_subscription_error(message: SubscriptionError) -> None
```
Handle SubscriptionError message from server.

**Parameters:**
- `message`: The SubscriptionError message

##### handle_table_update()
```python
handle_table_update(table_name: str, data_size: int) -> None
```
Handle table update data for subscriptions.

**Parameters:**
- `table_name`: Name of the table that was updated
- `data_size`: Size of the update data

##### get_subscription_status()
```python
get_subscription_status() -> Dict[str, Any]
```
Get comprehensive subscription status.

**Returns:** Dictionary with subscription status information

##### cleanup()
```python
cleanup() -> None
```
Clean up resources and subscriptions.

### LegacySubscriptionInterface

Compatibility layer for existing WebSocket client subscription methods.

#### Constructor

```python
LegacySubscriptionInterface(integration: WebSocketSubscriptionIntegration)
```

**Parameters:**
- `integration`: The WebSocket subscription integration

#### Methods

##### subscribe_single()
```python
subscribe_single(query: str) -> QueryId
```
Subscribe to a single query (legacy method).

**Parameters:**
- `query`: The SQL query string

**Returns:** QueryId for the subscription

##### subscribe_multi()
```python
subscribe_multi(queries: List[str]) -> QueryId
```
Subscribe to multiple queries (legacy method).

**Parameters:**
- `queries`: List of SQL query strings

**Returns:** QueryId for the subscription

##### unsubscribe()
```python
unsubscribe(query_id: QueryId) -> int
```
Unsubscribe from a query (legacy method).

**Parameters:**
- `query_id`: The QueryId to unsubscribe from

**Returns:** Request ID if successful, -1 otherwise

##### subscribe_to_queries()
```python
subscribe_to_queries(queries: List[str]) -> int
```
Subscribe to a list of queries (legacy method).

**Parameters:**
- `queries`: List of SQL query strings

**Returns:** QueryId as integer

##### get_active_subscriptions()
```python
get_active_subscriptions() -> List[QueryId]
```
Get active subscriptions.

**Returns:** List of active QueryIds

##### get_subscription_count()
```python
get_subscription_count() -> int
```
Get total subscription count.

**Returns:** Number of subscriptions

##### get_subscription_metrics()
```python
get_subscription_metrics() -> SubscriptionMetrics
```
Get subscription metrics.

**Returns:** `SubscriptionMetrics` object

## Data Classes

### SubscriptionInfo

Information about a subscription.

#### Attributes

- `query_id: QueryId` - The QueryId for this subscription
- `queries: List[str]` - List of SQL queries
- `request_id: int` - The request ID for tracking
- `state: SubscriptionState` - Current subscription state
- `created_at: float` - Creation timestamp
- `last_activity: float` - Last activity timestamp
- `message_count: int` - Number of messages received
- `error_count: int` - Number of errors encountered
- `last_error: Optional[str]` - Last error message

#### Methods

##### update_activity()
```python
update_activity() -> None
```
Update last activity timestamp.

##### increment_message_count()
```python
increment_message_count() -> None
```
Increment message count and update activity.

##### record_error()
```python
record_error(error: str) -> None
```
Record an error for this subscription.

**Parameters:**
- `error`: Error message to record

##### get_uptime()
```python
get_uptime() -> float
```
Get subscription uptime in seconds.

**Returns:** Uptime in seconds

##### get_idle_time()
```python
get_idle_time() -> float
```
Get time since last activity in seconds.

**Returns:** Idle time in seconds

### SubscriptionMetrics

Comprehensive subscription metrics.

#### Attributes

- `total_subscriptions: int` - Total number of subscriptions
- `active_subscriptions: int` - Number of active subscriptions
- `pending_subscriptions: int` - Number of pending subscriptions
- `error_subscriptions: int` - Number of error subscriptions
- `closed_subscriptions: int` - Number of closed subscriptions
- `total_messages: int` - Total messages received
- `total_errors: int` - Total errors encountered
- `average_uptime: float` - Average subscription uptime
- `error_rate: float` - Overall error rate

#### Class Methods

##### from_subscriptions()
```python
@classmethod
from_subscriptions(cls, subscriptions: Dict[QueryId, SubscriptionInfo]) -> 'SubscriptionMetrics'
```
Create metrics from subscription data.

**Parameters:**
- `subscriptions`: Dictionary of subscription data

**Returns:** `SubscriptionMetrics` instance

### WebSocketSubscriptionConfig

Configuration for WebSocket subscription integration.

#### Attributes

- `max_subscriptions: int = 1000` - Maximum concurrent subscriptions
- `enable_health_monitoring: bool = True` - Enable health monitoring
- `health_check_interval: float = 30.0` - Health check interval in seconds
- `enable_events: bool = True` - Enable event publishing
- `auto_activate_subscriptions: bool = True` - Auto-activate subscriptions
- `retry_failed_subscriptions: bool = False` - Enable retry on failure
- `max_retry_attempts: int = 3` - Maximum retry attempts

## Enums

### SubscriptionState

Subscription lifecycle states.

#### Values

- `PENDING = "pending"` - Subscription registered but not yet active
- `ACTIVE = "active"` - Subscription is active and receiving data
- `ERROR = "error"` - Subscription encountered an error
- `CLOSED = "closed"` - Subscription has been closed/unregistered

## Convenience Functions

### create_subscription_manager()

```python
create_subscription_manager(
    max_subscriptions: int = 1000,
    memory_accountant: Optional[MemoryAccountant] = None,
    event_manager: Optional[EnhancedEventManager] = None
) -> SubscriptionManager
```

Create a new subscription manager with standard configuration.

**Parameters:**
- `max_subscriptions`: Maximum number of concurrent subscriptions
- `memory_accountant`: Memory accounting for bounded storage (optional)
- `event_manager`: Event manager for subscription events (optional)

**Returns:** Configured `SubscriptionManager` instance

### create_websocket_subscription_integration()

```python
create_websocket_subscription_integration(
    max_subscriptions: int = 1000,
    event_manager: Optional[EnhancedEventManager] = None,
    config: Optional[WebSocketSubscriptionConfig] = None
) -> WebSocketSubscriptionIntegration
```

Create a WebSocket subscription integration with standard configuration.

**Parameters:**
- `max_subscriptions`: Maximum number of concurrent subscriptions
- `event_manager`: Event manager for subscription events (optional)
- `config`: Configuration for the integration (optional)

**Returns:** Configured `WebSocketSubscriptionIntegration` instance

## Events

The subscription manager publishes events to the event system when configured with an event manager.

### SubscriptionEvent

Published for subscription operations.

#### Attributes

- `query_id: Optional[str]` - The QueryId as string
- `table_name: Optional[str]` - Associated table name
- `sql_query: Optional[str]` - SQL query string
- `operation: Optional[str]` - Operation type (subscribe, activate, error, unsubscribe)
- `success: bool` - Whether the operation was successful
- `error: Optional[str]` - Error message if operation failed

## Error Handling

All methods handle errors gracefully and return appropriate values:

- Methods that modify state return `bool` to indicate success/failure
- Query methods return `None` or empty collections for missing data
- Errors are logged and optionally published as events
- Thread safety is maintained through proper locking

## Thread Safety

All classes and methods are thread-safe:

- Uses `threading.RLock` for nested lock support
- Bounded collections are thread-safe
- State changes are atomic where possible
- Callbacks are executed safely with error isolation

## Memory Management

The subscription manager uses bounded collections to prevent memory exhaustion:

- Configurable maximum subscription limits
- Memory accounting integration
- Automatic cleanup of closed subscriptions
- LRU eviction policies for bounded collections