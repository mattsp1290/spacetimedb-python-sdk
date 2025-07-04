"""
Memory management configuration for SpacetimeDB Python SDK.

This module provides configuration options and presets for memory management
settings to prevent memory exhaustion vulnerabilities.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemoryLimits:
    """Memory limit configuration."""
    
    # Global memory limits
    total_memory_mb: int = 512                    # Total SDK memory limit
    message_memory_mb: int = 50                   # Memory for message processing
    cache_memory_mb: int = 100                    # Memory for caches
    subscription_memory_mb: int = 200             # Memory for subscriptions
    
    # Per-component limits
    max_cache_entries: int = 10000                # Maximum cache entries
    max_subscriptions: int = 1000                 # Maximum active subscriptions  
    max_pending_requests: int = 5000              # Maximum pending requests
    
    # Message processing limits
    max_message_size_mb: int = 50                 # Maximum single message size
    max_field_size_mb: int = 10                   # Maximum single field size
    max_recursion_depth: int = 50                 # Maximum recursion depth
    
    # BSATN-specific limits
    max_bsatn_output_mb: int = 100               # Maximum BSATN output size
    max_bsatn_fields: int = 100000               # Maximum BSATN fields
    max_list_items: int = 1000000                # Maximum list/array items
    max_struct_fields: int = 10000               # Maximum struct fields
    
    # Performance tuning
    eviction_threshold_percent: int = 80         # Trigger eviction at % of limit
    cleanup_interval_seconds: int = 300          # Background cleanup interval
    memory_pressure_threshold_percent: int = 85  # Memory pressure threshold


@dataclass  
class SecurityLimits:
    """Security-related limits to prevent attacks."""
    
    # DoS protection
    max_connections_per_host: int = 100          # Maximum connections per host
    rate_limit_messages_per_second: int = 1000   # Message rate limit
    max_subscription_query_length: int = 10000   # Maximum query string length
    
    # Memory bomb protection
    max_nested_depth: int = 50                   # Maximum nesting depth
    max_string_length: int = 10 * 1024 * 1024    # 10MB string limit
    max_binary_data_size: int = 50 * 1024 * 1024 # 50MB binary data limit
    
    # Resource exhaustion protection
    max_open_files: int = 1000                   # Maximum open file handles
    max_threads: int = 100                       # Maximum thread count
    timeout_seconds: int = 30                    # Operation timeout


class MemoryConfigPresets:
    """Predefined memory configuration presets."""
    
    @staticmethod
    def conservative() -> MemoryLimits:
        """Conservative limits for resource-constrained environments."""
        return MemoryLimits(
            total_memory_mb=128,
            message_memory_mb=10,
            cache_memory_mb=20,
            subscription_memory_mb=50,
            max_cache_entries=1000,
            max_subscriptions=100,
            max_pending_requests=500,
            max_message_size_mb=10,
            max_field_size_mb=2,
            max_recursion_depth=20,
            max_bsatn_output_mb=20,
            max_bsatn_fields=10000,
            max_list_items=100000,
            max_struct_fields=1000
        )
    
    @staticmethod
    def standard() -> MemoryLimits:
        """Standard limits for typical applications."""
        return MemoryLimits()  # Use defaults
    
    @staticmethod
    def high_throughput() -> MemoryLimits:
        """Higher limits for high-throughput applications."""
        return MemoryLimits(
            total_memory_mb=2048,
            message_memory_mb=200,
            cache_memory_mb=500,
            subscription_memory_mb=1000,
            max_cache_entries=50000,
            max_subscriptions=5000,
            max_pending_requests=20000,
            max_message_size_mb=200,
            max_field_size_mb=50,
            max_recursion_depth=100,
            max_bsatn_output_mb=500,
            max_bsatn_fields=500000,
            max_list_items=5000000,
            max_struct_fields=50000
        )
    
    @staticmethod
    def minimal() -> MemoryLimits:
        """Minimal limits for embedded or testing environments."""
        return MemoryLimits(
            total_memory_mb=32,
            message_memory_mb=5,
            cache_memory_mb=5,
            subscription_memory_mb=10,
            max_cache_entries=100,
            max_subscriptions=10,
            max_pending_requests=50,
            max_message_size_mb=5,
            max_field_size_mb=1,
            max_recursion_depth=10,
            max_bsatn_output_mb=10,
            max_bsatn_fields=1000,
            max_list_items=10000,
            max_struct_fields=100
        )


class SecurityConfigPresets:
    """Predefined security configuration presets."""
    
    @staticmethod
    def strict() -> SecurityLimits:
        """Strict security limits."""
        return SecurityLimits(
            max_connections_per_host=10,
            rate_limit_messages_per_second=100,
            max_subscription_query_length=1000,
            max_nested_depth=10,
            max_string_length=1024 * 1024,       # 1MB
            max_binary_data_size=5 * 1024 * 1024, # 5MB
            max_open_files=100,
            max_threads=10,
            timeout_seconds=10
        )
    
    @staticmethod
    def standard() -> SecurityLimits:
        """Standard security limits."""
        return SecurityLimits()  # Use defaults
    
    @staticmethod
    def permissive() -> SecurityLimits:
        """More permissive limits for trusted environments."""
        return SecurityLimits(
            max_connections_per_host=1000,
            rate_limit_messages_per_second=10000,
            max_subscription_query_length=100000,
            max_nested_depth=100,
            max_string_length=100 * 1024 * 1024,    # 100MB
            max_binary_data_size=500 * 1024 * 1024, # 500MB
            max_open_files=10000,
            max_threads=1000,
            timeout_seconds=300
        )


class MemoryConfiguration:
    """Central memory configuration manager."""
    
    def __init__(
        self, 
        memory_limits: Optional[MemoryLimits] = None,
        security_limits: Optional[SecurityLimits] = None
    ):
        self.memory_limits = memory_limits or MemoryConfigPresets.standard()
        self.security_limits = security_limits or SecurityConfigPresets.standard()
        self._validation_enabled = True
        
    def apply_preset(self, preset_name: str) -> None:
        """Apply a predefined configuration preset."""
        memory_presets = {
            'conservative': MemoryConfigPresets.conservative,
            'standard': MemoryConfigPresets.standard,
            'high_throughput': MemoryConfigPresets.high_throughput,
            'minimal': MemoryConfigPresets.minimal
        }
        
        security_presets = {
            'strict': SecurityConfigPresets.strict,
            'standard': SecurityConfigPresets.standard,
            'permissive': SecurityConfigPresets.permissive
        }
        
        if preset_name in memory_presets:
            self.memory_limits = memory_presets[preset_name]()
            logger.info(f"Applied memory preset: {preset_name}")
        
        if preset_name in security_presets:
            self.security_limits = security_presets[preset_name]()
            logger.info(f"Applied security preset: {preset_name}")
    
    def validate_configuration(self) -> bool:
        """Validate the current configuration for consistency."""
        if not self._validation_enabled:
            return True
        
        issues = []
        
        # Check memory limit consistency
        component_memory = (
            self.memory_limits.message_memory_mb +
            self.memory_limits.cache_memory_mb +
            self.memory_limits.subscription_memory_mb
        )
        
        if component_memory > self.memory_limits.total_memory_mb:
            issues.append(
                f"Component memory ({component_memory}MB) exceeds total limit "
                f"({self.memory_limits.total_memory_mb}MB)"
            )
        
        # Check size consistency
        if self.memory_limits.max_field_size_mb > self.memory_limits.max_message_size_mb:
            issues.append("Field size limit exceeds message size limit")
        
        if self.memory_limits.max_message_size_mb > self.memory_limits.message_memory_mb:
            issues.append("Message size limit exceeds message memory allocation")
        
        # Check security limits
        if self.security_limits.max_string_length > self.memory_limits.max_field_size_mb * 1024 * 1024:
            issues.append("Security string limit exceeds memory field limit")
        
        if issues:
            for issue in issues:
                logger.warning(f"Configuration issue: {issue}")
            return False
        
        return True
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration."""
        return {
            'memory_limits': {
                'total_memory_mb': self.memory_limits.total_memory_mb,
                'message_memory_mb': self.memory_limits.message_memory_mb,
                'cache_memory_mb': self.memory_limits.cache_memory_mb,
                'subscription_memory_mb': self.memory_limits.subscription_memory_mb,
                'max_cache_entries': self.memory_limits.max_cache_entries,
                'max_subscriptions': self.memory_limits.max_subscriptions,
                'max_message_size_mb': self.memory_limits.max_message_size_mb,
                'max_recursion_depth': self.memory_limits.max_recursion_depth
            },
            'security_limits': {
                'max_connections_per_host': self.security_limits.max_connections_per_host,
                'rate_limit_messages_per_second': self.security_limits.rate_limit_messages_per_second,
                'max_nested_depth': self.security_limits.max_nested_depth,
                'max_string_length': self.security_limits.max_string_length,
                'timeout_seconds': self.security_limits.timeout_seconds
            },
            'validation_status': self.validate_configuration()
        }
    
    def set_validation_enabled(self, enabled: bool) -> None:
        """Enable or disable configuration validation."""
        self._validation_enabled = enabled
    
    def update_memory_limits(self, **kwargs) -> None:
        """Update specific memory limit values."""
        for key, value in kwargs.items():
            if hasattr(self.memory_limits, key):
                setattr(self.memory_limits, key, value)
                logger.info(f"Updated memory limit {key} to {value}")
            else:
                logger.warning(f"Unknown memory limit parameter: {key}")
        
        if self._validation_enabled:
            self.validate_configuration()
    
    def update_security_limits(self, **kwargs) -> None:
        """Update specific security limit values."""
        for key, value in kwargs.items():
            if hasattr(self.security_limits, key):
                setattr(self.security_limits, key, value)
                logger.info(f"Updated security limit {key} to {value}")
            else:
                logger.warning(f"Unknown security limit parameter: {key}")
        
        if self._validation_enabled:
            self.validate_configuration()


# Global configuration instance
_global_config: Optional[MemoryConfiguration] = None


def get_global_config() -> MemoryConfiguration:
    """Get or create the global memory configuration."""
    global _global_config
    if _global_config is None:
        _global_config = MemoryConfiguration()
    return _global_config


def configure_memory(
    preset: Optional[str] = None,
    memory_limits: Optional[MemoryLimits] = None,
    security_limits: Optional[SecurityLimits] = None,
    **kwargs
) -> MemoryConfiguration:
    """
    Configure global memory management settings.
    
    Args:
        preset: Configuration preset name ('conservative', 'standard', 'high_throughput', 'minimal')
        memory_limits: Custom memory limits
        security_limits: Custom security limits
        **kwargs: Additional configuration parameters
        
    Returns:
        The configured MemoryConfiguration instance
    """
    global _global_config
    
    if preset:
        _global_config = MemoryConfiguration()
        _global_config.apply_preset(preset)
    else:
        _global_config = MemoryConfiguration(memory_limits, security_limits)
    
    # Apply any additional parameters
    if kwargs:
        memory_params = {}
        security_params = {}
        
        for key, value in kwargs.items():
            if hasattr(_global_config.memory_limits, key):
                memory_params[key] = value
            elif hasattr(_global_config.security_limits, key):
                security_params[key] = value
        
        if memory_params:
            _global_config.update_memory_limits(**memory_params)
        if security_params:
            _global_config.update_security_limits(**security_params)
    
    logger.info("Memory configuration updated")
    return _global_config


def reset_config() -> None:
    """Reset configuration to defaults (useful for testing)."""
    global _global_config
    _global_config = None


# Export commonly used presets
CONSERVATIVE_CONFIG = MemoryConfigPresets.conservative()
STANDARD_CONFIG = MemoryConfigPresets.standard()
HIGH_THROUGHPUT_CONFIG = MemoryConfigPresets.high_throughput()
MINIMAL_CONFIG = MemoryConfigPresets.minimal()

STRICT_SECURITY = SecurityConfigPresets.strict()
STANDARD_SECURITY = SecurityConfigPresets.standard()
PERMISSIVE_SECURITY = SecurityConfigPresets.permissive()