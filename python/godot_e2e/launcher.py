"""Subprocess management for launching and connecting to Godot."""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import time
from typing import List, Optional

from .client import GodotClient


class GodotLauncher:
    """Launch a Godot instance with the E2E automation server enabled and
    return a connected :class:`GodotClient`.
    """

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None
        self.port: Optional[int] = None
        self.token: Optional[str] = None
        self.client: Optional[GodotClient] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def launch(
        self,
        project_path: str,
        godot_path: Optional[str] = None,
        port: int = 0,
        timeout: float = 10.0,
        extra_args: Optional[List[str]] = None,
    ) -> GodotClient:
        """Launch Godot and return a connected :class:`GodotClient`.

        Args:
            project_path: Path to the Godot project directory.
            godot_path: Path to the Godot executable.  Discovered
                automatically from ``GODOT_PATH`` env var or ``PATH``
                if *None*.
            port: TCP port for the automation server.  ``0`` means
                auto-allocate a free port.
            timeout: Seconds to wait for the connection to succeed.
            extra_args: Additional command-line arguments forwarded to
                the Godot process.

        Returns:
            A :class:`GodotClient` that has already completed the
            handshake.

        Raises:
            FileNotFoundError: if Godot cannot be located.
            RuntimeError: if the Godot process exits before we connect.
            ConnectionError: if the connection cannot be established
                within *timeout* seconds.
        """
        godot_path = godot_path or self._find_godot()

        if port == 0:
            port = self._get_free_port()
        self.port = port

        self.token = secrets.token_hex(16)

        cmd = [godot_path, "--path", os.path.abspath(project_path)]
        if extra_args:
            cmd.extend(extra_args)
        cmd.extend([
            "--",
            "--e2e",
            f"--e2e-port={port}",
            f"--e2e-token={self.token}",
        ])

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self.client = GodotClient("127.0.0.1", port)

        deadline = time.monotonic() + timeout
        last_error: Optional[Exception] = None

        while time.monotonic() < deadline:
            # If Godot already exited, report why.
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"Godot process exited with code {self.process.returncode}"
                )
            try:
                self.client.connect(timeout=2.0)
                self.client.hello(self.token)
                return self.client
            except (ConnectionRefusedError, ConnectionError, OSError) as exc:
                last_error = exc
                time.sleep(0.1)

        raise ConnectionError(
            f"Could not connect to Godot within {timeout}s: {last_error}"
        )

    def __del__(self) -> None:
        """Safety net: kill Godot if the launcher is garbage-collected."""
        self.kill()

    def kill(self) -> None:
        """Gracefully shut down Godot, falling back to a hard kill."""
        if self.client is not None:
            try:
                self.client.send_command("quit")
            except Exception:
                pass
            self.client.close()
            self.client = None

        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_free_port() -> int:
        """Bind to port 0 to let the OS assign a free port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    @staticmethod
    def _find_godot() -> str:
        """Locate the Godot executable via environment or PATH.

        Search order:
        1. ``GODOT_PATH`` environment variable.
        2. Common executable names on ``PATH``.
        """
        env_path = os.environ.get("GODOT_PATH")
        if env_path and os.path.isfile(env_path):
            return env_path

        for name in ("godot", "godot4", "Godot_v4"):
            found = shutil.which(name)
            if found:
                return found

        raise FileNotFoundError(
            "Could not find Godot executable. Set the GODOT_PATH environment "
            "variable or pass the godot_path parameter."
        )
