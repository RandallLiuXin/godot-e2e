"""Test suite conftest.py for godot-e2e."""

import pytest
import shutil
import os
import sys

# Add the python package to sys.path so we can import godot_e2e
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # up from tests/
sys.path.insert(0, os.path.join(REPO_ROOT, "python"))

from godot_e2e import GodotE2E, NodeNotFoundError, TimeoutError, ConnectionLostError, CommandError

GODOT_PROJECT = os.path.join(REPO_ROOT, "tests", "godot_project")
ADDON_SRC = os.path.join(REPO_ROOT, "addons", "godot_e2e")
ADDON_DST = os.path.join(GODOT_PROJECT, "addons", "godot_e2e")


# ---------------------------------------------------------------------------
# Addon copy + screenshot-on-failure plugin
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Copy the addon into the test project and register the screenshot plugin."""
    if os.path.exists(ADDON_DST):
        shutil.rmtree(ADDON_DST)
    shutil.copytree(ADDON_SRC, ADDON_DST)

    if not config.pluginmanager.has_plugin("godot_e2e_screenshot"):
        config.pluginmanager.register(_ScreenshotOnFailure(), "godot_e2e_screenshot")


class _ScreenshotOnFailure:
    """pytest plugin that stashes call reports so fixtures can detect failures."""

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        setattr(item, f"rep_{report.when}", report)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _game_process():
    """Module-scoped: one Godot process per test module."""
    with GodotE2E.launch(GODOT_PROJECT, timeout=30.0) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game


@pytest.fixture(scope="function")
def game(_game_process, request):
    """Function-scoped: reset to main scene between tests for a clean slate."""
    _game_process.change_scene("res://main.tscn")
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process

    # Screenshot on failure
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        _take_failure_screenshot(_game_process, request.node.name)


@pytest.fixture(scope="function")
def game_fresh(request):
    """Function-scoped: fresh Godot process per test (maximum isolation)."""
    with GodotE2E.launch(GODOT_PROJECT, timeout=30.0) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game

        if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
            _take_failure_screenshot(game, request.node.name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _take_failure_screenshot(game: GodotE2E, test_name: str):
    """Capture a screenshot on test failure and save it to ``test_output/``."""
    try:
        os.makedirs("test_output", exist_ok=True)
        safe_name = test_name.replace("/", "_").replace("\\", "_")
        path = os.path.join("test_output", f"{safe_name}_failure.png")
        game.screenshot(os.path.abspath(path))
        print(f"\n[godot-e2e] Failure screenshot saved: {path}")
    except Exception as e:
        print(f"\n[godot-e2e] Failed to capture screenshot: {e}")
