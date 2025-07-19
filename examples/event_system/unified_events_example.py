#!/usr/bin/env python3
"""
Unified Event System Example
============================

This example demonstrates the unified event system that consolidates
multiple event handling mechanisms into a single, cohesive interface.

Key features demonstrated:
- Event registration and handling
- Event filtering and routing
- Async and sync event handlers
- Event priorities and ordering
- Error handling in event processing
- Performance optimization techniques

Requirements:
- spacetimedb-sdk
- asyncio
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.events import (
    EventManager,
    Event,
    EventType,
    EventPriority,
    EventFilter,
    EventContext
)


class CustomEventType(Enum):
    """Application-specific event types"""
    USER_ACTION = "user_action"
    DATA_UPDATE = "data_update"
    SYSTEM_ALERT = "system_alert"
    PERFORMANCE_METRIC = "performance_metric"


@dataclass
class UserActionEvent(Event):
    """Custom event for user actions"""
    user_id: str
    action: str
    metadata: Dict[str, Any]
    
    @property
    def event_type(self) -> str:
        return CustomEventType.USER_ACTION.value


@dataclass
class DataUpdateEvent(Event):
    """Custom event for data updates"""
    table_name: str
    operation: str  # insert, update, delete
    record_id: str
    changes: Dict[str, Any]
    
    @property
    def event_type(self) -> str:
        return CustomEventType.DATA_UPDATE.value


class UnifiedEventSystemDemo:
    """Demonstrates the unified event system capabilities"""
    
    def __init__(self):
        self.client = SpacetimeDBClient()
        self.event_manager = self.client.event_manager
        self.event_stats = {
            'total_events': 0,
            'processed_events': 0,
            'failed_events': 0,
            'processing_time': 0.0
        }
    
    async def setup_event_handlers(self):
        """Set up various event handlers with different configurations"""
        
        print("Setting up unified event handlers...")
        print("=" * 50)
        
        # 1. Basic event handler
        @self.event_manager.on(EventType.CONNECTED)
        async def handle_connection(event: Event, context: EventContext):
            print(f"[CONNECTED] Connection established at {context.timestamp}")
            print(f"  Connection ID: {context.connection_id}")
            print(f"  Source: {context.source}")
        
        # 2. Handler with priority
        @self.event_manager.on(EventType.ROW_UPDATE, priority=EventPriority.HIGH)
        async def handle_critical_updates(event: Event, context: EventContext):
            print(f"[HIGH PRIORITY] Row update: {event.data}")
            # Process critical updates first
        
        # 3. Filtered event handler
        def user_filter(event: Event) -> bool:
            """Filter for user-related events"""
            return (
                hasattr(event, 'table_name') and 
                event.table_name == 'users'
            )
        
        @self.event_manager.on(
            EventType.ROW_UPDATE,
            filter=user_filter,
            priority=EventPriority.NORMAL
        )
        async def handle_user_updates(event: Event, context: EventContext):
            print(f"[USER UPDATE] User data changed: {event.data}")
        
        # 4. Custom event handler
        @self.event_manager.on(CustomEventType.USER_ACTION.value)
        async def handle_user_action(event: UserActionEvent, context: EventContext):
            print(f"[USER ACTION] {event.user_id} performed {event.action}")
            if event.metadata:
                print(f"  Metadata: {event.metadata}")
        
        # 5. Handler with error handling
        @self.event_manager.on(EventType.ERROR)
        async def handle_errors(event: Event, context: EventContext):
            print(f"[ERROR] {event.data.get('message', 'Unknown error')}")
            print(f"  Error type: {event.data.get('error_type', 'Unknown')}")
            # Log to error tracking service
        
        # 6. Wildcard handler for monitoring
        @self.event_manager.on("*", priority=EventPriority.LOW)
        async def monitor_all_events(event: Event, context: EventContext):
            self.event_stats['total_events'] += 1
            # Don't print for every event to avoid spam
            if self.event_stats['total_events'] % 10 == 0:
                print(f"[MONITOR] Total events processed: {self.event_stats['total_events']}")
        
        # 7. Synchronous handler (automatically wrapped)
        @self.event_manager.on(EventType.SUBSCRIPTION_UPDATE)
        def handle_subscription_sync(event: Event, context: EventContext):
            # Synchronous handlers are automatically wrapped in async
            print(f"[SUBSCRIPTION] Update received (sync handler)")
        
        print("Event handlers configured successfully!\n")
    
    async def demonstrate_event_filtering(self):
        """Demonstrate advanced event filtering capabilities"""
        
        print("\nEvent Filtering Demo")
        print("=" * 50)
        
        # Create complex filters
        class PriorityFilter(EventFilter):
            """Filter events by priority threshold"""
            
            def __init__(self, min_priority: int):
                self.min_priority = min_priority
            
            def matches(self, event: Event, context: EventContext) -> bool:
                return context.priority.value >= self.min_priority
        
        class CompositeFilter(EventFilter):
            """Combine multiple filters with AND/OR logic"""
            
            def __init__(self, filters: List[EventFilter], operator: str = "AND"):
                self.filters = filters
                self.operator = operator
            
            def matches(self, event: Event, context: EventContext) -> bool:
                if self.operator == "AND":
                    return all(f.matches(event, context) for f in self.filters)
                else:  # OR
                    return any(f.matches(event, context) for f in self.filters)
        
        # Register filtered handlers
        high_priority_filter = PriorityFilter(EventPriority.HIGH.value)
        
        @self.event_manager.on("*", filter=high_priority_filter)
        async def handle_high_priority_only(event: Event, context: EventContext):
            print(f"[HIGH PRIORITY ONLY] {event.event_type}: {event.data}")
        
        # Demonstrate filter in action
        test_events = [
            Event(event_type="test", data={"priority": "low"}),
            Event(event_type="test", data={"priority": "high"})
        ]
        
        for event in test_events:
            priority = EventPriority.LOW if "low" in str(event.data) else EventPriority.HIGH
            await self.event_manager.emit(event, priority=priority)
    
    async def demonstrate_event_ordering(self):
        """Demonstrate event priority and ordering"""
        
        print("\nEvent Ordering Demo")
        print("=" * 50)
        
        # Track execution order
        execution_order = []
        
        # Register handlers with different priorities
        @self.event_manager.on("order_test", priority=EventPriority.LOW)
        async def low_priority_handler(event: Event, context: EventContext):
            execution_order.append("LOW")
            print("  - Low priority handler executed")
        
        @self.event_manager.on("order_test", priority=EventPriority.NORMAL)
        async def normal_priority_handler(event: Event, context: EventContext):
            execution_order.append("NORMAL")
            print("  - Normal priority handler executed")
        
        @self.event_manager.on("order_test", priority=EventPriority.HIGH)
        async def high_priority_handler(event: Event, context: EventContext):
            execution_order.append("HIGH")
            print("  - High priority handler executed")
        
        @self.event_manager.on("order_test", priority=EventPriority.CRITICAL)
        async def critical_priority_handler(event: Event, context: EventContext):
            execution_order.append("CRITICAL")
            print("  - Critical priority handler executed")
        
        # Emit event
        print("Emitting test event...")
        await self.event_manager.emit(Event(event_type="order_test", data={}))
        
        print(f"\nExecution order: {' -> '.join(execution_order)}")
        print("(Higher priority handlers execute first)")
    
    async def demonstrate_event_performance(self):
        """Demonstrate performance optimization techniques"""
        
        print("\nEvent Performance Demo")
        print("=" * 50)
        
        # Test different event processing strategies
        event_count = 1000
        
        # 1. Sequential processing
        print(f"\n1. Sequential processing ({event_count} events)...")
        start_time = time.time()
        
        @self.event_manager.on("perf_test_seq")
        async def sequential_handler(event: Event, context: EventContext):
            # Simulate work
            await asyncio.sleep(0.001)
            self.event_stats['processed_events'] += 1
        
        for i in range(event_count):
            await self.event_manager.emit(
                Event(event_type="perf_test_seq", data={"index": i})
            )
        
        seq_duration = time.time() - start_time
        print(f"  Duration: {seq_duration:.2f}s")
        print(f"  Rate: {event_count / seq_duration:.2f} events/s")
        
        # 2. Batch processing
        print(f"\n2. Batch processing ({event_count} events)...")
        self.event_stats['processed_events'] = 0
        start_time = time.time()
        
        # Enable batch processing
        self.event_manager.enable_batching(
            batch_size=100,
            batch_timeout=0.1
        )
        
        @self.event_manager.on("perf_test_batch")
        async def batch_handler(events: List[Event], context: EventContext):
            # Process batch of events
            await asyncio.sleep(0.01)  # Simulate batch processing
            self.event_stats['processed_events'] += len(events)
        
        # Emit events rapidly
        tasks = []
        for i in range(event_count):
            task = self.event_manager.emit(
                Event(event_type="perf_test_batch", data={"index": i})
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.2)  # Wait for final batch
        
        batch_duration = time.time() - start_time
        print(f"  Duration: {batch_duration:.2f}s")
        print(f"  Rate: {event_count / batch_duration:.2f} events/s")
        print(f"  Speedup: {seq_duration / batch_duration:.2f}x")
        
        self.event_manager.disable_batching()
    
    async def demonstrate_error_handling(self):
        """Demonstrate error handling in event processing"""
        
        print("\nError Handling Demo")
        print("=" * 50)
        
        # Handler that might fail
        fail_count = 0
        
        @self.event_manager.on("error_test")
        async def unreliable_handler(event: Event, context: EventContext):
            nonlocal fail_count
            fail_count += 1
            
            if fail_count % 3 == 0:
                raise ValueError(f"Simulated error on attempt {fail_count}")
            
            print(f"  Successfully processed: {event.data}")
        
        # Error recovery handler
        @self.event_manager.on_error("error_test")
        async def handle_processing_error(
            error: Exception,
            event: Event,
            context: EventContext
        ):
            print(f"  [ERROR HANDLER] Caught error: {error}")
            print(f"    Event: {event.event_type}")
            print(f"    Retrying: {context.retry_count < 3}")
            
            if context.retry_count < 3:
                # Retry the event
                await asyncio.sleep(0.1 * context.retry_count)
                return True  # Retry
            
            return False  # Give up
        
        # Test error handling
        print("Testing error handling with retry logic...")
        for i in range(5):
            print(f"\nEvent {i + 1}:")
            await self.event_manager.emit(
                Event(event_type="error_test", data={"test": i})
            )
    
    async def demonstrate_event_lifecycle(self):
        """Demonstrate complete event lifecycle hooks"""
        
        print("\nEvent Lifecycle Demo")
        print("=" * 50)
        
        # Lifecycle hooks
        @self.event_manager.before_emit
        async def pre_process(event: Event, context: EventContext):
            """Called before event is emitted"""
            print(f"[PRE] Preparing to emit: {event.event_type}")
            # Add timing info
            context.metadata['emit_start'] = time.time()
        
        @self.event_manager.after_emit
        async def post_process(event: Event, context: EventContext):
            """Called after all handlers complete"""
            duration = time.time() - context.metadata.get('emit_start', time.time())
            print(f"[POST] Completed {event.event_type} in {duration:.3f}s")
            self.event_stats['processing_time'] += duration
        
        @self.event_manager.on_complete
        async def cleanup(event: Event, context: EventContext):
            """Called when event is fully processed"""
            print(f"[COMPLETE] Event {event.event_type} fully processed")
            # Clean up resources
        
        # Test lifecycle
        print("\nEmitting event with lifecycle hooks...")
        await self.event_manager.emit(
            Event(event_type="lifecycle_test", data={"test": "data"})
        )
    
    async def demonstrate_custom_events(self):
        """Demonstrate custom event types and routing"""
        
        print("\nCustom Events Demo")
        print("=" * 50)
        
        # Emit custom events
        print("Emitting custom user action...")
        await self.event_manager.emit(
            UserActionEvent(
                user_id="user123",
                action="login",
                metadata={
                    "ip": "192.168.1.1",
                    "user_agent": "Mozilla/5.0",
                    "timestamp": time.time()
                }
            )
        )
        
        print("\nEmitting custom data update...")
        await self.event_manager.emit(
            DataUpdateEvent(
                table_name="products",
                operation="update",
                record_id="prod456",
                changes={
                    "price": {"old": 99.99, "new": 89.99},
                    "stock": {"old": 100, "new": 95}
                }
            )
        )
    
    def print_statistics(self):
        """Print event processing statistics"""
        
        print("\n\nEvent Processing Statistics")
        print("=" * 50)
        print(f"Total events: {self.event_stats['total_events']}")
        print(f"Processed events: {self.event_stats['processed_events']}")
        print(f"Failed events: {self.event_stats['failed_events']}")
        print(f"Total processing time: {self.event_stats['processing_time']:.2f}s")
        
        if self.event_stats['processed_events'] > 0:
            avg_time = self.event_stats['processing_time'] / self.event_stats['processed_events']
            print(f"Average processing time: {avg_time * 1000:.2f}ms")
        
        # Get event manager statistics
        manager_stats = self.event_manager.get_statistics()
        print(f"\nEvent Manager Statistics:")
        print(f"Registered handlers: {manager_stats.get('handler_count', 0)}")
        print(f"Active subscriptions: {manager_stats.get('subscription_count', 0)}")
        print(f"Event types: {manager_stats.get('event_type_count', 0)}")


async def main():
    """Run the unified event system demonstration"""
    
    demo = UnifiedEventSystemDemo()
    
    try:
        # Set up handlers
        await demo.setup_event_handlers()
        
        # Run demonstrations
        await demo.demonstrate_event_filtering()
        await demo.demonstrate_event_ordering()
        await demo.demonstrate_event_performance()
        await demo.demonstrate_error_handling()
        await demo.demonstrate_event_lifecycle()
        await demo.demonstrate_custom_events()
        
        # Print statistics
        demo.print_statistics()
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
    finally:
        # Clean up
        if demo.client:
            await demo.client.close()


if __name__ == "__main__":
    asyncio.run(main())