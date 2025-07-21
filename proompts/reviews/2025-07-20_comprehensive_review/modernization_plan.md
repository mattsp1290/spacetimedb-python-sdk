# SpacetimeDB Python SDK - Modernization Plan
## Step-by-Step Consolidation Strategy

**Plan Date:** July 20, 2025  
**Estimated Timeline:** 8 weeks  
**Team Size:** 2-3 Senior Python Developers  

---

## Overview

This modernization plan provides a **systematic approach** to consolidating duplicate implementations and establishing modern versions as the canonical way to use each feature. The strategy prioritizes **security fixes** first, followed by **high-impact consolidations** to minimize disruption while maximizing benefits.

---

## Phase 1: Critical Security & Performance Fixes
**Timeline:** Weeks 1-2  
**Priority:** CRITICAL - Blocking for production

### Week 1: Security Hardening

#### **1.1 JSON Deserialization Security**
**Files to modify:**
- `src/spacetimedb_sdk/protocol.py:878`
- `src/spacetimedb_sdk/energy.py:139,233,318,321`
- `src/spacetimedb_sdk/websocket_client.py:1194-1199`

**Implementation:**
```python
# Create new module: src/spacetimedb_sdk/security/json_validator.py
import json
from typing import Any, Dict, Union

MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DEPTH = 100

class JSONSecurityError(Exception):
    pass

def safe_json_loads(data: str, max_size: int = MAX_JSON_SIZE) -> Union[Dict, List]:
    """Securely parse JSON with size and depth limits."""
    if len(data) > max_size:
        raise JSONSecurityError(f"JSON payload too large: {len(data)} > {max_size}")
    
    def depth_counter(obj, depth=0):
        if depth > MAX_DEPTH:
            raise JSONSecurityError(f"JSON nesting too deep: {depth} > {MAX_DEPTH}")
        return obj
    
    try:
        return json.loads(data, object_hook=lambda x: depth_counter(x, 0))
    except json.JSONDecodeError as e:
        raise JSONSecurityError(f"Invalid JSON: {e}")
```

**Migration Steps:**
1. Create `security/json_validator.py` module
2. Replace all `json.loads()` calls with `safe_json_loads()`
3. Add comprehensive tests for JSON bomb protection
4. Update documentation with security best practices

#### **1.2 Path Traversal Protection**
**File:** `src/spacetimedb_sdk/websocket_client.py:734-741`

**Current vulnerable code:**
```python
if '../' in validated_db_identifier or '..\\' in validated_db_identifier:
    raise ValidationError("Path traversal attempt in database identifier")
```

**Secure implementation:**
```python
import os
from pathlib import Path

def validate_database_identifier(identifier: str) -> str:
    """Securely validate database identifier against path traversal."""
    # Normalize path and check for escaping parent directory
    normalized = os.path.normpath(identifier)
    if normalized.startswith('..') or '/' in normalized or '\\' in normalized:
        raise ValidationError(f"Invalid database identifier: {identifier}")
    
    # Additional checks for common injection patterns
    forbidden_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
    if any(char in identifier for char in forbidden_chars):
        raise ValidationError(f"Database identifier contains forbidden characters: {identifier}")
    
    return identifier
```

#### **1.3 Exception Handling Security**
**Files to fix:**
- `src/spacetimedb_sdk/base_objects.py:228`
- `src/spacetimedb_sdk/connection_pool.py:114,127,164`
- `src/spacetimedb_sdk/websocket_client.py:1498-1511`

**Pattern to eliminate:**
```python
# BAD - Security risk
try:
    sensitive_operation()
except Exception:  # Too broad!
    pass  # Swallows all errors including security issues
```

**Secure pattern:**
```python
# GOOD - Specific exception handling
try:
    sensitive_operation()
except (ConnectionError, TimeoutError) as e:
    logger.warning(f"Connection issue: {e}")
    raise ConnectionFailedException(f"Failed to connect: {e}")
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    raise  # Re-raise validation errors
except Exception as e:
    logger.critical(f"Unexpected error in sensitive operation: {e}")
    raise UnexpectedError(f"Internal error: {type(e).__name__}")
```

### Week 2: Performance Optimization

#### **2.1 Fix O(n²) Connection Pool Operations**
**File:** `src/spacetimedb_sdk/connection_pool.py:400-410`

**Current O(n²) implementation:**
```python
while True:  # O(n) loop
    conn_id = self.connection_order[self.current_index]
    # Linear search through connections - O(n²) in aggregate
    if conn_id in self.connections and self.connections[conn_id].is_healthy():
        return self.connections[conn_id]
```

**Optimized O(1) implementation:**
```python
# Pre-compute healthy connections in O(1) lookup
def _update_healthy_connections(self):
    """Maintain O(1) lookup of healthy connections."""
    self._healthy_connections = {
        conn_id: conn for conn_id, conn in self.connections.items()
        if conn.is_healthy()
    }

def get_connection(self) -> PooledConnection:
    """Get connection in O(1) time."""
    if not self._healthy_connections:
        self._update_healthy_connections()
    
    # Round-robin through healthy connections only
    conn_id = next(iter(self._healthy_connections))
    return self._healthy_connections[conn_id]
```

#### **2.2 Fix Memory Leaks in Request Tracking**
**File:** `src/spacetimedb_sdk/websocket_client.py:377-384`

**Current unbounded dictionaries:**
```python
self.pending_requests = {}  # Unbounded - memory leak
self.response_futures = {}  # Unbounded - memory leak
```

**Bounded implementation:**
```python
from collections import OrderedDict
from typing import Optional

class BoundedRequestTracker:
    """Memory-bounded request tracking with automatic cleanup."""
    
    def __init__(self, max_size: int = 10000, cleanup_interval: int = 300):
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        self.pending_requests: OrderedDict = OrderedDict()
        self.response_futures: OrderedDict = OrderedDict()
        self._last_cleanup = time.time()
    
    def add_request(self, request_id: str, future: Future):
        """Add request with automatic cleanup."""
        self._cleanup_if_needed()
        
        if len(self.pending_requests) >= self.max_size:
            # Remove oldest requests to prevent memory exhaustion
            old_id, old_future = self.pending_requests.popitem(last=False)
            old_future.cancel()
            logger.warning(f"Removed old request due to memory limit: {old_id}")
        
        self.pending_requests[request_id] = future
        self.response_futures[request_id] = future
```

---

## Phase 2: Authentication System Consolidation
**Timeline:** Weeks 3-4  
**Priority:** HIGH - Eliminates confusion and security risks

### Week 3: Authentication Migration Preparation

#### **3.1 Create Migration Utilities**
**New file:** `src/spacetimedb_sdk/auth/migration_tools.py`

```python
import warnings
from typing import Optional, Dict, Any
from .storage import SecureAuthStorage, AuthCredentials

class AuthenticationMigrator:
    """Handles migration from legacy auth storage to modern secure storage."""
    
    @staticmethod
    def migrate_from_legacy(legacy_storage_path: Optional[str] = None) -> bool:
        """Migrate credentials from legacy auth storage."""
        try:
            # Import legacy storage temporarily for migration
            from ..auth_storage_original import AuthCredentials as LegacyCredentials
            
            # Read legacy credentials
            legacy_creds = LegacyCredentials.load(legacy_storage_path)
            if not legacy_creds:
                return False
            
            # Convert to secure storage
            secure_storage = SecureAuthStorage()
            secure_creds = AuthCredentials(
                identity=legacy_creds.identity,
                token=legacy_creds.token,
                host=legacy_creds.host
            )
            
            secure_storage.store_credentials(secure_creds)
            logger.info("Successfully migrated credentials to secure storage")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate credentials: {e}")
            return False

def deprecation_warning(old_module: str, new_module: str):
    """Emit deprecation warning for old auth storage usage."""
    warnings.warn(
        f"{old_module} is deprecated and will be removed in v2.0. "
        f"Use {new_module} instead. "
        f"See migration guide: https://docs.spacetimedb.com/python-sdk/auth-migration",
        DeprecationWarning,
        stacklevel=3
    )
```

#### **3.2 Update Import Deprecation Warnings**
**Files to modify:**
- `src/spacetimedb_sdk/auth_storage.py`
- `src/spacetimedb_sdk/auth_storage_deprecated.py`

**Enhanced deprecation pattern:**
```python
# auth_storage.py (temporary wrapper)
import warnings
from .auth.storage import SecureAuthStorage, AuthCredentials
from .auth.migration_tools import deprecation_warning, AuthenticationMigrator

# Emit deprecation warning
deprecation_warning("spacetimedb_sdk.auth_storage", "spacetimedb_sdk.auth.storage")

# Auto-migrate if possible
try:
    AuthenticationMigrator.migrate_from_legacy()
except Exception:
    pass  # Migration fails silently, user gets deprecation warning

# Export modern classes with deprecation warnings
class DeprecatedAuthCredentials(AuthCredentials):
    def __init__(self, *args, **kwargs):
        deprecation_warning("AuthCredentials from auth_storage", "AuthCredentials from auth.storage")
        super().__init__(*args, **kwargs)

# Preserve public API during transition
__all__ = ['DeprecatedAuthCredentials', 'SecureAuthStorage']
```

### Week 4: Authentication Consolidation

#### **4.1 Update All Import Statements**
**Files requiring import updates:**

1. **`src/spacetimedb_sdk/__init__.py`**
   ```python
   # OLD
   from .auth_storage import AuthCredentials
   
   # NEW
   from .auth.storage import AuthCredentials
   ```

2. **`src/spacetimedb_sdk/websocket_client.py`**
   ```python
   # OLD
   from .auth_storage import AuthCredentials
   
   # NEW
   from .auth.storage import AuthCredentials
   ```

3. **`src/spacetimedb_sdk/connection/authentication_handler.py`**
   ```python
   # OLD
   try:
       from ..auth_storage import AuthCredentials
   except ImportError:
       from ..auth.storage import AuthCredentials
   
   # NEW
   from ..auth.storage import AuthCredentials
   ```

#### **4.2 Remove Deprecated Files**
**Files to delete (after migration period):**
- `src/spacetimedb_sdk/auth_storage.py`
- `src/spacetimedb_sdk/auth_storage_deprecated.py`
- `src/spacetimedb_sdk/auth_storage_original.py`

**Migration verification script:**
```python
# scripts/verify_auth_migration.py
def verify_no_deprecated_imports():
    """Verify no code imports from deprecated auth modules."""
    deprecated_modules = [
        'auth_storage',
        'auth_storage_deprecated', 
        'auth_storage_original'
    ]
    
    issues = []
    for py_file in glob.glob('src/**/*.py', recursive=True):
        with open(py_file) as f:
            content = f.read()
            for module in deprecated_modules:
                if f'from .{module}' in content or f'import {module}' in content:
                    issues.append(f"{py_file} still imports {module}")
    
    return issues
```

---

## Phase 3: Event System Unification
**Timeline:** Weeks 5-6  
**Priority:** HIGH - Reduces API confusion and maintenance burden

### Week 5: Event System Migration

#### **5.1 Create Compatibility Layer**
**Enhanced file:** `src/spacetimedb_sdk/events/legacy_compat.py`

```python
"""Legacy event system compatibility layer."""
import warnings
from typing import Any, Callable, Dict, Union
from .core_events import Event, EventType, EventPriority
from .event_manager import UnifiedEventManager

class LegacyEventEmitter:
    """Compatibility wrapper for old EventEmitter API."""
    
    def __init__(self):
        warnings.warn(
            "EventEmitter is deprecated. Use UnifiedEventManager from events.event_manager",
            DeprecationWarning,
            stacklevel=2
        )
        self._unified_manager = UnifiedEventManager()
    
    def emit(self, event_type: str, data: Any = None):
        """Legacy emit method - converts to unified event format."""
        # Convert string event type to modern EventType enum
        try:
            modern_event_type = EventType[event_type.upper()]
        except KeyError:
            modern_event_type = EventType.CUSTOM
        
        event = Event(
            type=modern_event_type,
            data=data,
            priority=EventPriority.NORMAL
        )
        self._unified_manager.emit_event(event)

class LegacySDKEventManager:
    """Compatibility wrapper for old SDKEventManager."""
    
    def __init__(self):
        warnings.warn(
            "SDKEventManager is deprecated. Use UnifiedEventManager from events.event_manager",
            DeprecationWarning,
            stacklevel=2
        )
        self._unified_manager = UnifiedEventManager()
    
    def register_handler(self, event_type: str, handler: Callable):
        """Legacy handler registration."""
        try:
            modern_event_type = EventType[event_type.upper()]
        except KeyError:
            modern_event_type = EventType.CUSTOM
        
        self._unified_manager.register_handler(modern_event_type, handler)
```

#### **5.2 Update Core Import Patterns**
**File:** `src/spacetimedb_sdk/__init__.py`

```python
# NEW unified event system imports
from .events.event_manager import UnifiedEventManager as EventManager
from .events.core_events import Event, EventType, EventPriority
from .events.enhanced_event_system import EnhancedEventManager

# Legacy compatibility (with deprecation warnings)
from .events.legacy_compat import LegacyEventEmitter as EventEmitter
from .events.legacy_compat import LegacySDKEventManager as SDKEventManager

# Update __all__ to guide users to modern APIs
__all__ = [
    # Modern event system (recommended)
    'EventManager',
    'Event', 
    'EventType',
    'EventPriority',
    'EnhancedEventManager',
    
    # Legacy compatibility (deprecated)
    'EventEmitter',  # Use EventManager instead
    'SDKEventManager',  # Use EventManager instead
]
```

### Week 6: Event System Cleanup

#### **6.1 Remove Root-Level Event Files**
**Files to delete:**
- `src/spacetimedb_sdk/event_system.py`
- `src/spacetimedb_sdk/event_manager.py`

#### **6.2 Update All Event System Users**
**Files requiring updates:**

1. **`src/spacetimedb_sdk/websocket_client.py`**
   ```python
   # OLD
   from .event_system import EventEmitter, EventType
   
   # NEW
   from .events.event_manager import UnifiedEventManager
   from .events.core_events import EventType
   ```

2. **`src/spacetimedb_sdk/spacetimedb_client.py`**
   ```python
   # OLD
   from .event_manager import SDKEventManager
   
   # NEW
   from .events.event_manager import UnifiedEventManager
   ```

---

## Phase 4: Connection & Subscription Management
**Timeline:** Weeks 7-8  
**Priority:** MEDIUM - Architecture improvement and performance

### Week 7: Subscription Manager Consolidation

#### **7.1 Merge Subscription Functionality**
**Target:** Consolidate into `src/spacetimedb_sdk/connection/subscription_manager.py`

**Enhanced subscription manager:**
```python
class ConsolidatedSubscriptionManager:
    """Unified subscription manager combining all previous functionality."""
    
    def __init__(self, 
                 query_id_support: bool = True,
                 memory_bounded: bool = True,
                 metrics_enabled: bool = True):
        # Combine features from both implementations
        self.query_id_support = query_id_support  # From connection/ version
        self.memory_bounded = memory_bounded      # From connection/ version
        self.metrics_enabled = metrics_enabled    # From connection/ version
        
        # Basic state management from root version
        self.subscriptions: Dict[str, SubscriptionState] = {}
        
        # Enhanced features from connection version
        if memory_bounded:
            self.subscription_queries = BoundedDict(max_size=10000)
        else:
            self.subscription_queries = {}
        
        if metrics_enabled:
            self.metrics = SubscriptionMetrics()
```

#### **7.2 Remove Root-Level Subscription Manager**
**File to delete:** `src/spacetimedb_sdk/subscription_manager.py`

**Update imports across codebase:**
```python
# OLD
from .subscription_manager import SubscriptionManager

# NEW
from .connection.subscription_manager import SubscriptionManager
```

### Week 8: WebSocket Client Refactoring

#### **8.1 Split WebSocketClient Responsibilities**
**Current:** 2,179 lines, 6+ responsibilities  
**Target:** 4-5 focused classes

**New architecture:**
```python
# src/spacetimedb_sdk/connection/connection_manager.py
class ConnectionManager:
    """Handles WebSocket connection lifecycle."""
    def connect(self, url: str) -> bool: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...

# src/spacetimedb_sdk/connection/protocol_handler.py
class ProtocolHandler:
    """Handles message encoding/decoding and protocol logic."""
    def encode_message(self, message: Any) -> bytes: ...
    def decode_message(self, data: bytes) -> Any: ...

# src/spacetimedb_sdk/connection/compression_manager.py
class CompressionManager:
    """Handles message compression/decompression."""
    def compress(self, data: bytes) -> bytes: ...
    def decompress(self, data: bytes) -> bytes: ...

# src/spacetimedb_sdk/connection/auth_manager.py
class AuthenticationManager:
    """Handles authentication flow and token management."""
    def authenticate(self, credentials: AuthCredentials) -> bool: ...
    def refresh_token(self) -> bool: ...

# src/spacetimedb_sdk/websocket_client.py (refactored)
class WebSocketClient:
    """Coordinates connection, protocol, compression, and auth."""
    def __init__(self):
        self.connection = ConnectionManager()
        self.protocol = ProtocolHandler()
        self.compression = CompressionManager()
        self.auth = AuthenticationManager()
```

---

## Breaking Changes & Migration Guide

### **Breaking Changes by Phase**

#### **Phase 1: Security (Non-Breaking)**
- ✅ **No breaking changes** - Only internal security improvements
- JSON parsing becomes more strict (may reject previously accepted malformed JSON)

#### **Phase 2: Authentication (Breaking)**
- 🚨 **Import path changes:**
  ```python
  # OLD (will break)
  from spacetimedb_sdk.auth_storage import AuthCredentials
  
  # NEW (required)
  from spacetimedb_sdk.auth.storage import AuthCredentials
  ```

#### **Phase 3: Event System (Breaking)**
- 🚨 **Class name changes:**
  ```python
  # OLD (will break)
  from spacetimedb_sdk import EventEmitter, SDKEventManager
  
  # NEW (required)
  from spacetimedb_sdk import EventManager  # Unified
  from spacetimedb_sdk.events import UnifiedEventManager  # Direct
  ```

#### **Phase 4: Connection (Breaking)**
- 🚨 **Import path changes:**
  ```python
  # OLD (will break)
  from spacetimedb_sdk.subscription_manager import SubscriptionManager
  
  # NEW (required)
  from spacetimedb_sdk.connection.subscription_manager import SubscriptionManager
  ```

### **Migration Timeline**

```
Phase 1-2:  Deprecation warnings issued
Phase 3:    Compatibility layer provided (6 months)
Phase 4:    Legacy support removed
Version 2.0: Clean modern API only
```

### **User Migration Steps**

1. **Immediate (Phase 1-2):**
   - Update authentication imports
   - Test with deprecation warnings enabled
   - Run migration verification script

2. **Phase 3 (Event System):**
   - Replace old event classes with unified system
   - Use compatibility layer during transition
   - Update event handling code

3. **Phase 4 (Final):**
   - Update connection imports
   - Test with new WebSocket client architecture
   - Remove any legacy compatibility code

---

## Risk Management

### **Mitigation Strategies**

1. **Compatibility Layers:** Provide 6-month transition period
2. **Comprehensive Testing:** 95%+ test coverage for all changes
3. **Documentation:** Clear migration guides with code examples
4. **Gradual Rollout:** Phase-by-phase implementation reduces risk
5. **Rollback Plan:** Each phase can be reverted independently

### **Success Metrics**

- **Security:** Zero critical vulnerabilities in security audit
- **Performance:** 10x improvement in connection pool operations
- **Code Quality:** 50% reduction in duplicate code
- **Developer Experience:** Clear, consistent API with single import paths

This modernization plan transforms the SpacetimeDB Python SDK from a fragmented codebase with security risks into a unified, secure, and performant SDK ready for production use.