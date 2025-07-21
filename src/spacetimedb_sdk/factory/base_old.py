"""
Abstract base classes for the SpacetimeDB client factory pattern.

This module defines the enhanced interfaces and base implementations for
creating SpacetimeDB clients optimized for different server languages.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
import logging
from ..utils.error_formatting import ErrorFormatter
from enum import Enum

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..spacetimedb_client import SpacetimeDBClient
    from ..connection_builder import SpacetimeDBConnectionBuilder

from ..interfaces.client_interface import SpacetimeDBClientInterface
from ..interfaces.factory_interface import SpacetimeDBClientFactoryInterface
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


class SpacetimeDBClientFactory(SpacetimeDBClientFactoryInterface):
    """
    Abstract interface for SpacetimeDB client factories.
    
    This interface defines the contract for creating SpacetimeDB clients
    that are optimized for specific server languages while maintaining
    compatibility with the standard SpacetimeDB SDK.
    """
    
    def __init__(self):
        """Initialize factory with lazy loading setup."""
        self._client_class = None
        self._connection_builder_class = None
    
    def _get_client_class(self):
        """Lazy import of SpacetimeDBClient to avoid circular dependency."""
        if self._client_class is None:
            from ..spacetimedb_client import SpacetimeDBClient
            self._client_class = SpacetimeDBClient
        return self._client_class
    
    def _get_connection_builder_class(self):
        """Lazy import of SpacetimeDBConnectionBuilder to avoid circular dependency.""" 
        if self._connection_builder_class is None:
            from ..connection_builder import SpacetimeDBConnectionBuilder
            self._connection_builder_class = SpacetimeDBConnectionBuilder
        return self._connection_builder_class

    def create_client(
        self,
        host: str,
        database: str,
        server_language: str = "rust",
        protocol: str = "v1.json.spacetimedb",
        auto_reconnect: bool = True,
        **kwargs: Any
    ) -> SpacetimeDBClientInterface:
        """
        Create a SpacetimeDB client optimized for the specific server language.
        
        Args:
            host: Server host (e.g., "localhost:3000")
            database: Database name/identity
            server_language: Server implementation language
            protocol: SpacetimeDB protocol version
            auto_reconnect: Whether to enable automatic reconnection
            **kwargs: Additional configuration options
            
        Returns:
            SpacetimeDBClient: Configured client instance
            
        Raises:
            SpacetimeDBConnectionError: If client creation fails
        """
        ClientClass = self._get_client_class()
        
        try:
            return ClientClass(
                host=host,
                database=database,
                server_language=server_language,
                protocol=protocol,
                auto_reconnect=auto_reconnect,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create SpacetimeDB client: {e}")
            raise SpacetimeDBConnectionError(f"Client creation failed: {e}") from e
    
    def create_connection_builder(
        self,
        optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED,
        **kwargs
    ):
        """
        Create a connection builder with language-specific optimizations.
        
        Args:
            optimization_profile: Performance optimization profile
            **kwargs: Additional configuration options
            
        Returns:
            Pre-configured connection builder
        """
        BuilderClass = self._get_connection_builder_class()
        
        # Apply optimization profile
        config = self.get_recommended_config(optimization_profile)
        config.update(kwargs)
        
        return BuilderClass(**config)
    
    def get_supported_languages(self) -> list[str]:
        """Get list of supported server languages."""
        return [lang.value for lang in ServerLanguage]
    
    def get_supported_protocols(self) -> list[str]:
        """Get list of supported protocols."""
        return [TEXT_PROTOCOL, BIN_PROTOCOL]
    
    def validate_configuration(
        self, 
        host: str, 
        database: str, 
        server_language: str, 
        protocol: str
    ) -> bool:
        """
        Validate client configuration parameters.
        
        Args:
            host: Server host
            database: Database identity/name
            server_language: Server implementation language
            protocol: SpacetimeDB protocol version
            
        Returns:
            True if configuration is valid
        """
        # Basic validation
        if not host or not database:
            return False
        
        if server_language not in self.get_supported_languages():
            return False
        
        if protocol not in self.get_supported_protocols():
            return False
        
        return True

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
        base_config = {
            "auto_reconnect": True,
            "protocol": BIN_PROTOCOL,  # Default to binary for better performance
        }
        
        if optimization_profile == OptimizationProfile.PERFORMANCE:
            config = base_config.copy()
            config.update({
                "compression_type": CompressionType.BROTLI,
                "batch_size": 1000,
                "connection_timeout": 5.0,
                "query_timeout": 30.0,
                "enable_connection_pooling": True,
                "max_connections": 10,
            })
        elif optimization_profile == OptimizationProfile.RELIABILITY:
            config = base_config.copy()
            config.update({
                "compression_type": CompressionType.GZIP,
                "batch_size": 100,
                "connection_timeout": 30.0,
                "query_timeout": 60.0,
                "enable_connection_pooling": False,
                "retry_attempts": 5,
                "retry_delay": 2.0,
            })
        elif optimization_profile == OptimizationProfile.MINIMAL:
            config = base_config.copy()
            config.update({
                "compression_type": CompressionType.NONE,
                "batch_size": 50,
                "connection_timeout": 10.0,
                "query_timeout": 15.0,
                "enable_connection_pooling": False,
            })
        else:  # BALANCED
            config = base_config.copy()
            config.update({
                "compression_type": CompressionType.GZIP,
                "batch_size": 500,
                "connection_timeout": 15.0,
                "query_timeout": 30.0,
                "enable_connection_pooling": True,
                "max_connections": 5,
            })
        
        return config
    
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
        # Basic validation - can be overridden by subclasses
        return True
    
    @property
    def server_language(self) -> ServerLanguage:
        """
        Get the server language this factory supports.
        
        Returns:
            ServerLanguage: The server language
        """
        return ServerLanguage.RUST  # Default to Rust
    
    @property
    def supported_protocols(self) -> list[str]:
        """
        Get list of protocols supported by this server language.
        
        Returns:
            list[str]: List of supported protocol names
        """
        return [TEXT_PROTOCOL, BIN_PROTOCOL]
    
    @property
    def is_available(self) -> bool:
        """
        Check if this factory can create clients.
        
        Returns:
            bool: True if factory is available, False otherwise
        """
        return True
    
    @property
    def optimization_capabilities(self) -> Dict[str, bool]:
        """
        Get optimization capabilities for this server language.
        
        Returns:
            Dict[str, bool]: Map of optimization features to availability
        """
        return {
            "compression": True,
            "binary_protocol": True,
            "connection_pooling": True,
            "energy_management": True,
            "retry_policies": True,
        }


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
    ) -> SpacetimeDBClient:
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
            logger.error(ErrorFormatter.format_generic_error("Factory", "create client", e))
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
            logger.error(ErrorFormatter.format_generic_error("Factory", "create connection builder", e))
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
            logger.error(ErrorFormatter.format_generic_error("Factory", "compatibility validation", e))
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