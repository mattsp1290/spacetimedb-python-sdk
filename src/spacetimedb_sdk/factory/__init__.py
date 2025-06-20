"""
Enhanced Factory Pattern for SpacetimeDB SDK.

This module provides a factory pattern implementation that enables dynamic
instantiation of SpacetimeDB clients optimized for different server languages.
The factory pattern abstracts away server language differences while providing
optimized configurations for each implementation.

Key components:
- SpacetimeDBClientFactory: Enhanced factory for creating optimized clients
- Language-specific factories: Specialized configurations for each server language  
- FactoryRegistry: Registry for managing available factories
- create_client: High-level function for creating clients based on configuration
"""

from .base import SpacetimeDBClientFactory, SpacetimeDBClientFactoryBase
from .registry import SpacetimeDBFactoryRegistry
from .rust_factory import RustOptimizedFactory
from .python_factory import PythonOptimizedFactory
from .csharp_factory import CSharpOptimizedFactory
from .go_factory import GoOptimizedFactory
from .client_factory import (
    create_spacetimedb_client,
    get_spacetimedb_factory,
    list_supported_languages,
    get_language_info,
    create_optimized_client,
    # Convenience functions for each language
    create_rust_client,
    create_python_client,
    create_csharp_client,
    create_go_client,
    # Additional utilities
    get_recommended_config,
    validate_server_compatibility,
    get_optimization_capabilities
)

__all__ = [
    "SpacetimeDBClientFactory",
    "SpacetimeDBClientFactoryBase", 
    "SpacetimeDBFactoryRegistry",
    "RustOptimizedFactory",
    "PythonOptimizedFactory", 
    "CSharpOptimizedFactory",
    "GoOptimizedFactory",
    "create_spacetimedb_client",
    "get_spacetimedb_factory",
    "list_supported_languages", 
    "get_language_info",
    "create_optimized_client",
    # Convenience functions for each language
    "create_rust_client",
    "create_python_client",
    "create_csharp_client",
    "create_go_client",
    # Additional utilities
    "get_recommended_config",
    "validate_server_compatibility",
    "get_optimization_capabilities",
]