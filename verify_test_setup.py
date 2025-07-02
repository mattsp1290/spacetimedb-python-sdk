#!/usr/bin/env python3
"""
Test Setup Verification Script

Verifies that the integration test suite can be imported and basic
functionality works before running the full test suite.
"""

import sys
import traceback
from pathlib import Path

# Add src to Python path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def verify_imports():
    """Verify all required imports work."""
    
    print("🔍 Verifying imports...")
    
    try:
        # Core SDK imports
        from spacetimedb_sdk.websocket_client import ModernWebSocketClient, SubscriptionMetrics
        from spacetimedb_sdk.message_validator import SpacetimeDBMessageValidator, MessageValidationError
        from spacetimedb_sdk.large_message_handler import LargeMessageHandler
        from spacetimedb_sdk.connection_recovery import RobustConnectionManager
        print("✅ Core SDK imports successful")
        
        # Test framework imports
        import pytest
        print("✅ Pytest import successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

def verify_basic_functionality():
    """Verify basic functionality of core components."""
    
    print("\n🧪 Testing basic functionality...")
    
    try:
        # Test message validation
        from spacetimedb_sdk.message_validator import SpacetimeDBMessageValidator
        
        test_message = {
            "CallReducer": {
                "reducer": "test_reducer",
                "args": {"test": "data"},
                "request_id": 123
            }
        }
        
        result = SpacetimeDBMessageValidator.validate_message(test_message)
        assert result == True
        print("✅ Message validation working")
        
        # Test subscription metrics
        from spacetimedb_sdk.websocket_client import SubscriptionMetrics
        
        metrics = SubscriptionMetrics()
        metrics.record_subscription_data("test_table", 100)
        health = metrics.get_subscription_health("test_table")
        assert health['message_count'] == 1
        assert health['total_bytes'] == 100
        print("✅ Subscription metrics working")
        
        # Test WebSocket client creation
        from spacetimedb_sdk.websocket_client import ModernWebSocketClient
        from spacetimedb_sdk.protocol import TEXT_PROTOCOL
        
        client = ModernWebSocketClient(protocol=TEXT_PROTOCOL)
        assert client.protocol == TEXT_PROTOCOL
        assert client.use_binary == False
        print("✅ WebSocket client creation working")
        
        # Test large message handler
        from spacetimedb_sdk.large_message_handler import LargeMessageHandler
        
        sent_messages = []
        handler = LargeMessageHandler(lambda x: sent_messages.append(x))
        
        small_message = "test message"
        handler.send_large_message(small_message, "test")
        assert len(sent_messages) == 1
        print("✅ Large message handler working")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        traceback.print_exc()
        return False

def verify_test_files():
    """Verify test files exist and can be imported."""
    
    print("\n📁 Verifying test files...")
    
    test_files = [
        "test_sdk_client_integration.py",
        "test_performance_benchmarks.py", 
        "test_error_scenarios.py"
    ]
    
    tests_dir = current_dir / "tests"
    
    for test_file in test_files:
        test_path = tests_dir / test_file
        if test_path.exists():
            print(f"✅ {test_file} exists")
        else:
            print(f"❌ {test_file} missing")
            return False
    
    # Try importing test modules
    try:
        sys.path.insert(0, str(tests_dir))
        
        import test_sdk_client_integration
        print("✅ test_sdk_client_integration imports successfully")
        
        import test_performance_benchmarks
        print("✅ test_performance_benchmarks imports successfully")
        
        import test_error_scenarios  
        print("✅ test_error_scenarios imports successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Test file import failed: {e}")
        return False

def main():
    """Main verification function."""
    
    print("🚀 SpacetimeDB Python SDK Test Setup Verification")
    print("=" * 60)
    
    all_passed = True
    
    # Run verifications
    if not verify_imports():
        all_passed = False
    
    if not verify_basic_functionality():
        all_passed = False
        
    if not verify_test_files():
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All verification checks passed!")
        print("✅ Integration test suite is ready to run")
        print("\nNext steps:")
        print("  python run_integration_tests.py --fast")
        print("  python run_integration_tests.py --verbose")
    else:
        print("❌ Some verification checks failed")
        print("🔧 Please fix the issues above before running tests")
        
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())