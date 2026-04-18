**English** | [中文](README.zh-CN.md)

# godot-e2e

[![CI](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml/badge.svg)](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/godot-e2e)](https://pypi.org/project/godot-e2e/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://pypi.org/project/godot-e2e/)
[![Godot](https://img.shields.io/badge/Godot-4.x-blue?logo=godotengine)](https://godotengine.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green)](LICENSE)

Out-of-process E2E testing tool for Godot

---

## Quick Start

**1. Install the addon**

Copy `addons/godot_e2e/` into your Godot project's `addons/` directory, then enable the
**GodotE2E** plugin in **Project > Project Settings > Plugins**. This automatically registers
the `AutomationServer` autoload.

The server is completely dormant unless the game is launched with the `--e2e` flag, so it has
no effect in production builds.

**2. Install the Python package**

```bash
pip install godot-e2e
```

Or install from source:

```bash
pip install -e .
```

**3. Write a test**

```python
from godot_e2e import GodotE2E

def test_player_moves(game):
    initial_x = game.get_property("/root/Main/Player", "position:x")
    game.press_action("move_right")
    game.wait_physics_frames(10)
    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x
```

Run:

```bash
godot-e2e tests/ -v
```

---

## Features

- **Out-of-process** — game runs in a separate process; crashes are isolated and timeouts are safe
- **No engine modifications** — works with standard Godot 4.x binaries
- **Synchronous Python API** — no async/await required in test code
- **Input simulation** — keyboard, mouse clicks, named actions
- **Node operations** — get/set properties, call methods, group lookup, node existence checks
- **Frame synchronization** — wait for process frames, physics frames, or game time
- **Scene management** — change scene, reload scene
- **Screenshot capture** — manual or automatic on test failure (pytest integration)
- **pytest fixtures** — built-in fixtures with configurable test isolation strategies

---

## How It Works

Two processes communicate over a local TCP connection:

1. **Python (pytest)** — sends JSON-encoded commands and waits for responses
2. **Godot (AutomationServer)** — an Autoload that listens on a TCP port, executes commands on
   the main thread, and sends back results

The `AutomationServer` only opens its socket when the game is started with `--e2e` (and
optionally `--e2e-port=<port>`). When `--e2e-port=0` is used with `--e2e-port-file=<path>`, the
server picks a random available port and writes it to the given file — this enables running
multiple instances in parallel. In normal play or exported builds without the `--e2e` flag, the
autoload does nothing.

```
pytest ──── TCP (localhost) ──── AutomationServer (Godot Autoload)
  sends: {"cmd": "get_property", "path": "/root/Main/Player", "prop": "position:x"}
  gets:  {"ok": true, "value": 400.0}
```

---

## pytest Fixtures

Three isolation strategies are available depending on your needs.

### Strategy 1: reload_scene (default, fast)

Reloads the current scene between each test. Cheap and usually sufficient.

```python
# conftest.py
import pytest
from godot_e2e import GodotE2E

GODOT_PROJECT = "/path/to/your/project"

@pytest.fixture(scope="module")
def _game_process():
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game

@pytest.fixture(scope="function")
def game(_game_process):
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
```

### Strategy 2: game_fresh (strongest isolation)

Launches a brand new Godot process for each test. Slowest but fully isolated.

```python
@pytest.fixture(scope="function")
def game_fresh():
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

### Strategy 3: Shared session (fastest)

One process for the entire test session. Use when tests are carefully ordered and
do not share mutable state.

```python
@pytest.fixture(scope="session")
def game_session():
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

---

## CI Configuration

### Linux (GitHub Actions, headless via Xvfb)

```yaml
- name: Install Godot
  run: |
    wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_linux.x86_64.zip
    unzip -q Godot_v4.4-stable_linux.x86_64.zip
    sudo mv Godot_v4.4-stable_linux.x86_64 /usr/local/bin/godot

- name: Run E2E tests
  run: |
    pip install -e .
    xvfb-run --auto-servernum godot-e2e tests/e2e/ -v
```

### Windows (GitHub Actions)

```yaml
- name: Install Godot
  run: |
    Invoke-WebRequest -Uri "https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_win64.exe.zip" -OutFile godot.zip
    Expand-Archive godot.zip -DestinationPath C:\godot
  shell: pwsh

- name: Run E2E tests
  run: |
    pip install -e .
    godot-e2e tests/e2e/ -v
  env:
    GODOT_PATH: C:\godot\Godot_v4.4-stable_win64.exe
```

### macOS (GitHub Actions)

```yaml
- name: Install Godot
  run: |
    wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_macos.universal.zip
    unzip -q Godot_v4.4-stable_macos.universal.zip
    sudo mv "Godot.app" /Applications/Godot.app

- name: Run E2E tests
  run: |
    pip install -e .
    godot-e2e tests/e2e/ -v
  env:
    GODOT_PATH: /Applications/Godot.app/Contents/MacOS/Godot
```

Set `GODOT_PATH` to override the default Godot executable path, or use `godot-e2e --godot-path /path/to/godot tests/`.
The default search order is: `GODOT_PATH` environment variable, then `godot`, `godot4`, `Godot_v4` on `PATH`.

---

## API Reference

### Launch / Lifecycle

| Method | Description |
|---|---|
| `GodotE2E.launch(project_path, **kwargs)` | Context manager. Launches Godot and returns a connected `GodotE2E` instance. Pass `port=0` (default) to auto-allocate a free port. |
| `GodotE2E.connect(host, port, token)` | Connect to an already-running Godot instance with the `--e2e` flag. |
| `game.close()` | Terminate the Godot process and close the connection. |

### Node Operations

| Method | Description |
|---|---|
| `game.node_exists(path)` | Returns `True` if the node at `path` exists in the scene tree. |
| `game.wait_for_node(path, timeout=5.0)` | Blocks until the node exists or timeout is reached. |
| `game.get_property(path, prop)` | Get a property value. Supports dotted paths like `"position:x"`. |
| `game.set_property(path, prop, value)` | Set a property value on a node. |
| `game.call_method(path, method, *args)` | Call a method on a node and return the result. |
| `game.find_by_group(group)` | Return a list of node paths for all nodes in the given group. |

### Input Simulation

| Method | Description |
|---|---|
| `game.press_action(action)` | Press and immediately release a named input action. |
| `game.input_action(action, pressed)` | Set a named input action pressed state. |
| `game.key_press(scancode)` | Press and release a key by scancode. |
| `game.mouse_click(x, y, button=1)` | Click a mouse button at the given screen coordinates. |

### Frame Synchronization

| Method | Description |
|---|---|
| `game.wait_frames(n)` | Wait for `n` process (`_process`) frames to complete. |
| `game.wait_physics_frames(n)` | Wait for `n` physics (`_physics_process`) frames to complete. |
| `game.wait_seconds(t)` | Wait for `t` in-game seconds (affected by `Engine.time_scale`). |

### Scene Management

| Method | Description |
|---|---|
| `game.change_scene(scene_path)` | Change to a scene by `res://` path. |
| `game.reload_scene()` | Reload the current scene. |

### Diagnostics

| Method | Description |
|---|---|
| `game.screenshot(path=None)` | Capture a screenshot. Returns PNG bytes; saves to `path` if given. |

---

## Examples

| Example | Description |
|---|---|
| [minimal](examples/minimal/) | Simplest setup — node checks, property reading, method calls (3 tests) |
| [platformer](examples/platformer/) | Player movement, scoring, groups, scene reload (5 tests) |
| [ui_testing](examples/ui_testing/) | Button clicks, label verification, scene navigation (5 tests) |

Run any example:

```bash
cd examples/minimal
godot-e2e tests/e2e/ -v
```

---

## License

Apache 2.0. See [LICENSE](LICENSE).
