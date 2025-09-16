"""
Factory Interface for Dependency Injection

This interface breaks the circular dependency by providing abstract factory methods
that can be implemented without importing concrete client classes.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Protocol, runtime_checkable
from .client_interface import SpacetimeDBClientInterface


@runtime_checkable
class ClientFactory(Protocol):
    """Protocol for creating SpacetimeDB client instances."""
    
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
        Create a SpacetimeDB client instance.
        
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
        ...


class SpacetimeDBClientFactoryInterface(ABC):
    """
    Abstract base class for SpacetimeDB client factories.
    
    This factory interface provides a way to create client instances without
    directly importing the concrete SpacetimeDBClient class, breaking circular dependencies.
    """

    @abstractmethod
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
        Create a SpacetimeDB client instance.
        
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
        pass

    @abstractmethod
    def get_supported_languages(self) -> list[str]:
        """
        Get list of supported server languages.
        
        Returns:
            List of supported server language identifiers
        """
        pass

    @abstractmethod
    def get_supported_protocols(self) -> list[str]:
        """
        Get list of supported protocols.
        
        Returns:
            List of supported protocol identifiers
        """
        pass

    @abstractmethod
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
        pass


class ConnectionFactoryInterface(ABC):
    """Interface for creating connection-related components."""
    
    @abstractmethod
    def create_websocket_client(self, **kwargs) -> Any:
        """Create a WebSocket client instance."""
        pass
    
    @abstractmethod 
    def create_auth_manager(self, **kwargs) -> Any:
        """Create an authentication manager instance."""
        pass
    
    @abstractmethod
    def create_subscription_manager(self, **kwargs) -> Any:
        """Create a subscription manager instance."""
        pass


class DependencyInjectionContainer:
    """
    Simple dependency injection container for breaking circular dependencies.
    
    This container allows late binding of dependencies, solving the circular import problem.
    """
    
    def __init__(self):
        self._factories: Dict[str, Any] = {}
        self._instances: Dict[str, Any] = {}
    
    def register_factory(self, name: str, factory: Any) -> None:
        """Register a factory for a service."""
        self._factories[name] = factory
    
    def register_instance(self, name: str, instance: Any) -> None:
        """Register a singleton instance."""
        self._instances[name] = instance
    
    def get(self, name: str, **kwargs) -> Any:
        """Get a service instance."""
        if name in self._instances:
            return self._instances[name]
        
        if name in self._factories:
            return self._factories[name](**kwargs)
        
        raise ValueError(f"No factory or instance registered for '{name}'")
    
    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._factories or name in self._instances


# Global dependency injection container
_container = DependencyInjectionContainer()


def get_container() -> DependencyInjectionContainer:
    """Get the global dependency injection container."""
    return _container


def register_client_factory(factory: SpacetimeDBClientFactoryInterface) -> None:
    """Register the client factory in the global container."""
    _container.register_instance("client_factory", factory)


def get_client_factory() -> Optional[SpacetimeDBClientFactoryInterface]:
    """Get the registered client factory."""
    try:
        return _container.get("client_factory")
    except ValueError:
        return None