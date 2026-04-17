"""TCP client with length-prefix framing for communicating with Godot."""

from __future__ import annotations

import json
import socket
import struct
import threading
from typing import Any, Dict

from .types import (
    CommandError,
    ConnectionLostError,
    NodeNotFoundError,
)


class GodotClient:
    """Blocking TCP client that speaks the godot-e2e wire protocol.

    The wire format is simple length-prefixed JSON:
        [4-byte big-endian uint32 payload length][UTF-8 JSON payload]
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 6008) -> None:
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._recv_buffer: bytes = b""
        self._next_id: int = 1
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 10.0) -> None:
        """Connect to Godot's AutomationServer."""
        # Close any previous socket to avoid leaking on retry.
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        self._recv_buffer = b""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect((self.host, self.port))

    def close(self) -> None:
        """Close the TCP connection."""
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._recv_buffer = b""

    # ------------------------------------------------------------------
    # Command API
    # ------------------------------------------------------------------

    def send_command(self, action: str, **params: Any) -> Dict[str, Any]:
        """Send a command and block until the matching response arrives.

        Returns the parsed response dict with values deserialized into
        Python types (Vector2, Color, etc.) where applicable.

        Raises:
            NodeNotFoundError: if the server reports a missing node.
            CommandError: for any other server-side error.
            ConnectionLostError: if the connection drops.
        """
        with self._lock:
            cmd_id = self._next_id
            self._next_id += 1

            msg: Dict[str, Any] = {"id": cmd_id, "action": action, **params}
            payload = json.dumps(msg).encode("utf-8")
            header = struct.pack(">I", len(payload))

            try:
                self._sock.sendall(header + payload)
            except (OSError, AttributeError) as exc:
                raise ConnectionLostError(f"Failed to send command: {exc}") from exc

            response = self._read_response()

            if "error" in response:
                error_code = response["error"]
                error_msg = response.get("message", error_code)
                if "not found" in error_msg.lower() or "not found" in error_code.lower():
                    raise NodeNotFoundError(error_msg)
                raise CommandError(error_msg)

            return response

    def hello(self, token: str) -> Dict[str, Any]:
        """Send the handshake. Must be the first command after connecting."""
        return self.send_command("hello", token=token, protocol_version=1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_response(self) -> Dict[str, Any]:
        """Read one length-prefixed JSON message from the socket."""
        while True:
            # Try to extract a complete message from the buffer.
            if len(self._recv_buffer) >= 4:
                payload_len = struct.unpack(">I", self._recv_buffer[:4])[0]
                total = 4 + payload_len
                if len(self._recv_buffer) >= total:
                    payload = self._recv_buffer[4:total]
                    self._recv_buffer = self._recv_buffer[total:]
                    return json.loads(payload.decode("utf-8"))

            # Need more data from the network.
            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionLostError("Connection closed by Godot")
                self._recv_buffer += chunk
            except socket.timeout as exc:
                raise ConnectionLostError(f"Connection timed out: {exc}") from exc
            except OSError as exc:
                raise ConnectionLostError(f"Connection lost: {exc}") from exc
