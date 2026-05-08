---
hide:
  - navigation
  - toc
---

# godot-e2e

[![CI](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml/badge.svg)](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/godot-e2e)](https://pypi.org/project/godot-e2e/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://pypi.org/project/godot-e2e/)
[![Godot](https://img.shields.io/badge/Godot-4.5%2B-blue?logo=godotengine)](https://godotengine.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green)](https://github.com/RandallLiuXin/godot-e2e/blob/main/LICENSE)

**Out-of-process E2E testing for Godot 4.5+, driven from Python.**

godot-e2e launches your real game as a child process, drives it over a TCP wire protocol, and lets you assert on the running scene tree from pytest. No mocks, no in-engine test runner, no async/await — just synchronous Python code that exercises the same binary your players will run.

---

## Why godot-e2e

<div class="grid cards" markdown>

-   :material-shield-check: **Out-of-process by design**

    The game runs in its own process. A crash, a hang, or an infinite loop in the game can't take your test runner down with it.

-   :material-puzzle-outline: **No engine modifications**

    Works with stock Godot 4.5+ binaries. No custom builds, no patched headers, no recompilation. The addon is dormant unless launched with `--e2e`.

-   :material-language-python: **Synchronous Python API**

    No `async`/`await` discipline to learn. `game.click_at(...)`, `game.get_property(...)`, `expect(locator).to_be_visible()` — all blocking calls.

-   :material-test-tube: **pytest-native**

    Ships as a pytest plugin with a configurable `game` fixture. Auto-screenshot on failure, log capture on the failed report, parametrized scenes — all wired in.

</div>

---

## 30-second example

Install the Python package:

```bash
pip install godot-e2e
```

Copy `addons/godot_e2e/` into your Godot project, enable **GodotE2E** in **Project Settings → Plugins**, then write a test:

```python
from godot_e2e import expect

def test_player_moves_right(game):
    player = game.locator(name="Player")
    initial_x = player.get_property("position:x")

    game.press_action("move_right")
    game.wait_physics_frames(10)

    expect(player).to_satisfy(
        lambda p: p.get_property("position:x") > initial_x,
        description="player position.x increased after move_right",
    )
```

Run it:

```bash
godot-e2e tests/ -v
```

The `game` fixture launches your Godot project with the `--e2e` flag, hands you a connected client, and tears it down at the end of the test.

---

## Where to next

<div class="grid cards" markdown>

-   :material-rocket-launch: [**Getting Started**](getting-started.md)

    Install, configure `GODOT_PATH`, write your first test, run it locally and in CI.

-   :material-book-open-variant: [**API Reference**](api-reference.md)

    Every method, type, and exception. Locator, expect, the `GodotE2E` client, log capture, scene management.

-   :material-sitemap: [**Architecture**](architecture.md)

    How the TCP wire protocol works, the server's state machine, and the launcher / client boundary.

-   :material-clipboard-check-outline: [**Testing Patterns**](testing-patterns.md)

    Best practices learned the hard way: scene isolation, frame synchronization, dealing with flake.

</div>

---

## Compatibility

| godot-e2e   | Godot   | Python |
| ----------- | ------- | ------ |
| 1.2.x       | 4.5+    | 3.9+   |
| 1.0 – 1.1.x | 4.x     | 3.9+   |

Bumping the minimum supported Godot version is treated as a MINOR bump — see [Versioning](versioning.md).

---

## Project links

- **PyPI:** [pypi.org/project/godot-e2e](https://pypi.org/project/godot-e2e/)
- **Godot Asset Library:** search for *godot-e2e*
- **Source / Issues:** [github.com/RandallLiuXin/godot-e2e](https://github.com/RandallLiuXin/godot-e2e)
- **Roadmap:** [ROADMAP.md](https://github.com/RandallLiuXin/godot-e2e/blob/main/ROADMAP.md)
- **License:** Apache-2.0
