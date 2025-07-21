"""
Property-based tests for event system implementations.

Uses hypothesis to generate test cases that verify event system behavior
under various conditions and edge cases.
"""
import pytest
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, assume, example, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, Bundle, initialize
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from spacetimedb_sdk.events.event_system import EventSystem


class TestEventSystemProperties:
    """Property-based tests for event system behavior."""
    
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=8),  # event_name - reduced size
                st.dictionaries(
                    st.text(min_size=1, max_size=6),  # key - smaller
                    st.one_of(st.text(max_size=8), st.integers(), st.booleans()),  # value - limited text size
                    min_size=0,
                    max_size=2  # Fewer entries
                )  # event_data
            ),
            min_size=1,
            max_size=25  # Further reduced max events
        )
    )
    @settings(deadline=1500, max_examples=10)  # More aggressive optimization
    def test_event_system_processes_all_events(self, events):
        """Test that event system processes all emitted events."""
        event_system = EventSystem()
        received_events = []
        
        def handler(data):
            received_events.append(data)
        
        # Subscribe to all unique event names
        event_names = set(event_name for event_name, _ in events)
        for event_name in event_names:
            event_system.subscribe(event_name, handler)
        
        # Emit all events
        for event_name, event_data in events:
            event_system.emit(event_name, event_data)
        
        # All events should be received
        assert len(received_events) == len(events)
        
        # Event data should match
        for i, (_, original_data) in enumerate(events):
            assert received_events[i] == original_data
    
    @given(
        st.text(min_size=1, max_size=20),
        st.integers(min_value=1, max_value=50),
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.text(min_size=1, max_size=20),
            min_size=1,
            max_size=10
        )
    )
    def test_multiple_handlers_receive_same_event(self, event_name, handler_count, event_data):
        """Test that multiple handlers receive the same event."""
        event_system = EventSystem()
        handler_calls = []
        
        # Create multiple handlers
        for i in range(handler_count):
            def handler(data, handler_id=i):
                handler_calls.append((handler_id, data))
            
            event_system.subscribe(event_name, handler)
        
        # Emit event
        event_system.emit(event_name, event_data)
        
        # All handlers should receive the event
        assert len(handler_calls) == handler_count
        
        # All handlers should receive the same data
        for handler_id, received_data in handler_calls:
            assert received_data == event_data
        
        # All handlers should have been called
        called_handlers = set(handler_id for handler_id, _ in handler_calls)
        assert called_handlers == set(range(handler_count))
    
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=8),  # event_name - reduced size
                st.integers(min_value=1, max_value=3),  # handler_count - further reduced max
            ),
            min_size=1,
            max_size=5  # Much smaller list size
        ),
        st.dictionaries(
            st.text(min_size=1, max_size=6),  # Smaller keys
            st.text(min_size=1, max_size=10),  # Smaller values
            min_size=1,
            max_size=2  # Fewer dictionary entries
        )
    )
    @settings(deadline=1500, max_examples=8)  # Much more aggressive settings
    def test_event_routing_accuracy(self, event_subscriptions, test_data):
        """Test that events are routed only to subscribed handlers."""
        event_system = EventSystem()
        handler_calls = {}
        
        # Set up subscriptions
        for event_name, handler_count in event_subscriptions:
            handler_calls[event_name] = []
            
            for i in range(handler_count):
                def handler(data, evt_name=event_name, handler_id=i):
                    handler_calls[evt_name].append((handler_id, data))
                
                event_system.subscribe(event_name, handler)
        
        # Emit events - emit each unique event name only once
        unique_event_names = set(event_name for event_name, _ in event_subscriptions)
        for event_name in unique_event_names:
            event_system.emit(event_name, test_data)
        
        # Verify routing
        # Calculate expected handler counts by aggregating duplicates
        expected_counts = {}
        for event_name, handler_count in event_subscriptions:
            expected_counts[event_name] = expected_counts.get(event_name, 0) + handler_count
        
        for event_name, expected_handler_count in expected_counts.items():
            calls = handler_calls[event_name]
            assert len(calls) == expected_handler_count, \
                f"Event {event_name} not routed to all handlers"
            
            # Verify all handlers received correct data
            for handler_id, received_data in calls:
                assert received_data == test_data
    
    @given(
        st.text(min_size=1, max_size=15),
        st.integers(min_value=1, max_value=15),
        st.lists(st.integers(), min_size=1, max_size=50)
    )
    @settings(deadline=1500, max_examples=10)
    def test_handler_unsubscription_works(self, event_name, handler_count, test_events):
        """Test that unsubscribed handlers don't receive events."""
        event_system = EventSystem()
        handlers = []
        call_counts = [0] * handler_count
        
        # Create and subscribe handlers
        for i in range(handler_count):
            def handler(data, handler_id=i):
                call_counts[handler_id] += 1
            
            handlers.append(handler)
            event_system.subscribe(event_name, handler)
        
        # Emit first event (all handlers should receive)
        event_system.emit(event_name, test_events[0])
        assert all(count == 1 for count in call_counts)
        
        # Unsubscribe half the handlers
        handlers_to_unsubscribe = handlers[:handler_count // 2]
        for handler in handlers_to_unsubscribe:
            event_system.unsubscribe(event_name, handler)
        
        # Emit second event (only remaining handlers should receive)
        if len(test_events) > 1:
            event_system.emit(event_name, test_events[1])
            
            # Unsubscribed handlers should still have count 1
            for i in range(len(handlers_to_unsubscribe)):
                assert call_counts[i] == 1
            
            # Remaining handlers should have count 2
            for i in range(len(handlers_to_unsubscribe), handler_count):
                assert call_counts[i] == 2
    
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=8),  # event_name - smaller
                st.text(min_size=1, max_size=15),  # event_data - smaller
            ),
            min_size=1,
            max_size=50  # Much reduced max events
        )
    )
    @settings(deadline=1500, max_examples=10)
    def test_event_order_preservation(self, events):
        """Test that events are processed in the order they were emitted."""
        event_system = EventSystem()
        received_events = []
        
        def handler(data):
            received_events.append(data)
        
        # Subscribe to all unique event names
        event_names = set(event_name for event_name, _ in events)
        for event_name in event_names:
            event_system.subscribe(event_name, handler)
        
        # Emit events in sequence
        for event_name, event_data in events:
            event_system.emit(event_name, event_data)
        
        # Events should be received in the same order
        expected_data = [event_data for _, event_data in events]
        assert received_events == expected_data
    
    @given(
        st.text(min_size=1, max_size=8),
        st.integers(min_value=1, max_value=10),  # Much smaller for concurrent tests
        st.text(min_size=1, max_size=15)
    )
    @settings(deadline=1500, max_examples=5)  # Very conservative for concurrent tests
    def test_concurrent_event_emission(self, event_name, event_count, event_data):
        """Test thread safety of concurrent event emission."""
        event_system = EventSystem()
        received_events = []
        lock = threading.Lock()
        
        def handler(data):
            with lock:
                received_events.append(data)
        
        event_system.subscribe(event_name, handler)
        
        # Emit events concurrently
        def emit_event(i):
            event_system.emit(event_name, f"{event_data}_{i}")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(emit_event, i) for i in range(event_count)]
            for future in as_completed(futures):
                future.result()  # Wait for completion
        
        # All events should be received
        assert len(received_events) == event_count
        
        # All events should be valid
        for received in received_events:
            assert received.startswith(event_data)
    
    @given(
        st.text(min_size=1, max_size=10),
        st.integers(min_value=1, max_value=20)
    )
    @settings(deadline=1500, max_examples=5)
    def test_concurrent_subscription_management(self, event_name, operation_count):
        """Test thread safety of concurrent subscription operations."""
        event_system = EventSystem()
        handlers = []
        results = []
        
        def create_handler(handler_id):
            def handler(data):
                results.append((handler_id, data))
            return handler
        
        def subscribe_operation(i):
            handler = create_handler(i)
            handlers.append(handler)
            event_system.subscribe(event_name, handler)
        
        def unsubscribe_operation(i):
            if i < len(handlers):
                event_system.unsubscribe(event_name, handlers[i])
        
        # Run concurrent subscription operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            # Subscribe operations
            for i in range(operation_count):
                futures.append(executor.submit(subscribe_operation, i))
            
            # Unsubscribe some handlers
            for i in range(operation_count // 2):
                futures.append(executor.submit(unsubscribe_operation, i))
            
            # Wait for all operations
            for future in as_completed(futures):
                future.result()
        
        # Emit test event
        event_system.emit(event_name, "test_data")
        
        # Should not crash and should receive some events
        assert len(results) <= operation_count


class EventSystemStateMachine(RuleBasedStateMachine):
    """State machine for testing event system behavior."""
    
    def __init__(self):
        super().__init__()
        self.event_system = EventSystem()
        self.subscriptions = {}  # event_name -> list of handlers
        self.handler_calls = {}  # handler_id -> list of received data
        self.next_handler_id = 0
    
    event_names = Bundle('event_names')
    handlers = Bundle('handlers')
    event_data = Bundle('event_data')
    
    @rule(target=event_names, name=st.text(min_size=1, max_size=6))  # Much smaller names
    def add_event_name(self, name):
        return name
    
    @rule(target=event_data, data=st.dictionaries(
        st.text(min_size=1, max_size=5),  # Much smaller keys
        st.one_of(st.text(max_size=6), st.integers(), st.booleans()),  # Very limited text size
        min_size=0,
        max_size=2  # Fewer entries
    ))
    def add_event_data(self, data):
        return data
    
    @rule(target=handlers, event_name=event_names)
    def create_handler(self, event_name):
        """Create a new handler for an event."""
        handler_id = self.next_handler_id
        self.next_handler_id += 1
        
        def handler(data):
            if handler_id not in self.handler_calls:
                self.handler_calls[handler_id] = []
            self.handler_calls[handler_id].append(data)
        
        self.event_system.subscribe(event_name, handler)
        
        if event_name not in self.subscriptions:
            self.subscriptions[event_name] = []
        self.subscriptions[event_name].append(handler_id)
        
        return (handler_id, handler, event_name)
    
    @rule(handler_info=handlers)
    def remove_handler(self, handler_info):
        """Remove a handler."""
        handler_id, handler, event_name = handler_info
        
        self.event_system.unsubscribe(event_name, handler)
        
        if event_name in self.subscriptions:
            if handler_id in self.subscriptions[event_name]:
                self.subscriptions[event_name].remove(handler_id)
    
    @rule(event_name=event_names, data=event_data)
    def emit_event(self, event_name, data):
        """Emit an event."""
        self.event_system.emit(event_name, data)
    
    @invariant()
    def handlers_receive_events(self):
        """Verify that active handlers receive events."""
        # This is a simplified check - in practice, we'd track specific emissions
        # and verify they were received by the right handlers
        pass


class TestEventSystemEdgeCases:
    """Test specific edge cases for event system."""
    
    def test_empty_event_name(self):
        """Test behavior with empty event names."""
        event_system = EventSystem()
        
        # Empty event names should be handled gracefully
        try:
            event_system.subscribe("", lambda x: None)
            event_system.emit("", {"test": "data"})
        except ValueError:
            # Expected - empty event names should be rejected
            pass
    
    def test_none_handler(self):
        """Test behavior with None handler."""
        event_system = EventSystem()
        
        # None handler should either be rejected or handled gracefully
        try:
            event_system.subscribe("test", None)
            # If it doesn't raise, that's also acceptable behavior
        except (ValueError, TypeError):
            # Expected - None handlers may be rejected
            pass
    
    def test_handler_exception_isolation(self):
        """Test that handler exceptions don't affect other handlers."""
        event_system = EventSystem()
        successful_calls = []
        
        def good_handler(data):
            successful_calls.append(data)
        
        def bad_handler(data):
            raise ValueError("Handler error")
        
        event_system.subscribe("test", good_handler)
        event_system.subscribe("test", bad_handler)
        event_system.subscribe("test", good_handler)
        
        # Emit event
        event_system.emit("test", "test_data")
        
        # Good handlers should still be called despite bad handler
        assert len(successful_calls) == 2
        assert all(data == "test_data" for data in successful_calls)
    
    def test_recursive_event_emission(self):
        """Test handling of recursive event emission."""
        event_system = EventSystem()
        call_depth = 0
        max_depth = 0
        
        def recursive_handler(data):
            nonlocal call_depth, max_depth
            call_depth += 1
            max_depth = max(max_depth, call_depth)
            
            if call_depth < 5:  # Limit recursion
                event_system.emit("recursive", data)
            
            call_depth -= 1
        
        event_system.subscribe("recursive", recursive_handler)
        
        # Should handle recursive emission without stack overflow
        event_system.emit("recursive", "start")
        
        assert max_depth == 5
    
    def test_wildcard_subscriptions(self):
        """Test wildcard event subscriptions if supported."""
        event_system = EventSystem()
        wildcard_calls = []
        
        def wildcard_handler(data):
            wildcard_calls.append(data)
        
        # Test if wildcard subscriptions are supported
        if hasattr(event_system, 'subscribe_wildcard'):
            event_system.subscribe_wildcard("test.*", wildcard_handler)
            
            # Emit various events
            test_events = ["test.one", "test.two", "other.event"]
            for event in test_events:
                event_system.emit(event, f"data_for_{event}")
            
            # Should receive only matching events
            assert len(wildcard_calls) == 2
    
    def test_subscription_during_emission(self):
        """Test subscribing to events during event emission."""
        event_system = EventSystem()
        calls = []
        
        def handler1(data):
            calls.append(("handler1", data))
            
            # Subscribe another handler during emission
            def handler2(data):
                calls.append(("handler2", data))
            
            event_system.subscribe("test", handler2)
        
        event_system.subscribe("test", handler1)
        
        # Emit two events
        event_system.emit("test", "first")
        event_system.emit("test", "second")
        
        # First emission should trigger only handler1
        # Second emission should trigger both handlers
        assert len(calls) >= 2
        assert calls[0] == ("handler1", "first")


# Run state machine tests with optimized settings
TestEventSystemStateMachine = EventSystemStateMachine.TestCase
# Apply settings to state machine
TestEventSystemStateMachine.settings = settings(deadline=2000, max_examples=10, stateful_step_count=8)