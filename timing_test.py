#!/usr/bin/env python3
"""
Standalone timing analysis test to diagnose timing attack resistance issues.
"""
import time
import statistics
from typing import List, Tuple


class TimingAnalyzer:
    """Analyzes timing data for consistency with robust statistical methods."""
    
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
    def remove_outliers(measurements: List[float], z_threshold: float = 2.5) -> List[float]:
        """
        Remove statistical outliers using modified Z-score method.
        """
        if len(measurements) < 3:
            return measurements
        
        # Calculate median and median absolute deviation (MAD)
        median = statistics.median(measurements)
        mad = statistics.median([abs(x - median) for x in measurements])
        
        # If MAD is 0, use standard deviation instead
        if mad == 0:
            mad = statistics.stdev(measurements) * 0.6745  # Convert to MAD equivalent
        
        if mad == 0:  # All values are identical
            return measurements
        
        # Calculate modified Z-scores
        modified_z_scores = [abs(0.6745 * (x - median) / mad) for x in measurements]
        
        # Filter out outliers
        filtered = [measurements[i] for i, z in enumerate(modified_z_scores) if z < z_threshold]
        
        # Ensure we keep at least 70% of the original measurements
        min_keep = max(3, int(len(measurements) * 0.7))
        if len(filtered) < min_keep:
            return measurements
        
        return filtered
    
    @staticmethod
    def calculate_confidence_interval(measurements: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """
        Calculate confidence interval for timing measurements.
        """
        if len(measurements) < 2:
            return 0.0, 0.0
        
        mean = statistics.mean(measurements)
        std_err = statistics.stdev(measurements) / (len(measurements) ** 0.5)
        
        # Use t-distribution for small samples (< 30), normal for larger
        if len(measurements) < 30:
            # Approximate t-value for common confidence levels
            t_values = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
            t_value = t_values.get(confidence, 1.96)
        else:
            # Use normal distribution z-value
            t_value = 1.96  # 95% confidence
        
        margin = t_value * std_err
        lower = (mean - margin) * 1000  # Convert to ms
        upper = (mean + margin) * 1000  # Convert to ms
        
        return lower, upper
    
    @staticmethod
    def is_timing_consistent(measurements: List[float], max_variance_ms: float = 5.0, 
                           outlier_removal: bool = True, statistical_analysis: bool = True) -> bool:
        """
        Check if timing measurements are consistent using robust statistical analysis.
        """
        if len(measurements) < 3:
            return True  # Too few measurements to determine inconsistency
        
        # Make a copy to avoid modifying original data
        data = measurements.copy()
        
        # Remove outliers if requested
        if outlier_removal:
            data = TimingAnalyzer.remove_outliers(data)
        
        # If we don't have enough data after outlier removal, be lenient
        if len(data) < 3:
            return True
        
        if statistical_analysis:
            # Use statistical analysis for more robust timing consistency check
            
            # 1. Check coefficient of variation (CV)
            mean_time = statistics.mean(data)
            std_dev = statistics.stdev(data)
            
            if mean_time > 0:
                cv = std_dev / mean_time
                # Allow higher variation for very fast operations (< 1ms)
                cv_threshold = 0.5 if mean_time * 1000 < 1.0 else 0.3
                if cv > cv_threshold:
                    print(f"FAIL: CV too high: {cv:.3f} > {cv_threshold}")
                    return False
            
            # 2. Check interquartile range (IQR) relative to median
            sorted_data = sorted(data)
            n = len(sorted_data)
            q1_idx = n // 4
            q3_idx = (3 * n) // 4
            
            if q1_idx != q3_idx:
                q1 = sorted_data[q1_idx]
                q3 = sorted_data[q3_idx]
                median = statistics.median(data)
                
                if median > 0:
                    iqr_ratio = (q3 - q1) / median
                    # Allow higher IQR ratio for very fast operations
                    iqr_threshold = 0.4 if median * 1000 < 1.0 else 0.2
                    if iqr_ratio > iqr_threshold:
                        print(f"FAIL: IQR ratio too high: {iqr_ratio:.3f} > {iqr_threshold}")
                        return False
            
            # 3. Check 95% confidence interval width
            lower, upper = TimingAnalyzer.calculate_confidence_interval(data)
            ci_width = upper - lower
            mean_ms = mean_time * 1000
            
            if mean_ms > 0:
                ci_ratio = ci_width / mean_ms
                # Be more lenient for very fast operations
                ci_threshold = 0.6 if mean_ms < 1.0 else 0.4
                if ci_ratio > ci_threshold:
                    print(f"FAIL: CI ratio too high: {ci_ratio:.3f} > {ci_threshold}")
                    return False
        
        # Fallback to simple max difference check with increased tolerance
        _, _, max_diff = TimingAnalyzer.measure_timing_variance(data)
        max_diff_ms = max_diff * 1000
        
        if max_diff_ms >= max_variance_ms:
            print(f"FAIL: Max diff too high: {max_diff_ms:.3f}ms >= {max_variance_ms}ms")
            return False
        
        return True


def test_basic_timing():
    """Test basic timing consistency with simple operations."""
    print("=== Testing Basic Timing Consistency ===")
    
    # Test with very fast string comparison
    measurements = []
    for i in range(50):
        start = time.perf_counter()
        result = "test_string" == "test_string"
        end = time.perf_counter()
        measurements.append(end - start)
    
    print(f"Raw measurements (first 10): {[f'{m*1000000:.1f}μs' for m in measurements[:10]]}")
    print(f"Mean: {statistics.mean(measurements)*1000000:.1f}μs")
    print(f"Std dev: {statistics.stdev(measurements)*1000000:.1f}μs")
    print(f"Max diff: {(max(measurements) - min(measurements))*1000000:.1f}μs")
    
    # Test different configurations
    configs = [
        (True, True, "Full analysis"),
        (True, False, "No statistical analysis"),
        (False, True, "No outlier removal"),
        (False, False, "Simple analysis only")
    ]
    
    for outlier_removal, statistical_analysis, desc in configs:
        result = TimingAnalyzer.is_timing_consistent(
            measurements, 
            max_variance_ms=5.0,
            outlier_removal=outlier_removal,
            statistical_analysis=statistical_analysis
        )
        print(f"{desc}: {'PASS' if result else 'FAIL'}")
    
    print()


def test_credential_verification():
    """Test timing with actual credential verification."""
    print("=== Testing Credential Verification Timing ===")
    
    import secrets
    
    def verify_credentials_secure(stored: str, provided: str) -> bool:
        """Simplified secure credential verification."""
        if not isinstance(stored, str) or not isinstance(provided, str):
            return False
        stored_bytes = stored.encode('utf-8')
        provided_bytes = provided.encode('utf-8')
        return secrets.compare_digest(stored_bytes, provided_bytes)
    
    stored_credential = "correct_password_123"
    
    # Test correct credentials
    correct_measurements = []
    for _ in range(30):
        start = time.perf_counter()
        verify_credentials_secure(stored_credential, stored_credential)
        end = time.perf_counter()
        correct_measurements.append(end - start)
    
    # Test incorrect credentials
    incorrect_measurements = []
    wrong_credentials = ["wrong", "different_password", "", "x" * 100]
    for wrong_cred in wrong_credentials:
        for _ in range(8):
            start = time.perf_counter()
            verify_credentials_secure(stored_credential, wrong_cred)
            end = time.perf_counter()
            incorrect_measurements.append(end - start)
    
    print(f"Correct credentials - Mean: {statistics.mean(correct_measurements)*1000000:.1f}μs")
    print(f"Incorrect credentials - Mean: {statistics.mean(incorrect_measurements)*1000000:.1f}μs")
    
    # Test timing consistency
    correct_consistent = TimingAnalyzer.is_timing_consistent(correct_measurements, max_variance_ms=5.0)
    incorrect_consistent = TimingAnalyzer.is_timing_consistent(incorrect_measurements, max_variance_ms=5.0)
    
    print(f"Correct credentials timing consistent: {'PASS' if correct_consistent else 'FAIL'}")
    print(f"Incorrect credentials timing consistent: {'PASS' if incorrect_consistent else 'FAIL'}")
    
    # Check timing difference
    correct_avg = statistics.mean(correct_measurements)
    incorrect_avg = statistics.mean(incorrect_measurements)
    timing_diff_ms = abs(correct_avg - incorrect_avg) * 1000
    
    print(f"Timing difference: {timing_diff_ms:.3f}ms")
    print(f"Timing difference acceptable: {'PASS' if timing_diff_ms < 7.5 else 'FAIL'}")
    
    print()


if __name__ == "__main__":
    test_basic_timing()
    test_credential_verification()