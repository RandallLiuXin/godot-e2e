"""Platformer example E2E test fixtures."""
import pytest
import os
import sys
import shutil

# conftest.py is at examples/platformer/tests/e2e/conftest.py
# EXAMPLE_ROOT = examples/platformer/ (3 levels up)
# REPO_ROOT = repo root (2 more levels up)
_HERE = os.path.abspath(os.path.dirname(__file__))
EXAMPLE_ROOT = os.path.dirname(os.path.dirname(_HERE))
REPO_ROOT = os.path.dirname(os.path.dirname(EXAMPLE_ROOT))

sys.path.insert(0, os.path.join(REPO_ROOT, "python"))

from godot_e2e import GodotE2E

GODOT_PROJECT = os.path.join(EXAMPLE_ROOT, "godot_project")
ADDON_SRC = os.path.join(REPO_ROOT, "addons", "godot_e2e")
ADDON_DST = os.path.join(GODOT_PROJECT, "addons", "godot_e2e")


def pytest_configure(config):
    if os.path.exists(ADDON_DST):
        shutil.rmtree(ADDON_DST)
    shutil.copytree(ADDON_SRC, ADDON_DST)


@pytest.fixture(scope="module")
def _game_process():
    with GodotE2E.launch(GODOT_PROJECT, timeout=30.0) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game


@pytest.fixture(scope="function")
def game(_game_process):
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
