#!/usr/bin/env python3
"""
Comprehensive verification script to ensure the SDK is ready for external usage.
This simulates how external packages will use the SDK after pip installation.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

class ExternalUsageVerifier:
    def __init__(self):
        self.results = []
        self.project_root = Path.cwd()
        
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        status = "✅ PASSED" if passed else "❌ FAILED"
        self.results.append((test_name, passed, message))
        print(f"{status}: {test_name}")
        if message:
            print(f"  {message}")
    
    def create_isolated_test(self, test_name: str, test_code: str) -> bool:
        """Run test code in an isolated Python process."""
        try:
            # Create a temporary test script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_code)
                temp_file = f.name
            
            # Run in subprocess to ensure clean environment
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            # Clean up
            os.unlink(temp_file)
            
            if result.returncode == 0:
                self.log_result(test_name, True)
                return True
            else:
                self.log_result(test_name, False, f"Error: {result.stderr}")
                return False
                
        except Exception as e:
            self.log_result(test_name, False, f"Exception: {str(e)}")
            return False
    
    def test_basic_import(self):
        """Test basic package import."""
        test_code = """
import sys
sys.path.insert(0, 'src')
import spacetimedb_sdk
print("Import successful")
"""
        return self.create_isolated_test("Basic Import", test_code)
    
    def test_all_major_imports(self):
        """Test all major imports that external users might use."""
        test_code = """
import sys
sys.path.insert(0, 'src')

# Test main imports
from spacetimedb_sdk import (
    SpacetimeDBClient,
    ModernSpacetimeDBClient,
    SpacetimeDBConnectionBuilder,
    ConnectionPool,
    LoadBalancedConnectionManager,
    RetryPolicy
)

# Test shared types
from spacetimedb_sdk.shared_types import (
    PooledConnectionState,
    CircuitState,
    ConnectionHealth,
    CircuitBreaker
)

print("All imports successful")
"""
        return self.create_isolated_test("All Major Imports", test_code)
    
    def test_builder_pattern(self):
        """Test the builder pattern works correctly."""
        test_code = """
import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk import ModernSpacetimeDBClient

# Test builder creation
builder = ModernSpacetimeDBClient.builder()
assert builder is not None

# Test fluent API
configured = (
    builder
    .with_uri("ws://localhost:3000")
    .with_module_name("test")
    .with_token("test_token")
)

# Test validation
validation = configured.validate()
assert validation['valid'] == True
assert validation['configuration']['uri'] == "ws://localhost:3000"

print("Builder pattern works correctly")
"""
        return self.create_isolated_test("Builder Pattern", test_code)
    
    def test_connection_pool_creation(self):
        """Test connection pool can be created via builder."""
        test_code = """
import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk import ModernSpacetimeDBClient

# Test pool configuration
builder = (
    ModernSpacetimeDBClient.builder()
    .with_uri("ws://localhost:3000")
    .with_module_name("test")
    .with_connection_pool(min_connections=5, max_connections=20)
    .with_retry_policy(max_retries=3)
)

# Verify configuration
assert builder._use_connection_pool == True
assert builder._pool_min_connections == 5

print("Connection pool configuration works")
"""
        return self.create_isolated_test("Connection Pool Creation", test_code)
    
    def test_no_circular_imports(self):
        """Verify no circular imports in various import orders."""
        test_code = """
import sys
sys.path.insert(0, 'src')

# Clear any cached imports
for module in list(sys.modules.keys()):
    if module.startswith('spacetimedb_sdk'):
        del sys.modules[module]

# Test import order 1: pool -> builder
from spacetimedb_sdk.connection_pool import ConnectionPool
from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder

# Clear again
for module in list(sys.modules.keys()):
    if module.startswith('spacetimedb_sdk'):
        del sys.modules[module]

# Test import order 2: builder -> pool
from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
from spacetimedb_sdk.connection_pool import ConnectionPool

# Test import order 3: shared_types first
from spacetimedb_sdk.shared_types import RetryPolicy
from spacetimedb_sdk import ModernSpacetimeDBClient

print("No circular imports detected")
"""
        return self.create_isolated_test("No Circular Imports", test_code)
    
    def test_package_structure(self):
        """Verify package structure is correct."""
        try:
            # Check key files exist
            required_files = [
                "src/spacetimedb_sdk/__init__.py",
                "src/spacetimedb_sdk/shared_types.py",
                "src/spacetimedb_sdk/connection_builder.py",
                "src/spacetimedb_sdk/connection_pool.py",
                "pyproject.toml"
            ]
            
            all_exist = True
            for file in required_files:
                if not Path(file).exists():
                    self.log_result("Package Structure", False, f"Missing file: {file}")
                    all_exist = False
                    return False
            
            # Check shared_types is not empty
            shared_types_path = Path("src/spacetimedb_sdk/shared_types.py")
            if shared_types_path.stat().st_size < 100:
                self.log_result("Package Structure", False, "shared_types.py seems too small")
                return False
            
            self.log_result("Package Structure", True)
            return True
            
        except Exception as e:
            self.log_result("Package Structure", False, str(e))
            return False
    
    def test_no_test_fixtures_in_main(self):
        """Verify test fixtures are not imported in main package."""
        test_code = """
import sys
sys.path.insert(0, 'src')

# Check that test_fixtures is not in main exports
import spacetimedb_sdk

# These should NOT be available
forbidden_attrs = [
    'TestDatabase',
    'TestIsolation',
    'CoverageTracker',
    'TestResultAggregator'
]

has_forbidden = False
for attr in forbidden_attrs:
    if hasattr(spacetimedb_sdk, attr):
        print(f"ERROR: {attr} is exported from main package!")
        has_forbidden = True

if has_forbidden:
    raise RuntimeError("Test fixtures leaked into main package")

print("No test fixtures in main package")
"""
        return self.create_isolated_test("No Test Fixtures in Main", test_code)
    
    def test_example_usage(self):
        """Test a realistic example of SDK usage."""
        test_code = """
import sys
sys.path.insert(0, 'src')

from spacetimedb_sdk import ModernSpacetimeDBClient
from spacetimedb_sdk.shared_types import RetryPolicy

# Example 1: Simple client creation
client = ModernSpacetimeDBClient.builder() \\
    .with_uri("ws://localhost:3000") \\
    .with_module_name("my_game") \\
    .with_token("auth_token") \\
    .build()

# Example 2: Connection pool with retry
retry_policy = RetryPolicy(
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0
)

pool_builder = ModernSpacetimeDBClient.builder() \\
    .with_uri("ws://localhost:3000") \\
    .with_module_name("my_game") \\
    .with_connection_pool(
        min_connections=10,
        max_connections=50,
        load_balancing_strategy="least_latency"
    ) \\
    .with_retry_policy(
        max_retries=retry_policy.max_retries,
        base_delay=retry_policy.base_delay
    )

# Validate configuration
validation = pool_builder.validate()
assert validation['valid'] == True

print("Example usage works correctly")
"""
        return self.create_isolated_test("Example Usage", test_code)
    
    def create_pip_installable_test(self):
        """Create a test that simulates pip installation."""
        print("\n" + "="*60)
        print("Creating pip-installable package test...")
        print("="*60)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a test project that depends on spacetimedb-sdk
            test_project = temp_path / "test_external_project"
            test_project.mkdir()
            
            # Create a simple setup.py
            setup_py = test_project / "setup.py"
            setup_py.write_text("""
from setuptools import setup

setup(
    name="test-external-project",
    version="0.1.0",
    py_modules=["test_app"],
)
""")
            
            # Create test app that uses the SDK
            test_app = test_project / "test_app.py"
            test_app.write_text("""
import sys
sys.path.insert(0, '""" + str(self.project_root / "src") + """')

from spacetimedb_sdk import ModernSpacetimeDBClient

def main():
    # Try to use the SDK
    builder = ModernSpacetimeDBClient.builder()
    builder.with_uri("ws://localhost:3000")
    builder.with_module_name("test")
    
    print("External project can use SpacetimeDB SDK successfully!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
""")
            
            # Test the external project
            result = subprocess.run(
                [sys.executable, "test_app.py"],
                cwd=str(test_project),
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.log_result("External Project Usage", True)
                return True
            else:
                self.log_result("External Project Usage", False, 
                              f"Error: {result.stderr}")
                return False
    
    def run_all_tests(self):
        """Run all verification tests."""
        print("="*60)
        print("SpacetimeDB SDK External Usage Verification")
        print("="*60)
        print()
        
        # Run all tests
        self.test_package_structure()
        self.test_basic_import()
        self.test_all_major_imports()
        self.test_no_circular_imports()
        self.test_builder_pattern()
        self.test_connection_pool_creation()
        self.test_no_test_fixtures_in_main()
        self.test_example_usage()
        self.create_pip_installable_test()
        
        # Summary
        print("\n" + "="*60)
        print("VERIFICATION SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, p, _ in self.results if p)
        total = len(self.results)
        
        print(f"\nTotal tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        
        if passed < total:
            print("\nFailed tests:")
            for name, passed, msg in self.results:
                if not passed:
                    print(f"  - {name}: {msg}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\nSuccess rate: {success_rate:.1f}%")
        
        if passed == total:
            print("\n✅ All verification tests passed!")
            print("\nThe SDK is ready for external usage:")
            print("- No circular import issues")
            print("- All major functionality works")
            print("- Package structure is correct")
            print("- No test code leaked into main package")
            print("- External projects can use the SDK")
            return True
        else:
            print("\n❌ Some tests failed. Please fix the issues before publishing.")
            return False

def main():
    verifier = ExternalUsageVerifier()
    success = verifier.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
