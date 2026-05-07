"""Unit tests for Locator (mock client, no Godot)."""

import pytest

from godot_e2e import Locator, MultipleMatchesError, NodeNotFoundError, NotActionableError
from godot_e2e.locator import _build_query, _format_paths_for_error


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------

class MockClient:
    """Records send_command calls and returns canned responses.

    ``responses`` is a list keyed by call order. Each item is either:
      - a dict (returned as-is)
      - an exception instance (raised)
    """

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def send_command(self, action, **kwargs):
        self.calls.append((action, kwargs))
        if not self.responses:
            return {}
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# ---------------------------------------------------------------------------
# _build_query
# ---------------------------------------------------------------------------

def test_build_query_requires_kwargs():
    with pytest.raises(ValueError):
        _build_query({})


def test_build_query_rejects_unknown_keyword():
    with pytest.raises(ValueError, match="unknown locator strategy"):
        _build_query({"foo": "bar"})


def test_build_query_single_keyword():
    q = _build_query({"name": "Btn"})
    assert q == {"by": "name", "value": "Btn", "filters": []}


def test_build_query_multi_keyword_becomes_primary_plus_filters():
    q = _build_query({"type": "Button", "text": "Save"})
    assert q["by"] == "type"
    assert q["value"] == "Button"
    assert q["filters"] == [{"by": "text", "value": "Save"}]


# ---------------------------------------------------------------------------
# _format_paths_for_error
# ---------------------------------------------------------------------------

def test_format_paths_short():
    s = _format_paths_for_error(["/a", "/b", "/c"])
    assert s == "/a, /b, /c"


def test_format_paths_truncates_when_long():
    paths = [f"/n{i}" for i in range(15)]
    s = _format_paths_for_error(paths)
    assert s.endswith("...and 10 more")
    # The first five should be present.
    assert "/n0" in s and "/n4" in s
    # Nothing past index 4 should be in the head.
    assert "/n5" not in s.split(",")[5] if len(s.split(",")) > 5 else True


# ---------------------------------------------------------------------------
# Locator resolution
# ---------------------------------------------------------------------------

def _loc(client, **kwargs):
    return Locator(client, _build_query(kwargs))


def test_resolve_no_match_raises_node_not_found():
    client = MockClient(responses=[{"nodes": []}])
    with pytest.raises(NodeNotFoundError):
        _loc(client, name="Foo").get_property("text")


def test_resolve_multi_match_raises_multiple():
    client = MockClient(responses=[{"nodes": ["/a", "/b", "/c"]}])
    with pytest.raises(MultipleMatchesError) as excinfo:
        _loc(client, type="Button").get_property("text")
    assert excinfo.value.paths == ["/a", "/b", "/c"]


def test_first_picks_first():
    client = MockClient(responses=[
        {"nodes": ["/a", "/b", "/c"]},
        {"result": "ok"},
    ])
    val = _loc(client, type="Button").first().get_property("text")
    assert val == "ok"
    assert client.calls[1] == ("get_property", {"path": "/a", "property": "text"})


def test_nth_picks_index():
    client = MockClient(responses=[
        {"nodes": ["/a", "/b", "/c"]},
        {"result": "ok"},
    ])
    val = _loc(client, type="Button").nth(2).get_property("text")
    assert val == "ok"
    assert client.calls[1][1]["path"] == "/c"


def test_nth_out_of_range_raises():
    client = MockClient(responses=[{"nodes": ["/a"]}])
    with pytest.raises(NodeNotFoundError, match="out of range"):
        _loc(client, type="Button").nth(5).get_property("text")


def test_all_returns_path_pinned_locators():
    client = MockClient(responses=[{"nodes": ["/a", "/b"]}])
    locs = _loc(client, type="Button").all()
    assert len(locs) == 2
    # Each Locator's query should be path-pinned.
    assert locs[0]._query == {"by": "path", "value": "/a", "filters": []}
    assert locs[1]._query == {"by": "path", "value": "/b", "filters": []}


def test_filter_appends_predicate():
    client = MockClient(responses=[{"nodes": []}])
    loc = _loc(client, type="Button").filter(text="Save")
    assert loc._query == {
        "by": "type",
        "value": "Button",
        "filters": [{"by": "text", "value": "Save"}],
    }


def test_filter_rejects_unknown():
    client = MockClient()
    with pytest.raises(ValueError, match="unknown filter strategy"):
        _loc(client, type="Button").filter(foo="bar")


def test_nth_negative_rejected():
    client = MockClient()
    with pytest.raises(ValueError):
        _loc(client, type="Button").nth(-1)


# ---------------------------------------------------------------------------
# Inspection helpers (no raise on multi/zero where stated)
# ---------------------------------------------------------------------------

def test_exists_true():
    client = MockClient(responses=[{"nodes": ["/a"]}])
    assert _loc(client, name="X").exists() is True


def test_exists_false_on_zero():
    client = MockClient(responses=[{"nodes": []}])
    assert _loc(client, name="X").exists() is False


def test_count():
    client = MockClient(responses=[{"nodes": ["/a", "/b", "/c"]}])
    assert _loc(client, type="Button").count() == 3


def test_is_visible_reads_check():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"actionable": False, "checks": {"control": True, "visible": False, "mouse_filter_ok": True, "in_viewport": True}},
    ])
    assert _loc(client, name="X").is_visible() is False


def test_is_actionable_reads_top_level():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"actionable": True, "checks": {}},
    ])
    assert _loc(client, name="X").is_actionable() is True


# ---------------------------------------------------------------------------
# Click flow
# ---------------------------------------------------------------------------

def test_click_polls_actionable_then_clicks():
    client = MockClient(responses=[
        {"nodes": ["/a"]},                              # _resolve_one
        {"actionable": True, "checks": {"control": True}},  # node_actionable
        {"ok": True},                                    # click_node
    ])
    _loc(client, name="X").click()
    actions = [c[0] for c in client.calls]
    assert actions == ["find_nodes", "node_actionable", "click_node"]


def test_click_force_skips_actionability():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"ok": True},
    ])
    _loc(client, name="X").click(force=True)
    actions = [c[0] for c in client.calls]
    assert actions == ["find_nodes", "click_node"]
    # No node_actionable call.
    assert not any(c[0] == "node_actionable" for c in client.calls)


def test_click_raises_not_actionable_after_timeout():
    """Polling returns False repeatedly; eventually raises NotActionableError."""
    # Provide enough non-actionable responses that timeout is hit.
    not_actionable = {
        "actionable": False,
        "reasons": ["not_visible_in_tree"],
        "checks": {"control": True, "visible": False},
    }
    # 1 find_nodes + ~5 polls; mock returns the same forever-ish.
    responses = [{"nodes": ["/a"]}] + [not_actionable] * 200
    client = MockClient(responses=responses)
    with pytest.raises(NotActionableError) as excinfo:
        _loc(client, name="X").click(timeout=0.1)
    assert "not_visible_in_tree" in str(excinfo.value)
    assert excinfo.value.path == "/a"


# ---------------------------------------------------------------------------
# Chaining
# ---------------------------------------------------------------------------

def test_chained_locator_uses_parent_path_as_start():
    client = MockClient(responses=[
        {"nodes": ["/root/Menu/VBox"]},   # parent resolution
        {"nodes": ["/root/Menu/VBox/Button"]},  # child resolution
        {"ok": True},                      # click
    ])
    _loc(client, name="VBox").locator(type="Button").click(force=True)
    # Second find_nodes should carry start_path
    second = client.calls[1]
    assert second[0] == "find_nodes"
    assert second[1]["start_path"] == "/root/Menu/VBox"


def test_chained_locator_requires_single_parent():
    client = MockClient(responses=[
        {"nodes": ["/a", "/b"]},  # parent has 2 matches
    ])
    parent = _loc(client, type="Button")
    with pytest.raises(MultipleMatchesError):
        parent.locator(name="X")


# ---------------------------------------------------------------------------
# Action plumbing
# ---------------------------------------------------------------------------

def test_get_property_passes_path_and_prop():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"result": 42},
    ])
    val = _loc(client, name="X").get_property("counter")
    assert val == 42
    assert client.calls[1] == ("get_property", {"path": "/a", "property": "counter"})


def test_set_property_serializes_value():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"ok": True},
    ])
    _loc(client, name="X").set_property("text", "hello")
    assert client.calls[1] == ("set_property", {"path": "/a", "property": "text", "value": "hello"})


def test_call_method_serializes_args():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"result": "ok"},
    ])
    _loc(client, name="X").call("do_thing", [1, "two"])
    action, kw = client.calls[1]
    assert action == "call_method"
    assert kw["method"] == "do_thing"
    assert kw["args"] == [1, "two"]


def test_hover_dispatches_hover_node():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"ok": True},
    ])
    _loc(client, name="X").hover()
    assert client.calls[1] == ("hover_node", {"path": "/a"})


def test_wait_for_signal_dispatches():
    client = MockClient(responses=[
        {"nodes": ["/a"]},
        {"args": ["payload"]},
    ])
    args = _loc(client, name="X").wait_for_signal("pressed", timeout=2.0)
    assert args == ["payload"]
    assert client.calls[1][0] == "wait_for_signal"
    assert client.calls[1][1]["signal_name"] == "pressed"


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------

def test_repr_includes_query():
    client = MockClient()
    s = repr(_loc(client, name="X"))
    assert "Locator(" in s
    assert "'name'" in s


def test_repr_includes_index_and_start_path_when_set():
    client = MockClient()
    base = _loc(client, name="X")
    chained = Locator(client, base._query, start_path="/root/Menu", index=1)
    s = repr(chained)
    assert "start_path='/root/Menu'" in s
    assert "index=1" in s
