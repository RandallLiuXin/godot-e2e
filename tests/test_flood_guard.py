"""Unit tests for the engine-error-flood guard (no Godot).

Covers three layers:
  * ``EngineErrorFloodDetector`` sliding-window logic (deterministic fake clock)
  * ``GodotClient`` integration — arming, kill hook, fast-fail exception, and
    the ``collected_logs`` cap (§6 memory guard)
  * ``GodotLauncher._terminate_process`` — the process-only kill hook
"""

import json
import struct

import pytest

import inspect

from godot_e2e import (
    EngineErrorFloodDetector,
    EngineErrorFloodError,
    FloodStats,
    GodotE2E,
    LogEntry,
)
from godot_e2e.client import GodotClient


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _FakeClock:
    """Manually-advanced monotonic clock for deterministic window tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _FakeSocket:
    """Feeds canned length-prefixed JSON into GodotClient._read_response."""

    def __init__(self, responses):
        self._chunks = []
        for r in responses:
            payload = json.dumps(r).encode("utf-8")
            self._chunks.append(struct.pack(">I", len(payload)) + payload)
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, _bufsize):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def close(self):
        pass

    def settimeout(self, _t):
        pass


def _make_client(responses, collected_logs_limit=10_000):
    client = GodotClient(collected_logs_limit=collected_logs_limit)
    client._sock = _FakeSocket(responses)
    return client


def _errors(n, message="Null instance"):
    return [{"level": "error", "message": message} for _ in range(n)]


# ---------------------------------------------------------------------------
# EngineErrorFloodDetector — construction / validation
# ---------------------------------------------------------------------------

def test_detector_rejects_invalid_window():
    with pytest.raises(ValueError, match="window_seconds"):
        EngineErrorFloodDetector(window_seconds=0)


def test_detector_rejects_invalid_threshold():
    with pytest.raises(ValueError, match="error_threshold"):
        EngineErrorFloodDetector(error_threshold=0)


def test_detector_rejects_invalid_max_samples():
    with pytest.raises(ValueError, match="max_samples"):
        EngineErrorFloodDetector(max_samples=0)


# ---------------------------------------------------------------------------
# EngineErrorFloodDetector — window logic
# ---------------------------------------------------------------------------

def test_no_trip_on_no_errors():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    for _ in range(100):
        clock.advance(0.05)
        assert det.observe([LogEntry(level="info", message="tick")], 0) is None


def test_no_trip_on_sparse_errors():
    # A handful of errors spread out over time must never trip.
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    for _ in range(20):
        clock.advance(1.0)  # far apart — window only ever holds one event
        assert det.observe([LogEntry(level="error", message="boom")], 0) is None


def test_trips_when_errors_cross_threshold():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    # 49 errors — still under.
    assert det.observe([LogEntry(level="error", message="boom")] * 49, 0) is None
    clock.advance(0.05)
    # One more within the window tips it to 50.
    stats = det.observe([LogEntry(level="error", message="boom")], 0)
    assert isinstance(stats, FloodStats)
    assert stats.error_count == 50
    assert stats.dropped_count == 0


def test_boundary_just_under_does_not_trip():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    # Exactly threshold-1 within the window: no trip.
    assert det.observe([LogEntry(level="error", message="boom")] * 49, 0) is None


def test_window_evicts_old_events():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    assert det.observe(_errors_as_entries(40), 0) is None
    # Jump past the window — the earlier 40 errors must age out.
    clock.advance(5.0)
    assert det.observe(_errors_as_entries(40), 0) is None  # 40 < 50, not 80


def test_sustained_dropped_counts_toward_threshold():
    # Ring-buffer drops are strong flood evidence and count toward the trigger.
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    assert det.observe([], 25) is None
    clock.advance(0.05)
    stats = det.observe([], 25)
    assert stats is not None
    assert stats.dropped_count == 50
    assert stats.error_count == 0


def test_errors_and_dropped_combine():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    stats = det.observe(_errors_as_entries(30), 20)
    assert stats is not None
    assert stats.error_count == 30
    assert stats.dropped_count == 20


def test_samples_capped_and_populated():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=5, max_samples=3, time_source=clock
    )
    entries = [
        LogEntry(level="error", message=f"err{i}", file="res://x.gd", line=i)
        for i in range(5)
    ]
    stats = det.observe(entries, 0)
    assert stats is not None
    assert len(stats.samples) == 3  # capped at max_samples
    # Most recent errors are retained.
    assert stats.samples[-1].message == "err4"


def test_reset_clears_window():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=50, time_source=clock
    )
    assert det.observe(_errors_as_entries(40), 0) is None
    det.reset()
    clock.advance(0.05)
    # After reset the earlier 40 are gone, so 40 more must not trip.
    assert det.observe(_errors_as_entries(40), 0) is None


def _errors_as_entries(n):
    return [LogEntry(level="error", message="boom") for _ in range(n)]


# ---------------------------------------------------------------------------
# GodotClient integration — arming, kill hook, fast-fail
# ---------------------------------------------------------------------------

def _arm(client, *, threshold=50, window=2.0, clock=None, on_flood=None):
    det = EngineErrorFloodDetector(
        window_seconds=window,
        error_threshold=threshold,
        time_source=clock or _FakeClock(),
    )
    client.enable_flood_detection(det, on_flood=on_flood)
    return det


def test_client_not_armed_by_default_ignores_flood():
    # A bare client must behave exactly as before — no flood machinery.
    client = _make_client([{"id": 1, "ok": True, "_logs": _errors(500)}])
    resp = client.send_command("noop")  # must NOT raise
    assert resp == {"id": 1, "ok": True}


def test_client_flood_trips_kills_and_raises():
    killed = []
    client = _make_client([{"id": 1, "ok": True, "_logs": _errors(60)}])
    _arm(client, threshold=50, on_flood=lambda: killed.append(True))

    with pytest.raises(EngineErrorFloodError) as exc_info:
        client.send_command("noop")

    err = exc_info.value
    assert killed == [True]  # process kill hook fired
    assert err.error_count == 60
    assert err.dropped_count == 0
    assert err.window_seconds == 2.0
    assert err.samples  # carries representative error lines
    assert "Null instance" in str(err)  # sample error surfaced in the message
    assert "terminated early" in str(err)


def test_client_flood_trips_on_sustained_dropped():
    killed = []
    clock = _FakeClock()
    client = _make_client([
        {"id": 1, "ok": True, "_logs_dropped": 30},
        {"id": 2, "ok": True, "_logs_dropped": 30},
    ])
    _arm(client, threshold=50, clock=clock, on_flood=lambda: killed.append(True))

    client.send_command("first")  # 30 dropped — under threshold
    clock.advance(0.05)
    with pytest.raises(EngineErrorFloodError) as exc_info:
        client.send_command("second")  # 60 dropped total — trips
    assert killed == [True]
    assert exc_info.value.dropped_count == 60


def test_client_flood_survives_kill_hook_raising():
    # A kill hook that itself throws must not mask the flood exception.
    def boom():
        raise RuntimeError("kill failed")

    client = _make_client([{"id": 1, "ok": True, "_logs": _errors(60)}])
    _arm(client, threshold=50, on_flood=boom)

    with pytest.raises(EngineErrorFloodError):
        client.send_command("noop")


def test_client_flood_disabled_is_original_behavior():
    # threshold high enough that a 60-error response never trips → normal
    # response returned, logs still captured.
    client = _make_client([{"id": 1, "ok": True, "_logs": _errors(60)}])
    _arm(client, threshold=1000)
    resp = client.send_command("noop")
    assert resp == {"id": 1, "ok": True}
    assert len(client.last_logs) == 60


def test_reset_collected_logs_resets_detector():
    clock = _FakeClock()
    client = _make_client([
        {"id": 1, "ok": True, "_logs": _errors(40)},
        {"id": 2, "ok": True, "_logs": _errors(40)},
    ])
    _arm(client, threshold=50, clock=clock)

    client.send_command("first")  # 40 errors, under threshold
    client.reset_collected_logs()  # window cleared
    clock.advance(0.05)
    # Without the reset the two 40s would sum to 80 and trip; with it they don't.
    resp = client.send_command("second")
    assert resp == {"id": 2, "ok": True}


# ---------------------------------------------------------------------------
# GodotClient — collected_logs cap (§6 memory guard)
# ---------------------------------------------------------------------------

def test_collected_logs_capped_to_limit():
    # limit=5, feed 8 entries across two responses → keep the newest 5.
    client = _make_client(
        [
            {"id": 1, "ok": True, "_logs": [
                {"level": "info", "message": f"a{i}"} for i in range(5)
            ]},
            {"id": 2, "ok": True, "_logs": [
                {"level": "info", "message": f"b{i}"} for i in range(3)
            ]},
        ],
        collected_logs_limit=5,
    )
    client.send_command("first")
    client.send_command("second")
    assert len(client.collected_logs) == 5
    # Oldest three (a0..a2) dropped; newest five retained.
    assert [e.message for e in client.collected_logs] == \
        ["a3", "a4", "b0", "b1", "b2"]
    assert client.collected_logs_dropped == 3


def test_collected_logs_cap_stays_bounded_under_flood():
    # Many oversized responses must keep collected_logs bounded and idempotent.
    responses = [
        {"id": i, "ok": True, "_logs": _errors(50)} for i in range(1, 11)
    ]
    client = _make_client(responses, collected_logs_limit=100)
    for i in range(10):
        client.send_command(f"cmd{i}")
        assert len(client.collected_logs) <= 100  # never exceeds the cap
    assert len(client.collected_logs) == 100
    assert client.collected_logs_dropped == 400  # 500 seen - 100 kept


def test_collected_logs_cap_disabled_when_none():
    responses = [
        {"id": i, "ok": True, "_logs": _errors(50)} for i in range(1, 5)
    ]
    client = _make_client(responses, collected_logs_limit=None)
    for i in range(4):
        client.send_command(f"cmd{i}")
    assert len(client.collected_logs) == 200  # unbounded
    assert client.collected_logs_dropped == 0


def test_reset_collected_logs_resets_dropped_counter():
    client = _make_client(
        [{"id": 1, "ok": True, "_logs": _errors(10)}],
        collected_logs_limit=3,
    )
    client.send_command("noop")
    assert client.collected_logs_dropped == 7
    client.reset_collected_logs()
    assert client.collected_logs_dropped == 0
    assert client.collected_logs == []


# ---------------------------------------------------------------------------
# GodotLauncher._terminate_process — process-only kill hook
# ---------------------------------------------------------------------------

class _FakeProcess:
    def __init__(self, exited=False):
        self._exited = exited
        self.killed = False

    def poll(self):
        return 0 if self._exited else None

    def kill(self):
        self.killed = True
        self._exited = True

    # Present so the launcher's graceful ``kill()`` (invoked via ``__del__``
    # during GC) doesn't raise on this double.
    def terminate(self):
        self._exited = True

    def wait(self, timeout=None):
        return 0


def test_terminate_process_kills_running_process():
    from godot_e2e.launcher import GodotLauncher
    launcher = GodotLauncher()
    proc = _FakeProcess(exited=False)
    launcher.process = proc
    launcher._terminate_process()
    assert proc.killed is True


def test_terminate_process_noop_when_already_exited():
    from godot_e2e.launcher import GodotLauncher
    launcher = GodotLauncher()
    proc = _FakeProcess(exited=True)
    launcher.process = proc
    launcher._terminate_process()
    assert proc.killed is False


def test_terminate_process_noop_when_no_process():
    from godot_e2e.launcher import GodotLauncher
    launcher = GodotLauncher()
    launcher.process = None
    launcher._terminate_process()  # must not raise


# ---------------------------------------------------------------------------
# Runtime reconfiguration — EngineErrorFloodDetector.configure
# ---------------------------------------------------------------------------

def test_configure_partial_updates_only_given_fields():
    det = EngineErrorFloodDetector(window_seconds=2.0, error_threshold=100)
    det.configure(error_threshold=300)
    assert det.error_threshold == 300
    assert det.window_seconds == 2.0  # untouched
    assert det.enabled is True
    det.configure(window_seconds=5.0)
    assert det.window_seconds == 5.0
    assert det.error_threshold == 300  # still

def test_configure_toggle_enabled():
    det = EngineErrorFloodDetector(error_threshold=1)
    det.configure(enabled=False)
    assert det.enabled is False
    det.configure(enabled=True)
    assert det.enabled is True

def test_configure_rejects_invalid_values():
    det = EngineErrorFloodDetector()
    with pytest.raises(ValueError, match="window_seconds"):
        det.configure(window_seconds=0)
    with pytest.raises(ValueError, match="error_threshold"):
        det.configure(error_threshold=0)


def test_disabled_detector_never_trips_and_records_nothing():
    clock = _FakeClock()
    det = EngineErrorFloodDetector(
        window_seconds=2.0, error_threshold=5, enabled=False, time_source=clock
    )
    # Far past threshold, but disabled → no trip, no state accumulated.
    assert det.observe(_errors_as_entries(100), 100) is None
    # Re-enabling starts from a clean window (the disabled observe recorded
    # nothing), so a sub-threshold batch does not trip.
    det.configure(enabled=True)
    clock.advance(0.05)
    assert det.observe(_errors_as_entries(4), 0) is None
    clock.advance(0.05)
    assert det.observe(_errors_as_entries(1), 0) is not None  # now 5 → trips


# ---------------------------------------------------------------------------
# Runtime reconfiguration — GodotE2E.set_flood_detection
# ---------------------------------------------------------------------------

def test_set_flood_detection_retunes_threshold_live():
    clock = _FakeClock()
    client = _make_client([
        {"id": 1, "ok": True, "_logs": _errors(60)},
        {"id": 2, "ok": True, "_logs": _errors(60)},
    ])
    _arm(client, threshold=50, clock=clock)
    game = GodotE2E(client)

    # Raise the bar above 60 before the first (60-error) response → no trip.
    game.set_flood_detection(error_threshold=1000)
    resp = client.send_command("first")
    assert resp == {"id": 1, "ok": True}

    # Lower it back below 60 → the next 60-error response trips.
    game.set_flood_detection(error_threshold=50)
    clock.advance(0.05)
    with pytest.raises(EngineErrorFloodError):
        client.send_command("second")


def test_set_flood_detection_disable_opts_out():
    client = _make_client([{"id": 1, "ok": True, "_logs": _errors(500)}])
    _arm(client, threshold=50)
    game = GodotE2E(client)
    game.set_flood_detection(enabled=False)
    resp = client.send_command("noop")  # must NOT raise despite 500 errors
    assert resp == {"id": 1, "ok": True}


def test_set_flood_detection_lazily_arms_when_unarmed():
    # A connect()-style client with no detector: configuring one arms it.
    client = _make_client([{"id": 1, "ok": True, "_logs": _errors(10)}])
    game = GodotE2E(client)
    assert client._flood_detector is None
    game.set_flood_detection(error_threshold=5)
    assert client._flood_detector is not None
    with pytest.raises(EngineErrorFloodError):
        client.send_command("noop")  # 10 errors ≥ 5


def test_set_flood_detection_rejects_invalid_values():
    client = _make_client([])
    game = GodotE2E(client)
    with pytest.raises(ValueError, match="error_threshold"):
        game.set_flood_detection(error_threshold=0)


# ---------------------------------------------------------------------------
# Default threshold is 100 across the public surface
# ---------------------------------------------------------------------------

def test_default_threshold_is_100():
    assert EngineErrorFloodDetector().error_threshold == 100
    assert inspect.signature(
        GodotE2E.launch).parameters["flood_error_threshold"].default == 100
    from godot_e2e.launcher import GodotLauncher
    assert inspect.signature(
        GodotLauncher.launch).parameters["flood_error_threshold"].default == 100


# ---------------------------------------------------------------------------
# Message wording — dropped-driven flood with no captured error
# ---------------------------------------------------------------------------

def test_dropped_only_flood_message_does_not_claim_error():
    client = _make_client([{"id": 1, "ok": True, "_logs_dropped": 60}])
    _arm(client, threshold=50)
    with pytest.raises(EngineErrorFloodError) as exc_info:
        client.send_command("noop")
    msg = str(exc_info.value)
    assert exc_info.value.error_count == 0
    assert "log flood" in msg          # softened headline
    assert "error flood" not in msg    # must not claim an error flood
    assert "warning/print" in msg      # points triage at the real cause


def test_error_driven_flood_message_still_says_error():
    client = _make_client([{"id": 1, "ok": True, "_logs": _errors(60)}])
    _arm(client, threshold=50)
    with pytest.raises(EngineErrorFloodError) as exc_info:
        client.send_command("noop")
    assert "error flood" in str(exc_info.value)
