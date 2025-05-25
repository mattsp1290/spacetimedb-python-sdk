"""
CallReducerFlags - Enum for controlling reducer call behavior

This module provides the CallReducerFlags enum that controls various aspects
of reducer execution behavior, including update notifications and success callbacks.
"""

from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bsatn.writer import Writer
    from .bsatn.reader import Reader


class CallReducerFlags(IntEnum):
    """
    Flags that control the behavior of CallReducer messages.
    
    These flags affect how the server processes reducer calls and what
    notifications are sent back to the client.
    """
    
    # Request full database update after reducer execution
    FULL_UPDATE = 0
    
    # Don't send success notification for this reducer call  
    NO_SUCCESS_NOTIFY = 1
    
    def write_bsatn(self, writer: 'Writer') -> None:
        """
        Write this CallReducerFlags value to a BSATN writer.
        
        Args:
            writer: BSATN writer to write to
        """
        # CallReducerFlags are serialized as u8 values
        writer.write_u8(self.value)
    
    @classmethod
    def read_bsatn(cls, reader: 'Reader') -> 'CallReducerFlags':
        """
        Read a CallReducerFlags value from a BSATN reader.
        
        Args:
            reader: BSATN reader to read from
            
        Returns:
            CallReducerFlags instance
            
        Raises:
            ValueError: If the flag value is not recognized
        """
        from .bsatn.constants import TAG_U8
        
        tag = reader.read_tag()
        if tag != TAG_U8:
            raise ValueError(f"Expected u8 tag for CallReducerFlags, got {tag}")
        
        flag_value = reader.read_u8()
        
        # Validate the flag value
        try:
            return cls(flag_value)
        except ValueError:
            raise ValueError(f"Invalid CallReducerFlags value: {flag_value}")
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return f"CallReducerFlags.{self.name}"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"CallReducerFlags.{self.name}({self.value})" 