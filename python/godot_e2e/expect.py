"""Auto-retrying assertions for godot-e2e.

``expect(locator)`` returns a chainable assertion object whose matchers
poll the live game until they pass or a timeout elapses. Failures raise
:class:`ExpectationFailedError` (which subclasses both
:class:`GodotE2EError` and :class:`AssertionError`, so pytest renders it
as a regular assertion failure while tooling can still catch it as a
framework error).

Typical usage::

    expect(game.locator(text="Score: 10")).to_be_visible()
    expect(game.locator(name="Counter")).to_have_property("value", 5)
    expect(game.locator(group="enemies")).to_satisfy(
        lambda loc: loc.count() == 0,
        description="all enemies cleared",
    )

All polling happens client-side. Matchers wrap existing Locator methods
(``get_property``, ``is_visible``, ``exists``) — there are no new wire
commands. Lookup-style errors (``NodeNotFoundError``,
``MultipleMatchesError``, ``CommandError``) raised mid-poll are treated
as "not yet satisfied" and the loop keeps trying; this lets matchers
ride out transient states like scene reloads.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from .locator import Locator
from .types import (
    CommandError,
    ExpectationFailedError,
    MultipleMatchesError,
    NodeNotFoundError,
)


_DEFAULT_TIMEOUT = 5.0
_DEFAULT_POLL_INTERVAL = 0.05

# Sentinel for "no value observed yet" — distinguishable from a legitimate
# None observation (e.g. get_property on a property that's None).
_UNSET = object()


def expect(
    locator: Locator,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
) -> "LocatorAssertions":
    """Build a polling assertion handle for *locator*.

    Args:
        locator: The :class:`Locator` to make assertions against. The
            same Locator instance is re-resolved on every poll, so
            assertions ride scene changes the same way Locator actions
            do.
        timeout: Maximum seconds to keep retrying before raising
            :class:`ExpectationFailedError`. Default ``5.0``.
        poll_interval: Seconds to sleep between polls. Default ``0.05``
            (50 ms) — same cadence as Locator's auto-wait.

    Returns:
        A :class:`LocatorAssertions` handle on which to call a matcher.
    """
    if not isinstance(locator, Locator):
        raise TypeError(
            f"expect() takes a Locator; got {type(locator).__name__}. "
            f"Build one with game.locator(...) or game.get_by_text(...)."
        )
    if timeout < 0:
        raise ValueError(f"timeout must be >= 0; got {timeout}")
    if poll_interval <= 0:
        raise ValueError(f"poll_interval must be > 0; got {poll_interval}")
    return LocatorAssertions(locator, timeout=timeout, poll_interval=poll_interval)


class LocatorAssertions:
    """Polling assertion API. Build via :func:`expect`."""

    def __init__(
        self,
        locator: Locator,
        *,
        timeout: float,
        poll_interval: float,
    ):
        self._locator = locator
        self._timeout = timeout
        self._poll_interval = poll_interval

    # ------------------------------------------------------------------
    # Matchers
    # ------------------------------------------------------------------

    def to_have_property(self, name: str, value: Any) -> None:
        """Pass when ``locator.get_property(name) == value``.

        Polls until equality holds or the timeout elapses.
        """
        def check():
            return self._locator.get_property(name)

        self._poll(
            check=check,
            satisfied=lambda observed: observed == value,
            matcher=f"to_have_property({name!r}, {value!r})",
        )

    def to_have_text(self, text: str) -> None:
        """Pass when the target's ``text`` property equals *text*.

        Sugar for ``to_have_property("text", text)``. All Control nodes
        with user-facing text (``Label``, ``Button``, ``LineEdit``,
        ``RichTextLabel``, ...) expose the property under the same name.
        """
        def check():
            return self._locator.get_property("text")

        self._poll(
            check=check,
            satisfied=lambda observed: observed == text,
            matcher=f"to_have_text({text!r})",
        )

    def to_be_visible(self) -> None:
        """Pass when the target is visible in the scene tree.

        Uses the same visibility check as Locator's auto-wait. Reliable
        for ``Control`` (``is_visible_in_tree``) and ``Node2D``
        (``is_visible_in_tree``). For ``Node3D``, ``Window``, and plain
        ``Node`` the underlying actionability check refuses with
        ``unclickable_node_type`` and visibility cannot be determined
        through this matcher — use
        ``to_satisfy(lambda l: l.get_property("visible"))`` instead.
        """
        def check():
            return self._locator.is_visible()

        self._poll(
            check=check,
            satisfied=lambda observed: bool(observed),
            matcher="to_be_visible()",
        )

    def to_exist(self) -> None:
        """Pass when the locator's query resolves to one or more nodes.

        Doesn't require a single match — useful for "wait until at least
        one enemy spawns." Use ``to_satisfy(lambda l: l.count() == 1)``
        when you specifically need a single match.
        """
        def check():
            return self._locator.exists()

        self._poll(
            check=check,
            satisfied=lambda observed: bool(observed),
            matcher="to_exist()",
        )

    def to_satisfy(
        self,
        predicate: Callable[[Locator], Any],
        *,
        description: Optional[str] = None,
    ) -> None:
        """Pass when ``predicate(locator)`` returns truthy.

        The predicate receives the :class:`Locator` itself so it can
        compose any combination of property reads, visibility checks,
        and ``count()`` queries::

            expect(game.locator(group="enemies")).to_satisfy(
                lambda loc: loc.count() == 0,
                description="all enemies cleared",
            )

        Lookup errors raised inside the predicate
        (``NodeNotFoundError``, ``MultipleMatchesError``,
        ``CommandError``) are caught and treated as "not yet satisfied",
        so the predicate may freely call methods that require a node to
        exist without guarding them.

        Args:
            predicate: Callable taking the Locator, returning any value.
                Truthy means satisfied. Last-returned value is captured
                in the failure message and ``ExpectationFailedError.actual``.
            description: Optional human-readable label for the
                predicate. Without it, the matcher reports
                ``predicate <function ...>`` which is rarely useful.
        """
        if description is not None:
            label = f"to_satisfy({description!r})"
        else:
            label = f"to_satisfy({predicate!r})"

        def check():
            return predicate(self._locator)

        self._poll(
            check=check,
            satisfied=lambda observed: bool(observed),
            matcher=label,
        )

    # ------------------------------------------------------------------
    # Internal polling loop
    # ------------------------------------------------------------------

    def _poll(
        self,
        *,
        check: Callable[[], Any],
        satisfied: Callable[[Any], bool],
        matcher: str,
    ) -> None:
        """Run *check* until *satisfied* returns truthy or timeout fires.

        ``check`` returns the observation; ``satisfied`` decides whether
        that observation passes. Splitting the two means the failure
        message can report the actual last observation, not just "the
        predicate returned False".

        Lookup errors during ``check`` are absorbed (the loop keeps
        polling). ``CommandError`` is treated as retriable too — it can
        be a transient mid-scene-change hiccup *or* a permanent
        contract violation (e.g. property doesn't exist on the resolved
        node), and the wire protocol doesn't currently distinguish.
        We stash the most recent ``CommandError`` so the timeout
        failure can surface it instead of a generic "no observation"
        message. Other exceptions propagate — they're real bugs the
        caller should see, not transient states.
        """
        deadline = time.monotonic() + self._timeout
        observed: Any = _UNSET
        last_command_error: Optional[CommandError] = None
        # Run at least one iteration even when timeout=0, so the
        # zero-timeout case still delivers a real check (and a real
        # error) instead of a synthetic "deadline already passed".
        first = True
        while first or time.monotonic() < deadline:
            first = False
            try:
                observed = check()
                if satisfied(observed):
                    return
            except (NodeNotFoundError, MultipleMatchesError):
                # "Still looking" — the node hasn't resolved yet, or
                # multiple match without disambiguation. Normal during
                # polling.
                pass
            except CommandError as e:
                # See docstring: keep retrying, but stash to disambiguate
                # the eventual failure if we time out.
                last_command_error = e
            if time.monotonic() >= deadline:
                break
            time.sleep(self._poll_interval)
        self._fail(
            matcher=matcher,
            observed=observed,
            last_command_error=last_command_error,
        )

    def _fail(
        self,
        *,
        matcher: str,
        observed: Any,
        last_command_error: Optional[CommandError],
    ) -> None:
        if observed is _UNSET:
            # No poll produced a value. Could be: (a) locator never
            # resolved, (b) stable multi-match without disambiguation,
            # (c) every read raised CommandError. last_command_error
            # disambiguates case (c); the locator repr + scene_tree
            # dump cover (a)/(b).
            actual_repr = "<no successful observation captured>"
            actual_for_attr = None
            observation_captured = False
        else:
            actual_repr = repr(observed)
            actual_for_attr = observed
            observation_captured = True
        # Best-effort tree dump for diagnostics. If the dump itself
        # errors (server gone, etc.), fall through with None — the
        # matcher message and locator repr already carry the bulk of
        # the diagnostic value.
        scene_tree = None
        try:
            scene_tree = self._locator._client.send_command(
                "get_tree", path="/root", depth=4
            ).get("tree")
        except Exception:
            pass
        message = (
            f"expect({self._locator!r}).{matcher} did not hold within "
            f"{self._timeout}s; last observed: {actual_repr}"
        )
        if last_command_error is not None:
            message += f"; last server error: {last_command_error}"
        raise ExpectationFailedError(
            message,
            actual=actual_for_attr,
            observation_captured=observation_captured,
            matcher=matcher,
            scene_tree=scene_tree,
            timeout=self._timeout,
            last_error=last_command_error,
        )
