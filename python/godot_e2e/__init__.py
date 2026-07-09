"""godot-e2e: Out-of-process E2E testing tool for Godot."""

from .commands import GodotE2E
from .locator import Locator
from .expect import expect, LocatorAssertions
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
    LogEntry,
    LogVerbosity,
    parse_log_entries,
    GodotE2EError,
    NodeNotFoundError,
    TimeoutError,
    ConnectionLostError,
    CommandError,
    EngineErrorFloodError,
    MultipleMatchesError,
    NotActionableError,
    ExpectationFailedError,
)
from .client import GodotClient
from .launcher import GodotLauncher
from .flood import EngineErrorFloodDetector, FloodStats

__version__ = "1.3.0"

__all__ = [
    "GodotE2E",
    "Locator",
    "expect",
    "LocatorAssertions",
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
    "LogEntry",
    "LogVerbosity",
    "parse_log_entries",
    "GodotE2EError",
    "NodeNotFoundError",
    "TimeoutError",
    "ConnectionLostError",
    "CommandError",
    "EngineErrorFloodError",
    "MultipleMatchesError",
    "NotActionableError",
    "ExpectationFailedError",
    "GodotClient",
    "GodotLauncher",
    "EngineErrorFloodDetector",
    "FloodStats",
]
