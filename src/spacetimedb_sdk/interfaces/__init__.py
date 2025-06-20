"""
Modern SpacetimeDB Python SDK Interfaces

This module provides abstract base classes and interfaces that create a unified API
for SpacetimeDB clients across different server languages and deployment configurations.

These interfaces combine the best patterns from the blackholio-python-client with
the production-ready features of the spacetimedb-python-sdk.
"""

from .connection_interface import ConnectionInterface, ConnectionState
from .auth_interface import AuthInterface
from .subscription_interface import SubscriptionInterface
from .reducer_interface import ReducerInterface
from .client_interface import SpacetimeDBClientInterface

__all__ = [
    'ConnectionInterface',
    'ConnectionState',
    'AuthInterface',
    'SubscriptionInterface', 
    'ReducerInterface',
    'SpacetimeDBClientInterface'
]