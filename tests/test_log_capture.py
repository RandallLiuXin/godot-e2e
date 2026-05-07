"""Unit tests for engine log capture (no Godot)."""

import json
import struct

import pytest

from godot_e2e import (
    CommandError,
    GodotE2EError,
    LogEntry,
    LogVerbosity,
    NodeNotFoundError,
    NotActionableError,
    parse_log_entries,
)
from godot_e2e.client import GodotClient


# ---------------------------------------------------------------------------
# parse_log_entries / LogEntry helpers
# ---------------------------------------------------------------------------

def test_parse_log_entries_skips_non_dict():
    raw = [
        {"level": "error", "message": "boom"},
        "not-a-dict",
        None,
        {"level": "warning", "message": "careful"},
    ]
    entries = parse_log_entries(raw)
    assert [e.level for e in entries] == ["error", "warning"]


def test_parse_log_entries_defaults_missing_fields():
    entries = parse_log_entries([{"message": "lonely"}])
    assert len(entries) == 1
    assert entries[0].level == "info"
    assert entries[0].message == "lonely"
    assert entries[0].file == ""
    assert entries[0].function == ""
    assert entries[0].line == 0


def test_parse_log_entries_handles_full_payload():
    entries = parse_log_entries([{
        "level": "error",
        "message": "Null instance",
        "function": "_on_pressed",
        "file": "res://scripts/menu.gd",
        "line": 42,
    }])
    e = entries[0]
    assert e.level == "error"
    assert e.message == "Null instance"
    assert e.function == "_on_pressed"
    assert e.file == "res://scripts/menu.gd"
    assert e.line == 42


def test_log_entry_str_with_file_and_line():
    e = LogEntry(level="error", message="boom", file="res://x.gd", line=7)
    assert str(e) == "[ERROR] boom (res://x.gd:7)"


def test_log_entry_str_with_function_only():
    e = LogEntry(level="warning", message="careful", function="_ready")
    assert str(e) == "[WARNING] careful (in _ready)"


def test_log_entry_str_no_location():
    e = LogEntry(level="info", message="hello")
    assert str(e) == "[INFO] hello"


def test_log_verbosity_enum_values():
    # The wire protocol expects exact strings — pin them down.
    assert LogVerbosity.ERROR.value == "error"
    assert LogVerbosity.WARNING.value == "warning"
    assert LogVerbosity.INFO.value == "info"


# ---------------------------------------------------------------------------
# GodotClient: socket-level _logs extraction
# ---------------------------------------------------------------------------

class _FakeSocket:
    """Feeds canned length-prefixed JSON into GodotClient._read_response.

    sendall is recorded but ignored. Each item in ``responses`` is a dict
    that will be JSON-encoded with a 4-byte big-endian length prefix.
    """

    def __init__(self, responses):
        self._chunks: list[bytes] = []
        for r in responses:
            payload = json.dumps(r).encode("utf-8")
            self._chunks.append(struct.pack(">I", len(payload)) + payload)
        self.sent: list[bytes] = []

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


def _make_client(responses):
    client = GodotClient()
    client._sock = _FakeSocket(responses)
    return client


def test_response_logs_extracted_into_last_logs():
    client = _make_client([{
        "id": 1,
        "ok": True,
        "_logs": [
            {"level": "error", "message": "boom"},
            {"level": "warning", "message": "careful"},
        ],
    }])
    resp = client.send_command("noop")
    assert "_logs" not in resp  # stripped before returning to caller
    assert len(client.last_logs) == 2
    assert client.last_logs[0].level == "error"
    assert client.last_logs[1].level == "warning"


def test_response_without_logs_clears_last_logs():
    client = _make_client([
        {"id": 1, "ok": True, "_logs": [{"level": "error", "message": "boom"}]},
        {"id": 2, "ok": True},
    ])
    client.send_command("first")
    assert len(client.last_logs) == 1
    client.send_command("second")
    assert client.last_logs == []  # second response had no _logs


def test_collected_logs_accumulates_across_commands():
    client = _make_client([
        {"id": 1, "ok": True, "_logs": [{"level": "warning", "message": "w1"}]},
        {"id": 2, "ok": True, "_logs": [{"level": "error", "message": "e1"}]},
    ])
    client.send_command("a")
    client.send_command("b")
    assert [e.message for e in client.collected_logs] == ["w1", "e1"]


def test_reset_collected_logs():
    client = _make_client([
        {"id": 1, "ok": True, "_logs": [{"level": "warning", "message": "w1"}]},
    ])
    client.send_command("a")
    assert len(client.collected_logs) == 1
    client.reset_collected_logs()
    assert client.collected_logs == []
    assert client.last_logs == []


def test_dropped_count_appended_as_marker_uniformly():
    # The dropped marker must reach all three exits: last_logs (per-call
    # window), collected_logs (test-level accumulator), and exc.logs (on
    # the error path) — splitting it across only one would let consumers
    # silently miss buffer overflows depending on which API they read.
    client = _make_client([{
        "id": 1,
        "ok": True,
        "_logs": [{"level": "warning", "message": "kept"}],
        "_logs_dropped": 17,
    }])
    client.send_command("noop")

    def _has_dropped_marker(seq):
        return any("dropped" in e.message and "17" in e.message for e in seq)

    assert "kept" in [e.message for e in client.last_logs]
    assert _has_dropped_marker(client.last_logs)
    assert _has_dropped_marker(client.collected_logs)


def test_dropped_count_propagates_to_exception_logs():
    client = _make_client([{
        "id": 1,
        "error": "command_failed",
        "message": "kaboom",
        "_logs": [{"level": "error", "message": "real_err"}],
        "_logs_dropped": 9,
    }])
    with pytest.raises(CommandError) as exc_info:
        client.send_command("noop")
    err = exc_info.value
    assert any("real_err" in e.message for e in err.logs)
    assert any("dropped" in e.message and "9" in e.message for e in err.logs)


def test_error_response_attaches_logs_to_exception():
    client = _make_client([{
        "id": 1,
        "error": "command_failed",
        "message": "kaboom",
        "_logs": [
            {"level": "error", "message": "Null instance",
             "file": "res://x.gd", "line": 7},
        ],
    }])
    with pytest.raises(CommandError) as exc_info:
        client.send_command("noop")
    err = exc_info.value
    assert isinstance(err, GodotE2EError)
    assert len(err.logs) == 1
    assert err.logs[0].level == "error"
    assert err.logs[0].file == "res://x.gd"


def test_node_not_found_error_attaches_logs():
    client = _make_client([{
        "id": 1,
        "error": "not_found",
        "message": "Node not found: /root/Foo",
        "_logs": [{"level": "warning", "message": "scene reloaded"}],
    }])
    with pytest.raises(NodeNotFoundError) as exc_info:
        client.send_command("get_property", path="/root/Foo")
    assert len(exc_info.value.logs) == 1
    assert exc_info.value.logs[0].message == "scene reloaded"


def test_exception_logs_default_to_empty_list():
    # Constructing exceptions directly (not via wire) should give an empty
    # logs list — needed so caller code doesn't have to special-case None.
    err = CommandError("manual")
    assert err.logs == []
    err2 = NotActionableError("nope", "/root/X", ["hidden"], {"visible": False})
    assert err2.logs == []


# ---------------------------------------------------------------------------
# LogCaptureReporter pytest plugin
# ---------------------------------------------------------------------------

class _StubReport:
    """Pretends to be a pytest TestReport for hookimpl unit testing."""

    def __init__(self, when="call", failed=True):
        self.when = when
        self.failed = failed
        self.sections = []


class _StubItem:
    """Pretends to be a pytest test item carrying funcargs."""

    def __init__(self, funcargs=None):
        self.funcargs = funcargs or {}


def _make_game_with_logs(*log_messages):
    """Construct a real GodotE2E (no Godot) with a stuffed collected_logs."""
    client = GodotClient()
    client.collected_logs = [
        LogEntry(level="error", message=m) for m in log_messages
    ]
    from godot_e2e import GodotE2E
    return GodotE2E(client)


def test_log_reporter_attaches_section_on_call_failure():
    from godot_e2e.fixtures import _maybe_attach_logs_to_report
    game = _make_game_with_logs("BOOM")
    item = _StubItem(funcargs={"game": game})
    report = _StubReport(when="call", failed=True)

    _maybe_attach_logs_to_report(item, report)

    assert len(report.sections) == 1
    header, body = report.sections[0]
    assert header == "captured godot logs"
    assert "BOOM" in body


def test_log_reporter_attaches_section_on_setup_failure():
    # Setup-phase failures (e.g. fixture launch errors) need the section
    # too — that's the high-value capture window.
    from godot_e2e.fixtures import _maybe_attach_logs_to_report
    game = _make_game_with_logs("LAUNCH_FAIL")
    item = _StubItem(funcargs={"_game_instance": game})
    report = _StubReport(when="setup", failed=True)

    _maybe_attach_logs_to_report(item, report)

    assert len(report.sections) == 1
    assert "LAUNCH_FAIL" in report.sections[0][1]


def test_log_reporter_skips_passing_tests():
    from godot_e2e.fixtures import _maybe_attach_logs_to_report
    game = _make_game_with_logs("BOOM")
    item = _StubItem(funcargs={"game": game})
    report = _StubReport(when="call", failed=False)

    _maybe_attach_logs_to_report(item, report)

    assert report.sections == []


def test_log_reporter_skips_teardown_phase():
    # Teardown failures don't get the section — the test-level capture
    # window is already closed and emitting then would just confuse.
    from godot_e2e.fixtures import _maybe_attach_logs_to_report
    game = _make_game_with_logs("BOOM")
    item = _StubItem(funcargs={"game": game})
    report = _StubReport(when="teardown", failed=True)

    _maybe_attach_logs_to_report(item, report)

    assert report.sections == []


def test_log_reporter_skips_when_no_godot_fixture():
    from godot_e2e.fixtures import _maybe_attach_logs_to_report
    item = _StubItem(funcargs={"some_other": object()})
    report = _StubReport(when="call", failed=True)

    _maybe_attach_logs_to_report(item, report)

    assert report.sections == []


def test_log_reporter_skips_when_logs_empty():
    from godot_e2e.fixtures import _maybe_attach_logs_to_report
    client = GodotClient()
    # collected_logs left empty
    from godot_e2e import GodotE2E
    game = GodotE2E(client)
    item = _StubItem(funcargs={"game": game})
    report = _StubReport(when="call", failed=True)

    _maybe_attach_logs_to_report(item, report)

    assert report.sections == []


def test_launcher_rejects_invalid_log_verbosity():
    # Validation happens at the Python boundary so a typo fails fast
    # instead of being silently swallowed by config.gd's fallback.
    from godot_e2e.launcher import GodotLauncher
    launcher = GodotLauncher()
    with pytest.raises(ValueError, match="log_verbosity"):
        launcher.launch("./does_not_matter", log_verbosity="loud")


def test_godot_e2e_launch_rejects_invalid_log_verbosity():
    from godot_e2e import GodotE2E
    with pytest.raises(ValueError, match="log_verbosity"):
        GodotE2E.launch("./does_not_matter", log_verbosity="LOUD")


def test_launcher_accepts_none_log_verbosity():
    # None is the documented "use addon default" sentinel — must NOT
    # trigger validation. We can't actually launch Godot here, so we
    # only verify that the validate-and-raise path is skipped.
    from godot_e2e.launcher import GodotLauncher
    launcher = GodotLauncher()
    # Should fail later (Godot binary lookup) but NOT on log_verbosity
    # validation.
    try:
        launcher.launch("./does_not_matter", log_verbosity=None,
                        godot_path="/nonexistent/godot")
    except ValueError as exc:
        assert "log_verbosity" not in str(exc), (
            f"None should not trip log_verbosity validation: {exc}"
        )
    except (FileNotFoundError, ConnectionError, RuntimeError):
        pass  # expected — couldn't reach a real Godot


def test_log_reporter_finds_game_under_alternate_name():
    # Users with a custom-named GodotE2E fixture get picked up via the
    # values-scan fallback in _find_game_in_funcargs.
    from godot_e2e.fixtures import _maybe_attach_logs_to_report
    game = _make_game_with_logs("CUSTOM")
    item = _StubItem(funcargs={"my_custom_game_fixture": game})
    report = _StubReport(when="call", failed=True)

    _maybe_attach_logs_to_report(item, report)

    assert len(report.sections) == 1
    assert "CUSTOM" in report.sections[0][1]
