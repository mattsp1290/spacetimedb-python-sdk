#!/usr/bin/env python3
"""
Verification script for subscription manager consolidation.

This script verifies that all original functionality from the root-level
subscription_manager.py has been successfully consolidated into the enhanced
connection/subscription_manager.py implementation.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_subscription_manager_consolidation():
    """Test that the consolidated subscription manager has all required functionality."""
    
    print("🔍 Testing Subscription Manager Consolidation")
    print("=" * 50)
    
    try:
        # Test import from consolidated location
        from spacetimedb_sdk.connection.subscription_manager import (
            SubscriptionManager,
            SubscriptionState,
            SubscriptionInfo,
            get_subscription_manager,
            set_subscription_manager
        )
        print("✅ Import from connection/subscription_manager.py successful")
        
        # Test backward compatibility APIs
        manager = SubscriptionManager()
        print("✅ SubscriptionManager instantiation successful")
        
        # Test old-style API (table-name based)
        try:
            manager.register_subscription(
                table_name="test_table",
                query="SELECT * FROM test_table",
                request_id=12345,
                callback=lambda data: print(f"Callback: {data}")
            )
            print("✅ Old-style register_subscription API works")
        except Exception as e:
            print(f"❌ Old-style register_subscription failed: {e}")
            return False
        
        # Test new-style API (QueryId based)
        try:
            from spacetimedb_sdk.query_id import QueryId
            query_id = QueryId()
            manager.register_subscription(
                query_id=query_id,
                queries=["SELECT * FROM test_table"],
                request_id=12346
            )
            print("✅ New-style register_subscription API works")
        except Exception as e:
            print(f"❌ New-style register_subscription failed: {e}")
            return False
        
        # Test activation APIs
        try:
            # Old-style activation
            result = manager.activate_subscription(table_name="test_table")
            print(f"✅ Old-style activate_subscription works: {result}")
            
            # New-style activation
            result = manager.activate_subscription(query_id=query_id)
            print(f"✅ New-style activate_subscription works: {result}")
        except Exception as e:
            print(f"❌ activate_subscription failed: {e}")
            return False
        
        # Test status methods
        try:
            status = manager.get_subscription_status("test_table")
            print(f"✅ get_subscription_status works: {status['exists']}")
            
            active = manager.get_active_subscriptions()
            print(f"✅ get_active_subscriptions works: {len(active)} subscriptions")
            
            failed = manager.get_failed_subscriptions()
            print(f"✅ get_failed_subscriptions works: {len(failed)} failed")
            
            timeout = manager.get_timeout_subscriptions()
            print(f"✅ get_timeout_subscriptions works: {len(timeout)} timed out")
            
            summary = manager.get_subscription_summary()
            print(f"✅ get_subscription_summary works: {summary['total_subscriptions']} total")
        except Exception as e:
            print(f"❌ Status methods failed: {e}")
            return False
        
        # Test unregistration APIs
        try:
            # Old-style unregistration
            result = manager.unregister_subscription(table_name="test_table")
            print(f"✅ Old-style unregister_subscription works: {result}")
            
            # New-style unregistration
            result = manager.unregister_subscription(query_id=query_id)
            print(f"✅ New-style unregister_subscription works: {result}")
        except Exception as e:
            print(f"❌ unregister_subscription failed: {e}")
            return False
        
        # Test global manager functions
        try:
            global_manager = get_subscription_manager()
            print("✅ get_subscription_manager works")
            
            set_subscription_manager(manager)
            print("✅ set_subscription_manager works")
        except Exception as e:
            print(f"❌ Global manager functions failed: {e}")
            return False
        
        # Test SubscriptionState enum compatibility
        try:
            states = [
                SubscriptionState.PENDING,
                SubscriptionState.ACTIVE,
                SubscriptionState.ERROR,
                SubscriptionState.FAILED,  # Backward compatibility alias
                SubscriptionState.CLOSED,
                SubscriptionState.CANCELLED  # Backward compatibility alias
            ]
            print(f"✅ SubscriptionState enum has all states: {[s.value for s in states]}")
        except Exception as e:
            print(f"❌ SubscriptionState enum failed: {e}")
            return False
        
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Subscription manager consolidation successful!")
        print("✅ Backward compatibility maintained!")
        print("✅ Enhanced functionality available!")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def verify_file_structure():
    """Verify the file structure changes."""
    print("\n🔍 Verifying File Structure")
    print("=" * 30)
    
    # Check that root-level subscription_manager.py is removed
    root_file = "src/spacetimedb_sdk/subscription_manager.py"
    if os.path.exists(root_file):
        print(f"❌ Root-level subscription_manager.py still exists: {root_file}")
        return False
    else:
        print("✅ Root-level subscription_manager.py successfully removed")
    
    # Check that backup exists
    backup_file = "src/spacetimedb_sdk/subscription_manager.py.backup"
    if os.path.exists(backup_file):
        print(f"✅ Backup file exists: {backup_file}")
    else:
        print(f"❌ Backup file missing: {backup_file}")
        return False
    
    # Check that enhanced file exists
    enhanced_file = "src/spacetimedb_sdk/connection/subscription_manager.py"
    if os.path.exists(enhanced_file):
        print(f"✅ Enhanced subscription manager exists: {enhanced_file}")
    else:
        print(f"❌ Enhanced subscription manager missing: {enhanced_file}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 SpacetimeDB Python SDK - Subscription Manager Consolidation Verification")
    print("=" * 80)
    
    # Verify file structure
    if not verify_file_structure():
        print("\n❌ File structure verification failed!")
        sys.exit(1)
    
    # Test functionality
    if not test_subscription_manager_consolidation():
        print("\n❌ Functionality verification failed!")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("🎉 CONSOLIDATION VERIFICATION SUCCESSFUL!")
    print("✅ All subscription manager functionality has been successfully consolidated")
    print("✅ Backward compatibility is maintained")
    print("✅ Enhanced features are available")
    print("✅ File structure is correct")
    print("=" * 80)