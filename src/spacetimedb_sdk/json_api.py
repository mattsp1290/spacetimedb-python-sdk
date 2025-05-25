"""
JSON API Client for SpacetimeDB Python SDK.

Provides HTTP/JSON API support matching TypeScript SDK:
- Authentication and token management
- Database operations (list, info, etc.)
- HTTP-based reducer calls
- Identity management
- Module management operations
- Async/await support
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic
from urllib.parse import urljoin, urlparse
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from .protocol import Identity, EnergyQuanta
from .spacetimedb_client import Address

logger = logging.getLogger(__name__)

T = TypeVar('T')


class HttpMethod(Enum):
    """HTTP methods supported by the API."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class ApiResponse(Generic[T]):
    """Generic API response wrapper."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    raw_response: Optional[Any] = None


@dataclass
class DatabaseInfo:
    """Database information from API."""
    name: str
    address: Address
    host: str
    owner_identity: Optional[Identity] = None
    created_at: Optional[str] = None
    num_tables: int = 0
    num_reducers: int = 0


@dataclass
class ModuleInfo:
    """Module information from API."""
    name: str
    version: str
    tables: List[str] = field(default_factory=list)
    reducers: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ReducerCallResult:
    """Result of an HTTP reducer call."""
    request_id: str
    energy_used: Optional[EnergyQuanta] = None
    execution_time_ms: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class SpacetimeDBJsonAPI:
    """
    HTTP/JSON API client for SpacetimeDB operations.
    
    Provides non-WebSocket operations including:
    - Database management
    - Identity operations
    - HTTP-based reducer calls
    - Module management
    - Administrative tasks
    """
    
    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_async: bool = True,
        verify_ssl: bool = True
    ):
        """
        Initialize JSON API client.
        
        Args:
            base_url: Base URL for SpacetimeDB HTTP API
            auth_token: Authentication token
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            use_async: Whether to use async HTTP client
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_async = use_async and (HAS_AIOHTTP or HAS_HTTPX)
        self.verify_ssl = verify_ssl
        
        # Request session management
        self._session = None
        self._async_session = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Request/response logging
        self._enable_logging = False
        self._request_log: List[Dict[str, Any]] = []
        self._response_log: List[Dict[str, Any]] = []
        
        # Metrics
        self._metrics = {
            'requests_sent': 0,
            'requests_succeeded': 0,
            'requests_failed': 0,
            'total_retry_attempts': 0,
            'total_response_time_ms': 0
        }
        
        # Validate HTTP client availability
        if not (HAS_AIOHTTP or HAS_HTTPX or HAS_REQUESTS):
            raise ImportError(
                "No HTTP client library found. Install aiohttp, httpx, or requests:\n"
                "  pip install aiohttp  # Recommended for async\n"
                "  pip install httpx    # Alternative async/sync\n"
                "  pip install requests # Sync only"
            )
        
        self.logger = logging.getLogger(f"{__name__}.SpacetimeDBJsonAPI")
    
    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'SpacetimeDB-Python-SDK/1.1.1'
        }
        
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        if additional_headers:
            headers.update(additional_headers)
        
        return headers
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL for an endpoint."""
        return urljoin(self.base_url, endpoint.lstrip('/'))
    
    async def _async_request(
        self,
        method: HttpMethod,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> ApiResponse[Any]:
        """Make an async HTTP request."""
        if HAS_AIOHTTP:
            return await self._aiohttp_request(method, endpoint, data, params, headers)
        elif HAS_HTTPX:
            return await self._httpx_async_request(method, endpoint, data, params, headers)
        else:
            # Fallback to sync in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor,
                self._sync_request,
                method, endpoint, data, params, headers
            )
    
    async def _aiohttp_request(
        self,
        method: HttpMethod,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> ApiResponse[Any]:
        """Make request using aiohttp."""
        if not self._async_session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
            self._async_session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
        
        url = self._build_url(endpoint)
        request_headers = self._get_headers(headers)
        
        attempt = 0
        last_error = None
        
        while attempt <= self.max_retries:
            try:
                start_time = time.time()
                
                async with self._async_session.request(
                    method.value,
                    url,
                    json=data,
                    params=params,
                    headers=request_headers
                ) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    response_data = None
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
                    
                    self._log_request_response(
                        method, url, data, params, request_headers,
                        response.status, response_data, response_time
                    )
                    
                    if response.status >= 200 and response.status < 300:
                        self._metrics['requests_succeeded'] += 1
                        return ApiResponse(
                            success=True,
                            data=response_data,
                            status_code=response.status,
                            headers=dict(response.headers),
                            raw_response=response
                        )
                    else:
                        error_msg = response_data if isinstance(response_data, str) else json.dumps(response_data)
                        last_error = f"HTTP {response.status}: {error_msg}"
                        
                        if response.status < 500:  # Don't retry client errors
                            break
                            
            except Exception as e:
                last_error = str(e)
                self.logger.error(f"Request failed (attempt {attempt + 1}): {e}")
            
            attempt += 1
            if attempt <= self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)
                self._metrics['total_retry_attempts'] += 1
        
        self._metrics['requests_failed'] += 1
        return ApiResponse(
            success=False,
            error=last_error or "Request failed",
            status_code=500
        )
    
    async def _httpx_async_request(
        self,
        method: HttpMethod,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> ApiResponse[Any]:
        """Make request using httpx async."""
        if not self._async_session:
            self._async_session = httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl
            )
        
        url = self._build_url(endpoint)
        request_headers = self._get_headers(headers)
        
        attempt = 0
        last_error = None
        
        while attempt <= self.max_retries:
            try:
                start_time = time.time()
                
                response = await self._async_session.request(
                    method.value,
                    url,
                    json=data,
                    params=params,
                    headers=request_headers
                )
                
                response_time = (time.time() - start_time) * 1000
                
                response_data = None
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                self._log_request_response(
                    method, url, data, params, request_headers,
                    response.status_code, response_data, response_time
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    self._metrics['requests_succeeded'] += 1
                    return ApiResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        raw_response=response
                    )
                else:
                    error_msg = response_data if isinstance(response_data, str) else json.dumps(response_data)
                    last_error = f"HTTP {response.status_code}: {error_msg}"
                    
                    if response.status_code < 500:  # Don't retry client errors
                        break
                        
            except Exception as e:
                last_error = str(e)
                self.logger.error(f"Request failed (attempt {attempt + 1}): {e}")
            
            attempt += 1
            if attempt <= self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)
                self._metrics['total_retry_attempts'] += 1
        
        self._metrics['requests_failed'] += 1
        return ApiResponse(
            success=False,
            error=last_error or "Request failed",
            status_code=500
        )
    
    def _sync_request(
        self,
        method: HttpMethod,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> ApiResponse[Any]:
        """Make a synchronous HTTP request."""
        if HAS_HTTPX:
            return self._httpx_sync_request(method, endpoint, data, params, headers)
        elif HAS_REQUESTS:
            return self._requests_sync_request(method, endpoint, data, params, headers)
        else:
            raise RuntimeError("No sync HTTP client available")
    
    def _requests_sync_request(
        self,
        method: HttpMethod,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> ApiResponse[Any]:
        """Make request using requests library."""
        if not self._session:
            self._session = requests.Session()
            self._session.verify = self.verify_ssl
        
        url = self._build_url(endpoint)
        request_headers = self._get_headers(headers)
        
        attempt = 0
        last_error = None
        
        while attempt <= self.max_retries:
            try:
                start_time = time.time()
                
                response = self._session.request(
                    method.value,
                    url,
                    json=data,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout
                )
                
                response_time = (time.time() - start_time) * 1000
                
                response_data = None
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                self._log_request_response(
                    method, url, data, params, request_headers,
                    response.status_code, response_data, response_time
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    self._metrics['requests_succeeded'] += 1
                    return ApiResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        raw_response=response
                    )
                else:
                    error_msg = response_data if isinstance(response_data, str) else json.dumps(response_data)
                    last_error = f"HTTP {response.status_code}: {error_msg}"
                    
                    if response.status_code < 500:  # Don't retry client errors
                        break
                        
            except Exception as e:
                last_error = str(e)
                self.logger.error(f"Request failed (attempt {attempt + 1}): {e}")
            
            attempt += 1
            if attempt <= self.max_retries:
                time.sleep(self.retry_delay * attempt)
                self._metrics['total_retry_attempts'] += 1
        
        self._metrics['requests_failed'] += 1
        return ApiResponse(
            success=False,
            error=last_error or "Request failed",
            status_code=500
        )
    
    def _httpx_sync_request(
        self,
        method: HttpMethod,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> ApiResponse[Any]:
        """Make request using httpx sync."""
        if not self._session:
            self._session = httpx.Client(
                timeout=self.timeout,
                verify=self.verify_ssl
            )
        
        url = self._build_url(endpoint)
        request_headers = self._get_headers(headers)
        
        attempt = 0
        last_error = None
        
        while attempt <= self.max_retries:
            try:
                start_time = time.time()
                
                response = self._session.request(
                    method.value,
                    url,
                    json=data,
                    params=params,
                    headers=request_headers
                )
                
                response_time = (time.time() - start_time) * 1000
                
                response_data = None
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                self._log_request_response(
                    method, url, data, params, request_headers,
                    response.status_code, response_data, response_time
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    self._metrics['requests_succeeded'] += 1
                    return ApiResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        raw_response=response
                    )
                else:
                    error_msg = response_data if isinstance(response_data, str) else json.dumps(response_data)
                    last_error = f"HTTP {response.status_code}: {error_msg}"
                    
                    if response.status_code < 500:  # Don't retry client errors
                        break
                        
            except Exception as e:
                last_error = str(e)
                self.logger.error(f"Request failed (attempt {attempt + 1}): {e}")
            
            attempt += 1
            if attempt <= self.max_retries:
                time.sleep(self.retry_delay * attempt)
                self._metrics['total_retry_attempts'] += 1
        
        self._metrics['requests_failed'] += 1
        return ApiResponse(
            success=False,
            error=last_error or "Request failed",
            status_code=500
        )
    
    def _log_request_response(
        self,
        method: HttpMethod,
        url: str,
        data: Any,
        params: Any,
        headers: Dict[str, str],
        status_code: int,
        response_data: Any,
        response_time: float
    ) -> None:
        """Log request and response for debugging."""
        self._metrics['requests_sent'] += 1
        self._metrics['total_response_time_ms'] += response_time
        
        if self._enable_logging:
            request_log = {
                'timestamp': time.time(),
                'method': method.value,
                'url': url,
                'data': data,
                'params': params,
                'headers': headers
            }
            
            response_log = {
                'timestamp': time.time(),
                'status_code': status_code,
                'response_data': response_data,
                'response_time_ms': response_time
            }
            
            self._request_log.append(request_log)
            self._response_log.append(response_log)
            
            self.logger.debug(f"{method.value} {url} -> {status_code} ({response_time:.2f}ms)")
    
    # Public API methods
    
    async def list_databases(self) -> ApiResponse[List[DatabaseInfo]]:
        """
        List all available databases.
        
        Returns:
            ApiResponse containing list of DatabaseInfo
        """
        response = await self._async_request(HttpMethod.GET, "/databases")
        
        if response.success and response.data:
            databases = []
            for db_data in response.data:
                databases.append(DatabaseInfo(**db_data))
            response.data = databases
        
        return response
    
    async def get_database_info(self, database_name: str) -> ApiResponse[DatabaseInfo]:
        """
        Get information about a specific database.
        
        Args:
            database_name: Name of the database
            
        Returns:
            ApiResponse containing DatabaseInfo
        """
        response = await self._async_request(
            HttpMethod.GET,
            f"/databases/{database_name}"
        )
        
        if response.success and response.data:
            response.data = DatabaseInfo(**response.data)
        
        return response
    
    async def get_identity_info(self) -> ApiResponse[Dict[str, Any]]:
        """
        Get current identity information.
        
        Returns:
            ApiResponse containing identity data
        """
        return await self._async_request(HttpMethod.GET, "/identity")
    
    async def call_reducer_http(
        self,
        database_name: str,
        reducer_name: str,
        args: List[Any]
    ) -> ApiResponse[ReducerCallResult]:
        """
        Call a reducer via HTTP.
        
        Args:
            database_name: Name of the database
            reducer_name: Name of the reducer
            args: Arguments for the reducer
            
        Returns:
            ApiResponse containing ReducerCallResult
        """
        import uuid
        request_id = str(uuid.uuid4())
        
        data = {
            'request_id': request_id,
            'reducer': reducer_name,
            'args': args
        }
        
        start_time = time.time()
        response = await self._async_request(
            HttpMethod.POST,
            f"/databases/{database_name}/reducers/{reducer_name}/call",
            data=data
        )
        execution_time = (time.time() - start_time) * 1000
        
        if response.success and response.data:
            result = ReducerCallResult(
                request_id=request_id,
                execution_time_ms=execution_time,
                result=response.data.get('result'),
                error=response.data.get('error'),
                energy_used=EnergyQuanta(response.data['energy_used']) if 'energy_used' in response.data else None
            )
            response.data = result
        
        return response
    
    async def get_module_info(self, database_name: str) -> ApiResponse[ModuleInfo]:
        """
        Get module information for a database.
        
        Args:
            database_name: Name of the database
            
        Returns:
            ApiResponse containing ModuleInfo
        """
        response = await self._async_request(
            HttpMethod.GET,
            f"/databases/{database_name}/module"
        )
        
        if response.success and response.data:
            response.data = ModuleInfo(**response.data)
        
        return response
    
    async def execute_sql(
        self,
        database_name: str,
        query: str
    ) -> ApiResponse[List[Dict[str, Any]]]:
        """
        Execute a SQL query via HTTP.
        
        Args:
            database_name: Name of the database
            query: SQL query to execute
            
        Returns:
            ApiResponse containing query results
        """
        data = {'query': query}
        
        return await self._async_request(
            HttpMethod.POST,
            f"/databases/{database_name}/sql",
            data=data
        )
    
    # Sync wrappers for convenience
    
    def list_databases_sync(self) -> ApiResponse[List[DatabaseInfo]]:
        """Synchronous version of list_databases."""
        if self.use_async:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.list_databases())
            finally:
                loop.close()
        else:
            response = self._sync_request(HttpMethod.GET, "/databases")
            
            if response.success and response.data:
                databases = []
                for db_data in response.data:
                    databases.append(DatabaseInfo(**db_data))
                response.data = databases
            
            return response
    
    def get_database_info_sync(self, database_name: str) -> ApiResponse[DatabaseInfo]:
        """Synchronous version of get_database_info."""
        if self.use_async:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.get_database_info(database_name))
            finally:
                loop.close()
        else:
            response = self._sync_request(
                HttpMethod.GET,
                f"/databases/{database_name}"
            )
            
            if response.success and response.data:
                response.data = DatabaseInfo(**response.data)
            
            return response
    
    def call_reducer_http_sync(
        self,
        database_name: str,
        reducer_name: str,
        args: List[Any]
    ) -> ApiResponse[ReducerCallResult]:
        """Synchronous version of call_reducer_http."""
        if self.use_async:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.call_reducer_http(database_name, reducer_name, args)
                )
            finally:
                loop.close()
        else:
            import uuid
            request_id = str(uuid.uuid4())
            
            data = {
                'request_id': request_id,
                'reducer': reducer_name,
                'args': args
            }
            
            start_time = time.time()
            response = self._sync_request(
                HttpMethod.POST,
                f"/databases/{database_name}/reducers/{reducer_name}/call",
                data=data
            )
            execution_time = (time.time() - start_time) * 1000
            
            if response.success and response.data:
                result = ReducerCallResult(
                    request_id=request_id,
                    execution_time_ms=execution_time,
                    result=response.data.get('result'),
                    error=response.data.get('error'),
                    energy_used=EnergyQuanta(response.data['energy_used']) if 'energy_used' in response.data else None
                )
                response.data = result
            
            return response
    
    # Utility methods
    
    def enable_request_logging(self, enabled: bool = True) -> None:
        """Enable or disable request/response logging."""
        self._enable_logging = enabled
    
    def get_request_logs(self) -> List[Dict[str, Any]]:
        """Get request logs."""
        return self._request_log.copy()
    
    def get_response_logs(self) -> List[Dict[str, Any]]:
        """Get response logs."""
        return self._response_log.copy()
    
    def clear_logs(self) -> None:
        """Clear request/response logs."""
        self._request_log.clear()
        self._response_log.clear()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get API client metrics."""
        metrics = self._metrics.copy()
        
        if metrics['requests_sent'] > 0:
            metrics['success_rate'] = metrics['requests_succeeded'] / metrics['requests_sent']
            metrics['average_response_time_ms'] = metrics['total_response_time_ms'] / metrics['requests_sent']
        else:
            metrics['success_rate'] = 0
            metrics['average_response_time_ms'] = 0
        
        return metrics
    
    def reset_metrics(self) -> None:
        """Reset API client metrics."""
        self._metrics = {
            'requests_sent': 0,
            'requests_succeeded': 0,
            'requests_failed': 0,
            'total_retry_attempts': 0,
            'total_response_time_ms': 0
        }
    
    async def close(self) -> None:
        """Close HTTP sessions and cleanup resources."""
        if self._async_session:
            if HAS_AIOHTTP and isinstance(self._async_session, aiohttp.ClientSession):
                await self._async_session.close()
            elif HAS_HTTPX and isinstance(self._async_session, httpx.AsyncClient):
                await self._async_session.aclose()
            self._async_session = None
        
        if self._session:
            if HAS_REQUESTS and isinstance(self._session, requests.Session):
                self._session.close()
            elif HAS_HTTPX and isinstance(self._session, httpx.Client):
                self._session.close()
            self._session = None
        
        if self._executor:
            self._executor.shutdown(wait=True)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Run async close in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.close())
        finally:
            loop.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close() 