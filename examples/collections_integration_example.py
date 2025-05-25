"""
Example: Collections and Advanced Data Structures with SpacetimeDB Python SDK

Demonstrates:
- Array and vector operations
- Nested data structures
- Bulk operations
- Complex queries
- Real-world patterns
"""

import asyncio
import time
import random
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    PerformanceBenchmark,
    configure_default_logging,
    get_logger,
    EventContext,
    EventType,
)


# Configure logging
configure_default_logging(debug=False)
logger = get_logger()


@dataclass
class InventoryItem:
    """Item in player inventory."""
    item_id: int
    quantity: int
    slot: int = -1  # -1 means unassigned slot


@dataclass
class Player:
    """Game player with collections."""
    id: int
    name: str
    level: int
    inventory: List[InventoryItem] = field(default_factory=list)
    skills: Set[str] = field(default_factory=set)
    stats: Dict[str, int] = field(default_factory=dict)
    guild_id: int | None = None


@dataclass
class Guild:
    """Player guild with nested structures."""
    id: int
    name: str
    members: List[int] = field(default_factory=list)
    ranks: Dict[str, List[str]] = field(default_factory=dict)  # rank -> permissions
    treasury: Dict[str, Dict[str, int]] = field(default_factory=dict)  # currency -> {amount, last_updated}


class CollectionsExample:
    """Examples demonstrating collections and advanced data structures."""
    
    def __init__(self):
        self.client = None
        self.benchmark = PerformanceBenchmark()
        self.players = {}
        self.guilds = {}
    
    async def connect(self, uri: str, db_name: str):
        """Connect to SpacetimeDB."""
        self.client = (ModernSpacetimeDBClient.builder()
                      .with_uri(uri)
                      .with_db_name(db_name)
                      .build())
        
        await self.client.connect()
        
        # Track events
        self.client.on(EventType.INSERT, self._on_insert)
        self.client.on(EventType.UPDATE, self._on_update)
        self.client.on(EventType.DELETE, self._on_delete)
    
    def _on_insert(self, event: EventContext):
        """Handle insert events."""
        table = event.data.get("table_name")
        if table == "players":
            player = event.data.get("row")
            self.players[player["id"]] = player
        elif table == "guilds":
            guild = event.data.get("row")
            self.guilds[guild["id"]] = guild
    
    def _on_update(self, event: EventContext):
        """Handle update events."""
        pass
    
    def _on_delete(self, event: EventContext):
        """Handle delete events."""
        table = event.data.get("table_name")
        if table == "players":
            player_id = event.data.get("row_id")
            self.players.pop(player_id, None)
    
    async def example_1_inventory_management(self):
        """Example 1: Dynamic inventory management with arrays."""
        print("\n=== Example 1: Inventory Management ===")
        
        # Create player with empty inventory
        player_id = await self.client.call_reducer("create_player", {
            "name": "InventoryMaster",
            "level": 50,
            "inventory_slots": 50
        })
        
        print(f"Created player {player_id}")
        
        # Add items to inventory
        items_to_add = [
            {"id": 1001, "name": "Sword of Fire", "type": "weapon", "quantity": 1},
            {"id": 2001, "name": "Health Potion", "type": "consumable", "quantity": 50},
            {"id": 2002, "name": "Mana Potion", "type": "consumable", "quantity": 30},
            {"id": 3001, "name": "Iron Ore", "type": "material", "quantity": 100},
        ]
        
        with self.benchmark.measure("add_items"):
            for item in items_to_add:
                await self.client.call_reducer("add_to_inventory", {
                    "player_id": player_id,
                    "item_id": item["id"],
                    "quantity": item["quantity"]
                })
                print(f"  Added {item['quantity']}x {item['name']}")
        
        # Stack similar items
        await self.client.call_reducer("stack_inventory", {
            "player_id": player_id
        })
        print("  Stacked similar items")
        
        # Sort inventory by type
        await self.client.call_reducer("sort_inventory", {
            "player_id": player_id,
            "sort_by": "type"
        })
        print("  Sorted inventory by type")
        
        # Query inventory value
        total_value = await self.client.call_reducer("calculate_inventory_value", {
            "player_id": player_id
        })
        print(f"  Total inventory value: {total_value} gold")
        
        # Performance stats
        stats = self.benchmark.get_stats("add_items")
        if stats:
            print(f"\nPerformance: {stats['count']} items added in {stats['total']*1000:.2f}ms")
    
    async def example_2_guild_management(self):
        """Example 2: Guild management with nested structures."""
        print("\n=== Example 2: Guild Management ===")
        
        # Create guild with complex structure
        guild_data = {
            "name": "Dragon Slayers",
            "founder_id": 1,
            "ranks": {
                "Grandmaster": ["all"],
                "Officer": ["invite", "kick", "bank_withdraw", "bank_deposit"],
                "Elite": ["invite", "bank_deposit"],
                "Member": ["bank_view"],
                "Initiate": []
            },
            "treasury": {
                "gold": {"amount": 50000, "daily_limit": 5000},
                "gems": {"amount": 500, "daily_limit": 50},
                "tokens": {
                    "raid": {"amount": 100, "weekly_limit": 20},
                    "pvp": {"amount": 200, "weekly_limit": 50}
                }
            },
            "settings": {
                "recruitment": {
                    "open": True,
                    "min_level": 40,
                    "requirements": ["dragon_slayer_achievement"]
                },
                "tax_rate": 0.05,
                "bank_tabs": 5
            }
        }
        
        guild_id = await self.client.call_reducer("create_guild", guild_data)
        print(f"Created guild: {guild_data['name']}")
        
        # Add members with different ranks
        members = [
            {"player_id": 2, "rank": "Officer"},
            {"player_id": 3, "rank": "Elite"},
            {"player_id": 4, "rank": "Elite"},
            {"player_id": 5, "rank": "Member"},
            {"player_id": 6, "rank": "Member"},
            {"player_id": 7, "rank": "Initiate"},
        ]
        
        for member in members:
            await self.client.call_reducer("add_guild_member", {
                "guild_id": guild_id,
                **member
            })
            print(f"  Added member {member['player_id']} as {member['rank']}")
        
        # Perform treasury operations
        print("\nTreasury operations:")
        
        # Deposit gold
        await self.client.call_reducer("guild_deposit", {
            "guild_id": guild_id,
            "player_id": 3,
            "currency": "gold",
            "amount": 1000
        })
        print("  Player 3 deposited 1000 gold")
        
        # Withdraw with permission check
        try:
            await self.client.call_reducer("guild_withdraw", {
                "guild_id": guild_id,
                "player_id": 2,  # Officer can withdraw
                "currency": "gold",
                "amount": 500
            })
            print("  Officer withdrew 500 gold")
        except Exception as e:
            print(f"  Withdrawal failed: {e}")
        
        # Update nested permissions
        await self.client.call_reducer("update_rank_permissions", {
            "guild_id": guild_id,
            "rank": "Elite",
            "add_permissions": ["bank_withdraw"],
            "remove_permissions": []
        })
        print("  Updated Elite rank permissions")
        
        # Query guild statistics
        stats = await self.client.call_reducer("get_guild_stats", {
            "guild_id": guild_id
        })
        print(f"\nGuild statistics:")
        print(f"  Members: {stats['member_count']}")
        print(f"  Total wealth: {stats['total_wealth']} gold equivalent")
        print(f"  Average member level: {stats['avg_member_level']}")
    
    async def example_3_bulk_operations(self):
        """Example 3: Efficient bulk operations."""
        print("\n=== Example 3: Bulk Operations ===")
        
        # Bulk create NPCs
        print("Creating 100 NPCs...")
        npcs = []
        npc_types = ["merchant", "guard", "quest_giver", "trainer", "innkeeper"]
        
        for i in range(100):
            npc = {
                "name": f"NPC_{i:03d}",
                "type": random.choice(npc_types),
                "level": random.randint(1, 50),
                "location": {
                    "zone": f"zone_{i % 10}",
                    "x": random.uniform(-1000, 1000),
                    "y": random.uniform(-1000, 1000)
                },
                "dialogue": {
                    "greeting": f"Hello, I am {npc_types[i % len(npc_types)]} #{i}",
                    "farewell": "Safe travels!"
                }
            }
            npcs.append(npc)
        
        # Send in batches for efficiency
        batch_size = 20
        with self.benchmark.measure("bulk_npc_create"):
            for i in range(0, len(npcs), batch_size):
                batch = npcs[i:i+batch_size]
                await self.client.call_reducer("bulk_create_npcs", {"npcs": batch})
            print(f"  Created {len(npcs)} NPCs")
        
        # Bulk update - give all merchants a sale
        with self.benchmark.measure("bulk_npc_update"):
            await self.client.call_reducer("bulk_update_merchants", {
                "updates": {
                    "dialogue.sale": "Special offer today! 20% off all items!",
                    "metadata.sale_active": True,
                    "metadata.sale_discount": 0.20
                }
            })
            print("  Updated all merchants with sale information")
        
        # Bulk delete - remove low-level guards from high-level zones
        with self.benchmark.measure("bulk_npc_delete"):
            deleted = await self.client.call_reducer("bulk_delete_npcs", {
                "criteria": {
                    "type": "guard",
                    "level": {"$lt": 20},
                    "location.zone": {"$in": ["zone_7", "zone_8", "zone_9"]}
                }
            })
            print(f"  Deleted {deleted} low-level guards from high-level zones")
        
        # Performance report
        print("\nBulk operation performance:")
        for op in ["bulk_npc_create", "bulk_npc_update", "bulk_npc_delete"]:
            stats = self.benchmark.get_stats(op)
            if stats:
                print(f"  {op}: {stats['mean']*1000:.2f}ms")
    
    async def example_4_complex_queries(self):
        """Example 4: Complex query patterns."""
        print("\n=== Example 4: Complex Queries ===")
        
        # Join query - Find guild members with their inventory value
        print("Running complex queries...")
        
        # Top players by inventory value
        result = await self.client.execute_sql("""
            SELECT 
                p.name,
                p.level,
                g.name as guild_name,
                (
                    SELECT SUM(i.base_value * pi.quantity)
                    FROM player_inventory pi
                    JOIN items i ON pi.item_id = i.id
                    WHERE pi.player_id = p.id
                ) as inventory_value
            FROM players p
            LEFT JOIN guilds g ON p.guild_id = g.id
            ORDER BY inventory_value DESC
            LIMIT 10
        """)
        
        print("\nTop 10 players by inventory value:")
        for row in result:
            guild = row['guild_name'] or 'No Guild'
            print(f"  {row['name']} (Lvl {row['level']}, {guild}): {row['inventory_value']} gold")
        
        # Guild rankings with statistics
        result = await self.client.execute_sql("""
            WITH guild_stats AS (
                SELECT 
                    g.id,
                    g.name,
                    COUNT(p.id) as member_count,
                    AVG(p.level) as avg_level,
                    SUM(p.contribution_points) as total_contribution
                FROM guilds g
                LEFT JOIN players p ON g.id = p.guild_id
                GROUP BY g.id, g.name
            )
            SELECT 
                name,
                member_count,
                ROUND(avg_level, 1) as avg_level,
                total_contribution,
                RANK() OVER (ORDER BY total_contribution DESC) as contribution_rank,
                RANK() OVER (ORDER BY avg_level DESC) as level_rank
            FROM guild_stats
            WHERE member_count >= 5
        """)
        
        print("\nGuild rankings:")
        for row in result:
            print(f"  {row['name']}: {row['member_count']} members, "
                  f"avg level {row['avg_level']}, "
                  f"contribution rank #{row['contribution_rank']}")
        
        # Nested JSON query - Find players with specific achievements
        result = await self.client.execute_sql("""
            SELECT 
                name,
                level,
                achievements->>'total_count' as achievement_count,
                achievements->'categories'->>'combat' as combat_achievements
            FROM players
            WHERE 
                achievements @> '{"categories": {"combat": {"dragon_slayer": true}}}'
                AND level >= 50
        """)
        
        print("\nDragon slayers (level 50+):")
        for row in result:
            print(f"  {row['name']} - {row['achievement_count']} total achievements")
    
    async def example_5_real_world_patterns(self):
        """Example 5: Real-world game patterns."""
        print("\n=== Example 5: Real-World Patterns ===")
        
        # Auction house with complex data
        print("Setting up auction house...")
        
        # Create auction with nested bid history
        auction_id = await self.client.call_reducer("create_auction", {
            "seller_id": 1,
            "item": {
                "id": 9999,
                "name": "Legendary Sword of Destruction",
                "stats": {
                    "damage": 500,
                    "crit_chance": 0.25,
                    "attributes": ["fire_damage", "life_steal", "armor_pierce"]
                }
            },
            "starting_bid": 10000,
            "buyout_price": 50000,
            "duration_hours": 24,
            "bid_history": []
        })
        
        # Simulate bidding war
        bidders = [2, 3, 4, 5]
        current_bid = 10000
        
        print("Bidding war in progress...")
        for i in range(10):
            bidder = random.choice(bidders)
            bid_amount = current_bid + random.randint(500, 2000)
            
            success = await self.client.call_reducer("place_bid", {
                "auction_id": auction_id,
                "bidder_id": bidder,
                "amount": bid_amount
            })
            
            if success:
                current_bid = bid_amount
                print(f"  Player {bidder} bid {bid_amount} gold")
            
            await asyncio.sleep(0.1)  # Simulate time between bids
        
        # Matchmaking with complex criteria
        print("\nMatchmaking system...")
        
        # Create match request with nested preferences
        match_request = await self.client.call_reducer("request_match", {
            "player_id": 1,
            "mode": "ranked_3v3",
            "preferences": {
                "map_votes": ["ancient_arena", "crystal_caves", "sky_fortress"],
                "role": "damage",
                "mmr_range": {"min": 1400, "max": 1600}
            },
            "party_members": [2, 3],
            "restrictions": {
                "no_recent_opponents": True,
                "balanced_roles": True,
                "similar_playtime": True
            }
        })
        
        print("  Match request created")
        
        # Find suitable opponents
        opponents = await self.client.call_reducer("find_opponents", {
            "request_id": match_request,
            "search_criteria": {
                "mmr_tolerance": 100,
                "max_wait_time": 120,
                "region_priority": ["NA", "EU"]
            }
        })
        
        if opponents:
            print(f"  Found opponents: {opponents}")
        else:
            print("  Still searching for opponents...")
        
        # Leaderboard with complex scoring
        print("\nGenerating leaderboard...")
        
        leaderboard = await self.client.execute_sql("""
            WITH player_scores AS (
                SELECT 
                    p.id,
                    p.name,
                    p.level,
                    ps.wins,
                    ps.losses,
                    ps.mmr,
                    ps.win_rate,
                    ps.avg_damage,
                    ps.avg_healing,
                    (ps.mmr * 0.4 + 
                     ps.win_rate * 1000 * 0.3 + 
                     p.level * 10 * 0.2 +
                     ps.avg_damage * 0.1) as composite_score
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE ps.games_played >= 50
            )
            SELECT 
                name,
                level,
                wins,
                losses,
                mmr,
                ROUND(win_rate * 100, 1) as win_percent,
                ROUND(composite_score, 0) as score,
                ROW_NUMBER() OVER (ORDER BY composite_score DESC) as rank
            FROM player_scores
            ORDER BY composite_score DESC
            LIMIT 10
        """)
        
        print("\nTop 10 Leaderboard:")
        for row in leaderboard:
            print(f"  #{row['rank']} {row['name']} - Score: {row['score']}, "
                  f"MMR: {row['mmr']}, Win%: {row['win_percent']}")
    
    async def cleanup(self):
        """Clean up connection."""
        if self.client:
            await self.client.disconnect()
        
        # Print overall performance summary
        print("\n=== Performance Summary ===")
        all_operations = self.benchmark.get_all_stats()
        for op_name, stats in all_operations.items():
            print(f"{op_name}:")
            print(f"  Total calls: {stats['count']}")
            print(f"  Average time: {stats['mean']*1000:.2f}ms")
            print(f"  Min time: {stats['min']*1000:.2f}ms")
            print(f"  Max time: {stats['max']*1000:.2f}ms")


async def main():
    """Run all collections examples."""
    print("SpacetimeDB Collections and Advanced Data Structures Examples")
    print("===========================================================")
    
    example = CollectionsExample()
    
    try:
        # Connect to SpacetimeDB
        await example.connect("ws://localhost:3000", "game_database")
        print("✅ Connected to SpacetimeDB")
        
        # Run examples
        await example.example_1_inventory_management()
        await example.example_2_guild_management()
        await example.example_3_bulk_operations()
        await example.example_4_complex_queries()
        await example.example_5_real_world_patterns()
        
        print("\n✅ All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await example.cleanup()
    
    print("\nKey Takeaways:")
    print("- Arrays for fixed-size collections (inventory slots)")
    print("- Vectors for dynamic lists (guild members)")
    print("- Sets for unique collections (achievements)")
    print("- Nested maps for complex game state")
    print("- Bulk operations for performance")
    print("- Complex queries for analytics")
    print("- JSON queries for flexible schemas")


if __name__ == "__main__":
    asyncio.run(main()) 