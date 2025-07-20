# SpacetimeDB Python SDK - Troubleshooting Guide

This guide helps you diagnose and resolve common issues when using the SpacetimeDB Python SDK.

## Table of Contents

1. [Common Connection Issues](#common-connection-issues)
2. [Authentication Problems](#authentication-problems)
3. [Performance Issues](#performance-issues)
4. [Error Messages](#error-messages)
5. [Debug Logging](#debug-logging)
6. [Memory Issues](#memory-issues)
7. [Threading Issues](#threading-issues)
8. [Installation Problems](#installation-problems)

## Common Connection Issues

### Connection Refused / Cannot Connect

**Symptoms:**
- `ConnectionRefusedError` or `ConnectionError`
- Unable to establish WebSocket connection
- Timeouts during connection attempts

**Possible Causes:**
1. SpacetimeDB server is not running
2. Incorrect URL or port
3. Network connectivity issues
4. Firewall blocking connections

**Solutions:**

1. **Verify server status:**
   ```bash
   # Check if SpacetimeDB is running
   curl -f http://localhost:3000/health
   ```

2. **Check connection parameters:**
   ```python
   from spacetimedb_sdk import SpacetimeDBClient
   
   # Verify URL format
   client = SpacetimeDBClient("ws://localhost:3000")  # HTTP
   # or
   client = SpacetimeDBClient("wss://your-domain.com")  # HTTPS
   ```

3. **Test network connectivity:**
   ```python
   import asyncio
   import websockets
   
   async def test_connection():
       try:
           async with websockets.connect("ws://localhost:3000") as websocket:
               print("Connection successful")
       except Exception as e:
           print(f"Connection failed: {e}")
   
   asyncio.run(test_connection())
   ```

4. **Enable debug logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   
   # This will show detailed connection attempts
   ```

### Connection Drops / Unstable Connections

**Symptoms:**
- Intermittent connection losses
- `ConnectionResetError` or `ConnectionAbortedError`
- Frequent reconnection attempts

**Possible Causes:**
1. Network instability
2. Server overload
3. Firewall/proxy interference
4. Connection timeout settings

**Solutions:**

1. **Implement connection retry logic:**
   ```python
   from spacetimedb_sdk.retry_policies import ExponentialBackoffRetry
   
   retry_policy = ExponentialBackoffRetry(
       max_attempts=5,
       initial_delay=1.0,
       max_delay=30.0,
       multiplier=2.0
   )
   
   client = SpacetimeDBClient(
       url="ws://localhost:3000",
       retry_policy=retry_policy
   )
   ```

2. **Configure connection pooling:**
   ```python
   from spacetimedb_sdk import ConnectionPool
   
   pool = ConnectionPool(
       "ws://localhost:3000",
       min_size=5,
       max_size=20,
       connection_timeout=10.0,
       idle_timeout=300.0
   )
   ```

3. **Use connection health checks:**
   ```python
   async def connection_health_check():
       try:
           await client.ping()
           return True
       except Exception:
           return False
   
   # Check connection health periodically
   if not await connection_health_check():
       await client.reconnect()
   ```

### SSL/TLS Certificate Issues

**Symptoms:**
- `SSLError` or certificate verification failures
- Unable to connect to `wss://` endpoints

**Solutions:**

1. **Disable SSL verification (development only):**
   ```python
   import ssl
   
   ssl_context = ssl.create_default_context()
   ssl_context.check_hostname = False
   ssl_context.verify_mode = ssl.CERT_NONE
   
   client = SpacetimeDBClient(
       "wss://localhost:3000",
       ssl_context=ssl_context
   )
   ```

2. **Use custom CA certificates:**
   ```python
   import ssl
   
   ssl_context = ssl.create_default_context()
   ssl_context.load_verify_locations('/path/to/ca-certificate.pem')
   
   client = SpacetimeDBClient(
       "wss://your-domain.com",
       ssl_context=ssl_context
   )
   ```

## Authentication Problems

### Invalid Credentials

**Symptoms:**
- `AuthenticationError` or `UnauthorizedError`
- 401/403 HTTP status codes
- "Invalid token" error messages

**Solutions:**

1. **Verify credentials:**
   ```python
   from spacetimedb_sdk.auth import AuthenticationProvider
   
   auth_provider = AuthenticationProvider()
   
   # Check if token is valid
   if not auth_provider.validate_token(token):
       # Refresh token or re-authenticate
       new_token = await auth_provider.refresh_token(refresh_token)
   ```

2. **Check token expiration:**
   ```python
   import jwt
   import time
   
   def is_token_expired(token):
       try:
           payload = jwt.decode(token, options={"verify_signature": False})
           exp = payload.get('exp')
           return exp and time.time() > exp
       except jwt.InvalidTokenError:
           return True
   
   if is_token_expired(token):
       # Token expired, need to refresh
       pass
   ```

3. **Implement token refresh:**
   ```python
   from spacetimedb_sdk.auth import TokenManager
   
   token_manager = TokenManager()
   
   # Automatic token refresh
   token_manager.enable_auto_refresh(
       refresh_callback=your_refresh_function,
       refresh_threshold=300  # Refresh 5 minutes before expiry
   )
   ```

### Permission Denied

**Symptoms:**
- Operations fail with permission errors
- Access denied to certain resources

**Solutions:**

1. **Check user permissions:**
   ```python
   # Verify user has required permissions
   permissions = await client.get_user_permissions()
   if 'write' not in permissions:
       raise PermissionError("Write permission required")
   ```

2. **Use proper authentication scope:**
   ```python
   # Ensure authentication includes required scopes
   auth_provider.authenticate(
       username=username,
       password=password,
       scopes=['read', 'write', 'admin']
   )
   ```

## Performance Issues

### Slow Query Performance

**Symptoms:**
- Long response times
- Timeouts on queries
- High CPU usage

**Solutions:**

1. **Enable query caching:**
   ```python
   from spacetimedb_sdk.bounded_cache import BoundedCache
   
   query_cache = BoundedCache(max_size=1000)
   
   async def cached_query(query, params):
       cache_key = f"{query}:{hash(str(params))}"
       
       if cache_key in query_cache:
           return query_cache.get(cache_key)
       
       result = await client.query(query, params)
       query_cache.put(cache_key, result)
       return result
   ```

2. **Use batch operations:**
   ```python
   # Instead of individual queries
   results = []
   for item in items:
       result = await client.query(f"SELECT * FROM table WHERE id = {item.id}")
       results.append(result)
   
   # Use batch query
   ids = [item.id for item in items]
   results = await client.batch_query(
       "SELECT * FROM table WHERE id IN (?)",
       [ids]
   )
   ```

3. **Optimize connection pool:**
   ```python
   # Monitor pool utilization
   pool_stats = pool.get_statistics()
   if pool_stats['utilization'] > 0.8:
       # Increase pool size
       pool.resize(max_size=pool.max_size * 2)
   ```

### Memory Leaks

**Symptoms:**
- Continuously increasing memory usage
- Out of memory errors
- Slow garbage collection

**Solutions:**

1. **Use bounded collections:**
   ```python
   from spacetimedb_sdk.bounded_client_cache import BoundedClientCache
   
   # Replace unbounded cache
   cache = BoundedClientCache(
       max_size=10000,
       ttl=3600,  # 1 hour TTL
       eviction_policy='lru'
   )
   ```

2. **Implement proper cleanup:**
   ```python
   from contextlib import asynccontextmanager
   
   @asynccontextmanager
   async def managed_client():
       client = SpacetimeDBClient(url)
       try:
           await client.connect()
           yield client
       finally:
           await client.close()
   
   async with managed_client() as client:
       # Use client
       pass
   ```

3. **Monitor memory usage:**
   ```python
   import psutil
   import gc
   
   def check_memory_usage():
       process = psutil.Process()
       memory_info = process.memory_info()
       
       print(f"RSS: {memory_info.rss / 1024 / 1024:.1f} MB")
       print(f"VMS: {memory_info.vms / 1024 / 1024:.1f} MB")
       print(f"Objects: {len(gc.get_objects())}")
   
   # Call periodically
   check_memory_usage()
   ```

## Error Messages

### Common Error Messages and Solutions

#### "Connection timeout"
```
ConnectionTimeoutError: Connection attempt timed out after 30 seconds
```

**Solution:**
```python
# Increase connection timeout
client = SpacetimeDBClient(
    url="ws://localhost:3000",
    connection_timeout=60.0  # 60 seconds
)
```

#### "Protocol version mismatch"
```
ProtocolError: Protocol version mismatch: client=1.0, server=2.0
```

**Solution:**
```python
# Update SDK or specify protocol version
client = SpacetimeDBClient(
    url="ws://localhost:3000",
    protocol_version="2.0"
)
```

#### "Maximum connections exceeded"
```
ConnectionPoolError: Maximum connections exceeded (20/20)
```

**Solution:**
```python
# Increase pool size or implement connection sharing
pool = ConnectionPool(
    url="ws://localhost:3000",
    max_size=50  # Increase from default
)
```

#### "Invalid message format"
```
MessageError: Invalid message format: expected binary, got text
```

**Solution:**
```python
# Ensure proper message encoding
client = SpacetimeDBClient(
    url="ws://localhost:3000",
    message_format="binary"  # or "text"
)
```

#### "Subscription limit exceeded"
```
SubscriptionError: Maximum subscriptions exceeded (100/100)
```

**Solution:**
```python
# Clean up unused subscriptions
await client.unsubscribe_all()

# Or increase subscription limit
client.set_subscription_limit(200)
```

## Debug Logging

### Enable Debug Logging

```python
import logging

# Enable debug logging for the SDK
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable specific logger
logger = logging.getLogger('spacetimedb_sdk')
logger.setLevel(logging.DEBUG)

# Add handler for file logging
file_handler = logging.FileHandler('spacetimedb_debug.log')
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
```

### Structured Logging

```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Use structured logging
logger.info("Connection established", 
           connection_id="conn_123",
           database_url="ws://localhost:3000")
```

### Custom Debug Tools

```python
class DebugClient:
    def __init__(self, client):
        self.client = client
        self.request_count = 0
        self.error_count = 0
    
    async def debug_query(self, query, params=None):
        self.request_count += 1
        start_time = time.time()
        
        try:
            result = await self.client.query(query, params)
            duration = time.time() - start_time
            
            print(f"Query #{self.request_count}: {duration:.3f}s")
            print(f"  Query: {query}")
            print(f"  Params: {params}")
            print(f"  Result count: {len(result) if result else 0}")
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"Query #{self.request_count} FAILED: {e}")
            raise
    
    def get_stats(self):
        return {
            'requests': self.request_count,
            'errors': self.error_count,
            'error_rate': self.error_count / self.request_count if self.request_count > 0 else 0
        }

# Usage
debug_client = DebugClient(client)
result = await debug_client.debug_query("SELECT * FROM users WHERE id = ?", [user_id])
```

## Memory Issues

### Diagnosing Memory Problems

```python
import gc
import tracemalloc

# Enable memory tracing
tracemalloc.start()

# Your application code here
# ...

# Get memory statistics
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")

# Get top memory consumers
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("Top 10 memory consumers:")
for stat in top_stats[:10]:
    print(f"{stat.traceback.format()[-1]}: {stat.size / 1024:.1f} KB")

tracemalloc.stop()
```

### Memory Leak Detection

```python
import weakref
from collections import defaultdict

class MemoryTracker:
    def __init__(self):
        self.references = defaultdict(list)
    
    def track_object(self, obj, name=None):
        name = name or obj.__class__.__name__
        ref = weakref.ref(obj, lambda x: self.references[name].remove(x))
        self.references[name].append(ref)
    
    def get_alive_objects(self):
        alive = {}
        for name, refs in self.references.items():
            alive[name] = len([r for r in refs if r() is not None])
        return alive
    
    def print_stats(self):
        alive = self.get_alive_objects()
        print("Alive objects:")
        for name, count in alive.items():
            print(f"  {name}: {count}")

# Usage
tracker = MemoryTracker()

# Track objects
connection = SpacetimeDBClient(url)
tracker.track_object(connection, "SpacetimeDBClient")

# Check for leaks
tracker.print_stats()
```

## Threading Issues

### Thread Safety Problems

**Symptoms:**
- Race conditions
- Deadlocks
- Inconsistent state

**Solutions:**

1. **Use thread-safe collections:**
   ```python
   import threading
   from queue import Queue
   
   # Thread-safe queue for communication
   message_queue = Queue()
   
   # Thread-safe connection pool
   pool_lock = threading.Lock()
   
   def get_connection():
       with pool_lock:
           return pool.acquire()
   ```

2. **Proper async/await usage:**
   ```python
   import asyncio
   
   # Don't mix sync and async code
   async def async_function():
       # Use await for async operations
       result = await client.query("SELECT * FROM users")
       return result
   
   # Run async code properly
   result = asyncio.run(async_function())
   ```

3. **Use asyncio locks:**
   ```python
   import asyncio
   
   lock = asyncio.Lock()
   
   async def synchronized_operation():
       async with lock:
           # Critical section
           result = await client.query("SELECT * FROM users")
           return result
   ```

## Installation Problems

### Common Installation Issues

1. **Missing dependencies:**
   ```bash
   pip install spacetimedb-sdk[all]  # Install all optional dependencies
   ```

2. **Version conflicts:**
   ```bash
   pip install --upgrade spacetimedb-sdk
   pip check  # Check for dependency conflicts
   ```

3. **Python version issues:**
   ```bash
   python --version  # Check Python version
   # SDK requires Python 3.7+
   ```

4. **Virtual environment problems:**
   ```bash
   # Create fresh virtual environment
   python -m venv spacetimedb_env
   source spacetimedb_env/bin/activate  # Linux/Mac
   # or
   spacetimedb_env\Scripts\activate  # Windows
   
   pip install spacetimedb-sdk
   ```

### Verify Installation

```python
# Test basic functionality
import spacetimedb_sdk

print(f"SDK Version: {spacetimedb_sdk.__version__}")

# Test imports
from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.auth import AuthenticationProvider
from spacetimedb_sdk.bounded_cache import BoundedCache

print("All imports successful!")

# Test basic client creation
client = SpacetimeDBClient("ws://localhost:3000")
print("Client created successfully!")
```

## Getting Help

If you're still experiencing issues:

1. **Check the logs:** Enable debug logging and examine the output
2. **Review configuration:** Verify all configuration parameters
3. **Test in isolation:** Create a minimal reproduction case
4. **Check network:** Use tools like `curl` or `telnet` to test connectivity
5. **Update SDK:** Ensure you're using the latest version
6. **Report issues:** Create an issue with detailed information including:
   - SDK version
   - Python version
   - Operating system
   - Full error traceback
   - Minimal reproduction code

Remember to sanitize any sensitive information (credentials, URLs) before sharing logs or code examples.