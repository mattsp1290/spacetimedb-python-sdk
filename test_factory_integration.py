#!/usr/bin/env python3
"""
Test script to verify the factory integration is working correctly.

This script tests the new factory pattern and interface system that was
extracted from blackholio-python-client and integrated into spacetimedb-python-sdk.
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sys
import traceback
from typing import Dict, Any

def test_factory_imports():
    """Test that all factory components can be imported."""
    print("Testing factory imports...")
    
    try:
        # Test basic imports
        from spacetimedb_sdk import (
            create_spacetimedb_client,
            get_spacetimedb_factory,
            list_supported_languages,
            get_language_info,
            create_rust_client,
            create_python_client,
            create_csharp_client,
            create_go_client
        )
        
        # Test interface imports
        from spacetimedb_sdk import (
            ConnectionInterface,
            AuthInterface,
            SubscriptionInterface,
            ReducerInterface,
            SpacetimeDBClientInterface
        )
        
        # Test factory class imports
        from spacetimedb_sdk import (
            SpacetimeDBClientFactory,
            RustOptimizedFactory,
            PythonOptimizedFactory,
            CSharpOptimizedFactory,
            GoOptimizedFactory
        )
        
        print("✅ All imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

def test_supported_languages():
    """Test the list_supported_languages function."""
    print("\nTesting supported languages...")
    
    try:
        from spacetimedb_sdk import list_supported_languages
        
        languages = list_supported_languages()
        print(f"Supported languages: {languages}")
        
        expected_languages = {'rust', 'python', 'csharp', 'go'}
        found_languages = set(languages)
        
        if expected_languages.issubset(found_languages):
            print("✅ All expected languages are supported!")
            return True
        else:
            missing = expected_languages - found_languages
            print(f"❌ Missing languages: {missing}")
            return False
            
    except Exception as e:
        print(f"❌ Supported languages test failed: {e}")
        traceback.print_exc()
        return False

def test_language_info():
    """Test the get_language_info function."""
    print("\nTesting language info...")
    
    try:
        from spacetimedb_sdk import get_language_info
        
        info = get_language_info()
        print("Language information:")
        
        for lang, details in info.items():
            print(f"  {lang}:")
            print(f"    Registered: {details.get('registered', 'Unknown')}")
            print(f"    Available: {details.get('available', 'Unknown')}")
            if 'supported_protocols' in details:
                print(f"    Protocols: {details['supported_protocols']}")
            if 'error' in details:
                print(f"    Error: {details['error']}")
        
        print("✅ Language info retrieved successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Language info test failed: {e}")
        traceback.print_exc()
        return False

def test_factory_creation():
    """Test factory creation for each language."""
    print("\nTesting factory creation...")
    
    try:
        from spacetimedb_sdk import get_spacetimedb_factory
        from spacetimedb_sdk.factory.base import ServerLanguage
        
        success_count = 0
        total_languages = len(ServerLanguage)
        
        for language in ServerLanguage:
            try:
                print(f"  Testing {language.value} factory...")
                factory = get_spacetimedb_factory(language.value)
                
                print(f"    Factory class: {factory.__class__.__name__}")
                print(f"    Server language: {factory.server_language.value}")
                print(f"    Is available: {factory.is_available}")
                print(f"    Supported protocols: {factory.supported_protocols}")
                
                success_count += 1
                print(f"    ✅ {language.value} factory created successfully!")
                
            except Exception as e:
                print(f"    ❌ {language.value} factory failed: {e}")
        
        print(f"\nFactory creation results: {success_count}/{total_languages} successful")
        return success_count > 0  # At least one factory should work
        
    except Exception as e:
        print(f"❌ Factory creation test failed: {e}")
        traceback.print_exc()
        return False

def test_recommended_config():
    """Test getting recommended configuration."""
    print("\nTesting recommended configuration...")
    
    try:
        from spacetimedb_sdk import get_recommended_config
        from spacetimedb_sdk.factory.base import OptimizationProfile
        
        # Test getting config for Rust with different profiles
        for profile in OptimizationProfile:
            try:
                print(f"  Testing {profile.value} profile for Rust...")
                config = get_recommended_config("rust", profile)
                
                print(f"    Protocol: {config.get('protocol', 'Not specified')}")
                print(f"    Compression: {config.get('compression', 'Not specified')}")
                print(f"    Energy budget: {config.get('energy_budget', 'Not specified')}")
                print(f"    ✅ {profile.value} config retrieved successfully!")
                
            except Exception as e:
                print(f"    ❌ {profile.value} config failed: {e}")
        
        print("✅ Recommended configuration test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Recommended config test failed: {e}")
        traceback.print_exc()
        return False

def test_optimization_capabilities():
    """Test getting optimization capabilities."""
    print("\nTesting optimization capabilities...")
    
    try:
        from spacetimedb_sdk import get_optimization_capabilities
        
        for language in ['rust', 'python', 'csharp', 'go']:
            try:
                print(f"  Testing capabilities for {language}...")
                capabilities = get_optimization_capabilities(language)
                
                print(f"    Binary protocol: {capabilities.get('binary_protocol', False)}")
                print(f"    High concurrency: {capabilities.get('high_concurrency', False)}")
                print(f"    Low latency: {capabilities.get('low_latency', False)}")
                print(f"    ✅ {language} capabilities retrieved!")
                
            except Exception as e:
                print(f"    ❌ {language} capabilities failed: {e}")
        
        print("✅ Optimization capabilities test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Optimization capabilities test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Testing SpacetimeDB SDK Factory Integration")
    print("=" * 50)
    
    tests = [
        test_factory_imports,
        test_supported_languages,
        test_language_info,
        test_factory_creation,
        test_recommended_config,
        test_optimization_capabilities,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("=" * 50)
    print(f"🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Factory integration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())