"""Test F2: Group-Based Node Lookup."""

import pytest


def test_find_by_group_single(game):
    players = game.find_by_group("player")
    assert len(players) == 1
    assert "/root/Main/Player" in players[0]


def test_find_by_group_multiple(game):
    enemies = game.find_by_group("enemies")
    assert len(enemies) == 2
    paths = [str(p) for p in enemies]
    assert any("Enemy1" in p for p in paths)
    assert any("Enemy2" in p for p in paths)


def test_find_by_group_empty(game):
    result = game.find_by_group("nonexistent_group")
    assert result == []


def test_query_nodes_by_group(game):
    result = game.query_nodes(group="enemies")
    assert len(result) == 2


def test_query_nodes_by_pattern(game):
    result = game.query_nodes(pattern="Enemy*")
    assert len(result) >= 2


def test_get_property_via_group(game):
    """Use group to find node, then get property."""
    players = game.find_by_group("player")
    assert len(players) >= 1
    pos = game.get_property(players[0], "position")
    if hasattr(pos, "x"):
        assert pos.x == 400.0
    else:
        assert pos["x"] == 400.0
