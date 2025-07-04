"""
Isolated tests for the unified event system module

These tests will validate the unified event system functionality 
that will be extracted from websocket_client.py during Phase 2 refactoring.
"""
import pytest
import time
import threading
import queue
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional, List, Callable, Set
from enum import Enum
from dataclasses import dataclass, field
import uuid
import weakref


class EventType(Enum):
    """Event types for the unified event system"""
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_ERROR = "authentication_error"
    SUBSCRIPTION_APPLIED = "subscription_applied"
    SUBSCRIPTION_ERROR = "subscription_error"
    SUBSCRIPTION_DATA = "subscription_data"
    REDUCER_RESULT = "reducer_result"
    QUERY_RESULT = "query_result"
    HEARTBEAT = "heartbeat"
    PROTOCOL_ERROR = "protocol_error"
    CUSTOM = "custom"


@dataclass
class Event:
    """Event data structure"""
    type: EventType
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventPriority(Enum):
    """Event priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class EventSubscription:
    """Event subscription information"""
    callback: Callable
    event_type: EventType
    priority: EventPriority = EventPriority.NORMAL
    filter_func: Optional[Callable] = None
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    call_count: int = 0
    last_called: Optional[float] = None
    is_active: bool = True


class MockUnifiedEventSystem:
    """Mock unified event system to test the interface that will be extracted"""
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[EventSubscription]] = {}
        self.event_queue: queue.Queue = queue.Queue()
        self.event_history: List[Event] = []
        self.max_history_size: int = 1000
        self.processing_thread: Optional[threading.Thread] = None
        self.is_running: bool = False
        self.event_lock = threading.Lock()
        self.metrics: Dict[str, Any] = {
            'events_emitted': 0,
            'events_processed': 0,
            'subscribers_count': 0,
            'errors_count': 0,
            'processing_time': 0.0
        }
        self.error_handlers: List[Callable] = []
        self.middleware: List[Callable] = []
        self.weak_refs: Set[weakref.ref] = set()
        
    def start(self) -> None:
        """Start the event system"""
        if self.is_running:
            return
            
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_events, daemon=True)
        self.processing_thread.start()
        
    def stop(self) -> None:
        """Stop the event system"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
            
    def emit(self, event_type: EventType, data: Any = None, 
             source: str = "unknown", correlation_id: Optional[str] = None,
             metadata: Optional[Dict[str, Any]] = None) -> str:
        """Emit an event"""
        event = Event(
            type=event_type,
            data=data,
            source=source,
            correlation_id=correlation_id,
            metadata=metadata or {}
        )
        
        # Apply middleware
        for middleware in self.middleware:
            try:
                event = middleware(event)
                if event is None:
                    return ""  # Event was filtered out
            except Exception as e:
                self._handle_error(f"Middleware error: {e}")
                
        # Add to queue
        self.event_queue.put(event)
        self.metrics['events_emitted'] += 1
        
        return event.correlation_id or str(uuid.uuid4())
        
    def subscribe(self, event_type: EventType, callback: Callable,
                  priority: EventPriority = EventPriority.NORMAL,
                  filter_func: Optional[Callable] = None) -> str:
        """Subscribe to an event type"""
        subscription = EventSubscription(
            callback=callback,
            event_type=event_type,
            priority=priority,
            filter_func=filter_func
        )
        
        with self.event_lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
                
            self.subscribers[event_type].append(subscription)
            # Sort by priority (highest first)
            self.subscribers[event_type].sort(key=lambda s: s.priority.value, reverse=True)
            
        self.metrics['subscribers_count'] += 1
        
        # Create weak reference if callback is a bound method
        if hasattr(callback, '__self__'):
            weak_ref = weakref.ref(callback.__self__, self._cleanup_weak_ref)
            self.weak_refs.add(weak_ref)
            
        return subscription.subscription_id
        
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        with self.event_lock:
            for event_type, subscriptions in self.subscribers.items():
                for i, subscription in enumerate(subscriptions):
                    if subscription.subscription_id == subscription_id:
                        del subscriptions[i]
                        self.metrics['subscribers_count'] -= 1
                        return True
        return False
        
    def unsubscribe_all(self, event_type: EventType) -> int:
        """Unsubscribe all callbacks for an event type"""
        with self.event_lock:
            if event_type in self.subscribers:
                count = len(self.subscribers[event_type])
                self.subscribers[event_type].clear()
                self.metrics['subscribers_count'] -= count
                return count
        return 0
        
    def _process_events(self) -> None:
        """Process events from the queue"""
        while self.is_running:
            try:
                event = self.event_queue.get(timeout=0.1)
                self._dispatch_event(event)
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self._handle_error(f"Event processing error: {e}")
                
    def _dispatch_event(self, event: Event) -> None:
        """Dispatch an event to subscribers"""
        start_time = time.time()
        
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history_size:
            self.event_history.pop(0)
            
        # Get subscribers for this event type
        subscribers = self.subscribers.get(event.type, [])
        
        # Dispatch to subscribers
        for subscription in subscribers:
            if not subscription.is_active:
                continue
                
            try:
                # Apply filter if present
                if subscription.filter_func:
                    if not subscription.filter_func(event):
                        continue
                        
                # Call the callback
                subscription.callback(event)
                subscription.call_count += 1
                subscription.last_called = time.time()
                
            except Exception as e:
                self._handle_error(f"Callback error: {e}")
                subscription.is_active = False  # Deactivate problematic subscription
                
        # Update metrics
        self.metrics['events_processed'] += 1
        self.metrics['processing_time'] += time.time() - start_time
        
    def _handle_error(self, error: str) -> None:
        """Handle errors in event processing"""
        self.metrics['errors_count'] += 1
        
        for handler in self.error_handlers:
            try:
                handler(error)
            except Exception as e:
                print(f"Error handler failed: {e}")
                
    def _cleanup_weak_ref(self, weak_ref: weakref.ref) -> None:
        """Clean up weak references"""
        self.weak_refs.discard(weak_ref)
        
    def add_error_handler(self, handler: Callable) -> None:
        """Add an error handler"""
        self.error_handlers.append(handler)
        
    def remove_error_handler(self, handler: Callable) -> bool:
        """Remove an error handler"""
        try:
            self.error_handlers.remove(handler)
            return True
        except ValueError:
            return False
            
    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware for event processing"""
        self.middleware.append(middleware)
        
    def remove_middleware(self, middleware: Callable) -> bool:
        """Remove middleware"""
        try:
            self.middleware.remove(middleware)
            return True
        except ValueError:
            return False
            
    def get_metrics(self) -> Dict[str, Any]:
        """Get event system metrics"""
        return self.metrics.copy()
        
    def get_event_history(self, event_type: Optional[EventType] = None,
                          limit: Optional[int] = None) -> List[Event]:
        """Get event history"""
        history = self.event_history
        
        if event_type:
            history = [e for e in history if e.type == event_type]
            
        if limit:
            history = history[-limit:]
            
        return history
        
    def get_subscription_info(self, subscription_id: str) -> Optional[EventSubscription]:
        """Get subscription information"""
        for subscriptions in self.subscribers.values():
            for subscription in subscriptions:
                if subscription.subscription_id == subscription_id:
                    return subscription
        return None
        
    def get_all_subscriptions(self) -> Dict[EventType, List[EventSubscription]]:
        """Get all subscriptions"""
        return {k: v.copy() for k, v in self.subscribers.items()}
        
    def clear_event_history(self) -> None:
        """Clear event history"""
        self.event_history.clear()
        
    def wait_for_event(self, event_type: EventType, timeout: float = 5.0) -> Optional[Event]:
        """Wait for a specific event type"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check recent history
            for event in reversed(self.event_history):
                if event.type == event_type and event.timestamp >= start_time:
                    return event
                    
            time.sleep(0.01)
            
        return None
        
    def emit_and_wait(self, event_type: EventType, data: Any = None,
                      wait_for_type: Optional[EventType] = None,
                      timeout: float = 5.0) -> Optional[Event]:
        """Emit an event and wait for a response"""
        correlation_id = self.emit(event_type, data, correlation_id=str(uuid.uuid4()))
        
        if wait_for_type:
            return self.wait_for_event(wait_for_type, timeout)
        return None
        
    def bulk_emit(self, events: List[tuple]) -> List[str]:
        """Emit multiple events"""
        correlation_ids = []
        
        for event_data in events:
            if len(event_data) == 2:
                event_type, data = event_data
                correlation_id = self.emit(event_type, data)
            elif len(event_data) == 3:
                event_type, data, source = event_data
                correlation_id = self.emit(event_type, data, source)
            else:
                continue
                
            correlation_ids.append(correlation_id)
            
        return correlation_ids
        
    def pause_processing(self) -> None:
        """Pause event processing"""
        self.is_running = False
        
    def resume_processing(self) -> None:
        """Resume event processing"""
        if not self.is_running:
            self.start()


class TestUnifiedEventSystem:
    """Test unified event system functionality"""
    
    def test_event_system_initialization(self):
        """Test event system initialization"""
        system = MockUnifiedEventSystem()
        
        assert isinstance(system.subscribers, dict)
        assert isinstance(system.event_queue, queue.Queue)
        assert isinstance(system.event_history, list)
        assert system.max_history_size == 1000
        assert system.is_running is False
        assert system.processing_thread is None
        assert isinstance(system.metrics, dict)
        assert isinstance(system.error_handlers, list)
        assert isinstance(system.middleware, list)
        
    def test_event_system_start_stop(self):
        """Test starting and stopping event system"""
        system = MockUnifiedEventSystem()
        
        # Start system
        system.start()
        assert system.is_running is True
        assert system.processing_thread is not None
        
        # Stop system
        system.stop()
        assert system.is_running is False
        
    def test_event_emission(self):
        """Test event emission"""
        system = MockUnifiedEventSystem()
        
        # Emit basic event
        correlation_id = system.emit(EventType.CONNECTION_OPENED, "test_data")
        assert correlation_id != ""
        
        # Check metrics
        metrics = system.get_metrics()
        assert metrics['events_emitted'] == 1
        
        # Emit with metadata
        correlation_id = system.emit(
            EventType.AUTHENTICATION_SUCCESS,
            {"user": "test"},
            source="auth_handler",
            correlation_id="test_correlation",
            metadata={"session_id": "12345"}
        )
        assert correlation_id == "test_correlation"
        
    def test_event_subscription(self):
        """Test event subscription"""
        system = MockUnifiedEventSystem()
        
        # Track callback calls
        callback_called = False
        received_event = None
        
        def test_callback(event):
            nonlocal callback_called, received_event
            callback_called = True
            received_event = event
            
        # Subscribe to event
        subscription_id = system.subscribe(EventType.CONNECTION_OPENED, test_callback)
        assert subscription_id != ""
        
        # Check subscription was added
        subscriptions = system.get_all_subscriptions()
        assert EventType.CONNECTION_OPENED in subscriptions
        assert len(subscriptions[EventType.CONNECTION_OPENED]) == 1
        
        # Start system and emit event
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "test_data")
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check callback was called
        assert callback_called is True
        assert received_event is not None
        assert received_event.type == EventType.CONNECTION_OPENED
        assert received_event.data == "test_data"
        
        system.stop()
        
    def test_event_unsubscription(self):
        """Test event unsubscription"""
        system = MockUnifiedEventSystem()
        
        def test_callback(event):
            pass
            
        # Subscribe
        subscription_id = system.subscribe(EventType.CONNECTION_OPENED, test_callback)
        
        # Verify subscription exists
        subscriptions = system.get_all_subscriptions()
        assert len(subscriptions[EventType.CONNECTION_OPENED]) == 1
        
        # Unsubscribe
        success = system.unsubscribe(subscription_id)
        assert success is True
        
        # Verify subscription removed
        subscriptions = system.get_all_subscriptions()
        assert len(subscriptions.get(EventType.CONNECTION_OPENED, [])) == 0
        
        # Try to unsubscribe again
        success = system.unsubscribe(subscription_id)
        assert success is False
        
    def test_event_priority_handling(self):
        """Test event priority handling"""
        system = MockUnifiedEventSystem()
        
        # Track callback order
        callback_order = []
        
        def high_priority_callback(event):
            callback_order.append("high")
            
        def normal_priority_callback(event):
            callback_order.append("normal")
            
        def low_priority_callback(event):
            callback_order.append("low")
            
        # Subscribe with different priorities
        system.subscribe(EventType.CONNECTION_OPENED, normal_priority_callback, EventPriority.NORMAL)
        system.subscribe(EventType.CONNECTION_OPENED, high_priority_callback, EventPriority.HIGH)
        system.subscribe(EventType.CONNECTION_OPENED, low_priority_callback, EventPriority.LOW)
        
        # Start system and emit event
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "test_data")
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check order (high priority first)
        assert callback_order == ["high", "normal", "low"]
        
        system.stop()
        
    def test_event_filtering(self):
        """Test event filtering"""
        system = MockUnifiedEventSystem()
        
        # Track filtered events
        filtered_events = []
        all_events = []
        
        def filter_func(event):
            return event.data == "allowed"
            
        def filtered_callback(event):
            filtered_events.append(event)
            
        def all_callback(event):
            all_events.append(event)
            
        # Subscribe with filter
        system.subscribe(EventType.CONNECTION_OPENED, filtered_callback, filter_func=filter_func)
        system.subscribe(EventType.CONNECTION_OPENED, all_callback)
        
        # Start system and emit events
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "allowed")
        system.emit(EventType.CONNECTION_OPENED, "blocked")
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check filtering
        assert len(filtered_events) == 1
        assert len(all_events) == 2
        assert filtered_events[0].data == "allowed"
        
        system.stop()
        
    def test_event_history(self):
        """Test event history tracking"""
        system = MockUnifiedEventSystem()
        
        # Start system
        system.start()
        
        # Emit events
        system.emit(EventType.CONNECTION_OPENED, "data1")
        system.emit(EventType.AUTHENTICATION_SUCCESS, "data2")
        system.emit(EventType.CONNECTION_CLOSED, "data3")
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check history
        history = system.get_event_history()
        assert len(history) == 3
        assert history[0].type == EventType.CONNECTION_OPENED
        assert history[1].type == EventType.AUTHENTICATION_SUCCESS
        assert history[2].type == EventType.CONNECTION_CLOSED
        
        # Check filtered history
        conn_history = system.get_event_history(EventType.CONNECTION_OPENED)
        assert len(conn_history) == 1
        assert conn_history[0].type == EventType.CONNECTION_OPENED
        
        # Check limited history
        limited_history = system.get_event_history(limit=2)
        assert len(limited_history) == 2
        
        system.stop()
        
    def test_error_handling(self):
        """Test error handling in event processing"""
        system = MockUnifiedEventSystem()
        
        # Track errors
        errors = []
        
        def error_handler(error):
            errors.append(error)
            
        def failing_callback(event):
            raise Exception("Test error")
            
        def working_callback(event):
            pass
            
        # Add error handler
        system.add_error_handler(error_handler)
        
        # Subscribe callbacks
        system.subscribe(EventType.CONNECTION_OPENED, failing_callback)
        system.subscribe(EventType.CONNECTION_OPENED, working_callback)
        
        # Start system and emit event
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "test_data")
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check error was handled
        assert len(errors) > 0
        assert "Test error" in errors[0]
        
        # Check metrics
        metrics = system.get_metrics()
        assert metrics['errors_count'] > 0
        
        system.stop()
        
    def test_middleware_processing(self):
        """Test middleware processing"""
        system = MockUnifiedEventSystem()
        
        # Track middleware calls
        middleware_calls = []
        
        def logging_middleware(event):
            middleware_calls.append(f"log_{event.type.value}")
            return event
            
        def filtering_middleware(event):
            middleware_calls.append(f"filter_{event.type.value}")
            if event.data == "blocked":
                return None  # Filter out
            return event
            
        def enriching_middleware(event):
            middleware_calls.append(f"enrich_{event.type.value}")
            event.metadata['processed'] = True
            return event
            
        # Add middleware
        system.add_middleware(logging_middleware)
        system.add_middleware(filtering_middleware)
        system.add_middleware(enriching_middleware)
        
        # Track processed events
        processed_events = []
        
        def test_callback(event):
            processed_events.append(event)
            
        system.subscribe(EventType.CONNECTION_OPENED, test_callback)
        
        # Start system and emit events
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "allowed")
        system.emit(EventType.CONNECTION_OPENED, "blocked")
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check middleware was called
        assert len(middleware_calls) == 6  # 3 middleware x 2 events
        
        # Check filtering worked
        assert len(processed_events) == 1
        assert processed_events[0].data == "allowed"
        assert processed_events[0].metadata.get('processed') is True
        
        system.stop()
        
    def test_subscription_info(self):
        """Test subscription information retrieval"""
        system = MockUnifiedEventSystem()
        
        def test_callback(event):
            pass
            
        # Subscribe
        subscription_id = system.subscribe(
            EventType.CONNECTION_OPENED, 
            test_callback,
            EventPriority.HIGH
        )
        
        # Get subscription info
        info = system.get_subscription_info(subscription_id)
        assert info is not None
        assert info.callback == test_callback
        assert info.event_type == EventType.CONNECTION_OPENED
        assert info.priority == EventPriority.HIGH
        assert info.call_count == 0
        assert info.is_active is True
        
        # Test callback and check updated info
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "test_data")
        time.sleep(0.1)
        
        info = system.get_subscription_info(subscription_id)
        assert info.call_count == 1
        assert info.last_called is not None
        
        system.stop()
        
    def test_bulk_operations(self):
        """Test bulk event operations"""
        system = MockUnifiedEventSystem()
        
        # Track events
        received_events = []
        
        def test_callback(event):
            received_events.append(event)
            
        system.subscribe(EventType.CONNECTION_OPENED, test_callback)
        system.subscribe(EventType.AUTHENTICATION_SUCCESS, test_callback)
        
        # Bulk emit
        events = [
            (EventType.CONNECTION_OPENED, "data1"),
            (EventType.AUTHENTICATION_SUCCESS, "data2", "auth_source"),
            (EventType.CONNECTION_CLOSED, "data3")
        ]
        
        system.start()
        correlation_ids = system.bulk_emit(events)
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check results
        assert len(correlation_ids) == 3
        assert len(received_events) == 2  # Only subscribed to 2 event types
        
        system.stop()
        
    def test_unsubscribe_all(self):
        """Test unsubscribing all callbacks for event type"""
        system = MockUnifiedEventSystem()
        
        def callback1(event):
            pass
            
        def callback2(event):
            pass
            
        def callback3(event):
            pass
            
        # Subscribe multiple callbacks
        system.subscribe(EventType.CONNECTION_OPENED, callback1)
        system.subscribe(EventType.CONNECTION_OPENED, callback2)
        system.subscribe(EventType.AUTHENTICATION_SUCCESS, callback3)
        
        # Check subscriptions
        subscriptions = system.get_all_subscriptions()
        assert len(subscriptions[EventType.CONNECTION_OPENED]) == 2
        assert len(subscriptions[EventType.AUTHENTICATION_SUCCESS]) == 1
        
        # Unsubscribe all for CONNECTION_OPENED
        count = system.unsubscribe_all(EventType.CONNECTION_OPENED)
        assert count == 2
        
        # Check remaining subscriptions
        subscriptions = system.get_all_subscriptions()
        assert len(subscriptions.get(EventType.CONNECTION_OPENED, [])) == 0
        assert len(subscriptions[EventType.AUTHENTICATION_SUCCESS]) == 1
        
    def test_wait_for_event(self):
        """Test waiting for specific events"""
        system = MockUnifiedEventSystem()
        
        system.start()
        
        # Start waiting in a thread
        result = []
        
        def wait_for_event():
            event = system.wait_for_event(EventType.CONNECTION_OPENED, timeout=1.0)
            result.append(event)
            
        wait_thread = threading.Thread(target=wait_for_event)
        wait_thread.start()
        
        # Wait a bit then emit the event
        time.sleep(0.1)
        system.emit(EventType.CONNECTION_OPENED, "test_data")
        
        wait_thread.join()
        
        # Check result
        assert len(result) == 1
        assert result[0] is not None
        assert result[0].type == EventType.CONNECTION_OPENED
        
        system.stop()
        
    def test_pause_resume_processing(self):
        """Test pausing and resuming event processing"""
        system = MockUnifiedEventSystem()
        
        # Track events
        processed_events = []
        
        def test_callback(event):
            processed_events.append(event)
            
        system.subscribe(EventType.CONNECTION_OPENED, test_callback)
        
        # Start and emit event
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "data1")
        time.sleep(0.1)
        
        # Pause and emit another event
        system.pause_processing()
        system.emit(EventType.CONNECTION_OPENED, "data2")
        time.sleep(0.1)
        
        # Resume and emit third event
        system.resume_processing()
        system.emit(EventType.CONNECTION_OPENED, "data3")
        time.sleep(0.1)
        
        # Check processing
        assert len(processed_events) >= 1  # At least first event processed
        
        system.stop()
        
    def test_metrics_tracking(self):
        """Test metrics tracking"""
        system = MockUnifiedEventSystem()
        
        def test_callback(event):
            pass
            
        system.subscribe(EventType.CONNECTION_OPENED, test_callback)
        
        # Start and emit events
        system.start()
        system.emit(EventType.CONNECTION_OPENED, "data1")
        system.emit(EventType.CONNECTION_OPENED, "data2")
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check metrics
        metrics = system.get_metrics()
        assert metrics['events_emitted'] == 2
        assert metrics['events_processed'] == 2
        assert metrics['subscribers_count'] == 1
        assert metrics['processing_time'] > 0
        
        system.stop()


class TestEventSystemMockBehavior:
    """Test the mock event system behavior"""
    
    def test_mock_event_system_interface(self):
        """Test that mock event system implements expected interface"""
        system = MockUnifiedEventSystem()
        
        # Test all expected methods exist
        expected_methods = [
            'start', 'stop', 'emit', 'subscribe', 'unsubscribe', 'unsubscribe_all',
            'add_error_handler', 'remove_error_handler', 'add_middleware', 'remove_middleware',
            'get_metrics', 'get_event_history', 'get_subscription_info', 'get_all_subscriptions',
            'clear_event_history', 'wait_for_event', 'emit_and_wait', 'bulk_emit',
            'pause_processing', 'resume_processing'
        ]
        
        for method_name in expected_methods:
            assert hasattr(system, method_name), f"Missing method: {method_name}"
            assert callable(getattr(system, method_name)), f"Method {method_name} is not callable"
            
    def test_event_data_structure(self):
        """Test event data structure"""
        event = Event(
            type=EventType.CONNECTION_OPENED,
            data="test_data",
            source="test_source",
            correlation_id="test_correlation",
            metadata={"key": "value"}
        )
        
        assert event.type == EventType.CONNECTION_OPENED
        assert event.data == "test_data"
        assert event.source == "test_source"
        assert event.correlation_id == "test_correlation"
        assert event.metadata["key"] == "value"
        assert isinstance(event.timestamp, float)
        
    def test_event_subscription_data_structure(self):
        """Test event subscription data structure"""
        def test_callback(event):
            pass
            
        subscription = EventSubscription(
            callback=test_callback,
            event_type=EventType.CONNECTION_OPENED,
            priority=EventPriority.HIGH
        )
        
        assert subscription.callback == test_callback
        assert subscription.event_type == EventType.CONNECTION_OPENED
        assert subscription.priority == EventPriority.HIGH
        assert subscription.call_count == 0
        assert subscription.is_active is True
        assert isinstance(subscription.subscription_id, str)
        assert isinstance(subscription.created_at, float)