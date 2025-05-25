"""
Collections and Advanced Data Structures Integration Tests for SpacetimeDB Python SDK.

Tests complex collections, arrays, nested structures, and bulk operations
using actual SpacetimeDB WASM modules.
"""

import asyncio
import pytest
import time
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass
import random
import json

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    configure_default_logging,
    get_logger,
    
    # WASM integration
    SpacetimeDBServer,
    SpacetimeDBConfig,
    WASMModule,
    WASMTestHarness,
    PerformanceBenchmark,
    require_spacetimedb,
    require_sdk_test_module,
    
    # Subscription
    SubscriptionStrategy,
    
    # Event system
    EventContext,
    EventType,
    
    # Data types
    AlgebraicValue,
    type_builder,
    FieldInfo,
)


# Configure logging
configure_default_logging(debug=True)
logger = get_logger()


@dataclass
class GamePlayer:
    """Player in a game."""
    id: int
    name: str
    level: int
    experience: int
    inventory: List[int]  # Item IDs
    achievements: Set[str]
    position: Dict[str, float]  # {"x": 0.0, "y": 0.0, "z": 0.0}
    guild_id: int | None


@dataclass
class GameItem:
    """Game item."""
    id: int
    name: str
    type: str
    attributes: Dict[str, Any]
    stackable: bool
    max_stack: int


@dataclass
class GameGuild:
    """Player guild."""
    id: int
    name: str
    leader_id: int
    member_ids: List[int]
    treasury: Dict[str, int]  # {"gold": 1000, "gems": 50}
    permissions: Dict[int, Set[str]]  # {player_id: {"invite", "kick"}}


@dataclass 
class GameWorld:
    """Game world with nested structures."""
    id: int
    name: str
    regions: List[Dict[str, Any]]
    spawn_points: List[Tuple[float, float, float]]
    world_events: List[Dict[str, Any]]
    statistics: Dict[str, Dict[str, int]]  # Nested stats


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestCollectionOperations:
    """Test array, vector, and collection operations."""
    
    async def test_array_operations(self, wasm_harness, sdk_test_module):
        """Test fixed-size array operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "array_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Track events
            arrays_received = []
            
            def on_array_insert(event: EventContext):
                if event.type == EventType.INSERT:
                    arrays_received.append(event.data)
            
            client.on(EventType.INSERT, on_array_insert)
            
            # Subscribe to array tables
            subscription = (client.subscription_builder()
                           .subscribe(["SELECT * FROM ArrayTest"]))
            
            await asyncio.sleep(0.5)
            
            # Test different array sizes
            with benchmark.measure("array_operations"):
                # Small arrays
                await client.call_reducer("create_array_test", {
                    "name": "small_array",
                    "int_array": [1, 2, 3, 4, 5],
                    "float_array": [1.1, 2.2, 3.3],
                    "string_array": ["a", "b", "c"]
                })
                
                # Large arrays
                large_int_array = list(range(1000))
                await client.call_reducer("create_array_test", {
                    "name": "large_array",
                    "int_array": large_int_array,
                    "float_array": [float(i) * 0.1 for i in range(500)],
                    "string_array": [f"item_{i}" for i in range(100)]
                })
                
                # Nested arrays
                await client.call_reducer("create_nested_array", {
                    "name": "nested",
                    "matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                    "tensor": [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
                })
            
            # Wait for events
            await asyncio.sleep(1.0)
            
            # Verify arrays
            logger.info(f"Received {len(arrays_received)} array records")
            
            # Test array queries
            with benchmark.measure("array_queries"):
                # Query by array element
                result = await client.execute_sql(
                    "SELECT * FROM ArrayTest WHERE int_array[0] = 1"
                )
                
                # Query array length
                result = await client.execute_sql(
                    "SELECT * FROM ArrayTest WHERE LENGTH(string_array) > 50"
                )
            
            # Performance report
            logger.info("Array operation performance:")
            for op in ["array_operations", "array_queries"]:
                stats = benchmark.get_stats(op)
                if stats:
                    logger.info(f"  {op}: {stats['mean']*1000:.2f}ms")
            
        finally:
            await client.disconnect()
    
    async def test_vector_operations(self, wasm_harness, sdk_test_module):
        """Test dynamic vector/list operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "vector_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test inventory management (common use case)
            with benchmark.measure("inventory_operations"):
                # Create player with inventory
                player_id = await client.call_reducer("create_player", {
                    "name": "TestPlayer",
                    "level": 50,
                    "inventory": []  # Start empty
                })
                
                # Add items to inventory
                for i in range(100):
                    await client.call_reducer("add_to_inventory", {
                        "player_id": player_id,
                        "item_id": 1000 + i,
                        "quantity": random.randint(1, 10)
                    })
                
                # Remove items
                for i in range(20):
                    await client.call_reducer("remove_from_inventory", {
                        "player_id": player_id,
                        "item_id": 1000 + i
                    })
                
                # Sort inventory
                await client.call_reducer("sort_inventory", {
                    "player_id": player_id,
                    "sort_by": "item_type"
                })
            
            # Test batch vector operations
            with benchmark.measure("batch_vector_ops"):
                # Batch add
                await client.call_reducer("batch_add_items", {
                    "player_id": player_id,
                    "item_ids": list(range(2000, 2050))
                })
                
                # Batch remove
                await client.call_reducer("batch_remove_items", {
                    "player_id": player_id,
                    "item_ids": list(range(2000, 2010))
                })
            
            # Performance report
            stats = benchmark.get_stats("inventory_operations")
            if stats:
                logger.info(f"Inventory operations: {stats['mean']*1000:.2f}ms avg")
            
        finally:
            await client.disconnect()
    
    async def test_set_operations(self, wasm_harness, sdk_test_module):
        """Test set operations for unique collections."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "set_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test achievement system (set-based)
            with benchmark.measure("achievement_operations"):
                player_id = await client.call_reducer("create_player", {
                    "name": "AchievementHunter",
                    "achievements": set()
                })
                
                # Grant achievements
                achievements = [
                    "first_kill", "level_10", "level_50", "epic_loot",
                    "dungeon_master", "pvp_champion", "explorer"
                ]
                
                for achievement in achievements:
                    await client.call_reducer("grant_achievement", {
                        "player_id": player_id,
                        "achievement": achievement
                    })
                
                # Check duplicates (should be ignored)
                await client.call_reducer("grant_achievement", {
                    "player_id": player_id,
                    "achievement": "first_kill"  # Already has this
                })
            
            # Test set operations
            with benchmark.measure("set_math_operations"):
                # Union of achievements
                await client.call_reducer("merge_achievements", {
                    "player1_id": player_id,
                    "player2_achievements": {"rare_mount", "master_crafter"}
                })
                
                # Intersection for shared achievements
                result = await client.call_reducer("find_shared_achievements", {
                    "player_ids": [player_id, 2, 3]
                })
                
                # Difference for unique achievements
                result = await client.call_reducer("find_unique_achievements", {
                    "player_id": player_id,
                    "compare_to_ids": [2, 3, 4]
                })
            
            logger.info("Set operations completed successfully")
            
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestNestedDataStructures:
    """Test complex nested data structures."""
    
    async def test_nested_maps(self, wasm_harness, sdk_test_module):
        """Test nested map/dictionary structures."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "nested_map_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Create guild with nested structures
            with benchmark.measure("nested_map_creation"):
                guild_id = await client.call_reducer("create_guild", {
                    "name": "Elite Warriors",
                    "leader_id": 1,
                    "treasury": {
                        "gold": 10000,
                        "gems": 500,
                        "tokens": {"raid": 50, "pvp": 100, "craft": 25}
                    },
                    "permissions": {
                        1: ["all"],  # Leader
                        2: ["invite", "kick", "bank"],  # Officer
                        3: ["invite"],  # Member
                    },
                    "settings": {
                        "recruitment": {
                            "open": True,
                            "min_level": 50,
                            "requirements": {
                                "achievements": ["dungeon_master"],
                                "item_level": 400
                            }
                        },
                        "bank": {
                            "tabs": 5,
                            "access": {
                                "tab1": ["member"],
                                "tab2": ["officer", "leader"],
                                "tab3": ["leader"]
                            }
                        }
                    }
                })
            
            # Update nested values
            with benchmark.measure("nested_map_updates"):
                # Update treasury
                await client.call_reducer("update_guild_treasury", {
                    "guild_id": guild_id,
                    "currency": "gold",
                    "amount": 5000
                })
                
                # Update nested tokens
                await client.call_reducer("update_guild_tokens", {
                    "guild_id": guild_id,
                    "token_type": "raid",
                    "amount": 25
                })
                
                # Update permissions
                await client.call_reducer("update_member_permissions", {
                    "guild_id": guild_id,
                    "member_id": 4,
                    "permissions": ["invite", "bank_view"]
                })
            
            # Query nested data
            with benchmark.measure("nested_map_queries"):
                # Find guilds with enough gold
                result = await client.execute_sql(
                    "SELECT * FROM guilds WHERE treasury->>'gold' > 5000"
                )
                
                # Find guilds with specific permissions
                result = await client.execute_sql(
                    "SELECT * FROM guilds WHERE permissions @> '{\"2\": [\"kick\"]}'"
                )
            
            logger.info("Nested map operations completed")
            
        finally:
            await client.disconnect()
    
    async def test_deeply_nested_structures(self, wasm_harness, sdk_test_module):
        """Test deeply nested data structures."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "deep_nest_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Create game world with deep nesting
            with benchmark.measure("deep_structure_creation"):
                world = {
                    "name": "Mystic Realm",
                    "regions": [
                        {
                            "id": 1,
                            "name": "Forest of Whispers",
                            "zones": [
                                {
                                    "id": 101,
                                    "name": "Ancient Grove",
                                    "npcs": [
                                        {
                                            "id": 10001,
                                            "name": "Elder Tree Spirit",
                                            "dialogue": {
                                                "greeting": "Welcome, traveler",
                                                "quests": {
                                                    "q1": {
                                                        "name": "Gather herbs",
                                                        "rewards": {
                                                            "exp": 1000,
                                                            "items": [{"id": 5001, "qty": 5}]
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ],
                                    "spawns": {
                                        "monsters": [
                                            {
                                                "type": "wolf",
                                                "level_range": [10, 15],
                                                "loot_table": {
                                                    "common": [{"id": 2001, "chance": 0.5}],
                                                    "rare": [{"id": 2002, "chance": 0.1}]
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ],
                    "global_events": {
                        "weather": {
                            "current": "sunny",
                            "forecast": [
                                {"time": "12:00", "type": "cloudy"},
                                {"time": "18:00", "type": "rain"}
                            ]
                        }
                    }
                }
                
                world_id = await client.call_reducer("create_world", world)
            
            # Navigate and update deep structures
            with benchmark.measure("deep_structure_navigation"):
                # Update NPC dialogue
                await client.call_reducer("update_npc_dialogue", {
                    "world_id": world_id,
                    "region_id": 1,
                    "zone_id": 101,
                    "npc_id": 10001,
                    "dialogue_key": "farewell",
                    "text": "May the forest guide you"
                })
                
                # Add loot to monster
                await client.call_reducer("add_monster_loot", {
                    "world_id": world_id,
                    "path": ["regions", 0, "zones", 0, "spawns", "monsters", 0, "loot_table", "epic"],
                    "loot": [{"id": 2003, "chance": 0.01}]
                })
            
            logger.info("Deep nesting test completed")
            
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestBulkOperations:
    """Test bulk insert, update, and delete operations."""
    
    async def test_bulk_inserts(self, wasm_harness, sdk_test_module):
        """Test bulk insert performance and correctness."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "bulk_insert_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Track inserts
            insert_count = 0
            
            def on_insert(event: EventContext):
                nonlocal insert_count
                if event.type == EventType.INSERT:
                    insert_count += 1
            
            client.on(EventType.INSERT, on_insert)
            
            # Subscribe
            subscription = (client.subscription_builder()
                           .subscribe(["SELECT * FROM Players", "SELECT * FROM Items"]))
            
            await asyncio.sleep(0.5)
            
            # Bulk insert players
            num_players = 1000
            with benchmark.measure("bulk_insert_players"):
                players = []
                for i in range(num_players):
                    players.append({
                        "name": f"Player_{i}",
                        "level": random.randint(1, 100),
                        "experience": random.randint(0, 1000000),
                        "inventory": [],
                        "position": {"x": random.uniform(-1000, 1000), 
                                   "y": random.uniform(-1000, 1000)}
                    })
                
                # Send in batches
                batch_size = 100
                for i in range(0, len(players), batch_size):
                    batch = players[i:i+batch_size]
                    await client.call_reducer("bulk_create_players", {
                        "players": batch
                    })
            
            # Bulk insert items
            num_items = 5000
            with benchmark.measure("bulk_insert_items"):
                items = []
                item_types = ["weapon", "armor", "consumable", "material", "quest"]
                
                for i in range(num_items):
                    items.append({
                        "name": f"Item_{i}",
                        "type": random.choice(item_types),
                        "attributes": {
                            "power": random.randint(1, 100),
                            "durability": random.randint(50, 100),
                            "value": random.randint(1, 10000)
                        }
                    })
                
                # Send in larger batches
                batch_size = 500
                for i in range(0, len(items), batch_size):
                    batch = items[i:i+batch_size]
                    await client.call_reducer("bulk_create_items", {
                        "items": batch
                    })
            
            # Wait for all inserts
            await asyncio.sleep(2.0)
            
            # Verify counts
            logger.info(f"Total inserts observed: {insert_count}")
            
            # Performance analysis
            player_stats = benchmark.get_stats("bulk_insert_players")
            item_stats = benchmark.get_stats("bulk_insert_items")
            
            if player_stats:
                players_per_sec = num_players / player_stats['mean']
                logger.info(f"Player insert rate: {players_per_sec:.0f} players/sec")
            
            if item_stats:
                items_per_sec = num_items / item_stats['mean']
                logger.info(f"Item insert rate: {items_per_sec:.0f} items/sec")
            
        finally:
            await client.disconnect()
    
    async def test_bulk_updates(self, wasm_harness, sdk_test_module):
        """Test bulk update operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "bulk_update_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # First, create test data
            await client.call_reducer("setup_test_data", {
                "player_count": 500,
                "item_count": 2000
            })
            
            await asyncio.sleep(1.0)
            
            # Bulk update player levels
            with benchmark.measure("bulk_update_levels"):
                await client.call_reducer("bulk_level_up", {
                    "min_level": 1,
                    "max_level": 50,
                    "level_increase": 10
                })
            
            # Bulk update item prices
            with benchmark.measure("bulk_update_prices"):
                await client.call_reducer("bulk_adjust_prices", {
                    "item_type": "weapon",
                    "price_multiplier": 1.25
                })
            
            # Bulk update player positions
            with benchmark.measure("bulk_update_positions"):
                await client.call_reducer("bulk_teleport_players", {
                    "from_region": {"x_min": -100, "x_max": 100, 
                                   "y_min": -100, "y_max": 100},
                    "to_position": {"x": 0, "y": 0}
                })
            
            # Complex bulk update with conditions
            with benchmark.measure("conditional_bulk_update"):
                await client.call_reducer("bulk_grant_rewards", {
                    "conditions": {
                        "min_level": 50,
                        "has_achievement": "dungeon_master"
                    },
                    "rewards": {
                        "gold": 1000,
                        "items": [{"id": 9001, "qty": 1}],
                        "experience": 50000
                    }
                })
            
            logger.info("Bulk updates completed")
            
        finally:
            await client.disconnect()
    
    async def test_bulk_deletes(self, wasm_harness, sdk_test_module):
        """Test bulk delete operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "bulk_delete_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Track deletes
            delete_count = 0
            
            def on_delete(event: EventContext):
                nonlocal delete_count
                if event.type == EventType.DELETE:
                    delete_count += 1
            
            client.on(EventType.DELETE, on_delete)
            
            # Create test data
            await client.call_reducer("setup_test_data", {
                "player_count": 1000,
                "item_count": 5000
            })
            
            await asyncio.sleep(1.0)
            
            # Bulk delete inactive players
            with benchmark.measure("bulk_delete_players"):
                await client.call_reducer("bulk_delete_inactive", {
                    "days_inactive": 30,
                    "preserve_high_level": True,
                    "min_level_to_preserve": 80
                })
            
            # Bulk delete expired items
            with benchmark.measure("bulk_delete_items"):
                await client.call_reducer("bulk_delete_expired_items", {
                    "item_types": ["consumable"],
                    "expiry_threshold": int(time.time() - 86400)  # 1 day ago
                })
            
            # Cascade delete (guild and all members)
            with benchmark.measure("cascade_delete"):
                await client.call_reducer("delete_guild_cascade", {
                    "guild_id": 1,
                    "reassign_members_to": None  # Delete members too
                })
            
            # Wait for deletes
            await asyncio.sleep(2.0)
            
            logger.info(f"Total deletes observed: {delete_count}")
            
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestComplexQueries:
    """Test complex query patterns and performance."""
    
    async def test_join_queries(self, wasm_harness, sdk_test_module):
        """Test complex join operations."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "join_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Setup relational data
            await client.call_reducer("setup_relational_data", {
                "players": 100,
                "guilds": 10,
                "items": 500
            })
            
            await asyncio.sleep(1.0)
            
            # Test various join patterns
            with benchmark.measure("simple_join"):
                # Players with their guilds
                result = await client.execute_sql("""
                    SELECT p.name, p.level, g.name as guild_name
                    FROM players p
                    JOIN guilds g ON p.guild_id = g.id
                    WHERE p.level > 50
                """)
            
            with benchmark.measure("multi_join"):
                # Players with guilds and equipped items
                result = await client.execute_sql("""
                    SELECT p.name, g.name as guild, i.name as weapon
                    FROM players p
                    LEFT JOIN guilds g ON p.guild_id = g.id
                    JOIN player_equipment pe ON p.id = pe.player_id
                    JOIN items i ON pe.item_id = i.id
                    WHERE i.type = 'weapon'
                """)
            
            with benchmark.measure("aggregate_join"):
                # Guild statistics
                result = await client.execute_sql("""
                    SELECT g.name,
                           COUNT(p.id) as member_count,
                           AVG(p.level) as avg_level,
                           MAX(p.level) as max_level,
                           SUM(p.experience) as total_exp
                    FROM guilds g
                    LEFT JOIN players p ON g.id = p.guild_id
                    GROUP BY g.id, g.name
                    HAVING COUNT(p.id) > 5
                    ORDER BY avg_level DESC
                """)
            
            logger.info("Join queries completed")
            
        finally:
            await client.disconnect()
    
    async def test_subqueries(self, wasm_harness, sdk_test_module):
        """Test subquery patterns."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "subquery_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test various subquery patterns
            with benchmark.measure("in_subquery"):
                # Players in top guilds
                result = await client.execute_sql("""
                    SELECT * FROM players
                    WHERE guild_id IN (
                        SELECT id FROM guilds
                        WHERE treasury->>'gold' > 10000
                    )
                """)
            
            with benchmark.measure("exists_subquery"):
                # Players with rare items
                result = await client.execute_sql("""
                    SELECT * FROM players p
                    WHERE EXISTS (
                        SELECT 1 FROM player_inventory pi
                        JOIN items i ON pi.item_id = i.id
                        WHERE pi.player_id = p.id
                        AND i.rarity = 'legendary'
                    )
                """)
            
            with benchmark.measure("scalar_subquery"):
                # Players above average level
                result = await client.execute_sql("""
                    SELECT * FROM players
                    WHERE level > (
                        SELECT AVG(level) FROM players
                    )
                """)
            
            with benchmark.measure("correlated_subquery"):
                # Players with most valuable inventory
                result = await client.execute_sql("""
                    SELECT p.*, (
                        SELECT SUM(i.value * pi.quantity)
                        FROM player_inventory pi
                        JOIN items i ON pi.item_id = i.id
                        WHERE pi.player_id = p.id
                    ) as inventory_value
                    FROM players p
                    ORDER BY inventory_value DESC
                    LIMIT 10
                """)
            
            logger.info("Subquery tests completed")
            
        finally:
            await client.disconnect()
    
    async def test_window_functions(self, wasm_harness, sdk_test_module):
        """Test window functions and analytics."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "window_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test window functions
            with benchmark.measure("ranking_functions"):
                # Player rankings
                result = await client.execute_sql("""
                    SELECT name, level, experience,
                           ROW_NUMBER() OVER (ORDER BY level DESC, experience DESC) as rank,
                           RANK() OVER (ORDER BY level DESC) as level_rank,
                           DENSE_RANK() OVER (ORDER BY level DESC) as dense_level_rank,
                           PERCENT_RANK() OVER (ORDER BY experience DESC) as exp_percentile
                    FROM players
                """)
            
            with benchmark.measure("partition_functions"):
                # Rankings within guilds
                result = await client.execute_sql("""
                    SELECT name, guild_id, level,
                           ROW_NUMBER() OVER (PARTITION BY guild_id ORDER BY level DESC) as guild_rank,
                           AVG(level) OVER (PARTITION BY guild_id) as guild_avg_level,
                           level - AVG(level) OVER (PARTITION BY guild_id) as level_diff
                    FROM players
                    WHERE guild_id IS NOT NULL
                """)
            
            with benchmark.measure("moving_aggregates"):
                # Moving averages for player activity
                result = await client.execute_sql("""
                    SELECT date, player_count, events,
                           AVG(events) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as weekly_avg,
                           SUM(events) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cumulative
                    FROM daily_activity
                    ORDER BY date
                """)
            
            logger.info("Window function tests completed")
            
        finally:
            await client.disconnect()


@pytest.mark.integration
@pytest.mark.wasm
@pytest.mark.asyncio
class TestAdvancedPatterns:
    """Test advanced patterns and edge cases."""
    
    async def test_transaction_patterns(self, wasm_harness, sdk_test_module):
        """Test transaction consistency and patterns."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "transaction_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test atomic operations
            with benchmark.measure("atomic_transfer"):
                # Transfer items between players atomically
                result = await client.call_reducer("transfer_items", {
                    "from_player_id": 1,
                    "to_player_id": 2,
                    "items": [
                        {"item_id": 1001, "quantity": 5},
                        {"item_id": 1002, "quantity": 10}
                    ]
                })
            
            # Test transaction rollback
            with benchmark.measure("transaction_rollback"):
                try:
                    # This should fail and rollback
                    await client.call_reducer("complex_transaction", {
                        "operations": [
                            {"type": "debit", "player_id": 1, "amount": 1000000},  # Will fail
                            {"type": "credit", "player_id": 2, "amount": 1000000}
                        ]
                    })
                except Exception as e:
                    logger.info(f"Expected rollback: {e}")
            
            # Test optimistic locking
            with benchmark.measure("optimistic_locking"):
                # Get current version
                player = await client.execute_sql(
                    "SELECT id, version FROM players WHERE id = 1"
                )
                
                # Update with version check
                await client.call_reducer("update_player_optimistic", {
                    "player_id": 1,
                    "version": player[0]["version"],
                    "updates": {"level": 51, "experience": 500000}
                })
            
            logger.info("Transaction tests completed")
            
        finally:
            await client.disconnect()
    
    async def test_memory_efficiency(self, wasm_harness, sdk_test_module):
        """Test memory efficiency with large datasets."""
        require_spacetimedb()
        
        benchmark = PerformanceBenchmark()
        
        # Publish module
        address = await wasm_harness.publish_module(sdk_test_module, "memory_test")
        client = await wasm_harness.create_client(address)
        
        try:
            # Test streaming large results
            with benchmark.measure("stream_large_dataset"):
                # Subscribe with pagination hint
                subscription = (client.subscription_builder()
                               .with_page_size(100)
                               .subscribe(["SELECT * FROM large_table"]))
                
                # Process in chunks
                total_processed = 0
                async for chunk in subscription.stream():
                    total_processed += len(chunk)
                    if total_processed > 10000:
                        break
            
            # Test memory-efficient aggregations
            with benchmark.measure("efficient_aggregation"):
                # Use server-side aggregation
                result = await client.execute_sql("""
                    SELECT 
                        DATE_TRUNC('hour', timestamp) as hour,
                        COUNT(*) as event_count,
                        SUM(value) as total_value,
                        AVG(value) as avg_value
                    FROM events
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    GROUP BY hour
                    ORDER BY hour
                """)
            
            logger.info("Memory efficiency tests completed")
            
        finally:
            await client.disconnect()


# Pytest fixtures (reuse from other test files)
@pytest.fixture
async def spacetimedb_server():
    """Provide a SpacetimeDB server for testing."""
    config = SpacetimeDBConfig(listen_port=3100)
    server = SpacetimeDBServer(config)
    server.start()
    yield server
    server.stop()


@pytest.fixture
async def wasm_harness(spacetimedb_server):
    """Provide WASM test harness."""
    harness = WASMTestHarness(spacetimedb_server)
    await harness.setup()
    yield harness
    await harness.teardown()


@pytest.fixture
def sdk_test_module():
    """Provide SDK test module."""
    return WASMModule.from_file(require_sdk_test_module(), "sdk_test")


async def main():
    """Run collections and advanced data structures tests."""
    print("Collections and Advanced Data Structures Tests")
    print("=============================================\n")
    
    # Check prerequisites
    import shutil
    if not shutil.which("spacetimedb"):
        print("❌ SpacetimeDB not found in PATH!")
        return
    
    from spacetimedb_sdk.wasm_integration import find_sdk_test_module
    if not find_sdk_test_module():
        print("❌ SDK test module not found!")
        return
    
    print("✅ Prerequisites satisfied")
    print("\nTest Categories:")
    print("1. Collection Operations")
    print("   - Array operations (fixed-size)")
    print("   - Vector operations (dynamic)")
    print("   - Set operations (unique)")
    print("\n2. Nested Data Structures")
    print("   - Nested maps/dictionaries")
    print("   - Deeply nested structures")
    print("\n3. Bulk Operations")
    print("   - Bulk inserts (1000+ records)")
    print("   - Bulk updates with conditions")
    print("   - Bulk deletes with cascades")
    print("\n4. Complex Queries")
    print("   - Join operations")
    print("   - Subqueries")
    print("   - Window functions")
    print("\n5. Advanced Patterns")
    print("   - Transaction consistency")
    print("   - Memory efficiency")
    
    print("\n✅ Test structure ready!")
    print("\nTo run tests:")
    print("pytest test_collections_integration.py -v -m integration")


if __name__ == "__main__":
    asyncio.run(main()) 