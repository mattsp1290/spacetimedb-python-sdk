"""
Connection Diagnostics for SpaceTimeDB v1.1.2

Provides basic diagnostics for connection issues including server availability
and database existence checks.
"""

import time
import socket
import urllib.request
import urllib.error
import json
from typing import Dict, Any, Tuple, Optional, List
from urllib.parse import urlparse

from .exceptions import (
    SpacetimeDBError,
    DatabaseNotFoundError,
    DatabaseNotPublishedError,
    ServerNotAvailableError,
    WebSocketHandshakeError
)


class ConnectionDiagnostics:
    """
    Provides diagnostic capabilities for SpaceTimeDB connections.
    
    Features:
    - Server availability checks
    - Database existence verification
    - Connection error diagnosis
    - Network troubleshooting
    """
    
    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = 60.0  # Cache results for 60 seconds
    
    def check_server_available(self, host: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if SpaceTimeDB server is reachable.
        
        Args:
            host: Server host (e.g., "localhost:3000")
            
        Returns:
            Tuple of (is_available, server_info_dict)
        """
        cache_key = f"server_check:{host}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        server_info = {
            "host": host,
            "checked_at": time.time()
        }
        
        # Parse host and port
        if ':' in host:
            hostname, port_str = host.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 3000  # Default SpaceTimeDB port
        else:
            hostname = host
            port = 3000
        
        # Test 1: Socket connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            server_info["socket_reachable"] = (result == 0)
            server_info["port"] = port
            
            if result != 0:
                server_info["socket_error_code"] = result
                self._set_cached(cache_key, (False, server_info))
                return False, server_info
                
        except socket.gaierror as e:
            server_info["dns_error"] = str(e)
            server_info["socket_reachable"] = False
            self._set_cached(cache_key, (False, server_info))
            return False, server_info
        except Exception as e:
            server_info["socket_error"] = str(e)
            server_info["socket_reachable"] = False
            self._set_cached(cache_key, (False, server_info))
            return False, server_info
        
        # Test 2: HTTP health check
        health_url = f"http://{host}/health"
        try:
            start_time = time.time()
            
            req = urllib.request.Request(health_url)
            req.add_header('User-Agent', 'SpaceTimeDB-Python-SDK/1.1.2')
            
            with urllib.request.urlopen(req, timeout=5.0) as response:
                response_time = (time.time() - start_time) * 1000  # ms
                server_info["response_time_ms"] = round(response_time, 2)
                server_info["health_status_code"] = response.getcode()
                
                # Try to parse response
                try:
                    data = json.loads(response.read().decode('utf-8'))
                    server_info["server_version"] = data.get("version", "unknown")
                    server_info["server_status"] = data.get("status", "unknown")
                except:
                    # Health endpoint might return plain text
                    pass
                
                server_info["http_reachable"] = True
                is_available = True
                
        except urllib.error.HTTPError as e:
            server_info["health_status_code"] = e.code
            server_info["http_error"] = f"{e.code} {e.reason}"
            server_info["http_reachable"] = False
            # Server is responding but health check failed
            is_available = True  # Server is technically available
        except urllib.error.URLError as e:
            server_info["http_error"] = str(e.reason)
            server_info["http_reachable"] = False
            is_available = False
        except Exception as e:
            server_info["http_error"] = str(e)
            server_info["http_reachable"] = False
            is_available = False
        
        self._set_cached(cache_key, (is_available, server_info))
        return is_available, server_info
    
    def check_database_exists(self, host: str, database: str) -> Dict[str, Any]:
        """
        Check if database exists and its publication status.
        
        Args:
            host: Server host
            database: Database name
            
        Returns:
            Dict with keys:
            - exists: bool or "likely" or "unknown"  
            - published: bool
            - error: Optional error message
            - confidence: "high", "medium", "low", "none"
            - evidence: List of diagnostic evidence
            - suggested_action: What to do next
            - status_code: HTTP status if available
        """
        cache_key = f"db_check:{host}:{database}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        result = {
            "database": database,
            "host": host,
            "checked_at": time.time(),
            "exists": "unknown",
            "published": False,
            "confidence": "none",
            "evidence": [],
            "error": None,
            "status_code": None
        }
        
        # First check if server is available
        server_available, server_info = self.check_server_available(host)
        if not server_available:
            result["error"] = "Server not available"
            result["evidence"].append(f"Server at {host} is not reachable")
            result["suggested_action"] = f"Start SpaceTimeDB server on {host}"
            self._set_cached(cache_key, result)
            return result
        
        # Try to check database via HTTP endpoints
        # Note: These endpoints might not exist, but we try common patterns
        test_endpoints = [
            f"http://{host}/database/{database}/info",
            f"http://{host}/v1/database/{database}",
            f"http://{host}/api/databases/{database}"
        ]
        
        for endpoint in test_endpoints:
            try:
                req = urllib.request.Request(endpoint)
                req.add_header('User-Agent', 'SpaceTimeDB-Python-SDK/1.1.2')
                
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    # Database endpoint exists
                    result["exists"] = True
                    result["published"] = True
                    result["confidence"] = "high"
                    result["evidence"].append(f"HTTP endpoint {endpoint} returned {response.getcode()}")
                    result["status_code"] = response.getcode()
                    break
                    
            except urllib.error.HTTPError as e:
                result["status_code"] = e.code
                if e.code == 404:
                    result["evidence"].append(f"HTTP endpoint {endpoint} returned 404")
                elif e.code in [401, 403]:
                    # Auth error means database likely exists
                    result["exists"] = "likely"
                    result["confidence"] = "medium"
                    result["evidence"].append(f"HTTP endpoint {endpoint} returned {e.code} (auth required)")
            except:
                # Endpoint doesn't exist, try next
                continue
        
        # If no HTTP checks worked, try WebSocket probe
        if result["confidence"] == "none":
            ws_result = self._probe_websocket(host, database)
            result.update(ws_result)
        
        # Determine suggested action based on findings
        if result["exists"] == True and result["published"]:
            result["suggested_action"] = "Database is accessible"
        elif result["exists"] in [True, "likely"] and not result["published"]:
            result["suggested_action"] = f"spacetime publish {database}"
        elif result["exists"] == False:
            result["suggested_action"] = f"spacetime publish {database} --clear-database"
        else:
            result["suggested_action"] = f"spacetime publish {database} OR verify database name"
        
        self._set_cached(cache_key, result)
        return result
    
    def diagnose_connection_error(
        self, 
        error: Exception, 
        url: str,
        database_name: Optional[str] = None
    ) -> SpacetimeDBError:
        """
        Convert raw connection errors to diagnostic-rich exceptions.
        
        Args:
            error: The original exception
            url: Connection URL that failed
            database_name: Database name if known
            
        Returns:
            Enhanced SpacetimeDBError with diagnostics
        """
        # Extract host from URL
        parsed = urlparse(url)
        host = parsed.netloc or "unknown"
        
        # Extract database name from URL if not provided
        if not database_name and "/database/" in url:
            parts = url.split("/")
            try:
                db_index = parts.index("database")
                if db_index + 1 < len(parts):
                    database_name = parts[db_index + 1]
            except:
                pass
        
        error_str = str(error).lower()
        
        # Connection refused
        if "connection refused" in error_str or "errno 111" in error_str or "errno 61" in error_str:
            server_available, server_info = self.check_server_available(host)
            return ServerNotAvailableError(
                server_address=host,
                reason="Connection refused - server may not be running",
                network_diagnostics=server_info
            )
        
        # DNS/Host not found
        if "nodename nor servname provided" in error_str or "name or service not known" in error_str:
            return ServerNotAvailableError(
                server_address=host,
                reason="Host not found - check server address",
                network_diagnostics={"dns_error": "Unable to resolve hostname"}
            )
        
        # Timeout
        if "timed out" in error_str or "timeout" in error_str:
            from .exceptions import ConnectionTimeoutError
            return ConnectionTimeoutError(
                operation="WebSocket connection",
                timeout_seconds=10.0,  # Default timeout
                retry_count=0
            )
        
        # 404 errors - likely unpublished database
        if "404" in error_str or "not found" in error_str:
            if database_name:
                # Run database check
                db_check = self.check_database_exists(host, database_name)
                
                if db_check.get("exists") in [False, "unknown"]:
                    return DatabaseNotFoundError(
                        database_name=database_name,
                        status_code=404,
                        server_message="Not Found",
                        is_likely_unpublished=True,
                        diagnostic_info={
                            "url": url,
                            "database_check": db_check,
                            "database_state": "unpublished" if db_check["confidence"] in ["medium", "high"] else "unknown",
                            "confidence": db_check["confidence"]
                        }
                    )
                else:
                    return DatabaseNotPublishedError(
                        database_name=database_name,
                        host=host,
                        diagnostic_info={
                            "url": url,
                            "database_check": db_check
                        }
                    )
        
        # Protocol errors
        if "protocol" in error_str and ("mismatch" in error_str or "rejected" in error_str):
            from .exceptions import ProtocolMismatchError
            # Try to extract protocol from error
            protocol = "unknown"
            if "v1.text" in error_str:
                protocol = "v1.text.spacetimedb"
            elif "v1.json" in error_str:
                protocol = "v1.json.spacetimedb"
            elif "v1.bsatn" in error_str:
                protocol = "v1.bsatn.spacetimedb"
                
            return ProtocolMismatchError(
                requested_protocol=protocol,
                server_message=str(error)
            )
        
        # Auth errors
        if "401" in error_str or "unauthorized" in error_str:
            from .exceptions import AuthenticationError
            return AuthenticationError(
                reason="Unauthorized - check authentication token",
                status_code=401
            )
        
        # Generic connection error
        from .exceptions import SpacetimeDBConnectionError
        return SpacetimeDBConnectionError(
            message=f"Connection failed: {error}",
            cause=error,
            connection_info={
                "url": url,
                "host": host,
                "database": database_name,
                "error_type": type(error).__name__
            },
            suggestions=[
                "Check server is running",
                "Verify connection parameters",
                "Check network connectivity",
                f"Try: curl http://{host}/health"
            ]
        )
    
    def run_preflight_checks(
        self,
        host: str,
        database: str,
        raise_on_failure: bool = True
    ) -> Dict[str, Any]:
        """
        Run preflight checks before attempting connection.
        
        Args:
            host: Server host
            database: Database name
            raise_on_failure: Whether to raise exception on failure
            
        Returns:
            Dict with diagnostic results
            
        Raises:
            Appropriate SpacetimeDBError if raise_on_failure=True
        """
        results = {
            "host": host,
            "database": database,
            "timestamp": time.time(),
            "checks_passed": [],
            "checks_failed": [],
            "all_passed": True
        }
        
        # Check 1: Server availability
        server_available, server_info = self.check_server_available(host)
        results["server_check"] = server_info
        
        if server_available:
            results["checks_passed"].append("server_available")
        else:
            results["checks_failed"].append("server_available")
            results["all_passed"] = False
            
            if raise_on_failure:
                raise ServerNotAvailableError(
                    server_address=host,
                    reason="Preflight check failed - server not available",
                    network_diagnostics=server_info
                )
        
        # Check 2: Database status
        db_status = self.check_database_exists(host, database)
        results["database_check"] = db_status
        
        if db_status.get("published"):
            results["checks_passed"].append("database_published")
        else:
            results["checks_failed"].append("database_published")
            results["all_passed"] = False
            
            if raise_on_failure:
                if db_status.get("exists") in [True, "likely"]:
                    raise DatabaseNotPublishedError(
                        database_name=database,
                        host=host,
                        diagnostic_info=db_status
                    )
                else:
                    raise DatabaseNotFoundError(
                        database_name=database,
                        status_code=404,
                        diagnostic_info=db_status,
                        is_likely_unpublished=True
                    )
        
        return results
    
    def format_diagnostic_report(self, results: Dict[str, Any]) -> str:
        """
        Format diagnostic results into a readable report.
        
        Args:
            results: Diagnostic results dict
            
        Returns:
            Formatted report string
        """
        lines = [
            "SpaceTimeDB Connection Diagnostics",
            "=" * 40,
            f"Host: {results.get('host', 'unknown')}",
            f"Database: {results.get('database', 'unknown')}",
            ""
        ]
        
        # Server check results
        if "server_check" in results:
            server = results["server_check"]
            lines.append("Server Check:")
            lines.append(f"  - Available: {'✓' if server.get('socket_reachable') else '✗'}")
            if "response_time_ms" in server:
                lines.append(f"  - Response time: {server['response_time_ms']}ms")
            if "server_version" in server:
                lines.append(f"  - Version: {server['server_version']}")
            lines.append("")
        
        # Database check results
        if "database_check" in results:
            db = results["database_check"]
            lines.append("Database Check:")
            lines.append(f"  - Exists: {db.get('exists', 'unknown')}")
            lines.append(f"  - Published: {'✓' if db.get('published') else '✗'}")
            lines.append(f"  - Confidence: {db.get('confidence', 'none')}")
            if db.get("suggested_action"):
                lines.append(f"  - Action: {db['suggested_action']}")
            lines.append("")
        
        # Summary
        if "all_passed" in results:
            if results["all_passed"]:
                lines.append("✓ All checks passed")
            else:
                lines.append("✗ Some checks failed")
                if results.get("checks_failed"):
                    lines.append(f"  Failed: {', '.join(results['checks_failed'])}")
        
        return "\n".join(lines)
    
    def get_database_state(self, host: str, database: str) -> str:
        """
        Get simplified database state.
        
        Args:
            host: Server host
            database: Database name
            
        Returns:
            One of: "published", "unpublished", "non-existent", "unknown"
        """
        result = self.check_database_exists(host, database)
        
        if result.get("published"):
            return "published"
        elif result.get("exists") in [True, "likely"]:
            return "unpublished"
        elif result.get("exists") == False:
            return "non-existent"
        else:
            return "unknown"
    
    def clear_database_cache(self, host: str, database: str) -> None:
        """
        Clear cached results for a specific database.
        
        Args:
            host: Server host
            database: Database name
        """
        cache_key = f"db_check:{host}:{database}"
        if cache_key in self._cache:
            del self._cache[cache_key]
    
    def _probe_websocket(self, host: str, database: str) -> Dict[str, Any]:
        """
        Probe WebSocket endpoint to determine database state.
        
        Returns dict with additional diagnostic info.
        """
        result = {
            "evidence": [],
            "confidence": "low"
        }
        
        # We can't actually open a WebSocket here without the full client
        # But we can try an HTTP request to the WebSocket endpoint
        ws_url = f"http://{host}/v1/database/{database}/subscribe"
        
        try:
            req = urllib.request.Request(ws_url)
            req.add_header('User-Agent', 'SpaceTimeDB-Python-SDK/1.1.2')
            
            with urllib.request.urlopen(req, timeout=3.0) as response:
                # If we get here, endpoint exists but wrong protocol
                result["exists"] = "likely"
                result["published"] = False
                result["confidence"] = "medium"
                result["evidence"].append(f"WebSocket endpoint exists but requires upgrade")
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                result["exists"] = False
                result["published"] = False
                result["confidence"] = "high"
                result["evidence"].append("WebSocket endpoint returned 404")
            elif e.code == 426:  # Upgrade Required
                result["exists"] = "likely"
                result["published"] = True
                result["confidence"] = "high"
                result["evidence"].append("WebSocket endpoint requires protocol upgrade (database exists)")
        except:
            # Can't determine from this probe
            pass
        
        return result
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached result if still valid."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Any) -> None:
        """Set cached result."""
        self._cache[key] = (value, time.time())
