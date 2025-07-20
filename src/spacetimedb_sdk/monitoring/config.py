"""
Monitoring configuration and settings management.
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, List
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


@dataclass
class MonitoringConfig:
    """Configuration for performance monitoring system."""
    
    # General settings
    enabled: bool = True
    enable_auto_tuning: bool = False
    enable_alerts: bool = True
    enable_metrics_export: bool = False
    
    # Collection intervals (seconds)
    metrics_collection_interval: float = 5.0
    memory_sampling_interval: float = 10.0
    performance_report_interval: float = 60.0
    
    # History limits
    max_metric_history: int = 1000
    max_alert_history: int = 1000
    max_memory_samples: int = 1000
    
    # Performance thresholds
    connection_setup_threshold_ms: float = 100.0
    event_dispatch_threshold_ms: float = 0.1
    memory_growth_threshold_mb_per_sec: float = 10.0
    pool_utilization_threshold: float = 0.9
    
    # Auto-tuning settings
    auto_tuning_interval: float = 60.0
    auto_tuning_confidence_threshold: float = 0.7
    min_data_points_for_tuning: int = 10
    
    # Export settings
    export_format: str = "json"  # json, csv, prometheus
    export_path: str = "./monitoring_data"
    export_interval: float = 300.0  # 5 minutes
    
    # Component-specific settings
    monitor_connections: bool = True
    monitor_events: bool = True
    monitor_memory: bool = True
    monitor_pools: bool = True
    monitor_websocket: bool = True
    monitor_cache: bool = True
    
    # Alert settings
    alert_cooldown_seconds: float = 60.0
    max_alerts_per_component: int = 10
    alert_log_level: str = "WARNING"
    
    # Advanced settings
    enable_tracemalloc: bool = False
    profile_cpu: bool = False
    profile_memory: bool = False
    debug_mode: bool = False
    
    @classmethod
    def from_file(cls, config_path: str) -> "MonitoringConfig":
        """Load configuration from file."""
        path = Path(config_path)
        
        if not path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls()
        
        try:
            with open(path, 'r') as f:
                if path.suffix == '.json':
                    data = json.load(f)
                else:
                    # Could support other formats (YAML, TOML, etc.)
                    logger.warning(f"Unsupported config format: {path.suffix}")
                    return cls()
            
            return cls(**data)
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            return cls()
    
    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        """Load configuration from environment variables."""
        config = cls()
        
        # Map environment variables to config fields
        env_mappings = {
            'SPACETIMEDB_MONITORING_ENABLED': ('enabled', bool),
            'SPACETIMEDB_AUTO_TUNING_ENABLED': ('enable_auto_tuning', bool),
            'SPACETIMEDB_ALERTS_ENABLED': ('enable_alerts', bool),
            'SPACETIMEDB_METRICS_EXPORT_ENABLED': ('enable_metrics_export', bool),
            'SPACETIMEDB_METRICS_INTERVAL': ('metrics_collection_interval', float),
            'SPACETIMEDB_CONNECTION_THRESHOLD': ('connection_setup_threshold_ms', float),
            'SPACETIMEDB_EVENT_THRESHOLD': ('event_dispatch_threshold_ms', float),
            'SPACETIMEDB_MEMORY_THRESHOLD': ('memory_growth_threshold_mb_per_sec', float),
            'SPACETIMEDB_EXPORT_PATH': ('export_path', str),
            'SPACETIMEDB_DEBUG_MODE': ('debug_mode', bool),
        }
        
        for env_var, (field_name, field_type) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    if field_type == bool:
                        parsed_value = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        parsed_value = field_type(value)
                    setattr(config, field_name, parsed_value)
                except ValueError as e:
                    logger.warning(f"Invalid value for {env_var}: {value} - {e}")
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    def save(self, config_path: str) -> None:
        """Save configuration to file."""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving config to {config_path}: {e}")
    
    def validate(self) -> List[str]:
        """Validate configuration and return any issues."""
        issues = []
        
        # Validate intervals
        if self.metrics_collection_interval <= 0:
            issues.append("metrics_collection_interval must be positive")
        
        if self.memory_sampling_interval <= 0:
            issues.append("memory_sampling_interval must be positive")
        
        # Validate thresholds
        if self.connection_setup_threshold_ms <= 0:
            issues.append("connection_setup_threshold_ms must be positive")
        
        if self.event_dispatch_threshold_ms <= 0:
            issues.append("event_dispatch_threshold_ms must be positive")
        
        if self.pool_utilization_threshold < 0 or self.pool_utilization_threshold > 1:
            issues.append("pool_utilization_threshold must be between 0 and 1")
        
        # Validate export settings
        if self.enable_metrics_export:
            if self.export_format not in ('json', 'csv', 'prometheus'):
                issues.append(f"Invalid export_format: {self.export_format}")
        
        # Validate auto-tuning settings
        if self.enable_auto_tuning:
            if self.auto_tuning_confidence_threshold < 0 or self.auto_tuning_confidence_threshold > 1:
                issues.append("auto_tuning_confidence_threshold must be between 0 and 1")
        
        return issues
    
    def apply_profile(self, profile: str) -> None:
        """Apply a predefined configuration profile."""
        profiles = {
            'production': {
                'enabled': True,
                'enable_auto_tuning': True,
                'enable_alerts': True,
                'enable_metrics_export': True,
                'metrics_collection_interval': 30.0,
                'memory_sampling_interval': 60.0,
                'enable_tracemalloc': False,
                'debug_mode': False,
            },
            'development': {
                'enabled': True,
                'enable_auto_tuning': False,
                'enable_alerts': True,
                'enable_metrics_export': False,
                'metrics_collection_interval': 5.0,
                'memory_sampling_interval': 10.0,
                'enable_tracemalloc': True,
                'debug_mode': True,
            },
            'testing': {
                'enabled': True,
                'enable_auto_tuning': False,
                'enable_alerts': False,
                'enable_metrics_export': False,
                'metrics_collection_interval': 1.0,
                'memory_sampling_interval': 5.0,
                'enable_tracemalloc': False,
                'debug_mode': False,
            },
            'minimal': {
                'enabled': False,
                'enable_auto_tuning': False,
                'enable_alerts': False,
                'enable_metrics_export': False,
            }
        }
        
        if profile not in profiles:
            logger.warning(f"Unknown profile: {profile}")
            return
        
        profile_settings = profiles[profile]
        for key, value in profile_settings.items():
            setattr(self, key, value)
        
        logger.info(f"Applied monitoring profile: {profile}")


class ConfigManager:
    """Global configuration management."""
    
    def __init__(self):
        self._config: Optional[MonitoringConfig] = None
        self._config_path: Optional[str] = None
        
    def load_config(self, config_path: Optional[str] = None) -> MonitoringConfig:
        """Load configuration from file or environment."""
        if config_path:
            self._config = MonitoringConfig.from_file(config_path)
            self._config_path = config_path
        else:
            # Try environment first, then defaults
            self._config = MonitoringConfig.from_env()
        
        # Validate configuration
        issues = self._config.validate()
        if issues:
            logger.warning(f"Configuration validation issues: {issues}")
        
        return self._config
    
    def get_config(self) -> MonitoringConfig:
        """Get current configuration."""
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration values."""
        config = self.get_config()
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                logger.warning(f"Unknown configuration key: {key}")
        
        # Re-validate after updates
        issues = config.validate()
        if issues:
            logger.warning(f"Configuration validation issues after update: {issues}")
    
    def save_config(self, config_path: Optional[str] = None) -> None:
        """Save current configuration."""
        if config_path is None:
            config_path = self._config_path
        
        if config_path is None:
            logger.error("No config path specified for saving")
            return
        
        config = self.get_config()
        config.save(config_path)
    
    def apply_profile(self, profile: str) -> None:
        """Apply a configuration profile."""
        config = self.get_config()
        config.apply_profile(profile)


# Global configuration instance
_global_config_manager = ConfigManager()


def get_monitoring_config() -> MonitoringConfig:
    """Get global monitoring configuration."""
    return _global_config_manager.get_config()


def update_monitoring_config(**kwargs) -> None:
    """Update global monitoring configuration."""
    _global_config_manager.update_config(**kwargs)


def load_monitoring_config(config_path: Optional[str] = None) -> MonitoringConfig:
    """Load monitoring configuration."""
    return _global_config_manager.load_config(config_path)


def apply_monitoring_profile(profile: str) -> None:
    """Apply a monitoring configuration profile."""
    _global_config_manager.apply_profile(profile)