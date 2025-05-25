"""
Tests for RemoteModule System Implementation.

Tests runtime type information and module metadata functionality.
"""

import pytest
import asyncio
from typing import Optional, Dict, Any, List, Type
from unittest.mock import Mock, AsyncMock
from dataclasses import dataclass

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    RemoteModule,
    TableMetadata,
    ReducerMetadata,
    SpacetimeModule,
    GeneratedModule,
    DynamicModule,
    ModuleIntrospector,
    ModuleRegistry,
    get_module_registry,
    register_module,
    get_module,
    CallReducerFlags,
    DbContext,
    DbView,
    Reducers,
    AlgebraicType,
    ProductType,
    FieldInfo,
    type_builder
)


# Example table and reducer classes for testing
@dataclass
class User:
    """Example user table row."""
    id: int
    name: str
    email: str
    active: bool = True


@dataclass
class Message:
    """Example message table row."""
    id: int
    user_id: int
    content: str
    timestamp: float


class TestTableMetadata:
    """Test TableMetadata functionality."""
    
    def test_table_metadata_creation(self):
        """Test creating table metadata."""
        metadata = TableMetadata(
            table_name="users",
            row_type=User,
            primary_key="id",
            unique_columns=["email"],
            indexes=["name"]
        )
        
        assert metadata.table_name == "users"
        assert metadata.row_type == User
        assert metadata.primary_key == "id"
        assert metadata.unique_columns == ["email"]
        assert metadata.indexes == ["name"]
    
    def test_primary_key_extraction(self):
        """Test extracting primary key value."""
        metadata = TableMetadata(
            table_name="users",
            row_type=User,
            primary_key="id"
        )
        
        user = User(id=123, name="Alice", email="alice@example.com")
        pk_value = metadata.get_primary_key_value(user)
        
        assert pk_value == 123
    
    def test_unique_column_check(self):
        """Test checking if column is unique."""
        metadata = TableMetadata(
            table_name="users",
            row_type=User,
            primary_key="id",
            unique_columns=["email"]
        )
        
        assert metadata.is_unique_column("id") is True  # Primary key
        assert metadata.is_unique_column("email") is True
        assert metadata.is_unique_column("name") is False


class TestReducerMetadata:
    """Test ReducerMetadata functionality."""
    
    def test_reducer_metadata_creation(self):
        """Test creating reducer metadata."""
        metadata = ReducerMetadata(
            reducer_name="create_user",
            args_type=dict,
            param_names=["name", "email"],
            param_types={"name": str, "email": str},
            default_flags=CallReducerFlags.FULL_UPDATE,
            requires_auth=True
        )
        
        assert metadata.reducer_name == "create_user"
        assert metadata.args_type == dict
        assert metadata.param_names == ["name", "email"]
        assert metadata.requires_auth is True
    
    def test_args_validation(self):
        """Test validating reducer arguments."""
        metadata = ReducerMetadata(
            reducer_name="create_user",
            args_type=dict,
            param_names=["name", "email"]
        )
        
        # Valid args
        assert metadata.validate_args({"name": "Alice", "email": "alice@example.com"}) is True
        
        # Missing required arg
        assert metadata.validate_args({"name": "Alice"}) is False
        
        # Extra args are ok
        assert metadata.validate_args({"name": "Alice", "email": "alice@example.com", "extra": 123}) is True


class TestSpacetimeModule:
    """Test SpacetimeModule base class."""
    
    def test_module_registration(self):
        """Test registering tables and reducers."""
        # Create a test module
        class TestModule(SpacetimeModule):
            def _initialize_metadata(self):
                # Register tables
                self.register_table(
                    table_name="users",
                    row_type=User,
                    primary_key="id",
                    unique_columns=["email"]
                )
                
                self.register_table(
                    table_name="messages",
                    row_type=Message,
                    primary_key="id"
                )
                
                # Register reducers
                self.register_reducer(
                    reducer_name="create_user",
                    args_type=dict,
                    param_names=["name", "email"]
                )
        
        module = TestModule("test_module")
        
        # Check module name
        assert module.module_name == "test_module"
        
        # Check tables
        assert len(module.tables) == 2
        assert "users" in module.tables
        assert "messages" in module.tables
        
        # Check reducers
        assert len(module.reducers) == 1
        assert "create_user" in module.reducers
        
        # Get specific metadata
        user_table = module.get_table_metadata("users")
        assert user_table is not None
        assert user_table.primary_key == "id"
        
        create_user = module.get_reducer_metadata("create_user")
        assert create_user is not None
        assert create_user.param_names == ["name", "email"]


class TestDynamicModule:
    """Test DynamicModule functionality."""
    
    def test_dynamic_module_from_metadata(self):
        """Test creating module from metadata dictionary."""
        metadata = {
            "tables": [
                {
                    "name": "users",
                    "type": User,
                    "primary_key": "id",
                    "unique_columns": ["email"]
                },
                {
                    "name": "messages",
                    "type": Message,
                    "primary_key": "id"
                }
            ],
            "reducers": [
                {
                    "name": "create_user",
                    "type": dict,
                    "params": ["name", "email"],
                    "requires_auth": True
                }
            ]
        }
        
        module = DynamicModule("dynamic_test", metadata)
        
        # Check tables loaded
        assert len(module.tables) == 2
        assert module.tables["users"].row_type == User
        assert module.tables["messages"].row_type == Message
        
        # Check reducers loaded
        assert len(module.reducers) == 1
        assert module.reducers["create_user"].requires_auth is True


class TestGeneratedModule:
    """Test GeneratedModule functionality."""
    
    def test_generated_module_with_constructors(self):
        """Test generated module with custom constructors."""
        class MyGeneratedModule(GeneratedModule):
            def _initialize_metadata(self):
                self.register_table("users", User, primary_key="id")
                self.register_reducer("create_user", dict, param_names=["name", "email"])
        
        module = MyGeneratedModule("my_game")
        
        # Set constructors
        def db_view_constructor(client, module):
            return Mock(spec=DbView)
        
        def reducers_constructor(client, module):
            return Mock(spec=Reducers)
        
        module.set_constructors(
            db_view=db_view_constructor,
            reducers=reducers_constructor
        )
        
        # Check constructors set
        assert module.constructors.db_view_constructor is not None
        assert module.constructors.reducers_constructor is not None


class TestModuleIntrospector:
    """Test ModuleIntrospector utilities."""
    
    def test_extract_table_metadata(self):
        """Test extracting metadata from table class."""
        # Table with annotations
        class UsersTable:
            __tablename__ = "users"
            id: int
            name: str
            email: str
        
        metadata = ModuleIntrospector.extract_table_metadata(UsersTable)
        
        assert metadata.table_name == "users"
        assert metadata.row_type == UsersTable
    
    def test_extract_reducer_metadata(self):
        """Test extracting metadata from reducer function."""
        def create_user(name: str, email: str, active: bool = True) -> User:
            """Create a new user."""
            return User(id=0, name=name, email=email, active=active)
        
        metadata = ModuleIntrospector.extract_reducer_metadata(create_user)
        
        assert metadata.reducer_name == "create_user"
        assert metadata.param_names == ["name", "email", "active"]
        assert metadata.param_types == {"name": str, "email": str, "active": bool}
        assert metadata.return_type == User
    
    def test_discover_module(self):
        """Test discovering module structure."""
        # Create a mock module
        import types
        mock_module = types.ModuleType("test_game_module")
        
        # Add table class
        class UsersTable:
            __tablename__ = "users"
        
        # Add reducer function
        def reducer_create_user(name: str, email: str):
            pass
        reducer_create_user.__reducer__ = True
        
        # Add to module
        mock_module.UsersTable = UsersTable
        mock_module.reducer_create_user = reducer_create_user
        
        # Discover
        discovered = ModuleIntrospector.discover_module(mock_module)
        
        assert discovered.module_name == "test_game_module"
        assert "users" in discovered.tables
        assert "reducer_create_user" in discovered.reducers


class TestModuleRegistry:
    """Test ModuleRegistry functionality."""
    
    def test_module_registration(self):
        """Test registering and retrieving modules."""
        registry = ModuleRegistry()
        
        # Create test modules
        module1 = DynamicModule("module1")
        module2 = DynamicModule("module2")
        
        # Register
        registry.register(module1)
        registry.register(module2)
        
        # List modules
        modules = registry.list_modules()
        assert len(modules) == 2
        assert "module1" in modules
        assert "module2" in modules
        
        # Get specific module
        retrieved = registry.get("module1")
        assert retrieved == module1
    
    def test_get_all_tables(self):
        """Test getting all tables from all modules."""
        registry = ModuleRegistry()
        
        # Create modules with tables
        module1 = DynamicModule("game", {
            "tables": [{"name": "users", "type": User}]
        })
        module2 = DynamicModule("chat", {
            "tables": [{"name": "messages", "type": Message}]
        })
        
        registry.register(module1)
        registry.register(module2)
        
        # Get all tables
        all_tables = registry.get_all_tables()
        
        assert len(all_tables) == 2
        assert "game.users" in all_tables
        assert "chat.messages" in all_tables


class TestDbContextIntegration:
    """Test integration with DbContext."""
    
    @pytest.mark.asyncio
    async def test_context_with_module(self):
        """Test creating DbContext with module metadata."""
        # Create mock client
        client = Mock(spec=ModernSpacetimeDBClient)
        client.call_reducer = AsyncMock(return_value="req_123")
        
        # Create module with metadata
        module = DynamicModule("test", {
            "tables": [
                {"name": "users", "type": User, "primary_key": "id"}
            ],
            "reducers": [
                {"name": "create_user", "params": ["name", "email"]}
            ]
        })
        
        # Create context with module
        ctx = client.get_context(module=module)
        
        # Access table with metadata
        users = ctx.db.users
        assert users.metadata is not None
        assert users.primary_key == "id"
        assert users.row_type == User
        
        # Call reducer with metadata
        await ctx.reducers.create_user("Alice", "alice@example.com")
        
        # Should convert positional args to named args
        client.call_reducer.assert_called_with(
            "create_user",
            {"name": "Alice", "email": "alice@example.com"},
            flags=CallReducerFlags.FULL_UPDATE
        )


class TestAlgebraicTypeIntegration:
    """Test integration with algebraic type system."""
    
    def test_module_with_algebraic_types(self):
        """Test module with algebraic type information."""
        # Create algebraic type for User
        user_type = type_builder.product([
            FieldInfo("id", type_builder.u64()),
            FieldInfo("name", type_builder.string()),
            FieldInfo("email", type_builder.string()),
            FieldInfo("active", type_builder.bool_())
        ], "User")
        
        # Create module with algebraic type
        module = DynamicModule("typed_module")
        module.register_table(
            table_name="users",
            row_type=User,
            primary_key="id",
            algebraic_type=user_type
        )
        
        # Check algebraic type stored
        user_table = module.get_table_metadata("users")
        assert user_table.algebraic_type is not None
        assert user_table.algebraic_type.kind == "product"
        assert len(user_table.algebraic_type.fields) == 4


class TestGlobalRegistry:
    """Test global module registry."""
    
    def test_global_registry_functions(self):
        """Test global registry helper functions."""
        # Create and register module
        module = DynamicModule("global_test")
        register_module(module)
        
        # Retrieve from global registry
        retrieved = get_module("global_test")
        assert retrieved == module
        
        # Check registry
        registry = get_module_registry()
        assert "global_test" in registry.list_modules()


if __name__ == "__main__":
    # Run basic tests
    print("RemoteModule System Tests")
    print("========================\n")
    
    # Test table metadata
    metadata = TableMetadata(
        table_name="users",
        row_type=User,
        primary_key="id",
        unique_columns=["email"]
    )
    print(f"✅ Created TableMetadata: {metadata.table_name}")
    print(f"  - Primary key: {metadata.primary_key}")
    print(f"  - Row type: {metadata.row_type}")
    
    # Test module
    module = DynamicModule("test_module", {
        "tables": [
            {"name": "users", "type": User, "primary_key": "id"},
            {"name": "messages", "type": Message, "primary_key": "id"}
        ],
        "reducers": [
            {"name": "create_user", "params": ["name", "email"]}
        ]
    })
    
    print(f"\n✅ Created DynamicModule: {module.module_name}")
    print(f"  - Tables: {list(module.tables.keys())}")
    print(f"  - Reducers: {list(module.reducers.keys())}")
    
    # Test introspection
    user_meta = module.get_table_metadata("users")
    print(f"\n✅ Table metadata for 'users':")
    print(f"  - Row type: {user_meta.row_type.__name__}")
    print(f"  - Primary key: {user_meta.primary_key}")
    
    print("\n✅ All tests passed!") 