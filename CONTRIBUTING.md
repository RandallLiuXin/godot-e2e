# Contributing to godot-e2e

Thank you for your interest in contributing. This document covers everything you need to get started.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Running Tests](#running-tests)
- [Code Style Conventions](#code-style-conventions)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Commit Message Format](#commit-message-format)
- [Architecture Overview](#architecture-overview)
- [Adding New Commands](#adding-new-commands)

---

## Development Environment Setup

### Prerequisites

- Python 3.9 or later
- Godot 4.x (the `godot` or `godot4` binary must be on your PATH, or set via `GODOT_PATH`)
- Git

### Steps

1. **Clone the repository**

   ```bash
   git clone https://github.com/RandallLiuXin/godot-e2e.git
   cd godot-e2e
   ```

2. **Install the Python client in editable mode**

   ```bash
   pip install -e .
   ```

   For development dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

3. **Copy the GDScript addon into your Godot project**

   Copy the `addons/godot_e2e/` directory into your Godot project's `addons/` folder and enable it in **Project > Project Settings > Plugins**.

4. **Set the Godot executable path**

   The test launcher needs to know where your Godot binary is. Set the environment variable:

   ```bash
   export GODOT_PATH=/path/to/godot          # Linux / macOS
   set GODOT_PATH=C:\path\to\godot.exe       # Windows
   ```

   Alternatively, set `godot_path` in your project's `pyproject.toml` under `[tool.godot-e2e]`.

5. **Verify the setup**

   ```bash
   godot-e2e tests/ -v
   ```

   This requires a configured Godot binary (`GODOT_PATH` env var or on `PATH`).

---

## Running Tests

### Unit and integration tests

```bash
godot-e2e tests/ -v
```

### Example project E2E tests

These require a Godot binary and launch a real game process:

```bash
godot-e2e examples/platformer/tests/e2e/ -v
```

### Run a specific test file

```bash
godot-e2e tests/test_client.py -v
```

### Useful pytest flags

| Flag | Effect |
|------|--------|
| `-v` | Verbose output |
| `-s` | Show print/log output (do not capture) |
| `-k <expr>` | Run tests whose names match the expression |
| `--tb=short` | Shorter traceback format |

---

## Code Style Conventions

### Python

- Follow the existing code style in `python/godot_e2e/`.
- Type hints are encouraged for all public functions and methods.
- Do not add unnecessary abstractions, compatibility shims, or wrapper layers. Delete old code rather than wrapping it.
- Keep functions focused. If a function is hard to name, it is probably doing too much.
- Maximum line length: 100 characters (consistent with the existing codebase).
- No external formatting tools are enforced, but the code should be readable and consistent with its surroundings.

### GDScript

- Follow the [Godot GDScript style guide](https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_styleguide.html).
- Use static typing wherever practical (`var x: int`, `func foo(n: Node) -> String:`).
- Prefer `@warning_ignore` annotations over suppressing warnings by restructuring code.
- Keep the server state machine logic in `e2e_server.gd` clean and linear; avoid deep nesting.

---

## Submitting a Pull Request

1. **Fork** the repository and create a branch from `main`:

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes** and ensure all tests pass.

3. **Update `docs/update/next.md`** — add an entry under the appropriate category describing your change. This is **required** for every pull request.

4. **Update `CHANGELOG.md`** under the `[Unreleased]` section if your change is user-facing.

5. **Update documentation** in `docs/` if you are changing or adding public API surface.

6. **Push** your branch and open a pull request against `main`.

7. Fill in the pull request template completely. Incomplete templates will be asked to be revised before review.

8. A maintainer will review the PR. Be prepared to iterate based on feedback.

### Branch naming

| Type | Pattern |
|------|---------|
| Feature | `feat/<short-description>` |
| Bug fix | `fix/<short-description>` |
| Documentation | `docs/<short-description>` |
| Refactor | `refactor/<short-description>` |
| Tests | `test/<short-description>` |

---

## Reporting Bugs

Use the [Bug Report issue template](.github/ISSUE_TEMPLATE/bug_report.md) on GitHub. Include:

- A clear description of the bug
- Exact reproduction steps
- Your environment (OS, Godot version, Python version, godot-e2e version)
- Any relevant logs or screenshots

Do not open a GitHub issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) instead.

---

## Commit Message Format

Use the imperative mood in the subject line. Keep the subject under 72 characters. Add a blank line before the body if more explanation is needed.

```
Add wait_for_property helper to Python client

Expose the existing poll loop as a named public method so tests can
wait for a node property to reach an expected value without writing
custom loops.
```

Avoid:
- "Added ...", "Adding ..." (use "Add ...")
- "Fix bug" (too vague; name the bug)
- Trailing punctuation in the subject line

Reference issues when relevant: `Fixes #42` in the commit body or PR description.

---

## Architecture Overview

A full description of the system design is in [docs/architecture.md](docs/architecture.md).

In brief:

- **`addons/godot_e2e/`** - GDScript addon. Runs an in-process TCP server inside the Godot game. Accepts JSON commands over a length-prefixed framing protocol and returns JSON responses. The server only activates when the game is launched with the `--e2e` flag.
- **`python/godot_e2e/`** - Python client library. Connects to the TCP server, serializes commands, deserializes responses, and exposes a synchronous blocking API. Also contains the pytest plugin (`fixtures.py`) that manages game process lifecycle.
- **`tests/`** - Unit and integration tests for the Python client.
- **`examples/`** - Example Godot projects with E2E test suites demonstrating real usage patterns.

---

## Adding New Commands

Adding a new command requires changes on both sides.

### 1. GDScript side (`addons/godot_e2e/e2e_server.gd`)

Add a handler in the `_dispatch_command` function (or equivalent dispatch table):

```gdscript
"my_new_command":
    return _handle_my_new_command(payload)
```

Implement `_handle_my_new_command`:

```gdscript
func _handle_my_new_command(payload: Dictionary) -> Dictionary:
    var node_path: String = payload.get("node_path", "")
    var node := get_node_or_null(node_path)
    if node == null:
        return {"error": "node_not_found", "path": node_path}
    # ... command logic ...
    return {"ok": true}
```

Return a `Dictionary` with either a result payload or an `"error"` key.

### 2. Python side (`python/godot_e2e/client.py`)

Add a method to `GodotE2EClient`:

```python
def my_new_command(self, node_path: str) -> dict:
    """Brief description of what this command does."""
    return self._send({"cmd": "my_new_command", "node_path": node_path})
```

If the command is commonly used in tests, add a high-level helper in `python/godot_e2e/helpers.py`.

### 3. Tests

Add tests in `tests/` that cover:
- The happy path
- Missing or invalid `node_path`
- Any edge cases specific to the command

### 4. Documentation

Update `docs/api-reference.md` with the new command, its parameters, return value, and a short example.
