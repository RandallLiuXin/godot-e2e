# godot-e2e Product Brief for Marketing

This document is a source brief for the Marketing content factory. It is not
finished campaign copy. Use it as the grounded product profile for posts,
launch notes, comparison pieces, text-card prompts, and claim tracing.

## Marketing Agent Fields

```yaml
product: godot-e2e
category: Godot end-to-end testing framework
one_liner: Out-of-process E2E testing for Godot 4.5+, driven from synchronous Python and pytest.
current_version: "1.3.0"
current_status: alpha package, public repository, PyPI publishing status needs human confirmation
license: Apache-2.0
primary_audience:
  - Godot game developers who want automated gameplay and UI regression tests
  - teams already using Python, pytest, or CI for release quality
  - agents or maintainers generating behavior tests from game design docs
core_pain:
  - Godot gameplay and UI regressions are hard to catch with unit tests alone.
  - in-engine or mocked tests can miss behavior that only appears in a real running game process.
  - timing, scene reloads, engine logs, screenshots, and CI display setup make game E2E tests brittle.
primary_value:
  - run the actual Godot project as a separate process and drive it from pytest
  - keep test code synchronous and Python-native
  - capture useful failure evidence such as screenshots and Godot engine logs
supported_runtime:
  godot: "4.5+ for the current package line"
  python: "3.9+"
  test_runner: "pytest 7.0+"
install_surface:
  - copy addons/godot_e2e/ into a Godot project and enable the GodotE2E plugin
  - install the Python package with pip install godot-e2e
  - run tests through the godot-e2e CLI or pytest
public_assets:
  repository: https://github.com/RandallLiuXin/godot-e2e
  documentation_site: https://randallliuxin.github.io/godot-e2e/
  pypi: https://pypi.org/project/godot-e2e/
  readme: README.md
  demo_gifs:
    - docs/gif/demo_01.gif
    - docs/gif/demo_02.gif
  ci_example:
    - README.md#ci-configuration
    - skills/godot-e2e/assets/github-workflow-e2e.yml
claim_trace_sources:
  - README.md
  - docs/index.md
  - docs/getting-started.md
  - docs/api-reference.md
  - docs/testing-patterns.md
  - docs/architecture.md
  - CHANGELOG.md
  - pyproject.toml
  - .github/workflows/ci.yml
  - skills/godot-e2e/SKILL.md
  - skills/godot-e2e/assets/github-workflow-e2e.yml
```

## Product Positioning

godot-e2e is an out-of-process end-to-end testing tool for Godot. It launches a
real Godot project, connects to a dormant automation addon over localhost TCP,
and lets Python/pytest tests drive and inspect the running game.

The most useful short positioning is:

> Out-of-process E2E testing for Godot 4.5+, driven from Python.

For value-first marketing, lead with the pain: a game can pass unit checks while
the real UI, scene transitions, input handling, or runtime engine logs are
broken. godot-e2e is the bridge between pytest and the actual running Godot
process.

## Target Users and Use Cases

### Godot Developers

Use godot-e2e to write regression tests that launch the real project, simulate
player input, inspect the scene tree, and verify gameplay or UI state.

Typical use cases:

- player movement, scoring, inventory, win/lose loops, and scene transitions
- menu and UI button flows
- checking that important nodes, properties, labels, and signals behave after
  real inputs
- capturing failure screenshots and engine logs for debugging

### Small Teams and CI Maintainers

Use godot-e2e to run smoke and regression flows on pull requests. The repository
includes Linux and Windows CI examples. Linux runs under `xvfb` because Godot
needs a display server for this workflow.

### LLM Agents and Test-Generation Workflows

The bundled `skills/godot-e2e` profile positions the tool as an onboarding and
document-driven test-generation framework. Its recommended workflow is:

1. read a design doc or feature list
2. extract a coverage checklist of player-facing behaviors
3. write one behavior-asserting E2E test per feature
4. run the suite and report real implementation gaps instead of weakening tests

This angle is suitable for agent-facing posts, but do not imply that the public
package automatically reads design docs by itself. The repository provides a
skill/workflow guide for agents, not a standalone codegen product.

## Core Problems It Solves

- Real-game verification: tests drive the actual Godot process instead of a
  mocked scene or editor-only harness.
- Process isolation: game crashes or hangs are isolated from the Python test
  runner, with timeouts and launcher control on the Python side.
- Python-native authoring: tests use synchronous Python calls, pytest fixtures,
  and normal pytest reporting.
- Reduced flake: Locator queries, `expect()` auto-retry assertions, frame waits,
  and scene reload patterns help tests wait for real runtime state.
- Better failure evidence: screenshot-on-failure and Godot engine-log capture
  put more context in pytest reports and CI artifacts.
- CI repeatability: examples show Linux with `xvfb` and Windows with
  `GODOT_PATH` set to a downloaded Godot binary.

## Main Features

- Out-of-process architecture: Python and Godot run as separate processes and
  communicate over length-prefixed JSON on localhost TCP.
- Dormant addon: the Godot addon does nothing unless the game is launched with
  `--e2e`.
- No engine modifications: works with standard Godot binaries.
- Synchronous Python API: no async/await requirement in user tests.
- pytest integration: `game` and `game_fresh` fixtures, CLI wrapper, and
  screenshot capture on failure.
- Input simulation: named actions, keyboard events, mouse button events, mouse
  motion, and node clicking.
- Node operations: existence checks, property get/set, method calls, group
  lookup, scene tree snapshots, and batch reads for instant commands.
- Frame and state synchronization: wait for process frames, physics frames,
  elapsed game time, node existence, signals, properties, scene changes, and
  scene reloads.
- Locator API: lazy semantic queries by path, name, group, text, script, or type,
  plus chaining, filtering, `.first()`, `.nth()`, and `.all()`.
- Auto-retry assertions: `expect(locator).to_have_text(...)`,
  `to_have_property(...)`, `to_be_visible()`, `to_exist()`, and custom
  predicates through `to_satisfy(...)`.
- Engine log capture: Godot-side errors, warnings, runtime errors, shader errors,
  and optional info logs can appear in pytest reports and exceptions.
- Engine-error-flood guard: version 1.3.0 can fast-fail sustained per-frame
  runtime-error floods instead of idling to a long timeout.
- Failure screenshots: screenshots are saved under `test_output/` for failed
  tests that use the standard fixtures.
- Examples: minimal, platformer, and UI testing examples are included.
- Documentation site: MkDocs Material site with English and Chinese docs is
  deployed to GitHub Pages.

## Key Workflow

### Install

1. Copy `addons/godot_e2e/` into the target Godot project's `addons/` directory.
2. Enable the `GodotE2E` plugin in Godot under Project Settings > Plugins.
3. Install the Python package:

```bash
pip install godot-e2e
```

For local development against this repository:

```bash
pip install -e .
```

### Configure the Godot Binary

godot-e2e resolves the Godot executable in this order:

1. `--godot-path` on the `godot-e2e` CLI, which writes and overrides
   `GODOT_PATH` for the pytest run
2. `GODOT_PATH`
3. common executable names on `PATH`, including `godot`, `godot4`, and
   `Godot_v4`

### Write a Test

```python
from godot_e2e import expect


def test_player_moves_right(game):
    player = game.locator(name="Player")
    initial_x = player.get_property("position:x")

    game.input_action("move_right", True)
    game.wait_physics_frames(10)
    game.input_action("move_right", False)

    expect(player).to_satisfy(
        lambda loc: loc.get_property("position:x") > initial_x,
        description="player moved right",
    )
```

### Run Tests

```bash
godot-e2e tests/e2e/ -v
```

The built-in `game` fixture launches the project with the `--e2e` flag, connects
to the automation server, reloads the scene between tests, and captures a
screenshot when a test fails.

### Review Results

Use normal pytest output first. When failures happen, useful evidence can include:

- assertion failure text
- `captured godot logs` in pytest output
- exception-attached logs on `GodotE2EError`
- scene-tree dumps on timeout and expectation failures
- `test_output/<test_name>_failure.png` screenshots
- CI artifacts uploaded from `test_output/`

### Run in CI

The repository README contains Linux, Windows, and macOS snippets. The bundled
workflow template at `skills/godot-e2e/assets/github-workflow-e2e.yml` includes
Linux and Windows jobs.

Important CI facts:

- Linux needs a virtual display such as `xvfb-run`.
- `GODOT_PATH` should point to the downloaded Godot executable.
- Upload `test_output/` as an artifact to inspect failure screenshots.
- Use generous test timeouts because first Godot launch can be slower in CI.

## Supported Versions

Current repository facts:

- package version: `1.3.0`
- current Godot target: `4.5+`
- Python: `3.9+`
- pytest: `7.0+`
- package status classifier: `Development Status :: 3 - Alpha`
- license: Apache-2.0

The changelog says version 1.2.0 raised the minimum Godot version to 4.5 because
engine log capture depends on the Godot 4.5 `Logger` API. Version 1.3.0 CI
downloads Godot 4.5 stable for Linux and Windows test jobs.

## Known Limits and Claims to Avoid

Do not overstate these points:

- Do not claim full visual testing, screenshot diffing, or video recording.
  Current screenshots are primarily failure/debug artifacts.
- Do not claim mobile, web, console, or exported-release platform coverage unless
  separately verified.
- Do not claim that it supports `--headless`. The bundled CI template explicitly
  says Linux should use `xvfb-run` and notes that headless is not supported for
  this workflow.
- Do not claim built-in AI test generation as a package feature. The repository
  includes an agent skill for document-driven test generation, but the public
  Python package is the E2E runtime and pytest integration.
- Do not claim Godot 3 support. The current package line targets Godot 4.5+.
- Do not claim every future roadmap item is shipped. The roadmap includes planned
  items such as per-step trace artifacts and hit-test occlusion detection.
- Do not publish live GitHub stars, download counts, install counts, user counts,
  or benchmark numbers without refreshing and tracing them at content-production
  time.
- Do not promise zero flakiness. The tool provides synchronization patterns and
  retries, but game E2E tests still require careful authoring.

## Promotable Material

These are suitable for direct marketing use after normal editorial polishing:

- "Out-of-process E2E testing for Godot 4.5+, driven from Python."
- The real-process angle: pytest drives a live Godot game process rather than a
  mocked scene.
- The safety angle: the automation server is dormant unless the game is launched
  with `--e2e`.
- The authoring angle: synchronous Python, pytest fixtures, Locator queries, and
  `expect()` auto-retry assertions.
- The debugging angle: screenshots on failure, engine-log capture, scene-tree
  dumps, and engine-error-flood fast-fail behavior.
- The CI angle: Linux and Windows examples with `GODOT_PATH`, `xvfb-run` on
  Linux, and `test_output/` artifacts.
- The demo angle: README GIFs show pytest launching and driving real Godot game
  processes.

## Needs Human Confirmation Before Publishing

These items should be checked manually before use in public posts:

- current PyPI version and release date
- current GitHub stars, forks, issues, release downloads, and package downloads
- whether the Godot Asset Library listing is live and what exact listing URL to
  cite
- whether the public docs URL is the preferred destination over the GitHub README
- whether "alpha" is the desired public label, despite the package classifier
- whether to mention the agent-oriented `skills/godot-e2e` workflow in general
  public content or reserve it for agent/developer channels

## Source Notes for Claim Trace

Use these source anchors when producing actual posts:

- `README.md`: positioning, quick start, compatibility table, features, workflow,
  CI snippets, examples, demo GIF paths, license.
- `docs/index.md`: website positioning, "Why godot-e2e", 30-second example,
  links, compatibility, Asset Library mention.
- `docs/getting-started.md`: install/setup/run workflow, CLI usage, project path
  resolution, CI setup, screenshot artifacts.
- `docs/api-reference.md`: public API, Locators, `expect`, log capture,
  exceptions, pytest fixtures.
- `docs/testing-patterns.md`: test-authoring recommendations and debugging
  patterns.
- `docs/architecture.md`: process boundary, TCP protocol, dormant addon,
  localhost binding, token authentication.
- `CHANGELOG.md` and `docs/update/v1.3.0.md`: version 1.3.0 features, Godot 4.5
  rationale, CI/docs changes.
- `.github/workflows/ci.yml`: actual repo validation matrix and Godot 4.5 stable
  CI usage.
- `skills/godot-e2e/SKILL.md`: agent-facing onboarding and document-driven test
  generation workflow.
- `skills/godot-e2e/assets/github-workflow-e2e.yml`: copyable user-project CI
  template and headless limitation note.
