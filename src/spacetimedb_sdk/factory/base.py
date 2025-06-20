"""
Abstract base classes for the SpacetimeDB client factory pattern.

This module defines the enhanced interfaces and base implementations for
creating SpacetimeDB clients optimized for different server languages.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
import logging
from enum import Enum

from ..modern_client import ModernSpacetimeDBClient
from ..connection_builder import SpacetimeDBConnectionBuilder
from ..protocol import TEXT_PROTOCOL, BIN_PROTOCOL
from ..compression import CompressionType
from ..energy import EnergyBudgetManager
from ..retry_policies import RetryPolicy
from ..exceptions import (
    SpacetimeDBConnectionError,
    SpacetimeDBError,
)

logger = logging.getLogger(__name__)


class ServerLanguage(Enum):
    """Supported SpacetimeDB server languages."""
    RUST = "rust"
    PYTHON = "python"
    CSHARP = "csharp"
    GO = "go"


class OptimizationProfile(Enum):
    """Client optimization profiles."""
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    BALANCED = "balanced"
    MINIMAL = "minimal"


class SpacetimeDBClientFactory(ABC):
    """
    Abstract interface for SpacetimeDB client factories.
    
    This interface defines the contract for creating SpacetimeDB clients
    that are optimized for specific server languages while maintaining
    compatibility with the standard SpacetimeDB SDK.
    """
    
    @abstractmethod
    def create_client(
        self,
        host: str,
        database: str,
        auth_token: Optional[str] = None,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED,
        **kwargs: Any
    ) -> ModernSpacetimeDBClient:
        """
        Create a SpacetimeDB client optimized for the specific server language.
        
        Args:
            host: Server host (e.g., "localhost:3000")
            database: Database name/identity
            auth_token: Optional authentication token
            optimization_profile: Performance optimization profile
            **kwargs: Additional configuration options
            
        Returns:
            ModernSpacetimeDBClient: Configured client instance
            
        Raises:
            SpacetimeDBConnectionError: If client creation fails
            SpacetimeDBConfigurationError: If configuration is invalid
        """
        pass
    
    @abstractmethod
    def create_connection_builder(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    ) -> SpacetimeDBConnectionBuilder:
        """
        Create a connection builder with language-specific optimizations.
        
        Args:
            optimization_profile: Performance optimization profile
            
        Returns:
            SpacetimeDBConnectionBuilder: Pre-configured builder
        """
        pass
    
    @abstractmethod
    def get_recommended_config(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    ) -> Dict[str, Any]:
        """
        Get recommended configuration for the server language.
        
        Args:
            optimization_profile: Performance optimization profile
            
        Returns:
            Dict[str, Any]: Recommended configuration parameters
        """
        pass
    
    @abstractmethod
    def validate_compatibility(
        self,
        server_version: Optional[str] = None
    ) -> bool:
        """
        Validate compatibility with the target server.
        
        Args:
            server_version: Optional server version to check against
            
        Returns:
            bool: True if compatible, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def server_language(self) -> ServerLanguage:
        """
        Get the server language this factory supports.
        
        Returns:
            ServerLanguage: The server language
        """
        pass
    
    @property
    @abstractmethod
    def supported_protocols(self) -> list[str]:
        """
        Get list of protocols supported by this server language.
        
        Returns:
            list[str]: List of supported protocol names
        """
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this factory can create clients.
        
        Returns:
            bool: True if factory is available, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def optimization_capabilities(self) -> Dict[str, bool]:
        """
        Get optimization capabilities for this server language.
        
        Returns:
            Dict[str, bool]: Map of optimization features to availability
        """
        pass


class SpacetimeDBClientFactoryBase(SpacetimeDBClientFactory):
    """
    Base implementation of the SpacetimeDBClientFactory with common functionality.
    
    This base class provides common implementation details that are shared
    across all concrete factory implementations.
    """
    
    def __init__(self):
        """Initialize the factory."""
        self._validated = False
        self._compatibility_checked = False
        
    def create_client(
        self,
        host: str,
        database: str,
        auth_token: Optional[str] = None,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED,
        **kwargs: Any
    ) -> ModernSpacetimeDBClient:
        """
        Create a SpacetimeDB client optimized for the specific server language.
        """
        try:
            # Get optimized configuration
            config = self.get_recommended_config(optimization_profile)
            
            # Create connection builder with optimizations
            builder = self.create_connection_builder(optimization_profile)
            
            # Configure the builder
            builder = builder.with_uri(f"ws://{host}")
            builder = builder.with_module_name(database)
            
            if auth_token:
                builder = builder.with_token(auth_token)
            
            # Apply language-specific configuration
            for key, value in config.items():
                if hasattr(builder, f"with_{key}"):
                    builder = getattr(builder, f"with_{key}")(value)
            
            # Apply any additional kwargs
            for key, value in kwargs.items():
                if hasattr(builder, f"with_{key}"):
                    builder = getattr(builder, f"with_{key}")(value)
            
            # Build and return the client
            client = builder.connect()
            
            logger.info(
                f"Successfully created {self.server_language.value} optimized client"
            )
            return client
            
        except Exception as e:
            logger.error(f"Failed to create client: {e}")
            raise SpacetimeDBConnectionError(
                f"Cannot create client for {self.server_language.value} server: {str(e)}"
            )
    
    def create_connection_builder(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
    ) -> SpacetimeDBConnectionBuilder:
        """
        Create a connection builder with language-specific optimizations.
        """
        try:
            # Get base configuration
            config = self.get_recommended_config(optimization_profile)
            
            # Create builder with recommended settings
            builder = SpacetimeDBConnectionBuilder()
            
            # Apply language-specific defaults
            if "protocol" in config:
                builder = builder.with_protocol(config["protocol"])
            
            if "compression" in config:
                builder = builder.with_compression(config["compression"])
            
            if "energy_budget" in config:
                builder = builder.with_energy_budget(config["energy_budget"])
            
            if "retry_policy" in config:
                builder = builder.with_retry_policy(config["retry_policy"])
            
            return builder
            
        except Exception as e:
            logger.error(f"Failed to create connection builder: {e}")
            raise SpacetimeDBError(
                f"Cannot create connection builder: {str(e)}"
            )
    
    def validate_compatibility(
        self,
        server_version: Optional[str] = None
    ) -> bool:
        """
        Validate compatibility with the target server.
        
        Base implementation performs basic validation.
        Subclasses can override for language-specific checks.
        """
        try:
            # Basic validation - check if factory is available
            if not self.is_available:
                logger.warning(f"Factory for {self.server_language.value} is not available")
                return False
            
            # TODO: Add server version compatibility checks
            # This would require server introspection capabilities
            
            self._compatibility_checked = True
            return True
            
        except Exception as e:
            logger.error(f"Compatibility validation failed: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        """
        Check if this factory can create clients.
        
        Base implementation checks basic requirements.
        """
        try:
            # Check if we can create a connection builder
            builder = SpacetimeDBConnectionBuilder()
            
            # Check if required protocols are supported
            supported = self.supported_protocols
            if not supported:
                return False
            
            # Check optimization capabilities
            capabilities = self.optimization_capabilities
            if not capabilities:
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Factory availability check failed: {e}")
            return False
    
    def _get_performance_config(self) -> Dict[str, Any]:
        """Get performance-optimized configuration."""
        return {
            "protocol": BIN_PROTOCOL,
            "compression": CompressionType.BROTLI,
            "energy_budget": 200000,  # Higher budget for performance
            "retry_policy": RetryPolicy(
                max_attempts=3,
                initial_delay=0.1,
                max_delay=1.0,
                exponential_base=1.5
            ),
            "connection_timeout": 10.0,
            "keep_alive": True,
            "buffer_size": 64 * 1024,  # 64KB buffer
        }
    
    def _get_reliability_config(self) -> Dict[str, Any]:
        """Get reliability-optimized configuration."""
        return {
            "protocol": TEXT_PROTOCOL,  # More reliable for debugging
            "compression": CompressionType.NONE,  # Avoid compression issues
            "energy_budget": 100000,  # Conservative budget
            "retry_policy": RetryPolicy(
                max_attempts=10,
                initial_delay=1.0,
                max_delay=30.0,
                exponential_base=2.0
            ),
            "connection_timeout": 30.0,
            "keep_alive": True,
            "heartbeat_interval": 10.0,
        }
    
    def _get_balanced_config(self) -> Dict[str, Any]:
        """Get balanced configuration."""
        return {
            "protocol": BIN_PROTOCOL,
            "compression": CompressionType.GZIP,
            "energy_budget": 150000,
            "retry_policy": RetryPolicy(
                max_attempts=5,
                initial_delay=0.5,
                max_delay=10.0,
                exponential_base=2.0
            ),
            "connection_timeout": 20.0,
            "keep_alive": True,
        }
    
    def _get_minimal_config(self) -> Dict[str, Any]:
        """Get minimal configuration."""
        return {
            "protocol": TEXT_PROTOCOL,
            "compression": CompressionType.NONE,
            "energy_budget": 50000,
            "retry_policy": RetryPolicy(
                max_attempts=2,
                initial_delay=1.0,
                max_delay=5.0,
                exponential_base=2.0
            ),
            "connection_timeout": 15.0,
            "keep_alive": False,
        }