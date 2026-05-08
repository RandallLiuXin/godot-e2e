"""Unit tests for the ``expect()`` auto-retry assertion API.

These run against a mock client; the polling cadence is driven by
``time.monotonic`` and ``time.sleep`` which we monkeypatch to advance
deterministically. No Godot is launched.
"""

from __future__ import annotations

import pytest

from godot_e2e import (
    CommandError,
    ExpectationFailedError,
    Locator,
    MultipleMatchesError,
    NodeNotFoundError,
    expect,
)
from godot_e2e.locator import _build_query


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------

class MockClient:
    """Mock client for unit tests.

    Two ways to script responses, used together as needed:

    - ``responses``: ordered queue (consumed by ``send_command`` in
      arrival order, regardless of action). Items are dicts, exceptions,
      or zero-arg callables returning either. Used when the test needs
      tight per-call control.

    - ``defaults``: ``{action: dict_or_callable}``, returned whenever
      the queue is empty. Used to model "the polling state never
      changes" without piling 200 entries into ``responses``.

    Convention: tests that drive a polling loop set ``defaults`` for the
    polling actions (``find_nodes``, ``get_property``, etc.) and use
    ``responses`` only for the trailing one-shot ``get_tree`` failure
    dump (or to override one specific iteration).
    """

    def __init__(self, responses=None, defaults=None):
        self.responses = list(responses or [])
        self.defaults = dict(defaults or {})
        self.calls = []

    def send_command(self, action, **kwargs):
        self.calls.append((action, kwargs))
        if self.responses:
            item = self.responses.pop(0)
        elif action in self.defaults:
            item = self.defaults[action]
        else:
            return {}
        if callable(item):
            item = item()
        if isinstance(item, Exception):
            raise item
        return item


def _loc(client, **kwargs):
    return Locator(client, _build_query(kwargs))


# ---------------------------------------------------------------------------
# Deterministic time control
# ---------------------------------------------------------------------------

class _Clock:
    """Monkeypatch target for time.monotonic / time.sleep.

    ``monotonic()`` returns the cumulative virtual time. ``sleep(s)``
    advances it by ``s``. No real waiting happens.
    """

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    c = _Clock()
    # `from .expect import expect` in godot_e2e/__init__.py shadows the
    # submodule attribute with the function, so attribute lookup
    # `godot_e2e.expect` returns the function. Reach the actual module
    # object via sys.modules instead.
    import sys
    expect_mod = sys.modules["godot_e2e.expect"]
    monkeypatch.setattr(expect_mod.time, "monotonic", c.monotonic)
    monkeypatch.setattr(expect_mod.time, "sleep", c.sleep)
    return c


# ---------------------------------------------------------------------------
# expect() input validation
# ---------------------------------------------------------------------------

def test_expect_rejects_non_locator():
    with pytest.raises(TypeError, match="Locator"):
        expect("/root/Main")


def test_expect_rejects_negative_timeout():
    client = MockClient()
    with pytest.raises(ValueError, match="timeout"):
        expect(_loc(client, name="X"), timeout=-1)


def test_expect_rejects_nonpositive_poll_interval():
    client = MockClient()
    with pytest.raises(ValueError, match="poll_interval"):
        expect(_loc(client, name="X"), poll_interval=0)


# ---------------------------------------------------------------------------
# to_have_property
# ---------------------------------------------------------------------------

def test_to_have_property_passes_immediately(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/A"]},
        {"result": 5},
    ])
    expect(_loc(client, name="A")).to_have_property("counter", 5)


def test_to_have_property_passes_after_polling(clock):
    # Each retry costs a find_nodes + get_property pair (resolve every
    # call). Counter ticks 0, 0, then 5.
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 0},
        {"nodes": ["/root/A"]}, {"result": 0},
        {"nodes": ["/root/A"]}, {"result": 5},
    ])
    expect(_loc(client, name="A"), poll_interval=0.1).to_have_property("counter", 5)
    assert clock.now == pytest.approx(0.2)


def test_to_have_property_times_out_with_last_value(clock):
    # Stuck at 3; never reaches 5. Defaults route by action so the
    # polling loop and the trailing get_tree dump don't collide on a
    # shared queue.
    client = MockClient(defaults={
        "find_nodes": {"nodes": ["/root/A"]},
        "get_property": {"result": 3},
        "get_tree": {"tree": {"name": "root"}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.5, poll_interval=0.1).to_have_property("counter", 5)
    assert excinfo.value.actual == 3
    assert excinfo.value.matcher == "to_have_property('counter', 5)"
    assert excinfo.value.timeout == 0.5
    assert excinfo.value.scene_tree == {"name": "root"}
    assert "last observed: 3" in str(excinfo.value)


def test_to_have_property_swallows_node_not_found_during_poll(clock):
    # Node missing on first poll, present on second.
    client = MockClient(responses=[
        {"nodes": []},                                  # NodeNotFoundError
        {"nodes": ["/root/A"]}, {"result": 5},          # success
    ])
    expect(_loc(client, name="A"), poll_interval=0.1).to_have_property("counter", 5)


def test_to_have_property_swallows_command_error_during_poll(clock):
    # CommandError mid-poll (transient server hiccup) is absorbed; the
    # next iteration succeeds. This pins the contract that CommandError
    # is retriable, not propagated.
    client = MockClient(responses=[
        {"nodes": ["/root/A"]},
        CommandError("transient server hiccup"),       # raised by get_property
        {"nodes": ["/root/A"]}, {"result": 7},          # success
    ])
    expect(_loc(client, name="A"), poll_interval=0.05).to_have_property("counter", 7)


def test_to_have_property_matches_legitimate_none(clock):
    # Property whose actual value is None must satisfy
    # to_have_property("...", None) — the _UNSET sentinel must be
    # distinguishable from a legitimate None observation. This pairs
    # with test_failure_marks_observation_captured below for the
    # failure-side proof.
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": None},
    ])
    expect(_loc(client, name="A")).to_have_property("nullable_prop", None)


def test_to_have_property_propagates_unexpected_error(clock):
    # RuntimeError is not a known transient — must surface.
    def boom():
        raise RuntimeError("unrelated bug")

    client = MockClient(responses=[boom])
    with pytest.raises(RuntimeError, match="unrelated bug"):
        expect(_loc(client, name="A")).to_have_property("counter", 5)


# ---------------------------------------------------------------------------
# to_have_text
# ---------------------------------------------------------------------------

def test_to_have_text_passes(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/L"]},
        {"result": "Score: 10"},
    ])
    expect(_loc(client, name="L")).to_have_text("Score: 10")


def test_to_have_text_failure_message_includes_last_value(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/L"]}, {"result": "Score: 9"},
        {"tree": {}},  # tree dump
    ])
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="L"), timeout=0.0).to_have_text("Score: 10")
    assert excinfo.value.actual == "Score: 9"
    assert "to_have_text('Score: 10')" in excinfo.value.matcher


# ---------------------------------------------------------------------------
# to_be_visible
# ---------------------------------------------------------------------------

def test_to_be_visible_passes(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/M"]},
        {"checks": {"visible": True}},
    ])
    expect(_loc(client, name="M")).to_be_visible()


def test_to_be_visible_polls_until_true(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/M"]}, {"checks": {"visible": False}},
        {"nodes": ["/root/M"]}, {"checks": {"visible": False}},
        {"nodes": ["/root/M"]}, {"checks": {"visible": True}},
    ])
    expect(_loc(client, name="M"), poll_interval=0.05).to_be_visible()


# ---------------------------------------------------------------------------
# to_exist
# ---------------------------------------------------------------------------

def test_to_exist_passes(clock):
    client = MockClient(responses=[{"nodes": ["/root/E"]}])
    expect(_loc(client, name="E")).to_exist()


def test_to_exist_polls_until_node_appears(clock):
    client = MockClient(responses=[
        {"nodes": []},
        {"nodes": []},
        {"nodes": ["/root/E"]},
    ])
    expect(_loc(client, name="E"), poll_interval=0.1).to_exist()


def test_to_exist_times_out(clock):
    client = MockClient(defaults={
        "find_nodes": {"nodes": []},
        "get_tree": {"tree": {}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="E"), timeout=0.4, poll_interval=0.1).to_exist()
    assert excinfo.value.matcher == "to_exist()"


# ---------------------------------------------------------------------------
# to_satisfy
# ---------------------------------------------------------------------------

def test_to_satisfy_passes_with_locator_predicate(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 7},
    ])
    expect(_loc(client, name="A")).to_satisfy(
        lambda loc: loc.get_property("counter") > 5,
        description="counter > 5",
    )


def test_to_satisfy_swallows_lookup_errors_during_polling(clock):
    # Predicate calls get_property; node is missing initially, then appears.
    client = MockClient(responses=[
        {"nodes": []},                                       # NodeNotFoundError
        {"nodes": ["/root/A", "/root/B"]},                   # MultipleMatchesError
        {"nodes": ["/root/A"]}, {"result": 10},              # success
    ])
    expect(_loc(client, name="A"), poll_interval=0.05).to_satisfy(
        lambda loc: loc.get_property("counter") == 10,
        description="counter == 10",
    )


def test_to_satisfy_failure_uses_description(clock):
    # Predicate stays false; verify description appears in matcher label.
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 0},
        {"tree": {}},
    ])
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.0).to_satisfy(
            lambda loc: loc.get_property("counter") > 0,
            description="counter > 0",
        )
    assert excinfo.value.matcher == "to_satisfy('counter > 0')"


def test_to_satisfy_without_description_falls_back_to_repr(clock):
    pred = lambda loc: False  # noqa: E731
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 0},
        {"tree": {}},
    ])
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.0).to_satisfy(pred)
    # Fallback uses repr(predicate) — the exact string varies (lambda
    # repr includes file:line) but it must mention "lambda".
    assert "lambda" in excinfo.value.matcher.lower()


def test_to_satisfy_propagates_unexpected_error(clock):
    # ValueError raised by predicate should not be swallowed.
    def boom(loc):
        raise ValueError("predicate bug")

    client = MockClient()
    with pytest.raises(ValueError, match="predicate bug"):
        expect(_loc(client, name="A")).to_satisfy(boom)


# ---------------------------------------------------------------------------
# Failure-path diagnostics
# ---------------------------------------------------------------------------

def test_failure_attaches_scene_tree(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 1},
        {"tree": {"name": "root", "children": [{"name": "A"}]}},
    ])
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.0).to_have_property("x", 2)
    assert excinfo.value.scene_tree == {"name": "root", "children": [{"name": "A"}]}


def test_failure_tolerates_tree_dump_error(clock):
    # Polling fails, then the get_tree call also errors — the matcher
    # must still raise the original ExpectationFailedError, not the
    # tree-dump exception.
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 1},
        CommandError("tree dump failed"),
    ])
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.0).to_have_property("x", 2)
    assert excinfo.value.scene_tree is None


def test_failure_when_node_never_resolves(clock):
    # Node missing throughout. last observation is _UNSET.
    client = MockClient(defaults={
        "find_nodes": {"nodes": []},
        "get_tree": {"tree": {}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.2, poll_interval=0.1).to_have_property("x", 1)
    assert excinfo.value.actual is None
    assert "no successful observation" in str(excinfo.value)


def test_failure_when_locator_keeps_multimatching(clock):
    # Stable multi-match without .first() / .filter() also lands at the
    # _UNSET branch (every poll raises MultipleMatchesError, swallowed).
    # The failure wording must stay neutral — "node never resolved"
    # would be wrong here.
    client = MockClient(defaults={
        "find_nodes": {"nodes": ["/root/A", "/root/B"]},
        "get_tree": {"tree": {}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.2, poll_interval=0.1).to_have_property("x", 1)
    assert excinfo.value.actual is None
    assert "no successful observation" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Dual inheritance — pytest catches it as AssertionError
# ---------------------------------------------------------------------------

def test_expectation_failed_is_assertion_error(clock):
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 1},
        {"tree": {}},
    ])
    # except AssertionError must catch ExpectationFailedError so plain
    # pytest assertion handling treats it as an assertion failure
    # (better diff rendering, lands in the assertion section, etc.).
    with pytest.raises(AssertionError):
        expect(_loc(client, name="A"), timeout=0.0).to_have_property("x", 2)


def test_expectation_failed_also_caught_as_godot_e2e_error(clock):
    from godot_e2e import GodotE2EError
    client = MockClient(responses=[
        {"nodes": ["/root/A"]}, {"result": 1},
        {"tree": {}},
    ])
    with pytest.raises(GodotE2EError):
        expect(_loc(client, name="A"), timeout=0.0).to_have_property("x", 2)


# ---------------------------------------------------------------------------
# observation_captured + last_error fields on the exception
# ---------------------------------------------------------------------------

def test_failure_marks_observation_captured_true_when_value_seen(clock):
    # When a value WAS observed (just not the desired one),
    # observation_captured should be True and `actual` should hold the
    # last seen value — even if that value happens to be falsy.
    client = MockClient(defaults={
        "find_nodes": {"nodes": ["/root/A"]},
        "get_property": {"result": 0},   # falsy but real observation
        "get_tree": {"tree": {}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.2, poll_interval=0.1).to_have_property("counter", 5)
    assert excinfo.value.observation_captured is True
    assert excinfo.value.actual == 0


def test_failure_marks_observation_captured_false_when_no_observation(clock):
    # When no poll ever returned a value (every poll raised a swallowed
    # error), observation_captured must be False — distinguishes "saw
    # None" from "never saw anything".
    client = MockClient(defaults={
        "find_nodes": {"nodes": []},  # NodeNotFoundError every poll
        "get_tree": {"tree": {}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.2, poll_interval=0.1).to_have_property("x", 1)
    assert excinfo.value.observation_captured is False
    assert excinfo.value.actual is None


def test_failure_carries_last_command_error(clock):
    # When polling never succeeds because every get_property raises
    # CommandError, surface the last one in `last_error` and in the
    # message — this is the diagnostic that turns "opaque timeout"
    # into "the property doesn't exist on this node, dummy".
    client = MockClient(defaults={
        "find_nodes": {"nodes": ["/root/A"]},
        "get_property": CommandError("Property 'missing' not found"),
        "get_tree": {"tree": {}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.2, poll_interval=0.1).to_have_property("missing", 1)
    assert isinstance(excinfo.value.last_error, CommandError)
    assert "Property 'missing' not found" in str(excinfo.value.last_error)
    assert "last server error" in str(excinfo.value)
    assert excinfo.value.observation_captured is False


def test_failure_last_error_is_none_when_no_command_error_seen(clock):
    # When the only swallowed errors during polling were lookup-flavored
    # (NodeNotFoundError / MultipleMatchesError), last_error should be
    # None — those aren't surfaced because they're the normal
    # "still looking" signal.
    client = MockClient(defaults={
        "find_nodes": {"nodes": []},  # NodeNotFoundError throughout
        "get_tree": {"tree": {}},
    })
    with pytest.raises(ExpectationFailedError) as excinfo:
        expect(_loc(client, name="A"), timeout=0.2, poll_interval=0.1).to_have_property("x", 1)
    assert excinfo.value.last_error is None
    assert "last server error" not in str(excinfo.value)
