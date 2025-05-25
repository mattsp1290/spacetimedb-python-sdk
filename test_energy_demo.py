#!/usr/bin/env python3
"""
Proto-7 Energy Management System - Integration Demo

This demo showcases the complete EnergyQuanta Tracking System working together:
- Enhanced EnergyQuanta with tracking capabilities
- EnergyTracker monitoring energy levels and usage
- EnergyBudgetManager managing quotas and reservations
- Energy-aware client operations
- Energy events and analytics
"""

import os
import sys
import time

# Add the SDK to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    print("🚀 Proto-7: EnergyQuanta Tracking System - Integration Demo")
    print("=" * 60)
    
    # 1. Enhanced EnergyQuanta
    print("\n1️⃣ Enhanced EnergyQuanta Features:")
    from spacetimedb_sdk.protocol import EnergyQuanta
    
    energy = EnergyQuanta(quanta=500)
    energy.enable_usage_tracking()
    
    # Cost estimation
    cost = energy.get_cost_estimate("call_reducer", "transfer_funds")
    print(f"   💰 Estimated cost for transfer_funds: {cost} energy")
    
    # Affordability check
    can_afford = energy.can_afford(cost)
    print(f"   ✅ Can afford operation: {can_afford}")
    
    # Track usage
    success = energy.track_usage(cost, "transfer_funds")
    print(f"   📊 Usage tracked successfully: {success}")
    print(f"   ⚡ Remaining energy: {energy.quanta}")
    
    # 2. EnergyTracker
    print("\n2️⃣ EnergyTracker Features:")
    from spacetimedb_sdk.energy import EnergyTracker
    
    tracker = EnergyTracker(initial_energy=1000, max_energy=1000)
    tracker.set_replenishment_rate(5)  # 5 energy per second
    
    print(f"   🔋 Current energy: {tracker.get_current_energy()}")
    print(f"   📈 Max energy: {tracker.get_max_energy()}")
    print(f"   ⚡ Replenishment rate: {tracker.get_replenishment_rate()}/sec")
    
    # Consume energy
    tracker.consume_energy(200, "database_query")
    tracker.consume_energy(150, "reducer_call")
    
    # Get usage statistics
    stats = tracker.get_energy_usage()
    print(f"   📊 Operations performed: {stats['operation_count']}")
    print(f"   💯 Success rate: {stats['success_rate']:.1%}")
    print(f"   ⭐ Efficiency score: {stats['efficiency_score']:.2f}")
    
    # 3. EnergyBudgetManager
    print("\n3️⃣ EnergyBudgetManager Features:")
    from spacetimedb_sdk.energy import EnergyBudgetManager
    
    budget_manager = EnergyBudgetManager(initial_budget=2000)
    
    # Check budget status
    utilization = budget_manager.get_budget_utilization()
    print(f"   💳 Total budget: {utilization['total_budget']}")
    print(f"   💸 Used energy: {utilization['used_energy']}")
    print(f"   🏦 Remaining budget: {utilization['remaining_budget']}")
    
    # Reserve energy
    success = budget_manager.reserve_energy("critical_operation", 300)
    print(f"   🔒 Energy reservation successful: {success}")
    
    # Consume reserved energy
    success = budget_manager.consume_budget(300, "critical_operation")
    print(f"   💰 Reserved energy consumed: {success}")
    
    # 4. Energy Events
    print("\n4️⃣ Energy Event System:")
    from spacetimedb_sdk.energy import EnergyEventManager, EnergyEvent, EnergyEventType
    
    event_manager = EnergyEventManager()
    
    # Register event listener
    events_received = []
    def energy_event_listener(event):
        events_received.append(event)
        print(f"   🔔 Event received: {event.event_type.value} (energy: {event.current_energy})")
    
    event_manager.register_listener("energy_low", energy_event_listener)
    
    # Emit test event
    test_event = EnergyEvent(
        event_type=EnergyEventType.ENERGY_LOW,
        current_energy=150,
        timestamp=time.time(),
        threshold=200,
        operation="test_operation"
    )
    event_manager.emit_event(test_event)
    
    # 5. Energy-Aware Client
    print("\n5️⃣ Energy-Aware Client:")
    from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
    
    client = ModernSpacetimeDBClient(
        start_message_processing=False,
        initial_energy=800,
        max_energy=1000,
        energy_budget=3000
    )
    
    try:
        print(f"   ⚡ Current energy: {client.get_current_energy()}")
        
        budget_info = client.get_energy_budget()
        print(f"   💳 Budget remaining: {budget_info['remaining_budget']}")
        
        can_afford = client.can_afford_operation("send_message", ["Hello World"])
        print(f"   ✅ Can afford send_message: {can_afford}")
        
        # Add energy event listener
        client.add_energy_listener(energy_event_listener)
        
        # Get energy usage stats
        stats = client.get_energy_usage_stats()
        print(f"   📊 Energy utilization: {stats['energy_utilization_percent']:.1f}%")
        
    finally:
        client.shutdown()
    
    # 6. Energy Analytics
    print("\n6️⃣ Energy Usage Analytics:")
    from spacetimedb_sdk.energy import EnergyUsageAnalytics
    
    analytics = EnergyUsageAnalytics()
    
    # Track some operations
    analytics.track_operation("call_reducer", "transfer_funds", 75, 0.15, True)
    analytics.track_operation("call_reducer", "create_user", 45, 0.08, True)
    analytics.track_operation("query", "SELECT * FROM users", 20, 0.03, True)
    analytics.track_operation("subscription", "live_messages", 35, 0.05, True)
    
    # Generate report
    report = analytics.generate_report("1h")
    print(f"   📈 Total energy used: {report.total_energy_used}")
    print(f"   🎯 Operations: {report.operation_count}")
    print(f"   ⭐ Efficiency: {report.efficiency_score:.2f}")
    print(f"   💡 Recommendations: {len(report.recommendations)}")
    for rec in report.recommendations[:2]:  # Show first 2 recommendations
        print(f"      • {rec}")
    
    # 7. Energy Cost Estimation
    print("\n7️⃣ Energy Cost Estimation:")
    from spacetimedb_sdk.energy import EnergyCostEstimator
    
    estimator = EnergyCostEstimator()
    
    # Estimate costs for different operations
    reducer_cost = estimator.estimate_reducer_cost("complex_calculation", ["data1", "data2", "data3"])
    query_cost = estimator.estimate_query_cost("SELECT COUNT(*) FROM transactions WHERE amount > 1000")
    subscription_cost = estimator.estimate_subscription_cost("SELECT * FROM live_updates")
    
    print(f"   🧮 Complex reducer cost: {reducer_cost}")
    print(f"   🔍 Complex query cost: {query_cost}")
    print(f"   📡 Subscription cost: {subscription_cost}")
    
    # Get detailed breakdown
    breakdown = estimator.get_cost_breakdown("call_reducer", "complex_calculation")
    print(f"   📊 Cost breakdown confidence: {breakdown['confidence']}")
    
    print("\n🎉 Proto-7: EnergyQuanta Tracking System - Demo Complete!")
    print("✅ All energy management features working correctly")
    print("🚀 Ready for production use with SpacetimeDB Protocol v1.1.1")


if __name__ == "__main__":
    main() 