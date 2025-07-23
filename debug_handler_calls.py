#!/usr/bin/env python3
"""Debug script to trace handler calls."""

import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from spacetimedb_sdk.events.event_system import EventSystem

def debug_handler_calls():
    """Debug exactly which handlers get called and why."""
    event_system = EventSystem()
    
    def handler_star(data):
        print(f"* handler called with: {data}")
    
    def handler_0(data):
        print(f"0 handler called with: {data}")
    
    # Subscribe handlers
    event_system.subscribe("*", handler_star)
    event_system.subscribe("0", handler_0)
    
    print("=== Emitting event '0' ===")
    event_system.emit("0", {"test": "data"})
    
    print("\n=== Emitting event '*' ===")
    event_system.emit("*", {"test": "data"})
    
    print("\n=== Emitting event 'other' ===")
    event_system.emit("other", {"test": "data"})

if __name__ == "__main__":
    debug_handler_calls()