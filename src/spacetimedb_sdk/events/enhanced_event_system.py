"""
Enhanced Event System for SpacetimeDB SDK

Production-ready event management system with advanced features extracted
from blackholio-python-client's battle-tested patterns.

This module serves as a main entry point that imports from the refactored modules:
- event_types.py: Core event types, enums, and base classes
- event_handlers.py: Handler utilities and filtering
- event_manager.py: Main event management functionality
"""

import logging

# Import from refactored modules
from .event_types import (
    Event, EventT, EventType, EventPriority, EventMetrics
)
from .event_handlers import (
    EventFilter, EventHandler, AsyncEventHandler, SyncEventHandler,
    EventSubscriber, CallbackEventSubscriber, FilteredEventSubscriber,
    create_callback_handler, create_filtered_handler, create_type_filter,
    create_priority_filter, create_source_filter, create_age_filter
)
from .event_manager import (
    UnifiedEventManager as EnhancedEventManager, get_event_manager, event_context,
    publish_event, subscribe_to_events
)

logger = logging.getLogger(__name__)

# Export all important classes and functions for backward compatibility
__all__ = [
    # Event types and core classes
    'Event',
    'EventT', 
    'EventType',
    'EventPriority',
    'EventMetrics',
    
    # Event handlers and filtering
    'EventFilter',
    'EventHandler',
    'AsyncEventHandler',
    'SyncEventHandler',
    'EventSubscriber',
    'CallbackEventSubscriber',
    'FilteredEventSubscriber',
    
    # Helper functions for creating handlers and filters
    'create_callback_handler',
    'create_filtered_handler',
    'create_type_filter',
    'create_priority_filter',
    'create_source_filter',
    'create_age_filter',
    
    # Event manager and utilities
    'EnhancedEventManager',
    'get_event_manager',
    'event_context',
    'publish_event',
    'subscribe_to_events'
]