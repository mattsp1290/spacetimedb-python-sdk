"""
Reducer Scheduling Support for SpacetimeDB Python SDK.

This module provides scheduling capabilities for reducers using the ScheduleAt system.
It integrates with the existing reducer call infrastructure to enable time-based
and interval-based reducer execution.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Union, TYPE_CHECKING
from enum import Enum, auto

from .time_utils import (
    EnhancedTimestamp, EnhancedTimeDuration, ScheduleAt, 
    ScheduleAtTime, ScheduleAtInterval, PrecisionTimer
)

if TYPE_CHECKING:
    from .modern_client import ModernSpacetimeDBClient


class ScheduleStatus(Enum):
    """Status of a scheduled reducer."""
    PENDING = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class ScheduledReducerCall:
    """Represents a scheduled reducer call."""
    id: str
    reducer_name: str
    args: List[Any]
    schedule: ScheduleAt
    created_at: EnhancedTimestamp = field(default_factory=EnhancedTimestamp.now)
    status: ScheduleStatus = ScheduleStatus.PENDING
    execution_count: int = 0
    last_execution: Optional[EnhancedTimestamp] = None
    next_execution: Optional[EnhancedTimestamp] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate initial next execution time."""
        if self.next_execution is None:
            self.next_execution = self.schedule.to_timestamp_from(self.created_at)


@dataclass
class ScheduleResult:
    """Result of a scheduled reducer execution."""
    schedule_id: str
    execution_time: EnhancedTimestamp
    duration: EnhancedTimeDuration
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    energy_used: Optional[int] = None


class SchedulerError(Exception):
    """Base exception for scheduler errors."""
    pass


class ScheduleNotFoundError(SchedulerError):
    """Raised when a schedule is not found."""
    pass


class ScheduleValidationError(SchedulerError):
    """Raised when schedule validation fails."""
    pass


class ReducerScheduler:
    """
    Manages scheduled reducer calls with support for time-based and interval-based scheduling.
    
    Provides functionality to:
    - Schedule reducers at specific times or intervals
    - Manage scheduled reducer lifecycle
    - Handle execution results and errors
    - Support cancellation and rescheduling
    """
    
    def __init__(self, client: 'ModernSpacetimeDBClient'):
        """
        Initialize the scheduler.
        
        Args:
            client: The SpacetimeDB client to use for reducer calls
        """
        self.client = client
        self._schedules: Dict[str, ScheduledReducerCall] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger(__name__)
        self._execution_callbacks: List[Callable[[ScheduleResult], None]] = []
        self._error_callbacks: List[Callable[[str, Exception], None]] = []
        
        # Performance tracking
        self._execution_metrics: List[ScheduleResult] = []
        self._max_metrics_history = 1000
    
    def schedule_reducer(
        self,
        reducer_name: str,
        args: List[Any],
        schedule: Union[ScheduleAt, EnhancedTimestamp, EnhancedTimeDuration, datetime, timedelta, float],
        schedule_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a reducer to be called.
        
        Args:
            reducer_name: Name of the reducer to call
            args: Arguments to pass to the reducer
            schedule: When to schedule the reducer (ScheduleAt, timestamp, duration, etc.)
            schedule_id: Optional custom ID for the schedule
            metadata: Optional metadata to associate with the schedule
            
        Returns:
            The schedule ID
            
        Raises:
            ScheduleValidationError: If the schedule is invalid
        """
        # Convert schedule to ScheduleAt if needed
        if isinstance(schedule, ScheduleAt):
            schedule_at = schedule
        elif isinstance(schedule, EnhancedTimestamp):
            schedule_at = ScheduleAt.at_time(schedule)
        elif isinstance(schedule, EnhancedTimeDuration):
            schedule_at = ScheduleAt.at_interval(schedule)
        elif isinstance(schedule, datetime):
            schedule_at = ScheduleAt.at_time(EnhancedTimestamp.from_datetime(schedule))
        elif isinstance(schedule, timedelta):
            schedule_at = ScheduleAt.at_interval(EnhancedTimeDuration.from_timedelta(schedule))
        elif isinstance(schedule, (int, float)):
            # Assume seconds for numeric values
            if schedule > 0:
                schedule_at = ScheduleAt.at_interval(EnhancedTimeDuration.from_seconds(schedule))
            else:
                raise ScheduleValidationError("Numeric schedule must be positive")
        else:
            raise ScheduleValidationError(f"Invalid schedule type: {type(schedule)}")
        
        # Validate schedule
        try:
            schedule_at.validate()
        except ValueError as e:
            raise ScheduleValidationError(f"Invalid schedule: {e}")
        
        # Generate ID if not provided
        if schedule_id is None:
            import uuid
            schedule_id = str(uuid.uuid4())
        
        # Check for duplicate ID
        if schedule_id in self._schedules:
            raise ScheduleValidationError(f"Schedule ID already exists: {schedule_id}")
        
        # Create scheduled call
        scheduled_call = ScheduledReducerCall(
            id=schedule_id,
            reducer_name=reducer_name,
            args=args,
            schedule=schedule_at,
            metadata=metadata or {}
        )
        
        self._schedules[schedule_id] = scheduled_call
        
        self._logger.info(f"Scheduled reducer '{reducer_name}' with ID '{schedule_id}' for {schedule_at}")
        
        return schedule_id
    
    def schedule_at_time(
        self,
        reducer_name: str,
        args: List[Any],
        timestamp: Union[EnhancedTimestamp, datetime, float],
        schedule_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Schedule a reducer at a specific time."""
        return self.schedule_reducer(reducer_name, args, timestamp, schedule_id, metadata)
    
    def schedule_at_interval(
        self,
        reducer_name: str,
        args: List[Any],
        interval: Union[EnhancedTimeDuration, timedelta, float],
        schedule_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Schedule a reducer at regular intervals."""
        return self.schedule_reducer(reducer_name, args, interval, schedule_id, metadata)
    
    def schedule_in_seconds(
        self,
        reducer_name: str,
        args: List[Any],
        seconds: float,
        schedule_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Schedule a reducer to run after a delay in seconds."""
        future_time = EnhancedTimestamp.now() + EnhancedTimeDuration.from_seconds(seconds)
        return self.schedule_at_time(reducer_name, args, future_time, schedule_id, metadata)
    
    def schedule_daily(
        self,
        reducer_name: str,
        args: List[Any],
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        timezone_info: Optional[timezone] = None,
        schedule_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Schedule a reducer to run daily at a specific time."""
        # Calculate next occurrence
        tz = timezone_info or timezone.utc
        now = datetime.now(tz)
        target_time = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        # If target time is in the past today, schedule for tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)
        
        # Schedule at the target time, then every 24 hours
        first_execution = EnhancedTimestamp.from_datetime(target_time)
        interval = EnhancedTimeDuration.from_seconds(24 * 3600)  # 24 hours
        
        # For daily scheduling, we need to handle this specially
        # For now, just schedule the first execution
        return self.schedule_at_time(reducer_name, args, first_execution, schedule_id, metadata)
    
    def cancel_schedule(self, schedule_id: str) -> bool:
        """
        Cancel a scheduled reducer.
        
        Args:
            schedule_id: ID of the schedule to cancel
            
        Returns:
            True if the schedule was cancelled, False if not found
        """
        if schedule_id not in self._schedules:
            return False
        
        schedule = self._schedules[schedule_id]
        schedule.status = ScheduleStatus.CANCELLED
        
        self._logger.info(f"Cancelled schedule '{schedule_id}'")
        return True
    
    def reschedule(
        self,
        schedule_id: str,
        new_schedule: Union[ScheduleAt, EnhancedTimestamp, EnhancedTimeDuration, datetime, timedelta, float]
    ) -> bool:
        """
        Reschedule an existing scheduled reducer.
        
        Args:
            schedule_id: ID of the schedule to reschedule
            new_schedule: New schedule timing
            
        Returns:
            True if rescheduled successfully, False if not found
            
        Raises:
            ScheduleValidationError: If the new schedule is invalid
        """
        if schedule_id not in self._schedules:
            return False
        
        # Convert new schedule
        if isinstance(new_schedule, ScheduleAt):
            schedule_at = new_schedule
        elif isinstance(new_schedule, EnhancedTimestamp):
            schedule_at = ScheduleAt.at_time(new_schedule)
        elif isinstance(new_schedule, EnhancedTimeDuration):
            schedule_at = ScheduleAt.at_interval(new_schedule)
        elif isinstance(new_schedule, datetime):
            schedule_at = ScheduleAt.at_time(EnhancedTimestamp.from_datetime(new_schedule))
        elif isinstance(new_schedule, timedelta):
            schedule_at = ScheduleAt.at_interval(EnhancedTimeDuration.from_timedelta(new_schedule))
        elif isinstance(new_schedule, (int, float)):
            schedule_at = ScheduleAt.at_interval(EnhancedTimeDuration.from_seconds(new_schedule))
        else:
            raise ScheduleValidationError(f"Invalid schedule type: {type(new_schedule)}")
        
        # Validate new schedule
        try:
            schedule_at.validate()
        except ValueError as e:
            raise ScheduleValidationError(f"Invalid new schedule: {e}")
        
        # Update schedule
        schedule = self._schedules[schedule_id]
        schedule.schedule = schedule_at
        schedule.next_execution = schedule_at.to_timestamp_from(EnhancedTimestamp.now())
        schedule.status = ScheduleStatus.PENDING
        
        self._logger.info(f"Rescheduled '{schedule_id}' for {schedule_at}")
        return True
    
    def get_schedule(self, schedule_id: str) -> Optional[ScheduledReducerCall]:
        """Get a scheduled reducer call by ID."""
        return self._schedules.get(schedule_id)
    
    def list_schedules(
        self,
        status: Optional[ScheduleStatus] = None,
        reducer_name: Optional[str] = None
    ) -> List[ScheduledReducerCall]:
        """
        List scheduled reducer calls.
        
        Args:
            status: Optional status filter
            reducer_name: Optional reducer name filter
            
        Returns:
            List of matching scheduled calls
        """
        schedules = list(self._schedules.values())
        
        if status is not None:
            schedules = [s for s in schedules if s.status == status]
        
        if reducer_name is not None:
            schedules = [s for s in schedules if s.reducer_name == reducer_name]
        
        return schedules
    
    def get_pending_schedules(self) -> List[ScheduledReducerCall]:
        """Get all pending scheduled calls."""
        return self.list_schedules(status=ScheduleStatus.PENDING)
    
    def get_next_execution_time(self) -> Optional[EnhancedTimestamp]:
        """Get the next scheduled execution time."""
        pending = self.get_pending_schedules()
        if not pending:
            return None
        
        return min(s.next_execution for s in pending if s.next_execution is not None)
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._logger.info("Scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
        
        self._logger.info("Scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._process_schedules()
                await asyncio.sleep(1)  # Check every second
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in scheduler loop: {e}")
                for callback in self._error_callbacks:
                    try:
                        callback("scheduler_loop", e)
                    except Exception as cb_error:
                        self._logger.error(f"Error in error callback: {cb_error}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_schedules(self) -> None:
        """Process pending schedules."""
        now = EnhancedTimestamp.now()
        
        for schedule in list(self._schedules.values()):
            if schedule.status != ScheduleStatus.PENDING:
                continue
            
            if schedule.next_execution is None:
                continue
            
            if schedule.next_execution <= now:
                await self._execute_schedule(schedule)
    
    async def _execute_schedule(self, schedule: ScheduledReducerCall) -> None:
        """Execute a scheduled reducer call."""
        timer = PrecisionTimer()
        timer.start()
        
        schedule.status = ScheduleStatus.EXECUTING
        schedule.last_execution = EnhancedTimestamp.now()
        schedule.execution_count += 1
        
        self._logger.info(f"Executing scheduled reducer '{schedule.reducer_name}' (ID: {schedule.id})")
        
        try:
            # Call the reducer
            result = await self.client.call_reducer_async(
                schedule.reducer_name,
                *schedule.args
            )
            
            duration = timer.stop()
            
            # Create result
            schedule_result = ScheduleResult(
                schedule_id=schedule.id,
                execution_time=schedule.last_execution,
                duration=duration,
                success=True,
                result=result
            )
            
            schedule.status = ScheduleStatus.COMPLETED
            schedule.error_message = None
            
            # Handle interval scheduling
            if schedule.schedule.is_interval():
                # Reschedule for next interval
                schedule.next_execution = schedule.schedule.to_timestamp_from(schedule.last_execution)
                schedule.status = ScheduleStatus.PENDING
                self._logger.info(f"Rescheduled interval reducer '{schedule.reducer_name}' for {schedule.next_execution}")
            
            # Store metrics
            self._execution_metrics.append(schedule_result)
            if len(self._execution_metrics) > self._max_metrics_history:
                self._execution_metrics.pop(0)
            
            # Notify callbacks
            for callback in self._execution_callbacks:
                try:
                    callback(schedule_result)
                except Exception as e:
                    self._logger.error(f"Error in execution callback: {e}")
            
            self._logger.info(f"Successfully executed scheduled reducer '{schedule.reducer_name}' in {duration}")
            
        except Exception as e:
            duration = timer.stop()
            
            # Create error result
            schedule_result = ScheduleResult(
                schedule_id=schedule.id,
                execution_time=schedule.last_execution,
                duration=duration,
                success=False,
                error=str(e)
            )
            
            schedule.status = ScheduleStatus.FAILED
            schedule.error_message = str(e)
            
            # Store metrics
            self._execution_metrics.append(schedule_result)
            if len(self._execution_metrics) > self._max_metrics_history:
                self._execution_metrics.pop(0)
            
            # Notify callbacks
            for callback in self._execution_callbacks:
                try:
                    callback(schedule_result)
                except Exception as cb_error:
                    self._logger.error(f"Error in execution callback: {cb_error}")
            
            for callback in self._error_callbacks:
                try:
                    callback(schedule.id, e)
                except Exception as cb_error:
                    self._logger.error(f"Error in error callback: {cb_error}")
            
            self._logger.error(f"Failed to execute scheduled reducer '{schedule.reducer_name}': {e}")
    
    def add_execution_callback(self, callback: Callable[[ScheduleResult], None]) -> None:
        """Add a callback to be called when a scheduled reducer executes."""
        self._execution_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """Add a callback to be called when a scheduled reducer fails."""
        self._error_callbacks.append(callback)
    
    def remove_execution_callback(self, callback: Callable[[ScheduleResult], None]) -> None:
        """Remove an execution callback."""
        if callback in self._execution_callbacks:
            self._execution_callbacks.remove(callback)
    
    def remove_error_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """Remove an error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)
    
    def get_execution_metrics(self) -> List[ScheduleResult]:
        """Get execution metrics."""
        return self._execution_metrics.copy()
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self._execution_metrics:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'success_rate': 0.0,
                'average_duration': None,
                'total_duration': None
            }
        
        successful = [m for m in self._execution_metrics if m.success]
        failed = [m for m in self._execution_metrics if not m.success]
        
        total_duration = sum(m.duration.micros for m in self._execution_metrics)
        avg_duration = total_duration // len(self._execution_metrics)
        
        return {
            'total_executions': len(self._execution_metrics),
            'successful_executions': len(successful),
            'failed_executions': len(failed),
            'success_rate': len(successful) / len(self._execution_metrics),
            'average_duration': EnhancedTimeDuration(avg_duration),
            'total_duration': EnhancedTimeDuration(total_duration)
        }
    
    def clear_completed_schedules(self) -> int:
        """Remove completed and failed schedules. Returns number removed."""
        to_remove = [
            schedule_id for schedule_id, schedule in self._schedules.items()
            if schedule.status in (ScheduleStatus.COMPLETED, ScheduleStatus.FAILED, ScheduleStatus.CANCELLED)
            and not schedule.schedule.is_interval()  # Keep interval schedules
        ]
        
        for schedule_id in to_remove:
            del self._schedules[schedule_id]
        
        return len(to_remove)
    
    def clear_metrics(self) -> None:
        """Clear execution metrics."""
        self._execution_metrics.clear()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._running:
            # Can't await in __exit__, so just stop synchronously
            self._running = False
            if self._scheduler_task:
                self._scheduler_task.cancel()


# Convenience functions for common scheduling patterns
def schedule_once(
    client: 'ModernSpacetimeDBClient',
    reducer_name: str,
    args: List[Any],
    delay: Union[EnhancedTimeDuration, timedelta, float]
) -> str:
    """Schedule a reducer to run once after a delay."""
    if not hasattr(client, '_scheduler') or client._scheduler is None:
        client._scheduler = ReducerScheduler(client)
    
    return client._scheduler.schedule_reducer(reducer_name, args, delay)


def schedule_repeating(
    client: 'ModernSpacetimeDBClient',
    reducer_name: str,
    args: List[Any],
    interval: Union[EnhancedTimeDuration, timedelta, float]
) -> str:
    """Schedule a reducer to run repeatedly at intervals."""
    if not hasattr(client, '_scheduler') or client._scheduler is None:
        client._scheduler = ReducerScheduler(client)
    
    return client._scheduler.schedule_at_interval(reducer_name, args, interval)


def schedule_at(
    client: 'ModernSpacetimeDBClient',
    reducer_name: str,
    args: List[Any],
    timestamp: Union[EnhancedTimestamp, datetime, float]
) -> str:
    """Schedule a reducer to run at a specific time."""
    if not hasattr(client, '_scheduler') or client._scheduler is None:
        client._scheduler = ReducerScheduler(client)
    
    return client._scheduler.schedule_at_time(reducer_name, args, timestamp) 