#!/usr/bin/env python3
"""
Memory Optimization Example
============================

This example demonstrates memory optimization techniques for the SpacetimeDB SDK,
including bounded collections, memory monitoring, and efficient data structures.

Key concepts:
- Bounded cache management
- Memory pool optimization
- Garbage collection strategies
- Memory leak detection
- Resource cleanup patterns

Requirements:
- spacetimedb-sdk
- psutil (for memory monitoring)
- asyncio
"""


import sys
import os
# Add src directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import time
import gc
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections import deque, defaultdict
from weakref import WeakValueDictionary

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not installed. Memory monitoring will be limited.")

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.bounded_cache import BoundedCache
from spacetimedb_sdk.memory_management import MemoryManager
from spacetimedb_sdk.connection_pool import ConnectionPool


@dataclass
class MemorySnapshot:
    """Memory usage snapshot"""
    timestamp: float
    rss_mb: float
    vms_mb: float
    heap_size: int
    object_count: int
    cache_size: int
    pool_size: int


class MemoryMonitor:
    """Monitor memory usage and detect potential issues"""
    
    def __init__(self):
        self.snapshots: deque = deque(maxlen=1000)
        self.current_process = psutil.Process() if HAS_PSUTIL else None
        self.baseline_memory = None
    
    def take_snapshot(self, cache_size: int = 0, pool_size: int = 0) -> MemorySnapshot:
        """Take a memory usage snapshot"""
        
        if self.current_process:
            memory_info = self.current_process.memory_info()
            rss_mb = memory_info.rss / 1024 / 1024
            vms_mb = memory_info.vms / 1024 / 1024
        else:
            rss_mb = vms_mb = 0
        
        # Get heap size approximation
        heap_size = sys.getsizeof(gc.get_objects())
        
        # Count objects
        object_count = len(gc.get_objects())
        
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            rss_mb=rss_mb,
            vms_mb=vms_mb,
            heap_size=heap_size,
            object_count=object_count,
            cache_size=cache_size,
            pool_size=pool_size
        )
        
        self.snapshots.append(snapshot)
        
        if self.baseline_memory is None:
            self.baseline_memory = snapshot
        
        return snapshot
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage"""
        if not self.snapshots:
            return {}
        
        current = self.snapshots[-1]
        baseline = self.baseline_memory
        
        return {
            'current_rss_mb': current.rss_mb,
            'current_vms_mb': current.vms_mb,
            'rss_delta_mb': current.rss_mb - baseline.rss_mb,
            'vms_delta_mb': current.vms_mb - baseline.vms_mb,
            'object_count': current.object_count,
            'heap_size': current.heap_size
        }
    
    def detect_memory_leaks(self) -> List[str]:
        """Detect potential memory leaks"""
        issues = []
        
        if len(self.snapshots) < 10:
            return issues
        
        # Check for steadily increasing memory
        recent_snapshots = list(self.snapshots)[-10:]
        
        # Calculate trend
        rss_trend = sum(s.rss_mb for s in recent_snapshots[-5:]) / 5 - sum(s.rss_mb for s in recent_snapshots[:5]) / 5
        obj_trend = sum(s.object_count for s in recent_snapshots[-5:]) / 5 - sum(s.object_count for s in recent_snapshots[:5]) / 5
        
        if rss_trend > 10:  # More than 10MB increase
            issues.append(f"Increasing RSS memory trend: +{rss_trend:.1f}MB")
        
        if obj_trend > 1000:  # More than 1000 objects increase
            issues.append(f"Increasing object count trend: +{obj_trend:.0f} objects")
        
        # Check for memory spikes
        max_rss = max(s.rss_mb for s in recent_snapshots)
        avg_rss = sum(s.rss_mb for s in recent_snapshots) / len(recent_snapshots)
        
        if max_rss > avg_rss * 1.5:
            issues.append(f"Memory spike detected: {max_rss:.1f}MB (avg: {avg_rss:.1f}MB)")
        
        return issues
    
    def print_memory_report(self):
        """Print detailed memory report"""
        if not self.snapshots:
            print("No memory snapshots available")
            return
        
        current = self.snapshots[-1]
        baseline = self.baseline_memory
        
        print("\nMemory Usage Report")
        print("=" * 50)
        print(f"Current RSS: {current.rss_mb:.1f} MB")
        print(f"Current VMS: {current.vms_mb:.1f} MB")
        print(f"RSS Delta: {current.rss_mb - baseline.rss_mb:+.1f} MB")
        print(f"VMS Delta: {current.vms_mb - baseline.vms_mb:+.1f} MB")
        print(f"Object Count: {current.object_count:,}")
        print(f"Heap Size: {current.heap_size / 1024 / 1024:.1f} MB")
        
        # Check for issues
        issues = self.detect_memory_leaks()
        if issues:
            print(f"\nMemory Issues Detected:")
            for issue in issues:
                print(f"  ⚠️  {issue}")
        else:
            print(f"\n✅ No memory issues detected")


class OptimizedDataStructures:
    """Demonstrate memory-efficient data structures"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
    
    def demonstrate_bounded_cache(self):
        """Demonstrate bounded cache vs unbounded storage"""
        
        print("Bounded Cache Demo")
        print("=" * 50)
        
        # Take baseline snapshot
        self.monitor.take_snapshot()
        
        # Create unbounded dict
        print("\n1. Creating unbounded dictionary...")
        unbounded_dict = {}
        for i in range(10000):
            unbounded_dict[f"key_{i}"] = f"value_{i}" * 100  # Large values
        
        unbounded_snapshot = self.monitor.take_snapshot()
        print(f"   Memory usage: {unbounded_snapshot.rss_mb:.1f} MB")
        
        # Create bounded cache
        print("\n2. Creating bounded cache (max 1000 items)...")
        bounded_cache = BoundedCache(max_size=1000)
        for i in range(10000):
            bounded_cache.put(f"key_{i}", f"value_{i}" * 100)
        
        bounded_snapshot = self.monitor.take_snapshot(cache_size=len(bounded_cache))
        print(f"   Memory usage: {bounded_snapshot.rss_mb:.1f} MB")
        print(f"   Cache size: {len(bounded_cache)} items")
        
        # Compare memory usage
        unbounded_size = unbounded_snapshot.rss_mb - self.monitor.baseline_memory.rss_mb
        bounded_size = bounded_snapshot.rss_mb - unbounded_snapshot.rss_mb
        
        print(f"\n3. Memory comparison:")
        print(f"   Unbounded dict: {unbounded_size:.1f} MB")
        print(f"   Bounded cache: {bounded_size:.1f} MB")
        print(f"   Memory saved: {unbounded_size - bounded_size:.1f} MB ({((unbounded_size - bounded_size) / unbounded_size * 100):.1f}%)")
        
        # Clean up
        del unbounded_dict
        del bounded_cache
        gc.collect()
    
    def demonstrate_memory_pools(self):
        """Demonstrate memory pool usage"""
        
        print("\n\nMemory Pool Demo")
        print("=" * 50)
        
        # Simulate object creation without pool
        print("\n1. Creating objects without pool...")
        objects_without_pool = []
        
        baseline = self.monitor.take_snapshot()
        
        for i in range(1000):
            obj = {
                'id': i,
                'data': f"object_{i}",
                'metadata': {'created': time.time(), 'processed': False}
            }
            objects_without_pool.append(obj)
        
        without_pool_snapshot = self.monitor.take_snapshot()
        
        # Simulate object creation with pool
        print("\n2. Creating objects with memory pool...")
        
        class ObjectPool:
            def __init__(self, size: int):
                self.pool = deque()
                self.size = size
                self.created_count = 0
                self.reused_count = 0
            
            def get_object(self):
                if self.pool:
                    self.reused_count += 1
                    return self.pool.popleft()
                else:
                    self.created_count += 1
                    return {'id': 0, 'data': '', 'metadata': {}}
            
            def return_object(self, obj):
                if len(self.pool) < self.size:
                    # Reset object
                    obj['id'] = 0
                    obj['data'] = ''
                    obj['metadata'].clear()
                    self.pool.append(obj)
            
            def get_stats(self):
                return {
                    'created': self.created_count,
                    'reused': self.reused_count,
                    'pool_size': len(self.pool)
                }
        
        pool = ObjectPool(100)
        objects_with_pool = []
        
        for i in range(1000):
            obj = pool.get_object()
            obj['id'] = i
            obj['data'] = f"object_{i}"
            obj['metadata'] = {'created': time.time(), 'processed': False}
            objects_with_pool.append(obj)
        
        with_pool_snapshot = self.monitor.take_snapshot()
        
        # Return objects to pool
        for obj in objects_with_pool:
            pool.return_object(obj)
        
        # Compare memory usage
        without_pool_size = without_pool_snapshot.rss_mb - baseline.rss_mb
        with_pool_size = with_pool_snapshot.rss_mb - without_pool_snapshot.rss_mb
        
        print(f"\n3. Memory comparison:")
        print(f"   Without pool: {without_pool_size:.1f} MB")
        print(f"   With pool: {with_pool_size:.1f} MB")
        print(f"   Memory saved: {without_pool_size - with_pool_size:.1f} MB")
        
        stats = pool.get_stats()
        print(f"\n4. Pool statistics:")
        print(f"   Objects created: {stats['created']}")
        print(f"   Objects reused: {stats['reused']}")
        print(f"   Reuse rate: {stats['reused'] / (stats['created'] + stats['reused']) * 100:.1f}%")
        
        # Clean up
        del objects_without_pool
        del objects_with_pool
        del pool
        gc.collect()
    
    def demonstrate_weak_references(self):
        """Demonstrate weak references to prevent memory leaks"""
        
        print("\n\nWeak References Demo")
        print("=" * 50)
        
        class Connection:
            def __init__(self, id: str):
                self.id = id
                self.data = f"connection_data_{id}" * 100
        
        # Strong references (potential memory leak)
        print("\n1. Using strong references...")
        strong_refs = {}
        
        baseline = self.monitor.take_snapshot()
        
        for i in range(100):
            conn = Connection(f"conn_{i}")
            strong_refs[conn.id] = conn
        
        strong_snapshot = self.monitor.take_snapshot()
        
        # Weak references (automatic cleanup)
        print("\n2. Using weak references...")
        weak_refs = WeakValueDictionary()
        
        for i in range(100):
            conn = Connection(f"conn_{i}")
            weak_refs[conn.id] = conn
            # conn goes out of scope and can be garbage collected
        
        # Force garbage collection
        gc.collect()
        
        weak_snapshot = self.monitor.take_snapshot()
        
        print(f"\n3. Reference comparison:")
        print(f"   Strong references: {len(strong_refs)} objects")
        print(f"   Weak references: {len(weak_refs)} objects")
        print(f"   Memory with strong refs: {strong_snapshot.rss_mb - baseline.rss_mb:.1f} MB")
        print(f"   Memory with weak refs: {weak_snapshot.rss_mb - strong_snapshot.rss_mb:.1f} MB")
        
        # Clean up
        strong_refs.clear()
        weak_refs.clear()
        gc.collect()


class ConnectionPoolOptimization:
    """Demonstrate connection pool memory optimization"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
    
    async def demonstrate_pool_sizing(self):
        """Demonstrate optimal pool sizing"""
        
        print("\n\nConnection Pool Optimization Demo")
        print("=" * 50)
        
        # Test different pool sizes
        pool_sizes = [5, 10, 25, 50, 100]
        results = []
        
        for size in pool_sizes:
            print(f"\nTesting pool size: {size}")
            
            # Create pool
            pool = ConnectionPool(
                "ws://localhost:3000",
                min_size=size // 2,
                max_size=size,
                enable_monitoring=True
            )
            
            # Measure memory
            baseline = self.monitor.take_snapshot()
            
            # Simulate load
            tasks = []
            for i in range(size * 2):  # 2x pool size
                task = self._simulate_connection_use(pool)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # Measure memory after load
            after_load = self.monitor.take_snapshot(pool_size=size)
            
            memory_usage = after_load.rss_mb - baseline.rss_mb
            
            results.append({
                'pool_size': size,
                'memory_mb': memory_usage,
                'efficiency': size / memory_usage if memory_usage > 0 else 0
            })
            
            print(f"   Memory usage: {memory_usage:.1f} MB")
            print(f"   Efficiency: {size / memory_usage:.2f} connections/MB" if memory_usage > 0 else "N/A")
            
            await pool.close()
        
        # Find optimal pool size
        optimal = max(results, key=lambda x: x['efficiency'])
        print(f"\n✅ Optimal pool size: {optimal['pool_size']} connections")
        print(f"   Memory usage: {optimal['memory_mb']:.1f} MB")
        print(f"   Efficiency: {optimal['efficiency']:.2f} connections/MB")
    
    async def _simulate_connection_use(self, pool):
        """Simulate connection usage"""
        try:
            async with pool.acquire() as conn:
                # Simulate work
                await asyncio.sleep(0.1)
        except Exception:
            pass  # Ignore errors for demo
    
    async def demonstrate_connection_cleanup(self):
        """Demonstrate proper connection cleanup"""
        
        print("\n\nConnection Cleanup Demo")
        print("=" * 50)
        
        # Create pool with cleanup configuration
        pool = ConnectionPool(
            "ws://localhost:3000",
            min_size=5,
            max_size=20,
            idle_timeout=10.0,  # Close idle connections after 10s
            max_lifetime=300.0,  # Replace connections after 5 minutes
            cleanup_interval=5.0  # Check for cleanup every 5s
        )
        
        print("\n1. Creating connections...")
        baseline = self.monitor.take_snapshot()
        
        # Create many connections
        tasks = []
        for i in range(50):
            task = self._simulate_connection_use(pool)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        after_creation = self.monitor.take_snapshot(pool_size=20)
        
        print(f"   Memory after creation: {after_creation.rss_mb - baseline.rss_mb:.1f} MB")
        
        # Wait for cleanup
        print("\n2. Waiting for idle cleanup...")
        await asyncio.sleep(15)  # Wait longer than idle timeout
        
        # Force cleanup
        await pool.cleanup_idle_connections()
        
        after_cleanup = self.monitor.take_snapshot(pool_size=5)
        
        print(f"   Memory after cleanup: {after_cleanup.rss_mb - baseline.rss_mb:.1f} MB")
        print(f"   Memory saved: {after_creation.rss_mb - after_cleanup.rss_mb:.1f} MB")
        
        await pool.close()


class MemoryLeakDetector:
    """Detect and prevent memory leaks"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
        self.reference_tracker = defaultdict(int)
    
    def track_objects(self, obj_type: type):
        """Track objects of a specific type"""
        count = len([obj for obj in gc.get_objects() if isinstance(obj, obj_type)])
        self.reference_tracker[obj_type.__name__] = count
        return count
    
    def check_for_leaks(self) -> Dict[str, int]:
        """Check for object leaks"""
        leaks = {}
        
        for obj_type_name, previous_count in self.reference_tracker.items():
            # Find the type from name
            obj_type = None
            for obj in gc.get_objects():
                if hasattr(obj, '__name__') and obj.__name__ == obj_type_name:
                    obj_type = obj
                    break
            
            if obj_type:
                current_count = len([obj for obj in gc.get_objects() if isinstance(obj, obj_type)])
                if current_count > previous_count:
                    leaks[obj_type_name] = current_count - previous_count
        
        return leaks
    
    async def demonstrate_leak_detection(self):
        """Demonstrate memory leak detection"""
        
        print("\n\nMemory Leak Detection Demo")
        print("=" * 50)
        
        # Create baseline
        self.monitor.take_snapshot()
        
        # Track specific object types
        self.track_objects(dict)
        self.track_objects(list)
        
        print("\n1. Creating objects that might leak...")
        
        # Simulate potential leak
        leaked_objects = []
        for i in range(100):
            obj = {
                'id': i,
                'data': [f"item_{j}" for j in range(10)],
                'circular_ref': None
            }
            obj['circular_ref'] = obj  # Circular reference
            leaked_objects.append(obj)
        
        # Check for leaks
        leaks = self.check_for_leaks()
        
        print(f"\n2. Leak detection results:")
        if leaks:
            for obj_type, count in leaks.items():
                print(f"   ⚠️  {obj_type}: +{count} objects")
        else:
            print("   ✅ No leaks detected")
        
        # Clean up (break circular references)
        print("\n3. Cleaning up...")
        for obj in leaked_objects:
            obj['circular_ref'] = None
        
        leaked_objects.clear()
        gc.collect()
        
        # Check again
        final_leaks = self.check_for_leaks()
        print(f"\n4. After cleanup:")
        if final_leaks:
            for obj_type, count in final_leaks.items():
                print(f"   ⚠️  {obj_type}: +{count} objects still leaked")
        else:
            print("   ✅ All objects cleaned up")


async def main():
    """Run memory optimization demonstrations"""
    
    print("SpacetimeDB SDK Memory Optimization Demo")
    print("=" * 60)
    
    # Initialize demos
    data_structures = OptimizedDataStructures()
    pool_optimization = ConnectionPoolOptimization()
    leak_detector = MemoryLeakDetector()
    
    try:
        # Run demonstrations
        data_structures.demonstrate_bounded_cache()
        data_structures.demonstrate_memory_pools()
        data_structures.demonstrate_weak_references()
        
        await pool_optimization.demonstrate_pool_sizing()
        await pool_optimization.demonstrate_connection_cleanup()
        
        await leak_detector.demonstrate_leak_detection()
        
        # Final memory report
        data_structures.monitor.print_memory_report()
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())