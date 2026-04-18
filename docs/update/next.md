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

- Dynamic port allocation via `--e2e-port=0` and `--e2e-port-file=<path>` for multi-instance parallel testing (#5)
- `godot-e2e` CLI command as a thin wrapper over pytest with `--godot-path` support (#5)

## Changed

- Installation: enable the GodotE2E plugin in Project Settings instead of manually adding an autoload (#5)
- All user-facing docs updated from `pytest` to `godot-e2e` CLI (#5)
- CI workflow: example tests use `godot-e2e`, unit tests keep `python -m pytest` (#5)
- PR template: added `docs/update/next.md` checklist item (#5)

## Fixed

- Fix plugin.cfg: added proper `plugin.gd` (extends EditorPlugin) instead of pointing to `automation_server.gd` (extends Node), which caused `Unable to load addon script, base type is not EditorPlugin` (#5)

## Removed
