#!/usr/bin/env python3
"""
Diagnostic Tool for Blackholio AI Agent WebSocket Issues

This tool helps identify why the AI training system is still experiencing
"Invalid close frame" errors despite our fixes being applied to the SDK.
"""
import sys
import os
import json
import time
import logging
from pathlib import Path

def check_sdk_version_and_fixes():
    """Check if the latest SDK fixes are actually being used."""
    print("🔍 SDK VERSION & FIXES DIAGNOSTIC")
    print("=" * 50)
    
    try:
        # Check if our fixes are in the protocol.py file
        sdk_path = Path("src/spacetimedb_sdk/protocol.py")
        if sdk_path.exists():
            with open(sdk_path, 'r') as f:
                protocol_content = f.read()
            
            # Check for our SQL conversion fix
            if "SELECT * FROM" in protocol_content and "fix_subscription_queries" in protocol_content:
                print("✅ SQL conversion fix is present in protocol.py")
            else:
                print("❌ SQL conversion fix NOT found in protocol.py")
                print("   The AI team may be using an older SDK version")
                return False
        else:
            print("❌ SDK protocol.py not found - wrong SDK path?")
            return False
        
        # Check WebSocket client fixes
        ws_client_path = Path("src/spacetimedb_sdk/websocket_client.py")
        if ws_client_path.exists():
            with open(ws_client_path, 'r') as f:
                ws_content = f.read()
            
            # Check for our large message handling fix
            if "Processing large message" in ws_content and "invalid close frame" in ws_content.lower():
                print("✅ WebSocket large message fix is present in websocket_client.py")
            else:
                print("❌ WebSocket large message fix NOT found in websocket_client.py")
                print("   The AI team may be using an older SDK version")
                return False
        else:
            print("❌ SDK websocket_client.py not found")
            return False
        
        print("✅ All SDK fixes are present and up-to-date")
        return True
        
    except Exception as e:
        print(f"❌ Error checking SDK fixes: {e}")
        return False

def check_ai_agent_connection_implementation():
    """Check if AI agent is using custom connection that bypasses SDK fixes."""
    print("\n🤖 AI AGENT CONNECTION IMPLEMENTATION CHECK")
    print("=" * 55)
    
    # Common paths where custom connection might be
    possible_paths = [
        "src/blackholio_agent/environment/blackholio_connection_v112.py",
        "../blackholio-agent/src/blackholio_agent/environment/blackholio_connection_v112.py",
        "./blackholio_connection_v112.py",
        "./custom_connection.py"
    ]
    
    custom_connection_found = False
    
    for path in possible_paths:
        if Path(path).exists():
            print(f"🔍 Found custom connection file: {path}")
            custom_connection_found = True
            
            try:
                with open(path, 'r') as f:
                    custom_content = f.read()
                
                # Check if it has our SQL fix
                if "SELECT * FROM" in custom_content:
                    print(f"   ✅ {path} appears to have SQL conversion fix")
                else:
                    print(f"   ❌ {path} does NOT have SQL conversion fix")
                    print(f"   📋 SOLUTION: Apply fix from BLACKHOLIO_AI_AGENT_CUSTOM_CONNECTION_FIX.py")
                
                # Check if it directly sends WebSocket messages
                if "websocket.send" in custom_content.lower() or "ws.send" in custom_content.lower():
                    print(f"   ⚠️  {path} sends WebSocket messages directly")
                    print(f"   📋 This bypasses SDK fixes and may cause 'Invalid close frame' errors")
                
            except Exception as e:
                print(f"   ❌ Error reading {path}: {e}")
    
    if not custom_connection_found:
        print("✅ No custom connection files found - using standard SDK")
        print("   This means the AI agent should benefit from our SDK fixes")
    else:
        print("⚠️  Custom connection implementation detected")
        print("   This likely explains why 'Invalid close frame' errors persist")
    
    return custom_connection_found

def test_sdk_connection_directly():
    """Test if the SDK itself works correctly."""
    print("\n🧪 DIRECT SDK CONNECTION TEST")
    print("=" * 35)
    
    try:
        sys.path.insert(0, 'src')
        from spacetimedb_sdk import SpacetimeDBClient
        
        print("🔗 Testing direct SDK connection...")
        client = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="blackholio",
            auth_token=None,
            ssl_enabled=False,
            protocol="v1.json.spacetimedb",
            db_identity="c200e3d53a455398d91ad688a39a38ca59a8ce0b79863cb9df78f2866c6d31dc"
        )
        
        print("✅ SDK connection established")
        time.sleep(1)
        
        if client.identity:
            print("✅ SDK identity received")
        else:
            print("❌ SDK identity not received")
            return False
        
        # Test subscription
        subscription_id = client.subscribe(["entity", "circle", "player", "food", "config"])
        print(f"✅ SDK subscription sent (ID: {subscription_id})")
        
        # Wait for large message processing
        time.sleep(3)
        
        if client.is_connected:
            print("✅ SDK connection stable after large message")
            client.disconnect()
            print("✅ SDK clean disconnect")
            return True
        else:
            print("❌ SDK connection lost - matches AI agent error")
            return False
            
    except Exception as e:
        print(f"❌ SDK test failed: {e}")
        return False

def generate_fix_recommendations(sdk_fixes_present, custom_connection_found, sdk_test_passed):
    """Generate specific recommendations based on diagnostic results."""
    print("\n🎯 DIAGNOSTIC RESULTS & RECOMMENDATIONS")
    print("=" * 45)
    
    if not sdk_fixes_present:
        print("❌ PROBLEM: SDK fixes are missing")
        print("📋 SOLUTION:")
        print("   1. Pull latest SDK changes with git pull")
        print("   2. Verify src/spacetimedb_sdk/protocol.py contains SQL conversion")
        print("   3. Verify src/spacetimedb_sdk/websocket_client.py contains large message handling")
        print("   4. Restart AI training after SDK update")
        return
    
    if custom_connection_found:
        print("⚠️  PROBLEM: Custom connection bypasses SDK fixes")
        print("📋 SOLUTION:")
        print("   1. Apply fix from BLACKHOLIO_AI_AGENT_CUSTOM_CONNECTION_FIX.py")
        print("   2. Add fix_subscription_queries() to custom connection module")
        print("   3. Wrap all table name lists before sending to WebSocket")
        print("   4. OR: Migrate to standard SDK to benefit from all fixes")
        return
    
    if not sdk_test_passed:
        print("❌ PROBLEM: SDK test failed despite fixes being present")
        print("📋 SOLUTION:")
        print("   1. Check SpacetimeDB server is running correctly")
        print("   2. Verify blackholio database exists and is published")
        print("   3. Check for network/firewall issues")
        print("   4. Review server logs for WebSocket errors")
        return
    
    print("✅ ALL SYSTEMS WORKING: SDK fixes present and tested successfully")
    print("🤔 If AI agent still fails, possible causes:")
    print("   1. AI agent using different SDK installation")
    print("   2. AI agent environment has different dependencies")
    print("   3. AI agent error report may be outdated")
    print("   4. Different SpacetimeDB server version")
    print()
    print("📋 RECOMMENDATION: Have AI team run this diagnostic tool in their environment")

if __name__ == "__main__":
    print("🚨 BLACKHOLIO AI AGENT DIAGNOSTIC TOOL")
    print("Investigating WebSocket 'Invalid close frame' error persistence")
    print("=" * 65)
    
    # Run diagnostics
    sdk_fixes_present = check_sdk_version_and_fixes()
    custom_connection_found = check_ai_agent_connection_implementation()
    sdk_test_passed = test_sdk_connection_directly()
    
    # Generate recommendations
    generate_fix_recommendations(sdk_fixes_present, custom_connection_found, sdk_test_passed)
    
    print("\n" + "=" * 65)
    print("📧 NEXT STEPS FOR AI AGENT TEAM:")
    print("1. Run this diagnostic tool in your AI training environment")
    print("2. Compare results with this output")
    print("3. Apply recommended solutions based on differences")
    print("4. Retest AI training pipeline")
    print("5. Report back with diagnostic results if issues persist")
