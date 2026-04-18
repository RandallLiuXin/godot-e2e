# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/RandallLiuXin/godot-e2e/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/RandallLiuXin/godot-e2e/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/RandallLiuXin/godot-e2e/releases/tag/v1.0.0
