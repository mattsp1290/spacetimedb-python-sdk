"""
SpacetimeDB Protocol Handling Module

This module contains focused protocol handling components for SpacetimeDB message
encoding, decoding, and processing. This separation ensures clean architecture
and better testability.
"""

from .protocol_handler import (
    ProtocolHandler,
    MessageMetrics,
    ProcessedMessage,
    ProtocolConfiguration,
    ProtocolError,
    MessageValidationError,
    ProtocolSecurityError
)

__all__ = [
    'ProtocolHandler',
    'MessageMetrics', 
    'ProcessedMessage',
    'ProtocolConfiguration',
    'ProtocolError',
    'MessageValidationError',
    'ProtocolSecurityError'
]