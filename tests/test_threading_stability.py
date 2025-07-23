"""
Test suite for threading stability improvements in SpacetimeDB SDK.

This test validates the async/threading stability fixes implemented for:
- asyncio variable scoping issues during cleanup
- thread safety in connection manager
- proper cleanup sequencing to prevent race conditions
"""

import pytest
import threading
import time
import asyncio
import concurrent.futures
from unittest.mock import Mock, patch

from src.spacetimedb_sdk.events.event_manager import UnifiedEventManager, get_event_manager
from src.spacetimedb_sdk.connection.connection_manager import ConnectionManager, ConnectionConfig
from src.spacetimedb_sdk.events.core_events import BaseEvent as Event, EventType, EventPriority


class TestAsyncioCleanupStability:
    """Test asyncio variable scoping fixes during cleanup."""
    
    def test_event_manager_cleanup_without_asyncio(self):
        """Test that event manager cleanup doesn't crash when asyncio is unavailable."""
        manager = UnifiedEventManager(enable_async=False)
        
        # Simulate asyncio module being unavailable during cleanup
        with patch.dict('sys.modules', {'asyncio': None}):
            # This should not raise an exception
            manager._cleanup_event_loop()
            
        # Ensure cleanup succeeded
        assert manager._owned_loop is None
        assert manager._event_queue is None
        assert manager._processing_task is None
        assert manager._shutdown_event is None
    
    def test_event_manager_destructor_stability(self):
        """Test that __del__ method handles asyncio unavailability gracefully."""
        manager = UnifiedEventManager(enable_async=False)
        manager._is_shutting_down = False
        
        # Simulate asyncio module being unavailable during destruction
        with patch.dict('sys.modules', {'asyncio': None}):
            # This should not raise an exception
            manager.__del__()
    
    def test_global_event_manager_cleanup_robustness(self):
        """Test that global event manager cleanup handles errors gracefully."""
        from src.spacetimedb_sdk.events.event_manager import cleanup_global_event_manager
        
        # Should not raise exceptions even if global manager is None
        cleanup_global_event_manager()
        
        # Should not raise exceptions even if cleanup fails
        with patch('src.spacetimedb_sdk.events.event_manager._global_event_manager') as mock_manager:
            mock_manager._is_shutting_down = False
            mock_manager._cleanup_event_loop.side_effect = Exception("Cleanup error")
            
            # This should not propagate the exception
            cleanup_global_event_manager()


class TestConnectionManagerThreadSafety:
    """Test thread safety improvements in connection manager."""
    
    def test_concurrent_disconnect_calls(self):
        """Test that multiple concurrent disconnect calls don't cause race conditions."""
        manager = ConnectionManager()
        manager._test_mode = True  # Enable test mode for faster timeouts
        
        # Set up a mock connection
        mock_connection = Mock()
        mock_thread = Mock()
        mock_thread.is_alive.return_value = False
        
        manager._connection = mock_connection
        manager._connection_thread = mock_thread
        
        # Run multiple disconnect calls concurrently
        def disconnect_worker():
            manager.disconnect()
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=disconnect_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=2.0)
        
        # Verify all threads completed successfully
        for thread in threads:
            assert not thread.is_alive()
        
        # Verify final state is consistent
        assert manager._connection is None
        assert manager._connection_thread is None
    
    def test_callback_deadlock_prevention(self):
        """Test that callbacks are called outside of locks to prevent deadlocks."""
        manager = ConnectionManager()
        
        callback_called = threading.Event()
        callback_thread_id = None
        
        def test_callback(ws):
            nonlocal callback_thread_id
            callback_thread_id = threading.get_ident()
            # Simulate a callback that tries to call back into the manager
            # This should not deadlock
            state = manager.get_connection_state()
            callback_called.set()
        
        manager.set_callbacks(on_open=test_callback)
        
        # Simulate WebSocket open event
        manager._on_ws_open(Mock())
        
        # Verify callback was called
        assert callback_called.wait(timeout=1.0)
        assert callback_thread_id is not None


class TestEventManagerShutdownSequencing:
    """Test proper shutdown sequencing to prevent race conditions."""
    
    @pytest.mark.asyncio
    async def test_orderly_shutdown_sequence(self):
        """Test that shutdown follows proper sequencing."""
        manager = UnifiedEventManager(enable_async=True, max_worker_threads=2)
        
        # Add some handlers and events
        handler_called = []
        
        def test_handler(context):
            handler_called.append(threading.get_ident())
            time.sleep(0.1)  # Simulate work
        
        manager.on(EventType.CUSTOM, test_handler)
        
        # Emit some events
        for i in range(3):
            event = Event(
                type=EventType.CUSTOM,
                data={"test": f"event_{i}"},
                priority=EventPriority.NORMAL
            )
            await manager.emit_async(event)
        
        # Allow some processing time
        await asyncio.sleep(0.05)
        
        # Now shutdown - this should wait for current events to complete
        await manager.shutdown()
        
        # Verify shutdown completed properly
        assert manager._is_shutting_down
        assert manager._thread_pool is None
        assert manager._owned_loop is None
        
        # Verify events were processed
        assert len(handler_called) > 0
    
    @pytest.mark.asyncio
    async def test_shutdown_prevents_new_events(self):
        """Test that shutdown prevents new events from being processed."""
        manager = UnifiedEventManager(enable_async=True)
        
        handler_calls = []
        
        def test_handler(context):
            handler_calls.append(context.event.data)
        
        manager.on(EventType.CUSTOM, test_handler)
        
        # Start shutdown process
        manager._is_shutting_down = True
        
        # Try to emit an event after shutdown started
        event = Event(
            type=EventType.CUSTOM,
            data={"test": "should_not_process"},
            priority=EventPriority.NORMAL
        )
        
        # This should not process the event
        result = await manager.emit_async(event)
        
        # Allow time for any processing
        await asyncio.sleep(0.1)
        
        # Verify event was not processed
        assert len(handler_calls) == 0


class TestConcurrentOperationsStability:
    """Test stability under concurrent operations."""
    
    def test_concurrent_event_manager_operations(self):
        """Test concurrent operations on event manager."""
        manager = UnifiedEventManager(enable_async=False)  # Use sync for simpler testing
        
        results = []
        errors = []
        
        def worker_subscribe():
            try:
                def handler(context):
                    results.append(f"handled_{threading.get_ident()}")
                
                handler_id = manager.on(EventType.CUSTOM, handler)
                results.append(f"subscribed_{handler_id}")
            except Exception as e:
                errors.append(e)
        
        def worker_emit():
            try:
                event = Event(
                    type=EventType.CUSTOM,
                    data={"worker": threading.get_ident()},
                    priority=EventPriority.NORMAL
                )
                context = manager.emit(event)
                results.append(f"emitted_{context.event.metadata.event_id}")
            except Exception as e:
                errors.append(e)
        
        def worker_cleanup():
            try:
                manager.clear_all_handlers()
                results.append(f"cleared_{threading.get_ident()}")
            except Exception as e:
                errors.append(e)
        
        # Run concurrent operations
        threads = []
        
        # Start multiple workers of each type
        for _ in range(3):
            threads.append(threading.Thread(target=worker_subscribe))
            threads.append(threading.Thread(target=worker_emit))
        
        # Add one cleanup worker
        threads.append(threading.Thread(target=worker_cleanup))
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=2.0)
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Verify operations completed (we expect some results)
        assert len(results) > 0
    
    def test_memory_cleanup_under_load(self):
        """Test that memory cleanup works correctly under concurrent load."""
        from src.spacetimedb_sdk.events.event_manager import get_event_manager
        
        manager = get_event_manager()
        initial_handler_count = len(manager._handlers)
        
        def stress_worker():
            # Add and remove handlers rapidly
            for i in range(10):
                def handler(context):
                    pass
                
                handler_id = manager.on(EventType.CUSTOM, handler)
                
                # Emit some events
                event = Event(
                    type=EventType.CUSTOM,
                    data={"iteration": i},
                    priority=EventPriority.NORMAL
                )
                manager.emit(event)
                
                # Remove handler
                manager.off(EventType.CUSTOM, handler_id)
        
        # Run multiple stress workers
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=stress_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify memory was cleaned up properly
        final_handler_count = len(manager._handlers)
        
        # We should not have significantly more handlers than we started with
        assert final_handler_count <= initial_handler_count + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])