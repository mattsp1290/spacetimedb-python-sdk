# JSON API vs WebSocket: When to Use Each

## Overview

The SpacetimeDB Python SDK provides two ways to interact with your database:
1. **WebSocket Connection** - Real-time, bidirectional communication
2. **JSON API** - HTTP-based REST API for stateless operations

## Quick Comparison

| Feature | WebSocket | JSON API |
|---------|-----------|----------|
| Connection Type | Persistent | Request/Response |
| Real-time Updates | ✅ Yes | ❌ No |
| Subscriptions | ✅ Yes | ❌ No |
| Energy Efficiency | ✅ High (persistent) | ⚠️ Lower (per request) |
| Firewall Friendly | ⚠️ May need config | ✅ Standard HTTP |
| Stateless Operations | ❌ Overkill | ✅ Perfect |
| Load Balancing | ⚠️ Sticky sessions | ✅ Any backend |
| Authentication | Once per connection | Per request |

## When to Use WebSocket

Use WebSocket connections when you need:

### 1. Real-time Data Synchronization
```python
# Subscribe to live updates
client = ModernSpacetimeDBClient.builder() \
    .with_uri("ws://localhost:3000") \
    .with_module_name("chat_app") \
    .build()

# Real-time message updates
client.db.messages.on_insert(lambda ctx, msg: print(f"New: {msg.text}"))
client.subscribe(["SELECT * FROM messages WHERE channel = 'general'"])
```

### 2. Live Collaboration Features
- Multi-player games
- Collaborative editing
- Live dashboards
- Chat applications

### 3. Efficient Bulk Operations
```python
# Efficient for many operations
for i in range(1000):
    client.call_reducer("create_entity", position=(i, i))
# All calls use same connection
```

### 4. Event-Driven Applications
```python
# React to database changes
client.db.game_state.on_update(lambda ctx, old, new: 
    handle_state_change(old, new)
)
```

## When to Use JSON API

Use JSON API when you need:

### 1. Stateless Operations
```python
# One-off database query
async with SpacetimeDBJsonAPI("https://api.spacetimedb.com") as api:
    response = await api.execute_sql("mydb", "SELECT COUNT(*) FROM users")
    print(f"User count: {response.data}")
```

### 2. Administrative Tasks
```python
# List all databases
api = client.json_api
databases = await api.list_databases()
for db in databases.data:
    print(f"Database: {db.name}, Tables: {db.num_tables}")
```

### 3. Serverless/Lambda Functions
```python
# AWS Lambda function
def lambda_handler(event, context):
    api = SpacetimeDBJsonAPI(
        base_url=os.environ['SPACETIMEDB_URL'],
        auth_token=os.environ['SPACETIMEDB_TOKEN']
    )
    
    # Quick operation without persistent connection
    response = api.call_reducer_http_sync(
        "production_db",
        "process_order",
        [event['order_id']]
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps(response.data)
    }
```

### 4. CI/CD and Automation
```python
# Deployment script
api = SpacetimeDBJsonAPI("https://api.spacetimedb.com", admin_token)

# Check database health
db_info = api.get_database_info_sync("production")
if db_info.success:
    print(f"Database ready: {db_info.data.name}")
    
# Run migrations
api.call_reducer_http_sync("production", "run_migrations", [])
```

### 5. Microservice Integration
```python
# REST API endpoint in your service
@app.route('/api/users/<user_id>')
async def get_user(user_id):
    # Use JSON API for stateless HTTP-to-HTTP
    response = await spacetime_api.execute_sql(
        "users_db",
        f"SELECT * FROM users WHERE id = {user_id}"
    )
    return jsonify(response.data)
```

## Hybrid Approach

Often the best architecture uses both:

```python
class GameService:
    def __init__(self):
        # WebSocket for real-time game state
        self.ws_client = ModernSpacetimeDBClient.builder() \
            .with_uri("ws://localhost:3000") \
            .with_module_name("game") \
            .build()
        
        # JSON API for admin operations
        self.admin_api = SpacetimeDBJsonAPI(
            "http://localhost:3000",
            auth_token="admin_token"
        )
    
    async def start_game_session(self, player_id):
        """Use WebSocket for live gameplay"""
        self.ws_client.subscribe([
            f"SELECT * FROM players WHERE id = '{player_id}'",
            "SELECT * FROM game_state"
        ])
        
    async def get_player_stats(self, player_id):
        """Use JSON API for one-off queries"""
        return await self.admin_api.execute_sql(
            "game_db",
            f"SELECT * FROM player_stats WHERE player_id = '{player_id}'"
        )
```

## Performance Considerations

### WebSocket Performance
- **Connection overhead**: ~50-100ms initial setup
- **Message latency**: ~1-5ms per message
- **Memory usage**: ~10KB per connection
- **Best for**: High-frequency operations (>10/second)

### JSON API Performance
- **Request overhead**: ~20-50ms per request
- **No connection state**: 0KB memory on client
- **HTTP caching**: Can leverage CDNs
- **Best for**: Low-frequency operations (<1/second)

## Decision Matrix

```python
def choose_connection_type(
    realtime_needed: bool,
    operation_frequency: float,  # operations per second
    stateless_ok: bool,
    behind_firewall: bool
) -> str:
    if realtime_needed:
        return "WebSocket"
    
    if operation_frequency > 10:
        return "WebSocket"  # More efficient
    
    if stateless_ok and operation_frequency < 1:
        return "JSON API"  # Simpler
    
    if behind_firewall:
        return "JSON API"  # Easier to configure
    
    return "WebSocket"  # Default for most apps
```

## Best Practices

### WebSocket Best Practices
1. **Reuse connections** - Don't create new connections per operation
2. **Handle reconnection** - Network issues will happen
3. **Subscribe efficiently** - Use specific queries, not `SELECT *`
4. **Clean up** - Properly close connections when done

### JSON API Best Practices
1. **Use connection pooling** - For HTTP client efficiency
2. **Implement retry logic** - Network requests can fail
3. **Cache when possible** - Reduce unnecessary requests
4. **Use async when possible** - Better concurrency

## Example: E-commerce Platform

```python
class EcommercePlatform:
    """Hybrid approach for e-commerce"""
    
    def __init__(self):
        # WebSocket for inventory updates
        self.inventory_client = ModernSpacetimeDBClient.builder() \
            .with_uri("ws://localhost:3000") \
            .with_module_name("inventory") \
            .build()
        
        # JSON API for order processing
        self.order_api = SpacetimeDBJsonAPI("http://localhost:3000")
    
    async def monitor_inventory(self):
        """Real-time inventory tracking"""
        self.inventory_client.db.products.on_update(
            lambda ctx, old, new: self.handle_stock_change(old, new)
        )
        
    async def process_order(self, order_data):
        """Stateless order processing"""
        return await self.order_api.call_reducer_http(
            "orders_db",
            "process_order",
            [order_data]
        )
    
    async def generate_report(self, date_range):
        """One-off report generation"""
        return await self.order_api.execute_sql(
            "analytics_db",
            f"SELECT * FROM sales WHERE date BETWEEN '{date_range[0]}' AND '{date_range[1]}'"
        )
```

## Conclusion

- **Use WebSocket** for real-time, event-driven, and high-frequency operations
- **Use JSON API** for stateless, administrative, and integration scenarios
- **Consider both** for complex applications that need both capabilities
- **Performance matters** - Choose based on your operation patterns
- **Keep it simple** - Don't over-engineer; start with one and add the other when needed 