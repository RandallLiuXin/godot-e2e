# API Reference

Complete reference for the godot-e2e Python API. All public classes, methods, types, and exceptions are documented here.

---

## GodotE2E

`godot_e2e.GodotE2E`

The high-level E2E testing interface. This is the main class you interact with in tests.

### Class Methods

#### `GodotE2E.launch(project_path, godot_path=None, port=0, timeout=10.0, extra_args=None, log_verbosity=None)`

Launch a Godot process and return a connected `GodotE2E` instance. Returns a context manager.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_path` | `str` | required | Path to the Godot project directory (containing `project.godot`). |
| `godot_path` | `str` | `None` | Path to the Godot executable. If `None`, discovered from `GODOT_PATH` env var or `PATH`. |
| `port` | `int` | `0` | TCP port for the automation server. `0` means auto-allocate a free port. |
| `timeout` | `float` | `10.0` | Seconds to wait for the connection to succeed. |
| `extra_args` | `list` | `None` | Additional command-line arguments forwarded to the Godot process (placed before the `--` user-args separator). |
| `log_verbosity` | `str` | `None` | Engine log capture verbosity at startup: `"error"` / `"warning"` / `"info"`. `None` keeps the addon default (`"warning"`). Adjustable at runtime via `set_log_verbosity`. |

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

### Locators

These methods construct a [`Locator`](#locator). They do not hit the server.

#### `locator(**kwargs) -> Locator`

Build a Locator with one or more query strategies (AND-composed).

| Keyword | Description |
|---|---|
| `path` | Absolute scene path. Returns 0 or 1 match. |
| `name` | Node name. Glob if value contains `*` or `?`, else exact. |
| `group` | Group name. |
| `text` | Compared against `node.text` if present. Glob/exact same rule as `name`. |
| `script` | Script resource path (e.g. `"res://player.gd"`). Exact. |
| `type` | Class name. Matches via `is X` so descendants are included. |

**Returns**: `Locator`.

**Raises**: `ValueError` -- if no keyword is given or an unknown keyword is used.

#### `get_by_text(text) -> Locator`

Sugar for `locator(text=text)`.

#### `get_by_button(text) -> Locator`

Sugar for `locator(type="BaseButton", text=text)`. Matches `Button`, `CheckBox`, `OptionButton`, `MenuButton`, `LinkButton`.

---

### Engine Log Capture

godot-e2e captures Godot-side `push_error`, `push_warning`, script runtime errors, shader errors, and (at info verbosity) `print` / `printerr` output, then surfaces them on the Python side. Requires Godot 4.5+ (see [`Logger`](https://docs.godotengine.org/en/4.5/classes/class_logger.html)).

The default verbosity is `warning` (errors + warnings). Plain `print()` is excluded by default to avoid drowning the test output in noise.

#### `last_logs -> list[LogEntry]`

The log entries captured during the most recent command call. Cleared on each command.

#### `collected_logs -> list[LogEntry]`

All log entries captured since the last reset. The pytest plugin clears this at the start of every test, so under the standard `game` / `game_fresh` fixtures the list reflects only the logs produced by the current test (including its scene reload).

On test failure, the same list is appended to the pytest report under a `captured godot logs` section, alongside the standard `captured stdout` / `captured stderr` blocks.

#### `reset_collected_logs()`

Discard all entries in `collected_logs` and `last_logs`. The pytest fixtures call this automatically; you typically only need it to scope a specific assertion to a narrower window.

#### `set_log_verbosity(level)`

Adjust capture verbosity at runtime. The startup default comes from the launcher's `--e2e-log-verbosity` flag.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | `str` | — | One of `"error"`, `"warning"`, `"info"`. |

Raises `CommandError` for any other value.

```python
def test_print_visible_under_info(game):
    game.set_log_verbosity("info")
    game.call("/root/Player", "_announce")  # uses print()
    assert any("ready" in e.message for e in game.collected_logs)
```

#### `set_log_buffer_size(size)`

Resize the engine log capture ring buffer at runtime. The default of 200 is sized for typical test runs; raise it for debug sessions on high-error-density games where entries are being dropped between drains, or shrink it (and deliberately trigger overflow) when validating capture-overflow handling.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | — | Positive integer ring-buffer size. |

Raises `ValueError` for `size < 1` at the Python boundary; the wire side returns `invalid_argument` for the same condition if the command is sent directly via `GodotClient.send_command`.

When the buffer overflows between drains, the response carries a `_logs_dropped` count which the client surfaces as a single synthetic warning entry (`"<N log entries dropped due to capture buffer overflow>"`) appended uniformly to `last_logs`, `collected_logs`, and any raised exception's `logs`.

#### `set_flood_detection(*, enabled=None, window_seconds=None, error_threshold=None)`

Adjust the **engine-error-flood guard** at runtime. A non-fatal GDScript error in `_process` / `_physics_process` re-fires every frame; under headless (vsync-off) Godot this becomes hundreds-to-thousands of identical error lines per second, and an unattended run would otherwise idle to its full timeout while the game spins. The guard watches the error / `_logs_dropped` signal piggybacked on command responses over a sliding wall-clock window; once the combined error + dropped count in the window crosses the threshold, Godot is force-killed and the next command raises [`EngineErrorFloodError`](#exceptions).

The guard is **on by default**. Its startup parameters come from the `launch()` kwargs; this method retunes them mid-run (any argument left `None` is unchanged):

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | `bool` | `True` | Turn the guard on/off. |
| `window_seconds` | `float` | `2.0` | Sliding-window duration. |
| `error_threshold` | `int` | `100` | Combined error + dropped-log entries in the window that trip the guard. |

Raises `ValueError` for `window_seconds <= 0` or `error_threshold < 1`. The same three knobs are settable at launch via `GodotE2E.launch(..., flood_detection=..., flood_window_seconds=..., flood_error_threshold=...)`.

```python
def test_noisy_game_needs_a_higher_bar(game):
    game.set_flood_detection(error_threshold=300)  # this game logs a lot
    ...

def test_intentionally_error_heavy(game):
    game.set_flood_detection(enabled=False)  # opt this test out of the guard
    ...
```

Detection only advances while commands round-trip (e.g. an `expect()` / `wait_for_*` poll). A flood driven purely by dropped log lines — a `push_warning` / `print` storm with no captured error — is reported as a "log flood" rather than an "error flood" so triage isn't sent chasing a runtime error that doesn't exist.

---

### Misc

#### `quit(exit_code=0)`

Terminate the Godot process. The resulting `ConnectionLostError` is suppressed internally.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exit_code` | `int` | `0` | Process exit code. |

---

## Locator

`godot_e2e.Locator`

A lazy, multi-strategy reference to one or more nodes in the running scene tree. Locators **re-resolve on every action**, so they remain valid across `reload_scene()` and other tree mutations.

Construct via [`GodotE2E.locator()`](#locatorkwargs---locator), [`get_by_text()`](#get_by_texttext---locator), or [`get_by_button()`](#get_by_buttontext---locator). The constructor is not part of the public API.

### Refinement

Each method returns a *new* Locator. The original is never mutated.

#### `filter(**kwargs) -> Locator`

Add additional AND-composed predicates. Same keyword set as `GodotE2E.locator()`.

#### `first() -> Locator`

Always pick the first match in tree-walk order.

#### `nth(i) -> Locator`

Pick the i-th match (zero-indexed). Raises `ValueError` if `i < 0`.

#### `all() -> list[Locator]`

Resolve immediately and return one path-pinned Locator per match. Snapshot at call time -- subsequent tree mutations do not update the list. Returns `[]` (no error) when nothing matches.

#### `locator(**kwargs) -> Locator`

Chained sub-query, scoped under this Locator's resolved node. The parent is **re-resolved on every action** of the chained Locator (consistent with non-chained Locators), so chained Locators survive `reload_scene()`.

The parent must resolve to exactly one node *at action time*; otherwise `MultipleMatchesError` / `NodeNotFoundError` is raised when an action runs, not when this method is called. (`exists()` and `count()` swallow these on the parent and return `False` / `0`.)

---

### Inspection

#### `exists() -> bool`

True if the query resolves to one or more nodes. Never raises on lookup issues -- missing node, missing/ambiguous chained parent, or server lookup error all return `False`. Connection failures still propagate.

#### `count() -> int`

Number of matching nodes. Returns `0` on the same conditions where `exists()` returns `False`.

#### `is_visible() -> bool`

Whether the (single-match) target is visible in the scene tree.

**Raises**: `MultipleMatchesError`, `NodeNotFoundError`.

#### `is_actionable() -> bool`

Whether the (single-match) target passes all actionability checks (visible_in_tree + mouse_filter + viewport intersect).

**Raises**: `MultipleMatchesError`, `NodeNotFoundError`.

---

### Actions

Each action re-runs the query before operating. The Locator must resolve to exactly one node; otherwise `MultipleMatchesError` / `NodeNotFoundError` is raised.

#### `click(*, force=False, timeout=5.0)`

Click the node's screen position (left button). For Control targets, polls actionability up to `timeout` and raises `NotActionableError` if the node never becomes actionable. Pass `force=True` to skip the check. Right- / middle-click support is tracked as future work; use `GodotE2E.input_mouse_button(...)` directly if needed today.

#### `hover()`

Inject `InputEventMouseMotion` at the node's screen position. Useful for testing tooltip / hover state. Note that this triggers `mouse_entered` / `_gui_input` on intervening Controls.

#### `get_property(prop)`

Read a property. Sub-property paths like `"position:x"` are supported.

#### `set_property(prop, value)`

Write a property. Python type wrappers (`Vector2`, `Color`, ...) are serialized automatically.

#### `call(method, args=None)`

Call a method on the node and return its result.

#### `wait_visible(*, timeout=5.0)`

Block until the (resolved) target passes actionability checks. Raises `NotActionableError` (with structured `reasons` and `checks`) if the deadline elapses or the node never appears.

#### `wait_for_signal(signal_name, timeout=5.0)`

Block until the (resolved) node emits the named signal. Returns the list of signal arguments. Raises `TimeoutError` on deadline.

---

### Auto-wait scope

`click()` and `wait_visible()` poll a server-side actionability snapshot. The checks applied depend on the node kind:

- **`Control`** -- full check:
  1. `is_visible_in_tree()` -- visible up the parent chain.
  2. `mouse_filter != MOUSE_FILTER_IGNORE` -- would receive mouse events.
  3. `get_global_rect().intersects(viewport_rect)` -- inside the visible area.
- **`Node2D`** -- visibility only (`is_visible_in_tree()`). Node2D has no `mouse_filter` equivalent, and its bounding rect for viewport intersection is not generally available.
- **`Node3D` / `Window` / plain `Node`** -- actionability fails with reason `"unclickable_node_type"`. `click_node` / `hover_node` cannot resolve a screen position for these node kinds, so the check refuses up front rather than letting `click()` raise later. Use a child `Control` or `Node2D` instead.

Occlusion / hit-test detection is tracked as a separate ROADMAP task.

---

## expect

`godot_e2e.expect`

Auto-retrying assertions for Locators. Each matcher polls the live game until the condition holds or the timeout elapses, then raises [`ExpectationFailedError`](#expectationfailederror) -- which subclasses both `GodotE2EError` and `AssertionError`, so pytest renders it as a regular assertion failure.

```python
from godot_e2e import expect

expect(game.locator(name="StatusLabel")).to_have_text("Ready")
expect(game.locator(name="HUD"), timeout=10.0).to_have_property("score", 100)
expect(game.locator(group="enemies")).to_satisfy(
    lambda loc: loc.count() == 0,
    description="all enemies cleared",
)
```

All polling happens client-side; matchers wrap existing Locator methods (`get_property`, `is_visible`, `exists`) so no new wire commands are required. Lookup-style errors raised mid-poll (`NodeNotFoundError`, `MultipleMatchesError`, `CommandError`) are absorbed and the loop keeps polling; this lets matchers ride out transient states like scene reloads.

#### `expect(locator, *, timeout=5.0, poll_interval=0.05) -> LocatorAssertions`

Build a polling assertion handle for `locator`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `locator` | `Locator` | The Locator to assert against. Re-resolved on every poll, so assertions ride scene changes. |
| `timeout` | `float` | Maximum seconds to keep retrying. Default `5.0`. |
| `poll_interval` | `float` | Seconds to sleep between polls. Default `0.05`. |

**Raises**: `TypeError` if `locator` is not a `Locator`. `ValueError` if `timeout < 0` or `poll_interval <= 0`.

### Matchers

Each matcher returns `None` on success and raises `ExpectationFailedError` on timeout. The error message includes the last observed value, and `error.scene_tree` carries a depth-4 dump of `/root` for diagnostics.

#### `to_have_property(name, value)`

Pass when `locator.get_property(name) == value`.

#### `to_have_text(text)`

Pass when the target's `text` property equals `text`. Sugar for `to_have_property("text", text)`.

#### `to_be_visible()`

Pass when the target is visible in the scene tree (same check as Locator's auto-wait). Reliable for `Control` and `Node2D` (both use `is_visible_in_tree`). For `Node3D`, `Window`, and plain `Node`, the underlying actionability check refuses with `unclickable_node_type` and visibility cannot be determined through this matcher -- use `to_satisfy(lambda l: l.get_property("visible"))` instead.

#### `to_exist()`

Pass when the locator's query resolves to one or more nodes. Doesn't require a single match -- use `to_satisfy(lambda l: l.count() == 1)` when you specifically need one.

#### `to_satisfy(predicate, *, description=None)`

Pass when `predicate(locator)` returns truthy. The predicate receives the Locator itself, so it can compose any combination of property reads, visibility checks, and `count()` queries.

| Parameter | Type | Description |
|-----------|------|-------------|
| `predicate` | `Callable[[Locator], Any]` | Truthy return = satisfied. |
| `description` | `str \| None` | Human-readable label used in the failure message. Without it, the matcher reports `repr(predicate)`, which is rarely useful for lambdas. |

Lookup errors raised inside the predicate (`NodeNotFoundError`, `MultipleMatchesError`, `CommandError`) are caught and treated as "not yet satisfied", so the predicate may freely call methods that require a node to exist.

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

#### `launch(project_path, godot_path=None, port=0, timeout=10.0, extra_args=None, log_verbosity=None) -> GodotClient`

Launch Godot and return a connected `GodotClient` that has completed the handshake.

The launcher:
1. Finds the Godot binary (from `godot_path`, `GODOT_PATH` env var, or `PATH`).
2. If `port=0` (default), creates a temporary port file and passes `--e2e-port=0 --e2e-port-file=<path>` so Godot auto-selects a free port and writes it to the file.
3. Generates a random authentication token.
4. Starts Godot with `--e2e`, `--e2e-port=N`, `--e2e-token=X` (and `--e2e-port-file` / `--e2e-log-verbosity` when applicable).
5. Reads the actual port from the port file (if auto-allocated), then polls until a TCP connection succeeds and the handshake completes.

`log_verbosity`, when non-`None`, must be one of `"error"` / `"warning"` / `"info"` — invalid values raise `ValueError` before the subprocess starts, matching the runtime contract on `set_log_verbosity`.

**Raises**:
- `ValueError` -- if `log_verbosity` is not one of the valid values.
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

### LogEntry

```python
@dataclass
class LogEntry:
    level: str       # "error" | "warning" | "info" | "stderr"
    message: str
    function: str    # populated only for engine errors
    file: str        # populated only for engine errors
    line: int        # populated only for engine errors
```

Single log line captured from the Godot process. `function` / `file` / `line` are populated for `_log_error` callbacks (push_error, push_warning, runtime errors); they're empty for `info` / `stderr` entries (`print` / `printerr`). `__str__` renders as `[LEVEL] message (file:line)` for use in failure reports.

### LogVerbosity

```python
class LogVerbosity(str, Enum):
    ERROR = "error"
    WARNING = "warning"   # default
    INFO = "info"
```

The wire-protocol values accepted by `set_log_verbosity` and `--e2e-log-verbosity`.

#### `parse_log_entries(raw)`

Convert a raw `_logs` array (as it arrives on the wire) into a list of `LogEntry` objects. Used internally by `GodotClient`; exposed for callers that bypass the high-level API.

---

## Exceptions

All exceptions inherit from `GodotE2EError`.

### GodotE2EError

```python
class GodotE2EError(Exception):
    """Base exception for all godot-e2e errors."""

    logs: list[LogEntry]  # engine logs captured during the failing command
```

Every exception carries a `logs` attribute populated from the failed command's `_logs` payload. Empty list when no logs were captured (or when log capture is inactive).

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

### EngineErrorFloodError

```python
class EngineErrorFloodError(GodotE2EError):
    error_count: int      # error-level entries in the detection window
    dropped_count: int    # ring-buffer overflow drops in the window
    window_seconds: float # the sliding-window duration
    samples: list[LogEntry]  # a few representative error lines from the flood
```

Raised by the next command after the [flood guard](#set_flood_detection-enablednone-window_secondsnone-error_thresholdnone) trips: the running game emitted a sustained per-frame error (or dropped-log) flood, so Godot was force-killed and the run fast-fails instead of idling to its timeout. The attributes carry the evidence that fired the detector, and the message names a sample error line so the failure self-diagnoses. Tune or disable the guard with [`set_flood_detection`](#set_flood_detection-enablednone-window_secondsnone-error_thresholdnone).

### CommandError

```python
class CommandError(GodotE2EError):
    """Raised when the server returns an error response."""
```

Raised when the Godot server returns an error that is not a "not found" error. This includes unknown commands, invalid properties, failed method calls, and other server-side errors.

### MultipleMatchesError

```python
class MultipleMatchesError(GodotE2EError):
    def __init__(self, message: str, paths: list):
        self.paths = paths  # list[str]
```

Raised by Locator actions when the query matches more than one node and no `.first()` / `.nth(i)` / `.filter(...)` was applied. The `paths` attribute carries the full list of matched node paths.

### NotActionableError

```python
class NotActionableError(GodotE2EError):
    def __init__(self, message: str, path: str, reasons: list, checks: dict):
        self.path = path
        self.reasons = reasons  # e.g. ["not_visible_in_tree"]
        self.checks = checks    # dict of per-check booleans
```

Raised by `Locator.click()` and `Locator.wait_visible()` when the actionability poll times out. The `reasons` list names every failed check (`"not_visible_in_tree"`, `"mouse_filter_ignore"`, `"outside_viewport"`).

### ExpectationFailedError

```python
class ExpectationFailedError(GodotE2EError, AssertionError):
    actual: Any                    # last observed value (meaningful only if observation_captured)
    observation_captured: bool     # True if at least one poll returned a value
    matcher: str                   # e.g. "to_have_text('Ready')"
    scene_tree: dict | None        # depth-4 dump of /root, None on dump failure
    timeout: float                 # the timeout that was exceeded
    last_error: Exception | None   # last CommandError swallowed during polling, if any
```

Raised when an `expect(locator).to_*` matcher fails to hold within its timeout. Dual-inherits `AssertionError` so pytest renders it the same way it renders a plain `assert` failure -- the message lands in the assertion section of the report, not as a generic exception traceback. Catching `GodotE2EError` still works for tooling that wants to treat it as a framework error.

`observation_captured` distinguishes "the poll observed `None`" from "no poll ever returned a value" (a node that never resolved, a stable multi-match without disambiguation, or persistent server errors). `last_error` is set when the polling loop kept catching `CommandError` -- typically a `get_property` against a property that doesn't exist on the resolved node, or transient command failures that never resolved before the timeout.

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
