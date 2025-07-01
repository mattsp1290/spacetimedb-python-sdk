"""
Serialization utilities for SpacetimeDB objects to ensure client compatibility.

This module provides functions to serialize SpacetimeDB protocol objects
into dictionary format that client code expects, resolving AttributeError
issues where objects don't behave like dictionaries.
"""

from typing import Any, Dict, List, Union, Optional
import logging
import json

logger = logging.getLogger(__name__)


def _safe_extract(obj: Any, attr_name: str, default: Any = None) -> Any:
    """
    Safely extract attribute from object or dict.
    
    This function handles the core issue identified in the bug report where
    protocol handlers expect dict access but receive objects, causing AttributeError exceptions.
    
    Args:
        obj: Object or dict to extract from
        attr_name: Name of attribute/key to extract
        default: Default value if attribute/key not found
        
    Returns:
        Extracted value or default
    """
    if obj is None:
        return default
    
    # Try attribute access first (for objects)
    if hasattr(obj, attr_name):
        try:
            return getattr(obj, attr_name)
        except (AttributeError, TypeError):
            pass
    
    # Fall back to dict access
    if isinstance(obj, dict):
        return obj.get(attr_name, default)
    
    # Try dictionary-like access (objects with __getitem__)
    if hasattr(obj, '__getitem__') and hasattr(obj, 'get'):
        try:
            return obj.get(attr_name, default)
        except (AttributeError, TypeError):
            pass
    
    # Last resort: try direct __getitem__ access
    if hasattr(obj, '__getitem__'):
        try:
            return obj[attr_name]
        except (KeyError, TypeError, AttributeError):
            pass
    
    return default


def _get_message_type(data: Any) -> Optional[str]:
    """
    Get message type from data handling both objects and dicts.
    
    This function addresses the bug report issue where message type detection
    fails for object-based messages.
    
    Args:
        data: Message data (object or dict)
        
    Returns:
        Message type string or None if not detected
    """
    if data is None:
        return None
    
    # Check object class names first
    if hasattr(data, '__class__'):
        class_name = data.__class__.__name__
        # Check for common message types
        message_types = [
            'DatabaseUpdate', 'SubscriptionUpdate', 'TransactionCommit',
            'TransactionUpdate', 'InitialSubscription', 'IdentityToken',
            'SubscribeApplied', 'SubscriptionError', 'TableUpdate'
        ]
        
        for msg_type in message_types:
            if msg_type in class_name:
                return msg_type
    
    # Original dict-based detection
    if isinstance(data, dict):
        # Check for common message type keys
        if 'database_update' in data:
            return 'DatabaseUpdate'
        elif 'subscription_update' in data:
            return 'SubscriptionUpdate'
        elif 'transaction_commit' in data:
            return 'TransactionCommit'
        elif 'transaction_update' in data:
            return 'TransactionUpdate'
        elif 'initial_subscription' in data:
            return 'InitialSubscription'
        elif 'identity_token' in data:
            return 'IdentityToken'
        elif 'subscribe_applied' in data:
            return 'SubscribeApplied'
        elif 'subscription_error' in data:
            return 'SubscriptionError'
        elif 'table_update' in data:
            return 'TableUpdate'
    
    # Try to extract message type using _safe_extract
    for msg_type in ['DatabaseUpdate', 'SubscriptionUpdate', 'TransactionCommit']:
        if _safe_extract(data, msg_type.lower()) is not None:
            return msg_type
    
    return None


def _handle_database_update(data: Any) -> Dict[str, Any]:
    """
    Handle DatabaseUpdate message with object/dict compatibility.
    
    Args:
        data: DatabaseUpdate data (object or dict)
        
    Returns:
        Formatted database update dictionary
    """
    tables = _safe_extract(data, 'tables', [])
    request_id = _safe_extract(data, 'request_id')
    
    return {
        'type': 'DatabaseUpdate',
        'tables': tables,
        'request_id': request_id
    }


def _handle_subscription_update(data: Any) -> Dict[str, Any]:
    """
    Handle SubscriptionUpdate message with object/dict compatibility.
    
    Args:
        data: SubscriptionUpdate data (object or dict)
        
    Returns:
        Formatted subscription update dictionary
    """
    tables = _safe_extract(data, 'tables', [])
    query_id = _safe_extract(data, 'query_id')
    request_id = _safe_extract(data, 'request_id')
    
    return {
        'type': 'SubscriptionUpdate',
        'tables': tables,
        'query_id': query_id,
        'request_id': request_id
    }


def serialize_for_client(obj: Any) -> Any:
    """
    Serialize SpacetimeDB objects for client consumption.
    
    This function converts SpacetimeDB protocol objects into dictionary
    format that client code expects, ensuring compatibility with code
    that uses .get() methods and dictionary-like access.
    
    Args:
        obj: Object to serialize (can be any SpacetimeDB protocol object)
        
    Returns:
        Dictionary representation suitable for client code
    """
    # Import here to avoid circular imports
    from .protocol import (
        DatabaseUpdate, TimeDuration, Identity, ConnectionId, 
        EnergyQuanta, Timestamp, ReducerCallInfo, IdentityToken,
        TableUpdate, QueryId
    )
    
    if obj is None:
        return None
    
    if isinstance(obj, DatabaseUpdate):
        return {
            'tables': [serialize_for_client(table) for table in obj.tables]
        }
    
    elif isinstance(obj, TimeDuration):
        # Handle both direct nanos and nested dict format
        if hasattr(obj, 'nanos'):
            if isinstance(obj.nanos, dict):
                return {
                    'nanos': obj.nanos,
                    '__time_duration_micros__': obj.nanos.get('__time_duration_micros__')
                }
            else:
                return {
                    'nanos': obj.nanos,
                    '__time_duration_micros__': obj.nanos if isinstance(obj.nanos, int) else None
                }
        return {'nanos': 0}
    
    elif isinstance(obj, Identity):
        return {
            'data': obj.data
        }
    
    elif isinstance(obj, ConnectionId):
        return {
            'data': obj.data
        }
    
    elif isinstance(obj, EnergyQuanta):
        return {
            'quanta': obj.quanta if hasattr(obj, 'quanta') else getattr(obj, 'get', lambda k, d=None: d)('quanta', 0)
        }
    
    elif isinstance(obj, Timestamp):
        # Handle both direct nanos_since_epoch and nested dict format
        if hasattr(obj, 'nanos_since_epoch'):
            if isinstance(obj.nanos_since_epoch, dict):
                return {
                    'nanos_since_epoch': obj.nanos_since_epoch,
                    '__timestamp_micros_since_unix_epoch__': obj.nanos_since_epoch.get('__timestamp_micros_since_unix_epoch__')
                }
            else:
                return {
                    'nanos_since_epoch': obj.nanos_since_epoch
                }
        return {'nanos_since_epoch': 0}
    
    elif isinstance(obj, ReducerCallInfo):
        return {
            'reducer_name': obj.reducer_name,
            'reducer_id': obj.reducer_id,
            'args': obj.args,
            'request_id': obj.request_id
        }
    
    elif isinstance(obj, IdentityToken):
        return {
            'identity': serialize_for_client(obj.identity),
            'token': obj.token,
            'connection_id': serialize_for_client(obj.connection_id)
        }
    
    elif isinstance(obj, TableUpdate):
        return {
            'table_id': obj.table_id,
            'table_name': obj.table_name,
            'num_rows': obj.num_rows,
            'inserts': obj.inserts,
            'deletes': obj.deletes
        }
    
    elif isinstance(obj, QueryId):
        return {
            'id': obj.id
        }
    
    # Handle lists and dictionaries recursively
    elif isinstance(obj, list):
        return [serialize_for_client(item) for item in obj]
    
    elif isinstance(obj, dict):
        return {key: serialize_for_client(value) for key, value in obj.items()}
    
    # Handle objects with DictLikeMixin
    elif hasattr(obj, 'to_dict'):
        try:
            return obj.to_dict()
        except Exception as e:
            logger.debug(f"Error calling to_dict() on {type(obj).__name__}: {e}")
    
    # Handle objects with serialize_for_client method
    elif hasattr(obj, 'serialize_for_client'):
        try:
            return obj.serialize_for_client()
        except Exception as e:
            logger.debug(f"Error calling serialize_for_client() on {type(obj).__name__}: {e}")
    
    # Handle dataclass objects
    elif hasattr(obj, '__dataclass_fields__'):
        try:
            result = {}
            for field_name in obj.__dataclass_fields__:
                if hasattr(obj, field_name):
                    value = getattr(obj, field_name)
                    result[field_name] = serialize_for_client(value)
            return result
        except Exception as e:
            logger.debug(f"Error serializing dataclass {type(obj).__name__}: {e}")
    
    # For primitive types, return as-is
    elif isinstance(obj, (str, int, float, bool, bytes)):
        return obj
    
    # Last resort: try to convert to dict if possible
    elif hasattr(obj, '__dict__'):
        try:
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):  # Skip private attributes
                    result[key] = serialize_for_client(value)
            return result
        except Exception as e:
            logger.debug(f"Error serializing object {type(obj).__name__}: {e}")
    
    # If all else fails, return the object as-is and log a warning
    logger.warning(f"Unable to serialize object of type {type(obj).__name__}, returning as-is")
    return obj


def prepare_message_for_client(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare entire message for client consumption.
    
    This function recursively processes a message dictionary to ensure
    all SpacetimeDB objects are properly serialized for client compatibility.
    
    Args:
        message_data: Raw message data dictionary
        
    Returns:
        Message data with all objects properly serialized
    """
    if not isinstance(message_data, dict):
        return serialize_for_client(message_data)
    
    result = {}
    for key, value in message_data.items():
        result[key] = serialize_for_client(value)
    
    return result


def ensure_dict_compatible(obj: Any) -> Any:
    """
    Ensure an object supports dictionary-like operations.
    
    This function checks if an object already supports dictionary operations
    (.get(), __getitem__, etc.) and if not, converts it to a dictionary.
    
    Args:
        obj: Object to check/convert
        
    Returns:
        Object that supports dictionary operations
    """
    # If it's already a dict, return as-is
    if isinstance(obj, dict):
        return obj
    
    # If it has dictionary-like methods, return as-is
    if hasattr(obj, 'get') and hasattr(obj, '__getitem__'):
        return obj
    
    # Otherwise, serialize it to a dict
    return serialize_for_client(obj)


def validate_serialization(original: Any, serialized: Any) -> bool:
    """
    Validate that serialization preserved essential data.
    
    Args:
        original: Original object
        serialized: Serialized representation
        
    Returns:
        True if serialization is valid, False otherwise
    """
    try:
        # For simple types, they should be equal
        if isinstance(original, (str, int, float, bool, type(None))):
            return original == serialized
        
        # For dictionaries, check that serialized has expected structure
        if isinstance(serialized, dict):
            # Should have some data
            if not serialized and original is not None:
                return False
            
            # Check that all values are serializable to JSON
            try:
                json.dumps(serialized, default=str)
                return True
            except (TypeError, ValueError):
                return False
        
        # For lists, check recursively
        if isinstance(serialized, list):
            return all(validate_serialization(None, item) for item in serialized)
        
        return True
        
    except Exception as e:
        logger.debug(f"Validation error: {e}")
        return False


class ClientCompatibilityWrapper:
    """
    Wrapper class to make any object client-compatible.
    
    This class wraps any object and provides dictionary-like access
    by delegating to the serialize_for_client function.
    """
    
    def __init__(self, wrapped_object: Any):
        """Initialize wrapper with object to wrap."""
        self._wrapped = wrapped_object
        self._serialized = None
    
    def _ensure_serialized(self):
        """Ensure the object is serialized on first access."""
        if self._serialized is None:
            self._serialized = serialize_for_client(self._wrapped)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Dictionary-like get method."""
        self._ensure_serialized()
        if isinstance(self._serialized, dict):
            return self._serialized.get(key, default)
        return default
    
    def __getitem__(self, key: str) -> Any:
        """Dictionary-like access."""
        self._ensure_serialized()
        if isinstance(self._serialized, dict):
            return self._serialized[key]
        raise KeyError(key)
    
    def __contains__(self, key: str) -> bool:
        """Dictionary-like 'in' operator."""
        self._ensure_serialized()
        if isinstance(self._serialized, dict):
            return key in self._serialized
        return False
    
    def keys(self):
        """Dictionary-like keys method."""
        self._ensure_serialized()
        if isinstance(self._serialized, dict):
            return self._serialized.keys()
        return []
    
    def values(self):
        """Dictionary-like values method."""
        self._ensure_serialized()
        if isinstance(self._serialized, dict):
            return self._serialized.values()
        return []
    
    def items(self):
        """Dictionary-like items method."""
        self._ensure_serialized()
        if isinstance(self._serialized, dict):
            return self._serialized.items()
        return []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        self._ensure_serialized()
        return self._serialized if isinstance(self._serialized, dict) else {}
    
    def __repr__(self) -> str:
        """String representation."""
        return f"ClientCompatibilityWrapper({self._wrapped!r})"


def wrap_for_client_compatibility(obj: Any) -> Any:
    """
    Wrap an object to ensure client compatibility.
    
    Args:
        obj: Object to wrap
        
    Returns:
        Object that supports dictionary-like operations
    """
    # If already compatible, return as-is
    if isinstance(obj, dict) or (hasattr(obj, 'get') and hasattr(obj, '__getitem__')):
        return obj
    
    # Otherwise wrap it
    return ClientCompatibilityWrapper(obj)


# Convenience functions for specific object types
def serialize_database_update(db_update) -> Dict[str, Any]:
    """Serialize DatabaseUpdate specifically."""
    return serialize_for_client(db_update)


def serialize_time_duration(time_duration) -> Dict[str, Any]:
    """Serialize TimeDuration specifically."""
    return serialize_for_client(time_duration)


def serialize_identity(identity) -> Dict[str, Any]:
    """Serialize Identity specifically."""
    return serialize_for_client(identity)


def serialize_connection_id(connection_id) -> Dict[str, Any]:
    """Serialize ConnectionId specifically."""
    return serialize_for_client(connection_id)


def serialize_energy_quanta(energy_quanta) -> Dict[str, Any]:
    """Serialize EnergyQuanta specifically."""
    return serialize_for_client(energy_quanta)