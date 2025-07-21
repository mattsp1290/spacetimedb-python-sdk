#!/usr/bin/env python3
"""
Test script to verify the event system compatibility layer works correctly.

This script tests that:
1. Legacy EventEmitter API still works 
2. Legacy SDKEventManager API still works
3. Deprecation warnings are shown
4. Events are properly converted between legacy and modern formats
5. No breaking changes in existing functionality
"""

import warnings
import sys
import contextlib
from io import StringIO


def capture_warnings():
    """Context manager to capture deprecation warnings."""
    captured_warnings = []
    
    def warning_handler(message, category, filename, lineno, file=None, line=None):
        if category == DeprecationWarning:
            captured_warnings.append(str(message))
    
    old_showwarning = warnings.showwarning
    warnings.showwarning = warning_handler
    
    class WarningCapture:
        def __enter__(self):
            return captured_warnings
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            warnings.showwarning = old_showwarning
    
    return WarningCapture()


def test_legacy_event_emitter():
    """Test that legacy EventEmitter still works with compatibility layer."""
    print("🧪 Testing Legacy EventEmitter...")
    
    with capture_warnings() as warnings_list:
        # Import legacy EventEmitter - should work but show deprecation warning
        from spacetimedb_sdk.event_system import EventEmitter, EventType, create_event
        
        # Create event emitter - should show deprecation warning
        emitter = EventEmitter("TestEmitter")
        
        # Test event handler registration
        events_received = []
        
        def test_handler(context):
            events_received.append({
                'type': context.event_type,
                'data': context.event.data if hasattr(context.event, 'data') else None
            })
        
        # Register handler
        handler_id = emitter.on(EventType.CONNECTION_ESTABLISHED, test_handler)
        assert handler_id is not None, "Handler registration should return ID"
        
        # Create and emit event
        event = create_event(EventType.CONNECTION_ESTABLISHED, {"status": "connected"})
        context = emitter.emit(event)
        
        # Verify event was processed
        assert len(events_received) == 1, f"Expected 1 event, got {len(events_received)}"
        assert events_received[0]['type'] == EventType.CONNECTION_ESTABLISHED
        
        # Test handler removal
        removed = emitter.off(EventType.CONNECTION_ESTABLISHED, handler_id)
        assert removed, "Handler removal should succeed"
        
        # Test metrics
        metrics = emitter.get_metrics()
        assert 'events_emitted' in metrics, "Metrics should include events_emitted"
        assert metrics['events_emitted'] >= 1, "Should have emitted at least 1 event"
        
    # Verify deprecation warnings were shown
    assert len(warnings_list) > 0, "Should have shown deprecation warnings"
    print(f"  ✅ Legacy EventEmitter works (with {len(warnings_list)} deprecation warnings)")
    return True


def test_legacy_sdk_event_manager():
    """Test that legacy SDKEventManager still works."""
    print("🧪 Testing Legacy SDKEventManager...")
    
    with capture_warnings() as warnings_list:
        from spacetimedb_sdk.event_manager import SDKEventManager, EventType, get_event_manager
        
        # Create SDK event manager - should show deprecation warning
        manager = SDKEventManager("TestSDK")
        
        # Test event handler registration
        events_received = []
        
        def test_handler(event_data):
            events_received.append({
                'type': event_data.event_type.value,
                'data': event_data.data,
                'source': event_data.source
            })
        
        # Register handler
        success = manager.register_handler(EventType.CONNECTION_OPENED, test_handler)
        assert success, "Handler registration should succeed"
        
        # Emit event
        handler_count = manager.emit_event(
            EventType.CONNECTION_OPENED,
            {"connection_id": "test123"},
            source="TestClient"
        )
        assert handler_count >= 1, f"Should have called at least 1 handler, got {handler_count}"
        
        # Verify event was processed
        assert len(events_received) == 1, f"Expected 1 event, got {len(events_received)}"
        assert events_received[0]['type'] == EventType.CONNECTION_OPENED.value
        assert events_received[0]['data']['connection_id'] == "test123"
        assert events_received[0]['source'] == "TestClient"
        
        # Test statistics
        stats = manager.get_statistics()
        assert 'events_emitted' in stats, "Stats should include events_emitted"
        assert stats['events_emitted'] >= 1, "Should have emitted at least 1 event"
        
        # Test global instance
        global_manager = get_event_manager()
        assert global_manager is not None, "Global manager should be available"
        
    # Verify deprecation warnings were shown
    assert len(warnings_list) > 0, "Should have shown deprecation warnings"
    print(f"  ✅ Legacy SDKEventManager works (with {len(warnings_list)} deprecation warnings)")
    return True


def test_legacy_global_event_bus():
    """Test that global_event_bus still works."""
    print("🧪 Testing Legacy Global Event Bus...")
    
    with capture_warnings() as warnings_list:
        from spacetimedb_sdk.event_system import global_event_bus, EventType, create_event
        
        # Test global event bus
        events_received = []
        
        def test_handler(context):
            events_received.append(context.event_type)
        
        # Register handler on global bus
        handler_id = global_event_bus.on(EventType.DATABASE_UPDATE, test_handler)
        assert handler_id is not None, "Global bus handler registration should return ID"
        
        # Emit event through global bus
        event = create_event(EventType.DATABASE_UPDATE, {"changes": 5})
        global_event_bus.emit(event)
        
        # Verify event was processed
        assert len(events_received) == 1, f"Expected 1 event, got {len(events_received)}"
        assert events_received[0] == EventType.DATABASE_UPDATE
        
    print(f"  ✅ Legacy Global Event Bus works (with {len(warnings_list)} deprecation warnings)")
    return True


def test_modern_system_compatibility():
    """Test that modern system works and interoperates with legacy."""
    print("🧪 Testing Modern System Compatibility...")
    
    try:
        from spacetimedb_sdk.events import get_event_manager, EventType, Event, EventPriority
        
        # Get modern event manager
        manager = get_event_manager()
        
        # Test modern event creation and emission
        events_received = []
        
        def modern_handler(context):
            events_received.append({
                'type': context.event.type.value,
                'priority': context.event.priority.value,
                'data': context.event.data
            })
        
        # Register handler
        handler_id = manager.on(EventType.TABLE_ROW_INSERT, modern_handler)
        
        # Create modern event
        event = Event(
            type=EventType.TABLE_ROW_INSERT,
            data={"table": "users", "row_id": 123},
            priority=EventPriority.HIGH
        )
        
        # Emit event
        context = manager.emit(event)
        assert context is not None, "Emit should return context"
        
        # Verify event was processed
        assert len(events_received) == 1, f"Expected 1 event, got {len(events_received)}"
        assert events_received[0]['type'] == EventType.TABLE_ROW_INSERT.value
        assert events_received[0]['priority'] == EventPriority.HIGH.value
        
        print("  ✅ Modern system works correctly")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  Modern system not available: {e}")
        return False


def test_no_breaking_changes():
    """Test that no breaking changes occurred in existing APIs."""
    print("🧪 Testing No Breaking Changes...")
    
    # Test that all expected legacy exports are available
    legacy_exports = [
        ('spacetimedb_sdk.event_system', ['EventEmitter', 'EventType', 'EventContext', 'create_event']),
        ('spacetimedb_sdk.event_manager', ['SDKEventManager', 'EventType', 'EventData', 'get_event_manager']),
    ]
    
    for module_name, expected_exports in legacy_exports:
        try:
            module = __import__(module_name, fromlist=expected_exports)
            for export in expected_exports:
                assert hasattr(module, export), f"{module_name} should export {export}"
            print(f"  ✅ {module_name} exports intact")
        except ImportError as e:
            print(f"  ❌ Failed to import {module_name}: {e}")
            return False
    
    # Test that basic API patterns still work
    try:
        # EventEmitter pattern
        from spacetimedb_sdk.event_system import EventEmitter
        emitter = EventEmitter()
        assert hasattr(emitter, 'on'), "EventEmitter should have 'on' method"
        assert hasattr(emitter, 'emit'), "EventEmitter should have 'emit' method"
        assert hasattr(emitter, 'off'), "EventEmitter should have 'off' method"
        
        # SDKEventManager pattern
        from spacetimedb_sdk.event_manager import SDKEventManager
        manager = SDKEventManager()
        assert hasattr(manager, 'register_handler'), "SDKEventManager should have 'register_handler' method"
        assert hasattr(manager, 'emit_event'), "SDKEventManager should have 'emit_event' method"
        
        print("  ✅ API patterns preserved")
        return True
        
    except Exception as e:
        print(f"  ❌ API pattern test failed: {e}")
        return False


def main():
    """Run all compatibility tests."""
    print("SpacetimeDB SDK Event System Compatibility Test")
    print("=" * 50)
    
    # Suppress deprecation warnings for cleaner output during tests
    # (we capture them explicitly in test functions)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    tests = [
        test_legacy_event_emitter,
        test_legacy_sdk_event_manager,
        test_legacy_global_event_bus,
        test_modern_system_compatibility,
        test_no_breaking_changes,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__} failed: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED - Compatibility layer working correctly!")
        print("\nKey findings:")
        print("✅ Legacy EventEmitter API preserved")
        print("✅ Legacy SDKEventManager API preserved") 
        print("✅ Deprecation warnings shown appropriately")
        print("✅ Modern event system functional")
        print("✅ No breaking changes detected")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Compatibility issues detected!")
        return 1


if __name__ == "__main__":
    sys.exit(main())