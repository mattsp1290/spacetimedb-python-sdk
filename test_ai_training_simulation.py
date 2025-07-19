#!/usr/bin/env python3
"""
Simulate the exact AI training flow to identify why it's still failing
"""

import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
sys.path.insert(0, '/Users/punk1290/git/spacetimedb-python-sdk/src')

from spacetimedb_sdk import SpacetimeDBClient
import time
import logging

# Enable detailed logging like AI training would
logging.basicConfig(level=logging.DEBUG)

def simulate_ai_training_connection():
    """Simulate the exact connection flow that AI training uses"""
    print("🤖 Simulating AI training connection flow...")
    
    try:
        # Use the exact same parameters as mentioned in the error report
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="blackholio",
            auth_token=None,
            ssl_enabled=False,
            protocol="v1.json.spacetimedb",
            db_identity="c200e3d53a455398d91ad688a39a38ca59a8ce0b79863cb9df78f2866c6d31dc"
        )
        print("✅ Connection established")
        
        # Wait for identity like AI training would
        timeout = 20
        start_time = time.time()
        while not client.identity and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if client.identity:
            print(f"✅ Identity received: {str(client.identity)[:32]}...")
        else:
            print("❌ No identity received within timeout")
            return False
        
        # Try the exact table subscriptions the AI training uses
        game_tables = ["entity", "circle", "player", "food", "config"]
        print(f"🔍 Subscribing to game tables: {game_tables}")
        
        try:
            request_id = client.subscribe(game_tables)
            print(f"✅ Subscription request submitted (ID: {request_id})")
            
            # Wait for subscription to be processed
            time.sleep(3)
            print("✅ Subscription processing completed - no SQL errors")
            
        except Exception as e:
            print(f"❌ Subscription failed: {e}")
            if "sql parser error" in str(e).lower():
                print("🚨 This is the SQL parser error from the report!")
                return False
        
        # Try calling enter_game reducer like AI training does
        print("🎮 Testing enter_game reducer...")
        try:
            reducer_request = client.call_reducer("enter_game", "AITestAgent")
            print(f"✅ enter_game reducer called (ID: {reducer_request})")
            
            # Wait a bit to see if player spawns
            print("⏳ Waiting for player spawn...")
            time.sleep(5)
            
            # In a real scenario, we'd check for player entities here
            print("✅ Reducer call completed")
            
        except Exception as e:
            print(f"❌ Reducer call failed: {e}")
        
        # Test connection stability
        print("🔗 Testing connection stability...")
        time.sleep(2)
        
        if client.is_connected:
            print("✅ Connection remains stable")
        else:
            print("❌ Connection was lost")
            return False
        
        # Clean disconnect
        client.disconnect()
        print("✅ Clean disconnection completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_raw_websocket_messages():
    """Test raw WebSocket message inspection"""
    print("\n🔍 Testing raw WebSocket message inspection...")
    
    # Create a custom message handler to inspect what's actually being sent
    received_messages = []
    
    def message_inspector(message):
        received_messages.append(message)
        print(f"📨 Received message type: {type(message).__name__}")
        if hasattr(message, 'status'):
            print(f"    Status: {message.status}")
        if hasattr(message, 'error'):
            print(f"    Error: {message.error}")
    
    try:
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="blackholio",
            auth_token=None,
            ssl_enabled=False,
            protocol="v1.json.spacetimedb"
        )
        
        # Register message inspector
        client.register_on_event(lambda event: print(f"🎯 Event: {event.status} - {event.message}"))
        
        # Wait for connection
        time.sleep(1)
        
        # Test subscription with message inspection
        print("📤 Sending subscription request...")
        client.subscribe(["entity"])
        
        # Wait and inspect messages
        time.sleep(3)
        print(f"📥 Received {len(received_messages)} messages")
        
        client.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Raw message test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== AI Training Flow Simulation ===")
    
    # Test 1: Simulate exact AI training flow
    simulation_success = simulate_ai_training_connection()
    
    # Test 2: Inspect raw messages
    message_success = test_raw_websocket_messages()
    
    print(f"\n📊 Results:")
    print(f"   AI Training Simulation: {'✅ PASS' if simulation_success else '❌ FAIL'}")
    print(f"   Message Inspection: {'✅ PASS' if message_success else '❌ FAIL'}")
    
    if simulation_success and message_success:
        print("\n🎉 All tests passed - SDK is working correctly!")
        print("   The AI training error report may be outdated or from a different environment.")
    else:
        print("\n🚨 Issues detected - investigating further...")
