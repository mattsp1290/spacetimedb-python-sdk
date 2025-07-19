"""
Memory usage tracking and monitoring utilities.
"""

import gc
import sys
import threading
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
import psutil
import os


@dataclass
class MemoryReport:
    """Comprehensive memory usage report."""
    timestamp: float = field(default_factory=time.time)
    current_rss: int = 0  # Resident Set Size
    current_vms: int = 0  # Virtual Memory Size
    peak_rss: int = 0
    peak_vms: int = 0
    python_objects: int = 0
    gc_collections: Dict[int, int] = field(default_factory=dict)
    top_allocations: List[Tuple[str, int]] = field(default_factory=list)
    memory_growth_rate: float = 0.0  # bytes per second
    fragmentation_ratio: float = 0.0
    cache_efficiency: float = 0.0


class MemoryAccountant:
    """Thread-safe memory tracking and accounting."""
    
    def __init__(self, enable_tracemalloc: bool = False):
        self._lock = threading.RLock()
        self.enable_tracemalloc = enable_tracemalloc
        self._allocations: Dict[str, int] = defaultdict(int)
        self._deallocations: Dict[str, int] = defaultdict(int)
        self._object_counts: Dict[type, int] = defaultdict(int)
        self._memory_samples: deque = deque(maxlen=1000)
        self._allocation_history: deque = deque(maxlen=10000)
        self._start_time = time.time()
        self._peak_memory = 0
        self._tracemalloc_enabled = False
        
        # Initialize process monitoring
        self._process = psutil.Process(os.getpid())
        
        # Start tracemalloc if requested
        if enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()
            self._tracemalloc_enabled = True
    
    def record_allocation(self, size: int, category: str = "general") -> None:
        """Record a memory allocation."""
        with self._lock:
            self._allocations[category] += size
            self._allocation_history.append((time.time(), size, category))
            
            # Update peak memory
            current_memory = self.get_current_memory_usage()
            self._peak_memory = max(self._peak_memory, current_memory)
    
    def record_deallocation(self, size: int, category: str = "general") -> None:
        """Record a memory deallocation."""
        with self._lock:
            self._deallocations[category] += size
            self._allocation_history.append((time.time(), -size, category))
    
    def record_object_creation(self, obj_type: type) -> None:
        """Record object creation."""
        with self._lock:
            self._object_counts[obj_type] += 1
    
    def record_object_destruction(self, obj_type: type) -> None:
        """Record object destruction."""
        with self._lock:
            if self._object_counts[obj_type] > 0:
                self._object_counts[obj_type] -= 1
    
    def get_current_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        try:
            memory_info = self._process.memory_info()
            return memory_info.rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0
    
    def get_memory_info(self) -> Tuple[int, int]:
        """Get current RSS and VMS memory usage."""
        try:
            memory_info = self._process.memory_info()
            return memory_info.rss, memory_info.vms
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0, 0
    
    def estimate_size(self, obj: Any) -> int:
        """Estimate the size of a Python object."""
        try:
            return sys.getsizeof(obj)
        except (TypeError, OSError):
            return 0
    
    def would_exceed_limit(self, additional_size: int, limit: int = None) -> bool:
        """Check if allocation would exceed memory limit."""
        if limit is None:
            # Use 80% of available memory as default limit
            try:
                available_memory = psutil.virtual_memory().available
                limit = int(available_memory * 0.8)
            except:
                return False
        
        current_usage = self.get_current_memory_usage()
        return (current_usage + additional_size) > limit
    
    def get_allocation_summary(self) -> Dict[str, Dict[str, int]]:
        """Get summary of allocations and deallocations by category."""
        with self._lock:
            summary = {}
            all_categories = set(self._allocations.keys()) | set(self._deallocations.keys())
            
            for category in all_categories:
                allocated = self._allocations[category]
                deallocated = self._deallocations[category]
                net = allocated - deallocated
                
                summary[category] = {
                    'allocated': allocated,
                    'deallocated': deallocated,
                    'net': net
                }
            
            return summary
    
    def get_object_counts(self) -> Dict[str, int]:
        """Get current object counts by type."""
        with self._lock:
            return {str(obj_type): count for obj_type, count in self._object_counts.items()}
    
    def get_memory_growth_rate(self) -> float:
        """Calculate memory growth rate in bytes per second."""
        with self._lock:
            if len(self._allocation_history) < 2:
                return 0.0
            
            # Calculate based on recent history (last 60 seconds)
            current_time = time.time()
            recent_allocations = [
                (timestamp, size) for timestamp, size, _ in self._allocation_history
                if current_time - timestamp <= 60.0
            ]
            
            if len(recent_allocations) < 2:
                return 0.0
            
            # Calculate net allocation in time window
            net_allocation = sum(size for _, size in recent_allocations)
            time_window = current_time - recent_allocations[0][0]
            
            if time_window > 0:
                return net_allocation / time_window
            return 0.0
    
    def get_top_allocations(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top allocation categories by size."""
        with self._lock:
            allocations = [(category, self._allocations[category]) 
                          for category in self._allocations]
            allocations.sort(key=lambda x: x[1], reverse=True)
            return allocations[:limit]
    
    def get_tracemalloc_snapshot(self) -> Optional[Any]:
        """Get tracemalloc snapshot if enabled."""
        if self._tracemalloc_enabled and tracemalloc.is_tracing():
            try:
                return tracemalloc.take_snapshot()
            except:
                return None
        return None
    
    def calculate_fragmentation_ratio(self) -> float:
        """Calculate memory fragmentation ratio."""
        try:
            rss, vms = self.get_memory_info()
            if vms > 0:
                return 1.0 - (rss / vms)
            return 0.0
        except:
            return 0.0
    
    def get_gc_stats(self) -> Dict[int, int]:
        """Get garbage collection statistics."""
        return {i: gc.get_count()[i] for i in range(len(gc.get_count()))}
    
    def force_gc(self) -> int:
        """Force garbage collection and return collected objects."""
        return gc.collect()
    
    def get_memory_report(self) -> MemoryReport:
        """Generate comprehensive memory report."""
        with self._lock:
            rss, vms = self.get_memory_info()
            
            # Sample current memory
            self._memory_samples.append((time.time(), rss))
            
            # Calculate peak memory
            peak_rss = max(self._peak_memory, rss)
            peak_vms = vms  # VMS peak is harder to track, use current
            
            # Get object count
            try:
                python_objects = len(gc.get_objects())
            except:
                python_objects = 0
            
            # Calculate cache efficiency (placeholder - would need cache integration)
            cache_efficiency = 0.0
            
            return MemoryReport(
                current_rss=rss,
                current_vms=vms,
                peak_rss=peak_rss,
                peak_vms=peak_vms,
                python_objects=python_objects,
                gc_collections=self.get_gc_stats(),
                top_allocations=self.get_top_allocations(),
                memory_growth_rate=self.get_memory_growth_rate(),
                fragmentation_ratio=self.calculate_fragmentation_ratio(),
                cache_efficiency=cache_efficiency
            )
    
    def reset_statistics(self) -> None:
        """Reset all memory statistics."""
        with self._lock:
            self._allocations.clear()
            self._deallocations.clear()
            self._object_counts.clear()
            self._memory_samples.clear()
            self._allocation_history.clear()
            self._peak_memory = self.get_current_memory_usage()
            self._start_time = time.time()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        if self._tracemalloc_enabled:
            try:
                tracemalloc.stop()
            except:
                pass


class MemoryTracker:
    """Utility class for tracking memory usage of specific operations."""
    
    def __init__(self, accountant: MemoryAccountant, category: str = "operation"):
        self.accountant = accountant
        self.category = category
        self.start_memory = 0
        self.start_objects = 0
    
    def __enter__(self):
        """Start tracking memory usage."""
        self.start_memory = self.accountant.get_current_memory_usage()
        try:
            self.start_objects = len(gc.get_objects())
        except:
            self.start_objects = 0
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop tracking and record memory usage."""
        end_memory = self.accountant.get_current_memory_usage()
        memory_delta = end_memory - self.start_memory
        
        if memory_delta > 0:
            self.accountant.record_allocation(memory_delta, self.category)
        elif memory_delta < 0:
            self.accountant.record_deallocation(-memory_delta, self.category)
        
        try:
            end_objects = len(gc.get_objects())
            object_delta = end_objects - self.start_objects
            if object_delta != 0:
                # Could track object creation/destruction here
                pass
        except:
            pass


# Global memory accountant
_global_accountant: MemoryAccountant = None

def get_global_accountant() -> MemoryAccountant:
    """Get the global memory accountant."""
    global _global_accountant
    if _global_accountant is None:
        _global_accountant = MemoryAccountant()
    return _global_accountant

def track_memory(category: str = "operation") -> MemoryTracker:
    """Create a memory tracker for the given category."""
    return MemoryTracker(get_global_accountant(), category)