# godot-e2e Testing Patterns and Best Practices

Worked recipes for writing reliable godot-e2e tests. For the full API
surface, see `api-reference.md`.

## Table of Contents

1. [Fixture Strategies](#fixture-strategies)
2. [Physics-Based Testing](#physics-based-testing)
3. [UI Testing (Locator + expect)](#ui-testing-locator--expect)
4. [State Verification](#state-verification)
5. [Scene Transition Testing](#scene-transition-testing)
6. [Log Capture for Debugging](#log-capture-for-debugging)
7. [Flaky Test Mitigation](#flaky-test-mitigation)
8. [Game State Survival Patterns](#game-state-survival-patterns)
9. [Batch Operations](#batch-operations)
10. [Debugging Tips](#debugging-tips)
11. [Common Gotchas](#common-gotchas)

---

## Fixture Strategies

### Strategy 1: Scene Reload (default, recommended)

One Godot process per test module; scene reloaded before each test.

```python
@pytest.fixture(scope="module")
def _game_process():
    with GodotE2E.launch(PROJECT_PATH, timeout=15.0) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game

@pytest.fixture(scope="function")
def game(_game_process):
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
```

Resets the scene tree, node properties, and script variables. **Limitation:**
global state (autoloads, singletons, static vars) persists between tests.

### Strategy 2: Fresh Process (maximum isolation)

```python
@pytest.fixture(scope="function")
def game_fresh():
    with GodotE2E.launch(PROJECT_PATH, timeout=15.0) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

For tests that mutate global state or crash-recovery tests. ~2-5s per test.

### Skip the main menu — jump straight to the scene under test

```python
@pytest.fixture(scope="module")
def _game_process():
    with GodotE2E.launch(PROJECT_PATH) as game:
        game.wait_for_node("/root", timeout=10.0)
        game.change_scene("res://levels/level1.tscn")
        game.wait_for_node("/root/Level1", timeout=5.0)
        yield game
```

For games with a menu in front of gameplay, add a `game_playing` fixture that
navigates past the menu so each gameplay test starts in the right state.

---

## Physics-Based Testing

Always `wait_physics_frames` for movement — `wait_process_frames` does NOT
advance physics.

```python
def test_player_moves_right(game):
    player = game.locator(group="player")
    initial_x = player.get_property("position:x")
    game.input_action("move_right", True)
    game.wait_physics_frames(10)
    game.input_action("move_right", False)
    expect(player).to_satisfy(
        lambda l: l.get_property("position:x") > initial_x,
        description="player moved right",
    )
```

| Wait | Use for |
|------|---------|
| `wait_physics_frames` | CharacterBody2D movement, collision, RigidBody, `is_on_floor()` |
| `wait_process_frames` | Animation progress, UI transitions, `_process` logic |
| `wait_seconds` | Timed events, cooldowns (game time) |
| `wait_for_property` | Any state that will eventually change (preferred over frame counts) |

Gravity/falling: Y increases downward. Jump: Y decreases upward.

```python
def test_player_jumps(game):
    game.wait_for_property("/root/Main/Player", "is_on_floor", True, timeout=3.0)
    initial_y = game.get_property("/root/Main/Player", "position:y")
    game.press_action("jump")
    game.wait_physics_frames(5)
    peak_y = game.get_property("/root/Main/Player", "position:y")
    assert peak_y < initial_y  # moved up
```

---

## UI Testing (Locator + expect)

`Locator` is lazy and re-resolves on every action. Use semantic queries
(`group=`, `type=`, `text=`) so tests survive scene refactors.

### Click a button by visible text

```python
def test_start_button_starts_game(game):
    game.get_by_button("Start Game").click()   # auto-waits actionability
    expect(game.locator(name="GameStatus")).to_have_text("Playing")
```

`get_by_button(text)` covers anything `is BaseButton` (Button, CheckBox,
OptionButton, MenuButton, LinkButton).

### Disambiguate ambiguous queries

```python
game.locator(type="Button").first().click()
game.locator(type="Button").nth(2).click()
game.locator(type="Button").filter(text="OK").click()
```

### Iterate matched nodes

```python
def test_all_enemies_take_damage(game):
    enemies = game.locator(group="enemies").all()
    assert len(enemies) > 0, "no enemies in scene"
    for enemy in enemies:
        before = enemy.get_property("health")
        enemy.call("take_damage", [10])
        assert enemy.get_property("health") == before - 10
```

### Wait for actionability / visibility without clicking

```python
def test_overlay_appears(game):
    panel = game.locator(name="GameOverPanel")
    game.set_property("/root/Main/Player", "health", 0)
    expect(panel).to_be_visible()
```

### Check a toggle

```python
def test_pause_menu_toggles(game):
    panel = game.locator(name="PauseMenu")
    assert not panel.is_visible()
    game.call("/root/Main", "toggle_pause")
    expect(panel).to_be_visible()
```

---

## State Verification

### Prefer wait_for_property over manual polling

```python
# GOOD: server-side poll (no per-iteration network round-trip)
game.wait_for_property("/root/Main", "score", 10, timeout=5.0)
```

### Trigger a pickup via teleportation

```python
def test_coin_increases_score(game):
    initial = game.get_property("/root/Main", "score")
    coin_pos = game.get_property("/root/Main/Coin", "global_position")
    game.set_property("/root/Main/Player", "global_position", coin_pos)
    game.wait_for_property("/root/Main", "score", initial + 1, timeout=2.0)
```

### Method call return values

```python
def test_increment_method(game):
    result = game.call("/root/Main", "increment")
    assert result == 1
    assert game.get_property("/root/Main", "counter") == 1
```

---

## Scene Transition Testing

```python
def test_level_transition(game):
    game.change_scene("res://levels/level2.tscn")   # blocks until loaded
    game.wait_for_node("/root/Level2", timeout=5.0)
    assert game.get_property("/root/Level2", "level_name") == "Level 2"
```

```python
def test_reach_game_over(game):
    # Drive the loop to a fail/exit state THROUGH PLAY, not by setting flags.
    game.set_property("/root/Main/Player", "health", 1)
    enemy = game.locator(group="enemies").first()
    game.set_property("/root/Main/Player", "global_position",
                      enemy.get_property("global_position"))
    expect(game.locator(name="GameOverScreen"), timeout=5.0).to_be_visible()
```

---

## Log Capture for Debugging

Every `GodotE2EError` carries `.logs`. pytest auto-includes a
`captured godot logs` section on failure.

### Assert no errors during a test

```python
def test_button_click_quietly(game):
    game.get_by_button("OK").click()
    expect(game.locator(name="Status")).to_have_text("done")
    errors = [e for e in game.collected_logs if e.level == "error"]
    assert not errors, f"unexpected errors: {[str(e) for e in errors]}"
```

The "no `level == 'error'` entries during this test" assertion is the
sweet spot — robust and high-signal. Avoid anchoring on exact engine error
strings (Godot version-sensitive) or log line counts (timing-sensitive).

### Capture print() output

```python
with GodotE2E.launch("./project", log_verbosity="info") as game:
    game.call("/root/Main", "noisy_method")
    info = [e for e in game.last_logs if e.level == "info"]
```

---

## Flaky Test Mitigation

1. **State-based over time-based** — `wait_for_property(..., True)` beats
   `wait_physics_frames(5); assert ...`.
2. **Direction over exact values** — `assert new_x > old_x`, not `== 450.0`.
3. **Generous timeouts** — 10s for initial load, 5s for state changes.
4. **Expose game state as properties** — add `is_on_ground`, `is_dead`,
   `current_level`, `is_paused` rather than inferring from positions.

---

## Game State Survival Patterns

Death, pause, and scene-reload mechanics can break the TCP connection
mid-test. These patterns prevent the most common failures.

### Keep-alive: prevent game-over during long waits

If the player can die from inaction (Flappy Bird, auto-scrollers), a long
wait kills the player and the scene reload drops the connection.

```python
def keep_alive(game, frames, action="flap", interval=15):
    elapsed = 0
    while elapsed < frames:
        chunk = min(interval, frames - elapsed)
        game.wait_physics_frames(chunk)
        elapsed += chunk
        if elapsed < frames:
            game.press_action(action)
```

### Pause handling: avoid input_action deadlock

`input_action` waits 2 physics frames internally. If the action sets
`get_tree().paused = true`, physics stops and it hangs forever.

```python
# WRONG: game.input_action("pause", True)  — may deadlock
game.call("/root/Main", "toggle_pause")     # RIGHT
game.wait_process_frames(2)                  # process frames still run when paused
```

### Scene reload breaking the connection

If game-over calls `get_tree().reload_current_scene()`, prefer driving the
test with `change_scene` to force a clean load:

```python
game.change_scene("res://main.tscn")
game.wait_for_node("/root/Main", timeout=5.0)
```

---

## Batch Operations

```python
results = game.batch([
    ("get_property", {"path": player, "property": "position:x"}),
    ("get_property", {"path": player, "property": "position:y"}),
    ("get_property", {"path": player, "property": "health"}),
])
x, y, health = results
```

Only **instant** commands work in batch. Deferred commands (input, waits,
change_scene) return error entries.

---

## Debugging Tips

### Server-side wire log

```python
with GodotE2E.launch(path, extra_args=["--", "--e2e-log"]) as game:
    ...   # logs every request/response on the Godot side
```

### Dump the scene tree

```python
import json
print(json.dumps(game.get_tree("/root", depth=3), indent=2))
```

### TimeoutError diagnosis

```python
try:
    game.wait_for_node("/root/Missing", timeout=2.0)
except TimeoutError as e:
    print("Scene tree at timeout:", json.dumps(e.scene_tree, indent=2))
```

### Interactive debugging

```bash
# Terminal 1
godot --path ./project -- --e2e --e2e-port=6008 --e2e-log
# Terminal 2
python -c "from godot_e2e import GodotE2E; g=GodotE2E.connect(port=6008); print(g.get_tree('/root', depth=2)); g.close()"
```

---

## Common Gotchas

1. **press_action vs held input** — `press_action` only taps. Hold with
   `input_action(act, True)` / `wait` / `input_action(act, False)`.
2. **input_action vs input_key** — `input_action` does NOT drive
   `Input.get_axis()` / `Input.get_vector()`. Use `input_key` with the mapped
   scancode for those.
3. **Signal timing** — `wait_for_signal` only catches signals emitted after
   the listener registers. Use `wait_for_property` for state assertions.
4. **Exact position assertions** — assert direction or ranges, not equality.
5. **Global state leaks** — `reload_scene` does not reset autoloads; use
   `game_fresh`.
6. **--headless not supported** — use `xvfb-run` on Linux CI.
7. **Batch limitations** — instant commands only.
8. **Timeout vs game time** — `wait_seconds` follows `Engine.time_scale`;
   `timeout=` parameters are always wall-clock.
