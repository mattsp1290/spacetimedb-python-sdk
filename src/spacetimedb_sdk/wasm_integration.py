"""
WASM Integration Foundation for SpacetimeDB Python SDK.

Provides infrastructure for testing against real SpacetimeDB WASM modules:
- SpacetimeDB server management
- WASM module loading and lifecycle
- Integration test harness
- Performance benchmarking
"""

import asyncio
import json
import os
import subprocess
import tempfile
import time
import shutil
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse
import uuid

from .modern_client import ModernSpacetimeDBClient
from .logger import get_logger, LogLevel
# Import from the testing module, not the testing package
from . import testing
MockSpacetimeDBConnection = testing.MockSpacetimeDBConnection


logger = get_logger()


@dataclass
class SpacetimeDBConfig:
    """Configuration for SpacetimeDB server instance."""
    executable_path: Optional[str] = None
    data_dir: Optional[Path] = None
    listen_port: int = 3000
    log_level: str = "info"
    enable_telemetry: bool = False
    
    def __post_init__(self):
        """Validate and set defaults."""
        if self.executable_path is None:
            # Try to find spacetimedb in PATH
            self.executable_path = shutil.which("spacetimedb")
            if not self.executable_path:
                # Check common locations
                common_paths = [
                    "/usr/local/bin/spacetimedb",
                    "$HOME/.spacetime/bin/spacetimedb",
                    "../SpacetimeDB/target/release/spacetimedb"
                ]
                for path in common_paths:
                    expanded = os.path.expandvars(os.path.expanduser(path))
                    if os.path.exists(expanded):
                        self.executable_path = expanded
                        break
        
        if self.data_dir is None:
            self.data_dir = Path(tempfile.mkdtemp(prefix="spacetimedb_test_"))


class SpacetimeDBServer:
    """Manages a SpacetimeDB server instance for testing."""
    
    def __init__(self, config: Optional[SpacetimeDBConfig] = None):
        self.config = config or SpacetimeDBConfig()
        self.process: Optional[subprocess.Popen] = None
        self._started = False
        
    def start(self, timeout: float = 30.0) -> None:
        """Start the SpacetimeDB server."""
        if self._started:
            raise RuntimeError("Server already started")
        
        if not self.config.executable_path:
            raise RuntimeError("SpacetimeDB executable not found. Set SPACETIMEDB_PATH or install SpacetimeDB")
        
        # Prepare command
        cmd = [
            self.config.executable_path,
            "start",
            "--quiet",
            f"--listen-addr", f"127.0.0.1:{self.config.listen_port}",
            f"--log-level", self.config.log_level,
        ]
        
        if not self.config.enable_telemetry:
            cmd.extend(["--no-telemetry"])
        
        # Set up environment
        env = os.environ.copy()
        env["SPACETIMEDB_DATA_DIR"] = str(self.config.data_dir)
        
        logger.info(f"Starting SpacetimeDB server",
                   executable=self.config.executable_path,
                   port=self.config.listen_port,
                   data_dir=str(self.config.data_dir))
        
        # Start server
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to be ready
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_server_ready():
                self._started = True
                logger.info("SpacetimeDB server started successfully")
                return
            
            # Check if process died
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(f"SpacetimeDB server failed to start:\n{stderr}")
            
            time.sleep(0.1)
        
        # Timeout
        self.stop()
        raise TimeoutError(f"SpacetimeDB server failed to start within {timeout}s")
    
    def stop(self) -> None:
        """Stop the SpacetimeDB server."""
        if self.process:
            logger.info("Stopping SpacetimeDB server")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Server didn't stop gracefully, killing")
                self.process.kill()
                self.process.wait()
            
            self.process = None
            self._started = False
    
    def _is_server_ready(self) -> bool:
        """Check if server is ready to accept connections."""
        try:
            # Try to connect with a simple HTTP request
            import urllib.request
            url = f"http://127.0.0.1:{self.config.listen_port}/database"
            with urllib.request.urlopen(url, timeout=1) as response:
                return response.status == 200
        except:
            return False
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        
        # Clean up data directory if it's temporary
        if self.config.data_dir and str(self.config.data_dir).startswith(tempfile.gettempdir()):
            try:
                shutil.rmtree(self.config.data_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up data directory: {e}")


@dataclass
class WASMModule:
    """Represents a WASM module for testing."""
    name: str
    path: Path
    tables: Dict[str, Any] = field(default_factory=dict)
    reducers: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, path: Union[str, Path], name: Optional[str] = None) -> 'WASMModule':
        """Create WASMModule from file path."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"WASM module not found: {path}")
        
        name = name or path.stem
        return cls(name=name, path=path)
    
    def get_bytes(self) -> bytes:
        """Get WASM module bytes."""
        return self.path.read_bytes()


class WASMTestHarness:
    """Test harness for WASM integration testing."""
    
    def __init__(self, server: Optional[SpacetimeDBServer] = None):
        self.server = server or SpacetimeDBServer()
        self.databases: Dict[str, str] = {}  # name -> address mapping
        self.clients: List[ModernSpacetimeDBClient] = []
        
    async def setup(self):
        """Set up test harness."""
        if not self.server._started:
            self.server.start()
    
    async def teardown(self):
        """Tear down test harness."""
        # Disconnect all clients
        for client in self.clients:
            try:
                await client.disconnect()
            except:
                pass
        
        self.clients.clear()
        self.databases.clear()
    
    async def publish_module(self, module: WASMModule, database_name: Optional[str] = None) -> str:
        """
        Publish a WASM module to SpacetimeDB.
        
        Returns:
            Database address
        """
        database_name = database_name or f"test_{module.name}_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Publishing WASM module",
                   module=module.name,
                   database=database_name,
                   size=len(module.get_bytes()))
        
        # Use spacetimedb CLI to publish
        cmd = [
            self.server.config.executable_path,
            "publish",
            "--skip-clippy",
            "--yes",
            str(module.path),
            database_name,
            "-s", f"http://127.0.0.1:{self.server.config.listen_port}"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to publish module: {result.stderr}")
        
        # Extract database address from output
        # Expected format: "Published database: <address>"
        for line in result.stdout.split('\n'):
            if "database address:" in line.lower():
                address = line.split(':')[-1].strip()
                self.databases[database_name] = address
                logger.info(f"Published module successfully", address=address)
                return address
        
        raise RuntimeError(f"Could not extract database address from output: {result.stdout}")
    
    async def create_client(self, database_address: str, 
                          auth_token: Optional[str] = None) -> ModernSpacetimeDBClient:
        """Create a client connected to the database."""
        uri = f"ws://127.0.0.1:{self.server.config.listen_port}"
        
        client = (ModernSpacetimeDBClient.builder()
                 .with_uri(uri)
                 .with_module_name(database_address)
                 .with_auth_token(auth_token)
                 .build())
        
        await client.connect()
        self.clients.append(client)
        
        return client
    
    async def call_reducer(self, client: ModernSpacetimeDBClient, 
                          reducer_name: str, *args) -> str:
        """Call a reducer and return request ID."""
        return client.call_reducer(reducer_name, *args)
    
    async def wait_for_transaction(self, client: ModernSpacetimeDBClient,
                                 timeout: float = 5.0) -> None:
        """Wait for a transaction to be processed."""
        # Simple implementation - wait for any transaction update
        # In real implementation, would track specific transaction
        await asyncio.sleep(0.1)  # Give server time to process
    
    @asynccontextmanager
    async def database_context(self, module: WASMModule, 
                             database_name: Optional[str] = None):
        """Context manager for database lifecycle."""
        address = await self.publish_module(module, database_name)
        try:
            yield address
        finally:
            # In future, could add database cleanup
            pass


class PerformanceBenchmark:
    """Performance benchmarking for WASM operations."""
    
    def __init__(self):
        self.measurements: Dict[str, List[float]] = {}
        
    @contextmanager
    def measure(self, operation: str):
        """Measure operation timing."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            if operation not in self.measurements:
                self.measurements[operation] = []
            self.measurements[operation].append(duration)
    
    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation."""
        if operation not in self.measurements:
            return {}
        
        times = self.measurements[operation]
        return {
            "count": len(times),
            "total": sum(times),
            "mean": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
        }
    
    def report(self) -> str:
        """Generate performance report."""
        lines = ["Performance Benchmark Report", "=" * 40]
        
        for operation, times in self.measurements.items():
            stats = self.get_stats(operation)
            lines.extend([
                f"\n{operation}:",
                f"  Count: {stats['count']}",
                f"  Mean:  {stats['mean']*1000:.3f} ms",
                f"  Min:   {stats['min']*1000:.3f} ms",
                f"  Max:   {stats['max']*1000:.3f} ms",
                f"  Total: {stats['total']:.3f} s"
            ])
        
        return "\n".join(lines)


# Test discovery and helpers

def find_sdk_test_module() -> Optional[Path]:
    """
    Find the sdk_test_module.wasm from Go SDK.
    
    Looks in common locations:
    1. SPACETIMEDB_SDK_TEST_MODULE env var
    2. Adjacent Go SDK directory
    3. Current directory
    """
    # Check environment variable
    env_path = os.environ.get("SPACETIMEDB_SDK_TEST_MODULE")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
    
    # Check common locations
    search_paths = [
        "../spacetimedb-go/sdk_test_module.wasm",
        "../../spacetimedb-go/sdk_test_module.wasm",
        "./sdk_test_module.wasm",
        "./tests/sdk_test_module.wasm",
    ]
    
    for search_path in search_paths:
        path = Path(search_path)
        if path.exists():
            return path.resolve()
    
    return None


def require_spacetimedb() -> None:
    """Skip test if SpacetimeDB is not available."""
    import pytest
    
    if not shutil.which("spacetimedb"):
        pytest.skip("SpacetimeDB executable not found in PATH")


def require_sdk_test_module() -> Path:
    """Skip test if sdk_test_module.wasm is not available."""
    import pytest
    
    module_path = find_sdk_test_module()
    if not module_path:
        pytest.skip("sdk_test_module.wasm not found. Set SPACETIMEDB_SDK_TEST_MODULE env var")
    
    return module_path


# Pytest fixtures

def pytest_fixture(func):
    """Decorator to mark pytest fixtures."""
    return func


@pytest_fixture
async def spacetimedb_server():
    """Pytest fixture providing a SpacetimeDB server."""
    server = SpacetimeDBServer()
    server.start()
    yield server
    server.stop()


@pytest_fixture
async def wasm_harness(spacetimedb_server):
    """Pytest fixture providing WASM test harness."""
    harness = WASMTestHarness(spacetimedb_server)
    await harness.setup()
    yield harness
    await harness.teardown()


@pytest_fixture
def sdk_test_module():
    """Pytest fixture providing sdk_test_module.wasm."""
    return WASMModule.from_file(require_sdk_test_module(), "sdk_test")
