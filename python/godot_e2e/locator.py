"""Lazy, multi-strategy reference to a node in the running scene tree.

A ``Locator`` holds a query (by name/text/group/type/script/path, optionally
composed with filters) and re-resolves it on every action. This keeps tests
robust against scene reloads and refactors that move nodes around.

Typical usage::

    button = game.locator(text="Start")
    button.click()                              # auto-waits for visibility

    game.locator(group="enemies").filter(name="*Boss*").first().call("die")

    for btn in game.locator(type="BaseButton").all():
        btn.click()

The class is constructed via ``GodotE2E.locator(...)`` /
``game.get_by_text(...)`` / ``game.get_by_button(...)``; users do not
instantiate ``Locator`` directly.
"""

from __future__ import annotations

import time
from copy import deepcopy
from typing import Optional

from .types import (
    CommandError,
    MultipleMatchesError,
    NodeNotFoundError,
    NotActionableError,
    TimeoutError,
    deserialize,
    serialize,
)


_VALID_BY = {"path", "name", "group", "text", "script", "type"}


def _build_query(kwargs: dict) -> dict:
    """Turn keyword args into the wire query dict.

    With one kwarg, the kwarg becomes the primary ``by``. With multiple,
    the first becomes primary and the rest are appended as filters. The
    chosen primary affects nothing observable on the server, since all
    predicates are AND-composed; we just need a stable convention.
    """
    if not kwargs:
        raise ValueError(
            "locator() requires at least one of: "
            + ", ".join(sorted(_VALID_BY))
        )
    bad = [k for k in kwargs if k not in _VALID_BY]
    if bad:
        raise ValueError(
            f"unknown locator strategy: {bad}. "
            f"valid: {sorted(_VALID_BY)}"
        )
    items = list(kwargs.items())
    primary_by, primary_value = items[0]
    filters = [{"by": k, "value": v} for k, v in items[1:]]
    return {"by": primary_by, "value": primary_value, "filters": filters}


def _format_paths_for_error(paths: list) -> str:
    """Truncate long match lists for readable error messages."""
    if len(paths) <= 10:
        return ", ".join(paths)
    head = ", ".join(paths[:5])
    return f"{head}, ...and {len(paths) - 5} more"


class Locator:
    """Lazy reference to one or more scene-tree nodes.

    Instances are returned by ``GodotE2E.locator(...)`` and friends. Each
    action method (``click``, ``get_property``, ...) re-runs the query
    against the live scene tree, so a Locator created before
    ``reload_scene()`` is still valid afterwards.
    """

    def __init__(
        self,
        client,
        query: dict,
        *,
        start_path: str = "/root",
        index: Optional[int] = None,
    ):
        self._client = client
        self._query = query
        self._start_path = start_path
        # None: require exactly one match. Otherwise: nth() / first() chose i.
        self._index = index

    # ------------------------------------------------------------------
    # Refinement (returns a new Locator, never mutates self)
    # ------------------------------------------------------------------

    def filter(self, **kwargs) -> "Locator":
        """Return a new Locator with additional AND-composed predicates."""
        if not kwargs:
            raise ValueError("filter() requires at least one keyword")
        bad = [k for k in kwargs if k not in _VALID_BY]
        if bad:
            raise ValueError(
                f"unknown filter strategy: {bad}. valid: {sorted(_VALID_BY)}"
            )
        new_query = deepcopy(self._query)
        new_query.setdefault("filters", [])
        for k, v in kwargs.items():
            new_query["filters"].append({"by": k, "value": v})
        return Locator(
            self._client, new_query,
            start_path=self._start_path, index=self._index,
        )

    def first(self) -> "Locator":
        """Return a Locator that always picks the first match."""
        return Locator(
            self._client, deepcopy(self._query),
            start_path=self._start_path, index=0,
        )

    def nth(self, i: int) -> "Locator":
        """Return a Locator that picks the i-th match (zero-indexed)."""
        if i < 0:
            raise ValueError("nth() index must be >= 0")
        return Locator(
            self._client, deepcopy(self._query),
            start_path=self._start_path, index=i,
        )

    def all(self) -> list:
        """Resolve now and return one Locator per match.

        Each returned Locator is path-pinned, so it remains stable even if
        the original query later starts matching different nodes. This is
        a snapshot at call time; tree mutations after this call do not
        update the returned list.
        """
        paths = self._resolve_all()
        return [
            Locator(
                self._client,
                {"by": "path", "value": p, "filters": []},
                start_path=self._start_path,
            )
            for p in paths
        ]

    def locator(self, **kwargs) -> "Locator":
        """Chained sub-query scoped under this Locator's resolved node.

        The parent must resolve to exactly one node — multi-match parents
        without ``.first()`` / ``.nth(i)`` / ``.filter(...)`` raise
        ``MultipleMatchesError``.
        """
        parent_path = self._resolve_one()
        return Locator(self._client, _build_query(kwargs), start_path=parent_path)

    # ------------------------------------------------------------------
    # Resolution (private)
    # ------------------------------------------------------------------

    def _resolve_all(self) -> list:
        resp = self._client.send_command(
            "find_nodes", query=self._query, start_path=self._start_path
        )
        return resp.get("nodes", [])

    def _resolve_one(self) -> str:
        paths = self._resolve_all()
        if not paths:
            raise NodeNotFoundError(
                f"No node matches query {self._query!r} under {self._start_path!r}"
            )
        if self._index is not None:
            if self._index >= len(paths):
                raise NodeNotFoundError(
                    f"index {self._index} out of range; only {len(paths)} match(es) "
                    f"for query {self._query!r}"
                )
            return paths[self._index]
        if len(paths) > 1:
            raise MultipleMatchesError(
                f"{len(paths)} nodes match query {self._query!r}: "
                f"{_format_paths_for_error(paths)}. "
                f"Use .first() / .nth(i) / .filter(...) to disambiguate.",
                paths=paths,
            )
        return paths[0]

    # ------------------------------------------------------------------
    # Inspection (does not raise on multi/zero match where noted)
    # ------------------------------------------------------------------

    def exists(self) -> bool:
        """True if the query resolves to one or more nodes. Never raises."""
        try:
            return bool(self._resolve_all())
        except CommandError:
            return False

    def count(self) -> int:
        """Number of matching nodes. Never raises on multi-match."""
        return len(self._resolve_all())

    def is_visible(self) -> bool:
        """Whether the (single-match) target is visible in the scene tree.

        Raises ``MultipleMatchesError`` / ``NodeNotFoundError`` if the
        Locator does not resolve to exactly one node.
        """
        path = self._resolve_one()
        resp = self._client.send_command("node_actionable", path=path)
        return bool(resp.get("checks", {}).get("visible", False))

    def is_actionable(self) -> bool:
        """Whether the (single-match) target passes all actionability checks.

        Raises ``MultipleMatchesError`` / ``NodeNotFoundError`` if the
        Locator does not resolve to exactly one node.
        """
        path = self._resolve_one()
        resp = self._client.send_command("node_actionable", path=path)
        return bool(resp.get("actionable", False))

    # ------------------------------------------------------------------
    # Actions (re-resolve every call)
    # ------------------------------------------------------------------

    def click(self, *, force: bool = False, button: int = 1, timeout: float = 5.0):
        """Click the node's screen position.

        For Control targets, blocks until the actionability check passes
        (visible_in_tree + mouse_filter + viewport intersect) or times out.
        Pass ``force=True`` to skip the check.
        """
        path = self._resolve_one()
        if not force:
            self._wait_actionable(path, timeout=timeout)
        # button is reserved for future use; click_node is currently
        # left-button only on the server side. Accept the parameter so the
        # signature is forward-compatible with right/middle clicks.
        _ = button
        self._client.send_command("click_node", path=path)

    def hover(self):
        """Move the (simulated) mouse over the node's screen position.

        Useful for testing tooltips and hover-driven UI. Note that this
        injects a real ``InputEventMouseMotion`` and so triggers
        ``mouse_entered`` / ``_gui_input`` on Controls along the way.
        """
        path = self._resolve_one()
        self._client.send_command("hover_node", path=path)

    def get_property(self, prop: str):
        path = self._resolve_one()
        resp = self._client.send_command("get_property", path=path, property=prop)
        return deserialize(resp["result"])

    def set_property(self, prop: str, value):
        path = self._resolve_one()
        self._client.send_command(
            "set_property", path=path, property=prop, value=serialize(value)
        )

    def call(self, method: str, args: list = None):
        path = self._resolve_one()
        resp = self._client.send_command(
            "call_method", path=path, method=method,
            args=[serialize(a) for a in (args or [])],
        )
        return deserialize(resp.get("result"))

    def wait_visible(self, *, timeout: float = 5.0):
        """Block until the (resolved) target passes actionability checks.

        Same checks as auto-wait before ``click``. Raises ``TimeoutError``
        if the deadline elapses or the node disappears mid-wait.
        """
        deadline = time.monotonic() + timeout
        last_reasons = ["unresolved"]
        last_path = "<unresolved>"
        while time.monotonic() < deadline:
            try:
                path = self._resolve_one()
                last_path = path
            except NodeNotFoundError:
                time.sleep(0.05)
                continue
            resp = self._client.send_command("node_actionable", path=path)
            if resp.get("actionable", False):
                return
            last_reasons = resp.get("reasons", [])
            time.sleep(0.05)
        raise TimeoutError(
            f"Timed out after {timeout}s waiting for {last_path!r} "
            f"to become actionable; last reasons: {last_reasons}"
        )

    def wait_for_signal(self, signal_name: str, timeout: float = 5.0):
        """Block until the (resolved) node emits the named signal.

        Returns the list of signal arguments. Raises if the signal does
        not fire before ``timeout``.
        """
        path = self._resolve_one()
        resp = self._client.send_command(
            "wait_for_signal", path=path, signal_name=signal_name, timeout=timeout
        )
        return resp.get("args", [])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_actionable(self, path: str, *, timeout: float):
        deadline = time.monotonic() + timeout
        last_reasons: list = []
        last_checks: dict = {}
        while time.monotonic() < deadline:
            resp = self._client.send_command("node_actionable", path=path)
            if resp.get("actionable", False):
                return
            last_reasons = resp.get("reasons", [])
            last_checks = resp.get("checks", {})
            # If the node is non-Control we never poll-fail; node_actionable
            # would return actionable=True on the first call. So if we get
            # here, it's a Control and we should keep polling.
            time.sleep(0.05)
        raise NotActionableError(
            f"{path!r} did not become actionable within {timeout}s; "
            f"reasons: {last_reasons}",
            path=path, reasons=last_reasons, checks=last_checks,
        )

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        parts: list = [f"query={self._query!r}"]
        if self._start_path != "/root":
            parts.append(f"start_path={self._start_path!r}")
        if self._index is not None:
            parts.append(f"index={self._index}")
        return f"Locator({', '.join(parts)})"
