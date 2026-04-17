"""Test F1: TCP Server Lifecycle + F9: Error Handling."""

import pytest


def test_connect_and_handshake(game):
    """Verify that connection works and game is responsive."""
    exists = game.node_exists("/root/Main")
    assert exists is True


def test_node_not_found_error(game):
    """F9: NodeNotFoundError on invalid path."""
    with pytest.raises(Exception) as exc_info:
        game.get_property("/root/Nonexistent", "position")
    assert "not found" in str(exc_info.value).lower()


def test_property_not_found_error(game):
    """F9: Error on invalid property."""
    with pytest.raises(Exception):
        game.get_property("/root/Main", "nonexistent_property_xyz")


def test_method_not_found_error(game):
    """F9: Error on invalid method."""
    with pytest.raises(Exception):
        game.call("/root/Main", "nonexistent_method_xyz")


def test_unknown_command_error(game):
    """F9: Error on unknown command."""
    with pytest.raises(Exception):
        game._client.send_command("totally_invalid_command")


def test_crash_recovery(game_fresh):
    """Scenario 4: Crash Recovery — kill Godot, verify ConnectionLostError."""
    import os
    import signal

    # Verify it's working first
    assert game_fresh.node_exists("/root/Main") is True

    # Kill the Godot process
    pid = game_fresh._launcher.process.pid
    game_fresh._launcher.process.kill()
    game_fresh._launcher.process.wait()

    # Next command should raise ConnectionLostError
    from godot_e2e import ConnectionLostError
    with pytest.raises(ConnectionLostError):
        game_fresh.get_property("/root/Main", "counter")
