# Testing Patterns and Best Practices

This guide covers patterns, strategies, and tips for writing reliable E2E tests with godot-e2e.

---

## Fixture Strategies

godot-e2e supports three test isolation strategies, each with different tradeoffs between speed and isolation.

### Strategy 1: Scene Reload (default, recommended)

One Godot process per test module. The scene is reloaded before each test.

```python
@pytest.fixture(scope="module")
def _game_process():
    with GodotE2E.launch(PROJECT_PATH) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game

@pytest.fixture(scope="function")
def game(_game_process):
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
```

**When to use**: Most tests. Scene reload resets the scene tree, node properties, and script variables. This is fast (no process startup overhead) and provides good isolation.

**Limitations**: Global state that lives outside the scene (singletons, autoloads, static variables) persists between tests. If your game uses global state, use `change_scene` back to a known scene or use `game_fresh`.

### Strategy 2: Fresh Process (maximum isolation)

A new Godot process for every test function.

```python
@pytest.fixture(scope="function")
def game_fresh():
    with GodotE2E.launch(PROJECT_PATH) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

**When to use**: Tests that modify global state (autoload properties, singletons), tests that need a completely clean slate, or tests that verify crash recovery.

**Limitations**: Slow. Each test pays the cost of launching Godot and establishing a connection (~2-5 seconds). Use sparingly.

### Strategy 3: Shared Session (fastest)

One Godot process for the entire test session.

```python
@pytest.fixture(scope="session")
def game_session():
    with GodotE2E.launch(PROJECT_PATH) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

**When to use**: Read-only tests that do not mutate game state, or when you need the absolute fastest execution and are willing to manage test ordering manually.

**Limitations**: No automatic reset between tests. Tests must clean up after themselves or be carefully ordered. A crash in one test terminates the session.

---

## Physics-Based Testing

### Use wait_physics_frames for movement tests

Godot processes movement and physics in `_physics_process`. If your game moves a character in `_physics_process`, you must wait for physics frames to see the result:

```python
def test_player_moves_right(game):
    initial_x = game.get_property("/root/Main/Player", "position:x")
    game.input_action("ui_right", True)
    game.wait_physics_frames(10)          # Let physics run
    game.input_action("ui_right", False)
    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x
```

### Why not wait_process_frames for movement?

`wait_process_frames` waits for `_process` frames, which are visual/render frames. Physics runs on a separate tick rate (default 60 Hz). If your movement code is in `_physics_process` (as is standard for `CharacterBody2D`), waiting for process frames may not advance physics.

Always use `wait_physics_frames` when testing:
- Character movement
- Collision detection
- RigidBody behavior
- Any logic in `_physics_process`

Use `wait_process_frames` for:
- Animation progress
- UI transitions
- Anything in `_process`

---

## UI Testing

### Clicking a node directly

Use `click_node` to click at a Control or Node2D's screen position without calculating coordinates manually:

```python
def test_button_click(game):
    game.click_node("/root/Main/UI/StartButton")
    game.wait_for_node("/root/GameLevel", timeout=5.0)
```

The server computes the click position:
- **Control nodes**: center of `get_global_rect()`.
- **Node2D nodes**: viewport-transformed global position.

### Clicking at screen coordinates

For precise positioning or non-node targets:

```python
game.click(400, 300)                    # Click at center of 800x600 window
game.input_mouse_button(400, 300, 1, True)   # Mouse down
game.input_mouse_button(400, 300, 1, False)  # Mouse up
```

---

## State Verification

### Prefer wait_for_property over polling

Instead of reading a property in a loop:

```python
# Bad: manual polling
for _ in range(100):
    game.wait_physics_frames(1)
    if game.get_property("/root/Main", "score") == 10:
        break
else:
    assert False, "Score never reached 10"
```

Use `wait_for_property`, which polls on the Godot side (faster, no network round-trips per poll):

```python
# Good: server-side polling
game.wait_for_property("/root/Main", "score", 10, timeout=5.0)
```

### Reading properties after actions

Always wait for the appropriate number of frames after an input before reading state:

```python
def test_press_increments_counter(game):
    game.press_action("ui_accept")
    # press_action already waits 2 physics frames internally (press + release)
    counter = game.get_property("/root/Main", "counter")
    assert counter == 1
```

---

## Group-Based Node Lookup

### Prefer groups over hardcoded paths

Node paths like `"/root/Main/Enemies/Enemy1"` are fragile -- they break if you reorganize the scene tree. Instead, add nodes to groups and look them up dynamically:

```python
# Fragile: breaks if Enemy1 is moved
game.get_property("/root/Main/Enemies/Enemy1", "health")

# Robust: finds the node wherever it lives
enemies = game.find_by_group("enemies")
for enemy_path in enemies:
    health = game.get_property(enemy_path, "health")
    assert health > 0
```

### Combining groups with patterns

Use `query_nodes` to filter by both group and name pattern:

```python
# All boss enemies (in "enemies" group, name starts with "Boss")
bosses = game.query_nodes(pattern="Boss*", group="enemies")
```

---

## Scene Transition Testing

### Verify the new scene loads

Always call `wait_for_node` after `change_scene` to ensure the new scene is ready before reading its state:

```python
def test_level_transition(game):
    game.change_scene("res://levels/level2.tscn")
    game.wait_for_node("/root/Level2", timeout=5.0)
    level_name = game.get_property("/root/Level2", "level_name")
    assert level_name == "Level 2"
```

`change_scene` is deferred -- it blocks until the new scene's root is available, but you should still use `wait_for_node` if you need to access child nodes that may take additional frames to initialize.

### Verifying the current scene

```python
scene = game.get_scene()
assert "level2.tscn" in scene
```

### Reload for state reset

```python
def test_reload_resets_state(game):
    game.call("/root/Main", "add_to_counter", [10])
    assert game.get_property("/root/Main", "counter") == 10

    game.reload_scene()
    game.wait_for_node("/root/Main", timeout=5.0)

    counter = game.get_property("/root/Main", "counter")
    assert counter == 0
```

---

## Screenshot on Failure

### How it works

The built-in pytest plugin stashes test result reports on each test item. When a test using the `game` or `game_fresh` fixture fails, the fixture's teardown phase checks for the failure and captures a screenshot.

Screenshots are saved to:

```
test_output/<test_name>_failure.png
```

The path is printed to stdout:

```
[godot-e2e] Failure screenshot saved: test_output/test_player_moves_right_failure.png
```

### Manual screenshots

You can capture screenshots at any point in a test:

```python
def test_visual_state(game):
    game.press_action("ui_accept")
    path = game.screenshot("/tmp/after_accept.png")
    assert os.path.isfile(path)
```

If no path is provided, screenshots are saved to Godot's `user://e2e_screenshots/` directory with a timestamp filename.

### CI artifact collection

In CI, upload the `test_output/` directory as a build artifact:

```yaml
- name: Upload failure screenshots
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: e2e-failure-screenshots
    path: test_output/
```

---

## Flaky Test Mitigation

### Use wait_for_property instead of wait_frames for state changes

Frame-based waits are inherently timing-dependent. A test that works locally may fail in CI where frame rates differ:

```python
# Flaky: depends on frame timing
game.press_action("ui_accept")
game.wait_physics_frames(5)
assert game.get_property("/root/Main", "animation_done") is True
```

Instead, wait for the actual state:

```python
# Stable: waits until condition is met
game.press_action("ui_accept")
game.wait_for_property("/root/Main", "animation_done", True, timeout=5.0)
```

### Use directional assertions over exact values

Physics simulation can produce slightly different values depending on frame rate and timing:

```python
# Fragile: exact position depends on frame timing
assert game.get_property("/root/Main/Player", "position:x") == 450.0

# Robust: verify direction of movement
initial_x = game.get_property("/root/Main/Player", "position:x")
game.input_action("ui_right", True)
game.wait_physics_frames(10)
game.input_action("ui_right", False)
new_x = game.get_property("/root/Main/Player", "position:x")
assert new_x > initial_x    # Direction, not exact value
```

### Generous timeouts

Use comfortable timeouts, especially for CI:

```python
game.wait_for_node("/root/Main", timeout=10.0)    # 10s for initial load
game.wait_for_property("/root/Main", "ready", True, timeout=5.0)
```

---

## Batch Operations for Performance

When you need to read multiple properties, use `batch` to make a single network round-trip:

```python
# Slow: 3 round-trips
x = game.get_property("/root/Main/Player", "position:x")
y = game.get_property("/root/Main/Player", "position:y")
health = game.get_property("/root/Main/Player", "health")

# Fast: 1 round-trip
results = game.batch([
    ("get_property", {"path": "/root/Main/Player", "property": "position:x"}),
    ("get_property", {"path": "/root/Main/Player", "property": "position:y"}),
    ("get_property", {"path": "/root/Main/Player", "property": "health"}),
])
x, y, health = results
```

Batch only supports instant commands. Deferred commands (input, waits) return an error if included in a batch.

---

## Debugging Tips

### Enable server-side logging

The `--e2e-log` flag makes the Godot server print every request and response to stdout:

```
[godot-e2e] server listening on port 6008
[godot-e2e] client connected
[godot-e2e] << hello (id=1)
[godot-e2e] >> {"id":1,"ok":true,"godot_version":"4.4.0","server_version":"0.1.0"}
[godot-e2e] << get_property (id=2)
[godot-e2e] >> {"id":2,"result":{"_t":"v2","x":400.0,"y":300.0}}
```

To enable logging when using the launcher, pass the flag as an extra argument. Note that `--e2e-log` must be passed after the `--` separator (the launcher handles `--e2e`, `--e2e-port`, and `--e2e-token` automatically, but `--e2e-log` must be added explicitly):

```python
with GodotE2E.launch(project_path, extra_args=["--e2e-log"]) as game:
    ...
```

### Inspect the scene tree

Use `get_tree` to dump the current scene tree when a test fails or behaves unexpectedly:

```python
tree = game.get_tree("/root", depth=3)
import json
print(json.dumps(tree, indent=2))
```

The `TimeoutError` exception from `wait_for_node` automatically includes a scene tree dump in its `scene_tree` attribute:

```python
try:
    game.wait_for_node("/root/Main/MissingNode", timeout=2.0)
except TimeoutError as e:
    print("Scene tree at timeout:")
    print(json.dumps(e.scene_tree, indent=2))
```

### Connect to a running game

For interactive debugging, start Godot manually with `--e2e` and connect from Python:

```bash
godot --path ./my_project -- --e2e --e2e-port=6008 --e2e-log
```

```python
from godot_e2e import GodotE2E

game = GodotE2E.connect(port=6008)
print(game.get_tree("/root", depth=2))
game.close()
```

### Verify crash recovery

Use the `game_fresh` fixture for tests that intentionally crash or kill the Godot process:

```python
def test_crash_recovery(game_fresh):
    assert game_fresh.node_exists("/root/Main") is True

    # Kill the process
    game_fresh._launcher.process.kill()
    game_fresh._launcher.process.wait()

    # Next command raises ConnectionLostError
    with pytest.raises(ConnectionLostError):
        game_fresh.get_property("/root/Main", "counter")
```
