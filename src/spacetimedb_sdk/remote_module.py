"""
RemoteModule Interface for SpacetimeDB Python SDK.

Provides runtime type information and metadata for SpacetimeDB modules,
matching TypeScript SDK's module system for better type safety and introspection.
"""

from __future__ import annotations
from typing import TypeVar, Generic, Protocol, Any, Dict, List, Optional, Callable, Type, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import inspect

from .algebraic_type import AlgebraicType, ProductType
from .protocol import CallReducerFlags


# Type variables
TRowType = TypeVar('TRowType')
TArgsType = TypeVar('TArgsType')
TEventContext = TypeVar('TEventContext')
TDbView = TypeVar('TDbView')
TReducers = TypeVar('TReducers')
TSetReducerFlags = TypeVar('TSetReducerFlags')


@dataclass
class TableMetadata:
    """Runtime metadata for a SpacetimeDB table."""
    
    table_name: str
    row_type: Type[TRowType]
    primary_key: Optional[str] = None
    unique_columns: List[str] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)
    
    # Type information
    algebraic_type: Optional[AlgebraicType] = None
    
    # Runtime helpers
    row_constructor: Optional[Callable[[Dict[str, Any]], TRowType]] = None
    row_serializer: Optional[Callable[[TRowType], Dict[str, Any]]] = None
    
    def get_primary_key_value(self, row: TRowType) -> Any:
        """Extract primary key value from a row."""
        if self.primary_key and hasattr(row, self.primary_key):
            return getattr(row, self.primary_key)
        return None
    
    def is_unique_column(self, column_name: str) -> bool:
        """Check if a column has a unique constraint."""
        return column_name in self.unique_columns or column_name == self.primary_key


@dataclass
class ReducerMetadata:
    """Runtime metadata for a SpacetimeDB reducer."""
    
    reducer_name: str
    args_type: Type[TArgsType]
    
    # Type information
    algebraic_type: Optional[AlgebraicType] = None
    
    # Function signature
    param_names: List[str] = field(default_factory=list)
    param_types: Dict[str, Type] = field(default_factory=dict)
    return_type: Optional[Type] = None
    
    # Runtime helpers
    args_constructor: Optional[Callable[[Dict[str, Any]], TArgsType]] = None
    args_serializer: Optional[Callable[[TArgsType], Dict[str, Any]]] = None
    
    # Flags and options
    default_flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE
    requires_auth: bool = False
    
    def validate_args(self, args: Union[Dict[str, Any], TArgsType]) -> bool:
        """Validate reducer arguments."""
        # Basic validation - can be extended
        if isinstance(args, dict):
            return all(name in args for name in self.param_names if name != 'self')
        return True


class RemoteModule(Protocol):
    """
    Protocol for SpacetimeDB remote modules with runtime type information.
    
    Matches TypeScript SDK's module interface for consistency.
    """
    
    @property
    def module_name(self) -> str:
        """Get the module name."""
        ...
    
    @property
    def tables(self) -> Dict[str, TableMetadata]:
        """Get metadata for all tables in the module."""
        ...
    
    @property
    def reducers(self) -> Dict[str, ReducerMetadata]:
        """Get metadata for all reducers in the module."""
        ...
    
    def get_table_metadata(self, table_name: str) -> Optional[TableMetadata]:
        """Get metadata for a specific table."""
        ...
    
    def get_reducer_metadata(self, reducer_name: str) -> Optional[ReducerMetadata]:
        """Get metadata for a specific reducer."""
        ...


class SpacetimeModule(ABC):
    """
    Base class for SpacetimeDB modules with runtime type information.
    
    Provides infrastructure for module metadata and type introspection.
    """
    
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._tables: Dict[str, TableMetadata] = {}
        self._reducers: Dict[str, ReducerMetadata] = {}
        self._initialized = False
    
    @property
    def module_name(self) -> str:
        """Get the module name."""
        return self._module_name
    
    @property
    def tables(self) -> Dict[str, TableMetadata]:
        """Get metadata for all tables."""
        if not self._initialized:
            self._initialize_metadata()
        return self._tables
    
    @property
    def reducers(self) -> Dict[str, ReducerMetadata]:
        """Get metadata for all reducers."""
        if not self._initialized:
            self._initialize_metadata()
        return self._reducers
    
    def get_table_metadata(self, table_name: str) -> Optional[TableMetadata]:
        """Get metadata for a specific table."""
        return self.tables.get(table_name)
    
    def get_reducer_metadata(self, reducer_name: str) -> Optional[ReducerMetadata]:
        """Get metadata for a specific reducer."""
        return self.reducers.get(reducer_name)
    
    @abstractmethod
    def _initialize_metadata(self) -> None:
        """Initialize module metadata. Must be implemented by subclasses."""
        pass
    
    def register_table(
        self,
        table_name: str,
        row_type: Type[TRowType],
        primary_key: Optional[str] = None,
        unique_columns: Optional[List[str]] = None,
        indexes: Optional[List[str]] = None,
        algebraic_type: Optional[AlgebraicType] = None
    ) -> TableMetadata:
        """Register a table with metadata."""
        metadata = TableMetadata(
            table_name=table_name,
            row_type=row_type,
            primary_key=primary_key,
            unique_columns=unique_columns or [],
            indexes=indexes or [],
            algebraic_type=algebraic_type
        )
        self._tables[table_name] = metadata
        return metadata
    
    def register_reducer(
        self,
        reducer_name: str,
        args_type: Type[TArgsType],
        param_names: Optional[List[str]] = None,
        param_types: Optional[Dict[str, Type]] = None,
        return_type: Optional[Type] = None,
        algebraic_type: Optional[AlgebraicType] = None,
        default_flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE,
        requires_auth: bool = False
    ) -> ReducerMetadata:
        """Register a reducer with metadata."""
        metadata = ReducerMetadata(
            reducer_name=reducer_name,
            args_type=args_type,
            param_names=param_names or [],
            param_types=param_types or {},
            return_type=return_type,
            algebraic_type=algebraic_type,
            default_flags=default_flags,
            requires_auth=requires_auth
        )
        self._reducers[reducer_name] = metadata
        return metadata


# Constructor types for dynamic module creation

class EventContextConstructor(Protocol[TEventContext]):
    """Constructor for event context instances."""
    
    def __call__(self, **kwargs) -> TEventContext:
        """Create an event context instance."""
        ...


class DbViewConstructor(Protocol[TDbView]):
    """Constructor for database view instances."""
    
    def __call__(self, client: Any, module: RemoteModule) -> TDbView:
        """Create a database view instance."""
        ...


class ReducersConstructor(Protocol[TReducers]):
    """Constructor for reducers interface instances."""
    
    def __call__(self, client: Any, module: RemoteModule) -> TReducers:
        """Create a reducers interface instance."""
        ...


class SetReducerFlagsConstructor(Protocol[TSetReducerFlags]):
    """Constructor for SetReducerFlags instances."""
    
    def __call__(self, flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE) -> TSetReducerFlags:
        """Create a SetReducerFlags instance."""
        ...


@dataclass
class ModuleConstructors(Generic[TEventContext, TDbView, TReducers, TSetReducerFlags]):
    """
    Collection of constructors for creating module-specific instances.
    
    Used to dynamically create typed interfaces based on module metadata.
    """
    
    event_context_constructor: Optional[EventContextConstructor[TEventContext]] = None
    db_view_constructor: Optional[DbViewConstructor[TDbView]] = None
    reducers_constructor: Optional[ReducersConstructor[TReducers]] = None
    set_reducer_flags_constructor: Optional[SetReducerFlagsConstructor[TSetReducerFlags]] = None


class DynamicModule(SpacetimeModule):
    """
    Dynamic module implementation that can be created at runtime.
    
    Useful for modules loaded from external sources or created dynamically.
    """
    
    def __init__(self, module_name: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(module_name)
        self._metadata = metadata or {}
        
        # Auto-initialize if metadata provided
        if metadata:
            self._initialized = True
            self._load_from_metadata(metadata)
    
    def _initialize_metadata(self) -> None:
        """Initialize metadata from stored data."""
        if self._metadata:
            self._load_from_metadata(self._metadata)
        self._initialized = True
    
    def _load_from_metadata(self, metadata: Dict[str, Any]) -> None:
        """Load module information from metadata dictionary."""
        # Load tables
        for table_info in metadata.get('tables', []):
            self.register_table(
                table_name=table_info['name'],
                row_type=table_info.get('type', dict),
                primary_key=table_info.get('primary_key'),
                unique_columns=table_info.get('unique_columns', []),
                indexes=table_info.get('indexes', [])
            )
        
        # Load reducers
        for reducer_info in metadata.get('reducers', []):
            self.register_reducer(
                reducer_name=reducer_info['name'],
                args_type=reducer_info.get('type', dict),
                param_names=reducer_info.get('params', []),
                requires_auth=reducer_info.get('requires_auth', False)
            )


class GeneratedModule(SpacetimeModule):
    """
    Base class for generated SpacetimeDB modules.
    
    Generated code should inherit from this class and implement
    _initialize_metadata to register all tables and reducers.
    """
    
    def __init__(self, module_name: str):
        super().__init__(module_name)
        self._constructors = ModuleConstructors()
    
    @property
    def constructors(self) -> ModuleConstructors:
        """Get module constructors."""
        return self._constructors
    
    def set_constructors(
        self,
        event_context: Optional[EventContextConstructor] = None,
        db_view: Optional[DbViewConstructor] = None,
        reducers: Optional[ReducersConstructor] = None,
        set_reducer_flags: Optional[SetReducerFlagsConstructor] = None
    ) -> None:
        """Set module constructors for dynamic instance creation."""
        if event_context:
            self._constructors.event_context_constructor = event_context
        if db_view:
            self._constructors.db_view_constructor = db_view
        if reducers:
            self._constructors.reducers_constructor = reducers
        if set_reducer_flags:
            self._constructors.set_reducer_flags_constructor = set_reducer_flags


# Module introspection utilities

class ModuleIntrospector:
    """Utilities for module introspection and type discovery."""
    
    @staticmethod
    def extract_table_metadata(table_class: Type) -> TableMetadata:
        """Extract metadata from a table class using introspection."""
        # Get table name
        table_name = getattr(table_class, '__tablename__', table_class.__name__.lower())
        
        # Find primary key
        primary_key = None
        unique_columns = []
        
        # Check for annotations
        if hasattr(table_class, '__annotations__'):
            for field_name, field_type in table_class.__annotations__.items():
                # Check for primary key marker
                if hasattr(table_class, field_name):
                    field_value = getattr(table_class, field_name)
                    if hasattr(field_value, '__primary_key__'):
                        primary_key = field_name
                    if hasattr(field_value, '__unique__'):
                        unique_columns.append(field_name)
        
        return TableMetadata(
            table_name=table_name,
            row_type=table_class,
            primary_key=primary_key,
            unique_columns=unique_columns
        )
    
    @staticmethod
    def extract_reducer_metadata(reducer_func: Callable) -> ReducerMetadata:
        """Extract metadata from a reducer function using introspection."""
        # Get reducer name
        reducer_name = reducer_func.__name__
        
        # Get function signature
        sig = inspect.signature(reducer_func)
        param_names = []
        param_types = {}
        
        for param_name, param in sig.parameters.items():
            if param_name != 'self':
                param_names.append(param_name)
                if param.annotation != inspect.Parameter.empty:
                    param_types[param_name] = param.annotation
        
        # Get return type
        return_type = sig.return_annotation if sig.return_annotation != inspect.Signature.empty else None
        
        # Create args type (dict by default)
        args_type = dict
        
        return ReducerMetadata(
            reducer_name=reducer_name,
            args_type=args_type,
            param_names=param_names,
            param_types=param_types,
            return_type=return_type
        )
    
    @staticmethod
    def discover_module(module_obj: Any) -> SpacetimeModule:
        """Discover module structure from a Python module object."""
        module_name = getattr(module_obj, '__name__', 'unknown')
        dynamic_module = DynamicModule(module_name)
        
        # Discover tables (classes with __tablename__ or ending with 'Table')
        for name, obj in inspect.getmembers(module_obj, inspect.isclass):
            if hasattr(obj, '__tablename__') or name.endswith('Table'):
                metadata = ModuleIntrospector.extract_table_metadata(obj)
                dynamic_module._tables[metadata.table_name] = metadata
        
        # Discover reducers (functions marked as reducers)
        for name, obj in inspect.getmembers(module_obj, inspect.isfunction):
            if hasattr(obj, '__reducer__') or name.startswith('reducer_'):
                metadata = ModuleIntrospector.extract_reducer_metadata(obj)
                dynamic_module._reducers[metadata.reducer_name] = metadata
        
        dynamic_module._initialized = True
        return dynamic_module


# Module registry for managing multiple modules

class ModuleRegistry:
    """Registry for managing multiple SpacetimeDB modules."""
    
    def __init__(self):
        self._modules: Dict[str, RemoteModule] = {}
    
    def register(self, module: RemoteModule) -> None:
        """Register a module."""
        self._modules[module.module_name] = module
    
    def get(self, module_name: str) -> Optional[RemoteModule]:
        """Get a module by name."""
        return self._modules.get(module_name)
    
    def list_modules(self) -> List[str]:
        """List all registered module names."""
        return list(self._modules.keys())
    
    def get_all_tables(self) -> Dict[str, TableMetadata]:
        """Get all tables from all modules."""
        all_tables = {}
        for module in self._modules.values():
            for table_name, metadata in module.tables.items():
                qualified_name = f"{module.module_name}.{table_name}"
                all_tables[qualified_name] = metadata
        return all_tables
    
    def get_all_reducers(self) -> Dict[str, ReducerMetadata]:
        """Get all reducers from all modules."""
        all_reducers = {}
        for module in self._modules.values():
            for reducer_name, metadata in module.reducers.items():
                qualified_name = f"{module.module_name}.{reducer_name}"
                all_reducers[qualified_name] = metadata
        return all_reducers


# Global module registry
_global_registry = ModuleRegistry()

def get_module_registry() -> ModuleRegistry:
    """Get the global module registry."""
    return _global_registry

def register_module(module: RemoteModule) -> None:
    """Register a module in the global registry."""
    _global_registry.register(module)

def get_module(module_name: str) -> Optional[RemoteModule]:
    """Get a module from the global registry."""
    return _global_registry.get(module_name) 