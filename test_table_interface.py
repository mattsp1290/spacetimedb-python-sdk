"""
Test Enhanced Table Interface System for SpacetimeDB Python SDK.

Tests the TypeScript SDK-compatible table interface with:
- conn.db.table_name.on_insert(callback)
- conn.db.table_name.on_delete(callback)
- conn.db.table_name.on_update(callback)
- conn.db.table_name.iter()
- conn.db.table_name.count()
- conn.db.table_name.find_by_unique_column(value)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional, Any

from spacetimedb_sdk.table_interface import (
    TableHandle,
    DatabaseInterface,
    TableEventProcessor,
    RowChange,
    ReducerEvent,
    CallbackManager,
    create_event_context
)
from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient


# Sample table row types for testing
@dataclass
class User:
    id: int
    name: str
    email: str
    online: bool = False


@dataclass
class Message:
    id: int
    sender_id: int
    text: str
    timestamp: float


class TestCallbackManager(unittest.TestCase):
    """Test the callback management system."""
    
    def setUp(self):
        self.manager = CallbackManager("test_table")
        
    def test_add_callback(self):
        """Test adding callbacks."""
        callback = Mock()
        callback_id = self.manager.add_callback('insert', callback)
        
        self.assertIsInstance(callback_id, str)
        self.assertIn('test_table_insert', callback_id)
        self.assertIn(callback_id, self.manager._callbacks['insert'])
        
    def test_remove_callback(self):
        """Test removing callbacks."""
        callback = Mock()
        callback_id = self.manager.add_callback('delete', callback)
        
        # Remove callback
        removed = self.manager.remove_callback('delete', callback_id)
        self.assertTrue(removed)
        self.assertNotIn(callback_id, self.manager._callbacks['delete'])
        
        # Try removing non-existent callback
        removed = self.manager.remove_callback('delete', 'non_existent')
        self.assertFalse(removed)
        
    def test_invoke_callbacks(self):
        """Test invoking callbacks."""
        callback1 = Mock()
        callback2 = Mock()
        
        self.manager.add_callback('update', callback1)
        self.manager.add_callback('update', callback2)
        
        # Invoke callbacks
        self.manager.invoke_callbacks('update', 'arg1', kwarg='value')
        
        callback1.assert_called_once_with('arg1', kwarg='value')
        callback2.assert_called_once_with('arg1', kwarg='value')
        
    def test_callback_error_handling(self):
        """Test error handling in callbacks."""
        good_callback = Mock()
        bad_callback = Mock(side_effect=Exception("Test error"))
        
        self.manager.add_callback('insert', good_callback)
        self.manager.add_callback('insert', bad_callback)
        
        # Should not raise despite bad callback
        self.manager.invoke_callbacks('insert', 'test')
        
        good_callback.assert_called_once()
        bad_callback.assert_called_once()


class TestTableHandle(unittest.TestCase):
    """Test the table handle functionality."""
    
    def setUp(self):
        self.mock_client = Mock()
        self.mock_cache = Mock()
        self.mock_client._get_table_cache.return_value = self.mock_cache
        
        self.table = TableHandle("users", self.mock_client, User)
        
    def test_count(self):
        """Test row counting."""
        # Test with entries attribute
        self.mock_cache.entries = {'key1': User(1, 'Alice', 'alice@example.com')}
        count = self.table.count()
        self.assertEqual(count, 1)
        
        # Test with values method
        del self.mock_cache.entries
        self.mock_cache.values.return_value = [User(1, 'Alice', 'alice@example.com')]
        count = self.table.count()
        self.assertEqual(count, 1)
        
    def test_iter(self):
        """Test iteration over rows."""
        users = [
            User(1, 'Alice', 'alice@example.com'),
            User(2, 'Bob', 'bob@example.com')
        ]
        self.mock_cache.values.return_value = iter(users)
        
        result = list(self.table.iter())
        self.assertEqual(result, users)
        
    def test_on_insert(self):
        """Test insert callback registration."""
        callback = Mock()
        callback_id = self.table.on_insert(callback)
        
        self.assertIsInstance(callback_id, str)
        
        # Simulate insert event
        row_change = RowChange(
            op="insert",
            table_name="users",
            new_value=User(1, 'Alice', 'alice@example.com')
        )
        event_context = {}
        
        self.table._callback_manager.invoke_callbacks('insert', event_context, row_change)
        
        # Callback should be called with context and row
        callback.assert_called_once()
        args = callback.call_args[0]
        self.assertEqual(args[0], event_context)
        self.assertEqual(args[1], row_change.new_value)
        
    def test_on_delete(self):
        """Test delete callback registration."""
        callback = Mock()
        callback_id = self.table.on_delete(callback)
        
        # Simulate delete event
        row_change = RowChange(
            op="delete",
            table_name="users",
            old_value=User(1, 'Alice', 'alice@example.com')
        )
        event_context = {}
        
        self.table._callback_manager.invoke_callbacks('delete', event_context, row_change)
        
        callback.assert_called_once()
        args = callback.call_args[0]
        self.assertEqual(args[0], event_context)
        self.assertEqual(args[1], row_change.old_value)
        
    def test_on_update_with_primary_key(self):
        """Test update callback with primary key."""
        # Set primary key
        self.table.set_primary_key('id', lambda row: row.id)
        
        callback = Mock()
        callback_id = self.table.on_update(callback)
        
        # Simulate update event
        old_user = User(1, 'Alice', 'alice@example.com')
        new_user = User(1, 'Alice', 'alice@newdomain.com')
        
        row_change = RowChange(
            op="update",
            table_name="users",
            old_value=old_user,
            new_value=new_user,
            primary_key=1
        )
        event_context = {}
        
        self.table._callback_manager.invoke_callbacks('update', event_context, row_change)
        
        callback.assert_called_once()
        args = callback.call_args[0]
        self.assertEqual(args[0], event_context)
        self.assertEqual(args[1], old_user)
        self.assertEqual(args[2], new_user)
        
    def test_on_update_without_primary_key(self):
        """Test update callback fails without primary key."""
        with self.assertRaises(ValueError) as cm:
            self.table.on_update(Mock())
        
        self.assertIn("does not have a primary key", str(cm.exception))
        
    def test_find_by_unique_column(self):
        """Test finding by unique column."""
        users = [
            User(1, 'Alice', 'alice@example.com'),
            User(2, 'Bob', 'bob@example.com')
        ]
        self.mock_cache.values.return_value = iter(users)
        
        # Register unique column
        self.table.add_unique_column('email', lambda row: row.email)
        
        # Find by email
        result = self.table.find_by_unique_column('email', 'bob@example.com')
        self.assertEqual(result, users[1])
        
        # Not found
        result = self.table.find_by_unique_column('email', 'not@found.com')
        self.assertIsNone(result)
        
        # Invalid column
        with self.assertRaises(ValueError):
            self.table.find_by_unique_column('invalid', 'value')


class TestDatabaseInterface(unittest.TestCase):
    """Test the database interface functionality."""
    
    def setUp(self):
        self.mock_client = Mock()
        self.db = DatabaseInterface(self.mock_client)
        
    def test_register_table(self):
        """Test registering tables."""
        self.db.register_table("users", User, primary_key="id", unique_columns=["email"])
        
        self.assertIn("users", self.db._table_handles)
        self.assertIn("users", self.db._table_metadata)
        
        metadata = self.db._table_metadata["users"]
        self.assertEqual(metadata['row_type'], User)
        self.assertEqual(metadata['primary_key'], 'id')
        self.assertEqual(metadata['unique_columns'], ['email'])
        
    def test_get_table(self):
        """Test getting table by name."""
        self.db.register_table("messages", Message)
        
        table = self.db.get_table("messages")
        self.assertIsInstance(table, TableHandle)
        self.assertEqual(table.table_name, "messages")
        
        # Non-existent table
        table = self.db.get_table("non_existent")
        self.assertIsNone(table)
        
    def test_dynamic_attribute_access(self):
        """Test accessing tables via attributes."""
        self.db.register_table("users", User)
        self.db.register_table("Messages", Message)  # PascalCase
        
        # Direct access
        users_table = self.db.users
        self.assertIsInstance(users_table, TableHandle)
        
        # Snake_case to PascalCase conversion
        messages_table = self.db.messages
        self.assertIsInstance(messages_table, TableHandle)
        
        # Non-existent table
        with self.assertRaises(AttributeError):
            _ = self.db.non_existent_table
            
    def test_list_tables(self):
        """Test listing registered tables."""
        self.db.register_table("users", User)
        self.db.register_table("messages", Message)
        
        tables = self.db.list_tables()
        self.assertEqual(set(tables), {"users", "messages"})


class TestTableEventProcessor(unittest.TestCase):
    """Test the table event processor."""
    
    def setUp(self):
        self.mock_client = Mock()
        self.db = DatabaseInterface(self.mock_client)
        self.processor = TableEventProcessor(self.db)
        
        # Register test table
        self.db.register_table("users", User, primary_key="id")
        self.users_table = self.db.get_table("users")
        
    def test_process_inserts(self):
        """Test processing insert events."""
        # Mock table update
        table_update = Mock()
        table_update.table_name = "users"
        table_update.inserts = [
            {'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'online': True}
        ]
        table_update.deletes = []
        
        # Add insert callback
        insert_callback = Mock()
        self.users_table._callback_manager.add_callback('insert', insert_callback)
        
        # Process update
        event_context = create_event_context()
        self.processor.process_table_update(table_update, event_context)
        
        # Verify callback was called
        insert_callback.assert_called_once()
        
    def test_process_updates_with_primary_key(self):
        """Test processing update events with primary key."""
        # Set up primary key
        self.users_table.set_primary_key('id', lambda row: row.get('id'))
        
        # Mock table update with delete and insert of same PK
        table_update = Mock()
        table_update.table_name = "users"
        table_update.deletes = [
            {'id': 1, 'name': 'Alice', 'email': 'old@example.com', 'online': False}
        ]
        table_update.inserts = [
            {'id': 1, 'name': 'Alice', 'email': 'new@example.com', 'online': True}
        ]
        
        # Add update callback
        update_callback = Mock()
        self.users_table._callback_manager.add_callback('update', update_callback)
        
        # Process update
        event_context = create_event_context()
        self.processor.process_table_update(table_update, event_context)
        
        # Verify update callback was called
        update_callback.assert_called_once()


class TestModernClientIntegration(unittest.TestCase):
    """Test integration with ModernSpacetimeDBClient."""
    
    @patch('spacetimedb_sdk.modern_client.ModernWebSocketClient')
    def setUp(self, mock_ws_client_class):
        """Set up test client."""
        self.mock_ws = Mock()
        mock_ws_client_class.return_value = self.mock_ws
        
        self.client = ModernSpacetimeDBClient(
            start_message_processing=False  # Disable for testing
        )
        
        # Register tables
        self.client.register_table("users", User, primary_key="id", unique_columns=["email"])
        self.client.register_table("messages", Message, primary_key="id")
        
    def test_db_property_access(self):
        """Test accessing tables via db property."""
        # Access users table
        users_table = self.client.db.users
        self.assertIsInstance(users_table, TableHandle)
        self.assertEqual(users_table.table_name, "users")
        
        # Access messages table
        messages_table = self.client.db.messages
        self.assertIsInstance(messages_table, TableHandle)
        
    def test_table_callbacks_via_db(self):
        """Test registering callbacks via db interface."""
        # Register callbacks
        insert_callback = Mock()
        delete_callback = Mock()
        update_callback = Mock()
        
        self.client.db.users.on_insert(insert_callback)
        self.client.db.users.on_delete(delete_callback)
        self.client.db.users.on_update(update_callback)
        
        # Callbacks should be registered
        self.assertEqual(len(self.client.db.users._callback_manager._callbacks['insert']), 1)
        self.assertEqual(len(self.client.db.users._callback_manager._callbacks['delete']), 1)
        self.assertEqual(len(self.client.db.users._callback_manager._callbacks['update']), 1)
        
    def test_chained_api(self):
        """Test chained API usage."""
        # Mock cache data
        mock_cache = Mock()
        # Need to properly mock entries for count() method
        mock_cache.entries = {'user1': User(1, 'Alice', 'alice@example.com'), 
                              'user2': User(2, 'Bob', 'bob@example.com')}
        mock_cache.values.return_value = [
            User(1, 'Alice', 'alice@example.com'),
            User(2, 'Bob', 'bob@example.com')
        ]
        self.client._get_table_cache = Mock(return_value=mock_cache)
        
        # Chain operations
        count = self.client.db.users.count()
        self.assertEqual(count, 2)
        
        all_users = self.client.db.users.all()
        self.assertEqual(len(all_users), 2)
        
        # Register callback and find user
        self.client.db.users.add_unique_column('email', lambda u: u.email)
        user = self.client.db.users.find_by_unique_column('email', 'alice@example.com')
        self.assertEqual(user.name, 'Alice')


if __name__ == '__main__':
    unittest.main() 