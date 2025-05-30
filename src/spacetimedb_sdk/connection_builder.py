"""
SpacetimeDB Connection Builder

Provides a fluent builder API for creating SpacetimeDB connections,
matching the TypeScript SDK's DbConnection.builder() pattern.

Example usage:
    conn = ModernSpacetimeDBClient.builder() \
        .with_uri("ws://localhost:3000") \
        .with_module_name("my_module") \
        .with_token("auth_token") \
        .with_protocol(TEXT_PROTOCOL) \
        .on_connect(lambda: print("Connected!")) \
        .on_disconnect(lambda reason: print(f"Disconnected: {reason}")) \
        .with_energy_budget(10000) \
        .build()
"""

from typing import Optional, Callable, Any, Dict, List, TYPE_CHECKING
from types import ModuleType
import urllib.parse

# Import compression classes for builder configuration  
from .compression import CompressionConfig, CompressionLevel

# Import DbContext types
from .db_context import DbContext, DbView, Reducers, SetReducerFlags

from .protocol import CallReducerFlags, TEXT_PROTOCOL, BIN_PROTOCOL

# Import shared types
from .shared_types import RetryPolicy

if TYPE_CHECKING:
    from .modern_client import ModernSpacetimeDBClient
    from .protocol import Identity
    from .connection_pool import ConnectionPool, LoadBalancedConnectionManager

from .time_utils import EnhancedTimestamp, EnhancedTimeDuration, ScheduleAt


class SpacetimeDBConnectionBuilder:
    """
    Fluent builder for creating SpacetimeDB client connections.
    
    Provides a modern, TypeScript SDK-compatible API for configuring
    and creating SpacetimeDB client connections with comprehensive
    validation and callback support.
    """
    
    def __init__(self):
        """Initialize the connection builder with default values."""
        # Connection parameters
        self._uri: Optional[str] = None
        self._host: Optional[str] = None
        self._database_address: Optional[str] = None
        self._module_name: Optional[str] = None
        self._auth_token: Optional[str] = None
        self._ssl_enabled: bool = True
        
        # Protocol configuration
        self._protocol: str = TEXT_PROTOCOL
        self._autogen_package: Optional[str] = None
        
        # Connection behavior
        self._auto_reconnect: bool = True
        self._max_reconnect_attempts: int = 10
        
        # Energy management
        self._initial_energy: int = 100000
        self._max_energy: int = 1000000
        self._energy_budget: Optional[int] = None
        
        # Compression configuration
        self._compression_config: CompressionConfig = CompressionConfig()
        
        # Scheduling configuration
        self._auto_start_scheduler: bool = True
        self._max_concurrent_executions: int = 10
        
        # Callbacks
        self._on_connect_callbacks: List[Callable[[], None]] = []
        self._on_disconnect_callbacks: List[Callable[[str], None]] = []
        self._on_error_callbacks: List[Callable[[Exception], None]] = []
        self._on_identity_callbacks: List[Callable[[Identity], None]] = []
        
        # Context configuration
        self._build_context: bool = False
        self._db_view_class: type = DbView
        self._reducers_class: type = Reducers
        self._set_reducer_flags_class: type = SetReducerFlags
        
        # JSON API configuration
        self._json_api_base_url: Optional[str] = None
        
        # Connection pooling configuration
        self._use_connection_pool: bool = False
        self._pool_min_connections: int = 2
        self._pool_max_connections: int = 10
        self._pool_health_check_interval: float = 30.0
        self._pool_retry_policy: Optional[RetryPolicy] = None
        self._pool_load_balancing_strategy: str = "round_robin"
        
        # Test mode configuration
        self._test_mode: bool = False
    
    def with_uri(self, uri: str) -> 'SpacetimeDBConnectionBuilder':
        """
        Set the connection URI.
        
        Args:
            uri: WebSocket URI (e.g., "ws://localhost:3000" or "wss://testnet.spacetimedb.com")
        
        Returns:
            Self for method chaining
        
        Example:
            builder.with_uri("ws://localhost:3000")
        """
        if not uri:
            raise ValueError("URI cannot be empty")
        
        # Parse and validate URI
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme not in ('ws', 'wss'):
            raise ValueError(f"Invalid URI scheme: {parsed.scheme}. Must be 'ws' or 'wss'")
        
        self._uri = uri
        self._host = f"{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'wss' else 80)}"
        self._ssl_enabled = (parsed.scheme == 'wss')
        
        return self
    
    def with_module_name(self, module_name: str) -> 'SpacetimeDBConnectionBuilder':
        """
        Set the module/database name.
        
        Args:
            module_name: Name of the SpacetimeDB module/database
        
        Returns:
            Self for method chaining
        
        Example:
            builder.with_module_name("my_game_db")
        """
        if not module_name:
            raise ValueError("Module name cannot be empty")
        
        self._module_name = module_name
        self._database_address = module_name
        return self
    
    def with_token(self, token: str) -> 'SpacetimeDBConnectionBuilder':
        """
        Set the authentication token.
        
        Args:
            token: Authentication token for the connection
        
        Returns:
            Self for method chaining
        
        Example:
            builder.with_token("my_auth_token")
        """
        self._auth_token = token
        return self
    
    def with_protocol(self, protocol: str) -> 'SpacetimeDBConnectionBuilder':
        """
        Set the communication protocol.
        
        Args:
            protocol: Either "text" or "binary" protocol
        
        Returns:
            Self for method chaining
        
        Example:
            builder.with_protocol("binary")
        """
        if protocol not in ("text", "binary"):
            raise ValueError(f"Invalid protocol: {protocol}. Must be 'text' or 'binary'")
        
        self._protocol = protocol
        return self
    
    def with_autogen_package(self, package: ModuleType) -> 'SpacetimeDBConnectionBuilder':
        """
        Set the auto-generated package for table and reducer definitions.
        
        Args:
            package: The auto-generated Python module containing table/reducer definitions
        
        Returns:
            Self for method chaining
        
        Example:
            import my_generated_module
            builder.with_autogen_package(my_generated_module)
        """
        self._autogen_package = package
        return self
    
    def with_ssl(self, enabled: bool) -> 'SpacetimeDBConnectionBuilder':
        """
        Enable or disable SSL/TLS encryption.
        
        Args:
            enabled: Whether to use SSL/TLS encryption
        
        Returns:
            Self for method chaining
        
        Note:
            This is typically inferred from the URI scheme (ws vs wss)
        """
        self._ssl_enabled = enabled
        return self
    
    def with_auto_reconnect(self, enabled: bool, max_attempts: int = 10) -> 'SpacetimeDBConnectionBuilder':
        """
        Configure auto-reconnection behavior.
        
        Args:
            enabled: Whether to enable auto-reconnection
            max_attempts: Maximum number of reconnection attempts
            
        Returns:
            Self for method chaining
        """
        self._auto_reconnect = enabled
        self._max_reconnect_attempts = max_attempts
        return self
    
    def with_json_api_base_url(self, base_url: str) -> 'SpacetimeDBConnectionBuilder':
        """
        Set the base URL for JSON API operations.
        
        Args:
            base_url: Base URL for HTTP API (e.g., "https://api.spacetimedb.com")
            
        Returns:
            Self for method chaining
            
        Example:
            client = (ModernSpacetimeDBClient.builder()
                      .with_uri("ws://localhost:3000")
                      .with_module_name("my_module")
                      .with_json_api_base_url("http://localhost:3000")
                      .build())
        """
        self._json_api_base_url = base_url
        return self
    
    def with_energy_budget(self, budget: int, initial: int = 1000, max_energy: int = 1000) -> 'SpacetimeDBConnectionBuilder':
        """
        Configure energy management settings.
        
        Args:
            budget: Energy budget per hour
            initial: Initial energy amount
            max_energy: Maximum energy capacity
        
        Returns:
            Self for method chaining
        
        Example:
            builder.with_energy_budget(10000, 2000, 2000)
        """
        if budget < 0 or initial < 0 or max_energy < 0:
            raise ValueError("Energy values must be non-negative")
        
        self._energy_budget = budget
        self._initial_energy = initial
        self._max_energy = max_energy
        return self
    
    def with_compression(
        self,
        enabled: bool = True,
        level: CompressionLevel = CompressionLevel.BALANCED,
        threshold: int = 1024,
        prefer_brotli: bool = True
    ) -> 'SpacetimeDBConnectionBuilder':
        """
        Configure message compression.
        
        Args:
            enabled: Whether to enable compression
            level: Compression level (FASTEST, BALANCED, BEST)
            threshold: Minimum message size to compress (bytes)
            prefer_brotli: Prefer Brotli over Gzip when available
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_compression(
                enabled=True,
                level=CompressionLevel.BEST,
                threshold=2048
            )
        """
        self._compression_config = CompressionConfig(
            enabled=enabled,
            compression_level=level,
            minimum_size_threshold=threshold,
            prefer_brotli=prefer_brotli
        )
        return self
    
    def with_compression_level(self, level: CompressionLevel) -> 'SpacetimeDBConnectionBuilder':
        """
        Set compression level.
        
        Args:
            level: Compression level to use
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_compression_level(CompressionLevel.BEST)
        """
        self._compression_config.compression_level = level
        return self
    
    def with_compression_threshold(self, threshold: int) -> 'SpacetimeDBConnectionBuilder':
        """
        Set minimum message size threshold for compression.
        
        Args:
            threshold: Minimum message size in bytes to trigger compression
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_compression_threshold(2048)
        """
        if threshold < 0:
            raise ValueError("Compression threshold must be non-negative")
        
        self._compression_config.minimum_size_threshold = threshold
        return self
    
    def enable_compression(self, enabled: bool = True) -> 'SpacetimeDBConnectionBuilder':
        """
        Enable or disable compression.
        
        Args:
            enabled: Whether to enable compression
            
        Returns:
            Self for method chaining
            
        Example:
            builder.enable_compression(True)
        """
        self._compression_config.enabled = enabled
        return self
    
    def on_connect(self, callback: Callable[[], None]) -> 'SpacetimeDBConnectionBuilder':
        """
        Register a callback for connection events.
        
        Args:
            callback: Function to call when connected
        
        Returns:
            Self for method chaining
        
        Example:
            builder.on_connect(lambda: print("Connected to SpacetimeDB!"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_connect_callbacks.append(callback)
        return self
    
    def on_disconnect(self, callback: Callable[[str], None]) -> 'SpacetimeDBConnectionBuilder':
        """
        Register a callback for disconnection events.
        
        Args:
            callback: Function to call when disconnected (receives reason as string)
        
        Returns:
            Self for method chaining
        
        Example:
            builder.on_disconnect(lambda reason: print(f"Disconnected: {reason}"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_disconnect_callbacks.append(callback)
        return self
    
    def on_identity(self, callback: Callable[[str, Any, Any], None]) -> 'SpacetimeDBConnectionBuilder':
        """
        Register a callback for identity events.
        
        Args:
            callback: Function to call when identity is received (token, identity, connection_id)
        
        Returns:
            Self for method chaining
        
        Example:
            builder.on_identity(lambda token, identity, conn_id: print(f"Identity: {identity}"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_identity_callbacks.append(callback)
        return self
    
    def on_error(self, callback: Callable[[Exception], None]) -> 'SpacetimeDBConnectionBuilder':
        """
        Register a callback for error events.
        
        Args:
            callback: Function to call when an error occurs
        
        Returns:
            Self for method chaining
        
        Example:
            builder.on_error(lambda error: print(f"Error: {error}"))
        """
        if not callable(callback):
            raise ValueError("Callback must be callable")
        
        self._on_error_callbacks.append(callback)
        return self
    
    def with_message_processing(self, enabled: bool) -> 'SpacetimeDBConnectionBuilder':
        """
        Enable or disable automatic message processing.
        
        Args:
            enabled: Whether to start message processing automatically
        
        Returns:
            Self for method chaining
        
        Note:
            Typically used for testing scenarios where manual message processing is needed
        """
        self._start_message_processing = enabled
        return self
    
    def with_test_mode(self, enabled: bool = True) -> 'SpacetimeDBConnectionBuilder':
        """
        Enable test mode to prevent real WebSocket connections.
        
        Args:
            enabled: Whether to enable test mode
        
        Returns:
            Self for method chaining
        
        Example:
            client = (ModernSpacetimeDBClient.builder()
                      .with_uri("ws://localhost:3000")
                      .with_module_name("test_module")
                      .with_test_mode()
                      .build())
        """
        self._test_mode = enabled
        return self
    
    def with_context(
        self,
        build_context: bool = True,
        db_view_class: type = DbView,
        reducers_class: type = Reducers,
        set_reducer_flags_class: type = SetReducerFlags
    ) -> 'SpacetimeDBConnectionBuilder':
        """
        Configure DbContext to be built alongside the client.
        
        Args:
            build_context: Whether to build a DbContext instance
            db_view_class: Custom DbView class for typed table access
            reducers_class: Custom Reducers class for typed reducer access
            set_reducer_flags_class: Custom SetReducerFlags class
            
        Returns:
            Self for method chaining
            
        Example:
            ```python
            # Get both client and context
            client, ctx = (ModernSpacetimeDBClient.builder()
                          .with_uri("ws://localhost:3000")
                          .with_module_name("my_module")
                          .with_context()
                          .build_with_context())
            
            # With custom types
            client, ctx = (ModernSpacetimeDBClient.builder()
                          .with_uri("ws://localhost:3000")
                          .with_module_name("my_module")
                          .with_context(
                              db_view_class=MyDbView,
                              reducers_class=MyReducers
                          )
                          .build_with_context())
            ```
        """
        self._build_context = build_context
        self._db_view_class = db_view_class
        self._reducers_class = reducers_class
        self._set_reducer_flags_class = set_reducer_flags_class
        return self
    
    def with_scheduling(
        self,
        auto_start: bool = True,
        max_concurrent_executions: int = 10
    ) -> 'SpacetimeDBConnectionBuilder':
        """
        Configure reducer scheduling.
        
        Args:
            auto_start: Whether to automatically start the scheduler when connecting
            max_concurrent_executions: Maximum number of concurrent scheduled executions
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_scheduling(auto_start=True, max_concurrent_executions=5)
        """
        self._auto_start_scheduler = auto_start
        self._max_concurrent_executions = max_concurrent_executions
        return self
    
    def with_connection_pool(
        self,
        min_connections: int = 2,
        max_connections: int = 10,
        health_check_interval: float = 30.0,
        load_balancing_strategy: str = "round_robin"
    ) -> 'SpacetimeDBConnectionBuilder':
        """
        Enable connection pooling with specified configuration.
        
        Args:
            min_connections: Minimum number of connections in the pool
            max_connections: Maximum number of connections in the pool
            health_check_interval: Interval for health checks in seconds
            load_balancing_strategy: Strategy for load balancing ("round_robin", "least_latency", "random")
            
        Returns:
            Self for method chaining
            
        Example:
            pool = (ModernSpacetimeDBClient.builder()
                    .with_uri("ws://localhost:3000")
                    .with_module_name("my_module")
                    .with_connection_pool(
                        min_connections=5,
                        max_connections=20,
                        load_balancing_strategy="least_latency"
                    )
                    .build_pool())
        """
        self._use_connection_pool = True
        self._pool_min_connections = min_connections
        self._pool_max_connections = max_connections
        self._pool_health_check_interval = health_check_interval
        self._pool_load_balancing_strategy = load_balancing_strategy
        return self
    
    def with_retry_policy(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ) -> 'SpacetimeDBConnectionBuilder':
        """
        Configure retry policy for connection pool operations.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to retry delays
            
        Returns:
            Self for method chaining
            
        Example:
            builder.with_retry_policy(
                max_retries=5,
                base_delay=0.5,
                max_delay=30.0
            )
        """
        self._pool_retry_policy = RetryPolicy(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter
        )
        return self
    
    def build(self) -> 'ModernSpacetimeDBClient':
        """
        Build and return the configured SpacetimeDB client.
        
        Returns:
            Configured ModernSpacetimeDBClient instance
        
        Raises:
            ValueError: If required parameters are missing or invalid
        
        Example:
            client = builder.build()
        """
        # Validate required parameters
        if not self._uri:
            raise ValueError("URI is required. Use with_uri() to set it.")
        
        if not self._module_name:
            raise ValueError("Module name is required. Use with_module_name() to set it.")
        
        if not self._host:
            raise ValueError("Host could not be parsed from URI.")
        
        if not self._database_address:
            raise ValueError("Database address is required.")
        
        # Import here to avoid circular imports
        from .modern_client import ModernSpacetimeDBClient
        
        # Create the client
        client = ModernSpacetimeDBClient(
            autogen_package=self._autogen_package,
            protocol=self._protocol,
            auto_reconnect=self._auto_reconnect,
            max_reconnect_attempts=self._max_reconnect_attempts,
            initial_energy=self._initial_energy,
            max_energy=self._max_energy,
            energy_budget=self._energy_budget,
            compression_config=self._compression_config,
            test_mode=self._test_mode
        )
        
        # Register all callbacks
        for callback in self._on_connect_callbacks:
            client.register_on_connect(callback)
        
        for callback in self._on_disconnect_callbacks:
            client.register_on_disconnect(callback)
        
        for callback in self._on_error_callbacks:
            client.register_on_error(callback)
        
        for callback in self._on_identity_callbacks:
            client.register_on_identity(callback)
        
        # Configure scheduler if auto-start is enabled
        if self._auto_start_scheduler:
            # Initialize scheduler with configuration
            scheduler = client.scheduler
            scheduler._max_concurrent_executions = self._max_concurrent_executions
            
            # Add auto-start callback
            async def auto_start_scheduler():
                """Auto-start scheduler when connected."""
                try:
                    await scheduler.start()
                    client.logger.info("Scheduler auto-started successfully")
                except Exception as e:
                    client.logger.error(f"Failed to auto-start scheduler: {e}")
            
            def sync_auto_start_scheduler():
                """Sync wrapper for auto-start scheduler."""
                import asyncio
                try:
                    # Try to get current event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, schedule the coroutine
                        asyncio.create_task(auto_start_scheduler())
                    else:
                        # If no loop is running, run it
                        loop.run_until_complete(auto_start_scheduler())
                except RuntimeError:
                    # No event loop, create one
                    asyncio.run(auto_start_scheduler())
            
            client.register_on_connect(sync_auto_start_scheduler)
        
        # Set JSON API base URL if configured
        if self._json_api_base_url:
            client._json_api_base_url = self._json_api_base_url
        
        # Return the configured client
        return client
    
    def connect(self) -> 'ModernSpacetimeDBClient':
        """
        Build the client and immediately connect to SpacetimeDB.
        
        Returns:
            Connected ModernSpacetimeDBClient instance
        
        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If connection fails
        
        Example:
            client = builder.connect()
        """
        # Create client first
        client = self.build()
        
        # Set JSON API base URL if provided
        if self._json_api_base_url:
            client.set_json_api_base_url(self._json_api_base_url)
        
        # Connect to SpacetimeDB
        # Note: Callbacks are already registered on the client during build()
        client._connect_internal(
            auth_token=self._auth_token,
            host=self._host,
            database_address=self._database_address,
            ssl_enabled=self._ssl_enabled
        )
        
        return client
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate the current configuration without building.
        
        Returns:
            Dictionary containing validation results and current configuration
        
        Example:
            validation = builder.validate()
            if validation['valid']:
                client = builder.build()
        """
        issues = []
        
        if not self._uri:
            issues.append("URI is required")
        
        if not self._module_name:
            issues.append("Module name is required")
        
        if not self._host:
            issues.append("Host could not be parsed from URI")
        
        if self._energy_budget is not None and self._energy_budget < 0:
            issues.append("Energy budget must be non-negative")
        
        if self._initial_energy is not None and self._initial_energy < 0:
            issues.append("Initial energy must be non-negative")
        
        if self._max_energy is not None and self._max_energy < 0:
            issues.append("Max energy must be non-negative")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'configuration': {
                'uri': self._uri,
                'module_name': self._module_name,
                'protocol': self._protocol,
                'ssl_enabled': self._ssl_enabled,
                'auto_reconnect': self._auto_reconnect,
                'energy_budget': self._energy_budget,
                'callbacks_registered': {
                    'on_connect': len(self._on_connect_callbacks),
                    'on_disconnect': len(self._on_disconnect_callbacks),
                    'on_identity': len(self._on_identity_callbacks),
                    'on_error': len(self._on_error_callbacks)
                }
            }
        } 
    
    def build_with_context(self) -> tuple['ModernSpacetimeDBClient', DbContext]:
        """
        Build both the client and a DbContext instance.
        
        Returns:
            Tuple of (client, context)
            
        Raises:
            ValueError: If required parameters are missing or invalid
            
        Example:
            ```python
            client, ctx = builder.build_with_context()
            
            # Use context for structured access
            users = ctx.db.users
            await ctx.reducers.create_user({"name": "Alice"})
            ```
        """
        # Build the client
        client = self.build()
        
        # Build the context
        ctx = client.get_context(
            db_view_class=self._db_view_class,
            reducers_class=self._reducers_class,
            set_reducer_flags_class=self._set_reducer_flags_class
        )
        
        return client, ctx
    
    def build_pool(self) -> 'ConnectionPool':
        """
        Build a connection pool instead of a single client.
        
        Returns:
            Configured ConnectionPool instance
            
        Raises:
            ValueError: If required parameters are missing or invalid
            
        Example:
            ```python
            pool = (ModernSpacetimeDBClient.builder()
                    .with_uri("ws://localhost:3000")
                    .with_module_name("my_module")
                    .with_token("auth_token")
                    .with_connection_pool(min_connections=5, max_connections=20)
                    .with_retry_policy(max_retries=5)
                    .build_pool())
            
            # Use the pool
            def my_operation(client):
                return client.call_reducer("my_reducer", {"arg": "value"})
                
            result = pool.execute_with_retry(my_operation, "my_operation")
            
            # Get pool metrics
            metrics = pool.get_pool_metrics()
            print(f"Healthy connections: {metrics['healthy_connections']}")
            ```
        """
        if not self._use_connection_pool:
            raise ValueError("Connection pooling not enabled. Use with_connection_pool() first.")
        
        # Validate required parameters
        if not self._uri:
            raise ValueError("URI is required. Use with_uri() to set it.")
        
        if not self._module_name:
            raise ValueError("Module name is required. Use with_module_name() to set it.")
        
        # Build connection configuration
        connection_config = {
            'uri': self._uri,
            'host': self._host,
            'module_name': self._module_name,
            'database_address': self._database_address,
            'auth_token': self._auth_token,
            'ssl_enabled': self._ssl_enabled,
            'protocol': self._protocol,
            'auto_reconnect': self._auto_reconnect,
            'max_reconnect_attempts': self._max_reconnect_attempts,
            'initial_energy': self._initial_energy,
            'max_energy': self._max_energy,
            'energy_budget': self._energy_budget,
            'compression_config': self._compression_config,
            'autogen_package': self._autogen_package
        }
        
        # Lazy import to avoid circular dependency
        from .connection_pool import ConnectionPool
        
        # Create the connection pool
        pool = ConnectionPool(
            min_connections=self._pool_min_connections,
            max_connections=self._pool_max_connections,
            connection_config=connection_config,
            health_check_interval=self._pool_health_check_interval,
            retry_policy=self._pool_retry_policy,
            load_balancing_strategy=self._pool_load_balancing_strategy
        )
        
        return pool
    
    def connect_with_context(self) -> tuple['ModernSpacetimeDBClient', DbContext]:
        """
        Build the client and context, then immediately connect to SpacetimeDB.
        
        Returns:
            Tuple of (connected_client, context)
            
        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If connection fails
            
        Example:
            ```python
            client, ctx = builder.connect_with_context()
            
            # Already connected and ready to use
            if ctx.isActive:
                await ctx.reducers.send_message({"content": "Hello!"})
            ```
        """
        # Build client and context
        client, ctx = self.build_with_context()
        
        # Connect to SpacetimeDB
        # Note: Callbacks are already registered on the client during build()
        client._connect_internal(
            auth_token=self._auth_token,
            host=self._host,
            database_address=self._database_address,
            ssl_enabled=self._ssl_enabled
        )
        
        return client, ctx
