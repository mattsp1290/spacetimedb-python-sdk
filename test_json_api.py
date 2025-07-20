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


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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
from spacetimedb_sdk.spacetimedb_client import SpacetimeDBClient
from spacetimedb_sdk.protocol import EnergyQuanta
from spacetimedb_sdk.bsatn import SpacetimeDBAddress as Address


class TestJsonApiClient(unittest.TestCase):
    """Test the JSON API client functionality."""
    
    def setUp(self):
        """Set up test client without actual HTTP library dependency."""
        # We'll use the sync client with mocked requests
        # Patch the HAS_* flags to control which HTTP client is used
        with patch('spacetimedb_sdk.json_api.HAS_AIOHTTP', False), \
             patch('spacetimedb_sdk.json_api.HAS_HTTPX', False), \
             patch('spacetimedb_sdk.json_api.HAS_REQUESTS', True):
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
    
    @patch('spacetimedb_sdk.json_api.HAS_HTTPX', False)
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
        mock_response.text = ''
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session.verify = True
        mock_session_class.return_value = mock_session
        
        # Force sync mode and use requests
        self.api.use_async = False
        self.api._session = None  # Force session creation
        
        # Test
        response = self.api.list_databases_sync()
        
        # Verify session was created and used
        mock_session_class.assert_called_once()
        mock_session.request.assert_called_once()
        
        self.assertTrue(response.success)
        self.assertEqual(len(response.data), 1)
        self.assertIsInstance(response.data[0], DatabaseInfo)
        self.assertEqual(response.data[0].name, "test_db")
        self.assertEqual(response.data[0].num_tables, 5)
    
    @patch('spacetimedb_sdk.json_api.HAS_HTTPX', False)
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
        mock_response.text = ''
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session.verify = True
        mock_session_class.return_value = mock_session
        
        # Force sync mode and reset session
        self.api.use_async = False
        self.api._session = None
        
        # Test
        response = self.api.call_reducer_http_sync(
            "test_db",
            "create_user",
            ["Alice", "alice@example.com"]
        )
        
        # Verify session was created and used
        mock_session_class.assert_called_once()
        mock_session.request.assert_called_once()
        
        self.assertTrue(response.success)
        self.assertIsInstance(response.data, ReducerCallResult)
        self.assertEqual(response.data.result["name"], "Alice")
        self.assertIsNotNone(response.data.energy_used)
    
    @patch('spacetimedb_sdk.json_api.HAS_HTTPX', False)
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
        mock_session.verify = True
        mock_session_class.return_value = mock_session
        
        # Set low retry count for testing
        self.api.max_retries = 2
        self.api.retry_delay = 0.01
        self.api.use_async = False
        self.api._session = None  # Force session creation
        
        # Test
        response = self.api.get_database_info_sync("test_db")
        
        # Verify session was created
        mock_session_class.assert_called_once()
        
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
    
    @patch('spacetimedb_sdk.json_api.HAS_HTTPX', False)
    @patch('spacetimedb_sdk.json_api.requests.Session')
    def test_connection_timeout(self, mock_session_class):
        """Test connection timeout handling."""
        import requests
        
        # Mock timeout exception
        mock_session = Mock()
        mock_session.request.side_effect = requests.Timeout("Connection timeout")
        mock_session.verify = True
        mock_session_class.return_value = mock_session
        
        # Set low retry count and timeout for testing
        self.api.max_retries = 1
        self.api.retry_delay = 0.01
        self.api.timeout = 1.0
        self.api.use_async = False
        self.api._session = None
        
        # Test
        response = self.api.list_databases_sync()
        
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error)
        self.assertIn("timeout", response.error.lower())
        
        # Check retries happened
        self.assertEqual(mock_session.request.call_count, 2)  # Initial + 1 retry
    
    @patch('spacetimedb_sdk.json_api.HAS_HTTPX', False)
    @patch('spacetimedb_sdk.json_api.requests.Session')
    def test_connection_refused(self, mock_session_class):
        """Test connection refused handling."""
        import requests
        
        # Mock connection error
        mock_session = Mock()
        mock_session.request.side_effect = requests.ConnectionError("Connection refused")
        mock_session.verify = True
        mock_session_class.return_value = mock_session
        
        # Set low retry count for testing
        self.api.max_retries = 1
        self.api.retry_delay = 0.01
        self.api.use_async = False
        self.api._session = None
        
        # Test
        response = self.api.get_database_info_sync("test_db")
        
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error)
        self.assertIn("connection", response.error.lower())
        
        # Check retries happened
        self.assertEqual(mock_session.request.call_count, 2)  # Initial + 1 retry
    
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
    
    async def test_async_list_databases(self):
        """Test async list databases operation by mocking the internal async request method."""
        # Mock the internal async request method instead of HTTP client
        expected_data = [
            {
                "name": "async_db",
                "address": "async_address",
                "host": "localhost:3000"
            }
        ]
        
        mock_response = ApiResponse(
            success=True,
            data=expected_data,
            status_code=200
        )
        
        # Mock the internal _async_request method
        with patch.object(self.api, '_async_request', new_callable=AsyncMock) as mock_async_request:
            mock_async_request.return_value = mock_response
            
            # Test
            response = await self.api.list_databases()
            
            # Verify the method was called correctly
            mock_async_request.assert_called_once_with(HttpMethod.GET, "/v1/databases")
            
            self.assertTrue(response.success)
            self.assertEqual(len(response.data), 1)
            self.assertIsInstance(response.data[0], DatabaseInfo)
            self.assertEqual(response.data[0].name, "async_db")
    
    async def test_async_execute_sql(self):
        """Test async SQL execution by mocking the internal async request method."""
        # Mock the internal async request method instead of HTTP client
        expected_data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
        
        mock_response = ApiResponse(
            success=True,
            data=expected_data,
            status_code=200
        )
        
        # Mock the internal _async_request method
        with patch.object(self.api, '_async_request', new_callable=AsyncMock) as mock_async_request:
            mock_async_request.return_value = mock_response
            
            # Test
            response = await self.api.execute_sql(
                "test_db",
                "SELECT * FROM users"
            )
            
            # Verify the method was called correctly
            mock_async_request.assert_called_once_with(
                HttpMethod.POST,
                "/v1/database/test_db/sql",
                data={'query': 'SELECT * FROM users'}
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
    """Test JSON API integration with SpacetimeDBClient."""
    
    def setUp(self):
        """Set up test client."""
        # Create a mock WebSocket client
        with patch('spacetimedb_sdk.spacetimedb_client.WebSocketClient') as mock_ws_class:
            self.mock_ws = Mock()
            self.mock_ws.is_connected = False
            self.mock_ws._host = 'localhost:3000'
            self.mock_ws._ssl = False
            mock_ws_class.return_value = self.mock_ws
            
            # Create client without starting message processing
            self.client = SpacetimeDBClient(
                start_message_processing=False
            )
            
            # Set up the websocket client reference
            self.client.ws_client = self.mock_ws
    
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
        self.client.ws_client._host = "spacetimedb.com:3000"
        self.client.ws_client._ssl = True
        
        # Clear any existing json_api to force recreation
        self.client._json_api = None
        
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
        
        # Clear any existing json_api to force recreation
        self.client._json_api = None
        
        api = self.client.json_api
        self.assertEqual(api.auth_token, "client_token")


class TestConnectionBuilderIntegration(unittest.TestCase):
    """Test JSON API integration with connection builder."""
    
    @patch('spacetimedb_sdk.spacetimedb_client.WebSocketClient')
    def test_builder_with_json_api_url(self, mock_ws_class):
        """Test setting JSON API URL through builder."""
        mock_ws = Mock()
        mock_ws.is_connected = False
        mock_ws._host = 'localhost:3000'
        mock_ws._ssl = False
        mock_ws_class.return_value = mock_ws
        
        client = (SpacetimeDBClient.builder()
                  .with_uri("ws://localhost:3000")
                  .with_module_name("test_module")
                  .with_json_api_base_url("http://api.localhost:3000")
                  .build())
        
        # Access JSON API
        api = client.json_api
        self.assertEqual(api.base_url, "http://api.localhost:3000")


if __name__ == '__main__':
    unittest.main() 