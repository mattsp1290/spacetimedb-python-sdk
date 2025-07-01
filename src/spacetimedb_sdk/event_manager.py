"""
Event Manager for SpacetimeDB SDK event handling.

This module provides the SDKEventManager class that handles event chaining
from SDK to client to application, addressing the integration issues identified
in the bug report where events are not properly chained.
"""

import threading
import logging
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass
from enum import Enum
import time

from .serialization import _safe_extract, _get_message_type


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for the SDK event system."""
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_ERROR = "connection_error"
    SUBSCRIPTION_UPDATE = "subscription_update"
    SUBSCRIPTION_APPLIED = "subscription_applied"
    SUBSCRIPTION_ERROR = "subscription_error"
    DATABASE_UPDATE = "database_update"
    TRANSACTION_UPDATE = "transaction_update"
    IDENTITY_TOKEN = "identity_token"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"


@dataclass
class EventData:
    """Container for event data."""
    event_type: EventType
    data: Any
    timestamp: float
    source: str
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'event_type': self.event_type.value,
            'data': self.data,
            'timestamp': self.timestamp,
            'source': self.source,
            'metadata': self.metadata or {}
        }


class SDKEventManager:
    """
    Event manager for SpacetimeDB SDK event handling.
    
    This class addresses the event handler chaining issues identified in the
    bug report by providing:
    - Proper event registration and execution
    - Event chaining from SDK to client to application
    - Error handling in event callbacks
    - Event filtering and routing
    """
    
    def __init__(self, name: str = "SDKEventManager"):
        """Initialize the event manager."""
        self.name = name
        self.event_handlers: Dict[EventType, List[Callable[[EventData], None]]] = {}
        self.global_handlers: List[Callable[[EventData], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self.events_emitted = 0
        self.events_handled = 0
        self.handler_errors = 0
        
        # Configuration
        self.max_handlers_per_event = 50
        self.enable_error_logging = True
        
        logger.info(f"SDKEventManager '{self.name}' initialized")
    
    def register_handler(self, 
                        event_type: EventType, 
                        handler: Callable[[EventData], None]) -> bool:
        """
        Register an event handler for a specific event type.
        
        Args:
            event_type: Type of event to handle
            handler: Callback function to execute
            
        Returns:
            True if registered successfully, False otherwise
        """
        with self._lock:
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = []
            
            handlers = self.event_handlers[event_type]
            
            if len(handlers) >= self.max_handlers_per_event:
                logger.warning(f"Maximum handlers ({self.max_handlers_per_event}) reached for {event_type.value}")
                return False
            
            if handler not in handlers:
                handlers.append(handler)
                logger.debug(f"Registered handler for {event_type.value} (total: {len(handlers)})")
                return True
            else:
                logger.debug(f"Handler already registered for {event_type.value}")
                return False
    
    def register_global_handler(self, handler: Callable[[EventData], None]) -> bool:
        """
        Register a global handler that receives all events.
        
        Args:
            handler: Callback function to execute for all events
            
        Returns:
            True if registered successfully, False otherwise
        """
        with self._lock:
            if handler not in self.global_handlers:
                self.global_handlers.append(handler)
                logger.debug(f"Registered global handler (total: {len(self.global_handlers)})")
                return True
            else:
                logger.debug("Global handler already registered")
                return False
    
    def unregister_handler(self, 
                          event_type: EventType, 
                          handler: Callable[[EventData], None]) -> bool:
        """
        Unregister an event handler.
        
        Args:
            event_type: Type of event
            handler: Handler function to remove
            
        Returns:
            True if unregistered, False if not found
        """
        with self._lock:
            if event_type in self.event_handlers:
                handlers = self.event_handlers[event_type]
                if handler in handlers:
                    handlers.remove(handler)
                    logger.debug(f"Unregistered handler for {event_type.value} (remaining: {len(handlers)})")
                    return True
            return False
    
    def unregister_global_handler(self, handler: Callable[[EventData], None]) -> bool:
        """
        Unregister a global handler.
        
        Args:
            handler: Handler function to remove
            
        Returns:
            True if unregistered, False if not found
        """
        with self._lock:
            if handler in self.global_handlers:
                self.global_handlers.remove(handler)
                logger.debug(f"Unregistered global handler (remaining: {len(self.global_handlers)})")
                return True
            return False
    
    def emit_event(self, 
                   event_type: EventType, 
                   data: Any, 
                   source: str = "SDK",
                   metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Emit an event to all registered handlers.
        
        Args:
            event_type: Type of event to emit
            data: Event data
            source: Source of the event
            metadata: Optional metadata
            
        Returns:
            Number of handlers that successfully processed the event
        """
        with self._lock:
            self.events_emitted += 1
            
            event_data = EventData(
                event_type=event_type,
                data=data,
                timestamp=time.time(),
                source=source,
                metadata=metadata
            )
            
            handled_count = 0
            
            # Execute specific event handlers
            if event_type in self.event_handlers:
                for handler in self.event_handlers[event_type].copy():  # Copy to avoid modification during iteration
                    if self._execute_handler(handler, event_data):
                        handled_count += 1
            
            # Execute global handlers
            for handler in self.global_handlers.copy():
                if self._execute_handler(handler, event_data):
                    handled_count += 1
            
            self.events_handled += handled_count
            
            logger.debug(f"Emitted {event_type.value} event to {handled_count} handlers")
            return handled_count
    
    def _execute_handler(self, handler: Callable[[EventData], None], event_data: EventData) -> bool:
        """
        Execute a single event handler with error handling.
        
        Args:
            handler: Handler function to execute
            event_data: Event data to pass
            
        Returns:
            True if handler executed successfully, False otherwise
        """
        try:
            handler(event_data)
            return True
        except Exception as e:
            self.handler_errors += 1
            if self.enable_error_logging:
                logger.error(f"Error in event handler for {event_data.event_type.value}: {e}")
            return False
    
    def emit_connection_event(self, event_type: EventType, connection_info: Dict[str, Any]) -> int:
        """
        Emit a connection-related event.
        
        Args:
            event_type: Connection event type
            connection_info: Connection information
            
        Returns:
            Number of handlers that processed the event
        """
        return self.emit_event(
            event_type=event_type,
            data=connection_info,
            source="WebSocketClient",
            metadata={'category': 'connection'}
        )
    
    def emit_subscription_event(self, event_type: EventType, subscription_data: Any) -> int:
        """
        Emit a subscription-related event.
        
        Args:
            event_type: Subscription event type
            subscription_data: Subscription data
            
        Returns:
            Number of handlers that processed the event
        """
        # Extract useful metadata from subscription data
        metadata = {'category': 'subscription'}
        
        table_name = _safe_extract(subscription_data, 'table_name')
        if table_name:
            metadata['table_name'] = table_name
        
        request_id = _safe_extract(subscription_data, 'request_id')
        if request_id:
            metadata['request_id'] = request_id
        
        return self.emit_event(
            event_type=event_type,
            data=subscription_data,
            source="SubscriptionManager",
            metadata=metadata
        )
    
    def emit_message_event(self, message_data: Any, direction: str = "received") -> int:
        """
        Emit a message event based on message type detection.
        
        Args:
            message_data: Message data
            direction: "received" or "sent"
            
        Returns:
            Number of handlers that processed the event
        """
        message_type = _get_message_type(message_data)
        
        # Map message types to event types
        if message_type == 'DatabaseUpdate':
            event_type = EventType.DATABASE_UPDATE
        elif message_type in ['SubscriptionUpdate', 'SubscribeApplied']:
            event_type = EventType.SUBSCRIPTION_UPDATE
        elif message_type == 'SubscriptionError':
            event_type = EventType.SUBSCRIPTION_ERROR
        elif message_type == 'TransactionUpdate':
            event_type = EventType.TRANSACTION_UPDATE
        elif message_type == 'IdentityToken':
            event_type = EventType.IDENTITY_TOKEN
        else:
            event_type = EventType.MESSAGE_RECEIVED if direction == "received" else EventType.MESSAGE_SENT
        
        metadata = {
            'category': 'message',
            'direction': direction,
            'message_type': message_type
        }
        
        return self.emit_event(
            event_type=event_type,
            data=message_data,
            source="MessageHandler",
            metadata=metadata
        )
    
    def get_handler_count(self, event_type: EventType) -> int:
        """
        Get the number of handlers for a specific event type.
        
        Args:
            event_type: Event type to check
            
        Returns:
            Number of registered handlers
        """
        with self._lock:
            return len(self.event_handlers.get(event_type, []))
    
    def get_global_handler_count(self) -> int:
        """Get the number of global handlers."""
        with self._lock:
            return len(self.global_handlers)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get event manager statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            handler_counts = {}
            for event_type, handlers in self.event_handlers.items():
                handler_counts[event_type.value] = len(handlers)
            
            return {
                'name': self.name,
                'events_emitted': self.events_emitted,
                'events_handled': self.events_handled,
                'handler_errors': self.handler_errors,
                'global_handlers': len(self.global_handlers),
                'specific_handlers': handler_counts,
                'total_specific_handlers': sum(len(handlers) for handlers in self.event_handlers.values()),
                'success_rate': (self.events_handled / max(self.events_emitted, 1)) * 100,
                'error_rate': (self.handler_errors / max(self.events_handled, 1)) * 100
            }
    
    def clear_all_handlers(self) -> None:
        """Clear all event handlers."""
        with self._lock:
            handler_count = sum(len(handlers) for handlers in self.event_handlers.values())
            global_count = len(self.global_handlers)
            
            self.event_handlers.clear()
            self.global_handlers.clear()
            
            logger.info(f"Cleared {handler_count} specific handlers and {global_count} global handlers")
    
    def process_raw_message(self, message_data: Any) -> bool:
        """
        Process a raw message and emit appropriate events.
        
        This method provides integration with the subscription manager
        and message processing pipeline.
        
        Args:
            message_data: Raw message data
            
        Returns:
            True if message was processed and events emitted
        """
        try:
            # Emit the raw message event
            self.emit_message_event(message_data, "received")
            
            # Emit specific events based on message type
            message_type = _get_message_type(message_data)
            
            if message_type in ['DatabaseUpdate', 'SubscriptionUpdate']:
                self.emit_subscription_event(EventType.SUBSCRIPTION_UPDATE, message_data)
            elif message_type == 'SubscribeApplied':
                self.emit_subscription_event(EventType.SUBSCRIPTION_APPLIED, message_data)
            elif message_type == 'SubscriptionError':
                self.emit_subscription_event(EventType.SUBSCRIPTION_ERROR, message_data)
            elif message_type == 'IdentityToken':
                self.emit_event(EventType.IDENTITY_TOKEN, message_data, "ProtocolHandler")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing raw message: {e}")
            return False


# Global event manager instance
_global_event_manager: Optional[SDKEventManager] = None


def get_event_manager() -> SDKEventManager:
    """Get the global event manager instance."""
    global _global_event_manager
    if _global_event_manager is None:
        _global_event_manager = SDKEventManager("GlobalSDKEventManager")
    return _global_event_manager


def set_event_manager(manager: SDKEventManager) -> None:
    """Set the global event manager instance."""
    global _global_event_manager
    _global_event_manager = manager