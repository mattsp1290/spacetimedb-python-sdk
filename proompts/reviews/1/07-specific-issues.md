# SpacetimeDB Python SDK - Specific Issues and Fixes

## Critical Issues Requiring Immediate Attention

### 1. SQL Injection Vulnerability

**Location**: `websocket_client.py:900-902`
```python
message = OneOffQuery(
    message_id=message_id,
    query_string=query  # Direct user input!
)
```

**Fix**:
```python
# Add query validation
def validate_query(query: str) -> str:
    """Validate and sanitize SQL query."""
    # Implement whitelist of allowed operations
    ALLOWED_PATTERNS = [
        r'^SELECT\s+.*\s+FROM\s+\w+',
        r'^SHOW\s+TABLES',
        # Add other safe patterns
    ]
    
    # Check against whitelist
    if not any(re.match(pattern, query.strip(), re.IGNORECASE) 
              for pattern in ALLOWED_PATTERNS):
        raise ValueError("Query pattern not allowed")
    
    # Additional sanitization
    # Remove comments
    query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
    query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
    
    return query

# Use in one_off_query
def one_off_query(self, query: str) -> OneOffQueryResponse:
    sanitized_query = validate_query(query)
    message = OneOffQuery(
        message_id=message_id,
        query_string=sanitized_query
    )
```

### 2. Credential Storage Security

**Location**: `auth_storage.py`
```python
# Current insecure implementation
def store_credentials(identity, token, host, database):
    # Stores in plaintext!
    config = {
        'identity': identity,
        'token': token,
        'host': host,
        'database': database
    }
    with open(config_file, 'w') as f:
        json.dump(config, f)
```

**Fix**:
```python
import keyring
from cryptography.fernet import Fernet
import os

class SecureAuthStorage:
    def __init__(self):
        # Use system keyring for key storage
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self):
        key = keyring.get_password("spacetimedb", "encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            keyring.set_password("spacetimedb", "encryption_key", key)
        return key.encode()
    
    def store_credentials(self, identity, token, host, database):
        data = json.dumps({
            'identity': identity,
            'token': token,
            'host': host,
            'database': database,
            'timestamp': time.time()  # Add expiration
        })
        
        encrypted = self.cipher.encrypt(data.encode())
        
        # Store encrypted data
        config_dir = os.path.expanduser("~/.spacetimedb")
        os.makedirs(config_dir, mode=0o700, exist_ok=True)
        
        config_file = os.path.join(config_dir, "credentials.enc")
        with open(config_file, 'wb') as f:
            f.write(encrypted)
        
        # Set restrictive permissions
        os.chmod(config_file, 0o600)
```

### 3. Memory Leak in Request Tracking

**Location**: `websocket_client.py:255-256`
```python
self.pending_requests: Dict[int, threading.Event] = {}
self.request_responses: Dict[int, Any] = {}
```

**Fix**:
```python
from collections import OrderedDict
import time

class RequestTracker:
    def __init__(self, max_age_seconds=300, max_size=1000):
        self.pending_requests = OrderedDict()
        self.request_responses = OrderedDict()
        self.request_timestamps = OrderedDict()
        self.max_age_seconds = max_age_seconds
        self.max_size = max_size
        self._lock = threading.RLock()
    
    def add_request(self, request_id: int, event: threading.Event):
        with self._lock:
            # Clean old requests first
            self._cleanup_old_requests()
            
            # Enforce size limit
            while len(self.pending_requests) >= self.max_size:
                # Remove oldest
                oldest_id = next(iter(self.pending_requests))
                self.remove_request(oldest_id)
            
            self.pending_requests[request_id] = event
            self.request_timestamps[request_id] = time.time()
    
    def _cleanup_old_requests(self):
        current_time = time.time()
        expired_ids = [
            rid for rid, timestamp in self.request_timestamps.items()
            if current_time - timestamp > self.max_age_seconds
        ]
        
        for rid in expired_ids:
            self.remove_request(rid)
    
    def remove_request(self, request_id: int):
        with self._lock:
            self.pending_requests.pop(request_id, None)
            self.request_responses.pop(request_id, None)
            self.request_timestamps.pop(request_id, None)
```

### 4. Thread Safety in Subscription Management

**Location**: `websocket_client.py:793-813`
```python
# Current race condition
with self._lock:
    self.active_subscriptions[request_id] = query_id
    self.subscription_queries[query_id] = [query]

# Lock released here - race condition!
self.send_message(message)  # Another thread could modify state
```

**Fix**:
```python
def subscribe(self, queries: List[str]) -> QueryId:
    query_id = QueryId()
    request_id = self._get_next_request_id()
    
    # Prepare message first
    message = Subscribe(
        message_id=request_id,
        query_strings=queries,
        subscribe_call=True
    )
    
    # Hold lock for entire operation
    with self._lock:
        self.active_subscriptions[request_id] = query_id
        self.subscription_queries[query_id] = queries.copy()
        
        # Send while holding lock to ensure atomicity
        try:
            self._send_message_internal(message)
        except Exception as e:
            # Rollback on failure
            self.active_subscriptions.pop(request_id, None)
            self.subscription_queries.pop(query_id, None)
            raise
    
    return query_id

def _send_message_internal(self, message):
    """Internal send that assumes lock is held."""
    # Implementation without acquiring lock
    pass
```

### 5. Resource Cleanup on Disconnect

**Location**: `websocket_client.py:631-635`
```python
current_thread.join(timeout=2.0)
if current_thread.is_alive():
    self.logger.warning(f"Disconnect: connection_thread did NOT stop cleanly.")
    # Thread is leaked here!
```

**Fix**:
```python
import ctypes

class ConnectionManager:
    def __init__(self):
        self._stop_event = threading.Event()
        self._threads = []
    
    def disconnect(self, timeout=5.0):
        # Signal all threads to stop
        self._stop_event.set()
        
        # Close websocket first
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        
        # Wait for threads with timeout
        deadline = time.time() + timeout
        for thread in self._threads:
            remaining = deadline - time.time()
            if remaining > 0:
                thread.join(timeout=remaining)
            
            if thread.is_alive():
                self.logger.warning(f"Thread {thread.name} did not stop cleanly")
                # Force terminate as last resort
                self._force_terminate_thread(thread)
        
        # Clean up resources
        self._cleanup_resources()
    
    def _force_terminate_thread(self, thread):
        """Force terminate a thread (use with caution)."""
        if not thread.is_alive():
            return
            
        # Platform-specific thread termination
        thread_id = thread.ident
        if thread_id is not None:
            # This is dangerous but necessary for cleanup
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread_id), 
                ctypes.py_object(SystemExit)
            )
            if res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_long(thread_id), 0
                )
    
    def _cleanup_resources(self):
        """Clean up all resources."""
        self.active_subscriptions.clear()
        self.pending_requests.clear()
        self.request_responses.clear()
        # Close any open files, connections, etc.
```

### 6. DoS Protection for Large Messages

**Location**: BSATN reader without cumulative limits

**Fix**:
```python
class SecureBsatnReader:
    def __init__(self, buffer, max_total_memory=10 * 1024 * 1024):  # 10MB total
        self.buffer = buffer
        self.max_total_memory = max_total_memory
        self.allocated_memory = 0
        self.max_depth = 100
        self.current_depth = 0
    
    def _allocate_memory(self, size):
        """Track memory allocation."""
        if self.allocated_memory + size > self.max_total_memory:
            raise MemoryError(f"Total memory limit exceeded: {self.max_total_memory}")
        self.allocated_memory += size
        return size
    
    def _enter_nested(self):
        """Track nesting depth."""
        self.current_depth += 1
        if self.current_depth > self.max_depth:
            raise RecursionError(f"Maximum nesting depth exceeded: {self.max_depth}")
    
    def _exit_nested(self):
        """Exit nested structure."""
        self.current_depth -= 1
    
    def read_string(self):
        length = self.read_u32()
        self._allocate_memory(length)  # Track allocation
        
        if length > MAX_STRING_LEN:
            raise ValueError(f"String too large: {length}")
        
        data = self._read_bytes(length)
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError("Invalid UTF-8 in string")
    
    def read_array(self, element_reader):
        self._enter_nested()
        try:
            count = self.read_u32()
            if count > MAX_ARRAY_LEN:
                raise ValueError(f"Array too large: {count}")
            
            # Pre-allocate check
            estimated_size = count * 8  # Minimum 8 bytes per element
            self._allocate_memory(estimated_size)
            
            result = []
            for _ in range(count):
                result.append(element_reader())
            
            return result
        finally:
            self._exit_nested()
```

### 7. Async Context Misuse

**Location**: `websocket_client.py:451-460`
```python
async def _notify_subscription_state_change(self, event_type: str, data: Any) -> None:
    # This is async but never awaited!
    for callback in self._subscription_state_callbacks:
        try:
            callback(event_type, data)
        except Exception as e:
            self.logger.error(f"Error in subscription state callback: {e}")
```

**Fix**:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class EventNotifier:
    def __init__(self):
        self._subscription_state_callbacks = []
        self._async_callbacks = []
        self._executor = ThreadPoolExecutor(max_workers=2)
    
    def add_callback(self, callback, is_async=False):
        if is_async:
            self._async_callbacks.append(callback)
        else:
            self._subscription_state_callbacks.append(callback)
    
    def notify_subscription_state_change(self, event_type: str, data: Any):
        """Synchronous notification."""
        # Handle sync callbacks
        for callback in self._subscription_state_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Error in sync callback: {e}")
        
        # Handle async callbacks in background
        if self._async_callbacks:
            self._executor.submit(self._notify_async, event_type, data)
    
    def _notify_async(self, event_type: str, data: Any):
        """Run async callbacks."""
        asyncio.run(self._run_async_callbacks(event_type, data))
    
    async def _run_async_callbacks(self, event_type: str, data: Any):
        """Execute async callbacks."""
        tasks = []
        for callback in self._async_callbacks:
            task = asyncio.create_task(self._safe_async_callback(callback, event_type, data))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_async_callback(self, callback, event_type, data):
        """Safely execute async callback."""
        try:
            await callback(event_type, data)
        except Exception as e:
            self.logger.error(f"Error in async callback: {e}")
```

## Summary of Fixes Priority

### Week 1 - Critical Security
1. SQL injection prevention
2. Credential encryption
3. Input validation across all user inputs

### Week 2 - Stability
1. Memory leak fixes
2. Thread safety improvements
3. Resource cleanup

### Week 3 - Robustness
1. DoS protection
2. Error handling improvements
3. Async/sync consistency

### Week 4 - Testing
1. Security test suite
2. Stress testing
3. Integration testing

---
*These specific fixes address the most critical issues identified in the code review. Each fix includes both the problem and a concrete solution.*