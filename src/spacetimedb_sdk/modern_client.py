"""
Modern SpacetimeDB client implementation supporting protocol v1.1.1

This is the modernized version of spacetimedb_client.py with support for:
- Modern WebSocket protocol (v1.1.1)
- QueryId-based subscription management
- Enhanced connection lifecycle management
- Connection state tracking and metrics
- Connection event system
- Energy quota tracking and management
- Proper error handling and reconnection
- Fluent builder API for connection setup
"""

from typing import List, Dict, Callable, Optional, Any, Union, Tuple
from types import ModuleType
import json
import queue
import threading
import logging
import time
from dataclasses import dataclass

from .websocket_client import ModernWebSocketClient, ConnectionState
from .exceptions import (
    SpacetimeDBError,
    DatabaseNotFoundError,
    ServerNotAvailableError,
    AuthenticationError,
    ConnectionTimeoutError,
    SpacetimeDBConnectionError
)
from .connection_diagnostics import ConnectionDiagnostics
from .protocol import (
    TEXT_PROTOCOL, BIN_PROTOCOL,
    ServerMessage, Identity, ConnectionId,
    IdentityToken, TransactionUpdate, TransactionUpdateLight,
    SubscribeApplied, UnsubscribeApplied, SubscriptionError,
    OneOffQueryResponse, CallReducerFlags,
    generate_request_id,
    ensure_enhanced_connection_id,
    ensure_enhanced_identity
)
from .connection_id import (
    EnhancedConnectionId,
    EnhancedIdentity,
    EnhancedIdentityToken,
    ConnectionState as EnhancedConnectionState,
    ConnectionEventType,
    ConnectionEvent,
    ConnectionStateTracker,
    ConnectionLifecycleManager,
    ConnectionMetrics,
    ConnectionEventListener
)
from .query_id import QueryId
from .client_cache import ClientCache
from .compression import (
    CompressionManager,
    CompressionConfig,
    CompressionType,
    CompressionLevel,
    CompressionMetrics
)

# Import energy management components
from .energy import (
    EnergyTracker,
    EnergyBudgetManager,
    EnergyEventManager,
    EnergyCostEstimator,
    EnergyUsageAnalytics,
    EnergyEventListener,
    EnergyEvent,
    EnergyEventType,
    OutOfEnergyError,
    EnergyError
)

from .subscription_builder import AdvancedSubscriptionBuilder
from .table_interface import DatabaseInterface, TableEventProcessor, create_event_context, ReducerEvent as TableReducerEvent
from .event_system import (
    EventEmitter, EventContext, EventType, Event, 
    ReducerEvent as AdvancedReducerEvent, TableEvent,
    create_event, create_reducer_event, create_table_event,
    global_event_bus
)
from .json_api import SpacetimeDBJsonAPI, ApiResponse, DatabaseInfo, ModuleInfo

# Import DbContext
from .db_context import (
    DbContext, DbView, Reducers, SetReducerFlags,
    create_db_context, DbContextBuilder
)

# Import RemoteModule
from .remote_module import (
    RemoteModule, SpacetimeModule, ModuleIntrospector,
    get_module_registry, register_module
)


@dataclass
class ReducerEvent:
    """Information about a reducer event."""
    caller_identity: Identity
    caller_connection_id: ConnectionId
    reducer_name: str
    status: str
    message: str
    args: Dict[str, Any]
    energy_used: int
    execution_duration_nanos: int


@dataclass
class DbEvent:
    """Represents a database event."""
    table_name: str
    row_pk: str
    row_op: str  # "insert", "update", "delete"
    decoded_value: Optional[Any] = None
    old_value: Optional[Any] = None


class ModernSpacetimeDBClient:
    """
    Modern SpacetimeDB client with support for protocol v1.1.1.
    
    Features:
    - Modern WebSocket protocol support
    - QueryId-based subscription management
    - Enhanced connection lifecycle management
    - Connection state tracking and metrics
    - Connection event system
    - Energy quota tracking
    - Automatic reconnection
    - Proper error handling
    - Fluent builder API for connection setup
    """
    
    @classmethod
    def connect(
        cls,
        host: str,
        database_address: str,
        auth_token: Optional[str] = None,
        ssl_enabled: bool = True,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_identity: Optional[Callable[[str, Identity, ConnectionId], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        db_identity: Optional[str] = None,
        protocol: str = TEXT_PROTOCOL,
        autogen_package: Optional[ModuleType] = None,
        **kwargs
    ) -> 'ModernSpacetimeDBClient':
        """
        Simple connection method for easy client initialization.
        
        Args:
            host: SpacetimeDB host (e.g., "localhost:3000")
            database_address: Database name or address
            auth_token: Optional authentication token
            ssl_enabled: Whether to use SSL/TLS
            on_connect: Callback when connected
            on_disconnect: Callback when disconnected
            on_identity: Callback when identity is received
            on_error: Callback for errors
            db_identity: Optional database identity (UUID/hash)
            protocol: Protocol to use (default: TEXT_PROTOCOL)
            autogen_package: Optional autogenerated package module
            **kwargs: Additional arguments passed to constructor
            
        Returns:
            Connected SpacetimeDBClient instance
            
        Example:
            client = SpacetimeDBClient.connect(
                host="localhost:3000",
                database_address="my_module",
                on_connect=lambda: print("Connected!")
            )
        """
        # Create client instance with protocol
        client = cls(autogen_package=autogen_package, protocol=protocol, **kwargs)
        
        # Connect (instance method doesn't take protocol)
        client._connect_internal(
            auth_token=auth_token,
            host=host,
            database_address=database_address,
            ssl_enabled=ssl_enabled,
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            on_identity=on_identity,
            on_error=on_error,
            db_identity=db_identity
        )
        
        return client
    
    @classmethod
    def builder(cls) -> 'SpacetimeDBConnectionBuilder':
        """
        Create a new connection builder for fluent API configuration.
        
        Returns:
            SpacetimeDBConnectionBuilder instance for method chaining
        
        Example:
            client = ModernSpacetimeDBClient.builder() \
                .with_uri("ws://localhost:3000") \
                .with_module_name("my_module") \
                .with_token("auth_token") \
                .on_connect(lambda: print("Connected!")) \
                .build()
        """
        from .connection_builder import SpacetimeDBConnectionBuilder
        return SpacetimeDBConnectionBuilder()
    
    @property
    def db(self) -> DatabaseInterface:
        """
        Get the database interface for table access.
        
        Example:
            client.db.messages.on_insert(lambda ctx, row: print(f"New message: {row}"))
            all_users = list(client.db.users.iter())
            user = client.db.users.find_by_unique_column('id', user_id)
        """
        return self._db_interface
    
    def get_context(
        self,
        db_view_class: type = DbView,
        reducers_class: type = Reducers,
        set_reducer_flags_class: type = SetReducerFlags,
        module: Optional[RemoteModule] = None
    ) -> DbContext:
        """
        Get a DbContext instance for structured access to tables and reducers.
        
        Args:
            db_view_class: Custom DbView class for typed table access
            reducers_class: Custom Reducers class for typed reducer access  
            set_reducer_flags_class: Custom SetReducerFlags class
            module: RemoteModule with runtime type information
            
        Returns:
            DbContext instance configured with this client
            
        Example:
            ```python
            # Basic usage
            ctx = client.get_context()
            
            # With module metadata
            from my_generated_module import MyGameModule
            ctx = client.get_context(module=MyGameModule())
            
            # Access tables with type info
            users = ctx.db.users
            print(f"Primary key: {users.primary_key}")
            print(f"Row type: {users.row_type}")
            
            # Call reducers with validation
            await ctx.reducers.create_user(name="Alice", email="alice@example.com")
            ```
        """
        # Try to get module from client if not provided
        if module is None and self.autogen_package:
            # Try to discover module from autogen package
            discovered = ModuleIntrospector.discover_module(self.autogen_package)
            if discovered:
                module = discovered
        
        return create_db_context(self, db_view_class, reducers_class, set_reducer_flags_class, module)
    
    def context_builder(self) -> DbContextBuilder:
        """
        Create a fluent builder for DbContext configuration.
        
        Returns:
            DbContextBuilder instance for method chaining
            
        Example:
            ```python
            ctx = client.context_builder()
                .with_db_view(MyCustomDbView)
                .with_reducers(MyCustomReducers)
                .build()
            ```
        """
        return DbContextBuilder().with_client(self)
    
    def register_table(self, table_name: str, row_type: type,
                      primary_key: Optional[str] = None,
                      unique_columns: Optional[List[str]] = None):
        """
        Register a table with the client for enhanced table interface.
        
        Args:
            table_name: Name of the table
            row_type: Type of rows in the table
            primary_key: Name of the primary key column (if any)
            unique_columns: List of unique column names
        """
        self._db_interface.register_table(table_name, row_type, primary_key, unique_columns)
    
    def __init__(
        self,
        autogen_package: Optional[ModuleType] = None,
        protocol: str = TEXT_PROTOCOL,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        start_message_processing: bool = True,  # Allow disabling for testing
        initial_energy: int = 1000,  # Initial energy quota
        max_energy: int = 1000,  # Maximum energy capacity
        energy_budget: int = 5000,  # Energy budget per hour
        compression_config: Optional[CompressionConfig] = None,
        test_mode: bool = False,  # New parameter to prevent real connections
        auto_trigger_lifecycle: bool = True  # Automatically trigger client_connected reducer
    ):
        # Client state
        self.autogen_package = autogen_package
        # Convert protocol shortcuts to full protocol strings
        if protocol == "text":
            self.protocol = TEXT_PROTOCOL
        elif protocol == "binary" or protocol == "bsatn":
            self.protocol = BIN_PROTOCOL
        else:
            self.protocol = protocol
        self.test_mode = test_mode
        self.auto_trigger_lifecycle = auto_trigger_lifecycle
        
        # Compression configuration
        self.compression_config = compression_config or CompressionConfig()
        
        # Connection management
        self.ws_client: Optional[ModernWebSocketClient] = None
        self.connection_info: Dict[str, Any] = {}
        
        # Enhanced connection management
        self.connection_state_tracker = ConnectionStateTracker()
        self.connection_lifecycle_manager = ConnectionLifecycleManager()
        self.connection_metrics = ConnectionMetrics()
        
        # Energy management components
        self.energy_tracker = EnergyTracker(initial_energy, max_energy)
        self.energy_budget_manager = EnergyBudgetManager(energy_budget)
        self.energy_event_manager = EnergyEventManager()
        self.energy_cost_estimator = EnergyCostEstimator()
        self.energy_usage_analytics = EnergyUsageAnalytics()
        
        # Energy event listeners
        self._energy_event_listeners: List[EnergyEventListener] = []
        
        # Identity and connection tracking (both legacy and enhanced)
        self.identity: Optional[Identity] = None
        self.connection_id: Optional[ConnectionId] = None
        self.enhanced_identity: Optional[EnhancedIdentity] = None
        self.enhanced_connection_id: Optional[EnhancedConnectionId] = None
        self.auth_token: Optional[str] = None
        self.enhanced_identity_token: Optional[EnhancedIdentityToken] = None
        
        # Subscription management
        self.active_subscriptions: Dict[QueryId, List[str]] = {}  # QueryId -> queries
        self.subscription_callbacks: Dict[QueryId, List[Callable]] = {}
        
        # Event callbacks
        self._row_update_callbacks: Dict[str, List[Callable]] = {}
        self._reducer_callbacks: Dict[str, List[Callable]] = {}
        self._on_subscription_applied: List[Callable[[], None]] = []
        self._on_event: List[Callable[[ReducerEvent], None]] = []
        self._on_connect: List[Callable[[], None]] = []
        self._on_disconnect: List[Callable[[str], None]] = []
        self._on_identity: List[Callable[[str, Identity, ConnectionId], None]] = []
        self._on_error: List[Callable[[Exception], None]] = []
        
        # Enhanced connection event callbacks
        self._connection_event_listeners: List[ConnectionEventListener] = []
        
        # Message processing
        self.message_queue = queue.Queue()
        self.processing_thread: Optional[threading.Thread] = None
        self.should_stop_processing = threading.Event()
        
        # Client cache
        self.client_cache: Optional[ClientCache] = None
        if autogen_package:
            self.client_cache = ClientCache(autogen_package)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Connection diagnostics
        self._diagnostics = ConnectionDiagnostics()
        
        # Database interface for table access
        self._db_interface = DatabaseInterface(self)
        self._table_event_processor = TableEventProcessor(self._db_interface)
        
        # Module information
        self._module: Optional[RemoteModule] = None
        
        # Advanced event system
        self._event_emitter = EventEmitter(name=f"client_{id(self)}")
        self._setup_advanced_events()
        
        # JSON API client (initialized on demand)
        self._json_api: Optional[SpacetimeDBJsonAPI] = None
        self._json_api_base_url: Optional[str] = None
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.ModernSpacetimeDBClient_{id(self)}")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            self.logger.propagate = False

        self.logger.debug("ModernSpacetimeDBClient initializing...")
        
        # Setup enhanced connection event handling
        self._setup_enhanced_connection_events()
        
        # Setup energy event handling
        self._setup_energy_events()
        
        # Start message processing (can be disabled for testing)
        if start_message_processing:
            self._start_message_processing()
        self.logger.debug("ModernSpacetimeDBClient initialized.")
    
    def __del__(self):
        """Cleanup when the client is destroyed."""
        try:
            self.shutdown()
        except:
            pass
    
    def shutdown(self) -> None:
        """Properly shutdown the client and cleanup threads."""
        self.logger.debug(f"Shutdown called. Current thread: {threading.get_ident()}")
        with self._lock:
            self.logger.debug(f"Shutdown: Acquired _lock. should_stop_processing: {self.should_stop_processing.is_set()}")
            if self.should_stop_processing.is_set() and not (self.processing_thread and self.processing_thread.is_alive()):
                 self.logger.debug("Shutdown: Already stopped or stopping, exiting early.")
                 # return # Avoid returning if ws_client still needs cleanup

            self.should_stop_processing.set()
            self.logger.debug("Shutdown: Set should_stop_processing.")

            if self.enhanced_connection_id:
                try:
                    # Handle enhanced connection lifecycle (gracefully handle test mocks)
                    connection_id_str = "test_connection" if hasattr(self.enhanced_connection_id, '_mock_name') else self.enhanced_connection_id.to_hex()[:8]
                    self.logger.debug(f"Shutdown: Handling enhanced connection lifecycle for {connection_id_str}")
                    
                    self.connection_lifecycle_manager.on_connection_lost(
                        self.enhanced_connection_id, "Client disconnect"
                    )
                    self.connection_metrics.record_disconnection(self.enhanced_connection_id)
                except Exception as e:
                    self.logger.error(f"Shutdown: Error during connection lifecycle cleanup: {e}")
            
            if self.ws_client:
                self.logger.debug("Shutdown: Disconnecting ws_client.")
                try:
                    self.ws_client.disconnect()
                    self.logger.debug("Shutdown: ws_client.disconnect() called.")
                except Exception as e:
                    self.logger.error(f"Shutdown: Error disconnecting ws_client: {e}")
                self.ws_client = None
            
            if self.processing_thread and self.processing_thread.is_alive():
                self.logger.debug(f"Shutdown: Stopping processing_thread (ID: {self.processing_thread.ident}). Current state: {self.processing_thread.is_alive()}")
                try:
                    self.logger.debug(f"Shutdown: Putting None on message_queue (empty: {self.message_queue.empty()}).")
                    self.message_queue.put(None, timeout=0.1)
                except queue.Full:
                    self.logger.warning("Shutdown: Message queue full, processing_thread might be blocked on put.")
                except Exception as e:
                     self.logger.error(f"Shutdown: Error putting None on queue: {e}")
                
                self.logger.debug(f"Shutdown: Joining processing_thread (ID: {self.processing_thread.ident}).")
                self.processing_thread.join(timeout=3.0)
                if self.processing_thread.is_alive():
                    self.logger.warning(f"Shutdown: processing_thread (ID: {self.processing_thread.ident}) did NOT stop cleanly.")
                else:
                    self.logger.debug(f"Shutdown: processing_thread (ID: {self.processing_thread.ident}) stopped.")
            else:
                self.logger.debug("Shutdown: processing_thread is None or not alive.")
            
            self.logger.debug("Shutdown: Clearing client state.")
            # Clear all state
            self.identity = None
            self.connection_id = None
            self.enhanced_identity = None
            self.enhanced_connection_id = None
            self.enhanced_identity_token = None
            self.active_subscriptions.clear()
            self.subscription_callbacks.clear()
            self._connection_event_listeners.clear()
            
            # Clear message queue
            try:
                while not self.message_queue.empty():
                    self.message_queue.get_nowait()
                    self.message_queue.task_done()
            except:
                pass
            
            # Clean up JSON API client
            if self._json_api:
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._json_api.close())
                    loop.close()
                except:
                    pass
                self._json_api = None
            
            self.logger.debug("Shutdown: Process complete.")
    
    def _setup_enhanced_connection_events(self) -> None:
        """Setup enhanced connection event handling."""
        # Register internal event handlers
        self.connection_lifecycle_manager.register_listener(
            'connected', self._handle_enhanced_connect_event
        )
        self.connection_lifecycle_manager.register_listener(
            'disconnected', self._handle_enhanced_disconnect_event
        )
        self.connection_lifecycle_manager.register_listener(
            'identity_changed', self._handle_enhanced_identity_event
        )
    
    def _connect_internal(
        self,
        auth_token: Optional[str],
        host: str,
        database_address: str,
        ssl_enabled: bool = True,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_identity: Optional[Callable[[str, Identity, ConnectionId], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_event: Optional[Callable[[ReducerEvent], None]] = None,
        db_identity: Optional[str] = None
    ) -> None:
        """Internal method to connect to SpacetimeDB."""
        with self._lock:
            if self.ws_client and self.ws_client.is_connected:
                self.logger.warning("Already connected")
                return
            
            # Store callbacks
            if on_connect:
                self._on_connect.append(on_connect)
            if on_disconnect:
                self._on_disconnect.append(on_disconnect)
            if on_identity:
                self._on_identity.append(on_identity)
            if on_error:
                self._on_error.append(on_error)
            if on_event:
                self._on_event.append(on_event)
            
            # In test mode, skip actual connection
            if self.test_mode:
                self.logger.info("Test mode: Simulating connection without WebSocket")
                # Simulate successful connection
                self._simulate_test_connection()
                return
            
            # Create WebSocket client
            self.ws_client = ModernWebSocketClient(
                protocol=self.protocol,
                on_connect=self._handle_connect,
                on_disconnect=self._handle_disconnect,
                on_error=self._handle_error,
                on_message=self._handle_message,
                auto_reconnect=True,
                compression_config=self.compression_config
            )
            
            # Connect
            self.auth_token = auth_token
            self.ws_client.connect(auth_token, host, database_address, ssl_enabled, db_identity)
    
    def disconnect(self) -> None:
        """Disconnect from SpacetimeDB."""
        self.logger.debug(f"Disconnect called. Current thread: {threading.get_ident()}")
        with self._lock:
            self.logger.debug(f"Disconnect: Acquired _lock. Current state: {self.ws_client.state.value if self.ws_client else 'No ws_client'}")
            self.logger.info("Disconnect requested.")
            self.should_stop_processing.set()
            self.logger.debug("Disconnect: Set should_stop_processing.")

            if self.enhanced_connection_id:
                try:
                    # Handle enhanced connection lifecycle (gracefully handle test mocks)
                    connection_id_str = "test_connection" if hasattr(self.enhanced_connection_id, '_mock_name') else self.enhanced_connection_id.to_hex()[:8]
                    self.logger.debug(f"Disconnect: Handling enhanced connection lifecycle for {connection_id_str}")
                    
                    self.connection_lifecycle_manager.on_connection_lost(
                        self.enhanced_connection_id, "Client disconnect initiated"
                    )
                    self.connection_metrics.record_disconnection(self.enhanced_connection_id)
                except Exception as e:
                    self.logger.error(f"Disconnect: Error during pre-disconnect lifecycle management: {e}")
            
            if self.ws_client:
                self.logger.debug("Disconnect: Preparing to call ws_client.disconnect().")
                try:
                    self.ws_client.disconnect()
                    self.logger.debug("Disconnect: ws_client.disconnect() returned.")
                except Exception as e:
                    self.logger.error(f"Disconnect: Exception from ws_client.disconnect(): {e}", exc_info=True)
                finally:
                    self.logger.debug("Disconnect: Setting self.ws_client to None in finally block.")
                    self.ws_client = None
            else:
                self.logger.debug("Disconnect: self.ws_client is None, skipping ws_client.disconnect().")
            
            if self.processing_thread and self.processing_thread.is_alive():
                self.logger.debug(f"Disconnect: Stopping processing_thread (ID: {self.processing_thread.ident}). Current state: {self.processing_thread.is_alive()}")
                try:
                    self.logger.debug(f"Disconnect: Putting None on message_queue (empty: {self.message_queue.empty()}).")
                    self.message_queue.put(None, timeout=0.1)
                except queue.Full:
                    self.logger.warning("Disconnect: Message queue full during disconnect, thread might be stuck.")
                except Exception as e:
                    self.logger.error(f"Disconnect: Error putting None on message queue: {e}")
                
                self.logger.debug(f"Disconnect: Joining processing_thread (ID: {self.processing_thread.ident}).")
                self.processing_thread.join(timeout=2.0)
                if self.processing_thread.is_alive():
                    self.logger.warning(f"Disconnect: processing_thread (ID: {self.processing_thread.ident}) did not stop cleanly during disconnect.")
                else:
                    self.logger.debug(f"Disconnect: processing_thread (ID: {self.processing_thread.ident}) stopped.")
            else:
                self.logger.debug("Disconnect: processing_thread is None or not alive.")
            
            self.logger.debug("Disconnect: Clearing client state.")
            self.identity = None
            self.connection_id = None
            self.enhanced_identity = None
            self.enhanced_connection_id = None
            self.enhanced_identity_token = None
            self.active_subscriptions.clear()
            self.subscription_callbacks.clear()
            self.logger.info("Client disconnect process complete.")
    
    # Enhanced connection management methods
    def get_connection_id(self) -> Optional[EnhancedConnectionId]:
        """Get the current enhanced connection ID."""
        return self.enhanced_connection_id
    
    def get_connection_state(self) -> EnhancedConnectionState:
        """Get the current connection state."""
        if self.enhanced_connection_id:
            return self.connection_state_tracker.get_connection_state(self.enhanced_connection_id)
        return EnhancedConnectionState.DISCONNECTED
    
    def add_connection_listener(self, listener: ConnectionEventListener) -> None:
        """Add a connection event listener."""
        self._connection_event_listeners.append(listener)
    
    def get_connection_metrics(self) -> Dict[str, Any]:
        """Get connection metrics."""
        return self.connection_metrics.get_connection_stats()
    
    def get_identity_info(self) -> Optional[Dict[str, Any]]:
        """Get enhanced identity information."""
        if self.enhanced_identity_token:
            return self.enhanced_identity_token.extract_claims()
        elif self.enhanced_identity:
            return {
                'identity': self.enhanced_identity.to_hex(),
                'address': self.enhanced_identity.to_address(),
                'is_anonymous': self.enhanced_identity.is_anonymous(),
                'version': self.enhanced_identity.get_version()
            }
        return None
    
    def _handle_enhanced_connect_event(self, event: ConnectionEvent) -> None:
        """Handle enhanced connection event."""
        for listener in self._connection_event_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error in connection event listener: {e}")
    
    def _handle_enhanced_disconnect_event(self, event: ConnectionEvent) -> None:
        """Handle enhanced disconnection event."""
        for listener in self._connection_event_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error in connection event listener: {e}")
    
    def _handle_enhanced_identity_event(self, event: ConnectionEvent) -> None:
        """Handle enhanced identity change event."""
        for listener in self._connection_event_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error in connection event listener: {e}")
    
    def call_reducer(
        self,
        reducer_name: str,
        *args,
        flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE
    ) -> int:
        """Call a reducer with the given arguments."""
        if not self.is_connected:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        if self.test_mode:
            # In test mode, return a mock request ID
            return generate_request_id()
        
        # Encode arguments as JSON for now (BSATN in Task 4)
        args_json = json.dumps(args).encode('utf-8')
        
        return self.ws_client.call_reducer(reducer_name, args_json, flags)
    
    async def call_reducer_async(
        self,
        reducer_name: str,
        *args,
        flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE,
        timeout: float = 30.0
    ) -> Any:
        """
        Call a reducer asynchronously and wait for the result.
        
        Args:
            reducer_name: Name of the reducer to call
            args: Arguments for the reducer
            flags: Reducer call flags
            timeout: Timeout in seconds
            
        Returns:
            The reducer result
            
        Raises:
            RuntimeError: If not connected
            asyncio.TimeoutError: If the call times out
            Exception: If the reducer call fails
        """
        if not self.ws_client or not self.ws_client.is_connected:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        import asyncio
        import uuid
        
        # Generate a unique request ID for tracking
        request_id = self.call_reducer(reducer_name, *args, flags=flags)
        
        # Create a future to wait for the result
        result_future = asyncio.Future()
        
        def handle_reducer_result(event):
            """Handle reducer result event."""
            if hasattr(event, 'request_id') and event.request_id == request_id:
                if hasattr(event, 'status') and event.status == "success":
                    if not result_future.done():
                        result_future.set_result(getattr(event, 'result', None))
                else:
                    error_msg = getattr(event, 'message', 'Reducer call failed')
                    if not result_future.done():
                        result_future.set_exception(Exception(error_msg))
            elif hasattr(event, 'reducer') and event.reducer == reducer_name:
                # Fallback for events without request_id
                if hasattr(event, 'status') and event.status == "success":
                    if not result_future.done():
                        result_future.set_result(getattr(event, 'result', None))
                else:
                    error_msg = getattr(event, 'message', 'Reducer call failed')
                    if not result_future.done():
                        result_future.set_exception(Exception(error_msg))
        
        # Register temporary event handler
        self.register_on_event(handle_reducer_result)
        
        try:
            # Wait for the result with timeout
            result = await asyncio.wait_for(result_future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Reducer call '{reducer_name}' timed out after {timeout} seconds")
        finally:
            # Clean up the event handler
            if handle_reducer_result in self._on_event:
                self._on_event.remove(handle_reducer_result)
    
    def subscribe(self, queries: List[str]) -> int:
        """Subscribe to queries (legacy method)."""
        if not self.is_connected:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        if self.test_mode:
            # In test mode, return a mock request ID
            return generate_request_id()
        
        return self.ws_client.subscribe_to_queries(queries)
    
    def subscribe_single(self, query: str) -> QueryId:
        """Subscribe to a single query with QueryId tracking."""
        if not self.is_connected:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        if self.test_mode:
            # In test mode, create and track a mock QueryId
            query_id = QueryId(generate_request_id())
            with self._lock:
                self.active_subscriptions[query_id] = [query]
                self.subscription_callbacks[query_id] = []
            return query_id
        
        query_id = self.ws_client.subscribe_single(query)
        
        with self._lock:
            self.active_subscriptions[query_id] = [query]
            self.subscription_callbacks[query_id] = []
        
        return query_id
    
    def subscribe_multi(self, queries: List[str]) -> QueryId:
        """Subscribe to multiple queries with QueryId tracking."""
        if not self.is_connected:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        if self.test_mode:
            # In test mode, create and track a mock QueryId
            query_id = QueryId(generate_request_id())
            with self._lock:
                self.active_subscriptions[query_id] = queries
                self.subscription_callbacks[query_id] = []
            return query_id
        
        query_id = self.ws_client.subscribe_multi(queries)
        
        with self._lock:
            self.active_subscriptions[query_id] = queries
            self.subscription_callbacks[query_id] = []
        
        return query_id
    
    def unsubscribe(self, query_id: QueryId) -> int:
        """Unsubscribe from a query."""
        if not self.is_connected:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        with self._lock:
            if query_id in self.active_subscriptions:
                del self.active_subscriptions[query_id]
            if query_id in self.subscription_callbacks:
                del self.subscription_callbacks[query_id]
        
        if self.test_mode:
            # In test mode, return a mock request ID
            return generate_request_id()
        
        return self.ws_client.unsubscribe(query_id)
    
    def one_off_query(self, query: str) -> bytes:
        """Execute a one-off query."""
        if not self.is_connected:
            raise RuntimeError("Not connected to SpacetimeDB")
        
        if self.test_mode:
            # In test mode, return mock result
            return b"test_query_result"
        
        return self.ws_client.one_off_query(query)
    
    def subscription_builder(self) -> 'AdvancedSubscriptionBuilder':
        """
        Create a new subscription builder for fluent API configuration.
        
        Returns:
            AdvancedSubscriptionBuilder instance for method chaining
        
        Example:
            subscription = client.subscription_builder() \
                .on_applied(lambda: print("Subscription applied!")) \
                .on_error(lambda error: print(f"Error: {error.message}")) \
                .on_subscription_applied(lambda: print("All subscriptions ready")) \
                .with_retry_policy(max_retries=3, backoff_seconds=1.0) \
                .with_timeout(30.0) \
                .subscribe(["SELECT * FROM messages", "SELECT * FROM users"])
        """
        return AdvancedSubscriptionBuilder(self)
    
    @property
    def event_emitter(self) -> EventEmitter:
        """
        Get the advanced event emitter for custom event handling.
        
        Example:
            # Register for all table events
            client.event_emitter.on("*", lambda ctx: print(f"Event: {ctx.event_type}"))
            
            # Register for specific events with priority
            client.event_emitter.on(
                EventType.TABLE_ROW_UPDATE,
                lambda ctx: handle_update(ctx),
                priority=10
            )
            
            # Use async handlers
            async def async_handler(ctx):
                await process_event(ctx.event)
            
            client.event_emitter.on(EventType.REDUCER_SUCCESS, async_handler)
        """
        return self._event_emitter
    
    @property
    def json_api(self) -> SpacetimeDBJsonAPI:
        """
        Get the JSON API client for HTTP operations.
        
        Example:
            # List databases
            response = await client.json_api.list_databases()
            if response.success:
                for db in response.data:
                    print(f"Database: {db.name}")
            
            # Call reducer via HTTP
            response = await client.json_api.call_reducer_http(
                "my_database",
                "create_user",
                ["Alice", "alice@example.com"]
            )
            
            # Execute SQL query
            response = await client.json_api.execute_sql(
                "my_database",
                "SELECT * FROM users WHERE active = true"
            )
        """
        if self._json_api is None:
            # Derive JSON API URL from WebSocket connection info
            if self._json_api_base_url:
                base_url = self._json_api_base_url
            elif self.ws_client and hasattr(self.ws_client, '_host'):
                # Convert WebSocket URL to HTTP URL
                host = self.ws_client._host
                ssl = hasattr(self.ws_client, '_ssl') and self.ws_client._ssl
                protocol = 'https' if ssl else 'http'
                base_url = f"{protocol}://{host}"
            else:
                # Default to localhost
                base_url = "http://localhost:3000"
            
            self._json_api = SpacetimeDBJsonAPI(
                base_url=base_url,
                auth_token=self.auth_token,
                timeout=30.0,
                max_retries=3
            )
        
        return self._json_api
    
    def emit_event(self, event: Event, **context_kwargs) -> EventContext:
        """
        Emit a custom event through the event system.
        
        Args:
            event: Event to emit
            **context_kwargs: Additional context parameters
            
        Returns:
            EventContext with handling results
        """
        return self._event_emitter.emit(event, **context_kwargs)
    
    def on_event(
        self,
        event_type: Union[EventType, str],
        handler: Callable[[EventContext], None],
        priority: int = 0,
        handler_name: Optional[str] = None
    ) -> str:
        """
        Register an event handler using the advanced event system.
        
        Args:
            event_type: Type of event to handle
            handler: Handler function taking EventContext
            priority: Handler priority (higher = earlier)
            handler_name: Optional name for the handler
            
        Returns:
            Handler ID for removal
            
        Example:
            def handle_insert(ctx: EventContext):
                table_event = ctx.event
                print(f"New row in {table_event.table_name}: {table_event.row_data}")
                
            handler_id = client.on_event(EventType.TABLE_ROW_INSERT, handle_insert)
        """
        return self._event_emitter.on(event_type, handler, priority, handler_name)
    
    def off_event(self, event_type: Union[EventType, str], handler_id: str) -> bool:
        """
        Remove an event handler.
        
        Args:
            event_type: Event type the handler was registered for
            handler_id: Handler ID returned by on_event()
            
        Returns:
            True if handler was removed
        """
        return self._event_emitter.off(event_type, handler_id)
    
    def get_event_history(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        limit: Optional[int] = None
    ) -> List[Tuple[Event, EventContext]]:
        """
        Get event history from the event system.
        
        Args:
            event_type: Filter by specific event type
            limit: Maximum number of events to return
            
        Returns:
            List of (event, context) tuples
        """
        return self._event_emitter.get_history(event_type, limit)
    
    def get_event_metrics(self) -> Dict[str, int]:
        """Get event system metrics."""
        return self._event_emitter.get_metrics()
    
    def set_json_api_base_url(self, base_url: str) -> None:
        """
        Set the base URL for JSON API operations.
        
        Args:
            base_url: Base URL for HTTP API (e.g., "https://api.spacetimedb.com")
        """
        self._json_api_base_url = base_url
        
        # Reset JSON API client to use new URL
        if self._json_api:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._json_api.close())
            except:
                pass
            finally:
                loop.close()
            self._json_api = None
    
    # Event registration methods
    def register_on_connect(self, callback: Callable[[], None]) -> None:
        """Register a callback for connection events."""
        self._on_connect.append(callback)
    
    def register_on_disconnect(self, callback: Callable[[str], None]) -> None:
        """Register a callback for disconnection events."""
        self._on_disconnect.append(callback)
    
    def register_on_identity(self, callback: Callable[[str, Identity, ConnectionId], None]) -> None:
        """Register a callback for identity events."""
        self._on_identity.append(callback)
    
    def register_on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register a callback for error events."""
        self._on_error.append(callback)
    
    def register_on_event(self, callback: Callable[[ReducerEvent], None]) -> None:
        """Register a callback for reducer events."""
        self._on_event.append(callback)
    
    def register_on_subscription_applied(self, callback: Callable[[], None]) -> None:
        """Register a callback for subscription applied events."""
        self._on_subscription_applied.append(callback)
    
    def register_row_update(
        self,
        table_name: str,
        callback: Callable[[str, Optional[Any], Optional[Any], Optional[ReducerEvent]], None]
    ) -> None:
        """Register a callback for row updates on a specific table."""
        if table_name not in self._row_update_callbacks:
            self._row_update_callbacks[table_name] = []
        self._row_update_callbacks[table_name].append(callback)
    
    def register_reducer_callback(
        self,
        reducer_name: str,
        callback: Callable[[Identity, ConnectionId, str, str, Any], None]
    ) -> None:
        """Register a callback for specific reducer events."""
        if reducer_name not in self._reducer_callbacks:
            self._reducer_callbacks[reducer_name] = []
        self._reducer_callbacks[reducer_name].append(callback)
    
    # Internal event handlers
    def _handle_connect(self) -> None:
        """Handle WebSocket connection."""
        self.logger.info("Connected to SpacetimeDB")
        
        # Handle enhanced connection lifecycle
        if self.enhanced_connection_id:
            self.connection_lifecycle_manager.on_connection_established(
                self.enhanced_connection_id, self.enhanced_identity
            )
            self.connection_metrics.record_connection(self.enhanced_connection_id)
        
        for callback in self._on_connect:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in connect callback: {e}")
    
    def _handle_disconnect(self, reason: str) -> None:
        """Handle WebSocket disconnection."""
        self.logger.info(f"Disconnected from SpacetimeDB: {reason}")
        
        # Handle enhanced connection lifecycle
        if self.enhanced_connection_id:
            self.connection_lifecycle_manager.on_connection_lost(
                self.enhanced_connection_id, reason
            )
            self.connection_metrics.record_disconnection(self.enhanced_connection_id)
        
        for callback in self._on_disconnect:
            try:
                callback(reason)
            except Exception as e:
                self.logger.error(f"Error in disconnect callback: {e}")
    
    def _handle_error(self, error: Exception) -> None:
        """Handle WebSocket error."""
        self.logger.error(f"WebSocket error: {error}")
        for callback in self._on_error:
            try:
                callback(error)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    def _handle_message(self, message: ServerMessage) -> None:
        """Handle incoming server message from WebSocketClient by putting it on the queue."""
        if not self.should_stop_processing.is_set():
            try:
                self.message_queue.put(message)
            except Exception as e:
                self.logger.error(f"_handle_message: Failed to put message on queue: {e}")
        else:
            self.logger.debug(f"_handle_message: Not queueing {type(message).__name__} as client is shutting down.")
    
    def _start_message_processing(self) -> None:
        """Start the message processing thread."""
        if self.processing_thread and self.processing_thread.is_alive():
            self.logger.warning("_start_message_processing: Attempted to start an already running thread.")
            return
        self.logger.debug("_start_message_processing: Starting message processing thread...")
        self.should_stop_processing.clear() # Ensure it's cleared before starting a new thread
        self.processing_thread = threading.Thread(
            target=self._process_messages,
            daemon=True,
            name=f"ModernSpacetimeDBClient-ProcessMessages-{id(self)}"
        )
        self.processing_thread.start()
        self.logger.debug(f"_start_message_processing: Message processing thread (ID: {self.processing_thread.ident}) started.")
    
    def _process_messages(self) -> None:
        """Process incoming messages in a separate thread."""
        self.logger.debug(f"_process_messages: Thread (ID: {threading.get_ident()}) started. should_stop_processing: {self.should_stop_processing.is_set()}")
        while not self.should_stop_processing.is_set():
            try:
                message = self.message_queue.get(timeout=0.5)
                
                if message is None or self.should_stop_processing.is_set():
                    self.logger.debug(f"_process_messages: Shutdown signal (None or flag) received. Exiting loop. Flag: {self.should_stop_processing.is_set()}")
                    break
                    
                self.logger.debug(f"_process_messages: Handling server message of type {type(message).__name__}.")
                self._handle_server_message(message)
                self.message_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"_process_messages: Error processing message: {e}", exc_info=True)
                if self.should_stop_processing.is_set():
                    self.logger.debug("_process_messages: Exiting loop due to exception during shutdown.")
                    break
        self.logger.debug(f"_process_messages: Thread (ID: {threading.get_ident()}) exiting. should_stop_processing: {self.should_stop_processing.is_set()}")
    
    def _handle_server_message(self, message: ServerMessage) -> None:
        """Handle a specific server message."""
        if isinstance(message, IdentityToken):
            self._handle_identity_token(message)
        elif isinstance(message, TransactionUpdate):
            self._handle_transaction_update(message)
        elif isinstance(message, TransactionUpdateLight):
            self._handle_transaction_update_light(message)
        elif isinstance(message, SubscribeApplied):
            self._handle_subscribe_applied(message)
        elif isinstance(message, UnsubscribeApplied):
            self._handle_unsubscribe_applied(message)
        elif isinstance(message, SubscriptionError):
            self._handle_subscription_error(message)
        elif isinstance(message, OneOffQueryResponse):
            self._handle_one_off_query_response(message)
        else:
            self.logger.warning(f"Unhandled message type: {type(message)}")
    
    def _handle_identity_token(self, message: IdentityToken) -> None:
        """Handle identity token message."""
        with self._lock:
            # Store legacy types
            self.identity = message.identity
            self.connection_id = message.connection_id
            
            # Convert to enhanced types
            self.enhanced_identity = ensure_enhanced_identity(message.identity)
            self.enhanced_connection_id = ensure_enhanced_connection_id(message.connection_id)
            
            # Create enhanced identity token
            self.enhanced_identity_token = EnhancedIdentityToken(
                identity=self.enhanced_identity,
                token=message.token,
                connection_id=self.enhanced_connection_id
            )
            
            # Track connection establishment
            self.connection_state_tracker.connection_established(self.enhanced_connection_id)
            self.connection_lifecycle_manager.on_connection_established(
                self.enhanced_connection_id, self.enhanced_identity
            )
            self.connection_metrics.record_connection(self.enhanced_connection_id)
        
        self.logger.info(f"Received identity: {self.identity}")
        
        for callback in self._on_identity:
            try:
                callback(message.token, message.identity, message.connection_id)
            except Exception as e:
                self.logger.error(f"Error in identity callback: {e}")
        
        # Automatically trigger client_connected lifecycle reducer if enabled
        if self.auto_trigger_lifecycle:
            self._trigger_client_connected()
    
    def _trigger_client_connected(self) -> None:
        """
        Automatically trigger client_connected reducer for v1.1.2 compatibility.
        
        This method is called after receiving an identity token to automatically
        trigger the client_connected lifecycle reducer, matching the behavior
        of the C# SDK. The call is made gracefully - if the reducer doesn't exist
        or fails, it won't crash the connection.
        """
        try:
            if self.is_connected:
                self.logger.debug("Auto-triggering client_connected lifecycle reducer for v1.1.2 compatibility")
                
                # Call the reducer with no arguments (as expected by typical client_connected reducers)
                self.call_reducer("client_connected")
                
                self.logger.debug("Successfully triggered client_connected reducer")
            else:
                self.logger.debug("Skipping client_connected trigger - not connected")
                
        except Exception as e:
            # Don't crash the connection if the lifecycle reducer fails
            # This is expected behavior if the server doesn't have a client_connected reducer
            self.logger.debug(f"client_connected auto-trigger failed (reducer may not exist): {e}")
            # Note: We intentionally don't propagate this exception as it's optional functionality
    
    def _handle_transaction_update(self, message: TransactionUpdate) -> None:
        """Handle transaction update message."""
        # Create legacy reducer event for backward compatibility
        reducer_event = ReducerEvent(
            caller_identity=message.caller_identity,
            caller_connection_id=message.caller_connection_id,
            reducer_name=message.reducer_call.reducer_name,
            status="success" if isinstance(message.status, dict) else "error",
            message=str(message.status) if isinstance(message.status, str) else "",
            args={},  # TODO: Decode args
            energy_used=message.energy_quanta_used.quanta,
            execution_duration_nanos=message.total_host_execution_duration.nanos
        )
        
        # Create advanced reducer event
        advanced_reducer_event = create_reducer_event(
            reducer_name=message.reducer_call.reducer_name,
            status="success" if isinstance(message.status, dict) else "error",
            caller_identity=message.caller_identity,
            caller_connection_id=message.caller_connection_id,
            args={},  # TODO: Decode args
            error_message=str(message.status) if isinstance(message.status, str) else None,
            energy_used=message.energy_quanta_used.quanta,
            execution_duration_nanos=message.total_host_execution_duration.nanos,
            request_id=getattr(message.reducer_call, 'request_id', None)
        )
        
        # Update event type based on status
        if advanced_reducer_event.is_success:
            advanced_reducer_event.type = EventType.REDUCER_SUCCESS
        else:
            advanced_reducer_event.type = EventType.REDUCER_ERROR
        
        # Emit the advanced reducer event
        self._event_emitter.emit(advanced_reducer_event)
        
        # Create table reducer event for table interface
        table_reducer_event = TableReducerEvent(
            reducer_name=message.reducer_call.reducer_name,
            args={},  # TODO: Decode args
            sender=str(message.caller_identity) if message.caller_identity else None,
            status="success" if isinstance(message.status, dict) else "error", 
            message=str(message.status) if isinstance(message.status, str) else None,
            request_id=getattr(message.reducer_call, 'request_id', None)
        )
        
        # Create event context for table callbacks
        event_context = create_event_context(
            reducer_event=table_reducer_event,
            timestamp=time.time() if hasattr(time, 'time') else None
        )
        
        # Process table updates through table interface
        if hasattr(message, 'database_update') and message.database_update:
            for table_update in message.database_update.tables:
                # Process through table interface for new callbacks
                self._table_event_processor.process_table_update(
                    table_update,
                    event_context
                )
                
                # Emit advanced table events
                self._emit_table_events(table_update, advanced_reducer_event)
                
                # Also process through legacy system for backward compatibility
                self._process_table_update(table_update)
        
        # Call legacy event callbacks
        for callback in self._on_event:
            try:
                callback(reducer_event)
            except Exception as e:
                self.logger.error(f"Error in event callback: {e}")
        
        # Call legacy reducer-specific callbacks
        reducer_name = message.reducer_call.reducer_name
        if reducer_name in self._reducer_callbacks:
            for callback in self._reducer_callbacks[reducer_name]:
                try:
                    callback(
                        message.caller_identity,
                        message.caller_connection_id,
                        reducer_event.status,
                        reducer_event.message,
                        reducer_event.args
                    )
                except Exception as e:
                    self.logger.error(f"Error in reducer callback: {e}")
    
    def _handle_transaction_update_light(self, message: TransactionUpdateLight) -> None:
        """Handle lightweight transaction update."""
        # Create minimal event context for table callbacks
        event_context = create_event_context(timestamp=time.time())
        
        # Process table updates
        for table_update in message.update.tables:
            # Process through table interface for new callbacks
            self._table_event_processor.process_table_update(
                table_update,
                event_context
            )
            # Also process through legacy system for backward compatibility
            self._process_table_update(table_update)
    
    def _handle_subscribe_applied(self, message: SubscribeApplied) -> None:
        """Handle subscribe applied message."""
        self.logger.info(f"Subscription applied for query {message.query_id.id}")
        
        # Process initial table data
        self._process_table_update(message.table_rows)
        
        # Call subscription applied callbacks
        for callback in self._on_subscription_applied:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in subscription applied callback: {e}")
    
    def _handle_unsubscribe_applied(self, message: UnsubscribeApplied) -> None:
        """Handle unsubscribe applied message."""
        self.logger.info(f"Unsubscription applied for query {message.query_id.id}")
    
    def _handle_subscription_error(self, message: SubscriptionError) -> None:
        """Handle subscription error message."""
        self.logger.error(f"Subscription error: {message.error}")
        
        # TODO: Handle subscription errors appropriately
        # This might involve removing failed subscriptions and notifying callbacks
    
    def _handle_one_off_query_response(self, message: OneOffQueryResponse) -> None:
        """Handle one-off query response."""
        if message.error:
            self.logger.error(f"One-off query error: {message.error}")
        else:
            self.logger.info(f"One-off query completed with {len(message.tables)} tables")
        
        # TODO: Provide a way for applications to receive one-off query results
    
    def _process_table_update(self, table_update) -> None:
        """Process a table update and trigger callbacks."""
        # This is a simplified implementation
        # In a full implementation, this would:
        # 1. Update the client cache
        # 2. Determine what changed (inserts, updates, deletes)
        # 3. Call appropriate row update callbacks
        
        table_name = table_update.table_name
        
        # Call row update callbacks for this table
        if table_name in self._row_update_callbacks:
            for callback in self._row_update_callbacks[table_name]:
                try:
                    # Simplified callback - in reality would process actual row changes
                    callback("update", None, None, None)
                except Exception as e:
                    self.logger.error(f"Error in row update callback: {e}")
    
    def _emit_table_events(
        self, 
        table_update, 
        reducer_event: Optional[AdvancedReducerEvent] = None
    ) -> None:
        """Emit advanced events for table updates."""
        table_name = table_update.table_name
        
        # Emit insert events
        if hasattr(table_update, 'inserts'):
            for row_data in table_update.inserts:
                event = create_table_event(
                    table_name=table_name,
                    operation='insert',
                    row_data=row_data,
                    reducer_event=reducer_event
                )
                self._event_emitter.emit(event)
        
        # Emit delete events
        if hasattr(table_update, 'deletes'):
            for row_data in table_update.deletes:
                event = create_table_event(
                    table_name=table_name,
                    operation='delete',
                    row_data=row_data,
                    old_row_data=row_data,
                    reducer_event=reducer_event
                )
                self._event_emitter.emit(event)
        
        # Detect and emit update events if table has primary key
        table_handle = self._db_interface.get_table(table_name)
        if table_handle and table_handle._primary_key_getter:
            # Group by primary key to find updates
            deletes_by_pk = {}
            inserts_by_pk = {}
            
            if hasattr(table_update, 'deletes'):
                for row_data in table_update.deletes:
                    pk = table_handle._primary_key_getter(row_data)
                    if pk is not None:
                        deletes_by_pk[pk] = row_data
            
            if hasattr(table_update, 'inserts'):
                for row_data in table_update.inserts:
                    pk = table_handle._primary_key_getter(row_data)
                    if pk is not None:
                        inserts_by_pk[pk] = row_data
            
            # Find updates (same PK in both delete and insert)
            for pk in set(deletes_by_pk.keys()) & set(inserts_by_pk.keys()):
                event = create_table_event(
                    table_name=table_name,
                    operation='update',
                    row_data=inserts_by_pk[pk],
                    old_row_data=deletes_by_pk[pk],
                    primary_key=pk,
                    reducer_event=reducer_event
                )
                self._event_emitter.emit(event)
    
    def _simulate_test_connection(self) -> None:
        """Simulate a successful connection in test mode."""
        # Generate test identity and connection ID
        identity = Identity.from_hex("0" * 32)
        connection_id = ConnectionId.from_hex("0" * 16)
        
        # Call connect callbacks first
        self._handle_connect()
        
        # Simulate the complete identity token flow (this triggers lifecycle reducer)
        identity_token = IdentityToken(
            identity=identity,
            connection_id=connection_id,
            token="test_token"
        )
        
        # Process the identity token through the normal flow
        # This will trigger _trigger_client_connected if auto_trigger_lifecycle is enabled
        self._handle_identity_token(identity_token)
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        if self.test_mode:
            # In test mode, consider connected if we have identity
            return self.enhanced_connection_id is not None
        return self.ws_client is not None and self.ws_client.is_connected
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information."""
        base_info = {}
        if self.ws_client:
            base_info = self.ws_client.get_connection_info()
        else:
            base_info = {"state": "disconnected"}
        
        # Add enhanced connection information
        base_info.update({
            "enhanced_connection_id": self.enhanced_connection_id.to_hex() if self.enhanced_connection_id else None,
            "enhanced_identity": self.enhanced_identity.to_hex() if self.enhanced_identity else None,
            "connection_state": self.get_connection_state().value,
            "connection_metrics": self.get_connection_metrics(),
            "identity_info": self.get_identity_info()
        })
        
        return base_info

    # Energy-aware client methods
    def get_current_energy(self) -> int:
        """Get current energy level."""
        return self.energy_tracker.get_current_energy()
    
    def get_energy_budget(self) -> Dict[str, Any]:
        """Get energy budget information."""
        return self.energy_budget_manager.get_budget_utilization()
    
    def can_afford_operation(self, reducer_name: str, args: List[Any] = None) -> bool:
        """
        Check if an operation is affordable given current energy and budget constraints.
        
        Args:
            reducer_name: Name of the reducer to call
            args: Arguments for the reducer
            
        Returns:
            True if the operation can be afforded
        """
        # Estimate energy cost
        estimated_cost = self.energy_cost_estimator.estimate_reducer_cost(reducer_name, args)
        
        # Check both energy tracker and budget manager
        has_energy = self.energy_tracker.get_current_energy() >= estimated_cost
        within_budget = self.energy_budget_manager.can_execute_operation("call_reducer", estimated_cost)
        
        return has_energy and within_budget
    
    def call_reducer_energy_aware(
        self,
        reducer_name: str,
        *args,
        flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE,
        force: bool = False
    ) -> int:
        """
        Call a reducer with energy awareness and budget checking.
        
        Args:
            reducer_name: Name of the reducer to call
            args: Arguments for the reducer
            flags: Reducer call flags
            force: If True, bypass energy checks (for emergency operations)
            
        Returns:
            Request ID
            
        Raises:
            OutOfEnergyError: If insufficient energy or budget
        """
        if not force:
            # Estimate cost
            estimated_cost = self.energy_cost_estimator.estimate_reducer_cost(reducer_name, list(args))
            
            # Check affordability
            if not self.can_afford_operation(reducer_name, list(args)):
                current_energy = self.energy_tracker.get_current_energy()
                raise OutOfEnergyError(
                    f"Insufficient energy to call reducer '{reducer_name}'",
                    required=estimated_cost,
                    available=current_energy,
                    operation=f"call_reducer:{reducer_name}"
                )
            
            # Reserve energy in budget
            import uuid
            reservation_id = str(uuid.uuid4())
            if not self.energy_budget_manager.reserve_energy(reservation_id, estimated_cost):
                raise OutOfEnergyError(
                    f"Insufficient budget to call reducer '{reducer_name}'",
                    required=estimated_cost,
                    available=self.energy_budget_manager.get_remaining_budget(),
                    operation=f"call_reducer:{reducer_name}"
                )
            
            # Track operation start
            import time
            start_time = time.time()
            
            try:
                # Call the reducer
                request_id = self.call_reducer(reducer_name, *args, flags=flags)
                
                # On success, consume energy and budget
                duration = time.time() - start_time
                actual_cost = estimated_cost  # For now, use estimated cost
                
                # Consume from tracker and budget
                self.energy_tracker.consume_energy(actual_cost, f"call_reducer:{reducer_name}")
                self.energy_budget_manager.consume_budget(actual_cost, reservation_id)
                
                # Track in analytics
                self.energy_usage_analytics.track_operation(
                    "call_reducer", reducer_name, actual_cost, duration, True
                )
                
                # Calibrate cost estimator
                self.energy_cost_estimator.calibrate_costs("call_reducer", reducer_name, actual_cost)
                
                # Emit energy events if needed
                current_energy = self.energy_tracker.get_current_energy()
                if current_energy < self.energy_tracker.get_max_energy() * 0.2:  # 20% threshold
                    event = EnergyEvent(
                        event_type=EnergyEventType.ENERGY_LOW,
                        current_energy=current_energy,
                        threshold=int(self.energy_tracker.get_max_energy() * 0.2),
                        operation=f"call_reducer:{reducer_name}"
                    )
                    self.energy_event_manager.emit_event(event)
                    self._notify_energy_listeners(event)
                
                return request_id
                
            except Exception as e:
                # On failure, release reservation
                self.energy_budget_manager.release_energy(reservation_id)
                
                # Track failed operation
                duration = time.time() - start_time
                self.energy_usage_analytics.track_operation(
                    "call_reducer", reducer_name, estimated_cost, duration, False
                )
                raise
        else:
            # Force execution without energy checks
            return self.call_reducer(reducer_name, *args, flags=flags)
    
    def set_energy_budget(self, budget: int, period: float = 3600) -> None:
        """
        Set energy budget.
        
        Args:
            budget: Total energy budget
            period: Budget period in seconds (default: 1 hour)
        """
        self.energy_budget_manager.set_budget(budget, period)
    
    def add_energy_listener(self, listener: EnergyEventListener) -> None:
        """
        Add an energy event listener.
        
        Args:
            listener: Callback function for energy events
        """
        self._energy_event_listeners.append(listener)
        
        # Also register with energy event manager for all event types
        for event_type in EnergyEventType:
            self.energy_event_manager.register_listener(event_type.value, listener)
    
    def get_energy_usage_stats(self, time_range: str = "1h") -> Dict[str, Any]:
        """
        Get energy usage statistics.
        
        Args:
            time_range: Time range for statistics (e.g., "1h", "24h", "7d")
            
        Returns:
            Dictionary containing energy usage statistics
        """
        # Get stats from analytics
        report = self.energy_usage_analytics.generate_report(time_range)
        
        # Get current energy info
        current_energy = self.energy_tracker.get_current_energy()
        max_energy = self.energy_tracker.get_max_energy()
        budget_info = self.energy_budget_manager.get_budget_utilization()
        
        return {
            'current_energy': current_energy,
            'max_energy': max_energy,
            'energy_utilization_percent': (1 - current_energy / max_energy) * 100 if max_energy > 0 else 0,
            'budget_info': budget_info,
            'usage_report': {
                'time_range': report.time_range,
                'total_energy_used': report.total_energy_used,
                'operation_count': report.operation_count,
                'efficiency_score': report.efficiency_score,
                'top_consumers': report.top_consumers,
                'usage_trends': report.usage_trends,
                'recommendations': report.recommendations
            },
            'tracker_stats': self.energy_tracker.get_energy_usage(
                self._parse_time_range_seconds(time_range)
            )
        }
    
    def _parse_time_range_seconds(self, time_range: str) -> float:
        """Parse time range string to seconds."""
        if time_range.endswith('h'):
            return float(time_range[:-1]) * 3600
        elif time_range.endswith('m'):
            return float(time_range[:-1]) * 60
        elif time_range.endswith('d'):
            return float(time_range[:-1]) * 24 * 3600
        elif time_range.endswith('s'):
            return float(time_range[:-1])
        else:
            try:
                return float(time_range)  # Assume seconds
            except ValueError:
                return 3600  # Default to 1 hour
    
    def _setup_energy_events(self) -> None:
        """Setup energy event handling."""
        # Register for energy events that affect connection state
        self.energy_event_manager.register_listener(
            EnergyEventType.ENERGY_EXHAUSTED.value,
            self._handle_energy_exhausted
        )
        self.energy_event_manager.register_listener(
            EnergyEventType.BUDGET_EXCEEDED.value,
            self._handle_budget_exceeded
        )
    
    def _handle_energy_exhausted(self, event: EnergyEvent) -> None:
        """Handle energy exhausted event."""
        self.logger.warning(f"Energy exhausted: {event}")
        # Could implement automatic throttling or connection management here
    
    def _handle_budget_exceeded(self, event: EnergyEvent) -> None:
        """Handle budget exceeded event."""
        self.logger.warning(f"Energy budget exceeded: {event}")
        # Could implement budget reset or notification here
    
    def _notify_energy_listeners(self, event: EnergyEvent) -> None:
        """Notify all energy event listeners."""
        for listener in self._energy_event_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error in energy event listener: {e}")
    
    # Compression-related methods
    
    def get_compression_info(self) -> Dict[str, Any]:
        """
        Get comprehensive compression information.
        
        Returns:
            Dictionary containing compression configuration, capabilities, and metrics
        """
        if self.ws_client:
            return self.ws_client.get_compression_info()
        return {
            "config": {
                "enabled": self.compression_config.enabled,
                "minimum_threshold": self.compression_config.minimum_size_threshold,
                "compression_level": self.compression_config.compression_level.value
            },
            "capabilities": {"supported_types": []},
            "metrics": {"messages_compressed": 0, "compression_ratio": 1.0},
            "negotiated_compression": None
        }
    
    def get_compression_metrics(self) -> CompressionMetrics:
        """
        Get compression performance metrics.
        
        Returns:
            CompressionMetrics object with detailed performance data
        """
        if self.ws_client:
            return self.ws_client.get_compression_metrics()
        return CompressionMetrics()
    
    def enable_compression(self, enabled: bool = True) -> None:
        """
        Enable or disable message compression.
        
        Args:
            enabled: Whether to enable compression
        """
        self.compression_config.enabled = enabled
        if self.ws_client:
            self.ws_client.enable_compression(enabled)
    
    def set_compression_threshold(self, threshold: int) -> None:
        """
        Set minimum message size threshold for compression.
        
        Args:
            threshold: Minimum message size in bytes to trigger compression
        """
        if threshold < 0:
            raise ValueError("Compression threshold must be non-negative")
        
        self.compression_config.minimum_size_threshold = threshold
        if self.ws_client:
            self.ws_client.set_compression_threshold(threshold)
    
    def set_compression_level(self, level: CompressionLevel) -> None:
        """
        Set compression level.
        
        Args:
            level: Compression level (FASTEST, BALANCED, or BEST)
        """
        self.compression_config.compression_level = level
        if self.ws_client:
            self.ws_client.set_compression_level(level)
    
    def reset_compression_metrics(self) -> None:
        """Reset compression performance metrics."""
        if self.ws_client:
            self.ws_client.reset_compression_metrics()

    def _setup_advanced_events(self) -> None:
        """Setup advanced event system integration."""
        # Bridge legacy callbacks to advanced event system
        
        # Connection events
        self._event_emitter.on(
            EventType.CONNECTION_ESTABLISHED,
            lambda ctx: self._handle_connect()
        )
        
        self._event_emitter.on(
            EventType.CONNECTION_LOST,
            lambda ctx: self._handle_disconnect(ctx.event.data.get('reason', 'Unknown'))
        )
        
        # Table events - integrate with table interface
        self._event_emitter.on(
            EventType.TABLE_ROW_INSERT,
            self._handle_advanced_table_insert
        )
        
        self._event_emitter.on(
            EventType.TABLE_ROW_UPDATE,
            self._handle_advanced_table_update
        )
        
        self._event_emitter.on(
            EventType.TABLE_ROW_DELETE,
            self._handle_advanced_table_delete
        )
        
        # Reducer events
        self._event_emitter.on(
            EventType.REDUCER_SUCCESS,
            self._handle_advanced_reducer_success
        )
        
        self._event_emitter.on(
            EventType.REDUCER_ERROR,
            self._handle_advanced_reducer_error
        )

    def _handle_advanced_connect_event(self, event: ConnectionEvent) -> None:
        """Handle advanced connection event."""
        for listener in self._connection_event_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error in connection event listener: {e}")

    def _handle_advanced_disconnect_event(self, event: ConnectionEvent) -> None:
        """Handle advanced disconnection event."""
        for listener in self._connection_event_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error in connection event listener: {e}")

    def _handle_advanced_identity_event(self, event: ConnectionEvent) -> None:
        """Handle advanced identity change event."""
        for listener in self._connection_event_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error in connection event listener: {e}")

    def _handle_advanced_table_insert(self, ctx: EventContext) -> None:
        """Handle advanced table insert event - integrate with table interface."""
        # The table interface already handles table callbacks
        # This is just for advanced event system integration
        pass
    
    def _handle_advanced_table_update(self, ctx: EventContext) -> None:
        """Handle advanced table update event - integrate with table interface."""
        pass
    
    def _handle_advanced_table_delete(self, ctx: EventContext) -> None:
        """Handle advanced table delete event - integrate with table interface."""
        pass
    
    def _handle_advanced_reducer_success(self, ctx: EventContext) -> None:
        """Handle advanced reducer success event."""
        # Can be extended to trigger additional actions on reducer success
        pass
    
    def _handle_advanced_reducer_error(self, ctx: EventContext) -> None:
        """Handle advanced reducer error event."""
        # Can be extended to trigger additional error handling
        pass

    def set_module(self, module: RemoteModule) -> None:
        """
        Set the module for this client, providing runtime type information.
        
        Args:
            module: RemoteModule instance with table and reducer metadata
            
        Example:
            ```python
            from my_generated_module import MyGameModule
            client.set_module(MyGameModule())
            ```
        """
        self._module = module
        
        # Register module globally
        register_module(module)
        
        # Register tables with table interface
        for table_name, metadata in module.tables.items():
            self.register_table(
                table_name=table_name,
                row_type=metadata.row_type,
                primary_key=metadata.primary_key,
                unique_columns=metadata.unique_columns
            )
    
    @property
    def module(self) -> Optional[RemoteModule]:
        """Get the current module for this client."""
        return getattr(self, '_module', None)

    @property
    def diagnostics(self) -> ConnectionDiagnostics:
        """
        Get connection diagnostics utility for troubleshooting.
        
        Example:
            # Run preflight checks
            results = client.diagnostics.run_preflight_checks(
                host="localhost:3000",
                database="my_database",
                raise_on_failure=False
            )
            print(client.diagnostics.format_diagnostic_report(results))
            
            # Check server availability
            is_available, info = client.diagnostics.check_server_available("localhost:3000")
            
            # Check database exists
            db_status = client.diagnostics.check_database_exists("localhost:3000", "my_database")
        """
        return self._diagnostics
    
    def diagnose_connection(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Run connection diagnostics and optionally print results.
        
        Args:
            verbose: Whether to print diagnostic report
            
        Returns:
            Diagnostic results dict
            
        Example:
            results = client.diagnose_connection()
            if not results['all_passed']:
                print("Connection issues detected")
        """
        if not self.ws_client:
            return {
                "error": "Client not initialized",
                "all_passed": False
            }
        
        # Get connection info from WebSocket client
        host = getattr(self.ws_client, 'host', 'localhost:3000')
        database = getattr(self.ws_client, 'database_address', 'unknown')
        
        results = self._diagnostics.run_preflight_checks(
            host=host,
            database=database,
            raise_on_failure=False
        )
        
        if verbose:
            print(self._diagnostics.format_diagnostic_report(results))
        
        return results
    
    def check_database_status(self, database_name: str, host: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if a database exists and is published.
        
        Args:
            database_name: Name of the database to check
            host: Optional host override (uses current connection host if not provided)
            
        Returns:
            Dict containing:
            - exists: True/False/"likely"/"unknown"
            - published: True/False
            - state: "published"/"unpublished"/"non-existent"/"unknown"
            - confidence: "high"/"medium"/"low"/"none"
            - evidence: List of diagnostic evidence
            - suggested_action: Recommended action to take
            
        Example:
            status = client.check_database_status("my_game")
            print(f"Database exists: {status['exists']}")
            print(f"Database published: {status['published']}")
            print(f"Suggested action: {status['suggested_action']}")
        """
        # Use provided host or get from WebSocket client
        if host is None:
            if self.ws_client:
                host = getattr(self.ws_client, 'host', 'localhost:3000')
            else:
                # Default to localhost if no connection
                host = 'localhost:3000'
        
        # Use diagnostics to check database status
        db_status = self._diagnostics.check_database_exists(host, database_name)
        db_state = self._diagnostics.get_database_state(host, database_name)
        
        return {
            'exists': db_status.get('exists', 'unknown'),
            'published': db_status.get('published', False),
            'state': db_state,
            'confidence': db_status.get('confidence', 'low'),
            'evidence': db_status.get('evidence', []),
            'suggested_action': db_status.get('suggested_action', 'unknown'),
            'error': db_status.get('error'),
            'status_code': db_status.get('status_code')
        }
    
    async def wait_for_database_published(
        self, 
        database_name: str, 
        timeout: float = 30.0,
        check_interval: float = 2.0,
        host: Optional[str] = None
    ) -> bool:
        """
        Wait for a database to become published.
        
        This is useful after running `spacetime publish` to wait for the 
        database to become available before connecting.
        
        Args:
            database_name: Name of the database to wait for
            timeout: Maximum time to wait in seconds (default: 30)
            check_interval: How often to check in seconds (default: 2)
            host: Optional host override (uses current connection host if not provided)
            
        Returns:
            True if database became published within timeout, False otherwise
            
        Example:
            # After running spacetime publish my_game
            if await client.wait_for_database_published("my_game", timeout=60):
                print("Database is now published!")
                client.connect(host="localhost:3000", database_address="my_game")
            else:
                print("Timeout waiting for database to be published")
        """
        import asyncio
        import time
        
        # Use provided host or get from WebSocket client
        if host is None:
            if self.ws_client:
                host = getattr(self.ws_client, 'host', 'localhost:3000')
            else:
                host = 'localhost:3000'
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            # Check database status
            status = self.check_database_status(database_name, host)
            
            # Check if published
            if status['published'] and status['exists'] == True:
                self.logger.info(f"Database '{database_name}' is now published")
                # Clear cache to ensure fresh status on next check
                self._diagnostics.clear_database_cache(host, database_name)
                return True
            
            # Log current state
            self.logger.debug(
                f"Database '{database_name}' state: {status['state']} "
                f"(confidence: {status['confidence']})"
            )
            
            # Wait before next check
            await asyncio.sleep(check_interval)
        
        # Timeout reached
        self.logger.warning(
            f"Timeout waiting for database '{database_name}' to be published "
            f"after {timeout} seconds"
        )
        return False
    
    def wait_for_database_published_sync(
        self,
        database_name: str,
        timeout: float = 30.0,
        check_interval: float = 2.0,
        host: Optional[str] = None
    ) -> bool:
        """
        Synchronous version of wait_for_database_published.
        
        Args:
            database_name: Name of the database to wait for
            timeout: Maximum time to wait in seconds (default: 30)
            check_interval: How often to check in seconds (default: 2)
            host: Optional host override
            
        Returns:
            True if database became published within timeout, False otherwise
            
        Example:
            if client.wait_for_database_published_sync("my_game"):
                print("Database is now published!")
        """
        import time
        
        # Use provided host or get from WebSocket client
        if host is None:
            if self.ws_client:
                host = getattr(self.ws_client, 'host', 'localhost:3000')
            else:
                host = 'localhost:3000'
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            # Check database status
            status = self.check_database_status(database_name, host)
            
            # Check if published
            if status['published'] and status['exists'] == True:
                self.logger.info(f"Database '{database_name}' is now published")
                # Clear cache to ensure fresh status on next check
                self._diagnostics.clear_database_cache(host, database_name)
                return True
            
            # Log current state
            self.logger.debug(
                f"Database '{database_name}' state: {status['state']} "
                f"(confidence: {status['confidence']})"
            )
            
            # Wait before next check
            time.sleep(check_interval)
        
        # Timeout reached
        self.logger.warning(
            f"Timeout waiting for database '{database_name}' to be published "
            f"after {timeout} seconds"
        )
        return False
    
    @property
    def scheduler(self) -> 'ReducerScheduler':
        """
        Get the reducer scheduler for time-based and interval-based reducer execution.
        
        Example:
            # Schedule a reducer to run in 60 seconds
            schedule_id = client.scheduler.schedule_in_seconds(
                "cleanup_expired_sessions",
                [],
                60
            )
            
            # Schedule a reducer to run every 5 minutes
            schedule_id = client.scheduler.schedule_at_interval(
                "update_statistics",
                [],
                EnhancedTimeDuration.from_minutes(5)
            )
            
            # Schedule a reducer at a specific time
            future_time = EnhancedTimestamp.now() + EnhancedTimeDuration.from_hours(2)
            schedule_id = client.scheduler.schedule_at_time(
                "send_reminder",
                ["user123"],
                future_time
            )
            
            # Start the scheduler
            await client.scheduler.start()
        """
        if not hasattr(self, '_scheduler') or self._scheduler is None:
            from .scheduling import ReducerScheduler
            self._scheduler = ReducerScheduler(self)
        
        return self._scheduler


# Backward compatibility aliases
SpacetimeDBClient = ModernSpacetimeDBClient
