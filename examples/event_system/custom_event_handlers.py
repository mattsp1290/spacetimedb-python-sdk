#!/usr/bin/env python3
"""
Custom Event Handlers Example
=============================

This example demonstrates how to create and use custom event handlers
for specific application needs, including middleware, interceptors,
and advanced event processing patterns.

Key concepts:
- Custom event handler classes
- Event middleware and interceptors
- Conditional event handling
- Event transformation and enrichment
- Async event pipelines
- Event handler composition

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
import json
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.events import Event, EventContext, EventHandler


T = TypeVar('T', bound=Event)


class EventProcessor(ABC, Generic[T]):
    """Abstract base class for event processors"""
    
    @abstractmethod
    async def process(self, event: T, context: EventContext) -> Optional[T]:
        """Process an event, optionally transforming it"""
        pass


class LoggingProcessor(EventProcessor):
    """Logs all events passing through"""
    
    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self.event_count = 0
    
    async def process(self, event: Event, context: EventContext) -> Event:
        self.event_count += 1
        print(f"[{self.log_level}] Event #{self.event_count}: {event.event_type}")
        print(f"  Timestamp: {context.timestamp}")
        print(f"  Data: {json.dumps(event.data, indent=2)}")
        return event


class ValidationProcessor(EventProcessor):
    """Validates events against schemas"""
    
    def __init__(self, schemas: Dict[str, Dict[str, Any]]):
        self.schemas = schemas
    
    async def process(self, event: Event, context: EventContext) -> Optional[Event]:
        schema = self.schemas.get(event.event_type)
        if not schema:
            # No schema defined, pass through
            return event
        
        # Simple validation example
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in event.data:
                print(f"[VALIDATION ERROR] Missing required field: {field}")
                return None  # Filter out invalid events
        
        # Type validation
        field_types = schema.get('types', {})
        for field, expected_type in field_types.items():
            if field in event.data:
                actual_type = type(event.data[field]).__name__
                if actual_type != expected_type:
                    print(f"[VALIDATION ERROR] Field {field} has wrong type: expected {expected_type}, got {actual_type}")
                    return None
        
        print(f"[VALIDATION OK] Event {event.event_type} passed validation")
        return event


class EnrichmentProcessor(EventProcessor):
    """Enriches events with additional data"""
    
    def __init__(self, enrichment_source: Callable[[Event], Dict[str, Any]]):
        self.enrichment_source = enrichment_source
    
    async def process(self, event: Event, context: EventContext) -> Event:
        # Get enrichment data
        enrichment_data = self.enrichment_source(event)
        
        # Create enriched event
        enriched_data = {**event.data, **enrichment_data}
        enriched_event = Event(
            event_type=event.event_type,
            data=enriched_data
        )
        
        print(f"[ENRICHMENT] Added {len(enrichment_data)} fields to {event.event_type}")
        return enriched_event


class RateLimitProcessor(EventProcessor):
    """Rate limits event processing"""
    
    def __init__(self, max_events_per_second: float):
        self.max_events_per_second = max_events_per_second
        self.min_interval = 1.0 / max_events_per_second
        self.last_process_time = 0.0
    
    async def process(self, event: Event, context: EventContext) -> Optional[Event]:
        current_time = time.time()
        time_since_last = current_time - self.last_process_time
        
        if time_since_last < self.min_interval:
            # Rate limit exceeded
            wait_time = self.min_interval - time_since_last
            print(f"[RATE LIMIT] Waiting {wait_time:.3f}s before processing")
            await asyncio.sleep(wait_time)
        
        self.last_process_time = time.time()
        return event


class BatchProcessor(EventProcessor):
    """Batches events for efficient processing"""
    
    def __init__(self, batch_size: int, batch_timeout: float):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batch: List[Event] = []
        self.batch_start_time = None
        self.process_callback: Optional[Callable] = None
    
    async def process(self, event: Event, context: EventContext) -> Optional[Event]:
        if self.batch_start_time is None:
            self.batch_start_time = time.time()
        
        self.batch.append(event)
        
        # Check if batch is ready
        batch_full = len(self.batch) >= self.batch_size
        batch_timeout = (time.time() - self.batch_start_time) >= self.batch_timeout
        
        if batch_full or batch_timeout:
            await self._process_batch()
        
        return None  # Batch processor doesn't emit individual events
    
    async def _process_batch(self):
        if not self.batch:
            return
        
        print(f"[BATCH] Processing batch of {len(self.batch)} events")
        
        if self.process_callback:
            await self.process_callback(self.batch)
        
        # Reset batch
        self.batch = []
        self.batch_start_time = None
    
    def set_batch_handler(self, handler: Callable):
        """Set the callback for batch processing"""
        self.process_callback = handler


class EventPipeline:
    """Chains multiple event processors together"""
    
    def __init__(self, processors: List[EventProcessor]):
        self.processors = processors
    
    async def process(self, event: Event, context: EventContext) -> Optional[Event]:
        current_event = event
        
        for processor in self.processors:
            if current_event is None:
                break
            
            current_event = await processor.process(current_event, context)
        
        return current_event


class ConditionalHandler(EventHandler):
    """Handles events based on conditions"""
    
    def __init__(self, condition: Callable[[Event], bool], handler: Callable):
        self.condition = condition
        self.handler = handler
    
    async def handle(self, event: Event, context: EventContext):
        if self.condition(event):
            await self.handler(event, context)
        else:
            print(f"[CONDITIONAL] Skipping {event.event_type} - condition not met")


class RetryHandler(EventHandler):
    """Handles events with retry logic"""
    
    def __init__(self, handler: Callable, max_retries: int = 3, backoff_factor: float = 2.0):
        self.handler = handler
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    async def handle(self, event: Event, context: EventContext):
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                await self.handler(event, context)
                return  # Success
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count <= self.max_retries:
                    wait_time = (self.backoff_factor ** (retry_count - 1))
                    print(f"[RETRY] Attempt {retry_count} failed: {e}")
                    print(f"[RETRY] Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
        
        print(f"[RETRY] All {self.max_retries} retries failed. Last error: {last_error}")
        raise last_error


class CircuitBreakerHandler(EventHandler):
    """Implements circuit breaker pattern for event handling"""
    
    def __init__(self, handler: Callable, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self.handler = handler
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
    
    async def handle(self, event: Event, context: EventContext):
        # Check if circuit should be reset
        if self.is_open and self.last_failure_time:
            if time.time() - self.last_failure_time > self.reset_timeout:
                print("[CIRCUIT BREAKER] Resetting circuit")
                self.is_open = False
                self.failure_count = 0
        
        # Check if circuit is open
        if self.is_open:
            print("[CIRCUIT BREAKER] Circuit is OPEN - rejecting event")
            raise Exception("Circuit breaker is open")
        
        try:
            await self.handler(event, context)
            # Success - reset failure count
            if self.failure_count > 0:
                print("[CIRCUIT BREAKER] Success - resetting failure count")
                self.failure_count = 0
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                print(f"[CIRCUIT BREAKER] Opening circuit after {self.failure_count} failures")
                self.is_open = True
            
            raise e


class CustomEventHandlerDemo:
    """Demonstrates custom event handler patterns"""
    
    def __init__(self):
        self.client = SpacetimeDBClient()
    
    async def demonstrate_event_pipeline(self):
        """Demonstrate event processing pipeline"""
        
        print("Event Pipeline Demo")
        print("=" * 50)
        
        # Define schemas for validation
        schemas = {
            "user_action": {
                "required": ["user_id", "action"],
                "types": {
                    "user_id": "str",
                    "action": "str",
                    "timestamp": "float"
                }
            }
        }
        
        # Define enrichment function
        def enrich_user_data(event: Event) -> Dict[str, Any]:
            return {
                "enriched_at": time.time(),
                "server_region": "us-west",
                "api_version": "2.0"
            }
        
        # Create pipeline
        pipeline = EventPipeline([
            LoggingProcessor("DEBUG"),
            ValidationProcessor(schemas),
            EnrichmentProcessor(enrich_user_data),
            RateLimitProcessor(max_events_per_second=10)
        ])
        
        # Process events through pipeline
        test_events = [
            Event("user_action", {"user_id": "123", "action": "login"}),
            Event("user_action", {"action": "logout"}),  # Missing user_id
            Event("user_action", {"user_id": "456", "action": "purchase"})
        ]
        
        print("\nProcessing events through pipeline...")
        for event in test_events:
            print(f"\n--- Processing {event.event_type} ---")
            result = await pipeline.process(event, EventContext())
            if result:
                print(f"Pipeline output: {result.data}")
            else:
                print("Event filtered out by pipeline")
    
    async def demonstrate_conditional_handling(self):
        """Demonstrate conditional event handling"""
        
        print("\n\nConditional Handler Demo")
        print("=" * 50)
        
        # Define conditions
        def is_premium_user(event: Event) -> bool:
            return event.data.get("user_tier") == "premium"
        
        def is_high_value_transaction(event: Event) -> bool:
            return event.data.get("amount", 0) > 1000
        
        # Create conditional handlers
        premium_handler = ConditionalHandler(
            condition=is_premium_user,
            handler=lambda e, c: print(f"[PREMIUM] Special handling for premium user: {e.data}")
        )
        
        high_value_handler = ConditionalHandler(
            condition=is_high_value_transaction,
            handler=lambda e, c: print(f"[HIGH VALUE] Transaction requires approval: ${e.data.get('amount')}")
        )
        
        # Test conditional handling
        test_events = [
            Event("transaction", {"user_id": "123", "amount": 50, "user_tier": "basic"}),
            Event("transaction", {"user_id": "456", "amount": 2000, "user_tier": "premium"}),
            Event("transaction", {"user_id": "789", "amount": 100, "user_tier": "premium"})
        ]
        
        print("\nTesting conditional handlers...")
        for event in test_events:
            print(f"\nProcessing: {event.data}")
            await premium_handler.handle(event, EventContext())
            await high_value_handler.handle(event, EventContext())
    
    async def demonstrate_retry_handling(self):
        """Demonstrate retry handler with failures"""
        
        print("\n\nRetry Handler Demo")
        print("=" * 50)
        
        # Simulate unreliable service
        call_count = 0
        
        async def unreliable_handler(event: Event, context: EventContext):
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                raise Exception(f"Service unavailable (attempt {call_count})")
            
            print(f"[SUCCESS] Event processed after {call_count} attempts")
        
        # Create retry handler
        retry_handler = RetryHandler(
            handler=unreliable_handler,
            max_retries=3,
            backoff_factor=2.0
        )
        
        # Test retry handling
        print("\nTesting retry handler...")
        test_event = Event("test", {"data": "important"})
        
        try:
            await retry_handler.handle(test_event, EventContext())
        except Exception as e:
            print(f"[FAILED] Final failure: {e}")
    
    async def demonstrate_circuit_breaker(self):
        """Demonstrate circuit breaker pattern"""
        
        print("\n\nCircuit Breaker Demo")
        print("=" * 50)
        
        # Simulate service that fails then recovers
        failure_count = 0
        
        async def flaky_handler(event: Event, context: EventContext):
            nonlocal failure_count
            failure_count += 1
            
            if failure_count <= 6:
                raise Exception(f"Service error #{failure_count}")
            
            print(f"[SERVICE] Successfully processed: {event.data}")
        
        # Create circuit breaker
        circuit_breaker = CircuitBreakerHandler(
            handler=flaky_handler,
            failure_threshold=5,
            reset_timeout=2.0  # Short timeout for demo
        )
        
        print("\nTesting circuit breaker...")
        
        # Send events that will trigger circuit breaker
        for i in range(10):
            test_event = Event("test", {"index": i})
            
            try:
                await circuit_breaker.handle(test_event, EventContext())
            except Exception as e:
                print(f"Event {i}: {e}")
            
            if i == 7:
                print("\nWaiting for circuit to reset...")
                await asyncio.sleep(2.5)
    
    async def demonstrate_batch_processing(self):
        """Demonstrate batch event processing"""
        
        print("\n\nBatch Processing Demo")
        print("=" * 50)
        
        # Create batch processor
        batch_processor = BatchProcessor(
            batch_size=5,
            batch_timeout=2.0
        )
        
        # Define batch handler
        async def process_batch(events: List[Event]):
            print(f"\n[BATCH HANDLER] Processing {len(events)} events:")
            for i, event in enumerate(events):
                print(f"  {i+1}. {event.event_type}: {event.data}")
            
            # Simulate batch processing
            await asyncio.sleep(0.5)
            print("[BATCH HANDLER] Batch processing complete")
        
        batch_processor.set_batch_handler(process_batch)
        
        print("\nSending events for batching...")
        
        # Send events
        for i in range(12):
            event = Event("batch_test", {"index": i, "timestamp": time.time()})
            await batch_processor.process(event, EventContext())
            print(f"Sent event {i}")
            await asyncio.sleep(0.3)
        
        # Process final batch
        print("\nProcessing final batch...")
        await batch_processor._process_batch()


async def main():
    """Run custom event handler demonstrations"""
    
    demo = CustomEventHandlerDemo()
    
    try:
        await demo.demonstrate_event_pipeline()
        await demo.demonstrate_conditional_handling()
        await demo.demonstrate_retry_handling()
        await demo.demonstrate_circuit_breaker()
        await demo.demonstrate_batch_processing()
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
    finally:
        if demo.client:
            await demo.client.close()


if __name__ == "__main__":
    asyncio.run(main())