# API Reference

Complete reference for the godot-e2e Python API. All public classes, methods, types, and exceptions are documented here.

---

## GodotE2E

`godot_e2e.GodotE2E`

The high-level E2E testing interface. This is the main class you interact with in tests.

### Class Methods

#### `GodotE2E.launch(project_path, godot_path=None, port=0, timeout=10.0, extra_args=None)`

Launch a Godot process and return a connected `GodotE2E` instance. Returns a context manager.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_path` | `str` | required | Path to the Godot project directory (containing `project.godot`). |
| `godot_path` | `str` | `None` | Path to the Godot executable. If `None`, discovered from `GODOT_PATH` env var or `PATH`. |
| `port` | `int` | `0` | TCP port for the automation server. `0` means auto-allocate a free port. |
| `timeout` | `float` | `10.0` | Seconds to wait for the connection to succeed. |
| `extra_args` | `list` | `None` | Additional command-line arguments forwarded to the Godot process. |

**Returns**: `GodotE2E` (usable as a context manager with `with`).

**Raises**:
- `FileNotFoundError` -- if Godot cannot be located.
- `RuntimeError` -- if the Godot process exits before connection is established.
- `ConnectionError` -- if the connection cannot be established within `timeout` seconds.

**Example**:

```python
with GodotE2E.launch("./my_project") as game:
    game.wait_for_node("/root/Main")
    pos = game.get_property("/root/Main/Player", "position")
```

---

#### `GodotE2E.connect(host="127.0.0.1", port=6008, token="")`

Connect to an already-running Godot instance. Use this when you have started Godot manually with `--e2e`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | Host address. |
| `port` | `int` | `6008` | TCP port. |
| `token` | `str` | `""` | Authentication token (must match `--e2e-token` if set). |

**Returns**: `GodotE2E`.

---

### Lifecycle Methods

#### `close()`

Terminate the Godot process (if launched) and close the TCP connection. Called automatically when used as a context manager.

---

### Node Operations

#### `node_exists(path) -> bool`

Check whether a node exists in the scene tree.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Absolute node path (e.g., `"/root/Main/Player"`). |

**Returns**: `True` if the node exists, `False` otherwise.

---

#### `get_property(path, property)`

Get a property value from a node. Supports Godot's indexed property notation with colons.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Absolute node path. |
| `property` | `str` | Property name. Use colon notation for sub-properties (e.g., `"position:x"`). |

**Returns**: The property value, deserialized into the appropriate Python type (see [Types](#types)).

**Raises**:
- `NodeNotFoundError` -- if the node does not exist.
- `CommandError` -- if the property does not exist on the node.

**Example**:

```python
pos = game.get_property("/root/Main/Player", "position")     # Returns Vector2
x = game.get_property("/root/Main/Player", "position:x")     # Returns float
text = game.get_property("/root/Main/Label", "text")          # Returns str
```

---

#### `set_property(path, property, value)`

Set a property value on a node. The value is serialized before sending.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Absolute node path. |
| `property` | `str` | Property name (supports colon notation). |
| `value` | any | The value to set. Use godot-e2e types for Godot-specific types (e.g., `Vector2`). |

**Raises**: `NodeNotFoundError` -- if the node does not exist.

**Example**:

```python
from godot_e2e import Vector2

game.set_property("/root/Main/Player", "position", Vector2(100.0, 200.0))
game.set_property("/root/Main", "score", 0)
```

---

#### `call(path, method, args=None)`

Call a method on a node and return the result.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Absolute node path. |
| `method` | `str` | required | Method name to call. |
| `args` | `list` | `None` | List of arguments to pass. Each is serialized before sending. |

**Returns**: The method's return value, deserialized.

**Raises**:
- `NodeNotFoundError` -- if the node does not exist.
- `CommandError` -- if the method does not exist on the node.

**Example**:

```python
result = game.call("/root/Main", "get_counter")
game.call("/root/Main", "add_to_counter", [5])
```

---

#### `find_by_group(group) -> list`

Find all nodes belonging to a Godot group.

| Parameter | Type | Description |
|-----------|------|-------------|
| `group` | `str` | Group name. |

**Returns**: List of absolute node path strings.

**Example**:

```python
enemies = game.find_by_group("enemies")
# ["/root/Main/Enemy1", "/root/Main/Enemy2"]
```

---

#### `query_nodes(pattern="", group="") -> list`

Query nodes by name pattern, group, or both. The pattern uses Godot's `String.match()` glob syntax (supports `*` and `?` wildcards).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | `str` | `""` | Glob pattern to match against node names. |
| `group` | `str` | `""` | Filter to nodes in this group. |

**Returns**: List of absolute node path strings.

**Example**:

```python
# All nodes whose name starts with "Enemy"
game.query_nodes(pattern="Enemy*")

# All nodes in the "enemies" group
game.query_nodes(group="enemies")

# Nodes in "enemies" group whose name matches "Boss*"
game.query_nodes(pattern="Boss*", group="enemies")
```

---

#### `get_tree(path="/root", depth=4) -> dict`

Get a snapshot of the scene tree as a nested dictionary. Useful for debugging.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | `"/root"` | Root node path to start from. |
| `depth` | `int` | `4` | Maximum depth to traverse. |

**Returns**: A nested dict with keys `"name"`, `"type"`, `"path"`, and `"children"` (list of child dicts).

**Example**:

```python
tree = game.get_tree("/root/Main", depth=2)
# {
#   "name": "Main",
#   "type": "Node2D",
#   "path": "/root/Main",
#   "children": [
#     {"name": "Player", "type": "CharacterBody2D", "path": "/root/Main/Player", "children": []},
#     {"name": "Label", "type": "Label", "path": "/root/Main/Label", "children": []},
#     ...
#   ]
# }
```

---

#### `batch(commands) -> list`

Execute multiple commands in a single network round-trip. Only instant (non-deferred) commands are supported in batch. Deferred commands (input, waits) return an error entry.

| Parameter | Type | Description |
|-----------|------|-------------|
| `commands` | `list` | List of commands. Each is either a dict with an `"action"` key, or a tuple/list of `(action, params_dict)`. |

**Returns**: List of results, one per command. Each result is the deserialized return value.

**Example**:

```python
results = game.batch([
    ("get_property", {"path": "/root/Main/Player", "property": "position:x"}),
    ("get_property", {"path": "/root/Main/Player", "property": "position:y"}),
    {"action": "node_exists", "path": "/root/Main/Enemy"},
])
x, y, enemy_exists = results[0], results[1], results[2]
```

---

### Input Simulation

All input commands are **deferred**: the server injects the input event and then waits 2 physics frames before responding, ensuring Godot processes the input in `_physics_process`.

#### `input_key(keycode, pressed, physical=False)`

Inject a keyboard event.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keycode` | `int` | required | Godot key constant (e.g., `KEY_RIGHT`, `KEY_SPACE`). |
| `pressed` | `bool` | required | `True` for key-down, `False` for key-up. |
| `physical` | `bool` | `False` | If `True`, sets `physical_keycode` instead of `keycode`. |

---

#### `input_action(action_name, pressed, strength=1.0)`

Inject a named input action event.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action_name` | `str` | required | Action name as defined in Godot's Input Map (e.g., `"ui_right"`). |
| `pressed` | `bool` | required | `True` for press, `False` for release. |
| `strength` | `float` | `1.0` | Action strength (0.0 to 1.0). |

---

#### `input_mouse_button(x, y, button=1, pressed=True)`

Inject a mouse button event at screen coordinates.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x` | `float` | required | X screen coordinate. |
| `y` | `float` | required | Y screen coordinate. |
| `button` | `int` | `1` | Mouse button index (1 = left, 2 = right, 3 = middle). |
| `pressed` | `bool` | `True` | `True` for press, `False` for release. |

---

#### `input_mouse_motion(x, y, relative_x=0, relative_y=0)`

Inject a mouse motion event.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x` | `float` | required | X screen position. |
| `y` | `float` | required | Y screen position. |
| `relative_x` | `float` | `0` | Relative X motion. |
| `relative_y` | `float` | `0` | Relative Y motion. |

---

### High-Level Input Helpers

These are convenience wrappers that press and immediately release.

#### `press_key(keycode)`

Press and release a key in one call. Equivalent to calling `input_key(keycode, True)` then `input_key(keycode, False)`.

---

#### `press_action(action_name, strength=1.0)`

Press and release a named action. Equivalent to calling `input_action(action_name, True, strength)` then `input_action(action_name, False)`.

---

#### `click(x, y, button=1)`

Click at screen coordinates. Equivalent to calling `input_mouse_button` with `pressed=True` then `pressed=False`.

---

#### `click_node(path)`

Click at a node's screen position. The server computes the screen coordinates automatically:
- For `Control` nodes: uses the center of `get_global_rect()`.
- For `Node2D` nodes: transforms global position to screen coordinates.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Absolute node path. Must be a `Control` or `Node2D`. |

**Raises**:
- `NodeNotFoundError` -- if the node does not exist.
- `CommandError` -- if the node type does not support screen position calculation.

---

### Frame Synchronization

#### `wait_process_frames(count=1)`

Wait for the specified number of `_process` frames to complete.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `count` | `int` | `1` | Number of process frames to wait. |

---

#### `wait_physics_frames(count=1)`

Wait for the specified number of `_physics_process` frames to complete.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `count` | `int` | `1` | Number of physics frames to wait. |

---

#### `wait_seconds(seconds)`

Wait for the specified amount of in-game time (affected by `Engine.time_scale`).

| Parameter | Type | Description |
|-----------|------|-------------|
| `seconds` | `float` | Number of in-game seconds to wait. |

---

### Synchronization

#### `wait_for_node(path, timeout=5.0)`

Block until a node exists in the scene tree. Polls every process frame.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Absolute node path to wait for. |
| `timeout` | `float` | `5.0` | Maximum seconds to wait. |

**Raises**: `TimeoutError` -- if the node does not appear within the timeout. The exception's `scene_tree` attribute contains a tree dump captured at the moment of timeout (if retrieval succeeds).

---

#### `wait_for_signal(path, signal_name, timeout=5.0)`

Wait for a signal to be emitted.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Absolute path to the node that emits the signal. |
| `signal_name` | `str` | required | Name of the signal. |
| `timeout` | `float` | `5.0` | Maximum seconds to wait. |

**Returns**: List of signal arguments (may be empty).

**Raises**:
- `NodeNotFoundError` -- if the source node does not exist.
- `CommandError` -- if the signal does not exist on the node.
- `TimeoutError` -- if the signal is not emitted within the timeout.

---

#### `wait_for_property(path, property, value, timeout=5.0)`

Wait until a property equals the expected value. Polls every process frame.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Absolute node path. |
| `property` | `str` | required | Property name. |
| `value` | any | required | Expected value (serialized before comparison). |
| `timeout` | `float` | `5.0` | Maximum seconds to wait. |

**Raises**: `TimeoutError` -- if the property does not reach the expected value within the timeout.

---

### Scene Management

#### `get_scene() -> str`

Get the `res://` path of the currently loaded scene.

**Returns**: Scene file path string (e.g., `"res://main.tscn"`).

---

#### `change_scene(scene_path)`

Change to a different scene. This is a deferred operation -- the method blocks until the new scene is loaded and its root node is available.

| Parameter | Type | Description |
|-----------|------|-------------|
| `scene_path` | `str` | Scene resource path (e.g., `"res://levels/level2.tscn"`). |

---

#### `reload_scene()`

Reload the current scene. This is a deferred operation -- the method blocks until the scene is reloaded and ready. Useful for resetting state between tests.

---

### Screenshot

#### `screenshot(save_path="") -> str`

Capture a screenshot of the current viewport.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `save_path` | `str` | `""` | Absolute file path to save the PNG. If empty, saves to `user://e2e_screenshots/` with a timestamp filename. |

**Returns**: The absolute path to the saved PNG file.

---

### Misc

#### `quit(exit_code=0)`

Terminate the Godot process. The resulting `ConnectionLostError` is suppressed internally.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exit_code` | `int` | `0` | Process exit code. |

---

## GodotClient

`godot_e2e.GodotClient`

Low-level TCP client that speaks the godot-e2e wire protocol. You typically do not use this directly -- use `GodotE2E` instead.

### Constructor

```python
GodotClient(host="127.0.0.1", port=6008)
```

### Methods

#### `connect(timeout=10.0)`

Open a TCP connection to the Godot automation server.

**Raises**: `OSError` -- if the connection fails.

---

#### `close()`

Close the TCP connection.

---

#### `hello(token) -> dict`

Send the handshake message. Must be the first command after connecting.

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | Authentication token. |

**Returns**: Response dict with `"ok"`, `"godot_version"`, and `"server_version"` keys.

---

#### `send_command(action, **params) -> dict`

Send a command and block until the matching response arrives.

| Parameter | Type | Description |
|-----------|------|-------------|
| `action` | `str` | Command action name. |
| `**params` | any | Additional parameters included in the JSON message. |

**Returns**: The parsed response dictionary.

**Raises**:
- `NodeNotFoundError` -- if the server reports a missing node.
- `CommandError` -- for any other server-side error.
- `ConnectionLostError` -- if the TCP connection drops or times out.

---

## GodotLauncher

`godot_e2e.GodotLauncher`

Manages launching a Godot subprocess and connecting to it. Used internally by `GodotE2E.launch()`.

### Methods

#### `launch(project_path, godot_path=None, port=0, timeout=10.0, extra_args=None) -> GodotClient`

Launch Godot and return a connected `GodotClient` that has completed the handshake.

The launcher:
1. Finds the Godot binary (from `godot_path`, `GODOT_PATH` env var, or `PATH`).
2. If `port=0` (default), creates a temporary port file and passes `--e2e-port=0 --e2e-port-file=<path>` so Godot auto-selects a free port and writes it to the file.
3. Generates a random authentication token.
4. Starts Godot with `--e2e`, `--e2e-port=N`, `--e2e-token=X` (and `--e2e-port-file` when applicable).
5. Reads the actual port from the port file (if auto-allocated), then polls until a TCP connection succeeds and the handshake completes.

**Raises**:
- `FileNotFoundError` -- if Godot cannot be located.
- `RuntimeError` -- if the Godot process exits before connection.
- `ConnectionError` -- if connection is not established within `timeout`.

---

#### `kill()`

Gracefully shut down Godot by sending a `quit` command, then terminating the process. Falls back to `process.kill()` if the process does not exit within 5 seconds.

---

## Types

`godot_e2e.types`

Python dataclasses that mirror Godot's built-in types. These are used for serialization/deserialization of property values.

### Vector2

```python
@dataclass
class Vector2:
    x: float
    y: float
```

### Vector2i

```python
@dataclass
class Vector2i:
    x: int
    y: int
```

### Vector3

```python
@dataclass
class Vector3:
    x: float
    y: float
    z: float
```

### Vector3i

```python
@dataclass
class Vector3i:
    x: int
    y: int
    z: int
```

### Rect2

```python
@dataclass
class Rect2:
    x: float
    y: float
    w: float
    h: float
```

### Rect2i

```python
@dataclass
class Rect2i:
    x: int
    y: int
    w: int
    h: int
```

### Color

```python
@dataclass
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0
```

### Transform2D

```python
@dataclass
class Transform2D:
    x: Vector2
    y: Vector2
    origin: Vector2
```

### NodePath

```python
@dataclass
class NodePath:
    path: str
```

---

### Serialization Functions

#### `serialize(value)`

Convert Python types to JSON-serializable dicts with `_t` type tags. Primitives, lists, and plain dicts pass through. Godot types are tagged.

#### `deserialize(value)`

Convert JSON dicts with `_t` type tags back to Python types. Unknown tags with `_t: "_unknown"` pass through as raw dicts.

---

## Exceptions

All exceptions inherit from `GodotE2EError`.

### GodotE2EError

```python
class GodotE2EError(Exception):
    """Base exception for all godot-e2e errors."""
```

### NodeNotFoundError

```python
class NodeNotFoundError(GodotE2EError):
    """Raised when a node path doesn't resolve in the scene tree."""
```

Raised by: `get_property`, `set_property`, `call`, `click_node`, `wait_for_signal`.

### TimeoutError

```python
class TimeoutError(GodotE2EError):
    def __init__(self, message: str, scene_tree=None):
        self.scene_tree = scene_tree  # dict or None
```

Raised by: `wait_for_node`, `wait_for_signal`, `wait_for_property`.

The `scene_tree` attribute contains a tree dump captured at the moment of timeout (when available), which is useful for diagnosing why a node was not found.

### ConnectionLostError

```python
class ConnectionLostError(GodotE2EError):
    """Raised when the Godot process crashes or the TCP connection drops."""
```

Raised by: `send_command` (and any high-level method that sends commands).

### CommandError

```python
class CommandError(GodotE2EError):
    """Raised when the server returns an error response."""
```

Raised when the Godot server returns an error that is not a "not found" error. This includes unknown commands, invalid properties, failed method calls, and other server-side errors.

---

## pytest Fixtures

The `godot_e2e.fixtures` module is registered as a pytest plugin automatically via the `pytest11` entry point.

### `game`

**Scope**: function

A function-scoped fixture backed by a module-scoped Godot process. Reloads the scene before each test and captures a screenshot on failure.

The Godot project path is resolved from (in priority order):
1. `@pytest.mark.godot_project("path")` marker.
2. `godot_e2e_project_path` in pytest configuration.
3. `GODOT_E2E_PROJECT_PATH` environment variable.
4. Auto-detection of `project.godot` in common locations.

The Godot executable is resolved from the `GODOT_PATH` environment variable or `PATH`.

### `game_fresh`

**Scope**: function

A function-scoped fixture that launches a **fresh Godot process** for each test. Provides maximum isolation at the cost of speed. Captures a screenshot on failure.

### Screenshot on Failure

Both fixtures automatically capture a screenshot when a test fails. Screenshots are saved to `test_output/<test_name>_failure.png` in the current working directory.
