"""CLI entry point for godot-e2e.

Usage:
    godot-e2e [pytest-args...]
    godot-e2e tests/ -v
    godot-e2e --godot-path /path/to/godot tests/ -v
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    args = sys.argv[1:]

    # Extract --godot-path before forwarding to pytest.
    godot_path = None
    filtered: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--godot-path":
            if i + 1 >= len(args):
                print("error: --godot-path requires a value", file=sys.stderr)
                raise SystemExit(2)
            godot_path = args[i + 1]
            i += 2
        elif args[i].startswith("--godot-path="):
            godot_path = args[i].split("=", 1)[1]
            i += 1
        else:
            filtered.append(args[i])
            i += 1

    if godot_path:
        os.environ["GODOT_PATH"] = godot_path

    import pytest

    raise SystemExit(pytest.main(filtered))


if __name__ == "__main__":
    main()
