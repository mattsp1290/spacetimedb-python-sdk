"""
Comprehensive Time Utilities and Scheduling Support for SpacetimeDB Python SDK.

This module provides enhanced time handling capabilities including:
- Enhanced TimeDuration with arithmetic operations
- Enhanced Timestamp with timezone support
- ScheduleAt algebraic type for reducer scheduling
- Time formatting and conversion utilities
- High-precision time measurements
"""

import time
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Optional, Union, TYPE_CHECKING, List, Tuple, Dict

if TYPE_CHECKING:
    from .bsatn import BsatnWriter, BsatnReader


class TimeUnit(Enum):
    """Time units for duration calculations."""
    NANOSECONDS = auto()
    MICROSECONDS = auto()
    MILLISECONDS = auto()
    SECONDS = auto()
    MINUTES = auto()
    HOURS = auto()
    DAYS = auto()


@dataclass
class TimeRange:
    """Represents a time range with start and end timestamps."""
    start: 'EnhancedTimestamp'
    end: 'EnhancedTimestamp'
    
    def duration(self) -> 'EnhancedTimeDuration':
        """Get the duration of this time range."""
        return self.end - self.start
    
    def contains(self, timestamp: 'EnhancedTimestamp') -> bool:
        """Check if a timestamp falls within this range."""
        return self.start <= timestamp <= self.end
    
    def overlaps(self, other: 'TimeRange') -> bool:
        """Check if this range overlaps with another."""
        return self.start <= other.end and other.start <= self.end


class EnhancedTimeDuration:
    """
    Enhanced TimeDuration with comprehensive arithmetic and formatting support.
    
    Provides microsecond precision with additional utility methods for
    time calculations, formatting, and conversions.
    """
    
    def __init__(self, micros: int):
        """
        Create a TimeDuration.
        
        Args:
            micros: Duration in microseconds
        """
        self.micros = micros
    
    # Factory methods
    @classmethod
    def from_timedelta(cls, td: timedelta) -> 'EnhancedTimeDuration':
        """Create TimeDuration from a timedelta."""
        micros = int(td.total_seconds() * 1_000_000)
        return cls(micros)
    
    @classmethod
    def from_seconds(cls, seconds: float) -> 'EnhancedTimeDuration':
        """Create TimeDuration from seconds."""
        return cls(int(seconds * 1_000_000))
    
    @classmethod
    def from_milliseconds(cls, millis: float) -> 'EnhancedTimeDuration':
        """Create TimeDuration from milliseconds."""
        return cls(int(millis * 1_000))
    
    @classmethod
    def from_nanoseconds(cls, nanos: int) -> 'EnhancedTimeDuration':
        """Create TimeDuration from nanoseconds."""
        return cls(nanos // 1_000)
    
    @classmethod
    def zero(cls) -> 'EnhancedTimeDuration':
        """Create a zero duration."""
        return cls(0)
    
    @classmethod
    def max_value(cls) -> 'EnhancedTimeDuration':
        """Create maximum duration (1000 years)."""
        return cls(1000 * 365 * 24 * 3600 * 1_000_000)
    
    # Conversion methods
    def to_timedelta(self) -> timedelta:
        """Convert to a timedelta."""
        return timedelta(microseconds=self.micros)
    
    def to_seconds(self) -> float:
        """Convert to seconds as float."""
        return self.micros / 1_000_000.0
    
    def to_milliseconds(self) -> float:
        """Convert to milliseconds as float."""
        return self.micros / 1_000.0
    
    def to_nanoseconds(self) -> int:
        """Convert to nanoseconds."""
        return self.micros * 1_000
    
    def total_seconds(self) -> float:
        """Get total seconds (alias for to_seconds)."""
        return self.to_seconds()
    
    # Arithmetic operations
    def __add__(self, other: 'EnhancedTimeDuration') -> 'EnhancedTimeDuration':
        """Add two durations."""
        return EnhancedTimeDuration(self.micros + other.micros)
    
    def __sub__(self, other: 'EnhancedTimeDuration') -> 'EnhancedTimeDuration':
        """Subtract two durations."""
        return EnhancedTimeDuration(max(0, self.micros - other.micros))
    
    def __mul__(self, factor: Union[int, float]) -> 'EnhancedTimeDuration':
        """Multiply duration by a factor."""
        return EnhancedTimeDuration(int(self.micros * factor))
    
    def __truediv__(self, divisor: Union[int, float]) -> 'EnhancedTimeDuration':
        """Divide duration by a divisor."""
        return EnhancedTimeDuration(int(self.micros / divisor))
    
    def __floordiv__(self, other: 'EnhancedTimeDuration') -> int:
        """Get how many times other duration fits into this one."""
        if other.micros == 0:
            raise ZeroDivisionError("Cannot divide by zero duration")
        return self.micros // other.micros
    
    def __mod__(self, other: 'EnhancedTimeDuration') -> 'EnhancedTimeDuration':
        """Get remainder when dividing by another duration."""
        if other.micros == 0:
            raise ZeroDivisionError("Cannot modulo by zero duration")
        return EnhancedTimeDuration(self.micros % other.micros)
    
    def __neg__(self) -> 'EnhancedTimeDuration':
        """Negate duration (for calculations)."""
        return EnhancedTimeDuration(-self.micros)
    
    def __abs__(self) -> 'EnhancedTimeDuration':
        """Get absolute value of duration."""
        return EnhancedTimeDuration(abs(self.micros))
    
    # Comparison operations
    def __eq__(self, other) -> bool:
        return isinstance(other, EnhancedTimeDuration) and self.micros == other.micros
    
    def __lt__(self, other: 'EnhancedTimeDuration') -> bool:
        return self.micros < other.micros
    
    def __le__(self, other: 'EnhancedTimeDuration') -> bool:
        return self.micros <= other.micros
    
    def __gt__(self, other: 'EnhancedTimeDuration') -> bool:
        return self.micros > other.micros
    
    def __ge__(self, other: 'EnhancedTimeDuration') -> bool:
        return self.micros >= other.micros
    
    # Utility methods
    def is_zero(self) -> bool:
        """Check if duration is zero."""
        return self.micros == 0
    
    def is_positive(self) -> bool:
        """Check if duration is positive."""
        return self.micros > 0
    
    def is_negative(self) -> bool:
        """Check if duration is negative."""
        return self.micros < 0
    
    def clamp(self, min_duration: 'EnhancedTimeDuration', 
              max_duration: 'EnhancedTimeDuration') -> 'EnhancedTimeDuration':
        """Clamp duration to a range."""
        if self < min_duration:
            return min_duration
        elif self > max_duration:
            return max_duration
        return self
    
    # Formatting methods
    def format_human_readable(self) -> str:
        """Format duration in human-readable form."""
        if self.micros == 0:
            return "0s"
        
        abs_micros = abs(self.micros)
        sign = "-" if self.micros < 0 else ""
        
        # Convert to appropriate unit
        if abs_micros < 1_000:  # < 1ms
            return f"{sign}{abs_micros}μs"
        elif abs_micros < 1_000_000:  # < 1s
            return f"{sign}{abs_micros / 1_000:.1f}ms"
        elif abs_micros < 60_000_000:  # < 1min
            return f"{sign}{abs_micros / 1_000_000:.1f}s"
        elif abs_micros < 3_600_000_000:  # < 1hour
            minutes = abs_micros / 60_000_000
            return f"{sign}{minutes:.1f}min"
        elif abs_micros < 86_400_000_000:  # < 1day
            hours = abs_micros / 3_600_000_000
            return f"{sign}{hours:.1f}h"
        else:
            days = abs_micros / 86_400_000_000
            return f"{sign}{days:.1f}d"
    
    def format_precise(self) -> str:
        """Format duration with precise units."""
        return f"{self.micros}μs"
    
    # BSATN serialization
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write TimeDuration to BSATN format."""
        writer.write_i64(self.micros)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedTimeDuration':
        """Read TimeDuration from BSATN format."""
        micros = reader.read_i64()
        return cls(micros)
    
    # Validation
    def validate(self) -> None:
        """Validate duration is within reasonable bounds."""
        max_duration = 1000 * 365 * 24 * 3600 * 1_000_000  # 1000 years in microseconds
        if abs(self.micros) > max_duration:
            raise ValueError(f"Duration too long: {self.micros} microseconds")
    
    def __hash__(self) -> int:
        return hash(self.micros)
    
    def __repr__(self) -> str:
        return f"EnhancedTimeDuration({self.micros}μs)"
    
    def __str__(self) -> str:
        return self.format_human_readable()


class EnhancedTimestamp:
    """
    Enhanced Timestamp with timezone support and comprehensive operations.
    
    Provides microsecond precision with timezone handling, arithmetic operations,
    and formatting capabilities.
    """
    
    def __init__(self, micros_since_epoch: int, timezone_info: Optional[timezone] = None):
        """
        Create a Timestamp.
        
        Args:
            micros_since_epoch: Microseconds since Unix epoch
            timezone_info: Optional timezone information
        """
        self.micros_since_epoch = micros_since_epoch
        self.timezone_info = timezone_info or timezone.utc
    
    # Factory methods
    @classmethod
    def now(cls, tz: Optional[timezone] = None) -> 'EnhancedTimestamp':
        """Create a Timestamp for the current time."""
        now = datetime.now(tz or timezone.utc)
        micros = int(now.timestamp() * 1_000_000)
        return cls(micros, tz)
    
    @classmethod
    def from_datetime(cls, dt: datetime) -> 'EnhancedTimestamp':
        """Create a Timestamp from a datetime object."""
        micros = int(dt.timestamp() * 1_000_000)
        return cls(micros, dt.tzinfo)
    
    @classmethod
    def from_unix_timestamp(cls, timestamp: float, tz: Optional[timezone] = None) -> 'EnhancedTimestamp':
        """Create from Unix timestamp in seconds."""
        micros = int(timestamp * 1_000_000)
        return cls(micros, tz)
    
    @classmethod
    def from_iso_string(cls, iso_string: str) -> 'EnhancedTimestamp':
        """Create from ISO format string."""
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return cls.from_datetime(dt)
    
    @classmethod
    def epoch(cls) -> 'EnhancedTimestamp':
        """Create timestamp for Unix epoch."""
        return cls(0, timezone.utc)
    
    @classmethod
    def max_value(cls) -> 'EnhancedTimestamp':
        """Create maximum reasonable timestamp (year 2100)."""
        dt = datetime(2100, 1, 1, tzinfo=timezone.utc)
        return cls.from_datetime(dt)
    
    # Conversion methods
    def to_datetime(self, tz: Optional[timezone] = None) -> datetime:
        """Convert to a datetime object."""
        target_tz = tz or self.timezone_info
        dt = datetime.fromtimestamp(self.micros_since_epoch / 1_000_000, tz=timezone.utc)
        return dt.astimezone(target_tz)
    
    def to_unix_timestamp(self) -> float:
        """Convert to Unix timestamp in seconds."""
        return self.micros_since_epoch / 1_000_000
    
    def to_iso_string(self, include_microseconds: bool = True) -> str:
        """Convert to ISO format string."""
        dt = self.to_datetime()
        if include_microseconds:
            return dt.isoformat()
        else:
            return dt.replace(microsecond=0).isoformat()
    
    def to_utc(self) -> 'EnhancedTimestamp':
        """Convert to UTC timezone."""
        return EnhancedTimestamp(self.micros_since_epoch, timezone.utc)
    
    def to_timezone(self, tz: timezone) -> 'EnhancedTimestamp':
        """Convert to a specific timezone."""
        return EnhancedTimestamp(self.micros_since_epoch, tz)
    
    # Arithmetic operations
    def __add__(self, duration: EnhancedTimeDuration) -> 'EnhancedTimestamp':
        """Add a duration to timestamp."""
        return EnhancedTimestamp(
            self.micros_since_epoch + duration.micros,
            self.timezone_info
        )
    
    def __sub__(self, other: Union['EnhancedTimestamp', EnhancedTimeDuration]) -> Union['EnhancedTimestamp', EnhancedTimeDuration]:
        """Subtract timestamp or duration."""
        if isinstance(other, EnhancedTimestamp):
            # Return duration between timestamps
            return EnhancedTimeDuration(self.micros_since_epoch - other.micros_since_epoch)
        else:
            # Subtract duration from timestamp
            return EnhancedTimestamp(
                self.micros_since_epoch - other.micros,
                self.timezone_info
            )
    
    # Comparison operations
    def __eq__(self, other) -> bool:
        return isinstance(other, EnhancedTimestamp) and self.micros_since_epoch == other.micros_since_epoch
    
    def __lt__(self, other: 'EnhancedTimestamp') -> bool:
        return self.micros_since_epoch < other.micros_since_epoch
    
    def __le__(self, other: 'EnhancedTimestamp') -> bool:
        return self.micros_since_epoch <= other.micros_since_epoch
    
    def __gt__(self, other: 'EnhancedTimestamp') -> bool:
        return self.micros_since_epoch > other.micros_since_epoch
    
    def __ge__(self, other: 'EnhancedTimestamp') -> bool:
        return self.micros_since_epoch >= other.micros_since_epoch
    
    # Utility methods
    def duration_since(self, other: 'EnhancedTimestamp') -> EnhancedTimeDuration:
        """Get duration since another timestamp."""
        return EnhancedTimeDuration(self.micros_since_epoch - other.micros_since_epoch)
    
    def duration_until(self, other: 'EnhancedTimestamp') -> EnhancedTimeDuration:
        """Get duration until another timestamp."""
        return EnhancedTimeDuration(other.micros_since_epoch - self.micros_since_epoch)
    
    def is_past(self) -> bool:
        """Check if timestamp is in the past."""
        return self < EnhancedTimestamp.now(self.timezone_info)
    
    def is_future(self) -> bool:
        """Check if timestamp is in the future."""
        return self > EnhancedTimestamp.now(self.timezone_info)
    
    def is_today(self, tz: Optional[timezone] = None) -> bool:
        """Check if timestamp is today."""
        target_tz = tz or self.timezone_info
        today = datetime.now(target_tz).date()
        timestamp_date = self.to_datetime(target_tz).date()
        return timestamp_date == today
    
    def start_of_day(self, tz: Optional[timezone] = None) -> 'EnhancedTimestamp':
        """Get timestamp for start of the day."""
        target_tz = tz or self.timezone_info
        dt = self.to_datetime(target_tz)
        start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return EnhancedTimestamp.from_datetime(start_of_day)
    
    def end_of_day(self, tz: Optional[timezone] = None) -> 'EnhancedTimestamp':
        """Get timestamp for end of the day."""
        target_tz = tz or self.timezone_info
        dt = self.to_datetime(target_tz)
        end_of_day = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return EnhancedTimestamp.from_datetime(end_of_day)
    
    # Formatting methods
    def format_human_readable(self, tz: Optional[timezone] = None) -> str:
        """Format timestamp in human-readable form."""
        dt = self.to_datetime(tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    def format_relative(self, reference: Optional['EnhancedTimestamp'] = None) -> str:
        """Format timestamp relative to reference (or now)."""
        ref = reference or EnhancedTimestamp.now(self.timezone_info)
        duration = ref - self
        
        if duration.is_negative():
            # Future
            abs_duration = abs(duration)
            return f"in {abs_duration.format_human_readable()}"
        else:
            # Past
            return f"{duration.format_human_readable()} ago"
    
    # BSATN serialization
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write Timestamp to BSATN format."""
        writer.write_i64(self.micros_since_epoch)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnhancedTimestamp':
        """Read Timestamp from BSATN format."""
        micros = reader.read_i64()
        return cls(micros)
    
    # Validation
    def validate(self) -> None:
        """Validate timestamp is within reasonable bounds."""
        max_timestamp = int(datetime(2100, 1, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
        if self.micros_since_epoch > max_timestamp:
            raise ValueError(f"Timestamp too far in future: {self.micros_since_epoch}")
        if self.micros_since_epoch < 0:
            raise ValueError(f"Timestamp cannot be negative: {self.micros_since_epoch}")
    
    def __hash__(self) -> int:
        return hash(self.micros_since_epoch)
    
    def __repr__(self) -> str:
        return f"EnhancedTimestamp({self.micros_since_epoch}, {self.timezone_info})"
    
    def __str__(self) -> str:
        return self.format_human_readable()


class ScheduleAt:
    """
    ScheduleAt algebraic type for reducer scheduling.
    
    Represents when a scheduled reducer should execute:
    - At a specific point in time (Time variant)
    - At regular intervals (Interval variant)
    """
    
    def __init__(self):
        """Base class - use factory methods to create instances."""
        pass
    
    @classmethod
    def at_time(cls, timestamp: Union[EnhancedTimestamp, datetime, float]) -> 'ScheduleAtTime':
        """Schedule at a specific time."""
        if isinstance(timestamp, datetime):
            timestamp = EnhancedTimestamp.from_datetime(timestamp)
        elif isinstance(timestamp, (int, float)):
            timestamp = EnhancedTimestamp.from_unix_timestamp(timestamp)
        return ScheduleAtTime(timestamp)
    
    @classmethod
    def at_interval(cls, duration: Union[EnhancedTimeDuration, timedelta, float]) -> 'ScheduleAtInterval':
        """Schedule at regular intervals."""
        if isinstance(duration, timedelta):
            duration = EnhancedTimeDuration.from_timedelta(duration)
        elif isinstance(duration, (int, float)):
            duration = EnhancedTimeDuration.from_seconds(duration)
        return ScheduleAtInterval(duration)
    
    @abstractmethod
    def is_time(self) -> bool:
        """Check if this is a time-based schedule."""
        pass
    
    @abstractmethod
    def is_interval(self) -> bool:
        """Check if this is an interval-based schedule."""
        pass
    
    @abstractmethod
    def to_duration_from(self, from_time: EnhancedTimestamp) -> EnhancedTimeDuration:
        """Convert to duration from a reference time."""
        pass
    
    @abstractmethod
    def to_timestamp_from(self, from_time: EnhancedTimestamp) -> EnhancedTimestamp:
        """Convert to timestamp from a reference time."""
        pass
    
    @abstractmethod
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write ScheduleAt to BSATN format."""
        pass
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'ScheduleAt':
        """Read ScheduleAt from BSATN format."""
        tag = reader.read_tag()
        variant = reader.read_enum_header()
        
        if variant == 0:  # Interval variant
            duration = EnhancedTimeDuration.read_bsatn(reader)
            return ScheduleAtInterval(duration)
        elif variant == 1:  # Time variant
            timestamp = EnhancedTimestamp.read_bsatn(reader)
            return ScheduleAtTime(timestamp)
        else:
            raise ValueError(f"Invalid ScheduleAt variant: {variant}")
    
    @abstractmethod
    def validate(self) -> None:
        """Validate the schedule."""
        pass


class ScheduleAtTime(ScheduleAt):
    """Schedule at a specific time."""
    
    def __init__(self, timestamp: EnhancedTimestamp):
        super().__init__()
        self.timestamp = timestamp
    
    def is_time(self) -> bool:
        return True
    
    def is_interval(self) -> bool:
        return False
    
    def to_duration_from(self, from_time: EnhancedTimestamp) -> EnhancedTimeDuration:
        """Get duration from reference time to scheduled time."""
        duration = self.timestamp - from_time
        return duration if duration.is_positive() else EnhancedTimeDuration.zero()
    
    def to_timestamp_from(self, from_time: EnhancedTimestamp) -> EnhancedTimestamp:
        """Get the scheduled timestamp."""
        return self.timestamp
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write ScheduleAtTime to BSATN format."""
        writer.write_enum_header(1)  # Time variant
        self.timestamp.write_bsatn(writer)
    
    def validate(self) -> None:
        """Validate the scheduled time."""
        self.timestamp.validate()
    
    def __eq__(self, other) -> bool:
        return isinstance(other, ScheduleAtTime) and self.timestamp == other.timestamp
    
    def __repr__(self) -> str:
        return f"ScheduleAtTime({self.timestamp})"
    
    def __str__(self) -> str:
        return f"ScheduleAt(Time: {self.timestamp})"


class ScheduleAtInterval(ScheduleAt):
    """Schedule at regular intervals."""
    
    def __init__(self, interval: EnhancedTimeDuration):
        super().__init__()
        self.interval = interval
    
    def is_time(self) -> bool:
        return False
    
    def is_interval(self) -> bool:
        return True
    
    def to_duration_from(self, from_time: EnhancedTimestamp) -> EnhancedTimeDuration:
        """Get the interval duration."""
        return abs(self.interval)
    
    def to_timestamp_from(self, from_time: EnhancedTimestamp) -> EnhancedTimestamp:
        """Get next scheduled time from reference."""
        return from_time + abs(self.interval)
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Write ScheduleAtInterval to BSATN format."""
        writer.write_enum_header(0)  # Interval variant
        self.interval.write_bsatn(writer)
    
    def validate(self) -> None:
        """Validate the interval."""
        self.interval.validate()
        if self.interval.is_zero():
            raise ValueError("Interval cannot be zero")
    
    def __eq__(self, other) -> bool:
        return isinstance(other, ScheduleAtInterval) and self.interval == other.interval
    
    def __repr__(self) -> str:
        return f"ScheduleAtInterval({self.interval})"
    
    def __str__(self) -> str:
        return f"ScheduleAt(Interval: {self.interval})"


# Convenience functions for creating durations
def duration_from_seconds(seconds: float) -> EnhancedTimeDuration:
    """Create duration from seconds."""
    return EnhancedTimeDuration.from_seconds(seconds)

def duration_from_minutes(minutes: float) -> EnhancedTimeDuration:
    """Create duration from minutes."""
    return EnhancedTimeDuration.from_seconds(minutes * 60)

def duration_from_hours(hours: float) -> EnhancedTimeDuration:
    """Create duration from hours."""
    return EnhancedTimeDuration.from_seconds(hours * 3600)

def duration_from_days(days: float) -> EnhancedTimeDuration:
    """Create duration from days."""
    return EnhancedTimeDuration.from_seconds(days * 86400)

# Convenience functions for creating timestamps
def timestamp_now() -> EnhancedTimestamp:
    """Get current timestamp."""
    return EnhancedTimestamp.now()

def timestamp_from_iso(iso_string: str) -> EnhancedTimestamp:
    """Create timestamp from ISO string."""
    return EnhancedTimestamp.from_iso_string(iso_string)

# High-precision timing utilities
class PrecisionTimer:
    """High-precision timer for performance measurements."""
    
    def __init__(self):
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
    
    def start(self) -> None:
        """Start the timer."""
        self._start_time = time.perf_counter()
        self._end_time = None
    
    def stop(self) -> EnhancedTimeDuration:
        """Stop the timer and return elapsed duration."""
        if self._start_time is None:
            raise RuntimeError("Timer not started")
        
        self._end_time = time.perf_counter()
        elapsed_seconds = self._end_time - self._start_time
        return EnhancedTimeDuration.from_seconds(elapsed_seconds)
    
    def elapsed(self) -> EnhancedTimeDuration:
        """Get elapsed time without stopping."""
        if self._start_time is None:
            raise RuntimeError("Timer not started")
        
        current_time = time.perf_counter()
        elapsed_seconds = current_time - self._start_time
        return EnhancedTimeDuration.from_seconds(elapsed_seconds)
    
    def reset(self) -> None:
        """Reset the timer."""
        self._start_time = None
        self._end_time = None
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._start_time is not None and self._end_time is None:
            self.stop()


# Time-based metrics and monitoring
class TimeMetrics:
    """Collect and analyze time-based metrics."""
    
    def __init__(self):
        self._measurements: List[Tuple[str, EnhancedTimeDuration]] = []
        self._start_times: Dict[str, float] = {}
    
    def start_measurement(self, name: str) -> None:
        """Start measuring an operation."""
        self._start_times[name] = time.perf_counter()
    
    def end_measurement(self, name: str) -> EnhancedTimeDuration:
        """End measuring an operation."""
        if name not in self._start_times:
            raise ValueError(f"No measurement started for '{name}'")
        
        elapsed = time.perf_counter() - self._start_times[name]
        duration = EnhancedTimeDuration.from_seconds(elapsed)
        self._measurements.append((name, duration))
        del self._start_times[name]
        return duration
    
    def measure(self, name: str):
        """Context manager for measuring operations."""
        class MeasurementContext:
            def __init__(self, metrics: 'TimeMetrics', operation_name: str):
                self.metrics = metrics
                self.name = operation_name
                self.duration: Optional[EnhancedTimeDuration] = None
            
            def __enter__(self):
                self.metrics.start_measurement(self.name)
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.duration = self.metrics.end_measurement(self.name)
        
        return MeasurementContext(self, name)
    
    def get_measurements(self, name: Optional[str] = None) -> List[Tuple[str, EnhancedTimeDuration]]:
        """Get measurements, optionally filtered by name."""
        if name is None:
            return self._measurements.copy()
        return [(n, d) for n, d in self._measurements if n == name]
    
    def get_average_duration(self, name: str) -> Optional[EnhancedTimeDuration]:
        """Get average duration for an operation."""
        durations = [d for n, d in self._measurements if n == name]
        if not durations:
            return None
        
        total_micros = sum(d.micros for d in durations)
        return EnhancedTimeDuration(total_micros // len(durations))
    
    def get_total_duration(self, name: str) -> EnhancedTimeDuration:
        """Get total duration for an operation."""
        durations = [d for n, d in self._measurements if n == name]
        total_micros = sum(d.micros for d in durations)
        return EnhancedTimeDuration(total_micros)
    
    def clear(self) -> None:
        """Clear all measurements."""
        self._measurements.clear()
        self._start_times.clear()


# Backward compatibility aliases
TimeDuration = EnhancedTimeDuration
Timestamp = EnhancedTimestamp 