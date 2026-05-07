"""godot-e2e: Out-of-process E2E testing tool for Godot."""

from .commands import GodotE2E
from .locator import Locator
from .types import (
    Vector2,
    Vector2i,
    Vector3,
    Vector3i,
    Rect2,
    Rect2i,
    Color,
    Transform2D,
    NodePath,
    deserialize,
    serialize,
    GodotE2EError,
    NodeNotFoundError,
    TimeoutError,
    ConnectionLostError,
    CommandError,
    MultipleMatchesError,
    NotActionableError,
)
from .client import GodotClient
from .launcher import GodotLauncher

__version__ = "1.1.0"

__all__ = [
    "GodotE2E",
    "Locator",
    "Vector2",
    "Vector2i",
    "Vector3",
    "Vector3i",
    "Rect2",
    "Rect2i",
    "Color",
    "Transform2D",
    "NodePath",
    "deserialize",
    "serialize",
    "GodotE2EError",
    "NodeNotFoundError",
    "TimeoutError",
    "ConnectionLostError",
    "CommandError",
    "MultipleMatchesError",
    "NotActionableError",
    "GodotClient",
    "GodotLauncher",
]
