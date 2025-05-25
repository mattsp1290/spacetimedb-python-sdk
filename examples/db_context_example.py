"""
Example: DbContext Interface for SpacetimeDB Python SDK

Demonstrates structured access to database tables and reducers
using the DbContext interface, matching TypeScript SDK patterns.
"""

import asyncio
from typing import Optional, List, Dict, Any

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    DbContext,
    DbView,
    Reducers,
    SetReducerFlags,
    CallReducerFlags,
    GeneratedDbView,
    GeneratedReducers,
    configure_default_logging,
    get_logger
)


# Configure logging
configure_default_logging(debug=False)
logger = get_logger()


# Example: Custom typed database view
class GameDbView(DbView):
    """Typed database view for a game application."""
    
    @property
    def players(self):
        """Access the players table."""
        return self._get_typed_table("players", PlayersTable)
    
    @property
    def messages(self):
        """Access the messages table."""
        return self._get_typed_table("messages", MessagesTable)
    
    @property
    def game_sessions(self):
        """Access the game_sessions table."""
        return self._get_typed_table("game_sessions", GameSessionsTable)
    
    def _get_typed_table(self, name: str, table_class: type):
        """Get a typed table instance."""
        if name not in self._tables:
            self._tables[name] = table_class(self._client, name)
        return self._tables[name]


# Example: Typed table accessors
class PlayersTable:
    """Typed accessor for the players table."""
    
    def __init__(self, client, name: str):
        self.client = client
        self.name = name
        self._cache: Dict[int, Dict[str, Any]] = {}
    
    def find_by_id(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Find a player by ID."""
        return self._cache.get(player_id)
    
    def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a player by name."""
        for player in self._cache.values():
            if player.get("name") == name:
                return player
        return None
    
    def get_online_players(self) -> List[Dict[str, Any]]:
        """Get all online players."""
        return [p for p in self._cache.values() if p.get("online", False)]
    
    def on_player_join(self, callback):
        """Register callback for when a player joins."""
        # Would connect to actual event system
        logger.info(f"Registered on_player_join callback for {self.name}")


class MessagesTable:
    """Typed accessor for the messages table."""
    
    def __init__(self, client, name: str):
        self.client = client
        self.name = name
        self._messages: List[Dict[str, Any]] = []
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages."""
        return self._messages[-limit:]
    
    def get_by_player(self, player_id: int) -> List[Dict[str, Any]]:
        """Get messages from a specific player."""
        return [m for m in self._messages if m.get("player_id") == player_id]


class GameSessionsTable:
    """Typed accessor for game sessions."""
    
    def __init__(self, client, name: str):
        self.client = client
        self.name = name
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active game sessions."""
        return [s for s in self._sessions.values() if s.get("active", False)]
    
    def find_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Find a session by ID."""
        return self._sessions.get(session_id)


# Example: Custom typed reducers
class GameReducers(Reducers):
    """Typed reducers for game operations."""
    
    async def create_player(self, name: str, class_type: str) -> str:
        """Create a new player."""
        return await self._client.call_reducer("create_player", {
            "name": name,
            "class_type": class_type,
            "starting_level": 1,
            "starting_gold": 100
        })
    
    async def send_chat_message(self, player_id: int, content: str, channel: str = "global") -> str:
        """Send a chat message."""
        return await self._client.call_reducer("send_chat_message", {
            "player_id": player_id,
            "content": content,
            "channel": channel,
            "timestamp": None  # Server will set
        })
    
    async def start_game_session(self, host_player_id: int, game_mode: str, max_players: int = 4) -> str:
        """Start a new game session."""
        return await self._client.call_reducer("start_game_session", {
            "host_player_id": host_player_id,
            "game_mode": game_mode,
            "max_players": max_players,
            "settings": {
                "difficulty": "normal",
                "map": "default"
            }
        })
    
    async def join_game_session(self, player_id: int, session_id: str) -> str:
        """Join an existing game session."""
        return await self._client.call_reducer("join_game_session", {
            "player_id": player_id,
            "session_id": session_id
        })
    
    async def player_action(self, player_id: int, action_type: str, data: Dict[str, Any]) -> str:
        """Execute a player action."""
        return await self._client.call_reducer("player_action", {
            "player_id": player_id,
            "action_type": action_type,
            "action_data": data
        })


# Example: Custom SetReducerFlags
class GameSetReducerFlags(SetReducerFlags):
    """Custom reducer flags for game operations."""
    
    def use_optimistic_updates(self):
        """Enable optimistic updates for better UX."""
        self.set_flags(CallReducerFlags.NO_SUCCESS_NOTIFY)
        logger.info("Optimistic updates enabled")
    
    def use_full_updates(self):
        """Use full updates for consistency."""
        self.set_flags(CallReducerFlags.FULL_UPDATE)
        logger.info("Full updates enabled")


class DbContextExample:
    """Examples demonstrating DbContext usage."""
    
    def __init__(self):
        self.client: Optional[ModernSpacetimeDBClient] = None
        self.ctx: Optional[DbContext] = None
    
    async def example_1_basic_usage(self):
        """Example 1: Basic DbContext usage."""
        print("\n=== Example 1: Basic DbContext Usage ===")
        
        # Create client
        self.client = (ModernSpacetimeDBClient.builder()
                      .with_uri("ws://localhost:3000")
                      .with_module_name("game_db")
                      .build())
        
        # Get basic context
        ctx = self.client.get_context()
        
        print(f"✅ Created DbContext")
        print(f"  - Active: {ctx.isActive}")
        print(f"  - Reducer Flags: {ctx.setReducerFlags.flags}")
        
        # Access tables dynamically
        users = ctx.db.users
        messages = ctx.db.messages
        
        print(f"\n✅ Accessed tables:")
        print(f"  - users: {users.name}")
        print(f"  - messages: {messages.name}")
        
        # Call reducers
        print("\n✅ Calling reducers:")
        try:
            # Would need actual connection to work
            # result = await ctx.reducers.create_user({"name": "Alice"})
            print("  - create_user (would call server)")
            print("  - send_message (would call server)")
        except Exception as e:
            print(f"  - Not connected: {e}")
    
    async def example_2_typed_context(self):
        """Example 2: Typed DbContext with custom classes."""
        print("\n=== Example 2: Typed DbContext ===")
        
        # Create client with context
        self.client, self.ctx = (ModernSpacetimeDBClient.builder()
                                .with_uri("ws://localhost:3000")
                                .with_module_name("game_db")
                                .with_context(
                                    db_view_class=GameDbView,
                                    reducers_class=GameReducers,
                                    set_reducer_flags_class=GameSetReducerFlags
                                )
                                .build_with_context())
        
        print("✅ Created typed DbContext")
        
        # Access typed tables
        players = self.ctx.db.players
        messages = self.ctx.db.messages
        sessions = self.ctx.db.game_sessions
        
        print(f"\n✅ Typed table access:")
        print(f"  - players: {type(players).__name__}")
        print(f"  - messages: {type(messages).__name__}")
        print(f"  - sessions: {type(sessions).__name__}")
        
        # Typed methods available
        print("\n✅ Typed table methods:")
        print(f"  - players.find_by_id()")
        print(f"  - players.get_online_players()")
        print(f"  - messages.get_recent()")
        print(f"  - sessions.get_active_sessions()")
    
    async def example_3_game_flow(self):
        """Example 3: Complete game flow with DbContext."""
        print("\n=== Example 3: Game Flow with DbContext ===")
        
        # Assume we have a connected typed context
        if not self.ctx:
            print("❌ No context available")
            return
        
        print("Simulating game flow...")
        
        # 1. Create players
        print("\n1. Creating players:")
        try:
            # These would actually call the server
            # player1_id = await self.ctx.reducers.create_player("Alice", "warrior")
            # player2_id = await self.ctx.reducers.create_player("Bob", "mage")
            print("  - Created Alice (warrior)")
            print("  - Created Bob (mage)")
        except:
            print("  - (Simulated - not connected)")
        
        # 2. Start game session
        print("\n2. Starting game session:")
        try:
            # session_id = await self.ctx.reducers.start_game_session(1, "coop", 4)
            print("  - Started coop session (max 4 players)")
        except:
            print("  - (Simulated - not connected)")
        
        # 3. Join session
        print("\n3. Players joining session:")
        try:
            # await self.ctx.reducers.join_game_session(2, session_id)
            print("  - Bob joined the session")
        except:
            print("  - (Simulated - not connected)")
        
        # 4. Send messages
        print("\n4. Chat messages:")
        try:
            # await self.ctx.reducers.send_chat_message(1, "Ready to start?")
            # await self.ctx.reducers.send_chat_message(2, "Let's go!")
            print("  - Alice: Ready to start?")
            print("  - Bob: Let's go!")
        except:
            print("  - (Simulated - not connected)")
        
        # 5. Game actions
        print("\n5. Game actions:")
        try:
            # await self.ctx.reducers.player_action(1, "move", {"x": 10, "y": 20})
            # await self.ctx.reducers.player_action(2, "cast_spell", {"spell": "fireball", "target": "enemy1"})
            print("  - Alice moved to (10, 20)")
            print("  - Bob cast fireball on enemy1")
        except:
            print("  - (Simulated - not connected)")
    
    async def example_4_reducer_flags(self):
        """Example 4: Managing reducer flags."""
        print("\n=== Example 4: Reducer Flags Management ===")
        
        if not self.ctx:
            print("❌ No context available")
            return
        
        # Check current flags
        print(f"Current flags: {self.ctx.setReducerFlags.flags}")
        
        # Use optimistic updates for UI actions
        if isinstance(self.ctx.setReducerFlags, GameSetReducerFlags):
            self.ctx.setReducerFlags.use_optimistic_updates()
            print("✅ Switched to optimistic updates")
            
            # Later switch back for critical operations
            self.ctx.setReducerFlags.use_full_updates()
            print("✅ Switched back to full updates")
        else:
            # Basic flag management
            self.ctx.setReducerFlags.set_flags(CallReducerFlags.NO_SUCCESS_NOTIFY)
            print(f"✅ Set flags to: {self.ctx.setReducerFlags.flags}")
    
    async def example_5_event_handling(self):
        """Example 5: Event handling with typed tables."""
        print("\n=== Example 5: Event Handling ===")
        
        if not self.ctx:
            print("❌ No context available")
            return
        
        # Register event handlers on typed tables
        if hasattr(self.ctx.db, 'players'):
            players = self.ctx.db.players
            
            # Register callbacks
            def on_player_join(player):
                print(f"  🎮 Player joined: {player.get('name')}")
            
            players.on_player_join(on_player_join)
            print("✅ Registered player join handler")
        
        # Connection lifecycle
        def on_connect():
            print("  🔌 Connected to game server!")
        
        def on_disconnect():
            print("  ⚡ Disconnected from game server!")
        
        self.ctx.on_connect(on_connect)
        self.ctx.on_disconnect(on_disconnect)
        print("✅ Registered connection handlers")
    
    async def example_6_context_builder(self):
        """Example 6: Using DbContextBuilder directly."""
        print("\n=== Example 6: DbContextBuilder ===")
        
        # Create a mock client for demonstration
        from unittest.mock import Mock
        mock_client = Mock()
        mock_client.connected = True
        
        # Build context with builder
        from spacetimedb_sdk import DbContextBuilder
        
        ctx = (DbContextBuilder()
               .with_client(mock_client)
               .with_db_view(GameDbView)
               .with_reducers(GameReducers)
               .with_set_reducer_flags(GameSetReducerFlags)
               .build())
        
        print("✅ Built context with DbContextBuilder")
        print(f"  - DbView type: {type(ctx.db).__name__}")
        print(f"  - Reducers type: {type(ctx.reducers).__name__}")
        print(f"  - SetReducerFlags type: {type(ctx.setReducerFlags).__name__}")
    
    async def cleanup(self):
        """Clean up resources."""
        if self.ctx and self.ctx.isActive:
            await self.ctx.disconnect()
        
        if self.client:
            self.client.shutdown()


async def main():
    """Run all DbContext examples."""
    print("SpacetimeDB Python SDK - DbContext Examples")
    print("==========================================")
    
    example = DbContextExample()
    
    try:
        # Run examples
        await example.example_1_basic_usage()
        await example.example_2_typed_context()
        await example.example_3_game_flow()
        await example.example_4_reducer_flags()
        await example.example_5_event_handling()
        await example.example_6_context_builder()
        
        print("\n✅ All examples completed!")
        
        print("\nKey Takeaways:")
        print("- DbContext provides structured access to tables and reducers")
        print("- Use ctx.db.table_name for table access")
        print("- Use ctx.reducers.reducer_name() for reducer calls")
        print("- Custom classes enable type-safe operations")
        print("- Matches TypeScript SDK patterns for consistency")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await example.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 