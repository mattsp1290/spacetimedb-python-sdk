"""
Enhanced Energy Management for SpacetimeDB Protocol v1.1.1

This module provides comprehensive energy quota tracking, budget management,
usage analytics, and event-driven energy monitoring for production applications.
"""

from typing import Optional, List, Dict, Any, Callable, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
import collections
from collections import defaultdict, deque
import statistics

if TYPE_CHECKING:
    from .bsatn.writer import BsatnWriter
    from .bsatn.reader import BsatnReader


class EnergyError(Exception):
    """Base exception for energy-related errors."""
    pass


class OutOfEnergyError(EnergyError):
    """Raised when an operation cannot be performed due to insufficient energy."""
    
    def __init__(self, message: str, required: int = 0, available: int = 0, operation: str = ""):
        super().__init__(message)
        self.required = required
        self.available = available
        self.operation = operation
    
    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.operation:
            return f"{base_msg} (Operation: {self.operation}, Required: {self.required}, Available: {self.available})"
        return f"{base_msg} (Required: {self.required}, Available: {self.available})"


class EnergyExhaustedException(EnergyError):
    """Raised when energy is completely exhausted."""
    pass


class EnergyEventType(Enum):
    """Types of energy events."""
    ENERGY_LOW = "energy_low"
    ENERGY_EXHAUSTED = "energy_exhausted"
    ENERGY_REPLENISHED = "energy_replenished"
    OPERATION_DEFERRED = "operation_deferred"
    BUDGET_EXCEEDED = "budget_exceeded"
    EFFICIENCY_CHANGED = "efficiency_changed"


@dataclass
class EnergyEvent:
    """Represents an energy-related event."""
    event_type: EnergyEventType
    current_energy: int
    timestamp: float
    threshold: Optional[int] = None
    operation: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Serialize EnergyEvent to BSATN format."""
        field_count = 6
        writer.write_struct_header(field_count)
        
        writer.write_field_name("event_type")
        writer.write_string(self.event_type.value)
        
        writer.write_field_name("current_energy")
        writer.write_u32(self.current_energy)
        
        writer.write_field_name("timestamp")
        writer.write_f64(self.timestamp)
        
        writer.write_field_name("threshold")
        if self.threshold is not None:
            writer.write_option_some()
            writer.write_u32(self.threshold)
        else:
            writer.write_option_none()
        
        writer.write_field_name("operation")
        if self.operation is not None:
            writer.write_option_some()
            writer.write_string(self.operation)
        else:
            writer.write_option_none()
        
        writer.write_field_name("data")
        if self.data is not None:
            writer.write_option_some()
            # Simple JSON serialization for data dict
            import json
            writer.write_string(json.dumps(self.data))
        else:
            writer.write_option_none()
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnergyEvent':
        """Deserialize EnergyEvent from BSATN format."""
        field_count = reader.read_struct_header()
        
        event_type = None
        current_energy = 0
        timestamp = 0.0
        threshold = None
        operation = None
        data = None
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "event_type":
                event_type_str = reader.read_string()
                event_type = EnergyEventType(event_type_str)
            elif field_name == "current_energy":
                current_energy = reader.read_u32()
            elif field_name == "timestamp":
                timestamp = reader.read_f64()
            elif field_name == "threshold":
                if reader.read_option_tag():
                    threshold = reader.read_u32()
            elif field_name == "operation":
                if reader.read_option_tag():
                    operation = reader.read_string()
            elif field_name == "data":
                if reader.read_option_tag():
                    import json
                    data = json.loads(reader.read_string())
            else:
                reader.skip_value()
        
        return cls(
            event_type=event_type,
            current_energy=current_energy,
            timestamp=timestamp,
            threshold=threshold,
            operation=operation,
            data=data
        )


EnergyEventListener = Callable[[EnergyEvent], None]


@dataclass
class EnergyOperation:
    """Represents an energy-consuming operation."""
    operation_type: str  # "call_reducer", "query", "subscription"
    operation_name: str  # reducer name, query string, etc.
    energy_cost: int
    timestamp: float
    duration: Optional[float] = None
    success: bool = True
    metadata: Optional[Dict[str, Any]] = None
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Serialize EnergyOperation to BSATN format."""
        field_count = 7
        writer.write_struct_header(field_count)
        
        writer.write_field_name("operation_type")
        writer.write_string(self.operation_type)
        
        writer.write_field_name("operation_name")
        writer.write_string(self.operation_name)
        
        writer.write_field_name("energy_cost")
        writer.write_u32(self.energy_cost)
        
        writer.write_field_name("timestamp")
        writer.write_f64(self.timestamp)
        
        writer.write_field_name("duration")
        if self.duration is not None:
            writer.write_option_some()
            writer.write_f64(self.duration)
        else:
            writer.write_option_none()
        
        writer.write_field_name("success")
        writer.write_bool(self.success)
        
        writer.write_field_name("metadata")
        if self.metadata is not None:
            writer.write_option_some()
            import json
            writer.write_string(json.dumps(self.metadata))
        else:
            writer.write_option_none()
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnergyOperation':
        """Deserialize EnergyOperation from BSATN format."""
        field_count = reader.read_struct_header()
        
        operation_type = ""
        operation_name = ""
        energy_cost = 0
        timestamp = 0.0
        duration = None
        success = True
        metadata = None
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "operation_type":
                operation_type = reader.read_string()
            elif field_name == "operation_name":
                operation_name = reader.read_string()
            elif field_name == "energy_cost":
                energy_cost = reader.read_u32()
            elif field_name == "timestamp":
                timestamp = reader.read_f64()
            elif field_name == "duration":
                if reader.read_option_tag():
                    duration = reader.read_f64()
            elif field_name == "success":
                success = reader.read_bool()
            elif field_name == "metadata":
                if reader.read_option_tag():
                    import json
                    metadata = json.loads(reader.read_string())
            else:
                reader.skip_value()
        
        return cls(
            operation_type=operation_type,
            operation_name=operation_name,
            energy_cost=energy_cost,
            timestamp=timestamp,
            duration=duration,
            success=success,
            metadata=metadata
        )


@dataclass
class EnergyUsageReport:
    """Comprehensive energy usage report."""
    time_range: str
    total_energy_used: int
    operation_count: int
    efficiency_score: float
    top_consumers: List[Dict[str, Any]]
    usage_trends: Dict[str, Any]
    recommendations: List[str]
    generated_at: float = field(default_factory=time.time)
    
    def write_bsatn(self, writer: 'BsatnWriter') -> None:
        """Serialize EnergyUsageReport to BSATN format."""
        field_count = 8
        writer.write_struct_header(field_count)
        
        writer.write_field_name("time_range")
        writer.write_string(self.time_range)
        
        writer.write_field_name("total_energy_used")
        writer.write_u32(self.total_energy_used)
        
        writer.write_field_name("operation_count")
        writer.write_u32(self.operation_count)
        
        writer.write_field_name("efficiency_score")
        writer.write_f64(self.efficiency_score)
        
        writer.write_field_name("top_consumers")
        import json
        writer.write_string(json.dumps(self.top_consumers))
        
        writer.write_field_name("usage_trends")
        writer.write_string(json.dumps(self.usage_trends))
        
        writer.write_field_name("recommendations")
        writer.write_array_header(len(self.recommendations))
        for rec in self.recommendations:
            writer.write_string(rec)
        
        writer.write_field_name("generated_at")
        writer.write_f64(self.generated_at)
    
    @classmethod
    def read_bsatn(cls, reader: 'BsatnReader') -> 'EnergyUsageReport':
        """Deserialize EnergyUsageReport from BSATN format."""
        field_count = reader.read_struct_header()
        
        time_range = ""
        total_energy_used = 0
        operation_count = 0
        efficiency_score = 0.0
        top_consumers = []
        usage_trends = {}
        recommendations = []
        generated_at = time.time()
        
        for _ in range(field_count):
            field_name = reader.read_field_name()
            if field_name == "time_range":
                time_range = reader.read_string()
            elif field_name == "total_energy_used":
                total_energy_used = reader.read_u32()
            elif field_name == "operation_count":
                operation_count = reader.read_u32()
            elif field_name == "efficiency_score":
                efficiency_score = reader.read_f64()
            elif field_name == "top_consumers":
                import json
                top_consumers = json.loads(reader.read_string())
            elif field_name == "usage_trends":
                import json
                usage_trends = json.loads(reader.read_string())
            elif field_name == "recommendations":
                count = reader.read_array_header()
                recommendations = []
                for _ in range(count):
                    recommendations.append(reader.read_string())
            elif field_name == "generated_at":
                generated_at = reader.read_f64()
            else:
                reader.skip_value()
        
        return cls(
            time_range=time_range,
            total_energy_used=total_energy_used,
            operation_count=operation_count,
            efficiency_score=efficiency_score,
            top_consumers=top_consumers,
            usage_trends=usage_trends,
            recommendations=recommendations,
            generated_at=generated_at
        )


class EnergyTracker:
    """Tracks current energy levels and usage patterns."""
    
    def __init__(self, initial_energy: int = 1000, max_energy: int = 1000):
        self._current_energy = initial_energy
        self._max_energy = max_energy
        self._replenishment_rate = 10  # energy per second
        self._last_replenishment = time.time()
        self._usage_history: deque = deque(maxlen=1000)  # Recent operations
        self._lock = threading.Lock()
    
    def get_current_energy(self) -> int:
        """Get current energy level after applying replenishment."""
        with self._lock:
            self._apply_replenishment()
            return self._current_energy
    
    def get_max_energy(self) -> int:
        """Get maximum energy capacity."""
        return self._max_energy
    
    def get_replenishment_rate(self) -> float:
        """Get energy replenishment rate (energy per second)."""
        return self._replenishment_rate
    
    def set_replenishment_rate(self, rate: float) -> None:
        """Set energy replenishment rate."""
        with self._lock:
            self._replenishment_rate = max(0, rate)
    
    def consume_energy(self, amount: int, operation: str = "") -> bool:
        """
        Consume energy for an operation.
        
        Args:
            amount: Energy to consume
            operation: Operation description for tracking
            
        Returns:
            True if energy was successfully consumed, False if insufficient
        """
        with self._lock:
            self._apply_replenishment()
            
            if self._current_energy >= amount:
                self._current_energy -= amount
                
                # Track the operation
                operation_record = EnergyOperation(
                    operation_type="generic",
                    operation_name=operation,
                    energy_cost=amount,
                    timestamp=time.time(),
                    success=True
                )
                self._usage_history.append(operation_record)
                
                return True
            else:
                # Track failed operation
                operation_record = EnergyOperation(
                    operation_type="generic",
                    operation_name=operation,
                    energy_cost=amount,
                    timestamp=time.time(),
                    success=False
                )
                self._usage_history.append(operation_record)
                
                return False
    
    def track_operation(self, operation_type: str, operation_name: str, 
                       energy_cost: int, duration: float = None, 
                       success: bool = True, metadata: Dict[str, Any] = None) -> None:
        """Track an energy-consuming operation."""
        with self._lock:
            operation = EnergyOperation(
                operation_type=operation_type,
                operation_name=operation_name,
                energy_cost=energy_cost,
                timestamp=time.time(),
                duration=duration,
                success=success,
                metadata=metadata or {}
            )
            self._usage_history.append(operation)
    
    def predict_energy_cost(self, operation_type: str, operation_name: str) -> int:
        """
        Predict energy cost based on historical data.
        
        Args:
            operation_type: Type of operation
            operation_name: Specific operation name
            
        Returns:
            Predicted energy cost
        """
        with self._lock:
            # Find similar operations in history
            similar_ops = [
                op for op in self._usage_history
                if op.operation_type == operation_type and op.operation_name == operation_name
            ]
            
            if similar_ops:
                costs = [op.energy_cost for op in similar_ops]
                # Use median for more stable prediction
                return int(statistics.median(costs))
            else:
                # Default cost estimates
                return self._get_default_cost(operation_type)
    
    def get_energy_usage(self, time_range: Optional[float] = None) -> Dict[str, Any]:
        """
        Get energy usage statistics.
        
        Args:
            time_range: Time range in seconds (None for all time)
            
        Returns:
            Usage statistics dictionary
        """
        with self._lock:
            now = time.time()
            cutoff_time = now - time_range if time_range else 0
            
            relevant_ops = [
                op for op in self._usage_history
                if op.timestamp >= cutoff_time
            ]
            
            if not relevant_ops:
                return {
                    'total_energy_used': 0,
                    'operation_count': 0,
                    'success_rate': 1.0,
                    'average_cost': 0,
                    'efficiency_score': 1.0
                }
            
            total_energy = sum(op.energy_cost for op in relevant_ops if op.success)
            operation_count = len(relevant_ops)
            successful_ops = sum(1 for op in relevant_ops if op.success)
            success_rate = successful_ops / operation_count if operation_count > 0 else 1.0
            
            costs = [op.energy_cost for op in relevant_ops if op.success]
            average_cost = statistics.mean(costs) if costs else 0
            
            # Efficiency score based on success rate and cost stability
            cost_variance = statistics.variance(costs) if len(costs) > 1 else 0
            efficiency_score = success_rate * (1 / (1 + cost_variance / 100))
            
            return {
                'total_energy_used': total_energy,
                'operation_count': operation_count,
                'success_rate': success_rate,
                'average_cost': average_cost,
                'efficiency_score': min(1.0, efficiency_score)
            }
    
    def _apply_replenishment(self) -> None:
        """Apply energy replenishment based on time elapsed."""
        now = time.time()
        elapsed = now - self._last_replenishment
        
        if elapsed > 0:
            replenished = int(elapsed * self._replenishment_rate)
            self._current_energy = min(self._max_energy, self._current_energy + replenished)
            self._last_replenishment = now
    
    def _get_default_cost(self, operation_type: str) -> int:
        """Get default energy cost for operation types."""
        defaults = {
            'call_reducer': 50,
            'query': 25,
            'subscription': 30,
            'one_off_query': 20,
            'generic': 10
        }
        return defaults.get(operation_type, 10)


class EnergyBudgetManager:
    """Manages energy budgets and quotas."""
    
    def __init__(self, initial_budget: int = 5000):
        self._budget = initial_budget
        self._used_energy = 0
        self._reserved_energy = 0
        self._reservations: Dict[str, int] = {}
        self._budget_reset_time = time.time()
        self._budget_period = 3600  # 1 hour in seconds
        self._lock = threading.Lock()
    
    def set_budget(self, budget: int, period: float = 3600) -> None:
        """
        Set energy budget for a given period.
        
        Args:
            budget: Total energy budget
            period: Budget period in seconds
        """
        with self._lock:
            self._budget = budget
            self._budget_period = period
            self._reset_budget_if_needed()
    
    def get_budget(self) -> int:
        """Get total budget."""
        return self._budget
    
    def get_remaining_budget(self) -> int:
        """Get remaining budget after used and reserved energy."""
        with self._lock:
            self._reset_budget_if_needed()
            return max(0, self._budget - self._used_energy - self._reserved_energy)
    
    def get_used_energy(self) -> int:
        """Get energy used in current budget period."""
        with self._lock:
            self._reset_budget_if_needed()
            return self._used_energy
    
    def can_execute_operation(self, operation_type: str, estimated_cost: int) -> bool:
        """
        Check if an operation can be executed within budget.
        
        Args:
            operation_type: Type of operation
            estimated_cost: Estimated energy cost
            
        Returns:
            True if operation can be executed
        """
        with self._lock:
            self._reset_budget_if_needed()
            return (self._used_energy + self._reserved_energy + estimated_cost) <= self._budget
    
    def reserve_energy(self, reservation_id: str, amount: int) -> bool:
        """
        Reserve energy for a future operation.
        
        Args:
            reservation_id: Unique identifier for the reservation
            amount: Amount of energy to reserve
            
        Returns:
            True if reservation was successful
        """
        with self._lock:
            self._reset_budget_if_needed()
            
            if (self._used_energy + self._reserved_energy + amount) <= self._budget:
                self._reservations[reservation_id] = amount
                self._reserved_energy += amount
                return True
            return False
    
    def release_energy(self, reservation_id: str) -> bool:
        """
        Release a previously made energy reservation.
        
        Args:
            reservation_id: Unique identifier for the reservation
            
        Returns:
            True if reservation was found and released
        """
        with self._lock:
            if reservation_id in self._reservations:
                amount = self._reservations.pop(reservation_id)
                self._reserved_energy -= amount
                return True
            return False
    
    def consume_budget(self, amount: int, reservation_id: str = None) -> bool:
        """
        Consume energy from budget.
        
        Args:
            amount: Energy amount to consume
            reservation_id: Optional reservation to use
            
        Returns:
            True if consumption was successful
        """
        with self._lock:
            self._reset_budget_if_needed()
            
            if reservation_id and reservation_id in self._reservations:
                # Use reservation
                reserved_amount = self._reservations.pop(reservation_id)
                self._reserved_energy -= reserved_amount
                self._used_energy += amount
                return True
            elif (self._used_energy + amount) <= (self._budget - self._reserved_energy):
                # Use available budget
                self._used_energy += amount
                return True
            else:
                return False
    
    def get_budget_utilization(self) -> Dict[str, Any]:
        """Get comprehensive budget utilization statistics."""
        with self._lock:
            self._reset_budget_if_needed()
            
            # Calculate values directly without calling other methods that acquire locks
            remaining_budget = max(0, self._budget - self._used_energy - self._reserved_energy)
            utilization_percent = (self._used_energy / self._budget * 100) if self._budget > 0 else 0
            reserved_percent = (self._reserved_energy / self._budget * 100) if self._budget > 0 else 0
            
            time_remaining = self._budget_period - (time.time() - self._budget_reset_time)
            
            return {
                'total_budget': self._budget,
                'used_energy': self._used_energy,
                'reserved_energy': self._reserved_energy,
                'remaining_budget': remaining_budget,
                'utilization_percent': utilization_percent,
                'reserved_percent': reserved_percent,
                'time_remaining_seconds': max(0, time_remaining),
                'budget_period_seconds': self._budget_period,
                'active_reservations': len(self._reservations)
            }
    
    def _reset_budget_if_needed(self) -> None:
        """Reset budget if the budget period has elapsed."""
        now = time.time()
        if (now - self._budget_reset_time) >= self._budget_period:
            self._used_energy = 0
            self._reserved_energy = 0
            self._reservations.clear()
            self._budget_reset_time = now


class EnergyEventManager:
    """Manages energy-related events and notifications."""
    
    def __init__(self):
        self._listeners: Dict[str, List[EnergyEventListener]] = defaultdict(list)
        self._event_history: deque = deque(maxlen=500)
        self._lock = threading.Lock()
    
    def register_listener(self, event_type: str, listener: EnergyEventListener) -> None:
        """Register an event listener for specific event types."""
        with self._lock:
            self._listeners[event_type].append(listener)
    
    def unregister_listener(self, event_type: str, listener: EnergyEventListener) -> None:
        """Unregister an event listener."""
        with self._lock:
            if event_type in self._listeners:
                try:
                    self._listeners[event_type].remove(listener)
                except ValueError:
                    pass
    
    def emit_event(self, event: EnergyEvent) -> None:
        """Emit an energy event to all registered listeners."""
        with self._lock:
            self._event_history.append(event)
            
            # Notify listeners
            event_type_str = event.event_type.value
            for listener in self._listeners.get(event_type_str, []):
                try:
                    listener(event)
                except Exception as e:
                    # Log error but don't break other listeners
                    print(f"Error in energy event listener: {e}")
    
    def get_event_history(self, event_type: Optional[EnergyEventType] = None) -> List[EnergyEvent]:
        """Get event history, optionally filtered by event type."""
        with self._lock:
            if event_type:
                return [e for e in self._event_history if e.event_type == event_type]
            return list(self._event_history)


class EnergyCostEstimator:
    """Estimates energy costs for different operations."""
    
    def __init__(self):
        self._cost_history: Dict[str, List[int]] = defaultdict(list)
        self._base_costs = {
            'call_reducer': 50,
            'query': 25,
            'subscription': 30,
            'one_off_query': 20
        }
        self._lock = threading.Lock()
    
    def estimate_reducer_cost(self, reducer_name: str, args: List[Any] = None) -> int:
        """Estimate energy cost for a reducer call."""
        with self._lock:
            base_cost = self._base_costs['call_reducer']
            
            # Adjust based on historical data
            history_key = f"call_reducer:{reducer_name}"
            if history_key in self._cost_history:
                historical_costs = self._cost_history[history_key]
                avg_cost = statistics.mean(historical_costs)
                return int(avg_cost)
            
            # Adjust based on argument complexity
            if args:
                complexity_factor = min(1.5, 1 + len(args) * 0.1)
                base_cost = int(base_cost * complexity_factor)
            
            return base_cost
    
    def estimate_query_cost(self, query: str) -> int:
        """Estimate energy cost for a query."""
        with self._lock:
            base_cost = self._base_costs['query']
            
            # Simple heuristics based on query complexity
            query_lower = query.lower()
            
            # JOIN operations are more expensive
            if 'join' in query_lower:
                base_cost = int(base_cost * 1.5)
            
            # Aggregate functions are more expensive
            if any(func in query_lower for func in ['count', 'sum', 'avg', 'max', 'min']):
                base_cost = int(base_cost * 1.3)
            
            # ORDER BY is more expensive
            if 'order by' in query_lower:
                base_cost = int(base_cost * 1.2)
            
            return base_cost
    
    def estimate_subscription_cost(self, query: str) -> int:
        """Estimate energy cost for a subscription."""
        query_cost = self.estimate_query_cost(query)
        # Subscriptions have ongoing cost
        return int(query_cost * 1.2)
    
    def calibrate_costs(self, operation_type: str, operation_name: str, actual_cost: int) -> None:
        """Calibrate cost estimates based on actual usage."""
        with self._lock:
            history_key = f"{operation_type}:{operation_name}"
            self._cost_history[history_key].append(actual_cost)
            
            # Keep only recent history
            if len(self._cost_history[history_key]) > 50:
                self._cost_history[history_key] = self._cost_history[history_key][-50:]
    
    def get_cost_breakdown(self, operation_type: str, operation_name: str) -> Dict[str, Any]:
        """Get detailed cost breakdown and estimation factors."""
        estimated_cost = 0
        factors = []
        
        if operation_type == 'call_reducer':
            estimated_cost = self.estimate_reducer_cost(operation_name)
            factors.append(f"Base reducer cost: {self._base_costs['call_reducer']}")
        elif operation_type == 'query':
            estimated_cost = self.estimate_query_cost(operation_name)
            factors.append(f"Base query cost: {self._base_costs['query']}")
        elif operation_type == 'subscription':
            estimated_cost = self.estimate_subscription_cost(operation_name)
            factors.append(f"Base subscription cost: {self._base_costs['subscription']}")
        
        history_key = f"{operation_type}:{operation_name}"
        historical_data = None
        if history_key in self._cost_history:
            costs = self._cost_history[history_key]
            historical_data = {
                'sample_count': len(costs),
                'average_cost': statistics.mean(costs),
                'min_cost': min(costs),
                'max_cost': max(costs)
            }
        
        return {
            'estimated_cost': estimated_cost,
            'factors': factors,
            'historical_data': historical_data,
            'confidence': 'high' if historical_data and historical_data['sample_count'] >= 10 else 'medium'
        }


class EnergyUsageAnalytics:
    """Comprehensive energy usage analytics and reporting."""
    
    def __init__(self):
        self._operations: deque = deque(maxlen=5000)
        self._lock = threading.Lock()
    
    def track_operation(self, operation_type: str, operation_name: str, 
                       energy_cost: int, duration: float, success: bool = True,
                       metadata: Dict[str, Any] = None) -> None:
        """Track an energy-consuming operation for analytics."""
        with self._lock:
            operation = EnergyOperation(
                operation_type=operation_type,
                operation_name=operation_name,
                energy_cost=energy_cost,
                timestamp=time.time(),
                duration=duration,
                success=success,
                metadata=metadata or {}
            )
            self._operations.append(operation)
    
    def generate_report(self, time_range: str = "1h") -> EnergyUsageReport:
        """Generate comprehensive energy usage report."""
        with self._lock:
            # Parse time range
            time_range_seconds = self._parse_time_range(time_range)
            cutoff_time = time.time() - time_range_seconds
            
            relevant_ops = [
                op for op in self._operations
                if op.timestamp >= cutoff_time
            ]
            
            if not relevant_ops:
                return EnergyUsageReport(
                    time_range=time_range,
                    total_energy_used=0,
                    operation_count=0,
                    efficiency_score=1.0,
                    top_consumers=[],
                    usage_trends={},
                    recommendations=[]
                )
            
            # Calculate metrics
            total_energy = sum(op.energy_cost for op in relevant_ops if op.success)
            operation_count = len(relevant_ops)
            successful_ops = [op for op in relevant_ops if op.success]
            success_rate = len(successful_ops) / operation_count if operation_count > 0 else 1.0
            
            # Calculate efficiency score
            if successful_ops:
                avg_cost = statistics.mean([op.energy_cost for op in successful_ops])
                cost_variance = statistics.variance([op.energy_cost for op in successful_ops]) if len(successful_ops) > 1 else 0
                efficiency_score = success_rate * (1 / (1 + cost_variance / avg_cost))
            else:
                efficiency_score = 0.0
            
            # Get top consumers
            top_consumers = self._get_top_consumers(relevant_ops)
            
            # Analyze usage trends
            usage_trends = self._analyze_usage_trends(relevant_ops, time_range_seconds)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(relevant_ops, efficiency_score)
            
            return EnergyUsageReport(
                time_range=time_range,
                total_energy_used=total_energy,
                operation_count=operation_count,
                efficiency_score=min(1.0, efficiency_score),
                top_consumers=top_consumers,
                usage_trends=usage_trends,
                recommendations=recommendations
            )
    
    def get_top_consumers(self, limit: int = 10, time_range: str = "1h") -> List[Dict[str, Any]]:
        """Get top energy-consuming operations."""
        with self._lock:
            time_range_seconds = self._parse_time_range(time_range)
            cutoff_time = time.time() - time_range_seconds
            
            relevant_ops = [
                op for op in self._operations
                if op.timestamp >= cutoff_time and op.success
            ]
            
            return self._get_top_consumers(relevant_ops, limit)
    
    def get_usage_trends(self, time_range: str = "24h") -> Dict[str, Any]:
        """Get energy usage trends over time."""
        with self._lock:
            time_range_seconds = self._parse_time_range(time_range)
            cutoff_time = time.time() - time_range_seconds
            
            relevant_ops = [
                op for op in self._operations
                if op.timestamp >= cutoff_time
            ]
            
            return self._analyze_usage_trends(relevant_ops, time_range_seconds)
    
    def get_efficiency_metrics(self) -> Dict[str, Any]:
        """Get efficiency metrics and performance indicators."""
        with self._lock:
            if not self._operations:
                return {'efficiency_score': 1.0, 'success_rate': 1.0, 'avg_cost': 0}
            
            total_ops = len(self._operations)
            successful_ops = [op for op in self._operations if op.success]
            success_rate = len(successful_ops) / total_ops
            
            if successful_ops:
                avg_cost = statistics.mean([op.energy_cost for op in successful_ops])
                cost_variance = statistics.variance([op.energy_cost for op in successful_ops]) if len(successful_ops) > 1 else 0
                efficiency_score = success_rate * (1 / (1 + cost_variance / avg_cost))
            else:
                avg_cost = 0
                efficiency_score = 0.0
            
            return {
                'efficiency_score': min(1.0, efficiency_score),
                'success_rate': success_rate,
                'avg_cost': avg_cost,
                'total_operations': total_ops,
                'successful_operations': len(successful_ops)
            }
    
    def export_data(self, format: str = "dict") -> Union[Dict[str, Any], str]:
        """Export analytics data in various formats."""
        with self._lock:
            if format == "dict":
                return {
                    'operations': [
                        {
                            'operation_type': op.operation_type,
                            'operation_name': op.operation_name,
                            'energy_cost': op.energy_cost,
                            'timestamp': op.timestamp,
                            'duration': op.duration,
                            'success': op.success,
                            'metadata': op.metadata
                        }
                        for op in self._operations
                    ],
                    'export_timestamp': time.time()
                }
            else:
                raise ValueError(f"Unsupported export format: {format}")
    
    def _parse_time_range(self, time_range: str) -> float:
        """Parse time range string to seconds."""
        if time_range.endswith('h'):
            return float(time_range[:-1]) * 3600
        elif time_range.endswith('m'):
            return float(time_range[:-1]) * 60
        elif time_range.endswith('s'):
            return float(time_range[:-1])
        else:
            try:
                return float(time_range)  # Assume seconds
            except ValueError:
                return 3600  # Default to 1 hour
    
    def _get_top_consumers(self, operations: List[EnergyOperation], limit: int = 10) -> List[Dict[str, Any]]:
        """Get top energy consumers from operation list."""
        # Group by operation type and name
        consumption = defaultdict(lambda: {'total_energy': 0, 'count': 0})
        
        for op in operations:
            key = f"{op.operation_type}:{op.operation_name}"
            consumption[key]['total_energy'] += op.energy_cost
            consumption[key]['count'] += 1
        
        # Sort by total energy consumption
        sorted_consumers = sorted(
            consumption.items(),
            key=lambda x: x[1]['total_energy'],
            reverse=True
        )
        
        return [
            {
                'operation': key,
                'total_energy': data['total_energy'],
                'operation_count': data['count'],
                'avg_energy_per_operation': data['total_energy'] / data['count']
            }
            for key, data in sorted_consumers[:limit]
        ]
    
    def _analyze_usage_trends(self, operations: List[EnergyOperation], time_range_seconds: float) -> Dict[str, Any]:
        """Analyze usage trends over time."""
        if not operations:
            return {}
        
        # Create time buckets
        bucket_count = min(24, int(time_range_seconds / 300))  # 5-minute buckets, max 24
        bucket_size = time_range_seconds / bucket_count
        
        now = time.time()
        buckets = [0] * bucket_count
        
        for op in operations:
            if op.success:
                time_offset = now - op.timestamp
                bucket_index = int(time_offset / bucket_size)
                if 0 <= bucket_index < bucket_count:
                    buckets[bucket_count - 1 - bucket_index] += op.energy_cost
        
        return {
            'energy_over_time': buckets,
            'bucket_size_seconds': bucket_size,
            'peak_usage': max(buckets) if buckets else 0,
            'average_usage': statistics.mean(buckets) if buckets else 0,
            'trend_direction': 'increasing' if buckets and buckets[-1] > buckets[0] else 'decreasing'
        }
    
    def _generate_recommendations(self, operations: List[EnergyOperation], efficiency_score: float) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        if efficiency_score < 0.7:
            recommendations.append("Consider optimizing high-cost operations to improve efficiency")
        
        if operations:
            failed_ops = [op for op in operations if not op.success]
            if len(failed_ops) / len(operations) > 0.1:
                recommendations.append("High failure rate detected - consider implementing retry logic with backoff")
        
        # Check for frequent operations
        op_frequency = defaultdict(int)
        for op in operations:
            op_frequency[f"{op.operation_type}:{op.operation_name}"] += 1
        
        most_frequent = max(op_frequency.values()) if op_frequency else 0
        if most_frequent > len(operations) * 0.3:
            recommendations.append("Consider caching results for frequently called operations")
        
        if not recommendations:
            recommendations.append("Energy usage appears optimal - continue monitoring")
        
        return recommendations


# Export all energy management types
__all__ = [
    'EnergyError',
    'OutOfEnergyError', 
    'EnergyExhaustedException',
    'EnergyEventType',
    'EnergyEvent',
    'EnergyEventListener',
    'EnergyOperation',
    'EnergyUsageReport',
    'EnergyTracker',
    'EnergyBudgetManager',
    'EnergyEventManager',
    'EnergyCostEstimator',
    'EnergyUsageAnalytics'
] 