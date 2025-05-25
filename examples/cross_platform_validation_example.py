"""
Cross-Platform Integration Validation Example.

Demonstrates how to use the cross-platform validation framework to:
- Test SDK compatibility across platforms
- Validate environment-specific features
- Generate CI/CD configurations
- Create comprehensive validation reports
- Handle different deployment scenarios

This showcases ts-parity-20: Cross-Platform Integration Validation.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the SDK to the path for this example
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from spacetimedb_sdk.cross_platform_validation import (
    PlatformType, ArchitectureType, EnvironmentType, NetworkCondition,
    SystemInfo, PlatformValidator, CrossPlatformTestSuite
)
from spacetimedb_sdk.logger import configure_default_logging


async def example_1_basic_system_detection():
    """Example 1: Basic system detection and information."""
    print("=" * 60)
    print("Example 1: Basic System Detection")
    print("=" * 60)
    
    # Collect system information
    system_info = SystemInfo.collect()
    
    print(f"Platform: {system_info.platform.value}")
    print(f"Architecture: {system_info.architecture.value}")
    print(f"Python Version: {system_info.python_version}")
    print(f"Python Implementation: {system_info.python_implementation}")
    print(f"OS Version: {system_info.os_version}")
    print(f"Hostname: {system_info.hostname}")
    print(f"CPU Count: {system_info.cpu_count}")
    print(f"Memory: {system_info.memory_gb:.1f} GB")
    
    # Convert to dictionary for JSON serialization
    system_dict = system_info.to_dict()
    print(f"\nSystem Info JSON:")
    print(json.dumps(system_dict, indent=2))


async def example_2_platform_compatibility_validation():
    """Example 2: Platform compatibility validation."""
    print("\n" + "=" * 60)
    print("Example 2: Platform Compatibility Validation")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Test platform compatibility
    result = await validator.validate_platform_compatibility()
    
    print(f"Test: {result.test_name}")
    print(f"Passed: {result.passed}")
    print(f"Duration: {result.duration:.3f}s")
    
    if result.error_message:
        print(f"Error: {result.error_message}")
    
    print(f"Details:")
    for key, value in result.details.items():
        print(f"  {key}: {value}")


async def example_3_python_version_compatibility():
    """Example 3: Python version compatibility testing."""
    print("\n" + "=" * 60)
    print("Example 3: Python Version Compatibility")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Test Python version compatibility
    result = await validator.validate_python_version_compatibility()
    
    print(f"Test: {result.test_name}")
    print(f"Passed: {result.passed}")
    print(f"Duration: {result.duration:.3f}s")
    
    print(f"Python Details:")
    for key, value in result.details.items():
        print(f"  {key}: {value}")
    
    # Show version-specific features
    version_info = sys.version_info
    print(f"\nVersion-Specific Features:")
    print(f"  Python {version_info.major}.{version_info.minor}.{version_info.micro}")
    
    if version_info >= (3, 9):
        print(f"  ✅ Dict union operators (|)")
        print(f"  ✅ Generic types in standard collections")
    
    if version_info >= (3, 10):
        print(f"  ✅ Pattern matching (match/case)")
        print(f"  ✅ Union types with |")
    
    if version_info >= (3, 11):
        print(f"  ✅ Exception groups")
        print(f"  ✅ Fine-grained error locations")


async def example_4_architecture_compatibility():
    """Example 4: Architecture-specific compatibility testing."""
    print("\n" + "=" * 60)
    print("Example 4: Architecture Compatibility")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Test architecture compatibility
    result = await validator.validate_architecture_compatibility()
    
    print(f"Test: {result.test_name}")
    print(f"Passed: {result.passed}")
    print(f"Duration: {result.duration:.3f}s")
    
    print(f"Architecture Details:")
    for key, value in result.details.items():
        print(f"  {key}: {value}")
    
    # Test specific components
    print(f"\nComponent Testing:")
    bsatn_result = await validator._test_bsatn_arch_compatibility()
    print(f"  BSATN Serialization: {'✅ PASS' if bsatn_result else '❌ FAIL'}")
    
    compression_result = await validator._test_compression_arch_compatibility()
    print(f"  Compression: {'✅ PASS' if compression_result else '❌ FAIL'}")
    
    websocket_result = await validator._test_websocket_arch_compatibility()
    print(f"  WebSocket: {'✅ PASS' if websocket_result else '❌ FAIL'}")


async def example_5_environment_testing():
    """Example 5: Environment-specific testing."""
    print("\n" + "=" * 60)
    print("Example 5: Environment Testing")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Test different environments
    environments = [
        EnvironmentType.DEVELOPMENT,
        EnvironmentType.CI_CD,
        EnvironmentType.DOCKER,
        EnvironmentType.CLOUD
    ]
    
    for env_type in environments:
        print(f"\nTesting {env_type.name} environment:")
        result = await validator.validate_environment_compatibility(env_type)
        
        print(f"  Passed: {result.passed}")
        print(f"  Duration: {result.duration:.3f}s")
        
        # Show key details
        key_details = [
            "environment_variables", "file_permissions", 
            "network_access", "process_management"
        ]
        
        for detail in key_details:
            if detail in result.details:
                status = "✅" if result.details[detail] else "❌"
                print(f"  {detail}: {status}")


async def example_6_network_condition_simulation():
    """Example 6: Network condition simulation."""
    print("\n" + "=" * 60)
    print("Example 6: Network Condition Simulation")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Test different network conditions
    conditions = [
        NetworkCondition.NORMAL,
        NetworkCondition.HIGH_LATENCY,
        NetworkCondition.LOW_BANDWIDTH,
        NetworkCondition.INTERMITTENT
    ]
    
    for condition in conditions:
        print(f"\nTesting {condition.name} network condition:")
        result = await validator.validate_network_conditions(condition)
        
        print(f"  Passed: {result.passed}")
        print(f"  Duration: {result.duration:.3f}s")
        
        # Show test results
        test_results = ["connection_test", "subscription_test", "reducer_test"]
        for test in test_results:
            if test in result.details:
                status = "✅" if result.details[test] else "❌"
                print(f"  {test}: {status}")


async def example_7_deployment_scenarios():
    """Example 7: Deployment scenario validation."""
    print("\n" + "=" * 60)
    print("Example 7: Deployment Scenarios")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Test deployment scenarios
    result = await validator.validate_deployment_scenarios()
    
    print(f"Test: {result.test_name}")
    print(f"Passed: {result.passed}")
    print(f"Duration: {result.duration:.3f}s")
    
    print(f"\nDeployment Scenarios:")
    
    # Docker deployment
    docker_result = result.details.get("docker_deployment", {})
    docker_status = "✅" if docker_result.get("passed", False) else "❌"
    print(f"  Docker: {docker_status}")
    if docker_result.get("docker_version"):
        print(f"    Version: {docker_result['docker_version']}")
    
    # Cloud deployment
    cloud_result = result.details.get("cloud_deployment", {})
    cloud_status = "✅" if cloud_result.get("passed", False) else "❌"
    print(f"  Cloud: {cloud_status}")
    if cloud_result.get("cloud_providers"):
        providers = ", ".join(cloud_result["cloud_providers"])
        print(f"    Providers: {providers}")
    
    # Microservices
    micro_result = result.details.get("microservices_integration", {})
    micro_status = "✅" if micro_result.get("passed", False) else "❌"
    print(f"  Microservices: {micro_status}")
    
    # Monitoring
    monitor_result = result.details.get("monitoring_integration", {})
    monitor_status = "✅" if monitor_result.get("passed", False) else "❌"
    print(f"  Monitoring: {monitor_status}")


async def example_8_comprehensive_validation():
    """Example 8: Comprehensive validation with full report."""
    print("\n" + "=" * 60)
    print("Example 8: Comprehensive Validation")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Run comprehensive validation
    print("Running comprehensive validation...")
    report = await validator.run_comprehensive_validation()
    
    # Display summary
    summary = report["summary"]
    print(f"\nValidation Summary:")
    print(f"  Total Tests: {summary['total_tests']}")
    print(f"  Passed: {summary['passed_tests']}")
    print(f"  Failed: {summary['failed_tests']}")
    print(f"  Success Rate: {summary['success_rate']:.1f}%")
    print(f"  Total Duration: {summary['total_duration']:.3f}s")
    
    # Display system info
    system_info = report["system_info"]
    print(f"\nSystem Information:")
    print(f"  Platform: {system_info['platform']}")
    print(f"  Architecture: {system_info['architecture']}")
    print(f"  Python: {system_info['python_version']} ({system_info['python_implementation']})")
    print(f"  CPUs: {system_info['cpu_count']}")
    print(f"  Memory: {system_info['memory_gb']} GB")
    
    # Display test results
    print(f"\nTest Results:")
    for test_result in report["test_results"]:
        status = "✅ PASS" if test_result["passed"] else "❌ FAIL"
        duration = test_result["duration"]
        print(f"  {test_result['test_name']}: {status} ({duration:.3f}s)")
        
        if not test_result["passed"] and test_result.get("error_message"):
            print(f"    Error: {test_result['error_message']}")
    
    # Display recommendations
    print(f"\nRecommendations:")
    for i, recommendation in enumerate(report["recommendations"], 1):
        print(f"  {i}. {recommendation}")
    
    return report


async def example_9_cross_platform_test_suite():
    """Example 9: Using the cross-platform test suite."""
    print("\n" + "=" * 60)
    print("Example 9: Cross-Platform Test Suite")
    print("=" * 60)
    
    suite = CrossPlatformTestSuite()
    
    # Run basic validation
    print("Running basic validation...")
    basic_results = await suite.run_basic_validation()
    
    print(f"Basic validation completed:")
    print(f"  Success rate: {basic_results['summary']['success_rate']:.1f}%")
    
    # Run extended validation (without WASM for this example)
    print(f"\nRunning extended validation...")
    extended_results = await suite.run_extended_validation(include_wasm=False)
    
    print(f"Extended validation completed:")
    print(f"  Success rate: {extended_results['summary']['success_rate']:.1f}%")
    
    return extended_results


def example_10_ci_configuration_generation():
    """Example 10: Generate CI/CD configuration."""
    print("\n" + "=" * 60)
    print("Example 10: CI/CD Configuration Generation")
    print("=" * 60)
    
    suite = CrossPlatformTestSuite()
    
    # Generate default CI configuration
    print("Generating default CI configuration:")
    default_config = suite.generate_ci_config()
    print(default_config)
    
    # Generate custom CI configuration
    print(f"\n" + "-" * 40)
    print("Generating custom CI configuration:")
    custom_platforms = ["ubuntu-20.04", "ubuntu-22.04", "macos-12", "windows-2022"]
    custom_config = suite.generate_ci_config(custom_platforms)
    print(custom_config)


async def example_11_production_readiness_assessment():
    """Example 11: Production readiness assessment."""
    print("\n" + "=" * 60)
    print("Example 11: Production Readiness Assessment")
    print("=" * 60)
    
    suite = CrossPlatformTestSuite()
    
    # Run comprehensive validation
    results = await suite.run_basic_validation()
    
    # Assess production readiness
    summary = results["summary"]
    success_rate = summary["success_rate"]
    total_tests = summary["total_tests"]
    
    print(f"Production Readiness Assessment:")
    print(f"  Success Rate: {success_rate:.1f}%")
    print(f"  Total Tests: {total_tests}")
    
    # Define production readiness criteria
    criteria = {
        "minimum_success_rate": 80.0,
        "minimum_tests": 5,
        "critical_tests": [
            "platform_compatibility",
            "python_version_compatibility",
            "architecture_compatibility"
        ]
    }
    
    # Check criteria
    meets_success_rate = success_rate >= criteria["minimum_success_rate"]
    meets_test_count = total_tests >= criteria["minimum_tests"]
    
    # Check critical tests
    critical_tests_passed = []
    for test_result in results["test_results"]:
        if test_result["test_name"] in criteria["critical_tests"]:
            critical_tests_passed.append(test_result["passed"])
    
    all_critical_passed = all(critical_tests_passed)
    
    print(f"\nProduction Readiness Criteria:")
    print(f"  ✅ Success Rate ≥ 80%: {'✅ PASS' if meets_success_rate else '❌ FAIL'}")
    print(f"  ✅ Test Count ≥ 5: {'✅ PASS' if meets_test_count else '❌ FAIL'}")
    print(f"  ✅ Critical Tests Pass: {'✅ PASS' if all_critical_passed else '❌ FAIL'}")
    
    # Overall assessment
    production_ready = meets_success_rate and meets_test_count and all_critical_passed
    
    print(f"\n🎯 Overall Assessment: {'✅ PRODUCTION READY' if production_ready else '❌ NOT READY'}")
    
    if not production_ready:
        print(f"\nRecommendations for production readiness:")
        if not meets_success_rate:
            print(f"  • Improve test success rate (currently {success_rate:.1f}%)")
        if not meets_test_count:
            print(f"  • Add more comprehensive tests (currently {total_tests})")
        if not all_critical_passed:
            print(f"  • Fix critical test failures")
    
    return production_ready


async def example_12_error_handling_and_recovery():
    """Example 12: Error handling and recovery scenarios."""
    print("\n" + "=" * 60)
    print("Example 12: Error Handling and Recovery")
    print("=" * 60)
    
    validator = PlatformValidator()
    
    # Simulate various error conditions
    print("Testing error handling scenarios:")
    
    # Test with mock failures
    from unittest.mock import patch
    
    # Test import failure handling
    print(f"\n1. Testing import failure handling:")
    with patch('builtins.__import__', side_effect=ImportError("Mock import error")):
        try:
            result = await validator.validate_platform_compatibility()
            print(f"   Result: {result.passed} (Error handled gracefully)")
            if result.error_message:
                print(f"   Error: {result.error_message}")
        except Exception as e:
            print(f"   Unexpected error: {e}")
    
    # Test timeout handling
    print(f"\n2. Testing timeout scenarios:")
    import asyncio
    
    async def slow_operation():
        await asyncio.sleep(0.1)  # Simulate slow operation
        return True
    
    try:
        result = await asyncio.wait_for(slow_operation(), timeout=0.05)
        print(f"   Operation completed: {result}")
    except asyncio.TimeoutError:
        print(f"   ✅ Timeout handled correctly")
    
    # Test network failure simulation
    print(f"\n3. Testing network failure scenarios:")
    try:
        result = await validator.validate_network_conditions(NetworkCondition.INTERMITTENT)
        print(f"   Network test result: {result.passed}")
        print(f"   Duration: {result.duration:.3f}s")
    except Exception as e:
        print(f"   Network error handled: {e}")


async def main():
    """Run all cross-platform validation examples."""
    # Configure logging
    configure_default_logging(debug=True)
    
    print("🚀 SpacetimeDB Python SDK Cross-Platform Validation Examples")
    print("=" * 80)
    
    try:
        # Run all examples
        await example_1_basic_system_detection()
        await example_2_platform_compatibility_validation()
        await example_3_python_version_compatibility()
        await example_4_architecture_compatibility()
        await example_5_environment_testing()
        await example_6_network_condition_simulation()
        await example_7_deployment_scenarios()
        
        # Comprehensive validation
        report = await example_8_comprehensive_validation()
        
        # Test suite examples
        await example_9_cross_platform_test_suite()
        
        # CI configuration
        example_10_ci_configuration_generation()
        
        # Production readiness
        production_ready = await example_11_production_readiness_assessment()
        
        # Error handling
        await example_12_error_handling_and_recovery()
        
        # Final summary
        print("\n" + "=" * 80)
        print("🎉 Cross-Platform Validation Examples Completed!")
        print("=" * 80)
        
        print(f"Final Summary:")
        print(f"  Platform: {report['system_info']['platform']}")
        print(f"  Architecture: {report['system_info']['architecture']}")
        print(f"  Python: {report['system_info']['python_version']}")
        print(f"  Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"  Production Ready: {'✅ YES' if production_ready else '❌ NO'}")
        
        # Save report to file
        report_file = Path("cross_platform_validation_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"  Report saved to: {report_file}")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 