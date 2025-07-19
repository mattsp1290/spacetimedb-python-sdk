"""
OBSOLETE: WebSocket client regression tests for Phase 2 refactoring

These tests were designed to test the old WebSocket client API, which has been
completely refactored. The new API is fundamentally different and is tested
in the main tests/ directory.

The old API:
- Direct WebSocketClient instantiation with host, database_address, etc.
- Complex manual connection management
- Different callback patterns

The new API:
- SpacetimeDBClient.connect() or SpacetimeDBClient.builder() patterns
- Simplified connection management
- Modern callback patterns
- Enhanced features like energy tracking, compression, etc.

See tests/test_*.py for current API tests.
"""

import pytest

class TestObsoleteWebSocketClientRegression:
    """Obsolete regression tests - see main tests/ directory for current API tests"""
    
    def test_api_changed_notice(self):
        """Notify that the API has changed and these tests are obsolete"""
        assert True, "WebSocket client API has been refactored - see main tests/ directory"
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_connection_establishment_regression(self):
        """OBSOLETE: Use SpacetimeDBClient.connect() instead of WebSocketClient()"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_subscription_management_regression(self):
        """OBSOLETE: Use SpacetimeDBClient subscription methods"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_authentication_flow_regression(self):
        """OBSOLETE: Authentication is now handled automatically"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_error_handling_regression(self):
        """OBSOLETE: Error handling has been improved"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_message_sending_regression(self):
        """OBSOLETE: Message sending uses new protocol"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_connection_state_management_regression(self):
        """OBSOLETE: Connection state management has been redesigned"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_metrics_collection_regression(self):
        """OBSOLETE: Metrics collection has been enhanced"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_protocol_handling_regression(self):
        """OBSOLETE: Protocol handling has been modernized"""
        pass


class TestObsoleteSubscriptionMetricsRegression:
    """Obsolete subscription metrics tests"""
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_subscription_metrics_functionality(self):
        """OBSOLETE: Subscription metrics have been enhanced"""
        pass
    
    @pytest.mark.skip(reason="API has been refactored - see main tests/ directory")
    def test_subscription_metrics_error_handling(self):
        """OBSOLETE: Error handling has been improved"""
        pass