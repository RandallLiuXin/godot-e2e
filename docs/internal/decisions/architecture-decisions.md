# Architecture Decision Records

Internal design decisions for godot-e2e. Each ADR captures a choice that has shaped the codebase enough that the rationale is worth preserving — so future contributors and agents do not re-litigate settled decisions, and so when constraints change, the original assumptions can be revisited.

Format: terse. A few bullets per decision is enough. Add new ADRs at the bottom; never edit history.

---

## D1: TCP loopback + length-prefixed JSON wire protocol

- The protocol is a 4-byte big-endian length prefix followed by a UTF-8 JSON payload, over a `127.0.0.1` TCP socket.
- Considered alternatives:
  - **Unix domain sockets** — Windows support is messier than just using TCP loopback.
  - **Named pipes / Windows mailslots** — platform-specific glue not worth it for the throughput we need.
  - **protobuf / msgpack** — adds a code-generation step and a hard dependency on both Python and GDScript sides; wire volume is small (commands at human-step pace), so JSON's verbosity has no measurable cost.
- Authentication via random `--e2e-token` keeps the surface safe for local-only use; binding to `127.0.0.1` enforces the locality. Production builds without `--e2e` never open a socket.

---

## D2: Synchronous Python API (no `async`/`await`)

- Tests are written in pytest, whose idioms are synchronous. Mixing async into test bodies is a real ergonomic cost for marginal benefit (one game process at a time per test).
- The client serializes commands behind a lock and uses blocking sockets. We accept the small wall-clock cost for the readability win.
- Concurrent test runs are achieved by launching multiple game processes in parallel (auto-port allocation via `--e2e-port=0` + `--e2e-port-file`), not by issuing concurrent commands inside one connection.

---

## D3: No "test event bus" / signal-emit-from-test

- We considered exposing a registry that lets the Python side emit named signals into the running game (and subscribe to game-side signals by name, decoupled from node paths).
- The emit-from-test direction was rejected: it bypasses input simulation, which undermines the end-to-end guarantee. A behaviour testable only via signal emission can pass while the user-facing trigger (button, menu item) is broken — a false-confidence outcome that an e2e tool must not produce.
- The subscribe-by-name direction is largely redundant with `wait_for_signal(path, signal_name)`. The path requirement there is real, but the right fix is a multi-strategy Locator (see [ROADMAP.md](../../../ROADMAP.md) §1), not a parallel naming layer.
- White-box triggering for tests that explicitly opt out of e2e semantics remains available via `call_method`. That is a deliberate, named escape hatch — not a default authoring path.
