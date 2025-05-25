"""
Example: Enhanced Table Interface for SpacetimeDB Python SDK

Demonstrates TypeScript SDK-compatible table interface patterns.
"""

from dataclasses import dataclass
from typing import List, Optional
import time

from spacetimedb_sdk import ModernSpacetimeDBClient


# Example table row types
@dataclass
class User:
    id: int
    name: str
    email: str
    online: bool = False
    created_at: float = 0.0


@dataclass 
class Message:
    id: int
    sender_id: int
    text: str
    timestamp: float
    channel: str = "general"


@dataclass
class GameState:
    id: int
    player_id: int
    score: int
    level: int
    x_position: float
    y_position: float


def main():
    """Demonstrate enhanced table interface features."""
    
    # Example 1: Basic Table Access
    print("=== Example 1: Basic Table Access ===")
    
    # Create client with builder pattern
    client = (ModernSpacetimeDBClient.builder()
             .with_uri("ws://localhost:3000")
             .with_module_name("chat_app")
             .on_connect(lambda: print("Connected to SpacetimeDB!"))
             .build())
    
    # Register tables with metadata
    client.register_table("users", User, primary_key="id", unique_columns=["email"])
    client.register_table("messages", Message, primary_key="id")
    client.register_table("game_states", GameState, primary_key="id")
    
    # Access tables through db property
    users_table = client.db.users
    messages_table = client.db.messages
    game_states_table = client.db.game_states
    
    print(f"Registered tables: {client.db.list_tables()}")
    
    # Example 2: Row Callbacks - Insert
    print("\n=== Example 2: Insert Callbacks ===")
    
    def on_user_joined(ctx, user: User):
        print(f"🎉 New user joined: {user.name} ({user.email})")
        if user.online:
            print(f"   Status: Online")
    
    # Register insert callback
    insert_id = client.db.users.on_insert(on_user_joined)
    print(f"Registered insert callback with ID: {insert_id}")
    
    # Example 3: Row Callbacks - Delete
    print("\n=== Example 3: Delete Callbacks ===")
    
    def on_user_left(ctx, user: User):
        print(f"👋 User left: {user.name}")
    
    delete_id = client.db.users.on_delete(on_user_left)
    
    # Example 4: Row Callbacks - Update (requires primary key)
    print("\n=== Example 4: Update Callbacks ===")
    
    def on_user_updated(ctx, old_user: User, new_user: User):
        print(f"📝 User updated: {old_user.name}")
        if old_user.online != new_user.online:
            status = "came online" if new_user.online else "went offline"
            print(f"   Status change: {status}")
        if old_user.email != new_user.email:
            print(f"   Email changed: {old_user.email} → {new_user.email}")
    
    update_id = client.db.users.on_update(on_user_updated)
    
    # Example 5: Message Table Callbacks
    print("\n=== Example 5: Message Callbacks ===")
    
    def on_new_message(ctx, message: Message):
        # In real app, would look up sender name from users table
        print(f"💬 [{message.channel}] User#{message.sender_id}: {message.text}")
        
        # Check if this was from a reducer event
        if ctx and ctx.get('reducer_event'):
            reducer = ctx['reducer_event']
            print(f"   (via {reducer.reducer_name} reducer)")
    
    client.db.messages.on_insert(on_new_message)
    
    # Example 6: Game State Tracking
    print("\n=== Example 6: Game State Tracking ===")
    
    player_positions = {}  # Track last known positions
    
    def on_player_moved(ctx, old_state: GameState, new_state: GameState):
        player_id = new_state.player_id
        
        # Calculate movement
        dx = new_state.x_position - old_state.x_position
        dy = new_state.y_position - old_state.y_position
        distance = (dx**2 + dy**2)**0.5
        
        print(f"🎮 Player {player_id} moved {distance:.2f} units")
        
        # Check for level up
        if new_state.level > old_state.level:
            print(f"⭐ Player {player_id} leveled up to level {new_state.level}!")
            
        # Check for score change
        if new_state.score != old_state.score:
            score_change = new_state.score - old_state.score
            print(f"🏆 Player {player_id} scored {score_change:+d} points (total: {new_state.score})")
    
    client.db.game_states.on_update(on_player_moved)
    
    # Example 7: Querying Tables
    print("\n=== Example 7: Querying Tables ===")
    
    # Count rows
    user_count = client.db.users.count()
    message_count = client.db.messages.count()
    print(f"Users: {user_count}, Messages: {message_count}")
    
    # Iterate over all rows
    print("\nAll users:")
    for user in client.db.users.iter():
        status = "🟢" if user.online else "⚫"
        print(f"  {status} {user.name} ({user.email})")
    
    # Get all rows as list
    all_messages = client.db.messages.all()
    if all_messages:
        print(f"\nLast 5 messages:")
        for msg in all_messages[-5:]:
            print(f"  - {msg.text}")
    
    # Example 8: Finding by Unique Columns
    print("\n=== Example 8: Finding by Unique Columns ===")
    
    # Find user by email (registered as unique column)
    alice = client.db.users.find_by_unique_column('email', 'alice@example.com')
    if alice:
        print(f"Found user: {alice.name} (ID: {alice.id})")
    else:
        print("User not found")
    
    # Example 9: Removing Callbacks
    print("\n=== Example 9: Managing Callbacks ===")
    
    # Remove specific callback
    removed = client.db.users.remove_on_insert(insert_id)
    print(f"Removed insert callback: {removed}")
    
    # Example 10: Chained API Usage
    print("\n=== Example 10: Chained API Usage ===")
    
    # Chain multiple operations
    online_users = [
        user for user in client.db.users.iter() 
        if user.online
    ]
    print(f"Online users: {len(online_users)}")
    
    # Register callback and immediately use table
    client.db.messages.on_insert(
        lambda ctx, msg: print(f"Quick handler: {msg.text[:20]}...")
    )
    
    # Example 11: Complex Event Handling
    print("\n=== Example 11: Complex Event Handling ===")
    
    class ChatAnalytics:
        def __init__(self, client):
            self.client = client
            self.message_count = 0
            self.user_activity = {}
            
            # Register callbacks
            client.db.messages.on_insert(self.on_message)
            client.db.users.on_update(self.on_user_activity)
            
        def on_message(self, ctx, message: Message):
            self.message_count += 1
            sender_id = message.sender_id
            
            if sender_id not in self.user_activity:
                self.user_activity[sender_id] = {
                    'messages': 0,
                    'last_active': 0
                }
                
            self.user_activity[sender_id]['messages'] += 1
            self.user_activity[sender_id]['last_active'] = message.timestamp
            
            # Every 10 messages, print stats
            if self.message_count % 10 == 0:
                print(f"📊 Chat stats: {self.message_count} total messages")
                top_user = max(self.user_activity.items(), 
                              key=lambda x: x[1]['messages'])
                print(f"   Most active: User {top_user[0]} ({top_user[1]['messages']} messages)")
                
        def on_user_activity(self, ctx, old_user: User, new_user: User):
            if not old_user.online and new_user.online:
                # User came online
                activity = self.user_activity.get(new_user.id, {})
                messages = activity.get('messages', 0)
                print(f"📈 {new_user.name} is back! (sent {messages} messages today)")
    
    analytics = ChatAnalytics(client)
    
    # Example 12: Error Handling
    print("\n=== Example 12: Error Handling ===")
    
    try:
        # Try to register update callback on table without primary key
        test_table = client.db.get_table("test_table")
        if test_table and not test_table._primary_key_column:
            test_table.on_update(lambda ctx, old, new: None)
    except ValueError as e:
        print(f"Expected error: {e}")
    
    try:
        # Try to find by non-existent unique column
        client.db.users.find_by_unique_column('invalid_column', 'value')
    except ValueError as e:
        print(f"Expected error: {e}")
    
    print("\n=== Table Interface Demo Complete ===")
    
    # In a real application, you would connect and run the event loop
    # client.connect()
    # ... application runs ...
    # client.disconnect()


if __name__ == "__main__":
    main() 