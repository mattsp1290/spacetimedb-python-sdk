import websocket
import threading
import base64
import binascii
import logging
import re

from .exceptions import (
    WebSocketHandshakeError,
    DatabaseNotFoundError,
    AuthenticationError,
    ProtocolMismatchError,
    ConnectionTimeoutError,
    SpacetimeDBConnectionError
)
from .connection_diagnostics import ConnectionDiagnostics


class WebSocketClient:
    def __init__(self, protocol, on_connect=None, on_close=None, on_error=None, on_message=None, client_address=None):
        self._on_connect = on_connect
        self._on_close = on_close
        self._on_error = on_error
        self._on_message = on_message

        self.protocol = protocol
        self.ws = None
        self.message_thread = None
        self.host = None
        self.name_or_address = None
        self.is_connected = False
        self.client_address = client_address
        self.connection_url = None
        
        # Connection diagnostics
        self.diagnostics = ConnectionDiagnostics()
        self.enable_preflight_checks = True
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.WebSocketClient_{id(self)}")

    def connect(self, auth, host, name_or_address, ssl_enabled, db_identity=None):
        # Run preflight checks if enabled
        if self.enable_preflight_checks:
            try:
                self.logger.info("Running preflight checks...")
                checks = self.diagnostics.run_preflight_checks(
                    host=host,
                    database=name_or_address,
                    raise_on_failure=True
                )
                self.logger.info("Preflight checks passed")
            except Exception as e:
                self.logger.error(f"Preflight checks failed: {e}")
                if self._on_error:
                    self._on_error(e)
                raise
        
        protocol = "wss" if ssl_enabled else "ws"
        # For v1.1.2, always use name_or_address in the URL path
        url = f"{protocol}://{host}/v1/database/{name_or_address}/subscribe"
        
        # Build query parameters
        query_params = []
        if db_identity:
            query_params.append(f"db_identity={db_identity}")
        if self.client_address is not None:
            query_params.append(f"client_address={self.client_address}")
        
        # Add query parameters to URL if any exist
        if query_params:
            url += "?" + "&".join(query_params)
        
        # Store URL for error diagnostics
        self.connection_url = url

        self.host = host
        self.db_identity = db_identity
        self.name_or_address = name_or_address

        ws_header = None
        if auth:
            token_bytes = bytes(f"token:{auth}", "utf-8")
            base64_str = base64.b64encode(token_bytes).decode("utf-8")
            headers = {
                "Authorization": f"Basic {base64_str}",
            }
        else:
            headers = None

        self.ws = websocket.WebSocketApp(url,
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close, 
                                         header=headers, 
                                         subprotocols=[self.protocol])

        self.message_thread = threading.Thread(target=self.ws.run_forever)
        self.message_thread.start()

    def decode_hex_string(hex_string):
        try:
            return binascii.unhexlify(hex_string)
        except binascii.Error:
            return None

    def send(self, data):
        if not self.is_connected:
            print("[send] Not connected")

        self.ws.send(data)

    def close(self):
        self.ws.close()

    def on_open(self, ws):
        self.is_connected = True
        if self._on_connect:
            self._on_connect()

    def on_message(self, ws, message):
        # Process incoming message on a separate thread here
        t = threading.Thread(target=self.process_message, args=(message,))
        t.start()

    def process_message(self, message):
        if self._on_message:
            self._on_message(message)
        pass

    def on_error(self, ws, error):
        """WebSocket error occurred with enhanced error handling."""
        self.logger.error(f"WebSocket error: {error}")
        
        # Try to parse handshake errors
        try:
            error_str = str(error)
            
            # Check for handshake status codes
            if "Handshake status" in error_str:
                # Extract status code and message
                status_match = re.search(r"Handshake status (\d+)\s*(.*)?", error_str)
                if status_match:
                    status_code = int(status_match.group(1))
                    status_message = status_match.group(2) or "Unknown"
                    
                    # Extract server headers if available
                    headers = {}
                    if hasattr(error, 'headers'):
                        headers = dict(error.headers)
                    elif "spacetime-identity" in error_str:
                        # Try to extract headers from error string
                        identity_match = re.search(r"spacetime-identity:\s*([a-fA-F0-9]+)", error_str)
                        if identity_match:
                            headers["spacetime-identity"] = identity_match.group(1)
                        
                        token_match = re.search(r"spacetime-identity-token:\s*([\w.-]+)", error_str)
                        if token_match:
                            headers["spacetime-identity-token"] = token_match.group(1)
                    
                    # Create appropriate exception based on status code
                    if status_code == 404:
                        database_name = self.name_or_address or "unknown"
                        error = DatabaseNotFoundError(
                            database_name=database_name,
                            status_code=status_code,
                            server_message=status_message,
                            diagnostic_info={
                                "url": self.connection_url,
                                "protocol": self.protocol,
                                "headers": headers
                            }
                        )
                    elif status_code == 401 or status_code == 403:
                        error = AuthenticationError(
                            reason=f"HTTP {status_code}: {status_message}",
                            auth_method="Basic" if self.host else "None",
                            status_code=status_code
                        )
                    else:
                        error = WebSocketHandshakeError(
                            status_code=status_code,
                            status_message=status_message,
                            url=self.connection_url or "",
                            headers=headers,
                            diagnostic_info={
                                "protocol": self.protocol,
                                "database": self.name_or_address
                            }
                        )
            
            # Check for protocol mismatch
            elif "protocol" in error_str.lower() and ("mismatch" in error_str.lower() or "rejected" in error_str.lower()):
                error = ProtocolMismatchError(
                    requested_protocol=self.protocol,
                    server_message=error_str
                )
            
            # Check for timeout
            elif "timeout" in error_str.lower():
                error = ConnectionTimeoutError(
                    operation="WebSocket handshake",
                    timeout_seconds=10.0,
                    retry_count=0
                )
            
            # For other errors, use diagnostics
            else:
                # Run diagnostics to provide helpful error message
                try:
                    self.diagnostics.diagnose_connection_error(
                        error,
                        self.connection_url or "",
                        self.name_or_address
                    )
                except Exception as diag_error:
                    # If diagnostics raise an exception, use that
                    error = diag_error
                    
        except Exception as parse_error:
            self.logger.debug(f"Failed to parse WebSocket error: {parse_error}")
            # Keep original error if parsing fails
        
        if self._on_error:
            self._on_error(error)

    def on_close(self, ws, status_code, close_msg):
        if self._on_close:
            self._on_close(close_msg)
