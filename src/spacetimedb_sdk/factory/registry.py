"""
Factory Registry for SpacetimeDB SDK.

This module provides a registry system for managing SpacetimeDB client factories.
It enables dynamic factory registration and retrieval based on server language.
"""

from typing import Dict, Type, Optional, Any
import logging
from threading import Lock

from .base import SpacetimeDBClientFactory, ServerLanguage

logger = logging.getLogger(__name__)


class SpacetimeDBFactoryRegistry:
    """
    Registry for managing SpacetimeDB client factories.
    
    This registry provides thread-safe registration and retrieval of
    factory implementations for different server languages.
    """
    
    def __init__(self):
        """Initialize the registry."""
        self._factories: Dict[ServerLanguage, Type[SpacetimeDBClientFactory]] = {}
        self._instances: Dict[ServerLanguage, SpacetimeDBClientFactory] = {}
        self._lock = Lock()
    
    def register(
        self,
        language: ServerLanguage,
        factory_class: Type[SpacetimeDBClientFactory]
    ) -> None:
        """
        Register a factory class for a server language.
        
        Args:
            language: Server language enum
            factory_class: Factory class to register
            
        Raises:
            ValueError: If language is already registered
        """
        with self._lock:
            if language in self._factories:
                logger.warning(
                    f"Overriding existing factory for {language.value}"
                )
            
            self._factories[language] = factory_class
            # Clear cached instance if it exists
            if language in self._instances:
                del self._instances[language]
            
            logger.info(f"Registered factory for {language.value}: {factory_class.__name__}")
    
    def unregister(self, language: ServerLanguage) -> bool:
        """
        Unregister a factory for a server language.
        
        Args:
            language: Server language to unregister
            
        Returns:
            bool: True if factory was unregistered, False if not found
        """
        with self._lock:
            removed_factory = self._factories.pop(language, None)
            removed_instance = self._instances.pop(language, None)
            
            if removed_factory:
                logger.info(f"Unregistered factory for {language.value}")
                return True
            return False
    
    def get_factory(
        self,
        language: ServerLanguage,
        cache: bool = True,
        **kwargs: Any
    ) -> SpacetimeDBClientFactory:
        """
        Get a factory instance for a server language.
        
        Args:
            language: Server language
            cache: Whether to cache factory instances
            **kwargs: Additional arguments for factory initialization
            
        Returns:
            SpacetimeDBClientFactory: Factory instance
            
        Raises:
            ValueError: If language is not registered
        """
        with self._lock:
            # Check if language is registered
            if language not in self._factories:
                available = [lang.value for lang in self._factories.keys()]
                raise ValueError(
                    f"No factory registered for {language.value}. "
                    f"Available languages: {available}"
                )
            
            # Return cached instance if available and caching is enabled
            if cache and language in self._instances:
                return self._instances[language]
            
            # Create new instance
            factory_class = self._factories[language]
            try:
                factory = factory_class(**kwargs)
                
                # Cache the instance if caching is enabled
                if cache:
                    self._instances[language] = factory
                
                logger.debug(f"Created factory instance for {language.value}")
                return factory
                
            except Exception as e:
                logger.error(f"Failed to create factory for {language.value}: {e}")
                raise ValueError(
                    f"Cannot create factory for {language.value}: {str(e)}"
                )
    
    def get_factory_by_name(
        self,
        language_name: str,
        cache: bool = True,
        **kwargs: Any
    ) -> SpacetimeDBClientFactory:
        """
        Get a factory instance by language name string.
        
        Args:
            language_name: Server language name (e.g., "rust", "python")
            cache: Whether to cache factory instances
            **kwargs: Additional arguments for factory initialization
            
        Returns:
            SpacetimeDBClientFactory: Factory instance
            
        Raises:
            ValueError: If language name is not valid or registered
        """
        try:
            language = ServerLanguage(language_name.lower())
            return self.get_factory(language, cache=cache, **kwargs)
        except ValueError as e:
            if "is not a valid ServerLanguage" in str(e):
                available = [lang.value for lang in ServerLanguage]
                raise ValueError(
                    f"Invalid language name '{language_name}'. "
                    f"Valid languages: {available}"
                )
            raise
    
    def list_languages(self) -> list[ServerLanguage]:
        """
        Get list of registered languages.
        
        Returns:
            list[ServerLanguage]: List of registered server languages
        """
        with self._lock:
            return list(self._factories.keys())
    
    def list_language_names(self) -> list[str]:
        """
        Get list of registered language names.
        
        Returns:
            list[str]: List of registered language name strings
        """
        return [lang.value for lang in self.list_languages()]
    
    def get_available_factories(self) -> Dict[str, SpacetimeDBClientFactory]:
        """
        Get all available factory instances.
        
        Only returns factories that are actually available for use.
        
        Returns:
            Dict[str, SpacetimeDBClientFactory]: Map of language names to available factories
        """
        available = {}
        
        for language in self.list_languages():
            try:
                factory = self.get_factory(language, cache=True)
                if factory.is_available:
                    available[language.value] = factory
            except Exception as e:
                logger.debug(f"Factory for {language.value} is not available: {e}")
        
        return available
    
    def get_factory_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered factories.
        
        Returns:
            Dict[str, Dict[str, Any]]: Factory information by language name
        """
        info = {}
        
        for language in self.list_languages():
            try:
                factory = self.get_factory(language, cache=True)
                info[language.value] = {
                    "registered": True,
                    "available": factory.is_available,
                    "server_language": factory.server_language.value,
                    "supported_protocols": factory.supported_protocols,
                    "optimization_capabilities": factory.optimization_capabilities,
                    "class": factory.__class__.__name__,
                }
            except Exception as e:
                info[language.value] = {
                    "registered": True,
                    "available": False,
                    "error": str(e),
                }
        
        return info
    
    def clear_cache(self) -> None:
        """Clear all cached factory instances."""
        with self._lock:
            self._instances.clear()
            logger.info("Cleared factory instance cache")
    
    def is_registered(self, language: ServerLanguage) -> bool:
        """
        Check if a language is registered.
        
        Args:
            language: Server language to check
            
        Returns:
            bool: True if language is registered
        """
        return language in self._factories
    
    def is_available(self, language: ServerLanguage) -> bool:
        """
        Check if a language factory is available for use.
        
        Args:
            language: Server language to check
            
        Returns:
            bool: True if language factory is available
        """
        try:
            if not self.is_registered(language):
                return False
            
            factory = self.get_factory(language, cache=True)
            return factory.is_available
        except Exception:
            return False


# Global registry instance
registry = SpacetimeDBFactoryRegistry()