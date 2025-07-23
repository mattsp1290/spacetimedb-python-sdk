"""
Base serializable enum implementations for pytest-xdist compatibility.

This module provides base classes and patterns to ensure all enums in the
SpacetimeDB SDK are serializable for parallel test execution with pytest-xdist.
"""

import json
import pickle
from enum import Enum
from typing import Dict, Any, Type, Union


class SerializableEnum(Enum):
    """
    Base enum class that ensures compatibility with pytest-xdist serialization.
    
    This class provides additional methods to make enums fully serializable
    for use in parallel testing environments.
    """
    
    def __reduce__(self):
        """Custom pickle serialization for better compatibility."""
        return (self.__class__, (self.value,))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert enum to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'value': self.value,
            'class': self.__class__.__name__
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SerializableEnum':
        """Reconstruct enum from dictionary."""
        if data.get('class') != cls.__name__:
            raise ValueError(f"Cannot deserialize {data.get('class')} as {cls.__name__}")
        return cls(data['value'])
    
    def to_json(self) -> str:
        """Convert enum to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SerializableEnum':
        """Reconstruct enum from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __str__(self) -> str:
        """String representation using value."""
        return str(self.value)
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"{self.__class__.__name__}.{self.name}"


class StringEnum(SerializableEnum):
    """String-based enum that's inherently serializable."""
    
    def __str__(self) -> str:
        return self.value


def make_enum_serializable(enum_class: Type[Enum]) -> Type[SerializableEnum]:
    """
    Convert an existing enum class to be serializable.
    
    This is a utility function to retrofit existing enums with serialization
    capabilities without changing their API.
    
    Args:
        enum_class: The enum class to make serializable
        
    Returns:
        New enum class with serialization capabilities
    """
    
    # Create new enum class that inherits from SerializableEnum
    new_attrs = {}
    for member in enum_class:
        new_attrs[member.name] = member.value
    
    # Create the new class
    new_class = type(
        enum_class.__name__,
        (SerializableEnum,),
        new_attrs
    )
    
    # Copy over docstring and module info
    new_class.__doc__ = enum_class.__doc__
    new_class.__module__ = enum_class.__module__
    
    return new_class


def ensure_enum_serializable(value: Union[Enum, str, int, Any]) -> Any:
    """
    Ensure a value is serializable, converting enums if necessary.
    
    This is a utility function for use in test fixtures and other contexts
    where enum serialization might be an issue.
    
    Args:
        value: The value to ensure is serializable
        
    Returns:
        Serializable version of the value
    """
    if isinstance(value, Enum):
        if hasattr(value, 'to_dict'):
            # Already a SerializableEnum
            return value
        else:
            # Convert to serializable form
            return {
                '_enum_type': value.__class__.__name__,
                '_enum_module': value.__class__.__module__,
                '_enum_name': value.name,
                '_enum_value': value.value
            }
    elif isinstance(value, dict):
        # Recursively ensure dictionary values are serializable
        return {k: ensure_enum_serializable(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        # Recursively ensure sequence items are serializable
        return type(value)(ensure_enum_serializable(item) for item in value)
    else:
        # Value is already serializable
        return value


def restore_enum(data: Dict[str, Any]) -> Enum:
    """
    Restore an enum from serialized data.
    
    Args:
        data: Dictionary containing enum serialization data
        
    Returns:
        Restored enum instance
    """
    if not isinstance(data, dict) or '_enum_type' not in data:
        return data
    
    # Import the enum class
    module_name = data['_enum_module']
    class_name = data['_enum_type']
    
    try:
        module = __import__(module_name, fromlist=[class_name])
        enum_class = getattr(module, class_name)
        return enum_class(data['_enum_value'])
    except (ImportError, AttributeError, ValueError):
        # If we can't restore the enum, return the raw data
        return data


# Test helper functions for pytest compatibility
def create_serializable_test_data(**kwargs) -> Dict[str, Any]:
    """
    Create test data that's guaranteed to be serializable for pytest-xdist.
    
    This function ensures all enum values in the test data are properly
    serialized for parallel test execution.
    
    Args:
        **kwargs: Test data with potentially non-serializable enums
        
    Returns:
        Dictionary with all values made serializable
    """
    return {k: ensure_enum_serializable(v) for k, v in kwargs.items()}


def pytest_parametrize_with_enums(*enum_values):
    """
    Create pytest parametrize values that work with pytest-xdist.
    
    This decorator ensures enum parameters are serializable for parallel tests.
    
    Args:
        *enum_values: Enum values to use as test parameters
        
    Returns:
        List of serializable parameter values
    """
    return [ensure_enum_serializable(value) for value in enum_values]