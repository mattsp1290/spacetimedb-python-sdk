"""
Comprehensive tests for Time Utilities and Scheduling Support.

Tests the enhanced time handling capabilities including:
- EnhancedTimestamp and EnhancedTimeDuration
- ScheduleAt algebraic type
- ReducerScheduler functionality
- Time formatting and conversion utilities
- High-precision timing
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch

from spacetimedb_sdk.time_utils import (
    EnhancedTimestamp, EnhancedTimeDuration, ScheduleAt, ScheduleAtTime, ScheduleAtInterval,
    TimeRange, PrecisionTimer, TimeMetrics, TimeUnit,
    duration_from_seconds, duration_from_minutes, duration_from_hours, duration_from_days,
    timestamp_now, timestamp_from_iso
)

from spacetimedb_sdk.scheduling import (
    ReducerScheduler, ScheduledReducerCall, ScheduleResult, ScheduleStatus,
    SchedulerError, ScheduleNotFoundError, ScheduleValidationError,
    schedule_once, schedule_repeating, schedule_at
)


class TestEnhancedTimeDuration:
    """Test EnhancedTimeDuration functionality."""
    
    def test_creation_and_basic_properties(self):
        """Test basic duration creation and properties."""
        duration = EnhancedTimeDuration(1_000_000)  # 1 second
        assert duration.micros == 1_000_000
        assert duration.to_seconds() == 1.0
        assert duration.to_milliseconds() == 1000.0
        assert duration.to_nanoseconds() == 1_000_000_000
    
    def test_factory_methods(self):
        """Test duration factory methods."""
        # From seconds
        d1 = EnhancedTimeDuration.from_seconds(5.5)
        assert d1.micros == 5_500_000
        
        # From milliseconds
        d2 = EnhancedTimeDuration.from_milliseconds(1500)
        assert d2.micros == 1_500_000
        
        # From nanoseconds
        d3 = EnhancedTimeDuration.from_nanoseconds(2_000_000_000)
        assert d3.micros == 2_000_000
        
        # From timedelta
        td = timedelta(hours=1, minutes=30, seconds=45)
        d4 = EnhancedTimeDuration.from_timedelta(td)
        expected_micros = int(td.total_seconds() * 1_000_000)
        assert d4.micros == expected_micros
        
        # Zero and max
        assert EnhancedTimeDuration.zero().micros == 0
        assert EnhancedTimeDuration.max_value().micros > 0
    
    def test_arithmetic_operations(self):
        """Test duration arithmetic."""
        d1 = EnhancedTimeDuration.from_seconds(10)
        d2 = EnhancedTimeDuration.from_seconds(5)
        
        # Addition
        result = d1 + d2
        assert result.to_seconds() == 15.0
        
        # Subtraction
        result = d1 - d2
        assert result.to_seconds() == 5.0
        
        # Subtraction with clamping to zero
        result = d2 - d1
        assert result.to_seconds() == 0.0
        
        # Multiplication
        result = d1 * 2
        assert result.to_seconds() == 20.0
        
        # Division
        result = d1 / 2
        assert result.to_seconds() == 5.0
        
        # Floor division
        assert d1 // d2 == 2
        
        # Modulo
        d3 = EnhancedTimeDuration.from_seconds(7)
        result = d3 % d2
        assert result.to_seconds() == 2.0
        
        # Negation and absolute
        neg = -d1
        assert neg.micros == -d1.micros
        assert abs(neg) == d1
    
    def test_comparison_operations(self):
        """Test duration comparisons."""
        d1 = EnhancedTimeDuration.from_seconds(10)
        d2 = EnhancedTimeDuration.from_seconds(5)
        d3 = EnhancedTimeDuration.from_seconds(10)
        
        assert d1 > d2
        assert d2 < d1
        assert d1 >= d3
        assert d1 <= d3
        assert d1 == d3
        assert d1 != d2
    
    def test_utility_methods(self):
        """Test duration utility methods."""
        zero = EnhancedTimeDuration.zero()
        positive = EnhancedTimeDuration.from_seconds(5)
        negative = EnhancedTimeDuration(-1_000_000)
        
        assert zero.is_zero()
        assert not positive.is_zero()
        
        assert positive.is_positive()
        assert not zero.is_positive()
        assert not negative.is_positive()
        
        assert negative.is_negative()
        assert not positive.is_negative()
        assert not zero.is_negative()
        
        # Clamping
        min_dur = EnhancedTimeDuration.from_seconds(2)
        max_dur = EnhancedTimeDuration.from_seconds(8)
        
        small = EnhancedTimeDuration.from_seconds(1)
        large = EnhancedTimeDuration.from_seconds(10)
        middle = EnhancedTimeDuration.from_seconds(5)
        
        assert small.clamp(min_dur, max_dur) == min_dur
        assert large.clamp(min_dur, max_dur) == max_dur
        assert middle.clamp(min_dur, max_dur) == middle
    
    def test_formatting(self):
        """Test duration formatting."""
        # Microseconds
        d1 = EnhancedTimeDuration(500)
        assert "μs" in d1.format_human_readable()
        
        # Milliseconds
        d2 = EnhancedTimeDuration.from_milliseconds(1.5)
        assert "ms" in d2.format_human_readable()
        
        # Seconds
        d3 = EnhancedTimeDuration.from_seconds(30)
        assert "s" in d3.format_human_readable()
        
        # Minutes
        d4 = EnhancedTimeDuration.from_seconds(90)
        assert "min" in d4.format_human_readable()
        
        # Hours
        d5 = EnhancedTimeDuration.from_seconds(7200)
        assert "h" in d5.format_human_readable()
        
        # Days
        d6 = EnhancedTimeDuration.from_seconds(86400 * 2)
        assert "d" in d6.format_human_readable()
        
        # Zero
        assert EnhancedTimeDuration.zero().format_human_readable() == "0s"
        
        # Negative
        neg = -EnhancedTimeDuration.from_seconds(5)
        assert neg.format_human_readable().startswith("-")
        
        # Precise format
        assert d3.format_precise() == f"{d3.micros}μs"
    
    def test_validation(self):
        """Test duration validation."""
        # Valid duration
        valid = EnhancedTimeDuration.from_seconds(3600)
        valid.validate()  # Should not raise
        
        # Invalid duration (too long)
        invalid = EnhancedTimeDuration(1000 * 365 * 24 * 3600 * 1_000_000 + 1)
        with pytest.raises(ValueError):
            invalid.validate()


class TestEnhancedTimestamp:
    """Test EnhancedTimestamp functionality."""
    
    def test_creation_and_basic_properties(self):
        """Test basic timestamp creation and properties."""
        now_micros = int(time.time() * 1_000_000)
        timestamp = EnhancedTimestamp(now_micros)
        
        assert timestamp.micros_since_epoch == now_micros
        assert abs(timestamp.to_unix_timestamp() - time.time()) < 1.0
    
    def test_factory_methods(self):
        """Test timestamp factory methods."""
        # Now
        ts1 = EnhancedTimestamp.now()
        assert abs(ts1.to_unix_timestamp() - time.time()) < 1.0
        
        # From datetime
        dt = datetime(2023, 6, 15, 12, 30, 45, tzinfo=timezone.utc)
        ts2 = EnhancedTimestamp.from_datetime(dt)
        assert ts2.to_datetime() == dt
        
        # From Unix timestamp
        unix_time = time.time()
        ts3 = EnhancedTimestamp.from_unix_timestamp(unix_time)
        assert abs(ts3.to_unix_timestamp() - unix_time) < 0.001
        
        # From ISO string
        iso_str = "2023-06-15T12:30:45+00:00"
        ts4 = EnhancedTimestamp.from_iso_string(iso_str)
        assert ts4.to_iso_string().startswith("2023-06-15T12:30:45")
        
        # Epoch
        epoch = EnhancedTimestamp.epoch()
        assert epoch.micros_since_epoch == 0
        
        # Max value
        max_ts = EnhancedTimestamp.max_value()
        assert max_ts.micros_since_epoch > 0
    
    def test_timezone_handling(self):
        """Test timezone support."""
        utc_tz = timezone.utc
        est_tz = timezone(timedelta(hours=-5))
        
        # Create with timezone
        ts1 = EnhancedTimestamp.now(utc_tz)
        assert ts1.timezone_info == utc_tz
        
        # Convert timezone
        ts2 = ts1.to_timezone(est_tz)
        assert ts2.timezone_info == est_tz
        assert ts2.micros_since_epoch == ts1.micros_since_epoch  # Same instant
        
        # Convert to UTC
        ts3 = ts2.to_utc()
        assert ts3.timezone_info == timezone.utc
    
    def test_arithmetic_operations(self):
        """Test timestamp arithmetic."""
        ts = EnhancedTimestamp.now()
        duration = EnhancedTimeDuration.from_seconds(3600)  # 1 hour
        
        # Add duration
        future = ts + duration
        assert future.micros_since_epoch == ts.micros_since_epoch + duration.micros
        
        # Subtract duration
        past = ts - duration
        assert past.micros_since_epoch == ts.micros_since_epoch - duration.micros
        
        # Subtract timestamp (get duration)
        diff = future - ts
        assert isinstance(diff, EnhancedTimeDuration)
        assert diff.micros == duration.micros
    
    def test_comparison_operations(self):
        """Test timestamp comparisons."""
        ts1 = EnhancedTimestamp.now()
        time.sleep(0.001)  # Small delay
        ts2 = EnhancedTimestamp.now()
        ts3 = EnhancedTimestamp(ts1.micros_since_epoch)
        
        assert ts2 > ts1
        assert ts1 < ts2
        assert ts1 == ts3
        assert ts1 != ts2
        assert ts2 >= ts1
        assert ts1 <= ts2
    
    def test_utility_methods(self):
        """Test timestamp utility methods."""
        now = EnhancedTimestamp.now()
        past = now - EnhancedTimeDuration.from_seconds(3600)
        future = now + EnhancedTimeDuration.from_seconds(3600)
        
        # Duration calculations
        duration_since = now.duration_since(past)
        assert duration_since.to_seconds() == 3600
        
        duration_until = now.duration_until(future)
        assert duration_until.to_seconds() == 3600
        
        # Time checks
        assert past.is_past()
        assert not past.is_future()
        assert future.is_future()
        assert not future.is_past()
        
        # Day boundaries
        start = now.start_of_day()
        end = now.end_of_day()
        assert start <= now <= end
        assert start.to_datetime().hour == 0
        assert end.to_datetime().hour == 23
    
    def test_formatting(self):
        """Test timestamp formatting."""
        dt = datetime(2023, 6, 15, 12, 30, 45, tzinfo=timezone.utc)
        ts = EnhancedTimestamp.from_datetime(dt)
        
        # Human readable
        human = ts.format_human_readable()
        assert "2023-06-15" in human
        assert "12:30:45" in human
        
        # ISO string
        iso = ts.to_iso_string()
        assert iso.startswith("2023-06-15T12:30:45")
        
        iso_no_micros = ts.to_iso_string(include_microseconds=False)
        assert ".000000" not in iso_no_micros
        
        # Relative formatting
        now = EnhancedTimestamp.now()
        past = now - EnhancedTimeDuration.from_seconds(3600)
        future = now + EnhancedTimeDuration.from_seconds(3600)
        
        past_rel = past.format_relative(now)
        assert "ago" in past_rel
        
        future_rel = future.format_relative(now)
        assert "in " in future_rel
    
    def test_validation(self):
        """Test timestamp validation."""
        # Valid timestamp
        valid = EnhancedTimestamp.now()
        valid.validate()  # Should not raise
        
        # Invalid timestamp (too far in future)
        invalid_future = EnhancedTimestamp(int(datetime(2200, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000))
        with pytest.raises(ValueError):
            invalid_future.validate()
        
        # Invalid timestamp (negative)
        invalid_negative = EnhancedTimestamp(-1)
        with pytest.raises(ValueError):
            invalid_negative.validate()


class TestScheduleAt:
    """Test ScheduleAt algebraic type."""
    
    def test_schedule_at_time(self):
        """Test time-based scheduling."""
        timestamp = EnhancedTimestamp.now()
        schedule = ScheduleAt.at_time(timestamp)
        
        assert isinstance(schedule, ScheduleAtTime)
        assert schedule.is_time()
        assert not schedule.is_interval()
        assert schedule.timestamp == timestamp
        
        # Test with datetime
        dt = datetime.now(timezone.utc)
        schedule2 = ScheduleAt.at_time(dt)
        assert isinstance(schedule2, ScheduleAtTime)
        
        # Test with float (Unix timestamp)
        unix_time = time.time()
        schedule3 = ScheduleAt.at_time(unix_time)
        assert isinstance(schedule3, ScheduleAtTime)
    
    def test_schedule_at_interval(self):
        """Test interval-based scheduling."""
        duration = EnhancedTimeDuration.from_seconds(60)
        schedule = ScheduleAt.at_interval(duration)
        
        assert isinstance(schedule, ScheduleAtInterval)
        assert not schedule.is_time()
        assert schedule.is_interval()
        assert schedule.interval == duration
        
        # Test with timedelta
        td = timedelta(minutes=5)
        schedule2 = ScheduleAt.at_interval(td)
        assert isinstance(schedule2, ScheduleAtInterval)
        
        # Test with float (seconds)
        schedule3 = ScheduleAt.at_interval(30.0)
        assert isinstance(schedule3, ScheduleAtInterval)
    
    def test_duration_and_timestamp_calculations(self):
        """Test schedule calculations."""
        now = EnhancedTimestamp.now()
        
        # Time-based schedule
        future = now + EnhancedTimeDuration.from_seconds(3600)
        time_schedule = ScheduleAt.at_time(future)
        
        duration = time_schedule.to_duration_from(now)
        assert duration.to_seconds() == 3600
        
        timestamp = time_schedule.to_timestamp_from(now)
        assert timestamp == future
        
        # Interval-based schedule
        interval = EnhancedTimeDuration.from_seconds(1800)
        interval_schedule = ScheduleAt.at_interval(interval)
        
        duration = interval_schedule.to_duration_from(now)
        assert duration.to_seconds() == 1800
        
        timestamp = interval_schedule.to_timestamp_from(now)
        expected = now + interval
        assert timestamp == expected
    
    def test_validation(self):
        """Test schedule validation."""
        # Valid time schedule
        valid_time = ScheduleAt.at_time(EnhancedTimestamp.now())
        valid_time.validate()  # Should not raise
        
        # Valid interval schedule
        valid_interval = ScheduleAt.at_interval(EnhancedTimeDuration.from_seconds(60))
        valid_interval.validate()  # Should not raise
        
        # Invalid interval (zero)
        invalid_interval = ScheduleAtInterval(EnhancedTimeDuration.zero())
        with pytest.raises(ValueError):
            invalid_interval.validate()
    
    def test_string_representation(self):
        """Test string representations."""
        timestamp = EnhancedTimestamp.now()
        time_schedule = ScheduleAt.at_time(timestamp)
        
        time_str = str(time_schedule)
        assert "ScheduleAt(Time:" in time_str
        
        duration = EnhancedTimeDuration.from_seconds(60)
        interval_schedule = ScheduleAt.at_interval(duration)
        
        interval_str = str(interval_schedule)
        assert "ScheduleAt(Interval:" in interval_str


class TestTimeRange:
    """Test TimeRange functionality."""
    
    def test_time_range_operations(self):
        """Test time range operations."""
        start = EnhancedTimestamp.now()
        end = start + EnhancedTimeDuration.from_seconds(3600)
        range1 = TimeRange(start, end)
        
        # Duration
        duration = range1.duration()
        assert duration.to_seconds() == 3600
        
        # Contains
        middle = start + EnhancedTimeDuration.from_seconds(1800)
        assert range1.contains(middle)
        assert not range1.contains(start - EnhancedTimeDuration.from_seconds(1))
        
        # Overlaps
        range2 = TimeRange(
            start + EnhancedTimeDuration.from_seconds(1800),
            end + EnhancedTimeDuration.from_seconds(1800)
        )
        assert range1.overlaps(range2)
        
        range3 = TimeRange(
            end + EnhancedTimeDuration.from_seconds(1),
            end + EnhancedTimeDuration.from_seconds(3600)
        )
        assert not range1.overlaps(range3)


class TestPrecisionTimer:
    """Test PrecisionTimer functionality."""
    
    def test_timer_basic_usage(self):
        """Test basic timer usage."""
        timer = PrecisionTimer()
        
        timer.start()
        time.sleep(0.1)
        duration = timer.stop()
        
        assert duration.to_seconds() >= 0.1
        assert duration.to_seconds() < 0.2  # Should be close to 0.1
    
    def test_timer_context_manager(self):
        """Test timer as context manager."""
        with PrecisionTimer() as timer:
            time.sleep(0.05)
        
        # Timer should have stopped automatically
        assert timer._end_time is not None
    
    def test_timer_elapsed(self):
        """Test elapsed time without stopping."""
        timer = PrecisionTimer()
        timer.start()
        
        time.sleep(0.05)
        elapsed1 = timer.elapsed()
        
        time.sleep(0.05)
        elapsed2 = timer.elapsed()
        
        assert elapsed2 > elapsed1
        assert elapsed1.to_seconds() >= 0.05
    
    def test_timer_reset(self):
        """Test timer reset."""
        timer = PrecisionTimer()
        timer.start()
        timer.stop()
        
        timer.reset()
        assert timer._start_time is None
        assert timer._end_time is None
    
    def test_timer_errors(self):
        """Test timer error conditions."""
        timer = PrecisionTimer()
        
        # Stop without start
        with pytest.raises(RuntimeError):
            timer.stop()
        
        # Elapsed without start
        with pytest.raises(RuntimeError):
            timer.elapsed()


class TestTimeMetrics:
    """Test TimeMetrics functionality."""
    
    def test_metrics_basic_usage(self):
        """Test basic metrics usage."""
        metrics = TimeMetrics()
        
        metrics.start_measurement("test_op")
        time.sleep(0.05)
        duration = metrics.end_measurement("test_op")
        
        assert duration.to_seconds() >= 0.05
        
        measurements = metrics.get_measurements("test_op")
        assert len(measurements) == 1
        assert measurements[0][0] == "test_op"
        assert measurements[0][1] == duration
    
    def test_metrics_context_manager(self):
        """Test metrics context manager."""
        metrics = TimeMetrics()
        
        with metrics.measure("context_op") as ctx:
            time.sleep(0.05)
        
        assert ctx.duration is not None
        assert ctx.duration.to_seconds() >= 0.05
        
        measurements = metrics.get_measurements("context_op")
        assert len(measurements) == 1
    
    def test_metrics_aggregation(self):
        """Test metrics aggregation."""
        metrics = TimeMetrics()
        
        # Multiple measurements
        for i in range(3):
            with metrics.measure("repeated_op"):
                time.sleep(0.02)
        
        avg_duration = metrics.get_average_duration("repeated_op")
        total_duration = metrics.get_total_duration("repeated_op")
        
        assert avg_duration is not None
        assert avg_duration.to_seconds() >= 0.02
        assert total_duration.to_seconds() >= 0.06
    
    def test_metrics_filtering(self):
        """Test metrics filtering."""
        metrics = TimeMetrics()
        
        with metrics.measure("op1"):
            time.sleep(0.01)
        
        with metrics.measure("op2"):
            time.sleep(0.01)
        
        with metrics.measure("op1"):
            time.sleep(0.01)
        
        all_measurements = metrics.get_measurements()
        op1_measurements = metrics.get_measurements("op1")
        op2_measurements = metrics.get_measurements("op2")
        
        assert len(all_measurements) == 3
        assert len(op1_measurements) == 2
        assert len(op2_measurements) == 1
    
    def test_metrics_clear(self):
        """Test metrics clearing."""
        metrics = TimeMetrics()
        
        with metrics.measure("test"):
            time.sleep(0.01)
        
        assert len(metrics.get_measurements()) == 1
        
        metrics.clear()
        assert len(metrics.get_measurements()) == 0


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_duration_convenience_functions(self):
        """Test duration convenience functions."""
        d1 = duration_from_seconds(60)
        assert d1.to_seconds() == 60
        
        d2 = duration_from_minutes(2)
        assert d2.to_seconds() == 120
        
        d3 = duration_from_hours(1)
        assert d3.to_seconds() == 3600
        
        d4 = duration_from_days(1)
        assert d4.to_seconds() == 86400
    
    def test_timestamp_convenience_functions(self):
        """Test timestamp convenience functions."""
        ts1 = timestamp_now()
        assert abs(ts1.to_unix_timestamp() - time.time()) < 1.0
        
        iso_str = "2023-06-15T12:30:45+00:00"
        ts2 = timestamp_from_iso(iso_str)
        assert ts2.to_iso_string().startswith("2023-06-15T12:30:45")


class TestReducerScheduler:
    """Test ReducerScheduler functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing."""
        client = Mock()
        client.call_reducer_async = AsyncMock(return_value="success")
        return client
    
    @pytest.fixture
    def scheduler(self, mock_client):
        """Create a scheduler for testing."""
        return ReducerScheduler(mock_client)
    
    def test_scheduler_creation(self, scheduler, mock_client):
        """Test scheduler creation."""
        assert scheduler.client == mock_client
        assert len(scheduler._schedules) == 0
        assert not scheduler._running
    
    def test_schedule_reducer_time_based(self, scheduler):
        """Test scheduling a reducer at a specific time."""
        future_time = EnhancedTimestamp.now() + EnhancedTimeDuration.from_seconds(60)
        
        schedule_id = scheduler.schedule_reducer(
            "test_reducer",
            ["arg1", "arg2"],
            future_time
        )
        
        assert schedule_id in scheduler._schedules
        schedule = scheduler._schedules[schedule_id]
        assert schedule.reducer_name == "test_reducer"
        assert schedule.args == ["arg1", "arg2"]
        assert schedule.status == ScheduleStatus.PENDING
        assert isinstance(schedule.schedule, ScheduleAtTime)
    
    def test_schedule_reducer_interval_based(self, scheduler):
        """Test scheduling a reducer at intervals."""
        interval = EnhancedTimeDuration.from_seconds(30)
        
        schedule_id = scheduler.schedule_reducer(
            "periodic_reducer",
            [],
            interval
        )
        
        schedule = scheduler._schedules[schedule_id]
        assert isinstance(schedule.schedule, ScheduleAtInterval)
        assert schedule.schedule.interval == interval
    
    def test_schedule_with_various_types(self, scheduler):
        """Test scheduling with different input types."""
        # With datetime
        dt = datetime.now(timezone.utc) + timedelta(minutes=5)
        id1 = scheduler.schedule_reducer("test1", [], dt)
        assert id1 in scheduler._schedules
        
        # With timedelta
        td = timedelta(seconds=45)
        id2 = scheduler.schedule_reducer("test2", [], td)
        assert id2 in scheduler._schedules
        
        # With float (seconds)
        id3 = scheduler.schedule_reducer("test3", [], 120.0)
        assert id3 in scheduler._schedules
    
    def test_schedule_validation_errors(self, scheduler):
        """Test schedule validation errors."""
        # Invalid type
        with pytest.raises(ScheduleValidationError):
            scheduler.schedule_reducer("test", [], "invalid")
        
        # Negative numeric value
        with pytest.raises(ScheduleValidationError):
            scheduler.schedule_reducer("test", [], -5.0)
        
        # Duplicate ID
        scheduler.schedule_reducer("test", [], 60.0, schedule_id="duplicate")
        with pytest.raises(ScheduleValidationError):
            scheduler.schedule_reducer("test", [], 60.0, schedule_id="duplicate")
    
    def test_convenience_scheduling_methods(self, scheduler):
        """Test convenience scheduling methods."""
        # Schedule at time
        future = EnhancedTimestamp.now() + EnhancedTimeDuration.from_seconds(60)
        id1 = scheduler.schedule_at_time("test1", [], future)
        assert id1 in scheduler._schedules
        
        # Schedule at interval
        interval = EnhancedTimeDuration.from_seconds(30)
        id2 = scheduler.schedule_at_interval("test2", [], interval)
        assert id2 in scheduler._schedules
        
        # Schedule in seconds
        id3 = scheduler.schedule_in_seconds("test3", [], 45.0)
        assert id3 in scheduler._schedules
        
        # Schedule daily
        id4 = scheduler.schedule_daily("test4", [], hour=9, minute=30)
        assert id4 in scheduler._schedules
    
    def test_schedule_management(self, scheduler):
        """Test schedule management operations."""
        # Create some schedules
        id1 = scheduler.schedule_in_seconds("test1", [], 60.0)
        id2 = scheduler.schedule_in_seconds("test2", [], 120.0)
        
        # Get schedule
        schedule = scheduler.get_schedule(id1)
        assert schedule is not None
        assert schedule.id == id1
        
        # List schedules
        all_schedules = scheduler.list_schedules()
        assert len(all_schedules) == 2
        
        pending_schedules = scheduler.list_schedules(status=ScheduleStatus.PENDING)
        assert len(pending_schedules) == 2
        
        test1_schedules = scheduler.list_schedules(reducer_name="test1")
        assert len(test1_schedules) == 1
        
        # Cancel schedule
        assert scheduler.cancel_schedule(id1)
        assert scheduler._schedules[id1].status == ScheduleStatus.CANCELLED
        assert not scheduler.cancel_schedule("nonexistent")
        
        # Reschedule
        new_time = EnhancedTimestamp.now() + EnhancedTimeDuration.from_seconds(180)
        assert scheduler.reschedule(id2, new_time)
        assert not scheduler.reschedule("nonexistent", new_time)
    
    def test_next_execution_time(self, scheduler):
        """Test getting next execution time."""
        # No schedules
        assert scheduler.get_next_execution_time() is None
        
        # Add schedules
        now = EnhancedTimestamp.now()
        future1 = now + EnhancedTimeDuration.from_seconds(60)
        future2 = now + EnhancedTimeDuration.from_seconds(30)
        
        scheduler.schedule_at_time("test1", [], future1)
        scheduler.schedule_at_time("test2", [], future2)
        
        next_time = scheduler.get_next_execution_time()
        assert next_time == future2  # Earlier time
    
    @pytest.mark.asyncio
    async def test_scheduler_execution(self, scheduler, mock_client):
        """Test scheduler execution."""
        # Schedule a reducer to run immediately
        past_time = EnhancedTimestamp.now() - EnhancedTimeDuration.from_seconds(1)
        schedule_id = scheduler.schedule_at_time("test_reducer", ["arg1"], past_time)
        
        # Process schedules
        await scheduler._process_schedules()
        
        # Check that reducer was called
        mock_client.call_reducer_async.assert_called_once_with("test_reducer", "arg1")
        
        # Check schedule status
        schedule = scheduler._schedules[schedule_id]
        assert schedule.status == ScheduleStatus.COMPLETED
        assert schedule.execution_count == 1
        assert schedule.last_execution is not None
    
    @pytest.mark.asyncio
    async def test_scheduler_interval_execution(self, scheduler, mock_client):
        """Test interval-based scheduler execution."""
        # Schedule an interval reducer
        interval = EnhancedTimeDuration.from_seconds(1)
        schedule_id = scheduler.schedule_at_interval("interval_reducer", [], interval)
        
        # Set next execution to past to trigger immediate execution
        schedule = scheduler._schedules[schedule_id]
        schedule.next_execution = EnhancedTimestamp.now() - EnhancedTimeDuration.from_seconds(1)
        
        # Process schedules
        await scheduler._process_schedules()
        
        # Check that reducer was called
        mock_client.call_reducer_async.assert_called_once()
        
        # Check that it was rescheduled
        assert schedule.status == ScheduleStatus.PENDING
        assert schedule.execution_count == 1
        assert schedule.next_execution > EnhancedTimestamp.now()
    
    @pytest.mark.asyncio
    async def test_scheduler_error_handling(self, scheduler, mock_client):
        """Test scheduler error handling."""
        # Make the reducer call fail
        mock_client.call_reducer_async.side_effect = Exception("Test error")
        
        # Schedule a reducer
        past_time = EnhancedTimestamp.now() - EnhancedTimeDuration.from_seconds(1)
        schedule_id = scheduler.schedule_at_time("failing_reducer", [], past_time)
        
        # Process schedules
        await scheduler._process_schedules()
        
        # Check schedule status
        schedule = scheduler._schedules[schedule_id]
        assert schedule.status == ScheduleStatus.FAILED
        assert schedule.error_message == "Test error"
    
    def test_scheduler_callbacks(self, scheduler):
        """Test scheduler callbacks."""
        execution_results = []
        error_results = []
        
        def on_execution(result):
            execution_results.append(result)
        
        def on_error(schedule_id, error):
            error_results.append((schedule_id, error))
        
        scheduler.add_execution_callback(on_execution)
        scheduler.add_error_callback(on_error)
        
        # Test callback lists
        assert on_execution in scheduler._execution_callbacks
        assert on_error in scheduler._error_callbacks
        
        # Remove callbacks
        scheduler.remove_execution_callback(on_execution)
        scheduler.remove_error_callback(on_error)
        
        assert on_execution not in scheduler._execution_callbacks
        assert on_error not in scheduler._error_callbacks
    
    def test_scheduler_metrics(self, scheduler):
        """Test scheduler metrics."""
        # Initially empty
        stats = scheduler.get_execution_stats()
        assert stats['total_executions'] == 0
        assert stats['success_rate'] == 0.0
        
        # Add some mock metrics
        now = EnhancedTimestamp.now()
        duration = EnhancedTimeDuration.from_seconds(0.1)
        
        result1 = ScheduleResult("id1", now, duration, True)
        result2 = ScheduleResult("id2", now, duration, False, error="Test error")
        
        scheduler._execution_metrics = [result1, result2]
        
        stats = scheduler.get_execution_stats()
        assert stats['total_executions'] == 2
        assert stats['successful_executions'] == 1
        assert stats['failed_executions'] == 1
        assert stats['success_rate'] == 0.5
        assert stats['average_duration'].to_seconds() == 0.1
        assert stats['total_duration'].to_seconds() == 0.2
        
        # Clear metrics
        scheduler.clear_metrics()
        assert len(scheduler._execution_metrics) == 0
    
    def test_scheduler_cleanup(self, scheduler):
        """Test scheduler cleanup operations."""
        # Create various schedules
        id1 = scheduler.schedule_in_seconds("test1", [], 60.0)
        id2 = scheduler.schedule_at_interval("test2", [], 30.0)
        
        # Mark some as completed
        scheduler._schedules[id1].status = ScheduleStatus.COMPLETED
        
        # Clear completed schedules
        removed = scheduler.clear_completed_schedules()
        assert removed == 1  # Only non-interval completed schedules removed
        assert id1 not in scheduler._schedules
        assert id2 in scheduler._schedules  # Interval schedule kept


class TestSchedulingConvenienceFunctions:
    """Test scheduling convenience functions."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing."""
        client = Mock()
        client.call_reducer_async = AsyncMock(return_value="success")
        return client
    
    def test_schedule_once(self, mock_client):
        """Test schedule_once convenience function."""
        delay = EnhancedTimeDuration.from_seconds(60)
        schedule_id = schedule_once(mock_client, "test_reducer", ["arg1"], delay)
        
        assert hasattr(mock_client, '_scheduler')
        assert schedule_id in mock_client._scheduler._schedules
    
    def test_schedule_repeating(self, mock_client):
        """Test schedule_repeating convenience function."""
        interval = EnhancedTimeDuration.from_seconds(30)
        schedule_id = schedule_repeating(mock_client, "periodic_reducer", [], interval)
        
        assert hasattr(mock_client, '_scheduler')
        schedule = mock_client._scheduler._schedules[schedule_id]
        assert isinstance(schedule.schedule, ScheduleAtInterval)
    
    def test_schedule_at_convenience(self, mock_client):
        """Test schedule_at convenience function."""
        timestamp = EnhancedTimestamp.now() + EnhancedTimeDuration.from_seconds(120)
        schedule_id = schedule_at(mock_client, "timed_reducer", ["arg1"], timestamp)
        
        assert hasattr(mock_client, '_scheduler')
        schedule = mock_client._scheduler._schedules[schedule_id]
        assert isinstance(schedule.schedule, ScheduleAtTime)


class TestModernClientSchedulingIntegration:
    """Test integration between ModernSpacetimeDBClient and scheduling system."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock ModernSpacetimeDBClient for testing."""
        from unittest.mock import Mock, AsyncMock
        
        client = Mock()
        client.call_reducer_async = AsyncMock(return_value="success")
        client.call_reducer = Mock(return_value=12345)
        client.logger = Mock()
        client.register_on_event = Mock()
        client._on_event = []
        
        # Mock WebSocket client
        client.ws_client = Mock()
        client.ws_client.is_connected = True
        
        return client
    
    def test_client_scheduler_property(self, mock_client):
        """Test that ModernSpacetimeDBClient has scheduler property."""
        from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
        from spacetimedb_sdk.scheduling import ReducerScheduler
        
        # Create a real client instance for testing
        client = ModernSpacetimeDBClient()
        
        # Access scheduler property
        scheduler = client.scheduler
        
        assert isinstance(scheduler, ReducerScheduler)
        assert scheduler.client == client
    
    def test_client_call_reducer_async(self, mock_client):
        """Test that ModernSpacetimeDBClient has call_reducer_async method."""
        from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
        
        # Create a real client instance
        client = ModernSpacetimeDBClient()
        
        # Check that call_reducer_async method exists
        assert hasattr(client, 'call_reducer_async')
        assert callable(getattr(client, 'call_reducer_async'))
    
    @pytest.mark.asyncio
    async def test_scheduler_with_real_client(self):
        """Test scheduler integration with real client."""
        from spacetimedb_sdk.modern_client import ModernSpacetimeDBClient
        from spacetimedb_sdk.time_utils import EnhancedTimeDuration
        from unittest.mock import Mock, AsyncMock
        
        # Create client with mocked WebSocket
        client = ModernSpacetimeDBClient()
        client.ws_client = Mock()
        client.ws_client.is_connected = True
        client.call_reducer_async = AsyncMock(return_value="test_result")
        
        # Get scheduler
        scheduler = client.scheduler
        
        # Schedule a reducer
        schedule_id = scheduler.schedule_at_interval(
            "test_reducer",
            ["arg1", "arg2"],
            EnhancedTimeDuration.from_seconds(1)
        )
        
        assert schedule_id in scheduler._schedules
        schedule = scheduler._schedules[schedule_id]
        assert schedule.reducer_name == "test_reducer"
        assert schedule.args == ["arg1", "arg2"]
    
    def test_connection_builder_scheduling_config(self):
        """Test connection builder scheduling configuration."""
        from spacetimedb_sdk.connection_builder import SpacetimeDBConnectionBuilder
        
        builder = SpacetimeDBConnectionBuilder()
        
        # Test scheduling configuration
        result = builder.with_scheduling(auto_start=False, max_concurrent_executions=5)
        
        assert result == builder  # Should return self for chaining
        assert builder._auto_start_scheduler == False
        assert builder._max_concurrent_executions == 5
    
    def test_time_utilities_integration(self):
        """Test that time utilities work correctly."""
        from spacetimedb_sdk import (
            EnhancedTimestamp, EnhancedTimeDuration, ScheduleAt,
            duration_from_seconds, duration_from_minutes, timestamp_now
        )
        
        # Test factory functions
        duration = duration_from_seconds(60)
        assert isinstance(duration, EnhancedTimeDuration)
        assert duration.to_seconds() == 60
        
        duration_min = duration_from_minutes(5)
        assert isinstance(duration_min, EnhancedTimeDuration)
        assert duration_min.to_seconds() == 300
        
        timestamp = timestamp_now()
        assert isinstance(timestamp, EnhancedTimestamp)
        
        # Test ScheduleAt
        schedule_time = ScheduleAt.at_time(timestamp)
        assert schedule_time.is_time()
        assert not schedule_time.is_interval()
        
        schedule_interval = ScheduleAt.at_interval(duration)
        assert not schedule_interval.is_time()
        assert schedule_interval.is_interval()
    
    def test_scheduling_convenience_functions(self):
        """Test scheduling convenience functions."""
        from spacetimedb_sdk import schedule_once, schedule_repeating, schedule_at
        from spacetimedb_sdk.time_utils import EnhancedTimeDuration, EnhancedTimestamp
        from unittest.mock import Mock
        
        # Create mock client
        mock_client = Mock()
        mock_client._scheduler = None
        
        # Test schedule_once
        delay = EnhancedTimeDuration.from_seconds(30)
        schedule_id = schedule_once(mock_client, "test_reducer", ["arg1"], delay)
        
        assert hasattr(mock_client, '_scheduler')
        assert schedule_id is not None
        
        # Test schedule_repeating
        interval = EnhancedTimeDuration.from_seconds(60)
        schedule_id = schedule_repeating(mock_client, "periodic_reducer", [], interval)
        
        assert schedule_id is not None
        
        # Test schedule_at
        timestamp = EnhancedTimestamp.now() + EnhancedTimeDuration.from_seconds(120)
        schedule_id = schedule_at(mock_client, "timed_reducer", ["arg1"], timestamp)
        
        assert schedule_id is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 