"""High-level E2E command API for Godot."""

from .client import GodotClient
from .types import (
    serialize, deserialize, TimeoutError,
    ConnectionLostError, CommandError
)


class GodotE2E:
    """High-level E2E testing interface for Godot.

    Usage:
        with GodotE2E.launch("./my_project") as game:
            game.wait_for_node("/root/Main")
            pos = game.get_property("/root/Main/Player", "position")
    """

    def __init__(self, client: GodotClient, launcher=None):
        self._client = client
        self._launcher = launcher

    @classmethod
    def launch(cls, project_path: str, godot_path: str = None,
               port: int = 0, timeout: float = 10.0, extra_args: list = None,
               log_verbosity: str = None):
        """Launch Godot and return a connected GodotE2E instance.

        ``log_verbosity`` (one of ``"error"`` / ``"warning"`` / ``"info"``)
        sets the engine log capture level at startup. When *None*, the
        addon default (``"warning"``) applies. See
        :meth:`set_log_verbosity` for adjusting it at runtime.

        Returns a context manager."""
        from .launcher import GodotLauncher
        launcher = GodotLauncher()
        client = launcher.launch(
            project_path, godot_path, port, timeout, extra_args,
            log_verbosity=log_verbosity,
        )
        return cls(client, launcher)

    @classmethod
    def connect(cls, host: str = "127.0.0.1", port: int = 6008, token: str = ""):
        """Connect to an already-running Godot instance."""
        client = GodotClient(host, port)
        client.connect()
        client.hello(token)
        return cls(client)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._launcher:
            self._launcher.kill()
        elif self._client:
            self._client.close()

    # --- Node Operations (F2) ---

    def node_exists(self, path: str) -> bool:
        resp = self._client.send_command("node_exists", path=path)
        return resp.get("exists", False)

    def get_property(self, path: str, property: str):
        resp = self._client.send_command("get_property", path=path, property=property)
        return deserialize(resp["result"])

    def set_property(self, path: str, property: str, value):
        self._client.send_command(
            "set_property", path=path, property=property, value=serialize(value)
        )

    def call(self, path: str, method: str, args: list = None):
        resp = self._client.send_command(
            "call_method", path=path, method=method,
            args=[serialize(a) for a in (args or [])]
        )
        return deserialize(resp.get("result"))

    def find_by_group(self, group: str) -> list:
        resp = self._client.send_command("find_by_group", group=group)
        return resp.get("nodes", [])

    def query_nodes(self, pattern: str = "", group: str = "") -> list:
        resp = self._client.send_command("query_nodes", pattern=pattern, group=group)
        return resp.get("nodes", [])

    # --- Locator (multi-strategy lazy reference) ---

    def locator(self, **kwargs):
        """Build a :class:`Locator` for the given query.

        Supported keywords (all AND-composed): ``path``, ``name``,
        ``group``, ``text``, ``script``, ``type``. ``name`` and ``text``
        switch to glob matching when the value contains ``*`` or ``?``.
        ``type`` matches via instanceof, so ``type="BaseButton"`` covers
        ``Button``, ``CheckBox``, ``OptionButton``, etc.
        """
        from .locator import Locator, _build_query
        return Locator(self._client, _build_query(kwargs))

    def get_by_text(self, text: str):
        """Sugar for ``locator(text=text)``."""
        return self.locator(text=text)

    def get_by_button(self, text: str):
        """Sugar for any clickable button (``BaseButton`` family) with the
        given text. Covers ``Button``, ``CheckBox``, ``OptionButton``,
        ``MenuButton``, ``LinkButton``.
        """
        return self.locator(type="BaseButton", text=text)

    def get_tree(self, path: str = "/root", depth: int = 4) -> dict:
        resp = self._client.send_command("get_tree", path=path, depth=depth)
        return resp.get("tree", {})

    def batch(self, commands: list) -> list:
        """Execute multiple commands in one round-trip.

        Each command is either a dict with an "action" key, or a tuple/list of
        (action, params_dict).

        Example::

            results = game.batch([
                ("get_property", {"path": "/root/Player", "property": "health"}),
                {"action": "node_exists", "path": "/root/Enemy"},
            ])
        """
        cmd_list = []
        for cmd in commands:
            if isinstance(cmd, dict):
                cmd_list.append(cmd)
            elif isinstance(cmd, (list, tuple)):
                action = cmd[0]
                params = cmd[1] if len(cmd) > 1 else {}
                cmd_list.append({"action": action, **params})
        resp = self._client.send_command("batch", commands=cmd_list)
        results = resp.get("results", [])
        return [
            deserialize(r.get("result")) if "result" in r else r
            for r in results
        ]

    # --- Input Simulation (F3) ---

    def input_key(self, keycode: int, pressed: bool, physical: bool = False):
        self._client.send_command(
            "input_key", keycode=keycode, pressed=pressed, physical=physical
        )

    def input_action(self, action_name: str, pressed: bool, strength: float = 1.0):
        self._client.send_command(
            "input_action", action_name=action_name, pressed=pressed, strength=strength
        )

    def input_mouse_button(
        self, x: float, y: float, button: int = 1, pressed: bool = True
    ):
        self._client.send_command(
            "input_mouse_button", x=x, y=y, button=button, pressed=pressed
        )

    def input_mouse_motion(
        self, x: float, y: float, relative_x: float = 0, relative_y: float = 0
    ):
        self._client.send_command(
            "input_mouse_motion", x=x, y=y,
            relative_x=relative_x, relative_y=relative_y
        )

    # --- High-Level Helpers (F6) ---

    def press_key(self, keycode: int):
        """Press and release a key."""
        self.input_key(keycode, True)
        self.input_key(keycode, False)

    def press_action(self, action_name: str, strength: float = 1.0):
        """Press and release an action."""
        self.input_action(action_name, True, strength)
        self.input_action(action_name, False)

    def click(self, x: float, y: float, button: int = 1):
        """Click at screen position."""
        self.input_mouse_button(x, y, button, True)
        self.input_mouse_button(x, y, button, False)

    def click_node(self, path: str):
        """Click at a node's screen position."""
        self._client.send_command("click_node", path=path)

    # --- Frame Synchronization (F4) ---

    def wait_process_frames(self, count: int = 1):
        self._client.send_command("wait_process_frames", count=count)

    def wait_physics_frames(self, count: int = 1):
        self._client.send_command("wait_physics_frames", count=count)

    def wait_seconds(self, seconds: float):
        self._client.send_command("wait_seconds", seconds=seconds)

    # --- Synchronization (F6/F9) ---

    def wait_for_node(self, path: str, timeout: float = 5.0):
        """Wait until a node exists in the scene tree.

        Raises TimeoutError with a scene tree dump if the timeout is exceeded.
        """
        try:
            self._client.send_command("wait_for_node", path=path, timeout=timeout)
        except CommandError as e:
            if "timeout" in str(e).lower():
                tree = None
                try:
                    tree = self.get_tree()
                except Exception:
                    pass
                raise TimeoutError(
                    f"Timed out waiting for node '{path}' after {timeout}s",
                    scene_tree=tree,
                ) from e
            raise

    def wait_for_signal(self, path: str, signal_name: str, timeout: float = 5.0):
        resp = self._client.send_command(
            "wait_for_signal", path=path, signal_name=signal_name, timeout=timeout
        )
        return resp.get("args", [])

    def wait_for_property(self, path: str, property: str, value, timeout: float = 5.0):
        self._client.send_command(
            "wait_for_property", path=path, property=property,
            value=serialize(value), timeout=timeout,
        )

    # --- Scene Management (F11) ---

    def get_scene(self) -> str:
        resp = self._client.send_command("get_scene")
        return resp.get("scene", "")

    def change_scene(self, scene_path: str):
        self._client.send_command("change_scene", scene_path=scene_path)

    def reload_scene(self):
        self._client.send_command("reload_scene")

    # --- Screenshot (F10) ---

    def screenshot(self, save_path: str = "") -> str:
        """Capture a screenshot. Returns the absolute path to the saved PNG."""
        resp = self._client.send_command("screenshot", save_path=save_path)
        return resp.get("path", "")

    # --- Engine log capture ---

    @property
    def last_logs(self):
        """Engine log entries captured during the most recent command call."""
        return self._client.last_logs

    @property
    def collected_logs(self):
        """All engine log entries captured since the last reset.

        The pytest plugin clears this at the start of every test, so under
        the standard ``game`` / ``game_fresh`` fixtures the list reflects
        only the logs produced by the current test.
        """
        return self._client.collected_logs

    def reset_collected_logs(self):
        """Discard all entries in ``collected_logs`` and ``last_logs``."""
        self._client.reset_collected_logs()

    def set_log_verbosity(self, level: str):
        """Adjust engine log capture verbosity at runtime.

        ``level`` is one of ``"error"``, ``"warning"``, ``"info"``. The
        default at server startup comes from the ``--e2e-log-verbosity``
        launch flag (default ``"warning"``) — call this to override it
        within a single test (e.g. raise to ``"info"`` to also capture
        ``print()`` output).
        """
        self._client.send_command("set_log_verbosity", level=level)

    def set_log_buffer_size(self, size: int):
        """Resize the engine log capture ring buffer at runtime.

        The default of 200 is sized for typical test runs; raise it for
        debug sessions on high-error-density games where entries are
        being dropped between drains, or shrink it (and trigger an
        overflow on purpose) when validating capture-overflow handling.

        ``size`` must be a positive integer; ``ValueError`` is raised at
        the Python boundary for ``size < 1``, matching the runtime
        contract on the wire side.
        """
        if not isinstance(size, int) or size < 1:
            raise ValueError(f"size must be a positive int, got {size!r}")
        self._client.send_command("set_log_buffer_size", size=size)

    # --- Misc ---

    def quit(self, exit_code: int = 0):
        try:
            self._client.send_command("quit", exit_code=exit_code)
        except ConnectionLostError:
            pass  # Expected — Godot exits
