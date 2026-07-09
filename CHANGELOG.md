# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - 2026-07-09

### Added
- Engine-error-flood guard — a sustained runtime-error flood in `_process` / `_physics_process` (a non-fatal `SCRIPT ERROR` re-fired every frame under headless, vsync-off Godot) is now detected on the piggybacked engine-log stream via a sliding window; on trip, Godot is force-killed and the next command raises the new `EngineErrorFloodError` (carrying the error/dropped counts, window, and sample error lines), so unattended E2E runs fast-fail instead of spinning to their full timeout. On by default (window `2.0s`, threshold `100` combined error + dropped-log entries); tunable via the `flood_detection` / `flood_window_seconds` / `flood_error_threshold` launch kwargs and adjustable at runtime with `game.set_flood_detection(enabled=…, window_seconds=…, error_threshold=…)`. A flood driven purely by dropped log lines (a warning/`print` storm with no captured error) is reported as a "log flood" rather than an "error flood" so triage isn't sent after a runtime error that doesn't exist. Also bounds the per-test `collected_logs` accumulator (new `collected_logs_dropped` counter) so a flood can't grow it without bound (#20)
- GitHub Pages documentation site built with MkDocs Material — bilingual (en + zh-CN) via `mkdocs-static-i18n`, full-text search across both languages, language switcher in the header, dedicated landing page distinct from the README. Auto-deploys to `https://randallliuxin.github.io/godot-e2e/` on every push to `main` that touches `docs/`, `mkdocs.yml`, or `requirements-docs.txt` (#16)

### Changed
- CI overhaul (`.github/workflows/ci.yml`): the lint job now installs `ruff` (new `lint` extra) and runs a real `ruff check` plus `compileall` over the whole package, replacing the previous no-op (`ruff … || true`) and stale hand-maintained `py_compile` file list. Added a `build-check` job (`python -m build` + `twine check`) and a `secret-scan` job (gitleaks, wired to `.gitleaks.toml`) so packaging and secret regressions are caught on PRs; added run-level `concurrency` cancellation
- Docs workflow now builds with `mkdocs build --strict` on pull requests that touch docs (validation only — deploy still runs solely from `main` / manual dispatch)
- Documented the CI checks and how to reproduce each one locally in `CONTRIBUTING.md`
- Added a minimal `[tool.ruff]` configuration (rules `E`, `F`) to `pyproject.toml`

### Fixed
- `docs/update/release-checklist.md` step 7 — corrected the Asset Library field name (`Download Commit/URL`, not `Commit/Tag`) and clarified that it requires a full commit hash; tag names are rejected by the form (#15)

### Removed
- Dropped two unused imports (`NodeNotFoundError`, `time`) in `commands.py` flagged by `ruff`

## [1.2.0] - 2026-05-08

### Added
- `Locator` — lazy, multi-strategy node references (path / name / group / text / type / script, AND-composable via `filter()`); auto-waits actionability before `click()` on Control targets; new errors `MultipleMatchesError` / `NotActionableError`; new wire commands `find_nodes`, `node_actionable`, `hover_node` (#10)
- Engine log capture — Godot-side `Logger` subclass intercepts `push_error` / `push_warning` / runtime errors / shader errors (and `print` / `printerr` at info verbosity); Python-side `LogEntry` / `LogVerbosity`, `game.last_logs` / `collected_logs`, `set_log_verbosity` / `set_log_buffer_size` runtime controls, `--e2e-log-verbosity` startup flag, `log_verbosity` launch kwarg; failures include a "captured godot logs" pytest section; every `GodotE2EError` now carries a `logs` attribute (#11)
- `expect(locator)` auto-retry assertions — matchers `to_have_property`, `to_have_text`, `to_be_visible`, `to_exist`, plus `to_satisfy(predicate, *, description=...)`; client-side polling with configurable timeout / interval; `ExpectationFailedError` dual-inherits `GodotE2EError` and `AssertionError`, carries `actual` / `observation_captured` / `matcher` / `scene_tree` / `last_error` (#12)
- PEP 561 typed-distribution marker — `python/godot_e2e/py.typed` ships in wheel and sdist so downstream `mypy` / `pyright` / `pyre` consume the inline annotations on `GodotE2E`, `Locator`, `expect`, `LocatorAssertions`, and the typed exception classes instead of falling back to `Any` (#13)
- Repo-meta baseline: `ROADMAP.md` (+ zh-CN), `docs/versioning.md` (+ zh-CN), `.gitleaks.toml` config, `docs/update/next.template.md`; `docs/internal/` and `docs/review/` gitignored as local-only spaces for ADRs / design notes / reviewer artifacts (#8)

### Changed
- **Minimum Godot version raised to 4.5** — required by the new log-capture `Logger` API (introduced in Godot 4.5). Per `docs/versioning.md` this is a MINOR bump (#11)

## [1.1.0] - 2026-04-18

### Added
- `.gitattributes` with `export-ignore` rules so Asset Library downloads only include the `addons/` folder (#6)

### Fixed
- Fix plugin.cfg registration error: `automation_server.gd` was declared as EditorPlugin but extends Node. Added proper `plugin.gd` that auto-registers the AutomationServer autoload (#5)

### Added
- Dynamic port allocation: `--e2e-port=0` with `--e2e-port-file=<path>` lets Godot pick a random free port and write it to a file, enabling multiple E2E instances in parallel (#5)
- `godot-e2e` CLI command: thin wrapper over pytest with `--godot-path` support. `pip install godot-e2e` now provides the `godot-e2e` command (#5)

### Changed
- Installation: users now enable the GodotE2E plugin in Project Settings instead of manually adding an autoload (#5)
- Documentation: all user-facing examples updated from `pytest` to `godot-e2e` CLI (#5)
- CI workflow: example tests use `godot-e2e`, unit tests keep `python -m pytest` (#5)

## [1.0.0] - 2026-04-16

### Added
- GDScript automation server addon with TCP communication
- Non-blocking state machine (LISTENING, IDLE, WAITING, DISCONNECTED)
- Length-prefix framing protocol with JSON payloads
- Token-based authentication handshake
- Node operations: get/set property, call method, find_by_group, batch, get_tree
- Input simulation: keyboard, mouse, actions, click_node
- Frame synchronization: wait_process_frames, wait_physics_frames, wait_seconds
- Scene management: get_scene, change_scene, reload_scene (deferred)
- Screenshot capture with auto-save and absolute path return
- JSON serialization with _t type tags (Vector2, Vector3, Color, Rect2, etc.)
- Python client library with synchronous blocking API
- Process launcher with auto port allocation and token generation
- High-level helpers: press_key, press_action, click, wait_for_node
- pytest fixtures: game (reload strategy), game_fresh (fresh process)
- Screenshot on test failure (pytest plugin)
- Error handling: NodeNotFoundError, TimeoutError (with tree dump), ConnectionLostError
- Comprehensive test suite (42 tests)
- Platformer example with 5 E2E tests
- Documentation: getting started, API reference, architecture, testing patterns
- GitHub Actions CI for Linux and Windows

[Unreleased]: https://github.com/RandallLiuXin/godot-e2e/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/RandallLiuXin/godot-e2e/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/RandallLiuXin/godot-e2e/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/RandallLiuXin/godot-e2e/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/RandallLiuXin/godot-e2e/releases/tag/v1.0.0
