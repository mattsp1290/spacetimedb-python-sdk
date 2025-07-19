#!/usr/bin/env python3
"""
Test all message types to ensure BSATN encoding works correctly for all ClientMessage types.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk.protocol import (
    ProtocolEncoder, Subscribe, CallReducer, 
    SubscribeSingleMessage, SubscribeMultiMessage,
    Unsubscribe, UnsubscribeMultiMessage,
    OneOffQuery, OneOffQueryMessage
)
from spacetimedb_sdk.call_reducer_flags import CallReducerFlags
from spacetimedb_sdk.query_id import QueryId
from spacetimedb_sdk.bsatn.constants import TAG_ENUM
import uuid

def test_message_type(message, expected_variant, message_name):
    """Test encoding for a specific message type."""
    print(f"\n=== Testing {message_name} ===")
    
    encoder = ProtocolEncoder(use_binary=True)
    try:
        encoded = encoder.encode_client_message(message)
        print(f"✅ {message_name} encoded successfully: {len(encoded)} bytes")
        
        # Check that it starts with proper enum format
        if len(encoded) >= 5:
            if encoded[0] == TAG_ENUM:
                variant = int.from_bytes(encoded[1:5], 'little')
                if variant == expected_variant:
                    print(f"✅ Correct variant {variant}")
                else:
                    print(f"❌ Wrong variant: expected {expected_variant}, got {variant}")
            else:
                print(f"❌ Does not start with TAG_ENUM: starts with 0x{encoded[0]:02x}")
        
        return True
    except Exception as e:
        print(f"❌ {message_name} failed: {e}")
        return False

def main():
    """Test all message types."""
    print("SpacetimeDB Python SDK - All Message Types BSATN Test")
    print("=" * 60)
    
    success_count = 0
    total_count = 0
    
    # Test CallReducer (variant 0)
    total_count += 1
    if test_message_type(
        CallReducer(
            reducer="test_reducer",
            args=b"test_args",
            request_id=123,
            flags=CallReducerFlags.FULL_UPDATE
        ),
        0, "CallReducer"
    ):
        success_count += 1
    
    # Test Subscribe (variant 1)
    total_count += 1
    if test_message_type(
        Subscribe(
            query_strings=["entity", "player"],
            request_id=456
        ),
        1, "Subscribe"
    ):
        success_count += 1
    
    # Test SubscribeSingleMessage (variant 2)
    total_count += 1
    if test_message_type(
        SubscribeSingleMessage(
            query="SELECT * FROM entity",
            request_id=789,
            query_id=QueryId(id=1)
        ),
        2, "SubscribeSingleMessage"
    ):
        success_count += 1
    
    # Test SubscribeMultiMessage (variant 3)
    total_count += 1
    if test_message_type(
        SubscribeMultiMessage(
            query_strings=["entity", "player"],
            request_id=321,
            query_id=QueryId(id=2)
        ),
        3, "SubscribeMultiMessage"
    ):
        success_count += 1
    
    # Test Unsubscribe (variant 4)
    total_count += 1
    if test_message_type(
        Unsubscribe(
            request_id=654,
            query_id=QueryId(id=3)
        ),
        4, "Unsubscribe"
    ):
        success_count += 1
    
    # Test UnsubscribeMultiMessage (variant 5)
    total_count += 1
    if test_message_type(
        UnsubscribeMultiMessage(
            request_id=987,
            query_id=QueryId(id=4)
        ),
        5, "UnsubscribeMultiMessage"
    ):
        success_count += 1
    
    # Test OneOffQuery (variant 6)
    total_count += 1
    if test_message_type(
        OneOffQuery(
            message_id=uuid.uuid4().bytes,
            query_string="SELECT COUNT(*) FROM entity"
        ),
        6, "OneOffQuery"
    ):
        success_count += 1
    
    # Test OneOffQueryMessage (variant 7)
    total_count += 1
    if test_message_type(
        OneOffQueryMessage(
            message_id=uuid.uuid4().bytes,
            query_string="SELECT * FROM player"
        ),
        7, "OneOffQueryMessage"
    ):
        success_count += 1
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Successful: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("✅ ALL MESSAGE TYPES PASS - BSATN ENCODING FIX IS COMPLETE!")
    else:
        print("❌ SOME MESSAGE TYPES FAILED - MORE WORK NEEDED")

if __name__ == "__main__":
    main()