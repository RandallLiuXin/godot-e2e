# Architecture and Protocol

This document describes how godot-e2e works internally: the two-process architecture, the TCP wire protocol, the server state machine, command categories, type serialization, and the security model.

---

## Two-Process Architecture

godot-e2e runs as two separate processes communicating over a local TCP connection:

```
+---------------------+          TCP (localhost)          +---------------------------+
|                     |  -------------------------------->|                           |
|   Python (pytest)   |  JSON commands (length-prefixed)  |   Godot (game process)    |
|                     |  <--------------------------------|                           |
|  - GodotE2E class   |  JSON responses (length-prefixed) |  - AutomationServer       |
|  - GodotClient      |                                  |    (Autoload node)        |
|  - GodotLauncher    |                                  |  - CommandHandler          |
|  - pytest fixtures   |                                  |  - JsonSerializer          |
+---------------------+                                  +---------------------------+
      Test runner                                              Game under test
```

**Python side** (test runner):
- `GodotLauncher` starts the Godot process with `--e2e` flags.
- `GodotClient` manages the TCP socket and length-prefix framing.
- `GodotE2E` provides the high-level synchronous API used in tests.

**Godot side** (game process):
- `AutomationServer` is an Autoload node that runs a TCP server.
- `CommandHandler` executes commands on the main thread.
- `JsonSerializer` handles type conversion between Godot types and JSON.
- `Config` parses `--e2e`, `--e2e-port`, `--e2e-port-file`, `--e2e-token`, `--e2e-log` from command-line args.

The key design principle is that the game runs unmodified -- the AutomationServer Autoload is dormant unless `--e2e` is present, and all commands execute on Godot's main thread within the normal game loop.

---

## TCP Protocol

### Wire Format

Every message (both requests and responses) uses the same framing:

```
+------------------+------------------+
| 4 bytes          | N bytes          |
| payload length   | UTF-8 JSON       |
| (big-endian u32) | payload          |
+------------------+------------------+
```

The 4-byte header is a big-endian unsigned 32-bit integer specifying the byte length of the JSON payload that follows.

### Request Format

```json
{
    "id": 1,
    "action": "get_property",
    "path": "/root/Main/Player",
    "property": "position"
}
```

Every request has:
- `id` -- integer, monotonically increasing, used to match responses.
- `action` -- string, the command name.
- Additional fields depend on the command.

### Response Format (success)

```json
{
    "id": 1,
    "result": {"_t": "v2", "x": 400.0, "y": 300.0}
}
```

Or for commands with no return value:

```json
{
    "id": 2,
    "ok": true
}
```

### Response Format (error)

```json
{
    "id": 3,
    "error": "node_not_found",
    "message": "Node not found: /root/Nonexistent"
}
```

### Handshake

The first command after connecting must be `hello`:

**Request**:
```json
{
    "id": 1,
    "action": "hello",
    "token": "a1b2c3...",
    "protocol_version": 1
}
```

**Response**:
```json
{
    "id": 1,
    "ok": true,
    "godot_version": "4.4.0",
    "server_version": "1.0.0"
}
```

If the token does not match, the server responds with an `auth_failed` error and disconnects. Any command sent before `hello` results in a `not_authenticated` error and immediate disconnection.

### Request/Response Examples

**node_exists**:
```
-> {"id": 2, "action": "node_exists", "path": "/root/Main/Player"}
<- {"id": 2, "exists": true}
```

**set_property** (with type tag):
```
-> {"id": 3, "action": "set_property", "path": "/root/Main/Player",
    "property": "position", "value": {"_t": "v2", "x": 100.0, "y": 200.0}}
<- {"id": 3, "ok": true}
```

**wait_physics_frames** (deferred):
```
-> {"id": 4, "action": "wait_physics_frames", "count": 5}
   (server waits 5 physics frames before responding)
<- {"id": 4, "ok": true}
```

**batch**:
```
-> {"id": 5, "action": "batch", "commands": [
     {"action": "get_property", "path": "/root/Main", "property": "counter"},
     {"action": "node_exists", "path": "/root/Main/Enemy"}
   ]}
<- {"id": 5, "results": [
     {"id": null, "result": 0},
     {"id": null, "exists": true}
   ]}
```

---

## Server State Machine

The AutomationServer uses a state machine with five states:

```
                     +--- connection available ---+
                     |                            |
                     v                            |
+-------------+   +------+   +------------+   +---------+
| DISCONNECTED|-->| IDLE |-->| EXECUTING  |-->| WAITING |
+-------------+   +------+   +------------+   +---------+
      ^              |                            |
      |              +--- connection lost ---------+
      |                                           |
      +--- connection lost -----------------------+
      |
      +--- go back to LISTENING
      |
      v
+------------+
| LISTENING  |
+------------+
```

### States

| State | Description |
|-------|-------------|
| `LISTENING` | TCP server is accepting connections. No client connected. |
| `IDLE` | Client connected and authenticated. Server is polling for incoming messages. |
| `EXECUTING` | A command is being dispatched (transient -- moves to IDLE or WAITING immediately). |
| `WAITING` | A deferred command is in progress. The server polls for completion each frame. |
| `DISCONNECTED` | Client disconnected or connection lost. Server resets and returns to LISTENING. |

### Transitions

1. **LISTENING -> IDLE**: A client TCP connection is accepted.
2. **IDLE -> IDLE**: An instant command is received, executed, and responded to immediately.
3. **IDLE -> WAITING**: A deferred command is received. The server enters the appropriate wait type.
4. **WAITING -> IDLE**: The deferred operation completes (frames elapsed, node found, property matched, etc.).
5. **WAITING -> IDLE (timeout)**: The wait exceeds its timeout. An error response is sent.
6. **IDLE/WAITING -> DISCONNECTED**: The TCP connection drops or the peer disconnects.
7. **DISCONNECTED -> LISTENING**: The server resets all state and begins accepting new connections.

### Wait Types

When the server enters the WAITING state, it tracks which condition to poll for:

| WaitType | Trigger | Completion Condition |
|----------|---------|---------------------|
| `PROCESS_FRAMES` | `wait_process_frames` | Counter decremented each `_process` reaches zero. |
| `PHYSICS_FRAMES` | `wait_physics_frames`, input commands | Counter decremented each `_physics_process` reaches zero. |
| `SECONDS` | `wait_seconds` | Elapsed game time reaches target. |
| `NODE_EXISTS` | `wait_for_node` | `get_node_or_null(path)` returns non-null. |
| `SIGNAL_EMITTED` | `wait_for_signal` | The target signal fires (one-shot connection). |
| `PROPERTY_VALUE` | `wait_for_property` | `node.get(property) == expected_value`. |
| `SCENE_CHANGE` | `change_scene`, `reload_scene` | `current_scene.scene_file_path` matches the target (or any scene is loaded). |

All wait types support a wall-clock timeout (converted from seconds to milliseconds). If the timeout expires, the server sends a `timeout` error and transitions to IDLE.

---

## Command Categories

### Instant Commands

These execute synchronously in a single frame and respond immediately:

| Command | Description |
|---------|-------------|
| `hello` | Handshake / authentication. |
| `node_exists` | Check if a node exists. |
| `get_property` | Read a property value. |
| `set_property` | Write a property value. |
| `call_method` | Call a method on a node. |
| `find_by_group` | Find nodes by group name. |
| `query_nodes` | Query nodes by pattern/group. |
| `get_tree` | Get a scene tree snapshot. |
| `batch` | Execute multiple instant commands. |
| `get_scene` | Get current scene path. |
| `screenshot` | Capture a viewport screenshot. |
| `quit` | Terminate the Godot process. |

### Deferred Commands

These inject an event or request a wait, then respond after the condition is met:

| Command | Wait Type | Responds After |
|---------|-----------|----------------|
| `input_key` | `PHYSICS_FRAMES` (2) | 2 physics frames (input is processed). |
| `input_action` | `PHYSICS_FRAMES` (2) | 2 physics frames. |
| `input_mouse_button` | `PHYSICS_FRAMES` (2) | 2 physics frames. |
| `input_mouse_motion` | `PHYSICS_FRAMES` (2) | 2 physics frames. |
| `click_node` | `PHYSICS_FRAMES` (2) | 2 physics frames. |
| `wait_process_frames` | `PROCESS_FRAMES` | N process frames. |
| `wait_physics_frames` | `PHYSICS_FRAMES` | N physics frames. |
| `wait_seconds` | `SECONDS` | N in-game seconds. |
| `wait_for_node` | `NODE_EXISTS` | Node appears in tree (or timeout). |
| `wait_for_signal` | `SIGNAL_EMITTED` | Signal is emitted (or timeout). |
| `wait_for_property` | `PROPERTY_VALUE` | Property equals value (or timeout). |
| `change_scene` | `SCENE_CHANGE` | New scene is loaded. |
| `reload_scene` | `SCENE_CHANGE` | Scene is reloaded. |

Deferred commands cannot be used inside a `batch` -- the server returns an error for any deferred command encountered within a batch.

---

## Type Serialization

Values crossing the wire use `_t` type tags to preserve Godot types through JSON:

| Godot Type | `_t` Tag | JSON Fields | Python Type |
|------------|----------|-------------|-------------|
| `Vector2` | `v2` | `x`, `y` | `Vector2(x, y)` |
| `Vector2i` | `v2i` | `x`, `y` | `Vector2i(x, y)` |
| `Vector3` | `v3` | `x`, `y`, `z` | `Vector3(x, y, z)` |
| `Vector3i` | `v3i` | `x`, `y`, `z` | `Vector3i(x, y, z)` |
| `Rect2` | `r2` | `x`, `y`, `w`, `h` | `Rect2(x, y, w, h)` |
| `Rect2i` | `r2i` | `x`, `y`, `w`, `h` | `Rect2i(x, y, w, h)` |
| `Color` | `col` | `r`, `g`, `b`, `a` | `Color(r, g, b, a)` |
| `Transform2D` | `t2d` | `x` (v2), `y` (v2), `o` (v2) | `Transform2D(x, y, origin)` |
| `NodePath` | `np` | `v` (string) | `NodePath(path)` |
| (unsupported) | `_unknown` | `_class`, `_str` | Raw dict passthrough |

Primitives (`bool`, `int`, `float`, `String`) pass through without tags. Arrays and dictionaries are recursively serialized/deserialized.

On the Godot side, the `JsonSerializer` class also handles `PackedVector2Array`, `PackedFloat32Array`, `PackedInt32Array`, and `PackedStringArray` by converting them to plain arrays.

---

## How Input Simulation Works

When a test calls an input method (e.g., `input_action("ui_right", True)`):

1. **Python** sends the command over TCP.
2. **Godot server** (in `_process`) receives and dispatches the command.
3. **CommandHandler** creates the appropriate `InputEvent` (e.g., `InputEventAction`) and calls `Input.parse_input_event(event)`.
4. The command returns a **deferred** response with `wait_type: "physics_frames"` and `count: 2`.
5. **AutomationServer** enters the WAITING state and decrements the physics frame counter in `_physics_process`.
6. After 2 physics frames, the response is sent back.
7. **Python** receives the response and the `input_action` call returns.

The 2-physics-frame wait is critical: Godot processes input events during `_physics_process`, so waiting ensures the input has been fully processed (including movement, collision detection, etc.) before the test reads any state.

For hold-style input (e.g., holding a direction), the test must:
1. Send `input_action("ui_right", True)` -- press.
2. Call `wait_physics_frames(N)` -- let N physics frames run with input held.
3. Send `input_action("ui_right", False)` -- release.

---

## How Scene Changes Work

When `change_scene` or `reload_scene` is called:

1. **CommandHandler** calls `get_tree().change_scene_to_file(path)`.
2. The command returns a deferred response with `wait_type: "scene_change"` and the target `scene_path`.
3. Each frame, the server polls `get_tree().current_scene`:
   - Checks if `current_scene` is not null.
   - Checks if `current_scene.scene_file_path` matches the target path.
4. Once the condition is met, the response is sent.

For `reload_scene`, the target path is the current scene's own `scene_file_path`, so the server waits until the scene is fully reloaded.

---

## Security Model

godot-e2e is designed for local testing environments only. The security model has two layers:

### 1. The --e2e flag

The AutomationServer checks `Config.is_enabled()` in `_ready()`. If the `--e2e` flag is not present in command-line arguments, the server disables all processing and never opens a TCP socket. This means:

- Normal game execution is unaffected.
- Production builds (exported games) will not have the server active unless explicitly launched with `--e2e`.
- The flag is passed after the `--` separator in the command line, so Godot itself does not process it.

### 2. Token authentication

When the launcher starts Godot, it generates a random 16-byte hex token (`secrets.token_hex(16)`) and passes it via `--e2e-token=X`. The Python client must send this token in the `hello` handshake.

If the token does not match:
- The server sends an `auth_failed` error.
- The connection is immediately closed.

This prevents other processes on the same machine from connecting to the automation server. When connecting manually (without the launcher), you can set the token to empty string on both sides to skip authentication.

### Network Binding

The TCP server binds to `127.0.0.1` (localhost only), so it is not accessible from other machines on the network. The Python client also connects to `127.0.0.1` by default.
