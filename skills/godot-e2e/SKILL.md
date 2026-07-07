---
name: godot-e2e
description: >-
  Onboard a Godot project to the godot-e2e end-to-end testing framework and
  generate a real, behavior-asserting test suite from the project's design
  doc — to raise game stability and catch unimplemented or regressed
  features. Use this skill whenever the user wants to: add E2E / end-to-end /
  integration / gameplay tests to a Godot project; "set up godot-e2e",
  "test the running game", "make my Godot game more stable", "test that the
  features in my GDD actually work", or "check my design doc is fully
  implemented"; generate tests from a design document, GDD, feature list, or
  requirements spec; wire godot-e2e into CI/CD (GitHub Actions). The library
  has zero LLM training data, so DO use this skill rather than guessing the
  API — it carries the full reference. Covers first-time setup, document-driven
  test generation, and CI templates.
---

# godot-e2e — Onboarding & Document-Driven Test Generation

$ARGUMENTS

`godot-e2e` runs your **actual game** and drives it over TCP from Python:
Locator-based semantic node queries, `expect()` auto-retry assertions, and
engine-log capture so failures are self-diagnosing. It has **zero LLM
training coverage** — never guess the API. Everything you need is in this
skill and `references/`.

This skill has three workflows. Pick what the user needs — they're usually
done in order on a fresh project, but each stands alone:

- **A. Quick Setup** — get the addon installed and the first test green.
- **B. Document-Driven Test Generation** — the core value. Turn the project's
  design doc into a coverage checklist, then one behavior-asserting test per
  feature, surfacing features the doc promises but the game doesn't deliver.
- **C. CI/CD Wiring** — run the suite on every push.

Before writing any test code, skim `references/api-reference.md` so the API
calls are correct. Reach for `references/testing-patterns.md` for recipes
(physics, UI, scene transitions, flaky-test mitigation, keep-alive).

---

## A. Quick Setup

Goal: addon installed, autoload registered, the project path configured, one
real test passing. Stop guessing paths — confirm each step against the project.

1. **Confirm prerequisites.** Python 3.9+, `pip install godot-e2e`, and a
   Godot 4.x binary. Find the binary path; the suite locates it via the
   `GODOT_PATH` env var or `--godot-path`.

2. **Copy the addon** into the user's Godot project:
   `<godot-e2e>/addons/godot_e2e/` → `your_game/addons/godot_e2e/`. The addon
   ships in the godot-e2e repo (the Python package alone does not contain it).
   It is **dormant** unless Godot is launched with `--e2e` — zero overhead in
   production.

3. **Register the autoload.** Project Settings → Autoload → add
   `res://addons/godot_e2e/automation_server.gd` named `AutomationServer`
   (use the script, i.e. the `*` prefix — not a scene).

4. **Find the entry-scene root node.** Read `project.godot`'s
   `run/main_scene`; open that `.tscn` and note its **root node name** (often
   `Main`). Every fixture waits on `/root/<RootNodeName>`.

5. **Point the suite at the project — no conftest needed.** The pytest plugin
   ships the `game` and `game_fresh` fixtures out of the box; `game` already
   reloads the scene between tests **and** captures a failure screenshot to
   `test_output/`. Just tell it where `project.godot` lives, easiest first:
   - the `GODOT_E2E_PROJECT_PATH` env var;
   - or `@pytest.mark.godot_project("path/to/project")` on a test/module;
   - or nothing, if `project.godot` is auto-detectable (`./godot_project`, `../godot_project`, or `.`).

   Only write a `conftest.py` when you need something the built-ins don't give
   you (e.g. a "skip the menu" fixture). If you do, **layer on top of the
   built-in `game`** — do NOT redefine `game`/`game_fresh` yourself, or you
   silently lose the screenshot-on-failure teardown. `assets/conftest.py` shows
   the additive pattern.

6. **Write one real test** (not a smoke test — apply the Quality Standards
   below) and run it:
   ```bash
   godot-e2e tests/e2e/ -v
   ```
   If it can't find Godot, set `GODOT_PATH` or pass `--godot-path`. If it
   times out, read the `captured godot logs` section and bump `launch(...,
   timeout=15.0)`.

---

## B. Document-Driven Test Generation (core)

This is what makes godot-e2e raise stability instead of producing vacuous
tests. The discipline: **the design doc is the source of truth; the test
suite must cover every player-facing feature it promises, and each test must
prove the behavior actually happens at runtime.** A feature the doc promises
but the game doesn't deliver is a *gap* — the most valuable thing this
workflow finds.

Adapted from GodotMaker's `gm-evaluate` quality gate, generalized to any
design doc / GDD / feature list / requirements spec.

### Step 1 — Build the coverage checklist

Read whatever document the user points at (a GDD, a feature list, a
requirements doc, release notes, or a Notion/markdown spec). If there's no
doc, help the user write a short flat feature list first — without it there's
nothing to verify against.

Extract a **flat checklist of player-facing features**. For each feature
capture: a stable ID (`F1`, `F2`, …), the **observable behavior** in one line
(what the *player* sees or does, not internal architecture), the scene(s)
involved, and the expected effect. Then extract **flows** — playable loops
that must be reachable through play: start → play → win / lose / exit.

Write this to a `coverage-checklist.md` (template in `assets/`). It's the
contract between doc and suite — keep it in the repo and reconcile it whenever
the doc changes.

Pull observable behavior, not implementation. "Player takes damage and the
health bar shrinks" is testable; "DamageSystem decrements the HealthComponent"
is not — it names internals the player never sees.

### Step 2 — One test file per feature

For each checklist row, write one test file named after the feature, e.g.
`test_player_moves_right.py`, `test_coin_increases_score.py`. Keeping the
feature in the filename makes the test→feature mapping mechanical and stable.

Each test must assert the **observable behavior** named in the row — not
internal state. Drive the game the way a player would (input, clicks), then
assert the visible effect with `expect()`.

For each flow, write a flow test (`test_flow_win.py`, …) that reaches the
named completion/fail/exit state **through play** — drive the loop to the end,
don't just set a flag. Static "the win function exists" evidence doesn't
count.

Use Locators + `expect()` over hardcoded paths so tests survive scene
refactors. See `references/testing-patterns.md` for per-category recipes.

### Step 3 — Enforce the quality red-lines

Apply the Quality Standards below to every test as you write it. A test that
only checks existence, or asserts nothing changed, proves nothing about
gameplay and must be rewritten.

### Step 4 — Run and reconcile

```bash
godot-e2e tests/e2e/ -v
```

Triage every result — the distinction is the whole point of this workflow:

- **Test bug** (wrong node path, missing `wait_physics_frames`, too-tight
  timeout) → fix the test. Read the `captured godot logs` and any
  `scene_tree` on the failure first.
- **Gap / regression** — the input is correct and the observable behavior
  genuinely doesn't happen → this is a **finding about the game**, not the
  test. The doc promises a feature the implementation is missing or has
  broken. Record it; do not paper over it by weakening the assertion. This is
  the payoff: the doc said it works, the runtime says it doesn't.

Do **not** silently fix game bugs from inside this workflow — surface them so
the user decides.

### Step 5 — Prune orphans and report

- **Orphan tests** — any test file with no matching feature in the current
  doc. Either delete it, or (if the feature should still exist) add it back to
  the doc. The suite must map 1:1 to the current doc.
- Update `coverage-checklist.md` with each row's status: `pass` / `fail` /
  `gap` / `orphan`. Hand the user a short summary: features covered, gaps
  found (with the doc line each one came from), and orphans pruned.

When done, the suite contains exactly one test per current feature plus flow
tests for every playable loop — and the checklist proves the doc is (or
isn't) fully implemented.

---

## C. CI/CD Wiring

Run the suite on every push so regressions surface immediately.

1. Copy `assets/github-workflow-e2e.yml` to `.github/workflows/e2e.yml`.
2. Set `GODOT_VERSION` to the project's Godot version and `TEST_PATH` to the
   test directory.
3. Commit. The workflow downloads Godot, installs `godot-e2e`, and runs the
   suite on Linux (under `xvfb`) and Windows.

Critical facts the template already handles, but worth knowing:

- **godot-e2e does NOT support `--headless`** (Godot bug #73557). Linux needs
  a virtual display — the template uses `xvfb-run`. Windows/macOS have a
  desktop session by default.
- The Godot binary is found via `GODOT_PATH` (the template sets it after
  download).
- `test_output/` (failure screenshots) is uploaded as a build artifact.
- Use a generous `--timeout` (first launch is slow in CI) and
  `launch(..., timeout=15.0)`.

For macOS or GitLab CI variants, see the CI section in
`references/testing-patterns.md`.

---

## E2E Test Quality Standards

Every test must meet these, whichever workflow produced it. Tests that fail
them are rejected — they pass CI while proving nothing, which is worse than no
test because it manufactures false confidence.

1. **At least one user action** — `input_action`, `press_action`, `click`,
   `Locator.click()`, or a gameplay-triggering `call`.
2. **At least one state-change assertion** — verify a property *changed* or a
   visible effect *happened*. Prefer `expect(...)` matchers over manual
   `assert get_property(...) == X`.
3. **No pure existence tests** — `node_exists` / `Locator.exists()` may be a
   *precondition*, never the only assertion.
4. **Assert direction for continuous physics quantities** — position,
   velocity, and other float physics values differ per machine, so assert a
   direction/range (`assert new_x > initial_x`), not `== 450.0`. This does
   **not** apply to discrete deterministic values: a score, lives count, or a
   UI label string *should* be asserted exactly (`to_have_property("score", 3)`,
   `to_have_text("Paused")`) — a direction check there would let real bugs
   through.
5. **Drive end states through play** — reach win/lose/exit by playing the
   loop, not by setting the flag that the UI reads.

```python
# BAD — only checks existence; proves nothing about gameplay:
def test_player(game):
    assert game.locator(group="player").exists()

# GOOD — drives input, asserts the observable result with auto-retry:
from godot_e2e import expect

def test_player_moves_right(game):
    player = game.locator(group="player")
    initial_x = player.get_property("position:x")
    game.input_action("move_right", True)
    game.wait_physics_frames(10)  # _process(delta) mover? use wait_process_frames
    game.input_action("move_right", False)
    expect(player).to_satisfy(
        lambda l: l.get_property("position:x") > initial_x,
        description="player moved right",
    )
```

---

## When Things Break

- Read the `captured godot logs` section on every failure first — every
  `GodotE2EError` carries `.logs` of what Godot printed during the failing
  command. Ignoring it doubles diagnosis time.
- `TimeoutError.scene_tree` and `ExpectationFailedError.scene_tree` /
  `.actual` / `.last_error` tell you what the tree actually looked like.
- `NotActionableError.reasons` lists why a click failed
  (`not_visible_in_tree`, `mouse_filter_ignore`, `outside_viewport`,
  `unclickable_node_type`).
- After any structural change to the game, run `godot-e2e tests/e2e/ -v` to
  catch broken fixtures immediately.

## References

- `references/api-reference.md` — full API: Locator, expect(), raw-path ops,
  input, waits, scenes, log capture, types, exceptions, critical rules.
- `references/testing-patterns.md` — recipes by category, flaky-test
  mitigation, keep-alive/pause survival, batch ops, CI variants, gotchas.
- `assets/conftest.py` — optional advanced template: project-path config plus
  an additive "skip the menu" fixture that layers on the built-in `game`
  (keeping its screenshot-on-failure teardown). Not needed for basic setup.
- `assets/github-workflow-e2e.yml` — GitHub Actions CI template.
- `assets/coverage-checklist.md` — doc→suite coverage contract template.
