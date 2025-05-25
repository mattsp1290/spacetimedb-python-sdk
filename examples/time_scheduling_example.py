"""
Time Utilities and Scheduling Example for SpacetimeDB Python SDK.

This example demonstrates the comprehensive time handling and scheduling capabilities:
- Enhanced time types with arithmetic and formatting
- ScheduleAt algebraic type for flexible scheduling
- ReducerScheduler for automated reducer execution
- High-precision timing and performance monitoring
- Real-world scheduling patterns

Use cases shown:
- Game event scheduling (tournaments, daily rewards)
- Data processing pipelines (ETL, cleanup tasks)
- Monitoring and alerting systems
- Performance benchmarking
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from spacetimedb_sdk import (
    ModernSpacetimeDBClient,
    get_logger,
    LogLevel
)

from spacetimedb_sdk.time_utils import (
    EnhancedTimestamp, EnhancedTimeDuration, ScheduleAt,
    TimeRange, PrecisionTimer, TimeMetrics,
    duration_from_seconds, duration_from_minutes, duration_from_hours, duration_from_days,
    timestamp_now, timestamp_from_iso
)

from spacetimedb_sdk.scheduling import (
    ReducerScheduler, ScheduleStatus, ScheduleResult,
    schedule_once, schedule_repeating, schedule_at
)


# Configure logging
logger = get_logger(__name__)
logger.set_level(LogLevel.INFO)


def demonstrate_time_utilities():
    """Demonstrate enhanced time utilities."""
    print("=== Time Utilities Demonstration ===\n")
    
    # 1. Creating and manipulating durations
    print("1. Duration Operations:")
    
    # Various ways to create durations
    d1 = EnhancedTimeDuration.from_seconds(30.5)
    d2 = duration_from_minutes(5)
    d3 = duration_from_hours(2)
    
    print(f"   30.5 seconds: {d1}")
    print(f"   5 minutes: {d2}")
    print(f"   2 hours: {d3}")
    
    # Arithmetic operations
    total = d1 + d2 + d3
    print(f"   Total duration: {total}")
    print(f"   In seconds: {total.to_seconds()}")
    print(f"   Human readable: {total.format_human_readable()}")
    
    # Duration comparisons and utilities
    print(f"   Is d1 positive? {d1.is_positive()}")
    print(f"   d2 > d1? {d2 > d1}")
    
    # 2. Creating and manipulating timestamps
    print("\n2. Timestamp Operations:")
    
    # Various ways to create timestamps
    now = timestamp_now()
    past = now - duration_from_hours(3)
    future = now + duration_from_days(1)
    
    print(f"   Now: {now}")
    print(f"   3 hours ago: {past}")
    print(f"   Tomorrow: {future}")
    
    # Timezone handling
    utc_time = now.to_utc()
    est_time = now.to_timezone(timezone(timedelta(hours=-5)))
    
    print(f"   UTC: {utc_time.format_human_readable()}")
    print(f"   EST: {est_time.format_human_readable()}")
    
    # Relative formatting
    print(f"   Past relative to now: {past.format_relative()}")
    print(f"   Future relative to now: {future.format_relative()}")
    
    # 3. Time ranges
    print("\n3. Time Range Operations:")
    
    meeting_start = now + duration_from_minutes(30)
    meeting_end = meeting_start + duration_from_hours(1)
    meeting_range = TimeRange(meeting_start, meeting_end)
    
    print(f"   Meeting: {meeting_start} to {meeting_end}")
    print(f"   Duration: {meeting_range.duration()}")
    
    check_time = now + duration_from_minutes(45)
    print(f"   Is {check_time} during meeting? {meeting_range.contains(check_time)}")
    
    # 4. Schedule types
    print("\n4. Schedule Types:")
    
    # Time-based schedule
    deadline = now + duration_from_hours(6)
    time_schedule = ScheduleAt.at_time(deadline)
    print(f"   Schedule at specific time: {time_schedule}")
    
    # Interval-based schedule
    interval_schedule = ScheduleAt.at_interval(duration_from_minutes(15))
    print(f"   Schedule at intervals: {interval_schedule}")
    
    # Calculate when they would execute
    print(f"   Time schedule executes in: {time_schedule.to_duration_from(now)}")
    print(f"   Interval schedule executes in: {interval_schedule.to_duration_from(now)}")


def demonstrate_precision_timing():
    """Demonstrate high-precision timing capabilities."""
    print("\n=== Precision Timing Demonstration ===\n")
    
    # 1. Basic timer usage
    print("1. Basic Timer:")
    timer = PrecisionTimer()
    
    timer.start()
    # Simulate some work
    import time
    time.sleep(0.1)
    duration = timer.stop()
    
    print(f"   Operation took: {duration}")
    print(f"   Precise: {duration.format_precise()}")
    
    # 2. Context manager usage
    print("\n2. Context Manager Timer:")
    with PrecisionTimer() as timer:
        time.sleep(0.05)
    
    print(f"   Context operation took: {timer.stop()}")
    
    # 3. Time metrics collection
    print("\n3. Time Metrics:")
    metrics = TimeMetrics()
    
    # Simulate multiple operations
    for i in range(3):
        with metrics.measure(f"operation_{i}"):
            time.sleep(0.02 + i * 0.01)
    
    # Repeated operations
    for i in range(2):
        with metrics.measure("repeated_op"):
            time.sleep(0.03)
    
    # Analyze metrics
    all_measurements = metrics.get_measurements()
    print(f"   Total measurements: {len(all_measurements)}")
    
    repeated_avg = metrics.get_average_duration("repeated_op")
    repeated_total = metrics.get_total_duration("repeated_op")
    print(f"   Repeated op average: {repeated_avg}")
    print(f"   Repeated op total: {repeated_total}")


class GameEventScheduler:
    """Example game event scheduler using SpacetimeDB scheduling."""
    
    def __init__(self, client: ModernSpacetimeDBClient):
        self.client = client
        self.scheduler = ReducerScheduler(client)
        self.event_history: List[Dict[str, Any]] = []
        
        # Set up callbacks
        self.scheduler.add_execution_callback(self._on_event_executed)
        self.scheduler.add_error_callback(self._on_event_error)
    
    def _on_event_executed(self, result: ScheduleResult):
        """Handle successful event execution."""
        self.event_history.append({
            'schedule_id': result.schedule_id,
            'execution_time': result.execution_time,
            'duration': result.duration,
            'success': result.success,
            'timestamp': timestamp_now()
        })
        logger.info(f"Game event executed successfully: {result.schedule_id}")
    
    def _on_event_error(self, schedule_id: str, error: Exception):
        """Handle event execution errors."""
        logger.error(f"Game event failed: {schedule_id} - {error}")
    
    def schedule_daily_rewards(self, hour: int = 0, minute: int = 0):
        """Schedule daily reward distribution."""
        schedule_id = self.scheduler.schedule_daily(
            "distribute_daily_rewards",
            [],
            hour=hour,
            minute=minute,
            schedule_id="daily_rewards"
        )
        logger.info(f"Scheduled daily rewards at {hour:02d}:{minute:02d}")
        return schedule_id
    
    def schedule_tournament(self, start_time: datetime, duration: timedelta):
        """Schedule a tournament event."""
        # Tournament start
        start_id = self.scheduler.schedule_at_time(
            "start_tournament",
            [{"tournament_id": "weekly_pvp", "duration_minutes": int(duration.total_seconds() / 60)}],
            start_time,
            schedule_id=f"tournament_start_{start_time.isoformat()}"
        )
        
        # Tournament end
        end_time = start_time + duration
        end_id = self.scheduler.schedule_at_time(
            "end_tournament",
            [{"tournament_id": "weekly_pvp"}],
            end_time,
            schedule_id=f"tournament_end_{end_time.isoformat()}"
        )
        
        logger.info(f"Scheduled tournament: {start_time} to {end_time}")
        return start_id, end_id
    
    def schedule_server_maintenance(self, delay: timedelta):
        """Schedule server maintenance with warnings."""
        now = timestamp_now()
        
        # Warning 1 hour before
        warning_time = now + (delay - duration_from_hours(1))
        self.scheduler.schedule_at_time(
            "send_maintenance_warning",
            [{"minutes_until": 60}],
            warning_time,
            schedule_id="maintenance_warning_60min"
        )
        
        # Warning 15 minutes before
        warning_time = now + (delay - duration_from_minutes(15))
        self.scheduler.schedule_at_time(
            "send_maintenance_warning",
            [{"minutes_until": 15}],
            warning_time,
            schedule_id="maintenance_warning_15min"
        )
        
        # Actual maintenance
        maintenance_time = now + delay
        maintenance_id = self.scheduler.schedule_at_time(
            "start_server_maintenance",
            [],
            maintenance_time,
            schedule_id="server_maintenance"
        )
        
        logger.info(f"Scheduled server maintenance in {delay}")
        return maintenance_id
    
    def schedule_periodic_cleanup(self, interval: timedelta):
        """Schedule periodic database cleanup."""
        cleanup_id = self.scheduler.schedule_at_interval(
            "cleanup_expired_data",
            [],
            interval,
            schedule_id="periodic_cleanup"
        )
        logger.info(f"Scheduled periodic cleanup every {interval}")
        return cleanup_id
    
    async def start_scheduler(self):
        """Start the event scheduler."""
        await self.scheduler.start()
        logger.info("Game event scheduler started")
    
    async def stop_scheduler(self):
        """Stop the event scheduler."""
        await self.scheduler.stop()
        logger.info("Game event scheduler stopped")
    
    def get_scheduled_events(self) -> List[Dict[str, Any]]:
        """Get all scheduled events."""
        schedules = self.scheduler.list_schedules()
        events = []
        
        for schedule in schedules:
            events.append({
                'id': schedule.id,
                'reducer_name': schedule.reducer_name,
                'status': schedule.status.name,
                'next_execution': schedule.next_execution,
                'execution_count': schedule.execution_count,
                'created_at': schedule.created_at,
                'is_interval': schedule.schedule.is_interval()
            })
        
        return events
    
    def get_event_statistics(self) -> Dict[str, Any]:
        """Get event execution statistics."""
        stats = self.scheduler.get_execution_stats()
        
        return {
            'total_events_executed': stats['total_executions'],
            'successful_events': stats['successful_executions'],
            'failed_events': stats['failed_executions'],
            'success_rate': f"{stats['success_rate']:.1%}",
            'average_execution_time': stats['average_duration'],
            'total_execution_time': stats['total_duration'],
            'events_in_history': len(self.event_history)
        }


class DataProcessingPipeline:
    """Example data processing pipeline with scheduled tasks."""
    
    def __init__(self, client: ModernSpacetimeDBClient):
        self.client = client
        self.scheduler = ReducerScheduler(client)
        self.metrics = TimeMetrics()
        
        # Pipeline configuration
        self.pipeline_config = {
            'etl_interval': duration_from_hours(6),  # Every 6 hours
            'cleanup_interval': duration_from_days(1),  # Daily
            'backup_interval': duration_from_hours(12),  # Twice daily
            'analytics_interval': duration_from_minutes(30)  # Every 30 minutes
        }
    
    def setup_pipeline(self):
        """Set up the complete data processing pipeline."""
        logger.info("Setting up data processing pipeline...")
        
        # ETL process
        self.scheduler.schedule_at_interval(
            "run_etl_process",
            [{"source": "external_api", "target": "analytics_db"}],
            self.pipeline_config['etl_interval'],
            schedule_id="etl_pipeline"
        )
        
        # Data cleanup
        self.scheduler.schedule_at_interval(
            "cleanup_old_data",
            [{"retention_days": 30}],
            self.pipeline_config['cleanup_interval'],
            schedule_id="data_cleanup"
        )
        
        # Backup process
        self.scheduler.schedule_at_interval(
            "backup_database",
            [{"backup_type": "incremental"}],
            self.pipeline_config['backup_interval'],
            schedule_id="database_backup"
        )
        
        # Analytics generation
        self.scheduler.schedule_at_interval(
            "generate_analytics_reports",
            [],
            self.pipeline_config['analytics_interval'],
            schedule_id="analytics_reports"
        )
        
        logger.info("Data processing pipeline configured")
    
    def schedule_one_time_migration(self, delay: timedelta):
        """Schedule a one-time data migration."""
        migration_time = timestamp_now() + delay
        
        migration_id = self.scheduler.schedule_at_time(
            "run_data_migration",
            [{"migration_version": "v2.1.0", "batch_size": 1000}],
            migration_time,
            schedule_id=f"migration_{migration_time.micros_since_epoch}"
        )
        
        logger.info(f"Scheduled data migration for {migration_time}")
        return migration_id
    
    def benchmark_pipeline_performance(self):
        """Benchmark pipeline performance."""
        print("\n=== Pipeline Performance Benchmark ===\n")
        
        # Simulate pipeline operations
        operations = [
            ("data_extraction", 0.5),
            ("data_transformation", 1.2),
            ("data_loading", 0.8),
            ("index_rebuild", 2.1),
            ("analytics_update", 0.3)
        ]
        
        for op_name, duration in operations:
            with self.metrics.measure(op_name):
                import time
                time.sleep(duration / 10)  # Scaled down for demo
        
        # Report results
        print("Pipeline Operation Performance:")
        for op_name, _ in operations:
            avg_duration = self.metrics.get_average_duration(op_name)
            if avg_duration:
                print(f"   {op_name}: {avg_duration}")
        
        total_duration = self.metrics.get_total_duration("data_extraction")
        for op_name, _ in operations[1:]:
            total_duration += self.metrics.get_total_duration(op_name)
        
        print(f"   Total pipeline time: {total_duration}")


async def demonstrate_scheduling_patterns():
    """Demonstrate various scheduling patterns."""
    print("\n=== Scheduling Patterns Demonstration ===\n")
    
    # Create a mock client for demonstration
    class MockClient:
        async def call_reducer_async(self, reducer_name: str, *args):
            logger.info(f"Mock reducer call: {reducer_name}({args})")
            return f"Success: {reducer_name}"
    
    client = MockClient()
    
    # 1. Simple one-time scheduling
    print("1. One-time Scheduling:")
    delay = duration_from_seconds(2)
    schedule_id = schedule_once(client, "send_notification", ["Welcome!"], delay)
    print(f"   Scheduled notification in {delay}: {schedule_id}")
    
    # 2. Repeating scheduling
    print("\n2. Repeating Scheduling:")
    interval = duration_from_seconds(5)
    repeat_id = schedule_repeating(client, "heartbeat_check", [], interval)
    print(f"   Scheduled heartbeat every {interval}: {repeat_id}")
    
    # 3. Specific time scheduling
    print("\n3. Specific Time Scheduling:")
    future_time = timestamp_now() + duration_from_seconds(10)
    time_id = schedule_at(client, "daily_report", [], future_time)
    print(f"   Scheduled report at {future_time}: {time_id}")
    
    # 4. Advanced scheduler usage
    print("\n4. Advanced Scheduler:")
    scheduler = ReducerScheduler(client)
    
    # Schedule with metadata
    metadata = {"priority": "high", "category": "system"}
    advanced_id = scheduler.schedule_reducer(
        "system_check",
        [{"check_type": "full"}],
        duration_from_seconds(3),
        metadata=metadata
    )
    print(f"   Advanced schedule with metadata: {advanced_id}")
    
    # Schedule daily task
    daily_id = scheduler.schedule_daily(
        "daily_backup",
        [],
        hour=2,
        minute=30,
        timezone_info=timezone.utc
    )
    print(f"   Daily backup at 02:30 UTC: {daily_id}")
    
    # Start scheduler and run briefly
    await scheduler.start()
    
    # Wait a moment to see some executions
    print("\n   Running scheduler for 3 seconds...")
    await asyncio.sleep(3)
    
    # Show scheduler status
    pending = scheduler.get_pending_schedules()
    stats = scheduler.get_execution_stats()
    
    print(f"   Pending schedules: {len(pending)}")
    print(f"   Execution stats: {stats}")
    
    await scheduler.stop()


def demonstrate_modern_client_scheduling():
    """Demonstrate scheduling integration with ModernSpacetimeDBClient."""
    print("=== Modern Client Scheduling Integration ===\n")
    
    from spacetimedb_sdk import (
        ModernSpacetimeDBClient,
        EnhancedTimestamp, EnhancedTimeDuration, ScheduleAt,
        duration_from_seconds, duration_from_minutes
    )
    
    # 1. Connection builder with scheduling
    print("1. Connection Builder with Scheduling:")
    
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("game_server")
              .with_scheduling(auto_start=True, max_concurrent_executions=5)
              .build())
    
    print(f"   Client created with auto-start scheduler")
    print(f"   Scheduler available: {hasattr(client, 'scheduler')}")
    
    # 2. Accessing the scheduler
    print("\n2. Scheduler Access:")
    
    scheduler = client.scheduler
    print(f"   Scheduler type: {type(scheduler).__name__}")
    print(f"   Scheduler client: {scheduler.client == client}")
    
    # 3. Scheduling examples
    print("\n3. Scheduling Examples:")
    
    # Schedule a cleanup task in 30 seconds
    cleanup_schedule = scheduler.schedule_in_seconds(
        "cleanup_expired_sessions",
        [],
        30
    )
    print(f"   Scheduled cleanup task: {cleanup_schedule}")
    
    # Schedule periodic statistics update every 5 minutes
    stats_schedule = scheduler.schedule_at_interval(
        "update_statistics",
        ["daily_stats"],
        duration_from_minutes(5)
    )
    print(f"   Scheduled periodic stats: {stats_schedule}")
    
    # Schedule a specific event at a future time
    future_time = EnhancedTimestamp.now() + duration_from_minutes(30)
    event_schedule = scheduler.schedule_at_time(
        "send_daily_rewards",
        ["all_players"],
        future_time
    )
    print(f"   Scheduled future event: {event_schedule}")
    
    # Schedule daily maintenance at 3 AM
    maintenance_schedule = scheduler.schedule_daily(
        "daily_maintenance",
        [],
        hour=3,
        minute=0
    )
    print(f"   Scheduled daily maintenance: {maintenance_schedule}")
    
    # 4. Schedule management
    print("\n4. Schedule Management:")
    
    # List all schedules
    all_schedules = scheduler.list_schedules()
    print(f"   Total schedules: {len(all_schedules)}")
    
    # List pending schedules
    pending_schedules = scheduler.get_pending_schedules()
    print(f"   Pending schedules: {len(pending_schedules)}")
    
    # Get next execution time
    next_execution = scheduler.get_next_execution_time()
    if next_execution:
        print(f"   Next execution: {next_execution.format_relative()}")
    
    # 5. Schedule modification
    print("\n5. Schedule Modification:")
    
    # Reschedule the cleanup task
    new_time = EnhancedTimestamp.now() + duration_from_seconds(60)
    rescheduled = scheduler.reschedule(cleanup_schedule, new_time)
    print(f"   Rescheduled cleanup: {rescheduled}")
    
    # Cancel the event schedule
    cancelled = scheduler.cancel_schedule(event_schedule)
    print(f"   Cancelled event: {cancelled}")
    
    print("   ✓ Modern client scheduling integration demonstrated\n")


async def demonstrate_async_scheduling():
    """Demonstrate async scheduling functionality."""
    print("=== Async Scheduling Demo ===\n")
    
    from spacetimedb_sdk import (
        ModernSpacetimeDBClient,
        EnhancedTimeDuration,
        ScheduleStatus
    )
    from unittest.mock import Mock, AsyncMock
    
    # Create a mock client for demonstration
    client = ModernSpacetimeDBClient()
    client.ws_client = Mock()
    client.ws_client.is_connected = True
    client.call_reducer_async = AsyncMock(return_value="async_result")
    
    print("1. Async Scheduler Setup:")
    scheduler = client.scheduler
    
    # Add execution callback
    def on_execution(result):
        print(f"   Execution completed: {result.schedule_id} - Success: {result.success}")
    
    scheduler.add_execution_callback(on_execution)
    
    # Add error callback
    def on_error(schedule_id, error):
        print(f"   Execution failed: {schedule_id} - Error: {error}")
    
    scheduler.add_error_callback(on_error)
    
    print("   Callbacks registered")
    
    # 2. Schedule some tasks
    print("\n2. Scheduling Async Tasks:")
    
    # Schedule immediate execution (for demo)
    past_time = EnhancedTimestamp.now() - EnhancedTimeDuration.from_seconds(1)
    immediate_schedule = scheduler.schedule_at_time(
        "immediate_task",
        ["test_arg"],
        past_time
    )
    print(f"   Scheduled immediate task: {immediate_schedule}")
    
    # Schedule interval task
    interval_schedule = scheduler.schedule_at_interval(
        "interval_task",
        [],
        EnhancedTimeDuration.from_seconds(2)
    )
    print(f"   Scheduled interval task: {interval_schedule}")
    
    # 3. Start scheduler and process
    print("\n3. Scheduler Execution:")
    
    try:
        # Start the scheduler
        await scheduler.start()
        print("   Scheduler started")
        
        # Process schedules for a short time
        await scheduler._process_schedules()
        print("   Processed schedules")
        
        # Check execution metrics
        metrics = scheduler.get_execution_metrics()
        print(f"   Execution metrics: {len(metrics)} executions")
        
        # Get execution stats
        stats = scheduler.get_execution_stats()
        print(f"   Success rate: {stats.get('success_rate', 0):.1%}")
        avg_duration = stats.get('average_duration')
        if avg_duration:
            print(f"   Average duration: {avg_duration.to_seconds():.3f}s")
        else:
            print(f"   Average duration: N/A")
        
    finally:
        # Stop the scheduler
        await scheduler.stop()
        print("   Scheduler stopped")
    
    print("   ✓ Async scheduling demonstrated\n")


def demonstrate_convenience_functions():
    """Demonstrate scheduling convenience functions."""
    print("=== Scheduling Convenience Functions ===\n")
    
    from spacetimedb_sdk import (
        schedule_once, schedule_repeating, schedule_at,
        EnhancedTimestamp, EnhancedTimeDuration,
        duration_from_minutes, duration_from_hours
    )
    from unittest.mock import Mock
    
    # Create mock client
    mock_client = Mock()
    mock_client._scheduler = None
    
    print("1. Convenience Function Usage:")
    
    # Schedule once
    delay = EnhancedTimeDuration.from_seconds(30)
    once_id = schedule_once(mock_client, "one_time_task", ["arg1"], delay)
    print(f"   schedule_once: {once_id}")
    
    # Schedule repeating
    interval = duration_from_minutes(5)
    repeat_id = schedule_repeating(mock_client, "periodic_task", [], interval)
    print(f"   schedule_repeating: {repeat_id}")
    
    # Schedule at specific time
    future_time = EnhancedTimestamp.now() + duration_from_hours(1)
    at_id = schedule_at(mock_client, "future_task", ["arg1"], future_time)
    print(f"   schedule_at: {at_id}")
    
    print(f"   Client has scheduler: {hasattr(mock_client, '_scheduler')}")
    print("   ✓ Convenience functions demonstrated\n")


def demonstrate_typescript_parity():
    """Demonstrate TypeScript SDK parity features."""
    print("=== TypeScript SDK Parity Features ===\n")
    
    from spacetimedb_sdk import (
        EnhancedTimestamp, EnhancedTimeDuration, ScheduleAt,
        ModernSpacetimeDBClient,
        duration_from_minutes
    )
    
    print("1. Time Utilities (TypeScript Parity):")
    
    # Microsecond precision timestamps
    timestamp = EnhancedTimestamp.now()
    print(f"   Current timestamp: {timestamp.micros_since_epoch} μs")
    print(f"   ISO format: {timestamp.to_iso_string()}")
    
    # Duration arithmetic
    duration1 = EnhancedTimeDuration.from_seconds(30)
    duration2 = duration_from_minutes(2)
    total_duration = duration1 + duration2
    print(f"   Duration arithmetic: {duration1} + {duration2} = {total_duration}")
    
    # Timestamp arithmetic
    future_time = timestamp + total_duration
    print(f"   Future time: {future_time.format_relative()}")
    
    print("\n2. ScheduleAt Algebraic Type (TypeScript Parity):")
    
    # Time-based schedule
    time_schedule = ScheduleAt.at_time(future_time)
    print(f"   Time schedule: {time_schedule}")
    print(f"   Is time-based: {time_schedule.is_time()}")
    print(f"   Is interval-based: {time_schedule.is_interval()}")
    
    # Interval-based schedule
    interval_schedule = ScheduleAt.at_interval(duration1)
    print(f"   Interval schedule: {interval_schedule}")
    print(f"   Is time-based: {interval_schedule.is_time()}")
    print(f"   Is interval-based: {interval_schedule.is_interval()}")
    
    print("\n3. Client Integration (TypeScript Parity):")
    
    # Connection builder pattern
    client = (ModernSpacetimeDBClient.builder()
              .with_uri("ws://localhost:3000")
              .with_module_name("test_module")
              .with_scheduling(auto_start=True)
              .build())
    
    print(f"   Client created with builder pattern")
    print(f"   Has scheduler property: {hasattr(client, 'scheduler')}")
    print(f"   Has async reducer calls: {hasattr(client, 'call_reducer_async')}")
    
    # Scheduler access
    scheduler = client.scheduler
    print(f"   Scheduler type: {type(scheduler).__name__}")
    
    print("   ✓ TypeScript parity features demonstrated\n")


async def main():
    """Run all time and scheduling demonstrations."""
    print("SpacetimeDB Python SDK - Time and Scheduling Support Demo")
    print("=" * 60)
    print()
    
    try:
        # Basic time utilities
        demonstrate_time_utilities()
        
        # Precision timing
        demonstrate_precision_timing()
        
        # Scheduling patterns
        await demonstrate_scheduling_patterns()
        
        # Modern client integration
        demonstrate_modern_client_scheduling()
        
        # Async scheduling
        await demonstrate_async_scheduling()
        
        # Convenience functions
        demonstrate_convenience_functions()
        
        # TypeScript parity
        demonstrate_typescript_parity()
        
        print("🎉 All time and scheduling demonstrations completed successfully!")
        print("\nKey Features Implemented:")
        print("✓ Microsecond precision timestamps and durations")
        print("✓ ScheduleAt algebraic type (Time | Interval)")
        print("✓ Comprehensive time arithmetic and formatting")
        print("✓ Reducer scheduling with time-based and interval-based execution")
        print("✓ Async reducer calling support")
        print("✓ Connection builder integration")
        print("✓ TypeScript SDK parity for time and scheduling")
        print("✓ Convenience functions for common scheduling patterns")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 