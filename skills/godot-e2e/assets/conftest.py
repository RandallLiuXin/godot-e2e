"""godot-e2e fixtures for this project.

Copy this file to your test directory (e.g. tests/e2e/conftest.py) and adjust:
  - GODOT_PROJECT : path to the directory containing project.godot
  - "/root/Main"  : your entry-scene root node — read it from project.godot's
                    run/main_scene (the .tscn's root node name).

You usually do NOT need this file: the godot-e2e pytest plugin already
provides `game` and `game_fresh` fixtures and can auto-detect the project.
Keep a custom conftest.py when you want explicit control over the project
path, the entry-scene wait path, or a "skip the menu" fixture.

Godot binary: set GODOT_PATH env var (or pass --godot-path to godot-e2e).
"""
import os

import pytest

from godot_e2e import GodotE2E

# Directory that contains project.godot. Adjust the relative hop as needed.
GODOT_PROJECT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


@pytest.fixture(scope="module")
def _game_process():
    """One Godot process shared across all tests in a module."""
    with GodotE2E.launch(GODOT_PROJECT, timeout=15.0) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game


@pytest.fixture(scope="function")
def game(_game_process):
    """Reload the entry scene before each test (fast, good isolation)."""
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process


@pytest.fixture(scope="function")
def game_fresh():
    """Fresh Godot process per test — use for tests that mutate autoload state."""
    with GodotE2E.launch(GODOT_PROJECT, timeout=15.0) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
