"""
Timing Attack Resistance Tests

This module tests that authentication operations are resistant to timing attacks
by ensuring consistent execution times regardless of input differences.

Critical Security Tests:
- Credential verification timing consistency
- Token comparison timing independence
- Password verification timing uniformity
- Rate limiting effectiveness
- Authentication failure timing consistency

These tests help prevent timing-based side-channel attacks where attackers
can infer information about valid credentials by measuring execution times.
"""

import time
import statistics
import secrets
import pytest
from typing import List, Tuple
import threading
import concurrent.futures

from src.spacetimedb_sdk.auth.secure_verification import (
    SecureVerificationManager,
    verify_credentials_secure,
    verify_token_secure,
    verify_password_secure,
    VerificationResult
)
from src.spacetimedb_sdk.connection.authentication_handler import AuthenticationHandler


class TimingAnalyzer:
    """Analyzes timing data for consistency."""
    
    @staticmethod
    def measure_timing_variance(measurements: List[float]) -> Tuple[float, float, float]:
        """
        Calculate timing variance metrics.
        
        Returns:
            Tuple of (variance, std_dev, max_difference)
        """
        if len(measurements) < 2:
            return 0.0, 0.0, 0.0
        
        variance = statistics.variance(measurements)
        std_dev = statistics.stdev(measurements)
        max_diff = max(measurements) - min(measurements)
        
        return variance, std_dev, max_diff
    
    @staticmethod
    def is_timing_consistent(measurements: List[float], max_variance_ms: float = 1.0) -> bool:
        """
        Check if timing measurements are consistent (variance < threshold).
        
        Args:
            measurements: List of timing measurements in seconds
            max_variance_ms: Maximum allowed variance in milliseconds
            
        Returns:
            True if timing is consistent, False otherwise
        """
        _, _, max_diff = TimingAnalyzer.measure_timing_variance(measurements)
        max_diff_ms = max_diff * 1000  # Convert to milliseconds
        
        return max_diff_ms < max_variance_ms


class TestTimingAttackResistance:
    """Test suite for timing attack resistance."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.verification_manager = SecureVerificationManager()
        self.auth_handler = AuthenticationHandler()
        
        # Test credentials of various lengths
        self.test_credentials = [
            ("short", "test"),
            ("medium_length", "test_password_123"),
            ("very_long_credential", "this_is_a_very_long_password_that_should_test_timing_consistency_across_different_string_lengths"),
            ("empty", ""),
            ("special_chars", "p@ssw0rd!#$%^&*()"),
            ("unicode", "пароль密码パスワード"),
        ]
        
        # Number of measurements for statistical significance
        self.measurement_count = 100
        self.timing_threshold_ms = 1.0  # 1ms maximum variance
    
    def measure_execution_time(self, func, *args, **kwargs) -> float:
        """Measure execution time of a function."""
        start = time.perf_counter()
        func(*args, **kwargs)
        return time.perf_counter() - start
    
    def test_credential_verification_timing_consistency(self):
        """Test that credential verification has consistent timing."""
        stored_credential = "correct_password_123"
        
        # Test with correct credentials
        correct_times = []
        for _ in range(self.measurement_count):
            timing = self.measure_execution_time(
                verify_credentials_secure,
                stored_credential,
                stored_credential
            )
            correct_times.append(timing)
        
        # Test with incorrect credentials of varying lengths
        incorrect_times = []
        for wrong_cred, _ in self.test_credentials:
            for _ in range(10):  # Fewer iterations per credential
                timing = self.measure_execution_time(
                    verify_credentials_secure,
                    stored_credential,
                    wrong_cred
                )
                incorrect_times.append(timing)
        
        # Analyze timing consistency
        assert TimingAnalyzer.is_timing_consistent(
            correct_times, self.timing_threshold_ms
        ), "Correct credential verification timing is inconsistent"
        
        assert TimingAnalyzer.is_timing_consistent(
            incorrect_times, self.timing_threshold_ms
        ), "Incorrect credential verification timing is inconsistent"
        
        # Verify that correct and incorrect verifications have similar timing
        correct_avg = statistics.mean(correct_times)
        incorrect_avg = statistics.mean(incorrect_times)
        timing_diff_ms = abs(correct_avg - incorrect_avg) * 1000
        
        assert timing_diff_ms < self.timing_threshold_ms, (
            f"Timing difference between correct and incorrect credentials too large: "
            f"{timing_diff_ms:.3f}ms > {self.timing_threshold_ms}ms"
        )
    
    def test_token_verification_timing_consistency(self):
        """Test that token verification has consistent timing."""
        stored_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        # Test with various wrong tokens of different lengths
        timing_measurements = []
        
        for test_name, wrong_token in self.test_credentials:
            for _ in range(10):
                timing = self.measure_execution_time(
                    verify_token_secure,
                    stored_token,
                    wrong_token
                )
                timing_measurements.append(timing)
        
        # Test with correct token
        for _ in range(20):
            timing = self.measure_execution_time(
                verify_token_secure,
                stored_token,
                stored_token
            )
            timing_measurements.append(timing)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms
        ), "Token verification timing is inconsistent across different inputs"
    
    def test_password_verification_timing_consistency(self):
        """Test that password verification has consistent timing."""
        stored_hash = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # "password"
        salt = "random_salt_123"
        
        timing_measurements = []
        
        # Test with various wrong passwords
        wrong_passwords = ["wrong", "incorrect_password", "", "p", "very_long_incorrect_password_that_should_not_affect_timing"]
        
        for wrong_password in wrong_passwords:
            for _ in range(20):
                timing = self.measure_execution_time(
                    verify_password_secure,
                    stored_hash,
                    wrong_password,
                    salt
                )
                timing_measurements.append(timing)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms * 2  # Allow slightly more variance for password hashing
        ), "Password verification timing is inconsistent"
    
    def test_authentication_handler_credential_verification(self):
        """Test timing consistency of authentication handler's credential verification."""
        stored_cred = "test_credential_12345"
        
        timing_measurements = []
        
        # Test various credential lengths and content
        test_inputs = [
            "",
            "x",
            "wrong",
            "test_credential_12345",  # Correct
            "test_credential_123456",  # One char longer
            "test_credential_1234",   # One char shorter
            "wrong_credential_completely_different_length",
        ]
        
        for test_input in test_inputs:
            for _ in range(15):
                timing = self.measure_execution_time(
                    self.auth_handler._verify_credentials,
                    stored_cred,
                    test_input
                )
                timing_measurements.append(timing)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms
        ), "AuthenticationHandler credential verification timing is inconsistent"
    
    def test_identity_token_verification_timing(self):
        """Test timing consistency of identity and token verification."""
        expected_identity = "deadbeefcafebabe1234567890abcdef12345678"
        expected_token = "jwt.token.signature"
        
        timing_measurements = []
        
        # Test various combinations of correct/incorrect identity and token
        test_cases = [
            (expected_identity, expected_token),     # Both correct
            ("wrong_identity", expected_token),      # Wrong identity
            (expected_identity, "wrong_token"),      # Wrong token  
            ("wrong_identity", "wrong_token"),       # Both wrong
            ("", ""),                                # Both empty
            ("x", "y"),                              # Short values
            ("very_long_incorrect_identity_value", "very_long_incorrect_token_value"), # Long values
        ]
        
        for identity, token in test_cases:
            for _ in range(15):
                timing = self.measure_execution_time(
                    self.auth_handler.verify_identity_credentials,
                    expected_identity,
                    identity,
                    expected_token,
                    token
                )
                timing_measurements.append(timing)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms * 1.5  # Allow slightly more variance for dual verification
        ), "Identity and token verification timing is inconsistent"
    
    def test_concurrent_verification_timing(self):
        """Test timing consistency under concurrent access."""
        stored_credential = "concurrent_test_credential"
        
        def worker_verification(credential: str) -> float:
            """Worker function for concurrent testing."""
            return self.measure_execution_time(
                verify_credentials_secure,
                stored_credential,
                credential
            )
        
        # Run concurrent verifications with different inputs
        test_inputs = ["correct", "wrong1", "wrong2", "", "very_long_wrong_credential"]
        timing_measurements = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit many concurrent verification tasks
            futures = []
            for _ in range(50):
                for test_input in test_inputs:
                    futures.append(executor.submit(worker_verification, test_input))
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                timing_measurements.append(future.result())
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms * 2  # Allow more variance under concurrency
        ), "Concurrent credential verification timing is inconsistent"
    
    def test_rate_limiting_timing_consistency(self):
        """Test that rate limiting doesn't introduce timing variations."""
        manager = SecureVerificationManager(rate_limit_window=1.0, max_attempts=3)
        identifier = "test_user"
        
        timing_measurements = []
        
        # Make attempts up to rate limit
        for i in range(5):  # Exceed rate limit
            timing = self.measure_execution_time(
                manager.verify_credentials,
                "stored",
                "provided",
                identifier
            )
            timing_measurements.append(timing)
        
        # Continue with rate-limited attempts
        for i in range(10):
            timing = self.measure_execution_time(
                manager.verify_credentials,
                "stored",
                "provided",
                identifier
            )
            timing_measurements.append(timing)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms * 2
        ), "Rate limiting affects verification timing consistency"
    
    def test_empty_and_null_credential_timing(self):
        """Test timing consistency with edge cases like empty and None values."""
        timing_measurements = []
        
        # Test various edge cases
        edge_cases = [
            ("", ""),
            ("valid", ""),
            ("", "valid"),
            (None, "valid"),  # Will be handled as invalid format
            ("valid", None),  # Will be handled as invalid format
        ]
        
        for stored, provided in edge_cases:
            for _ in range(20):
                timing = self.measure_execution_time(
                    self.verification_manager.verify_credentials,
                    stored or "",
                    provided or ""
                )
                timing_measurements.append(timing)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms
        ), "Edge case credential verification timing is inconsistent"
    
    def test_statistical_timing_analysis(self):
        """Perform statistical analysis of timing measurements."""
        stored_cred = "statistical_test_credential"
        
        # Collect timing data for different scenarios
        scenarios = {
            "correct": [],
            "wrong_short": [],
            "wrong_long": [],
            "empty": []
        }
        
        # Collect measurements
        for _ in range(100):
            # Correct credential
            timing = self.measure_execution_time(
                verify_credentials_secure, stored_cred, stored_cred
            )
            scenarios["correct"].append(timing)
            
            # Wrong short credential
            timing = self.measure_execution_time(
                verify_credentials_secure, stored_cred, "x"
            )
            scenarios["wrong_short"].append(timing)
            
            # Wrong long credential
            timing = self.measure_execution_time(
                verify_credentials_secure, stored_cred, "very_long_wrong_credential_that_differs_significantly"
            )
            scenarios["wrong_long"].append(timing)
            
            # Empty credential
            timing = self.measure_execution_time(
                verify_credentials_secure, stored_cred, ""
            )
            scenarios["empty"].append(timing)
        
        # Statistical analysis
        for scenario_name, measurements in scenarios.items():
            variance, std_dev, max_diff = TimingAnalyzer.measure_timing_variance(measurements)
            
            # Convert to milliseconds for readability
            variance_ms = variance * 1000 * 1000  # variance of seconds² to ms²
            std_dev_ms = std_dev * 1000
            max_diff_ms = max_diff * 1000
            
            print(f"\n{scenario_name} scenario statistics:")
            print(f"  Standard deviation: {std_dev_ms:.3f}ms")
            print(f"  Maximum difference: {max_diff_ms:.3f}ms")
            print(f"  Mean time: {statistics.mean(measurements)*1000:.3f}ms")
            
            # Assert timing consistency
            assert max_diff_ms < self.timing_threshold_ms, (
                f"{scenario_name} scenario timing variance too high: "
                f"{max_diff_ms:.3f}ms > {self.timing_threshold_ms}ms"
            )
    
    def test_memory_access_pattern_consistency(self):
        """Test that memory access patterns don't reveal information."""
        # This test uses different string lengths to ensure that
        # memory access patterns are consistent
        
        base_string = "x" * 100
        timing_measurements = []
        
        # Test strings of different lengths but same comparison result
        test_strings = [
            "y" * 10,      # Short, different first character
            "y" * 50,      # Medium, different first character  
            "y" * 100,     # Same length, different first character
            "y" * 200,     # Longer, different first character
            "x" + "y" * 99,  # Same first char, different second
            "x" * 50 + "y" * 50,  # Same start, different middle/end
        ]
        
        for test_string in test_strings:
            for _ in range(20):
                timing = self.measure_execution_time(
                    verify_credentials_secure,
                    base_string,
                    test_string
                )
                timing_measurements.append(timing)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, self.timing_threshold_ms
        ), "Memory access patterns affect timing consistency"


@pytest.mark.security
class TestTimingAttackPrevention:
    """Additional security-focused timing attack tests."""
    
    def test_prevents_credential_enumeration(self):
        """Test that timing doesn't leak information about valid usernames."""
        verification_manager = SecureVerificationManager()
        
        # Simulate checking various usernames with consistent timing
        usernames = ["admin", "user", "test", "nonexistent", "", "a" * 100]
        timing_measurements = []
        
        for username in usernames:
            for _ in range(10):
                # Simulate credential check (always fails)
                timing = time.perf_counter()
                result = verification_manager.verify_credentials(
                    "stored_credential",
                    f"wrong_password_for_{username}"
                )
                elapsed = time.perf_counter() - timing
                timing_measurements.append(elapsed)
                
                assert result == VerificationResult.FAILURE
        
        # Verify timing consistency across different usernames
        variance, std_dev, max_diff = TimingAnalyzer.measure_timing_variance(timing_measurements)
        max_diff_ms = max_diff * 1000
        
        assert max_diff_ms < 1.0, (
            f"Username enumeration timing vulnerability detected: "
            f"max timing difference {max_diff_ms:.3f}ms"
        )
    
    def test_branch_prediction_resistance(self):
        """Test resistance to branch prediction attacks."""
        # Test that execution path doesn't depend on input content
        verification_manager = SecureVerificationManager()
        
        stored = "test_credential"
        
        # Test patterns that might affect branch prediction
        test_patterns = [
            "test_credential",      # Exact match
            "test_credentia",       # One char short
            "test_credentialx",     # One char long
            "xest_credential",      # Different first char
            "test_xredential",      # Different middle char
            "test_credentialx",     # Different last char
            "",                     # Empty
            "x" * len(stored),      # Same length, all different
        ]
        
        timing_measurements = []
        
        for pattern in test_patterns:
            for _ in range(20):
                timing = time.perf_counter()
                verification_manager.verify_credentials(stored, pattern)
                elapsed = time.perf_counter() - timing
                timing_measurements.append(elapsed)
        
        assert TimingAnalyzer.is_timing_consistent(
            timing_measurements, 1.0
        ), "Branch prediction vulnerabilities detected in credential verification"


if __name__ == "__main__":
    # Run basic timing analysis
    print("Running timing attack resistance tests...")
    
    analyzer = TimingAnalyzer()
    
    # Quick test
    stored = "test_credential"
    measurements = []
    
    for i in range(100):
        wrong_cred = "wrong" + "x" * i  # Increasing length
        start = time.perf_counter()
        verify_credentials_secure(stored, wrong_cred)
        elapsed = time.perf_counter() - start
        measurements.append(elapsed)
    
    variance, std_dev, max_diff = analyzer.measure_timing_variance(measurements)
    print(f"Timing analysis results:")
    print(f"  Standard deviation: {std_dev * 1000:.3f}ms")
    print(f"  Maximum difference: {max_diff * 1000:.3f}ms")
    print(f"  Timing consistent: {analyzer.is_timing_consistent(measurements)}")