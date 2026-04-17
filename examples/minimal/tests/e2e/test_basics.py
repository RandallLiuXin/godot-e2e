"""Minimal example: the simplest godot-e2e tests."""


def test_node_exists(game):
    """Verify the main scene loaded correctly."""
    assert game.node_exists("/root/Main")
    assert game.node_exists("/root/Main/Label")


def test_get_property(game):
    """Read a property from a node."""
    text = game.get_property("/root/Main/Label", "text")
    assert text == "Hello godot-e2e!"


def test_call_method(game):
    """Call a GDScript method and check its return value."""
    result = game.call("/root/Main", "increment")
    assert result == 1
    assert game.get_property("/root/Main", "counter") == 1
