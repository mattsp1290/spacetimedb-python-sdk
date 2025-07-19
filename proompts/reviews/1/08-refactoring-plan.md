# SpacetimeDB Python SDK - Refactoring Plan

## Overview

This document provides a structured plan for refactoring the SpacetimeDB Python SDK to address the issues identified in the code review while maintaining backward compatibility where possible.

## Refactoring Principles

1. **Incremental Changes**: Small, testable changes that can be reviewed independently
2. **Backward Compatibility**: Maintain existing API where possible, deprecate gradually
3. **Test-Driven**: Write tests before refactoring
4. **Performance First**: Ensure refactoring improves or maintains performance
5. **Security by Design**: Build security into the architecture

## Phase 1: Critical Security Fixes (Week 1-2)

### 1.1 Secure Credential Management

**Current Structure**:
```
auth_storage.py (insecure)
└── store_credentials() → plaintext JSON
```

**Target Structure**:
```
auth/
├── __init__.py
├── storage.py (encrypted storage)
├── providers.py (auth providers)
└── validators.py (token validation)
```

**Migration Steps**:
1. Create new `auth/` package
2. Implement `SecureAuthStorage` class
3. Add migration utility for existing credentials
4. Deprecate old `auth_storage.py`

### 1.2 Input Validation Framework

**New Structure**:
```
validation/
├── __init__.py
├── validators.py (base validators)
├── sql_validator.py (SQL injection prevention)
├── url_validator.py (URL validation)
└── data_validator.py (data size/type validation)
```

**Implementation**:
```python
# validation/validators.py
from abc import ABC, abstractmethod
from typing import Any, TypeVar

T = TypeVar('T')

class Validator(ABC):
    @abstractmethod
    def validate(self, value: Any) -> T:
        """Validate and return sanitized value."""
        pass

class CompositeValidator(Validator):
    def __init__(self, *validators: Validator):
        self.validators = validators
    
    def validate(self, value: Any) -> Any:
        for validator in self.validators:
            value = validator.validate(value)
        return value
```

## Phase 2: Architecture Simplification (Week 3-4)

### 2.1 Split Large Modules

**Current**: `websocket_client.py` (1500+ lines)

**Target Structure**:
```
connection/
├── __init__.py
├── websocket.py (200 lines - pure websocket handling)
├── state_manager.py (150 lines - connection state)
├── message_handler.py (300 lines - message processing)
├── subscription_manager.py (200 lines - subscription logic)
└── auth_handler.py (150 lines - authentication)
```

**Refactoring Strategy**:
```python
# connection/websocket.py
class WebSocketConnection:
    """Pure websocket handling, no business logic."""
    def __init__(self, url: str):
        self.url = url
        self._ws = None
    
    async def connect(self):
        """Establish connection."""
        pass
    
    async def send(self, data: bytes):
        """Send raw data."""
        pass
    
    async def receive(self) -> bytes:
        """Receive raw data."""
        pass

# connection/message_handler.py
class MessageHandler:
    """Handle message processing."""
    def __init__(self, connection: WebSocketConnection):
        self.connection = connection
        self.handlers = {}
    
    def register_handler(self, msg_type: str, handler: Callable):
        """Register message type handler."""
        self.handlers[msg_type] = handler
    
    async def process_message(self, raw_data: bytes):
        """Process incoming message."""
        # Decode, validate, dispatch
        pass
```

### 2.2 Consolidate Event Systems

**Current**: Multiple event systems
- `event_system.py`
- `event_manager.py`
- `events/` package

**Target**: Single, unified event system
```
events/
├── __init__.py
├── core.py (base event system)
├── handlers.py (event handlers)
└── types.py (event type definitions)
```

## Phase 3: Performance Optimization (Month 2)

### 3.1 Connection Pooling

**New Structure**:
```python
# connection/pool.py
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio

@dataclass
class PoolConfig:
    min_size: int = 5
    max_size: int = 20
    max_idle_time: float = 300.0
    health_check_interval: float = 30.0

class ConnectionPool:
    def __init__(self, config: PoolConfig):
        self.config = config
        self._connections: List[PooledConnection] = []
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> PooledConnection:
        """Acquire connection from pool."""
        # Try to get available connection
        # Create new if needed and under limit
        # Wait if at max capacity
        pass
    
    async def release(self, conn: PooledConnection):
        """Return connection to pool."""
        # Validate connection health
        # Return to available queue
        # Or dispose if unhealthy
        pass
```

### 3.2 Message Batching

**Implementation**:
```python
# protocol/batching.py
class MessageBatcher:
    def __init__(
        self, 
        send_func: Callable,
        max_batch_size: int = 100,
        max_wait_ms: int = 10
    ):
        self.send_func = send_func
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self._batch: List[Message] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task = None
    
    async def send(self, message: Message):
        """Add message to batch."""
        async with self._batch_lock:
            self._batch.append(message)
            
            if len(self._batch) >= self.max_batch_size:
                await self._flush()
            elif not self._flush_task:
                self._flush_task = asyncio.create_task(
                    self._delayed_flush()
                )
    
    async def _flush(self):
        """Send batched messages."""
        if not self._batch:
            return
            
        batch = self._batch
        self._batch = []
        
        # Encode as batch message
        batch_msg = BatchMessage(messages=batch)
        await self.send_func(batch_msg)
```

## Phase 4: Testing Infrastructure (Month 2)

### 4.1 Test Framework Setup

**Structure**:
```
tests/
├── conftest.py (pytest configuration)
├── fixtures/
│   ├── __init__.py
│   ├── server_mock.py
│   ├── data_generators.py
│   └── test_utils.py
├── unit/
├── integration/
├── security/
├── performance/
└── e2e/
```

### 4.2 Mock Infrastructure

```python
# tests/fixtures/server_mock.py
class MockSpacetimeDBServer:
    """Comprehensive server mock for testing."""
    
    def __init__(self, port: int = 0):
        self.port = port
        self.app = aiohttp.web.Application()
        self._setup_routes()
        self._connections: Dict[str, WebSocketResponse] = {}
    
    def _setup_routes(self):
        self.app.router.add_get('/v1/database/{db}/subscribe', self.handle_subscribe)
        self.app.router.add_post('/v1/database/{db}/call_reducer', self.handle_reducer)
    
    async def handle_subscribe(self, request):
        """Mock WebSocket subscription endpoint."""
        ws = WebSocketResponse()
        await ws.prepare(request)
        
        # Send initial handshake
        await ws.send_json({
            "InitialConnection": {
                "identity": "test-identity",
                "token": "test-token"
            }
        })
        
        # Handle messages
        async for msg in ws:
            # Process and respond
            pass
        
        return ws
```

## Phase 5: API Modernization (Month 3)

### 5.1 Simplified Client API

**Current**: Multiple ways to create clients
**Target**: Single, clear entry point

```python
# spacetimedb_sdk/client.py
from typing import Optional, Union
from .connection import ConnectionConfig

class SpacetimeDBClient:
    """Unified client interface."""
    
    @classmethod
    def connect(
        cls,
        url: str,
        *,
        auth_token: Optional[str] = None,
        config: Optional[ConnectionConfig] = None
    ) -> 'SpacetimeDBClient':
        """Create and connect client."""
        config = config or ConnectionConfig()
        # Validate URL
        # Setup connection
        # Return connected client
        pass
    
    async def subscribe(self, *queries: str) -> Subscription:
        """Subscribe to queries."""
        pass
    
    async def call_reducer(
        self, 
        name: str, 
        *args, 
        **kwargs
    ) -> ReducerResult:
        """Call a reducer."""
        pass
```

### 5.2 Deprecation Strategy

```python
# Maintain backward compatibility
def create_client(*args, **kwargs):
    warnings.warn(
        "create_client is deprecated, use SpacetimeDBClient.connect()",
        DeprecationWarning,
        stacklevel=2
    )
    return SpacetimeDBClient.connect(*args, **kwargs)
```

## Migration Timeline

### Month 1
- Week 1-2: Security fixes (Phase 1)
- Week 3-4: Architecture simplification (Phase 2)

### Month 2
- Week 1-2: Performance optimization (Phase 3)
- Week 3-4: Testing infrastructure (Phase 4)

### Month 3
- Week 1-2: API modernization (Phase 5)
- Week 3-4: Documentation and examples

## Success Metrics

### Code Quality
- Cyclomatic complexity < 10 per method
- Module size < 500 lines
- Test coverage > 90%
- Zero security vulnerabilities

### Performance
- Message throughput > 10k/sec
- Memory usage < 100MB baseline
- Connection setup < 100ms
- Zero memory leaks

### Maintainability
- Clear module boundaries
- Consistent patterns
- Comprehensive documentation
- Easy onboarding for new developers

## Risk Mitigation

### Backward Compatibility
- Maintain old API with deprecation warnings
- Provide migration guide
- Automated migration tools where possible

### Testing Strategy
- Test each refactoring phase independently
- Maintain integration test suite
- Performance regression tests
- Security validation

### Rollback Plan
- Git branches for each phase
- Feature flags for new implementations
- Gradual rollout to users

---
*This refactoring plan provides a structured approach to improving the SDK while minimizing disruption to existing users.*