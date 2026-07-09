"""TCP client with length-prefix framing for communicating with Godot."""

from __future__ import annotations

import json
import socket
import struct
import threading
from typing import Any, Callable, Dict, List, Optional

from .flood import EngineErrorFloodDetector
from .types import (
    CommandError,
    ConnectionLostError,
    EngineErrorFloodError,
    LogEntry,
    NodeNotFoundError,
    parse_log_entries,
)


class GodotClient:
    """Blocking TCP client that speaks the godot-e2e wire protocol.

    The wire format is simple length-prefixed JSON:
        [4-byte big-endian uint32 payload length][UTF-8 JSON payload]
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6008,
        collected_logs_limit: Optional[int] = 10_000,
    ) -> None:
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._recv_buffer: bytes = b""
        self._next_id: int = 1
        self._lock = threading.Lock()
        # Engine log capture state. ``last_logs`` is the slice from the most
        # recent response; ``collected_logs`` accumulates across the whole
        # test (the pytest plugin resets it per-test).
        self.last_logs: List[LogEntry] = []
        self.collected_logs: List[LogEntry] = []
        # Safety cap on the test-level accumulator so a sustained error flood
        # can't grow ``collected_logs`` without bound (mirrors the addon-side
        # ring buffer). When the cap is exceeded, oldest entries are discarded
        # and counted in ``collected_logs_dropped``. ``None`` disables the cap.
        self._collected_logs_limit = collected_logs_limit
        self.collected_logs_dropped = 0
        # Engine-error-flood detection, armed by the launcher via
        # ``enable_flood_detection``. Off by default so a bare client (e.g. in
        # unit tests) behaves exactly as before.
        self._flood_detector: Optional[EngineErrorFloodDetector] = None
        self._on_flood: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------
    # Log capture API
    # ------------------------------------------------------------------

    def reset_collected_logs(self) -> None:
        """Discard all entries in ``collected_logs``. Called by the pytest
        plugin at the start of each test so logs don't leak across tests."""
        self.collected_logs = []
        self.last_logs = []
        self.collected_logs_dropped = 0
        if self._flood_detector is not None:
            self._flood_detector.reset()

    # ------------------------------------------------------------------
    # Flood detection
    # ------------------------------------------------------------------

    def enable_flood_detection(
        self,
        detector: EngineErrorFloodDetector,
        on_flood: Optional[Callable[[], None]] = None,
    ) -> None:
        """Arm engine-error-flood detection for this client.

        ``detector`` is fed every response's log delta inside
        :meth:`send_command`. When it trips, ``on_flood`` (if given) is invoked
        to stop the flood at its source, then :class:`EngineErrorFloodError`
        is raised.

        ``on_flood`` runs while the command lock is held, so it MUST NOT call
        back into :meth:`send_command` — e.g. don't pass ``launcher.kill``,
        which sends a ``quit`` command and would deadlock on the non-reentrant
        lock. Pass a hook that only signals the OS process (terminate/kill).
        """
        self._flood_detector = detector
        self._on_flood = on_flood

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

            # Strip log metadata before exposing the response to callers.
            # last_logs holds the delta for this response; collected_logs
            # accumulates until the test boundary resets it. The dropped
            # marker is appended to ``entries`` itself so all three exits
            # — last_logs, collected_logs, and exc.logs on the error path
            # — surface buffer-overflow events uniformly.
            logs_raw = response.pop("_logs", None) or []
            dropped = int(response.pop("_logs_dropped", 0) or 0)
            entries = parse_log_entries(logs_raw)
            if dropped > 0:
                entries.append(LogEntry(
                    level="warning",
                    message=f"<{dropped} log entries dropped due to capture buffer overflow>",
                ))
            self.last_logs = entries
            self.collected_logs.extend(entries)
            self._trim_collected_logs()

            # Flood check runs before the per-command error check: a sustained
            # error flood should fast-fail the whole run even when this
            # particular response happened to succeed.
            if self._flood_detector is not None:
                stats = self._flood_detector.observe(entries, dropped)
                if stats is not None:
                    self._raise_flood(stats)

            if "error" in response:
                error_code = response["error"]
                error_msg = response.get("message", error_code)
                if "not found" in error_msg.lower() or "not found" in error_code.lower():
                    exc = NodeNotFoundError(error_msg)
                else:
                    exc = CommandError(error_msg)
                exc.logs = entries
                raise exc

            return response

    def hello(self, token: str) -> Dict[str, Any]:
        """Send the handshake. Must be the first command after connecting."""
        return self.send_command("hello", token=token, protocol_version=1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim_collected_logs(self) -> None:
        """Enforce the ``collected_logs`` cap by dropping oldest entries.

        Keeps the most recent ``_collected_logs_limit`` entries and records how
        many were discarded in ``collected_logs_dropped`` so the overflow is
        observable rather than silent. No-op when the cap is ``None``.
        """
        limit = self._collected_logs_limit
        if limit is None or len(self.collected_logs) <= limit:
            return
        overflow = len(self.collected_logs) - limit
        del self.collected_logs[:overflow]
        self.collected_logs_dropped += overflow

    def _raise_flood(self, stats) -> None:
        """Stop the flood at its source and raise :class:`EngineErrorFloodError`.

        ``_on_flood`` (the launcher's process kill) runs first so Godot stops
        burning frames even if the caller swallows the exception. It runs under
        the command lock, so it must not re-enter :meth:`send_command`.
        """
        if self._on_flood is not None:
            try:
                self._on_flood()
            except Exception:
                pass
        sample_text = "; ".join(str(e) for e in stats.samples) or \
            "<no error sample captured>"
        msg = (
            f"Engine error flood detected: {stats.error_count} error(s) and "
            f"{stats.dropped_count} dropped log(s) within "
            f"{stats.window_seconds}s. Godot was terminated early to fast-fail "
            f"instead of spinning to timeout. Sample errors: {sample_text}"
        )
        exc = EngineErrorFloodError(
            msg,
            error_count=stats.error_count,
            dropped_count=stats.dropped_count,
            window_seconds=stats.window_seconds,
            samples=stats.samples,
        )
        exc.logs = self.last_logs
        raise exc

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
