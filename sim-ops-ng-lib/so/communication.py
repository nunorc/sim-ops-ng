"""Socket communication between simulator and API: newline-delimited JSON, with a write lock per socket."""

import json
import logging
import socket
import threading
from typing import Callable, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

# a peer that sends this much without a newline is broken; drop it rather than buffer forever
MAX_MESSAGE_BYTES = 16 * 1024 * 1024


def convert_to_serializable(obj: Any) -> Any:
    """Recursively convert enums and other non-serializable types to JSON-serializable format"""
    if isinstance(obj, Enum):
        # Convert enum to its value
        return obj.value
    elif isinstance(obj, dict):
        # Recursively convert dict values
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        # Recursively convert list/tuple items
        return [convert_to_serializable(item) for item in obj]
    else:
        # Return as-is for basic types
        return obj


def encode_message(message: Dict[str, Any]) -> bytes:
    """One message as a line of compact JSON (json.dumps never emits a raw newline)."""
    return (json.dumps(message) + "\n").encode()


def iter_messages(buffer: bytes) -> tuple[list[Dict[str, Any]], bytes]:
    """Split complete lines off `buffer`; returns (decoded messages, remaining partial line)."""
    *lines, rest = buffer.split(b"\n")
    messages = []
    for line in lines:
        if not line.strip():
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError as e:
            logger.warning("Dropping malformed message: %s", e)
    return messages, rest


class SocketServer:
    """Socket server for SimOps to handle API requests and broadcast state"""

    # a client that can't take a message within this time is dropped, so it can't stall the sim's broadcasts
    SEND_TIMEOUT = 5.0

    def __init__(self, host: str = "127.0.0.1", port: int = 5555):
        self.host = host
        self.port = port
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # connected client -> its write lock
        self._clients: dict[socket.socket, threading.Lock] = {}
        self._clients_lock = threading.Lock()

        # Command handlers
        self._command_handlers: Dict[str, Callable] = {}
        # called on every subscribe, so the caller can push a state snapshot instead of making it wait for the next tick
        self._on_subscribe: Optional[Callable] = None

    def register_handler(self, command: str, handler: Callable):
        """Register a handler for a specific command"""
        self._command_handlers[command] = handler

    def set_on_subscribe(self, callback: Callable):
        """Register a callback invoked (no args) each time a client subscribes"""
        self._on_subscribe = callback

    def start(self):
        """Start the socket server"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the socket server"""
        self._running = False

        with self._clients_lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            self._close(client)

        if self._server_socket:
            self._close(self._server_socket)

        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    @staticmethod
    def _close(sock: socket.socket):
        try:
            sock.close()
        except OSError:
            pass

    def _drop_client(self, client_socket: socket.socket):
        with self._clients_lock:
            self._clients.pop(client_socket, None)
        self._close(client_socket)

    def _run_server(self):
        """Main server loop"""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)

            while self._running:
                try:
                    client_socket, addr = self._server_socket.accept()
                    client_socket.settimeout(self.SEND_TIMEOUT)
                    with self._clients_lock:
                        self._clients[client_socket] = threading.Lock()

                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        logger.error("Server error: %s", e)
        except Exception as e:
            logger.error("Socket server error: %s", e)
        finally:
            if self._server_socket:
                self._close(self._server_socket)

    def _handle_client(self, client_socket: socket.socket, _addr):
        """Handle individual client connection"""
        buffer = b""
        try:
            while self._running:
                try:
                    data = client_socket.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break

                messages, buffer = iter_messages(buffer + data)
                for message in messages:
                    if message.get('type') == 'command':
                        # a handler can block for seconds and the API uses one connection, so run each on its own thread
                        threading.Thread(target=self._process_message, args=(message, client_socket),
                                         daemon=True).start()
                    else:
                        self._process_message(message, client_socket)

                if len(buffer) > MAX_MESSAGE_BYTES:
                    logger.error("Client sent %d bytes without a message boundary, dropping it", len(buffer))
                    break
        except OSError as e:
            if self._running:
                logger.info("Client disconnected: %s", e)
        except Exception:
            logger.exception("Client handler error")
        finally:
            self._drop_client(client_socket)

    def _send(self, client_socket: socket.socket, payload: bytes) -> bool:
        """Send one encoded message to a client; a client that fails a send is dropped."""
        with self._clients_lock:
            lock = self._clients.get(client_socket)
        if lock is None:
            return False
        try:
            with lock:
                client_socket.sendall(payload)
            return True
        except OSError as e:
            # a timed-out sendall may have written a partial message, breaking framing: the connection can't be reused
            logger.warning("Send to client failed, dropping it: %s", e)
            self._drop_client(client_socket)
            return False

    def _process_message(self, message: Dict[str, Any], client_socket: socket.socket):
        """Process incoming message"""
        msg_type = message.get('type')

        if msg_type == 'command':
            command = message.get('command')
            params = message.get('params', {})
            cmd_id = message.get('id')  # Get command ID for matching

            if command in self._command_handlers:
                try:
                    result = self._command_handlers[command](params)
                    # Convert any enums in the result to serializable format
                    serializable_result = convert_to_serializable(result)
                    response = {
                        'type': 'response', 'id': cmd_id, 'command': command, 'success': True,
                        'data': serializable_result
                    }
                except Exception as e:
                    response = {
                        'type': 'response', 'id': cmd_id, 'command': command, 'success': False, 'error': str(e)
                    }
            else:
                response = {
                    'type': 'response', 'id': cmd_id, 'command': command, 'success': False,
                    'error': 'Unknown command'
                }

            self._send(client_socket, encode_message(response))

        elif msg_type == 'subscribe':
            # every accepted client already receives broadcasts; subscribing asks for a snapshot now
            if self._on_subscribe:
                try:
                    self._on_subscribe()
                except Exception as e:
                    logger.error("on_subscribe callback error: %s", e)

    def broadcast(self, data: Dict[str, Any]):
        """Broadcast state to all connected clients"""
        # Convert enums and other non-serializable types to JSON-serializable format
        payload = encode_message(convert_to_serializable(data))

        with self._clients_lock:
            clients = list(self._clients)
        for client in clients:
            self._send(client, payload)


class SocketClient:
    """Socket client for SimOpsAPI; `start()` keeps it connected (and subscribed) in the background."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5555, timeout: float = 5.0,
                 retry_interval: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retry_interval = retry_interval
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._listener_thread: Optional[threading.Thread] = None
        self._broadcast_handlers: Dict[str, Callable] = {}

        # serialises connect/reconnect between the supervisor and send_command
        self._connect_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._supervisor_thread: Optional[threading.Thread] = None
        # log the first failed connect attempt of an outage, not every retry
        self._connect_failing = False

        # Response handling for commands
        self._pending_commands: Dict[int, Dict] = {}
        self._command_counter = 0
        self._command_lock = threading.Lock()

    def start(self):
        """Connect now if possible, and keep reconnecting in the background."""
        self._stop_event.clear()
        self.connect()
        if self._supervisor_thread is None or not self._supervisor_thread.is_alive():
            self._supervisor_thread = threading.Thread(target=self._supervise, daemon=True)
            self._supervisor_thread.start()

    def _supervise(self):
        while not self._stop_event.wait(self.retry_interval):
            if not self._connected:
                self.connect()

    def connect(self) -> bool:
        """Connect to the socket server, replacing a dead connection (no-op if still connected)"""
        with self._connect_lock:
            if self._connected:
                return True
            # drop a dead connection first; its listener exits once it is no longer self._socket
            if self._socket is not None:
                self._shutdown(self._socket)
                self._socket = None
                self._fail_pending('Connection to sim lost')
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
            except OSError as e:
                if sock is not None:
                    sock.close()
                if not self._connect_failing:
                    logger.warning("Cannot connect to sim at %s:%s (%s), retrying", self.host, self.port, e)
                    self._connect_failing = True
                return False

            self._socket = sock
            self._connected = True
            if self._connect_failing:
                logger.info("Connected to sim at %s:%s", self.host, self.port)
                self._connect_failing = False

            # Start listener thread before subscribing, the server answers with a snapshot
            self._listener_thread = threading.Thread(target=self._listen, args=(sock,), daemon=True)
            self._listener_thread.start()

            # Subscribe to broadcasts
            self.send_message({'type': 'subscribe'})
            return self._connected

    @staticmethod
    def _shutdown(sock: socket.socket):
        try:
            # unblocks a listener's recv()
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def disconnect(self):
        """Disconnect from the socket server and stop reconnecting"""
        self._stop_event.set()
        with self._connect_lock:
            sock, self._socket = self._socket, None
            self._connected = False
        if sock:
            self._shutdown(sock)
        if self._listener_thread:
            self._listener_thread.join(timeout=2)
        self._fail_pending('Disconnected')
        if self._supervisor_thread:
            self._supervisor_thread.join(timeout=5)
            self._supervisor_thread = None

    def is_connected(self) -> bool:
        """Check if connected to server"""
        return self._connected

    def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to the server"""
        sock = self._socket
        if not self._connected or not sock:
            return False

        try:
            with self._send_lock:
                sock.sendall(encode_message(message))
            return True
        except OSError as e:
            logger.warning("Send error: %s", e)
            self._connected = False
            return False

    def send_command(self, command: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a command and wait for the server's response (with 'success' and other fields)."""
        if not self._connected or not self._socket:
            if not self.connect():
                return {'success': False, 'error': 'Not connected'}

        # Generate unique command ID and register the pending response
        event = threading.Event()
        with self._command_lock:
            self._command_counter += 1
            cmd_id = self._command_counter
            self._pending_commands[cmd_id] = {'event': event, 'response': None}

        message = {
            'type': 'command',
            'id': cmd_id,
            'command': command,
            'params': params or {}
        }

        if not self.send_message(message):
            with self._command_lock:
                del self._pending_commands[cmd_id]
            return {'success': False, 'error': 'Failed to send message'}

        # Wait for response with timeout
        answered = event.wait(timeout=self.timeout)
        with self._command_lock:
            pending = self._pending_commands.pop(cmd_id)
        if not answered:
            return {'success': False, 'error': 'Command timeout'}
        return pending.get('response') or {'success': False, 'error': 'No response'}

    def _fail_pending(self, error: str):
        """Answer every outstanding command with an error instead of letting it time out."""
        with self._command_lock:
            for pending in self._pending_commands.values():
                if not pending['event'].is_set():
                    pending['response'] = {'success': False, 'error': error}
                    pending['event'].set()

    def register_broadcast_handler(self, event_type: str, handler: Callable):
        """Register a handler for broadcast events"""
        self._broadcast_handlers[event_type] = handler

    def _handle_message(self, message: Dict[str, Any]):
        # Handle state broadcasts
        if message.get('type') == 'state':
            if 'state' in self._broadcast_handlers:
                self._broadcast_handlers['state'](message)

        # Handle command responses
        elif message.get('type') == 'response':
            cmd_id = message.get('id')
            if cmd_id is not None:
                with self._command_lock:
                    if cmd_id in self._pending_commands:
                        self._pending_commands[cmd_id]['response'] = message
                        self._pending_commands[cmd_id]['event'].set()

    def _listen(self, sock: socket.socket):
        """Listen for broadcasts and responses on `sock` until it closes or is replaced"""
        buffer = b""

        while sock is self._socket:
            try:
                data = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError as e:
                if sock is self._socket:
                    logger.warning("Listen error: %s", e)
                break
            if not data:
                break

            messages, buffer = iter_messages(buffer + data)
            for message in messages:
                try:
                    self._handle_message(message)
                except Exception:
                    logger.exception("Error handling message from sim")

            if len(buffer) > MAX_MESSAGE_BYTES:
                logger.error("Sim sent %d bytes without a message boundary, reconnecting", len(buffer))
                break

        # only the listener of the current socket may mark the client disconnected
        if sock is self._socket:
            logger.warning("Connection to sim at %s:%s lost", self.host, self.port)
            self._connected = False
            self._fail_pending('Connection to sim lost')
