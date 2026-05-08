"""Real-Godot integration tests for engine log capture (ROADMAP task 2).

These exercise the full path: GDScript ``push_error`` / ``push_warning`` /
runtime errors fire on the game side, our Logger subclass captures them,
the wire response carries them as ``_logs``, and the Python client surfaces
them via ``game.collected_logs`` (and on raised exceptions).
"""

import pytest

from godot_e2e import CommandError


# ---------------------------------------------------------------------------
# Default verbosity (warning) — push_error and push_warning captured
# ---------------------------------------------------------------------------

def test_push_error_captured(game):
    game.call("/root/Menu", "e2e_emit_error", ["BANG"])
    messages = [str(e) for e in game.collected_logs]
    assert any("BANG" in m for m in messages), (
        f"expected 'BANG' in captured logs, got {messages!r}"
    )
    error_entries = [e for e in game.collected_logs if e.level == "error"]
    assert any("BANG" in e.message for e in error_entries)


def test_push_warning_captured_at_default_verbosity(game):
    game.call("/root/Menu", "e2e_emit_warning", ["WARN_X"])
    warning_entries = [e for e in game.collected_logs if e.level == "warning"]
    assert any("WARN_X" in e.message for e in warning_entries), (
        f"expected 'WARN_X' warning, got {[str(e) for e in game.collected_logs]!r}"
    )


def test_print_not_captured_at_default_verbosity(game):
    # Default verbosity is "warning" — print() goes through _log_message
    # which only fires at "info". This test pins that contract down.
    game.call("/root/Menu", "e2e_emit_print", ["NOISY_PRINT"])
    messages = [e.message for e in game.collected_logs]
    assert not any("NOISY_PRINT" in m for m in messages), (
        f"print() leaked into collected_logs at warning verbosity: {messages!r}"
    )


def test_runtime_script_error_captured(game):
    # Calling a method on null is a script runtime error
    # (ErrorType.SCRIPT). callv returns null; the error stays in the
    # response's _logs slice.
    game.call("/root/Menu", "e2e_trigger_runtime_error")
    error_entries = [e for e in game.collected_logs if e.level == "error"]
    assert len(error_entries) >= 1, (
        f"expected at least one error from runtime null deref, got {[str(e) for e in game.collected_logs]!r}"
    )


# ---------------------------------------------------------------------------
# Runtime verbosity adjustment
# ---------------------------------------------------------------------------

def test_set_log_verbosity_to_info_captures_print(game):
    game.set_log_verbosity("info")
    try:
        game.call("/root/Menu", "e2e_emit_print", ["VISIBLE_PRINT"])
        messages = [e.message for e in game.collected_logs]
        assert any("VISIBLE_PRINT" in m for m in messages), (
            f"expected 'VISIBLE_PRINT' at info verbosity, got {messages!r}"
        )
    finally:
        # Restore so subsequent tests in this module aren't polluted.
        game.set_log_verbosity("warning")


def test_set_log_verbosity_back_to_warning_drops_print(game):
    game.set_log_verbosity("info")
    game.set_log_verbosity("warning")
    game.reset_collected_logs()
    game.call("/root/Menu", "e2e_emit_print", ["DROPPED_PRINT"])
    messages = [e.message for e in game.collected_logs]
    assert not any("DROPPED_PRINT" in m for m in messages)


def test_set_log_verbosity_to_error_drops_warning(game):
    game.set_log_verbosity("error")
    try:
        game.reset_collected_logs()
        game.call("/root/Menu", "e2e_emit_warning", ["NOPE_WARN"])
        warning_entries = [e for e in game.collected_logs if e.level == "warning"]
        assert not any("NOPE_WARN" in e.message for e in warning_entries)
    finally:
        game.set_log_verbosity("warning")


def test_set_log_verbosity_invalid_raises(game):
    with pytest.raises(CommandError) as exc_info:
        game.set_log_verbosity("loud")
    assert "level" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# last_logs / collected_logs distinction
# ---------------------------------------------------------------------------

def test_last_logs_reflects_only_most_recent_command(game):
    game.call("/root/Menu", "e2e_emit_warning", ["FIRST"])
    # node_exists triggers no logs of its own at warning verbosity, so
    # last_logs should be empty or at most contain unrelated noise.
    game.node_exists("/root/Menu")
    last = [e.message for e in game.last_logs]
    assert not any("FIRST" in m for m in last), (
        f"FIRST leaked into last_logs after a follow-up command: {last!r}"
    )
    # But collected_logs still has FIRST.
    collected = [e.message for e in game.collected_logs]
    assert any("FIRST" in m for m in collected)


def test_reset_collected_logs_clears_state(game):
    game.call("/root/Menu", "e2e_emit_warning", ["BEFORE_RESET"])
    assert len(game.collected_logs) >= 1
    game.reset_collected_logs()
    assert game.collected_logs == []
    assert game.last_logs == []


# ---------------------------------------------------------------------------
# Exceptions expose the per-command logs slice
# ---------------------------------------------------------------------------

def test_exceptions_expose_logs_attribute(game):
    # Every godot-e2e exception inherits a ``logs`` attribute populated
    # from the failed command's _logs slice. This server command returns
    # an error without emitting a push_error, so the slice is empty —
    # but the attribute must exist and be the right type.
    with pytest.raises(Exception) as exc_info:
        game.get_property("/root/Menu", "this_property_does_not_exist_xyz")
    err = exc_info.value
    assert hasattr(err, "logs"), (
        f"exception type {type(err).__name__} missing 'logs' attribute"
    )
    assert isinstance(err.logs, list)


def test_collected_logs_picks_up_error_from_prior_command(game):
    # Verify the test-level accumulator correctly picks up errors emitted
    # during a successful command (the call_method path) and keeps them
    # available for downstream assertions.
    game.call("/root/Menu", "e2e_emit_error", ["PRE_ERROR_TAG"])
    msgs = [e.message for e in game.collected_logs if e.level == "error"]
    assert any("PRE_ERROR_TAG" in m for m in msgs)


# ---------------------------------------------------------------------------
# Buffer overflow accounting — exercises the GDScript _evicted_high_seq
# path that the Python mock tests can't reach.
# ---------------------------------------------------------------------------

def test_buffer_overflow_reports_dropped_count(game):
    # Shrink the ring buffer to a known size, then emit more than that
    # in a single command so the response carries both truncated entries
    # AND a _logs_dropped count. The point is to exercise the real
    # GDScript drain_since arithmetic — the Python mock path can't.
    BUFFER_SIZE = 5
    BURST_COUNT = 20
    game.set_log_buffer_size(BUFFER_SIZE)
    game.reset_collected_logs()

    game.call("/root/Menu", "e2e_emit_many_warnings", [BURST_COUNT])

    # Every emit_many warning is push_warning ("warning" level). The
    # response's _logs slice can carry at most BUFFER_SIZE warning
    # entries; the remaining BURST_COUNT - BUFFER_SIZE were evicted and
    # surface as a dropped marker.
    burst_entries = [e for e in game.last_logs
                     if e.level == "warning" and "BURST_" in e.message]
    dropped_markers = [e for e in game.last_logs
                       if "dropped" in e.message]

    assert len(burst_entries) <= BUFFER_SIZE, (
        f"expected at most {BUFFER_SIZE} burst entries, got {len(burst_entries)}"
    )
    assert len(dropped_markers) == 1, (
        f"expected exactly one dropped marker, got {len(dropped_markers)}"
    )
    # The marker's count must equal the actual loss within the burst.
    expected_dropped = BURST_COUNT - len(burst_entries)
    marker_msg = dropped_markers[0].message
    assert str(expected_dropped) in marker_msg, (
        f"dropped marker {marker_msg!r} should contain {expected_dropped}"
    )

    # Restore default buffer for downstream tests.
    game.set_log_buffer_size(200)


def test_set_log_buffer_size_rejects_invalid_at_python_boundary(game):
    # The Python wrapper validates before sending — so size < 1 raises
    # ValueError without ever hitting the wire.
    with pytest.raises(ValueError, match="positive int"):
        game.set_log_buffer_size(0)
    with pytest.raises(ValueError, match="positive int"):
        game.set_log_buffer_size(-3)


def test_set_log_buffer_size_rejects_invalid_at_wire_boundary(game):
    # Direct wire calls bypass the Python validator — the server-side
    # handler must still reject invalid values with invalid_argument.
    from godot_e2e import CommandError
    with pytest.raises(CommandError):
        game._client.send_command("set_log_buffer_size", size=0)
    with pytest.raises(CommandError):
        game._client.send_command("set_log_buffer_size", size=-3)


# ---------------------------------------------------------------------------
# Startup verbosity flag — exercises the launcher path that's separate
# from the runtime set_log_verbosity command.
# ---------------------------------------------------------------------------

def test_startup_log_verbosity_flag_takes_effect():
    # Launch a standalone Godot with --e2e-log-verbosity=info baked in
    # at startup. The launcher must apply it before any command runs, so
    # the very first call that emits print() should see the line in
    # collected_logs without us calling set_log_verbosity.
    import os
    from godot_e2e import GodotE2E

    # Resolve the same GODOT_PROJECT path the conftest uses, without a
    # relative import (this directory isn't a package).
    here = os.path.abspath(os.path.dirname(__file__))
    example_root = os.path.dirname(os.path.dirname(here))
    project_path = os.path.join(example_root, "godot_project")

    with GodotE2E.launch(
        project_path,
        godot_path=os.environ.get("GODOT_PATH"),
        timeout=30.0,
        log_verbosity="info",
    ) as g:
        g.wait_for_node("/root/Menu", timeout=10.0)
        g.reset_collected_logs()

        g.call("/root/Menu", "e2e_emit_print", ["STARTUP_PRINT_TAG"])

        msgs = [e.message for e in g.collected_logs]
        assert any("STARTUP_PRINT_TAG" in m for m in msgs), (
            "expected --e2e-log-verbosity=info to capture print() at startup, "
            f"got {msgs!r}"
        )
