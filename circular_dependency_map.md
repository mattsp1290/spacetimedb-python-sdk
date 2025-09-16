# Circular Dependency Analysis Report

## Identified Circular Import Chain

The following circular dependency exists in the SpacetimeDB Python SDK:

```
spacetimedb_client.py
    ↓ imports websocket_client
websocket_client.py  
    ↓ imports auth.authentication_manager
auth/authentication_manager.py
    ↓ imports connection.authentication_handler
connection/__init__.py
    ↓ imports enhanced_connection_manager  
connection/enhanced_connection_manager.py
    ↓ imports factory.base
factory/__init__.py
    ↓ imports factory.base
factory/base.py
    ↓ imports spacetimedb_client ← CIRCULAR DEPENDENCY!
```

## Root Cause Analysis

The circular dependency is caused by:

1. **Tight Coupling**: The factory pattern tries to create `SpacetimeDBClient` instances but imports the concrete class directly
2. **Layering Violation**: Lower-level modules (factory, connection, auth) depend on higher-level modules (client)
3. **Missing Abstractions**: No interfaces or abstract base classes to break dependencies

## Dependency Injection Solution

### Phase 1: Create Abstract Interfaces

Create interface definitions that break the direct dependencies:

1. `interfaces/client_interface.py` - Define `ClientInterface` protocol
2. `interfaces/factory_interface.py` - Define `FactoryInterface` protocol  
3. `interfaces/connection_interface.py` - Define `ConnectionInterface` protocol
4. `interfaces/auth_interface.py` - Define `AuthInterface` protocol

### Phase 2: Implement Dependency Injection

1. **Factory Pattern**: Use abstract factory interfaces instead of concrete classes
2. **Constructor Injection**: Pass dependencies via constructors rather than importing
3. **Late Binding**: Use lazy imports and forward references where needed
4. **Registry Pattern**: Create a dependency registry for service location

### Phase 3: Module Restructuring

1. Move shared types to `shared_types.py` 
2. Create `dependency_injection.py` module with IoC container
3. Update modules to use injected dependencies

## Implementation Strategy

1. **Backwards Compatibility**: Ensure all existing functionality continues working
2. **Gradual Migration**: Break the circular dependency incrementally
3. **Interface Segregation**: Create minimal, focused interfaces
4. **Dependency Inversion**: Depend on abstractions, not concretions

## Critical Files to Modify

1. `factory/base.py` - Remove direct import of SpacetimeDBClient
2. `connection/enhanced_connection_manager.py` - Use interface instead of concrete factory
3. `auth/authentication_manager.py` - Use injected dependencies  
4. `websocket_client.py` - Use injected auth manager
5. `spacetimedb_client.py` - Implement dependency injection pattern

## Success Criteria

- [ ] All modules can be imported without circular dependency errors
- [ ] All existing functionality continues to work exactly as before
- [ ] Module dependencies follow proper layering (high-level → low-level)
- [ ] Code is more testable with dependency injection
- [ ] Performance impact is minimal