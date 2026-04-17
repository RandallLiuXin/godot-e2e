# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-16

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

[0.1.0]: https://github.com/RandallLiuXin/godot-e2e/releases/tag/v0.1.0
