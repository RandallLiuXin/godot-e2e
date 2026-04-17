"""Test F10: Screenshot Capture."""

import pytest
import os


def test_screenshot_auto_path(game):
    """Screenshot without explicit path returns an absolute path."""
    path = game.screenshot()
    assert path != ""
    assert os.path.isabs(path)


def test_screenshot_explicit_path(game, tmp_path):
    """Screenshot with explicit absolute path saves the file."""
    save_path = str(tmp_path / "test_screenshot.png")
    result_path = game.screenshot(save_path)
    assert os.path.isfile(save_path), f"Screenshot not saved to {save_path}"
