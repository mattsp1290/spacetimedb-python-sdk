"""
WebSocket Integration for Unified Event System

This module provides seamless integration between the WebSocket client
and the unified event system, enabling automatic event emission for
WebSocket lifecycle and message events.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass
from enum import Enum
import weakref

from .core_events import EventType, EventContext, create_connection_event
from .event_manager import UnifiedEventManager
from .event_filters import EventFilter, TypeFilter, SourceFilter


logger = logging.getLogger(__name__)


class WebSocketEventType(Enum):
    """WebSocket-specific event types mapped to unified event types."""
    
    # Connection lifecycle
    CONNECTING = EventType.CONNECTION_OPENED
    CONNECTED = EventType.CONNECTION_OPENED
    DISCONNECTING = EventType.CONNECTION_CLOSED
    DISCONNECTED = EventType.CONNECTION_CLOSED
    ERROR = EventType.CONNECTION_ERROR
    RECONNECTING = EventType.CONNECTION_RECONNECTING
    TIMEOUT = EventType.CONNECTION_TIMEOUT
    
    # Message events
    MESSAGE_RECEIVED = EventType.MESSAGE_RECEIVED
    MESSAGE_SENT = EventType.MESSAGE_SENT
    MESSAGE_ERROR = EventType.MESSAGE_ERROR
    MESSAGE_QUEUED = EventType.MESSAGE_QUEUED
    MESSAGE_DROPPED = EventType.MESSAGE_DROPPED
    
    # Protocol events
    HANDSHAKE_COMPLETE = EventType.AUTHENTICATION_SUCCESS
    HANDSHAKE_FAILED = EventType.AUTHENTICATION_FAILED
    HEARTBEAT = EventType.CONNECTION_HEARTBEAT


@dataclass
class WebSocketEventData:
    """Data structure for WebSocket events."""
    connection_id: str
    url: str
    state: str
    timestamp: float
    message: Optional[Any] = None
    error: Optional[Exception] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for event context."""
        return {
            'connection_id': self.connection_id,
            'url': self.url,
            'state': self.state,
            'timestamp': self.timestamp,
            'message': self.message,
            'error': str(self.error) if self.error else None,
            'metadata': self.metadata or {}
        }


class WebSocketEventHandler:
    """
    Handler for WebSocket events that bridges WebSocket clients to the unified event system.
    
    This class automatically captures WebSocket events and emits them through
    the unified event system with proper context and metadata.
    """
    
    def __init__(self, event_manager: UnifiedEventManager):
        self.event_manager = event_manager
        self.connection_registry: Dict[str, Dict[str, Any]] = {}
        self.message_stats: Dict[str, int] = {}
        self.last_heartbeat: Dict[str, float] = {}
        
        # Event emission settings
        self.emit_raw_messages = True
        self.emit_heartbeats = False
        self.batch_messages = True
        self.max_message_size = 1024 * 1024  # 1MB
        
        # Performance tracking
        self.events_emitted = 0
        self.errors_encountered = 0
        self.last_event_time = 0.0
    
    def register_connection(
        self,
        connection_id: str,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Register a new WebSocket connection."""
        self.connection_registry[connection_id] = {
            'url': url,
            'connected_at': time.time(),
            'state': 'connecting',
            'metadata': metadata or {},
            'message_count': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }
        
        # Emit connection event
        self._emit_connection_event(
            EventType.CONNECTION_OPENED,
            connection_id,
            url,
            state='connecting',
            metadata=metadata
        )
    
    def unregister_connection(self, connection_id: str):
        """Unregister a WebSocket connection."""
        if connection_id in self.connection_registry:
            conn_info = self.connection_registry[connection_id]
            
            # Emit disconnection event
            self._emit_connection_event(
                EventType.CONNECTION_CLOSED,
                connection_id,
                conn_info['url'],
                state='disconnected',
                metadata=conn_info['metadata']
            )
            
            # Clean up
            del self.connection_registry[connection_id]
            self.message_stats.pop(connection_id, None)
            self.last_heartbeat.pop(connection_id, None)
    
    def on_connection_opened(self, connection_id: str, url: str, metadata: Optional[Dict[str, Any]] = None):
        """Handle WebSocket connection opened."""
        if connection_id in self.connection_registry:
            self.connection_registry[connection_id]['state'] = 'connected'
            self.connection_registry[connection_id]['connected_at'] = time.time()
        
        self._emit_connection_event(
            EventType.CONNECTION_OPENED,
            connection_id,
            url,
            state='connected',
            metadata=metadata
        )
    
    def on_connection_closed(self, connection_id: str, code: int = None, reason: str = None):
        """Handle WebSocket connection closed."""
        if connection_id in self.connection_registry:
            conn_info = self.connection_registry[connection_id]
            conn_info['state'] = 'disconnected'
            conn_info['close_code'] = code
            conn_info['close_reason'] = reason
            
            metadata = conn_info['metadata'].copy()
            metadata.update({
                'close_code': code,
                'close_reason': reason,
                'duration': time.time() - conn_info['connected_at']
            })
            
            self._emit_connection_event(
                EventType.CONNECTION_CLOSED,
                connection_id,
                conn_info['url'],
                state='disconnected',
                metadata=metadata
            )
    
    def on_connection_error(self, connection_id: str, error: Exception, url: str = None):
        """Handle WebSocket connection error."""
        if connection_id in self.connection_registry:
            conn_info = self.connection_registry[connection_id]
            conn_info['state'] = 'error'
            conn_info['last_error'] = error
            url = url or conn_info['url']
        
        self.errors_encountered += 1
        
        self._emit_connection_event(
            EventType.CONNECTION_ERROR,
            connection_id,
            url or 'unknown',
            state='error',
            error=error,
            metadata={'error_type': type(error).__name__}
        )
    
    def on_message_received(
        self,
        connection_id: str,
        message: Any,
        message_type: str = 'text',
        size: int = None
    ):
        """Handle WebSocket message received."""
        if connection_id in self.connection_registry:
            conn_info = self.connection_registry[connection_id]
            conn_info['message_count'] += 1
            if size:
                conn_info['bytes_received'] += size
        
        self.message_stats[connection_id] = self.message_stats.get(connection_id, 0) + 1
        
        # Check message size limit
        if size and size > self.max_message_size:
            logger.warning(f"Large message received: {size} bytes")
            
            # Emit performance warning
            self._emit_system_event(
                EventType.PERFORMANCE_WARNING,
                connection_id=connection_id,
                warning_type='large_message',
                message_size=size
            )
        
        # Emit message event
        self._emit_message_event(
            EventType.MESSAGE_RECEIVED,
            connection_id,
            message,
            message_type=message_type,
            size=size
        )
    
    def on_message_sent(
        self,
        connection_id: str,
        message: Any,
        message_type: str = 'text',
        size: int = None
    ):
        """Handle WebSocket message sent."""
        if connection_id in self.connection_registry:
            conn_info = self.connection_registry[connection_id]
            if size:
                conn_info['bytes_sent'] += size
        
        self._emit_message_event(
            EventType.MESSAGE_SENT,
            connection_id,
            message,
            message_type=message_type,
            size=size
        )
    
    def on_message_error(self, connection_id: str, error: Exception, message: Any = None):
        """Handle WebSocket message error."""
        self.errors_encountered += 1
        
        self._emit_message_event(
            EventType.MESSAGE_ERROR,
            connection_id,
            message,
            error=error,
            error_type=type(error).__name__
        )
    
    def on_heartbeat(self, connection_id: str):
        """Handle WebSocket heartbeat."""
        if not self.emit_heartbeats:
            return
        
        self.last_heartbeat[connection_id] = time.time()
        
        self._emit_connection_event(
            EventType.CONNECTION_HEARTBEAT,
            connection_id,
            self.connection_registry.get(connection_id, {}).get('url', 'unknown'),
            state='heartbeat'
        )
    
    def on_reconnecting(self, connection_id: str, attempt: int, delay: float):
        """Handle WebSocket reconnection attempt."""
        if connection_id in self.connection_registry:
            self.connection_registry[connection_id]['state'] = 'reconnecting'
        
        self._emit_connection_event(
            EventType.CONNECTION_RECONNECTING,
            connection_id,
            self.connection_registry.get(connection_id, {}).get('url', 'unknown'),
            state='reconnecting',
            metadata={
                'attempt': attempt,
                'delay': delay
            }
        )
    
    def _emit_connection_event(
        self,
        event_type: EventType,
        connection_id: str,
        url: str,
        state: str,
        error: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Emit a connection-related event."""
        event_data = WebSocketEventData(
            connection_id=connection_id,
            url=url,
            state=state,
            timestamp=time.time(),
            error=error,
            metadata=metadata
        )
        
        context = EventContext.create(
            event_type=event_type,
            source="websocket_client",
            data=event_data.to_dict(),
            connection_id=connection_id,
            url=url,
            state=state
        )
        
        self._emit_event(event_type, context)
    
    def _emit_message_event(
        self,
        event_type: EventType,
        connection_id: str,
        message: Any,
        message_type: str = 'text',
        size: Optional[int] = None,
        error: Optional[Exception] = None,
        **metadata
    ):
        """Emit a message-related event."""
        # Determine message size if not provided
        if size is None and message is not None:
            if isinstance(message, str):
                size = len(message.encode('utf-8'))
            elif isinstance(message, bytes):
                size = len(message)
            elif isinstance(message, dict):
                size = len(json.dumps(message).encode('utf-8'))
        
        event_data = {
            'connection_id': connection_id,
            'message': message if self.emit_raw_messages else None,
            'message_type': message_type,
            'size': size,
            'timestamp': time.time(),
            'error': str(error) if error else None
        }
        event_data.update(metadata)
        
        context = EventContext.create(
            event_type=event_type,
            source="websocket_client",
            data=event_data,
            connection_id=connection_id,
            message_type=message_type,
            size=size
        )
        
        self._emit_event(event_type, context)
    
    def _emit_system_event(self, event_type: EventType, **metadata):
        """Emit a system-related event."""
        context = EventContext.create(
            event_type=event_type,
            source="websocket_handler",
            data=metadata,
            **metadata
        )
        
        self._emit_event(event_type, context)
    
    def _emit_event(self, event_type: EventType, context: EventContext):
        """Emit an event through the unified event manager."""
        try:
            self.event_manager.emit(event_type, context)
            self.events_emitted += 1
            self.last_event_time = time.time()
        except Exception as e:
            logger.error(f"Failed to emit event {event_type}: {e}")
            self.errors_encountered += 1
    
    def get_connection_stats(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific connection."""
        if connection_id not in self.connection_registry:
            return None
        
        conn_info = self.connection_registry[connection_id]
        return {
            'connection_id': connection_id,
            'url': conn_info['url'],
            'state': conn_info['state'],
            'connected_at': conn_info['connected_at'],
            'message_count': conn_info['message_count'],
            'bytes_sent': conn_info['bytes_sent'],
            'bytes_received': conn_info['bytes_received'],
            'last_heartbeat': self.last_heartbeat.get(connection_id),
            'metadata': conn_info['metadata']
        }
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall WebSocket handler statistics."""
        active_connections = sum(1 for conn in self.connection_registry.values() if conn['state'] == 'connected')
        total_messages = sum(conn['message_count'] for conn in self.connection_registry.values())
        total_bytes_sent = sum(conn['bytes_sent'] for conn in self.connection_registry.values())
        total_bytes_received = sum(conn['bytes_received'] for conn in self.connection_registry.values())
        
        return {
            'active_connections': active_connections,
            'total_connections': len(self.connection_registry),
            'total_messages': total_messages,
            'total_bytes_sent': total_bytes_sent,
            'total_bytes_received': total_bytes_received,
            'events_emitted': self.events_emitted,
            'errors_encountered': self.errors_encountered,
            'last_event_time': self.last_event_time,
            'emit_raw_messages': self.emit_raw_messages,
            'emit_heartbeats': self.emit_heartbeats,
            'batch_messages': self.batch_messages
        }


class WebSocketEventIntegration:
    """
    Main integration class that provides WebSocket event integration.
    
    This class manages the integration between WebSocket clients and the
    unified event system, providing automatic event emission and filtering.
    """
    
    def __init__(self, event_manager: UnifiedEventManager):
        self.event_manager = event_manager
        self.websocket_handler = WebSocketEventHandler(event_manager)
        self.client_registry: Dict[str, weakref.ref] = {}
        self.auto_register_clients = True
        self.connection_filters: List[EventFilter] = []
        self.message_filters: List[EventFilter] = []
        
        # Set up default filters
        self._setup_default_filters()
    
    def _setup_default_filters(self):
        """Set up default event filters."""
        # Connection event filter
        connection_filter = TypeFilter([
            EventType.CONNECTION_OPENED,
            EventType.CONNECTION_CLOSED,
            EventType.CONNECTION_ERROR,
            EventType.CONNECTION_RECONNECTING,
            EventType.CONNECTION_TIMEOUT,
            EventType.CONNECTION_HEARTBEAT
        ], name="websocket_connection_filter")
        
        # Message event filter
        message_filter = TypeFilter([
            EventType.MESSAGE_RECEIVED,
            EventType.MESSAGE_SENT,
            EventType.MESSAGE_ERROR,
            EventType.MESSAGE_QUEUED,
            EventType.MESSAGE_DROPPED
        ], name="websocket_message_filter")
        
        # WebSocket source filter
        websocket_source_filter = SourceFilter([
            "websocket_client",
            "websocket_handler"
        ], name="websocket_source_filter")
        
        self.connection_filters = [connection_filter, websocket_source_filter]
        self.message_filters = [message_filter, websocket_source_filter]
    
    def register_websocket_client(self, client, connection_id: str, url: str, metadata: Optional[Dict[str, Any]] = None):
        """Register a WebSocket client for automatic event handling."""
        self.client_registry[connection_id] = weakref.ref(client)
        self.websocket_handler.register_connection(connection_id, url, metadata)
        
        # Set up client event hooks if supported
        if hasattr(client, 'on_open'):
            original_on_open = client.on_open
            
            def enhanced_on_open(*args, **kwargs):
                self.websocket_handler.on_connection_opened(connection_id, url, metadata)
                if original_on_open:
                    return original_on_open(*args, **kwargs)
            
            client.on_open = enhanced_on_open
        
        if hasattr(client, 'on_close'):
            original_on_close = client.on_close
            
            def enhanced_on_close(code=None, reason=None, *args, **kwargs):
                self.websocket_handler.on_connection_closed(connection_id, code, reason)
                if original_on_close:
                    return original_on_close(code, reason, *args, **kwargs)
            
            client.on_close = enhanced_on_close
        
        if hasattr(client, 'on_error'):
            original_on_error = client.on_error
            
            def enhanced_on_error(error, *args, **kwargs):
                self.websocket_handler.on_connection_error(connection_id, error, url)
                if original_on_error:
                    return original_on_error(error, *args, **kwargs)
            
            client.on_error = enhanced_on_error
        
        if hasattr(client, 'on_message'):
            original_on_message = client.on_message
            
            def enhanced_on_message(message, *args, **kwargs):
                message_type = 'text' if isinstance(message, str) else 'binary'
                self.websocket_handler.on_message_received(connection_id, message, message_type)
                if original_on_message:
                    return original_on_message(message, *args, **kwargs)
            
            client.on_message = enhanced_on_message
    
    def unregister_websocket_client(self, connection_id: str):
        """Unregister a WebSocket client."""
        if connection_id in self.client_registry:
            del self.client_registry[connection_id]
        
        self.websocket_handler.unregister_connection(connection_id)
    
    def add_connection_filter(self, event_filter: EventFilter):
        """Add a filter for connection events."""
        self.connection_filters.append(event_filter)
    
    def add_message_filter(self, event_filter: EventFilter):
        """Add a filter for message events."""
        self.message_filters.append(event_filter)
    
    def get_active_connections(self) -> List[str]:
        """Get list of active connection IDs."""
        return [
            conn_id for conn_id, conn_info in self.websocket_handler.connection_registry.items()
            if conn_info['state'] == 'connected'
        ]
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific connection."""
        return self.websocket_handler.get_connection_stats(connection_id)
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """Get overall integration statistics."""
        return {
            'registered_clients': len(self.client_registry),
            'active_connections': len(self.get_active_connections()),
            'connection_filters': len(self.connection_filters),
            'message_filters': len(self.message_filters),
            'websocket_handler_stats': self.websocket_handler.get_overall_stats()
        }
    
    def cleanup(self):
        """Clean up the integration."""
        # Unregister all clients
        for connection_id in list(self.client_registry.keys()):
            self.unregister_websocket_client(connection_id)
        
        # Clear filters
        self.connection_filters.clear()
        self.message_filters.clear()


class ConnectionEventMapper:
    """
    Maps WebSocket connection events to unified event system events.
    
    This class provides a mapping layer between WebSocket-specific events
    and the unified event system, enabling consistent event handling.
    """
    
    def __init__(self):
        self.event_mappings = self._create_event_mappings()
        self.reverse_mappings = {v: k for k, v in self.event_mappings.items()}
    
    def _create_event_mappings(self) -> Dict[str, EventType]:
        """Create mappings from WebSocket events to unified events."""
        return {
            'connecting': EventType.CONNECTION_OPENED,
            'open': EventType.CONNECTION_OPENED,
            'connected': EventType.CONNECTION_OPENED,
            'close': EventType.CONNECTION_CLOSED,
            'closed': EventType.CONNECTION_CLOSED,
            'disconnect': EventType.CONNECTION_CLOSED,
            'error': EventType.CONNECTION_ERROR,
            'reconnect': EventType.CONNECTION_RECONNECTING,
            'reconnecting': EventType.CONNECTION_RECONNECTING,
            'timeout': EventType.CONNECTION_TIMEOUT,
            'ping': EventType.CONNECTION_HEARTBEAT,
            'pong': EventType.CONNECTION_HEARTBEAT,
            'heartbeat': EventType.CONNECTION_HEARTBEAT,
            'message': EventType.MESSAGE_RECEIVED,
            'send': EventType.MESSAGE_SENT,
            'message_error': EventType.MESSAGE_ERROR,
            'auth_success': EventType.AUTHENTICATION_SUCCESS,
            'auth_failed': EventType.AUTHENTICATION_FAILED,
            'auth_expired': EventType.AUTHENTICATION_EXPIRED
        }
    
    def map_to_unified_event(self, websocket_event: str) -> Optional[EventType]:
        """Map a WebSocket event to a unified event type."""
        return self.event_mappings.get(websocket_event.lower())
    
    def map_from_unified_event(self, event_type: EventType) -> Optional[str]:
        """Map a unified event type to a WebSocket event."""
        return self.reverse_mappings.get(event_type)
    
    def create_context_from_websocket_event(
        self,
        websocket_event: str,
        connection_id: str,
        url: str,
        data: Optional[Any] = None,
        **metadata
    ) -> Optional[EventContext]:
        """Create an event context from a WebSocket event."""
        unified_event = self.map_to_unified_event(websocket_event)
        if not unified_event:
            return None
        
        return EventContext.create(
            event_type=unified_event,
            source="websocket_client",
            data=data,
            connection_id=connection_id,
            url=url,
            websocket_event=websocket_event,
            **metadata
        )


# Global integration instance
_global_integration = None


def get_global_websocket_integration() -> Optional[WebSocketEventIntegration]:
    """Get the global WebSocket integration instance."""
    return _global_integration


def set_global_websocket_integration(integration: WebSocketEventIntegration):
    """Set the global WebSocket integration instance."""
    global _global_integration
    _global_integration = integration


def create_websocket_integration(event_manager: UnifiedEventManager) -> WebSocketEventIntegration:
    """Create a new WebSocket integration instance."""
    integration = WebSocketEventIntegration(event_manager)
    set_global_websocket_integration(integration)
    return integration


# Convenience functions
def register_websocket_client(client, connection_id: str, url: str, metadata: Optional[Dict[str, Any]] = None):
    """Register a WebSocket client with the global integration."""
    integration = get_global_websocket_integration()
    if integration:
        integration.register_websocket_client(client, connection_id, url, metadata)
    else:
        logger.warning("No global WebSocket integration found")


def unregister_websocket_client(connection_id: str):
    """Unregister a WebSocket client from the global integration."""
    integration = get_global_websocket_integration()
    if integration:
        integration.unregister_websocket_client(connection_id)


def get_websocket_stats() -> Optional[Dict[str, Any]]:
    """Get WebSocket integration statistics."""
    integration = get_global_websocket_integration()
    if integration:
        return integration.get_integration_stats()
    return None