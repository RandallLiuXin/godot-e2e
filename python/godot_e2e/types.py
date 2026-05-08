"""Python-side types that mirror GDScript types, plus exception classes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


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
# Engine log capture
# ---------------------------------------------------------------------------

class LogVerbosity(str, Enum):
    """Verbosity levels for engine log capture, matching the server-side names."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class LogEntry:
    """A single log line captured from the running Godot process.

    ``level`` is one of: ``error`` (push_error / runtime / shader / generic
    error), ``warning`` (push_warning), ``info`` (print() at info verbosity),
    ``stderr`` (printerr() at info verbosity).

    ``function`` / ``file`` / ``line`` are populated only for engine errors
    (``_log_error`` callback); they're empty for ``info`` / ``stderr`` entries.
    """
    level: str
    message: str
    function: str = ""
    file: str = ""
    line: int = 0

    def __str__(self) -> str:
        prefix = f"[{self.level.upper()}]"
        if self.file and self.line > 0:
            loc = f" ({self.file}:{self.line})"
        elif self.function:
            loc = f" (in {self.function})"
        else:
            loc = ""
        return f"{prefix} {self.message}{loc}"


def parse_log_entries(raw: list) -> List[LogEntry]:
    """Convert the raw ``_logs`` array from a wire response into LogEntry objects."""
    out: List[LogEntry] = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        out.append(LogEntry(
            level=e.get("level", "info"),
            message=e.get("message", ""),
            function=e.get("function", ""),
            file=e.get("file", ""),
            line=int(e.get("line", 0) or 0),
        ))
    return out


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class GodotE2EError(Exception):
    """Base exception for all godot-e2e errors.

    The ``logs`` attribute holds engine log entries captured during the
    failing command (when log capture is active). Set by GodotClient after
    construction; defaults to an empty list so subclasses don't need to
    thread the parameter through their own ``__init__``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logs: List[LogEntry] = []


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


class MultipleMatchesError(GodotE2EError):
    """Raised when a Locator action requires a single match but the query
    matched multiple nodes. Carries the full list of matched paths so the
    caller can pick one explicitly via .first() / .nth(i) / .filter(...).
    """

    def __init__(self, message: str, paths: list):
        super().__init__(message)
        self.paths = paths


class NotActionableError(GodotE2EError):
    """Raised when a Locator action's actionability check fails (visibility,
    mouse_filter, viewport bounds). Carries the per-check status and the
    list of failing reasons.
    """

    def __init__(self, message: str, path: str, reasons: list, checks: dict):
        super().__init__(message)
        self.path = path
        self.reasons = reasons
        self.checks = checks


class ExpectationFailedError(GodotE2EError, AssertionError):
    """Raised when an ``expect(locator).to_*`` matcher fails to hold within
    its timeout.

    Dual-inherits ``AssertionError`` so pytest renders it the same way it
    renders a plain ``assert`` failure (the message lands in the assertion
    section of the test report, not as a generic exception traceback).
    Catching ``GodotE2EError`` still works for tooling that wants to
    treat it as a framework error.

    Attributes:
        actual: Last value observed by the polling loop. Meaningful only
            when ``observation_captured`` is ``True`` — otherwise defaults
            to ``None``. For ``to_satisfy``, this is the predicate's
            return value.
        observation_captured: ``True`` if at least one poll returned a
            value (even a falsy or ``None`` one). ``False`` if every
            poll raised a swallowed lookup error — caused by a node
            that never resolved, a stable multi-match without
            ``.first()`` / ``.filter()``, or repeated server errors.
            Use this to distinguish "the predicate observed ``None``"
            from "no observation was ever made".
        matcher: Human-readable matcher description, e.g.
            ``"to_have_text('Start')"``.
        scene_tree: Tree dump captured at the moment of failure, depth 4
            from ``/root``. ``None`` if the dump call itself errored.
        timeout: The timeout that was exceeded, in seconds.
        last_error: Most recent ``CommandError`` swallowed during
            polling, if any. Populated when the server kept rejecting
            the read (e.g. property doesn't exist on the resolved node,
            or transient command failures persisted past the timeout).
            ``None`` when polling never raised ``CommandError``.
    """

    def __init__(
        self,
        message: str,
        *,
        actual=None,
        observation_captured: bool = False,
        matcher: str = "",
        scene_tree=None,
        timeout: float = 0.0,
        last_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.actual = actual
        self.observation_captured = observation_captured
        self.matcher = matcher
        self.scene_tree = scene_tree
        self.timeout = timeout
        self.last_error = last_error
