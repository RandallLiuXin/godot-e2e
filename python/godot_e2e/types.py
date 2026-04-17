"""Python-side types that mirror GDScript types, plus exception classes."""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Type classes
# ---------------------------------------------------------------------------

@dataclass
class Vector2:
    x: float
    y: float


@dataclass
class Vector2i:
    x: int
    y: int


@dataclass
class Vector3:
    x: float
    y: float
    z: float


@dataclass
class Vector3i:
    x: int
    y: int
    z: int


@dataclass
class Rect2:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Rect2i:
    x: int
    y: int
    w: int
    h: int


@dataclass
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0


@dataclass
class Transform2D:
    x: Vector2
    y: Vector2
    origin: Vector2


@dataclass
class NodePath:
    path: str


# ---------------------------------------------------------------------------
# Deserialization  (JSON with _t tags -> Python types)
# ---------------------------------------------------------------------------

_DESERIALIZERS = {
    "v2": lambda d: Vector2(d["x"], d["y"]),
    "v2i": lambda d: Vector2i(d["x"], d["y"]),
    "v3": lambda d: Vector3(d["x"], d["y"], d["z"]),
    "v3i": lambda d: Vector3i(d["x"], d["y"], d["z"]),
    "r2": lambda d: Rect2(d["x"], d["y"], d["w"], d["h"]),
    "r2i": lambda d: Rect2i(d["x"], d["y"], d["w"], d["h"]),
    "col": lambda d: Color(d["r"], d["g"], d["b"], d.get("a", 1.0)),
    "t2d": lambda d: Transform2D(
        deserialize(d["x"]),
        deserialize(d["y"]),
        deserialize(d["o"]),
    ),
    "np": lambda d: NodePath(d["v"]),
}


def deserialize(value):
    """Convert JSON with ``_t`` type tags back to Python types."""
    if isinstance(value, dict):
        tag = value.get("_t")
        if tag == "_unknown":
            return value  # pass through unknown types
        fn = _DESERIALIZERS.get(tag)
        if fn is not None:
            return fn(value)
        # Regular dict – deserialize values recursively
        return {k: deserialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deserialize(v) for v in value]
    return value  # primitives pass through


# ---------------------------------------------------------------------------
# Serialization  (Python types -> JSON with _t tags)
# ---------------------------------------------------------------------------

def serialize(value):
    """Convert Python types to JSON-serialisable dicts with ``_t`` type tags."""
    if isinstance(value, Vector2):
        return {"_t": "v2", "x": value.x, "y": value.y}
    if isinstance(value, Vector2i):
        return {"_t": "v2i", "x": value.x, "y": value.y}
    if isinstance(value, Vector3):
        return {"_t": "v3", "x": value.x, "y": value.y, "z": value.z}
    if isinstance(value, Vector3i):
        return {"_t": "v3i", "x": value.x, "y": value.y, "z": value.z}
    if isinstance(value, Rect2):
        return {"_t": "r2", "x": value.x, "y": value.y, "w": value.w, "h": value.h}
    if isinstance(value, Rect2i):
        return {"_t": "r2i", "x": value.x, "y": value.y, "w": value.w, "h": value.h}
    if isinstance(value, Color):
        return {"_t": "col", "r": value.r, "g": value.g, "b": value.b, "a": value.a}
    if isinstance(value, Transform2D):
        return {
            "_t": "t2d",
            "x": serialize(value.x),
            "y": serialize(value.y),
            "o": serialize(value.origin),
        }
    if isinstance(value, NodePath):
        return {"_t": "np", "v": value.path}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    return value  # primitives


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class GodotE2EError(Exception):
    """Base exception for all godot-e2e errors."""


class NodeNotFoundError(GodotE2EError):
    """Raised when a node path doesn't resolve in the scene tree."""


class TimeoutError(GodotE2EError):
    """Raised when a wait_for_* operation exceeds its timeout.

    The optional *scene_tree* attribute contains a tree dump captured at the
    moment the timeout fired, which is useful for diagnostics.
    """

    def __init__(self, message: str, scene_tree=None):
        super().__init__(message)
        self.scene_tree = scene_tree


class ConnectionLostError(GodotE2EError):
    """Raised when the Godot process crashes or the TCP connection drops."""


class CommandError(GodotE2EError):
    """Raised when the server returns an error response."""
