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

- Repo-meta baseline: `ROADMAP.md` (+ zh-CN, with five tasks), `docs/versioning.md` (+ zh-CN), `.gitleaks.toml` config, `docs/update/next.template.md`. `docs/internal/` is now gitignored as a local-only space for ADRs, design notes, and lessons that we do not publish. — @LiuXin

## Changed

## Fixed

## Removed
