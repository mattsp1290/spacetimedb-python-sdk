"""
Tests for DbContext Interface Implementation.

Tests the structured database context interface for table and reducer access.
"""

import pytest
import asyncio
from typing import Optional, Dict, Any, List
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    DbContext,
    DbView,
    Reducers,
    SetReducerFlags,
    create_db_context,
    DbContextBuilder,
    GeneratedDbView,
    GeneratedReducers,
    TypedDbContext,
    CallReducerFlags,
    TableAccessor
)


class TestDbContext:
    """Test DbContext functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing."""
        client = Mock(spec=ModernSpacetimeDBClient)
        client.connected = True
        client.call_reducer = AsyncMock(return_value="request_123")
        return client
    
    def test_basic_context_creation(self, mock_client):
        """Test basic DbContext creation."""
        ctx = create_db_context(mock_client)
        
        assert isinstance(ctx, DbContext)
        assert isinstance(ctx.db, DbView)
        assert isinstance(ctx.reducers, Reducers)
        assert isinstance(ctx.setReducerFlags, SetReducerFlags)
        assert ctx.isActive is True
    
    def test_context_with_custom_classes(self, mock_client):
        """Test DbContext with custom classes."""
        # Custom classes
        class MyDbView(DbView):
            pass
        
        class MyReducers(Reducers):
            pass
        
        class MySetReducerFlags(SetReducerFlags):
            pass
        
        ctx = create_db_context(
            mock_client,
            db_view_class=MyDbView,
            reducers_class=MyReducers,
            set_reducer_flags_class=MySetReducerFlags
        )
        
        assert isinstance(ctx.db, MyDbView)
        assert isinstance(ctx.reducers, MyReducers)
        assert isinstance(ctx.setReducerFlags, MySetReducerFlags)
    
    def test_db_view_table_access(self, mock_client):
        """Test table access through DbView."""
        ctx = create_db_context(mock_client)
        
        # Access tables dynamically
        users_table = ctx.db.users
        messages_table = ctx.db.messages
        
        assert users_table.name == "users"
        assert messages_table.name == "messages"
        
        # Accessing same table returns same instance
        assert ctx.db.users is users_table
    
    @pytest.mark.asyncio
    async def test_reducer_access(self, mock_client):
        """Test reducer access and calls."""
        ctx = create_db_context(mock_client)
        
        # Call reducer through context
        result = await ctx.reducers.create_user({"name": "Alice", "email": "alice@example.com"})
        
        # Verify client was called correctly
        mock_client.call_reducer.assert_called_once_with(
            "create_user",
            {"name": "Alice", "email": "alice@example.com"}
        )
        assert result == "request_123"
    
    @pytest.mark.asyncio
    async def test_reducer_with_positional_args(self, mock_client):
        """Test reducer calls with positional arguments."""
        ctx = create_db_context(mock_client)
        
        # Call with positional args
        await ctx.reducers.send_message("Hello", 123)
        
        # Should convert to dict
        mock_client.call_reducer.assert_called_with(
            "send_message",
            {"args": ("Hello", 123)}
        )
    
    def test_set_reducer_flags(self, mock_client):
        """Test reducer flags management."""
        ctx = create_db_context(mock_client)
        
        # Default flags
        assert ctx.setReducerFlags.flags == CallReducerFlags.FULL_UPDATE
        
        # Set new flags
        ctx.setReducerFlags.set_flags(CallReducerFlags.NO_SUCCESS_NOTIFY)
        assert ctx.setReducerFlags.flags == CallReducerFlags.NO_SUCCESS_NOTIFY
    
    def test_is_active_property(self, mock_client):
        """Test isActive property reflects connection state."""
        ctx = create_db_context(mock_client)
        
        # Initially connected
        assert ctx.isActive is True
        
        # Disconnect
        mock_client.connected = False
        assert ctx.isActive is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self, mock_client):
        """Test disconnecting through context."""
        mock_client.disconnect = AsyncMock()
        ctx = create_db_context(mock_client)
        
        await ctx.disconnect()
        
        mock_client.disconnect.assert_called_once()
    
    def test_connection_callbacks(self, mock_client):
        """Test registering connection callbacks."""
        ctx = create_db_context(mock_client)
        
        on_connect = Mock()
        on_disconnect = Mock()
        
        ctx.on_connect(on_connect)
        ctx.on_disconnect(on_disconnect)
        
        assert mock_client.on_connect == on_connect
        assert mock_client.on_disconnect == on_disconnect
    
    def test_context_builder(self, mock_client):
        """Test DbContextBuilder fluent API."""
        builder = DbContextBuilder()
        
        # Custom classes
        class MyDbView(DbView):
            pass
        
        class MyReducers(Reducers):
            pass
        
        ctx = (builder
               .with_client(mock_client)
               .with_db_view(MyDbView)
               .with_reducers(MyReducers)
               .build())
        
        assert isinstance(ctx.db, MyDbView)
        assert isinstance(ctx.reducers, MyReducers)
    
    def test_context_builder_validation(self):
        """Test context builder validates client."""
        builder = DbContextBuilder()
        
        # Should fail without client
        with pytest.raises(ValueError, match="Client is required"):
            builder.build()


class TestTableAccessor:
    """Test TableAccessor functionality."""
    
    @pytest.fixture
    def table_accessor(self):
        """Create a table accessor for testing."""
        mock_client = Mock(spec=ModernSpacetimeDBClient)
        return TableAccessor(mock_client, "users")
    
    def test_table_name(self, table_accessor):
        """Test table name property."""
        assert table_accessor.name == "users"
    
    def test_iter_method(self, table_accessor):
        """Test iter method."""
        # Currently returns empty iterator
        items = list(table_accessor.iter())
        assert items == []
    
    def test_count_method(self, table_accessor):
        """Test count method."""
        # Currently returns 0
        assert table_accessor.count() == 0
    
    def test_all_method(self, table_accessor):
        """Test all method."""
        # Currently returns empty list
        assert table_accessor.all() == []
    
    def test_find_by_unique_column(self, table_accessor):
        """Test find by unique column."""
        # Currently returns None
        result = table_accessor.find_by_unique_column("id", 123)
        assert result is None
    
    def test_event_callbacks(self, table_accessor):
        """Test event callback registration."""
        on_insert = Mock()
        on_update = Mock()
        on_delete = Mock()
        
        insert_id = table_accessor.on_insert(on_insert)
        update_id = table_accessor.on_update(on_update)
        delete_id = table_accessor.on_delete(on_delete)
        
        assert insert_id == "users_on_insert"
        assert update_id == "users_on_update"
        assert delete_id == "users_on_delete"


class TestGeneratedIntegration:
    """Test integration with generated code."""
    
    def test_generated_db_view(self, mock_client):
        """Test GeneratedDbView with typed tables."""
        # Mock table classes
        class UsersTable:
            def __init__(self, client):
                self.client = client
                self.name = "users"
            
            def find_by_id(self, id: int):
                return {"id": id, "name": "User"}
        
        class MessagesTable:
            def __init__(self, client):
                self.client = client
                self.name = "messages"
        
        # Registry
        table_registry = {
            "users": UsersTable,
            "messages": MessagesTable
        }
        
        db_view = GeneratedDbView(mock_client, table_registry)
        
        # Access typed tables
        users = db_view.users
        assert isinstance(users, UsersTable)
        assert users.find_by_id(123) == {"id": 123, "name": "User"}
        
        # Access unregistered table falls back to default
        other = db_view.other_table
        assert isinstance(other, TableAccessor)
    
    @pytest.mark.asyncio
    async def test_generated_reducers(self, mock_client):
        """Test GeneratedReducers with typed reducers."""
        # Mock reducer classes
        class CreateUserReducer:
            def __init__(self, client):
                self.client = client
            
            async def __call__(self, name: str, email: str):
                return await self.client.call_reducer(
                    "create_user",
                    {"name": name, "email": email}
                )
        
        # Registry
        reducer_registry = {
            "create_user": CreateUserReducer
        }
        
        reducers = GeneratedReducers(mock_client, reducer_registry)
        
        # Access typed reducer
        create_user = reducers.create_user
        assert isinstance(create_user, CreateUserReducer)
        
        # Call typed reducer
        result = await create_user("Alice", "alice@example.com")
        mock_client.call_reducer.assert_called_with(
            "create_user",
            {"name": "Alice", "email": "alice@example.com"}
        )


class TestTypedDbContext:
    """Test TypedDbContext with runtime checking."""
    
    def test_typed_context_creation(self, mock_client):
        """Test creating typed context."""
        ctx = TypedDbContext(
            mock_client,
            DbView,
            Reducers,
            SetReducerFlags,
            enable_type_checking=True
        )
        
        assert isinstance(ctx, TypedDbContext)
        assert ctx._enable_type_checking is True
    
    def test_type_checking_disabled(self, mock_client):
        """Test with type checking disabled."""
        ctx = TypedDbContext(
            mock_client,
            DbView,
            Reducers,
            SetReducerFlags,
            enable_type_checking=False
        )
        
        assert ctx._enable_type_checking is False


class TestConnectionBuilderIntegration:
    """Test DbContext integration with connection builder."""
    
    @patch('spacetimedb_sdk.modern_client.ModernSpacetimeDBClient')
    def test_build_with_context(self, MockClient):
        """Test building client with context."""
        from spacetimedb_sdk import ModernSpacetimeDBClient
        
        # Mock client instance
        mock_instance = Mock()
        mock_instance.get_context.return_value = Mock(spec=DbContext)
        MockClient.return_value = mock_instance
        
        # Build with context
        client, ctx = (ModernSpacetimeDBClient.builder()
                      .with_uri("ws://localhost:3000")
                      .with_module_name("test_module")
                      .with_context()
                      .build_with_context())
        
        assert client == mock_instance
        assert ctx == mock_instance.get_context.return_value
        mock_instance.get_context.assert_called_once()
    
    @patch('spacetimedb_sdk.modern_client.ModernSpacetimeDBClient')
    def test_connect_with_context(self, MockClient):
        """Test connecting with context."""
        from spacetimedb_sdk import ModernSpacetimeDBClient
        
        # Mock client instance
        mock_instance = Mock()
        mock_instance.get_context.return_value = Mock(spec=DbContext)
        mock_instance.connect = Mock()
        MockClient.return_value = mock_instance
        
        # Connect with context
        client, ctx = (ModernSpacetimeDBClient.builder()
                      .with_uri("ws://localhost:3000")
                      .with_module_name("test_module")
                      .with_token("test_token")
                      .connect_with_context())
        
        assert client == mock_instance
        assert ctx == mock_instance.get_context.return_value
        mock_instance.connect.assert_called_once()


@pytest.mark.asyncio
async def test_end_to_end_example():
    """Test end-to-end usage example."""
    # This is a documentation test showing the API
    
    # Mock client
    client = Mock(spec=ModernSpacetimeDBClient)
    client.connected = True
    client.call_reducer = AsyncMock(return_value="req_123")
    
    # Get context
    ctx = client.get_context()
    
    # Access tables
    users = ctx.db.users
    messages = ctx.db.messages
    
    # Call reducers
    await ctx.reducers.create_user({"name": "Alice", "email": "alice@example.com"})
    await ctx.reducers.send_message({"content": "Hello world!", "user_id": 123})
    
    # Check connection
    if ctx.isActive:
        print("Connected to SpacetimeDB!")
    
    # Disconnect
    client.disconnect = AsyncMock()
    await ctx.disconnect()


if __name__ == "__main__":
    # Run basic tests
    print("DbContext Interface Tests")
    print("========================\n")
    
    # Test basic creation
    from unittest.mock import Mock
    mock_client = Mock()
    mock_client.connected = True
    
    ctx = create_db_context(mock_client)
    print(f"✅ Created DbContext: {ctx}")
    print(f"✅ DbView: {ctx.db}")
    print(f"✅ Reducers: {ctx.reducers}")
    print(f"✅ IsActive: {ctx.isActive}")
    
    # Test table access
    users = ctx.db.users
    messages = ctx.db.messages
    print(f"\n✅ Accessed tables:")
    print(f"  - users: {users.name}")
    print(f"  - messages: {messages.name}")
    
    print("\n✅ All tests passed!") 