#!/usr/bin/env python3
"""Debug script to reproduce the event system bug."""

import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from spacetimedb_sdk.events.event_system import EventSystem

def debug_event_processing():
    """Debug the event processing issue."""
    event_system = EventSystem()
    received_events = []
    call_details = []
    
    def handler(data):
        received_events.append(data)
        call_details.append(f"Handler called with data: {data}")
        print(f"Handler called with data: {data}")
    
    # This reproduces the failing test case
    events = [('0', {}), ('*', {})]
    
    # Subscribe to all unique event names (this includes "*")
    event_names = set(event_name for event_name, _ in events)
    print(f"Event names to subscribe to: {event_names}")
    
    for event_name in event_names:
        print(f"Subscribing handler to event: '{event_name}'")
        event_system.subscribe(event_name, handler)
    
    # Emit all events
    print("\nEmitting events...")
    for event_name, event_data in events:
        print(f"Emitting event: '{event_name}' with data: {event_data}")
        event_system.emit(event_name, event_data)
    
    print(f"\nExpected: {len(events)} events processed")
    print(f"Actual: {len(received_events)} events processed")
    print(f"Event details: {call_details}")
    
    return len(received_events), len(events)

if __name__ == "__main__":
    debug_event_processing()