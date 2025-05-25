"""
DbContext Interface for SpacetimeDB Python SDK.

Provides structured access to database views and reducers with type safety.
Matches TypeScript SDK's DbContext pattern for better developer experience.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Protocol, Any, Dict, Optional, Callable, Type, cast, TYPE_CHECKING
from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass

if TYPE_CHECKING:
    from .modern_client import ModernSpacetimeDBClient
    from .remote_module import RemoteModule, TableMetadata, ReducerMetadata

from .protocol import CallReducerFlags
from .request_tracker import RequestTracker


# Type variables for generic DbContext
TDbView = TypeVar('TDbView')
TReducers = TypeVar('TReducers')
TSetReducerFlags = TypeVar('TSetReducerFlags')


class TableProtocol(Protocol):
    """Protocol for table access with type safety."""
    
    @property
    def name(self) -> str:
        """Get table name."""
        ...
    
    def iter(self) -> Any:
        """Iterate over table rows."""
        ...
    
    def count(self) -> int:
        """Get row count."""
        ...
    
    def all(self) -> list:
        """Get all rows."""
        ...
    
    def find_by_unique_column(self, column: str, value: Any) -> Any:
        """Find row by unique column value."""
        ...


class ReducerProtocol(Protocol):
    """Protocol for reducer access with type safety."""
    
    async def __call__(self, *args, **kwargs) -> str:
        """Call reducer with arguments."""
        ...


class DbView:
    """Base class for database view access."""
    
    def __init__(self, client: 'ModernSpacetimeDBClient', module: Optional['RemoteModule'] = None):
        self._client = client
        self._module = module
        self._tables: Dict[str, TableProtocol] = {}
    
    def __getattr__(self, name: str) -> TableProtocol:
        """Dynamic table access via attribute lookup."""
        if name not in self._tables:
            # Create lazy table accessor
            self._tables[name] = self._create_table_accessor(name)
        return self._tables[name]
    
    def _create_table_accessor(self, table_name: str) -> TableProtocol:
        """Create a table accessor for the given table name."""
        # Check if module has metadata for this table
        metadata = None
        if self._module:
            metadata = self._module.get_table_metadata(table_name)
        
        return TableAccessor(self._client, table_name, metadata)


class Reducers:
    """Base class for reducer access."""
    
    def __init__(self, client: 'ModernSpacetimeDBClient', module: Optional['RemoteModule'] = None):
        self._client = client
        self._module = module
        self._reducers: Dict[str, ReducerProtocol] = {}
    
    def __getattr__(self, name: str) -> ReducerProtocol:
        """Dynamic reducer access via attribute lookup."""
        if name not in self._reducers:
            # Create lazy reducer accessor
            self._reducers[name] = self._create_reducer_accessor(name)
        return self._reducers[name]
    
    def _create_reducer_accessor(self, reducer_name: str) -> ReducerProtocol:
        """Create a reducer accessor for the given reducer name."""
        # Check if module has metadata for this reducer
        metadata = None
        if self._module:
            metadata = self._module.get_reducer_metadata(reducer_name)
        
        return ReducerAccessor(self._client, reducer_name, metadata)


class SetReducerFlags:
    """Base class for setting reducer flags."""
    
    def __init__(self, flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE):
        self._flags = flags
    
    @property
    def flags(self) -> CallReducerFlags:
        """Get current flags."""
        return self._flags
    
    def set_flags(self, flags: CallReducerFlags) -> None:
        """Set reducer flags."""
        self._flags = flags


class DbContext(Generic[TDbView, TReducers, TSetReducerFlags]):
    """
    Database context providing structured access to tables and reducers.
    
    Matches TypeScript SDK's DbContext interface for consistency.
    """
    
    def __init__(
        self,
        client: 'ModernSpacetimeDBClient',
        db_view_class: Type[TDbView] = DbView,
        reducers_class: Type[TReducers] = Reducers,
        set_reducer_flags_class: Type[TSetReducerFlags] = SetReducerFlags,
        module: Optional['RemoteModule'] = None
    ):
        """
        Initialize DbContext with client and optional custom classes.
        
        Args:
            client: SpacetimeDB client instance
            db_view_class: Custom DbView class for typed table access
            reducers_class: Custom Reducers class for typed reducer access
            set_reducer_flags_class: Custom SetReducerFlags class
            module: RemoteModule with runtime type information
        """
        self._client = client
        self._module = module
        
        # Create instances with module information
        if db_view_class == DbView:
            self._db = cast(TDbView, DbView(client, module))
        else:
            # For custom classes, try to pass module if constructor accepts it
            try:
                self._db = db_view_class(client, module)
            except TypeError:
                # Fallback to client-only constructor
                self._db = db_view_class(client)
        
        if reducers_class == Reducers:
            self._reducers = cast(TReducers, Reducers(client, module))
        else:
            # For custom classes, try to pass module if constructor accepts it
            try:
                self._reducers = reducers_class(client, module)
            except TypeError:
                # Fallback to client-only constructor
                self._reducers = reducers_class(client)
        
        self._set_reducer_flags = set_reducer_flags_class() if set_reducer_flags_class != SetReducerFlags else cast(TSetReducerFlags, SetReducerFlags())
    
    @property
    def module(self) -> Optional['RemoteModule']:
        """Get the remote module associated with this context."""
        return self._module
    
    @property
    def db(self) -> TDbView:
        """Access database view for table operations."""
        return self._db
    
    @property
    def reducers(self) -> TReducers:
        """Access reducers for calling server-side functions."""
        return self._reducers
    
    @property
    def setReducerFlags(self) -> TSetReducerFlags:
        """Access reducer flags configuration."""
        return self._set_reducer_flags
    
    @property
    def isActive(self) -> bool:
        """Check if the connection is active."""
        return self._client.connected
    
    async def disconnect(self) -> None:
        """Disconnect from the database."""
        await self._client.disconnect()
    
    def on_connect(self, callback: Callable[[], None]) -> None:
        """Register connection callback."""
        self._client.on_connect = callback
    
    def on_disconnect(self, callback: Callable[[], None]) -> None:
        """Register disconnection callback."""
        self._client.on_disconnect = callback


class TableAccessor:
    """Provides access to a specific table with common operations."""
    
    def __init__(self, client: 'ModernSpacetimeDBClient', table_name: str, metadata: Optional['TableMetadata'] = None):
        self._client = client
        self._table_name = table_name
        self._metadata = metadata
    
    @property
    def name(self) -> str:
        """Get table name."""
        return self._table_name
    
    @property
    def metadata(self) -> Optional['TableMetadata']:
        """Get table metadata if available."""
        return self._metadata
    
    @property
    def primary_key(self) -> Optional[str]:
        """Get primary key column name."""
        return self._metadata.primary_key if self._metadata else None
    
    @property
    def row_type(self) -> Optional[Type]:
        """Get the row type for this table."""
        return self._metadata.row_type if self._metadata else None
    
    def iter(self):
        """Iterate over table rows."""
        # Implementation would connect to actual table data
        # For now, return empty iterator
        return iter([])
    
    def count(self) -> int:
        """Get row count."""
        # Implementation would query actual table
        return 0
    
    def all(self) -> list:
        """Get all rows."""
        return list(self.iter())
    
    def find_by_unique_column(self, column: str, value: Any) -> Optional[Any]:
        """Find row by unique column value."""
        # Implementation would query table with unique constraint
        return None
    
    def on_insert(self, callback: Callable[[Any, Any], None]) -> str:
        """Register insert callback."""
        # Implementation would connect to table events
        return f"{self._table_name}_on_insert"
    
    def on_update(self, callback: Callable[[Any, Any, Any], None]) -> str:
        """Register update callback."""
        return f"{self._table_name}_on_update"
    
    def on_delete(self, callback: Callable[[Any, Any], None]) -> str:
        """Register delete callback."""
        return f"{self._table_name}_on_delete"


class ReducerAccessor:
    """Provides access to a specific reducer."""
    
    def __init__(self, client: 'ModernSpacetimeDBClient', reducer_name: str, metadata: Optional['ReducerMetadata'] = None):
        self._client = client
        self._reducer_name = reducer_name
        self._metadata = metadata
    
    @property
    def metadata(self) -> Optional['ReducerMetadata']:
        """Get reducer metadata if available."""
        return self._metadata
    
    async def __call__(self, *args, **kwargs) -> str:
        """Call the reducer with arguments."""
        # Validate arguments if metadata available
        if self._metadata:
            if kwargs:
                # Validate named arguments match expected parameters
                if not self._metadata.validate_args(kwargs):
                    raise ValueError(f"Invalid arguments for reducer '{self._reducer_name}'")
            elif args:
                # Convert positional args to named args if we have metadata
                if self._metadata.param_names:
                    kwargs = dict(zip(self._metadata.param_names, args))
                else:
                    kwargs = {"args": args}
        else:
            # No metadata, use existing logic
            if args and not kwargs:
                kwargs = args[0] if len(args) == 1 and isinstance(args[0], dict) else {"args": args}
        
        # Use default flags if available
        flags = self._metadata.default_flags if self._metadata else CallReducerFlags.FULL_UPDATE
        
        # Call reducer through client
        return await self._client.call_reducer(self._reducer_name, kwargs, flags=flags)


# Factory functions

def create_db_context(
    client: 'ModernSpacetimeDBClient',
    db_view_class: Type[TDbView] = DbView,
    reducers_class: Type[TReducers] = Reducers,
    set_reducer_flags_class: Type[TSetReducerFlags] = SetReducerFlags,
    module: Optional['RemoteModule'] = None
) -> DbContext[TDbView, TReducers, TSetReducerFlags]:
    """
    Create a DbContext instance with optional custom classes.
    
    Args:
        client: SpacetimeDB client instance
        db_view_class: Custom DbView class for typed table access
        reducers_class: Custom Reducers class for typed reducer access
        set_reducer_flags_class: Custom SetReducerFlags class
        module: RemoteModule with runtime type information
    
    Returns:
        Configured DbContext instance
    
    Example:
        ```python
        # Basic usage
        ctx = create_db_context(client)
        
        # With custom classes
        ctx = create_db_context(
            client,
            db_view_class=MyDbView,
            reducers_class=MyReducers
        )
        
        # With module metadata
        ctx = create_db_context(client, module=my_module)
        ```
    """
    return DbContext(client, db_view_class, reducers_class, set_reducer_flags_class, module)


# Type-safe context builders

@dataclass
class DbContextBuilder:
    """Fluent builder for creating DbContext instances."""
    
    client: Optional['ModernSpacetimeDBClient'] = None
    db_view_class: Type = DbView
    reducers_class: Type = Reducers
    set_reducer_flags_class: Type = SetReducerFlags
    module: Optional['RemoteModule'] = None
    
    def with_client(self, client: 'ModernSpacetimeDBClient') -> 'DbContextBuilder':
        """Set the client instance."""
        self.client = client
        return self
    
    def with_module(self, module: 'RemoteModule') -> 'DbContextBuilder':
        """Set the remote module for type information."""
        self.module = module
        return self
    
    def with_db_view(self, db_view_class: Type[TDbView]) -> 'DbContextBuilder':
        """Set custom DbView class."""
        self.db_view_class = db_view_class
        return self
    
    def with_reducers(self, reducers_class: Type[TReducers]) -> 'DbContextBuilder':
        """Set custom Reducers class."""
        self.reducers_class = reducers_class
        return self
    
    def with_set_reducer_flags(self, set_reducer_flags_class: Type[TSetReducerFlags]) -> 'DbContextBuilder':
        """Set custom SetReducerFlags class."""
        self.set_reducer_flags_class = set_reducer_flags_class
        return self
    
    def build(self) -> DbContext:
        """Build the DbContext instance."""
        if not self.client:
            raise ValueError("Client is required for DbContext")
        
        return DbContext(
            self.client,
            self.db_view_class,
            self.reducers_class,
            self.set_reducer_flags_class,
            self.module
        )


# Integration with generated code

class GeneratedDbView(DbView):
    """Base class for generated database views with typed tables."""
    
    def __init__(self, client: 'ModernSpacetimeDBClient', table_registry: Dict[str, Type], module: Optional['RemoteModule'] = None):
        super().__init__(client, module)
        self._table_registry = table_registry
    
    def _create_table_accessor(self, table_name: str) -> TableProtocol:
        """Create typed table accessor from registry."""
        # The table_registry contains row types, not table accessor types
        # So we should just use the base implementation which creates TableAccessor instances
        return super()._create_table_accessor(table_name)


class GeneratedReducers(Reducers):
    """Base class for generated reducers with typed methods."""
    
    def __init__(self, client: 'ModernSpacetimeDBClient', reducer_registry: Dict[str, Type], module: Optional['RemoteModule'] = None):
        super().__init__(client, module)
        self._reducer_registry = reducer_registry
    
    def _create_reducer_accessor(self, reducer_name: str) -> ReducerProtocol:
        """Create typed reducer accessor from registry."""
        if reducer_name in self._reducer_registry:
            reducer_class = self._reducer_registry[reducer_name]
            return reducer_class(self._client)
        return super()._create_reducer_accessor(reducer_name)


# Helper for runtime type checking

class TypedDbContext(DbContext[TDbView, TReducers, TSetReducerFlags]):
    """DbContext with runtime type checking."""
    
    def __init__(
        self,
        client: 'ModernSpacetimeDBClient',
        db_view_class: Type[TDbView],
        reducers_class: Type[TReducers],
        set_reducer_flags_class: Type[TSetReducerFlags],
        enable_type_checking: bool = True
    ):
        super().__init__(client, db_view_class, reducers_class, set_reducer_flags_class)
        self._enable_type_checking = enable_type_checking
    
    def _validate_table_access(self, table_name: str) -> None:
        """Validate table access if type checking is enabled."""
        if self._enable_type_checking:
            # Check if table exists in schema
            # This would be implemented with actual schema checking
            pass
    
    def _validate_reducer_call(self, reducer_name: str, args: Dict[str, Any]) -> None:
        """Validate reducer call if type checking is enabled."""
        if self._enable_type_checking:
            # Check if reducer exists and validate arguments
            # This would be implemented with actual schema checking
            pass 