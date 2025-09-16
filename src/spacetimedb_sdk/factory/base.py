"""
Abstract base classes for the SpacetimeDB client factory pattern using dependency injection.

This module defines the enhanced interfaces and base implementations for
creating SpacetimeDB clients with circular import resolution.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING
import logging
from ..utils.error_formatting import ErrorFormatter
from enum import Enum

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from ..spacetimedb_client import SpacetimeDBClient
    from ..connection_builder import SpacetimeDBConnectionBuilder

from ..interfaces.client_interface import SpacetimeDBClientInterface
from ..interfaces.factory_interface import SpacetimeDBClientFactoryInterface
from ..protocol import TEXT_PROTOCOL, BIN_PROTOCOL
from ..compression import CompressionType
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
    Concrete implementation of SpacetimeDB client factory using dependency injection.
    
    This factory uses lazy imports to avoid circular dependencies while maintaining
    full compatibility with existing code.
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
        Create a SpacetimeDB client instance using dependency injection.
        
        Args:
            host: Server host (e.g., "localhost:3000")
            database: Database identity/name
            server_language: Server implementation language
            protocol: SpacetimeDB protocol version
            auto_reconnect: Whether to enable automatic reconnection
            **kwargs: Additional configuration options
            
        Returns:
            SpacetimeDB client instance
            
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
        Get recommended configuration for the optimization profile.
        
        Args:
            optimization_profile: Performance optimization profile
            
        Returns:
            Dictionary containing recommended configuration
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


# Keep the old class name for compatibility
SpacetimeDBClientFactoryBase = SpacetimeDBClientFactory