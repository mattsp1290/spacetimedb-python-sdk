#!/usr/bin/env python3
"""Debug script to analyze handler matching behavior."""

import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from spacetimedb_sdk.events.event_system import LegacyEventHandler

def test_handler_matching():
    """Test the wildcard matching behavior."""
    
    # Create handlers
    wildcard_handler = LegacyEventHandler("*", lambda x: print(f"Wildcard: {x}"))
    exact_handler = LegacyEventHandler("0", lambda x: print(f"Exact: {x}"))
    
    print("Wildcard handler:")
    print(f"  event_name: '{wildcard_handler.event_name}'")
    print(f"  is_wildcard: {wildcard_handler.is_wildcard}")
    if wildcard_handler.is_wildcard:
        print(f"  prefix: '{wildcard_handler.prefix}'")
    
    print("\nExact handler:")
    print(f"  event_name: '{exact_handler.event_name}'")
    print(f"  is_wildcard: {exact_handler.is_wildcard}")
    
    # Test matching
    test_events = ["0", "*", "test", ""]
    
    print(f"\nTesting event matching:")
    for event_name in test_events:
        wildcard_match = wildcard_handler._matches_event(event_name)
        exact_match = exact_handler._matches_event(event_name)
        print(f"  Event '{event_name}': wildcard={wildcard_match}, exact={exact_match}")

if __name__ == "__main__":
    test_handler_matching()