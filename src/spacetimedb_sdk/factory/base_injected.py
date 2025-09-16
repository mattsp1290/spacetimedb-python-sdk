"""
Abstract base classes for the SpacetimeDB client factory pattern using dependency injection.

This module defines factory interfaces that use dependency injection to break circular imports.
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


class SpacetimeDBClientFactoryBase(SpacetimeDBClientFactoryInterface):
    """
    Base implementation of SpacetimeDB client factory using dependency injection.
    
    This factory uses lazy imports and dependency injection to avoid circular imports
    while maintaining full compatibility with existing code.
    """
    
    def __init__(self):
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
        **kwargs
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
        """
        ClientClass = self._get_client_class()
        
        # Create client with injected dependencies
        client = ClientClass(
            host=host,
            database=database,
            server_language=server_language,
            protocol=protocol,
            auto_reconnect=auto_reconnect,
            **kwargs
        )
        
        return client
    
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


class DependencyInjectedFactory(SpacetimeDBClientFactoryBase):
    """
    Factory implementation that uses dependency injection container.
    
    This factory can be registered in the DI container and used throughout
    the application without creating circular dependencies.
    """
    
    def __init__(self, container=None):
        super().__init__()
        self._container = container
    
    def set_container(self, container):
        """Set the dependency injection container."""
        self._container = container
    
    def create_client(
        self,
        host: str,
        database: str,
        server_language: str = "rust",
        protocol: str = "v1.json.spacetimedb",
        auto_reconnect: bool = True,
        **kwargs
    ) -> SpacetimeDBClientInterface:
        """Create client using DI container if available."""
        if self._container and self._container.has("spacetimedb_client_class"):
            ClientClass = self._container.get("spacetimedb_client_class")
        else:
            # Fallback to lazy import
            ClientClass = self._get_client_class()
        
        return ClientClass(
            host=host,
            database=database,
            server_language=server_language,
            protocol=protocol,
            auto_reconnect=auto_reconnect,
            **kwargs
        )