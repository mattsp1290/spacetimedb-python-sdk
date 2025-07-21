"""
Protocol handler for version-specific serialization and message formatting.

This module provides ProtocolHandler class that manages different protocol
versions and ensures proper message formatting based on the protocol version.
"""

from typing import Any, Dict, List, Union, Optional
import logging
from enum import Enum
import time  # Security fix: Static import to replace dynamic __import__('time')

from .serialization import serialize_for_client, prepare_message_for_client, ensure_dict_compatible

logger = logging.getLogger(__name__)


class ProtocolVersion(Enum):
    """Supported SpacetimeDB protocol versions."""
    V1_JSON = "v1.json.spacetimedb"
    V1_BSATN = "v1.bsatn.spacetimedb"
    V1_1_JSON = "v1.1.json.spacetimedb"
    V1_1_BSATN = "v1.1.bsatn.spacetimedb"
    V1_1_2_JSON = "v1.1.2.json.spacetimedb"
    V1_1_2_BSATN = "v1.1.2.bsatn.spacetimedb"


class SerializationMode(Enum):
    """Serialization modes for different use cases."""
    CLIENT_COMPATIBLE = "client_compatible"  # Ensure dictionary-like behavior
    PROTOCOL_NATIVE = "protocol_native"      # Use native protocol objects
    HYBRID = "hybrid"                        # Mix of both based on context


class ProtocolHandler:
    """
    Handler for protocol-specific message formatting and serialization.
    
    This class manages different protocol versions and ensures that messages
    are properly formatted for client consumption while maintaining protocol
    compatibility.
    """
    
    def __init__(self, 
                 version: Union[str, ProtocolVersion] = ProtocolVersion.V1_JSON,
                 serialization_mode: SerializationMode = SerializationMode.CLIENT_COMPATIBLE):
        """
        Initialize protocol handler.
        
        Args:
            version: Protocol version to use
            serialization_mode: How to serialize objects for clients
        """
        if isinstance(version, str):
            # Try to match string to enum
            version_map = {
                "v1.json.spacetimedb": ProtocolVersion.V1_JSON,
                "v1.bsatn.spacetimedb": ProtocolVersion.V1_BSATN,
                "v1.1.json.spacetimedb": ProtocolVersion.V1_1_JSON,
                "v1.1.bsatn.spacetimedb": ProtocolVersion.V1_1_BSATN,
                "v1.1.2.json.spacetimedb": ProtocolVersion.V1_1_2_JSON,
                "v1.1.2.bsatn.spacetimedb": ProtocolVersion.V1_1_2_BSATN,
            }
            self.version = version_map.get(version, ProtocolVersion.V1_JSON)
        else:
            self.version = version
        
        self.serialization_mode = serialization_mode
        self.is_binary = "bsatn" in self.version.value
        self.is_json = "json" in self.version.value
        
        logger.info(f"Protocol handler initialized: {self.version.value}, mode: {serialization_mode.value}")
    
    def format_message(self, message_data: Any) -> Any:
        """
        Format message based on protocol version and serialization mode.
        
        Args:
            message_data: Raw message data to format
            
        Returns:
            Formatted message data
        """
        if self.serialization_mode == SerializationMode.CLIENT_COMPATIBLE:
            return self._ensure_dict_compatible(message_data)
        elif self.serialization_mode == SerializationMode.PROTOCOL_NATIVE:
            return message_data  # Return as-is
        else:  # HYBRID
            return self._hybrid_format(message_data)
    
    def _ensure_dict_compatible(self, data: Any) -> Any:
        """
        Ensure all objects in data support dictionary operations.
        
        Args:
            data: Data to process
            
        Returns:
            Data with dictionary-compatible objects
        """
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if hasattr(value, 'get') and hasattr(value, '__getitem__'):
                    # Already dict-like
                    result[key] = value
                elif hasattr(value, '__dataclass_fields__') or hasattr(value, '__dict__'):
                    # Object that needs conversion
                    result[key] = serialize_for_client(value)
                else:
                    # Primitive or already compatible
                    result[key] = self._ensure_dict_compatible(value)
            return result
        elif isinstance(data, list):
            return [self._ensure_dict_compatible(item) for item in data]
        elif hasattr(data, '__dataclass_fields__') or (hasattr(data, '__dict__') and not isinstance(data, (str, int, float, bool, bytes))):
            return serialize_for_client(data)
        else:
            return data
    
    def _hybrid_format(self, data: Any) -> Any:
        """
        Apply hybrid formatting based on data type and protocol version.
        
        Args:
            data: Data to format
            
        Returns:
            Formatted data
        """
        # For v1.1.2, use more aggressive client compatibility
        if "v1.1.2" in self.version.value:
            return self._ensure_dict_compatible(data)
        else:
            # For older versions, be more conservative
            return ensure_dict_compatible(data)
    
    def prepare_server_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a server message for client consumption.
        
        Args:
            message_data: Raw server message data
            
        Returns:
            Client-ready message data
        """
        # Apply version-specific transformations
        if self.version in (ProtocolVersion.V1_1_2_JSON, ProtocolVersion.V1_1_2_BSATN):
            # Latest version needs comprehensive serialization
            return prepare_message_for_client(message_data)
        else:
            # Older versions might need lighter touch
            return self.format_message(message_data)
    
    def prepare_client_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a client message for server transmission.
        
        Args:
            message_data: Client message data
            
        Returns:
            Server-ready message data
        """
        # Client messages typically don't need as much processing
        # but we may need to ensure proper encoding
        if self.is_binary:
            # For BSATN, ensure all objects are properly encoded
            return self._prepare_for_binary_encoding(message_data)
        else:
            # For JSON, ensure JSON-serializable
            return self._prepare_for_json_encoding(message_data)
    
    def _prepare_for_binary_encoding(self, data: Any) -> Any:
        """
        Prepare data for binary (BSATN) encoding.
        
        Args:
            data: Data to prepare
            
        Returns:
            Binary-encoding-ready data
        """
        # For BSATN, we typically want the native objects
        return data
    
    def _prepare_for_json_encoding(self, data: Any) -> Any:
        """
        Prepare data for JSON encoding.
        
        Args:
            data: Data to prepare
            
        Returns:
            JSON-encoding-ready data
        """
        import json
        
        def make_json_serializable(obj):
            """Make an object JSON-serializable."""
            if isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_serializable(item) for item in obj]
            elif isinstance(obj, bytes):
                # Convert bytes to list for JSON
                return list(obj)
            elif hasattr(obj, '__dataclass_fields__'):
                # Serialize dataclass
                return serialize_for_client(obj)
            elif hasattr(obj, 'to_dict'):
                return obj.to_dict()
            else:
                # Check if it's JSON-serializable
                try:
                    json.dumps(obj)
                    return obj
                except (TypeError, ValueError):
                    # Convert to string as fallback
                    return str(obj)
        
        return make_json_serializable(data)
    
    def get_protocol_info(self) -> Dict[str, Any]:
        """
        Get information about the current protocol configuration.
        
        Returns:
            Protocol information dictionary
        """
        return {
            "version": self.version.value,
            "serialization_mode": self.serialization_mode.value,
            "is_binary": self.is_binary,
            "is_json": self.is_json,
            "supports_dict_compatibility": self.serialization_mode != SerializationMode.PROTOCOL_NATIVE
        }
    
    def validate_message_compatibility(self, message_data: Any) -> bool:
        """
        Validate that a message is compatible with the current protocol.
        
        Args:
            message_data: Message data to validate
            
        Returns:
            True if compatible, False otherwise
        """
        try:
            formatted = self.format_message(message_data)
            
            # Check that formatted message has expected properties
            if self.serialization_mode == SerializationMode.CLIENT_COMPATIBLE:
                # Should support dictionary operations
                if isinstance(formatted, dict):
                    return True
                elif hasattr(formatted, 'get') and hasattr(formatted, '__getitem__'):
                    return True
                else:
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Message compatibility validation failed: {e}")
            return False
    
    def create_error_response(self, error_message: str, request_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Create a standardized error response.
        
        Args:
            error_message: Error message text
            request_id: Optional request ID
            
        Returns:
            Formatted error response
        """
        error_response = {
            "error": error_message,
            "protocol_version": self.version.value,
            "timestamp": time.time()  # Security fix: Using static import instead of dynamic __import__
        }
        
        if request_id is not None:
            error_response["request_id"] = request_id
        
        return self.format_message(error_response)


class ProtocolHandlerFactory:
    """Factory for creating protocol handlers."""
    
    @staticmethod
    def create_handler(version: str, 
                      compatibility_mode: bool = True) -> ProtocolHandler:
        """
        Create a protocol handler for the specified version.
        
        Args:
            version: Protocol version string
            compatibility_mode: Whether to enable client compatibility
            
        Returns:
            Configured ProtocolHandler instance
        """
        serialization_mode = (
            SerializationMode.CLIENT_COMPATIBLE if compatibility_mode 
            else SerializationMode.PROTOCOL_NATIVE
        )
        
        return ProtocolHandler(version=version, serialization_mode=serialization_mode)
    
    @staticmethod
    def create_v1_1_2_handler(compatibility_mode: bool = True) -> ProtocolHandler:
        """Create handler for v1.1.2 protocol."""
        return ProtocolHandlerFactory.create_handler("v1.1.2.json.spacetimedb", compatibility_mode)
    
    @staticmethod
    def create_legacy_handler(compatibility_mode: bool = True) -> ProtocolHandler:
        """Create handler for legacy v1 protocol."""
        return ProtocolHandlerFactory.create_handler("v1.json.spacetimedb", compatibility_mode)


# Global default handler
default_protocol_handler = ProtocolHandler()


def get_default_handler() -> ProtocolHandler:
    """Get the default protocol handler."""
    return default_protocol_handler


def set_default_handler(handler: ProtocolHandler) -> None:
    """Set the default protocol handler."""
    global default_protocol_handler
    default_protocol_handler = handler


def format_for_client(message_data: Any, version: Optional[str] = None) -> Any:
    """
    Convenience function to format message data for client compatibility.
    
    Args:
        message_data: Data to format
        version: Optional protocol version (uses default if not specified)
        
    Returns:
        Client-compatible formatted data
    """
    if version:
        handler = ProtocolHandlerFactory.create_handler(version, compatibility_mode=True)
    else:
        handler = get_default_handler()
    
    return handler.format_message(message_data)