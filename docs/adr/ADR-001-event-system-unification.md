# ADR-001: Event System Unification

## Status
✅ **ACCEPTED** - Implemented in v1.1.2

## Context

The SpacetimeDB Python SDK previously had multiple incompatible event handling systems:
1. Legacy callback-based system (`spacetimedb_client.py`)
2. Async event handlers (`spacetimedb_async_client.py`)
3. WebSocket-specific event handling (`websocket_client.py`)

This fragmentation led to:
- Inconsistent APIs across different client types
- Difficult testing due to multiple event interfaces
- Code duplication and maintenance overhead
- Poor developer experience when switching between client types

## Decision

We will implement a **unified event system** that consolidates all event handling into a single, coherent interface with the following characteristics:

### Core Components

1. **Unified Event Manager**: Single point of event registration and dispatch
2. **Event Types**: Standardized event type enumeration
3. **Event Context**: Rich context information for each event
4. **Event Filters**: Flexible filtering system for selective event handling
5. **Priority System**: Event priority levels for processing order

### Architecture Design

```python
# Unified interface
@event_manager.on(EventType.ROW_UPDATE)
async def handle_row_update(event: Event, context: EventContext):
    # Handle event
    pass

# With filtering
@event_manager.on(EventType.ROW_UPDATE, filter=lambda e: e.table == 'users')
async def handle_user_updates(event: Event, context: EventContext):
    # Handle user-specific updates
    pass

# With priority
@event_manager.on(EventType.CONNECTED, priority=EventPriority.HIGH)
async def handle_connection(event: Event, context: EventContext):
    # High priority connection handler
    pass
```

### Key Features

1. **Backward Compatibility**: Legacy event handlers continue to work
2. **Async-First**: Native async/await support with sync wrapper
3. **Type Safety**: Strongly typed events with proper annotations
4. **Performance**: Optimized event dispatch with batching support
5. **Extensibility**: Plugin architecture for custom event types

## Rationale

### Benefits

1. **Consistency**: Single API across all client types
2. **Maintainability**: Reduced code duplication and complexity
3. **Performance**: Optimized event dispatch and filtering
4. **Developer Experience**: Better IDE support and documentation
5. **Testing**: Unified testing framework for all event types

### Trade-offs

1. **Migration Effort**: Existing code needs to be updated
2. **Bundle Size**: Slightly larger due to unified system
3. **Learning Curve**: Developers need to learn new API

## Implementation Details

### Event Manager Architecture

```python
class EventManager:
    def __init__(self):
        self.handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self.filters: Dict[str, List[EventFilter]] = defaultdict(list)
        self.middleware: List[EventMiddleware] = []
        self.batch_processor: Optional[BatchProcessor] = None
    
    def on(self, event_type: str, filter: Optional[EventFilter] = None, 
           priority: EventPriority = EventPriority.NORMAL):
        """Register event handler with optional filtering and priority"""
        
    async def emit(self, event: Event, context: Optional[EventContext] = None):
        """Emit event to all registered handlers"""
        
    async def remove_handler(self, event_type: str, handler: EventHandler):
        """Remove specific event handler"""
```

### Event Context

```python
@dataclass
class EventContext:
    timestamp: float
    source: str
    connection_id: str
    user_id: Optional[str]
    request_id: Optional[str]
    metadata: Dict[str, Any]
    priority: EventPriority
    retry_count: int = 0
```

### Migration Strategy

1. **Phase 1**: Implement unified system alongside existing systems
2. **Phase 2**: Add migration utilities and documentation
3. **Phase 3**: Deprecate old systems with warnings
4. **Phase 4**: Remove deprecated systems in next major version

## Consequences

### Positive

- **Unified API**: Consistent event handling across all client types
- **Better Testing**: Single test framework for all event scenarios
- **Improved Performance**: Optimized event dispatch and batching
- **Enhanced Developer Experience**: Better IDE support and documentation
- **Future-Proof**: Extensible architecture for new event types

### Negative

- **Breaking Changes**: Some existing code needs updates
- **Migration Complexity**: Requires careful planning for large codebases
- **Initial Learning Curve**: Developers need to adapt to new patterns

### Neutral

- **Bundle Size**: Slight increase due to unified system
- **Memory Usage**: Minimal impact due to efficient implementation

## Monitoring and Success Metrics

### Performance Metrics
- Event dispatch latency < 1ms (95th percentile)
- Memory usage increase < 5%
- Event throughput > 10,000 events/second

### Adoption Metrics
- Migration guide usage and feedback
- Community adoption rate
- Issue reports related to event system

### Quality Metrics
- Test coverage > 95%
- Zero critical bugs in event dispatch
- Documentation completeness score > 90%

## Implementation Timeline

- **Week 1-2**: Core event manager implementation
- **Week 3-4**: Event filtering and priority system
- **Week 5-6**: Backward compatibility layer
- **Week 7-8**: Migration utilities and documentation
- **Week 9-10**: Testing and performance optimization
- **Week 11-12**: Beta release and community feedback

## Related ADRs

- [ADR-002: Authentication Handler Design](ADR-002-authentication-handler-design.md)
- [ADR-003: Connection Pooling Architecture](ADR-003-connection-pooling-architecture.md)

## References

- [Event System API Documentation](../event_system_api.md)
- [Migration Guide](../migration_guide.md)
- [Performance Benchmarks](../performance_benchmarks.md)
- [Community RFC: Event System Unification](https://github.com/spacetimedb/spacetimedb-python-sdk/discussions/123)

---

**Author**: SpacetimeDB Python SDK Team  
**Date**: 2024-01-15  
**Last Updated**: 2024-01-20  
**Status**: Accepted and Implemented