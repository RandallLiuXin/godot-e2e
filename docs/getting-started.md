# Getting Started with godot-e2e

This guide walks you through installing godot-e2e, setting up your Godot project, writing your first test, and running tests locally and in CI.

---

## Prerequisites

- **Godot 4.x** -- any standard Godot 4 binary (editor or headless).
- **Python 3.9+** -- required by the Python test client.
- **pytest 7.0+** -- the test runner. Installed automatically as a dependency.

---

## Installation

### From source (development)

Clone the repository and install in editable mode:

```bash
git clone https://github.com/your-org/godot-e2e.git
cd godot-e2e
pip install -e .
```

This installs the `godot_e2e` Python package from the `python/` directory and registers the pytest plugin automatically.

### From PyPI (when published)

```bash
pip install godot-e2e
```

---

## Setting Up the Godot Addon

### Step 1: Copy the addon

Copy the `addons/godot_e2e/` directory from this repository into your Godot project's `addons/` directory:

```
your_game/
  addons/
    godot_e2e/
      automation_server.gd
      command_handler.gd
      config.gd
      json_serializer.gd
  scenes/
  project.godot
```

### Step 2: Add the Autoload

In Godot, go to **Project > Project Settings > Autoload** and add a new entry:

| Field | Value |
|-------|-------|
| Path  | `res://addons/godot_e2e/automation_server.gd` |
| Name  | `AutomationServer` |

Use the script directly (not a scene file). In the Godot UI this corresponds to the `*` prefix notation: `*res://addons/godot_e2e/automation_server.gd`.

### Step 3: Understand the --e2e flag

The AutomationServer is **completely dormant** unless the game is launched with the `--e2e` command-line flag. When the flag is absent:

- No TCP server is created.
- No processing occurs (`set_process(false)`, `set_physics_process(false)`).
- There is zero runtime overhead in production builds.

When `--e2e` is present, the server listens on a TCP port (default 6008) and accepts commands from the Python test client.

Additional flags parsed from command-line arguments (passed after `--`):

| Flag | Description |
|------|-------------|
| `--e2e` | Enable the automation server. Required. |
| `--e2e-port=N` | TCP port to listen on (default: 6008). Use `0` for auto-selection. |
| `--e2e-port-file=PATH` | Write the actual listening port to this file. Used with `--e2e-port=0` for multi-instance support. |
| `--e2e-token=X` | Authentication token. The Python client must send this in the handshake. |
| `--e2e-log` | Enable verbose server-side logging to stdout. |

The launcher passes all of these automatically when you use `GodotE2E.launch()`.

---

## Writing Your First Test

### Step 1: Create a test file

Create a file called `tests/test_basic.py`:

```python
def test_player_exists(game):
    """Verify the Player node is present in the scene tree."""
    assert game.node_exists("/root/Main/Player")
```

The `game` fixture is provided by godot-e2e's pytest plugin. It launches Godot, connects over TCP, and reloads the scene between tests.

### Step 2: Create a conftest.py

If you want manual control over fixtures (recommended), create `tests/conftest.py`:

```python
import pytest
import os
from godot_e2e import GodotE2E

GODOT_PROJECT = os.path.join(os.path.dirname(__file__), "..", "godot_project")


@pytest.fixture(scope="module")
def _game_process():
    """One Godot process shared across all tests in this module."""
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game


@pytest.fixture(scope="function")
def game(_game_process):
    """Reset to the main scene before each test."""
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
```

### Step 3: Add a more interesting test

```python
def test_player_moves_right(game):
    """Hold the right action for 10 physics frames and verify movement."""
    initial_x = game.get_property("/root/Main/Player", "position:x")

    game.input_action("ui_right", True)       # Press
    game.wait_physics_frames(10)               # Let physics run
    game.input_action("ui_right", False)       # Release

    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x, f"Player should move right: {initial_x} -> {new_x}"
```

Key points:
- `input_action` simulates a named Godot input action (defined in Project Settings > Input Map).
- `wait_physics_frames` ensures physics steps actually run before reading the result.
- The sub-property syntax `"position:x"` accesses `node.position.x` via Godot's indexed property notation.

---

## Running Tests

### Basic usage

```bash
godot-e2e tests/ -v
```

### Setting the Godot executable path

godot-e2e looks for the Godot binary in this order:

1. `GODOT_PATH` environment variable.
2. Common executable names on `PATH`: `godot`, `godot4`, `Godot_v4`.

To set it explicitly:

```bash
# Linux / macOS
export GODOT_PATH=/usr/local/bin/godot
godot-e2e tests/ -v

# Windows (PowerShell)
$env:GODOT_PATH = "C:\godot\Godot_v4.4-stable_win64.exe"
godot-e2e tests/ -v
```

### Setting the project path

The test fixtures locate your Godot project in this order:

1. `@pytest.mark.godot_project("path")` marker on the test or module.
2. `godot_e2e_project_path` key in `pytest.ini` or `pyproject.toml`.
3. `GODOT_E2E_PROJECT_PATH` environment variable.
4. Auto-detection: searches `./godot_project`, `../godot_project`, and `.` for a `project.godot` file.

### Verbose server-side logging

Pass `--e2e-log` as an extra argument to see the Godot server's request/response log. This requires passing extra args through the launcher:

```python
with GodotE2E.launch(project_path, extra_args=["--", "--e2e-log"]) as game:
    ...
```

Note: the launcher already passes `--e2e`, `--e2e-port`, and `--e2e-token` automatically.

---

## CI Setup

### Linux (GitHub Actions with Xvfb)

Godot requires a display server on Linux. Use `xvfb-run` to provide a virtual framebuffer:

```yaml
name: E2E Tests (Linux)

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Godot
        run: |
          wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_linux.x86_64.zip
          unzip -q Godot_v4.4-stable_linux.x86_64.zip
          sudo mv Godot_v4.4-stable_linux.x86_64 /usr/local/bin/godot

      - name: Install dependencies
        run: pip install -e .

      - name: Run E2E tests
        run: xvfb-run --auto-servernum godot-e2e tests/ -v
```

### Windows (GitHub Actions)

Windows does not require a virtual display:

```yaml
name: E2E Tests (Windows)

on: [push, pull_request]

jobs:
  e2e:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Godot
        shell: pwsh
        run: |
          Invoke-WebRequest -Uri "https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_win64.exe.zip" -OutFile godot.zip
          Expand-Archive godot.zip -DestinationPath C:\godot

      - name: Install dependencies
        run: pip install -e .

      - name: Run E2E tests
        run: godot-e2e tests/ -v
        env:
          GODOT_PATH: C:\godot\Godot_v4.4-stable_win64.exe
```

### macOS (GitHub Actions)

```yaml
name: E2E Tests (macOS)

on: [push, pull_request]

jobs:
  e2e:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Godot
        run: |
          wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_macos.universal.zip
          unzip -q Godot_v4.4-stable_macos.universal.zip
          sudo mv "Godot.app" /Applications/Godot.app

      - name: Install dependencies
        run: pip install -e .

      - name: Run E2E tests
        run: godot-e2e tests/ -v
        env:
          GODOT_PATH: /Applications/Godot.app/Contents/MacOS/Godot
```

### Tips for CI

- **Timeouts**: increase the `timeout` parameter in `GodotE2E.launch()` for CI environments (10-15 seconds), since first launch can be slow.
- **Screenshots on failure**: the built-in screenshot-on-failure plugin saves PNGs to `test_output/`. Upload this directory as a build artifact for debugging.
- **Headless Godot**: if you have a headless Godot build, you can use it instead of `xvfb-run` on Linux.

---

## Next Steps

- [API Reference](api-reference.md) -- full documentation of every method, type, and exception.
- [Architecture](architecture.md) -- how the TCP protocol and server state machine work.
- [Testing Patterns](testing-patterns.md) -- best practices for writing reliable E2E tests.
