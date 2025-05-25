"""
Comprehensive example demonstrating SpacetimeDB specialized data structures.

This example shows how to use all the data structures including OperationsMap,
specialized collections, concurrent access patterns, and performance monitoring.
"""

import asyncio
import threading
import time
import random
from typing import Any, Dict, List

# Import SpacetimeDB data structures
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.spacetimedb_sdk.data_structures import (
    OperationsMap, IdentityCollection, ConnectionIdCollection, QueryIdCollection,
    ConcurrentSet, LRUCache, CollectionManager, CollectionStrategy,
    CollectionMetrics, Equalable, collection_manager,
    create_operations_map, create_identity_collection, create_connection_id_collection,
    create_query_id_collection, create_concurrent_set, create_lru_cache,
    get_collection, get_all_metrics
)
from src.spacetimedb_sdk.protocol import Identity, ConnectionId, QueryId
from src.spacetimedb_sdk.time_utils import EnhancedTimestamp


class GamePlayer:
    """Example game player object with custom equality."""
    
    def __init__(self, player_id: int, name: str, level: int):
        self.player_id = player_id
        self.name = name
        self.level = level
        self.last_seen = EnhancedTimestamp.now()
    
    def is_equal(self, other: Any) -> bool:
        """Custom equality based on player_id only."""
        if isinstance(other, GamePlayer):
            return self.player_id == other.player_id
        return False
    
    def __str__(self):
        return f"Player({self.player_id}, {self.name}, level {self.level})"
    
    def __repr__(self):
        return self.__str__()


def demonstrate_operations_map():
    """Demonstrate OperationsMap functionality."""
    print("=== OperationsMap Demonstration ===")
    
    # Create operations map with custom equality
    player_map = OperationsMap[GamePlayer, Dict[str, Any]]()
    
    # Create some players
    player1 = GamePlayer(1, "Alice", 10)
    player2 = GamePlayer(1, "Alice_Updated", 15)  # Same ID, different data
    player3 = GamePlayer(2, "Bob", 8)
    
    # Store player data
    player_map.set(player1, {"score": 1000, "guild": "Warriors"})
    player_map.set(player3, {"score": 800, "guild": "Mages"})
    
    print(f"Map size: {player_map.size()}")
    print(f"Player 1 data: {player_map.get(player1)}")
    
    # Update with player2 (same ID as player1)
    player_map.set(player2, {"score": 1500, "guild": "Champions"})
    print(f"Map size after update: {player_map.size()}")  # Should still be 2
    print(f"Player 1 data after update: {player_map.get(player1)}")  # Should be updated
    
    # Test different strategies
    print("\n--- Testing Different Strategies ---")
    
    # Ordered map maintains insertion order
    ordered_map = OperationsMap[str, int](CollectionStrategy.ORDERED_MAP)
    for i in range(5):
        ordered_map.set(f"key_{i}", i)
    
    print("Ordered map keys:", list(ordered_map.keys()))
    
    # Get metrics
    metrics = player_map.get_metrics()
    print(f"\nMetrics: {metrics.operation_count} operations, avg time: {metrics.average_time:.6f}s")


def demonstrate_identity_collection():
    """Demonstrate IdentityCollection functionality."""
    print("\n=== IdentityCollection Demonstration ===")
    
    # Create identity collection
    identities = create_identity_collection("game_identities")
    
    # Create some identities
    identity1 = Identity(b"player1_identity_32_chars_long!")
    identity2 = Identity(b"player2_identity_32_chars_long!")
    identity3 = Identity(b"player3_identity_32_chars_long!")
    
    # Add identities
    print(f"Added identity1: {identities.add(identity1)}")
    print(f"Added identity2: {identities.add(identity2)}")
    print(f"Added identity1 again: {identities.add(identity1)}")  # Should be False
    
    print(f"Collection size: {identities.size()}")
    print(f"Contains identity1: {identity1 in identities}")
    print(f"Contains identity3: {identity3 in identities}")
    
    # Find by hex string
    hex_str = identity1.to_hex()
    found = identities.find_by_hex(hex_str)
    print(f"Found by hex: {found == identity1}")
    
    # List all identities
    print(f"All identities: {len(identities.to_list())} items")


def demonstrate_connection_collection():
    """Demonstrate ConnectionIdCollection functionality."""
    print("\n=== ConnectionIdCollection Demonstration ===")
    
    connections = ConnectionIdCollection()
    
    # Create connection IDs with metadata
    conn1 = ConnectionId(b"connection_1_data_bytes")
    conn2 = ConnectionId(b"connection_2_data_bytes")
    conn3 = ConnectionId(b"connection_3_data_bytes")
    
    metadata1 = {"client": "web", "version": "1.0", "region": "us-east"}
    metadata2 = {"client": "mobile", "version": "2.0", "region": "eu-west"}
    metadata3 = {"client": "desktop", "version": "1.5", "region": "ap-south"}
    
    # Add connections
    connections.add(conn1, metadata1)
    connections.add(conn2, metadata2)
    connections.add(conn3, metadata3)
    
    print(f"Connection collection size: {connections.size()}")
    
    # Test metadata operations
    retrieved_metadata = connections.get_metadata(conn1)
    print(f"Connection 1 metadata: {retrieved_metadata}")
    
    # Update metadata
    updated_metadata = retrieved_metadata.copy()
    updated_metadata.update({"version": "1.2", "updated": True})
    connections.set_metadata(conn1, updated_metadata)
    updated_metadata = connections.get_metadata(conn1)
    print(f"Updated metadata: {updated_metadata}")
    
    # Find by hex
    found_conn = connections.find_by_hex(conn2.to_hex())
    print(f"Found connection by hex: {found_conn.to_hex() if found_conn else None}")


def demonstrate_query_collection():
    """Demonstrate QueryIdCollection functionality."""
    print("\n=== QueryIdCollection Demonstration ===")
    
    # Create query collection
    queries = create_query_id_collection("game_queries")
    
    # Add queries with metadata
    query1 = QueryId(2001)
    query2 = QueryId(2002)
    query3 = QueryId(2003)
    
    queries.add(query1, {"sql": "SELECT * FROM players", "timeout": 30})
    queries.add(query2, {"sql": "SELECT * FROM guilds", "timeout": 60})
    
    # Simulate old query by manually setting timestamp
    old_timestamp = time.time() - 5.0  # 5 seconds ago
    queries._query_timestamps[2001] = old_timestamp
    
    queries.add(query3, {"sql": "SELECT * FROM items", "timeout": 45})
    
    print(f"Query collection size: {queries.size()}")
    
    # Find old queries
    old_queries = queries.find_by_age(3.0)  # Older than 3 seconds
    print(f"Old queries found: {len(old_queries)}")
    
    # Cleanup old queries
    removed_count = queries.cleanup_old_queries(3.0)
    print(f"Removed {removed_count} old queries")
    print(f"Collection size after cleanup: {queries.size()}")


def demonstrate_concurrent_set():
    """Demonstrate ConcurrentSet functionality."""
    print("\n=== ConcurrentSet Demonstration ===")
    
    # Create concurrent sets
    active_players = create_concurrent_set("active_players")
    guild_members = create_concurrent_set("guild_members")
    
    # Add some players
    players = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
    for player in players:
        active_players.add(player)
    
    # Add guild members (some overlap)
    guild_players = ["Bob", "Charlie", "Frank", "Grace"]
    for player in guild_players:
        guild_members.add(player)
    
    print(f"Active players: {active_players.size()}")
    print(f"Guild members: {guild_members.size()}")
    
    # Set operations
    union_set = active_players.union(guild_members)
    intersection_set = active_players.intersection(guild_members)
    difference_set = active_players.difference(guild_members)
    
    print(f"Union: {union_set.to_list()}")
    print(f"Intersection: {intersection_set.to_list()}")
    print(f"Difference (active but not in guild): {difference_set.to_list()}")


def demonstrate_lru_cache():
    """Demonstrate LRUCache functionality."""
    print("\n=== LRUCache Demonstration ===")
    
    # Create LRU cache for player data
    player_cache = create_lru_cache("player_cache", max_size=3)
    
    # Add player data
    player_cache.set("player_1", {"name": "Alice", "level": 10, "score": 1000})
    player_cache.set("player_2", {"name": "Bob", "level": 8, "score": 800})
    player_cache.set("player_3", {"name": "Charlie", "level": 12, "score": 1200})
    
    print(f"Cache size: {player_cache.size()}")
    
    # Access player_1 to make it most recently used
    data = player_cache.get("player_1")
    print(f"Retrieved player_1: {data}")
    
    # Add another player (should evict player_2)
    player_cache.set("player_4", {"name": "Diana", "level": 9, "score": 900})
    
    print(f"Cache size after adding player_4: {player_cache.size()}")
    print(f"Player_2 still in cache: {'player_2' in player_cache}")
    print(f"Player_1 still in cache: {'player_1' in player_cache}")
    
    # Check hit ratio
    player_cache.get("player_1")  # Hit
    player_cache.get("nonexistent")  # Miss
    
    metrics = player_cache.get_metrics()
    print(f"Cache hit ratio: {metrics['hit_ratio']:.2f}")
    print(f"Hits: {metrics['hit_count']}, Misses: {metrics['miss_count']}")


def demonstrate_concurrent_access():
    """Demonstrate concurrent access patterns."""
    print("\n=== Concurrent Access Demonstration ===")
    
    # Create a shared operations map
    shared_map = create_operations_map("shared_game_data")
    results = []
    
    def worker_thread(worker_id: int):
        """Worker thread that performs operations on shared data."""
        try:
            for i in range(50):
                key = f"worker_{worker_id}_item_{i}"
                value = f"data_{worker_id}_{i}"
                
                # Set data
                shared_map.set(key, value)
                
                # Get data back
                retrieved = shared_map.get(key)
                if retrieved != value:
                    results.append(f"Worker {worker_id}: Data mismatch!")
                
                # Small random delay
                time.sleep(random.uniform(0.001, 0.005))
            
            results.append(f"Worker {worker_id}: Completed successfully")
        except Exception as e:
            results.append(f"Worker {worker_id}: Error - {e}")
    
    # Create and start worker threads
    threads = []
    start_time = time.perf_counter()
    
    for worker_id in range(5):
        thread = threading.Thread(target=worker_thread, args=(worker_id,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    end_time = time.perf_counter()
    
    print(f"Concurrent access completed in {end_time - start_time:.3f} seconds")
    print(f"Shared map final size: {shared_map.size()}")
    print(f"Results: {len([r for r in results if 'Completed' in r])} workers completed successfully")
    
    # Check for errors
    errors = [r for r in results if 'Error' in r or 'mismatch' in r]
    if errors:
        print(f"Errors encountered: {errors}")
    else:
        print("No errors encountered during concurrent access")


def demonstrate_performance_monitoring():
    """Demonstrate performance monitoring capabilities."""
    print("\n=== Performance Monitoring Demonstration ===")
    
    # Create collections for performance testing
    perf_map = create_operations_map("performance_test")
    perf_cache = create_lru_cache("performance_cache", 1000)
    
    # Perform many operations
    print("Performing 10,000 operations...")
    start_time = time.perf_counter()
    
    for i in range(10000):
        key = f"perf_key_{i}"
        value = f"perf_value_{i}"
        
        # Operations map
        perf_map.set(key, value)
        perf_map.get(key)
        
        # Cache operations
        perf_cache.set(key, {"data": value, "timestamp": time.time()})
        perf_cache.get(key)
    
    end_time = time.perf_counter()
    total_time = end_time - start_time
    
    print(f"Total time: {total_time:.3f} seconds")
    print(f"Operations per second: {40000 / total_time:.0f}")
    
    # Get detailed metrics
    map_metrics = perf_map.get_metrics()
    cache_metrics = perf_cache.get_metrics()
    
    print(f"\nOperationsMap metrics:")
    print(f"  Operations: {map_metrics.operation_count}")
    print(f"  Average time: {map_metrics.average_time * 1000:.3f} ms")
    print(f"  Max time: {map_metrics.max_time * 1000:.3f} ms")
    
    print(f"\nLRUCache metrics:")
    print(f"  Hit ratio: {cache_metrics['hit_ratio']:.3f}")
    print(f"  Cache size: {cache_metrics['current_size']}")
    
    # Get all metrics from collection manager
    all_metrics = get_all_metrics()
    print(f"\nTotal collections monitored: {len(all_metrics)}")


def demonstrate_real_world_scenario():
    """Demonstrate a real-world gaming scenario."""
    print("\n=== Real-World Gaming Scenario ===")
    
    # Game server data structures
    online_players = create_identity_collection("online_players")
    active_connections = create_connection_id_collection("active_connections")
    pending_queries = create_query_id_collection("pending_queries")
    player_sessions = create_operations_map("player_sessions")
    guild_cache = create_lru_cache("guild_cache", 100)
    
    print("Setting up game server data structures...")
    
    # Simulate players joining
    players = []
    for i in range(10):
        identity = Identity(f"player_{i:02d}_identity_32_chars_!".encode())
        connection = ConnectionId(3000 + i)
        
        # Add to collections
        online_players.add(identity)
        active_connections.add(connection, {
            "player_id": i,
            "join_time": time.time(),
            "client_type": random.choice(["web", "mobile", "desktop"])
        })
        
        # Create player session
        session_data = {
            "identity": identity,
            "connection": connection,
            "level": random.randint(1, 50),
            "guild_id": random.randint(1, 5),
            "last_activity": EnhancedTimestamp.now()
        }
        
        player = GamePlayer(i, f"Player_{i}", session_data["level"])
        player_sessions.set(player, session_data)
        players.append(player)
    
    print(f"Online players: {online_players.size()}")
    print(f"Active connections: {active_connections.size()}")
    print(f"Player sessions: {player_sessions.size()}")
    
    # Simulate some queries
    for i in range(5):
        query = QueryId(4000 + i)
        pending_queries.add(query, {
            "sql": f"SELECT * FROM game_data WHERE region = 'region_{i}'",
            "player_id": i,
            "timeout": 30
        })
    
    # Cache some guild data
    for guild_id in range(1, 6):
        guild_data = {
            "id": guild_id,
            "name": f"Guild_{guild_id}",
            "members": random.randint(5, 20),
            "level": random.randint(1, 10)
        }
        guild_cache.set(f"guild_{guild_id}", guild_data)
    
    # Simulate player activity
    print("\nSimulating player activity...")
    for _ in range(20):
        player = random.choice(players)
        session = player_sessions.get(player)
        if session:
            session["last_activity"] = EnhancedTimestamp.now()
            session["actions"] = session.get("actions", 0) + 1
            player_sessions.set(player, session)
    
    # Show final statistics
    print(f"\nFinal Statistics:")
    print(f"  Online players: {online_players.size()}")
    print(f"  Active connections: {active_connections.size()}")
    print(f"  Pending queries: {pending_queries.size()}")
    print(f"  Player sessions: {player_sessions.size()}")
    print(f"  Guild cache hit ratio: {guild_cache.get_hit_ratio():.3f}")
    
    # Show metrics summary
    all_metrics = get_all_metrics()
    total_operations = sum(
        metrics.get("operation_count", 0) 
        for metrics in all_metrics.values() 
        if isinstance(metrics, dict)
    )
    print(f"  Total operations across all collections: {total_operations}")


def main():
    """Main demonstration function."""
    print("SpacetimeDB Specialized Data Structures Demonstration")
    print("=" * 60)
    
    try:
        # Run all demonstrations
        demonstrate_operations_map()
        demonstrate_identity_collection()
        demonstrate_connection_collection()
        demonstrate_query_collection()
        demonstrate_concurrent_set()
        demonstrate_lru_cache()
        demonstrate_concurrent_access()
        demonstrate_performance_monitoring()
        demonstrate_real_world_scenario()
        
        print("\n" + "=" * 60)
        print("All demonstrations completed successfully!")
        
        # Final metrics summary
        print("\nFinal Metrics Summary:")
        all_metrics = get_all_metrics()
        for name, metrics in all_metrics.items():
            if isinstance(metrics, dict) and "operation_count" in metrics:
                print(f"  {name}: {metrics['operation_count']} operations")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 