# godot-e2e API Reference

Condensed reference for the `godot-e2e` Python client. The library has
**zero LLM training coverage** — do not guess method names or signatures,
look them up here. For worked recipes (movement, UI, scene transitions,
flaky-test mitigation, keep-alive, CI), see `testing-patterns.md`.

## Table of Contents

1. [Imports](#imports)
2. [Launch / Lifecycle](#launch--lifecycle)
3. [Locator — Semantic Queries](#locator--semantic-queries)
4. [expect() — Auto-Retry Assertions](#expect--auto-retry-assertions)
5. [Raw-Path Operations](#raw-path-operations)
6. [Input Simulation](#input-simulation)
7. [Frame & Time Synchronization](#frame--time-synchronization)
8. [Scene Management](#scene-management)
9. [Engine Log Capture](#engine-log-capture)
10. [Types & Exceptions](#types--exceptions)
11. [pytest Fixtures](#pytest-fixtures)
12. [Critical Rules](#critical-rules)

---

## Imports

```python
from godot_e2e import (
    GodotE2E,                 # launch / connect, the command surface
    expect, Locator, LocatorAssertions,
    Vector2, Vector2i, Vector3, Vector3i, Rect2, Rect2i,
    Color, Transform2D, NodePath,
    LogEntry, LogVerbosity, parse_log_entries,
    # exceptions
    GodotE2EError, NodeNotFoundError, TimeoutError, ConnectionLostError,
    CommandError, MultipleMatchesError, NotActionableError,
    ExpectationFailedError,
)
```

---

## Launch / Lifecycle

| Method | Description |
|---|---|
| `GodotE2E.launch(project_path, godot_path=None, port=0, timeout=10.0, extra_args=None, log_verbosity=None)` | Context manager. Launches Godot + connects. `port=0` auto-allocates (parallel-safe). `log_verbosity` ∈ `"error"`/`"warning"`/`"info"`. Bump `timeout` to 15-30s for CI. |
| `GodotE2E.connect(host="127.0.0.1", port=6008, token="")` | Connect to an already-running Godot launched with `--e2e`. |
| `game.close()` | Kill the Godot process and close the connection. |

```python
with GodotE2E.launch("./godot_project", timeout=15.0) as game:
    game.wait_for_node("/root/Main", timeout=10.0)
    ...
```

`--headless` is **not** supported (Godot bug #73557). On Linux CI use
`xvfb-run`; Windows/macOS provide a display by default.

---

## Locator — Semantic Queries

`Locator` is **lazy**: the query re-resolves on every action, so a Locator
created before `reload_scene()` still works afterward. Prefer Locators over
hardcoded paths — they survive scene-tree restructuring.

| Constructor | Description |
|---|---|
| `game.locator(path=, name=, group=, text=, type=, script=)` | At least one kwarg; AND-composed. `name`/`text` accept glob (`*`, `?`). `type` matches via `is X` (descendants included — `type="BaseButton"` covers `Button`/`CheckBox`/`OptionButton`/…). |
| `game.get_by_text(text)` | Sugar for `locator(text=text)`. |
| `game.get_by_button(text)` | Sugar for `locator(type="BaseButton", text=text)`. |

| Refinement | Returns | Description |
|---|---|---|
| `loc.filter(**kwargs)` | `Locator` | Add AND-composed predicates. |
| `loc.first()` / `loc.nth(i)` | `Locator` | Pick first / i-th match. |
| `loc.all()` | `list[Locator]` | Snapshot of all matches; `[]` if none (no raise). |
| `loc.locator(**kwargs)` | `Locator` | Sub-query under this Locator's resolved node (parent resolved at action time). |

| Inspection (no raise on miss) | Returns |
|---|---|
| `loc.exists()` / `loc.count()` | `bool` / `int` |
| `loc.is_visible()` / `loc.is_actionable()` | `bool` (raises on multi-match / missing) |

| Action (re-resolves; needs exactly one match) | Notes |
|---|---|
| `loc.click(*, force=False, timeout=5.0)` | Auto-waits actionability for `Control` (visible + mouse_filter + in viewport); `Node2D` checks visibility only. `force=True` skips the check. Raises `NotActionableError` on timeout. |
| `loc.hover()` | Inject `InputEventMouseMotion` at the node's screen position. |
| `loc.get_property(prop)` / `loc.set_property(prop, value)` / `loc.call(method, args=None)` | Path-pinned versions of the `game.*` calls. |
| `loc.wait_visible(*, timeout=5.0)` | Block until target passes actionability. Raises `NotActionableError` with `.reasons` + `.checks`. |
| `loc.wait_for_signal(signal_name, timeout=5.0)` | Block until the resolved node emits the signal. |

---

## expect() — Auto-Retry Assertions

`expect(locator, *, timeout=5.0, poll_interval=0.05) -> LocatorAssertions`
re-resolves the Locator on each poll. Lookup errors during polling
(`NodeNotFoundError`, `MultipleMatchesError`, `CommandError`) are caught —
the node may appear / disambiguate later. **Prefer this over manual
`wait + assert`**: it retries and attaches `scene_tree` + `last_error` to
failures.

| Matcher | Passes When |
|---|---|
| `to_have_property(name, value)` | `locator.get_property(name) == value` |
| `to_have_text(text)` | Target's `text` property equals (sugar for property `"text"`). |
| `to_be_visible()` | Visible in scene tree (Control / Node2D). For `Node3D`/`Window`/`Node`, use `to_satisfy(lambda l: l.get_property("visible"), description=...)`. |
| `to_exist()` | Query resolves to ≥1 node. |
| `to_satisfy(predicate, *, description=None)` | `predicate(locator)` truthy. **Always pass `description=`** — otherwise lambda failures print `repr(predicate)`. |

```python
expect(game.locator(group="player")).to_have_property("health", 100)
expect(game.locator(name="StatusLabel"), timeout=2.0).to_have_text("Ready")
expect(game.locator(group="enemies")).to_exist()
expect(player, timeout=3.0).to_satisfy(
    lambda l: l.get_property("position:x") > initial_x,
    description="player moved right",
)
```

`ExpectationFailedError` dual-inherits `AssertionError`, so pytest renders it
as a normal assertion failure. Attributes: `actual`, `observation_captured`,
`matcher`, `scene_tree`, `last_error`, `timeout`, `logs`.

---

## Raw-Path Operations

Direct on `game` — use only when you have a **stable known path** and a
Locator would just add ceremony (root-level singletons, autoloads, the
`Main` entry node).

| Method | Description |
|---|---|
| `game.node_exists(path) -> bool` | Path resolves to a node. |
| `game.get_property(path, prop)` | Read; supports dotted sub-property (`"position:x"`, `"global_position"`). |
| `game.set_property(path, prop, value)` | Write. |
| `game.call(path, method, args=None)` | Call a **public** method, returns result. `_private()` methods are not callable. |
| `game.find_by_group(group) -> list[str]` | Paths of all nodes in a group. |
| `game.query_nodes(pattern="", group="") -> list[str]` | Search by name pattern or group. |
| `game.get_tree(path="/root", depth=4) -> dict` | Scene-tree structure (debugging). |
| `game.batch(commands: list) -> list` | Multiple **instant** commands in one round-trip. Deferred commands (input, waits) return error entries. |

---

## Input Simulation

| Method | Description |
|---|---|
| `game.press_action(action_name, strength=1.0)` | Press **and** release (a tap, ~4 physics frames). |
| `game.input_action(action_name, pressed, strength=1.0)` | Set action state. **Needs 2 args.** Use `True`/`False` to hold/release for sustained movement. |
| `game.press_key(keycode)` | Tap a key. |
| `game.input_key(keycode, pressed, physical=False)` | Hold/release a raw keyboard key. Use this only when the game reads raw `InputEventKey` in `_input`/`_unhandled_input`, or you're deliberately testing a physical key. For anything mapped to an **Input Map action** — including `Input.get_axis()` / `Input.get_vector()`, which read action strengths — prefer `input_action`. |
| `game.click(x, y, button=1)` | Click a screen coordinate. |
| `game.click_node(path)` | Click at a node's screen position. |
| `game.input_mouse_button(x, y, button=1, pressed=True)` | Low-level mouse button. |
| `game.input_mouse_motion(x, y, relative_x=0, relative_y=0)` | Mouse motion. |

For sustained movement: `input_action(act, True)` → `wait_physics_frames(N)`
→ `input_action(act, False)`. `press_action` alone only taps.

`input_action` injects an `InputEventAction` via `Input.parse_input_event`, so
it updates the engine's action state: `Input.is_action_pressed`,
`get_action_strength`, `get_axis`, and `get_vector` all see it. This is the
default for movement — reach for `input_key` only when the game bypasses the
Input Map and reads raw key events directly.

---

## Frame & Time Synchronization

| Method | Use for |
|---|---|
| `game.wait_physics_frames(count=1)` | CharacterBody2D movement, collisions, RigidBody, `is_on_floor()`. **Required after movement input before asserting position.** |
| `game.wait_process_frames(count=1)` | Animation progress, UI transitions, `_process` logic. Does NOT advance physics. |
| `game.wait_seconds(seconds)` | Timer-gated / wall-clock-seconds waits. (Game time — affected by `Engine.time_scale`.) |
| `game.wait_for_node(path, timeout=5.0)` | Block until a node exists. |
| `game.wait_for_property(path, prop, value, timeout=5.0)` | Server-side poll until property equals value (faster than a Python loop). |
| `game.wait_for_signal(path, signal, timeout=5.0)` | Block until a node emits a signal (listener registers on arrival — earlier emissions are missed). |

Under headless uncapped FPS, frame counts elapse far faster than wall time —
use `wait_seconds` / `wait_for_property` for anything gated by a `Timer`.

---

## Scene Management

| Method | Description |
|---|---|
| `game.get_scene() -> str` | Current scene file path. |
| `game.change_scene(scene_path)` | Switch scene; blocks until loaded. Prefer over `reload_scene` when you need a clean load. |
| `game.reload_scene()` | Reload current scene. Resets the scene tree but NOT autoload/singleton state. |
| `game.screenshot(save_path="") -> str` | Capture a PNG, return its path. |

---

## Engine Log Capture

Every error carries the Godot logs that preceded it — read them first when
diagnosing a failure.

| Member | Description |
|---|---|
| `game.last_logs` | `LogEntry` list from the **most recent** command (cleared each command). |
| `game.collected_logs` | `LogEntry` list since reset (built-in fixtures clear this per test). |
| `game.reset_collected_logs()` | Narrow the window before a sub-assertion. |
| `game.set_log_verbosity(level)` | `"error"` / `"warning"` (default) / `"info"`. `"info"` adds `print()` but fills the buffer 4-10× faster. |
| `game.set_log_buffer_size(size)` | Resize the ring buffer (default 200). |
| `LogEntry` fields | `level`, `message`, `function`, `file`, `line` (last three populated for engine errors only). |
| `GodotE2EError.logs` | Every exception carries `.logs` from the failing command. |

Default verbosity `"warning"` captures `push_error`/`push_warning`; `print()`
is NOT captured unless you bump to `"info"`. pytest auto-includes a
`captured godot logs` section on failure — no setup needed.

---

## Types & Exceptions

Godot structs round-trip as the imported dataclasses (`Vector2`, `Color`, …).

| Exception | When |
|---|---|
| `NodeNotFoundError` | Node path doesn't exist. |
| `TimeoutError` | `wait_for_*` exceeded. Has `.scene_tree`. |
| `ConnectionLostError` | Godot crashed or the TCP connection dropped. |
| `CommandError` | The server returned an error. |
| `MultipleMatchesError` | A Locator action matched >1 node without `.first()`/`.nth()`/`.filter()`. Has `.paths`. |
| `NotActionableError` | `Locator.click()` / `wait_visible()` timed out on actionability. Has `.path`, `.reasons`, `.checks`. Reasons: `"not_visible_in_tree"`, `"mouse_filter_ignore"`, `"outside_viewport"`, `"unclickable_node_type"`. |
| `ExpectationFailedError` | `expect(...)` matcher exceeded timeout. Dual-inherits `AssertionError`. |

All inherit from `GodotE2EError` (which carries `.logs`).

---

## pytest Fixtures

The pytest plugin auto-registers two fixtures. Both reset `collected_logs`
at test entry and capture a screenshot on failure to `test_output/`.

| Fixture | Scope | Speed | Isolation | Use when |
|---|---|---|---|---|
| `game` | module process + per-test `reload_scene()` | Fast | Good | Default — most tests. |
| `game_fresh` | fresh process per test | Slow | Maximum | Tests that mutate autoload / singleton / static state. |

Project-path resolution order: `@pytest.mark.godot_project("path")` marker →
`godot_e2e_project_path` in `pytest.ini`/`pyproject.toml` →
`GODOT_E2E_PROJECT_PATH` env → auto-detect (`./godot_project`,
`../godot_project`, `.`). Godot binary: `GODOT_PATH` env or `--godot-path`.

Configure the project path with the resolution order above — no conftest
needed. Add a `conftest.py` (see `assets/conftest.py`) only for extra setup
such as a "skip the menu" fixture, and build it **on top of** the built-in
`game` (never redefine `game`/`game_fresh`, or you lose the
screenshot-on-failure teardown).

---

## Critical Rules

| # | Rule | Why |
|---|------|-----|
| 1 | Use `wait_physics_frames` after movement input | `wait_process_frames` does not advance physics — position/collision won't update. |
| 2 | Hold input for sustained movement | `press_action` only taps (~4 frames). Use `input_action(act, True/False)` around a wait. |
| 3 | `input_action` needs 2 args | `input_action("jump", True)`, not `input_action("jump")`. For a tap use `press_action`. |
| 4 | Prefer `expect()` over manual wait + assert | Retries with `scene_tree` + `last_error`, renders as a normal pytest assertion. |
| 5 | Assert **direction**, not exact values | `assert new_x > initial_x`, not `== 450.0`. Physics varies per machine. |
| 6 | Locators over hardcoded paths | `get_by_button("Start")` survives tree restructuring; `/root/Main/UI/Menu/StartButton` doesn't. |
| 7 | Read `.logs` on every failure | Each `GodotE2EError` carries what Godot printed during the failing command. |
| 8 | Use `wait_seconds`/`wait_for_property` for Timer waits | Frame counts fly by under headless uncapped FPS. |
| 9 | `input_action` can deadlock on pause | If the action sets `get_tree().paused = true`, physics stops and `input_action` (which waits 2 physics frames) hangs. Toggle pause via `call()` instead. |
