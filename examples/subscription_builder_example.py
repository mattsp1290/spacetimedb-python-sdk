"""
SpacetimeDB Advanced Subscription Builder Examples

This file demonstrates the advanced subscription builder API for creating and managing
SpacetimeDB subscriptions, matching the TypeScript SDK's subscription patterns.

The subscription builder provides advanced features like:
- Fluent API with method chaining
- Comprehensive callback support
- Retry policies and error handling
- Multiple subscription strategies
- Performance metrics and monitoring
- State management and lifecycle tracking
"""

import sys
import os
import time
import threading

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import the SpacetimeDB SDK
from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from spacetimedb_sdk.subscription_builder import (
    SubscriptionState,
    SubscriptionStrategy,
    SubscriptionError,
    SubscriptionMetrics
)


# Example 1: Basic subscription matching TypeScript SDK
def example_basic_subscription():
    """
    Basic subscription setup using the subscription builder pattern.
    
    TypeScript equivalent:
    const subscription = await conn.subscription_builder()
        .onApplied(() => console.log("Subscription applied!"))
        .onError(error => console.error("Subscription error:", error))
        .subscribe(["SELECT * FROM messages"]);
    """
    print("=== Example 1: Basic Subscription ===")
    
    # Create client (using builder from previous task)
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("chat_app")
              .build())
    
    # Create subscription using builder pattern
    subscription = (client.subscription_builder()
                   .on_applied(lambda: print("✅ Subscription is now active!"))
                   .on_error(lambda error: print(f"❌ Subscription error: {error.message}"))
                   .on_subscription_applied(lambda: print("🎉 All subscriptions ready!"))
                   .subscribe(["SELECT * FROM messages"]))
    
    print(f"📊 Subscription ID: {subscription.subscription_id}")
    print(f"🔄 State: {subscription.get_state().value}")
    print(f"📈 Active: {subscription.is_active()}")
    
    return subscription


# Example 2: Advanced subscription with comprehensive callbacks
def example_advanced_subscription():
    """
    Advanced subscription with all callback types and configuration options.
    
    Shows TypeScript parity with additional Python-specific features.
    """
    print("\n=== Example 2: Advanced Subscription ===")
    
    # Create client
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("multiplayer_game")
              .with_protocol("binary")
              .build())
    
    # Track subscription events
    events = []
    
    def on_applied():
        events.append("applied")
        print("🟢 Subscription applied - ready to receive data!")
    
    def on_error(error: SubscriptionError):
        events.append(f"error:{error.error_type}")
        print(f"🔴 Subscription error: {error.message}")
        print(f"   Error type: {error.error_type}")
        print(f"   Retry count: {error.retry_count}")
    
    def on_subscription_applied():
        events.append("subscription_applied")
        print("🎯 All subscriptions are now active and synchronized!")
    
    def on_data_update(table_name: str, update_data):
        events.append(f"data_update:{table_name}")
        print(f"📊 Data update received for table '{table_name}': {update_data}")
    
    def on_state_change(state: SubscriptionState, reason: str):
        events.append(f"state_change:{state.value}")
        print(f"🔄 Subscription state changed to '{state.value}': {reason}")
    
    # Create advanced subscription
    subscription = (client.subscription_builder()
                   .on_applied(on_applied)
                   .on_error(on_error)
                   .on_subscription_applied(on_subscription_applied)
                   .on_data_update(on_data_update)
                   .on_state_change(on_state_change)
                   .with_strategy(SubscriptionStrategy.MULTI_QUERY)
                   .with_timeout(45.0)
                   .with_retry_policy(
                       max_retries=5,
                       backoff_seconds=1.0,
                       exponential_backoff=True,
                       max_backoff_seconds=30.0
                   )
                   .subscribe([
                       "SELECT * FROM player_positions WHERE game_id = 'game123'",
                       "SELECT * FROM game_events WHERE game_id = 'game123' AND timestamp > NOW() - INTERVAL '1 hour'",
                       "SELECT * FROM chat_messages WHERE room_id = 'game123_chat'"
                   ]))
    
    print(f"✅ Advanced subscription created!")
    print(f"📊 Subscription ID: {subscription.subscription_id}")
    print(f"📝 Queries: {len(subscription.get_queries())}")
    print(f"🎯 Query IDs: {[qid.id for qid in subscription.get_query_ids()]}")
    
    return subscription, events


# Example 3: Subscription strategy comparison
def example_subscription_strategies():
    """
    Demonstrate different subscription strategies and their use cases.
    """
    print("\n=== Example 3: Subscription Strategies ===")
    
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("strategy_demo")
              .build())
    
    # Strategy 1: Single Query (one subscription per query)
    print("🔹 Single Query Strategy:")
    single_sub = (client.subscription_builder()
                  .with_strategy(SubscriptionStrategy.SINGLE_QUERY)
                  .on_applied(lambda: print("  ✅ Single query subscription applied"))
                  .subscribe([
                      "SELECT * FROM users",
                      "SELECT * FROM orders"
                  ]))
    
    print(f"  📊 Query IDs: {len(single_sub.get_query_ids())} (one per query)")
    
    # Strategy 2: Multi Query (one subscription for all queries)
    print("\n🔹 Multi Query Strategy:")
    multi_sub = (client.subscription_builder()
                 .with_strategy(SubscriptionStrategy.MULTI_QUERY)
                 .on_applied(lambda: print("  ✅ Multi query subscription applied"))
                 .subscribe([
                     "SELECT * FROM products",
                     "SELECT * FROM inventory"
                 ]))
    
    print(f"  📊 Query IDs: {len(multi_sub.get_query_ids())} (all queries in one)")
    
    # Strategy 3: Adaptive (automatically choose based on query characteristics)
    print("\n🔹 Adaptive Strategy:")
    adaptive_sub = (client.subscription_builder()
                    .with_strategy(SubscriptionStrategy.ADAPTIVE)
                    .on_applied(lambda: print("  ✅ Adaptive subscription applied"))
                    .subscribe([
                        "SELECT * FROM analytics_data WHERE date >= '2024-01-01'"
                    ]))
    
    print(f"  📊 Automatically chose strategy for {len(adaptive_sub.get_queries())} queries")
    
    return single_sub, multi_sub, adaptive_sub


# Example 4: Error handling and retry policies
def example_error_handling():
    """
    Demonstrate comprehensive error handling and retry policies.
    """
    print("\n=== Example 4: Error Handling & Retry Policies ===")
    
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("error_demo")
              .build())
    
    error_events = []
    retry_events = []
    
    def on_error(error: SubscriptionError):
        error_events.append(error)
        print(f"🔴 Error occurred: {error.message}")
        print(f"   Type: {error.error_type}")
        print(f"   Query: {error.query}")
        print(f"   Timestamp: {time.ctime(error.timestamp)}")
    
    def on_state_change(state: SubscriptionState, reason: str):
        if state == SubscriptionState.RETRYING:
            retry_events.append((state, reason))
            print(f"🔄 Retrying subscription: {reason}")
        elif state == SubscriptionState.ERROR:
            print(f"💀 Subscription failed permanently: {reason}")
    
    # Configure robust retry policy
    subscription = (client.subscription_builder()
                   .on_error(on_error)
                   .on_state_change(on_state_change)
                   .with_retry_policy(
                       max_retries=3,
                       backoff_seconds=2.0,
                       exponential_backoff=True,
                       max_backoff_seconds=16.0
                   )
                   .with_timeout(60.0)
                   .subscribe([
                       "SELECT * FROM reliable_data WHERE important = true"
                   ]))
    
    print(f"✅ Error-resilient subscription created")
    print(f"🛡️  Max retries: 3 with exponential backoff")
    print(f"⏱️  Timeout: 60 seconds")
    
    return subscription, error_events, retry_events


# Example 5: Subscription metrics and monitoring
def example_subscription_metrics():
    """
    Demonstrate subscription performance metrics and monitoring.
    """
    print("\n=== Example 5: Subscription Metrics & Monitoring ===")
    
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("metrics_demo")
              .build())
    
    def print_metrics(subscription):
        metrics = subscription.get_metrics()
        print(f"📊 Subscription Metrics:")
        print(f"   ID: {metrics.subscription_id}")
        print(f"   Lifetime: {metrics.get_lifetime_seconds():.2f} seconds")
        print(f"   Apply Duration: {metrics.get_apply_duration_seconds():.2f} seconds" if metrics.get_apply_duration_seconds() else "   Apply Duration: Not yet applied")
        print(f"   Query Count: {metrics.query_count}")
        print(f"   Error Count: {metrics.error_count}")
        print(f"   Retry Count: {metrics.retry_count}")
        print(f"   Data Updates: {metrics.data_updates_received}")
    
    # Create monitored subscription
    subscription = (client.subscription_builder()
                   .on_applied(lambda: print("✅ Subscription applied - starting metrics collection"))
                   .on_data_update(lambda table, data: print(f"📈 Data update for {table}"))
                   .subscribe([
                       "SELECT * FROM monitoring_table",
                       "SELECT count(*) as total_records FROM activity_log"
                   ]))
    
    # Print initial metrics
    print_metrics(subscription)
    
    # Simulate some time passing
    time.sleep(0.1)
    
    # Print updated metrics
    print("\nUpdated metrics:")
    print_metrics(subscription)
    
    return subscription


# Example 6: Query validation and security
def example_query_validation():
    """
    Demonstrate query validation and security features.
    """
    print("\n=== Example 6: Query Validation & Security ===")
    
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("validation_demo")
              .build())
    
    builder = client.subscription_builder()
    
    # Test valid queries
    valid_queries = [
        "SELECT * FROM safe_table",
        "SELECT id, name FROM users WHERE active = true",
        "select count(*) from orders where date >= '2024-01-01'"
    ]
    
    print("🔍 Validating queries...")
    errors = builder.validate_queries(valid_queries)
    
    if not errors:
        print("✅ All queries are valid!")
        print("Valid queries:")
        for i, query in enumerate(valid_queries, 1):
            print(f"  {i}. {query}")
    else:
        print("❌ Validation errors found:")
        for error in errors:
            print(f"  - {error}")
    
    # Test invalid queries
    print("\n🚨 Testing invalid queries:")
    invalid_queries = [
        "",  # Empty query
        "INSERT INTO users VALUES (1, 'hacker')",  # Non-SELECT
        "SELECT * FROM users; DROP TABLE users;--",  # SQL injection attempt
        "DELETE FROM sensitive_data"  # Dangerous operation
    ]
    
    validation_errors = builder.validate_queries(invalid_queries)
    print(f"Found {len(validation_errors)} validation errors:")
    for error in validation_errors:
        print(f"  ❌ {error}")
    
    # Create subscription with valid queries only
    if not errors:
        subscription = builder.subscribe(valid_queries)
        print(f"\n✅ Secure subscription created with {len(valid_queries)} validated queries")
        return subscription
    
    return None


# Example 7: Subscription lifecycle management
def example_subscription_lifecycle():
    """
    Demonstrate complete subscription lifecycle management.
    """
    print("\n=== Example 7: Subscription Lifecycle Management ===")
    
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("lifecycle_demo")
              .build())
    
    lifecycle_events = []
    
    def track_lifecycle(event_name):
        def callback(*args):
            lifecycle_events.append((event_name, time.time(), args))
            print(f"🔄 Lifecycle event: {event_name}")
        return callback
    
    # Create subscription with lifecycle tracking
    print("Creating subscription with lifecycle tracking...")
    subscription = (client.subscription_builder()
                   .on_applied(track_lifecycle("applied"))
                   .on_subscription_applied(track_lifecycle("subscription_applied"))
                   .on_state_change(lambda state, reason: track_lifecycle("state_change")(state.value, reason))
                   .on_data_update(track_lifecycle("data_update"))
                   .subscribe([
                       "SELECT * FROM lifecycle_table"
                   ]))
    
    print(f"✅ Subscription created: {subscription.subscription_id}")
    print(f"📊 Initial state: {subscription.get_state().value}")
    
    # Demonstrate subscription management
    print("\n📈 Subscription status:")
    print(f"  Active: {subscription.is_active()}")
    print(f"  Cancelled: {subscription.is_cancelled()}")
    print(f"  Has errors: {subscription.has_errors()}")
    
    # Simulate lifecycle operations
    print("\n🛑 Cancelling subscription...")
    subscription.cancel()
    
    print(f"📊 Final state: {subscription.get_state().value}")
    print(f"  Active: {subscription.is_active()}")
    print(f"  Cancelled: {subscription.is_cancelled()}")
    
    print(f"\n📝 Lifecycle events captured: {len(lifecycle_events)}")
    for event_name, timestamp, args in lifecycle_events:
        print(f"  - {event_name} at {time.ctime(timestamp)}")
    
    return subscription, lifecycle_events


# Example 8: TypeScript SDK compatibility demonstration
def example_typescript_compatibility():
    """
    Side-by-side comparison with TypeScript SDK patterns.
    """
    print("\n=== Example 8: TypeScript SDK Compatibility ===")
    
    print("TypeScript SDK pattern:")
    print("""
    const subscription = await conn.subscription_builder()
        .onApplied(() => console.log("Applied!"))
        .onError(error => console.error("Error:", error))
        .onSubscriptionApplied(() => console.log("Ready!"))
        .withTimeout(30000)
        .withRetryPolicy({ maxRetries: 3, backoffMs: 1000 })
        .subscribe([
            "SELECT * FROM messages WHERE user_id = 'user123'",
            "SELECT * FROM notifications WHERE user_id = 'user123'"
        ]);
    """)
    
    print("Python SDK equivalent:")
    print("""
    subscription = (client.subscription_builder()
                   .on_applied(lambda: print("Applied!"))
                   .on_error(lambda error: print(f"Error: {error}"))
                   .on_subscription_applied(lambda: print("Ready!"))
                   .with_timeout(30.0)
                   .with_retry_policy(max_retries=3, backoff_seconds=1.0)
                   .subscribe([
                       "SELECT * FROM messages WHERE user_id = 'user123'",
                       "SELECT * FROM notifications WHERE user_id = 'user123'"
                   ]))
    """)
    
    # Actually create the subscription
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("compatibility_demo")
              .build())
    
    subscription = (client.subscription_builder()
                   .on_applied(lambda: print("✅ Applied!"))
                   .on_error(lambda error: print(f"❌ Error: {error}"))
                   .on_subscription_applied(lambda: print("🎉 Ready!"))
                   .with_timeout(30.0)
                   .with_retry_policy(max_retries=3, backoff_seconds=1.0)
                   .subscribe([
                       "SELECT * FROM messages WHERE user_id = 'user123'",
                       "SELECT * FROM notifications WHERE user_id = 'user123'"
                   ]))
    
    print("✅ Python SDK provides identical API patterns to TypeScript!")
    print("🚀 Plus additional Python-specific enhancements:")
    print("  - Comprehensive metrics and monitoring")
    print("  - Advanced retry policies with exponential backoff")
    print("  - Query validation and security features")
    print("  - Rich state management and lifecycle tracking")
    
    return subscription


def main():
    """Run all subscription builder examples."""
    print("SpacetimeDB Python SDK - Advanced Subscription Builder Examples")
    print("=" * 70)
    
    try:
        # Run all examples
        example_basic_subscription()
        example_advanced_subscription()
        example_subscription_strategies()
        example_error_handling()
        example_subscription_metrics()
        example_query_validation()
        example_subscription_lifecycle()
        example_typescript_compatibility()
        
        print("\n" + "=" * 70)
        print("🎉 All examples completed successfully!")
        print("✅ Advanced Subscription Builder is working correctly")
        print("🚀 Python SDK now has TypeScript SDK subscription parity + advanced features!")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    main() 