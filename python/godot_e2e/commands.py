"""High-level E2E command API for Godot."""

from .client import GodotClient
from .types import (
    serialize, deserialize, TimeoutError, NodeNotFoundError,
    ConnectionLostError, CommandError
)
import time


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
               port: int = 0, timeout: float = 10.0, extra_args: list = None):
        """Launch Godot and return a connected GodotE2E instance.
        Returns a context manager."""
        from .launcher import GodotLauncher
        launcher = GodotLauncher()
        client = launcher.launch(project_path, godot_path, port, timeout, extra_args)
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

    # --- Misc ---

    def quit(self, exit_code: int = 0):
        try:
            self._client.send_command("quit", exit_code=exit_code)
        except ConnectionLostError:
            pass  # Expected — Godot exits
