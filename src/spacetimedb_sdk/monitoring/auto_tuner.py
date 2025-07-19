"""
Auto-tuning system for dynamic performance optimization.
"""

import time
import threading
import math
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict
import logging

from .metrics import PoolMetrics, EventMetrics, ConnectionMetrics, MemoryMetrics


logger = logging.getLogger(__name__)


@dataclass
class TuningRecommendation:
    """A tuning recommendation with rationale."""
    component: str
    parameter: str
    current_value: Any
    recommended_value: Any
    confidence: float  # 0.0 to 1.0
    rationale: str
    impact_estimate: str  # "low", "medium", "high"


@dataclass
class UsagePattern:
    """Usage pattern analysis for a component."""
    component: str
    avg_utilization: float
    peak_utilization: float
    min_utilization: float
    utilization_variance: float
    trend: str  # "increasing", "decreasing", "stable"
    pattern_confidence: float


class AutoTuner:
    """Automatic performance tuning system."""
    
    def __init__(self, enable_auto_apply: bool = False):
        self._lock = threading.RLock()
        self.enable_auto_apply = enable_auto_apply
        
        # Tuning history
        self._tuning_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._usage_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Tuning parameters
        self.tuning_interval = 60.0  # seconds
        self.min_data_points = 10
        self.confidence_threshold = 0.7
        
        # Component-specific tuners
        self._pool_tuners: Dict[str, PoolTuner] = {}
        self._event_tuner = EventSystemTuner()
        self._connection_tuner = ConnectionTuner()
        self._memory_tuner = MemoryTuner()
        
        # Callbacks for applying changes
        self._apply_callbacks: Dict[str, Callable] = {}
        
        # Auto-tuning thread
        self._tuning_thread: Optional[threading.Thread] = None
        self._stop_tuning = threading.Event()
        
        # Start auto-tuning if enabled
        if enable_auto_apply:
            self.start_auto_tuning()
    
    def start_auto_tuning(self) -> None:
        """Start automatic tuning thread."""
        with self._lock:
            if self._tuning_thread is None or not self._tuning_thread.is_alive():
                self._stop_tuning.clear()
                self._tuning_thread = threading.Thread(
                    target=self._auto_tuning_loop,
                    daemon=True
                )
                self._tuning_thread.start()
                logger.info("Auto-tuning started")
    
    def stop_auto_tuning(self) -> None:
        """Stop automatic tuning thread."""
        with self._lock:
            if self._tuning_thread:
                self._stop_tuning.set()
                if self._tuning_thread.is_alive():
                    self._tuning_thread.join(timeout=5.0)
                logger.info("Auto-tuning stopped")
    
    def _auto_tuning_loop(self) -> None:
        """Main auto-tuning loop."""
        while not self._stop_tuning.is_set():
            try:
                # Generate recommendations
                recommendations = self.generate_recommendations()
                
                # Apply high-confidence recommendations if auto-apply is enabled
                if self.enable_auto_apply:
                    for rec in recommendations:
                        if rec.confidence >= self.confidence_threshold:
                            self._apply_recommendation(rec)
                
                # Sleep until next tuning cycle
                self._stop_tuning.wait(self.tuning_interval)
                
            except Exception as e:
                logger.error(f"Error in auto-tuning loop: {e}")
                self._stop_tuning.wait(self.tuning_interval * 2)  # Longer wait on error
    
    def register_apply_callback(self, component: str, callback: Callable[[str, Any], bool]) -> None:
        """Register a callback for applying tuning changes."""
        with self._lock:
            self._apply_callbacks[component] = callback
    
    def record_usage_metrics(self, component: str, metrics: Dict[str, float]) -> None:
        """Record usage metrics for a component."""
        with self._lock:
            timestamp = time.time()
            self._usage_history[component].append((timestamp, metrics))
    
    def record_performance_metrics(self, component: str, metrics: Dict[str, float]) -> None:
        """Record performance metrics for a component."""
        with self._lock:
            timestamp = time.time()
            self._performance_history[component].append((timestamp, metrics))
    
    def analyze_usage_pattern(self, component: str) -> Optional[UsagePattern]:
        """Analyze usage patterns for a component."""
        with self._lock:
            history = self._usage_history.get(component, deque())
            
            if len(history) < self.min_data_points:
                return None
            
            # Extract utilization values
            utilizations = []
            for timestamp, metrics in history:
                if 'utilization' in metrics:
                    utilizations.append(metrics['utilization'])
            
            if not utilizations:
                return None
            
            # Calculate statistics
            avg_util = sum(utilizations) / len(utilizations)
            peak_util = max(utilizations)
            min_util = min(utilizations)
            
            # Calculate variance
            variance = sum((x - avg_util) ** 2 for x in utilizations) / len(utilizations)
            
            # Determine trend
            trend = self._calculate_trend(utilizations)
            
            # Calculate confidence based on data quality
            confidence = min(1.0, len(utilizations) / 100.0)
            
            return UsagePattern(
                component=component,
                avg_utilization=avg_util,
                peak_utilization=peak_util,
                min_utilization=min_util,
                utilization_variance=variance,
                trend=trend,
                pattern_confidence=confidence
            )
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a series of values."""
        if len(values) < 2:
            return "stable"
        
        # Use linear regression to determine trend
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        # Calculate slope
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        # Determine trend based on slope
        if abs(slope) < 0.01:  # Very small slope
            return "stable"
        elif slope > 0:
            return "increasing"
        else:
            return "decreasing"
    
    def optimize_pool_sizes(self, usage_history: List[PoolMetrics]) -> Dict[str, TuningRecommendation]:
        """Optimize pool sizes based on usage patterns."""
        recommendations = {}
        
        for pool_name in set(metric.pool_name for metric in usage_history):
            pool_metrics = [m for m in usage_history if m.pool_name == pool_name]
            
            if len(pool_metrics) < self.min_data_points:
                continue
            
            # Get or create pool tuner
            if pool_name not in self._pool_tuners:
                self._pool_tuners[pool_name] = PoolTuner(pool_name)
            
            tuner = self._pool_tuners[pool_name]
            recommendation = tuner.recommend_size_adjustment(pool_metrics)
            
            if recommendation:
                recommendations[pool_name] = recommendation
        
        return recommendations
    
    def optimize_event_system(self, event_metrics: EventMetrics) -> List[TuningRecommendation]:
        """Optimize event system parameters."""
        return self._event_tuner.generate_recommendations(event_metrics)
    
    def optimize_connections(self, connection_metrics: ConnectionMetrics) -> List[TuningRecommendation]:
        """Optimize connection parameters."""
        return self._connection_tuner.generate_recommendations(connection_metrics)
    
    def optimize_memory_usage(self, memory_metrics: MemoryMetrics) -> List[TuningRecommendation]:
        """Optimize memory usage parameters."""
        return self._memory_tuner.generate_recommendations(memory_metrics)
    
    def generate_recommendations(self) -> List[TuningRecommendation]:
        """Generate all tuning recommendations."""
        recommendations = []
        
        try:
            # Analyze usage patterns for all components
            patterns = {}
            for component in self._usage_history:
                pattern = self.analyze_usage_pattern(component)
                if pattern:
                    patterns[component] = pattern
            
            # Generate component-specific recommendations
            for component, pattern in patterns.items():
                if component.startswith('pool_'):
                    # Pool optimization
                    pool_name = component.replace('pool_', '')
                    if pool_name in self._pool_tuners:
                        # Get recent pool metrics
                        recent_metrics = self._get_recent_pool_metrics(pool_name)
                        if recent_metrics:
                            rec = self._pool_tuners[pool_name].recommend_size_adjustment(recent_metrics)
                            if rec:
                                recommendations.append(rec)
                
                elif component == 'event_system':
                    # Event system optimization
                    recent_metrics = self._get_recent_event_metrics()
                    if recent_metrics:
                        event_recs = self._event_tuner.generate_recommendations(recent_metrics)
                        recommendations.extend(event_recs)
                
                elif component == 'connection_manager':
                    # Connection optimization
                    recent_metrics = self._get_recent_connection_metrics()
                    if recent_metrics:
                        conn_recs = self._connection_tuner.generate_recommendations(recent_metrics)
                        recommendations.extend(conn_recs)
        
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def _get_recent_pool_metrics(self, pool_name: str) -> List[PoolMetrics]:
        """Get recent pool metrics for analysis."""
        # This would integrate with the actual pool metrics collection
        # For now, return empty list as placeholder
        return []
    
    def _get_recent_event_metrics(self) -> Optional[EventMetrics]:
        """Get recent event metrics for analysis."""
        # This would integrate with the actual event metrics collection
        return None
    
    def _get_recent_connection_metrics(self) -> Optional[ConnectionMetrics]:
        """Get recent connection metrics for analysis."""
        # This would integrate with the actual connection metrics collection
        return None
    
    def _apply_recommendation(self, recommendation: TuningRecommendation) -> bool:
        """Apply a tuning recommendation."""
        try:
            callback = self._apply_callbacks.get(recommendation.component)
            if callback:
                success = callback(recommendation.parameter, recommendation.recommended_value)
                if success:
                    # Record successful tuning
                    self._tuning_history[recommendation.component].append({
                        'timestamp': time.time(),
                        'parameter': recommendation.parameter,
                        'old_value': recommendation.current_value,
                        'new_value': recommendation.recommended_value,
                        'confidence': recommendation.confidence
                    })
                    logger.info(f"Applied tuning: {recommendation.component}.{recommendation.parameter} "
                              f"= {recommendation.recommended_value} (was {recommendation.current_value})")
                return success
            else:
                logger.warning(f"No apply callback registered for component: {recommendation.component}")
                return False
        except Exception as e:
            logger.error(f"Error applying recommendation: {e}")
            return False
    
    def get_tuning_history(self, component: str = None) -> Dict[str, List[Dict]]:
        """Get tuning history for components."""
        with self._lock:
            if component:
                return {component: list(self._tuning_history.get(component, []))}
            else:
                return {comp: list(history) for comp, history in self._tuning_history.items()}


class PoolTuner:
    """Specialized tuner for object pools."""
    
    def __init__(self, pool_name: str):
        self.pool_name = pool_name
        self.min_efficiency = 0.6  # Minimum acceptable efficiency
        self.target_utilization = 0.75  # Target utilization rate
    
    def recommend_size_adjustment(self, metrics_history: List[PoolMetrics]) -> Optional[TuningRecommendation]:
        """Recommend pool size adjustments."""
        if len(metrics_history) < 5:
            return None
        
        # Calculate average utilization
        avg_utilization = sum(m.utilization_rate for m in metrics_history) / len(metrics_history)
        peak_utilization = max(m.utilization_rate for m in metrics_history)
        current_max_size = metrics_history[-1].max_size
        
        # Determine if adjustment is needed
        if avg_utilization > 0.9:  # Over-utilized
            # Increase pool size
            new_size = int(current_max_size * 1.5)
            confidence = min(0.9, avg_utilization)
            rationale = f"High average utilization ({avg_utilization:.1%}) suggests pool is too small"
            impact = "medium"
            
        elif avg_utilization < 0.3 and current_max_size > 5:  # Under-utilized
            # Decrease pool size (but not below minimum)
            new_size = max(5, int(current_max_size * 0.7))
            confidence = min(0.8, 1.0 - avg_utilization)
            rationale = f"Low average utilization ({avg_utilization:.1%}) suggests pool is too large"
            impact = "low"
            
        elif peak_utilization > 0.95:  # Peak pressure
            # Moderate increase
            new_size = int(current_max_size * 1.2)
            confidence = 0.7
            rationale = f"Peak utilization ({peak_utilization:.1%}) suggests capacity constraints"
            impact = "medium"
            
        else:
            # No adjustment needed
            return None
        
        return TuningRecommendation(
            component=f"pool_{self.pool_name}",
            parameter="max_size",
            current_value=current_max_size,
            recommended_value=new_size,
            confidence=confidence,
            rationale=rationale,
            impact_estimate=impact
        )


class EventSystemTuner:
    """Specialized tuner for event system."""
    
    def generate_recommendations(self, metrics: EventMetrics) -> List[TuningRecommendation]:
        """Generate event system tuning recommendations."""
        recommendations = []
        
        # Batch size optimization
        if metrics.batch_efficiency < 0.5 and metrics.events_per_second > 100:
            recommendations.append(TuningRecommendation(
                component="event_system",
                parameter="batch_size",
                current_value="unknown",
                recommended_value=min(1000, metrics.events_per_second * 2),
                confidence=0.8,
                rationale=f"Low batch efficiency ({metrics.batch_efficiency:.1%}) with high event rate",
                impact_estimate="high"
            ))
        
        # Queue depth optimization
        if metrics.max_queue_depth > 10000:
            recommendations.append(TuningRecommendation(
                component="event_system",
                parameter="max_queue_size",
                current_value=metrics.max_queue_depth,
                recommended_value=int(metrics.max_queue_depth * 1.5),
                confidence=0.7,
                rationale="Queue depth approaching limits",
                impact_estimate="medium"
            ))
        
        return recommendations


class ConnectionTuner:
    """Specialized tuner for connection management."""
    
    def generate_recommendations(self, metrics: ConnectionMetrics) -> List[TuningRecommendation]:
        """Generate connection tuning recommendations."""
        recommendations = []
        
        # Connection timeout optimization
        if metrics.avg_connection_time > 0.2:  # 200ms
            recommendations.append(TuningRecommendation(
                component="connection_manager",
                parameter="connection_timeout",
                current_value="unknown",
                recommended_value=max(5.0, metrics.avg_connection_time * 3),
                confidence=0.7,
                rationale=f"High average connection time ({metrics.avg_connection_time:.3f}s)",
                impact_estimate="medium"
            ))
        
        # Pool size optimization
        if metrics.connection_pool_utilization > 0.9:
            recommendations.append(TuningRecommendation(
                component="connection_manager",
                parameter="pool_size",
                current_value="unknown",
                recommended_value="increase by 50%",
                confidence=0.8,
                rationale=f"High pool utilization ({metrics.connection_pool_utilization:.1%})",
                impact_estimate="high"
            ))
        
        return recommendations


class MemoryTuner:
    """Specialized tuner for memory management."""
    
    def generate_recommendations(self, metrics: MemoryMetrics) -> List[TuningRecommendation]:
        """Generate memory tuning recommendations."""
        recommendations = []
        
        # Cache size optimization
        if metrics.cache_hit_rate < 0.8:
            recommendations.append(TuningRecommendation(
                component="memory_manager",
                parameter="cache_size",
                current_value=metrics.cache_size,
                recommended_value=int(metrics.cache_size * 1.5),
                confidence=0.7,
                rationale=f"Low cache hit rate ({metrics.cache_hit_rate:.1%})",
                impact_estimate="medium"
            ))
        
        # GC frequency optimization
        if metrics.gc_collections > 100:  # High GC activity
            recommendations.append(TuningRecommendation(
                component="memory_manager",
                parameter="gc_threshold",
                current_value="unknown",
                recommended_value="increase threshold",
                confidence=0.6,
                rationale=f"High GC activity ({metrics.gc_collections} collections)",
                impact_estimate="low"
            ))
        
        return recommendations