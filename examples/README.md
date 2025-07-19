# SpacetimeDB Python SDK - Examples

This directory contains comprehensive examples and usage patterns for the SpacetimeDB Python SDK. The examples are organized by category and demonstrate best practices for different use cases.

## 📁 Directory Structure

```
examples/
├── authentication/          # Authentication and security examples
│   ├── basic_auth_example.py
│   ├── jwt_token_management.py
│   └── credential_migration.py
├── connection_pooling/       # Connection management examples
│   ├── multi_database_example.py
│   └── pool_optimization.py
├── event_system/            # Event handling examples
│   ├── unified_events_example.py
│   ├── custom_event_handlers.py
│   └── event_filtering.py
├── performance/             # Performance optimization examples
│   ├── memory_optimization.py
│   └── connection_tuning.py
├── security/               # Security best practices
│   ├── secure_credential_storage.py
│   └── input_validation.py
├── migration/              # Migration examples
│   ├── 01_basic_connection_before.py
│   ├── 01_basic_connection_after.py
│   ├── 02_event_handling_before.py
│   ├── 02_event_handling_after.py
│   └── 03_advanced_features_example.py
└── quickstart/             # Quick start examples
    ├── client/
    │   ├── main.py
    │   └── main_v112.py
    └── server/
```

## 🚀 Quick Start

### Basic Usage

```python
import asyncio
from spacetimedb_sdk import SpacetimeDBClient

async def main():
    # Connect to SpacetimeDB
    client = SpacetimeDBClient("ws://localhost:3000")
    
    try:
        await client.connect()
        
        # Your code here
        result = await client.query("SELECT * FROM users")
        print(f"Found {len(result)} users")
        
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Running Examples

Each example is self-contained and can be run directly:

```bash
# Run a specific example
python examples/authentication/basic_auth_example.py

# Run with development server
python examples/quickstart/client/main.py

# Run performance optimization example
python examples/performance/memory_optimization.py
```

## 📂 Example Categories

### 🔐 Authentication Examples

**Location**: `examples/authentication/`

These examples demonstrate secure authentication patterns and credential management:

- **`basic_auth_example.py`**: Basic authentication flow with username/password
- **`jwt_token_management.py`**: JWT token handling, refresh, and validation
- **`credential_migration.py`**: Migrating from legacy auth to new system

**Key Features**:
- Secure credential storage
- Automatic token refresh
- Multi-provider authentication
- Audit logging

### 🔗 Connection Pooling Examples

**Location**: `examples/connection_pooling/`

Examples showing efficient connection management for high-performance applications:

- **`multi_database_example.py`**: Managing connections to multiple databases
- **`pool_optimization.py`**: Optimizing pool settings for different workloads

**Key Features**:
- Connection pool configuration
- Load balancing strategies
- Health monitoring
- Performance tuning

### 📡 Event System Examples

**Location**: `examples/event_system/`

Comprehensive examples of the unified event system:

- **`unified_events_example.py`**: Complete event system demonstration
- **`custom_event_handlers.py`**: Custom event handler patterns
- **`event_filtering.py`**: Advanced event filtering techniques

**Key Features**:
- Event registration and handling
- Custom event types
- Event filtering and routing
- Error handling and recovery

### ⚡ Performance Examples

**Location**: `examples/performance/`

Examples focused on optimizing performance and resource usage:

- **`memory_optimization.py`**: Memory management and optimization
- **`connection_tuning.py`**: Connection tuning for different workloads

**Key Features**:
- Memory leak prevention
- Connection optimization
- Performance monitoring
- Resource cleanup

### 🔒 Security Examples

**Location**: `examples/security/`

Security best practices and implementation examples:

- **`secure_credential_storage.py`**: Encrypted credential storage
- **`input_validation.py`**: Input validation and sanitization

**Key Features**:
- Encryption and key management
- Input validation
- SQL injection prevention
- Audit logging

### 🔄 Migration Examples

**Location**: `examples/migration/`

Examples showing how to migrate from older SDK versions:

- **Before/After patterns**: Side-by-side comparison of old vs new APIs
- **Migration utilities**: Tools to help with the transition
- **Compatibility layers**: Maintaining backward compatibility

## 📋 Requirements

### Basic Requirements

```bash
pip install spacetimedb-sdk
```

### Optional Dependencies

For enhanced functionality in some examples:

```bash
# For security examples
pip install cryptography keyring

# For performance monitoring
pip install psutil

# For validation examples
pip install bleach validators marshmallow

# For all features
pip install spacetimedb-sdk[all]
```

## 🛠️ Development Setup

### Setting Up Examples

1. **Clone the repository**:
   ```bash
   git clone https://github.com/spacetimedb/spacetimedb-python-sdk
   cd spacetimedb-python-sdk
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .[dev]
   ```

3. **Start SpacetimeDB server** (for examples that need it):
   ```bash
   # Follow SpacetimeDB installation instructions
   spacetimedb start
   ```

4. **Run examples**:
   ```bash
   python examples/quickstart/client/main.py
   ```

### Example Server Setup

Some examples require a running SpacetimeDB server. See `examples/quickstart/server/` for a basic server setup.

## 📖 Example Details

### Authentication Examples

#### Basic Authentication
```python
from spacetimedb_sdk.auth import AuthenticationProvider

provider = AuthenticationProvider()
result = await provider.authenticate({
    'username': 'your_username',
    'password': 'your_password'
})

if result.success:
    print("Authentication successful!")
```

#### JWT Token Management
```python
from spacetimedb_sdk.auth import TokenManager

token_manager = TokenManager()
token_manager.enable_auto_refresh()

# Token is automatically refreshed before expiry
token = await token_manager.get_current_token()
```

### Connection Pooling Examples

#### Basic Pool Usage
```python
from spacetimedb_sdk import ConnectionPool

pool = ConnectionPool(
    "ws://localhost:3000",
    min_size=5,
    max_size=20
)

async with pool.acquire() as conn:
    result = await conn.query("SELECT * FROM users")
```

#### Pool Optimization
```python
# Optimize for latency-sensitive workloads
pool = ConnectionPool(
    "ws://localhost:3000",
    min_size=10,
    max_size=30,
    connection_timeout=5.0,
    tcp_nodelay=True
)
```

### Event System Examples

#### Event Registration
```python
from spacetimedb_sdk.events import EventManager

@event_manager.on(EventType.ROW_UPDATE)
async def handle_update(event, context):
    print(f"Row updated: {event.data}")

@event_manager.on(EventType.CONNECTED, priority=EventPriority.HIGH)
async def handle_connection(event, context):
    print("Connected to database")
```

#### Custom Event Handlers
```python
class CustomEventHandler:
    def __init__(self):
        self.processed_count = 0
    
    async def handle_event(self, event, context):
        self.processed_count += 1
        # Custom processing logic
```

### Performance Examples

#### Memory Optimization
```python
from spacetimedb_sdk.bounded_cache import BoundedCache

# Use bounded cache to prevent memory leaks
cache = BoundedCache(
    max_size=10000,
    ttl=3600,  # 1 hour TTL
    eviction_policy='lru'
)
```

#### Connection Tuning
```python
# Workload-specific optimization
if workload_type == "high_frequency":
    pool_config = {
        'min_size': 10,
        'max_size': 30,
        'connection_timeout': 5.0,
        'tcp_nodelay': True
    }
```

## 🧪 Testing Examples

### Running Example Tests

```bash
# Run all example tests
pytest examples/

# Run specific example tests
pytest examples/authentication/

# Run with coverage
pytest --cov=examples examples/
```

### Writing Tests for Examples

```python
import pytest
from examples.authentication.basic_auth_example import AuthDemo

@pytest.mark.asyncio
async def test_auth_demo():
    demo = AuthDemo()
    result = await demo.demonstrate_basic_auth()
    assert result is not None
```

## 📝 Best Practices

### Code Organization

1. **Import Structure**: Use absolute imports for SDK components
2. **Error Handling**: Always include comprehensive error handling
3. **Resource Cleanup**: Use context managers for automatic cleanup
4. **Documentation**: Include docstrings and inline comments
5. **Type Hints**: Use type hints for better IDE support

### Example Structure

```python
#!/usr/bin/env python3
"""
Example Title
=============

Brief description of what this example demonstrates.

Key concepts:
- Feature 1
- Feature 2
- Feature 3

Requirements:
- spacetimedb-sdk
- optional-dependency
"""

import asyncio
from spacetimedb_sdk import SpacetimeDBClient

class ExampleDemo:
    """Demonstration class for the example"""
    
    def __init__(self):
        self.client = SpacetimeDBClient("ws://localhost:3000")
    
    async def demonstrate_feature(self):
        """Demonstrate specific feature"""
        pass
    
    async def cleanup(self):
        """Clean up resources"""
        if self.client:
            await self.client.close()

async def main():
    """Main function"""
    demo = ExampleDemo()
    
    try:
        await demo.demonstrate_feature()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await demo.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

### Performance Guidelines

1. **Use Connection Pooling**: Always use connection pools for production
2. **Implement Caching**: Use bounded caches for frequently accessed data
3. **Monitor Resources**: Include resource monitoring in examples
4. **Handle Errors Gracefully**: Implement proper error handling and recovery
5. **Clean Up Resources**: Always clean up connections and resources

## 🔧 Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure SpacetimeDB server is running
2. **Authentication Failures**: Check credentials and server configuration
3. **Memory Issues**: Use bounded collections and proper cleanup
4. **Performance Problems**: Optimize connection pool settings

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run example with debug output
```

### Getting Help

- **Documentation**: Check the main documentation in `/docs/`
- **Issues**: Report issues on GitHub
- **Community**: Join the SpacetimeDB community discussions

## 🤝 Contributing

We welcome contributions to the examples! Here's how to contribute:

1. **Fork the repository**
2. **Create a feature branch**
3. **Add your example** following the established patterns
4. **Include tests** for your example
5. **Update documentation** as needed
6. **Submit a pull request**

### Example Contribution Guidelines

- Follow the existing code style and structure
- Include comprehensive documentation
- Add error handling and resource cleanup
- Write tests for your examples
- Update this README if adding new categories

## 📚 Related Documentation

- [API Reference](../docs/api_reference.md)
- [Best Practices Guide](../docs/best_practices.md)
- [Performance Tuning](../docs/performance_tuning.md)
- [Security Guide](../docs/security_guide.md)
- [Migration Guide](../docs/migration_guide.md)

---

**Happy coding with SpacetimeDB!** 🚀