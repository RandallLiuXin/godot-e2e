"""Sliding-window detector for sustained engine-error floods.

A non-fatal GDScript runtime error in ``_process`` / ``_physics_process``
re-fires every frame. Headless Godot has no vsync, so a single such error
becomes hundreds-to-thousands of identical error lines per second. The E2E
client sees this as a burst of ``error``-level entries — and, once the addon's
ring buffer can no longer drain fast enough, a rising ``_logs_dropped`` count —
piggybacked on every command response during an ``expect`` / ``wait_for`` poll.

This detector watches that signal over a short wall-clock window and reports a
flood once the combined error + dropped volume in the window crosses a
threshold, so the launcher can kill Godot and fast-fail instead of idling to
the full timeout.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, List, Optional, Tuple

from .types import LogEntry


@dataclass
class FloodStats:
    """Evidence captured at the moment the detector trips."""

    error_count: int
    dropped_count: int
    window_seconds: float
    samples: List[LogEntry] = field(default_factory=list)


class EngineErrorFloodDetector:
    """Trip when error-level volume in a sliding window crosses a threshold.

    The window is measured in wall-clock seconds against ``time_source`` (the
    monotonic clock by default; injectable so tests can drive a fake clock).
    Only responses that actually carry a log delta advance the window: a test
    that sits in a pure ``sleep`` without sending commands produces no signal
    and cannot trip the detector. That is acceptable because virtually all E2E
    waits poll via ``expect`` / ``wait_for`` (which round-trip every ~50ms).
    """

    def __init__(
        self,
        *,
        window_seconds: float = 2.0,
        error_threshold: int = 50,
        max_samples: int = 3,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be > 0; got {window_seconds}")
        if error_threshold < 1:
            raise ValueError(f"error_threshold must be >= 1; got {error_threshold}")
        if max_samples < 1:
            raise ValueError(f"max_samples must be >= 1; got {max_samples}")
        self.window_seconds = window_seconds
        self.error_threshold = error_threshold
        self.max_samples = max_samples
        self._time = time_source
        # One (timestamp, error_count, dropped_count) triple per observed
        # response, oldest first. Trimmed to the window on every observe().
        self._events: Deque[Tuple[float, int, int]] = deque()
        self._samples: Deque[LogEntry] = deque(maxlen=max_samples)

    def reset(self) -> None:
        """Forget all accumulated window state (called at the test boundary)."""
        self._events.clear()
        self._samples.clear()

    def observe(self, entries: List[LogEntry], dropped: int) -> Optional[FloodStats]:
        """Feed one response's log delta; return :class:`FloodStats` if the
        window now qualifies as a flood, else ``None``.

        ``dropped`` is the addon ring-buffer overflow count reported for this
        response. Both error entries and dropped entries count toward the
        threshold: a drop is a log line the buffer could not hold, which under
        E2E only happens when production far outpaces the ~200-entry drain —
        i.e. exactly the flood we want to catch.
        """
        error_entries = [e for e in entries if e.level == "error"]
        for e in error_entries:
            self._samples.append(e)

        now = self._time()
        self._events.append((now, len(error_entries), int(dropped)))

        cutoff = now - self.window_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

        total_errors = sum(ev[1] for ev in self._events)
        total_dropped = sum(ev[2] for ev in self._events)
        if total_errors + total_dropped >= self.error_threshold:
            return FloodStats(
                error_count=total_errors,
                dropped_count=total_dropped,
                window_seconds=self.window_seconds,
                samples=list(self._samples),
            )
        return None
