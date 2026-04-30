**English** | [中文](versioning.zh-CN.md)

# Versioning Policy

godot-e2e follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

This document defines what counts as a breaking change for this project specifically. godot-e2e ships across three surfaces — a Python package, a Godot addon, and the wire protocol between them — and "breaking" means something different on each.

---

## Stable surfaces

A breaking change to anything in the table below requires a `MAJOR` bump.

| Surface | Examples | Examples of breaking changes |
|---|---|---|
| **Public Python API** | symbols re-exported from `godot_e2e/__init__.py` (`GodotE2E`, error classes, type wrappers like `Vector2`) | renaming a method, removing a parameter, changing return type, raising a different exception class for the same condition |
| **Wire protocol** | command names, request/response shape, type tags (`_t: "v2"` etc.), the 4-byte length-prefix framing | renaming a command, removing a field, changing the framing header, changing the meaning of an existing field |
| **Addon API** | autoload name (`AutomationServer`), command-line flags (`--e2e`, `--e2e-port`, `--e2e-port-file`, `--e2e-token`, `--e2e-log`), `addons/godot_e2e/` directory layout | renaming the autoload, removing or renaming a flag, moving the addon to a different directory |
| **pytest fixtures** | fixture names (`game`, `game_fresh`), config keys (`godot_e2e_project_path`, env `GODOT_E2E_PROJECT_PATH`, `GODOT_PATH`), `@pytest.mark.godot_project` | renaming a fixture, changing what gets reset between tests in a way that breaks existing test ordering |

---

## Explicitly **not** stable

These can change in any release without a major bump:

- **Internal helpers.** Anything not exported from `__init__.py`, including `GodotClient`, `GodotLauncher` internals, and any private name (leading `_`).
- **New commands within the same minor.** A wire command added in `1.x.0` may iterate on its shape until `1.(x+1).0`.
- **Error message text.** Match on exception class, not on message strings.
- **Log output format.** The `--e2e-log` content is for humans; do not parse it.
- **Test-output directory layout.** `test_output/...` paths can be reorganized.
- **Default port and timeout values.** Configure explicitly if you depend on them.
- **Type-tag set for new Godot types.** Adding a new `_t` tag is non-breaking; removing or renaming an existing one is.

---

## Compatibility window

- **Godot:** tested against Godot 4.x stable. A new minor of godot-e2e may require a newer Godot 4.x minor; this will be called out in the changelog.
- **Python:** tested against Python 3.9+. Dropping a Python version is a `MAJOR` change.

---

## How a breaking change reaches users

1. Discussion in an issue, with the affected surface tagged.
2. Pre-announcement in `docs/update/next.md` under "Changed" with a `BREAKING:` prefix.
3. One minor of deprecation warnings on the affected entry point, where feasible.
4. Major version bump on release.
5. Migration notes in the archived `vX.Y.Z.md` file.

For features added inside the same minor, we may iterate freely until the following release — the surface is considered "stabilizing", not stable, until the minor ships.
