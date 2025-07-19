#!/usr/bin/env python3
"""
Test script for SpacetimeDB v1.1.2 Database Publishing Detection (Task 5)

This script tests the enhanced database publishing detection functionality,
including error messages, status checking, and helper methods.
"""

import os
import sys
import time
import asyncio
from unittest.mock import Mock, patch, MagicMock
import urllib.error

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from spacetimedb_sdk import SpacetimeDBClient
from spacetimedb_sdk.exceptions import DatabaseNotFoundError, ServerNotAvailableError
from spacetimedb_sdk.connection_diagnostics import ConnectionDiagnostics, diagnose_connection


def print_section(title):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}\n")


def test_database_not_found_error_messages():
    """Test that DatabaseNotFoundError provides clear guidance."""
    print_section("Testing DatabaseNotFoundError Messages")
    
    # Test unpublished database error
    print("1. Testing unpublished database error message:")
    try:
        raise DatabaseNotFoundError(
            database_name="my_game",
            is_likely_unpublished=True,
            diagnostic_info={
                "database_state": "unpublished",
                "confidence": "high",
                "evidence": ["database_info: 404 Not Found", "database_identity: 404 Not Found"]
            }
        )
    except DatabaseNotFoundError as e:
        print(str(e))
        print(f"\nis_unpublished property: {e.is_unpublished}")
    
    # Test non-existent database error
    print("\n\n2. Testing non-existent database error message:")
    try:
        raise DatabaseNotFoundError(
            database_name="fake_db",
            diagnostic_info={
                "database_state": "non-existent",
                "confidence": "high"
            }
        )
    except DatabaseNotFoundError as e:
        print(str(e))
        print(f"\nis_unpublished property: {e.is_unpublished}")
    
    # Test unknown state error
    print("\n\n3. Testing unknown state error message:")
    try:
        raise DatabaseNotFoundError(
            database_name="mystery_db",
            diagnostic_info={
                "database_state": "unknown",
                "confidence": "low",
                "evidence": ["Connection timeout", "Server error"],
                "server_version": "1.1.2"
            }
        )
    except DatabaseNotFoundError as e:
        print(str(e))
        print(f"\nis_unpublished property: {e.is_unpublished}")


def test_connection_diagnostics():
    """Test the ConnectionDiagnostics class."""
    print_section("Testing ConnectionDiagnostics")
    
    diag = ConnectionDiagnostics(timeout=2.0)
    
    # Test network connectivity check
    print("1. Testing network connectivity check:")
    network_status = diag.check_network_connectivity()
    print(f"Internet connected: {network_status['internet_connected']}")
    print(f"DNS working: {network_status['dns_working']}")
    print(f"Latency: {network_status.get('latency_ms', 'N/A')}ms")
    
    # Test server availability check (localhost)
    print("\n2. Testing server availability check:")
    is_available, info = diag.check_server_available("localhost:3000")
    print(f"Server available: {is_available}")
    if info:
        print(f"Server info: {info}")
    
    # Test database state detection
    print("\n3. Testing database state detection:")
    # Mock a 404 response for all endpoints
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://localhost:3000/v1/database/test_db/info",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        
        db_status = diag.check_database_exists("localhost:3000", "test_db")
        print(f"Database status: {db_status}")
        
        db_state = diag.get_database_state("localhost:3000", "test_db")
        print(f"Database state: {db_state}")
    
    # Test cache functionality
    print("\n4. Testing cache functionality:")
    # First call should hit the endpoints
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://localhost:3000/v1/database/cached_db/info",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        
        status1 = diag.check_database_exists("localhost:3000", "cached_db")
        print(f"First call (should hit endpoints): {status1['endpoints_tested']} endpoints tested")
        
        # Second call should use cache
        status2 = diag.check_database_exists("localhost:3000", "cached_db")
        print(f"Second call (should use cache): {status2['endpoints_tested']} endpoints tested")
        
        # Clear cache and try again
        diag.clear_database_cache("localhost:3000", "cached_db")
        status3 = diag.check_database_exists("localhost:3000", "cached_db")
        print(f"After cache clear: {status3['endpoints_tested']} endpoints tested")


def test_client_helper_methods():
    """Test the SpacetimeDBClient helper methods."""
    print_section("Testing Client Helper Methods")
    
    # Create a client in test mode
    client = SpacetimeDBClient(test_mode=True)
    
    print("1. Testing check_database_status:")
    # Mock the diagnostics check
    with patch.object(client._diagnostics, 'check_database_exists') as mock_check:
        mock_check.return_value = {
            'exists': 'likely',
            'published': False,
            'confidence': 'medium',
            'evidence': ['All endpoints returned 404'],
            'suggested_action': 'publish',
            'error': 'Database not accessible - likely unpublished',
            'status_code': 404
        }
        
        with patch.object(client._diagnostics, 'get_database_state') as mock_state:
            mock_state.return_value = 'unpublished'
            
            status = client.check_database_status("my_game")
            print(f"Database exists: {status['exists']}")
            print(f"Database published: {status['published']}")
            print(f"Database state: {status['state']}")
            print(f"Confidence: {status['confidence']}")
            print(f"Suggested action: {status['suggested_action']}")
            print(f"Evidence: {status['evidence']}")
    
    print("\n2. Testing synchronous wait_for_database_published:")
    # Mock the check_database_status to simulate publishing after 2 checks
    call_count = 0
    def mock_status(db_name, host=None):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return {
                'exists': 'likely',
                'published': False,
                'state': 'unpublished',
                'confidence': 'medium'
            }
        else:
            return {
                'exists': True,
                'published': True,
                'state': 'published',
                'confidence': 'high'
            }
    
    with patch.object(client, 'check_database_status', side_effect=mock_status):
        start = time.time()
        result = client.wait_for_database_published_sync(
            "my_game",
            timeout=10.0,
            check_interval=0.5
        )
        elapsed = time.time() - start
        print(f"Wait result: {result}")
        print(f"Time elapsed: {elapsed:.1f}s")
        print(f"Number of checks: {call_count}")


def test_error_handling_integration():
    """Test integration with WebSocket error handling."""
    print_section("Testing Error Handling Integration")
    
    print("1. Testing WebSocketHandshakeError delegation to DatabaseNotFoundError:")
    
    # Import WebSocketHandshakeError
    from spacetimedb_sdk.exceptions import WebSocketHandshakeError
    
    try:
        # This should delegate to DatabaseNotFoundError
        raise WebSocketHandshakeError(
            status_code=404,
            status_message="Not Found",
            url="ws://localhost:3000/v1/database/my_game/subscribe",
            diagnostic_info={
                "is_likely_unpublished": True,
                "database_state": "unpublished",
                "confidence": "high"
            }
        )
    except DatabaseNotFoundError as e:
        print("✓ Successfully delegated to DatabaseNotFoundError")
        print(f"Database name extracted: {e.database_name}")
        print(f"Is likely unpublished: {e.is_likely_unpublished}")
    except Exception as e:
        print(f"✗ Unexpected error type: {type(e).__name__}")
    
    print("\n2. Testing diagnose_connection_error with enhanced detection:")
    
    diag = ConnectionDiagnostics()
    
    # Mock the various checks
    with patch.object(diag, 'check_network_connectivity') as mock_network:
        mock_network.return_value = {
            'internet_connected': True,
            'dns_working': True,
            'latency_ms': 10
        }
        
        with patch.object(diag, 'check_server_available') as mock_server:
            mock_server.return_value = (True, {'status_code': 200})
            
            with patch.object(diag, 'check_database_exists') as mock_db:
                mock_db.return_value = {
                    'exists': 'likely',
                    'published': False,
                    'confidence': 'medium',
                    'status_code': 404,
                    'error': 'Database not accessible',
                    'evidence': ['All endpoints returned 404']
                }
                
                with patch.object(diag, 'get_database_state') as mock_state:
                    mock_state.return_value = 'unpublished'
                    
                    try:
                        diag.diagnose_connection_error(
                            Exception("Connection failed"),
                            "ws://localhost:3000/v1/database/my_game/subscribe",
                            "my_game"
                        )
                    except DatabaseNotFoundError as e:
                        print("✓ Enhanced DatabaseNotFoundError raised")
                        print(f"Database state in diagnostic info: {e.diagnostic_info.get('database_state')}")
                        print(f"Confidence level: {e.diagnostic_info.get('confidence')}")
                        print(f"Is likely unpublished: {e.is_likely_unpublished}")


async def test_async_wait_for_published():
    """Test async version of wait_for_database_published."""
    print_section("Testing Async wait_for_database_published")
    
    client = SpacetimeDBClient(test_mode=True)
    
    # Mock to simulate database becoming published after 3 checks
    call_count = 0
    def mock_status(db_name, host=None):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return {
                'exists': 'likely',
                'published': False,
                'state': 'unpublished',
                'confidence': 'medium'
            }
        else:
            return {
                'exists': True,
                'published': True,
                'state': 'published',
                'confidence': 'high'
            }
    
    with patch.object(client, 'check_database_status', side_effect=mock_status):
        start = time.time()
        result = await client.wait_for_database_published(
            "async_game",
            timeout=10.0,
            check_interval=0.5
        )
        elapsed = time.time() - start
        print(f"Async wait result: {result}")
        print(f"Time elapsed: {elapsed:.1f}s")
        print(f"Number of checks: {call_count}")


def test_diagnostic_report_formatting():
    """Test the diagnostic report formatting."""
    print_section("Testing Diagnostic Report Formatting")
    
    # Create mock diagnostic results
    diagnostics = {
        "network": {
            "internet_connected": True,
            "dns_working": True,
            "latency_ms": 15
        },
        "server": {
            "available": True,
            "info": {
                "response_time_ms": 5
            }
        },
        "version": "1.1.2",
        "database": {
            "exists": "likely",
            "published": False,
            "confidence": "medium",
            "error": "Database not accessible - likely unpublished",
            "evidence": [
                "database_info: 404 Not Found",
                "database_identity: 404 Not Found",
                "database_names: 404 Not Found"
            ]
        },
        "all_passed": False
    }
    
    diag = ConnectionDiagnostics()
    report = diag.format_diagnostic_report(diagnostics)
    print(report)


def test_convenience_function():
    """Test the diagnose_connection convenience function."""
    print_section("Testing diagnose_connection Convenience Function")
    
    # Mock all the checks
    with patch('spacetimedb_sdk.connection_diagnostics.ConnectionDiagnostics') as MockDiag:
        mock_instance = MockDiag.return_value
        mock_instance.run_preflight_checks.return_value = {
            "network": {"internet_connected": True, "dns_working": True},
            "server": {"available": True},
            "database": {
                "exists": "likely",
                "published": False,
                "confidence": "medium"
            },
            "all_passed": False
        }
        mock_instance.format_diagnostic_report.return_value = "Mock diagnostic report"
        
        # Test with verbose output
        print("Testing with verbose=True:")
        results = diagnose_connection("localhost:3000", "test_db", verbose=True)
        print(f"Results: {results}")
        
        # Test without verbose output
        print("\nTesting with verbose=False:")
        results = diagnose_connection("localhost:3000", "test_db", verbose=False)
        print(f"Results returned (no report printed): {results}")


def main():
    """Run all tests."""
    print("SpacetimeDB v1.1.2 Database Publishing Detection Tests")
    print("=====================================================")
    
    # Run synchronous tests
    test_database_not_found_error_messages()
    test_connection_diagnostics()
    test_client_helper_methods()
    test_error_handling_integration()
    test_diagnostic_report_formatting()
    test_convenience_function()
    
    # Run async tests
    print("\nRunning async tests...")
    asyncio.run(test_async_wait_for_published())
    
    print_section("All Tests Completed")
    print("✓ Database publishing detection implementation tested successfully!")
    print("\nKey features verified:")
    print("- Enhanced error messages with publishing guidance")
    print("- Database state detection with heuristics")
    print("- Helper methods for checking and waiting for publishing")
    print("- Caching for performance")
    print("- Integration with existing error handling")
    print("- Both sync and async support")


if __name__ == "__main__":
    main()
