#!/usr/bin/env python3
"""
Performance Benchmarks for SDK-Client Integration

Tests performance characteristics to ensure the integration
meets production requirements.
"""

import pytest
import time
import threading
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

from spacetimedb_sdk.websocket_client import WebSocketClient, SubscriptionMetrics
from spacetimedb_sdk.message_validator import SpacetimeDBMessageValidator
from spacetimedb_sdk.large_message_handler import LargeMessageHandler
from spacetimedb_sdk.protocol import TEXT_PROTOCOL


class TestMessageValidationPerformance:
    """Test message validation performance under load."""
    
    def test_validation_throughput(self):
        """Test message validation throughput."""
        
        # Create test messages of varying complexity
        simple_message = {
            "CallReducer": {
                "reducer": "test",
                "args": {},
                "request_id": 1
            }
        }
        
        complex_message = {
            "SubscribeMulti": {
                "query_strings": [
                    "SELECT * FROM players WHERE level > 10",
                    "SELECT * FROM games WHERE status = 'active'",
                    "SELECT * FROM items WHERE rarity = 'legendary'"
                ],
                "request_id": 2,
                "query_id": list(range(16))  # 16-byte query ID
            }
        }
        
        # Measure validation performance
        start_time = time.time()
        
        for i in range(10000):
            SpacetimeDBMessageValidator.validate_message(simple_message)
            SpacetimeDBMessageValidator.validate_message(complex_message)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should validate 20,000 messages in under 2 seconds
        assert duration < 2.0, f"Validation took {duration:.2f}s for 20,000 messages"
        
        throughput = 20000 / duration
        print(f"Message validation throughput: {throughput:.0f} msg/sec")
        assert throughput > 10000, "Validation throughput should exceed 10,000 msg/sec"
    
    def test_concurrent_validation(self):
        """Test concurrent message validation performance."""
        
        test_message = {
            "CallReducer": {
                "reducer": "concurrent_test",
                "args": {"thread_id": 0},
                "request_id": 1
            }
        }
        
        def validate_messages(thread_id: int, count: int):
            """Validate messages in a thread."""
            for i in range(count):
                test_message["CallReducer"]["args"]["thread_id"] = thread_id
                test_message["CallReducer"]["request_id"] = i
                SpacetimeDBMessageValidator.validate_message(test_message)
        
        # Test with multiple threads
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for thread_id in range(4):
                future = executor.submit(validate_messages, thread_id, 2500)
                futures.append(future)
            
            # Wait for all threads to complete
            for future in futures:
                future.result()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle 10,000 validations across 4 threads efficiently
        assert duration < 3.0, f"Concurrent validation took {duration:.2f}s"
        
        throughput = 10000 / duration
        print(f"Concurrent validation throughput: {throughput:.0f} msg/sec")


class TestSubscriptionMetricsPerformance:
    """Test subscription metrics performance under load."""
    
    def test_high_frequency_data_recording(self):
        """Test metrics recording with high-frequency updates."""
        
        metrics = SubscriptionMetrics()
        
        # Simulate high-frequency game updates
        start_time = time.time()
        
        for i in range(50000):
            table_name = f"table_{i % 10}"  # 10 different tables
            metrics.record_subscription_data(table_name, 256)  # 256 bytes per update
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle 50,000 updates quickly
        assert duration < 5.0, f"Metrics recording took {duration:.2f}s for 50,000 updates"
        
        throughput = 50000 / duration
        print(f"Metrics recording throughput: {throughput:.0f} updates/sec")
        
        # Verify data integrity
        all_health = metrics.get_all_subscription_health()
        assert len(all_health) == 10  # 10 tables
        
        for health in all_health.values():
            assert health['message_count'] == 5000  # 50,000 / 10 tables
            assert health['total_bytes'] == 5000 * 256
    
    def test_health_calculation_performance(self):
        """Test health calculation performance."""
        
        metrics = SubscriptionMetrics()
        
        # Set up metrics data for 100 tables
        for table_id in range(100):
            table_name = f"perf_table_{table_id}"
            for _ in range(1000):
                metrics.record_subscription_data(table_name, 128)
        
        # Measure health calculation performance
        start_time = time.time()
        
        for _ in range(1000):
            all_health = metrics.get_all_subscription_health()
            assert len(all_health) == 100
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should calculate health for 100 tables 1000 times quickly
        assert duration < 2.0, f"Health calculation took {duration:.2f}s"
        
        calc_rate = 100000 / duration  # 100 tables * 1000 iterations
        print(f"Health calculation rate: {calc_rate:.0f} calculations/sec")


class TestLargeMessagePerformance:
    """Test large message handling performance."""
    
    def test_chunking_performance(self):
        """Test message chunking performance."""
        
        sent_chunks = []
        def mock_send(chunk):
            sent_chunks.append(chunk)
        
        handler = LargeMessageHandler(mock_send)
        
        # Create 5MB message
        large_data = "x" * (5 * 1024 * 1024)
        large_message = json.dumps({
            "InitialSubscription": {
                "database_update": {
                    "tables": [{"table_name": "large_table", "data": large_data}]
                }
            }
        })
        
        start_time = time.time()
        handler.send_large_message(large_message, "performance_test")
        end_time = time.time()
        
        duration = end_time - start_time
        message_size = len(large_message.encode('utf-8'))
        
        print(f"Chunked {message_size} bytes in {duration:.3f}s")
        print(f"Chunking throughput: {message_size / duration / 1024 / 1024:.1f} MB/s")
        
        # Should chunk efficiently
        assert duration < 1.0, "5MB message should chunk in under 1 second"
        assert len(sent_chunks) > 1, "Large message should be chunked"
    
    def test_reassembly_performance(self):
        """Test message reassembly performance."""
        
        handler = LargeMessageHandler(lambda x: None)
        
        # Create test chunks
        test_data = b"performance_test_data" * 10000  # ~200KB
        chunk_size = handler.MAX_FRAME_SIZE
        chunks = []
        
        for i in range(0, len(test_data), chunk_size):
            chunk_data = test_data[i:i + chunk_size]
            sequence = i // chunk_size
            chunks.append({
                "chunk_id": "test_chunk",
                "sequence": sequence,
                "data": chunk_data,
                "size": len(chunk_data)
            })
        
        # Simulate chunk reassembly
        start_time = time.time()
        
        # Add to handler's internal state
        chunk_id = "test_chunk"
        handler._chunk_metadata[chunk_id] = {
            "total_size": len(test_data),
            "chunk_count": len(chunks),
            "message_type": "test",
            "start_time": time.time(),
            "received_chunks": 0
        }
        handler._incoming_chunks[chunk_id] = {}
        
        # Process all chunks
        for i, chunk_info in enumerate(chunks):
            from spacetimedb_sdk.large_message_handler import ChunkInfo
            chunk_obj = ChunkInfo(
                chunk_id=chunk_id,
                total_size=len(test_data),
                chunk_count=len(chunks),
                sequence=i,
                data=chunk_info["data"],
                timestamp=time.time()
            )
            handler._incoming_chunks[chunk_id][i] = chunk_obj
            handler._chunk_metadata[chunk_id]["received_chunks"] += 1
        
        # Reassemble
        reassembled = handler._reassemble_message(chunk_id)
        end_time = time.time()
        
        duration = end_time - start_time
        
        print(f"Reassembled {len(test_data)} bytes from {len(chunks)} chunks in {duration:.3f}s")
        
        # Should reassemble quickly and correctly
        assert duration < 0.1, "Reassembly should be very fast"
        assert len(reassembled) == len(test_data)


class TestConcurrentClientSimulation:
    """Simulate multiple concurrent clients."""
    
    def test_multiple_client_simulation(self):
        """Test SDK can handle multiple concurrent client connections."""
        
        # Simulate 10 concurrent clients
        clients = []
        results = []
        
        def simulate_client(client_id: int):
            """Simulate a client's message processing."""
            try:
                # Create client with unique protocol
                client = WebSocketClient(protocol=TEXT_PROTOCOL)
                
                # Process messages
                for i in range(100):
                    message = {
                        "CallReducer": {
                            "reducer": f"client_{client_id}_action",
                            "args": {"iteration": i},
                            "request_id": client_id * 1000 + i
                        }
                    }
                    
                    # Validate message
                    SpacetimeDBMessageValidator.validate_message(message)
                    
                    # Record metrics
                    client.subscription_metrics.record_subscription_data(
                        f"client_{client_id}_table", 
                        len(json.dumps(message))
                    )
                
                # Get final health
                health = client.get_all_subscription_health()
                results.append((client_id, health))
                
            except Exception as e:
                results.append((client_id, f"Error: {e}"))
        
        # Run concurrent clients
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for client_id in range(10):
                future = executor.submit(simulate_client, client_id)
                futures.append(future)
            
            # Wait for completion
            for future in futures:
                future.result()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"10 concurrent clients processed 1000 messages in {duration:.2f}s")
        
        # Should complete quickly
        assert duration < 10.0, "Concurrent client simulation should complete quickly"
        
        # All clients should succeed
        assert len(results) == 10
        for client_id, result in results:
            assert not isinstance(result, str), f"Client {client_id} failed: {result}"
            assert isinstance(result, dict), f"Client {client_id} should return health dict"


class TestMemoryUsage:
    """Test memory usage characteristics."""
    
    def test_metrics_memory_usage(self):
        """Test that metrics don't consume excessive memory."""
        
        metrics = SubscriptionMetrics()
        
        # Add data for many tables
        for table_id in range(1000):
            table_name = f"memory_test_table_{table_id}"
            
            # Add 100 data points per table
            for i in range(100):
                metrics.record_subscription_data(table_name, 128)
        
        # Should have 1000 tables with 100 messages each
        all_health = metrics.get_all_subscription_health()
        assert len(all_health) == 1000
        
        # Each table should have recorded data
        for health in all_health.values():
            assert health['message_count'] == 100
            assert health['total_bytes'] == 12800  # 128 * 100
    
    def test_large_message_handler_cleanup(self):
        """Test that large message handler cleans up properly."""
        
        handler = LargeMessageHandler(lambda x: None)
        
        # Create and abandon multiple chunked messages
        for i in range(50):
            chunk_id = f"abandoned_chunk_{i}"
            handler._chunk_metadata[chunk_id] = {
                "total_size": 10000,
                "chunk_count": 5,
                "message_type": "test",
                "start_time": time.time() - 100,  # Old timestamp
                "received_chunks": 0
            }
            handler._incoming_chunks[chunk_id] = {}
        
        # Should have 50 abandoned chunks
        assert len(handler._chunk_metadata) == 50
        
        # Run cleanup
        handler._cleanup_stale_chunks()
        
        # Should have cleaned up old chunks
        assert len(handler._chunk_metadata) == 0
        assert len(handler._incoming_chunks) == 0


if __name__ == "__main__":
    # Run performance benchmarks
    pytest.main([__file__, "-v", "-s", "--tb=short"])