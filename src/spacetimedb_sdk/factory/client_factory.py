"""
High-level client factory functions for SpacetimeDB SDK.

This module provides the main entry points for creating SpacetimeDB
clients using the enhanced factory pattern. It handles factory registration,
selection based on server language, and provides convenient functions
for client creation.
"""

from typing import Any, Dict, Optional, Union
import logging
from ..utils.error_formatting import ErrorFormatter

from .registry import registry, SpacetimeDBFactoryRegistry
from .base import SpacetimeDBClientFactory, ServerLanguage, OptimizationProfile
from .rust_factory import RustOptimizedFactory
from .python_factory import PythonOptimizedFactory
from .csharp_factory import CSharpOptimizedFactory
from .go_factory import GoOptimizedFactory
from ..spacetimedb_client import SpacetimeDBClient
from ..exceptions import (
    SpacetimeDBConnectionError,
    SpacetimeDBError,
)

logger = logging.getLogger(__name__)

# Register all factory implementations
def _register_factories():
    """Register all available factory implementations."""
    registry.register(ServerLanguage.RUST, RustOptimizedFactory)
    registry.register(ServerLanguage.PYTHON, PythonOptimizedFactory)
    registry.register(ServerLanguage.CSHARP, CSharpOptimizedFactory)
    registry.register(ServerLanguage.GO, GoOptimizedFactory)
    logger.debug("Registered all SpacetimeDB client factories")

# Auto-register on module import
_register_factories()


def get_spacetimedb_factory(
    language: Union[str, ServerLanguage],
    **kwargs: Any
) -> SpacetimeDBClientFactory:
    """
    Get a SpacetimeDB factory for the specified language.
    
    Args:
        language: Server language (string or enum)
        **kwargs: Additional arguments for factory initialization
        
    Returns:
        SpacetimeDBClientFactory: The appropriate factory instance
        
    Raises:
        SpacetimeDBConfigurationError: If language is not supported
        
    Example:
        # Get factory by string
        factory = get_spacetimedb_factory("rust")
        
        # Get factory by enum
        factory = get_spacetimedb_factory(ServerLanguage.PYTHON)
    """
    try:
        # Convert string to enum if needed
        if isinstance(language, str):
            lang_enum = ServerLanguage(language.lower())
        else:
            lang_enum = language
        
        logger.info(f"Getting SpacetimeDB factory for language: {lang_enum.value}")
        
        # Get factory from registry
        factory = registry.get_factory(lang_enum, cache=True, **kwargs)
        
        # Validate factory is available
        if not factory.is_available:
            raise SpacetimeDBError(
                f"Factory for {lang_enum.value} is registered but not available. "
                f"Check server installation and configuration."
            )
        
        return factory
        
    except ValueError as e:
        if "is not a valid ServerLanguage" in str(e):
            available = [lang.value for lang in ServerLanguage]
            raise SpacetimeDBError(
                f"Invalid language '{language}'. Available languages: {available}"
            )
        raise SpacetimeDBError(str(e))
    except Exception as e:
        logger.error(ErrorFormatter.format_generic_error("Factory", f"get factory for {language}", e))
        raise SpacetimeDBError(
            f"Cannot get factory for language '{language}': {str(e)}"
        )


def create_spacetimedb_client(
    host: str,
    database: str,
    server_language: Union[str, ServerLanguage] = ServerLanguage.RUST,
    auth_token: Optional[str] = None,
    optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED,
    factory: Optional[SpacetimeDBClientFactory] = None,
    **kwargs: Any
) -> SpacetimeDBClient:
    """
    Create a SpacetimeDB client optimized for the specified server language.
    
    This is the main entry point for creating SpacetimeDB clients with
    language-specific optimizations.
    
    Args:
        host: Server host (e.g., "localhost:3000")
        database: Database name/identity
        server_language: Server language (string or enum)
        auth_token: Optional authentication token
        optimization_profile: Performance optimization profile
        factory: Optional factory instance to use directly
        **kwargs: Additional configuration parameters
        
    Returns:
        SpacetimeDBClient: Optimized client instance
        
    Raises:
        SpacetimeDBConnectionError: If client creation fails
        SpacetimeDBConfigurationError: If configuration is invalid
        
    Example:
        # Create client for Rust server with performance optimization
        client = create_spacetimedb_client(
            host="localhost:3000",
            database="my_game",
            server_language="rust",
            optimization_profile=OptimizationProfile.PERFORMANCE
        )
        
        # Create client with authentication
        client = create_spacetimedb_client(
            host="production.example.com:443",
            database="production_db",
            server_language=ServerLanguage.PYTHON,
            auth_token="your_token_here",
            optimization_profile=OptimizationProfile.RELIABILITY
        )
    """
    try:
        # Use provided factory or get one based on language
        if factory is None:
            factory = get_spacetimedb_factory(server_language)
        
        logger.info(
            f"Creating SpacetimeDB client using {factory.server_language.value} "
            f"factory with {optimization_profile.value} profile"
        )
        
        # Create client using factory
        client = factory.create_client(
            host=host,
            database=database,
            auth_token=auth_token,
            optimization_profile=optimization_profile,
            **kwargs
        )
        
        logger.info("Successfully created optimized SpacetimeDB client")
        return client
        
    except (SpacetimeDBConnectionError, SpacetimeDBError):
        # Re-raise our exceptions
        raise
    except Exception as e:
        logger.error(ErrorFormatter.format_generic_error("Factory", "create SpacetimeDB client", e))
        raise SpacetimeDBConnectionError(
            f"Cannot create SpacetimeDB client: {str(e)}"
        )


def create_optimized_client(
    host: str,
    database: str,
    server_language: Union[str, ServerLanguage],
    optimization_profile: OptimizationProfile,
    auth_token: Optional[str] = None,
    **kwargs: Any
) -> SpacetimeDBClient:
    """
    Create a client with specific optimization profile.
    
    Convenience function that emphasizes the optimization aspect.
    
    Args:
        host: Server host
        database: Database name
        server_language: Server language
        optimization_profile: Specific optimization profile
        auth_token: Optional authentication token
        **kwargs: Additional configuration
        
    Returns:
        SpacetimeDBClient: Optimized client
    """
    return create_spacetimedb_client(
        host=host,
        database=database,
        server_language=server_language,
        auth_token=auth_token,
        optimization_profile=optimization_profile,
        **kwargs
    )


def list_supported_languages() -> list[str]:
    """
    List all supported server languages.
    
    Returns languages that have registered factories and are available.
    
    Returns:
        list[str]: List of supported language names
        
    Example:
        languages = list_supported_languages()
        print(f"Supported languages: {languages}")
        # Output: Supported languages: ['rust', 'python', 'csharp', 'go']
    """
    available_factories = registry.get_available_factories()
    return sorted(available_factories.keys())


def get_language_info() -> Dict[str, Dict[str, Any]]:
    """
    Get detailed information about all supported languages.
    
    Returns:
        Dict[str, Dict[str, Any]]: Language information by name
        
    Example:
        info = get_language_info()
        for lang, details in info.items():
            print(f"{lang}: available={details['available']}")
    """
    return registry.get_factory_info()


def get_recommended_config(
    server_language: Union[str, ServerLanguage],
    optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED
) -> Dict[str, Any]:
    """
    Get recommended configuration for a server language and optimization profile.
    
    Args:
        server_language: Server language
        optimization_profile: Optimization profile
        
    Returns:
        Dict[str, Any]: Recommended configuration parameters
        
    Example:
        config = get_recommended_config("rust", OptimizationProfile.PERFORMANCE)
        print(f"Recommended energy budget: {config['energy_budget']}")
    """
    factory = get_spacetimedb_factory(server_language)
    return factory.get_recommended_config(optimization_profile)


def validate_server_compatibility(
    server_language: Union[str, ServerLanguage],
    server_version: Optional[str] = None
) -> bool:
    """
    Validate compatibility with a specific server.
    
    Args:
        server_language: Server language to check
        server_version: Optional server version
        
    Returns:
        bool: True if compatible, False otherwise
        
    Example:
        if validate_server_compatibility("rust", "1.0.0"):
            print("Server is compatible!")
    """
    try:
        factory = get_spacetimedb_factory(server_language)
        return factory.validate_compatibility(server_version)
    except Exception as e:
        logger.error(ErrorFormatter.format_generic_error("Factory", "compatibility validation", e))
        return False


def get_optimization_capabilities(
    server_language: Union[str, ServerLanguage]
) -> Dict[str, bool]:
    """
    Get optimization capabilities for a server language.
    
    Args:
        server_language: Server language to check
        
    Returns:
        Dict[str, bool]: Map of optimization features to availability
        
    Example:
        capabilities = get_optimization_capabilities("rust")
        if capabilities["high_concurrency"]:
            print("Rust server supports high concurrency!")
    """
    factory = get_spacetimedb_factory(server_language)
    return factory.optimization_capabilities


# Convenience functions for each language
def create_rust_client(
    host: str,
    database: str,
    auth_token: Optional[str] = None,
    optimization_profile: OptimizationProfile = OptimizationProfile.PERFORMANCE,
    **kwargs: Any
) -> SpacetimeDBClient:
    """Create a client optimized for Rust servers."""
    return create_spacetimedb_client(
        host=host,
        database=database,
        server_language=ServerLanguage.RUST,
        auth_token=auth_token,
        optimization_profile=optimization_profile,
        **kwargs
    )


def create_python_client(
    host: str,
    database: str,
    auth_token: Optional[str] = None,
    optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED,
    **kwargs: Any
) -> SpacetimeDBClient:
    """Create a client optimized for Python servers."""
    return create_spacetimedb_client(
        host=host,
        database=database,
        server_language=ServerLanguage.PYTHON,
        auth_token=auth_token,
        optimization_profile=optimization_profile,
        **kwargs
    )


def create_csharp_client(
    host: str,
    database: str,
    auth_token: Optional[str] = None,
    optimization_profile: OptimizationProfile = OptimizationProfile.BALANCED,
    **kwargs: Any
) -> SpacetimeDBClient:
    """Create a client optimized for C# servers."""
    return create_spacetimedb_client(
        host=host,
        database=database,
        server_language=ServerLanguage.CSHARP,
        auth_token=auth_token,
        optimization_profile=optimization_profile,
        **kwargs
    )


def create_go_client(
    host: str,
    database: str,
    auth_token: Optional[str] = None,
    optimization_profile: OptimizationProfile = OptimizationProfile.PERFORMANCE,
    **kwargs: Any
) -> SpacetimeDBClient:
    """Create a client optimized for Go servers."""
    return create_spacetimedb_client(
        host=host,
        database=database,
        server_language=ServerLanguage.GO,
        auth_token=auth_token,
        optimization_profile=optimization_profile,
        **kwargs
    )