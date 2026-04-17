"""pytest fixtures for godot-e2e."""

import pytest
import os
from .commands import GodotE2E


def pytest_configure(config):
    """Register the screenshot-on-failure plugin (idempotent)."""
    if not config.pluginmanager.has_plugin("godot_e2e_screenshot"):
        config.pluginmanager.register(ScreenshotOnFailure(), "godot_e2e_screenshot")


class ScreenshotOnFailure:
    """pytest plugin that captures screenshots on test failure."""

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        # Stash the call report on the test item so fixtures can access it.
        setattr(item, f"rep_{report.when}", report)


@pytest.fixture(scope="module")
def _game_instance(request):
    """Module-scoped: one Godot process per test module."""
    project_path = _get_project_path(request)
    godot_path = _get_godot_path(request)

    with GodotE2E.launch(project_path, godot_path=godot_path) as game:
        yield game


@pytest.fixture(scope="function")
def game(_game_instance, request):
    """Function-scoped fixture: reload the scene between tests and capture a
    screenshot on failure.

    Requires a module-scoped ``_game_instance`` to be in scope (one Godot
    process shared across all tests in the same module).
    """
    _game_instance.reload_scene()
    _game_instance.wait_for_node("/root", timeout=5.0)
    yield _game_instance

    # Screenshot on failure
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        _take_failure_screenshot(_game_instance, request.node.name)


@pytest.fixture(scope="function")
def game_fresh(request):
    """Function-scoped fixture: fresh Godot process per test (maximum isolation).

    Use this when tests must not share any Godot state at all.
    """
    project_path = _get_project_path(request)
    godot_path = _get_godot_path(request)

    with GodotE2E.launch(project_path, godot_path=godot_path) as game:
        yield game

        # Screenshot on failure
        if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
            _take_failure_screenshot(game, request.node.name)


# ---------------------------------------------------------------------------
# Internal helpers
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


def _get_project_path(request) -> str:
    """Resolve the Godot project path from multiple sources (in priority order):

    1. ``@pytest.mark.godot_project("path")`` marker on the test/module.
    2. ``godot_e2e_project_path`` key in ``pytest.ini`` / ``pyproject.toml``.
    3. ``GODOT_E2E_PROJECT_PATH`` environment variable.
    4. Auto-detection: searches ``./godot_project``, ``../godot_project``, and
       ``.`` for a ``project.godot`` file.
    """
    # 1. Marker
    marker = request.node.get_closest_marker("godot_project")
    if marker:
        return marker.args[0]

    # 2. pytest config key
    try:
        config_path = request.config.getini("godot_e2e_project_path")
        if config_path:
            return config_path
    except (ValueError, KeyError):
        pass

    # 3. Environment variable
    env_path = os.environ.get("GODOT_E2E_PROJECT_PATH", "")
    if env_path:
        return env_path

    # 4. Auto-detection
    for candidate in ["./godot_project", "../godot_project", "."]:
        if os.path.isfile(os.path.join(candidate, "project.godot")):
            return candidate

    raise FileNotFoundError(
        "Could not find a Godot project. Set the GODOT_E2E_PROJECT_PATH "
        "environment variable, add 'godot_e2e_project_path' to your pytest "
        "configuration, or use @pytest.mark.godot_project('path/to/project') "
        "on your test class or module."
    )


def _get_godot_path(request) -> str | None:
    """Return the path to the Godot executable, or None to use PATH lookup.

    Reads from the ``GODOT_PATH`` environment variable.
    """
    return os.environ.get("GODOT_PATH") or None
