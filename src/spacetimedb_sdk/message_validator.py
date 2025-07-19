"""
SpacetimeDB Message Validation

Validates that messages conform to the SpacetimeDB protocol specification
and prevents invalid custom message types from being sent.
"""

import json
import time
from typing import Dict, Any, Set, List, Union, Optional
from enum import Enum
import logging

from .protocol import ClientMessage
from .query_id import QueryId


class MessageValidationError(Exception):
    """Raised when a message fails validation."""
    pass


class SpacetimeDBMessageValidator:
    """
    Validates messages conform to SpacetimeDB protocol specification.
    
    Prevents protocol violations by blocking invalid message types and formats
    that could cause server-side parsing failures.
    """
    
    # Valid SpacetimeDB message types as defined in the protocol
    VALID_MESSAGE_TYPES = {
        'CallReducer',
        'Subscribe', 
        'OneOffQuery',
        'SubscribeSingle',
        'SubscribeMulti', 
        'Unsubscribe',
        'UnsubscribeMulti'
    }
    
    # Enhanced message classes that map to legacy validation names
    ENHANCED_MESSAGE_MAPPING = {
        'SubscribeSingleMessage': 'SubscribeSingle',
        'SubscribeMultiMessage': 'SubscribeMulti',
        'UnsubscribeMultiMessage': 'UnsubscribeMulti',
        'OneOffQueryMessage': 'OneOffQuery',
        'CallReducerMessage': 'CallReducer'
    }
    
    # All valid message class names (legacy + enhanced)
    VALID_CLASS_NAMES = VALID_MESSAGE_TYPES | set(ENHANCED_MESSAGE_MAPPING.keys())
    
    # Invalid custom message types that clients sometimes try to send
    INVALID_CUSTOM_TYPES = {
        'heartbeat',
        'ping',
        'pong', 
        'close',
        'connect',
        'disconnect',
        'keep_alive',
        'status',
        'health_check'
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @classmethod
    def validate_message(cls, message: Union[Dict[str, Any], ClientMessage]) -> bool:
        """
        Validate message conforms to SpacetimeDB protocol.
        
        Args:
            message: Message to validate (dict or ClientMessage object)
            
        Returns:
            True if message is valid
            
        Raises:
            MessageValidationError: If message is invalid
        """
        validator = cls()
        return validator._validate_message_internal(message)
    
    def _validate_message_internal(self, message: Union[Dict[str, Any], ClientMessage]) -> bool:
        """Internal message validation logic."""
        
        # Handle ClientMessage objects
        if not isinstance(message, dict):
            if hasattr(message, '__class__'):
                # Check if it's a valid ClientMessage type
                class_name = message.__class__.__name__
                if class_name in self.VALID_CLASS_NAMES:
                    return True
                else:
                    raise MessageValidationError(
                        f"Invalid ClientMessage type: {class_name}. "
                        f"Valid types: {self.VALID_MESSAGE_TYPES}"
                    )
            
            # Try to convert to dict for validation
            if hasattr(message, '__dict__'):
                message = message.__dict__
            else:
                raise MessageValidationError(
                    f"Cannot validate message of type: {type(message)}"
                )
        
        # Validate dictionary-based messages
        return self._validate_dict_message(message)
    
    def _validate_dict_message(self, message: Dict[str, Any]) -> bool:
        """
        Validate dictionary-based message format.
        
        Supports both formats for SDK-client compatibility:
        1. Direct variant format (preferred): {"CallReducer": {...}}
        2. Legacy format (migration support): {"type": "CallReducer", "CallReducer": {...}}
        """
        
        # Check for legacy 'type' field usage
        if 'type' in message:
            message_type = message['type']
            
            # Block known invalid custom types
            if message_type in self.INVALID_CUSTOM_TYPES:
                raise MessageValidationError(
                    f"Invalid custom message type: '{message_type}'. "
                    f"SpacetimeDB does not support custom message types. "
                    f"Valid message types: {self.VALID_MESSAGE_TYPES}"
                )
            
            # For valid types in legacy format, log warning but don't fail
            if message_type in self.VALID_MESSAGE_TYPES:
                self.logger.warning(
                    f"Message contains legacy 'type' field: {message_type}. "
                    f"Consider using direct variant format: {{'{message_type}': {{...}}}}"
                )
            else:
                # Unknown type field - this might be problematic
                self.logger.warning(
                    f"Message contains unknown 'type' field: '{message_type}'. "
                    f"This field is not part of SpacetimeDB protocol specification."
                )
        
        # Validate message structure - check for direct variant format (preferred)
        valid_keys = set(message.keys())
        
        # Check if message contains any valid SpacetimeDB message type as top-level key
        has_valid_message_type = bool(valid_keys.intersection(self.VALID_MESSAGE_TYPES))
        
        # Also check for enhanced message types that might have different names
        enhanced_message_types = set(self.ENHANCED_MESSAGE_MAPPING.keys())
        has_enhanced_message_type = bool(valid_keys.intersection(enhanced_message_types))
        
        # Accept message if it has valid message type structure
        if has_valid_message_type or has_enhanced_message_type:
            # Validate specific message type requirements
            self._validate_message_type_requirements(message)
            return True
        
        # If no direct variants found, check if this might be a legacy format issue
        if 'type' in message and message['type'] in self.VALID_MESSAGE_TYPES:
            # This looks like a legacy format where type field exists but variant key is missing
            raise MessageValidationError(
                f"Message has legacy 'type' field but missing variant key. "
                f"Expected: {{'{message['type']}': {{...}}}} "
                f"Got: {list(valid_keys)}"
            )
        
        # Final fallback - message doesn't match expected format
        raise MessageValidationError(
            f"Invalid SpacetimeDB message format. Message must contain one of: {self.VALID_MESSAGE_TYPES}. "
            f"Got keys: {list(valid_keys)}. "
            f"Use direct variant format: {{'MessageType': {{'field': 'value'}}}}"
        )
        
        return True
    
    def _validate_message_type_requirements(self, message: Dict[str, Any]) -> None:
        """Validate requirements for specific message types."""
        
        if 'CallReducer' in message:
            self._validate_call_reducer(message['CallReducer'])
        
        elif 'Subscribe' in message:
            self._validate_subscribe(message['Subscribe'])
        
        elif 'SubscribeSingle' in message:
            self._validate_subscribe_single(message['SubscribeSingle'])
        
        elif 'SubscribeMulti' in message:
            self._validate_subscribe_multi(message['SubscribeMulti'])
        
        elif 'Unsubscribe' in message:
            self._validate_unsubscribe(message['Unsubscribe'])
        
        elif 'UnsubscribeMulti' in message:
            self._validate_unsubscribe_multi(message['UnsubscribeMulti'])
        
        elif 'OneOffQuery' in message:
            self._validate_one_off_query(message['OneOffQuery'])
        
        # Handle enhanced message types
        elif 'SubscribeSingleMessage' in message:
            self._validate_subscribe_single(message['SubscribeSingleMessage'])
        
        elif 'SubscribeMultiMessage' in message:
            self._validate_subscribe_multi(message['SubscribeMultiMessage'])
        
        elif 'UnsubscribeMultiMessage' in message:
            self._validate_unsubscribe_multi(message['UnsubscribeMultiMessage'])
        
        elif 'OneOffQueryMessage' in message:
            self._validate_one_off_query(message['OneOffQueryMessage'])
        
        elif 'CallReducerMessage' in message:
            self._validate_call_reducer(message['CallReducerMessage'])
    
    def _validate_call_reducer(self, call_reducer: Dict[str, Any]) -> None:
        """Validate CallReducer message format."""
        required_fields = {'reducer', 'args', 'request_id'}
        if not required_fields.issubset(call_reducer.keys()):
            missing = required_fields - set(call_reducer.keys())
            raise MessageValidationError(
                f"CallReducer missing required fields: {missing}"
            )
        
        # Validate field types
        if not isinstance(call_reducer['reducer'], str):
            raise MessageValidationError(
                f"CallReducer 'reducer' must be a string, got {type(call_reducer['reducer']).__name__}"
            )
        
        if not isinstance(call_reducer['args'], dict):
            raise MessageValidationError(
                f"CallReducer 'args' must be a dict, got {type(call_reducer['args']).__name__}"
            )
        
        if not isinstance(call_reducer['request_id'], int):
            raise MessageValidationError(
                f"CallReducer 'request_id' must be an int, got {type(call_reducer['request_id']).__name__}"
            )
    
    def _validate_subscribe(self, subscribe: Dict[str, Any]) -> None:
        """Validate Subscribe message format."""
        required_fields = {'query_strings', 'request_id'}
        if not required_fields.issubset(subscribe.keys()):
            missing = required_fields - set(subscribe.keys())
            raise MessageValidationError(
                f"Subscribe missing required fields: {missing}"
            )
        
        # Validate query_strings is a list
        if not isinstance(subscribe['query_strings'], list):
            raise MessageValidationError(
                "Subscribe query_strings must be a list"
            )
    
    def _validate_subscribe_single(self, subscribe_single: Dict[str, Any]) -> None:
        """Validate SubscribeSingle message format."""
        required_fields = {'query', 'request_id', 'query_id'}
        if not required_fields.issubset(subscribe_single.keys()):
            missing = required_fields - set(subscribe_single.keys())
            raise MessageValidationError(
                f"SubscribeSingle missing required fields: {missing}"
            )
    
    def _validate_subscribe_multi(self, subscribe_multi: Dict[str, Any]) -> None:
        """Validate SubscribeMulti message format."""
        required_fields = {'query_strings', 'request_id', 'query_id'}
        if not required_fields.issubset(subscribe_multi.keys()):
            missing = required_fields - set(subscribe_multi.keys())
            raise MessageValidationError(
                f"SubscribeMulti missing required fields: {missing}"
            )
        
        # Validate query_strings is a list
        if not isinstance(subscribe_multi['query_strings'], list):
            raise MessageValidationError(
                "SubscribeMulti query_strings must be a list"
            )
    
    def _validate_unsubscribe(self, unsubscribe: Dict[str, Any]) -> None:
        """Validate Unsubscribe message format."""
        required_fields = {'request_id', 'query_id'}
        if not required_fields.issubset(unsubscribe.keys()):
            missing = required_fields - set(unsubscribe.keys())
            raise MessageValidationError(
                f"Unsubscribe missing required fields: {missing}"
            )
    
    def _validate_unsubscribe_multi(self, unsubscribe_multi: Dict[str, Any]) -> None:
        """Validate UnsubscribeMulti message format."""
        required_fields = {'request_id', 'query_id'}
        if not required_fields.issubset(unsubscribe_multi.keys()):
            missing = required_fields - set(unsubscribe_multi.keys())
            raise MessageValidationError(
                f"UnsubscribeMulti missing required fields: {missing}"
            )
    
    def _validate_one_off_query(self, one_off_query: Dict[str, Any]) -> None:
        """Validate OneOffQuery message format."""
        required_fields = {'message_id', 'query_string'}
        if not required_fields.issubset(one_off_query.keys()):
            missing = required_fields - set(one_off_query.keys())
            raise MessageValidationError(
                f"OneOffQuery missing required fields: {missing}"
            )


class SpacetimeDBHeartbeatManager:
    """
    Provides proper SpacetimeDB-compatible heartbeat/keep-alive functionality.
    
    Instead of sending invalid custom messages, uses valid OneOffQuery messages
    as heartbeats to maintain connection health.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_heartbeat_message(self) -> Dict[str, Any]:
        """
        Create a valid SpacetimeDB heartbeat using OneOffQuery.
        
        Returns:
            Valid OneOffQuery message that can serve as a heartbeat
        """
        import uuid
        
        heartbeat_message = {
            "OneOffQuery": {
                "message_id": list(uuid.uuid4().bytes),
                "query_string": "SELECT 1",  # Simple query as heartbeat
                "timestamp": int(time.time())
            }
        }
        
        return heartbeat_message
    
    def create_connection_test_message(self) -> Dict[str, Any]:
        """
        Create a connection test message using valid SpacetimeDB protocol.
        
        Returns:
            Valid OneOffQuery message for testing connection health
        """
        import uuid
        
        test_message = {
            "OneOffQuery": {
                "message_id": list(uuid.uuid4().bytes),
                "query_string": "SELECT COUNT(*) FROM sqlite_master WHERE type='table'",
                "purpose": "connection_test"
            }
        }
        
        return test_message


# Convenience functions
def validate_spacetimedb_message(message: Union[Dict[str, Any], ClientMessage]) -> bool:
    """
    Validate a SpacetimeDB message.
    
    Args:
        message: Message to validate
        
    Returns:
        True if valid
        
    Raises:
        MessageValidationError: If message is invalid
    """
    return SpacetimeDBMessageValidator.validate_message(message)


def create_heartbeat_message() -> Dict[str, Any]:
    """
    Create a valid heartbeat message for SpacetimeDB.
    
    Returns:
        Valid OneOffQuery message serving as heartbeat
    """
    manager = SpacetimeDBHeartbeatManager()
    return manager.create_heartbeat_message()


def suggest_valid_alternative(invalid_message_type: str) -> str:
    """
    Suggest valid alternatives for invalid custom message types.
    
    Args:
        invalid_message_type: The invalid message type
        
    Returns:
        Suggestion for valid alternative
    """
    suggestions = {
        'heartbeat': 'Use create_heartbeat_message() to create a valid OneOffQuery heartbeat',
        'ping': 'Use create_heartbeat_message() for keep-alive functionality',
        'pong': 'SpacetimeDB handles connection responses automatically',
        'close': 'Use websocket.close() method instead of custom close message',
        'connect': 'Use client.connect() method instead of custom connect message',
        'disconnect': 'Use websocket.close() method instead of custom disconnect message',
        'keep_alive': 'Use create_heartbeat_message() for connection keep-alive',
        'status': 'Query database tables directly using Subscribe or OneOffQuery',
        'health_check': 'Use create_connection_test_message() for health checks'
    }
    
    return suggestions.get(
        invalid_message_type.lower(), 
        f"Use one of the valid SpacetimeDB message types: {SpacetimeDBMessageValidator.VALID_MESSAGE_TYPES}"
    )