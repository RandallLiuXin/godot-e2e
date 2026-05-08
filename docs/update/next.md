# Next Release

> **Contributors:** Every pull request MUST include an entry in this file describing the change.
> When a new version is released, this file will be archived as `vX.Y.Z.md` and a fresh copy will take its place.

## How to add an entry

Append your change under the appropriate category below. Use this format:

```
- Brief description of the change (#PR_NUMBER) — @author
```

If no category fits, add a new one following [Keep a Changelog](https://keepachangelog.com/) conventions.

---

## Added

- `Locator` — lazy, multi-strategy reference for finding nodes by name / group / text / type / script / path, AND-composable via `filter()` and chainable via `parent.locator(...)`. Re-resolves on every action so `reload_scene()` leaves existing Locators valid. Auto-waits actionability before `click()` on Control targets. New errors `MultipleMatchesError` and `NotActionableError`. New wire commands `find_nodes`, `node_actionable`, `hover_node`. ROADMAP task 1. — @LiuXin

- Engine log capture — `push_error`, `push_warning`, script runtime errors, shader errors, and (at info verbosity) `print` / `printerr` are intercepted via a `Logger` subclass on the Godot side and surfaced on the Python side. `LogEntry` / `LogVerbosity` types, `game.last_logs` / `game.collected_logs` accessors, `game.set_log_verbosity(level)` and `game.set_log_buffer_size(size)` runtime controls, `--e2e-log-verbosity={error|warning|info}` startup flag (default `warning`), `log_verbosity` launch kwarg with Python-side validation. On test failure, captured logs land in pytest's report under a `captured godot logs` section. Every `GodotE2EError` subclass now carries a `logs` attribute; ring-buffer overflow is reported as a uniform synthetic entry across `last_logs` / `collected_logs` / `exc.logs`. New wire commands `set_log_verbosity`, `set_log_buffer_size`. ROADMAP task 2. — @LiuXin

- Repo-meta baseline: `ROADMAP.md` (+ zh-CN, with five tasks), `docs/versioning.md` (+ zh-CN), `.gitleaks.toml` config, `docs/update/next.template.md`. `docs/internal/` is now gitignored as a local-only space for ADRs, design notes, and lessons that we do not publish. — @LiuXin

## Changed

## Compatibility

- **Minimum Godot version raised to 4.5** — the engine log capture feature relies on the `Logger` virtual class introduced in Godot 4.5 ([class reference](https://docs.godotengine.org/en/4.5/classes/class_logger.html), [PR #91006](https://github.com/godotengine/godot/pull/91006)). Per `docs/versioning.md` this is a MINOR bump. — @LiuXin

## Fixed

## Removed
