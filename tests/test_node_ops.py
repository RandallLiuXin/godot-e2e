"""Test F2: Node Operations + F8: JSON Serialization."""

import pytest


def test_node_exists_true(game):
    assert game.node_exists("/root/Main") is True
    assert game.node_exists("/root/Main/Player") is True
    assert game.node_exists("/root/Main/Label") is True


def test_node_exists_false(game):
    assert game.node_exists("/root/Nonexistent") is False


def test_get_property_string(game):
    text = game.get_property("/root/Main", "test_string")
    assert text == "Hello E2E"


def test_get_property_int(game):
    counter = game.get_property("/root/Main", "counter")
    assert counter == 0


def test_get_property_float(game):
    speed = game.get_property("/root/Main", "player_speed")
    assert speed == 200.0


def test_get_property_vector2(game):
    """F8: Vector2 serialization round-trip."""
    pos = game.get_property("/root/Main/Player", "position")
    if hasattr(pos, "x"):
        assert pos.x == 400.0
        assert pos.y == 300.0
    else:
        assert pos["x"] == 400.0
        assert pos["y"] == 300.0


def test_get_property_sub_property(game):
    """F8: Sub-property access via colon notation."""
    x = game.get_property("/root/Main/Player", "position:x")
    assert x == 400.0


def test_set_property(game):
    game.set_property("/root/Main", "test_string", "Modified")
    result = game.get_property("/root/Main", "test_string")
    assert result == "Modified"


def test_set_property_vector2(game):
    """F8: Vector2 deserialization (set_property)."""
    from godot_e2e import Vector2

    game.set_property("/root/Main/Player", "position", Vector2(100.0, 200.0))
    pos = game.get_property("/root/Main/Player", "position")
    if hasattr(pos, "x"):
        assert pos.x == 100.0
        assert pos.y == 200.0
    else:
        assert pos["x"] == 100.0
        assert pos["y"] == 200.0


def test_call_method(game):
    result = game.call("/root/Main", "get_counter")
    assert result == 0


def test_call_method_with_args(game):
    result = game.call("/root/Main", "add_to_counter", [5])
    assert result == 5
    counter = game.get_property("/root/Main", "counter")
    assert counter == 5


def test_batch_operations(game):
    """F2: Batch command."""
    results = game.batch([
        {"action": "get_property", "path": "/root/Main", "property": "counter"},
        {"action": "get_property", "path": "/root/Main", "property": "test_string"},
        {"action": "node_exists", "path": "/root/Main/Player"},
    ])
    assert len(results) == 3


def test_get_tree(game):
    tree = game.get_tree("/root/Main", depth=1)
    assert tree["name"] == "Main"
    assert tree["type"] == "Node2D"
    children_names = [c["name"] for c in tree["children"]]
    assert "Label" in children_names
    assert "Player" in children_names
