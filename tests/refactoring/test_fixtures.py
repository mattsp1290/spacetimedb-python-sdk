"""
Test fixtures and utilities for Phase 2 refactoring tests

This module provides reusable test fixtures, data generators, and utilities
for comprehensive testing of the refactored modules.
"""
import pytest
import time
import json
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import Mock, patch
from dataclasses import dataclass

from .mock_infrastructure import (
    MockSpacetimeDBServer, MockServerConfig, MockServerBehavior,
    TestDataGenerator, create_test_server, create_slow_server,
    create_unreliable_server, create_auth_failing_server
)


@dataclass
class ScenarioConfig:
    """Test scenario configuration"""
    name: str
    description: str
    server_behavior: MockServerBehavior
    expected_outcomes: Dict[str, Any]
    test_data: Optional[Dict[str, Any]] = None
    duration: float = 10.0  # Test duration in seconds
    
    
class TestFixtures:
    """Collection of test fixtures for various scenarios"""
    
    @staticmethod
    def get_connection_scenarios() -> List[ScenarioConfig]:
        """Get connection test scenarios"""
        return [
            ScenarioConfig(
                name="normal_connection",
                description="Normal successful connection",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'connected': True,
                    'authenticated': True,
                    'subscriptions_allowed': True
                }
            ),
            ScenarioConfig(
                name="slow_connection",
                description="Connection with slow server responses",
                server_behavior=MockServerBehavior.SLOW_RESPONSE,
                expected_outcomes={
                    'connected': True,
                    'response_time_high': True,
                    'eventual_success': True
                }
            ),
            ScenarioConfig(
                name="auth_failures",
                description="Connection with authentication failures",
                server_behavior=MockServerBehavior.AUTHENTICATION_FAILURES,
                expected_outcomes={
                    'connected': True,
                    'auth_retries': True,
                    'eventual_auth': False
                }
            ),
            ScenarioConfig(
                name="intermittent_errors",
                description="Connection with intermittent server errors",
                server_behavior=MockServerBehavior.INTERMITTENT_ERRORS,
                expected_outcomes={
                    'connected': True,
                    'error_recovery': True,
                    'partial_success': True
                }
            )
        ]
        
    @staticmethod
    def get_subscription_scenarios() -> List[ScenarioConfig]:
        """Get subscription test scenarios"""
        return [
            ScenarioConfig(
                name="single_subscription",
                description="Single table subscription",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'subscription_created': True,
                    'data_received': True,
                    'updates_processed': True
                },
                test_data={'tables': ['users'], 'update_count': 5}
            ),
            ScenarioConfig(
                name="multiple_subscriptions",
                description="Multiple table subscriptions",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'all_subscriptions_created': True,
                    'data_from_all_tables': True,
                    'no_cross_contamination': True
                },
                test_data={'tables': ['users', 'messages', 'logs'], 'update_count': 10}
            ),
            ScenarioConfig(
                name="subscription_with_errors",
                description="Subscriptions with server errors",
                server_behavior=MockServerBehavior.INTERMITTENT_ERRORS,
                expected_outcomes={
                    'some_subscriptions_fail': True,
                    'error_handling': True,
                    'recovery_attempts': True
                },
                test_data={'tables': ['users', 'messages'], 'update_count': 15}
            ),
            ScenarioConfig(
                name="high_volume_subscriptions",
                description="High volume subscription data",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'performance_maintained': True,
                    'memory_stable': True,
                    'all_data_processed': True
                },
                test_data={'tables': ['large_table'], 'update_count': 100}
            )
        ]
        
    @staticmethod
    def get_authentication_scenarios() -> List[ScenarioConfig]:
        """Get authentication test scenarios"""
        return [
            ScenarioConfig(
                name="successful_auth",
                description="Successful authentication flow",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'identity_received': True,
                    'token_stored': True,
                    'authenticated_state': True
                }
            ),
            ScenarioConfig(
                name="auth_token_refresh",
                description="Authentication token refresh",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'token_refreshed': True,
                    'no_service_interruption': True,
                    'new_token_valid': True
                }
            ),
            ScenarioConfig(
                name="auth_failures_with_retry",
                description="Authentication failures with retry logic",
                server_behavior=MockServerBehavior.AUTHENTICATION_FAILURES,
                expected_outcomes={
                    'retry_attempts': True,
                    'exponential_backoff': True,
                    'eventual_failure': True
                }
            ),
            ScenarioConfig(
                name="concurrent_auth_requests",
                description="Concurrent authentication requests",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'no_race_conditions': True,
                    'single_identity': True,
                    'all_requests_handled': True
                }
            )
        ]
        
    @staticmethod
    def get_integration_scenarios() -> List[ScenarioConfig]:
        """Get integration test scenarios"""
        return [
            ScenarioConfig(
                name="full_lifecycle",
                description="Complete client lifecycle",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'connection_successful': True,
                    'authentication_successful': True,
                    'subscriptions_working': True,
                    'data_flow_correct': True,
                    'graceful_shutdown': True
                },
                test_data={'duration': 30.0}
            ),
            ScenarioConfig(
                name="error_recovery",
                description="Error recovery and resilience",
                server_behavior=MockServerBehavior.INTERMITTENT_ERRORS,
                expected_outcomes={
                    'errors_detected': True,
                    'recovery_successful': True,
                    'service_restored': True,
                    'data_consistency': True
                },
                test_data={'duration': 20.0}
            ),
            ScenarioConfig(
                name="performance_under_load",
                description="Performance under high load",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'performance_maintained': True,
                    'memory_efficient': True,
                    'no_bottlenecks': True
                },
                test_data={'duration': 15.0, 'load_factor': 10}
            ),
            ScenarioConfig(
                name="module_isolation",
                description="Module isolation and independence",
                server_behavior=MockServerBehavior.NORMAL,
                expected_outcomes={
                    'modules_independent': True,
                    'no_tight_coupling': True,
                    'clean_interfaces': True
                },
                test_data={'duration': 10.0}
            )
        ]


class ScenarioRunner:
    """Helper class to run test scenarios"""
    
    def __init__(self, scenario: ScenarioConfig):
        self.scenario = scenario
        self.server: Optional[MockSpacetimeDBServer] = None
        self.results: Dict[str, Any] = {}
        
    def setup(self):
        """Set up the scenario"""
        if self.scenario.server_behavior == MockServerBehavior.SLOW_RESPONSE:
            self.server = create_slow_server()
        elif self.scenario.server_behavior == MockServerBehavior.INTERMITTENT_ERRORS:
            self.server = create_unreliable_server()
        elif self.scenario.server_behavior == MockServerBehavior.AUTHENTICATION_FAILURES:
            self.server = create_auth_failing_server()
        else:
            self.server = create_test_server()
            
        self.server.start()
        
        # Add scenario-specific test data
        if self.scenario.test_data:
            self._setup_test_data()
            
    def _setup_test_data(self):
        """Set up scenario-specific test data"""
        test_data = self.scenario.test_data
        
        if 'tables' in test_data:
            for table in test_data['tables']:
                if table == 'large_table':
                    data = TestDataGenerator.generate_large_dataset(table, 1000)
                elif table == 'users':
                    data = TestDataGenerator.generate_user_data(50)
                elif table == 'messages':
                    data = TestDataGenerator.generate_message_data(100)
                else:
                    data = TestDataGenerator.generate_large_dataset(table, 20)
                    
                self.server.add_table_data('test-db', table, data)
                
    def run(self, test_function: Callable) -> Dict[str, Any]:
        """Run the scenario with a test function"""
        try:
            self.setup()
            
            # Run the test function
            start_time = time.time()
            test_function(self.server, self.scenario)
            end_time = time.time()
            
            # Collect results
            self.results = {
                'scenario_name': self.scenario.name,
                'duration': end_time - start_time,
                'expected_duration': self.scenario.duration,
                'server_metrics': self.server.get_metrics(),
                'success': True,
                'error': None
            }
            
        except Exception as e:
            self.results = {
                'scenario_name': self.scenario.name,
                'duration': 0,
                'expected_duration': self.scenario.duration,
                'server_metrics': self.server.get_metrics() if self.server else {},
                'success': False,
                'error': str(e)
            }
            
        finally:
            self.teardown()
            
        return self.results
        
    def teardown(self):
        """Clean up the scenario"""
        if self.server:
            self.server.stop()
            
    def validate_outcomes(self) -> Dict[str, bool]:
        """Validate expected outcomes"""
        validation_results = {}
        
        for outcome, expected in self.scenario.expected_outcomes.items():
            # This would contain scenario-specific validation logic
            validation_results[outcome] = self._validate_outcome(outcome, expected)
            
        return validation_results
        
    def _validate_outcome(self, outcome: str, expected: Any) -> bool:
        """Validate a specific outcome"""
        # Placeholder for outcome validation logic
        # In a real implementation, this would check specific metrics
        # or states based on the outcome type
        return True


class PerformanceBaseline:
    """Performance baseline measurements for regression testing"""
    
    def __init__(self):
        self.baselines = {
            'connection_time': 1.0,  # seconds
            'authentication_time': 0.5,  # seconds
            'subscription_time': 0.1,  # seconds per subscription
            'message_processing_time': 0.001,  # seconds per message
            'memory_usage_mb': 50,  # MB
            'cpu_usage_percent': 10  # percent
        }
        
    def check_performance(self, metrics: Dict[str, float]) -> Dict[str, bool]:
        """Check if performance meets baseline requirements"""
        results = {}
        
        for metric, baseline in self.baselines.items():
            if metric in metrics:
                results[metric] = metrics[metric] <= baseline * 1.1  # 10% tolerance
            else:
                results[metric] = False
                
        return results
        
    def update_baseline(self, metric: str, value: float):
        """Update baseline for a metric"""
        self.baselines[metric] = value


class TestDataFactory:
    """Factory for creating test data sets"""
    
    @staticmethod
    def create_user_dataset(size: str = "medium") -> List[Dict[str, Any]]:
        """Create user dataset of specified size"""
        sizes = {
            'small': 10,
            'medium': 100,
            'large': 1000,
            'xlarge': 10000
        }
        
        count = sizes.get(size, 100)
        return TestDataGenerator.generate_user_data(count)
        
    @staticmethod
    def create_message_dataset(size: str = "medium") -> List[Dict[str, Any]]:
        """Create message dataset of specified size"""
        sizes = {
            'small': 20,
            'medium': 200,
            'large': 2000,
            'xlarge': 20000
        }
        
        count = sizes.get(size, 200)
        return TestDataGenerator.generate_message_data(count)
        
    @staticmethod
    def create_mixed_dataset(tables: List[str], size: str = "medium") -> Dict[str, List[Dict[str, Any]]]:
        """Create mixed dataset for multiple tables"""
        dataset = {}
        
        for table in tables:
            if table == 'users':
                dataset[table] = TestDataFactory.create_user_dataset(size)
            elif table == 'messages':
                dataset[table] = TestDataFactory.create_message_dataset(size)
            else:
                # Generic table data
                sizes = {'small': 10, 'medium': 100, 'large': 1000, 'xlarge': 10000}
                count = sizes.get(size, 100)
                dataset[table] = TestDataGenerator.generate_large_dataset(table, count)
                
        return dataset


class ConfigurationManager:
    """Manage test configurations"""
    
    def __init__(self):
        self.configs = {}
        
    def add_config(self, name: str, config: Dict[str, Any]):
        """Add a test configuration"""
        self.configs[name] = config
        
    def get_config(self, name: str) -> Dict[str, Any]:
        """Get a test configuration"""
        return self.configs.get(name, {})
        
    def load_default_configs(self):
        """Load default test configurations"""
        self.configs.update({
            'integration': {
                'timeout': 30.0,
                'retry_count': 3,
                'memory_limit_mb': 100,
                'connection_pool_size': 5
            },
            'performance': {
                'timeout': 60.0,
                'warmup_time': 5.0,
                'measurement_time': 30.0,
                'load_factor': 10
            },
            'stress': {
                'timeout': 300.0,
                'concurrent_clients': 50,
                'operations_per_second': 100,
                'duration': 120.0
            },
            'regression': {
                'timeout': 15.0,
                'baseline_tolerance': 0.1,
                'fail_on_regression': True
            }
        })


# Global instances
test_fixtures = TestFixtures()
performance_baseline = PerformanceBaseline()
test_data_factory = TestDataFactory()
config_manager = ConfigurationManager()
config_manager.load_default_configs()


# Pytest fixtures
@pytest.fixture
def connection_scenarios():
    """Provide connection test scenarios"""
    return test_fixtures.get_connection_scenarios()


@pytest.fixture
def subscription_scenarios():
    """Provide subscription test scenarios"""
    return test_fixtures.get_subscription_scenarios()


@pytest.fixture
def authentication_scenarios():
    """Provide authentication test scenarios"""
    return test_fixtures.get_authentication_scenarios()


@pytest.fixture
def integration_scenarios():
    """Provide integration test scenarios"""
    return test_fixtures.get_integration_scenarios()


@pytest.fixture
def scenario_runner():
    """Provide scenario runner factory"""
    def _create_runner(scenario: ScenarioConfig) -> ScenarioRunner:
        return ScenarioRunner(scenario)
    return _create_runner


@pytest.fixture
def performance_baseline_fixture():
    """Provide performance baseline"""
    return performance_baseline


@pytest.fixture
def test_data_factory_fixture():
    """Provide test data factory"""
    return test_data_factory


@pytest.fixture
def test_config():
    """Provide test configuration"""
    def _get_config(config_name: str) -> Dict[str, Any]:
        return config_manager.get_config(config_name)
    return _get_config


@pytest.fixture
def mock_server_factory():
    """Provide mock server factory"""
    def _create_server(behavior: MockServerBehavior = MockServerBehavior.NORMAL) -> MockSpacetimeDBServer:
        if behavior == MockServerBehavior.SLOW_RESPONSE:
            return create_slow_server()
        elif behavior == MockServerBehavior.INTERMITTENT_ERRORS:
            return create_unreliable_server()
        elif behavior == MockServerBehavior.AUTHENTICATION_FAILURES:
            return create_auth_failing_server()
        else:
            return create_test_server()
    return _create_server


@pytest.fixture
def temp_database():
    """Provide temporary database for testing"""
    temp_dir = tempfile.mkdtemp(prefix="spacetimedb_test_")
    
    # Create mock database files
    db_config = {
        'path': temp_dir,
        'name': 'test_db',
        'schema': TestDataGenerator.generate_schema(['users', 'messages', 'logs'])
    }
    
    yield db_config
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)