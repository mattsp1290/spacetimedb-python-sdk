"""
Base classes and mixins for SpacetimeDB objects to provide dictionary-like behavior.

This module provides the DictLikeMixin class that makes SpacetimeDB objects 
compatible with client code that expects dictionary-like access patterns.
"""

from typing import Any, Dict, List, Union, Iterator, Tuple
import logging

logger = logging.getLogger(__name__)


class DictLikeMixin:
    """
    Mixin to provide dictionary-like behavior to SpacetimeDB objects.
    
    This mixin enables objects to support:
    - .get(key, default) method
    - obj['key'] access
    - 'key' in obj checks
    - .keys(), .values(), .items() methods
    
    This ensures compatibility with client code that expects dictionary-like access.
    """
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Dictionary-like get method.
        
        Args:
            key: Attribute name to retrieve
            default: Default value if key not found
            
        Returns:
            Attribute value or default
        """
        try:
            return getattr(self, key, default)
        except Exception as e:
            logger.debug(f"Error accessing attribute '{key}' on {type(self).__name__}: {e}")
            return default
    
    def __getitem__(self, key: str) -> Any:
        """
        Dictionary-like access using obj[key] syntax.
        
        Args:
            key: Attribute name to retrieve
            
        Returns:
            Attribute value
            
        Raises:
            KeyError: If attribute doesn't exist
        """
        try:
            if hasattr(self, key):
                return getattr(self, key)
            raise KeyError(f"'{key}' not found in {type(self).__name__}")
        except AttributeError:
            raise KeyError(f"'{key}' not found in {type(self).__name__}")
    
    def __contains__(self, key: str) -> bool:
        """
        Dictionary-like 'in' operator support.
        
        Args:
            key: Attribute name to check
            
        Returns:
            True if attribute exists, False otherwise
        """
        return hasattr(self, key)
    
    def keys(self) -> List[str]:
        """
        Dictionary-like keys method.
        
        Returns:
            List of public attribute names
        """
        return [attr for attr in dir(self) 
                if not attr.startswith('_') 
                and not callable(getattr(self, attr, None))]
    
    def values(self) -> List[Any]:
        """
        Dictionary-like values method.
        
        Returns:
            List of public attribute values
        """
        return [getattr(self, key) for key in self.keys()]
    
    def items(self) -> List[Tuple[str, Any]]:
        """
        Dictionary-like items method.
        
        Returns:
            List of (key, value) tuples for public attributes
        """
        return [(key, getattr(self, key)) for key in self.keys()]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert object to dictionary representation.
        
        Returns:
            Dictionary with all public attributes
        """
        return dict(self.items())
    
    def update(self, other: Union[Dict[str, Any], 'DictLikeMixin']) -> None:
        """
        Update object attributes from dictionary or another object.
        
        Args:
            other: Dictionary or DictLikeMixin object to update from
        """
        if isinstance(other, dict):
            for key, value in other.items():
                if hasattr(self, key):
                    setattr(self, key, value)
        elif hasattr(other, 'items'):
            for key, value in other.items():
                if hasattr(self, key):
                    setattr(self, key, value)
        else:
            raise TypeError(f"Cannot update from {type(other)}")


class SerializableMixin:
    """
    Mixin to provide serialization support for SpacetimeDB objects.
    
    This mixin provides methods to serialize objects for client consumption
    and ensure they are properly formatted.
    """
    
    def serialize_for_client(self) -> Dict[str, Any]:
        """
        Serialize object for client consumption.
        
        This method should be overridden by subclasses to provide
        appropriate serialization logic.
        
        Returns:
            Dictionary representation suitable for client code
        """
        if hasattr(self, 'to_dict'):
            return self.to_dict()
        
        # Fallback: serialize public attributes
        return {
            attr: getattr(self, attr) 
            for attr in dir(self) 
            if not attr.startswith('_') 
            and not callable(getattr(self, attr, None))
        }
    
    def __json__(self) -> Dict[str, Any]:
        """Support for JSON serialization."""
        return self.serialize_for_client()


class SpacetimeDBObject(DictLikeMixin, SerializableMixin):
    """
    Base class for all SpacetimeDB objects.
    
    This class combines DictLikeMixin and SerializableMixin to provide
    both dictionary-like access and proper serialization for all
    SpacetimeDB protocol objects.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize SpacetimeDB object with keyword arguments.
        
        Args:
            **kwargs: Attribute values to set
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self) -> str:
        """
        String representation of the object.
        
        Returns:
            String showing class name and key attributes
        """
        class_name = type(self).__name__
        attrs = []
        
        # Show first few key attributes
        for key in self.keys()[:3]:
            value = getattr(self, key)
            if isinstance(value, (str, int, float, bool)):
                attrs.append(f"{key}={repr(value)}")
            else:
                attrs.append(f"{key}={type(value).__name__}(...)")
        
        if len(self.keys()) > 3:
            attrs.append("...")
        
        attrs_str = ", ".join(attrs)
        return f"{class_name}({attrs_str})"
    
    def __eq__(self, other) -> bool:
        """
        Equality comparison.
        
        Args:
            other: Object to compare with
            
        Returns:
            True if objects are equal, False otherwise
        """
        if not isinstance(other, type(self)):
            return False
        
        try:
            for key in self.keys():
                if getattr(self, key) != getattr(other, key, None):
                    return False
            return True
        except Exception:
            return False