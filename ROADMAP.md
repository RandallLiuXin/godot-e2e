**English** | [中文](ROADMAP.zh-CN.md)

# Roadmap

Planned work for godot-e2e, ordered by priority and dependency.
For released changes see [CHANGELOG.md](CHANGELOG.md).

The four tasks below share one goal: reduce the cognitive load on LLM agents
(and humans) authoring godot-e2e tests. Each addresses a distinct,
non-overlapping pain point.

---

## 1. Locator with multi-strategy queries

**Pain:** Tests require absolute paths like `/root/Menu/VBox/ClickButton`.
Authors must inspect the scene tree for every reference; scene refactors
break tests. This is the single biggest authoring tax.

**In scope**
- Lazy `Locator` class, re-resolved on every action.
- Query strategies: `path`, `name`, `group`, `text`, `script`, `type`,
  composable via `filter()`.
- Server-side query command supporting these strategies.
- Locator action methods with auto-wait on `Control`: `click`,
  `get_property`, `set_property`, `call`, `wait_visible`, `exists`.
- Multi-match: error by default; opt-in `.first()` / `.nth(i)` / `.all()`.

**Out of scope**
- Auto-wait on `Node2D` / `Node3D` (semantics unclear, deferred).
- Removing the existing path-based API — both coexist.
- Codegen / recorder.

**Acceptance:** the `ui_testing` example has a sibling test file using
Locator-only that is measurably shorter and contains no absolute paths.

---

## 2. Engine error / log capture

**Pain:** Game-side `push_error`, script runtime errors, and `print()`
output are invisible to the test process. Tests can pass while the game
silently logs a critical error, or fail without the agent seeing why.

**In scope**
- Capture `push_error` / `push_warning` / engine errors on the Godot side.
- Buffer recent log messages in `AutomationServer`.
- Attach a `_logs` array to command responses and to raised exceptions.
- pytest reporting: include captured logs in the failure section.
- Configurable verbosity (errors only / warnings / info).

**Out of scope**
- Replacing Godot's logger or capturing at C++ level.
- Persistent log file emission (use Godot's existing logging for that).

**Acceptance:** a test that triggers `push_error("X")` shows "X" in
pytest's failure output without test-code changes beyond using the `game`
fixture.

---

## 3. `expect()` with auto-retry assertions

**Pain:** `assert game.get_property(...) == expected` runs once and fails
on timing. Authors must remember to use `wait_for_property`, which only
supports equality. Flaky tests proliferate.

**In scope**
- `expect(locator)` returning a chainable assertion object.
- Matchers: `to_have_property`, `to_have_text`, `to_be_visible`,
  `to_exist`, plus predicate `to_satisfy(lambda v: ...)`.
- Client-side polling with configurable timeout / interval.
- Failure messages include the last observed value and a tree dump.

**Out of scope**
- Soft assertions / failure aggregation (pytest plugins cover this).
- Snapshot testing.

**Depends on:** task 1 (Locator).

**Acceptance:** a test using `expect(locator).to_have_text(...)` is stable
across 100 consecutive CI runs without explicit frame waits.

---

## 4. Step API + lightweight trace

**Pain:** When a test fails, the agent has one screenshot and a stack
trace. Diagnosing a mid-test failure requires re-running with prints.

**In scope**
- `with game.step("name"):` context manager.
- Per-step capture: screenshot, scene tree snapshot, command log slice.
- On failure, artifacts written to
  `test_output/<test_name>/<step_index>_<name>/`.
- pytest hook surfaces the artifact directory in the failure report.

**Out of scope**
- Interactive trace viewer.
- Video recording.
- Trace zip / sharing format.

**Depends on:** task 2 (engine log capture) — captured logs are part of
the per-step trace.

**Acceptance:** a failing test produces per-step artifacts that an agent
can read to identify the failing step without re-running the test.

---

## 5. Hit-test actionability / occlusion detection

**Pain:** Task 1's actionability check only verifies the target node's own
state (`is_visible_in_tree`, `mouse_filter`, viewport rect). It cannot tell
whether a click would actually reach the target — modal popups, overlapping
sibling Controls, and ancestors with `mouse_filter = STOP` can all silently
swallow the event. Tests pass while the click went somewhere else.

**Approach (firm constraint):** delegate to Godot's own GUI dispatcher
rather than reimplementing hit-test in GDScript. The engine's rules
(`CanvasLayer`, `top_level`, `clip_contents`, `mouse_filter` cascade,
transparent regions, nested viewports) evolve across versions; any
GDScript reimplementation is guaranteed to drift.

**In scope**
- A position-based hit query that delegates to engine state (likely:
  inject `InputEventMouseMotion` at the target position and read the
  resulting hovered Control via `Viewport.gui_get_hovered_control()` or
  whatever public position-query API the then-current Godot exposes).
- An `occluded_by` field in actionability errors naming what blocked the
  click.
- `force=True` opt-out on Locator actions to skip the check.
- Documented side effects: injected motion fires `mouse_entered` /
  `_gui_input` on whatever it crosses. Document, do not hide.

**Out of scope**
- Manual GDScript hit-test traversal (rejected — see Approach).
- Hit-testing for `Node2D` / `Node3D` (different problem; user-space
  `Area2D` / `Area3D` are the right tool for those).

**Depends on:** task 1 (Locator). Should not start until task 1 has
shipped and real authoring sessions have surfaced the actual occlusion
patterns we need to handle — premature hardening here would lock in
guesses.

**Acceptance:** a test that clicks a Locator covered by a modal popup
fails with a message naming the occluder, instead of silently passing
because the click reached the modal.

---

## Considered and rejected

- **Test event bus / signal-emit-from-test.** Bypasses input simulation,
  undermining the end-to-end guarantee. A behaviour testable only via
  signal emission can pass while the user-facing trigger is broken — a
  false-confidence risk. White-box triggering remains available via
  `call_method` for tests that explicitly opt out of e2e semantics.
- **Codegen / recorder.** Godot scene semantics (transforms, anchors,
  viewport nesting) are too rich for a useful recorder without it
  becoming a project of its own. Rich tree introspection serves agents
  better.
- **Inspector pause UI.** Godot's editor already serves this role.
- **Video recording.** Per-step screenshots cover ~90% of the diagnostic
  value at a fraction of the cost.
