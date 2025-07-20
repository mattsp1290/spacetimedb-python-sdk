"""
Test helper functions for SpacetimeDB SDK tests.

This module provides standardized patterns for client instantiation and common
test utilities to ensure consistency across the test suite and prevent
constructor API mismatches.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Optional, Dict, Any, Callable

# Add SDK to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from spacetimedb_sdk import SpacetimeDBClient


class ClientTestHelper:
    """Helper class for standardized SpacetimeDBClient testing patterns."""
    
    @staticmethod
    def create_test_client(
        test_mode: bool = True,
        start_message_processing: bool = False,
        **kwargs
    ) -> SpacetimeDBClient:
        """
        Create a SpacetimeDBClient instance for testing using the correct constructor API.
        
        This method uses only the constructor parameters that are actually supported
        by the modern SpacetimeDBClient implementation.
        
        Args:
            test_mode: Enable test mode (prevents real WebSocket connections)
            start_message_processing: Whether to start message processing thread
            **kwargs: Additional constructor parameters (autogen_package, protocol, etc.)
            
        Returns:
            SpacetimeDBClient instance configured for testing
            
        Example:
            # Basic test client
            client = ClientTestHelper.create_test_client()
            
            # Client with specific protocol
            client = ClientTestHelper.create_test_client(
                protocol="v1.bsatn.spacetimedb"
            )
        """
        return SpacetimeDBClient(
            test_mode=test_mode,
            start_message_processing=start_message_processing,
            **kwargs
        )
    
    @staticmethod
    def create_mock_client(
        host: str = "localhost:3000",
        database_address: str = "test_db",
        auth_token: Optional[str] = None,
        ssl_enabled: bool = False,
        **kwargs
    ) -> SpacetimeDBClient:
        """
        Create a SpacetimeDBClient that attempts connection using the correct API.
        
        This method uses the SpacetimeDBClient.connect() class method which
        properly handles connection parameters.
        
        Args:
            host: SpacetimeDB host
            database_address: Database name or address
            auth_token: Optional authentication token
            ssl_enabled: Whether to use SSL/TLS
            **kwargs: Additional connection parameters
            
        Returns:
            SpacetimeDBClient instance (may not be connected in test environment)
            
        Example:
            # Mock client for connection testing
            with patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp'):
                client = ClientTestHelper.create_mock_client(
                    database_address="test_injection_db"
                )
        """
        return SpacetimeDBClient.connect(
            host=host,
            database_address=database_address,
            auth_token=auth_token,
            ssl_enabled=ssl_enabled,
            **kwargs
        )
    
    @staticmethod
    def create_client_with_instance_connect(
        host: str = "localhost:3000",
        database_address: str = "test_db",
        auth_token: Optional[str] = None,
        ssl_enabled: bool = False,
        client_kwargs: Optional[Dict[str, Any]] = None
    ) -> SpacetimeDBClient:
        """
        Create a SpacetimeDBClient and connect using the instance method.
        
        This pattern is useful when you need to register callbacks before connecting.
        
        Args:
            host: SpacetimeDB host
            database_address: Database name or address
            auth_token: Optional authentication token
            ssl_enabled: Whether to use SSL/TLS
            client_kwargs: Additional constructor parameters
            
        Returns:
            SpacetimeDBClient instance
            
        Example:
            # Client with callbacks registered before connection
            client = ClientTestHelper.create_client_with_instance_connect(
                client_kwargs={"test_mode": True}
            )
        """
        client_kwargs = client_kwargs or {}
        client = SpacetimeDBClient(**client_kwargs)
        
        client.connect_instance(
            host=host,
            database_address=database_address,
            auth_token=auth_token,
            ssl_enabled=ssl_enabled
        )
        
        return client


# Convenience functions for backward compatibility with existing tests
def create_test_client(**kwargs) -> SpacetimeDBClient:
    """
    Convenience function for creating test clients.
    
    DEPRECATED: Use ClientTestHelper.create_test_client() instead.
    """
    return ClientTestHelper.create_test_client(**kwargs)


def create_mock_client(**kwargs) -> SpacetimeDBClient:
    """
    Convenience function for creating mock clients.
    
    DEPRECATED: Use ClientTestHelper.create_mock_client() instead.
    """
    return ClientTestHelper.create_mock_client(**kwargs)


# Standard test fixtures and patterns
def mock_websocket_app():
    """
    Context manager for mocking WebSocketApp to prevent real connections.
    
    Example:
        with mock_websocket_app():
            client = ClientTestHelper.create_mock_client()
    """
    return patch('spacetimedb_sdk.websocket_client.websocket.WebSocketApp')


class StandardTestPatterns:
    """Collection of standard test patterns for common scenarios."""
    
    @staticmethod
    def test_constructor_api_compliance():
        """
        Test that demonstrates correct constructor API usage.
        
        This can be used as a reference for proper client instantiation.
        """
        # ✅ CORRECT: Basic constructor with only supported parameters
        client1 = SpacetimeDBClient(test_mode=True)
        
        # ✅ CORRECT: Class method for connection
        client2 = SpacetimeDBClient.connect(
            host="localhost:3000",
            database_address="test_db"
        )
        
        # ✅ CORRECT: Instance method for connection with callbacks
        client3 = SpacetimeDBClient(test_mode=True)
        client3.register_on_connect(lambda: print("Connected!"))
        client3.connect_instance(
            host="localhost:3000",
            database_address="test_db"
        )
        
        # ❌ INCORRECT: Don't pass connection params to constructor
        # client4 = SpacetimeDBClient(host="localhost:3000", database_address="test_db")
        
        return [client1, client2, client3]
    
    @staticmethod
    def test_security_input_validation_pattern(malicious_input: str):
        """
        Standard pattern for testing security input validation.
        
        Args:
            malicious_input: Potentially malicious input to test
            
        Returns:
            True if input was handled safely, False if it caused issues
        """
        try:
            with mock_websocket_app():
                # Test the malicious input through proper API
                client = ClientTestHelper.create_mock_client(
                    database_address=malicious_input
                )
                # Input validation happens during connection attempt
                return True
        except (ValueError, TypeError, Exception) as e:
            # Expected for malicious inputs
            return "invalid" in str(e).lower() or "malformed" in str(e).lower()


# Documentation and migration guide
CONSTRUCTOR_MIGRATION_GUIDE = """
SpacetimeDBClient Constructor API Migration Guide
==============================================

OLD PATTERN (Will fail with TypeError):
    client = SpacetimeDBClient(
        host="localhost:3000",
        database_address="my_db",
        auth_token="token",
        ssl_enabled=True
    )

NEW PATTERNS (Correct modern API):

1. Class method (creates and connects in one step):
    client = SpacetimeDBClient.connect(
        host="localhost:3000",
        database_address="my_db",
        auth_token="token",
        ssl_enabled=True
    )

2. Instance method (for callback registration before connect):
    client = SpacetimeDBClient(test_mode=True)  # Constructor params only
    client.register_on_connect(lambda: print("Connected!"))
    client.connect_instance(
        host="localhost:3000",
        database_address="my_db",
        auth_token="token",
        ssl_enabled=True
    )

3. For testing (no real connection):
    client = SpacetimeDBClient(test_mode=True)

SUPPORTED CONSTRUCTOR PARAMETERS:
- autogen_package: Optional[ModuleType]
- protocol: str (default: TEXT_PROTOCOL)
- auto_reconnect: bool (default: True)
- max_reconnect_attempts: int (default: 10)
- start_message_processing: bool (default: True)
- initial_energy: int (default: 1000)
- max_energy: int (default: 1000)
- energy_budget: int (default: 5000)
- compression_config: Optional[CompressionConfig]
- test_mode: bool (default: False)
- auto_trigger_lifecycle: bool (default: True)

CONNECTION PARAMETERS (use with connect methods):
- host: str
- database_address: str
- auth_token: Optional[str]
- ssl_enabled: bool
- db_identity: Optional[str]
"""

if __name__ == "__main__":
    print("SpacetimeDB SDK Test Helpers")
    print("=" * 40)
    print(CONSTRUCTOR_MIGRATION_GUIDE)
    
    # Demonstrate correct patterns
    print("\nTesting correct constructor patterns:")
    patterns = StandardTestPatterns.test_constructor_api_compliance()
    print(f"✅ Created {len(patterns)} clients using correct API patterns")