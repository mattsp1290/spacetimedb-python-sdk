#!/usr/bin/env python3
"""
Event Filtering Example
=======================

This example demonstrates advanced event filtering techniques including:
- Pattern-based filtering
- Conditional filtering with complex logic
- Performance-optimized filtering
- Dynamic filter composition
- Filter chaining and combination

Requirements:
- spacetimedb-sdk
- asyncio
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import re
import time
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.events import Event, EventContext, EventFilter


class FilterOperator(Enum):
    """Logical operators for combining filters"""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    XOR = "XOR"


class BaseFilter(EventFilter):
    """Base class for all custom filters"""
    
    def __init__(self, name: str):
        self.name = name
        self.match_count = 0
        self.check_count = 0
    
    def matches(self, event: Event, context: EventContext) -> bool:
        self.check_count += 1
        result = self._check_match(event, context)
        if result:
            self.match_count += 1
        return result
    
    @abstractmethod
    def _check_match(self, event: Event, context: EventContext) -> bool:
        """Implement actual matching logic"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filter statistics"""
        return {
            "name": self.name,
            "checks": self.check_count,
            "matches": self.match_count,
            "match_rate": self.match_count / self.check_count if self.check_count > 0 else 0
        }


class PatternFilter(BaseFilter):
    """Filter events based on regex patterns"""
    
    def __init__(self, field: str, pattern: str, flags: int = 0):
        super().__init__(f"PatternFilter({field})")
        self.field = field
        self.pattern = re.compile(pattern, flags)
    
    def _check_match(self, event: Event, context: EventContext) -> bool:
        value = event.data.get(self.field, "")
        if not isinstance(value, str):
            value = str(value)
        return self.pattern.match(value) is not None


class RangeFilter(BaseFilter):
    """Filter numeric values within a range"""
    
    def __init__(self, field: str, min_value: Optional[float] = None, max_value: Optional[float] = None):
        super().__init__(f"RangeFilter({field})")
        self.field = field
        self.min_value = min_value
        self.max_value = max_value
    
    def _check_match(self, event: Event, context: EventContext) -> bool:
        value = event.data.get(self.field)
        if value is None or not isinstance(value, (int, float)):
            return False
        
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        
        return True


class TimeWindowFilter(BaseFilter):
    """Filter events within a time window"""
    
    def __init__(self, window_seconds: float, max_events: Optional[int] = None):
        super().__init__(f"TimeWindowFilter({window_seconds}s)")
        self.window_seconds = window_seconds
        self.max_events = max_events
        self.events: List[float] = []
    
    def _check_match(self, event: Event, context: EventContext) -> bool:
        current_time = time.time()
        
        # Remove old events outside window
        self.events = [t for t in self.events if current_time - t < self.window_seconds]
        
        # Check if we can accept this event
        if self.max_events and len(self.events) >= self.max_events:
            return False
        
        # Add event to window
        self.events.append(current_time)
        return True


class CompositeFilter(BaseFilter):
    """Combine multiple filters with logical operators"""
    
    def __init__(self, operator: FilterOperator, *filters: EventFilter):
        super().__init__(f"CompositeFilter({operator.value})")
        self.operator = operator
        self.filters = list(filters)
    
    def _check_match(self, event: Event, context: EventContext) -> bool:
        if self.operator == FilterOperator.AND:
            return all(f.matches(event, context) for f in self.filters)
        elif self.operator == FilterOperator.OR:
            return any(f.matches(event, context) for f in self.filters)
        elif self.operator == FilterOperator.NOT:
            # NOT only uses first filter
            return not self.filters[0].matches(event, context) if self.filters else True
        elif self.operator == FilterOperator.XOR:
            # XOR: exactly one filter matches
            matches = sum(1 for f in self.filters if f.matches(event, context))
            return matches == 1
        
        return False
    
    def add_filter(self, filter: EventFilter):
        """Add a filter to the composite"""
        self.filters.append(filter)
    
    def remove_filter(self, filter: EventFilter):
        """Remove a filter from the composite"""
        self.filters.remove(filter)


class PredicateFilter(BaseFilter):
    """Filter using custom predicate function"""
    
    def __init__(self, name: str, predicate: Callable[[Event, EventContext], bool]):
        super().__init__(name)
        self.predicate = predicate
    
    def _check_match(self, event: Event, context: EventContext) -> bool:
        return self.predicate(event, context)


class CachingFilter(BaseFilter):
    """Cache filter results for performance"""
    
    def __init__(self, inner_filter: EventFilter, cache_size: int = 1000):
        super().__init__(f"CachingFilter({inner_filter})")
        self.inner_filter = inner_filter
        self.cache_size = cache_size
        self.cache: Dict[str, bool] = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _get_cache_key(self, event: Event, context: EventContext) -> str:
        """Generate cache key for event"""
        # Simple key based on event type and data hash
        data_str = str(sorted(event.data.items()))
        return f"{event.event_type}:{hash(data_str)}"
    
    def _check_match(self, event: Event, context: EventContext) -> bool:
        cache_key = self._get_cache_key(event, context)
        
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        result = self.inner_filter.matches(event, context)
        
        # Update cache with LRU eviction
        if len(self.cache) >= self.cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[cache_key] = result
        return result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_hits + self.cache_misses
        return {
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.cache_hits / total_requests if total_requests > 0 else 0
        }


class DynamicFilter(BaseFilter):
    """Filter that can be modified at runtime"""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.conditions: List[Callable[[Event, EventContext], bool]] = []
        self.enabled = True
    
    def add_condition(self, condition: Callable[[Event, EventContext], bool]):
        """Add a condition to the filter"""
        self.conditions.append(condition)
    
    def remove_condition(self, condition: Callable[[Event, EventContext], bool]):
        """Remove a condition from the filter"""
        self.conditions.remove(condition)
    
    def clear_conditions(self):
        """Remove all conditions"""
        self.conditions.clear()
    
    def enable(self):
        """Enable the filter"""
        self.enabled = True
    
    def disable(self):
        """Disable the filter"""
        self.enabled = False
    
    def _check_match(self, event: Event, context: EventContext) -> bool:
        if not self.enabled:
            return True  # Pass through when disabled
        
        # All conditions must match (AND logic)
        return all(condition(event, context) for condition in self.conditions)


class EventFilterDemo:
    """Demonstrates advanced event filtering techniques"""
    
    def __init__(self):
        self.client = SpacetimeDBClient()
        self.filters: Dict[str, BaseFilter] = {}
    
    async def demonstrate_pattern_filtering(self):
        """Demonstrate pattern-based filtering"""
        
        print("Pattern Filtering Demo")
        print("=" * 50)
        
        # Create pattern filters
        email_filter = PatternFilter(
            "email",
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        
        error_filter = PatternFilter(
            "message",
            r".*error.*|.*exception.*|.*failed.*",
            re.IGNORECASE
        )
        
        self.filters["email"] = email_filter
        self.filters["error"] = error_filter
        
        # Test events
        test_events = [
            Event("user_signup", {"email": "user@example.com", "name": "John"}),
            Event("user_signup", {"email": "invalid-email", "name": "Jane"}),
            Event("system_log", {"message": "Connection error occurred"}),
            Event("system_log", {"message": "Everything is working fine"}),
            Event("system_log", {"message": "Failed to process request"})
        ]
        
        print("\nTesting email pattern filter:")
        for event in test_events[:2]:
            if email_filter.matches(event, EventContext()):
                print(f"  ✓ Valid email: {event.data.get('email')}")
            else:
                print(f"  ✗ Invalid email: {event.data.get('email')}")
        
        print("\nTesting error pattern filter:")
        for event in test_events[2:]:
            if error_filter.matches(event, EventContext()):
                print(f"  ⚠️  Error detected: {event.data.get('message')}")
            else:
                print(f"  ✓ Normal message: {event.data.get('message')}")
    
    async def demonstrate_range_filtering(self):
        """Demonstrate range-based filtering"""
        
        print("\n\nRange Filtering Demo")
        print("=" * 50)
        
        # Create range filters
        price_filter = RangeFilter("price", min_value=10.0, max_value=100.0)
        age_filter = RangeFilter("age", min_value=18, max_value=65)
        
        self.filters["price"] = price_filter
        self.filters["age"] = age_filter
        
        # Test events
        test_events = [
            Event("purchase", {"item": "Book", "price": 25.99}),
            Event("purchase", {"item": "Laptop", "price": 1299.99}),
            Event("purchase", {"item": "Pen", "price": 2.99}),
            Event("user_data", {"name": "Alice", "age": 25}),
            Event("user_data", {"name": "Bob", "age": 17}),
            Event("user_data", {"name": "Charlie", "age": 70})
        ]
        
        print("\nTesting price range filter ($10-$100):")
        for event in test_events[:3]:
            if price_filter.matches(event, EventContext()):
                print(f"  ✓ In range: {event.data.get('item')} - ${event.data.get('price')}")
            else:
                print(f"  ✗ Out of range: {event.data.get('item')} - ${event.data.get('price')}")
        
        print("\nTesting age range filter (18-65):")
        for event in test_events[3:]:
            if age_filter.matches(event, EventContext()):
                print(f"  ✓ Eligible: {event.data.get('name')} (age {event.data.get('age')})")
            else:
                print(f"  ✗ Not eligible: {event.data.get('name')} (age {event.data.get('age')})")
    
    async def demonstrate_composite_filtering(self):
        """Demonstrate composite filter logic"""
        
        print("\n\nComposite Filtering Demo")
        print("=" * 50)
        
        # Create individual filters
        premium_filter = PredicateFilter(
            "premium_user",
            lambda e, c: e.data.get("user_tier") == "premium"
        )
        
        high_value_filter = RangeFilter("amount", min_value=1000.0)
        
        verified_filter = PredicateFilter(
            "verified",
            lambda e, c: e.data.get("verified") == True
        )
        
        # Create composite filters
        # Premium OR high-value transactions
        premium_or_high_value = CompositeFilter(
            FilterOperator.OR,
            premium_filter,
            high_value_filter
        )
        
        # Must be verified AND (premium OR high-value)
        secure_transaction = CompositeFilter(
            FilterOperator.AND,
            verified_filter,
            premium_or_high_value
        )
        
        self.filters["secure_transaction"] = secure_transaction
        
        # Test events
        test_events = [
            Event("transaction", {
                "user_id": "1",
                "amount": 500,
                "user_tier": "basic",
                "verified": True
            }),
            Event("transaction", {
                "user_id": "2",
                "amount": 2000,
                "user_tier": "basic",
                "verified": True
            }),
            Event("transaction", {
                "user_id": "3",
                "amount": 100,
                "user_tier": "premium",
                "verified": True
            }),
            Event("transaction", {
                "user_id": "4",
                "amount": 5000,
                "user_tier": "premium",
                "verified": False
            })
        ]
        
        print("\nTesting composite filter (Verified AND (Premium OR HighValue)):")
        for event in test_events:
            data = event.data
            result = secure_transaction.matches(event, EventContext())
            status = "✓ Approved" if result else "✗ Rejected"
            print(f"  {status}: User {data['user_id']} - "
                  f"${data['amount']} - {data['user_tier']} - "
                  f"Verified: {data['verified']}")
    
    async def demonstrate_time_window_filtering(self):
        """Demonstrate time window filtering"""
        
        print("\n\nTime Window Filtering Demo")
        print("=" * 50)
        
        # Create time window filter (max 3 events per 2 seconds)
        rate_limit_filter = TimeWindowFilter(
            window_seconds=2.0,
            max_events=3
        )
        
        self.filters["rate_limit"] = rate_limit_filter
        
        print("Testing rate limit filter (max 3 events per 2 seconds):")
        
        # Send burst of events
        for i in range(10):
            event = Event("api_request", {"request_id": i})
            
            if rate_limit_filter.matches(event, EventContext()):
                print(f"  ✓ Request {i} allowed")
            else:
                print(f"  ✗ Request {i} rate limited")
            
            if i == 4:
                print("  ... waiting 2 seconds ...")
                await asyncio.sleep(2.1)
            else:
                await asyncio.sleep(0.1)
    
    async def demonstrate_caching_filter(self):
        """Demonstrate filter result caching"""
        
        print("\n\nCaching Filter Demo")
        print("=" * 50)
        
        # Create expensive filter
        def expensive_check(event: Event, context: EventContext) -> bool:
            # Simulate expensive computation
            time.sleep(0.01)  # 10ms per check
            return event.data.get("score", 0) > 50
        
        expensive_filter = PredicateFilter("expensive", expensive_check)
        cached_filter = CachingFilter(expensive_filter, cache_size=100)
        
        self.filters["cached"] = cached_filter
        
        # Test with repeated events
        events = [
            Event("score_check", {"user": "A", "score": 60}),
            Event("score_check", {"user": "B", "score": 40}),
            Event("score_check", {"user": "A", "score": 60}),  # Duplicate
            Event("score_check", {"user": "C", "score": 75}),
            Event("score_check", {"user": "B", "score": 40}),  # Duplicate
            Event("score_check", {"user": "A", "score": 60}),  # Duplicate
        ]
        
        print("Testing cached filter performance:")
        
        # Test without cache
        start_time = time.time()
        for event in events:
            expensive_filter.matches(event, EventContext())
        no_cache_time = time.time() - start_time
        
        # Test with cache
        start_time = time.time()
        for event in events:
            result = cached_filter.matches(event, EventContext())
            print(f"  Event {event.data['user']}: {'Pass' if result else 'Fail'}")
        cache_time = time.time() - start_time
        
        # Print performance comparison
        cache_stats = cached_filter.get_cache_stats()
        print(f"\nPerformance comparison:")
        print(f"  Without cache: {no_cache_time:.3f}s")
        print(f"  With cache: {cache_time:.3f}s")
        print(f"  Speedup: {no_cache_time / cache_time:.2f}x")
        print(f"\nCache statistics:")
        print(f"  Hit rate: {cache_stats['hit_rate']:.1%}")
        print(f"  Cache size: {cache_stats['cache_size']}")
    
    async def demonstrate_dynamic_filtering(self):
        """Demonstrate dynamic filter modification"""
        
        print("\n\nDynamic Filtering Demo")
        print("=" * 50)
        
        # Create dynamic filter
        dynamic_filter = DynamicFilter("configurable")
        self.filters["dynamic"] = dynamic_filter
        
        # Start with basic condition
        dynamic_filter.add_condition(
            lambda e, c: e.data.get("priority", 0) > 5
        )
        
        print("Initial filter: priority > 5")
        
        # Test events
        test_events = [
            Event("task", {"id": 1, "priority": 3, "category": "bug"}),
            Event("task", {"id": 2, "priority": 7, "category": "feature"}),
            Event("task", {"id": 3, "priority": 9, "category": "bug"})
        ]
        
        print("\nTesting with initial conditions:")
        for event in test_events:
            if dynamic_filter.matches(event, EventContext()):
                print(f"  ✓ Task {event.data['id']} passes")
            else:
                print(f"  ✗ Task {event.data['id']} filtered")
        
        # Add another condition
        print("\nAdding condition: category == 'bug'")
        dynamic_filter.add_condition(
            lambda e, c: e.data.get("category") == "bug"
        )
        
        print("\nTesting with both conditions:")
        for event in test_events:
            if dynamic_filter.matches(event, EventContext()):
                print(f"  ✓ Task {event.data['id']} passes")
            else:
                print(f"  ✗ Task {event.data['id']} filtered")
        
        # Disable filter
        print("\nDisabling filter:")
        dynamic_filter.disable()
        
        for event in test_events:
            if dynamic_filter.matches(event, EventContext()):
                print(f"  ✓ Task {event.data['id']} passes (filter disabled)")
    
    def print_filter_statistics(self):
        """Print statistics for all filters"""
        
        print("\n\nFilter Statistics")
        print("=" * 50)
        
        for name, filter in self.filters.items():
            stats = filter.get_stats()
            print(f"\n{name}:")
            print(f"  Total checks: {stats['checks']}")
            print(f"  Matches: {stats['matches']}")
            print(f"  Match rate: {stats['match_rate']:.1%}")
            
            # Print cache stats if available
            if isinstance(filter, CachingFilter):
                cache_stats = filter.get_cache_stats()
                print(f"  Cache hit rate: {cache_stats['hit_rate']:.1%}")


async def main():
    """Run event filtering demonstrations"""
    
    demo = EventFilterDemo()
    
    try:
        await demo.demonstrate_pattern_filtering()
        await demo.demonstrate_range_filtering()
        await demo.demonstrate_composite_filtering()
        await demo.demonstrate_time_window_filtering()
        await demo.demonstrate_caching_filter()
        await demo.demonstrate_dynamic_filtering()
        
        demo.print_filter_statistics()
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
    finally:
        if demo.client:
            await demo.client.close()


if __name__ == "__main__":
    asyncio.run(main())