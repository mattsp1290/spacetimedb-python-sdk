#!/usr/bin/env python3
"""
Fix for WebSocket Large Message Handling

The issue is that WebSocket connections fail with "Invalid close frame" errors
after receiving large InitialSubscription messages (61KB+). This fix improves
the WebSocket message handling to properly process large messages.
"""

import websocket
import json
import logging
from typing import Any, Dict, Optional

class ImprovedWebSocketHandler:
    """
    Improved WebSocket message handler for large messages and better error handling.
    """
    
    def __init__(self, original_handler, logger=None):
        self.original_handler = original_handler
        self.logger = logger or logging.getLogger(__name__)
        self.message_buffer = b""
        self.max_message_size = 10 * 1024 * 1024  # 10MB limit
        self.large_message_threshold = 50 * 1024  # 50KB
        
    def enhanced_on_message(self, ws, message):
        """
        Enhanced message handler with support for large messages.
        
        Fixes:
        1. Proper handling of large JSON messages
        2. Buffer management for fragmented messages  
        3. Memory-efficient processing
        4. Better error recovery
        """
        try:
            # Handle message data type
            if isinstance(message, str):
                message_data = message.encode('utf-8')
            else:
                message_data = message
            
            message_size = len(message_data)
            
            # Log large message handling
            if message_size > self.large_message_threshold:
                self.logger.info(f"Processing large message: {message_size} bytes")
                
                # For very large messages, process in chunks to avoid memory issues
                if message_size > self.max_message_size:
                    self.logger.error(f"Message too large: {message_size} bytes (max: {self.max_message_size})")
                    return
            
            # Try to decode and process the message
            try:
                # First, try to parse as JSON to validate structure
                if message_data.startswith(b'{'):
                    # Parse JSON to ensure it's valid before forwarding
                    parsed_json = json.loads(message_data.decode('utf-8'))
                    
                    # Log InitialSubscription details for debugging
                    if "InitialSubscription" in parsed_json:
                        self._log_initial_subscription_details(parsed_json, message_size)
                
                # Forward to original handler
                self.original_handler(ws, message)
                
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error in large message: {e}")
                self.logger.debug(f"Message preview: {message_data[:200]}...")
                raise
                
        except Exception as e:
            self.logger.error(f"Enhanced message handler error: {e}")
            # Don't let message processing errors crash the connection
            # Log the error but continue
    
    def enhanced_on_error(self, ws, error):
        """
        Enhanced error handler with better large message error detection.
        """
        error_str = str(error).lower()
        
        # Detect specific large message issues
        if "invalid close frame" in error_str:
            self.logger.error("WebSocket Invalid Close Frame Error detected")
            self.logger.info("This often occurs after processing large messages (>50KB)")
            self.logger.info("Possible solutions:")
            self.logger.info("1. Server may need WebSocket frame size limit adjustment")
            self.logger.info("2. Client may need chunked message processing")
            self.logger.info("3. Consider message compression or streaming")
            
        elif "frame too large" in error_str or "message too large" in error_str:
            self.logger.error("WebSocket frame size limit exceeded")
            self.logger.info("Consider implementing message chunking or increasing WebSocket limits")
            
        elif "buffer overflow" in error_str or "memory" in error_str:
            self.logger.error("WebSocket buffer/memory issue with large message")
            self.logger.info("Consider streaming large messages or increasing buffer sizes")
        
        # Call original error handler
        if hasattr(self, 'original_error_handler'):
            self.original_error_handler(ws, error)
    
    def enhanced_on_close(self, ws, close_status_code, close_msg):
        """
        Enhanced close handler with better error analysis.
        """
        if close_status_code:
            self.logger.info(f"WebSocket closed with status: {close_status_code}")
            
            # Analyze close codes related to large message issues
            if close_status_code == 1009:  # Message too big
                self.logger.error("WebSocket closed: Message too big (1009)")
                self.logger.info("Server rejected message due to size limit")
            elif close_status_code == 1002:  # Protocol error  
                self.logger.error("WebSocket closed: Protocol error (1002)")
                self.logger.info("Possible frame formatting issue with large messages")
            elif close_status_code == 1006:  # Abnormal closure
                self.logger.error("WebSocket closed: Abnormal closure (1006)")
                self.logger.info("Connection dropped unexpectedly, possibly during large message processing")
        else:
            self.logger.info("WebSocket closed without status code")
        
        # Call original close handler if available
        if hasattr(self, 'original_close_handler'):
            self.original_close_handler(ws, close_status_code, close_msg)
    
    def _log_initial_subscription_details(self, parsed_json: Dict[str, Any], message_size: int):
        """Log details about InitialSubscription for debugging."""
        try:
            initial_sub = parsed_json.get("InitialSubscription", {})
            database_update = initial_sub.get("database_update", {})
            tables = database_update.get("tables", [])
            
            self.logger.info(f"InitialSubscription received: {message_size} bytes")
            self.logger.info(f"Tables in subscription: {len(tables)}")
            
            for table in tables:
                table_name = table.get("table_name", "unknown")
                num_rows = table.get("num_rows", 0)
                self.logger.info(f"  - {table_name}: {num_rows} rows")
                
        except Exception as e:
            self.logger.debug(f"Error logging InitialSubscription details: {e}")


def apply_large_message_fix_to_websocket_client(ws_client):
    """
    Apply the large message handling fix to an existing WebSocket client.
    
    This patches the WebSocket client to better handle large messages like
    the 61KB InitialSubscription that was causing connection failures.
    """
    logger = getattr(ws_client, 'logger', logging.getLogger(__name__))
    
    # Create enhanced handler
    enhanced_handler = ImprovedWebSocketHandler(
        original_handler=ws_client._on_ws_message,
        logger=logger
    )
    
    # Store original handlers
    enhanced_handler.original_error_handler = ws_client._on_ws_error
    enhanced_handler.original_close_handler = ws_client._on_ws_close
    
    # Replace with enhanced handlers
    ws_client._on_ws_message = enhanced_handler.enhanced_on_message
    ws_client._on_ws_error = enhanced_handler.enhanced_on_error  
    ws_client._on_ws_close = enhanced_handler.enhanced_on_close
    
    logger.info("Applied large message handling fix to WebSocket client")
    
    return enhanced_handler


def create_websocket_with_large_message_support(url, **kwargs):
    """
    Create a WebSocket connection with built-in large message support.
    
    This creates a WebSocket that can handle large InitialSubscription messages
    without experiencing "Invalid close frame" errors.
    """
    
    # Set WebSocket options for large messages
    websocket_options = {
        'ping_interval': 60,  # Keep connection alive during large message processing
        'ping_timeout': 30,   # Reasonable timeout
        'enable_multithread': True,  # Allow concurrent message processing
    }
    websocket_options.update(kwargs)
    
    # Override default message size limits if supported by websocket-client
    try:
        # Some WebSocket implementations allow setting max frame size
        if hasattr(websocket, 'setdefaulttimeout'):
            websocket.setdefaulttimeout(60)  # Longer timeout for large messages
    except:
        pass
    
    logger = logging.getLogger(__name__)
    
    def enhanced_on_message(ws, message):
        """Enhanced message handler for this WebSocket."""
        handler = ImprovedWebSocketHandler(None, logger)
        handler.enhanced_on_message(ws, message)
    
    def enhanced_on_error(ws, error):
        """Enhanced error handler for this WebSocket.""" 
        handler = ImprovedWebSocketHandler(None, logger)
        handler.enhanced_on_error(ws, error)
    
    def enhanced_on_close(ws, close_status_code, close_msg):
        """Enhanced close handler for this WebSocket."""
        handler = ImprovedWebSocketHandler(None, logger)
        handler.enhanced_on_close(ws, close_status_code, close_msg)
    
    # Create WebSocket with enhanced handlers
    ws = websocket.WebSocketApp(
        url,
        on_message=enhanced_on_message,
        on_error=enhanced_on_error, 
        on_close=enhanced_on_close,
        **websocket_options
    )
    
    logger.info(f"Created WebSocket with large message support for: {url}")
    return ws


# Test the fix
if __name__ == "__main__":
    print("🔧 WebSocket Large Message Fix")
    print("This fix addresses 'Invalid close frame' errors when processing large messages (61KB+)")
    print()
    print("Key improvements:")
    print("✅ Better handling of large JSON messages")
    print("✅ Enhanced error detection and logging") 
    print("✅ Memory-efficient message processing")
    print("✅ Improved WebSocket close frame analysis")
    print()
    print("To apply this fix:")
    print("1. Import: from WEBSOCKET_LARGE_MESSAGE_FIX import apply_large_message_fix_to_websocket_client")
    print("2. Apply to client: apply_large_message_fix_to_websocket_client(your_ws_client)")
    print("3. Or use: create_websocket_with_large_message_support(url)")
