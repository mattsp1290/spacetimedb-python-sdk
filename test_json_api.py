"""
Test JSON API Client for SpacetimeDB Python SDK.

Tests the HTTP/JSON API support:
- API client initialization and configuration
- Database operations (list, info)
- Identity management
- HTTP-based reducer calls
- Module information retrieval
- SQL query execution
- Error handling and retries
- Sync/async operations
- Metrics and logging
"""

import unittest
import asyncio
import json
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Dict, Any, List

from spacetimedb_sdk.json_api import (
    SpacetimeDBJsonAPI,
    ApiResponse,
    DatabaseInfo,
    ModuleInfo,
    ReducerCallResult,
    HttpMethod
)
from spacetimedb_sdk import ModernSpacetimeDBClient


class TestJsonApiClient(unittest.TestCase):
    """Test the JSON API client functionality."""
    
    def setUp(self):
        """Set up test client without actual HTTP library dependency."""
        # We'll use the sync client with mocked requests
        self.api = SpacetimeDBJsonAPI(
            base_url="http://localhost:3000",
            auth_token="test_token",
            use_async=False
        )
    
    def test_initialization(self):
        """Test API client initialization."""
        api = SpacetimeDBJsonAPI(
            base_url="https://api.spacetimedb.com",
            auth_token="my_token",
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
            use_async=True,
            verify_ssl=False
        )
        
        self.assertEqual(api.base_url, "https://api.spacetimedb.com")
        self.assertEqual(api.auth_token, "my_token")
        self.assertEqual(api.timeout, 60.0)
        self.assertEqual(api.max_retries, 5)
        self.assertEqual(api.retry_delay, 2.0)
        self.assertFalse(api.verify_ssl)
    
    def test_headers_generation(self):
        """Test header generation with authentication."""
        # With auth token
        api = SpacetimeDBJsonAPI("http://localhost", auth_token="test_token")
        headers = api._get_headers()
        
        self.assertEqual(headers['Authorization'], 'Bearer test_token')
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['Accept'], 'application/json')
        self.assertIn('SpacetimeDB-Python-SDK', headers['User-Agent'])
        
        # Without auth token
        api_no_auth = SpacetimeDBJsonAPI("http://localhost")
        headers_no_auth = api_no_auth._get_headers()
        self.assertNotIn('Authorization', headers_no_auth)
    
    def test_url_building(self):
        """Test URL building from base and endpoint."""
        api = SpacetimeDBJsonAPI("http://localhost:3000/")
        
        self.assertEqual(
            api._build_url("/databases"),
            "http://localhost:3000/databases"
        )
        self.assertEqual(
            api._build_url("databases/mydb"),
            "http://localhost:3000/databases/mydb"
        )
    
    @patch('spacetimedb_sdk.json_api.requests.Session')
    def test_list_databases_sync(self, mock_session_class):
        """Test synchronous list databases operation."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "test_db",
                "address": "test_address",
                "host": "localhost:3000",
                "num_tables": 5,
                "num_reducers": 10
            }
        ]
        mock_response.headers = {}
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Force sync mode
        self.api.use_async = False
        
        # Test
        response = self.api.list_databases_sync()
        
        self.assertTrue(response.success)
        self.assertEqual(len(response.data), 1)
        self.assertIsInstance(response.data[0], DatabaseInfo)
        self.assertEqual(response.data[0].name, "test_db")
        self.assertEqual(response.data[0].num_tables, 5)
    
    @patch('spacetimedb_sdk.json_api.requests.Session')
    def test_call_reducer_http_sync(self, mock_session_class):
        """Test synchronous HTTP reducer call."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"user_id": 123, "name": "Alice"},
            "energy_used": 100
        }
        mock_response.headers = {}
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Force sync mode
        self.api.use_async = False
        
        # Test
        response = self.api.call_reducer_http_sync(
            "test_db",
            "create_user",
            ["Alice", "alice@example.com"]
        )
        
        self.assertTrue(response.success)
        self.assertIsInstance(response.data, ReducerCallResult)
        self.assertEqual(response.data.result["name"], "Alice")
        self.assertIsNotNone(response.data.energy_used)
    
    @patch('spacetimedb_sdk.json_api.requests.Session')
    def test_error_handling(self, mock_session_class):
        """Test error handling and retries."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError()
        mock_response.text = "Internal Server Error"
        mock_response.headers = {}
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Set low retry count for testing
        self.api.max_retries = 2
        self.api.retry_delay = 0.01
        self.api.use_async = False
        
        # Test
        response = self.api.get_database_info_sync("test_db")
        
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error)
        self.assertEqual(response.status_code, 500)
        
        # Check retries happened
        self.assertEqual(mock_session.request.call_count, 3)  # Initial + 2 retries
    
    def test_metrics_tracking(self):
        """Test metrics collection."""
        # Reset metrics
        self.api.reset_metrics()
        
        # Simulate some requests
        self.api._metrics['requests_sent'] = 10
        self.api._metrics['requests_succeeded'] = 8
        self.api._metrics['requests_failed'] = 2
        self.api._metrics['total_retry_attempts'] = 3
        self.api._metrics['total_response_time_ms'] = 1500
        
        metrics = self.api.get_metrics()
        
        self.assertEqual(metrics['requests_sent'], 10)
        self.assertEqual(metrics['success_rate'], 0.8)
        self.assertEqual(metrics['average_response_time_ms'], 150)
        self.assertEqual(metrics['total_retry_attempts'], 3)
    
    def test_request_logging(self):
        """Test request/response logging."""
        # Enable logging
        self.api.enable_request_logging(True)
        
        # Log a request/response
        self.api._log_request_response(
            HttpMethod.GET,
            "http://localhost:3000/databases",
            None,
            None,
            {"Authorization": "Bearer test"},
            200,
            {"databases": []},
            25.5
        )
        
        # Check logs
        request_logs = self.api.get_request_logs()
        response_logs = self.api.get_response_logs()
        
        self.assertEqual(len(request_logs), 1)
        self.assertEqual(request_logs[0]['method'], "GET")
        self.assertEqual(request_logs[0]['url'], "http://localhost:3000/databases")
        
        self.assertEqual(len(response_logs), 1)
        self.assertEqual(response_logs[0]['status_code'], 200)
        self.assertEqual(response_logs[0]['response_time_ms'], 25.5)
        
        # Clear logs
        self.api.clear_logs()
        self.assertEqual(len(self.api.get_request_logs()), 0)
    
    def test_context_manager(self):
        """Test context manager functionality."""
        with SpacetimeDBJsonAPI("http://localhost:3000") as api:
            self.assertIsNotNone(api)
            # API should be usable here
        
        # After context, resources should be cleaned up
        # (We can't easily test this without mocking the session cleanup)


class TestAsyncJsonApiClient(unittest.IsolatedAsyncioTestCase):
    """Test async functionality of JSON API client."""
    
    async def asyncSetUp(self):
        """Set up async test client."""
        self.api = SpacetimeDBJsonAPI(
            base_url="http://localhost:3000",
            auth_token="test_token",
            use_async=True
        )
    
    @patch('spacetimedb_sdk.json_api.aiohttp.ClientSession')
    async def test_async_list_databases(self, mock_session_class):
        """Test async list databases operation."""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {
                "name": "async_db",
                "address": "async_address",
                "host": "localhost:3000"
            }
        ])
        mock_response.headers = {}
        
        mock_session = AsyncMock()
        mock_session.request = AsyncMock()
        mock_session.request.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Force aiohttp
        self.api._async_session = mock_session
        
        # Test
        response = await self.api.list_databases()
        
        self.assertTrue(response.success)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].name, "async_db")
    
    @patch('spacetimedb_sdk.json_api.aiohttp.ClientSession')
    async def test_async_execute_sql(self, mock_session_class):
        """Test async SQL execution."""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ])
        mock_response.headers = {}
        
        mock_session = AsyncMock()
        mock_session.request = AsyncMock()
        mock_session.request.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Force aiohttp
        self.api._async_session = mock_session
        
        # Test
        response = await self.api.execute_sql(
            "test_db",
            "SELECT * FROM users"
        )
        
        self.assertTrue(response.success)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["name"], "Alice")
    
    async def test_async_context_manager(self):
        """Test async context manager."""
        async with SpacetimeDBJsonAPI("http://localhost:3000") as api:
            self.assertIsNotNone(api)
            # API should be usable here
        
        # Resources should be cleaned up after context


class TestClientIntegration(unittest.TestCase):
    """Test JSON API integration with ModernSpacetimeDBClient."""
    
    @patch('spacetimedb_sdk.modern_client.ModernWebSocketClient')
    def setUp(self, mock_ws_class):
        """Set up test client."""
        self.mock_ws = Mock()
        mock_ws_class.return_value = self.mock_ws
        
        self.client = ModernSpacetimeDBClient(
            start_message_processing=False
        )
    
    def test_json_api_property(self):
        """Test accessing JSON API through client."""
        # First access should create the API client
        api = self.client.json_api
        self.assertIsInstance(api, SpacetimeDBJsonAPI)
        
        # Subsequent access should return same instance
        api2 = self.client.json_api
        self.assertIs(api, api2)
    
    def test_json_api_url_derivation(self):
        """Test JSON API URL is derived from WebSocket connection."""
        # Set up mock WebSocket client with connection info
        self.client.ws_client = Mock()
        self.client.ws_client._host = "spacetimedb.com:3000"
        self.client.ws_client._ssl = True
        
        api = self.client.json_api
        self.assertEqual(api.base_url, "https://spacetimedb.com:3000")
    
    def test_set_json_api_base_url(self):
        """Test setting custom JSON API base URL."""
        # Set custom URL
        self.client.set_json_api_base_url("https://api.custom.com")
        
        # Access API
        api = self.client.json_api
        self.assertEqual(api.base_url, "https://api.custom.com")
    
    def test_json_api_auth_token(self):
        """Test JSON API uses client auth token."""
        self.client.auth_token = "client_token"
        
        api = self.client.json_api
        self.assertEqual(api.auth_token, "client_token")


class TestConnectionBuilderIntegration(unittest.TestCase):
    """Test JSON API integration with connection builder."""
    
    @patch('spacetimedb_sdk.modern_client.ModernWebSocketClient')
    def test_builder_with_json_api_url(self, mock_ws_class):
        """Test setting JSON API URL through builder."""
        mock_ws = Mock()
        mock_ws.is_connected = False
        mock_ws_class.return_value = mock_ws
        
        client = (ModernSpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("test_module")
                  .with_json_api_base_url("http://api.localhost:3000")
                  .build())
        
        # Access JSON API
        api = client.json_api
        self.assertEqual(api.base_url, "http://api.localhost:3000")


if __name__ == '__main__':
    unittest.main() 