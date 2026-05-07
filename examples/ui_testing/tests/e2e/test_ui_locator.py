"""Locator-based mirror of test_ui.py.

Same coverage as the path-based version, no absolute paths.
"""

import pytest

from godot_e2e import (
    CommandError,
    MultipleMatchesError,
    NodeNotFoundError,
    NotActionableError,
)


# ---------------------------------------------------------------------------
# Same scenarios as test_ui.py, expressed via Locator
# ---------------------------------------------------------------------------

def test_initial_ui_state(game):
    title = game.get_by_text("UI Testing Demo").get_property("text")
    assert title == "UI Testing Demo"

    status = game.locator(name="StatusLabel").get_property("text")
    assert status == "Not clicked yet"


def test_button_click_updates_label(game):
    button = game.get_by_button("Click Me")
    button.click()
    game.wait_process_frames(2)

    status = game.locator(name="StatusLabel").get_property("text")
    assert status == "Clicked 1 times"

    button.click()
    game.wait_process_frames(2)

    status = game.locator(name="StatusLabel").get_property("text")
    assert status == "Clicked 2 times"


def test_navigate_to_detail_page(game):
    game.get_by_button("Go to Detail").click()
    game.wait_for_node("/root/Detail", timeout=5.0)

    label = game.get_by_text("Detail Page").get_property("text")
    assert label == "Detail Page"


def test_navigate_back_to_menu(game):
    game.get_by_button("Go to Detail").click()
    game.wait_for_node("/root/Detail", timeout=5.0)

    game.get_by_button("Back to Menu").click()
    game.wait_for_node("/root/Menu", timeout=5.0)

    title = game.get_by_text("UI Testing Demo").get_property("text")
    assert title == "UI Testing Demo"


# ---------------------------------------------------------------------------
# Locator-specific coverage
# ---------------------------------------------------------------------------

def test_multi_match_raises(game):
    """Two Buttons in the menu — bare query raises MultipleMatchesError."""
    with pytest.raises(MultipleMatchesError) as excinfo:
        game.locator(type="Button").get_property("text")
    assert len(excinfo.value.paths) == 2


def test_first_disambiguates(game):
    """`.first()` always picks the first match in tree-walk order."""
    text = game.locator(type="Button").first().get_property("text")
    assert text == "Click Me"


def test_nth_disambiguates(game):
    text = game.locator(type="Button").nth(1).get_property("text")
    assert text == "Go to Detail"


def test_all_returns_locators_per_match(game):
    buttons = game.locator(type="Button").all()
    assert len(buttons) == 2
    texts = [b.get_property("text") for b in buttons]
    assert texts == ["Click Me", "Go to Detail"]


def test_filter_narrows(game):
    """Filter to disambiguate two Buttons by text."""
    button = game.locator(type="Button").filter(text="Click Me")
    assert button.get_property("text") == "Click Me"


def test_glob_name(game):
    """Glob in `name` matches by node name (not by some other property that
    happens to share a value)."""
    matches = game.locator(name="*Label").all()
    names = sorted(b.get_property("name") for b in matches)
    assert names == ["StatusLabel", "TitleLabel"]


def test_glob_text(game):
    """Glob in `text` resolves to the dynamic label after clicks."""
    game.get_by_button("Click Me").click()
    game.wait_process_frames(2)
    # Now StatusLabel.text == "Clicked 1 times"
    label = game.locator(text="Clicked*")
    assert label.get_property("text") == "Clicked 1 times"


def test_type_instanceof(game):
    """`type=BaseButton` matches the Button subclass."""
    buttons = game.locator(type="BaseButton").all()
    assert len(buttons) == 2


def test_script_strategy(game):
    """`script=res://menu.gd` finds the menu root."""
    menu = game.locator(script="res://menu.gd")
    # The Control with menu.gd attached has a "click_count" property.
    assert menu.get_property("click_count") == 0


def test_chained_locator(game):
    """Parent.locator(...) scopes the child query under the parent's path."""
    vbox = game.locator(name="VBox")
    buttons = vbox.locator(type="Button").all()
    assert len(buttons) == 2


def test_chained_locator_requires_single_parent(game):
    """Multi-match parent without disambiguation raises at action time
    (chained Locators resolve the parent lazily so they can survive
    scene reloads). Construction and `.exists()` deliberately do not
    raise."""
    parent = game.locator(type="Button")  # 2 matches
    chained = parent.locator(name="anything")  # construction is silent
    assert chained.exists() is False        # exists() swallows the multi-match
    with pytest.raises(MultipleMatchesError):
        chained.get_property("text")


def test_no_match_raises_node_not_found(game):
    with pytest.raises(NodeNotFoundError):
        game.locator(name="DoesNotExist").get_property("text")


def test_exists_does_not_raise(game):
    assert game.locator(name="ClickButton").exists() is True
    assert game.locator(name="DoesNotExist").exists() is False


def test_count(game):
    assert game.locator(type="Button").count() == 2
    assert game.locator(type="Button").filter(text="Click Me").count() == 1
    assert game.locator(name="DoesNotExist").count() == 0


def test_is_visible_is_actionable(game):
    button = game.get_by_button("Click Me")
    assert button.is_visible() is True
    assert button.is_actionable() is True


def test_locator_survives_reload_scene(game):
    """A locator constructed before reload_scene resolves correctly after."""
    button = game.get_by_button("Click Me")
    button.click()
    game.wait_process_frames(2)

    game.reload_scene()
    game.wait_for_node("/root/Menu", timeout=5.0)

    # Same locator; resolves against the freshly reloaded tree.
    assert button.get_property("text") == "Click Me"


def test_hover(game):
    """hover() injects a motion event without clicking — counter stays 0."""
    button = game.get_by_button("Click Me")
    button.hover()
    game.wait_process_frames(2)

    menu = game.locator(script="res://menu.gd")
    assert menu.get_property("click_count") == 0


def test_force_skips_actionability(game):
    """force=True clicks without waiting; sanity check that it succeeds."""
    button = game.get_by_button("Click Me")
    button.click(force=True)
    game.wait_process_frames(2)
    status = game.locator(name="StatusLabel").get_property("text")
    assert status == "Clicked 1 times"


# ---------------------------------------------------------------------------
# Live-Godot coverage for the remaining Locator wrappers
# ---------------------------------------------------------------------------

def test_wait_visible_succeeds_when_already_actionable(game):
    """Happy path: returns immediately for a button that's already visible."""
    button = game.get_by_button("Click Me")
    button.wait_visible(timeout=2.0)


def test_wait_visible_raises_when_invisible(game):
    """Timeout path: hiding the Control surfaces a NotActionableError with
    the structured 'not_visible_in_tree' reason."""
    button = game.get_by_button("Click Me")
    button.set_property("visible", False)
    with pytest.raises(NotActionableError) as excinfo:
        button.wait_visible(timeout=0.3)
    assert "not_visible_in_tree" in excinfo.value.reasons


def test_set_property_round_trip(game):
    """set_property writes through Locator and is observable via is_visible()."""
    button = game.get_by_button("Click Me")
    assert button.is_visible() is True
    button.set_property("visible", False)
    assert button.is_visible() is False


def test_call_invokes_node_method(game):
    """call() invokes a Node method via Locator and the side effect is
    visible through other API surfaces."""
    button = game.get_by_button("Click Me")
    button.call("add_to_group", ["e2e_test_group"])
    members = game.find_by_group("e2e_test_group")
    assert any(p.endswith("ClickButton") for p in members)


def test_wait_for_signal_timeout_propagates(game):
    """wait_for_signal wrapper propagates the server-side timeout as a
    CommandError. (Happy-path firing is not exercised here because the
    blocking call cannot also click the button from the same thread.)"""
    button = game.get_by_button("Click Me")
    with pytest.raises(CommandError):
        button.wait_for_signal("pressed", timeout=0.3)
