"""Test F11: Scene Management."""

import pytest


def test_get_scene(game):
    scene = game.get_scene()
    assert "main.tscn" in scene


def test_reload_scene(game):
    """Reload resets state."""
    game.call("/root/Main", "add_to_counter", [10])
    assert game.get_property("/root/Main", "counter") == 10
    game.reload_scene()
    game.wait_for_node("/root/Main", timeout=5.0)
    counter = game.get_property("/root/Main", "counter")
    assert counter == 0


def test_change_scene(game):
    """Change to test_level.tscn."""
    game.change_scene("res://test_level.tscn")
    game.wait_for_node("/root/TestLevel", timeout=5.0)
    scene = game.get_scene()
    assert "test_level.tscn" in scene


def test_change_scene_and_read_property(game):
    """After scene change, can read properties of new scene."""
    game.change_scene("res://test_level.tscn")
    game.wait_for_node("/root/TestLevel", timeout=5.0)
    name = game.get_property("/root/TestLevel", "level_name")
    assert name == "TestLevel"
