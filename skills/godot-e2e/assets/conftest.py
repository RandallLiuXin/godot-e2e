"""Optional godot-e2e conftest for this project.

You usually do NOT need this file. The godot-e2e pytest plugin already ships
the `game` and `game_fresh` fixtures, and `game` reloads the scene between
tests *and* captures a screenshot to `test_output/` on failure. Prefer
configuring the project path without a conftest:

  - pyproject.toml:  [tool.pytest.ini_options]
                     godot_e2e_project_path = "path/to/project"
  - or pytest.ini:   [pytest]
                     godot_e2e_project_path = path/to/project
  - or env var:      GODOT_E2E_PROJECT_PATH=path/to/project
  - or per test:     @pytest.mark.godot_project("path/to/project")

Godot binary: set the GODOT_PATH env var (or pass --godot-path to godot-e2e).

Keep this file only when you need something the built-ins don't provide — the
common case being a "skip the menu" fixture that starts each gameplay test
already past the main menu.

IMPORTANT: do NOT redefine `game` / `game_fresh` here. Overriding them drops
the plugin's screenshot-on-failure teardown (see godot_e2e/fixtures.py).
Instead, build ADDITIVE fixtures that depend on the built-in `game`, as below —
the built-in teardown still runs, so failure screenshots keep working.
"""
import pytest


@pytest.fixture(scope="function")
def game_playing(game):
    """Gameplay-ready fixture: reuse the built-in `game`, then navigate past
    the menu so each test starts in the scene under test.

    Depends on the built-in `game` fixture, so scene-reload isolation and the
    screenshot-on-failure teardown are inherited — you only add the navigation.
    Adjust the button text / target node to match your project.
    """
    game.get_by_button("Start Game").click()
    game.wait_for_node("/root/Main/Level", timeout=5.0)
    return game
