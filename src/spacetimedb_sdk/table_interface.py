"""
Enhanced Table Interface System for SpacetimeDB Python SDK.

Provides rich table interaction APIs matching TypeScript SDK functionality:
- conn.db.table_name.on_insert(callback)
- conn.db.table_name.on_delete(callback) 
- conn.db.table_name.on_update(callback)
- conn.db.table_name.iter()
- conn.db.table_name.count()
- conn.db.table_name.find_by_<unique_column>(value)
"""

import logging
from typing import Any, Callable, Dict, Iterator, List, Optional, Type, TypeVar, Generic, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import threading
import uuid
from weakref import WeakSet, WeakKeyDictionary

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T')
CallbackId = str
EventContext = TypeVar('EventContext')


@dataclass
class RowChange:
    """Represents a change to a table row."""
    op: str  # "insert", "update", "delete"
    table_name: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    primary_key: Optional[Any] = None
    timestamp: Optional[float] = None
    reducer_event: Optional['ReducerEvent'] = None


@dataclass  
class ReducerEvent:
    """Information about the reducer that caused a row change."""
    reducer_name: str
    args: Dict[str, Any]
    sender: Optional[str] = None
    status: str = "committed"
    message: Optional[str] = None
    request_id: Optional[bytes] = None


class CallbackManager:
    """Manages callbacks for table events."""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self._callbacks: Dict[str, Dict[CallbackId, Callable]] = {
            'insert': {},
            'delete': {},
            'update': {}
        }
        self._lock = threading.RLock()
        self._next_id = 0
        
    def add_callback(self, event_type: str, callback: Callable) -> CallbackId:
        """Add a callback and return its ID."""
        with self._lock:
            callback_id = f"{self.table_name}_{event_type}_{self._next_id}"
            self._next_id += 1
            self._callbacks[event_type][callback_id] = callback
            logger.debug(f"Added {event_type} callback {callback_id} for table {self.table_name}")
            return callback_id
            
    def remove_callback(self, event_type: str, callback_id: CallbackId) -> bool:
        """Remove a callback by ID. Returns True if removed."""
        with self._lock:
            if callback_id in self._callbacks[event_type]:
                del self._callbacks[event_type][callback_id]
                logger.debug(f"Removed {event_type} callback {callback_id} for table {self.table_name}")
                return True
            return False
            
    def invoke_callbacks(self, event_type: str, *args, **kwargs):
        """Invoke all callbacks for an event type."""
        with self._lock:
            callbacks = list(self._callbacks[event_type].values())
            
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {event_type} callback for table {self.table_name}: {e}")


class TableHandle(Generic[T]):
    """
    Handle for interacting with a specific table in the client cache.
    
    Provides TypeScript SDK-compatible API for table operations.
    """
    
    def __init__(self, table_name: str, client: Any, row_type: Type[T]):
        self.table_name = table_name
        self.client = client
        self.row_type = row_type
        self._callback_manager = CallbackManager(table_name)
        self._unique_columns: Dict[str, Callable[[T], Any]] = {}
        self._primary_key_column: Optional[str] = None
        self._primary_key_getter: Optional[Callable[[T], Any]] = None
        
    def count(self) -> int:
        """Get the number of rows in the table."""
        cache = self.client._get_table_cache(self.table_name)
        if hasattr(cache, 'entries'):
            return len(cache.entries)
        elif hasattr(cache, 'values'):
            return len(list(cache.values()))
        return 0
        
    def iter(self) -> Iterator[T]:
        """Iterate over all rows in the table."""
        cache = self.client._get_table_cache(self.table_name)
        if hasattr(cache, 'values'):
            return iter(cache.values())
        elif hasattr(cache, 'entries'):
            return iter(cache.entries.values())
        return iter([])
        
    def all(self) -> List[T]:
        """Get all rows as a list."""
        return list(self.iter())
        
    # Insert callbacks
    def on_insert(self, callback: Callable[[EventContext, T], None]) -> CallbackId:
        """
        Register a callback to run when a row is inserted.
        
        Args:
            callback: Function called with (event_context, row) when a row is inserted
            
        Returns:
            CallbackId that can be used to remove the callback
        """
        def wrapper(event_context, row_change: RowChange):
            if row_change.new_value:
                callback(event_context, row_change.new_value)
                
        return self._callback_manager.add_callback('insert', wrapper)
        
    def remove_on_insert(self, callback_id: CallbackId) -> bool:
        """Remove an insert callback by ID."""
        return self._callback_manager.remove_callback('insert', callback_id)
        
    # Delete callbacks  
    def on_delete(self, callback: Callable[[EventContext, T], None]) -> CallbackId:
        """
        Register a callback to run when a row is deleted.
        
        Args:
            callback: Function called with (event_context, row) when a row is deleted
            
        Returns:
            CallbackId that can be used to remove the callback
        """
        def wrapper(event_context, row_change: RowChange):
            if row_change.old_value:
                callback(event_context, row_change.old_value)
                
        return self._callback_manager.add_callback('delete', wrapper)
        
    def remove_on_delete(self, callback_id: CallbackId) -> bool:
        """Remove a delete callback by ID."""
        return self._callback_manager.remove_callback('delete', callback_id)
        
    # Update callbacks (only for tables with primary key)
    def on_update(self, callback: Callable[[EventContext, T, T], None]) -> CallbackId:
        """
        Register a callback to run when a row is updated.
        
        Only available for tables with a primary key.
        
        Args:
            callback: Function called with (event_context, old_row, new_row) when updated
            
        Returns:
            CallbackId that can be used to remove the callback
        """
        if not self._primary_key_column:
            raise ValueError(f"Table {self.table_name} does not have a primary key - updates not supported")
            
        def wrapper(event_context, row_change: RowChange):
            if row_change.old_value and row_change.new_value:
                callback(event_context, row_change.old_value, row_change.new_value)
                
        return self._callback_manager.add_callback('update', wrapper)
        
    def remove_on_update(self, callback_id: CallbackId) -> bool:
        """Remove an update callback by ID."""
        return self._callback_manager.remove_callback('update', callback_id)
        
    # Unique column support
    def add_unique_column(self, column_name: str, getter: Callable[[T], Any]):
        """Register a unique column for find_by operations."""
        self._unique_columns[column_name] = getter
        
    def set_primary_key(self, column_name: str, getter: Callable[[T], Any]):
        """Set the primary key column for update detection."""
        self._primary_key_column = column_name
        self._primary_key_getter = getter
        
    def find_by_unique_column(self, column_name: str, value: Any) -> Optional[T]:
        """Find a row by a unique column value."""
        if column_name not in self._unique_columns:
            raise ValueError(f"Column {column_name} is not registered as unique for table {self.table_name}")
            
        getter = self._unique_columns[column_name]
        for row in self.iter():
            if getter(row) == value:
                return row
        return None
        
    # Internal methods for event processing
    def _process_row_change(self, row_change: RowChange, event_context: Any = None):
        """Process a row change and invoke appropriate callbacks."""
        if row_change.op == "insert":
            self._callback_manager.invoke_callbacks('insert', event_context, row_change)
        elif row_change.op == "delete":
            self._callback_manager.invoke_callbacks('delete', event_context, row_change)
        elif row_change.op == "update":
            self._callback_manager.invoke_callbacks('update', event_context, row_change)
            

class DatabaseInterface:
    """
    Provides table access through conn.db.table_name pattern.
    
    This class dynamically provides access to table handles.
    """
    
    def __init__(self, client: Any):
        self.client = client
        self._table_handles: Dict[str, TableHandle] = {}
        self._table_metadata: Dict[str, Dict[str, Any]] = {}
        
    def register_table(self, table_name: str, row_type: Type[Any], 
                      primary_key: Optional[str] = None,
                      unique_columns: Optional[List[str]] = None):
        """
        Register a table with the database interface.
        
        Args:
            table_name: Name of the table
            row_type: Type of rows in the table
            primary_key: Name of primary key column (if any)
            unique_columns: List of unique column names
        """
        # Create table handle
        handle = TableHandle(table_name, self.client, row_type)
        
        # Store metadata
        self._table_metadata[table_name] = {
            'row_type': row_type,
            'primary_key': primary_key,
            'unique_columns': unique_columns or []
        }
        
        # Register unique columns
        if unique_columns:
            for col in unique_columns:
                # Assume getter is an attribute access
                handle.add_unique_column(col, lambda row, c=col: getattr(row, c, None))
                
        # Set primary key
        if primary_key:
            handle.set_primary_key(primary_key, lambda row: getattr(row, primary_key, None))
            
        self._table_handles[table_name] = handle
        
    def get_table(self, table_name: str) -> Optional[TableHandle]:
        """Get a table handle by name."""
        return self._table_handles.get(table_name)
        
    def __getattr__(self, table_name: str) -> TableHandle:
        """
        Dynamic attribute access for tables.
        
        Allows conn.db.table_name syntax.
        """
        if table_name in self._table_handles:
            return self._table_handles[table_name]
            
        # Try snake_case to PascalCase conversion
        pascal_name = ''.join(word.capitalize() for word in table_name.split('_'))
        if pascal_name in self._table_handles:
            return self._table_handles[pascal_name]
            
        raise AttributeError(f"No table '{table_name}' registered in database interface")
        
    def list_tables(self) -> List[str]:
        """List all registered table names."""
        return list(self._table_handles.keys())
        
    def get_table_metadata(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a table."""
        return self._table_metadata.get(table_name)


class TableEventProcessor:
    """
    Processes table update events and triggers callbacks.
    
    Bridges between raw protocol events and the table interface.
    """
    
    def __init__(self, db_interface: DatabaseInterface):
        self.db_interface = db_interface
        self.logger = logging.getLogger(f"{__name__}.TableEventProcessor")
        
    def process_table_update(self, table_update: 'TableUpdate', event_context: Any = None):
        """Process a table update from the protocol."""
        table_name = table_update.table_name
        table_handle = self.db_interface.get_table(table_name)
        
        if not table_handle:
            self.logger.warning(f"No table handle registered for {table_name}")
            return
            
        # Process inserts
        for insert_data in table_update.inserts:
            row_change = RowChange(
                op="insert",
                table_name=table_name,
                new_value=insert_data
            )
            table_handle._process_row_change(row_change, event_context)
            
        # Process deletes  
        for delete_data in table_update.deletes:
            row_change = RowChange(
                op="delete",
                table_name=table_name,
                old_value=delete_data
            )
            table_handle._process_row_change(row_change, event_context)
            
        # Detect updates if table has primary key
        if table_handle._primary_key_getter:
            # Group by primary key to find updates
            deletes_by_pk = {}
            inserts_by_pk = {}
            
            for delete_data in table_update.deletes:
                pk = table_handle._primary_key_getter(delete_data)
                if pk is not None:
                    deletes_by_pk[pk] = delete_data
                    
            for insert_data in table_update.inserts:
                pk = table_handle._primary_key_getter(insert_data)
                if pk is not None:
                    inserts_by_pk[pk] = insert_data
                    
            # Find updates (same PK in both delete and insert)
            for pk in set(deletes_by_pk.keys()) & set(inserts_by_pk.keys()):
                row_change = RowChange(
                    op="update",
                    table_name=table_name,
                    old_value=deletes_by_pk[pk],
                    new_value=inserts_by_pk[pk],
                    primary_key=pk
                )
                table_handle._process_row_change(row_change, event_context)


# Helper function to create event context
def create_event_context(reducer_event: Optional[ReducerEvent] = None, 
                        timestamp: Optional[float] = None) -> Dict[str, Any]:
    """Create an event context for callbacks."""
    return {
        'reducer_event': reducer_event,
        'timestamp': timestamp or None,
        'source': 'table_interface'
    } 