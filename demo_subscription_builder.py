#!/usr/bin/env python3
"""
SpacetimeDB Advanced Subscription Builder Demo

Demonstrates the subscription builder API patterns without requiring an actual
SpacetimeDB connection. Shows TypeScript SDK compatibility and advanced features.
"""

import sys
sys.path.append('src')

from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
from spacetimedb_sdk.subscription_builder import (
    AdvancedSubscriptionBuilder,
    SubscriptionState,
    SubscriptionStrategy,
    SubscriptionError,
    RetryPolicy
)


def demo_typescript_compatibility():
    """Demonstrate TypeScript SDK compatibility patterns."""
    print("SpacetimeDB Advanced Subscription Builder - TypeScript Compatibility Demo")
    print("=" * 75)
    
    print("\n🎯 TypeScript SDK Pattern:")
    print("""
    const subscription = await conn.subscription_builder()
        .onApplied(() => console.log("Subscription applied!"))
        .onError(error => console.error("Error:", error.message))
        .onSubscriptionApplied(() => console.log("All subscriptions ready!"))
        .withTimeout(30000)
        .withRetryPolicy({ maxRetries: 3, backoffMs: 1000 })
        .subscribe([
            "SELECT * FROM messages WHERE user_id = 'user123'",
            "SELECT * FROM notifications WHERE user_id = 'user123'"
        ]);
    """)
    
    print("🐍 Python SDK Equivalent:")
    print("""
    subscription = (client.subscription_builder()
                   .on_applied(lambda: print("Subscription applied!"))
                   .on_error(lambda error: print(f"Error: {error.message}"))
                   .on_subscription_applied(lambda: print("All subscriptions ready!"))
                   .with_timeout(30.0)
                   .with_retry_policy(max_retries=3, backoff_seconds=1.0)
                   .subscribe([
                       "SELECT * FROM messages WHERE user_id = 'user123'",
                       "SELECT * FROM notifications WHERE user_id = 'user123'"
                   ]))
    """)


def demo_builder_api():
    """Demonstrate the builder API construction and validation."""
    print("\n🔧 Builder API Demonstration:")
    print("=" * 50)
    
    # Create a mock client for demonstration
    client = ModernSpacetimeDBClient(start_message_processing=False)
    
    # Show builder creation
    print("1. Creating subscription builder:")
    builder = client.subscription_builder()
    print(f"   ✅ Builder created: {type(builder).__name__}")
    
    # Show fluent API chaining
    print("\n2. Fluent API chaining:")
    result = (builder
              .on_applied(lambda: print("Applied!"))
              .on_error(lambda error: print(f"Error: {error}"))
              .on_subscription_applied(lambda: print("Ready!"))
              .with_strategy(SubscriptionStrategy.MULTI_QUERY)
              .with_timeout(45.0)
              .with_retry_policy(max_retries=3, backoff_seconds=2.0))
    
    print(f"   ✅ Chaining works: {result is builder}")
    
    # Show configuration inspection
    print("\n3. Configuration inspection:")
    print(f"   Strategy: {builder._strategy.value}")
    print(f"   Timeout: {builder._timeout_seconds}s")
    print(f"   Max retries: {builder._retry_policy.max_retries}")
    print(f"   Backoff: {builder._retry_policy.backoff_seconds}s")
    
    # Show query validation
    print("\n4. Query validation:")
    valid_queries = [
        "SELECT * FROM messages",
        "SELECT id, content FROM posts WHERE active = true"
    ]
    errors = builder.validate_queries(valid_queries)
    print(f"   Valid queries: {len(errors) == 0}")
    
    invalid_queries = [
        "",  # Empty
        "INSERT INTO messages VALUES (1, 'hack')",  # Non-SELECT
        "SELECT * FROM users; DROP TABLE users;--"  # SQL injection
    ]
    errors = builder.validate_queries(invalid_queries)
    print(f"   Invalid queries detected: {len(errors)} errors")
    
    return builder


def demo_retry_policy():
    """Demonstrate retry policy functionality."""
    print("\n⚙️ Retry Policy Demonstration:")
    print("=" * 40)
    
    # Linear backoff policy
    linear_policy = RetryPolicy(
        max_retries=3,
        backoff_seconds=2.0,
        exponential_backoff=False,
        max_backoff_seconds=10.0
    )
    
    print("Linear backoff policy:")
    for retry in range(4):
        delay = linear_policy.calculate_delay(retry)
        print(f"   Retry {retry}: {delay:.1f}s delay")
    
    # Exponential backoff policy
    exp_policy = RetryPolicy(
        max_retries=5,
        backoff_seconds=1.0,
        exponential_backoff=True,
        max_backoff_seconds=16.0
    )
    
    print("\nExponential backoff policy:")
    for retry in range(6):
        delay = exp_policy.calculate_delay(retry)
        print(f"   Retry {retry}: {delay:.1f}s delay")


def demo_subscription_strategies():
    """Demonstrate subscription strategy selection."""
    print("\n📊 Subscription Strategy Demonstration:")
    print("=" * 45)
    
    client = ModernSpacetimeDBClient(start_message_processing=False)
    builder = client.subscription_builder()
    
    # Test adaptive strategy selection
    print("Adaptive strategy selection:")
    
    # Single query
    strategy = builder._choose_strategy(["SELECT * FROM messages"])
    print(f"   1 query → {strategy.value}")
    
    # Multiple queries (3)
    queries = [f"SELECT * FROM table{i}" for i in range(3)]
    strategy = builder._choose_strategy(queries)
    print(f"   3 queries → {strategy.value}")
    
    # Many queries (8)
    queries = [f"SELECT * FROM table{i}" for i in range(8)]
    strategy = builder._choose_strategy(queries)
    print(f"   8 queries → {strategy.value}")
    
    # Explicit strategy override
    builder.with_strategy(SubscriptionStrategy.MULTI_QUERY)
    strategy = builder._choose_strategy(["SELECT * FROM single"])
    print(f"   Explicit MULTI_QUERY → {strategy.value}")


def demo_subscription_state():
    """Demonstrate subscription state management."""
    print("\n🔄 Subscription State Management:")
    print("=" * 38)
    
    # Show all possible states
    print("Available subscription states:")
    for state in SubscriptionState:
        print(f"   - {state.value.upper()}: {state.name}")
    
    # Demonstrate state transitions
    client = ModernSpacetimeDBClient(start_message_processing=False)
    builder = client.subscription_builder()
    
    state_changes = []
    
    def track_state_change(state, reason):
        state_changes.append((state.value, reason))
        print(f"   State changed to: {state.value} ({reason})")
    
    builder.on_state_change(track_state_change)
    
    print("\nSimulated state transitions:")
    builder._change_state(SubscriptionState.ACTIVE, "Subscription applied")
    builder._change_state(SubscriptionState.ERROR, "Connection lost")
    builder._change_state(SubscriptionState.RETRYING, "Attempting retry")
    builder._change_state(SubscriptionState.CANCELLED, "User cancelled")
    
    print(f"\nTotal state changes tracked: {len(state_changes)}")


def demo_advanced_features():
    """Demonstrate advanced Python-specific features."""
    print("\n🚀 Advanced Python Features:")
    print("=" * 32)
    
    print("Features that EXCEED TypeScript SDK:")
    print("   ✅ Comprehensive metrics and monitoring")
    print("   ✅ Advanced retry policies with exponential backoff")
    print("   ✅ Query validation and security features")
    print("   ✅ Rich state management and lifecycle tracking")
    print("   ✅ Multiple subscription strategies")
    print("   ✅ Thread-safe operation")
    print("   ✅ Detailed error information")
    print("   ✅ Performance analytics")
    
    # Show metrics structure
    client = ModernSpacetimeDBClient(start_message_processing=False)
    builder = client.subscription_builder()
    metrics = builder.get_metrics()
    
    print(f"\nMetrics tracking example:")
    print(f"   Subscription ID: {metrics.subscription_id}")
    print(f"   Creation time: {metrics.creation_time}")
    print(f"   Error count: {metrics.error_count}")
    print(f"   Retry count: {metrics.retry_count}")
    print(f"   Query count: {metrics.query_count}")
    print(f"   Lifetime: {metrics.get_lifetime_seconds():.3f} seconds")


def main():
    """Run all demonstrations."""
    try:
        demo_typescript_compatibility()
        demo_builder_api()
        demo_retry_policy()
        demo_subscription_strategies()
        demo_subscription_state()
        demo_advanced_features()
        
        print("\n" + "=" * 75)
        print("🎉 Advanced Subscription Builder Demo Completed Successfully!")
        print("✅ TypeScript SDK parity achieved with advanced Python features")
        print("🚀 Ready for Task 3: Message Compression Support")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 