"""Test F3: Input Simulation."""

import pytest


def test_input_action_ui_accept(game):
    """Press ui_accept -- counter increments."""
    counter_before = game.get_property("/root/Main", "counter")
    game.press_action("ui_accept")
    counter_after = game.get_property("/root/Main", "counter")
    assert counter_after == counter_before + 1


def test_input_action_multiple(game):
    """Multiple presses stack up."""
    game.press_action("ui_accept")
    game.press_action("ui_accept")
    game.press_action("ui_accept")
    counter = game.get_property("/root/Main", "counter")
    assert counter == 3


def test_input_key_movement(game):
    """Press right arrow -- player moves right via ui_right action."""
    initial_x = game.get_property("/root/Main/Player", "position:x")
    game.input_action("ui_right", True)
    game.wait_physics_frames(10)
    game.input_action("ui_right", False)
    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x, f"Player should move right: {initial_x} -> {new_x}"


def test_input_mouse_button(game):
    """Mouse click does not crash (basic smoke test)."""
    game.input_mouse_button(400, 300, button=1, pressed=True)
    game.input_mouse_button(400, 300, button=1, pressed=False)


def test_input_mouse_motion(game):
    """Mouse motion does not crash (basic smoke test)."""
    game.input_mouse_motion(100, 100, relative_x=50, relative_y=50)
