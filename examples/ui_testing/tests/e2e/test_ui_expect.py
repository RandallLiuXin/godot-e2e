"""Real-Godot integration tests for ``expect()`` auto-retry assertions.

Exercises every matcher against a live engine. The polling-success
tests use the ``e2e_set_*_after`` hooks on Menu to schedule a delayed
state change, then immediately assert with a timeout that's larger
than the delay — the assertion must poll past the delay and pass.
"""

import time
import pytest

from godot_e2e import ExpectationFailedError, expect


# ---------------------------------------------------------------------------
# Happy paths — state already correct at expect() time
# ---------------------------------------------------------------------------

def test_to_have_text_passes_immediately(game):
    expect(game.locator(name="StatusLabel"), timeout=1.0).to_have_text(
        "Not clicked yet"
    )  # initial scene state


def test_to_have_property_passes_immediately(game):
    expect(game.locator(name="Menu")).to_have_property("click_count", 0)


def test_to_be_visible_passes_immediately(game):
    expect(game.locator(name="ClickButton")).to_be_visible()


def test_to_exist_passes_immediately(game):
    expect(game.locator(type="Button")).to_exist()


# ---------------------------------------------------------------------------
# Polling — delayed state change must be picked up before timeout
# ---------------------------------------------------------------------------

def test_to_have_text_polls_until_delayed_change(game):
    game.call("/root/Menu", "e2e_set_text_after", ["DELAYED", 0.4])
    started = time.monotonic()
    expect(game.locator(name="StatusLabel"), timeout=3.0).to_have_text("DELAYED")
    elapsed = time.monotonic() - started
    # Polling must have actually waited for the timer (~0.4s); if it
    # passed in <0.2s the helper fired synchronously, which would be a
    # bug in the helper (silently invalidates the polling test).
    assert elapsed > 0.2, f"helper fired too fast ({elapsed:.2f}s)"


def test_to_have_property_polls_until_counter_changes(game):
    game.call("/root/Menu", "e2e_set_counter_after", [42, 0.3])
    started = time.monotonic()
    expect(game.locator(name="Menu"), timeout=3.0).to_have_property("click_count", 42)
    elapsed = time.monotonic() - started
    # Must actually wait for the timer (~0.3s); a synchronous helper
    # regression or polling early-exit would let this pass with
    # elapsed near 0.
    assert elapsed > 0.15, f"helper fired too fast ({elapsed:.2f}s)"


def test_to_be_visible_polls_until_button_shown(game):
    # Hide first (synchronously), then schedule a delayed re-show.
    game.set_property("/root/Menu/VBox/ClickButton", "visible", False)
    game.call("/root/Menu", "e2e_set_button_visible_after", [True, 0.3])
    started = time.monotonic()
    expect(game.locator(name="ClickButton"), timeout=3.0).to_be_visible()
    elapsed = time.monotonic() - started
    assert elapsed > 0.15, f"helper fired too fast ({elapsed:.2f}s)"


def test_to_exist_polls_through_scene_reload(game):
    # reload_scene tears down the current Menu node, then rebuilds it.
    # to_exist must ride the gap.
    game.reload_scene()
    expect(game.locator(name="Menu"), timeout=5.0).to_exist()


# ---------------------------------------------------------------------------
# to_satisfy — composes Locator methods, uses description
# ---------------------------------------------------------------------------

def test_to_satisfy_with_locator_predicate(game):
    game.call("/root/Menu", "e2e_set_counter_after", [10, 0.3])
    expect(game.locator(name="Menu"), timeout=3.0).to_satisfy(
        lambda loc: loc.get_property("click_count") >= 10,
        description="click_count >= 10",
    )


def test_to_satisfy_combines_visibility_and_text(game):
    game.call("/root/Menu", "e2e_set_text_after", ["Ready", 0.3])
    expect(game.locator(name="StatusLabel"), timeout=3.0).to_satisfy(
        lambda loc: loc.is_visible() and loc.get_property("text") == "Ready",
        description="StatusLabel is visible and reads 'Ready'",
    )


# ---------------------------------------------------------------------------
# Failures — message, attached scene_tree, AssertionError compatibility
# ---------------------------------------------------------------------------

def test_failure_message_includes_last_observed_value(game):
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(game.locator(name="StatusLabel"), timeout=0.3).to_have_text(
            "this text never appears"
        )
    assert excinfo.value.actual == "Not clicked yet"
    assert "Not clicked yet" in str(excinfo.value)


def test_failure_attaches_scene_tree(game):
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(game.locator(name="Menu"), timeout=0.3).to_have_property(
            "click_count", 99999
        )
    # scene_tree may be None if the dump itself fails, but in the happy
    # case (live engine) we expect a populated dict rooted at "root".
    assert excinfo.value.scene_tree is not None
    assert isinstance(excinfo.value.scene_tree, dict)


def test_failure_when_node_never_resolves(game):
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(
            game.locator(name="DoesNotExistAnywhere"), timeout=0.3
        ).to_have_property("text", "x")
    assert excinfo.value.actual is None
    assert "no successful observation" in str(excinfo.value)


def test_expectation_failed_is_assertion_error(game):
    # pytest's `raises(AssertionError)` must catch ExpectationFailedError
    # so users get assertion-style failure rendering for free.
    with pytest.raises(AssertionError):
        expect(
            game.locator(name="StatusLabel"), timeout=0.3
        ).to_have_text("nope")
