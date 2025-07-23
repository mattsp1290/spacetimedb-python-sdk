#!/usr/bin/env python3
"""Debug script to understand how subscriptions work."""

import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from spacetimedb_sdk.events.event_system import EventSystem

def debug_subscriptions():
    """Debug how subscriptions are registered."""
    event_system = EventSystem()
    
    def handler1(data):
        print(f"Handler1: {data}")
    
    def handler2(data):
        print(f"Handler2: {data}")
    
    # Subscribe to wildcard
    print("Subscribing to '*' (should be wildcard)")
    event_system.subscribe("*", handler1)
    
    # Subscribe to "0" 
    print("Subscribing to '0' (should be exact match)")
    event_system.subscribe("0", handler2)
    
    # Check internal state
    print(f"\nHandler registry keys: {list(event_system._handler_registry.keys())}")
    print(f"Legacy handlers keys: {list(event_system._legacy_handlers.keys())}")
    
    # Check the UnifiedEventManager state
    manager = event_system._manager
    print(f"\nUnifiedEventManager handlers keys: {list(manager._handlers.keys())}")
    print(f"UnifiedEventManager wildcard handlers: {len(manager._wildcard_handlers)}")
    
    # Check what handlers are registered for CUSTOM events
    if 'CUSTOM' in manager._handlers:
        for priority, handler_list in manager._handlers['CUSTOM'].items():
            print(f"  Priority {priority}: {len(handler_list)} handlers")
            for handler_info in handler_list:
                print(f"    Handler {handler_info.handler_id}: {type(handler_info.handler).__name__}")
                
    # Check wildcard handlers
    for priority, handler_list in manager._wildcard_handlers.items():
        print(f"Wildcard Priority {priority}: {len(handler_list)} handlers")

if __name__ == "__main__":
    debug_subscriptions()