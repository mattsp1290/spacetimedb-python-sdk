#!/usr/bin/env python3
"""
Test for actual circular import issues at runtime.
"""

import sys
import traceback
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

def test_import(module_name):
    """Test importing a module and catch any circular import errors."""
    try:
        print(f"Testing import: {module_name}")
        module = __import__(module_name, fromlist=[''])
        print(f"✅ Successfully imported {module_name}")
        return True
    except ImportError as e:
        print(f"❌ ImportError in {module_name}: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Other error in {module_name}: {e}")
        traceback.print_exc()
        return False

def main():
    """Test imports of key modules."""
    test_modules = [
        "spacetimedb_sdk.protocol",
        "spacetimedb_sdk.query_id", 
        "spacetimedb_sdk.spacetimedb_client",
        "spacetimedb_sdk.websocket_client",
        "spacetimedb_sdk.connection_builder",
        "spacetimedb_sdk",
    ]
    
    print("🔍 Testing for runtime circular import issues...")
    
    results = []
    for module in test_modules:
        result = test_import(module)
        results.append((module, result))
        print()
    
    print("📊 Results Summary:")
    for module, success in results:
        status = "✅" if success else "❌"
        print(f"   {status} {module}")
    
    failed = [m for m, s in results if not s]
    if failed:
        print(f"\n❌ Failed imports: {len(failed)}")
        for module in failed:
            print(f"   - {module}")
    else:
        print(f"\n✅ All modules imported successfully!")

if __name__ == "__main__":
    main()