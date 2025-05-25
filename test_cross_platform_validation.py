"""
Comprehensive tests for Cross-Platform Integration Validation.

Tests the cross-platform validation framework to ensure it correctly:
- Detects platform and architecture information
- Validates Python version compatibility
- Tests environment-specific features
- Simulates network conditions
- Validates deployment scenarios
- Generates accurate reports

This validates ts-parity-20: Cross-Platform Integration Validation.
"""

import asyncio
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from src.spacetimedb_sdk.cross_platform_validation import (
    PlatformType, ArchitectureType, EnvironmentType, NetworkCondition,
    SystemInfo, ValidationResult, NetworkSimulator, PlatformValidator,
    CrossPlatformTestSuite
)


class TestPlatformDetection:
    """Test platform and architecture detection."""
    
    def test_platform_detection_linux(self):
        """Test Linux platform detection."""
        with patch('platform.system', return_value='Linux'):
            assert PlatformType.current() == PlatformType.LINUX
    
    def test_platform_detection_macos(self):
        """Test macOS platform detection."""
        with patch('platform.system', return_value='Darwin'):
            assert PlatformType.current() == PlatformType.MACOS
    
    def test_platform_detection_windows(self):
        """Test Windows platform detection."""
        with patch('platform.system', return_value='Windows'):
            assert PlatformType.current() == PlatformType.WINDOWS
    
    def test_platform_detection_unknown(self):
        """Test unknown platform detection."""
        with patch('platform.system', return_value='FreeBSD'):
            assert PlatformType.current() == PlatformType.UNKNOWN
    
    def test_architecture_detection_x86_64(self):
        """Test x86_64 architecture detection."""
        with patch('platform.machine', return_value='x86_64'):
            assert ArchitectureType.current() == ArchitectureType.X86_64
    
    def test_architecture_detection_arm64(self):
        """Test ARM64 architecture detection."""
        with patch('platform.machine', return_value='arm64'):
            assert ArchitectureType.current() == ArchitectureType.ARM64
        
        with patch('platform.machine', return_value='aarch64'):
            assert ArchitectureType.current() == ArchitectureType.ARM64
    
    def test_architecture_detection_i386(self):
        """Test i386 architecture detection."""
        with patch('platform.machine', return_value='i386'):
            assert ArchitectureType.current() == ArchitectureType.I386
    
    def test_architecture_detection_unknown(self):
        """Test unknown architecture detection."""
        with patch('platform.machine', return_value='sparc'):
            assert ArchitectureType.current() == ArchitectureType.UNKNOWN


class TestSystemInfo:
    """Test system information collection."""
    
    @patch('psutil.virtual_memory')
    @patch('platform.node')
    @patch('platform.platform')
    @patch('platform.python_implementation')
    @patch('os.cpu_count')
    def test_system_info_collection(self, mock_cpu_count, mock_python_impl, 
                                   mock_platform, mock_node, mock_memory):
        """Test system information collection."""
        # Mock system information
        mock_cpu_count.return_value = 8
        mock_python_impl.return_value = "CPython"
        mock_platform.return_value = "Linux-5.4.0-x86_64"
        mock_node.return_value = "test-host"
        
        # Mock memory info
        memory_mock = Mock()
        memory_mock.total = 16 * 1024**3  # 16GB
        mock_memory.return_value = memory_mock
        
        # Collect system info
        info = SystemInfo.collect()
        
        # Verify information
        assert info.cpu_count == 8
        assert info.python_implementation == "CPython"
        assert info.os_version == "Linux-5.4.0-x86_64"
        assert info.hostname == "test-host"
        assert info.memory_gb == 16.0
        assert info.python_version.startswith(f"{sys.version_info.major}.{sys.version_info.minor}")
    
    def test_system_info_to_dict(self):
        """Test system info dictionary conversion."""
        info = SystemInfo(
            platform=PlatformType.LINUX,
            architecture=ArchitectureType.X86_64,
            python_version="3.11.0",
            python_implementation="CPython",
            os_version="Linux-5.4.0",
            hostname="test-host",
            cpu_count=8,
            memory_gb=16.0
        )
        
        data = info.to_dict()
        
        assert data["platform"] == "linux"
        assert data["architecture"] == "x86_64"
        assert data["python_version"] == "3.11.0"
        assert data["python_implementation"] == "CPython"
        assert data["cpu_count"] == 8
        assert data["memory_gb"] == 16.0


class TestValidationResult:
    """Test validation result handling."""
    
    def test_validation_result_creation(self):
        """Test validation result creation."""
        result = ValidationResult(
            test_name="test_example",
            passed=True,
            duration=1.5,
            details={"feature": True}
        )
        
        assert result.test_name == "test_example"
        assert result.passed is True
        assert result.duration == 1.5
        assert result.details["feature"] is True
        assert result.error_message is None
    
    def test_validation_result_with_error(self):
        """Test validation result with error."""
        result = ValidationResult(
            test_name="test_failure",
            passed=False,
            duration=0.5,
            error_message="Test failed"
        )
        
        assert result.passed is False
        assert result.error_message == "Test failed"
    
    def test_validation_result_to_dict(self):
        """Test validation result dictionary conversion."""
        system_info = SystemInfo(
            platform=PlatformType.LINUX,
            architecture=ArchitectureType.X86_64,
            python_version="3.11.0",
            python_implementation="CPython",
            os_version="Linux-5.4.0",
            hostname="test-host",
            cpu_count=8,
            memory_gb=16.0
        )
        
        result = ValidationResult(
            test_name="test_example",
            passed=True,
            duration=1.5,
            details={"feature": True},
            system_info=system_info
        )
        
        data = result.to_dict()
        
        assert data["test_name"] == "test_example"
        assert data["passed"] is True
        assert data["duration"] == 1.5
        assert data["details"]["feature"] is True
        assert "system_info" in data
        assert data["system_info"]["platform"] == "linux"


class TestNetworkSimulator:
    """Test network condition simulation."""
    
    def test_network_simulator_initialization(self):
        """Test network simulator initialization."""
        sim = NetworkSimulator()
        
        assert sim.condition == NetworkCondition.NORMAL
        assert sim.latency_ms == 0
        assert sim.bandwidth_limit is None
        assert sim.packet_loss == 0.0
    
    def test_high_latency_simulation(self):
        """Test high latency simulation."""
        sim = NetworkSimulator()
        
        with sim.simulate_condition(NetworkCondition.HIGH_LATENCY):
            assert sim.condition == NetworkCondition.HIGH_LATENCY
            assert sim.latency_ms == 500
        
        # Should reset after context
        assert sim.condition == NetworkCondition.NORMAL
        assert sim.latency_ms == 0
    
    def test_low_bandwidth_simulation(self):
        """Test low bandwidth simulation."""
        sim = NetworkSimulator()
        
        with sim.simulate_condition(NetworkCondition.LOW_BANDWIDTH):
            assert sim.condition == NetworkCondition.LOW_BANDWIDTH
            assert sim.bandwidth_limit == 1024
        
        # Should reset after context
        assert sim.bandwidth_limit is None
    
    def test_intermittent_simulation(self):
        """Test intermittent connection simulation."""
        sim = NetworkSimulator()
        
        with sim.simulate_condition(NetworkCondition.INTERMITTENT):
            assert sim.condition == NetworkCondition.INTERMITTENT
            assert sim.packet_loss == 0.1
        
        # Should reset after context
        assert sim.packet_loss == 0.0
    
    def test_add_latency(self):
        """Test latency addition."""
        sim = NetworkSimulator()
        
        start_time = time.perf_counter()
        sim.add_latency(100)  # 100ms
        duration = time.perf_counter() - start_time
        
        # Should add approximately 100ms (allow some tolerance)
        assert 0.09 <= duration <= 0.15


class TestPlatformValidator:
    """Test platform validation functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create platform validator for testing."""
        return PlatformValidator()
    
    @pytest.mark.asyncio
    async def test_platform_compatibility_validation(self, validator):
        """Test platform compatibility validation."""
        result = await validator.validate_platform_compatibility()
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "platform_compatibility"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "imports_successful" in result.details
        assert "platform_supported" in result.details
        assert "architecture_supported" in result.details
        assert "python_version_supported" in result.details
    
    @pytest.mark.asyncio
    async def test_python_version_compatibility(self, validator):
        """Test Python version compatibility validation."""
        result = await validator.validate_python_version_compatibility()
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "python_version_compatibility"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "version" in result.details
        assert "implementation" in result.details
        assert "version_supported" in result.details
        assert "async_await_support" in result.details
    
    @pytest.mark.asyncio
    async def test_architecture_compatibility(self, validator):
        """Test architecture compatibility validation."""
        result = await validator.validate_architecture_compatibility()
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "architecture_compatibility"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "architecture" in result.details
        assert "byte_order" in result.details
        assert "pointer_size" in result.details
    
    @pytest.mark.asyncio
    async def test_environment_compatibility_development(self, validator):
        """Test development environment compatibility."""
        result = await validator.validate_environment_compatibility(EnvironmentType.DEVELOPMENT)
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "environment_compatibility_development"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "environment_type" in result.details
        assert result.details["environment_type"] == "DEVELOPMENT"
    
    @pytest.mark.asyncio
    async def test_environment_compatibility_ci_cd(self, validator):
        """Test CI/CD environment compatibility."""
        result = await validator.validate_environment_compatibility(EnvironmentType.CI_CD)
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "environment_compatibility_ci_cd"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "environment_type" in result.details
        assert result.details["environment_type"] == "CI_CD"
    
    @pytest.mark.asyncio
    async def test_network_conditions_normal(self, validator):
        """Test normal network conditions."""
        result = await validator.validate_network_conditions(NetworkCondition.NORMAL)
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "network_conditions_normal"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "condition" in result.details
        assert result.details["condition"] == "NORMAL"
    
    @pytest.mark.asyncio
    async def test_network_conditions_high_latency(self, validator):
        """Test high latency network conditions."""
        result = await validator.validate_network_conditions(NetworkCondition.HIGH_LATENCY)
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "network_conditions_high_latency"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "condition" in result.details
        assert result.details["condition"] == "HIGH_LATENCY"
    
    @pytest.mark.asyncio
    async def test_spacetimedb_version_compatibility(self, validator):
        """Test SpacetimeDB version compatibility."""
        versions = ["1.1.1", "1.1.0"]
        result = await validator.validate_spacetimedb_versions(versions)
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "spacetimedb_version_compatibility"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "tested_versions" in result.details
        assert result.details["tested_versions"] == versions
        assert "version_results" in result.details
    
    @pytest.mark.asyncio
    async def test_deployment_scenarios(self, validator):
        """Test deployment scenarios validation."""
        result = await validator.validate_deployment_scenarios()
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "deployment_scenarios"
        assert isinstance(result.passed, bool)
        assert result.duration > 0
        assert "docker_deployment" in result.details
        assert "cloud_deployment" in result.details
        assert "microservices_integration" in result.details
        assert "monitoring_integration" in result.details
    
    @pytest.mark.asyncio
    async def test_comprehensive_validation(self, validator):
        """Test comprehensive validation."""
        report = await validator.run_comprehensive_validation()
        
        assert isinstance(report, dict)
        assert "summary" in report
        assert "system_info" in report
        assert "test_results" in report
        assert "recommendations" in report
        
        # Check summary
        summary = report["summary"]
        assert "total_tests" in summary
        assert "passed_tests" in summary
        assert "failed_tests" in summary
        assert "success_rate" in summary
        assert "total_duration" in summary
        
        # Check test results
        assert isinstance(report["test_results"], list)
        assert len(report["test_results"]) > 0
        
        # Check recommendations
        assert isinstance(report["recommendations"], list)
    
    def test_python_version_check(self, validator):
        """Test Python version checking."""
        # Should pass for current Python version (3.8+)
        assert validator._check_python_version() is True
    
    @pytest.mark.asyncio
    async def test_bsatn_arch_compatibility(self, validator):
        """Test BSATN architecture compatibility."""
        result = await validator._test_bsatn_arch_compatibility()
        
        # Should work on supported architectures
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_compression_arch_compatibility(self, validator):
        """Test compression architecture compatibility."""
        result = await validator._test_compression_arch_compatibility()
        
        # Should work if compression is available
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_websocket_arch_compatibility(self, validator):
        """Test WebSocket architecture compatibility."""
        result = await validator._test_websocket_arch_compatibility()
        
        # Should work if websockets package is available
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_file_permissions(self, validator):
        """Test file permissions testing."""
        result = await validator._test_file_permissions(EnvironmentType.DEVELOPMENT)
        
        # Should be able to create temporary files
        assert result is True
    
    @pytest.mark.asyncio
    async def test_network_access(self, validator):
        """Test network access testing."""
        result = await validator._test_network_access(EnvironmentType.DEVELOPMENT)
        
        # Should be able to create sockets
        assert result is True
    
    @pytest.mark.asyncio
    async def test_process_management(self, validator):
        """Test process management testing."""
        result = await validator._test_process_management(EnvironmentType.DEVELOPMENT)
        
        # Should be able to run subprocesses
        assert result is True
    
    @pytest.mark.asyncio
    async def test_docker_deployment(self, validator):
        """Test Docker deployment testing."""
        result = await validator._test_docker_deployment()
        
        assert isinstance(result, dict)
        assert "passed" in result
        
        # If Docker is available, should have version info
        if result["passed"]:
            assert "docker_version" in result
            assert "container_support" in result
    
    def test_environment_variables_check(self, validator):
        """Test environment variables checking."""
        # Test CI/CD detection
        with patch.dict(os.environ, {"CI": "true"}):
            result = validator._check_environment_variables(EnvironmentType.CI_CD)
            assert result is True
        
        # Test without CI variables
        with patch.dict(os.environ, {}, clear=True):
            result = validator._check_environment_variables(EnvironmentType.CI_CD)
            assert result is False
        
        # Development should always pass
        result = validator._check_environment_variables(EnvironmentType.DEVELOPMENT)
        assert result is True
    
    def test_recommendations_generation(self, validator):
        """Test recommendations generation."""
        # Test with no failed tests
        validator.results = [
            ValidationResult("test1", True, 1.0),
            ValidationResult("test2", True, 1.0)
        ]
        
        recommendations = validator._generate_recommendations()
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Test with failed tests
        validator.results = [
            ValidationResult("test1", True, 1.0),
            ValidationResult("test2", False, 1.0, error_message="Failed")
        ]
        
        recommendations = validator._generate_recommendations()
        assert any("failed" in rec.lower() for rec in recommendations)


class TestCrossPlatformTestSuite:
    """Test cross-platform test suite."""
    
    @pytest.fixture
    def test_suite(self):
        """Create test suite for testing."""
        return CrossPlatformTestSuite()
    
    @pytest.mark.asyncio
    async def test_basic_validation(self, test_suite):
        """Test basic validation."""
        results = await test_suite.run_basic_validation()
        
        assert isinstance(results, dict)
        assert "summary" in results
        assert "system_info" in results
        assert "test_results" in results
        assert "recommendations" in results
    
    @pytest.mark.asyncio
    async def test_extended_validation_without_wasm(self, test_suite):
        """Test extended validation without WASM."""
        results = await test_suite.run_extended_validation(include_wasm=False)
        
        assert isinstance(results, dict)
        assert "summary" in results
        assert "wasm_validation" not in results
    
    @pytest.mark.asyncio
    async def test_extended_validation_with_wasm(self, test_suite):
        """Test extended validation with WASM."""
        results = await test_suite.run_extended_validation(include_wasm=True)
        
        assert isinstance(results, dict)
        assert "summary" in results
        assert "wasm_validation" in results
        
        # WASM validation should have passed/failed status
        wasm_results = results["wasm_validation"]
        assert "passed" in wasm_results
    
    def test_ci_config_generation(self, test_suite):
        """Test CI configuration generation."""
        config = test_suite.generate_ci_config()
        
        assert isinstance(config, str)
        assert "Cross-Platform Validation" in config
        assert "ubuntu-latest" in config
        assert "macos-latest" in config
        assert "windows-latest" in config
        assert "python-version" in config
    
    def test_ci_config_custom_platforms(self, test_suite):
        """Test CI configuration with custom platforms."""
        platforms = ["ubuntu-20.04", "ubuntu-22.04"]
        config = test_suite.generate_ci_config(platforms)
        
        assert isinstance(config, str)
        assert "ubuntu-20.04" in config
        assert "ubuntu-22.04" in config
        assert "macos-latest" not in config


class TestIntegrationScenarios:
    """Test integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_validation_workflow(self):
        """Test complete validation workflow."""
        suite = CrossPlatformTestSuite()
        
        # Run basic validation
        results = await suite.run_basic_validation()
        
        # Verify structure
        assert "summary" in results
        assert "system_info" in results
        assert "test_results" in results
        assert "recommendations" in results
        
        # Verify summary
        summary = results["summary"]
        assert summary["total_tests"] > 0
        assert summary["passed_tests"] >= 0
        assert summary["failed_tests"] >= 0
        assert 0 <= summary["success_rate"] <= 100
        assert summary["total_duration"] > 0
        
        # Verify system info
        system_info = results["system_info"]
        assert "platform" in system_info
        assert "architecture" in system_info
        assert "python_version" in system_info
        
        # Verify test results
        test_results = results["test_results"]
        assert len(test_results) > 0
        
        for test_result in test_results:
            assert "test_name" in test_result
            assert "passed" in test_result
            assert "duration" in test_result
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in validation."""
        validator = PlatformValidator()
        
        # Mock a failing test
        with patch.object(validator, '_check_dependencies', side_effect=Exception("Mock error")):
            result = await validator.validate_platform_compatibility()
            
            assert result.passed is False
            assert result.error_message is not None
            assert "Mock error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_performance_measurement(self):
        """Test performance measurement accuracy."""
        validator = PlatformValidator()
        
        # Test a simple validation
        start_time = time.perf_counter()
        result = await validator.validate_platform_compatibility()
        actual_duration = time.perf_counter() - start_time
        
        # Measured duration should be close to actual
        assert abs(result.duration - actual_duration) < 0.1
    
    def test_system_info_accuracy(self):
        """Test system information accuracy."""
        info = SystemInfo.collect()
        
        # Verify platform detection
        current_platform = platform.system().lower()
        if current_platform == "linux":
            assert info.platform == PlatformType.LINUX
        elif current_platform == "darwin":
            assert info.platform == PlatformType.MACOS
        elif current_platform == "windows":
            assert info.platform == PlatformType.WINDOWS
        
        # Verify Python version
        expected_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert info.python_version == expected_version
        
        # Verify basic system properties
        assert info.cpu_count > 0
        assert info.memory_gb > 0
        assert len(info.hostname) > 0


class TestRealWorldScenarios:
    """Test real-world deployment scenarios."""
    
    @pytest.mark.asyncio
    async def test_ci_cd_environment_simulation(self):
        """Test CI/CD environment simulation."""
        validator = PlatformValidator()
        
        # Simulate CI environment
        with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true"}):
            result = await validator.validate_environment_compatibility(EnvironmentType.CI_CD)
            
            assert result.passed is True
            assert result.details["environment_type"] == "CI_CD"
            assert result.details["environment_variables"] is True
    
    @pytest.mark.asyncio
    async def test_docker_environment_simulation(self):
        """Test Docker environment simulation."""
        validator = PlatformValidator()
        
        result = await validator.validate_environment_compatibility(EnvironmentType.DOCKER)
        
        assert isinstance(result, ValidationResult)
        assert result.test_name == "environment_compatibility_docker"
        assert "container_networking" in result.details
        assert "volume_mounting" in result.details
        assert "environment_variables" in result.details
    
    @pytest.mark.asyncio
    async def test_production_readiness_check(self):
        """Test production readiness validation."""
        suite = CrossPlatformTestSuite()
        
        results = await suite.run_basic_validation()
        
        # Check if system is production ready
        summary = results["summary"]
        success_rate = summary["success_rate"]
        
        # Production readiness criteria
        production_ready = (
            success_rate >= 80 and  # At least 80% tests pass
            summary["total_tests"] >= 5  # Minimum test coverage
        )
        
        # Should have recommendations
        recommendations = results["recommendations"]
        assert len(recommendations) > 0
        
        if production_ready:
            # Should have positive recommendation
            assert any("ready" in rec.lower() for rec in recommendations)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"]) 