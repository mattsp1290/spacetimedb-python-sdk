"""
SpacetimeDB Protocol Helpers

This module provides convenient helper functions for encoding SpacetimeDB protocol messages
in the correct binary format. These functions are useful for any client that needs to send
properly formatted messages to SpacetimeDB servers.

Fixes the common issue where clients send JSON messages (starting with '{') but servers
expect binary BSATN format, resulting in "unknown tag 0x7b for sum type ClientMessage" errors.
"""

from typing import List, Dict, Any, Optional, Union
from .protocol import (
    ProtocolEncoder, 
    ProtocolDecoder,
    Subscribe,
    SubscribeSingleMessage,
    CallReducer,
    OneOffQuery,
    generate_request_id,
    BIN_PROTOCOL,
    TEXT_PROTOCOL
)
from .query_id import QueryId
from .call_reducer_flags import CallReducerFlags
import json
import uuid


class SpacetimeDBProtocolHelper:
    """
    Helper class for encoding SpacetimeDB protocol messages.
    
    Provides simple methods for creating properly formatted binary or JSON messages
    that can be sent to SpacetimeDB servers via WebSocket connections.
    """
    
    def __init__(self, use_binary: bool = True):
        """
        Initialize the protocol helper.
        
        Args:
            use_binary: If True, encode messages in binary BSATN format.
                       If False, encode messages in JSON format.
        """
        self.use_binary = use_binary
        self.encoder = ProtocolEncoder(use_binary=use_binary)
        self.decoder = ProtocolDecoder(use_binary=use_binary)
    
    def get_protocol_subprotocol(self) -> str:
        """
        Get the WebSocket subprotocol string for this encoding format.
        
        Returns:
            The subprotocol string to use in WebSocket connections
        """
        return BIN_PROTOCOL if self.use_binary else TEXT_PROTOCOL
    
    def get_expected_frame_type(self) -> str:
        """
        Get the expected WebSocket frame type for this protocol.
        
        Returns:
            "BINARY" for binary protocol, "TEXT" for JSON protocol
        """
        return "BINARY" if self.use_binary else "TEXT"
    
    def validate_protocol_consistency(self) -> None:
        """
        Validate that protocol configuration is consistent.
        
        Raises:
            ValueError: If protocol configuration is inconsistent
        """
        subprotocol = self.get_protocol_subprotocol()
        
        if self.use_binary and "json" in subprotocol:
            raise ValueError(f"Protocol mismatch: use_binary=True but subprotocol is {subprotocol}")
        
        if not self.use_binary and "bsatn" in subprotocol:
            raise ValueError(f"Protocol mismatch: use_binary=False but subprotocol is {subprotocol}")
    
    def encode_subscription(self, tables: List[str], request_id: Optional[int] = None) -> Union[bytes, str]:
        """
        Encode a subscription message for multiple tables.
        
        Args:
            tables: List of table names or SQL queries to subscribe to
            request_id: Optional request ID (auto-generated if not provided)
            
        Returns:
            Encoded message bytes ready for WebSocket transmission
        """
        if request_id is None:
            request_id = generate_request_id()
        
        # Convert table names to SQL queries if they're just table names
        query_strings = []
        for table in tables:
            if self._is_table_name(table):
                query_strings.append(f"SELECT * FROM {table}")
            else:
                query_strings.append(table)
        
        subscribe_msg = Subscribe(
            query_strings=query_strings,
            request_id=request_id
        )
        
        encoded = self.encoder.encode_client_message(subscribe_msg)
        
        # Return appropriate type based on protocol
        if self.use_binary:
            return encoded  # bytes for binary protocol
        else:
            # Convert bytes to string for JSON protocol
            if isinstance(encoded, bytes):
                return encoded.decode('utf-8')
            return encoded
    
    def encode_single_subscription(self, table_or_query: str, 
                                 query_id: Optional[int] = None,
                                 request_id: Optional[int] = None) -> Union[bytes, str]:
        """
        Encode a subscription message for a single table or query.
        
        Args:
            table_or_query: Table name or SQL query to subscribe to
            query_id: Optional query ID (auto-generated if not provided)
            request_id: Optional request ID (auto-generated if not provided)
            
        Returns:
            Encoded message bytes ready for WebSocket transmission
        """
        if request_id is None:
            request_id = generate_request_id()
        
        if query_id is None:
            query_id = request_id
        
        # Convert table name to SQL query if needed
        query = table_or_query
        if self._is_table_name(table_or_query):
            query = f"SELECT * FROM {table_or_query}"
        
        subscribe_msg = SubscribeSingleMessage(
            query=query,
            request_id=request_id,
            query_id=QueryId(id=query_id)
        )
        
        encoded = self.encoder.encode_client_message(subscribe_msg)
        
        # Return appropriate type based on protocol
        if self.use_binary:
            return encoded  # bytes for binary protocol
        else:
            # Convert bytes to string for JSON protocol
            if isinstance(encoded, bytes):
                return encoded.decode('utf-8')
            return encoded
    
    def encode_reducer_call(self, reducer_name: str, 
                          args: Dict[str, Any], 
                          request_id: Optional[int] = None,
                          flags: CallReducerFlags = CallReducerFlags.FULL_UPDATE) -> Union[bytes, str]:
        """
        Encode a reducer call message.
        
        Args:
            reducer_name: Name of the reducer to call
            args: Arguments for the reducer
            request_id: Optional request ID (auto-generated if not provided)
            flags: Reducer call flags
            
        Returns:
            Encoded message bytes ready for WebSocket transmission
        """
        if request_id is None:
            request_id = generate_request_id()
        
        # Convert args to JSON bytes
        args_bytes = json.dumps(args).encode('utf-8')
        
        call_reducer_msg = CallReducer(
            reducer=reducer_name,
            args=args_bytes,
            request_id=request_id,
            flags=flags
        )
        
        encoded = self.encoder.encode_client_message(call_reducer_msg)
        
        # Return appropriate type based on protocol
        if self.use_binary:
            return encoded  # bytes for binary protocol
        else:
            # Convert bytes to string for JSON protocol
            if isinstance(encoded, bytes):
                return encoded.decode('utf-8')
            return encoded
    
    def encode_one_off_query(self, query: str, message_id: Optional[bytes] = None) -> Union[bytes, str]:
        """
        Encode a one-off query message.
        
        Args:
            query: SQL query to execute
            message_id: Optional message ID (auto-generated if not provided)
            
        Returns:
            Encoded message bytes ready for WebSocket transmission
        """
        if message_id is None:
            message_id = uuid.uuid4().bytes
        
        query_msg = OneOffQuery(
            message_id=message_id,
            query_string=query
        )
        
        encoded = self.encoder.encode_client_message(query_msg)
        
        # Return appropriate type based on protocol
        if self.use_binary:
            return encoded  # bytes for binary protocol
        else:
            # Convert bytes to string for JSON protocol
            if isinstance(encoded, bytes):
                return encoded.decode('utf-8')
            return encoded
    
    def decode_server_message(self, data: bytes):
        """
        Decode a server message from received bytes.
        
        Args:
            data: Raw message bytes received from WebSocket
            
        Returns:
            Decoded server message object
        """
        return self.decoder.decode_server_message(data)
    
    def _is_table_name(self, text: str) -> bool:
        """
        Check if text looks like a simple table name vs. a SQL query.
        
        Args:
            text: Text to check
            
        Returns:
            True if it looks like a table name, False if it looks like a SQL query
        """
        if not text:
            return False
        
        # If it contains spaces or SQL keywords, assume it's a query
        sql_keywords = ['select', 'from', 'where', 'join', 'order', 'group', 'having', 'limit']
        text_lower = text.lower().strip()
        
        if ' ' in text_lower:
            return False
        
        for keyword in sql_keywords:
            if keyword in text_lower:
                return False
        
        return True


# Convenience functions for quick use

def get_json_protocol_subprotocol() -> str:
    """
    Get the JSON protocol subprotocol string.
    
    Returns:
        The JSON protocol subprotocol string for WebSocket connections
    """
    return TEXT_PROTOCOL

def get_binary_protocol_subprotocol() -> str:
    """
    Get the binary protocol subprotocol string.
    
    Returns:
        The binary protocol subprotocol string for WebSocket connections
    """
    return BIN_PROTOCOL

def create_binary_subscription(tables: List[str]) -> bytes:
    """
    Create a binary-encoded subscription message for multiple tables.
    
    Args:
        tables: List of table names to subscribe to
        
    Returns:
        Binary message bytes ready for WebSocket transmission
        
    Example:
        message = create_binary_subscription(["entity", "player", "circle"])
        await websocket.send(message)
    """
    helper = SpacetimeDBProtocolHelper(use_binary=True)
    result = helper.encode_subscription(tables)
    # Ensure we return bytes for binary protocol
    return result if isinstance(result, bytes) else result.encode('utf-8')


def create_binary_reducer_call(reducer_name: str, args: Dict[str, Any]) -> bytes:
    """
    Create a binary-encoded reducer call message.
    
    Args:
        reducer_name: Name of the reducer to call
        args: Arguments for the reducer
        
    Returns:
        Binary message bytes ready for WebSocket transmission
        
    Example:
        message = create_binary_reducer_call("enter_game", {"player_name": "Alice"})
        await websocket.send(message)
    """
    helper = SpacetimeDBProtocolHelper(use_binary=True)
    result = helper.encode_reducer_call(reducer_name, args)
    # Ensure we return bytes for binary protocol
    return result if isinstance(result, bytes) else result.encode('utf-8')


def create_json_subscription(tables: List[str]) -> str:
    """
    Create a JSON-encoded subscription message for multiple tables.
    
    Args:
        tables: List of table names to subscribe to
        
    Returns:
        JSON message string ready for WebSocket text frame transmission
        
    Example:
        message = create_json_subscription(["entity", "player"])
        await websocket.send(message)  # Sends as TEXT frame
    """
    helper = SpacetimeDBProtocolHelper(use_binary=False)
    result = helper.encode_subscription(tables)
    # Ensure we return string for JSON protocol
    return result if isinstance(result, str) else result.decode('utf-8')


def create_json_reducer_call(reducer_name: str, args: Dict[str, Any]) -> str:
    """
    Create a JSON-encoded reducer call message.
    
    Args:
        reducer_name: Name of the reducer to call
        args: Arguments for the reducer
        
    Returns:
        JSON message string ready for WebSocket text frame transmission
        
    Example:
        message = create_json_reducer_call("enter_game", {"player_name": "Alice"})
        await websocket.send(message)  # Sends as TEXT frame
    """
    helper = SpacetimeDBProtocolHelper(use_binary=False)
    result = helper.encode_reducer_call(reducer_name, args)
    # Ensure we return string for JSON protocol
    return result if isinstance(result, str) else result.decode('utf-8')


def get_binary_protocol_subprotocol() -> str:
    """Get the binary protocol subprotocol string."""
    return BIN_PROTOCOL


def get_json_protocol_subprotocol() -> str:
    """Get the JSON protocol subprotocol string."""
    return TEXT_PROTOCOL