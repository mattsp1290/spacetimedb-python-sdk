"""
Large Message Handler for SpacetimeDB

Handles messages larger than WebSocket frame limits by implementing
chunking/reassembly to prevent "Invalid close frame" errors.
"""

import math
import base64
import json
import asyncio
import threading
from typing import Dict, List, Optional, Union, Any, Callable
from dataclasses import dataclass
import logging
import uuid
import time

from .protocol import ClientMessage, ServerMessage


@dataclass
class ChunkInfo:
    """Information about a message chunk."""
    chunk_id: str
    total_size: int
    chunk_count: int
    sequence: int
    data: bytes
    timestamp: float


class LargeMessageHandler:
    """
    Handles messages larger than WebSocket frame limits.
    
    Provides automatic chunking for outgoing large messages and
    reassembly for incoming chunked messages.
    """
    
    # Conservative frame size limit (50KB) to avoid WebSocket issues
    MAX_FRAME_SIZE = 50 * 1024  # 50KB safe limit
    
    # Maximum total message size (10MB) for security
    MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Chunk timeout (30 seconds)
    CHUNK_TIMEOUT = 30.0
    
    def __init__(self, websocket_send_func: Callable[[Union[str, bytes]], None]):
        """
        Initialize large message handler.
        
        Args:
            websocket_send_func: Function to send data via WebSocket
        """
        self.websocket_send = websocket_send_func
        self.logger = logging.getLogger(__name__)
        
        # Track incoming chunks for reassembly
        self._incoming_chunks: Dict[str, Dict[int, ChunkInfo]] = {}
        self._chunk_metadata: Dict[str, dict] = {}
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Cleanup timer
        self._cleanup_timer: Optional[threading.Timer] = None
        self._start_cleanup_timer()
    
    def send_large_message(
        self, 
        message_data: Union[str, bytes], 
        message_type: str = "unknown",
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> None:
        """
        Send a potentially large message, chunking if necessary.
        
        Args:
            message_data: Message data to send
            message_type: Type of message for logging
            progress_callback: Optional callback for progress updates (event, current, total)
        """
        if isinstance(message_data, str):
            data_bytes = message_data.encode('utf-8')
        else:
            data_bytes = message_data
        
        message_size = len(data_bytes)
        
        if message_size > self.MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Message too large: {message_size} bytes exceeds maximum {self.MAX_MESSAGE_SIZE} bytes"
            )
        
        if message_size <= self.MAX_FRAME_SIZE:
            # Small message - send normally
            self.logger.debug(f"Sending {message_type} message ({message_size} bytes) normally")
            
            if progress_callback:
                progress_callback('start', message_size, 1)
            
            self.websocket_send(message_data)
            
            if progress_callback:
                progress_callback('complete', message_size, 1)
        else:
            # Large message - send in chunks
            self.logger.info(f"Sending large {message_type} message ({message_size} bytes) in chunks")
            self._send_chunked_message(data_bytes, message_type, progress_callback)
    
    def _send_chunked_message(
        self, 
        data: bytes, 
        message_type: str, 
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> None:
        """Send message in multiple chunks with progress tracking."""
        total_size = len(data)
        chunk_count = math.ceil(total_size / self.MAX_FRAME_SIZE)
        chunk_id = str(uuid.uuid4())
        
        self.logger.debug(f"Chunking {message_type} message: {total_size} bytes into {chunk_count} chunks")
        
        # Notify start of chunked message
        if progress_callback:
            progress_callback('start', total_size, chunk_count)
        
        # Send header with metadata
        header = {
            "ChunkedMessage": {
                "chunk_id": chunk_id,
                "total_size": total_size,
                "chunk_count": chunk_count,
                "message_type": message_type,
                "timestamp": time.time()
            }
        }
        
        header_json = json.dumps(header)
        self.logger.debug(f"Sending chunk header: {len(header_json)} bytes")
        self.websocket_send(header_json)
        
        # Send chunks
        for i in range(0, total_size, self.MAX_FRAME_SIZE):
            chunk_data = data[i:i + self.MAX_FRAME_SIZE]
            sequence = i // self.MAX_FRAME_SIZE
            
            chunk_message = {
                "MessageChunk": {
                    "chunk_id": chunk_id,
                    "sequence": sequence,
                    "data": base64.b64encode(chunk_data).decode('utf-8'),
                    "size": len(chunk_data)
                }
            }
            
            chunk_json = json.dumps(chunk_message)
            self.logger.debug(f"Sending chunk {sequence + 1}/{chunk_count}: {len(chunk_data)} bytes")
            self.websocket_send(chunk_json)
            
            # Progress update for each chunk
            if progress_callback:
                progress_callback('chunk', sequence + 1, chunk_count)
        
        # Notify completion
        if progress_callback:
            progress_callback('complete', total_size, chunk_count)
    
    def handle_incoming_message(
        self, 
        message_data: Union[str, bytes], 
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Optional[bytes]:
        """
        Handle incoming message, reassembling chunks if necessary.
        
        Args:
            message_data: Received message data
            progress_callback: Optional callback for progress updates
            
        Returns:
            Complete message if ready, None if more chunks needed
        """
        try:
            if isinstance(message_data, bytes):
                message_str = message_data.decode('utf-8')
            else:
                message_str = message_data
            
            message = json.loads(message_str)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not a JSON message, return as-is
            if isinstance(message_data, str):
                return message_data.encode('utf-8')
            return message_data
        
        # Check for chunk header
        if "ChunkedMessage" in message:
            return self._handle_chunk_header(message["ChunkedMessage"], progress_callback)
        
        # Check for chunk data
        elif "MessageChunk" in message:
            return self._handle_chunk_data(message["MessageChunk"], progress_callback)
        
        # Regular message, return as-is
        else:
            return message_str.encode('utf-8')
    
    def _handle_chunk_header(
        self, 
        header: dict, 
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> None:
        """Handle chunked message header."""
        chunk_id = header["chunk_id"]
        total_size = header["total_size"]
        chunk_count = header["chunk_count"]
        message_type = header.get("message_type", "unknown")
        
        if total_size > self.MAX_MESSAGE_SIZE:
            self.logger.error(f"Rejecting oversized chunked message: {total_size} bytes")
            return None
        
        with self._lock:
            self._chunk_metadata[chunk_id] = {
                "total_size": total_size,
                "chunk_count": chunk_count,
                "message_type": message_type,
                "start_time": time.time(),
                "received_chunks": 0
            }
            self._incoming_chunks[chunk_id] = {}
        
        self.logger.debug(f"Started receiving chunked {message_type} message: {total_size} bytes in {chunk_count} chunks")
        
        # Notify start of chunked message reception
        if progress_callback:
            progress_callback('start', total_size, chunk_count)
        
        return None
    
    def _handle_chunk_data(
        self, 
        chunk_data: dict, 
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Optional[bytes]:
        """Handle individual chunk data."""
        chunk_id = chunk_data["chunk_id"]
        sequence = chunk_data["sequence"]
        data_b64 = chunk_data["data"]
        chunk_size = chunk_data.get("size", 0)
        
        with self._lock:
            # Check if we have metadata for this chunk
            if chunk_id not in self._chunk_metadata:
                self.logger.warning(f"Received chunk without header: {chunk_id}")
                return None
            
            metadata = self._chunk_metadata[chunk_id]
            
            # Decode chunk data
            try:
                chunk_bytes = base64.b64decode(data_b64)
            except Exception as e:
                self.logger.error(f"Failed to decode chunk data: {e}")
                return None
            
            # Validate chunk size
            if len(chunk_bytes) != chunk_size and chunk_size > 0:
                self.logger.warning(f"Chunk size mismatch: expected {chunk_size}, got {len(chunk_bytes)}")
            
            # Store chunk
            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                total_size=metadata["total_size"],
                chunk_count=metadata["chunk_count"],
                sequence=sequence,
                data=chunk_bytes,
                timestamp=time.time()
            )
            
            self._incoming_chunks[chunk_id][sequence] = chunk_info
            metadata["received_chunks"] += 1
            
            self.logger.debug(
                f"Received chunk {sequence}: {len(chunk_bytes)} bytes "
                f"({metadata['received_chunks']}/{metadata['chunk_count']})"
            )
            
            # Progress update for received chunk
            if progress_callback:
                progress_callback('chunk', metadata['received_chunks'], metadata['chunk_count'])
            
            # Check if all chunks received
            if metadata["received_chunks"] == metadata["chunk_count"]:
                complete_message = self._reassemble_message(chunk_id)
                
                # Notify completion
                if progress_callback:
                    progress_callback('complete', metadata['total_size'], metadata['chunk_count'])
                
                return complete_message
            
            return None
    
    def _reassemble_message(self, chunk_id: str) -> bytes:
        """Reassemble complete message from chunks."""
        with self._lock:
            if chunk_id not in self._incoming_chunks:
                self.logger.error(f"Cannot reassemble message: chunk_id {chunk_id} not found")
                return b""
            
            chunks = self._incoming_chunks[chunk_id]
            metadata = self._chunk_metadata[chunk_id]
            
            # Sort chunks by sequence
            sorted_sequences = sorted(chunks.keys())
            
            # Reassemble data
            reassembled = b""
            for sequence in sorted_sequences:
                chunk_info = chunks[sequence]
                reassembled += chunk_info.data
            
            # Validate total size
            if len(reassembled) != metadata["total_size"]:
                self.logger.error(
                    f"Reassembled message size mismatch: expected {metadata['total_size']}, "
                    f"got {len(reassembled)}"
                )
            
            # Clean up
            del self._incoming_chunks[chunk_id]
            del self._chunk_metadata[chunk_id]
            
            message_type = metadata.get("message_type", "unknown")
            self.logger.info(f"Successfully reassembled {message_type} message: {len(reassembled)} bytes")
            
            return reassembled
    
    def _start_cleanup_timer(self) -> None:
        """Start timer for cleaning up stale chunks."""
        def cleanup():
            self._cleanup_stale_chunks()
            self._start_cleanup_timer()  # Reschedule
        
        self._cleanup_timer = threading.Timer(30.0, cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()
    
    def _cleanup_stale_chunks(self) -> None:
        """Clean up chunks that have timed out."""
        current_time = time.time()
        stale_chunk_ids = []
        
        with self._lock:
            for chunk_id, metadata in self._chunk_metadata.items():
                start_time = metadata.get("start_time", current_time)
                if current_time - start_time > self.CHUNK_TIMEOUT:
                    stale_chunk_ids.append(chunk_id)
            
            for chunk_id in stale_chunk_ids:
                self.logger.warning(f"Cleaning up stale chunks for message {chunk_id}")
                if chunk_id in self._incoming_chunks:
                    del self._incoming_chunks[chunk_id]
                if chunk_id in self._chunk_metadata:
                    del self._chunk_metadata[chunk_id]
    
    def get_chunk_stats(self) -> dict:
        """Get statistics about chunk handling."""
        with self._lock:
            return {
                "active_chunk_groups": len(self._chunk_metadata),
                "total_chunks_in_memory": sum(len(chunks) for chunks in self._incoming_chunks.values()),
                "max_frame_size": self.MAX_FRAME_SIZE,
                "max_message_size": self.MAX_MESSAGE_SIZE
            }
    
    def shutdown(self) -> None:
        """Shutdown the handler and clean up resources."""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        
        with self._lock:
            self._incoming_chunks.clear()
            self._chunk_metadata.clear()


class AsyncLargeMessageHandler:
    """
    Async version of LargeMessageHandler for use with asyncio.
    """
    
    MAX_FRAME_SIZE = 50 * 1024  # 50KB
    MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
    CHUNK_TIMEOUT = 30.0
    
    def __init__(self, websocket_send_func: Callable[[Union[str, bytes]], asyncio.Task]):
        """
        Initialize async large message handler.
        
        Args:
            websocket_send_func: Async function to send data via WebSocket
        """
        self.websocket_send = websocket_send_func
        self.logger = logging.getLogger(__name__)
        
        # Track incoming chunks for reassembly
        self._incoming_chunks: Dict[str, Dict[int, ChunkInfo]] = {}
        self._chunk_metadata: Dict[str, dict] = {}
        
        # Async lock
        self._lock = asyncio.Lock()
    
    async def send_large_message(self, message_data: Union[str, bytes], message_type: str = "unknown") -> None:
        """
        Send a potentially large message asynchronously, chunking if necessary.
        
        Args:
            message_data: Message data to send
            message_type: Type of message for logging
        """
        if isinstance(message_data, str):
            data_bytes = message_data.encode('utf-8')
        else:
            data_bytes = message_data
        
        message_size = len(data_bytes)
        
        if message_size > self.MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Message too large: {message_size} bytes exceeds maximum {self.MAX_MESSAGE_SIZE} bytes"
            )
        
        if message_size <= self.MAX_FRAME_SIZE:
            # Small message - send normally
            self.logger.debug(f"Sending {message_type} message ({message_size} bytes) normally")
            await self.websocket_send(message_data)
        else:
            # Large message - send in chunks
            self.logger.info(f"Sending large {message_type} message ({message_size} bytes) in chunks")
            await self._send_chunked_message(data_bytes, message_type)
    
    async def _send_chunked_message(self, data: bytes, message_type: str) -> None:
        """Send message in multiple chunks asynchronously."""
        total_size = len(data)
        chunk_count = math.ceil(total_size / self.MAX_FRAME_SIZE)
        chunk_id = str(uuid.uuid4())
        
        self.logger.debug(f"Chunking {message_type} message: {total_size} bytes into {chunk_count} chunks")
        
        # Send header
        header = {
            "ChunkedMessage": {
                "chunk_id": chunk_id,
                "total_size": total_size,
                "chunk_count": chunk_count,
                "message_type": message_type,
                "timestamp": time.time()
            }
        }
        
        await self.websocket_send(json.dumps(header))
        
        # Send chunks
        for i in range(0, total_size, self.MAX_FRAME_SIZE):
            chunk_data = data[i:i + self.MAX_FRAME_SIZE]
            sequence = i // self.MAX_FRAME_SIZE
            
            chunk_message = {
                "MessageChunk": {
                    "chunk_id": chunk_id,
                    "sequence": sequence,
                    "data": base64.b64encode(chunk_data).decode('utf-8'),
                    "size": len(chunk_data)
                }
            }
            
            await self.websocket_send(json.dumps(chunk_message))
            self.logger.debug(f"Sent chunk {sequence + 1}/{chunk_count}: {len(chunk_data)} bytes")
    
    async def handle_incoming_message(self, message_data: Union[str, bytes]) -> Optional[bytes]:
        """
        Handle incoming message asynchronously, reassembling chunks if necessary.
        
        Args:
            message_data: Received message data
            
        Returns:
            Complete message if ready, None if more chunks needed
        """
        try:
            if isinstance(message_data, bytes):
                message_str = message_data.decode('utf-8')
            else:
                message_str = message_data
            
            message = json.loads(message_str)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not a JSON message, return as-is
            if isinstance(message_data, str):
                return message_data.encode('utf-8')
            return message_data
        
        # Check for chunk header
        if "ChunkedMessage" in message:
            await self._handle_chunk_header(message["ChunkedMessage"])
            return None
        
        # Check for chunk data
        elif "MessageChunk" in message:
            return await self._handle_chunk_data(message["MessageChunk"])
        
        # Regular message, return as-is
        else:
            return message_str.encode('utf-8')
    
    async def _handle_chunk_header(self, header: dict) -> None:
        """Handle chunked message header asynchronously."""
        chunk_id = header["chunk_id"]
        total_size = header["total_size"]
        chunk_count = header["chunk_count"]
        message_type = header.get("message_type", "unknown")
        
        if total_size > self.MAX_MESSAGE_SIZE:
            self.logger.error(f"Rejecting oversized chunked message: {total_size} bytes")
            return
        
        async with self._lock:
            self._chunk_metadata[chunk_id] = {
                "total_size": total_size,
                "chunk_count": chunk_count,
                "message_type": message_type,
                "start_time": time.time(),
                "received_chunks": 0
            }
            self._incoming_chunks[chunk_id] = {}
        
        self.logger.debug(f"Started receiving chunked {message_type} message: {total_size} bytes in {chunk_count} chunks")
    
    async def _handle_chunk_data(self, chunk_data: dict) -> Optional[bytes]:
        """Handle individual chunk data asynchronously."""
        chunk_id = chunk_data["chunk_id"]
        sequence = chunk_data["sequence"]
        data_b64 = chunk_data["data"]
        chunk_size = chunk_data.get("size", 0)
        
        async with self._lock:
            # Check if we have metadata for this chunk
            if chunk_id not in self._chunk_metadata:
                self.logger.warning(f"Received chunk without header: {chunk_id}")
                return None
            
            metadata = self._chunk_metadata[chunk_id]
            
            # Decode chunk data
            try:
                chunk_bytes = base64.b64decode(data_b64)
            except Exception as e:
                self.logger.error(f"Failed to decode chunk data: {e}")
                return None
            
            # Store chunk
            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                total_size=metadata["total_size"],
                chunk_count=metadata["chunk_count"],
                sequence=sequence,
                data=chunk_bytes,
                timestamp=time.time()
            )
            
            self._incoming_chunks[chunk_id][sequence] = chunk_info
            metadata["received_chunks"] += 1
            
            self.logger.debug(
                f"Received chunk {sequence}: {len(chunk_bytes)} bytes "
                f"({metadata['received_chunks']}/{metadata['chunk_count']})"
            )
            
            # Check if all chunks received
            if metadata["received_chunks"] == metadata["chunk_count"]:
                return await self._reassemble_message(chunk_id)
            
            return None
    
    async def _reassemble_message(self, chunk_id: str) -> bytes:
        """Reassemble complete message from chunks asynchronously."""
        async with self._lock:
            if chunk_id not in self._incoming_chunks:
                self.logger.error(f"Cannot reassemble message: chunk_id {chunk_id} not found")
                return b""
            
            chunks = self._incoming_chunks[chunk_id]
            metadata = self._chunk_metadata[chunk_id]
            
            # Sort chunks by sequence
            sorted_sequences = sorted(chunks.keys())
            
            # Reassemble data
            reassembled = b""
            for sequence in sorted_sequences:
                chunk_info = chunks[sequence]
                reassembled += chunk_info.data
            
            # Clean up
            del self._incoming_chunks[chunk_id]
            del self._chunk_metadata[chunk_id]
            
            message_type = metadata.get("message_type", "unknown")
            self.logger.info(f"Successfully reassembled {message_type} message: {len(reassembled)} bytes")
            
            return reassembled