"""Test F4: Frame Synchronization."""

import pytest
import time


def test_wait_process_frames(game):
    """wait_process_frames completes without error."""
    game.wait_process_frames(5)


def test_wait_physics_frames(game):
    """wait_physics_frames completes without error."""
    game.wait_physics_frames(5)


def test_wait_seconds(game):
    """wait_seconds waits for game time."""
    start = time.monotonic()
    game.wait_seconds(0.1)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05  # generous lower bound


def test_wait_for_node_exists(game):
    """wait_for_node succeeds for existing node."""
    game.wait_for_node("/root/Main", timeout=2.0)


def test_wait_for_node_timeout(game):
    """wait_for_node raises TimeoutError for non-existent node."""
    from godot_e2e import TimeoutError

    with pytest.raises((TimeoutError, Exception)) as exc_info:
        game.wait_for_node("/root/NeverExists", timeout=1.0)
    err_msg = str(exc_info.value).lower()
    assert "timeout" in err_msg or "timed out" in err_msg


def test_wait_for_property(game):
    """wait_for_property succeeds when property already matches."""
    game.wait_for_property("/root/Main", "counter", 0, timeout=2.0)
