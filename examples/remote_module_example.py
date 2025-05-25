"""
RemoteModule System Example for SpacetimeDB Python SDK.

Demonstrates how to use the module system with runtime type information,
metadata introspection, and enhanced DbContext integration.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

from spacetimedb_sdk import (
    # Core client
    SpacetimeDBClient,
    
    # RemoteModule system
    RemoteModule,
    GeneratedModule,
    DynamicModule,
    ModuleIntrospector,
    TableMetadata,
    ReducerMetadata,
    get_module_registry,
    register_module,
    
    # DbContext
    DbContext,
    DbView,
    Reducers,
    GeneratedDbView,
    GeneratedReducers,
    
    # Type system
    type_builder,
    FieldInfo,
    
    # Connection
    connection_builder
)


# ============================================================================
# PART 1: Define Data Models
# ============================================================================

@dataclass
class Player:
    """Player table row."""
    id: int
    username: str
    email: str
    level: int = 1
    experience: int = 0
    created_at: float = 0.0


@dataclass
class Item:
    """Item table row."""
    id: int
    player_id: int
    name: str
    item_type: str
    quantity: int = 1
    properties: Dict[str, Any] = None


@dataclass
class Guild:
    """Guild table row."""
    id: int
    name: str
    leader_id: int
    member_count: int = 1
    created_at: float = 0.0


@dataclass 
class ChatMessage:
    """Chat message table row."""
    id: int
    player_id: int
    guild_id: Optional[int]
    content: str
    timestamp: float


# ============================================================================
# PART 2: Create Generated Module (as if from code generation)
# ============================================================================

class GameModule(GeneratedModule):
    """
    Example of a generated module with full metadata.
    
    In practice, this would be auto-generated from SpacetimeDB schema.
    """
    
    def _initialize_metadata(self):
        """Initialize all table and reducer metadata."""
        
        # Register tables with full metadata
        self.register_table(
            table_name="players",
            row_type=Player,
            primary_key="id",
            unique_columns=["username", "email"],
            indexes=["level"],
            algebraic_type=type_builder.product([
                FieldInfo("id", type_builder.u64()),
                FieldInfo("username", type_builder.string()),
                FieldInfo("email", type_builder.string()),
                FieldInfo("level", type_builder.u32()),
                FieldInfo("experience", type_builder.u32()),
                FieldInfo("created_at", type_builder.f64())
            ], "Player")
        )
        
        self.register_table(
            table_name="items",
            row_type=Item,
            primary_key="id",
            indexes=["player_id", "item_type"]
        )
        
        self.register_table(
            table_name="guilds",
            row_type=Guild,
            primary_key="id",
            unique_columns=["name"]
        )
        
        self.register_table(
            table_name="chat_messages",
            row_type=ChatMessage,
            primary_key="id",
            indexes=["player_id", "guild_id", "timestamp"]
        )
        
        # Register reducers with full metadata
        self.register_reducer(
            reducer_name="create_player",
            args_type=dict,
            param_names=["username", "email"],
            param_types={"username": str, "email": str},
            return_type=Player,
            requires_auth=False
        )
        
        self.register_reducer(
            reducer_name="level_up",
            args_type=dict,
            param_names=["player_id"],
            param_types={"player_id": int},
            requires_auth=True
        )
        
        self.register_reducer(
            reducer_name="give_item",
            args_type=dict,
            param_names=["player_id", "item_name", "item_type", "quantity"],
            param_types={
                "player_id": int,
                "item_name": str,
                "item_type": str,
                "quantity": int
            }
        )
        
        self.register_reducer(
            reducer_name="create_guild",
            args_type=dict,
            param_names=["name", "leader_id"],
            param_types={"name": str, "leader_id": int}
        )
        
        self.register_reducer(
            reducer_name="send_message",
            args_type=dict,
            param_names=["content", "guild_id"],
            param_types={"content": str, "guild_id": Optional[int]}
        )


# ============================================================================
# PART 3: Create Typed DbView and Reducers (optional for type safety)
# ============================================================================

class GameDbView(GeneratedDbView):
    """Typed database view for the game module."""
    
    def __init__(self, client, module: Optional[RemoteModule] = None):
        # Register table types
        table_registry = {
            "players": Player,
            "items": Item,
            "guilds": Guild,
            "chat_messages": ChatMessage
        }
        super().__init__(client, table_registry, module)


class GameReducers(GeneratedReducers):
    """Typed reducers for the game module."""
    
    def __init__(self, client, module: Optional[RemoteModule] = None):
        # Initialize with empty reducer registry - we'll use dynamic access
        super().__init__(client, {}, module)
    
    async def create_player(self, username: str, email: str) -> str:
        """Create a new player."""
        # Access the reducer dynamically
        reducer = self._create_reducer_accessor("create_player")
        return await reducer(username=username, email=email)
    
    async def level_up(self, player_id: int) -> str:
        """Level up a player."""
        reducer = self._create_reducer_accessor("level_up")
        return await reducer(player_id=player_id)
    
    async def give_item(self, player_id: int, item_name: str, 
                       item_type: str, quantity: int = 1) -> str:
        """Give an item to a player."""
        reducer = self._create_reducer_accessor("give_item")
        return await reducer(
            player_id=player_id,
            item_name=item_name,
            item_type=item_type,
            quantity=quantity
        )
    
    async def create_guild(self, name: str, leader_id: int) -> str:
        """Create a new guild."""
        reducer = self._create_reducer_accessor("create_guild")
        return await reducer(name=name, leader_id=leader_id)
    
    async def send_message(self, content: str, guild_id: Optional[int] = None) -> str:
        """Send a chat message."""
        reducer = self._create_reducer_accessor("send_message")
        return await reducer(content=content, guild_id=guild_id)


# ============================================================================
# PART 4: Module Introspection and Runtime Discovery
# ============================================================================

def demonstrate_module_introspection():
    """Show module introspection capabilities."""
    print("Module Introspection Demo")
    print("=" * 50)
    
    # Create module
    module = GameModule("mmo_game")
    
    # Inspect module metadata
    print(f"\nModule: {module.module_name}")
    print(f"Tables: {len(module.tables)}")
    print(f"Reducers: {len(module.reducers)}")
    
    # Inspect tables
    print("\nTables:")
    for table_name, metadata in module.tables.items():
        print(f"\n  {table_name}:")
        print(f"    - Row type: {metadata.row_type.__name__}")
        print(f"    - Primary key: {metadata.primary_key}")
        print(f"    - Unique columns: {metadata.unique_columns}")
        print(f"    - Indexes: {metadata.indexes}")
        
        # Check algebraic type
        if metadata.algebraic_type:
            print(f"    - Has algebraic type with {len(metadata.algebraic_type.fields)} fields")
    
    # Inspect reducers
    print("\nReducers:")
    for reducer_name, metadata in module.reducers.items():
        print(f"\n  {reducer_name}:")
        print(f"    - Parameters: {metadata.param_names}")
        print(f"    - Parameter types: {metadata.param_types}")
        print(f"    - Return type: {metadata.return_type}")
        print(f"    - Requires auth: {metadata.requires_auth}")
    
    # Register in global registry
    register_module(module)
    
    # Show registry
    registry = get_module_registry()
    print(f"\nGlobal Registry: {registry.list_modules()}")


# ============================================================================
# PART 5: Dynamic Module Creation
# ============================================================================

def create_dynamic_module_example():
    """Create a module dynamically from metadata."""
    print("\n\nDynamic Module Creation")
    print("=" * 50)
    
    # Define module metadata (could come from API, config file, etc.)
    metadata = {
        "tables": [
            {
                "name": "achievements",
                "type": dict,  # Using dict as generic type
                "primary_key": "id",
                "unique_columns": ["name"]
            },
            {
                "name": "player_achievements",
                "type": dict,
                "primary_key": "id",
                "indexes": ["player_id", "achievement_id"]
            }
        ],
        "reducers": [
            {
                "name": "unlock_achievement",
                "params": ["player_id", "achievement_name"],
                "requires_auth": True
            }
        ]
    }
    
    # Create dynamic module
    dynamic_module = DynamicModule("achievements_module", metadata)
    
    print(f"\nCreated dynamic module: {dynamic_module.module_name}")
    print(f"Tables: {list(dynamic_module.tables.keys())}")
    print(f"Reducers: {list(dynamic_module.reducers.keys())}")
    
    return dynamic_module


# ============================================================================
# PART 6: Using Modules with DbContext
# ============================================================================

async def use_module_with_context():
    """Demonstrate using modules with DbContext."""
    print("\n\nUsing Module with DbContext")
    print("=" * 50)
    
    # Create module
    game_module = GameModule("mmo_game")
    
    # Create mock client (in real usage, connect to SpacetimeDB)
    client = SpacetimeDBClient()
    
    # Create context with module
    ctx: DbContext[GameDbView, GameReducers, Any] = client.get_context(
        db_view_class=GameDbView,
        reducers_class=GameReducers,
        module=game_module
    )
    
    print("\nAccessing tables with metadata:")
    
    # Access table metadata
    players_table = ctx.db.players
    print(f"\nPlayers table:")
    print(f"  - Table name: {players_table.name}")
    print(f"  - Primary key: {players_table.primary_key}")
    print(f"  - Row type: {players_table.row_type}")
    
    # Metadata is available
    if players_table.metadata:
        print(f"  - Unique columns: {players_table.metadata.unique_columns}")
        print(f"  - Has algebraic type: {players_table.metadata.algebraic_type is not None}")
    
    print("\n✅ Module system provides full runtime type information!")


# ============================================================================
# PART 7: Advanced Module Features
# ============================================================================

def demonstrate_advanced_features():
    """Show advanced module features."""
    print("\n\nAdvanced Module Features")
    print("=" * 50)
    
    # Extract metadata from existing classes
    print("\n1. Extracting metadata from classes:")
    player_metadata = ModuleIntrospector.extract_table_metadata(Player)
    print(f"   - Extracted table name: {player_metadata.table_name}")
    print(f"   - Row type: {player_metadata.row_type}")
    
    # Extract metadata from functions
    def example_reducer(player_id: int, amount: int = 100) -> bool:
        """Example reducer function."""
        return True
    
    reducer_metadata = ModuleIntrospector.extract_reducer_metadata(example_reducer)
    print(f"\n2. Extracting metadata from function:")
    print(f"   - Reducer name: {reducer_metadata.reducer_name}")
    print(f"   - Parameters: {reducer_metadata.param_names}")
    print(f"   - Parameter types: {reducer_metadata.param_types}")
    print(f"   - Return type: {reducer_metadata.return_type}")
    
    # Module versioning and compatibility
    print("\n3. Module compatibility:")
    module1 = GameModule("game_v1")
    module2 = GameModule("game_v2")
    
    # In a real system, you could compare schemas
    print(f"   - Module 1 tables: {len(module1.tables)}")
    print(f"   - Module 2 tables: {len(module2.tables)}")
    print("   - Schema comparison would check compatibility")


# ============================================================================
# MAIN: Run All Examples
# ============================================================================

async def main():
    """Run all RemoteModule examples."""
    print("SpacetimeDB RemoteModule System Examples")
    print("=" * 70)
    
    # 1. Module introspection
    demonstrate_module_introspection()
    
    # 2. Dynamic module creation
    dynamic_module = create_dynamic_module_example()
    
    # 3. Using modules with DbContext
    await use_module_with_context()
    
    # 4. Advanced features
    demonstrate_advanced_features()
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary: RemoteModule System Benefits")
    print("=" * 70)
    print("""
✅ Runtime Type Information: Full metadata for tables and reducers
✅ Type Safety: Typed DbView and Reducers classes with IDE support
✅ Dynamic Discovery: Introspect modules at runtime
✅ Schema Evolution: Track changes and ensure compatibility
✅ Code Generation Support: Base classes for generated modules
✅ Global Registry: Manage multiple modules in one application
✅ Integration: Seamless integration with DbContext and client

The RemoteModule system brings TypeScript SDK's type safety and
runtime introspection capabilities to the Python SDK!
    """)


if __name__ == "__main__":
    asyncio.run(main()) 