"""
WebSocket Integration for Unified Event System

This module provides integration between the WebSocket client and the unified event system,
replacing the scattered event handling across multiple components.
"""

import logging
from typing import Any, Dict, Optional, Callable, List
from .core_events import (
    Event, EventType, EventPriority,
    ConnectionEvent, AuthenticationEvent, SubscriptionEvent,
    TableEvent, ReducerEvent, TransactionEvent, MessageEvent, ErrorEvent
)
from .event_manager import get_event_manager, EventContext
from .event_filters import type_filter, CommonFilters

logger = logging.getLogger(__name__)


class WebSocketEventIntegration:
    """
    Integration layer between WebSocket client and unified event system.
    
    This class replaces the scattered event handling in the WebSocket client
    with centralized event management.
    """
    
    def __init__(self, websocket_client=None):
        """Initialize WebSocket event integration."""
        self.websocket_client = websocket_client
        self.event_manager = get_event_manager()
        self._connection_handlers: List[str] = []
        self._message_handlers: List[str] = []
        self._setup_internal_handlers()
        
        logger.info("WebSocket event integration initialized")
    
    def _setup_internal_handlers(self):
        """Setup internal event handlers for WebSocket events."""
        
        # Handle connection events internally
        connection_handler_id = self.event_manager.on(
            "*",  # Listen to all events
            self._internal_connection_handler,
            priority=100,  # High priority for internal handling
            handler_name="websocket_connection_handler"
        )
        self._connection_handlers.append(connection_handler_id)
        
        # Handle message routing internally
        message_handler_id = self.event_manager.on(
            "*",
            self._internal_message_router,
            priority=90,  # High priority for message routing
            handler_name="websocket_message_router"
        )
        self._message_handlers.append(message_handler_id)
    
    def _internal_connection_handler(self, context: EventContext):
        """Internal handler for connection state management."""
        event = context.event
        
        # Only handle connection events
        if not event.type.value.startswith('connection'):
            return
        
        # Log connection state changes
        logger.info(f"Connection event: {event.type.value} - {event.data}")
        
        # Update WebSocket client state if available
        if self.websocket_client:
            try:
                if event.type == EventType.CONNECTION_ESTABLISHED:
                    self._handle_connection_established(event)
                elif event.type == EventType.CONNECTION_CLOSED:
                    self._handle_connection_closed(event)
                elif event.type == EventType.CONNECTION_ERROR:
                    self._handle_connection_error(event)
            except Exception as e:
                logger.error(f"Error in connection handler: {e}")
    
    def _internal_message_router(self, context: EventContext):
        """Internal router for message-based events."""
        event = context.event
        
        # Route based on event type
        if event.type == EventType.MESSAGE_RECEIVED:
            self._route_received_message(event)
        elif event.type == EventType.SUBSCRIPTION_UPDATE:
            self._route_subscription_update(event)
        elif event.type == EventType.DATABASE_UPDATE:
            self._route_database_update(event)
    
    def _handle_connection_established(self, event: Event):
        """Handle connection established event."""
        connection_id = event.get_context('connection_id')
        host = event.get_context('host')
        
        logger.info(f"WebSocket connection established: {connection_id} to {host}")
        
        # Update client state
        if self.websocket_client and hasattr(self.websocket_client, '_connection_id'):
            self.websocket_client._connection_id = connection_id
    
    def _handle_connection_closed(self, event: Event):
        """Handle connection closed event."""
        reason = event.get_context('reason', 'unknown')
        logger.info(f"WebSocket connection closed: {reason}")
        
        # Clear client state
        if self.websocket_client and hasattr(self.websocket_client, '_connection_id'):
            self.websocket_client._connection_id = None
    
    def _handle_connection_error(self, event: Event):
        """Handle connection error event."""
        error = event.get_context('error', 'unknown error')
        logger.error(f"WebSocket connection error: {error}")
        
        # Emit error event for application handling
        error_event = ErrorEvent(
            error_message=str(error),
            error_type="ConnectionError",
            component="WebSocketClient",
            operation="connection"
        )
        self.event_manager.emit(error_event)
    
    def _route_received_message(self, event: Event):
        """Route received message to appropriate handlers."""
        message_data = event.get_context('message_data')
        message_type = event.get_context('message_type')
        
        # Create specific events based on message type
        if message_type == 'DatabaseUpdate':
            db_event = Event(
                type=EventType.DATABASE_UPDATE,
                data={
                    'update_data': message_data,
                    'source_message': event.metadata.event_id
                }
            )
            self.event_manager.emit(db_event)
            
        elif message_type == 'SubscriptionUpdate':
            sub_event = SubscriptionEvent(
                operation='update',
                success=True,
                data={'update_data': message_data}
            )
            self.event_manager.emit(sub_event)
            
        elif message_type == 'IdentityToken':
            auth_event = AuthenticationEvent(
                auth_token=message_data.get('token'),
                identity=message_data.get('identity'),
                success=True
            )
            self.event_manager.emit(auth_event)
    
    def _route_subscription_update(self, event: Event):
        """Route subscription update events."""
        # Already handled by message router, but can add additional logic here
        pass
    
    def _route_database_update(self, event: Event):
        """Route database update events."""
        update_data = event.get_context('update_data', {})
        
        # Extract table information if available
        table_name = update_data.get('table_name')
        operation = update_data.get('operation', 'update')
        row_data = update_data.get('row_data')
        
        if table_name:
            table_event = TableEvent(
                table_name=table_name,
                operation=operation,
                row_data=row_data
            )
            self.event_manager.emit(table_event)
    
    # Public API for WebSocket client integration
    
    def emit_connection_opened(self, connection_id: str, host: str, database: str):
        """Emit connection opened event."""
        event = ConnectionEvent(
            connection_id=connection_id,
            state="opened",
            host=host,
            database=database
        )
        event.type = EventType.CONNECTION_OPENED
        self.event_manager.emit(event)
    
    def emit_connection_established(self, connection_id: str, host: str, database: str):
        """Emit connection established event."""
        event = ConnectionEvent(
            connection_id=connection_id,
            state="established",
            host=host,
            database=database
        )
        self.event_manager.emit(event)
    
    def emit_connection_closed(self, connection_id: Optional[str] = None, reason: str = "unknown"):
        """Emit connection closed event."""
        event = ConnectionEvent(
            connection_id=connection_id,
            state="closed",
            error=reason
        )
        event.type = EventType.CONNECTION_CLOSED
        self.event_manager.emit(event)
    
    def emit_connection_error(self, error: str, connection_id: Optional[str] = None):
        """Emit connection error event."""
        event = ConnectionEvent(
            connection_id=connection_id,
            state="error",
            error=error
        )
        event.type = EventType.CONNECTION_ERROR
        self.event_manager.emit(event)
    
    def emit_message_received(self, message_data: Any, message_type: Optional[str] = None):
        """Emit message received event."""
        event = MessageEvent(
            message_data=message_data,
            direction="received",
            message_type=message_type
        )
        self.event_manager.emit(event)
    
    def emit_message_sent(self, message_data: Any, message_type: Optional[str] = None):
        """Emit message sent event."""
        event = MessageEvent(
            message_data=message_data,
            direction="sent",
            message_type=message_type
        )
        self.event_manager.emit(event)
    
    def emit_identity_token_received(self, token: str, identity: Optional[str] = None):
        """Emit identity token received event."""
        event = AuthenticationEvent(
            auth_token=token,
            identity=identity,
            success=True
        )
        event.type = EventType.IDENTITY_TOKEN
        self.event_manager.emit(event)
    
    def emit_subscription_applied(self, query_id: str, table_name: Optional[str] = None):
        """Emit subscription applied event."""
        event = SubscriptionEvent(
            query_id=query_id,
            table_name=table_name,
            operation="applied",
            success=True
        )
        self.event_manager.emit(event)
    
    def emit_subscription_error(self, error: str, query_id: Optional[str] = None, table_name: Optional[str] = None):
        """Emit subscription error event."""
        event = SubscriptionEvent(
            query_id=query_id,
            table_name=table_name,
            operation="error",
            success=False,
            error=error
        )
        self.event_manager.emit(event)
    
    def emit_database_update(self, update_data: Dict[str, Any]):
        """Emit database update event."""
        event = Event(
            type=EventType.DATABASE_UPDATE,
            data={'update_data': update_data}
        )
        self.event_manager.emit(event)
    
    def emit_transaction_update(self, transaction_data: Dict[str, Any]):
        """Emit transaction update event."""
        transaction_id = transaction_data.get('transaction_id', 'unknown')
        operation = transaction_data.get('operation', 'update')
        
        event = TransactionEvent(
            transaction_id=transaction_id,
            operation=operation,
            success=transaction_data.get('success', True),
            error=transaction_data.get('error')
        )
        self.event_manager.emit(event)
    
    def emit_reducer_called(self, reducer_name: str, args: List[Any] = None, 
                           kwargs_dict: Dict[str, Any] = None, request_id: Optional[bytes] = None):
        """Emit reducer called event."""
        event = ReducerEvent(
            reducer_name=reducer_name,
            args=args or [],
            kwargs_dict=kwargs_dict or {},
            status="called",
            request_id=request_id
        )
        self.event_manager.emit(event)
    
    def emit_reducer_success(self, reducer_name: str, result: Any = None, 
                            energy_used: int = 0, execution_time_nanos: int = 0):
        """Emit reducer success event."""
        event = ReducerEvent(
            reducer_name=reducer_name,
            status="success",
            energy_used=energy_used,
            execution_duration_nanos=execution_time_nanos
        )
        event.type = EventType.REDUCER_SUCCESS
        event.add_context('result', result)
        self.event_manager.emit(event)
    
    def emit_reducer_error(self, reducer_name: str, error: str, 
                          energy_used: int = 0, execution_time_nanos: int = 0):
        """Emit reducer error event."""
        event = ReducerEvent(
            reducer_name=reducer_name,
            status="error",
            error_message=error,
            energy_used=energy_used,
            execution_duration_nanos=execution_time_nanos
        )
        event.type = EventType.REDUCER_ERROR
        self.event_manager.emit(event)
    
    # Event subscription helpers for WebSocket client
    
    def on_connection_event(self, handler: Callable[[EventContext], None], priority: int = 0) -> str:
        """Subscribe to connection events."""
        return self.event_manager.on("*", handler, priority, "connection_event_handler")
    
    def on_message_event(self, handler: Callable[[EventContext], None], priority: int = 0) -> str:
        """Subscribe to message events."""
        filter_func = CommonFilters.websocket_events()
        
        def filtered_handler(context: EventContext):
            if filter_func.matches(context.event):
                handler(context)
        
        return self.event_manager.on("*", filtered_handler, priority, "message_event_handler")
    
    def on_authentication_event(self, handler: Callable[[EventContext], None], priority: int = 0) -> str:
        """Subscribe to authentication events."""
        filter_func = CommonFilters.authentication_events()
        
        def filtered_handler(context: EventContext):
            if filter_func.matches(context.event):
                handler(context)
        
        return self.event_manager.on("*", filtered_handler, priority, "auth_event_handler")
    
    def on_subscription_event(self, handler: Callable[[EventContext], None], priority: int = 0) -> str:
        """Subscribe to subscription events."""
        filter_func = CommonFilters.subscription_events()
        
        def filtered_handler(context: EventContext):
            if filter_func.matches(context.event):
                handler(context)
        
        return self.event_manager.on("*", filtered_handler, priority, "subscription_event_handler")
    
    def on_database_event(self, handler: Callable[[EventContext], None], priority: int = 0) -> str:
        """Subscribe to database events."""
        filter_func = CommonFilters.database_activity()
        
        def filtered_handler(context: EventContext):
            if filter_func.matches(context.event):
                handler(context)
        
        return self.event_manager.on("*", filtered_handler, priority, "database_event_handler")
    
    def shutdown(self):
        """Shutdown the integration and cleanup handlers."""
        # Remove internal handlers
        for handler_id in self._connection_handlers + self._message_handlers:
            self.event_manager.off("*", handler_id)
        
        self._connection_handlers.clear()
        self._message_handlers.clear()
        
        logger.info("WebSocket event integration shutdown")


# Global integration instance
_websocket_integration: Optional[WebSocketEventIntegration] = None


def get_websocket_integration(websocket_client=None) -> WebSocketEventIntegration:
    """Get or create the global WebSocket integration instance."""
    global _websocket_integration
    
    if _websocket_integration is None:
        _websocket_integration = WebSocketEventIntegration(websocket_client)
    elif websocket_client and _websocket_integration.websocket_client != websocket_client:
        # Update the WebSocket client reference
        _websocket_integration.websocket_client = websocket_client
    
    return _websocket_integration


def set_websocket_integration(integration: WebSocketEventIntegration):
    """Set the global WebSocket integration instance."""
    global _websocket_integration
    _websocket_integration = integration


# Convenience functions for WebSocket clients

def emit_ws_connection_opened(connection_id: str, host: str, database: str):
    """Convenience function to emit connection opened."""
    integration = get_websocket_integration()
    integration.emit_connection_opened(connection_id, host, database)


def emit_ws_connection_established(connection_id: str, host: str, database: str):
    """Convenience function to emit connection established."""
    integration = get_websocket_integration()
    integration.emit_connection_established(connection_id, host, database)


def emit_ws_connection_closed(connection_id: Optional[str] = None, reason: str = "unknown"):
    """Convenience function to emit connection closed."""
    integration = get_websocket_integration()
    integration.emit_connection_closed(connection_id, reason)


def emit_ws_connection_error(error: str, connection_id: Optional[str] = None):
    """Convenience function to emit connection error."""
    integration = get_websocket_integration()
    integration.emit_connection_error(error, connection_id)


def emit_ws_message_received(message_data: Any, message_type: Optional[str] = None):
    """Convenience function to emit message received."""
    integration = get_websocket_integration()
    integration.emit_message_received(message_data, message_type)


def emit_ws_message_sent(message_data: Any, message_type: Optional[str] = None):
    """Convenience function to emit message sent."""
    integration = get_websocket_integration()
    integration.emit_message_sent(message_data, message_type)


# Integration helper for existing WebSocket clients

class WebSocketEventMixin:
    """
    Mixin class for WebSocket clients to easily integrate with unified events.
    
    Add this as a parent class to existing WebSocket clients to get event integration.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_integration = get_websocket_integration(self)
    
    def _emit_connection_opened(self, connection_id: str, host: str, database: str):
        """Emit connection opened event."""
        self._event_integration.emit_connection_opened(connection_id, host, database)
    
    def _emit_connection_established(self, connection_id: str, host: str, database: str):
        """Emit connection established event."""
        self._event_integration.emit_connection_established(connection_id, host, database)
    
    def _emit_connection_closed(self, connection_id: Optional[str] = None, reason: str = "unknown"):
        """Emit connection closed event."""
        self._event_integration.emit_connection_closed(connection_id, reason)
    
    def _emit_connection_error(self, error: str, connection_id: Optional[str] = None):
        """Emit connection error event."""
        self._event_integration.emit_connection_error(error, connection_id)
    
    def _emit_message_received(self, message_data: Any, message_type: Optional[str] = None):
        """Emit message received event."""
        self._event_integration.emit_message_received(message_data, message_type)
    
    def _emit_message_sent(self, message_data: Any, message_type: Optional[str] = None):
        """Emit message sent event."""
        self._event_integration.emit_message_sent(message_data, message_type)
    
    def on_connection_event(self, handler: Callable[[EventContext], None], priority: int = 0) -> str:
        """Subscribe to connection events."""
        return self._event_integration.on_connection_event(handler, priority)
    
    def on_message_event(self, handler: Callable[[EventContext], None], priority: int = 0) -> str:
        """Subscribe to message events."""
        return self._event_integration.on_message_event(handler, priority)